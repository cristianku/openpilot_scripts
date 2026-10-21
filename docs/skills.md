# Skills

Each skill directory contains a `SKILL.md` manifest and a `scripts/` implementation. Run the wrapper script, never the `_common.sh` directly. See the repo `README.md` for how to install them as Codex skills (symlink into `~/.agents/skills/`).

## setup-psa-torque (stable)

Recreates the mapped local openpilot folder from upstream `master` by default, or from the latest published GitHub Release with `release`. It recreates the custom **stable** branch (`psa-torque` / `psa-torque-sunny`) from that source, points `.gitmodules` to `cristianku/opendbc`, sets the `opendbc_repo` gitlink to the matching stable opendbc branch commit, and for `sunny` points `sunnypilot/neural_network_data` to `cristianku/neural-network-data:master`. Pushes with `--force-with-lease`. Does not commit inside opendbc or touch panda.

```bash
./setup-psa-torque/scripts/setup_psa_torque.sh comma master
./setup-psa-torque/scripts/setup_psa_torque.sh sunny release
```

## setup-psa-torque-testing (testing)

Same as above but for the **testing** branches (`psa-torque-testing` / `psa-torque-sunny-testing`).

```bash
./setup-psa-torque-testing/scripts/setup_psa_torque.sh comma   # or: sunny
```

<!-- [pinned source] - START -->
### Bloccare il testing a un commit del master

Usa `master=<commit>` per generare la branch testing da uno specifico commit appartenente alla storia del `master` ufficiale selezionato:

```bash
./OP-setup-psa-torque-testing/scripts/setup_psa_torque.sh sunny master=de197ba6
```

Sono accettati SHA Git esadecimali da 7 a 40 caratteri. Lo script clona il master ufficiale, risolve lo SHA, verifica che sia un suo antenato e interrompe il workflow senza push se il controllo fallisce.

Lo SHA deve appartenere all'upstream ufficiale (`sunnypilot/sunnypilot` oppure `commaai/openpilot`), non alla branch generata in `cristianku/openpilot`. Per riprodurre la base del commit personalizzato `4b34316`, usa il suo parent upstream Sunnypilot: `master=de197ba6`.

Il pin blocca soltanto il codice upstream. Con `sunny`, il submodule `sunnypilot/neural_network_data` continua a essere aggiornato al commit più recente pubblicato su `cristianku/neural-network-data:master`, quindi `neural_network_lateral_control/PSA_PEUGEOT_3008.json` resta fresco. Il workflow non modifica il codice del loader o del controller NNLC.
<!-- [pinned source] - END -->

## OP-merge-psa-torque-testing / OP-merge-psa-torque-sunny-testing (promote)

<!-- [merge only] - START -->
Promote opendbc testing → stable: recreate a dedicated opendbc merge workspace, merge `*-testing` into stable with a merge commit, require Peugeot 3008 interface tests + PSA safety tests to pass, and push stable with a lease protecting the previously observed remote SHA. Both skills stop here: Cristian runs openpilot setup separately, choosing its source. Neither rebuilds openpilot or refreshes its submodule pointer.
<!-- [merge only] - END -->

```bash
./OP-merge-psa-torque-testing/scripts/merge_psa_torque.sh
./OP-merge-psa-torque-sunny-testing/scripts/merge_psa_torque.sh
```

## commit-push-opendbc

Stage/commit/push working changes in `cristianku/opendbc` on the current feature branch. Verifies `origin` is `cristianku/opendbc`, refuses protected branches (`master`/`main`), never force-pushes, only touches opendbc.

```bash
./commit-push-opendbc/scripts/commit_push.sh "optional message"
```

<!-- [upstream merge] - START -->
## op-merge-upstream

Integra il `master` ufficiale di opendbc nel branch testing locale: `sunny` usa `sunnypilot/opendbc` e `psa-torque-sunny-testing`; `comma` usa `commaai/opendbc` e `psa-torque-testing`. Richiede il branch corretto già attivo e un checkout pulito. Completa la storia shallow, verifica l'antenato comune e crea un branch di backup prima del merge.

```bash
bash /Users/cristianku/GitHub/COMMA.AI/CRISTIANKU/openpilot_scripts/op-merge-upstream/scripts/merge_upstream.sh sunny
```

