# /// script
# dependencies = ["pandas", "pyarrow", "numpy"]
# ///
import pandas as pd, numpy as np
r = pd.read_parquet("out/raw.parquet")
for a in [0x2B6,0x2F6,0x4F6,0x796,0x452,0x32D,0x38D]:
    for b in sorted(r[r.addr==a].bus.unique()):
        x = r[(r.addr==a)&(r.bus==b)].sort_values("t")
        dt = np.diff(x.t.values)
        print(hex(a), b, "n", len(x), "t0 %.1f t1 %.1f"%(x.t.min(), x.t.max()), "dt med %.4f p1 %.4f p99 %.4f max %.3f"%(np.median(dt), np.percentile(dt,1), np.percentile(dt,99), dt.max()))
cs = pd.read_parquet("out/carState.parquet")
print(cs.t.min(), cs.t.max(), len(cs))
print(cs.describe().T)
