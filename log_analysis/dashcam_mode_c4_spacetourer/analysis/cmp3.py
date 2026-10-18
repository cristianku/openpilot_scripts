# /// script
# dependencies = ["pandas", "pyarrow", "numpy"]
# ///
import pandas as pd, numpy as np
m = pd.read_parquet("out/m.parquet").sort_values("t").reset_index(drop=True)
m["a"] = m.aEgo.shift(-10)
gmp = (m.ACC_STATUS==4)&(m.POTENTIAL_WHEEL_TORQUE_REQUEST==1)&(m.WHEEL_TORQUE_REQUEST==1)&(~m.gas.astype(bool))
g = m[gmp]
for abs_ in (3,6):
    s = g[g.AUTO_BRAKING_STATUS==abs_]
    print(f"AUTO_BRAKING_STATUS={abs_}: n={len(s)} v={s.vEgo.min()*3.6:.0f}-{s.vEgo.max()*3.6:.0f} kmh  whlT max={s.GMP_WHEEL_TORQUE.max():.0f}  frames whlT>300: {(s.GMP_WHEEL_TORQUE>300).sum()}  a>0.3: {(s.a>0.3).sum()}")
print("2F6 ARC_STATUS in GMP:", g.f6_ARC_STATUS.value_counts().to_dict(), " 2F6 ABS:", g.f6_AUTO_BRAKING_STATUS.value_counts().to_dict())
print("4F6 SENSOR_STATE in GMP:", g.l_ARTIV_SENSOR_STATE.value_counts().to_dict())
print("452 in GMP: RVV", g.c_RVV_ACC_ACTIVATION_REQ.value_counts().to_dict(), "FORCE_HAB", g.c_FORCE_ACTIVATION_HAB_CMD.value_counts().to_dict(), "ARC_HABIT", g.c_ARC_HABIT_ACTIVATION_REQ.value_counts().to_dict())
print("gearbox torque intervention P333 in GMP:", g.g_P333_Com_stGbxTrqIntv.value_counts().to_dict())
print("gear in GMP:", g.e2_P152_Gearbx_stGear.value_counts().sort_index().to_dict())
# frames where stock request torque > engine actual
print("cols e:", [c for c in m.columns if c.startswith(("e_","e2_","g_"))])
