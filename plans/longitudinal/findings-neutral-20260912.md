# Findings — prova ARTIV neutra del 12 settembre 2026

## Esito e limiti

La prova ha trasmesso i quattro payload neutri previsti con contatori/checksum validi e riscontri TX del Panda. Il fault ACC della vettura **non è stato eliminato**. La causa precisa rimane aperta: l’interruzione iniziale di circa 112 ms è osservata, ma non dimostra da sola la causa del fault.

**Approfondimento completato:** nel journal `0x76D` compare il codice grezzo `D16287` (`U1162:87`) a +16,907891 s, subito dopo il primo stato 3 nel `32D`. Una fonte diagnostica Peugeot associa questo codice alla perdita di informazioni del sistema di distanza. Il clock BSI colloca invece i tre codici `B12A7/B12A8/B12A9` del radar vicino alla ripartenza, circa +227,9 s. Questo rafforza l’ipotesi di un problema di continuità al passaggio, ma non misura la soglia di timeout né dimostra che ridurre l’attesa risolva il fault. Dettagli e limiti nella sezione diagnostica sotto.

Il confronto completo non trova ID/DLC persistenti della bibbia assenti durante l’emulazione, contando RX ed echi TX sullo stesso bus. L’inventario iniziale ARTIV era comunque incompleto: un DBC storico documenta anche `0x116` (versione) e `0x776` (journal dei guasti), entrambi a evento. Questi due ID sono assenti nella bibbia e presenti nella nuova prova al ritorno del radar; `776` compare anche all’inizio della prova.

## Fonti e riproducibilità

- [Prova 3d, cinque rlog e cinque qlog](../../log_analysis/logitudinal_tests/test1/0000003d--3e125c1bb1/): route `6616faac453a3064/0000003d--3e125c1bb1`, intervallo circa 259,49 s. I dieci checksum sono stati confrontati con gli originali del comma durante l’acquisizione.
- [Bibbia 3a, otto rlog e otto qlog](../../log_analysis/dashcam_mode_bibbia_longitudinale/0000003a--e445e79563/): route `6616faac453a3064/0000003a--e445e79563`, intervallo circa 434,04 s; vedere il README di acquisizione.
- [Risultati, estratti e script](findings-neutral-20260912/) e [provenienza/hash](findings-neutral-20260912/provenance.json). I log originali restano nei percorsi sopra: gli estratti JSON non li sostituiscono.
- Codice opendbc della prova: `6bd6cd7008583805d983c2cac9d410518821b3d8`; openpilot da initData: `fa10bf841558480a3404569e1a22001f34e1a3ae`.
- Codice di riferimento: `opendbc/car/psa/{carcontroller,carstate,interface,neutral_radar,psacan}.py`, `opendbc/safety/modes/psa.h`, `opendbc/dbc/psa_aee2010_r3.dbc` nel checkout opendbc.
- DBC storico consultato in sola lettura: `/Users/cristianku/GitHub/COMMA.AI/COMMA OLD/openpilot_elkoled_longi/opendbc/dbc/AEE2010_R3_HS2.dbc`. `116` a riga 74, `776` a 874, attributi evento/periodo a 1232 e 1398–1399, significato del bit ETAT_DTC a 1779. È una fonte di interpretazione storica, non una specifica OEM verificata per questa vettura.

I tempi sotto sono relativi al primo evento letto nel rlog della route, da `logMonoTime`. Gli orologi civili del dispositivo sono incoerenti. I timestamp dei messaggi di log Python possono seguire quelli CAN di pochi millisecondi: per i passaggi TX/RX si usano i timestamp CAN.

CarParams della prova: `dashcamOnly=false`, `passive=false`, `openpilotLongitudinalControl=false`, `pcmCruise=true`, `safetyParam=0`; nessun `carControl.longActive=true`. È una prova **neutra parcheggiata**, non la validazione del prototipo attivo del piano. Il default dashcam descritto nei documenti dell’11 settembre è quindi uno stato storico precedente al commit `6bd6cd70`.

## Payload e trasmissione

