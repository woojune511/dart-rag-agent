"""One-shot bounded provider execution. Runtime and active store are never opened here."""
from common_exec import *
import copy, math, threading, time
from decimal import Decimal

CAP=Decimal('36');MAX_CALLS=105;WALL=9000;MODEL='gpt-6.1-sol';EMODEL='text-embedding-3-large'
URLS={'document':'https://api.openai.com/v1/embeddings','query':'https://api.openai.com/v1/embeddings','answer':'https://api.openai.com/v1/responses'}

def identity_hash(x):return hashlib.sha256(enc(x)).hexdigest()
def schedule_label(row):return f'{row["case_id"]}:{row["arm"]}:r{row["repeat"]}'
def generation_entry(entry,row):
    bound=entry['input_bound'];need(bound<=(98304 if row['arm']=='A' else 229376),'Generation reservation ceiling')
    return {'kind':'answer','label':schedule_label(row),'body':entry['body'],'body_sha256':entry['body_sha256'],
      'input_bound':bound,'reserve':str((Decimal(bound)*Decimal('2.5')+8192*Decimal('10'))/1000000),'row':row}
def embedding_entry(kind,label,texts,tokens):
    need(kind in ('document','query') and isinstance(texts,list) and texts,'Embedding shape')
    bound=tokens+32*len(texts)
    if kind=='query':need(len(texts)==1 and bound<=1024,'Query embedding bound')
    body={'model':EMODEL,'input':texts,'dimensions':3072,'encoding_format':'float'}
    return {'kind':kind,'label':label,'body':body,'body_sha256':identity_hash(body),'input_bound':bound,
      'reserve':str(Decimal(bound)*Decimal('.13')/1000000)}

