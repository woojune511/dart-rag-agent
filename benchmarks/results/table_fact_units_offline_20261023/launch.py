"""External wall-clock limit for the one frozen, offline run."""
import json
from pathlib import Path
import subprocess
import sys
import time

out = Path(__file__).resolve().parent
assert not (out / 'launcher_result.json').exists(), 'No automatic experiment rerun'
start = time.monotonic()
timed_out = False
with (out / 'stdout.log').open('w', encoding='utf-8') as log:
    try:
        result = subprocess.run([sys.executable, '-B', '-X', 'utf8', str(out / 'run.py'), 'run'],
                                stdout=log, stderr=subprocess.STDOUT, timeout=1800,
                                cwd=out.parents[2], check=False)
        exit_code = result.returncode
    except subprocess.TimeoutExpired:
        timed_out, exit_code = True, 124
receipt = {'exit_code': exit_code, 'timed_out': timed_out,
           'elapsed_seconds': round(time.monotonic() - start, 2),
           'wall_clock_cap_seconds': 1800, 'terminated_only_own_child_if_timeout': True}
(out / 'launcher_result.json').write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')
print(json.dumps(receipt), flush=True)
raise SystemExit(exit_code)
