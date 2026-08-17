# 프로젝트 컨텍스트

> 새 세션에서 현재 상태를 2분 안에 파악하기 위한 handoff다. 현재 제품 상태,
> 검증, blocker와 우선순위의 단일 기준은
> [project_status.md](docs/overview/project_status.md)다. 세부 runtime 동작은
> [agent_runtime_contract.md](docs/architecture/agent_runtime_contract.md), 완료된 변경은
> [implementation_history.md](docs/history/implementation_history.md)를 따른다.

Last updated: 2026-08-18

## 현재 범위

- 제품은 DART 공시를 분석하는 single-agent `FinancialAgent`다.
- 핵심 흐름은 구조 보존 ingest, dense/BM25 hybrid retrieval, LLM semantic
  planning, deterministic calculation, evidence/provenance validation이다.
- MAS, report-cache promotion, evaluator, benchmark runner와 review workflow는
  optional 또는 experimental surface다.
- 범용 agent, broad web workflow, productivity-tool 확장은 현재 범위가 아니다.

## 현재 checkpoint

| 항목 | 현재 상태 |
| --- | --- |
| Source checkpoint | local code checkpoint `ca2969b` on `codex/finalize-five-minute-review`; 이 handoff 문서 commit과 이후 변경은 `git log`로 확인 |
| Public numeric contract | `resolved_calculation_trace`, explicit `structured_result`, task/artifact projection |
| Default runtime boundary | MAS/eval/benchmark/promotion/cache 구현은 unconfigured import/invocation에서 격리 |
| Calculation ownership | graph-state orchestrator와 state-free owner들로 분리 중; runtime/ontology deterministic planning은 `financial_calculation_execution.py`, semantic-planner shape/segment/task validation과 narrative-task policy projection은 `financial_graph_helpers.py`, query/task/operand/report period·single-report-scope와 candidate period/table coherence policy는 `financial_scope_policies.py`, generic operation-family/numeric-grounding policy는 `financial_operation_policies.py`, structured-cell selection/scoring과 candidate selected-cell preparation은 `financial_structured_cells.py`, candidate concept-conflict·contextual-aggregate preference·note-aggregate lookup preference·balance-sheet aggregate-operand·CAPEX total-operand와 surface/segment/metadata policy projection은 `financial_surface_contracts.py`, row text·column-candidate label·delta-like row-label·aggregate-like row 및 candidate value-role/stage·candidate operand-context/structured-sibling·segment-local/segment-metric composition·sibling-surface hit count는 `financial_row_surfaces.py`, lookup-hint projection/match·direct candidate logical/family signature·candidate location/entity subject score·deterministic positional preference bonus·candidate source-priority score·complete operand-candidate scoring·candidate-to-operand matching·candidate direct-match strength·direct candidate semantic priority·canonical-statement winner·ratio-component acceptance·direct-grounding 및 direct-acceptance classification과 operand resolution은 `financial_operand_resolution.py`, aggregate calculation/public projection·bounded repair·quantitative-impact parsing/composition은 `financial_aggregate_projection.py`, read-only focus/section/compression 및 query-to-metric/operand match projection은 `financial_retrieval_hints.py`, collapsed-ratio evidence repair는 `financial_runtime_trace.py`, direct structured lookup과 lookup answer-slot/support projection은 `financial_lookup_recovery.py`, nested result projection은 `financial_answer_projection.py`, query-focus/source-visible text projection은 `financial_text_surface.py`, caller-facing run projection은 `financial_agent_run_projection.py`, prepared candidate와 structured period-pair projection은 `financial_reconciliation_candidates.py`, reflection retry-query projection은 `financial_reflection_projection.py`에 귀속 |
| Phase 3 | OPEN; query/task/operand period-focus, single-report-scope, candidate period/table coherence와 concept-conflict·contextual-aggregate preference·note-aggregate lookup preference·balance-sheet aggregate-operand·CAPEX total-operand, location/entity subject score, deterministic positional preference bonus·source-priority score·complete operand-candidate scoring·candidate-to-operand matching·candidate direct-match strength·direct candidate semantic priority·canonical-statement winner·ratio-component acceptance·direct-grounding 및 direct-acceptance classification, column-candidate/delta-like row-label classification, structured-cell selection/scoring과 candidate selected-cell preparation, candidate report/period-scope, candidate surface-contract/segment-binding, candidate metadata-policy, segment-local/segment-metric, aggregate-like row와 candidate value-role/stage 및 operand-context/structured-sibling, lookup-hint projection/match, direct candidate logical/family signature, sibling-surface hit-count와 query-to-metric/operand match ownership까지 수렴했지만 reconciliation candidate construction/ranking, broader alignment/rebuild와 ledger ownership 전체는 미완료 |
| Runtime correctness | 알려진 unit/contract blocker 없음; 최신 수치는 [Current Gate Status](docs/overview/project_status.md#current-gate-status) 참조 |
| Benchmark | 최신 코드에 대한 refresh 상태는 [Project Status](docs/overview/project_status.md#current-gate-status)만 기준으로 사용 |

## 남은 Phase 3 범위

세부 우선순위는 [Next Work](docs/overview/project_status.md#next-work)가 단일 기준이다.
현재 durable debt는 다음 네 범주다.

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
3. bounded read-only reconciliation artifact-reference projection까지만 진행된 broader
   task/artifact ledger synchronization; artifact mutation과 whole-ledger sync는 제외
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
exact-deletion/owner/caller/DAG parity가 통과했다. 다음 characterize-only
inventory는 operation-policy owner의 정확한 12줄
`_is_percent_point_difference_query(...)`을 public
`is_percent_point_difference_query(...)`로 이름 수렴시킨다. 정확한 계약과
projected gate는
[Next Work](docs/overview/project_status.md#next-work)가 단일 기준이다.

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
