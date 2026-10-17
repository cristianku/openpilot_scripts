# EPS Defect PSA 3008 — domande round 2

**Data:** 16 ottobre 2026
**Per:** ChatGPT Astra (accesso in lettura ai file del Mac)
**Vincoli:** sola lettura. Nessuna modifica ai repository, nessuna scrittura o riavvio sul comma (`ssh comma`). La **safety del panda (`opendbc/safety/modes/psa.h`) non si tocca**: Cristian non vuole allentamenti, quindi niente passthrough dinamico del LANE_KEEP_ASSIST della telecamera.

Grazie per il round 1. Abbiamo accettato:
- la riserva sugli echo, che non sono il tempo reale sul filo;
- il test a 100 Hz isolato, con il dither spento;
- tutte le osservazioni sul dither.

Restano cinque domande.

---

## Stato attuale

- **LANE_KEEP_ASSIST a 100 Hz** (non committato, non ancora sul comma). Il contenuto si calcola ancora ogni `STEER_STEP = 5` cicli; nei 4 cicli in mezzo si rimanda identico l'ultimo frame.
  - Diff: `lka_100hz.diff` (in questa cartella)
  - Test: `test_lka_100hz.py` (in questa cartella; nel repo è `opendbc/car/psa/tests/test_lka_100hz.py`)
  - Repo: `/Users/cristianku/GitHub/COMMA.AI/CRISTIANKU/opendbc` (branch `psa-torque-sunny-testing`, HEAD `4ea63ca81`)
  - Test locali:
    - car PSA: 67 falliti prima e dopo (gli stessi, test vecchi radar/longitudinale), 125 → 128 passati;
    - safety PSA: identica al baseline (12 falliti preesistenti).
- **Per il giro di prova** il piano è `EPS_DITHER_AMPLITUDE = 0` in `opendbc/car/psa/values.py`, quindi solo i 100 Hz.

## Percorsi

- **Log** (rlog/qlog, niente video): `/Users/cristianku/Downloads/comma_logs/<route>--<seg>/`
  - oggi: `0000010e` … `00000115`, tutti con rlog;
  - 14 ottobre: qlog `00000104` … `0000010b`; rlog di `00000104` e `00000108` (segmenti 4–7).
- **Log storici con rlog** (settembre/1 ottobre, tutti dopo la reinstallazione): sotto `/Users/cristianku/GitHub/COMMA.AI/CRISTIANKU/openpilot_scripts/comma_logs/` e `/Users/cristianku/GitHub/COMMA.AI/CRISTIANKU/openpilot_scripts/log_analysis/*/`
- **Script di analisi del round 1** (copiati qui, stabili): `scripts/`. Prendono come argomento **una cartella per route che contiene le cartelle dei segmenti**. Per costruirla dalla struttura piatta di Downloads:
  ```sh
  mkdir -p /tmp/routes
  for d in ~/Downloads/comma_logs/*--*--*; do
    r=$(basename $d | sed -E 's/--[0-9]+$//')
    mkdir -p /tmp/routes/$r
    ln -sfn $d /tmp/routes/$r/
  done
  ```
- **Parser**: `/Users/cristianku/GitHub/COMMA.AI/CRISTIANKU/openpilot_scripts/log_analysis/psa_eps_timeline.py`
  - `CEREAL_DIR=/Users/cristianku/GitHub/COMMA.AI/CRISTIANKU/new_openpilot_psa_torque_sunny_testing/openpilot/cereal`
- **Workspace openpilot** (software di oggi `a8b556a07`): `/Users/cristianku/GitHub/COMMA.AI/CRISTIANKU/new_openpilot_psa_torque_sunny_testing`

---

## Domande

### 1. Revisione della modifica a 100 Hz

Leggi `lka_100hz.diff` e il contesto in `opendbc/car/psa/carcontroller.py`, cioè `update()`, `_activate_eps`, `_deactivate_eps` e `_reset_lat_state`. Poi dimmi:

- Rischi nelle transizioni: scaletta di attivazione 2→3→4, rearm, disingaggio, primo avvio con `lka_msg_last = None`, cambio di stato EPS a metà dei 5 cicli.
- La safety del panda (`psa_tx_hook`, limiti 8/38, `max_rt_delta`) accetta 5 frame identici ogni 50 ms senza effetti collaterali, ad esempio su `desired_torque_last` o `rt_torque_last`?
- Va cambiato qualcosa prima del giro di prova?

### 2. Protocollo del giro di prova

La frequenza dei Defect varia molto tra giri con lo stesso software (da 0 a 111/ora). Ci serve un criterio per dire se i 100 Hz funzionano:

- Quanti minuti servono, da disingaggiato e da ingaggiato, per concludere qualcosa (es. confronto Poisson con 64/ora disingaggiato e 111/ora ingaggiato in classe 30/70)?
- A 100 Hz la metrica "% intervalli a 50 ms" non ha più senso. Quale metrica di cadenza sugli echo usiamo (buco massimo, percentili degli intervalli…)? Se ti va, adatta `scripts/segstate.py` e dimmi il comando.
- Cos'altro controllare nei log dopo il giro: `0x795`, scarti safety (src 192), `steerFaultTemporary`, altro?

### 3. Versione di prima della reinstallazione

Per circa 6 mesi il problema non c'era; dopo la reinstallazione sì.

- Dove possono essere rimaste tracce sul comma della versione precedente: AGNOS, firmware/firma del panda, params, `/persist`, log di boot, altro? Dammi **comandi in sola lettura** da lanciare via `ssh comma`. Non lanciarli tu se scrivono qualcosa.
- Come ricostruire dalla storia git (`cristianku/openpilot`, branch testing, commit "Update Peugeot 3008 Sunny testing repository pointers") quale base sunnypilot/openpilot girava prima?

### 4. Il commit `aa0ac919b` (SPI turnaround 400 µs, 5 agosto 2026)

È nel software di oggi. Analizza `openpilot/selfdrive/pandad/spi.cc`, `panda.cc` e `pandad.cc`:

- Il thread di invio (`can_send_thread`) può restare bloccato dal lock SPI mentre il loop RX a 100 Hz legge? Per quanto, con il traffico reale? Route 108, da `pandaStates`: in ricezione bus0 ~1.500, bus1 ~980, bus2 ~240 frame/s; in trasmissione (inoltro compreso) bus2 ~1.500, bus0 ~240 frame/s.
- Questo può produrre ritardi TX a scalini da ~10 ms, compatibili con i 3/7/11/21 ms che vediamo tra `sendcan` e l'echo?
- Annullare quel commit in locale per un giro di prova è un esperimento sensato e sicuro? Il firmware del panda e la safety non cambiano.

### 5. Leggere i DTC dell'EPS

L'EPS risponde alla diagnosi su `0x6B5` (vedi `opendbc/car/psa/values.py`, query FW).

- È sicuro leggere i DTC dell'EPS dal comma, offroad, con il quadro acceso: UDS `0x19 0x02`, sola lettura?
- Quale indirizzo di risposta, quale bus, che sessione serve?
- Prepara uno script in sola lettura (libreria UDS di opendbc/panda) da far lanciare a Cristian. **Niente clear DTC, niente cambi di sessione oltre il necessario.**

---

Rispondi in modo concreto, con numeri. Per ogni analisi sui log dimmi il comando esatto. Scrivi i risultati in un file `.md` accanto a questo, per esempio `risposte_astra_round2.md`.
