# /// script
# dependencies = ["pandas", "pyarrow", "numpy"]
# ///
import pandas as pd
r = pd.read_parquet("out/raw.parquet")
for a in [0x208,0x228,0x348,0x452]:
    for b in [0,1,2]:
        x = r[(r.addr==a)&(r.bus==b)].sort_values("t")
        if len(x): print(hex(a), b, len(x), x.hex.iloc[1000:1006].tolist())
x = r[(r.addr==0x452)&(r.bus==0)].sort_values("t")
print(x.hex.str[:4].value_counts().head(10))
y = r[(r.addr==0x452)&(r.bus==1)].sort_values("t")
print(y.hex.str[:4].value_counts().head(10))
