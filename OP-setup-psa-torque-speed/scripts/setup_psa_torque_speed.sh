#!/usr/bin/env bash
set -euo pipefail

# Publish the Peugeot 3008 speed branch: the same setup as OP-setup-psa-torque-testing, but the
# openpilot branch is psa-torque-sunny-speed and opendbc_repo points to opendbc psa-torque-sunny-speed.

usage="Usage: $0 sunny [master|master=<upstream-commit>|release]"

for arg in "$@"; do
  case "${arg}" in
    -h|--help|help)
      cat <<'HELP'
Uso: setup_psa_torque_speed.sh sunny [master|master=<commit>|release]

Primo parametro obbligatorio: sunny (alias sunnypilot).
comma non e' implementato: openpilot di comma non ha lo Speed Limit Assist.
Secondo parametro: come OP-setup-psa-torque-testing (predefinito: master).
  sunny master     -> sunnypilot/sunnypilot:master, con Nav2Pilot sempre iniettato dalla sua patch
  nav-alpha e' il vecchio nome di master; SKIP_NAV=true per costruire senza Nav2Pilot.
Destinazione: cristianku/openpilot:psa-torque-sunny-speed
opendbc_repo punta a cristianku/opendbc:psa-torque-sunny-speed.

Esempio: setup_psa_torque_speed.sh sunny
Aiuto: setup_psa_torque_speed.sh --help (oppure help, -h)
Il setup ricrea la cartella locale e pubblica il branch; questo aiuto non esegue operazioni.
HELP
      exit 0
      ;;
  esac
done

if [[ $# -lt 1 || $# -gt 2 ]]; then
  echo "ERROR: the first parameter sunny is required" >&2
  echo "${usage}" >&2
  exit 2
fi

variant="$1"
source_arg="${2:-master}"

case "${variant}" in
  sunny|sunnypilot)
    ;;
  comma|openpilot)
    echo "ERROR: comma non implementato: openpilot di comma non ha lo Speed Limit Assist, usa sunny" >&2
    exit 2
    ;;
  *)
    echo "${usage}" >&2
    exit 2
    ;;
esac

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
testing_wrapper="${script_dir}/../../OP-setup-psa-torque-testing/scripts/setup_psa_torque.sh"

if [[ ! -f "${testing_wrapper}" ]]; then
  echo "ERROR: missing ${testing_wrapper}" >&2
  exit 1
fi

# The testing setup does all the work (Nav2Pilot, torqued, Models and speed-limit changes, pointers,
# protected push); only the target branch changes. If opendbc psa-torque-sunny-speed does not
# exist yet it is created from psa-torque-sunny-testing.
SUNNY_TARGET_BRANCH="psa-torque-sunny-speed" \
  OPENDBC_SOURCE_BRANCH="${OPENDBC_SOURCE_BRANCH:-psa-torque-sunny-testing}" \
  bash "${testing_wrapper}" sunny "${source_arg}"
