# /// script
# requires-python = ">=3.11"
# dependencies = ["pycapnp", "zstandard"]
# ///
"""Correlazione temporale: bus-off/errori bus2 del panda vs Defect EPS (steerFaultTemporary), dai qlog."""
import sys
import re
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, "/Users/cristianku/GitHub/COMMA.AI/CRISTIANKU/openpilot_scripts/log_analysis")
import psa_eps_timeline as pet

logs = Path(sys.argv[1])
only = sys.argv[2:]
schema = pet.load_schema()

segs = defaultdict(list)
for d in logs.iterdir():
    m = re.match(r"^(.+)--(\d+)$", d.name)
    if m and (d / "qlog.zst").is_file():
        segs[m.group(1)].append((int(m.group(2)), d / "qlog.zst"))

for route in sorted(segs):
    if only and route not in only:
        continue
    t0 = None
    busoff_t = []
    err_t = []
    defect_t = []
    prev_bo = None
    prev_err = None
    fault = False
    for seg, path in sorted(segs[route]):
        for ev in pet.read_events(schema, path):
            if t0 is None:
                t0 = ev.logMonoTime
            t = (ev.logMonoTime - t0) / 1e9
            w = ev.which()
            if w == "pandaStates":
                c = ev.pandaStates[0].canState2
                if prev_bo is not None and c.busOffCnt > prev_bo:
                    busoff_t.append(t)
                if prev_err is not None and c.totalErrorCnt > prev_err:
                    err_t.append((t, c.totalErrorCnt - prev_err))
                prev_bo = c.busOffCnt
                prev_err = c.totalErrorCnt
            elif w == "carState":
                f = ev.carState.steerFaultTemporary
                if f and not fault:
                    defect_t.append(t)
                fault = f

    def nearest(t, lst):
        if not lst:
            return None
        return min(lst, key=lambda x: abs(x - t)) - t

    err_times = [t for t, n in err_t]
    print(f"ROUTE {route}: defect={len(defect_t)} busoff_bus2={len(busoff_t)} campioni_con_errori_bus2={len(err_t)}")
    matched = 0
    for td in defect_t:
        nb = nearest(td, busoff_t)
        ne = nearest(td, err_times)
        if ne is not None and abs(ne) < 1.0:
            matched += 1
        nb_s = f"{nb:+7.2f}s" if nb is not None else "   -   "
        ne_s = f"{ne:+7.2f}s" if ne is not None else "   -   "
        print(f"   defect t={td:8.1f}  busoff piu' vicino {nb_s}   errore bus2 piu' vicino {ne_s}")
    print(f"   defect con errore bus2 entro 1s: {matched}/{len(defect_t)}")
    # e al contrario: quanti episodi di errori bus2 NON hanno defect vicino
    episodes = []
    for t in err_times:
        if not episodes or t - episodes[-1] > 2.0:
            episodes.append(t)
    no_def = [t for t in episodes if all(abs(t - d) > 2.0 for d in defect_t)]
    print(f"   episodi errori bus2: {len(episodes)}, senza defect entro 2s: {len(no_def)}\n")
