# /// script
# dependencies = ["pandas", "pyarrow", "numpy", "cantools"]
# ///
import pandas as pd, numpy as np, cantools
db = cantools.database.load_file("psa.dbc", strict=False)
r = pd.read_parquet("out/raw.parquet")
for a in [0x2B6, 0x2F6, 0x4F6, 0x796, 0x452, 0x32D]:
    msg = db.get_message_by_frame_id(a)
    covered = set()
    for s in msg.signals:
        # cantools: s.start is DBC start bit; compute bit set via encoding a mask
        for i in range(msg.length*8):
            pass
    # compute coverage by encoding all-ones per signal
    cov = np.zeros(msg.length*8, bool)
    for s in msg.signals:
        d = {x.name: (x.minimum if False else 0) for x in msg.signals}
        raw = bytearray(msg.length)
        # set signal raw to max to get mask
        data = msg.encode({x.name: 0 for x in msg.signals}, scaling=False, strict=False, padding=False)
        data2 = msg.encode({x.name: ((1<<x.length)-1 if x.name==s.name else 0) for x in msg.signals}, scaling=False, strict=False, padding=False)
        b = int.from_bytes(bytes(a ^ b for a,b in zip(data, data2)), "big")
        for i in range(msg.length*8):
            if (b >> (msg.length*8-1-i)) & 1: cov[i]=True
    x = r[(r.addr==a)&(r.bus==1)]
    arr = np.array([list(bytes.fromhex(h)) for h in x.hex], dtype=np.uint8)
    bits = np.unpackbits(arr, axis=1)  # msb first per byte -> index byte*8 + (7-bit)
    var = bits.min(0) != bits.max(0)
    unc_var = [ (i//8, 7-(i%8), bits[:,i].mean().round(3)) for i in range(bits.shape[1]) if var[i] and not cov[i]]
    const_unc = [ (i//8, 7-(i%8), int(bits[0,i])) for i in range(bits.shape[1]) if not var[i] and not cov[i] and bits[0,i]==1]
    print(hex(a), msg.name, "len", msg.length, "uncovered varying bits (byte,bit,mean):", unc_var, " uncovered constant-1 bits:", const_unc)
