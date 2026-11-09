---
name: OP-setup-smartspeed
description: Use when Cristian asks to build or refresh cristianku/openpilot:smartspeed, the sunnypilot handed to other people today - sunnypilot master plus only the road recording at full resolution (the one commit of cristianku/sunnypilot:full-res-record), no Smartspeed, no Nav2Pilot, nothing of the Peugeot.
---

# OP Setup Smartspeed

Builds `cristianku/openpilot:smartspeed`: a sunnypilot for someone else's comma that can record the road camera at the
sensor's full resolution (2688 x 1520 on an OS04C10, instead of 1344 x 760), so their drives can feed the sign reader at
full definition. Smartspeed itself is not handed out yet: none of the speed-limit work is in it.

## What goes in

- The base: `sunnypilot/sunnypilot:master` (default), `master=<commit>` (a commit of that master) or `release` (the latest
  GitHub Release).
- The one commit of `cristianku/sunnypilot:full-res-record`: the Developer switch `RecordRoadFullResolution` ("record road
  at full resolution", comma 4, comma 3X and sunnylink, offroad only, off by default), camerad's full road stream
  (`VISION_STREAM_NARROW_ROAD_FULL`, through the BPS), encoderd and loggerd writing `fcamera.hevc` from it.

Left out: Smartspeed, speedvisiond and the models submodule, Nav2Pilot, the PSA opendbc pointer, the Peugeot NNLC data,
the torqued `psa` patch and the Distill model catalog.

## Run

```bash
scripts/setup_smartspeed.sh            # master
scripts/setup_smartspeed.sh master=<commit>
scripts/setup_smartspeed.sh release
scripts/setup_smartspeed.sh --help     # runs nothing
```

It uses the testing setup's common script (`OP-setup-psa-torque-testing/scripts/setup_psa_torque_common.sh`). Its
speed-limits step, pointed at `full-res-record` (`SPEED_LIMITS_SOURCE_BRANCH`), applies that branch's change over
sunnypilot master with `git apply --3way`, so its log says "speed limits" for it. With `NAV2PILOT_BRANCH` empty it prints
"SKIP_NAV set". It deletes and recreates its local checkout and force-pushes `smartspeed` with `--force-with-lease`.
`NO_PUSH=true` is a dry run.

`full-res-record` is one commit on sunnypilot master. When it conflicts with a newer master, move it there (cherry-pick,
resolve, `git push --force-with-lease`) and run this again. Changes to the recording are `git commit --amend` on that
branch, never a copy here.

## On the car

Install with the custom software URL `installer.comma.ai/cristianku/smartspeed` (Settings, Software, Uninstall, then the
URL). It builds on the device on first boot. Then Settings, Developer, "record road at full resolution" on, and reboot:
camerad and encoderd read the switch at start. `fcamera.hevc` is then 2688 x 1520 at the same bitrate; qcamera stays
small. Off and reboot gives the stock recording back.

camerad's full-resolution path (the road through the BPS) has never run on a comma: it compiles and the setup's dry run
passes, but whether the BPS writes real pixels to the full stream is proven only on a device.

Report the pushed commit SHA of `smartspeed` first.
