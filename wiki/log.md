# Log

Append-only, chronological record of wiki activity. Entry format:
`## [YYYY-MM-DD] <ingest|query|lint> | <short title>` — greppable with `grep "^## \[" log.md`.

## [2026-07-02] ingest | Wiki bootstrap from opendbc + openpilot_sunny

Instantiated the LLM-wiki pattern (see `../llm-wiki.md`) in `openpilot_scripts/wiki/`.
Raw sources = the code repos: `opendbc` and `openpilot_sunny` (`openpilot`/commaai deferred).

Created:
- Schema section in `../AGENTS.md` (conventions + ingest/query/lint workflows).
- `overview.md`, `index.md`, this log.
- Sources: `opendbc.md`, `openpilot_sunny.md`, `openpilot.md` (stub).
- Concepts: `car-interface-contract.md`, `runtime-pipeline.md` (draft), `safety-model.md`.
- Entities: `psa-peugeot-3008.md`.

Grounded on real inspection of repo trees, `opendbc/car/interfaces.py` base classes, and `opendbc/car/psa/{interface,values}.py`. Open threads noted in `runtime-pipeline.md` (confirm cereal message names) and the PSA entity page (longitudinal path, torque-tuning history).

## [2026-07-02] ingest | Depth pass + Mermaid graphs

Feedback: pages too terse and no dependency/relationship graph for openpilot_sunny. Expanded and added diagrams, all grounded in code:
- `sources/openpilot_sunny.md` — rewritten with fork-lineage graph, repo+submodule **dependency graph** (Mermaid), and detailed selfdrive/system/sunnypilot subsystem tables.
- `concepts/runtime-pipeline.md` — added verified **message-flow graph** (Mermaid) + a full publish/subscribe table + timing, sourced from each daemon's `PubMaster`/`SubMaster` and `cereal/services.py`. Removed "draft".
- `entities/psa-peugeot-3008.md` — expanded with 3-bus CAN layout, full carstate signal map, carcontroller EPS **state-machine** diagram, torque flow, longitudinal-OFF status, CarSpecs, FW query; read `carstate.py`/`carcontroller.py`/`psacan.py` in full.

Verified pub/sub from: `card.py`, `controlsd.py`, `plannerd.py`, `radard.py`, `selfdrived.py`, `modeld.py`, `locationd/{locationd,paramsd,torqued,lagd,calibrationd}.py`. Process list from `system/manager/process_config.py`.

## [2026-07-02] ingest | Lateral control deep-dive

Triggered by a selection on `psa/interface.py` `steerActuatorDelay = 0.376803`. Created `concepts/lateral-control.md`: full torque path (modelV2.desiredCurvature → clip_curvature → LatControlTorque in lateral-accel space → actuators.torque → PSA CarController × STEER_MAX → EPS), the delay-comp chain (steerActuatorDelay seeds lagd → liveDelay → controlsd delay_frames), torque tuning (latAccelFactor/latAccelOffset/friction via configure_torque_tune + torqued live learning), and the NNLC hook (LatControlTorqueExt, sunny-only). Read: `controlsd.py`, `latcontrol_torque.py`, `opendbc/car/lateral.py`, `opendbc/car/interfaces.py` (torque tuning), `lagd.py`.

## [2026-07-02] feedback | Cover openpilot_sunny in depth, not just opendbc

User: "non devi solo studiare opendbc ma anche openpilot_sunny." Correction to focus. Next ingests must prioritize the openpilot_sunny stack (modeld/driving model, plannerd/longitudinal, selfdrived engagement, locationd, MADS) grounded in openpilot_sunny code — the opendbc/PSA port should not dominate the wiki. See feedback memory `wiki-cover-openpilot-sunny`.

## [2026-07-02] ingest | openpilot_sunny stack deep-dive + torque controller v0/v1

Refocused on openpilot_sunny. Created concepts: `driving-model.md` (modeld two-stage vision+policy net → modelV2; grounded in modeld.py/constants.py/fill_model_msg.py), `longitudinal-control.md` (plannerd LongitudinalMpc → longcontrol → accel; PSA long OFF), `engagement-state-machine.md` (selfdrived StateMachine + sunnypilot MADS, with state diagrams).

Then compared the two torque controllers (user request) and added a "v0 vs v1" section to `lateral-control.md`: v1 = upstream `latcontrol_torque.py` (VERSION 1; delay-compensated setpoint + filtered jerk lookahead; KP0.8/KI0.15; no D); v0 = `sunnypilot/.../latcontrol_torque_v0.py` (VERSION 0; jerk folded into setpoint; KP1.0/KI0.3; measurement-rate filter, KD=0). **Selection** in `controlsd_ext.py::initialize_lateral_control`: default (`EnforceTorqueControl` false) → **v0** (FIXME "revert when upstream fixes tuning issues with v1"), so sunny/3008 runs v0 today; `EnforceTorqueControl=1`+`TorqueControlTune!=0` → v1.

## [2026-07-02] query | v0/v1 selection is param/UI/sunnylink-driven, not per-car

Confirmed the torque-controller version is chosen from params `EnforceTorqueControl` + `TorqueControlTune` (both `PERSISTENT|BACKUP` in `params_keys.h`), exposed in the device UI (Settings → Steering) and sunnylink (`settings_ui*`). Fingerprint-independent → **no change needed in `psa/interface.py`** beyond the existing torque-steer declaration. Caveat: `EnforceTorqueControl` ⊕ `NeuralNetworkLateralControl` are mutually exclusive (`ui_state._enforce_constraints`); with NNLC on, base controller is v0 + NN override, so picking v1 means NNLC off. Documented in `lateral-control.md` "Which one runs".

