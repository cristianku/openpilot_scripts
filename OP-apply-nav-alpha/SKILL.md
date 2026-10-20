---
name: OP-apply-nav-alpha
description: Rebuild Cristian's nav-alpha branches (cristianku/sunnypilot and cristianku/openpilot) from the latest upstream master and reapply ONLY the Nav2Pilot changes - setNavRoute with waypoints and setMapboxToken - stored as patches in openpilot_scripts. Use when sunnypilot/master or commaai/master moved and nav-alpha must be realigned for the Nav2Pilot apps, or to check whether it still applies. Pushes only with Cristian's explicit ok.
---

# OP-apply-nav-alpha

The Nav2Pilot changes (what the Android/iOS apps need on the device) are kept as one patch per fork in
`patches/`. Every realignment starts from a **fresh upstream master** and reapplies that patch as **one commit**:
no merges, no old history, nothing else from the old branch. Full description of the change set, file by file,
and how to resolve conflicts: `openpilot_scripts/docs/nav-alpha-nav2pilot.md` (read it before resolving anything).

## Variants

| variant | clone | upstream remote | fork branch | patch |
|---|---|---|---|---|
| `sunny` | `CRISTIANKU/sunnypilot-nav-alpha` | `upstream` = sunnypilot/sunnypilot | `origin` = cristianku/sunnypilot `nav-alpha` | `patches/sunnypilot.patch` |
| `comma` | `CRISTIANKU/openpilot-nav-alpha` | `commaai` = commaai/openpilot | `origin` = cristianku/openpilot `nav-alpha` | `patches/openpilot.patch` |

Overrides: `NAV_REPO` (clone folder), `NAV_BRANCH` (default `nav-alpha`).

## Workflow

Script by absolute path: `scripts/apply_nav_alpha.sh <sunny|comma> <command>`. With no variant given, do both.

1. `status` — fetches master, lists upstream commits since the patch base that touch the patched files or the
   watched upstream files (`navd.py`, `tiles.py`, `rpc.py`), and says whether the patch applies cleanly. Read-only.
2. If upstream changed `openpilot/selfdrive/navigation/navd.py`: review it against our subclass
   (`calculate_route` is a copy of upstream's with waypoints added; see the doc). A change there can apply cleanly
   and still be lost in our override.
3. `apply` — refuses a dirty tree, saves the old branch as local `nav-alpha-prev`, recreates `nav-alpha` from
   master, `git apply --3way` the patch, runs the checks and makes the local commit. **Does not push.**
   - exit 2 = conflicts: resolve them using the doc (keep upstream's new code, re-add only our lines),
     `git add` the files, then `scripts/apply_nav_alpha.sh <variant> commit` (re-runs the checks first).
4. If the resolution or a navd review changed our code: `save-patch` to store the new patch (+ base), and
   `sync-check` so sunny and comma Nav2Pilot packages stay identical (only the sunnylink lines may differ).
   Mirror the same code change in the other fork's patch.
5. Report to Cristian: master SHA, upstream changes reviewed, conflicts and how they were solved, check results.
6. `push` (`--force-with-lease` on `origin nav-alpha`) **only after Cristian's explicit ok**.

## Checks (`check`, also run by `commit` and `push`)

- every patched file exists, no conflict markers, Python syntax OK
- `params_keys.h`: no duplicate keys, `MapboxToken` present
- `process_config.py` runs navd from our package; `athenad.py` imports our `athena` module
- submodule gitlinks identical to upstream master (the patch never moves a submodule)
- ruff on the patched Python files (warning only: local ruff version may differ from the repo's)

Unit tests are not run here (they need the openpilot build env): use the Docker `spnav` container if asked.

## Safety

- Never pushes without Cristian's ok; never touches upstream remotes; never deploys to the device.
- The old branch stays as local `nav-alpha-prev` until the next `apply`.
- `nav-alpha` is a source branch for `OP-setup-psa-torque(-testing) <variant> nav-alpha`, never a PSA target.
