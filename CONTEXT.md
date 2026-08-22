# 프로젝트 컨텍스트

> 새 세션에서 현재 상태를 2분 안에 파악하기 위한 handoff다. 현재 제품 상태,
> 검증, blocker와 우선순위의 단일 기준은
> [project_status.md](docs/overview/project_status.md)다. 세부 runtime 동작은
> [agent_runtime_contract.md](docs/architecture/agent_runtime_contract.md), 완료된 변경은
> [implementation_history.md](docs/history/implementation_history.md)를 따른다.

Last updated: 2026-08-22

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
| Source checkpoint | local code checkpoint `f77bd87` on `codex/finalize-five-minute-review`; 이 handoff 문서 commit과 이후 변경은 `git log`로 확인 |
| Public numeric contract | `resolved_calculation_trace`, explicit `structured_result`, task/artifact projection |
| Default runtime boundary | MAS/eval/benchmark/promotion/cache 구현은 unconfigured import/invocation에서 격리 |
| Calculation ownership | graph-state orchestrator와 state-free owner들로 분리 중; runtime/ontology deterministic planning은 `financial_calculation_execution.py`, semantic-planner shape/segment/task validation과 narrative-task policy projection은 `financial_graph_helpers.py`, desired consolidation-scope와 query/task/operand/report period·single-report-scope·strict-company-scope·report-source receipt·year-token projection 및 candidate period/table coherence policy는 `financial_scope_policies.py`, generic operation-family/numeric-grounding policy는 `financial_operation_policies.py`, structured-cell selection/scoring과 candidate selected-cell preparation은 `financial_structured_cells.py`, candidate concept-conflict·contextual-aggregate preference·note-aggregate lookup preference·balance-sheet aggregate-operand·CAPEX total-operand와 surface/segment/metadata policy projection은 `financial_surface_contracts.py`, row text·column-candidate label·delta-like row-label·aggregate-like row 및 candidate value-role/stage·candidate operand-context/structured-sibling·segment-local/segment-metric composition·sibling-surface hit count는 `financial_row_surfaces.py`, lookup-hint projection/match·direct candidate logical/family signature·candidate location/entity subject score·deterministic positional preference bonus·candidate source-priority score·complete operand-candidate scoring·candidate-to-operand matching·candidate direct-match strength·direct candidate semantic priority·canonical-statement winner·ratio-component acceptance·direct-grounding 및 direct-acceptance classification과 operand resolution은 `financial_operand_resolution.py`, aggregate calculation/public projection·bounded repair·quantitative-impact parsing/composition은 `financial_aggregate_projection.py`, read-only focus/section/compression 및 query-to-metric/operand match projection은 `financial_retrieval_hints.py`, structured-result subtask-row/answer projection·nested-result evidence collection과 collapsed-ratio evidence repair는 `financial_runtime_trace.py`, direct structured lookup과 lookup answer-slot/support projection은 `financial_lookup_recovery.py`, nested result와 preferred complete aggregate-answer selection은 `financial_answer_projection.py`, query-focus/source-visible text projection은 `financial_text_surface.py`, caller-facing run projection은 `financial_agent_run_projection.py`, prepared candidate와 structured period-pair projection은 `financial_reconciliation_candidates.py`, reflection retry-query projection은 `financial_reflection_projection.py`에 귀속 |
| Phase 3 | OPEN; desired consolidation-scope, query/task/operand period-focus, single-report-scope, candidate period/table coherence와 concept-conflict·contextual-aggregate preference·note-aggregate lookup preference·balance-sheet aggregate-operand·CAPEX total-operand, location/entity subject score, deterministic positional preference bonus·source-priority score·complete operand-candidate scoring·candidate-to-operand matching·candidate direct-match strength·direct candidate semantic priority·canonical-statement winner·ratio-component acceptance·direct-grounding 및 direct-acceptance classification, column-candidate/delta-like row-label classification, structured-cell selection/scoring과 candidate selected-cell preparation, candidate report/period-scope, candidate surface-contract/segment-binding, candidate metadata-policy, segment-local/segment-metric, aggregate-like row와 candidate value-role/stage 및 operand-context/structured-sibling, lookup-hint projection/match, direct candidate logical/family signature, sibling-surface hit-count와 query-to-metric/operand match ownership까지 수렴했지만 reconciliation candidate construction/ranking, broader alignment/rebuild와 ledger ownership 전체는 미완료 |
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
686.355 seconds가 통과했다. 다음 batch는 exact 29-line
`financial_graph_retrieval_budget._store_query_result_cache(...)`를 public
`store_query_result_cache(...)`로 rename하고 pipeline import 한 개, call 세
개와 `_retrieve` 파생 hash 기대 네 개만 갱신한다. Exact temporary projection
source/tests/whole `+5/-5`, `+4/-4`, `+9/-9`, current/projected direct/identity
각 12/12, exact structural 2/2, focused 370/370 in 24.968 seconds 경계는
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
