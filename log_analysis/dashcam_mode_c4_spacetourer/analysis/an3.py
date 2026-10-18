# /// script
# dependencies = ["pandas", "pyarrow", "numpy"]
# ///
import pandas as pd, numpy as np
m = pd.read_parquet("out/m.parquet"); m["tt"]=m.t-601.33
R=0.329
m["ratio"] = m.e_P000_Com_nEng*2*np.pi/60 / (m.vEgo/R)
mask = ((m.ACC_STATUS==4)&(m.POTENTIAL_WHEEL_TORQUE_REQUEST==1)&(~m.gas)).values
for lag in [0,25,50,75,100,150]:
    f = m.GMP_WHEEL_TORQUE.shift(-lag).values
    ok = mask & ~np.isnan(f)
    e = m.GMP_POTENTIAL_WHEEL_TORQUE.values[ok]-f[ok]
    print(f"potT(t) - whlT(t+{lag*0.02:.1f}s): median {np.median(e):.0f} mad {np.median(abs(e-np.median(e))):.0f}  corr {np.corrcoef(m.GMP_POTENTIAL_WHEEL_TORQUE.values[ok], f[ok])[0,1]:.3f}")
s = m[mask]
print("potT==0 frac", (s.GMP_POTENTIAL_WHEEL_TORQUE==0).mean(), " when whlT<=0:", (s[s.GMP_WHEEL_TORQUE<=0].GMP_POTENTIAL_WHEEL_TORQUE==0).mean())
# steady state: |aEgo|<0.05, rate small
st = s[(s.aEgo.abs()<0.05)&(s.GMP_WHEEL_TORQUE>50)]
print("steady potT/whlT median", (st.GMP_POTENTIAL_WHEEL_TORQUE/st.GMP_WHEEL_TORQUE).median(), "diff median", (st.GMP_POTENTIAL_WHEEL_TORQUE-st.GMP_WHEEL_TORQUE).median())
# WTR=2 frames
w2 = m[m.WHEEL_TORQUE_REQUEST==2]
print("WTR=2 whlT values", w2.GMP_WHEEL_TORQUE.describe().round(0).to_dict())
# brake entry: previous torque vs friction torque*ratio
b = (m.POTENTIAL_WHEEL_TORQUE_REQUEST==2).astype(int); st_idx = m.index[b.diff()==1]
for i in st_idx:
    p = m.loc[i-1]
    print(f"entry {p.tt:.1f}: whlT_prev {p.GMP_WHEEL_TORQUE:.0f}  -trqFrc*ratio {-p.e2_P017_Com_trqFrc*p.ratio:.0f}  P198*ratio {p.e_P198_ActMod_trqClthTraIntv*p.ratio:.0f}  gear {p.e2_P152_Gearbx_stGear} aEgo {p.aEgo:.2f} MDD_first {m.loc[i].MDD_DESIRED_DECELERATION}")
en = m.index[b.diff()==-1]
for i in en:
    p = m.loc[i-1]; q=m.loc[i]
    print(f"exit {q.tt:.1f}: MDD_last {p.MDD_DESIRED_DECELERATION} aEgo {p.aEgo:.2f} whlT_next {q.GMP_WHEEL_TORQUE:.0f} wtr {q.WHEEL_TORQUE_REQUEST} -trqFrc*ratio {-q.e2_P017_Com_trqFrc*q.ratio:.0f} st {q.ACC_STATUS} gas {q.gas}")
# whlT min floor in GMP vs friction
g = m[mask & (m.vEgo>8).values]
print("GMP whlT<-40 frames:", (g.GMP_WHEEL_TORQUE< -40).sum())
