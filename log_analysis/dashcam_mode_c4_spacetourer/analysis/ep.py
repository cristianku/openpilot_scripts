# /// script
# dependencies = ["pandas", "pyarrow", "numpy"]
# ///
import pandas as pd, numpy as np, sys
pd.set_option("display.width", 300); pd.set_option("display.max_rows", 2000)
m = pd.read_parquet("out/m.parquet"); m["tt"]=(m.t-601.33).round(2); m["kmh"]=(m.vEgo*3.6).round(1)
a, b, step = float(sys.argv[1]), float(sys.argv[2]), int(sys.argv[3])
s = m[(m.tt>=a)&(m.tt<=b)].iloc[::step]
cols = ["tt","ACC_STATUS","POTENTIAL_WHEEL_TORQUE_REQUEST","WHEEL_TORQUE_REQUEST","MDD_DESIRED_DECELERATION","GMP_WHEEL_TORQUE","GMP_POTENTIAL_WHEEL_TORQUE","MIN_TIME_FOR_DESIRED_GEAR","aEgo","u_ACCEL_LONGI_CALIB","w_ACCEL_LONGI_ROUES","u_EFFORT_FREIN","u_ACC_ETAT_DECEL_OR_ESP_STATUS","b_BRAKE_PRESSURE","e_P003_Com_trqActOut","e_P198_ActMod_trqClthTraIntv","e_P000_Com_nEng","e2_P152_Gearbx_stGear","kmh","c_SPEED_SETPOINT","l_DISTANCE_GAP","l_RELATIVE_SPEED","l_TIME_GAP","gas","brake"]
s = s[cols].copy()
s.columns = ["tt","st","pot","wtr","mdd","whlT","potT","mt","aEgo","acal","arou","eff","accst","bp","engT","clT","rpm","gear","kmh","set","dist","vrel","tgap","gas","brk"]
s["aEgo"]=s.aEgo.round(2)
print(s.to_string(index=False))
