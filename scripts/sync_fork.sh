#!/usr/bin/env bash
# Sync fork from the server: moves the master of a fork to upstream master, the same as the button on GitHub.
# Fast-forward only: it refuses when the fork has commits of its own, and never forces.
#   sync_fork.sh <sunnypilot|openpilot>
# Env: NO_PUSH=true (says what it would do), FORK_CACHE (bare cache, as in update_fork_branch.sh)
set -euo pipefail

GITHUB="${GITHUB:-https://github.com}"
FORK_CACHE="${FORK_CACHE:-/root/work/fork-branch-cache.git}"
NO_PUSH="${NO_PUSH:-false}"

die() { echo "ERROR: $*" >&2; exit 1; }
g() { git -C "${FORK_CACHE}" "$@"; }

case "${1:-}" in
  sunnypilot) upstream="sunnypilot/sunnypilot" fork="cristianku/sunnypilot" ;;
  openpilot) upstream="commaai/openpilot" fork="cristianku/openpilot" ;;
  *) echo "Usage: sync_fork.sh <sunnypilot|openpilot>" >&2; exit 1 ;;
esac

[[ -d "${FORK_CACHE}" ]] || git init -q --bare "${FORK_CACHE}"
echo "== fetch ${upstream} master and ${fork} master"
g fetch -q --no-tags "${GITHUB}/${upstream}.git" "+refs/heads/master:refs/sources/sync/${fork}/upstream"
g fetch -q --no-tags "${GITHUB}/${fork}.git" "+refs/heads/master:refs/sources/sync/${fork}/fork"
new="$(g rev-parse "refs/sources/sync/${fork}/upstream")"
old="$(g rev-parse "refs/sources/sync/${fork}/fork")"

if [[ "${new}" == "${old}" ]]; then
  echo "${fork} master is already at ${new:0:10}: nothing to do."
  exit 0
fi
g merge-base --is-ancestor "${old}" "${new}" || die "${fork} master has commits upstream does not have: not touched."

echo "== ${fork} master: ${old:0:10} -> ${new:0:10}, $(g rev-list --count "${old}..${new}") commits"
if [[ "${NO_PUSH}" == "true" ]]; then
  echo "NO_PUSH: not published"
  exit 0
fi
g push -q "${GITHUB}/${fork}.git" "${new}:refs/heads/master"
echo "== published"
