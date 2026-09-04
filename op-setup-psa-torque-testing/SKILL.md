---
name: op-setup-psa-torque-testing
description: Use when preparing Cristian's Peugeot 3008 testing workspace from the current upstream master, an exact commit in its history, or the latest GitHub Release, for either Sunnypilot or comma.ai.
---

# Setup Peugeot 3008 Testing

Use the bundled Peugeot 3008 testing setup workflow.

## Parameters

- First parameter: `comma` / `openpilot` uses comma.ai and branch `psa-torque-testing`; `sunny` / `sunnypilot` uses Sunnypilot and branch `psa-torque-sunny-testing`. It defaults to `comma`.
<!-- [pinned source] - START -->
- Second parameter: `master` uses the current upstream master branch; `master=<commit>` uses that exact 7-40 character hexadecimal commit after verifying it belongs to the selected upstream master history; `release` resolves the latest published GitHub Release tag. It defaults to `master`.
<!-- [pinned source] - END -->

Examples: `scripts/setup_psa_torque.sh sunny`, `scripts/setup_psa_torque.sh sunny master=de197ba6`, `scripts/setup_psa_torque.sh sunny release`, and `scripts/setup_psa_torque.sh openpilot master`. Use the separate `op-setup-psa-torque` skill for stable branches.

`master=<commit>` always identifies an official upstream commit, not a generated commit from `cristianku/openpilot`. For example, custom commit `4b34316` was generated from upstream Sunnypilot commit `de197ba6`, so use `master=de197ba6`. Pinning the upstream source does not pin Sunny neural data: every Sunny run still points `sunnypilot/neural_network_data` to the latest commit currently published on `cristianku/neural-network-data:master`.

## Workflow

1. Determine the requested variant: `comma` or `sunny`.
2. Resolve the directory containing this `SKILL.md`.
3. Run the bundled wrapper by absolute path: `scripts/setup_psa_torque.sh <variant> [master|master=<commit>|release]`.
4. Report the source mode, resolved upstream source commit and release tag when applicable, opendbc pointer commit, Sunny neural-network-data pointer when applicable, and whether the workflow pushed the openpilot testing branch.

The wrapper recreates the mapped local openpilot folder every time. For `sunny` only, it points the existing `sunnypilot/neural_network_data` submodule to `cristianku/neural-network-data:master`, which exposes the custom `neural_network_lateral_control/` data to Sunnypilot. This data pointer is the only Sunny NNLC customization: the wrapper does not alter the NNLC loader or controller runtime files and does not copy model files. It does not commit inside opendbc and does not clone, update, stage, or commit panda.

After cloning the selected upstream source, the wrapper edits `selfdrive/locationd/torqued.py` to add `'psa'` to the `ALLOWED_CARS` gate, so torqued (live `latAccelFactor`/friction learning) runs for the Peugeot 3008. The upstream source ships this list without PSA and the clone is recreated every run, so this patch is reapplied each time. The edit is idempotent (skipped if `psa` is already present) and is staged so it lands in the pushed testing branch commit.

For both variants, clone the configured upstream source directly, recreate the custom testing branch from its exact commit, update `.gitmodules` to `cristianku/opendbc`, set the `opendbc_repo` gitlink to Cristian's matching testing opendbc branch commit, and push with `--force-with-lease`. Default to current master; with `master=<commit>`, verify and check out that commit from the selected upstream master history; in release mode query GitHub's latest-release endpoint, verify the returned tag, and clone that tag. Do not copy opendbc files into openpilot.

## Safety

- The mapped local openpilot testing directory is deleted and recreated.
- The workflow can rewrite `psa-torque-testing` or `psa-torque-sunny-testing` with `--force-with-lease`.
- Keep `opendbc_repo` as a submodule pointer (`160000 commit`), never a vendored directory.
- Keep `sunnypilot/neural_network_data` as a submodule pointer (`160000 commit`) and update it only for the `sunny` variant.
- Always use neural-network-data branch `master` for both Sunny stable and Sunny testing; do not create a separate testing branch.
- Stop and report an error if GitHub does not return a release tag or if that tag is unavailable from the selected upstream.
<!-- [pinned source] - START -->
- Stop and report an error if a `master=<commit>` value is malformed, unavailable from the selected upstream, or outside its master history. Never treat a generated `cristianku/openpilot` commit as an upstream source commit.
<!-- [pinned source] - END -->
- Stage only `.gitmodules`, `opendbc_repo`, `selfdrive/locationd/torqued.py` (the PSA `ALLOWED_CARS` patch), and `sunnypilot/neural_network_data` when applicable.
- Override the neural data source only with `NEURAL_NETWORK_DATA_REPO` or `NEURAL_NETWORK_DATA_BRANCH` when explicitly required.
- Stop and report the error if cloning, validation, or a protected push fails.
