# Findings test2 — retro, primo movimento e fault radar

## Esito

La route `6616faac453a3064/00000040--fa1066f2c5` conferma la sequenza descritta da Cristian: avvio dei sostituti senza fault, inserimento della retro senza fault, errore dopo il primo movimento. **Il movimento provoca lo stop esplicito del nostro profilo neutro**, con log `ARTIV neutral: stopped (vehicle moved); no automatic retry`. Cessano sostituti e TesterPresent; circa 120 ms dopo lo stato `32D` della vettura segnala il fault, seguito dal journal `76D`.

La causa dello stop è la condizione `standstill=false`, non la selezione della retromarcia. Nel codice questa condizione vale per il profilo neutro anche in avanti; questa registrazione documenta concretamente solo la manovra in retro.

## Acquisizione e riferimenti

- [Log originali test2](../../log_analysis/logitudinal_tests/test2/00000040--fa1066f2c5/): un segmento, 1 rlog + 1 qlog, **6.812.570 byte** complessivi. Selezionata la route con contatore più alto disponibile (`0x40`); le date civili dei file sul comma sono incoerenti.
- [Manifest SHA256](../../log_analysis/logitudinal_tests/test2/00000040--fa1066f2c5/SHA256SUMS.remote) e [verifica acquisizione](../../log_analysis/logitudinal_tests/test2/00000040--fa1066f2c5/acquisition_verification.json). Hash remoti stabili prima e dopo la copia e identici a quelli locali. Decodifica completa: **76.607 eventi rlog**, **12.672 eventi qlog**; entrambi contengono `startOfRoute` ed `endOfRoute`.
- [Script e risultati](findings-test2-20260912/): `analyze_test2.py`, `test2.json`, `summary.json`, `summary.txt` e `provenance.json`. I JSON contengono i campioni carState, CAN selezionati, transizioni e conteggi; gli originali restano il riferimento integrale.
- Versione da initData: openpilot **`81854c4da1ca9793d2c73911df38fa84b7e1fc69`**. In lettura SSH il checkout opendbc è **`fd64d7e9b6cd6335667eff1530815b574edbef37`**, lo stesso gitlink dell’openpilot registrato.
- Durata relativa all’evento iniziale letto: circa **44,943 s**. I tempi sotto sono `logMonoTime` relativi a quell’evento; alcuni eventi iniziali del file hanno timestamp leggermente precedente, conservato negli estratti.

CarParams: `dashcamOnly=false`, `passive=false`, `openpilotLongitudinalControl=false`, `pcmCruise=true`, `safetyParam=0`. Nessun `carControl.longActive=true`. Il profilo effettivo è **parked neutral trial**.

## Cronologia osservata

| Tempo, s | Evento |
|---:|---|
| 17,151465 | Richiesta programming `6B6: 02 10 02` |
| 17,218446 | Risposta positiva `696: 06 50 02 00 C8 00 14` |
| 17,221701 | Primo invio dei quattro sostituti |
| 17,240213 | Primi echi TX sul bus 1, src129 |
| 29,727529 | `gearShifter=reverse`, vettura ferma, CAN valido, `accFaulted=false` |
| 34,167146 | Rilascio freno, ancora ferma e senza fault |
| 35,542442 | `gasPressed=true`, ancora ferma e senza fault |
| 36,044895 | `gasPressed=false`, ancora ferma e senza fault |
| 36,519442 | Ultimo invio `2B6`, `2F6`, `4F6` |
| 36,528363 | Primo `standstill=false`: `vEgoRaw=0,038194 m/s`, circa **0,1375 km/h**; retro ancora inserita |
| 36,536026 | Log esplicito `stopped (vehicle moved); no automatic retry` |
| 36,536254 | Ultimi echi dei sostituti veloci già accodati prima dello stop |
| 36,656349 | `32D.ACC_ETAT_DECEL_OR_ESP_STATUS=3`; anche `FA_ETAT_DECEL=3`, `DEFAUT_ACC_FREIN=0` |
| 36,657973 | `carState.accFaulted=true` |
| 36,660810 | Avviso `Cruise Fault: Restart the car to engage` |
| 36,695658 | `76D` registra `99 D1 62 87 03 BF 1E 95`: `U1162:87`, stato JDD 1 secondo la decodifica già documentata |
| 36,747923 | `canValid=false` |
| 37,310417 | La vettura torna ferma; la sessione non riparte |
| 37,744657 | Avviso `canError/permanent`, testo UI `Unknown Vehicle Variant` |
| 41,429161 | Tornano `2B6`/`2F6` originali |
| 41,431158 | `canValid=true` |
| 44,883735 | `accFaulted=false` verso la fine della registrazione |

