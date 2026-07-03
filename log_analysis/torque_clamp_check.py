# /// script
# requires-python = ">=3.11"
# dependencies = ["pandas", "numpy", "pycapnp", "zstandard"]
# ///
"""Is torqued pinned against its learning clamp? Compare the learned torque
params (device cache and/or a route's logs) with the offline values in
opendbc torque_data/override.toml, and recommend new offline values.

Background: torqued can only learn within a window around the offline values
(~ +/-30% latAccelFactor, +/-50% friction - see FACTOR_CLAMP/FRICTION_CLAMP
below). If the vehicle's true gain is outside that window, the filtered value
saturates at the clamp edge and the controller permanently runs with the
wrong gain (symptom on the PSA 3008: ~1.5 Hz lane-center zig-zag).

Usage:
  uv run torque_clamp_check.py [route] [--last] [--device] [--json]

  route      route id (00000029--0f498d7077) or a segment name
             (00000029--0f498d7077--3: the segment suffix is stripped, the
             whole route is analyzed). Reads its liveTorqueParameters.csv
             (convert first with the comma-logs-to-csv skill).
  --last     newest converted route instead of naming one
  --device   fetch + decode the params cached on the comma (needs ssh)
  (default with no args: --last plus --device best-effort)

Env: COMMA_HOST (default comma), COMMA_LOGS_DIR, OPENDBC_DIR, CEREAL_DIR,
     CAR (default PSA_PEUGEOT_3008).
"""

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path

import numpy as np

# learning window relative to the offline values (openpilot torqued)
FACTOR_CLAMP = 0.30
FRICTION_CLAMP = 0.50
# "pinned": filtered sits within this fraction of the clamp edge
PIN_TOL = 0.02

CAR = os.environ.get("CAR", "PSA_PEUGEOT_3008")
COMMA_HOST = os.environ.get("COMMA_HOST", "comma")
OPENDBC_DIR = Path(os.environ.get(
    "OPENDBC_DIR", "/Users/cristianku/GitHub/COMMA.AI/CRISTIANKU/opendbc"))
LOGS_DIR = Path(os.environ.get(
    "COMMA_LOGS_DIR",
    "/Users/cristianku/GitHub/COMMA.AI/CRISTIANKU/openpilot_scripts/comma_logs"))
CEREAL_DIR = Path(os.environ.get(
    "CEREAL_DIR", "/Users/cristianku/GitHub/COMMA.AI/SUNNYPILOT/openpilot_sunny/cereal"))


def offline_values() -> dict:
    toml = OPENDBC_DIR / "opendbc/car/torque_data/override.toml"
    with open(toml, "rb") as f:
        data = tomllib.load(f)
    if CAR not in data:
        sys.exit(f"{CAR} not found in {toml}")
    factor, max_lat, friction = data[CAR]
    return {"file": str(toml), "lat_accel_factor": factor,
            "max_lat_accel": max_lat, "friction": friction,
            "factor_window": [round(factor * (1 - FACTOR_CLAMP), 3),
                              round(factor * (1 + FACTOR_CLAMP), 3)],
            "friction_window": [round(friction * (1 - FRICTION_CLAMP), 3),
                                round(friction * (1 + FRICTION_CLAMP), 3)]}


