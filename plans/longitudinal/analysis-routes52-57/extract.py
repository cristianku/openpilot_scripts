from pathlib import Path
import sys,json,collections
import capnp,zstandard,numpy as np
ROOT=Path('/Users/cristianku/GitHub/COMMA.AI/CRISTIANKU');OUT=Path('/tmp/psa-downhill-52-57')
BASE=ROOT/'openpilot_scripts/log_analysis/logitudinal_tests/20260913/acc_downhill_52_57'
sys.path.insert(0,str(ROOT/'opendbc'))
from opendbc.can.packer import CANPacker
from opendbc.can.parser import get_raw_value
capnp.remove_import_hook();schema=capnp.load(str(ROOT/'new_openpilot_psa_torque_sunny_testing/openpilot/cereal/log.capnp'),imports=[str(ROOT/'opendbc/opendbc/car')])
p=CANPacker('psa_aee2010_r3');names={}
ids={0x208,0x228,0x2b6,0x2f6,0x452,0x32d,0x38d,0x348,0x4f6,0x796,0x56e}
def decode(data,sig):
 value=get_raw_value(data,sig)
 if sig.is_signed and value & (1 << (sig.size-1)):value-=1 << sig.size
 return value*sig.factor+sig.offset
for route in sorted({f.parent.name.rsplit('--',1)[0] for f in BASE.glob('*/rlog.zst')}):
 rows=collections.defaultdict(list);meta=collections.defaultdict(list);last={};counts=collections.Counter()
 def row(k,t,ns,vs):
  names[k]=ns;rows[k].append([t,*vs])
 for file in sorted(BASE.glob(route+'--*/rlog.zst'),key=lambda f:int(f.parent.name.rsplit('--',1)[1])):
  raw=zstandard.ZstdDecompressor().stream_reader(file.read_bytes()).read();t0=None
  for e in schema.Event.read_multiple_bytes(raw):
   t=e.logMonoTime/1e9;k=e.which();counts[k]+=1;t0=t if t0 is None else t0
   if k in ('can','sendcan'):
    for c in getattr(e,k):
     if c.address in (0x696,0x6b6):meta['diag'].append([t,k,c.src,hex(c.address),bytes(c.dat).hex()])
     if c.address not in ids:continue
     msg=p.dbc.addr_to_msg[c.address];data=bytes(c.dat);ns=list(msg.sigs)
     if any(max(s.msb,s.lsb)//8>=len(data) for s in msg.sigs.values()):continue
     row(f'{k}_{c.src}_{hex(c.address)}',t,ns,[decode(data,msg.sigs[n]) for n in ns])
   elif k=='carState':
    c=e.carState
    row(k,t,['vEgo','vEgoRaw','aEgo','gas','brake','canValid','accFaulted','cruiseEnabled','setSpeed','vCruise','steeringAngle'],[c.vEgo,c.vEgoRaw,c.aEgo,c.gasPressed,c.brakePressed,c.canValid,c.accFaulted,c.cruiseState.enabled,c.cruiseState.speed,c.vCruise,c.steeringAngleDeg])
   elif k=='carControl':
    c=e.carControl;row(k,t,['enabled','longActive','accel','pitch'],[c.enabled,c.longActive,c.actuators.accel,c.orientationNED[1] if len(c.orientationNED)==3 else float('nan')])
   elif k=='carOutput':row(k,t,['accel'],[e.carOutput.actuatorsOutput.accel])
   elif k=='controlsState':
    c=e.controlsState;row(k,t,['p','i','f','forceDecel'],[c.upAccelCmd,c.uiAccelCmd,c.ufAccelCmd,c.forceDecel])
   elif k=='longitudinalPlan':
    c=e.longitudinalPlan;row(k,t,['aTarget','hasLead','speed0','accel0','jerk0','allowBrake'],[c.aTarget,c.hasLead,c.speeds[0] if c.speeds else np.nan,c.accels[0] if c.accels else np.nan,c.jerks[0] if c.jerks else np.nan,c.allowBrake])
   elif k=='pandaStates':
    for i,c in enumerate(e.pandaStates):
     d=c.to_dict();row(f'panda{i}',t,['controlsAllowed','rxInvalid','txBlocked'],[d.get('controlsAllowed',0),d.get('safetyRxChecksInvalid',0),d.get('safetyTxBlocked',0)])
     v={n:d.get(n) for n in ['safetyModel','safetyParam','faults']}
     if v!=last.get(f'panda{i}'):meta[f'panda{i}'].append([t,v]);last[f'panda{i}']=v
   elif k in ('carParams','initData'):
    d=getattr(e,k).to_dict()
    if k=='carParams':d={n:d.get(n) for n in ['carFingerprint','dashcamOnly','passive','openpilotLongitudinalControl','pcmCruise','safetyConfigs','longitudinalTuning']}
    else:
     d={**{n:d.get(n) for n in ['gitCommit','gitBranch','dirty','wallTimeNanos']},'params':{v['key']:v['value'].decode(errors='replace') for v in d.get('params',{}).get('entries',[]) if any(s in v['key'] for s in ['Disengage','Cruise','SpeedLimit','Experimental','AlphaLong'])}}
    if not meta[k]:meta[k].append([t,d])
   elif k in ('selfdriveState','longitudinalPlanSP','onroadEvents','onroadEventsSP'):
    if k=='selfdriveState':
     c=e.selfdriveState;d={n:getattr(c,n) for n in ['enabled','active','alertText1','alertText2','alertType']};d['stateRaw']=c.state.raw
    elif k=='onroadEvents':d=[v.to_dict() for v in getattr(e,k)]
    else:d=getattr(e,k).to_dict()
    if d!=last.get(k):meta[k].append([t,d]);last[k]=d
   elif k in ('logMessage','errorLogMessage'):
    try:msg=json.loads(str(getattr(e,k))).get('msg','')
    except:msg=str(getattr(e,k))
    if any(s in str(msg).lower() for s in ['artiv','fault','can error','mismatch','blocked']):meta['logs'].append([t,msg])
  meta['files'].append({'file':file.parent.name,'first':t0,'last':t});print('Parsed',file.parent.name,flush=True)
 np.savez_compressed(OUT/(route+'.npz'),**{k:np.asarray(v) for k,v in rows.items()})
 meta['counts']=dict(counts);(OUT/(route+'.json')).write_text(json.dumps(meta,indent=2,default=str));print('SAVED',route,flush=True)
(OUT/'signals.json').write_text(json.dumps(names,indent=2))