Al primo campione di movimento il gas risulta già rilasciato e il freno risulta premuto. Questo dettaglio non cambia il trigger: il codice interrompe la sessione quando perde lo stato di fermo, non quando rileva il pedale o la retro.

## Catena nel codice della prova

- [carcontroller.py](../../../opendbc/opendbc/car/psa/carcontroller.py): con longitudinale disabilitato crea `NeutralRadar(stationary_only=True)`; passa `CS.out.standstill` alla sessione e genera i sostituti/TesterPresent solo quando `neutral_radar.active` è vero.
- [carstate.py](../../../opendbc/opendbc/car/psa/carstate.py): sulla 3008 il fermo deriva dalle velocità ruota, `vEgoRaw <= 0.1 * KPH_TO_MS`. La prima velocità osservata supera questa soglia di **0,1 km/h**.
- [neutral_radar.py](../../../opendbc/opendbc/car/psa/neutral_radar.py): `if not stationary and (self.stationary_only or not self.active)` chiama `stop('vehicle moved')`. `stop_reason` impedisce i tentativi successivi, anche quando la vettura torna ferma.
- Nel profilo registrato `longitudinal_profile=false`: [interface.py](../../../opendbc/opendbc/car/psa/interface.py) non forza `accFaulted` per il solo `stop_reason`. Qui il primo fault segue davvero lo stato 3 ricevuto nel `32D`, circa **120,3 ms dopo il log di stop**.

Il radar originale torna circa 4,9 s dopo lo stop. Nel frattempo non ci sono i sostituti e il CAN diventa invalido. Questo spiega anche il successivo avviso `canError` senza dover attribuire una variazione reale al modello di vettura riconosciuto.

## Trasmissione e confronto con test1

| ID | TX | Echi TX | Rifiuti | Frequenza media durante invio |
|---|---:|---:|---:|---:|
| `2B6` | 961 | 961 | 0 | 49,747 Hz |
| `2F6` | 961 | 961 | 0 | 49,747 Hz |
| `4F6` | 193 | 193 | 0 | 9,949 Hz |
| `796` | 20 | 20 | 0 | 0,995 Hz |

Conteggi dei payload TX/eco corrispondenti; zero errori di contatore/checksum nelle sequenze sostitutive `2B6`/`2F6`. Gap massimo fra due invii veloci: 24,058 ms. Sono presenti 19 TesterPresent, 19 echi e 19 risposte positive; l’ultima risposta è a 36,345579 s. **Non è un timeout del TesterPresent a fermare la prova.**

Fra primo invio e stop passano circa **19,314 s**, senza campioni `accFaulted=true` o `canValid=false` in quell’intervallo. I messaggi continuano anche dopo aver inserito la retro e premuto il gas, finché `standstill` resta vero.

| Misura | test1, codice precedente | test2, patch `fd64d7e9` |
|---|---:|---:|
| Risposta positiva → primo sendcan | 42,641 ms | **3,255 ms** |
| Ultimo `2B6` originale → primo eco sostitutivo | 111,623 ms | **82,143 ms** |
| Ultimo `2F6` originale → primo eco sostitutivo | 111,623 ms | **101,643 ms** |
| Fault subito dopo avvio dell’emulazione | Sì | **Non osservato** |

I due gap di test2 differiscono perché gli ultimi originali dei due ID hanno timestamp diversi. Non dichiarare “entrambi sotto 100 ms” né dedurre un timeout universale di 100 ms. Il contatore riparte da 0 mentre gli ultimi originali sono rispettivamente 6 e 5: nonostante questa discontinuità iniziale, qui non compare un fault all’avvio. La continuità dei contatori citata sopra riguarda la sequenza dei nostri TX.

L’esito è un riscontro positivo della patch **in questa prova**, non una validazione completa della sostituzione radar o del profilo in movimento. Il punto ora da affrontare è la politica del profilo neutro al movimento, che interrompe trasmissioni ancora necessarie mentre l’originale è in programming. Abilitare il longitudinale attivo cambierebbe anche la politica di attuazione e non è equivalente a continuare una prova con messaggi neutri.

