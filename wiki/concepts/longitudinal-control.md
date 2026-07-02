---
title: Longitudinal control (plannerd → longcontrol → accel)
type: concept
repos: [openpilot_sunny, opendbc]
sources: [selfdrive/controls/lib/longitudinal_planner.py, selfdrive/controls/lib/longitudinal_mpc_lib/long_mpc.py, selfdrive/controls/lib/longcontrol.py, selfdrive/controls/lib/drive_helpers.py, opendbc/opendbc/car/interfaces.py]
updated: 2026-07-02
---

# Longitudinal control

The speed/gap side of the stack: decide a target acceleration, then command it. Two stages, both in `selfdrive/controls/`.

## plannerd — the longitudinal plan

`plannerd.py` runs `LongitudinalPlanner` (`longitudinal_planner.py`, at `DT_MDL` = 20 Hz), which solves a **Model Predictive Control** problem (`LongitudinalMpc`, `longitudinal_mpc_lib/long_mpc.py`) over the model horizon to produce a speed/accel trajectory. Inputs: `modelV2` (ego plan + `leadsV3`), the cruise set speed (`V_CRUISE`, from `car/cruise.py`), current `carState`, `radarState`.

Acceleration is bounded by:
- `get_max_accel(v_ego)` — `A_CRUISE_MAX_VALS = [1.6, 1.2, 0.8, 0.6]` over speed breakpoints `[0, 10, 25, 40]` m/s (less accel at higher speed).
- `ACCEL_MIN / ACCEL_MAX = -3.5 / 2.0` m/s² (from `opendbc/car/interfaces.py`).
- `limit_accel_in_turns(...)` — reserves a lateral-accel budget so it won't accelerate hard mid-corner.
- `get_coast_accel(pitch)` — engine-braking/coast model on grades.

The MPC picks a **source** (`LongitudinalPlanSource`: cruise vs lead follow). Output: `longitudinalPlan` (+ sunnypilot `longitudinalPlanSP`), consumed by `controlsd`.

## controlsd — plan → actuator accel

`controlsd` runs `LongControl` (`longcontrol.py`) with a small state machine `LongCtrlState` (`off` / `pid` / `stopping` / `starting`) that turns the planned accel into `carControl.actuators.accel`, handling smooth stop/launch. This becomes the accel the car port must realize.

## At the car (opendbc)

`card` → the port's `CarController` turns `actuators.accel` into brake/gas/ACC CAN. Whether openpilot does this at all is gated by `CP.openpilotLongitudinalControl`. **On the PSA Peugeot 3008 it is currently OFF** (`openpilotLongitudinalControl = alpha_long`, `alphaLongitudinalAvailable = False`, `radarUnavailable = True`) — the ACC/torque path in `psa/carcontroller.py` is commented-out scaffolding. See [../entities/psa-peugeot-3008.md](../entities/psa-peugeot-3008.md). So today the sunny stack plans longitudinally but the 3008 does not actuate it (stock ACC stays in control).

## sunnypilot specifics

`LongitudinalPlanner` subclasses `LongitudinalPlannerSP` (`sunnypilot/.../longitudinal_planner.py`) which layers SP features onto the base plan, most notably **Speed Limit Control (SLC)**.

### Speed Limit Control (SLC)

`sunnypilot/selfdrive/controls/lib/speed_limit/` resolves a target speed limit and (optionally) feeds it to the planner as a `LongitudinalPlanSource.speedLimitAssist`. Settings (`common.py` enums):

- **Mode** (`SpeedLimitMode`): `off` (0) / `information` (1, just show the sign) / `warning` (2) / `assist` (3, actively adjust set speed). **Warning** is rendered in the onroad UI (`ui/sunnypilot/onroad/speed_limit.py::_draw_sign_main`): when `is_overspeed = has_limit and round(speed_limit_final_last) < round(speed)`, the on-screen limit sign turns **red** — a **visual** cue (no chime found in the UI code). It requires `has_limit = speed_limit_valid or speed_limit_last_valid`, so with no valid limit the sign is grey ("---") and there is no warning.
- **Source / Policy**: `car_state_only`, `map_data_only`, `car_state_priority`, `map_data_priority`, `combined` (4 — both car + map). The **car** source reads `carStateSP.speedLimit` (`resolver._get_from_car_state`) — an SP field the port's `carstate.py` must populate from a CAN TSR signal (base `car.capnp` has no `speedLimit`). The **map** source reads `liveMapDataSP.speedLimit`/`speedLimitAhead` from `mapd`/`navd` (OSM), gated on GPS-fix age.
  - **PSA 3008: the car source is empty.** `psa/carstate.py` sets no speed-limit field, so `carStateSP.speedLimit = 0` — with `combined`, only the **map** source actually contributes. To enable the car source you'd need the 3008 to broadcast a speed-limit/TSR signal on CAN and parse it into `ret_sp.speedLimit`.
  - **Reference implementations** (brands that fill `ret_sp.speedLimit`): `opendbc/sunnypilot/car/{hyundai,toyota,tesla}/carstate_ext.py`. Hyundai's `update_speed_limit` reads the camera TSR (`LKAS12.CF_Lkas_TsrSpeed_Display_Clu`) or nav head-unit (`Navi_HU.SpeedLim_Nav_Clu`) on legacy CAN, or `FR_CMR_02_100ms.ISLW_SpdCluMainDis` on CAN-FD, treats 0/255 as "no data", then `ret_sp.speedLimit = value * speed_conv`. It's gated behind SP flags (`SPEED_LIMIT_AVAILABLE`, `HAS_LKAS12`).
- **Offset**: `OffsetType` `off`/`fixed`/`percentage`; final target = `speed_limit + offset` (percentage → `value% × limit`).

**Availability depends on openpilot longitudinal** (`helpers.set_speed_limit_assist_availability`): if `not CP.openpilotLongitudinalControl and CP_SP.pcmCruiseSpeed`, SLC is **not allowed to actuate** and any `assist` mode is auto-downgraded to `warning`. So on cars where openpilot does not control longitudinal — **including the PSA 3008** (`openpilotLongitudinalControl` off, stock ACC) — SLC can only **inform/warn**, never slow the car. See [../entities/psa-peugeot-3008.md](../entities/psa-peugeot-3008.md).

## Related

- [driving-model.md](driving-model.md) — `action.desiredAcceleration` + `leadsV3` feeding the plan.
- [runtime-pipeline.md](runtime-pipeline.md) — plannerd/controlsd messages.
- [lateral-control.md](lateral-control.md) — the steering counterpart.
