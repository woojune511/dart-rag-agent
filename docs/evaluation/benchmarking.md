# Benchmarking Guide

이 문서는 **현재 기준의 benchmark 운영 방식**과 **retrospective scorecard 실험 계획/결과**를 정리하는 문서다.  
과거 ingest candidate 실험과 오래된 tuning 기록은 [../history/experiment_history.md](../history/experiment_history.md)로 보낸다.

함께 보면 좋은 문서:
- 단일 문서 기준선: [single_document_eval_strategy.md](single_document_eval_strategy.md)
- metric spec: [evaluation_metrics_v1.md](evaluation_metrics_v1.md)
- Golden dataset schema: [golden_dataset_schema.md](golden_dataset_schema.md)
- answer generation 원칙: [../architecture/answer_generation_principles.md](../architecture/answer_generation_principles.md)

## At a Glance

| 항목 | 현재 기본값 / 원칙 |
| --- | --- |
| baseline 문서 | `삼성전자 2024 사업보고서` |
| 운영 baseline | `contextual_all_2500_320` |
| 빠른 회귀 경로 | `debug-first -> store-fixed eval-only -> full benchmark` |
| math 기준선 | `dev_math_focus` |
| broader sanity check | `dev_fast_focus_selective_serial` |
| scorecard 결과 위치 | 이 문서의 `Retrospective Results` |
| 오래된 실험 로그 위치 | [../history/experiment_history.md](../history/experiment_history.md) |

## 목적

이 프로젝트의 benchmark는 단순히 “점수가 높다”를 보는 용도가 아니다. 현재 목표는 아래 세 가지를 동시에 만족하는 것이다.

| 목표 | 설명 |
| --- | --- |
| 정답성 확인 | retrieval / answer / numeric correctness를 분리해서 본다 |
| 실험 속도 유지 | full re-ingest를 반복하지 않고도 회귀 확인이 가능해야 한다 |
| 설계 결정의 정량적 입증 | 왜 이런 구조를 선택했는지 baseline 대비 수치로 설명할 수 있어야 한다 |

따라서 이 문서는 **현재 운영 guide**와 **retrospective scorecard track**을 함께 다룬다.

## Decision Policy

이 프로젝트에서는 **기술적으로 중요한 결정은 실험 없이 확정하지 않는다.**

| 규칙 | 의미 |
| --- | --- |
| decision-first가 아니라 hypothesis-first | 먼저 “왜 바꾸는가”와 기대 효과를 적는다 |
| baseline/proposed를 분리 | 무엇과 무엇을 비교하는지 명확히 남긴다 |
| metric을 먼저 고른다 | 결과를 보고 지표를 고르지 않는다 |
| artifact를 남긴다 | `summary.md`, `summary.json`, replay/debug trace를 남긴다 |
| 문서까지 닫아야 완료 | `benchmarking.md`와 `DECISIONS.md`에 반영되기 전까진 닫지 않는다 |

즉 새로운 architecture, retrieval, evaluator 결정은 모두  
**실험 설계 -> 실행 -> artifact 기록 -> 해석 문서화** 순서를 통과해야 한다.

## 현재 benchmark 기준

### 기준선 철학

현재 가장 먼저 고정하는 기준선은 **단일 문서 benchmark**다.

| 원칙 | 현재 해석 |
| --- | --- |
| 대표 기준 문서 | `삼성전자 2024 사업보고서` |
| 우선순위 | single-document lab을 먼저 안정화 |
| 확장 순서 | 그 다음에만 multi-company generalization으로 확장 |

이 원칙은 [single_document_eval_strategy.md](single_document_eval_strategy.md)와 일치한다.

### 현재 운영 baseline

현재 대표 baseline은 다음과 같다.

| baseline | 역할 |
| --- | --- |
| `contextual_all_2500_320` | 가장 저렴한 후보가 아니라, 현재까지 가장 안정적인 품질 기준점 |

### 현재 실전적으로 의미 있는 비교 축

오래된 ingest candidate를 전부 이 문서에 나열하지 않는다. 현재 살아 있는 비교 축만 남긴다.

| 비교 축 | 용도 |
| --- | --- |
| `contextual_all_2500_320` | 품질 baseline |
| `contextual_selective_v2_prefix_2500_320` | 저비용 retrieval 후보 |
| `plain + graph expansion` | structure-aware retrieval / graph 구조 실험 |
| `plain + reference_note expansion` | `REFERENCE_NOTE` 확장 효과 검증 |

과거의 `contextual_parent_only`, `contextual_parent_hybrid`, 초기 `selective` 비교는  
현재 guide 문서의 핵심이 아니므로 [../history/experiment_history.md](../history/experiment_history.md)에서 본다.

