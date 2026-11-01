from common_exec import *
from collections import Counter
from decimal import Decimal,localcontext,ROUND_HALF_UP

rows=load(OUT/'graded_answers.json');mapping=load(OUT/'review_mapping.json')
answers=[json.loads(x) for x in (OUT/'live/answers.jsonl').read_text('utf8').splitlines()]
bykey={(a['case_id'],a['arm'],a['repeat']):a for a in answers}
receipts=0;not_cited=[];not_visible=[]
for r in rows:
    a=bykey[r['case_id'],r['arm'],r['repeat']]
    packet=load(OUT/'packets'/f'{r["case_id"]}_{r["arm"]}.json')
    visible={d['source_id'] for d in packet['documents']};cited=set(a['answer']['cited_source_ids'])
    for item in r['receipts']:
        receipts+=1;sid=item.get('source_id')
        if sid and sid not in visible:not_visible.append({'review_id':r['review_id'],'source_id':sid})
        if sid and sid not in cited:not_cited.append({'review_id':r['review_id'],'source_id':sid})
    need(bool(r['notes']) and bool(r['receipts']),'Missing grading explanation')
need(not not_visible,'Review source outside actual packet')
# Non-cited sources can document omitted information, but cannot make a claim faithful.
with localcontext() as ctx:
    ctx.prec=60
    rate=(Decimal(2680239)-Decimal(2323476))/Decimal(2323476)*100
    need(rate.quantize(Decimal('.01'),rounding=ROUND_HALF_UP)==Decimal('15.35'),'Arithmetic witness')
scope_packet=load(OUT/'packets/H07_A.json')
scope_sources=[{'source_id':d['source_id'],'text':d['text']} for d in scope_packet['documents'] if '소재지' in d['text']]
need(scope_sources,'H07 missing scope was not actually delivered')
s=load(OUT/'summary.json');regressions=[]
rank={'FAIL':0,'AMBIGUOUS':0,'PARTIAL':1,'PASS':2,'NOT_APPLICABLE':2}
for p in s['pairs']:
    worse=[a for a in ('accuracy','completeness','faithfulness','appropriate_abstention') if rank[p['C'][a]]<rank[p['A'][a]]]
    if worse:regressions.append({'case_id':p['case_id'],'repeat':p['repeat'],'axes':worse})
need(not regressions,'Review a newly observed regression before closeout')
put(OUT/'closeout_validation.json',{'status':'PASS','at':now(),'reviewed_answers':len(rows),'review_receipts':receipts,
  'not_visible_receipts':not_visible,'non_cited_receipts_for_manual_boundary':not_cited,
  'H09_exact_growth_rate_percent':str(rate),'H09_rounded_percent':'15.35','H07_A_delivered_scope_sources':scope_sources,
  'paired_metric_regressions':regressions,'new_material_fact_or_refusal_regressions':0,
  'primary_decision':'MIXED_INCONCLUSIVE: positive pooled difference; strict increase not observed in repetition2',
  'H17_gloss_sensitivity':{'A_all_pass':28,'C_all_pass':30,'difference':2,'delta_pp':100*2/30,'repeat1':[13,15],'repeat2':[15,15],
    'note':'Treating the common harmless acronym expansion as supported changes both arms equally; conclusion unchanged.'},
  'H16_unit_adjudication':'All4 fulfilled under natural per-product price meaning; no additional literal /개 requirement inserted.',
  'review_files':{f'masked_review/batch{i}/review.json':sha(OUT/'masked_review'/f'batch{i}'/'review.json') for i in (1,2,3)},
  'unit_gloss_adjudication_sha256':sha(OUT/'unit_gloss_adjudication.json'),'preservation':frozen()})
print(json.dumps({'status':'PASS','answers':len(rows),'receipts':receipts,'not_visible':not_visible,'non_cited':not_cited,'regressions':regressions},ensure_ascii=False),flush=True)
