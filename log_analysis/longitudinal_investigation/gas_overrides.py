# /// script
# requires-python = ">=3.11"
# dependencies = ["numpy", "pandas"]
# ///
"""Driver gas overrides that interrupt an openpilot deceleration.

A gas press is counted when, in the 1.5 s before it, openpilot longitudinal was active,
no pedal was pressed and the planner was asking for < -0.3 m/s^2 for at least 0.5 s,
with vEgo > 8 km/h. These are the moments in which the driver (Cristian) judged the
deceleration unnecessary. Reported: planner source, DEC mode, sunnypilot sub-source,
model request, lead presence/distance, speed, set speed.

Usage: uv run gas_overrides.py   -> out/gas_overrides.csv + stdout summary
"""
import glob
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import OUT_DIR  # noqa: E402

DT = 0.05
SRC = {0: "cruise", 1: "lead0", 2: "lead1", 3: "lead2", 4: "e2e"}
SPS = {0: "cruise", 1: "sccVision", 2: "sccMap", 3: "speedLimitAssist"}
rows = []
for f in sorted(glob.glob(str(OUT_DIR / "timeline" / "*.csv.gz"))):
  route = Path(f).name.replace(".csv.gz", "")
  d = pd.read_csv(f)
  gas = d.gas_pressed.fillna(0).to_numpy() > 0.5
  brk = d.brake_pressed.fillna(0).to_numpy() > 0.5
  eng = d.cc_long_active.fillna(0).to_numpy() > 0.5
  pa = d.plan_a_target.to_numpy()
  v = d.v_ego.to_numpy()
  last = -1000
  for i in range(31, len(d)):
    if not gas[i] or gas[i - 1]:
      continue
    if i - last < int(5 / DT):
      continue
    lo = i - 30
    if not eng[lo:i].all() or gas[lo:i].any() or brk[lo:i].any():
      continue
    if v[i] < 8 / 3.6:
      continue
    neg = pa[lo:i] < -0.3
    if neg.sum() < 10:
      continue
    last = i
    j = i - 2
    r = d.iloc[j]
    rows.append({
      "route": route, "seg": int(r.seg), "seg_t": round(float(r.seg_t), 1), "route_t": round(float(r.route_t), 1),
      "v_kph": round(float(v[j]) * 3.6, 1), "v_cruise": r.v_cruise, "plan_a": round(float(r.plan_a_target), 2),
      "plan_a_min_1s5": round(float(np.min(pa[lo:i])), 2), "model_a": round(float(r.md_des_accel), 2),
      "src": SRC.get(int(r.plan_source)) if r.plan_source == r.plan_source else None,
      "sp_src": SPS.get(int(r.sp_source)) if r.sp_source == r.sp_source else None,
      "dec": None if r.dec_state != r.dec_state else ("blended" if int(r.dec_state) == 1 else "acc"),
      "lead": int(r.lead_present > 0.5), "lead_d": round(float(r.lead_d), 1) if r.lead_present > 0.5 else None,
      "lead_v_kph": round(float(r.lead_v) * 3.6, 1) if r.lead_present > 0.5 else None,
      "psa_brake": int(r.can_decel_req > 0.5), "a_ego": round(float(r.a_ego), 2),
      "lat": r.gps_lat, "lon": r.gps_lon,
    })
df = pd.DataFrame(rows)
df.to_csv(OUT_DIR / "gas_overrides.csv", index=False)
print(len(df), "gas overrides of an active deceleration")
df["regime"] = np.where(df.route >= "000000b8", "gain1.55", "gain1.0")
print(df.groupby(["regime", "src"]).size())
print(df.groupby(["regime", "dec"]).size())
print(df.groupby(["src", "lead"]).size())
pd.set_option("display.width", 220)
print(df.drop(columns=["lat", "lon"]).to_string())
