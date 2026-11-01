"""Source-grounded, unblinded review notes. Never imported by retrieval code."""
import json
import re
from run import OUT, prior, save

def packet(cid,arm):return prior.load(OUT/f'packets/{cid}_{arm}.json')
checks=[]
def quote(cid,arm,uid,s):
    p=packet(cid,arm)
    d=next(d for d in p['documents'] if d['chunk_id']==uid)
    assert s in d['text'],(cid,uid,s)
    q={'case_id':cid,'arm':arm,'uid':uid,'quote':s,'text_sha256':prior.text_sha(d['text'])}
    checks.append(q)
    return q
def absent(cid,strings):
    p=packet(cid,'F12')
    original=prior.encoded(p)
    folded=re.sub(r'[\s,]','',original)
    for s in strings:assert re.sub(r'[\s,]','',s) not in folded,(cid,s)
    return {'absent_strings_from_entire_F12_packet':strings,'packet_sha256':prior.sha(OUT/f'packets/{cid}_F12.json'),'interpretation':'Absence of these source values is machine checked; equivalence/meaning assessment is bounded assistant review.'}

rows=[]
cid='KBF_T2_018'
rows.append({'case_id':cid,'verdict':'EXACT_OPERAND_PRECISION_LOSS; rounded alternative and causal narrative retained',
 'lost':[quote(cid,'N12','20240326000894:625:2','신용손실충당금전입액 | (3,146,409) | (1,847,775) | (1,185,133)')],
 'retained':[quote(cid,'F12','20240326000894:1846:5','신용손실충당금전입액 (d) | 3,146 | 1,299 | 1,848 | 1,185'),quote(cid,'F12','20240326000894:1846:5','신용손실충당금전입액은 미래경기 불확실성에 대비한 보수적인 충당금적립으로')],
 **absent(cid,['3,146,409','1,847,775']),
 'interpretation':'The frozen broad witness panel still counts this case covered through rounded MD&A values. Exact million-won operands are newly absent; the thousand-million-won alternative changes calculable precision. Do not call it a complete loss or an observed answer error.',
 'deterministic_growth_pct':{'exact_original':(3146409/1847775-1)*100,'rounded_retained':(3146/1848-1)*100}})
cid='SKH_T3_080'
rows.append({'case_id':cid,'verdict':'CONSOLIDATED_BASIS_EVIDENCE_LOSS; separate-basis values remain',
 'lost':[quote(cid,'N12','20240319000684:381:252','외화환산손실 | 906,120'),quote(cid,'N12','20240319000684:381:252','외화환산이익 | (573,884)')],
 'retained':[quote(cid,'F12','20240319000684:633:233','외화환산손실 | 640,782'),quote(cid,'F12','20240319000684:633:233','외화환산이익 | (330,272)'),quote(cid,'F12','20240319000684:342:213','외환차이 | 1,903,535')],
 **absent(cid,['573,884','906,120']),
 'interpretation':'Original historical evaluation uses consolidated translation gain/loss. Separate values are not the same scope, and broad FX differences are not the same measure. The question does not expressly specify consolidation; a clearly labeled separate-basis answer may remain possible. This is confirmed loss of the prior basis, not measured full answer failure.'})
cid='SAM_T3_028'
rows.append({'case_id':cid,'verdict':'REQUIRED_AMOUNT_EVIDENCE_LOSS',
 'lost':[quote(cid,'N12','20240312000736:319:191','조정내역 계 | 재고자산평가손실(환입) 등 | 5,037,579')],
 'retained':[quote(cid,'F12','20240312000736:210:82','동 비용에는 재고자산평가손실 금액이 포함되어 있습니다.'),quote(cid,'F12','20240312000736:209:81','재고자산 계 | 56,506,958 | (4,319,092) | 52,187,866')],
 **absent(cid,['5,037,579','3,558,358']),
 'interpretation':'The annual loss/reversal amount is newly unavailable. Retained cost-inclusion explanation and ending valuation allowance cannot replace the period expense amount. Preserve the source qualifier 등; do not infer a same-basis causal percentage.'})
cid='MIX_T2_022'
rows.append({'case_id':cid,'verdict':'REPLACEMENT_SUPPORT_PRESERVED',
 'lost':[quote(cid,'N12','20240318000844:34:1','- 핀테크 | 1,354,767 | 14.0 | 1,186,635 | 14.4')],
 'retained':[quote(cid,'F12','20240318000844:42:1','- 핀테크 | 1,354,767 | 14.0 | 1,186,635 | 14.4'),quote(cid,'F12','20240318000844:1559:7','네이버페이 결제액은 2023년 59.6조원으로 21.8% 증가하였는데, 이는 외부 결제액 증가에 따른 페이 생태계의 지속적 확장과, 현장결제 확대 및 예약/주문 분야의 지속성장에 따른 결과입니다.')],
 'interpretation':'Same consolidated current/prior row survives in another source with the matching headers. Growth drivers and payment amount also survive. Source ID loss is not a required-evidence loss here.'})
