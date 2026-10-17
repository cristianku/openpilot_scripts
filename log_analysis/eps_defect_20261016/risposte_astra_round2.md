# EPS Defect PSA 3008 — conclusioni Astra, round 2

**Data:** 16 ottobre 2026  
**Destinatario:** Claude, per revisione e preparazione locale.  
**Sorgenti verificate:** opendbc HEAD `4ea63ca816146ad979612833d5871dd906564ae5`, con patch locale a 100 Hz; openpilot/sunnypilot `a8b556a07736dbbe92949875dc92ec9860db1730`.

## Decisioni principali

1. **Non considerare pronta per il giro la patch a 100 Hz nella forma attuale.** La ripetizione in condizioni stabili passa la safety, ma la cache ripete un comando attivo per altri quattro cicli dopo un cambio urgente di stato. Proporre a Cristian una correzione locale circoscritta e i relativi test prima di applicarla.
2. **Dither spento durante il confronto a 100 Hz.** Il parametro locale risulta ancora `EPS_DITHER_AMPLITUDE = 6`: il valore zero è il piano di prova, non una modifica eseguita da Astra.
3. **Puntare a 30 minuti effettivi con laterale disattivo e 30 con laterale attivo**, distribuiti preferibilmente su più giri. Zero Defect in 30 minuti dà un limite superiore Poisson unilaterale al 95% di circa **6 eventi/ora**, con le riserve sotto.
4. **Non rimuovere `aa0ac919b` per il giro su strada.** Il margine SPI corregge un problema documentato di protocollo; non c'è evidenza che rimuoverlo sia una prova sicura o risolutiva.
5. **Diagnosi EPS: TX `0x6B5`, RX attesa `0x695`, non `0x6BD`.** Bus 0 è il primo candidato; risposta e supporto a `19 02 FF` non sono ancora verificati sul veicolo. Offroad standard significa `NO_OUTPUT`, quindi la query non è eseguibile rispettando contemporaneamente l'assenza di cambi di modalità. Lo script preparato si ferma in questa condizione.

**Non sono stati modificati il controller, i parametri della vettura, il firmware o la safety. Nessun SSH, invio CAN, cambio di sessione o operazione sul comma è stato eseguito.** Sono stati aggiunti soltanto questo documento, strumenti locali di verifica e risultati nella cartella autorizzata.

## 1. Revisione della patch a 100 Hz

### Finding prioritario: cache non invalidata fuori dai cinque cicli

`lat_active` viene calcolato a ogni `update()`, ma `_reset_lat_state()`, l'override del guidatore e la costruzione di `lka_msg_last` vengono eseguiti soltanto quando:

```python
self.frame % self.params.STEER_STEP == 0
```

Negli altri quattro cicli viene accodato il vecchio `lka_msg_last`, anche se nel frattempo le condizioni sono cambiate.

Ho riprodotto questi cinque casi con il controller reale, senza cambiare i sorgenti:

| Cambio immediatamente dopo un aggiornamento sterzo | Ripetizioni del vecchio frame attivo | Aggiornamento al ciclo sterzo successivo |
|---|---:|---|
| `CC.latActive = False` | 4 | Neutro |
| EPS entra in Defect, stato 4 | 4 | Neutro |
| Velocità scende sotto 51 km/h | 4 | Neutro |
| EPS esce dallo stato Active | 4 | Coppia zero, procedura di attivazione |
| Coppia grezza guidatore supera la soglia | 4 | Coppia zero |

Il ritardo aggiuntivo dalla rilevazione al successivo aggiornamento è fino a **40 ms**. I payload della riproduzione sono in [review_lka_100hz.jsonl](review_lka_100hz.jsonl).

Il controllo a 20 Hz aveva già una granularità temporale simile: la novità è inviare altri frame attivi dopo che il software ha già osservato il cambio. Non è dimostrato che questo provochi il Defect; è un problema concreto di coerenza delle transizioni della patch.

