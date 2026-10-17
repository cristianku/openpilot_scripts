# /// script
# requires-python = ">=3.11"
# dependencies = ["numpy", "pandas"]
# ///
"""DEC (Dynamic Experimental Control) mode switches and what they do to the planner target.

The running build (2026.003.000, before sunnypilot commit 5ec0c0219 "Sunset DEC") gates the
e2e candidate with DEC: only in 'blended' mode does modelV2.action.desiredAcceleration take
part in the min() of longitudinal_planner.py; in 'acc' mode the target is min(MPC, cruise).
This script finds every engaged DEC switch and measures the planner aTarget step 0.5 s
before -> 0.5 s after, together with what the model was asking at that moment.

Usage: uv run dec_switching.py   -> out/dec_switches.csv + stdout summary
"""
import glob
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import OUT_DIR  # noqa: E402

rows = []
total_eng_s = 0.0
for f in sorted(glob.glob(str(OUT_DIR / "timeline" / "*.csv.gz"))):
  route = Path(f).name.replace(".csv.gz", "")
  d = pd.read_csv(f, usecols=["route_t", "seg", "seg_t", "v_ego", "dec_state", "cc_long_active", "plan_a_target",
                              "md_des_accel", "plan_source", "lead_present", "gas_pressed", "brake_pressed"])
  eng = (d.cc_long_active.fillna(0) > 0.5).to_numpy()
  total_eng_s += eng.sum() * 0.05
  dec = d.dec_state.to_numpy()
  pa = d.plan_a_target.to_numpy()
  ma = d.md_des_accel.to_numpy()
  for i in range(10, len(d) - 10):
    if dec[i] != dec[i] or dec[i - 1] != dec[i - 1] or dec[i] == dec[i - 1]:
      continue
    if not eng[i - 10:i + 11].all():
      continue
    rows.append({
      "route": route, "seg": int(d.seg.iloc[i]), "seg_t": round(float(d.seg_t.iloc[i]), 1),
      "route_t": round(float(d.route_t.iloc[i]), 1), "to": "blended" if int(dec[i]) == 1 else "acc",
      "v_kph": round(float(d.v_ego.iloc[i]) * 3.6, 1), "plan_before": round(float(pa[i - 10]), 2),
      "plan_after": round(float(pa[i + 10]), 2), "model_at_switch": round(float(ma[i]), 2),
      "step": round(float(pa[i + 10] - pa[i - 10]), 2), "lead": int(d.lead_present.iloc[i] > 0.5),
    })
df = pd.DataFrame(rows)
df.to_csv(OUT_DIR / "dec_switches.csv", index=False)
print("engaged hours: %.2f, DEC switches while engaged: %d (%.1f per engaged minute)" % (
  total_eng_s / 3600, len(df), len(df) / max(total_eng_s / 60, 1e-6)))
to_acc = df[df.to] if False else df[df["to"] == "acc"]
print("switches to acc while the model asked < -0.3:", int((to_acc.model_at_switch < -0.3).sum()),
      " median planner step %.2f m/s^2" % to_acc[to_acc.model_at_switch < -0.3].step.median())
print("  of which planner step > +0.5 m/s^2:", int(((to_acc.model_at_switch < -0.3) & (to_acc.step > 0.5)).sum()))
to_bl = df[df["to"] == "blended"]
print("switches to blended:", len(to_bl), " median planner step %.2f" % to_bl.step.median(),
      " steps < -0.5:", int((to_bl.step < -0.5).sum()))
