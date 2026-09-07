# Chiavetta su serverone-ai

Host SSH: `serverone-ai` (`10.10.10.110`). Joseph: container Proxmox `125`, hostname `openpilot-nnlc-joseph`, IP `10.10.10.192`. Verificare ogni volta con `pct list` e `pct config 125` prima di operare.

Il collegamento SSH trasporta solo comandi e risultati. I byte dei log passano dalla USB al disco del container tramite una pipe locale sullo stesso host. Non modificare la configurazione dei mount del container e non riavviarlo.

1. Identificare il volume con `lsblk -o NAME,SIZE,FSTYPE,LABEL,MOUNTPOINTS,UUID`. La chiavetta usata da Cristian è exFAT, etichetta `chiavetta`, UUID `6A83-60D4`; verificare la corrispondenza, non assumere un nome `/dev/sdX` stabile. Montarla in sola lettura su un punto libero, per esempio `/mnt/joseph-usb`, con `ro,nosuid,nodev,noexec`.
2. Confrontare lo SHA-256 di `joseph-nnlc/sync_logs.py` con lo script locale della skill prima di eseguire la copia USB. Se differisce, ispezionare la differenza. Verificare i file con la funzione `verify_files` dello script e `manifest.json`; usare `runpy.run_path` per caricare le funzioni senza eseguire `main`.
3. Controllare spazio e processi del container. Creare una directory nuova con `pct exec 125 -- mktemp -d /root/openpilot-nnlc-tools/.joseph-usb-XXXXXXXX` e conservare il percorso esatto restituito.
4. Sul solo host Proxmox eseguire una pipeline con `set -o pipefail`: `tar -C /mnt/joseph-usb -cf - joseph-nnlc | pct exec 125 -- tar --no-same-owner -xf - -C PERCORSO_TEMPORANEO`. Il contenuto della chiavetta e TrueNAS restano invariati.
5. Sempre tramite `pct exec 125 --`, eseguire `python3 PERCORSO_TEMPORANEO/joseph-nnlc/sync_logs.py --import-usb PERCORSO_TEMPORANEO --dry-run`, poi importare con lo stesso comando senza `--dry-run`. Aggiungere `--truncate` solo per la pulizia autorizzata. Gli hash della copia temporanea vengono verificati prima della pulizia e quelli in `data` dopo l'importazione.
6. Dopo il successo, verificare i log in `data` e rimuovere esclusivamente la directory temporanea creata in questa esecuzione. Se la copia/importazione fallisce, conservarla per la diagnosi/ripresa. Smontare sull'host il mount USB creato da questa procedura una volta terminato ogni accesso; non smontare volumi montati dall'utente o da altri processi senza verificarne l'uso.

Per un'importazione con `--truncate`, il resoconto finale deve riportare vecchi log rimossi, nuovi rlog verificati e conservazione di `output`, USB e originali TrueNAS. Non lasciare mount persistenti Proxmox o configurazioni pendenti come effetto di questa procedura.
