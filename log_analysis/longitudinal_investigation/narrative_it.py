"""Italian narrative blocks for report.py.

Numbers are computed from the outputs passed in; the interpretive sentences were written
after reading those outputs (investigation of 2026-10-17) and say how confident they are.
"""

import json
import statistics


def _median(values):
  clean = []
  for v in values:
    if v is None:
      continue
    if isinstance(v, float) and v != v:
      continue
    clean.append(v)
  if not clean:
    return None
  return statistics.median(clean)


def _f(x, nd=1):
  if x is None:
    return "–"
  return ("%." + str(nd) + "f") % x


def header(inv, events):
  n_routes = 0
  n_seg = 0
  for r in inv:
    if r.get("op_long"):
      n_routes += 1
      n_seg += r["n_segments"]
  return (
    "<h1>Peugeot 3008 – frenate anticipate a semafori e rotonde: indagine sui log</h1>"
    "<p>Generato il 2026-10-17 da <code>openpilot_scripts/log_analysis/longitudinal_investigation/</code>. "
    "%d route con longitudinale openpilot, %d segmenti rlog, %d eventi candidati. "
    "Sola lettura su openpilot, opendbc e sui log; nessun accesso al comma.</p>" % (n_routes, n_seg, len(events)))


def summary(events, resp, track, decs, gas):
  return SUMMARY_HTML


SUMMARY_HTML = r"""
<h2>Risposta breve</h2>
<div class="warn"><b>Limite principale:</b> nessun video locale. Le conclusioni su <i>chi</i> ha generato la frenata sono solide
(telemetria + CAN); quelle su <i>se</i> fosse giustificata (rosso/verde, pedoni, traffico in rotonda, posizione della linea) restano
<b>non verificate</b>. Confidenza massima: media.</div>
<h3>Semafori – fermata 5–10 m prima della linea</h3>
<ul>
<li><b>Non riprodotta nei log disponibili.</b> Nel regime attuale (guadagno 1.55, route 000000b8 → 00000115) ci sono 21 arresti completi
con openpilot ingaggiato fino a 0 km/h: <b>tutti dietro un veicolo</b> (lead da visione, tracciato per secondi/minuti e che riparte prima di noi:
veicoli reali). Gap all'arresto: mediana 5.6 m (IQR 3.6–6.9 m, 23 arresti in tutte le route). È il comportamento di progetto dell'MPC
(<code>STOP_DISTANCE = 6 m</code> in <code>long_mpc.py</code>) e del modello: dietro un'auto, non davanti a una linea. Nessun arresto ingaggiato
"primo in fila" a un semaforo mappato: quelli senza lead (E115, E131, settembre, guadagno 1.0) non sono a semafori OSM.</li>
<li><b>Dove si ferma rispetto al piano del modello:</b> negli ultimi secondi l'auto percorre <b>meno</b> di quanto il modello prevedeva:
mediana −0.3 m a 2 s, −1.1 m a 4 s, −2.5 m a 6 s, −4.8 m a 8 s prima dell'arresto (n≈18–21, regime 1.55). Contributo del controller PSA
(guadagno 1.55 → decelerazione misurata ≈1.4× la richiesta) a un arresto un po' corto: <b>da 1 a ~5 m</b>, non 10 m da solo.</li>
<li><b>Frenata iniziata presto ai semafori</b> (diverso problema): nei casi mappati (E245/E246, E473, E500) la richiesta nasce dal
<b>modello (e2e)</b> 120–330 m prima del semaforo OSM, a −0.7…−0.8 m/s², quando DEC passa in <i>blended</i>; il PSA la trasforma in
−1.1…−2.0 m/s² misurati; il conducente preme l'acceleratore. Origine: <b>modello + gating DEC</b>; amplificazione: <b>opendbc PSA</b>.</li>
</ul>
<h3>Rotonde – rallentamento troppo anticipato</h3>
<ul>
<li><b>Route di settembre con Smart Cruise Control attivo</b> (SCC-Map/Vision=1): il rallentamento lontano dalla rotonda è del
<b>planner sunnypilot</b>, non del modello. Esempio E145 (00000070--97bd1ebf25 seg 7): <code>sccMap</code> porta il vTarget a 25.9 km/h e poi
<code>sccVision</code> a ~21 km/h; il candidato <i>cruise</i> chiede −1.2 m/s² (A_CRUISE_MIN) a ~224 m dall'ingresso mentre il modello
chiede −0.3…−0.9 e poi +0.9: l'auto scende a 23 km/h e riaccelera. Stesso schema in E084 (sccMap 26 km/h, 343 m, override gas),
E037/E047 (sccVision).</li>
<li><b>Route di ottobre (SCC disattivato)</b>: cause miste. E641 (00000111--5190df2b4b seg 42, ~t_seg 56 s): a 88 km/h DEC passa in blended
~16 s prima e il <b>modello</b> chiede −1.35…−1.7 m/s² (PSA al clamp −2.0), l'auto scende a 2.9 km/h ~7 m prima dell'anello OSM, senza
lead negli ultimi 15 s → conducente preme gas. È il caso "quasi zero su ingresso libero" (libero solo secondo il lead da visione: traffico
nell'anello non verificabile). E667/E668: veicolo davanti che rallenta all'ingresso (MPC lead) + riduzione del set speed del conducente
(77→57 km/h) + modello. E643/E620: coda dietro un lead (legittimo). E291/E292: <i>cruise</i> perché vEgo sopra il set speed.
E659: <code>speedLimitAssist</code> a 35 km/h.</li>
</ul>
<h3>Quale sottosistema</h3>
<table>
<tr><th>Strato</th><th>Verdetto</th><th>Evidenza</th></tr>
<tr><td>A. Modello (e2e)</td><td>origine di gran parte delle frenate anticipate ai semafori e del caso rotonda E641 (ott.)</td><td>fonte e2e all'onset; DEC blended; richieste −0.7…−1.7</td></tr>
<tr><td>B. Planner / MPC / sunnypilot</td><td>origine delle frenate lontane dalle rotonde in settembre (SCC-Map/Vision), di SLA (E659), della commutazione DEC (≈2.4 switch/min, 131 gradini &lt; −0.5 m/s²) e del gap 6 m dietro un lead</td><td>longitudinalPlanSP.source, vTarget; dec.state</td></tr>
<tr><td>C. Lead fantasma</td><td>non evidenziato: i lead all'arresto sono tracciati a lungo, rallentano da velocità reali e partono prima di noi</td><td>lead_track_s, lead_vmax, partenza</td></tr>
<tr><td>D. LongControl PI</td><td>neutro: kiV=[0] → uscita = aTarget</td><td>carParams; carControl.accel ≡ aTarget</td></tr>
<tr><td>E. Controller PSA opendbc</td><td><b>amplifica</b> ogni frenata ≈1.4× (guadagno 1.55) fino a −1.5 m/s²; contribuisce a "sembra frenare troppo presto/troppo",
alle riprese con gas e a un arresto 1–5 m più corto del piano</td><td>0x2B6 vs carControl; tracking modello</td></tr>
<tr><td>F. Veicolo</td><td>esegue il comando 0x2B6 entro ~0.1 m/s²</td><td>tabella 3.1</td></tr>
</table>
<div class="box"><b>Nota storica utile per la LUT freno:</b> nelle route 00000050–00000058 (inizio settembre) il comando 0x2B6 si saturava a
<b>−1.00 m/s²</b> (richieste −1.2…−1.8 → comando −1.00): è con buona probabilità la "frenata debole" ricordata, cioè un <i>clamp</i>, non un
difetto di guadagno. Dalle route 00000069–0000007d il comando segue 1:1 la richiesta fino a ≈−1.9 e il veicolo la esegue.</div>
"""


