#!/usr/bin/env bash
# [comma update] - START
set -euo pipefail

usage() {
  echo "Usage: $0 [--dry-run] [--no-reboot] [ssh-host]" >&2
}

dry_run=0
do_reboot=1
ssh_host="comma"

while (($# > 0)); do
  case "$1" in
    --dry-run)
      dry_run=1
      shift
      ;;
    --no-reboot)
      do_reboot=0
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    -*)
      usage
      exit 2
      ;;
    *)
      ssh_host="$1"
      shift
      if (($# > 0)); then
        usage
        exit 2
      fi
      ;;
  esac
done

if [[ ! "$ssh_host" =~ ^[A-Za-z0-9._@-]+$ ]]; then
  echo "Invalid SSH host: $ssh_host" >&2
  exit 2
fi

ssh_options=(-o BatchMode=yes -o ConnectTimeout=10)

ssh "${ssh_options[@]}" "$ssh_host" bash -s -- "$dry_run" <<'REMOTE_SCRIPT'
set -euo pipefail

dry_run="$1"
repo="/data/openpilot"

if [[ ! -d "$repo/.git" ]]; then
  echo "ERROR: $repo is not a Git checkout" >&2
  exit 10
fi

cd "$repo"

branch="$(git symbolic-ref --quiet --short HEAD)" || {
  echo "ERROR: detached HEAD; refusing automatic update" >&2
  exit 11
}

upstream="$(git rev-parse --abbrev-ref '@{upstream}' 2>/dev/null)" || {
  echo "ERROR: branch $branch has no upstream" >&2
  exit 12
}

if [[ -n "$(git status --porcelain --untracked-files=normal)" ]]; then
  echo "ERROR: working tree is dirty; refusing automatic update" >&2
  git status --short --branch >&2
  exit 13
fi

before="$(git rev-parse HEAD)"
echo "Device branch: $branch"
echo "Upstream:      $upstream"
echo "Current HEAD:  $before"

if [[ "$dry_run" == "1" ]]; then
  tracked="$(git rev-parse "$upstream" 2>/dev/null || true)"
  echo "Tracked HEAD:  ${tracked:-unavailable (run update to fetch)}"
  echo "DRY RUN: no files changed and no reboot requested"
  exit 0
fi

remote="${upstream%%/*}"
git fetch --prune "$remote"
target="$(git rev-parse "$upstream")"
echo "Remote HEAD:   $target"

if [[ "$before" != "$target" ]] && ! git merge-base --is-ancestor "$before" "$target"; then
  echo "ERROR: local branch is not a fast-forward of $upstream" >&2
  exit 14
fi

git merge --ff-only "$upstream"
git submodule sync --recursive
git submodule update --init --recursive

if [[ -n "$(git status --porcelain --untracked-files=normal)" ]]; then
  echo "ERROR: checkout is dirty after update" >&2
  git status --short --branch >&2
  exit 15
fi

after="$(git rev-parse HEAD)"
echo "Installed HEAD: $after"
echo "OP_UPDATE_COMMA_OK"
REMOTE_SCRIPT

if ((dry_run == 1 || do_reboot == 0)); then
  exit 0
fi

echo "Update completed; rebooting $ssh_host"
if ssh "${ssh_options[@]}" "$ssh_host" "sudo reboot"; then
  reboot_status=0
else
  reboot_status=$?
fi

# SSH commonly exits with 255 because the remote host closes the connection
# while rebooting. Treat that as an expected reboot outcome.
if ((reboot_status != 0 && reboot_status != 255)); then
  echo "ERROR: reboot command failed with SSH status $reboot_status" >&2
  exit "$reboot_status"
fi

echo "Reboot command sent to $ssh_host"
# [comma update] - END
