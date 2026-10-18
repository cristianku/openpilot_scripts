# /// script
# dependencies = ["pandas", "pyarrow", "numpy"]
# ///
import pandas as pd, numpy as np
m = pd.read_parquet("out/m.parquet").sort_values("t").reset_index(drop=True)
m["vk"] = m.vEgo*3.6
gmp = (m.ACC_STATUS==4)&(m.POTENTIAL_WHEEL_TORQUE_REQUEST==1)&(m.WHEEL_TORQUE_REQUEST==1)&(~m.gas.astype(bool))
# best lag torque -> aEgo
for lag in [0,10,15,20,25,30,40,50]:  # frames at 50Hz
    a = m.aEgo.shift(-lag)
    x = m.loc[gmp,"GMP_WHEEL_TORQUE"]; y=a[gmp]; v=m.vEgo[gmp]
    ok = y.notna()
    A = np.c_[x[ok], np.ones(ok.sum()), v[ok]**2]
    c, res, *_ = np.linalg.lstsq(A, y[ok], rcond=None)
    print(lag*20,"ms", c.round(6), "rms", np.sqrt(np.mean((A@c-y[ok])**2)).round(3))
