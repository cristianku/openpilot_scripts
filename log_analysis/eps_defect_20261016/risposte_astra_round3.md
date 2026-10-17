# Review del codice — risposte Astra, round 3

**Data:** 16 ottobre 2026.  
**Destinatario:** Claude e Cristian.  
**Perimetro:** review locale, test offline, nessun comando sul comma. Unico file aggiunto ai repository da questa review: il presente documento. Sorgenti, test e safety esistenti preservati; helper e compilazioni della review in `/private/tmp/psa_round3_review/`.

Le righe citate sono quelle del worktree esaminato, basato su opendbc `4ea63ca81` con le modifiche non committate del round 3.

## Conclusione operativa

**La correzione dei cinque casi concordati funziona e i test forniti passano. Prima del giro proporrei ancora di chiudere due casi accessibili anche con dither a zero:**

1. **Freno già noto a CarState con `latActive` ancora vero:** il controller continua a ripetere coppia non nulla, che la safety rifiuta. È una condizione non coperta dal nuovo rilascio. Il veto sul freno esisteva già nella safety; non va modificato.
2. **Disattivazione breve durante la scaletta:** il frame viene portato subito a STATUS 2, ma lo stato interno resta al vecchio STATUS. Alla ripresa ho riprodotto una sequenza **2→4**, senza nuovo 3. Va sincronizzata la macchina a stati con il rilascio effettivamente inviato, oppure va accettata esplicitamente questa semantica; non si può affermare che la scaletta sul CAN resti sempre 2→3→4.

**Il dither a zero è confermato e non aggiunge perturbazioni.** Ho confrontato tutti i messaggi CAN e gli output attuatori su 1.500 cicli con e senza le routine del dither: identici, a parità di input e RNG dei messaggi hold-wheel.

**Con dither acceso non è invece dimostrata né garantita la simmetria della perturbazione consegnata.** Il confronto col limiter, l'annullamento e la quantizzazione CAN hanno limiti concreti descritti sotto. Non sono blocchi aggiuntivi per un test con ampiezza zero.

Le osservazioni qui presenti non sono una certificazione della dinamica dello sterzo o della risoluzione del Defect. Non ho applicato nessuna correzione né installato la versione.

## 1. Rilascio nei cicli intermedi e transizioni

### Cosa è corretto

Riferimenti: `opendbc/car/psa/carcontroller.py:605`, `:630`, `:634`, `:745`, `:809`, `:821`.

Il rilascio aggiorna realmente `lka_msg_last`, azzera TORQUE e TORQUE_FACTOR e azzera `apply_torque_scaled_last`. Le copie successive rimangono neutre fino al successivo calcolo ordinario. `carOutput` usa il riferimento aggiornato, quindi riporta zero anche nei cicli intermedi (`:1063`).

La distinzione tra:

- disingaggio/Defect/velocità bassa → STATUS 2;
- EPS che esce da Active/override → STATUS precedente;

è implementata come concordato. Il gate `lka_last_eps_active` evita di azzerare continuamente il fattore della normale scaletta in attesa dell'EPS. La priorità di `not lat_active` sul resto è corretta, anche se il frame precedente era già neutro ma con STATUS diverso da 2.

I **20 sottotest** forniti, cinque condizioni per cicli 1–4, passano con controller e safety reali, compresa la ripresa della coppia.

### P1 — Freno noto ma coppia ancora ripetuta

Riferimenti:

- `carcontroller.py:613` e `:617`: le condizioni urgenti non includono il freno;
- `carcontroller.py:775`: anche il ramo ordinario non lo include tra i veti diretti di coppia;
- `opendbc/car/psa/carstate.py:121`: `brakePressed` è già disponibile;
- `opendbc/safety/modes/psa.h:194` e `:316`: il freno fisico viene letto dalla safety e vieta coppia non nulla.

Riproduzione con ampiezza zero, a coppia stabilizzata:

```text
frame 100: comando attivo, TORQUE=75, TORQUE_FACTOR=57
prima del frame 101:
  CS.out.brakePressed = True
  Dat_BSI/P013_MainBrake = 1 ricevuto dalla safety sul bus 2
  CC.latActive resta temporaneamente True
frame 101:
  il controller ripete TORQUE=75, TORQUE_FACTOR=57
  safety_tx_hook restituisce False
```

Non è un'ipotesi di fault EPS: è uno scarto riprodotto. Può verificarsi durante il ritardo di propagazione verso `carControl`, o se una configurazione mantiene il laterale richiesto mentre il veto panda è già presente.

**Proposta, non applicata:** trattare il freno noto come veto di coppia coerente con la safety, sia nel ramo a 20 Hz sia nei cicli intermedi. Aggiungerlo soltanto al helper non basta: il successivo calcolo ordinario potrebbe riproporre coppia. Conservare la semantica di STATUS coerente con `lat_active`, senza cambiare arbitrariamente la politica MADS e senza toccare `psa.h`.

