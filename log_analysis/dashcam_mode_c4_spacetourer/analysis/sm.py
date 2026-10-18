# /// script
# dependencies = ["pandas", "pyarrow", "numpy"]
# ///
import pandas as pd, numpy as np
pd.set_option("display.width", 250)
m = pd.read_parquet("out/m.parquet")
m["T"] = m.t - 601.33
k = ["ACC_STATUS","c_RVV_ACC_ACTIVATION_REQ","c_LONGITUDINAL_REGULATION_TYPE","gas","brake","AUTO_BRAKING_STATUS","f6_ARC_STATUS","POTENTIAL_WHEEL_TORQUE_REQUEST","u_APPUI_FREIN_RECONSTRUIT"]
key = m[k].fillna(-1).astype(str).agg("|".join, axis=1)
ch = m[key != key.shift()]
out = ch[["T"]+k+["vEgo","c_SPEED_SETPOINT","c_INTER_VEHICLE_TIME_SETPOINT","l_TARGET_DETECTED","MDD_DESIRED_DECELERATION","GMP_WHEEL_TORQUE"]].copy()
out["vEgo"] = (out.vEgo*3.6).round(1)
out.columns = ["T","st","rvv","type","gas","brk","abs","arc","pot","appui","kmh","set","tgap","lead","decel","whlT"]
# drop pot-only changes inside status 4 for brevity
print(len(out))
print(out[(out.pot.shift()==out.pot) | (out.st!=out.st.shift()) | True].to_string(index=False, max_rows=400))
