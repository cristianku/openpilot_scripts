---
name: setup-peugeot-3008-testing
description: Prepare Cristian's Peugeot 3008 testing workspace from current upstream master, point opendbc to the matching custom testing branch, and import optional steering NN models. Use variant comma for peugeot-3008-testing or sunny for peugeot-3008-sunny-testing.
---

# Setup Peugeot 3008 Testing

Use the bundled Peugeot 3008 testing setup workflow.

## Parameters

- `comma`: use openpilot and opendbc branch `peugeot-3008-testing`.
- `sunny`: use openpilot and opendbc branch `peugeot-3008-sunny-testing`.

Default to `comma` only when the user does not specify a variant. Use the separate `setup-peugeot-3008` skill for stable branches.

## Workflow

1. Determine the requested variant: `comma` or `sunny`.
2. Resolve the directory containing this `SKILL.md`.
3. Run the bundled wrapper by absolute path: `scripts/setup_peugeot_3008.sh <variant>`.
4. Report the upstream master commit, opendbc pointer commit, steering-model import status, and whether the workflow pushed the openpilot testing branch.

The wrapper recreates the mapped local openpilot folder every time. It checks `cristianku/sunny_steering_nn:main`; when a non-empty `models/` folder exists, it copies that folder into the openpilot root and commits it. On sunnypilot, it also points the NNLC loader to the copied root `models/` folder. It does not commit inside opendbc and does not clone, update, stage, or commit panda.

For both variants, clone the current upstream `master` branch directly, recreate the custom testing branch from its exact HEAD, update `.gitmodules` to `cristianku/opendbc`, set the `opendbc_repo` gitlink to Cristian's matching testing opendbc branch commit, and push with `--force-with-lease`. Use `commaai/openpilot` for `comma` and `sunnypilot/sunnypilot` for `sunny`. Do not copy opendbc files into openpilot.

## Safety

- The mapped local openpilot testing directory is deleted and recreated.
- The workflow can rewrite `peugeot-3008-testing` or `peugeot-3008-sunny-testing` with `--force-with-lease`.
- Keep `opendbc_repo` as a submodule pointer (`160000 commit`), never a vendored directory.
- If `models/` is absent or empty in `sunny_steering_nn`, continue without changing NNLC.
- Stage only `.gitmodules`, `opendbc_repo`, the imported `models/` tree, and the Sunny NNLC helper when models are present.
- Override the model source only with `STEERING_NN_REPO`, `STEERING_NN_BRANCH`, or `STEERING_NN_MODELS_DIR` when explicitly required.
- Stop and report the error if cloning, validation, or a protected push fails.
