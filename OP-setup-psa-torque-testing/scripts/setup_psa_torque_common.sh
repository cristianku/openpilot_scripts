#!/usr/bin/env bash
set -euo pipefail

# ---------------------------------------------------------------------------
# Frozen-release PSA setup (submodule pointers, builds on device).
#
# Source is a configured full, buildable upstream release tag
# (sunnypilot/sunnypilot or commaai/openpilot). The release source has SConstruct + all
# SConscript, opendbc_repo / neural_network_data as real SUBMODULES, and NO
# `prebuilt` marker, so the device compiles from source on first boot and our
# torque-based psa.h lands in the panda firmware.
#
# Why not the prebuilt release branch (learned the hard way 2026-07-23):
# sunnypilot's release-mici is prebuilt-only - it ships compiled binaries + a
# `prebuilt` marker AND STRIPS the root SConstruct, so the device cannot
# compile there ("No SConstruct file found") and our compiled psa.h can never
# be deployed. We therefore stay on a frozen release tag like v2026.002.001,
# which is the full buildable source. Helpers below are layout-robust (ask
# git for real paths) so they work on both the old and new monorepo layout.
# The device build takes ~15-20 min on first boot - the price for compiled
# safety, the same way a source build does.
# ---------------------------------------------------------------------------

BRANCH="${BRANCH:?BRANCH must be set}"
GITHUB_USER="${GITHUB_USER:-cristianku}"
WORKSPACE_ROOT="${WORKSPACE_ROOT:-/Users/cristianku/GitHub/COMMA.AI/CRISTIANKU}"
NO_PUSH="${NO_PUSH:-false}"   # set true to build the branch locally + commit WITHOUT pushing (safe dry run)

branch_suffix="${BRANCH#psa-torque}"
branch_suffix="${branch_suffix#-}"
dir_branch_suffix="${branch_suffix//-/_}"
dir_suffix="${dir_branch_suffix:+_${dir_branch_suffix}}"
title_suffix=""
if [[ -n "${branch_suffix}" ]]; then
  title_branch_suffix="${branch_suffix//-/ }"
title_suffix=" $(printf '%s' "${title_branch_suffix}" | awk '{ print toupper(substr($0, 1, 1)) substr($0, 2) }')"
fi

OPENPILOT_DIR="${OPENPILOT_DIR:-new_openpilot_psa_torque${dir_suffix}}"

OPENPILOT_REPO="${OPENPILOT_REPO:-https://github.com/${GITHUB_USER}/openpilot.git}"
OPENPILOT_SOURCE_REPO="${OPENPILOT_SOURCE_REPO:?OPENPILOT_SOURCE_REPO must be set}"
OPENPILOT_SOURCE_BRANCH="${OPENPILOT_SOURCE_BRANCH:?OPENPILOT_SOURCE_BRANCH must be set (a branch like master, or a release tag)}"
# [pinned source] - START
OPENPILOT_SOURCE_COMMIT="${OPENPILOT_SOURCE_COMMIT:-}"
RESOLVED_OPENPILOT_SOURCE_COMMIT=""
# [pinned source] - END
OPENDBC_REPO="${OPENDBC_REPO:-https://github.com/${GITHUB_USER}/opendbc.git}"
OPENDBC_SOURCE_REPO="${OPENDBC_SOURCE_REPO:-${OPENDBC_REPO}}"
OPENDBC_SOURCE_BRANCH="${OPENDBC_SOURCE_BRANCH:-}"
USE_CUSTOM_NEURAL_NETWORK_DATA="${USE_CUSTOM_NEURAL_NETWORK_DATA:-false}"
NEURAL_NETWORK_DATA_REPO="${NEURAL_NETWORK_DATA_REPO:-https://github.com/${GITHUB_USER}/neural-network-data.git}"
NEURAL_NETWORK_DATA_BRANCH="${NEURAL_NETWORK_DATA_BRANCH:-master}"
COMMIT_MESSAGE="${COMMIT_MESSAGE:-Update Peugeot 3008${title_suffix} repository pointers (on ${OPENPILOT_SOURCE_BRANCH})}"