Questo non può garantire zero scarti in assoluto: un evento fisico può arrivare al panda prima che il controller lo osservi. Il problema riprodotto è continuare a inviare coppia quando il freno è **già noto al controller**.

### P2 — Disattivazione breve durante la scaletta

Riferimenti: `carcontroller.py:630`–`:635`, `:656`–`:671`, `:746`–`:752`.

Il helper aggiorna `lka_last_status`, ma non `self.status`, `apply_torque_factor`, `eps_activation_frame` o `latActiveLast`. La scelta conserva la macchina a stati a 20 Hz, ma rende possibile una divergenza tra stato interno e comando già inviato.

Sequenza riprodotta, EPS non ancora Active:

| Frame | Condizione | TORQUE | FACTOR | STATUS inviato |
|---:|---|---:|---:|---:|
| 0 | Attivazione richiesta | 0 | 10 | 3 |
| 1 | `latActive=False` | 0 | 0 | 2 |
| 2–4 | `latActive=True` di nuovo | 0 | 0 | 2 |
| 5 | Aggiornamento ordinario, EPS ancora non Active | 0 | 20 | **4** |

Il passaggio successivo al rilascio è quindi **2→4**. I frame sono accettati dalla safety, perché la coppia è zero; questo non dimostra che siano corretti per la procedura OEM di attivazione.

**Proposta, non applicata:** registrare il rilascio osservato come evento pendente e riconciliarlo al successivo aggiornamento ordinario, prima di avanzare la scaletta. In questo modo si può mantenere la cadenza delle decisioni a 20 Hz senza dimenticare l'interruzione già comunicata all'EPS. Non basta cambiare solo il payload in cache.

Non ho dimostrato che questo salto provochi il Defect o un mancato ingaggio sul veicolo. Ho dimostrato il salto e l'assenza di copertura nei test attuali.

### Rearm con EPS ancora Active

Riferimenti: `carcontroller.py:645`, `:756`–`:761`.

Ho forzato una scadenza di rearm nel test, mantenendo l'EPS Active in ritardo di risposta. Il controller invia e ripete STATUS 2 con coppia/fattore zero, conservando `deactivation_in_progress`. Quando il test fa scendere l'EPS da Active, ai successivi aggiornamenti ordinari la scaletta produce 3 e 4, poi la coppia riprende quando l'EPS torna Active. Tutti i frame della prova passano la safety.

Quindi **non ho trovato un errore introdotto dal helper nel rearm nominale con risposta tardiva dell'EPS**. Il comportamento di attesa resta quello esistente; non equivale a una prova del tempo di hold-off fisico.

### `lat_active` breve e takeover

Riferimenti: `carcontroller.py:747`, `:769`, `:1049`, `:1066`.

Se `lat_active` diventa falso e torna vero interamente tra due aggiornamenti:

- il rilascio CAN avviene;
- il vecchio timer del ciclo EPS può rimanere invariato;
- `latActiveLast` non vede il falso;
- non nasce automaticamente il takeover che sarebbe richiesto se il falso fosse osservato nel ramo ordinario.

Nel test con EPS mantenuto Active: rilascio al frame 101, ripresa della coppia al 105, `eps_activation_frame` resta 5 e `takeover_req` resta 0. È la conseguenza della decisione di non toccare takeover e macchina a stati nei cicli intermedi. Va descritta e testata, senza presentarla come già equivalente a un disingaggio ordinario completo.

Un takeover **già pendente** non viene cancellato dal helper: ho verificato che il suo contatore resta invariato al frame dispari e termina normalmente al successivo frame pari. L'eventuale soppressione delle richieste takeover quando la sessione radar possiede 0x2F6 è preesistente (`:1047`).

### Il rilascio può essere scartato dalla safety?

Il frame neutro prodotto dal helper ha forma valida e passa i test con override. Il ramo PSA a coppia zero azzera i riferimenti della safety prima dei controlli di rate (`psa.h:300`). Non emerge uno scarto dovuto al salto dalla coppia attiva a zero, al fattore zero o alla conservazione dello STATUS.

Questo non è una garanzia contro ogni possibile rifiuto esterno, ad esempio stato globale panda/relay errato. Il caso di scarto concreto trovato nella review riguarda un **rilascio mancante sul freno**, non il frame neutro costruito dal helper.

## 2. Dither: programmazione, anticipo del rearm, segno e RNG

Riferimenti: `carcontroller.py:563`–`:601`, `:638`–`:654`, `:758`.

### Rearm anticipato

**Sì, l'annullamento è coperto:** il ramo di anticipo chiama `_deactivate_eps()`, che chiama `_cancel_eps_dither()`. Ho verificato con controller e safety che, forzando la decisione di preemption, il campione inviato è neutro STATUS 2 e la prenotazione viene portata a `-1`.

Questa prova verifica il collegamento tra decisione di anticipo e annullamento; non risimula il modello di previsione curva. I test EPS esistenti sulla funzione di decisione passano separatamente.

