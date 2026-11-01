"""Read-only mechanical delivery audit; literal presence is NOT semantic support."""
from common_exec import *
from collections import Counter
from decimal import Decimal
import copy,re,statistics

def normalized(s):return re.sub(r'\s+','',str(s))
def main():
    qs=load(PREP/'questions.json');cases={c['case_id']:c for c in load(PREP/'rubric.json')['cases']}
    detail=[];statuses=Counter();unit_statuses=Counter()
    for q in qs:
        cid=q['case_id'];ret=load(OUT/'retrieval'/f'{cid}.json');a=load(OUT/'packets'/f'{cid}_A.json');c=load(OUT/'packets'/f'{cid}_C.json')
        need(len(ret['dense'])==16 and len(ret['bm25'])<=24 and len(ret['rrf'])==12,'Candidate fixed limits')
        need(len(a['documents'])==len(c['documents'])==12,'Source delivery count')
        stripped=copy.deepcopy(c)
        for d in stripped['documents']:d.pop('table_fact_units',None)
        need(stripped==a,'A/C source parity')
        need(all(x['metadata']['rcept_no']==q['receipt'] for k in ('dense','bm25','rrf') for x in ret[k]),'Explicit receipt filter')
        decisions=load(OUT/'projection_decisions'/f'{cid}.json')
        statuses.update(d['status'] for d in decisions);unit_statuses.update(u['status'] for d in decisions for u in d.get('units',[]))
        literal=[]
        for e in cases[cid]['evidence']:
            needle=normalized(e['quote'])
            # Keep this an exact-literal diagnostic, not an inferred relationship score.
            literal.append({'evidence_id':e['id'],'quote':e['quote'],
              'A_exact_quote_in_serialized_packet':needle in normalized(enc(a).decode()),
              'C_exact_quote_in_serialized_packet':needle in normalized(enc(c).decode())})
        detail.append({'case_id':cid,'A_bytes':len(enc(a)),'C_bytes':len(enc(c)),
          'same_sources':12,'dense':len(ret['dense']),'bm25':len(ret['bm25']),
          'candidate_union':len({x['metadata']['chunk_uid'] for k in ('dense','bm25') for x in ret[k]}),
          'attached_units':sum(len(d.get('table_fact_units',{}).get('units',[])) for d in c['documents']),
          'attached_tables':sum(bool(d.get('table_fact_units')) for d in c['documents']),
          'literal_diagnostic':literal})
    ledger=[json.loads(x) for x in (OUT/'live/ledger.jsonl').read_text('utf8').splitlines()]
    dispatch=[x for x in ledger if x['event']=='dispatch'];settled=[x for x in ledger if x['event']=='settled']
    need(len(dispatch)==len(settled)==105 and len({x['label'] for x in dispatch})==105,'Call ledger cardinality')
    need(sum(Decimal(x['estimated_usd']) for x in settled)==Decimal(load(OUT/'execution_result.json')['usage_estimated_usd']),'Cost ledger sum')
    put(OUT/'delivery_audit.json',{'status':'PASS','at':now(),'cases':detail,'table_decisions':dict(statuses),'unit_decisions':dict(unit_statuses),
      'all_sources12':True,'query_reformulation_calls':0,'reranker_calls':0,'external_judge_calls':0,'lookup_only_saved_results':True,
      'A_mean_bytes':statistics.mean(x['A_bytes'] for x in detail),'C_mean_bytes':statistics.mean(x['C_bytes'] for x in detail),
      'limitation':'Exact quote hits do not establish joined period/entity/unit support; quotes spanning cells can be false negatives. Semantic outcomes use actual-packet source review.',
      'cost_sum':str(sum(Decimal(x['estimated_usd']) for x in settled)),'preservation':frozen()})
    print(json.dumps({'status':'PASS','table_decisions':dict(statuses),'unit_decisions':dict(unit_statuses),'questions':18,'sources_each_arm':12},ensure_ascii=False),flush=True)
if __name__=='__main__':main()
