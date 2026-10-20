---
name: OP-setup-psa-torque-testing
description: Use when preparing Cristian's Peugeot 3008 testing workspace for Sunnypilot or comma.ai, by default from Cristian's Nav2Pilot branch (nav-alpha / sunny-nav-alpha, realigned to upstream master first), or from upstream master, an exact commit in its history, or the latest GitHub Release.
---

# OP Setup PSA Torque Testing

Use the bundled Peugeot 3008 testing setup workflow.

## Parameters

- First parameter: `comma` / `openpilot` uses comma.ai and branch `psa-torque-testing`; `sunny` / `sunnypilot` uses Sunnypilot and branch `psa-torque-sunny-testing`. It defaults to `comma`.
<!-- [pinned source] - START -->
- Second parameter: `nav-alpha` (default) uses Cristian's Nav2Pilot branch for the variant (upstream master + Nav2Pilot, on cristianku/openpilot); `master` uses official upstream master without Nav2Pilot; `master=<commit>` uses that exact 7-40 character hexadecimal commit after verifying it belongs to the selected source branch history; `release` resolves the latest published GitHub Release tag. It defaults to `nav-alpha`.
<!-- [pinned source] - END -->

Examples: `scripts/setup_psa_torque.sh sunny`, `scripts/setup_psa_torque.sh sunny master=de197ba6`, `scripts/setup_psa_torque.sh sunny release`, and `scripts/setup_psa_torque.sh openpilot master`. Use the separate `OP-setup-psa-torque` skill for stable branches.

`master=<commit>` identifies a commit from official upstream master, not a generated commit from `cristianku/openpilot`. For example, custom commit `4b34316` was generated from upstream Sunnypilot commit `de197ba6`, so use `master=de197ba6`. Pinning the upstream source does not pin Sunny neural data: every Sunny run still points `sunnypilot/neural_network_data` to the latest commit currently published on `cristianku/neural-network-data:master`.

<!-- [help] - START -->
## Help

For a request such as `$OP-setup-psa-torque-testing help`, or a request only asking for parameters/examples, run the bundled wrapper with `--help`, show its output, and stop. Do not run setup. The wrapper also accepts `help`, `-h`, and `<variant> --help`. Skill selection/autocomplete is controlled by the client; this help is displayed after submitting the request.
<!-- [help] - END -->

<!-- [nav source] - START -->
## Source parameter

The first parameter stays `comma` or `sunny`. The second parameter selects the source:

- `sunny master`: official `sunnypilot/sunnypilot:master`.
- `sunny nav-alpha` (or just `sunny`): `cristianku/openpilot:sunny-nav-alpha` (sunnypilot master + Nav2Pilot).
- `sunny feature/nav-alpha`: old name, same source (`nav-alpha`).
- `comma master`: official `commaai/openpilot:master`.
- `comma nav-alpha` (or just `comma`): `cristianku/openpilot:nav-alpha` (comma master + Nav2Pilot).

`nav-alpha` works with both `comma` and `sunny`, including aliases `openpilot` and `sunnypilot`. `feature/nav-alpha` is accepted for Sunny only, as the old name of `nav-alpha`. Keep the same target branch, local folder and submodule rules as the selected variant: `psa-torque-testing` for comma, `psa-torque-sunny-testing` for Sunny, with custom neural data only for Sunny. `nav-alpha` is a source branch, never the publication target. Only committed changes published to the selected remote source are included; uncommitted or unpushed local changes are not copied. Do not use `sunny-nav` as the first parameter.

With `nav-alpha` the wrapper first realigns the Nav2Pilot branch to the latest upstream master with `openpilot_scripts/scripts/update_fork_branch.sh` (the `OP-update-nav-alpha` / `OP-update-sunny-nav-alpha` skills): it pushes only when the branch is behind. If the Nav2Pilot patch no longer applies the setup stops: resolve with `OP-apply-nav-alpha`, or rerun with `master` (no Nav2Pilot) or `SKIP_NAV_UPDATE=true` (uses the branch as it is).