## 실행 루프

| 단계 | 무엇을 하나 | 주 도구 | 언제 쓰나 |
| --- | --- | --- | --- |
| 1. debug-first | 문제를 benchmark 전에 재현하고 실패 층을 좁힘 | `src/ops/debug_math_workflow.py` | 특정 문항 / 특정 failure mode 분석 |
| 2. screening | 빠른 retrieval / contamination 진단 | benchmark runner with fast profile | 후보를 빠르게 거를 때 |
| 3. store-fixed eval-only | 기존 store 재사용 end-to-end 회귀 | [src/ops/run_eval_only.py](/C:/Users/admin/Desktop/dart-rag-agent/src/ops/run_eval_only.py) | 같은 store에서 current agent/evaluator 회귀 |
| 4. full evaluation | shortlist 후보에 대한 전체 품질 확인 | benchmark runner full eval | release-grade 확인 |

### Screening vs Full Evaluation

| 단계 | 주요 지표 | 어떻게 해석하나 |
| --- | --- | --- |
| Screening | `retrieval_hit_at_k`, `section_match_rate`, `citation_coverage`, `contamination_rate`, latency, ingest / API cost | retriever diagnostic과 비용 |
| Full evaluation | `faithfulness`, `answer_relevancy`, `context_recall`, `completeness`, numeric / math 전용 지표 | 최종 답 품질 |

> 핵심 원칙: screening metric은 **retriever diagnostic**, full evaluation은 **최종 답 품질**이다.

### Store-fixed eval-only fast path

반복 실험에서 full parse / ingest가 병목이므로, 현재는 **store-fixed eval-only 경로**를 적극 사용한다.

| 항목 | 내용 |
| --- | --- |
| 스크립트 | [src/ops/run_eval_only.py](/C:/Users/admin/Desktop/dart-rag-agent/src/ops/run_eval_only.py) |
| 용도 | 기존 store 재사용, current agent/evaluator 전체 회귀, answer/evidence/rendering 회귀 |
| 주의 1 | source output dir는 persisted store가 실제로 들어 있는 결과 번들이어야 한다 |
| 주의 2 | `latest/` 같은 임시 번들은 source로 부적절할 수 있다 |
| 주의 3 | 이 경로는 **같은 answer를 재채점하는 evaluator-only replay가 아니다**. 같은 store를 읽고 current code path를 다시 실행한다 |

> evaluator만 바꿔서 **같은 historical answer / runtime_evidence / calculation trace**를 재판정하려면 `retrospective_*_eval.py` 계열 replay 스크립트를 사용한다.

## 실행 프로파일

현재 기준으로 자주 쓰는 프로파일만 남긴다.

| 프로파일 | 목적 | 주요 대상 | 언제 쓰나 |
| --- | --- | --- | --- |
| `dev_fast` | 빠른 screening | 단일 회사, mixed query | 새 후보를 빠르게 거를 때 |
| `curated_single_doc_core` | curated single-doc core set 점검 | 2023 수동 검수 DART dataset | curated dataset 기준선 회귀 |
| `multi_metric_numeric_smoke` | multi-subtask numeric trace 회귀 | curated multi-metric numeric subset | runtime/evaluator projection 검증 |
| `curated_multi_report_smoke` | multi-report 분리셋 점검 | multi-report curated subset | multi-report path smoke |
| `single_document_graph_micro` | graph / structure-aware retrieval 비교 | 소수 문항 마이크로 실험 | 구조 실험 초기 확인 |
| `release_generalization` | 다기업 일반화 확인 | shortlist 후보 | release-grade 확인 |
| `dev_math_focus` | math / numeric reasoning 기준선 | `comparison`, `ratio`, `growth`, `trend` | 계산 구조 비교 |
| `dev_math_edge_focus` | 엣지 케이스 회귀 | `%p`, ratio row miss, operand shortfall | math regression debug |

## 데이터셋

### Canonical dataset

현재 기본 평가셋은 evidence-backed canonical 형식이다.

| 대표 파일 | 용도 |
| --- | --- |
| `benchmarks/eval_dataset.canonical.json` | 일반 canonical 질문셋 |
| `benchmarks/eval_dataset.math_focus.json` | math focus 질문셋 |
| 기업별 canonical dataset | 확장용 |

| 핵심 필드 | 의미 |
| --- | --- |
| `question` | 평가 질의 |
| `answer_key` | 기대 답 |
| `expected_sections` | retrieval diagnostic용 canonical section |
| `evidence` | answer key를 뒷받침하는 quote |
| `missing_info_policy` | 정보 부족 시 기대 동작 |

