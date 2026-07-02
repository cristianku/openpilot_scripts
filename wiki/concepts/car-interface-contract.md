---
title: The car interface contract (opendbc)
type: concept
repos: [opendbc]
sources: [opendbc/opendbc/car/interfaces.py, opendbc/opendbc/car/psa/]
updated: 2026-07-02
---

# The car interface contract

To support a car, a brand port in `opendbc/opendbc/car/<brand>/` implements three base classes from `opendbc/car/interfaces.py`. openpilot's `card.py` drives them each control cycle.

## The three base classes

**`CarInterfaceBase`** (`interfaces.py:98`) — describes the car and wires it up.
- `_get_params(ret, candidate, fingerprint, car_fw, alpha_long, is_release, docs) -> CarParams` (static): fills the `CarParams` for a platform — brand, `safetyConfigs`, lateral tuning, `steerControlType` (torque vs angle), `steerActuatorDelay`, `minSteerSpeed`, `radarUnavailable`, `openpilotLongitudinalControl`, etc.
- Class attributes `CarState` and `CarController` bind the other two classes.
- Note the sunnypilot mixin: `CarInterfaceBase(ABC, CarInterfaceBaseSP)` (from `opendbc/sunnypilot/car/interfaces.py`).

**`CarStateBase`** (`interfaces.py:304`) — CAN → normalized state.
- `update(can_parsers) -> (CarState, CarStateSP)`: reads parsed CAN signals and produces the normalized `CarState` (speed, steering angle/torque, gear, buttons, cruise state, doors, blinkers…).
- Helpers: `update_speed_kf`, `update_blinker_from_lamp/stalk`, `update_steering_pressed`, `update_button_enable`.

**`CarControllerBase`** (`interfaces.py:402`) — control → CAN.
- `update(CC, CC_SP, CS, now_nanos) -> (Actuators, list[CanData])`: takes the desired `CarControl` (from controlsd) and the current state, applies rate/torque limits, and returns the actuators actually commanded plus the CAN messages to send.

## Files a brand port provides

Using PSA as the reference ([../entities/psa-peugeot-3008.md](../entities/psa-peugeot-3008.md)):

| File | Contains |
| --- | --- |
| `interface.py` | `CarInterface(CarInterfaceBase)` + `_get_params`. |
| `carstate.py` | `CarState(CarStateBase)` + the CAN signal parsing. |
| `carcontroller.py` | `CarController(CarControllerBase)` + actuator command building. |
| `values.py` | `CAR` platforms (`Platforms`), `CarControllerParams` (steer limits), DBC map, fingerprints/FW query config, `CarDocs`. |
| `fingerprints.py` | Fingerprint (CAN msg lengths) and/or FW-version tables for car identification. |
| `<brand>can.py` | CAN address/signal helpers used by carstate + carcontroller (e.g. `psacan.py`). |

## Key `CarParams` knobs (steering)

- `steerControlType`: `torque` (EPS takes a torque command, needs lateral torque tuning) vs `angle` (EPS takes an angle). PSA 3008 uses **torque**.
- `CarControllerParams` in `values.py`: `STEER_MAX`, `STEER_STEP`, `STEER_DELTA_UP/DOWN`, `STEER_DRIVER_*`, `MAX/MIN_TORQUE_FACTOR` — these bound and shape the torque command and **must stay within what the panda safety model allows** ([safety-model.md](safety-model.md)).
- `steerActuatorDelay`, `steerLimitTimer`, `minSteerSpeed`, `steerAtStandstill`.

## Related

- [runtime-pipeline.md](runtime-pipeline.md) — where `card.py`/`CarInterface` sits in the loop.
- [safety-model.md](safety-model.md) — the independent enforcement of these limits.
- Torque learning on-device: [../../docs/device-operations.md](../../docs/device-operations.md).
