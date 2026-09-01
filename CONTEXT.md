# 프로젝트 컨텍스트

> 새 세션에서 현재 상태를 2분 안에 파악하기 위한 handoff다. 현재 제품 상태,
> 검증, blocker와 우선순위의 단일 기준은
> [project_status.md](docs/overview/project_status.md)다. 세부 runtime 동작은
> [agent_runtime_contract.md](docs/architecture/agent_runtime_contract.md), 완료된 변경은
> [implementation_history.md](docs/history/implementation_history.md)를 따른다.

Last updated: 2026-09-01

## 현재 범위

- 제품은 DART 공시를 분석하는 single-agent `FinancialAgent`다.
- 핵심 흐름은 구조 보존 ingest, dense/BM25 hybrid retrieval, LLM semantic
  planning, deterministic calculation, evidence/provenance validation이다.
- MAS, report-cache promotion, evaluator, benchmark runner와 review workflow는
  optional 또는 experimental surface다.
- 범용 agent, broad web workflow, productivity-tool 확장은 현재 범위가 아니다.

## 현재 checkpoint

- Source: `main@a9a2df5` 위의 미커밋 작업 트리다. 사용자가 이미 수정한
  `src/api/financial_router.py`와 untracked
  `tests/test_financial_router_http_contract.py`는 이번 의미 계산 프로그램 변경과
  분리되어 있으며 보존한다.
- 사용자가 manifest
  `70db0fb131b648e69b5fc096f4bdfdd3191502ffa90caab7df8538d376b4e91a`와
  `$0.40` 한도를 승인했다. 실행 직전 동일 no-call receipt를 재확인한 뒤
  `HYU_T2_010`, `HYU_T3_072`, `SAM_T2_078`을 Hyundai-then-Samsung 순서로
  정확히 한 번 실행했다. 30초 heartbeat로 303.767초에 완료됐으며 automatic run
  retry는 없었다. 세 문항 모두 runtime error 0, ledger `ok`지만 runtime complete와
  clean focused acceptance는 각각 1/3이다. 이 one-run 승인은 소진됐다.
- 삼성은 canonical 연구개발비용 `28,352,769백만원`, 연결 기준 근거, Harman 설명으로
  2/2를 유지했다. T2는 정확한 `87.0만 대`와 `78.1만 대`가 prompt에 있었지만
  compiler가 미국 시장 전체 판매량을 선택했고, basis 검증에서 차단되어 1/2다.
  T3는 하나의 source-defined 요약 근거로 실제 손익 네 항목을 보존해 2/3가 됐지만,
  지분율은 다른 회사의 `53%` candidate ID를 골라 subject 검증에서 차단됐다.
- T3의 `700,691백만원`은 원문 연결 주석의 실제 당기 값이다. 정답표의
  `1,294,367백만원`은 별도 주석 값이며 질문은 연결/별도를 지정하지 않는다.
  이를 단순 계산 오답이나 서로 동치인 숫자로 처리하면 안 된다. 기준별 표시·평가
  계약의 재검토 항목으로 남겼고 answer key, 수치 허용 오차와 검증기는 바꾸지 않았다.
  지분율 누락 때문에 T3 문항 전체 acceptance는 여전히 실패다.
- Raw/final faithfulness는 T2 `1.000/1.000`, T3 `0.700/0.700`, 삼성
  `1.000/1.000`으로 coverage 기반 상향이 없다. T3 요약 항목 보존은 실제로 관찰됐다.
  반면 T2 계산 출력 자체가 빠져 이번 run은 `11.4%` 계산/`11.5%` 원문 표시의
  병존을 provider-backed로 확인하지 못했다. 그 경계는 이전 no-call 검증만 유지한다.
- 이번 사용량은 18 LLM calls, 543,641 tokens, 문항별 query embedding 33회,
  document embedding 0회다. 세 문항의 내부 compiler retry는 각각 1회다.
  Runner LLM 추정 `$0.2719901`은 승인 한도 아래지만 embedding 가격은 제외되어
  전체 청구액이 아니다. Router 초기화의 74-query embedding batch 2회도 승인 범위로
  실행됐으며 문항별 usage 밖에 기록된다. 추가 ingest/report fetch/KB/full gate는 없다.
- 실행된 127-file runtime build
  `20fefb3212af7c2391fc7e358b53cf1c6c445b1dfd30a8326462808bd95ef9c7`과
  profile/dataset/source fingerprint는 실행 후에도 동일하다. 실행 직전 5,490-byte
  canonical receipt는 기존 두 rehearsal과 같은
  `e0be3cfaa0506d81e49fc49fde890458dc591929102c88fa9010717965568ed6`로
  일치했다. 원본 store/SQLite, 이전 결과와 제외된 사용자 파일은 불변이고 임시
  store도 남지 않았다. Runtime 소스는 이번 실행에서 수정하지 않았다.
- Local-only admission은
  `benchmarks/results/source_display_qualitative_focused_admission_2026-09-01`에
  그대로 보존했다. 새 결과는
  `benchmarks/results/source_display_qualitative_focused_successor_2026-09-01`이며,
  top SHA-256은 `6725d3248c4002c6f2f835786a59dc4180e7f09dd1a9e972aa594df606e93e5a`다.
- 후속 provider-free selected-source 기준 표시 수정을 완료했다. 합성 fixture는
  17/17, 의미 계산/evaluator/provenance/ledger/import focused 237/237, 전체
  693/693(15.904초), runtime-domain audit 86을 통과했다. runtime build는 127 files,
  `e9a127d0cd0e0a17d780efa6ee3926f9ebb14198b6c83a684fbe9962d4aa3035`다.
- 질문 hard scope는 그대로 두고, 검증된 direct answer slot의 연결/별도 metadata를
  render-only scope로 사용한다. 모든 numeric 출력이 같은 알려진 기준이면 첫 출력에
  한 번만 표시하고, 독립 출력의 기준이 다르면 각각 표시한다. 선택 근거가 unknown이면
  unselected candidate로 채우지 않는다. 한국어/영어 표기는 reviewed config가 소유한다.
  candidate 선택·상태·source display·scope/unit/subject/coupling 검증은 바뀌지 않았다.
- 저장 T3 프로그램과 proposed/selected 후보 6개를 순수 실행기에 다시 넣었을 때
  selected IDs, `candidate_subject_mismatch`, `ob_001` 누락과 `partial` 2/3는 그대로다.
  답변에는 `2023년 연결기준 Motional 투자장부금액`만 추가됐다. socket 0, 저장 결과
  bytes와 source store/SQLite는 불변이며 새 provider 결과나 채점은 없다. 최신 유료
  acceptance는 여전히 1/3이다.
- 후속 provider-free multi-output answer-variant production evaluator 통합도 완료했다.
  `accepted_answer_variants`는 typed loader가 strict하게 읽고, canonical direct output을
  candidate-bound operand와 결합해 value/unit/subject/period/basis/source를 검증한다.
  서로 다른 actual output을 배정한 정확히 하나의 완전한 variant와 답변 숫자가 같은
  variant를 가리킬 때만 completeness reference를 그 source-qualified `answer_key`로
  바꾼다. no-field/no-match/partial/mixed/invalid/ambiguous는 canonical key로 fail closed한다.
- 합성 production-contract module 12/12, focused 249/249, 전체 705/705, audit 86과
  network-blocked 12/12(socket 0)을 통과했다. 기존 scalar result-binding과
  `accepted_answer_keys`, raw qualitative score, result schema는 바뀌지 않았다. Curated
  dataset·saved result·최신 유료 acceptance 1/3은 불변이며 provider/benchmark 호출은
  없었다.
- 후속 `HYU_T3_072` 실제 공시 근거의 provider-free read-only review도 완료했다.
  연결 주석의 동일 Motional 행은 `26% / 700,691백만원`, 연결 요약 표는 영업수익
  `1,775`, 계속영업손실 `803,742`, 기타포괄손익 `12,115`, 총포괄손실
  `791,627백만원`을 제공하므로 한 개의 완전한 연결기준 variant를 이룬다. 여섯
  immutable candidate를 순수 실행기에 넣은 결과는 validation error 없이 `ok`다.
- 별도 주석의 `25.81% / 1,294,367백만원`도 실제 direct pair지만, 같은 별도 기준의
  완전한 요약손익은 reviewed store에서 확인되지 않았다. `791,627`은 연결 요약에만
  있다. 현재 canonical key는 별도 direct pair와 연결 summary를 결합하고 있으므로
  source-basis atomicity 기준의 완전한 별도 variant로 등록할 수 없다. Dataset/key,
  tolerance, score, saved result는 수정하지 않았다.
- 후속 generic canonical-operand projection repair도 완료했다. `%`처럼 셀 값에 내장된
  단위가 table hint보다 우선하며 둘의 provenance는 분리되고, metric column header와
  current report year도 별도 필드로 남는다. Row-local subject validator는 parser footnote만
  제거한 실제 header identity와 source row IDs를 binding에 보존하며 compile/execute가 한
  public projector를 사용한다. Evaluator는 explicit subject/provenance를 요구하고 label
  fallback을 허용하지 않는다.
- 동일 immutable Hyundai store에서 기존 여섯 candidate ID가 모두 유지됐고, direct
  operand는 `26% / %`, `Motional AD LLC`, `2023`으로 투영됐다. 세 obligation 실행은
  validation `ready`, result `ok`; 메모리 안의
  `hyu_t3_072_consolidated_current` proposal은 projection error 없이
  `atomic_answer_variant_match`다. 합성 contract 13/13, focused 261/261, 전체 707/707,
  audit 86, import 19/19와 canonical DAG가 통과했다. SQLite/payload/dataset/result와 제외
  사용자 파일은 byte-stable이고 provider/benchmark/ingest 호출은 없었다.
- 실제 variant 등록은 여전히 보류다. 다음 우선순위는 source-complete consolidated
  variant 등록과 mixed-basis canonical key/evidence 정정을 어떻게 묶을지 정하는 별도
  dataset-governance 결정이다. 등록/정답 수정, T2/T3 compiler repair, paid replay와
  Phase 3는 각각 별도 명시적 결정이다.
- 숫자형·혼합형 canonical flow는 `requirement plan -> retrieval/evidence ->
  immutable candidate catalog -> semantic program compiler -> validate/execute ->
  render/verify`다. 서술형 전용 경로는 유지한다.
- pre-evidence 계획은 `answer_obligations`만 만들며 계산 타입을 결정하지 않는다.
  `operation_family`는 검증·실행된 AST에서 사후 파생하는 호환 필드다.
- 후보 ID, 원문 값/단위, 기간, 회사·연결/별도·부문·기준, 표/행/셀 위치와
  source anchor는 코드가 만든 catalog가 소유한다. LLM은 ID만 선택한다.

## 완료된 의미 계산 전환과 후속 이력 (historical)

아래 검증 수치와 no-call/승인 기록은 각 구현 시점의 이력이다. 최신 실행 결과와
다음 우선순위는 위 checkpoint 및 `project_status.md`의 Next Work를 따른다.

- 첫 candidate-stage 후속은 provider 없이 prompt admission owner를 수정했다.
  required `evidence_requirement`마다 출력 obligation과 분리된 bounded local
  cohort를 먼저 예약하고, 숫자 사이의 소수점은 문장 경계로 보지 않아 함께
  기재된 비율·수량의 주체와 기간 문맥을 보존한다. 불변 Hyundai store의 재구성
  probe에서는 기존 128개 총 prompt budget 안에 `87.0만 대`와 `78.1만 대`의
  정확한 candidate ID가 모두 포함됐다. 이는 no-call owner 검증이며 새 benchmark
  acceptance가 아니다.
- 두 번째 candidate-stage 후속도 provider 없이 hard-scope provenance owner를
  수정했다. `consolidated/separate`는 policy가 인식하는 query 표면이 명시한
  경우에만 obligation·required input·task hard scope가 될 수 있다. 명시가 없으면
  LLM 출력과 report metadata가 hard scope를 제안해도 `unknown`으로 내리고, 하나가
  명시되면 query가 우선하며, 둘 다 명시된 비교만 obligation별 두 값을 허용한다.
  저장된 `HYU_T3_072` planner payload의 `consolidated / consolidated / separate`도
  no-call projection에서 모두 `unknown`이 됐다. 이는 새 compiler/provider 결과가
  아니다.
- 세 번째 candidate-stage 후속은 obligation-owned seed preservation owner를
  수정했다. 필수 숫자 그룹은 선호 statement type이나 context-only generic hint보다
  실제 local header/value 또는 full pipe row와 더 구체적인 declared surface를 먼저
  보존한다. Section/table context, index prefix와 flattened summary는 atomic witness나
  binding 권위가 아니다. 불변 Samsung SQLite의 no-call projection에서 기존 retrieved
  8개는 그대로이고 canonical source `20240312000736:80:2`가 seed window에 추가됐다.
  원본 SHA-256은
  `f492d72be2753ac7a1c3012a36176d8c9ccf0d84fff1cc422c00e47fd5609ed0`로
  동일하다. 이는 이전 partial artifact를 pass로 바꾸는 provider acceptance가 아니다.
- `financial_calculation_execution.py`는 참조, AST, 상수, 단위, scope/context,
  coupling, 순환 의존성, 0 나눗셈과 required-obligation 완전성을 fail-closed로
  검증한다. 불완전하면 최대 한 번 누락/모호 obligation만 재컴파일하며,
  valid output을 다시 바인딩하지 않는다.
- 현재 코드 기준 no-call 검증은 semantic-program 95/95, evaluator projection 69/69,
  adjacent 151/151(해당 evaluator와 import 19/19 포함), runtime-domain audit
  86 reviewed literals, canonical graph DAG, affected pycompile 5개, 전체 unittest
  676/676을 통과했다. 이번 신규 12개 테스트와 기존 override 전용 8개 테스트 삭제는
  표시·단위·scope·provenance, 실제 graph→ledger→evaluator projection, 정성 점수
  독립성을 고정한다. 고정 structured output·mock catalog·mock judge를 사용했으며
  실제 retrieval/provider end-to-end acceptance를 뜻하지 않는다.
- 세 owner repair의 최소 integration admission도 provider 없이 완료했다. 정확히
  `HYU_T2_010`, `HYU_T3_072`, `SAM_T2_078`, Hyundai-then-Samsung, 한 번 실행,
  automatic run retry 없음, `$0.40` ceiling으로 고정한 manifest SHA-256은
  `e9839d111f9bd76a674ee7dd7c4c0d59f75e0836f74cd3e364b2f39b4803435e`다.
  Google query/routing embedding과 두 agent LLM route, evaluator LLM, OpenAI
  evaluator answer-relevancy embedding을 모두 열거했다. Production `eval-only`
  진입에서 첫 vector-store/provider construction 직전에 차단한 두 회의 5,302-byte
  canonical receipt는
  `fdfbf90f3adb195e9ffe7134177ac68bc856c8fdfe9e40719c09d04ae66459af`로
  byte-identical이다. Provider/network/output은 0이고 source fingerprint, absent
  target, temporary-store set은 불변이었다.
- 이전 generic-repairs 단계에서 사용자가 그 exact manifest를 승인해 replay를 한 번
  실행했다. 2/2 company와 3/3 question이 283.0초에 runtime error 0, ledger
  integrity `ok`로 끝났고 automatic run retry는 없었다. 18 LLM calls,
  556,699 tokens, query embedding 33회, document embedding 0회, runner-estimated
  `$0.2662671`로 `$0.40` ceiling 아래 `$0.1337329`를 남겼다. Embedding 가격은
  profile에 없어 이 추정에 포함되지 않는다. 실행 뒤 Hyundai/Samsung whole-store
  fingerprint와 raw SQLite SHA-256은 admission 때와 동일하고 임시
  `dart_eval_store_*`도 남지 않았다.
- 그 이전 run의 semantic acceptance는 1/3이었다. `SAM_T2_078`은 canonical
  `연구개발비용 총계 / 28,352,769 / 백만원 / 20240312000736:80:2`와 scope note,
  Harman 근거를 결합해 2/2 obligation, calculation/grounded rendering `1.000`으로
  닫혔다. `HYU_T2_010`은 2023 exact candidate는 prompt에 들어왔지만 2022 exact
  candidate는 빠졌고, compiler가 제안한 대체 후보의 segment/basis provenance가
  requirement와 맞지 않아 1/2 `partial`로 fail-closed 됐다. `HYU_T3_072`는 query에
  없던 연결/별도 hard scope가 모두 `unknown`으로 정규화되어 이전 planner 결함은
  닫혔지만, 같은 Motional 행에서 고른 지분율·장부금액·당기순이익 후보의 unit/display
  metadata가 비어 `empty_direct_rendering`으로 거절되어 0/5 `incomplete`다.
- 두 Hyundai 잔여의 provider-free 특성화와 일반 수정은 끝났다. Semantic query
  budget은 composite query를 보존하면서 각 required obligation/input group의
  specific query를 하나씩 먼저 예약한다. 저장 T2 계획의 기초·기말·서술 그룹과,
  source-defined summary로 고친 T3 계획의 지분율·장부금액·손익 그룹이 모두 기존
  총 budget 안에서 예약됐다. Formula variable은 candidate metadata가 unknown인
  `segment`/`basis`만 LLM-declared applicability로 보완할 수 있고 explicit conflict,
  company, period, consolidation scope는 계속 거절한다.
- T3 상세표의 24개 peer chunk에는 unit hint가 없으므로 unitless leaf value를
  복원하지 않았다. 연결 주석 source `20240313001451:183:93`은 `백만원`과 실제
  source schema인 영업수익·계속영업손익·기타포괄손익·총포괄손익을 보존한다.
  Planner는 사용자가 구성 항목을 열거하지 않은 `요약 손익`을 관행적인 여러 direct
  metric으로 발명하지 않고 하나의 narrative obligation으로 남긴다. 저장 BM25에서
  손익 specific query는 이 explicit-unit source를 6위에 올렸다. 이는 retrieval
  admission 검증이지 새 compiler/provider acceptance가 아니다.
- Hyundai SQLite와 structure graph SHA-256은 각각
  `73b65b54dfdd6d63390a219f67b4d8a8e61b7169be481a3fc1f6c586db31db37`,
  `110e7063e78f5a75a92fb602c552761304937d3e26329500cf87cd33a374740a`로
  불변이고 임시 `dart_eval_store_*`도 없다. 이번 후속의 provider, embedding,
  evaluator, Chroma-client, benchmark 호출은 모두 0이다.
- 새 no-call admission도 완료했다. Schema-v3 manifest
  `4e3e1d8df40cd25d8fa850eb9f571ec76dadbfc13b7154b22e67d9d96acfe3e4`는
  127-file runtime build
  `9fabb94a8106befedd43db769bffb9af3131240b807f504a668385cdf83eb1c9`,
  기존 profile/dataset과 정확히 `HYU_T2_010`, `HYU_T3_072`, `SAM_T2_078`,
  Hyundai-then-Samsung, one eval-only execution, automatic run retry 없음,
  `$0.40` ceiling을 묶는다. 최신 same-scope runner estimate는 `$0.2662671`이며
  embedding 가격은 포함되지 않고 ceiling은 진행 중 request를 중단할 수 없다.
- Production-order rehearsal 두 회는 첫 vector-store/provider construction 전에
  차단됐고 5,189 canonical bytes가 receipt
  `7f2068120e3c5d6f35b3cb20d810fdae6c0f70587571d13009ccbb71f45b3e91`로
  byte-identical이다. Source fingerprint, absent target, temp-store set은 불변이고
  이 rehearsal의 provider constructor/network/benchmark output은 모두 0이었다.
  이후 사용자가 exact manifest를 승인했고, 실행 직전 동일 receipt와 input hash를
  다시 확인한 뒤 최신 3문항 successor를 한 번 실행했다.