def data_notes(inv):
  return (
    "<div class='warn'><b>Video assente.</b> In nessuna cartella locale (comma_logs, log_analysis/**) esiste un "
    "<code>fcamera.hevc</code>, <code>ecamera.hevc</code> o <code>qcamera.ts</code>: tutte le route sono state scaricate "
    "con <code>--no-video</code>. Quindi stato del semaforo, linea di arresto, attraversamenti, pedoni e traffico in rotonda "
    "<b>non sono stati osservati</b>. Ogni scheda riporta segmento e frame fcamera da guardare.</div>"
    "<p>Regime del guadagno freno PSA, misurato dal CAN (rapporto MDD_DESIRED_DECELERATION / carControl.accel in frenata stabile): "
    "<b>≈1.0</b> sulle route fino a 0000007d (settembre), <b>≈1.5</b> (1.55 meno il filtro) da 000000b8 in poi, comprese tutte le "
    "route del 14–16 ottobre (build fb1c36569 e a8b556a07). Il working tree attuale di opendbc (mappa identità BRAKE_ACCEL_BP/V, "
    "isteresi su pendenza) <b>non</b> ha mai guidato in questi log.</p>"
    "<p>Su tutte le route: <code>ExperimentalMode=1</code>, <code>DynamicExperimentalControl=1</code> e DEC attivo "
    "(<code>longitudinalPlanSP.dec.active=true</code>): la build in auto è precedente al commit sunnypilot 5ec0c0219 "
    "\"Sunset DEC\" del 16 ottobre. <code>carParams.radarUnavailable=true</code>: i lead sono solo visione (modello). "
    "<code>longitudinalTuning.kiV=[0]</code>: LongControl è puro feed-forward (uscita = aTarget, nessuna correzione integrale).</p>")


