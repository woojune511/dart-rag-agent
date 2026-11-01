"""Aggregate fixed denominators; no external models, no answer regeneration."""
from common_exec import *
from collections import Counter
from decimal import Decimal
import statistics

def main():
    for p,h in load(OUT/'raw_output_seal.json')['files'].items():need(sha(OUT/p)==h,'Raw seal drift')
    mapping={x['review_id']:x for x in load(OUT/'review_mapping.json')};rubric=load(PREP/'rubric.json')
    cases={c['case_id']:c for c in rubric['cases']};review_rows=[]
    for i in (1,2,3):
        folder=OUT/'masked_review'/f'batch{i}';expected={x['review_id'] for x in load(folder/'items.json')}
        rows=load(folder/'review.json')['reviews']
        need(len(rows)==24 and {x['review_id'] for x in rows}==expected,'Incomplete/duplicate review batch')
        review_rows+=rows
    overrides=load(OUT/'adjudication.json').get('overrides',[]) if (OUT/'adjudication.json').is_file() else []
    original={x['review_id']:x for x in review_rows};rows=[]
    for review in review_rows:
        r=copy_review=dict(review)
        for o in overrides:
            if o['review_id']==r['review_id']:r={**r,**o['replacement_fields'],'adjudication_reason':o['reason']}
        m=mapping[r['review_id']];need(r['case_id']==m['case_id'],'Review case identity')
        gold=cases[r['case_id']];required={x['id'] for x in gold['required_facts']}
        need(len(r['required_facts'])==len(required) and {f['id'] for f in r['required_facts']}==required,'Required fact coverage')
        for axis in ('accuracy','completeness','faithfulness'):need(r[axis] in ('PASS','PARTIAL','FAIL','AMBIGUOUS'),'Grade value')
        need(all(f['status'] in ('FULFILLED','PARTIAL','OMITTED','INCORRECT','UNRESOLVED') and f['note'] for f in r['required_facts']),'Fact status')
        need((r['completeness']=='PASS')==all(f['status']=='FULFILLED' for f in r['required_facts']),'Completeness/fact inconsistency')
        rows.append({**r,**m,'answerable':r['case_id'] in rubric['primary_answerable_ids'],
          'all_pass':all(r[a]=='PASS' for a in ('accuracy','completeness','faithfulness')),'company':gold['company']})
    need(len(rows)==72 and len({r['review_id'] for r in rows})==72,'Total grading coverage')
    def stats(group):
        return {'n':len(group),'all_pass':sum(r['all_pass'] for r in group),
          **{a:dict(Counter(r[a] for r in group)) for a in ('accuracy','completeness','faithfulness')},
          'required_fact_status':dict(Counter(f['status'] for r in group for f in r['required_facts'])),
          'answers_with_required_fact_omission':sum(any(f['status'] in ('OMITTED','PARTIAL') for f in r['required_facts']) for r in group)}
    primary={a:stats([r for r in rows if r['arm']==a and r['answerable']]) for a in ('A','C')}
    refusals={a:{**stats([r for r in rows if r['arm']==a and not r['answerable']]),
      'appropriate_abstention':dict(Counter(r['appropriate_abstention'] for r in rows if r['arm']==a and not r['answerable']))} for a in ('A','C')}
    repeats={str(rep):{a:stats([r for r in rows if r['repeat']==rep and r['arm']==a and r['answerable']]) for a in ('A','C')} for rep in (1,2)}
    companies={c:{a:stats([r for r in rows if r['company']==c and r['arm']==a and r['answerable']]) for a in ('A','C')} for c in sorted({r['company'] for r in rows})}
    pairs=[]
    for cid in cases:
        for rep in (1,2):
            pair={a:next(r for r in rows if r['case_id']==cid and r['arm']==a and r['repeat']==rep) for a in ('A','C')}
            pairs.append({'case_id':cid,'repeat':rep,'answerable':pair['A']['answerable'],
              'A_review':pair['A']['review_id'],'C_review':pair['C']['review_id'],
              'all_pass_delta':int(pair['C']['all_pass'])-int(pair['A']['all_pass']),
              'A':{k:pair['A'][k] for k in ('accuracy','completeness','faithfulness','appropriate_abstention')},
              'C':{k:pair['C'][k] for k in ('accuracy','completeness','faithfulness','appropriate_abstention')}})
    outputs=[json.loads(x) for x in (OUT/'live/answers.jsonl').read_text('utf8').splitlines()]
    performance={}
    for arm in ('A','C'):
        group=[x for x in outputs if x['arm']==arm]
        performance[arm]={'answers':len(group),'input_tokens':sum(x['usage']['input_tokens'] for x in group),
          'output_tokens':sum(x['usage']['output_tokens'] for x in group),
          'reasoning_tokens':sum((x['usage'].get('output_tokens_details') or {}).get('reasoning_tokens',0) for x in group),
          'estimated_usd':str(sum(Decimal(x['estimated_usd']) for x in group)),
          'median_seconds':statistics.median(x['seconds'] for x in group),'structural_failures':sum(bool(x['structural_errors']) for x in group)}
    result={'at':now(),'status':'GRADED','primary_answerable':primary,'refusals':refusals,'per_repeat':repeats,'per_company':companies,'pairs':pairs,
      'performance':performance,'delta_all_pass_pp':100*(primary['C']['all_pass']-primary['A']['all_pass'])/30,
      'gain_each_repeat':all(v['C']['all_pass']>v['A']['all_pass'] for v in repeats.values()),
      'nonnegative_report_count':sum(v['C']['all_pass']>=v['A']['all_pass'] for v in companies.values()),
      'material_regression_decision':'Requires source-adjudicated review of every regression; do not infer from aggregate alone.',
      'adjudication_overrides':len(overrides),'preservation':frozen(),'external_judge_calls':0}
    put(OUT/'graded_answers.json',rows);put(OUT/'summary.json',result)
    print(json.dumps({'primary':primary,'refusals':refusals,'delta_pp':result['delta_all_pass_pp']},ensure_ascii=False),flush=True)
if __name__=='__main__':main()
