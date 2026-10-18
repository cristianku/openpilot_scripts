# /// script
# dependencies = ["pandas", "pyarrow"]
# ///
import pandas as pd
m = pd.read_parquet("out/m.parquet"); print(m.columns.tolist()); print(len(m), m.t.min(), m.t.max())
b = pd.read_parquet("out/2B6.parquet")
g = b[(b.ACC_STATUS==4)&(b.POTENTIAL_WHEEL_TORQUE_REQUEST==1)]
print(g.groupby("GEAR_TYPE").MIN_TIME_FOR_DESIRED_GEAR.value_counts())
print(b.groupby(["ACC_STATUS","GEAR_TYPE"]).MIN_TIME_FOR_DESIRED_GEAR.value_counts())
