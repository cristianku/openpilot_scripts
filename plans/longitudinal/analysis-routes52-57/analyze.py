from pathlib import Path
import json,numpy as np
P=Path('/tmp/psa-downhill-52-57');N=json.loads((P/'signals.json').read_text())
def spans(mask):
 d=np.diff(np.r_[False,mask,False].astype(int));return list(zip(np.where(d==1)[0],np.where(d==-1)[0]))
for file in sorted(P.glob('000*.npz')):
 raw=np.load(file);Z={k:raw[k] for k in raw.files};meta=json.loads(file.with_suffix('.json').read_text());t0=min(r['first'] for r in meta['files'])
 def val(k,n,t):
  a=Z[k];idx=np.clip(np.searchsorted(a[:,0],t,side='right')-1,0,len(a)-1);return a[idx,N[k].index(n)+1]
 def cv(k,n):return Z[k][:,N[k].index(n)+1]
 def snap(t):
  return {n:round(float(val(k,s,t)),3) for n,k,s in [('v','carState','vEgoRaw'),('a','carState','aEgo'),('set','carState','setSpeed'),('gas','carState','gas'),('BSI','carState','cruiseEnabled'),('fault','carState','accFaulted'),('enabled','carControl','enabled'),('long','carControl','longActive'),('target','carControl','accel'),('pitch','carControl','pitch'),('pressure','can_1_0x32d','EFFORT_FREIN')] if k in Z}
 print('\nROUTE',file.stem,'duration',round(max(r['last'] for r in meta['files'])-t0,2))
 print('PARAMS',meta['carParams']);print('INIT',meta['initData']);print('LOGS',[v for v in meta.get('logs',[]) if isinstance(v[1],str)])
 print('PANDA', {k:{n:np.unique(cv(k,n)).tolist()[:12] for n in N[k]} for k in Z if k.startswith('panda')})
 print('ALERTS',meta.get('selfdriveState',[])[:8], 'total',len(meta.get('selfdriveState',[])))
 if 'sendcan_1_0x2b6' not in Z:continue
 k='sendcan_1_0x2b6';a=Z[k];ts=a[:,0];status=cv(k,'ACC_STATUS');req=cv(k,'MDD_DECEL_CONTROL_REQ');active=status==4
 print('TX COUNTS',len(ts),'status',dict(zip(*[v.tolist() for v in np.unique(status,return_counts=True)])),'brakeframes',sum(req))
 print('ACC faulty spans',[(round(Z['carState'][l,0]-t0,2),round(Z['carState'][r-1,0]-Z['carState'][l,0],2)) for l,r in spans(cv('carState','accFaulted')>0)])
 pulses=[]
 for l,r in spans((req>0)&active):
  start=ts[l];end=ts[min(r,len(ts)-1)];dd=cv(k,'MDD_DESIRED_DECELERATION')[l:r]
  pulses.append({'t':round(start-t0,3),'duration':round(end-start,3),'decel_min':round(float(dd.min()),3),'decel_max':round(float(dd.max()),3),'before':snap(start-0.02),'after':snap(end+0.01)})
 print('BRAKE EPISODES',len(pulses));print(json.dumps(pulses[:16]))
 if pulses:
  times=np.asarray([x['t'] for x in pulses]);best=max(times,key=lambda t:np.sum((times>=t)&(times<t+40)))
  print('DENSE BRAKE WINDOW',best);print(json.dumps([x for x in pulses if best<=x['t']<best+40]))
 cs=Z['carState'];cst=cs[:,0];eng=cv('carState','cruiseEnabled')>0;gas=cv('carState','gas')>0
 for l in np.where(np.diff(eng.astype(int),prepend=0)==1)[0]:
  t=cst[l]
  if not gas[l]:continue
  print('GAS ENGAGEMENT',round(t-t0,3),snap(t))
  for dt in [-0.1,0,0.05,0.1,0.2,0.4,0.8,1.2,2]:
   q=t+dt;print('  ',dt,snap(q),'status',val(k,'ACC_STATUS',q),'brake_req',val(k,'MDD_DECEL_CONTROL_REQ',q))
 gas_on_tx=val('carState','gas',ts)>0
 print('GAS + BRAKE REQ',np.sum(gas_on_tx&(req>0)))
 for l,r in spans(gas_on_tx&(req>0))[:5]:print('GAS BRAKE',ts[l]-t0,ts[r-1]-ts[l],snap(ts[l]))
 summary={'route':file.stem,'t0':t0,'pulses':pulses}
 (P/(file.stem+'-summary.json')).write_text(json.dumps(summary,indent=2))
