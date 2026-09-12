# Accelerazioni, decelerazioni e tabella candidata PSA — route 49

<!-- [longitudinal analysis] - START -->
Analisi del 12 settembre 2026, richiesta da Cristian per ricavare le tabelle del longitudinale dai log dashcam. **Risultato: due curve candidate di coppia con compensazione esplicita della pendenza e una verifica della richiesta di frenata. Nessuna modifica al controller.**

## Dati e metodo

- Stima sulla route `6616faac453a3064/00000049--a95dde6809`, confronto separato sulla precedente `6616faac453a3064/0000003a--e445e79563` della bibbia.
- Cristian conferma salita e poi discesa nella route 49; attivazioni/disattivazioni con freno e pulsante. I tentativi rifiutati verso la fine non sono dati di attuazione e non entrano nella calibrazione.
- CAN originale sul bus 1: `0x2B6`, `0x452`, `0x32D`, `0x38D`; marcia da `0x348` sul bus 0. Le unità di coppia sono quelle dichiarate dal DBC, Nm.
- Allineamento a 10 Hz con ultimo campione disponibile, età massima 150 ms. Accelerazione ottenuta dalla derivata di `carState.vEgoRaw` con Savitzky–Golay centrato di 1,1 s; conservati anche `aEgo` e i segnali CAN per confronto. Filtro offline, non proposta di filtro per il controller.
- Selezione: `ACC_STATUS=4`, CAN valido, pedali non premuti, velocità >2 m/s. Richieste GMP attive e richiesta decelerazione disattiva per la coppia; richiesta decelerazione attiva per la frenata. Escluse le sentinelle di coppia e la decelerazione inattiva `2.05`.
- Esclusione di un secondo prima/dopo le transizioni di validità, pedali o modo. Route 49: **179,8 s GMP e 55,1 s frenata**; route 3a: **93,4 s GMP e 23,0 s frenata**. Durate dopo selezione, non durata totale con ACC inserito.
- Regressione robusta `soft_l1`, scala 60 Nm, stimata soltanto sulla route 49. Intervalli descrittivi tramite 300 bootstrap di interi episodi GMP, non trattando i campioni consecutivi come indipendenti.

## Pendenza: perché la tabella sui soli m/s² era sbagliata

La prima aggregazione di coppia contro derivata della velocità mescolava salita e discesa. È conservata nei riepiloghi diagnostici, **non è la tabella proposta**.

La differenza `ACCEL_LONGI_CALIB - derivata_velocità` segue il termine `9.81*sin(pitch)` con correlazione **0,946** nella route 49 e **0,927** nella route 3a. `pitch` proviene da `carControl.orientationNED[1]`. Questo riscontro, insieme al percorso dichiarato da Cristian, giustifica l'inclusione della pendenza nell'analisi.

Non sono misure indipendenti di pendenza stradale: l'inclinazione stimata include errori di calibrazione, filtraggio e movimento della carrozzeria. Rimane un offset mediano di circa **0,16 / 0,15 m/s²** fra `ACCEL_LONGI_CALIB` e accelerazione corretta nelle due route. Non va interpretato automaticamente come vento o come una costante fisica da aggiungere.

La variabile di ingresso del fit è:

```python
a_equivalente = accelerazione_da_velocita + 9.81 * sin(pitch)
```

Per un eventuale controller la variabile di partenza sarebbe la richiesta di accelerazione, con gestione e verifica dell'orientamento. Questa analisi non implementa quel percorso e non dimostra che aggiungere il termine da solo produca il comportamento desiderato.

## Tabella candidata principale

Curva GMP di base, valida come proposta offline nel sottointervallo rappresentato. A pendenza nulla l'ingresso coincide con l'accelerazione; in salita/discesa **non** si usa direttamente `CC.actuators.accel` senza compensazione.

| Accelerazione equivalente (m/s²) | GMP_WHEEL_TORQUE (Nm DBC) | GMP_POTENTIAL_WHEEL_TORQUE (Nm DBC) |
|---:|---:|---:|
| 0,00 | 179 | 169 |
| 0,25 | 301 | 279 |
| 0,50 | 424 | 390 |
| 0,75 | 547 | 501 |
| 1,00 | 670 | 612 |

Forma dei punti, **non codice da incollare nell'attuale controller**:

```python
EQUIVALENT_ACCEL_BP = (0.0, 0.25, 0.5, 0.75, 1.0)
WHEEL_TORQUE_V = (179, 301, 424, 547, 670)
POTENTIAL_TORQUE_V = (169, 279, 390, 501, 612)
```

Fit sottostante: `wheel ≈ 178,5 + 491,7*a_equivalente`; `potential ≈ 168,6 + 443,2*a_equivalente`. I punti sono campioni della regressione, non medie esatte né misure indipendenti a ciascuna accelerazione. Il segnale potential ha quantizzazione di 4 Nm nel DBC; i numeri qui sono arrotondamenti del fit, la codifica deve rispettarne la risoluzione.

Il CSV riporta secondi/episodi osservati vicino a ogni punto e intervalli bootstrap: per esempio a +0,5 m/s², wheel 424 con intervallo descrittivo 389–474 Nm. Questi intervalli non coprono tutte le incertezze sistematiche.

Sono stati osservati valori equivalenti negativi in GMP, ma il fit lineare del potential diventerebbe negativo dove i campioni selezionati arrivano invece a zero. **La regione negativa richiede una mappa a tratti e non è proposta qui.** +1,5/+2 m/s² non sono coperti. Non usare il clipping agli estremi di questa tabella parziale per completare implicitamente il controllo.

