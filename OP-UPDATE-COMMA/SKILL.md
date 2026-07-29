---
name: op-update-comma
description: Aggiorna automaticamente il checkout openpilot sul dispositivo comma tramite SSH e riavvia il dispositivo dopo un aggiornamento riuscito. Usare quando Cristian chiede di aggiornare, fare pull, portare all'ultima versione o aggiornare e riavviare il comma; supporta anche verifica senza modifiche e aggiornamento senza reboot.
---

<!-- [comma update] - START -->
# OP Update Comma

Usare `scripts/update_comma.sh` per aggiornare `/data/openpilot` sul dispositivo indicato, mantenendo il branch e l'upstream già configurati.

## Esecuzione

Se l'utente chiede esplicitamente aggiornamento e reboot, eseguire direttamente:

```bash
scripts/update_comma.sh comma
```

Comunicare prima che il dispositivo verrà aggiornato e riavviato. Al termine, riportare commit iniziale, commit installato e conferma dell'invio del reboot.

Opzioni:

```bash
scripts/update_comma.sh --dry-run comma
scripts/update_comma.sh --no-reboot comma
```

- Usare `--dry-run` quando l'utente chiede soltanto controllo o anteprima.
- Usare `--no-reboot` soltanto quando richiesto esplicitamente.
- Accettare un alias SSH alternativo come argomento host quando l'utente lo indica.

## Regole di sicurezza

Lo script deve:

1. operare esclusivamente in `/data/openpilot`;
2. rifiutare detached HEAD, upstream mancante o working tree sporco;
3. aggiornare esclusivamente tramite fast-forward;
4. sincronizzare e aggiornare ricorsivamente i submodule;
5. riavviare soltanto se tutte le operazioni precedenti riescono.

Non aggirare un rifiuto con `git reset`, `git clean`, stash automatico o cambio branch. Mostrare lo stato rilevato e chiedere istruzioni all'utente.

Se l'utente domanda soltanto come aggiornare il dispositivo, spiegare il comando senza eseguirlo.
<!-- [comma update] - END -->
