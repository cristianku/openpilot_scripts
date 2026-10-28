# External branches of psa-torque-sunny-testing

`OP-setup-psa-torque-testing sunny` rebuilds `cristianku/openpilot:psa-torque-sunny-testing` (the branch the comma
always runs) from the upstream base and injects these. Read this list **before every setup** and bring each source
up to date first.

The setup takes only what each source adds (a pointer, or its changes since the upstream master), not the whole
branch, so a source left behind still builds. Keeping them on the current master matters because each is also
installed or used on its own (Distill, Nav2Pilot), and a conflict with a new master shows up when the source is
updated, in its own repository, not in the middle of a setup.

| What | Source | How it is injected | Upstream | Update with |
|---|---|---|---|---|
| The base | `sunnypilot/sunnypilot:master` (or `master=<commit>`, `release`) | cloned | — | the fork `cristianku/sunnypilot` master: **Sync fork** on GitHub (Cristian) |
| Nav2Pilot (setNavRoute waypoints, setMapboxToken) | `OP-apply-nav-alpha/patches/sunnypilot.patch`, published as `cristianku/openpilot:sunny-nav-alpha` and `cristianku/sunnypilot:nav-alpha` | the patch, 3-way, on the base | `sunnypilot/sunnypilot:master` | `OP-update-sunny-nav-alpha`; on conflicts `OP-apply-nav-alpha` |
| PSA port, stock ARTIV radar logging | `cristianku/opendbc:psa-torque-sunny-testing` | `opendbc_repo` pointer (the whole branch) | `sunnypilot/opendbc:master` | `op-merge-upstream sunny` |
| NNLC lateral model of the Peugeot 3008 | `cristianku/neural-network-data:master` | `sunnypilot/neural_network_data` pointer | `sunnypilot/neural-network-data` | **Sync fork** on GitHub; new Peugeot data with `op-nnlc-fetch-peugeot` |
| Distill driving models in the Models menu and SunnyLink | `cristianku/sunnypilot:distilled` | its 3 catalog files, changes since the merge-base with master | `sunnypilot/sunnypilot:master` | `OP-update-distilled` |
| Speed limits (Speed Limit Source "Map Data + Vision", `speedVisionSP`, the `vision` source, the models submodule `cristianku/speed-limits-models`) | `cristianku/sunnypilot:speed-limits` | all its changes since the merge-base with master | `sunnypilot/sunnypilot:master` | merge `sunnypilot/sunnypilot:master` into `speed-limits`, run its resolver tests, push (no skill yet) |
| torqued learning for PSA | the setup script itself | `'psa'` added to `ALLOWED_CARS` in `selfdrive/locationd/torqued.py` | — | — |

## Before the setup

1. The fork masters equal upstream: `cristianku/sunnypilot` master = `sunnypilot/sunnypilot` master (and
   `cristianku/openpilot` master = `commaai/openpilot` master for the comma variant). If not, Cristian syncs them on
   GitHub.
2. Each source above is not behind its upstream: run its update skill when it is. They push; stop and report on a
   conflict instead of forcing.
3. Then the setup (`OP-setup-psa-torque-testing sunny`), and on the comma `psa-torque-sunny-testing`.

How far behind each source is (read-only):

```bash
up=$(git ls-remote https://github.com/sunnypilot/sunnypilot.git master | cut -f1)
git ls-remote https://github.com/cristianku/sunnypilot.git master   # = $up when the fork is synced
# in a clone with both fetched: git rev-list --count <source>..$up   (0 = up to date)
```

A new external branch is added here, in the setup script (an `enable_*` step, fail closed on conflicts, a `SKIP_*`
switch) and in `OP-setup-psa-torque-testing/SKILL.md`.
