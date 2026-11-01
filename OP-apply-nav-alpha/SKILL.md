---
name: OP-apply-nav-alpha
description: Work on the Nav2Pilot commit (setNavRoute with waypoints and setMapboxToken) in Cristian's local nav-alpha clones - status, apply on a fresh upstream master, resolve conflicts, change the code (commit = amend) - and publish cristianku/openpilot nav-alpha (comma) or sunny-nav-alpha (sunnypilot). Use when OP-update-nav-alpha / OP-update-sunny-nav-alpha stop on conflicts, when upstream changed navd.py/tiles.py/rpc.py, or when the Nav2Pilot code itself must change. For a plain realignment use the OP-update skills. Runs everything automatically, push included, without asking.
---

# OP-apply-nav-alpha

The Nav2Pilot changes (what the Android/iOS apps need on the device) are **one commit** on top of upstream master,
on cristianku/openpilot `nav-alpha` (comma) and `sunny-nav-alpha` (sunnypilot). Every realignment moves that commit
onto a **fresh upstream master**: no merges, no old history. Full description of the change set, file by file, and
how to resolve conflicts: `openpilot_scripts/docs/nav-alpha-nav2pilot.md` (read it before resolving anything).

**Those two branches are the only source of the Nav2Pilot code**: there is no patch file or copy anywhere else. The
setups take the diff of the branch's commit (`git diff <branch>^ <branch>`, applied with 3-way), the OP-update skills
cherry-pick it onto the new master. Every change to its logic on the device (setNavRoute, setMapboxToken, our
navd/waypoints/mapbox modules, the destination widget, a new RPC/param the apps need) is made in the local clone on
`nav-alpha`, staged and committed with `commit` (it amends the one commit), done the same way in the other fork,
checked with `sync-check`, then `push`ed for both.

## Variants

| variant | clone | upstream remote | fork branch |
|---|---|---|---|
| `sunny` | `CRISTIANKU/sunnypilot-nav-alpha` | `upstream` = sunnypilot/sunnypilot | cristianku/openpilot `sunny-nav-alpha` |
| `comma` | `CRISTIANKU/openpilot-nav-alpha` | `commaai` = commaai/openpilot | cristianku/openpilot `nav-alpha` |

Both published branches live on cristianku/openpilot: `installer.comma.ai/<user>/<branch>` always clones
`<user>/openpilot`, so that is where people can install them from. The local branch in both clones is `nav-alpha`.
Every sunny publish also puts the very same commit on cristianku/sunnypilot `nav-alpha` (`update_fork_branch.sh`
does it, also when `sunny-nav-alpha` was already up to date), so the two never drift apart. In the sunny clone
`origin` is cristianku/sunnypilot: its `origin/nav-alpha` is that copy.

Overrides: `NAV_REPO` (clone folder), `NAV_BRANCH` (local branch, default `nav-alpha`).

## Workflow

Script by absolute path: `scripts/apply_nav_alpha.sh <sunny|comma> <command>`. With no variant given, do both.

**Everything is automatic: never ask Cristian for confirmation at any step, push included.** Stop only if the
checks fail or a conflict cannot be resolved with the doc, and then report why.

1. `status` — fetches master and the published branch, lists upstream commits since the commit's base that touch
   the Nav2Pilot files or the watched upstream files (`navd.py`, `tiles.py`, `rpc.py`), and says whether the
   commit applies cleanly on the new master. Read-only.
2. If upstream changed `openpilot/selfdrive/navigation/navd.py`: review it against our subclass
   (`calculate_route` is a copy of upstream's with waypoints added; see the doc). A change there can apply cleanly
   and still be lost in our override.
3. `apply` — refuses a dirty tree, saves the old branch as local `nav-alpha-prev`, recreates `nav-alpha` from
   master, `git apply --3way` the published Nav2Pilot commit, runs the checks and makes the local commit (same
   message). Skip it when `status` says master has not moved and the fork branch is not behind (nothing to do).
   - exit 2 = conflicts: resolve them using the doc (keep upstream's new code, re-add only our lines),
     `git add` the files, then `scripts/apply_nav_alpha.sh <variant> commit` (re-runs the checks first).
4. To change our code (also after a navd review): edit, `git add`, `commit` — on a branch that already has the
   Nav2Pilot commit it amends it, so the branch stays master + one commit. Make the same change in the other fork,
   and `sync-check` so sunny and comma Nav2Pilot packages stay identical (only the sunnylink lines may differ).
5. `push` right away, without asking: checks, refuses a branch with more than one commit on master, pushes the
   local branch to cristianku/openpilot `nav-alpha` / `sunny-nav-alpha` (`--force-with-lease`), then runs
   `openpilot_scripts/scripts/update_fork_branch.sh` (the OP-update script), which moves the commit onto the latest
   master if it moved meanwhile and, for sunny, puts the same commit on cristianku/sunnypilot `nav-alpha`. If it
   moved the commit, align the local clone: `git fetch origin nav-alpha && git reset --hard origin/nav-alpha`
   (comma; sunny the same, `origin` = cristianku/sunnypilot, whose `nav-alpha` is the copy of `sunny-nav-alpha`).
   `NO_PUSH=true` stops before the push. Never use VS Code "Sync" / GitHub "Sync fork" on these branches.
6. Report to Cristian at the end: master SHA, upstream changes reviewed, conflicts and how they were solved, check
   results, what was pushed.

## Checks (`check`, also run by `commit` and `push`)

- every Nav2Pilot file exists, no conflict markers, Python syntax OK
- `params_keys.h`: no duplicate keys, `MapboxToken` present
- `process_config.py` runs navd from our package; `athenad.py` imports our `athena` module
- submodule gitlinks identical to upstream (Nav2Pilot never moves a submodule)
- ruff on the Nav2Pilot Python files (warning only: local ruff version may differ from the repo's)

Unit tests are not run here (they need the openpilot build env): use the Docker `spnav` container if asked.

## Safety

- Pushes automatically once the checks pass; never touches upstream remotes; never deploys to the device.
- The old branch stays as local `nav-alpha-prev` until the next `apply`.
- `nav-alpha` / `sunny-nav-alpha` are the default sources of `OP-setup-psa-torque(-testing)`, never a PSA target.
