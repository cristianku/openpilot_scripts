# /// script
# requires-python = ">=3.11"
# dependencies = ["numpy", "pandas"]
# ///
"""Step 6: evidence flags, ranking and the final event index.

Flags are HYPOTHESES computed from telemetry + map only (no video was available):

  possibly_premature_braking   openpilot was decelerating and the driver overrode with gas
                               (above 5 km/h), OR roundabout entry / signal more than
                               --far-onset m after the start of the < -0.5 m/s^2 request
  possibly_premature_stop      complete stop while engaged, no lead at standstill, mapped
                               signal more than 12 m ahead (GPS+OSM, +-15 m) OR lead at
                               standstill with a gap > 8 m
  possible_phantom_lead        lead-sourced braking with a lead that appeared < 25 m ahead,
                               was tracked < 3 s, or never moved (vmax < 3 km/h) and did not
                               depart before us
  model_originated             e2e was the planner source at the onset of the request
  planner_originated           lead0/lead1 (MPC) or cruise (incl. SCC/SLA sub-source) at onset
  controller_amplification     measured decel / openpilot request > 1.3 while braking (PSA gain)
  vehicle_mismatch             |measured - PSA command| > 0.3 m/s^2 while braking
  dec_switching                >= 3 DEC acc<->blended switches during the approach
  insufficient_evidence        not engaged, no GPS/map, or nothing analysable

Score = severity (premature flags, gas override, low minimum speed, brake cycles, DEC
switches) weighted by diagnostic usefulness (engaged, GPS+map class). It ranks what to look
at first; it is not a defect verdict.

Usage: uv run rank_events.py [--far-onset 150]
Output: out/event_index.csv, out/event_index.json, out/selected_events.json
"""

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import OUT_DIR  # noqa: E402


def flags_for(ev, far_onset):
  f = []
  engaged = bool(ev.get("analysable"))
  cls = ev.get("map_class")
  src0 = ev.get("src_at_onset_plan05")
  gas_premature = False
  if engaged:
    if ev.get("gas_override_during_approach"):
      gas_premature = True
    if ev.get("diseng_cause") == "driver_gas" and (ev.get("v_at_diseng_kph") or 0) > 5:
      gas_premature = True
  far = False
  if cls == "roundabout" and ev.get("roundabout_entry_rel_onset_m") is not None:
    if ev["roundabout_entry_rel_onset_m"] > far_onset:
      far = True
  if cls == "traffic_light" and ev.get("signal_rel_onset_m") is not None:
    if ev["signal_rel_onset_m"] > far_onset and not ev.get("lead_at_stop"):
      far = True
  if gas_premature or far:
    f.append("possibly_premature_braking")

  if ev["kind"] == "stop" and ev.get("engaged_at_min"):
    if not ev.get("lead_at_stop"):
      rel = ev.get("nearest_signal_rel_m")
      if rel is not None and rel > 12:
        f.append("possibly_premature_stop")
    else:
      gap = ev.get("lead_d_at_stop")
      if gap is not None and gap > 8:
        f.append("possibly_premature_stop")

  if engaged and src0 in ("lead0", "lead1"):
    phantom = False
    if ev.get("lead_first_d") is not None and ev["lead_first_d"] < 25 and (ev.get("lead_track_s") or 99) < 3:
      phantom = True
    if ev.get("lead_vmax_kph") is not None and ev["lead_vmax_kph"] < 3 and ev.get("lead_departs_first") is False:
      phantom = True
    if phantom:
      f.append("possible_phantom_lead")

  if engaged and src0 == "e2e":
    f.append("model_originated")
  if engaged and src0 in ("lead0", "lead1", "cruise"):
    f.append("planner_originated")
  ratio = ev.get("resp_meas_over_req")
  if ratio is not None and ratio > 1.3:
    f.append("controller_amplification")
  mm = ev.get("resp_meas_minus_cmd")
  if mm is not None and abs(mm) > 0.3:
    f.append("vehicle_mismatch")
  if (ev.get("eng_dec_switches") or 0) >= 3:
    f.append("dec_switching")
  if not engaged or cls in (None, "no_gps", "map_unavailable", "not_mapped"):
    f.append("insufficient_evidence")
  return f


