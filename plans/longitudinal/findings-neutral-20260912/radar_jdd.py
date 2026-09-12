# [radar findings] - START
from pathlib import Path
ANALYSIS_DIR = Path(__file__).resolve().parent
exec((ANALYSIS_DIR / 'compare_radar_logs.py').open().read().split('for name,path in routes.items():')[0])
rows=[];start=None
for f in sorted(routes['test'].glob('*/rlog.zst')):
 raw=zstandard.ZstdDecompressor().stream_reader(f.open('rb')).read()
 for e in schema.Event.read_multiple_bytes(raw):
  if start is None:start=e.logMonoTime
  if e.which()!='can':continue
  for c in e.can:
   if c.address!=0x776 or c.src!=1:continue
   t=(e.logMonoTime-start)/1e9;b=bytes(c.dat)
   d={'t':round(t,6),'payload':b.hex(),'frame':(b[0]>>4)&3,'dtc_status':(b[0]>>3)&1}
   if d['frame']==1:d.update(dtc=b[1:4].hex(),reference_time=int.from_bytes(b[4:8],'big')/10)
   rows.append(d)
(ANALYSIS_DIR / 'radar_jdd.json').write_text(json.dumps(rows,indent=2))
codes=collections.defaultdict(list)
for r in rows:
 if 'dtc' in r:codes[(r['dtc'],r['dtc_status'])].append(r['t'])
for (dtc,status),ts in codes.items():print(dtc,status,len(ts),min(ts),max(ts))

# [radar findings] - END
