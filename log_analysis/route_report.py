# /// script
# requires-python = ">=3.11"
# dependencies = ["pandas", "numpy"]
# ///
"""Report of one route: overview, engagement, lateral tracking quality,
oscillation metrics, learning state, faults.

Usage:
  uv run route_report.py <route>        # e.g. 00000029--0f498d7077
  uv run route_report.py --last         # newest converted route
  uv run route_report.py --last --json  # machine-readable output
  uv run route_report.py --list         # routes available locally

Requires the route CSVs (see comma-logs-to-csv skill). Env: COMMA_LOGS_DIR.
"""

import argparse
import json
import sys

from oplog import list_routes, route_metrics


def show(m: dict) -> None:
    o, e = m["overview"], m["engagement"]
    print(f"== ROUTE {m['route']} ==")
    print(f"{o['duration_min']} min, {o['distance_km']} km, "
          f"mean {o['v_mean_kmh']} km/h, max {o['v_max_kmh']} km/h")
    print(f"\nlateral active {e['lat_active_pct']}%  "
          f"({e['engagements']} engagements, "
          f"{e['overrides_while_engaged']} overrides = {e['overrides_per_min_engaged']}/min engaged)")

    if m["tracking"]:
        t, osc = m["tracking"], m["oscillation"]
        print(f"\nTRACKING (while active)")
        print(f"  lat-accel error: mean abs {t['lat_accel_error_mean_abs']}  "
              f"p95 {t['lat_accel_error_p95']}  max {t['lat_accel_error_max']}  m/s^2")
        print(f"  output mean abs {t['output_mean_abs']}   saturated {t['saturated_pct']}%")
        print(f"\nOSCILLATION")
        print(f"  torque sign flips {osc['torque_sign_flips_per_s']}/s   "
              f"error sign flips {osc['error_sign_flips_per_s']}/s")
        print(f"  oscillation freq {osc['oscillation_freq_hz']} Hz   "
              f"hf torque RMS {osc['osc_torque_rms']}  (longest engaged stretch)")
        for band, b in osc["by_speed_kmh"].items():
            print(f"    {band:>6} km/h ({b['time_s']:.0f}s): "
                  f"flips {b['torque_sign_flips_per_s']}/s, err {b['error_mean_abs']}")
    else:
        print("\n(no significant engaged time - tracking/oscillation skipped)")

    if m["learning"]:
        print(f"\nLEARNING (start -> end)")
        L = m["learning"]
        if "live_delay_s" in L:
            d = L["live_delay_s"]
            print(f"  liveDelay {d['start']} -> {d['end']} s  "
                  f"({d['status']}, validBlocks {d['valid_blocks']})")
        if "torqued" in L:
            q = L["torqued"]
            print(f"  latAccelFactor {q['lat_accel_factor'][0]} -> {q['lat_accel_factor'][1]}   "
                  f"friction {q['friction'][0]} -> {q['friction'][1]}   "
                  f"(valid {q['live_valid']}, {q['bucket_points']} pts)")
        if "live_params" in L:
            p = L["live_params"]
            print(f"  angleOffset {p['angle_offset_deg'][0]} -> {p['angle_offset_deg'][1]} deg   "
                  f"steerRatio {p['steer_ratio'][0]} -> {p['steer_ratio'][1]}   "
                  f"stiffness {p['stiffness_factor'][0]} -> {p['stiffness_factor'][1]}")

    f = m["faults"]
    print(f"\nFAULTS: steerFaultTemporary x{f['steer_fault_temporary_events']}, "
          f"permanent {f['steer_fault_permanent']}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("route", nargs="?")
    ap.add_argument("--last", action="store_true")
    ap.add_argument("--list", action="store_true", dest="list_")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    routes = list_routes()
    if args.list_:
        print("\n".join(routes) or "no converted routes found")
        return
    route = routes[-1] if args.last else args.route
    if not route:
        sys.exit("give a route id, or --last (see --list)")

    m = route_metrics(route)
    print(json.dumps(m, indent=2)) if args.json else show(m)


if __name__ == "__main__":
    main()
