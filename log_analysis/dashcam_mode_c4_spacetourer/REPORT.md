# C4 SpaceTourer: come funziona l'ACC di serie (log in dashcam)

Route 00000009--dc7802815d, segmenti 10–20, dongle 378c9bf47606eb28. Sono 636 s di guida con dashcamOnly=True: l'ACC di serie era attivo e openpilot non era mai ingaggiato.
T = secondi dall'inizio del segmento 10.

## Accelerazione (motore)
- Valori in 0x2B6: POTENTIAL_WHEEL_TORQUE_REQUEST=1, WHEEL_TORQUE_REQUEST=1, MDD_DESIRED_DECELERATION=2.05 (inattivo).
- GMP_WHEEL_TORQUE è la coppia reale alla ruota. Il motore la segue entro un frame: Dyn_CMM.P198 × rapporto ≈ 1.07·T + 7 Nm.
- Modello: a ≈ 1.36e-3·T − 0.09 − 1.53e-4·v². Corrisponde a una massa di circa 2230 kg; servono circa 735 Nm per ogni m/s².
- Per tenere a = 0 servono circa 66 + 0.112·v² Nm: 88 Nm a 50 km/h, 152 a 100, 206 a 127.
- In modalità motore la coppia richiesta va da −120 a +831 Nm, con rampe di 150–250 Nm/s.
- POTENTIAL vale circa la coppia richiesta − 26 Nm e non scende mai sotto 0.

## Frenata
- 5 episodi, 26.8 s in totale.
- Valori in 0x2B6: POTENTIAL=2, WHEEL_TORQUE_REQUEST=0, DECEL_TYPE=1, DECEL_CONTROL_REQ=1, coppie a −4000.
- La decelerazione ottenuta è uguale a MDD, con errore medio quasi nullo. Il ritardo è di 0.56–0.94 s.
- Valori di MDD: da −0.15 a −1.30.
- Entrata in frenata: la coppia scende fino a quella minima di trascinamento (da −60 a −94 Nm), poi WHEEL_TORQUE_REQUEST=2 per 0.04–0.28 s, poi il freno.
- Uscita dalla frenata: con MDD a circa −0.15/−0.2 torna alla coppia minima con WTR=2 per circa 0.3 s, poi la coppia risale in rampa.

## Macchina a stati
- Stato 3 (Waiting) solo da 27 km/h in su; sotto resta 2.
- Mai attivo sotto 39.8 km/h. Non c'è stop&go nei dati.
- All'attivazione l'ACC parte dalla coppia reale del momento, quindi senza scalino.
- Gas premuto: lo stato passa a 5 solo se il guidatore chiede più coppia dell'ACC.
- Freno premuto: lo stato passa a 2 entro 20 ms.
- GEAR_TYPE == COUNTER&1. MIN_TIME vale 6.2 quando GEAR_TYPE=1 e 3.6 quando GEAR_TYPE=0.
- Checksum, contatori e frequenze sono uguali a quelli di psacan.py.

## Cosa cambia per il port
1. Sulla C4 il port chiede fino a −300/−400 Nm col motore, ma il freno motore della C4 arriva al massimo a circa −120 Nm; lo stock a quel punto passa al freno. Quindi tra circa −0.15 e −0.5 m/s² la C4 rallenterebbe meno del richiesto.
2. Uscita dalla frenata diversa. Il port riparte da 0 Nm, lo stock dalla coppia minima e poi in rampa.
3. Il +10% di BRAKE_ACCEL_V del 3008 sul C4 farebbe frenare circa il 10% in più.
4. La mappa di coppia del 3008 (490 Nm per m/s², 179 Nm a a=0) sul C4 darebbe circa 1/3 di accelerazione in meno.
5. All'attivazione il port fa ripartire il filtro da 0, con un breve calo di coppia.
6. MIN_TIME: il port manda sempre 6.2, lo stock alterna 6.2/3.6. Cambiarlo richiede di toccare la safety.
7. WHEEL_TORQUE_REQUEST=2 ("low range") non è ammesso dal port né dalla safety.
8. Il port mette lo stato 5 a ogni pressione del gas. È diverso dallo stock ma prudente.
9. Il port mostra Waiting da 1 km/h, lo stock da 27 km/h. Non sappiamo se la BSI accetti l'attivazione sotto.
10. longitudinalActuatorDelay vale 0.45 s, mentre il ritardo misurato sul C4 è di 0.56–0.94 s.

