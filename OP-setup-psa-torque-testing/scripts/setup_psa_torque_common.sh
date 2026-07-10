#!/usr/bin/env bash
set -euo pipefail

BRANCH="${BRANCH:?BRANCH must be set}"
GITHUB_USER="${GITHUB_USER:-cristianku}"
WORKSPACE_ROOT="${WORKSPACE_ROOT:-/Users/cristianku/GitHub/COMMA.AI/CRISTIANKU}"

branch_suffix="${BRANCH#psa-torque}"
branch_suffix="${branch_suffix#-}"
dir_branch_suffix="${branch_suffix//-/_}"
dir_suffix="${dir_branch_suffix:+_${dir_branch_suffix}}"
title_suffix=""
if [[ -n "${branch_suffix}" ]]; then
  title_branch_suffix="${branch_suffix//-/ }"
title_suffix=" $(printf '%s' "${title_branch_suffix}" | awk '{ print toupper(substr($0, 1, 1)) substr($0, 2) }')"
fi

OPENPILOT_DIR="${OPENPILOT_DIR:-new_openpilot_psa_torque${dir_suffix}}"

OPENPILOT_REPO="${OPENPILOT_REPO:-https://github.com/${GITHUB_USER}/openpilot.git}"
OPENPILOT_SOURCE_REPO="${OPENPILOT_SOURCE_REPO:-https://github.com/commaai/openpilot.git}"
OPENPILOT_SOURCE_BRANCH="${OPENPILOT_SOURCE_BRANCH:-master}"
OPENDBC_REPO="${OPENDBC_REPO:-https://github.com/${GITHUB_USER}/opendbc.git}"
OPENDBC_SOURCE_REPO="${OPENDBC_SOURCE_REPO:-${OPENDBC_REPO}}"
OPENDBC_SOURCE_BRANCH="${OPENDBC_SOURCE_BRANCH:-}"
USE_CUSTOM_NEURAL_NETWORK_DATA="${USE_CUSTOM_NEURAL_NETWORK_DATA:-false}"
NEURAL_NETWORK_DATA_REPO="${NEURAL_NETWORK_DATA_REPO:-https://github.com/${GITHUB_USER}/neural-network-data.git}"
NEURAL_NETWORK_DATA_BRANCH="${NEURAL_NETWORK_DATA_BRANCH:-master}"
COMMIT_MESSAGE="${COMMIT_MESSAGE:-Update Peugeot 3008${title_suffix} repository pointers}"

NEURAL_NETWORK_DATA_SHA=""

ensure_remote_branch() {
  local repo_url="$1"
  local branch="$2"
  local source_repo_url="${3:-}"
  local source_branch="${4:-}"

  if git ls-remote --exit-code --heads "${repo_url}" "${branch}" >/dev/null 2>&1; then
    return
  fi

  if [[ -z "${source_repo_url}" ]]; then
    source_repo_url="${repo_url}"
  fi

  if [[ -z "${source_branch}" ]]; then
    source_branch="$(
      git ls-remote --symref "${source_repo_url}" HEAD \
        | awk '/^ref:/ { sub("refs/heads/", "", $2); print $2; exit }'
    )"
  fi

  if [[ -z "${source_branch}" ]]; then
    echo "ERROR: could not determine source branch for ${source_repo_url}" >&2
    exit 1
  fi

  local tmp_dir
  tmp_dir="$(mktemp -d)"

  echo "Remote branch ${branch} does not exist in ${repo_url}; creating from ${source_repo_url} ${source_branch}"
  if ! (
    git clone --no-tags --single-branch --branch "${source_branch}" "${source_repo_url}" "${tmp_dir}/repo"
    git -C "${tmp_dir}/repo" checkout -b "${branch}"
    git -C "${tmp_dir}/repo" remote add target "${repo_url}"
    GIT_LFS_SKIP_PUSH=1 git -C "${tmp_dir}/repo" push target "${branch}"
  ); then
    rm -rf "${tmp_dir}"
    echo "ERROR: failed to create remote branch ${branch} in ${repo_url}" >&2
    exit 1
  fi

  rm -rf "${tmp_dir}"
}