**Annullare non garantisce tre secondi di distanza dal rearm effettivo.** La programmazione usa `eps_rearm_frames`, cioè la scadenza nominale. Se viene deciso un rearm anticipato, il burst può essere troncato. La proprietà realmente ottenuta è “margini sulla scadenza nominale e interruzione all'anticipo”, non “nessun burst negli ultimi tre secondi prima di qualunque rearm”.

### Alternanza del segno

Il segno cambia a ogni programmazione (`:579`), anche se poi il burst non parte o viene annullato. Non viola i limiti e non è un blocco per la prova a zero. **Non garantisce però l'alternanza dei burst effettivamente percepiti:** uno annullato prima dell'inizio può consumare un segno, facendo partire due burst successivi dallo stesso lato.

Per una futura valutazione con dither acceso, registrare segno e istante del primo campione realmente applicato. Se il requisito diventa alternare i burst effettivamente iniziati, il segno va consumato su quell'evento, una volta sola. Nessun recupero o impulso compensativo dopo override.

### RNG senza seed fisso

Va bene per la distribuzione temporale prevista. È un `random.Random()` privato del controller (`:199` circa), quindi la programmazione non consuma il generatore globale usato dal jitter dei messaggi hold-wheel. Non c'è motivo di imporre un seed fisso in produzione; nei test il seed esplicito è corretto. Per riprodurre un evento basta loggare il frame estratto e il segno, senza affidarsi alla possibilità di ricostruire il seed.

Un dettaglio statistico: `uniform()` seguito da `round()` non produce probabilità esattamente uguali su tutti i punti della griglia a 20 Hz; gli estremi hanno metà del bacino di arrotondamento. Con margini attuali 2,0 e 7,8 s allineati alla griglia, non ho trovato uno sforamento dei margini. Non è un problema pratico per questa prova.

Nel harness l'EPS è già Active al frame zero: il valore zero usato come sentinella di `eps_activation_frame` fa ripetere `_start_eps_active_cycle()` al frame 5. È un comportamento preesistente del timer che ora riprogramma anche il burst; non genera due burst fisici, ma conta per interpretare seed, segno iniziale e test. Non è una nuova perturbazione quando A=0.

## 3. Il controllo del clipping non garantisce simmetria

Riferimenti: `carcontroller.py:788`–`:818`; limiter reale in `opendbc/car/lateral.py:70`.

Il confronto:

```python
limitato(base + dither) == base + dither
```

dimostra soltanto che il totale di quel campione non è stato modificato dal limiter. **Non dimostra né la differenza rispetto a una traiettoria senza dither né la somma zero del burst applicato.**

### 3a. Il dither può nascondere un clipping della base

Controesempio con il limiter reale, coppia positiva e nessun override:

```text
ultimo applicato = 35
base richiesta = 44
dither richiesto = -3
limitato(44 - 3, 35) = 41  -> il controllo attuale passa
limitato(44, 35) = 43
differenza effettiva rispetto alla base limitata = 41 - 43 = -2, non -3
```

Se in futuro si vuole verificare che l'incremento sia quello nominale, occorre considerare anche il comando base ammesso, con una definizione esplicita della traiettoria di riferimento. Controllare solo il totale è insufficiente.

### 3b. Annullare a metà lascia un prefisso non bilanciato

Se i campioni già applicati hanno area non nulla, `_cancel_eps_dither()` non li annulla retroattivamente. È corretto non compensarli dopo override; è invece scorretto il commento “drop the burst, no asymmetric pull” (`:795`) se inteso come garanzia.

La proprietà ottenibile è “interrompi al primo campione problematico e mantieni i limiti”, non “media zero per qualunque burst interrotto”.

### 3c. Il riferimento del rate limiter contiene l'ultimo dither

Controesempio con il limiter reale:

```text
ultima base = 90
ultimo dither = -6
ultimo comando applicato = 84
nuova base = 100; nuovo dither = -4
limitato(96, 84) = 92 -> clipping, quindi annullamento
ricalcolo senza nuovo dither: limitato(100, 84) = 92
traiettoria senza il dither precedente: limitato(100, 90) = 98
residuo dopo annullamento = -6
```

Ho verificato anche una traiettoria completa attraverso il controller e la safety: burst al frame 645, salto del comando base al frame 675. Al frame di annullamento l'uscita effettiva codificata è **3**, contro **5** nella traiettoria con identici input ma dither sempre spento. Il burst risulta cancellato (`start_frame=-1`), ma resta una differenza nel comando.

**Non correggere questo residuo azzerando arbitrariamente il riferimento del limiter durante normale guida:** quel riferimento rappresenta l'ultimo comando consegnato. Una simile scorciatoia potrebbe chiedere un salto non ammesso. Il rilascio urgente a zero è un caso distinto, gestito esplicitamente dalla safety.

### 3d. Anche un burst completo può avere una piccola media non nulla sul CAN

Il limiter opera su interi effettivi; poi `can_torque` viene arrotondato dopo la divisione per il fattore (`:802`).

Caso reale nel harness, richiesta costante 0,5:

```text
base intera effettiva = 43
TORQUE_FACTOR = 57
base codificata senza dither: TORQUE=75 -> effettiva 42,75
somma dei 24 campioni nominali del dither = 0
somma delle differenze effettive codificate rispetto alla base = +2,85
media della differenza nel burst = +0,11875 unità effettive
area su 24 intervalli da 50 ms = +0,1425 unità effettive*s
```

Ho riprodotto lo stesso risultato sia calcolando la conversione sia confrontando i frame prodotti da due esecuzioni complete del controller, con safety accettante. È circa lo **0,079% di STEER_MAX** come media del burst: un effetto numericamente piccolo, ma una controprova della garanzia di media *esattamente* zero sul CAN. Non dimostra una deviazione fisica misurabile della vettura.

### Coppia guidatore e saturazione

Il limite legato al guidatore e la saturazione ±150 sono già dentro `apply_driver_steer_torque_limits`, quindi il confronto vede un taglio del totale causato da questi vincoli. Non risolve però prefissi troncati, storia del limiter e quantizzazione. Inoltre gli override possono terminare il burst prima che il confronto venga eseguito.

Con questi limiti non va promessa simmetria per qualsiasi traiettoria. Per una futura prova A>0 occorrono misure di base, nominale, applicato, conversione CAN e motivo di annullamento. La media zero resta una proprietà della forma nominale completa; l'uscita reale deve essere misurata.

## 4. Dither a zero

Riferimenti: `opendbc/car/psa/values.py:93`, `carcontroller.py:566`, `:585`, `:794`.

**Confermo che il parametro reale è zero.** La programmazione esce prima del sorteggio e del calcolo della durata. `_eps_dither()` restituisce zero prima della trigonometria. Il ramo di annullamento per clipping non viene eseguito, perché richiede `dither != 0`.

Verifiche aggiuntive:

1. 1.500 cicli con `uniform()` e `_eps_dither_burst_time()` sostituiti da funzioni che sollevano errore se chiamate: nessuna chiamata inattesa.
2. Due esecuzioni da 1.500 cicli, inclusi override, EPS non attivo, Defect, brevi disingaggi, velocità bassa e scadenza nominale: una con codice reale A=0, l'altra con `_schedule_eps_dither`/`_cancel_eps_dither` inerti e `_eps_dither` sempre zero. **Tutti i messaggi CAN e tutti gli output attuatori identici.**

“Inerte” vale quindi per l'attuazione nei casi verificati, non come assenza di qualsiasi istruzione: l'oggetto RNG privato viene comunque costruito e i campi interni possono essere aggiornati a `-1`.

La prova mantiene la stessa patch di rilascio in entrambe le esecuzioni. Non è un confronto con il vecchio controller che inviava a 20 Hz.

## 5. Proposta minima per torqued — nessuna modifica applicata

Riferimenti nel checkout openpilot attuale: `openpilot/selfdrive/locationd/torqued.py:179`, `:203`–`:212`.

Il learner legge `carOutput.actuatorsOutput.torque`, applica la compensazione del ritardo e inserisce punti torque/accelerazione. Con il dither acceso i suoi gate attuali non bastano: il burst è progettato proprio per restare sotto la soglia di `steeringPressed`.

**Per il giro attuale A=0 non serve intervenire su torqued a causa del dither.**

Per una prima fase sperimentale A>0, la soluzione con minore ambiguità è escludere la raccolta per il fit durante l'intero giro con dither abilitato, mantenendo disponibili i parametri già validi. Questo richiede una decisione esplicita nel codice/configurazione openpilot; non è una funzione già implementata dalla patch.

Per escludere soltanto i burst, la proposta minima corretta è invece:

1. un segnale dedicato di “eccitazione laterale/dati non adatti al learner”, pubblicato insieme all'output con timestamp coerente; non riciclare `steeringPressed`, `latActive` o un campo numerico con un significato diverso;
2. flag valido durante il burst, inclusi gli zeri interni, e durante l'assestamento dopo fine/annullamento;
3. storico nel learner e filtro prima di `filtered_points.add_point()`, allineato alla stessa compensazione di ritardo già usata per torque/override;
4. test dell'intervallo escluso e della prima finestra nuovamente ammessa.

Il trasporto del flag richiede un percorso/schema esplicito tra controller e pubblicazione di `carOutput`; non esiste già in questa patch. Non descriverlo come una sola riga in torqued. La durata di assestamento va scelta da misure, non ricavata automaticamente da `HISTORY=5` o dall'hold-off EPS di 1,3 s.

**Non falsare `actuatorsOutput.torque` riportando soltanto la base:** il valore deve continuare a descrivere il comando inviato. Sottrarre il dither dal campo non elimina la risposta fisica dai dati di accelerazione.

## 6. Test: copertura e limiti

### Risultati riconfermati

| Verifica eseguita | Esito |
|---|---|
| `test_lka_100hz.py` + `test_eps_dither.py` | **12 passati, 20 sottotest passati** |
| `test_psa.py -k eps` | **24 passati, 9 deselect** |
| Probe aggiuntivi di questa review | **12 passati**: controllano gli esiti osservati, inclusi i controesempi |