| ID | TX in sendcan | Echi Panda | Frequenza misurata | Payload a contatore 0 |
|---|---:|---:|---:|---|
| `2B6` | 10.269 | 10.269 | 49,784 Hz | `FE 00 00 02 00 00 03 0A` |
| `2F6` | 10.269 | 10.269 | 49,784 Hz | `00 FF 86 00 F8 60 0F 00` |
| `4F6` | 2.054 | 2.054 | 9,957 Hz | `FF FE 5F FE 00` |
| `796` | 206 | 206 | 0,996 Hz | `00 00 00 00 00 00 00 00` |

Tutti i payload TX compaiono identici nella bibbia. Questo è un confronto di appartenenza byte per byte ai payload originali, non un replay sincronizzato della guida. Per `2B6` e `2F6` non risultano errori di checksum né salti di contatore nella sequenza TX ordinata per tempo. In questa prova anche il passaggio dal contatore originale 15 al nostro 0 è continuo; il codice riparte da 0 e non garantisce questa coincidenza in ogni prova.

I segnali dei quattro sostituti coincidono anche con quelli del radar fra +10 s e il programming, esclusi contatore/checksum/parità. Richieste coppia/frenata disabilitate: decelerazione 2,05, coppie -4000, richieste e min-time 0; `ACC_STATUS=2`, `AUTO_BRAKING_STATUS=3`, `ARC_STATUS=6`, nessun target. Questi numeri sono codici inattivi secondo il profilo registrato.

`sendcan.src=1` è la destinazione; `can.src=129` è bus 1 + offset TX 128, non un bus fisico diverso. `src=193` denota il rifiuto TX sul bus 1. Per questi quattro ID non risultano rifiuti. La corrispondenza degli echi verifica gli invii del Panda, non l’accettazione applicativa delle ECU riceventi. Fonte del flag: `openpilot/selfdrive/pandad/panda.h` e `panda.cc` nel checkout openpilot della prova.

## Sequenza del fault

| Tempo, s | Evento |
|---:|---|
| 16,765971 | Ultimi `2B6`/`2F6` originali sul bus 1, contatore 15 |
| 16,769035 | `sendcan 6B6`: `02 10 02` |
| 16,828693 | `RX 696`: `06 50 02 00 C8 00 14` |
| 16,871334 | Primi quattro sostituti in sendcan |
| 16,877594 | Primi echi TX: gap osservato di **111,623 ms** dagli ultimi `2B6`/`2F6` originali |
| 16,888346 | `32D.ACC_ETAT_DECEL_OR_ESP_STATUS=3` |
| 16,890110 | `carState.accFaulted=true` |
| 16,893119 | Avviso `Cruise Fault: Restart the car to engage` |
| 16,907891 | Journal `76D`, bus0: `99 D1 62 87 03 BE 2E D7`, passaggio a permanente di `U1162:87` secondo il formato JDD comune |
| 223,135027 | Log `ARTIV neutral: stopped (vehicle moved); no automatic retry` |
| 223,372747 | CAN non valido dopo l’interruzione dei sostituti |
| 227,860843 | Ritorno `2B6` originale e messaggio versione `116` |
| 227,873380 | CAN nuovamente valido |
| 227,920863 | Il radar originale riporta `ACC_STATUS=15`; primo JDD post-ritorno |
| 228,402988 | `2B6.AUTO_BRAKING_STATUS=7` originale |

Durante l’emulazione il CAN rimane valido, non tornano i quattro ID radar originali su src1 e arrivano **205 risposte positive `02 7E 00`** ai 205 TesterPresent. Il mantenimento della sessione è osservato per oltre tre minuti. Lo stop è provocato da `standstill=false`, non da un timeout TesterPresent o di echi.

Il primo `32D` con stato 3 è `80 BC 19 00 80 00 00 C0`. Cambia anche `FA_ETAT_DECEL` a 3, mentre `DEFAUT_ACC_FREIN` in quel frame è 0. Il port usa `ACC_ETAT_DECEL_OR_ESP_STATUS == 3` per `accFaulted`; il DBC corrente non fornisce una tabella VAL_ per quel campo. Questo prova la sorgente software dell’avviso, non identifica un guasto hardware o uno specifico DTC.

Non è dimostrato che il gap sia l’unica causa, che la sessione programming sia di per sé accettabile per tutte le altre ECU, o che basti ridurre l’attesa. I vecchi test sintetici verificano il codice, non il criterio di timeout delle ECU della vettura.