**Proposta da sottoporre a Cristian prima di modificare:** mantenere a 20 Hz il calcolo ordinario di coppia e scaletta, ma gestire a ogni ciclo le condizioni urgenti che richiedono coppia zero/uscita dall'attivo. Il frame in cache e il riferimento di coppia del controller devono riflettere il rilascio. La logica di rearm e gli avvisi non vanno riscritti incidentalmente.

Non tutte le transizioni hanno lo stesso messaggio: disingaggio/Defect/soglia usano il percorso inattivo; l'override guidatore usa il rilascio della coppia nel percorso attivo. Evitare un unico reset indiscriminato che cambi anche la semantica del rearm.

### Safety: i frame identici sono accettati, con condizioni

Ho compilato in `/private/tmp` la safety locale e provato **2.400 frame**, con:

- intervallo simulato 10 ms;
- contenuto cambiato ogni cinque frame;
- salita fino a 150 unità effettive;
- entrambi i segni;
- fattori 25, 37, 65 e 100.

**Tutti accettati**, in assenza di override, freno, perdita di autorizzazione o altre violazioni.

La spiegazione nel codice è:

- `desired_torque_last` viene aggiornato al valore ricevuto; una ripetizione ha delta zero;
- `rt_torque_last` viene aggiornato in base al tempo trascorso, non al numero di copie;
- `MAX_RT_INTERVAL` è 250 ms;
- con `max_rt_delta = 150`, l'intero intervallo globale ammesso `[-150, +150]` rimane comunque dentro il controllo RT implementato. Non emerge una nuova restrizione causata dalle copie;
- il ramo PSA per coppia zero azzera i riferimenti e aggiorna il timer: ripetere un neutro mantiene tali riferimenti a zero;
- questo percorso torque non impone un limite di frequenza TX a 20 Hz. L'accettazione della safety non prova l'accettazione OEM a 100 Hz.

**Eccezione importante: dopo uno scarto la cache può continuare a essere rifiutata.** Ho riprodotto:

```text
coppia effettiva 32 accettata
DRIVER_TORQUE raw = 18 -> raw*3 = 54 > 50
frame cached 32 -> rifiutato; riferimenti safety azzerati
DRIVER_TORQUE torna a 0
stesso frame cached 32 -> ancora rifiutato: salto da 0 superiore a 8
frame neutro, poi coppia 8 -> accettati
```

Questo comportamento di reset è già nella safety. Aumentare la frequenza non deve essere interpretato come garanzia che tutte le copie arrivino al bus. Monitorare `src=192` e correggere il rilascio nel controller; **non allentare la safety**.

### Scaletta, rearm e primo avvio

- Il numero di avanzamenti della scaletta rimane a 20 Hz: cinque copie non equivalgono a cinque chiamate di `_activate_eps()`.
- Dopo un frame inattivo con STATUS 2, l'attivazione sale normalmente a 3 e 4. Se il processo parte già con richiesta attiva, `status` iniziale 2 viene incrementato a 3 al primo calcolo: è comportamento preesistente, non introdotto dalla cache.
- `_deactivate_eps()` imposta STATUS 2, fattore zero e latch di disattivazione. Se l'EPS risulta ancora Active, mantiene la disattivazione; la ripartenza dipende dalla successiva osservazione dell'EPS non attivo.
- I timer di rearm sono basati su frame/tempo e non sul numero di messaggi accodati; la patch non rende il rearm cinque volte più rapido.
- `lka_msg_last = None` non crea normalmente un buco iniziale: `self.frame` parte da zero, quindi il primo `update()` costruisce il frame prima del blocco che lo invia.
- Il commento della patch che attribuisce il 40/60 o 30/70 direttamente al bus è troppo assertivo: va corretto per distinguere gli intervalli degli echo registrati dai tempi fisici di TX.

### Test prima di considerarla pronta

I tre test presenti passano, ma verificano frequenza e stabilità del contenuto durante l'attivazione. Il test chiamato “engaged” non dimostra di raggiungere EPS Active con coppia non nulla, perché non inietta una risposta EPS Active.

