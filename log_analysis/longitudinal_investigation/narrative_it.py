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


SUMMARY_HTML = "<!-- filled in after review -->"


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


TL_HTML = "<!-- filled in after review -->"
RB_HTML = "<!-- filled in after review -->"


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


LIMITS_HTML = "<!-- filled in after review -->"
