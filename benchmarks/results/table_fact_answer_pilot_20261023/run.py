"""Isolated, frozen-packet generation pilot. Never imports runtime or opens a store."""
from __future__ import annotations
import copy
import hashlib
import itertools
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from decimal import Decimal

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
OLD = ROOT / 'benchmarks/results/full77_sol_top12_20261020'
FCT = ROOT / 'benchmarks/results/table_fact_units_offline_20261023'
BUD = ROOT / 'benchmarks/results/table_fact_budget77_offline_20261023'
MODEL = 'gpt-6.1-sol'
CAP = Decimal('20')
WALL = 5400
MAX_CALLS = 72
URL = 'https://api.openai.com/v1/responses'
IDS = ['HYU_T3_072','MIX_T3_063','KAK_T3_055','SKI_T1_068','SAM_T1_001','MIX_T2_047',
       'POS_T1_057','SKH_T1_060','MIX_T3_048','CEL_T3_040','SAM_T4_029','HYU_T4_079']

class Stop(RuntimeError):
    pass

def need(ok, message):
    if not ok:
        raise Stop(message)

def now():
    return datetime.now(timezone.utc).isoformat()

def enc(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')

def load(path):
    return json.loads(Path(path).read_text('utf-8'))

def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda: f.read(2**20), b''):
            h.update(b)
    return h.hexdigest()

def put(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as f:
        f.write(enc(value) + b'\n')
        f.flush()
        os.fsync(f.fileno())

def append(path, value):
    with Path(path).open('ab') as f:
        f.write(enc(value) + b'\n')
        f.flush()
        os.fsync(f.fileno())

def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT, env={**os.environ,'GIT_OPTIONAL_LOCKS':'0'}).decode('utf-8')

def git_state():
    return {'head':git('rev-parse','HEAD').strip(), 'index':sha(ROOT/'.git/index'),
            'status':git('status','--short'), 'staged_diff':git('diff','--cached','--name-only')}

def snapshot():
    previous = load(BUD/'before.json')['files']
    for rel, item in previous.items():
        need(sha(ROOT/rel) == item['sha256'], 'Prior protected file drift: '+rel)
    paths = set(previous)
    for folder in (BUD, FCT):
        paths.update(p.relative_to(ROOT).as_posix() for p in folder.rglob('*') if p.is_file())
    paths.update(p for p in git('ls-files','-z').split('\0') if p)
    paths.update(p for p in git('ls-files','--others','--exclude-standard','-z').split('\0') if p)
    files = {p:{'sha256':sha(ROOT/p), 'bytes':(ROOT/p).stat().st_size} for p in sorted(paths) if (ROOT/p).is_file()}
    put(OUT/'before.json', {'at':now(), 'files':files, **git_state()})
    return len(files)

def preserve():
    b = load(OUT/'before.json')
    changed = [p for p,v in b['files'].items() if not (ROOT/p).is_file() or sha(ROOT/p)!=v['sha256']]
    g = git_state()
    return {'at':now(), 'protected_files':len(b['files']), 'changed':changed,
            'git_equal':{k:g[k]==b[k] for k in g}, 'env_unchanged':'.env' not in changed,
            'active_store_opened':False, 'store_check':'Raw file byte hashes; no SQLite client opened.'}

def reservation(body):
    # UTF-8 bytes bound visible byte-level tokenization, plus 4096 for protocol/schema overhead.
    # No network tokenizer call. Observed input above this reservation is a hard stop.
    bound = len(enc(body)) + 4096
    need(bound < 272000, 'Long-context tariff not authorized')
    return bound, Decimal(bound)*Decimal('2.5')/1000000 + Decimal(8192)*Decimal('10')/1000000