NEURAL_NETWORK_DATA_SHA=""

# Read before main() changes directory.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EXTRA_MODEL_CATALOG_SOURCE_REPO="${EXTRA_MODEL_CATALOG_SOURCE_REPO:-https://github.com/${GITHUB_USER}/sunnypilot.git}"
EXTRA_MODEL_CATALOG_SOURCE_BRANCH="${EXTRA_MODEL_CATALOG_SOURCE_BRANCH:-distilled}"
EXTRA_MODEL_CATALOG_UPSTREAM_REPO="${EXTRA_MODEL_CATALOG_UPSTREAM_REPO:-https://github.com/sunnypilot/sunnypilot.git}"
SKIP_EXTRA_MODEL_CATALOG="${SKIP_EXTRA_MODEL_CATALOG:-false}"   # true: leave the sunnypilot Models menu as upstream
# [nav source] - START
# Nav2Pilot, injected on every base from its canonical patch (OP-apply-nav-alpha/patches/<fork>.patch) by the
# testing wrapper; empty: built without it. The .base file names the upstream commit the patch was made on.
NAV2PILOT_PATCH="${NAV2PILOT_PATCH:-}"
NAV2PILOT_BASE="${NAV2PILOT_BASE:-}"
# upstream files the Nav2Pilot code copies or subclasses (as scripts/update_fork_branch.sh): a change there can
# apply cleanly and still be lost
NAV_WATCHED_FILES="openpilot/selfdrive/navigation/navd.py openpilot/selfdrive/navigation/tiles.py openpilot/system/athena/rpc.py"
# [nav source] - END
# [speed limits] - START
# The speed-limit work (Speed Limit Source "Signs Read By", speedVisionSP, the models submodule) lives on its own
# branch of cristianku/sunnypilot, as the opendbc work lives on psa-torque-sunny-testing of cristianku/opendbc.
SPEED_LIMITS_SOURCE_REPO="${SPEED_LIMITS_SOURCE_REPO:-https://github.com/${GITHUB_USER}/sunnypilot.git}"
SPEED_LIMITS_SOURCE_BRANCH="${SPEED_LIMITS_SOURCE_BRANCH:-speed-limits}"
SPEED_LIMITS_UPSTREAM_REPO="${SPEED_LIMITS_UPSTREAM_REPO:-https://github.com/sunnypilot/sunnypilot.git}"
SKIP_SPEED_LIMITS="${SKIP_SPEED_LIMITS:-false}"   # true: leave Speed Limit Assist as upstream
# [speed limits] - END

ensure_remote_branch() {
  local repo_url="$1"
  local branch="$2"
  local source_repo_url="${3:-}"
  local source_branch="${4:-}"

  if git ls-remote --exit-code --heads "${repo_url}" "${branch}" >/dev/null 2>&1; then
    return
  fi

  if [[ -z "${source_repo_url}" ]]; then
    source_repo_url="${repo_url}"
  fi

  if [[ -z "${source_branch}" ]]; then
    source_branch="$(
      git ls-remote --symref "${source_repo_url}" HEAD \
        | awk '/^ref:/ { sub("refs/heads/", "", $2); print $2; exit }'
    )"
  fi

  if [[ -z "${source_branch}" ]]; then
    echo "ERROR: could not determine source branch for ${source_repo_url}" >&2
    exit 1
  fi

  local tmp_dir
  tmp_dir="$(mktemp -d)"

  echo "Remote branch ${branch} does not exist in ${repo_url}; creating from ${source_repo_url} ${source_branch}"
  if ! (
    git clone --no-tags --single-branch --branch "${source_branch}" "${source_repo_url}" "${tmp_dir}/repo"
    git -C "${tmp_dir}/repo" checkout -b "${branch}"
    git -C "${tmp_dir}/repo" remote add target "${repo_url}"
    GIT_LFS_SKIP_PUSH=1 git -C "${tmp_dir}/repo" push target "${branch}"
  ); then
    rm -rf "${tmp_dir}"
    echo "ERROR: failed to create remote branch ${branch} in ${repo_url}" >&2
    exit 1
  fi

  rm -rf "${tmp_dir}"
}

