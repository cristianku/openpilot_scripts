import json,numpy as np
from pathlib import Path
P=Path('/tmp/psa-downhill-52-57');N=json.loads((P/'signals.json').read_text());route='00000056--be50d375dd';raw=np.load(P/(route+'.npz'));Z={k:raw[k] for k in raw.files};M=json.loads((P/(route+'.json')).read_text());t0=M['files'][0]['first']
def col(k,n):return Z[k][:,N[k].index(n)+1]
def at(k,n,t):
 a=Z[k];i=np.clip(np.searchsorted(a[:,0],np.asarray(t)+t0,side='right')-1,0,len(a)-1);return col(k,n)[i]
def stats(k,n,start,end):
 m=(Z[k][:,0]>=t0+start)&(Z[k][:,0]<t0+end);v=col(k,n)[m];return [round(float(x),5) for x in [v.min(),np.median(v),v.max()]]
summary={}
for k,ns in [('carState',['vEgoRaw','aEgo','setSpeed','gas','brake','canValid','cruiseEnabled','accFaulted']),('carControl',['enabled','longActive','accel','pitch']),('panda0',['controlsAllowed','txBlocked','rxInvalid']),('sendcan_1_0x2b6',['ACC_STATUS','MDD_DESIRED_DECELERATION','MDD_DECEL_CONTROL_REQ','GMP_WHEEL_TORQUE'])]:
 for n in ns:summary[k+'/'+n]=stats(k,n,557.5,572.4)
p=json.loads((P/(route+'-summary.json')).read_text())['pulses'];p=[v for v in p if 557.5<=v['t']<572.4];summary['pulses']=p;summary['pulse_count']=len(p)
for k in ('sendcan_1_0x2b6','can_129_0x2b6'):
 a=Z[k];m=(a[:,0]>=t0+557.5)&(a[:,0]<t0+572.4);summary[k+'/frames']=int(sum(m));summary[k+'/max_gap']=float(np.diff(a[m,0]).max())
print(json.dumps({k:v for k,v in summary.items() if k!='pulses'},indent=2));(P/'downhill_metrics.json').write_text(json.dumps(summary,indent=2))
for t in [702,703.5,704,704.3,704.6,704.8,705,706,710]:
 print('FAULT',t,{n:round(float(at(k,s,t)),3) for n,k,s in [('speed','carState','vEgoRaw'),('gas','carState','gas'),('brake','carState','brake'),('fault','carState','accFaulted'),('BSI','carState','cruiseEnabled'),('enabled','carControl','enabled'),('req','sendcan_1_0x2b6','MDD_DECEL_CONTROL_REQ'),('status','sendcan_1_0x2b6','ACC_STATUS'),('BRAKEFAULT','can_1_0x32d','DEFAUT_ACC_FREIN'),('MOTEURFAULT','can_0_0x348','P025_Com_stESPErr')]})
print('PLANSP sample',min(M['longitudinalPlanSP'],key=lambda v:abs(v[0]-t0-565)))
print('ERRORS',len(M.get('decode_errors',[])))
