# Discord entry points

<!-- [discord news] - START -->
Observed on 18 October 2026. These are navigation hints, not proof of present access or a complete channel inventory. Verify visible names and timestamps in Discord. Inspect active forum threads as well as channel feeds.

## comma.ai community

Server ID: `469524606043160576`.

| Channel | ID | Use |
| --- | --- | --- |
| announcements | `524572601826410498` | Official announcements |
| dev-openpilot | `524594418628558878` | Navigation, models and upstream development |
| dev-opendbc | `1282121586002104402` | Vehicle integration and CAN |
| current-projects | `1249579909739708446` | Active development forum |
| chestnut | `1185723603191337001` | Model hardware and compatibility |
| comma-four | `1436852432503046294` | Device developments and field reports |
| comma-three-3x | `871838269405556736` | Older device developments and compatibility |
| panda | `524328405433450531` | Vehicle interface hardware |
| datasets | `1302044405280149536` | Data and training |
| dev-connect-web | `1244366765983535145` | Web, remote device access and navigation integrations |

## sunnypilot

Server ID: `880416502577266699`.

Official community forum: `https://community.sunnypilot.ai/` (latest topics: `/latest`). The project states that Discord is no longer actively maintained/monitored for official support. Check the forum for current developments instead of treating old Discord announcements as the latest project activity. Source: `https://community.sunnypilot.ai/t/new-community-forum-in-open-beta/361` and the Discord announcements channel.

| Channel | ID | Use |
| --- | --- | --- |
| announcements | `881348853956223006` | Project announcements |
| sunnypilot-updates | `881222129322950727` | Release announcements |
| sunnylink-updates | `1267280242192551976` | Remote configuration service |
| dev-sunnypilot | `1015026687844560907` | Development events; filter star/fork noise |
| general | `880416502577266703` | Current technical discussion and maintainer replies |
| tuning-nnlc | `1118704399850680522` | Neural lateral control and tuning |
| driving-model-discussion | `1182907121621278801` | Model-specific forum discussions |
| sunnypilot-experience | `1033780445416013864` | User reports; distinguish them from validated changes |

Vehicle channels and additional categories may be below the current sidebar viewport or collapsed. Discover relevant accessible ones from the UI, especially when Cristian specifies a car or port.

## Technical starting points

- Official openpilot docs: `https://docs.comma.ai/`; safety concepts: `https://docs.comma.ai/concepts/safety/`.
- Official Sunnypilot documentation index: `https://community.sunnypilot.ai/t/documentation-index/202`.
- Maintainer explanation of torque controller v0/v1 (19 February 2026): `https://community.sunnypilot.ai/t/torque-lateral-control-update-tuning-toggle-v0-vs-v1/3124`. Useful for distinguishing controller tuning from driving model behavior; check current code before treating an old configuration instruction as current.
- Speed-dependent torque learning discussion (21 March 2026): `https://community.sunnypilot.ai/t/speed-dependent-torque-learning-for-non-linear-eps/3922`. Read replies and linked PRs; the initial vehicle-specific report is not proof of availability or benefit on PSA.

Treat these as starting points for investigation, not a closed reading list. Follow original design explanations and current code where the topic leads.
<!-- [discord news] - END -->
