# [radar findings] - START
from pathlib import Path
ANALYSIS_DIR = Path(__file__).resolve().parent
import bisect
exec((ANALYSIS_DIR / 'compare_radar_logs.py').open().read().split('for name,path in routes.items():')[0])

inventory={}
for name,path in routes.items():
 stats={}; start=None; count=0
 state=sorted(json.loads((ANALYSIS_DIR / ('radar_'+name+'.json')).read_text())['state'])
 state_times=[s[0] for s in state]
 def add(key,t,data):
  if key not in stats:stats[key]={'n':0,'first':t,'last':t,'seconds':{},'samples':[],'maxgap':0}
  d=stats[key];d['n']+=1
  d['maxgap']=max(d['maxgap'],t-d['last']);d['first']=min(d['first'],t);d['last']=max(d['last'],t)
  sec=int(t);d['seconds'][sec]=d['seconds'].get(sec,0)+1
  if len(d['samples'])<3:d['samples'].append([round(t,6),data.hex()])
 for f in sorted(path.glob('*/rlog.zst')):
  raw=zstandard.ZstdDecompressor().stream_reader(f.open('rb')).read()
  for e in schema.Event.read_multiple_bytes(raw):
   if start is None:start=e.logMonoTime
   kind=e.which()
   if kind not in ('can','sendcan'):continue
   t=(e.logMonoTime-start)/1e9
   idx=bisect.bisect_right(state_times,t)-1
   parked=idx>=0 and state[idx][2]['standstill']
   if name=='test':phase='pre' if t<16.769035 else 'emulation' if 16.877594<=t<223.135027 else 'post' if t>=227.860843 else 'transition'
   else:phase='parked' if parked else 'moving_or_initial'
   for c in getattr(e,kind):
    data=bytes(c.dat);a=c.address;src=c.src
    add((kind,src,a,len(data),'all'),t,data)
    add((kind,src,a,len(data),phase),t,data)
    if kind=='can' and src<192:
     bus=src-128 if src>=128 else src
     add(('physical',bus,a,len(data),'all'),t,data)
     add(('physical',bus,a,len(data),phase),t,data)
    count+=1
 inventory[name]=[dict(kind=k[0],src=k[1],addr=k[2],dlc=k[3],phase=k[4],**v) for k,v in stats.items()]
 print(name,'frames examined',count,'keys',len(stats),flush=True)
(ANALYSIS_DIR / 'radar_full_inventory.json').write_text(json.dumps(inventory))

def select(name,phase='all',kind='physical',bus=None):
 return {(r['src'],r['addr'],r['dlc']):r for r in inventory[name] if r['phase']==phase and r['kind']==kind and (bus is None or r['src']==bus)}
for phase in ('all','pre','emulation','post'):
 test=select('test',phase);stock=select('stock')
 print('STOCK ABSENT IN TEST '+phase, [(b,hex(a),d,stock[b,a,d]['n'],round(stock[b,a,d]['first'],3),round(stock[b,a,d]['last'],3)) for b,a,d in sorted(stock.keys()-test.keys())],flush=True)
pre=select('test','pre','can',1);active=select('test','emulation','can',1)
print('NATIVE BUS1 DISAPPEARING AFTER PROGRAM',[(hex(a),d,pre[b,a,d]['n']) for b,a,d in sorted(pre.keys()-active.keys())],flush=True)
print('BUS1 full compare',[(hex(a),d,r['n'],select('test','emulation').get((b,a,d),{}).get('n',0)) for (b,a,d),r in sorted(select('stock',bus=1).items())],flush=True)

# [radar findings] - END
