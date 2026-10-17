# /// script
# requires-python = ">=3.11"
# dependencies = ["numpy", "pandas"]
# ///
"""Does the car follow the model's own trajectory? (closed-loop tracking bias)

For every engaged 20 Hz sample with planner source = e2e (the model is the one in command)
compare the distance actually travelled in the next T seconds with the modelV2 predicted
position at +T s (md_x_Ts) and the speed reached with the predicted speed (md_v_Ts).

Groups: PSA brake gain regime (1.0 routes <= 0000007d, 1.55 routes >= 000000b8, measured
from CAN in this investigation) x request bin (braking / near zero / accelerating).
A negative distance bias while braking means the vehicle decelerates harder than the plan.

Usage: uv run plan_tracking.py   -> out/plan_tracking.csv + stdout
"""
import glob
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import OUT_DIR  # noqa: E402

DT = 0.05
rows = []
for f in sorted(glob.glob(str(OUT_DIR / "timeline" / "*.csv.gz"))):
  route = Path(f).name.replace(".csv.gz", "")
  gain = 1.55 if route >= "000000b8" else 1.0
  d = pd.read_csv(f, usecols=["route_t", "v_ego", "plan_source", "plan_a_target", "cc_long_active", "md_x_2s",
                              "md_x_4s", "md_v_2s", "md_v_4s", "brake_pressed", "gas_pressed", "can_decel_req"])
  v = d.v_ego.to_numpy()
  t = d.route_t.to_numpy()
  eng = (d.cc_long_active.fillna(0) > 0.5).to_numpy() & (d.brake_pressed.fillna(0) < 0.5).to_numpy() & (d.gas_pressed.fillna(0) < 0.5).to_numpy()
  cum = np.concatenate([[0.0], np.cumsum(v * DT)])
  for T in (2, 4):
    n = int(T / DT)
    for i in range(0, len(d) - n, 4):
      if not eng[i:i + n + 1].all():
        continue
      if abs(t[i + n] - t[i] - T) > 0.2:
        continue
      if d.plan_source.iloc[i] != 4:
        continue
      if v[i] < 3.0:
        continue
      a = d.plan_a_target.iloc[i]
      if a < -0.3:
        b = "brake(<-0.3)"
      elif a < 0.2:
        b = "neutral"
      else:
        b = "accel(>0.2)"
      x_pred = d["md_x_%ds" % T].iloc[i]
      v_pred = d["md_v_%ds" % T].iloc[i]
      rows.append((route, gain, T, b, v[i] * 3.6, cum[i + n] - cum[i] - x_pred, (v[i + n] - v_pred) * 3.6, d.can_decel_req.iloc[i]))
df = pd.DataFrame(rows, columns=["route", "gain", "T", "bin", "v_kph", "dist_err_m", "speed_err_kph", "psa_brake"])
df.to_csv(OUT_DIR / "plan_tracking.csv", index=False)
pd.set_option("display.width", 200)
g = df.groupby(["T", "bin", "gain"]).agg(n=("dist_err_m", "size"), v=("v_kph", "median"), dist_err_med=("dist_err_m", "median"),
                                         dist_err_p25=("dist_err_m", lambda s: s.quantile(0.25)), dist_err_p75=("dist_err_m", lambda s: s.quantile(0.75)),
                                         speed_err_med=("speed_err_kph", "median"), routes=("route", "nunique"))
print(g.round(2).to_string())
