from pathlib import Path
import os,json,numpy as np
os.environ['MPLCONFIGDIR']='/tmp/psa-downhill-52-57/mpl'
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
P=Path('/tmp/psa-downhill-52-57');OUT=Path('/Users/cristianku/GitHub/COMMA.AI/CRISTIANKU/openpilot_scripts/plans/longitudinal/analysis-routes52-57');OUT.mkdir(parents=True,exist_ok=True)
N=json.loads((P/'signals.json').read_text());r='00000056--be50d375dd';raw=np.load(P/(r+'.npz'));Z={k:raw[k] for k in raw.files};t0=json.loads((P/(r+'.json')).read_text())['files'][0]['first']
def xy(k,n,start,end):
 a=Z[k];t=a[:,0]-t0;m=(t>=start)&(t<end);return t[m]-start,a[m,1+N[k].index(n)]
def line(ax,k,n,start,end,scale=1,**kw):
 x,y=xy(k,n,start,end);ax.plot(x,y*scale,**kw)
plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False})
a,b=557.5,572.4
fig,axs=plt.subplots(4,1,figsize=(12,8),sharex=True,layout='constrained');fig.suptitle('Discesa: 14 attivazioni del freno in 14,9 secondi\nRoute 56 · da 557,5 s · messaggi inviati e risposta registrata',fontsize=14)
line(axs[0],'carState','vEgoRaw',a,b,3.6,label='Velocità CAN',color='#0077b6');line(axs[0],'carState','setSpeed',a,b,3.6,label='Setpoint CAN',color='black',linestyle='--');axs[0].set_ylabel('km/h');axs[0].legend(loc='lower right',ncol=2)
line(axs[1],'carControl','accel',a,b,label='Richiesta al controller',color='#0077b6');x,y=xy('sendcan_1_0x2b6','MDD_DESIRED_DECELERATION',a,b);y[y>1]=np.nan;axs[1].plot(x,y,label='Decelerazione CAN con freno attivo',color='#d1495b');axs[1].axhline(-.5,color='black',ls=':',label='Soglia −0,50');axs[1].set_ylabel('m/s²');axs[1].legend(loc='lower right',ncol=3,fontsize=8)
line(axs[2],'sendcan_1_0x2b6','MDD_DECEL_CONTROL_REQ',a,b,label='Richiesta freno 0x2B6',color='#d1495b',drawstyle='steps-post');line(axs[2],'can_1_0x32d','EFFORT_FREIN',a,b,label='Flag EFFORT_FREIN 0x32D',color='#35a16b',alpha=.7,drawstyle='steps-post');axs[2].set_yticks([0,1],['OFF','ON']);axs[2].legend(loc='upper right',ncol=2,fontsize=8)
line(axs[3],'carState','aEgo',a,b,label='Accelerazione del veicolo',color='#6a4c93');axs[3].axhline(0,color='black',lw=.6);axs[3].set_ylabel('m/s²');axs[3].set_xlabel('Secondi dall’inizio della finestra');axs[3].legend(loc='upper right')
for ax in axs:ax.grid(alpha=.2)
fig.savefig(OUT/'downhill-brake-cycling.png',dpi=160);plt.close(fig)
a,b=348.95,349.75
fig,axs=plt.subplots(3,1,figsize=(10,6),sharex=True,layout='constrained');fig.suptitle('ACC inserito mentre il gas è già premuto\nRoute 56 · intorno a 349,13 s',fontsize=14)
line(axs[0],'can_0_0x228','P334_ACCPed_Position',a,b,label='Pedale fisico 0x228',color='#0077b6');axs[0].set_ylabel('Pedale (%)');axs[0].legend()
for k,n,label,color in [('carState','cruiseEnabled','Attivazione ACC BSI','#35a16b'),('carControl','enabled','CC.enabled','#0077b6'),('carControl','longActive','CC.longActive','#d1495b')]:line(axs[1],k,n,a,b,label=label,color=color,drawstyle='steps-post')
axs[1].set_yticks([0,1]);axs[1].legend(ncol=3,fontsize=9)
line(axs[2],'sendcan_1_0x2b6','ACC_STATUS',a,b,color='#d1495b',drawstyle='steps-post');axs[2].set_yticks([3,4,5],['3 Waiting','4 Active','5 On hold']);axs[2].set_ylim(2.8,5.2);axs[2].set_xlabel('Secondi dall’inizio della finestra')
for ax in axs:ax.grid(alpha=.2)
fig.savefig(OUT/'engagement-with-gas.png',dpi=160);plt.close(fig)
print(OUT)
