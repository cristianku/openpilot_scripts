# /// script
# requires-python = ">=3.11"
# dependencies = ["pycapnp", "zstandard"]
# ///
"""PSA EPS activation ladder: timeline + dropout stats, straight from rlog.

Why this exists: the interesting signals for the PSA EPS handshake are RAW CAN,
not cereal fields, so the CSV export (`OP-comma-logs-to-csv`) can't show them.
This reads rlog.zst directly and decodes:

  sendcan bus 0  0x3F2 LANE_KEEP_ASSIST : STATUS (our request), TORQUE,
                                          TORQUE_FACTOR, LXA_ACTIVATION, DRIVE
  can     bus 0  0x495 IS_DAT_DIRA      : EPS_STATE_LKA (what the EPS answers),
                                          EPS_TORQUE, STEERWHL_HOLD_BY_DRV

  EPS_STATE_LKA : 0 Unauthorised, 1 Authorised, 2 Available, 3 Active, 4 Defect
  LKA STATUS    : 0 UNAVAILABLE, 1 UNSELECTED, 2 READY, 3 AUTHORIZED, 4 ACTIVE

In cabana a `src` of 128+N means "sent by openpilot on bus N", which is why our
own LANE_KEEP_ASSIST shows up as `128:3F2` there but as src 0 of `sendcan` here.

Usage:
  uv run psa_eps_timeline.py <route> [--timeline] [--gaps] [--all]

  <route>      route id (0000002f--78d6cb01a1) under COMMA_LOGS_DIR
  --timeline   one line per change of (latActive, request, EPS state, pressed)
  --gaps       duty cycle + every window with latActive=1 and EPS not Active
               (default when neither flag is given)

Env: COMMA_LOGS_DIR, CEREAL_DIR (autodetected), OPENDBC_DIR (autodetected).
"""

import argparse
import os
import re
import sys
import tempfile
from pathlib import Path

import capnp
import zstandard

LOGS_DIR = Path(os.environ.get(
    "COMMA_LOGS_DIR",
    "/Users/cristianku/GitHub/COMMA.AI/CRISTIANKU/openpilot_scripts/comma_logs"))

OPENDBC_DIR = Path(os.environ.get(
    "OPENDBC_DIR", "/Users/cristianku/GitHub/COMMA.AI/CRISTIANKU/opendbc"))

# Checkouts to look in for cereal/, newest layout first. commaai master moved
# selfdrive/cereal under openpilot/; sunnypilot did not - so try both.
CEREAL_CANDIDATES = [
    "/Users/cristianku/GitHub/COMMA.AI/CRISTIANKU/new_openpilot_psa_torque_sunny_testing/cereal",
    "/Users/cristianku/GitHub/COMMA.AI/CRISTIANKU/new_openpilot_psa_torque_sunny/cereal",
    "/Users/cristianku/GitHub/COMMA.AI/SUNNYPILOT/openpilot_sunny/openpilot/cereal",
    "/Users/cristianku/GitHub/COMMA.AI/SUNNYPILOT/openpilot_sunny/cereal",
]

DBC = OPENDBC_DIR / "opendbc/dbc/psa_aee2010_r3.dbc"
ADDR_LKA, ADDR_DIRA = 0x3F2, 0x495


# --------------------------------------------------------------------------
# cereal schema. car.capnp now lives in opendbc (opendbc/car/car.capnp) while
# log.capnp still does `import "car.capnp"`, so a bare capnp.load() on any
# checkout fails with 'Import failed: car.capnp'. Stage a dir of symlinks that
# puts them side by side. This is the bit that is easy to forget - don't
# re-derive it, just call staged_cereal().
# --------------------------------------------------------------------------
def staged_cereal() -> Path:
    env = os.environ.get("CEREAL_DIR")
    cands = [Path(env)] if env else [Path(c) for c in CEREAL_CANDIDATES]
    src = next((c for c in cands if (c / "log.capnp").is_file()), None)
    if src is None:
        sys.exit(f"no cereal/log.capnp found in:\n  " + "\n  ".join(map(str, cands)))

    car = src / "car.capnp"
    if not car.is_file():
        car = OPENDBC_DIR / "opendbc/car/car.capnp"
    if not car.is_file():
        sys.exit(f"car.capnp not found next to {src} nor in {OPENDBC_DIR}")

    stage = Path(tempfile.mkdtemp(prefix="cereal-stage-"))
    for name in ("log.capnp", "deprecated.capnp", "custom.capnp", "include"):
        p = src / name
        if p.exists():
            (stage / name).symlink_to(p)
    (stage / "car.capnp").symlink_to(car)
    return stage