def prepare():
    count = snapshot()
    requests = {r['case_id']:r['body'] for r in load(OLD/'requests.json')}
    contract = {r['case_id']:r for r in load(BUD/'evaluation_contract.json')['cases']}
    entries, parity = [], []
    nonpacket = None
    for cid in IDS:
        original = requests[cid]
        base = copy.deepcopy(original)
        base['input'][1]['content'] = '<PACKET>'
        if nonpacket is None:
            nonpacket = base
        need(base == nonpacket, 'Non-packet settings vary by question')
        a = load(FCT/'packets'/f'{cid}_A12.json')
        need(json.loads(original['input'][1]['content'])==a, 'Original packet mismatch '+cid)
        for arm, path in [('A',FCT/'packets'/f'{cid}_A12.json'),
                          ('B',BUD/'packets'/f'{cid}_64KiB.json'),
                          ('C',BUD/'packets'/f'{cid}_160KiB.json')]:
            packet = load(path)
            need(packet['query']==a['query']==contract[cid]['question'], 'Question mismatch')
            need(packet['report_scope']==a['report_scope'], 'Scope mismatch')
            need(len(packet['documents'])==len(a['documents']), 'Document count changed')
            for old_doc,new_doc in zip(a['documents'],packet['documents']):
                need(all(new_doc.get(k)==v for k,v in old_doc.items()), 'Original source field changed')
                need(set(new_doc)-set(old_doc) <= {'table_fact_units'}, 'Unexpected packet attachment')
            body = copy.deepcopy(original)
            if arm != 'A':
                body['input'][1]['content'] = enc(packet).decode('utf-8')
            bound, reserve = reservation(body)
            entries.append({'case_id':cid,'arm':arm,'group':contract[cid]['group'],
                'packet_path':path.relative_to(ROOT).as_posix(),'packet_sha256':sha(path),
                'packet_bytes':len(enc(packet)),'body':body,'body_sha256':hashlib.sha256(enc(body)).hexdigest(),
                'input_token_bound':bound,'reservation_usd':str(reserve)})
            parity.append({'case_id':cid,'arm':arm,'original_sources_preserved':True,'nonpacket_parity':True})
    permutations = list(itertools.permutations('ABC'))
    schedule=[]
    for rep in (1,2):
        for i,cid in enumerate(IDS):
            order = permutations[i % 6]
            if rep==2:
                order = tuple(reversed(order))
            for arm in order:
                schedule.append({'case_id':cid,'arm':arm,'repetition':rep,'label':f'{cid}:{arm}:r{rep}'})
    put(OUT/'requests.json', entries)
    put(OUT/'schedule.json', schedule)
    put(OUT/'parity.json', parity)
    selected=[contract[cid] for cid in IDS]
    put(OUT/'evaluation_contract.json', {'cases':selected, 'source':str(BUD/'evaluation_contract.json'),
        'source_sha256':sha(BUD/'evaluation_contract.json'), 'rule':'Existing factual and refusal criteria are not changed. Historical grades are references, not new baseline outcomes.'})
    rates={'input':'2','cache_read':'0.1','cache_write_30m':'2.5','output':'10'}
    total_reserve=sum(Decimal(x['reservation_usd'])*2 for x in entries)
    need(total_reserve<=CAP, 'All saturated reservations exceed budget')
    put(OUT/'pricing.json', {'at':now(),'sources':[
        'https://developers.openai.com/api/docs/pricing',
        'https://developers.openai.com/api/docs/models/gpt-6.1-sol',
        'https://developers.openai.com/api/docs/guides/prompt-caching#summary-of-model-differences'],
        'rates_usd_per_million':rates,'cache_ttl':'30m API default; request has no override',
        'expected_usd_range':[3,5], 'expected_is_not_guaranteed':True,
        'all_saturated_reservations_usd':str(total_reserve), 'cap_usd':str(CAP),
        'reservation_rule':'UTF-8 request bytes +4096 input tokens, all charged at cache-write rate; output8192. Guard actual usage and next dispatch.'})
    put(OUT/'protocol.json', {'at':now(),'status':'PRE_REGISTERED_BEFORE_NEW_GENERATION',
        'user_words':'[$academic-research-suite](C:\\Users\\geonj\\.codex\\skills\\academic-research-suite\\SKILL.md) 그럼 실제 답변 비교 실험을 수행해줘',
        'case_ids':IDS,'arms':{'A':'Original A12 packet','B':'Verified fact-unit packet64KiB','C':'Same fact-unit packet160KiB'},
        'repetitions':2,'max_http_attempts':MAX_CALLS,'retries':0,'cap_usd':str(CAP),'max_wall_seconds':WALL,
        'model':MODEL,'fixed_generation':nonpacket,'candidate_selection':'Saved candidates, rank/order, final12 and original delivered document window fixed; no refill.',
        'interventions':'A-to-B changes evidence representation/attachment; B-to-C changes only saved context budget. A-to-C is combined effect.',
        'order':'All6 arm permutations used twice across12 cases; second repetition reverses each case order; all fresh generation.',
        'primary':'8 common-answerable cases,2 repetitions per arm. Complete = correctness PASS AND completeness PASS AND support PASS.',
        'separate_groups':'2 preexisting HOLD cases diagnostic only;2 refusal controls reported separately.',
        'grading':'Frozen rubric; grade each answer against supplied and cited evidence. Missing facts remain incomplete even if refusal is prudent. ID validity alone does not establish support.',
        'failed_generation':'No answer-based retries. Malformed/unknown-citation answers retained as failures. Provider/usage/config errors stop the run, with charges recorded when known.',
        'review':'Seal raw outputs before masked first review; hide arm, repetition, peer outcomes. Context size can reveal condition; assistant review is not independent human validation.',
        'interpretation':'Paired descriptive counts only;12 deliberately selected development-exposed cases and2 repetitions do not establish general superiority.',
        'external_calls':'Only72 Responses generations. No embedding, search, judge or provider probes.',
        'implementation':'Experimental files only; no app restart, runtime/config/store changes, commits or pushes.'})
    put(OUT/'preparation.json',{'at':now(),'protected_files':count,'entries':len(entries),'scheduled_calls':len(schedule),
        'all_saturated_reservations_usd':str(total_reserve),'external_calls':0,'active_store_opened':False})
    print('PREPARED',len(schedule),'calls; reservation',total_reserve,'USD;',count,'protected files',flush=True)

