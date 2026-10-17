# /// script
# requires-python = ">=3.11"
# dependencies = ["pycapnp", "zstandard"]
# ///
"""3F2 realmente usciti su bus0 (echo src128) e scartati (src192): buchi vs Defect."""
import sys, bisect
from pathlib import Path
sys.path.insert(0, "/Users/cristianku/GitHub/COMMA.AI/CRISTIANKU/openpilot_scripts/log_analysis")
import psa_eps_timeline as pet
sigs = pet.dbc_signals(pet.DBC, {0x495})
schema = pet.load_schema()
for rdir in sys.argv[1:]:
    rdir = Path(rdir)
    segs = sorted((p for p in rdir.iterdir() if (p / "rlog.zst").exists()), key=lambda p: int(p.name.rsplit("--", 1)[1]))
    echo = []; blk = []; prev = 0; onsets = []; t0 = None
    for seg in segs:
        for ev in pet.read_events(schema, seg / "rlog.zst"):
            if t0 is None: t0 = ev.logMonoTime
            t = (ev.logMonoTime - t0) / 1e9
            if ev.which() == "can":
                for m in ev.can:
                    if m.address == 0x3F2 and m.src == 128: echo.append(t)
                    elif m.address == 0x3F2 and m.src == 192: blk.append(t)
                    elif m.address == 0x495 and m.src == 0:
                        e = int(pet.extract(bytes(m.dat), sigs[0x495]["EPS_STATE_LKA"]))
                        if e == 4 and prev != 4: onsets.append(t)
                        prev = e
    gaps = [(b - a, b) for a, b in zip(echo, echo[1:])]
    big = [(g, t) for g, t in gaps if g > 0.075]
    print(f"== {rdir.name}: defect={len(onsets)} echo={len(echo)} scartati={len(blk)} buchi_echo>75ms={len(big)}")
    near_blk = sum(1 for d in onsets if any(d - 0.5 <= b <= d for b in blk))
    near_gap = sum(1 for d in onsets if any(d - 0.5 <= t <= d + 0.05 for g, t in big))
    print(f"   defect con scarto nei 0.5s prima: {near_blk}/{len(onsets)}   defect con buco echo: {near_gap}/{len(onsets)}")
    for d in onsets[:12]:
        bb = [round(b - d, 3) for b in blk if d - 1.0 <= b <= d + 0.1]
        gg = [(round(t - d, 3), round(g * 1000)) for g, t in big if d - 1.0 <= t <= d + 0.1]
        print(f"   Defect @{d:8.2f}  scarti(rel)={bb}  buchi(rel,ms)={gg}")
    print("   primi scarti:", [round(b, 2) for b in blk[:15]])
