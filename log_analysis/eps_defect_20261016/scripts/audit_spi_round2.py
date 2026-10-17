# /// script
# requires-python = ">=3.11"
# dependencies = ["pycapnp", "zstandard"]
# ///
# [eps spi] - START
"""Read specified rlogs: SPI counters, batch sizes and EPS diagnostic traffic."""
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import psa_eps_timeline as pet

schema = pet.load_schema()
for name in sys.argv[1:]:
  spi = []; sizes = []; states = []; diag = []
  try:
    for event in pet.read_events(schema, Path(name)):
      if event.which() == 'pandaStates':
        for st in event.pandaStates:
          spi.append(int(st.spiErrorCount))
          states.append((event.logMonoTime / 1e9, [(x.totalRxCnt, x.totalTxCnt) for x in (st.canState0, st.canState1, st.canState2)]))
      elif event.which() == 'can':
        sizes.append(len(event.can))
        for msg in event.can:
          if msg.address in (0x6B5, 0x695) and msg.src < 4 and len(diag) < 16:
            diag.append((hex(msg.address), msg.src, bytes(msg.dat).hex()))
    rates = []
    if len(states) > 1 and states[-1][0] > states[0][0]:
      duration = states[-1][0] - states[0][0]
      rates = [{'bus': i, 'rx_per_s': round((states[-1][1][i][0]-states[0][1][i][0])/duration, 1),
                'tx_per_s': round((states[-1][1][i][1]-states[0][1][i][1])/duration, 1)} for i in range(3)]
    print(json.dumps({'rlog': name, 'spi_min_max': [min(spi), max(spi)] if spi else [],
                      'mean_frames_batch': sum(sizes)/len(sizes) if sizes else None,
                      'max_frames_batch': max(sizes) if sizes else None, 'rates': rates, 'diag_examples': diag}), flush=True)
  except Exception as exc:
    print(json.dumps({'rlog': name, 'error': str(exc)}), flush=True)
# [eps spi] - END