원칙:
- 정답은 문자열만 두지 않고 evidence quote를 같이 둔다.
- section 라벨은 retrieval diagnostic을 위한 것이지, 항상 최종 정답 판정 기준은 아니다.

### Curated DART review datasets

최근에는 DART 원문을 직접 검수한 curated dataset이 별도로 정리되었다.

| 파일 | 역할 |
| --- | --- |
| `benchmarks/datasets/single_doc_eval_full.curated.json` | single-document canonical source of truth |
| `benchmarks/datasets/single_doc_eval_multi_subtask.curated.json` | multi-subtask question subset |
| `benchmarks/datasets/single_doc_eval_multi_metric_numeric.curated.json` | multi-metric numeric smoke subset |
| `benchmarks/datasets/multi_report_eval_full.curated.json` | multi-report canonical source of truth |
| `benchmarks/datasets/single_doc_eval_full.json` | question/task oriented working dataset |
| `benchmarks/datasets/multi_report_eval_full.json` | question/task oriented working dataset |

현재 운영 원칙:

- `single_doc_eval_full.curated.json`
  - core/canonical single-document benchmark 후보
  - active row `77`
- `multi_report_eval_full.curated.json`
  - single-document으로 닫히지 않는 질문 분리셋
  - 현재 active row `1` (`SAM_T2_002`)

주의:

- `benchmarks/eval_dataset.canonical.json`, `benchmarks/eval_dataset.math_focus.json`은 여전히 일부 profile / retrospective script에서 사용되는 legacy benchmark asset이다.
- 따라서 당분간은 **curated dataset과 legacy benchmark dataset이 공존**한다.
- 다음 정리 단계는 주력 benchmark/profile을 curated dataset 기준으로 재정렬하는 것이다.

### Multi-metric numeric smoke subset

최근에는 runtime schema projection과 reconciliation regression을 보기 위한 소규모 subset을 별도로 분리했다.

| 파일 | 역할 |
| --- | --- |
| `benchmarks/datasets/single_doc_eval_multi_metric_numeric.curated.json` | 숫자 subtask가 2개 이상인 계산 질문 subset |
| `benchmarks/profiles/multi_metric_numeric_smoke.json` | NAVER 2023 / SK하이닉스 2023 중심 smoke profile |

현재 해석:

- 이 subset은 broad quality benchmark보다 **`matched_operands -> calculation_operands -> aggregate projection`** 경로를 보기 위한 회귀용이다.
- 최근 smoke에서는 retrieval hit은 유지됐고, `SKH_T1_060`은
  - initial refusal
  - unit mismatch
  - current/prior aggregate 혼선
  를 순차적으로 벗어났다.
- 현재 latest direct run은 `25.2%` numeric answer까지 도달하지만, **사채 final aggregate 대신 detail row 0원을 집는 문제**가 남아 있다.
- 따라서 이 subset의 현재 핵심 용도는 retrieval miss보다 **wide note table aggregate binding 회귀**에 더 가깝다.

### Math focus dataset

`dev_math_focus`는 계산 구조 실험의 기준선으로 사용한다.

대표 질문군:
- `comparison`
- `ratio`
- `growth_rate`
- `trend`

## 지표 해석

### 1. 최종 품질 지표

| 지표 | 무엇을 보나 |
| --- | --- |
| `faithfulness` | 답변이 실제 근거에 충실한가 |
| `answer_relevancy` | 질문에 직접 답했는가 |
| `context_recall` | 필요한 근거를 retrieval/evidence가 충분히 회수했는가 |
| `completeness` | 질문이 요구한 핵심 정보를 빠뜨리지 않았는가 |
| `numeric_pass_rate` | numeric 질문에서 최종 PASS 비율 |

이 지표들은 사용자가 실제로 받은 답 품질을 본다.

### 2. retrieval diagnostic 지표

| 지표 | 무엇을 보나 |
| --- | --- |
| `retrieval_hit_at_k` | expected section hit 여부 |
| `section_match_rate` | retrieved set의 section alignment 비율 |
| `context_precision_at_k` | top-k purity |
| `ndcg_at_k` | ranking quality |
| `citation_coverage` | 답변 citation이 기대 섹션을 얼마나 포함하나 |

이 지표들은 **retrieval purity와 section alignment**를 보는 진단용이다.  
최종 정답 판정과 반드시 동일하게 해석하지 않는다.

### 3. numeric / math 지표

