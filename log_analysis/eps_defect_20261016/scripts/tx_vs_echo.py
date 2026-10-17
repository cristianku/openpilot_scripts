# /// script
# requires-python = ">=3.11"
# dependencies = ["pycapnp", "zstandard"]
# ///
"""Intervalli 3F2: quando card lo pubblica (sendcan) vs quando torna l'echo dal bus; e intervalli dei pacchetti can di pandad."""
import sys
from pathlib import Path
from collections import Counter
sys.path.insert(0, "/Users/cristianku/GitHub/COMMA.AI/CRISTIANKU/openpilot_scripts/log_analysis")
import psa_eps_timeline as pet
schema = pet.load_schema()
def h(iv):
    return dict(sorted(Counter(int(round(x * 1000 / 5)) * 5 for x in iv).items()))
for rdir in sys.argv[1:]:
    rdir = Path(rdir)
    segs = sorted((p for p in rdir.iterdir() if (p / "rlog.zst").exists()), key=lambda p: int(p.name.rsplit("--", 1)[1]))
    tx = []; echo = []; cam = []; canpk = []
    for seg in segs[:3]:
        for ev in pet.read_events(schema, seg / "rlog.zst"):
            t = ev.logMonoTime / 1e9
            w = ev.which()
            if w == "sendcan":
                if any(m.address == 0x3F2 for m in ev.sendcan): tx.append(t)
            elif w == "can":
                canpk.append(t)
                for m in ev.can:
                    if m.address == 0x3F2 and m.src == 128: echo.append(t)
                    if m.address == 0x3F2 and m.src == 2: cam.append(t)
    d = lambda l: [b - a for a, b in zip(l, l[1:])]
    print(f"== {rdir.name}")
    print("   sendcan 3F2 (card)  ms:", h(d(tx)))
    print("   echo 3F2 sul bus    ms:", h(d(echo)))
    print("   camera 3F2          ms:", h(d(cam)))
    print("   pacchetti can pandad ms:", h(d(canpk)))
