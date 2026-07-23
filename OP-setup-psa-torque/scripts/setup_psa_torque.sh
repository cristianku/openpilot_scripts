#!/usr/bin/env bash
set -euo pipefail

variant="${1:-comma}"

case "${variant}" in
  comma)
    branch="psa-torque"
    source_branch="psa-torque-testing"
    ;;
  sunny)
    branch="psa-torque-sunny"
    source_branch="psa-torque-sunny-testing"
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

# Source is a FROZEN stable release TAG (submodule-pointer mechanism, builds on
# device), NOT master HEAD. master HEAD kept breaking the device (stuck on logo,
# 2026-07-23) because it moves under us mid-upstream-changes. The TAG is the
# full buildable SOURCE of a shipped release: SConstruct + submodules + NO
# prebuilt marker, so the device compiles our torque-based psa.h on first boot,
# on a known-good frozen base. NOT the prebuilt release-mici branch (it strips
# SConstruct). Bump these tags to move to a newer stable release.
openpilot_source_repo="https://github.com/commaai/openpilot.git"
openpilot_source_branch="v0.11.1"
use_custom_neural_network_data="false"

if [[ "${variant}" == "sunny" ]]; then
  openpilot_source_repo="https://github.com/sunnypilot/sunnypilot.git"
  openpilot_source_branch="v2026.002.001"
  use_custom_neural_network_data="true"
fi

BRANCH="${branch}" \
  OPENPILOT_SOURCE_REPO="${OPENPILOT_SOURCE_REPO:-${openpilot_source_repo}}" \
  OPENPILOT_SOURCE_BRANCH="${OPENPILOT_SOURCE_BRANCH:-${openpilot_source_branch}}" \
  OPENDBC_SOURCE_BRANCH="${OPENDBC_SOURCE_BRANCH:-${source_branch}}" \
  USE_CUSTOM_NEURAL_NETWORK_DATA="${use_custom_neural_network_data}" \
  bash "${common_script}"
