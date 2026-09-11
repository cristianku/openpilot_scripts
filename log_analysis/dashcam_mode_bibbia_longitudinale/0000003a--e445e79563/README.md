# Dashcam mode — riferimento longitudinale («la bibbia»)

Route: `6616faac453a3064/0000003a--e445e79563`.

Cristian ha indicato questa registrazione come riferimento per replicare il longitudinale, riferendo di aver fatto funzionare il longitudinale della vettura con Sunnypilot in dashcam mode.

## Acquisizione completata

Scaricata l’11 settembre 2026 tramite SSH in sola lettura da `comma`, percorso `/data/media/0/realdata/0000003a--e445e79563--*`.

- Tutti gli 8 segmenti presenti sul dispositivo, da `--0` a `--7`.
- 8 `rlog.zst` completi e 8 `qlog.zst`: 76.721.126 byte totali. Video non inclusi.
- SHA-256 di tutti i 16 file locali confrontati con quelli calcolati sul dispositivo: corrispondenza completa.
- Decompressione Zstandard e lettura integrale degli eventi Cap’n Proto riuscite per tutti i 16 file.
- Originali preservati nelle rispettive cartelle di segmento.
- Nessuna modifica, installazione, invio CAN o riavvio sul dispositivo.

## Identificazione della registrazione

- Intervallo monotono dei dati: 434.042 secondi (circa 7.23 minuti).
- Velocità massima registrata in `carState.vEgo`: 76.98 km/h.
- Versione openpilot da `initData`: `f544c80ffeb669ff5e5bcbbc372e610c6eb04898`, ramo `psa-torque-sunny-testing`.
- Tutti i messaggi `carParams` presenti riportano `PSA_PEUGEOT_3008`, `dashcamOnly=true`, `passive=true`, `openpilotLongitudinalControl=false`, `pcmCruise=true`.
- Nessun campione `carControl.longActive=true` nei rlog.

Questi parametri confermano la registrazione in dashcam/passive mode. La route è il riferimento richiesto per studiare i messaggi del controllo longitudinale originale; non documenta un controllo longitudinale già eseguito da Sunnypilot. La ricostruzione dettagliata di stati, coppia, frenata e transizioni resta da svolgere sui dati CAN originali.

## File di verifica

- `SHA256SUMS.remote`: checksum ottenuti dal comma prima della copia.
- `acquisition_verification.json`: inventario, dimensioni, checksum, conteggi degli eventi, parametri e riepilogo per segmento.

Le date di alcuni file del dispositivo sono incoerenti: identificare la prova dalla route e usare i tempi monotoni per allineare i segnali.

## Riferimento aggiuntivo in sola lettura

Cristian ha indicato `/Users/cristianku/GitHub/COMMA.AI/ELKOLED/elkoled_opendbc` come fonte di spunti, esclusivamente in sola lettura. Il longitudinale Elkoled è incompleto.

Nel suo `opendbc/car/psa/carcontroller.py`, la distanza `modelV2.leadsV3[0].x[0]` viene divisa per `5 + vEgo` e convertita in posizioni discrete con isteresi. `self.bars` passa a `create_HS2_DYN_MDD_ETAT_2F6`; in `psacan.py` viene codificata in `TARGET_POSITION` del messaggio `0x2F6`, insieme a `TARGET_DETECTED` derivato da `leadVisible`. Questo è uno spunto per usare la distanza del modello sul display della vettura. La corrispondenza visiva delle posizioni deve essere verificata; il rapporto usato è euristico e non coincide con il tempo interveicolare fisico `d/v`.

Nessun codice è stato copiato o modificato nel repository Elkoled o nel port PSA durante questa acquisizione.
