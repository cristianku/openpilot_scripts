# /// script
# requires-python = ">=3.11"
# dependencies = ["numpy", "pandas"]
# ///
"""Step 7: local HTML report (Italian) from the outputs of the previous steps.

Reads out/*.json|csv and out/figures/*; the narrative conclusions live in
narrative_it.py (kept separate so numbers here stay reproducible).
Output: out/report.html (open it locally; it references figures/ next to it).
"""

import html
import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import OUT_DIR  # noqa: E402
import narrative_it  # noqa: E402

FIG = OUT_DIR / "figures"


def esc(x):
  if x is None:
    return "–"
  if isinstance(x, float):
    if x != x:
      return "–"
    return "%.2f" % x if abs(x) < 100 else "%.0f" % x
  return html.escape(str(x))


def table(df, cols=None, max_rows=400):
  if cols is not None:
    df = df[cols]
  out = ["<table><thead><tr>"]
  for c in df.columns:
    out.append("<th>%s</th>" % esc(c))
  out.append("</tr></thead><tbody>")
  n = 0
  for _, r in df.iterrows():
    n += 1
    if n > max_rows:
      break
    out.append("<tr>")
    for c in df.columns:
      out.append("<td>%s</td>" % esc(r[c]))
    out.append("</tr>")
  out.append("</tbody></table>")
  return "".join(out)


CSS = """
body{font-family:-apple-system,Helvetica,Arial,sans-serif;max-width:1250px;margin:20px auto;padding:0 16px;color:#222}
h1{font-size:24px} h2{font-size:20px;border-bottom:2px solid #ddd;padding-bottom:4px;margin-top:36px}
h3{font-size:16px;margin-top:24px}
table{border-collapse:collapse;font-size:12px;margin:8px 0}
th,td{border:1px solid #ddd;padding:3px 6px;text-align:right} th{background:#f3f3f3}
td:first-child,th:first-child{text-align:left}
.box{background:#fff8e1;border-left:4px solid #f9a825;padding:10px 14px;margin:12px 0}
.ok{background:#e8f5e9;border-left:4px solid #43a047;padding:10px 14px;margin:12px 0}
.warn{background:#ffebee;border-left:4px solid #e53935;padding:10px 14px;margin:12px 0}
.card{border:1px solid #ccc;border-radius:6px;padding:10px;margin:18px 0}
.flags span{display:inline-block;background:#eceff1;border-radius:3px;padding:1px 6px;margin:2px;font-size:11px}
.insp{font-family:monospace;font-size:12px;background:#f7f7f7;padding:6px;min-height:36px;white-space:pre}
img.tel{width:100%;cursor:crosshair} img.map{width:430px}
.row{display:flex;gap:12px;align-items:flex-start;flex-wrap:wrap}
code{background:#f3f3f3;padding:1px 4px}
"""

JS = """
function inspect(ev, id){
  var img = ev.target; var r = img.getBoundingClientRect();
  var fx = (ev.clientX - r.left) / r.width;
  var meta = window.SERIES[id]; if(!meta){return;}
  var x = meta.x0 + (fx - meta.left) / (meta.right - meta.left) * (meta.x1 - meta.x0);
  var best = null; var bd = 1e9;
  for (var i = 0; i < meta.rows.length; i++){ var d = Math.abs(meta.rows[i][0] - x); if (d < bd){bd = d; best = meta.rows[i];} }
  if(!best){return;}
  var t = ['t_rel', 'route_t', 'seg', 'seg_t', 'fcam_frame', 'kmh', 'model_a', 'plan_a', 'source', 'DEC', 'cc_accel', 'PSA_brake', 'aEgo', 'lead_d', 'model_stop_x'];
  var s = ''; for (var k = 0; k < t.length; k++){ s += t[k] + '=' + (best[k] === null ? '–' : best[k]) + '  '; if (k == 4){ s += '\\n'; } }
  document.getElementById('insp_' + id).textContent = s + '\\n(video: fcamera.hevc del segmento ' + best[2] + ', frame ' + (best[4] === null ? '?' : best[4]) + ' a 20 fps)';
}
"""


