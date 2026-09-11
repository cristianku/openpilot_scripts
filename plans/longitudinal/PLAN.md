# Longitudinale PSA Peugeot 3008 — findings e piano di implementazione

> Per l’esecuzione: usare `superpowers:executing-plans` e TDD, un passo alla volta nella sessione corrente. Questo documento pianifica il lavoro; non abilita il controllo sul veicolo.

**Data:** 11 settembre 2026. **Stato:** passi 1–4 verificati offline; abilitazione alpha_long del passo 6 collegata su richiesta di Cristian; calibrazione ancora aperta.

**Obiettivo:** collegare l’accelerazione richiesta da Sunnypilot ai messaggi longitudinali PSA, sostituendo il radar ARTIV con gestione coerente di coppia, frenata, disattivazione e comunicazione.

**Architettura:** `CarController` decide stati, richieste, frequenze e contatori. I quattro costruttori esistenti in `psacan.py` codificano i segnali espliciti. La sessione ARTIV gestisce accettazione diagnostica, silenzio radar ed echi; la safety verifica separatamente i comandi consentiti.

**Tecnologie:** Python, CANPacker/CANParser e DBC PSA, log Cap’n Proto/Zstandard, safety C e libsafety, test locali.

**Specifica:** le sezioni 3–5 di questo stesso documento costituiscono la specifica della prima implementazione. La sezione 1 contiene osservazioni, la sezione 2 i limiti dell’interpretazione. Le ipotesi sperimentali sono esplicitamente identificate e non equivalgono a calibrazioni validate.

## Vincoli comuni

- Repository di implementazione: `/Users/cristianku/GitHub/COMMA.AI/CRISTIANKU/opendbc`, ramo `psa-torque-sunny-testing`.
- Questo piano e i relativi findings risiedono in `openpilot_scripts/plans/longitudinal/`, come richiesto da Cristian.
- Prima piattaforma: `CAR.PSA_PEUGEOT_3008`. Le altre PSA conservano il comportamento precedente.
- `/Users/cristianku/GitHub/COMMA.AI/ELKOLED/elkoled_opendbc` è **esclusivamente in sola lettura**. È un prototipo incompleto da cui prendere spunti.
- Conservare la separazione controller/costruttori CAN richiesta da Cristian: niente logica di controllo, frequenze o valori nascosti in `psacan.py`.
- Ogni modifica di codice avrà i marcatori di inizio/fine del blocco, per esempio `# [psa longitudinal] - START` / `END`.
- Preservare modifiche preesistenti e port laterale. Niente refactor, commit, push o rigenerazione openpilot impliciti nell’esecuzione di questo piano.
- Installazioni, aggiornamenti, prove di attuazione e riavvii sul comma sono eseguiti da Cristian. Nessuna di queste operazioni è autorizzata da questo documento.
- Serverone-ai non deve essere acceso, neppure indirettamente.

## Avanzamento dell’implementazione — 11 settembre 2026

Prima consegna locale estesa ai passi **1–4**: fixture originali, generatore dinamico, sessione utilizzabile in movimento dopo conferma e filtro safety C. I passi **5 e 7 rimangono aperti** e il passo **6 è parzialmente completato**. Su successiva richiesta esplicita di Cristian («abilitalo»), `alpha_long=True` ora abilita il profilo Peugeot 3008, rimuove `dashcamOnly` e imposta il flag safety. Senza selezione il default resta dashcam. Questa richiesta anticipa l’abilitazione rispetto alla calibrazione prevista; non convalida i valori sperimentali.

- **43 test passati**: 12 comandi/fixture, 8 sessione longitudinale, 16 regressioni neutre, 7 safety longitudinale con libsafety C compilata localmente.
- TDD verificato sui comportamenti mancanti: prima dell’implementazione fallivano 18 asserzioni del generatore, 4 della sessione e 32 della safety; le fixture di codifica erano già verdi.
- Ruff sui sette file Python modificati/aggiunti: passato. Verifica del diff e documentazione della consegna in [LONGITUDINAL.md](LONGITUDINAL.md).
- Suite safety PSA precedente: 67 test, 45 passati, 12 saltati, **10 fallimenti identici prima/dopo**, verificati anche in un archivio temporaneo del commit `74bfc461d37621ac2ffcd0939425fe9fb081e1d7`.
- Le 33 funzioni test PSA esistenti, eseguite direttamente senza pytest: 32 passate e lo stesso errore preesistente su `_update_cruise_button_events`, prima/dopo. Suite pytest completa non eseguita perché pytest non installato.
- L’ordine e la coerenza dei due ID sono verificati nei test del controller; la safety controlla i singoli payload, senza una transazione atomica fra frame CAN.
- Il filtro safety TX si applica anche senza il nuovo flag. Un takeover legacy che ricopia un `0x2F6` con richieste fisiche non autorizzate può quindi essere rifiutato: i test laterali Python invariati non dimostrano l’invarianza di ogni avviso stock. Il problema safety laterale preesistente resta fuori da questa modifica.
- La perdita della sessione durante frenata interrompe gli invii, azzera l’accelerazione riportata ed espone `accFaulted` al successivo update. La risposta fisica delle ECU e il ritorno del radar in movimento restano da verificare.
- Nessuna modifica a Elkoled, installazione sul comma, commit o push. I valori min-time 6,2 e coppie inizialmente uguali rimangono ipotesi sperimentali, non risultati validati sul veicolo.

## 1. Findings verificati

### 1.1 La «bibbia» dashcam

[Archivio originale e README](../../log_analysis/dashcam_mode_bibbia_longitudinale/0000003a--e445e79563/README.md).

