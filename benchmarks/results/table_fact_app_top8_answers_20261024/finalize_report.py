"""Publish one evidence-bounded report for this completed, sealed experiment."""
from common import *
from decimal import Decimal

def link(name,path=None):
    return f'[{name}]({(OUT/(path or name)).as_posix()})'

def main():
    s=load(OUT/'summary.json');v=load(OUT/'closeout_validation.json');rows=load(OUT/'graded_answers.json')
    perf=load(OUT/'performance.json');protocol=load(PREP/'protocol.json')
    need(v['status']=='PASS' and len(rows)==72,'Incomplete evaluation')
    new_regressions=[x for x in s['pairs'] if any(
        {'PASS':3,'PARTIAL':2,'AMBIGUOUS':1,'FAIL':0}[x['C'][axis]] <
        {'PASS':3,'PARTIAL':2,'AMBIGUOUS':1,'FAIL':0}[x['A'][axis]]
        for axis in ('accuracy','completeness','faithfulness')) or
        (not x['answerable'] and x['A']['appropriate_abstention']=='PASS' and x['C']['appropriate_abstention']!='PASS')]
    need(not new_regressions,'Unexpected post-adjudication regression; inspect before report')
    decision={
      'status':'MIXED_INCONCLUSIVE_FOR_DEFAULT_ROLLOUT',
      'prespecified_screen':protocol['metrics']['decision'],
      'answerable_complete_and_supported':{'A':26,'C':28,'denominator_per_arm':30,'delta_pp':s['delta_all_pass_pp']},
      'accuracy_and_completeness_unchanged':True,
      'gain_each_repeat':s['gain_each_repeat'],
      'nonnegative_report_count':s['nonnegative_report_count'],
      'new_material_regressions_observed_after_source_adjudication':0,
      'rollout_or_runtime_change_performed':False,
      'reason':'The prespecified positive gain in both repetitions is not met. The two answerable gains are noncentral citation details in repeat2, not recovered numeric/table required facts. Do not generalize this exposed3-report result or infer a160KiB budget requirement.',
      'interpretation_sensitivity':{'not_a_replacement_for_frozen_primary_scores':True,
        'if_both_noncentral_H15_H17_extras_were_tolerated':{'A_all_pass':28,'C_all_pass':28,'n_per_arm':30},
        'H12_nearest_category_permissive_reading':'Would affect refusal completeness, but A remains0/2 appropriate refusals because abstained=false in both; C remains1/2.'}
    }
    put(OUT/'decision.json',decision)
    checks=[
      ('Simpson paradox','Report-level gains are Kia0,SDS0,Amore+2; repeat-level gains0,+2. No reversal, but all answerable gain is concentrated in one report and one repeat.'),
      ('Ecological fallacy','72 outputs are not72 independent test questions. The panel has18 exposed questions,15 answerable and3 refusal, nested in3 reports; repetitions share inputs.'),
      ('Berkson selection','Handwritten, previously evaluated3-report panel. It is an exploratory transfer/regression sample, not a representative or unseen holdout.'),
      ('Collider bias','No outcome-conditioned exclusions or post-result subgroup adjustment. Answerability and company strata were frozen before execution.'),
      ('Base-rate neglect','Answerable30 and refusal6 per arm are separate. The designed refusal prevalence is not an estimate of production traffic.'),
      ('Regression to mean','Fresh paired A and C responses were generated for the full frozen panel, not only earlier worst cases. Two repeats still do not establish stable effects.'),
      ('Survivorship bias','All72 authorized attempts succeeded and are retained/reviewed. Zero retries, invalid output replacements or missing-result exclusions.'),
      ('Look-elsewhere effect','There have been many prior project experiments. Report all axes/cases and the failed practical gate; do not present this selected follow-up as confirmatory significance.'),
      ('Forking paths','Requests, rubric and schedule frozen before calls. Raw outputs sealed before review. One explicit consistency adjudication applies the same original rule to R004/R006; no gold rewrite. Sensitivity is labeled separately.'),
      ('Correlation and causation','Fixed paired intervention supports a local descriptive A/C comparison. Stochastic removal of two prose extras is not proof of a table-binding mechanism; budget and representation were jointly specified and all C inputs fit64KiB.'),
      ('Reverse causality','Prepared hashes predate outputs; outputs could not alter executed questions/inputs. No response regeneration or feedback tuning.')
    ]
    stats={'coverage':'11/11 checked','confidence':'CAUTION','formal_significance_test_performed':False,
      'reason':'Three report clusters, dependent repeats, exposed panel, small interpretation-sensitive gains. Descriptive counts and paired differences only.',
      'checks':[{'type':k,'assessment':text} for k,text in checks]}
    put(OUT/'statistical_interpretation.json',stats)
    names={
      'H01':'기아 공장별 생산능력','H02':'기아 별도 RV 내수·수출 매출','H03':'기아 연결 연구개발비 증가액',
      'H04':'기아 ASP와 증가 배경','H05':'기아2026 북미 생산·공급 전략','H06':'기아 RV 영업이익률 거절',
      'H07':'삼성SDS 국내·중국 지역 매출','H08':'삼성SDS 개발비 자산화·비용 처리','H09':'삼성SDS 클라우드 매출 증가',
      'H10':'삼성SDS 상생펀드 예치금·제한','H11':'FabriX·Brity 제품 역할','H12':'FabriX 단독 매출 거절',
      'H13':'아모레퍼시픽 사업별 연결 매출','H14':'아모레퍼시픽·코스비전 부재료 매입',
      'H15':'아모레퍼시픽 생산 설비 투자 비중','H16':'려 샴푸 가격·조정 이유','H17':'아모레퍼시픽 채널 성장 설명','H18':'라네즈 미국 온라인 매출 거절'}
    case_lines=[]
    for cid in names:
        group=[r for r in rows if r['case_id']==cid]
        answerable=group[0]['answerable']
        counts={a:sum(r['all_pass'] if answerable else r['appropriate_abstention']=='PASS' for r in group if r['arm']==a) for a in ('A','C')}
        note={'H07':'양쪽 모두 소재지 기준 생략','H12':'A 거절 플래그2건, C1건 불일치','H15':'A2 코스비전 관계 인용 누락','H17':'A2 창립 수식어 추가'}.get(cid,'차이 없음')
        case_lines.append(f"| {cid} | {names[cid]} | {counts['A']}/2 | {counts['C']}/2 | {note} |")
    input_ratio=perf['C']['input_tokens']/perf['A']['input_tokens']
    cost_ratio=Decimal(perf['C']['estimated_usd'])/Decimal(perf['A']['estimated_usd'])
    report=f'''# 현재 앱 조건에서 표 근거 보강 답변 비교 — 2026-10-24

**실행은 완료했고, 기본 경로 적용 판단은 보류한다.** Terra·low·top8을 고정한 이번 비교에서 답변 가능 문항의 정확도와 필수 항목 충족률은 양쪽 모두 28/30이었다. 표 보강은 출처 충실도를 28/30에서30/30으로 높였지만, 차이는 두 번째 반복의 비중심 부가 설명 두 건에 한정됐다. 사전에 정한 ‘두 반복 모두 완전·근거충실 답변 증가’ 조건은 충족하지 않았다.

72회 모두 성공했고 실패·재시도는0회다. API 사용량과 사전에 고정한 단가로 계산한 비용은 **$1.0771543**, 생성 구간은 **189.16초(약3분9초)**였다. 허용 상한72회·$13.28·9,000초 안에서 완료했다. 이 시간은 검토 작업이나 앱 검색을 포함한 전체 사용자 응답 시간이 아니다.

**무엇을 비교했는가.** 이미 평가에 사용한 기아·삼성SDS·아모레퍼시픽 보고서의18문항을 각 조건에서2회 생성했다. 새 holdout이 아니라 노출된 전이·회귀 확인 패널이다. 답변 가능15문항×2회=30개와 거절3문항×2회=6개를 분리했다.

| 조건 | A: 기존 전달 | C: 표 보강 전달 |
|---|---|---|
| 모델·추론 | gpt-5.6-terra / low | 동일 |
| 검색 근거 | 저장된 RRF 상위8개 | 같은 문서·점수·순서 |
| 본문·문맥 | 현재 native 입력 | A를 그대로 보존 |
| 추가 표현 | 없음 | 기존에 연결·검증한 값/행/열/기간/주체/단위/출처 묶음 |
| 문맥 한도 | 64KiB | 160KiB |
| 생성 설정 | 원래 시스템 프롬프트·JSON schema, output8192, default tier | 동일 |

실제18문항의 C 입력은 모두64KiB 이내였고 최대63,978bytes였다. 따라서 **이번 결과로160KiB 한도가 필요하다고 주장할 수 없다.** H11은 A와C 입력 자체가 같다. Query reformulation, Nori, 후보 추가, RRF 변경, 새 검색·임베딩·ingest는 없었다. 과거 Sol·top12 결과와 이번 Terra·top8을 직접 빼서 모델 또는 문맥 수 효과로 해석하지 않는다. 사전 동결 조건은 [{PREP.name}/protocol.json]({(PREP/'protocol.json').as_posix()})에 있다.

**주평가: 답변 가능한15문항, 조건당30답변.** 아래 PASS는 동결한 필수 사실과 실제 인용 문맥을 대조한 엄격 판정이다. 필수 범위 일부만 생략해도 PARTIAL이므로, 정확도28/30을 ‘수치2건 오답’으로 해석하면 안 된다.

| 지표 | A 기존 | C 표 보강 | 차이 |
|---|---:|---:|---:|
| 정확도 PASS | 28/30 (93.3%) | 28/30 (93.3%) | 0 |
| 필수 항목 전부 충족 | 28/30 (93.3%) | 28/30 (93.3%) | 0 |
| 인용 출처 충실도 PASS | 28/30 (93.3%) | 30/30 (100%) | +2답변, +6.7%p |
| 위 세 축 모두 PASS | 26/30 (86.7%) | 28/30 (93.3%) | +2답변, +6.7%p |
| 필수 사실 충족 | 94/96 | 94/96 | 0 |
| 필수 사실 일부 생략 답변 | 2/30 | 2/30 | 0 |

두 미충족 답변은 모두 H07의 소재지 기준 생략이다. 해당 답변의 네 금액·기간·단위·연결 범위는 맞았다. 주평가에서 C가 새로 틀린 필수 값·기간·주체·단위는 관측되지 않았다. 판정 한계와 표본 범위 때문에 ‘회귀가 절대로 없다’는 보장은 아니다.

| 완전·근거충실 답변을 나눈 집계 | A | C |
|---|---:|---:|
| 반복1 | 14/15 | 14/15 |
| 반복2 | 12/15 | 14/15 |
| 기아 | 10/10 | 10/10 |
| 삼성SDS | 8/10 | 8/10 |
| 아모레퍼시픽 | 8/10 | 10/10 |

보고서3개 모두 비악화였지만, 이득은 아모레퍼시픽의 반복2에만 나타났다. 사전 실용 판정 조건 중 ‘두 반복 모두 양의 차이’가 실패하여 **MIXED / INCONCLUSIVE**다. 이 조건은 통계적 유의성 검정이 아니다.

**거절3문항은 별도 평가했다.** 적절한 거절은 A4/6→C5/6이었다. 동결 기준은 범위를 한정한 정보 부족 설명, 요청된 가까운 공시값, 임의 값 생성 없음과 `abstained=true`를 함께 요구한다. 본문만 보면 양쪽6/6 모두 요청한 미공시 수치를 만들어내지 않았다. 이는 완전한 거절 성공률과 다른 관찰이다.

H12에서 A는2회 모두 IT서비스 전체를 ‘가장 가까운 공시’라고 부르고 정확한 클라우드 금액은 부가 항목으로 제시했다. C는2회 모두 클라우드 집계를 먼저 제시했다. 금액을 새로 찾아낸 개선이 아니라 범주 선택·설명 차이다. A2회와 C반복2는 본문에서 단독 매출 확인 불가라고 답하면서도 `abstained=false`를 반환했다. C의 거절 개선은1회만 재현됐다.

거절 답변의 충실도는 최종 일관성 판정 후 양쪽5/6이다. A반복2와 C반복2 모두 인용 매출표에 없는 FabriX–클라우드 포함 가능성을 덧붙였다. 수치를 발명하거나 포함을 확정한 오류로 확대하지 않고, 제한된 비중심 근거 부족으로 PARTIAL 처리했다.

**차이를 만든 사례와 남은 실패 경계.**

- H07: `20260310002989:147:32`는 실제 문맥8위에 있고 ‘연결실체의 지역별 영업현황(소재지 기준)’을 명시한다. A/C 네 답변 모두 이를 생략했다. 이 replay에서 해당 문제는 후보·문맥 누락이 아니라 답변 단계의 필수 범위 생략이다. 값 표와 별도 표제의 의미 연결을 이번 보강만으로 해결하지 못했다.
- H15: 네 답변 모두21,870÷91,560×100=23.9%로 맞았다. A반복2의 ‘종속회사(코스비전)’ 설명은 문맥1위 `49:12`에 근거가 있지만 답변은 `48:11`만 인용했다. C반복2는 그 부가 설명을 쓰지 않았다. 실제 인용의 누락 개선이며 계산 정확도 개선이나 없는 사실의 복구가 아니다.
- H17: 네 답변 모두 온라인·MBS 활동과 성장 관계를 맞췄다. A반복2가 원문 ‘80주년’에 ‘창립’을 추가한 반면 C는 추가하지 않았다. 엄격한 인용 기준의 소폭 차이며 표 숫자 읽기의 개선 증거로 볼 수 없다.
- H12: 표 보강 뒤에도 거절 플래그 불일치와 비중심 범주 추정이 남았다. 순위·후보를 바꾸지 않은 이번 실험으로 이 문제가 안정적으로 해결됐다고 할 수 없다.

H15·H17의 부가 표현을 허용하는 완화된 해석을 가정하면 완전·근거충실 답변은 A28/30=C28/30이 된다. 이는 **동결한 주평가를 대체하는 점수가 아니라 해석 민감도**다. 엄격 점수의 개선은 유지하되 작은 두 경계 판정에 의존한다는 점을 함께 남긴다. H12의 가까운 범주 표현을 더 관대하게 읽어도 A의 거절 플래그 실패는2회 모두 남는다.

**18문항 전체 결과.** 답변 가능한 문항은 세 축 모두 PASS, 거절 문항은 적절한 거절 기준으로 표시했다. 분모는 각각2회다.

| 문항 | 대상 | A | C | 관찰 |
|---|---|---:|---:|---|
{chr(10).join(case_lines)}

**비용과 시간.** [실행 전 고정한 단가]({(PREP/'pricing.json').as_posix()})와 응답 usage를 대조했다. API 청구서 확정액이 아닌 사용량 기반 추산이며, 반복 호출의 캐시 읽기·쓰기 효과를 포함한다. 따라서 이번 평균을 실제 앱의 신규 질문 비용으로 그대로 쓰지 않는다.

| 조건당36답변 | A | C |
|---|---:|---:|
| 입력 토큰 | 240,136 | 430,170 |
| 출력 토큰 (추론 포함) | 7,456 | 8,071 |
| 추론 토큰 | 864 | 1,388 |
| 캐시 읽기 토큰 | 120,014 | 221,215 |
| 캐시 쓰기 토큰 | 120,014 | 208,847 |
| 추산 비용 | $0.4137258 | $0.6634285 |
| 생성 호출 중앙 지연 | 2.290초 | 2.422초 |

C의 입력은{input_ratio:.2f}배, 비용은{cost_ratio:.2f}배였다. 정확도 이득 없이 비용이 증가했고, 확인된 이득은 인용 충실도 두 건과 거절 한 건이다. 실제 앱의 검색·네트워크·cold-cache 전체 지연을 측정한 것은 아니다.

**검증과 해석 한계.** 실행 전 요청·정답 기준을 고정하고,72개 응답 원본을 봉인한 뒤 조건·반복 표시를 가린 새 검토 컨텍스트3개로 실제 인용과 필수 사실을 대조했다.72답변과359개 출처 기록을 확인했고 구조 실패는0이었다. 근거 표현 모양으로 조건이 드러날 수 있어 완전한 블라인드가 아니며, 같은 모델 계열의 검토로 독립 인간·다른 모델 계열 검증을 대신하지 않는다.

R006의 충실도만 원 판정 PASS에서 PARTIAL로 조정했다. 같은 종류의 FabriX–클라우드 추정을 R004에서는 감점하고 R006에서는 감점하지 않은 불일치를 원 인용으로 재검토한 결과다. 원 리뷰는 유지했고 조정 이유를 별도로 남겼다. 정답·필수 기준·생성 응답은 변경하지 않았다. 주평가30답변의 수치와 거절 성공률에는 이 조정의 영향이 없다.

이 실험은 기존18문항에 대한 현재 앱 조건의 국소 비교다. 과거77문항 답변을 이번에 재생성하지 않았다. 준비 단계에서 확인한 top9–12의 배당·재고·영업권·그룹 매출 등 근거 부재는 top8을 고정한 이번 보강으로 복구하지 않았다. 기존 표제·기간·범위의 미연결과 H14의 상속된 표제 문맥 긴장도 파서 수정을 하지 않았으므로 구현상 남는다. 답변의 출처 ID 검사 통과, 물리적 셀 연결 통과, 이번 검토의 의미 판정은 각각 다른 수준의 증거다.

통계적 해석 오류는 **11/11 점검**했다. 결과는 기술통계이며 유의성·모집단 일반화를 주장하지 않는다. {link('statistical_interpretation.json')}에 보고서/반복 집중, 선택 편향, 반복 의존성, 다중 시도와 판정 민감도를 기록했다.

**보존과 종료.** 보호 대상864개 파일, HEAD·index·Git 상태, `.env`, 활성 v12 store11개 파일은 모두 실행 전과 같았다. store는 SQLite/Chroma 클라이언트로 열지 않고 파일 해시만 읽었으므로, 이번에는 SQLite 내부 바이트 변경도 없었다. 새 검색·임베딩·외부 모델 채점 호출·앱 재시작·기본 경로 수정·커밋·push는 모두0이다. 유료 생성72회와 네이티브 검토 작업은 구분한다. 산출물은 이 별도 평가 폴더에만 저장했다.

이번 결과는 표 보강의 기존 개선 증거를 부정하지 않지만, **Terra·low·top8 기본 경로로 이득이 안정적으로 이전됐다는 채택 근거도 충족하지 못했다.** 현 구현을 유지하고 이 실험은 여기서 종료한다. 추가 규칙·재호출·자동 재튜닝을 시작하지 않는다.

재현 근거: {link('summary.json')}, {link('graded_answers.json')}, {link('decision.json')}, {link('parent_source_audit.json')}, {link('adjudication.json')}, {link('raw_output_seal.json')}, {link('closeout_validation.json')}.
'''
    with (OUT/'report.md').open('x',encoding='utf8',newline='\n') as f:f.write(report)
    passport='''## Material Passport

- Origin Skill: academic-research-suite / experiment-agent
- Origin Mode: run + validate
- Origin Date: 2026-10-24 Asia/Seoul
- Verification Status: EXECUTION_COMPLETE_SOURCE_REVIEWED; PRACTICAL_TRANSFER_GATE_NOT_MET
- Scope: Exposed18, Terra/low/top8, original64KiB versus table augmentation160KiB, two repeats per arm.
- Executed:72/72 generation calls; USD1.0771543 estimated;189.16seconds generation;0 retries.
- Validation:72 sealed raw outputs,72 source reviews, one documented consistent-rule adjudication,11/11 statistical fallacy checks.
- Decision:Mixed/inconclusive for default rollout; accuracy/completeness unchanged, small repeat2 citation gain.
- Limits:Same-family masked review, three exposed reports, all C inputs fit64KiB; no independent-human/population claim.
- Preservation:Source and uncommitted files, env and active v12 store byte-identical; no app restart, retrieval, embeddings, external judge or runtime change.
- Evidence:report.md, summary.json, decision.json, closeout_validation.json, passport_run_ledger.yaml.
'''
    (OUT/'passport.md').write_text(passport,encoding='utf8',newline='\n')
    put(OUT/'ledger_closeout.json',{
      'kind':'tool_receipt','step':'final_validation_and_report','command':'aggregate.py; closeout_checks.py; finalize_report.py',
      'status':'passed','exit_status':0,'retries_used':0,
      'input_paths':['summary.json','graded_answers.json','closeout_validation.json','decision.json','statistical_interpretation.json','report.md'],
      'gate_tokens':['EXECUTION_AND_PRESERVATION_PASS','PRACTICAL_TRANSFER_GATE_NOT_MET','11_OF_11_FALLACIES_CHECKED','NO_ROLLOUT']})
    claims={'steps':[{'step':x,'status':'passed'} for x in ('execution_admission','paid_generation72','masked_source_review72','final_validation_and_report')]}
    (OUT/'claims.json').write_bytes(enc(claims)+b'\n')
    sealed=['report.md','summary.json','graded_answers.json','decision.json','statistical_interpretation.json','adjudication.json','parent_source_audit.json','raw_output_seal.json','closeout_validation.json','review_validation.json','performance.json','masked_review/batch2/clarification.json']+[f'masked_review/batch{i}/review.json' for i in (1,2,3)]
    put(OUT/'final_result_seal.json',{'at':now(),'files':{n:sha(OUT/n) for n in sealed},'meaning':'Integrity fingerprints, not independent semantic certification.'})
    print('Final report saved. Transfer decision:MIXED_INCONCLUSIVE; protected files unchanged.')

if __name__=='__main__':main()
