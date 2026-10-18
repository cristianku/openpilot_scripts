#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

STABLE_BRANCH="psa-torque-sunny" \
  TESTING_BRANCH="psa-torque-sunny-testing" \
  MERGE_DIR="merge_opendbc_psa_torque_sunny" \
  COMMIT_MESSAGE="Merge psa-torque-sunny-testing into psa-torque-sunny" \
  /bin/bash "${script_dir}/merge_psa_torque_common.sh"
