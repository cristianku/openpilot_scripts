# Longitudinal investigation: findings

Notes moved here on 2026-10-20 from the psa-longitudinal-engineer agent memory (written 2026-10-18).

## Findings (traffic lights / roundabouts, 2026-10-17)
Investigation of premature braking at traffic lights/roundabouts (2026-10-17), tooling in
openpilot_scripts/log_analysis/longitudinal_investigation/ (outputs in out/, gitignored).

- Brake gain actually applied, measured from CAN 0x2B6 vs carControl.accel: ~1.0 on routes up to
  0000007d (Sept), ~1.5 (1.55 minus filter) from 000000b8 on, incl. all 14-16 Oct routes
  (openpilot commits fb1c36569, a8b556a07 — not present in the local openpilot checkout).
- Vehicle brake ECU tracks MDD_DESIRED_DECELERATION within ~0.1 m/s^2 (layer F is fine) ->
  with 1.55 the measured decel is ~1.4x the openpilot request; LongControl kiV=[0] (pure FF).
- DEC (DynamicExperimentalControl) was active in every route (build predates sunnypilot 5ec0c0219
  "Sunset DEC", 2026-10-16): e2e candidate only in 'blended'; ~2.4 switches per engaged minute.
- radarUnavailable=True: all leads are vision; MPC STOP_DISTANCE 6 m -> median standstill gap ~5.5 m.
- No fcamera/qcamera anywhere locally (all downloads --no-video): video evidence must be fetched by Cristian.
- Overpass: overpass-api.de needs a User-Agent (406 without), often 502 under load; mail.ru mirror times out.

**Why:** these are expensive to re-derive and drive any future brake-LUT/hysteresis calibration.
**How to apply:** do not re-measure the gain regime; reuse extract.py timelines; treat 1.0-vs-1.55 route
comparisons as confounded by different models (OP10, RDF, RDF V2) and SCC settings.

## Log parsing traps
- cereal schema in this sunnypilot checkout: new_openpilot_psa_torque_sunny_testing/openpilot/cereal
  (commaai layout under openpilot/); car.capnp must be staged next to log.capnp (see common.py in
  openpilot_scripts/log_analysis/longitudinal_investigation/). Run with `uv run` (PEP 723 headers).
- Logs live in several trees: comma_logs/, log_analysis/drive_logs/<date>/, log_analysis/*_2026*/ —
  walk with rglob("rlog.zst"); some copies are truncated (000000b8--26 in longitudinal_noise_20261001).
- initData is repeated in every segment with the route-start logMonoTime: do not use it as segment t0.
- Our 0x2B6 is sendcan src=1 (PSA_ADAS_BUS); its echo is can src=129.
- longitudinalPlanSP.deprecated.dec.{state,active} still readable with the post-sunset schema.
- Video sync key: narrowRoadEncodeIdx.segmentNum/segmentId by timestampSof (fcamera, 20 fps).