| Dato | Valore verificato |
|---|---|
| Route | `6616faac453a3064/0000003a--e445e79563` |
| Acquisizione | 8 segmenti, 8 rlog + 8 qlog, 76.721.126 byte |
| Integrità | SHA-256 confrontati con il comma; tutti i 16 log decodificati integralmente |
| Intervallo registrato | 434,042 s, circa 7 min 14 s |
| Velocità massima da `carState.vEgo` | 76,98 km/h |
| openpilot registrato | `f544c80ffeb669ff5e5bcbbc372e610c6eb04898` |
| Parametri registrati | `dashcamOnly=true`, `passive=true`, `openpilotLongitudinalControl=false`, `pcmCruise=true` |
| `carControl.longActive=true` | Nessun campione |

Cristian ha usato il longitudinale originale della vettura mentre Sunnypilot registrava in dashcam mode. Questi dati sono il riferimento dei messaggi originali; non dimostrano che Sunnypilot abbia già controllato accelerazione o frenata.

Versioni lette durante il confronto:

- opendbc locale: `74bfc461d37621ac2ffcd0939425fe9fb081e1d7`;
- Elkoled: `cdf7eab4ae95e41c8569eff11171645b527dd31a`.

Le date di alcuni file sul dispositivo sono incoerenti. Per correlare i segnali usare identificatore route, segmento e `logMonoTime`.

### 1.2 Messaggi radar e ricodifica

Solo frame CAN effettivamente ricevuti su bus 1, esclusi gli echi TX:

| ID | Messaggio | Frequenza nominale | Frame nella route |
|---|---|---:|---:|
| `0x2B6` | `HS2_DYN1_MDD_ETAT_2B6` | 50 Hz | 21.656 |
| `0x2F6` | `HS2_DYN_MDD_ETAT_2F6` | 50 Hz | 21.655 |
| `0x4F6` | `HS2_DAT_ARTIV_V2_4F6` | 10 Hz | 4.331 |
| `0x796` | `HS2_SUPV_ARTIV_796` | 1 Hz | 433 |

I due DBC hanno lo stesso layout per `0x2B6` e `0x2F6`: segnali, bit, dimensioni, segno, fattori e offset.

Con il DBC corrente e i nostri costruttori abbiamo decodificato e ricodificato **43.311/43.311 frame identici byte per byte**. Tutti i checksum dei due ID sono validi. Questo verifica la codifica, non il significato fisico di ogni campo né una legge di controllo.

I contatori avanzano normalmente modulo 16; sono presenti pochi salti di acquisizione. Non imporre continuità artificiale ai dati originali.

### 1.3 Stati longitudinali osservati in `0x2B6`

| Condizione secondo il DBC | `ACC_STATUS` | `POTENTIAL_WHEEL_TORQUE_REQUEST` | `WHEEL_TORQUE_REQUEST` | `MDD_DECEL_TYPE` | `MDD_DECEL_CONTROL_REQ` |
|---|---:|---:|---:|---:|---:|
| Inhibited / Waiting | 2 / 3 | 0 | 0 | 0 | 0 |
| Controllo in modalità GMP | 4 | 1 | 1 oppure 2 | 0 | 0 |
| Frenata ACC | 4 | 2 | 0 | 1 | 1 |
| Suspended osservato | 5 | 1 | 1 oppure 2 | 0 | 0 |

Conteggi: 12.524 frame con stato 2, 686 con stato 3, 8.374 con stato 4 e 72 con stato 5. La frenata ACC compare in 2.194 frame `0x2B6`.

La combinazione dei flag distingue una richiesta fisica da un codice inattivo: `2.05` nel campo decelerazione e `-4000` nei campi coppia sono usati nei payload inattivi. Non interpretarli come un’accelerazione o coppia da applicare.

La decelerazione minima decodificata in questa route è **-0,8 m/s²**. La registrazione non convalida frenate forti o di emergenza.

### 1.4 Le due coppie non sono equivalenti

Elkoled assegna lo stesso `torque` a `GMP_POTENTIAL_WHEEL_TORQUE` e `GMP_WHEEL_TORQUE`.

Nella route ci sono 6.252 frame con entrambe le richieste abilitate. In 6.098 di questi i due campi differiscono di più di 2 Nm, quindi la differenza non è spiegata dal solo arrotondamento del primo campo a passi di 4 Nm. La differenza fra i campi va da -672 a +510 Nm.

Massimi decodificati: 776 Nm nel campo potential e 832 Nm nel campo wheel. Sono osservazioni di questa guida, non limiti della vettura.

### 1.5 `MIN_TIME_FOR_DESIRED_GEAR`: alternanza verificata

Il campo è codificato su 6 bit con fattore DBC 0,1. Il nome e l’unità dichiarati nel DBC non provano da soli la sua funzione reale.

In **21.656/21.656 frame** il bit chiamato `GEAR_TYPE` coincide con `COUNTER & 1`.

| Richiesta potential | Contatore | Campioni | `MIN_TIME_FOR_DESIRED_GEAR` osservato |
|---|---|---:|---|
| 0, nessuna richiesta | Pari/dispari | 13.210 | Sempre `0.0` |
| 2, modalità frenata | Pari/dispari | 2.194 | Sempre `0.0` |
| 1, modalità GMP | Dispari | 3.126 | `6.2` in 3.121 frame; `0.0` in 5 |
| 1, modalità GMP | Pari | 3.126 | `1.2–2.5` in 3.115 frame; `6.2` in 6; `0.0` in 5 |

Il grafico a dente di sega collega campioni alternati, distanti circa 20 ms. Ogni parità costituisce una sequenza a circa 25 Hz. **È verificata l’alternanza; non è dimostrato che il bit sia un multiplexer né che il campo rappresenti due tempi di cambio.**

Non fissare `2.4` perché compare in una finestra. Non trasformare l’ipotesi di multiplexing in una modifica del DBC senza ulteriori riscontri.

