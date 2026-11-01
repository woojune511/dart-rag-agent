"""Record the assistant's source-checked judgments; not an automated LLM judge."""
from common import *
from decimal import Decimal, ROUND_HALF_UP
from statistics import mean, median

# Reviewed against each complete answer and its supplied/cited evidence dossier.
CASE_REVIEW={
 ('01_income','generic'):(True,True,'generic:117 supplies connected period/scope/unit header; generic:118 supplies both totals. Amounts in thousand won and 5.23% match source rounding. Repeat 1 omits citation to the table header source.'),
 ('01_income','dart'):(True,True,'999:3 contains revenue 3,514,315,500 and operating profit 183,933,032, current/prior columns, thousand-won unit and consolidated operating-results heading. Both answers calculate 5.23%.'),
 ('01_inventory','generic'):(True,True,'generic:23 includes the full consolidated balance-sheet heading, 2025-12-31, KRW unit, both exact operands, and supports 9.24%.'),
 ('01_inventory','dart'):(True,True,'199:94 supports net inventory 353,314,248 thousand won; 93:1 supplies consolidated 2025 summary assets 3,822,122 million won. Unit conversion and 9.24% are correct within source display precision.'),
 ('01_capex','generic'):(False,True,'Both cash-flow operands missing from supplied packet. Generic:49/87 are asset movement notes, not acquisition cash payments. Both answers appropriately refuse; not complete for an answerable question.'),
 ('01_capex','dart'):(False,True,'104:6 cash-flow source is in corpus but RRF31, outside top12. Visible notes 215:110/239:134 support the disclosed additions amounts; 1010:8 supports MDA PPE amount but not a full two-operand cash-flow answer. Refusal is faithful.'),
 ('01_business','generic'):(True,True,'generic:6 supports all four food categories, representative brands including Welchs, and subsidiary rental/esports/beer. generic:21 supports eight geographic reporting segments; repeat1 generic:4/5 supports smart-farm purpose and withheld commercialization details.'),
 ('01_business','dart'):(True,True,'30:0 contains the food manufacturing/sales grouping, all product categories, brands and uses. Both answers correctly distinguish product categories from separate business segments.'),
 ('02_income','generic'):(True,True,'generic:40 contains current consolidated segment totals and million-won unit. Revenue 11,314,459 and profit 913,331 support 8.07%, within published display precision.'),
 ('02_income','dart'):(True,True,'128:21 contains the current consolidated segment table with million-won unit and both totals; 8.07% is correct.'),
 ('02_inventory','generic'):(False,True,'generic:121 supplies inventory 2,412,997 million won and rounded 16.5% but not total assets. Both replies refuse to infer a precise denominator from the rounded ratio. Full operands exist in corpus but source generic:18 is RRF16.'),
 ('02_inventory','dart'):(True,True,'97:0 supplies both exact won amounts, consolidated summary heading and 2025 column. 844:8 supports net-of-allowance inventory statement. Ratio 16.53% correct.'),
 ('02_capex','generic'):(True,True,'generic:24 includes 2025 consolidated cash-flow heading, won unit, PPE 1,192,112,995,578 and intangible 54,210,548,833. Positive sum 1,246,323,544,411 is correct.'),
 ('02_capex','dart'):(False,True,'106:5 actual cash-flow operands exist but rank RRF22. 205:98 supports additions 1,217,587,270 thousand won; 227:120 supports prior-period intangible carrying amount. Both replies correctly refuse to substitute asset additions for cash expenditure.'),
 ('02_business','generic'):(True,True,'generic:6 contains all three segments, passive components/semiconductor substrates/camera modules, and application mapping. Required and additional claims supported.'),
 ('02_business','dart'):(True,True,'9:9 contains all three segment-product mappings; 46:1 supports smartphone, automotive and PC applications.'),
}

