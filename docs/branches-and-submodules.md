# Branches and submodules

## Branch mapping

| Workflow | Variant | Upstream source | openpilot branch | opendbc branch |
| --- | --- | --- | --- | --- |
| Stable | `comma` | `commaai/openpilot:master` | `peugeot-3008` | `peugeot-3008` |
| Stable | `sunny` | `sunnypilot/sunnypilot:master` | `peugeot-3008-sunny` | `peugeot-3008-sunny` |
| Testing | `comma` | `commaai/openpilot:master` | `peugeot-3008-testing` | `peugeot-3008-testing` |
| Testing | `sunny` | `sunnypilot/sunnypilot:master` | `peugeot-3008-sunny-testing` | `peugeot-3008-sunny-testing` |

Testing branches are where changes are validated. Once ready, the merge skills promote testing → stable in opendbc, then refresh the matching openpilot pointer. `master`/`main` are protected — the commit/push skill refuses to act on them.

## Submodule relationships

openpilot references the other repos as **git submodules**, i.e. exact commit SHAs stored in the tree as `160000 commit`, not dynamic branch pointers.

- `opendbc_repo` → a specific commit of `cristianku/opendbc` on the matching branch (both variants).
- `sunnypilot/neural_network_data` → a specific commit of `cristianku/neural-network-data:master` (**sunny variant only**).

Rules:
- Always keep these as submodule pointers, never vendored directories.
- Neural-network-data always uses branch `master` for both Sunny stable and Sunny testing — no separate testing branch.
- The setup scripts stage only `.gitmodules`, `opendbc_repo`, and (sunny) `sunnypilot/neural_network_data`.
- Updating a submodule pointer changes the openpilot repo, not the submodule repo.

See [neural-network-data-submodule.md](neural-network-data-submodule.md) for the exact procedure to bump submodule pointers via the GitHub API without cloning the full openpilot repo.
