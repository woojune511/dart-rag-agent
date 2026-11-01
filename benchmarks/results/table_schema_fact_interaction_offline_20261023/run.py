"""Frozen saved-retrieval x fact-delivery comparison. Experiment artifact only."""
from __future__ import annotations
import copy
import gzip
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import socket
import statistics
import subprocess
import sys
import time
from collections import Counter
from io import BytesIO

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
BASE = OUT.parent
SCHEMA = BASE / 'table_schema_search_validated_offline_20261022'
FACT = BASE / 'table_fact_units_offline_20261023'
BUDGET = BASE / 'table_fact_budget77_offline_20261023'
EXPORT = BASE / 'v12_store_recovery_preparation_2026-10-17'
ACTIVE = ROOT / 'data/app_full11_2023_v12_20261017'
START = time.monotonic()
CAP = 163840
ARMS = ('A12_original', 'S12_original', 'A12_fact160', 'S12_fact160')

def denied(*a, **kw):
    raise RuntimeError('Offline experiment: network and provider/store clients prohibited')

socket.create_connection = socket.socket.connect = socket.socket.connect_ex = socket.getaddrinfo = denied
os.environ['GIT_OPTIONAL_LOCKS'] = '0'
sys.dont_write_bytecode = True

def load(p):
    return json.loads(Path(p).read_text(encoding='utf-8'))

def encoded(x):
    return json.dumps(x, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)

def digest(x):
    return hashlib.sha256(encoded(x).encode('utf-8')).hexdigest()

def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(4*1024*1024),b''):
            h.update(b)
    return h.hexdigest()

def save(n,x):
    p=(OUT/n).resolve()
    assert p.is_relative_to(OUT)
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

def beat(phase,**kw):
    row={'phase':phase,'elapsed_seconds':round(time.monotonic()-START,2),**kw}
    with (OUT/'heartbeat.jsonl').open('a',encoding='utf-8') as f:
        f.write(encoded(row)+'\n')
    print(encoded(row),flush=True)
    if time.monotonic()-START>1800:
        raise TimeoutError('Offline phase exceeded 30 minutes')

def git(*args):
    return subprocess.check_output(['git',*args],cwd=ROOT)

def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    m=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m

def dependencies():
    files=[SCHEMA/'results.json',SCHEMA/'protocol.json',SCHEMA/'source_review.json',
           SCHEMA/'known_witness_panel.json',SCHEMA/'all77_source_audit.json',
           FACT/'run.py',FACT/'projector.py',FACT/'projections.json',FACT/'source_checks.json',
           BASE/'table_bundle_delivery_offline_20261022/projector.py',
           BUDGET/'results.json',BUDGET/'evaluation_contract.json',BUDGET/'evaluation_supplement.json',
           BUDGET/'postrun_required_fact_review.json',BUDGET/'postrun_boundary_check.py',
           ROOT/'src/processing/financial_parser.py']
    files.extend(EXPORT.glob('*.jsonl.gz'))
    files.extend(ROOT/r['path'] for r in load(FACT/'source_checks.json').values())
    for r in load(SCHEMA/'results.json'):
        cid=r['case_id']
        files.extend(SCHEMA/f'packets/{cid}_{arm}.json' for arm in ('A12','S12'))
        files.extend([FACT/f'packets/{cid}_A12.json',BUDGET/f'packets/{cid}_160KiB.json'])
    return sorted(set(files))

