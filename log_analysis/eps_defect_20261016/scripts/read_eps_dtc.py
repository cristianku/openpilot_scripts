# [eps dtc] - START
"""Read EPS DTCs through an already permitted pandad transport; never change safety.

Run parked, ignition on. Stock offroad NO_OUTPUT is intentionally refused.
No Panda connection, session changes, tester-present, clears, or parameter writes.
"""
import argparse
import json
import sys
import time
from pathlib import Path

TX_ADDR, RX_ADDR, BUS = 0x6B5, 0x695, 0
REQUEST_FRAME = bytes.fromhex('031902ff00000000')
FLOW_FRAME = bytes.fromhex('3000000000000000')


def decode_response(raw):
  if len(raw) < 3 or raw[:2] != b'\x59\x02' or (len(raw) - 3) % 4:
    raise ValueError('Attesa risposta UDS 59 02, availability mask e record da 4 byte')
  return {'raw_uds': raw.hex(), 'status_availability': raw[2],
          'dtcs': [{'dtc_hex': raw[i:i+3].hex(), 'status': raw[i+3]} for i in range(3, len(raw), 4)]}


def validate_frame(addr, data, bus):
  if (addr, bus) != (TX_ADDR, BUS) or bytes(data) not in (REQUEST_FRAME, FLOW_FRAME):
    raise ValueError('Consentiti solo 19 02 FF e ISO-TP flow control su 0x6B5 bus 0')


def require_read_transport(is_onroad, started, safety_model, safety_param):
  if is_onroad != b'0' or started or safety_model != 'elm327' or not (safety_param & 1):
    raise RuntimeError('Richiesti offroad e ELM327 gia attivo senza multiplexing OBD. '
                       'NO_OUTPUT/PSA non consentono questa query; nessun cambio automatico.')


def read_dtcs(transport):
  from opendbc.car.uds import UdsClient, DTC_REPORT_TYPE, DTC_STATUS_MASK_TYPE
  client = UdsClient(transport, TX_ADDR, rx_addr=RX_ADDR, bus=BUS, timeout=2,
                     response_pending_timeout=2)
  payload = client.read_dtc_information(DTC_REPORT_TYPE.DTC_BY_STATUS_MASK, DTC_STATUS_MASK_TYPE.ALL)
  return decode_response(b'\x59\x02' + payload)


class PandadTransport:
  def __init__(self):
    from openpilot.cereal import messaging
    self.messaging = messaging
    self.sm = messaging.SubMaster(['pandaStates', 'deviceState'])
    self.deadline = time.monotonic() + 20
    end = time.monotonic() + 5
    while not all(self.sm.seen.values()) and time.monotonic() < end:
      self.sm.update(100)
    self._check()
    self.rx = messaging.sub_sock('can', timeout=0)
    # Never compete with an existing publisher; msgq rejects multiple publishers.
    self.tx = messaging.pub_sock('sendcan')

  def _check(self):
    if time.monotonic() > self.deadline:
      raise TimeoutError('Limite totale di 20 secondi raggiunto')
    self.sm.update(0)
    for topic, max_age in (('pandaStates', .5), ('deviceState', 3)):
      if not self.sm.seen[topic] or not self.sm.valid[topic] or time.monotonic() - self.sm.recv_time[topic] > max_age:
        raise RuntimeError(f'{topic} assente, invalido o non aggiornato')
    pandas = self.sm['pandaStates']
    if len(pandas) != 1:
      raise RuntimeError('Atteso un solo panda; mapping bus non verificato')
    is_onroad = Path('/data/params/d/IsOnroad').read_bytes().strip()
    require_read_transport(is_onroad, bool(self.sm['deviceState'].started),
                           str(pandas[0].safetyModel), int(pandas[0].safetyParam))

  def can_send(self, addr, data, bus, timeout=None):
    self._check()
    validate_frame(addr, data, bus)
    msg = self.messaging.new_message('sendcan', 1, valid=True)
    msg.sendcan[0].address = addr
    msg.sendcan[0].dat = bytes(data)
    msg.sendcan[0].src = bus
    self.tx.send(msg.to_bytes())

  def can_recv(self):
    self._check()
    out = []
    for event in self.messaging.drain_sock(self.rx, wait_for_one=False):
      for frame in event.can:
        if frame.address == TX_ADDR and frame.src == 192 + BUS:
          raise RuntimeError('Query scartata dalla safety: nessun tentativo di aggirarla')
        if frame.address == RX_ADDR and frame.src == BUS:
          out.append((frame.address, bytes(frame.dat), frame.src))
    return out


def main():
  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument('--decode', metavar='UDS_HEX', help='Decodifica offline una risposta completa 59 02 ...')
  args = parser.parse_args()
  try:
    result = decode_response(bytes.fromhex(args.decode)) if args.decode is not None else read_dtcs(PandadTransport())
    print(json.dumps(result, indent=2))
    return 0
  except Exception as exc:
    print(f'{type(exc).__name__}: {exc}', file=sys.stderr)
    return 1


if __name__ == '__main__':
  sys.exit(main())
# [eps dtc] - END
