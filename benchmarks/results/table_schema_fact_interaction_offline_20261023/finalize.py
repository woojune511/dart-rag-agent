"""Reconcile frozen evidence reviews and write a bounded report, no new run."""
from collections import Counter
import hashlib
import json
import run

OUT,ROOT=run.OUT,run.ROOT
load,save,sha=run.load,run.save,run.sha
req=load(OUT/'required_evidence_review.json')
all77=load(OUT/'all77_evidence_review.json')
contract=load(OUT/'evaluation_contract.json')
frozen_cases={c['case_id']:c for c in contract['cases']}
assert len(all77['cases'])==77 and {c['case_id'] for c in all77['cases']}==frozen_cases.keys()
for inp in all77['inputs']:assert sha(ROOT/inp['path'])==inp['sha256'],inp['path']
receipts=0;packet_receipts=0;criteria=0;unreviewed=0
categories=Counter();by_group={}
for case in all77['cases']:
    cid=case['case_id'];gold=frozen_cases[cid]
    assert case['group']==gold['group'] and case['required_units_unchanged']==gold['required_units']
    assert case['HOLD_lifted'] is False
    criteria+=len(case['required_units_unchanged'])
    assert {u['unit_id'] for u in case['criterion_review_status']}=={u['unit_id'] for u in gold['required_units']}
    unreviewed+=sum(u['finding']=='NOT_REASSESSED_FOR_FULL_SEMANTIC_SUFFICIENCY' for u in case['criterion_review_status'])
    category=case['bounded_semantic_review']['category'];categories[category]+=1
    by_group.setdefault(case['group'],Counter())[category]+=1
    packets={}
    for arm,info in case['input_receipts'].items():
        p=ROOT/info['path'];packet=load(p);packets[arm]=packet
        assert sha(p)==info['file_sha256'] and run.digest(packet)==info['canonical_json_sha256']
        assert len(run.encoded(packet).encode('utf8'))==info['packet_bytes']
        packet_receipts+=1
    for receipt in case['actual_packet_source_receipts']:
        packet=packets[receipt['arm']]
        doc=next(d for d in packet['documents'] if d['chunk_id']==receipt['owner_uid'])
        assert doc['source_id']==receipt['source_id']
        if receipt['field']=='text':
            start,end=receipt['character_span']
            assert doc['text'][start:end]==receipt['quote']
            assert hashlib.sha256(doc['text'].encode('utf8')).hexdigest()==receipt['text_sha256']
        else:
            assert receipt['field']=='table_fact_units'
            w=doc['table_fact_units'];r,c=receipt['at']
            unit=next(u for u in w['units'] if u[:2]==[r,c])
            assert w['cells'][unit[2]]==receipt['value']
            assert [w['cells'][i] for i in unit[3]]==receipt['row_axes']
            assert [w['cells'][i] for i in unit[4]]==receipt['column_axes']
            assert all(w[k]==v for k,v in receipt['frame'].items())
            assert receipt['physical_key']==w['document_sha256']+'|'+w['table_locator']+f'|{r}:{c}'
        receipts+=1
