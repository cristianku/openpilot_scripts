$op-setup-psa-torque-testing sunny master=de197ba6

<!-- [upstream merge] - START -->
Per preparare il merge del master ufficiale **opendbc** nel testing Sunny:

`$op-merge-upstream sunny`

Richiede un checkout pulito su `psa-torque-sunny-testing`. Crea un backup e lascia il merge senza commit/push, da controllare e testare. È un'operazione separata dal setup openpilot qui sopra.
<!-- [upstream merge] - END -->

<!-- [pinned source] - START -->
> **Nota:** `de197ba6` è la base Sunnypilot del 30 agosto 2026 che completa correttamente l'installazione sul comma. I master successivi introducono 44 commit, incluso AGNOS 19.7, e sul dispositivo l'installazione resta bloccata. Il pin riguarda soltanto il codice Sunnypilot: il workflow continua a caricare il JSON PSA più recente da `cristianku/neural-network-data:master` e non modifica il loader o il controller NNLC. La base contiene già il ripristino dei PID NNLC della [PR #1779](https://github.com/sunnypilot/sunnypilot/pull/1779) e il Lateral Jerk Torque Controller. La community segnala inoltre ping-pong con NNLC abbinato ai driving model moderni; per una prova comparabile usare un modello Legacy oppure disabilitare NNLC.
<!-- [pinned source] - END -->

<!-- [artiv programming] - START -->
## 11 settembre 2026 — prova ARTIV programming

Setup eseguito con `$op-setup-psa-torque-testing sunny master` e pubblicato sul branch `psa-torque-sunny-testing`:

| Componente | Commit |
| --- | --- |
| openpilot generato | `04bfc6d26e72fa11a6186a7216d520add61349cd` |
| Base Sunnypilot master | `6135084c941d4d947dd90c78326a557c3c857f89` |
| opendbc con prova ARTIV | `766a8903b9d31c677d1874d5e4be6ad044b8e587` |
| Neural data master | `ddff5973d9e666ca42896fb59bdb10ff7541c5fd` |

Questo setup usa il master corrente, non il pin `de197ba6` indicato sopra. La pubblicazione è verificata; installazione e funzionamento sul veicolo di questa versione restano da verificare. Apprendimento torque PSA abilitato in `torqued.py`.

### Comportamento della prova

- Solo Peugeot 3008: dopo 10 secondi consecutivi da fermo con CAN valido, invia una richiesta `02 10 02` a `0x6B6`, bus 1, DLC 3.
- Movimento o CAN non valido fanno ripartire l'attesa. Una volta inviata, la richiesta non viene ripetuta fino al riavvio del controller; nessun TesterPresent di mantenimento.
- La safety inclusa autorizza questo comando corto; quella precedente lo blocca.
- Nei log controllare l'eco TX e la risposta su `0x696`: `50 02` indica accettazione, `7F 10 xx` un rifiuto con relativo codice. Verificare anche i messaggi radar `0x2F6` e `0x4F6`: l'invio della richiesta non dimostra che il radar sia entrato in programming o abbia smesso di trasmettere.

**Prova esclusivamente con auto parcheggiata e mantenuta ferma.** La sessione può rendere indisponibili radar, ACC e frenata automatica; il ritorno al funzionamento normale va verificato prima di muoversi.

Verifica locale: 8 test ARTIV passati. La suite PSA completa presenta 11 errori riprodotti anche sul codice precedente alla modifica.

**Installazione e prova sul comma a cura di Cristian. Nessuna installazione automatica né modifica al dispositivo eseguita dall'agente.**
<!-- [artiv programming] - END -->
