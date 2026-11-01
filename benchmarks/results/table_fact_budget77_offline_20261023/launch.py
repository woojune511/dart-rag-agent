"""Bounded, monitored local replay. No automatic retries."""
from pathlib import Path
import json
import subprocess
import sys
import time

OUT = Path(__file__).resolve().parent
start = time.monotonic()
with (OUT / 'stdout.log').open('w', encoding='utf-8') as log:
    process = subprocess.Popen([sys.executable, '-B', '-X', 'utf8', str(OUT / 'compare.py'), 'run'],
                               stdout=log, stderr=subprocess.STDOUT, cwd=OUT.parents[2])
    print(json.dumps({'phase': 'launched', 'pid': process.pid, 'timeout_seconds': 1800}), flush=True)
    while process.poll() is None:
        elapsed = time.monotonic() - start
        if elapsed > 1800:
            print('Hard 30-minute limit reached; terminating this experiment process only.', flush=True)
            process.kill()
            process.wait()
            break
        print(json.dumps({'phase': 'process_alive', 'elapsed_seconds': round(elapsed, 2),
                          'stdout_bytes': (OUT / 'stdout.log').stat().st_size}), flush=True)
        time.sleep(20)
result = {'exit_code': process.returncode, 'elapsed_seconds': round(time.monotonic() - start, 2),
          'retried': False, 'external_API_calls': 0}
(OUT / 'launcher_result.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
print(json.dumps(result), flush=True)
sys.exit(process.returncode)
