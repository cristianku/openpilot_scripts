# /// script
# requires-python = ">=3.11"
# dependencies = ["pycapnp", "zstandard"]
# ///
"""Intervalli tra 3F2 realmente usciti (echo src128, timestamp panda busTime) vs camera (src2); intervallo minimo prima dei Defect."""
import sys
from pathlib import Path
from collections import Counter
sys.path.insert(0, "/Users/cristianku/GitHub/COMMA.AI/CRISTIANKU/openpilot_scripts/log_analysis")
import psa_eps_timeline as pet
sigs = pet.dbc_signals(pet.DBC, {0x495})
schema = pet.load_schema()
def hist(iv):
    b = Counter()
    for x in iv:
        ms = x * 1000
        if ms < 20: b["<20"] += 1
        elif ms < 35: b["20-35"] += 1
        elif ms < 45: b["35-45"] += 1
        elif ms < 55: b["45-55"] += 1
        elif ms < 65: b["55-65"] += 1
        else: b[">65"] += 1
    return dict(b)
for rdir in sys.argv[1:]:
    rdir = Path(rdir)
    segs = sorted((p for p in rdir.iterdir() if (p / "rlog.zst").exists()), key=lambda p: int(p.name.rsplit("--", 1)[1]))
    echo = []; cam = []; prev = 0; onsets = []; t0 = None
    for seg in segs:
        for ev in pet.read_events(schema, seg / "rlog.zst"):
            if t0 is None: t0 = ev.logMonoTime
            t = (ev.logMonoTime - t0) / 1e9
            if ev.which() == "can":
                for m in ev.can:
                    if m.address == 0x3F2 and m.src == 128: echo.append(t)
                    elif m.address == 0x3F2 and m.src == 2: cam.append(t)
                    elif m.address == 0x495 and m.src == 0:
                        e = int(pet.extract(bytes(m.dat), sigs[0x495]["EPS_STATE_LKA"]))
                        if e == 4 and prev != 4: onsets.append(t)
                        prev = e
    ie = [b - a for a, b in zip(echo, echo[1:])]
    ic = [b - a for a, b in zip(cam, cam[1:])]
    print(f"== {rdir.name} defect={len(onsets)}")
    print(f"   echo nostri: {hist(ie)}")
    print(f"   camera     : {hist(ic)}")
    mins = []
    for d in onsets:
        w = [b - a for a, b in zip(echo, echo[1:]) if d - 0.3 <= b <= d]
        mins.append(round(min(w) * 1000) if w else None)
    print(f"   intervallo minimo nei 300ms prima di ogni Defect (ms): {mins}")
