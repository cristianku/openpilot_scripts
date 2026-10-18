#!/usr/bin/env python3
"""Check wrapper routing without cloning, deleting checkouts, or pushing."""

# [nav source] - START
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


TORQUE_ROOT = Path(__file__).resolve().parents[1]
PEUGEOT_ROOT = Path(os.environ.get(
  "PEUGEOT_TESTING_SKILL_ROOT",
  str(Path.home() / ".codex/skills/setup-peugeot-3008-testing"),
))

PEUGEOT_STABLE_ROOT = Path(os.environ.get(
  "PEUGEOT_STABLE_SKILL_ROOT",
  str(Path.home() / ".codex/skills/setup-peugeot-3008"),
))


def wrappers():
  return (
    (TORQUE_ROOT, 'setup_psa_torque.sh', 'setup_psa_torque_common.sh', 'psa-torque', True),
    (PEUGEOT_ROOT, 'setup_peugeot_3008.sh', 'setup_peugeot_3008_common.sh', 'peugeot-3008', True),
    (PEUGEOT_STABLE_ROOT, 'setup_peugeot_3008.sh', 'setup_peugeot_3008_common.sh', 'peugeot-3008', False),
  )


class SourceVariantsTest(unittest.TestCase):
  def test_help_has_no_setup_side_effects(self):
    for root, wrapper, *_ in wrappers():
      for args in (['--help'], ['help'], ['-h'], ['sunny', 'nav-alpha', '--help']):
        with self.subTest(skill=root.name, args=args), tempfile.TemporaryDirectory() as tmp:
          script = Path(tmp) / wrapper
          shutil.copy2(root / 'scripts' / wrapper, script)
          # No common script: help must return before touching setup code.
          result = subprocess.run(['bash', str(script), *args], capture_output=True, text=True)
          self.assertEqual(result.returncode, 0, result.stderr)
          self.assertIn('sunny nav-alpha', result.stdout)
          self.assertIn('feature/nav-alpha', result.stdout)
          self.assertIn('cristianku/openpilot', result.stdout)

  def capture(self, root, wrapper_name, common_name, args, overrides=None):
    with tempfile.TemporaryDirectory() as tmp:
      scripts = Path(tmp)
      shutil.copy2(root / "scripts" / wrapper_name, scripts / wrapper_name)
      (scripts / common_name).write_text("""#!/usr/bin/env bash
python3 - <<'PY'
import json, os
keys = ('BRANCH', 'OPENPILOT_SOURCE_REPO', 'OPENPILOT_SOURCE_BRANCH',
        'OPENPILOT_SOURCE_COMMIT', 'OPENDBC_SOURCE_BRANCH',
        'USE_CUSTOM_NEURAL_NETWORK_DATA')
print(json.dumps({key: os.environ.get(key, '') for key in keys}))
PY
""")
      env = {key: value for key, value in os.environ.items()
             if not key.startswith(('OPENPILOT_', 'OPENDBC_', 'NEURAL_NETWORK_DATA_'))}
      env.update(overrides or {})
      result = subprocess.run(
        ["bash", str(scripts / wrapper_name), *args],
        env=env, capture_output=True, text=True, check=True,
      )
      return json.loads(result.stdout)

  def test_source_and_target_variants(self):
    for root, wrapper, common, prefix, testing in wrappers():
      for args, repo, source_branch, sunny in (
        ([], 'commaai/openpilot', 'master', False),
        (['comma'], 'commaai/openpilot', 'master', False),
        (['sunny'], 'sunnypilot/sunnypilot', 'master', True),
        (['sunny', 'master'], 'sunnypilot/sunnypilot', 'master', True),
        (['sunny', 'nav-alpha'], 'cristianku/sunnypilot', 'feature/nav-alpha', True),
        (['sunny', 'feature/nav-alpha'], 'cristianku/sunnypilot', 'feature/nav-alpha', True),
      ):
        with self.subTest(skill=root.name, args=args):
          actual = self.capture(root, wrapper, common, args)
          base = prefix + ('-sunny' if sunny else '')
          self.assertEqual(actual['BRANCH'], base + ('-testing' if testing else ''))
          self.assertEqual(actual['OPENDBC_SOURCE_BRANCH'], base + ('' if testing else '-testing'))
          self.assertEqual(actual['OPENPILOT_SOURCE_REPO'], f'https://github.com/{repo}.git')
          self.assertEqual(actual['OPENPILOT_SOURCE_BRANCH'], source_branch)
          self.assertEqual(actual['USE_CUSTOM_NEURAL_NETWORK_DATA'], str(sunny).lower())

  def test_invalid_source_stops_before_setup(self):
    for root, wrapper, *_ in wrappers():
      for args in (['sunny-nav'], ['comma', 'nav-alpha'], ['sunny', 'unknown-source']):
        with self.subTest(skill=root.name, args=args), tempfile.TemporaryDirectory() as tmp:
          script = Path(tmp) / wrapper
          shutil.copy2(root / 'scripts' / wrapper, script)
          result = subprocess.run(['bash', str(script), *args], capture_output=True, text=True)
          self.assertEqual(result.returncode, 2, result.stderr)
          self.assertNotIn('missing', result.stderr)

  def test_torque_aliases_and_pin(self):
    for variant in ('openpilot', 'sunnypilot'):
      with self.subTest(variant=variant):
        actual = self.capture(
          TORQUE_ROOT, 'setup_psa_torque.sh', 'setup_psa_torque_common.sh',
          [variant, 'master=1234567'],
        )
        self.assertEqual(actual['OPENPILOT_SOURCE_COMMIT'], '1234567')
        expected = 'master'
        self.assertEqual(actual['OPENPILOT_SOURCE_BRANCH'], expected)

  def test_explicit_source_overrides(self):
    for root, wrapper, common, *_ in wrappers():
      with self.subTest(skill=root.name):
        actual = self.capture(root, wrapper, common, ['sunny', 'nav-alpha'], {
          'OPENPILOT_SOURCE_REPO': '/tmp/explicit-fixture',
          'OPENPILOT_SOURCE_BRANCH': 'explicit-source',
        })
        self.assertEqual(actual['OPENPILOT_SOURCE_REPO'], '/tmp/explicit-fixture')
        self.assertEqual(actual['OPENPILOT_SOURCE_BRANCH'], 'explicit-source')


if __name__ == '__main__':
  unittest.main()
# [nav source] - END
