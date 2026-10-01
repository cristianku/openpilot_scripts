import hashlib
import json
import os
import shlex
import subprocess
import tarfile
from pathlib import Path

BASE = Path('/Users/cristianku/GitHub/COMMA.AI/CRISTIANKU/openpilot_scripts/log_analysis')
DEST = BASE / 'longitudinal_review_20261001_1700'
CACHE = BASE / 'longitudinal_noise_20261001'
DEST.mkdir(parents=True, exist_ok=True)
SSH = ['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=8', 'comma@192.168.88.29']
REMOTE = '''import hashlib,json
from pathlib import Path
root=Path('/data/media/0/realdata'); routes={}
for p in root.iterdir():
 if p.is_dir() and '--' in p.name: routes.setdefault(p.name.rsplit('--',1)[0],[]).append(p)
latest=sorted(routes.items(),key=lambda kv:max(p.stat().st_mtime for p in kv[1]),reverse=True)[:4]
out=[]
for index,(route,dirs) in enumerate(latest):
 files=[]
 for p in sorted(dirs,key=lambda p:int(p.name.rsplit('--',1)[1])):
  for name in (('qlog.zst','rlog.zst') if index==0 else ('qlog.zst',)):
   f=p/name
   if not f.is_file(): continue
   h=hashlib.sha256()
   with f.open('rb') as s:
    for chunk in iter(lambda:s.read(1048576),b''):h.update(chunk)
   files.append(dict(path=str(f.relative_to(root)),size=f.stat().st_size,sha256=h.hexdigest(),mtime=f.stat().st_mtime))
 out.append(dict(route=route,files=files))
print(json.dumps(out))
'''

def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for data in iter(lambda: stream.read(1048576), b''):
            h.update(data)
    return h.hexdigest()

manifest = json.loads(subprocess.check_output(SSH + ['python3 -'], input=REMOTE, text=True))
(DEST / 'acquisition_manifest.json').write_text(json.dumps(manifest, indent=2))
files = [f for route in manifest for f in route['files']]
missing = []
cached = []
for f in files:
    source, target = CACHE / f['path'], DEST / f['path']
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.is_file() and target.stat().st_size == f['size'] and digest(target) == f['sha256']:
        cached.append(f['path'])
    elif source.is_file() and source.stat().st_size == f['size'] and digest(source) == f['sha256']:
        if target.exists():
            raise RuntimeError('Preserve existing unexpected file: ' + str(target))
        os.link(source, target)
        cached.append(f['path'])
    else:
        missing.append(f)
print(json.dumps(dict(routes=[r['route'] for r in manifest], files=len(files), reused_verified=len(cached), download_files=len(missing), download_MB=round(sum(f['size'] for f in missing)/1e6, 2))), flush=True)
if missing:
    names = {f['path'] for f in missing}
    remote_cmd = 'tar -C /data/media/0/realdata -cf - ' + ' '.join(shlex.quote(f['path']) for f in missing)
    proc = subprocess.Popen(SSH + [remote_cmd], stdout=subprocess.PIPE)
    with tarfile.open(fileobj=proc.stdout, mode='r|') as archive:
        for member in archive:
            if member.name not in names or not member.isfile():
                raise RuntimeError('Unexpected archive entry: ' + member.name)
            archive.extract(member, DEST, filter='data')
            print('Downloaded ' + member.name, flush=True)
    if proc.wait() != 0:
        raise RuntimeError('SSH download failed')
for f in files:
    path = DEST / f['path']
    assert path.stat().st_size == f['size'] and digest(path) == f['sha256'], f['path']
verification = dict(host='comma@192.168.88.29', read_only_device=True, sha256_verified=True,
                    total_files=len(files), fresh_downloads=[f['path'] for f in missing],
                    reused_matched_current_remote=cached,
                    verified_rlogs=[f['path'] for f in files if f['path'].endswith('/rlog.zst')])
(DEST / 'acquisition_verification.json').write_text(json.dumps(verification, indent=2))
print('SHA256 verified all ' + str(len(files)) + ' files. Destination: ' + str(DEST), flush=True)
