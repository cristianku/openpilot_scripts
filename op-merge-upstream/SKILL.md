---
name: op-merge-upstream
description: Use when Cristian asks to fetch and merge official opendbc master into his PSA Sunny or comma testing branch. Does not merge openpilot branches, promote testing to stable, or regenerate openpilot.
---

# OP Merge Upstream

<!-- [upstream merge] - START -->
Prepare a local, uncommitted opendbc merge for review and PSA validation.

| Argument | Official source | Required local branch |
| --- | --- | --- |
| `sunny` / `sunnypilot` | `sunnypilot/opendbc:master` | `psa-torque-sunny-testing` |
| `comma` / `openpilot` | `commaai/opendbc:master` | `psa-torque-testing` |

Specify the variant; ask if it cannot be inferred from the request. Example invocation: `$op-merge-upstream sunny`.

## Run

1. Read the shared and repository AGENTS.md instructions. Inspect the checkout status and explain the source, target and pending-merge behavior. A request to create this skill or explain a merge does not authorize running it.
2. Resolve this skill's directory, then run its wrapper by absolute path:
   `bash <skill-directory>/scripts/merge_upstream.sh sunny`.
   The checkout defaults to `/Users/cristianku/GitHub/COMMA.AI/CRISTIANKU/opendbc`; use `OPENDBC_DIR` only for an explicitly selected alternative checkout. The wrapper checks the fork's origin and requires the mapped branch already checked out. Do not switch branches automatically.
3. On exit 2, report conflicted paths and the backup reference. Leave resolutions to a separately scoped review; do not blindly choose ours/theirs or retry. On any other failure, report the actual state and stop. Never bypass missing ancestry with `--allow-unrelated-histories`.
4. On success, inspect `git status`, `git diff --cached --stat`, and the staged diff. If a merge is pending, run the PSA-specific tests (`opendbc/car/psa/tests`), PSA interface tests (`opendbc/car/tests/test_car_interfaces.py -k PSA_`), and `opendbc/safety/tests/test_psa.py` using the repository's documented environment. Report unavailable dependencies or failures; do not claim validation from a clean Git merge alone.
5. Report source SHA, original HEAD, backup reference, conflicting/changed files, tests, and whether the merge is pending or already incorporated. Finish here unless commit or push was separately requested. Keep failed validation uncommitted. Publishing must also account for compatibility with the user's selected openpilot base.

## Behavior and limits

The wrapper refuses dirty or detached checkouts and operations already in progress. It completes shallow history from `origin`, fetches official `master` directly by URL without changing remote configuration, and checks for a common ancestor. Fetch updates Git metadata; it may download substantial history. It creates a backup branch at the original HEAD, then merges with `--no-ff --no-commit`, including when a fast-forward is possible. HEAD stays unchanged; index and tracked files contain the proposed merge.

`git merge --abort` cancels a pending merge; do not run it automatically or after new user edits without reviewing the state. The backup protects committed history, not subsequent uncommitted work. An already incorporated source produces no merge or backup.

A conflict-free merge can still break PSA behavior or compatibility with pinned Sunny (for example `de197ba6`). Passing tests does not establish road behavior. Do not run openpilot setup, refresh its pointers, promote stable, push, update submodule checkouts, or operate on devices as part of this skill alone.
<!-- [upstream merge] - END -->
