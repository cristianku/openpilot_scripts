# Peugeot 3008 openpilot setup scripts

These scripts prepare Cristian's Peugeot 3008 openpilot workspaces and update only the custom `opendbc_repo` integration.

## Layout

- `stable/`: creates or refreshes the stable Peugeot branches.
- `testing/`: creates or refreshes the testing Peugeot branches.

Each directory contains a wrapper and its shared implementation. Run the wrapper, not the `_common.sh` file directly.

## Usage

Stable comma.ai variant:

```bash
./stable/setup_peugeot_3008.sh comma
```

Stable sunnypilot variant for comma 4:

```bash
./stable/setup_peugeot_3008.sh sunny
```

Testing variants:

```bash
./testing/setup_peugeot_3008.sh comma
./testing/setup_peugeot_3008.sh sunny
```

## Branch mapping

| Workflow | Variant | openpilot branch | opendbc branch |
| --- | --- | --- | --- |
| Stable | `comma` | `peugeot-3008` | `peugeot-3008` |
| Stable | `sunny` | `peugeot-3008-sunny` | `peugeot-3008-sunny` |
| Testing | `comma` | `peugeot-3008-testing` | `peugeot-3008-testing` |
| Testing | `sunny` | `peugeot-3008-sunny-testing` | `peugeot-3008-sunny-testing` |

## sunnypilot release handling

`release-mici` is a stripped prebuilt branch, so the sunny workflow does not use it directly as a development tree. Instead, the script:

1. Reads `git_src_commit` from `sunnypilot/sunnypilot:release-mici`.
2. Fetches that complete source commit.
3. Creates the requested Peugeot sunny branch from the source commit.
4. Points `opendbc_repo` to Cristian's matching opendbc branch.
5. Pushes with `--force-with-lease` using the remote SHA observed before rebuilding.

This keeps the custom comma 4 branch aligned with the source used for the stable sunnypilot release while preserving the Peugeot opendbc changes.

## Defaults and overrides

The scripts default to:

- GitHub user: `cristianku`
- Workspace root: `/Users/cristianku/GitHub/COMMA.AI/CRISTIANKU`
- openpilot fork: `https://github.com/cristianku/openpilot.git`
- opendbc fork: `https://github.com/cristianku/opendbc.git`

The main overrides are:

- `GITHUB_USER`
- `WORKSPACE_ROOT`
- `OPENPILOT_DIR`
- `OPENPILOT_REPO`
- `OPENPILOT_SOURCE_REPO`
- `OPENPILOT_SOURCE_BRANCH`
- `OPENPILOT_RELEASE_BRANCH`
- `OPENDBC_REPO`
- `OPENDBC_SOURCE_REPO`
- `OPENDBC_SOURCE_BRANCH`
- `COMMIT_MESSAGE`

Example:

```bash
WORKSPACE_ROOT="$HOME/GitHub" ./stable/setup_peugeot_3008.sh sunny
```

## Safety behavior

- The mapped local openpilot directory is deleted and recreated on every run.
- The sunny workflows may rewrite their remote openpilot branch with `--force-with-lease`.
- Only `.gitmodules` and the `opendbc_repo` pointer are staged in openpilot.
- The scripts do not clone, update, stage, or commit `panda`.
- Git LFS upload is skipped when pushing the pointer commit.

Review the configured repository URLs and branch names before running the scripts against another account.
