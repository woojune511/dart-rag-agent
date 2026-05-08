# Technical Highlights

이 문서는 프로젝트를 빠르게 훑을 때 먼저 봐야 할 핵심 기술 포인트를 요약한다.

현재 이 저장소는 단순한 DART QA 앱보다, **DART 도메인 위에서 multi-agent financial analysis system을 설계/검증하는 실험 프로젝트**로 읽는 것이 맞다.  
아래 기술 포인트들은 그 MAS 실험의 기반 자산이다.

## 0. 강한 single-agent 자산을 MAS building block으로 재사용한다

이 프로젝트는 처음부터 MAS로 시작한 것은 아니다. 먼저 아래 자산을 단단하게 만들었다.

| 자산 | 앞으로의 역할 |
| --- | --- |
| structure-aware parser | 공통 retrieval substrate |
| hybrid retrieval + graph expansion | Analyst / Researcher 공용 retrieval layer |
| formula planner + safe AST | Analyst core |
| operand grounding evaluator | Critic / evaluator core |
| benchmark / replay infra | offline scorecard / regression layer |

즉 현재 방향은 “새 MAS를 백지에서 다시 짠다”가 아니라,  
**이미 검증된 single-agent 자산을 role-separated MAS로 이식하는 것**이다.

## 0-1. 병렬 worker + critic loop + merge를 갖춘 walking MAS skeleton을 실제로 개통했다

최근에는 single-agent 자산을 설명용으로만 두지 않고, 실제 MAS topology 안으로 이식했다.

핵심 포인트:

- `Orchestrator_Plan -> Analyst / Researcher -> Critic -> Orchestrator_Merge`
- communication은 자유 채팅이 아니라 `tasks`, `artifacts`, `evidence_pool`, `critic_reports` 기반 task ledger
- real-store smoke 기준
  - Analyst migration: `numeric_result_match_rate = 1.000`
  - Researcher migration: `citation_match_rate = 1.000`, `critic_pass_rate = 1.000`
  - E2E MAS smoke: mixed-intent 질의 `2/2`에서 최종 report 생성, `1/2`에서 critic-triggered analyst retry 관측

의미:

- 이 프로젝트는 더 이상 “MAS를 설계할 예정”인 상태가 아니라,
  **실제 worker migration과 critic loop까지 개통된 walking skeleton**을 갖고 있다.
- 이후 Researcher/Orchestrator 품질 튜닝은 모두 이 E2E baseline 위에서 delta로 측정할 수 있다.

## 1. 비표준 공시 문서를 구조적으로 읽는 ingestion

이 프로젝트는 일반 웹 문서를 대상으로 한 splitter 대신, DART XML의 구조를 직접 해석하는 parser를 사용한다.

핵심 포인트:

- `SECTION-*`, `TITLE`, `P`, `TABLE`, `TABLE-GROUP`를 직접 파싱
- section path, block type, table context를 retrieval metadata로 유지
- chunking을 문자 길이보다 **문서 구조 보존** 중심으로 설계

의미:

- 공시 문서처럼 표와 문단, 섹션 경계가 중요한 도메인에서 retrieval 품질과 citation 품질을 동시에 확보하기 위한 결정이다.

## 1-1. raw XML을 직접 LLM에 주지 않고, high-value section만 soft heading으로 정규화한다

최근 확인된 핵심 문제는 DART 원문이 항상 nested `SECTION-*`로 하위 구조를 주지 않는다는 점이다.

핵심 포인트:

- `IV. 이사의 경영진단 및 분석의견`의 하위 제목들은 `SECTION-*`가 아니라 bold `SPAN` 내부에 묻혀 있음
- parser는 `SECTION-* + TITLE(ATOC="Y")`의 canonical `section_path`를 유지하고,
  `local_heading`은 LLM 안내용 soft metadata로만 복원한다
- high-value section만 보수적으로 heading을 복원해
  - `3. 재무상태 및 영업실적 > 나. 영업실적`
  - `[클라우드] > (가) 영업 개요`
  같은 문맥 라벨을 준다
- low-value corporate/governance section은 coarse section 단위로 남겨 오탐 heading을 줄인다

의미:

- 문제의 본질은 “LLM이 XML을 못 읽는다”보다, **invalid XML-like markup와 과한 hidden-heading 복원이 동시에 parser를 복잡하게 만든다**는 데 있다.
- 따라서 parser는 raw source를 직접 고치지 않고 sanitize를 먼저 적용하고,
  high-value section만 soft heading으로 복원하는 단순한 RAG-friendly contract를 택한다.

## 1-2. 대형 표는 full-table 하나로 두지 않고 column/row/narrative split을 함께 쓴다

