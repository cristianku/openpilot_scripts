# /// script
# requires-python = ">=3.11"
# dependencies = ["pycapnp", "zstandard"]
# ///
import sys, capnp, zstandard
from pathlib import Path
from collections import Counter
CEREAL = Path.home()/"GitHub/COMMA.AI/SUNNYPILOT/sunnypilot/openpilot/cereal"
CAR = Path.home()/"GitHub/COMMA.AI/CRISTIANKU/opendbc/opendbc/car"
capnp.remove_import_hook()
log = capnp.load(str(CEREAL/"log.capnp"), imports=[str(CEREAL), str(CAR)])
for seg in sorted(Path(sys.argv[1]).iterdir(), key=lambda p: int(p.name.split("--")[-1])):
    raw = zstandard.ZstdDecompressor().decompress((seg/"rlog.zst").read_bytes(), max_output_size=4*1024**3)
    cp = None; en = Counter(); v = []; buses = Counter(); dongle=None
    for e in log.Event.read_multiple_bytes(raw, traversal_limit_in_words=2**61):
        w = e.which()
        if w == "carParams" and cp is None:
            c = e.carParams; cp = (c.carFingerprint, c.dashcamOnly, c.openpilotLongitudinalControl, c.alphaLongitudinalAvailable)
        elif w == "selfdriveState":
            en[(e.selfdriveState.enabled, e.selfdriveState.active)] += 1
        elif w == "carState":
            v.append(e.carState.vEgo)
        elif w == "initData":
            dongle = (e.initData.dongleId, e.initData.gitBranch, e.initData.gitCommit[:8])
        elif w == "can":
            for m in e.can: buses[m.src] += 1
    print(seg.name, dongle, cp, dict(en), f"vmax={max(v)*3.6:.0f}kmh" if v else "", dict(buses))