assert dict(categories)==all77['review_categories'] and criteria==154
physical=load(OUT/'physical_audit.json');preserve=load(OUT/'preservation.json')
assert physical['status']=='PASS' and not physical['issues'] and not preserve['changed']
assert load(OUT/'required_reconciliation.json')['status']=='PASS_BOOKKEEPING_AND_INPUT_RECEIPTS'
agg=load(OUT/'aggregate_summary.json');loss=load(OUT/'loss_layers.json')
assert agg['cases']==agg['exact_A12_fact160_replays']==77
assert sum(loss['counts'].values())==agg['physical_unit_changes']['lost']==2204
verdict={'status':'COMPLETE_OFFLINE_NOT_ADOPTED','external_model_API_calls':0,'cost_usd':0,
    'hypothesis_gate':'FAIL: Samsung common mandatory evidence regresses after augmentation; no new frozen required unit in the bounded panel.',
    'positive_interaction':'LGES product-table USD source context is restored by augmentation; outside legacy26 denominator.',
    'redundant_retrieval_gain':'Motional ownership/carrying already recovered by A12_fact160; S12 has no incremental unit on current4.',
    'review_reconciliation':{'Motional_net_profit':'Both reviewers observe loss of -803,742 supplementary investment-row profit. Frozen four-item profit_summary is incomplete in both augmented arms; do not count a new binary failure or silently call this no loss.',
        'HOLD':'Conditional Hyundai US sales operand loss is reported separately; no HOLD promotion.',
        'LGES':'Restored product-table USD is outside legacy26; not substituted with raw-material USD.',
        'no_regression_claim':'Confirmed common loss suffices to fail gate; remaining unknowns do not count as passes.'},
    'all77_review_validation':{'cases':77,'criteria_unchanged':criteria,'packet_file_and_canonical_hashes':packet_receipts,
        'actual_text_or_fact_receipts_checked':receipts,'not_fully_reassessed_criteria':unreviewed,
        'categories':dict(categories),'by_group':{g:dict(v) for g,v in by_group.items()}},
    'interpretation_limits':['No new answers or accuracy/faithfulness/refusal score.',
        'Development-exposed cases; no new-report generalization.',
        'Augmentation plus160KiB is a combined delivery package, not a pure-format intervention.',
        'S12 is schema plus frozen stream allocation, not all possible table search methods.',
        'Physical source linkage does not certify financial meaning or model interpretation.'],
    'input_hashes':{n:sha(OUT/n) for n in ['results.json','required_evidence_review.json','all77_evidence_review.json','physical_audit.json','preservation.json','loss_layers.json']},
    'disposition':'Do not advance S12 to paid answer generation or production adoption. Retain existing runtime and experimental A12_fact160 comparison baseline.'}
save('final_adjudication.json',verdict)

label={'A12_original':'기존 검색 · 원래 전달64KiB','S12_original':'표 스키마 검색 · 원래 전달64KiB',
       'A12_fact160':'기존 검색 · 표 보강160KiB','S12_fact160':'표 스키마 검색 · 표 보강160KiB'}
lines=['# 표 근거 보강 후 표 스키마 검색 재검증', '',
    '2026-10-23 · academic-research-suite · 저장된77문항 오프라인 비교 · 외부 모델 API0회 / $0', '',
    '**결론: 이전 표 스키마 검색 S12는 이번에도 채택하지 않는다.** 표 보강으로 LG에너지솔루션 가격표의 USD 단위 누락은 복구됐지만, 삼성 연결 배당금 근거 손실이 남았다. Motional 지분율·장부금액에서 기존 S12가 보였던 이점은 기존 검색 A12에 같은 보강을 적용해도 얻어졌다. 이번 실행은 완료됐고, 필수 근거 회귀가 없어야 한다는 다음 단계 조건은 통과하지 못했다.', '',
    '이 결과는 “이전에 실패한 방법은 다시 실험해도 소용없다”는 뜻이 아니다. 전달 단계가 바뀌면 개별 결과도 바뀐다는 사례는 확인했다. 다만 개선된 기준선보다 추가 이득이 있는지 다시 비교해야 하며, 이번 S12는 그 조건을 충족하지 못했다.', '',
    '**비교 조건**', '',
    '저장된 A12와 S12 각각에 원래64KiB 전달과 같은 표 보강160KiB 전달을 적용했다. 각 검색 조건 안에서 후보·점수·Dense·BM25·RRF 순서·선택12개·질문·명시적 보고서 범위를 고정했다. S12는 기존 청크 BM25와 표 스키마 검색 흐름을 고정된 규칙으로 혼합한 이전 실험이며, 이번에 검색을 다시 실행하거나 배분을 조정하지 않았다.', '',
    '각 조건의 기존 실제 전달 문서는 그대로 보존했다. 원래64KiB 한도에서 생략됐던 문서를160KiB에서 다시 채워 넣지 않았다. 원문 연결이 검증된 값·행·열·문맥을 같은 projector, 첫 표 소유자, 원문 순서, 원자적 바이트 예산 규칙으로 첨부했다. 기존746개 청크의 검증 결과를 그대로 사용하고 새로 필요한 S12 청크100개에 같은 검증기를 적용했다(96개 허용,2개 유효 숫자 unit 없음,2개 표 payload 없음).', '',
    '기존 A12 보강 결과는 이전160KiB 실험과77/77 동일하게 재현됐다. 별도의 답변 생성이나 평가 모델 호출은 하지 않았다. 표 보강과160KiB는 하나의 전달 패키지이므로 표 형식만의 효과로 해석하지 않는다.', '',
    '**동결된 필수 근거 패널**', '',
    '아래는 답변 정답률이 아니라 실제 입력에 필요한 근거가 있는지의 판정이다. 기존 패널10문항26항목은 공통8문항20항목과 HOLD2문항6항목으로 나눴다. Current4는 기존 미완료4문항13항목이며 일부 문항이 앞 패널과 겹치므로 수치를 합산하지 않는다.', '',
    '| 조건 | 공통 필수 근거 /20 | 공통 완비 문항 /8 | HOLD 조건부 근거 /6 | Current4 근거 /13 | Current4 완비 /4 |',
    '|---|---:|---:|---:|---:|---:|']