### 1.6 Stato e display in `0x2F6`

- `ARC_STATUS`: valori osservati 6, 10, 12.
- `AUTO_BRAKING_STATUS`: valori 3, 5, 6, anche nel `0x2B6`.
- `AEB_ENABLED`: sempre 0 in questa route. Non dedurre la funzionalità AEB dalla combinazione dei nomi DBC.
- Senza target, 18.561 frame: distanza 255,5 e tempo display 6,2.
- Con target, 3.094 frame: distanza e tempo variano.
- `TARGET_POSITION`: **sempre 0**, anche con target.

Elkoled collega `modelV2.leadsV3[0].x[0] / (5 + vEgo)` a `self.bars`, con isteresi, e poi a `TARGET_POSITION`. È uno spunto per il display. La mappatura visiva non è verificata per questa Peugeot; il rapporto non è il tempo fisico `d/v`.

### 1.7 `0x452` e set speed

Il DBC attribuisce il `0x452` alla BSI. `carstate.py` legge `SPEED_SETPOINT` e `RVV_ACC_ACTIVATION_REQ` da questo messaggio.

Nelle tre prove precedenti delle route 36/38/39, durante 4,8 s di silenzio radar, arrivavano comunque 96 frame `0x452` sul bus 1, cioè 20 Hz. Il setpoint era 255 già prima della disattivazione. Erano prove da fermo, con ACC inattivo: non dimostrano la disponibilità del setpoint durante ogni stato di un futuro controllo attivo.

Per sostituire il radar non basta inviare un set speed: Sunnypilot deve produrre l’accelerazione richiesta e il port deve tradurla in richieste CAN di coppia/frenata. La prima versione non aggiunge un trasmettitore `0x452`.

### 1.8 Stato del codice e verifiche locali prima dell’implementazione

- I quattro costruttori generici sono già disponibili e ricevono bus/segnali espliciti.
- Il controller invia attualmente una prova neutra, dopo conferma programming e silenzio radar.
- `NeutralRadar` interrompe la prova se la vettura si muove. Questa regola è corretta per la prova parcheggiata; non può essere semplicemente mantenuta in un controllo longitudinale attivo.
- L’interfaccia corrente imposta `dashcamOnly=True`, `alphaLongitudinalAvailable=False`; il longitudinale openpilot non è abilitato.
- `psa_tx_hook` ammette gli ID radar, ma non verifica i valori longitudinali dei due messaggi. Anche il ramo laterale contiene un controllo che lascia `tx=true` in caso di violazione: è un problema preesistente da tenere distinto e non cambiare incidentalmente.
- Baseline eseguita: `python3 -m unittest opendbc.car.psa.tests.test_neutral_radar -q` → **16 test passati**.
- La suite pytest completa non è stata eseguita: `pytest` non è installato né nel Python di sistema né nella `.venv` verificata. Il test `test_synthetic_cruise_button_events_follow_stock_setpoint` richiama un metodo attualmente commentato: problema preesistente da affrontare esplicitamente se si modifica la gestione dei pulsanti.

## 2. Cosa recuperare da Elkoled

Recuperare lo schema generale: conversione accelerazione/coppia, distinzione GMP/frenata, stato cruise, messaggi a 50 Hz e idea del lead derivato dal modello.

Adattamenti necessari:

1. Usare `CC.longActive` e le condizioni del nostro controller per autorizzare le richieste, non soltanto `CS.out.cruiseState.enabled`.
2. Usare la stessa decisione di frenata nei due messaggi. Il caso Elkoled `enabled=False, braking=True` produce richiesta 0 in `0x2B6` e 1 in `0x2F6`.
3. Impostare tutti i campi: nel suo `0x2F6` distanza, ARC e stato frenata commentati diventano zero; tempo display è fisso a 5,0.
4. Passare esplicitamente contatore e bit alternato. L’argomento `frame` Elkoled è inutilizzato, ma il nostro CANPacker genera comunque contatori automatici se omessi: non si tratta di un contatore bloccato.
5. Gestire anche `0x4F6` e `0x796`, già presenti nella nostra prova neutra.
6. Non assumere validata la tabella coppia, la soglia di frenata, la compensazione della pendenza o il tempo cambio fisso.

## 3. Prima implementazione proposta

### 3.1 Procedere con un prototipo verificabile offline

Primo risultato concreto: generare comandi longitudinali dinamici nei test usando i costruttori esistenti, con parametri sperimentali identificati. Non aspettare la decodifica completa di ogni segnale per scrivere e testare il codice.

Il profilo iniziale riprende Elkoled come **ipotesi di lavoro**:

```python
ACCEL_LOOKUP = [-1.0, -0.5, 0.0, 0.5, 1.0, 1.5, 2.0]
TORQUE_LOOKUP = [-400, -300, 120, 350, 550, 800, 1000]
BRAKE_ACCEL_THRESHOLD = -0.5
MIN_TIME_GMP_EXPERIMENTAL = 6.2
MIN_TIME_INACTIVE_OR_BRAKING = 0.0
```

La tabella serve al prototipo; non convalida la risposta del veicolo. Il primo intervallo di prova numerica è `[-1.0, 2.0] m/s²`, con saturazione agli estremi. Le richieste fuori intervallo non devono andare in overflow nel CAN. Non estendere la frenata a valori più forti sulla base del solo commento Elkoled.

Nel prototipo i due campi coppia possono iniziare dalla stessa tabella, ma vanno rappresentati come due valori distinti: i dati mostrano che il controllo originale non li uguaglia. La calibrazione dei due campi è una voce di lavoro esplicita.

`MIN_TIME_GMP_EXPERIMENTAL=6.2` fisso è una semplificazione consapevole del prototipo, **non la ricostruzione del pattern originale**. I test devono dirlo e non chiamarla replica della bibbia. L’alternanza registrata resta un criterio di confronto da risolvere prima di dichiarare la fedeltà al radar.

