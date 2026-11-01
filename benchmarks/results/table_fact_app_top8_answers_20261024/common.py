"""Bounded execution artifacts; no runtime/store imports."""
from __future__ import annotations
import hashlib, json, os, subprocess, sys
from datetime import datetime, timezone
from pathlib import Path

OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[2]
PREP=OUT.parent/'table_fact_app_top8_preparation_20261024'

class Stop(RuntimeError): pass
def need(ok, message):
    if not ok: raise Stop(message)
def now(): return datetime.now(timezone.utc).isoformat()
def enc(x): return json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode('utf8')
def load(p): return json.loads(Path(p).read_text('utf8'))
def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(4194304),b''):h.update(b)
    return h.hexdigest()
def digest(x): return hashlib.sha256(enc(x)).hexdigest()
def put(p,x):
    p=Path(p).resolve();need(p.is_relative_to(OUT),'Write outside new execution directory')
    p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('xb') as f:f.write(enc(x)+b'\n');f.flush();os.fsync(f.fileno())
def append(p,x):
    p=Path(p).resolve();need(p.is_relative_to(OUT),'Append outside execution directory')
    p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('ab') as f:f.write(enc(x)+b'\n');f.flush();os.fsync(f.fileno())
def git(*args): return subprocess.check_output(['git',*args],cwd=ROOT,env={**os.environ,'GIT_OPTIONAL_LOCKS':'0'})
def preserve():
    b=load(PREP/'before.json')
    changed=[p for p,h in b['files'].items() if not (ROOT/p).is_file() or sha(ROOT/p)!=h]
    active=ROOT/'data/app_full11_2023_v12_20261017'
    actual={p.relative_to(ROOT).as_posix() for p in active.rglob('*') if p.is_file()}
    checks={'head':git('rev-parse','HEAD').decode().strip()==b['head'],
            'index':sha(ROOT/git('rev-parse','--git-path','index').decode().strip())==b['index_sha256'],
            'git_status':hashlib.sha256(git('status','--short','--untracked-files=all','-z')).hexdigest()==b['git_status_sha256'],
            'active_store_file_set':actual==set(b['active_store_files'])}
    return {'at':now(),'changed':changed,'checks':checks,'protected_files':len(b['files']),
            'env_byte_identical':'.env' not in changed,'active_store_files':len(actual),
            'active_store_bytes_identical':not actual.intersection(changed) and checks['active_store_file_set'],
            'active_store_opened':False,'method':'Read raw file hashes only; no SQLite/Chroma client.'}
def frozen():
    f=load(PREP/'freeze.json')
    for p,h in f['local_files'].items():need(sha(PREP/p)==h,'Preparation drift: '+p)
    for p,h in f['external_dependency_files'].items():need(sha(ROOT/p)==h,'Preparation dependency drift: '+p)
    p=preserve();need(not p['changed'] and all(p['checks'].values()),'Protected source/env/store changed')
    return p
def runner_frozen():
    for p,h in load(OUT/'runner_freeze.json')['files'].items():need(sha(OUT/p)==h,'Runner drift: '+p)
    for n in ('requests18.json','schedule72.json','protocol.json','pricing.json','rubric18.json'):
        need(sha(PREP/n)==load(PREP/'freeze.json')['local_files'][n],'Frozen request/protocol drift')
