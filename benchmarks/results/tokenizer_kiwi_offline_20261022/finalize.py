"""Bounded source review of the one fixed experiment. No retrieval changes."""
import json
from collections import Counter
from pathlib import Path
from run import OUT, ROOT, prior, save, preserve

results = {r['case_id']:r for r in prior.load(OUT/'results.json')}
audit = prior.load(OUT/'all77_source_audit.json')['cases']
panel = prior.load(OUT/'known_witness_panel.json')
packets = {(cid,a):prior.load(OUT/'packets'/f'{cid}_{a}.json') for cid in results for a in ['A12','K12']}

def witness(cid,arm,uid,substring):
    d=next(d for d in packets[cid,arm]['documents'] if d['chunk_id']==uid)
    assert substring in d['text'], (cid,arm,uid,substring)
    return {'case_id':cid,'arm':arm,'uid':uid,'quote':substring,'offset':d['text'].index(substring),
            'source_text_sha256':prior.text_sha(d['text']),'context':d['context']}

facts = [
    witness('MIX_T3_048','A12','20240312000736:127:6','배당금의 지급 | (9,864,474)'),
    witness('MIX_T3_048','K12','20240312000736:590:0','2024년부터 2026년까지 3년간 발생하는 잉여현금흐름의 50%'),
    witness('CEL_T3_040','A12','20240318000913:517:357','조정항목에 의한 합계 | 재고자산평가손실 | 2,526,280'),
    witness('CEL_T3_040','A12','20240318000913:517:357','조정항목에 의한 합계 | 재고자산평가손실환입 | (48,885,812)'),
    witness('CEL_T3_040','A12','20240318000913:517:357','조정항목에 의한 합계 | 재고자산폐기손실 | 25,163,510'),
    witness('CEL_T3_040','K12','20240318000913:917:320','조정항목에 의한 합계 | 재고자산평가손실 | 1,010,161'),
    witness('SKH_T3_080','A12','20240319000684:381:252','외화환산손실 | 906,120'),
    witness('SKH_T3_080','A12','20240319000684:381:252','외화환산이익 | (573,884)'),
    witness('SKH_T3_080','K12','20240319000684:633:233','외화환산손실 | 640,782'),
    witness('SAM_T3_028','A12','20240312000736:319:191','재고자산평가손실(환입) 등 | 5,037,579'),
    witness('CEL_T1_038','A12','20240318000913:185:25','매출액 | 1,873,430,064 | 500,776,927 | 5,143,344 | (202,918,804) | 2,176,431,531'),
    witness('CEL_T1_038','K12','20240318000913:360:200','무형자산상각비 | 145,878,128 | 36,171,696 | 209,548 | 27,466 | 182,286,838'),
    witness('HYU_T2_010','K12','20240313001451:96:5','2023년 미국시장에서 현대차는 전년 대비 11.5% 증가한 87.0만 대'),
    witness('HYU_T2_010','K12','20240313001451:96:5','2022년에는 전년 대비 0.9% 감소한 78.1만 대'),
    witness('HYU_T3_011','K12','20240313001451:1047:3','GV70, GV80 등 고급차 및 SUV 판매증가 영향 믹스개선'),
    witness('LGE_T2_052','A12','20240314001110:20:1','(단위 : USD)'),
    witness('LGE_T2_052','K12','20240314001110:21:2','전동공구용 배터리 | 1.89 | 1.62 | 1.28'),
    witness('LGE_T2_052','K12','20240314001110:897:3','배터리 판매가격 대비 투입 원재료비가 높아서 발생하는 Lagging 영향'),
    witness('NAV_T3_032','K12','20240318000844:40:4','CapEx | 692.3 | 756.2'),
    witness('CEL_T3_015','K12','20240318000913:969:372','2023년 12월 28일을 합병기일로 셀트리온헬스케어를 흡수합병'),
    witness('CEL_T3_015','K12','20240318000913:575:415','개발-생산-판매 일원화를 통한 제품력 및 원가경쟁력 확보'),
    witness('MIX_T3_050','K12','20240318000913:949:352','특수관계자거래 | 제품 및 용역매출 | 0 | 60,441,029 | 0 | 0 | 782,446 | 1,669,765,912 | 89,307 | 0 | 1,731,078,694'),
]