### 3.2 Stati del controller

Separare disponibilità della sessione, engagement di Sunnypilot e modalità di attuazione:

| Condizione | Comportamento richiesto |
|---|---|
| Sessione non confermata | Nessun messaggio radar sostitutivo |
| Sessione pronta, longitudinale non attivo | Richieste longitudinali disabilitate, payload coerenti |
| `CC.longActive`, CAN valido, dati finiti, nessun override | GMP oppure frenata secondo il comando |
| Freno o acceleratore del conducente | Richieste di attuazione disabilitate in entrambi i messaggi |
| `CC.longActive=False`, NaN/inf o CAN invalido | Nessuna richiesta di coppia/frenata; azzerare memoria della richiesta |
| Sessione persa / radar originale tornato | Nessun invio concorrente con il radar; stato di indisponibilità visibile a Sunnypilot |

Una disattivazione del controllo non deve essere confusa con la chiusura della sessione diagnostica: normalmente si possono mantenere messaggi coerenti senza attuazione. La perdita della sessione o la ricomparsa del radar richiedono invece la gestione specifica della comunicazione.

La regola iniziale di override pedali è conservativa e intenzionale; non pretende di riprodurre lo stato Suspended originale, che nella route può mantenere richieste GMP.

### 3.3 Campi e frequenze

- `0x2B6`/`0x2F6`: 50 Hz, un solo blocco di emissione nel controller, contatore modulo 16 esplicito.
- `GEAR_TYPE = counter & 1`: riprodurre il bit osservato senza attribuirgli una semantica cambio non dimostrata.
- GMP: potential request 1, wheel request 1 nel primo profilo, decel request/type 0, decelerazione inattiva 2,05.
- Frenata ACC: potential request 2, wheel request 0, decel request/type 1, coppie inattive -4000. La richiesta frenata nel `0x2F6` deve coincidere con quella nel `0x2B6`.
- Inattivo: richieste 0, coppie -4000, decelerazione 2,05, min time 0.
- Per il prototipo tenere AEB/prefill/ripartenza disabilitati; non dichiarare funzioni implementate assegnando loro uno stato Active.
- `0x4F6` a 10 Hz e `0x796` a 1 Hz: continuare a generarli dal controller, inizialmente con il profilo neutro documentato.
- Il primo prototipo mantiene display e dati target neutri. Il display dal modello viene aggiunto come passo separato, con verifica propria.
- Nessuna modifica alla firma o alla responsabilità dei quattro costruttori `psacan.py`.

### 3.4 Inventario esplicito dei messaggi da sostituire senza radar

Quando ARTIV è confermato in programming e i suoi messaggi sono cessati, il controller deve produrre **tutti e quattro** questi ID. La tabella è l’inventario della sostituzione, non soltanto delle richieste di coppia/frenata.

| ID | Costruttore esistente in `psacan.py` | Bus / DLC | Frequenza | Responsabilità |
|---|---|---|---|---|
| `0x2B6` | `create_HS2_DYN1_MDD_ETAT_2B6` | 1 / 8 byte | 50 Hz | Stato ACC, richieste coppia e decelerazione |
| `0x2F6` | `create_HS2_DYN_MDD_ETAT_2F6` | 1 / 8 byte | 50 Hz | Stato radar/ACC, target/display, richiesta frenata e takeover |
| `0x4F6` | `create_HS2_DAT_ARTIV_V2_4F6` | 1 / 5 byte | 10 Hz | Stato sensore e dati di distanza/velocità relativa target |
| `0x796` | `create_HS2_SUPV_ARTIV_796` | 1 / 8 byte | 1 Hz | Supervisione ARTIV |

**`0x2B6`: valori decisi dal controller**

| Segnale | Inattivo / prova neutra | Prototipo attivo |
|---|---|---|
| `MDD_DESIRED_DECELERATION` | 2,05, codice inattivo | Accelerazione limitata quando è richiesta frenata; 2,05 in GMP |
| `POTENTIAL_WHEEL_TORQUE_REQUEST` | 0 | 1 in GMP, 2 in frenata |
| `MIN_TIME_FOR_DESIRED_GEAR` | 0 | 6,2 sperimentale in GMP; 0 in frenata |
| `GMP_POTENTIAL_WHEEL_TORQUE` | -4000, codice inattivo | Coppia potential sperimentale in GMP; -4000 in frenata |
| `GMP_WHEEL_TORQUE` | -4000, codice inattivo | Coppia wheel sperimentale in GMP; -4000 in frenata |
| `ACC_STATUS` | 2 nel profilo neutro iniziale | 4 durante attuazione autorizzata; 2 al rilascio delle richieste nel primo profilo |
| `WHEEL_TORQUE_REQUEST` | 0 | 1 in GMP nel primo profilo; 0 in frenata. Modalità 2 da calibrare |
| `AUTO_BRAKING_STATUS` | 3 | 3 nel primo profilo senza AEB; non dichiarare AEB attivo |
| `MDD_DECEL_TYPE` | 0 | 1 soltanto per frenata ACC |
| `MDD_DECEL_CONTROL_REQ` | 0 | 1 soltanto per frenata ACC autorizzata |
| `GEAR_TYPE` | `counter & 1` | Stesso bit alternato osservato |
| `PREFILL_REQUEST` | 0 | 0: prefill non implementato |
| `COUNTER` | Modulo 16 | Modulo 16, deciso dal controller |
| `CHECKSUM` | Calcolato dal packer | Calcolato dal packer; somma nibble modulo 16 = `0xC` |

**`0x2F6`: un solo messaggio per stato, display e takeover**

