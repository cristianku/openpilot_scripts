# /// script
# requires-python = ">=3.11"
# dependencies = ["numpy", "pandas"]
# ///
"""Layer E/F check: openpilot request (carControl.actuators.accel) -> PSA brake command
(0x2B6 MDD_DESIRED_DECELERATION, as transmitted) -> measured aEgo 0.3 s later.

Only engaged samples in PSA brake mode (MDD_DECEL_CONTROL_REQ=1), no pedals, vEgo > 3 m/s,
and a request that was steady (std < 0.05 over the 0.3 s lag) so the filter has settled.

Usage: uv run response_bins.py -> out/response_bins.csv + stdout
"""
import glob
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import OUT_DIR  # noqa: E402

LAG = 6
BINS = [(-0.6, -0.3), (-1.0, -0.6), (-1.5, -1.0), (-3.0, -1.5)]
rows = []
for f in sorted(glob.glob(str(OUT_DIR / "timeline" / "*.csv.gz"))):
  route = Path(f).name.replace(".csv.gz", "")
  d = pd.read_csv(f, usecols=["cc_accel", "can_decel", "can_decel_req", "cc_long_active", "a_ego", "v_ego", "pitch",
                              "brake_pressed", "gas_pressed"])
  d["a_fut"] = d.a_ego.shift(-LAG)
  steady = (d.cc_accel.rolling(LAG).std() < 0.05).shift(-LAG).fillna(False)
  m = (d.can_decel_req > 0.5) & (d.cc_long_active > 0.5) & (d.cc_accel < -0.3) & (d.v_ego > 3) & \
      (d.brake_pressed < 0.5) & (d.gas_pressed < 0.5) & steady
  x = d[m]
  for lo, hi in BINS:
    b = x[(x.cc_accel >= lo) & (x.cc_accel < hi)]
    if len(b) < 10:
      continue
    rows.append({"route": route, "regime": "1.55" if route >= "000000b8" else "1.0", "bin": "%.1f..%.1f" % (lo, hi),
                 "n": len(b), "req": b.cc_accel.mean(), "cmd": b.can_decel.mean(), "meas": b.a_fut.mean(),
                 "meas_minus_cmd": (b.a_fut - b.can_decel).mean(), "pitch_deg": b.pitch.mean() * 57.2958})
df = pd.DataFrame(rows)
df.to_csv(OUT_DIR / "response_bins.csv", index=False)
agg = []
for (reg, b), g in df.groupby(["regime", "bin"]):
  w = g.n
  agg.append({"regime": reg, "bin": b, "routes": len(g), "n": int(w.sum()),
              "req": (g.req * w).sum() / w.sum(), "cmd": (g.cmd * w).sum() / w.sum(), "meas": (g.meas * w).sum() / w.sum(),
              "meas_minus_cmd": (g.meas_minus_cmd * w).sum() / w.sum()})
a = pd.DataFrame(agg)
a["meas_over_req"] = a.meas / a.req
a.to_csv(OUT_DIR / "response_bins_summary.csv", index=False)
print(a.round(2).to_string())
