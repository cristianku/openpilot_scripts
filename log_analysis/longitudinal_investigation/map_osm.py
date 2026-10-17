# /// script
# requires-python = ">=3.11"
# dependencies = ["numpy", "pandas", "requests"]
# ///
"""Step 4: classify events with OpenStreetMap (Overpass) + route-direction map matching.

Privacy: only bounding boxes (south, west, north, east) around candidate events are sent;
no log, trajectory, timestamp or video leaves the machine. Overlapping event boxes are
merged (capped in size) to reduce the number of queries. Every request is appended to
out/osm_queries.jsonl (endpoint, bbox, UTC time, HTTP status, bytes). Responses are cached
in out/osm_cache/ and re-used: re-running does not re-query.

Matching (per event, using the GPS trajectory of the event window):
  - trajectory = valid fixes (hasFix, horizontalAccuracy < 20 m), resampled, cumulative
    along-track distance s (m) from the window start
  - a mapped point feature (traffic_signals, crossing, stop, give_way, mini_roundabout) is
    "on route" when it is a node of a road way the trajectory follows AND it lies within
    LATERAL_MAX m of the trajectory; its along-track position is the projection
  - traffic_signals:direction / direction=forward|backward is honoured when present,
    using the order of the node on the way vs the driving direction
  - a roundabout (junction=roundabout|circular way) is "entered" when the trajectory gets
    within ROUNDABOUT_ENTRY_M of the ring geometry; entry s = first such point
  - junctions = nodes of followed ways shared with another road way, on route

Distances are reported relative to the event minimum-speed / standstill point:
  rel = s_feature - s_min   (positive: feature AHEAD of where the car stopped/slowed most)
GPS (+-2..5 m) and OSM placement (signals are mapped at the stop line OR at the junction
centre depending on the mapper) make these +-10..20 m indications, NOT stop-line distances.

Usage: uv run map_osm.py [--offline]   (--offline: cache only, no network)
Output: out/events_mapped.json / .csv
"""

import argparse
import datetime
import hashlib
import json
import math
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import OUT_DIR  # noqa: E402

# (endpoint, attempts, timeout s): the main instance answers 502 when busy, so retry it
ENDPOINTS = [
  ("https://overpass-api.de/api/interpreter", 4, 60),
  ("https://maps.mail.ru/osm/tools/overpass/api/interpreter", 1, 45),
]
USER_AGENT = "psa-longitudinal-investigation/0.1 (local, offline research)"
CACHE_DIR = OUT_DIR / "osm_cache"
QUERY_LOG = OUT_DIR / "osm_queries.jsonl"
PAD_M = 120.0
MAX_BOX_M = 1500.0
LATERAL_MAX = 15.0
ROUNDABOUT_ENTRY_M = 12.0
MATCH_MAX_M = 20.0
EARTH_R = 6371000.0

ROAD_TYPES = ("motorway", "trunk", "primary", "secondary", "tertiary", "unclassified", "residential",
              "living_street", "motorway_link", "trunk_link", "primary_link", "secondary_link",
              "tertiary_link", "road")


# ------------------------------------------------------------------ geometry
def to_xy(lat, lon, lat0, lon0):
  x = math.radians(lon - lon0) * EARTH_R * math.cos(math.radians(lat0))
  y = math.radians(lat - lat0) * EARTH_R
  return x, y


def point_segment(px, py, ax, ay, bx, by):
  """distance from P to segment AB and the parameter u in [0,1]"""
  dx = bx - ax
  dy = by - ay
  L2 = dx * dx + dy * dy
  if L2 <= 1e-9:
    return math.hypot(px - ax, py - ay), 0.0
  u = ((px - ax) * dx + (py - ay) * dy) / L2
  if u < 0.0:
    u = 0.0
  if u > 1.0:
    u = 1.0
  qx = ax + u * dx
  qy = ay + u * dy
  return math.hypot(px - qx, py - qy), u


def project_on_track(px, py, tx, ty, ts):
  """return (lateral distance, along-track s) of P on the polyline (tx, ty) with cumulative ts"""
  best_d = 1e9
  best_s = None
  for i in range(len(tx) - 1):
    d, u = point_segment(px, py, tx[i], ty[i], tx[i + 1], ty[i + 1])
    if d < best_d:
      best_d = d
      best_s = ts[i] + u * (ts[i + 1] - ts[i])
  return best_d, best_s


