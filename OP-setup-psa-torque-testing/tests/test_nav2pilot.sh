#!/usr/bin/env bash
# enable_nav2pilot: the Nav2Pilot commit of the branch is applied, staged, on whichever base the setup cloned; a commit
# that no longer applies, or a merge in its place, stops the setup; without a branch (SKIP_NAV=true) nothing changes.
set -euo pipefail

skill_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
common_script="${skill_root}/scripts/setup_psa_torque_common.sh"
test_root="$(mktemp -d)"
trap 'rm -rf "${test_root}"' EXIT

fail() {
  echo "FAIL: $*" >&2
  exit 1
}

git_test() {
  git -c user.name=Test -c user.email=test@example.invalid -c init.defaultBranch=master "$@"
}

navd=openpilot/selfdrive/navigation/navd.py
make_base() {
  local dest="$1"
  mkdir -p "${dest}/$(dirname "${navd}")"
  printf '%s\n' 'def route():' '  return None' > "${dest}/${navd}"
  git_test -C "${dest}" init -q
  git_test -C "${dest}" add -- .
  git_test -C "${dest}" commit -qm 'upstream master'
}

# The fork, as OP-apply-nav-alpha publishes it: sunny-nav-alpha = upstream master + one Nav2Pilot commit.
fork="${test_root}/fork"
make_base "${fork}"
git_test -C "${fork}" checkout -qb sunny-nav-alpha
printf '%s\n' 'def route():' '  return waypoints()' > "${fork}/${navd}"
printf '%s\n' 'def waypoints():' '  return []' > "${fork}/openpilot/selfdrive/navigation/waypoints.py"
git_test -C "${fork}" add -- .
git_test -C "${fork}" commit -qm 'nav alpha: Nav2Pilot'
# A "Sync fork" merge in place of the single commit.
git_test -C "${fork}" checkout -qb merged master
git_test -C "${fork}" commit -q --allow-empty -m 'upstream moved'
git_test -C "${fork}" merge -q --no-edit sunny-nav-alpha

BRANCH="psa-torque-sunny-testing"
OPENPILOT_SOURCE_REPO="${test_root}"
OPENPILOT_SOURCE_BRANCH=master
NAV2PILOT_BRANCH=sunny-nav-alpha
NAV2PILOT_REPO="file://${fork}"
# shellcheck disable=SC1090
source "${common_script}"

# Applied and staged.
applied="${test_root}/applied"
make_base "${applied}"
enable_nav2pilot "${applied}" | grep -q 'Added Nav2Pilot' || fail "not applied"
grep -q waypoints "${applied}/${navd}" || fail "navd.py not patched"
git -C "${applied}" diff --cached --name-only | grep -q 'waypoints.py' || fail "new file not staged"

# A base where upstream changed the same lines: the setup stops.
conflict="${test_root}/conflict"
make_base "${conflict}"
printf '%s\n' 'def route():' '  return upstream_route()' > "${conflict}/${navd}"
git_test -C "${conflict}" commit -qam 'upstream changed navd'
if (enable_nav2pilot "${conflict}" > /dev/null 2>&1); then
  fail "a commit that does not apply did not stop the setup"
fi

# A merge on the branch: the setup stops.
merged="${test_root}/merged"
make_base "${merged}"
if (NAV2PILOT_BRANCH=merged enable_nav2pilot "${merged}" > /dev/null 2>&1); then
  fail "a merge on the Nav2Pilot branch did not stop the setup"
fi

# Without a branch: nothing.
skipped="${test_root}/skipped"
make_base "${skipped}"
NAV2PILOT_BRANCH="" enable_nav2pilot "${skipped}" | grep -q 'built without Nav2Pilot' || fail "skip ignored"
git -C "${skipped}" diff --cached --quiet || fail "skip staged changes"

echo "PASS: Nav2Pilot injected from its branch commit, stopped on a conflict or a merge, skipped without a branch"