공시 주석의 표는 단순 row split만으로는 충분하지 않았다.

핵심 포인트:

- wide table은 먼저 `column window`로 자른다
- 그래도 크면 `row split`을 추가 적용한다
- `1. 분할방법 | 아주 긴 설명 ...` 같은 서술형 표 row는
  - header로 오판하지 않고
  - 값 셀 안의 `(1)`, `(2)` 같은 번호를 기준으로 추가 분할한다
- chunk metadata에 `table_view`를 남겨
  - `full`
  - `row_window`
  - `column_window`
  - `column_row_window`
  를 구분한다

의미:

- 이 프로젝트의 table handling은 “표를 텍스트로만 펴서 넣는다”가 아니라,
  **numeric retrieval에 필요한 구조는 유지하면서 oversized chunk를 줄이는 width-aware / narrative-aware splitting**으로 발전했다.
- 실제로 POSCO 대형 표의 `5985` char chunk는 이 단계에서 해소됐다.

## 2. retrieval granularity와 reasoning context를 분리한 parent-child retrieval

검색은 child chunk로 하고, 답변은 parent section을 우선 컨텍스트로 삼는다.

핵심 포인트:

- child chunk는 검색 정밀도 확보
- parent section은 answer generation의 맥락 안정화
- contextual ingest는 child chunk 앞에 설명용 context를 붙여 retrieval 신호를 보강

의미:

- “잘 찾는 것”과 “잘 설명하는 것”의 요구가 다르다는 점을 구조로 분리한 설계다.

## 3. answer generation을 evidence compression 문제로 재정의

이 프로젝트의 핵심 전환점은 answer generation을 자유 생성에서 evidence compression으로 다시 정의한 것이다.

현재 구조:

```text
retrieve
  -> build_structured_evidence
  -> compress
  -> validate
  -> cite
```

핵심 포인트:

- runtime evidence를 structured object로 기록
- `selected_claim_ids`, `kept_claim_ids`, `dropped_claim_ids`, `unsupported_sentences`를 결과물에 남김
- validator가 unsupported / redundant / overextended 문장을 후단에서 걸러낼 수 있게 함

의미:

- 답변이 왜 그렇게 나왔는지 설명 가능하게 만들고, benchmark tuning을 넘어 agent의 controllability를 높이기 위한 방향이다.

## 4. 숫자 질문은 generic judge에서 분리

`300조 8,709억원`과 `300,870,903 백만원`은 같은 값이지만, generic `faithfulness` judge는 이를 종종 false fail로 처리한다.

그래서 숫자 질문은 별도 evaluator path로 분리했다.

핵심 포인트:

- `numeric_equivalence`
- `numeric_grounding`
- `numeric_retrieval_support`
- `numeric_final_judgement`
- `absolute_error_rate`
- `calculation_correctness`

의미:

- 하나의 LLM judge에 모든 채점을 맡기지 않고, 숫자 동치성 / grounding / retrieval support를 병렬로 해석하는 방향이다.
- retrospective evaluator 실험에서 `operand grounding` 판정으로 바꾼 뒤, human-correct positive set 기준 false negative rate를 `12.5% -> 0.0%`로 줄였다.

## 4-1. 계산은 LLM에게 맡기지 않고 planner/executor로 분리

단순 RAG에서 LLM이 직접 계산까지 하게 두면, retrieval이 충분해도 단위/표현/부호 처리에서 흔들리는 경우가 반복됐다.

핵심 포인트:

- direct-calc baseline은 같은 retrieval evidence를 주고 LLM에게 바로 계산/답변을 시킴
- proposed path는 `formula planner -> safe AST calculator -> grounded renderer`
- retrospective architecture 실험에서 numeric-only 9문항 기준:
  - direct calc strict correctness: `0.556`
  - formula planner + AST strict correctness: `1.000`

의미:

- 이 프로젝트의 계산 경로는 단순한 prompt tuning이 아니라, **LLM의 역할을 “수식/답안 계획”으로 제한하고 실행은 symbolic engine으로 넘기는 neuro-symbolic 분리**라는 점이 정량적으로 입증됐다.

## 5. 평가를 먼저 고정하고 시스템을 바꾸는 방식

최근 방향 전환의 핵심은 “시스템을 더 고치기 전에 평가 기준을 먼저 고정한다”는 것이다.

핵심 포인트:

- 삼성전자 2024 사업보고서 기준 single-document Golden Dataset 구축
- category별 metric 분리
- `single_document_dev` benchmark profile 추가
- multi-company benchmark는 그 이후 단계로 후순위화

의미:

- retrieval / generation tweak를 계속 쌓는 대신, 무엇을 실제 개선으로 볼지 기준선을 먼저 만든다.

