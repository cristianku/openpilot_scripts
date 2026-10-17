# /// script
# requires-python = ">=3.11"
# dependencies = ["pycapnp", "zstandard"]
# ///
"""Step 0: inventory of every local route (read-only).

For each route: segments present, camera files present, software version /
commit, relevant params (ExperimentalMode, DEC, SLA, SCC), carParams
longitudinal flags, GPS date of the first fix.

Usage: uv run inventory.py            -> out/inventory.json + table on stdout
"""

import datetime
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import OUT_DIR, all_segment_dirs, read_events  # noqa: E402

PARAM_KEYS = [
  "ExperimentalMode", "DynamicExperimentalControl", "LongitudinalPersonality",
  "SmartCruiseControlMap", "SmartCruiseControlVision", "SpeedLimitMode",
  "SpeedLimitOffsetType", "SpeedLimitValueOffset", "OsmLocal", "AlphaLongitudinalEnabled",
  "ModelManager_ActiveBundle",
]

CAMERA_FILES = ["fcamera.hevc", "ecamera.hevc", "qcamera.ts", "dcamera.hevc"]


def read_route_header(seg_dir):
  info = {}
  for ev in read_events(seg_dir / "rlog.zst"):
    w = ev.which()
    if w == "initData" and "version" not in info:
      i = ev.initData
      info["version"] = i.version
      info["git_commit"] = i.gitCommit
      info["git_branch"] = i.gitBranch
      info["params"] = {}
      for e in i.params.entries:
        if e.key in PARAM_KEYS:
          value = bytes(e.value).decode("utf-8", "replace")
          if e.key == "ModelManager_ActiveBundle":
            try:
              value = json.loads(value)["displayName"]
            except Exception:
              value = value[:80]
          info["params"][e.key] = value
    elif w == "carParams" and "fingerprint" not in info:
      cp = ev.carParams
      info["fingerprint"] = str(cp.carFingerprint)
      info["op_long"] = bool(cp.openpilotLongitudinalControl)
      info["passive"] = bool(cp.passive)
      info["radar_unavailable"] = bool(cp.radarUnavailable)
      info["long_actuator_delay"] = float(cp.longitudinalActuatorDelay)
      info["stop_accel"] = float(cp.stopAccel)
      info["ki_bp"] = list(cp.longitudinalTuning.kiBP)
      info["ki_v"] = list(cp.longitudinalTuning.kiV)
    elif w == "gpsLocationExternal" and "gps_date" not in info:
      g = ev.gpsLocationExternal
      if g.hasFix and g.unixTimestampMillis > 0:
        dt = datetime.datetime.fromtimestamp(g.unixTimestampMillis / 1000.0, datetime.timezone.utc)
        info["gps_date"] = dt.strftime("%Y-%m-%d %H:%M UTC")
  return info


def main():
  OUT_DIR.mkdir(exist_ok=True)
  routes = all_segment_dirs()
  table = []
  for route, segs in routes.items():
    seg_numbers = list(segs.keys())
    cams = {}
    for name in CAMERA_FILES:
      cams[name] = 0
    for seg, d in segs.items():
      for name in CAMERA_FILES:
        if (d / name).is_file():
          cams[name] += 1
    first_dir = segs[seg_numbers[0]]
    try:
      header = read_route_header(first_dir)
    except Exception as exc:  # corrupt/partial download
      header = {"error": str(exc)[:200]}
    # GPS date might only appear later; try the second segment too
    if "gps_date" not in header and len(seg_numbers) > 1:
      try:
        h2 = read_route_header(segs[seg_numbers[1]])
        if "gps_date" in h2:
          header["gps_date"] = h2["gps_date"]
      except Exception:
        pass
    row = {
      "route": route,
      "n_segments": len(seg_numbers),
      "seg_min": seg_numbers[0],
      "seg_max": seg_numbers[-1],
      "folder": str(first_dir.parent),
      "cameras": cams,
    }
    row.update(header)
    table.append(row)
    p = row.get("params", {})
    print(f"{route}  segs={len(seg_numbers):3d} [{seg_numbers[0]}..{seg_numbers[-1]}]  "
          f"ver={row.get('version')} {str(row.get('git_commit'))[:9]}  date={row.get('gps_date')}  "
          f"EM={p.get('ExperimentalMode')} DEC={p.get('DynamicExperimentalControl')} "
          f"SLA={p.get('SpeedLimitMode')} SCCm={p.get('SmartCruiseControlMap')} SCCv={p.get('SmartCruiseControlVision')} "
          f"pers={p.get('LongitudinalPersonality')} oplong={row.get('op_long')} cams={sum(cams.values())}")
  (OUT_DIR / "inventory.json").write_text(json.dumps(table, indent=1))


if __name__ == "__main__":
  main()
