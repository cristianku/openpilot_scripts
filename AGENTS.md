# AGENTS.md — openpilot / Peugeot 3008 knowledge hub

Single source of truth for how Cristian's openpilot Peugeot 3008 (PSA) port is structured and operated. Any coding agent (Claude Code, Codex, etc.) working in `opendbc`, `neural-network-data`, `openpilot_scripts`, or a generated `openpilot` checkout should read this first.

Two layers of documentation live here:
- **Operational runbook** — how the fork/branch/submodule/device workflow works: [docs/](docs/).
- **Knowledge wiki** — how openpilot & opendbc actually work, to understand and develop them over time: [wiki/](wiki/) (start at [wiki/index.md](wiki/index.md)). This section defines how that wiki is maintained.

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

---

# Knowledge wiki schema

This applies the LLM-wiki pattern in [llm-wiki.md](llm-wiki.md) to understanding/developing openpilot. The **raw sources are the code repos themselves** (`opendbc`, `openpilot_sunny`, later `openpilot`) — read them, never treat them as wiki content. The wiki is `wiki/`; this section is its schema.

## Layout (`wiki/`)

- `index.md` — catalog of every page (read first when answering). `log.md` — append-only chronological record.
- `overview.md` — architecture entry point.
- `sources/` — one page per raw source repo (structural map: what each dir does + where the important code is).
- `concepts/` — cross-cutting ideas (the interface contract, the runtime pipeline, safety, messaging, tuning…).
- `entities/` — concrete things (a specific car port, daemon, message, tuning experiment).

## Page format

Start every page with YAML frontmatter: `title`, `type` (source|concept|entity|overview|index|log), `repos`, `updated` (absolute date), and `sources` (repo-relative paths the page is grounded on) when applicable. Link between pages with **relative markdown links** so they work in VS Code and GitHub. Cite code as repo-relative paths, optionally `file.py:line`.

## Grounding rule (important)

Every claim about how the code works must be grounded in the actual repos, not memory. Read the files, cite them in `sources`. Mark anything unverified as *draft* / *open question* rather than asserting it. Code drifts — prefer directory/contract-level facts over line numbers, and re-verify before relying on a page.

## Workflows

**Ingest** (a new source, subsystem, or finding): read the relevant code → discuss key takeaways → write/update the page(s) in the right folder → add/refresh cross-references on related pages → update `index.md` → append a `log.md` entry (`## [YYYY-MM-DD] ingest | <title>`). One finding may touch several pages.

**Query** (answering a question): read `index.md` → open the relevant pages → verify against the code if it matters → answer with citations. If the answer is durable knowledge, file it back as a new/updated page (and log it).

**Lint** (periodic health check): find contradictions, stale claims, orphan pages, missing cross-references, concepts mentioned but lacking a page, and drafts to verify against current code. Report + fix, then log it.
