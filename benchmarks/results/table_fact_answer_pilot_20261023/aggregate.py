"""Aggregate sealed, adjudicated reviews without querying a provider or store."""
from collections import Counter
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import statistics

OUT=Path(__file__).resolve().parent
def load(p):return json.loads(Path(p).read_text('utf-8'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def put(p,v):
    with Path(p).open('x',encoding='utf-8') as f:json.dump(v,f,ensure_ascii=False,indent=2)

def main():
    live=OUT/'live'
    for p,h in load(live/'raw_seal.json')['files'].items():assert sha(live/p)==h,p
    for p,h in load(OUT/'freeze.json')['files'].items():assert sha(OUT/p)==h,p
    mapping={x['review_id']:x for x in load(OUT/'review_mapping.json')}
    source=load(OUT/'adjudicated_reviews.json')
    reviews=source['reviews']
    assert len(reviews)==72 and set(mapping)=={x['review_id'] for x in reviews}
    cases={c['case_id']:c for c in load(OUT/'rubric.json')['cases']}
    answers={x['label']:x for x in map(json.loads,(live/'answers.jsonl').read_text('utf-8').splitlines())}
    rows=[]
    for r in reviews:
        m=mapping[r['review_id']]
        assert m['case_id']==r['case_id']
        c=cases[r['case_id']]
        states=Counter(u['status'] for u in r['units'])
        assert {u['unit_id'] for u in r['units']}=={u['unit_id'] for u in c['frozen_required_units']}
        rows.append({**r,**{k:m[k] for k in ['arm','repetition','label']},'group':c['group'],
            'complete_success':None if c['group']=='diagnostic_or_hold' else all(r[k]=='PASS' for k in ['accuracy','completeness','faithfulness']),
            'unit_states':dict(states),'missing_units':states['OMITTED'],
            'unfulfilled_units':sum(n for s,n in states.items() if s!='FULFILLED'),
            'provider_answer_structural_error':answers[m['label']]['structural_error'],
            'unknown_citations':answers[m['label']]['unknown_citations']})
    groups={}
    for group in sorted({r['group'] for r in rows}):
        groups[group]={}
        for arm in 'ABC':
            rs=[r for r in rows if r['arm']==arm and r['group']==group]
            groups[group][arm]={'answers':len(rs),'complete_success':None if group=='diagnostic_or_hold' else sum(r['complete_success'] for r in rs),
                **{k:dict(Counter(r[k] for r in rs)) for k in ['accuracy','completeness','faithfulness','appropriate_abstention']},
                'unit_states':dict(sum((Counter(r['unit_states']) for r in rs),Counter())),
                'omitted_units':sum(r['missing_units'] for r in rs),
                'unfulfilled_units':sum(r['unfulfilled_units'] for r in rs)}
    pairs={}
    index={(r['case_id'],r['arm'],r['repetition']):r for r in rows}
    score={'FAIL':0,'PARTIAL':1,'PASS':2}
    for lo,hi in [('A','B'),('B','C'),('A','C')]:
        results=[]
        for cid,c in cases.items():
            for rep in (1,2):
                left,right=index[cid,lo,rep],index[cid,hi,rep]
                changes={}
                for axis in ['accuracy','completeness','faithfulness']:
                    a,b=left[axis],right[axis]
                    changes[axis]=(score[b]-score[a]) if a in score and b in score else None
                lu={u['unit_id']:u['status'] for u in left['units']}
                ru={u['unit_id']:u['status'] for u in right['units']}
                results.append({'case_id':cid,'repetition':rep,'group':c['group'],'changes':changes,
                    'complete_before':left['complete_success'],'complete_after':right['complete_success'],
                    'newly_fulfilled':[u for u in ru if ru[u]=='FULFILLED' and lu[u]!='FULFILLED'],
                    'lost_fulfilled':[u for u in ru if lu[u]=='FULFILLED' and ru[u]!='FULFILLED']})
        pairs[lo+'_'+hi]=results
    performance={}
    for arm in 'ABC':
        rs=[a for a in answers.values() if a['arm']==arm]
        times=[r['seconds'] for r in rs]
        performance[arm]={'answers':len(rs),'estimated_usd':str(sum(Decimal(r['estimated_usd']) for r in rs)),
            'input_tokens':sum(r['usage']['input_tokens'] for r in rs),
            'output_tokens':sum(r['usage']['output_tokens'] for r in rs),
            'reasoning_tokens':sum(r['usage']['output_tokens_details']['reasoning_tokens'] for r in rs),
            'cached_tokens':sum(r['usage']['input_tokens_details']['cached_tokens'] for r in rs),
            'cache_write_tokens':sum(r['usage']['input_tokens_details']['cache_write_tokens'] for r in rs),
            'latency_mean':statistics.mean(times),'latency_median':statistics.median(times),'latency_max':max(times)}
    put(OUT/'paired_results.json',rows)
    put(OUT/'summary.json',{'groups':groups,'pairs':pairs,'performance':performance,
        'execution':load(live/'execution_result.json'),'raw_seal_verified':True,'frozen_inputs_verified':True,
        'source_review':'Masked native-assistant review plus root adjudication; no independent human or judge API.',
        'all_citation_ids_valid':all(not r['unknown_citations'] for r in rows),
        'all_answers_schema_valid':all(not r['provider_answer_structural_error'] for r in rows),
        'statistical_inference':'Descriptive only; repeats are not independent questions; development-exposed purposive sample.'})
    print(json.dumps({'groups':groups,'performance':performance},ensure_ascii=False,indent=2))

if __name__=='__main__':main()
