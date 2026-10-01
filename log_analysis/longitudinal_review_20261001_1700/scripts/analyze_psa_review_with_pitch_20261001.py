import sys,json,re,csv,gzip,math,time
from pathlib import Path
from collections import Counter
import numpy as np
sys.path.insert(0,'/Users/cristianku/GitHub/COMMA.AI/CRISTIANKU/openpilot_scripts/log_analysis')
import psa_eps_timeline as p
p.CEREAL_CANDIDATES=['/tmp/psa_device_sources_20261001/openpilot/cereal']
ROOT=Path('/Users/cristianku/GitHub/COMMA.AI/CRISTIANKU/openpilot_scripts/log_analysis/longitudinal_noise_20261001')
DBCP=Path('/Users/cristianku/GitHub/COMMA.AI/CRISTIANKU/opendbc/opendbc/dbc/psa_aee2010_r3.dbc')
schema=p.load_schema()
S={};cur=None
for line in DBCP.read_text().splitlines():
 m=re.match(r'^BO_\s+(\d+)\s+(\w+)\s*:',line)
 if m: cur=S.setdefault(int(m[1]),{})
 m=re.match(r'^\s*SG_\s+(\w+)\s*:\s*(\d+)\|(\d+)@(\d)([+-])\s*\(([^,]+),([^\)]+)\)',line)
 if m and cur is not None:
  n,st,le,order,sign,scale,offset=m.groups();cur[n]=(int(st),int(le),order=='0',sign=='-',float(scale),float(offset))
