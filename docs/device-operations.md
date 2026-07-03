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

## Update the device to the latest branch (pull the new build)

The on-device openpilot lives at `/data/openpilot` and is a plain git checkout. To
pull down an updated testing branch you fetch, move the checkout to the new tip, and
refresh the submodules.

**Important:** the Peugeot testing branches (`peugeot-3008-sunny-testing`,
`peugeot-3008-testing`) are **force-pushed** by the setup skills, so their history is
rewritten. A plain `git pull` fails on divergence — you must `git fetch` +
`git reset --hard`.

Do this **offroad** (`cat /data/params/d/IsOnroad` must be `0`):

```bash
ssh comma
cd /data/openpilot
git fetch origin
git reset --hard origin/peugeot-3008-sunny-testing   # force-pushed → reset, not pull
git submodule update --init --recursive               # updates opendbc_repo + neural_network_data
scons -j$(nproc)                                       # rebuild (or let manager rebuild at boot)
sudo reboot
```

- `git reset --hard origin/<branch>` — required because the branch was force-pushed;
  a `git pull` would report divergent histories and refuse to fast-forward.
- `git submodule update --init --recursive` — without it, `opendbc_repo` (the PSA port,
  including `override.toml`) and `sunnypilot/neural_network_data` stay on the old commits
  even though the openpilot tree moved.
- `scons` can take a few minutes; alternatively the manager recompiles at boot if the
  `prebuilt` marker is absent.

To confirm the device landed on the right commits after the update:

```bash
cd /data/openpilot && git log --oneline -1 && git submodule status
```

## Decoding param values on the device

The default `python3` lacks `capnp`. Use the venv python that has it:

```bash
/usr/local/venv/bin/python   # Python 3.12, has capnp
```