recreate_clone_from_source() {
  local target_repo_url="$1"
  local dest="$2"
  local branch="$3"
  local source_repo_url="$4"
  local source_branch="$5"

  if [[ -z "${dest}" || "${dest}" == "/" || "${dest}" == "." ]]; then
    echo "ERROR: refusing to recreate unsafe destination: ${dest}" >&2
    exit 1
  fi

  if [[ -e "${dest}" ]]; then
    echo "Recreating ${dest} directly from ${source_repo_url} ${source_branch}"
    rm -rf "${dest}"
  fi

  GIT_LFS_SKIP_SMUDGE=1 git clone --no-tags --single-branch --branch "${source_branch}" "${source_repo_url}" "${dest}"
  local source_commit
  source_commit="$(git -C "${dest}" rev-parse HEAD)"
  echo "Using upstream source commit ${source_commit}"
  git -C "${dest}" checkout -B "${branch}"
  git -C "${dest}" remote rename origin source
  git -C "${dest}" remote add origin "${target_repo_url}"
}

set_opendbc_pointer() {
  local dest="$1"
  local repo_url="$2"
  local branch="$3"
  local source_repo_url="${4:-}"
  local source_branch="${5:-}"

  ensure_remote_branch "${repo_url}" "${branch}" "${source_repo_url}" "${source_branch}"

  local opendbc_sha
  opendbc_sha="$(git ls-remote --heads "${repo_url}" "refs/heads/${branch}" | awk 'NR == 1 { print $1 }')"
  if [[ ! "${opendbc_sha}" =~ ^[0-9a-fA-F]{40}$ ]]; then
    echo "ERROR: could not resolve ${repo_url} ${branch}" >&2
    exit 1
  fi

  git -C "${dest}" config --file .gitmodules submodule.opendbc.url "${repo_url}"
  git -C "${dest}" add -- .gitmodules
  git -C "${dest}" update-index --add --cacheinfo "160000,${opendbc_sha},opendbc_repo"
  echo "Pointing opendbc_repo to ${repo_url} ${branch} (${opendbc_sha})"
}

set_neural_network_data_pointer() {
  local dest="$1"
  if [[ "${USE_CUSTOM_NEURAL_NETWORK_DATA}" != "true" ]]; then
    return
  fi

  local submodule_path="sunnypilot/neural_network_data"
  if ! git -C "${dest}" ls-files --stage -- "${submodule_path}" | awk '$1 == "160000" { found = 1 } END { exit !found }'; then
    echo "ERROR: ${submodule_path} is not a submodule in ${dest}" >&2
    exit 1
  fi

  NEURAL_NETWORK_DATA_SHA="$(git ls-remote --heads "${NEURAL_NETWORK_DATA_REPO}" "refs/heads/${NEURAL_NETWORK_DATA_BRANCH}" | awk 'NR == 1 { print $1 }')"
  if [[ ! "${NEURAL_NETWORK_DATA_SHA}" =~ ^[0-9a-fA-F]{40}$ ]]; then
    echo "ERROR: could not resolve ${NEURAL_NETWORK_DATA_REPO} ${NEURAL_NETWORK_DATA_BRANCH}" >&2
    exit 1
  fi

  git -C "${dest}" config --file .gitmodules submodule.sunnypilot/neural_network_data.url "${NEURAL_NETWORK_DATA_REPO}"
  git -C "${dest}" add -- .gitmodules
  git -C "${dest}" update-index --add --cacheinfo "160000,${NEURAL_NETWORK_DATA_SHA},${submodule_path}"
  echo "Pointing ${submodule_path} to ${NEURAL_NETWORK_DATA_REPO} ${NEURAL_NETWORK_DATA_BRANCH} (${NEURAL_NETWORK_DATA_SHA})"
}

