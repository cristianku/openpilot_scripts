---
title: Overview — openpilot / opendbc knowledge wiki
type: overview
repos: [opendbc, openpilot_sunny, openpilot]
updated: 2026-07-02
---

# Overview

This wiki is the compounding knowledge base for understanding and developing openpilot, maintained in the `openpilot_scripts` repo. Its **raw sources** are the code repos themselves — read from, never edited by the wiki:

- [opendbc](sources/opendbc.md) — the car-abstraction layer (CAN parsing/packing, per-brand ports, panda safety). Consumed by openpilot as the `opendbc_repo` submodule.
- [openpilot_sunny](sources/openpilot_sunny.md) — the full ADAS stack. A fork of **sunnypilot**, which is itself a fork of **commaai/openpilot**.
- [openpilot](sources/openpilot.md) — commaai upstream *(to be ingested later; sunnypilot's ancestor)*.

See [../AGENTS.md](../AGENTS.md) for the wiki schema (conventions + ingest/query/lint workflows). This page is the entry point; [index.md](index.md) is the full catalog.

## How the pieces fit

openpilot is the application; **opendbc is its car interface**; **panda is the independent safety layer** (firmware). The relationship is submodule-based (exact commit SHAs), documented in [../docs/branches-and-submodules.md](../docs/branches-and-submodules.md).

```
        camera/sensors                         CAN bus
             │                                    ▲
             ▼                                    │
  ┌───────────────────┐   plan    ┌──────────────┴───────────────┐
  │ perception (modeld)│ ───────▶ │ control → car abstraction     │
  │ localization       │          │ (controlsd → card → opendbc   │
  │ (locationd)        │          │  CarController) → panda safety │
  └───────────────────┘          └───────────────────────────────┘
```

The runtime data flow (which daemon produces what) is documented in [concepts/runtime-pipeline.md](concepts/runtime-pipeline.md).

## The car port contract

Adding or maintaining a car (like the Peugeot 3008) means implementing the **opendbc car interface contract**: `interface.py`, `carstate.py`, `carcontroller.py`, `values.py`, `fingerprints.py`. This contract is the single most important concept for this project — see [concepts/car-interface-contract.md](concepts/car-interface-contract.md).

The concrete port we maintain: [entities/psa-peugeot-3008.md](entities/psa-peugeot-3008.md).

## Safety

Every actuation is bounded by the panda safety model (C code + tests in `opendbc/safety`). The PSA port uses `SafetyModel.psa`. See [concepts/safety-model.md](concepts/safety-model.md). Safety + interface tests gate every promotion to a stable branch (the merge skills enforce this — [../docs/skills.md](../docs/skills.md)).
