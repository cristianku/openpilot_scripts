# log_analysis

Scripts to judge how the PSA (Peugeot 3008) lateral port is behaving from
drive logs, and to A/B compare tuning changes. Written to be driven by a
human **or an LLM agent**: stable CLI, stable metric keys, `--json` output.

## Workflow

```bash
# 1. pull logs from the device (skill: download-comma-logs)
~/.claude/skills/download-comma-logs/scripts/download_logs.sh --last --no-video

# 2. convert to CSV (skill: comma-logs-to-csv)
uv run ~/.claude/skills/comma-logs-to-csv/scripts/log_to_csv.py --last \
  --types carState,carControl,controlsState,liveParameters,liveTorqueParameters,liveDelay

# 3. analyze (this folder; uv provides pandas/numpy automatically)
uv run route_report.py --last            # single-route report
uv run route_report.py --last --json     # same, machine-readable
uv run route_report.py --list            # locally available routes
uv run compare_routes.py <routeA> <routeB> [--json]   # A/B after a tuning change
```

Everything reads the CSVs under `comma_logs/csv/<route>/` (env override:
`COMMA_LOGS_DIR`). If a route isn't converted yet, the scripts print the
exact command to run. `oplog.py` holds the shared metric code — import it
for custom analysis; treat metric key names as a stable API (extend, don't
rename).

## Metric glossary & how to read it

**engagement**
- `lat_active_pct`, `engagements` — how much/often openpilot steered.
- `overrides_per_min_engaged` — rising edges of `steeringPressed` while
  engaged, per engaged minute. High values = driver keeps correcting
  (or the PSA driver-torque threshold flickers — inspect `carState.steeringTorque`).

**tracking** (torque controller, only while active)
- `lat_accel_error_mean_abs` / `_p95` / `_max` (m/s²) — desired vs actual
  lateral accel. Lower is better; mean abs ≲0.2 is decent, p95 ≳0.6 means
  visible corner cutting / weaving.
- `saturated_pct` — % of time the request hit its limit. Non-zero at normal
  speeds suggests latAccelFactor too low or torque limits too tight.

**oscillation** — the lane-center zig-zag signature (the main PSA issue)
- `torque_sign_flips_per_s`, `error_sign_flips_per_s` — how often command /
  error cross zero. A calm controller sits well under ~1/s on straights;
  ~3/s means visible zig-zag.
- `oscillation_freq_hz` — FFT peak of controller output in the **0.3–3 Hz**
  band on the longest engaged stretch (below 0.3 Hz is road curvature, not
  oscillation). The observed PSA limit cycle is ~1.2–1.5 Hz.
- `osc_torque_rms` — RMS of the output minus its 1 s rolling mean =
  oscillation *amplitude*. This is the number a fix should shrink.
- `by_speed_kmh` — same metrics split into 0–30 / 30–60 / 60+ km/h bins.
  **Compare within bins**: two drives with different speed mixes are not
  comparable on the totals.

**learning** (start → end of route; wiped by the reset-comma-learned-params skill)
- `live_delay_s` — lagd actuator-delay estimate; `status: unestimated`
  means it's still running on the offline `steerActuatorDelay`.
- `torqued.lat_accel_factor` / `friction`, `live_valid` — torqued fit.
- `live_params.angle_offset_deg` / `steer_ratio` / `stiffness_factor`.

**faults** — `steerFaultTemporary` event count, `steerFaultPermanent`.

## Caveats

- A route mixes roads, speeds and driver interventions: prefer several
  drives on the same road before/after a change, and the by-speed bins.
- Metrics only cover time with the torque controller active; a route with
  little engaged time (<100 samples) reports `tracking/oscillation: null`.
- Timestamps are aligned across topics by nearest-neighbour (~10 ms); fine
  for these statistics, not for phase/delay estimation.