for a in run.ARMS:
    s=req['summary'][a]
    lines.append(f"| {label[a]} | {s['legacy_common_present']} | {s['legacy_common_complete_cases']} | {s['legacy_HOLD_present']} | {s['current4_required_units_present']} | {s['current4_complete_cases']} |")
lines+=['',
    '공통 패널에서 S12의 차이는 보강 전후 모두18→17로 동일했다. Current4에서 S12의 기존 이점6→8은 보강 후9→9로 사라졌다. 이는 전달 개선이 검색 개선의 일부 이득을 이미 달성한 사례다. HOLD의6→4는 현대차 미국 판매 두 값의 조건부 손실이며 공통 성능에 합산하지 않는다.', '',
    '| 사례 | 확인된 결과 | 해석 |','|---|---|---|',
    '| 삼성 연결 배당금 MIX_T3_048 | A12 보강에는9,864,474백만원 지급 근거가 있고 S12 보강에는 없음. 별도9,810,119백만원과 환원정책은 남음 | 다른 범위의 수치는 대체 근거로 인정할 수 없음. 최종 선택에서 빠진 표를 보강만으로 복구하지 못함 |',
    '| LG에너지솔루션 LGE_T2_052 | S12 원래 입력에서 빠진 제품 가격표 USD가 S12 보강에서 같은 표의 원문 연결 문맥으로 복구 | 보강과 검색의 상호작용이 확인된 긍정 사례.26항목 밖의 별도 결과이며 원재료 표 USD를 제품 표에 전용한 것이 아님 |',
    '| Motional HYU_T3_072 | 두 보강 조건 모두 허용된 범위별 지분율·장부금액 대체 근거를 제공. 필수4개 요약손익은 둘 다 미완료 | S12의 추가 필수 근거 이득 없음. A12의 보충 순손익 -803,742는 S12 예산에서 누락돼 별도 손실로 남김 |',
    '| SK이노베이션 SKI_T1_068 | 두 보강 조건 모두 배터리 손익과 전체 영업이익의 화폐단위 연결 유지 | 보강으로 얻은 축 연결이 유지됨. S12만의 추가 복구로 집계하지 않음 |',
    '| 현대차 미국 판매 HYU_T2_010 · HOLD | A12의87.0/78.1만대 서술이 두 S12 조건 모두 없음 | 조건부 근거 손실. 기존 질문 판정 HOLD는 유지 |', '',
    'Motional의 투자 표 첫 전달 소유자는 A12의3번째 문서에서 S12의9번째로 바뀌었다. 해당 표에서 실제 허용된 unit은1,701→1,426개였고, 보충 순손익이 예산에 걸렸다. 지분율·장부금액은 다른 전달 출처에 남아 있으므로 그 필수 항목까지 모두 소실됐다고 세지 않았다. 서로 다른 범위의26%/700,691백만원과25.81%/1,294,367백만원을 하나의 표 수치로 합치지 않았다.', '',
    '**전체77문항에서 확인한 범위**', '',
    '공통46·거절19·HOLD12 구분과 기존154개 기준을 유지했다.77문항 모두 문서·값 묶음 차이와 바이트 크기를 검사했다. 기존 인용 손실20건과 축 연결 감시19건을 포함한 중복 제거34문항을 제한된 의미 검토 대상으로 읽었다. 90/154기준은 이 전체77검토에서 의미 충족 여부를 전부 다시 판정하지 않았고, 미검토·모호함을 통과로 처리하지 않았다. 별도 필수 근거 패널과 검토 대상이 겹친다.', '',
    '| 전체77 검토 분류 | 문항 수 |','|---|---:|',
    '| 검토한 기존 근거 유지 | 17 |','| 출처 ID는 빠졌으나 동등한 대체 근거 확인 | 10 |',
    '| 필수 근거 손실 확인 | 2: 공통1, 조건부 HOLD1 |','| 주체·축·부분 근거 해석 미해결 | 5 |','| 의미 전수 판정 미실시 | 43: 거절19 포함 |', '',
    '따라서 “나머지76문항은 회귀 없음” 또는 “전체 정확도 변화 없음”이라고 주장하지 않는다. 확인된 공통 회귀1건만으로도 사전 다음 단계 조건을 실패하며, 남은 불확실성 때문에 결론이 채택 쪽으로 바뀌지는 않는다.', '',
    '**전달량과 물리적 무결성**', '',
    '| 조건 | 실제 전달 문서 발생 수 | 평균 입력 바이트 | 전달 숫자 unit 발생 수 |','|---|---:|---:|---:|']
