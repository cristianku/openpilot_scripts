---
title: Wiki index
type: index
updated: 2026-07-02
---

# Index

Catalog of every wiki page. Read this first when answering a question, then drill into the relevant pages. Keep it current on every ingest.

## Start here

- [overview.md](overview.md) — architecture map + how the repos fit together (entry point).
- [../AGENTS.md](../AGENTS.md) — the wiki schema (conventions + ingest/query/lint workflows).

## Sources (raw code repos — read-only)

- [sources/opendbc.md](sources/opendbc.md) — car-abstraction layer (CAN, ports, safety).
- [sources/openpilot_sunny.md](sources/openpilot_sunny.md) — full ADAS stack (sunnypilot fork).
- [sources/openpilot.md](sources/openpilot.md) — commaai upstream *(stub, not yet ingested)*.

## Concepts (cross-cutting)

- [concepts/car-interface-contract.md](concepts/car-interface-contract.md) — the 3 base classes a car port implements.
- [concepts/runtime-pipeline.md](concepts/runtime-pipeline.md) — perception → plan → control → actuation; verified daemon pub/sub + Mermaid message-flow graph.
- [concepts/driving-model.md](concepts/driving-model.md) — modeld vision+policy net → `modelV2` (openpilot_sunny).
- [concepts/lateral-control.md](concepts/lateral-control.md) — path curvature → torque → EPS; delay comp, torque tuning, NNLC (openpilot_sunny controlsd).
- [concepts/longitudinal-control.md](concepts/longitudinal-control.md) — plannerd MPC → longcontrol → accel (openpilot_sunny).
- [concepts/engagement-state-machine.md](concepts/engagement-state-machine.md) — selfdrived states + sunnypilot MADS.
- [concepts/safety-model.md](concepts/safety-model.md) — independent panda safety enforcement.

Diagrams (Mermaid): dependency + fork-lineage graphs in [sources/openpilot_sunny.md](sources/openpilot_sunny.md); message-flow graph in [concepts/runtime-pipeline.md](concepts/runtime-pipeline.md); EPS state machine + data-flow in [entities/psa-peugeot-3008.md](entities/psa-peugeot-3008.md).

## Entities (concrete things)

- [entities/psa-peugeot-3008.md](entities/psa-peugeot-3008.md) — Cristian's Peugeot 3008 port.
- [entities/psa-3008-torque-oscillation-2026-07.md](entities/psa-3008-torque-oscillation-2026-07.md) — lane-center weave analysis from device rlogs: quadratic torque-factor gain + mis-reported actuator torque → corrupted torqued friction → 0.5–0.7 Hz limit cycle; recommended fixes.
- [entities/psa-3008-can-reverse-engineering.md](entities/psa-3008-can-reverse-engineering.md) — CAN findings beyond the DBC: stock camera LKA (`0x3F2`) behavior, ACC setpoint/HMI mirrors, odometer/speed fields, and the negative TSR result (recognized speed limit not on harness-visible buses).

## Operational runbook (Cristian's fork/branch/device workflow)

Lives in [../docs/](../docs/) (not part of the code wiki, but linked from it):
- [../docs/repos-and-workspace.md](../docs/repos-and-workspace.md)
- [../docs/branches-and-submodules.md](../docs/branches-and-submodules.md)
- [../docs/skills.md](../docs/skills.md)
- [../docs/neural-network-data-submodule.md](../docs/neural-network-data-submodule.md)
- [../docs/device-operations.md](../docs/device-operations.md)
