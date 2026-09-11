# Prototipo longitudinale PSA — Peugeot 3008

Stato all’11 settembre 2026: implementati e verificati **offline i passi 1–4**
del [piano](PLAN.md).
Su richiesta esplicita di Cristian («abilitalo»), l’interfaccia ora espone
`alphaLongitudinalAvailable=True` soltanto per Peugeot 3008. Con `alpha_long=True`
imposta `openpilotLongitudinalControl=True`, `dashcamOnly=False` e il flag safety
`PSA_LONG_CONTROL`. Senza selezione conserva il profilo dashcam precedente.
L’abilitazione anticipa la calibrazione: mapping coppia e min-time restano sperimentali.
La modalità passive scelta da Sunnypilot continua a inibire i comandi.

## Riferimento e responsabilità

La [bibbia dashcam](../../log_analysis/dashcam_mode_bibbia_longitudinale/)
contiene la route `6616faac453a3064/0000003a--e445e79563`, registrata con il
longitudinale originale in funzione. Le 16 fixture in
[fixture CAN](../../../opendbc/opendbc/car/psa/tests/fixtures/longitudinal_reference.json) conservano segmento, timestamp,
bus, payload originale e segnali dei casi GMP, frenata, inattività e target.
I test ricodificano quei byte e controllano checksum, contatore e bit alternato.
Questa verifica dimostra la codifica; non convalida la conversione accelerazione/coppia.

`CarController` decide condizioni, valori, frequenze e contatori.
`psacan.py` continua a codificare i singoli messaggi con tutti gli ingressi
espliciti. `NeutralRadar` verifica la sessione. La safety C controlla i
payload trasmessi indipendentemente dalla logica Python.

## Quattro messaggi sostitutivi

| ID | Bus / DLC | Frequenza | Contenuto del prototipo |
|---|---|---|---|
| `0x2B6` | 1 / 8 | 50 Hz | Richieste GMP oppure frenata, stato ACC, contatore e checksum |
| `0x2F6` | 1 / 8 | 50 Hz | Stessa decisione frenata; takeover laterale nel medesimo frame |
| `0x4F6` | 1 / 5 | 10 Hz | Stato sensore e sentinelle senza target della prova neutra |
| `0x796` | 1 / 8 | 1 Hz | Supervisione con il payload neutro registrato |

Non viene aggiunto un TX `0x452`: il setpoint resta una sorgente BSI ricevuta.
Il trattamento del valore indisponibile 255 e la sua continuità con radar
sostituito fanno parte del passo 6 ancora aperto.

Il takeover compare per due emissioni consecutive del solo `0x2F6` periodico,
poi viene azzerato. Funziona anche con `CC.longActive=False` e non abilita
richieste fisiche. La prova neutra mantiene il takeover a zero.

## Abilitazione e sessione

Una richiesta fisica richiede simultaneamente Peugeot 3008,
`openpilotLongitudinalControl=True`, assenza di dashcam/passive, safety PSA
con bit `PSA_LONG_CONTROL=1`, sessione attiva, `CC.enabled`, `CC.longActive`,
CAN valido, accelerazione finita e nessun pedale premuto.

Ogni aggiornamento riparte dai valori inattivi: coppie -4000, decelerazione
2,05, richieste e min-time a zero. Il controller espone in
`actuatorsOutput.accel` la richiesta limitata oppure zero se inibita;
non è una misura della risposta fisica né la conferma TX del Panda.

La sessione parte ancora dopo 10 s consecutivi da fermo con CAN valido,
risposta programming effettiva e almeno 100 ms di silenzio radar.
Soltanto il profilo sperimentale già attivo può proseguire in movimento.
Disengagement e pedali annullano le richieste mantenendo la sessione.
Il ritorno del radar, i rifiuti diagnostici e i timeout fermano invece tutti
i sostituti e TesterPresent, senza retry. `CarInterface` espone
`accFaulted=True`, cruise non disponibile e non enabled al successivo update.
Il percorso `selfdrived` di Sunnypilot associa `accFaulted` a disattivazione
immediata; l’integrazione end-to-end resta da provare nel passo 6.
Riscontro nel checkout `new_openpilot_psa_torque_sunny_testing`, commit
`f544c80ffeb669ff5e5bcbbc372e610c6eb04898`: `openpilot/selfdrive/car/car_events.py`
e `openpilot/selfdrive/selfdrived/events.py`.

Durante una frenata, la perdita di sessione interrompe gli invii e azzera la
richiesta riportata. Questo comportamento software è testato; la persistenza
dell’ultimo comando nelle ECU e il ritorno del radar non sono verificati in moto.

