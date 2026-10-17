# /// script
# requires-python = ">=3.11"
# dependencies = ["pycapnp", "zstandard"]
# ///
"""Tensione (peripheralState.voltage) intorno ai Defect EPS, dagli rlog disponibili."""
import sys
sys.path.insert(0, "/Users/cristianku/GitHub/COMMA.AI/CRISTIANKU/openpilot_scripts/log_analysis")
import psa_eps_timeline as pet

route = sys.argv[1]
segs = sorted((p for p in pet.LOGS_DIR.iterdir() if p.name.startswith(route + "--")),
              key=lambda p: int(p.name.rsplit("--", 1)[1]))
sigs = pet.dbc_signals(pet.DBC, {0x495})
schema = pet.load_schema()

volts = []
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
        if w == "peripheralState":
            volts.append((t, ev.peripheralState.voltage))
        elif w == "can":
            for m in ev.can:
                if m.address == 0x495 and m.src == 0:
                    eps = int(pet.extract(bytes(m.dat), sigs[0x495]["EPS_STATE_LKA"]))
                    if eps == 4 and prev != 4:
                        onsets.append(t)
                    prev = eps

vs = [v for t, v in volts]
print(f"tensione su tutto: min={min(vs)} max={max(vs)} media={sum(vs)/len(vs):.0f} mV  campioni={len(vs)}")
for t_on in onsets:
    win = [(round(t - t_on, 2), v) for t, v in volts if t_on - 1.5 <= t <= t_on + 1.0]
    print(f"Defect @{t_on:7.2f}: {win}")
