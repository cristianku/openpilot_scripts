# /// script
# requires-python = ">=3.11"
# dependencies = ["pycapnp", "zstandard"]
# ///
"""Per segmento: % intervalli LANE_KEEP_ASSIST a 50ms sul bus, Defect, intervalli piu' comuni."""
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
    print(f"== {rdir.name}")
    prev = 0
    for seg in segs:
        echo = []; nd = 0; cards = []
        try:
            for ev in pet.read_events(schema, seg / "rlog.zst"):
                t = ev.logMonoTime / 1e9
                w = ev.which()
                if w == "sendcan":
                    if any(m.address == 0x3F2 for m in ev.sendcan): cards.append(t)
                elif w == "can":
                    for m in ev.can:
                        if m.address == 0x3F2 and m.src == 128: echo.append(t)
                        elif m.address == 0x495 and m.src == 0:
                            e = int(pet.extract(bytes(m.dat), sigs[0x495]["EPS_STATE_LKA"]))
                            if e == 4 and prev != 4: nd += 1
                            prev = e
        except Exception as ex:
            print(f"   seg {seg.name.rsplit('--',1)[1]}: ERR"); continue
        iv = Counter(round((b - a) * 100) * 10 for a, b in zip(echo, echo[1:]))
        n = sum(iv.values()) or 1
        ic = Counter(round((b - a) * 1000 / 5) * 5 for a, b in zip(cards, cards[1:]))
        print(f"   seg {seg.name.rsplit('--',1)[1]:>3s}: defect={nd:2d}  bus@50ms={100*iv[50]/n:4.0f}%  bus={dict(iv.most_common(4))}  card={dict(ic.most_common(3))}")
