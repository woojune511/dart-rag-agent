"""72 exact prepared generation requests; no retrieval/embedding/judge route."""
from common import *
import threading,time
from decimal import Decimal

CAP=Decimal('13.28');MAX_CALLS=72;WALL=9000;TIMEOUT=90
MODEL='gpt-5.6-terra';URL='https://api.openai.com/v1/responses'

def entries():
    reqs={(x['case_id'],x['arm']):x for x in load(PREP/'requests18.json')}
    out=[]
    for row in load(PREP/'schedule72.json'):
        r=reqs[row['case_id'],row['arm']]
        need(digest(r['body'])==r['body_sha256']==row['body_sha256'],'Prepared request hash mismatch')
        need(r['input_bound']==len(enc(r['body']))+4096==row['input_bound'],'Input bound drift')
        need(r['body']['model']==MODEL and r['body']['reasoning']=={'effort':'low'} and r['body']['max_output_tokens']==8192,'Generation drift')
        out.append({'body':r['body'],'body_sha256':r['body_sha256'],'input_bound':r['input_bound'],
                    'reserve':str((Decimal(r['input_bound'])*Decimal('2.5')+8192*Decimal(12))/1000000),
                    'label':f'{row["case_id"]}:{row["arm"]}:r{row["repeat"]}','row':row})
    need(len(out)==len({x['label'] for x in out})==72,'Schedule cardinality')
    need(sum(Decimal(e['reserve']) for e in out)==Decimal('13.270333')<=CAP,'Aggregate reservation changed')
    return out

class Guard:
    def __init__(self,path,manifest,live=False):
        self.path=Path(path);self.path.mkdir(parents=True,exist_ok=False)
        self.manifest=manifest;self.live=live;self.calls=0;self.completed=0
        self.cost=Decimal(0);self.unsettled=Decimal(0);self.started=None;self.closed=False;self.labels=set()
    def elapsed(self):return 0 if self.started is None else time.monotonic()-self.started
    def summary(self):return {'attempts':self.calls,'completed_provider_requests':self.completed,
        'usage_estimated_usd':str(self.cost),'unsettled_reserved_usd':str(self.unsettled),'elapsed_seconds':self.elapsed()}
    def validate(self,request,e):
        need(not self.closed,'Closed runner');need(e['label'] in self.manifest,'Unplanned label')
        need(digest(e['body'])==e['body_sha256']==self.manifest[e['label']],'Body drift')
        need(request.method=='POST' and str(request.url)==URL and request.content==enc(e['body']),'Endpoint/body drift')
        need(self.calls<MAX_CALLS,'Call cap');need(self.elapsed()<WALL,'Wall cap')
        need(e['label'] not in self.labels,'Duplicate dispatch');need(not self.unsettled,'Unsettled prior liability')
        need(self.cost+self.unsettled+Decimal(e['reserve'])<=CAP,'Cost cap')
    def usage(self,raw,e):
        need(raw.get('model')==MODEL,'Response model drift')
        need(raw.get('service_tier')=='default','Response tier drift')
        need((raw.get('reasoning') or {}).get('effort')=='low','Response reasoning drift')
        need(raw.get('status') in ('completed','incomplete'),'Unexpected provider status')
        u=raw.get('usage');need(isinstance(u,dict),'Missing usage')
        ip,op=u.get('input_tokens'),u.get('output_tokens');detail=u.get('input_tokens_details') or {}
        cr,cw=detail.get('cached_tokens'),detail.get('cache_write_tokens')
        need(all(type(v) is int and v>=0 for v in (ip,op,cr,cw)),'Missing/invalid usage fields')
        need(cr+cw<=ip and u.get('total_tokens')==ip+op,'Usage inconsistency')
        need(ip<=e['input_bound'] and op<=8192,'Reservation exceeded')
        cost=(Decimal(ip-cr-cw)*2+Decimal(cr)*Decimal('.2')+Decimal(cw)*Decimal('2.5')+Decimal(op)*12)/1000000
        return cost,u
    def answer(self,raw,e):
        text=''.join(c.get('text','') for o in raw.get('output',[]) for c in o.get('content',[]) if c.get('type')=='output_text')
        answer=None;errors=[]
        if raw.get('status')!='completed':errors.append('incomplete_response')
        try:
            answer=json.loads(text)
            need(isinstance(answer,dict) and set(answer)=={'answer','abstained','cited_source_ids'},'answer_schema')
            need(isinstance(answer['answer'],str) and bool(answer['answer'].strip()),'empty_answer')
            need(type(answer['abstained']) is bool,'abstained_type')
            need(isinstance(answer['cited_source_ids'],list) and all(isinstance(x,str) for x in answer['cited_source_ids']),'citation_type')
            visible={d['source_id'] for d in json.loads(e['body']['input'][1]['content'])['documents']}
            need(set(answer['cited_source_ids'])<=visible,'unknown_citation')
            need(answer['abstained'] or answer['cited_source_ids'],'missing_citation')
        except Exception as exc:errors.append(type(exc).__name__+': '+str(exc)[:180])
        return {'answer':answer,'raw_text':text,'structural_errors':errors,'provider_status':raw.get('status')}
    def send(self,client,e):
        if self.live:runner_frozen()
        request=client.build_request('POST',URL,content=enc(e['body']),timeout=min(TIMEOUT,max(.1,WALL-self.elapsed())))
        self.validate(request,e)
        if self.started is None:
            self.started=time.monotonic();put(self.path/'first_dispatch.json',{'at':now(),'unix':time.time(),'wall_seconds':WALL})
        self.calls+=1;self.labels.add(e['label']);self.unsettled=Decimal(e['reserve']);n=f'{self.calls:03d}'
        put(self.path/f'{n}_request.json',e['body'])
        append(self.path/'ledger.jsonl',{'event':'dispatch','at':now(),'attempt':self.calls,'label':e['label'],
            'request_sha256':e['body_sha256'],'input_bound':e['input_bound'],'reserved_usd':str(self.unsettled)})
        started=time.monotonic()
        try:
            response=client.send(request);rawbytes=response.read()
            p=self.path/f'{n}_response_raw.bin'
            with p.open('xb') as f:f.write(rawbytes);f.flush();os.fsync(f.fileno())
            append(self.path/'ledger.jsonl',{'event':'http_result','at':now(),'attempt':self.calls,
                'http_status':response.status_code,'request_id':response.headers.get('x-request-id'),'raw_sha256':sha(p)})
            need(response.status_code==200,'HTTP status '+str(response.status_code))
            raw=response.json();put(self.path/f'{n}_response.json',raw)
            cost,usage=self.usage(raw,e);need(cost<=self.unsettled,'Actual cost exceeds reserved liability')
            self.cost+=cost;self.unsettled=Decimal(0);self.completed+=1
            seconds=time.monotonic()-started
            append(self.path/'ledger.jsonl',{'event':'settled','at':now(),'attempt':self.calls,'label':e['label'],
                'usage':usage,'estimated_usd':str(cost),'seconds':seconds,'response_model':raw.get('model')})
            append(self.path/'answers.jsonl',{'attempt':self.calls,**e['row'],**self.answer(raw,e),
                'usage':usage,'estimated_usd':str(cost),'seconds':seconds})
            return raw
        except BaseException:
            self.closed=True;raise

