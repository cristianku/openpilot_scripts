# /// script
# dependencies = ["pandas", "pyarrow"]
# ///
import pandas as pd
c = pd.read_csv("out/census.csv")
for a in [0x2B6,0x2F6,0x4F6,0x796,0x452,0x32D,0x38D,0x2CD]:
    print(hex(a), c[c.addr==a][["bus","len","n"]].values.tolist())
print("buses:", c.groupby("bus").addr.nunique().to_dict())
cs = pd.read_parquet("out/carState.parquet")
print("duration s", cs.t.max())
b = pd.read_parquet("out/2B6.parquet"); b = b[b.bus==1]
print("2B6 ACC_STATUS counts", b.ACC_STATUS.value_counts().to_dict())
for col in ["POTENTIAL_WHEEL_TORQUE_REQUEST","WHEEL_TORQUE_REQUEST","MDD_DECEL_TYPE","MDD_DECEL_CONTROL_REQ","AUTO_BRAKING_STATUS","PREFILL_REQUEST","GEAR_TYPE"]:
    print(col, b.groupby("ACC_STATUS")[col].value_counts().to_dict())
s = pd.read_parquet("out/452.parquet"); s=s[s.bus==1]
print("452 type", s.LONGITUDINAL_REGULATION_TYPE.value_counts().to_dict(), "rvv", s.RVV_ACC_ACTIVATION_REQ.value_counts().to_dict(), "mode", s.ACC_PROGRAM_MODE.value_counts().to_dict(), "brakeonly", s.BRAKE_ONLY_CMD_BSI.value_counts().to_dict())
# ACC_STATUS segments
b = b.sort_values("t"); ch = b[b.ACC_STATUS != b.ACC_STATUS.shift()]
print(ch[["t","ACC_STATUS"]].to_string())
