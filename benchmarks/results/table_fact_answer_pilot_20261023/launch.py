"""Enforce an absolute90minute wall deadline on the only live experiment process."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

OUT=Path(__file__).resolve().parent

def wait_bounded(process, seconds):
    try:
        return process.wait(timeout=seconds), False
    except subprocess.TimeoutExpired:
        process.kill()
        return process.wait(), True

def main():
    if len(sys.argv)>1 and sys.argv[1]=='--test':
        p=subprocess.Popen([sys.executable,'-B','-c','import time; time.sleep(5)'],
                           creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        _,killed=wait_bounded(p,0.05)
        assert killed and p.poll() is not None
        print('WHOLE_PROCESS_TIMEOUT_MOCK_PASS; external calls0')
        return
    marker=OUT/'watchdog_started.json'
    with marker.open('x',encoding='utf-8') as f:
        json.dump({'max_wall_seconds':5400,'scope':'Includes preflight, generation and child cleanup; no automatic restart.'},f)
    env=dict(os.environ)
    env['TABLE_FACT_PILOT_WATCHDOG']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    started=time.monotonic()
    p=subprocess.Popen([sys.executable,'-B','-X','utf8',str(OUT/'run.py'),'live'],
        cwd=OUT.parents[2],env=env,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    code,killed=wait_bounded(p,5400)
    with (OUT/'watchdog_result.json').open('x',encoding='utf-8') as f:
        json.dump({'exit_code':code,'hard_timeout':killed,'elapsed_seconds':time.monotonic()-started,
                   'restarted':False,'note':'A killed in-flight call may be charged; inspect dispatch/settled ledger and retain its reservation.'},f)
    sys.exit(code if not killed else 124)

if __name__=='__main__':
    main()
