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
OPENPILOT_RELEASE_BRANCH="${OPENPILOT_RELEASE_BRANCH:-}"
RECREATE_OPENPILOT_FROM_RELEASE="${RECREATE_OPENPILOT_FROM_RELEASE:-false}"
OPENDBC_REPO="${OPENDBC_REPO:-https://github.com/${GITHUB_USER}/opendbc.git}"
OPENDBC_SOURCE_REPO="${OPENDBC_SOURCE_REPO:-${OPENDBC_REPO}}"
OPENDBC_SOURCE_BRANCH="${OPENDBC_SOURCE_BRANCH:-}"
COMMIT_MESSAGE="${COMMIT_MESSAGE:-Update Peugeot 3008${title_suffix} opendbc integration}"

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

materialize_branch_tree() {
  local repo_url="$1"
  local dest="$2"
  local branch="$3"
  local source_repo_url="${4:-}"
  local source_branch="${5:-}"

  ensure_remote_branch "${repo_url}" "${branch}" "${source_repo_url}" "${source_branch}"

  echo "Materializing ${repo_url} ${branch} -> ${dest}"
  rm -rf "${dest}"
  git clone --no-tags --branch "${branch}" --single-branch "${repo_url}" "${dest}"
  rm -rf "${dest}/.git"
}

recreate_clone() {
  local repo_url="$1"
  local dest="$2"
  local branch="$3"
  local source_repo_url="${4:-}"
  local source_branch="${5:-}"

  ensure_remote_branch "${repo_url}" "${branch}" "${source_repo_url}" "${source_branch}"

  if [[ -z "${dest}" || "${dest}" == "/" || "${dest}" == "." ]]; then
    echo "ERROR: refusing to recreate unsafe destination: ${dest}" >&2
    exit 1
  fi

  if [[ -e "${dest}" ]]; then
    echo "Recreating ${dest}"
    rm -rf "${dest}"
  fi

  echo "Cloning ${repo_url} -> ${dest}"
  git clone --branch "${branch}" --single-branch "${repo_url}" "${dest}"
}

recreate_clone_from_release_source() {
  local target_repo_url="$1"
  local dest="$2"
  local branch="$3"
  local source_repo_url="$4"
  local release_branch="$5"

  if [[ -z "${release_branch}" ]]; then
    echo "ERROR: OPENPILOT_RELEASE_BRANCH is required when recreating from a release source" >&2
    exit 1
  fi

  if [[ -z "${dest}" || "${dest}" == "/" || "${dest}" == "." ]]; then
    echo "ERROR: refusing to recreate unsafe destination: ${dest}" >&2
    exit 1
  fi

  if [[ -e "${dest}" ]]; then
    echo "Recreating ${dest} directly from ${source_repo_url} ${release_branch}"
    rm -rf "${dest}"
  fi

  git clone --no-tags --single-branch --branch "${release_branch}" "${source_repo_url}" "${dest}"
  local source_commit
  source_commit="$(git -C "${dest}" rev-parse HEAD)"
  echo "Using upstream release commit ${source_commit}"
  git -C "${dest}" checkout -B "${branch}"
  git -C "${dest}" remote rename origin source
  git -C "${dest}" remote add origin "${target_repo_url}"
}

commit_and_push() {
  local dest="$1"
  local branch="$2"
  local message="$3"
  local force_with_lease="$4"
  local expected_remote_sha="$5"
  shift 5
  local paths=("$@")

  if [[ -z "$(git -C "${dest}" status --porcelain -- "${paths[@]}")" ]]; then
    if [[ "${force_with_lease}" == "true" ]] && \
       [[ "$(git -C "${dest}" rev-parse HEAD)" != "${expected_remote_sha}" ]]; then
      echo "Updating ${branch} from the current upstream release"
      GIT_LFS_SKIP_PUSH=1 git -C "${dest}" push \
        --force-with-lease="refs/heads/${branch}:${expected_remote_sha}" origin "${branch}"
      return
    fi
    echo "No opendbc integration changes to commit in ${dest}"
    return
  fi

  echo "Committing changes in ${dest}"
  git -C "${dest}" add -- "${paths[@]}"
  git -C "${dest}" commit -m "${message}"
  if [[ "${force_with_lease}" == "true" ]]; then
    GIT_LFS_SKIP_PUSH=1 git -C "${dest}" push \
      --force-with-lease="refs/heads/${branch}:${expected_remote_sha}" origin "${branch}"
  else
    GIT_LFS_SKIP_PUSH=1 git -C "${dest}" push origin "${branch}"
  fi
}

main() {
  mkdir -p "${WORKSPACE_ROOT}"
  cd "${WORKSPACE_ROOT}"

  local expected_remote_sha=""
  if [[ "${RECREATE_OPENPILOT_FROM_RELEASE}" == "true" ]]; then
    expected_remote_sha="$(git ls-remote --heads "${OPENPILOT_REPO}" "refs/heads/${BRANCH}" | awk 'NR == 1 { print $1 }')"
    recreate_clone_from_release_source "${OPENPILOT_REPO}" "${OPENPILOT_DIR}" "${BRANCH}" \
      "${OPENPILOT_SOURCE_REPO}" "${OPENPILOT_RELEASE_BRANCH}"
  else
    recreate_clone "${OPENPILOT_REPO}" "${OPENPILOT_DIR}" "${BRANCH}" "${OPENPILOT_SOURCE_REPO}" "${OPENPILOT_SOURCE_BRANCH}"
  fi

  cd "${OPENPILOT_DIR}"

  materialize_branch_tree "${OPENDBC_REPO}" "opendbc_repo" "${BRANCH}" "${OPENDBC_SOURCE_REPO}" "${OPENDBC_SOURCE_BRANCH}"

  commit_and_push "." "${BRANCH}" "${COMMIT_MESSAGE}" "${RECREATE_OPENPILOT_FROM_RELEASE}" "${expected_remote_sha}" \
    "opendbc_repo"

  echo
  echo "Ready:"
  echo "  ${WORKSPACE_ROOT}/${OPENPILOT_DIR}"
  echo "  ${WORKSPACE_ROOT}/${OPENPILOT_DIR}/opendbc_repo"
}

main "$@"
