# Dashcam mode — riferimento longitudinale, route 49

<!-- [route reference] - START -->
Route: `6616faac453a3064/00000049--a95dde6809`.

Registrazione indicata da Cristian il 12 settembre 2026 come nuovo riferimento della bibbia longitudinale, da conservare insieme alla route `0000003a--e445e79563`.

## Contesto fornito da Cristian

- Guida in dashcam mode, con ACC originale della vettura. Cristian conferma un percorso in salita e poi in discesa.
- Ripetute attivazioni e disattivazioni dell'ACC: alcune tramite pulsante, altre con un piccolo colpo di freno seguito dalla riattivazione.
- Soprattutto verso la fine: numerose pressioni del pulsante ACC con il messaggio sul quadro **“Activation denied, conditions unsuitable”**, che Cristian riferisce comparire perché viaggiava sotto i 30 km/h.

Queste sono osservazioni del conducente. Gli istanti dei tentativi, la causa del rifiuto e l'eventuale soglia esatta devono ancora essere ricostruiti dai segnali CAN. Non si assume che la stringa visualizzata sul quadro sia presente testualmente nei log di openpilot.

## Acquisizione e verifiche

- Copia dal comma via SSH in sola lettura, da `/data/media/0/realdata`, il 12 settembre 2026.
- Tutti i **10 segmenti disponibili**, numerati da 0 a 9: **10 rlog e 10 qlog**, 103.453.608 byte totali. Video non inclusi.
- SHA-256 dei 20 file locali corrispondente agli originali; checksum remoti invariati prima e dopo la copia.
- Decompressione Zstandard e lettura completa degli eventi Cap'n Proto riuscite per tutti i file.
- Durata coperta dai rlog: **572,175 s**, circa **9 minuti e 32 secondi**. Velocità massima `carState.vEgo`: **83,09 km/h**.
- `initData.dongleId` corrisponde alla route richiesta: `6616faac453a3064`.
- Versione registrata: `42024c6f4ead8e3f0b9d8f817e963c35b2055907`, branch **psa-torque-sunny-testing**.
- Tutti i `carParams` letti concordano: `PSA_PEUGEOT_3008`, `dashcamOnly=true`, `passive=true`, `openpilotLongitudinalControl=false`, `pcmCruise=true`.
- Nessun campione `carControl.longActive=true` nei rlog: la modalità dashcam/passive è confermata dai dati.

L'acquisizione non costituisce una calibrazione della coppia né una ricostruzione già completata degli stati ACC. Originali conservati nelle sottocartelle di segmento; nessuna modifica sul dispositivo.

## File di verifica

- [SHA256SUMS.remote](SHA256SUMS.remote): checksum calcolati sul comma.
- [acquisition_verification.json](acquisition_verification.json): inventario, dimensioni, checksum, conteggi eventi, parametri e riepilogo dei segmenti, con le note del conducente.
## Analisi accelerazione e coppia

Disponibile il [rapporto di calibrazione offline](../../../plans/longitudinal/analysis-route49/README.md), con tabella candidata che considera la pendenza, confronto con la route 3a e studio delle decelerazioni.
<!-- [route reference] - END -->
