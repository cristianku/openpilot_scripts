# comma_logs

Drive logs synced from the comma device (`comma:/data/media/0/realdata/`).
Everything in this folder except this README is **gitignored** — logs are big
(GBs) and never get committed.

## How data gets here

- **Download**: `download-comma-logs` skill
  (`~/.claude/skills/download-comma-logs/scripts/download_logs.sh`)
  - `--last` only the most recent route, `--route <id>` a specific one,
    `--no-video` skip cameras, `--list` show what's on the device.
- **Convert to CSV**: `comma-logs-to-csv` skill
  (`uv run ~/.claude/skills/comma-logs-to-csv/scripts/log_to_csv.py --last`)
- **Analyze / A/B compare**: scripts in [`../log_analysis/`](../log_analysis/README.md)
  (`route_report.py`, `compare_routes.py` — oscillation metrics, learning state, `--json`)

## Layout

```
comma_logs/
├── <route>--<segment>/        # e.g. 00000029--0f498d7077--0  (1 min per segment)
│   ├── rlog.zst               # full log, every message (~100 Hz) — use for analysis
│   ├── qlog.zst               # subsampled log (~20 Hz), small, quick look
│   ├── fcamera.hevc           # road camera        ┐
│   ├── ecamera.hevc           # wide road camera   │ video = the bulk of the size
│   ├── dcamera.hevc           # driver camera      │
│   └── qcamera.ts             # low-res preview    ┘
├── boot/                      # device boot logs (full sync only)
└── csv/<route>/<type>.csv     # output of comma-logs-to-csv
```

A **route** is one ignition-on drive (`00000029--0f498d7077`); segments are
its 1-minute slices. CSVs have one file per message type (`carState.csv`,
`controlsState.csv`, …), nested fields flattened to dot-notation columns,
plus `t` (seconds since route start), `logMonoTime` (ns) and `segment`.

## Useful message types (PSA lateral work)

| type | what's inside |
|---|---|
| `carState` | steeringAngleDeg, steeringTorque (driver), steeringTorqueEps, vEgo, steeringPressed |
| `carControl` | actuators.torque (commanded), latActive |
| `controlsState` | torque controller internals: error, p/i/f, output, saturated, desiredCurvature |
| `carOutput` | what was actually sent to the EPS |
| `liveParameters` | learned angleOffset, steerRatio, stiffnessFactor |
| `liveTorqueParameters` | learned latAccelFactor, friction (torqued) |
| `liveDelay` | learned actuator delay (lagd) |

Schemas: `openpilot_sunny/cereal/log.capnp`. The full openpilot python env
does not build on this Mac (x86_64) — the CSV converter is standalone
(pycapnp + zstandard via uv), don't try `uv sync` in openpilot.
