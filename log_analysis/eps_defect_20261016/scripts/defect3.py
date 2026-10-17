# /// script
# requires-python = ">=3.11"
# dependencies = ["pycapnp", "zstandard"]
# ///
"""Intorno al primo Defect: 495 grezzo, 3F2 nostro (sendcan) e 3F2 su tutti i src di can."""
import sys
sys.path.insert(0, "/Users/cristianku/GitHub/COMMA.AI/CRISTIANKU/openpilot_scripts/log_analysis")
import psa_eps_timeline as pet

route = sys.argv[1]
which_defect = int(sys.argv[2]) if len(sys.argv) > 2 else 0
segs = sorted((p for p in pet.LOGS_DIR.iterdir() if p.name.startswith(route + "--")),
              key=lambda p: int(p.name.rsplit("--", 1)[1]))
sigs = pet.dbc_signals(pet.DBC, {0x3F2, 0x495})
schema = pet.load_schema()

rows = []
t0 = None
for seg in segs:
    f = seg / "rlog.zst"
    if not f.exists():
        continue
    for ev in pet.read_events(schema, f):
        t = ev.logMonoTime / 1e9
        if t0 is None:
            t0 = t
        t = t - t0
        w = ev.which()
        if w == "sendcan":
            for m in ev.sendcan:
                rows.append((t, "TX", m.src, m.address, bytes(m.dat)))
        elif w == "can":
            for m in ev.can:
                rows.append((t, "RX", m.src, m.address, bytes(m.dat)))

# trova i defect
onsets = []
prev = 0
for t, d, src, addr, dat in rows:
    if d == "RX" and addr == 0x495 and src == 0:
        eps = int(pet.extract(dat, sigs[0x495]["EPS_STATE_LKA"]))
        if eps == 4 and prev != 4:
            onsets.append(t)
        prev = eps
print("defect:", [round(x, 2) for x in onsets])

# conteggio per (dir,src,addr) per capire chi c'e' sul bus
from collections import Counter
cnt = Counter((d, src, addr) for t, d, src, addr, dat in rows)
print("3F2 per direzione/src:", {k: v for k, v in cnt.items() if k[2] == 0x3F2})
print("TX per src/addr:", sorted((k[1], hex(k[2]), v) for k, v in cnt.items() if k[0] == "TX"))

t_on = onsets[which_defect]
print(f"\n==== Defect @ {t_on:.3f} ====")
for t, d, src, addr, dat in rows:
    if t < t_on - 0.35 or t > t_on + 0.6:
        continue
    if addr == 0x495 and d == "RX":
        s = sigs[0x495]
        dec = " ".join(f"{k}={pet.extract(dat, s[k]):g}" for k in s)
        print(f"{t:8.3f} {d} src{src:3d} 495 {dat.hex()}  {dec}")
    elif addr == 0x3F2:
        s = sigs[0x3F2]
        dec = " ".join(f"{k}={pet.extract(dat, s[k]):g}" for k in ("STATUS", "TORQUE", "TORQUE_FACTOR", "LXA_ACTIVATION", "DRIVE", "0_COUNTER", "SET_ANGLE", "unknown2", "unknown4", "LANE_DEPARTURE"))
        print(f"{t:8.3f} {d} src{src:3d} 3F2 {dat.hex()}  {dec}")
