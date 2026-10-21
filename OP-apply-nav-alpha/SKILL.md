---
name: OP-apply-nav-alpha
description: Work on the Nav2Pilot patches (setNavRoute with waypoints and setMapboxToken) in Cristian's local nav-alpha clones - status, apply on a fresh upstream master, resolve conflicts, save the patch - and publish cristianku/openpilot nav-alpha (comma) or sunny-nav-alpha (sunnypilot). Use when OP-update-nav-alpha / OP-update-sunny-nav-alpha stop on conflicts, when upstream changed navd.py/tiles.py/rpc.py, or when the Nav2Pilot code itself must change. For a plain realignment use the OP-update skills. Runs everything automatically, push included, without asking.
---

# OP-apply-nav-alpha

The Nav2Pilot changes (what the Android/iOS apps need on the device) are kept as one patch per fork in
`patches/`. Every realignment starts from a **fresh upstream master** and reapplies that patch as **one commit**:
no merges, no old history, nothing else from the old branch. Full description of the change set, file by file,
and how to resolve conflicts: `openpilot_scripts/docs/nav-alpha-nav2pilot.md` (read it before resolving anything).

## Variants

| variant | clone | upstream remote | fork branch | patch |
|---|---|---|---|---|
| `sunny` | `CRISTIANKU/sunnypilot-nav-alpha` | `upstream` = sunnypilot/sunnypilot | cristianku/openpilot `sunny-nav-alpha` | `patches/sunnypilot.patch` |
| `comma` | `CRISTIANKU/openpilot-nav-alpha` | `commaai` = commaai/openpilot | cristianku/openpilot `nav-alpha` | `patches/openpilot.patch` |

Both published branches live on cristianku/openpilot: `installer.comma.ai/<user>/<branch>` always clones
`<user>/openpilot`, so that is where people can install them from. The local branch in both clones is `nav-alpha`.

Overrides: `NAV_REPO` (clone folder), `NAV_BRANCH` (local branch, default `nav-alpha`).

## Workflow

Script by absolute path: `scripts/apply_nav_alpha.sh <sunny|comma> <command>`. With no variant given, do both.

**Everything is automatic: never ask Cristian for confirmation at any step, push included.** Stop only if the
checks fail or a conflict cannot be resolved with the doc, and then report why.

1. `status` — fetches master, lists upstream commits since the patch base that touch the patched files or the
   watched upstream files (`navd.py`, `tiles.py`, `rpc.py`), and says whether the patch applies cleanly. Read-only.
2. If upstream changed `openpilot/selfdrive/navigation/navd.py`: review it against our subclass
   (`calculate_route` is a copy of upstream's with waypoints added; see the doc). A change there can apply cleanly
   and still be lost in our override.
3. `apply` — refuses a dirty tree, saves the old branch as local `nav-alpha-prev`, recreates `nav-alpha` from
   master, `git apply --3way` the patch, runs the checks and makes the local commit. Skip it when `status` says
   master has not moved and the fork branch is not behind (nothing to do).
   - exit 2 = conflicts: resolve them using the doc (keep upstream's new code, re-add only our lines),
     `git add` the files, then `scripts/apply_nav_alpha.sh <variant> commit` (re-runs the checks first).
4. If the resolution or a navd review changed our code: `save-patch` to store the new patch (+ base), and
   `sync-check` so sunny and comma Nav2Pilot packages stay identical (only the sunnylink lines may differ).
   Mirror the same code change in the other fork's patch.
5. `push` right away, without asking: runs `save-patch`, then publishes upstream master + the saved patch with
   `openpilot_scripts/scripts/update_fork_branch.sh` (the same script the OP-update skills and the setups use).
   That script makes its own commit, so afterwards align the local clone: `git fetch origin <fork branch>` and
   `git reset --hard origin/<fork branch>` on `nav-alpha` (otherwise VS Code shows pending sync changes).
   Never use VS Code "Sync" / GitHub "Sync fork" on these branches.
6. Report to Cristian at the end: master SHA, upstream changes reviewed, conflicts and how they were solved, check
   results, what was pushed.

## Checks (`check`, also run by `commit` and `push`)

- every patched file exists, no conflict markers, Python syntax OK
- `params_keys.h`: no duplicate keys, `MapboxToken` present
- `process_config.py` runs navd from our package; `athenad.py` imports our `athena` module
- submodule gitlinks identical to upstream master (the patch never moves a submodule)
- ruff on the patched Python files (warning only: local ruff version may differ from the repo's)

Unit tests are not run here (they need the openpilot build env): use the Docker `spnav` container if asked.

## Safety

- Pushes automatically once the checks pass; never touches upstream remotes; never deploys to the device.
- The old branch stays as local `nav-alpha-prev` until the next `apply`.
- `nav-alpha` / `sunny-nav-alpha` are the default sources of `OP-setup-psa-torque(-testing)`, never a PSA target.
