#!/usr/bin/env python3
# [nnlc download] - START
"""Download the verified Peugeot NNLC export; mutate only the local model."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import shlex
import stat
import subprocess
import sys
import tempfile


HOST = 'openpilot-nnlc'
REMOTE_FILE = '/root/openpilot-nnlc-tools/output/2026-06-29_15-07-19/train/training_results/lateral_data_pruned/lateral_data_pruned.json'
DESTINATION = Path('/Users/cristianku/GitHub/COMMA.AI/CRISTIANKU/neural-network-data/neural_network_lateral_control/PSA_PEUGEOT_3008.json')
REMOTE_READER = '''import hashlib, json, socket, sys
from pathlib import Path
path = Path(sys.argv[1])
raw = path.read_bytes()
header = {'source': sys.argv[1], 'sha256': hashlib.sha256(raw).hexdigest(),
          'size': len(raw), 'hostname': socket.gethostname()}
sys.stdout.buffer.write(json.dumps(header).encode() + b'\\n' + raw)
'''


def reject_constant(value):
  raise ValueError(f'JSON non finito: {value}')


def finite_number(value):
  return type(value) in (int, float) and math.isfinite(value)


def vector(values, size, name):
  if not isinstance(values, list) or len(values) != size:
    raise ValueError(f'Dimensione non valida: {name}')
  result = []
  column = isinstance(values[0], list)
  for value in values:
    if isinstance(value, list) != column:
      raise ValueError(f'Forma non uniforme: {name}')
    if column:
      if len(value) != 1:
        raise ValueError(f'Dimensione non valida: {name}')
      value = value[0]
    if not finite_number(value):
      raise ValueError(f'Valore numerico non valido: {name}')
    result.append(value)
  return result


def validate_model(raw):
  model = json.loads(raw, parse_constant=reject_constant)
  if not isinstance(model, dict) or type(model.get('input_size')) is not int or model['input_size'] <= 0:
    raise ValueError('input_size NNLC non valido')
  if type(model.get('output_size')) is not int or model['output_size'] != 1:
    raise ValueError('output_size NNLC deve essere 1')
  size = model['input_size']
  vector(model.get('input_mean'), size, 'input_mean')
  if any(value <= 0 for value in vector(model.get('input_std'), size, 'input_std')):
    raise ValueError('input_std deve contenere valori positivi')
  if 'input_vars' in model and (not isinstance(model['input_vars'], list) or len(model['input_vars']) != size):
    raise ValueError('input_vars non corrisponde a input_size')
  layers = model.get('layers')
  if not isinstance(layers, list) or not layers:
    raise ValueError('layers NNLC mancanti')
  for layer in layers:
    if not isinstance(layer, dict) or layer.get('activation') not in ('σ', 'sigmoid', 'identity'):
      raise ValueError('Attivazione NNLC non supportata')
    weight_keys = [key for key in layer if key.endswith('_W')]
    bias_keys = [key for key in layer if key.endswith('_b')]
    if len(weight_keys) != 1 or len(bias_keys) != 1:
      raise ValueError('Pesi/bias NNLC ambigui o mancanti')
    weights = layer[weight_keys[0]]
    if not isinstance(weights, list) or not weights:
      raise ValueError('Matrice NNLC vuota')
    for row in weights:
      if not isinstance(row, list) or len(row) != size or not all(finite_number(value) for value in row):
        raise ValueError('Dimensioni o valori dei pesi NNLC non validi')
    size = len(weights)
    vector(layer[bias_keys[0]], size, bias_keys[0])
  if size != model['output_size']:
    raise ValueError('Ultimo layer incompatibile con output_size')
  return model


def download(remote_file):
  if not remote_file.startswith('/'):
    raise ValueError('Il percorso remoto deve essere assoluto')
  command = ['ssh', '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes',
             '-o', 'ConnectTimeout=8', '-o', 'ConnectionAttempts=1', HOST,
             'python3 - ' + shlex.quote(remote_file)]
  result = subprocess.run(command, input=REMOTE_READER.encode(), capture_output=True, timeout=30)
  if result.returncode:
    detail = result.stderr.decode(errors='replace').strip()
    raise ValueError(f'SSH {HOST} non riuscito: {detail}')
  header_raw, separator, raw = result.stdout.partition(b'\n')
  if not separator:
    raise ValueError('Risposta SSH incompleta')
  header = json.loads(header_raw)
  if not isinstance(header, dict) or header.get('source') != remote_file or header.get('size') != len(raw):
    raise ValueError('Sorgente o dimensione del download non corrispondente')
  digest = hashlib.sha256(raw).hexdigest()
  if header.get('sha256') != digest:
    raise ValueError('SHA-256 del download non corrispondente')
  return raw, header


def install(raw, destination):
  if destination.is_symlink() or (destination.exists() and not destination.is_file()):
    raise ValueError('La destinazione deve essere un file ordinario')
  previous = destination.read_bytes() if destination.exists() else None
  if previous == raw:
    return 'unchanged', None
  mode = stat.S_IMODE(destination.stat().st_mode) if previous is not None else 0o644
  destination.parent.mkdir(parents=True, exist_ok=True)
  fd, temporary_name = tempfile.mkstemp(prefix='.' + destination.name + '.', dir=destination.parent)
  temporary = Path(temporary_name)
  backup = None
  try:
    with os.fdopen(fd, 'wb') as stream:
      stream.write(raw)
      stream.flush()
      os.fsync(stream.fileno())
    temporary.chmod(mode)
    if previous is not None:
      backup_dir = destination.parent / '.nnlc-backups'
      backup_dir.mkdir(exist_ok=True)
      timestamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
      backup_fd, backup_name = tempfile.mkstemp(prefix=f'{destination.name}.{timestamp}.', suffix='.bak', dir=backup_dir)
      backup = Path(backup_name)
      with os.fdopen(backup_fd, 'wb') as stream:
        stream.write(previous)
        stream.flush()
        os.fsync(stream.fileno())
    # Refuse to overwrite work edited while the local snapshot was being prepared.
    current = destination.read_bytes() if destination.exists() else None
    if current != previous:
      raise ValueError('Destinazione modificata durante il download: sostituzione annullata')
    os.replace(temporary, destination)
  finally:
    temporary.unlink(missing_ok=True)
  return ('updated' if previous is not None else 'downloaded'), str(backup) if backup else None


def main():
  parser = argparse.ArgumentParser(description='Scarica il modello NNLC Peugeot 3008 da openpilot-nnlc.')
  parser.add_argument('--remote-file', default=REMOTE_FILE, help='Esportazione Peugeot alternativa esplicitamente indicata.')
  parser.add_argument('--destination', type=Path, default=DESTINATION, help='File locale; default PSA_PEUGEOT_3008.json nel repository neural-network-data.')
  args = parser.parse_args()
  try:
    raw, header = download(args.remote_file)
    model = validate_model(raw)
    status, backup = install(raw, args.destination)
    print(json.dumps({'status': status, 'host': HOST, 'hostname': header.get('hostname'),
                      'source': args.remote_file, 'destination': str(args.destination),
                      'sha256': header['sha256'], 'bytes': len(raw), 'backup': backup,
                      'input_size': model['input_size'], 'output_size': model['output_size'],
                      'layers': len(model['layers']), 'training_time': model.get('current_date_and_time')}, ensure_ascii=False))
    return 0
  except (OSError, ValueError, subprocess.TimeoutExpired) as error:
    print(f'ERROR: {error}', file=sys.stderr)
    return 1


if __name__ == '__main__':
  sys.exit(main())
# [nnlc download] - END
