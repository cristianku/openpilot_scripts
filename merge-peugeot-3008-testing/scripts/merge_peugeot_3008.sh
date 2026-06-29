#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

STABLE_BRANCH="peugeot-3008" \
  TESTING_BRANCH="peugeot-3008-testing" \
  SETUP_VARIANT="comma" \
  MERGE_DIR="merge_opendbc_peugeot_3008" \
  COMMIT_MESSAGE="Merge peugeot-3008-testing into peugeot-3008" \
  /bin/bash "${script_dir}/merge_peugeot_3008_common.sh"
