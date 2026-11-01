"""Hard whole-process-tree deadline starts at first paid dispatch."""
from common_exec import *
import time
need(not (OUT/'live').exists(),'One-shot execution; no automatic resume')
env={**os.environ,'HOLDOUT18_WATCHDOG':sha(__file__),'PYTHONDONTWRITEBYTECODE':'1'}
with (OUT/'stdout.log').open('xb') as log:
    child=subprocess.Popen([sys.executable,'-B','-X','utf8',str(OUT/'run.py'),'live'],cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT)
    put(OUT/'process.json',{'pid':child.pid,'at':now(),'deadline':'9000s from first_dispatch.json'})
    deadline=None
    while child.poll() is None:
        start=OUT/'live/first_dispatch.json'
        if deadline is None and start.exists():
            try:deadline=time.monotonic()+max(0,9000-(time.time()-load(start)['unix']))
            except (json.JSONDecodeError,OSError):pass  # fsync writer may still be filling the new file
        if deadline is not None and time.monotonic()>=deadline:
            subprocess.run(['taskkill','/PID',str(child.pid),'/T','/F'],capture_output=True)
            put(OUT/'watchdog_timeout.json',{'at':now(),'pid':child.pid,'reason':'User 9000 second cap'})
            break
        time.sleep(1)
    rc=child.wait()
put(OUT/'process_exit.json',{'at':now(),'exit_code':rc})
print('Execution process exited',rc,flush=True)
raise SystemExit(rc)