I probe che mostrano un difetto sono assert sulla **presenza del comportamento riprodotto**, non test di regressione che attestino una correzione.

Non ho rieseguito le suite complete radar/longitudinale o l'intera safety PSA. I 67 e 12 fallimenti baseline descritti nelle domande restano risultati riferiti da Claude. Ho verificato che `psa.h` non ha diff e ho usato la sua compilazione reale nei test mirati.

### Casi mancanti prioritari

- Freno nei cicli 1–4, freno al calcolo ordinario, freno rilasciato prima del successivo calcolo, ripresa senza scarti persistenti.
- `lat_active=False` per un solo ciclo, ripristinato prima del successivo calcolo, sia durante attivazione sia con coppia attiva.
- EPS che esce/rientra rapidamente da Active prima del successivo aggiornamento; verifica dello STATUS sul CAN e della politica timer/avvisi.
- Scaletta interrotta a STATUS 3 e a STATUS 4: attese esplicite per i payload successivi, non solo corrispondenza con i campi cache.
- Rearm nominale/anticipato con risposta EPS ritardata, più takeover già pendente.
- Dither: confronto del comando effettivo codificato con una traiettoria di riferimento, clipping della base nascosto dal dither, annullamento in entrambe le semionde, saturazione ±150, fattore variabile e residui del limiter.
- Ramo `CS.out.steeringPressed=True` indipendente dal raw, segni di coppia opposti, velocità esattamente 51 e vicina alla soglia. I sottotest attuali usano raw positivo e velocità 40 per la condizione bassa.

### Test che dimostrano meno di quanto suggerisce il nome

- `test_lka_sent_every_cycle_when_engaged`, `test_lka_100hz.py:47`: abilita la richiesta ma non inietta EPS Active. Verifica soprattutto trasmissione durante la scaletta. I nuovi sottotest di rilascio colmano parte di questa lacuna.
- `test_activation_ladder_not_released_between_steps`, `:234`: il confronto con `lka_last_*` dopo `h.step()` è parzialmente autoreferenziale, perché il helper aggiorna proprio quei campi. L'assert finale sul fattore offre una controprova utile, ma mancano la sequenza attesa 3/4/2 e l'uguaglianza col frame precedente.
- `test_full_burst_through_safety`, `test_eps_dither.py:76`: somma i valori ritornati da `_eps_dither()`, registrati **prima** di limitazione e codifica. Verifica nominale + accettazione safety; non prova la media zero della perturbazione effettivamente inviata. Il controesempio CAN sopra passa comunque questo tipo di test.
- `test_clipping_drops_the_burst`, `:90`: verifica che non vengano più richiesti campioni nominali, ma non che l'uscita ritorni immediatamente alla traiettoria senza dither.
- `test_amplitude_zero_means_no_burst`, `:68`: prova zero campioni richiesti e nessuna prenotazione; l'equivalenza di tutti gli output è stata verificata dai probe aggiuntivi.

La riga aggiunta al fixture `test_psa.py:325` è appropriata al nuovo accesso a `params`: non ho trovato un problema di produzione introdotto da quel cambio di test.

## 7. Cosa resta prima del giro

**Non considererei ancora chiusa la preparazione locale:** aggiungerei il veto freno coerente con la safety e risolverei/testerei il rilascio breve durante la scaletta, senza allargare il lavoro ad altre logiche. Sono proposte da autorizzare/applicare da parte di Cristian/Claude; Astra non ha corretto il worktree.

Per i cinque casi già concordati, la correzione è confermata. Il rearm con risposta tardiva e i takeover già pendenti non mostrano nuovi difetti nei probe eseguiti. Ampiezza zero è confermata: i problemi del dither acceso non impongono di rifare il dither per eseguire un test limitato ai 100 Hz.

Restano due commenti troppo forti:

- `carcontroller.py:823`: “irregular 20 Hz cadence -> EPS Defect” afferma causalità. Scrivere che è una mitigazione della correlazione osservata negli echo, senza equipararla a misura sul filo o causa dimostrata.
- `carcontroller.py:795`: “no asymmetric pull” non è una garanzia supportata dall'algoritmo. Qualificare anche “zero mean” in `values.py:95` come proprietà della forma nominale completa.

Conservare il confronto con dither spento, firmware/safety invariati e metriche per esposizione già concordate. Nessuna prova locale dimostra che l'EPS accetti fisicamente 100 Hz senza Defect: quello resta l'esito da misurare, dopo la preparazione.

## Comandi esatti e riproducibilità

Tutti i comandi seguenti sono stati eseguiti **sul Mac**, dalla root di opendbc. Nessuna analisi di log aggiuntiva o chiamata sul dispositivo è stata eseguita in questo round: sono review dei sorgenti, calcoli e test offline.

### Test forniti

```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python \
  /private/tmp/psa_round3_review/run_pytest.py \
  -q -p no:randomly -p no:cacheprovider \
  opendbc/car/psa/tests/test_lka_100hz.py \
  opendbc/car/psa/tests/test_eps_dither.py
```

