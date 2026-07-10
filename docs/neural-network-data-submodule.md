# Updating openpilot submodule pointers without cloning

openpilot/sunnypilot is large. You can bump its submodule pointers purely through the GitHub API — no full clone required — because a submodule is just a tree entry (`mode 160000`, `type commit`, a SHA, and a path).

## When to use

To point `cristianku/openpilot:<branch>` at newer commits of its submodules, e.g. for `psa-torque-sunny-testing`:
- `sunnypilot/neural_network_data` → HEAD of `cristianku/neural-network-data:master`
- `opendbc_repo` → HEAD of `cristianku/opendbc:psa-torque-sunny-testing`

## Procedure (via GitHub API)

1. Get the current commit SHA of the openpilot branch.
2. Get HEAD SHA of each submodule branch.
3. Create a new tree based on the openpilot branch commit, updating each submodule entry (`path`, `mode=160000`, `type=commit`, `sha=<submodule HEAD>`).
4. Create a new commit with that tree.
5. Move the branch ref with `update_ref` **without force**.

Notes:
- Do not use `force=true` unless explicitly needed.
- Do not modify `.gitmodules` unless the submodule URL itself changes.
- Only create the openpilot commit if at least one tree entry actually changed.

## Verify (local checkout)

```bash
git fetch origin && git checkout psa-torque-sunny-testing && git pull origin psa-torque-sunny-testing
git submodule status sunnypilot/neural_network_data
git submodule status opendbc_repo
```

The reusable ChatGPT prompt (Italian) and full step list live in
[../chatgpt-skills/psa-torque-sunny-testing-update-neural-network-data-submodule.md](../chatgpt-skills/psa-torque-sunny-testing-update-neural-network-data-submodule.md).

The `setup-psa-torque*` skills perform the equivalent pointer update locally with `--force-with-lease`; use this API method when you only want to bump pointers without recreating the local openpilot checkout.
