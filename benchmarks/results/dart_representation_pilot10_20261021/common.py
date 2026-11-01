"""Isolated evaluation preparation; no provider or store construction."""
from contextlib import ExitStack, contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
from unittest.mock import patch

BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[2]
sys.path.insert(0, str(ROOT))

def now():
    return datetime.now(timezone.utc).isoformat()

def sha(path):
    with Path(path).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()

def load(path):
    return json.loads(Path(path).read_text('utf-8-sig'))

def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8', newline='\n') as f:
        f.write(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+'\n')

@contextmanager
def offline():
    with ExitStack() as stack:
        stack.enter_context(patch.dict(os.environ, {'ANONYMIZED_TELEMETRY':'False','LANGSMITH_TRACING':'false','LANGCHAIN_TRACING_V2':'false'}))
        for target in ('socket.socket.connect','socket.socket.connect_ex','socket.create_connection','httpx.Client.send','httpx.AsyncClient.send','requests.sessions.Session.request'):
            stack.enter_context(patch(target, side_effect=AssertionError('Offline preparation forbids network')))
        yield
