---
title: Safety model (panda)
type: concept
repos: [opendbc]
sources: [opendbc/opendbc/safety/]
updated: 2026-07-02
---

# Safety model

Safety is enforced **independently of the driving code**, in the panda safety layer (C). It lives in `opendbc/opendbc/safety/` and is compiled into panda firmware. Even if the control stack commands something unsafe, the safety layer clamps or blocks it. This is why steering limits appear in two places (car port `CarControllerParams` *and* the safety model) and must agree.

## Layout (`opendbc/opendbc/safety/`)

| File/dir | Role |
| --- | --- |
| `safety.h` | Top-level dispatch across safety models. |
| `declarations.h`, `helpers.h`, `can.h` | Shared types, RX/TX helpers, CAN checks. |
| `lateral.h`, `longitudinal.h` | Generic lateral/longitudinal limit helpers (torque/angle rate limits, accel bounds). |
| `ignition.h` | Ignition/engagement gating. |
| `modes/` | Per-brand safety models (one per `SafetyModel`). |
| `sunnypilot/` | sunnypilot-specific safety additions. |
| `tests/` | Python safety tests (must pass to ship). |

## PSA

- The port selects `SafetyModel.psa` via `ret.safetyConfigs = [get_safety_config(SafetyModel.psa)]` in `psa/interface.py`.
- The PSA safety mode in `modes/` must accept the torque commands the [car controller](car-interface-contract.md) can produce (bounded by `STEER_MAX`, `STEER_DELTA_UP/DOWN`, driver-torque allowance) and reject anything outside.

## Why it matters for our workflow

The merge/promotion skills **require the PSA safety tests + interface tests to pass before pushing a stable branch** ([../../docs/skills.md](../../docs/skills.md)). Changing steering limits or CAN TX in the port without updating the safety model/tests will fail promotion — by design.

## Related

- [car-interface-contract.md](car-interface-contract.md) — where the port-side limits are set.
- [../entities/psa-peugeot-3008.md](../entities/psa-peugeot-3008.md) — the concrete limits in use.
