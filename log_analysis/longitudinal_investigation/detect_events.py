# /// script
# requires-python = ">=3.11"
# dependencies = ["numpy", "pandas"]
# ///
"""Step 2: candidate events from the 20 Hz timelines (telemetry only, no map, no video).

Event kinds (thresholds are CLI-configurable, defaults are first guesses):
  stop        speed falls below --stop-speed (0.3 m/s) after being above --approach-speed
  near_stop   local speed minimum below --near-stop-speed (5 km/h) that is not a stop
  slowdown    local minimum with a drop >= --drop-kph from the max of the previous
              --lookback s, followed by a recovery >= --recover-kph within --lookahead s
  hard_decel  a_ego < --hard-decel for >= 0.5 s (merged into the nearest event if any)

For each event the window [t_min - lookback, t_min + after] is summarised:
speed at the peak before the drop, minimum speed, first sustained negative
request (plan / carControl / model), first sustained physical deceleration,
distance travelled from those onsets to the minimum, planner source shares,
DEC state, lead presence, driver pedals, GPS at onset and at the minimum.

Nothing is labelled a defect here: flags are hypotheses to be checked against
map + video + the per-event pipeline analysis.

Usage: uv run detect_events.py [--routes r1 r2 ...] [thresholds]
Output: out/events.csv, out/events.json
"""

import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import OUT_DIR  # noqa: E402

TIMELINE_DIR = OUT_DIR / "timeline"
DT = 0.05  # longitudinalPlan period

PLAN_SOURCES = {0: "cruise", 1: "lead0", 2: "lead1", 3: "lead2", 4: "e2e"}
SP_SOURCES = {0: "cruise", 1: "sccVision", 2: "sccMap", 3: "speedLimitAssist"}


def parse_args():
  p = argparse.ArgumentParser()
  p.add_argument("--routes", nargs="*", default=None)
  p.add_argument("--stop-speed", type=float, default=0.3, help="m/s")
  p.add_argument("--near-stop-speed", type=float, default=5.0 / 3.6, help="m/s")
  p.add_argument("--approach-speed", type=float, default=15.0 / 3.6, help="m/s, speed that must precede an event")
  p.add_argument("--drop-kph", type=float, default=12.0)
  p.add_argument("--recover-kph", type=float, default=6.0)
  p.add_argument("--lookback", type=float, default=40.0, help="s before the minimum")
  p.add_argument("--lookahead", type=float, default=25.0, help="s after the minimum")
  p.add_argument("--hard-decel", type=float, default=-2.0, help="m/s^2")
  p.add_argument("--request-onset", type=float, default=-0.3, help="m/s^2, sustained request threshold")
  p.add_argument("--onset-hold", type=float, default=1.0, help="s the request must stay below threshold")
  p.add_argument("--min-separation", type=float, default=12.0, help="s between two minima")
  return p.parse_args()


def rolling_min_index(values, center, before, after):
  lo = max(0, center - before)
  hi = min(len(values), center + after + 1)
  return lo + int(np.nanargmin(values[lo:hi]))


def sustained_onset(series, start, end, threshold, hold_n):
  """Last index in [start, end] where series goes below threshold and stays there for hold_n samples
  up to the end (i.e. the beginning of the final continuous request), searching backwards from end."""
  if end <= start:
    return None
  below = series[start:end + 1] < threshold
  if not below[-1]:
    # request may have ended slightly before the minimum (stopping state); search the last run
    idx = len(below) - 1
    while idx >= 0 and not below[idx]:
      idx -= 1
    if idx < 0:
      return None
    below = below[:idx + 1]
  run_start = len(below) - 1
  while run_start > 0 and below[run_start - 1]:
    run_start -= 1
  if len(below) - run_start < hold_n:
    return None
  return start + run_start


def first_sustained(series, start, end, threshold, hold_n):
  """First index in [start, end] where series < threshold for hold_n consecutive samples."""
  count = 0
  for i in range(start, end + 1):
    v = series[i]
    if v < threshold:
      count += 1
      if count >= hold_n:
        return i - hold_n + 1
    else:
      count = 0
  return None


def path_distance(v, i0, i1):
  if i0 is None or i1 is None or i1 <= i0:
    return 0.0
  return float(np.nansum(v[i0:i1]) * DT)


def share(values):
  out = {}
  total = 0
  for v in values:
    if v is None or (isinstance(v, float) and math.isnan(v)):
      continue
    out[v] = out.get(v, 0) + 1
    total += 1
  if total == 0:
    return {}
  result = {}
  for k, n in sorted(out.items(), key=lambda kv: -kv[1]):
    result[k] = round(n / total, 3)
  return result


