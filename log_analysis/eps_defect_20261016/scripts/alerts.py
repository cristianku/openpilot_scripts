# /// script
# requires-python = ">=3.11"
# dependencies = ["pycapnp", "zstandard"]
# ///
"""Estrae dai qlog gli episodi di alert (selfdriveState) e gli onroadEvents."""
import sys
import re
from pathlib import Path
from collections import Counter, defaultdict

sys.path.insert(0, "/Users/cristianku/GitHub/COMMA.AI/CRISTIANKU/openpilot_scripts/log_analysis")
import psa_eps_timeline as pet

logs = Path(sys.argv[1])
schema = pet.load_schema()

segs = defaultdict(list)
for d in logs.iterdir():
    m = re.match(r"^(.+)--(\d+)$", d.name)
    if m and (d / "qlog.zst").is_file():
        segs[m.group(1)].append((int(m.group(2)), d / "qlog.zst"))

alert_count = Counter()
event_count = Counter()
episodes = []  # (route, seg, t, alertType, text1, text2, durata)

for route in sorted(segs):
    t0 = None
    cur = None
    cur_start = None
    prev_events = set()
    for seg, path in sorted(segs[route]):
        try:
            evs = list(pet.read_events(schema, path))
        except Exception as e:
            print(f"ERR {route}--{seg}: {e}")
            continue
        for ev in evs:
            if t0 is None:
                t0 = ev.logMonoTime
            t = (ev.logMonoTime - t0) / 1e9
            w = ev.which()
            if w == "selfdriveState":
                s = ev.selfdriveState
                key = (str(s.alertType), s.alertText1, s.alertText2)
                if s.alertType == "":
                    key = None
                if key != cur:
                    if cur is not None:
                        episodes.append((route, cur_seg, cur_start, cur[0], cur[1], cur[2], t - cur_start))
                        alert_count[cur[0]] += 1
                    cur = key
                    cur_start = t
                    cur_seg = seg
            elif w == "onroadEvents":
                names = set(str(e.name) for e in ev.onroadEvents)
                for n in names - prev_events:
                    event_count[n] += 1
                prev_events = names

print("=== alertType (episodi) ===")
for k, v in alert_count.most_common():
    print(f"{v:6d}  {k}")
print("\n=== onroadEvents (fronti di salita) ===")
for k, v in event_count.most_common():
    print(f"{v:6d}  {k}")
print("\n=== episodi ===")
for r, sg, t, a, t1, t2, dur in episodes:
    print(f"{r} seg{sg:3d} t={t:8.1f} dur={dur:5.2f}s  {a} | {t1} | {t2}")
