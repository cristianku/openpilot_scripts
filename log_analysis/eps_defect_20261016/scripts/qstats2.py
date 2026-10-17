# /// script
# requires-python = ">=3.11"
# dependencies = ["pycapnp", "zstandard"]
# ///
"""Dai qlog: per route tempo con latActive, numero di Defect EPS (steerFaultTemporary), e contesto di ogni Defect."""
import sys
import re
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, "/Users/cristianku/GitHub/COMMA.AI/CRISTIANKU/openpilot_scripts/log_analysis")
import psa_eps_timeline as pet

logs = Path(sys.argv[1])
schema = pet.load_schema()

segs = defaultdict(list)
for d in logs.iterdir():
    m = re.match(r"^(.+)--(\d+)$", d.name)
    if m and (d / "qlog.zst").is_file():
        segs[m.group(1)].append((int(m.group(2)), d / "qlog.zst"))

for route in sorted(segs):
    t0 = None
    lat_t = 0.0
    last_cc_t = None
    lat = False
    lng = False
    long_t = 0.0
    cruise = False
    fault = False
    n = 0
    v = 0.0
    ang = 0.0
    lat_pos = 0.0
    lon_pos = 0.0
    curv = 0.0
    speeds = []
    for seg, path in sorted(segs[route]):
        for ev in pet.read_events(schema, path):
            if t0 is None:
                t0 = ev.logMonoTime
            t = (ev.logMonoTime - t0) / 1e9
            w = ev.which()
            if w == "carControl":
                if last_cc_t is not None and lat:
                    lat_t += t - last_cc_t
                if last_cc_t is not None and lng:
                    long_t += t - last_cc_t
                last_cc_t = t
                lat = ev.carControl.latActive
                curv = ev.carControl.actuators.curvature
                lng = ev.carControl.longActive
                if lng and last_cc_t is not None:
                    pass
            elif w == "gpsLocationExternal" or w == "gpsLocation":
                lat_pos = ev.gpsLocationExternal.latitude if w == "gpsLocationExternal" else ev.gpsLocation.latitude
                lon_pos = ev.gpsLocationExternal.longitude if w == "gpsLocationExternal" else ev.gpsLocation.longitude
            elif w == "carState":
                cs = ev.carState
                v = cs.vEgo
                ang = cs.steeringAngleDeg
                if cs.steerFaultTemporary and not fault:
                    n += 1
                    speeds.append(v * 3.6)
                    print(f"  {route} seg{seg:3d} t={t:7.1f} v={v*3.6:5.1f}km/h ang={ang:6.1f} "
                          f"lat={int(lat)} long={int(lng)} cruise={int(cs.cruiseState.enabled)} gps={lat_pos:.5f},{lon_pos:.5f}")
                fault = cs.steerFaultTemporary
    rate = n / (lat_t / 3600) if lat_t > 0 else 0
    print(f"ROUTE {route}: latActive={lat_t/60:6.1f} min  longActive={long_t/60:6.1f} min  defect={n:3d}  ({rate:5.1f}/h)\n")
