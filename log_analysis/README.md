# log_analysis

Scripts to judge how the PSA (Peugeot 3008) lateral port is behaving from
drive logs, and to A/B compare tuning changes. Written to be driven by a
human **or an LLM agent**: stable CLI, stable metric keys, `--json` output.

## Workflow

```bash
# 1. pull logs from the device (skill: OP-download-comma-logs)
~/.claude/skills/OP-download-comma-logs/scripts/download_logs.sh --last --no-video
#    ...or one specific route:
~/.claude/skills/OP-download-comma-logs/scripts/download_logs.sh --route <route> --no-video

# 2. convert to CSV (skill: OP-comma-logs-to-csv)
uv run ~/.claude/skills/OP-comma-logs-to-csv/scripts/log_to_csv.py --last \
  --types carState,carControl,controlsState,liveParameters,liveTorqueParameters,liveDelay

# 3. analyze (this folder; uv provides pandas/numpy automatically)
uv run route_report.py --last            # single-route report
uv run route_report.py --last --json     # same, machine-readable
uv run route_report.py --list            # locally available routes
uv run compare_routes.py <routeA> <routeB> [--json]   # A/B after a tuning change
uv run torque_clamp_check.py             # is torqued clipped by override.toml?

# 4. raw-CAN analysis of the EPS handshake (skips step 2, reads rlog directly)
uv run psa_eps_timeline.py <route>              # duty cycle + every dropout
uv run psa_eps_timeline.py <route> --timeline   # one line per state change
```

`torque_clamp_check.py` compares the learned latAccelFactor (device cache +
route logs) against the offline override.toml — both the local checkout and
the toml **deployed on the device** (the clamp is ±30% of the deployed value,
`FACTOR_SANITY` in torqued.py). It prints a verdict with the recommended
LAT_ACCEL_FACTOR and flags local-vs-deployed mismatches.

## psa_eps_timeline.py — the EPS activation ladder (raw CAN)

The PSA EPS handshake lives on CAN, not in cereal, so the CSV export cannot
show it. This script reads `rlog.zst` directly and lines up our request
against the EPS answer:

| column | source | meaning |
|---|---|---|
| `req` | `sendcan` src 0, `0x3F2` LANE_KEEP_ASSIST `STATUS` | what **we** ask: 0 UNAVAILABLE, 1 UNSELECTED, 2 READY, 3 AUTHORIZED, 4 ACTIVE |
| `eps` | `can` src 0, `0x495` IS_DAT_DIRA `EPS_STATE_LKA` | what the **EPS** answers: 0 Unauthorised, 1 Authorised, 2 Available, 3 Active, 4 Defect |
| `fct` / `trq` | LANE_KEEP_ASSIST `TORQUE_FACTOR` / `TORQUE` | the two signals the EPS multiplies (`trq * fct/100`) |
| `lat` / `prs` | `carControl.latActive` / `carState.steeringPressed` | engaged, driver on the wheel |

Steering is only real when `eps == 3`. The `--gaps` view (default) reports the
**duty cycle** — how much of the engaged time actually had the EPS Active —
and every dropout, classified by cause:

- **rearm forzato** — `req` went to 1 first, i.e. *we* dropped the EPS on
  purpose (`EPS_REARM_PERIOD` in `psa/values.py`).
- **EPS ha mollato da solo** — `req` was still 2/4 when `eps` fell: the EPS
  disengaged by itself, usually on driver torque.

Two gotchas that cost time every single time — they are handled in the script,
don't re-derive them:

- **cereal won't load out of the box.** `log.capnp` still does
  `import "car.capnp"`, but `car.capnp` now lives in
  `opendbc/opendbc/car/car.capnp`; a plain `capnp.load()` dies with
  `Import failed: car.capnp` (the error misleadingly points at `safetyModel`).
  `staged_cereal()` builds a temp dir of symlinks putting them side by side.
- **cabana bus numbers.** In cabana, `128:3F2` means "openpilot sent this on
  bus 0" (`src = 128 + bus` for messages out of `sendcan`). In the log it is
  `sendcan` with `src == 0`. Received messages keep their real bus (`0:495`).

Everything else reads the CSVs under `comma_logs/csv/<route>/` (env override:
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