## Perimetro di questa attività

Scaricati e analizzati i log richiesti, aggiornati indice e findings. Nessuna nuova modifica a opendbc, nessun invio diagnostico/CAN, aggiornamento o riavvio del comma.


<!-- [neutral motion] - START -->
## Correzione locale autorizzata — continuità in movimento

Il 12 settembre Cristian ha approvato la soluzione proposta dopo la diagnosi di test2. Applicata nel checkout locale opendbc `psa-torque-sunny-testing`, su base `fd64d7e9b6cd6335667eff1530815b574edbef37`.

- In [carcontroller.py](../../../opendbc/opendbc/car/psa/carcontroller.py) il controller crea `NeutralRadar(stationary_only=False)` anche per il profilo neutro. Dopo l’avvio da fermo la perdita di `standstill` non interrompe più i quattro sostituti né il TesterPresent: la sessione continua anche in retro.
- Restano l’attesa iniziale da fermo, la conferma `50 02`, il controllo degli originali e tutti i timeout. Il movimento prima dell’attivazione continua a bloccare l’avvio. Ritorno radar, CAN invalido, perdita degli echi e mancata risposta diagnostica conservano lo stop senza ritentativi automatici.
- In [neutral_radar.py](../../../opendbc/opendbc/car/psa/neutral_radar.py) aggiornati soltanto commenti e descrizione del log di avvio: `ARTIV: emulation started (motion allowed)`. Il testo descrive la politica di movimento e non implica l’abilitazione del longitudinale attivo.
- La scelta del profilo di attuazione è separata: con `openpilotLongitudinalControl=false` restano i payload neutri, senza richieste di coppia, frenata o set speed. Nessuna modifica a `psacan.py`, frequenze, contatori, flag safety, `values.py` o `interface.py`.

### Verifica locale della correzione

Aggiornati [test_neutral_radar.py](../../../opendbc/opendbc/car/psa/tests/test_neutral_radar.py) e [test_longitudinal_session.py](../../../opendbc/opendbc/car/psa/tests/test_longitudinal_session.py).

Prima della modifica di produzione, i due test di continuità fallivano con `vehicle moved`, uno esattamente al primo campione in movimento in retro. Dopo la modifica:

```sh
.venv/bin/python -m unittest opendbc.car.psa.tests.test_neutral_radar opendbc.car.psa.tests.test_longitudinal_session
ruff check opendbc/car/psa/carcontroller.py opendbc/car/psa/neutral_radar.py opendbc/car/psa/tests/test_neutral_radar.py opendbc/car/psa/tests/test_longitudinal_session.py
git diff --check
```

**26 test passati**, lint e controllo whitespace passati. Il test di manovra attraversa retro da fermo, gas da fermo, movimento in retro a `vEgoRaw=0,038194444 m/s`, arresto e movimento in avanti. In 400 cicli verifica 200 invii per ciascun ID veloce, 40 `4F6`, 4 `796` e 4 TesterPresent, con contatori continui, checksum validi e payload neutri. Imposta anche `CC.enabled=true`, `CC.longActive=true`, accelerazioni richieste positive/negative e target visibile: con il profilo neutro non compaiono richieste fisiche né invii di set speed `452`.

Verificati anche il blocco all’avvio in movimento nei due profili e le regressioni esistenti di sessione. Questa verifica mirata non equivale a dichiarare tutta la suite PSA verde; i due problemi preesistenti della suite più ampia sono già documentati nei [findings precedenti](findings-neutral-20260912.md#patch-locale-autorizzata--transizione-radar).

### Riscontro ancora necessario

La patch elimina localmente l’interruzione osservata in test2. L’accettazione dei payload neutri durante il movimento deve ancora essere verificata sul veicolo: nessun test software dimostra da solo che tutte le ECU li accettino in quelle condizioni. La successiva registrazione sarà `test3`, confrontando continuità TX/echi/TesterPresent, stato `32D`, `accFaulted` e `canValid` nella manovra.

Modifica preparata e verificata soltanto in locale; nessun commit/push, aggiornamento del checkout openpilot o intervento sul comma eseguito in questa attività. L’installazione sul dispositivo resta a Cristian.
<!-- [neutral motion] - END -->