| 지표 | 무엇을 보나 |
| --- | --- |
| `numeric_equivalence` | 최종 숫자/표시 단위 기준 정답성 |
| `numeric_grounding` | 답변 숫자가 evidence와 grounded되는가 |
| `numeric_retrieval_support` | 현재는 operand grounding 기반 support |
| `numeric_final_judgement` | numeric 최종 PASS/FAIL |
| `operand_selection_correctness` | 필요한 operand를 제대로 뽑았는가 |
| `unit_consistency_pass` | 단위 정규화가 맞는가 |
| `numeric_result_correctness` | 계산 결과값 자체가 맞는가 |
| `trend_interpretation_correctness` | trend 해석이 맞는가 |
| `grounded_rendering_correctness` | renderer가 없는 숫자를 만들지 않았는가 |
| `calculation_correctness` | math path 전체 correctness |

핵심 원칙:
- generic judge 하나로 숫자 질문을 채점하지 않는다
- 최종 numeric PASS는 **정답성 + grounding** 중심으로 본다
- `retrieval_hit_at_k`는 이제 numeric PASS의 직접 기준이 아니라 retriever diagnostic이다

## Reviewer artifacts

결과 검수는 단순 summary만으로 끝내지 않는다.

| artifact | 용도 |
| --- | --- |
| `summary.md` | 빠른 실행 결과 요약 |
| `review.md` | 사람이 읽는 상세 리뷰 |
| `review.csv` | 질문별 정리 |
| `results.json` | 기계적으로 재분석 가능한 전체 결과 |
| `compact_review.md` | 압축된 리뷰 |
| `compact_review.html` | 시각적으로 보기 쉬운 리뷰 |

특히 아래 필드는 answer debugging에 중요하다.

| 필드 | 용도 |
| --- | --- |
| `runtime_evidence` | 실제 사용된 evidence 확인 |
| `selected_claim_ids` / `kept_claim_ids` / `dropped_claim_ids` | claim selection 흐름 추적 |
| `unsupported_sentences` / `sentence_checks` | answer faithfulness 디버그 |
| `calculation_operands` / `calculation_plan` / `calculation_result` | math path 디버그 |

## 캐시 정책

기본 캐시 정책은 `Hybrid Cache`다.

| 설정 | 현재 기본값 |
| --- | --- |
| `reuse_store` | `true` |
| `reuse_context_cache` | `true` |
| `force_reindex` | `false` |

캐시는 두 층으로 나뉜다.

| 계층 | 의미 |
| --- | --- |
| `stores/...` | persisted retrieval / vector artifacts |
| `context_cache/...` | contextual ingest / context generation cache |

즉 같은 보고서 / 같은 청킹 / 같은 ingest mode면 context 생성 비용을 다시 쓰지 않는다.

## MAS Migration Smokes

이 섹션은 retrospective ablation이 아니라, **기존 single-agent 자산을 MAS worker / orchestrator로 안전하게 이식했는지 보는 migration acceptance check**다.

### Analyst wrapper smoke

| 항목 | 내용 |
| --- | --- |
| 목적 | `FinancialAgent.run()`을 MAS Analyst worker로 감쌌을 때 numeric parity가 유지되는지 확인 |
| 스크립트 | [src/ops/mas_analyst_smoke.py](/C:/Users/admin/Desktop/dart-rag-agent/src/ops/mas_analyst_smoke.py) |
| store | `reference-note-plain-graph-2500-320` on `삼성전자 2024` |
| 질문 | `comparison_001`, `comparison_004`, `trend_002` |
| 주요 결과 | `calc_status_match_rate = 1.000`, `numeric_result_match_rate = 1.000`, `operand_count_match_rate = 0.667`, `answer_match_rate = 0.333` |
| 해석 | exact wording은 흔들리지만 계산 결과와 계산 상태는 direct engine과 MAS wrapper가 일치했다. 즉 Analyst migration은 **numeric correctness를 유지한 채 task ledger / artifact store로 옮겨졌다**. |
| Evidence | [mas_analyst_smoke_2026-04-30.json](/C:/Users/admin/Desktop/dart-rag-agent/benchmarks/results/mas_analyst_smoke_2026-04-30.json) |

### Researcher wrapper smoke

| 항목 | 내용 |
| --- | --- |
| 목적 | scoped narrative retrieval + summarization core가 MAS Researcher worker로 이식됐는지 확인 |
| 스크립트 | [src/ops/mas_researcher_smoke.py](/C:/Users/admin/Desktop/dart-rag-agent/src/ops/mas_researcher_smoke.py) |
| store | `reference-note-plain-graph-2500-320` on `삼성전자 2024` |
| 질문 | `business_overview_001`, `risk_analysis_001`, `r_and_d_investment_002` |
| 주요 결과 | `citation_match_rate = 1.000`, `evidence_link_nonempty_rate = 1.000`, `critic_pass_rate = 1.000`, `answer_match_rate = 0.333` |
| 해석 | citation과 grounding wiring은 direct narrative core와 MAS wrapper가 일치했다. answer wording/quality는 아직 tuning 여지가 있지만, **Researcher migration과 deterministic critic 연동 자체는 성공**했다. |
| Evidence | [mas_researcher_smoke_2026-04-30.json](/C:/Users/admin/Desktop/dart-rag-agent/benchmarks/results/mas_researcher_smoke_2026-04-30.json) |