def main():
    import run
    run.verify()
    for seal in ('raw_seal.json','packets_seal.json'):
        for p,digest in load(BASE/seal).items():assert sha(p)==digest
    answers=load(BASE/'review/answers.json');assert len(answers)==40
    judgements=[]
    for r in answers:
        if r['type']=='negative':
            complete,packet,reason=True,True,'Explicit evidence-relative refusal for daily sales, abstained true, no invented or averaged daily value. Annual periods cited only as contrast. Negative control scored separately.'
            assert r['abstained'] is True
        else:complete,packet,reason=CASE_REVIEW[(r['id'],r['arm'])]
        citation=True
        if (r['id'],r['arm'],r['repeat'])==('01_income','generic',1):
            citation=False
            assert r['cited_source_ids']==['20260311003892:20260311003892%3Ageneric%3A118']
            reason+=' Strict citation coverage fails: the current/prior column labels and applicable thousand-won unit are in uncited generic:117. Unrelated FX-table unit labels later in 118 do not supply this table header. Entire packet still supports the answer.'
        judgements.append({'id':r['id'],'arm':r['arm'],'repeat':r['repeat'],'type':r['type'],'complete_correct':complete,
                           'packet_faithful':packet,'cited_support_complete':citation,'faithful_under_frozen_rule':packet and citation,
                           'supported_complete':complete and packet and citation,'abstained':r['abstained'],'reason':reason,
                           'cited_source_ids':r['cited_source_ids'],'answer_file':str(BASE/'live'/f'{r["id"]}_{r["arm"]}_r{r["repeat"]}'/'answer.value.json')})
    ledger=[json.loads(x) for x in (BASE/'ledger.jsonl').read_text('utf-8').splitlines()]
    traces=load(BASE/'retrieval.json');corpora=load(BASE/'corpus_manifest.json')['corpora'];plan=load(BASE/'preflight.json')
    costs={a:Decimal(0) for a in ('generic','dart')};shared=Decimal(0)
    for row in ledger:
        if row['stage']=='embedding':
            if row['id']=='queries':shared+=Decimal(row['usd'])
            else:
                batch=plan['batches'][int(row['id'].split('_')[1])];arm=next(c['arm'] for c in corpora if c['path']==batch['corpus']);costs[arm]+=Decimal(row['usd'])
    summary={}
    for arm in ('generic','dart'):
        pos=[j for j in judgements if j['arm']==arm and j['type']!='negative'];neg=[j for j in judgements if j['arm']==arm and j['type']=='negative']
        paid=[r for r in ledger if r['stage']=='answer' and '_'+arm+'_' in r['id']]
        answer_cost=sum((Decimal(r['usd']) for r in paid),Decimal(0))
        summary[arm]={'positive_count':len(pos),'complete_correct':sum(j['complete_correct'] for j in pos),'packet_faithful':sum(j['packet_faithful'] for j in pos),
                      'faithful_under_frozen_rule':sum(j['faithful_under_frozen_rule'] for j in pos),'supported_complete':sum(j['supported_complete'] for j in pos),
                      'correct_by_repeat':[sum(j['complete_correct'] for j in pos if j['repeat']==i) for i in (1,2)],
                      'negative_correct':sum(j['complete_correct'] for j in neg),'negative_count':len(neg),'answer_usd':str(answer_cost),'corpus_embedding_usd':str(costs[arm]),
                      'shared_query_embedding_half_usd':str(shared/2),'total_allocated_usd':str(answer_cost+costs[arm]+shared/2),
                      'r1_answer_usd':str(sum((Decimal(r['usd']) for r in paid if r['id'].endswith('_r1')),Decimal(0))),
                      'r2_answer_usd':str(sum((Decimal(r['usd']) for r in paid if r['id'].endswith('_r2')),Decimal(0))),
                      'input_tokens':sum(r['usage']['input_tokens'] for r in paid),'output_tokens':sum(r['usage']['output_tokens'] for r in paid),
                      'cached_input_tokens':sum((r['usage'].get('input_tokens_details') or {}).get('cached_tokens',0) for r in paid),
                      'cache_write_tokens':sum((r['usage'].get('input_tokens_details') or {}).get('cache_write_tokens',0) for r in paid),
                      'mean_answer_seconds':mean(r['seconds'] for r in paid),'median_answer_seconds':median(r['seconds'] for r in paid),
                      'mean_packet_chunks':mean(len(t['selected']) for t in traces if t['arm']==arm),'mean_proxy_tokens':mean(t['request_proxy_tokens'] for t in traces if t['arm']==arm)}
    pairs=[]
    for q in load(BASE/'question_seed.json'):
        if q['type']=='negative':continue
        outcomes={a:[next(j['complete_correct'] for j in judgements if j['id']==q['id'] and j['arm']==a and j['repeat']==i) for i in (1,2)] for a in ('generic','dart')}
        pairs.append({'id':q['id'],'company':q['company'],**outcomes,'repeat_consistent':all(v[0]==v[1] for v in outcomes.values())})
    write(BASE/'judgements.json',{'reviewer':'Assistant manual source review, not independent/blind','reviewed_at':now(),'rubric_sha256':sha(BASE/'rubric.json'),'rows':judgements})
    write(BASE/'summary.json',{'arms':summary,'paired_questions':pairs,'total_usd':str(sum(Decimal(r['usd']) for r in ledger)),'judgement_file_sha256':sha(BASE/'judgements.json'),
                                'interpretation':'No aggregate answer accuracy gain; stable one-question gain and one regression. Citation context issue in one generic repeat, not unsupported packet content.'})
    # Independent Decimal checks of calculations made in complete numeric answers.
    checks=[]
    for name,a,b,expected in [('N-income',3514315500,183933032,'5.23'),('N-inventory-generic',3822122467403,353314247728,'9.24'),('N-inventory-dart',3822122000000,353314248000,'9.24'),('S-income',11314459,913331,'8.07'),('S-inventory-dart',14595895255468,2412996843057,'16.53')]:
        actual=(Decimal(b)/Decimal(a)*100).quantize(Decimal('.01'),rounding=ROUND_HALF_UP);assert str(actual)==expected
        checks.append({'case':name,'numerator':b,'denominator':a,'percent':str(actual),'passed':True})
    assert 1192112995578+54210548833==1246323544411
    checks.append({'case':'S-capex-generic','sum_krw':1246323544411,'passed':True})
    write(BASE/'arithmetic_review.json',checks)
    print(json.dumps(summary,ensure_ascii=False,indent=2))

if __name__=='__main__':
    with offline():main()