notes = {
    'SKH_T3_080':('REQUIRED_CONNECTED_AMOUNTS_LOST','연결 외화환산이익/손실573,884/906,120백만원 표381:252가 RRF4→19. 별도330,272/640,782백만원은 남지만 연결 두 금액의 대체 근거가 아니다.'),
    'MIX_T3_048':('REQUIRED_EVIDENCE_LOST','연결 실제 배당 지급9,864,474백만원의 BM257→129로 후보 단계부터 탈락. 환원정책은 유지되지만 선언배당으로 대체할 수 없다.'),
    'HYU_T3_011':('PRIMARY_EVIDENCE_RETAINED_DETAIL_LOST','1045:1 손실. 1047:3의 물량 증가와 고급차/SUV 믹스 개선은 유지. 재료비 등 모든 보충 설명이 동일하게 보존된 것은 아니다.'),
    'SAM_T3_028':('REQUIRED_AMOUNT_AND_ACCOUNTING_LINK_LOST','연결5,037,579/별도3,558,358백만원 및 매출원가 처리 근거를 담던5개 출처가 모두 최종12개 밖. 핵심 표는 후보에 있지만 순위13~29로 탈락. 남은 추정/정책/다른 자산 손상 자료에서 동등한 근거를 확인하지 못했다.'),
    'LGE_T2_052':('PRODUCT_PRICE_UNIT_CONTEXT_LOST','원재료 가격24:2/23:1과 Lagging 설명897:3은 유지. 제품가격21:2는 남지만 그 표의 USD표제20:1이 RRF8→14로 탈락. 다른 원재료 표의 USD를 제품가격에 연결할 수 없다.'),
    'NAV_T3_032':('PRIMARY_EVIDENCE_RETAINED_DETAIL_LOST','40:4의 연결CapEx692.3십억원과 세종/춘천/클라우드 투자 설명 및37:1/38:2시설근거는 유지. 별도 주석1238:137의 추가 설명은 손실.'),
    'CEL_T1_038':('REQUIRED_DENOMINATOR_LOST','총상각182,286,838천원 및 매출원가/판관비 배분360:200은 유지. 영업이익률 영향을 계산할 연결 매출2,176,431,531천원 표185:25가 후보에서 탈락하고 남은12개에서 동일 분모 근거를 확인하지 못했다.'),
    'CEL_T3_015':('PRIMARY_EVIDENCE_RETAINED_DETAIL_LOST','574:414/691:94 손실. 969:372에 합병일·승인 사실, 연결 주석575:415에 합병비율·목적이 남음. 추가 거래/재무 설명의 동일성은 주장하지 않는다.'),
    'CEL_T3_040':('THREE_REQUIRED_CONNECTED_AMOUNTS_LOST','연결 gross 평가손실2,526,280/환입48,885,812/폐기25,163,510천원 표가 RRF11→15. 순환입 등 반올림 표시와 별도 금액은 남아 있지만 연결 세 항목의 대체 근거가 아니다.'),
    'MIX_T3_050':('PRIMARY_SEPARATE_SCOPE_RETAINED_CONNECTED_COMPARISON_LOST','별도 특수관계자 제품·용역매출949:352와 그 합계1,731,078,694천원은 유지. 과거 답변이 별도로 비교했던 연결545:385는 손실. 범위를 섞거나 연결 금액까지 보존됐다고 주장하지 않는다.'),
}
reviews=[]
for a in audit:
    lost=a['arms']['K12']['historical_cited_sources_lost']
    if not lost: continue
    if a['case_id'] in notes:
        status,note=notes[a['case_id']]
    elif a['historical_group']=='refusal':
        status,note='REFUSAL_NOT_EVALUATED','기존 인용 출처 교체를 기록. 새 답변 없이 거절 성공/실패를 판정하지 않는다.'
    else:
        assert a['historical_group']=='diagnostic_or_hold'
        status,note='HOLD_REMAINS_UNRESOLVED','기존 질문/평가 범위 HOLD 유지. 출처 손실을 기록하되 정확도 회귀로 집계하지 않는다. KBF의 고정 진단 패널 필수항목은 별도 기존 대체근거로 보존된다.'
    reviews.append({'case_id':a['case_id'],'historical_group':a['historical_group'],'lost_citations':lost,'finding':status,'note':note})