recreate_clone_from_source() {
  local target_repo_url="$1"
  local dest="$2"
  local branch="$3"
  local source_repo_url="$4"
  local source_ref="$5"   # a stable TAG (or branch); git clone --branch accepts both

  if [[ -z "${dest}" || "${dest}" == "/" || "${dest}" == "." ]]; then
    echo "ERROR: refusing to recreate unsafe destination: ${dest}" >&2
    exit 1
  fi

  if [[ -e "${dest}" ]]; then
    echo "Recreating ${dest} directly from ${source_repo_url} ${source_ref}"
    rm -rf "${dest}"
  fi

  # --branch accepts a branch OR a tag; clone it, then create OUR branch from
  # that exact tree so the device tracks a normal branch.
  GIT_LFS_SKIP_SMUDGE=1 git clone --no-tags --single-branch --branch "${source_ref}" "${source_repo_url}" "${dest}"
  local source_commit
  # [pinned source] - START
  local source_tip
  source_tip="$(git -C "${dest}" rev-parse HEAD)"
  source_commit="${source_tip}"
  if [[ -n "${OPENPILOT_SOURCE_COMMIT}" ]]; then
    if ! source_commit="$(git -C "${dest}" rev-parse --verify "${OPENPILOT_SOURCE_COMMIT}^{commit}" 2>/dev/null)"; then
      echo "ERROR: commit ${OPENPILOT_SOURCE_COMMIT} is unavailable from ${source_repo_url} ${source_ref}" >&2
      exit 1
    fi
    if ! git -C "${dest}" merge-base --is-ancestor "${source_commit}" "${source_tip}"; then
      echo "ERROR: commit ${source_commit} is not in ${source_repo_url} ${source_ref}" >&2
      exit 1
    fi
    GIT_LFS_SKIP_SMUDGE=1 git -C "${dest}" checkout --detach "${source_commit}"
  fi
  RESOLVED_OPENPILOT_SOURCE_COMMIT="${source_commit}"
  # [pinned source] - END
  echo "Using upstream source ${source_ref} (${source_commit})"
  git -C "${dest}" checkout -B "${branch}"
  git -C "${dest}" remote rename origin source
  git -C "${dest}" remote add origin "${target_repo_url}"
}

set_opendbc_pointer() {
  local dest="$1"
  local repo_url="$2"
  local branch="$3"
  local source_repo_url="${4:-}"
  local source_branch="${5:-}"

  ensure_remote_branch "${repo_url}" "${branch}" "${source_repo_url}" "${source_branch}"

  local opendbc_sha
  opendbc_sha="$(git ls-remote --heads "${repo_url}" "refs/heads/${branch}" | awk 'NR == 1 { print $1 }')"
  if [[ ! "${opendbc_sha}" =~ ^[0-9a-fA-F]{40}$ ]]; then
    echo "ERROR: could not resolve ${repo_url} ${branch}" >&2
    exit 1
  fi

  # find the opendbc submodule path (opendbc_repo), robust to layout
  local submodule_path
  submodule_path="$(git -C "${dest}" ls-files --stage \
    | awk '$1 == "160000" && $4 ~ /(^|\/)opendbc_repo$/ && !found { found = $4 } END { print found }')"
  submodule_path="${submodule_path:-opendbc_repo}"
  local submodule_name
  submodule_name="$(git -C "${dest}" config --file .gitmodules --get-regexp '^submodule\..*\.path$' \
    | awk -v p="${submodule_path}" '$2 == p && !name { name = $1; sub(/^submodule\./, "", name); sub(/\.path$/, "", name) } END { print name }')"
  submodule_name="${submodule_name:-opendbc}"

  git -C "${dest}" config --file .gitmodules "submodule.${submodule_name}.url" "${repo_url}"
  git -C "${dest}" add -- .gitmodules
  git -C "${dest}" update-index --add --cacheinfo "160000,${opendbc_sha},${submodule_path}"
  echo "Pointing ${submodule_path} to ${repo_url} ${branch} (${opendbc_sha})"
}

