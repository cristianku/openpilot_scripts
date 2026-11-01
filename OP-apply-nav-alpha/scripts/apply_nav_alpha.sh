#!/usr/bin/env bash
# Riapplica le modifiche Nav2Pilot (setNavRoute con waypoint + setMapboxToken) su un master fresco.
# L'unica fonte del codice e' il commit Nav2Pilot sulle branch nav-alpha / sunny-nav-alpha di cristianku/openpilot
# (master upstream + quel solo commit): qui lo si riapplica, lo si modifica (commit = amend) e lo si ripubblica.
# Documentazione: openpilot_scripts/docs/nav-alpha-nav2pilot.md
set -euo pipefail

SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
# moves the published Nav2Pilot commit onto the latest master (also used by OP-update-*)
UPDATE_SCRIPT="${SKILL_DIR}/../scripts/update_fork_branch.sh"
FORK_URL="https://github.com/cristianku/openpilot.git"
CRISTIANKU_DIR="/Users/cristianku/GitHub/COMMA.AI/CRISTIANKU"

usage() {
  cat >&2 <<'EOF'
Uso: apply_nav_alpha.sh <sunny|comma> <comando>

Comandi:
  status      fetch del master, dice se il branch e' indietro e se il commit Nav2Pilot si applica pulito
  apply       backup del branch, ricrea il branch dal master, applica il commit Nav2Pilot pubblicato,
              controlli, commit locale
  check       controlli statici sul working tree
  commit      controlli + commit delle modifiche in index; se il branch ha gia' il commit Nav2Pilot lo
              corregge (amend): resta sempre un solo commit sul master
  sync-check  confronta il pacchetto Nav2Pilot di sunny con quello di comma (devono restare uguali)
  push        pubblica il branch (master + il commit Nav2Pilot) su cristianku/openpilot
              (nav-alpha per comma, sunny-nav-alpha per sunny), poi scripts/update_fork_branch.sh
              lo porta sull'ultimo master se serve (e sul mirror per sunny)

Variabili: NAV_REPO (cartella del clone), NAV_BRANCH (branch locale, default nav-alpha)
EOF
  exit 1
}

