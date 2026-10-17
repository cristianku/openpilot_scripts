# /// script
# requires-python = ">=3.11"
# dependencies = ["numpy", "pandas", "matplotlib"]
# ///
"""Step 5: per-event figures (telemetry + local map sketch) for the HTML report.

Telemetry figure (x = seconds relative to the event minimum / standstill):
  1 speed: vEgo, set speed (vCruise), model predicted speed at +2 s; engaged shading
  2 accel: model desiredAcceleration, planner aTarget, carControl accel, PSA 0x2B6
           MDD_DESIRED_DECELERATION (only while MDD_DECEL_CONTROL_REQ=1), measured aEgo
  3 strips: planner source, DEC mode, PSA mode (brake / torque), driver pedals
  4 distances: vision lead dRel, model predicted stop distance, model position at +4 s,
           and (for stops) the distance actually left to the standstill point

Map sketch: GPS trajectory (local metres, coloured by speed) with the OSM features of
the cached Overpass answer. Drawn locally; no map tiles are downloaded.

Usage: uv run plots.py [event_id ...]     (default: every event selected by report.py rules)
Output: out/figures/<event_id>_telemetry.png, <event_id>_map.png, <event_id>_series.json
"""

import json
import math
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import OUT_DIR  # noqa: E402

FIG_DIR = OUT_DIR / "figures"
DT = 0.05
SRC_COLORS = {0: "#9e9e9e", 1: "#e53935", 2: "#fb8c00", 3: "#fdd835", 4: "#1e88e5"}
SRC_NAMES = {0: "cruise", 1: "lead0", 2: "lead1", 3: "lead2", 4: "e2e"}
EARTH_R = 6371000.0

# axes rectangle of the telemetry figure, in figure fractions: used by the HTML click-to-time
FIG_LEFT = 0.08
FIG_RIGHT = 0.97


def strip(ax, x, values, colors, y0, h, label):
  start = 0
  n = len(values)
  for i in range(1, n + 1):
    if i == n or values[i] != values[start]:
      val = values[start]
      if val in colors:
        ax.axvspan(x[start], x[min(i, n - 1)], ymin=y0, ymax=y0 + h, color=colors[val], lw=0)
      start = i
  ax.text(x[0], (y0 + h / 2), " " + label, transform=ax.get_xaxis_transform(), va="center", fontsize=7)


