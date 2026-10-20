#!/usr/bin/env bash
set -euo pipefail

variant="${1:-comma}"
source_mode="${2:-nav-alpha}"

case "${variant}" in
  comma|openpilot)
    variant="comma"
    branch="psa-torque"
    source_branch="psa-torque-testing"
    ;;
  sunny|sunnypilot)
    variant="sunny"
    branch="psa-torque-sunny"
    source_branch="psa-torque-sunny-testing"
    ;;
  *)
    # [nav source] - START
    echo "Usage: $0 [comma|openpilot|sunny|sunnypilot] [master|release|nav-alpha]" >&2
    # [nav source] - END
    exit 2
    ;;
esac

case "${source_mode}" in
  master|release)
    ;;
  # [nav source] - START
  nav-alpha)
    ;;
  feature/nav-alpha)
    if [[ "${variant}" != "sunny" ]]; then
      echo "ERROR: feature/nav-alpha requires the sunny variant; use comma nav-alpha" >&2
      exit 2
    fi
    ;;
  # [nav source] - END
  *)
    # [nav source] - START
    echo "Usage: $0 [comma|openpilot|sunny|sunnypilot] [master|release|nav-alpha]" >&2
    # [nav source] - END
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

# [nav source] - START
# Both Nav2Pilot branches live on cristianku/openpilot, so anyone can install them with
# installer.comma.ai/cristianku/<branch>.
nav_branch=""
if [[ "${source_mode}" == "nav-alpha" || "${source_mode}" == "feature/nav-alpha" ]]; then
  if [[ "${variant}" == "sunny" ]]; then
    nav_branch="sunny-nav-alpha"
  else
    nav_branch="nav-alpha"
  fi
  openpilot_source_repo="https://github.com/cristianku/openpilot.git"
  openpilot_source_branch="${nav_branch}"
fi
# [nav source] - END

openpilot_source_repo="${OPENPILOT_SOURCE_REPO:-${openpilot_source_repo}}"
if [[ "${source_mode}" == "release" ]]; then
  openpilot_source_branch="$(resolve_latest_release_tag "${openpilot_source_repo}")"
else
  openpilot_source_branch="${OPENPILOT_SOURCE_BRANCH:-${openpilot_source_branch}}"
fi
# [source] - END

# The Nav2Pilot branch is first realigned to the latest upstream master; nothing is pushed when it
# already is. Skipped when the source is overridden from the environment.
if [[ -n "${nav_branch}" && -z "${OPENPILOT_SOURCE_REPO:-}" && -z "${OPENPILOT_SOURCE_BRANCH:-}" \
      && "${SKIP_NAV_UPDATE:-false}" != "true" ]]; then
  update_script="$(cd "${script_dir}" && pwd -P)/../../scripts/update_fork_branch.sh"
  if ! bash "${update_script}" "${nav_branch}"; then
    echo "ERROR: ${nav_branch} could not be realigned to upstream master (see above)." >&2
    echo "Fix it with OP-apply-nav-alpha, or rerun with master (no Nav2Pilot)" >&2
    echo "or with SKIP_NAV_UPDATE=true (uses ${nav_branch} as it is now)." >&2
    exit 1
  fi
fi

BRANCH="${branch}" \
  OPENPILOT_SOURCE_REPO="${openpilot_source_repo}" \
  OPENPILOT_SOURCE_BRANCH="${openpilot_source_branch}" \
  OPENDBC_SOURCE_BRANCH="${OPENDBC_SOURCE_BRANCH:-${source_branch}}" \
  USE_CUSTOM_NEURAL_NETWORK_DATA="${use_custom_neural_network_data}" \
  bash "${common_script}"