Servono casi con coppia effettivamente non nulla e cambio al ciclo 1, 2, 3 e 4: disingaggio, Defect, soglia velocità, override raw, uscita EPS Active. Verificare rilascio immediato, ripresa dopo rilascio, scaletta completa e rearm nominale/anticipato, anche con EPS che risponde in ritardo. Non trasformare questi controlli in una modifica della safety.

## 2. Protocollo e metriche del giro

### Durata e interpretazione statistica

Per zero eventi in un'esposizione T, il limite superiore Poisson unilaterale al 95% è:

```text
lambda_upper95 = -ln(0,05) / T_ore ≈ 2,996 / T_ore
```

| Minuti senza Defect, per ciascuno stato | Limite superiore 95%, eventi/ora |
|---:|---:|
| 5 | 35,95 |
| 10 | 17,97 |
| 15 | 11,98 |
| 30 | 5,99 |
| 60 | 3,00 |

Assumendo per ipotesi tassi fissi di 64/h e 111/h, bastano circa 2,81 e 1,62 minuti senza eventi per rendere improbabile quel preciso tasso al livello 5%. **Non è una prova convincente del fix:** sappiamo già che il baseline varia tra giri, segmenti e fasi, fino a zero eventi.

Per un limite nominale inferiore al 10% di quei tassi servirebbero circa 28,1 minuti senza eventi contro 64/h e 16,2 minuti contro 111/h, trattando i tassi storici come noti. Sono stime illustrative: non incorporano l'incertezza del baseline né la dipendenza tra eventi.

**Protocollo proposto:** 30 minuti cumulativi con `latActive=False` e 30 con `latActive=True`, preferibilmente in più giri/avvii naturali. Annotare condizioni, velocità, software esatto e transizioni. Per la parte attiva conta il tempo realmente attivo, non la durata totale del tragitto. Nessuna prova hands-off: il guidatore resta responsabile della guida e pronto a riprendere il controllo.

Confrontare esposizioni simili per velocità e condizioni. Se si decide di contare soltanto tratti sopra 51 km/h, ricalcolare anche il baseline con lo stesso filtro: i tassi storici aggregati non sono automaticamente equivalenti a quel sottoinsieme.

Uno o più Defect richiedono l'analisi dell'episodio; zero eventi è un risultato favorevole con un limite misurato, non una dimostrazione che il fault sia eliminato.

### Metriche a 100 Hz

La metrica primaria resta **numero di episodi Defect per ora di esposizione**, separato per `latActive`. Un episodio è un ingresso in stato 4, non ogni frame che riporta 4.

Per `sendcan` e gli echo `0x3F2/src128`, separatamente:

- frequenza media e conteggio frame;
- intervalli p50, p95, p99, p99,9 e massimo;
- percentuale e numero di intervalli oltre 20, 30, 50 e 100 ms;
- coppie con timestamp identico, indice di raccolta in batch;
- distribuzione dei buchi nelle finestre attorno a Defect e `0x795`;
- eventuali sequenze di scarti `0x3F2/src192`, distinguendo avvio/transizioni e regime attivo stabile.

Il contenuto ripetuto non ha un contatore che renda sempre univoco l'abbinamento sendcan/echo: non presentare un semplice accoppiamento per ordine come misura certa della latenza di ogni singolo frame.

Come soglie esplorative, indagare buchi `sendcan >20 ms` e echo `>30 ms`; 50–100 ms meritano ispezione puntuale. Non sono soglie OEM validate né criteri autonomi di sicurezza. A 100 Hz si possono osservare intervalli echo zero seguiti da 20 ms anche con trasmissione regolare: evitare di usare “100% a 10 ms” come obiettivo.

Controllare inoltre `steerFaultTemporary`, stato EPS grezzo, `STEERING_REBOOT_REQUEST`, condizioni di override/freno, `controlsAllowedLateral`, contatori `safetyTxBlocked`, overflow/lost frame, bus-off e incremento di `spiErrorCount`. La correlazione 1:1 tra 0x795 e Defect rimane da verificare anche dopo la modifica.

### Strumento preparato