## [2026-07-02] query | NNLC is offline-trained; PSA_PEUGEOT_3008.json exists but not enabled

Clarified NNLC workflow (grounded in `nnlc/helpers.py::get_nn_model_path` + the model json). NNLC models are trained OFFLINE from logs (json has `layers`, `input_mean/std/vars`, `model_test_loss`, training timestamp) and committed to `neural_network_data`; the device does NOT train them. On-device live learning = `torqued` (latAccelFactor/offset/friction) + `lagd` (lag). `PSA_PEUGEOT_3008.json` exists ONLY in `cristianku/neural-network-data` (115 models vs 114 upstream), trained 2026-07-01, test loss 0.0257, 18 inputs / 4 layers. `get_nn_model_path` matches it by fingerprint (exact), but it's only used when `NeuralNetworkLateralControl` is on — Cristian hasn't enabled it yet, so the 3008 runs the v0 base controller with live torqued/lagd. Added "trained offline / matching / PSA status" to `lateral-control.md` NNLC section.

## [2026-07-02] ingest | Speed Limit Control (SLC)

From the Cruise → Speed Limit Settings UI. Documented SLC in `longitudinal-control.md`: Mode (off/information/warning/assist), Source/Policy (car/map/combined), Offset (off/fixed/percentage; final = limit + offset). Key grounded finding (`speed_limit/helpers.set_speed_limit_assist_availability`): if `not openpilotLongitudinalControl and pcmCruiseSpeed`, SLC assist is disallowed and auto-downgraded to warning → **on the PSA 3008 (OP long off, stock ACC) SLC can only inform/warn, never actuate speed**. Sources: `speed_limit/common.py`, `helpers.py`, `speed_limit_resolver.py`, `longitudinal_planner.py` (SP), `params_keys.h`.

## [2026-07-02] query | SLC car source needs CarStateSP.speedLimit — PSA doesn't populate it

Confirmed (user's intuition, verified): SLC's car source reads `sm['carStateSP'].speedLimit` (`speed_limit_resolver._get_from_car_state`); base `car.capnp` has no `speedLimit` — it's an SP field the port's `carstate.py` must fill from a CAN TSR signal. `psa/carstate.py` sets no speed-limit field → `carStateSP.speedLimit = 0` → on the 3008 the car source is empty and SLC (already warning-only due to OP long off) is effectively **map-only**. Noted in `longitudinal-control.md` SLC section + PSA entity open threads.

## [2026-07-02] ingest | Drive-log analysis: lane-center oscillation + TSR CAN hunt

First wiki ingest grounded in **device rlogs** rather than code. Two new entity pages:

- `entities/psa-3008-torque-oscillation-2026-07.md` — analyzed ~11 min of highway rlogs (routes `0000001f--29c561ddb1` seg 25–33, `00000022--b31b936f36` seg 5–6, extracted on-device via LogReader). Confirmed 0.5–0.7 Hz lane-center weave; root cause chain: quadratic effective gain from |torque|-scaled TORQUE_FACTOR (57% of active time in the <40% gain zone) + `new_actuators.torque` reported without the factor → torqued live friction inflated to 0.25–0.26 and in use (`useParams=1`). Fixes proposed (report effective torque; slew-limit the factor), constrained by Cristian's requirement to keep the soft center feel. Also noted `steeringTorqueEps` is never populated.
- `entities/psa-3008-can-reverse-engineering.md` — hunted the recognized-speed-limit ("60" cluster display) message using two video-confirmed sign passages as ground truth (frames extracted from fcamera.hevc). Negative result: not on buses 0/1/2 → likely IS CAN behind BSI; needs external sniffer. Byproducts: `0x3F2` confirmed live as the **stock camera's LANE_KEEP_ASSIST** (DBC byte5 TORQUE_FACTOR stays 0; `unknown2` byte2 is the slew-limited 0–100 gain-like ramp — the port sends 24 fixed), `0x50E` = ACC HMI mirror w/ SPEED_SETPOINT copy, `0x2E8` ACC flags, `0x48E`/`0x54E` speed km/h, `0x552` odometer, plus decoy dynamics (`0x2D8`, `0x4F6`, `0x348` bWUC).

Cross-refs updated: PSA entity (known-issue box in the lateral section; Torque tuning + Speed limit/TSR open threads), `concepts/lateral-control.md` (Related), `index.md`.

## [2026-07-02] ingest | Factor slew applied; effective-torque reporting rejected (steer_limited_by_safety)

Applied fix 1 from `entities/psa-3008-torque-oscillation-2026-07.md` in `opendbc` (`psa-torque-sunny-testing`): TORQUE_FACTOR now slews ±3/step toward the same MIN→MAX target (old instant recompute left commented). Fix "report cmd×factor/100 in actuatorsOutput.torque" was applied then **reverted**: verified in openpilot_sunny that `controlsd.py` uses `|actuators.torque − actuatorsOutput.torque| > 1e-2` as `steer_limited_by_safety`, which freezes the lateral integrator in every latcontrol variant → a factor-scaled report would read as permanently-limited steer at center. Warning comment added at the reporting line in `carcontroller.py`; torqued over-estimation remains an open sunny-side thread. Also added a liveDelay (~0.46 s) breakdown section: ~200 ms DELTA_UP ramp + ~100–150 ms low-gain onset + ~50–100 ms real EPS/vehicle — EPS hardware likely fine.
