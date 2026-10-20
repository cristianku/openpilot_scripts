---
name: OP-update-nav-alpha
description: Realign cristianku/openpilot nav-alpha (comma openpilot + Nav2Pilot) to the latest commaai/openpilot master and publish it, in one command. Use when Cristian asks to update/realign comma nav-alpha, or when a setup finds it behind. Pushes when invoked; does nothing if already up to date.
---

# OP-update-nav-alpha

Rebuilds `cristianku/openpilot:nav-alpha` = latest `commaai/openpilot` master + the Nav2Pilot patch
(`OP-apply-nav-alpha/patches/openpilot.patch`), as one commit, and pushes it with `--force-with-lease`.
Anyone installs it on a comma with `installer.comma.ai/cristianku/nav-alpha`.

Run: `bash /Users/cristianku/GitHub/COMMA.AI/CRISTIANKU/openpilot_scripts/scripts/update_fork_branch.sh nav-alpha`

- Already up to date (same content as master + patch, also after a GitHub "Sync fork"): nothing is pushed.
- Exit 2 = the patch no longer applies on the new master: nothing is pushed. Resolve with `OP-apply-nav-alpha comma`
  (apply, resolve, push), which publishes through the same script.
- An `ATTENZIONE` line lists upstream commits to `navd.py`/`tiles.py`/`rpc.py`: review them with `OP-apply-nav-alpha`
  (our code copies or subclasses those files).
- `NO_PUSH=true` builds the commit without publishing.

Works in a bare cache clone (`CRISTIANKU/fork-branch-cache.git`); no working folder is touched.
The setup skills (`OP-setup-psa-torque(-testing) comma nav-alpha`) run this automatically before cloning.

Report: the published commit SHA (or "già aggiornato"), the commaai master it is based on, any ATTENZIONE lines.
