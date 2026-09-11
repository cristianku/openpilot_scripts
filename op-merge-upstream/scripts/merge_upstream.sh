#!/usr/bin/env bash
# [upstream merge] - START
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: merge_upstream.sh <sunny|comma>

Fetch official opendbc master into the matching local PSA testing branch.
Creates a backup branch and leaves the merge UNCOMMITTED for review/tests.
No push, openpilot setup, submodule checkout, or device operations.

OPENDBC_DIR overrides the local checkout (default: Cristian's opendbc workspace).
Exit codes: 0 = ready for review/already merged; 1 = error; 2 = merge conflicts.
EOF
}

die() { echo "ERROR: $*" >&2; exit 1; }

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
  usage
  exit 0
fi
[[ $# -eq 1 ]] || { usage >&2; exit 1; }
case "$1" in
  sunny|sunnypilot)
    target_branch="psa-torque-sunny-testing"
    upstream="https://github.com/sunnypilot/opendbc.git"
    ;;
  comma|openpilot)
    target_branch="psa-torque-testing"
    upstream="https://github.com/commaai/opendbc.git"
    ;;
  *) usage >&2; exit 1 ;;
esac

repo="${OPENDBC_DIR:-/Users/cristianku/GitHub/COMMA.AI/CRISTIANKU/opendbc}"
cd "${repo}" || die "Cannot open checkout: ${repo}"
[[ "$(git rev-parse --is-inside-work-tree)" == "true" ]] || die "Not a Git working tree"
repo="$(git rev-parse --show-toplevel)"
cd "${repo}"
origin="$(git config --get remote.origin.url)" || die "Missing origin remote"
case "${origin}" in
  https://github.com/cristianku/opendbc|https://github.com/cristianku/opendbc.git|git@github.com:cristianku/opendbc.git|ssh://git@github.com/cristianku/opendbc.git) ;;
  *) die "Expected origin cristianku/opendbc; found ${origin}" ;;
esac

preflight() {
  local active marker
  active="$(git symbolic-ref --quiet --short HEAD)" || die "Detached HEAD; expected ${target_branch}"
  [[ "${active}" == "${target_branch}" ]] || die "Expected branch ${target_branch}; found ${active}. Switch explicitly before running."
  for marker in MERGE_HEAD CHERRY_PICK_HEAD REVERT_HEAD rebase-merge rebase-apply sequencer BISECT_START; do
    [[ ! -e "$(git rev-parse --git-path "${marker}")" ]] || die "Git operation in progress (${marker}); finish or abort it first."
  done
  [[ -z "$(git status --porcelain --untracked-files=all)" ]] || die "Dirty working tree/index (including untracked files); preserve your work first."
}

preflight
before="$(git rev-parse HEAD)"
echo "Checkout: ${repo}"
echo "Target: ${target_branch} (${before})"
echo "Source: ${upstream} master"

# Complete the fork's ancestry first: upstream alone may not contain custom
# commits at a shallow boundary. Failure leaves the worktree and HEAD unchanged.
if [[ "$(git rev-parse --is-shallow-repository)" == "true" ]]; then
  echo "Completing shallow history from origin"
  git fetch --no-tags --no-recurse-submodules --unshallow origin || die "Could not complete fork history; no merge attempted."
fi
git fetch --no-tags --no-recurse-submodules "${upstream}" refs/heads/master || die "Upstream fetch failed; no merge attempted."
source_sha="$(git rev-parse --verify 'FETCH_HEAD^{commit}')"
base="$(git merge-base HEAD "${source_sha}")" || die "No common ancestor with upstream master; refusing unrelated histories."
echo "Fetched master: ${source_sha}"
echo "Common ancestor: ${base}"

# Recheck after network operations in case the checkout changed meanwhile.
preflight
[[ "$(git rev-parse HEAD)" == "${before}" ]] || die "HEAD changed during fetch; no merge attempted."
if git merge-base --is-ancestor "${source_sha}" HEAD; then
  echo "Already merged: no worktree changes, commit, or push."
  exit 0
fi

backup="backup/${target_branch}-before-upstream-$(date -u +%Y%m%dT%H%M%SZ)-$$"
git branch "${backup}" "${before}"
echo "Backup: ${backup} (${before})"
echo "Merging master for review; HEAD will stay at ${before}"

# --no-ff prevents even a fast-forward from advancing the branch before review.
# Disable autostash, reuse of old resolutions and recursive submodule checkouts.
if git -c merge.autostash=false -c rerere.enabled=false -c submodule.recurse=false \
    merge --no-ff --no-commit "${source_sha}"; then
  git diff --cached --check || die "Diff check failed; merge left pending for review."
  git diff --cached --stat
  echo "Merge prepared, NOT committed or pushed. Run PSA tests and review the diff."
  printf 'To cancel this pending merge: git -C %q merge --abort\n' "${repo}"
else
  if [[ -n "$(git diff --name-only --diff-filter=U)" ]]; then
    echo "CONFLICTS: merge left pending; no automatic ours/theirs resolution." >&2
    git diff --name-only --diff-filter=U
    printf 'To cancel this pending merge: git -C %q merge --abort\n' "${repo}"
    exit 2
  fi
  die "Merge failed; inspect git status. Backup: ${backup}. No commit or push."
fi
# [upstream merge] - END
