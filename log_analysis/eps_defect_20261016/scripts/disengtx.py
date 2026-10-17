# /// script
# requires-python = ">=3.11"
# dependencies = ["pycapnp", "zstandard"]
# ///
"""Per route: da disingaggiati (carControl.latActive=0) quanti LANE_KEEP_ASSIST mandiamo al secondo, e Defect per stato."""
import sys
from pathlib import Path
from collections import Counter
sys.path.insert(0, "/Users/cristianku/GitHub/COMMA.AI/CRISTIANKU/openpilot_scripts/log_analysis")
import psa_eps_timeline as pet
sigs = pet.dbc_signals(pet.DBC, {0x495})
schema = pet.load_schema()
print(f"{'route':22s} {'commit':9s} {'min_dis':>7s} {'LKA/s dis':>9s} {'min_lat':>7s} {'LKA/s lat':>9s} {'def_dis':>7s} {'def_lat':>7s}")
for rdir in sys.argv[1:]:
    rdir = Path(rdir)
    segs = sorted((p for p in rdir.iterdir() if (p / "rlog.zst").exists()), key=lambda p: int(p.name.rsplit("--", 1)[1]))
    lat = None; last_t = None; tm = Counter(); n = Counter(); d = Counter(); prev = 0; commit = ""; dash = False
    for seg in segs:
        try:
            for ev in pet.read_events(schema, seg / "rlog.zst"):
                t = ev.logMonoTime / 1e9; w = ev.which()
                if w == "initData" and not commit: commit = ev.initData.gitCommit[:8]
                elif w == "carParams": dash = dash or ev.carParams.dashcamOnly
                elif w == "carControl":
                    if last_t is not None and lat is not None: tm[lat] += t - last_t
                    last_t = t; lat = bool(ev.carControl.latActive)
                elif w == "can" and lat is not None:
                    for m in ev.can:
                        if m.address == 0x3F2 and m.src == 128: n[lat] += 1
                        elif m.address == 0x495 and m.src == 0:
                            e = int(pet.extract(bytes(m.dat), sigs[0x495]["EPS_STATE_LKA"]))
                            if e == 4 and prev != 4: d[lat] += 1
                            prev = e
        except Exception:
            pass
    if dash: continue
    rd = n[False] / tm[False] if tm[False] else 0; rl = n[True] / tm[True] if tm[True] else 0
    print(f"{rdir.name:22s} {commit:9s} {tm[False]/60:7.1f} {rd:9.1f} {tm[True]/60:7.1f} {rl:9.1f} {d[False]:7d} {d[True]:7d}")
