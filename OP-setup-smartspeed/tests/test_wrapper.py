#!/usr/bin/env python3
"""The smartspeed wrapper's routing, without cloning or pushing: what it hands the testing setup's common script."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

WRAPPER = Path(__file__).resolve().parents[1] / 'scripts' / 'setup_smartspeed.sh'
KEYS = ('BRANCH', 'OPENPILOT_DIR', 'OPENPILOT_SOURCE_REPO', 'OPENPILOT_SOURCE_BRANCH', 'OPENPILOT_SOURCE_COMMIT',
        'NAV2PILOT_BRANCH', 'USE_CUSTOM_NEURAL_NETWORK_DATA', 'SKIP_OPENDBC', 'SKIP_PSA_TORQUED',
        'SKIP_EXTRA_MODEL_CATALOG', 'SKIP_SPEED_LIMITS', 'SPEED_LIMITS_SOURCE_BRANCH', 'COMMIT_MESSAGE')


class WrapperTest(unittest.TestCase):
  def run_wrapper(self, args, overrides=None):
    with tempfile.TemporaryDirectory() as tmp:
      dump = Path(tmp) / 'dump.py'
      dump.write_text(f'import json, os\nprint(json.dumps({{k: os.environ.get(k, "") for k in {KEYS!r}}}))\n')
      common = Path(tmp) / 'common.sh'
      common.write_text(f'#!/usr/bin/env bash\npython3 {dump}\n')
      env = {key: value for key, value in os.environ.items()
             if not key.startswith(('OPENPILOT_', 'NAV2PILOT_', 'SKIP_', 'SPEED_LIMITS_', 'COMMIT_MESSAGE'))}
      env['COMMON_SCRIPT'] = str(common)
      env.update(overrides or {})
      return subprocess.run(['bash', str(WRAPPER), *args], env=env, capture_output=True, text=True)

  def test_builds_sunnypilot_master_with_only_the_recording(self):
    result = self.run_wrapper([])
    self.assertEqual(result.returncode, 0, result.stderr)
    actual = json.loads(result.stdout)
    self.assertEqual(actual['BRANCH'], 'smartspeed')
    self.assertEqual(actual['OPENPILOT_DIR'], 'new_openpilot_smartspeed')
    self.assertEqual(actual['OPENPILOT_SOURCE_REPO'], 'https://github.com/sunnypilot/sunnypilot.git')
    self.assertEqual(actual['OPENPILOT_SOURCE_BRANCH'], 'master')
    self.assertEqual(actual['OPENPILOT_SOURCE_COMMIT'], '')
    self.assertEqual(actual['NAV2PILOT_BRANCH'], '')
    self.assertEqual(actual['USE_CUSTOM_NEURAL_NETWORK_DATA'], 'false')
    self.assertEqual(actual['SKIP_OPENDBC'], 'true')
    self.assertEqual(actual['SKIP_PSA_TORQUED'], 'true')
    self.assertEqual(actual['SKIP_EXTRA_MODEL_CATALOG'], 'true')
    # The speed-limits step applies the one commit of full-res-record, not the speed-limit work.
    self.assertEqual(actual['SKIP_SPEED_LIMITS'], 'false')
    self.assertEqual(actual['SPEED_LIMITS_SOURCE_BRANCH'], 'full-res-record')
    self.assertIn('full resolution', actual['COMMIT_MESSAGE'])

  def test_pinned_commit_never_nav(self):
    result = self.run_wrapper(['master=1234567'], {'SKIP_NAV': 'false'})
    self.assertEqual(result.returncode, 0, result.stderr)
    actual = json.loads(result.stdout)
    self.assertEqual(actual['OPENPILOT_SOURCE_COMMIT'], '1234567')
    self.assertEqual(actual['OPENPILOT_SOURCE_BRANCH'], 'master')
    self.assertEqual(actual['NAV2PILOT_BRANCH'], '')

  def test_help_runs_nothing(self):
    for args in (['--help'], ['help'], ['-h']):
      with self.subTest(args=args):
        result = self.run_wrapper(args, {'COMMON_SCRIPT': '/nonexistent'})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('installer.comma.ai/cristianku/smartspeed', result.stdout)

  def test_bad_arguments_stop_before_the_setup(self):
    for args in (['sunny'], ['master=xyz'], ['master', 'extra']):
      with self.subTest(args=args):
        result = self.run_wrapper(args, {'COMMON_SCRIPT': '/nonexistent'})
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertNotIn('missing', result.stderr)


if __name__ == '__main__':
  unittest.main()