def from_route(route: str | None) -> dict | None:
    import pandas as pd
    base = LOGS_DIR / "csv"
    if route is None:  # --last
        routes = sorted(d.name for d in base.iterdir() if d.is_dir()) if base.is_dir() else []
        routes = [r for r in routes if (base / r / "liveTorqueParameters.csv").is_file()]
        if not routes:
            return None
        route = routes[-1]
    f = base / route / "liveTorqueParameters.csv"
    if not f.is_file():
        sys.exit(f"{f} missing - convert the route first (comma-logs-to-csv skill, "
                 f"include liveTorqueParameters in --types)")
    lt = pd.read_csv(f)
    # raw estimates are only meaningful once the fit is valid; before that the
    # column holds init/garbage values (e.g. constant 10.55)
    valid = lt[lt.liveValid.astype(bool)]
    half = valid.iloc[len(valid) // 2:] if len(valid) else valid
    return {
        "route": route,
        "filtered_start_end": [round(float(lt.latAccelFactorFiltered.iloc[0]), 3),
                               round(float(lt.latAccelFactorFiltered.iloc[-1]), 3)],
        "raw_factor_median": round(float(half.latAccelFactorRaw.median()), 3) if len(half) else None,
        "raw_factor_p10_p90": [round(float(half.latAccelFactorRaw.quantile(0.1)), 3),
                               round(float(half.latAccelFactorRaw.quantile(0.9)), 3)] if len(half) else None,
        "friction_filtered_end": round(float(lt.frictionCoefficientFiltered.iloc[-1]), 4),
        "friction_raw_median": round(float(half.frictionCoefficientRaw.median()), 4) if len(half) else None,
        "live_valid": bool(lt.liveValid.iloc[-1]),
        "bucket_points": int(lt.totalBucketPoints.iloc[-1]),
        "cal_perc": int(lt.calPerc.iloc[-1]),
    }


def deployed_offline() -> list | None:
    """The override.toml triple actually deployed on the device - THIS is what
    the clamp uses, not the local checkout."""
    r = subprocess.run(
        ["ssh", "-o", "ConnectTimeout=8", COMMA_HOST,
         f'grep -h \'"{CAR}"\' /data/openpilot/opendbc_repo/opendbc/car/torque_data/override.toml '
         f'/data/openpilot/opendbc/car/torque_data/override.toml 2>/dev/null | grep -v "^#" | head -1'],
        capture_output=True, text=True)
    line = r.stdout.strip()
    if r.returncode != 0 or "=" not in line:
        return None
    try:
        return json.loads(line.split("=", 1)[1].strip())
    except json.JSONDecodeError:
        return None


def from_device() -> dict | None:
    """Fetch + decode the capnp Event cached in /data/params/d/LiveTorqueParameters."""
    with tempfile.TemporaryDirectory() as td:
        dst = Path(td) / "LiveTorqueParameters"
        r = subprocess.run(
            ["scp", "-o", "ConnectTimeout=8",
             f"{COMMA_HOST}:/data/params/d/LiveTorqueParameters", str(dst)],
            capture_output=True, text=True)
        if r.returncode != 0 or not dst.is_file():
            return None
        import capnp
        capnp.remove_import_hook()
        schema = capnp.load(str(CEREAL_DIR / "log.capnp"),
                            imports=[str(CEREAL_DIR), str(CEREAL_DIR / "include")])
        with schema.Event.from_bytes(dst.read_bytes(),
                                     traversal_limit_in_words=2**61) as ev:
            p = ev.liveTorqueParameters
            return {"lat_accel_factor_filtered": round(p.latAccelFactorFiltered, 3),
                    "friction_filtered": round(p.frictionCoefficientFiltered, 4),
                    "lat_accel_offset_filtered": round(p.latAccelOffsetFiltered, 4),
                    "live_valid": bool(p.liveValid),
                    "bucket_points": int(p.totalBucketPoints),
                    "use_params": bool(p.useParams)}


def verdict(off: dict, deployed: list | None, route: dict | None, dev: dict | None) -> dict:
    """The estimator (filtered) learns freely; torqued clips the value it
    HANDS TO THE CONTROLLER to +/-30% of the *deployed* offline factor
    (torqued.py FACTOR_SANITY). So the interesting number is
    used = clip(filtered, deployed window)."""
    v = {"recommendation": None}
    # which offline governs the clamp: the one on the device, if known
    gov = deployed[0] if deployed else off["lat_accel_factor"]
    lo, hi = round(gov * (1 - FACTOR_CLAMP), 3), round(gov * (1 + FACTOR_CLAMP), 3)
    v["governing_factor_window"] = [lo, hi]

    if deployed and abs(deployed[0] - off["lat_accel_factor"]) > 1e-6:
        v["deploy_mismatch"] = (
            f"local override.toml has factor {off['lat_accel_factor']} but the DEVICE runs "
            f"{deployed[0]} - the local change is not deployed; the clamp on the car is "
            f"still [{lo}, {hi}].")

    filtered = (dev or {}).get("lat_accel_factor_filtered") \
        or (route or {}).get("filtered_start_end", [None, None])[1]
    if filtered is None:
        v["note"] = "no learned data available (no device, no converted route)"
        return v

    used = min(max(filtered, lo), hi)
    v["controller_uses"] = round(used, 3)
    v["clamped"] = used != filtered
    best = (route or {}).get("raw_factor_median") or filtered
    gain_err = round((best / used - 1) * 100)
    if v["clamped"] or abs(gain_err) > 10:
        v["recommendation"] = (
            f"controller uses {round(used, 3)} (filtered {filtered} clipped to [{lo}, {hi}]) "
            f"but the best estimate of the true factor is ~{best} -> commanded torque is "
            f"~{abs(gain_err)}% too {'high' if gain_err > 0 else 'low'} (oscillation risk). "
            f"Deploy an override.toml with LAT_ACCEL_FACTOR ~= {best}, then run "
            f"reset-comma-learned-params.")
    else:
        v["recommendation"] = (
            f"controller uses {round(used, 3)}, best estimate ~{best} (within {abs(gain_err)}%) "
            f"- offline values OK; let torqued keep converging.")
    return v


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("route", nargs="?", help="route id or segment name")
    ap.add_argument("--route", dest="route_opt", help=argparse.SUPPRESS)  # back-compat
    ap.add_argument("--last", action="store_true")
    ap.add_argument("--device", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    route_arg = args.route or args.route_opt
    if route_arg:
        # accept a segment name too: 00000029--0f498d7077--3 -> route
        # (segment suffix is 1-4 digits; the route hash is 10 chars, untouched)
        route_arg = re.sub(r"--\d{1,4}$", "", route_arg)
    args.route = route_arg
    use_route = args.route or args.last or not args.device
    use_device = args.device or not (args.route or args.last)

    off = offline_values()
    route = from_route(args.route) if use_route else None
    dev = from_device() if use_device else None
    deployed = deployed_offline() if use_device else None
    out = {"car": CAR, "offline_local": off, "offline_deployed": deployed,
           "route_logs": route,
           "device_cache": dev if dev else "unreachable" if use_device else None,
           "verdict": verdict(off, deployed, route, dev)}

    if args.json:
        print(json.dumps(out, indent=2))
        return
    print(f"CAR {CAR}   local toml factor={off['lat_accel_factor']} friction={off['friction']}"
          + (f"   DEPLOYED {deployed}" if deployed else ""))
    if dev:
        print(f"device: filtered={dev['lat_accel_factor_filtered']} "
              f"friction={dev['friction_filtered']} valid={dev['live_valid']} "
              f"pts={dev['bucket_points']} useParams={dev['use_params']}")
    elif use_device:
        print(f"device: unreachable ({COMMA_HOST})")
    if route:
        print(f"route {route['route']}: filtered {route['filtered_start_end'][0]} -> "
              f"{route['filtered_start_end'][1]}   raw median {route['raw_factor_median']} "
              f"(p10-p90 {route['raw_factor_p10_p90']})   "
              f"friction {route['friction_filtered_end']} (raw {route['friction_raw_median']})   "
              f"valid={route['live_valid']} pts={route['bucket_points']}")
    vd = out["verdict"]
    if vd.get("deploy_mismatch"):
        print(f"\n!! {vd['deploy_mismatch']}")
    print(f"\nVERDICT: {vd['recommendation'] or vd.get('note')}")


if __name__ == "__main__":
    main()
