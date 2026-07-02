---
title: The driving model (modeld → modelV2)
type: concept
repos: [openpilot_sunny]
sources: [selfdrive/modeld/modeld.py, selfdrive/modeld/constants.py, selfdrive/modeld/fill_model_msg.py, selfdrive/modeld/parse_model_outputs.py]
updated: 2026-07-02
---

# The driving model

`modeld` (`selfdrive/modeld/`) is openpilot's perception+planning neural net. It runs at **20 Hz** (`ModelConstants.MODEL_RUN_FREQ`) on camera frames (via `VisionIpc`) and emits `modelV2` — the single most-subscribed message in the stack ([runtime-pipeline.md](runtime-pipeline.md)). Everything downstream (planning, control, engagement) keys off it.

## Two-stage model

modeld runs two compiled nets (tinygrad, `jits` metadata):

1. **Vision** — consumes `N_FRAMES = 2` camera frames per run, outputs a `FEATURE_LEN = 512` feature vector.
2. **Policy** (`on_policy`) — consumes the features plus these inputs and outputs the trajectory/plan:
   - `desire` (`DESIRE_LEN = 8`) — a **rising-edge pulse** (lane-change/turn intent), driven by `DesireHelper`.
   - `traffic_convention` (`2`) — LHD/RHD.
   - `lateral_control_params` (`2`).
   - `prev_desired_curv` (`1`) — feedback of the last curvature.

Time horizon: `T_IDXS` = 33 non-linear points out to **10 s**; `X_IDXS` out to **192 m**.

## `modelV2` outputs (`fill_model_msg.py`)

| Field | Meaning |
| --- | --- |
| `position`, `velocity`, `acceleration`, `orientation`, `orientationRate` | The predicted ego trajectory (the "plan"), each an xyzt over `T_IDXS`. |
| `laneLines` (4) + `laneLineProbs`, `roadEdges` (2) | Lane/road geometry. |
| `leadsV3` (3) | Lead vehicles: distance `x`, velocity, accel, probability. |
| **`action.desiredCurvature`** | The steering target → lateral control. |
| **`action.desiredAcceleration`** | The accel target → longitudinal. |
| `meta` | Disengage predictions, FCW (forward-collision) thresholds, brake/turn probabilities. |
| `confidence` | green / yellow / red model confidence. |

## From model output to control targets (`get_action`)

`modeld.py` derives the `action` two ways:
- **from the plan**: `get_accel_from_plan(...)` and `get_curvature_from_plan(...)` over the predicted trajectory; or
- **from the action head directly**: `desired_curvature = action[0,0] / max(1, v_ego)²`, `desired_accel = action[0,1]`.

Both are smoothed (`LAT_SMOOTH_SECONDS` / `LONG_SMOOTH_SECONDS`) against the previous action. The result:
- `action.desiredCurvature` → `controlsd` → lateral controller ([lateral-control.md](lateral-control.md)).
- `action.desiredAcceleration` → `plannerd`/`controlsd` → longitudinal ([longitudinal-control.md](longitudinal-control.md)).

## sunnypilot specifics

- **Model selection**: `sunnypilot/` adds `models/` + `modeld_v2/` and a **model manager** (`models_manager`) so the driving model file is selectable/downloadable (`modelManagerSP`). Base modeld stays the runner.
- **NNLC is separate**: the neural-network *lateral control* ([lateral-control.md](lateral-control.md)) is a torque model, not this driving model — don't conflate them.
- `driverMonitoringState` comes from a **separate** net, `dmonitoringmodeld`, not this one.

## Related

- [runtime-pipeline.md](runtime-pipeline.md) — modeld's subscribers/publishers and 20 Hz timing.
- [lateral-control.md](lateral-control.md) / [longitudinal-control.md](longitudinal-control.md) — how the action targets become actuator commands.
