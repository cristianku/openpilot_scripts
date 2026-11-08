#!/usr/bin/env bash
# SKIP_OPENDBC and SKIP_PSA_TORQUED (OP-setup-sunny-full-res): opendbc_repo and torqued stay upstream's, nothing staged;
# without them the PSA pointer and the torqued patch are still made.
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

upstream_opendbc=1111111111111111111111111111111111111111
make_checkout() {
  local dest="$1"
  mkdir -p "${dest}/openpilot/selfdrive/locationd"
  printf '%s\n' "ALLOWED_CARS = ['toyota', 'hyundai']" > "${dest}/openpilot/selfdrive/locationd/torqued.py"
  printf '%s\n' '[submodule "opendbc"]' '  path = opendbc_repo' '  url = https://github.com/sunnypilot/opendbc.git' \
    > "${dest}/.gitmodules"
  git_test -C "${dest}" init -q
  git_test -C "${dest}" add -- .
  git_test -C "${dest}" update-index --add --cacheinfo "160000,${upstream_opendbc},opendbc_repo"
  git_test -C "${dest}" commit -qm 'upstream'
}

# A local opendbc fork with the branch the pointer follows.
opendbc="${test_root}/opendbc"
mkdir -p "${opendbc}"
git_test -C "${opendbc}" init -q
git_test -C "${opendbc}" commit -q --allow-empty -m 'psa'
git_test -C "${opendbc}" branch -q psa-torque-sunny-testing

run() {
  local dest="$1"
  shift
  (
    export BRANCH=psa-torque-sunny-testing OPENPILOT_SOURCE_REPO=unused OPENPILOT_SOURCE_BRANCH=master "$@"
    # shellcheck disable=SC1090
    source "${common_script}"
    enable_psa_torqued_learning "${dest}"
    set_opendbc_pointer "${dest}" "${opendbc}" psa-torque-sunny-testing
  )
}

skipped="${test_root}/skipped"
make_checkout "${skipped}"
run "${skipped}" SKIP_OPENDBC=true SKIP_PSA_TORQUED=true >/dev/null
git -C "${skipped}" diff --cached --quiet || fail "SKIP_OPENDBC/SKIP_PSA_TORQUED staged changes"
git -C "${skipped}" diff --quiet -- openpilot/selfdrive/locationd/torqued.py .gitmodules \
  || fail "SKIP_PSA_TORQUED changed torqued.py"
[[ "$(git -C "${skipped}" ls-files --stage opendbc_repo | awk '{ print $2 }')" == "${upstream_opendbc}" ]] \
  || fail "opendbc_repo moved with SKIP_OPENDBC"

psa="${test_root}/psa"
make_checkout "${psa}"
run "${psa}" >/dev/null
grep -q "'psa'" "${psa}/openpilot/selfdrive/locationd/torqued.py" || fail "torqued not patched by default"
[[ "$(git -C "${psa}" ls-files --stage opendbc_repo | awk '{ print $2 }')" == "$(git -C "${opendbc}" rev-parse HEAD)" ]] \
  || fail "opendbc_repo not pointed to the fork by default"

echo "PASS: SKIP_OPENDBC and SKIP_PSA_TORQUED leave upstream as it is"
