#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

STABLE_BRANCH="peugeot-3008-sunny" \
  TESTING_BRANCH="peugeot-3008-sunny-testing" \
  SETUP_VARIANT="sunny" \
  MERGE_DIR="merge_opendbc_peugeot_3008_sunny" \
  COMMIT_MESSAGE="Merge peugeot-3008-sunny-testing into peugeot-3008-sunny" \
  /bin/bash "${script_dir}/merge_peugeot_3008_common.sh"