| Segnale | Prima versione | Evoluzione prevista |
|---|---|---|
| `TARGET_DETECTED` | 0 | Lead valido del modello, coordinato con `0x4F6` |
| `INTER_VEHICLE_DISTANCE` | 255,5, sentinella senza target | Distanza modello valida, saturata al range utile |
| `DISPLAY_INTERVEHICLE_TIME` | 6,2, sentinella senza target | Tempo derivato dal target, dopo verifica della semantica |
| `TARGET_POSITION` | 0 | Posizione display solo dopo verifica sulla vettura |
| `REQUEST_TAKEOVER` | 0 nella prova neutra; richiesta del controller nel profilo longitudinale | Integrare gli avvisi laterali esistenti nello stesso frame |
| `MDD_DECEL_CONTROL_REQ` | Stessa decisione autorizzata del `0x2B6` | Mai un booleano `braking` indipendente dall’abilitazione |
| `ARC_STATUS` | 6, come profilo neutro | Stati ulteriori solo per funzioni realmente implementate e verificate |
| `AUTO_BRAKING_STATUS` | 3, coerente con `0x2B6` | Non copiare 5/6 dai log come prova di AEB funzionante |
| `AEB_ENABLED`, `AUTO_BRAKING_IN_PROGRESS` | 0 | AEB fuori dalla prima implementazione |
| `DRIVE_AWAY_REQUEST` | 0 | Ripartenza automatica da sviluppare e verificare separatamente |
| `BLIND_SENSOR` | 0 nel profilo iniziale | Gestire il guasto dal percorso di disponibilità/sessione |
| `REQ_VISUAL_COLL_ALERT_ARC`, `REQ_AUDIO_COLL_ALERT_ARC`, `REQ_HAPTIC_COLL_ALERT_ARC` | 0 | Allarmi collisione fuori dalla prima implementazione |
| `COUNTER` | Modulo 16, esplicito | Una sola sequenza per tutte le funzioni nel frame |
| `CHECKSUM` | Calcolato dal packer | Somma nibble modulo 16 = `0x8` |

**`0x4F6`: stato sensore e target**

- `TIME_GAP=25.5`, `DISTANCE_GAP=254`, `RELATIVE_SPEED=93.8`: codici senza target osservati nella prova neutra; non valori fisici da interpretare come un veicolo a quella distanza/velocità.
- `ARTIV_SENSOR_STATE=2`, `TARGET_DETECTED=0`, `ARTIV_TARGET_CHANGE_INFO=0`, `TRAFFIC_DIRECTION=0` nel primo profilo.
- Nel passo display/lead, aggiornare i tre dati cinematici e il target soltanto con informazioni valide e unità verificate; tornare alle sentinelle alla perdita del target.
- Il DBC attuale non definisce contatore o checksum per questo ID: non aggiungerli arbitrariamente.

**`0x796`: supervisione**

- Nel primo profilo: `FAULT_CODE=0`, `STATUS_NO_CONFIG=0`, `STATUS_PARTIAL_WAKEUP_GMP=0`, `UCE_ELECTR_STATE=0`, come nel payload neutro registrato.
- Nessun contatore/checksum definito nel DBC. La risposta degli altri ECU a questo profilo di supervisione deve essere verificata; il payload non garantisce da solo l’assenza di errori.

**Diagnostica necessaria alla sessione, distinta dai quattro ID sostitutivi**

- TX `0x6B6`, bus 1, DLC 3: `02 10 02` per richiedere programming dopo la condizione iniziale prevista.
- RX `0x696`: conferma `06 50 02 00 C8 00 14` osservata; validare struttura e servizio, non inventare una ricezione.
- TX `0x6B6`, bus 1, DLC 3: `02 3E 00` a 1 Hz durante la sessione, con riscontro RX `02 7E 00` atteso su `0x696`.
- Timeout, rifiuti e ritorno del radar restano responsabilità del gestore di sessione.

`0x452` rimane una sorgente BSI ricevuta, non un messaggio radar da sostituire. Il controller continua a ricevere anche velocità ruote, freni, pedali e stati delle altre centraline.

### 3.5 Takeover integrato e assenza di doppioni `0x2F6`

Osservazione di Cristian: eliminando il `0x2F6` originale del radar si può inserire la richiesta takeover direttamente nel nostro frame periodico. È il comportamento da implementare.

- Con emulazione attiva, `create_HS2_DYN_MDD_ETAT_2F6` è **l’unico produttore** di `0x2F6` nel controller.
- Inserire `self.takeover_req` in `request_takeover` dello stesso frame che contiene stato, frenata e display.
- Non chiamare anche `create_request_takeover(...)` e non copiare un vecchio `CS.HS2_DYN_MDD_ETAT_2F6` del radar disattivato.
- La richiesta takeover può provenire dal controllo laterale anche con `CC.longActive=False`: non deve abilitare coppia o frenata.
- Nella prima integrazione preservare i due invii a 50 Hz del ramo takeover attuale, incrementando il contatore ripetizioni solo quando il frame unico è realmente generato. Non estendere incidentalmente la durata dell’avviso.
- L’attuale prova neutra mantiene `REQUEST_TAKEOVER=0`; il profilo longitudinale integra la richiesta esistente. Il comportamento delle altre PSA resta invariato.
- La garanzia di sorgente unica vale dopo la conferma del silenzio radar e finché il gestore non ne rileva il ritorno. Non dedurla dalla sola emissione di `02 10 02`.

Test specifico: in 100 cicli controller devono essere prodotti 50 frame `0x2F6`, sia senza takeover sia con takeover richiesto; stesso contatore continuo, nessun frame supplementare. Verificare che esattamente le emissioni previste contengano il valore richiesto e che i campi longitudinali siano invariati.

### 3.6 Set speed e parametri Sunnypilot