## Statistiche condizionate della bibbia

L’associazione usa l’ultimo stato `carState` con timestamp non successivo al frame CAN; `standstill` e le sue transizioni sono conservati nell’estratto. I campioni prima del primo carState sono esclusi dalle righe condizionate per fermo/movimento. Non dedurre una causa fisica dalla sola correlazione.

| Condizione | Segnale | Distribuzione originale |
|---|---|---|
| Ferma, con carState disponibile | `2B6.AUTO_BRAKING_STATUS` | **3: 4.486/4.486** |
| Ferma, con carState disponibile | `2F6.ARC_STATUS` | **6: 4.482/4.482** |
| `ACC_STATUS=2`, fermo e movimento inclusi | `2B6.AUTO_BRAKING_STATUS` | 3: 9.518; 6: 2.636; 5: 370; totale 12.524 |
| `ACC_STATUS=2`, solo movimento | `2B6.AUTO_BRAKING_STATUS` | 3: 4.789; 6: 2.636; 5: 370; totale 7.795 |
| `POTENTIAL_WHEEL_TORQUE_REQUEST=1` | `2B6.AUTO_BRAKING_STATUS` | 6: 6.090; 3: 150; 5: 12; totale 6.252 |
| `POTENTIAL_WHEEL_TORQUE_REQUEST=2` | `2B6.AUTO_BRAKING_STATUS` | **6: 2.194/2.194** |

Le percentuali aggregate non giustificano cambiare alla cieca 3→6 e 6→12 nella prova neutra. L’affermazione “6 maggioritario anche in inattivo” è errata. Anche attribuire 9.518/12.524 al solo movimento è errato: quel denominatore comprende l’auto ferma.

Per il prototipo attivo restano differenze reali: stato frenata sempre 3 e ARC sempre 6, min-time 6,2 fisso invece dell’alternanza osservata, due coppie inizialmente uguali, assenza di `WHEEL_TORQUE_REQUEST=2` (268 dei 6.252 frame GMP originali). I dati non autorizzano né convalidano un’automatica sostituzione con gli stati maggioritari. Nel `796` della bibbia tutti i 433 payload sono zero: l’affermazione che anche questo messaggio vari con il target non è supportata.

## Inventario completo, inclusi i messaggi lenti

Sono stati letti tutti i 13 rlog delle due route: 1.197.531 record CAN/sendcan nella prova e 1.956.047 nella bibbia. L’inventario conserva tipo evento, src, ID, DLC, fase, conteggio, primo/ultimo tempo, conteggi per secondo e campioni grezzi.

Per il confronto di presenza, la categoria tecnica `physical` nel JSON riunisce RX ed echi TX sul bus di base (`129→1`, ecc.), escludendo i rifiuti. Non significa conferma di ricezione da una specifica ECU e non conta solo gli originali del radar. Le fasi della prova sono esplicite nello script; “emulation” va da 16,877594 a 223,135027 s.

Selezionando gli ID/DLC della bibbia osservati anche dopo +5 s (esclusione della sola finestra iniziale), nessuno è assente durante l’emulazione: **77 combinazioni su bus0, 26 su bus1, 77 su bus2**. Le combinazioni della bibbia senza riscontro sono confinate all’avvio, fra +3,024 e +4,411 s. La soglia è un criterio osservativo esplicito, non una prova che ogni ID selezionato sia periodico per specifica.

Sul bus1, i quattro originali sostituiti cessano al programming; gli altri ID persistenti continuano ad arrivare, compresi `212`, `2B2`, `2F8`, `318`, `408`, `32D`, `452` e `552`. Il precedente confronto limitato a finestre brevi non era sufficiente per dichiarare completo l’inventario.

| ID ARTIV nel DBC storico | Funzione | Osservazione |
|---|---|---|
| `2B6`, `2F6`, `4F6`, `796` | Periodici già sostituiti | Presenza e payload verificati |
| `696` | Risposta diagnostica | Programming e TesterPresent ricevuti |
| `116` | Versione, trasmissione a evento | Una RX sul bus1 a 227,860843 s: `E8 FF FF FF 30 66 92 01`; assente nella bibbia |
| `776` | Journal des défauts, trasmissione a evento | 52 RX nella prova; assente nella bibbia |