def load_schema():
    d = staged_cereal()
    capnp.remove_import_hook()
    return capnp.load(str(d / "log.capnp"), imports=[str(d), str(d / "include")])


def read_events(schema, path: Path):
    raw = path.read_bytes()
    if path.suffix == ".zst":
        raw = zstandard.ZstdDecompressor().decompress(raw, max_output_size=4 * 1024**3)
    return schema.Event.read_multiple_bytes(raw)


# --------------------------------------------------------------------------
# minimal DBC reader: positions come from the dbc so they can't drift
# --------------------------------------------------------------------------
BO_RE = re.compile(r"^BO_\s+(\d+)\s+(\w+)\s*:")
SG_RE = re.compile(r"^\s*SG_\s+(\w+)\s*:\s*(\d+)\|(\d+)@(\d)([+-])\s*\(([^,]+),")


def dbc_signals(path: Path, addresses: set[int]) -> dict[int, dict]:
    """{address: {signal: (start_bit, length, is_big_endian, signed, scale)}}"""
    out, cur = {}, None
    for line in path.read_text().splitlines():
        if m := BO_RE.match(line):
            addr = int(m.group(1))
            cur = out.setdefault(addr, {}) if addr in addresses else None
        elif cur is not None and (m := SG_RE.match(line)):
            name, start, length, order, sign, scale = m.groups()
            cur[name] = (int(start), int(length), order == "0", sign == "-", float(scale))
        elif line.strip() == "":
            pass
    return out


