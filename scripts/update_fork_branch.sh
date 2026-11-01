#!/usr/bin/env bash
# Riallinea un branch di cristianku/openpilot al master upstream e lo pubblica. Chiunque lo installa con
# installer.comma.ai/cristianku/<branch>.
#
# Uso: update_fork_branch.sh <nav-alpha|sunny-nav-alpha|distilled>
#   nav-alpha        commaai/openpilot master + il commit Nav2Pilot
#   sunny-nav-alpha  sunnypilot/sunnypilot master + il commit Nav2Pilot,
#                    lo stesso commit va anche su cristianku/sunnypilot nav-alpha (MIRROR_REPO)
#   distilled        sync cristianku/sunnypilot:distilled with upstream master, then mirror to cristianku/openpilot:distilled
#
# nav-alpha e sunny-nav-alpha sono l'unica fonte del codice Nav2Pilot: un commit sopra il master upstream.
# Lo script sposta quel commit sul master attuale (come un cherry-pick: stesso messaggio, stesso autore).
# Se il branch e' gia' sul master attuale non fa niente. Se il commit non si applica piu' (conflitti) si ferma
# con exit 2 e non pubblica niente: i conflitti si risolvono con OP-apply-nav-alpha, che poi ripubblica.
# Non tocca nessuna cartella di lavoro: usa un clone bare di cache e un index temporaneo.
#
# Env: NO_PUSH=true (costruisce il commit ma non lo pubblica)
#      FORK_CACHE (clone bare di cache, default <CRISTIANKU>/fork-branch-cache.git)
#      TARGET_REPO (default https://github.com/cristianku/openpilot.git)
set -euo pipefail

OPENPILOT_SCRIPTS="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
CRISTIANKU_DIR="$(dirname "${OPENPILOT_SCRIPTS}")"
FORK_CACHE="${FORK_CACHE:-${CRISTIANKU_DIR}/fork-branch-cache.git}"
TARGET_REPO="${TARGET_REPO:-https://github.com/cristianku/openpilot.git}"
NO_PUSH="${NO_PUSH:-false}"
# upstream files our Nav2Pilot code copies or subclasses: a change there can apply cleanly and still be lost
NAV_WATCHED_FILES="openpilot/selfdrive/navigation/navd.py openpilot/selfdrive/navigation/tiles.py openpilot/system/athena/rpc.py"

usage() {
  sed -n '2,/^set -euo/p' "$0" | sed '$d' | sed 's/^# \{0,1\}//' >&2
  exit 1
}

die() {
  echo "ERRORE: $*" >&2
  exit 1
}

g() {
  git -C "${FORK_CACHE}" "$@"
}