if [[ $# -ne 2 ]]; then
  usage
fi

VARIANT="$1"
COMMAND="$2"

if [[ "${VARIANT}" == "sunny" || "${VARIANT}" == "sunnypilot" ]]; then
  VARIANT="sunny"
  DEFAULT_REPO="${CRISTIANKU_DIR}/sunnypilot-nav-alpha"
  UPSTREAM_REMOTE="upstream"
  UPSTREAM_URL_PATTERN="sunnypilot/sunnypilot"
  FORK_BRANCH="sunny-nav-alpha"
  NAV_PACKAGE="openpilot/sunnypilot/navd"
elif [[ "${VARIANT}" == "comma" || "${VARIANT}" == "openpilot" ]]; then
  VARIANT="comma"
  DEFAULT_REPO="${CRISTIANKU_DIR}/openpilot-nav-alpha"
  UPSTREAM_REMOTE="commaai"
  UPSTREAM_URL_PATTERN="commaai/openpilot"
  FORK_BRANCH="nav-alpha"
  NAV_PACKAGE="openpilot/selfdrive/navigation/nav2pilot"
else
  usage
fi

REPO="${NAV_REPO:-${DEFAULT_REPO}}"
BRANCH="${NAV_BRANCH:-nav-alpha}"
UPSTREAM_REF="${UPSTREAM_REMOTE}/master"
# the published Nav2Pilot commit, fetched by fetch_upstream
FORK_REF="refs/remotes/fork/${FORK_BRANCH}"
# upstream file that our code subclasses or copies: every upstream change to it must be reviewed
WATCHED_FILES="openpilot/selfdrive/navigation/navd.py openpilot/selfdrive/navigation/tiles.py openpilot/system/athena/rpc.py"

g() {
  git -C "${REPO}" "$@"
}

die() {
  echo "ERRORE: $*" >&2
  exit 1
}

check_repo() {
  if [[ ! -d "${REPO}/.git" && ! -f "${REPO}/.git" ]]; then
    die "${REPO} non e' un clone git"
  fi
  local upstream_url
  upstream_url="$(g remote get-url "${UPSTREAM_REMOTE}" 2>/dev/null || true)"
  if [[ "${upstream_url}" != *"${UPSTREAM_URL_PATTERN}"* ]]; then
    die "il remote ${UPSTREAM_REMOTE} di ${REPO} non punta a ${UPSTREAM_URL_PATTERN} (trovato: '${upstream_url}')"
  fi
}

check_clean() {
  local dirty
  dirty="$(g status --porcelain --ignore-submodules=all)"
  if [[ -n "${dirty}" ]]; then
    echo "${dirty}" >&2
    die "working tree di ${REPO} non pulito: committa o metti da parte prima"
  fi
}

fetch_upstream() {
  echo "== fetch ${UPSTREAM_REF} e cristianku/openpilot ${FORK_BRANCH}"
  g fetch "${UPSTREAM_REMOTE}" master
  g fetch "${FORK_URL}" "+refs/heads/${FORK_BRANCH}:${FORK_REF}"
  if [[ "$(g rev-list --parents -n 1 "${FORK_REF}" | wc -w)" -ne 2 ]]; then
    die "cristianku/openpilot ${FORK_BRANCH} e' un merge, non un solo commit Nav2Pilot sul master: ricostruiscilo a mano"
  fi
}

# the published Nav2Pilot commit as a diff over its own base
fork_diff() {
  g diff --binary --full-index "${FORK_REF}^" "${FORK_REF}"
}

# the upstream commit the local branch sits on
branch_base() {
  g merge-base "${UPSTREAM_REF}" HEAD
}

# the files Nav2Pilot modifies or creates in the working tree, one per line
nav_files() {
  g diff --name-only --diff-filter=d --ignore-submodules=all "$(branch_base)"
}

# files that exist upstream and the published Nav2Pilot commit modifies (the "upstream touches")
patch_upstream_files() {
  local file
  for file in $(g diff --name-only --diff-filter=d "${FORK_REF}^" "${FORK_REF}"); do
    if g cat-file -e "${UPSTREAM_REF}:${file}" 2>/dev/null; then
      echo "${file}"
    fi
  done
}

show_upstream_changes() {
  local base
  base="$(g rev-parse "${FORK_REF}^")"
  local new_master
  new_master="$(g rev-parse "${UPSTREAM_REF}")"
  echo "== ${FORK_BRANCH} pubblicato su ${UPSTREAM_REF} ${base:0:10}, master ora ${new_master:0:10}"
  if [[ "${base}" == "${new_master}" ]]; then
    echo "   master non e' cambiato"
    return
  fi
  if ! g cat-file -e "${base}^{commit}" 2>/dev/null; then
    echo "   ATTENZIONE: il commit base ${base:0:10} non e' nel clone (shallow): rivedi a mano ${WATCHED_FILES}"
    return
  fi
  local files
  files="$(patch_upstream_files) ${WATCHED_FILES}"
  echo "   commit upstream che toccano i file di Nav2Pilot o quelli sorvegliati:"
  # shellcheck disable=SC2086
  g log --oneline "${base}..${new_master}" -- ${files} | sed 's/^/     /'
  # shellcheck disable=SC2086
  g diff --stat "${base}" "${new_master}" -- ${files} | sed 's/^/     /'
}

cmd_status() {
  check_repo
  fetch_upstream
  show_upstream_changes
  local current
  current="$(g rev-parse --abbrev-ref HEAD)"
  echo "== branch corrente: ${current}"
  if g rev-parse --verify --quiet "fork/${FORK_BRANCH}" >/dev/null; then
    local counts
    counts="$(g rev-list --left-right --count "${UPSTREAM_REF}...fork/${FORK_BRANCH}")"
    echo "   cristianku/openpilot ${FORK_BRANCH}: indietro/avanti rispetto a ${UPSTREAM_REF} = ${counts}"
  fi
  echo "== il commit Nav2Pilot si applica pulito su ${UPSTREAM_REF}?"
  local index_file
  index_file="$(mktemp)"
  rm -f "${index_file}"
  # applied to a temporary index only: the working tree and the real index are not touched
  GIT_INDEX_FILE="${index_file}" g read-tree "${UPSTREAM_REF}"
  if fork_diff | GIT_INDEX_FILE="${index_file}" g apply --cached --check; then
    echo "   SI"
  else
    echo "   NO: apply fara' un merge a 3 vie, controlla i conflitti"
  fi
  rm -f "${index_file}"
}

cmd_apply() {
  check_repo
  check_clean
  fetch_upstream
  show_upstream_changes

  local backup
  backup="${BRANCH}-prev"
  if g rev-parse --verify --quiet "${BRANCH}" >/dev/null; then
    g branch -f "${backup}" "${BRANCH}"
    echo "== backup locale del branch: ${backup} = $(g rev-parse --short "${backup}")"
  fi

  echo "== ricreo ${BRANCH} da ${UPSTREAM_REF}"
  g checkout -q --no-track -B "${BRANCH}" "${UPSTREAM_REF}"

  echo "== applico il commit Nav2Pilot di cristianku/openpilot ${FORK_BRANCH} $(g rev-parse --short "${FORK_REF}")"
  if ! fork_diff | g apply --3way --index --whitespace=nowarn; then
    echo >&2
    echo "CONFLITTI: risolvili seguendo docs/nav-alpha-nav2pilot.md, poi 'git add' e:" >&2
    echo "  $0 ${VARIANT} commit   (rifa i controlli prima di committare)" >&2
    exit 2
  fi

  cmd_commit
}

cmd_check() {
  check_repo
  local failed=0
  local file

  echo "== controlli"
  for file in $(nav_files); do
    if [[ ! -f "${REPO}/${file}" ]]; then
      echo "   MANCA ${file}"
      failed=1
      continue
    fi
    if grep -n -E '^(<<<<<<<|=======|>>>>>>>)( |$)' "${REPO}/${file}" >/dev/null; then
      echo "   CONFLITTO non risolto in ${file}"
      failed=1
    fi
    if [[ "${file}" == *.py ]]; then
      local syntax_output
      if ! syntax_output="$(python3 -c 'import ast, sys; ast.parse(open(sys.argv[1]).read(), sys.argv[1])' "${REPO}/${file}" 2>&1)"; then
        echo "   SINTASSI python errata in ${file}: $(echo "${syntax_output}" | tail -1)"
        failed=1
      fi
    fi
  done

  local params_file="${REPO}/openpilot/common/params_keys.h"
  local duplicates
  duplicates="$(grep -o -E '^ *\{"[A-Za-z0-9_]+"' "${params_file}" | tr -d ' {"' | sort | uniq -d | tr '\n' ' ')"
  if [[ -n "${duplicates}" ]]; then
    echo "   CHIAVI DOPPIE in params_keys.h: ${duplicates}"
    failed=1
  fi
  if ! grep -q '{"MapboxToken"' "${params_file}"; then
    echo "   MANCA la chiave MapboxToken in params_keys.h"
    failed=1
  fi

  local module="${NAV_PACKAGE//\//.}"
  if ! grep -q "PythonProcess(\"navd\", \"${module}.navd\"" "${REPO}/openpilot/system/manager/process_config.py"; then
    echo "   process_config.py: navd non punta a ${module}.navd"
    failed=1
  fi
  if ! grep -q "^import ${module}.athena" "${REPO}/openpilot/system/athena/athenad.py"; then
    echo "   athenad.py: manca 'import ${module}.athena' (registra setNavRoute e setMapboxToken)"
    failed=1
  fi

  # the gitlinks must stay exactly as upstream: Nav2Pilot never moves a submodule
  local base
  base="$(branch_base)"
  local upstream_links
  local our_links
  upstream_links="$(g ls-tree -r "${base}" | awk '$2 == "commit" {print $3, $4}')"
  our_links="$(g ls-files --stage | awk '$1 == "160000" {print $2, $4}')"
  if [[ "${upstream_links}" != "${our_links}" ]]; then
    echo "   SUBMODULI diversi da ${UPSTREAM_REF} ${base:0:10}:"
    diff <(echo "${upstream_links}") <(echo "${our_links}") | sed 's/^/     /' || true
    failed=1
  fi

  local python_files
  python_files="$(nav_files | grep '\.py$' || true)"
  if [[ "${failed}" -ne 0 ]]; then
    die "controlli falliti"
  fi
  if command -v ruff >/dev/null 2>&1; then
    # shellcheck disable=SC2086
    if ! (cd "${REPO}" && ruff check ${python_files}); then
      echo "   ATTENZIONE: ruff segnala problemi (versione locale $(ruff --version), non bloccante)"
    fi
  fi

  echo "   tutti i controlli OK"
}

# How many commits the local branch has on its upstream base: 0 before the first commit, 1 after; more is wrong.
commits_on_base() {
  g rev-list --count "$(branch_base)..HEAD"
}

cmd_commit() {
  cmd_check
  if ! g diff --quiet --ignore-submodules=all; then
    g diff --stat --ignore-submodules=all >&2
    die "ci sono modifiche non in index: fai 'git add' dei file risolti"
  fi
  if g diff --cached --quiet --ignore-submodules=all; then
    echo "== niente in index da committare"
    return
  fi
  local count
  count="$(commits_on_base)"
  if [[ "${count}" -eq 1 ]]; then
    # the branch stays upstream + one Nav2Pilot commit: a change is folded into it
    g commit -q --amend --no-edit
    echo "== commit Nav2Pilot corretto (amend): $(g log -1 --oneline)"
  elif [[ "${count}" -eq 0 ]]; then
    local message_file
    message_file="$(mktemp)"
    # same message as the published commit
    g log -1 --format=%B "${FORK_REF}" > "${message_file}"
    g commit -q -F "${message_file}"
    rm -f "${message_file}"
    echo "== commit locale: $(g log -1 --oneline)"
  else
    die "${BRANCH} ha ${count} commit sopra ${UPSTREAM_REF}: deve averne uno solo (git rebase -i e squash)"
  fi
  g diff --stat "$(branch_base)" HEAD | tail -1
  echo "   NON pubblicato: per pubblicarlo '$0 ${VARIANT} push'"
}

# strips what legitimately differs between the two forks: header, module path, class name
normalize_nav_file() {
  awk '
    skip_blank == 1 && $0 == "" { skip_blank = 0; next }
    { skip_blank = 0 }
    /^Copyright \(c\) 2021-, Haibin Wen, sunnypilot/ { in_header = 1 }
    in_header == 1 {
      if ($0 ~ /^See the LICENSE.md file/) { in_header = 0; skip_blank = 1 }
      next
    }
    { print }
  ' "$1" | sed -e 's/openpilot\.sunnypilot\.navd/openpilot.selfdrive.navigation.nav2pilot/g' \
               -e 's/RouteEngineSP/Nav2PilotRouteEngine/g'
}

cmd_sync_check() {
  local sunny_dir="${CRISTIANKU_DIR}/sunnypilot-nav-alpha/openpilot/sunnypilot/navd"
  local comma_dir="${CRISTIANKU_DIR}/openpilot-nav-alpha/openpilot/selfdrive/navigation/nav2pilot"
  local file
  local different=0
  for file in athena.py mapbox.py waypoints.py navd.py tests/test_navd_mapbox.py tests/test_navd_waypoints.py; do
    echo "== ${file}"
    if ! diff <(normalize_nav_file "${sunny_dir}/${file}") <(normalize_nav_file "${comma_dir}/${file}"); then
      different=1
    fi
  done
  if [[ "${different}" -eq 0 ]]; then
    echo "   i due pacchetti sono identici"
  else
    echo "   differenze sopra: attese solo quelle su sunnylink (docstring di athena.py e test sul dispatcher)"
  fi
}

cmd_push() {
  check_repo
  check_clean
  local current
  current="$(g rev-parse --abbrev-ref HEAD)"
  if [[ "${current}" != "${BRANCH}" ]]; then
    die "sei su ${current}, non su ${BRANCH}"
  fi
  cmd_check
  # The published branch is always an upstream master commit + the one Nav2Pilot commit: the setups take
  # exactly that commit.
  local count
  count="$(commits_on_base)"
  if [[ "${count}" -ne 1 ]]; then
    die "${BRANCH} ha ${count} commit sopra ${UPSTREAM_REF}: deve averne uno solo"
  fi
  local head
  head="$(g rev-parse HEAD)"
  local published
  published="$(git ls-remote "${FORK_URL}" "refs/heads/${FORK_BRANCH}" | awk 'NR == 1 { print $1 }')"
  if [[ "${published}" == "${head}" ]]; then
    echo "== cristianku/openpilot ${FORK_BRANCH} e' gia' ${head:0:10}"
  elif [[ "${NO_PUSH:-false}" == "true" ]]; then
    echo "NO_PUSH: ${FORK_BRANCH} ${head:0:10} non pubblicato (su GitHub: ${published:0:10})"
    return
  else
    echo "== push di ${BRANCH} su cristianku/openpilot ${FORK_BRANCH} (prima: ${published:-nessuno})"
    # LFS lives on comma's/sunnypilot's own storage (.lfsconfig): nothing to upload
    GIT_LFS_SKIP_PUSH=1 g -c push.negotiate=true push -q \
      --force-with-lease="refs/heads/${FORK_BRANCH}:${published}" "${FORK_URL}" "HEAD:refs/heads/${FORK_BRANCH}"
  fi
  # onto the latest master if it moved meanwhile, and the sunny mirror
  bash "${UPDATE_SCRIPT}" "${FORK_BRANCH}"
}

if [[ "${COMMAND}" == "status" ]]; then
  cmd_status
elif [[ "${COMMAND}" == "apply" ]]; then
  cmd_apply
elif [[ "${COMMAND}" == "check" ]]; then
  cmd_check
elif [[ "${COMMAND}" == "commit" ]]; then
  cmd_commit
elif [[ "${COMMAND}" == "sync-check" ]]; then
  cmd_sync_check
elif [[ "${COMMAND}" == "push" ]]; then
  cmd_push
else
  usage
fi
