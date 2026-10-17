# /// script
# requires-python = ">=3.11"
# dependencies = ["pycapnp", "zstandard"]
# ///
"""Per ogni (src, addr): periodo tipico vs buco massimo nella finestra prima di ogni Defect.
Segnala i messaggi che si interrompono (buco > 2.5x periodo mediano) prima del Defect."""
import sys
import statistics
from collections import defaultdict
sys.path.insert(0, "/Users/cristianku/GitHub/COMMA.AI/CRISTIANKU/openpilot_scripts/log_analysis")
import psa_eps_timeline as pet

route = sys.argv[1]
pre = float(sys.argv[2]) if len(sys.argv) > 2 else 1.0
segs = sorted((p for p in pet.LOGS_DIR.iterdir() if p.name.startswith(route + "--")),
              key=lambda p: int(p.name.rsplit("--", 1)[1]))
sigs = pet.dbc_signals(pet.DBC, {0x495})
schema = pet.load_schema()

times = defaultdict(list)
last_dat = {}
changes = defaultdict(list)  # (src,addr) -> [(t, old, new)]
onsets = []
prev = 0
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
        if w == "can":
            for m in ev.can:
                if m.src >= 128:
                    continue
                k = (m.src, m.address)
                times[k].append(t)
                if m.address == 0x495 and m.src == 0:
                    eps = int(pet.extract(bytes(m.dat), sigs[0x495]["EPS_STATE_LKA"]))
                    if eps == 4 and prev != 4:
                        onsets.append(t)
                    prev = eps

period = {}
for k, ts in times.items():
    if len(ts) > 20:
        period[k] = statistics.median(b - a for a, b in zip(ts, ts[1:]))

print(f"defect: {len(onsets)}  messaggi distinti: {len(times)}")
hits = defaultdict(int)
for t_on in onsets:
    out = []
    for k, ts in times.items():
        if k not in period or period[k] <= 0:
            continue
        win = [x for x in ts if t_on - pre <= x <= t_on]
        # include last before window to catch a gap spanning the window start
        before = [x for x in ts if x < t_on - pre]
        if before:
            win = [before[-1]] + win
        win.append(t_on)
        g = max(b - a for a, b in zip(win, win[1:])) if len(win) > 1 else 0
        if g > 2.5 * period[k] and g > 0.03:
            out.append(f"{k[0]}:{k[1]:X}({period[k]*1000:.0f}ms->{g*1000:.0f}ms)")
            hits[k] += 1
    print(f"Defect @{t_on:8.3f}: {' '.join(sorted(out)) if out else 'nessun buco'}")
print("\nmessaggi con buco ricorrente:", sorted(((f'{k[0]}:{k[1]:X}', v) for k, v in hits.items()), key=lambda x: -x[1])[:15])