### E2E MAS smoke

| 항목 | 내용 |
| --- | --- |
| 목적 | real `Orchestrator + Analyst + Researcher + Critic + Merge`가 mixed-intent 질의에서 끝까지 한 바퀴 도는지 확인 |
| 스크립트 | [src/ops/mas_e2e_smoke.py](/C:/Users/admin/Desktop/dart-rag-agent/src/ops/mas_e2e_smoke.py) |
| 질의 수 | `2` |
| 주요 결과 | final report 생성 `2/2`, critic pass 최종 `2/2`, critic-triggered analyst retry 관측 `1/2` |
| 해석 | MAS는 이제 문서상 topology가 아니라, **task decomposition -> parallel workers -> critic retry -> merge**를 실제로 수행하는 baseline이 됐다. 이후 품질 개선은 이 baseline 대비 delta로 측정한다. |
| Evidence | [mas_e2e_smoke_2026-04-30.json](/C:/Users/admin/Desktop/dart-rag-agent/benchmarks/results/mas_e2e_smoke_2026-04-30.json) |

## Parser Structure Smokes

이 섹션은 retrieval/generation 품질이 아니라, **DART 원문 구조를 parser가 얼마나 복원하는지**를 보는 acceptance check다.

### NAVER 2023 hidden-heading recovery smoke

| 항목 | 내용 |
| --- | --- |
| 목적 | `SECTION-*` 밖에 숨어 있는 bold sub-heading을 `local_heading`으로 복원하고, parser가 어디까지 구조를 잃는지 확인 |
| 스크립트 | [src/ops/dump_report_structure.py](/C:/Users/admin/Desktop/dart-rag-agent/src/ops/dump_report_structure.py) |
| 산출물 | [naver_2023_structure_outline.json](/C:/Users/admin/Desktop/dart-rag-agent/benchmarks/results/naver_2023_structure_outline.json) |
| 성공 신호 | sanitize 이후 `IV. 이사의 경영진단 및 분석의견`과 `II > 7. 기타 참고사항`의 핵심 hidden heading이 soft `local_heading`으로 복원 |
| 실패 신호 | noisy inline heading이 일부 남거나, low-value section에서 coarse parsing 대신 오탐 heading이 늘어나는 경우 |
| 해석 | parser는 deep hierarchy 복원기보다, sanitize + high-value-section soft heading 복원기 쪽이 RAG 목적에 더 적합함 |

핵심 결론:

- 하위 섹션이 `SECTION-*`가 아니라 bold `SPAN`에 숨어 있는 경우는 soft `local_heading` 복원으로 충분한 경우가 많다
- raw source 안의 `<소매판매액 ...>` 같은 **텍스트성 angle bracket**는 sanitize가 먼저 막아야 한다
- low-value section까지 세세하게 복원하려고 들수록 parser 복잡도와 오탐이 커지므로, 다음 parser 실험은 **high-value-section whitelist + conservative heading** 기준으로 본다

### Parser Chunk Smoke

parser 구조 정리 이후에는 실제 chunk 분포도 같이 본다.

최근 smoke 기준:

| 문서 | chunks | avg chars | max chars | `over2500` |
| --- | --- | ---: | ---: | ---: |
| NAVER 2023 | 258 | 1215.9 | 2500 | 0 |
| 삼성전자 2024 | 356 | 1641.8 | 2500 | 0 |
| SK하이닉스 2023 | 245 | 1030.6 | 2498 | 0 |
| POSCO홀딩스 2023 | 668 | 1111.3 | 2500 | 0 |

해석:

- wide table은 `column window -> row split`으로 처리
- `1. 분할방법 | ...` 같은 서술형 표 row는 label-value narrative split을 적용
- parser baseline의 남은 검증 과제는 oversized chunk 해소가 아니라, 질문 subset 기준 retrieval / numeric 회귀 확인이다

## Retrospective Scorecard Track

이 섹션은 **이미 내린 중요한 기술 결정이 정량적으로 어떤 차이를 만들었는지**를 회고적으로 입증하기 위한 실험 트랙이다.