def card(ev):
  eid = ev["event_id"]
  tel = FIG / (eid + "_telemetry.png")
  mp = FIG / (eid + "_map.png")
  ser = FIG / (eid + "_series.json")
  parts = ['<div class="card" id="%s">' % eid]
  parts.append("<h3>%s — %s, segmento %s, t_seg %.1f s (route_t %.1f s) — %s / %s — rank %s, score %s, confidenza %s</h3>" % (
    eid, esc(ev["route"]), esc(ev["seg"]), ev["seg_t"], ev["t_min"], esc(ev.get("map_class")), esc(ev["kind"]),
    esc(ev.get("rank")), esc(ev.get("score")), esc(ev.get("confidence"))))
  fl = ev.get("flags") or []
  parts.append('<div class="flags">' + "".join("<span>%s</span>" % esc(f) for f in fl) + "</div>")
  facts = []
  facts.append("v %.0f → %.1f km/h; aEgo min %.2f m/s²" % (ev["v_peak_kph"], ev["v_min_kph"], ev["a_min"]))
  if ev.get("t_onset_plan05") is not None:
    facts.append("prima richiesta sostenuta < −0.5 m/s² a %.1f s prima del minimo, a %s km/h, %s m prima del minimo, fonte <b>%s</b>" % (
      ev["t_min"] - ev["t_onset_plan05"], esc(ev.get("v_onset_plan05_kph")), esc(ev.get("dist_onset_plan05_to_min")),
      esc(ev.get("src_at_onset_plan05"))))
  facts.append("fonti planner (ingaggiato): %s; DEC blended %s, switch DEC %s; salti aTarget > +0.5: %s" % (
    esc(json.dumps(ev.get("eng_plan_sources"))), esc(ev.get("eng_blended_share")), esc(ev.get("eng_dec_switches")),
    esc(ev.get("eng_plan_up_jumps"))))
  if ev.get("resp_n", 0) and ev.get("resp_n", 0) >= 10:
    facts.append("frenata: richiesta media %s → comando PSA %s → misurata %s m/s² (misurata/richiesta %s)" % (
      esc(ev.get("resp_req_mean")), esc(ev.get("resp_cmd_mean")), esc(ev.get("resp_meas_mean")), esc(ev.get("resp_meas_over_req"))))
  facts.append("ingressi in modo freno PSA: %s; disingaggio: %s (%s km/h)" % (
    esc(ev.get("eng_brake_entries")), esc(ev.get("diseng_cause")), esc(ev.get("v_at_diseng_kph"))))
  if ev.get("lead_at_stop") is not None and ev["kind"] == "stop":
    facts.append("lead all'arresto: %s, gap %s m (traccia %s s, comparso a %s m, vmax lead %s km/h, parte prima di noi: %s)" % (
      esc(ev.get("lead_at_stop")), esc(ev.get("lead_d_at_stop")), esc(ev.get("lead_track_s")), esc(ev.get("lead_first_d")),
      esc(ev.get("lead_vmax_kph")), esc(ev.get("lead_departs_first"))))
  if ev.get("nearest_signal_rel_m") is not None:
    facts.append("semaforo OSM sul percorso: %s m oltre il punto di minimo/arresto (±15 m GPS+OSM; NON è la linea di arresto)" % esc(ev["nearest_signal_rel_m"]))
  if ev.get("nearest_roundabout_rel_m") is not None:
    facts.append("ingresso rotonda OSM: %s m oltre il minimo; %s m oltre l'inizio della richiesta (±15 m)" % (
      esc(ev["nearest_roundabout_rel_m"]), esc(ev.get("roundabout_entry_rel_onset_m"))))
  if ev.get("road_names"):
    facts.append("strada (OSM): %s; classi %s; maxspeed %s" % (esc(", ".join(ev["road_names"][:3])), esc(",".join(ev.get("road_classes") or [])),
                                                              esc(",".join(ev.get("osm_maxspeed") or []))))
  if ev.get("intent"):
    it = []
    for r in ev["intent"]:
      it.append("T−%ss: percorsi %s m, modello prevedeva %s m (err %s)" % (r["T"], esc(r["d_rem"]), esc(r.get("x_pred_T")), esc(r.get("err_pred_T"))))
    facts.append("intento del modello vs arresto reale: " + "; ".join(it))
  parts.append("<ul>" + "".join("<li>%s</li>" % f for f in facts) + "</ul>")
  parts.append("<p><b>Spiegazione (automatica, da verificare col video):</b> %s</p>" % narrative_it.explain(ev))
  parts.append('<div class="row">')
  if tel.exists():
    parts.append('<div style="flex:1;min-width:640px"><img class="tel" src="figures/%s" onclick="inspect(event, \'%s\')">'
                 '<div class="insp" id="insp_%s">clicca sul grafico per leggere i valori e il frame video corrispondente</div></div>' % (tel.name, eid, eid))
  if mp.exists():
    parts.append('<div><img class="map" src="figures/%s"></div>' % mp.name)
  parts.append("</div>")
  parts.append("<p><i>Video:</i> non disponibile in locale (nessun fcamera.hevc/qcamera.ts). Frame di riferimento al minimo: segmento %s, frame %s.</p>" % (
    esc(ev.get("fcam_seg")), esc(ev.get("fcam_frame"))))
  parts.append("</div>")
  series = None
  if ser.exists():
    series = ser.read_text()
  return "".join(parts), series