def extract(data: bytes, spec) -> float:
    start, length, big_endian, signed, scale = spec
    total = len(data) * 8
    if big_endian:
        pos = (start // 8) * 8 + (7 - start % 8)
        shift = total - pos - length
    else:
        shift = start
    if shift < 0 or shift + length > total:
        return 0.0
    v = (int.from_bytes(data, "big" if big_endian else "little") >> shift) & ((1 << length) - 1)
    if signed and v >> (length - 1):
        v -= 1 << length
    return v * scale


# --------------------------------------------------------------------------
def collect(route: str):
    segs = sorted((p for p in LOGS_DIR.iterdir() if p.name.startswith(route + "--")),
                  key=lambda p: int(p.name.rsplit("--", 1)[1]))
    if not segs:
        sys.exit(f"no segments for route '{route}' in {LOGS_DIR}")
    sigs = dbc_signals(DBC, {ADDR_LKA, ADDR_DIRA})
    schema = load_schema()

    rows, t0 = [], None
    for seg in segs:
        f = seg / "rlog.zst"
        if not f.exists():
            continue
        for ev in read_events(schema, f):
            w = ev.which()
            t = ev.logMonoTime / 1e9
            if t0 is None:
                t0 = t
            t -= t0
            if w == "can":
                for m in ev.can:
                    if m.address == ADDR_DIRA and m.src == 0:
                        d, s = bytes(m.dat), sigs[ADDR_DIRA]
                        rows.append((t, {"eps": int(extract(d, s["EPS_STATE_LKA"])),
                                         "hold": int(extract(d, s["STEERWHL_HOLD_BY_DRV"])),
                                         "eps_nm": extract(d, s["EPS_TORQUE"])}))
            elif w == "sendcan":
                for m in ev.sendcan:
                    if m.address == ADDR_LKA and m.src == 0:
                        d, s = bytes(m.dat), sigs[ADDR_LKA]
                        rows.append((t, {"req": int(extract(d, s["STATUS"])),
                                         "trq": int(extract(d, s["TORQUE"])),
                                         "fct": int(extract(d, s["TORQUE_FACTOR"])),
                                         "lxa": int(extract(d, s["LXA_ACTIVATION"]))}))
            elif w == "carControl":
                rows.append((t, {"lat": int(ev.carControl.latActive)}))
            elif w == "carState":
                rows.append((t, {"prs": int(ev.carState.steeringPressed),
                                 "drv": ev.carState.steeringTorque,
                                 "v": ev.carState.vEgo}))
    rows.sort(key=lambda r: r[0])

    st = {"eps": 0, "hold": 0, "eps_nm": 0.0, "req": 0, "trq": 0, "fct": 0,
          "lxa": 0, "lat": 0, "prs": 0, "drv": 0.0, "v": 0.0}
    samples = []
    for t, d in rows:
        st.update(d)
        samples.append((t, dict(st)))
    return len(segs), samples


def print_timeline(samples):
    watch = ("lat", "lxa", "req", "eps", "prs")
    hdr = (f"{'t':>8}  {'lat':>3} {'lxa':>3} {'req':>3} {'eps':>3} {'prs':>3} "
           f"{'fct':>4} {'trq':>6} {'epsNm':>6} {'drv':>6} {'v':>5}")
    print(hdr)
    print("-" * len(hdr))
    prev = None
    for t, s in samples:
        key = tuple(s[k] for k in watch)
        if key == prev:
            continue
        prev = key
        print(f"{t:8.3f}  {s['lat']:3d} {s['lxa']:3d} {s['req']:3d} {s['eps']:3d} "
              f"{s['prs']:3d} {s['fct']:4d} {s['trq']:6d} {s['eps_nm']:6.1f} "
              f"{s['drv']:6.1f} {s['v']:5.1f}")


def print_gaps(samples):
    lat_time = active_time = 0.0
    for (t, s), (tn, _) in zip(samples, samples[1:]):
        if s["lat"]:
            lat_time += tn - t
            if s["eps"] == 3:
                active_time += tn - t
    if lat_time == 0:
        print("  latActive mai attivo in questa route")
        return
    print(f"  latActive totale          : {lat_time:7.1f} s")
    print(f"  di cui EPS Active (eps=3) : {active_time:7.1f} s  ({100*active_time/lat_time:.1f} %)")
    print(f"  BUCO (latActive, eps!=3)  : {lat_time-active_time:7.1f} s  "
          f"({100*(lat_time-active_time)/lat_time:.1f} %)\n")

    print("  buchi con latActive=1 (EPS non Active):")
    print(f"  {'inizio':>8} {'durata':>7} {'req@drop':>8} {'prs':>5}  causa")
    gaps, in_gap = [], None
    for i, (t, s) in enumerate(samples):
        if s["lat"] and s["eps"] != 3 and in_gap is None:
            prev_req = samples[i-1][1]["req"] if i else s["req"]
            in_gap = (t, s["req"], prev_req, i)
        elif in_gap is not None and (s["eps"] == 3 or not s["lat"]):
            t_start, req_at, prev_req, i0 = in_gap
            prs_in = any(x[1]["prs"] for x in samples[i0:i + 1])
            # request==1 means WE asked the EPS to drop (the 5 s forced rearm);
            # anything else means the EPS let go on its own (driver override).
            forced = 1 in (prev_req, req_at)
            cause = "rearm forzato (EPS_REARM_PERIOD)" if forced else "EPS ha mollato da solo"
            if not s["lat"]:
                cause += " + latActive OFF"
            gaps.append((t_start, t - t_start, req_at, prs_in, cause))
            in_gap = None
    if in_gap is not None:
        t_start, req_at, _, _ = in_gap
        gaps.append((t_start, samples[-1][0] - t_start, req_at, False, "fine route"))

    for t_start, dur, ra, prs_in, cause in gaps:
        print(f"  {t_start:8.2f} {dur:7.2f} {ra:8d} {str(prs_in):>5}  {cause}")
    d = sorted(g[1] for g in gaps)
    if d:
        print(f"\n  n={len(d)}  min={d[0]:.2f}s  mediana={d[len(d)//2]:.2f}s  "
              f"max={d[-1]:.2f}s  somma={sum(d):.1f}s")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("route")
    ap.add_argument("--timeline", action="store_true")
    ap.add_argument("--gaps", action="store_true")
    ap.add_argument("--all", action="store_true")
    a = ap.parse_args()

    n_segs, samples = collect(a.route)
    print(f"route {a.route}: {n_segs} segmenti, {samples[-1][0]:.1f} s\n")
    if a.timeline or a.all:
        print_timeline(samples)
        print()
    if a.gaps or a.all or not a.timeline:
        print_gaps(samples)


if __name__ == "__main__":
    main()
