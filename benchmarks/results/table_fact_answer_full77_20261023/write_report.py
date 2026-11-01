"""Render descriptive result tables after sealed, source-reviewed aggregation."""
from pathlib import Path
import json

OUT=Path(__file__).resolve().parent
def load(name):return json.loads((OUT/name).read_text('utf-8'))
def ratio(n,d):return f'{n}/{d} ({100*n/d:.1f}%)' if d else '—'
def grade(g,axis):return ratio(g[axis].get('PASS',0),g['answers'])
def clean(s):return str(s).replace('|','/').replace('\n',' ')

def main():
    s=load('summary.json');rows=load('paired_results.json');r=load('rubric.json');g=s['groups'];e=s['execution']
    byid={c['case_id']:c for c in r['cases']}
    index={(x['case_id'],x['arm'],x['repetition']):x for x in rows}
    lines=['## Material Passport','',
      '- Origin Skill: academic-research-suite / experiment-agent run + validate',
      '- Date: 2026-10-23 Asia/Seoul',
      '- Verification Status: ANALYZED — frozen-input generation and source review completed; not independent human validation or stochastic reproducibility certification.',
      '- Scope: development-exposed77 questions × A/C ×2repetitions; original retrieval and generation conditions fixed.',
      '- Source/implementation changes: none. Only isolated experiment artifacts; no app restart, commit or push.','',
      '# 표 값 단위 전달: 기존 77문항 실제 답변 비교','',
      '<!-- ROOT_INTERPRETATION: add reviewed findings here; do not infer acceptance from transport completion. -->','',
      '## 조건과 평가 분모','',
      'A는 원래 저장된 A12 문맥, C는 같은 문서에 원문 위치 연결을 확인한 표의 값·행·열 정보를 추가한 최대160KiB 문맥이다. 후보·점수·순서·최종 선택12개와 실제 전달 문서 창을 고정했다. 모델은 gpt-6.1-sol, reasoning low, 원래 프롬프트·응답 스키마, 최대 출력8,192토큰이다. 두 조건 모두 이번 실행에서 새 답변을 생성했다. 검색·임베딩·별도 judge API 호출은 없다.',
      '',
      '선택12개와 실제 전달 문서는 구분한다. 기존 byte 제한으로 6문항은 실제6–11개 문서였고, 나머지71문항은12개였다. 두 조건에서 그 문서 수·ID·원문·순서는 동일하다. C는 근거 표현과 전달량을 함께 바꾸므로 순수 형식 효과나 순수 예산 효과로 분리할 수 없다.',
      '',
      '사전에 동결한 평가군은 답변 가능46문항, 거절19문항, HOLD12문항이다. 조건별 응답 수는92·38·24이다. HOLD의 전체 정확도·완전성·완전 정답은 null로 두었다. 과거48/55문항 분모와 직접 비교하지 않는다. 완전 정답은 정확도·완전성·출처 충실도가 모두 PASS인 경우다. 유효한 출처 ID만으로 의미 지지가 확인되는 것은 아니다.','',
      '## 답변 가능46문항','',
      '| 판정 | A: 원래 문맥 | C: 표 값 단위 추가 |','|---|---:|---:|']
    for axis,label in [('accuracy','정확도 PASS'),('completeness','필수 요청 완료 PASS'),('faithfulness','출처 충실도 PASS')]:
        lines.append(f"| {label} | {grade(g['common_answerable']['A'],axis)} | {grade(g['common_answerable']['C'],axis)} |")
    lines.append(f"| 완전 정답 | {ratio(g['common_answerable']['A']['complete_success'],92)} | {ratio(g['common_answerable']['C']['complete_success'],92)} |")
    lines+=['','| 반복 | A 완전 정답 | C 완전 정답 |','|---|---:|---:|']
    for rep in ('1','2'):
        x=s['repetitions'][rep]['common_answerable'];lines.append(f"| {rep} | {x['A']['complete_success']}/46 | {x['C']['complete_success']}/46 |")
    lines+=['','| 사전 구분 | 문항 수 | A 완전 정답 | C 완전 정답 |','|---|---:|---:|---:|']
    for name in ('pilot12','other65'):
        x=s['subsets'][name]['common_answerable'];lines.append(f"| {name} 중 답변 가능 | {x['A']['cases']} | {ratio(x['A']['complete_success'],x['A']['answers'])} | {ratio(x['C']['complete_success'],x['C']['answers'])} |")
    lines+=['','## 개선·회귀 대조','',
      '| 문항·반복 | 정확도 변화 | 완전성 변화 | 충실도 변화 | 새로 충족한 기록 | 충족을 잃은 기록 |','|---|---:|---:|---:|---|---|']
    for p in s['pairs']['A_C']:
        ch=p['changes']
        if any(v not in (None,0) for v in ch.values()) or p['newly_fulfilled'] or p['lost_fulfilled']:
            lines.append(f"| {p['case_id']} r{p['repetition']} | {ch['accuracy']} | {ch['completeness']} | {ch['faithfulness']} | {', '.join(p['newly_fulfilled']) or '—'} | {', '.join(p['lost_fulfilled']) or '—'} |")
    lines+=['','변화는 FAIL=0, PARTIAL=1, PASS=2의 차이이며 평균 간격척도나 효과 크기로 해석하지 않는다. null/AMBIGUOUS는 수치 차이로 환산하지 않는다. 단위 목록은 동결한 평가 기록이다. 전체154기록에는 alias/checkpoint17개와 선택적 진단1개가 포함되므로 독립 필수 사실154개로 세지 않는다. 종류별 집계는 summary.json의 unit_record_states_by_kind에 보존했다.','',
      '## 거절과 HOLD','',
      '| 구분 | A | C |','|---|---:|---:|',
      f"| 거절19문항: 적절한 거절 PASS | {grade(g['refusal']['A'],'appropriate_abstention')} | {grade(g['refusal']['C'],'appropriate_abstention')} |",
      f"| 거절19문항: 충실도 PASS | {grade(g['refusal']['A'],'faithfulness')} | {grade(g['refusal']['C'],'faithfulness')} |",
      f"| HOLD12문항: 개별 주장 충실도 PASS | {grade(g['diagnostic_or_hold']['A'],'faithfulness')} | {grade(g['diagnostic_or_hold']['C'],'faithfulness')} |",'',
      '## 실행·비용','',
      f"- 성공 답변 {e['successful_answers']}개, HTTP 시도 {e['attempts']}회. 최초44번째 요청의503/server_is_overloaded는 원본 그대로 보존했다. 사용자 승인 후 실패1개와 미실행264개만 이어서 생성했다. 기존 성공43개를 다시 생성하거나 답변 내용으로 선별하지 않았다.",
      f"- 사용량 기준 성공 요청 추정 비용 ${e['estimated_usd']}; 실패 요청의 미정산 예약 ${e['unsettled_reservation_usd']}를 포함한 보수적 합계 ${e['total_cost_with_uncertain_reservation_usd']}. 승인 상한은 총309회·$70.09. 미정산 실패 호출을 무료로 가정하지 않는다.",
      f"- 두 구간 합산 active-process 시간 {e['aggregate_active_process_seconds']/60:.2f}분. 승인 대기는 제외하며 합계150분 상한을 유지했다. 생성·평가 중 기존 앱 재시작 없음.",
      '- 아래 비용·시간은 답변 생성 API 측정값이다. 네이티브 Codex 검토의 구독 사용량은 별도 계측하지 않았다.','',
      '| 조건 | 입력 토큰 | 출력 토큰 | reasoning 토큰 | 추정 비용 | 평균 응답 시간 |','|---|---:|---:|---:|---:|---:|']
    for arm in 'AC':
        x=s['performance'][arm];lines.append(f"| {arm} | {x['input_tokens']:,} | {x['output_tokens']:,} | {x['reasoning_tokens']:,} | ${x['estimated_usd']} | {x['latency_mean']:.2f}초 |")
    lines+=['','## 해석의 한계와 검증','',
      '동결한 기준을 사용해 원본 응답을 봉인한 뒤 네이티브 assistant가 조건명·반복 번호를 가린 입력을 검토했다. 문맥의 길이·표현에서 조건을 추측할 수 있으므로 완전한 맹검이 아니다. 독립 인간 정답이나 다른 모델 계열의 검증으로 주장하지 않는다. 모든77문항은 개발 과정에 노출됐고, 나머지65문항도 새 holdout이 아니다. 반복2회는 독립 문항 수를 두 배로 만들지 않는다. root의 판정 조정은 기존 기준과 실제 출처 인용으로 남기며 초기 판정은 보존한다.',
      '',
      '통계 오류 점검11/11: (1) 전체·pilot12·other65·반복별 방향을 분리, (2) 문항 집계를 새 기업 일반화로 확장하지 않음, (3) 개발 노출 표본의 선택 편향 인정, (4) 결과를 본 뒤 평가군 재선택하지 않음, (5) 거절 기저 비율을 분리, (6) 과거 실패와 비교하는 대신 이번 A를 새로 생성, (7)503실패와 재개 기록을 포함하고 모든 성공 답변 유지, (8) 유리한 문항만 보고하지 않고 전체77개 제시, (9) 여러 선행 실험이 있었음을 인정하고 이번 기준 사전 동결, (10) 표현·근거량의 결합 처치를 개별 원인의 효과로 주장하지 않음, (11) 처치가 답변보다 앞서지만 일반적 인과·성능 우월성 주장은 하지 않음. 유의성 검정이나 독립 반복 가정의 신뢰구간은 제시하지 않는다.',
      '',
      '## 전체77문항 판정표','',
      '각 칸은 정확도/완전성/충실도이며 P=PASS, ~ =PARTIAL, F=FAIL, ?=AMBIGUOUS, H=HOLD(null)이다. 실제 단위별 누락과 판정 근거는 paired_results.json 및 masked_review 원본 검토에 있다.','',
      '| 문항 | 평가군 | A r1 | C r1 | A r2 | C r2 |','|---|---|---|---|---|---|']
    code={'PASS':'P','PARTIAL':'~','FAIL':'F','AMBIGUOUS':'?',None:'H'}
    for cid,c in byid.items():
        cells=[]
        for arm,rep in [('A',1),('C',1),('A',2),('C',2)]:
            x=index[cid,arm,rep];cells.append('/'.join(code[x[k]] for k in ['accuracy','completeness','faithfulness']))
        lines.append(f"| {cid} | {c['group']} | "+' | '.join(cells)+' |')
    lines+=['','## 산출물','',
      '- protocol.json / freeze.json / rubric.json: 생성 전 조건·기준',
      '- live/ 및 resume01/live/: 두 구간의 원본 요청·응답·비용·봉인',
      '- combined/: 원본을 보존한308개 답변 색인과 연결 검사',
      '- review_mapping.json / masked_review/: 답변 연결 및 초기 검토',
      '- adjudicated_reviews.json / summary.json / paired_results.json: 최종 판정과 전체 집계',
      '- final_preservation.json: 보호 파일·Git·.env·v12 store 검증','']
    with (OUT/'report.md').open('x',encoding='utf-8') as f:f.write('\n'.join(lines))
    print('REPORT_TABLES_WRITTEN;root interpretation and final preservation still required')

if __name__=='__main__':main()
