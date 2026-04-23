# 실행 계획

이 문서는 다음 스프린트의 우선순위와 성공 조건을 정리한 계획서다.

현재 가장 큰 방향 전환은 다음이다.

- retrieval / generation의 국소 조정보다
- **단일 문서 Golden Dataset + evaluator 확정**
  을 먼저 한다

상세 전략은 [single_document_eval_strategy.md](docs/single_document_eval_strategy.md)를 참고한다.

## 현재 기준선

현재 기본 baseline:

- `chunk_size = 2500`
- `chunk_overlap = 320`
- `ingest_mode = contextual_all`
- retrieval = dense + BM25 + RRF
- reasoning = evidence-first

현재까지 확인된 사실:

- 삼성전자 기준으로 `contextual_parent_only_2500_320`가 screening을 통과한 적이 있다
- `plain`은 risk retrieval miss가 반복됐다
- `contextual_selective_v2`는 business overview miss 가능성이 남아 있다
- `contextual_parent_hybrid`는 품질은 보완할 수 있지만 비용 이점이 약할 수 있다
- 3기업을 한 번에 도는 monolithic run은 timeout과 비용 리스크가 커서 기본 루프로 부적합하다

추가로 확인된 평가 한계:

- 기존 `ground_truth` 한 줄만으로는 도메인 비전문가가 정답 타당성을 검수하기 어렵다
- retrieval 지표보다 answer-level 지표의 신뢰도를 설명하기 어려웠다

## 이번 스프린트 목표

이번 스프린트는 운영 기본값을 바꾸는 단계가 아니다.

현재 1순위 목표:

- 삼성전자 2024 사업보고서 1건 기준으로
- Golden Dataset과 evaluator를 먼저 고정하는 것

즉 다음 단계는

- 더 싼 ingest 후보를 찾는 것
- 다기업 generalization을 다시 돌리는 것

보다 먼저,

- 질문 taxonomy 확정
- JSON schema 확정
- retrieval / generation / numeric / refusal evaluator 확정
- benchmark runner의 single-document 모드 정리

를 하는 것이다.

추가로, `v6` / `v7` faithfulness 보정 실험을 통해 **question-type별 hardcoded rule을 계속 늘리는 방식은 장기적으로 위험하다**는 점이 분명해졌다. 앞으로는 점수 자체를 올리는 것보다, [answer_generation_principles.md](docs/answer_generation_principles.md)에 정리한 원칙에 맞춰 answer generation 구조를 더 단순하고 설명 가능하게 만드는 것을 우선한다.

또한 구조 개편 방향은 [architecture_direction.md](docs/architecture_direction.md)에 정리했다. 현재 결론은 full GraphRAG / full multi-agent로 바로 가기보다, document-structure graph + structured evidence + answer compression/validation 쪽 리팩터링이 더 적절하다는 것이다.

숫자 질문(`numeric_fact`)은 일반 서술형 `faithfulness` judge와 분리해서 다루기로 했고, 현재 [numeric_evaluation_architecture.md](docs/numeric_evaluation_architecture.md)에 정리한 **parallel numeric evaluators + resolver** 구조의 1차 구현이 들어간 상태다. 삼성전자 `numeric_fact_001` 재검증에서는 generic `faithfulness=0.0`인데도 `numeric_final_judgement=PASS`가 나와, false fail을 줄이는 방향이 유효함을 확인했다. 다음 단계는 설계 그 자체보다, 이 numeric evaluator를 aggregate와 해석 규칙에 제대로 반영하는 것이다.

추가로 answer generation 쪽에서는 `compress -> validate`를 유지하되, 이제 문자열 중심이 아니라 **typed compression / validation output**으로 옮겨가고 있다. 현재 구현은 아래 필드를 남긴다.

- `selected_claim_ids`
- `draft_points`
- `kept_claim_ids`
- `dropped_claim_ids`
- `unsupported_sentences`
- `sentence_checks`

typed artifact 검증 결과, 이 필드들은 reviewer artifact에서 실제로 읽히지만 validator가 아직 충분히 공격적으로 pruning하지는 못한다. 따라서 다음 단계는 validator를 더 세게 만드는 것보다, compression 앞단의 claim selection을 더 구조화하는 것이다.

기본 운영 방식:

- 평소에는 `benchmarks/profiles/dev_fast.json`으로 단일 기업 + screening only
- shortlist 검증 때만 `benchmarks/profiles/release_generalization.json`으로 3기업 run
- release run도 회사별 job으로 분리 실행하고 partial summary를 허용

