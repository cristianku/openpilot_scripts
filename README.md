# Peugeot 3008 openpilot setup scripts

These scripts prepare Cristian's Peugeot 3008 openpilot workspaces and update only the custom `opendbc_repo` integration.

## Layout

- `setup-psa-torque/`: creates or refreshes the stable Peugeot branches.
- `setup-psa-torque-testing/`: creates or refreshes the testing Peugeot branches.
- `merge-psa-torque-testing/`: promotes `psa-torque-testing` into `psa-torque` in opendbc.
- `merge-psa-torque-sunny-testing/`: promotes `psa-torque-sunny-testing` into `psa-torque-sunny` in opendbc.

Each skill stores its wrapper and shared implementation under `scripts/`. Run the wrapper, not the `_common.sh` file directly.

Both directories also contain a `SKILL.md` manifest, so they can be discovered as separate Codex skills in the VS Code extension, Codex CLI, and Codex app.

## Add the skills to Codex in VS Code

The Codex VS Code extension and Codex CLI share the same skill discovery locations described in the official [Codex Agent Skills documentation](https://developers.openai.com/codex/skills). Clone and open this repository:

```bash
git clone https://github.com/cristianku/openpilot_scripts.git
cd openpilot_scripts
code .
```

### Install for your user account

Use this option to make both skills available in every repository opened with Codex. Run these commands from the `openpilot_scripts` repository root:

```bash
mkdir -p "$HOME/.agents/skills"
ln -s "$PWD/setup-psa-torque" "$HOME/.agents/skills/setup-psa-torque"
ln -s "$PWD/setup-psa-torque-testing" "$HOME/.agents/skills/setup-psa-torque-testing"
ln -s "$PWD/merge-psa-torque-testing" "$HOME/.agents/skills/merge-psa-torque-testing"
ln -s "$PWD/merge-psa-torque-sunny-testing" "$HOME/.agents/skills/merge-psa-torque-sunny-testing"
```

The resulting layout is:

```text
~/.agents/skills/
├── setup-psa-torque -> /absolute/path/openpilot_scripts/setup-psa-torque
├── setup-psa-torque-testing -> /absolute/path/openpilot_scripts/setup-psa-torque-testing
├── merge-psa-torque-testing -> /absolute/path/openpilot_scripts/merge-psa-torque-testing
└── merge-psa-torque-sunny-testing -> /absolute/path/openpilot_scripts/merge-psa-torque-sunny-testing
```

### Install for one repository only

Use repository-scoped skills when they should only be available while working in a specific openpilot or opendbc checkout. From that target repository's root, run:

```bash
mkdir -p .agents/skills
ln -s /absolute/path/openpilot_scripts/setup-psa-torque .agents/skills/setup-psa-torque
ln -s /absolute/path/openpilot_scripts/setup-psa-torque-testing .agents/skills/setup-psa-torque-testing
ln -s /absolute/path/openpilot_scripts/merge-psa-torque-testing .agents/skills/merge-psa-torque-testing
ln -s /absolute/path/openpilot_scripts/merge-psa-torque-sunny-testing .agents/skills/merge-psa-torque-sunny-testing
```

Replace `/absolute/path/openpilot_scripts` with the actual clone location. Do not commit machine-specific absolute symlinks unless every contributor uses the same path.

Codex normally detects skill changes automatically. If they do not appear, restart the Codex extension or VS Code. In Codex chat, run `/skills` or type `$` to select:

- `$setup-psa-torque`
- `$setup-psa-torque-testing`
- `$merge-psa-torque-testing`
- `$merge-psa-torque-sunny-testing`

After installation, updating this repository with `git pull` also updates the symlinked skills.

## Usage

Stable comma.ai variant:

```bash
./setup-psa-torque/scripts/setup_psa_torque.sh comma
```

Stable sunnypilot variant for comma 4:

```bash
./setup-psa-torque/scripts/setup_psa_torque.sh sunny
```

Testing variants:

```bash
./setup-psa-torque-testing/scripts/setup_psa_torque.sh comma
./setup-psa-torque-testing/scripts/setup_psa_torque.sh sunny
```

Promote tested opendbc changes to stable and then refresh the matching openpilot submodule pointer:

```bash
./merge-psa-torque-testing/scripts/merge_psa_torque.sh
./merge-psa-torque-sunny-testing/scripts/merge_psa_torque.sh
```

The merge skills operate only on `cristianku/opendbc`. They validate the Peugeot interface and PSA safety tests before pushing the stable opendbc branch, then invoke the corresponding stable setup skill. They never merge generated openpilot testing branches into stable openpilot branches.

## Branch mapping

| Workflow | Variant | Upstream source | openpilot branch | opendbc branch |
| --- | --- | --- | --- | --- |
| Stable | `comma` | `commaai/openpilot:master` | `psa-torque` | `psa-torque` |
| Stable | `sunny` | `sunnypilot/sunnypilot:master` | `psa-torque-sunny` | `psa-torque-sunny` |
| Testing | `comma` | `commaai/openpilot:master` | `psa-torque-testing` | `psa-torque-testing` |
| Testing | `sunny` | `sunnypilot/sunnypilot:master` | `psa-torque-sunny-testing` | `psa-torque-sunny-testing` |

## Master source handling

Every workflow clones the current `master` branch directly from the official upstream repository:

1. Clone `commaai/openpilot:master` for `comma`, or `sunnypilot/sunnypilot:master` for `sunny`.
2. Create the requested Peugeot branch from that exact upstream HEAD.
3. Update `.gitmodules` to use `https://github.com/cristianku/opendbc.git`.
4. Set the `opendbc_repo` gitlink to the exact commit of Cristian's matching opendbc branch without copying its files.
5. Push with `--force-with-lease` using the custom remote SHA observed before rebuilding.

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
- `OPENDBC_REPO`
- `OPENDBC_SOURCE_REPO`
- `OPENDBC_SOURCE_BRANCH`
- `COMMIT_MESSAGE`

Example:

```bash
WORKSPACE_ROOT="$HOME/GitHub" ./setup-psa-torque/scripts/setup_psa_torque.sh sunny
```

## Safety behavior

- The mapped local openpilot directory is deleted and recreated on every run.
- All workflows may rewrite their remote openpilot branch with `--force-with-lease`.
- Only `.gitmodules` and the `opendbc_repo` submodule pointer are staged in openpilot.
- The scripts do not clone, update, stage, or commit `panda`.
- Git LFS upload is skipped when pushing the pointer commit.

Review the configured repository URLs and branch names before running the scripts against another account.
