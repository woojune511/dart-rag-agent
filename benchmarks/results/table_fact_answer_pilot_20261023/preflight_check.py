"""Provider-free request parity and actual MockTransport payload audit."""
import copy, hashlib, importlib.util, json, socket
from collections import Counter
from decimal import Decimal
from pathlib import Path
P=Path(__file__).resolve().parent; ROOT=P.parents[2]
def denied(*args,**kwargs): raise RuntimeError('Network prohibited in preflight audit')
socket.socket.connect=socket.socket.connect_ex=socket.create_connection=socket.getaddrinfo=denied
import httpx
def load(p): return json.loads(p.read_text(encoding='utf-8'))
def enc(x): return json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
issues=[]
def check(ok,where):
 if not ok: issues.append(where)
entries=load(P/'requests.json'); schedule=load(P/'schedule.json'); protocol=load(P/'protocol.json')
original={x['case_id']:x['body'] for x in load(ROOT/'benchmarks/results/full77_sol_top12_20261020/requests.json')}
ids=protocol['case_ids']; expected={(cid,arm,rep) for cid in ids for arm in 'ABC' for rep in (1,2)}
check(len(ids)==len(set(ids))==12,'12 unique cases')
check(len(entries)==len({(e['case_id'],e['arm']) for e in entries})==36,'36 unique prepared bodies')
check(len(schedule)==len({x['label'] for x in schedule})==72,'72 unique dispatch labels')
check({(x['case_id'],x['arm'],x['repetition']) for x in schedule}==expected,'exact12x3x2 schedule')
by={(e['case_id'],e['arm']):e for e in entries}; stats=Counter(); reserve=Decimal(0)
for e in entries:
 cid,arm=e['case_id'],e['arm']; body=e['body']; source=ROOT/e['packet_path']; pkt=load(source)
 base=copy.deepcopy(body); old=copy.deepcopy(original[cid]); base['input'][1]['content']=old['input'][1]['content']='<PACKET>'
 check(base==old,f'nonpacket generation parity {cid}/{arm}')
 check(body['model']=='gpt-6.1-sol' and body['reasoning']=={'effort':'low'} and body['max_output_tokens']==8192 and body['service_tier']=='default',f'model/settings {cid}/{arm}')
 check(not body.get('tools') and body.get('stream') is False and body.get('store') is False,f'no tools/stream/store {cid}/{arm}')
 check(json.loads(body['input'][1]['content'])==pkt,f'body preserves complete packet {cid}/{arm}')
 check(sha(source)==e['packet_sha256'] and hashlib.sha256(enc(body)).hexdigest()==e['body_sha256'],f'source/body hashes {cid}/{arm}')
 a=json.loads(original[cid]['input'][1]['content']); stripped=copy.deepcopy(pkt)
 for d in stripped['documents']: d.pop('table_fact_units',None)
 check(stripped==a,f'original full packet and document sequence {cid}/{arm}')
 check(len(enc(pkt))==e['packet_bytes'],f'packet bytes {cid}/{arm}')
 check(arm=='A' or len(enc(pkt))<=({'B':65536,'C':163840}[arm]),f'context budget {cid}/{arm}')
 bound=len(enc(body))+4096; price=Decimal(bound)*Decimal('2.5')/1000000+Decimal(8192)*Decimal('10')/1000000
 check(bound==e['input_token_bound'] and price==Decimal(e['reservation_usd']) and bound<272000,f'reservation arithmetic {cid}/{arm}')
 reserve+=price*2
 stats[arm+'_bodies']+=1; stats[arm+'_fact_attached_documents']+=sum('table_fact_units' in d for d in pkt['documents'])
check(reserve<=20,'all72 reservation below USD20')
for cid in ids:
 orders={rep:[x['arm'] for x in schedule if x['case_id']==cid and x['repetition']==rep] for rep in (1,2)}
 check(orders[2]==list(reversed(orders[1])),f'reversal {cid}')
