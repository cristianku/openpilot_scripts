# /// script
# requires-python = ">=3.11"
# dependencies = ["pycapnp", "zstandard"]
# ///
import sys, capnp, zstandard
from pathlib import Path
CEREAL = Path.home()/"GitHub/COMMA.AI/SUNNYPILOT/sunnypilot/openpilot/cereal"
CAR = Path.home()/"GitHub/COMMA.AI/CRISTIANKU/opendbc/opendbc/car"
capnp.remove_import_hook()
log = capnp.load(str(CEREAL/"log.capnp"), imports=[str(CEREAL), str(CAR)])
t0=None
for seg in sorted([p for p in Path(sys.argv[1]).iterdir() if p.is_dir()], key=lambda p: int(p.name.split("--")[-1])):
    raw = zstandard.ZstdDecompressor().decompress((seg/"rlog.zst").read_bytes(), max_output_size=4*1024**3)
    lo=hi=None; lo_all=None
    for e in log.Event.read_multiple_bytes(raw, traversal_limit_in_words=2**61):
        if lo_all is None: lo_all = e.logMonoTime
        if t0 is None: t0 = e.logMonoTime
        if e.which()=="carState":
            if lo is None: lo=e.logMonoTime
            hi=e.logMonoTime
    print(seg.name, "first evt %.2f carState %.2f..%.2f"%((lo_all-t0)/1e9,(lo-t0)/1e9-601.33,(hi-t0)/1e9-601.33))
