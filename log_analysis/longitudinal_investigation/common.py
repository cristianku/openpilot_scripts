"""Shared helpers for the longitudinal investigation (read-only on logs).

- cereal schema loading (car.capnp staging trap handled like psa_eps_timeline.py)
- rlog / qlog reading
- route discovery across the local log folders

Nothing here writes next to the recordings. Outputs go to ./out/ (gitignored).
"""

import os
import sys
import tempfile
from pathlib import Path


HERE = Path(__file__).resolve().parent
OUT_DIR = HERE / "out"

OPENPILOT_DIR = Path("/Users/cristianku/GitHub/COMMA.AI/CRISTIANKU/new_openpilot_psa_torque_sunny_testing")
OPENDBC_DIR = Path("/Users/cristianku/GitHub/COMMA.AI/CRISTIANKU/opendbc")

# commaai master moved cereal/ under openpilot/, sunnypilot did not: try both.
CEREAL_CANDIDATES = [
  OPENPILOT_DIR / "openpilot" / "cereal",
  OPENPILOT_DIR / "cereal",
]

# Every local folder where Cristian keeps route--segment directories is found by
# walking these two trees (read-only).
SEARCH_ROOTS = [
  Path("/Users/cristianku/GitHub/COMMA.AI/CRISTIANKU/openpilot_scripts/comma_logs"),
  Path("/Users/cristianku/GitHub/COMMA.AI/CRISTIANKU/openpilot_scripts/log_analysis"),
]

DBC_PATH = OPENDBC_DIR / "opendbc" / "dbc" / "psa_aee2010_r3.dbc"


def staged_cereal():
  src = None
  for cand in CEREAL_CANDIDATES:
    if (cand / "log.capnp").is_file():
      src = cand
      break
  if src is None:
    sys.exit("no cereal/log.capnp found")

  car = src / "car.capnp"
  if not car.is_file():
    car = OPENDBC_DIR / "opendbc" / "car" / "car.capnp"

  stage = Path(tempfile.mkdtemp(prefix="cereal-stage-"))
  for name in ("log.capnp", "deprecated.capnp", "custom.capnp", "include"):
    p = src / name
    if p.exists():
      (stage / name).symlink_to(p)
  (stage / "car.capnp").symlink_to(car)
  return stage


_SCHEMA = None


def load_schema():
  global _SCHEMA
  if _SCHEMA is None:
    import capnp  # lazy: map/report steps do not need pycapnp
    d = staged_cereal()
    capnp.remove_import_hook()
    _SCHEMA = capnp.load(str(d / "log.capnp"), imports=[str(d), str(d / "include")])
  return _SCHEMA


def read_events(path):
  import zstandard
  schema = load_schema()
  raw = Path(path).read_bytes()
  raw = zstandard.ZstdDecompressor().decompress(raw, max_output_size=4 * 1024 ** 3)
  return schema.Event.read_multiple_bytes(raw)


_SEGMENT_CACHE = None


def all_segment_dirs():
  """{route: {seg: Path}}; first copy found wins (duplicates across folders are identical downloads)."""
  global _SEGMENT_CACHE
  if _SEGMENT_CACHE is not None:
    return _SEGMENT_CACHE
  result = {}
  for root in SEARCH_ROOTS:
    if not root.is_dir():
      continue
    for log in sorted(root.rglob("rlog.zst")):
      d = log.parent
      if HERE in d.parents:
        continue
      parts = d.name.split("--")
      if len(parts) != 3:
        continue
      if not parts[2].isdigit():
        continue
      route = parts[0] + "--" + parts[1]
      seg = int(parts[2])
      if route not in result:
        result[route] = {}
      if seg not in result[route]:
        result[route][seg] = d
  for route in result:
    result[route] = dict(sorted(result[route].items()))
  _SEGMENT_CACHE = dict(sorted(result.items()))
  return _SEGMENT_CACHE


def segment_dirs(route):
  routes = all_segment_dirs()
  if route in routes:
    return routes[route]
  return {}
