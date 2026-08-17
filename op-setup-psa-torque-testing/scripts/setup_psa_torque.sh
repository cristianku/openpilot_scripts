#!/usr/bin/env bash
set -euo pipefail

variant="${1:-comma}"
source_mode="${2:-master}"

case "${variant}" in
  comma|openpilot)
    variant="comma"
    branch="psa-torque-testing"
    source_branch="psa-torque"
    ;;
  sunny|sunnypilot)
    variant="sunny"
    branch="psa-torque-sunny-testing"
    source_branch="psa-torque-sunny"
    ;;
  *)
    echo "Usage: $0 [comma|openpilot|sunny|sunnypilot] [master|release]" >&2
    exit 2
    ;;
esac

case "${source_mode}" in
  master|release)
    ;;
  *)
    echo "Usage: $0 [comma|openpilot|sunny|sunnypilot] [master|release]" >&2
    exit 2
    ;;
esac

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
common_script="${script_dir}/setup_psa_torque_common.sh"

if [[ ! -f "${common_script}" ]]; then
  echo "ERROR: missing ${common_script}" >&2
  exit 1
fi

# [source] - START
# Default to master for the selected upstream. Release mode resolves the latest
# published GitHub Release tag at execution time.
resolve_latest_release_tag() {
  local repo_url="$1"
  local github_repo="${repo_url#https://github.com/}"
  github_repo="${github_repo%.git}"
  local release_tag

  release_tag="$(curl --fail --silent --show-error --location \
    "https://api.github.com/repos/${github_repo}/releases/latest" \
    | python3 -c 'import json, sys; tag = json.load(sys.stdin).get("tag_name"); assert tag; print(tag)')"

  if ! git ls-remote --exit-code --tags "${repo_url}" "refs/tags/${release_tag}" >/dev/null; then
    echo "ERROR: latest GitHub release tag ${release_tag} is unavailable in ${repo_url}" >&2
    exit 1
  fi

  printf '%s\n' "${release_tag}"
}

openpilot_source_repo="https://github.com/commaai/openpilot.git"
openpilot_source_branch="master"
use_custom_neural_network_data="false"

if [[ "${variant}" == "sunny" ]]; then
  openpilot_source_repo="https://github.com/sunnypilot/sunnypilot.git"
  openpilot_source_branch="master"
  use_custom_neural_network_data="true"
fi

openpilot_source_repo="${OPENPILOT_SOURCE_REPO:-${openpilot_source_repo}}"
if [[ "${source_mode}" == "release" ]]; then
  openpilot_source_branch="$(resolve_latest_release_tag "${openpilot_source_repo}")"
else
  openpilot_source_branch="${OPENPILOT_SOURCE_BRANCH:-${openpilot_source_branch}}"
fi
# [source] - END

BRANCH="${branch}" \
  OPENPILOT_SOURCE_REPO="${openpilot_source_repo}" \
  OPENPILOT_SOURCE_BRANCH="${openpilot_source_branch}" \
  OPENDBC_SOURCE_BRANCH="${OPENDBC_SOURCE_BRANCH:-${source_branch}}" \
  USE_CUSTOM_NEURAL_NETWORK_DATA="${use_custom_neural_network_data}" \
  bash "${common_script}"