for a in run.ARMS:
    s=agg['arms'][a]
    lines.append(f"| {label[a]} | {s['actual_source_events']:,} | {s['mean_bytes']:,.0f} | {s['table_unit_events']:,} |")
lines+=['',
    'S12 보강은 평균 입력을 약10.7% 늘렸고 숫자 unit 전달은17,772→20,607건이었다. 그러나 기존 대비5,039건이 추가되는 동시에2,204건이 빠졌다. 이는 표의 숫자 셀 전달 발생 수이며 독립 필수 사실 수가 아니다. 빠진2,204건 중1,874건은 실제 S12 전달 문서의 표 payload에 해당 표가 없었고330건은 보강 예산에서 제외됐다. 원래 문서 자체가 없는 경우에는 최종 선택과 기존 전체 문서 바이트 생략을 이 집계에서 분리하지 않았다.', '',
    '두 보강 조건154개 입력을 원문과 대조했다.434개 물리 표,17,993개 고유 물리 unit,30,236개 셀,2,206개 표별 문맥 구간에서 위치·값·행/열 의존·문맥 연결 불일치는0건이었다. 두 조건에 공통으로 전달된 unit의 의존 내용 변경도0건이었다. 이 검사는 기간·주체·단위의 의미 해석 또는 LLM 독해 성공을 인증하지 않는다.', '',
    '**다음 단계 판단과 보존**', '',
    '이번 우선순위1 비교는 여기서 종료한다. 현재 S12를 유료 답변 생성이나 앱 기본 검색으로 확대하지 않는다. 다음 재검증 후보를 고를 때는 표 보강으로 이미 복구된 항목을 새 이득으로 세지 않고, 개선된 A12 기준선에서도 빠지는 필수 근거를 실제로 가져오는지부터 확인하는 것이 필요하다. 다른 검색 방식에 대해서도 이 결과만으로 실패를 일반화하지 않는다.', '',
    '기존 구현·다른 미커밋 변경·.env·v12 store를 보존했다.5,708개 보호 파일과 활성 store11개 파일의 바이트, Git HEAD/index/status가 모두 동일했다. store/SQLite를 열지 않았고 앱 재시작·모델 API 호출·검색 재실행·답변 생성은0회다. 산출물은 이 별도 ignored 실험 폴더에만 기록했으며 채택·커밋·push는 수행하지 않았다.', '',
    '이 실험은 개발 과정에서 이미 확인한77문항을 재사용한 오프라인 근거 실험이다. 별도 문서의 일반화, 답변 정확도·출처 충실도·거절 성능의 향상, 통계적 유의성을 측정하지 않았다. 두 소스 검토 작업은 fork 없이 분리된 입력으로 수행했고 요청 모델은 gpt-6-astra/xhigh였으나 제공자가 확인한 실행 모델 식별은 없었다. 과거 결과를 알고 있는 비맹검 검토이며 독립 모델 검증으로 주장하지 않는다.', '',
    '**재현 근거**', '']
