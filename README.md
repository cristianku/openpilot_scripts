# Peugeot 3008 openpilot setup scripts

These scripts prepare Cristian's Peugeot 3008 openpilot workspaces and update only the custom `opendbc_repo` integration.

## Layout

- `setup-peugeot-3008/`: creates or refreshes the stable Peugeot branches.
- `setup-peugeot-3008-testing/`: creates or refreshes the testing Peugeot branches.

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
ln -s "$PWD/setup-peugeot-3008" "$HOME/.agents/skills/setup-peugeot-3008"
ln -s "$PWD/setup-peugeot-3008-testing" "$HOME/.agents/skills/setup-peugeot-3008-testing"
```

The resulting layout is:

```text
~/.agents/skills/
├── setup-peugeot-3008 -> /absolute/path/openpilot_scripts/setup-peugeot-3008
└── setup-peugeot-3008-testing -> /absolute/path/openpilot_scripts/setup-peugeot-3008-testing
```

### Install for one repository only

Use repository-scoped skills when they should only be available while working in a specific openpilot or opendbc checkout. From that target repository's root, run:

```bash
mkdir -p .agents/skills
ln -s /absolute/path/openpilot_scripts/setup-peugeot-3008 .agents/skills/setup-peugeot-3008
ln -s /absolute/path/openpilot_scripts/setup-peugeot-3008-testing .agents/skills/setup-peugeot-3008-testing
```

Replace `/absolute/path/openpilot_scripts` with the actual clone location. Do not commit machine-specific absolute symlinks unless every contributor uses the same path.

Codex normally detects skill changes automatically. If they do not appear, restart the Codex extension or VS Code. In Codex chat, run `/skills` or type `$` to select:

- `$setup-peugeot-3008`
- `$setup-peugeot-3008-testing`

After installation, updating this repository with `git pull` also updates the symlinked skills.

## Usage

Stable comma.ai variant:

```bash
./setup-peugeot-3008/scripts/setup_peugeot_3008.sh comma
```

Stable sunnypilot variant for comma 4:

```bash
./setup-peugeot-3008/scripts/setup_peugeot_3008.sh sunny
```

Testing variants:

```bash
./setup-peugeot-3008-testing/scripts/setup_peugeot_3008.sh comma
./setup-peugeot-3008-testing/scripts/setup_peugeot_3008.sh sunny
```

## Branch mapping

| Workflow | Variant | Release source | openpilot branch | opendbc branch |
| --- | --- | --- | --- | --- |
| Stable | `comma` | `commaai/openpilot:release-mici` | `peugeot-3008` | `peugeot-3008` |
| Stable | `sunny` | `sunnypilot/sunnypilot:release-mici` | `peugeot-3008-sunny` | `peugeot-3008-sunny` |
| Testing | `comma` | `commaai/openpilot:release-mici` | `peugeot-3008-testing` | `peugeot-3008-testing` |
| Testing | `sunny` | `sunnypilot/sunnypilot:release-mici` | `peugeot-3008-sunny-testing` | `peugeot-3008-sunny-testing` |

## release-mici source handling

`release-mici` is a stripped prebuilt branch in both upstream repositories, so the workflows do not use it directly as a development tree. Instead, the script:

1. Resolves the release's complete source commit: from `git_src_commit` when available, or from sunnypilot's matching `v<version>` source tag.
2. Fetches that complete source commit.
3. Creates the requested Peugeot branch from the source commit.
4. Points `opendbc_repo` to Cristian's matching opendbc branch.
5. Pushes with `--force-with-lease` using the remote SHA observed before rebuilding.

This keeps both custom comma 4 variants aligned with the source used for their stable release while preserving the Peugeot opendbc changes.

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
- `RECREATE_OPENPILOT_FROM_RELEASE`
- `OPENDBC_REPO`
- `OPENDBC_SOURCE_REPO`
- `OPENDBC_SOURCE_BRANCH`
- `COMMIT_MESSAGE`

Example:

```bash
WORKSPACE_ROOT="$HOME/GitHub" ./setup-peugeot-3008/scripts/setup_peugeot_3008.sh sunny
```

## Safety behavior

- The mapped local openpilot directory is deleted and recreated on every run.
- All workflows may rewrite their remote openpilot branch with `--force-with-lease`.
- Only `.gitmodules` and the `opendbc_repo` pointer are staged in openpilot.
- The scripts do not clone, update, stage, or commit `panda`.
- Git LFS upload is skipped when pushing the pointer commit.

Review the configured repository URLs and branch names before running the scripts against another account.
