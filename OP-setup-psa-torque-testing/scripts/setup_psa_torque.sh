#!/usr/bin/env bash
set -euo pipefail

# [help] - START
for arg in "$@"; do
  case "${arg}" in
    -h|--help|help)
      cat <<'HELP'
Uso: setup_psa_torque.sh [comma|sunny] [master|master=<commit>|release]

Primo parametro: comma oppure sunny (predefinito: comma).
Secondo parametro: la base upstream (predefinito: master).
  sunny master          -> sunnypilot/sunnypilot:master
  comma master          -> commaai/openpilot:master
  master=<commit>       -> quel commit del master upstream
  release               -> l'ultima GitHub Release upstream
Nav2Pilot viene sempre iniettato sulla base, dalla patch canonica
OP-apply-nav-alpha/patches/sunnypilot.patch (sunny) o openpilot.patch (comma), la stessa di
cristianku/openpilot:sunny-nav-alpha / nav-alpha; SKIP_NAV=true per costruire senza.
nav-alpha e feature/nav-alpha (vecchi nomi, solo sunny per il secondo) valgono come master.
Prima di lanciarlo: docs/external-branches.md (sincronizzare master e branch esterni).
Destinazione Sunny: cristianku/openpilot:psa-torque-sunny-testing
Destinazione comma: cristianku/openpilot:psa-torque-testing
Alias: openpilot = comma; sunnypilot = sunny.

Esempio: setup_psa_torque.sh sunny
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
source_arg="${2:-master}"
source_mode="${source_arg}"
pinned_source_commit=""
# [nav source] - START
usage="Usage: $0 [comma|openpilot|sunny|sunnypilot] [master|master=<upstream-commit>|release]"
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
  # Old names of the default: Nav2Pilot is now injected on every base, so they mean master.
  nav-alpha)
    source_mode="master"
    ;;
  feature/nav-alpha)
    if [[ "${variant}" != "sunny" ]]; then
      echo "ERROR: feature/nav-alpha requires the sunny variant; use comma master" >&2
      exit 2
    fi
    source_mode="master"
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
# Nav2Pilot is injected on whichever base was chosen, from its canonical patch (the one that builds
# cristianku/openpilot:sunny-nav-alpha / nav-alpha); SKIP_NAV=true builds without it.
nav_patch=""
nav_base=""
if [[ "${SKIP_NAV:-false}" != "true" ]]; then
  nav_fork="openpilot"
  [[ "${variant}" == "sunny" ]] && nav_fork="sunnypilot"
  nav_patches="${NAV2PILOT_PATCHES:-${script_dir}/../../OP-apply-nav-alpha/patches}"
  nav_patch="${nav_patches}/${nav_fork}.patch"
  nav_base="${nav_patches}/${nav_fork}.base"
  if [[ ! -s "${nav_patch}" ]]; then
    echo "ERROR: missing the Nav2Pilot patch ${nav_patch} (SKIP_NAV=true to build without Nav2Pilot)" >&2
    exit 1
  fi
fi
# [nav source] - END

openpilot_source_repo="${OPENPILOT_SOURCE_REPO:-${openpilot_source_repo}}"
if [[ "${source_mode}" == "release" ]]; then
  openpilot_source_branch="$(resolve_latest_release_tag "${openpilot_source_repo}")"
else
  openpilot_source_branch="${OPENPILOT_SOURCE_BRANCH:-${openpilot_source_branch}}"
fi
# [source] - END

# [pinned source] - START
BRANCH="${branch}" \
  OPENPILOT_SOURCE_REPO="${openpilot_source_repo}" \
  OPENPILOT_SOURCE_BRANCH="${openpilot_source_branch}" \
  OPENPILOT_SOURCE_COMMIT="${pinned_source_commit}" \
  OPENDBC_SOURCE_BRANCH="${OPENDBC_SOURCE_BRANCH:-${source_branch}}" \
  USE_CUSTOM_NEURAL_NETWORK_DATA="${use_custom_neural_network_data}" \
  NAV2PILOT_PATCH="${nav_patch}" \
  NAV2PILOT_BASE="${nav_base}" \
  bash "${common_script}"
# [pinned source] - END