def prepare():
    assert not (OUT/'freeze.json').exists()
    assert git('check-ignore',str(OUT.relative_to(ROOT))).strip()
    deps=dependencies()
    paths={ROOT/p for p in load(BUDGET/'before.json')['files']}
    paths.update(deps)
    paths.update(p for p in ACTIVE.rglob('*') if p.is_file())
    paths.update(ROOT/p.decode('utf-8') for p in git('ls-files','--cached','--others','--exclude-standard','-z').split(b'\0') if p)
    paths.add(ROOT/'.env')
    paths={p for p in paths if p.is_file() and not p.is_relative_to(OUT)}
    before={}
    for i,p in enumerate(sorted(paths),1):
        before[p.relative_to(ROOT).as_posix()]={'sha256':sha(p),'bytes':p.stat().st_size}
        if i%1000==0:beat('preservation_snapshot',files=i,total=len(paths))
    status=git('status','--porcelain=v1','-uall')
    (OUT/'git_status_before.bin').write_bytes(status)
    save('before.json',{'files':before,'head':git('rev-parse','HEAD').decode().strip(),'index':sha(ROOT/'.git/index')})
    for n in ('evaluation_contract.json','evaluation_supplement.json'):
        (OUT/n).write_bytes((BUDGET/n).read_bytes())
    protocol={
        'version':'saved_schema_fact_interaction_v1','date':'2026-10-23','status':'FROZEN_BEFORE_NEW_PROJECTION_OUTPUT',
        'scope':'First priority only: frozen A12 versus S12 retrieval with and without the same table-fact delivery package.',
        'population':{'cases':77,'common_answerable':46,'refusal':19,'HOLD':12},
        'arms':{'A12_original':'Saved A12 original64KiB packet', 'S12_original':'Saved S12 original64KiB packet',
                'A12_fact160':'Same A12 packet plus unchanged source-validated fact-unit assembler, total160KiB',
                'S12_fact160':'Same S12 packet plus identical fact-unit assembler, total160KiB'},
        'retrieval_fixed_within_arm':'Saved candidate lists, scores, Dense, BM25 rules, RRF60 order, selected12, query and explicit receipt. No retrieval recomputation.',
        'delivery_fixed_between_retrieval_arms':['Frozen projector and XML helper','first physical table owner','source row/column unit order',
            'atomic dependency admission; skip oversized unit and continue','no original source refill','no query-aware priorities',
            'original text, context, source IDs and document order intact within each arm'],
        'new_S12_projections':'Reuse every existing UID projection exactly. For previously unprojected S12 UIDs, run the same frozen generic projector over the saved metadata and hash-checked original XML. No schema expansion or filling missing stored values from XML.',
        'causal_limits':'Delivery package combines table augmentation and160KiB; not a pure format effect. S12 combines schema and frozen stream allocation; not representation-only.',
        'evaluation':['All77 invariants, source/physical-unit additions/losses and byte sizes',
            'unchanged154 criteria with bounded source review and explicit unresolved cases',
            'legacy26 known-witness facts, current4 failures and19axis-watch',
            'review alternatives before interpreting source-ID loss as fact loss',
            'A12_fact160 exact replay against previous saved160KiB packets',
            'independent original XML/cell/context verification for delivered additions'],
        'gate':'Proceed toward an answer-generation plan only if S12_fact160 has new required evidence beyond A12_fact160 and no confirmed required-evidence regression in reviewed cases. Unknowns do not count as passes. No tuning or automatic production adoption.',
        'limits':{'external_model_API_calls':0,'cost_usd':0,'new_answers':0,'scored_runs':1,'run_seconds':1800,
                  'store_or_SQLite_client':False,'app_restart':False,'network':'blocked'},
        'preservation':{'write_scope':OUT.relative_to(ROOT).as_posix(),'existing_runtime_env_active_store_prior_artifacts':'immutable'},
        'interpretation':'Development-exposed offline evidence availability; not answer accuracy, semantic certification or generalization.'}
    save('protocol.json',protocol)
    save('freeze.json',{'local':{n:sha(OUT/n) for n in ('run.py','protocol.json','evaluation_contract.json','evaluation_supplement.json')},
                        'dependencies':{p.relative_to(ROOT).as_posix():sha(p) for p in deps},'at':time.time()})
    (OUT/'passport.md').write_text('# Material Passport\n\n- Origin: academic-research-suite / experiment-agent run and validate\n- Scope: frozen A12/S12 retrieval by original64KiB/fact160KiB delivery,77development-exposed questions\n- Status: FROZEN; execution and bounded review pending\n- External model API calls:0; cost:$0\n- Production adoption:none\n',encoding='utf-8')
    save('initial_entry.json',{'kind':'initial_instructions','user_words':'그럼 네가 제안한 우선순위대로 실험해보자','resolved_scope':'First-priority saved A12/S12 offline comparison only; no paid provider calls.'})
    save('freeze_entry.json',{'kind':'tool_receipt','step':'schema_fact_protocol_freeze','status':'passed',
         'command':'run.py prepare','exit_status':0,'retries_used':0,
         'input_sha256':{n:sha(OUT/n) for n in ('run.py','protocol.json')},'output_sha256':sha(OUT/'freeze.json'),
         'gate_tokens':['77_CASES','FOUR_FROZEN_ARMS','EXTERNAL_API_0','NO_PRODUCTION_CHANGE']})
    save('claims.json',{'steps':[{'step':'schema_fact_protocol_freeze','status':'passed'}]})
    beat('frozen',cases=77,protected_files=len(before),dependencies=len(deps))

def frozen():
    f=load(OUT/'freeze.json')
    for n,h in f['local'].items():assert sha(OUT/n)==h,('local change',n)
    for n,h in f['dependencies'].items():assert sha(ROOT/n)==h,('dependency change',n)

