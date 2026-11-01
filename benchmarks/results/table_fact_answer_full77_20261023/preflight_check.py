"""Independent, network-denied preflight; never opens .env or a live store."""
from pathlib import Path
from collections import Counter
from decimal import Decimal
import copy
import hashlib
import importlib.util
import json
import socket
import subprocess
import sys
import time

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]

def read(p):
    return json.loads(Path(p).read_text('utf-8'))

def canonical(v):
    return json.dumps(v, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')

def digest(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()

checks = []
def check(name, value, detail=None):
    assert value, name
    checks.append({'name': name, 'status': 'PASS', 'detail': detail})

def denied(*args, **kwargs):
    raise AssertionError('Network transport prohibited in independent audit')

socket.create_connection = denied
socket.socket.connect = denied
socket.socket.connect_ex = denied

old = {x['case_id']: x['body'] for x in read(ROOT/'benchmarks/results/full77_sol_top12_20261020/requests.json')}
contract = read(ROOT/'benchmarks/results/table_fact_budget77_offline_20261023/evaluation_contract.json')['cases']
cids = [x['case_id'] for x in contract]
groups = {x['case_id']: x['group'] for x in contract}
reqs = read(OUT/'requests.json')
schedule = read(OUT/'schedule.json')
protocol = read(OUT/'protocol.json')
pricing = read(OUT/'pricing.json')
parity = read(OUT/'parity.json')
offline = read(OUT/'offline_validation.json')
check('77_unique_case_ids', len(cids) == len(set(cids)) == 77)
check('154_unique_case_arm_bodies', len(reqs) == 154 and len({(x['case_id'],x['arm']) for x in reqs}) == 154)
check('only_two_expected_arms', {(x['case_id'],x['arm']) for x in reqs} == {(cid,arm) for cid in cids for arm in ('A','C')})
check('77_case_group_counts', Counter(groups.values()) == {'common_answerable':46,'refusal':19,'diagnostic_or_hold':12}, dict(Counter(groups.values())))
control = protocol['fixed_generation']
check('fixed_model_reasoning_output', control['model']=='gpt-6.1-sol' and control['reasoning']=={'effort':'low'} and control['max_output_tokens']==8192)
check('fixed_default_no_stream_store', control['service_tier']=='default' and control['store'] is False and control['stream'] is False)
check('fixed_strict_answer_schema', control['text']['format']['strict'] is True and control['text']['format']['type']=='json_schema' and set(control['text']['format']['schema']['properties'])=={'answer','cited_source_ids','abstained'} and control['text']['format']['schema']['additionalProperties'] is False)
check('no_model_tools_or_hidden_generation_inputs', set(control)=={'model','reasoning','max_output_tokens','service_tier','store','stream','text','input'} and len(control['input'])==2)
by_key = {}
reservations = Decimal(0)
packet_sizes = {'A':[], 'C':[]}
source_hashes = {}
for x in reqs:
    cid, arm = x['case_id'], x['arm']
    by_key[cid,arm] = x
    src = ROOT/x['packet_path']
    expected = ROOT/('benchmarks/results/table_fact_units_offline_20261023/packets/'+cid+'_A12.json' if arm=='A' else 'benchmarks/results/table_fact_budget77_offline_20261023/packets/'+cid+'_160KiB.json')
    assert src.resolve()==expected.resolve(), ('source_path',cid,arm)
    p = read(src)
    a = json.loads(old[cid]['input'][1]['content'])
    assert digest(src)==x['packet_sha256'], ('source_sha',cid,arm)
    source_hashes[x['packet_path']] = x['packet_sha256']
    assert json.loads(x['body']['input'][1]['content'])==p, ('wire_packet',cid,arm)
    assert hashlib.sha256(canonical(x['body'])).hexdigest()==x['body_sha256'], ('body_hash',cid,arm)
    assert x['group']==groups[cid], ('group',cid,arm)
    stripped = copy.deepcopy(p)
    for d in stripped['documents']:
        d.pop('table_fact_units',None)
    assert stripped==a, ('original_text_metadata_sequence',cid,arm)
    if arm=='A':
        assert x['body']==old[cid], ('original_body_exact',cid)
    else:
        expect_body = copy.deepcopy(old[cid])
        expect_body['input'][1]['content'] = canonical(p).decode('utf-8')
        assert x['body']==expect_body, ('only_fact_packet_changed',cid)
    nonevidence = copy.deepcopy(x['body'])
    nonevidence['input'][1]['content'] = '<PACKET>'
    assert nonevidence==control, ('nonpacket_parity',cid,arm)
    expected_question = next(c['question'] for c in contract if c['case_id']==cid)
    assert p['query']==a['query']==expected_question and p['report_scope']==a['report_scope'], ('question_scope',cid,arm)
    size = len(canonical(p))
    assert size==x['packet_bytes'] and size<=(65536 if arm=='A' else 163840), ('packet_budget',cid,arm)
    packet_sizes[arm].append(size)
    bound = len(canonical(x['body']))+4096
    reserve = Decimal(bound)*Decimal('2.5')/1000000 + Decimal(8192)*10/1000000
    assert bound==x['input_token_bound'] and bound<272000, ('token_bound',cid,arm)
    assert reserve==Decimal(x['reservation_usd']), ('reservation',cid,arm)
    reservations += 2*reserve
check('all154_source_packet_and_body_hashes_recomputed', True)
check('all154_original_text_metadata_order_preserved', True)
check('all77_A_wire_bodies_exact_original', True)
check('all77_C_only_fact_units_added_to_existing_documents', True)
check('all154_nonpacket_generation_parity', True)
check('packet_budgets', True, {k:{'min':min(v),'max':max(v)} for k,v in packet_sizes.items()})
check('all154_per_call_reservations_recomputed', True)
check('aggregate_reservation', reservations==Decimal('70.0828250')==Decimal(pricing['all_saturated_reservations_usd']) and reservations<=Decimal('70.09'), str(reservations))
expected_schedule=[]
for rep in (1,2):
    for i,cid in enumerate(cids):
        order = ('A','C') if i%2==0 else ('C','A')
        if rep==2: order=tuple(reversed(order))
        for arm in order:
            expected_schedule.append({'case_id':cid,'arm':arm,'repetition':rep,'label':f'{cid}:{arm}:r{rep}'})
check('exact308_predeclared_balanced_reversed_schedule', schedule==expected_schedule)
check('unique308_labels', len(schedule)==len({x['label'] for x in schedule})==308)
check('every_case_arm_exactly_two_repetitions', Counter((x['case_id'],x['arm']) for x in schedule)==Counter({(cid,a):2 for cid in cids for a in ('A','C')}))
check('154_parity_receipts_match', len(parity)==154 and {(x['case_id'],x['arm']) for x in parity}==set(by_key) and all(x['nonpacket_parity'] and x['original_sources_preserved'] for x in parity))
check('protocol_caps', protocol['max_http_attempts']==308 and Decimal(protocol['cap_usd'])==Decimal('70.09') and protocol['max_wall_seconds']==9000 and protocol['retries']==0)
check('root308_mock_and10_controls', offline['status']=='PASS' and offline['mock_calls']==308 and offline['external_calls']==0 and len(offline['negative_controls'])==10)
check('root_mock_exact_runner_version', offline['runner_sha256']==digest(OUT/'run.py'))
check('reported6334_file_preservation_clean', offline['preservation']['protected_files']==6334 and offline['preservation']['changed']==[] and all(offline['preservation']['git_equal'].values()) and offline['preservation']['env_unchanged'], 'Root hashed private/store files; this audit does not reopen them.')

spec=importlib.util.spec_from_file_location('full77_independent_runner',OUT/'run.py')
mod=importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
check('runtime_constants', mod.CAP==Decimal('70.09') and mod.WALL==9000 and mod.MAX_CALLS==308 and mod.MODEL=='gpt-6.1-sol')
import httpx
entry=by_key[schedule[0]['case_id'],schedule[0]['arm']]
row=schedule[0]
def response(req, mutation=None):
    raw={'model':'gpt-6.1-sol','service_tier':'default','reasoning':{'effort':'low'},'status':'completed',
      'usage':{'input_tokens':100,'output_tokens':10,'input_tokens_details':{'cached_tokens':0,'cache_write_tokens':97}},
      'output':[{'content':[{'type':'output_text','text':'{"answer":"fixture","cited_source_ids":[],"abstained":true}'}]}]}
    if mutation: mutation(raw)
    return httpx.Response(200,json=raw,request=req)

mock_root=OUT/'preflight_mock'
mock_root.mkdir(exist_ok=False)
mutations={
    'service_tier_drift':lambda r:r.update(service_tier='priority'),
    'reasoning_drift':lambda r:r.update(reasoning={'effort':'high'}),
    'incomplete_response':lambda r:r.update(status='incomplete'),
    'input_reservation_exceeded':lambda r:r['usage'].update(input_tokens=entry['input_token_bound']+1),
    'output_reservation_exceeded':lambda r:r['usage'].update(output_tokens=8193),
    'negative_usage':lambda r:r['usage'].update(output_tokens=-1),
    'inconsistent_cache_usage':lambda r:r['usage']['input_tokens_details'].update(cached_tokens=100),
    'missing_cache_write_usage':lambda r:r['usage']['input_tokens_details'].pop('cache_write_tokens'),
}
for name,mutation in mutations.items():
    g=mod.Runner(mock_root/name)
    with httpx.Client(transport=httpx.MockTransport(lambda req:response(req,mutation))) as client:
        try: g.send(client,entry,row)
        except mod.Stop: pass
        else: raise AssertionError('Expected failure: '+name)
    assert g.calls==1 and g.closed and g.completed==0, name
check('eight_additional_provider_drift_usage_controls',True,list(mutations))
for name,mutation in {
    'malformed_answer_retained':lambda r:r['output'][0]['content'][0].update(text='not json'),
    'unknown_citation_retained':lambda r:r['output'][0]['content'][0].update(text='{"answer":"fixture","cited_source_ids":["unknown-source"],"abstained":false}')
}.items():
    g=mod.Runner(mock_root/name)
    with httpx.Client(transport=httpx.MockTransport(lambda req:response(req,mutation))) as client:
        g.send(client,entry,row)
    assert g.calls==1 and g.completed==1 and not g.closed, name
    result=json.loads((mock_root/name/'answers.jsonl').read_text('utf-8'))
    assert result['structural_error'] if name.startswith('malformed') else result['unknown_citations']==['unknown-source']
check('bad_answers_retained_without_regeneration',True)

launch_spec=importlib.util.spec_from_file_location('full77_independent_launch',OUT/'launch.py')
launch=importlib.util.module_from_spec(launch_spec)
launch_spec.loader.exec_module(launch)
t=time.monotonic()
child=subprocess.Popen([sys.executable,'-B','-c','import time; time.sleep(5)'],creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
exit_code,killed=launch.wait_bounded(child,0.05)
check('real_subprocess_hard_timeout',killed and child.poll() is not None and time.monotonic()-t<5,{'exit_code':exit_code,'seconds':time.monotonic()-t})
run_source=(OUT/'run.py').read_text('utf-8')
launch_source=(OUT/'launch.py').read_text('utf-8')
check('single_no_retry_direct_transport', 'httpx.HTTPTransport(retries=0)' in run_source and 'trust_env=False' in run_source and 'follow_redirects=False' in run_source)
check('closed_authorization_and_launcher_marker', "put(OUT/'authorization_consumed.json'" in run_source and "path.open('xb')" in run_source and "marker.open('x'" in launch_source)
check('whole_process9000_watchdog_required', 'wait_bounded(p,9000)' in launch_source and "need(os.environ.get('TABLE_FACT_FULL77_WATCHDOG')==sha(OUT/'launch.py')" in run_source)
check('all_frozen_files_checked_before_key_read', run_source.index("for p,h in frozen['files'].items()")<run_source.index("env=dotenv_values(ROOT/'.env')"))
check('source_packets_checked_before_key_read', run_source.index("for entry in entries.values():need(sha(ROOT/entry['packet_path'])")<run_source.index("env=dotenv_values(ROOT/'.env')"))

report={
 'status':'PASS','blocking_findings':[],
 'scope':'Independent pre-live transport, schedule, frozen-input and cost audit. Not semantic answer validation.',
 'external_calls':0,'network_connections_denied':True,'env_opened':False,'active_store_opened':False,
 'checks':checks,'additional_mock_calls':10,'root_mock_calls_verified':308,
 'source_packet_hashes':source_hashes,
 'input_sha256':{p:digest(OUT/p) for p in ('run.py','launch.py','requests.json','schedule.json','parity.json','protocol.json','pricing.json','offline_validation.json','evaluation_contract.json','before.json')},
 'limitations':[
  'USD cap is guarded by serialized UTF-8 input bytes plus4096 and worst output reservation under fixed published rates; a provider usage/pricing violation can only be detected after response, so the bound is not an external billing guarantee.',
  'Strict source/frozen file equality proves transport consistency, not fact-unit semantic accuracy or output quality.',
  'Private .env and active store bytes were not opened by this audit; root offline receipt reports their matching hashes.',
  'Run final freeze only after rubric and preflight report are present; no live launch was performed in this audit.'
 ]}
with (OUT/'preflight_audit.json').open('x',encoding='utf-8') as f:
    json.dump(report,f,ensure_ascii=False,indent=2)
print(json.dumps({'status':report['status'],'checks':len(checks),'external_calls':0,'additional_mock_calls':10,'reservation_usd':str(reservations),'blocking_findings':[]},ensure_ascii=False))