class Guard:
    def __init__(self,path,manifest,live=False):
        self.path=Path(path);self.path.mkdir(parents=True,exist_ok=False)
        self.manifest=manifest;self.calls=0;self.cost=Decimal(0);self.unsettled=Decimal(0)
        self.started=None;self.closed=False;self.labels=set();self.completed=0;self.counts={k:0 for k in URLS};self.live=live
    def elapsed(self):return 0 if self.started is None else time.monotonic()-self.started
    def validate(self,request,entry):
        need(not self.closed,'Runner closed');need(entry['label'] in self.manifest,'Unplanned request label')
        need(identity_hash(entry['body'])==entry['body_sha256']==self.manifest[entry['label']],'Frozen body drift')
        need(request.method=='POST' and str(request.url)==URLS[entry['kind']] and request.content==enc(entry['body']),'Endpoint/body drift')
        need(self.calls<MAX_CALLS and self.counts[entry['kind']]<{'document':15,'query':18,'answer':72}[entry['kind']],'Call cap')
        need(self.elapsed()<WALL,'Wall cap');need(entry['label'] not in self.labels,'Duplicate dispatch')
        need(self.cost+self.unsettled+Decimal(entry['reserve'])<=CAP,'Cost cap')
        need(not self.unsettled,'Unsettled prior request')
    def send(self,client,entry):
        # Hash all executable sources before any request; no network/SDK fallbacks exist.
        if self.live:check_execution_freeze()
        remaining=WALL-self.elapsed()
        request=client.build_request('POST',URLS[entry['kind']],content=enc(entry['body']),timeout=min(180,remaining))
        self.validate(request,entry)
        if self.started is None:
            self.started=time.monotonic();put(self.path/'first_dispatch.json',{'at':now(),'unix':time.time(),'max_wall_seconds':WALL})
        self.calls+=1;self.counts[entry['kind']]+=1;self.labels.add(entry['label']);self.unsettled=Decimal(entry['reserve'])
        prefix=f'{self.calls:03d}';put(self.path/f'{prefix}_request.json',entry['body'])
        append(self.path/'ledger.jsonl',{'event':'dispatch','at':now(),'attempt':self.calls,'kind':entry['kind'],'label':entry['label'],
          'request_sha256':entry['body_sha256'],'input_bound':entry['input_bound'],'reserved_usd':str(self.unsettled)})
        started=time.monotonic()
        try:
            response=client.send(request);raw_bytes=response.read()
            rawpath=self.path/f'{prefix}_response_raw.bin'
            with rawpath.open('xb') as f:f.write(raw_bytes);f.flush();os.fsync(f.fileno())
            append(self.path/'ledger.jsonl',{'event':'http_result','at':now(),'attempt':self.calls,'http_status':response.status_code,
              'request_id':response.headers.get('x-request-id'),'raw_sha256':sha(rawpath)})
            need(response.status_code==200,'HTTP status '+str(response.status_code))
            raw=response.json();put(self.path/f'{prefix}_response.json',raw)
            cost,usage=self.validate_response(raw,entry)
            need(cost<=self.unsettled,'Observed usage exceeds reserved liability')
            self.cost+=cost;self.unsettled=Decimal(0);self.completed+=1
            seconds=time.monotonic()-started
            append(self.path/'ledger.jsonl',{'event':'settled','at':now(),'attempt':self.calls,'label':entry['label'],'kind':entry['kind'],
              'usage':usage,'estimated_usd':str(cost),'seconds':seconds,'response_model':raw.get('model')})
            if entry['kind']=='answer':
                answer=self.answer(raw,entry)
                append(self.path/'answers.jsonl',{'attempt':self.calls,**entry['row'],**answer,'usage':usage,'seconds':seconds,'estimated_usd':str(cost)})
            return raw
        except BaseException:
            self.closed=True;raise
    def validate_response(self,raw,entry):
        usage=raw.get('usage');need(isinstance(usage,dict),'Missing usage')
        expected=MODEL if entry['kind']=='answer' else EMODEL
        need(raw.get('model')==expected,'Provider model drift')
        if entry['kind']=='answer':
            ip,op=usage.get('input_tokens'),usage.get('output_tokens');details=usage.get('input_tokens_details') or {}
            read,write=details.get('cached_tokens'),details.get('cache_write_tokens')
            need(all(type(v) is int and v>=0 for v in [ip,op,read,write]),'Missing/invalid generation usage')
            need(read+write<=ip and usage.get('total_tokens')==ip+op,'Inconsistent usage')
            need(ip<=entry['input_bound'] and op<=8192,'Token reservation exceeded')
            need(raw.get('service_tier')=='default','Service tier drift')
            need((raw.get('reasoning') or {}).get('effort')=='low','Reasoning drift')
            need(raw.get('status') in ('completed','incomplete'),'Unexpected provider response status')
            return (Decimal(ip-read-write)*2+Decimal(read)*Decimal('.1')+Decimal(write)*Decimal('2.5')+Decimal(op)*10)/1000000,usage
        ip=usage.get('prompt_tokens')
        need(type(ip) is int and 0<ip<=entry['input_bound'] and usage.get('total_tokens')==ip,'Embedding usage mismatch')
        data=raw.get('data');need(isinstance(data,list) and len(data)==len(entry['body']['input']),'Embedding count')
        need({d.get('index') for d in data}==set(range(len(data))),'Embedding indices')
        for d in data:
            v=d.get('embedding');need(isinstance(v,list) and len(v)==3072,'Embedding dimensions')
            need(all(type(x) in (int,float) and math.isfinite(x) for x in v) and any(v),'Invalid embedding vector')
        return Decimal(ip)*Decimal('.13')/1000000,usage
    def answer(self,raw,entry):
        text=''.join(c.get('text','') for o in raw.get('output',[]) for c in o.get('content',[]) if c.get('type')=='output_text')
        answer=None;errors=[]
        if raw.get('status')!='completed':errors.append('incomplete_response')
        try:
            answer=json.loads(text)
            need(isinstance(answer,dict) and set(answer)=={'answer','cited_source_ids','abstained'},'answer_schema')
            need(isinstance(answer['answer'],str) and answer['answer'].strip(),'empty_answer')
            need(type(answer['abstained']) is bool,'abstained_type')
            need(isinstance(answer['cited_source_ids'],list) and all(isinstance(x,str) for x in answer['cited_source_ids']),'citation_type')
            visible={d['source_id'] for d in json.loads(entry['body']['input'][1]['content'])['documents']}
            need(set(answer['cited_source_ids'])<=visible,'unknown_citation')
            need(answer['abstained'] or answer['cited_source_ids'],'missing_citation')
        except Exception as exc:errors.append(type(exc).__name__+': '+str(exc)[:150])
        return {'answer':answer,'raw_text':text,'structural_errors':errors,'provider_status':raw.get('status')}
    def summary(self):return {'attempts':self.calls,'completed_provider_requests':self.completed,'counts':self.counts,
      'usage_estimated_usd':str(self.cost),'unsettled_reserved_usd':str(self.unsettled),'elapsed_seconds':self.elapsed()}

