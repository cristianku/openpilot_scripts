# /// script
# requires-python = ">=3.11"
# dependencies = ["pycapnp", "zstandard"]
# ///
"""Per route: dashcamOnly, durata, Defect EPS (0x495=4), eventi 0x795 byte0!=0, 3F2 inviati, stati EPS."""
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
    dash = set(); prev = 0; n_def = 0; n795 = 0; last795 = None; tx3f2 = 0; st = Counter(); t0 = None; t = 0
    vals795 = Counter()
    for seg in segs:
        for ev in pet.read_events(schema, seg / "rlog.zst"):
            if t0 is None: t0 = ev.logMonoTime
            t = (ev.logMonoTime - t0) / 1e9
            w = ev.which()
            if w == "carParams":
                dash.add(ev.carParams.dashcamOnly)
            elif w == "sendcan":
                tx3f2 += sum(1 for m in ev.sendcan if m.address == 0x3F2)
            elif w == "can":
                for m in ev.can:
                    if m.src != 0: continue
                    if m.address == 0x495:
                        e = int(pet.extract(bytes(m.dat), sigs[0x495]["EPS_STATE_LKA"]))
                        st[e] += 1
                        if e == 4 and prev != 4: n_def += 1
                        prev = e
                    elif m.address == 0x795:
                        b0 = m.dat[0]
                        vals795[bytes(m.dat).hex()] += 1
                        if b0 != 0 and (last795 is None or last795 == 0): n795 += 1
                        last795 = b0
    print(f"{rdir.name}: seg={len(segs)} dur={t/60:.1f}min dashcamOnly={dash} 3F2_inviati={tx3f2} "
          f"DEFECT={n_def} 795_fault={n795} stati_EPS={dict(sorted(st.items()))} 795={dict(vals795)}")