핵심 질문:

- 왜 저비용 후보들이 numeric / risk / R&D에서 abstention으로 무너지는가
- 왜 NAVER에서는 business overview가 계속 miss되는가
- missing-information 질문에서 hallucination을 어떻게 줄일 것인가
- 이 문제를 줄인 뒤에도 `contextual_parent_only` 또는 `contextual_selective_v2`가 비용 이점을 유지하는가

## 우선순위 작업

### 0. Single-document benchmark lab 구축

목표:

- 삼성전자 2024 사업보고서 1건만 대상으로 benchmark 기준선을 다시 세운다

산출물:

- `docs/single_document_eval_strategy.md`
- `benchmarks/golden/samsung_2024_v1.json`
- `benchmarks/profiles/single_document_dev.json`

핵심 순서:

1. 질문 taxonomy 확정
2. JSON schema v1 확정
3. Golden Dataset 20~30개 구축
4. category별 evaluator 분리 + metric spec 고정
5. benchmark runner 연결
6. 그 다음에만 시스템 개선 재개

현재 진행 상태:

- Golden Dataset `v1 draft` 20문항 생성 완료
- `docs/evaluation_metrics_v1.md` 추가 완료
- evaluator loader가 `query_id / ground_truth_answer / ground_truth_context_ids / ground_truth_evidence_quotes`를 읽도록 확장 완료
- retrieval / generation / numeric / refusal metric v1 1차 구현 완료
- single-document benchmark profile 추가 완료
- 다음 단계는 dataset을 `draft -> verified`로 검수하고, single-document runner를 실제 기준선으로 고정하는 것이다

### 0-1. Document-Structure Graph micro benchmark

목표:

- expensive `contextual_ingest` 없이도 retrieval 이후 문서 구조 확장만으로 충분한 context recall을 확보할 수 있는지 본다

현재 구현 범위:

- `retrieve -> expand_via_structure_graph -> evidence`
- 확장에 사용하는 구조 정보:
  - `parent_id`
  - sibling (`sibling_prev`, `sibling_next`)
  - `table_context`
- graph는 full GraphRAG가 아니라 **retrieval 후 후처리 확장용 최소 구조 그래프**로 둔다

산출물:

- `benchmarks/profiles/single_document_graph_micro.json`
- `plain + graph expansion` 실험 결과 1회

비교 대상:

- Control:
  - `contextual_all_2500_320`
- Reference:
  - `plain_1500_200`
  - `plain_2500_320`
- Treatment:
  - `plain_graph_1500_200`
  - `plain_graph_2500_320`

micro-dataset:

- `q_001` numeric fact
- `q_004` multi-hop calculation
- `q_006` business overview
- `q_009` risk synthesis
- `q_019` adversarial refusal

핵심 질문:

- graph expansion이 `plain` 대비 `context_recall`과 retrieval support를 실제로 끌어올리는가
- `contextual_all` 대비 비용은 크게 낮으면서 성능은 어느 정도 유지되는가
- 1500/200 vs 2500/320 중 어떤 chunking이 graph expansion과 더 잘 맞는가

현재 상태:

- 1차 `graph_micro_2026-04-22`
  - `plain + graph expansion`만으로는 `contextual_all` 대체 실패
  - `q_009` 리스크 질문에서 seed retrieval miss가 핵심 병목으로 드러남
- 2차 `graph_micro_constrained_2026-04-22`
  - `table -> paragraph prev만 허용`, `sibling_next 제거`, `max_docs=8`
  - noise는 줄었지만 seed retrieval miss는 해결하지 못함
- 3차 `graph_micro_prefix_2026-04-22`
  - `plain` / `plain_graph`에 Zero-Cost Prefix 추가
  - `q_009`는 plain 계열에서도 `hit@k = 1.0`으로 회복
  - `q_001` 연결 기준 매출액은 여전히 `연결재무제표 주석` 위주로 retrieve되고 answerable abstention이 남음

현재 판단:

- graph expansion은 retrieval replacement가 아니라 **retrieval 보강 수단**
- 리스크 질문은 `Zero-Cost Prefix`로 seed retrieval을 먼저 살리는 쪽이 맞음
- 다음 우선순위는 graph보다 `numeric_fact`의 query target alignment
  - `연결 기준 매출액`
  - `연결 손익계산서`
  - `매출 및 수주상황`
  - `요약재무정보`
  를 같은 target family로 다루고, `연결재무제표 주석`은 기본 감점하는 쪽

