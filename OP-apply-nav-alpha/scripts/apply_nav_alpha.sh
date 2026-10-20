#!/usr/bin/env bash
# Riapplica le modifiche Nav2Pilot (setNavRoute con waypoint + setMapboxToken) su un master fresco.
# Documentazione: openpilot_scripts/docs/nav-alpha-nav2pilot.md
set -euo pipefail

SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PATCH_DIR="${SKILL_DIR}/patches"
CRISTIANKU_DIR="/Users/cristianku/GitHub/COMMA.AI/CRISTIANKU"

usage() {
  cat >&2 <<'EOF'
Uso: apply_nav_alpha.sh <sunny|comma> <comando>

Comandi:
  status      fetch del master, dice se il branch e' indietro e se la patch si applica pulita
  apply       backup del branch, ricrea il branch dal master, applica la patch, controlli, commit locale
  check       controlli statici sul working tree
  commit      controlli + commit delle modifiche in index (dopo una risoluzione manuale di conflitti)
  save-patch  rigenera patches/<variante>.patch dal branch (quando cambi il codice Nav2Pilot)
  sync-check  confronta il pacchetto Nav2Pilot di sunny con quello di comma (devono restare uguali)
  push        push --force-with-lease del branch sul fork (SOLO con l'ok di Cristian)

Variabili: NAV_REPO (cartella del clone), NAV_BRANCH (default nav-alpha)
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
  PATCH_FILE="${PATCH_DIR}/sunnypilot.patch"
  BASE_FILE="${PATCH_DIR}/sunnypilot.base"
  NAV_PACKAGE="openpilot/sunnypilot/navd"
elif [[ "${VARIANT}" == "comma" || "${VARIANT}" == "openpilot" ]]; then
  VARIANT="comma"
  DEFAULT_REPO="${CRISTIANKU_DIR}/openpilot-nav-alpha"
  UPSTREAM_REMOTE="commaai"
  UPSTREAM_URL_PATTERN="commaai/openpilot"
  PATCH_FILE="${PATCH_DIR}/openpilot.patch"
  BASE_FILE="${PATCH_DIR}/openpilot.base"
  NAV_PACKAGE="openpilot/selfdrive/navigation/nav2pilot"
else
  usage
fi

REPO="${NAV_REPO:-${DEFAULT_REPO}}"
BRANCH="${NAV_BRANCH:-nav-alpha}"
FORK_REMOTE="origin"
UPSTREAM_REF="${UPSTREAM_REMOTE}/master"
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
  local fork_url
  fork_url="$(g remote get-url "${FORK_REMOTE}" 2>/dev/null || true)"
  if [[ "${fork_url}" != *"cristianku/"* ]]; then
    die "il remote ${FORK_REMOTE} di ${REPO} non e' il fork cristianku (trovato: '${fork_url}')"
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
  echo "== fetch ${UPSTREAM_REF} e ${FORK_REMOTE}/${BRANCH}"
  g fetch "${UPSTREAM_REMOTE}" master
  g fetch "${FORK_REMOTE}" "${BRANCH}" || echo "(il fork non ha ancora ${BRANCH})"
}

# the files the patch modifies or creates, one per line
patch_files() {
  grep '^diff --git ' "${PATCH_FILE}" | sed 's#^diff --git a/\(.*\) b/.*#\1#'
}

# files that exist upstream and the patch modifies (the "upstream touches")
patch_upstream_files() {
  local file
  for file in $(patch_files); do
    if g cat-file -e "${UPSTREAM_REF}:${file}" 2>/dev/null; then
      echo "${file}"
    fi
  done
}

show_upstream_changes() {
  local base
  base="$(cat "${BASE_FILE}")"
  local new_master
  new_master="$(g rev-parse "${UPSTREAM_REF}")"
  echo "== patch salvata su ${UPSTREAM_REF} ${base:0:10}, master ora ${new_master:0:10}"
  if [[ "${base}" == "${new_master}" ]]; then
    echo "   master non e' cambiato dalla patch"
    return
  fi
  if ! g cat-file -e "${base}^{commit}" 2>/dev/null; then
    echo "   ATTENZIONE: il commit base ${base:0:10} non e' nel clone (shallow): rivedi a mano ${WATCHED_FILES}"
    return
  fi
  local files
  files="$(patch_upstream_files) ${WATCHED_FILES}"
  echo "   commit upstream che toccano i file della patch o quelli sorvegliati:"
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
  if g rev-parse --verify --quiet "${FORK_REMOTE}/${BRANCH}" >/dev/null; then
    local counts
    counts="$(g rev-list --left-right --count "${UPSTREAM_REF}...${FORK_REMOTE}/${BRANCH}")"
    echo "   ${FORK_REMOTE}/${BRANCH}: indietro/avanti rispetto a ${UPSTREAM_REF} = ${counts}"
  fi
  echo "== la patch si applica pulita su ${UPSTREAM_REF}?"
  local index_file
  index_file="$(mktemp)"
  rm -f "${index_file}"
  # applied to a temporary index only: the working tree and the real index are not touched
  GIT_INDEX_FILE="${index_file}" g read-tree "${UPSTREAM_REF}"
  if GIT_INDEX_FILE="${index_file}" g apply --cached --check "${PATCH_FILE}"; then
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
  g branch -q --set-upstream-to="${FORK_REMOTE}/${BRANCH}" "${BRANCH}" 2>/dev/null || true

  echo "== applico $(basename "${PATCH_FILE}")"
  if ! g apply --3way --index --whitespace=nowarn "${PATCH_FILE}"; then
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
  for file in $(patch_files); do
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

  # the gitlinks must stay exactly as upstream master: the patch never moves a submodule
  local upstream_links
  local our_links
  upstream_links="$(g ls-tree -r "${UPSTREAM_REF}" | awk '$2 == "commit" {print $3, $4}')"
  our_links="$(g ls-files --stage | awk '$1 == "160000" {print $2, $4}')"
  if [[ "${upstream_links}" != "${our_links}" ]]; then
    echo "   SUBMODULI diversi da ${UPSTREAM_REF}:"
    diff <(echo "${upstream_links}") <(echo "${our_links}") | sed 's/^/     /' || true
    failed=1
  fi

  local python_files
  python_files="$(patch_files | grep '\.py$' || true)"
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

cmd_commit() {
  cmd_check
  if ! g diff --quiet --ignore-submodules=all; then
    g diff --stat --ignore-submodules=all >&2
    die "ci sono modifiche non in index: fai 'git add' dei file risolti"
  fi
  local master
  master="$(g rev-parse --short "${UPSTREAM_REF}")"
  local message_file
  message_file="$(mktemp)"
  cat > "${message_file}" <<EOF
nav alpha: Nav2Pilot setNavRoute waypoints and setMapboxToken

Reapplied with OP-apply-nav-alpha on ${UPSTREAM_REF} ${master}.
New code in ${NAV_PACKAGE}/; upstream touches: one import in athenad,
the navd module in process_config, the MapboxToken param key.

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>
EOF
  g commit -q -F "${message_file}"
  rm -f "${message_file}"
  echo "== commit locale: $(g log -1 --oneline)"
  g diff --stat "${UPSTREAM_REF}" HEAD | tail -1
  echo "   NON pushato: per pubblicarlo serve l'ok di Cristian, poi '$0 ${VARIANT} push'"
}

cmd_save_patch() {
  check_repo
  check_clean
  local base
  base="$(g merge-base "${UPSTREAM_REF}" "${BRANCH}")"
  local master
  master="$(g rev-parse "${UPSTREAM_REF}")"
  if [[ "${base}" != "${master}" ]]; then
    echo "ATTENZIONE: ${BRANCH} e' basato su ${base:0:10}, non sull'ultimo ${UPSTREAM_REF} ${master:0:10}"
  fi
  g diff --binary --full-index --ignore-submodules=all "${base}" "${BRANCH}" > "${PATCH_FILE}"
  echo "${base}" > "${BASE_FILE}"
  echo "== salvata $(basename "${PATCH_FILE}") (base ${base:0:10}):"
  git apply --stat "${PATCH_FILE}" | tail -1
  echo "   ricordati di aggiornare la patch dell'altra variante e docs/nav-alpha-nav2pilot.md se serve"
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
  echo "== push --force-with-lease di ${BRANCH} su ${FORK_REMOTE}"
  # LFS lives on comma's/sunnypilot's own storage (.lfsconfig): nothing to upload from the fork, as in the setup skills
  GIT_LFS_SKIP_PUSH=1 g push --force-with-lease="${BRANCH}" "${FORK_REMOTE}" "${BRANCH}"
}

if [[ "${COMMAND}" == "status" ]]; then
  cmd_status
elif [[ "${COMMAND}" == "apply" ]]; then
  cmd_apply
elif [[ "${COMMAND}" == "check" ]]; then
  cmd_check
elif [[ "${COMMAND}" == "commit" ]]; then
  cmd_commit
elif [[ "${COMMAND}" == "save-patch" ]]; then
  cmd_save_patch
elif [[ "${COMMAND}" == "sync-check" ]]; then
  cmd_sync_check
elif [[ "${COMMAND}" == "push" ]]; then
  cmd_push
else
  usage
fi
