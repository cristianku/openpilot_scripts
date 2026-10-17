# /// script
# requires-python = ">=3.11"
# dependencies = ["numpy", "pandas"]
# ///
"""Step 3: per-event pipeline reconstruction (engagement-aware).

For every candidate event of out/events.json this adds:

  engagement     t_diseng (first openpilot-long drop between the speed peak and the
                 minimum) + cause (driver brake / gas / other), engaged_at_min
  sources        planner source shares *while engaged*, number of source switches,
                 DEC acc<->blended switches, positive jumps of aTarget (> 0.5 m/s^2 in 0.5 s)
  onsets         first sustained engaged request below -0.5 m/s^2 (plan), model
                 request below -0.5, physical decel below -0.5; distance from each
                 onset to the minimum
  model intent   for T = 10, 8, 6, 4, 3, 2 s before the standstill:
                   d_rem   = distance actually travelled until standstill (integral of vEgo)
                   stop_x  = modelV2 predicted distance where its speed drops below 0.5 m/s
                   x_end   = modelV2 predicted position at 10 s
                   x_pred_T= modelV2 predicted position at +T s (the moment the car really stopped)
                 err_pred_T = d_rem - x_pred_T (negative: the car travelled LESS than the model
                 planned at that moment, i.e. it was slower than the model's own trajectory)
                 err = d_rem - stop_x (negative: car stopped BEFORE the point the model was
                 aiming at, at that moment)
  lead gap       vision lead dRel at standstill (if a lead is present)
  response       engaged braking samples: request (carControl), PSA command (0x2B6),
                 measured aEgo 0.3 s later; ratios (gain actually applied, vehicle tracking)
  brake cycles   number of PSA brake entries (0x2B6 MDD_DECEL_CONTROL_REQ 0->1) during the
                 engaged approach

Output: out/events_analyzed.json / .csv
"""

import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import OUT_DIR  # noqa: E402

DT = 0.05
PLAN_SOURCES = {0: "cruise", 1: "lead0", 2: "lead1", 3: "lead2", 4: "e2e"}
SP_SOURCES = {0: "cruise", 1: "sccVision", 2: "sccMap", 3: "speedLimitAssist"}
INTENT_TIMES = [8, 6, 5, 4, 3, 2]
LAG_N = 6  # 0.3 s


def num(x):
  if x is None:
    return None
  if isinstance(x, float) and math.isnan(x):
    return None
  if isinstance(x, (np.floating, float)):
    if math.isnan(float(x)):
      return None
    return round(float(x), 3)
  return x


def first_true(mask, start, end):
  for i in range(start, end + 1):
    if mask[i]:
      return i
  return None


def first_sustained_below(series, valid, start, end, threshold, hold_n):
  count = 0
  for i in range(start, end + 1):
    if valid[i] and series[i] < threshold:
      count += 1
      if count >= hold_n:
        return i - hold_n + 1
    else:
      count = 0
  return None


