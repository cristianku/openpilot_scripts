---
name: merge-peugeot-3008-sunny-testing
description: Promote Cristian's sunny Peugeot 3008 opendbc testing branch by merging peugeot-3008-sunny-testing into peugeot-3008-sunny, validating the PSA port, pushing stable safely, and refreshing the matching sunny openpilot opendbc pointer. Use when the sunny Peugeot testing changes are ready for stable.
---

# Merge Peugeot 3008 Sunny Testing

Promote the sunny Peugeot 3008 opendbc testing branch to stable. Never merge the generated openpilot branches into each other.

## Workflow

1. Run the bundled script by absolute path: `scripts/merge_peugeot_3008.sh`.
2. Let the script recreate its dedicated opendbc merge workspace.
3. Merge `peugeot-3008-sunny-testing` into `peugeot-3008-sunny` with a merge commit.
4. Require the Peugeot 3008 interface tests and PSA safety tests to pass before pushing.
5. Push `peugeot-3008-sunny` with a lease protecting the previously observed remote SHA.
6. Run the `sunny` variant of `setup-peugeot-3008` to refresh `peugeot-3008-sunny` in openpilot.
7. Report the opendbc merge commit and resulting openpilot pointer commit.

## Safety

- Stop without pushing when either branch is missing, a merge conflicts, tests fail, or the remote stable SHA changes.
- Delete and recreate only the dedicated merge workspace.
- Merge only in `cristianku/opendbc`; do not merge openpilot sunny testing into openpilot sunny stable.
- If opendbc was already merged but pointer refresh failed previously, rerun the skill to retry the setup step.

## Overrides

- `OPENDBC_REPO`: alternate opendbc remote.
- `WORKSPACE_ROOT` and `MERGE_DIR`: merge workspace location.
- `SETUP_SCRIPT`: alternate stable setup wrapper.
- `MERGE_TEST_COMMAND`: replace the default interface and safety test commands.
- `SKIP_TESTS=true`: explicit emergency override; avoid for normal promotion.
