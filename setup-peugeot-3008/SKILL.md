---
name: setup-peugeot-3008
description: Prepare Cristian's stable Peugeot 3008 openpilot workspace and refresh the matching custom opendbc integration. Use variant comma for peugeot-3008 or sunny for the comma 4 peugeot-3008-sunny release-aligned workflow.
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
4. Report whether the workflow updated and pushed the openpilot branch and its `opendbc_repo` pointer.

The wrapper recreates the mapped local openpilot folder every time. It does not commit inside opendbc and does not clone, update, stage, or commit panda.

For `sunny`, the wrapper reads `git_src_commit` from `sunnypilot/sunnypilot:release-mici`, recreates the branch from that complete source commit, applies Cristian's matching opendbc pointer, and pushes with `--force-with-lease`.

## Safety

- The mapped local openpilot directory is deleted and recreated.
- The sunny workflow can rewrite `peugeot-3008-sunny` with `--force-with-lease`.
- Stage only `.gitmodules` and `opendbc_repo` in the openpilot repository.
- Stop and report the error if release metadata, cloning, validation, or a protected push fails.
