---
name: OP-setup-psa-torque-testing
description: Use when preparing Cristian's Peugeot 3008 testing workspace for Sunnypilot or comma.ai (psa-torque-sunny-testing is the branch the comma runs) - on upstream master, an exact commit in its history or the latest GitHub Release, always with Nav2Pilot injected from its patch, after syncing the external branches listed in docs/external-branches.md.
---

# OP Setup PSA Torque Testing

Use the bundled Peugeot 3008 testing setup workflow.

## Parameters

- First parameter: `comma` / `openpilot` uses comma.ai and branch `psa-torque-testing`; `sunny` / `sunnypilot` uses Sunnypilot and branch `psa-torque-sunny-testing`. It defaults to `comma`.
<!-- [pinned source] - START -->
- Second parameter, the upstream base: `master` (default) uses official upstream master; `master=<commit>` uses that exact 7-40 character hexadecimal commit after verifying it belongs to the selected source branch history; `release` resolves the latest published GitHub Release tag. Nav2Pilot is injected on every base (see Source parameter). `nav-alpha` and `feature/nav-alpha` (Sunny only), the old names, are accepted and mean `master`.
<!-- [pinned source] - END -->

Examples: `scripts/setup_psa_torque.sh sunny` (master + Nav2Pilot), `scripts/setup_psa_torque.sh sunny master=de197ba6`, `scripts/setup_psa_torque.sh sunny release`, and `scripts/setup_psa_torque.sh openpilot master`. Use the separate `OP-setup-psa-torque` skill for stable branches.

`master=<commit>` identifies a commit from official upstream master, not a generated commit from `cristianku/openpilot`. For example, custom commit `4b34316` was generated from upstream Sunnypilot commit `de197ba6`, so use `master=de197ba6`. Pinning the upstream source does not pin Sunny neural data: every Sunny run still points `sunnypilot/neural_network_data` to the latest commit currently published on `cristianku/neural-network-data:master`.

<!-- [help] - START -->
## Help

For a request such as `$OP-setup-psa-torque-testing help`, or a request only asking for parameters/examples, run the bundled wrapper with `--help`, show its output, and stop. Do not run setup. The wrapper also accepts `help`, `-h`, and `<variant> --help`. Skill selection/autocomplete is controlled by the client; this help is displayed after submitting the request.
<!-- [help] - END -->

<!-- [nav source] - START -->
## Source parameter

The first parameter stays `comma` or `sunny`. The second parameter selects only the upstream base:

- `sunny master` (or just `sunny`): official `sunnypilot/sunnypilot:master`.
- `comma master` (or just `comma`): official `commaai/openpilot:master`.
- `master=<commit>`, `release`: as above, on the variant's upstream.

Nav2Pilot (setNavRoute waypoints, setMapboxToken: what the Android/iOS apps need) is **always injected** on that base from its canonical patch, `OP-apply-nav-alpha/patches/sunnypilot.patch` (Sunny) or `openpilot.patch` (comma), the same patch that builds `cristianku/openpilot:sunny-nav-alpha` / `nav-alpha`. It is applied with 3-way context and staged; if it no longer applies the setup stops without publishing (resolve with `OP-apply-nav-alpha`). A warning lists the upstream files the Nav2Pilot code copies (navd.py, tiles.py, rpc.py) when they changed since the patch was made. `SKIP_NAV=true` builds without Nav2Pilot. The setup no longer realigns or pushes the Nav2Pilot branches: keeping them current is part of step 0 below (`OP-update-sunny-nav-alpha`). Do not use `sunny-nav` as the first parameter.
<!-- [nav source] - END -->

## Workflow

0. Read `openpilot_scripts/docs/external-branches.md` and bring every external branch up to date first: the fork masters equal upstream (Cristian syncs them on GitHub), then each source's update skill when it is behind (Nav2Pilot, opendbc, neural-network-data, Distill, speed limits). Stop and report on a conflict.
1. Determine the requested variant: `comma` or `sunny`.
2. Resolve the directory containing this `SKILL.md`.
3. Run the bundled wrapper by absolute path: `scripts/setup_psa_torque.sh <variant> [master|master=<commit>|release|nav-alpha]`.
4. Report the pushed openpilot testing-branch commit SHA first (it is the commit Cristian sees on the comma after an update), then the source mode, resolved upstream source commit and release tag when applicable, opendbc pointer commit, Sunny neural-network-data pointer when applicable, and whether the workflow pushed the openpilot testing branch.

<!-- [branch display] - START -->
Start the final report with the openpilot commit as the very first line, prominently: `Commit da controllare sul comma: **<openpilot-commit-sha>**` using the full SHA of the commit the wrapper created on `cristianku/openpilot` and pushed with `--force-with-lease` (the commit that will show on the device after an update). Immediately after, report the branch: `Branch da controllare sul comma: **psa-torque-sunny-testing**` for Sunny, or `Branch da controllare sul comma: **psa-torque-testing**` for comma.ai. Always render the commit SHA and the exact target branch name in bold Markdown, so Cristian can easily compare them with the branch and commit displayed on the device. This identifies the prepared commit and branch; it does not claim the device has been updated.
<!-- [branch display] - END -->

