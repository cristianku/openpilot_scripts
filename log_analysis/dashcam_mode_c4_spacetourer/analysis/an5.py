# /// script
# dependencies = ["pandas", "pyarrow", "numpy"]
# ///
import pandas as pd
m = pd.read_parquet("out/m.parquet"); m["tt"]=m.t-601.33
print(pd.crosstab(m.c_FORCE_ACTIVATION_HAB_CMD, m.AUTO_BRAKING_STATUS))
f = m[m.c_FORCE_ACTIVATION_HAB_CMD != m.c_FORCE_ACTIVATION_HAB_CMD.shift()].tt.values
a = m[m.AUTO_BRAKING_STATUS != m.AUTO_BRAKING_STATUS.shift()].tt.values
print("FORCE changes", f.round(2)); print("ABS changes", a.round(2))
