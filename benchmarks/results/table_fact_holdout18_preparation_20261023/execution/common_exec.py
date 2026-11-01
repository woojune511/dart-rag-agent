"""Isolated experiment utilities; no provider or active-store client."""
import gzip, hashlib, json, os, subprocess, sys
from pathlib import Path
from datetime import datetime, timezone

OUT = Path(__file__).resolve().parent
PREP = OUT.parent
ROOT = PREP.parents[2]
sys.path.insert(0, str(ROOT))

class Stop(RuntimeError): pass
def need(condition, message):
    if not condition: raise Stop(message)
def now(): return datetime.now(timezone.utc).isoformat()
def enc(x): return json.dumps(x, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf8')
def load(p): return json.loads(Path(p).read_text('utf8'))
def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(2**20),b''): h.update(b)
    return h.hexdigest()
def put(p,x):
    p=Path(p).resolve();need(p.is_relative_to(OUT),'Write outside execution scope')
    p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('xb') as f: f.write(enc(x)+b'\n');f.flush();os.fsync(f.fileno())
def append(p,x):
    p=Path(p).resolve();need(p.is_relative_to(OUT),'Append outside execution scope')
    p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('ab') as f: f.write(enc(x)+b'\n');f.flush();os.fsync(f.fileno())
def corpus():
    with gzip.open(PREP/'corpus.jsonl.gz','rt',encoding='utf8') as f: return [json.loads(x) for x in f]
def git(*args): return subprocess.check_output(['git',*args],cwd=ROOT,env={**os.environ,'GIT_OPTIONAL_LOCKS':'0'})
def preserve():
    b=load(PREP/'before.json')
    changed=[p for p,h in b['files'].items() if not (ROOT/p).is_file() or sha(ROOT/p)!=h]
    checks={'head':git('rev-parse','HEAD').decode().strip()==b['head'],
      'index':sha(ROOT/'.git/index')==b['index_sha256'],
      'status':git('status','--porcelain=v1','-z','--untracked-files=all')==(PREP/'git_status_before.bin').read_bytes()}
    active=ROOT/'data/app_full11_2023_v12_20261017'
    store_paths={str(p.relative_to(ROOT)) for p in active.rglob('*') if p.is_file()}
    checks['active_store_file_set']=store_paths==set(b['active_store_files'])
    return {'at':now(),'changed':changed,'checks':checks,'protected_files':len(b['files']),
      'active_store_files':len(store_paths),'env_unchanged':'.env' not in changed,
      'active_store_unchanged':not set(changed).intersection(b['active_store_files']) and checks['active_store_file_set'],
      'active_store_opened':False,'method':'Raw byte hashes only; no SQLite/Chroma client opened for active store.'}
def frozen():
    f=load(PREP/'freeze.json')
    for p,h in f['files'].items():need(sha(PREP/p)==h,'Preparation changed '+p)
    for p,h in f['dependencies'].items():need(sha(ROOT/p)==h,'Algorithm changed '+p)
    check=preserve();need(not check['changed'] and all(check['checks'].values()),'Protected files changed')
    return check
def module(path,name):
    import importlib.util
    s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s)
    sys.modules[name]=m;s.loader.exec_module(m);return m