def main():
  inv = json.loads((OUT_DIR / "inventory.json").read_text())
  events = json.loads((OUT_DIR / "event_index.json").read_text())
  selected = json.loads((OUT_DIR / "selected_events.json").read_text())
  resp = pd.read_csv(OUT_DIR / "response_bins_summary.csv")
  track = pd.read_csv(OUT_DIR / "plan_tracking.csv")
  decs = pd.read_csv(OUT_DIR / "dec_switches.csv")
  gas = pd.read_csv(OUT_DIR / "gas_overrides.csv")
  queries = []
  qpath = OUT_DIR / "osm_queries.jsonl"
  if qpath.exists():
    for line in qpath.read_text().splitlines():
      queries.append(json.loads(line))

  H = ["<!doctype html><html lang='it'><head><meta charset='utf-8'><title>PSA 3008 – frenate anticipate semafori/rotonde</title>"
       "<style>%s</style><script>%s</script></head><body>" % (CSS, JS)]
  H.append(narrative_it.header(inv, events))
  H.append(narrative_it.summary(events, resp, track, decs, gas))

  # ---------------------------------------------------- data
  H.append("<h2>1. Dati analizzati</h2>")
  inv_rows = []
  for r in inv:
    if not r.get("op_long"):
      continue
    p = r.get("params", {})
    inv_rows.append({"route": r["route"], "segmenti": r["n_segments"], "commit": str(r.get("git_commit"))[:9],
                     "data GPS": r.get("gps_date"), "modello": p.get("ModelManager_ActiveBundle"),
                     "EM": p.get("ExperimentalMode"), "DEC": p.get("DynamicExperimentalControl"),
                     "SCC map": p.get("SmartCruiseControlMap"), "SCC vision": p.get("SmartCruiseControlVision"),
                     "SLA mode": p.get("SpeedLimitMode"), "personality": p.get("LongitudinalPersonality"),
                     "video": sum(r.get("cameras", {}).values())})
  H.append(table(pd.DataFrame(inv_rows)))
  H.append(narrative_it.data_notes(inv))

  # ---------------------------------------------------- method + external queries
  H.append("<h2>2. Metodo, soglie, query esterne</h2>")
  H.append(narrative_it.method())
  H.append("<h3>Query Overpass effettuate (%d richieste)</h3>" % len(queries))
  if queries:
    qdf = pd.DataFrame(queries)
    qdf["bbox_swne"] = qdf["bbox_swne"].apply(lambda b: ", ".join("%.4f" % x for x in b))
    H.append(table(qdf[["utc", "endpoint", "bbox_swne", "bbox_size_m", "status", "bytes"]]))

  # ---------------------------------------------------- cross-cutting evidence
  H.append("<h2>3. Evidenze trasversali (tutte le route)</h2>")
  H.append("<h3>3.1 Richiesta openpilot → comando PSA 0x2B6 → decelerazione misurata</h3>")
  H.append(table(resp.round(2)))
  H.append(narrative_it.response_notes(resp))
  H.append("<h3>3.2 L'auto segue la traiettoria del modello? (solo campioni con fonte e2e)</h3>")
  g = track.groupby(["T", "bin", "gain"]).agg(n=("dist_err_m", "size"), v_kmh=("v_kph", "median"),
                                             errore_velocita_kmh=("speed_err_kph", "median"),
                                             errore_distanza_m=("dist_err_m", "median"),
                                             routes=("route", "nunique")).reset_index()
  H.append(table(g.round(2)))
  H.append(narrative_it.tracking_notes(g))
  H.append("<h3>3.3 Switch DEC (acc ↔ blended) durante la guida ingaggiata</h3>")
  H.append(narrative_it.dec_notes(decs))
  H.append("<h3>3.4 Override con acceleratore durante una decelerazione di openpilot</h3>")
  gas["regime"] = gas.route.apply(lambda r: "1.55" if r >= "000000b8" else "1.0")
  H.append(table(gas.groupby(["regime", "src"]).size().reset_index(name="n")))
  H.append(narrative_it.gas_notes(gas))

  # ---------------------------------------------------- traffic lights / roundabouts
  idx = pd.read_csv(OUT_DIR / "event_index.csv")
  H.append("<h2>4. Semafori</h2>")
  H.append(narrative_it.traffic_light_notes(events))
  tl = idx[(idx.map_class == "traffic_light")]
  H.append(table(tl[["event_id", "route", "seg", "seg_t", "kind", "engaged", "engaged_at_min", "diseng_cause", "v_peak_kph",
                     "v_min_kph", "src_at_onset", "src_top", "dist_onset_to_min_m", "signal_from_onset_m",
                     "nearest_signal_rel_min_m", "lead_at_stop", "lead_gap_at_stop_m", "meas_over_req", "flags", "score"]]))
  H.append("<h2>5. Rotonde</h2>")
  H.append(narrative_it.roundabout_notes(events))
  rb = idx[(idx.map_class == "roundabout")]
  H.append(table(rb[["event_id", "route", "seg", "seg_t", "kind", "engaged", "diseng_cause", "v_peak_kph", "v_min_kph",
                     "src_at_onset", "src_top", "dist_onset_to_min_m", "roundabout_entry_from_onset_m",
                     "nearest_roundabout_rel_min_m", "meas_over_req", "dec_switches", "flags", "score"]]))

  # ---------------------------------------------------- ranking
  H.append("<h2>6. Indice eventi (prime 80 posizioni per score)</h2>")
  H.append("<p>Indice completo: <code>event_index.csv</code> / <code>event_index.json</code> (%d eventi).</p>" % len(idx))
  H.append(table(idx.head(80)[["rank", "event_id", "route", "seg", "seg_t", "kind", "map_class", "v_peak_kph", "v_min_kph",
                               "engaged", "src_at_onset", "flags", "score", "confidence"]]))

  # ---------------------------------------------------- cards
  H.append("<h2>7. Schede evento</h2>")
  H.append("<p>Grafici: t = 0 al minimo di velocità/arresto; linea viola tratteggiata = prima richiesta sostenuta &lt; −0.5 m/s². "
           "Clic su un grafico: valori a quell'istante + indice del frame fcamera da guardare quando il video sarà scaricato.</p>")
  series_js = []
  by_id = {}
  for ev in events:
    by_id[ev["event_id"]] = ev
  order = []
  for ev in events:
    if ev["event_id"] in selected:
      order.append(ev)
  for ev in order:
    c, s = card(ev)
    H.append(c)
    if s is not None:
      series_js.append("SERIES['%s']=%s;" % (ev["event_id"], s))
  H.append("<script>window.SERIES={};" + "".join(series_js) + "</script>")

  H.append("<h2>8. Rischi, limiti, domande aperte</h2>")
  H.append(narrative_it.limits(events))
  H.append("</body></html>")
  (OUT_DIR / "report.html").write_text("\n".join(H))
  print("report ->", OUT_DIR / "report.html")


if __name__ == "__main__":
  main()