- 최신 run의 기록은 17 LLM calls, 467,828 tokens, 문항별 query embedding 33회,
  document embedding 0회, runner-estimated `$0.2437528`이다. `$0.40` 한도 아래
  `$0.1562472`를 남겼지만 embedding 가격은 포함되지 않는다. 별도로 승인된
  router 초기화의 74-query embedding batch 2회는 문항별 usage 밖의 로그에 남는다.
  내부 compiler retry는 순서대로 1/1/0회였고 automatic run retry는 없었다.
  실행 뒤 source whole-store/SQLite, runtime/profile/dataset hash와 사용자 파일은
  불변이며 임시 store는 모두 정리됐다. 결과 top SHA-256은
  `6e2165cf0c6f966e509d59e556f9fc76f5e0bee30d249ce246b7679511942b16`이다.
  세부 acceptance와 다음 범위는 `project_status.md`의 Next Work를 따른다.
- 승인된 provider-backed store-fixed 재검증은 `SAM_T2_078`, `NAV_T2_006`,
  `LGE_T1_051`을 순차 실행했고, 별도 승인된 LGE-only successor가 마지막 경계를
  확인했다. Samsung은 `연구개발비용 총계 / 28,352,769 / 백만원`과 Harman 설명을
  2/2 obligation으로, NAVER는 같은 커머스 행의 `2,546.6 / 1,801.1억원`,
  계산·원문 표시 `41.4%`, Poshmark 설명을 4/4 obligation으로 보존했다.
- LGE-only successor는 한 번의 targeted retry 뒤 553개 catalog / 128개 prompt
  후보에서 같은 연결 주석의 `영업이익(손실) 2,163,234백만원`과
  `기타영업손익 676,874백만원`을 선택했다. 같은 표 문맥의 설명이 후자를 IRA
  첨단제조 생산세액공제 수익으로 직접 연결하므로, 이는 prose의 반올림 표시
  `6,769억원`보다 정밀한 compatible source다. 계산은
  `2,163,234 - 676,874 = 1,486,360백만원`, execution 3/3, ledger integrity `ok`,
  numeric PASS다. 혼합 비표 문단의 `6,769억원` `sentence_value`도 catalog/prompt에
  계속 남아 있으며, 후보 보존을 특정 표시의 강제 선택으로 바꾸지 않는다.
- curated evaluator에는 이 두 정당한 표현을 별도 atomic variant로 등록했다.
  `connected_note_precise`는 `2,163,234 - 676,874 = 1,486,360백만원`과 연결
  주석 provenance를, `management_discussion_rounded`는
  `2조 1,632억원 - 6,769억원 = 1조 4,863억원`과 해당 문단 provenance를 한
  묶음으로 요구한다. 서로 다른 variant의 operand/result 교차 조합은 실패한다.
  기존 저장 LGE artifact의 no-call evaluator replay는 precise variant를 선택해
  numeric/operand/result/calculation `1.000`을 기록했다. 새 provider 실행은 아니다.
- 두 `0.700`은 no-call로 서로 다른 경계임을 확인했다. LGE의 세 obligation은
  회사·2023년·연결 범위를 공통으로 갖지만 기존 renderer가 이를 버리고
  `항목: 값`만 이어 붙였다. 이제 모든 rendered obligation에 같은 non-unknown
  scope만 첫 숫자 문장에 한 번 투영하고 나머지도 완전문장으로 렌더링한다.
  저장 LGE 프로그램을 순수 executor로 재실행했을 때 3/3 값과 candidate/source
  trace는 그대로였고 missing obligation은 없었다. 새 evaluator/provider 점수는
  만들지 않았다.
- NAVER의 선택 후보 4개, runtime evidence 4개, retrieved preview 8개에는 judge가
  요구한 두 번째 인수 효과가 하나도 없다. 따라서 renderer가 이를 보완하면
  근거 없는 생성이 된다. 이 residual은 evidence/planner/compiler coverage 관찰로
  남기며 문항별 문구는 추가하지 않는다.
- 별도 승인 아래 KB receipt `20240326000894`의 isolated canonical store를
  구축했다. 두 번의 provider-free preflight manifest는 SHA-256
  `3017fdb8cfabb65072ae5e4dff22f047f542235e93cfb3b861b791ab519de0d2`로
  같았다. 실제 store는 51개 section parent, 2,093개 chunk/embedding,
  OpenAI `text-embedding-3-large` 3,072차원이며 Chroma metadata는 오직
  `KB금융 / 2023 / 20240326000894`만 담는다. cache status는 `completed`이고
  heartbeat는 2,093/2,093, 약 128초에 종료했다.
- 실제 실행의 ingest delta는 document-embedding 33회, 2,093 texts,
  670,328 estimated tokens, LLM 0회였다. 다만 ingest 전에 전체
  `FinancialAgent` 생성이 semantic-router canonical query 74개를 embedding하는
  추가 endpoint 호출 1회를 만들었다. 질문/evaluator 호출은 아니지만 승인
  manifest보다 넓은 초기화였으므로, 이후 store-only 경로를 routing/evaluator를
  생성할 수 없는 최소 ingest facade로 바꾸고 테스트로 고정했다. 완성된 store를
  중복 유료 재구축하지는 않았다.
- 별도 승인된 corrected `KBF_T2_018`, `KBF_T1_017` focused store-fixed 재실행도
  끝났다. 두 번의 no-call preflight receipt는
  `d516610e26d6b8352c5901243206708cce368749e3bccd9c7652e30acb635d2d`로 같았고,
  두 실행 모두 기존 2,093-document store를 재사용해 document embedding은 0회였다.
  5문항 gate는 승인·실행하지 않았다.
- T1은 provider-backed canonical acceptance다. 2,462 catalog / 128 prompt 후보에서
  같은 NIM 행·표·source의 `1.83% / 1.73%`를 선택하고 `0.10%p`를 실행해 3/3
  obligation, task 1/artifact 4, ledger integrity `ok`, numeric PASS와
  faithfulness/completeness `1.000 / 1.000`을 기록했다.
- T2는 numeric PASS와 4/4 execution이어도 canonical acceptance가 아니다.
  선택 fingerprint는 MDA 표의 `3,146억원 / 1,848억원 / 70.24%`였고, 질문이
  명시한 연결 포괄손익계산서의 canonical 행은 `20240326000894:470:1`,
  `3,146,409백만원 / 1,847,775백만원 / 약 70.28%`다. evaluator 점수와 ledger
  무결성은 잘못된 source row를 정당화하지 않는다.
- 원인은 두 층이다. retrieval query 8개가 같은 obligation objective라는 이유로
  첫 검색 결과를 7회 재사용해 exact statement candidate가 catalog/prompt에
  들어오지 못했다. 이제 query-result cache는 exact source/query/filter만 재사용하고
  서로 다른 semantic query는 독립 실행한다. 또 원문 MDA 단위는 `십억원`인데
  parser가 suffix `억원`으로 잘랐다. unit token을 longest-first로 인식하도록 고쳤다.
- no-call 검증은 retrieval 22/22, parser 31/31, semantic-program 46/46,
  runtime-domain audit 86, 전체 unittest 614/614다. 이 수치는 cache/parser
  no-call successor의 기존 검증 기록이며 이번 fresh replay 뒤 다시 실행한 수치가
  아니다.
- 별도 승인 아래 parser signature가 반영된 isolated KB successor store를 새로
  구축했다. 두 번의 store-only preflight manifest는
  `50260722b3c567e56404053fc9f93e1df22a67fd51d33c94bd592bac10b7b600`으로
  같았다. 약 100초 동안 51 section parent와 2,093 chunk/embedding을 만들었고,
  document embedding은 33회/2,093 texts/670,334 estimated tokens였다. 질문·평가
  LLM 호출은 없었다. MDA `20240326000894:1616:1`은 이제 `십억원`, canonical
  income-statement `20240326000894:470:1`은 `백만원`으로 저장되어 parser 수정은
  실제 store에서 확인됐다.
- focused pair의 production-order preflight도 두 번 동일한 receipt
  `4615185a56da5060df7b1ed6c7f98e025556cb134287b201a7d82c099a2fdb97`를
  만들었다. T2 실행 뒤 Chroma SQLite raw byte가 바뀌어 T1 전에는 새 store
  snapshot에 대해 다시 두 번 rehearsal했고 receipt는
  `09b11b482266a06a133b721073002d471fadae036a733ccb92bad6508982c21b`였다.
  두 focused run 모두 document embedding은 0회였고 5문항 gate는 승인·실행하지
  않았다.
- fresh-store `KBF_T2_018`은 8개의 서로 다른 query를 실제로 8회 실행해 이전
  objective-cache collapse가 사라졌지만, 모든 query에 같은 긴 risk/section suffix가
  붙어 최종 evidence 8개가 전부 연결재무제표 주석으로 수렴했다. canonical
  statement 후보 `cand_e1d8aa527b06dfafde43`와
  `cand_ac08297806e6475c8ecd`는 prompt에 들어가지 못했고 compiler는 0/2
  obligation, evaluator `UNCERTAIN`, completeness `0.0`으로 종료했다. 이는 계산
  문제가 아니라 generic query-enrichment/evidence-coverage 문제다.
- fresh-store `KBF_T1_017`은 prompt에 같은 NIM 행의 `1.83%`와 `1.73%`가 모두
  있었다. 첫 compiler program은 period-scope 검증에서 거절됐고, 한 번의 retry는
  두 번째 operand를 candidate ID로 직접 bind하지 않고 존재하지 않는 `ob_003`을
  만들었다. validator는 이를 fail-closed로 거절했다. evaluator numeric PASS와
  무관하게 semantic result는 1/2 obligation partial이므로 canonical acceptance가
  아니다.
- eval-only Chroma open이 logical fingerprint와 2,093 embedding을 보존하면서
  source SQLite raw SHA를 바꾼 관찰은 generic no-call 계약으로 닫았다. hard report
  scope와 query별 semantic enrichment를 분리했고, derived output과 비표시
  `evidence_requirements`의 scope를 분리했으며, candidate 변수는 해당 requirement
  ID를 명시적으로 bind한다. retry에는 허용된 candidate/obligation/requirement ID만
  제공하고 validator는 미등록 ID를 계속 거절한다.
- eval-only는 source store 전체 바이트를 fingerprint한 뒤 동일한 disposable copy만
  열고, Chroma client 종료 후 source fingerprint를 재검증하고 copy를 삭제한다.
  이 no-call successor 자체는 provider/benchmark/report fetch/ingest/query
  embedding/LLM 호출이 없었다.
- 이후 별도 승인된 `KBF_T2_018 -> KBF_T1_017` store-fixed replay를 실행했다.
  두 실행 모두 document embedding 0회였고 source-store fingerprint는 실행 전후
  `484899d27e2b5469c79b1865d287945e634566af7c805898d37714e589404dd4`로
  같았다. 5문항 gate는 승인·실행하지 않았다.
- T2는 3,918개 catalog / 128개 prompt 후보와 한 번의 compiler retry 뒤에도
  선택 후보 0개, 0/2 obligation, numeric FAIL로 종료했다. 8개 검색은 서로
  독립 실행됐지만 숫자 query도 서술 obligation의 risk/주석 prior를 공유해 최종
  8개 evidence가 전부 연결재무제표 주석으로 수렴했고 canonical
  `20240326000894:470:1`은 catalog에 들어오지 못했다.
- T1은 1,650개 catalog / 128개 prompt 후보에서 첫 시도에 같은 NIM 행·표·source의
  `cand_fa953151cf02e5921f0b = 1.83%`와
  `cand_4de1f1e0c09dfb8d30d1 = 1.73%`를 각각
  `ob_002:req_001`과 `ob_002:req_002`에 bind했다. `nim_2023 - nim_2022 =
  0.10%p`, 2/2 output, missing 0, numeric PASS이므로 source/program 계산은
  canonical로 인정한다. completeness `0.700`은 답변이 방향어를 생략한 별도
  정성 평가 신호이며 계산 trace를 뒤집지 않는다.
- paid replay 뒤 추가 provider 호출 없이 검색 소유권을 planner가 선언한
  obligation/evidence-requirement 단위로 좁혔다. 숫자 query에는 서술 policy를
  섞지 않고, required numeric input은 전체 chunk와 공백 변형을 검사하며,
  ordered statement type과 구조화 표를 우선해 각 requirement의 best source를
  `seed_retrieved_docs`에 보존한다. 실제 저장 store의 no-call probe는
  `20240326000894:470:1`을 1순위로 선택했다.
- 2026-08-29 별도 승인 범위로 `KBF_T2_018`만 다시 store-fixed replay했다. 두
  production-order no-call receipt는
  `4c062416c1c8ed12a0004be688e156632b7e2b61081c4ce872e246a93bef8c5c`로
  같았고, document embedding은 0회였다. canonical row `470:1`은 최종 retrieval
  rank 6까지 들어왔지만 compiler의 4,447 catalog / 128 prompt 후보에는 정확한
  숫자 cell이 없었다. 한 번의 retry 뒤 selected candidate/output은 0, obligation은
  0/2였고 evaluator는 `UNCERTAIN`, completeness `0.000`, refusal accuracy `1.000`을
  기록했다. 5문항 gate는 승인·실행하지 않았다.
- 실패는 세 일반 계약으로 좁혀졌다. 여러 줄 `table_header_context`를 한 줄로
  평탄화해 첫 data preview 값을 기간으로 오인했고, 공백만 다른 label이 prompt
  relevance에서 탈락했으며, mixed question의 required narrative obligation은
  numeric-only seed group과 공용 prompt relevance에 가려졌다.
- no-call successor는 header line을 보존하고 숫자형 data preview를 배제하며,
  공백 동치 relevance와 numeric/narrative별 prompt group을 사용한다. required
  evidence supplement는 숫자 입력에는 compatible table best를, narrative에는
  period-only hint를 제외한 여러 설명형 후보를 bounded policy로 보존해 최종 의미
  선택을 compiler에 남긴다.
- 저장 store probe에서 `470:1`의
  `cand_e1d8aa527b06dfafde43 = (3,146,409), 2023`과
  `cand_ac08297806e6475c8ecd = (1,847,775), 2022`, 그리고 원인 문단
  `493:16`의 `cand_eca9ff59eee4097a3e74`가 모두 prompt에 들어갔다. 고정 program은
  validator `ready`, execution `ok`, 2/2 output과 `70.28%`를 만들었다. 이는
  provider acceptance가 아니다. source-store fingerprint는 계속
  `484899d27e2b5469c79b1865d287945e634566af7c805898d37714e589404dd4`다.
- 이어 별도 승인된 `KBF_T2_018` 단독 acceptance replay를 현재 head에서 실행했다.
  두 production-order no-call receipt는
  `e172d03e065ba0ae641c08cbb563e2a3a681d35acb8aa220e4f99f5a0b8084e0`로
  같았다. compiler는 retry 없이 4,196개 catalog 후보 중 5개를 선택하고 2/2
  obligation을 실행했다. 동일 연결 손익계산서 행 `470:1`의
  `(3,146,409)백만원 / (1,847,775)백만원`을 `abs` 증가율로 계산해 `70.28%`를
  반환했고 numeric PASS, calculation/grounded rendering `1.000`, ledger integrity
  `ok`였다. document embedding은 0회이고 source-store fingerprint는 계속
  `484899d27e2b5469c79b1865d287945e634566af7c805898d37714e589404dd4`다.
- 숫자 source/program은 canonical이지만 mixed 답변 전체는 아직 acceptance가
  아니다. compiler가 일반 자산·대출 증가 문단을 충당금 증가의 직접 원인처럼
  서술했다. qualitative completeness는 `0.700`이었고 evaluator의 원문 numeric
  grounding 응답도 이 인과 비약을 지적했지만, 숫자 역할의 deterministic operand
  override가 계산 판정만 `PASS`로 유지했다. 이는 의도한 역할 분리이며 서술
  obligation의 의미 완전성을 대신하지 않는다.
- 추가 provider 호출 없이 narrative 원인·관계도 planner가 별도
  `evidence_requirements`로 선언하고 task/retrieval이 그 요구를 소유하도록 했다.
  compiler는 `evidence_bindings`로 candidate ID와 requirement ID를 연결해야 하며,
  일반 배경·다른 지표의 동시 변화·위험관리 절차를 직접 인과 근거로 승격하지
  못한다. required binding 누락·unknown·cross-obligation·scope mismatch는
  fail-closed다. focused 118/118, runtime-domain audit 86, full unittest 635/635가
  통과했다.
- 이어 사용자가 승인한 `KBF_T2_018` 단독 replay를 새 output successor에서 한 번
  실행했다. 두 no-call receipt는
  `3b10ce5c6537df882fef87de2eb2205051bf662cebf265679af52f930301ebb6`로 같았다.
  compiler는 4,305개 catalog에서 5개를 retry 없이 선택했고, 동일 `470:1` 행의
  두 값을 계산해 `70.28%`, 2/2 output, ledger `ok`, numeric PASS를 유지했다.
  이번 서술은 `worse/crisis` 시나리오, Expected Loss/Economic Capital,
  Total Exposure, 미래전망정보 방법론을 선택 근거에 맞춰 기술했으며 qualitative
  completeness는 `1.000`이었다. agent/judge는 각 3회, 전체 104,248 tokens,
  query embedding 11회, document embedding 0회였다.
- 이 결과의 저장 `faithfulness=1.000`은 acceptance 근거로 쓰지 않는다. 원시
  faithfulness는 `0.500`이었고, numeric PASS가 혼합형 서술 점수 전체를 덮었다.
  evaluator judge context도 같은 runtime evidence의 `claim`/`quote_span`과 index
  metadata를 중복 넣어 4,000자 예산에서 뒤쪽 두 서술 근거를 잘랐다. 일반 후속은
  colon-bearing index metadata를 제거하고 중복 payload를 합쳐 이번 네 근거를
  3,008자로 모두 보존하며, narrative output이 있으면 numeric faithfulness override와
  numeric-fast gate를 금지한다. `format_preference=mixed`도 독립 차단하므로 서술
  output 자체가 누락된 경우에도 fail-closed다. 관련 evaluator/runner 118/118과 전체 unittest
  637/637가 통과했고 source-store fingerprint는 계속 `484899d...4dd4`다.
- 이어 별도 승인된 corrected-evaluator `KBF_T2_018` 단독 replay를 두 번의
  byte-identical production-order no-call receipt
  `b8f05c7848ed8d1cc9efd8595ab57ff439f2cb96db2e895086cd4c9ffe302905` 뒤
  정확히 한 번 실행했다. compiler는 3,741개 catalog 후보에서 3개를 retry 없이
  선택했고, 동일 연결 손익계산서 행 `470:1`의
  `(3,146,409)백만원 / (1,847,775)백만원`을 계산해 `70.28%`와 직접 근거화된
  worse/crisis 시나리오 설명을 2/2 output으로 반환했다.
- 수정 evaluator의 원시 판정은 `raw_faithfulness=1.000`이고 override reason은
  `null`이었다. numeric raw/final judgement 모두 `PASS`, completeness `1.000`,
  calculation/grounded rendering `1.000`, task 1/artifact 4, ledger integrity `ok`,
  error 0으로 corrected-evaluator focused acceptance가 닫혔다. agent/judge는 각
  3회, 전체 102,577 tokens, query embedding 11회, document embedding 0회였고
  runner 추정 비용은 `$0.0605193`이었다.
- source-store fingerprint는 실행 전후
  `484899d27e2b5469c79b1865d287945e634566af7c805898d37714e589404dd4`로
  같았고 단독 T2 acceptance HOLD는 해소됐다.
- 이어 사용자가 정확히 승인한 current-head 5문항 store-fixed gate를 두 번의
  byte-identical no-call rehearsal receipt
  `c714bdc02c891aa802eb801b57e2056a6060412cea03031ab846e3f02a2ad08e` 뒤 한 번
  실행했다. 대상은 `NAV_T2_006`, `HYU_T2_010`, `HYU_T3_072`, `LGE_T1_051`,
  `SAM_T2_078`뿐이며 source bundle은
  `policy_gate_regression_2026-06-03_1138_actual`이다.
- 실행은 520.3초에 4/4 company와 5/5 question을 오류 없이 완주했고 모든
  task/artifact ledger integrity는 `ok`였다. 그러나 다섯 문항 모두 필수
  obligation을 빠뜨려 `partial` 또는 `incomplete`였고, formal
  `full_eval_fail_count=4`로 **통합 gate는 실패했다**. screen pass count 4는
  저장 bundle 재사용 screening 신호일 뿐 semantic-program acceptance가 아니다.
