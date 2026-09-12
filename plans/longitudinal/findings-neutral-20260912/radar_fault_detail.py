# [radar findings] - START
from pathlib import Path
ANALYSIS_DIR = Path(__file__).resolve().parent
exec((ANALYSIS_DIR / 'compare_radar_logs.py').open().read().split('for name,path in routes.items():')[0])
from opendbc.can.packer import CANPacker
from opendbc.can.parser import get_raw_value
p=CANPacker('psa_aee2010_r3')
for name,path in routes.items():
 start=None; prev={}; transitions=[]; window=collections.defaultdict(collections.Counter); states=collections.Counter(); missing={}
 for f in sorted(path.glob('*/rlog.zst')):
  raw=zstandard.ZstdDecompressor().stream_reader(f.open('rb')).read()
  for e in schema.Event.read_multiple_bytes(raw):
   if start is None:start=e.logMonoTime
   t=(e.logMonoTime-start)/1e9
   if e.which()!='can':continue
   for c in e.can:
    if c.src!=1:continue
    if name=='test':
     w='before' if 12<t<16 else 'during' if 18<t<22 else 'after' if 235<t<239 else None
     if w:window[w][c.address]+=1
    if c.address not in (0x32d,0x2b6,0x2f6,0x4f6):continue
    vals={n:round(get_raw_value(bytes(c.dat),s)*s.factor+s.offset,6) for n,s in p.dbc.addr_to_msg[c.address].sigs.items()}
    wanted={0x32d:['ACC_ETAT_DECEL_OR_ESP_STATUS'],0x2b6:['ACC_STATUS','AUTO_BRAKING_STATUS'],0x2f6:['ARC_STATUS','AUTO_BRAKING_STATUS'],0x4f6:['ARTIV_SENSOR_STATE']}[c.address]
    v={k:vals[k] for k in wanted}; states[(hex(c.address),str(v))]+=1
    if v!=prev.get(c.address):
     if name=='test':transitions.append([round(t,6),hex(c.address),bytes(c.dat).hex(),v])
     prev[c.address]=v
 print(name,'transitions',json.dumps(transitions),flush=True)
 print(name,'states',states,flush=True)
 if name=='test':print('missing during',[hex(a) for a,n in window['before'].items() if n>2 and not window['during'][a]],'windows', {w:{hex(a):n for a,n in c.items()} for w,c in window.items()},flush=True)

# [radar findings] - END
