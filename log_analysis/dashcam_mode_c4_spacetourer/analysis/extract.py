# /// script
# requires-python = ">=3.11"
# dependencies = ["pycapnp", "zstandard", "cantools", "pandas", "pyarrow"]
# ///
"""Extract C4 CAN (all buses) + carState into parquet: census + decoded long msgs."""
import sys, capnp, zstandard, cantools, pandas as pd
from pathlib import Path
from collections import Counter
CEREAL = Path.home()/"GitHub/COMMA.AI/SUNNYPILOT/sunnypilot/openpilot/cereal"
CARD = Path.home()/"GitHub/COMMA.AI/CRISTIANKU/opendbc/opendbc/car"
DBC = Path(__file__).parent/"psa.dbc"
capnp.remove_import_hook()
log = capnp.load(str(CEREAL/"log.capnp"), imports=[str(CEREAL), str(CARD)])
db = cantools.database.load_file(str(DBC), strict=False)
WANT = {0x2B6, 0x2F6, 0x4F6, 0x796, 0x452, 0x32D, 0x38D, 0x2CD, 0x228, 0x348, 0x30D, 0x3CD, 0x208, 0x329, 0x349, 0x388}
out = Path(sys.argv[2]); out.mkdir(exist_ok=True)
census = Counter(); raw_rows = []; dec = {}; cs = []
t0 = None
for seg in sorted(Path(sys.argv[1]).iterdir(), key=lambda p: int(p.name.split("--")[-1])):
    raw = zstandard.ZstdDecompressor().decompress((seg/"rlog.zst").read_bytes(), max_output_size=4*1024**3)
    for e in log.Event.read_multiple_bytes(raw, traversal_limit_in_words=2**61):
        w = e.which()
        if t0 is None: t0 = e.logMonoTime
        t = (e.logMonoTime - t0)/1e9
        if w == "can":
            for m in e.can:
                census[(m.src, m.address, len(m.dat))] += 1
                if m.src in (0, 1, 2) and m.address in WANT:
                    raw_rows.append((t, m.src, m.address, bytes(m.dat).hex()))
                    try:
                        d = db.decode_message(m.address, bytes(m.dat), decode_choices=False)
                        d["t"] = t; d["bus"] = m.src
                        dec.setdefault(m.address, []).append(d)
                    except Exception:
                        pass
        elif w == "carState":
            c = e.carState
            cs.append(dict(t=t, vEgo=c.vEgo, aEgo=c.aEgo, gas=c.gasPressed, brake=c.brakePressed,
                           cruiseEn=c.cruiseState.enabled, cruiseAvail=c.cruiseState.available,
                           vCruise=c.cruiseState.speed, standstill=c.standstill, gear=str(c.gearShifter)))
pd.DataFrame(cs).to_parquet(out/"carState.parquet")
pd.DataFrame(raw_rows, columns=["t","bus","addr","hex"]).to_parquet(out/"raw.parquet")
for a, rows in dec.items():
    pd.DataFrame(rows).to_parquet(out/f"{a:03X}.parquet")
pd.DataFrame([(b,a,l,n) for (b,a,l),n in census.items()], columns=["bus","addr","len","n"]).sort_values(["bus","addr"]).to_csv(out/"census.csv", index=False)
print("done", len(cs))