def method():
  return (
    "<ol>"
    "<li><b>Estrazione</b> (<code>extract.py</code>): rlog → timeline a 20 Hz sul clock di longitudinalPlan; gli altri topic "
    "con ultimo valore ricevuto. 0x2B6 decodificato con il DBC <code>psa_aee2010_r3.dbc</code> dal <code>sendcan</code> bus 1 "
    "(= ciò che è stato trasmesso). Chiave video: <code>narrowRoadEncodeIdx</code> (segmento + frame per timestampSof).</li>"
    "<li><b>Eventi</b> (<code>detect_events.py</code>): arresto (v &lt; 0.3 m/s dopo &gt; 15 km/h), quasi-arresto (min &lt; 5 km/h), "
    "rallentamento (calo ≥ 12 km/h rispetto al massimo dei 40 s precedenti, poi ripresa ≥ 6 km/h), finestra −40 s/+25 s. "
    "Soglie configurabili da CLI.</li>"
    "<li><b>Pipeline</b> (<code>analyze_events.py</code>): solo tratti con <code>carControl.longActive</code>; onset = prima "
    "richiesta &lt; −0.5 m/s² sostenuta 1 s; fonte planner, DEC, salti di aTarget, ingressi freno PSA, risposta misurata, "
    "intento del modello (posizione prevista a +T s vs distanza realmente percorsa fino all'arresto), lead all'arresto.</li>"
    "<li><b>Mappa</b> (<code>map_osm.py</code>): Overpass con bounding box ≤ ~1.5–2 km attorno agli eventi; map matching con "
    "direzione (vie seguite, nodi della via, direzione semaforo se taggata, ingresso rotonda = primo punto entro 12 m dall'anello). "
    "Distanze ±15 m: OSM mappa il semaforo sulla linea o al centro dell'incrocio a seconda del mapper.</li>"
    "<li><b>Ranking</b> (<code>rank_events.py</code>) e <b>grafici</b> (<code>plots.py</code>): flag = ipotesi, non difetti.</li>"
    "</ol>")


def response_notes(resp):
  return (
    "<div class='ok'>Il veicolo (centralina freno) <b>esegue fedelmente</b> la decelerazione trasmessa: |misurata − comando| "
    "≤ 0.1 m/s² in tutti i bin, entrambe i regimi. Lo strato <b>F (risposta veicolo)</b> non spiega il problema.</div>"
    "<div class='box'>Con 1.55 la decelerazione <b>misurata è ≈1.4× quella chiesta da openpilot</b> fino a −1.5 m/s² "
    "(es. richiesta −0.77 → comando −1.13 → misurata −1.10). Con ki=0 in LongControl nessuno corregge l'errore: lo fa solo il "
    "modello/MPC al ciclo successivo, rivedendo il piano. Sopra −1.3 m/s² il clamp −2.0 riduce l'effetto.</div>")


def tracking_notes(g):
  return (
    "<p>Per i campioni in cui il modello è la fonte (e2e) e chiede frenata, la velocità reale dopo 2 s / 4 s è "
    "<b>sopra</b> la velocità prevista dal modello con guadagno 1.0 e <b>sotto</b> con guadagno 1.55 (segno invertito, "
    "≈1.5 km/h dopo 4 s). Cioè: con 1.55 l'auto rallenta più del piano del modello. Effetto piccolo per singolo ciclo, "
    "ma sistematico; diverse route/modelli tra i due regimi sono un fattore confondente.</p>")


def dec_notes(decs):
  n = len(decs)
  to_acc = decs[decs["to"] == "acc"]
  bad = to_acc[to_acc.model_at_switch < -0.3]
  up = bad[bad.step > 0.5]
  to_bl = decs[decs["to"] == "blended"]
  down = to_bl[to_bl.step < -0.5]
  return (
    "<p>%d switch DEC con openpilot ingaggiato (≈2.4 al minuto). %d passaggi a <i>acc</i> mentre il modello chiedeva &lt; −0.3 "
    "m/s²: la fonte e2e esce dal min() e il target sale (mediana %+.2f m/s²; %d volte &gt; +0.5). %d passaggi a <i>blended</i> "
    "con gradino di aTarget &lt; −0.5 m/s². È un meccanismo di <b>commutazione di fonte nel planner sunnypilot</b> (non opendbc) "
    "che produce frena-rilascia-frena negli avvicinamenti.</p>" % (n, len(bad), bad.step.median() if len(bad) else 0.0, len(up),
                                                                  len(down)))


