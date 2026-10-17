# /// script
# requires-python = ">=3.11"
# dependencies = ["pycapnp", "zstandard"]
# ///
"""Per segmento: minuti disingaggiato/ingaggiato, Defect in ciascuno stato, distribuzione intervalli LKA sul bus per stato."""
import sys
from pathlib import Path
from collections import Counter
sys.path.insert(0, "/Users/cristianku/GitHub/COMMA.AI/CRISTIANKU/openpilot_scripts/log_analysis")
import psa_eps_timeline as pet
sigs = pet.dbc_signals(pet.DBC, {0x495})
schema = pet.load_schema()
# aggregato per (classe di regolarita', stato)
agg_min = Counter(); agg_def = Counter()
for rdir in sys.argv[1:]:
    rdir = Path(rdir)
    segs = sorted((p for p in rdir.iterdir() if (p / "rlog.zst").exists()), key=lambda p: int(p.name.rsplit("--", 1)[1]))
    prev = 0
    for seg in segs:
        lat = None; last_t = None; tm = Counter(); d = Counter(); iv = Counter(); last_echo = None
        try:
            for ev in pet.read_events(schema, seg / "rlog.zst"):
                t = ev.logMonoTime / 1e9; w = ev.which()
                if w == "carControl":
                    if last_t is not None and lat is not None: tm[lat] += t - last_t
                    last_t = t; lat = bool(ev.carControl.latActive)
                elif w == "can":
                    for m in ev.can:
                        if m.address == 0x3F2 and m.src == 128:
                            if last_echo is not None: iv[round((t - last_echo) * 100) * 10] += 1
                            last_echo = t
                        elif m.address == 0x495 and m.src == 0:
                            e = int(pet.extract(bytes(m.dat), sigs[0x495]["EPS_STATE_LKA"]))
                            if e == 4 and prev != 4 and lat is not None: d[lat] += 1
                            prev = e
        except Exception:
            continue
        n = sum(iv.values())
        if n < 100: continue
        p50 = iv[50] / n; p3070 = (iv[30] + iv[70]) / n
        if p3070 > 0.03: cls = "C: 30/70 presenti"
        elif p50 > 0.8: cls = "A: regolare (>80% a 50ms)"
        else: cls = "B: 40/60 alternati"
        for st in (False, True):
            agg_min[(cls, st)] += tm[st] / 60; agg_def[(cls, st)] += d[st]
print(f"{'regolarita LKA sul bus':28s} {'stato':14s} {'minuti':>7s} {'Defect':>7s} {'/ora':>6s}")
for cls in sorted(set(k[0] for k in agg_min)):
    for st in (False, True):
        m = agg_min[(cls, st)]; dd = agg_def[(cls, st)]
        print(f"{cls:28s} {'ingaggiato' if st else 'disingaggiato':14s} {m:7.1f} {dd:7d} {dd/(m/60) if m > 0.5 else float('nan'):6.0f}")
