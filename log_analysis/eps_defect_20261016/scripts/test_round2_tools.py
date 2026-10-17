# [eps review] - START
import unittest
import read_eps_dtc as dtc
from cadence_100hz import summarize


class FakeEps:
  def __init__(self):
    self.sent = []
    self.queue = []

  def can_send(self, addr, data, bus, timeout=None):
    dtc.validate_frame(addr, data, bus)
    self.sent.append(bytes(data))
    if bytes(data) == dtc.REQUEST_FRAME:
      self.queue.append((dtc.RX_ADDR, bytes.fromhex('100b5902ff123456'), dtc.BUS))
    elif bytes(data) == dtc.FLOW_FRAME:
      self.queue.append((dtc.RX_ADDR, bytes.fromhex('2101aabbcc020000'), dtc.BUS))

  def can_recv(self):
    result, self.queue = self.queue, []
    return result


class TestReadOnlyDtc(unittest.TestCase):
  def test_dtc_records_and_status_are_preserved(self):
    result = dtc.decode_response(bytes.fromhex('5902ff12345601aabbcc02'))
    self.assertEqual(result['status_availability'], 255)
    self.assertEqual(result['dtcs'], [{'dtc_hex': '123456', 'status': 1}, {'dtc_hex': 'aabbcc', 'status': 2}])

  def test_empty_report_is_distinct_from_no_response(self):
    self.assertEqual(dtc.decode_response(bytes.fromhex('5902ff'))['dtcs'], [])
    for raw in ('', '5902', '7f1911', '5902ff1234'):
      with self.subTest(raw=raw), self.assertRaises(ValueError):
        dtc.decode_response(bytes.fromhex(raw))

  def test_only_read_request_and_flow_control_are_allowed(self):
    for data in (dtc.REQUEST_FRAME, dtc.FLOW_FRAME):
      dtc.validate_frame(dtc.TX_ADDR, data, dtc.BUS)
    for addr, data, bus in ((0x6B6, dtc.REQUEST_FRAME, 0), (0x6B5, dtc.REQUEST_FRAME, 1),
                             (0x6B5, bytes.fromhex('0210010000000000'), 0),
                             (0x6B5, bytes.fromhex('0414ffffff000000'), 0)):
      with self.subTest(addr=addr, data=data.hex(), bus=bus), self.assertRaises(ValueError):
        dtc.validate_frame(addr, data, bus)

  def test_real_uds_client_receives_multiframe_report_without_session_change(self):
    eps = FakeEps()
    result = dtc.read_dtcs(eps)
    self.assertEqual(len(result['dtcs']), 2)
    self.assertEqual(eps.sent, [dtc.REQUEST_FRAME, dtc.FLOW_FRAME])

  def test_transport_refuses_onroad_or_non_diagnostic_safety(self):
    dtc.require_read_transport(b'0', False, 'elm327', 1)
    for state in ((b'1', False, 'elm327', 1), (b'0', True, 'elm327', 1),
                  (b'0', False, 'noOutput', 0), (b'0', False, 'psa', 0),
                  (b'0', False, 'elm327', 0)):
      with self.subTest(state=state), self.assertRaises(RuntimeError):
        dtc.require_read_transport(*state)


class TestCadenceSummary(unittest.TestCase):
  def test_zero_events_upper_bound_and_batched_echoes(self):
    result = summarize(1800, {'defects': 0}, {'echo': [0., .01, .02, .04]})
    self.assertAlmostEqual(result['zero_defect_upper95_per_hour'], 5.991464547, places=7)
    self.assertEqual(result['echo']['same_batch_pairs'], 1)
    self.assertEqual(result['echo']['max_ms'], 40)
    self.assertEqual(result['echo']['percent_gt_30ms'], 25)

  def test_missing_exposure_is_not_a_successful_zero_event_test(self):
    result = summarize(0, {'defects': 0}, {'echo': []})
    self.assertIsNone(result['zero_defect_upper95_per_hour'])


if __name__ == '__main__':
  unittest.main()
# [eps review] - END