# ------------------------------------------------------------------ overpass
def bbox_of(lats, lons, pad_m):
  lat_c = float(np.mean(lats))
  dlat = pad_m / EARTH_R * 180.0 / math.pi
  dlon = dlat / math.cos(math.radians(lat_c))
  return [float(np.min(lats)) - dlat, float(np.min(lons)) - dlon, float(np.max(lats)) + dlat, float(np.max(lons)) + dlon]


def box_size_m(b):
  lat_c = (b[0] + b[2]) / 2
  h = (b[2] - b[0]) * math.pi / 180 * EARTH_R
  w = (b[3] - b[1]) * math.pi / 180 * EARTH_R * math.cos(math.radians(lat_c))
  return max(h, w)


def boxes_overlap(a, b):
  if a[2] < b[0] or b[2] < a[0]:
    return False
  if a[3] < b[1] or b[3] < a[1]:
    return False
  return True


def merge_box(a, b):
  return [min(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]), max(a[3], b[3])]


def overpass_query(b):
  s, w, n, e = b
  bb = "%.5f,%.5f,%.5f,%.5f" % (s, w, n, e)
  roads = "|".join(ROAD_TYPES)
  return (
    "[out:json][timeout:60];("
    'node["highway"="traffic_signals"](%s);'
    'node["crossing"="traffic_signals"](%s);'
    'node["highway"="crossing"](%s);'
    'node["highway"="stop"](%s);'
    'node["highway"="give_way"](%s);'
    'node["highway"="mini_roundabout"](%s);'
    'way["junction"~"^(roundabout|circular)$"](%s);'
    'way["highway"~"^(%s)$"](%s);'
    ");out body geom;"
  ) % (bb, bb, bb, bb, bb, bb, bb, roads, bb)


def fetch(b, offline):
  q = overpass_query(b)
  key = hashlib.sha1(q.encode()).hexdigest()[:16]
  path = CACHE_DIR / (key + ".json")
  if path.exists():
    return json.loads(path.read_text())
  if offline:
    return None
  CACHE_DIR.mkdir(parents=True, exist_ok=True)
  attempts = []
  for url, n_try, tmo in ENDPOINTS:
    for k in range(n_try):
      attempts.append((url, tmo, k))
  for url, tmo, k in attempts:
    status = None
    size = 0
    try:
      r = requests.post(url, data={"data": q}, headers={"User-Agent": USER_AGENT}, timeout=tmo)
      status = r.status_code
      size = len(r.content)
      ok = r.status_code == 200
    except Exception as exc:
      ok = False
      status = "error: " + str(exc)[:80]
    with open(QUERY_LOG, "a") as f:
      f.write(json.dumps({
        "utc": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "endpoint": url, "bbox_swne": [round(x, 5) for x in b],
        "bbox_size_m": round(box_size_m(b)), "status": status, "bytes": size, "cache_key": key,
      }) + "\n")
    if ok:
      data = r.json()
      path.write_text(json.dumps(data))
      time.sleep(1.0)
      return data
    time.sleep(4.0 + 4.0 * k)
  return None


