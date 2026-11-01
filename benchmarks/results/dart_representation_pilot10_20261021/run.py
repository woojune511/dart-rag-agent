"""Frozen, bounded two-arm pilot. First error stops; there is no resume mode."""
from common import *
from decimal import Decimal
from urllib.parse import quote
import gzip, threading, time
os.environ['TIKTOKEN_CACHE_DIR']=str(ROOT/'benchmarks/results/full77_v12_final_20261018/tokenizer_cache')
CAP=Decimal('3')

def enc(x):return json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def append(path,x):
    with Path(path).open('a',encoding='utf-8',newline='\n') as f:f.write(enc(x).decode()+'\n')
def event(stage,**kw):
    row={'time':now(),'stage':stage,**kw};append(BASE/'heartbeat.jsonl',row);print(enc(row).decode(),flush=True)
def rows(path):
    with gzip.open(path,'rt',encoding='utf-8') as f:return [json.loads(x) for x in f]
def body(packet):
    from src.config.simple_rag import ANSWER_INSTRUCTIONS,RagAnswer
    return {'model':'gpt-6.1-sol','input':[{'role':'system','content':ANSWER_INSTRUCTIONS},{'role':'user','content':enc(packet).decode()}],
            'max_output_tokens':8192,'reasoning':{'effort':'low'},'service_tier':'default','store':False,'stream':False,
            'text':{'format':{'type':'json_schema','name':'RagAnswer','strict':True,'schema':RagAnswer.model_json_schema()}}}
def verify():
    for path,digest in load(BASE/'freeze.json')['files'].items():assert sha(path)==digest,'Frozen dependency changed: '+path
def usage_cost(stage,response):
    u=response['usage']
    if stage=='embedding':
        assert u['prompt_tokens']==u['total_tokens'] and u['prompt_tokens']>0
        return Decimal(u['prompt_tokens'])*Decimal('.13')/1000000
    n,o=u['input_tokens'],u['output_tokens'];d=u.get('input_tokens_details') or {}
    c,w=d.get('cached_tokens',0),d.get('cache_write_tokens',0)
    assert 0<=c+w<=n<272000 and o>=0
    return (Decimal(n-c-w)*2+Decimal(c)*Decimal('.1')+Decimal(w)*Decimal('2.5')+Decimal(o)*10)/1000000

class Runner:
    def __init__(self):
        self.cost=Decimal(0);self.calls=0;self.answers=0;self.active='initializing';self.halt=threading.Event();self.start=time.monotonic()
    def heartbeat(self):
        while not self.halt.wait(15):event('HEARTBEAT',active=self.active,calls=self.calls,answers=self.answers,usd=str(self.cost),seconds=round(time.monotonic()-self.start))
    def post(self,cid,stage,request):
        import httpx
        from dotenv import dotenv_values
        verify()
        assert not (BASE/'stopped.json').exists() and time.monotonic()-self.start<7200
        assert self.calls<load(BASE/'preflight.json')['max_provider_calls']
        if stage=='embedding':reserve=Decimal(sum(len(x.encode('utf-8')) for x in request['input']))*Decimal('.13')/1000000
        else:
            assert self.answers<40
            # UTF-8 byte count bounds BPE text tokens; schema/wire framing cushion.
            reserve=Decimal(len(enc(request))+2048)*5/1000000+Decimal(request['max_output_tokens'])*15/1000000
        assert self.cost+reserve<=CAP,'Budget admission refused'
        directory=BASE/'live'/cid;self.active=cid
        write(directory/(stage+'.request.json'),request)
        write(directory/(stage+'.consumed.json'),{'at':now(),'request_sha256':hashlib.sha256(enc(request)).hexdigest(),'reserve_usd':str(reserve),'retries':0})
        self.calls+=1
        if stage=='answer':self.answers+=1
        event('DISPATCH',id=cid,kind=stage,call=self.calls,answers=self.answers,reserve_usd=str(reserve))
        key=os.getenv('OPENAI_API_KEY') or dotenv_values(ROOT/'.env').get('OPENAI_API_KEY')
        assert key,'Provider key missing'
        start=time.monotonic()
        try:
            with httpx.Client(transport=httpx.HTTPTransport(retries=0),timeout=240,follow_redirects=False) as client:
                response=client.post('https://api.openai.com/v1/'+('embeddings' if stage=='embedding' else 'responses'),headers={'Authorization':'Bearer '+key},json=request)
        except httpx.HTTPError:
            raise RuntimeError('Provider transport failure; sensitive URL and headers withheld; no retry') from None
        write(directory/(stage+'.http.json'),{'status':response.status_code,'seconds':time.monotonic()-start,'request_id':response.headers.get('x-request-id')})
        assert response.status_code==200,f'HTTP {response.status_code}; no retry'
        raw=response.json();write(directory/(stage+'.raw.json'),raw)
        usd=usage_cost(stage,raw)
        assert usd<=reserve and self.cost+usd<=CAP,'Usage exceeded reservation'
        self.cost+=usd
        append(BASE/'ledger.jsonl',{'id':cid,'stage':stage,'usage':raw['usage'],'usd':str(usd),'seconds':time.monotonic()-start,'model':raw.get('model')})
        if stage=='embedding':return raw
        assert raw['status']=='completed' and not raw.get('error'),'Incomplete response'
        values=[c['text'] for m in raw['output'] if m['type']=='message' for c in m['content'] if c['type']=='output_text']
        assert len(values)==1
        from src.config.simple_rag import RagAnswer
        value=RagAnswer.model_validate_json(values[0]).model_dump()
        packet=json.loads(request['input'][1]['content']);ids={x['source_id'] for x in packet['documents']}
        assert set(value['cited_source_ids'])<=ids and (value['abstained'] or value['cited_source_ids'])
        write(directory/(stage+'.value.json'),value)
        return value