def inventory(packet):
    units={}
    for d in packet['documents']:
        w=d.get('table_fact_units')
        if not w:continue
        frame={k:v for k,v in w.items() if k not in ('source_id','cells','units')}
        for row,col,val,ra,ca in w['units']:
            key=w['document_sha256']+'|'+w['table_locator']+f'|{row}:{col}'
            payload={'at':[row,col],'value':w['cells'][val], 'row_axes':[w['cells'][i] for i in ra],
                     'column_axes':[w['cells'][i] for i in ca],'frame':frame}
            assert key not in units
            units[key]=payload
    return units

def execute():
    frozen()
    assert not (OUT/'started.json').exists(),'One scored run only'
    save('started.json',{'at':time.time(),'external_model_API_calls':0})
    assembler=module('frozen_fact_assembler',FACT/'run.py');assembler.CAP=CAP
    projector=module('frozen_fact_projector',FACT/'projector.py')
    rankings=load(SCHEMA/'results.json')
    projections=load(FACT/'projections.json')
    originals={r['case_id']:{a:load(SCHEMA/f"packets/{r['case_id']}_{a}.json") for a in ('A12','S12')} for r in rankings}
    wanted={d['chunk_id'] for p in originals.values() for x in p.values() for d in x['documents']}
    missing=wanted-projections.keys()
    metadata={}
    for path in sorted(EXPORT.glob('*.jsonl.gz')):
        with gzip.open(path,'rt',encoding='utf-8') as f:
            for line in f:
                item=json.loads(line);uid=item['metadata']['chunk_uid']
                if uid in wanted:
                    assert uid not in metadata
                    assert hashlib.sha256(item['text'].encode('utf-8')).hexdigest()==item['text_sha256']
                    metadata[uid]=item
        beat('source_export',matched=len(metadata),wanted=len(wanted))
    assert wanted==metadata.keys()
    for cid,packets in originals.items():
        for label,p in packets.items():
            for d in p['documents']:
                m=metadata[d['chunk_id']]
                assert d['text'] in (m['text'],m['text'].strip())
                assert all(m['metadata'].get(k)==v for k,v in d['context'].items())
    sys.path.insert(0,str(ROOT))
    from lxml import etree
    from src.processing.financial_parser import _sanitize_xml_like_text
    trees={};sources=load(FACT/'source_checks.json')
    for uid in sorted(missing):
        meta=metadata[uid]['metadata'];receipt=meta['rcept_no'];src=sources[receipt]
        if receipt not in trees:
            p=ROOT/src['path'];assert sha(p)==src['sha256']
            clean,_=_sanitize_xml_like_text(p.read_text(encoding='utf-8'))
            parser=etree.XMLParser(no_network=True,resolve_entities=False,recover=False,huge_tree=True)
            trees[receipt]=etree.parse(BytesIO(clean.encode('utf-8')),parser)
            assert len(parser.error_log)==0
        obj=json.loads(meta.get('table_object_json') or '{}')
        key=(obj.get('source_document_sha256','')+'|'+obj.get('source_table_locator','')) if obj else None
        projected,rec=projector.build_units(meta,trees[receipt],src['sha256'])
        projections[uid]={'physical_key':key,'projection':projected,'receipt':rec}
        if sum(u in projections for u in missing)%20==0:beat('new_projection',complete=sum(u in projections for u in missing),total=len(missing))
    additions={uid:projections[uid] for uid in sorted(missing)}
    save('additional_projections.json',additions)
    save('projection_manifest.json',{'base_path':FACT.relative_to(ROOT).as_posix()+'/projections.json',
         'base_sha256':sha(FACT/'projections.json'),'additional_sha256':sha(OUT/'additional_projections.json'),
         'existing_unique_docs':len(projections)-len(additions),'additional_unique_docs':len(additions),
         'addition_status':dict(Counter(p['receipt']['status'] for p in additions.values())),
         'all_original_packet_text_and_context_match_saved_export':True})
    del metadata,trees
    results=[]
    previous={r['case_id']:r for r in load(BUDGET/'results.json')}
    for n,r in enumerate(rankings,1):
        cid=r['case_id'];row={'case_id':cid,'arms':{},'saved_retrieval_sha256':{},'exact_A12_fact160_replay':False}
        enhanced={}
        for label in ('A12','S12'):
            original=originals[cid][label]
            assert original['query']==r['query'] and original['report_scope']==r['report_scope']
            assert [d['chunk_id'] for d in original['documents']]==r['packets'][label]['uids']
            assert len(encoded(original).encode('utf-8'))==r['packets'][label]['bytes']<=65536
            selected=[h['uid'] for h in r['rrf'][label][:12]]
            assert len(selected)==12
            row['saved_retrieval_sha256'][label]=digest({'dense':r['dense'],'lexical':r['lexical'][label],'rrf':r['rrf'][label]})
            changed,decisions=assembler.project_packet(original,projections)
            if label=='A12':
                assert original==load(FACT/f'packets/{cid}_A12.json')
                assert changed==load(BUDGET/f'packets/{cid}_160KiB.json')
                assert decisions==previous[cid]['arms']['160KiB']['decisions']
                row['exact_A12_fact160_replay']=True
            for suffix,p in (('original',original),('fact160',changed)):
                arm=label+'_'+suffix;save(f'packets/{cid}_{arm}.json',p)
                row['arms'][arm]={'packet_sha256':digest(p),'packet_bytes':len(encoded(p).encode('utf-8')),
                    'selected12':selected,'actual_ids':[d['chunk_id'] for d in p['documents']],
                    'original_omitted':r['packets'][label]['omitted'],
                    'table_units':sum(len(d.get('table_fact_units',{}).get('units',[])) for d in p['documents'])}
                if suffix=='fact160':row['arms'][arm]['decisions']=decisions
            enhanced[label]=inventory(changed)
        a,b=enhanced['A12'],enhanced['S12'];common=a.keys()&b.keys()
        row['physical_unit_changes']={'common':len(common),'added':sorted(b.keys()-a.keys()),'lost':sorted(a.keys()-b.keys()),
            'changed_dependencies':[k for k in sorted(common) if a[k]!=b[k]]}
        results.append(row)
        save(f'cases/{cid}.json',row)
        beat('case_complete',case=n,total=77,case_id=cid,A_units=len(a),S_units=len(b),added=len(row['physical_unit_changes']['added']),lost=len(row['physical_unit_changes']['lost']))
    save('results.json',results)
    summary={'cases':77,'exact_A12_fact160_replays':77,'external_model_API_calls':0,'cost_usd':0,'new_answers':0,'retrieval_recomputations':0,'arms':{}}
    for arm in ARMS:
        x=[r['arms'][arm] for r in results];sizes=[r['packet_bytes'] for r in x]
        summary['arms'][arm]={'actual_source_events':sum(len(r['actual_ids']) for r in x),
            'mean_bytes':statistics.mean(sizes),'median_bytes':statistics.median(sizes),'max_bytes':max(sizes),
            'table_unit_events':sum(r['table_units'] for r in x)}
    summary['physical_unit_changes']={'common_events':sum(r['physical_unit_changes']['common'] for r in results),
        **{k:sum(len(r['physical_unit_changes'][k]) for r in results) for k in ('added','lost','changed_dependencies')},
        'cases_with_losses':[r['case_id'] for r in results if r['physical_unit_changes']['lost']]}
    save('aggregate_summary.json',summary)
    frozen()
    save('execution_entry.json',{'kind':'tool_receipt','step':'frozen_schema_fact_execution','status':'passed','command':'run.py run',
         'exit_status':0,'retries_used':0,'input_sha256':{'freeze.json':sha(OUT/'freeze.json'),'run.py':sha(OUT/'run.py')},
         'output_sha256':sha(OUT/'results.json'),'gate_tokens':['77_COMPLETE','A12_EXACT_REPLAY77','API_0']})
    beat('completed',cases=77)