### Test EPS preesistenti

```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python \
  /private/tmp/psa_round3_review/run_pytest.py \
  -q -p no:randomly -p no:cacheprovider \
  opendbc/car/psa/tests/test_psa.py -k eps
```

### Probe aggiuntivi

```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python \
  /private/tmp/psa_round3_review/run_pytest.py \
  -q -s -p no:randomly -p no:cacheprovider \
  /private/tmp/psa_round3_review/test_extra_round3.py \
  > /private/tmp/psa_round3_review/extra.out
```

La build di libsafety crea normalmente alcuni output nella directory dei test: per preservare il worktree il launcher sposta **solo i file di compilazione** in `/private/tmp/psa_round3_review`. Sorgenti, flag e hook C restano quelli locali. `PYTHONDONTWRITEBYTECODE` e `no:cacheprovider` evitano cache Python/pytest nei repository. Questa redirezione non modifica il codice della safety.

### Ispezioni principali

```sh
git status --short
git branch --show-current
git diff -- opendbc/car/psa/carcontroller.py opendbc/car/psa/values.py opendbc/car/psa/tests/test_psa.py
git diff -- opendbc/safety/modes/psa.h
nl -ba opendbc/car/psa/carcontroller.py
nl -ba opendbc/car/psa/tests/test_lka_100hz.py
nl -ba opendbc/car/psa/tests/test_eps_dither.py
nl -ba opendbc/car/psa/values.py
nl -ba opendbc/car/psa/carstate.py
nl -ba opendbc/safety/modes/psa.h
nl -ba opendbc/car/lateral.py
nl -ba /Users/cristianku/GitHub/COMMA.AI/CRISTIANKU/new_openpilot_psa_torque_sunny_testing/openpilot/selfdrive/locationd/torqued.py
```

Le copie dei due test nella cartella di analisi risultano identiche ai file nel worktree (`cmp`).

I file temporanei potrebbero sparire: il codice completo dei due helper e l'output sono riportati nelle appendici seguenti, così questo documento resta autosufficiente per Claude.

## Appendice A — launcher dei test

```python
import inspect
import sys
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))
from opendbc.safety.tests.libsafety import libsafety_py

# Keep compilation artifacts out of the reviewed worktree.
namespace = dict(vars(libsafety_py))
source = inspect.getsource(libsafety_py._build_libsafety).replace('dir=libsafety_dir', 'dir="/private/tmp/psa_round3_review"')
exec(compile(source, '<temporary build directory only>', 'exec'), namespace)
libsafety_py._build_libsafety = namespace['_build_libsafety']

import pytest
raise SystemExit(pytest.main(sys.argv[1:]))

```

## Appendice B — probe aggiuntivi completi