set_neural_network_data_pointer() {
  local dest="$1"
  if [[ "${USE_CUSTOM_NEURAL_NETWORK_DATA}" != "true" ]]; then
    return
  fi

  # Ask git for the actual tracked gitlink path (drain the full ls-files stream,
  # no awk early exit, to avoid SIGPIPE/141 under pipefail).
  local submodule_path
  submodule_path="$(git -C "${dest}" ls-files --stage \
    | awk '$1 == "160000" && $4 ~ /(^|\/)sunnypilot\/neural_network_data$/ && !found { found = $4 } END { print found }')"
  if [[ -z "${submodule_path}" ]]; then
    echo "ERROR: sunnypilot/neural_network_data is not a submodule in ${dest}" >&2
    exit 1
  fi
  local submodule_name
  submodule_name="$(git -C "${dest}" config --file .gitmodules --get-regexp '^submodule\..*\.path$' \
    | awk -v p="${submodule_path}" '$2 == p && !name { name = $1; sub(/^submodule\./, "", name); sub(/\.path$/, "", name) } END { print name }')"
  submodule_name="${submodule_name:-sunnypilot/neural_network_data}"

  NEURAL_NETWORK_DATA_SHA="$(git ls-remote --heads "${NEURAL_NETWORK_DATA_REPO}" "refs/heads/${NEURAL_NETWORK_DATA_BRANCH}" | awk 'NR == 1 { print $1 }')"
  if [[ ! "${NEURAL_NETWORK_DATA_SHA}" =~ ^[0-9a-fA-F]{40}$ ]]; then
    echo "ERROR: could not resolve ${NEURAL_NETWORK_DATA_REPO} ${NEURAL_NETWORK_DATA_BRANCH}" >&2
    exit 1
  fi

  git -C "${dest}" config --file .gitmodules "submodule.${submodule_name}.url" "${NEURAL_NETWORK_DATA_REPO}"
  git -C "${dest}" add -- .gitmodules
  git -C "${dest}" update-index --add --cacheinfo "160000,${NEURAL_NETWORK_DATA_SHA},${submodule_path}"
  echo "Pointing ${submodule_path} to ${NEURAL_NETWORK_DATA_REPO} ${NEURAL_NETWORK_DATA_BRANCH} (${NEURAL_NETWORK_DATA_SHA})"
}

enable_psa_torqued_learning() {
  # Upstream ships torqued's ALLOWED_CARS gate without PSA, so live
  # latAccelFactor/friction learning stays off for the Peugeot 3008. Add 'psa'.
  # Idempotent. Ask git for the real torqued path (layout-robust).
  local dest="$1"
  local torqued_rel
  torqued_rel="$(git -C "${dest}" ls-files \
    | grep -E '(^|/)selfdrive/locationd/torqued\.py$' | head -n1)"
  if [[ -z "${torqued_rel}" ]]; then
    echo "ERROR: torqued.py not tracked under ${dest}" >&2
    exit 1
  fi
  local torqued="${dest}/${torqued_rel}"
  echo "Using torqued at ${torqued_rel}"

  if grep -Eq "^ALLOWED_CARS *=.*['\"]psa['\"]" "${torqued}"; then
    echo "torqued ALLOWED_CARS already includes psa; nothing to do"
    return
  fi

  if ! grep -Eq "^ALLOWED_CARS *= *\[.*\]" "${torqued}"; then
    echo "ERROR: could not find ALLOWED_CARS list in ${torqued}" >&2
    exit 1
  fi

  sed -i.bak -E "s/^(ALLOWED_CARS *= *\[[^]]*)\]/\1, 'psa']/" "${torqued}"
  rm -f "${torqued}.bak"

  if ! grep -Eq "^ALLOWED_CARS *=.*['\"]psa['\"]" "${torqued}"; then
    echo "ERROR: failed to add psa to ALLOWED_CARS in ${torqued}" >&2
    exit 1
  fi

  git -C "${dest}" add -- "${torqued_rel}"
  echo "Enabled PSA torque-param learning (added 'psa' to torqued ALLOWED_CARS)"
}

