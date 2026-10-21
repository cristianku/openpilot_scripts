# Pubblicazioni nella community Sunnypilot — sorgente e installazione

<!-- [community publication] - START -->
## Regola obbligatoria per annunci, release e nuove funzionalità

Ogni volta che pubblichiamo nella community Sunnypilot (GitHub, Discord, forum o altri canali) una funzionalità, un modello o una versione basata su Sunnypilot, **distinguere sempre il repository che contiene il codice sorgente dalla branch pubblicata per l'installazione sul comma**.

Prima di pubblicare, verificare sui repository remoti:
1. **Upstream originale**, se pertinente: `sunnypilot/sunnypilot:master` (non presentare il fork `cristianku/openpilot` come l'upstream ufficiale).
2. **Sorgente di sviluppo**: link al repository/branch che contiene *davvero* le modifiche e viene mantenuto. Per le integrazioni SunnyPilot di Cristian, l'obiettivo è `cristianku/sunnypilot:<branch>`. Per componenti separati (ad esempio `cristianku/sunnypilot.speedlimits` e `cristianku/openpilot.distill`), includere anche il repository del componente quando rilevante.
3. **Distribuzione**: link alla branch installabile `https://github.com/cristianku/openpilot/tree/<branch>` e, quando è verificato che esista e sia installabile, `https://installer.comma.ai/cristianku/<branch>`.
4. **Stato reale**: precisare se si tratta di proposta, lavoro in corso, test o release. Non dichiarare installabile una branch non pubblicata; non dichiarare supporto o test su veicoli non verificati.
5. **Corrispondenza**: prima di indicare il link di installazione, verificare che il codice copiato nella branch `cristianku/openpilot:<branch>` corrisponda alla sorgente approvata; identificare commit/branch usati quando utile.

La separazione è intenzionale: `cristianku/sunnypilot` conserva le modifiche sorgente; `cristianku/openpilot` ospita branch di distribuzione di Sunnypilot perché il flusso di installazione le risolve lì. Il nome `openpilot` del repository **non** significa che quelle branch contengano commaai/openpilot. Non assumere che tutte le branch condividano l'identica provenienza: controllare caso per caso.

### Template inglese per una pubblicazione nella community

> **Based on:** [sunnypilot/sunnypilot](https://github.com/sunnypilot/sunnypilot)
>
> **Source / development:** `cristianku/sunnypilot:<SOURCE_BRANCH>` — <URL della branch sorgente verificata>
>
> **Installable build:** `cristianku/openpilot:<INSTALL_BRANCH>` — <URL della branch di distribuzione verificata>
>
> **Comma installer:** `https://installer.comma.ai/cristianku/<INSTALL_BRANCH>` (solo se pubblicato e verificato)
>
> **Status and compatibility:** <testato / sperimentale / in sviluppo; dispositivi/auto supportati e limitazioni>

Adattare i nomi delle branch alla funzionalità effettiva; non compilare i segnaposto con nomi inventati. Se l'installazione **non** esiste ancora, sostituire le due righe di distribuzione con: **"Not yet available for installation; source/development only."**

### Caso specifico: Distill

Architettura *richiesta/pianificata*, da non spacciare per già implementata:

- Sorgente canonica desiderata: `cristianku/sunnypilot:distilled`, contenente le modifiche al catalogo dei modelli Distill.
- `OP-update-distilled` dovrà integrare `sunnypilot/sunnypilot:master` nella branch sorgente, preservare le modifiche e, **solo dopo verifica dei conflitti e dei test**, pubblicare lo stesso codice come `cristianku/openpilot:distilled`.
- Le skill PSA dovranno consumare le modifiche Distill dalla sorgente condivisa, anziché mantenere una seconda copia della patch. **Il workflow corrente potrebbe ancora utilizzare una patch locale in `openpilot_scripts`: verificare l'implementazione prima di annunciare il nuovo flusso come operativo.**
- Fino a quando le branch `distilled` non esistono e non sono verificate, non pubblicare come funzionante il link `installer.comma.ai/cristianku/distilled`.

Questa è una **regola di documentazione e comunicazione**, non un'autorizzazione a fare merge, push, aggiornare skill, pubblicare annunci o installare software sul dispositivo. Ogni intervento mantiene le regole di autorizzazione del progetto.
<!-- [community publication] - END -->