Example requests: `$OP-setup-psa-torque-testing comma nav-alpha` or `$OP-setup-psa-torque-testing sunny nav-alpha`. Pass both positional parameters to the wrapper: `bash scripts/setup_psa_torque.sh comma nav-alpha` or `bash scripts/setup_psa_torque.sh sunny nav-alpha`.
<!-- [nav source] - END -->

## Workflow

1. Determine the requested variant: `comma` or `sunny`.
2. Resolve the directory containing this `SKILL.md`.
3. Run the bundled wrapper by absolute path: `scripts/setup_psa_torque.sh <variant> [master|master=<commit>|release|nav-alpha]`.
4. Report the pushed openpilot testing-branch commit SHA first (it is the commit Cristian sees on the comma after an update), then the source mode, resolved upstream source commit and release tag when applicable, opendbc pointer commit, Sunny neural-network-data pointer when applicable, and whether the workflow pushed the openpilot testing branch.

<!-- [branch display] - START -->
Start the final report with the openpilot commit as the very first line, prominently: `Commit da controllare sul comma: **<openpilot-commit-sha>**` using the full SHA of the commit the wrapper created on `cristianku/openpilot` and pushed with `--force-with-lease` (the commit that will show on the device after an update). Immediately after, report the branch: `Branch da controllare sul comma: **psa-torque-sunny-testing**` for Sunny, or `Branch da controllare sul comma: **psa-torque-testing**` for comma.ai. Always render the commit SHA and the exact target branch name in bold Markdown, so Cristian can easily compare them with the branch and commit displayed on the device. This identifies the prepared commit and branch; it does not claim the device has been updated.
<!-- [branch display] - END -->

The wrapper recreates the mapped local openpilot folder every time. For `sunny` only, it points the existing `sunnypilot/neural_network_data` submodule to `cristianku/neural-network-data:master`, which exposes the custom `neural_network_lateral_control/` data to Sunnypilot. This data pointer is the only Sunny NNLC customization: the wrapper does not alter the NNLC loader or controller runtime files and does not copy model files. It does not commit inside opendbc and does not clone, update, stage, or commit panda.

After cloning the selected upstream source, the wrapper edits `selfdrive/locationd/torqued.py` to add `'psa'` to the `ALLOWED_CARS` gate, so torqued (live `latAccelFactor`/friction learning) runs for the Peugeot 3008. The upstream source ships this list without PSA and the clone is recreated every run, so this patch is reapplied each time. The edit is idempotent (skipped if `psa` is already present) and is staged so it lands in the pushed testing branch commit.

Sunny variant only: the wrapper also applies `patches/sunnypilot-extra-model-catalog.patch`, so the sunnypilot Models menu on the comma (and the sunnylink model list) also shows Cristian's openpilot.distill models published on Hugging Face (`cristianku/openpilot-distill-models`, folder "Distill cristianku"). It adds `openpilot/sunnypilot/models/extra_catalog.py`, merges that catalog into the qcom one in `fetcher.py`, and leaves only the chestnut url in `ModelManager_ActiveJson` so sunnylink reads the small models from the device cache. comma openpilot has no Models menu, so nothing is applied there. If sunnypilot changes `openpilot/sunnypilot/models` and the patch no longer applies, the setup stops with an error: update the patch, or rerun with `SKIP_EXTRA_MODEL_CATALOG=true`.

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
- Stage only `.gitmodules`, `opendbc_repo`, `selfdrive/locationd/torqued.py` (the PSA `ALLOWED_CARS` patch), and `sunnypilot/neural_network_data` and the extra model catalog files (`sunnypilot/models/extra_catalog.py`, `fetcher.py`, its test) when applicable.
- Override the neural data source only with `NEURAL_NETWORK_DATA_REPO` or `NEURAL_NETWORK_DATA_BRANCH` when explicitly required.
- Stop and report the error if cloning, validation, or a protected push fails.