enable_extra_model_catalog() {
  # [distill source] - START
  # Apply ONLY the three model-catalog file changes from the canonical
  # cristianku/sunnypilot:distilled branch. Never use a second local patch copy.
  # Keep Nav2Pilot/PSA changes from this checkout and fail closed on conflicts.
  local dest="$1"
  if [[ "${SKIP_EXTRA_MODEL_CATALOG}" == "true" ]]; then
    echo "SKIP_EXTRA_MODEL_CATALOG set: Models menu left as upstream"
    return
  fi

  local fetcher_rel
  fetcher_rel="$(git -C "${dest}" ls-files | grep -E '(^|/)sunnypilot/models/fetcher\.py$' | head -n1 || true)"
  if [[ -z "${fetcher_rel}" ]]; then
    echo "No sunnypilot Models menu in this source: extra model catalog not needed"
    return
  fi

  local extra_rel
  extra_rel="$(git -C "${dest}" ls-files | grep -E '(^|/)sunnypilot/models/extra_catalog\.py$' | head -n1 || true)"
  if [[ -n "${extra_rel}" ]]; then
    echo "Extra model catalog already in this checkout; not applying it again"
    return
  fi

  local src_ref=refs/remotes/distill/catalog
  local upstream_ref=refs/remotes/distill/upstream
  echo "Fetching canonical Distill source ${EXTRA_MODEL_CATALOG_SOURCE_REPO}:${EXTRA_MODEL_CATALOG_SOURCE_BRANCH}"
  git -C "${dest}" fetch -q --no-tags "${EXTRA_MODEL_CATALOG_SOURCE_REPO}" \
    "+refs/heads/${EXTRA_MODEL_CATALOG_SOURCE_BRANCH}:${src_ref}" || {
      echo "ERROR: canonical Distill source branch missing/unreachable. No local patch fallback." >&2
      exit 1
    }
  git -C "${dest}" fetch -q --no-tags "${EXTRA_MODEL_CATALOG_UPSTREAM_REPO}" \
    "+refs/heads/master:${upstream_ref}"

  if ! git -C "${dest}" cat-file -e "${src_ref}:openpilot/sunnypilot/models/extra_catalog.py" 2>/dev/null; then
    echo "ERROR: canonical Distill source does not contain extra_catalog.py" >&2
    exit 1
  fi

  local base_commit
  base_commit="$(git -C "${dest}" merge-base "${upstream_ref}" "${src_ref}")"
  if [[ -z "${base_commit}" ]]; then
    echo "ERROR: canonical Distill branch has no common SunnyPilot upstream ancestor" >&2
    exit 1
  fi

  local patch_file
  patch_file="$(mktemp)"
  # Whitelist: do not copy the entire Distill branch (which may have other
  # upstream updates). Extract only the catalog feature changes since its
  # upstream merge-base; apply with 3-way context to PSA/Nav2Pilot checkout.
  git -C "${dest}" diff --binary "${base_commit}" "${src_ref}" -- \
    openpilot/sunnypilot/models/extra_catalog.py \
    openpilot/sunnypilot/models/fetcher.py \
    openpilot/sunnypilot/models/tests/test_manager_download.py > "${patch_file}"
  if [[ ! -s "${patch_file}" ]]; then
    rm -f "${patch_file}"
    echo "ERROR: canonical Distill branch has no catalog changes to integrate" >&2
    exit 1
  fi
  if ! git -C "${dest}" apply --3way --index "${patch_file}"; then
    rm -f "${patch_file}"
    echo "ERROR: canonical Distill changes conflict with the PSA/Nav2Pilot base." >&2
    echo "Resolve the conflict in source/checkout; do not silently restore a stale local patch." >&2
    exit 1
  fi
  rm -f "${patch_file}"
  echo "Added Distill models from canonical source ${src_ref} (Model menu + SunnyLink)"
  # [distill source] - END
}

