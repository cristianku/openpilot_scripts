"""Shared helpers for analyzing comma/openpilot drive logs exported to CSV.

Input is the per-type CSV export produced by the `comma-logs-to-csv` skill
(one file per message type under comma_logs/csv/<route>/). All metrics are
returned as a plain nested dict so callers can print, diff or JSON-dump them.

Not a package: scripts in this folder import it directly (same dir).
"""

import os
import re
from pathlib import Path

import numpy as np
import pandas as pd

LOGS_DIR = Path(os.environ.get(
    "COMMA_LOGS_DIR",
    "/Users/cristianku/GitHub/COMMA.AI/CRISTIANKU/openpilot_scripts/comma_logs"))

CONVERT_HINT = (
    "uv run ~/.claude/skills/comma-logs-to-csv/scripts/log_to_csv.py {route} "
    "--types carState,carControl,controlsState,liveParameters,liveTorqueParameters,liveDelay"
)

# controlsState column prefix for the torque controller
TS = "lateralControlState.torqueState."

SPEED_BINS = [(0, 30), (30, 60), (60, 200)]  # km/h


def list_routes(csv_only: bool = True) -> list[str]:
    """Routes available locally, oldest first."""
    base = LOGS_DIR / "csv" if csv_only else LOGS_DIR
    if not base.is_dir():
        return []
    if csv_only:
        return sorted(d.name for d in base.iterdir() if d.is_dir())
    return sorted({m.group(1) for d in base.iterdir()
                   if (m := re.match(r"^(.+)--\d+$", d.name))})


def load_route(route: str) -> dict[str, pd.DataFrame | None]:
    """Load the CSVs of a route. carState/carControl/controlsState are
    required; learning topics are optional (None when missing)."""
    d = LOGS_DIR / "csv" / route
    if not d.is_dir():
        raise FileNotFoundError(
            f"no CSVs for route '{route}' in {d}.\n"
            f"Convert first: {CONVERT_HINT.format(route=route)}")
    out = {}
    for name in ["carState", "carControl", "controlsState",
                 "liveParameters", "liveTorqueParameters", "liveDelay"]:
        f = d / f"{name}.csv"
        out[name] = pd.read_csv(f) if f.is_file() else None
    for req in ["carState", "carControl", "controlsState"]:
        if out[req] is None:
            raise FileNotFoundError(
                f"{req}.csv missing for '{route}'.\n"
                f"Convert first: {CONVERT_HINT.format(route=route)}")
    return out


def _rising_edges(b: pd.Series) -> int:
    return int((b.astype(int).diff() == 1).sum())


def _sign_flips(s: pd.Series) -> int:
    return int((np.sign(s).diff().abs() == 2).sum())


def _round(x, nd=3):
    return None if x is None or (isinstance(x, float) and np.isnan(x)) else round(float(x), nd)


def _dominant_freq(sig: np.ndarray, fs: float) -> float | None:
    """Peak frequency (Hz) of a detrended, Hann-windowed FFT, searched in
    0.3-3 Hz. Band starts at 0.3 Hz on purpose: below that lives normal
    road-following (curves), above lives the lane-center oscillation.
    None when the window is too short (<10 s)."""
    if len(sig) < 10 * fs:
        return None
    x = sig - sig.mean()
    x = x * np.hanning(len(x))
    freqs = np.fft.rfftfreq(len(x), 1 / fs)
    power = np.abs(np.fft.rfft(x)) ** 2
    band = (freqs >= 0.3) & (freqs <= 3.0)
    if not band.any() or power[band].max() == 0:
        return None
    return float(freqs[band][np.argmax(power[band])])


def _highpass_rms(sig: np.ndarray, fs: float) -> float | None:
    """RMS of the signal minus its 1s centered rolling mean - the amplitude
    of the fast (oscillatory) content, ignoring road curvature."""
    if len(sig) < 10 * fs:
        return None
    k = max(int(fs), 3)
    hp = sig - pd.Series(sig).rolling(k, center=True, min_periods=1).mean().values
    return float(np.sqrt(np.mean(hp ** 2)))


def _longest_true_run(mask: np.ndarray) -> slice:
    best = slice(0, 0)
    start = None
    for i, v in enumerate(list(mask) + [False]):
        if v and start is None:
            start = i
        elif not v and start is not None:
            if i - start > best.stop - best.start:
                best = slice(start, i)
            start = None
    return best