def decode(addr,data):
 out={}
 for n,(st,le,big,signed,scale,offset) in S[addr].items():
  shift=len(data)*8-((st//8)*8+7-st%8)-le if big else st
  if shift<0 or shift+le>len(data)*8:continue
  value=(int.from_bytes(data,'big' if big else 'little')>>shift)&((1<<le)-1)
  if signed and value>>(le-1):value-=1<<le
  out[n]=value*scale+offset
 return out

def process(route,kind):
 counts=Counter();can_counts=Counter();rows=[];cmds=[];pressures=[];abs_rows=[];state={};valid={}; t0=None; versions=set(); gaps=[]
 segs=sorted(ROOT.glob(route+'--*'),key=lambda p:int(p.name.rsplit('--',1)[1]))
 for seg in segs:
  f=seg/(kind+'.zst')
  if not f.exists():continue
  if kind=='rlog' and str(f.relative_to(ROOT)) not in VERIFIED:continue
  st=time.monotonic()
  for ev in p.read_events(schema,f):
   w=ev.which();counts[w]+=1;t=ev.logMonoTime/1e9
   if t0 is None:t0=t
   if w=='initData':versions.add(str(ev.initData.gitCommit))
   if w=='carState':
    cs=ev.carState
    state.update(v=cs.vEgo*3.6,vr=cs.vEgoRaw*3.6,a=cs.aEgo,gas=int(cs.gasPressed),pedal_brake=int(cs.brakePressed),cruise=int(cs.cruiseState.enabled),set_speed=cs.cruiseState.speed*3.6,standstill=int(cs.standstill),esp=int(cs.espActive),canvalid=int(cs.canValid),state_t=t)
   elif w=='carOutput':
    o=ev.carOutput.actuatorsOutput
    state.update(applied=o.accel,output_t=t)
   elif w=='longitudinalPlan':
    lp=ev.longitudinalPlan
    state.update(target=lp.aTarget,source=str(lp.longitudinalPlanSource),haslead=int(lp.hasLead),shouldstop=int(lp.shouldStop),plan_t=t)
   elif w=='longitudinalPlanSP':
    sp=ev.longitudinalPlanSP
    state.update(dec=str(sp.dec.state),source_sp=str(sp.longitudinalPlanSource),vtarget_sp=sp.vTarget*3.6,scc_vision_active=int(sp.smartCruiseControl.vision.active),scc_map_active=int(sp.smartCruiseControl.map.active),sla_active=int(sp.speedLimit.assist.active))
   elif w=='radarState':
    rs=ev.radarState
    try:state.update(lead=int(rs.leadOne.present),drel=rs.leadOne.dRel,vrel=rs.leadOne.vRel,radar_t=t)
    except Exception:pass
   elif w in ('modelV2','drivingModelData'):
    md=getattr(ev,w)
    try:state.update(model_accel=md.action.desiredAcceleration,model_shouldstop=int(md.action.shouldStop),model_t=t)
    except Exception:pass
   elif w=='carControl':
    cc=ev.carControl
    state.update(cc_t=t,requested=cc.actuators.accel,long=int(cc.longActive),enabled=int(cc.enabled),longstate=str(cc.actuators.longControlState),pitch=cc.orientationNED[1] if len(cc.orientationNED)==3 else 0.0)
    rows.append(dict(t=t,**state))
   elif w in ('can','sendcan'):
    for frame in getattr(ev,w):
     addr=frame.address;bus=frame.src
     if addr not in (694,717,813,1293,973):continue
     can_counts[(w,bus,hex(addr))]+=1
     d=decode(addr,bytes(frame.dat))
     if w=='sendcan' and addr==694 and bus==1:
      cmd=dict(t=t,braking=d.get('MDD_DECEL_CONTROL_REQ'),decel=d.get('MDD_DESIRED_DECELERATION'),status=d.get('ACC_STATUS'),torque=d.get('GMP_WHEEL_TORQUE'),potential_torque=d.get('GMP_POTENTIAL_WHEEL_TORQUE'))
      cmds.append(cmd);state.update(can_t=t,can_decel=cmd['decel'],can_braking=cmd['braking'],can_status=cmd['status'],can_torque=cmd['torque'])
     elif w=='can' and bus in (0,1):
      if addr==717:
       pressure=d.get('AUTO_BRAKING_PRESSURE',math.nan)
       pressures.append(dict(t=t,bus=bus,pressure=pressure));state.update(**{'pressure_'+str(bus):pressure,'pressure_t_'+str(bus):t})
      elif addr==1293:
       flag=d.get('P351_Com_bABSIntvActv',math.nan);abs_rows.append(dict(t=t,bus=bus,abs=flag))
      elif addr==813:
       state.update(**{'ucf_accel_'+str(bus):d.get('ACCEL_LONGI_CALIB',math.nan),'ucf_fault_'+str(bus):d.get('DEFAUT_ACC_FREIN',math.nan)})
  if kind=='rlog':print(route,seg.name.rsplit('--',1)[1],'read',round(time.monotonic()-st,1),'s',flush=True)
 rows.sort(key=lambda x:x['t']);cmds.sort(key=lambda x:x['t'])
 fields=sorted({k for row in rows for k in row})
 with gzip.open(ROOT/(route+'_'+kind+'_timeline.csv.gz'),'wt',newline='') as stream:
  writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader();writer.writerows(rows)
 for name,data in [('commands',cmds),('pressures',pressures),('abs',abs_rows)]:
  (ROOT/(route+'_'+kind+'_'+name+'.json')).write_text(json.dumps(data))
 result={'route':route,'kind':kind,'segments_present':[int(p.name.rsplit('--',1)[1]) for p in segs], 'duration_s':rows[-1]['t']-rows[0]['t'] if rows else 0,'t0':t0,'versions':sorted(versions),'counts':dict(counts),'can_counts':{'|'.join(map(str,k)):v for k,v in can_counts.items()},'rows':len(rows),'abs_samples':len(abs_rows),'abs_flag_ones':sum(r['abs']==1 for r in abs_rows),'pressure_max_by_bus':{str(b):max((r['pressure'] for r in pressures if r['bus']==b),default=None) for b in (0,1)}}
 if rows:
  active=[r for r in rows if r.get('long') and not r.get('gas') and not r.get('pedal_brake')]
  result.update(active_rows=len(active),vmax=max(r.get('v',0) for r in rows),min_requested=min((r['requested'] for r in active),default=None),min_applied=min((r.get('applied',0) for r in active),default=None),brake_saturation_rows=sum(r.get('applied',0)<=-1.99 for r in active),dec_counts=dict(Counter(r.get('dec') for r in active)),source_counts=dict(Counter(r.get('source') for r in active)))
  releases=[]
  for i in range(1,len(rows)):
   r=rows[i];before=rows[i-1]
   if before.get('gas')==1 and r.get('gas')==0 and r['t']-before['t']<1.0 and r.get('enabled'):
    after=[x for x in rows[i:i+(500 if kind=='rlog' else 60)] if x['t']<=r['t']+3]
    releases.append({'t':r['t'],'relative_s':r['t']-t0,'v':r.get('v'),'min_requested_next3s':min(x['requested'] for x in after),'min_applied_next3s':min(x.get('applied',0) for x in after),'initial_requested':r['requested'],'initial_applied':r.get('applied'),'source':r.get('source'),'dec':r.get('dec'),'drel':r.get('drel'),'long':r['long'],'state':r.get('longstate')})
  result['gas_releases']=releases
  # Brake onsets include separate CAN deceleration and mode flags.
  onsets=[]
  for i in range(1,len(cmds)):
   prev,cur=cmds[i-1:i+1]
   if cur['braking'] and not prev['braking'] and cur['t']-prev['t']<1:
    idx=int(np.searchsorted([r['t'] for r in rows],cur['t']))
    r=rows[max(0,min(idx-1,len(rows)-1))]
    onsets.append(dict(t=cur['t'],relative_s=cur['t']-t0,decel=cur['decel'],v=r.get('v'),requested=r.get('requested'),applied=r.get('applied'),source=r.get('source'),dec=r.get('dec'),gas=r.get('gas'),drel=r.get('drel')))
  result['brake_onsets']=onsets
 (ROOT/(route+'_'+kind+'_summary.json')).write_text(json.dumps(result,indent=2))
 print('SUMMARY',json.dumps({k:v for k,v in result.items() if k not in ('counts','can_counts','gas_releases','brake_onsets','segments_present')}),'gas releases',len(result.get('gas_releases',[])),'brake_onsets',len(result.get('brake_onsets',[])),flush=True)
 return result
if __name__=='__main__':
 kind=sys.argv[1] if len(sys.argv)>1 else 'qlog'
 manifest=json.loads((ROOT/'acquisition_manifest.json').read_text())
 VERIFIED=set(json.loads((ROOT/'rlog_partial_acquisition.json').read_text())['verified_files']) if kind=='rlog' else set()
 for r in manifest:
  if kind=='qlog' or any(x.startswith(r['route']+'--') for x in VERIFIED):process(r['route'],kind)
