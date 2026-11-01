---
name: OP-update-sunny-nav-alpha
description: Realign cristianku/openpilot sunny-nav-alpha (sunnypilot + Nav2Pilot) to the latest sunnypilot/sunnypilot master and publish it, in one command. Use when Cristian asks to update/realign the sunnypilot nav-alpha, or when a setup finds it behind. Pushes when invoked; does nothing if already up to date.
---

# OP-update-sunny-nav-alpha

Moves the Nav2Pilot commit of `cristianku/openpilot:sunny-nav-alpha` (the branch is `sunnypilot/sunnypilot` master + that one
commit, the only source of the Nav2Pilot code) onto the latest master, like a cherry-pick (same message and author),
and pushes it with `--force-with-lease`.
It lives on cristianku/openpilot (not cristianku/sunnypilot) because `installer.comma.ai/<user>/<branch>` always
clones `<user>/openpilot`: anyone installs it with `installer.comma.ai/cristianku/sunny-nav-alpha`.

Run: `bash /Users/cristianku/GitHub/COMMA.AI/CRISTIANKU/openpilot_scripts/scripts/update_fork_branch.sh sunny-nav-alpha`

- Already up to date (the commit already sits on the current master): nothing is pushed.
- Exit 2 = the commit no longer applies on the new master: nothing is pushed. Resolve with `OP-apply-nav-alpha sunny`
  (apply, resolve, push), which publishes through the same script.
- An `ATTENZIONE` line lists upstream commits to `navd.py`/`tiles.py`/`rpc.py`: review them with `OP-apply-nav-alpha`.
- Stops without pushing if the branch is a merge or more than one commit on master: redo it with `OP-apply-nav-alpha`.
- `NO_PUSH=true` builds the commit without publishing.
- Never use GitHub "Sync fork" on this branch: cristianku/openpilot is a fork of commaai, so it would merge comma
  master into sunnypilot.

Works in a bare cache clone (`CRISTIANKU/fork-branch-cache.git`); no working folder is touched.
`OP-setup-psa-torque sunny nav-alpha` runs this automatically before cloning; `OP-setup-psa-torque-testing` does not (it only reads the commit: run this first, see docs/external-branches.md).

Report: the published commit SHA (or "già aggiornato"), the sunnypilot master it is based on, any ATTENZIONE lines.