enable_nav2pilot() {
  # [nav source] - START
  # Apply the Nav2Pilot patch with 3-way context on the chosen base (master, a pinned commit or a release); stop
  # without publishing on a conflict: resolve it with OP-apply-nav-alpha, which saves the patch again.
  local dest="$1"
  if [[ -z "${NAV2PILOT_PATCH}" ]]; then
    echo "SKIP_NAV set: built without Nav2Pilot"
    return
  fi
  if ! git -C "${dest}" apply --3way --index "${NAV2PILOT_PATCH}"; then
    echo "ERROR: the Nav2Pilot patch does not apply to this base (${OPENPILOT_SOURCE_BRANCH})." >&2
    echo "Resolve it with OP-apply-nav-alpha, or SKIP_NAV=true to build without Nav2Pilot." >&2
    exit 1
  fi
  local base=""
  [[ -n "${NAV2PILOT_BASE}" && -s "${NAV2PILOT_BASE}" ]] && base="$(tr -d '[:space:]' < "${NAV2PILOT_BASE}")"
  if [[ -n "${base}" ]] && git -C "${dest}" cat-file -e "${base}^{commit}" 2>/dev/null; then
    local watched
    # shellcheck disable=SC2086
    watched="$(git -C "${dest}" diff --name-only "${base}" HEAD -- ${NAV_WATCHED_FILES})"
    if [[ -n "${watched}" ]]; then
      echo "WARNING: upstream changed files the Nav2Pilot code copies since its patch was made (${base:0:9}):" >&2
      echo "${watched}" >&2
      echo "It applied cleanly, but check them with OP-apply-nav-alpha." >&2
    fi
  fi
  echo "Added Nav2Pilot from $(basename "${NAV2PILOT_PATCH}")"
  # [nav source] - END
}

enable_speed_limits() {
  # [speed limits] - START
  # Apply the speed-limit branch of cristianku/sunnypilot: every change it carries since its merge-base with
  # sunnypilot/sunnypilot:master (the branch holds only that work), files and the models submodule pointer, with
  # 3-way context on the PSA/Nav2Pilot checkout. Fail closed on conflicts, as the Distill catalog does.
  local dest="$1"
  if [[ "${SKIP_SPEED_LIMITS}" == "true" ]]; then
    echo "SKIP_SPEED_LIMITS set: Speed Limit Assist left as upstream"
    return
  fi

  local resolver_rel
  resolver_rel="$(git -C "${dest}" ls-files | grep -E '(^|/)sunnypilot/selfdrive/controls/lib/speed_limit/speed_limit_resolver\.py$' | head -n1 || true)"
  if [[ -z "${resolver_rel}" ]]; then
    echo "No sunnypilot Speed Limit Assist in this source: speed limits not needed"
    return
  fi
  if git -C "${dest}" grep -q -e 'SpeedLimitSignReader' -- "${resolver_rel}"; then
    echo "Speed limits already in this checkout; not applying them again"
    return
  fi

  local src_ref=refs/remotes/speedlimits/source
  local upstream_ref=refs/remotes/speedlimits/upstream
  echo "Fetching speed limits ${SPEED_LIMITS_SOURCE_REPO}:${SPEED_LIMITS_SOURCE_BRANCH}"
  git -C "${dest}" fetch -q --no-tags "${SPEED_LIMITS_SOURCE_REPO}" \
    "+refs/heads/${SPEED_LIMITS_SOURCE_BRANCH}:${src_ref}" || {
      echo "ERROR: speed limits source branch missing/unreachable (SKIP_SPEED_LIMITS=true to build without it)." >&2
      exit 1
    }
  git -C "${dest}" fetch -q --no-tags "${SPEED_LIMITS_UPSTREAM_REPO}" "+refs/heads/master:${upstream_ref}"

  local base_commit
  base_commit="$(git -C "${dest}" merge-base "${upstream_ref}" "${src_ref}" || true)"
  if [[ -z "${base_commit}" ]]; then
    echo "ERROR: speed limits branch has no common SunnyPilot upstream ancestor" >&2
    exit 1
  fi

  local patch_file
  patch_file="$(mktemp)"
  git -C "${dest}" diff --binary "${base_commit}" "${src_ref}" > "${patch_file}"
  if [[ ! -s "${patch_file}" ]]; then
    rm -f "${patch_file}"
    echo "Speed limits branch has no changes over SunnyPilot master: nothing to add"
    return
  fi
  if ! git -C "${dest}" apply --3way --index "${patch_file}"; then
    rm -f "${patch_file}"
    echo "ERROR: speed limits changes conflict with the PSA/Nav2Pilot base." >&2
    echo "Merge sunnypilot master into ${SPEED_LIMITS_SOURCE_BRANCH} and resolve there, or SKIP_SPEED_LIMITS=true." >&2
    exit 1
  fi
  rm -f "${patch_file}"
  echo "Added speed limits from ${SPEED_LIMITS_SOURCE_BRANCH} ($(git -C "${dest}" rev-parse --short "${src_ref}"))"
  # [speed limits] - END
}

