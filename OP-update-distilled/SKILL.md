---
name: OP-update-distilled
description: Sync the canonical cristianku/sunnypilot:distilled branch with sunnypilot/sunnypilot:master, then mirror the exact commit to cristianku/openpilot:distilled for comma installation. Stops on conflicts or validation errors.
---

# OP-update-distilled

<!-- [distill sync] - START -->
## Canonical source and installable mirror

**Source of truth:** `cristianku/sunnypilot:distilled` (SunnyPilot + the custom openpilot.distill model catalog).
**Official upstream:** `sunnypilot/sunnypilot:master`.
**Installable mirror:** `cristianku/openpilot:distilled` (contains **SunnyPilot**, despite the target repository name).
**Installer (only when mirror exists and is verified):** `https://installer.comma.ai/cristianku/distilled`.

Do **not** use a locally duplicated `sunnypilot-extra-model-catalog.patch` as the source of Distill changes.

## Two-stage update

Run:

```bash
bash /Users/cristianku/GitHub/COMMA.AI/CRISTIANKU/openpilot_scripts/scripts/update_fork_branch.sh distilled
```

The command delegates to `scripts/update_distilled.sh`.

1. Fetch the **existing** canonical `cristianku/sunnypilot:distilled` and the latest official SunnyPilot `master`. Perform a Git merge equivalent to GitHub's "Sync fork", preserving custom Distill commits. The upstream used is explicitly `sunnypilot/sunnypilot`, **never** `commaai/openpilot`.
2. After conflict checks and Python syntax validation, push canonical `distilled` with a non-forced push. Copy the **identical commit SHA** to `cristianku/openpilot:distilled`, using `--force-with-lease` on this generated mirror alone.

If the master is already integrated, stage 1 is a no-op; stage 2 repairs an absent/outdated mirror.

## Conflicts, dry run and safety

- `NO_PUSH=true bash .../scripts/update_fork_branch.sh distilled` previews the source merge and validations **without writing either remote**.
- Merge conflict = exit 2 with the unmerged checkout retained under a printed temporary path; no branch is published. If working as an LLM coding agent, inspect the conflict, attempt a **reasoned** resolution, run the relevant tests, ask for approval if the intended behavior is ambiguous, then commit/push the canonical source and rerun the skill. Never choose ours/theirs indiscriminately.
- Missing source branch or source files, failed syntax checks or a concurrent remote change = stop without updating the mirror.
- If the canonical push succeeds but mirroring fails, report the partial state and rerun after resolving the issue.
- No changes to the comma device are made by this skill. The installer link must be verified before publishing it in the community.

The SunnyPilot PSA setup skills fetch the *catalog diff* from the canonical source branch and apply it to their PSA/Nav2Pilot build. They do not consume the generated OpenPilot mirror and must not rely on a second patch copy.

For public posts, follow [community publication rules](../docs/community-publication.md): include **both** source and installation URLs, with accurate release status.

Report both remote commit SHAs, the upstream base and any conflicts.
<!-- [distill sync] - END -->