def telemetry_figure(ev, df):
  t0 = max(ev["t_window_start"], ev["t_peak"] - 12.0)
  t1 = min(ev["t_window_end"], ev["t_min"] + 15.0)
  w = df[(df.route_t >= t0) & (df.route_t <= t1)].reset_index(drop=True)
  if len(w) < 20:
    return None
  x = (w.route_t - ev["t_min"]).to_numpy()
  eng = w.cc_long_active.fillna(0).to_numpy() > 0.5

  fig, axs = plt.subplots(4, 1, figsize=(11, 10), sharex=True,
                          gridspec_kw={"height_ratios": [2.2, 2.4, 1.0, 1.8]})
  fig.subplots_adjust(left=FIG_LEFT, right=FIG_RIGHT, top=0.95, bottom=0.06, hspace=0.08)

  # ---------- speed
  ax = axs[0]
  ax.plot(x, w.v_ego * 3.6, color="k", lw=1.6, label="vEgo")
  ax.plot(x, w.md_v_2s * 3.6, color="#1e88e5", lw=0.8, alpha=0.7, label="modello v(+2 s)")
  vc = w.v_cruise.where(w.v_cruise < 250)
  ax.plot(x, vc, color="#7cb342", lw=1.0, ls="--", label="set speed (vCruise)")
  for i in range(len(x) - 1):
    if eng[i]:
      ax.axvspan(x[i], x[i + 1], color="#c8e6c9", alpha=0.35, lw=0)
  ax.set_ylabel("km/h")
  ax.legend(loc="upper right", fontsize=7, ncol=3)
  ax.set_title("%s  %s  seg %s  t_seg %.1f s  [%s]  (verde = openpilot long attivo)" % (
    ev["event_id"], ev["route"], ev["seg"], ev["seg_t"], ev.get("map_class", ev["kind"])), fontsize=9)
  ax.grid(alpha=0.3)

  # ---------- accel
  ax = axs[1]
  ax.plot(x, w.md_des_accel, color="#1e88e5", lw=1.0, label="modelV2 desiredAcceleration")
  ax.plot(x, w.plan_a_target, color="#8e24aa", lw=1.0, label="longitudinalPlan aTarget")
  ax.plot(x, w.cc_accel.where(eng), color="#00897b", lw=1.0, ls="--", label="carControl accel")
  brake_cmd = w.can_decel.where(w.can_decel_req > 0.5)
  ax.plot(x, brake_cmd, color="#e53935", lw=1.4, label="PSA 0x2B6 decel (freno)")
  ax.plot(x, w.a_ego, color="k", lw=1.4, alpha=0.8, label="aEgo misurata")
  ax.axhline(0, color="k", lw=0.5)
  ax.axhline(-0.5, color="#e53935", lw=0.4, ls=":")
  ax.set_ylim(-3.0, 2.0)
  ax.set_ylabel("m/s²")
  ax.legend(loc="lower left", fontsize=7, ncol=3)
  ax.grid(alpha=0.3)

  # ---------- strips
  ax = axs[2]
  ax.set_yticks([])
  src = w.plan_source.fillna(-1).astype(int).to_numpy()
  strip(ax, x, list(src), SRC_COLORS, 0.75, 0.22, "planner source")
  dec = w.dec_state.fillna(-1).astype(int).to_numpy()
  strip(ax, x, list(dec), {0: "#bdbdbd", 1: "#1e88e5"}, 0.5, 0.22, "DEC (grigio acc, blu blended)")
  mode = []
  for i in range(len(w)):
    if not eng[i]:
      mode.append(-1)
    elif w.can_decel_req.iloc[i] > 0.5:
      mode.append(1)
    else:
      mode.append(0)
  strip(ax, x, mode, {0: "#66bb6a", 1: "#e53935"}, 0.25, 0.22, "PSA modo (verde coppia, rosso freno)")
  ped = []
  for i in range(len(w)):
    if w.brake_pressed.iloc[i] > 0.5:
      ped.append(1)
    elif w.gas_pressed.iloc[i] > 0.5:
      ped.append(2)
    else:
      ped.append(0)
  strip(ax, x, ped, {1: "#b71c1c", 2: "#f9a825"}, 0.0, 0.22, "pedali (rosso freno, giallo gas)")
  handles = []
  for k in (0, 1, 2, 4):
    handles.append(plt.Rectangle((0, 0), 1, 1, color=SRC_COLORS[k], label=SRC_NAMES[k]))
  ax.legend(handles=handles, loc="upper right", fontsize=6, ncol=4)

  # ---------- distances
  ax = axs[3]
  lead = w.lead_d.where(w.lead_present > 0.5)
  ax.plot(x, lead, color="#e53935", lw=1.2, label="lead dRel (visione)")
  ax.plot(x, w.md_stop_x, color="#1e88e5", lw=1.2, label="modello: distanza di arresto prevista")
  ax.plot(x, w.md_x_4s, color="#90caf9", lw=0.8, label="modello: posizione a +4 s")
  if ev["kind"] == "stop":
    v = w.v_ego.to_numpy()
    i_min = int(np.argmin(np.abs(x)))
    rem = np.full(len(x), np.nan)
    acc = 0.0
    for i in range(i_min - 1, -1, -1):
      acc += v[i] * DT
      rem[i] = acc
    ax.plot(x, rem, color="k", lw=1.2, ls="--", label="distanza effettivamente percorsa fino all'arresto")
  ax.set_ylim(0, 80)
  ax.set_ylabel("m")
  ax.set_xlabel("s rispetto al minimo di velocità / arresto (t=0 = route_t %.1f s)" % ev["t_min"])
  ax.legend(loc="upper right", fontsize=7, ncol=2)
  ax.grid(alpha=0.3)
  for a in axs:
    a.axvline(0, color="k", lw=0.6, ls=":")
    if ev.get("t_onset_plan05") is not None:
      a.axvline(ev["t_onset_plan05"] - ev["t_min"], color="#8e24aa", lw=0.6, ls="--")
  axs[0].set_xlim(x[0], x[-1])
  FIG_DIR.mkdir(parents=True, exist_ok=True)
  path = FIG_DIR / (ev["event_id"] + "_telemetry.png")
  fig.savefig(path, dpi=90)
  plt.close(fig)

  # compact series for the click-to-time inspector (2 Hz)
  series = []
  for i in range(0, len(w), 10):
    r = w.iloc[i]
    series.append([
      round(float(x[i]), 2), round(float(r.route_t), 2), int(r.seg), round(float(r.seg_t), 1),
      None if r.fcam_frame != r.fcam_frame else int(r.fcam_frame),
      round(float(r.v_ego) * 3.6, 1), round(float(r.md_des_accel), 2), round(float(r.plan_a_target), 2),
      SRC_NAMES.get(int(r.plan_source), "?") if r.plan_source == r.plan_source else None,
      None if r.dec_state != r.dec_state else ("blended" if int(r.dec_state) == 1 else "acc"),
      None if r.cc_accel != r.cc_accel else round(float(r.cc_accel), 2),
      round(float(r.can_decel), 2) if r.can_decel_req > 0.5 else None,
      round(float(r.a_ego), 2),
      round(float(r.lead_d), 1) if r.lead_present > 0.5 else None,
      None if r.md_stop_x != r.md_stop_x else round(float(r.md_stop_x), 1),
    ])
  meta = {"x0": float(x[0]), "x1": float(x[-1]), "left": FIG_LEFT, "right": FIG_RIGHT, "rows": series}
  (FIG_DIR / (ev["event_id"] + "_series.json")).write_text(json.dumps(meta))
  return path


