#!/usr/bin/env bash
set -euo pipefail

BRANCH="${BRANCH:?BRANCH must be set}"
GITHUB_USER="${GITHUB_USER:-cristianku}"
WORKSPACE_ROOT="${WORKSPACE_ROOT:-/Users/cristianku/GitHub/COMMA.AI/CRISTIANKU}"

branch_suffix="${BRANCH#peugeot-3008}"
branch_suffix="${branch_suffix#-}"
dir_branch_suffix="${branch_suffix//-/_}"
dir_suffix="${dir_branch_suffix:+_${dir_branch_suffix}}"
title_suffix=""
if [[ -n "${branch_suffix}" ]]; then
  title_branch_suffix="${branch_suffix//-/ }"
title_suffix=" $(printf '%s' "${title_branch_suffix}" | awk '{ print toupper(substr($0, 1, 1)) substr($0, 2) }')"
fi

OPENPILOT_DIR="${OPENPILOT_DIR:-new_openpilot_peugeot_3008${dir_suffix}}"

OPENPILOT_REPO="${OPENPILOT_REPO:-https://github.com/${GITHUB_USER}/openpilot.git}"
OPENPILOT_SOURCE_REPO="${OPENPILOT_SOURCE_REPO:-https://github.com/commaai/openpilot.git}"
OPENPILOT_SOURCE_BRANCH="${OPENPILOT_SOURCE_BRANCH:-master}"
OPENDBC_REPO="${OPENDBC_REPO:-https://github.com/${GITHUB_USER}/opendbc.git}"
OPENDBC_SOURCE_REPO="${OPENDBC_SOURCE_REPO:-${OPENDBC_REPO}}"
OPENDBC_SOURCE_BRANCH="${OPENDBC_SOURCE_BRANCH:-}"
STEERING_NN_REPO="${STEERING_NN_REPO:-https://github.com/${GITHUB_USER}/sunny_steering_nn.git}"
STEERING_NN_BRANCH="${STEERING_NN_BRANCH:-main}"
STEERING_NN_MODELS_DIR="${STEERING_NN_MODELS_DIR:-models}"
COMMIT_MESSAGE="${COMMIT_MESSAGE:-Update Peugeot 3008${title_suffix} opendbc pointer and steering models}"

STEERING_NN_SOURCE_SHA=""
STEERING_NN_MODEL_COUNT=0

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

sync_steering_nn_models() {
  local dest="$1"
  local tmp_dir
  tmp_dir="$(mktemp -d)"

  echo "Checking ${STEERING_NN_REPO} ${STEERING_NN_BRANCH} for ${STEERING_NN_MODELS_DIR}/"
  if ! git clone --quiet --no-checkout --filter=blob:none --depth=1 --branch "${STEERING_NN_BRANCH}" \
    "${STEERING_NN_REPO}" "${tmp_dir}/repo"; then
    rm -rf "${tmp_dir}"
    echo "ERROR: failed to clone ${STEERING_NN_REPO} ${STEERING_NN_BRANCH}" >&2
    exit 1
  fi

  STEERING_NN_SOURCE_SHA="$(git -C "${tmp_dir}/repo" rev-parse HEAD)"
  if ! git -C "${tmp_dir}/repo" cat-file -e "HEAD:${STEERING_NN_MODELS_DIR}" 2>/dev/null; then
    echo "No ${STEERING_NN_MODELS_DIR}/ folder at ${STEERING_NN_SOURCE_SHA}; skipping steering models"
    rm -rf "${tmp_dir}"
    return
  fi

  if [[ "$(git -C "${tmp_dir}/repo" cat-file -t "HEAD:${STEERING_NN_MODELS_DIR}")" != "tree" ]]; then
    rm -rf "${tmp_dir}"
    echo "ERROR: ${STEERING_NN_MODELS_DIR} exists but is not a folder in ${STEERING_NN_REPO}" >&2
    exit 1
  fi

  git -C "${tmp_dir}/repo" sparse-checkout init --cone
  git -C "${tmp_dir}/repo" sparse-checkout set "${STEERING_NN_MODELS_DIR}"
  git -C "${tmp_dir}/repo" checkout --quiet

  local source_models="${tmp_dir}/repo/${STEERING_NN_MODELS_DIR}"
  STEERING_NN_MODEL_COUNT="$(find "${source_models}" -type f | wc -l | tr -d ' ')"
  if [[ "${STEERING_NN_MODEL_COUNT}" -eq 0 ]]; then
    echo "The ${STEERING_NN_MODELS_DIR}/ folder is empty; skipping steering models"
    rm -rf "${tmp_dir}"
    return
  fi

  mkdir -p "${dest}/models"
  cp -R "${source_models}/." "${dest}/models/"
  git -C "${dest}" add -- models

  local nnlc_helper="${dest}/sunnypilot/selfdrive/controls/lib/nnlc/helpers.py"
  if [[ -f "${nnlc_helper}" ]]; then
    perl -0pi -e 's#^TORQUE_NN_MODEL_PATH = .*#TORQUE_NN_MODEL_PATH = os.path.join(BASEDIR, "models")#m' "${nnlc_helper}"
    if ! grep -Fqx 'TORQUE_NN_MODEL_PATH = os.path.join(BASEDIR, "models")' "${nnlc_helper}"; then
      rm -rf "${tmp_dir}"
      echo "ERROR: failed to point sunnypilot NNLC to the copied models folder" >&2
      exit 1
    fi
    git -C "${dest}" add -- sunnypilot/selfdrive/controls/lib/nnlc/helpers.py
    echo "Pointing sunnypilot NNLC to ${dest}/models"
  fi

  if ! find "${dest}/models" -type f -name 'PSA_PEUGEOT_3008*.json' -print -quit | grep -q .; then
    echo "WARNING: copied models do not include PSA_PEUGEOT_3008*.json" >&2
  fi

  echo "Copied ${STEERING_NN_MODEL_COUNT} steering model file(s) from ${STEERING_NN_SOURCE_SHA}"
  rm -rf "${tmp_dir}"
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
    echo "No opendbc pointer changes to commit in ${dest}"
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

  set_opendbc_pointer "." "${OPENDBC_REPO}" "${BRANCH}" "${OPENDBC_SOURCE_REPO}" "${OPENDBC_SOURCE_BRANCH}"
  sync_steering_nn_models "."
  commit_and_push "." "${BRANCH}" "${COMMIT_MESSAGE}" "${expected_remote_sha}"

  echo
  echo "Ready:"
  echo "  ${WORKSPACE_ROOT}/${OPENPILOT_DIR}"
  echo "  ${WORKSPACE_ROOT}/${OPENPILOT_DIR}/opendbc_repo"
  if [[ "${STEERING_NN_MODEL_COUNT}" -gt 0 ]]; then
    echo "  ${WORKSPACE_ROOT}/${OPENPILOT_DIR}/models (${STEERING_NN_MODEL_COUNT} files from ${STEERING_NN_SOURCE_SHA})"
  fi
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
  main "$@"
fi