cid='MIX_T3_063'
rows.append({'case_id':cid,'verdict':'HOLD_REMAINS; extra byte omission and axis context loss',
 'lost':[quote(cid,'N12','20240318000844:425:301','다. 당기말 및 전기말 현재, 당기 및 전기 중 주요 관계기업과 공동기업의 요약 재무정보 및 해당 기업으로부터 수령한 배당금은 다음과 같습니다.')],
 'interpretation':'Lost source introduces the following table, but supplies no requested rank or net-income values. Historical scope/reference HOLD remains; do not score this as newly wrong. Packet shrinks from six to four whole sources because changed order and larger metadata interact with the fixed byte budget. UID gains do not establish correctly scoped ranking evidence.'})
cid='CEL_T3_015'
rows.append({'case_id':cid,'verdict':'CORE_SUPPORT_PRESERVED; optional historical detail lost',
 'lost':[quote(cid,'N12','20240318000913:691:94','파생상품자산 18백만원 및 파생상품부채 65백만원을 추가 인식하였습니다')],
 'retained':[quote(cid,'F12','20240318000913:575:415','합병의 목적 | 통합된 자원의 대규모 투자, 개발-생산-판매 일원화를 통한 제품력 및 원가경쟁력 확보, 투명성 제고를 통한 투자자 신뢰증진'),quote(cid,'F12','20240318000913:575:415','합병기일 | 2023-12-28'),quote(cid,'F12','20240318000913:575:415','합병비율 | 피합병법인 보통주식 1주당 합병기업의 보통주식 0.4492620주 교부')],
 **absent(cid,['18백만원','65백만원']),
 'interpretation':'Core merger facts and purpose stay available. The source supporting an optional derivative-recognition detail in the old answer disappears. Do not equate fewer optional facts with failure of the required summary.'})
cid='CEL_T3_040'
rows.append({'case_id':cid,'verdict':'TARGET_NOT_RECOVERED_AND_SEPARATE_GROSS_AMOUNTS_NEWLY_LOST',
 'lost':[quote(cid,'N12','20240318000913:917:320','조정항목에 의한 합계 | 재고자산평가손실 | 1,010,161'),quote(cid,'N12','20240318000913:917:320','조정항목에 의한 합계 | 재고자산평가손실환입 | (45,139,758)'),quote(cid,'N12','20240318000913:917:320','조정항목에 의한 합계 | 재고자산폐기손실 | 22,312,563')],
 'retained':[quote(cid,'F12','20240318000913:319:159','재고자산평가손실환입 등 | (21,196)'),quote(cid,'F12','20240318000913:732:135','재고자산평가손실환입 등 | (21,817)')],
 **absent(cid,['2,526,280','48,885,812','25,163,510','1,010,161','45,139,758','22,312,563']),
 'interpretation':'The three consolidated amounts remain outside final12. The three separate amounts previously inside N12 are now also absent. Net cost recognition cannot reconstruct three gross components. The question does not expressly require consolidated scope, so this separate-basis loss matters and is not captured by the consolidated-only frozen 26-unit panel.'})
expected={x['case_id'] for x in prior.load(OUT/'all77_source_audit.json')['cases'] if x['historical_citations_newly_lost_vs_N12']}
assert expected=={r['case_id'] for r in rows}
cid='HYU_T3_072'
rows.append({'case_id':cid,'verdict':'SCOPE_TRADEOFF_AND_PARTIAL_GAIN; not a full recovery',
 'lost':[quote(cid,'N12','20240313001451:293:151','전체 공동기업 및 관계기업 | 공동기업 및 관계기업 | Motional AD LLC | 709,112 | 0 | (8,421) | 700,691')],
 'retained_or_new':[quote(cid,'F12','20240313001451:687:106','전체 공동기업 | Motional AD LLC (*1,11) | 자율주행 소프트웨어 개발 | 미국 | 25.81% | 1,294,367'),quote(cid,'F12','20240313001451:294:152','전체 공동기업 및 관계기업 | 공동기업 및 관계기업 | Motional AD LLC | 922,942 | 0 | (15,881) | 907,061')],
 **absent(cid,['700,691']),
 'interpretation':'The N12 current-marked consolidated investment value 700,691 million disappears (RRF9 to13). Newly selected F12 separate/current-marked table supplies 25.81% ownership and 1,294,367 million investment. Prior-marked 907,061 is not current. The question does not require consolidation, so the separate row is a useful partial alternative; no Motional profit/loss recovery is established. These scope/period descriptions rely on saved parser markers and headers, not new original-report period validation. Keep this post-hoc partial tradeoff outside the frozen26-unit score.'})
save('source_review.json',{'reviewer':'same assistant, unblinded; no independent reviewer or model judge','cases_reviewed':len(rows),'method':'All seven newly lost historical-citation cases plus the prior Nori partial-gain Motional case inspected in baseline and treatment whole-source packets. Quotes verified exactly; explicit absence checks supplement semantic source review. Other69 cases receive source/citation/panel audit, not exhaustive semantic adjudication.','cases':rows})
save('quote_verification.json',{'status':'PASS','quotes_checked':len(checks),'cases':len(rows),'quotes':checks})
print('PASS',len(rows),'source reviews;',len(checks),'exact quotes')
