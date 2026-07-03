# /// script
# requires-python = ">=3.11"
# dependencies = ["pandas", "numpy"]
# ///
"""A/B comparison of routes - did a tuning change actually improve things?

Usage:
  uv run compare_routes.py <routeA> <routeB> [routeC ...]
  uv run compare_routes.py <routeA> <routeB> --json

Columns are printed oldest-argument-first; with exactly two routes a delta
column shows B-A (negative flips/error = improvement). Routes must already
be converted to CSV (comma-logs-to-csv skill). Env: COMMA_LOGS_DIR.
"""

import argparse
import json

from oplog import route_metrics

# (label, path into the metrics dict, lower_is_better)
ROWS = [
    ("duration_min",            ("overview", "duration_min"), None),
    ("distance_km",             ("overview", "distance_km"), None),
    ("v_mean_kmh",              ("overview", "v_mean_kmh"), None),
    ("lat_active_pct",          ("engagement", "lat_active_pct"), None),
    ("overrides_per_min",       ("engagement", "overrides_per_min_engaged"), True),
    ("error_mean_abs",          ("tracking", "lat_accel_error_mean_abs"), True),
    ("error_p95",               ("tracking", "lat_accel_error_p95"), True),
    ("saturated_pct",           ("tracking", "saturated_pct"), True),
    ("torque_flips_per_s",      ("oscillation", "torque_sign_flips_per_s"), True),
    ("error_flips_per_s",       ("oscillation", "error_sign_flips_per_s"), True),
    ("oscillation_freq_hz",     ("oscillation", "oscillation_freq_hz"), None),
    ("osc_torque_rms",          ("oscillation", "osc_torque_rms"), True),
]


def dig(m, path):
    for k in path:
        if m is None:
            return None
        m = m.get(k)
    return m


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("routes", nargs="+")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    if len(args.routes) < 2:
        ap.error("need at least two routes to compare")

    metrics = {r: route_metrics(r) for r in args.routes}

    if args.json:
        print(json.dumps(metrics, indent=2))
        return

    short = [r.split("--")[0] for r in args.routes]
    w = max(22, *(len(s) + 2 for s in short))
    header = f"{'metric':<24}" + "".join(f"{s:>{w}}" for s in short)
    delta = len(args.routes) == 2
    if delta:
        header += f"{'delta (B-A)':>{w}}"
    print(header)
    print("-" * len(header))

    for label, path, lower_better in ROWS:
        vals = [dig(metrics[r], path) for r in args.routes]
        line = f"{label:<24}" + "".join(
            f"{('-' if v is None else v):>{w}}" for v in vals)
        if delta and None not in vals:
            d = round(vals[1] - vals[0], 3)
            mark = ""
            if lower_better is not None and d != 0:
                improved = (d < 0) if lower_better else (d > 0)
                mark = "  improved" if improved else "  WORSE"
            line += f"{d:>{w - len(mark)}}{mark}" if mark else f"{d:>{w}}"
        print(line)

    # per-speed oscillation detail
    print("\ntorque sign flips /s by speed band:")
    bands = sorted({b for r in args.routes
                    for b in (dig(metrics[r], ("oscillation", "by_speed_kmh")) or {})})
    for band in bands:
        vals = [dig(metrics[r], ("oscillation", "by_speed_kmh", band,
                                 "torque_sign_flips_per_s")) for r in args.routes]
        print(f"  {band:>8} km/h " + "".join(
            f"{('-' if v is None else v):>{w}}" for v in vals))

    if delta:
        print("\nnote: routes differ in road/speed mix - compare the same kind of "
              "drive, and prefer the by-speed rows over the totals.")


if __name__ == "__main__":
    main()