## Limiti
- Solo 5 frenate, la più forte a −1.3 m/s². Niente stop&go.
- La strada sembra piana.
- Il raggio ruota (0.329 m) è stato assunto, non misurato.

Script in `analysis/` (vedi sotto).

## Confronto con i valori del port (problema "la macchina non accelera")
Cosa sappiamo: il radar va in programmazione e l'ACC stock smette, quindi la macchina prende i nostri messaggi. L'utente però dice che, con il longitudinale di openpilot acceso, non accelera. Quei giri non sono in questa cartella.

### Coppia (GMP_WHEEL_TORQUE, Nm alla ruota)
Modello stock C4, uguale con ritardo da 0 a 300 ms (rms 0.073):
`a = 1.355e-3·T − 0.089 − 1.55e-4·v²`, quindi `T = (a + 0.089 + 1.55e-4·v²) / 1.355e-3` (v in m/s).

| accel chiesta | port | stock 50 km/h | 80 | 100 | 120 |
|---|---|---|---|---|---|
| −0.4 | −204 | −208 | −173 | −141 | −103 |
| 0 | 179 | 88 | 122 | 154 | 193 |
| +0.25 | 301 | 272 | 306 | 338 | 377 |
| +0.5 | 424 | 457 | 491 | 523 | 562 |
| +1.0 | 670 | 826 | 860 | 892 | 931 |
| +1.5 | 800 | 1195 | 1229 | 1261 | 1300 |

Accelerazione che la C4 otterrebbe con la tabella del port (calcolata col modello):
- chiedendo +0.5 m/s²: tra 0.31 e 0.46;
- chiedendo +1.0 m/s²: tra 0.65 e 0.79.

È più debole dello stock ma accelera, quindi la scala di coppia **non** spiega un'accelerazione nulla.

POTENTIAL nello stock vale WHEEL − 26 Nm a velocità costante e WHEEL − 18 Nm in accelerazione, e non è mai sotto 0. Il port arriva a −300/−400.

### Campi diversi dallo stock nei frame in cui accelera
- **MIN_TIME_FOR_DESIRED_GEAR:** lo stock manda sempre 6.2 sui frame dispari (GEAR_TYPE=1) e 3.6 sui pari. Il port manda 6.2 su tutti, e la safety impone 62. **Primo sospetto.**
- **0x2F6 ARC_STATUS:** lo stock manda 12 (attivo), il port 6 (inibito).
- **Aggancio:** lo stock parte dalla coppia reale, con 2–4 frame a WHEEL_TORQUE_REQUEST=2. Il port parte da 0 Nm con WTR=1.
- **AUTO_BRAKING_STATUS=3: escluso.** Lo stock lo manda a 126–127 km/h e il motore segue comunque la coppia (errore rms 6 Nm).
- **Uguali allo stock:** 0x452 sul bus 1 (RVV=1, ARC_HABIT=1), 0x4F6 SENSOR_STATE=2, Dyn_CMM P333_Com_stGbxTrqIntv=2 nel 100% dei frame in cui l'ACC accelera.

### Verifica da fare sul log col longitudinale acceso
- `Dyn_CMM.P198_ActMod_trqClthTraIntv` × rapporto deve seguire il nostro GMP_WHEEL_TORQUE (stock: ≈ 1.07·T + 7). Rapporti: 3a 5.36, 4a 3.90, 5a 3.23, 6a 2.62, 7a 2.09, 8a 1.76.
- `P333_Com_stGbxTrqIntv` deve valere 2.

Se non succede, la centralina motore scarta il nostro 0x2B6. Il primo campo da correggere è MIN_TIME a 6.2/3.6, che richiede di modificare anche la safety in psa.h.

## Come rilanciare l'analisi
Gli script sono in `analysis/` e girano con `uv run -q <script>.py` dalla cartella `analysis/`.
- `extract.py ../00000009--dc7802815d out` estrae i parquet; `psa.dbc` è il DBC pulito per cantools.
- `merge.py` crea `out/m.parquet`.
- `cmp*.py` contengono il confronto con il port.
- `an*.py`, `br.py`, `sm.py`, `bits.py`, `ep.py` sono le analisi di dettaglio.

Nota: `extract.py` e `overview.py` cercano lo schema cereal in `~/GitHub/COMMA.AI/SUNNYPILOT/sunnypilot/openpilot/cereal`.
