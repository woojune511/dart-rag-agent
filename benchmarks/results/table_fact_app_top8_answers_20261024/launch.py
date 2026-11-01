"""One-shot process watchdog, only new execution process can be terminated."""
from common import *
import time
need(not (OUT/'live').exists(),'Already dispatched; no automatic resume')
env={**os.environ,'APP_TOP8_WATCHDOG':sha(__file__),'PYTHONDONTWRITEBYTECODE':'1'}
with (OUT/'stdout.log').open('xb') as log:
    child=subprocess.Popen([sys.executable,'-B','-X','utf8',str(OUT/'run.py'),'live'],cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT)
    put(OUT/'process.json',{'at':now(),'pid':child.pid,'deadline':'9000seconds from first dispatch'})
    deadline=None
    while child.poll() is None:
        p=OUT/'live/first_dispatch.json'
        if deadline is None and p.exists():
            try:deadline=time.monotonic()+max(0,9000-(time.time()-load(p)['unix']))
            except (OSError,json.JSONDecodeError):pass
        if deadline is not None and time.monotonic()>=deadline:
            subprocess.run(['taskkill','/PID',str(child.pid),'/T','/F'],capture_output=True)
            put(OUT/'watchdog_timeout.json',{'at':now(),'pid':child.pid,'reason':'User time cap'})
            break
        time.sleep(1)
    rc=child.wait()
put(OUT/'process_exit.json',{'at':now(),'exit_code':rc})
print('Execution process exited',rc,flush=True)
raise SystemExit(rc)