# ------------------------------------------------------------------ matching
def classify_event(ev, traj, osm):
  """traj: DataFrame with route_t, gps_lat, gps_lon, v_ego (valid fixes only)"""
  lat0 = float(traj.gps_lat.iloc[0])
  lon0 = float(traj.gps_lon.iloc[0])
  tx = []
  ty = []
  for la, lo in zip(traj.gps_lat, traj.gps_lon):
    x, y = to_xy(la, lo, lat0, lon0)
    tx.append(x)
    ty.append(y)
  # along-track from integrated wheel speed is smoother than GPS distance at low speed;
  # use GPS geometry for projection but wheel odometry for the s coordinate
  ts = [0.0]
  for i in range(1, len(tx)):
    ts.append(ts[-1] + math.hypot(tx[i] - tx[i - 1], ty[i] - ty[i - 1]))
  t_arr = traj.route_t.to_numpy()

  def s_at_time(tq):
    return float(np.interp(tq, t_arr, ts))

  nodes = {}
  ways = []
  for el in osm.get("elements", []):
    if el["type"] == "node":
      nodes[el["id"]] = el
    elif el["type"] == "way" and "geometry" in el:
      ways.append(el)

  # which road ways does the trajectory follow? (point-to-way distance < MATCH_MAX_M,
  # heading compatible within 45 deg)
  followed = {}
  sample_step = max(1, len(tx) // 150)
  for i in range(0, len(tx) - 1, sample_step):
    hx = tx[min(i + 1, len(tx) - 1)] - tx[i]
    hy = ty[min(i + 1, len(tx) - 1)] - ty[i]
    moving = math.hypot(hx, hy) > 0.3
    best = None
    best_d = MATCH_MAX_M
    for w in ways:
      tags = w.get("tags", {})
      if "highway" not in tags and "junction" not in tags:
        continue
      g = w["geometry"]
      for k in range(len(g) - 1):
        ax, ay = to_xy(g[k]["lat"], g[k]["lon"], lat0, lon0)
        bx, by = to_xy(g[k + 1]["lat"], g[k + 1]["lon"], lat0, lon0)
        d, _ = point_segment(tx[i], ty[i], ax, ay, bx, by)
        if d >= best_d:
          continue
        if moving:
          sx = bx - ax
          sy = by - ay
          cosang = abs(sx * hx + sy * hy) / max(1e-6, math.hypot(sx, sy) * math.hypot(hx, hy))
          if cosang < 0.7 and not tags.get("junction"):
            continue
        best_d = d
        best = w
    if best is not None:
      followed[best["id"]] = best

  followed_node_ids = set()
  for w in followed.values():
    for nid in w.get("nodes", []):
      followed_node_ids.add(nid)

  feats = []
  # point features
  for nid, n in nodes.items():
    tags = n.get("tags", {})
    kind = None
    if tags.get("highway") == "traffic_signals":
      kind = "traffic_signals"
    elif tags.get("crossing") == "traffic_signals" or tags.get("crossing:signals") == "yes":
      kind = "signal_crossing"
    elif tags.get("highway") == "crossing":
      kind = "crossing"
    elif tags.get("highway") == "stop":
      kind = "stop_sign"
    elif tags.get("highway") == "give_way":
      kind = "give_way"
    elif tags.get("highway") == "mini_roundabout":
      kind = "mini_roundabout"
    if kind is None:
      continue
    if "lat" not in n:
      continue
    px, py = to_xy(n["lat"], n["lon"], lat0, lon0)
    lat_d, s = project_on_track(px, py, tx, ty, ts)
    if lat_d > LATERAL_MAX or s is None:
      continue
    on_way = nid in followed_node_ids
    direction = tags.get("traffic_signals:direction") or tags.get("direction")
    dir_ok = None
    if direction in ("forward", "backward"):
      dir_ok = direction_matches(nid, direction, followed, lat0, lon0, tx, ty)
    feats.append({"kind": kind, "osm_id": nid, "lateral_m": round(lat_d, 1), "s": round(s, 1),
                  "on_followed_way": on_way, "direction_tag": direction, "direction_ok": dir_ok})

  # roundabouts entered
  for w in ways:
    tags = w.get("tags", {})
    if tags.get("junction") not in ("roundabout", "circular"):
      continue
    g = w["geometry"]
    ring = []
    for p in g:
      ring.append(to_xy(p["lat"], p["lon"], lat0, lon0))
    entry_i = None
    for i in range(len(tx)):
      dmin = 1e9
      for k in range(len(ring) - 1):
        d, _ = point_segment(tx[i], ty[i], ring[k][0], ring[k][1], ring[k + 1][0], ring[k + 1][1])
        if d < dmin:
          dmin = d
      if dmin < ROUNDABOUT_ENTRY_M:
        entry_i = i
        break
    if entry_i is None:
      continue
    # ring size (diameter estimate)
    xs = []
    ys = []
    for r in ring:
      xs.append(r[0])
      ys.append(r[1])
    diam = max(max(xs) - min(xs), max(ys) - min(ys))
    feats.append({"kind": "roundabout", "osm_id": w["id"], "lateral_m": 0.0, "s": round(ts[entry_i], 1),
                  "on_followed_way": True, "direction_tag": None, "direction_ok": None,
                  "ring_extent_m": round(diam, 0), "name": tags.get("name")})

  # junctions (nodes of followed ways shared with another road way)
  count_by_node = {}
  for w in ways:
    tags = w.get("tags", {})
    if tags.get("highway") not in ROAD_TYPES:
      continue
    if tags.get("highway") == "service" and tags.get("service") in ("parking_aisle", "driveway"):
      continue
    for nid in w.get("nodes", []):
      count_by_node[nid] = count_by_node.get(nid, 0) + 1
  for w in followed.values():
    nids = w.get("nodes", [])
    g = w["geometry"]
    for k in range(len(nids)):
      nid = nids[k]
      if count_by_node.get(nid, 0) < 2:
        continue
      px, py = to_xy(g[k]["lat"], g[k]["lon"], lat0, lon0)
      lat_d, s = project_on_track(px, py, tx, ty, ts)
      if lat_d > LATERAL_MAX or s is None:
        continue
      feats.append({"kind": "junction", "osm_id": nid, "lateral_m": round(lat_d, 1), "s": round(s, 1),
                    "on_followed_way": True, "direction_tag": None, "direction_ok": None})

  s_min = s_at_time(ev["t_min"])
  s_onset = None
  t_on = ev.get("t_onset_plan05") or ev.get("t_onset_plan")
  if t_on is not None:
    s_onset = s_at_time(t_on)
  for f in feats:
    f["rel_to_min_m"] = round(f["s"] - s_min, 1)
    f["rel_to_onset_m"] = None if s_onset is None else round(f["s"] - s_onset, 1)

  road_names = []
  for w in followed.values():
    name = w.get("tags", {}).get("name")
    if name and name not in road_names:
      road_names.append(name)
  highway_classes = []
  for w in followed.values():
    hc = w.get("tags", {}).get("highway")
    if hc and hc not in highway_classes:
      highway_classes.append(hc)
  maxspeeds = []
  for w in followed.values():
    ms = w.get("tags", {}).get("maxspeed")
    if ms and ms not in maxspeeds:
      maxspeeds.append(ms)
  return feats, road_names, highway_classes, maxspeeds


def direction_matches(nid, direction, followed, lat0, lon0, tx, ty):
  """forward = the signal applies to traffic moving in the way's node order"""
  for w in followed.values():
    nids = w.get("nodes", [])
    if nid not in nids:
      continue
    k = nids.index(nid)
    g = w["geometry"]
    if k + 1 < len(g):
      ax, ay = to_xy(g[k]["lat"], g[k]["lon"], lat0, lon0)
      bx, by = to_xy(g[k + 1]["lat"], g[k + 1]["lon"], lat0, lon0)
    elif k > 0:
      ax, ay = to_xy(g[k - 1]["lat"], g[k - 1]["lon"], lat0, lon0)
      bx, by = to_xy(g[k]["lat"], g[k]["lon"], lat0, lon0)
    else:
      return None
    # vehicle heading near the node: nearest trajectory step
    best_i = 0
    best_d = 1e9
    for i in range(len(tx) - 1):
      d = math.hypot(tx[i] - ax, ty[i] - ay)
      if d < best_d:
        best_d = d
        best_i = i
    hx = tx[min(best_i + 3, len(tx) - 1)] - tx[max(best_i - 3, 0)]
    hy = ty[min(best_i + 3, len(tx) - 1)] - ty[max(best_i - 3, 0)]
    along = (bx - ax) * hx + (by - ay) * hy
    if direction == "forward":
      return along > 0
    return along < 0
  return None


def classify(feats, kind):
  """event class from features near the minimum: rel_to_min in [-15, +X]"""
  sig = []
  rb = []
  junc = []
  other = []
  for f in feats:
    rel = f["rel_to_min_m"]
    if f["kind"] in ("traffic_signals", "signal_crossing"):
      if f.get("direction_ok") is False:
        continue
      if -25.0 <= rel <= 80.0:
        sig.append(f)
    elif f["kind"] in ("roundabout", "mini_roundabout"):
      # the speed minimum of a roundabout passage is often inside the ring (after entry)
      if -60.0 <= rel <= 150.0:
        rb.append(f)
    elif f["kind"] == "junction":
      if -10.0 <= rel <= 60.0:
        junc.append(f)
    elif f["kind"] in ("stop_sign", "give_way", "crossing"):
      if -10.0 <= rel <= 60.0:
        other.append(f)
  cls = "unclassified"
  if sig and (not rb or min(abs(x["rel_to_min_m"]) for x in sig) <= min(abs(x["rel_to_min_m"]) for x in rb)):
    cls = "traffic_light"
  elif rb:
    cls = "roundabout"
  elif junc or other:
    cls = "other_intersection"
  return cls, sig, rb, junc, other


def main():
  ap = argparse.ArgumentParser()
  ap.add_argument("--offline", action="store_true")
  args = ap.parse_args()
  events = json.loads((OUT_DIR / "events_analyzed.json").read_text())

  # trajectories and boxes
  trajs = {}
  boxes = []
  frames = {}
  skipped_ids = set()
  for ev in events:
    # map only what can inform the diagnosis: openpilot-controlled stops / near-stops,
    # openpilot slowdowns to < 35 km/h or overridden with gas, plus driver-driven
    # complete stops (human baseline at the same places)
    selected = False
    if ev.get("analysable") and ev["kind"] in ("stop", "near_stop"):
      selected = True
    if ev.get("analysable") and ev["kind"] == "slowdown":
      if ev["v_min_kph"] < 35 or ev.get("gas_override_during_approach"):
        selected = True
    if ev["kind"] == "stop":
      selected = True
    if not selected:
      skipped_ids.add(ev["event_id"])
      continue
    if ev["route"] not in frames:
      frames[ev["route"]] = pd.read_csv(OUT_DIR / "timeline" / (ev["route"] + ".csv.gz"),
                                        usecols=["route_t", "gps_lat", "gps_lon", "gps_fix", "gps_acc", "v_ego"])
    df = frames[ev["route"]]
    w = df[(df.route_t >= ev["t_window_start"]) & (df.route_t <= ev["t_window_end"])]
    w = w[(w.gps_fix > 0.5) & (w.gps_acc < 20) & (w.gps_lat != 0)]
    w = w.iloc[::2]  # 10 Hz is plenty
    if len(w) < 20:
      continue
    trajs[ev["event_id"]] = w
    boxes.append((bbox_of(w.gps_lat.to_numpy(), w.gps_lon.to_numpy(), PAD_M), [ev["event_id"]]))

  # merge overlapping boxes (bounded size)
  merged = []
  for b, ids in boxes:
    placed = False
    for m in merged:
      if boxes_overlap(m[0], b):
        nb = merge_box(m[0], b)
        if box_size_m(nb) <= MAX_BOX_M:
          m[0] = nb
          m[1].extend(ids)
          placed = True
          break
    if not placed:
      merged.append([b, list(ids)])
  print(len(trajs), "events with GPS,", len(merged), "map boxes")

  osm_by_event = {}
  for b, ids in merged:
    data = fetch(b, args.offline)
    for eid in ids:
      osm_by_event[eid] = data

  out = []
  for ev in events:
    eid = ev["event_id"]
    row = dict(ev)
    if eid in skipped_ids:
      row["map_class"] = "not_mapped"
    else:
      row["map_class"] = "no_gps"
    row["map_features"] = []
    if eid in trajs:
      data = osm_by_event.get(eid)
      if data is None:
        row["map_class"] = "map_unavailable"
      else:
        feats, names, classes, maxspeeds = classify_event(ev, trajs[eid], data)
        cls, sig, rb, junc, other = classify(feats, ev["kind"])
        row["map_class"] = cls
        row["map_features"] = feats
        row["road_names"] = names
        row["road_classes"] = classes
        row["osm_maxspeed"] = maxspeeds
        row["nearest_signal_rel_m"] = None if not sig else min(sig, key=lambda f: abs(f["rel_to_min_m"]))["rel_to_min_m"]
        row["nearest_roundabout_rel_m"] = None if not rb else min(rb, key=lambda f: abs(f["rel_to_min_m"]))["rel_to_min_m"]
        row["roundabout_entry_rel_onset_m"] = None
        if rb and rb[0].get("rel_to_onset_m") is not None:
          row["roundabout_entry_rel_onset_m"] = min(rb, key=lambda f: abs(f["rel_to_min_m"]))["rel_to_onset_m"]
        row["signal_rel_onset_m"] = None
        if sig and sig[0].get("rel_to_onset_m") is not None:
          row["signal_rel_onset_m"] = min(sig, key=lambda f: abs(f["rel_to_min_m"]))["rel_to_onset_m"]
        row["n_crossings_ahead"] = len([f for f in other if f["kind"] == "crossing"])
    out.append(row)
  (OUT_DIR / "events_mapped.json").write_text(json.dumps(out, indent=1, default=str))
  flat = []
  for ev in out:
    r = {}
    for k, val in ev.items():
      if isinstance(val, (dict, list)):
        r[k] = json.dumps(val, default=str)
      else:
        r[k] = val
    flat.append(r)
  pd.DataFrame(flat).to_csv(OUT_DIR / "events_mapped.csv", index=False)
  counts = {}
  for ev in out:
    counts[ev["map_class"]] = counts.get(ev["map_class"], 0) + 1
  print(counts)


if __name__ == "__main__":
  main()
