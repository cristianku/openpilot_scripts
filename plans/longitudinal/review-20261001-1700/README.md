# Verifica longitudinale PSA sui log recenti — 1 ottobre 2026

Il filtro nuovo può smussare i gradini documentati del comando di frenata. Il replay lo conferma; non dimostra che sparirà un rumore, né che la frenata fisica e la distanza dal lead resteranno adeguate. Il fattore 1.55 resta una taratura del port, non una costante PSA originale comprovata.

## Versione effettivamente presente sul comma

Letto via SSH in sola lettura da `comma@192.168.88.29`:
- openpilot `4bfe6f87f5d9e6d8bd2b618cbcfa9b11c2d812d9`, `psa-torque-sunny-testing`, commit del 17 settembre.
- opendbc `d79cb27c85fb9f447cb0276858a6a51376a09198`.
- `BRAKE_ACCEL_GAIN=1.55`; filtro frenata nuovo assente.
- Entrambi i checkout risultano puliti. Nessuna modifica/installazione/pull/reset/riavvio sul comma.

Le quattro route riportano lo stesso commit openpilot in `initData`. Non sono log del filtro appena pubblicato. Il codice locale esaminato è opendbc `4d68f2632c32a72b8d31b63a6e6786abc2b34d05`, che include il filtro del commit `017e5fa71c8146cedb576c3a3144a7663ec5a6f1`.

## Cronologia verificata in Git

- 11 settembre 2026, 23:56:52 Europe/Zurich: `8e8e1f1c6eb084f37e730bde0e3a5d9accdf49d2` aggiunge il percorso di controllo longitudinale sperimentale e i test. Questo è un dato sul codice, non la data provata della prima guida con longitudinale.
- 15 settembre, 21:05:39: `8ccc165e5` introduce il parametro di guadagno a 1.25; `82b01b1b` applica il guadagno nel ramo freno.
- 15 settembre, 23:34:35: `2138d3e4c32682fbf137ddfe344c7253664ec1b6` porta il guadagno da 1.25 a **1.55**, nella taratura route84.
- 1 ottobre, 18:25:20: `017e5fa71` aggiunge il filtro separato `BRAKE_FILTER_RC=0.20 s`, senza cambiare 1.55 o il limite -2.0 m/s².

## Acquisizione e verifica

Dati: `../../../log_analysis/longitudinal_review_20261001_1700/`.

174 file verificati SHA-256 contro il dispositivo: 141 qlog delle ultime quattro route e 33 rlog dell'ultima route. 167 copie esistenti corrispondono ai checksum riletti dal dispositivo e sono state riutilizzate; 7 rlog mancanti/incompleti (`b8--26..32`, 67.64 MB) sono stati scaricati adesso. Video esclusi. Lettura integrale Zstandard/Cap'n Proto riuscita.

| Route | Segmenti qlog | Durata letta | Rlog letti |
|---|---:|---:|---:|
| b8 / 8846cc65c2 | 33 | 32.22 min | 33, intera route |
| b7 / 4b0081ab51 | 33 | 32.05 min | 0 |
| b6 / eadcd02942 | 41 | 40.12 min | 0 |
| b4 / 68c9b67304 | 34 | 33.80 min | 0 |

La durata totale qlog è circa 138.19 min. I file hanno alcuni mtime incoerenti (luglio), perciò gli allineamenti e gli episodi usano tempi monotoni. Gli SHA-256 degli schemi `log.capnp`, `custom.capnp`, `deprecated.capnp`, `car.capnp` usati sono identici agli schemi riletti dal dispositivo.

Manifest, snapshot dispositivo, checksum schemi e verifica: `acquisition_manifest.json`, `acquisition_verification.json`, `device_snapshot.json`, `schema_checksums_remote.sha256` nella cartella dati. Gli originali restano nei rispettivi segmenti. Copie degli script di lavoro sono sotto `scripts/`; alcune mantengono riferimenti ai moduli di lavoro in `/tmp`.

## Evidenze dell'ultima route

192459 campioni carControl e 40 ingressi nel ramo freno. Durante controllo longitudinale senza pedali, la richiesta minima è circa -1.897 m/s² e il controller arriva al limite -2.0. Rilevati 26 rilasci del gas. Il bit DBC ABS `P351_Com_bABSIntvActv` resta zero nei 38792 messaggi Dat_ABR letti; non è una prova sul rumore o sull'uso della pompa per frenata automatica.

Episodio b8: circa 17:51 dall'inizio della registrazione (tempo monotono 1106.80 s), rilascio gas a 99.1 km/h, lead a circa 69 m, richiesta -1.663 m/s². Il controller installato passa da zero al limite -2.0 e il CAN 0x2B6 richiede -2.0. Il guadagno spiega la saturazione: -1.663 × 1.55 viene limitato a -2.0. Sono comandi intenzionali del controller; non equivalgono a pressione freno o decelerazione fisica.

