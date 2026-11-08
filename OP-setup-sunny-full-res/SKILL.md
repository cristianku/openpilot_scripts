---
name: OP-setup-sunny-full-res
description: Use when Cristian asks to build or refresh the sunnypilot branch for other people's cars that records the road camera at full resolution (cristianku/openpilot:sunny-full-res) - sunnypilot master, Nav2Pilot and the speed-limit work, nothing of the Peugeot.
---

# OP Setup Sunny Full Res

Builds `cristianku/openpilot:sunny-full-res`: a sunnypilot for someone else's comma that records the road camera at the
sensor's full resolution (2688 x 1520 on an OS04C10, instead of 1928 x 1208), so their drives can feed the sign reader at
full definition.

## What goes in

- The base: `sunnypilot/sunnypilot:master` (default), `master=<commit>` (a commit of that master) or `release` (the latest
  GitHub Release).
- Nav2Pilot (setNavRoute waypoints, setMapboxToken) from its one commit on `cristianku/openpilot:sunny-nav-alpha`, as the
  testing setup injects it. `SKIP_NAV=true` builds without it.
- Everything `cristianku/sunnypilot:speed-limits` changes since its merge-base with sunnypilot master. It carries the
  Developer switch `RecordRoadFullResolution` ("record road at full resolution"), camerad's full road stream
  (`VISION_STREAM_NARROW_ROAD_FULL`) and the rest of the speed-limit work (Smartspeed, speedvisiond, the models submodule),
  all off until switched on.

Left out: the PSA opendbc pointer (opendbc_repo stays upstream's), the Peugeot NNLC data, the torqued `psa` patch and the
Distill model catalog.

## Run

```bash
scripts/setup_sunny_full_res.sh            # master
scripts/setup_sunny_full_res.sh master=<commit>
scripts/setup_sunny_full_res.sh release
scripts/setup_sunny_full_res.sh --help     # runs nothing
```

It uses the testing setup's common script (`OP-setup-psa-torque-testing/scripts/setup_psa_torque_common.sh`, with
`SKIP_OPENDBC`, `SKIP_PSA_TORQUED`, `SKIP_EXTRA_MODEL_CATALOG`), so the code lives in one place. Before a run, bring
sunny-nav-alpha and speed-limits up to date as `docs/external-branches.md` says. It deletes and recreates its local
checkout and force-pushes `sunny-full-res` with `--force-with-lease`. `NO_PUSH=true` is a dry run.

## On the car

Install with the custom software URL `installer.comma.ai/cristianku/sunny-full-res` (Settings, Software, Uninstall, then
the URL). It builds on the device on first boot. Then Settings, Developer, "record road at full resolution" on, and
reboot: camerad and loggerd read the switch at start. `fcamera.hevc` is then 2688 x 1520 at the same bitrate; qcamera stays
small. Off and reboot gives the stock recording back.

camerad's full-resolution path (the road through the BPS) has never run on a comma: it compiles and the setup's dry run
passes, but whether the BPS writes real pixels to the full stream is proven only on a device.

Report the pushed commit SHA of `sunny-full-res` first.