assert len(reviews)==16
assert Counter(r['historical_group'] for r in reviews)=={'common_answerable':10,'diagnostic_or_hold':3,'refusal':3}
absence={}
for cid,values in {'MIX_T3_048':['9,864,474'],'CEL_T3_040':['2,526,280','48,885,812','25,163,510'],
                   'SKH_T3_080':['573,884','906,120'],'SAM_T3_028':['5,037,579','3,558,358'],
                   'CEL_T1_038':['2,176,431,531']}.items():
    absence[cid]={v:[d['chunk_id'] for d in packets[cid,'K12']['documents'] if v in d['text']] for v in values}
    assert all(not matches for matches in absence[cid].values())
source_review={'reviewer':'same assistant; source-grounded, not blinded or independent',
    'scope':'All77 mechanical audit, all16 historical citation-loss cases triaged;10 common-answerable cases inspected with source witnesses. No complete new gold annotation, unseen-report test, generated answers or independent semantic grading.',
    'groups':dict(Counter(r['historical_group'] for r in reviews)),'cases':reviews,'verified_quote_witnesses':facts,
    'exact_value_absence_checks':absence,'absence_limit':'Exact strings alone do not establish semantic absence; source readings and table scope support bounded findings. No exhaustive alternative-unit/rounding oracle.'}
save('source_review.json',source_review)

gains=[]; losses=[]
for c in panel['cases']:
    for u in c['units']:
        a,b=bool(u['stages']['A12']['packet']),bool(u['stages']['K12']['packet'])
        if a!=b:(gains if b else losses).append({'case_id':c['case_id'],'unit_id':u['unit_id']})
assert len(gains)==0 and len(losses)==4
parity=prior.load(OUT/'baseline_parity.json')
errors=[]
for cid,r in results.items():
    old=prior.load(prior.BASE/'live/retrieval'/f'{cid}.json')['bm25']
    errors.extend(abs(a['score']-b['score']) for a,b in zip(r['lexical']['A12'],old))
assert max(errors)==0
parity['BM25_max_score_error']=max(errors)
save('baseline_parity.json',parity)
preservation=preserve()
before=prior.load(OUT/'before.json')
preservation['unique_protected_files']=len({str((ROOT/p).resolve()).lower() for p in before})
preservation['hash_entries']=preservation.pop('protected_files')
save('preservation.json',preservation)
execution=prior.load(OUT/'execution_result.json')
execution.update(status='COMPLETE_NOT_ADOPTED',preservation=preservation,focused_tests_passed=7,
    valid_treatment_runs=1,preflight_correction='knlm unavailable in pinned package; cong fixed before treatment; see preflight_receipt.json',
    verification_status='PARTIAL: exact baseline and offline mechanics verified; bounded same-assistant source review, no generated answers or independent holdout',
    command='.venv/Scripts/python.exe -u -B -X utf8 benchmarks/results/tokenizer_kiwi_offline_20261022/run.py run')
save('execution_result.json',execution)
save('review.json',{'status':'COMPLETE_NOT_ADOPTED','decision':'고정한 전체 형태소 치환 K12는 기존 A12보다 필수근거를 덜 보존하므로 미채택. 자동 추가 튜닝 없음.',
    'summary':prior.load(OUT/'automated_summary.json')['arms'],'panel_gains':gains,'panel_losses':losses,
    'source_review':source_review,'mechanism':prior.load(OUT/'mechanism_diagnostics.json'),'execution':execution})
print(prior.encoded({'status':execution['status'],'gains':gains,'losses':losses,'preservation':preservation}))
