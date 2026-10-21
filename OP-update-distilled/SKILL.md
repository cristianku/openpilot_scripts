---
name: OP-update-distilled
description: Realign cristianku/openpilot distilled (sunnypilot master + the openpilot.distill models in the Models menu) to the latest sunnypilot/sunnypilot master and publish it, in one command. Use when Cristian asks to create/update the distilled branch. Pushes when invoked; does nothing if already up to date.
---

# OP-update-distilled

Rebuilds `cristianku/openpilot:distilled` = latest `sunnypilot/sunnypilot` master + the extra model catalog patch
(`OP-setup-psa-torque-testing/patches/sunnypilot-extra-model-catalog.patch`, the same one the Sunny setups apply),
as one commit, and pushes it with `--force-with-lease`. On a comma installed from it, the Models menu (and the
sunnylink model list) also shows the openpilot.distill models published on Hugging Face
(`cristianku/openpilot-distill-models`, folder "Distill cristianku"). Install: `installer.comma.ai/cristianku/distilled`.

Run: `bash /Users/cristianku/GitHub/COMMA.AI/CRISTIANKU/openpilot_scripts/scripts/update_fork_branch.sh distilled`

- Already up to date: nothing is pushed.
- Exit 2 = sunnypilot changed `openpilot/sunnypilot/models` and the patch no longer applies: nothing is pushed;
  update the patch (both setup skills carry a copy).
- `NO_PUSH=true` builds the commit without publishing.
- comma openpilot has no Models menu: there is no comma version of this branch.
- Never use GitHub "Sync fork" on this branch (it would merge comma master into sunnypilot).

<!-- [community publication] - START -->
## Community publication note

When reporting or announcing an **actually published** `distilled` version, identify both the verified maintained **source** branch in `cristianku/sunnypilot` and the **installation** branch in `cristianku/openpilot`, plus the installer URL *only when tested and live*. The desired source-first, upstream-merge-then-mirror workflow is documented as a **proposal** in [../docs/community-publication.md](../docs/community-publication.md); the current script still uses the extra-catalog patch. Do not claim that the desired two-stage workflow is already implemented or publish an installer URL for a missing branch.
<!-- [community publication] - END -->

Report: the published commit SHA (or "già aggiornato") and the sunnypilot master it is based on.
