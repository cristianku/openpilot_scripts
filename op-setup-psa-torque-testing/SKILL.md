---
name: op-setup-psa-torque-testing
description: Prepare Cristian's Peugeot 3008 testing workspace from the chosen upstream master or its latest GitHub Release, point opendbc to the matching custom testing branch, and for Sunny point neural network data to Cristian's neural-network-data master branch. Use sunny or sunnypilot for Sunnypilot, comma or openpilot for comma.ai, and optionally master or release as the source mode.
---

# Setup Peugeot 3008 Testing

Use the bundled Peugeot 3008 testing setup workflow.

## Parameters

- First parameter: `comma` / `openpilot` uses comma.ai and branch `psa-torque-testing`; `sunny` / `sunnypilot` uses Sunnypilot and branch `psa-torque-sunny-testing`. It defaults to `comma`.
- Second parameter: `master` uses the upstream master branch; `release` resolves the latest published GitHub Release tag for that upstream. It defaults to `master`.

Examples: `scripts/setup_psa_torque.sh sunny`, `scripts/setup_psa_torque.sh sunny release`, and `scripts/setup_psa_torque.sh openpilot master`. Use the separate `op-setup-psa-torque` skill for stable branches.

## Workflow

1. Determine the requested variant: `comma` or `sunny`.
2. Resolve the directory containing this `SKILL.md`.
3. Run the bundled wrapper by absolute path: `scripts/setup_psa_torque.sh <variant> [master|release]`.
4. Report the source mode, resolved upstream source commit and release tag when applicable, opendbc pointer commit, Sunny neural-network-data pointer when applicable, and whether the workflow pushed the openpilot testing branch.

The wrapper recreates the mapped local openpilot folder every time. For `sunny` only, it points the existing `sunnypilot/neural_network_data` submodule to `cristianku/neural-network-data:master`. It does not alter the NNLC loader or copy model files. It does not commit inside opendbc and does not clone, update, stage, or commit panda.

After cloning the selected upstream source, the wrapper edits `selfdrive/locationd/torqued.py` to add `'psa'` to the `ALLOWED_CARS` gate, so torqued (live `latAccelFactor`/friction learning) runs for the Peugeot 3008. The upstream source ships this list without PSA and the clone is recreated every run, so this patch is reapplied each time. The edit is idempotent (skipped if `psa` is already present) and is staged so it lands in the pushed testing branch commit.

For both variants, clone the configured upstream source directly, recreate the custom testing branch from its exact commit, update `.gitmodules` to `cristianku/opendbc`, set the `opendbc_repo` gitlink to Cristian's matching testing opendbc branch commit, and push with `--force-with-lease`. Default to master; in release mode query GitHub's latest-release endpoint, verify the returned tag, and clone that tag. Do not copy opendbc files into openpilot.

## Safety

- The mapped local openpilot testing directory is deleted and recreated.
- The workflow can rewrite `psa-torque-testing` or `psa-torque-sunny-testing` with `--force-with-lease`.
- Keep `opendbc_repo` as a submodule pointer (`160000 commit`), never a vendored directory.
- Keep `sunnypilot/neural_network_data` as a submodule pointer (`160000 commit`) and update it only for the `sunny` variant.
- Always use neural-network-data branch `master` for both Sunny stable and Sunny testing; do not create a separate testing branch.
- Stop and report an error if GitHub does not return a release tag or if that tag is unavailable from the selected upstream.
- Stage only `.gitmodules`, `opendbc_repo`, `selfdrive/locationd/torqued.py` (the PSA `ALLOWED_CARS` patch), and `sunnypilot/neural_network_data` when applicable.
- Override the neural data source only with `NEURAL_NETWORK_DATA_REPO` or `NEURAL_NETWORK_DATA_BRANCH` when explicitly required.
- Stop and report the error if cloning, validation, or a protected push fails.
