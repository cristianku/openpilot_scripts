# /// script
# dependencies = ["pandas", "pyarrow", "numpy"]
# ///
import pandas as pd, numpy as np
pd.set_option("display.width", 250); pd.set_option("display.max_columns", 40)
for f in ["2B6","2F6","4F6","796","452","32D","38D","348","228","208","329","349","30D","3CD"]:
    d = pd.read_parquet(f"out/{f}.parquet")
    print("==", f, len(d), sorted(d.bus.unique()))
    for c in d.columns:
        if c in ("t","bus"): continue
        vc = d[c].value_counts()
        if len(vc) <= 12: print("  ", c, dict(vc))
        else: print("  ", c, "n=%d min %.3f p5 %.3f med %.3f p95 %.3f max %.3f"%(len(vc), d[c].min(), d[c].quantile(.05), d[c].median(), d[c].quantile(.95), d[c].max()))
