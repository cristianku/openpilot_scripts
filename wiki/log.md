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
