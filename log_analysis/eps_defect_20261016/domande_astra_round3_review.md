# Review del codice — round 3

**Data:** 16 ottobre 2026
**Per:** ChatGPT Astra (accesso in lettura ai file del Mac)
**Vincoli:**
- sola lettura: niente modifiche ai repository, niente commit, niente comandi sul comma;
- la safety del panda (`opendbc/safety/modes/psa.h`) non si tocca.

Scrivi la risposta in `risposte_astra_round3.md`, accanto a questo file.

Ho applicato le modifiche concordate nel round 2. Ti chiedo una review del codice prima del giro di prova.

---

## Cosa è cambiato

Repo: `/Users/cristianku/GitHub/COMMA.AI/CRISTIANKU/opendbc`, branch `psa-torque-sunny-testing`, HEAD `4ea63ca81` più modifiche non committate.

Diff completo: `lka_100hz.diff` (in questa cartella). File toccati:
- `opendbc/car/psa/carcontroller.py`
- `opendbc/car/psa/values.py`
- `opendbc/car/psa/tests/test_psa.py`, una riga

Test nuovi:
- `opendbc/car/psa/tests/test_lka_100hz.py`
- `opendbc/car/psa/tests/test_eps_dither.py`

Le copie di entrambi sono in questa cartella.

### 1. LANE_KEEP_ASSIST a 100 Hz con rilascio nei cicli intermedi

- Il contenuto si calcola a 20 Hz (`STEER_STEP = 5`); il frame (`lka_msg_last`) parte a ogni ciclo.
- `_lka_release_between_steps()` gira nei 4 cicli intermedi. Su una condizione urgente sostituisce subito `lka_msg_last` con TORQUE=0, TORQUE_FACTOR=0 e azzera `apply_torque_scaled_last`:
  - `lat_active` falso (disingaggio, Defect, velocità ≤ 51 km/h): STATUS 2;
  - frame costruito con EPS Active ed EPS non più Active: STATUS invariato;
  - frame costruito con EPS Active e override del guidatore (`steeringPressed` o coppia grezza ×3 > 50): STATUS invariato.
- Rearm, takeover e scaletta non vengono toccati nei cicli intermedi.

### 2. Dither rifatto (ampiezza 0 per il giro di prova)

- `d(t) = segno · A · sin²(πt/T) · sin(2πft)`, con f = 2,5 Hz, 3 onde, T = 1,2 s. Con A = 6 la sequenza a 20 Hz è `0 0 0 1 0 -2 -3 -3 0 4 6 4 0 -4 -6 -4 0 3 3 2 0 -1 0 0`.
- Un burst per ciclo EPS:
  - viene programmato in `_start_eps_active_cycle()` → `_schedule_eps_dither()`;
  - parte in un momento casuale in `[2 s, rearm − 3 s − 1,2 s]`, allineato ai frame a 20 Hz;
  - il segno si alterna a ogni programmazione.
- `_cancel_eps_dither()` viene chiamato in:
  - `_reset_lat_state()`;
  - `_deactivate_eps()`;
  - il ramo override a 20 Hz;
  - `_lka_release_between_steps()` quando rilascia;
  - nel punto di applicazione, se `apply_driver_steer_torque_limits(base + dither)` è diverso da `base + dither`. In quel caso il burst viene annullato e quel ciclo si ricalcola senza dither.
- Un burst annullato non riprende e non viene compensato.
- `EPS_DITHER_AMPLITUDE = 0` in `values.py`: per il giro di prova va testato solo il 100 Hz.

### Test eseguiti (in locale, dalla root di opendbc)

```sh
.venv/bin/python -m pytest -q -p no:randomly \
  opendbc/car/psa/tests/test_lka_100hz.py opendbc/car/psa/tests/test_eps_dither.py
```

Risultato: 12 passati e 20 sottotest, cioè 5 condizioni × cicli 1–4, con controller e safety vere.

Controprove fatte:
- disattivando `_lka_release_between_steps` falliscono tutti i 20 sottotest;
- disattivando `_cancel_eps_dither` falliscono i test su taglio e override.

Suite complete, confrontate col baseline:
- `opendbc/car/psa/tests/`: 67 falliti (gli stessi di prima, test vecchi di radar e longitudinale), 137 passati, nessun fallimento nuovo;
- safety PSA (`opendbc/safety/tests/test_psa*.py`): identica al baseline, con 12 falliti preesistenti.

---

## Domande

1. **Rilascio nei cicli intermedi.** Ci sono transizioni non coperte o coperte male?
   - impulso di rearm (`_deactivate_eps` con `deactivation_in_progress`, EPS ancora Active);
   - scaletta 2→3→4 interrotta;
   - `lat_active` che va e viene in pochi cicli;
   - interazione con i messaggi di takeover.

   Il rilascio può produrre un frame che la safety rifiuta (src 192)?

2. **Dither, programmazione e annullamento.**
   - Il rearm anticipato in curva (`_should_preempt_eps_rearm`, possibile già dopo 3 s) è coperto da `_deactivate_eps` → `_cancel_eps_dither`?
   - Il segno si alterna anche quando un burst viene annullato: è un problema?
   - L'RNG non ha seed in produzione: va bene?

3. **Controllo del taglio.** Il confronto `limitato(base + dither) != base + dither` basta a garantire che non venga mai consegnata una perturbazione asimmetrica? Pensa a:
   - il limite sulla coppia guidatore (`STEER_DRIVER_ALLOWANCE`, `driver_torque`);
   - la saturazione a `STEER_MAX`;
   - il campione dopo un annullamento a metà burst: si riparte da `apply_torque_scaled_last`, che contiene ancora l'ultimo dither.

4. **Dither spento davvero.** Con `EPS_DITHER_AMPLITUDE = 0` il codice nuovo è del tutto inerte, cioè il comportamento è identico al solo 100 Hz?

5. **torqued.** Con il dither acceso, `carOutput.actuatorsOutput.torque` include il dither. Come lo escluderesti dall'apprendimento con il minimo intervento? Il learner sta in openpilot, non in opendbc: dammi solo la proposta.

6. **Test.** Quali casi mancano? Ci sono test che passano per il motivo sbagliato?

7. **Blocchi per il giro.** C'è qualcosa che impedisce di fare il giro di prova con questa versione (100 Hz, dither a 0)?

Rispondi in modo concreto, indicando le righe di codice. Per ogni verifica dimmi il comando esatto.
