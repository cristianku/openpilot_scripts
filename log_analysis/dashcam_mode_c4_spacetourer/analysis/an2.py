# /// script
# dependencies = ["pandas", "pyarrow", "numpy"]
# ///
import pandas as pd, numpy as np
m = pd.read_parquet("out/m.parquet"); m["tt"]=m.t-601.33
R = 0.329
# overall ratio from rpm and v
m["ratio"] = m.e_P000_Com_nEng*2*np.pi/60 / (m.vEgo/R)
g = m[(m.ACC_STATUS==4)&(m.POTENTIAL_WHEEL_TORQUE_REQUEST==1)&(~m.gas)&(m.vEgo>8)].copy()
print("ratio by gear:", g.groupby("e2_P152_Gearbx_stGear").ratio.median().round(2).to_dict(), g.e2_P152_Gearbx_stGear.value_counts().to_dict())
for lag in [0,10,20,30,40,50]:
    x = m.GMP_WHEEL_TORQUE.values; 
    for col in ["e_P003_Com_trqActOut","e_P198_ActMod_trqClthTraIntv"]:
        y = m[col].shift(-lag).values
        mask = ((m.ACC_STATUS==4)&(m.POTENTIAL_WHEEL_TORQUE_REQUEST==1)&(~m.gas)&(m.vEgo>8)).values & ~np.isnan(y)
        wr = y[mask]*m.ratio.values[mask]
        A = np.vstack([x[mask], np.ones(mask.sum())]).T
        c, res, *_ = np.linalg.lstsq(A, y[mask], rcond=None)
        c2, *_ = np.linalg.lstsq(A, wr, rcond=None)
        rms = np.sqrt(np.mean((A@c - y[mask])**2)); rms2=np.sqrt(np.mean((A@c2 - wr)**2))
        print(f"lag {lag*0.02:.2f}s {col}: eng = {c[0]:.3f}*whlT + {c[1]:.1f} rms {rms:.1f} | eng*ratio = {c2[0]:.3f}*whlT + {c2[1]:.1f} rms {rms2:.1f}")
# accel model with lag L
for L in [0,15,25,35,45]:
    a = m.aEgo.shift(-L)
    mask = ((m.ACC_STATUS==4)&(m.POTENTIAL_WHEEL_TORQUE_REQUEST==1)&(~m.gas)&(m.vEgo>8)&(m.g_P009_Com_bGearShftActv==0)).values & a.notna().values
    A = np.vstack([m.GMP_WHEEL_TORQUE.values[mask], np.ones(mask.sum()), m.vEgo.values[mask]**2]).T
    c, *_ = np.linalg.lstsq(A, a.values[mask], rcond=None)
    rms = np.sqrt(np.mean((A@c - a.values[mask])**2))
    print(f"L={L*0.02:.2f}s a = {c[0]*1000:.3f}e-3*T + {c[1]:.3f} + {c[2]*1e4:.3f}e-4*v^2  rms {rms:.3f}  m_eff={1/(c[0]*R):.0f}kg  CdA_eq={-c[2]*2*(1/(c[0]*R))/1.2:.2f}")
# simple binned mapping at the best lag: torque needed for accel at speed bands
L=25
a = m.aEgo.shift(-L)
mask = ((m.ACC_STATUS==4)&(m.POTENTIAL_WHEEL_TORQUE_REQUEST==1)&(~m.gas)&(m.vEgo>8))
d = pd.DataFrame(dict(T=m.GMP_WHEEL_TORQUE, a=a, v=(m.vEgo*3.6)))[mask]
d["vb"] = pd.cut(d.v, [30,60,80,100,115,130]); d["ab"] = pd.cut(d.a, [-0.6,-0.3,-0.1,0.1,0.3,0.6,1.0])
print(d.pivot_table(index="ab", columns="vb", values="T", aggfunc="median", observed=False).round(0))
print(d.pivot_table(index="ab", columns="vb", values="T", aggfunc="count", observed=False))
print("whlT range in GMP:", d["T"].min(), d["T"].max(), "potT range", m[mask].GMP_POTENTIAL_WHEEL_TORQUE.min(), m[mask].GMP_POTENTIAL_WHEEL_TORQUE.max())