```python
import json
import math
import random
import unittest
from unittest.mock import patch

from opendbc.car.lateral import apply_driver_steer_torque_limits as limit
from opendbc.car.psa.tests.test_lka_100hz import ReleaseHarness
from opendbc.car.psa.carcontroller import CarController
from opendbc.car import structs
from opendbc.safety.tests.libsafety import libsafety_py


class TestExtraRound3(unittest.TestCase):
  def test_brake_known_to_carstate_still_repeats_nonzero_frame(self):
    h=ReleaseHarness(self)
    while h.controller.frame<=100: h.step()
    h.cs.out.brakePressed=True
    addr,data,bus=h.packer.make_can_msg('Dat_BSI',2,{'P013_MainBrake':1})
    h.safety.safety_rx_hook(libsafety_py.make_CANPacket(addr,bus,data))
    self.assertTrue(h.safety.get_brake_pressed_prev())
    c=h.controller; frame=c.frame
    _,msgs=c.update(h.cc.as_reader(),structs.CarControlSP(),h.cs,(frame+1)*10_000_000)
    msg=next(m for m in msgs if m[0]==0x3F2)
    accepted=bool(h.safety.safety_tx_hook(libsafety_py.make_CANPacket(msg[0],msg[2],msg[1])))
    print('BRAKE_STALE',json.dumps({'frame':frame,'brake_known':bool(h.cs.out.brakePressed),
                                    'raw_torque':c.lka_last_torque,'factor':c.lka_last_factor,
                                    'accepted':accepted}),flush=True)
    self.assertNotEqual(c.lka_last_torque,0)
    self.assertFalse(accepted)

  def test_rearm_ladder_and_late_eps_response(self):
    h=ReleaseHarness(self)
    while h.controller.frame <= 100: h.step()
    c=h.controller
    c.eps_activation_frame=100; c.eps_rearm_frames=5
    seen=[]
    for _ in range(9): seen.append(h.step())
    self.assertTrue(c.deactivation_in_progress)
    self.assertTrue(all(t==0 and f==0 and st==2 for frame,t,f,st in seen if frame>=105))
    h.cs.eps_active=False; h.cs.eps_state_lka=2
    ladder=[]
    for _ in range(10):
      row=h.step()
      if row[0]%5==0: ladder.append(row[3])
    self.assertEqual(ladder,[3,4])
    h.cs.eps_active=True; h.cs.eps_state_lka=3
    self.assertTrue(any(h.step()[1] for _ in range(20)))

  def test_short_inactive_pulse_during_activation(self):
    h=ReleaseHarness(self)
    h.cs.eps_active=False; h.cs.eps_state_lka=2
    first=h.step()
    self.assertEqual(first[3],3)
    h.cc.latActive=False
    released=h.step()
    self.assertEqual(released[1:],(0,0,2))
    h.cc.latActive=True
    while h.controller.frame<5: h.step()
    resumed=h.step()
    print('SHORT_LADDER',json.dumps({'first':first,'release':released,'resumed':resumed}),flush=True)
    self.assertEqual(resumed[3],4)  # observed: skips STATUS 3 after the release

  def test_short_inactive_pulse_does_not_latch_takeover_or_reset_cycle(self):
    h=ReleaseHarness(self)
    while h.controller.frame<=100: h.step()
    activation=h.controller.eps_activation_frame
    h.cc.latActive=False
    release=h.step()
    h.cc.latActive=True
    rows=[]
    for _ in range(10): rows.append(h.step())
    print('SHORT_ACTIVE',json.dumps({'release':release,'resumed':rows,'activation_before':activation,
                                    'activation_after':h.controller.eps_activation_frame,
                                    'takeover_req':h.controller.takeover_req,'status':h.controller.status}),flush=True)
    self.assertEqual(h.controller.eps_activation_frame,activation)
    self.assertEqual(h.controller.takeover_req,0)

  def test_nonzero_takeover_is_preserved_by_release(self):
    h=ReleaseHarness(self)
    while h.controller.frame<=100: h.step()
    c=h.controller; c.takeover_req=1; c.start_takeover_repeats=1
    h.cc.latActive=False
    h.step()  # frame101 odd: no takeover TX expected
    self.assertEqual(c.takeover_req,1)
    self.assertEqual(c.start_takeover_repeats,1)
    h.step()  # frame102 even: pending takeover finishes
    self.assertEqual(c.takeover_req,0)
    self.assertEqual(c.start_takeover_repeats,0)

  def test_zero_amplitude_skips_rng_and_waveform_math(self):
    h=ReleaseHarness(self); c=h.controller
    c.params.EPS_DITHER_AMPLITUDE=0
    with patch.object(c.eps_dither_rng,'uniform',side_effect=AssertionError('unexpected rng draw')):
      with patch.object(c,'_eps_dither_burst_time',side_effect=AssertionError('unexpected waveform math')):
        for _ in range(1500): h.step()

  def test_limit_total_does_not_measure_additive_perturbation(self):
    h=ReleaseHarness(self); p=h.controller.params
    total=limit(44-3,35,0,p,p.STEER_MAX)
    base=limit(44,35,0,p,p.STEER_MAX)
    self.assertEqual(total,41)
    self.assertEqual(base,43)
    self.assertEqual(total-base,-2)
    print('LIMIT_COUNTEREXAMPLE',json.dumps({'base_request':44,'previous_output':35,'dither_request':-3,
                                             'total_output':total,'base_only_from_same_previous':base,
                                             'actual_increment':total-base}),flush=True)

  def test_cancel_retains_dither_in_rate_limit_memory(self):
    h=ReleaseHarness(self); p=h.controller.params
    # Last base 90, last dither -6 -> previous applied output 84.
    tentative=limit(100-4,84,0,p,p.STEER_MAX)
    cancelled=limit(100,84,0,p,p.STEER_MAX)
    no_excitation=limit(100,90,0,p,p.STEER_MAX)
    self.assertNotEqual(tentative,96)
    self.assertEqual(cancelled,92)
    self.assertEqual(no_excitation,98)
    print('CANCEL_MEMORY',json.dumps({'after_cancel':cancelled,'without_previous_dither':no_excitation,
                                     'residual':cancelled-no_excitation}),flush=True)

  def test_can_quantization_full_burst_bias(self):
    h=ReleaseHarness(self); c=h.controller
    factor=57; base=43
    c.params.EPS_DITHER_AMPLITUDE=6
    c.eps_dither_start_frame=0; c.eps_dither_sign=1
    baseline_raw=round(base*100/factor)
    residuals=[]; requested=[]
    for k in range(24):
      c.frame=k*5; d=c._eps_dither(); requested.append(d)
      raw=round((base+d)*100/factor)
      residuals.append((raw-baseline_raw)*factor/100)
    print('ENCODED_BURST',json.dumps({'requested_sum':sum(requested),'encoded_residual_sum':sum(residuals),
                                     'encoded_residual_mean':sum(residuals)/24}),flush=True)
    self.assertEqual(sum(requested),0)
    self.assertNotAlmostEqual(sum(residuals),0)

  def test_early_rearm_cancels_dither(self):
    h=ReleaseHarness(self); c=h.controller
    c.params.EPS_DITHER_AMPLITUDE=6
    c.eps_dither_rng=random.Random(0)
    while c.frame<=100: h.step()
    self.assertGreater(c.eps_dither_start_frame,0)
    c.frame=105
    with patch.object(c,'_should_preempt_eps_rearm',return_value=True):
      row=h.step()
    self.assertEqual(row[1:],(0,0,2))
    self.assertEqual(c.eps_dither_start_frame,-1)

  def test_zero_amplitude_matches_disabled_dither_methods(self):
    def run(stubbed):
      random.seed(77)
      h=ReleaseHarness(self); c=h.controller
      c.params.EPS_DITHER_AMPLITUDE=0
      if stubbed:
        c._schedule_eps_dither=lambda:None
        c._cancel_eps_dither=lambda:None
        c._eps_dither=lambda:0
      result=[]
      original=c.update
      def record(*args):
        actuators,msgs=original(*args)
        result.append((actuators.to_dict(),[(a,bytes(d),b) for a,d,b in msgs]))
        return actuators,msgs
      c.update=record
      for frame in range(1500):
        if frame==101:h.cs.steering['DRIVER_TORQUE']=18
        if frame==103:h.cs.steering['DRIVER_TORQUE']=0
        if frame==301:h.cs.eps_active=False;h.cs.eps_state_lka=2
        if frame==309:h.cs.eps_active=True;h.cs.eps_state_lka=3
        if frame==401:h.cc.latActive=False
        if frame==403:h.cc.latActive=True
        if frame==501:h.cs.eps_active=False;h.cs.eps_state_lka=4
        if frame==509:h.cs.eps_active=True;h.cs.eps_state_lka=3
        if frame==601:h.cs.speed_kph=50
        if frame==607:h.cs.speed_kph=72
        h.step()
      return result
    self.assertEqual(run(False),run(True))
    print('ZERO_AMPLITUDE_EQUIVALENCE',json.dumps({'frames':1500,'all_can_and_actuators_equal':True}),flush=True)

  def test_actual_transmitted_full_burst_and_truncated_burst(self):
    def run(amplitude,jump_at=None):
      h=ReleaseHarness(self); c=h.controller
      c.params.EPS_DITHER_AMPLITUDE=amplitude; c.eps_dither_rng=random.Random(0)
      results={}; start=None
      for _ in range(1000):
        frame=c.frame
        if frame==jump_at:h.cc.actuators.torque=-1
        row=h.step()
        if frame==150:start=c.eps_dither_start_frame
        results[frame]=(row[1]*row[2]/100,c.apply_torque_scaled_last,c.eps_dither_start_frame)
      return start,results
    start,excited=run(6)
    _,base=run(0)
    residual=sum(excited[k][0]-base[k][0] for k in range(start,start+120,5))
    self.assertNotAlmostEqual(residual,0)
    jump=start+30
    _,truncated=run(6,jump)
    _,base_jump=run(0,jump)
    print('ACTUAL_WIRE_BURST',json.dumps({'start':start,'complete_burst_sum_residual':residual,
                                        'jump_frame':jump,'cancelled_pending':truncated[jump][2],
                                        'cancel_frame_output':truncated[jump][0],
                                        'no_dither_same_frame':base_jump[jump][0]}),flush=True)
    self.assertEqual(truncated[jump][2],-1)
    self.assertNotEqual(truncated[jump][0],base_jump[jump][0])


if __name__=='__main__': unittest.main()

```

