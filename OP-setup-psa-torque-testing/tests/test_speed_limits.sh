#!/usr/bin/env bash
# enable_speed_limits: the speed-limits branch of cristianku/sunnypilot is applied over the PSA/Nav2Pilot checkout
# (its files and its models submodule pointer, staged), only once, never on a source without Speed Limit Assist,
# skipped with SKIP_SPEED_LIMITS=true, and the setup stops on a conflict instead of publishing.
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

resolver=openpilot/sunnypilot/selfdrive/controls/lib/speed_limit/speed_limit_resolver.py

# SunnyPilot master.
upstream="${test_root}/sunnypilot-upstream"
mkdir -p "${upstream}/$(dirname "${resolver}")" "${upstream}/openpilot/selfdrive/ui"
printf '%s\n' 'POLICIES = ["car", "map"]' 'def resolve(car, map):' '  return car or map' > "${upstream}/${resolver}"
printf '%s\n' 'ui = "upstream"' > "${upstream}/openpilot/selfdrive/ui/ui.py"
printf '%s\n' '[submodule "opendbc"]' '  path = opendbc_repo' '  url = https://example.invalid/opendbc.git' > "${upstream}/.gitmodules"
git_test -C "${upstream}" init -q
git_test -C "${upstream}" add -- .
git_test -C "${upstream}" commit -qm 'sunnypilot master'

# cristianku/sunnypilot:speed-limits, from that master: a resolver change, a new file and the models submodule.
source_repo="${test_root}/sunnypilot-fork"
git_test clone -q "${upstream}" "${source_repo}"
git_test -C "${source_repo}" checkout -qb speed-limits
printf '%s\n' 'POLICIES = ["car", "map"]' 'SIGN_READER = "SpeedLimitSignReader"' 'def resolve(car, map):' '  return car or map' \
  > "${source_repo}/${resolver}"
printf '%s\n' 'speed vision' > "${source_repo}/openpilot/selfdrive/ui/speed_vision.py"
printf '%s\n' '[submodule "sunnypilot/speed_limits/models"]' '  path = openpilot/sunnypilot/speed_limits/models' \
  '  url = https://github.com/cristianku/speed-limits-models.git' >> "${source_repo}/.gitmodules"
models_sha=79d691449fd0565f293dac65dc23fa3559128560
git_test -C "${source_repo}" add -- .
git_test -C "${source_repo}" update-index --add --cacheinfo "160000,${models_sha},openpilot/sunnypilot/speed_limits/models"
git_test -C "${source_repo}" commit -qm 'speed limits'

# The setup's checkout: master plus a Nav2Pilot change elsewhere.
make_checkout() {
  local dest="$1"
  git_test clone -q "${upstream}" "${dest}"
  printf '%s\n' 'ui = "nav2pilot"' > "${dest}/openpilot/selfdrive/ui/ui.py"
  git_test -C "${dest}" commit -qam 'Nav2Pilot'
  git -C "${dest}" config user.name Test
  git -C "${dest}" config user.email test@example.invalid
}

SPEED_LIMITS_SOURCE_REPO="${source_repo}"
SPEED_LIMITS_SOURCE_BRANCH="speed-limits"
SPEED_LIMITS_UPSTREAM_REPO="${upstream}"
BRANCH="psa-torque-sunny-testing"
OPENPILOT_SOURCE_REPO="${upstream}"
OPENPILOT_SOURCE_BRANCH="master"
# shellcheck disable=SC1090
source "${common_script}"

# Applied: files and the submodule pointer, staged; the Nav2Pilot change kept.
checkout="${test_root}/checkout"
make_checkout "${checkout}"
enable_speed_limits "${checkout}" > /dev/null
git -C "${checkout}" diff --cached --quiet && fail "nothing staged"
grep -q SpeedLimitSignReader "${checkout}/${resolver}" || fail "resolver change missing"
[[ -f "${checkout}/openpilot/selfdrive/ui/speed_vision.py" ]] || fail "new file missing"
grep -q 'ui = "nav2pilot"' "${checkout}/openpilot/selfdrive/ui/ui.py" || fail "Nav2Pilot change lost"
grep -q 'cristianku/speed-limits-models' "${checkout}/.gitmodules" || fail ".gitmodules entry missing"
pointer="$(git -C "${checkout}" ls-files --stage -- openpilot/sunnypilot/speed_limits/models | awk '{print $1, $2}')"
[[ "${pointer}" == "160000 ${models_sha}" ]] || fail "models submodule pointer is '${pointer}'"

# Once only: a second run changes nothing.
git -C "${checkout}" commit -qm 'setup'
enable_speed_limits "${checkout}" | grep -q 'already in this checkout' || fail "applied twice"
git -C "${checkout}" diff --cached --quiet || fail "second run staged changes"

# Skipped on request.
skipped="${test_root}/skipped"
make_checkout "${skipped}"
SKIP_SPEED_LIMITS=true enable_speed_limits "${skipped}" | grep -q 'SKIP_SPEED_LIMITS set' || fail "skip ignored"
SKIP_SPEED_LIMITS=false
git -C "${skipped}" diff --cached --quiet || fail "skip staged changes"

# A source without Speed Limit Assist (comma.ai): nothing to do.
comma="${test_root}/comma"
make_checkout "${comma}"
git -C "${comma}" rm -q -- "${resolver}"
git -C "${comma}" commit -qm 'no sunnypilot'
enable_speed_limits "${comma}" | grep -q 'not needed' || fail "applied without Speed Limit Assist"

# A conflict on the same lines: the setup stops (exit 1), nothing to publish.
conflict="${test_root}/conflict"
make_checkout "${conflict}"
printf '%s\n' 'POLICIES = ["car", "map", "other"]' 'SIGN_READER = "something else"' 'def resolve(car, map):' '  return map' \
  > "${conflict}/${resolver}"
git -C "${conflict}" commit -qam 'conflicting change'
if (enable_speed_limits "${conflict}" > /dev/null 2>&1); then
  fail "a conflict did not stop the setup"
fi

echo "PASS: speed limits applied once, with the models submodule, skipped on request, stopped on a conflict"
