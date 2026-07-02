---
title: "3008 lane-center oscillation — drive-log analysis (2026-07-02)"
type: entity
repos: [opendbc, openpilot_sunny]
platform: CAR.PSA_PEUGEOT_3008
sources: [opendbc/opendbc/car/psa/carcontroller.py, opendbc/opendbc/car/psa/values.py, opendbc/opendbc/car/torque_data/override.toml]
updated: 2026-07-02
---

# 3008 lane-center oscillation — drive-log analysis (2026-07-02)

Field finding, grounded in device rlogs, not just code. **Symptom** (Cristian, highway ~120 km/h): the car weaves ("ping-pong") around lane center on straights, while curves track well.

## Data analyzed

Device `comma-dd51123b` (dongle `6616faac453a3064`), drives of 2026-07-02:

- Route `0000001f--29c561ddb1` segments 25–33 and `00000022--b31b936f36` segments 5–6 — ~11 min of highway, vEgo 30–32 m/s, `latActive` ≈ 1.0, hands-off.
- Extraction: on-device `LogReader` (`PYTHONPATH=/data/openpilot /usr/local/venv/bin/python3`), 100 Hz series of `carState`, `carControl`, `carOutput`, `controlsState.torqueState`, `liveTorqueParameters` (66k samples).

## Measurements

| Metric | Value |
| --- | --- |
| Steering-angle oscillation on straights | spectral peak **0.5–0.7 Hz**, std 0.8–2.6° (slow-curvature detrended) |
| Torque command distribution while active | p50 = 40/250, p90 = 103/250 → **57% of the time \|T\| < 50** (torque factor < 40) |
| torqued live learning (`useParams=1`, `liveValid=1`) | friction filtered **0.247 → 0.264** rising within the drive; latAccelFactor drifting **2.21 → 1.99** |
| Fixed tune (`torque_data/override.toml`) | `[2.538, 2.767, 0.2105]` — friction 0.21 already ~2× typical (0.05–0.15) |
| Controller output vs friction | straights: mean \|output\| 0.238 vs friction term 0.25 → **friction alone is the size of a typical correction** |
| actual vs desired latAccel lag (straights) | **360–600 ms** cross-correlation delay (`steerActuatorDelay` = 0.376803) |
| `carState.steeringTorqueEps` | **always 0** — not populated by `psa/carstate.py` |

## Root-cause chain

1. `carcontroller.py` scales `TORQUE_FACTOR` linearly with |torque| (`MIN_TORQUE_FACTOR=25` → `MAX=100`, `values.py`). Effective EPS torque ≈ `TORQUE × FACTOR/100`, so the command→torque map is **quadratic**: gain ~0.25–0.4 near center, ~1.0 in curves. Lane centering lives almost entirely in the low-gain zone (57% of samples).
2. `new_actuators.torque` is reported as `apply_torque_last / STEER_MAX` **without the factor** (end of `CarController.update`). At center the port claims ~4× the torque actually applied.
3. `torqued` learns from that over-reported torque → sees "large command, little response near zero" → interprets it as huge friction → live friction 0.25+ **and openpilot uses it** (`useParams=1`).
4. Oversized friction term punches every micro-correction → overshoot → opposite correction → **limit cycle at 0.5–0.7 Hz**. Curves are fine because factor saturates near 100 where reported ≈ real.

## Corroboration from the stock camera

The stock camera's own `LANE_KEEP_ASSIST` (0x3F2) frames — observed on bus 2, see [psa-3008-can-reverse-engineering.md](psa-3008-can-reverse-engineering.md) — never step their gain-like byte instantly: `unknown2` ramps 0→100 over ~15 s at startup and slews 2–3 units per 50 ms frame. The stock system does not change torque authority per-cycle the way the port recomputes `TORQUE_FACTOR` every `STEER_STEP`.

## Fixes

Constraint from Cristian: keep the soft variable factor at center — raising `MIN_TORQUE_FACTOR` or fixing the factor at 100 makes small corrections harsher and is **rejected**.

1. **Slew-limit the factor — APPLIED 2026-07-02** (`carcontroller.py`, old code left commented): same MIN→MAX target from |torque|, but followed at **±3 per 20 Hz step**. +3 exactly matches a full-rate torque ramp (`STEER_DELTA_UP=10` → target moves 75/250×10 = 3/step), so curve entry is unaffected; on the way down the factor decays slower than the torque, which keeps gain up through zero crossings (kills the collapse). Road test + learned-params reset pending.
2. **Report effective torque (cmd × factor/100) in `actuatorsOutput.torque` — tried, then REVERTED after verification**: sunny's controlsd computes `steer_limited_by_safety = |actuators.torque − actuatorsOutput.torque| > 1e-2` (`selfdrive/controls/controlsd.py`) and all latcontrol variants freeze the lateral integrator while it is true (`latcontrol_torque*.py`); a factor-scaled report reads as permanently-limited steer at center. A warning comment now sits on the reporting line in `carcontroller.py`. Consequence: **torqued still over-estimates applied torque at center** — fixing it needs an openpilot_sunny-side change (PSA-aware effective-torque feed to torqued, or port-aware limited-steer comparison). Open thread.
3. Optional: populate `carState.steeringTorqueEps` from CAN so torqued/analysis have a real EPS-torque measurement.

## liveDelay breakdown (why lagd says ~0.46 s)

`liveDelay.lateralDelayEstimate` = 0.446 ± 0.053 (8 valid blocks) on 2026-07-02 — consistent with the 360–600 ms measured here. It is end-to-end, not EPS hardware: ~200 ms command ramp (`STEER_DELTA_UP=10`/step, median command ~40/250 → 4 steps), ~100–150 ms of low-gain onset (factor 25–35 at correction start), ~50–100 ms genuine EPS/bus/vehicle. The EPS itself is likely normal; expect the estimate to drop after the fixes + params reset. Raising `STEER_DELTA_UP` would attack the first term (separate, cautious road experiment — check EPS fault tolerance and panda safety limits).

## Open questions

- Whether the learned friction converges back below ~0.15 after the sunny-side reporting fix + reset (validates the whole chain).
- Whether `steerActuatorDelay` 0.377 s is genuinely the plant delay or partly an artifact of the same nonlinearity (see liveDelay breakdown above).
