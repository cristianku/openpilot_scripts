# /// script
# dependencies = ["pandas", "pyarrow", "numpy"]
# ///
import pandas as pd, numpy as np
m = pd.read_parquet("out/m.parquet"); m["tt"]=m.t-601.33
dt = 0.02
# --- MDD when not braking
print("MDD when pot!=2:", m[m.POTENTIAL_WHEEL_TORQUE_REQUEST!=2].MDD_DESIRED_DECELERATION.unique())
print("torques when pot==2:", m[m.POTENTIAL_WHEEL_TORQUE_REQUEST==2][["GMP_WHEEL_TORQUE","GMP_POTENTIAL_WHEEL_TORQUE"]].drop_duplicates().values.tolist())
print("torques when st in 2,3:", m[m.ACC_STATUS.isin([2,3])][["GMP_WHEEL_TORQUE","GMP_POTENTIAL_WHEEL_TORQUE","MDD_DESIRED_DECELERATION","MIN_TIME_FOR_DESIRED_GEAR"]].drop_duplicates().values.tolist())
# --- lag: brake episodes, resample to uniform 50Hz index already ~
b = m.POTENTIAL_WHEEL_TORQUE_REQUEST==2
grp = (b != b.shift()).cumsum()
for name, sig in [("aEgo","aEgo"),("acal","u_ACCEL_LONGI_CALIB"),("arou","w_ACCEL_LONGI_ROUES")]:
    res=[]
    for g, s in m[b].groupby(grp[b]):
        if len(s) < 100: continue
        i0, i1 = s.index[0], s.index[-1]
        cmd = m.loc[i0:i1, "MDD_DESIRED_DECELERATION"].values
        best=None
        for lag in range(0, 60):
            y = m.loc[i0+lag:i1+lag, sig].values[:len(cmd)]
            if len(y) < len(cmd): break
            e = np.sqrt(np.mean((y-cmd)**2))
            if best is None or e < best[1]: best=(lag,e, np.mean(y-cmd))
        res.append((round(m.tt[i0],1), best[0]*dt, round(best[1],3), round(best[2],3)))
    print("lag MDD->", name, res)
# --- MDD rate
s = m[b]
d = s.MDD_DESIRED_DECELERATION.diff()[b.shift().fillna(False)]
print("MDD step per frame:", d.round(2).value_counts().to_dict())
# jerk rates over 0.2s
for g, s in m[b].groupby(grp[b]):
    x = s.MDD_DESIRED_DECELERATION.values
    if len(x)<20: continue
    r = (x[10:]-x[:-10])/0.2
    print("ep %.1f MDD rate min %.2f max %.2f m/s3"%(s.tt.iloc[0], r.min(), r.max()))
# --- wheel torque rate in GMP
g = m[(m.POTENTIAL_WHEEL_TORQUE_REQUEST==1)&(m.ACC_STATUS==4)&(~m.gas)]
w = g.GMP_WHEEL_TORQUE.values; ok = np.diff(g.index.values[:])==1
dw = np.diff(w)[ok]/dt
print("whlT rate Nm/s pct:", np.percentile(dw,[0.1,1,5,50,95,99,99.9]).round(0))
