# AGENTS.md — openpilot / Peugeot 3008 knowledge hub

Single source of truth for how Cristian's openpilot Peugeot 3008 (PSA) port is structured and operated. Any coding agent (Claude Code, Codex, etc.) working in `opendbc`, `neural-network-data`, `openpilot_scripts`, or a generated `openpilot` checkout should read this first. Detailed docs live under [docs/](docs/).

## What this is

A PSA / **Peugeot 3008** port of openpilot, maintained across a small set of forks and driven by the automation skills in this repo. Two variants (`comma` = upstream commaai, `sunny` = sunnypilot) each with a stable and a testing branch. Actual porting work happens in `opendbc`; `openpilot` is regenerated from upstream `master` and only carries submodule pointers.

## Core facts (memorize these)

- Workspace root: `/Users/cristianku/GitHub/COMMA.AI/CRISTIANKU`
- opendbc fork `cristianku/opendbc` holds the port at `opendbc/car/psa/` — platform `CAR.PSA_PEUGEOT_3008`.
- openpilot references opendbc (`opendbc_repo`) and, for sunny, `sunnypilot/neural_network_data` as **submodules = exact commit SHAs**, never vendored dirs.
- Neural-network-data always uses branch `master` (both sunny stable and testing) — no separate testing branch.
- `panda` is never touched by any workflow here.
- `master`/`main` are protected; work on the mapped feature branch.

## Branch mapping

| Variant | Upstream | openpilot / opendbc branch (stable) | (testing) |
| --- | --- | --- | --- |
| `comma` | `commaai/openpilot:master` | `peugeot-3008` | `peugeot-3008-testing` |
| `sunny` | `sunnypilot/sunnypilot:master` | `peugeot-3008-sunny` | `peugeot-3008-sunny-testing` |

## Typical workflow

1. Edit the port in `opendbc` on a testing branch → `commit-push-opendbc`.
2. Refresh the openpilot testing checkout/pointer → `setup-peugeot-3008-testing <variant>`.
3. When validated, promote testing → stable → `merge-peugeot-3008-testing` / `merge-peugeot-3008-sunny-testing` (runs PSA safety + interface tests, pushes stable with a lease, refreshes the openpilot stable pointer).

## Docs index

- [docs/repos-and-workspace.md](docs/repos-and-workspace.md) — the four repos, remotes, upstream sources, PSA file layout.
- [docs/branches-and-submodules.md](docs/branches-and-submodules.md) — branch table and submodule rules.
- [docs/skills.md](docs/skills.md) — every skill, its wrapper command, and overrides.
- [docs/neural-network-data-submodule.md](docs/neural-network-data-submodule.md) — bump openpilot submodule pointers via GitHub API without cloning.
- [docs/device-operations.md](docs/device-operations.md) — `ssh comma`, resetting self-learned params, decoding params with capnp.

## Conventions

- Run skill wrappers by absolute path; never invoke `*_common.sh` directly.
- Never force-push to opendbc via the commit skill; setup skills use `--force-with-lease` only on the mapped openpilot branch.
- Keep submodule pointers as `160000 commit`. Stage only `.gitmodules`, `opendbc_repo`, and (sunny) `sunnypilot/neural_network_data`.