Per la prima integrazione mantenere `pcmCruise=True` e `pcmCruiseSpeed=True`: usare il setpoint BSI letto dal `0x452`, che alimenta il set speed utilizzato da Sunnypilot. Il controller riceve `CC.actuators.accel`, non deve calcolare da solo una legge di inseguimento della velocità.

Gestire il valore 255 come indisponibile, non come 255 km/h; preservare la semantica di inizializzazione usata da Sunnypilot. Verificare la continuità del setpoint e della richiesta di engagement con radar sostituito. Se questa sorgente non è utilizzabile, la gestione autonoma del set speed/pulsanti richiede una revisione esplicita di questa scelta.

L’ordine iniziale prevedeva l’abilitazione alla fine. La successiva richiesta esplicita di Cristian («abilitalo») anticipa questo collegamento: `alpha_long`, rimozione di `dashcamOnly` nel solo profilo sperimentale e flag safety ora sono collegati, dopo i test di sessione e safety. Senza `alpha_long` il default resta quello precedente. Guadagni longitudinali, ritardo attuazione, arresto e ripartenza devono essere scelti e verificati esplicitamente: i default generici dell’interfaccia non costituiscono una calibrazione PSA.

## 4. Sequenza di implementazione e test

Tutti i percorsi di codice seguenti sono relativi al repository opendbc. I test nuovi usano `unittest`, già disponibile. Per ogni passo: scrivere il test, osservarne il fallimento per il comportamento mancante, implementare, eseguire il test e le regressioni pertinenti. Eseguire nella stessa sessione, senza commit o push automatici.

### Passo 1 — Fixture originali e confronto riproducibile

**File:** nuovi `opendbc/car/psa/tests/test_longitudinal.py` e `opendbc/car/psa/tests/fixtures/longitudinal_reference.json`.

**Input:** i rlog originali della bibbia. **Output:** pochi esempi con route, segmento, tempo monotono, bus, byte e segnali; non incorporare l’intera route nei test.

- [x] Selezionare campioni Inhibited, Waiting, GMP high/low range, frenata, Suspended e target presente/assente, includendo entrambe le parità.
- [x] Verificare nei test la ricodifica esatta dei payload attraverso i costruttori attuali.
- [x] Aggiungere asserzioni indipendenti sui byte noti per evitare che un errore comune a packer/parser passi inosservato.
- [x] Conservare la distinzione tra prova della codifica e prova della logica: questo test può già passare perché i costruttori esistono.

Esempio di asserzione sul riferimento:

```python
self.assertEqual(encoded[0], sample["address"])
self.assertEqual(encoded[1].hex(), sample["payload_hex"])
self.assertEqual(encoded[2], 1)
```

**Completato quando:** ogni campione riproduce i byte originali e conserva la propria provenienza verificabile.

### Passo 2 — Comandi dinamici locali nel CarController

**File:** `opendbc/car/psa/carcontroller.py`, `opendbc/car/psa/values.py`, `opendbc/car/psa/tests/test_longitudinal.py`.

**Interfaccia proposta:** metodo privato `_update_longitudinal(self, CC, CS) -> None` nel controller, che aggiorna i valori di comando prima della costruzione dei messaggi. Nessun CAN viene generato dal metodo: l’emissione resta nel blocco temporizzato esistente.

**Stato prodotto:** `longitudinal_active`, `longitudinal_braking`, `longitudinal_accel`, `longitudinal_potential_torque`, `longitudinal_wheel_torque`, `longitudinal_min_time`. Questi valori alimentano esplicitamente i due costruttori. Reset dei valori inattivi a ogni aggiornamento, prima di valutare le condizioni di attuazione.

- [x] Scrivere i test di disattivazione e override prima della mappatura accelerazione/coppia.
- [x] Implementare la tabella sperimentale e il clamp numerico nel controller usando costanti in `values.py`.
- [x] Calcolare un’unica decisione GMP/frenata per i due messaggi.
- [x] Iniziare senza compensazione di pendenza; aggiungerla solo con un test che chiarisca segno, unità e interazione con l’accelerazione richiesta da Sunnypilot.
- [x] Collegare i valori ai costruttori nel ramo sperimentale; mantenere i byte della prova neutra nel ramo attuale.
- [x] Integrare `REQUEST_TAKEOVER` nel solo `0x2F6` periodico del profilo longitudinale ed escludere lì il secondo invio legacy, come specificato nella sezione 3.5.
- [x] Aggiornare `actuatorsOutput.accel` con la richiesta effettivamente limitata/annullata, senza presentarla come accelerazione misurata.

| Test | Risultato atteso |
|---|---|
| Cruise originale enabled, `CC.longActive=False` | Nessuna richiesta fisica |
| `CC.longActive=True`, accel 0,5 | GMP; torque sperimentale 350 Nm, potential quantizzato a 352 Nm |
| `CC.longActive=True`, accel -0,75 | Frenata ACC; richiesta presente in entrambi gli ID |
| `CC.longActive=False`, accel -0,75 | Richiesta assente in entrambi gli ID |
| Acceleratore/freno premuto | Richieste disabilitate, senza residuo del ciclo precedente |
| NaN, +inf, -inf | Payload inattivo; nessuna eccezione/overflow |
| Accel oltre gli estremi della tabella | Clamp coerente e verificabile |
| 32 emissioni | Due cicli contatore, checksum validi, bit alternato corretto |
| Takeover laterale con longitudinale disattivo | Avviso nello stesso `0x2F6`, richieste coppia/frenata a zero |
| Takeover durante frenata autorizzata | Un solo `0x2F6`, avviso e richiesta frenata coerenti |
| 100 cicli con takeover | Esattamente 50 frame `0x2F6`, senza doppioni o salti introdotti nel contatore |

**Comando:** `python3 -m unittest opendbc.car.psa.tests.test_longitudinal -v`.

