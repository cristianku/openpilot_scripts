# [radar diagnosis] - START
from pathlib import Path
import bisect
import json
import statistics

ANALYSIS_DIR = Path(__file__).resolve().parent
exec((ANALYSIS_DIR / 'compare_radar_logs.py').read_text().split('for name,path in routes.items():')[0])
from opendbc.car.uds import get_dtc_num_as_str
selected = {0x552, 0x55F, 0x776, 0x76D, 0x768, 0x775, 0x116, 0x32D, 0x2F8, 0x318, 0x408}
rows = []
start = None
for f in sorted(routes['test'].glob('*/rlog.zst')):
  raw = zstandard.ZstdDecompressor().stream_reader(f.open('rb')).read()
  for e in schema.Event.read_multiple_bytes(raw):
    if start is None:
      start = e.logMonoTime
    if e.which() != 'can':
      continue
    t = (e.logMonoTime - start) / 1e9
    for c in e.can:
      if c.address in selected and c.src in (0, 1, 2):
        rows.append({'t': t, 'addr': c.address, 'src': c.src, 'data': bytes(c.dat).hex()})
rows.sort(key=lambda r: r['t'])
clocks = []
for r in rows:
  if r['addr'] == 0x552 and r['src'] == 1:
    b = bytes.fromhex(r['data'])
    ticks = int.from_bytes(b[:4], 'big')
    if ticks < 0xFFFFFFFE:
      clocks.append({'t': r['t'], 'clock_s': ticks / 10, 'reset_counter': b[7], 'data': r['data']})
offsets = [c['clock_s'] - c['t'] for c in clocks]
clock_model = {'samples': len(clocks), 'offset_median': statistics.median(offsets),
               'offset_min': min(offsets), 'offset_max': max(offsets),
               'reset_counters': sorted({c['reset_counter'] for c in clocks}),
               'reference_resolution_s': 0.1,
               'timing_caveat': 'Indicative alignment assumes a common BSI clock and allows +/-0.1 s for quantization. ECU synchronization and transmission latency are not independently bounded.',
               'excluded_from_alignment': {'0x775': 'Reference 51.7 s is not established on the BSI clock; do not assign an event time.'}}

clock_times = [c['t'] for c in clocks]
jdd = []
for r in rows:
  if r['addr'] not in (0x776, 0x76D, 0x768, 0x775) or r['src'] == 2:
    continue
  b = bytes.fromhex(r['data'])
  if (b[0] >> 4) & 3 != 1:
    continue
  d = dict(r)
  d.update(raw_dtc=b[1:4].hex().upper(), dtc=get_dtc_num_as_str(b[1:3]).upper() + f':{b[3]:02X}',
           status=(b[0] >> 3) & 1,
           reference_s=int.from_bytes(b[4:8], 'big') / 10)
  d['jdd_layout'] = 'historical DBC' if r['addr'] in (0x775, 0x776) else 'shared JDD layout inferred from payloads'
  d['bsi_clock_alignment'] = 'not established' if r['addr'] == 0x775 else 'compatible with this route; common clock assumed'
  d['event_t_estimate'] = None
  d['event_t_range_with_quantization'] = None
  if r['addr'] != 0x775:
    d['event_t_estimate'] = d['reference_s'] - clock_model['offset_median']
    d['event_t_range_with_quantization'] = [d['reference_s'] - max(offsets) - 0.1,
                                           d['reference_s'] - min(offsets) + 0.1]
  i = bisect.bisect_right(clock_times, r['t']) - 1
  if i >= 0:
    d['previous_bsi_clock'] = clocks[i]
  jdd.append(d)
summary = []
for key in sorted({(d['addr'], d['raw_dtc'], d['status'], d['reference_s']) for d in jdd}):
  samples = [d for d in jdd if (d['addr'], d['raw_dtc'], d['status'], d['reference_s']) == key]
  summary.append({'addr': hex(key[0]), 'raw_dtc': key[1], 'status': key[2], 'reference_s': key[3],
                  'n': len(samples), 'first_rx': samples[0]['t'], 'last_rx': samples[-1]['t'],
                  'dtc': samples[0]['dtc'], 'bsi_clock_alignment': samples[0]['bsi_clock_alignment'],
                  'event_t_estimate': samples[0]['event_t_estimate'],
                  'event_t_range_with_quantization': samples[0]['event_t_range_with_quantization']})
result = {'clock_model': clock_model, 'jdd_summary': summary, 'jdd_frames': jdd, 'bsi_clocks': clocks, 'can_frames': rows}
(ANALYSIS_DIR / 'diagnostic_timeline.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps({'clock_model': clock_model, 'jdd_summary': summary}, indent=2))
# [radar diagnosis] - END