def gas_notes(gas):
  return (
    "<p>Override del guidatore con acceleratore mentre openpilot stava decelerando (≥ 0.5 s di richiesta &lt; −0.3 m/s², "
    "&gt; 8 km/h). È l'indicatore più diretto di decelerazione giudicata inutile. Nel regime 1.55 la maggior parte è "
    "su fonte lead (MPC, lead da visione), poi e2e, poi cruise (target ridotto da SCC/SLA o set speed). Lista completa: "
    "<code>gas_overrides.csv</code>.</p>")


def traffic_light_notes(events):
  return TL_HTML


def roundabout_notes(events):
  return RB_HTML


TL_HTML = r"""
<p>14 eventi classificati "semaforo" (semaforo OSM sulla via percorsa, nel verso di marcia se taggato, tra −25 e +80 m dal minimo). I semafori
mappati in OSM in Svizzera sono spesso al centro dell'incrocio: la distanza "semaforo − punto di arresto" ha incertezza ±15 m e
<b>non</b> è la distanza dalla linea di arresto. Tutti gli arresti completi a semaforo nel regime attuale avvengono con un lead davanti o con
il conducente che prende il controllo; nessuno permette di misurare "5–10 m prima della linea".</p>
<p>Schema ricorrente (E245/E246, E473, E500; in E472 ed E387 l'onset è su lead1, poi e2e): DEC resta in <i>acc</i> mentre il modello inizia già a chiedere decelerazione; poi
passa in <i>blended</i> e la fonte diventa e2e con un gradino a −0.7…−1.4 m/s²; il PSA moltiplica per 1.55 (clamp −2.0); la velocità scende
sotto la traiettoria del modello, il modello chiede meno freno o accelerazione, il freno PSA esce e rientra (2–4 ingressi), il conducente
spesso preme il gas. Distanza dell'onset dal semaforo OSM: 120–480 m.</p>
"""
RB_HTML = r"""
<p>15 eventi "rotonda" (anello OSM <code>junction=roundabout</code> attraversato dalla traiettoria; minimo di velocità tra 60 m dopo e 150 m
prima dell'ingresso). Nella maggior parte l'inizio della richiesta &lt; −0.5 m/s² è a 220–420 m dall'ingresso. Separare:</p>
<ul>
<li><b>SCC-Map / SCC-Vision (settembre)</b>: E145, E084, E037, E047 → origine planner sunnypilot (target ridotto a 20–26 km/h), cruise a −1.2 m/s².</li>
<li><b>Modello</b>: E641 (quasi arresto senza lead), E090/E151 (settembre).</li>
<li><b>Lead reale / coda</b>: E643, E620, E668, parte di E667.</li>
<li><b>Set speed / vEgo sopra set speed</b>: E291, E292, inizio di E667.</li>
</ul>
<p>Un rallentamento dolce prima della rotonda è normale; i casi sospetti sono quelli con fonte SCC (settembre) e E641. Per E641 serve il video
del segmento 42 della route 00000111 (frame ~1100–1200 e segmento 43 inizio) per vedere se nell'anello c'era traffico.</p>
"""


def explain(ev):
  """Short automatic explanation from the measured pipeline, with alternatives."""
  parts = []
  src = ev.get("src_at_onset_plan05")
  cls = ev.get("map_class")
  if not ev.get("analysable"):
    return "openpilot longitudinale non attivo nel tratto di decelerazione: guida del conducente, utile solo come riferimento."
  if src == "e2e":
    parts.append("La decelerazione nasce dal <b>modello</b> (fonte e2e, DEC in blended).")
  elif src in ("lead0", "lead1"):
    parts.append("La decelerazione nasce dall'<b>MPC su lead da visione</b> (%s)." % src)
  elif src == "cruise":
    sp = ev.get("eng_sp_sources") or {}
    sub = None
    if sp:
      sub = max(sp, key=sp.get)
    if sub and sub != "cruise":
      parts.append("La decelerazione nasce dal candidato <b>cruise</b> con target ridotto da <b>%s</b> (sunnypilot)." % sub)
    else:
      parts.append("La decelerazione nasce dal candidato <b>cruise</b> (velocità sopra il set speed o reset dopo override).")
  else:
    parts.append("Nessuna richiesta sostenuta &lt; −0.5 m/s² mentre ingaggiato: rallentamento lieve o guidato dal conducente.")
  r = ev.get("resp_meas_over_req")
  if r is not None and r > 1.3:
    parts.append("Il controller PSA amplifica: decelerazione misurata %.2f× la richiesta (guadagno 1.55); il veicolo esegue il comando." % r)
  if (ev.get("eng_dec_switches") or 0) >= 3:
    parts.append("%d switch DEC durante l'avvicinamento: la fonte entra/esce dal min() del planner." % ev["eng_dec_switches"])
  if ev["kind"] == "stop" and ev.get("lead_at_stop"):
    parts.append("All'arresto c'è un lead (visione) a %s m: il punto di arresto è vincolato dal veicolo davanti "
                 "(MPC STOP_DISTANCE = 6 m) o dal modello, non dalla linea." % _f(ev.get("lead_d_at_stop")))
  if "possibly_premature_braking" in (ev.get("flags") or []):
    parts.append("Il conducente ha premuto l'acceleratore durante la frenata (o l'onset è molto lontano dall'incrocio): possibile frenata anticipata.")
  if cls in ("traffic_light", "roundabout"):
    parts.append("Alternative non escludibili senza video: semaforo rosso/giallo, pedoni, traffico in rotonda, veicolo che svolta.")
  return " ".join(parts)