Ho aggiunto [scripts/cadence_100hz.py](scripts/cadence_100hz.py), senza alterare `segstate.py`. Legge solo rlog, separa le esposizioni secondo `latActive`, decodifica EPS_STATE_LKA dal DBC, segnala errori/segmenti intermedi mancanti e non calcola intervalli attraverso cambi di stato o segmenti mancanti. Non conta come nuovo ingresso un primo campione già in Defect, perché manca il fronte osservato.

Il tempo è quello degli eventi registrati, non il tempo hardware sul filo. Non esegue il filtro velocità. Il riepilogo SPI first/last non sostituisce l'analisi di reset e incrementi intermedi del contatore.

Comando per un futuro log, dopo aver organizzato le cartelle per route come indicato nelle domande:

```sh
CEREAL_DIR=/Users/cristianku/GitHub/COMMA.AI/CRISTIANKU/new_openpilot_psa_torque_sunny_testing/openpilot/cereal \
uv run /Users/cristianku/GitHub/COMMA.AI/CRISTIANKU/openpilot_scripts/log_analysis/eps_defect_20261016/scripts/cadence_100hz.py \
  /tmp/routes/ID_ROUTE
```

Verificato sul baseline `0000010f--8517150ed6`: 4 segmenti leggibili, 6 Defect, 6 fronti 0x795, 10 scarti 0x3F2, 229,823 s classificati inattivi; echo p99 62,773 ms e massimo 64,104 ms. Risultato completo in [cadence_baseline_10f.jsonl](cadence_baseline_10f.jsonl). Questo è un log a 20 Hz: non è una prova dei 100 Hz.

## 3. Ritrovare il software precedente alla reinstallazione

### Dove cercare e cosa prova ciascuna traccia

Ordine di utilità:

1. Vecchi rlog/qlog/bootlog precedenti alla reinstallazione, se esistono ancora: `initData.gitCommit`, versione e dati di avvio identificano la sessione registrata. I log indicati finora sono successivi alla reinstallazione.
2. Reflog e oggetti Git del vecchio checkout, o di copie rimaste sul Mac: possono conservare i tip di branch force-pushati che `git log --all` non raggiunge più.
3. Checkout rimasti in `/data/safe_staging/old_openpilot`, `finalized` o altre copie esplicitamente presenti. Sono candidati, non backup storici garantiti.
4. Log manager/pandad/boot: cercare commit, versione panda e firma effettiva. Il wrapper `pandad.py` può aggiornare il firmware: il gitlink panda identifica il sorgente atteso, non dimostra da solo quale binario girasse in passato.
5. Params `GitCommit`, `GitBranch`, `Version`, `LastUpdateTime`: normalmente descrivono lo stato corrente/ultimo, non una cronologia. `CarParamsPersistent` conserva dati di fingerprint/FW delle ECU e non è una prova della vecchia versione openpilot.

`/persist` può sopravvivere a reinstallazioni e contenere dati hardware/calibrazione, ma non è un archivio garantito di versioni openpilot. AGNOS corrente e slot OS non identificano da soli la vecchia applicazione. Non stampare indiscriminatamente tutti i params o i contenuti di `/persist`: potrebbero contenere credenziali e dati privati.

### Comandi in sola lettura da far eseguire a Cristian

I comandi seguenti **non sono stati eseguiti da Astra**. Non avviano Panda/pandad e non modificano params, safety, checkout o servizi.

```sh
ssh comma 'bash -s' <<'SH'
export GIT_OPTIONAL_LOCKS=0
uname -a
for f in /VERSION /etc/os-release; do
  if [ -r "$f" ]; then cat "$f"; fi
done
for k in GitCommit GitCommitDate GitBranch GitRemote Version LastUpdateTime IsOnroad; do
  f="/data/params/d/$k"
  if [ -r "$f" ]; then
    printf '%s: ' "$k"
    cat "$f"
    printf '\n'
  fi
done
for d in /data/openpilot /data/safe_staging/old_openpilot /data/safe_staging/finalized; do
  if [ -d "$d/.git" ] || [ -f "$d/.git" ]; then
    printf '\nCheckout: %s\n' "$d"
    git -C "$d" show -s --format='%H %cI %s' HEAD
    git -C "$d" reflog show --all --date=iso --format='%h %gD %gs' | head -100
    git -C "$d" ls-tree HEAD panda opendbc_repo
  fi
done
for d in /data/swaglog /data/boot /data/media/0/realdata /persist; do
  if [ -d "$d" ]; then
    printf '\nInventario: %s\n' "$d"
    find "$d" -maxdepth 2 -type f \( -name '*boot*' -o -name '*.log' -o -name 'qlog*' -o -name 'rlog*' \) -print 2>/dev/null | head -100
  fi
done
SH
```

