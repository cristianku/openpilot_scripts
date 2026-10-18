# /// script
# dependencies = ["pandas", "pyarrow", "numpy"]
# ///
import pandas as pd, numpy as np
from collections import Counter
r = pd.read_parquet("out/raw.parquet")
# checksum: find chk_ini for each message given checksum nibble location (byte, high?)
loc = {0x2B6:(7,False), 0x2F6:(6,False), 0x452:(5,False), 0x32D:(7,False), 0x38D:(5,False)}
for a,(byte,hi) in loc.items():
    for b in sorted(r[r.addr==a].bus.unique()):
        x = r[(r.addr==a)&(r.bus==b)]
        c = Counter()
        for h in x.hex.values:
            d = bytearray(bytes.fromhex(h))
            chk = (d[byte]>>4) if hi else (d[byte]&0xF)
            if hi: d[byte]&=0x0F
            else: d[byte]&=0xF0
            s = sum((v>>4)+(v&0xF) for v in d)
            c[(chk+s)&0xF]+=1
        print(hex(a), b, "chk_ini candidates", c.most_common(3))
# counter monotonic check 2B6/2F6
for a,byte in [(0x2B6,7),(0x2F6,6),(0x32D,7)]:
    x = r[(r.addr==a)&(r.bus==1)].sort_values("t")
    cn = np.array([bytes.fromhex(h)[byte]>>4 for h in x.hex])
    dif = (np.diff(cn))%16
    print(hex(a), "counter step", Counter(dif).most_common(4))
d = pd.read_parquet("out/2B6.parquet").sort_values("t")
s4 = d[d.ACC_STATUS==4]
print(pd.crosstab([s4.POTENTIAL_WHEEL_TORQUE_REQUEST, s4.GEAR_TYPE], s4.MIN_TIME_FOR_DESIRED_GEAR))
for st in [2,3,5,6]:
    s = d[d.ACC_STATUS==st]; print(st, pd.crosstab(s.GEAR_TYPE, s.MIN_TIME_FOR_DESIRED_GEAR).to_dict())
