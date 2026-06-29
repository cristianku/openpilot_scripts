---
name: setup-peugeot-3008-testing
description: Prepare Cristian's Peugeot 3008 testing workspace and refresh the matching custom opendbc integration. Use variant comma for peugeot-3008-testing or sunny for the comma 4 peugeot-3008-sunny-testing release-aligned workflow.
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
4. Report whether the workflow updated and pushed the openpilot testing branch and its `opendbc_repo` pointer.

The wrapper recreates the mapped local openpilot folder every time. It does not commit inside opendbc and does not clone, update, stage, or commit panda.

For `sunny`, the wrapper reads `git_src_commit` from `sunnypilot/sunnypilot:release-mici`, recreates the testing branch from that complete source commit, applies Cristian's testing opendbc pointer, and pushes with `--force-with-lease`.

## Safety

- The mapped local openpilot testing directory is deleted and recreated.
- The sunny workflow can rewrite `peugeot-3008-sunny-testing` with `--force-with-lease`.
- Stage only `.gitmodules` and `opendbc_repo` in the openpilot repository.
- Stop and report the error if release metadata, cloning, validation, or a protected push fails.
