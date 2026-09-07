---
name: nnlc-joseph-sync
description: Copia i log di Joseph da TrueNAS a una chiavetta USB sul Mac e li importa offline sulla macchina openpilot-nnlc-joseph. Usare per preparare o importare questi log; --truncate pulisce soltanto i vecchi log sulla macchina Joseph, su richiesta esplicita.
---

# Log NNLC Joseph tramite chiavetta

Eseguire `scripts/sync_logs.py` con Python 3.9+. La procedura ha due fasi: copia sulla chiavetta dal Mac e importazione locale su Joseph dopo il trasporto fisico. Non trasferire i log dal Mac al server Joseph via rete.

**TrueNAS è sempre una sorgente in sola lettura. Non rimuovere, spostare o modificare i suoi log.** Non usare `--remove-source-files` o sincronizzazioni che cancellano la sorgente.

## 1. Preparare la chiavetta sul Mac

Sorgente: `admin@truenas.local:/mnt/POOL/FILEBROWSER/DATA/comma/joseph/realdata/`.
Chiavetta di Cristian: `/Volumes/chiavetta`. Scrivere soltanto nella sottocartella `joseph-nnlc`.

```bash
python3 ~/.codex/skills/nnlc-joseph-sync/scripts/sync_logs.py --usb /Volumes/chiavetta --dry-run
python3 ~/.codex/skills/nnlc-joseph-sync/scripts/sync_logs.py --usb /Volumes/chiavetta
```

Occorrono SSH e rsync sul Mac. Il volume deve essere montato; lo script non crea falsi punti di mount. Copia incrementalmente `rlog.zst`, `rlog.bz2` e `rlog.*.zip`, mantenendo i file compressi. Ignora video e altri file. Non estrae ZIP sul Mac o sulla chiavetta e non contatta Joseph.

La cartella `joseph-nnlc` contiene `realdata/`, `manifest.json` con dimensioni e SHA-256 calcolati su TrueNAS e `sync_logs.py`, lo script portabile per l'importazione. Il manifest viene scritto solo dopo avere verificato le copie. In caso di interruzione ripetere il comando di esportazione. Non formattare, cancellare altri file o espellere automaticamente il volume.

## 2. Importare offline sulla macchina Joseph

Dopo che Cristian collega la chiavetta, identificare il punto di mount effettivo. Joseph è il container Proxmox `125` su `serverone-ai`: quando la chiavetta è collegata all'host, seguire [Importazione locale da Proxmox](references/proxmox-usb.md). Il percorso passato a `--import-usb` può essere anche una copia temporanea locale del contenuto USB. Non supporre che il percorso macOS esista su Linux e non usare un trasferimento di rete come ripiego.

Eseguire **sulla macchina Joseph**, sostituendo `/mnt/chiavetta` con il mount effettivo:

```bash
python3 /mnt/chiavetta/joseph-nnlc/sync_logs.py --import-usb /mnt/chiavetta --dry-run
python3 /mnt/chiavetta/joseph-nnlc/sync_logs.py --import-usb /mnt/chiavetta
```

Solo per una pulizia esplicitamente richiesta dei log ereditati dal clone:

```bash
python3 /mnt/chiavetta/joseph-nnlc/sync_logs.py --import-usb /mnt/chiavetta --truncate
```

`--truncate` è vietato nell'esportazione e non viene memorizzato: vale solo per quella importazione. Svuota esclusivamente `/root/openpilot-nnlc-tools/data/` sul sistema con hostname `openpilot-nnlc-joseph`. `output`, modelli, codice, ambienti Python, chiavetta e TrueNAS restano invariati. La prima pulizia del clone è stata completata il 7 settembre 2026 (801 vecchi log rimossi, 434 log Joseph importati e verificati). Per le importazioni successive omettere `--truncate`, salvo una nuova richiesta esplicita di pulizia.

Prima dell'importazione verificare che non siano attivi training o altre importazioni. Lo script verifica gli hash della chiavetta, prepara i rlog in una directory temporanea sul disco Joseph, poi esegue l'eventuale pulizia. Gli ZIP devono contenere un solo rlog nel percorso del segmento, con eventuali entry directory. Il file `.zst`/`.bz2` resta compresso come previsto dal training. Symlink, percorsi ZIP anomali, log in conflitto o verifica fallita fermano l'importazione prima della pulizia. Gli hash vengono verificati anche dopo l'importazione.

Se il trasferimento locale si interrompe, ripetere **senza `--truncate`**. Una pulizia interrotta lascia il marker `.nnlc-joseph-truncate-pending`: ispezionare lo stato e completarla con `--truncate` entro l'autorizzazione esistente, senza rimuovere manualmente il marker. Non avviare training o modificare il comma come parte di questa skill. Per un nuovo training usare `data`, evitando i dataset precedenti in `output`.

Riportare la fase completata, numero di file, byte e verifica SHA-256. Non dichiarare importazione o pulizia su Joseph completate quando è stata preparata soltanto la chiavetta.
