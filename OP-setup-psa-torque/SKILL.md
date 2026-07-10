---
name: OP-setup-psa-torque
description: Prepare Cristian's stable Peugeot 3008 workspace from current upstream master, point opendbc to the matching custom branch, and for Sunny point neural network data to Cristian's neural-network-data master branch. Use variant comma for psa-torque or sunny for psa-torque-sunny.
---

# Setup Peugeot 3008

Use the bundled stable Peugeot 3008 setup workflow.

## Parameters

- `comma`: use openpilot and opendbc branch `psa-torque`.
- `sunny`: use openpilot and opendbc branch `psa-torque-sunny`.

Default to `comma` only when the user does not specify a variant. Use the separate `OP-setup-psa-torque-testing` skill for testing branches.

## Workflow

1. Determine the requested variant: `comma` or `sunny`.
2. Resolve the directory containing this `SKILL.md`.
3. Run the bundled wrapper by absolute path: `scripts/setup_psa_torque.sh <variant>`.
4. Report the upstream master commit, opendbc pointer commit, Sunny neural-network-data pointer when applicable, and whether the workflow pushed the openpilot branch.

The wrapper recreates the mapped local openpilot folder every time. For `sunny` only, it points the existing `sunnypilot/neural_network_data` submodule to `cristianku/neural-network-data:master`. It does not alter the NNLC loader or copy model files. It does not commit inside opendbc and does not clone, update, stage, or commit panda.

After cloning the fresh upstream `master`, the wrapper edits `selfdrive/locationd/torqued.py` to add `'psa'` to the `ALLOWED_CARS` gate, so torqued (live `latAccelFactor`/friction learning) runs for the Peugeot 3008. Upstream master ships this list without PSA and the clone is recreated every run, so this patch is reapplied each time. The edit is idempotent (skipped if `psa` is already present) and is staged so it lands in the pushed branch commit.

For both variants, clone the current upstream `master` branch directly, recreate the custom branch from its exact HEAD, update `.gitmodules` to `cristianku/opendbc`, set the `opendbc_repo` gitlink to Cristian's matching opendbc branch commit, and push with `--force-with-lease`. Use `commaai/openpilot` for `comma` and `sunnypilot/sunnypilot` for `sunny`. Do not copy opendbc files into openpilot.

## Safety

- The mapped local openpilot directory is deleted and recreated.
- The workflow can rewrite `psa-torque` or `psa-torque-sunny` with `--force-with-lease`.
- Keep `opendbc_repo` as a submodule pointer (`160000 commit`), never a vendored directory.
- Keep `sunnypilot/neural_network_data` as a submodule pointer (`160000 commit`) and update it only for the `sunny` variant.
- Always use neural-network-data branch `master` for both Sunny stable and Sunny testing; do not create a separate testing branch.
- Stage only `.gitmodules`, `opendbc_repo`, `selfdrive/locationd/torqued.py` (the PSA `ALLOWED_CARS` patch), and `sunnypilot/neural_network_data` when applicable.
- Override the neural data source only with `NEURAL_NETWORK_DATA_REPO` or `NEURAL_NETWORK_DATA_BRANCH` when explicitly required.
- Stop and report the error if cloning, validation, or a protected push fails.
