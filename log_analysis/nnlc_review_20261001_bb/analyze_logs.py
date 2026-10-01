# [nnlc review] - START
import csv
import gzip
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np

sys.path.insert(0,'/Users/cristianku/GitHub/COMMA.AI/CRISTIANKU/openpilot_scripts/log_analysis')
import psa_eps_timeline as p
p.CEREAL_CANDIDATES=['/Users/cristianku/GitHub/COMMA.AI/CRISTIANKU/new_openpilot_psa_torque_sunny_testing/openpilot/cereal']
schema=p.load_schema()
ROOT=Path('/Users/cristianku/GitHub/COMMA.AI/CRISTIANKU/openpilot_scripts/log_analysis/nnlc_review_20261001_bb')
signals=p.dbc_signals(p.DBC,{0x3F2,0x495,0x305})
state={}; rows=[];can_rows=[]; counts=Counter();versions=set();cp=[];cp_sp=[];params=[]; live=[]
for seg in sorted(ROOT.glob('000000bb--2d3dbf3a70--*'),key=lambda path:int(path.name.rsplit('--',1)[1])):
 for event in p.read_events(schema,seg/'rlog.zst'):
  topic=event.which();t=event.logMonoTime/1e9;counts[topic]+=1
  if topic=='initData':versions.add(str(event.initData.gitCommit))
  elif topic=='carParams':
   x=event.carParams
   cp.append(dict(platform=str(x.carFingerprint),steerControlType=str(x.steerControlType),torque=x.lateralTuning.torque.to_dict() if x.lateralTuning.which()=='torque' else {}))
  elif topic=='carParamsSP':cp_sp.append(event.carParamsSP.neuralNetworkLateralControl.to_dict())
  elif topic=='carState':
   x=event.carState;state.update(v=x.vEgo*3.6,angle=x.steeringAngleDeg,rate=x.steeringRateDeg,
     driver=x.steeringTorque,pressed=int(x.steeringPressed),eps_torque=x.steeringTorqueEps,canvalid=int(x.canValid),state_t=t)
  elif topic=='liveParameters':
   x=event.liveParameters;state.update(roll=x.roll,angle_offset=x.angleOffsetDeg,stiffness=x.stiffnessFactor,steer_ratio=x.steerRatio)
  elif topic=='lateralTorqueParameters':
   x=event.lateralTorqueParameters.to_dict();live.append(dict(t=t,values=x))
  elif topic=='carControl':
   x=event.carControl;state.update(torque=x.actuators.torque,lat=int(x.latActive),enabled=int(x.enabled),cc_t=t,curvature_request=x.actuators.curvature)
  elif topic=='carOutput':
   x=event.carOutput.actuatorsOutput;state.update(output_torque=x.torque,output_can=x.torqueOutputCan,output_t=t)
  elif topic=='controlsState':
   x=event.controlsState
   if x.lateralControlState.which()=='torqueState':
    torque=x.lateralControlState.torqueState
    state.update(actual=torque.actualLateralAccel,desired=torque.desiredLateralAccel,desired_jerk=torque.desiredLateralJerk,
                 pid_error=torque.error,p=torque.p,i=torque.i,f=torque.f,pid_output=torque.output,active=int(torque.active),
                 saturated=int(torque.saturated),desired_curvature=x.desiredCurvature,actual_curvature=x.curvature)
    rows.append(dict(t=t,**state))
  elif topic=='carControlSP':
   for param in event.carControlSP.params:
    if 'Neural' in str(param.key) or 'Torque' in str(param.key):
     value=bytes(param.value).decode('utf8',errors='replace')
     item=dict(key=str(param.key),type=str(param.type),value=value)
     if item not in params:params.append(item)
  elif topic in ('can','sendcan'):
   for frame in getattr(event,topic):
    addr=frame.address;bus=frame.src
    if addr not in signals:continue
    decoded={name:p.extract(bytes(frame.dat),spec) for name,spec in signals[addr].items()}
    if addr==0x3F2 and (topic=='sendcan' and bus==0 or topic=='can' and bus in [128,192]):
     item=dict(t=t,topic=topic,bus=bus,torque=decoded.get('TORQUE'),factor=decoded.get('TORQUE_FACTOR'),status=decoded.get('STATUS'))
     can_rows.append(item)
     if topic=='sendcan':state.update(can_t=t,can_torque=item['torque'],can_factor=item['factor'],can_status=item['status'])
    elif addr==0x495 and topic=='can' and bus==0:state.update(eps=decoded.get('EPS_STATE_LKA'),eps_t=t)
 print('Read',seg.name,flush=True)
fields=sorted({key for row in rows for key in row})
with gzip.open(ROOT/'lateral_timeline.csv.gz','wt',newline='') as stream:
 writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader();writer.writerows(rows)
(ROOT/'can_steering.json').write_text(json.dumps(can_rows))
active=[r for r in rows if r.get('lat') and r['active'] and r.get('v',0)>51 and not r.get('pressed')]
nontrivial=[r for r in active if abs(r['desired'])>.15 and abs(r.get('torque',0))>.05]
error_rows=[r for r in active if abs(r['desired']-r['actual'])>.15 and abs(r['pid_error'])>.03]
def correlation(items,a,b):
 if len(items)<3:return None
 return float(np.corrcoef([r[a] for r in items],[r[b] for r in items])[0,1])
summary=dict(route='000000bb--2d3dbf3a70',versions=sorted(versions),counts=dict(counts),rows=len(rows),
 duration_s=rows[-1]['t']-rows[0]['t'],t0=rows[0]['t'],carParams=cp[:1],models=cp_sp[:1],logged_params=params,
 active_no_driver=len(active),desired_torque_nontrivial=len(nontrivial),
 desired_external_torque_same_sign=sum(r['desired']*r['torque']>0 for r in nontrivial),
 desired_feedforward_same_sign=sum(r['desired']*r['f']>0 for r in nontrivial),
 pid_error_vs_lat_error_corr=correlation([dict(r,lat_error=r['desired']-r['actual']) for r in error_rows],'lat_error','pid_error'),
 opposite_pid_error_count=sum((r['desired']-r['actual'])*r['pid_error']<0 for r in error_rows),
 pid_error_nontrivial=len(error_rows),torque_vs_desired_corr=correlation(active,'desired','torque'),
 external_torque_vs_can_corr=correlation([r for r in active if 'can_torque'in r],'torque','can_torque'),
 saturated_rows=sum(r['saturated'] for r in active),live_parameters_first=live[:1],live_parameters_last=live[-1:])
(ROOT/'lateral_summary.json').write_text(json.dumps(summary,indent=2))
print(json.dumps(summary,indent=2),flush=True)
# [nnlc review] - END
