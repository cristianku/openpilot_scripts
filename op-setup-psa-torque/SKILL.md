---
# [skill] - START
name: op-setup-psa-torque
description: Prepare Cristian's stable Peugeot 3008 workspace from a FROZEN stable release tag (sunny v2026.002.001 / comma v0.11.1), point opendbc to the matching custom branch, and for Sunny point neural network data to Cristian's neural-network-data master branch. Builds on device (submodule pointers, no prebuilt) - NOT master HEAD (breaks) nor the prebuilt release-mici branch (strips SConstruct). Use variant comma for psa-torque or sunny for psa-torque-sunny.
# [skill] - END
---

# Setup Peugeot 3008

Use the bundled stable Peugeot 3008 setup workflow.

## Parameters

- `comma`: use openpilot and opendbc branch `psa-torque`.
- `sunny`: use openpilot and opendbc branch `psa-torque-sunny`.

Default to `comma` only when the user does not specify a variant. Use the separate `op-setup-psa-torque-testing` skill for testing branches.

## Workflow

1. Determine the requested variant: `comma` or `sunny`.
2. Resolve the directory containing this `SKILL.md`.
3. Run the bundled wrapper by absolute path: `scripts/setup_psa_torque.sh <variant>`.
<!-- [skill] - START -->
4. Report the frozen upstream source commit, opendbc pointer commit, Sunny neural-network-data pointer and NNLC patch status when applicable, and whether the workflow pushed the openpilot stable branch.
<!-- [skill] - END -->

The wrapper recreates the mapped local openpilot folder every time. For `sunny` only, it points the existing `sunnypilot/neural_network_data` submodule to `cristianku/neural-network-data:master`. It does not copy model files. It does not commit inside opendbc and does not clone, update, stage, or commit panda.

<!-- [skill] - START -->
After cloning the frozen upstream release tag, the wrapper edits `selfdrive/locationd/torqued.py` to add `'psa'` to the `ALLOWED_CARS` gate, so torqued (live `latAccelFactor`/friction learning) runs for the Peugeot 3008. The upstream source ships this list without PSA and the clone is recreated every run, so this patch is reapplied each time. The edit is idempotent (skipped if `psa` is already present) and is staged so it lands in the pushed branch commit.

<!-- [nnlc] - START -->
For `sunny` only, the wrapper also reapplies the bundled NNLC torque-space correction after every upstream clone. It preserves the extension's dedicated PID instead of replacing it with the base lateral-acceleration PID, applies `friction_override` through `get_friction_in_torque_space`, and logs the PID that actually controls NNLC. The patch supports both the legacy root layout and the `openpilot/` monorepo layout, is idempotent, and stops the workflow if upstream no longer matches the reviewed code.
<!-- [nnlc] - END -->

For both variants, clone the configured frozen upstream release tag directly, recreate the custom stable branch from its exact commit, update `.gitmodules` to `cristianku/opendbc`, set the `opendbc_repo` gitlink to Cristian's matching stable opendbc branch commit, and push with `--force-with-lease`. The defaults are `commaai/openpilot:v0.11.1` for `comma` and `sunnypilot/sunnypilot:v2026.002.001` for `sunny`. Do not copy opendbc files into openpilot.
<!-- [skill] - END -->

## Safety

- The mapped local openpilot directory is deleted and recreated.
- The workflow can rewrite `psa-torque` or `psa-torque-sunny` with `--force-with-lease`.
- Keep `opendbc_repo` as a submodule pointer (`160000 commit`), never a vendored directory.
- Keep `sunnypilot/neural_network_data` as a submodule pointer (`160000 commit`) and update it only for the `sunny` variant.
- Always use neural-network-data branch `master` for both Sunny stable and Sunny testing; do not create a separate testing branch.
<!-- [nnlc] - START -->
- Stage only `.gitmodules`, `opendbc_repo`, `selfdrive/locationd/torqued.py` (the PSA `ALLOWED_CARS` patch), `sunnypilot/neural_network_data`, and—only for Sunny—the three patched NNLC runtime files: `selfdrive/controls/lib/latcontrol_torque.py`, `sunnypilot/selfdrive/controls/lib/latcontrol_torque_ext.py`, and `sunnypilot/selfdrive/controls/lib/nnlc/nnlc.py`. These paths may carry the upstream `openpilot/` prefix.
<!-- [nnlc] - END -->
- Override the neural data source only with `NEURAL_NETWORK_DATA_REPO` or `NEURAL_NETWORK_DATA_BRANCH` when explicitly required.
- Stop and report the error if cloning, validation, or a protected push fails.