def analyse(df, ev):
  t = df["route_t"].to_numpy()
  v = df["v_ego"].to_numpy()
  a = df["a_ego"].to_numpy()
  eng = df["cc_long_active"].fillna(0).to_numpy() > 0.5
  brake = df["brake_pressed"].fillna(0).to_numpy() > 0.5
  gas = df["gas_pressed"].fillna(0).to_numpy() > 0.5
  plan_a = df["plan_a_target"].to_numpy()
  md_a = df["md_des_accel"].to_numpy()
  cc_a = df["cc_accel"].to_numpy()
  can_d = df["can_decel"].to_numpy()
  can_req = df["can_decel_req"].fillna(0).to_numpy() > 0.5
  src = df["plan_source"].to_numpy()
  dec = df["dec_state"].to_numpy()

  i_peak = int(np.searchsorted(t, ev["t_peak"]))
  i_min = int(np.searchsorted(t, ev["t_min"]))
  i_min = min(i_min, len(t) - 1)
  i_end = min(len(t) - 1, i_min + int(3 / DT))
  out = {}

  # ---------------- engagement
  i_dis = None
  for i in range(i_peak + 1, i_min + 1):
    if eng[i - 1] and not eng[i]:
      i_dis = i
      break
  out["engaged_at_peak"] = bool(eng[i_peak])
  out["engaged_at_min"] = bool(eng[i_min])
  out["t_diseng"] = None if i_dis is None else round(float(t[i_dis]), 2)
  cause = None
  if i_dis is not None:
    lo = max(0, i_dis - 6)
    hi = min(len(t) - 1, i_dis + 2)
    if brake[lo:hi + 1].any():
      cause = "driver_brake"
    elif gas[lo:hi + 1].any():
      cause = "driver_gas"
    else:
      cause = "other"
  out["diseng_cause"] = cause
  out["v_at_diseng_kph"] = None if i_dis is None else round(float(v[i_dis]) * 3.6, 1)
  # did the driver press gas while engaged during the approach (override)?
  out["gas_override_during_approach"] = bool((gas[i_peak:i_min + 1] & eng[i_peak:i_min + 1]).any()) if i_min > i_peak else False

  # engaged range used for the analysis
  i_last = i_min if i_dis is None else i_dis - 1
  if i_last <= i_peak or not eng[i_peak:i_last + 1].any():
    out["analysable"] = False
    return out
  out["analysable"] = True
  sel = np.zeros(len(t), dtype=bool)
  sel[i_peak:i_last + 1] = eng[i_peak:i_last + 1]

  # ---------------- sources
  shares = {}
  count = 0
  switches = 0
  prev = None
  for i in range(i_peak, i_last + 1):
    if not sel[i] or src[i] != src[i]:
      continue
    name = PLAN_SOURCES.get(int(src[i]), str(src[i]))
    shares[name] = shares.get(name, 0) + 1
    count += 1
    if prev is not None and name != prev:
      switches += 1
    prev = name
  for k in list(shares.keys()):
    shares[k] = round(shares[k] / max(count, 1), 3)
  out["eng_plan_sources"] = shares
  out["eng_source_switches"] = switches
  dec_sw = 0
  blended = 0
  dec_n = 0
  prev = None
  for i in range(i_peak, i_last + 1):
    if not sel[i] or dec[i] != dec[i]:
      continue
    dec_n += 1
    if int(dec[i]) == 1:
      blended += 1
    if prev is not None and int(dec[i]) != prev:
      dec_sw += 1
    prev = int(dec[i])
  out["eng_dec_switches"] = dec_sw
  out["eng_blended_share"] = None if dec_n == 0 else round(blended / dec_n, 3)

  # sunnypilot sub-source (cruise -> SLA / SCC) while engaged
  sps = {}
  nn = 0
  for i in range(i_peak, i_last + 1):
    s = df["sp_source"].iloc[i]
    if not sel[i] or s != s:
      continue
    name = SP_SOURCES.get(int(s), str(s))
    sps[name] = sps.get(name, 0) + 1
    nn += 1
  for k in list(sps.keys()):
    sps[k] = round(sps[k] / max(nn, 1), 3)
  out["eng_sp_sources"] = sps

  # positive jumps of the planner target while engaged (source switching signature)
  jumps = 0
  big_jump = 0.0
  k = int(0.5 / DT)
  for i in range(i_peak + k, i_last + 1):
    if sel[i] and sel[i - k]:
      dj = plan_a[i] - plan_a[i - k]
      if dj > 0.5:
        jumps += 1
      if dj > big_jump:
        big_jump = dj
  out["eng_plan_up_jumps"] = jumps
  out["eng_plan_max_up_jump"] = round(float(big_jump), 2)

  # ---------------- onsets (engaged only)
  hold = int(1.0 / DT)
  o_plan = first_sustained_below(plan_a, sel, i_peak, i_last, -0.5, hold)
  o_model = first_sustained_below(md_a, sel, i_peak, i_last, -0.5, hold)
  o_phys = first_sustained_below(a, sel, i_peak, i_last, -0.5, hold)
  o_plan_light = first_sustained_below(plan_a, sel, i_peak, i_last, -0.2, hold)

  def dist(i0, i1):
    if i0 is None or i1 is None or i1 <= i0:
      return None
    return round(float(np.nansum(v[i0:i1]) * DT), 1)

  out["t_onset_plan05"] = None if o_plan is None else round(float(t[o_plan]), 2)
  out["t_onset_plan02"] = None if o_plan_light is None else round(float(t[o_plan_light]), 2)
  out["t_onset_model05"] = None if o_model is None else round(float(t[o_model]), 2)
  out["t_onset_phys05"] = None if o_phys is None else round(float(t[o_phys]), 2)
  out["v_onset_plan05_kph"] = None if o_plan is None else round(float(v[o_plan]) * 3.6, 1)
  out["dist_onset_plan05_to_min"] = dist(o_plan, i_min)
  out["dist_onset_plan02_to_min"] = dist(o_plan_light, i_min)
  out["dist_onset_model05_to_min"] = dist(o_model, i_min)
  out["src_at_onset_plan05"] = None
  if o_plan is not None and src[o_plan] == src[o_plan]:
    out["src_at_onset_plan05"] = PLAN_SOURCES.get(int(src[o_plan]))
  out["model_leads_plan_s"] = None
  if o_plan is not None and o_model is not None:
    out["model_leads_plan_s"] = round(float(t[o_plan] - t[o_model]), 2)

  # ---------------- model intent vs actual stop (only stops reached while engaged)
  intent = []
  if ev["kind"] == "stop" and eng[i_min]:
    for T in INTENT_TIMES:
      i = i_min - int(T / DT)
      if i < i_peak or not eng[i]:
        continue
      d_rem = float(np.nansum(v[i:i_min]) * DT)
      stop_x = df["md_stop_x"].iloc[i]
      x_end = df["md_x_end"].iloc[i]
      lead_on = bool(df["lead_present"].iloc[i] > 0.5)
      # model predicted position after exactly T seconds (when the car actually stopped)
      x_pred = df["md_x_%ds" % T].iloc[i] if ("md_x_%ds" % T) in df.columns else float("nan")
      row = {
        "T": T, "v_kph": round(float(v[i]) * 3.6, 1), "d_rem": round(d_rem, 1),
        "stop_x": num(stop_x), "x_end": num(x_end),
        "err_stop_x": None if stop_x != stop_x else round(d_rem - float(stop_x), 1),
        "err_x_end": None if x_end != x_end else round(d_rem - float(x_end), 1),
        "x_pred_T": num(x_pred),
        "err_pred_T": None if x_pred != x_pred else round(d_rem - float(x_pred), 1),
        "src": PLAN_SOURCES.get(int(src[i])) if src[i] == src[i] else None,
        "lead": lead_on,
        "lead_d": num(df["lead_d"].iloc[i]) if lead_on else None,
      }
      intent.append(row)
  out["intent"] = intent

  # lead gap at standstill
  out["lead_at_stop"] = bool(df["lead_present"].iloc[i_min] > 0.5)
  out["lead_d_at_stop"] = num(df["lead_d"].iloc[min(len(t) - 1, i_min + int(1 / DT))]) if out["lead_at_stop"] else None
  out["lead_v_at_stop"] = num(df["lead_v"].iloc[i_min]) if out["lead_at_stop"] else None

  # lead plausibility: continuous track before the stop, and what it does before we move off
  lp = df["lead_present"].fillna(0).to_numpy() > 0.5
  ld = df["lead_d"].to_numpy()
  lv = df["lead_v"].to_numpy()
  out["lead_track_s"] = None
  out["lead_first_d"] = None
  out["lead_vmax_kph"] = None
  out["lead_departs_first"] = None
  out["lead_d_gain_before_go"] = None
  if lp[i_min]:
    j = i_min
    while j > 0 and lp[j - 1]:
      j -= 1
    out["lead_track_s"] = round((i_min - j) * DT, 1)
    out["lead_first_d"] = num(ld[j])
    out["lead_vmax_kph"] = num(np.nanmax(lv[j:i_min + 1]) * 3.6)
    # standstill run, then first sample where we move again
    k = i_min
    while k < len(t) - 1 and v[k] < 1.0 and (t[k] - t[i_min]) < 120:
      k += 1
    if k > i_min + int(2 / DT) and k < len(t) - 1:
      # dRel just before we roll vs at the beginning of the standstill
      k0 = min(len(t) - 1, i_min + int(1 / DT))
      k1 = max(k0, k - int(0.5 / DT))
      if lp[k0] and lp[k1]:
        gain_d = float(ld[k1] - ld[k0])
        out["lead_d_gain_before_go"] = round(gain_d, 1)
        out["lead_departs_first"] = bool(gain_d > 2.0)
      elif lp[k0] and not lp[k1]:
        out["lead_departs_first"] = True  # lead vanished while we were still stopped

  # ---------------- response (engaged braking samples)
  req_list = []
  cmd_list = []
  meas_list = []
  for i in range(i_peak, max(i_peak, i_last - LAG_N)):
    if sel[i] and can_req[i] and cc_a[i] < -0.3 and v[i] > 2.0 and not brake[i] and not gas[i]:
      req_list.append(cc_a[i])
      cmd_list.append(can_d[i])
      meas_list.append(a[i + LAG_N])
  if len(req_list) >= 10:
    req_arr = np.asarray(req_list)
    cmd_arr = np.asarray(cmd_list)
    meas_arr = np.asarray(meas_list)
    out["resp_n"] = len(req_list)
    out["resp_req_mean"] = round(float(req_arr.mean()), 2)
    out["resp_cmd_mean"] = round(float(cmd_arr.mean()), 2)
    out["resp_meas_mean"] = round(float(meas_arr.mean()), 2)
    out["resp_cmd_over_req"] = round(float(cmd_arr.mean() / req_arr.mean()), 2)
    out["resp_meas_over_req"] = round(float(meas_arr.mean() / req_arr.mean()), 2)
    out["resp_meas_minus_cmd"] = round(float((meas_arr - cmd_arr).mean()), 2)
  else:
    out["resp_n"] = len(req_list)

  # brake cycles during the engaged approach
  entries = 0
  for i in range(i_peak + 1, i_last + 1):
    if sel[i] and can_req[i] and not can_req[i - 1]:
      entries += 1
  out["eng_brake_entries"] = entries

  # mean pitch (deg) during approach
  p = df["pitch"].to_numpy()[i_peak:i_last + 1]
  out["pitch_deg"] = None if np.all(np.isnan(p)) else round(math.degrees(float(np.nanmean(p))), 2)
  # set speed during approach
  vc = df["v_cruise"].to_numpy()[i_peak:i_last + 1]
  out["v_cruise_min"] = num(np.nanmin(vc)) if len(vc) else None
  out["v_cruise_max"] = num(np.nanmax(vc)) if len(vc) else None
  return out


def main():
  events = json.loads((OUT_DIR / "events.json").read_text())
  by_route = {}
  for ev in events:
    by_route.setdefault(ev["route"], []).append(ev)
  result = []
  for route, evs in by_route.items():
    df = pd.read_csv(OUT_DIR / "timeline" / (route + ".csv.gz"))
    for ev in evs:
      extra = analyse(df, ev)
      merged = dict(ev)
      merged.update(extra)
      result.append(merged)
  (OUT_DIR / "events_analyzed.json").write_text(json.dumps(result, indent=1, default=str))
  flat = []
  for ev in result:
    row = {}
    for k, val in ev.items():
      if isinstance(val, (dict, list)):
        row[k] = json.dumps(val)
      else:
        row[k] = val
    flat.append(row)
  pd.DataFrame(flat).to_csv(OUT_DIR / "events_analyzed.csv", index=False)
  n_ok = 0
  for ev in result:
    if ev.get("analysable"):
      n_ok += 1
  print(len(result), "events,", n_ok, "with an engaged approach")


if __name__ == "__main__":
  main()
