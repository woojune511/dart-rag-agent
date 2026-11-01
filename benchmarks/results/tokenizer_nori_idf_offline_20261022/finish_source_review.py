"""Source-bound manual annotations; does not modify any ranking or criterion."""
from run import OUT,prior,save
cache={}

def packet(cid,arm):
    if (cid,arm) not in cache:cache[cid,arm]=prior.load(OUT/'packets'/f'{cid}_{arm}.json')
    return cache[cid,arm]

def witness(cid,arm,uid,quote):
    d=next(d for d in packet(cid,arm)['documents'] if d['chunk_id']==uid)
    assert quote in d['text'],(cid,arm,uid,quote)
    return dict(case_id=cid,arm=arm,uid=uid,quote=quote,offset=d['text'].index(quote),
                source_text_sha256=prior.text_sha(d['text']),context=d['context'])

rows=[]
def add(cid,arm,disposition,rationale,refs,absent=()):
    text='\n'.join(d['text'] for d in packet(cid,arm)['documents'])
    assert all(t not in text for t in absent),(cid,arm,absent)
    rows.append(dict(case_id=cid,arm=arm,disposition=disposition,rationale=rationale,
        witnesses=[witness(cid,*r) for r in refs],
        exact_strings_absent=list(absent),absence_limit='Exact-string absence is a locator check; semantic disposition follows source review, not substring scoring.'))

add('MIX_T3_048','N12','required_evidence_loss',
    '연결 실제 현금 지급9,864,474백만원이 빠졌다. 남은9,809,438 선언배당 및연9.8조원 정책은 실제 지급의 대체 근거가 아니다. RRF14로 최종12 밖이며 바이트 생략은 아니다.',
    [('A12','20240312000736:127:6','배당금의 지급 | (9,864,474)'),
     ('N12','20240312000736:591:1','현금배당금총액(백만원) | 현금배당금총액(백만원) | 9,809,438'),
     ('N12','20240312000736:590:0','2024년부터 2026년까지 3년간 발생하는 잉여현금흐름의 50%')],['9,864,474','9864474'])
for arm in ('N12','NL12'):
    add('CEL_T3_040',arm,'three_required_units_lost',
        '연결 gross 평가손실·환입·폐기 세 항목이 RRF15로 빠졌다. 별도1,010,161/45,139,758/22,312,563천원과 연결 순환입21,196백만원은 세 원래 항목을 복구하지 못한다. 두 treatment 문맥 출처 집합은 동일하다.',
        [('A12','20240318000913:517:357','재고자산평가손실 | 2,526,280'),
         ('A12','20240318000913:517:357','재고자산평가손실환입 | (48,885,812)'),
         ('A12','20240318000913:517:357','재고자산폐기손실 | 25,163,510'),
         (arm,'20240318000913:917:320','재고자산평가손실 | 1,010,161'),
         (arm,'20240318000913:318:158','(-)21,196백만원')],['2,526,280','48,885,812','25,163,510'])

add('SAM_T3_028','L12','connected_amount_support_lost',
    '연결당기 재고평가5,037,579백만원이 없어지고 별도3,558,358 및비용 포함 설명은 남는다. 연결금액을 대신할 출처는 이번 문맥에서 확인하지 못했다. 고정26항목 외 추가 회귀 사례다.',
    [('A12','20240312000736:319:191','재고자산평가손실(환입) 등 | 5,037,579'),
     ('L12','20240312000736:532:148','재고자산평가손실(환입) 등 | 3,558,358'),
     ('L12','20240312000736:210:82','동 비용에는 재고자산평가손실 금액이 포함되어 있습니다.')],['5,037,579','5037579'])
add('CEL_T1_038','L12','required_denominator_lost',
    '연결 당기 매출2,176,431,531천원 분모가 빠졌다. 상각총액182,286,838은 남지만 매출2,283,967,480은전기(period_focus: prior)로 당기 영업이익률 계산에 대신 쓸 수 없다.',
    [('A12','20240318000913:185:25','매출액 | 1,873,430,064 | 500,776,927 | 5,143,344 | (202,918,804) | 2,176,431,531'),
     ('L12','20240318000913:360:200','무형자산상각비 | 145,878,128 | 36,171,696 | 209,548 | 27,466 | 182,286,838'),
     ('L12','20240318000913:186:26','[period_focus: prior]')],['2,176,431,531','2176431531'])
add('LGE_T2_052','L12','product_unit_context_lost_primary_trend_retained',
    '제품가격1.89/1.62표는 남고 그USD표제가 빠졌다. 원재료표23:1의USD를 제품표에 빌려 쓰면 안 된다. 주요 원재료 및lagging 근거는 남으므로 질문전체 실패로 판정하지 않는다.',
    [('A12','20240314001110:20:1','(단위 : USD)'),
     ('L12','20240314001110:21:2','전동공구용 배터리 | 1.89 | 1.62'),
     ('L12','20240314001110:897:3','배터리 판매가격 대비 투입 원재료비가 높아서 발생하는 Lagging 영향')])
add('NAV_T3_032','L12','primary_evidence_preserved_secondary_note_lost',
    '1238:137의93백만원 사업양수도 포함 각주는 빠졌지만 연결CapEx692.3십억원과시설 범위·세종 자산·차입원가 자본화 자료는 남는다. 부수 인용의 손실을 핵심 근거 회귀로 세지 않는다.',
    [('A12','20240318000844:1238:137','취득한 금액 93백만원'),
     ('L12','20240318000844:40:4','CapEx | 692.3 | 756.2'),
     ('L12','20240318000844:1236:135','자본화된 차입원가 | | | | | | | | 4,418,000')])
add('CEL_T3_015','L12','primary_evidence_preserved_secondary_sources_changed',
    '합병일·목적·교부비율은575:415와969:372에 남는다. 기존별도 파생상품 등부수 인용 손실은 합병질문의 핵심 회귀로 보지 않는다.',
    [('L12','20240318000913:575:415','합병기일 | 2023-12-28'),
     ('L12','20240318000913:575:415','합병의 목적 | 통합된 자원의 대규모 투자, 개발-생산-판매 일원화')])
add('CEL_T3_040','L12','primary_evidence_preserved_separate_comparison_lost',
    '과거별도 비교표917:320은 빠졌지만 기존필수 연결gross 세 항목이517:357에 모두 남는다.',
    [('L12','20240318000913:517:357','재고자산평가손실 | 2,526,280'),
     ('L12','20240318000913:517:357','재고자산평가손실환입 | (48,885,812)'),
     ('L12','20240318000913:517:357','재고자산폐기손실 | 25,163,510')])
add('HYU_T1_009','L12','reported_ratio_retained_recalculation_support_reduced',
    '외부고객 부문합계표76:0과162,663,579백만원 분모는 빠졌다. 공시 금융매출22,401,156 및비중13.8%는113:0/107:0에 남아 답변 전체 회귀로 단정하지 않는다. 13.77%정밀 재계산의 근거는 약해졌다.',
    [('L12','20240313001451:113:0','매출액 | 22,401,156 | 13.8')],['162,663,579'])

save('root_source_review.json',{'reviewer':'Parent assistant, unblinded, bounded source review','scope':'All7 L12 common-answerable citation-loss cases, plus frozen-panel N12/NL12 losses. Refusal outcomes unscored; exact-quote checks do not prove overall semantic correctness.','rows':rows})
print('Source review rows:',len(rows),'exact witnesses:',sum(len(r['witnesses']) for r in rows))