Leggere successivamente soltanto i file di log pertinenti identificati dall'inventario. Non usare `pandad.py` per “leggere la versione”: il suo percorso di avvio può flashare il panda.

### Ricostruzione Git locale

Il checkout generato corrente conserva un solo commit raggiungibile con il titolo richiesto. Ho verificato:

```text
custom: a8b556a07736dbbe92949875dc92ec9860db1730
parent/base: f7bc31f208848aeafeda0800fa4a13c4b541d871
panda gitlink: 4230530f5ec4c7f11971f868ae9930b3547346eb
opendbc gitlink: 4ea63ca816146ad979612833d5871dd906564ae5
```

Il commit custom modifica `.gitmodules`, `opendbc_repo`, `torqued.py` e il gitlink neural data. Per questo commit il parent identifica la base immediata; verificare sempre il diff prima di generalizzare a tutti i commit con lo stesso titolo.

Comandi in sola lettura, anche su altre copie locali del fork:

```sh
git log --all --date=iso --format='%H %P %cI %s' \
  --grep='Update Peugeot 3008 Sunny testing repository pointers'
git reflog show --all --date=iso --format='%H %gD %gs'

# Per uno SHA candidato recuperato, senza fare checkout:
git show -s --format='%H%n%P%n%cI%n%B' SHA_CANDIDATO
git diff-tree --no-commit-id --name-only -r SHA_CANDIDATO
git ls-tree SHA_CANDIDATO panda opendbc_repo
git show SHA_CANDIDATO:openpilot/selfdrive/pandad/spi.cc
git merge-base --is-ancestor aa0ac919b SHA_CANDIDATO
```

L'ultimo comando restituisce 0 se il commit SPI è antenato, 1 se non lo è; 128 se manca un oggetto/riferimento. La presenza di un antenato non esclude un successivo revert: leggere anche il file effettivo.

Se reflog e riferimenti non bastano, `git fsck --full --no-reflogs --unreachable` può elencare oggetti non più raggiungibili, senza recuperarli su disco; **non aggiungere `--lost-found`**. Non eseguire fetch, gc, prune, reset o checkout per questa ricerca. Se la reinstallazione ha eliminato anche oggetti e log, non c'è un metodo certo per ricostruire quale commit fosse effettivamente installato dalla sola cronologia odierna del branch.

## 4. Analisi di aa0ac919b e lock SPI

### Cosa blocca cosa

Sì: TX e RX usano `hw_lock`, e `spi_transfer()` mantiene il lock durante la singola transazione SPI, compresi ACK e turnaround.

Il commit introduce due attese:

1. prima del nuovo header, fino a completare 400 µs dall'ultima attività registrata;
2. dopo HACK e prima del payload, altri 400 µs.

La prima può essere già scaduta quando si entra. **Il costo ordinario è circa 400–800 µs per transazione, più ioctl, trasferimento e attesa ACK; non 400 µs per frame CAN.** Il lock viene rilasciato tra transazioni e tra tentativi del retry, non dopo l'intero `bulk_transfer()`. Il backoff NACK avviene fuori dal lock, ma ritarda comunque il completamento della chiamata TX.

`SPI_BUF_SIZE=2048`, chunk utile del bulk transfer 1984 byte. Un frame CAN classico con payload da 8 byte occupa 14 byte nel protocollo host/panda. Il traffico CAN inoltrato viene gestito dal panda: non richiede una transazione SPI host separata per ciascun frame inoltrato; le copie ricevute/echo contribuiscono al volume RX host.

