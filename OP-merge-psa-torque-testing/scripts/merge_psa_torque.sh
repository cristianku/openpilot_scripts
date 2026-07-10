#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

STABLE_BRANCH="psa-torque" \
  TESTING_BRANCH="psa-torque-testing" \
  SETUP_VARIANT="comma" \
  MERGE_DIR="merge_opendbc_psa_torque" \
  COMMIT_MESSAGE="Merge psa-torque-testing into psa-torque" \
  /bin/bash "${script_dir}/merge_psa_torque_common.sh"
