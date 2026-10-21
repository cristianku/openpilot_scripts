#!/usr/bin/env bash
set -euo pipefail

# [help] - START
for arg in "$@"; do
  case "${arg}" in
    -h|--help|help)
      cat <<'HELP'
Uso: setup_psa_torque.sh [comma|sunny] [nav-alpha|master|master=<commit>|release]

Primo parametro: comma oppure sunny (predefinito: comma).
Secondo parametro: nav-alpha (predefinito, con Nav2Pilot) oppure master.
  sunny nav-alpha  -> cristianku/openpilot:sunny-nav-alpha (sunnypilot master + Nav2Pilot)
  sunny master     -> sunnypilot/sunnypilot:master
  comma nav-alpha  -> cristianku/openpilot:nav-alpha (comma master + Nav2Pilot)
  comma master     -> commaai/openpilot:master
Con nav-alpha il branch Nav2Pilot viene prima riallineato all'ultimo master upstream
(scripts/update_fork_branch.sh; SKIP_NAV_UPDATE=true per usarlo com'e').
Anche feature/nav-alpha e' accettato come secondo parametro per sunny (vecchio nome, usa nav-alpha).
Destinazione Sunny: cristianku/openpilot:psa-torque-sunny-testing
Destinazione comma: cristianku/openpilot:psa-torque-testing
Alias: openpilot = comma; sunnypilot = sunny.
Altre sorgenti: master=<commit> o release dall'upstream ufficiale.

Esempio: setup_psa_torque.sh sunny nav-alpha
Aiuto: setup_psa_torque.sh --help (oppure help, -h)
Il setup ricrea la cartella locale e pubblica il branch; questo aiuto non esegue operazioni.
HELP
      exit 0
      ;;
  esac
done
# [help] - END

variant="${1:-comma}"
# [pinned source] - START
source_arg="${2:-nav-alpha}"
source_mode="${source_arg}"
pinned_source_commit=""
# [nav source] - START
usage="Usage: $0 [comma|openpilot|sunny|sunnypilot] [master|master=<upstream-commit>|release|nav-alpha]"
# [nav source] - END

if [[ "${source_arg}" == master=* ]]; then
  source_mode="master"
  pinned_source_commit="${source_arg#master=}"
  if [[ ! "${pinned_source_commit}" =~ ^[0-9a-fA-F]{7,40}$ ]]; then
    echo "ERROR: master=<upstream-commit> requires a 7-40 character hexadecimal Git commit" >&2
    echo "${usage}" >&2
    exit 2
  fi
fi
# [pinned source] - END

case "${variant}" in
  comma|openpilot)
    variant="comma"
    branch="psa-torque-testing"
    source_branch="psa-torque"
    ;;
  sunny|sunnypilot)
    variant="sunny"
    # OP-setup-psa-torque-speed publishes the same setup on psa-torque-sunny-speed
    branch="${SUNNY_TARGET_BRANCH:-psa-torque-sunny-testing}"
    source_branch="psa-torque-sunny"
    ;;
  *)
    echo "${usage}" >&2
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
    echo "${usage}" >&2
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

# [pinned source] - START
BRANCH="${branch}" \
  OPENPILOT_SOURCE_REPO="${openpilot_source_repo}" \
  OPENPILOT_SOURCE_BRANCH="${openpilot_source_branch}" \
  OPENPILOT_SOURCE_COMMIT="${pinned_source_commit}" \
  OPENDBC_SOURCE_BRANCH="${OPENDBC_SOURCE_BRANCH:-${source_branch}}" \
  USE_CUSTOM_NEURAL_NETWORK_DATA="${use_custom_neural_network_data}" \
  bash "${common_script}"
# [pinned source] - END
