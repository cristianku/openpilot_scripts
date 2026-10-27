#!/usr/bin/env bash
# enable_nav2pilot: the canonical Nav2Pilot patch is applied, staged, on whichever base the setup cloned; a patch that
# no longer applies stops the setup; without a patch (SKIP_NAV=true) nothing changes.
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

# The patch, made as OP-apply-nav-alpha makes it: a diff over the upstream base.
patch_source="${test_root}/patch-source"
make_base "${patch_source}"
printf '%s\n' 'def route():' '  return waypoints()' > "${patch_source}/${navd}"
printf '%s\n' 'def waypoints():' '  return []' > "${patch_source}/openpilot/selfdrive/navigation/waypoints.py"
git -C "${patch_source}" add -N -- .
nav_patch="${test_root}/sunnypilot.patch"
git -C "${patch_source}" diff --binary --full-index > "${nav_patch}"

BRANCH="psa-torque-sunny-testing"
OPENPILOT_SOURCE_REPO="${test_root}"
OPENPILOT_SOURCE_BRANCH=master
NAV2PILOT_PATCH="${nav_patch}"
NAV2PILOT_BASE=""
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
  fail "a patch that does not apply did not stop the setup"
fi

# Without a patch: nothing.
skipped="${test_root}/skipped"
make_base "${skipped}"
NAV2PILOT_PATCH="" enable_nav2pilot "${skipped}" | grep -q 'built without Nav2Pilot' || fail "skip ignored"
git -C "${skipped}" diff --cached --quiet || fail "skip staged changes"

echo "PASS: Nav2Pilot injected on the base, stopped on a conflict, skipped without a patch"
