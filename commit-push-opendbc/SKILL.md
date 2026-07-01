---
name: commit-push-opendbc
description: Commit and push the current changes in Cristian's opendbc repo (cristianku/opendbc) on the current feature branch. Use when asked to commit and push opendbc / PSA / Peugeot changes.
---

# Commit and Push opendbc

Stage, commit, and push the working changes in `cristianku/opendbc` on the current branch.

## Workflow

1. Run the bundled script by absolute path: `scripts/commit_push.sh "optional commit message"`.
2. The script verifies the repo's `origin` is `cristianku/opendbc` and that HEAD is on a real branch.
3. It refuses to act on protected branches (`master`, `main`) — create a feature branch first.
4. It stages all changes (`git add -A`), commits, and pushes with `-u origin <branch>`.
5. If the tree is clean it pushes any unpushed local commits, otherwise reports nothing to do.
6. Report the resulting commit and the branch pushed.

## Usage

- With a message: pass it as arguments, e.g. `scripts/commit_push.sh "psa: fix steer output reporting"`.
- Without a message: a timestamped default (`update: <date time>`) is used.

## Safety

- Stop without pushing when `origin` is not the expected opendbc remote, HEAD is detached, or the branch is protected.
- Never force-push; a rejected push surfaces as an error to resolve manually.
- Only ever touches the opendbc repo, never the openpilot repos or submodule pointers.

## Overrides

- `OPENDBC_REPO`: path to the opendbc working copy (default Cristian's local clone).
- `EXPECTED_REMOTE`: substring the `origin` URL must contain (default `cristianku/opendbc`).
- `PROTECTED_BRANCHES`: space-separated branches to refuse (default `master main`).