def score_for(ev, flags):
  s = 0.0
  if "possibly_premature_braking" in flags:
    s += 3
  if "possibly_premature_stop" in flags:
    s += 3
  if "possible_phantom_lead" in flags:
    s += 2
  if ev.get("v_min_kph") is not None and ev["v_min_kph"] < 5:
    s += 1
  s += min(2.0, (ev.get("eng_brake_entries") or 0) / 2.0)
  s += min(2.0, (ev.get("eng_dec_switches") or 0) / 2.0)
  if ev.get("map_class") in ("traffic_light", "roundabout"):
    s *= 1.5
  if not ev.get("analysable"):
    s *= 0.2
  return round(s, 2)


def confidence_for(ev):
  # no video anywhere: never 'high'
  if not ev.get("analysable"):
    return "bassa"
  if ev.get("map_class") in ("traffic_light", "roundabout", "other_intersection") and ev.get("gps_valid"):
    return "media"
  return "bassa"


def main():
  ap = argparse.ArgumentParser()
  ap.add_argument("--far-onset", type=float, default=150.0)
  args = ap.parse_args()
  events = json.loads((OUT_DIR / "events_mapped.json").read_text())
  rows = []
  for ev in events:
    fl = flags_for(ev, args.far_onset)
    ev["flags"] = fl
    ev["score"] = score_for(ev, fl)
    ev["confidence"] = confidence_for(ev)
  events.sort(key=lambda e: -e["score"])
  for rank, ev in enumerate(events):
    ev["rank"] = rank + 1
    s = ev.get("eng_plan_sources") or {}
    top = None
    if s:
      top = max(s, key=s.get)
    rows.append({
      "rank": ev["rank"], "event_id": ev["event_id"], "route": ev["route"], "seg": ev["seg"], "seg_t": ev["seg_t"],
      "fcam_seg": ev.get("fcam_seg"), "fcam_frame": ev.get("fcam_frame"),
      "route_t_min": ev["t_min"], "kind": ev["kind"], "map_class": ev.get("map_class"),
      "v_peak_kph": ev["v_peak_kph"], "v_min_kph": ev["v_min_kph"], "a_min": ev["a_min"],
      "engaged": ev.get("analysable"), "engaged_at_min": ev.get("engaged_at_min"),
      "diseng_cause": ev.get("diseng_cause"), "src_at_onset": ev.get("src_at_onset_plan05"), "src_top": top,
      "dist_onset_to_min_m": ev.get("dist_onset_plan05_to_min"),
      "roundabout_entry_from_onset_m": ev.get("roundabout_entry_rel_onset_m"),
      "signal_from_onset_m": ev.get("signal_rel_onset_m"),
      "nearest_signal_rel_min_m": ev.get("nearest_signal_rel_m"),
      "nearest_roundabout_rel_min_m": ev.get("nearest_roundabout_rel_m"),
      "lead_at_stop": ev.get("lead_at_stop"), "lead_gap_at_stop_m": ev.get("lead_d_at_stop"),
      "meas_over_req": ev.get("resp_meas_over_req"), "meas_minus_cmd": ev.get("resp_meas_minus_cmd"),
      "brake_entries": ev.get("eng_brake_entries"), "dec_switches": ev.get("eng_dec_switches"),
      "lat": ev.get("lat_min"), "lon": ev.get("lon_min"),
      "flags": ";".join(ev["flags"]), "score": ev["score"], "confidence": ev["confidence"],
    })
  pd.DataFrame(rows).to_csv(OUT_DIR / "event_index.csv", index=False)
  (OUT_DIR / "event_index.json").write_text(json.dumps(events, indent=1, default=str))

  # events that get a full card in the report: every engaged traffic-light / roundabout
  # event, plus the top-ranked engaged events of other classes
  selected = []
  for ev in events:
    if ev.get("analysable") and ev.get("map_class") in ("traffic_light", "roundabout"):
      selected.append(ev["event_id"])
  for ev in events:
    if len(selected) >= 70:
      break
    if ev["event_id"] in selected:
      continue
    if ev.get("analysable") and ev["score"] >= 4:
      selected.append(ev["event_id"])
  (OUT_DIR / "selected_events.json").write_text(json.dumps(selected))
  counts = {}
  for ev in events:
    key = (ev.get("map_class"), bool(ev.get("analysable")))
    counts[key] = counts.get(key, 0) + 1
  for k, n in sorted(counts.items(), key=lambda kv: str(kv[0])):
    print(k, n)
  print(len(selected), "events selected for cards")


if __name__ == "__main__":
  main()