commit_and_push() {
  local dest="$1"
  local branch="$2"
  local message="$3"
  local expected_remote_sha="$4"

  if git -C "${dest}" diff --cached --quiet; then
    echo "No repository pointer changes to commit in ${dest}"
    if [[ "${NO_PUSH}" == "true" ]]; then return; fi
    if [[ "$(git -C "${dest}" rev-parse HEAD)" != "${expected_remote_sha}" ]]; then
      echo "Updating ${branch} from ${OPENPILOT_SOURCE_BRANCH}"
      GIT_LFS_SKIP_PUSH=1 git -C "${dest}" push \
        --force-with-lease="refs/heads/${branch}:${expected_remote_sha}" origin "${branch}"
    fi
    return
  fi

  echo "Committing changes in ${dest}"
  git -C "${dest}" commit -m "${message}"

  if [[ "${NO_PUSH}" == "true" ]]; then
    echo "NO_PUSH set: committed locally, NOT pushing. Inspect ${dest} then re-run without NO_PUSH."
    return
  fi

  GIT_LFS_SKIP_PUSH=1 git -C "${dest}" push \
    --force-with-lease="refs/heads/${branch}:${expected_remote_sha}" origin "${branch}"
}

main() {
  mkdir -p "${WORKSPACE_ROOT}"
  cd "${WORKSPACE_ROOT}"

  local expected_remote_sha
  expected_remote_sha="$(git ls-remote --heads "${OPENPILOT_REPO}" "refs/heads/${BRANCH}" | awk 'NR == 1 { print $1 }')"
  recreate_clone_from_source "${OPENPILOT_REPO}" "${OPENPILOT_DIR}" "${BRANCH}" \
    "${OPENPILOT_SOURCE_REPO}" "${OPENPILOT_SOURCE_BRANCH}"

  cd "${OPENPILOT_DIR}"

  enable_nav2pilot "."
  enable_psa_torqued_learning "."
  enable_extra_model_catalog "."
  enable_speed_limits "."
  set_opendbc_pointer "." "${OPENDBC_REPO}" "${BRANCH}" "${OPENDBC_SOURCE_REPO}" "${OPENDBC_SOURCE_BRANCH}"
  set_neural_network_data_pointer "."
  commit_and_push "." "${BRANCH}" "${COMMIT_MESSAGE}" "${expected_remote_sha}"

  echo
  # [source] - START
  # [pinned source] - START
  echo "Ready (source ref: ${OPENPILOT_SOURCE_BRANCH}, commit: ${RESOLVED_OPENPILOT_SOURCE_COMMIT}, builds on device - no prebuilt):"
  # [pinned source] - END
  # [source] - END
  echo "  ${WORKSPACE_ROOT}/${OPENPILOT_DIR}"
  echo "  ${WORKSPACE_ROOT}/${OPENPILOT_DIR}/opendbc_repo"
  if [[ "${USE_CUSTOM_NEURAL_NETWORK_DATA}" == "true" ]]; then
    echo "  neural_network_data (${NEURAL_NETWORK_DATA_BRANCH} at ${NEURAL_NETWORK_DATA_SHA})"
  fi
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
  main "$@"
fi
