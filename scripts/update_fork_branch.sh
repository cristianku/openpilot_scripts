#!/usr/bin/env bash
# Ricostruisce un branch di cristianku/openpilot dal master upstream piu' una patch, in un solo commit,
# e lo pubblica. Chiunque lo installa con installer.comma.ai/cristianku/<branch>.
#
# Uso: update_fork_branch.sh <nav-alpha|sunny-nav-alpha|distilled>
#   nav-alpha        commaai/openpilot master + Nav2Pilot (OP-apply-nav-alpha/patches/openpilot.patch)
#   sunny-nav-alpha  sunnypilot/sunnypilot master + Nav2Pilot (OP-apply-nav-alpha/patches/sunnypilot.patch),
#                    lo stesso commit va anche su cristianku/sunnypilot nav-alpha (MIRROR_REPO)
#   distilled        sync cristianku/sunnypilot:distilled with upstream master, then mirror to cristianku/openpilot:distilled
#
# Se il branch su GitHub e' gia' il master attuale piu' la stessa patch non fa niente.
# Se la patch non si applica piu' (conflitti) si ferma con exit 2 e non pubblica niente: per nav-alpha e
# sunny-nav-alpha i conflitti si risolvono con OP-apply-nav-alpha, che poi ripubblica con questo script.
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

NAV_BASE_FILE=""
# second branch that gets the very same commit (empty = none)
MIRROR_REPO=""
MIRROR_BRANCH=""
if [[ "${TARGET}" == "nav-alpha" ]]; then
  SOURCE_NAME="commaai"
  SOURCE_REPO="https://github.com/commaai/openpilot.git"
  PATCH_FILE="${OPENPILOT_SCRIPTS}/OP-apply-nav-alpha/patches/openpilot.patch"
  NAV_BASE_FILE="${OPENPILOT_SCRIPTS}/OP-apply-nav-alpha/patches/openpilot.base"
  TITLE="nav alpha: Nav2Pilot setNavRoute waypoints and setMapboxToken"
elif [[ "${TARGET}" == "sunny-nav-alpha" ]]; then
  SOURCE_NAME="sunnypilot"
  SOURCE_REPO="https://github.com/sunnypilot/sunnypilot.git"
  PATCH_FILE="${OPENPILOT_SCRIPTS}/OP-apply-nav-alpha/patches/sunnypilot.patch"
  NAV_BASE_FILE="${OPENPILOT_SCRIPTS}/OP-apply-nav-alpha/patches/sunnypilot.base"
  TITLE="nav alpha: Nav2Pilot setNavRoute waypoints and setMapboxToken"
  # cristianku/sunnypilot nav-alpha must never drift from sunny-nav-alpha
  MIRROR_REPO="https://github.com/cristianku/sunnypilot.git"
  MIRROR_BRANCH="nav-alpha"
else
  usage
fi

[[ -f "${PATCH_FILE}" ]] || die "manca la patch ${PATCH_FILE}"

# the files the patch modifies or creates, one per line
patch_files() {
  grep '^diff --git ' "${PATCH_FILE}" | sed 's#^diff --git a/\(.*\) b/.*#\1#'
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

# The branch as it is now on GitHub (empty when it does not exist yet).
fetch_current() {
  current="$(git ls-remote "${TARGET_REPO}" "refs/heads/${TARGET}" | awk 'NR == 1 { print $1 }')"
  if [[ -n "${current}" ]]; then
    g fetch -q --no-tags "${TARGET_REPO}" "+refs/heads/${TARGET}:refs/targets/${TARGET}"
  fi
}

# master + patch on a temporary index: sets tree.
build_tree() {
  local index_file="${work_dir}/index"
  GIT_INDEX_FILE="${index_file}" g read-tree "${master}"
  echo "== applico $(basename "${PATCH_FILE}") su ${SOURCE_NAME} master ${master:0:10}"
  if ! GIT_INDEX_FILE="${index_file}" g apply --cached --3way --whitespace=nowarn "${PATCH_FILE}"; then
    echo >&2
    if [[ -n "${NAV_BASE_FILE}" ]]; then
      echo "CONFLITTI: la patch non si applica piu' su ${SOURCE_NAME} master. Non ho pubblicato niente." >&2
      echo "Risolvili con OP-apply-nav-alpha (apply, risoluzione, push): ripubblica anche ${TARGET}." >&2
    else
      echo "CONFLITTI: la patch non si applica piu' su ${SOURCE_NAME} master. Non ho pubblicato niente." >&2
      echo "Aggiorna ${PATCH_FILE} (sunnypilot ha cambiato openpilot/sunnypilot/models)." >&2
    fi
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

  if [[ -n "${NAV_BASE_FILE}" ]]; then
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
  fi

  if [[ "${failed}" -ne 0 ]]; then
    die "controlli falliti: non ho pubblicato niente"
  fi
  echo "   OK"
}

# Upstream commits since the patch was saved that touch files our Nav2Pilot code copies or subclasses.
warn_nav_watched() {
  if [[ -z "${NAV_BASE_FILE}" ]]; then
    return
  fi
  local base
  base="$(cat "${NAV_BASE_FILE}")"
  if ! g cat-file -e "${base}^{commit}" 2>/dev/null; then
    return
  fi
  local changes
  # shellcheck disable=SC2086
  changes="$(g log --oneline "${base}..${master}" -- ${NAV_WATCHED_FILES})"
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
build_tree
check_tree
warn_nav_watched

# Up to date: same content as master + patch, with master in its history (also after a GitHub
# "Sync fork", which merges master into the branch instead of rebuilding it).
if [[ -n "${current}" ]]; then
  current_tree="$(g rev-parse "${current}^{tree}")"
  if [[ "${current_tree}" == "${tree}" ]] && g merge-base --is-ancestor "${master}" "${current}"; then
    echo "== ${TARGET} e' gia' aggiornato: ${current:0:10} = ${SOURCE_NAME} master ${master:0:10} + patch"
    push_mirror "${current}"
    exit 0
  fi
fi

message_file="${work_dir}/message"
cat > "${message_file}" <<EOF
${TITLE}

Rebuilt by openpilot_scripts/scripts/update_fork_branch.sh on ${SOURCE_NAME} master
${master:0:10} plus $(basename "${PATCH_FILE}").
EOF
commit="$(g commit-tree "${tree}" -p "${master}" -F "${message_file}")"
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
