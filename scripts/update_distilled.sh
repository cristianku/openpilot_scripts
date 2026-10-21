#!/usr/bin/env bash
# [distill sync] - START
# Synchronize the canonical SunnyPilot Distill branch with official upstream,
# then mirror the exact commit into cristianku/openpilot for comma installation.
# Never merge commaai/openpilot into the Sunnypilot source.
set -euo pipefail

SOURCE_REPO="${DISTILLED_SOURCE_REPO:-https://github.com/cristianku/sunnypilot.git}"
UPSTREAM_REPO="${DISTILLED_UPSTREAM_REPO:-https://github.com/sunnypilot/sunnypilot.git}"
TARGET_REPO="${TARGET_REPO:-https://github.com/cristianku/openpilot.git}"
BRANCH=distilled
NO_PUSH="${NO_PUSH:-false}"

work_dir="$(mktemp -d)"
trap 'rm -rf "${work_dir}"' EXIT
checkout="${work_dir}/distilled"

echo "== canonical source: ${SOURCE_REPO}:${BRANCH}"
echo "== official upstream: ${UPSTREAM_REPO}:master"
echo "== installable mirror: ${TARGET_REPO}:${BRANCH}"

source_before="$(git ls-remote --heads "${SOURCE_REPO}" "refs/heads/${BRANCH}" | awk 'NR == 1 {print $1}')"
if [[ ! "${source_before}" =~ ^[0-9a-f]{40}$ ]]; then
  echo "ERROR: canonical branch ${SOURCE_REPO}:${BRANCH} is missing. No mirror was changed." >&2
  exit 1
fi

# A temporary Git checkout implements GitHub's Sync fork semantics: merge upstream
# into the long-lived feature branch, preserving its own commits and ancestry.
GIT_LFS_SKIP_SMUDGE=1 git clone -q --filter=blob:none --no-tags --single-branch --branch "${BRANCH}" "${SOURCE_REPO}" "${checkout}"
git -C "${checkout}" remote add upstream "${UPSTREAM_REPO}"
git -C "${checkout}" fetch -q --filter=blob:none --no-tags upstream master

if ! git -C "${checkout}" -c user.name="cristianku automation" -c user.email="cristianku@users.noreply.github.com" \
  merge --no-edit upstream/master; then
  echo "ERROR: conflicts merging Sunnypilot master into canonical ${BRANCH}." >&2
  echo "Files to resolve:" >&2
  git -C "${checkout}" diff --name-only --diff-filter=U >&2 || true
  echo "No branch was published. Resolve the conflict with an AI/code agent or manually." >&2
  echo "Conflict checkout preserved at: ${checkout}" >&2
  echo "After resolving and testing, commit and push the source branch, then rerun OP-update-distilled to mirror it." >&2
  trap - EXIT
  exit 2
fi

git -C "${checkout}" merge-base --is-ancestor upstream/master HEAD || {
  echo "ERROR: upstream master is not an ancestor of candidate Distill branch" >&2; exit 2;
}
git -C "${checkout}" diff --check upstream/master...HEAD
for file in \
  openpilot/sunnypilot/models/extra_catalog.py \
  openpilot/sunnypilot/models/fetcher.py \
  openpilot/sunnypilot/models/tests/test_manager_download.py; do
  if [[ ! -f "${checkout}/${file}" ]]; then
    echo "ERROR: required Distill file missing: ${file}" >&2
    exit 2
  fi
done
python3 -c 'import ast,sys; [ast.parse(open(f, encoding="utf-8").read(), filename=f) for f in sys.argv[1:]]' \
  "${checkout}/openpilot/sunnypilot/models/extra_catalog.py" \
  "${checkout}/openpilot/sunnypilot/models/fetcher.py" \
  "${checkout}/openpilot/sunnypilot/models/tests/test_manager_download.py"

candidate="$(git -C "${checkout}" rev-parse HEAD)"
echo "== checked canonical candidate: ${candidate}"
if [[ "${NO_PUSH}" == "true" ]]; then
  echo "NO_PUSH=true: dry-run OK, neither repository modified."
  exit 0
fi

# First publish the canonical branch: non-forced push refuses concurrent or divergent changes.
if [[ "${candidate}" != "${source_before}" ]]; then
  echo "== publish merged canonical source"
  GIT_LFS_SKIP_PUSH=1 git -C "${checkout}" push origin "HEAD:refs/heads/${BRANCH}" || {
    echo "ERROR: canonical push rejected; the installable mirror was not touched." >&2; exit 1;
  }
else
  echo "== canonical source already synchronized"
fi

published_source="$(git ls-remote --heads "${SOURCE_REPO}" "refs/heads/${BRANCH}" | awk 'NR == 1 {print $1}')"
if [[ "${published_source}" != "${candidate}" ]]; then
  echo "ERROR: canonical branch moved concurrently. Mirror NOT updated." >&2
  exit 1
fi

mirror_before="$(git ls-remote --heads "${TARGET_REPO}" "refs/heads/${BRANCH}" | awk 'NR == 1 {print $1}')"
if [[ "${mirror_before}" == "${published_source}" ]]; then
  echo "== mirror already at canonical commit"
else
  echo "== publish installable mirror: ${TARGET_REPO}:${BRANCH}"
  # Only the generated mirror can be rewritten, protected by its observed SHA.
  if ! GIT_LFS_SKIP_PUSH=1 git -C "${checkout}" push \
    --force-with-lease="refs/heads/${BRANCH}:${mirror_before}" \
    "${TARGET_REPO}" "HEAD:refs/heads/${BRANCH}"; then
    echo "ERROR: canonical branch updated, but installable mirror failed; retry the skill." >&2
    exit 1
  fi
fi

published_mirror="$(git ls-remote --heads "${TARGET_REPO}" "refs/heads/${BRANCH}" | awk 'NR == 1 {print $1}')"
if [[ "${published_mirror}" != "${published_source}" ]]; then
  echo "ERROR: mirror SHA differs from canonical SHA. Check remote updates." >&2
  exit 1
fi

echo "== synchronized source and mirror: ${published_source}"
echo "Installable: https://installer.comma.ai/cristianku/${BRANCH}"
# [distill sync] - END
