# /// script
# requires-python = ">=3.11"
# dependencies = ["pycapnp", "zstandard"]
# ///
"""Per ogni route: data, commit, dashcam, minuti, Defect EPS, regolarita' LANE_KEEP_ASSIST sul bus, carico CPU."""
import sys
import datetime
from pathlib import Path
from collections import Counter
sys.path.insert(0, "/Users/cristianku/GitHub/COMMA.AI/CRISTIANKU/openpilot_scripts/log_analysis")
import psa_eps_timeline as pet
sigs = pet.dbc_signals(pet.DBC, {0x495})
schema = pet.load_schema()

print(f"{'route':22s} {'data':16s} {'commit':9s} {'dash':4s} {'min':>5s} {'defect':>6s} {'/ora':>5s} "
      f"{'LKA@50ms':>8s} {'LKA30/70':>8s} {'cpu%':>5s} {'cpuMax':>6s} {'tempC':>5s}")
for rdir in sorted(Path(sys.argv[1]).iterdir()):
    segs = sorted((p for p in rdir.iterdir() if (p / "rlog.zst").exists()),
                  key=lambda p: int(p.name.rsplit("--", 1)[1]))
    if not segs:
        continue
    date = None
    commit = ""
    dash = set()
    prev = 0
    n_def = 0
    echo = []
    cpu = []
    temps = []
    t_first = None
    t_last = None
    for seg in segs:
        try:
            evs = pet.read_events(schema, seg / "rlog.zst")
            for ev in evs:
                t = ev.logMonoTime / 1e9
                if t_first is None:
                    t_first = t
                t_last = t
                w = ev.which()
                if w == "initData" and not commit:
                    commit = ev.initData.gitCommit[:8]
                elif w == "gpsLocationExternal" and date is None:
                    ms = ev.gpsLocationExternal.unixTimestampMillis
                    if ms > 1.6e12:
                        date = datetime.datetime.fromtimestamp(ms / 1000).strftime("%Y-%m-%d %H:%M")
                elif w == "carParams":
                    dash.add(ev.carParams.dashcamOnly)
                elif w == "deviceState":
                    c = list(ev.deviceState.cpuUsagePercent)
                    if c:
                        cpu.append(sum(c) / len(c))
                    tc = list(ev.deviceState.cpuTempC)
                    if tc:
                        temps.append(max(tc))
                elif w == "can":
                    for m in ev.can:
                        if m.address == 0x3F2 and m.src == 128:
                            echo.append(t)
                        elif m.address == 0x495 and m.src == 0:
                            e = int(pet.extract(bytes(m.dat), sigs[0x495]["EPS_STATE_LKA"]))
                            if e == 4 and prev != 4:
                                n_def += 1
                            prev = e
        except Exception as ex:
            print(f"   ERR {seg.name}: {ex}")
    mins = (t_last - t_first) / 60
    iv = [round((b - a) * 100) for a, b in zip(echo, echo[1:])]  # in centesimi di secondo
    c = Counter(iv)
    p50 = 100 * c[5] / len(iv) if iv else float("nan")
    p3070 = 100 * (c[3] + c[7]) / len(iv) if iv else float("nan")
    d = "Y" if True in dash else "N"
    cpu_avg = sum(cpu) / len(cpu) if cpu else float("nan")
    cpu_max = max(cpu) if cpu else float("nan")
    tmax = max(temps) if temps else float("nan")
    print(f"{rdir.name:22s} {date or '?':16s} {commit:9s} {d:4s} {mins:5.1f} {n_def:6d} {n_def / (mins / 60):5.0f} "
          f"{p50:7.0f}% {p3070:7.1f}% {cpu_avg:5.0f} {cpu_max:6.0f} {tmax:5.0f}")