### 0-2. Prefix + Selective Contextual Retrieval

목표:

- `plain + prefix`의 retrieval 보강은 유지하되, 표 기반 숫자 질문에서 필요한 최소 contextualization만 추가
- 전체 contextual ingest 대신 **선택적 contextualization + zero-cost prefix** 조합의 품질을 확인

현재 상태:

- `dev_fast_focus_selective_prefix_2026-04-23` 실행 완료
- 새 후보 `contextual_selective_v2_prefix_2500_320` 추가
  - `ingest_mode = contextual_selective_v2`
  - `use_zero_cost_prefix = true`

핵심 결과:

- `plain_prefix_2500_320`
  - retrieval seed는 강하지만 `numeric_fact_001`에서 “구체적인 수치 정보가 없다”고 기권
  - `numeric_final_judgement = FAIL`
- `contextual_selective_v2_prefix_2500_320`
  - `screen_pass = yes`
  - `faithfulness 0.675`
  - `answer_relevancy 0.580`
  - `context_recall 0.625`
  - `numeric_pass = 1.000`

현재 해석:

- `plain + prefix`만으로는 표 내부 의미를 충분히 복원하지 못한다.
- `table` 청크에 selective contextualization을 추가하면 `q_001`과 `q_009` 둘 다 더 안정적으로 처리된다.
- 현재 저비용 품질 후보는 `plain_prefix`보다 `contextual_selective_v2_prefix`가 더 설득력 있다.

### 0-3. Query routing 재설계 준비

목표:

- retrieval / validator 앞단의 query routing variance를 먼저 줄인다
- `query_type` 하나가 intent와 retrieval format preference를 동시에 결정하는 현재 구조를 정리한다

최근 확인된 문제:

- `contextual_selective_v2_prefix_2500_320` store를 재사용한 직접 실행에서
  - `주요 재무 리스크는 무엇인가요?`
  - `회사가 영위하는 주요 사업은 무엇인가요?`
  질문이 모두 `numeric_fact`로 잘못 분류되는 사례가 확인됐다
- 이는 retrieval이나 validator 이전에 **query routing 자체가 불안정**하다는 뜻이다
- 기존에는 `business_overview`가 table penalty를 받는 구조적 충돌도 있었고, 최근 수정으로 이 충돌은 완화했다

다음 단계 준비물:

1. `intent` / `format_preference` 분리 스키마 초안
2. edge case few-shot 예제 세트
3. semantic router용 canonical query 세트
4. `financial_graph.py`에 최소 변경으로 끼울 routing 설계안

방향:

- keyword rule을 계속 늘리지 않는다
- 초기에는 `few-shot LLM classifier`와 `semantic router`를 함께 준비한다
- 최종 운영 구조는 병렬보다 **직렬 cascade**를 우선 검토한다

현재 상태:

- `routing cascade v1` 구현 완료
  - `intent + format_preference` state 분리
  - semantic router fast-path
  - few-shot LLM fallback
- `dev_fast_focus_routing_cascade_2026-04-23` 실행 완료
- `contextual_selective_v2_prefix_2500_320` 결과:
  - `faithfulness 0.925`
  - `answer_relevancy 0.632`
  - `context_recall 0.625`
  - `completeness 0.775`
  - `numeric_pass = 1.000`
- `risk_analysis_001`와 `business_overview_001`는 fast-path가 애매할 때 fallback에서 올바른 intent로 교정됨

다음 단계:

1. semantic router threshold와 margin을 Golden Set 기준으로 보정
2. fallback 로그를 canonical query 세트에 다시 흡수
3. 그 다음에만 generation prompt / validator 추가 튜닝 재개

참고:

- [query_routing_rearchitecture.md](docs/query_routing_rearchitecture.md)

### 1. Answer generation 원칙 정리와 rule inventory 정리

목표:

- 최근 answer-stage rule을 `유지 / 실험용 / 제거 후보`로 분류
- benchmark score와 운영 기본값 최적화를 분리
- answer generation 구조를 “새 내용을 쓰는 단계”가 아니라 “evidence를 질문 범위에 맞게 압축하는 단계”로 재정의

산출물:

- `docs/answer_generation_principles.md`
- 최근 rule inventory와 각 rule의 목적/부작용 메모

### 1-1. Typed compression / validation 검증

목표:

