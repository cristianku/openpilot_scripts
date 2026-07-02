# Comma device operations

Cristian's comma device (hostname `comma-dd51123b`) is reachable via the SSH alias `ssh comma`.

## Reset self-learned parameters (auto-learning / "autoapprendimento")

openpilot self-learned params are stored as individual **files** (not folders) in `/data/params/d/`:

- `LiveTorqueParameters` — torqued: steering torque learning (`latAccelFactor`, `latAccelOffset`, `friction`)
- `LiveParametersV2` — paramsd: `steerRatio`, `angleOffset`, `stiffnessFactor` (old key `LiveParameters` is migrated away)
- `LiveDelay` — lagd: learned steering actuator lag
- `CalibrationParams` — calibrationd: camera mount calibration

To restart learning from scratch, remove the relevant files **while offroad** (`cat /data/params/d/IsOnroad` must be `0`), then `sudo reboot`. Daemons re-learn from defaults; first drives feel rough until re-converged.

```bash
rm -f /data/params/d/LiveTorqueParameters /data/params/d/LiveDelay
```

Use `rm -f` (files, no `-r`). This is what the UI "Settings → Device → Reset Calibration" button does internally (`params.remove(...)`). Resetting `LiveTorqueParameters` forces torqued to re-learn `latAccelFactor` after changing `STEER_MAX` / torque-factor tuning.

## Decoding param values on the device

The default `python3` lacks `capnp`. Use the venv python that has it:

```bash
/usr/local/venv/bin/python   # Python 3.12, has capnp
```
