# [nnlc download] - START
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).parents[1] / 'scripts/fetch_model.py'
REMOTE = '/root/openpilot-nnlc-tools/output/2026-06-29_15-07-19/train/training_results/lateral_data_pruned/lateral_data_pruned.json'


def model_bytes():
  return json.dumps({
    'input_size': 2, 'output_size': 1, 'input_mean': [[0], [1]], 'input_std': [[1], [2]],
    'input_vars': ['speed', 'lataccel'],
    'layers': [{'dense_1_W': [[1, 2], [3, 4]], 'dense_1_b': [[0], [0]], 'activation': 'σ'},
               {'dense_2_W': [[1, 2]], 'dense_2_b': [[0]], 'activation': 'identity'}],
  }).encode()


class TestFetchModel(unittest.TestCase):
  def setUp(self):
    self.tmp = tempfile.TemporaryDirectory()
    self.addCleanup(self.tmp.cleanup)
    self.root = Path(self.tmp.name)
    self.destination = self.root / 'models/PSA_PEUGEOT_3008.json'
    self.remote_data = self.root / 'remote.bin'
    self.remote_data.write_bytes(model_bytes())
    fake_ssh = self.root / 'ssh'
    fake_ssh.write_text(f'''#!{sys.executable}
import hashlib, json, os, pathlib, sys
sys.stdin.buffer.read()
if os.environ.get('NNLC_TEST_FAIL'):
  print('offline', file=sys.stderr)
  sys.exit(255)
raw = pathlib.Path(os.environ['NNLC_TEST_FILE']).read_bytes()
header = {{'source': {REMOTE!r}, 'sha256': hashlib.sha256(raw).hexdigest(),
          'size': len(raw), 'hostname': 'openpilot-nnlc-new'}}
if os.environ.get('NNLC_TEST_BAD_HASH'):
  header['sha256'] = '0' * 64
sys.stdout.buffer.write(json.dumps(header).encode() + b'\\n' + raw)
''')
    fake_ssh.chmod(0o755)
    self.env = dict(os.environ, PATH=str(self.root) + os.pathsep + os.environ['PATH'], NNLC_TEST_FILE=str(self.remote_data))

  def run_download(self):
    return subprocess.run([sys.executable, str(SCRIPT), '--destination', str(self.destination)],
                          env=self.env, capture_output=True, text=True)

  def preserve_original(self):
    self.destination.parent.mkdir(parents=True)
    self.destination.write_bytes(b'previous model, preserve exactly')
    return self.destination.read_bytes()

  def test_downloads_valid_model_with_correct_filename(self):
    result = self.run_download()
    self.assertEqual(result.returncode, 0, result.stderr)
    self.assertEqual(self.destination.read_bytes(), self.remote_data.read_bytes())
    report = json.loads(result.stdout)
    self.assertEqual(report['sha256'], hashlib.sha256(self.remote_data.read_bytes()).hexdigest())
    self.assertEqual(report['destination'], str(self.destination))
    self.assertEqual(report['status'], 'downloaded')

  def test_replaces_only_after_preserving_backup(self):
    previous = self.preserve_original()
    result = self.run_download()
    self.assertEqual(result.returncode, 0, result.stderr)
    report = json.loads(result.stdout)
    self.assertEqual(Path(report['backup']).read_bytes(), previous)
    self.assertEqual(self.destination.read_bytes(), model_bytes())
    self.assertEqual(report['status'], 'updated')

  def test_identical_download_preserves_mtime_and_creates_no_backup(self):
    self.destination.parent.mkdir(parents=True)
    self.destination.write_bytes(model_bytes())
    before = self.destination.stat().st_mtime_ns
    result = self.run_download()
    self.assertEqual(result.returncode, 0, result.stderr)
    report = json.loads(result.stdout)
    self.assertEqual(report['status'], 'unchanged')
    self.assertIsNone(report['backup'])
    self.assertEqual(self.destination.stat().st_mtime_ns, before)
    self.assertEqual(list(self.destination.parent.rglob('*.bak')), [])

  def test_checksum_error_preserves_original(self):
    previous = self.preserve_original()
    self.env['NNLC_TEST_BAD_HASH'] = '1'
    result = self.run_download()
    self.assertNotEqual(result.returncode, 0)
    self.assertIn('SHA-256', result.stderr)
    self.assertEqual(self.destination.read_bytes(), previous)
    self.assertEqual(list(self.destination.parent.rglob('*.bak')), [])

  def test_invalid_json_preserves_original(self):
    previous = self.preserve_original()
    self.remote_data.write_bytes(b'{unfinished')
    result = self.run_download()
    self.assertNotEqual(result.returncode, 0)
    self.assertEqual(self.destination.read_bytes(), previous)
    self.assertEqual(list(self.destination.parent.rglob('*.bak')), [])

  def test_rejects_incompatible_or_nonfinite_models(self):
    previous = self.preserve_original()
    cases = [lambda m: m.update(output_size=2),
             lambda m: m.update(input_std=[[0], [2]]),
             lambda m: m['layers'][0].update(dense_1_W=[[1]]),
             lambda m: m['layers'][0].update(activation='arbitrary_method'),
             lambda m: m['layers'][0].update(dense_1_b=[[float('nan')], [0]])]
    for mutate in cases:
      with self.subTest(mutate=mutate):
        model = json.loads(model_bytes())
        mutate(model)
        self.remote_data.write_bytes(json.dumps(model).encode())
        result = self.run_download()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.destination.read_bytes(), previous)
        self.assertEqual(list(self.destination.parent.rglob('*.bak')), [])

  def test_unreachable_host_preserves_original(self):
    previous = self.preserve_original()
    self.env['NNLC_TEST_FAIL'] = '1'
    result = self.run_download()
    self.assertNotEqual(result.returncode, 0)
    self.assertEqual(self.destination.read_bytes(), previous)
    self.assertEqual(list(self.destination.parent.rglob('*.bak')), [])

  def test_mixed_vector_shapes_preserve_original(self):
    previous = self.preserve_original()
    for field in ('input_mean', 'input_std', 'dense_1_b'):
      with self.subTest(field=field):
        model = json.loads(model_bytes())
        target = model['layers'][0] if field == 'dense_1_b' else model
        target[field][0] = target[field][0][0]
        self.remote_data.write_bytes(json.dumps(model).encode())
        result = self.run_download()
        try:
          self.assertNotEqual(result.returncode, 0)
          self.assertEqual(self.destination.read_bytes(), previous)
          self.assertEqual(list(self.destination.parent.rglob('*.bak')), [])
        finally:
          self.destination.write_bytes(previous)

  def test_uniform_flat_vectors_are_supported(self):
    model = json.loads(model_bytes())
    for field in ('input_mean', 'input_std'):
      model[field] = [value[0] for value in model[field]]
    for layer in model['layers']:
      bias_key = next(key for key in layer if key.endswith('_b'))
      layer[bias_key] = [value[0] for value in layer[bias_key]]
    self.remote_data.write_bytes(json.dumps(model).encode())
    result = self.run_download()
    self.assertEqual(result.returncode, 0, result.stderr)
    self.assertEqual(self.destination.read_bytes(), self.remote_data.read_bytes())


if __name__ == '__main__':
  unittest.main()
# [nnlc download] - END
