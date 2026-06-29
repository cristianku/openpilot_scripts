---
name: setup-peugeot-3008-testing
description: Prepare Cristian's Peugeot 3008 testing workspace directly from the current upstream comma 4 release-mici branch and vendor the complete custom opendbc tree. Use variant comma for peugeot-3008-testing or sunny for peugeot-3008-sunny-testing.
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
4. Report the upstream release commit and whether the workflow updated and pushed the openpilot testing branch.

The wrapper recreates the mapped local openpilot folder every time. It does not commit inside opendbc and does not clone, update, stage, or commit panda.

For both variants, clone the current upstream `release-mici` branch directly, recreate the custom testing branch from its exact HEAD, replace `opendbc_repo` with the complete contents of Cristian's matching testing opendbc branch, remove the nested `.git`, and push with `--force-with-lease`. Use `commaai/openpilot` for `comma` and `sunnypilot/sunnypilot` for `sunny`. Never use `cristianku/openpilot:release-mici` as the source.

## Safety

- The mapped local openpilot testing directory is deleted and recreated.
- The workflow can rewrite `peugeot-3008-testing` or `peugeot-3008-sunny-testing` with `--force-with-lease`.
- Keep `opendbc_repo` as a regular tracked directory, never a submodule pointer.
- Stage only `opendbc_repo` in the openpilot repository.
- Stop and report the error if cloning, validation, or a protected push fails.