def find_minima(df, args):
  v = df["v_ego"].to_numpy()
  n = len(v)
  lb = int(args.lookback / DT)
  la = int(args.lookahead / DT)
  minima = []

  # 1) stops: start of every standstill run preceded by approach speed
  stopped = v < args.stop_speed
  i = 1
  while i < n:
    if stopped[i] and not stopped[i - 1]:
      lo = max(0, i - lb)
      if np.nanmax(v[lo:i]) >= args.approach_speed:
        minima.append((i, "stop"))
      j = i
      while j < n and stopped[j]:
        j += 1
      i = j
    else:
      i += 1

  # 2) local minima that are not stops
  vs = pd.Series(v).rolling(11, center=True, min_periods=1).mean().to_numpy()
  step = int(1.0 / DT)
  for i in range(lb // 4, n - 1, step):
    j = rolling_min_index(vs, i, int(5 / DT), int(5 / DT))
    if j != i and abs(j - i) > step // 2:
      continue
    j = rolling_min_index(vs, i, int(5 / DT), int(5 / DT))
    vmin = vs[j]
    if vmin < args.stop_speed:
      continue
    lo = max(0, j - lb)
    hi = min(n, j + la)
    peak_before = np.nanmax(vs[lo:j + 1])
    peak_after = np.nanmax(vs[j:hi])
    drop = (peak_before - vmin) * 3.6
    recover = (peak_after - vmin) * 3.6
    if vmin < args.near_stop_speed and peak_before >= args.approach_speed:
      minima.append((j, "near_stop"))
    elif drop >= args.drop_kph and recover >= args.recover_kph:
      minima.append((j, "slowdown"))

  # de-duplicate: keep stops first, then the lowest minimum inside min_separation
  minima.sort()
  kept = []
  sep = int(args.min_separation / DT)
  for idx, kind in minima:
    if kept and idx - kept[-1][0] < sep:
      prev_idx, prev_kind = kept[-1]
      prio = {"stop": 0, "near_stop": 1, "slowdown": 2}
      if prio[kind] < prio[prev_kind] or (prio[kind] == prio[prev_kind] and v[idx] < v[prev_idx]):
        kept[-1] = (idx, kind)
      continue
    kept.append((idx, kind))
  return kept


def summarise(df, route, idx, kind, args):
  v = df["v_ego"].to_numpy()
  a = df["a_ego"].to_numpy()
  n = len(v)
  lb = int(args.lookback / DT)
  la = int(args.lookahead / DT)
  lo = max(0, idx - lb)
  hi = min(n - 1, idx + la)
  hold_n = int(args.onset_hold / DT)

  # peak before the minimum, then search onsets between peak and minimum
  peak = lo + int(np.nanargmax(v[lo:idx + 1]))
  plan_a = df["plan_a_target"].to_numpy()
  cc_a = df["cc_accel"].to_numpy()
  md_a = df["md_des_accel"].to_numpy()

  onset_plan = first_sustained(plan_a, peak, idx, args.request_onset, hold_n)
  onset_cc = first_sustained(cc_a, peak, idx, args.request_onset, hold_n)
  onset_model = first_sustained(md_a, peak, idx, args.request_onset, hold_n)
  onset_phys = first_sustained(a, peak, idx, args.request_onset, hold_n)
  # final continuous request leading to the minimum (re-braking after a release)
  final_plan = sustained_onset(plan_a, peak, idx, args.request_onset, hold_n)

  def at(col, i):
    if i is None:
      return None
    val = df[col].iloc[i]
    if isinstance(val, float) and math.isnan(val):
      return None
    return float(val)

  def tt(i):
    if i is None:
      return None
    return round(float(df["route_t"].iloc[i]), 2)

  window = df.iloc[peak:idx + 1]
  engaged_share = float(window["cc_long_active"].fillna(0).mean()) if len(window) else 0.0
  brake_any = int(window["brake_pressed"].fillna(0).max()) if len(window) else 0
  gas_any = int(window["gas_pressed"].fillna(0).max()) if len(window) else 0

  # brake-release-brake cycles of the PSA command during the approach
  req = window["can_decel_req"].fillna(0).to_numpy()
  brake_entries = int(np.sum((req[1:] > 0.5) & (req[:-1] < 0.5))) if len(req) > 1 else 0

  # hard decel episodes inside the window
  hard_n = int(np.sum(a[peak:idx + 1] < args.hard_decel))

  # planner sources during the decel phase (peak -> minimum)
  srcs = []
  for s in window["plan_source"]:
    if isinstance(s, float) and math.isnan(s):
      srcs.append(None)
    else:
      srcs.append(PLAN_SOURCES.get(int(s), str(s)))
  sp_srcs = []
  for s in window["sp_source"]:
    if isinstance(s, float) and math.isnan(s):
      sp_srcs.append(None)
    else:
      sp_srcs.append(SP_SOURCES.get(int(s), str(s)))
  dec = []
  for s in window["dec_state"]:
    if isinstance(s, float) and math.isnan(s):
      dec.append(None)
    elif int(s) == 1:
      dec.append("blended")
    else:
      dec.append("acc")

  # source at the request onset and when requests are most negative
  def source_at(i):
    if i is None:
      return None
    s = df["plan_source"].iloc[i]
    if isinstance(s, float) and math.isnan(s):
      return None
    return PLAN_SOURCES.get(int(s), str(s))

  most_neg = None
  if len(window):
    most_neg = peak + int(np.nanargmin(plan_a[peak:idx + 1]))

  lead_share = float(window["lead_present"].fillna(0).mean()) if len(window) else 0.0
  lead_min_d = None
  lead_rows = window[window["lead_present"] > 0.5]
  if len(lead_rows):
    lead_min_d = round(float(lead_rows["lead_d"].min()), 1)

  gps_ok = window[(window["gps_fix"] > 0.5) & (window["gps_acc"] < 20)]
  ev = {
    "route": route,
    "kind": kind,
    "seg": int(df["seg"].iloc[idx]),
    "seg_t": round(float(df["seg_t"].iloc[idx]), 1),
    "fcam_seg": at("fcam_seg", idx),
    "fcam_frame": at("fcam_frame", idx),
    "t_min": tt(idx),
    "t_peak": tt(peak),
    "t_window_start": tt(lo),
    "t_window_end": tt(hi),
    "v_peak_kph": round(float(v[peak]) * 3.6, 1),
    "v_min_kph": round(float(v[idx]) * 3.6, 1),
    "a_min": round(float(np.nanmin(a[peak:idx + 1])), 2),
    "a_mean_decel": round(float(np.nanmean(a[peak:idx + 1])), 2),
    "t_onset_plan": tt(onset_plan),
    "t_onset_cc": tt(onset_cc),
    "t_onset_model": tt(onset_model),
    "t_onset_phys": tt(onset_phys),
    "t_final_plan_onset": tt(final_plan),
    "v_at_onset_plan_kph": None if onset_plan is None else round(float(v[onset_plan]) * 3.6, 1),
    "dist_onset_plan_to_min_m": round(path_distance(v, onset_plan, idx), 1),
    "dist_onset_model_to_min_m": round(path_distance(v, onset_model, idx), 1),
    "dist_peak_to_min_m": round(path_distance(v, peak, idx), 1),
    "time_onset_plan_to_min_s": None if onset_plan is None else round((idx - onset_plan) * DT, 1),
    "source_at_onset": source_at(onset_plan),
    "source_at_most_negative": source_at(most_neg),
    "plan_a_min": round(float(np.nanmin(plan_a[peak:idx + 1])), 2),
    "model_a_min": round(float(np.nanmin(md_a[peak:idx + 1])), 2),
    "cc_a_min": None if np.all(np.isnan(cc_a[peak:idx + 1])) else round(float(np.nanmin(cc_a[peak:idx + 1])), 2),
    "plan_sources": share(srcs),
    "sp_sources": share(sp_srcs),
    "dec_states": share(dec),
    "engaged_share": round(engaged_share, 2),
    "experimental": at("sd_experimental", idx),
    "driver_brake": brake_any,
    "driver_gas": gas_any,
    "psa_brake_entries": brake_entries,
    "hard_decel_samples": hard_n,
    "lead_share": round(lead_share, 2),
    "lead_min_d": lead_min_d,
    "gps_valid": int(len(gps_ok) > 10),
    "lat_min": at("gps_lat", idx),
    "lon_min": at("gps_lon", idx),
    "bearing_min": at("gps_bearing", idx),
    "lat_onset": at("gps_lat", onset_plan if onset_plan is not None else peak),
    "lon_onset": at("gps_lon", onset_plan if onset_plan is not None else peak),
    "gps_acc_min": at("gps_acc", idx),
    "gps_unix_ms": at("gps_unix_ms", idx),
    "pitch_mean_deg": None if window["pitch"].isna().all() else round(math.degrees(float(window["pitch"].mean())), 2),
  }
  return ev


def main():
  args = parse_args()
  files = sorted(TIMELINE_DIR.glob("*.csv.gz"))
  events = []
  for f in files:
    route = f.name.replace(".csv.gz", "")
    if args.routes and route not in args.routes:
      continue
    df = pd.read_csv(f)
    if len(df) < 200:
      continue
    for idx, kind in find_minima(df, args):
      ev = summarise(df, route, idx, kind, args)
      events.append(ev)
  for i, ev in enumerate(events):
    ev["event_id"] = "E%03d" % (i + 1)
  OUT_DIR.mkdir(exist_ok=True)
  (OUT_DIR / "events.json").write_text(json.dumps(events, indent=1))
  flat = []
  for ev in events:
    row = dict(ev)
    for k in ("plan_sources", "sp_sources", "dec_states"):
      row[k] = json.dumps(row[k])
    flat.append(row)
  pd.DataFrame(flat).to_csv(OUT_DIR / "events.csv", index=False)
  print(len(events), "events")
  kinds = {}
  for ev in events:
    key = (ev["kind"], ev["engaged_share"] > 0.8)
    kinds[key] = kinds.get(key, 0) + 1
  for k, nn in sorted(kinds.items()):
    print(k, nn)


if __name__ == "__main__":
  main()
