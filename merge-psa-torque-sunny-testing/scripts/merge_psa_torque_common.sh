#!/usr/bin/env bash
set -euo pipefail

STABLE_BRANCH="${STABLE_BRANCH:?STABLE_BRANCH must be set}"
TESTING_BRANCH="${TESTING_BRANCH:?TESTING_BRANCH must be set}"

GITHUB_USER="${GITHUB_USER:-cristianku}"
WORKSPACE_ROOT="${WORKSPACE_ROOT:-/Users/cristianku/GitHub/COMMA.AI/CRISTIANKU}"
OPENDBC_REPO="${OPENDBC_REPO:-https://github.com/${GITHUB_USER}/opendbc.git}"
MERGE_DIR="${MERGE_DIR:-merge_opendbc_${STABLE_BRANCH//-/_}}"
COMMIT_MESSAGE="${COMMIT_MESSAGE:-Merge ${TESTING_BRANCH} into ${STABLE_BRANCH}}"
MAX_EXAMPLES="${MAX_EXAMPLES:-5}"
SKIP_TESTS="${SKIP_TESTS:-false}"

remote_branch_sha() {
  local branch="$1"
  git ls-remote --heads "${OPENDBC_REPO}" "refs/heads/${branch}" | awk 'NR == 1 { print $1 }'
}

run_tests() {
  local repo_dir="$1"

  if [[ "${SKIP_TESTS}" == "true" ]]; then
    echo "Skipping tests because SKIP_TESTS=true"
    return
  fi

  if [[ -n "${MERGE_TEST_COMMAND:-}" ]]; then
    echo "Running custom merge test command"
    (
      cd "${repo_dir}"
      /bin/bash -lc "${MERGE_TEST_COMMAND}"
    )
    return
  fi

  if ! command -v uv >/dev/null 2>&1; then
    echo "ERROR: uv is required to provision the clean merge test environment" >&2
    exit 1
  fi

  local uv_cache_dir="${UV_CACHE_DIR:-/tmp/uv-cache-merge-psa-torque}"
  local -a uv_test=(uv run --no-default-groups --with pytest --with "hypothesis==6.47.*" --with cffi python -m pytest -q)

  echo "Running PSA interface tests"
  (
    cd "${repo_dir}"
    UV_CACHE_DIR="${uv_cache_dir}" MAX_EXAMPLES="${MAX_EXAMPLES}" "${uv_test[@]}" \
      opendbc/car/tests/test_car_interfaces.py -k PSA_PEUGEOT_3008
  )

  echo "Running PSA safety tests"
  (
    cd "${repo_dir}"
    UV_CACHE_DIR="${uv_cache_dir}" "${uv_test[@]}" opendbc/safety/tests/test_psa.py
  )
}

main() {
  local stable_sha
  local testing_sha
  stable_sha="$(remote_branch_sha "${STABLE_BRANCH}")"
  testing_sha="$(remote_branch_sha "${TESTING_BRANCH}")"

  if [[ ! "${stable_sha}" =~ ^[0-9a-fA-F]{40}$ ]]; then
    echo "ERROR: missing remote branch ${STABLE_BRANCH} in ${OPENDBC_REPO}" >&2
    exit 1
  fi

  if [[ ! "${testing_sha}" =~ ^[0-9a-fA-F]{40}$ ]]; then
    echo "ERROR: missing remote branch ${TESTING_BRANCH} in ${OPENDBC_REPO}" >&2
    exit 1
  fi

  mkdir -p "${WORKSPACE_ROOT}"
  cd "${WORKSPACE_ROOT}"

  if [[ -z "${MERGE_DIR}" || "${MERGE_DIR}" == "/" || "${MERGE_DIR}" == "." ]]; then
    echo "ERROR: refusing to recreate unsafe merge directory: ${MERGE_DIR}" >&2
    exit 1
  fi

  if [[ -e "${MERGE_DIR}" ]]; then
    echo "Recreating ${MERGE_DIR}"
    rm -rf "${MERGE_DIR}"
  fi

  echo "Cloning ${STABLE_BRANCH} from ${OPENDBC_REPO}"
  git clone --no-tags --single-branch --branch "${STABLE_BRANCH}" "${OPENDBC_REPO}" "${MERGE_DIR}"
  git -C "${MERGE_DIR}" fetch --no-tags origin     "refs/heads/${TESTING_BRANCH}:refs/remotes/origin/${TESTING_BRANCH}"

  if git -C "${MERGE_DIR}" merge-base --is-ancestor "origin/${TESTING_BRANCH}" HEAD; then
    echo "${TESTING_BRANCH} is already merged into ${STABLE_BRANCH}"
  else
    echo "Merging ${TESTING_BRANCH} into ${STABLE_BRANCH}"
    git -C "${MERGE_DIR}" merge --no-ff --no-commit "origin/${TESTING_BRANCH}"
    git -C "${MERGE_DIR}" diff --cached --check
    run_tests "${MERGE_DIR}"
    git -C "${MERGE_DIR}" commit -m "${COMMIT_MESSAGE}"
    git -C "${MERGE_DIR}" push       --force-with-lease="refs/heads/${STABLE_BRANCH}:${stable_sha}" origin "${STABLE_BRANCH}"
  fi

  echo
  echo "Ready:"
  echo "  opendbc ${TESTING_BRANCH} -> ${STABLE_BRANCH}"
  echo "  merge workspace: ${WORKSPACE_ROOT}/${MERGE_DIR}"
}

main "$@"