def freeze():
    import tiktoken
    encoding=tiktoken.get_encoding('cl100k_base')
    assert not (BASE/'freeze.json').exists()
    gold=load(BASE/'rubric.json');questions=load(BASE/'question_seed.json')
    assert {x['id'] for x in gold['questions']}=={x['id'] for x in questions} and len(questions)==10
    corpora=load(BASE/'corpus_manifest.json')['corpora'];batches=[]
    for corpus in corpora:
        data=rows(corpus['path']);batch=[];nt=0
        for i,row in enumerate(data):
            if batch and (len(batch)>=64 or nt+row['tokens']>100000):batches.append({'corpus':corpus['path'],'indices':batch});batch=[];nt=0
            batch.append(i);nt+=row['tokens']
        if batch:batches.append({'corpus':corpus['path'],'indices':batch})
    embed_tokens=sum(x['tokens'] for c in corpora for x in rows(c['path']))+sum(len(encoding.encode(q['query'])) for q in questions)
    write(BASE/'preflight.json',{'batches':batches,'embedding_calls':len(batches)+1,'max_provider_calls':len(batches)+1+40,'embedding_tokens_local':embed_tokens,'estimated_embedding_usd':str(Decimal(embed_tokens)*Decimal('.13')/1000000),'max_answers':40,'cap_usd':str(CAP),'paid_calls_so_far':0,'tokenizer':'cl100k_base shared proxy cap, actual provider usage recorded'})
    paths=list(ROOT.glob('src/**/*.py'))+list(ROOT.glob('src/config/schemas/*'))+list(BASE.glob('*.py'))+list(BASE.glob('*.json'))+list(BASE.glob('*.gz'))+list(BASE.glob('sources/**/*'))+[ROOT/'pyproject.toml']
    files={str(p.resolve()):sha(p) for p in paths if p.is_file()}
    write(BASE/'freeze.json',{'created_at':now(),'files':files,'source_revision':'local v12, HEAD plus frozen dirty/untracked files','source_selection_note':'Nongshim 2025 source already used; Samsung Electro-Mechanics no prior report receipt found in searched manifests/datasets. Not a wholly new holdout.'})
    verify();event('FROZEN',files=len(files),embedding_calls=len(batches)+1,embedding_usd=str(Decimal(embed_tokens)*Decimal('.13')/1000000))

