# /// script
# dependencies = ["pandas", "pyarrow", "numpy"]
# ///
import pandas as pd, numpy as np
m = pd.read_parquet("out/m.parquet").sort_values("t").reset_index(drop=True)
R = {3:5.36,4:3.90,5:3.23,6:2.62,7:2.09,8:1.76}
m["eng_whl"] = m.e_P198_ActMod_trqClthTraIntv * m.e2_P152_Gearbx_stGear.map(R)
gmp = (m.ACC_STATUS==4)&(m.POTENTIAL_WHEEL_TORQUE_REQUEST==1)&(m.WHEEL_TORQUE_REQUEST==1)&(~m.gas.astype(bool))
g = m[gmp & m.eng_whl.notna()]
for abs_ in (3,6):
    s = g[g.AUTO_BRAKING_STATUS==abs_]
    err = s.eng_whl - (1.07*s.GMP_WHEEL_TORQUE+7)
    print(f"ABS={abs_}: n={len(s)} req mean {s.GMP_WHEEL_TORQUE.mean():.0f} Nm, engine@wheel mean {s.eng_whl.mean():.0f} Nm, tracking err median {err.median():.0f} rms {np.sqrt((err**2).mean()):.0f}")
    hi = s[s.GMP_WHEEL_TORQUE>250]
    print(f"   req>250: n={len(hi)} req {hi.GMP_WHEEL_TORQUE.mean():.0f} -> engine {hi.eng_whl.mean():.0f}")
# P003 / P002 (gas pedal) during ACC - driver foot?
print("pedal rAPP in GMP:", g.e_P002_Com_rAPP.describe().round(1).to_dict())
