# [nnlc review] - START
"""Plot the recorded NNLC divergence; reads the downloaded analysis only."""
import csv
import gzip
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent
summary = json.loads((ROOT / "lateral_summary.json").read_text())
with gzip.open(ROOT / "lateral_timeline.csv.gz", "rt") as stream:
  rows = [{key: float(value) for key, value in row.items() if value}
          for row in csv.DictReader(stream)]
rows = [row for row in rows if 220.4 <= row["t"] - summary["t0"] <= 222.3]
times = [row["t"] - summary["t0"] for row in rows]
fig, axes = plt.subplots(3, 1, figsize=(10, 8), sharex=True)
for key, label in [("desired", "Desiderata"), ("actual", "Da angolo sterzo / modello veicolo")]:
  axes[0].plot(times, [row[key] for row in rows], label=label)
axes[0].set_ylabel("Acc. laterale (m/s²)")
axes[0].legend(loc="upper left")
axes[1].plot(times, [row["desired"] - row["actual"] for row in rows], label="Errore laterale: desiderata − misurata")
axes[1].plot(times, [row["pid_error"] for row in rows], label="Errore NNLC (coppia normalizzata)")
axes[1].set_ylabel("Errori, unità diverse")
axes[1].legend(loc="upper left")
axes[2].plot(times, [row.get("can_torque", 0) * row.get("can_factor", 0) / 100 for row in rows], label="TORQUE × TORQUE_FACTOR / 100")
axes[2].set_ylabel("Richiesta CAN (unità DBC)")
axes[2].set_xlabel("Secondi dall'inizio del log analizzato")
axes[2].legend(loc="upper left")
pressed = next((t for t, row in zip(times, rows) if row.get("pressed")), None)
for ax in axes:
  ax.axhline(0, color="gray", linewidth=0.6)
  if pressed is not None:
    ax.axvline(pressed, color="red", linestyle="--", label="Intervento volante rilevato")
  ax.grid(alpha=0.2)
fig.suptitle("PSA NNLC — route bb, openpilot 0023601\nErrore NNLC opposto all'errore laterale e successivo intervento volante")
fig.tight_layout()
fig.savefig(ROOT / "nnlc_divergence.png", dpi=160)
print(ROOT / "nnlc_divergence.png")
# [nnlc review] - END
