# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Analisi mirata: rotonde (frenata) e ripartenze da stop (accelerazione).

Legge i CSV prodotti da log_to_csv.py per una route e risponde a due domande:
  1. Alle rotonde non rallentava abbastanza -> il MODELLO chiedeva di rallentare
     (modelAccel/aTarget negativi) ma la frenata non bastava (aEgo poco negativo),
     oppure il modello non chiedeva affatto di rallentare?
  2. Ripartenze da stop -> quanto era lenta l'accelerazione (comando vs reale)
     e c'era un gasPressed del conducente?

Catena longitudinale confrontata:
  modelAccel (modelV2.action.desiredAcceleration)  -> cosa vuole il modello
  aTarget      (longitudinalPlan.aTarget)          -> cosa comanda il planner
  actAccel     (carControl.actuators.accel)        -> cosa manda al veicolo
  aEgo         (carState.aEgo)                     -> cosa fa davvero il veicolo

Uso:
  python3 analyze_roundabout_restart.py <route> [--json]
  (legge COMMA_LOGS_DIR/csv/<route>/)
"""

import argparse
import bisect
import csv
import json
import os
from pathlib import Path

LOGS_DIR = Path(os.environ.get(
    "COMMA_LOGS_DIR",
    "/Users/cristianku/GitHub/COMMA.AI/CRISTIANKU/openpilot_scripts/comma_logs"))


def load_csv(path: Path) -> list[dict]:
    with path.open(newline="") as f:
        return list(csv.DictReader(f))


def fnum(row: dict, key: str, default=0.0) -> float:
    v = row.get(key)
    if v is None or v == "" or v == "nan" or v == "None":
        return default
    try:
        return float(v)
    except ValueError:
        return default


def bnum(row: dict, key: str, default=0.0) -> float:
    v = row.get(key)
    if v is None or v == "":
        return default
    if v in ("True", "true", "1"):
        return 1.0
    if v in ("False", "false", "0"):
        return 0.0
    return fnum(row, key, default)


def build_timeline(route: str) -> dict:
    base = LOGS_DIR / "csv" / route
    cs = load_csv(base / "carState.csv")
    cc = load_csv(base / "carControl.csv")
    lp = load_csv(base / "longitudinalPlan.csv")
    mv = load_csv(base / "modelV2.csv")

    cs_t = [fnum(r, "logMonoTime") for r in cs]
    cc_t = [fnum(r, "logMonoTime") for r in cc]
    lp_t = [fnum(r, "logMonoTime") for r in lp]
    mv_t = [fnum(r, "logMonoTime") for r in mv]

    def nearest(times, t):
        i = bisect.bisect_left(times, t)
        if i <= 0:
            return 0
        if i >= len(times):
            return len(times) - 1
        return i - 1 if (t - times[i - 1]) <= (times[i] - t) else i

    t0 = cs_t[0]
    rows = []
    for i in range(len(cs)):
        t = cs_t[i]
        r = cs[i]
        j = nearest(cc_t, t)
        k = nearest(lp_t, t)
        m = nearest(mv_t, t)
        rows.append({
            "t": (t - t0) / 1e9,
            "vEgo": fnum(r, "vEgo") * 3.6,
            "aEgo": fnum(r, "aEgo"),
            "gasPressed": bnum(r, "gasPressed"),
            "brakePressed": bnum(r, "brakePressed"),
            "cruiseEnabled": bnum(r, "cruiseState.enabled"),
            "longActive": bnum(cc[j], "longActive"),
            "actAccel": fnum(cc[j], "actuators.accel"),
            "aTarget": fnum(lp[k], "aTarget"),
            "shouldStop": bnum(lp[k], "shouldStop"),
            "planSource": lp[k].get("longitudinalPlanSource", ""),
            "modelAccel": fnum(mv[m], "action.desiredAcceleration"),
            "modelCurv": fnum(mv[m], "action.desiredCurvature"),
            "modelShouldStop": bnum(mv[m], "action.shouldStop"),
        })
    return {"rows": rows, "t0": t0}


def detect_roundabouts(rows, min_dur=3.0, min_curv=0.02):
    """Segmenti con curvatura sostenuta (rotonda/curva stretta)."""
    n = len(rows)
    segs = []
    i = 0
    while i < n:
        if abs(rows[i]["modelCurv"]) >= min_curv:
            j = i
            while j + 1 < n and abs(rows[j + 1]["modelCurv"]) >= min_curv * 0.5:
                j += 1
            dur = rows[j]["t"] - rows[i]["t"]
            if dur >= min_dur:
                segs.append([i, j])
            i = j + 1
        else:
            i += 1
    merged = []
    for s in segs:
        if merged and s[0] - merged[-1][1] < 40:  # ~2s a 20Hz
            merged[-1][1] = s[1]
        else:
            merged.append(s)
    return merged


def detect_stops(rows, min_dur=1.5, v_thresh=5.0):
    """Segmenti di fermo (vEgo < v_thresh) duraturi."""
    n = len(rows)
    segs = []
    i = 0
    while i < n:
        if rows[i]["vEgo"] < v_thresh:
            j = i
            while j + 1 < n and rows[j + 1]["vEgo"] < v_thresh:
                j += 1
            dur = rows[j]["t"] - rows[i]["t"]
            if dur >= min_dur:
                segs.append([i, j])
            i = j + 1
        else:
            i += 1
    return segs


def analyze_roundabout(rows, i0, i1, approach_s=8.0):
    """Finestra: approach_s prima di i0 + traversata. Confronta la catena."""
    a0 = max(0, i0 - int(approach_s * 20))
    win = rows[a0:i1 + 1]
    v_in = win[0]["vEgo"]
    v_min = min(r["vEgo"] for r in win)
    modelAccel_min = min(r["modelAccel"] for r in win)
    aTarget_min = min(r["aTarget"] for r in win)
    actAccel_min = min(r["actAccel"] for r in win)
    aEgo_min = min(r["aEgo"] for r in win)
    model_want_slow = sum(1 for r in win if r["modelAccel"] < -0.5) / max(1, len(win))
    brake_gap = min(r["actAccel"] - r["aEgo"] for r in win)  # >0 = frena meno del comando
    return {
        "t_start": round(win[0]["t"], 1),
        "t_end": round(win[-1]["t"], 1),
        "v_entry_kmh": round(v_in, 1),
        "v_min_kmh": round(v_min, 1),
        "modelAccel_min": round(modelAccel_min, 2),
        "aTarget_min": round(aTarget_min, 2),
        "actAccel_min": round(actAccel_min, 2),
        "aEgo_min": round(aEgo_min, 2),
        "model_want_slow_pct": round(100 * model_want_slow, 0),
        "brake_gap_cmd_vs_real": round(brake_gap, 2),
    }


def analyze_restart(rows, i0, i1, v_end=15.0, max_s=40.0):
    """Ripartenza: dal fermo fino a v>v_end o max_s. Confronta la catena."""
    end = i1
    for k in range(i1, min(len(rows), i1 + int(max_s * 20))):
        if rows[k]["vEgo"] > v_end:
            end = k
            break
    win = rows[i0:end + 1]
    if len(win) < 2:
        return None
    t0 = win[0]["t"]
    t10 = t20 = None
    for r in win:
        if t10 is None and r["vEgo"] >= 10:
            t10 = r["t"] - t0
        if t20 is None and r["vEgo"] >= 20:
            t20 = r["t"] - t0
    dt = win[-1]["t"] - win[0]["t"]
    dv = (win[-1]["vEgo"] - win[0]["vEgo"]) / 3.6
    a_mean = dv / dt if dt > 0 else 0.0
    actAccel_max = max(r["actAccel"] for r in win)
    aTarget_max = max(r["aTarget"] for r in win)
    modelAccel_max = max(r["modelAccel"] for r in win)
    aEgo_max = max(r["aEgo"] for r in win)
    gas_tap = sum(1 for r in win if r["gasPressed"] >= 1.0)
    accel_gap = max(r["actAccel"] - r["aEgo"] for r in win)
    return {
        "t_start": round(t0, 1),
        "t_end": round(win[-1]["t"], 1),
        "dur_s": round(dt, 1),
        "v_end_kmh": round(win[-1]["vEgo"], 1),
        "a_mean_ms2": round(a_mean, 2),
        "t_to_10kmh_s": round(t10, 1) if t10 is not None else None,
        "t_to_20kmh_s": round(t20, 1) if t20 is not None else None,
        "modelAccel_max": round(modelAccel_max, 2),
        "aTarget_max": round(aTarget_max, 2),
        "actAccel_max": round(actAccel_max, 2),
        "aEgo_max": round(aEgo_max, 2),
        "accel_gap_cmd_vs_real": round(accel_gap, 2),
        "gas_tap_samples": gas_tap,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("route")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--min-curv", type=float, default=0.02)
    ap.add_argument("--min-dur", type=float, default=3.0)
    ap.add_argument("--entry-min", type=float, default=25.0,
                    help="mostra solo rotonde con entry speed >= questo (km/h)")
    args = ap.parse_args()

    tl = build_timeline(args.route)
    rows = tl["rows"]
    dur = rows[-1]["t"] - rows[0]["t"]
    vmax = max(r["vEgo"] for r in rows)

    rbs = detect_roundabouts(rows, min_dur=args.min_dur, min_curv=args.min_curv)
    stops = detect_stops(rows)

    rb_all = [analyze_roundabout(rows, i0, i1) for i0, i1 in rbs]
    rb_shown = [r for r in rb_all if r["v_entry_kmh"] >= args.entry_min]
    st_all = [a for a in (analyze_restart(rows, i0, i1) for i0, i1 in stops) if a]
    st_shown = [r for r in st_all if 20 < r["t_start"] < dur - 25]

    result = {
        "route": args.route,
        "duration_s": round(dur, 1),
        "vmax_kmh": round(vmax, 1),
        "n_roundabouts_total": len(rb_all),
        "roundabouts_entry_ge_%d" % args.entry_min: rb_shown,
        "n_stops_total": len(st_all),
        "restarts": st_shown,
    }

    if args.json:
        print(json.dumps(result, indent=2))
        return

    print(f"Route {args.route}: {dur:.0f}s, vmax {vmax:.0f} km/h")
    print(f"\n=== ROTONDE con entry >= {args.entry_min:.0f} km/h ({len(rb_shown)} di {len(rb_all)}) ===")
    print("  catena: modelAccel -> aTarget -> actAccel -> aEgo  (min durante avvicinamento)")
    for k, r in enumerate(rb_shown):
        print(f"  [{k}] t={r['t_start']}-{r['t_end']}s  entry {r['v_entry_kmh']} -> min {r['v_min_kmh']} km/h")
        print(f"      model {r['modelAccel_min']}  aTarget {r['aTarget_min']}  actAccel {r['actAccel_min']}  aEgo {r['aEgo_min']}  (m/s2)")
        print(f"      modello chiedeva rallentare forte: {r['model_want_slow_pct']}%  |  gap cmd-reale frenata: {r['brake_gap_cmd_vs_real']}")
    print(f"\n=== RIPARTENZE DA STOP ({len(st_shown)}) ===")
    print("  catena: modelAccel -> aTarget -> actAccel -> aEgo  (max durante ripartenza)")
    for k, r in enumerate(st_shown):
        print(f"  [{k}] t={r['t_start']}-{r['t_end']}s  dur {r['dur_s']}s  -> {r['v_end_kmh']} km/h  (t10={r['t_to_10kmh_s']}s t20={r['t_to_20kmh_s']}s)")
        print(f"      model {r['modelAccel_max']}  aTarget {r['aTarget_max']}  actAccel {r['actAccel_max']}  aEgo {r['aEgo_max']}  (m/s2)  aMedia {r['a_mean_ms2']}")
        print(f"      gap cmd-reale accel: {r['accel_gap_cmd_vs_real']}  |  gasTap conducente: {r['gas_tap_samples']} campioni")


if __name__ == "__main__":
    main()