**Completato quando:** i test dimostrano disattivazione, override, limiti e coerenza dei messaggi; le 16 regressioni della prova neutra restano verdi. Questo passo produce un prototipo offline, non una calibrazione completata.

### Passo 3 — Sessione ARTIV utilizzabile dal controllo attivo

**File:** `opendbc/car/psa/neutral_radar.py`, `carcontroller.py`, `interface.py`, nuovi test `test_longitudinal_session.py`; conservare `test_neutral_radar.py`.

**Interfaccia proposta:** estendere il gestore esistente con `stationary_only: bool = True`; `update(frame, now_nanos, stationary, can_valid=True)` e `process_can(can_packets)` conservano il contratto. Il controller imposta `stationary_only=False` esclusivamente per il profilo longitudinale sperimentale. Il nome può essere generalizzato solo se necessario, aggiornando tutti i riferimenti e i test nello stesso passo.

- [x] Conservare l’avvio a vettura ferma e CAN valido, risposta `50 02` e almeno 100 ms senza i quattro ID originali.
- [x] Consentire il movimento dopo la conferma solo nel profilo attivo; la prova neutra deve continuare a interrompersi quando l’auto si muove.
- [x] Conservare timeout di bus, echi e diagnostica, e blocco immediato della sovrapposizione con il radar originale.
- [x] Separare disattivazione del cruise da perdita della sessione: nel primo caso mantenere messaggi senza richieste; nel secondo interrompere la sostituzione ed esporre l’indisponibilità.
- [x] Esporre il guasto attraverso il percorso `CarState`/eventi compatibile con Sunnypilot, verificando il segnale letto da `selfdrived`. Non usare soltanto un messaggio di log.
- [x] Definire e testare cosa accade a una frenata in corso quando scade la sessione: non dedurre dai log parcheggiati un rilascio o un passaggio al radar senza conseguenze.

**Test obbligatori:** nessuna risposta; risposta stale/negativa; eco rifiutato src 193; eco reale src 129; movimento nei due profili; ritorno radar; scadenza TesterPresent; CAN invalido; disengagement e successivo engagement con sessione valida.

**Comando:** `python3 -m unittest opendbc.car.psa.tests.test_neutral_radar opendbc.car.psa.tests.test_longitudinal_session -v`.

**Completato quando:** il controllo attivo non eredita lo stop al primo movimento e nessun errore di sessione permette richieste o trasmissioni concorrenti non gestite.

### Passo 4 — Safety longitudinale indipendente

**File:** `opendbc/safety/modes/psa.h`, `opendbc/safety/tests/test_psa.py` oppure un modulo dedicato `test_psa_longitudinal.py`, `opendbc/car/psa/values.py` per il flag condiviso.

**Interfaccia proposta:** flag `PSA_LONG_CONTROL = 1` nel `safetyParam`, attualmente ignorato dalla safety PSA. Verificarne l’assenza di conflitti prima di assegnarlo. L’abilitazione delle richieste richiede il flag e `longitudinal_allowed`; i messaggi neutri restano ammessi senza il flag.

- [x] Scrivere prima il test che dimostri il rifiuto di una richiesta attiva con controlli non consentiti.
- [x] Controllare raw values e flag di `0x2B6`: range coppia/decelerazione, sentinelle inattive, richieste incompatibili, prefill e tipo frenata non implementato.
- [x] Controllare la richiesta frenata del `0x2F6` con gli stessi criteri di abilitazione; rifiutare ripartenza/AEB non implementati.
- [x] Consentire i valori takeover previsti senza richiedere che il longitudinale sia attivo, preservando però il blocco delle richieste fisiche non autorizzate.
- [x] Conservare contatori/checksum validi anche quando i valori sono inattivi.
- [x] Testare i confini dell’intervallo sperimentale, entrambi i pedali e controlli disabilitati.
- [x] Verificare l’ordine di emissione e la coerenza fra i due ID senza imporre alla ricezione simultaneità impossibile sul CAN.
- [x] Verificare i payload realmente prodotti dal controller contro libsafety, evitando fixture che non corrispondano alla produzione.

Esempio di criterio da codificare nel test C/Python:

```python
self.safety.set_controls_allowed(False)
self.assertFalse(self._tx(active_gmp_message))
self.assertFalse(self._tx(active_brake_message))
self.assertTrue(self._tx(neutral_message))
```

**Comando futuro:** `python3 -m unittest opendbc.safety.tests.test_psa_longitudinal -v` se si sceglie il modulo dedicato. Il caricamento libsafety compila codice C localmente; non compila o installa sul comma.

**Completato quando:** i payload vietati sono rifiutati indipendentemente dal controller e quelli inattivi continuano a passare. Eventuali problemi preesistenti laterali sono riportati separatamente, senza mascherare i risultati.

### Passo 5 — Calibrazione e risoluzione dei campi sperimentali

**File:** test/fixture del passo 1, `values.py`, `carcontroller.py`; findings e confronto in questa cartella.

- [ ] Separare i frame per parità e controllare quali altri campi seguano il ciclo pari/dispari; verificare `MIN_TIME_FOR_DESIRED_GEAR` anche nelle transizioni GMP/frenata e nei pochi valori eccezionali.
- [ ] Correlare i due campi coppia con richiesta high/low range, accelerazione misurata, velocità, marcia e pedali; rispettare i timestamp e distinguere Nm motore/Nm ruota.
- [ ] Sostituire l’uguaglianza sperimentale delle due coppie solo con una regola motivata dai dati o da una prova specifica di Cristian.
- [ ] Determinare ritardo e risposta nella regione coperta dalla route; non estrapolare la frenata forte dalla minima osservata di -0,8 m/s².
- [ ] Introdurre limiti di variazione e isteresi GMP/frenata misurati; testare inversioni del comando e campioni alla soglia -0,5.
- [ ] Definire arresto, mantenimento e ripartenza come comportamenti separati. La ripartenza resta disabilitata finché non esiste un caso di riferimento e una verifica specifica.
- [ ] Registrare per ogni costante origine, unità, range e condizioni testate. `6.2` fisso e tabella Elkoled restano esplicitamente sperimentali se non sostituiti.

