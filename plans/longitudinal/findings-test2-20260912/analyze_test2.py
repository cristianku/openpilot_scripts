# [radar test2] - START
from pathlib import Path
import collections
import hashlib
import json
import sys

import capnp
import zstandard

ROOT = Path('/Users/cristianku/GitHub/COMMA.AI/CRISTIANKU')
sys.path.insert(0, str(ROOT / 'opendbc'))
from opendbc.can.packer import CANPacker
from opendbc.can.parser import get_raw_value

OUTPUT = Path(__file__).resolve().parent
ROUTE = ROOT / 'openpilot_scripts/log_analysis/logitudinal_tests/test2/00000040--fa1066f2c5'
capnp.remove_import_hook()
schema = capnp.load(str(ROOT / 'new_openpilot_psa_torque_sunny_testing/openpilot/cereal/log.capnp'),
                    imports=[str(ROOT / 'opendbc/opendbc/car')])
packer = CANPacker('psa_aee2010_r3')
radar_ids = (0x2B6, 0x2F6, 0x4F6, 0x796)
selected_ids = (*radar_ids, 0x696, 0x6B6, 0x32D, 0x776, 0x768, 0x76D, 0x552)
out = {'init': [], 'params': [], 'logs': [], 'alerts': [], 'states': [], 'state_transitions': [], 'can': [], 'can_state_transitions': [], 'files': [], 'longactive': 0}
counts = collections.Counter()
previous_state = previous_alert = None
previous_can = {}
start = None
wanted = {0x32D: ('ACC_ETAT_DECEL_OR_ESP_STATUS', 'FA_ETAT_DECEL', 'DEFAUT_ACC_FREIN', 'VEHICLE_STANDSTILL'),
          0x2B6: ('ACC_STATUS', 'AUTO_BRAKING_STATUS', 'POTENTIAL_WHEEL_TORQUE_REQUEST', 'WHEEL_TORQUE_REQUEST'),
          0x2F6: ('ARC_STATUS', 'AUTO_BRAKING_STATUS')}
for file in sorted(ROUTE.glob('*/rlog.zst')):
  data = file.read_bytes()
  raw = zstandard.ZstdDecompressor().stream_reader(data).read()
  file_counts = collections.Counter()
  for e in schema.Event.read_multiple_bytes(raw):
    if start is None:
      start = e.logMonoTime
    t = (e.logMonoTime - start) / 1e9
    kind = e.which()
    counts[kind] += 1
    file_counts[kind] += 1
    if kind in ('can', 'sendcan'):
      for c in getattr(e, kind):
        if c.address not in selected_ids:
          continue
        payload = bytes(c.dat)
        row = {'t': t, 'kind': kind, 'src': c.src, 'addr': c.address, 'data': payload.hex()}
        out['can'].append(row)
        if c.address in wanted and c.src in (1, 129, 193):
          message = packer.dbc.addr_to_msg[c.address]
          values = {name: round(get_raw_value(payload, message.sigs[name]) * message.sigs[name].factor + message.sigs[name].offset, 6) for name in wanted[c.address]}
          key = (kind, c.src, c.address)
          if values != previous_can.get(key):
            out['can_state_transitions'].append({**row, 'values': values})
            previous_can[key] = values
    elif kind == 'carState':
      d = e.carState.to_dict()
      state = {name: d.get(name) for name in ('vEgo', 'vEgoRaw', 'gearShifter', 'standstill', 'gasPressed', 'brakePressed', 'canValid', 'accFaulted')}
      state['cruiseEnabled'] = d['cruiseState']['enabled']
      state['cruiseAvailable'] = d['cruiseState']['available']
      sample = {'t': t, **state}
      out['states'].append(sample)
      flags = {k: v for k, v in state.items() if k not in ('vEgo', 'vEgoRaw')}
      if flags != previous_state:
        out['state_transitions'].append(sample)
        previous_state = flags
    elif kind == 'carControl':
      out['longactive'] += int(e.carControl.longActive)
    elif kind in ('logMessage', 'errorLogMessage'):
      message = str(getattr(e, kind))
      try:
        parsed = json.loads(message)
        message = parsed.get('msg', parsed.get('message', message))
      except (ValueError, AttributeError):
        pass
      if not str(message).startswith('\x1b') and any(word in str(message).lower() for word in ('artiv', 'radar', 'can error', 'can invalid')):
        out['logs'].append({'t': t, 'message': message})
    elif kind in ('selfdriveState', 'controlsState'):
      alert = {k: v for k, v in getattr(e, kind).to_dict().items() if k.startswith('alert')}
      if alert and alert != previous_alert:
        out['alerts'].append({'t': t, **alert})
        previous_alert = alert
    elif kind == 'carParams':
      d = e.carParams.to_dict()
      out['params'].append({k: d.get(k) for k in ('carFingerprint', 'dashcamOnly', 'passive', 'openpilotLongitudinalControl', 'pcmCruise', 'safetyConfigs')})
    elif kind == 'initData':
      d = e.initData.to_dict()
      out['init'].append({k: d.get(k) for k in ('gitCommit', 'gitBranch', 'version', 'dongleId')})
  out['files'].append({'file': str(file.relative_to(ROUTE)), 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest(), 'events': dict(file_counts)})
out['duration'] = t
out['event_counts'] = dict(counts)
metrics = {}
for address in radar_ids:
  tx = [r for r in out['can'] if r['kind'] == 'sendcan' and r['src'] == 1 and r['addr'] == address]
  echo = [r for r in out['can'] if r['kind'] == 'can' and r['src'] == 129 and r['addr'] == address]
  native = [r for r in out['can'] if r['kind'] == 'can' and r['src'] == 1 and r['addr'] == address]
  refused = [r for r in out['can'] if r['kind'] == 'can' and r['src'] == 193 and r['addr'] == address]
  m = {'tx': len(tx), 'echo': len(echo), 'refused': len(refused), 'echo_payload_counts_match_tx': collections.Counter(r['data'] for r in tx) == collections.Counter(r['data'] for r in echo)}
  if tx:
    m.update(first_tx=tx[0], last_tx=tx[-1], first_echo=echo[0] if echo else None,
             max_tx_gap_ms=max((b['t'] - a['t']) * 1000 for a, b in zip(tx, tx[1:])) if len(tx) > 1 else None)
    before = [r for r in native if r['t'] < tx[0]['t']]
    after = [r for r in native if r['t'] > tx[-1]['t']]
    m['last_native_before'] = before[-1] if before else None
    m['first_native_after'] = after[0] if after else None
    m['handover_gap_ms'] = (echo[0]['t'] - before[-1]['t']) * 1000 if before and echo else None
    if address in (0x2B6, 0x2F6):
      byte_index = 7 if address == 0x2B6 else 6
      counters = [bytes.fromhex(r['data'])[byte_index] >> 4 for r in tx]
      m['counter_errors'] = sum(b != (a + 1) % 16 for a, b in zip(counters, counters[1:]))
      m['checksum_errors'] = sum((sum((b >> 4) + (b & 15) for b in bytes.fromhex(r['data'])) & 15) != (12 if address == 0x2B6 else 8) for r in tx)
  metrics[hex(address)] = m
out['radar_metrics'] = metrics
out['diagnostic_frames'] = [r for r in out['can'] if r['addr'] in (0x6B6, 0x696)]
(OUTPUT / 'test2.json').write_text(json.dumps(out, indent=2) + '\n')
summary = {k: v for k, v in out.items() if k not in ('can', 'states', 'event_counts')}
(OUTPUT / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
print(json.dumps(summary, indent=2))
# [radar test2] - END
