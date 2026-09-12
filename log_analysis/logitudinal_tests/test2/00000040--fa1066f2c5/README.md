# Test2 — prova neutra con inserimento retro e movimento

Route: `6616faac453a3064/00000040--fa1066f2c5`.

- Versione openpilot `81854c4da`, opendbc `fd64d7e9`.
- Un segmento completo: 1 rlog e 1 qlog, durata circa 44,943 s.
- Hash remoti stabili durante la copia e corrispondenti ai locali; entrambi i file decodificati integralmente, con fine route presente.
- Acquisizione SSH in sola lettura il 12 settembre 2026. Video non scaricati.
- Avvio e retro senza fault. Al primo movimento il profilo neutro interrompe i sostituti; segue il fault.

Dettagli: [findings test2](../../../../plans/longitudinal/findings-test2-20260912.md). Vedere anche `SHA256SUMS.remote` e `acquisition_verification.json`.