Il `6B6` è la richiesta diagnostica diretta al radar, non una sua trasmissione. L’esistenza di `116` e `776` amplia l’inventario ARTIV, ma non dimostra un quinto heartbeat mancante. La prova non copre ogni evento e condizione possibile della vettura.

## Nuova evidenza: registro guasti 0x776

Nel DBC storico `776` è `HS2_EMIS_NEW_JDD_ARTIV_776`, trasmettitore ARTIV, destinatario BSI, periodo 0 e modalità evento. L’attuale DBC PSA e il monitor dei quattro ID non lo includono. Il commento storico della trama cita DIRA/GEP e sembra copiato da altri messaggi: non usarlo come conferma della centralina di origine; conservare la distinzione fra attribuzione del DBC e osservazione sul bus.

- `NUMERO_TRAME = (byte0 >> 4) & 3`; `NOMBRE_TRAMES = byte0 >> 6`.
- `ETAT_DTC = (byte0 >> 3) & 1`: nel DBC 1 indica passaggio a permanente, 0 passaggio a fuggitivo/intermittente.
- Per mux 1, byte1–3 sono il codice grezzo a 24 bit, byte4–7 il riferimento temporale BE ×0,1 s. Il commento vecchio prevede terzo byte 00, ma `C14687` dimostra che va preservato il valore grezzo senza forzarne la semantica.
- Per mux 2 sono riportati chilometraggio e contesto, senza una traduzione qui convalidata.

| Codice grezzo, mux1 | ETAT_DTC | Ripetizioni | Tempi di ricezione, s |
|---|---:|---:|---|
| `C14687` | 0 | 7 | 0,003500–3,208435 |
| `92A700` | 1 | 1 | 227,920863 |
| `92A900` | 1 | 9 | 228,120709–231,726585 |
| `92A800` | 1 | 9 | 231,928666–235,523364 |

Le 14 trame iniziali del journal finiscono a 3,297321 s: `776` era già assente circa 13,47 s prima del programming. Non è quindi un’ulteriore trasmissione periodica interrotta al momento della sostituzione. Le altre 38 trame arrivano dopo il ritorno del radar.

La conversione numerica con `opendbc/car/uds.py:get_dtc_num_as_str` dà `C14687→U0146:87`, `92A700→B12A7:00`, `92A800→B12A8:00`, `92A900→B12A9:00`. È una conversione di formato, non una definizione OEM del guasto. Non è stata trovata una descrizione verificata per questa versione ARTIV nelle fonti locali consultate, inclusa la cartella ARTIV di PyPSADiag. L’allineamento temporale è stato completato nell’approfondimento sotto. Il DBC storico descrive anche `55F` come ACK BSI del journal.

## Approfondimento completato: il guasto iniziale è registrato anche fuori dal radar

Sono stati riletti i cinque rlog della prova selezionando anche i journal delle altre centraline e il clock BSI. Script: [diagnostic_timeline.py](findings-neutral-20260912/diagnostic_timeline.py); dati grezzi, clock e decodifica: [diagnostic_timeline.json](findings-neutral-20260912/diagnostic_timeline.json); [riepilogo](findings-neutral-20260912/diagnostic_timeline_summary.txt).

Il `76D` è presente sui bus0/2 e manca nella bibbia. Nel conteggio sotto si usa soltanto bus0 per evitare di contare due volte il messaggio inoltrato. La struttura mux1/mux2 coincide con il JDD storico e produce riferimenti temporali coerenti con la prova. **L’applicazione di tale struttura a `76D` e `768` è un’inferenza dai payload**, non una definizione completa disponibile nel DBC corrente. L’attribuzione precisa di `76D` all’ECU ESP non è stata confermata dalle fonti locali: non dedurla soltanto dal suffisso dell’ID. Per `768` il DBC corrente indica trasmettitore `CMM___Motor_SG`, ma usa il nome generico `BSI_FaultLog`.

