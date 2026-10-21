---
# [skill] - START
name: OP-setup-psa-torque
description: Use when preparing Cristian's stable Peugeot 3008 workspace on branch psa-torque or psa-torque-sunny, by default from his comma/Sunny Nav2Pilot branch (nav-alpha / sunny-nav-alpha, realigned to upstream master first), or from upstream master or the latest GitHub Release, rather than a testing branch.
# [skill] - END
---

# OP Setup PSA Torque

Use the bundled stable Peugeot 3008 setup workflow.

## Parameters

- First parameter: `comma` / `openpilot` uses comma.ai and branch `psa-torque`; `sunny` / `sunnypilot` uses Sunnypilot and branch `psa-torque-sunny`. It defaults to `comma`.
<!-- [nav source] - START -->
- Second parameter: `nav-alpha` (default) uses Cristian's Nav2Pilot branch for the selected variant (upstream master + Nav2Pilot, on cristianku/openpilot); `master` uses the upstream master branch without Nav2Pilot; `release` resolves the latest published GitHub Release tag for that upstream. It defaults to `nav-alpha`.
<!-- [nav source] - END -->

Examples: `scripts/setup_psa_torque.sh sunny`, `scripts/setup_psa_torque.sh sunny release`, and `scripts/setup_psa_torque.sh openpilot master`. Use the separate `OP-setup-psa-torque-testing` skill for testing branches.

<!-- [nav source] - START -->
## Source parameter

- `comma master`: official `commaai/openpilot:master`.
- `comma nav-alpha` (or just `comma`): `cristianku/openpilot:nav-alpha` (comma master + Nav2Pilot).
- `sunny master`: official `sunnypilot/sunnypilot:master`.
- `sunny nav-alpha` (or just `sunny`, or the old name `sunny feature/nav-alpha`): `cristianku/openpilot:sunny-nav-alpha` (sunnypilot master + Nav2Pilot).

Aliases: `openpilot` = `comma`; `sunnypilot` = `sunny`. The source selection keeps the mapped target branch, local folder and submodule rules: `psa-torque` for comma, `psa-torque-sunny` for Sunny. `nav-alpha` is a source branch, never the publication target. Only committed changes published to the selected remote source are included; uncommitted or unpushed local changes are not copied.

With `nav-alpha` the wrapper first realigns the Nav2Pilot branch to the latest upstream master with `openpilot_scripts/scripts/update_fork_branch.sh` (the `OP-update-nav-alpha` / `OP-update-sunny-nav-alpha` skills): it pushes only when the branch is behind. If the Nav2Pilot patch no longer applies the setup stops: resolve with `OP-apply-nav-alpha`, or rerun with `master` (no Nav2Pilot) or `SKIP_NAV_UPDATE=true` (uses the branch as it is).

Example request: `$OP-setup-psa-torque comma nav-alpha`. Pass both positional parameters to the wrapper: `bash scripts/setup_psa_torque.sh comma nav-alpha`.
<!-- [nav source] - END -->

## Workflow

1. Determine the requested variant: `comma` or `sunny`.
2. Resolve the directory containing this `SKILL.md`.
<!-- [nav source] - START -->
3. Run the bundled wrapper with `bash` and its absolute path: `bash scripts/setup_psa_torque.sh <variant> [master|release|nav-alpha]`.
<!-- [nav source] - END -->
<!-- [skill] - START -->
4. Report the source mode, resolved upstream source commit and release tag when applicable, opendbc pointer commit, Sunny neural-network-data pointer when applicable, and whether the workflow pushed the openpilot stable branch.
<!-- [skill] - END -->

The wrapper recreates the mapped local openpilot folder every time. For `sunny` only, it points the existing `sunnypilot/neural_network_data` submodule to `cristianku/neural-network-data:master`, which exposes the custom `neural_network_lateral_control/` data to Sunnypilot. This data pointer is the only Sunny NNLC customization: the wrapper does not alter the NNLC loader or controller runtime files and does not copy model files. It does not commit inside opendbc and does not clone, update, stage, or commit panda.

<!-- [skill] - START -->
After cloning the selected upstream source, the wrapper edits `selfdrive/locationd/torqued.py` to add `'psa'` to the `ALLOWED_CARS` gate, so torqued (live `latAccelFactor`/friction learning) runs for the Peugeot 3008. The upstream source ships this list without PSA and the clone is recreated every run, so this patch is reapplied each time. The edit is idempotent (skipped if `psa` is already present) and is staged so it lands in the pushed branch commit.

Sunny variant only: the wrapper fetches the model-catalog changes from the canonical **`cristianku/sunnypilot:distilled`** branch and applies the three-file diff to the selected SunnyPilot/PSA/Nav2Pilot base. It makes Cristian's openpilot.distill models visible in the comma Models menu and in SunnyLink. There is **no separate local Distill patch**. On a conflict the setup stops without publishing; resolve the changes in the source or checkout, or explicitly use `SKIP_EXTRA_MODEL_CATALOG=true` to omit the feature. The source branch should first be synced with upstream using `OP-update-distilled`.

For both variants, clone the configured upstream source directly, recreate the custom stable branch from its exact commit, update `.gitmodules` to `cristianku/opendbc`, set the `opendbc_repo` gitlink to Cristian's matching stable opendbc branch commit, and push with `--force-with-lease`. Default to master; `nav-alpha` selects Cristian's navigation branch for the variant; in release mode query GitHub's latest-release endpoint, verify the returned tag, and clone that tag. Do not copy opendbc files into openpilot.
<!-- [skill] - END -->

## Safety

- The mapped local openpilot directory is deleted and recreated.
- The workflow can rewrite `psa-torque` or `psa-torque-sunny` with `--force-with-lease`.
- Keep `opendbc_repo` as a submodule pointer (`160000 commit`), never a vendored directory.
- Keep `sunnypilot/neural_network_data` as a submodule pointer (`160000 commit`) and update it only for the `sunny` variant.
- Always use neural-network-data branch `master` for both Sunny stable and Sunny testing; do not create a separate testing branch.
- Stop and report an error if GitHub does not return a release tag or if that tag is unavailable from the selected upstream.
- Stage only `.gitmodules`, `opendbc_repo`, `selfdrive/locationd/torqued.py` (the PSA `ALLOWED_CARS` patch), and `sunnypilot/neural_network_data` and the extra model catalog files (`sunnypilot/models/extra_catalog.py`, `fetcher.py`, its test) when applicable.
- Override the neural data source only with `NEURAL_NETWORK_DATA_REPO` or `NEURAL_NETWORK_DATA_BRANCH` when explicitly required.
- Stop and report the error if cloning, validation, or a protected push fails.
