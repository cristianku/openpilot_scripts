#!/usr/bin/env bash
set -euo pipefail

# [pinned source] - START
skill_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
wrapper="${skill_root}/scripts/setup_psa_torque.sh"
test_root="$(mktemp -d)"
trap 'rm -rf "${test_root}"' EXIT

fail() {
  echo "FAIL: $*" >&2
  exit 1
}

commit_fixture() {
  local repo="$1"
  local message="$2"
  git -C "${repo}" -c user.name=Test -c user.email=test@example.invalid commit -qm "${message}"
}

opendbc_repo="${test_root}/opendbc"
mkdir -p "${opendbc_repo}"
git -C "${opendbc_repo}" init -q
git -C "${opendbc_repo}" checkout -qb psa-torque-testing
printf '%s\n' 'fixture opendbc' > "${opendbc_repo}/README"
git -C "${opendbc_repo}" add README
commit_fixture "${opendbc_repo}" 'fixture opendbc'
opendbc_sha="$(git -C "${opendbc_repo}" rev-parse HEAD)"

source_repo="${test_root}/upstream-openpilot"
mkdir -p "${source_repo}/selfdrive/locationd" "${source_repo}/models"
git -C "${source_repo}" init -q
git -C "${source_repo}" checkout -qb master
printf '%s\n' 'ALLOWED_CARS = []' > "${source_repo}/selfdrive/locationd/torqued.py"
printf '%s\n' 'pinned revision' > "${source_repo}/revision.txt"
printf '%s\n' '*.onnx filter=lfs diff=lfs merge=lfs -text' > "${source_repo}/.gitattributes"
printf '%s\n' \
  'version https://git-lfs.github.com/spec/v1' \
  'oid sha256:0000000000000000000000000000000000000000000000000000000000000000' \
  'size 1' > "${source_repo}/models/model.onnx"
printf '[submodule "opendbc"]\n\tpath = opendbc_repo\n\turl = %s\n' "${opendbc_repo}" > "${source_repo}/.gitmodules"
git -C "${source_repo}" add .gitattributes .gitmodules models/model.onnx revision.txt selfdrive/locationd/torqued.py
git -C "${source_repo}" update-index --add --cacheinfo "160000,${opendbc_sha},opendbc_repo"
commit_fixture "${source_repo}" 'pinned upstream revision'
pinned_sha="$(git -C "${source_repo}" rev-parse HEAD)"
pinned_short_sha="${pinned_sha:0:8}"

printf '%s\n' 'newer master revision' > "${source_repo}/revision.txt"
printf '%s\n' \
  'version https://git-lfs.github.com/spec/v1' \
  'oid sha256:1111111111111111111111111111111111111111111111111111111111111111' \
  'size 1' > "${source_repo}/models/model.onnx"
git -C "${source_repo}" add models/model.onnx revision.txt
commit_fixture "${source_repo}" 'newer upstream revision'

target_repo="${test_root}/target-openpilot.git"
git init -q --bare "${target_repo}"

export GIT_AUTHOR_NAME=Test
export GIT_AUTHOR_EMAIL=test@example.invalid
export GIT_COMMITTER_NAME=Test
export GIT_COMMITTER_EMAIL=test@example.invalid

WORKSPACE_ROOT="${test_root}" \
OPENPILOT_DIR="generated-openpilot" \
OPENPILOT_REPO="${target_repo}" \
OPENPILOT_SOURCE_REPO="${source_repo}" \
OPENDBC_REPO="${opendbc_repo}" \
OPENDBC_SOURCE_REPO="${opendbc_repo}" \
NO_PUSH=true \
  "${wrapper}" comma "master=${pinned_short_sha}" >/dev/null

generated_repo="${test_root}/generated-openpilot"
[[ "$(git -C "${generated_repo}" show HEAD^:revision.txt)" == 'pinned revision' ]] \
  || fail "generated branch was not based on the requested master commit"

git -C "${generated_repo}" merge-base --is-ancestor "${pinned_sha}" master \
  || fail "requested commit is not from the selected upstream master history"

echo "PASS: testing setup pins an exact upstream master commit"
# [pinned source] - END
