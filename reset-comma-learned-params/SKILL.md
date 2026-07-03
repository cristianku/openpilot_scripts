---
name: reset-comma-learned-params
description: Reset the learned lateral-tuning params on Cristian's comma device (LiveDelay, LiveTorqueParameters, LiveParametersV2) so lagd/torqued relearn from the offline opendbc values. Use after changing steerActuatorDelay, torque_data/override.toml, or anything that alters the steering plant (e.g. torque factor logic). Keeps user toggles and camera calibration.
---

# Reset comma learned params

Wipe the auto-learned lateral params on the comma device so learning restarts
from the offline values shipped in opendbc. Required after any change to the
steering plant or its offline model, otherwise cached estimates (e.g. an old
`LiveDelay`) silently override the new code.

## Workflow

1. Run the bundled script by absolute path: `scripts/reset_learned_params.sh [--reboot] [--force]`.
2. The script verifies the device is reachable over SSH and **offroad** (refuses onroad unless `--force`).
3. It deletes only the learned caches in `/data/params/d/`:
   - `LiveDelay` — lagd actuator-delay estimate (this is what makes a new `steerActuatorDelay` inert if left in place)
   - `LiveTorqueParameters` — torqued latAccelFactor/friction fit
   - `LiveParametersV2` (and legacy `LiveParameters`) — stiffness, steer ratio, angle offset
4. It confirms deletion and reports what was removed.
5. With `--reboot` it reboots the device; otherwise remind the user to reboot before the next drive.

## Usage

- Normal: `scripts/reset_learned_params.sh --reboot`
- Without reboot: `scripts/reset_learned_params.sh` (reboot manually before driving)

## Safety

- Never deletes `LiveTorqueParamsToggle` / `LiveTorqueParamsRelaxedToggle` (user settings) or `CalibrationParams` (camera calibration — valid and slow to relearn).
- Refuses to act while the device is onroad: controlsd holds the old values in memory and would rewrite them.
- Reset AFTER deploying new software to the device, not before — otherwise the old code relearns stale values onto the clean slate.

## Overrides

- `COMMA_HOST`: ssh host of the device (default `comma`).
