---
name: merge-psa-torque-sunny-testing
description: Promote Cristian's Sunny PSA torque opendbc testing branch by merging psa-torque-sunny-testing into psa-torque-sunny, validating the PSA port, and pushing only the stable branch safely. Use when the Sunny PSA torque testing changes are ready for stable.
---

# Merge PSA Torque Sunny Testing

Promote the Sunny PSA torque opendbc testing branch to stable. Never merge the generated openpilot branches into each other.

## Workflow

1. Run the bundled script by absolute path: `scripts/merge_psa_torque.sh`.
2. Let the script recreate its dedicated opendbc merge workspace.
3. Merge `psa-torque-sunny-testing` into `psa-torque-sunny` with a merge commit.
4. Require the PSA interface tests and PSA safety tests to pass before pushing.
5. Push `psa-torque-sunny` with a lease protecting the previously observed remote SHA.
6. Report the resulting opendbc merge commit.

## Safety

- Stop without pushing when either branch is missing, a merge conflicts, tests fail, or the remote stable SHA changes.
- Delete and recreate only the dedicated merge workspace.
- Merge only in `cristianku/opendbc`; do not modify either openpilot branch.
- Treat `psa-torque-sunny-testing` as read-only: never commit, reset, rebase, delete, or push it.

## Overrides

- `OPENDBC_REPO`: alternate opendbc remote.
- `WORKSPACE_ROOT` and `MERGE_DIR`: merge workspace location.
- `MERGE_TEST_COMMAND`: replace the default interface and safety test commands.
- `SKIP_TESTS=true`: explicit emergency override; avoid for normal promotion.
