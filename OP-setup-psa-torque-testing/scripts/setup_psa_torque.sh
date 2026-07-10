#!/usr/bin/env bash
set -euo pipefail

variant="${1:-comma}"

case "${variant}" in
  comma)
    branch="psa-torque-testing"
    source_branch="psa-torque"
    ;;
  sunny)
    branch="psa-torque-sunny-testing"
    source_branch="psa-torque-sunny"
    ;;
  *)
    echo "Usage: $0 [comma|sunny]" >&2
    exit 2
    ;;
esac

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
common_script="${script_dir}/setup_psa_torque_common.sh"

if [[ ! -f "${common_script}" ]]; then
  echo "ERROR: missing ${common_script}" >&2
  exit 1
fi

openpilot_source_repo="https://github.com/commaai/openpilot.git"
openpilot_source_branch="master"
use_custom_neural_network_data="false"

if [[ "${variant}" == "sunny" ]]; then
  openpilot_source_repo="https://github.com/sunnypilot/sunnypilot.git"
  openpilot_source_branch="master"
  use_custom_neural_network_data="true"
fi

BRANCH="${branch}" \
  OPENPILOT_SOURCE_REPO="${OPENPILOT_SOURCE_REPO:-${openpilot_source_repo}}" \
  OPENPILOT_SOURCE_BRANCH="${OPENPILOT_SOURCE_BRANCH:-${openpilot_source_branch}}" \
  OPENDBC_SOURCE_BRANCH="${OPENDBC_SOURCE_BRANCH:-${source_branch}}" \
  USE_CUSTOM_NEURAL_NETWORK_DATA="${use_custom_neural_network_data}" \
  bash "${common_script}"