- NAVER는 계산과 원문 `41.4%`는 맞지만 segment metadata가 없는 Poshmark 설명을
  strict scope가 거절해 1/2였다. 현대차 두 문항은 source text 속 숫자가 atomic
  candidate가 아니거나 상세표/MDA의 `unknown` consolidation scope가 planner의
  `consolidated` 요구와 충돌해 각각 0/2, 1/4였다. `HYU_T3_072`의 유일한 direct
  output은 unit이 `UNKNOWN`인데도 `ok`가 되어 빈 값으로 렌더링됐으므로 별도
  validator/render fail-open 결함이다.
- LGE의 정밀 `676,874백만원` 후보는 128개 compiler prompt에 있었지만 LLM이
  반올림 prose를 선택하고 선언하지 않은 formula 변수와 불완전 evidence binding을
  retry에서도 반복해 1/2였다. Samsung의 이전 수용 정밀 후보
  `28,352,769백만원`은 이번 prompt 128개에 들어오지 않았고 rounded prose 선택이
  scope/numeric 검증에서 거절돼 1/2였다.
- 공통 blocker는 특정 문항 표현이 아니라 (1) evidence surface별 scope 적용 가능성,
  (2) source-visible 수치의 atomic candidate화와 obligation별 prompt 보존,
  (3) retry의 formula/evidence binding 폐쇄성, (4) render 불가능 direct output의
  fail-closed 검증이다. 이를 generic no-call fixture로 특성화·수정한 뒤에만 새
  provider replay를 검토한다. Phase 3 리팩터링과 통합은 계속 HOLD다.
- gate는 agent/judge 합계 31 LLM calls / 939,313 tokens, query embedding 55회,
  document embedding 0회, 추정 `$0.4732093`를 사용했다. 네 source-store logical
  fingerprint는 실행 전후 같았고 결과/store/cache/heartbeat는 local-only다.
  Preflight의 provider 열거에는 Google 경로만 적혔지만 실제 evaluator는 승인된
  `five_question_evaluators` 안에서 OpenAI query embedding도 문항당 2회 사용했다.
  실행 범위를 넘긴 것은 아니나 admission manifest의 provider 완전성 residual로
  기록하며, 이번 결과를 완전한 admission 증거라고 부르지 않는다.
- 후속 provider 호출 없이 네 blocker를 generic fixture로 먼저 재현한 뒤 수정했다.
  Narrative compiler는 metadata가 비어 있는 `consolidation_scope`, `segment`,
  `basis`에만 `scope_applicability_fields`를 선언할 수 있고 explicit conflict,
  company, period는 계속 fail-closed다. Required evidence scope에도 같은 제한을
  적용한다.
- `financial_numeric_surface.py`는 policy의 한국어 count unit과 scale을 사용해
  `1,560만 대`, `87.0만 대`를 `COUNT`로 정규화한다. Chunk에 table metadata가
  붙어도 explicit-inline-unit 값은 atomic candidate로 남기되, 같은 source의
  structured value와 normalized value/unit이 같으면 중복만 제거한다.
- Prompt admission은 source diversity가 전체 group budget을 독점하지 않게 충분히
  큰 group의 1/4을 relevant alternate row에 남기고 `aggregate_label`을 semantic
  relevance surface로 사용한다. 이는 candidate visibility만 바꾸며 answer를 코드가
  선택하지 않는다.
- Targeted retry에는 obligation별 required requirement ID, validation error,
  formula AST variable과 variable binding의 exact-set invariant를 전달한다. Direct
  binding은 requested unit과 dimension이 맞고 source-grounded display가 비어 있지
  않을 때만 `ok`가 된다. Semantic 58/58, 인접 131/131, audit 86, import/DAG
  20/20, pycompile, legacy symbol 0, full 641/641, diff check가 통과했다.
- 이 결과는 no-call contract close일 뿐 provider acceptance가 아니다. 실패한
  5문항 gate가 최신 integration evidence이며, 다음 store-fixed replay는 provider
  경로와 exact cost ceiling을 새 manifest에 묶고 별도 승인을 받은 뒤에만 한다.
  Phase 3 리팩터링은 계속 중단한다.
- 사용자는 이어 네 generic contract 수정 head를 검증하는 동일 5문항 store-fixed
  gate를 정확히 한 번 승인했다. production-order preflight receipt는
  `c48b007fdeeb457fe3fdb977a044b1816d4043c3857de65acba4af9df55640e3`,
  runtime build SHA-256은
  `e4daebab644cf978f21942f73fac49f03788b03c1abe6638ce9e406e1ad5e794`다.
  Google agent/evaluator/query-embedding 경로와 OpenAI evaluator answer-relevancy
  embedding을 모두 명시했고, fresh ingest, document embedding, KB row, 다른
  question ID와 자동 full-run retry는 허용하지 않았다.
- successor는 508.3초에 4/4 company와 5/5 question을 오류 없이 완주했다. 31 LLM
  calls / 927,550 tokens, query embedding 55회, document embedding 0회였고 runner
  추정 비용은 `$0.4644884`로 승인 상한 `$0.60` 이하였다. top-level result SHA-256은
  `e5a13e15a25ac295157ff469b53cd0bf055050edf6060ee89910d31351c9269c`다.
- 그러나 **integration gate는 다시 실패했다**. 다섯 row 모두 `partial`, 모든
  task/artifact ledger는 integrity `ok`, error rate는 0, formal
  `full_eval_fail_count=4`다. company-average faithfulness/completeness/context
  recall은 `0.800 / 0.3875 / 0.953125`이고, 유일하게 numeric judgement가 적용된
  LGE는 FAIL이다. screen pass 4는 여전히 저장 bundle screening일 뿐 acceptance가
  아니다.
- NAVER는 올바른 `2,546,649 / 1,801,079백만원`과 원문 `41.4%`를 골랐지만, 첫
  상대기간 candidate는 period scope에서, 명시적 2022 candidate는 서로 다른 report
  context fingerprint에서 거절돼 계산 obligation이 빠졌다. LGE도 retry가 올바른
  `2,163,234 / 676,874백만원`과 정확한 차감식을 만들었지만 연결 손익계산서와 연결
  주석의 fingerprint가 다르다는 이유만으로 derived output이 거절됐다.
- `HYU_T2_010`의 narrative는 새 `scope_applicability_fields`를 통해 통과했지만
  `87.0만 대 / 78.1만 대` atomic input은 compiler prompt에 없었다. Samsung의
  `28,352,769백만원` canonical aggregate도 runtime catalog/program에 들어오지
  않았다. 두 값은 결과 artifact의 benchmark answer/evidence 쪽에만 있으므로
  runtime retrieval 성공으로 간주하지 않는다.
- `HYU_T3_072`는 Motional이 아니라 `중국` 행의 `53%`를 선택했는데 segment/subject
  metadata가 비어 있어 direct validator가 이를 허용했다. 같은 retry의 Motional
  장부금액과 손익 후보는 보였지만, planner가 `direct_value`로 선언한 값을 원 단위로
  바꾸기 위해 LLM이 `* 1000000` expression을 붙여 validator가 올바르게 거절했다.
  상세표 원문에 함께 보이는 sibling cell도 각각 bind 가능한 candidate ID로 충분히
  확장되지 않았다.
- 따라서 다음 provider-free 작업은 세 일반 계약을 먼저 특성화하는 것이다:
  (1) 동일 metric/범위의 인접기간과 명시적으로 연결된 statement-note operand를
  exact fingerprint equality 대신 검증 가능한 semantic compatibility로 다루기,
  (2) obligation-owned atomic numeric/structured-row sibling admission으로 source-
  visible count와 aggregate cell을 prompt에 보존하기, (3) direct binding의 subject/
  row identity를 fail-closed로 검증하고 단위 변환을 계산식이 아닌 deterministic
  display normalization으로 처리하기. 재실행이나 Phase 3 owner move는 아직
  승인되지 않았다.
- 네 source-store fingerprint는 전후 동일했고 disposable Chroma copy는 모두
  제거됐다. successor 결과/store/cache/heartbeat는 local-only이며 자동 retry는
  실행하지 않았다. 이 successor가 최신 integration evidence다.
- 후속 provider 호출이나 runtime 수정 없이 세 잔여를
  `tests/fixtures/semantic_program_contract_residuals.json`의 generic
  `known_failure_characterization`으로 고정했다. 특정 회사명·benchmark ID·answer
  key·provider output은 fixture에 없다. 기존 semantic-program baseline 58/58 뒤
  3개 characterization을 추가한 focused suite는 61/61이다.
- 동일 metric·scope의 인접 report-period case와 동일 회사/기간/연결/basis의
  statement-note 차감 case는 다른 검증 오류 없이 오직
  `expression_context_mismatch: context_fingerprint`로 거절된다. 이는 scope나 단위
  문제가 아니라 exact context identity policy의 현재 경계임을 분리한다.
- 표 metadata의 `table_value_labels_text`에는 requested share/carrying/net-result,
  aggregate, current/prior count 여섯 값이 모두 보이지만 bindable catalog에는 현재
  선택 행의 `53`만 생긴다. source visibility와 immutable candidate availability가
  별개임을 고정했다.
- 첫 구현 seam에서 direct subject/row identity fail-open을 닫았다. Candidate catalog는
  structured `row_headers`를 보존하고, row-backed numeric direct binding은 명시적
  `segment` 또는 candidate-local row label/header만 주체 근거로 사용한다. 표 전체
  `source_text`에 요청 문자열이 있어도 로컬 행이 모순되면
  `candidate_subject_mismatch`로 거절한다.
- 로컬 행 정체성이 아예 없을 때만 같은 source의 narrative witness가 요청 주체를
  실제로 match하면 compatibility bridge를 허용한다. Witness는 명시적으로 다른
  로컬 행을 덮어쓸 수 없다. Wrong-row negative, structured same-row positive,
  compatibility positive/negative가 모두 통과한다.
- Candidate-catalog completeness 감사는 historical Samsung/Hyundai SQLite를
  `mode=ro&immutable=1`로만 열었다. 전후 file length/SHA-256은 Samsung
  `40,361,984 / f492d72be2753ac7a1c3012a36176d8c9ccf0d84fff1cc422c00e47fd5609ed0`,
  Hyundai `69,447,680 / 73b65b54dfdd6d63390a219f67b4d8a8e61b7169be481a3fc1f6c586db31db37`로
  동일하다. Provider, benchmark, ingest, embedding, evaluator는 실행하지 않았다.
- 최신 parser의 structured row/value records는 full header chain과 local row/value/unit/
  source를 stable ID로 보존한다. 오래된 store도 full pipe row는 남아 있었지만 fallback이
  마지막 physical header line만 골라 반복 leaf header의 parent group을 잃고 있었다.
  이제 valid header row를 column별 ordered chain으로 병합하여 opening `25.92`와 closing
  `25.81`, 각 carrying value와 latest result를 구별한다. Flattened
  `table_value_labels_text`는 계속 candidate 권위가 아니며 cross-row pairing은 금지된다.
- Generic structured/legacy/flattened/sibling-admission 계약 뒤 provider-free 검증은
  semantic-program 67/67, import/DAG 19/19, runtime-domain audit 86, full discovery
  650/650이다. Direct display는 여전히 요청 result unit과 source-visible `700백만원`을
  함께 보존하는 별도 characterization이다.
- Saved successor에서 Motional target-row leaf candidates는 이미 prompt에 있었으므로 그
  wrong-source 선택은 catalog miss가 아니다. 반면 reconstructed Samsung total과 두
  Hyundai sales-count stable ID는 saved prompt에 없지만, 당시 trace에는 seed/catalog source
  identity가 없어 source-window absence와 prompt-budget drop을 구분할 수 없다. 다음 작업은
  compact candidate-stage provenance observability와 admission characterization이다. Compiler
  retry/selection, expression compatibility, display-unit semantics, Phase 3, provider replay는
  별도 seam/HOLD다.
- Candidate-stage observability 구현은 retrieval trace에 retrieved/seed window의 ordered
  stable source ID와 unidentified count를 남긴다. Canonical calculation plan의
  `semantic_candidate_stage_diagnostics_v1`은 source별 source/catalog/prompt candidate count,
  kind count, sorted opaque-ID fingerprint, prompt-drop count만 보존하며 raw value, label,
  full catalog는 복제하지 않는다.
- Generic fixture는 source 자체 부재, source는 있으나 필요한 local-cell projection 부재,
  catalog에는 있으나 prompt admission에서 제거된 상태를 구분한다. 이 batch에서는 provider,
  persisted-store retrieval, embedding, ingest, store mutation, evaluator를 실행하지 않았다.
  Synthetic unit test만 trace path를 실행했고 retrieval selection, calculation/ledger, dataset
  semantics는 바꾸지 않았다. 따라서 saved successor를 사후 분류하거나 정책을 추측해서
  수정하지 않는다.
- 최소 affected store-fixed admission은 `HYU_T2_010`, `HYU_T3_072`,
  `SAM_T2_078`과 Hyundai/Samsung 두 company run으로 고정했다. Runtime build
  `4f84b59ea1926c5a2306bc2e602e29fee68b3526bd9997dbed4ee8eff53155e0`에서
  production-order no-call rehearsal 두 회가 byte-identical receipt
  `0c229555c3cd9d9216358c7393a26f0aa6b4931eaa404a007197a3facf2d9da4`를 만들었고,
  사용자가 승인한 정확히 한 번의 provider-backed replay를 같은 manifest로 실행했다.
- Monitored eval-only run은 373.4초에 2/2 company와 3/3 question을 error 0,
  task/artifact integrity `ok`로 완료했다. 그러나 세 row 모두 `partial`이다.
  `HYU_T2_010`은 1/2 obligation, `HYU_T3_072`는 1/3 obligation,
  `SAM_T2_078`은 1/2 obligation만 충족했으므로 acceptance는 실패했다.
- 새 trace는 손실 owner를 구분했다. `SAM_T2_078`의 canonical total source
  `20240312000736:80:2`는 retrieved/seed window 모두에 없어 source-window/retrieval
  absence다. `HYU_T2_010`의 `87.0만 대`와 `78.1만 대` source는 seed에 있고
  runtime catalog fingerprint도 offline reconstruction과 일치하지만 해당 candidate는
  128개 prompt에서 탈락했다. `HYU_T3_072`의 target-row `25.81`, `1,294,367`,
  `-803,742` candidate는 prompt에 모두 있었으나, 질문에 명시되지 않은
  `consolidated`/`separate` scope를 requirement planner가 hard constraint로 만들고
  compiler가 direct obligation에 expression을 제안해 validator가 fail-closed했다.
- 실행은 18 LLM calls / 573,899 tokens / query embedding 33회 / document embedding
  0회 / runner 추정 `$0.3156427`로 `$0.40` 상한보다 `$0.0843573` 낮았다. Embedding
  가격은 runner 추정에 포함되지 않는다. 자동 retry, fresh ingest, 다른 row 실행은 없었다.
  결과 top SHA-256은
  `49351e06df72722a63ae4209e358cb84c9dc73a3403912c385576a84bdd4c6a7`이다.
- 실행 후 admission file-manifest store fingerprint는 Hyundai/Samsung 각각
  `e2e0d391449d1e87efe43b722dc6ca6fc60271894cd2669575d46f138ed6026a`,
  `b39280122c6e4d6989e3050dcd727545b1b90e1c7dab60bd16c33ac1fa5d79b7`로 사전 값과
  같았다. Raw SQLite SHA-256도
  `73b65b54dfdd6d63390a219f67b4d8a8e61b7169be481a3fc1f6c586db31db37`,
  `f492d72be2753ac7a1c3012a36176d8c9ccf0d84fff1cc422c00e47fd5609ed0`로 유지됐고
  남은 `dart_eval_store_*`는 0개다.
- 세 owner의 provider-free characterization과 in-place repair는 모두 끝났다. 마지막
  generic fixture는 preferred-statement generic total, scope-only context note, local
  row/value source를 분리했고 기존 우선순위가 첫 후보를 잘못 예약하는 실패를 고정했다.
  수정 후 source-visible atomic row가 seed 예약을 소유한다. 저장 Samsung source는
  `mode=ro&immutable=1`로만 읽었고 Chroma/provider/embedding/evaluator는 호출하지 않았다.
- 다음 안전한 작업은 같은 3문항 store-fixed successor의 production-order no-call
  manifest와 두 번의 byte-identical rehearsal을 준비하는 것이다. 실제 provider replay는
  새로운 정확한 비용·범위 승인이 있기 전까지 금지한다. 회사명·문항 ID·정답 값 runtime
  분기와 Phase 3은 계속 HOLD다.

## 이전 release checkpoint (historical)

아래 표와 세부 checkpoint는 semantic calculation program 전환 전의 release
증거다. 새 canonical 경로의 현재 성능이나 provider replay 결과로 해석하지 않는다.

| 항목 | 현재 상태 |
| --- | --- |
| Source checkpoint | semantic source-scope/evaluator 계약은 `d87e030`, GitHub Actions `33007869709` green; 그 전 release stabilization `6d6ca01`, evidence docs `99c4429`, cross-platform receipt fix `40ae6a7`, failed-canary docs `aaf920a`가 있으며 `main`은 `f0a5145` |
| Public numeric contract | `resolved_calculation_trace`, explicit `structured_result`, task/artifact projection |
| Default runtime boundary | MAS/eval/benchmark/promotion/cache 구현은 unconfigured import/invocation에서 격리 |
| Calculation ownership | graph-state orchestrator와 state-free owner들로 분리 중; runtime/ontology deterministic planning은 `financial_calculation_execution.py`, semantic-planner shape/segment/task validation과 narrative-task policy projection은 `financial_graph_helpers.py`, desired consolidation-scope와 query/task/operand/report period·single-report-scope·strict-company-scope·report-source receipt·year-token projection 및 candidate period/table coherence policy는 `financial_scope_policies.py`, generic operation-family/numeric-grounding policy는 `financial_operation_policies.py`, structured-cell selection/scoring과 candidate selected-cell preparation은 `financial_structured_cells.py`, candidate concept-conflict·contextual-aggregate preference·note-aggregate lookup preference·balance-sheet aggregate-operand·CAPEX total-operand와 surface/segment/metadata policy projection은 `financial_surface_contracts.py`, row text·column-candidate label·delta-like row-label·aggregate-like row 및 candidate value-role/stage·candidate operand-context/structured-sibling·segment-local/segment-metric composition·sibling-surface hit count는 `financial_row_surfaces.py`, lookup-hint projection/match·direct candidate logical/family signature·candidate location/entity subject score·deterministic positional preference bonus·candidate source-priority score·complete operand-candidate scoring·candidate-to-operand matching·candidate direct-match strength·direct candidate semantic priority·canonical-statement winner·ratio-component acceptance·direct-grounding 및 direct-acceptance classification과 operand resolution은 `financial_operand_resolution.py`, aggregate calculation/public projection·bounded repair·quantitative-impact parsing/composition은 `financial_aggregate_projection.py`, statement/section hint inference와 read-only focus/section/compression 및 query-to-metric/operand match projection은 `financial_retrieval_hints.py`, structured-result subtask-row/answer projection·nested-result evidence collection과 collapsed-ratio evidence repair는 `financial_runtime_trace.py`, direct structured lookup과 lookup answer-slot/support projection은 `financial_lookup_recovery.py`, nested result와 preferred complete aggregate-answer selection은 `financial_answer_projection.py`, query-focus/source-visible text projection은 `financial_text_surface.py`, caller-facing run projection은 `financial_agent_run_projection.py`, prepared candidate와 structured period-pair projection은 `financial_reconciliation_candidates.py`, reflection retry-query projection은 `financial_reflection_projection.py`에 귀속 |
| Phase 3 | OPEN but **REFACTORING PAUSED**; desired consolidation-scope, query/task/operand period-focus, single-report-scope, candidate period/table coherence와 concept-conflict·contextual-aggregate preference·note-aggregate lookup preference·balance-sheet aggregate-operand·CAPEX total-operand, location/entity subject score, deterministic positional preference bonus·source-priority score·complete operand-candidate scoring·candidate-to-operand matching·candidate direct-match strength·direct candidate semantic priority·canonical-statement winner·ratio-component acceptance·direct-grounding 및 direct-acceptance classification, column-candidate/delta-like row-label classification, structured-cell selection/scoring과 candidate selected-cell preparation, candidate report/period-scope, candidate surface-contract/segment-binding, candidate metadata-policy, segment-local/segment-metric, aggregate-like row와 candidate value-role/stage 및 operand-context/structured-sibling, lookup-hint projection/match, direct candidate logical/family signature, sibling-surface hit-count와 query-to-metric/operand match ownership까지 수렴했지만 reconciliation candidate construction/ranking, broader alignment/rebuild와 ledger ownership 전체는 미완료 |
| Runtime correctness | `SAM_T2_078`, `NAV_T2_006`, `LGE_T1_051` successor가 모두 canonical row/value/unit/source와 계산 결과를 보존했다. LGE wrong-entity fallback blocker는 닫혔고, NAVER의 1회 reflection/replan은 correctness가 아닌 efficiency residual이다 |
| Benchmark | 2026-08-27 current-head 5-question store-fixed gate는 4/4 company와 5/5 question을 완주했고 screen pass 4, error/integrity issue 0, faithfulness/context recall/grounded rendering/calculation/refusal `1.000`이다. Formal `full_eval_fail_count=1`은 `HYU_T2_010`의 LLM completeness가 출처 귀속 문구를 요구해 `0.700`을 준 정성 residual이다. Company-average completeness `0.9625`, question-weighted `0.940`; 59 LLM calls, 324,521 tokens, 45 query embeddings, 0 document embeddings, `$0.3059185`; fresh ingest evidence는 아니다 |