The wrapper recreates the mapped local openpilot folder every time. For `sunny` only, it points the existing `sunnypilot/neural_network_data` submodule to `cristianku/neural-network-data:master`, which exposes the custom `neural_network_lateral_control/` data to Sunnypilot. This data pointer is the only Sunny NNLC customization: the wrapper does not alter the NNLC loader or controller runtime files and does not copy model files. It does not commit inside opendbc and does not clone, update, stage, or commit panda.

After cloning the selected upstream source, the wrapper edits `selfdrive/locationd/torqued.py` to add `'psa'` to the `ALLOWED_CARS` gate, so torqued (live `latAccelFactor`/friction learning) runs for the Peugeot 3008. The upstream source ships this list without PSA and the clone is recreated every run, so this patch is reapplied each time. The edit is idempotent (skipped if `psa` is already present) and is staged so it lands in the pushed testing branch commit.

Sunny variant only: the wrapper fetches the model-catalog changes from the canonical **`cristianku/sunnypilot:distilled`** branch and applies the three-file diff to the selected SunnyPilot/PSA/Nav2Pilot base. It makes Cristian's openpilot.distill models visible in the comma Models menu and in SunnyLink. There is **no separate local Distill patch**. On a conflict the setup stops without publishing; resolve the changes in the source or checkout, or explicitly use `SKIP_EXTRA_MODEL_CATALOG=true` to omit the feature. The source branch should first be synced with upstream using `OP-update-distilled`.

<!-- [speed limits] - START -->
Sunny variant only: the wrapper then applies the speed-limit work from **`cristianku/sunnypilot:speed-limits`**, the way the opendbc work comes from `cristianku/opendbc:psa-torque-sunny-testing`: every change of that branch since its merge-base with `sunnypilot/sunnypilot:master` (Speed Limit Source "Signs Read By" with the neural network as a reader, the `speedVisionSP` message, the resolver's `vision` source, the sunnylink setting, and the `openpilot/sunnypilot/speed_limits/models` submodule pointing to `cristianku/speed-limits-models`), applied with 3-way context and staged. Work on speed limits is committed and pushed to `speed-limits`; this setup only picks it up. It is skipped on a source without Speed Limit Assist (comma.ai) and when the checkout already has it. On a conflict the setup stops without publishing: merge sunnypilot master into `speed-limits` and resolve there, or use `SKIP_SPEED_LIMITS=true` to build without it. Overrides: `SPEED_LIMITS_SOURCE_REPO`, `SPEED_LIMITS_SOURCE_BRANCH`.
<!-- [speed limits] - END -->

For all variants, clone the configured upstream source directly, recreate the custom testing branch from its exact commit, update `.gitmodules` to `cristianku/opendbc`, set the `opendbc_repo` gitlink to Cristian's matching testing opendbc branch commit, and push with `--force-with-lease`. Default to the current selected source branch; with `master=<commit>`, verify and check out that commit from the selected source branch history; in release mode query GitHub's latest-release endpoint, verify the returned tag, and clone that tag. Do not copy opendbc files into openpilot.

## Safety

- The mapped local openpilot testing directory is deleted and recreated.
- The workflow can rewrite `psa-torque-testing` or `psa-torque-sunny-testing` with `--force-with-lease`.
- Keep `opendbc_repo` as a submodule pointer (`160000 commit`), never a vendored directory.
- Keep `sunnypilot/neural_network_data` as a submodule pointer (`160000 commit`) and update it only for the `sunny` variant.
- Always use neural-network-data branch `master` for both Sunny stable and Sunny testing; do not create a separate testing branch.
- Stop and report an error if GitHub does not return a release tag or if that tag is unavailable from the selected upstream.
<!-- [pinned source] - START -->
- Stop and report an error if a `master=<commit>` value is malformed, unavailable from the selected upstream, or outside the selected source branch history. Never treat a generated `cristianku/openpilot` commit as an upstream source commit.
<!-- [pinned source] - END -->
- Stage only `.gitmodules`, `opendbc_repo`, `selfdrive/locationd/torqued.py` (the PSA `ALLOWED_CARS` patch), and `sunnypilot/neural_network_data`, the extra model catalog files (`sunnypilot/models/extra_catalog.py`, `fetcher.py`, its test) and the files of `cristianku/sunnypilot:speed-limits` (with its `speed_limits/models` submodule pointer) when applicable.
- Override the neural data source only with `NEURAL_NETWORK_DATA_REPO` or `NEURAL_NETWORK_DATA_BRANCH` when explicitly required.
- Stop and report the error if cloning, validation, or a protected push fails.
