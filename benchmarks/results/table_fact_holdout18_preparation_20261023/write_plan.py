"""Render the single human-readable handoff; not a live experiment entrypoint."""
from common import *
def main():
    assert not (BASE/'freeze.json').exists()
    qs=read(BASE/'rubric.json')['cases'];acq=read(BASE/'acquisition.json');v=read(BASE/'validation.json')
    proj=read(BASE/'projection.json');price=read(BASE/'pricing.json');audit=read(BASE/'exposure_audit.json')
    kinds={'numeric_direct':'표 직접 조회','calculation':'계산','mixed':'수치·설명','narrative':'관계·서술','refusal':'제한적 답변 불가'}
    def link(name):return f'[{name}]({(BASE/name).as_posix()})'
    lines=['# 새 보고서 18문항: 기존 전달 64KiB 대 표 보강 160KiB 비교 준비',
      '', '## Material Passport','',
      '- Origin Skill: academic-research-suite / experiment-agent','- Origin Mode: plan','- Origin Date: 2026-10-23',
      '- Version Label: holdout18-v1','- Verification Status: PREPARED_NOT_EXECUTED; 원문·산술·입력 준비 검증 통과, 검색·답변 평가는 미실행',
      '- 모델·임베딩·외부 judge API 호출 0회. 사용자가 별도 허용한 무료 DART 조회·다운로드 7회만 수행.',
      '- 기존 구현·미커밋 변경·.env·v12 store 보존. 앱 재시작·커밋·push 없음.',
      '', '## 무엇을 검증하는가','',
      '개발 과정에 노출된 기존 77문항에서 관찰한 표 근거 전달 개선이, 기존 평가에서 사용한 기록이 없는 보고서에도 재현되는지 확인한다. 질문·검색 결과·생성 조건을 공유하고 **기존 64KiB 전달(A)**과 **동일 전달 문서에 검증된 표 값 묶음을 추가한 160KiB 전달(C)**을 각각 2회 생성한다.',
      '이 비교는 표 표현과 사용 가능한 문맥량을 함께 바꾸는 패키지 효과다. 표 표현만의 효과나 문맥 증가만의 효과로 분리해 해석하지 않는다. 검색 후보에서 빠졌거나 A의 실제 문맥에서 생략된 문서를 C가 새로 가져오지는 않는다.',
      '', '## 보고서와 미사용 확인','',
      '| 보고서 | 접수번호 | v12 청크 수 | 원문 |','|---|---|---:|---|']
    for r in acq['reports']:
        lines.append(f"| {r['label']} 2025 사업보고서 | {r['rcept_no']} | {proj['counts'][r['rcept_no']]['chunks']:,} | [DART]({r['public_url']}) |")
    lines += ['',f"선정 규칙은 원문 검토 전에 고정했다. 자동차·IT서비스/물류·화장품 업종에서 각 1개 기업을 목적 표집했고, 2026-10-23까지 제출된 2025.12 사업보고서 중 최신 제출본을 선택했다. 무작위 표본은 아니다.",
      f"로컬 프로젝트와 지정 보관 경로의 텍스트 자료 {audit['files_scanned']:,}개를 용량 제한 없이 접수번호로 대조했고, 기존 원문 SHA-256 중복과 평가 자료의 해당 보고서 소유 관계도 발견되지 않았다. 구조화해 추출한 이전 질문 {audit['old_questions']:,}개와 새 질문의 공백 정규화 완전 일치도 0건이다. 범위는 {link('exposure_audit.json')}에 명시했다. 삭제된 기록·다른 외부 저장소·모델 학습 데이터까지의 미노출을 보증하지 않는다.",
      '질문은 실제 이용 상황을 가정해 원문을 보고 새로 작성했다. 실제 사용자 로그가 아니며, 다른 기업 보고서에서 이 기업명이 한 번도 등장하지 않았다는 뜻도 아니다. 검색 결과와 생성 답변은 보지 않았고, 결과가 나온 후 질문을 쉬운 것으로 바꾸지 않는다.',
      '', '## 문항 구성','',
      '보고서마다 표 직접 조회 2개, 계산 1개, 수치·설명 1개, 관계·서술 1개, 제한적 답변 불가 1개다. 답변 가능 15문항과 답변 불가 3문항을 분리해 집계한다. 각 문항에는 해당 접수번호를 caller scope로 명시하며, 질문의 연도에서 보고서 범위를 추정하지 않는다.',
      '| ID | 보고서 | 유형 | 질문 |','|---|---|---|---|']
    for q in qs:lines.append(f"| {q['case_id']} | {q['company']} | {kinds[q['kind']]} | {q['question'].replace('|',' / ')} |")
    lines += ['',f"실행용 질문은 {link('questions.json')}, 정답·필수 사실·원문 XPath·금지된 오독·선택 설명은 {link('rubric.json')}에 분리했다. 정답과 채점 기준은 모델 입력에 넣지 않는다.",
      '', '## 고정 실행 조건','',
      '| 항목 | 조건 |','|---|---|',
      '| 생성 | gpt-6.1-sol, reasoning low, max_output_tokens 8192, standard/default, store=false, stream=false |',
      '| 프롬프트·응답 | 직전 full77 실험과 시스템 프롬프트·strict RagAnswer JSON schema가 정확히 동일. 추가 지시문 없음 |',
      '| 파싱·검색 입력 | v12 financial_parser_v12_schema_literal_labels / structural_selective_v2_prefix_2500_320, chunk 2500·overlap 320 |',
      '| 임베딩 | text-embedding-3-large, 3072차원. 원래 검색 입력으로만 생성하며 C 표 보강은 임베딩에 넣지 않음 |',
      '| 검색 | Dense 16 + 현재 한국어 bigram/ASCII BM25 최대 24, 동일 가중 RRF60, 최종 선택 최대 12 |',
      '| 검색 실행 | 기존 search(k=8)의 후보를 한 번 캡처해 같은 RRF 함수로 12개 선택. search(k=12)로 후보를 24/36개까지 늘리지 않음 |',
      '| 후보 공유 | 질문별 검색 1회. 후보·점수·순서·top12를 저장하고 A/C 및 2회 반복에 똑같이 사용 |',
      '| corpus | 새 보고서 3개만 들어간 별도 평가 store. BM25 통계는 양쪽이 같은 3개 보고서를 공유. 과거 11개 corpus와 IDF가 같다는 주장은 하지 않음 |',
      '| A | 65,536 UTF-8 bytes. 현재 전체 청크 단위 생략 방식 유지 |',
      '| C | 정확히 A에 실제 들어간 문서의 ID·본문·기존 문맥·순서 보존. 검증된 table_fact_units만 추가, 163,840 bytes |',
      '| C 부착 | 물리적 표의 첫 소유 청크에 원문 순서로 원자적 셀·행·열 의존 묶음을 추가. 검증 실패/예산 초과는 생략하고 기록 |',
      '| 추가 검색 기법 | query reformulation·분해·확장·Nori·S12·reranker·국가 보완·캡션 확장·Planner·Compiler 없음 |',
      '| 반복 | 18 × 2조건 × 2회 = 72답변. 홀수/짝수 문항 AC/CA, 두 번째 반복은 순서를 반대로. 동시성 1 |',
      '| 시간 | 첫 유료 dispatch부터 전체 2시간 30분, 20초 heartbeat, 단계별 진행·호출·비용·미정산 예약 기록 |',
      '',
      '최종 선택 12개와 실제 전달 개수는 다를 수 있다. A가 64KiB 한도 때문에 문서를 생략하면 C도 그 문서를 새로 넣지 않는다. 이 차이를 흐리면 이전 패키지와 다른 실험이 되므로 문항별 selected/delivered/omitted 목록을 모두 저장한다.',
      'C의 물리적 연결 검증은 저장된 표 metadata에 있는 값·축·문맥이 원문에 대응하는지 확인한다. 원문만 뒤져 새 값을 보충하거나 기간·주체·단위의 의미 해석까지 검증했다고 표시하지 않는다.',
      '', '## 비용과 호출 상한','',
      '| 단계 | 입력·실행량 | 최대 HTTP 시도 | 비용 참고 |','|---|---|---:|---|',
      '| 새 보고서 임베딩 | 3,768청크 → 동일 문자열 3,734개, 2,726,886토큰, 최대 256입력/250,000토큰 배치 | 15 | 측정 입력 기준 약 $0.3545 |',
      '| 질문 임베딩 | 18질문, 로컬 측정 합계 1,288토큰, 각 1회 | 18 | 측정 입력 기준 약 $0.00017 |',
      '| 답변 생성 | A/C 각각 36회, 합계 72회 | 72 | 과거 평균·캐시 사용에 따라 변동 |',
      '| 합계 | 준비 단계에서 이 API들은 미호출 | **105** | **예상 $3~6 / 보수적 상한 $36.00** |',
      '',
      '예상치는 직전 full77의 입력·출력 평균과 실제 캐시 과금에서 답변 비용 약 $2.32, 캐시를 재사용하지 않고 모두 30분 캐시 쓰기로 계산하면 약 $3.50로 환산한 값에 새 임베딩과 길이 변동 여유를 더한 것이다. 실제 패킷은 검색 후에 정해지므로 $3~6은 보장이 아니다.',
      '단가는 2026-10-23 [OpenAI 공식 API 가격](https://developers.openai.com/api/docs/pricing)과 [캐시 정책](https://developers.openai.com/api/docs/guides/prompt-caching#summary-of-model-differences)으로 확인했다. Sol 입력 $2/M·출력 $10/M·기본 30분 캐시 쓰기 $2.50/M·캐시 읽기 $0.10/M, embedding-3-large $0.13/M를 사용한다. 캐시 할인은 상한에서 가정하지 않는다.',
      f"최대 입력 예약 A 98,304 / C 229,376토큰, 출력 8,192토큰, 임베딩 여유를 모두 채우는 경우의 예약 합계는 **${price['saturated_total_reservation_usd']}**다. 두 입력 예약은 272K 이하 단가 범위 안에 있다. ${price['cap_usd']}는 계정 청구 설정이 아니라 실험 runner가 dispatch 전에 강제할 예산이다. 상세 산식은 {link('pricing.json')}에 있다.",
      '모든 HTTP 시도를 차감하며 실패·타임아웃도 호출을 소비한다. 자동 재시도·provider probe·추가 judge·모델 대체는 0회다. 요청 전 UTF-8 body bytes+4,096 예약이 해당 조건 상한을 넘으면 문맥을 줄여 맞추지 않고 멈춘다. usage 누락·모델/차원 불일치·알 수 없는 요율·통신 실패는 예약 비용을 남기고 중단한다. 조기 중단 시 72개 완료로 보고하지 않는다.',
      '', '## 판정 기준과 분석','',
      '1. **정확도:** 요청한 주체·기간·연결/별도 범위·단위·수치/관계가 맞는가. 계산은 같은 범위 피연산자와 요청한 반올림을 독립 검산한다.',
      '2. **필수 항목 누락:** 아래 문항별 필수 사실을 모두 포함했는가. 답변 가능한 질문에서 신중하게 거절해도 필수 답이 없으면 완전성은 실패다. 선택 항목 생략은 감점하지 않는다.',
      '3. **출처 충실도:** 실제 답변에 인용된 모델 입력이 모든 중요한 주장과 추가 설명을 뒷받침하는가. ID가 유효하거나 원문 정답표에 있다는 이유만으로 통과시키지 않는다.',
      '4. **답변 불가:** 요청 범위에서 무엇이 부족한지 설명하고 지어낸 값·관계를 만들지 않는가. 전체 보고서에 없다고 확대하지 않는다. abstained=true와 내용의 적절성을 함께 확인한다.',
      '주지표는 답변 가능 15문항 × 2회에서 정확도·완전성·출처 충실도 모두 PASS인 수(조건별 분모 30)다. 거절 3문항 × 2회(분모 6)는 별도로 제시한다. 전체 18문항의 전환, 두 번 모두 개선/회귀, 보고서별 변화와 소요 비용도 함께 보고한다.',
      '후속 해석을 위한 실패 층은 원문/파싱, 후보, RRF 선택, A 문맥 생략, C 검증/예산 생략, 실제 전달 근거의 오독·잘못된 인용으로 구분한다. 구조 검증 PASS와 답변 PASS는 서로 다른 지표다.',
      '72답변은 독립 표본 72개가 아니다. 18질문·3보고서의 기술적 짝 비교이며, 반복별·보고서별 개수와 퍼센트포인트 변화를 보고한다. 모집단 정확도·유의성·다른 문서 전반의 개선으로 확대하지 않는다.',
      '사전 실용적 판정: 두 반복 모두 답변 가능 주지표가 개선되고, 3보고서 중 최소 2개에서 비음수이며, 새 중대한 사실·출처·거절 회귀가 확인되지 않으면 제한적 전이 근거로 본다. 그 외는 혼합/불충분 결과로 남긴다. 이는 통계 검정이나 자동 앱 적용 기준이 아니다.',
      '원시 출력 72개를 먼저 봉인하고 조건·반복을 가린 별도 문맥에서 원문과 실제 인용 문맥을 검토한다. 표 보강 모양 때문에 조건이 드러날 수 있으므로 완전 맹검이라고 부르지 않는다. 새 정답 충돌이 발견되면 원래 채점과 별도 민감도 결과를 모두 남기고 유리한 쪽에 맞춰 기준을 고치지 않는다.',
      '', '## 실행 단계와 중단점','',
      '1. 명시적인 실행 승인 뒤, 새 execution/ 폴더 안에만 제한된 runner를 준비한다. 현재 준비본에는 유료 실행 runner를 기동하지 않았으며 전송 guard의 mock 검증도 실제 실행 전에 필요하다.',
      '2. 동결 파일·원문·기존 구현 hash, 공식 단가, .env/store 보존 조건을 확인한다. 문항·정답·표 보강 알고리즘은 고치지 않는다.',
      '3. 준비된 corpus를 15개 배치로 임베딩하고 새 store만 구축한다. 3,768개의 원래 UID를 모두 보존한다. query embedding 18회로 검색을 한 번씩 저장한다.',
      '4. 네트워크를 막은 별도 단계에서 A/C 패킷을 조립하고 기존 필드 동등성·출처 물리 연결·byte 한도·호출 예약을 검사한다. 기존 표 보강 run.py는 import 때 socket을 차단하므로 온라인 프로세스와 분리한다.',
      '5. 같은 prompt/model/schema로 동결 순서의 72개 답변을 생성한다. 모든 호출은 예산·횟수·시간 상한 아래에서 예약 후 전송하며 자동 재시도하지 않는다.',
      '6. 실제 인용 문맥에 근거해 채점·실패 층·비용을 비교하고 결과를 별도 보고한다. 앱 전환이나 runtime 변경은 이 실험의 일부가 아니다.',
      '', '현재 준비본을 다시 검사하는 **무호출 명령**:', '', '```powershell',
      '.venv\\Scripts\\python.exe -B -X utf8 benchmarks/results/table_fact_holdout18_preparation_20261023/validate_preparation.py', '```',
      '',f"정확한 조건은 {link('protocol.json')}, 향후 runner 필수 gate는 {link('review_protocol.json')}의 required_execution_gates에 있다. 실행 store는 {(BASE/'execution/store').as_posix()}, collection은 holdout18_v12_20261023으로 고정하며 기존 v12 store와 연결하지 않는다.",
      '', '## 문항별 정답·근거·판정','',
      '아래 정답은 하나의 허용 예시다. 필수 사실의 의미를 보존한 다른 표현도 허용한다. 원문 위치와 인용 134개는 별도 JSON에서 전체 확인할 수 있다. 보고서별 작성과 다른 작성자의 교차 검토를 수행했으며 독립 인간 정답은 아니다. 질문 밖 세부 요구 4건(H10·H11·H17·H18)은 검색/생성 전에 선택 사항으로 옮겼다. 원래 작성본과 검토 기록은 보존했다.']
    reports={r['rcept_no']:r for r in acq['reports']}
    for q in qs:
        lines += ['',f"### {q['case_id']} · {q['company']} · {kinds[q['kind']]}",'',q['question'],'','**정답 예시**: '+q['reference_answer'],'','**필수 판정**:']
        for fact in q['required_facts']:lines.append('- '+fact['expected'])
        blocks=sorted({e['block_index'] for e in q['evidence']})
        source_file=BASE/'sources'/q['receipt']/'review.txt'
        lines += ['',f"**근거**: [원문]({reports[q['receipt']]['public_url']}), [로컬 원문 검토본]({source_file.as_posix()})의 block {', '.join(map(str,blocks))}. rubric.json의 evidence에 셀/문단 XPath와 원문 인용을 모두 기록했다.",
          '**실패 예**: '+' / '.join(q['failure_conditions']),
          '**선택 사항**: '+' / '.join(q['optional_items'])]
        if q['case_id']=='H14':lines += ['**기간 연결 한계**: 값 표 자체에 별도 연도 열이 없으며 2025년 사업보고서 표지와 연차 문맥을 따른다. 값 표에서 독립적으로 기간 시작·종료일을 검증했다고 표현하지 않는다.']
    lines += ['', '## 검증 결과와 남은 한계','',
      f"검증 PASS: 18문항·3보고서·유형 배분, 원문 근거 134곳의 XPath 유일성/문자열 대응, 계산 3건, 수정된 필수 기준 4건, 단일 보고서 scope, 72회 교차 순서, 15개 임베딩 배치·105회 상한·비용 산식. {link('validation.json')} 참조.",
      f"기존 보호 파일 {v['protected_files']}개, .env, active v12 store {v['active_v12_store_files']}개 파일의 바이트 hash, Git HEAD/index/status가 모두 동일했다. SQLite/Chroma client를 열지 않아 내부 정리·WAL 등 store 내부 변경도 없었다. 이번 준비는 별도 ignored 폴더에만 기록했다.",
      '아직 측정하지 않은 것: 새 질문의 Dense/BM25 후보·top12, 실제 A/C 문맥 크기, 답변 정확도·회귀·실사용 유용성, provider 실행 안정성. 비용 예상은 과거 길이를 이용한 추정이다. 3개 보고서는 제한된 전이 검증이며 전체 공시 도메인의 일반화 증거로는 부족하다.',
      '교차 검토는 native Codex workers를 사용했고 요청 model은 gpt-6-astra/xhigh였다. 실제 provider 모델 신원은 별도 확인되지 않았다. 이 작성·검토 과정과 이후 실험대상 gpt-6.1-sol API 72회를 구분한다.',
      '',f"기계 판독 원본: {link('questions.json')} · {link('rubric.json')} · {link('protocol.json')} · {link('pricing.json')} · {link('gold_adjudication.json')} · {link('freeze.json')}",'']
    (BASE/'plan.md').write_text('\n'.join(lines),encoding='utf8')
    print(json.dumps({'plan_bytes':(BASE/'plan.md').stat().st_size,'required_facts':sum(len(q['required_facts']) for q in qs)},ensure_ascii=False))
if __name__=='__main__':main()
