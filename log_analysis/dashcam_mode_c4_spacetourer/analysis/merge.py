# /// script
# dependencies = ["pandas", "pyarrow", "numpy"]
# ///
import pandas as pd, numpy as np
def L(f, bus=None, cols=None, pre=""):
    d = pd.read_parquet(f"out/{f}.parquet")
    if bus is not None: d = d[d.bus==bus]
    d = d.sort_values("t")
    d = d[["t"]+cols] if cols else d.drop(columns=["bus"])
    return d.rename(columns={c: pre+c for c in d.columns if c!="t"})
m = L("2B6", 1, pre="")
def J(m, d):
    return pd.merge_asof(m, d, on="t", direction="backward")
m = J(m, L("2F6",1,["TARGET_DETECTED","INTER_VEHICLE_DISTANCE","ARC_STATUS","DISPLAY_INTERVEHICLE_TIME","MDD_DECEL_CONTROL_REQ","AUTO_BRAKING_STATUS","DRIVE_AWAY_REQUEST"], "f6_"))
m = J(m, L("4F6",1,["TIME_GAP","DISTANCE_GAP","RELATIVE_SPEED","TARGET_DETECTED","ARTIV_TARGET_CHANGE_INFO","ARTIV_SENSOR_STATE"], "l_"))
m = J(m, L("452",1,["LONGITUDINAL_REGULATION_TYPE","SPEED_SETPOINT","RVV_ACC_ACTIVATION_REQ","INTER_VEHICLE_TIME_SETPOINT","ARC_HABIT_ACTIVATION_REQ","FORCE_ACTIVATION_HAB_CMD","COCKPIT_GO_ACC_REQUEST"], "c_"))
m = J(m, L("32D",1,["ACCEL_LONGI_CALIB","EFFORT_FREIN","ACC_ETAT_DECEL_OR_ESP_STATUS","APPUI_FREIN_RECONSTRUIT","VEHICLE_STANDSTILL"], "u_"))
m = J(m, L("38D",0,["ACCEL_LONGI_ROUES","VITESSE_VEHICULE_ROUES"], "w_"))
m = J(m, L("208",0,["P000_Com_nEng","P003_Com_trqActOut","P002_Com_rAPP","P014_Brk_stRed","P198_ActMod_trqClthTraIntv"], "e_"))
m = J(m, L("348",0,["P152_Gearbx_stGear","P019_Com_trqPrp","P017_Com_trqFrc"], "e2_"))
m = J(m, L("349",0,["P283_Com_stGearTrgtPos","P009_Com_bGearShftActv","P057_Com_xTrqTIIDes","P333_Com_stGbxTrqIntv","P030_Gbx_stDrvTrnEgd"], "g_"))
m = J(m, L("3CD",0,["P226_Com_stBrkActv","BRAKE_PRESSURE"], "b_"))
cs = pd.read_parquet("out/carState.parquet").sort_values("t")
m = J(m, cs)
m.to_parquet("out/m.parquet")
print(m.shape); print(m.columns.tolist())
