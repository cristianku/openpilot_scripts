# /// script
# dependencies = ["pandas", "pyarrow", "numpy"]
# ///
import pandas as pd, numpy as np
m = pd.read_parquet("out/m.parquet"); m["T"]=m.t-601.33; m["kmh"]=m.vEgo*3.6
for st in [2,3,4,5]:
    s=m[m.ACC_STATUS==st]; print(st, "kmh min %.1f max %.1f"%(s.kmh.min(), s.kmh.max()))
# AUTO_BRAKING_STATUS vs speed
for v in [3,5,6]:
    s=m[m.AUTO_BRAKING_STATUS==v]; print("ABS",v,"kmh min %.1f max %.1f"%(s.kmh.min(), s.kmh.max()))
# transitions of AUTO_BRAKING_STATUS
c = m[m.AUTO_BRAKING_STATUS!=m.AUTO_BRAKING_STATUS.shift()]
print(c[["T","AUTO_BRAKING_STATUS","kmh","ACC_STATUS","f6_ARC_STATUS"]].to_string(index=False))
c = m[m.ACC_STATUS!=m.ACC_STATUS.shift()]
print(c[["T","ACC_STATUS","kmh","gas","brake","u_APPUI_FREIN_RECONSTRUIT","c_RVV_ACC_ACTIVATION_REQ"]].to_string(index=False))
# 2F6 arc status
c = m[m.f6_ARC_STATUS!=m.f6_ARC_STATUS.shift()]
print(c[["T","f6_ARC_STATUS","kmh","ACC_STATUS"]].to_string(index=False))
