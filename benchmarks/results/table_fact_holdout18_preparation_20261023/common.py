"""Task-local preparation utilities. No model/store clients."""
from pathlib import Path
import hashlib, json, subprocess, datetime, contextlib, socket, sys
BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[2]
sys.path.insert(0, str(ROOT))
def now(): return datetime.datetime.now(datetime.timezone.utc).isoformat()
def read(p): return json.loads(Path(p).read_text('utf-8'))
def sha(p):
    h = hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda: f.read(4*1024*1024), b''): h.update(b)
    return h.hexdigest()
def write(p, value):
    p = Path(p).resolve()
    assert p.is_relative_to(BASE)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+'\n', encoding='utf-8')
def git(*args): return subprocess.check_output(['git', *args], cwd=ROOT)
@contextlib.contextmanager
def offline():
    def denied(*a, **k): raise RuntimeError('Network prohibited in offline preparation')
    targets = [(socket,'create_connection'),(socket,'getaddrinfo'),(socket.socket,'connect'),(socket.socket,'connect_ex')]
    previous=[(obj,key,getattr(obj,key)) for obj,key in targets]
    for obj,key in targets: setattr(obj,key,denied)
    try: yield
    finally:
        for obj,key,value in previous: setattr(obj,key,value)
