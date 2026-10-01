import csv
import gzip
import importlib.util
import json
import subprocess
from pathlib import Path

import numpy as np

from opendbc.car import Bus
from opendbc.car.psa.tests.test_longitudinal import LongitudinalHarness

ROOT = Path('/Users/cristianku/GitHub/COMMA.AI/CRISTIANKU/openpilot_scripts/log_analysis/longitudinal_review_20261001_1700')
old_path = Path('/tmp/psa_review_installed_controller_20261001.py')
old_path.write_bytes(subprocess.check_output(['git', 'show', 'd79cb27c8:opendbc/car/psa/carcontroller.py']))
spec = importlib.util.spec_from_file_location('psa_review_installed_controller', old_path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

def replay(route, kind):
    current = LongitudinalHarness()
    old = LongitudinalHarness()
    old.controller = module.CarController({Bus.main: 'psa_aee2010_r3'}, old.controller.CP, old.controller.CP_SP)
    for harness in [old, current]:
        harness.controller.radar_active = True
    out = []
    with gzip.open(ROOT / f'{route}_{kind}_timeline.csv.gz', 'rt') as stream:
        rows = list(csv.DictReader(stream))
    for i, r in enumerate(rows):
        t = float(r['t'])
        next_t = float(rows[i+1]['t']) if i+1 < len(rows) else t + .01
        # Hold the recorded input at 100 Hz; reset through the recorded gates.
        cycles = max(1, round((next_t-t)/.01))
        if next_t-t > .2:
            for h in [old,current]:
                h.cc.longActive = False
                h.controller._update_longitudinal(h.cc.as_reader(), h.cs)
            cycles = 1
        for h in [old,current]:
            h.cc.actuators.accel = float(r['requested'])
            h.cc.enabled = bool(int(r.get('enabled') or 0))
            h.cc.longActive = bool(int(r.get('long') or 0))
            h.cc.orientationNED = [0.0, float(r.get('pitch') or 0), 0.0]
            for attr,key in [('gasPressed','gas'),('brakePressed','pedal_brake'),('canValid','canvalid')]:
                setattr(h.cs.out,attr,bool(int(r.get(key) or 0)))
            h.cs.out.cruiseState.enabled = bool(int(r.get('cruise') or 0))
            for _ in range(cycles):
                h.controller._update_longitudinal(h.cc.as_reader(), h.cs)
        out.append(dict(t=t,requested=float(r['requested']),recorded=float(r.get('applied') or 0),
                        old=old.controller.longitudinal_accel,filtered=current.controller.longitudinal_accel,
                        braking_old=int(old.controller.longitudinal_braking),braking_filtered=int(current.controller.longitudinal_braking),
                        active_old=int(old.controller.longitudinal_active),active_filtered=int(current.controller.longitudinal_active),
                        gas=int(r.get('gas') or 0),long=int(r.get('long') or 0),v=float(r.get('v') or 0),
                        aego=float(r.get('a') or 0),source=r.get('source'),drel=float(r.get('drel') or 0)))
    fields=list(out[0])
    with gzip.open(ROOT/f'{route}_{kind}_replay.csv.gz','wt',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader();writer.writerows(out)
    mode_changes=sum(r['braking_old']!=r['braking_filtered'] or r['active_old']!=r['active_filtered'] for r in out)
    entries=[i for i,r in enumerate(out) if r['braking_old'] and (i==0 or not out[i-1]['braking_old'])]
    details=[]
    for i in entries:
        r=out[i]
        j=next((j for j in range(i+1,min(i+100,len(out))) if out[j]['t']>=r['t']+.1),min(i+1,len(out)-1))
        details.append(dict(t=r['t'],v=r['v'],requested=r['requested'],old=r['old'],filtered=r['filtered'],
                            filtered_after_100ms=out[j]['filtered'],source=r['source'],drel=r['drel'],
                            gas_last_second=any(x['gas'] for x in out[max(0,i-(100 if kind=='rlog' else 10)):i])))
    jumps_old=[];jumps_new=[]
    errors=[]
    for prev,r in zip(out,out[1:]):
        if r['t']-prev['t']<=.12 and r['braking_old']:
            jumps_old.append(max(0,prev['old']-r['old']))
            jumps_new.append(max(0,prev['filtered']-r['filtered']))
            errors.append(abs(r['old']-r['recorded']))
    summary=dict(route=route,kind=kind,rows=len(out),mode_changes=mode_changes,brake_entries=len(entries),
                 old_max_stronger_step=max(jumps_old,default=0),filtered_max_stronger_step=max(jumps_new,default=0),
                 recorded_old_median_abs_error=float(np.median(errors)),recorded_old_p95_abs_error=float(np.percentile(errors,95)),
                 episodes=details)
    print(json.dumps({k:v for k,v in summary.items() if k!='episodes'}),flush=True)
    return summary

result=dict(method='Recorded requests and pitch held at 100 Hz through installed old controller and current controller; radar session assumed available; no planner or physical vehicle feedback replay.',
            installed_opendbc='d79cb27c85fb9f447cb0276858a6a51376a09198',
            local_opendbc=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
            routes=[replay('000000b8--8846cc65c2','rlog'),replay('000000b4--68c9b67304','qlog')])
(ROOT/'controller_replay_summary.json').write_text(json.dumps(result,indent=2))
