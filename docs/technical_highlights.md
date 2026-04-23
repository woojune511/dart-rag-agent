# Technical Highlights

이 문서는 프로젝트를 빠르게 훑을 때 먼저 봐야 할 핵심 기술 포인트를 요약한다.

## 1. 비표준 공시 문서를 구조적으로 읽는 ingestion

이 프로젝트는 일반 웹 문서를 대상으로 한 splitter 대신, DART XML의 구조를 직접 해석하는 parser를 사용한다.

핵심 포인트:

- `SECTION-*`, `TITLE`, `P`, `TABLE`, `TABLE-GROUP`를 직접 파싱
- section path, block type, table context를 retrieval metadata로 유지
- chunking을 문자 길이보다 **문서 구조 보존** 중심으로 설계

의미:

- 공시 문서처럼 표와 문단, 섹션 경계가 중요한 도메인에서 retrieval 품질과 citation 품질을 동시에 확보하기 위한 결정이다.

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

## 7. selective contextualization으로 표 의미를 복원하는 저비용 retrieval

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

## 8. 비용 통제를 고려한 benchmark 운영

benchmark는 model quality만이 아니라 실험 비용과 반복 속도까지 함께 다룬다.

핵심 포인트:

- `dev_fast` / `release_generalization` 프로파일 분리
- `Hybrid Cache`
  - `stores/...`
  - `context_cache/...`
- screening -> full evaluation 2단계 운영

의미:

- 실험 비용을 통제하면서도 품질 하한선을 유지하는 실험 운영 구조 자체가 이 프로젝트의 중요한 엔지니어링 결정이다.