## Mapping sperimentale e safety

Le costanti in `values.py` provengono dal prototipo incompleto Elkoled:

| Accelerazione richiesta, m/s² | -1 | -0,5 | 0 | 0,5 | 1 | 1,5 | 2 |
|---|---:|---:|---:|---:|---:|---:|---:|
| Coppia della tabella, Nm secondo DBC | -400 | -300 | 120 | 350 | 550 | 800 | 1000 |

La richiesta viene limitata a [-1, 2]. Sotto -0,5 si usa frenata ACC:
potential request 2, wheel request 0, decel type/request 1 e coppie inattive.
Altrimenti si interpola la tabella: entrambe le richieste GMP valgono 1,
decelerazione inattiva e min-time fisso 6,2. Non c’è compensazione di pendenza.

I due campi coppia ricevono inizialmente lo stesso valore, ma il potential
ha risoluzione 4 Nm: 350 viene codificato come 352. Nei log originali i due
campi differiscono molto più della quantizzazione: l’uguaglianza è soltanto
un’ipotesi del prototipo. Anche il min-time fisso **non riproduce** l’alternanza
6,2/1,2–2,5 osservata. `GEAR_TYPE=counter & 1` riproduce il bit registrato,
senza attribuirgli una semantica cambio dimostrata.

La safety richiede flag e controlli consentiti, senza gas o freno, per le
richieste fisiche. Verifica i due campi coppia separatamente entro [-400, 1000]
Nm, decelerazione entro [-1, -0,5], sentinelle, combinazioni di richieste,
checksum, parità del bit e assenza di prefill/AEB/ripartenza implementabili
dal prototipo. Il limite -0,5 in frenata include l’arrotondamento di richieste
appena sotto la soglia. Questi sono limiti software sperimentali.

Il filtro dei payload TX radar vale nella safety PSA anche senza il nuovo
flag: i payload neutri passano; le richieste fisiche vengono rifiutate.
Di conseguenza anche un takeover legacy che ricopia dal radar un `0x2F6`
con richiesta frenata/AEB/ripartenza può essere rifiutato. I test laterali
Python restano invariati; ciò non dimostra l’invarianza di ogni avviso stock.
Il preesistente controllo safety dello sterzo non viene corretto da questo lavoro.

I due ID sono controllati singolarmente dalla safety: non c’è una transazione
atomica CAN fra loro. I test del controller verificano ordine `0x2B6`, `0x2F6`
e decisione frenata coerente, inclusi takeover e transizioni.

## Verifiche riproducibili

```sh
python3 -m unittest opendbc.car.psa.tests.test_longitudinal opendbc.car.psa.tests.test_longitudinal_session opendbc.car.psa.tests.test_neutral_radar opendbc.safety.tests.test_psa_longitudinal -q
```

Risultato: **43 test passati**, compresi i 16 della prova neutra. I test safety
compilano e caricano libsafety C sul Mac. Ruff passa sui sette file Python
aggiunti/modificati; `git diff --check` verifica il diff.

La suite safety PSA esistente esegue 67 test: 45 passati, 12 saltati e
10 fallimenti. Lo stesso risultato, con gli stessi test falliti, è stato
riprodotto su una copia temporanea del commit precedente
`74bfc461d37621ac2ffcd0939425fe9fb081e1d7`.
Le 33 funzioni test del port PSA, eseguite direttamente perché pytest non è
installato, danno 32 passati e il medesimo errore preesistente su
`_update_cruise_button_events`, sia prima sia dopo queste modifiche.
La suite pytest completa non è stata eseguita.

## Lavoro ancora aperto

- Passo 5: identificare min-time e due coppie; calibrare ritardo, risposta,
  limiti di variazione, isteresi, arresto e mantenimento. La bibbia arriva
  soltanto a -0,8 m/s² di frenata osservata; non valida frenate forti.
- Passo 6, parzialmente completato: `alpha_long` e flag safety sono collegati
  ai parametri reali e testati fino alla generazione dei comandi. Restano tuning,
  gestione setpoint 255 e verifica dell’integrazione completa con Sunnypilot.
- Passo 7: lead dal modello con validità/scadenza e dati coerenti nei due
  messaggi display. `TARGET_POSITION` resta zero finché la mappatura visiva
  non è verificata. AEB, prefill e ripartenza automatica restano disabilitati.

Nessuna installazione, aggiornamento, riavvio o prova sul comma fa parte di
questa consegna. Il repository Elkoled è stato consultato soltanto in lettura.