질문:
- 왜 direct LLM calc가 아니라 `formula planner + AST`가 필요했는가?
- 왜 일반 semantic retrieval만으로는 부족했고 ontology retrieval이 필요했는가?
- 왜 section hit evaluator 대신 operand grounding evaluator가 필요했는가?

### 실험 설계 원칙

1. 결정 하나당 하나의 가설
2. 시스템 품질 실험과 evaluator 메타-실험 분리
3. 가능한 한 같은 store / 같은 question set / 같은 evaluator 유지
4. 결과는 `baseline -> proposed` delta로 기록
5. 중요한 결정은 raw artifact와 curated scorecard를 둘 다 남긴다

### 핵심 retrospective 실험 3개

| 실험 | 목적 | baseline | proposed | 벤치셋 | 주요 지표 |
| --- | --- | --- | --- | --- | --- |
| `Direct Calc vs Operation Path vs Formula Planner + AST` | direct calc와 rule calc의 한계를 보여주고 formula planner의 가치를 입증 | direct-calc RAG, operation-based math path | formula planner + safe AST | `dev_math_focus` | `numeric_pass`, `calculation_correctness`, 단위/포맷 오류 수 |
| `Standard Retrieval vs Ontology-Guided Retrieval` | 일반 semantic retrieval의 source miss를 보이고 ontology retrieval의 operand 회수율 복구를 검증 | ontology off | ontology-guided retrieval on | `comparison_005`, `comparison_006`, 추가 ratio 질문 | `operand_grounding_score`, `retrieval_hit_at_k`, `ratio_row_candidates > 0`, `numeric_pass` |
| `Section Match Evaluator vs Operand Grounding Evaluator` | section match evaluator의 false negative를 줄이는지 검증 | `expected_sections` 기반 numeric support | operand grounding 기반 numeric support | small adjudication set | false negative rate, human adjudication alignment, `numeric_final_judgement` stability |

### 권장 실행 순서

1. `Section Match Evaluator vs Operand Grounding Evaluator`
2. `Direct Calc vs Operation Path vs Formula Planner + AST`
3. `Standard Retrieval vs Ontology-Guided Retrieval`

### Scorecard 산출물 형식

| 필드 | 의미 |
| --- | --- |
| `Decision` | 어떤 설계 결정을 검증했는가 |
| `Benchmark` | 어떤 질문셋 / 결과 번들을 사용했는가 |
| `Baseline` | 무엇과 비교했는가 |
| `Proposed` | 현재 구조는 무엇인가 |
| `Primary metric delta` | 가장 중요한 수치 변화 |
| `Secondary metric delta` | 보조 지표 변화 |
| `Runtime / cost delta` | 비용 변화가 있다면 기록 |
| `Interpretation` | 왜 이런 결과가 나왔는가 |
| `Kept / Reverted / Ambiguous` | 최종 판단 |

## Retrospective Results

이 섹션은 **실제로 완료된 retrospective experiment**를 scorecard 형태로 누적 기록하는 곳이다.  
raw artifact는 각 run directory의 `summary.md`, `summary.json`, `results.json`에 남기고, 여기에는 빠르게 읽을 수 있는 해석만 압축해 적는다.

### Result 1. `Section Match Evaluator -> Operand Grounding Evaluator`

| 항목 | 내용 |
| --- | --- |
| Decision | numeric support 판정을 `expected_sections` 기반 section hit 중심에서, 실제 계산에 사용한 operand의 grounded 여부 중심으로 재정의 |
| Type | evaluator meta-experiment |
| Source bundle | [dev_math_focus_evalonly_2026-04-28](/C:/Users/admin/Desktop/dart-rag-agent/benchmarks/results/dev_math_focus_evalonly_2026-04-28/삼성전자-2024/results.json) |
| Replay script | [src/ops/retrospective_operand_grounding_eval.py](/C:/Users/admin/Desktop/dart-rag-agent/src/ops/retrospective_operand_grounding_eval.py) |
| Adjudication set | positive-only 8문항 (`comparison_001`, `comparison_002`, `comparison_004`, `trend_002`, `trend_003`, `comparison_005`, `comparison_006`, `comparison_007`) |
| Excluded | `comparison_003` (`display-aware equivalence` 영향 혼입), `trend_001` (`numeric_final_judgement` 없음) |
| Primary metric | human-correct numeric questions 기준 false negative rate |
| Result | `0.125 -> 0.000`, recovered case: `comparison_001` |
| Interpretation | section-based support는 같은 숫자가 다른 유효 섹션에 있을 때 억울한 FAIL을 만들 수 있었다. operand grounding support는 금융 문서처럼 수치가 여러 섹션에 반복되는 도메인에서 사람 판정과 더 잘 맞는다. |
| Evidence | [retrospective summary.md](/C:/Users/admin/Desktop/dart-rag-agent/benchmarks/results/retrospective_operand_grounding_2026-04-29/summary.md), [retrospective summary.json](/C:/Users/admin/Desktop/dart-rag-agent/benchmarks/results/retrospective_operand_grounding_2026-04-29/summary.json) |

