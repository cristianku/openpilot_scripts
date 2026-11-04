# ops-web

openpilot cristianku home: the home page of this work. It shows what is behind, reading GitHub by itself, and starts the skills of
this repository with a button. It runs on the server `openpilot-distill`, port 8768, at https://ops.farm.14bodhi.com.

## Install or update

```bash
portal/install_service.sh            # unit, /etc/ops-web.env, start; safe to run again
portal/install_service.sh --dry-run  # prints the unit, changes nothing
systemctl restart ops-web            # after a change here; a running job survives it
python3 portal/tests/test_portal.py  # the tests: they run no skill
```

Data is in `/root/work/ops-web`: `cache.git`, `status.json` and `logs/`. It can be deleted when no job is running.

## What it reads

Every 10 minutes, after each job and with Check now. The status comes from a bare cache that holds commits and trees
only (about 26 MB), with no token. `portal/status.py` lists every branch and what it follows, as in
`docs/external-branches.md`. A new source of a setup goes there too.

The generated branch needs a build when master, a submodule pointer or what an injected branch adds has changed. Files
are compared, not dates: a realignment moves `sunny-nav-alpha` and changes nothing it adds. A file two injected
branches change, or that master changed too, has neither one's content, so it is left out of the comparison.

The comma.ai sources (`nav-alpha`, `psa-torque-testing`) have their own group on the page. They never become a step of
the to-do list, because the comma runs the sunnypilot build.

The comma is read with `git rev-parse` over ssh, and nothing else. When it is off or away the page says so.

## What it runs

Only the actions in `portal/catalog.py`, with parameters checked against their own lists. Every skill folder needs an
entry there, or the tests fail and the page lists it. Skills that need a person or the Mac are shown without a button.

- One job at a time. A job does not start while a script of `BUSY_SCRIPTS` runs on this machine, for example a Publish
  of the speed limits site. The other way round is not checked: a Publish started during a portal job is not blocked.
- A trial run sets `NO_PUSH=true` and uses its own workspace, or `--dry-run` on the comma.
- `op-merge-upstream` never switches branch, so each variant has its clone: `/root/work/opendbc` for sunnypilot and
  `/root/work/opendbc-comma` for comma.ai, made by `install_service.sh`. The merge stays pending there.

## Who can reach it

- Only loopback and `OPS_WEB_PROXY_IPS` (raspy), and only with a host of `OPS_WEB_HOSTS`. A refused address is written
  to the service log: `journalctl -u ops-web`.
- The sign-in code, `OPS_WEB_TOKEN` in `/etc/ops-web.env`, makes a session of 30 days.
- Authentik replaces the code only when Traefik also sends `X-Ops-Proxy-Secret` with the value of
  `OPS_WEB_PROXY_SECRET`. The address of raspy is no proof: its 21 containers, public sites included, leave from it, and
  any of them could forge `X-authentik-username`.