**Completato quando:** il rapporto distingue la parte implementata e verificata da quella ancora sperimentale. Un test che conferma la formula scelta non deve essere presentato come validazione della formula sul veicolo.

### Passo 6 — Collegamento ai parametri e al set speed Sunnypilot

**File:** `opendbc/car/psa/interface.py`, `carstate.py`, test parametri/integrati.

- [x] Abilitare `alphaLongitudinalAvailable` solo per Peugeot 3008 e collegare `alpha_long`, `openpilotLongitudinalControl` e flag safety nello stesso ramo.
- [x] Mantenere il comportamento preesistente quando l’opzione non è selezionata.
- [x] Rendere coerenti `dashcamOnly`/passive mode e l’abilitazione richiesta: il profilo dashcam non deve trasmettere comandi longitudinali attivi anche se riceve per errore `CC.longActive=True`.
- [ ] Impostare tuning, ritardo e gestione stopping a partire dal passo 5. Controllare i parametri effettivamente letti da Sunnypilot, non solo quelli restituiti dall’interfaccia locale.
- [ ] Gestire il setpoint BSI indisponibile (255), la sua inizializzazione e i cambi tramite pulsanti senza feedback da messaggi da noi trasmessi.
- [ ] Verificare che invalidità della sessione generi disengagement/indisponibilità nell’integrazione Sunnypilot.
- [ ] Se si passa al set speed autonomo, aggiornare esplicitamente il piano e i test dei pulsanti prima di cambiare `pcmCruiseSpeed`.

**Test parametri:** default, opzione attiva, dashcam/passive, altra PSA, setpoint valido/0/255, perdita setpoint, perdita sessione. **Test integrazione:** `CarInterface` riceve CAN fisico ed echi e produce lo stato coerente con i comandi del controller.

**Completato quando:** selezione del profilo, stato cruise, planner, controller e safety concordano sull’abilitazione. Nessuna rigenerazione o installazione openpilot è implicita in questo passo.

### Passo 7 — Display basato sul modello

**File:** `carcontroller.py`, `tests/test_longitudinal_display.py`; utilizzare il `model_sm` già presente.

**Interfaccia proposta:** `_update_longitudinal_display(self, CC, CS, now_nanos) -> None`, produce distanza/tempo/target e posizione per il blocco CAN; nessun invio dentro il metodo.

- [ ] Leggere lead del modello soltanto se aggiornato, valido e con valori finiti; controllare anche probabilità e disponibilità.
- [ ] Resettare target/distanza/tempo alle sentinelle quando il dato scade o il lead scompare. Non mantenere l’ultima posizione per un lead non valido.
- [ ] Separare il rapporto euristico Elkoled dalla distanza in metri e dal tempo interveicolare: non scrivere lo stesso numero in segnali con unità diverse.
- [ ] Preparare nei test la quantizzazione/isteresi Elkoled, lasciando `TARGET_POSITION=0` nel profilo iniziale finché Cristian non ne verifica la mappatura sul display.
- [ ] Coordinare i dati target fra `0x2F6` e `0x4F6`; non inventare una velocità relativa se il modello non fornisce un dato valido.

**Test:** acquisizione/perdita lead, dati stale/NaN, distanza negativa, velocità zero, attraversamento delle soglie e limitazione ai range DBC.

**Completato quando:** la codifica è corretta e il comportamento visivo verificato da Cristian è documentato separatamente. La visualizzazione non abilita AEB o richieste di frenata.

## 5. Verifica finale e consegna

- [x] Rieseguire test nuovi e regressioni PSA pertinenti; riportare separatamente fallimenti preesistenti o verifiche non eseguite.
- [x] Replay dei campioni originali per la codifica e scenari sintetici per le richieste nuove: sono due verifiche diverse.
- [x] Verificare assenza di modifiche al repository Elkoled e assenza di operazioni sul dispositivo.
- [x] Mantenere [NEUTRAL_RADAR.md](NEUTRAL_RADAR.md) e [LONGITUDINAL.md](LONGITUDINAL.md) in `openpilot_scripts/plans/longitudinal/` con profili, limiti, ipotesi sperimentali, risultati e istruzioni per leggere i log.
- [ ] Consegnare diff locale, test eseguiti e limiti noti. Dichiarare quale parte è pronta offline e quale non è stata provata sul veicolo.
- [ ] Cristian decide ed esegue installazione e prove. I nuovi log vengono analizzati solo dopo la sua richiesta, conservando gli originali e confrontandoli con la bibbia.

La prima consegna implementativa è il generatore dinamico offline dei passi 1–2. Il controllo longitudinale completo richiede anche sessione, safety, calibrazione e integrazione dei passi 3–6. Il display del passo 7 è indipendente dalla capacità di attuazione e può essere completato successivamente.

## Allegati

- [Findings del confronto con Elkoled](findings-dashcam.json): conteggi, campioni originali, distribuzioni e casi di codifica sperimentale.
- [Distribuzione min-time per parità](findings-min-time-parity.json): dati numerici dell’alternanza.
- [Archivio della bibbia](../../log_analysis/dashcam_mode_bibbia_longitudinale/0000003a--e445e79563/): rlog/qlog originali, checksum e verifica di acquisizione.

Gli allegati sono snapshot dell’analisi offline; gli originali della route restano la fonte primaria. Le etichette DBC nei findings sono interpretazioni da verificare, non una specifica ufficiale PSA.