### Result 2. `Direct Calc -> Formula Planner + AST`

| 항목 | 내용 |
| --- | --- |
| Decision | 수치 질문에서 LLM이 직접 계산한 답을 쓰게 하지 않고, LLM은 수식 planner 역할만 맡기고 실제 연산은 symbolic executor(AST)로 분리 |
| Type | system architecture retrospective experiment |
| Source bundle | [dev_math_focus_evalonly_operandgrounding_v2_2026-04-29](/C:/Users/admin/Desktop/dart-rag-agent/benchmarks/results/dev_math_focus_evalonly_operandgrounding_v2_2026-04-29/삼성전자-2024/results.json) |
| Replay script | [src/ops/retrospective_math_architecture_eval.py](/C:/Users/admin/Desktop/dart-rag-agent/src/ops/retrospective_math_architecture_eval.py) |
| Slice | numeric-only 9문항 (`comparison_001`~`comparison_007`, `trend_002`, `trend_003`) |
| Excluded | `trend_001` (정성적 추이 서술형) |
| Primary metric | strict correctness rate (`numeric_equivalence == 1.0` and `numeric_grounding == 1.0`) |
| Result | direct calc `0.556`, formula planner + AST `1.000`, delta `+0.444` |
| Secondary metrics | direct calc equivalence `0.556`, grounding `0.778`; formula+AST equivalence / grounding `1.000 / 1.000`; legacy operation-path overlap `0.500` |
| Interpretation | retrieval과 evidence는 고정한 채 answer generation만 바꿨을 때, direct calc baseline은 9문항 중 4문항에서 단위/표현/부호 처리에 흔들렸다. 같은 evidence 기반에서 formula planner + AST 경로는 9문항을 모두 통과했다. |
| Representative failures | `comparison_002` `43조 4,327억원 -> 475,963억원`, `comparison_003` `81조 9,082억원 -> 819,082 백만원`, `comparison_004` `10.9% -> 10.88%`, `trend_003` `-24.55% 변했습니다` |
| Evidence | [retrospective summary.md](/C:/Users/admin/Desktop/dart-rag-agent/benchmarks/results/retrospective_math_architecture_2026-04-29/summary.md), [retrospective summary.json](/C:/Users/admin/Desktop/dart-rag-agent/benchmarks/results/retrospective_math_architecture_2026-04-29/summary.json) |

### Result 3. `Standard Retrieval -> Ontology-Guided Retrieval`

| 항목 | 내용 |
| --- | --- |
| Decision | retrieval-side ontology hook (`preferred_sections`, `supplement_sections`, `query_hints`)을 사용해 ratio/percent 질문의 source miss를 보완 |
| Type | system retrieval retrospective experiment |
| Source bundle | [dev_math_focus_evalonly_operandgrounding_v2_2026-04-29](/C:/Users/admin/Desktop/dart-rag-agent/benchmarks/results/dev_math_focus_evalonly_operandgrounding_v2_2026-04-29/삼성전자-2024/results.json) |
| Replay script | [src/ops/retrospective_ontology_retrieval_eval.py](/C:/Users/admin/Desktop/dart-rag-agent/src/ops/retrospective_ontology_retrieval_eval.py) |
| Slice | `comparison_004`, `comparison_005`, `comparison_006` |
| Ablation scope | ontology retrieval hook만 on/off. planner prior와 evaluator는 고정 |
| Primary metrics | `operand_grounding_score`, `calc_success_rate`, `row_candidate_recovery_rate` |
| Result | grounding `0.500 -> 1.000`, calc success `0.333 -> 1.000`, row recovery `0.000 -> 0.667` |
| Secondary metrics | section match `0.458 -> 0.583`, avg operand count `1.000 -> 1.667`, component recovery `0.333 -> 0.333` |
| Interpretation | 일반 semantic retrieval은 정답 section을 스쳐도 `연구개발활동` row를 놓쳐 ratio 질문이 `insufficient_operands`로 끝났다. ontology-guided retrieval은 `연구개발활동` / `연구개발실적` 계열 seed를 보강해 ratio row 회수와 최종 계산 성공을 복구했다. |
| Representative recoveries | `comparison_005`: `rows 0 -> 1`, `calc insufficient_operands -> ok`; `comparison_006`: `rows 0 -> 1`, `operands 0 -> 2`, `calc insufficient_operands -> ok` |
| Evidence | [retrospective summary.md](/C:/Users/admin/Desktop/dart-rag-agent/benchmarks/results/retrospective_ontology_retrieval_2026-04-29/summary.md), [retrospective summary.json](/C:/Users/admin/Desktop/dart-rag-agent/benchmarks/results/retrospective_ontology_retrieval_2026-04-29/summary.json) |

