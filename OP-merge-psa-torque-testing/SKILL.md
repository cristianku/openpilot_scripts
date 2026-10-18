---
name: OP-merge-psa-torque-testing
description: Promote Cristian's non-Sunny Peugeot 3008 opendbc testing branch into psa-torque, validate the PSA port, and push stable safely. Use when testing changes are ready for stable; openpilot setup is a separate user-invoked operation.
---

# Merge Peugeot 3008 Testing

<!-- [merge only] - START -->
Promote only `cristianku/opendbc:psa-torque-testing` into `psa-torque`. Stop after validation and the stable push. Cristian runs openpilot setup separately and chooses its source there; this skill does not rebuild openpilot, refresh its submodule pointer, or invoke a setup wrapper.
<!-- [merge only] - END -->

## Workflow

1. Run the bundled script with `bash` and its absolute path: `bash scripts/merge_psa_torque.sh`.
2. Let the script recreate its dedicated opendbc merge workspace.
3. Merge `psa-torque-testing` into `psa-torque` with a merge commit.
4. Require the Peugeot 3008 interface tests and PSA safety tests to pass before pushing.
5. Push `psa-torque` with a lease protecting the previously observed remote SHA.
<!-- [merge only] - START -->
6. Report the stable opendbc commit, whether a merge was needed, test results and push status. State that openpilot and the comma device were not updated.
<!-- [merge only] - END -->

## Safety

- Stop without pushing when either branch is missing, a merge conflicts, tests fail, or the remote stable SHA changes.
- Delete and recreate only the dedicated merge workspace.
- Merge only in `cristianku/opendbc`; do not merge openpilot testing into openpilot stable.
- If testing is already contained in stable, report that no merge was needed and stop.

## Overrides

- `OPENDBC_REPO`: alternate opendbc remote.
- `WORKSPACE_ROOT` and `MERGE_DIR`: merge workspace location.
- `MERGE_TEST_COMMAND`: replace the default interface and safety test commands.
- `SKIP_TESTS=true`: use only if Cristian explicitly authorizes the emergency override.