spec=importlib.util.spec_from_file_location('pilot_preflight_runner',P/'run.py'); runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(runner)
captured=[]
def mock(req):
 body=json.loads(req.content);pkt=json.loads(body['input'][1]['content']); captured.append({'body_sha256':hashlib.sha256(req.content).hexdigest(),'fact_docs':sum('table_fact_units' in d for d in pkt['documents'])})
 answer={'answer':'provider-free transport fixture','abstained':True,'cited_source_ids':[pkt['documents'][0]['source_id']]}
 return httpx.Response(200,request=req,json={'model':runner.MODEL,'service_tier':'default','reasoning':{'effort':'low'},'status':'completed','usage':{'input_tokens':100,'output_tokens':10,'total_tokens':110,'input_tokens_details':{'cached_tokens':0,'cache_write_tokens':0}},'output':[{'content':[{'type':'output_text','text':json.dumps(answer)}]}]})
g=runner.Runner(P/'preflight_mock_transport')
# Use one preselected case for three actual Runner.send MockTransport calls.
cid=ids[0]
with httpx.Client(transport=httpx.MockTransport(mock),trust_env=False) as client:
 for arm in 'ABC':
  e=by[cid,arm]; row=next(x for x in schedule if x['case_id']==cid and x['arm']==arm and x['repetition']==1)
  g.send(client,e,row)
  check(captured[-1]['body_sha256']==e['body_sha256'],f'actual MockTransport bytes {arm}')
  check(captured[-1]['fact_docs']==sum('table_fact_units' in d for d in load(ROOT/e['packet_path'])['documents']),f'actual MockTransport fact fields {arm}')
result={'schema_version':'generation_pilot_independent_preflight_audit_v1','status':'REQUEST_AND_MOCK_TRANSPORT_PASS_WALL_GUARD_PENDING' if not issues else 'ISSUES_FOUND','issues':issues,'review_mode':'Shared task context; independent provider-free body/transport inspection, no answer-quality evaluation','checked':{'prepared_bodies':len(entries),'scheduled_calls':len(schedule),'model':'gpt-6.1-sol','reasoning':'low','max_output_tokens':8192,'nonpacket_conditions_match_original':not issues,'field_counts':dict(stats),'all_saturated_reservations_usd':str(reserve),'actual_runner_mock_calls':g.calls,'external_calls':0,'captured_transport_payloads':captured},'static_findings':[{'id':'F01','severity':'blocking unless externally bounded','status':'pending external watchdog verification','finding':'httpx timeout150 is not a total in-flight wall deadline. Dispatch-time WALL5400 checks alone cannot enforce total90min if bytes keep arriving.'}], 'static_verified':['Direct HTTP sends complete canonical entry.body, so attached fact fields are not filtered by the response JSON schema.','MAX_CALLS72, unique labels, HTTPTransport retries0 and follow_redirectsFalse, exclusive authorization_consumed/live directory prevent automatic retry or resume.','Dispatch reservation is persisted before send; unknown-usage/transport errors close runner and retain unsettled reservation.','Malformed answer and unknown citations are stored as outcomes, with no answer-based retry branch.','Key value is only in live client headers; no key/header persistence in request/response receipts.','Requests copy original model/prompt/schema/service tier/settings; only user packet content changes.'],'limitations':['Pricing rates and provider usage fields were not revalidated online by this reviewer; cost arithmetic is conditional on root verified tariff.','Byte-plus4096 reservation is conservative local accounting, not proof of provider tokenizer or billing behavior. Observed reservation/provider drift stops later calls.','Mock success does not establish live provider compatibility or answer-quality gain.','Wall-time external watchdog must be independently checked before live authorization.','This reviewer did not read or print .env/API key, restart app, open store or call a network/model endpoint.'],'artifacts':{'runner_sha256':sha(P/'run.py'),'requests_sha256':sha(P/'requests.json'),'schedule_sha256':sha(P/'schedule.json'),'protocol_sha256':sha(P/'protocol.json'),'checker_sha256':sha(Path(__file__))}}
(P/'preflight_audit.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'status':result['status'],'issues':issues,'calls':g.calls,'external_calls':0,'reserve':str(reserve),'field_counts':dict(stats)},ensure_ascii=False))