Anche negli ultimi segmenti scaricati ci sono ingressi autonomi: tempo monotono 1797.93 s, 56.0 km/h, lead 46.2 m, richiesta -0.460 e vecchio comando -0.713; nessun gas nel secondo precedente. Il nuovo filtro darebbe inizialmente -0.034 e circa -0.341 dopo 100 ms, sugli stessi ingressi.

## Replay prima/dopo

Gli ingressi registrati carControl/carState, inclusa la pendenza orientationNED, sono mantenuti a 100 Hz e passati a `_update_longitudinal` del controller installato (caricato dal commit d79cb27c8) e del controller locale. Sono rispettate le condizioni registrate enabled/longActive/CAN/consenso cruise/pedali. Si assume sessione radar disponibile: questo replay verifica il calcolo del comando, non l'intero handshake radar/CAN. Per i qlog a 10 Hz si mantengono gli ingressi fino al campione successivo; i risultati intermedi sono simulati.

Sulla route b8, l'uscita del controller precedente ricostruita concorda con il carOutput registrato: errore assoluto mediano circa 3.3e-8 m/s², percentile95 circa 0.075 m/s². La non simultaneità dei topic contribuisce alle differenze. Nessun cambiamento delle condizioni active/braking nei 192459 campioni; entrambi hanno 40 ingressi freno. Massimo incremento verso frenata più forte per campione circa 0.01 s: prima 2.0, dopo 0.09524 m/s².

Nel gradino di 17:51: il nuovo comando parte da -0.09524 e dopo circa 100 ms è -0.88633; il vecchio passa direttamente a -2.0. Per un gradino mantenuto il filtro arriva al 90% in circa 0.47 s. Le richieste di frenata più deboli si applicano subito e i pedali/disattivazioni azzerano lo stato.

Il replay b4 a 10 Hz conferma il comportamento con 82 ingressi freno e zero cambiamenti dei modi active/braking; il massimo salto fra campioni è ridotto da circa 1.447 a 0.559 m/s². Non va confrontato direttamente con il valore per ciclo 100 Hz del rlog.

Il filtro **ritarda l'aumento della decelerazione richiesta**, anche per richieste forti. Non contiene un trattamento separato delle richieste urgenti. Il replay non ricalcola il planner sulla nuova velocità/distanza, non modella attuatori o pendenza fisica, non predice la nuova aEgo né prova la sufficienza della frenata. La risposta fisica registrata appartiene al codice vecchio.

Grafico: `../../../log_analysis/longitudinal_review_20261001_1700/brake_filter_replay.png`. Risultati: `controller_replay_summary.json` e timeline/replay CSV compressi nella cartella dati.

## Gli altri port usano moltiplicatori?

Ci sono conversioni e tarature specifiche, ma non un guadagno di frenata universale equivalente a PSA1.55:
- Honda Nidec: `gb = accel / 4.8 - creep_brake`, poi conversione del freno normalizzato in unità CAN mediante NIDEC_BRAKE_MAX; inoltre isteresi e limitazione dell'incremento. È una conversione fra accelerazione e comando freno grezzo.
- GM: interpolazione fra accelerazione richiesta e BRAKE_LOOKUP_BP/BRAKE_LOOKUP_V, distinguendo rigenerazione e freno a frizione.
- Hyundai upstream: accelerazione richiesta limitata ai bounds e inviata ai costruttori ACC; in quel controller non c'è il moltiplicatore PSA1.55.

Fonti primarie verificate: https://raw.githubusercontent.com/commaai/opendbc/master/opendbc/car/honda/carcontroller.py ; https://raw.githubusercontent.com/commaai/opendbc/master/opendbc/car/gm/carcontroller.py ; https://raw.githubusercontent.com/commaai/opendbc/master/opendbc/car/hyundai/carcontroller.py . Nel checkout Sunny sono presenti ulteriori percorsi/tuning: la descrizione Hyundai riguarda il controller upstream esaminato.

Nel nostro caso 1.55 moltiplica un comando già espresso in m/s² (amplificazione fino al55%, prima del clamp). Per richieste sotto circa -1.2903 m/s² raggiunge già -2.0. I log mostrano che la formula viene applicata; non dimostrano che 1.55 sia la taratura migliore o corretta.

## Test eseguiti ora e limiti

`.venv/bin/python -m pytest -q opendbc/car/psa/tests/test_longitudinal_brake_filter.py opendbc/safety/tests/test_psa_brake_filter.py`: **9 passati, 10 subtest passati**.

`.venv/bin/python -m pytest -q opendbc/car/psa/tests/test_longitudinal_response_tuning.py`: **3 passati**.

La suite PSA completa ha già fallimenti preesistenti, confrontati prima/dopo il merge nella sessione precedente; non è stata rieseguita qui. Nessuna prova sul comma con il filtro, nessuna installazione o modifica ai repository prodotto. Bonsai non disponibile dopo due tentativi; acquisizione e analisi effettuate dal primario.
