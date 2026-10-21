---
name: OP-setup-psa-torque-speed
description: Use when publishing Cristian's Peugeot 3008 speed-limit work branch for Sunnypilot - the same setup as OP-setup-psa-torque-testing, but it publishes cristianku/openpilot:psa-torque-sunny-speed with opendbc_repo pointing to cristianku/opendbc:psa-torque-sunny-speed. First parameter sunny is required (comma is not implemented); second parameter nav-alpha (default), master, master=<commit> or release.
---

# OP Setup PSA Torque Speed

Publish the Sunnypilot speed branch. All the work is done by the `OP-setup-psa-torque-testing` setup; only the target branch changes.

## Parameters

- First parameter, required: `sunny` (alias `sunnypilot`). `comma` / `openpilot` stops with "non implementato": comma openpilot has no Speed Limit Assist.
- Second parameter: same as `OP-setup-psa-torque-testing` - `nav-alpha` (default, `cristianku/openpilot:sunny-nav-alpha`), `master` (`sunnypilot/sunnypilot:master`), `master=<commit>`, `release`.

Examples: `scripts/setup_psa_torque_speed.sh sunny`, `scripts/setup_psa_torque_speed.sh sunny master`.

## Help

For a request such as `$OP-setup-psa-torque-speed help`, or one only asking for parameters/examples, run the wrapper with `--help`, show its output, and stop. Do not run setup.

## Workflow

1. Resolve the directory containing this `SKILL.md`.
2. Run the wrapper by absolute path: `scripts/setup_psa_torque_speed.sh sunny [nav-alpha|master|master=<commit>|release]`.
3. The wrapper calls `OP-setup-psa-torque-testing/scripts/setup_psa_torque.sh sunny <source>` with `SUNNY_TARGET_BRANCH=psa-torque-sunny-speed` and `OPENDBC_SOURCE_BRANCH=psa-torque-sunny-testing`: same Nav2Pilot realign, torqued `ALLOWED_CARS` patch, extra model catalog, neural-network-data pointer and protected push as testing.
4. Report like `OP-setup-psa-torque-testing`, starting with `Commit da controllare sul comma: **<openpilot-commit-sha>**` and then `Branch da controllare sul comma: **psa-torque-sunny-speed**`, followed by source mode, upstream source commit, opendbc pointer commit and neural-network-data pointer.

## Branches

- opendbc work happens on `cristianku/opendbc:psa-torque-sunny-speed` (created from `psa-torque-sunny-testing`). Only committed and pushed opendbc changes end up in the pointer.
- The setup does not align `psa-torque-sunny-speed` with `psa-torque-sunny-testing`; it only points the openpilot branch to the current opendbc speed commit.
- If opendbc `psa-torque-sunny-speed` is missing, the setup creates it from `psa-torque-sunny-testing`.

## Safety

- The local folder `new_openpilot_psa_torque_sunny_speed` is deleted and recreated.
- The workflow can rewrite `cristianku/openpilot:psa-torque-sunny-speed` with `--force-with-lease`; it never touches `psa-torque-sunny-testing` or `psa-torque-sunny`.
- Any change to the testing setup (patches, pointers, nav realign) applies here too, because this skill reuses it.
- `NO_PUSH=true` builds and commits locally without pushing; `SKIP_NAV_UPDATE=true` uses `sunny-nav-alpha` as it is.