## Confronto su una route diversa

Errore medio assoluto rispetto ai **comandi di coppia originali registrati**, non errore dell'accelerazione ottenuta guidando con openpilot:

| Campo, route 3a | Elkoled senza pitch | Elkoled con lo stesso pitch | Nuova curva con pitch |
|---|---:|---:|---:|
| Wheel | 163 Nm | 104 Nm | **59 Nm** |
| Potential | 134 Nm | 103 Nm | **70 Nm** |

La nuova curva riproduce meglio i comandi originali in questi dati. La route di confronto è separata, ma nota durante l'analisi esplorativa: non è un test prospettico cieco. Questo risultato non convalida stabilità, sicurezza o accuratezza dell'accelerazione del controller futuro. Si sta osservando un ACC originale già in controllo, con dinamiche di cambio e centraline proprie.

[Grafico coppia con compensazione pendenza](pitch-compensated-torque.png) · [Panoramica della route](route49-overview.png).

## Decelerazione: richiesta diretta, non tabella coppia

Nella route 49, sui tratti di frenata selezionati, `MDD_DESIRED_DECELERATION` va da **−1,30 a −0,05 m/s²**. La risposta ricavata dalla velocità segue già bene questa richiesta. Lo scarto minimo nella scansione esplorativa è circa 0,055 m/s² RMS a 0,4–0,5 s; nella route 3a il minimo è intorno a 0,7 s. Sono ritardi apparenti del sistema originale e del filtraggio, non un ritardo attuatore da copiare automaticamente in `interface.py`.

Con confronto fissato a +0,4 s, mantenuto anche sulla seconda route:

| Fascia richiesta route 49 | Secondi | Mediana richiesta | Mediana accelerazione osservata dopo 0,4 s |
|---:|---:|---:|---:|
| intorno a −1,25 | 6,2 | −1,30 | −1,27 |
| intorno a −1,00 | 15,3 | −0,95 | −0,97 |
| intorno a −0,75 | 9,9 | −0,70 | −0,73 |
| intorno a −0,50 | 12,3 | −0,45 | −0,49 |
| intorno a −0,25 | 7,6 | −0,25 | −0,29 |

I dati sostengono come base la richiesta di decelerazione diretta, con successiva taratura della retroazione; non giustificano una nuova tabella di coppia per il freno. **Il radar originale frena anche con richieste più deboli di −0,5 m/s²**: la nostra soglia fissa `BRAKE_ACCEL_THRESHOLD=-0.5` non ricostruisce l'intera scelta GMP/frenata originale. Non sostituirla con un'altra soglia inventata: la scelta deve considerare coppia disponibile, pendenza e stato del veicolo. Arresto, mantenimento e ripartenza non sono calibrati da questa selezione, che esclude v<=2 m/s.

## Vento, carico e controllo in retroazione

Una tabella è un comando iniziale, non un autoapprendimento. Nel checkout esaminato:

- GM configura `longitudinalTuning.kiV` non nullo (`opendbc/car/gm/interface.py`); `LongControl` confronta `a_target` e `CS.aEgo` e integra lo scarto.
- Ford documenta che la PCM compensa la pendenza per gas/accelerazione e usa `sin(pitch)*g` per la gestione dei bit freno/precarica (`opendbc/car/ford/carcontroller.py`).
- Toyota ha compensazioni legate all'inclinazione e alle sue variazioni (`opendbc/car/toyota/carcontroller.py`).
- PSA lascia il guadagno integrale al default zero. Non è stata implementata una taratura di questa correzione.

Il controllo in retroazione può contrastare errori persistenti dovuti anche a vento o carico, entro limiti e dinamica del sistema, senza doverli identificare singolarmente. Non equivale a imparare e salvare una mappa di coppia come i parametri laterali. Questa registrazione non misura vento, massa effettiva o pendenza con uno strumento indipendente, quindi non permette di separarli tutti né di validare un guadagno integrale da sola.

## Artefatti e riproduzione

- [candidate_torque_table.csv](candidate_torque_table.csv): tabella principale con pendenza, copertura e bootstrap.
- [calibration_results.json](calibration_results.json): fit, confronti, frenate, diagnostica e tabella alternativa da accordo fra sensori. La proposta principale è nella chiave `pitch_compensated`.
- `*-sources.json`: hash dei rlog sorgente; `*.npz`: segnali estratti e allineati, non originali modificati.
- [analyze.py](analyze.py): estrazione, selezione e riepiloghi; [report.py](report.py): regressioni, confronto, CSV e grafici.
- `sensor_agreement_diagnostic_table.csv` e `torque-calibration.png`: tentativo diagnostico precedente basato sui pochi tratti in cui i sensori concordano. Non scelto come proposta principale: copertura di soli 13,1 s e nessun vantaggio convincente sulla route di confronto.

Esecuzione dal Mac con le dipendenze già presenti (`numpy`, `scipy`, `matplotlib`, `pycapnp`, `zstandard`, modulo CAN opendbc locale):

```sh
python3 analyze.py
python3 report.py
```

Gli script usano il checkout locale `new_openpilot_psa_torque_sunny_testing` per lo schema Cap'n Proto e le due route nella bibbia. Per cambiare dati/DBC/schema rigenerare le cache di estrazione in una copia di lavoro; non trattare cache vecchie come nuova analisi.

Nessun comando inviato alla vettura, nessun aggiornamento del comma e nessuna modifica a `values.py`, `interface.py` o `carcontroller.py` durante questa analisi.
<!-- [longitudinal analysis] - END -->
