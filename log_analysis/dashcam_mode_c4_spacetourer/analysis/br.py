# /// script
# dependencies = ["pandas", "pyarrow", "numpy"]
# ///
import pandas as pd, numpy as np
pd.set_option("display.width", 250)
m = pd.read_parquet("out/m.parquet"); m["tt"]=m.t-601.33; m["kmh"]=m.vEgo*3.6
b = (m.POTENTIAL_WHEEL_TORQUE_REQUEST==2).astype(int)
edges = b.diff().fillna(0)
starts = m.index[edges==1].tolist(); ends = m.index[edges==-1].tolist()
rows=[]
for s in starts:
    e = next((x for x in ends if x> s), len(m)-1)
    seg = m.loc[s:e-1]
    pre = m.loc[max(s-50,0):s-1]; post = m.loc[e:e+50]
    rows.append(dict(T0=m.tt[s], dur=m.tt[e]-m.tt[s], kmh=m.kmh[s], decel_min=seg.MDD_DESIRED_DECELERATION.min(),
        decel_first=seg.MDD_DESIRED_DECELERATION.iloc[0], decel_last=seg.MDD_DESIRED_DECELERATION.iloc[-1],
        aEgo_min=seg.aEgo.min(), calib_min=seg.u_ACCEL_LONGI_CALIB.min(),
        T_pre=pre.GMP_WHEEL_TORQUE.iloc[-1] if len(pre) else np.nan, Tp_pre=pre.GMP_POTENTIAL_WHEEL_TORQUE.iloc[-1] if len(pre) else np.nan,
        T_post=m.GMP_WHEEL_TORQUE[e], Tp_post=m.GMP_POTENTIAL_WHEEL_TORQUE[e],
        Tbrk=seg.GMP_WHEEL_TORQUE.unique()[:3].tolist(), Tpbrk_range=(seg.GMP_POTENTIAL_WHEEL_TORQUE.min(), seg.GMP_POTENTIAL_WHEEL_TORQUE.max()),
        lead=seg.l_TARGET_DETECTED.max(), dist=seg.l_DISTANCE_GAP.min(), vrel=seg.l_RELATIVE_SPEED.min(), st_after=m.ACC_STATUS[e], brk=seg.brake.any(), gas=seg.gas.any(),
        effort=seg.u_EFFORT_FREIN.mean(), accst=seg.u_ACC_ETAT_DECEL_OR_ESP_STATUS.unique().tolist(), brkactv=seg.b_P226_Com_stBrkActv.unique().tolist()))
r = pd.DataFrame(rows)
print(r.to_string())
print("total brake s", r.dur.sum(), "n", len(r))
