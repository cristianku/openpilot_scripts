# /// script
# requires-python = ">=3.11"
# dependencies = ["pycapnp", "zstandard", "numpy", "pandas"]
# ///
"""Step 1: rlog -> one 20 Hz timeline per route (read-only on the logs).

The base clock is longitudinalPlan (20 Hz, one row per planner cycle). Every
other topic is sampled with "last value received at or before this row"
(zero-order hold), so a row shows what each process had published when the
planner produced that output. 100 Hz topics (carState, carControl, carOutput,
sendcan) are therefore decimated to 20 Hz here; controller timing at 100 Hz is
analysed separately in analyze_events.py where needed.

Columns (units):
  t            logMonoTime of the longitudinalPlan row, s (monotonic, device clock)
  route_t      t - first logMonoTime of the route, s
  seg, seg_t   segment number, seconds from the first message of that segment
  v_ego, a_ego, v_ego_raw            carState, m/s, m/s^2
  brake_pressed, gas_pressed, standstill, cruise_enabled, v_cruise(km/h), v_cruise_cluster(km/h)
  steer_deg, yaw_rate, blinker_l, blinker_r
  cc_enabled, cc_long_active, cc_accel (carControl.actuators.accel, m/s^2), cc_long_state (enum int)
  pitch (carControl.orientationNED[1], rad; nan if missing), cc_override
  out_accel  carOutput.actuatorsOutput.accel, m/s^2
  plan_a_target, plan_should_stop, plan_source (log.LongitudinalPlan.LongitudinalPlanSource int),
  plan_has_lead, plan_v0, plan_v_end, plan_a0, plan_allow_throttle, plan_fcw
  sp_source (custom LongitudinalPlanSource int), sp_v_target, sp_a_target,
  dec_state (0 acc, 1 blended; nan if missing), dec_active,
  sla_state, sla_v_target, sl_resolver (m/s), sl_dist, sl_source
  md_des_accel, md_should_stop (modelV2.action), md_x_end (position.x at 10 s, m),
  md_v_1s .. md_v_8s (predicted speed at t s, m/s), md_x_2s .. md_x_8s (predicted
  position along x at t s, m), md_stop_x (predicted position where
  predicted speed first drops below 0.5 m/s, m; nan if it never does), md_a0,
  md_lead_prob, md_lead_x, md_lead_v, md_gas_prob
  lead_present, lead_d, lead_vrel, lead_v, lead_a, lead_prob, lead_radar, lead2_present, lead2_d
  sd_enabled, sd_active, sd_experimental, sd_personality, sd_state
  gps_lat, gps_lon, gps_speed, gps_bearing, gps_acc, gps_fix, gps_unix_ms, gps_age (s since that fix)
  map_sl_valid, map_sl, map_sl_ahead, map_sl_ahead_dist
  can_decel (0x2B6 MDD_DESIRED_DECELERATION physical m/s^2, as transmitted on bus 1),
  can_decel_req (MDD_DECEL_CONTROL_REQ), can_decel_type, can_wheel_torque_req,
  can_gmp_torque (N.m), can_gmp_pot_torque (N.m), can_pot_req, can_acc_status
  fcam_seg, fcam_frame  narrowRoadEncodeIdx (fcamera.hevc) segment + frame index (presentation order)
                        of the last frame whose start-of-frame precedes the row: video sync key

Usage:
  uv run extract.py <route> [<route> ...]   -> out/timeline/<route>.csv.gz
  uv run extract.py --all-long              -> every route with openpilot longitudinal
"""

import json
import multiprocessing
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import DBC_PATH, OUT_DIR, all_segment_dirs, read_events  # noqa: E402

TIMELINE_DIR = OUT_DIR / "timeline"
ADDR_2B6 = 0x2B6
ADAS_BUS = 1
MD_V_TIMES = [1.0, 2.0, 3.0, 4.0, 6.0, 8.0]
MD_X_TIMES = [2.0, 3.0, 4.0, 5.0, 6.0, 8.0]


# ---------------------------------------------------------------- DBC decode
def load_2b6_spec():
  spec = {}
  inside = False
  for line in DBC_PATH.read_text(errors="replace").splitlines():
    if line.startswith("BO_ "):
      inside = line.startswith("BO_ 694 ")
      continue
    if not inside:
      continue
    line = line.strip()
    if not line.startswith("SG_ "):
      if line == "":
        inside = False
      continue
    # SG_ NAME : start|len@0+ (scale,offset) ...
    name = line.split()[1]
    layout = line.split(":")[1].split()[0]
    start = int(layout.split("|")[0])
    length = int(layout.split("|")[1].split("@")[0])
    big_endian = layout.split("@")[1][0] == "0"
    factor_txt = line.split("(")[1].split(")")[0]
    scale = float(factor_txt.split(",")[0])
    offset = float(factor_txt.split(",")[1])
    spec[name] = (start, length, big_endian, scale, offset)
  return spec