def limits(events):
  return LIMITS_HTML


LIMITS_HTML = r"""
<ul>
<li><b>Nessun video</b>: stato del semaforo, linea di arresto, pedoni, ciclisti e traffico in rotonda non osservati. Per verificarli Cristian deve
scaricare i video (es. <code>download_logs.sh --route &lt;route&gt;</code> senza <code>--no-video</code>) almeno dei segmenti nelle schede:
00000111--5190df2b4b seg 41–43 e 59, 00000113--45e8445fdf seg 10–11, 0000010c--3e15dcd7cd seg 33–35, 0000010d--cebfdc9d54 seg 10–11,
000000c5--eeb1073747 seg 5–8, 00000070--97bd1ebf25 seg 6–7, 00000058--c9356c573d seg 7. Ogni scheda riporta il frame fcamera.</li>
<li>Il codice openpilot in auto (2026.003.000, commit fb1c36569 / a8b556a07 del fork) <b>non è presente</b> nel checkout locale (HEAD 001096d17
del 16 ottobre, che ha già rimosso DEC): la logica DEC è stata letta da <code>git show 5ec0c0219^</code>. I campi registrati confermano DEC attivo.</li>
<li>Il confronto guadagno 1.0 vs 1.55 è confuso da modelli diversi (OP10/Terrible/RDF/RDF V2) e SCC diversi: stima di direzione, non di entità esatta.</li>
<li>GPS ±2–5 m e posizione OSM del semaforo/anello ±5–15 m: le distanze sono indicative. Overpass ha risposto 502/504 a diverse richieste
(riprovate); 50 eventi senza fix GPS valido (inizio route).</li>
<li>Eventi "slowdown" di guida non ingaggiata e ad alta velocità non sono stati mappati (solo 351 dei 691 eventi), per limitare le query.</li>
<li>Gli stati privati del controller PSA (filtro, isteresi) non sono nei log: sono dedotti dal CAN 0x2B6 trasmesso.</li>
<li>Domande aperte: (1) il "5–10 m" si verifica primo in fila con rosso? servono 2–3 casi con video; (2) traffico nell'anello in E641;
(3) il comportamento senza DEC (build attuale dopo il sunset) cambia gli onset? servono nuove route registrate con video.</li>
</ul>
<h3>Correzione opendbc PSA – solo descrizione (non implementata)</h3>
<p>I dati giustificano di <b>togliere l'amplificazione 1.55</b> nel ramo freno: il veicolo esegue già la decelerazione richiesta (|misurata − comando|
≤ 0.1 m/s²) e LongControl non ha integrale, quindi 1.55 produce ≈1.4× la decelerazione pianificata. La mappa identità
<code>BRAKE_ACCEL_BP/V</code> già nel working tree va nella direzione giusta per −0.3…−1.5 m/s²; la "frenata debole" storica coincide con il clamp
−1.0 delle prime build, non con un guadagno unitario. Restano da verificare prima di qualsiasi prova su strada (supervisionata): autorità
sopra −1.5 m/s² e in discesa, effetto sull'isteresi freno/coppia (rischio di più ingressi/uscite), richieste brevi vicino a 0. <b>Non</b> risolve:
onset anticipati del modello, SCC/SLA, commutazioni DEC, gap 6 m dietro un lead: sono openpilot/sunnypilot e non vanno "nascosti" nel
controller PSA.</p>
"""