def map_figure(ev, df, osm):
  w = df[(df.route_t >= ev["t_window_start"]) & (df.route_t <= ev["t_window_end"])]
  w = w[(w.gps_fix > 0.5) & (w.gps_acc < 20) & (w.gps_lat != 0)]
  if len(w) < 20:
    return None
  lat0 = float(w.gps_lat.iloc[0])
  lon0 = float(w.gps_lon.iloc[0])

  def xy(lat, lon):
    return (math.radians(lon - lon0) * EARTH_R * math.cos(math.radians(lat0)), math.radians(lat - lat0) * EARTH_R)

  tx = []
  ty = []
  for la, lo in zip(w.gps_lat, w.gps_lon):
    p = xy(la, lo)
    tx.append(p[0])
    ty.append(p[1])
  fig, ax = plt.subplots(figsize=(5.5, 5.5))
  pad = 60
  xmin = min(tx) - pad
  xmax = max(tx) + pad
  ymin = min(ty) - pad
  ymax = max(ty) + pad
  if osm is not None:
    for el in osm.get("elements", []):
      if el["type"] != "way" or "geometry" not in el:
        continue
      gx = []
      gy = []
      for p in el["geometry"]:
        q = xy(p["lat"], p["lon"])
        gx.append(q[0])
        gy.append(q[1])
      tags = el.get("tags", {})
      if tags.get("junction") in ("roundabout", "circular"):
        ax.plot(gx, gy, color="#8e24aa", lw=3, alpha=0.6)
      else:
        ax.plot(gx, gy, color="#bdbdbd", lw=1.5 if tags.get("highway") in ("primary", "secondary", "trunk") else 0.8)
    for el in osm.get("elements", []):
      if el["type"] != "node" or "lat" not in el:
        continue
      tags = el.get("tags", {})
      q = xy(el["lat"], el["lon"])
      if q[0] < xmin or q[0] > xmax or q[1] < ymin or q[1] > ymax:
        continue
      if tags.get("highway") == "traffic_signals":
        ax.plot(q[0], q[1], marker="^", color="#e53935", ms=9, mec="k")
      elif tags.get("crossing") == "traffic_signals":
        ax.plot(q[0], q[1], marker="^", color="#ff8a80", ms=7, mec="k")
      elif tags.get("highway") == "crossing":
        ax.plot(q[0], q[1], marker="s", color="#fff59d", ms=5, mec="k")
      elif tags.get("highway") in ("give_way", "stop"):
        ax.plot(q[0], q[1], marker="v", color="#ffb300", ms=7, mec="k")
      elif tags.get("highway") == "mini_roundabout":
        ax.plot(q[0], q[1], marker="o", color="#8e24aa", ms=9, mec="k")
  sc = ax.scatter(tx, ty, c=(w.v_ego * 3.6).to_numpy(), cmap="viridis", s=6, zorder=5)
  plt.colorbar(sc, ax=ax, fraction=0.04, label="km/h")
  t_arr = w.route_t.to_numpy()

  def mark(tq, color, label):
    if tq is None:
      return
    i = int(np.argmin(np.abs(t_arr - tq)))
    ax.plot(tx[i], ty[i], marker="o", ms=11, mfc="none", mec=color, mew=2, zorder=6, label=label)

  mark(ev.get("t_onset_plan05"), "#8e24aa", "inizio richiesta < -0.5")
  mark(ev["t_min"], "#e53935", "minimo/arresto")
  ax.annotate("", xy=(tx[-1], ty[-1]), xytext=(tx[-6], ty[-6]), arrowprops=dict(arrowstyle="->", color="k"))
  ax.set_xlim(xmin, xmax)
  ax.set_ylim(ymin, ymax)
  ax.set_aspect("equal")
  ax.set_xlabel("m (est)")
  ax.set_ylabel("m (nord)")
  ax.legend(fontsize=7, loc="best")
  ax.set_title("%s mappa OSM locale (▲ semaforo, ■ attraversamento, viola rotonda)" % ev["event_id"], fontsize=8)
  fig.tight_layout()
  path = FIG_DIR / (ev["event_id"] + "_map.png")
  fig.savefig(path, dpi=85)
  plt.close(fig)
  return path


