# /// script
# requires-python = ">=3.11"
# dependencies = ["pycapnp", "zstandard"]
# ///
"""Per ogni Defect: da quanto l'EPS era Active, buco max tra i 3F2 inviati, buco max tra i 495 ricevuti."""
import sys
sys.path.insert(0, "/Users/cristianku/GitHub/COMMA.AI/CRISTIANKU/openpilot_scripts/log_analysis")
import psa_eps_timeline as pet

route = sys.argv[1]
segs = sorted((p for p in pet.LOGS_DIR.iterdir() if p.name.startswith(route + "--")),
              key=lambda p: int(p.name.rsplit("--", 1)[1]))
sigs = pet.dbc_signals(pet.DBC, {pet.ADDR_DIRA})
schema = pet.load_schema()

t0 = None
tx = []      # tempi 3F2 inviati
rx = []      # (t, eps) 495 ricevuti
cs = []      # (t, card cycle) carState
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
        if w == "sendcan":
            for m in ev.sendcan:
                if m.address == pet.ADDR_LKA and m.src == 0:
                    tx.append(t)
        elif w == "can":
            for m in ev.can:
                if m.address == pet.ADDR_DIRA and m.src == 0:
                    eps = int(pet.extract(bytes(m.dat), sigs[pet.ADDR_DIRA]["EPS_STATE_LKA"]))
                    rx.append((t, eps))

prev = 0
active_since = None
for t, eps in rx:
    if eps == 3 and prev != 3:
        active_since = t
    if eps == 4 and prev != 4:
        win = [x for x in tx if t - 2.0 <= x <= t]
        gaps = [b - a for a, b in zip(win, win[1:])]
        maxgap = max(gaps) if gaps else -1
        act = (t - active_since) if (prev == 3 and active_since is not None) else -1
        # quanto dura il defect
        end = next((t2 for t2, e2 in rx if t2 > t and e2 != 4), None)
        dur = (end - t) if end else -1
        print(f"Defect @{t:8.3f}  prima={prev}  attivo_da={act:6.2f}s  dur_defect={dur:5.2f}s  "
              f"3F2 n={len(win)} in 2s, buco_max={maxgap*1000:5.0f}ms")
    prev = eps

gaps_all = [b - a for a, b in zip(tx, tx[1:])]
big = [g for g in gaps_all if g > 0.06]
print(f"\n3F2 totali={len(tx)}  periodo medio={sum(gaps_all)/len(gaps_all)*1000:.1f}ms  buchi>60ms={len(big)}")
