# [radar findings] - START
from pathlib import Path
ANALYSIS_DIR = Path(__file__).resolve().parent
import sys, json, collections
from pathlib import Path
import capnp, zstandard
ROOT=Path('/Users/cristianku/GitHub/COMMA.AI/CRISTIANKU')
sys.path.insert(0,str(ROOT/'opendbc'))
capnp.remove_import_hook()
schema=capnp.load(str(ROOT/'new_openpilot_psa_torque_sunny_testing/openpilot/cereal/log.capnp'),imports=[str(ROOT/'opendbc/opendbc/car')])
base=ROOT/'openpilot_scripts/log_analysis'
routes={'test':base/'logitudinal_tests/test1/0000003d--3e125c1bb1','stock':base/'dashcam_mode_bibbia_longitudinale/0000003a--e445e79563'}
for name,path in routes.items():
 out={'can':[],'logs':[],'state':[],'params':[],'init':[],'alerts':[],'longactive':0,'counts':{}}
 counts=collections.Counter(); start=None; previous=None; lastalert=None
 for f in sorted(path.glob('*/rlog.zst')):
  raw=zstandard.ZstdDecompressor().stream_reader(f.open('rb')).read()
  for e in schema.Event.read_multiple_bytes(raw):
   if start is None:start=e.logMonoTime
   t=(e.logMonoTime-start)/1e9; kind=e.which(); counts[kind]+=1
   if kind in ('can','sendcan'):
    for c in getattr(e,kind):
     if c.address in (0x2b6,0x2f6,0x4f6,0x796,0x6b6,0x696,0x452):out['can'].append([round(t,6),kind,c.src,c.address,bytes(c.dat).hex()])
   elif kind in ('logMessage','errorLogMessage'):
    msg=str(getattr(e,kind))
    if any(s.lower() in msg.lower() for s in ('artiv','radar','can error','can invalid')):out['logs'].append([round(t,6),msg])
   elif kind=='carParams':
    d=e.carParams.to_dict(); out['params'].append({k:d.get(k) for k in ('carFingerprint','dashcamOnly','passive','openpilotLongitudinalControl','pcmCruise','safetyConfigs')})
   elif kind=='initData':
    d=e.initData.to_dict();out['init'].append({k:d.get(k) for k in ('gitCommit','gitBranch','version','dongleId')})
   elif kind=='carState':
    d=e.carState.to_dict(); state={k:d.get(k) for k in ('canValid','accFaulted','standstill','brakePressed','gasPressed','cruiseState')}
    if state!=previous:out['state'].append([round(t,6),round(d['vEgo'],3),state]);previous=state
   elif kind=='carControl':out['longactive']+=int(e.carControl.longActive)
   elif kind in ('selfdriveState','controlsState'):
    d=getattr(e,kind).to_dict();alert={k:v for k,v in d.items() if k.startswith('alert')}
    if alert and alert!=lastalert:out['alerts'].append([round(t,6),alert]);lastalert=alert
 out['counts']=dict(counts);out['duration']=t
 (ANALYSIS_DIR / ('radar_'+name+'.json')).write_text(json.dumps(out))
 print(name,json.dumps({k:v for k,v in out.items() if k not in ('can','state','alerts','logs')}),flush=True)
 print('logs',json.dumps(out['logs']),flush=True)
 print('CAN',collections.Counter((x[1],x[2],hex(x[3])) for x in out['can']),flush=True)

# [radar findings] - END