def check_execution_freeze():
    for p,h in load(OUT/'runner_freeze.json')['files'].items():need(sha(OUT/p)==h,'Execution file drift '+p)
    # The full immutable preparation was checked at admission and each local stage.
    for p,h in load(PREP/'freeze.json')['dependencies'].items():need(sha(ROOT/p)==h,'Runtime dependency drift '+p)

def planned_embeddings():
    rows=corpus();bysha={r['text_sha256']:r for r in rows};plan=load(PREP/'embedding_plan.json');entries=[]
    for batch in plan['batches']:
        hashes=batch['text_sha256'];texts=[bysha[h]['text'] for h in hashes]
        need(len(texts)<=256 and batch['tokens']<=250000,'Frozen embedding batch bound')
        need(all(hashlib.sha256(t.encode('utf8')).hexdigest()==h for t,h in zip(texts,hashes)),'Embedding input identity')
        e=embedding_entry('document',f'doc:{batch["index"]}',texts,batch['tokens']);e['hashes']=hashes;entries.append(e)
    os.environ['TIKTOKEN_CACHE_DIR']=str(ROOT/'benchmarks/results/kbf_parser_embedding_admission_2026-09-09/tokenizer_cache')
    import tiktoken
    tokenizer=tiktoken.get_encoding('cl100k_base')
    for q in load(PREP/'questions.json'):
        e=embedding_entry('query',f'query:{q["case_id"]}',[q['question']],len(tokenizer.encode_ordinary(q['question'])));e['case_id']=q['case_id'];entries.append(e)
    need(len(entries)==33,'Embedding schedule cardinality');return entries

def setup():
    p=frozen();put(OUT/'preservation_before.json',p)
    put(OUT/'authorization.json',{'at':now(),'user_words':load(OUT/'ledger_initial.json')['user_words'],
      'preparation_freeze_sha256':sha(PREP/'freeze.json'),'protocol_sha256':sha(PREP/'protocol.json'),
      'max_attempts':105,'max_usd':'36','max_wall_seconds':9000,'retries':0,'execution_authorized':True})
    put(OUT/'pricing_revalidation.json',{'at':now(),'rates_unchanged':True,
      'rates_usd_per_million':{'input':'2','output':'10','cache_read':'.1','cache_write_30m':'2.5','embedding':'.13'},
      'sources':['https://developers.openai.com/api/docs/pricing','https://developers.openai.com/api/docs/guides/prompt-caching'],
      'method':'Official documentation retrieved via OpenAI developer documentation tool before execution; default30m write pricing.'})
    entries=planned_embeddings();put(OUT/'embedding_requests.json',entries)
    print('SETUP PASS:33 embedding requests frozen; paid calls0',flush=True)

