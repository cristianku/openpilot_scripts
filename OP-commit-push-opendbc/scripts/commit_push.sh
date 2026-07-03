#!/usr/bin/env bash
# Commit and push changes in Cristian's opendbc repo.
# Usage: commit_push.sh [commit message...]
# If no message is given, a timestamped default is used.

set -euo pipefail

# Repo location (override with OPENDBC_REPO).
OPENDBC_REPO="${OPENDBC_REPO:-/Users/cristianku/GitHub/COMMA.AI/CRISTIANKU/opendbc}"
# Expected remote so we never push to the wrong repo (substring match on origin URL).
EXPECTED_REMOTE="${EXPECTED_REMOTE:-cristianku/opendbc}"
# Branches we refuse to push to directly.
PROTECTED_BRANCHES="${PROTECTED_BRANCHES:-master main}"

die() { echo "ERROR: $*" >&2; exit 1; }

[ -d "$OPENDBC_REPO/.git" ] || die "not a git repo: $OPENDBC_REPO"
cd "$OPENDBC_REPO"

# Validate this is the intended opendbc remote.
origin_url="$(git remote get-url origin 2>/dev/null || true)"
[ -n "$origin_url" ] || die "no 'origin' remote configured in $OPENDBC_REPO"
case "$origin_url" in
  *"$EXPECTED_REMOTE"*) ;;
  *) die "origin is '$origin_url', expected to contain '$EXPECTED_REMOTE'. Refusing." ;;
esac

branch="$(git symbolic-ref --short -q HEAD || true)"
[ -n "$branch" ] || die "detached HEAD; checkout a branch first"

# Refuse to push to protected branches.
for p in $PROTECTED_BRANCHES; do
  if [ "$branch" = "$p" ]; then
    die "refusing to commit/push on protected branch '$branch'. Create a feature branch first."
  fi
done

# Nothing to do?
if git diff --quiet && git diff --cached --quiet && [ -z "$(git status --porcelain)" ]; then
  echo "Nothing to commit on '$branch' — working tree clean."
  # Still push in case there are local commits not yet pushed.
  if [ -n "$(git log --oneline @{u}.. 2>/dev/null || true)" ]; then
    echo "Pushing existing unpushed commits..."
    git push -u origin "$branch"
  else
    echo "Nothing to push."
  fi
  exit 0
fi

# Build commit message.
if [ "$#" -gt 0 ]; then
  msg="$*"
else
  msg="update: $(date '+%Y-%m-%d %H:%M:%S')"
fi

echo "Repo:    $OPENDBC_REPO"
echo "Branch:  $branch"
echo "Remote:  $origin_url"
echo "Message: $msg"
echo
echo "Changes to be committed:"
git status --short
echo

git add -A
git commit -m "$msg"
git push -u origin "$branch"

echo
echo "Done. Pushed '$branch' to origin."
git log --oneline -1
