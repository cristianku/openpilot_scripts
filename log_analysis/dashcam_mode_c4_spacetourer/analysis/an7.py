# /// script
# dependencies = ["pandas", "pyarrow", "numpy"]
# ///
import pandas as pd
m = pd.read_parquet("out/m.parquet")
print("GEAR_TYPE == COUNTER&1:", (m.GEAR_TYPE == (m.COUNTER.astype(int)&1)).mean())
b = m[m.POTENTIAL_WHEEL_TORQUE_REQUEST==2]
print("MDD in brake mode: min %.2f max %.2f"%(b.MDD_DESIRED_DECELERATION.min(), b.MDD_DESIRED_DECELERATION.max()))
print("2F6 DRIVE_AWAY", m.f6_DRIVE_AWAY_REQUEST.unique(), "32D standstill", m.u_VEHICLE_STANDSTILL.unique(), "vmin active", (m[m.ACC_STATUS==4].vEgo.min()*3.6))
print("452 COCKPIT_GO", m.c_COCKPIT_GO_ACC_REQUEST.unique())