- `compress` / `validate`의 typed output이 실제 benchmark 결과에 유의미하게 남는지 확인
- `business_overview` / `risk` 문항에서
  - 어떤 claim을 선택했는지
  - 어떤 claim을 버렸는지
  - 어떤 문장을 unsupported로 제거했는지
  를 reviewer artifact에서 바로 읽을 수 있게 만들기

산출물:

- `results.json`
- `review.csv`
- `review.md`
  에 아래 필드가 실제로 채워진 run 1회
  - `selected_claim_ids`
  - `draft_points`
  - `kept_claim_ids`
  - `dropped_claim_ids`
  - `unsupported_sentences`
  - `sentence_checks`

현재 상태:

- `dev_fast_cache_check_2026-04-17`에서 typed artifact 기록 자체는 확인했다.
- `dev_fulleval_sentence_validator_2026-04-21`에서 sentence-level validator를 5문항 full eval에 다시 붙여 확인했다.
- `dev_focus_validator_2026-04-21`에서는 실제 prune verdict가 처음으로 의미 있게 발생했다.

현재 문제:

- 5문항 full eval 기준으로는 `dropped_claim_ids`, `unsupported_sentences`가 아직 충분히 많이 생기지 않는다.
- validator가 실제로 자르기 시작했지만, 여전히 claim selection이 과도하거나 애매하면 answer quality가 흔들린다.

다음 작업:

- validator를 더 세게 만드는 것보다 `claim_type` / `topic_key` 기반 selection으로 이동
- `business_overview`, `risk`에서 group-wise claim selection 도입

### 2. Query-stage abstention 분석

대상:

- `numeric_fact`
- `risk_analysis`
- `r_and_d_investment`

목표:

- retrieved docs는 충분한데 answer가 abstain하는 케이스를 분리
- 실제 retrieval miss와 reasoning / prompting miss를 구분
- smoke query failure를 “retrieval failure / evidence failure / analyze failure” 수준으로 다시 분류

### 1-1. Cost-efficient workflow 정착

- `reuse_store`, `reuse_context_cache`, `force_reindex`를 실행 설정으로 명시
- 같은 보고서/동일 청킹 설정 재실행 시 contextual ingest 비용을 다시 쓰지 않게 만들기
- `stores/`와 `context_cache/`를 분리해, store를 다시 만들더라도 API 호출은 재사용할 수 있게 유지
- fast loop에서는 full eval을 기본 비활성화

### 3. NAVER business overview retrieval 개선

현재 관찰:

- NAVER는 parser 보정 후에도 `business_overview_001`이 계속 miss된다.
- 상위 검색 결과가 `I. 회사의 개요`, `IV. 이사의 경영진단 및 분석의견`, `III. 재무에 관한 사항` 쪽으로 편중된다.

목표:

- NAVER에서 실제 사업 설명이 들어 있는 section 우선순위를 다시 정의
- rerank나 section bias 조정이 필요한지 확인
- 다음 run에서 `business_overview_001` miss를 먼저 줄이기

### 4. Missing-information 안정화

현재 관찰:

- NAVER에서 `신규사업 및 중단사업` 질문은 smoke 단계에서 hallucination으로 잡힌다.

목표:

- missing-information prompt / 판정 기준을 점검
- partial limitation과 true missing response를 더 분명히 구분
- “근거 없음” 응답이 citation 없이 단정으로 흐르지 않도록 제어

### 5. 평가 보강

- screening cutoff는 그대로 유지:
  - `retrieval_hit_drop_threshold = 0.10`
  - `section_match_drop_threshold = 0.15`
- critical category는 `risk / business / numeric`로 본다
- 산출물:
  - 기업별 `results.json`, `summary.csv`, `summary.md`, `review.csv`, `review.md`
  - 전체 `cross_company_summary.csv`, `cross_company_summary.md`
- 승자 선정 우선순위를 문서화:
  1. pass count
  2. critical miss 여부
  3. API calls 감소율
  4. ingest 시간 감소율
  5. full eval의 `faithfulness`, `context_recall`
  6. reviewer artifact 정성 검토

### 6. Numeric evaluator 분리

목표:

- `numeric_fact`를 일반 서술형 judge 하나로 채점하지 않기
- 값 동치성, evidence grounding, retrieval support를 분리해서 보기
- false fail을 줄이되, 불확실한 케이스는 `uncertain`으로 남기기

방향:

- `Numeric Extractor`
- `Numeric Equivalence Checker`
- `Grounding Judge`
- `Retrieval Support Check`
- `Conflict Resolver`

참조:

- [numeric_evaluation_architecture.md](docs/numeric_evaluation_architecture.md)

현재 상태:

- `Numeric Extractor`, `Numeric Equivalence Checker`, `Grounding Judge`, `Retrieval Support Check`, `Conflict Resolver`가 `numeric_fact` path에 1차 구현됨
- `results.json`, `review.csv`, `review.md`에 `numeric_equivalence`, `numeric_grounding`, `numeric_retrieval_support`, `numeric_final_judgement`, `numeric_confidence`가 기록됨
- 다음 단계는 이 값을 aggregate / summary / 승자 해석에 더 직접 반영하는 것

### 7. Claim grouping 기반 compression

목표:

- `business_overview`와 `risk`에서 근거가 섞이며 답이 과잉 설명으로 흐르는 문제를 줄이기
- validator가 뒤에서 과하게 자르는 대신, compression 단계에서부터 잘못된 claim 조합을 줄이기

방향:

- evidence에 `claim_type` / `topic_key` 추가
- `business_overview`
  - `DX / DS / SDC / Harman` 대표 claim만 유지
- `risk`
  - 상위 taxonomy claim과 하위 risk item claim을 동시에 다 넣지 않기
- top-N evidence selection 대신 group-wise selection 도입

## 측정 항목

### 품질

- `retrieval_hit_at_k`
- `section_match_rate`
- `citation_coverage`
- `contamination_rate`
- reviewer artifact에서 질문별 정답 근거 추적 가능 여부

### 속도 / 비용

- `ingest.elapsed_sec`
- `api_calls`
- `parent_context_calls`
- `child_context_calls`
- `prompt_tokens`
- `output_tokens`

### 정식 평가

- `faithfulness`
- `answer_relevancy`
- `context_recall`

## 성공 조건

이번 단계의 성공 조건은 “기본값 후보 확정”이 아니라 아래다.

- 삼성전자 2024 기준 단일 문서 Golden Dataset v1이 생길 것
- 질문 taxonomy와 schema가 문서로 고정될 것
- `numeric`, `refusal`, `synthesis`가 서로 다른 evaluator path로 해석될 것
- 이후 retrieval / generation 실험이 이 기준선 위에서만 진행될 것

- 최근 hardcoded answer-stage rule이 어떤 역할을 하는지 문서로 설명 가능할 것
- benchmark-only 최적화와 운영 기본값 후보를 구분하는 기준이 문서에 명시될 것
- NAVER `business_overview_001` miss 원인을 retrieval / reasoning 중 어디인지 분리
- typed validator artifact에서 실제 pruning이 언제, 왜 일어났는지 설명 가능할 것
- 다음 단계가 “validator를 더 세게”가 아니라 “claim selection을 더 구조화”하는 방향으로 정리될 것
- numeric / risk / R&D abstention이 반복되는 대표 케이스 3개 이상을 설명 가능하게 정리
- missing-information hallucination을 유발하는 대표 패턴을 재현 가능하게 문서화
- 위 수정 후 `dev_fast` 기준 재실험으로 적어도 1개 failure type이 줄어드는지 확인
- numeric 질문의 false fail을 answer generation 문제와 evaluator 문제로 분리해 설명 가능할 것

## 현재 상태와 다음 단계

`v4_generalization_fix_2026-04-17`의 실제 결과는 다음과 같다.

- `run_status = completed`
- 3개 기업 공통 screening 통과 후보 없음
- `contextual_all_2500_320`
  - 가장 안정적인 baseline
- `contextual_parent_only_2500_320`
  - 가장 큰 비용 절감
  - 하지만 answerable smoke abstention 반복
- `contextual_selective_v2_2500_320`
  - 의미 있는 비용 절감
  - 하지만 business overview / risk miss 반복
- `contextual_parent_hybrid_2500_320`
  - baseline보다 비싼 경우가 있어 실익이 약함

지금 기준 다음 우선순위는 아래다.

1. query routing 재설계 초안 준비
2. numeric evaluator aggregate / reporting 반영
3. `numeric_final_judgement = PASS`와 generic `faithfulness` 불일치 보정 정책 정리
4. `business_overview` / `risk` generation 프롬프트 및 validator 튜닝
5. typed compression / validation output이 reviewer artifact에서 실제로 해석 가능한지 검증
6. query-stage abstention을 유발하는 evidence / analyze 단계 패턴 점검
7. NAVER business overview retrieval 실패 원인 정리
8. missing-information hallucination 억제
9. 그 다음에 `dev_fast` 기준 재실험
10. 실패 유형이 줄어든 뒤에만 release generalization 재실행