## Appendice C — output dei probe

```text
ACTUAL_WIRE_BURST {"start": 645, "complete_burst_sum_residual": 2.8500000000000014, "jump_frame": 675, "cancelled_pending": -1, "cancel_frame_output": 3.0, "no_dither_same_frame": 5.0}
.BRAKE_STALE {"frame": 101, "brake_known": true, "raw_torque": 75, "factor": 57, "accepted": false}
.ENCODED_BURST {"requested_sum": 0, "encoded_residual_sum": 2.8499999999999988, "encoded_residual_mean": 0.11874999999999995}
.CANCEL_MEMORY {"after_cancel": 92, "without_previous_dither": 98, "residual": -6}
..LIMIT_COUNTEREXAMPLE {"base_request": 44, "previous_output": 35, "dither_request": -3, "total_output": 41, "base_only_from_same_previous": 43, "actual_increment": -2}
...SHORT_ACTIVE {"release": [101, 0, 0, 2], "resumed": [[102, 0, 0, 2], [103, 0, 0, 2], [104, 0, 0, 2], [105, 14, 57, 4], [106, 14, 57, 4], [107, 14, 57, 4], [108, 14, 57, 4], [109, 14, 57, 4], [110, 28, 57, 4], [111, 28, 57, 4]], "activation_before": 5, "activation_after": 5, "takeover_req": 0, "status": 4}
.SHORT_LADDER {"first": [0, 0, 10, 3], "release": [1, 0, 0, 2], "resumed": [5, 0, 20, 4]}
.ZERO_AMPLITUDE_EQUIVALENCE {"frames": 1500, "all_can_and_actuators_equal": true}
..
12 passed in 0.60s

```
