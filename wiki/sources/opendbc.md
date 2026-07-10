---
title: opendbc (car-abstraction layer)
type: source
repo: opendbc
remote: https://github.com/cristianku/opendbc.git
upstream: commaai/opendbc
updated: 2026-07-02
---

# opendbc

The car-abstraction layer: it turns raw CAN traffic into openpilot's normalized car state and turns control commands back into CAN messages, and it holds the panda **safety** code. openpilot pulls it in as the `opendbc_repo` submodule. Local checkout: `/Users/cristianku/GitHub/COMMA.AI/CRISTIANKU/opendbc`.

## Top-level layout (`opendbc/opendbc/`)

| Dir/file | Role |
| --- | --- |
| `can/` | CAN message parsing/packing engine (`CANParser`, `CANPacker`) driven by DBC files. |
| `car/` | The car ports and the interface contract (see below). |
| `dbc/` | DBC definition files (signal ↔ bytes maps), e.g. `psa_aee2010_r3`. |
| `safety/` | Panda safety model: C headers, per-model logic (`modes/`), and tests. See [../concepts/safety-model.md](../concepts/safety-model.md). |
| `sunnypilot/` | sunnypilot-specific extensions layered on top (`car/`, `mads_base.py`). The base classes inherit from `...SP` mixins defined here. |
| `testing.py` | Test helpers. |

## `car/` — the port contract

The heart of the repo. Key shared files:

- `interfaces.py` — the base classes `CarInterfaceBase`, `CarStateBase`, `CarControllerBase` (and radar). Full contract: [../concepts/car-interface-contract.md](../concepts/car-interface-contract.md).
- `structs.py` — the normalized data structs: `CarParams`, `CarState`, `CarControl`, `Actuators`, enums (`SafetyModel`, `SteerControlType`, `GearShifter`, …).
- `values.py` (top-level) — the global `PLATFORMS` registry aggregating every brand's `CAR`.
- `car_helpers.py`, `fingerprints.py`, `fw_versions.py` — car identification (fingerprinting by CAN messages / firmware versions).
- `docs_definitions.py`, `docs.py` — auto-generated support docs (`CarDocs`, `CarHarness`, `CarParts`).
- `torque_data/` — lateral torque tuning tables (`params.toml`, `override.toml`, `substitute.toml`) used by `configure_torque_tune`.
- `vehicle_model.py` — bicycle model / steering geometry.

Per-brand port directories (each implements the contract): `psa/`, `hyundai/`, `toyota/`, `honda/`, `ford/`, `gm/`, `chrysler/`, `mazda/`, `nissan/`, `subaru/`, `tesla/`, `volkswagen/`, `rivian/`, `body/`, plus `mock/`.

Our port lives in `car/psa/` → [../entities/psa-peugeot-3008.md](../entities/psa-peugeot-3008.md).

## Notes

- The fork adds the Peugeot 3008 platform; branches map per [../../docs/branches-and-submodules.md](../../docs/branches-and-submodules.md).
- `master` here diverges from upstream only by the PSA additions on the `psa-torque*` branches.