class Runner:
    def __init__(self,directory):
        self.directory=Path(directory)
        self.directory.mkdir(parents=True,exist_ok=False)
        self.calls=0
        self.cost=Decimal(0)
        self.reserved_unsettled=Decimal(0)
        self.started=time.monotonic()
        self.closed=False
        self.labels=set()
        self.completed=0

    def validate(self, req, entry, row):
        need(not self.closed,'Runner closed')
        need(req.method=='POST' and str(req.url)==URL,'Unauthorized endpoint')
        need(req.content==enc(entry['body']),'Frozen body drift')
        need(hashlib.sha256(req.content).hexdigest()==entry['body_sha256'],'Body hash drift')
        need(self.calls<MAX_CALLS,'Call limit')
        need(time.monotonic()-self.started<WALL,'Wall time limit')
        need(row['label'] not in self.labels,'Duplicate dispatch')
        need(self.cost+self.reserved_unsettled+Decimal(entry['reservation_usd'])<=CAP,'Cost limit')
        need(entry['input_token_bound']<272000,'Input reservation limit')

    def send(self,client,entry,row):
        req=client.build_request('POST',URL,content=enc(entry['body']))
        self.validate(req,entry,row)
        self.calls+=1
        self.labels.add(row['label'])
        self.reserved_unsettled=Decimal(entry['reservation_usd'])
        prefix=f'{self.calls:03d}'
        put(self.directory/f'{prefix}_request.json',entry['body'])
        append(self.directory/'ledger.jsonl',{'event':'dispatch','at':now(),'attempt':self.calls,**row,
            'request_sha256':entry['body_sha256'],'reserved_usd':str(self.reserved_unsettled)})
        t=time.monotonic()
        try:
            response=client.send(req)
            response.read()
            append(self.directory/'ledger.jsonl',{'event':'http_result','at':now(),'attempt':self.calls,
                'http_status':response.status_code,'request_id':response.headers.get('x-request-id')})
            raw=response.json()
            put(self.directory/f'{prefix}_response.json',raw)
            need(response.status_code==200,'HTTP status '+str(response.status_code))
            usage=raw.get('usage')
            need(isinstance(usage,dict),'Missing usage')
            ip,op=usage.get('input_tokens'),usage.get('output_tokens')
            details=usage.get('input_tokens_details') or {}
            read,write=details.get('cached_tokens'),details.get('cache_write_tokens')
            need(all(type(v) is int and v>=0 for v in (ip,op,read,write)), 'Missing/invalid token breakdown')
            need(read+write<=ip,'Inconsistent input usage')
            cost=(Decimal(ip-read-write)*2+Decimal(read)*Decimal('.1')+Decimal(write)*Decimal('2.5')+Decimal(op)*10)/1000000
            self.cost+=cost
            self.reserved_unsettled=Decimal(0)
            elapsed=time.monotonic()-t
            append(self.directory/'ledger.jsonl',{'event':'settled','at':now(),'attempt':self.calls,**row,
                'usage':usage,'estimated_usd':str(cost),'seconds':elapsed,'response_model':raw.get('model')})
            need(ip<=entry['input_token_bound'] and op<=8192,'Token reservation exceeded')
            need(self.cost<=CAP,'Cost exceeded')
            need(raw.get('model')==MODEL,'Provider model drift')
            need(raw.get('service_tier')=='default','Service tier drift')
            need((raw.get('reasoning') or {}).get('effort')=='low','Reasoning drift')
            need(raw.get('status')=='completed','Incomplete provider response')
            text=''.join(c.get('text','') for o in raw.get('output',[]) for c in o.get('content',[]) if c.get('type')=='output_text')
            answer=None
            structural_error=None
            try:
                answer=json.loads(text)
                need(set(answer)=={'answer','cited_source_ids','abstained'},'Unexpected answer schema')
                need(isinstance(answer['answer'],str) and answer['answer'].strip(),'Empty answer')
                need(type(answer['abstained']) is bool,'Invalid abstention')
                need(isinstance(answer['cited_source_ids'],list) and all(isinstance(s,str) for s in answer['cited_source_ids']),'Invalid citations')
            except Exception as exc:
                structural_error=type(exc).__name__+': '+str(exc)[:200]
            valid_sources={d['source_id'] for d in json.loads(entry['body']['input'][1]['content'])['documents']}
            cited=answer.get('cited_source_ids',[]) if isinstance(answer,dict) else []
            unknown=[s for s in cited if isinstance(s,str) and s not in valid_sources] if isinstance(cited,list) else []
            append(self.directory/'answers.jsonl',{'at':now(),'attempt':self.calls,**row,'answer':answer,'raw_text':text,
                'structural_error':structural_error,'unknown_citations':unknown,'seconds':elapsed,'usage':usage,'estimated_usd':str(cost)})
            self.completed+=1
        except BaseException:
            self.closed=True
            raise

    def summary(self):
        return {'attempts':self.calls,'completed':self.completed,'estimated_usd':str(self.cost),
                'unsettled_reservation_usd':str(self.reserved_unsettled),'elapsed_seconds':time.monotonic()-self.started}

