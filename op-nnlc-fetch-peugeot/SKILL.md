---
name: op-nnlc-fetch-peugeot
description: Usare quando Cristian chiede di scaricare da openpilot-nnlc il modello NNLC del Peugeot 3008 nel repository locale neural-network-data. Non avvia allenamenti o installazioni sul comma.
---

# Scarica NNLC Peugeot 3008

Esegui lo script tramite percorso assoluto:

```bash
python3 /Users/cristianku/GitHub/COMMA.AI/CRISTIANKU/openpilot_scripts/op-nnlc-fetch-peugeot/scripts/fetch_model.py
```

Si collega via SSH a `openpilot-nnlc` e salva con il nome riconosciuto da Sunnypilot:
`/Users/cristianku/GitHub/COMMA.AI/CRISTIANKU/neural-network-data/neural_network_lateral_control/PSA_PEUGEOT_3008.json`.

La sorgente verificata è `/root/openpilot-nnlc-tools/output/2026-06-29_15-07-19/train/training_results/lateral_data_pruned/lateral_data_pruned.json`. Il nome remoto generico non identifica la vettura: non scegliere altri JSON o l'ultimo training per data. Se Cristian indica una nuova esportazione Peugeot, passa `--remote-file /percorso/assoluto.json`. `--destination` serve per una destinazione alternativa richiesta o una prova isolata.

Lo script controlla SHA-256 e struttura NNLC prima di sostituire il file. Conserva il precedente in `neural_network_lateral_control/.nnlc-backups/*.bak` e installa atomicamente. Un file identico non produce modifiche o backup.

Riporta esito, percorso locale, SHA-256 e backup quando presente. Se SSH o validazione falliscono, segnala il problema: non accendere host o modificare il server. Questa skill non autorizza commit, push, cambio branch, allenamenti o operazioni sul comma.
