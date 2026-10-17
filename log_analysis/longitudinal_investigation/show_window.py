# /// script
# requires-python = ">=3.11"
# dependencies = ["numpy", "pandas"]
# ///
"""Print a compact table of one route window (debug / evidence helper).

Usage: uv run show_window.py <route> <route_t_start> <route_t_end> [step_s]
"""

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import OUT_DIR  # noqa: E402

SRC = {0: "cru", 1: "ld0", 2: "ld1", 3: "ld2", 4: "e2e"}
SPS = {0: "cru", 1: "sccV", 2: "sccM", 3: "SLA"}


def main():
  route = sys.argv[1]
  t0 = float(sys.argv[2])
  t1 = float(sys.argv[3])
  step = 0.5
  if len(sys.argv) > 4:
    step = float(sys.argv[4])
  df = pd.read_csv(OUT_DIR / "timeline" / (route + ".csv.gz"))
  w = df[(df.route_t >= t0) & (df.route_t <= t1)]
  every = max(1, int(round(step / 0.05)))
  w = w.iloc[::every]
  print("route_t seg  seg_t  kph   aEgo  md_a  plan_a src  sp   dec cc_a  out_a  canDec req gmpT  lead d   vLd  "
        "mdStopX mdV2s mdV4s xEnd vCru pitch° brk gas act stop")
  for _, r in w.iterrows():
    src = SRC.get(int(r.plan_source), "?") if r.plan_source == r.plan_source else "nan"
    sps = SPS.get(int(r.sp_source), "?") if r.sp_source == r.sp_source else "nan"
    dec = "-"
    if r.dec_state == r.dec_state:
      dec = "BL" if int(r.dec_state) == 1 else "acc"
    lead = "%5.1f %5.1f" % (r.lead_d, r.lead_v) if r.lead_present > 0.5 else "    -     -"
    pitch = r.pitch * 57.3 if r.pitch == r.pitch else float("nan")
    print("%7.1f %3d %6.1f %5.1f %5.2f %5.2f %5.2f  %s %4s %3s %5.2f %5.2f %5.2f %d %6.0f %s %6.1f %5.1f %5.1f %5.0f %4.0f %5.1f %d %d %d %d" % (
      r.route_t, r.seg, r.seg_t, r.v_ego * 3.6, r.a_ego, r.md_des_accel, r.plan_a_target, src, sps, dec,
      r.cc_accel, r.out_accel, r.can_decel, int(r.can_decel_req) if r.can_decel_req == r.can_decel_req else -1,
      r.can_gmp_torque, lead, r.md_stop_x, r.md_v_2s * 3.6, r.md_v_4s * 3.6, r.md_x_end, r.v_cruise, pitch,
      r.brake_pressed, r.gas_pressed, r.cc_long_active, r.plan_should_stop))


if __name__ == "__main__":
  main()
