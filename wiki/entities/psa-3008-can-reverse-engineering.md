---
title: "3008 CAN reverse-engineering notes (beyond the DBC)"
type: entity
repos: [opendbc]
platform: CAR.PSA_PEUGEOT_3008
sources: [opendbc/opendbc/dbc/psa_aee2010_r3.dbc]
updated: 2026-07-02
---

# 3008 CAN reverse-engineering notes (beyond the DBC)

Findings from analyzing device rlogs (`can` events, buses 0/1/2 as seen by the comma harness) that are **not** in `psa_aee2010_r3.dbc`, or correct/extend it. Grounded in the drives of 2026-07-02 (dongle `6616faac453a3064`). Method for the TSR hunt: two independent, video-confirmed 60 km/h sign passages (route `00000019--131cf7274b` seg 3 t≈44.5 s; route `00000022--b31b936f36` seg 2 t≈14–16 s) used as ground-truth events; scanned all buses at byte level, bit level, sliding 4/6/8-bit fields, mux-aware (byte0 selector), plus burst/new-ID detection around the events.

## Main negative result: recognized speed limit is NOT on the tapped buses

The "60" shown in the cluster after a sign is recognized appears **nowhere** on buses 0/1/2: no field changes at both events and no field settles to a common encoding after them (same sign = same value constraint). Everything that correlated in time turned out to be ACC state, vehicle dynamics, or engine (see table).

Interpretation: on the 3008 the displayed limit (likely camera+nav fusion in NAC/BSI) travels on the IS/infotainment CAN behind the BSI, which does not pass through the ADAS-camera connector where the harness sits. **To capture it**: sniff another access point (OBD gateway, cluster connector) with a separate CAN logger during a sign passage. Until then, `carStateSP.speedLimit` cannot be fed from CAN and SLC stays map-only on this car (see [../concepts/longitudinal-control.md](../concepts/longitudinal-control.md), SLC section).

## Decoded / characterized messages

| ID | Bus seen | DBC status | Finding |
| --- | --- | --- | --- |
| `0x3F2` (1010) | 2 (rx) | `LANE_KEEP_ASSIST` | **Stock camera's own LKA command** observed live (the port TX's its replacement on bus 0; panda blocks forwarding). `TORQUE` = 11-bit signed, sweeps smoothly (±450 raw in a roundabout). DBC-position `TORQUE_FACTOR` (byte5) stayed **0** the whole time; `unknown2` (byte2) is the active gain-like signal: **ramps 0→100 in ~15 s at startup** (even standing still), 100 at cruise, 9–34 in slow city traffic, always slew-limited ~2–3/frame. The port sends `unknown2=24` fixed — semantics worth investigating (authority %? lane quality?). |
| `0x452` (1106) byte1 | 1 | `HS2_DAT_MDD_CMD_452.SPEED_SETPOINT` | Confirmed km/h, but it **tracks current vehicle speed while ACC is not engaged** (pre-arm display), `0xFF` = unavailable. Not a TSR value. |
| `0x50E` (1294) | 2 (rx) | not in DBC | ACC HMI mirror on the camera bus: byte6 = copy of `0x452` SPEED_SETPOINT (same values/timing), byte0 = flag set (0x02/0x12/0x22/0x32 availability states), byte7 = counter/checksum. |
| `0x2E8` (744) byte3 bits 5–6 | 0 | not in DBC | ACC availability/status flags; toggle with `0x452`/`0x50E` transitions. |
| `0x48E` (1166) byte0 | 2 | not in DBC | Vehicle speed in km/h (integer), camera-side. |
| `0x54E` (1358) byte6 | 2 | not in DBC | Also vehicle speed km/h (1 Hz status). |
| `0x552` (1362) byte6 | 1, 2 | not in DBC | **Odometer**, +1 per km. bytes2–3 also count (finer distance units). |
| `0x2D8` (728) | 1 | `NEW_MSG_2D8` | Continuous signed measurements (bytes1–2 wobble ~0x3E80–0x4080, bytes3–4 slow ramp) — inclinometer/dynamics-like, not TSR. |
| `0x4F6` (1270) | 1 | `HS2_DAT_ARTIV_V2_4F6` | Radar target dynamics (smooth distance/speed-like ramps at 10 Hz), despite the `DAT` name. |
| `0x40D` (1037), `0x50D` (1293), `0x38D` (909), `0x488` (1160) | 0/1 | partly in DBC (ABR/CMM) | Brake/engine dynamic fields — frequent false positives in event-correlation scans (they co-vary with braking near signs). |
| `0x348` (840) byte6 bit4 | 0 | `Dyn2_CMM.P370_Com_bWUC` | Engine warm-up-cycle flag; flipped once mid-drive — classic decoy in change-detection scans. |
| `0x492/0x4B2/0x4D2` | 2 (rx) | not in DBC | ASCII VIN broadcast fragments (`VF3…`, 1 Hz) on the camera-side bus (ECU provisioning). |

## Bus-direction observations (open question)

- Frames **received on bus 2** include both camera-origin traffic (`0x3F2` stock LKA, `0x50E`) and BSI-ish broadcasts (VIN, odometer `0x552`, body data parsed by `carstate` from `Bus.cam`) — so bus 2 is not a pure "camera TX only" segment; the camera connector likely carries a second CAN where BSI and camera both talk. Topology not fully mapped; treat per-message directions above as observations, not a wiring diagram.
- Bus 1 rx is dominated by ARTIV (radar/MDD) transmissions: `0x2B6`, `0x2F6`, plus undocumented `0x212`, `0x2B2`, `0x2F8`, `0x318`, `0x408` (all fast dynamic data, undecoded).
- Bus 0 rx (~38 IDs) is a gateway-filtered subset, not the full body/HS2 bus — another reason cluster/display traffic is invisible here.

## Related

- Oscillation analysis that spawned this work: [psa-3008-torque-oscillation-2026-07.md](psa-3008-torque-oscillation-2026-07.md)
- Port reference: [psa-peugeot-3008.md](psa-peugeot-3008.md)
