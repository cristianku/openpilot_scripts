# /// script
# requires-python = ">=3.11"
# dependencies = ["pycapnp", "zstandard"]
# ///
"""Per ogni (src, addr, byte): in quanti Defect quel byte cambia nella finestra [t-W, t]
contro la probabilita' di cambio in una finestra W qualsiasi. Ordina per 'arricchimento'."""
import sys
from collections import defaultdict
import bisect
sys.path.insert(0, "/Users/cristianku/GitHub/COMMA.AI/CRISTIANKU/openpilot_scripts/log_analysis")
import psa_eps_timeline as pet

route = sys.argv[1]
W = float(sys.argv[2]) if len(sys.argv) > 2 else 0.15
segs = sorted((p for p in pet.LOGS_DIR.iterdir() if p.name.startswith(route + "--")),
              key=lambda p: int(p.name.rsplit("--", 1)[1]))
sigs = pet.dbc_signals(pet.DBC, {0x495})
schema = pet.load_schema()

last = {}
chg = defaultdict(list)   # (src,addr,byte) -> tempi di cambio
onsets = []
prev = 0
t0 = None
t_end = 0
for seg in segs:
    f = seg / "rlog.zst"
    if not f.exists():
        continue
    for ev in pet.read_events(schema, f):
        t = ev.logMonoTime / 1e9
        if t0 is None:
            t0 = t
        t = t - t0
        t_end = t
        w = ev.which()
        if w == "can":
            for m in ev.can:
                if m.src >= 128:
                    continue
                dat = bytes(m.dat)
                k = (m.src, m.address)
                old = last.get(k)
                if old is not None:
                    for i in range(min(len(old), len(dat))):
                        if old[i] != dat[i]:
                            chg[(m.src, m.address, i)].append(t)
                last[k] = dat
                if m.address == 0x495 and m.src == 0:
                    eps = int(pet.extract(dat, sigs[0x495]["EPS_STATE_LKA"]))
                    if eps == 4 and prev != 4:
                        onsets.append(t)
                    prev = eps

total = t_end
res = []
for k, ts in chg.items():
    if k[1] == 0x495 and k[0] == 0:
        pass
    n_hit = 0
    for t_on in onsets:
        i = bisect.bisect_left(ts, t_on - W)
        # escludo l'istante stesso del defect (il 495 che lo annuncia)
        if i < len(ts) and ts[i] < t_on - 0.001:
            n_hit += 1
    # probabilita' di base: frazione del tempo coperta da finestre che contengono un cambio
    # stima semplice: 1 - exp(-rate*W) con rate = cambi/s
    import math
    rate = len(ts) / total
    p0 = 1 - math.exp(-rate * W)
    res.append((n_hit, p0, k, len(ts)))

res.sort(key=lambda r: (-(r[0] / len(onsets) - r[1]), ))
print(f"defect={len(onsets)}  finestra={W}s  durata={total:.0f}s")
for n_hit, p0, k, n in res[:25]:
    print(f"{k[0]}:{k[1]:03X} byte{k[2]}  hit={n_hit}/{len(onsets)}  base={p0:.2f}  cambi_tot={n}")
