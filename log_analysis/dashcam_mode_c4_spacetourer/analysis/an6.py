# /// script
# dependencies = ["pandas", "pyarrow", "numpy"]
# ///
import pandas as pd, numpy as np
m = pd.read_parquet("out/m.parquet"); m["tt"]=m.t-601.33
a = m[(m.ACC_STATUS==4)&(~m.gas)&(~m.brake)]
print("active no-pedal: aEgo min %.2f max %.2f p1 %.2f p99 %.2f; whlT max %d; MDD min %.2f"%(a.aEgo.min(), a.aEgo.max(), a.aEgo.quantile(.01), a.aEgo.quantile(.99), a.GMP_WHEEL_TORQUE.max(), a.MDD_DESIRED_DECELERATION.min()))
# accel by speed band max
a2 = a.assign(v=a.vEgo*3.6)
print(a2.groupby(pd.cut(a2.v,[30,60,90,110,130]), observed=False).aEgo.agg(["min","max","count"]).round(2))
# WTR=2 durations
w = (m.WHEEL_TORQUE_REQUEST==2).astype(int); g=(w!=w.shift()).cumsum()
for k, s in m[w==1].groupby(g[w==1]):
    print("WTR2 %.2f dur %.2fs st %s whlT %s"%(s.tt.iloc[0], len(s)*0.02, s.ACC_STATUS.unique(), s.GMP_WHEEL_TORQUE.tolist()[:6]))
# carState aEgo vs acal lag (filter)
for lag in range(0,30,3):
    y=m.aEgo.shift(-lag); ok=y.notna()
    print(lag*0.02, round(np.sqrt(np.mean((y[ok]-m.u_ACCEL_LONGI_CALIB[ok])**2)),3), end=" | ")
print()
