---
name: psa-long-findings-2026-10-17
description: Confirmed PSA long facts from routes 00000118/00000119 (2026-10-17) - brake lag, shortfall, model behaviour at STOP/roundabouts, log/video sync traps
metadata:
  type: project
---

Routes 00000118--067193060f and 00000119--090c17ffa0 (2026-10-17) ran openpilot 85530a0a -> opendbc 0b0890a47 (identity BRAKE_ACCEL table, BRAKE_FILTER_RC 0.2, CP.longitudinalActuatorDelay 0.15), model "RDF Model V2 (Aug 11 2026)", Experimental, personality aggressive, SCC vision/map off, SLA mode 3 never the active source.

- The command->aEgo lag in brake mode is about 0.6-0.7 s (about 0.2 s of it is the opendbc brake filter). Steady-state aEgo is about 90% of the command (-1.33 vs -1.48). There was no clip at -2.0 in any event.
- None of the 12 driver brake overrides were caused by the car. Every one was a model/planner decision: a rolling STOP at about 5 km/h, roundabout entry at 22-38 km/h, or late slowing after a tunnel exit or in turns.
- `modelV2.action.shouldStop` = vEgo<0.3 and a<0.1 (sunnypilot modeld_v2). It is NOT a stop intent signal. Use min of predicted velocity instead.
- Video sync: qcamera frame n sof = 0.05*n - 0.33 s relative to the segment's first log msg (`qNarrowRoadEncodeIdx`). The device is a mici with an os04c10 sensor. qcam 526x330 is scaled non-uniformly from 1344x760 (fy about 496 px).
- The 0x32D ACCEL_LONGI_CALIB signal includes gravity (accelerometer). Do not compare it directly with aEgo on slopes.

**Why:** Cristian asked whether to retune PSA brakes. The evidence shows the planner is the problem, not the brake actuation.
**How to apply:** Check the planner/model first for "not braking enough" complaints. The only opendbc levers are lag (longitudinalActuatorDelay, BRAKE_FILTER_RC) and the 10% gain shortfall. Their effect is a few km/h or metres.