def offline():
    import httpx
    entries={(r['case_id'],r['arm']):r for r in load(OUT/'requests.json')}
    schedule=load(OUT/'schedule.json')
    need(len(schedule)==72 and len({r['label'] for r in schedule})==72,'Invalid schedule')
    def mock(req):
        b=json.loads(req.content)
        pkt=json.loads(b['input'][1]['content'])
        result={'answer':'offline fixture','abstained':True,'cited_source_ids':[pkt['documents'][0]['source_id']]}
        return httpx.Response(200,json={'model':MODEL,'service_tier':'default','reasoning':{'effort':'low'},'status':'completed',
            'usage':{'input_tokens':100,'output_tokens':10,'total_tokens':110,'input_tokens_details':{'cached_tokens':0,'cache_write_tokens':97},'output_tokens_details':{'reasoning_tokens':0}},
            'output':[{'type':'message','content':[{'type':'output_text','text':enc(result).decode()}]}]},request=req)
    g=Runner(OUT/'offline')
    with httpx.Client(transport=httpx.MockTransport(mock)) as client:
        for row in schedule:
            g.send(client,entries[row['case_id'],row['arm']],row)
    tests=[]
    def rejects(name,fn):
        try:fn()
        except Stop:tests.append(name)
        else:raise Stop('Negative control admitted: '+name)
    row=schedule[0];entry=entries[row['case_id'],row['arm']]
    for name in ('endpoint','body','call_cap','cost_cap','wall_cap','duplicate','closed'):
        n=Runner(OUT/'offline_negative'/name)
        req=httpx.Request('POST',URL,content=enc(entry['body']))
        if name=='endpoint': req=httpx.Request('POST','https://api.openai.com/v1/embeddings',content=enc(entry['body']))
        if name=='body': req=httpx.Request('POST',URL,content=b'{}')
        if name=='call_cap': n.calls=72
        if name=='cost_cap': n.cost=CAP
        if name=='wall_cap': n.started-=WALL+1
        if name=='duplicate': n.labels.add(row['label'])
        if name=='closed': n.closed=True
        rejects(name,lambda:n.validate(req,entry,row))
    for name in ('http_error','missing_usage','model_drift'):
        n=Runner(OUT/'offline_negative'/name)
        def bad(req):
            resp=mock(req); data=resp.json()
            if name=='missing_usage':data.pop('usage')
            if name=='model_drift':data['model']='different'
            return httpx.Response(500 if name=='http_error' else 200,json=data,request=req)
        with httpx.Client(transport=httpx.MockTransport(bad)) as client:
            rejects(name,lambda:n.send(client,entry,row))
        need(n.calls==1 and n.closed,'Failure retry/close guard')
    put(OUT/'offline_validation.json',{'at':now(),'status':'PASS','mock_calls':g.calls,'negative_controls':tests,
        'external_calls':0,'runner_sha256':sha(__file__),'preservation':preserve()})
    print('OFFLINE PASS',g.calls,'mocked calls;',len(tests),'negative controls;0 external calls',flush=True)