if [[ $# -ne 1 ]]; then
  usage
fi
TARGET="$1"

# [distill sync] - START
# Distill is source-first: do not rebuild its code from a duplicated patch.
if [[ "${TARGET}" == "distilled" ]]; then
  exec bash "${OPENPILOT_SCRIPTS}/scripts/update_distilled.sh"
fi
# [distill sync] - END

# second branch that gets the very same commit (empty = none)
MIRROR_REPO=""
MIRROR_BRANCH=""
if [[ "${TARGET}" == "nav-alpha" ]]; then
  SOURCE_NAME="commaai"
  SOURCE_REPO="https://github.com/commaai/openpilot.git"
elif [[ "${TARGET}" == "sunny-nav-alpha" ]]; then
  SOURCE_NAME="sunnypilot"
  SOURCE_REPO="https://github.com/sunnypilot/sunnypilot.git"
  # cristianku/sunnypilot nav-alpha must never drift from sunny-nav-alpha
  MIRROR_REPO="https://github.com/cristianku/sunnypilot.git"
  MIRROR_BRANCH="nav-alpha"
else
  usage
fi

# the files the Nav2Pilot commit modifies or creates, one per line
patch_files() {
  g diff --name-only --diff-filter=d "${nav_base}" "${current}"
}

# Upstream master into the cache. The first time it downloads the whole history (some minutes),
# later only what is new.
fetch_master() {
  if [[ ! -d "${FORK_CACHE}" ]]; then
    echo "== creo la cache ${FORK_CACHE} (la prima volta scarica tutta la storia, qualche minuto)"
    git init -q --bare "${FORK_CACHE}"
  fi
  echo "== fetch ${SOURCE_NAME} master"
  g fetch -q --no-tags "${SOURCE_REPO}" "+refs/heads/master:refs/sources/${SOURCE_NAME}/master"
  master="$(g rev-parse "refs/sources/${SOURCE_NAME}/master")"
}

# The branch as it is now on GitHub: one Nav2Pilot commit on an upstream master commit. Sets current and
# nav_base (the master commit it sits on).
fetch_current() {
  current="$(git ls-remote "${TARGET_REPO}" "refs/heads/${TARGET}" | awk 'NR == 1 { print $1 }')"
  [[ -n "${current}" ]] || die "${TARGET} non esiste su ${TARGET_REPO}: e' la fonte del codice Nav2Pilot, crealo con OP-apply-nav-alpha"
  g fetch -q --no-tags "${TARGET_REPO}" "+refs/heads/${TARGET}:refs/targets/${TARGET}"
  local parents
  parents="$(g rev-list --parents -n 1 "${current}" | wc -w)"
  if [[ "${parents}" -ne 2 ]]; then
    die "${TARGET} ${current:0:10} e' un merge (forse un \"Sync fork\" di GitHub): rifallo un solo commit sul master con OP-apply-nav-alpha"
  fi
  nav_base="$(g rev-parse "${current}^")"
  if ! g merge-base --is-ancestor "${nav_base}" "${master}"; then
    die "${TARGET} non e' un solo commit sul ${SOURCE_NAME} master (sotto c'e' ${nav_base:0:10}): rifallo con OP-apply-nav-alpha"
  fi
}

# The Nav2Pilot commit moved onto master on a temporary index (a cherry-pick): sets tree.
build_tree() {
  local index_file="${work_dir}/index"
  GIT_INDEX_FILE="${index_file}" g read-tree "${master}"
  echo "== sposto il commit Nav2Pilot ${current:0:10} (era su ${nav_base:0:10}) su ${SOURCE_NAME} master ${master:0:10}"
  if ! g diff --binary --full-index "${nav_base}" "${current}" \
      | GIT_INDEX_FILE="${index_file}" g apply --cached --3way --whitespace=nowarn; then
    echo >&2
    echo "CONFLITTI: il commit Nav2Pilot non si applica piu' su ${SOURCE_NAME} master. Non ho pubblicato niente." >&2
    echo "Risolvili con OP-apply-nav-alpha (apply, risoluzione, push): ripubblica anche ${TARGET}." >&2
    exit 2
  fi
  tree="$(GIT_INDEX_FILE="${index_file}" g write-tree)"
}

check_tree() {
  local failed=0
  local file
  echo "== controlli"
  for file in $(patch_files); do
    if ! g cat-file -e "${tree}:${file}" 2>/dev/null; then
      echo "   MANCA ${file}"
      failed=1
      continue
    fi
    if [[ "${file}" == *.py ]]; then
      if ! g show "${tree}:${file}" | python3 -c 'import ast, sys; ast.parse(sys.stdin.read())' 2>/dev/null; then
        echo "   SINTASSI python errata in ${file}"
        failed=1
      fi
    fi
  done

  local params
  params="$(g show "${tree}:openpilot/common/params_keys.h")"
  local duplicates
  duplicates="$(echo "${params}" | grep -o -E '^ *\{"[A-Za-z0-9_]+"' | tr -d ' {"' | sort | uniq -d | tr '\n' ' ')"
  if [[ -n "${duplicates}" ]]; then
    echo "   CHIAVI DOPPIE in params_keys.h: ${duplicates}"
    failed=1
  fi
  if ! echo "${params}" | grep -q '{"MapboxToken"'; then
    echo "   MANCA la chiave MapboxToken in params_keys.h"
    failed=1
  fi

  if [[ "${failed}" -ne 0 ]]; then
    die "controlli falliti: non ho pubblicato niente"
  fi
  echo "   OK"
}

# Upstream commits since the Nav2Pilot commit's base that touch files our Nav2Pilot code copies or subclasses.
warn_nav_watched() {
  local changes
  # shellcheck disable=SC2086
  changes="$(g log --oneline "${nav_base}..${master}" -- ${NAV_WATCHED_FILES})"
  if [[ -n "${changes}" ]]; then
    echo "ATTENZIONE: upstream ha cambiato file che il codice Nav2Pilot copia o estende (rivedili con OP-apply-nav-alpha):"
    echo "${changes}" | sed 's/^/   /'
  fi
}

# The published commit also on MIRROR_REPO MIRROR_BRANCH (only sunny-nav-alpha has one).
push_mirror() {
  local published="$1"
  if [[ -z "${MIRROR_REPO}" ]]; then
    return
  fi
  local mirror_current
  mirror_current="$(git ls-remote "${MIRROR_REPO}" "refs/heads/${MIRROR_BRANCH}" | awk 'NR == 1 { print $1 }')"
  if [[ "${mirror_current}" == "${published}" ]]; then
    echo "== ${MIRROR_REPO} ${MIRROR_BRANCH} e' gia' lo stesso commit ${published:0:10}"
    return
  fi
  if [[ "${NO_PUSH}" == "true" ]]; then
    echo "NO_PUSH: ${MIRROR_REPO} ${MIRROR_BRANCH} non pubblicato"
    return
  fi
  echo "== push di ${MIRROR_BRANCH} su ${MIRROR_REPO} (prima: ${mirror_current:-nessuno})"
  GIT_LFS_SKIP_PUSH=1 g -c push.negotiate=true push -q \
    --force-with-lease="refs/heads/${MIRROR_BRANCH}:${mirror_current}" "${MIRROR_REPO}" "${published}:refs/heads/${MIRROR_BRANCH}"
  echo "== pubblicato: ${MIRROR_REPO} ${MIRROR_BRANCH} = ${published}"
}

work_dir="$(mktemp -d)"
trap 'rm -rf "${work_dir}"' EXIT

fetch_master
fetch_current

# Up to date: the Nav2Pilot commit already sits on the current master.
if [[ "${nav_base}" == "${master}" ]]; then
  tree="$(g rev-parse "${current}^{tree}")"
  check_tree
  echo "== ${TARGET} e' gia' aggiornato: ${current:0:10} = ${SOURCE_NAME} master ${master:0:10} + Nav2Pilot"
  push_mirror "${current}"
  exit 0
fi

build_tree
check_tree
warn_nav_watched

# Same message and author as the Nav2Pilot commit, as a cherry-pick keeps them.
message_file="${work_dir}/message"
g log -1 --format=%B "${current}" > "${message_file}"
commit="$(GIT_AUTHOR_NAME="$(g log -1 --format=%an "${current}")" \
  GIT_AUTHOR_EMAIL="$(g log -1 --format=%ae "${current}")" \
  GIT_AUTHOR_DATE="$(g log -1 --format=%aD "${current}")" \
  g commit-tree "${tree}" -p "${master}" -F "${message_file}")"
echo "== commit ${commit:0:10} (prima su GitHub: ${current:-nessuno})"

if [[ "${NO_PUSH}" == "true" ]]; then
  echo "NO_PUSH: non pubblicato"
  push_mirror "${commit}"
  exit 0
fi

echo "== push di ${TARGET} su ${TARGET_REPO}"
# LFS lives on comma's/sunnypilot's own storage (.lfsconfig): nothing to upload, as in the setup skills.
# push.negotiate asks GitHub which history it already has, so only the new commit is sent.
GIT_LFS_SKIP_PUSH=1 g -c push.negotiate=true push -q \
  --force-with-lease="refs/heads/${TARGET}:${current}" "${TARGET_REPO}" "${commit}:refs/heads/${TARGET}"
echo "== pubblicato: ${TARGET} = ${commit}"
echo "   installazione sul comma: installer.comma.ai/cristianku/${TARGET}"
push_mirror "${commit}"