### Dati misurati sulla route 108

Ho riletto gli rlog dei segmenti 4–7, senza video:

| Misura | Intervallo osservato |
|---|---:|
| RX bus 0 | 1.479,7–1.482,4 frame/s |
| RX bus 1 | 962,1–963,9 frame/s |
| RX bus 2 | 234,8–235,1 frame/s |
| TX bus 0 | 234,5–234,9 frame/s |
| TX bus 1 | 88,9–89,7 frame/s |
| TX bus 2 | 1.485,0–1.491,9 frame/s |
| Frame per evento CAN, media | 45,17–45,31 |
| Frame per evento CAN, massimo | 87 |
| `spiErrorCount` | **22, invariato nei quattro segmenti** |

Circa 45 frame × 14 byte = 630 byte medi, circa 1.218 byte al massimo osservato se tutti hanno payload 8 byte: compatibili con un singolo chunk RX. A 50 MHz, il solo payload da 630 byte richiede circa **101 µs** sullo SPI. Le chiamate e gli ACK aggiungono tempo; questa è una stima di ordine di grandezza, non una misura del tempo di lock.

Con questi numeri un normale RX può ritardare TX di una frazione di millisecondo o circa un millisecondo. Più transazioni di controllo/seriale, scheduling e code possono aggiungere ritardo. ACK lenti/errori possono trattenere il lock molto più a lungo: i timeout sono clampati ad almeno 20 ms e RX può attendere fino al default di 500 ms. Il percorso di recupero non fornisce una garanzia generale di latenza massima breve.

**Non emerge un meccanismo ordinario che trasformi direttamente i 400 µs in scalini di 10 ms.** Il polling RX a 100 Hz quantizza già l'osservazione degli echo. Il lock può contribuire al ritardo reale e allo spostamento di fase, ma i 3/7/11/21 ms sendcan→echo non permettono di separare questi contributi. Il contatore SPI stabile non dimostra assenza di qualunque attesa o NACK di backpressure.

### Rimuovere il commit?

