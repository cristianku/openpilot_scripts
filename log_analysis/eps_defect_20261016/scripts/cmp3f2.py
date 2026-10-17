# /// script
# requires-python = ">=3.11"
# dependencies = ["pycapnp", "zstandard"]
# ///
"""Distribuzione dei 3F2 nostri (TX) e della telecamera (src2), e gli ultimi prima di ogni Defect."""
import sys
from pathlib import Path
from collections import Counter
sys.path.insert(0, "/Users/cristianku/GitHub/COMMA.AI/CRISTIANKU/openpilot_scripts/log_analysis")
import psa_eps_timeline as pet
sigs = pet.dbc_signals(pet.DBC, {0x495})
schema = pet.load_schema()
for rdir in sys.argv[1:]:
    rdir = Path(rdir)
    segs = sorted((p for p in rdir.iterdir() if (p / "rlog.zst").exists()), key=lambda p: int(p.name.rsplit("--", 1)[1]))
    tx = []; cam = []; prev = 0; onsets = []; t0 = None
    for seg in segs:
        for ev in pet.read_events(schema, seg / "rlog.zst"):
            if t0 is None: t0 = ev.logMonoTime
            t = (ev.logMonoTime - t0) / 1e9
            w = ev.which()
            if w == "sendcan":
                for m in ev.sendcan:
                    if m.address == 0x3F2: tx.append((t, bytes(m.dat).hex()))
            elif w == "can":
                for m in ev.can:
                    if m.address == 0x3F2 and m.src == 2: cam.append((t, bytes(m.dat).hex()))
                    if m.address == 0x495 and m.src == 0:
                        e = int(pet.extract(bytes(m.dat), sigs[0x495]["EPS_STATE_LKA"]))
                        if e == 4 and prev != 4: onsets.append(t)
                        prev = e
    print(f"== {rdir.name}: defect={len(onsets)}")
    print("  TX piu' frequenti :", Counter(d for t, d in tx).most_common(6))
    print("  CAM piu' frequenti:", Counter(d for t, d in cam).most_common(6))
    # byte per byte: valori che la camera usa e noi mai
    for i in range(8):
        tv = Counter(d[2*i:2*i+2] for t, d in tx); cv = Counter(d[2*i:2*i+2] for t, d in cam)
        print(f"  byte{i}: TX={dict(tv.most_common(5))}  CAM={dict(cv.most_common(5))}")
    for t_on in onsets:
        lt = [d for t, d in tx if t_on - 0.2 <= t <= t_on]
        lc = [d for t, d in cam if t_on - 0.2 <= t <= t_on]
        print(f"  Defect @{t_on:8.2f}  TX={lt}  CAM={lc}")
