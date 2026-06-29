---
name: setup-peugeot-3008
description: Prepare Cristian's stable Peugeot 3008 openpilot workspace from the current upstream master branch and point the opendbc submodule to the matching custom branch. Use variant comma for peugeot-3008 or sunny for peugeot-3008-sunny.
---

# Setup Peugeot 3008

Use the bundled stable Peugeot 3008 setup workflow.

## Parameters

- `comma`: use openpilot and opendbc branch `peugeot-3008`.
- `sunny`: use openpilot and opendbc branch `peugeot-3008-sunny`.

Default to `comma` only when the user does not specify a variant. Use the separate `setup-peugeot-3008-testing` skill for testing branches.

## Workflow

1. Determine the requested variant: `comma` or `sunny`.
2. Resolve the directory containing this `SKILL.md`.
3. Run the bundled wrapper by absolute path: `scripts/setup_peugeot_3008.sh <variant>`.
4. Report the upstream master commit, opendbc pointer commit, and whether the workflow pushed the openpilot branch.

The wrapper recreates the mapped local openpilot folder every time. It does not commit inside opendbc and does not clone, update, stage, or commit panda.

For both variants, clone the current upstream `master` branch directly, recreate the custom branch from its exact HEAD, update `.gitmodules` to `cristianku/opendbc`, set the `opendbc_repo` gitlink to Cristian's matching opendbc branch commit, and push with `--force-with-lease`. Use `commaai/openpilot` for `comma` and `sunnypilot/sunnypilot` for `sunny`. Do not copy opendbc files into openpilot.

## Safety

- The mapped local openpilot directory is deleted and recreated.
- The workflow can rewrite `peugeot-3008` or `peugeot-3008-sunny` with `--force-with-lease`.
- Keep `opendbc_repo` as a submodule pointer (`160000 commit`), never a vendored directory.
- Stage only `.gitmodules` and the `opendbc_repo` gitlink in the openpilot repository.
- Stop and report the error if cloning, validation, or a protected push fails.
