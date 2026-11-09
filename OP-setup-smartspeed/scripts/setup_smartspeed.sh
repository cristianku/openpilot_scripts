#!/usr/bin/env bash
set -euo pipefail

# The sunnypilot we hand out today: sunnypilot master and the one commit of cristianku/sunnypilot:full-res-record (the
# Developer switch RecordRoadFullResolution, camerad's full road stream, encoderd and loggerd), nothing else: no Smartspeed,
# no Nav2Pilot, nothing of the Peugeot. Built by the testing setup's common script, so the code lives in one place: its
# speed-limits step applies the branch's changes over sunnypilot master, here that one commit.

# [help] - START
for arg in "$@"; do
  case "${arg}" in
    -h|--help|help)
      cat <<'HELP'
Uso: setup_smartspeed.sh [master|master=<commit>|release]

Costruisce cristianku/openpilot:smartspeed, un sunnypilot per l'auto di un altro che registra la strada
a risoluzione piena (2688x1520 con l'interruttore Developer "record road at full resolution", spento di default).
Dentro: sunnypilot/sunnypilot master (o quel commit, o l'ultima release)
  + il commit di cristianku/sunnypilot:full-res-record (RecordRoadFullResolution, camerad, encoderd, loggerd).
Fuori: Smartspeed e speedvisiond, Nav2Pilot, opendbc PSA, dati NNLC del Peugeot, patch torqued psa, catalogo Distill.
Installazione: installer.comma.ai/cristianku/smartspeed

Esempio: setup_smartspeed.sh master
Aiuto: setup_smartspeed.sh --help (oppure help, -h)
Il setup ricrea la cartella locale e pubblica il branch con --force-with-lease; questo aiuto non esegue operazioni.
HELP
      exit 0
      ;;
  esac
done
# [help] - END

usage="Usage: $0 [master|master=<upstream-commit>|release]"
if [[ $# -gt 1 ]]; then
  echo "${usage}" >&2
  exit 2
fi

source_arg="${1:-master}"
pinned_source_commit=""
case "${source_arg}" in
  master|release)
    source_mode="${source_arg}"
    ;;
  master=*)
    source_mode="master"
    pinned_source_commit="${source_arg#master=}"
    if [[ ! "${pinned_source_commit}" =~ ^[0-9a-fA-F]{7,40}$ ]]; then
      echo "ERROR: master=<upstream-commit> requires a 7-40 character hexadecimal Git commit" >&2
      echo "${usage}" >&2
      exit 2
    fi
    ;;
  *)
    echo "${usage}" >&2
    exit 2
    ;;
esac

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
common_script="${COMMON_SCRIPT:-${script_dir}/../../OP-setup-psa-torque-testing/scripts/setup_psa_torque_common.sh}"
if [[ ! -f "${common_script}" ]]; then
  echo "ERROR: missing ${common_script}" >&2
  exit 1
fi

openpilot_source_repo="${OPENPILOT_SOURCE_REPO:-https://github.com/sunnypilot/sunnypilot.git}"
if [[ "${source_mode}" == "release" ]]; then
  github_repo="${openpilot_source_repo#https://github.com/}"
  github_repo="${github_repo%.git}"
  openpilot_source_branch="$(curl --fail --silent --show-error --location \
    "https://api.github.com/repos/${github_repo}/releases/latest" \
    | python3 -c 'import json, sys; tag = json.load(sys.stdin).get("tag_name"); assert tag; print(tag)')"
  if ! git ls-remote --exit-code --tags "${openpilot_source_repo}" "refs/tags/${openpilot_source_branch}" >/dev/null; then
    echo "ERROR: latest GitHub release tag ${openpilot_source_branch} is unavailable in ${openpilot_source_repo}" >&2
    exit 1
  fi
else
  openpilot_source_branch="${OPENPILOT_SOURCE_BRANCH:-master}"
fi

BRANCH="smartspeed" \
  OPENPILOT_DIR="${OPENPILOT_DIR:-new_openpilot_smartspeed}" \
  OPENPILOT_SOURCE_REPO="${openpilot_source_repo}" \
  OPENPILOT_SOURCE_BRANCH="${openpilot_source_branch}" \
  OPENPILOT_SOURCE_COMMIT="${pinned_source_commit}" \
  NAV2PILOT_BRANCH="" \
  USE_CUSTOM_NEURAL_NETWORK_DATA="false" \
  SKIP_OPENDBC="true" \
  SKIP_PSA_TORQUED="true" \
  SKIP_EXTRA_MODEL_CATALOG="true" \
  SKIP_SPEED_LIMITS="false" \
  SPEED_LIMITS_SOURCE_BRANCH="full-res-record" \
  COMMIT_MESSAGE="${COMMIT_MESSAGE:-sunnypilot ${openpilot_source_branch} + the road recorded at full resolution (Developer switch, off by default)}" \
  bash "${common_script}"