def live():
    import httpx,numpy as np
    from dotenv import dotenv_values
    need(os.environ.get('HOLDOUT18_WATCHDOG')==sha(OUT/'launch.py'),'Whole-process watchdog required')
    check_execution_freeze();frozen()
    test=load(OUT/'test_result_final.json')
    need(test['status']=='PASS' and test['run_sha256']==sha(__file__) and test['offline_stage_sha256']==sha(OUT/'offline_stage.py')
      and test['common_sha256']==sha(OUT/'common_exec.py') and load(OUT/'offline_stage_smoke_hydration.json')['status']=='PASS','Offline gates')
    need(load(OUT/'preflight_audit.json')['status']=='PASS','Independent preflight audit')
    put(OUT/'authorization_consumed.json',{'at':now(),'authorization_sha256':sha(OUT/'authorization.json'),'runner_freeze_sha256':sha(OUT/'runner_freeze.json')})
    entries=load(OUT/'embedding_requests.json');manifest={e['label']:e['body_sha256'] for e in entries}
    g=Guard(OUT/'live',manifest,live=True);finished=threading.Event();state={'phase':'document_embedding'};error=None;status='STOPPED'
    def heartbeat():
        while not finished.wait(20):
            record={'at':now(),**state,**g.summary()};append(OUT/'live/heartbeat.jsonl',record);print(json.dumps(record),flush=True)
    threading.Thread(target=heartbeat,daemon=True).start()
    try:
        key=dotenv_values(ROOT/'.env').get('OPENAI_API_KEY');need(isinstance(key,str) and key,'Missing credential')
        with httpx.Client(headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'},
          transport=httpx.HTTPTransport(retries=0),follow_redirects=False,trust_env=False) as client:
            vecs=[];hashes=[];query_vectors={}
            for e in entries:
                state['phase']=e['label'];raw=g.send(client,e)
                vectors=[d['embedding'] for d in sorted(raw['data'],key=lambda d:d['index'])]
                if e['kind']=='document':hashes.extend(e['hashes']);vecs.extend(vectors)
                else:query_vectors[e['case_id']]=vectors[0]
                print(f'{g.calls}/105 {e["label"]}; USD {g.cost}',flush=True)
            need(len(hashes)==3734 and len(query_vectors)==18,'Saved vector cardinality')
            np.save(OUT/'live/document_vectors.npy',np.asarray(vecs,dtype=np.float32),allow_pickle=False)
            put(OUT/'live/vector_manifest.json',{'text_sha256':hashes,'array_sha256':sha(OUT/'live/document_vectors.npy'),'float32':'Chroma native storage representation'})
            put(OUT/'live/query_vectors.json',query_vectors)
            put(OUT/'live/vector_receipts.json',{'files':{n:sha(OUT/'live'/n) for n in ['document_vectors.npy','vector_manifest.json','query_vectors.json']}})
            state['phase']='offline_store_retrieval_packets'
            subprocess.run([sys.executable,'-B','-X','utf8',str(OUT/'offline_stage.py'),'real'],cwd=ROOT,check=True,
              timeout=max(1,WALL-g.elapsed()))
            frozen();check_execution_freeze()
            requests={(e['case_id'],e['arm']):e for e in load(OUT/'requests.json')};schedule=load(PREP/'schedule.json')
            need(len(requests)==36 and len(schedule)==72,'Generation cardinality')
            answer_entries=[generation_entry(requests[r['case_id'],r['arm']],r) for r in schedule]
            need(len({e['label'] for e in answer_entries})==72,'Duplicate generation schedule')
            g.manifest.update({e['label']:e['body_sha256'] for e in answer_entries})
            put(OUT/'generation_freeze.json',{'at':now(),'requests_sha256':sha(OUT/'requests.json'),'schedule_sha256':sha(PREP/'schedule.json'),
              'packet_hashes':{p.name:sha(p) for p in (OUT/'packets').glob('*.json')},'before_answer_calls':g.counts['answer']})
            reserve=sum(Decimal(e['reserve']) for e in answer_entries);need(g.cost+reserve<=CAP,'Aggregate generation reservation')
            for e in answer_entries:
                state['phase']=e['label'];g.send(client,e)
                print(f'{g.calls}/105 {e["label"]}; USD {g.cost}',flush=True)
        need(g.calls==105 and g.counts=={'document':15,'query':18,'answer':72},'Final cardinality')
        frozen();check_execution_freeze()
        status='COMPLETED'
    except BaseException as exc:
        # No credential-bearing URL or headers are included in error messages.
        error={'type':type(exc).__name__,'message':str(exc)[:500]}
    finally:
        finished.set();checks=preserve()
        result={'at':now(),'status':status,'error':error,**g.summary(),'preservation':checks,'app_restarts':0,'external_judge_calls':0,
          'active_store_opened':False,'runtime_source_changes':0,'retries':0}
        put(OUT/'execution_result.json',result)
        put(OUT/'raw_output_seal.json',{'at':now(),'files':{str(p.relative_to(OUT)):sha(p) for p in (OUT/'live').glob('*') if p.is_file()},
          'status':status,'before_semantic_review':True})
        print(json.dumps(result,ensure_ascii=False),flush=True)
    need(status=='COMPLETED' and not checks['changed'] and all(checks['checks'].values()),'Execution stopped; no automatic retry')

if __name__=='__main__':
    if sys.argv[1]=='setup':setup()
    elif sys.argv[1]=='live':live()
    else:raise Stop('Unknown mode')
