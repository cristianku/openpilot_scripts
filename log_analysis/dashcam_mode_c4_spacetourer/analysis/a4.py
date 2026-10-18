# /// script
# dependencies = ["pandas", "pyarrow", "numpy"]
# ///
import pandas as pd, numpy as np
r = pd.read_parquet("out/raw.parquet")
x = r[(r.addr==0x2B6)].sort_values("t").reset_index(drop=True)
d = pd.read_parquet("out/2B6.parquet").sort_values("t").reset_index(drop=True)
x["st"] = d.ACC_STATUS.values; x["mt"]=d.MIN_TIME_FOR_DESIRED_GEAR.values; x["gt"]=d.GEAR_TYPE.values; x["cnt"]=d.COUNTER.values
for st in [2,3,4,5,6]:
    s = x[x.st==st]
    print("status", st)
    print(s.head(20)[["t","hex","mt","gt","cnt"]].to_string(index=False))
# relation of MIN_TIME / GEAR_TYPE to counter
print(pd.crosstab(x.cnt, [x.mt]))
print(pd.crosstab(x.cnt, x.gt))
