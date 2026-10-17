# /// script
# requires-python = ">=3.11"
# dependencies = ["pycapnp", "zstandard"]
# ///
"""Ritardo tra pubblicazione di card (sendcan) e uscita sul bus (echo src128) per LANE_KEEP_ASSIST."""
import sys
from pathlib import Path
from collections import Counter
sys.path.insert(0, "/Users/cristianku/GitHub/COMMA.AI/CRISTIANKU/openpilot_scripts/log_analysis")
import psa_eps_timeline as pet
schema = pet.load_schema()
rdir = Path(sys.argv[1])
segs = sorted((p for p in rdir.iterdir() if (p / "rlog.zst").exists()), key=lambda p: int(p.name.rsplit("--", 1)[1]))
tx = []; echo = []
for seg in segs:
    for ev in pet.read_events(schema, seg / "rlog.zst"):
        t = ev.logMonoTime / 1e9
        w = ev.which()
        if w == "sendcan":
            for m in ev.sendcan:
                if m.address == 0x3F2: tx.append((t, bytes(m.dat)))
        elif w == "can":
            for m in ev.can:
                if m.address == 0x3F2 and m.src == 128: echo.append((t, bytes(m.dat)))
# abbina ogni echo al sendcan precedente piu' vicino con stessi dati
lat = []
j = 0
for te, de in echo:
    while j + 1 < len(tx) and tx[j + 1][0] <= te:
        j += 1
    k = j
    while k >= 0 and tx[k][1] != de and te - tx[k][0] < 0.2:
        k -= 1
    if k >= 0 and tx[k][1] == de:
        lat.append(te - tx[k][0])
h = dict(sorted(Counter(int(round(x * 1000)) for x in lat).items()))
print(f"abbinati {len(lat)}/{len(echo)}  ritardo card->bus (ms): {h}")