## 6. seed retrieval을 싸게 보강하는 zero-cost prefix

graph expansion만으로는 잘못 잡힌 seed retrieval을 복구하기 어렵다는 점이 micro benchmark에서 드러났다.

그래서 `plain` 인덱싱에는 LLM 없이도 semantic hint를 주는 `Zero-Cost Prefix`를 도입했다.

핵심 포인트:

- 원문 앞에 `[섹션]`, `[분류]`, `[키워드]`를 hardcoded 문자열로 삽입
- `위험관리 및 파생거래 -> 리스크 / 시장위험 / 신용위험 / 유동성위험` 같은 alias를 같이 주입
- `plain + graph expansion`과 조합해 seed retrieval miss를 줄임

의미:

- `contextual_ingest`처럼 청크마다 LLM 요약을 붙이지 않고도, vocabulary mismatch를 크게 완화할 수 있다.
- 비용을 거의 0으로 유지하면서도 retrieval recall을 회복하는 **도메인 특화 RAG 엔지니어링 결정**이다.

## 7. 재무 온톨로지로 ratio/percent source miss를 복구

일반 semantic retrieval은 질문에 `매출`, `비중`, `%` 같은 고빈도 단어가 섞이면 `연구개발활동`처럼 정답 row가 있는 section을 놓칠 수 있었다.

핵심 포인트:

- `financial_ontology.json`에 metric family별
  - `preferred_sections`
  - `supplement_sections`
  - `query_hints`
  를 분리
- retrieval 단계에서만 ontology hook을 켠 retrospective 실험에서:
  - `operand_grounding_score` `0.50 -> 1.00`
  - `calc_success_rate` `0.33 -> 1.00`
  - `row_candidate_recovery_rate` `0.00 -> 0.67`
- 특히 `comparison_005`, `comparison_006`에서 `연구개발활동` row를 다시 끌어오며 `insufficient_operands`를 해소

의미:

- 이 프로젝트의 ontology는 단순 라벨링 파일이 아니라, **재무 ratio 질문에서 source miss를 복구하는 retrieval control layer**로 작동한다.
- 포트폴리오 관점에서는 “semantic search만으로는 부족한 도메인에서, 선언적 도메인 지식으로 operand 회수율을 복구했다”는 스토리를 만든다.

## 8. selective contextualization으로 표 의미를 복원하는 저비용 retrieval

`plain + prefix`는 seed retrieval 복구에는 강했지만, 표 내부 의미가 중요한 숫자 질문에서는 한계가 드러났다.

그래서 현재는 `contextual_selective_v2 + prefix` 조합을 저비용 주력 후보로 보고 있다.

핵심 포인트:

- `Zero-Cost Prefix`로 seed retrieval vocabulary mismatch 완화
- `table` 청크와 일부 핵심 섹션만 선택적으로 LLM context 생성
- 전체 `contextual_all`보다 훨씬 적은 ingest 비용으로
  - `numeric_fact_001`
  - `risk_analysis_001`
  같은 질문의 answerability 회복

의미:

- 무조건 모든 청크에 contextualization을 붙이지 않고, 문서 구조와 질문 특성에 따라 **필요한 부분만 의미를 번역**하는 retrieval 설계다.
- 이는 비용 절감보다도 “표를 읽을 수 있게 만드는 최소한의 semantic lift”라는 점에서 중요한 결정이다.

## 9. 비용 통제를 고려한 benchmark 운영

benchmark는 model quality만이 아니라 실험 비용과 반복 속도까지 함께 다룬다.

핵심 포인트:

- `dev_fast` / `release_generalization` 프로파일 분리
- `Hybrid Cache`
  - `stores/...`
  - `context_cache/...`
- screening -> full evaluation 2단계 운영

의미:

- 실험 비용을 통제하면서도 품질 하한선을 유지하는 실험 운영 구조 자체가 이 프로젝트의 중요한 엔지니어링 결정이다.

## 10. query routing을 retrieval 정책과 분리한 cascade 설계

최근에는 retrieval 품질 저하의 일부 원인이 검색기 자체보다 query routing variance라는 점이 드러났다.

핵심 포인트:

- `query_type` 하나로 모든 정책을 결정하지 않음
- `intent`
- `format_preference`
를 분리해 state로 유지
- semantic router fast-path
- few-shot LLM fallback
- rerank / retrieval block-type 정책은 `format_preference` 기준으로 적용

의미:

- 질문의 의도와 evidence 형식 선호를 분리하면서 table penalty 같은 정책 충돌을 줄인다.
- 쉬운 질문은 빠르고 저렴하게, 애매한 질문은 fallback으로 정교하게 처리하는 cascade routing은 포트폴리오 관점에서도 설명력이 높은 설계다.