`2892d1b`는 94-line runtime-trace resolver를 같은 owner와 본문에서 public
`financial_runtime_trace.resolve_runtime_calculation_trace(...)`로 이름
수렴시켰다. Core private mesh는 82 records / 29 unique bindings / 30
importers, shared normalization 밖은 28/25/7이며 48/203 DAG는 불변이다.
Exact affected 101/101, corrected focused coverage 1,176/1,176, audit 217,
pycompile 18/18, fresh identity 11/11, full 2,143/2,143가 통과했다. 이어 최신
reviewer closeout이 `review_surface_ready`, fixture manifest verified, demo
13/13, integrity `ok`, critic `accepted`를 재확인했다. 이는 curated fixture
계약이지 live replay가 아니다. 이어 draft PR #86의 첫 Ubuntu run이 raw-byte
fixture hash의 CRLF/LF 의존성을 발견했고 `ab7e9ba`가 schema-v2 normalized-LF
binding과 양쪽 줄바꿈 회귀 테스트로 수정했다. Exact-head remote run
`32809007035`에서 reviewer 32/32, audit 217과 full 2,145/2,145가 통과했다.
이어 exact-profile store-fixed policy gate가 4개 회사/5문항을 error 0.0%로
완주했지만 NAVER operand/final projection 비결정성, LGE absolute-result
rendering, Samsung numeric trace 불일치와 evaluator false positive를 발견했다.
NAVER와 LGE의 첫 generic fix 및 focused replay에 이어 Samsung semantic
selection/one-way lookup provenance/refusal marker/prefix cleanup을 구현했고, 세 번의
current-agent 실행이 같은 canonical row와 answer를 유지했다. 2026-08-26 full gate도
Samsung을 clean하게 재현했지만 NAVER operand artifact payload가 비어 integrity
error와 복구 재계획을 만들었고, LGE final-answer surface sync가 fresh
`derived_value` nested trace를 잘못 덮는 후속 결함을 드러냈다. LGE의 명시적
derived-value 역동기화와 NAVER provisional operand artifact 문제는 각각 focused
successor에서 차단됐다. 이어 exact-artifact 정성 진단은 broad retrieval context가
final claim-scoped runtime evidence보다 먼저 보이는 evaluator ordering과 중앙 late
numeric refresh가 이미 근거화된 source-visible query term을 덮는 공통 surface
문제로 분류됐다. Context 우선순위, explicit-role difference rendering, late refresh
term preservation을 일반 계약으로 고친 뒤 focused LGE replay C와 최종 monitored
4-company/5-question gate가 clean하게 통과했다. 이어 pre-commit review에서
source-row ambiguity, direct-operand plan coverage, evaluator override 권한을 세 군데
더 fail-closed로 보강했고 full unittest 2,165/2,165로 검증했다. 리팩터링은 계속
중단 상태다. 2026-08-27 exact-current-head canary가 드러낸 LGE correctness
blocker는 `d87e030`과 아래 세 행 successor에서 닫혔다. NAVER는 correct result와
integrity를 유지하면서도 1회 reflection/replan을 사용하므로 efficiency debt는
남지만 integration correctness blocker는 아니다. 최신 5-question store-fixed gate도
runtime correctness와 provenance를 유지했지만 `HYU_T2_010`의 attribution-only LLM
completeness 변동으로 formal full-eval fail 1을 기록했다. Integration review는 이
결과를 runtime regression이 아닌 정성 evaluator residual로 분류하고 진행하는 쪽을
선택했다. Review에서 runtime/CI blocker는 새로 발견되지 않았지만 `d87e030`의 실제
semantic source-scope 동작과 normative runtime contract가 어긋나고 PR #86 본문이
이전 HOLD 결과를 유지한 documentation blocker가 확인됐다. 이 successor는 runtime을
바꾸지 않고 계약을 동기화했다. PR 본문은 현재 gate와 history-preserving merge
요건을 반영했고 exact-head GitHub Actions `33014459130`도 reviewer contracts와 full
unittest 2,172/2,172를 통과했다. 사용자는 이 근거를 확인한 뒤 PR #86 merge를
명시적으로 승인했다. 허용된 다음 동작은 merge commit 방식으로 통합한 뒤 그
commit이 기존 `main`과 승인된 PR head를 부모로 보존하는지, 그리고 `main` push CI가
green인지 확인하는 것뿐이다. 두 조건이 충족되면 release integration은 완료로
간주한다. Phase 3 리팩터링은 계속 중단 상태다.
상세 범위는 [Next Work](docs/overview/project_status.md#next-work)만 따른다.

### 2026-08-26 Samsung semantic-row and one-way provenance checkpoint

- LLM은 동일 표의 유사 행 가운데 의미상 대상 행을 선택하거나 ambiguous를
  반환하고, deterministic code는 선택 행의 기간/단위/source 계약만 검증한다.
- source row가 만든 canonical lookup slot은 final answer prose에서 다시 읽어
  덮어쓰지 않는다. coarse flattened lookup은 다중 row/value 표를 추측하지 않는다.
- retrieval zero-cost metadata prefix는 LLM context와 final evidence quote에서
  제거하되 실제 문서 heading인 `[Harman]`은 보존한다.
- evaluator missing/refusal marker는 phrase boundary로 판정하므로 `끊임없는`의
  `없`을 refusal로 보지 않는다.
- focused B/C와 후속 full gate의 `SAM_T2_078` answer는 byte-identical했고,
  `numeric_extraction_fingerprint`도
  `de311d9fa0818ca04bacad873ee16ad8dda94633ee3296287722cd64a7067c08`로 같았다.
  세 실행 모두 canonical tuple `28,352,769 / 백만원 / ev_001`과 정확한 source
  row `연구개발비용 총계 | 제55기 | 28,352,769 | 백만원`을 보존했다.
- full gate는 747.5초, 62 LLM calls, 354,014 LLM tokens, 46 query embeddings,
  0 document embeddings, estimated runtime LLM cost `$0.3427218`이었다. persisted
  store를 재사용했으며 fresh DART fetch/parse/ingest는 없었다.
- fresh LGE successor는 final prose가 세 숫자를 나열해도 explicit
  `derived_value` nested result와 primary slot을 `1,486,334백만원`으로 유지했다.
  당시 narrative completeness 0.500은 별도 answer-quality residual이었고, 아래
  final clean-gate checkpoint에서 generic surface contract로 닫혔다.

### 2026-08-26 NAV dependency operand-artifact checkpoint

- dependency가 끝나기 전에 생성된 빈 `operand_set`은 성공한 계산 결과의
  plan-complete input slot과 source provenance가 모두 확인될 때만 같은 artifact
  id/order/cardinality로 확정한다. missing/incomplete/unprovenanced 상태는 기존
  integrity error를 유지한다.
- focused successor는 최초 `coverage=sufficient operands=0`을 재현하고도
  `41.4%`, `current_period/prior_period`, `ev_001`을 보존했다.
- ledger는 `error / 1 issue / 0 operands`에서
  `ok / 0 issues / 2 finalized operands`로 닫혔고 recovery replan은 없었다.
- latency는 `268.740 -> 129.626`초, agent calls/tokens는
  `21 / 126,829 -> 11 / 70,923`; query embeddings 8, document embeddings 0,
  fresh fetch/parse/ingest 0이었다.
- audit 217, focused 381/381, full unittest 2,160/2,160가 통과했다. raw bundle은
  ignored local artifact이며 full gate를 대체하지 않는다.

### 2026-08-26 final clean-gate checkpoint

- evaluator는 final claim-scoped runtime evidence를 broad retrieved context보다
  먼저 배치한다. Numeric equivalence/grounding은 deterministic contract가 맡고,
  정성 설명 평가는 그 결과를 뒤집지 않는다.
- preferred complete numeric answer는 explicit `minuend/subtrahend` slot으로
  component difference를 렌더링한다. 중앙 late numeric refresh도 같은
  evidence-bound `preserve_source_visible_query_terms(...)`를 다시 적용하므로
  이후 단계가 근거화된 `IRA`/`AMPC` 표기를 지우지 않는다.
- focused LGE replay C는 numeric PASS, faithfulness/completeness/calculation
  1.000과 `1,486,334백만원`, `원문 표기: IRA, AMPC.`를 보존했다.
- 최종 monitored store-fixed eval-only gate는 570.031초에 4/4 company와 5/5
  question을 완료했다. pass count 4, full-eval fail count 0, error/integrity
  issue 0, aggregate faithfulness/completeness/context recall/numeric pass rate
  1.000이다.
- `SAM_T2_078`은 `연구개발비용 총계 / 28,352,769 / 백만원 / ev_001`을 유지했다.
  52 LLM calls, 290,893 tokens, query embeddings 46, document embeddings 0,
  estimated runtime LLM cost `$0.2595345`; top result SHA-256은
  `2d786dd729b17b374681ad986250b72bca062093f626ebf9547822c366ad72b3`다.
- 관련 498/498, audit 217, full unittest 2,163/2,163가 통과했다. Output과
  heartbeat는 ignored local artifact이고 fresh ingest evidence가 아니다.
- PR #86은 여전히 draft이고 `main`은 바뀌지 않았다. 다음 일은 review 후
  history-preserving merge 여부를 명시적으로 결정하는 것이다.

### 2026-08-26 post-gate pre-commit hardening checkpoint

- active required operand가 있는 numeric lookup에서 같은 raw value가 서로 다른
  source row에 정확히 나타나면 deterministic recovery는 행 의미를 추측하지 않고
  `ambiguous_direct_lookup_source_evidence`로 중단한다. 후보 범위는 visible
  `retrieved_docs`와 evidence-preserving `seed_retrieved_docs`이며, LLM의 semantic
  선택을 코드의 first/rank/company/question rule로 대체하지 않는다.
- ledger finalization은 slot-derived input뿐 아니라 이미 존재하는 direct
  `calculation_operands`에도 `calculation_plan.ordered_operand_ids` 전체 coverage를
  요구한다. 일부 operand만 material/provenance를 갖는 경우 provisional artifact를
  그대로 두고 integrity failure를 유지한다.
- evaluator의 deterministic `grounded_rendering_correctness`가 실패한 경우 LLM
  numeric-grounding override가 그 결과를 1로 올리거나 grounding 경로를 우회할 수
  없다. qualitative judgement와 deterministic rendering authority를 분리한다.
- runtime-domain audit 217과 full unittest 2,165/2,165가 231.977초에 통과했다.
  이는 최신 source/contract evidence다.
- 이 하드닝 뒤 provider-backed agent benchmark는 다시 실행하지 않았다. 저장된
  clean-gate Samsung answer를 현재 replay/evaluator로 no-call 재평가한 결과
  numeric equivalence/retrieval support/grounded rendering/calculation은 각각
  1.000이었지만 `numeric_grounding=null`이라 final judgement는 `UNCERTAIN`이었다.
  이는 historical-answer compatibility 진단이며 fresh/current-agent pass가 아니다.
- clean gate는 여전히 유효한 직전 provider integration evidence지만 exact current
  source 실행은 아니다. Source/tests는 `6d6ca01`, evidence docs는 `99c4429`에
  기록됐다. 병합은 자동으로 수행하지 않는다.

### 2026-08-26 cross-platform release-validation checkpoint

- 첫 exact-head CI `32963349345`는 reviewer job을 통과했지만 Ubuntu full
  discovery에서 2,165개 중 structural receipt 1개가 실패했다. Runtime failure가
  아니라 `Path.glob()` 반환 순서를 그대로 caller list 계약에 사용한 test-only
  portability 결함이었다.
- `40ae6a7`은 해당 모듈 목록을 명시적으로 정렬했다. 로컬 focused 1/1과
  `tests.test_financial_graph_helpers` 290/290가 통과했다.
- successor CI `32964249893`은 exact code head에서 reviewer 14초와 full unittest
  2,165/2,165를 통과했다. Full discovery 실행은 294.776초, job은 5분 51초였다.
- PR #86은 여전히 draft이고 `main`은 바뀌지 않았다. 다음 일은 clean provider
  gate가 final hardening 직전이라는 한계를 포함해 추가 provider replay 여부와
  history-preserving merge 여부를 명시적으로 결정하는 것이다.

### 2026-08-27 exact-current-head three-row canary checkpoint

- `b422a9b`에서 persisted company store와 같은 policy profile을 재사용해
  `SAM_T2_078`, `NAV_T2_006`, `LGE_T1_051`을 순차 monitored `--eval-only`로
  실행했다. 32 embedding calls는 모두 query embedding이었고 document embedding,
  DART fetch/parse/ingest는 없었다.
- Samsung은 `연구개발비용 총계 / 28,352,769 / 백만원 / ev_001` canonical tuple과
  exact source row를 유지했다. Faithfulness/completeness/refusal/grounded rendering/
  calculation은 모두 `1.000`, integrity는 `ok`였다.
- NAVER는 같은 row의 `2,546.6억원 / 1,801.1억원 = 41.4%`와 두 operand,
  integrity `ok`를 유지했다. 그러나 최초 operand artifact가 부분 상태로 판정돼
  reflection과 semantic replan이 발생했고 30 LLM calls, 177,670 tokens,
  371.691초가 들었다. 정답 pass와 별개로 run-to-run efficiency가 불안정하다.
- LGE는 numeric FAIL했다. Numeric extraction은 올바른 consolidated 값
  `2,163,234백만원`을 final prose에 적었지만 structured `raw_value`를 비워
  반환했다. Runtime은 final prose를 역파싱하지 않았고, generic fallback이 다른
  법인 표의 동명 `영업이익 28,980백만원` 행을 선택했다. Correct row는 이미
  retrieved table metadata에 있었으므로 retrieval miss나 산술 오류가 아니라,
  incomplete semantic output 뒤 entity/table scope를 보장하지 못한 fallback
  acceptance 문제다. 최종 결과 `-647,920백만원`은 선택된 잘못된 피감수에 대한
  산술만 맞다.
- LGE의 extraction prompt fingerprint는 직전 clean run과 같지만 provider가 당시엔
  `raw_value=2,163,234`, 이번에는 빈 값을 반환했다. 따라서 한 번 더 통과시키는
  replay보다 structured contract violation을 명시적으로 처리하는 일반 수정이 먼저다.
- 세 행 합계는 57 LLM calls, 311,132 tokens, 589.281 question-seconds,
  estimated runtime LLM cost `$0.3217084`였다. Raw result/heartbeat는 ignored local
  artifact다. PR #86과 `main`은 변경하지 않았으며 integration은 HOLD다.

### 2026-08-27 semantic source-scope repair successor checkpoint

- `d87e030`은 incomplete numeric structured output을 한 번만 같은 context에서
  semantic retry하고, 여전히 `raw_value`가 없으면 final prose를 역파싱하지 않은 채
  fail closed한다. 동일 raw value의 source 후보는 stable id로 LLM이 의미 선택하고,
  deterministic code가 선택 id와 row/value/unit/source를 검증한다.
- reconciliation은 structured 후보의 material value가 충돌하면 score gap과 무관하게
  semantic rerank를 요청하며 row headers, cells, table context를 판단 payload에
  포함한다. Broad direct fallback은 이미 선택된 structured row를 덮지 않는다.
- `LGE_T1_051`은 `2,163,234백만원 - 6,769억원 = 1,486,334백만원`과
  `IRA, AMPC`를 복구했다. `SAM_T2_078`은 `연구개발비용 총계 / 28,352,769 /
  백만원 / ev_001`, `NAV_T2_006`은 exact raw `2,546,649 / 1,801,079백만원`과
  source-stated display `2조 5,466억원 / 1조 8,011억원`, 계산 `41.4%`를 보존했다.
  세 행 모두 faithfulness/completeness/refusal/grounded rendering/calculation
  `1.000`, integrity `ok`, error `0`이다.
- 저장된 Samsung row의 single-input `unit_consistency_pass=0`은 계산 실패가 아니라
  evaluator definition error였다. 단위 간 일관성을 비교할 두 번째 operand가 없으면
  이제 `None`을 반환하며, replay utility도 production evaluator와 같은 answer-slot
  operand projection을 사용한다. No-call replay는 unit N/A와 calculation `1.000`을
  확인했다.
- NAVER `operand_selection_correctness=0.6667`은 두 실제 입력은 모두 일치하지만
  dataset `expected_operands`가 derived result `41.4%`까지 세 번째 operand로 넣은
  schema 한계다. Runtime input binding을 이 점수에 맞춰 바꾸지 않았다. 한 번의
  reflection/replan은 남았지만 이전 canary 대비 calls `30 -> 20`, tokens
  `177,670 -> 112,062`, latency `371.691 -> 222.486`초로 관측됐다. 단일 실행의
  provider variance이므로 일반 성능 향상 claim은 아니다.
- 세 successor 합계는 40 LLM calls, 200,855 tokens, 30 query embeddings,
  0 document embeddings, 361.107 question-seconds, `$0.2064883`였다. Persisted store를
  재사용한 focused `--eval-only`이며 fresh DART fetch/parse/ingest evidence가 아니다.
- runtime-domain audit 217, 관련 794/794, helper 290/290, dependency projection
  75/75, full unittest 2,172/2,172가 통과했다. Raw bundles/heartbeats는 ignored local
  artifacts다. LGE correctness HOLD는 닫혔지만 PR #86은 draft이고 `main`은 그대로다;
  broader paid gate 또는 integration은 별도 결정이 필요하다.
- GitHub Actions `33007869709`도 `d87e030`에서 reviewer 32/32, audit 217,
  Ubuntu/Python 3.13 full unittest 2,172/2,172를 통과했다. Full discovery는
  211.605초, job은 4분 26초였다.

### 2026-08-27 current-head five-question store-fixed gate checkpoint

- docs/source HEAD `5cdab83`, runtime `d87e030`에서
  `curated_policy_driven_runtime_gate.json`의 `NAV_T2_006`, `HYU_T2_010`,
  `HYU_T3_072`, `LGE_T1_051`, `SAM_T2_078`을 한 번의 monitored `--eval-only`로
  실행했다. Source bundle은 `policy_gate_regression_2026-06-03_1138_actual`, 새
  ignored output은 `integration_policy_gate_semantic_source_scope_successor_2026-08-27`이다.
- 실행 전 profile/store signature와 네 cache의 `completed` 상태를 무호출로
  확인했고, 네 vector index는 strict health probe에서 각각 `result_count=1`로
  통과했다. 이 네 preflight query embedding은 아래 benchmark artifact usage 밖이다.
- 592.607초에 4/4 company, 5/5 question을 완료했다. Screen pass count 4,
  runtime error 0, task/artifact integrity issue 0이며 모든 문항의 faithfulness,
  context recall, grounded rendering, calculation, refusal은 `1.000`이다. LGE는 유일한
  numeric-applicable row로 PASS했고 나머지 mixed/lookup row의 numeric judgement는
  N/A다.
- `NAV_T2_006`은 exact `2,546,649 / 1,801,079백만원 = 41.4%`,
  `LGE_T1_051`은 `2,163,234백만원 - 6,769억원 = 1,486,334백만원`,
  `SAM_T2_078`은 exact `연구개발비용 총계 / 28,352,769 / 백만원 / ev_001`을
  유지했다. `HYU_T3_072`에서는 첫 numeric structured response의 빈 `raw_value`를
  새 bounded retry가 거부하고 다시 받아 Motional의 `50.00% -> 25.81%`,
  `1,294,367백만원`, 손실 두 값을 정상 보존했다.
- Formal winner ranking은 company pass 4지만 `full_eval_fail_count=1`이다.
  `HYU_T2_010` 답은 `87.0만 대 / 78.1만 대 = 11.5%`와 IRA 등 보호무역주의 대응
  필요성을 모두 담고 faithfulness/context recall/calculation/integrity가 clean이다.
  LLM completeness만 답 안에 “사업보고서에서”라는 출처 귀속 문구가 없다는 이유로
  `0.700`을 줘 Hyundai company completeness가 `0.850`이 됐다. 직전 의미상 같은
  답은 `1.000`이었으므로 runtime correctness regression이나 새 answer rule의 근거로
  쓰지 않는다.
- Artifact usage는 59 LLM calls, 324,521 tokens, 45 query embeddings,
  0 document embeddings, 498.909 question-seconds, estimated runtime LLM cost
  `$0.3059185`다. Top result SHA-256은
  `1d9f7508e758dd85c057dc1be5d7f87cf261495b44833d1a0d9d88a90c5d63c8`이다.
  No-call deterministic replay는 다섯 문항 모두 grounded rendering/calculation
  `1.000`을 확인했지만 mixed-row synthetic numeric verdict는 gate claim으로 쓰지 않는다.
- Fresh DART fetch/parse/ingest와 document embedding은 없었다. Raw result,
  heartbeat, replay summary는 ignored local artifacts이고 stage하지 않는다. PR #86은
  draft, `main`은 그대로이며 이 checkpoint는 코드 변경을 추가하지 않았다.

## 이전 Phase 3 owner-move 기록 (historical)

이 절은 semantic calculation program 전환 전의 owner-move 부채 기록이다.
현재 우선순위와 activation 조건은
[Next Work](docs/overview/project_status.md#next-work)가 단일 기준이다.

1. 일부 진행된 aggregate repair/precedence decision; period/material/source/
   coherence/rank/dedupe, narrative-validation policy, row-focus, growth display/material,
   result support/reuse, prepared material inspection/rendering, growth trace inspection,
   bounded aggregate row/gap/lookup-answer surface, final-answer evidence/provenance/operand
   projection, aggregate calculation/public projection, subtask upsert/rank,
   nested traversal/scoring/selected-result promotion과
   growth-answer numeric completion/sanitization과 deterministic quantitative-
   impact parsing/composition은 state-free owner로 이동했으며
   bounded nested-result replacement와 arithmetic surface sync까지 이동했으며
   broader alignment/rebuild/final sequencing은 graph에 유지
2. 일부 진행된 dependency 및 ratio/absolute seam; ratio presentation/readiness/
   scale, bounded operand preparation, lookup magnitude, same-block unit/table repair,
   direct structured lookup-row/value projection, dependency input
   matching/binding policy, deterministic runtime/ontology planning, semantic-
   planner scope/shape/segment/task validation, narrative-task policy와
   lookup answer-slot/support projection, generic operand-period와 query/task
   period-focus, structured-cell selection/scoring과 candidate selected-cell
   preparation, single-report-scope, candidate report/period-scope, candidate surface-contract/
   segment-binding/scoped surface-affinity·contextual-aggregate preference와 period/table coherence 및 location/entity
   subject score와 deterministic positional preference bonus 및 source-priority
   score, column-candidate label,
   delta-like row-label classification, candidate metadata-policy,
   segment-local/segment-metric과
   aggregate-like row stage/role와 candidate value-role/stage 및 operand-
   context/structured-sibling, lookup-hint
   projection/match, direct candidate
   logical/family signature, sibling-surface hit-count, candidate direct-match
   strength·direct candidate semantic priority·canonical-statement winner·ratio-
   component acceptance·direct-grounding/direct-acceptance classification과
   query-to-metric/operand match ownership과 complete operand-candidate scoring은 이동했고
   graph-state lookup, reconciliation candidate construction/ranking과 broader evidence orchestration과
   주변 sequencing은 제외
3. bounded read-only reconciliation refs와 성공·plan-complete·provenance-bearing
   input slot에서 attached provisional operand artifact를 제자리 확정하는 범위까지
   진행된 broader task/artifact ledger synchronization; missing-artifact 생성과
   whole-ledger sync는 제외
4. public contract 이동과 함께 일부 진행된 private API/test mesh

이 목록은 총 작업량이나 정해진 slice 수를 의미하지 않는다. 완료된 owner 이동은
behavior·accuracy·performance 개선이나 Phase 3 완료를 뜻하지 않는다.
`d1305f8`의 7/15줄 segment-local/segment-metric pair와 `80a37f8`의 10/2줄
aggregate-like row stage/role pair, `2eec794`의 5/14/7/5줄 lookup-hint group에
이어 `8cdcc94`가 정확한 26/22줄 direct logical/family candidate-signature
pair를 `financial_operand_resolution.py`의 public API로 이동했고, `a530033`은
정확한 30줄 sibling-surface hit-count projection을
`financial_row_surfaces.py`의 public API로 이동했다. `8e4dca4`는 정확한
6/14줄 query-to-metric/operand match pair를
`financial_retrieval_hints.py`의 public API로 이동했다. `55bc286`은 정확한
11/25줄 query/task period-focus pair를 `financial_scope_policies.py`의 public
API로 이동했다. `9092f5e`는 정확한 16/18줄 candidate value-role/stage pair를
같은 row-surface owner의 public API로 이동했고, `78e3508`은 정확한 15/19줄
candidate operand-context/table-row structured-sibling pair를 같은 owner로
이동했다. `0bfa1f0`은 정확한 21줄 candidate selected-cell projection을
`financial_structured_cells.py`의 public API로 이동했다. Direct/ratio
acceptance, broader matching/scoring은 graph에 남는다. `2b0e9c1`은 정확한
56줄 scoped surface-affinity projection을 `financial_surface_contracts.py`의
public API로 이동했고, `7ec0cc3`은 정확한 30줄 candidate period/table
coherence projection을 `financial_scope_policies.py`의 public API로 이동했다.
`23f08b2`는 정확한 53줄 candidate location/entity subject score projection을
`financial_operand_resolution.py`의 public API로 이동했다. `e04a7bf`는 정확한
7줄 delta-like row-label 분류기를 `financial_row_surfaces.py`의 public API로
이동했고, `c4558b7`은 정확한 7줄 preference bonus를
`financial_operand_resolution.py`의 public API로 이동했다. `0dc278e`는
정확한 10줄 column-candidate label projection을
`financial_row_surfaces.py`의 public API로 이동했다. 이 이동에서 audit이
기존 year-regex record의 경로 변경을 감지해 같은 literal의 reviewed
baseline 경로·fingerprint·line만 교정했고 전체 218개는 불변이다.
`4c8c89c`는 두 inline candidate concept-conflict marker를 retrieval policy의
단일 declarative constant로 분류하고 정확한 27줄 predicate를
`financial_surface_contracts.py`의 public API로 이동했다. 세 caller의
gate/return/stop, contract negative/positive/text precedence와
48-module/203-edge DAG는 그대로다. Inline marker 한 grouped record가 runtime
scan에서 사라져 reviewed baseline은 218에서 217로 줄었고 audit와 exact-count
contract를 함께 갱신했다. `c837e31`은 이어서 정확한 17줄 contextual-
aggregate preference predicate를 같은 surface owner의 public API로 옮겼다.
Binding-policy role/stage/positive-contract precedence와 세 caller branch는
그대로이며 focused 4/4, owner 122/122, affected 1,082/1,082, import 19/19,
audit 217, full 1,975/1,975가 통과했다. 새 characterize-only inventory는
정확한 9줄 balance-sheet aggregate operand predicate만 같은 surface owner로
옮기는 후속을 선택했다. `f35be1a`는 그 predicate를 body 변경 없이 public
`is_balance_sheet_aggregate_operand(...)`로 옮겼고 focused 4/4, owner 126/126,
affected 1,086/1,086, import 19/19, audit 217, full 1,979/1,979가 통과했다.
`cefde44`는 이어서 정확한 13줄 CAPEX-total operand predicate를 public
`is_capex_total_operand(...)`로 옮기고 inline ontology key를 retrieval policy의
`CAPEX_TOTAL_CONCEPT_KEY`로 명명했다. 네 caller branch는 graph에 유지됐으며
focused 4/4, owner 130/130, affected 1,090/1,090, import 19/19, audit 217,
full 1,983/1,983이 통과했다. `1119ac3`은 이어서 정확한 23줄 note-aggregate
lookup-preference predicate를 public
`operand_prefers_note_aggregate_lookup(...)`로 옮겼다. 한 caller의 scoring
branch는 graph에 유지됐으며 focused 4/4, owner 134/134, affected
1,094/1,094, import 19/19, audit 217, full 1,987/1,987이 통과했다. `334fff0`은
이어 정확한 76줄 candidate source-priority scorer를 public
`candidate_source_priority_bonus(...)`로 옮겼다. 전체 candidate scorer와
후속 period/table/report score는 graph에 유지됐으며 focused 4/4, owner
138/138, affected 1,098/1,098, import 19/19, audit 217, full 1,991/1,991이
통과했다. `1a24bc1`은 이어 정확한 83줄 candidate-to-operand matcher를 public
`candidate_matches_operand(...)`로 옮겼다. 사전 문서가 graph caller 하나만
기록했던 누락을 live source inventory로 바로잡아 graph reconciliation 두 경로와
ops 진단 한 경로, 총 세 direct caller를 모두 새 owner로 갱신했다. Focused 4/4,
owner 142/142, affected 1,102/1,102, reconciliation plan 51/51, import 19/19,
audit 217, full 1,995/1,995가 통과했다. `91ceae7`은 이어 정확한 122줄
candidate direct-match-strength scorer를 public
`candidate_direct_match_strength(...)`로 옮겼다. 여섯 graph caller의 여덟
threshold/addition/tuple 위치는 유지됐고 focused 4/4, owner 146/146,
affected 1,106/1,106, reconciliation plan 51/51, import 19/19, audit 217,
full 1,999/1,999가 통과했다. `1be4cad`는 이어 정확한 53줄 direct-candidate
semantic-priority projection을 public `direct_candidate_semantic_priority(...)`로
옮겼다. 세 graph call의 sort/recompute/compare와 collapse/adoption은 유지됐고
focused 4/4, graph owner 150/150, operand owner 69/69, affected 1,110/1,110,
reconciliation plan 51/51, import 19/19, audit 217, full 2,003/2,003이 통과했다.
`73a049c`는 이어 정확한 42줄 canonical-statement-winner predicate를 public
`candidate_is_canonical_statement_winner(...)`로 옮겼다. 한 graph call의
candidate/operand/year 전달과 `canonical_winner` 저장·후속 collapse/rank
adoption은 유지됐고 focused 4/4, graph owner 154/154, operand owner 69/69,
affected 1,114/1,114, reconciliation plan 51/51, import 19/19, audit 217, full
2,007/2,007이 통과했다. `20feddc`는 이어 정확한 68줄 ratio-component-
acceptance predicate를 public
`candidate_satisfies_ratio_component_acceptance_contract(...)`로 옮겼다. 세
reconciliation call의 first-hit/combined-condition/fallback-assignment와 이후
cell fallback/adoption은 유지됐고 focused 4/4, graph owner 158/158, operand
owner 69/69, affected 1,118/1,118, reconciliation plan 51/51, import 19/19,
audit 217, full 2,011/2,011이 통과했다. `4c422ed`는 이어 정확한 86줄
direct-grounding predicate를 public
`candidate_is_direct_grounding_candidate(...)`로 옮겼다. Graph와
reconciliation의 세 call에서 direct-acceptance first rejection, ordered
non-lookup filtering/unique-ambiguous fallback, first-hit/ratio-cell fallback과
candidate/cell adoption은 유지됐고 focused 4/4, graph owner 162/162, operand
owner 69/69, affected 1,122/1,122, reconciliation plan 51/51, import 19/19,
audit 217, full 2,015/2,015가 통과했다. `6ebcf59`는 이어 정확한 161줄
direct-acceptance predicate를 public
`candidate_satisfies_direct_acceptance_contract(...)`로 옮겼다. 다섯 call의
direct-then-ratio laziness, rejection stop, pair score/append, fallback과
candidate/cell adoption은 유지됐고 focused 4/4, graph owner 166/166, operand
owner 69/69, affected 1,126/1,126, reconciliation plan 51/51, import 19/19,
audit 217, full 2,019/2,019가 통과했다. `3d6986e`는 이어 정확한 315줄
operand-candidate scorer를 public `score_operand_candidate(...)`로 옮겼다.
일곱 production call의 입력, ranking/adoption/stop은 caller에 유지됐고 인접한
report-file/local-unit I/O helper는 이동하지 않았다. Focused 4/4, graph owner
170/170, operand owner 69/69, affected 1,130/1,130, reconciliation plan 51/51,
import 19/19, audit 217, full 2,023/2,023과 pycompile/body/caller/DAG parity가
통과했다. `cce5700`은 이어 이미 올바른 surface owner에 있던 정확한 3줄
`_operand_segment_label(...)`을 public `operand_segment_label(...)`로 이름
수렴시켰다. 13개 source call의 인자·laziness·fallback·stop은 유지됐고
focused 4/4, graph owner 174/174, surface owner 1/1, operand owner 69/69,
affected 1,134/1,134, reconciliation plan 51/51, import 19/19, audit 217,
full 2,027/2,027과 exact rename/body/caller/DAG parity가 통과했다. `ae964b3`은
이어 같은 owner의 정확한 4줄 `_operand_needles(...)`을 public
`operand_needles(...)`로 이름 수렴시켰다. 24개 source call과 9개 외부 import의
평가 순서·인자·adoption·stop은 유지했고, public 이름과 충돌한 한 local
collection만 `normalized_operand_needles`로 명확히 바꿔 shadow를 제거했다.
Focused 4/4, graph owner 178/178, surface owner 1/1, operand owner 69/69,
affected 1,138/1,138, additional caller 17/17, reconciliation plan 51/51,
import 19/19, audit 217, full 2,031/2,031과 transform/body/identity/caller/DAG
parity가 통과했다. `83cf700`은 이어 같은 owner의 정확한 3줄
`_text_has_negative_surface(...)`을 public `text_has_negative_surface(...)`로
이름 수렴시켰다. 외부 8/local 2 call의 인자·short-circuit·stop과 두
import-only binding은 유지됐고 focused 4/4, graph owner 182/182, surface owner
1/1, operand owner 69/69, affected 1,142/1,142, additional retrieval-pipeline
1/1, reconciliation plan 51/51, import 19/19, audit 217, full 2,035/2,035와
transform/body/identity/caller/DAG parity가 통과했다. `a0c9a84`은 이어 대칭인
정확한 3줄 `_text_has_positive_surface(...)`을 public
`text_has_positive_surface(...)`로 이름 수렴시켰다. 외부 25/local 1 call과
6개 live 외부 binding의 평가 순서·인자·short-circuit·stop은 유지됐고
focused 4/4, graph owner 186/186, surface owner 1/1, operand owner 69/69,
affected 1,146/1,146, additional retrieval-pipeline 1/1, reconciliation plan
51/51, import 19/19, audit 217, full 2,039/2,039와 transform/body/identity/
caller/DAG parity가 통과했다. `faf75a0`은 이어 같은 owner의 정확한 13줄
`_text_has_contract_term(...)`을 public `text_has_contract_term(...)`로 이름
수렴시켰다. 외부 1/local 3 call의 normalization·compact matching·short-
circuit·stop은 유지됐고 focused 4/4, graph owner 190/190, surface owner 1/1,
operand owner 69/69, affected 1,150/1,150, additional retrieval-pipeline 1/1,
reconciliation plan 51/51, import 19/19, audit 217, full 2,043/2,043와
transform/body/identity/caller/DAG parity가 통과했다. 다음 characterize-only
inventory로 선택했던 정확한 22줄 `_operand_surface_contract(...)`은
`5b71fd6`에서 public `operand_surface_contract(...)`로 이름 수렴했다. 외부
2/local 5 call과 live 1/import-only 1 외부 binding의 explicit-contract/
legacy-policy/needle-fallback 순서·복사·adoption·stop은 유지됐고 focused
4/4, graph owner 194/194, surface owner 1/1, operand owner 69/69, affected
1,154/1,154, additional retrieval-pipeline 1/1, reconciliation plan 51/51,
import 19/19, audit 217, full 2,047/2,047 및 transform/body/identity/caller/DAG
parity가 통과했다. Surface owner의 유일한 remaining private segment-surface
assembler는 owner-local이라 private로 유지한다. 이어 정확한 2줄
`_generic_column_headers()`은 `ea830ed`에서 public
`generic_column_headers()`로 이름 수렴했다. Row-local 1/external 1 call의
policy projection 순서·laziness·identity·stop은 유지됐고 focused 4/4, graph
owner 198/198, surface owner 1/1, operand owner 69/69, affected 1,158/1,158,
additional retrieval-pipeline 1/1, reconciliation plan 51/51, import 19/19,
audit 217, full 2,051/2,051 및 transform/body/identity/caller/DAG parity가
통과했다. 이어 정확한 9줄 `_extract_table_row_label(...)`은 `786a356`에서
public `extract_table_row_label(...)`로 이름 수렴했다. External 3/local 0
call의 raw normalization·delimiter split/fallthrough·identity·stop은 유지됐고
focused 4/4, graph owner 202/202, surface owner 1/1, operand owner 69/69,
affected 1,162/1,162, additional retrieval-pipeline 1/1, reconciliation plan
51/51, import 19/19, audit 217, full 2,055/2,055 및 transform/body/identity/
caller/DAG parity가 통과했다. 이어 정확한 9줄
`_strip_financial_label_annotations(...)`은 `472906e`에서 public
`strip_financial_label_annotations(...)`로 이름 수렴했다. Row-local 2/
graph-helper 1/operand-resolution 2 call의 truth/normalization/annotation-
regex/whitespace-strip, exact identity, adoption/stop은 유지됐고 focused 4/4,
graph owner 206/206, surface owner 1/1, operand owner 69/69, affected
1,166/1,166, additional retrieval-pipeline 1/1, reconciliation plan 51/51,
import 19/19, audit 217, full 2,059/2,059 및 transform/body/identity/caller/DAG
parity가 통과했다. 이어 정확한 14줄
`_strip_leading_period_qualifiers(...)`은 `98aee5a`에서 public
`strip_leading_period_qualifiers(...)`로 이름 수렴했다. Row-local 3/
aggregate-projection 1 call의 truth/normalization/compile/sub-strip-equality
loop, exact adopted identity와 caller adoption/stop은 유지됐고 focused 4/4,
graph owner 210/210, surface owner 1/1, operand owner 69/69, affected
1,170/1,170, additional retrieval-pipeline 1/1, reconciliation plan 51/51,
import 19/19, audit 217, full 2,063/2,063 및 transform/body/identity/caller/DAG
parity가 통과했다. 이어 정확한 11줄 `_surface_match_variants(...)`은
`05415ed`에서 public `surface_match_variants(...)`로 이름 수렴했다. Row-local
2/graph-calculation 2/operand-resolution 5 call의 raw truth/normalization,
eager helper order, ordered dedupe, first-representative identity와 caller
adoption/stop은 유지됐고 focused 4/4, graph owner 214/214, surface owner 1/1,
operand owner 69/69, affected 1,174/1,174, additional retrieval-pipeline 1/1,
reconciliation plan 51/51, import 19/19, audit 217, full 2,067/2,067 및
transform/body/identity/caller/DAG parity가 통과했다. 이어 정확한 16줄
`_operand_text_match(...)`은 `6f28f8b`에서 public
`operand_text_match(...)`로 이름 수렴했다. 10개 모듈의 62 call과 9개 외부
binding은 public API를 사용하며 variant/needle 반복, per-haystack fresh
needle lookup, exact/substring/compact short-circuit, exact bool result와 caller
adoption/stop은 유지됐다. Focused 4/4, graph owner 218/218, surface owner 1/1,
operand owner 69/69, affected 1,178/1,178, additional retrieval-pipeline 1/1,
reconciliation plan 51/51, import 19/19, audit 217, full 2,071/2,071 및
transform 16/16/body/identity/36-caller/DAG parity가 통과했다. Characterize
checkpoint가 빠뜨린 5개 non-graph test module의 live ref 30개도 함께 public
binding으로 갱신됐다. 이어 정확한 16줄
`_extract_numeric_value_after_operand_text(...)`은 `7739ab0`에서 public
`extract_numeric_value_after_operand_text(...)`로 이름 수렴했다. Graph
calculation/evidence와 operand resolution의 5개 call 및 3개 외부 binding은
public API를 사용한다. Normalization, needle compact, character-wise escaped
pattern, search, candidate distance sort, first result identity와 3개 caller의
adoption/stop은 유지됐다. Focused 4/4, graph owner 222/222, surface owner 1/1,
operand owner 69/69, affected 1,182/1,182, additional retrieval-pipeline 1/1,
reconciliation plan 51/51, import 19/19, audit 217, full 2,075/2,075 및
transform 8/8/body/identity/caller/DAG parity가 통과했다. 이어 정확한 24줄
`_format_structured_candidate_row_text(...)`은 `72eb1b8`에서 public
`format_structured_candidate_row_text(...)`로 이름 수렴했다. Graph helpers의
2개 call과 1개 external binding은 public API를 사용하며 label/header dedupe,
repeated header normalization, cell-part construction/join, caller assignment/
adoption/stop은 유지됐다. Focused 4/4, graph owner 226/226, surface owner 1/1,
operand owner 69/69, affected 1,186/1,186, additional retrieval-pipeline 1/1,
reconciliation plan 51/51, import 19/19, audit 217, full 2,079/2,079 및
transform 3/3/body/identity/caller/DAG parity가 통과했다. 이어 정확한 47줄
`_parse_unstructured_table_row_cells(...)`은 `ac90a62`에서 public
`parse_unstructured_table_row_cells(...)`로 이름 수렴했다. 5개 importer의
7개 call과 6개 caller 정의는 public API를 사용하며 row/header/period
fallback, numeric/labeled-value parsing, caller gate/adoption/stop은 유지됐다.
Focused 4/4, graph owner 230/230, surface owner 1/1, operand owner 69/69,
affected 1,190/1,190, additional retrieval-pipeline 1/1, reconciliation plan
51/51, import 19/19, audit 217, full 2,083/2,083 및 transform/body/identity/
caller/DAG parity가 통과했다. 이어 정확한 35줄
`_structured_cell_period_text(...)`은 `89227aa`에서 public
`structured_cell_period_text(...)`로 이름 수렴했다. 4개 importer의 4개
call은 public API를 사용하며 policy-marker/query-year/report-year/fiscal-
rank fallback과 caller gate/adoption/stop은 유지됐다. Focused 4/4, graph
owner 234/234, surface owner 1/1, operand owner 69/69, affected 1,194/1,194,
additional retrieval-pipeline 1/1, reconciliation plan 51/51, import 19/19,
audit 217, full 2,087/2,087 및 transform/body/identity/caller/DAG parity가
통과했다. 이어 operation-policy owner의 정확한 3줄
`_is_ratio_percent_query(...)`은 `f010b6f`에서 public
`is_ratio_percent_query(...)`로 이름 수렴했다. 4개 importer의 7개 call은
public API를 사용하며 normalization/policy-marker iteration/short-circuit와
6개 depth-zero caller 및 calculation depth-one caller의 gate/adoption/
exception scope는 유지됐다. Focused 4/4, graph owner 238/238, surface owner
1/1, operand owner 69/69, affected 1,198/1,198, reflection capability 24/24,
retrieval-pipeline 1/1, reconciliation plan 51/51, import 19/19, audit 217, full
2,091/2,091 및 transform/body/identity/caller/DAG parity가 통과했다. 이어
같은 owner의 정확한 6줄 `_query_requests_narrative_context(...)`은
`1883395`에서 public `query_requests_narrative_context(...)`로 이름
수렴했다. 5개 importer의 18개 call은 public API를 사용하며 input truth/
string/normalization/lowercase, blank early return, policy-hint tuple
construction/membership short-circuit와 18개 depth-zero caller의 gate/
adoption/stop은 유지됐다. Focused 4/4, graph owner 242/242, surface owner 1/1,
operand owner 69/69, affected 1,202/1,202, answer projection 23/23, retrieval
hints 5/5, text surface 30/30, reflection capability 24/24, retrieval-pipeline
1/1, reconciliation plan 51/51, import 19/19, audit 217, full 2,095/2,095 및
transform/body/identity/caller/DAG parity가 통과했다. 이어 같은 owner의 정확한
8줄 `_label_implies_percent_metric(...)`은 `1c8400f`에서 public
`label_implies_percent_metric(...)`로 이름 수렴했다. 4개 importer의 5개
call은 public API를 사용하며 input truth/string/normalization, blank early
return, configured marker와 `%`/`%p` tuple construction, membership short-
circuit, unit-family/operand-conflict/reconciliation/candidate-surface caller
gate와 adoption/stop은 유지됐다. Focused 4/4, graph owner 246/246, surface
owner 1/1, operand owner 69/69, affected 1,206/1,206, reflection promotion
15/15, reflection capability 24/24, retrieval-pipeline 1/1, reconciliation plan
51/51, import 19/19, audit 217, full 2,099/2,099 및 transform/body/identity/
caller/DAG parity가 통과했다. 이어 같은 owner의 정확한 11줄
`_is_single_metric_period_comparison(...)`은 `f0fae1f`에서 public
`is_single_metric_period_comparison(...)`로 이름 수렴했다. 소스의 4개 call은
public API를 사용하고 query normalization, policy snapshot/marker short-
circuit, truthy-label filtering, stable hash/equality dedupe와 도달 가능한
3개 caller의 gate/adoption/stop은 유지됐다. 네 CURRENT-SOURCE 계약은 concept-
operand caller의 네 번째 call이 `len(ordered_specs) == 1`과 truthy
`raw_explicit_roles`의 모순 때문에 런타임 도달 불가임도 고정했다. Focused
4/4, graph owner 250/250, surface owner 1/1, operand owner 69/69, affected
1,210/1,210, reflection promotion 15/15, reflection capability 24/24,
retrieval-pipeline 1/1, reconciliation plan 51/51, import 19/19, audit 217, full
2,103/2,103 및 transform/body/identity/caller/DAG parity가 통과했다. 이어
`ca2969b`가 `_build_concept_required_operands(...)`의 도달 불가능 9줄 분기를
replacement 없이 삭제했다. Spec ordering, raw-role recomputation, earlier
difference/growth return과 downstream operand construction은 유지됐고 helper
call/caller는 4/4에서 도달 가능한 3/3으로 줄었다. Focused 4/4, graph owner
254/254, surface owner 1/1, operand owner 69/69, affected 1,214/1,214,
reflection promotion 15/15, reflection capability 24/24, retrieval-pipeline
1/1, reconciliation plan 51/51, import 19/19, audit 217, full 2,107/2,107 및
exact-deletion/owner/caller/DAG parity가 통과했다. 이어 operation-policy
owner의 정확한 12줄 `_is_percent_point_difference_query(...)`은 `1d8eb67`에서
public `is_percent_point_difference_query(...)`로 이름 수렴했다. 5개
importer의 7개 외부 call과 1개 owner-local call은 public API를 사용하며
normalization, policy snapshot, direct-marker precedence, ratio/comparison
gating, lazy membership, immutability와 caller adoption/stop은 유지됐다.
Focused pre/post 4/4, graph owner 258/258, surface owner 1/1, operand owner
69/69, affected 1,218/1,218, reflection promotion 15/15, reflection capability
24/24, retrieval-pipeline 1/1, reconciliation plan 51/51, import 19/19, audit
217, full 2,111/2,111 및 transform/body/identity/caller/DAG parity가 통과했다.
이어 같은 owner의 정확한 21줄 `_should_coerce_percent_point_unit(...)`은
`a893cb3`에서 public `should_coerce_percent_point_unit(...)`로 이름 수렴했다.
두 importer/call과 기존 test binding 18개가 public API를 사용하며 percent-
point/mode/ordered-ID/operand-map/unit gate, operation/formula result와 두
caller의 adoption/fallback/exception scope는 유지됐다. Focused pre/post 4/4,
graph owner 262/262, calculation-execution 45/45, math 24/24, surface 1/1,
operand 69/69, affected 1,222/1,222, reflection promotion 15/15, reflection
capability 24/24, retrieval-pipeline 1/1, reconciliation plan 51/51, import
19/19, audit 217, full 2,115/2,115 및 transform/body/identity/caller/DAG parity가
통과했다. 이어 같은 owner의 정확한 40줄
`_requires_direct_numeric_grounding(...)`은 `7de65fc`에서 public
`requires_direct_numeric_grounding(...)`로 이름 수렴했다. 세 importer/call과
기존 test binding 19개가 public API를 사용하며 shallow task snapshot,
operation precedence, required-row filter/copy ordering, ratio/sum과
difference/growth 결과, fallback classifier adoption 및 세 caller의 gate/
argument/adoption/exception scope는 유지됐다. Focused pre/post 4/4, graph owner
266/266, operation contracts 242/242, retrieval hints 5/5, task artifacts 15/15,
surface 1/1, operand 69/69, affected 1,226/1,226, reflection promotion 15/15,
reflection capability 24/24, retrieval-pipeline 1/1, reconciliation plan 51/51,
import 19/19, audit 217, full 2,119/2,119 및 transform/body/identity/caller/DAG
parity가 통과했다. 이어 scope-policy owner의 정확한 15줄
`_desired_consolidation_scope(...)`은 `d6e7765`에서 public
`desired_consolidation_scope(...)`로 이름 수렴했다. 다섯 importer의 열두
call과 기존 test binding 26개가 public API를 사용하며 query/metadata/default
precedence, copy/eager-lazy evaluation, exact 결과 및 caller gate/adoption은
유지됐다. 계산 caller의 충돌 지역 store 1개/load 8개만
`requested_consolidation_scope`로 바뀌고 keyword 이름 2개는 유지됐다.
Focused pre/post 4/4, graph owner 270/270, affected 1,230/1,230, audit 217,
full 2,123/2,123 및 transform/body/identity/eleven-caller/DAG parity가
통과했다. 이어 같은 owner의 정확한 11줄
`_metadata_period_match_strength(...)`은 `5509d78`에서 public
`metadata_period_match_strength(...)`로 이름 수렴했다. 세 importer/call과
기존 test binding 19개가 public API를 사용하며 input short-circuit,
repeated label conversion, set dedupe/intersection, exact overlap ratio 및 세
caller의 score adoption/exception scope는 유지됐다. Focused pre/post 4/4,
graph owner 274/274, affected 1,234/1,234, audit 217, full 2,127/2,127 및
transform/body/identity/three-caller/DAG parity가 통과했다. 이어 같은
owner의 정확한 10줄 `_extract_period_sort_key(...)`은 `d9dddc4`에서
public `extract_period_sort_key(...)`로 이름 수렴했다. 실제 importer/call은
public API를 사용하고 `financial_graph_calculation.py`의 load/call 0인 private
import 1줄은 삭제됐다. First-year/당기/전기/default precedence와 calculation-
execution의 time-series gate, stable sort, evidence/growth adoption 및 outer
exception scope는 유지됐다. Focused pre/post 4/4, retrieval scope 28/28,
graph owner 278/278, affected 1,238/1,238, audit 217, full 2,131/2,131 및
transform/body/identity/sole-caller/DAG parity가 통과했다. 이어 같은 owner의
정확한 10줄 `_should_apply_strict_company_scope(...)`은 `579141d`에서 public
`should_apply_strict_company_scope(...)`로 이름 수렴했다. 이어 정확한 7줄
`_report_scope_source_receipts(...)`은 `faba39e`에서 public
`report_scope_source_receipts(...)`로 이름 수렴했다. Fresh-list/source-order/
normalization/equality-dedupe와 single-report/strict-company/retrieval 세 caller의
서로 다른 exception boundary는 유지됐다. Focused pre/post 4/4, retrieval scope
28/28, graph owner 286/286, affected 1,246/1,246, audit 217, full 2,139/2,139 및
transform/body/identity/three-caller/DAG parity가 통과했다. 이어 같은 owner의
정확한 25줄 `_extract_year_tokens(...)`은 `d2a8f8e`에서 public
`extract_year_tokens(...)`로 이름 수렴했다. Query/scope/source-year precedence,
narrow conversion exception과 generic/concept operand 및 dependency-query 세
caller의 결과 채택은 유지됐다. Focused pre/post 4/4, retrieval scope 28/28,
graph owner 290/290, affected 1,250/1,250, audit 217, full 2,143/2,143 및
body/identity/three-caller/48-module/205-edge DAG parity가 통과했다. 이어
`be1fbc9`가 세 importer의 load/call 0인 cross-module private import 4줄을
삭제했다. Helper 정의와 다른 importer의 live call은 보존됐고 DAG는 정확히
48 modules/203 edges로 줄었다. Characterize-only inventory의 19개 tuple 기대뿐
아니라 26개 standalone DAG 기대와 line/fingerprint 파급도 함께 갱신했다.
Focused DAG 19/19, graph 290/290, affected semantic 1,250/1,250, separate owner
144/144, combined caller/import 110/110, audit 217, full 2,143/2,143가 통과했다.
이어 `3eadee4`가 optional MAS node 세 파일에서 import/load/call/dynamic consumer
0인 정확한 2줄 helper 세 개와 top-level separator를 삭제했다. Live orchestrator
trace와 artifact-boundary users는 유지됐다. Targeted MAS 45/45, import 19/19,
audit 217, full 2,143/2,143가 통과했고 recursive DAG는 48/203 그대로다. 이어
`4dd38ca`가 `financial_graph_model_loaders.py`의 cross-module private wrapper
13개를 public contract로 이름 수렴시켰다. `_graph_model(...)`의 lazy cached
lookup과 caller exception boundary는 유지됐다. Characterize-only inventory가
누락한 CURRENT-SOURCE fingerprint 16개까지 갱신해 source `+50/-50`, tests
`+34/-34`, whole `+84/-84`로 마감했고 affected 466/466, import 19/19, audit
217, full 2,143/2,143가 통과했다. 이어 `643bdf6`이
`financial_langchain_loaders.py`의 lazy loader 4개 전체를 public contract로
이름 수렴시켰다. Function-local import, exact factory/identity, document
metadata copy와 caller exception boundary는 유지됐다. Source `+42/-42`, tests
`+29/-29`, whole `+71/-71`이며 affected 676/676, import 19/19, audit 217,
full 2,143/2,143가 통과했다. 이어 `4a4550c`가
`financial_text_surface.py`의 externally imported private text primitive 4개
전체를 public contract로 이름 수렴시켰다. Exact regex, raw truth/string,
normalization, fresh result, caller adoption과 exception boundary는 유지됐다.
Source `+36/-36`, tests `+24/-24`, whole `+60/-60`이며 focused 432/432,
audit 217, unchanged 48/203 DAG, full 2,143/2,143가 통과했다. 이어
`f220c9c`가 `financial_answer_projection.py`의 유일한 externally imported
private selector를 public
`preferred_complete_aggregate_subtask_answer(...)`로 in-place rename했다.
63줄 body, 네 caller, 세 completion path, longest/stable selection과 exception
stop은 유지됐다. Source `+9/-9`, tests `+15/-15`, whole `+24/-24`이며 direct
7/7, public identity 4/4, focused 527/527, audit 217, unchanged 48/203 DAG, full
2,143/2,143가 통과했다. 이어 `6d0e21c`가
`financial_graph_evidence.py`에서 load/call/external consumer가 모두 0인
config import 6개를 삭제했다. 정의와 다른 owner의 live import/call은
유지됐고 source `-6`, tests `+9/-9`, focused 339/339, audit 217, unchanged
48/203 DAG, full 2,143/2,143가 통과했다. 다음 batch는
`7cdb317`에서 `financial_graph_calculation.py`의 zero-load
`query_focus_marker_groups` import 한 줄만 삭제했다. 명시적 compatibility
identity가 있는 인접 `text_has_negative_surface`는 유지됐고 source `-1`,
tests `+7/-7`, focused 339/339, audit 217, pycompile 2/2, unchanged 48/203 DAG,
full 2,143/2,143가 통과했다. 이어 `5de5e23`이
`financial_graph_reconciliation.py`가 사용하지 않던
`effective_structured_cell_unit_hint`, `find_reconciliation_match_entry`,
`pair_candidate_period_score`, `structured_cell_identity` import 네 개만
삭제했다. Owner 정의와 2/2/2/4 live calls는 유지됐고 source `-4`, tests
`+3/-7`, focused 323/323, audit 217, pycompile 3/3, unchanged 48/203 DAG,
full 2,143/2,143가 통과했다. 이어 `5ff7fd2`가
`financial_graph_evidence.py`의 zero-load `operand_needles` import 한 줄만
삭제했다. Canonical owner 정의와 총 24개 source call, 나머지 여덟 external
importer, 같은 tuple의 세 live import는 유지됐고 source `-1`, tests
`+9/-11`, focused 339/339, audit 217, pycompile 2/2, unchanged 48/203 DAG,
full 2,143/2,143가 통과했다. 이어 `eea2935`가
`financial_graph_calculation.py`의 zero-load·zero-guard `TYPE_CHECKING` import
항목만 같은 typing import 줄에서 삭제했다. 나머지 일곱 typing binding과 모든
line fingerprint는 유지됐고 source/whole `+1/-1`, tests 변경 0, focused
339/339, audit 217, pycompile 1/1, unchanged 48/203 DAG, full 2,143/2,143가
통과했다. 이어 `f04e774`가 `financial_retrieval_pipeline.py`의 exact 2-line
document wrapper를 같은 위치와 본문으로 public `make_document(...)`로
이름 수렴시키고 evidence import 한 개와 direct call 세 개만 갱신했다. Loader
edge, 세 keyword call, unrelated storage-local helper는 유지됐고 source/whole
`+5/-5`, tests 변경 0, public identity/behavior 4/4, focused 339/339, audit
217, pycompile 2/2, unchanged 48/203 DAG, full 2,143/2,143가 통과했다. 이어
`67bc02e`가 `financial_retrieval_hints.py`의 exact 6-line supplement-section
helper를 같은 위치와 본문으로 public
`supplement_section_terms_for_query(...)`로 이름 수렴시키고 reconciliation
import/call 각 한 개와 기존 CURRENT-SOURCE 기대 다섯 개만 갱신했다.
Fresh-list/intent gate/lazy ontology/ordered dedupe와 caller sequencing은
유지됐고 source/tests/whole `+3/-3`, `+5/-5`, `+8/-8`, identity/behavior
10/10, focused 365/365, audit 217, pycompile 4/4, unchanged 48/203 DAG, full
2,143/2,143가 통과했다. 이어 `31e4c26`이 같은 owner의 exact 9-line
topic-hint helper를 같은 위치와 본문으로 public
`retrieval_hint_from_topic(...)`로 이름 수렴시키고 retrieval-pipeline
import/call 각 한 개와 test binding/fingerprint 아홉 개만 갱신했다.
Narrative-policy/ontology와 `_retrieve` orchestration은 유지됐고 source/tests/
whole `+3/-3`, `+9/-9`, `+12/-12`, identity/behavior 10/10, focused 343/343,
audit 217, pycompile 4/4, unchanged 48/203 DAG, full 2,143/2,143가 통과했다.
이어 `c9a315f`가 `financial_operand_resolution.py`의 exact 17-line
reconciliation-reference canonicalizer를 같은 위치와 본문으로 public
`canonicalize_structured_operand_reconciliation_refs(...)`로 이름 수렴시키고
graph-calculation import/call 각 한 개와 기존 test 기대 42개만 갱신했다.
Sibling canonicalizer/normalizer와 calculation orchestration은 유지됐고
source/tests/whole `+3/-3`, `+42/-42`, `+45/-45`, identity/behavior 10/10,
focused 665/665, audit 217, pycompile 4/4, unchanged 48/203 DAG, full
2,143/2,143가 통과했다. 이어 `dce0d63`이 같은 owner의 exact 19-line
required-role conflict helper를 같은 위치와 본문으로 public
`operand_rows_conflict_by_required_role(...)`로 이름 수렴시키고 dependency-
projection import/call 각 한 개와 기존 test 기대 33개만 갱신했다. Role
normalization/callback order와 precedence orchestration은 유지됐고 source/
tests/whole `+3/-3`, `+33/-33`, `+36/-36`, identity/behavior 10/10, focused
695/695, audit 217, pycompile 4/4, unchanged 48/203 DAG, full 2,143/2,143가
통과했다. 이어 `6aeb0d1`이 같은 owner의 exact six-line display-unit set
helper를 같은 위치와 본문으로 public
`operand_row_display_unit_set(...)`로 이름 수렴시키고 dependency-projection
import 한 개와 연속된 두 call, 기존 test 기대 32개만 갱신했다. Raw-unit-only
cleanup/dedupe와 caller precedence sequencing은 유지됐고 source/tests/whole
`+4/-4`, `+32/-32`, `+36/-36`, identity/behavior 10/10, focused 695/695,
audit 217, pycompile 4/4, unchanged 48/203 DAG, full 2,143/2,143가 통과했다.
이어 `48130ab`이 같은 owner의 exact 11-line reconciliation-ID canonicalizer를
같은 위치와 본문으로 public `canonical_structured_reconciliation_id(...)`로
이름 수렴시키고 owner-local call 두 개, graph-calculation import/call 각 한
개와 기존 direct-name/count 기대 32개만 갱신했다. Prefix/marker/raw-row
semantics와 두 caller sequencing은 유지됐고 source/tests/whole `+5/-5`,
`+32/-32`, `+37/-37`, identity/behavior 10/10, focused 804/804, audit 217,
pycompile 4/4, unchanged 48/203 DAG, full 2,143/2,143가 통과했다. 이어
`c1d3b8c`가 같은 owner의 exact 11-line table-context predicate를 같은 위치와
본문으로 public `operand_rows_have_single_table_context(...)`로 이름 수렴시키고
dependency/graph import 두 개와 call 네 개, 기존 direct-name/count/fingerprint
기대 45개만 갱신했다. Table/source/anchor fallback, repeated normalization,
blank filter, set dedupe와 네 caller sequencing은 유지됐고 source/tests/whole
`+7/-7`, `+45/-45`, `+52/-52`, direct behavior 1/1, identity 2/2,
focused 879/879, audit 217, pycompile 5/5, unchanged 48/203 DAG, full
2,143/2,143가 통과했다. 이어 `0b2b66d`가 exact 13-line period-comparison
collapse predicate를 같은 위치와 본문으로 public
`period_comparison_operand_rows_collapse_to_same_slot(...)`로 이름 수렴시키고
dependency/graph import 두 개와 production call 여섯 개, 기존 direct-name/
count/fingerprint 기대 46개만 갱신했다. Current/prior role grouping, exact
normalization/membership, ordered shallow copy와 shared same-slot predicate는
유지됐고 source/tests/whole `+9/-9`, `+46/-46`, `+55/-55`, direct behavior
1/1, identity 2/2, focused 879/879 in 265.674 seconds, audit 217, pycompile
5/5, unchanged 48/203 DAG, full 2,143/2,143 in 319.738 seconds가 통과했다.
이어 `5bff185`가 exact 31-line evidence-surface segment-label predicate를
같은 위치와 본문으로 public `evidence_surface_contains_segment_label(...)`로
이름 수렴시키고 owner-local call 한 개, graph import/call 각 한 개와 기존
기대 38개만 갱신했다. Variant/punctuation/space normalization, ordered
dedupe, shallow policy copy와 case-sensitive segment/scope matching은
유지됐고 source/tests/whole `+4/-4`, `+38/-38`, `+42/-42`, direct behavior
1/1, graph identity, focused 879/879 in 276.791 seconds, audit 217, pycompile
4/4, unchanged 48/203 DAG, full 2,143/2,143 in 326.614 seconds가 통과했다.
이어 `03da7b8`이 exact 21-line required-surface operand-row filter를 같은
위치와 본문으로 public
`filter_operand_rows_by_required_surface_contract(...)`로 이름 수렴시키고
graph import 한 개와 call 두 개, 기존 기대 39개만 갱신했다. Early-return
identity, single evidence indexing, ordered row filtering, lazy operand match와
keyword propagation은 유지됐고 source/tests/whole `+4/-4`, `+39/-39`,
`+43/-43`, direct behavior 1/1, graph identity, focused 911/911 in 308.132
seconds, audit 217, pycompile 6/6, unchanged 48/203 DAG, full 2,143/2,143 in
350.243 seconds가 통과했다. 이어 `3198927`이 exact 53-line operand-slot
evidence-surface predicate를 같은 위치와 본문으로 public
`operand_slot_has_evidence_surface_match(...)`로 이름 수렴시키고 graph
import 한 개와 call 여섯 개, 기존 기대 39개만 갱신했다. Matched-line fast
path, evidence metadata/cell surface assembly와 여섯 caller의 guard/adoption
순서는 유지됐고 source/tests/whole `+8/-8`, `+39/-39`, `+47/-47`, direct
behavior 1/1, graph identity, focused 911/911 in 189.724 seconds, audit 217,
pycompile 4/4, unchanged 48/203 DAG, full 2,143/2,143 in 241.129 seconds가
통과했다. 이어 `b5ec9ae`가 exact 13-line ratio same-slot predicate를 같은
위치와 본문으로 public `ratio_operand_rows_collapse_to_same_slot(...)`로
이름 수렴시키고 source import 세 개와 call 열 개, 기존 기대 53개만
갱신했다. Numerator-before-denominator group 구성, 독립적인 `rows or []`
평가, role prefix와 shallow row copy 순서는 유지됐고 source/tests/whole
`+14/-14`, `+53/-53`, `+67/-67`, direct behavior 1/1, public identity 3/3,
focused 1,004/1,004 in 255.994 seconds, audit 217, pycompile 9/9, unchanged
48/203 DAG, full 2,143/2,143 in 259.261 seconds가 통과했다. 이어 `a7c02de`가 exact 8-line evidence-item index를 같은 위치와
본문으로 public `evidence_items_by_id(...)`로 이름 수렴시키고 owner-local
call 네 개, aggregate/graph import 두 개와 external call 열한 개, 기존 기대
57개만 갱신했다. Ordered comprehension, blank-ID filter, retained ID 반복
정규화, key-before-shallow-copy, duplicate last-value overwrite와 caller
순서는 유지됐고 source/tests/whole `+18/-18`, `+56/-56`, `+74/-74`,
direct behavior 1/1, public identity 2/2, focused 1,004/1,004 in 253.742
seconds, audit 217, pycompile 7/7, unchanged 48/203 DAG, full 2,143/2,143 in
292.697 seconds가 통과했다. 이어 `bd29a11`이 exact 10-line missing-required-operands detector를
같은 위치와 본문으로 public `missing_required_operands(...)`로 이름
수렴시키고 owner-local call 두 개, calculation-execution/dependency-
projection/graph import 세 개와 external call 22개, 기존 기대 61개만
갱신했다. Ordered required/row scan, first-match short circuit, covered-row
skip와 missing-row shallow copy는 유지됐고 source/tests/whole `+28/-28`,
`+61/-61`, `+89/-89`, direct behavior 1/1, public identity 3/3, focused
1,084/1,084 in 341.291 seconds, audit 217, pycompile 11/11, unchanged 48/203
DAG, full 2,143/2,143 in 352.063 seconds가 통과했다. 이어 `ecc074c`가 exact
23-line `_evidence_item_for_operand_row(...)`를 public
`evidence_item_for_operand_row(...)`로 이름 수렴시키고 owner-local call 네
개, aggregate/graph/lookup-recovery import 세 개와 external call 22개, 기존
direct-name/count/fingerprint 기대 65개만 갱신했다. Ordered ID cleanup,
exact-before-recon-before-stripped fallback, truthy identity return, falsey
continuation과 caller adoption 순서는 유지됐고 source/tests/whole
`+30/-30`, `+65/-65`, `+95/-95`, direct/structure 7/7, public identity
3/3, focused 1,004/1,004 in 207.349 seconds, audit 217, pycompile 9/9,
unchanged 48/203 DAG, full 2,143/2,143 in 217.647 seconds가 통과했다. 이어
`9ab7e64`가 exact 24-line operand-row requirement matcher를 같은 위치와
본문으로 public `operand_row_matches_requirement(...)`로 이름 수렴시키고
owner-local call 열한 개, calculation-execution/dependency-projection/graph-
evidence/graph-calculation import 네 개와 external call 열한 개, 기존
direct-name/count/fingerprint 기대 67개만 갱신했다. Conflict-first rejection,
role/label/concept precedence, eager row-surface 구성, lazy truthy matching과
20 caller의 guard/adoption 순서는 유지됐고 source/tests/whole
`+27/-27`, `+67/-67`, `+94/-94`, direct/structure 7/7 in 10.148 seconds,
public identity 4/4, focused 1,004/1,004 in 201.883 seconds, audit 217,
pycompile 9/9, unchanged 48/203 DAG, full 2,143/2,143 in 222.306 seconds가
통과했다. 이어 `d8a41af`가 exact 6-line query-budget integer coercion을
같은 위치와 본문으로 public `query_budget_int(...)`로 이름 수렴시키고
retrieval-pipeline import 한 개와 `_retrieve(...)` call 다섯 개, 기존
caller/aggregate fingerprint 기대 네 개만 갱신했다. Raw `value or 0`,
단일 `int`, TypeError/ValueError fallback, outside-try zero clamp와 다섯
budget assignment 순서는 유지됐고 source/tests/whole `+7/-7`, `+4/-4`,
`+11/-11`, direct/identity 5/5, focused 338/338 in 177.154 seconds, audit
217, pycompile 2/2, unchanged 48/203 DAG, full 2,143/2,143 in 220.001
seconds가 통과했다. 이어 `820dbd9`가 exact 7-line matched-ontology concept-
spec helper를 같은 위치와 본문으로 public
`matched_ontology_concept_specs(...)`로 이름 수렴시키고 owner-local call 한
개, graph import/call 각 한 개와 기존 기대 세 개만 갱신했다. Ontology
lookup, comparison-mode concept call, raw falsey fallback, first/second mapping
conversion과 caller loop 순서는 유지됐고 source/tests/whole `+4/-4`,
`+3/-3`, `+7/-7`, direct/identity 6/6, focused 556/556 in 182.895 seconds,
audit 217, pycompile 4/4, unchanged 48/203 DAG, full 2,143/2,143 in 236.016
seconds가 통과했다. 이어 `cf2faf4`가 exact 4-line preferred-calculation-
sections helper를 같은 위치와 본문으로 public
`preferred_calc_sections(...)`로 이름 수렴시키고 owner-local call 한 개,
reconciliation/reflection-projection import 두 개와 external call 네 개,
기존 기대 36개만 갱신했다. Non-comparison/trend fresh-list early return,
ontology lookup과 exact result identity, 다섯 caller의 argument/stop 순서는
유지됐고 source/tests/whole `+8/-8`, `+36/-36`, `+44/-44`, direct/identity
7/7, structure 2/2, focused 655/655 in 241.308 seconds, audit 217, pycompile
7/7, unchanged 48/203 DAG, full 2,143/2,143 in 292.304 seconds가 통과했다.
이어 `b8f78a5`가 exact 6-line display-operand-label helper를 같은 위치와
본문으로 public `display_operand_label(...)`로 이름 수렴시키고 answer-slots/
calculation/rendering import 세 개와 external call 열두 개, 기존 exact test
ref 다섯 개만 갱신했다. 단일 whitespace normalization, 세 regex
substitution의 패턴/순서/previous-result binding과 ten-caller adoption/stop
순서는 유지됐고 source/tests/whole `+16/-16`, `+5/-5`, `+21/-21`, direct/
identity 10/10, focused 626/626 in 235.511 seconds, audit 217, pycompile 6/6,
unchanged 48/203 DAG, full 2,143/2,143 in 279.103 seconds가 통과했다. 이어
`28c3798`이 exact 8-line section-hint-alias helper를 같은 위치와 본문으로
public `section_hint_alias(...)`로 이름 수렴시키고 reflection-projection import
한 개와 external call 세 개, 기존 name/count 기대 아홉 개만 갱신했다.
Falsey early return, hierarchy split-last/strip branch, numbered-prefix regex와
caller evaluation/adoption 순서는 유지됐고 source/tests/whole `+5/-5`,
`+9/-9`, `+14/-14`, direct/identity 12/12, focused 660/660 in 295.478
seconds, audit 217, pycompile 5/5, unchanged 48/203 DAG, full 2,143/2,143 in
340.329 seconds가 통과했다. 이어 `cd8315d`가 exact 9-line sentence-operand-
context matcher를 같은 위치와 본문으로 public
`sentence_matches_operand_context(...)`로 이름 수렴시키고 owner-local call 네
개, graph-evidence import/call 각 한 개와 derived hash 기대 여덟 개만
갱신했다. Eager sentence/compact normalization, ordered surface scan,
normalized-before-compact lazy containment과 다섯 caller의 guard/adoption
순서는 유지됐고 source/tests/whole `+7/-7`, `+8/-8`, `+15/-15`, direct/
identity 12/12, focused 701/701 in 281.277 seconds, audit 217, pycompile 3/3,
unchanged 48/203 DAG, full 2,143/2,143 in 352.324 seconds가 통과했다. 이어
`fe31f2e`가 exact 10-line concept-spec lookup helper를 같은 위치와 본문으로
public `concept_spec_for_key(...)`로 이름 수렴시키고 owner-local call 세 개,
calculation import/call 각 한 개와 owner-count 기대 43개만 갱신했다. Blank-key
early return, eager provider list materialization, group skip, first normalized
concept match와 shallow-copy return 순서는 유지됐고 source/tests/whole
`+6/-6`, `+43/-43`, `+49/-49`, direct/identity 12/12, focused 783/783 in
282.888 seconds, audit 217, pycompile 2/2, unchanged 48/203 DAG, full
2,143/2,143 in 339.369 seconds가 통과했다. 이어 `b530b38`이 exact 16-line
structured-result subtask-row/answer helper를 같은 위치와 본문으로 public
`structured_result_subtask_rows_and_answer(...)`로 이름 수렴시키고 owner-local
call 한 개, agent-run/aggregate/graph import 세 개와 external call 네 개,
기존 exact-name 기대 21개와 owner-count 기대 한 개만 갱신했다. Eager row
materialization, ordered Mapping filter와 shallow copy, formatted-result-before-
rendered-value fallback, normalization과 다섯 caller의 adoption 순서는 유지됐고
source/tests/whole `+9/-9`, `+22/-22`, `+31/-31`, direct/identity 12/12,
focused 839/839 in 223.658 seconds, audit 217, pycompile 4/4, unchanged 48/203
DAG, full 2,143/2,143 in 270.252 seconds가 통과했다. 이어 `2b74563`이 exact
19-line generic metric-alias helper를 같은 위치와 본문으로 public
`build_generic_metric_aliases(...)`로 이름 수렴시키고 owner-local call 세 개,
graph-evidence import/call 각 한 개, exact-name 기대 여덟 개, owner-count 기대
43개와 derived structural-hash 기대 여덟 개만 갱신했다. Blank-label early
return, parenthesis alias 순서, substitution field eager access와 ordered dedupe는
유지됐고 source/tests/whole `+6/-6`, `+59/-59`, `+65/-65`, direct/identity
12/12, focused 645/645 in 199.963 seconds, audit 217, pycompile 2/2, unchanged
48/203 DAG, full 2,143/2,143 in 244.527 seconds가 통과했다. 이어 `7a4f847`이
exact 21-line selected-query dedupe helper를 같은 위치와 본문으로 public
`drop_queries_already_selected(...)`로 이름 수렴시키고 pipeline import 한 개와
external call 두 개, `_retrieve` CURRENT-SOURCE caller hash 두 개와 파생 caller-
map hash 두 개만 갱신했다. Selected-signature eager completion, falsey filter,
kept/dropped identity/order와 exact duplicate trace는 유지됐고 source/tests/whole
`+4/-4`, `+4/-4`, `+8/-8`, direct/identity 12/12, focused 370/370 in 19.499
seconds, audit 217, pycompile 3/3, unchanged 48/203 DAG, full 2,143/2,143 in
286.986 seconds가 통과했다. 이어 `67537a1`이 exact 28-line nested-result-
evidence helper를 같은 위치와 본문으로 public
`collect_nested_result_evidence(...)`로 이름 수렴시키고 graph-calculation
import 한 개와 external call 두 개, owner-count 기대 한 개와 파생 CURRENT-
SOURCE hash 기대 세 개만 갱신했다. Evidence/payload/recursion order, Mapping
filter, shallow-copy identity와 inclusive depth bound는 유지됐고 실제 source/
tests/whole `+4/-4`, `+4/-4`, `+8/-8`, direct/identity 12/12, focused 744/744
in 36.626 seconds, audit 217, pycompile 3/3, unchanged 48/203 DAG, full
2,143/2,143 in 336.370 seconds가 통과했다. 이어 `f77bd87`이 exact 30-line
query-context-term limiter를 같은 위치와 본문으로 public
`limit_query_context_terms(...)`로 이름 수렴시키고 pipeline import 한 개,
external call 두 개와 `_retrieve` 파생 hash 기대 네 개만 갱신했다. Item
normalize/filter, first-occurrence dedupe, nonpositive unlimited, head/head-tail
selection과 trace field/order는 유지됐고 source/tests/whole `+4/-4`, `+4/-4`,
`+8/-8`, direct/identity 12/12, exact structural 2/2, focused 370/370 in 23.165
seconds, audit 217, pycompile 3/3, unchanged 48/203 DAG, full 2,143/2,143 in
686.355 seconds가 통과했다. 이어 `ea3ee9f`가 exact 29-line query-result-cache
store helper를 같은 위치와 본문으로 public `store_query_result_cache(...)`로
이름 수렴시키고 pipeline import 한 개, external call 세 개와 `_retrieve` 파생
hash 기대 네 개만 갱신했다. Empty-key early return, ordered entry construction,
두 번의 docs materialization, explicit cache replacement와 return/stored-entry
identity 경계는 유지됐고 source/tests/whole `+5/-5`, `+4/-4`, `+9/-9`,
direct/identity 12/12, exact structural 2/2, focused 370/370 in 21.811 seconds,
audit 217, pycompile 3/3, unchanged 48/203 DAG, full 2,143/2,143 in 313.768
seconds가 통과했다. 이어 `7321eed`가 exact 34-line executed-query duplicate-
drop helper를 같은 위치와 본문으로 public
`drop_duplicate_executed_query(...)`로 이름 수렴시키고 pipeline import 한 개,
`if ...: continue` call 세 개와 `_retrieve` 파생 hash 기대 네 개만 갱신했다.
Source normalization, falsey-signature no-mutation return, per-source set
adoption, duplicate-only trace mutation과 partial-mutation exception 순서는
유지됐고 source/tests/whole `+5/-5`, `+4/-4`, `+9/-9`, direct/identity 12/12,
exact structural 2/2, focused 370/370 in 19.897 seconds, audit 217, pycompile
3/3, unchanged 48/203 DAG, full 2,143/2,143 in 297.563 seconds가 통과했다.
이어 `01959ca`가 exact 45-line query-result-cache lookup helper를 같은 위치와
본문으로 public `lookup_query_result_cache(...)`로 이름 수렴시키고 pipeline
import 한 개, assignment call 세 개와 `_retrieve` 파생 hash 기대 네 개만
갱신했다. Key-first/falsey early return, exact-hit precedence, insertion-ordered
objective fallback, capacity gate, shallow-copy/fresh-doc-slice identity와 caller
hit/miss 경계는 유지됐고 source/tests/whole `+5/-5`, `+4/-4`, `+9/-9`,
direct/identity 12/12, exact structural 2/2, focused 370/370 in 19.947 seconds,
audit 217, pycompile 3/3, unchanged 48/203 DAG, full 2,143/2,143 in 302.217
seconds가 통과했다. 이어 `877de9e`가 exact 46-line executed-query telemetry
summary helper를 같은 위치와 본문으로 public
`summarize_executed_query_telemetry(...)`로 이름 수렴시키고 pipeline import/
call 한 쌍, direct test import/call 한 쌍과 `_retrieve` 파생 hash 기대 네 개만
갱신했다. Summary field/order, `len(...)` 선행, source별 집계, falsey telemetry
continue, boolean/embedding coercion·누적 순서와 caller trace-construction
경계는 유지됐고 source/tests/whole `+3/-3`, `+6/-6`, `+9/-9`, direct/
identity 12/12, exact structural 2/2, focused 369/369 in 171.572 seconds,
audit 217, pycompile 4/4, unchanged 48/203 DAG, full 2,143/2,143 in 254.573
seconds가 통과했다. 이어 `4506c9f`가 exact 23-line query-budget application
helper를 같은 위치와 본문으로 public `apply_query_budget(...)`로 이름
수렴시키고 pipeline import 한 개/call 세 개, direct test import 한 개/call
두 개와 `_retrieve` 파생 hash 기대 네 개만 갱신했다. Eager normalize/filter,
optional dedupe, nonpositive unlimited, sufficient-budget identity, period-
balanced truncation과 ordered trace/caller adoption 경계는 유지됐고 source/
tests/whole `+5/-5`, `+7/-7`, `+12/-12`, direct/identity 12/12, exact
structural 2/2 in 14.718 seconds, focused 369/369 in 165.974 seconds, audit
217, pycompile 4/4, unchanged 48/203 DAG, full 2,143/2,143 in 226.536
seconds가 통과했다. 이어 `e17d165`가 exact 80-line trace-only cross-trace
reuse candidate diagnostics helper를 같은 위치와 본문으로 public
`cross_trace_reuse_candidate_diagnostics(...)`로 이름 수렴시키고 pipeline
import/call 한 쌍, direct test import/call 한 쌍과 파생 hash 기대 네 개만
갱신했다. Previous/current trace 순회, exact source/query/filter identity,
cap-independent aggregate counts, five-row prior detail slice, cache-hit flags,
ordered trace mapping과 caller adoption 경계는 유지됐고 source/tests/whole
`+3/-3`, `+6/-6`, `+9/-9`, direct/identity 13/13, exact structural 2/2 in
14.213 seconds, focused 369/369 in 166.132 seconds, audit 217, pycompile 4/4,
unchanged 48/203 DAG, full 2,143/2,143 in 231.614 seconds가 통과했다.
이어 `cd443a4`가 exact 20-line runtime-projection metadata helper를 같은
위치와 본문으로 public `attach_runtime_projection_metadata(...)`로 이름
수렴시키고 owner-local call 다섯 개, external import 세 개/call 네 개,
기존 test symbol string 여덟 개와 owner-count 기대 한 개만 갱신했다.
No-material same-object return, shallow metadata copy/update, source/task
normalization, legacy flag, in-place trace adoption과 caller sequencing은
유지됐고 source/tests/whole `+13/-13`, `+9/-9`, `+22/-22`, direct/identity
14/14, exact structural 5/5 in 5.514 seconds, focused 195/195 in 10.520
seconds, audit 217, pycompile 6/6, unchanged 48/203 DAG, full 2,143/2,143 in
249.989 seconds가 통과했다. 이어 `cb470e0`이 exact 22-line canonical runtime-
trace state-update helper를 같은 위치와 본문으로 public
`runtime_trace_state_update(...)`로 이름 수렴시키고 external import 두 개/
call 26개, 기존 test symbol ref 열 개, owner-count 기대 한 개와 파생
CURRENT-SOURCE hash 기대 열두 개만 갱신했다. Canonical trace build, shallow
structured-result copy, read-only report-cache candidate 분류/조건부 trace
adoption과 caller sequencing은 유지됐고 source/tests/whole `+29/-29`,
`+23/-23`, `+52/-52`, direct/identity 18/18, exact affected contracts 8/8 in
1.713 seconds, focused 597/597 in 177.377 seconds, audit 217, pycompile 9/9,
unchanged 48/203 DAG, full 2,143/2,143 in 323.315 seconds가 통과했다. 이어
`f58550f`가 exact 92-line task-scoped trace projection helper를 같은 위치와
본문으로 public `project_task_trace_from_state(...)`로 이름 수렴시키고
external import/call 각 한 개, 기존 test patch string 네 개와 owner-count
기대 한 개만 갱신했다. Task/artifact copy, four-artifact lookup order,
active canonical-trace override, aggregate-sibling suppression,
reconciliation fallback과 caller sequencing은 유지됐고 source/tests/whole
`+3/-3`, `+5/-5`, `+8/-8`, projected-public direct/identity 33/33, exact
affected contracts 3/3, focused 766/766, audit 217, pycompile 5/5, unchanged
48/203 DAG, full 2,143/2,143가 통과했다. 이어 `45ccc05`가 exact 96-line
read-only report-cache candidate helper를 같은 위치와 본문으로 public
`report_cache_candidate_for_trace(...)`로 이름 수렴시키고 owner-local call,
planning import/call과 owner-count 기대만 갱신했다. Candidate field
precedence, producer/key/consumer classification, fixed read-only annotation,
retrieval-bypass projection과 cache-serving-disabled 경계는 유지됐고 source/
tests/whole `+4/-4`, `+1/-1`, `+5/-5`, projected-public direct/identity 45/45,
exact affected contracts 7/7, focused 561/561, audit 217, pycompile 3/3,
unchanged 48/203 DAG, full 2,143/2,143가 통과했다. 이어 `3062222`가 같은
owner의 exact 59-line aggregate calculation projection helper를 기존 public
aggregate wrapper와 구분되는 `build_runtime_aggregate_calculation_projection(...)`
로 이름 수렴시키고 external import 세 개/call 네 개, owner-local call 두 개,
기존 test symbol binding 21개와 owner-count 기대 한 개만 갱신했다. Aggregate
row/operand/source-ID/answer-slot composition과 여섯 caller sequencing은
유지됐고 source/tests/whole `+10/-10`, `+22/-22`, `+32/-32`, exact affected
contracts 8/8, focused 837/837, audit 217, pycompile 7/7, unchanged 48/203 DAG,
full 2,143/2,143가 통과했다. 이어 `814d7bf`가
`financial_runtime_normalization.py`의 exact 31-line KRW compact formatter를
같은 위치와 본문으로 public `format_korean_won_compact(...)`로 이름
수렴시키고 rendering/runtime-trace import/call 두 쌍만 갱신했다. Policy-
driven scale/suffix/rounding과 두 caller sequencing은 유지됐고 source/tests/
whole `+5/-5`, `+0/-0`, `+5/-5`, behavior/identity 13/13, exact structural
4/4, focused 780/780, audit 217, pycompile 3/3, unchanged 48/203 DAG, full
2,143/2,143가 통과했다. 이어 `72f9fa6`이 `financial_formula_eval.py`의 exact
51-line restricted formula evaluator를 같은 위치와 본문으로 public
`safe_eval_formula(...)`로 이름 수렴시키고 calculation-execution import 한
개/call 두 개, 기존 test patch binding 열 개와 파생 caller/payload hash 네
개만 갱신했다. Restricted AST evaluation과 두 caller catch boundary는
유지됐고 source/tests/whole `+4/-4`, `+14/-14`, `+18/-18`, direct behavior/
identity 31/31, exact affected 5/5, focused 863/863, audit 217, pycompile 2/2,
unchanged 48/203 DAG, full 2,143/2,143가 통과했다. 이어
`57013dd`가 `financial_graph_helpers.py`의 exact 31-line concept-metric label
helper를 같은 위치와 본문으로 public `build_concept_metric_label(...)`로
이름 수렴시키고 owner-local call 네 개, planning import/call 한 쌍과 기존
owner-count 기대 43개만 갱신했다. Policy-driven label construction과 다섯
caller gate는 유지됐고 source/tests/whole `+7/-7`, `+43/-43`, `+50/-50`,
exact affected 41/41, focused 634/634, audit 217, pycompile 2/2, unchanged
48/203 DAG, full 2,143/2,143가 통과했다. 이어 `17acfe6`이 같은 파일의 exact
24-line concept-task constraint builder를 public
`build_concept_task_constraints(...)`로 이름 수렴시키고 owner-local call 두
개, planning import/call 한 쌍, 기존 exact test symbol ref 14개, owner-count
기대 43개와 active derived hash 기대 네 개만 갱신했다. Policy/default
composition, four-field result와 세 caller gate는 유지됐고 source/tests/whole
`+5/-5`, `+61/-61`, `+66/-66`, exact affected 48/48, focused 638/638,
audit 217, pycompile 2/2, unchanged 48/203 DAG, full 2,143/2,143가 통과했다.
이어 `965b893`이 같은 파일의 exact 25-line operation-family inference
helper를 public `infer_operation_family_from_query(...)`로 이름 수렴시키고
owner-local call 네 개, planning import/call 한 쌍, exact test symbol ref
32개, owner-count 기대 43개와 active derived hash 기대 열 개만 갱신했다.
Policy/predicate/cue precedence와 다섯 caller gate는 유지됐고 source/tests/
whole `+7/-7`, `+85/-85`, `+92/-92`, exact affected 52/52, focused 634/634,
audit 217, pycompile 2/2, unchanged 48/203 DAG, full 2,143/2,143가 통과했다.
이어 `5a40a1b`가 같은 파일의 exact 32-line generic operand-label extractor를
public `extract_generic_operand_labels(...)`로 이름 수렴시키고 owner-local
call 세 개, evidence/reconciliation import/call 두 쌍, exact test symbol ref
24개, owner-count 기대 43개와 active derived hash record 13개만 갱신했다.
Generic policy/ontology label composition과 다섯 caller gate는 유지됐고
source/tests/whole `+8/-8`, `+80/-80`, `+88/-88`, exact affected 51/51,
focused 634/634, audit 217, pycompile 3/3, unchanged 48/203 DAG, full
  2,143/2,143가 통과했다. 이어 `eeefa47`이
`financial_retrieval_hints.py`의 exact 35-line statement/section hint inference
helper를 public `infer_statement_and_section_hints(...)`로 이름 수렴시키고
owner-local call 한 개, helpers/planning import 두 개와 external call 네 개,
exact test symbol ref 12개, owner-count 기대 두 개와 active derived hash record
여덟 개만 갱신했다. Ordered document/segment/numeric/narrative/ontology hint
composition과 다섯 caller gate는 유지됐고 source/tests/whole `+8/-8`,
`+22/-22`, `+30/-30`, exact affected 13/13, focused 541/541, audit 217,
  pycompile 3/3, unchanged 48/203 DAG, full 2,143/2,143가 통과했다. 이어
  `a2da2d6`이 `financial_graph_helpers.py`의 exact 40-line policy-driven
  metric-task query builder를 public `build_metric_task_query(...)`로 이름
  수렴시키고 owner-local call 네 개, planning import/call 한 쌍, exact test
  symbol ref 일곱 개, graph owner-count 기대 43개와 파생 owner/order 기대 한
  개만 갱신했다. Year/scope/operand/template composition과 다섯 keyword-only
  caller gate는 유지됐고 source/tests/whole `+7/-7`, `+50/-50`, `+57/-57`,
  exact affected 45/45, focused 628/628, audit 217, pycompile 2/2, unchanged
  48/203 DAG, full 2,143/2,143가 통과했다. 이어 `f152cbd`가 같은 파일의
  exact 57-line state-free generic-concept spec inference를 public
  `infer_generic_concept_spec(...)`로 이름 수렴시키고 owner-local call 네 개,
  planning import/call 한 쌍, exact test symbol ref 일곱 개, graph owner-count
  기대 43개와 active derived hash record 여덟 개만 갱신했다. Exact/fuzzy/
  ontology-fallback precedence와 다섯 two-positional caller gate는 유지됐고
  source/tests/whole `+7/-7`, `+58/-58`, `+65/-65`, exact affected 46/46,
  focused 628/628, audit 217, pycompile 2/2, unchanged 48/203 DAG, full
  2,143/2,143가 통과했다. 이어진 docs/static Phase 3 종료 감사는 production
  source/test 변경 없이 private mesh와 네 부채군을 다시 계수했고, 다음
  exact batch로 runtime-trace resolver public API visibility seam 하나만
  선택했다. `2892d1b`가 그 94-line resolver를 in-place public API로 이름
  수렴시키고 17 source imports, 28 direct source calls, five direct test
  imports, 102 test name loads, 28 patch targets와 파생 기대만 갱신했다.
  Resolver precedence/body/state/ledger 및 여섯 lazy adapter wrapper는
  유지됐다. Source/tests/whole `+46/-46`, `+142/-142`, `+188/-188`, exact
  101/101, corrected focused 1,176/1,176, audit 217, pycompile 18/18, identity
  11/11, unchanged 48/203 DAG, full 2,143/2,143가 통과했다. 이어 reviewer
  gate와 fixture demo를 재실행해 `review_surface_ready`, manifest verified,
  13/13, integrity `ok`, critic `accepted`를 확인했다. Production source/test는
  바뀌지 않았고 리팩터링은 중단됐다.
- `ab7e9ba`는 PR #86 Ubuntu checkout이 발견한 fixture raw-byte CRLF/LF
  불일치를 schema-v2 `line_endings_lf` binding으로 고쳤다. LF/CRLF direct
  regressions, local reviewer 32/32, audit 217, exact-head GitHub Actions
  `32809007035`의 full 2,145/2,145가 통과했다.
- source/docs head `672fc7f`에서 current profile과 기존 4개 store의 설정 일치,
  strict vector health를 확인한 뒤 provider-backed eval-only 5문항을 실행했다.
  첫 full run은 error 0.0%였지만 NAVER가 correct task outputs 대신 다른 MDA
  pair를 최종 operand로 택해 `17.6%`를 냈고, LGE는 올바른 절대값을
  "상승했습니다"로 렌더링했으며, Samsung은 final answer와 lookup trace가
  불일치했다. NAVER/Samsung focused rerun은 numeric trace가 수렴했지만 이로써
  안정 pass가 아니라 run-to-run 비결정성이 확인됐다. Samsung의 남은
  `refusal_accuracy=0`은 `끊임없는` 안의 `없`을 잡은 evaluator false positive다.
  7 question executions의 recorded runtime LLM cost는 `$0.4344568`이고 embedding
  cost는 보고되지 않았다. 두 result/heartbeat bundle은 ignored local-only이며
  stage하지 않는다. 이어 NAVER의 기존 semantic-plan `segment_label`을 flattened
  table-label recovery가 강제하도록 하고, complete result와 source-stated 비율이
  동치이면 task-output operand를 보존하는 일반 precedence 계약을 추가했다. 실제
  source-stated 충돌의 repair 경로는 유지됐고, 중복 raw binding-policy read는
  삭제했다. Focused 5/5, aggregate 126/126, operation 242/242, graph-helper 290/290,
  audit 217, full 2,147/2,147가 통과했다. 이어 store-fixed NAVER focused replay를
  두 번 실행했고 두 실행 모두 `커머스`, `2,546,649 / 1,801,079백만원`, `41.4%`로
  같은 numeric trace를 유지했다. 두 번째 실행의 LLM grounded-rendering judge가
  질문이 요구한 정성 설명을 금지된 내용으로 오독해 calculation score를 0으로
  낮춘 evaluator false negative를 발견했다. Numeric rendering은 canonical trace,
  trace-derived value, runtime evidence만 deterministic하게 비교하도록 바꾸고,
  semantic trend judgement는 calculation score에서 분리했다. Exact artifacts를
  no-call replay한 결과 양쪽 grounded rendering/calculation이 1.000/1.000으로
  수렴했다. Evaluator/benchmark focused 114/114, audit 217, full 2,151/2,151가
  통과했다. 이어 generic `difference` answer slot을 기간 증감 `period_delta`와
  구성요소 차감 `derived_value`로 구분했다. Fresh derived row는
  `minuend/subtrahend`, `primary_value`, `direction=null`을 보존하며 current/prior
  slot을 합성하지 않는다. 관련 regression 829/829, audit 217, pycompile과 full
  2,153/2,153가 통과했다. Existing store를 재사용한 monitored `LGE_T1_051`
  eval-only는 `1,486,334백만원입니다`로 중립 렌더링했고 numeric PASS,
  faithfulness/completeness/grounded rendering/calculation 1.000, error 0.0%를
  기록했다. 9 LLM calls, 45,848 tokens, `$0.0478852`였고 no DART parse/fetch/
  ingest였다. Result/heartbeat는 ignored local-only다. PR #86은 draft, `main`은
  그대로다. Release gate와 재개 조건은
  [Next Work](docs/overview/project_status.md#next-work)가 단일 기준이다.
- 이어 evaluator runtime-evidence context ordering, explicit-role component-
  difference answer rendering, late numeric refresh의 grounded query-term
  preservation을 일반 계약으로 추가했다. Focused LGE replay C가 completeness
  1.000을 회복했고, 최종 store-fixed gate는 4/4 company, 5/5 question, pass
  count 4, full-eval fail count 0, error/integrity issue 0으로 닫혔다. 관련
  498/498, audit 217, full 2,163/2,163가 통과했다. 이는 persisted-store
  integration evidence이며 fresh ingest나 새 published quality claim은 아니다.
  PR #86과 `main` 상태는 그대로다.

## 구현 원칙

- benchmark 질문, 회사명과 metric-specific phrase를 runtime branch에 넣지 않는다.
- 금융 domain vocabulary는 ontology, retrieval policy, config 또는 documented data
  artifact에 둔다.
- LLM은 intent와 semantics를 판단하고, 산술·unit conversion·dependency binding·
  dedupe·validation은 deterministic code가 담당한다.
- answer composer는 evidence에 없는 claim을 만들지 않는다.
- parser/ingest/cache signature가 바뀌지 않으면 store-fixed `eval-only`를 fresh
  ingest보다 우선한다.
- `src/agent` 또는 `src/routing` 변경은 broader tests 전에
  `python -m src.ops.audit_runtime_domain_terms`를 실행한다.
- benchmark/store/cache/heartbeat output은 명시적 승인 없이는 stage하지 않는다.

## 새 세션 시작 순서

1. `AGENTS.md`
2. 이 문서
3. [project_status.md](docs/overview/project_status.md)
4. `git status -sb`
5. `git log -5 --oneline`
6. 선택된 batch가 있으면 관련 runtime contract와 focused test

ChatGPT/Codex memory는 사용자 선호와 반복 작업 습관만 보조한다. 최신 commit,
blocker, benchmark, API/model 상태와 artifact 위치는 repo 문서와 Git을 우선한다.

## 문서 지도

| 필요한 정보 | 권위 문서 |
| --- | --- |
| 현재 제품·gate·blocker·우선순위 | [project_status.md](docs/overview/project_status.md) |
| runtime behavior contract | [agent_runtime_contract.md](docs/architecture/agent_runtime_contract.md) |
| 실행 topology와 owner 역할 | [runtime_flow_roles.md](docs/overview/runtime_flow_roles.md) |
| Phase debt와 stop line | [core_runtime_surface_refactoring_plan.md](docs/architecture/core_runtime_surface_refactoring_plan.md) |
| 구현 연대기와 commit별 수치 | [implementation_history.md](docs/history/implementation_history.md) |
| benchmark와 실험 연대기 | [experiment_history.md](docs/history/experiment_history.md) |
| 장기 backlog | [backlog_and_next_epics.md](docs/planning/backlog_and_next_epics.md) |

이 축약 이전 snapshot은 Git의 `1897fd1^:CONTEXT.md`에서 확인할 수 있다.