def setup():
    check=frozen();planned=entries();put(OUT/'preservation_before.json',check)
    put(OUT/'authorization.json',{'at':now(),'user_words':load(OUT/'ledger_initial.json')['user_words'],
        'accepted_plan':'Prior response offered72 calls,USD13.28,9000seconds. User accepted experiment execution.',
        'preparation_freeze_sha256':sha(PREP/'freeze.json'),'request_file_sha256':sha(PREP/'requests18.json'),
        'max_attempts':72,'cap_usd':'13.28','wall_seconds':9000,'retries':0,
        'provider':'OpenAI Responses API','model':MODEL,'content':'Frozen user questions and public DART report evidence packets only',
        'paid_execution_authorized':True})
    put(OUT/'planned_entries.json',planned)
    print('SETUP PASS:72 generation calls planned; no execution or provider probe',flush=True)

def live():
    import httpx
    from dotenv import dotenv_values
    need(os.environ.get('APP_TOP8_WATCHDOG')==sha(OUT/'launch.py'),'Whole-process watchdog required')
    frozen();runner_frozen()
    test=load(OUT/'guard_tests.json');need(test['status']=='PASS' and test['run_sha256']==sha(__file__),'Offline guard tests stale')
    need(load(OUT/'preflight_audit.json')['status']=='PASS','Preflight review required')
    need(load(OUT/'authorization.json')['paid_execution_authorized'],'Missing execution authority')
    put(OUT/'authorization_consumed.json',{'at':now(),'authorization_sha256':sha(OUT/'authorization.json'),'runner_freeze_sha256':sha(OUT/'runner_freeze.json')})
    planned=load(OUT/'planned_entries.json');need(planned==entries(),'Plan drift')
    g=Guard(OUT/'live',{e['label']:e['body_sha256'] for e in planned},live=True)
    finished=threading.Event();state={'phase':'initializing'};status='STOPPED';error=None
    def heartbeat():
        while not finished.wait(20):
            r={'at':now(),**state,**g.summary()};append(OUT/'live/heartbeat.jsonl',r);print(json.dumps(r),flush=True)
    threading.Thread(target=heartbeat,daemon=True).start()
    try:
        key=dotenv_values(ROOT/'.env').get('OPENAI_API_KEY');need(isinstance(key,str) and key,'Missing credential')
        with httpx.Client(headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'},
                          transport=httpx.HTTPTransport(retries=0),follow_redirects=False,trust_env=False) as client:
            for e in planned:
                state['phase']=e['label'];g.send(client,e)
                print(f'{g.calls}/72 {e["label"]}; USD {g.cost}',flush=True)
        need(g.calls==g.completed==72,'Final cardinality')
        frozen();runner_frozen();status='COMPLETED'
    except BaseException as exc:
        error={'type':type(exc).__name__,'message':str(exc)[:400]}
    finally:
        finished.set();check=preserve()
        result={'at':now(),'status':status,'error':error,**g.summary(),'preservation':check,
                'embedding_calls':0,'real_searches':0,'external_judge_calls':0,'app_restarts':0,'retries':0}
        put(OUT/'execution_result.json',result)
        put(OUT/'raw_output_seal.json',{'at':now(),'files':{p.relative_to(OUT).as_posix():sha(p) for p in (OUT/'live').glob('*') if p.is_file()},
                                    'status':status,'before_semantic_review':True})
        print(json.dumps(result,ensure_ascii=False),flush=True)
    need(status=='COMPLETED' and not check['changed'] and all(check['checks'].values()),'Stopped; no automatic retry')

if __name__=='__main__':
    if sys.argv[1]=='setup':setup()
    elif sys.argv[1]=='live':live()
    else:raise Stop('Unknown command')
