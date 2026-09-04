$op-setup-psa-torque-testing sunny master=de197ba6

<!-- [pinned source] - START -->
> **Nota:** `de197ba6` è la base Sunnypilot del 30 agosto 2026 che completa correttamente l'installazione sul comma. I master successivi introducono 44 commit, incluso AGNOS 19.7, e sul dispositivo l'installazione resta bloccata. Il pin riguarda soltanto il codice Sunnypilot: il workflow continua a caricare il JSON PSA più recente da `cristianku/neural-network-data:master` e non modifica il loader o il controller NNLC. La base contiene già il ripristino dei PID NNLC della [PR #1779](https://github.com/sunnypilot/sunnypilot/pull/1779) e il Lateral Jerk Torque Controller. La community segnala inoltre ping-pong con NNLC abbinato ai driving model moderni; per una prova comparabile usare un modello Legacy oppure disabilitare NNLC.
<!-- [pinned source] - END -->