def run():
    import numpy as np,tiktoken
    from rank_bm25 import BM25Okapi
    from src.storage.bm25_index import tokenize_ko
    assert not (BASE/'execution_started.json').exists(),'No automatic rerun or resume'
    verify();write(BASE/'execution_started.json',{'time':now(),'freeze_sha256':sha(BASE/'freeze.json')})
    runner=Runner();threading.Thread(target=runner.heartbeat,daemon=True).start()
    try:
        plan=load(BASE/'preflight.json');corpora=load(BASE/'corpus_manifest.json')['corpora'];questions=load(BASE/'question_seed.json')
        data={c['path']:rows(c['path']) for c in corpora};vectors={p:[] for p in data}
        for bi,b in enumerate(plan['batches']):
            request={'model':'text-embedding-3-large','dimensions':3072,'encoding_format':'float','input':[data[b['corpus']][i]['text'] for i in b['indices']]}
            raw=runner.post(f'emb_{bi:03d}','embedding',request)
            assert [x['index'] for x in raw['data']]==list(range(len(b['indices'])))
            vectors[b['corpus']].extend(x['embedding'] for x in raw['data'])
        raw=runner.post('queries','embedding',{'model':'text-embedding-3-large','dimensions':3072,'encoding_format':'float','input':[q['query'] for q in questions]})
        assert [x['index'] for x in raw['data']]==list(range(10))
        qvectors=np.array([x['embedding'] for x in raw['data']],dtype=np.float32)
        encoder=tiktoken.get_encoding('cl100k_base');packets={};retrieval=[]
        for c in corpora:
            p=c['path'];ds=data[p];v=np.array(vectors[p],dtype=np.float32)
            assert v.shape==(len(ds),3072) and np.isfinite(v).all()
            np.save(BASE/f'{c["arm"]}_{c["rcept_no"]}.npy',v)
            bm=BM25Okapi([tokenize_ko(x['text']) for x in ds])
            for qi,q in enumerate(questions):
                if q['company']!=c['company']:continue
                start=time.monotonic();dist=np.sum((v-qvectors[qi])**2,axis=1)
                dense=sorted(range(len(ds)),key=lambda i:(float(dist[i]),i))[:24]
                scores=bm.get_scores(tokenize_ko(q['query']))
                lexical=[i for i in sorted(range(len(ds)),key=lambda i:(-float(scores[i]),i))[:24] if scores[i]>0]
                rrf={}
                for order in (dense,lexical):
                    for rank,i in enumerate(order,1):rrf[i]=rrf.get(i,0)+1/(60+rank)
                selected=sorted(rrf,key=lambda i:rrf[i],reverse=True)[:12]
                packet={'query':q['query'],'report_scope':{'rcept_no':c['rcept_no']},'documents':[]};omitted=[]
                for i in selected:
                    row=ds[i];rid=c['rcept_no'];uid=row['id']
                    item={'source_id':quote(rid,safe='')+':'+quote(uid,safe=''),'document_id':rid,'chunk_id':uid,'text':row['text'],'context':{k:x for k,x in row['metadata'].items() if k not in ('chunk_uid','chunk_id')}}
                    proposal={**packet,'documents':packet['documents']+[item]}
                    n=len(encoder.encode(enc(body(proposal)).decode(),disallowed_special=()))
                    if len(enc(proposal))>65536 or n>12000:omitted.append({'id':uid,'reason':'byte_or_token_limit'});continue
                    packet=proposal
                assert packet['documents']
                packets[(q['id'],c['arm'])]=packet
                trace={'id':q['id'],'arm':c['arm'],'dense':[{'id':ds[i]['id'],'distance':float(dist[i])} for i in dense],
                       'bm25':[{'id':ds[i]['id'],'score':float(scores[i])} for i in lexical],'rrf_top12':[{'id':ds[i]['id'],'score':rrf[i]} for i in selected],
                       'selected':[x['chunk_id'] for x in packet['documents']],'omitted':omitted,'packet_bytes':len(enc(packet)),
                       'request_proxy_tokens':len(encoder.encode(enc(body(packet)).decode(),disallowed_special=())),'retrieval_seconds':time.monotonic()-start}
                retrieval.append(trace);write(BASE/'packets'/f'{q["id"]}_{c["arm"]}.json',packet)
        write(BASE/'retrieval.json',retrieval)
        write(BASE/'packets_seal.json',{str(p):sha(p) for p in (BASE/'packets').glob('*.json')})
        for q in questions:
            for repeat,arms in [(1,('generic','dart')),(2,('dart','generic'))]:
                for arm in arms:
                    cid=f'{q["id"]}_{arm}_r{repeat}';packet=packets[(q['id'],arm)]
                    runner.post(cid,'answer',body(packet))
                    event('ANSWER_COMPLETE',id=cid,answers=runner.answers,usd=str(runner.cost))
        verify();assert runner.answers==40
        write(BASE/'execution_complete.json',{'time':now(),'answers':runner.answers,'provider_calls':runner.calls,'usd':str(runner.cost),'seconds':time.monotonic()-runner.start})
        write(BASE/'raw_seal.json',{str(p):sha(p) for p in (BASE/'live').rglob('*') if p.is_file()})
        event('COMPLETE',answers=runner.answers,usd=str(runner.cost))
    except BaseException as e:
        write(BASE/'stopped.json',{'time':now(),'type':type(e).__name__,'message':str(e),'active':runner.active,'calls':runner.calls,'answers_attempted':runner.answers,'known_usage_usd':str(runner.cost),'no_retry':True});raise
    finally:runner.halt.set()

if __name__=='__main__':
    if sys.argv[1]=='freeze':
        with offline():freeze()
    elif sys.argv[1]=='run':run()
    else:raise ValueError('Expected freeze or run')