def load_osm_for(ev):
  # map_osm caches answers by query hash; the event record keeps nothing but features,
  # so find the cached box that contains this event's minimum point
  cache = OUT_DIR / "osm_cache"
  qlog = OUT_DIR / "osm_queries.jsonl"
  if not qlog.exists() or ev.get("lat_min") is None:
    return None
  best = None
  for line in qlog.read_text().splitlines():
    q = json.loads(line)
    if q["status"] != 200:
      continue
    s, w_, n, e = q["bbox_swne"]
    if s <= ev["lat_min"] <= n and w_ <= ev["lon_min"] <= e:
      best = cache / (q["cache_key"] + ".json")
  if best is None or not best.exists():
    return None
  return json.loads(best.read_text())


def main():
  events = json.loads((OUT_DIR / "events_mapped.json").read_text())
  wanted = set(sys.argv[1:])
  sel_path = OUT_DIR / "selected_events.json"
  if not wanted and sel_path.exists():
    wanted = set(json.loads(sel_path.read_text()))
  frames = {}
  n = 0
  for ev in events:
    if wanted and ev["event_id"] not in wanted:
      continue
    if ev["route"] not in frames:
      frames[ev["route"]] = pd.read_csv(OUT_DIR / "timeline" / (ev["route"] + ".csv.gz"))
    df = frames[ev["route"]]
    telemetry_figure(ev, df)
    map_figure(ev, df, load_osm_for(ev))
    n += 1
  print(n, "events plotted ->", FIG_DIR)


if __name__ == "__main__":
  main()
