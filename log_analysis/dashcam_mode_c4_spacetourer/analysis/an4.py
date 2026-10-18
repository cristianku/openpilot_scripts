# /// script
# dependencies = ["pandas", "pyarrow", "numpy"]
# ///
import pandas as pd, numpy as np
m = pd.read_parquet("out/m.parquet"); m["tt"]=m.t-601.33; m["kmh"]=m.vEgo*3.6
a = m[(m.ACC_STATUS==4)&(~m.gas)]
nl = a[a.l_TARGET_DETECTED==0]
e = nl.kmh - nl.c_SPEED_SETPOINT
print("no-lead active frames", len(nl), "speed - setpoint km/h: mean %.2f std %.2f p5 %.2f p95 %.2f"%(e.mean(), e.std(), e.quantile(.05), e.quantile(.95)))
# wheel-speed based
e2 = nl.w_VITESSE_VEHICULE_ROUES - nl.c_SPEED_SETPOINT
print("  wheel 38D speed - setpoint: mean %.2f"%e2.mean())
# set speed changes
c = m[m.c_SPEED_SETPOINT != m.c_SPEED_SETPOINT.shift()][["tt","c_SPEED_SETPOINT","kmh","ACC_STATUS"]]
print(c.to_string(index=False))
ld = a[(a.l_TARGET_DETECTED==1)]
print("lead frames active", len(ld), "time gap setpoint", a.c_INTER_VEHICLE_TIME_SETPOINT.unique())
st = ld[(ld.l_RELATIVE_SPEED.abs()<0.5)]
print("steady following: TIME_GAP med %.2f p10 %.2f p90 %.2f ; dist/v med %.2f n=%d"%(st.l_TIME_GAP.median(), st.l_TIME_GAP.quantile(.1), st.l_TIME_GAP.quantile(.9), (st.l_DISTANCE_GAP/st.vEgo).median(), len(st)))
# 2F6 vs 4F6 consistency
x = m[(m.l_TARGET_DETECTED==1)&(m.f6_TARGET_DETECTED==1)]
print("dist 2F6-4F6 med %.2f; disp_time-TIME_GAP med %.2f"%((x.f6_INTER_VEHICLE_DISTANCE-x.l_DISTANCE_GAP).median(), (x.f6_DISPLAY_INTERVEHICLE_TIME-x.l_TIME_GAP).median()))
print("TIME_GAP vs dist/vEgo med", (x.l_TIME_GAP - x.l_DISTANCE_GAP/x.vEgo).median())
print("target detected mismatch frac", (m.l_TARGET_DETECTED != m.f6_TARGET_DETECTED).mean())
# ARTIV_TARGET_CHANGE_INFO toggles
r = pd.read_parquet("out/4F6.parquet").sort_values("t"); r["tt"]=r.t-601.33
ch = r[r.ARTIV_TARGET_CHANGE_INFO != r.ARTIV_TARGET_CHANGE_INFO.shift()]
print("TCI toggles", len(ch)); 
r["dd"] = r.DISTANCE_GAP.diff().abs()
for i in ch.index[:25]:
    j = r.index.get_loc(i)
    w = r.iloc[max(j-1,0):j+1]
    print("  %.1f TCI->%d tgt %d dist %s->%s"%(r.tt[i], r.ARTIV_TARGET_CHANGE_INFO[i], r.TARGET_DETECTED[i], w.DISTANCE_GAP.iloc[0], w.DISTANCE_GAP.iloc[-1]))
# target-detected transitions
tg = r[r.TARGET_DETECTED != r.TARGET_DETECTED.shift()]
print("target transitions", len(tg))
# 2F6 MDD_DECEL_CONTROL_REQ vs 2B6
print("2F6 decel_req vs 2B6:", pd.crosstab(m.MDD_DECEL_CONTROL_REQ, m.f6_MDD_DECEL_CONTROL_REQ).to_dict())
print("2B6 ABS vs 2F6 ABS equal frac", (m.AUTO_BRAKING_STATUS==m.f6_AUTO_BRAKING_STATUS).mean())
# 32D standstill / ARRET
print("ACC_ETAT_DECEL vs pot:", pd.crosstab(m.u_ACC_ETAT_DECEL_OR_ESP_STATUS, m.POTENTIAL_WHEEL_TORQUE_REQUEST).to_dict())
print("ACC_ETAT_DECEL vs st:", pd.crosstab(m.u_ACC_ETAT_DECEL_OR_ESP_STATUS, m.ACC_STATUS).to_dict())
print("EFFORT_FREIN vs pot:", pd.crosstab(m.u_EFFORT_FREIN, m.POTENTIAL_WHEEL_TORQUE_REQUEST).to_dict())
print("APPUI vs brake:", pd.crosstab(m.u_APPUI_FREIN_RECONSTRUIT, m.brake).to_dict())
print("452 FORCE_ACT vs st", pd.crosstab(m.c_FORCE_ACTIVATION_HAB_CMD, m.ACC_STATUS).to_dict())
print("452 ARC_HABIT vs st", pd.crosstab(m.c_ARC_HABIT_ACTIVATION_REQ, m.ACC_STATUS).to_dict())
print("452 TIME_SET vs rvv", pd.crosstab(m.c_INTER_VEHICLE_TIME_SETPOINT, m.c_RVV_ACC_ACTIVATION_REQ).to_dict())