**No come primo esperimento su strada.** La [PR originale #38464](https://github.com/commaai/openpilot/pull/38464) documenta collisioni ai turnaround, errori e retry sotto carico; la guardia serve a lasciar riarmare il periferico SPI. I numeri della descrizione iniziale della PR non sostituiscono il diff finale locale, che usa 400 µs.

Non cambiare firmware o safety non rende automaticamente innocua una modifica al trasporto CAN. Prima avrebbe senso una misura su banco dei tempi prima/dopo `hw_lock`, durata transazione, ACK/retry e volume RX, mantenendo la guardia. Tale strumentazione non è stata implementata né autorizzata per il dispositivo.

## 5. DTC EPS: indirizzi, sessione e script

### Cosa sappiamo

`values.py` contiene:

```text
EPS TX: 0x6B5
PSA_RX_OFFSET: -0x20
RX attesa: 0x695
query FW configurate sui bus 0, 1 e 2, senza OBD multiplexing
sessione usata dalla query FW: 10 01, default
```

**Bus 0 è un candidato motivato, non un fatto diagnostico già provato:** è il bus dei segnali EPS principali, ma la configurazione FW prova tutti e tre i bus. Nel campione `10e:0` ho trovato richieste `10 01` su 0x6B5, ma nessuna risposta 0x695; gli altri campioni ispezionati non aggiungono una risposta. Non inventare quindi un riscontro positivo del veicolo.

La richiesta completa è **`19 02 FF`**, non soltanto `19 02`: il terzo byte è la maschera di stato. Risposta positiva attesa `59 02`, availability mask e record da tre byte DTC più un byte status. Riferimento primario d'implementazione: [udsoncan, ReadDTCInformation](https://udsoncan.readthedocs.io/en/latest/udsoncan/services.html#readdtcinformation-0x19).

Il servizio legge i DTC e non li cancella. Il supporto su questo EPS e nella sessione corrente va verificato. Tentare prima senza alcun cambio di sessione; se arriva un NRC per sessione/servizio non supportato o un timeout, registrarlo e fermarsi. La query FW in default session non prova che `0x19` sia supportato.

### Vincolo operativo: offroad e safety invariata

Nel checkout verificato `send_panda_states()` imposta `NO_OUTPUT` quando non onroad. La whitelist della modalità PSA non autorizza 0x6B5. Pertanto non si può promettere una lettura DTC funzionante tramite quel trasporto senza predisporre una modalità diagnostica consentita.

Lo script **non predispone tale modalità**: non chiama `set_safety_mode`, non ferma/riavvia processi, non apre direttamente Panda, non invia heartbeat, non modifica OBD multiplexing o params e non cambia sessione. Sulla configurazione offroad standard si fermerà prima della query. Questo è un limite reale delle condizioni richieste, non un motivo per aggirare la safety.

Per una lettura effettiva serve un trasporto diagnostico già consentito e verificato, oppure uno strumento diagnostico esterno. Un eventuale cambiamento temporaneo di modalità sul comma sarebbe un'operazione separata da autorizzare esplicitamente; non è incluso né eseguito.

### Script preparato e limiti di verifica

[scripts/read_eps_dtc.py](scripts/read_eps_dtc.py) usa `opendbc.car.uds.UdsClient` con un adapter sui servizi `can`/`sendcan` di pandad:

- indirizzi fissi TX 0x6B5, RX 0x695, bus 0;
- unico servizio UDS `19 02 FF`, più ISO-TP flow control necessario alla risposta multiframe;
- controllo offroad e rifiuto di `deviceState.started=True`;
- richiede un solo panda, stato aggiornato, modalità **ELM327 già presente** e parametro senza OBD multiplexing;
- ricontrolla le condizioni durante la richiesta e rifiuta i frame scartati dalla safety;
- limite totale 20 s; nessun tentativo automatico su altri bus/sessioni;
- restituisce codici DTC grezzi e byte status, senza inventare descrizioni PSA.

**Verificato solo localmente:** parsing, rifiuto dei servizi non ammessi, controlli di stato e scambio multiframe con il vero UdsClient contro un EPS simulato. Non è stato verificato il trasporto IPC sul comma né il supporto del suo EPS.

Decodifica offline, senza collegamento:

```sh
python3 scripts/read_eps_dtc.py --decode 5902ff12345601aabbcc02
```

Solo per Cristian, con vettura parcheggiata e quadro acceso, se il trasporto diagnostico è già stato predisposto legittimamente: dal Mac, nella cartella di questo documento, lo script può essere passato via stdin senza copiarlo sul dispositivo:

```sh
ssh comma 'cd /data/openpilot && PYTHONDONTWRITEBYTECODE=1 /usr/local/venv/bin/python -' \
  < scripts/read_eps_dtc.py
```

**Questo comando non è stato eseguito.** Con `NO_OUTPUT` il risultato atteso è un rifiuto esplicito prima della trasmissione, non una lettura riuscita.

## Verifiche riproducibili e file aggiunti

### Test locali eseguiti

Dal repository opendbc:

```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider \
  opendbc/car/psa/tests/test_lka_100hz.py
```

Esito: **3 passed**. Non ho rieseguito l'intera suite PSA: i 67 fallimenti car e i 12 safety citati nelle domande restano risultati riportati da Claude, non risultati riconfermati in questa revisione.

Riproduzione delle transizioni e safety compilata, ora conservata stabilmente:

```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python \
  /Users/cristianku/GitHub/COMMA.AI/CRISTIANKU/openpilot_scripts/log_analysis/eps_defect_20261016/scripts/review_lka_100hz.py
```

La prima esecuzione era `/private/tmp/review_lka_round2.py`, poi copiata nello script sopra. Il loader usa il sorgente locale `libsafety_py.py` e sposta solo gli output del compilatore in `/private/tmp`; non cambia i sorgenti safety. Esito finale: cinque casi con quattro ripetizioni stale, **2.400 frame accettati** in regime valido, caso di scarto/azzeramento/ripresa confermato. Output: [review_lka_100hz.jsonl](review_lka_100hz.jsonl).

Test degli strumenti nuovi, dal repository opendbc:

```sh
PYTHONDONTWRITEBYTECODE=1 \
PYTHONPATH=/Users/cristianku/GitHub/COMMA.AI/CRISTIANKU/openpilot_scripts/log_analysis/eps_defect_20261016/scripts \
.venv/bin/python -m unittest test_round2_tools -q
```

Esito: **7 test OK**, tutti offline. Questi test non attestano una lettura DTC sul veicolo.

### Analisi log eseguite

L'interprete già disponibile contiene pycapnp e zstandard. Nessuna dipendenza installata.

Comando dell'audit finale SPI/diagnostica, che riproduce anche i controlli inizialmente eseguiti via Python stdin:

```sh
PYTHONDONTWRITEBYTECODE=1 \
CEREAL_DIR=/Users/cristianku/GitHub/COMMA.AI/CRISTIANKU/new_openpilot_psa_torque_sunny_testing/openpilot/cereal \
/Users/cristianku/.cache/uv/environments-v2/tx-vs-echo-07910a42fe36946a/bin/python \
  /Users/cristianku/GitHub/COMMA.AI/CRISTIANKU/openpilot_scripts/log_analysis/eps_defect_20261016/scripts/audit_spi_round2.py \
  /Users/cristianku/Downloads/comma_logs/00000108--d343db86dc--4/rlog.zst \
  /Users/cristianku/Downloads/comma_logs/00000108--d343db86dc--5/rlog.zst \
  /Users/cristianku/Downloads/comma_logs/00000108--d343db86dc--6/rlog.zst \
  /Users/cristianku/Downloads/comma_logs/00000108--d343db86dc--7/rlog.zst \
  /Users/cristianku/Downloads/comma_logs/0000010e--a8ba9cec69--0/rlog.zst \
  /Users/cristianku/Downloads/comma_logs/0000010f--8517150ed6--0/rlog.zst \
  > /private/tmp/audit_spi_round2.jsonl
```

Output copiato in [audit_spi_round2.jsonl](audit_spi_round2.jsonl).

Comando di verifica del riepilogo cadenza sul baseline:

```sh
PYTHONDONTWRITEBYTECODE=1 \
CEREAL_DIR=/Users/cristianku/GitHub/COMMA.AI/CRISTIANKU/new_openpilot_psa_torque_sunny_testing/openpilot/cereal \
/Users/cristianku/.cache/uv/environments-v2/tx-vs-echo-07910a42fe36946a/bin/python \
  /Users/cristianku/GitHub/COMMA.AI/CRISTIANKU/openpilot_scripts/log_analysis/eps_defect_20261016/scripts/cadence_100hz.py \
  /private/tmp/claude-501/-Users-cristianku-GitHub-COMMA-AI-CRISTIANKU-opendbc/320221af-d231-491b-aded-0fb95c758f45/scratchpad/today/0000010f--8517150ed6 \
  > /private/tmp/cadence_100hz_baseline_round2.jsonl
```

La directory temporanea nell'ultimo comando è l'organizzazione per route usata nella verifica; i dati originali restano in Downloads. Per le esecuzioni future usare una directory per route persistente o ricreata come descritto nelle domande.

### Sorgenti principali ispezionate

- `opendbc/car/psa/carcontroller.py`, `carstate.py`, `values.py`, `psacan.py`;
- `opendbc/safety/modes/psa.h`, `elm327.h`, `opendbc/safety/lateral.h`, `declarations.h`;
- `opendbc/car/uds.py` e DBC PSA;
- nel checkout openpilot: `pandad.cc`, `panda.cc`, `panda.h`, `spi.cc`, `panda_comms.h`, `panda_safety.cc`, `pandad.py`, messaging e params;
- `git show aa0ac919b -- openpilot/selfdrive/pandad/spi.cc`, commit corrente, parent, gitlink e reflog locali.

I 19 script precedenti, il diff e i test forniti da Claude sono stati preservati. Nessun commit, push o aggiornamento del dispositivo.