def freeze():
    need(load(OUT/'offline_validation.json')['runner_sha256']==sha(__file__),'Offline runner mismatch')
    need((OUT/'rubric.json').is_file(),'Rubric required before freeze')
    files=['run.py','launch.py','before.json','requests.json','schedule.json','parity.json','evaluation_contract.json',
           'protocol.json','pricing.json','preparation.json','rubric.json','rubric_notes.md','offline_validation.json']
    put(OUT/'freeze.json',{'at':now(),'files':{p:sha(OUT/p) for p in files},'external_calls_before_freeze':0})
    print('FROZEN',len(files),'files',flush=True)

def live():
    import httpx
    from dotenv import dotenv_values
    need(os.environ.get('TABLE_FACT_PILOT_WATCHDOG')==sha(OUT/'launch.py'),'Whole-process watchdog required')
    frozen=load(OUT/'freeze.json')
    for p,h in frozen['files'].items():need(sha(OUT/p)==h,'Frozen file drift '+p)
    before=preserve()
    need(not before['changed'] and all(before['git_equal'].values()),'Protected file drift')
    entries={(r['case_id'],r['arm']):r for r in load(OUT/'requests.json')}
    for entry in entries.values():need(sha(ROOT/entry['packet_path'])==entry['packet_sha256'],'Source packet drift')
    env=dotenv_values(ROOT/'.env')
    key=env.get('OPENAI_API_KEY') or os.environ.get('OPENAI_API_KEY')
    need(bool(key),'Configured key missing')
    base=env.get('OPENAI_BASE_URL') or os.environ.get('OPENAI_BASE_URL') or 'https://api.openai.com/v1'
    need(base.rstrip('/')=='https://api.openai.com/v1','Configured provider differs')
    put(OUT/'authorization_consumed.json',{'at':now(),'freeze_sha256':sha(OUT/'freeze.json'),
        'scope':'72 fresh generations; no retries or other model calls; USD20/5400seconds max'})
    g=Runner(OUT/'live');done=threading.Event();error=None;status='STOPPED'
    def heartbeat():
        while not done.wait(15):
            append(g.directory/'heartbeat.jsonl',{'at':now(),'phase':'generation',**g.summary()})
            print('HEARTBEAT',g.completed,'/',MAX_CALLS,'cost',g.cost,flush=True)
    heartbeat_thread=threading.Thread(target=heartbeat,daemon=True)
    heartbeat_thread.start()
    try:
        # Direct single HTTP transport: no SDK retries, redirects, proxy routing, tools or hidden probes.
        with httpx.Client(transport=httpx.HTTPTransport(retries=0),trust_env=False,follow_redirects=False,
                timeout=httpx.Timeout(150,connect=20),headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'}) as client:
            for row in load(OUT/'schedule.json'):
                need(time.monotonic()-g.started<WALL-150,'Insufficient remaining wall time for request')
                g.send(client,entries[row['case_id'],row['arm']],row)
                print('ANSWER',g.completed,row['label'],'USD',str(g.cost),flush=True)
        need(g.calls==g.completed==72,'Incomplete schedule')
        status='COMPLETED'
    except BaseException as exc:
        # No HTTP request headers or credential values are persisted or printed.
        error={'type':type(exc).__name__,'message':str(exc)[:500] if isinstance(exc,Stop) else 'Transport/execution error; no automatic retry.'}
    finally:
        done.set()
        heartbeat_thread.join()
        result={'at':now(),'status':status,'error':error,**g.summary()}
        put(g.directory/'execution_result.json',result)
        put(g.directory/'raw_seal.json',{'at':now(),'files':{p.relative_to(g.directory).as_posix():sha(p) for p in g.directory.rglob('*') if p.is_file()}})
        put(OUT/'post_generation_preservation.json',preserve())
        print(json.dumps(result,ensure_ascii=False),flush=True)
    need(status=='COMPLETED','Execution stopped; see saved result')

if __name__=='__main__':
    {'prepare':prepare,'offline':offline,'freeze':freeze,'live':live}[sys.argv[1]]()