Il merge resta **senza commit e senza push**, anche se sarebbe possibile un fast-forward. In caso di conflitti si ferma e mostra i file da esaminare; non sceglie automaticamente ours/theirs. Verificare il diff, i test PSA e la compatibilità con la base openpilot scelta prima di pubblicare. Per annullare il merge ancora in corso usare `git merge --abort`, dopo aver verificato che non ci siano nuove modifiche da preservare. Non aggiorna openpilot né dispositivi.
<!-- [upstream merge] - END -->

<!-- [comma update] - START -->
## op-update-comma

Aggiorna `/data/openpilot` sul dispositivo `comma` mantenendo branch e upstream attivi, accetta soltanto fast-forward, aggiorna ricorsivamente i submodule e riavvia soltanto dopo un aggiornamento riuscito. Rifiuta working tree sporchi, detached HEAD e branch divergenti.

```bash
./OP-UPDATE-COMMA/scripts/update_comma.sh comma
./OP-UPDATE-COMMA/scripts/update_comma.sh --dry-run comma
```
<!-- [comma update] - END -->

<!-- [discord news] - START -->
## OP-news (technical community news)

Invoke `$OP-news` to discover important developments and learn about openpilot through the comma.ai/Sunnypilot Discord servers, Sunnypilot's community forum and original documentation/code. Read older discussions when useful; prioritize technical value over age. Topics include navigation, models, controls, safety, porting, NNLC and hardware. It explains findings in natural Italian with dated links, distinguishing current behavior, historical designs, proposals and user reports. It does not post, react, install updates or change device state.

Examples: `$OP-news ultime 24 ore`, `$OP-news solo sunnypilot, modelli e NNLC`. Source: `OP-news/SKILL.md`; known server/channel entry points are in `OP-news/references/channels.md`.
<!-- [discord news] - END -->

## OP-apply-nav-alpha (Nav2Pilot)

Lavora sulle patch Nav2Pilot nei cloni locali (conflitti, modifiche al codice) e pubblica `cristianku/openpilot` `nav-alpha` (comma) o `sunny-nav-alpha` (sunnypilot) dall'ultimo master upstream, riapplicando solo le modifiche Nav2Pilot (`setNavRoute` con waypoint, `setMapboxToken`), salvate come patch in `OP-apply-nav-alpha/patches/`. Un solo commit sopra master, backup locale `nav-alpha-prev`, push solo con l'ok di Cristian. Dettagli e risoluzione conflitti: [nav-alpha-nav2pilot.md](nav-alpha-nav2pilot.md).

```bash
./OP-apply-nav-alpha/scripts/apply_nav_alpha.sh sunny status   # oppure: comma
./OP-apply-nav-alpha/scripts/apply_nav_alpha.sh sunny apply
```

## OP-update-nav-alpha, OP-update-sunny-nav-alpha, OP-update-distilled

Un comando per riallineare al master upstream un branch di `cristianku/openpilot` e pubblicarlo (push solo se e' indietro):
`nav-alpha` (comma + Nav2Pilot), `sunny-nav-alpha` (sunnypilot + Nav2Pilot), `distilled` (sunnypilot + modelli openpilot.distill
nel menu Models). Si installano con `installer.comma.ai/cristianku/<branch>`. Se la patch non si applica piu' si ferma
senza pubblicare. I setup PSA chiamano lo stesso script per il loro nav-alpha.

```bash
./scripts/update_fork_branch.sh sunny-nav-alpha   # oppure: nav-alpha, distilled; NO_PUSH=true per provare
```

<!-- [community publication] - START -->
## Community posts / release notes

When a SunnyPilot-based feature is announced publicly, the announcement must name its **actual maintained source branch** and the **separate installable branch** in `cristianku/openpilot`; verify both are published and correspond. Follow [docs/community-publication.md](community-publication.md) for the template, validation and Distill-specific status notes. This does not change or execute any skill.
<!-- [community publication] - END -->

## Common overrides

`GITHUB_USER`, `WORKSPACE_ROOT`, `OPENPILOT_DIR`, `OPENPILOT_REPO`, `OPENPILOT_SOURCE_REPO`, `OPENPILOT_SOURCE_BRANCH`, `OPENDBC_REPO`, `OPENDBC_SOURCE_REPO`, `OPENDBC_SOURCE_BRANCH`, `NEURAL_NETWORK_DATA_REPO`, `NEURAL_NETWORK_DATA_BRANCH`, `COMMIT_MESSAGE`. Merge skills add `MERGE_DIR`, `MERGE_TEST_COMMAND`, and `SKIP_TESTS=true` (explicitly authorized emergency only).