def route_metrics(route: str) -> dict:
    """All metrics for one route. Keys are stable: other tools/models rely
    on them, extend but don't rename."""
    d = load_route(route)
    cs, cc, st = d["carState"], d["carControl"], d["controlsState"]
    lp, lt, ld = d["liveParameters"], d["liveTorqueParameters"], d["liveDelay"]

    dt = np.diff(cs.t)
    dur_s = float(cs.t.max() - cs.t.min())
    lat = cc.latActive.astype(bool)

    # align latActive and vEgo onto other timelines (nearest timestamp)
    cs_sorted = cs.sort_values("t")
    st_sorted = st.sort_values("t")
    lat_on_cs = pd.merge_asof(cs_sorted[["t"]], cc.sort_values("t")[["t", "latActive"]],
                              on="t", direction="nearest")["latActive"].astype(bool)
    v_on_st = pd.merge_asof(st_sorted[["t"]], cs_sorted[["t", "vEgo"]],
                            on="t", direction="nearest")["vEgo"]

    overrides = _rising_edges(cs_sorted.steeringPressed.astype(bool) & lat_on_cs)
    engaged_min = float(lat.mean()) * dur_s / 60

    m = {
        "route": route,
        "overview": {
            "duration_min": _round(dur_s / 60, 1),
            "distance_km": _round(np.sum(cs.vEgo.values[:-1] * dt) / 1000, 1),
            "v_mean_kmh": _round(cs.vEgo.mean() * 3.6, 1),
            "v_max_kmh": _round(cs.vEgo.max() * 3.6, 1),
        },
        "engagement": {
            "lat_active_pct": _round(lat.mean() * 100, 1),
            "engagements": _rising_edges(lat),
            "overrides_while_engaged": overrides,
            "overrides_per_min_engaged": _round(overrides / engaged_min, 2) if engaged_min > 0 else None,
        },
    }

    # ---- torque controller, while active ----
    active = st_sorted[f"{TS}active"].astype(bool).values
    ts = st_sorted[active]
    v_ts = v_on_st[active] * 3.6
    if len(ts) > 100:
        fs = 1.0 / float(np.median(np.diff(st_sorted.t)))
        err, out = ts[f"{TS}error"], ts[f"{TS}output"]
        act_s = len(ts) / fs

        run = _longest_true_run(active)
        run_out = st_sorted[f"{TS}output"].values[run]

        m["tracking"] = {
            "lat_accel_error_mean_abs": _round(err.abs().mean()),
            "lat_accel_error_p95": _round(err.abs().quantile(0.95)),
            "lat_accel_error_max": _round(err.abs().max()),
            "output_mean_abs": _round(out.abs().mean()),
            "saturated_pct": _round(ts[f"{TS}saturated"].astype(bool).mean() * 100, 1),
        }
        m["oscillation"] = {
            "torque_sign_flips_per_s": _round(_sign_flips(out) / act_s, 2),
            "error_sign_flips_per_s": _round(_sign_flips(err) / act_s, 2),
            "oscillation_freq_hz": _round(_dominant_freq(run_out, fs), 2),
            "osc_torque_rms": _round(_highpass_rms(run_out, fs)),
            "by_speed_kmh": {},
        }
        for lo, hi in SPEED_BINS:
            band = ts[(v_ts >= lo) & (v_ts < hi)]
            if len(band) < 5 * fs:  # need >=5s in the bin
                continue
            bs = len(band) / fs
            m["oscillation"]["by_speed_kmh"][f"{lo}-{hi if hi < 200 else '+'}"] = {
                "time_s": _round(bs, 0),
                "torque_sign_flips_per_s": _round(_sign_flips(band[f"{TS}output"]) / bs, 2),
                "error_mean_abs": _round(band[f"{TS}error"].abs().mean()),
            }
    else:
        m["tracking"] = None
        m["oscillation"] = None

    # ---- learning state (start -> end of route) ----
    learn = {}
    if ld is not None and len(ld):
        learn["live_delay_s"] = {"start": _round(ld.lateralDelayEstimate.iloc[0]),
                                 "end": _round(ld.lateralDelayEstimate.iloc[-1]),
                                 "status": str(ld.status.iloc[-1]),
                                 "valid_blocks": int(ld.validBlocks.iloc[-1])}
    if lt is not None and len(lt):
        learn["torqued"] = {"lat_accel_factor": [_round(lt.latAccelFactorFiltered.iloc[0]),
                                                 _round(lt.latAccelFactorFiltered.iloc[-1])],
                            "friction": [_round(lt.frictionCoefficientFiltered.iloc[0], 4),
                                         _round(lt.frictionCoefficientFiltered.iloc[-1], 4)],
                            "live_valid": bool(lt.liveValid.iloc[-1]),
                            "bucket_points": int(lt.totalBucketPoints.iloc[-1])}
    if lp is not None and len(lp):
        learn["live_params"] = {"angle_offset_deg": [_round(lp.angleOffsetDeg.iloc[0], 2),
                                                     _round(lp.angleOffsetDeg.iloc[-1], 2)],
                                "steer_ratio": [_round(lp.steerRatio.iloc[0], 2),
                                                _round(lp.steerRatio.iloc[-1], 2)],
                                "stiffness_factor": [_round(lp.stiffnessFactor.iloc[0], 2),
                                                     _round(lp.stiffnessFactor.iloc[-1], 2)]}
    m["learning"] = learn or None

    m["faults"] = {
        "steer_fault_temporary_events": _rising_edges(cs.steerFaultTemporary.astype(bool)),
        "steer_fault_permanent": bool(cs.steerFaultPermanent.any()),
    }
    return m
