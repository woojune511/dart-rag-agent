"""Check the packaged saved-output data using only the Python standard library.

This checks the public payload against its manifest, not upstream execution,
answer correctness, the application runtime or the reported 12-case metrics.
"""

import hashlib
import json
from pathlib import Path
import re
import sys


def verify(directory):
    html = (directory / 'index.html').read_text(encoding='utf-8')
    blocks = re.findall(r'<script id="demo-data" type="application/json">(.*?)</script>', html, re.S)
    if len(blocks) != 1:
        raise ValueError('Expected exactly one saved-data block')
    payload = json.loads(blocks[0])
    manifest = json.loads((directory / 'provenance.json').read_text(encoding='utf-8'))
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')
    if hashlib.sha256(canonical).hexdigest() != manifest['payload_sha256']:
        raise ValueError('Saved-data hash does not match the provenance manifest')
    ids = [case['id'] for case in payload['cases']]
    if ids != manifest['case_ids'] or len(ids) != len(set(ids)) or payload['initial_case'] not in ids:
        raise ValueError('Case selection does not match the provenance manifest')
    return len(ids)


if __name__ == '__main__':
    try:
        count = verify(Path(__file__).resolve().parent)
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f'FAIL: {error}', file=sys.stderr)
        raise SystemExit(1)
    print(f'PASS: {count} saved cases match the public data manifest.')
    print('Integrity only; no provider calls, runtime execution or new quality evaluation.')