| Journal | Codice, mux1 | ETAT_DTC | Ripetizioni mux1 | Prima RX, s | Riferimento JDD, s | Tempo nominale allineato, s |
|---|---|---:|---:|---:|---:|---:|
| `76D` bus0 | `D16287` → `U1162:87` | 1 | 9 | 16,907891 | 6.279.547,9 | ≈16,8 |
| `768` bus0 | `D16287` → `U1162:87` | 1 | 9 | 224,163839 | 6.279.754,9 | ≈223,8 |
| `768` bus0 | `D16287` → `U1162:87` | 0 | 9 | 228,662893 | 6.279.759,0 | ≈227,9 |
| `776` bus1 | `92A700` → `B12A7:00` | 1 | 1 | 227,920863 | 6.279.759,0 | ≈227,9 |
| `776` bus1 | `92A900` → `B12A9:00` | 1 | 9 | 228,120709 | 6.279.759,0 | ≈227,9 |
| `776` bus1 | `92A800` → `B12A8:00` | 1 | 9 | 231,928666 | 6.279.759,0 | ≈227,9 |

### Interpretazione del codice, con fonte e limiti

Un rapporto diagnostico **Autel MaxiSys per Peugeot 2008 del 2020**, pagina 3, elenca `U1162:87` nella centralina ESP90 come perdita delle informazioni provenienti dal sistema di avviso distanza o dalla telecamera multifunzione. Nello stesso rapporto `U1262:81` è distinto e riguarda dati non validi. Fonte primaria: [rapporto Autel MAXIA20260105091959, diagnosi del 5 gennaio 2026](https://gateway-prodeu.autel.com/api/pdf-report-manage/pdf-report/download/c4263c2268214bbfa06785f52b65a0f1).

Questo è un riscontro pertinente PSA per la descrizione di `U1162:87`, **non** la specifica della soglia temporale o della centralina della nostra 3008. Non implica che il radar sia fisicamente guasto e non identifica quale singola trama sia stata dichiarata assente. La conversione `D162→U1162` è verificabile con il decoder ISO 15031-6 già presente in opendbc; il terzo byte `87` viene conservato separatamente.

### Allineamento con il clock BSI

`552.CPT_TEMPOREL` è un intero BE nei primi quattro byte, risoluzione 0,1 s secondo il DBC storico. Sono presenti **263 campioni** validi sul bus1. La differenza `clock_s − tempo_route` ha mediana **6.279.531,088989 s**, minimo 6.279.531,082673 e massimo 6.279.531,105872. I riferimenti JDD dei journal `76D/768/776` sono compatibili con questa base temporale.

La risoluzione di 100 ms impedisce di ordinare al millisecondo il riferimento JDD rispetto al primo sostituto. Lo script conserva l’offset nominale e un intervallo indicativo che amplia gli estremi di ±0,1 s: per il guasto iniziale circa **+16,69…16,92 s**, per i tre guasti ARTIV circa **+227,79…228,02 s**. Questi intervalli assumono la stessa base BSI; non sono limiti certificati della sincronizzazione e latenza delle ECU. Il timestamp CAN di ricezione del primo `76D`, +16,907891 s, è invece direttamente osservato.

Il precedente `U0146:87` del `776` ha riferimento nominale ≈−0,4 s: è già presente all’inizio della registrazione. Il `775` iniziale contiene `540600` (`C1406:00`) con riferimento 51,7 s; la sua base temporale non è stabilita e lo script **non gli assegna** un tempo allineato al BSI. `COMPTEUR_RAZ_GCT` del `552` vale 254, fuori dal range utile storico 0…253: non è una prova di assenza o presenza di reset.

### Conseguenza per la diagnosi e punto preciso del codice

1. Il fault iniziale non è spiegato soltanto dal parser di openpilot: oltre a `32D` e all’avviso, un journal CAN registra `U1162:87` durante il passaggio. In questo caso il port sta segnalando uno stato ricevuto dalla vettura.
2. I tre codici `B12A7/B12A8/B12A9` hanno tutti il riferimento del ritorno del radar, circa 228 s. Non vanno usati come spiegazione temporale del primo fault a 16,9 s. Il diverso ritardo di trasmissione dei tre journal non implica tre diversi momenti di insorgenza.
3. Dopo lo stop dei sostituti compare anche `U1162:87` in `768`; al ritorno del radar il suo stato passa a 0, secondo il formato JDD. Non compare una nuova insorgenza in `768` all’avvio dell’emulazione. L’assenza di un journal, da sola, non certifica l’accettazione dei sostituti da parte della centralina motore.
4. Il primo buco è **111,623 ms**. Nel codice della prova (`6bd6cd70`), in `opendbc/car/psa/neutral_radar.py`, `NeutralRadar.update()` richiedeva `now_nanos - last_radar_rx_nanos >= 100_000_000`, oltre alla risposta positiva. Sono 100 ms **dall’ultimo messaggio radar originale**, non 100 ms aggiunti dopo la risposta. Nel log la risposta positiva è già arrivata a +16,828693 s, ma i primi sostituti vengono accodati solo a +16,871334 s, altri **42,641 ms** dopo; il riscontro TX arriva a +16,877594 s. L’attesa è quindi un contributo concreto alla discontinuità.
5. L’ipotesi prioritaria è un timeout/perdita di informazioni al passaggio, eventualmente mantenuto fino al ripristino di una condizione della vettura. Resta da distinguere dagli effetti della sessione programming e da criteri di validità non ricavati dai log. Il limite **250 ms** in `RADAR_TX_TIMEOUTS` controlla i nostri echi TX: non è il timeout dell’ESP e non dimostra che 112 ms siano tollerati dalla vettura.

Una eventuale correzione mirata dovrebbe riguardare la transizione fra originale e sostituti, mantenendo conferma diagnostica, rilevamento del ritorno radar e stop in caso di rifiuto. Il risultato osservabile da richiedere sarebbe continuità temporale migliorata e assenza della nuova insorgenza `U1162:87`/stato 3 nel `32D`. I log attuali non convalidano né un nuovo valore della soglia né l’efficacia della modifica; nella fase di sola diagnosi non era stata applicata alcuna patch PSA. La successiva modifica locale autorizzata è descritta sotto. Payload 3/6 e parser non sono il bersaglio giustificato da queste evidenze.

## Patch locale autorizzata — transizione radar

Cristian ha autorizzato la modifica dopo la proposta in chat e ha confermato «ok vai». Applicata sul ramo `psa-torque-sunny-testing`, base `6bd6cd7008583805d983c2cac9d410518821b3d8`, senza commit, push o operazioni sul comma.

File modificati:

- [neutral_radar.py](../../../opendbc/opendbc/car/psa/neutral_radar.py): in `NeutralRadar.update()` il controllo dei 100 ms è sostituito dal confronto fra ultimo RX radar originale e risposta positiva. Quando l’ultimo RX è strettamente precedente alla conferma, il controller può iniziare al primo ciclo utile. Se un originale ha timestamp uguale o successivo alla conferma, l’avvio rimane impedito; oltre il timeout esistente di 1 s la prova termina senza nuovo tentativo automatico. I timestamp uguali vengono trattati conservativamente perché non stabiliscono l’ordine dentro lo stesso pacchetto CAN.
- [test_neutral_radar.py](../../../opendbc/opendbc/car/psa/tests/test_neutral_radar.py): verificato l’invio dei quattro payload letterali al primo ciclo dopo conferma; aggiornato il caso di originale successivo alla conferma; aggiunti i quattro ID nello stesso pacchetto della risposta in entrambi gli ordini.

La condizione appartiene alla sessione condivisa dai profili neutro e sperimentale. Payload, contatori, frequenze e politica di attuazione restano quelli del controller esistente. Rimangono conferma diagnostica valida, vettura ferma e CAN valido all’avvio, stop al ritorno degli originali, timeout degli echi e del TesterPresent. Questo controllo verifica le RX già ricevute; non può garantire che il radar non trasmetta di nuovo dopo l’avvio, caso gestito dallo stop esistente.

### Verifica locale

- Prima della modifica alla produzione, i tre casi della transizione fallivano per il comportamento atteso da correggere (10 assertion considerando gli otto sottocasi dello stesso pacchetto).
- `.venv/bin/python -m unittest -q opendbc.car.psa.tests.test_neutral_radar`: **18 test superati**, inclusi payload, frequenze, contatori, conferma assente/rifiutata, ritorno radar, echi, movimento e CAN invalido.
- `ruff check opendbc/car/psa/neutral_radar.py opendbc/car/psa/tests/test_neutral_radar.py`: superato. `git diff --check`: superato.
- Suite completa delle classi PSA con `unittest discover`: 38 metodi eseguiti, uno fallisce con 7 sottocasi su `dashcamOnly`. È `TestLongitudinalCommands.test_alpha_long_selects_peugeot_profile_and_matching_safety`, che si aspetta il precedente default dashcam; `6bd6cd70` lo aveva già cambiato a false.
- Eseguite anche le 33 funzioni `test_*` di `test_psa.py` tramite `unittest.FunctionTestCase`: 32 superate, una in errore perché `test_synthetic_cruise_button_events_follow_stock_setpoint` richiama `_update_cruise_button_events`, assente da `CarState`.
- Entrambi i problemi della suite più ampia sono stati riprodotti caricando in memoria `neutral_radar.py` originale da `git show HEAD:...`, prima di importare i rispettivi test. Non sono introdotti dalla patch e non sono stati modificati in questo intervento. La suite PSA completa quindi **non è tutta verde**.

`pytest` non è presente nella venv del port: i test sono stati eseguiti con `unittest`, incluse esplicitamente le funzioni che la discovery standard non raccoglie. Ruff è stato eseguito dall’installazione già disponibile nel PATH.

Nel test sintetico la conferma arriva a 10,067 s e il controller emette a 10,070 s: questo verifica l’eliminazione dell’attesa software, **non** misura un nuovo gap sul bus della macchina. La route `test1` resta la registrazione del codice precedente. La prova sul veicolo deve ancora verificare il gap reale e l’eventuale nuova insorgenza `U1162:87`/stato 3 nel `32D`; la scomparsa del fault non è ancora dimostrata.

Hash dei due file dopo la verifica:

- `neutral_radar.py`: SHA256 `dd1157498f245eb5b1629ebe088b13f007580ece6025744309e82f5b4371f731`.
- `test_neutral_radar.py`: SHA256 `c1144edef431f8f543841126daee35e883c69b03f8c16339720468e7b3bead1f`.

## Verifiche ancora aperte

1. Completare la descrizione dei codici ARTIV con una fonte pertinente alla versione del radar e l’attribuzione del journal `76D`. L’allineamento al clock BSI e l’interpretazione pertinente PSA di `U1162:87` sono ora documentati sopra.
2. Distinguere un eventuale timeout al passaggio da effetti della sessione programming o da altre condizioni diagnostiche; il confronto dei soli payload non li esclude.
3. Trattare separatamente la calibrazione del profilo attivo. Non mascherare `accFaulted`, non alterare `32D` ricevuto e non disabilitare `canValid` per far sparire l’avviso.

La consegna comprende la patch locale alla sessione e i suoi test, oltre alla documentazione. Controller, costruttori CAN, safety e dispositivo restano invariati.

## File e riesecuzione

I quattro script iniziali sono stati conservati con la sola sostituzione dei percorsi temporanei con percorsi relativi alla loro cartella e marcatori di blocco. Le dipendenze di lettura restano il checkout opendbc, il checkout openpilot per lo schema Cap’n Proto, pycapnp e zstandard. Eseguirli nell’ordine: `compare_radar_logs.py`, `radar_fault_detail.py`, `radar_full_inventory.py`, `radar_jdd.py`. Il nuovo `diagnostic_timeline.py` rilegge direttamente i cinque rlog della prova e scrive `diagnostic_timeline.json`; il suo stdout è salvato in `diagnostic_timeline_summary.txt`. I file stdout `*_summary.txt` e `radar_fault_detail.txt` sono snapshot della precedente esecuzione; possono essere rigenerati redirigendo stdout nei rispettivi file.

Gli script riscrivono esclusivamente i rispettivi estratti nella propria cartella. I JSON e gli stdout originari sono copiati byte per byte; i due risultati `diagnostic_timeline.*` sono stati generati direttamente nella cartella finale; `provenance.json` ne documenta gli hash. I file di stdout possono includere riepiloghi intermedi: le qualificazioni e le correzioni di questo documento prevalgono sulle etichette abbreviate degli script.
