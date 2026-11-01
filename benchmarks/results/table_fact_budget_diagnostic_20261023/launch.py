import json
from pathlib import Path
import subprocess
import sys
import time

out = Path(__file__).resolve().parent
assert not (out / 'launcher_result.json').exists()
start = time.monotonic()
with (out / 'stdout.log').open('w', encoding='utf-8') as log:
    try:
        r = subprocess.run([sys.executable, '-B', '-X', 'utf8', str(out / 'check.py')],
                           cwd=out.parents[2], stdout=log, stderr=subprocess.STDOUT,
                           timeout=300, check=False)
        code, timeout = r.returncode, False
    except subprocess.TimeoutExpired:
        code, timeout = 124, True
result = {'exit_code': code, 'timeout': timeout, 'elapsed_seconds': round(time.monotonic() - start, 2)}
(out / 'launcher_result.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
print(json.dumps(result))
raise SystemExit(code)