def preserve():
    before=load(OUT/'before.json')
    changed=[p for p,r in before['files'].items() if not (ROOT/p).is_file() or sha(ROOT/p)!=r['sha256']]
    store=[p for p in before['files'] if p.startswith(ACTIVE.relative_to(ROOT).as_posix()+'/')]
    result={'protected_files':len(before['files']),'changed':changed,'env_byte_identical':'.env' not in changed,
        'active_store_files':len(store),'active_store_byte_identical':not any(p in changed for p in store),
        'HEAD_unchanged':git('rev-parse','HEAD').decode().strip()==before['head'],'index_unchanged':sha(ROOT/'.git/index')==before['index'],
        'git_status_unchanged':git('status','--porcelain=v1','-uall')==(OUT/'git_status_before.bin').read_bytes(),
        'store_or_SQLite_opened':False,'app_restarts':0,'external_model_API_calls':0}
    save('preservation.json',result)
    assert not changed and all(result[k] for k in ('env_byte_identical','active_store_byte_identical','HEAD_unchanged','index_unchanged','git_status_unchanged'))
    beat('preserved',**result)

if __name__=='__main__':
    try:
        {'prepare':prepare,'run':execute,'preserve':preserve}[sys.argv[1]]()
    except Exception as exc:
        save('failure_'+sys.argv[1]+'.json',{'type':type(exc).__name__,'error':str(exc),'at':time.time()})
        raise
