# Skills

Each skill directory contains a `SKILL.md` manifest and a `scripts/` implementation. Run the wrapper script, never the `_common.sh` directly. See the repo `README.md` for how to install them as Codex skills (symlink into `~/.agents/skills/`).

## setup-peugeot-3008 (stable)

Recreates the mapped local openpilot folder from current upstream `master`, recreates the custom **stable** branch (`peugeot-3008` / `peugeot-3008-sunny`) from that HEAD, points `.gitmodules` to `cristianku/opendbc`, sets the `opendbc_repo` gitlink to the matching opendbc branch commit, and for `sunny` points `sunnypilot/neural_network_data` to `cristianku/neural-network-data:master`. Pushes with `--force-with-lease`. Does not commit inside opendbc or touch panda.

```bash
./setup-peugeot-3008/scripts/setup_peugeot_3008.sh comma   # or: sunny
```

## setup-peugeot-3008-testing (testing)

Same as above but for the **testing** branches (`peugeot-3008-testing` / `peugeot-3008-sunny-testing`).

```bash
./setup-peugeot-3008-testing/scripts/setup_peugeot_3008.sh comma   # or: sunny
```

## merge-peugeot-3008-testing / merge-peugeot-3008-sunny-testing (promote)

Promote opendbc testing → stable: recreate a dedicated opendbc merge workspace, merge `*-testing` into stable with a merge commit, require Peugeot 3008 interface tests + PSA safety tests to pass, push stable with a lease protecting the previously observed remote SHA, then run the matching stable `setup-peugeot-3008` variant to refresh the openpilot pointer. Only operates on `cristianku/opendbc`; never merges openpilot branches into each other.

```bash
./merge-peugeot-3008-testing/scripts/merge_peugeot_3008.sh
./merge-peugeot-3008-sunny-testing/scripts/merge_peugeot_3008.sh
```

## commit-push-opendbc

Stage/commit/push working changes in `cristianku/opendbc` on the current feature branch. Verifies `origin` is `cristianku/opendbc`, refuses protected branches (`master`/`main`), never force-pushes, only touches opendbc.

```bash
./commit-push-opendbc/scripts/commit_push.sh "optional message"
```

## Common overrides

`GITHUB_USER`, `WORKSPACE_ROOT`, `OPENPILOT_DIR`, `OPENPILOT_REPO`, `OPENPILOT_SOURCE_REPO`, `OPENPILOT_SOURCE_BRANCH`, `OPENDBC_REPO`, `OPENDBC_SOURCE_REPO`, `OPENDBC_SOURCE_BRANCH`, `NEURAL_NETWORK_DATA_REPO`, `NEURAL_NETWORK_DATA_BRANCH`, `COMMIT_MESSAGE`. Merge skills add `MERGE_DIR`, `SETUP_SCRIPT`, `MERGE_TEST_COMMAND`, and `SKIP_TESTS=true` (emergency only).