### Result 4. `Evaluator sub-decision replay audit (Decisions 73 / 75 / 76)`

| 항목 | 내용 |
| --- | --- |
| Decision | early evaluator 결정 중 `eval-only` 재실행 근거에 기대던 항목을 fixed historical output replay로 재검증 |
| Type | evaluator meta-experiment / evidence-quality audit |
| Source bundle | [dev_math_focus_evalonly_datasetfix_2026-04-29](/C:/Users/admin/Desktop/dart-rag-agent/benchmarks/results/dev_math_focus_evalonly_datasetfix_2026-04-29/삼성전자-2024/results.json) |
| Replay script | [src/ops/retrospective_evaluator_ablation_eval.py](/C:/Users/admin/Desktop/dart-rag-agent/src/ops/retrospective_evaluator_ablation_eval.py) |
| Slice | `comparison_001`, `comparison_004`, `trend_002`, `comparison_005` |
| Primary finding 1 | `comparison_001` strict equivalence `0.0 -> 1.0` |
| Primary finding 2 | `comparison_004` legacy label matcher `0.0 -> 1.0` |
| Primary finding 3 | `trend_002`, `comparison_005` operand override 전 `0.0 -> 1.0` |
| Interpretation | 결정 75와 76의 핵심 효과는 fixed historical outputs에서도 재현된다. 반면 결정 73은 “전역 1e-4 tolerance” 자체보다 현재의 `display-aware equivalence`가 durable fix라는 점이 더 정확했다. |
| Evidence | [retrospective summary.md](/C:/Users/admin/Desktop/dart-rag-agent/benchmarks/results/retrospective_evaluator_ablation_2026-04-30/summary.md), [retrospective summary.json](/C:/Users/admin/Desktop/dart-rag-agent/benchmarks/results/retrospective_evaluator_ablation_2026-04-30/summary.json) |

## 이 문서에 더 이상 쌓지 않을 것

아래 내용은 이 문서에서 계속 늘리지 않는다.

- 오래된 ingest candidate별 세부 실험 로그
- 날짜별 validator 메모 누적
- 과거 candidate matrix 전체 회고

이런 기록은 [../history/experiment_history.md](../history/experiment_history.md)와 benchmark artifact 자체로 남긴다.

## 실행 예시

fast iteration:

```bash
python -m src.ops.benchmark_runner --config benchmarks/profiles/dev_fast.json
```

eval-only 회귀:

```bash
python -m src.ops.run_eval_only --config benchmarks/profiles/dev_math_focus.json --source-output-dir benchmarks/results/dev_math_focus_llmshift_2026-04-28 --output-dir benchmarks/results/dev_math_focus_evalonly_example --company-run-id samsung_2024
```

retrospective evaluator replay:

```bash
python -m src.ops.retrospective_operand_grounding_eval --source-results benchmarks/results/dev_math_focus_evalonly_2026-04-28/삼성전자-2024/results.json --output-dir benchmarks/results/retrospective_operand_grounding_2026-04-29
```

retrospective math architecture replay:

```bash
python -m src.ops.retrospective_math_architecture_eval --source-results benchmarks/results/dev_math_focus_evalonly_operandgrounding_v2_2026-04-29/삼성전자-2024/results.json --dataset-path benchmarks/eval_dataset.math_focus.json --legacy-operation-results benchmarks/results/dev_math_focus_2026-04-27/삼성전자-2024/results.json --output-dir benchmarks/results/retrospective_math_architecture_2026-04-29
```

retrospective ontology retrieval replay:

```bash
python -m src.ops.retrospective_ontology_retrieval_eval --source-results benchmarks/results/dev_math_focus_evalonly_operandgrounding_v2_2026-04-29/삼성전자-2024/results.json --output-dir benchmarks/results/retrospective_ontology_retrieval_2026-04-29
```

retrospective evaluator sub-decision replay:

```bash
python -m src.ops.retrospective_evaluator_ablation_eval --source-results benchmarks/results/dev_math_focus_evalonly_datasetfix_2026-04-29/삼성전자-2024/results.json --dataset benchmarks/eval_dataset.math_focus.json --output-dir benchmarks/results/retrospective_evaluator_ablation_2026-04-30
```