enable_psa_torqued_learning() {
  # A fresh clone of upstream master ships torqued's ALLOWED_CARS gate without
  # PSA, so torqued (live latAccelFactor/friction learning) stays disabled for
  # the Peugeot 3008. Add 'psa' so the learner runs on the port. Idempotent.
  local dest="$1"
  local torqued="${dest}/selfdrive/locationd/torqued.py"

  if [[ ! -f "${torqued}" ]]; then
    echo "ERROR: torqued.py not found at ${torqued}" >&2
    exit 1
  fi

  if grep -Eq "^ALLOWED_CARS *=.*['\"]psa['\"]" "${torqued}"; then
    echo "torqued ALLOWED_CARS already includes psa; nothing to do"
    return
  fi

  if ! grep -Eq "^ALLOWED_CARS *= *\[.*\]" "${torqued}"; then
    echo "ERROR: could not find ALLOWED_CARS list in ${torqued}" >&2
    exit 1
  fi

  sed -i.bak -E "s/^(ALLOWED_CARS *= *\[[^]]*)\]/\1, 'psa']/" "${torqued}"
  rm -f "${torqued}.bak"

  if ! grep -Eq "^ALLOWED_CARS *=.*['\"]psa['\"]" "${torqued}"; then
    echo "ERROR: failed to add psa to ALLOWED_CARS in ${torqued}" >&2
    exit 1
  fi

  git -C "${dest}" add -- selfdrive/locationd/torqued.py
  echo "Enabled PSA torque-param learning (added 'psa' to torqued ALLOWED_CARS)"
}

commit_and_push() {
  local dest="$1"
  local branch="$2"
  local message="$3"
  local expected_remote_sha="$4"

  if git -C "${dest}" diff --cached --quiet; then
    if [[ "$(git -C "${dest}" rev-parse HEAD)" != "${expected_remote_sha}" ]]; then
      echo "Updating ${branch} from the current upstream master"
      GIT_LFS_SKIP_PUSH=1 git -C "${dest}" push \
        --force-with-lease="refs/heads/${branch}:${expected_remote_sha}" origin "${branch}"
      return
    fi
    echo "No repository pointer changes to commit in ${dest}"
    return
  fi

  echo "Committing changes in ${dest}"
  git -C "${dest}" commit -m "${message}"
  GIT_LFS_SKIP_PUSH=1 git -C "${dest}" push \
    --force-with-lease="refs/heads/${branch}:${expected_remote_sha}" origin "${branch}"
}

main() {
  mkdir -p "${WORKSPACE_ROOT}"
  cd "${WORKSPACE_ROOT}"

  local expected_remote_sha
  expected_remote_sha="$(git ls-remote --heads "${OPENPILOT_REPO}" "refs/heads/${BRANCH}" | awk 'NR == 1 { print $1 }')"
  recreate_clone_from_source "${OPENPILOT_REPO}" "${OPENPILOT_DIR}" "${BRANCH}" \
    "${OPENPILOT_SOURCE_REPO}" "${OPENPILOT_SOURCE_BRANCH}"

  cd "${OPENPILOT_DIR}"

  enable_psa_torqued_learning "."
  set_opendbc_pointer "." "${OPENDBC_REPO}" "${BRANCH}" "${OPENDBC_SOURCE_REPO}" "${OPENDBC_SOURCE_BRANCH}"
  set_neural_network_data_pointer "."
  commit_and_push "." "${BRANCH}" "${COMMIT_MESSAGE}" "${expected_remote_sha}"

  echo
  echo "Ready:"
  echo "  ${WORKSPACE_ROOT}/${OPENPILOT_DIR}"
  echo "  ${WORKSPACE_ROOT}/${OPENPILOT_DIR}/opendbc_repo"
  if [[ "${USE_CUSTOM_NEURAL_NETWORK_DATA}" == "true" ]]; then
    echo "  ${WORKSPACE_ROOT}/${OPENPILOT_DIR}/sunnypilot/neural_network_data (${NEURAL_NETWORK_DATA_BRANCH} at ${NEURAL_NETWORK_DATA_SHA})"
  fi
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
  main "$@"
fi