for name,desc in [('protocol.json','동결 조건'),('results.json','77문항 네 조건 결과'),('required_evidence_review.json','필수 근거 패널과 원문 위치'),
                  ('all77_evidence_review.json','전체77 검토 범위·미해결'),('physical_audit.json','원문 물리 검사'),('loss_layers.json','손실 단계 분류'),
                  ('preservation.json','기존 상태 보존'),('final_adjudication.json','최종 통합 판정')]:
    lines.append(f'- [{desc}]({(OUT/name).as_posix()})')
lines+=['','ARS Material Passport: experiment-agent run→validate · VERIFIED_SAVED_INPUT_REPLAY / ANALYZED_BOUNDED_EVIDENCE · 완료, 미채택.']
(OUT/'report.md').write_text('\n'.join(lines)+'\n',encoding='utf8')
(OUT/'passport.md').write_text('# Material Passport\n\n- Origin Skill: academic-research-suite / experiment-agent run and validate\n- Date: 2026-10-23\n- Status: COMPLETE_OFFLINE_NOT_ADOPTED\n- Verification: all77 saved replay;154 augmented packet physical checks; bounded evidence review, not full semantic or answer validation\n- External model API calls:0; cost:$0\n- Gate: confirmed mandatory evidence regression; no answer-generation expansion\n- Review runtime: two workers requested gpt-6-astra/xhigh, fork_turns=none; actual provider identity unattested; unblinded development-exposed review\n- Preservation:5708protected files, .env,11active v12 store files, Git HEAD/index/status unchanged\n- Report:report.md\n',encoding='utf8')
save('all77_entry.json',{'kind':'tool_receipt','step':'all77_bounded_review_reconciliation','status':'passed','command':'Delegated source review; parent finalize.py',
    'exit_status':0,'retries_used':0,'input_sha256':{'all77_evidence_review.json':sha(OUT/'all77_evidence_review.json'),'finalize.py':sha(OUT/'finalize.py')},
    'output_sha256':sha(OUT/'final_adjudication.json'),'gate_tokens':['77_CASE_MATRIX','154_CRITERIA_FIXED','89_SOURCE_RECEIPTS','UNREVIEWED_NOT_PASS']})
save('final_entry.json',{'kind':'tool_receipt','step':'final_report_and_disposition','status':'passed','command':'finalize.py',
    'exit_status':0,'retries_used':0,'input_sha256':{'final_adjudication.json':sha(OUT/'final_adjudication.json'),'preservation.json':sha(OUT/'preservation.json')},
    'output_sha256':sha(OUT/'report.md'),'gate_tokens':['COMPLETED_NOT_ADOPTED','API0','NO_RUNTIME_CHANGES']})
print(json.dumps({'status':verdict['status'],'all77_packet_hashes':packet_receipts,'source_receipts':receipts,'not_fully_reassessed_criteria':unreviewed,'report':str(OUT/'report.md')},ensure_ascii=False))
