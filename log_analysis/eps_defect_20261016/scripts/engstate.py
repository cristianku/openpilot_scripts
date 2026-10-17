# /// script
# requires-python = ">=3.11"
# dependencies = ["pycapnp", "zstandard"]
# ///
"""Regolarita' di LANE_KEEP_ASSIST sul bus e tempo di card, separati per ingaggiato / disingaggiato."""
import sys, statistics
from pathlib import Path
from collections import Counter, defaultdict
sys.path.insert(0, "/Users/cristianku/GitHub/COMMA.AI/CRISTIANKU/openpilot_scripts/log_analysis")
import psa_eps_timeline as pet
schema = pet.load_schema()
iv = defaultdict(Counter); lat = defaultdict(list)
for rdir in sys.argv[1:]:
    rdir = Path(rdir)
    segs = sorted((p for p in rdir.iterdir() if (p / "rlog.zst").exists()), key=lambda p: int(p.name.rsplit("--", 1)[1]))
    state = "?"; last_can = None; last_echo = None
    for seg in segs:
        try:
            for ev in pet.read_events(schema, seg / "rlog.zst"):
                w = ev.which(); t = ev.logMonoTime / 1e9
                if w == "carControl":
                    state = "INGAGGIATO" if ev.carControl.enabled else "disingaggiato"
                elif w == "can":
                    last_can = t
                    for m in ev.can:
                        if m.address == 0x3F2 and m.src == 128:
                            if last_echo is not None:
                                iv[state][round((t - last_echo) * 100) * 10] += 1
                            last_echo = t
                elif w == "sendcan" and last_can is not None and any(m.address == 0x3F2 for m in ev.sendcan):
                    lat[state].append((t - last_can) * 1000)
        except Exception:
            last_echo = None
for s in ("disingaggiato", "INGAGGIATO"):
    c = iv[s]; n = sum(c.values()) or 1
    pos = [x for x in lat[s] if x > 0]
    print(f"{s:14s}: LKA a 50ms={100*c[50]/n:4.0f}%  40/60={100*(c[40]+c[60])/n:4.0f}%  30/70={100*(c[30]+c[70])/n:4.1f}%   card mediana={statistics.median(pos):4.1f} ms  (n={n})")
