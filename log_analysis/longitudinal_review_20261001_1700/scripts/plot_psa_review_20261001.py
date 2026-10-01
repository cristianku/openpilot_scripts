import csv
import gzip
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

root=Path('/Users/cristianku/GitHub/COMMA.AI/CRISTIANKU/openpilot_scripts/log_analysis/longitudinal_review_20261001_1700')
onset=1106.799763429
with gzip.open(root/'000000b8--8846cc65c2_rlog_replay.csv.gz','rt') as stream:
    rows=[r for r in csv.DictReader(stream) if onset-.5<=float(r['t'])<=onset+1.2]
t=[float(r['t'])-onset for r in rows]
fig,axes=plt.subplots(2,1,figsize=(10,6.4),sharex=True,layout='constrained')
axes[0].plot(t,[float(r['requested']) for r in rows],color='#777777',ls='--',label='Richiesta planner registrata')
axes[0].plot(t,[float(r['old']) for r in rows],color='#c62828',label='Controller installato (replay)')
axes[0].plot(t,[float(r['filtered']) for r in rows],color='#1565c0',lw=2,label='Nuovo filtro RC = 0,20 s (replay)')
axes[0].set_ylabel('Comando [m/s²]')
axes[0].set_title('Rilascio gas a 99 km/h: il filtro smussa il gradino, ma ritarda la crescita')
axes[0].legend(loc='lower left',fontsize=9)
axes[1].plot(t,[float(r['aego']) for r in rows],color='#333333',label='aEgo della vettura con vecchio codice (registrata)')
axes[1].set_ylabel('aEgo misurata [m/s²]')
axes[1].set_xlabel('Secondi dal primo comando di frenata nel replay')
axes[1].legend(fontsize=9)
for axis in axes:
    axis.grid(alpha=.2)
    axis.axvline(0,color='#777777',lw=.8)
fig.suptitle('Route b8, circa 17:51 — simulazione dei comandi, nessuna risposta fisica nuova simulata',fontsize=10)
fig.savefig(root/'brake_filter_replay.png',dpi=170)
print(root/'brake_filter_replay.png')
