# /// script
# requires-python = ">=3.11"
# dependencies = ["pycapnp", "zstandard"]
# ///
# [eps cadence] - START
"""Offline rlog cadence by latActive; event timestamps are NOT wire timestamps.

Input: route directory containing segment directories, as for segstate.py.
Reads logs only; JSON goes to stdout. Reports missing/unreadable segments.
"""
import argparse
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


def summarize(seconds, counts, intervals):
  out = {'seconds': round(seconds, 3), **counts}
  out['zero_defect_upper95_per_hour'] = -math.log(.05) * 3600 / seconds if seconds > 0 and counts['defects'] == 0 else None
  for name, values in intervals.items():
    ordered = sorted(values)
    summary = {'interval_count': len(ordered)}
    if ordered:
      for label, p in (('p50_ms', .5), ('p95_ms', .95), ('p99_ms', .99), ('p999_ms', .999), ('max_ms', 1)):
        summary[label] = round(ordered[max(0, math.ceil(p * len(ordered)) - 1)] * 1000, 3)
      summary['same_batch_pairs'] = sum(x == 0 for x in ordered)
      for threshold in (.020, .030, .050, .100):
        summary[f'percent_gt_{round(threshold*1000)}ms'] = round(100 * sum(x > threshold for x in ordered) / len(ordered), 4)
    out[name] = summary
  return out


def analyze(route):
  import psa_eps_timeline as pet
  schema = pet.load_schema()
  eps_spec = pet.dbc_signals(pet.DBC, {0x495})[0x495]['EPS_STATE_LKA']
  groups = {name: {'seconds': 0., 'counts': dict(defects=0, m795_rising=0, rejected_3f2=0, send_3f2=0, echo_3f2=0),
                   'intervals': {'send': [], 'echo': []}} for name in ('unknown', 'inactive', 'active')}
  lat = 'unknown'; epoch = 0; prev_eps = prev_795 = None
  last = {}; previous_segment = None; errors = []; spi = []
  segments = sorted((p for p in route.iterdir() if (p / 'rlog.zst').is_file()), key=lambda p: int(p.name.rsplit('--', 1)[1]))
  if not segments:
    raise ValueError(f'Nessun rlog in {route}; i qlog non sono adatti alla cadenza')
  for seg in segments:
    number = int(seg.name.rsplit('--', 1)[1])
    if previous_segment is None or number != previous_segment + 1:
      if previous_segment is not None:
        errors.append({'segment': seg.name, 'error': 'segmenti intermedi mancanti'})
      lat = 'unknown'; epoch += 1; last.clear(); prev_eps = prev_795 = None
    records = []; segment_spi = []
    try:
      for event in pet.read_events(schema, seg / 'rlog.zst'):
        t = event.logMonoTime / 1e9; kind = event.which()
        if kind == 'carControl':
          records.append((t, 'lat', bool(event.carControl.latActive)))
        elif kind == 'sendcan':
          records.extend((t, 'send', None) for m in event.sendcan if m.address == 0x3F2 and m.src == 0)
        elif kind == 'can':
          records.append((t, 'tick', None))
          for m in event.can:
            if m.address == 0x3F2 and m.src in (128, 192):
              records.append((t, 'echo' if m.src == 128 else 'reject', None))
            elif m.address == 0x495 and m.src == 0 and len(m.dat) >= 3:
              records.append((t, 'eps', int(pet.extract(bytes(m.dat), eps_spec))))
            elif m.address == 0x795 and m.src == 0 and len(m.dat):
              records.append((t, 'm795', int(m.dat[0])))
        elif kind == 'pandaStates':
          segment_spi.extend((t, i, int(p.spiErrorCount)) for i, p in enumerate(event.pandaStates))
    except Exception as exc:
      errors.append({'segment': seg.name, 'error': str(exc)})
      previous_segment = None; lat = 'unknown'; epoch += 1; last.clear(); prev_eps = prev_795 = None
      continue
    records.sort(key=lambda item: item[0])
    previous_t = None
    for t, kind, value in records:
      if previous_t is not None:
        groups[lat]['seconds'] += t - previous_t
      previous_t = t
      if kind == 'lat':
        new_lat = 'active' if value else 'inactive'
        if new_lat != lat:
          epoch += 1; lat = new_lat
      g = groups[lat]
      if kind in ('send', 'echo'):
        g['counts'][f'{kind}_3f2'] += 1
        if kind in last and last[kind][1] == epoch:
          g['intervals'][kind].append(t - last[kind][0])
        last[kind] = (t, epoch)
      elif kind == 'reject':
        g['counts']['rejected_3f2'] += 1
      elif kind == 'eps':
        if value == 4 and prev_eps is not None and prev_eps != 4:
          g['counts']['defects'] += 1
        prev_eps = value
      elif kind == 'm795':
        if value == 1 and prev_795 is not None and prev_795 != 1:
          g['counts']['m795_rising'] += 1
        prev_795 = value
    spi.extend(segment_spi)
    previous_segment = number
  return {'route': route.name, 'timestamp_basis': 'logMonoTime of event batches, not wire time',
          'segments_read': len(segments) - sum('segmenti intermedi' not in x['error'] for x in errors),
          'errors': errors, 'groups': {k: summarize(**v) for k, v in groups.items()},
          'spi_first_last': [spi[0], spi[-1]] if spi else []}


def main():
  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument('routes', type=Path, nargs='+')
  args = parser.parse_args()
  for route in args.routes:
    print(json.dumps(analyze(route), sort_keys=True))


if __name__ == '__main__':
  main()
# [eps cadence] - END