def decode_signal(data, sig):
  start, length, big_endian, scale, offset = sig
  total = len(data) * 8
  if big_endian:
    pos = (start // 8) * 8 + (7 - start % 8)
    shift = total - pos - length
    raw_int = int.from_bytes(data, "big")
  else:
    shift = start
    raw_int = int.from_bytes(data, "little")
  if shift < 0:
    return float("nan")
  value = (raw_int >> shift) & ((1 << length) - 1)
  return value * scale + offset


# ---------------------------------------------------------------- per segment
class TopicBuffer:
  """Times + dict of column lists for one topic."""

  def __init__(self, columns):
    self.t = []
    self.cols = {}
    for c in columns:
      self.cols[c] = []

  def add(self, t, values):
    self.t.append(t)
    for c in self.cols:
      self.cols[c].append(values.get(c, np.nan))


def safe(fn):
  try:
    return fn()
  except Exception:
    return np.nan


def interp_list(times, values, at):
  if len(times) == 0 or len(values) != len(times):
    return np.nan
  return float(np.interp(at, times, values))


def first_stop_x(t_list, v_list, x_list):
  n = min(len(v_list), len(x_list))
  for i in range(n):
    if v_list[i] < 0.5:
      return float(x_list[i])
  return np.nan


def read_segment(args):
  seg, seg_dir, spec = args
  bufs = {
    "carState": TopicBuffer(["v_ego", "a_ego", "v_ego_raw", "brake_pressed", "gas_pressed", "standstill",
                             "cruise_enabled", "v_cruise", "v_cruise_cluster", "steer_deg", "yaw_rate",
                             "blinker_l", "blinker_r"]),
    "carControl": TopicBuffer(["cc_enabled", "cc_long_active", "cc_accel", "cc_long_state", "pitch", "cc_override"]),
    "carOutput": TopicBuffer(["out_accel"]),
    "longitudinalPlanSP": TopicBuffer(["sp_source", "sp_v_target", "sp_a_target", "dec_state", "dec_active",
                                       "sla_state", "sla_v_target", "sl_resolver", "sl_dist", "sl_source"]),
    "modelV2": TopicBuffer(["md_des_accel", "md_should_stop", "md_x_end", "md_stop_x", "md_a0",
                            "md_lead_prob", "md_lead_x", "md_lead_v", "md_gas_prob"]
                           + ["md_v_%ds" % int(x) for x in MD_V_TIMES]
                           + ["md_x_%ds" % int(x) for x in MD_X_TIMES]),
    "radarState": TopicBuffer(["lead_present", "lead_d", "lead_vrel", "lead_v", "lead_a", "lead_prob", "lead_radar",
                               "lead2_present", "lead2_d"]),
    "selfdriveState": TopicBuffer(["sd_enabled", "sd_active", "sd_experimental", "sd_personality", "sd_state"]),
    "gpsLocationExternal": TopicBuffer(["gps_lat", "gps_lon", "gps_speed", "gps_bearing", "gps_acc", "gps_fix",
                                        "gps_unix_ms", "gps_t"]),
    "liveMapDataSP": TopicBuffer(["map_sl_valid", "map_sl", "map_sl_ahead", "map_sl_ahead_dist"]),
    "narrowRoadEncodeIdx": TopicBuffer(["fcam_seg", "fcam_frame"]),
    "sendcan": TopicBuffer(["can_decel", "can_decel_req", "can_decel_type", "can_wheel_torque_req",
                            "can_gmp_torque", "can_gmp_pot_torque", "can_pot_req", "can_acc_status"]),
  }
  plan_rows = []
  seg_t0 = None
  counter_selfdrive = 0

  for ev in read_events(seg_dir / "rlog.zst"):
    t = ev.logMonoTime * 1e-9
    w = ev.which()
    # initData is repeated in every segment with the route start time: skip it
    if seg_t0 is None and w != "initData":
      seg_t0 = t
    if w == "carState":
      cs = ev.carState
      bufs[w].add(t, {
        "v_ego": cs.vEgo, "a_ego": cs.aEgo, "v_ego_raw": cs.vEgoRaw,
        "brake_pressed": int(cs.brakePressed), "gas_pressed": int(cs.gasPressed), "standstill": int(cs.standstill),
        "cruise_enabled": int(cs.cruiseState.enabled), "v_cruise": cs.vCruise, "v_cruise_cluster": cs.vCruiseCluster,
        "steer_deg": cs.steeringAngleDeg, "yaw_rate": cs.yawRate,
        "blinker_l": int(cs.leftBlinker), "blinker_r": int(cs.rightBlinker),
      })
    elif w == "carControl":
      cc = ev.carControl
      pitch = np.nan
      if len(cc.orientationNED) == 3:
        pitch = cc.orientationNED[1]
      bufs[w].add(t, {
        "cc_enabled": int(cc.enabled), "cc_long_active": int(cc.longActive), "cc_accel": cc.actuators.accel,
        "cc_long_state": int(cc.actuators.longControlState.raw), "pitch": pitch,
        "cc_override": int(cc.cruiseControl.override),
      })
    elif w == "carOutput":
      bufs[w].add(t, {"out_accel": ev.carOutput.actuatorsOutput.accel})
    elif w == "longitudinalPlan":
      lp = ev.longitudinalPlan
      speeds = list(lp.speeds)
      accels = list(lp.accels)
      plan_rows.append({
        "t": t, "plan_a_target": lp.aTarget, "plan_should_stop": int(lp.shouldStop),
        "plan_source": int(lp.longitudinalPlanSource.raw), "plan_has_lead": int(lp.hasLead),
        "plan_v0": speeds[0] if speeds else np.nan, "plan_v_end": speeds[-1] if speeds else np.nan,
        "plan_a0": accels[0] if accels else np.nan, "plan_allow_throttle": int(lp.allowThrottle),
        "plan_fcw": int(lp.fcw),
      })
    elif w == "longitudinalPlanSP":
      sp = ev.longitudinalPlanSP
      values = {
        "sp_source": int(sp.longitudinalPlanSource.raw), "sp_v_target": sp.vTarget, "sp_a_target": sp.aTarget,
        "dec_state": safe(lambda: int(sp.deprecated.dec.state.raw)),
        "dec_active": safe(lambda: int(sp.deprecated.dec.active)),
        "sla_state": safe(lambda: int(sp.speedLimit.assist.state.raw)),
        "sla_v_target": safe(lambda: sp.speedLimit.assist.vTarget),
        "sl_resolver": safe(lambda: sp.speedLimit.resolver.speedLimit),
        "sl_dist": safe(lambda: sp.speedLimit.resolver.distToSpeedLimit),
        "sl_source": safe(lambda: int(sp.speedLimit.resolver.source.raw)),
      }
      bufs[w].add(t, values)
    elif w == "modelV2":
      md = ev.modelV2
      vt = list(md.velocity.t)
      vx = list(md.velocity.x)
      px = list(md.position.x)
      values = {
        "md_des_accel": md.action.desiredAcceleration, "md_should_stop": int(md.action.shouldStop),
        "md_x_end": px[-1] if px else np.nan,
        "md_stop_x": first_stop_x(vt, vx, px),
        "md_a0": md.acceleration.x[0] if len(md.acceleration.x) else np.nan,
      }
      for x in MD_V_TIMES:
        values["md_v_%ds" % int(x)] = interp_list(vt, vx, x)
      pt = list(md.position.t)
      for x in MD_X_TIMES:
        values["md_x_%ds" % int(x)] = interp_list(pt, px, x)
      if len(md.leadsV3) > 0:
        ld = md.leadsV3[0]
        values["md_lead_prob"] = ld.prob
        values["md_lead_x"] = ld.x[0] if len(ld.x) else np.nan
        values["md_lead_v"] = ld.v[0] if len(ld.v) else np.nan
      gp = list(md.meta.disengagePredictions.gasPressProbs)
      if len(gp) > 1:
        values["md_gas_prob"] = gp[1]
      bufs[w].add(t, values)
    elif w == "radarState":
      rs = ev.radarState
      l1 = rs.leadOne
      l2 = rs.leadTwo
      bufs[w].add(t, {
        "lead_present": int(l1.present), "lead_d": l1.dRel, "lead_vrel": l1.vRel, "lead_v": l1.vLead,
        "lead_a": l1.aLeadK, "lead_prob": l1.modelProb, "lead_radar": int(l1.radar),
        "lead2_present": int(l2.present), "lead2_d": l2.dRel,
      })
    elif w == "selfdriveState":
      counter_selfdrive += 1
      if counter_selfdrive % 5 != 0:
        continue
      ss = ev.selfdriveState
      bufs[w].add(t, {
        "sd_enabled": int(ss.enabled), "sd_active": int(ss.active), "sd_experimental": int(ss.experimentalMode),
        "sd_personality": int(ss.personality.raw), "sd_state": int(ss.state.raw),
      })
    elif w == "gpsLocationExternal":
      g = ev.gpsLocationExternal
      bufs[w].add(t, {
        "gps_lat": g.latitude, "gps_lon": g.longitude, "gps_speed": g.speed, "gps_bearing": g.bearingDeg,
        "gps_acc": g.horizontalAccuracy, "gps_fix": int(g.hasFix), "gps_unix_ms": float(g.unixTimestampMillis),
        "gps_t": t,
      })
    elif w == "liveMapDataSP":
      lm = ev.liveMapDataSP
      bufs[w].add(t, {
        "map_sl_valid": int(lm.speedLimitValid), "map_sl": lm.speedLimit,
        "map_sl_ahead": lm.speedLimitAhead, "map_sl_ahead_dist": lm.speedLimitAheadDistance,
      })
    elif w == "narrowRoadEncodeIdx":
      e = ev.narrowRoadEncodeIdx
      # index by start-of-frame time, so a timeline row maps to the frame captured just before it
      bufs[w].add(e.timestampSof * 1e-9, {"fcam_seg": e.segmentNum, "fcam_frame": e.segmentId})
    elif w == "sendcan":
      for m in ev.sendcan:
        if m.address != ADDR_2B6:
          continue
        if m.src != ADAS_BUS:
          continue
        d = bytes(m.dat)
        bufs[w].add(t, {
          "can_decel": decode_signal(d, spec["MDD_DESIRED_DECELERATION"]),
          "can_decel_req": decode_signal(d, spec["MDD_DECEL_CONTROL_REQ"]),
          "can_decel_type": decode_signal(d, spec["MDD_DECEL_TYPE"]),
          "can_wheel_torque_req": decode_signal(d, spec["WHEEL_TORQUE_REQUEST"]),
          "can_gmp_torque": decode_signal(d, spec["GMP_WHEEL_TORQUE"]),
          "can_gmp_pot_torque": decode_signal(d, spec["GMP_POTENTIAL_WHEEL_TORQUE"]),
          "can_pot_req": decode_signal(d, spec["POTENTIAL_WHEEL_TORQUE_REQUEST"]),
          "can_acc_status": decode_signal(d, spec["ACC_STATUS"]),
        })

  if not plan_rows:
    return None
  df = pd.DataFrame(plan_rows)
  grid = df["t"].to_numpy()
  for name, buf in bufs.items():
    t_arr = np.asarray(buf.t)
    if name == "narrowRoadEncodeIdx" and len(t_arr) > 1:
      order = np.argsort(t_arr)
      t_arr = t_arr[order]
      for c in buf.cols:
        buf.cols[c] = list(np.asarray(buf.cols[c], dtype=float)[order])
    if len(t_arr) == 0:
      for c in buf.cols:
        df[c] = np.nan
      continue
    idx = np.searchsorted(t_arr, grid, side="right") - 1
    valid = idx >= 0
    idx_c = np.clip(idx, 0, len(t_arr) - 1)
    for c, values in buf.cols.items():
      arr = np.asarray(values, dtype=float)
      col = arr[idx_c]
      col[~valid] = np.nan
      df[c] = col
  df["gps_age"] = df["t"] - df["gps_t"]
  df = df.drop(columns=["gps_t"])
  df["seg"] = seg
  df["seg_t"] = df["t"] - seg_t0
  return df


def extract_route(route):
  segs = all_segment_dirs().get(route)
  if not segs:
    print("no segments for", route)
    return
  spec = load_2b6_spec()
  jobs = []
  for seg, d in segs.items():
    jobs.append((seg, d, spec))
  with multiprocessing.Pool(6) as pool:
    frames = pool.map(read_segment_safe, jobs)
  good = []
  for f in frames:
    if f is not None:
      good.append(f)
  if not good:
    print("nothing extracted for", route)
    return
  df = pd.concat(good, ignore_index=True).sort_values("t").reset_index(drop=True)
  df["route_t"] = df["t"] - df["t"].iloc[0]
  TIMELINE_DIR.mkdir(parents=True, exist_ok=True)
  out = TIMELINE_DIR / (route + ".csv.gz")
  df.to_csv(out, index=False, float_format="%.5g")
  print(f"{route}: {len(good)} segs, {len(df)} rows, {df['route_t'].iloc[-1] / 60:.1f} min -> {out}")


def read_segment_safe(args):
  try:
    return read_segment(args)
  except Exception as exc:
    print("segment failed", args[0], args[1], str(exc)[:200])
    return None


def main():
  routes = sys.argv[1:]
  if routes == ["--all-long"]:
    inv = json.loads((OUT_DIR / "inventory.json").read_text())
    routes = []
    for row in inv:
      if row.get("op_long"):
        routes.append(row["route"])
  for r in routes:
    out = TIMELINE_DIR / (r + ".csv.gz")
    if out.exists():
      print("exists, skip", out)
      continue
    extract_route(r)


if __name__ == "__main__":
  main()
