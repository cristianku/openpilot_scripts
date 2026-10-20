---
name: OP-update-sunny-nav-alpha
description: Realign cristianku/openpilot sunny-nav-alpha (sunnypilot + Nav2Pilot) to the latest sunnypilot/sunnypilot master and publish it, in one command. Use when Cristian asks to update/realign the sunnypilot nav-alpha, or when a setup finds it behind. Pushes when invoked; does nothing if already up to date.
---

# OP-update-sunny-nav-alpha

Rebuilds `cristianku/openpilot:sunny-nav-alpha` = latest `sunnypilot/sunnypilot` master + the Nav2Pilot patch
(`OP-apply-nav-alpha/patches/sunnypilot.patch`), as one commit, and pushes it with `--force-with-lease`.
It lives on cristianku/openpilot (not cristianku/sunnypilot) because `installer.comma.ai/<user>/<branch>` always
clones `<user>/openpilot`: anyone installs it with `installer.comma.ai/cristianku/sunny-nav-alpha`.

Run: `bash /Users/cristianku/GitHub/COMMA.AI/CRISTIANKU/openpilot_scripts/scripts/update_fork_branch.sh sunny-nav-alpha`

- Already up to date (same content as master + patch): nothing is pushed.
- Exit 2 = the patch no longer applies on the new master: nothing is pushed. Resolve with `OP-apply-nav-alpha sunny`
  (apply, resolve, push), which publishes through the same script.
- An `ATTENZIONE` line lists upstream commits to `navd.py`/`tiles.py`/`rpc.py`: review them with `OP-apply-nav-alpha`.
- `NO_PUSH=true` builds the commit without publishing.
- Never use GitHub "Sync fork" on this branch: cristianku/openpilot is a fork of commaai, so it would merge comma
  master into sunnypilot.

Works in a bare cache clone (`CRISTIANKU/fork-branch-cache.git`); no working folder is touched.
The setup skills (`OP-setup-psa-torque(-testing) sunny nav-alpha`) run this automatically before cloning.

Report: the published commit SHA (or "già aggiornato"), the sunnypilot master it is based on, any ATTENZIONE lines.
