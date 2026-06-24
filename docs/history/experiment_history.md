# Experiment History

> Internal experiment log, not a first-read portfolio document. Start with
> [../../README.md](../../README.md) and
> [../overview/portfolio_experiment_report.md](../overview/portfolio_experiment_report.md)
> for the compressed experiment story. This file preserves detailed historical
> runs and should stay append-oriented.

이 문서는 benchmark와 retrieval 파이프라인이 버전별로 어떻게 바뀌었는지, 그리고 그때 실험 결과가 어떻게 달라졌는지를 한 번에 보기 위한 기록이다.

## At a Glance

| 항목 | 현재 해석 |
| --- | --- |
| 문서 역할 | append-only experiment log |
| 읽는 순서 | `큰 흐름 -> Timeline Index -> 필요한 버전 상세` |
| 초기 국면 | 저비용 ingest 후보 탐색과 다기업 일반화 검증 |
| 중간 전환 | retrieval 문제와 generation 문제를 분리해서 보기 시작 |
| 최근 전환 | single-document benchmark와 evaluator를 먼저 고정 |
| raw artifact 위치 | 각 버전 디렉터리의 `summary.md`, `results.json`, `cross_company_summary.md` |

## Timeline Index

| 버전 / 단계 | 무엇을 검증했나 | 핵심 takeaway |
| --- | --- | --- |
| [v1 Legacy Local Test](#v1-legacy-local-test) | 초기 low-cost ingest 후보 비교 | `contextual_all`만 안정적인 baseline으로 남음 |
| [v2 Low-Cost Retrieval](#v2-low-cost-retrieval) | parent/selective/hybrid 저비용 retrieval | 비용 절감 가능성은 보였지만 single-doc 한계 존재 |
| [v3 Generalization](#v3-generalization) | 삼성전자 -> 다기업 일반화 | single-company winner가 cross-company winner가 아님 |
| [v4 Generalization Fix](#v4-generalization-fix) | parser / evaluation 보정 후 재검증 | ingest 비용보다 query-stage miss와 abstention이 더 큰 문제로 드러남 |
| [dev_fast Cache Check](#dev_fast-cache-check) | 빠른 반복 실험 루프 점검 | cache 기반 반복 속도 개선 확인 |
| [Graph Micro + Zero-Cost Prefix (2026-04-22)](#graph-micro--zero-cost-prefix-2026-04-22) | graph / zero-cost prefix 실험 | 구조 그래프의 가능성과 한계를 함께 확인 |
| [v5 / v6 / v7 Faithfulness Follow-up](#v5--v6--v7-faithfulness-follow-up) | faithfulness 흔들림 원인 추적 | retrieval보다 answer synthesis 문제가 큼 |
| [Typed Compression / Validation and Sentence-Level Validator](#typed-compression--validation-and-sentence-level-validator) | generation을 compression 문제로 재정의 | free-form generation보다 structured pipeline이 유리 |
| [Numeric Evaluator Follow-up](#numeric-evaluator-follow-up) | 숫자 질문 평가 문제 정리 | generic faithfulness만으로는 부족 |
| [Numeric Evaluator Implementation](#numeric-evaluator-implementation) | numeric evaluator 1차 구현 | numeric path를 별도 evaluator/resolver로 분리 |
| [Typed Compression / Validation Outputs](#typed-compression--validation-outputs) | structured output artifact 보강 | debugging/traceability 향상 |
| [Reset Point: Single-Document Evaluation First](#reset-point-single-document-evaluation-first) | 방향 재정렬 | single-document benchmark와 evaluator를 먼저 고정 |
| [Prefix + Selective Contextual Retrieval Focus Run (2026-04-23)](#prefix--selective-contextual-retrieval-focus-run-2026-04-23) | selective/prefix retrieval 재평가 | source miss와 routing 연계 문제 확인 |
| [Evaluator + Routing Cascade v1 (2026-04-23)](#evaluator--routing-cascade-v1-2026-04-23) | evaluator + routing 구조 개편 | query routing을 cascade로 재구성 |
| [Routing Calibration + Ambiguity Guard (2026-04-24)](#routing-calibration--ambiguity-guard-2026-04-24) | ambiguity guard / calibration | routing variance를 줄이는 쪽으로 이동 |
| [Numeric Extractor Node (2026-04-26)](#numeric-extractor-node-2026-04-26) | numeric generation path 분리 | numeric 질문은 extractor 기반 path가 더 안정적 |
| [Concept Gate Focused Hardening (2026-06-08)](#concept-gate-focused-hardening-2026-06-08) | POS/KBF/KAB focused eval-only residual과 후속 full replay 확인 | ratio peer-unit binding, growth+narrative repair, narrative-summary aggregate guard 이후 monitored full 7 eval-only가 7 / 7 PASS |
| [KAB_T1_066 CIR Direct-Support And Coherent Ratio Close (2026-06-09)](#kab_t1_066-cir-direct-support-and-coherent-ratio-close-2026-06-09) | KAB CIR denominator support, coherent ratio operands, source display rendering | 최종 답변이 `4,355억원 / 11,623억원 = 37.47%`로 source-visible하게 닫힘 |
| [Expanded Structural Ablation Refresh (2026-06-10)](#expanded-structural-ablation-refresh-2026-06-10) | 9문항 structural-vs-plain ablation | structural은 numeric `1.000`, plain은 `0.833`; `KBF_T1_017`, `SKH_T3_080`가 separating numeric failures |
| [Hard Numeric Runtime Closure (2026-06-11)](#hard-numeric-runtime-closure-2026-06-11) | 5문항 hard numeric replay | ROE average-equity, margin-drag aggregate binding, late ratio refresh 이후 hard set 5 / 5 numeric PASS |
| [Hard Structural-vs-Plain Replay (2026-06-11)](#hard-structural-vs-plain-replay-2026-06-11) | 같은 hard set의 structural vs plain 비교 | structural 5 / 5, plain 4 / 5; `SKH_T1_060` row binding이 separating failure |
| [Curated Single-Doc Core Full Eval (2026-06-12)](#curated-single-doc-core-full-eval-2026-06-12) | 삼성/네이버/현대차 15문항 broader eval-only | all companies error `0.0%`, faithfulness/completeness `1.000`; exclusive narrative loop fixed |
| [CEL_T1_038 Unit and Final Answer Consistency (2026-06-12)](#cel_t1_038-unit-and-final-answer-consistency-2026-06-12) | margin-drag focused regression | claim-visible `원` unit is preserved through lookup capture, late ratio projection, and query-focused final answer selection |
| [Financial Graph Calculation Refactor Focused Eval (2026-06-15)](#financial-graph-calculation-refactor-focused-eval-2026-06-15) | aggregate/projection refactor after repeated patching | SKI/POS PASS cases stayed stable; HYU self-ratio regression is blocked and remaining gap is operand binding/table structure |
| [HYU Ratio Task-Output Rebinding (2026-06-15)](#hyu-ratio-task-output-rebinding-2026-06-15) | HYU_T1_034 late denominator task-output binding | focused eval-only recovered `83.81%` ratio and returned numeric PASS |
| [HYU Source-Slot Ratio Rebuild (2026-06-16)](#hyu-source-slot-ratio-rebuild-2026-06-16) | HYU_T1_034 incoherent ratio candidate suppression and source-slot fallback | lookup/single-value source slots rebuild `83.81%` answer; focused eval-only numeric PASS |
| [SKI Source-Stated Growth Repair and Narrative Pruning (2026-06-16)](#ski-source-stated-growth-repair-and-narrative-pruning-2026-06-16) | SKI_T2_069 aggregate period-comparison repair and boilerplate context pruning | source-stated `84.3%` display is preserved; focused eval-only numeric PASS and irrelevant forward-looking boilerplate removed |
| [KBF Aggregate Public Answer Projection Closure (2026-06-17)](#kbf-aggregate-public-answer-projection-closure-2026-06-17) | KBF_T2_018 mixed numeric+narrative public answer projection | supported aggregate `formatted_result` survives public answer projection; focused eval-only numeric PASS |
| [Expanded Ablation Refresh After KBF Projection Fix (2026-06-17)](#expanded-ablation-refresh-after-kbf-projection-fix-2026-06-17) | 9문항 structural-vs-plain ablation refresh | structural 7 / 9, plain 4 / 9; `SAM_T3_028`, `CEL_T1_013`, `SKH_T3_080` separate |
| [Post-Refactor Expanded Structural Refresh (2026-06-18)](#post-refactor-expanded-structural-refresh-2026-06-18) | operand filtering cleanup 이후 9문항 structural full-system refresh | structural improved to 8 / 9; only `SKH_T1_060` remains numeric FAIL |
| [Post-Refactor Expanded Plain Refresh (2026-06-18)](#post-refactor-expanded-plain-refresh-2026-06-18) | 같은 코드 상태의 9문항 plain retrieval refresh | plain improved to 5 / 9; current comparison is structural 8 / 9 vs plain 5 / 9 |
| [Post-Refactor Operand Filtering Separator Smoke (2026-06-18)](#post-refactor-operand-filtering-separator-smoke-2026-06-18) | required-operand candidate/filtering cleanup 이후 focused separator smoke | `SAM_T3_028` and `CEL_T1_013` remained numeric PASS with source-scale answers |
| [Structured Operand Evidence Alignment Regression (2026-06-18)](#structured-operand-evidence-alignment-regression-2026-06-18) | structured operand/evidence realignment commit 이후 7문항 broader focused regression | `KAB`, `POS`, `SAM`, `CEL`, `KBF`, `SKH` hard cases all stayed numeric PASS; residual is trace/completeness quality |
| [Aggregate Numeric Trace Hygiene Hard Set (2026-06-19)](#aggregate-numeric-trace-hygiene-hard-set-2026-06-19) | aggregate trace sync and final-answer numeric hygiene 이후 5문항 hard replay | `POS`, `SAM`, `CEL`, `KBF`, `SKH` all PASS; KBF unsupported numeric sentence and SKH stale lookup display removed |
| [SKH_T1_060 Structured Subtask Projection Closure (2026-06-19)](#skh_t1_060-structured-subtask-projection-closure-2026-06-19) | expanded structural residual의 trace/answer consistency fix | focused rerun passes `42.02%`; full 9-question structural refresh still pending before changing aggregate claim |
| [KBF_T2_018 Supported Aggregate Narrative Repair (2026-06-19)](#kbf_t2_018-supported-aggregate-narrative-repair-2026-06-19) | full structural refresh after SKH fix exposed a supported aggregate final-answer precedence bug | full run is `8 / 9`; focused KBF repair passes with `70.28%`; rerun full structural before claiming fresh `9 / 9` |
| [Expanded Structural Numeric-Surface Conflict Closure (2026-06-22)](#expanded-structural-numeric-surface-conflict-closure-2026-06-22) | takeout-restored structural full-system eval-only after aggregate projection hardening | focused KBF guard and full 9-question structural refresh both pass; structural is now `9 / 9` numeric PASS |
| [Post-Cleanup Runtime Numeric Projection Refresh (2026-06-24)](#post-cleanup-runtime-numeric-projection-refresh-2026-06-24) | post-PR #77 cleanup and `1d78b31` numeric projection regression fix after store-fixed full replay | expanded structural remains `9 / 9` numeric PASS; KB completeness residual keeps cross-company full-eval fail count at `1` |
| [KB Period-Difference Rendering Closure (2026-06-24)](#kb-period-difference-rendering-closure-2026-06-24) | focused follow-up for the KB completeness residual from the post-cleanup replay | KB 2-question eval-only now has numeric `2 / 2` PASS and completeness `1.000` |
| [Focused Numeric Projection Closure Follow-up (2026-06-24)](#focused-numeric-projection-closure-follow-up-2026-06-24) | CEL/KAB/KBF focused regressions after ratio/dependency repairs | CEL and KAB focused rows PASS; KB focused pair is `2 / 2` numeric PASS after weak unit-repaired task output no longer blocks coherent direct period rows |
| [Final Financial Operand Projection Repair (2026-06-24)](#final-financial-operand-projection-repair-2026-06-24) | KBF stale growth projection and SKH disjoint-source table-label overwrite after the focused closure | focused KBF/SKH rows PASS; full six-company 9-question eval-only is `9 / 9` numeric PASS |
| [Growth Narrative Payload / Rendering Judge Compaction (2026-06-15)](#growth-narrative-payload--rendering-judge-compaction-2026-06-15) | NAV/KBF growth narrative canaries after numeric refresh | KBF grounded-rendering token overflow was removed by compact runtime evidence and judge payload projection |
| [Runtime Cost-Control Diagnostics (2026-06-09)](#runtime-cost-control-diagnostics-2026-06-09) | phase usage, prompt-size diagnostics, numeric extraction history canary | aggregate prompt 축소 후 다음 병목은 duplicate numeric extraction / failed lookup retry loop로 확인 |
| [MAS Smoke Outcome Refresh (2026-06-07)](#mas-smoke-outcome-refresh-2026-06-07) | live/default MAS smoke outcome 관측 | acceptance contract는 선명해졌고, valid default-store compact contract는 source-controlled baseline으로 고정 |

## 보는 법

| 섹션 | 무엇을 보면 되나 |
| --- | --- |
| `코드 / 설정 변화` | 무엇을 바꿨는지 |
| `핵심 결과` | 어떤 후보가 좋아졌거나 실패했는지 |
| `해석` | 왜 다음 버전으로 넘어갔는지 |

상세 원본 결과는 각 버전 디렉터리의 `results.json`, `summary.md`, `cross_company_summary.md`를 참고한다.

## Final Financial Operand Projection Repair (2026-06-24)

참조:

- active branch / PR:
  - `codex/repair-financial-operands`
  - `https://github.com/woojune511/dart-rag-agent/pull/78`
- commits:
  - `fafe639 fix: repair financial operand projection`
  - `c3d234a test: cover financial operand regressions`
- local result bundle:
  - `benchmarks/results/ablation_expanded_candidate_full_system_2026-06-10/`
- heartbeat logs:
  - focused KBF:
    `benchmarks/results/ablation_expanded_candidate_full_system_2026-06-10/heartbeat_kbf_t2_final_trace_sync_retry_2026-06-24.jsonl`
  - focused SKH:
    `benchmarks/results/ablation_expanded_candidate_full_system_2026-06-10/heartbeat_skh_t1_periodless_table_label_retry_2026-06-24.jsonl`
  - final full 9Q:
    `benchmarks/results/ablation_expanded_candidate_full_system_2026-06-10/heartbeat_full9_final_after_kbf_skh_repairs_2026-06-24.jsonl`
- artifact hygiene: result bundles and heartbeat logs are local experiment
  output and should not be staged.

### Context

- The preceding focused numeric projection closure closed CEL/KAB/KBF
  regressions, but the next full replay still exposed two hard residuals:
  - `KBF_T2_018`: the final answer/evidence carried the correct current value,
    prior value, and growth rate, but the public calculation trace could remain
    stale.
  - `SKH_T1_060`: aggregate ratio subtasks had the correct task-output values,
    but direct evidence repair could overwrite a source-backed task output with
    a conflicting row from a disjoint source context.
- Both failures were projection/provenance contract problems, not missing
  financial vocabulary.

### Failure Layer

| Question | Layer | Root cause |
| --- | --- | --- |
| `KBF_T2_018` | projection / rendering trace | final-answer surface operands were not synchronized back into `calculation_result`, `calculation_plan`, and `answer_slots` when the projected growth trace was stale |
| `SKH_T1_060` | operand extraction / aggregate subtask repair | table-label lookup did not strip leading period markers for row-label matching, and direct evidence repair did not protect task-output operands from disjoint conflicting source rows |

### Code / Contract Change

- Public result projection now calls
  `_append_final_answer_surface_operands_from_evidence()` before debug/citation
  projection so final-answer numeric surfaces are preserved in the runtime
  calculation trace.
- Final-answer surface operand repair now:
  - backfills missing non-percent projected operands from final-answer/evidence
    numeric components;
  - syncs stale growth-rate trace fields when current/prior operands calculate
    to the percent already visible in the final answer.
- Table-label metadata lookup now:
  - marks `table_label_metadata_lookup` slots;
  - derives periodless surface variants from
    `CALCULATION_SLOT_POLICY["leading_period_strip_pattern"]`;
  - can prefer exact table-label metadata on ties with structured rows from the
    same evidence.
- Aggregate task-output ratio repair now protects a source slot when the
  preferred direct evidence slot has disjoint source-row ids and conflicting
  values.
- Regression tests pin the KBF growth trace sync and SKH table-label /
  disjoint-source repair behavior.
- No company names, benchmark IDs, or metric-specific runtime branches were
  added.

### Focused Results

| Run | Command scope | Result |
| --- | --- | --- |
| KBF focused replay | `--company-run-id kbf_2023_expanded_candidate --question-id KBF_T2_018` | `KBF_T2_018` numeric final judgement `PASS`; current `3,146,409`, prior `1,847,775`, growth `70.28%` |
| SKH focused replay | `--company-run-id skh_2023_expanded_candidate --question-id SKH_T1_060` | `SKH_T1_060` numeric final judgement `PASS`; short-term borrowings `4,145,647`, ratio `42.02%` |

Focused command pattern:

```bash
python3 -m src.ops.benchmark_runner \
  --config benchmarks/profiles/curated_ablation_expanded_candidate_full_system.json \
  --output-dir benchmarks/results/ablation_expanded_candidate_full_system_2026-06-10 \
  --company-run-id <company_run_id> \
  --question-id <question_id> \
  --eval-only \
  --progress-heartbeat-sec 60 \
  --heartbeat-log benchmarks/results/ablation_expanded_candidate_full_system_2026-06-10/<heartbeat>.jsonl
```

### Final Full Replay

Command:

```bash
python3 -m src.ops.benchmark_runner \
  --config benchmarks/profiles/curated_ablation_expanded_candidate_full_system.json \
  --output-dir benchmarks/results/ablation_expanded_candidate_full_system_2026-06-10 \
  --eval-only \
  --progress-heartbeat-sec 60 \
  --heartbeat-log benchmarks/results/ablation_expanded_candidate_full_system_2026-06-10/heartbeat_full9_final_after_kbf_skh_repairs_2026-06-24.jsonl
```

Per-question numeric final judgement:

| Company bundle | Questions |
| --- | --- |
| `kb금융-2023` | `KBF_T2_018: PASS`, `KBF_T1_017: PASS` |
| `posco홀딩스-2023` | `POS_T1_057: PASS` |
| `sk하이닉스-2023` | `SKH_T3_080: PASS`, `SKH_T1_060: PASS` |
| `삼성전자-2023` | `SAM_T3_028: PASS`, `MIX_T1_021: PASS` |
| `셀트리온-2023` | `CEL_T1_013: PASS` |
| `카카오뱅크-2023` | `KAB_T1_066: PASS` |

Final result: expanded structural six-company, nine-question store-fixed
`eval-only` replay is `9 / 9` numeric final judgement PASS.

### Validation

- `python3 -m unittest tests.test_structured_operand_extraction tests.test_subtask_loop`:
  `274` tests OK.
- `python3 -m src.ops.audit_runtime_domain_terms`: passed with `215`
  reviewed literals.
- `git diff --check`: passed.
- `python3 -m unittest discover -s tests`: `1345` tests OK.
- Full 9-question store-fixed `eval-only`: `9 / 9` numeric PASS.

### Interpretation

- The latest expanded structural numeric gate is again closed by a fresh full
  replay, not only by focused follow-up rows.
- The repair follows the numeric regression methodology:
  - failure layers were classified before patching;
  - fixes were expressed as projection, table-label, and provenance contracts;
  - focused rows were closed before the full replay;
  - raw benchmark artifacts remain local-only.

## Focused Numeric Projection Closure Follow-up (2026-06-24)

### Context

- After the period-difference rendering closure, focused probes exposed two
  numeric projection regressions:
  - complete task-output ratio values could lose to conflicting direct detail
    rows from a retrieved same-table context;
  - a period-comparison prior operand whose original unit was missing could be
    KRW-repaired from alternate table surface text and then block the coherent
    direct row from the actual multi-period table.
- A separate lookup gap came from fiscal ordinal headers such as `제16기` /
  `제15기` not being classified as period columns in table-label metadata
  lookup.

### Code / Contract Change

- Added fiscal-period header detection to `CALCULATION_SLOT_POLICY` and made
  table-label lookup consume it generically.
- Narrowed dependency retrieval override:
  - same-value or materially compatible sibling-context candidates can still
    replace task output;
  - stale `0` task output and KRW display-unit mismatch can be repaired by
    sibling table context;
  - same-unit conflicting task outputs remain protected.
- Task-output ratio append now:
  - synthesizes bindings from `depends_on + required_operands` when explicit
    `inputs` are absent;
  - uses operand-set artifacts to repair answer-slot value/unit conflicts;
  - realigns count-like task-output slots from the sibling result unit when the
    source display unit is KRW.
- Period-comparison conflict blocking no longer treats an
  `alternate_table_krw_surface` repair with no original source unit as stronger
  than coherent direct period rows.

### Results

- Focused `CEL_T1_013` eval-only:
  - numeric final judgement `PASS`
  - faithfulness `1.000`
  - completeness `1.000`
  - numeric pass rate `1.000`
- Focused `KAB_T1_066` eval-only:
  - numeric final judgement `PASS`
  - numeric pass rate `1.000`
- Focused KB금융 2-question eval-only:
  - `KBF_T2_018`: numeric final judgement `PASS`
  - `KBF_T1_017`: numeric final judgement `PASS`
  - combined numeric pass rate `1.000`
  - faithfulness `1.000`
  - completeness `0.850`
  - error rate `0.0%`

### Validation

- `python3 -m unittest discover -s tests`: `1332` tests OK.
- `python3 -m unittest tests.test_subtask_loop tests.test_operation_contracts tests.test_lookup_recovery_policy`:
  `497` tests OK.
- `python3 -m src.ops.audit_runtime_domain_terms`: passed with `215`
  reviewed literals.
- `git diff --check`: passed.

### Interpretation

- The focused regressions are closed without adding company names, benchmark
  IDs, or metric-specific runtime branches.
- Full six-company `9Q` was not rerun after this focused closure. The latest
  full aggregate claim remains the earlier 2026-06-24 `9 / 9` numeric PASS
  refresh, plus the focused closures recorded here.

## KB Period-Difference Rendering Closure (2026-06-24)

참조:

- local result bundle:
  - `benchmarks/results/ablation_expanded_candidate_full_system_2026-06-10/kb금융-2023/`
- heartbeat logs:
  - focused NIM check:
    `benchmarks/results/ablation_expanded_candidate_full_system_2026-06-10/heartbeat_kbf_t1_017_period_difference_rendering_2026-06-24.jsonl`
  - focused KB two-question check:
    `benchmarks/results/ablation_expanded_candidate_full_system_2026-06-10/heartbeat_kbf_after_period_difference_rendering_2026-06-24.jsonl`
- artifact hygiene: result bundles and heartbeat logs are local experiment
  output and should not be staged.

### Setup

- Focused follow-up after the 2026-06-24 post-cleanup full replay left a
  KB금융 completeness residual.
- The residual question was `KBF_T1_017`: numeric judgement was PASS, but the
  public answer omitted explicit `2022년` wording, omitted direction, and used
  an exclusion-style phrase for a period comparison.

### Results

| Run | Scope | Result | Key detail |
| --- | --- | --- | --- |
| Focused NIM check | `KBF_T1_017` | PASS | Completeness improved to `1.000`; answer renders `2022년 ... 대비 ... 상승`. |
| Focused KB company check | `KBF_T2_018`, `KBF_T1_017` | numeric `2 / 2` PASS | Completeness `1.000`, faithfulness `1.000`, error rate `0.0%`. |

Representative fixed answer:

- `KB금융 2023년 순이자마진은 1.83%입니다. 2022년 순이자마진 1.73% 대비 순이자마진(NIM) 증감폭은 0.1% 상승했습니다.`

### Code / Contract Change

- Failure layer: aggregate answer rendering.
- Deterministic difference rows already carried structured period-comparison
  slots: `current_value`, `prior_value`, `delta_value`, and `direction`.
- Runtime now renders that slot shape through a dedicated
  period-comparison-difference policy template instead of the generic
  exclusion/subtraction template.
- Direction words and sentence fragments live in `CALCULATION_RENDER_POLICY`,
  not in runtime control-flow literals.

### Validation

- `python3 -m unittest tests.test_operation_contracts tests.test_subtask_loop`:
  `477` OK.
- `python3 -m src.ops.audit_runtime_domain_terms`: passed with `215` reviewed
  literals.
- `git diff --check`: passed.

### Interpretation

- The KB residual from the post-cleanup full replay is closed in focused
  company validation.
- A fresh six-company 9-question replay is only needed if the project needs a
  new cross-company aggregate table after this focused rendering fix.

## Post-Cleanup Runtime Numeric Projection Refresh (2026-06-24)

참조:

- local result bundle:
  - `benchmarks/results/ablation_expanded_candidate_full_system_2026-06-10/`
- heartbeat log:
  - `benchmarks/results/ablation_expanded_candidate_full_system_2026-06-10/heartbeat_full_9q_after_runtime_numeric_projection_fix_2026-06-24.jsonl`
- source commit:
  - `1d78b31 Fix runtime numeric projection regressions`
- artifact hygiene: result bundles and heartbeat logs are local experiment
  output and should not be staged.

### Setup

- Store-fixed structural full-system `eval-only` over the expanded 9-question
  profile after the PR #77 post-merge runtime-surface cleanup and the
  `1d78b31` numeric projection regression fix.
- Profile:
  `benchmarks/profiles/curated_ablation_expanded_candidate_full_system.json`
- Command:
  `python3 -m src.ops.benchmark_runner --config benchmarks/profiles/curated_ablation_expanded_candidate_full_system.json --output-dir benchmarks/results/ablation_expanded_candidate_full_system_2026-06-10 --eval-only --progress-heartbeat-sec 60 --heartbeat-log benchmarks/results/ablation_expanded_candidate_full_system_2026-06-10/heartbeat_full_9q_after_runtime_numeric_projection_fix_2026-06-24.jsonl`

### Results

| Scope | Result | Detail |
| --- | --- | --- |
| Full expanded structural refresh | `9 / 9` numeric PASS | Six companies completed, no pending companies. |
| Winner ranking | `structural_selective_v2_prefix_2500_320` | `avg_full_numeric_pass_rate=1.000`, `avg_full_completeness=0.958`, `avg_full_faithfulness=1.000`, `avg_full_context_recall=0.900`. |
| Cross-company full eval | `full_eval_fail_count=1` | KB금융 completeness remains `0.750`; numeric pass rate and faithfulness are both `1.000`. |

Company-level aggregate metrics:

| Company | Questions | Numeric | Completeness | Faithfulness | Recall |
| --- | ---: | ---: | ---: | ---: | ---: |
| 카카오뱅크 2023 | 1 | 1.000 | 1.000 | 1.000 | 1.000 |
| POSCO홀딩스 2023 | 1 | 1.000 | 1.000 | 1.000 | 1.000 |
| 삼성전자 2023 | 2 | 1.000 | 1.000 | 1.000 | 1.000 |
| 셀트리온 2023 | 1 | 1.000 | 1.000 | 1.000 | 0.667 |
| KB금융 2023 | 2 | 1.000 | 0.750 | 1.000 | 0.833 |
| SK하이닉스 2023 | 2 | 1.000 | 1.000 | 1.000 | 0.900 |

### Interpretation

- The cleanup and `1d78b31` projection fix did not regress the expanded
  structural numeric gate: the current source baseline still clears all nine
  numeric final judgements.
- The remaining cross-company full-eval failure is not numeric correctness. It
  is a KB금융 completeness residual, so follow-up work should inspect the public
  answer and evidence/projection trace for missing explanatory coverage before
  changing retrieval or calculator code.
- Further refactoring should be tied to named owner-boundary work from
  `docs/architecture/core_runtime_surface_refactoring_plan.md`; blind
  line-count reduction is no longer the next useful step.

## Expanded Structural Numeric-Surface Conflict Closure (2026-06-22)

참조:

- local result bundle:
  - `benchmarks/results/ablation_expanded_candidate_full_system_2026-06-10/`
- heartbeat logs:
  - focused KBF guard:
    `benchmarks/results/ablation_expanded_candidate_full_system_2026-06-10/heartbeat_kbf_t2_018_numeric_surface_conflict_guard_2026-06-22.jsonl`
  - full structural closure:
    `benchmarks/results/ablation_expanded_candidate_full_system_2026-06-10/heartbeat_full_structural_after_numeric_surface_conflict_guard_2026-06-22.jsonl`
- artifact hygiene: result bundles and heartbeat logs are local experiment
  output and should not be staged.

### Setup

- Store-fixed structural full-system `eval-only` over the expanded 9-question
  profile restored from the 2026-06-19 takeout artifacts.
- Profile:
  `benchmarks/profiles/curated_ablation_expanded_candidate_full_system.json`
- The triggering failure was `KBF_T2_018`: a public answer could contain both a
  conflicting weak numeric prefix (`3,146억원 / 1,299억원 / 142.19%`) and the
  supported aggregate narrative (`3,146,409백만원 / 1,847,775백만원 / 70.28%`).

### Results

| Run | Scope | Result | Key detail |
| --- | --- | --- | --- |
| Focused conflict guard | `KBF_T2_018` | PASS | Same unstable path produced intermediate `142.19%`, but final answer kept the clean aggregate `70.28%` answer. |
| Live commit comparison | `HEAD=6557f50` vs `HEAD~1=66b8cc2`, focused `KBF_T2_018` | both PASS | Non-deterministic planning/retrieval meant this live score comparison did not isolate the fix. |
| Deterministic projection ablation | same synthetic aggregate state on both commits | `HEAD` PASS, `HEAD~1` FAIL | The old runtime left the conflicting `142.19%` numeric prefix in the public answer; the new runtime selected the clean aggregate answer. |
| Full structural refresh | 9 expanded questions | `9 / 9` PASS | All expanded structural numeric final judgements passed. |

Passing rows:

- `KAB_T1_066`
- `POS_T1_057`
- `SAM_T3_028`
- `MIX_T1_021`
- `CEL_T1_013`
- `KBF_T2_018`
- `KBF_T1_017`
- `SKH_T3_080`
- `SKH_T1_060`

### Code / Contract Change

- Failure layer: final-answer projection for mixed growth+narrative aggregate
  answers, not retrieval or evaluator normalization.
- Runtime now lets a clean aggregate/narrative candidate replace the current
  public answer when:
  - it shares enough numeric surfaces with the current public answer, and
  - the current public answer contains more conflicting numeric claims than the
    candidate introduces.
- This is a generic numeric-surface consistency guard. No company name,
  benchmark ID, report phrase, or metric-specific runtime branch was added.

### Validation

- `python3 -m unittest tests.test_financial_agent_run_projection tests.test_benchmark_runner_runtime_projection tests.test_subtask_loop`:
  `300` tests OK.
- `python3 -m unittest discover -s tests`: `1275` tests OK.
- `python3 -m src.ops.audit_runtime_domain_terms`: passed with `215` reviewed
  literals.

### Interpretation

- The earlier `8 / 9 + focused KBF closure` caveat is now resolved for this
  structural profile: the latest full structural replay is `9 / 9` numeric
  PASS.
- Remaining work should shift from patching this row to code ownership cleanup:
  isolate aggregate answer projection / runtime trace projection from the
  larger graph helper surface.

## KBF_T2_018 Supported Aggregate Narrative Repair (2026-06-19)

참조:

- local result bundle:
  - `benchmarks/results/ablation_expanded_candidate_full_system_2026-06-10/`
- heartbeat logs:
  - full structural refresh:
    `benchmarks/results/ablation_expanded_candidate_full_system_2026-06-10/heartbeat_full_structural_after_projection_fix_2026-06-19.jsonl`
  - focused repair check:
    `benchmarks/results/ablation_expanded_candidate_full_system_2026-06-10/heartbeat_kbf_t2_018_supported_aggregate_fix_2026-06-19.jsonl`
- artifact hygiene: result bundles and heartbeat logs are local experiment
  output and should not be staged.

### Setup

- Store-fixed structural full-system `eval-only` over the expanded 9-question
  profile after the `SKH_T1_060` projection fix.
- Profile:
  `benchmarks/profiles/curated_ablation_expanded_candidate_full_system.json`

### Results

| Run | Scope | Result | Key detail |
| --- | --- | --- | --- |
| Full structural refresh | 9 expanded questions | `8 / 9` PASS | only `KBF_T2_018` failed; `SKH_T1_060` passed at `42.02%` |
| Focused repair check | `KBF_T2_018` | PASS | answer preserved `3,146,409백만원`, `1,847,775백만원`, and `70.28%` |

Focused repair metrics:

| Question | Result | Faithfulness | Completeness | Context recall | Context P@5 | Latency |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| `KBF_T2_018` | PASS | `1.000` | `1.000` | `0.667` | `1.000` | `306.3s` |

### Code / Contract Change

- Failure layer: final-answer precedence in mixed growth+narrative aggregation.
- The failed full run emitted a spurious final answer using
  `100만원 / 5,400만원 / 98.15% 감소`, but the same structured result already
  contained a supported `aggregate_subtasks` narrative answer with
  `3,146,409백만원 / 1,847,775백만원 / 70.28% 증가`.
- Runtime now compares final-answer numeric surfaces against a supported
  `aggregate_subtasks` narrative answer. If the current final answer is
  numerically incompatible with that supported aggregate, the supported
  aggregate becomes the final answer.
- The comparison is generic numeric-surface equivalence. No company name,
  benchmark ID, report-specific phrase, or metric-specific runtime branch was
  added.

### Validation

- Focused growth/projection regression set: `6` tests OK.
- `python -m src.ops.audit_runtime_domain_terms`: passed with `215` reviewed
  literals.
- `python -m unittest discover -s tests`: `1271` tests OK.

### Interpretation

- The completed full structural run remains `8 / 9` because it happened before
  this KBF repair.
- The only failing row from that run passes focused store-fixed eval-only after
  the repair.
- Rerun the full 9-question structural profile before publishing a fresh full
  `9 / 9` aggregate claim.

## SKH_T1_060 Structured Subtask Projection Closure (2026-06-19)

참조:

- local result bundle:
  - `benchmarks/results/ablation_expanded_candidate_full_system_2026-06-10/`
- heartbeat log:
  - `benchmarks/results/ablation_expanded_candidate_full_system_2026-06-10/heartbeat_skh_t1_060_trace_projection_fix_2026-06-19.jsonl`
- artifact hygiene: result bundles and heartbeat logs are local experiment
  output and should not be staged.

### Setup

- Store-fixed structural full-system `eval-only` focused rerun for
  `SKH_T1_060`.
- This followed a 2026-06-19 expanded structural run where the other eight
  expanded questions passed, while `SKH_T1_060` was `UNCERTAIN`.
- Pre-fix 9-question heartbeat log:
  `benchmarks/results/ablation_expanded_candidate_full_system_2026-06-10/heartbeat_full_structural_after_trace_hygiene_2026-06-19.jsonl`.
- Profile:
  `benchmarks/profiles/curated_ablation_expanded_candidate_full_system.json`

### Code / Contract Change

- The failure layer was not evidence retrieval: the final public answer and
  `structured_result` already reported the source-supported `42.02%`.
- The problem was stale runtime projection: `resolved_calculation_trace` could
  retain an intermediate aggregate lookup operand (`9,857,189백만원`) even when
  structured subtask outputs had corrected the public answer.
- Runtime projection now rebuilds the resolved trace from structured subtask
  outputs when the public answer matches the structured subtask result.
- Numeric slot visibility now recognizes compact KRW display surfaces, so
  `4조 1,456억원` in a public answer can match the canonical slot
  `4,145,647백만원`.
- This stays within the generic runtime contract. No company name, benchmark
  ID, or metric-specific branch was added.

### Results

| Question | Result | Answer | Faithfulness | Completeness | Context recall | Context P@5 | Latency |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: |
| `SKH_T1_060` | PASS | `42.02%` | `1.000` | `1.000` | `1.000` | `1.000` | `353.7s` |

### Interpretation

- This closes the focused residual exposed by the expanded structural refresh.
- It should not yet be reported as a fresh full structural `9 / 9` aggregate,
  because the full 9-question structural profile has not been rerun after this
  patch.
- Next benchmark step: rerun the structural expanded 9-question store-fixed
  `eval-only` profile. Plain retrieval remains `5 / 9` until a source change
  affects plain projection/scoring enough to justify rerunning it.
- Validation:
  - `python -m src.ops.audit_runtime_domain_terms`
  - `python -m unittest tests.test_benchmark_runner_runtime_projection.BenchmarkRunnerRuntimeProjectionTests.test_serialise_eval_results_reprojects_structured_subtasks_when_operands_are_stale tests.test_benchmark_runner_runtime_projection.BenchmarkRunnerRuntimeProjectionTests.test_serialise_eval_results_keeps_structured_runtime_contract`
  - `python -m unittest tests.test_benchmark_runner_runtime_projection tests.test_financial_agent_run_projection tests.test_aggregate_subtask_projection`

## Aggregate Numeric Trace Hygiene Hard Set (2026-06-19)

참조:

- commit: `e3a1eb1` (`Harden aggregate numeric trace hygiene`)
- local result bundle:
  - `benchmarks/results/ablation_expanded_candidate_full_system_2026-06-10/`
- heartbeat log:
  - `benchmarks/results/ablation_expanded_candidate_full_system_2026-06-10/heartbeat_hard_set_after_growth_filter_2026-06-19.jsonl`
- artifact hygiene: result bundles and heartbeat logs are local experiment
  output and should not be staged.

### Setup

- Store-fixed structural full-system `eval-only` focused replay after aggregate
  arithmetic trace synchronization and final-answer numeric hygiene changes.
- Profile:
  `benchmarks/profiles/curated_ablation_expanded_candidate_full_system.json`
- Scope:
  - `POS_T1_057`
  - `SAM_T3_028`
  - `CEL_T3_040`
  - `KBF_T2_018`
  - `SKH_T3_080`

### Code / Contract Change

- Aggregate lookup surface synchronization now propagates corrected lookup
  slots into nested mirrors such as `series`, `components_by_role`,
  `components_by_group`, `current_value`, and `derived_metrics`.
- Final growth answers with a strong calculation trace now drop numeric
  sentences whose numeric surfaces are not supported by the resolved growth
  trace. This is a generic trace/evidence hygiene rule, not a company,
  benchmark ID, or metric-specific branch.
- The guard is intentionally limited to strong growth traces so a weak or
  stale growth row cannot overwrite a better supported aggregate answer.

### Results

| Question | Result | Avg score | Faithfulness | Completeness | Context recall | Context P@5 | Latency |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `POS_T1_057` | PASS | `0.961` | `1.000` | `1.000` | `1.000` | `1.000` | `254.0s` |
| `SAM_T3_028` | PASS | `0.945` | `1.000` | `0.700` | `1.000` | `1.000` | `206.6s` |
| `CEL_T3_040` | PASS | `0.848` | `1.000` | `1.000` | `0.333` | `0.667` | `255.8s` |
| `KBF_T2_018` | PASS | `0.880` | `1.000` | `1.000` | `0.667` | `1.000` | `267.2s` |
| `SKH_T3_080` | PASS | `0.942` | `1.000` | `1.000` | `1.000` | `1.000` | `257.3s` |

### Interpretation

- The focused hard set is `5 / 5` numeric PASS after the trace hygiene changes.
- `KBF_T2_018` no longer leaks the unsupported prior-period sentence
  containing `-93.69%` / `2,800만원`; final answer keeps the trace-supported
  `70.28%` growth sentence.
- `SKH_T3_080` no longer exposes stale `0백만원` lookup display; final answer
  preserves the source-visible `5,739억원`, `9,061억원`, and `-3,322억원`
  surfaces.
- This run is a focused regression gate. The current expanded comparison
  remains structural `8 / 9` vs plain `5 / 9` until both expanded profiles are
  rerun.
- Validation:
  - `python -m src.ops.audit_runtime_domain_terms`
  - `python -m unittest tests.test_subtask_loop`
  - `python -m unittest discover -s tests`

## Structured Operand Evidence Alignment Regression (2026-06-18)

참조:

- local result bundle:
  - `benchmarks/results/ablation_expanded_candidate_full_system_2026-06-10/`
- heartbeat log:
  - `benchmarks/results/ablation_expanded_candidate_full_system_2026-06-10/heartbeat_broader_focused_gate_2026-06-18.jsonl`
- artifact hygiene: result bundles and heartbeat logs are local experiment
  output and should not be staged.

### Setup

- Store-fixed structural full-system `eval-only` regression after commit
  `f9f6183` (`Stabilize structured operand evidence alignment`).
- Profile:
  `benchmarks/profiles/curated_ablation_expanded_candidate_full_system.json`
- Scope:
  - company runs: KakaoBank, POSCO Holdings, Samsung Electronics, Celltrion,
    KB Financial Group, SK hynix
  - question ids: `KBF_T2_018`, `SKH_T3_080`, `CEL_T1_013`, `CEL_T3_040`,
    `POS_T1_057`, `KAB_T1_066`, `SAM_T3_028`
- Purpose: regression-check the recently fixed hard cases before expanding to a
  full benchmark. This does not replace the current 9-question structural-vs-plain
  aggregate comparison.

### Results

| Question | Result | Answer / observation | Faithfulness | Completeness | Context recall |
| --- | --- | --- | ---: | ---: | ---: |
| `KAB_T1_066` | PASS | CIR `37.47%` | `1.000` | `1.000` | `1.000` |
| `POS_T1_057` | PASS | Interest coverage `3.5269배` | `1.000` | `1.000` | `1.000` |
| `SAM_T3_028` | PASS | Inventory valuation impact `2.79%` | `1.000` | `0.500` | `1.000` |
| `CEL_T1_013` | PASS | Capitalized-development ratio `52.99%` | `1.000` | `1.000` | `0.667` |
| `CEL_T3_040` | PASS | Inventory loss/reversal/disposal summary | `1.000` | `0.000` | `0.333` |
| `KBF_T2_018` | PASS | Credit-loss provision increase `70.28%` plus risk narrative | `1.000` | `1.000` | `0.667` |
| `SKH_T3_080` | PASS | FX translation net effect `-3,322억원` | `1.000` | `1.000` | `1.000` |

Run-level readout:

- Numeric PASS: `7 / 7`
- Heartbeat wall-clock runtime: about `32.2m`
- No source changes were produced by this run; raw benchmark outputs remain
  local-only.

### Interpretation

- The structured operand/evidence alignment changes survived the broader
  focused regression without benchmark-specific runtime branches.
- Follow-up focused eval-only on 2026-06-19 added a declarative credit-loss
  scenario narrative retrieval policy. `KBF_T2_018` stayed numeric PASS and
  context recall improved from `0.333` to `0.667`; context precision@5 and
  section match both improved to `1.000`.
- `SAM_T3_028` and `CEL_T3_040` are still quality watch items because final
  numeric judgement passes while completeness remains weak.
- `CEL_T1_013`, `KBF_T2_018`, and `SKH_T3_080` still emit stale/intermediate
  calculation traces before final answer recovery. The next polish task is
  trace cleanup, not new arithmetic logic.
- Keep the current aggregate ablation claim as structural `8 / 9` vs plain
  `5 / 9` until both full expanded profiles are rerun.

## Post-Refactor Expanded Structural Refresh (2026-06-18)

참조:

- structural local result bundle:
  - `benchmarks/results/ablation_expanded_candidate_full_system_2026-06-10/`
- heartbeat log:
  - `benchmarks/results/ablation_expanded_candidate_full_system_2026-06-10/heartbeat_full_structural_after_operand_filter_refactor_2026-06-18.jsonl`
- artifact hygiene: result bundles and heartbeat logs are local experiment
  output and should not be staged.

### Setup

- Store-fixed `eval-only` over the nine-question expanded structural
  full-system slice.
- Profile:
  `benchmarks/profiles/curated_ablation_expanded_candidate_full_system.json`
- This rerun followed the operand-candidate filtering cleanup:
  `_required_operand_rows_from_candidates()` and
  `_merge_required_operand_fallback_rows()`.
- The plain-retrieval counterpart was rerun later in the same code state; see
  [Post-Refactor Expanded Plain Refresh (2026-06-18)](#post-refactor-expanded-plain-refresh-2026-06-18).

### Results

| Metric | Structural full-system |
| --- | ---: |
| Numeric PASS | `8 / 9` |
| Avg numeric pass rate | `0.917` |
| Avg faithfulness | `0.942` |
| Avg completeness | `0.850` |
| Avg context recall | `0.889` |
| LLM calls / tokens | `135` / `722,298` |
| Query embedding calls | `63` |
| Estimated runtime cost | `$0.6334` |
| Heartbeat runtime | about `42.5m` |

| Question | Result | Answer / observation |
| --- | --- | --- |
| `KAB_T1_066` | PASS | CIR `37.47%` |
| `POS_T1_057` | PASS | Interest coverage `3.5269배`; the focused closure now holds in the full structural refresh |
| `SAM_T3_028` | PASS | Inventory valuation impact `2.79%` |
| `MIX_T1_021` | PASS | Debt ratio `25.36%`, current ratio `258.77%` |
| `CEL_T1_013` | PASS | Capitalized-development ratio `52.99%` |
| `KBF_T2_018` | PASS | Credit-loss provision increase `70.28%` plus risk narrative |
| `KBF_T1_017` | PASS | NIM difference `0.1%` |
| `SKH_T3_080` | PASS | FX translation net effect `-3,322억원` |
| `SKH_T1_060` | FAIL | Remaining role/denominator binding residual after `distinct_ratio_roles` reflection |

### Interpretation

- The structural expanded slice improved from `7 / 9` to `8 / 9`; the only
  remaining numeric failure is `SKH_T1_060`.
- `POS_T1_057` is no longer a structural residual after the focused closure.
  The later plain refresh still fails this question through public-answer
  display/unit drift.
- `SKH_T1_060` should be treated as the next hard-case engineering target:
  the run recovered most debt and asset values, then failed the final
  role/denominator binding check.
- Follow-up focused rerun on 2026-06-19 closed `SKH_T1_060` after a structured
  subtask projection fix. Keep this section's aggregate claim at `8 / 9` until
  the full structural profile is rerun under the fixed code.

## Post-Refactor Expanded Plain Refresh (2026-06-18)

참조:

- plain local result bundle:
  - `benchmarks/results/ablation_expanded_candidate_plain_retrieval_2026-06-10/`
- heartbeat log:
  - `benchmarks/results/ablation_expanded_candidate_plain_retrieval_2026-06-10/heartbeat_plain_after_operand_filter_refactor_2026-06-18.jsonl`
- artifact hygiene: result bundles and heartbeat logs are local experiment
  output and should not be staged.

### Setup

- Store-fixed `eval-only` over the nine-question expanded plain-retrieval
  slice.
- Profile:
  `benchmarks/profiles/curated_ablation_expanded_candidate_plain_retrieval.json`
- This rerun used the same post-refactor code state as the structural `8 / 9`
  refresh.

### Results

| Metric | Plain retrieval |
| --- | ---: |
| Numeric PASS | `5 / 9` |
| Avg numeric pass rate | `0.556` |
| Avg faithfulness | `0.589` |
| Avg completeness | `0.522` |
| Avg context recall | `0.926` |
| Avg Context P@5 | `0.800` |
| LLM calls / tokens | `116` / `585,879` |
| Query embedding calls | `63` |
| Estimated runtime cost | `$0.6681` |
| Heartbeat runtime | about `41.5m` |

| Question | Result | Answer / observation |
| --- | --- | --- |
| `KAB_T1_066` | PASS | CIR `37.47%` |
| `POS_T1_057` | FAIL | Internal ratio reached `3.5269배`, but public answer rendered as scale-broken `352687284.05%` |
| `SAM_T3_028` | PASS | Runtime/operand fixes now recover `2.79%`; no longer a current structural-only separator |
| `MIX_T1_021` | PASS | Debt ratio `25.36%`, current ratio `258.77%` |
| `CEL_T1_013` | FAIL | Uses broader denominator and returns `49.74%` instead of structural `52.99%` |
| `KBF_T2_018` | PASS | Numeric judge accepts `71.35%`; answer is noisier than structural but passes |
| `KBF_T1_017` | PASS | NIM difference `0.1%` |
| `SKH_T3_080` | FAIL | Misbinds FX gain/loss surfaces and returns `-1,351,498백만원` |
| `SKH_T1_060` | FAIL | Shared debt/asset role-binding residual |

### Interpretation

- The current expanded comparison is structural `8 / 9` vs plain `5 / 9`.
- Current structural-only separators are `POS_T1_057`, `CEL_T1_013`, and
  `SKH_T3_080`.
- `SAM_T3_028` moved from separator to shared PASS because the post-refactor
  runtime/operand path also helps plain retrieval.
- `SKH_T1_060` remains a shared hard residual, so it should be treated as a
  runtime role-binding problem rather than a structural-vs-plain separator.

## Post-Refactor Operand Filtering Separator Smoke (2026-06-18)

참조:

- structural local result bundle:
  - `benchmarks/results/ablation_expanded_candidate_full_system_2026-06-10/`
- heartbeat logs:
  - `benchmarks/results/ablation_expanded_candidate_full_system_2026-06-10/heartbeat_sam_t3_028_after_operand_filter_refactor_2026-06-18.jsonl`
  - `benchmarks/results/ablation_expanded_candidate_full_system_2026-06-10/heartbeat_cel_t1_013_after_operand_filter_refactor_2026-06-18.jsonl`
- artifact hygiene: result bundles and heartbeat logs are local experiment
  output and should not be staged.

### Setup

- Store-fixed focused `eval-only` after the calculation-runtime refactor that
  centralized required-operand candidate generation and surface-contract
  filtering.
- Profile:
  `benchmarks/profiles/curated_ablation_expanded_candidate_full_system.json`
- Scope:
  - `SAM_T3_028` on `samsung_2023_expanded_candidate`
  - `CEL_T1_013` on `celltrion_2023_expanded_candidate`

### Results

| Question | Numeric judgement | Answer | Faithfulness | Completeness | Avg score |
| --- | --- | --- | ---: | ---: | ---: |
| `SAM_T3_028` | PASS | `2.79%` | `1.000` | `0.700` | `0.945` |
| `CEL_T1_013` | PASS | `52.99%` | `1.000` | `1.000` | `0.923` |

### Interpretation

- This smoke confirms that the operand-filtering refactor did not break two
  strong structural-vs-plain separator cases.
- The result should not replace the existing nine-question aggregate claim.
  Rerun the full expanded store-fixed eval-only profile before changing the
  aggregate pass-rate table.

## Expanded Ablation Refresh After KBF Projection Fix (2026-06-17)

참조:

- structural local result bundle:
  - `benchmarks/results/ablation_expanded_candidate_full_system_2026-06-10/`
- plain local result bundle:
  - `benchmarks/results/ablation_expanded_candidate_plain_retrieval_2026-06-10/`
- artifact hygiene: result bundles and heartbeat logs are local experiment
  output and should not be staged.

### Setup

- Store-fixed `eval-only` over the nine-question expanded ablation slice.
- Structural profile:
  `benchmarks/profiles/curated_ablation_expanded_candidate_full_system.json`
- Plain profile:
  `benchmarks/profiles/curated_ablation_expanded_candidate_plain_retrieval.json`
- Both runs used monitored heartbeats.

### Results

| Metric | Structural full-system | Plain retrieval |
| --- | ---: | ---: |
| Numeric PASS | `7 / 9` | `4 / 9` |
| Avg faithfulness | `0.833` | `0.678` |
| Avg completeness | `0.578` | `0.389` |
| Avg context recall | `0.867` | `0.904` |
| Avg Context P@5 | `0.867` | `0.778` |
| Estimated runtime cost | `$0.6156` | `$0.8348` |
| LLM calls / tokens | `133` / `732,650` | `120` / `687,109` |
| Query embedding calls | `54` | `62` |

Separating cases:

| Question | Structural | Plain | Read |
| --- | --- | --- | --- |
| `SAM_T3_028` | PASS | FAIL | structural keeps cost-of-sales scale; plain answers `2792.63%` |
| `CEL_T1_013` | PASS | FAIL | structural keeps the R&D denominator; plain answers `49.74%` |
| `SKH_T3_080` | PASS | FAIL | structural keeps foreign-currency gain/loss row binding; plain misbinds the loss surface |

Shared residuals:

- `POS_T1_057`: interest-cost sign/display and unit binding.
- `SKH_T1_060`: debt-component numerator / asset denominator aggregation.

### Interpretation

- At the time, the expanded slice was no longer a stop-line: structural cleared
  the documented `7 / 9` rule and the plain rerun established the `4 / 9`
  baseline that later structural refreshes still compare against.
- The result supports a narrow structural-representation claim around scale,
  denominator, and row-binding preservation. It does not support a claim that
  the benchmark is fully solved.

## KBF Aggregate Public Answer Projection Closure (2026-06-17)

참조:

- local focused result bundle:
  - `benchmarks/results/ablation_expanded_candidate_full_system_2026-06-10/kb금융-2023/`
- artifact hygiene: this result bundle and heartbeat log are local experiment
  output and should not be staged.

### Setup

- Store-fixed focused `eval-only` over `KBF_T2_018` using the expanded
  candidate full-system profile and existing store.
- Command shape:
  `benchmark_runner --config benchmarks/profiles/curated_ablation_expanded_candidate_full_system.json --output-dir benchmarks/results/ablation_expanded_candidate_full_system_2026-06-10 --eval-only --company-run-id kbf_2023_expanded_candidate --question-id KBF_T2_018 --progress-heartbeat-sec 60 --heartbeat-log <path>`.

### Context

- The nine-question expanded refresh recovered the growth operands and
  structured aggregate result, but the public top-level `answer` was
  narrative-only. The evaluator saw that public answer and failed
  numeric/completeness even though `structured_result.formatted_result` already
  contained the complete numeric+narrative answer.

### Code / Contract Change

- Aggregate late numeric answer projection now promotes
  `calculation_result.formatted_result` / `rendered_value` when:
  - it differs from the current public answer,
  - it covers the nested numeric projection,
  - it has no untraced growth numeric material, and
  - the current public answer is empty, incomplete, or numerically unsafe.
- This is a generic trace-preservation fix. No company name, benchmark ID,
  report-specific phrase, or metric-specific runtime branch was added.

### Result

- Focused `KBF_T2_018` eval-only:
  - `numeric_final_judgement = PASS`
  - faithfulness `1.000`
  - completeness `1.000`
  - numeric grounding `1.000`
  - answer includes `3,146,409백만원`, `1,847,775백만원`, and `70.28%`.

### Validation

- `.venv/bin/python -m unittest tests.test_subtask_loop.SubtaskLoopTests.test_late_runtime_numeric_answer_promotes_supported_aggregate_formatted_result`:
  `1` test OK.
- Related aggregate/growth tests:
  `4` tests OK.
- `.venv/bin/python -m src.ops.audit_runtime_domain_terms`: passed with
  `215` reviewed literals.

### Interpretation

- This closed the focused `KBF_T2_018` public projection bug. The immediate
  follow-up expanded ablation refresh confirmed that the structural
  full-system slice reached `7 / 9` and justified the plain baseline
  comparison. A later 2026-06-18 structural refresh improved this to `8 / 9`.

## SKI Source-Stated Growth Repair and Narrative Pruning (2026-06-16)

참조:

- local result bundle:
  - `benchmarks/results/regression_ski_t2_069_repro_from_refactor_check_2026-06-16/`
- artifact hygiene: this result bundle and heartbeat logs are local experiment
  output and should not be staged.

### Setup

- Store-fixed focused eval-only over `SKI_T2_069`.
- Command shape:
  `benchmark_runner --config benchmarks/profiles/curated_single_doc_official_77.json --output-dir <existing-regression-dir> --company-run-id ski_2023_official_77 --eval-only --question-id SKI_T2_069 --numeric-fast-gate --progress-heartbeat-sec 30 --heartbeat-log <path>`.

### Code / Policy Change

- Period-comparison traces can be repaired from evidence after runtime
  projection when source evidence states a derived growth display that differs
  from stale task-output arithmetic.
- Aggregate-subtask period-comparison repair now preserves trace subtask rows
  before older state rows, then realigns growth/difference slots against
  table-label context and rebuilds the aggregate projection.
- If LLM operand extraction is empty, dependency or direct structured operand
  rows are preserved instead of being replaced by an empty operand artifact.
- Mixed numeric+narrative refresh now prunes existing context sentences unless
  they match supported narrative-summary rows or high-score evidence
  candidates. The score floor is declarative policy:
  `CALCULATION_NARRATIVE_POLICY["growth_supported_candidate_min_score"]`.
- The implementation stayed generic: no company name, benchmark ID,
  report-specific phrase, or metric-specific keyword bundle was added to
  runtime control flow.

### Results

- Latest focused `SKI_T2_069` eval-only:
  - `numeric_final_judgement = PASS`
  - faithfulness `1.000`
  - completeness `1.000`
  - numeric pass rate `1.000`
  - context P@5 `0.800`
- Final answer preserves the source-stated `84.3%` decrease and removes the
  unrelated forward-looking-information boilerplate:
  `2023년 정유 영업이익은 4,092억원이며, 2022년 2조 6,008억원 대비 84.3% 감소했습니다. 이러한 영업이익 감소는 유가 하락의 영향으로 제품가와 유가와의 차이(마진)가 감소했기 때문입니다.`

### Validation

- `python -m unittest tests.test_structured_operand_extraction tests.test_aggregate_subtask_projection tests.test_subtask_loop tests.test_financial_agent_run_projection tests.test_evaluator_runtime_projection`:
  `398` tests OK.
- `python -m src.ops.audit_runtime_domain_terms`: passed with `216` reviewed
  literals.
- `git diff --check`: passed.

### Interpretation

- The blocker was not a company-specific answer patch. It was stale
  period-comparison projection and overly broad preservation of narrative-like
  context sentences.
- The fix keeps source-stated numeric displays visible while retaining formula
  traces, and narrows answer-context carryover to evidence-supported narrative
  material.
- Remaining cleanup work is structural: continue shrinking/refactoring
  `financial_graph_calculation.py` around common trace projection and repair
  primitives before adding new benchmark-driven behavior.

## HYU Source-Slot Ratio Rebuild (2026-06-16)

참조:

- local result bundle:
  - `benchmarks/results/focused_hyu_t1_034_after_skip_incoherent_numeric_candidate_2026-06-16/`
- artifact hygiene: benchmark result bundle and heartbeat logs are local
  experiment output and should not be staged.

### Setup

- Store-fixed focused eval-only over `HYU_T1_034`.
- Command shape:
  `benchmark_runner --config benchmarks/profiles/curated_single_doc_official_77.json --output-dir <existing-focused-dir> --company-run-id hyundai_2023_official_77 --eval-only --question-id HYU_T1_034 --progress-heartbeat-sec 30 --heartbeat-log <path>`.

### Context

- Earlier guards blocked incoherent ratio candidates that mixed dependency
  slots with conflicting direct evidence, but the aggregate answer could still
  close as partial because the known lookup source slots were not reused to
  rebuild the ratio.
- A first source-slot fallback attempt exposed a denominator-selection issue:
  explicit stale denominator seeds could prefer a sibling lookup over the true
  base lookup.

### Code / Contract Change

- Preferred complete numeric answer can rebuild a ratio from source-task
  slots when the ratio row is insufficient or dependency-incoherent, but only
  when numerator and denominator slots are material and distinct.
- Source-slot candidates are restricted to lookup / single-value producer rows;
  ratio rows cannot become their own denominator source.
- Producer `metric_label` is preserved on source slots and used as generic
  matching metadata when a lookup primary label is stale or too broad.
- Lookup realignment from projected operands now keeps self-task projection
  behavior but blocks non-self-task overwrites when direct provenance is
  disjoint or source anchors conflict.
- The change is generic source-slot / provenance handling. No company,
  benchmark-id, report-specific phrase, or metric-specific runtime branch was
  added.

### Result

| Question | Previous focused state | New focused eval-only | Interpretation |
| --- | ---: | ---: | --- |
| `HYU_T1_034` | FAIL, avg `0.774`, safe partial after bad ratio suppression | PASS, avg `0.948` | Source slots rebuild `차량 영업이익 / 전체 영업이익 = 83.81%`. |

Final answer:

`2023년 전체 영업이익에서 차량 부문이 차지하는 비중은 83.81%입니다. 계산: 차량 영업이익 12조 6,773억원 / 전체 영업이익 15조 1,269억원.`

### Validation

- targeted ratio source-slot tests: `3` tests OK
- `python -m unittest tests.test_subtask_loop`: `205` tests OK
- related projection/subtask suite: `255` tests OK
- `python -m unittest discover -s tests`: `1171` tests OK
- `python -m src.ops.audit_runtime_domain_terms`: passed with `216`
  reviewed literals

## Growth Narrative Payload / Rendering Judge Compaction (2026-06-15)

참조:

- commits:
  - `64753a2` Stabilize growth narrative numeric refresh
  - `5188bda` Compact runtime evidence judge payloads
- local focused result bundles summarized, then cleaned:
  - `benchmarks/results/numeric_first_nav_t2_006_refactor5_probe_2026-06-15/`
  - `benchmarks/results/numeric_first_kbf_t2_018_refactor4_probe_2026-06-15/`
  - `benchmarks/results/numeric_first_kbf_t2_018_payload2_probe_2026-06-15/`
- artifact hygiene: these benchmark result bundles were local experiment output
  and were not staged.

### Context

- After the growth narrative numeric refresh, `NAV_T2_006` and `KBF_T2_018`
  were numerically healthy in focused eval-only runs.
- `KBF_T2_018` still exposed an evaluator/runtime payload issue: the
  grounded-rendering judge received an oversized nested `calculation_result`
  payload and failed with a token-limit error even though numeric equivalence
  and grounding were already `1.000`.
- The runtime evidence symptom was table-backed metadata carrying large
  serialized table payloads into public evidence items.

### Code / Contract Change

- Caller-facing runtime evidence metadata is compacted before final result
  projection: large table payload JSON fields are dropped while small
  provenance, unit, routing, and row-summary metadata are preserved.
- Trend and grounded-rendering LLM judges receive a compact
  `calculation_result` projection that omits nested subtask results, retrieved
  documents, runtime evidence, and debug payloads. Deterministic numeric
  scoring still uses the full runtime trace.
- The change stayed generic payload/projection plumbing; no company, question,
  metric, or benchmark-specific runtime branch was added.

### Focused Results

| Question | Result bundle | Key outcome |
| --- | --- | --- |
| `NAV_T2_006` | `numeric_first_nav_t2_006_refactor5_probe_2026-06-15` | faithfulness `1.000`, answer relevancy `0.845`, completeness `1.000`, calculation correctness `1.000`, grounded rendering `1.000`, error `0.0%` |
| `KBF_T2_018` before payload compaction | `numeric_first_kbf_t2_018_refactor4_probe_2026-06-15` | numeric `PASS`, but grounded-rendering judge hit the token limit; public runtime evidence was about `115k` chars |
| `KBF_T2_018` after payload compaction | `numeric_first_kbf_t2_018_payload2_probe_2026-06-15` | numeric `PASS`, numeric equivalence/grounding `1.000`, calculation correctness `1.000`, grounded rendering `1.000`, answer relevancy `0.841`, public runtime evidence about `23.6k` chars |

### Validation

- `python -m unittest tests.test_lookup_recovery_policy`: `16` tests OK.
- `python -m unittest tests.test_subtask_loop`: `192` tests OK.
- `python -m unittest tests.test_financial_agent_run_projection`: `43` tests OK.
- `python -m unittest tests.test_evaluator_runtime_projection`: `65` tests OK.
- `python -m src.ops.audit_runtime_domain_terms`: passed.

## HYU Ratio Task-Output Rebinding (2026-06-15)

참조:

- local result bundle:
  - `benchmarks/results/hyu_t1_034_ratio_task_output_distinct_source_2026-06-15/`
- artifact hygiene: benchmark result bundle is local experiment output and
  should not be staged.

### Setup

- Store-fixed focused eval-only over `HYU_T1_034`.
- Command shape:
  `benchmark_runner --config benchmarks/profiles/curated_single_doc_official_77.json --eval-only --question-id HYU_T1_034 --progress-heartbeat-sec 30 --heartbeat-log <path>`.

### Code / Contract Change

- Recovered lookup task-output slots now preserve `task_output:<task_id>`
  provenance when the structured source row is stale or blank.
- When a lookup task has one required operand, recovered answer-text slots
  inherit missing concept/period metadata from that producer contract.
- Ratio dependency source selection avoids reusing a task output already bound
  to the opposite ratio role group, so late total-denominator lookups can
  replace collapsed self-ratio operands.
- The change is generic dependency/provenance handling; no company,
  benchmark-id, or metric-specific runtime branch was added.

### Result

| Question | Previous latest | New focused eval-only | Interpretation |
| --- | ---: | ---: | --- |
| `HYU_T1_034` | FAIL, avg `0.774` | PASS, avg `0.947` | Late total operating-income lookup is bound as denominator; final ratio is `83.81%`. |

Verification:

- `python -m unittest tests.test_aggregate_subtask_projection tests.test_evaluator_runtime_projection tests.test_financial_agent_run_projection`: `152` tests OK.
- `python -m src.ops.audit_runtime_domain_terms`: passed with `216` reviewed literals.
- `git diff --check -- src\agent\financial_graph_calculation.py tests\test_aggregate_subtask_projection.py`: passed.
- Post-fix large-diff review replaced `segment_revenue_*` structured-cell
  affinity policy keys with generic `scoped_*` keys in runtime/config
  consumers. The marker vocabulary remains declarative in retrieval policy.
  Scoped surface affinity scoring and dependency-projection slot/source
  matching helpers were centralized in `financial_graph_helpers`, reducing
  duplicated nested implementation in `financial_graph_calculation`.
  Lookup task-output slot recovery was moved to
  `src/agent/financial_dependency_projection.py`; table-label evidence
  collection, dependency operand construction, and source-task answer-slot
  candidate extraction now live there too. Source-task operand derivation and
  fallback dependency operation-plan construction for ratio/growth repair are
  also delegated there, as are existing operand refresh from lookup slots and
  operand-id dedupe. Ratio missing-role fill, including denominator candidate
  inference from sibling lookup rows, is also centralized there. Dependency
  calculation-plan executability checks and deterministic/fallback rebuild are
  delegated there via callbacks. Recalculation state creation, absolute-ratio
  magnitude post-processing, and recalculated row assembly are now delegated
  there too. Lookup-row realignment from projected task-output operands is now
  delegated there as a row-level helper.
  `tests.test_operation_contracts` plus
  `tests.test_aggregate_subtask_projection` passed `271` tests; runtime
  domain-term audit, projection/evaluator/run projection suites `152` OK, and
  `git diff --check` also passed.

Post-fix focused regression:

| Question | Regression bundle | Result |
| --- | --- | --- |
| `SKI_T2_069` | `benchmarks/results/regression_ski_t2_069_after_hyu_rebind_2026-06-15/` | numeric `PASS`, faithfulness/completeness `1.000` |
| `POS_T1_075` | `benchmarks/results/regression_pos_t1_075_after_hyu_rebind_2026-06-15/` | numeric `PASS`, faithfulness/completeness `1.000` |
| `HYU_T1_034` | `benchmarks/results/regression_hyu_t1_034_after_hyu_rebind_2026-06-15/` | numeric `PASS`, faithfulness `1.000`, numeric grounding `1.000` |

## Financial Graph Calculation Refactor Focused Eval (2026-06-15)

참조:

- local result bundles:
  - `benchmarks/results/refactor_check_ski_t2_069_eval_only_2026-06-15/`
  - `benchmarks/results/refactor_check_hyu_t1_034_eval_only_2026-06-15/`
  - `benchmarks/results/refactor_check_pos_t1_075_eval_only_2026-06-15/`
- artifact hygiene: these result bundles are local experiment artifacts and
  should not be staged.

### Setup

- Store-fixed `--eval-only` refreshes using copied focused result bundles.
- Heartbeat-monitored command shape:
  `benchmark_runner --eval-only --progress-heartbeat-sec 30 --heartbeat-log <path>`.
- Focus:
  - already-passing aggregate/numeric answer cases stayed stable after the
    refactor
  - known failed ratio-binding case did not regress into unsupported numeric
    certainty

### Code / Contract Change

- Numeric display/evidence extraction was moved into
  `src/agent/financial_numeric_surface.py`, so runtime and evaluator share the
  same candidate extraction behavior instead of maintaining parallel regex
  surfaces.
- `financial_graph_calculation` now uses helper-level contracts for:
  - aggregate answer candidate selection
  - aggregate projection rebuild
  - artifact projection payload sync
  - late ratio answer refresh from resolved traces
- Ratio completeness now rejects numerator/denominator rows that collapse to the
  same source/value slot, even if their labels or operand ids differ.
- The operation plan guard applies the same generic distinct-role check before
  accepting selected ratio rows.
- No company name, benchmark id, report-specific phrase, or metric-specific
  runtime branch was added.

### Result

| Question | Previous | Refactor check | Interpretation |
| --- | ---: | ---: | --- |
| `SKI_T2_069` | PASS, avg `0.9630` | PASS, avg `0.9645` | Source-stated growth/narrative rendering remained stable. |
| `POS_T1_075` | PASS, avg `0.9444` | PASS, avg `0.9194` | User-facing answer stayed unchanged: `2023년 연결기준 EBITDA는 1,701,152백만원입니다.` |
| `HYU_T1_034` | FAIL, avg `0.7612` | FAIL, avg `0.7751` | Same-source/value self-ratio is blocked; answer now closes as a safer partial result. |

### HYU Interpretation

- The first refactor check exposed an unsupported `100%` ratio because numerator
  and denominator were both drawn from the same source/value slot while carrying
  different labels.
- The generic collapse guard now rejects that path and forces replanning /
  partial closure instead of accepting a self-ratio as complete evidence.
- The final answer remains a `FAIL`, but the failure mode is safer:
  recoverable operating-income values are shown, and the answer states that the
  requested ratio cannot be fully confirmed.
- The remaining gap should be handled in operand binding policy or
  table-structure interpretation. It should not be patched in aggregate answer
  composition.

### Validation

- `.venv\Scripts\python.exe -m py_compile src/agent/financial_graph_calculation.py src/agent/financial_numeric_surface.py src/ops/evaluator.py tests/test_aggregate_subtask_projection.py`
- `.venv\Scripts\python.exe -m unittest tests.test_aggregate_subtask_projection tests.test_evaluator_runtime_projection tests.test_financial_agent_run_projection`:
  `145` tests OK
- `.venv\Scripts\python.exe -m src.ops.audit_runtime_domain_terms`: passed
  with `216` reviewed literals
- `git diff --check`: passed

### Follow-up Projection Helper Smoke

After lookup-row realignment and dependency recalculation assembly were moved
into `src/agent/financial_dependency_projection.py`, the focused store-fixed
eval-only smoke was refreshed:

| Question | Bundle | Result |
| --- | --- | --- |
| `HYU_T1_034` | `benchmarks/results/refactor_projection_hyu_t1_034_eval_only_2026-06-15/` | numeric `PASS`, faithfulness `1.000`, avg `0.947`; final ratio `83.81%` |
| `POS_T1_075` | `benchmarks/results/refactor_projection_pos_t1_075_eval_only_2026-06-15/` | numeric `PASS`, faithfulness/completeness `1.000`, avg `0.919` |
| `SKI_T2_069` | `benchmarks/results/refactor_projection_ski_t2_069_eval_only_2026-06-15/` | numeric `PASS`, faithfulness/completeness `1.000`, avg `0.965` |

These bundles are local benchmark artifacts and should not be staged.

## Curated Single-Doc Core Full Eval (2026-06-12)

참조:

- profile: `benchmarks/profiles/curated_single_doc_core.json`
- local result bundle was summarized from
  `benchmarks/results/curated_single_doc_core_2026-06-11/` and then deleted
  under benchmark artifact hygiene
- source commits:
  - `d5bfbc1 Tighten narrative evidence projection`
  - `ebaeb66 Stop exclusive narrative replanning loops`

### Setup

- Store-fixed `--eval-only` refresh using existing local stores.
- Heartbeat-monitored command shape:
  `benchmark_runner --config benchmarks/profiles/curated_single_doc_core.json --eval-only --progress-heartbeat-sec 30`.
- Scope:
  - 삼성전자 2023: `5` questions
  - 네이버 2023: `5` questions
  - 현대자동차 2023: `5` questions
- This is a broader sanity run for the current single-document core profile,
  not the full `77`-question curated dataset.

### Code / Contract Change

- `MIX_T2_047` exposed over-broad final runtime evidence projection for
  narrative summaries. The runtime now projects final evidence from
  `kept_claim_ids` / `selected_claim_ids` for nonnumeric final answers, and
  preferred-section compression can use a sufficiently supported high-priority
  section instead of carrying weaker cross-section context.
- `SAM_T4_070` exposed a loop in forward-looking / refusal-style questions:
  the task was planned as `narrative_policy_exclusive`, evidence extraction
  marked the direct requested value as missing, compression produced a refusal,
  but aggregate synthesis still emitted planner feedback. The graph then
  re-entered semantic planning even though an exclusive narrative policy has no
  useful numeric subtask expansion.
- The fix is a generic routing rule: when
  `semantic_plan.status == narrative_policy_exclusive`, aggregate output is
  terminal and routes to `cite`.
- No company, benchmark id, or report-specific runtime branch was added.

### Result

| Company | Questions | Avg score | Faithfulness | Completeness | Recall | Hit@k | Section | Citation | Numeric pass | Error |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 삼성전자 2023 | 5 | `0.837` | `1.000` | `1.000` | `0.800` | `0.800` | `0.750` | `0.933` | `1.000` | `0.0%` |
| 네이버 2023 | 5 | `0.795` | `1.000` | `1.000` | `1.000` | `0.600` | `0.600` | `0.867` | `1.000` | `0.0%` |
| 현대자동차 2023 | 5 | `0.928` | `1.000` | `1.000` | `1.000` | `1.000` | `0.900` | `1.000` | `-` | `0.0%` |

Question-level low signals:

| Question | Observation | Interpretation |
| --- | --- | --- |
| `SAM_T4_070` | faithful refusal, but retrieval hit / section match `0.000` | The answer correctly refuses the missing 2026 yield, but final runtime evidence only preserves the forward-looking caution sentence rather than the nearby 3nm/GAA support context. |
| `NAV_T4_008` | safe missing answer, retrieval hit / section match `0.000`, answer relevancy `0.380` | Out-of-domain missing numeric query closes safely, but retrieval/evaluator alignment is weak. |
| `NAV_T4_033` | safe missing answer, retrieval hit / section match `0.000` | Missing operational-logistics query closes safely, but expected missing-evidence support is not projected strongly. |

### Validation

- Focused routing / forward-looking tests: `6` tests OK.
- Runtime domain-language audit: passed with `216` reviewed literals.
- Focused `SAM_T4_070` eval-only completed in `52.3s`.
- Full 15-question eval-only completed with all company error rates at `0.0%`.

### Interpretation

- The main runtime risk found during broader eval was not arithmetic accuracy;
  it was terminal control flow for policy-driven narrative refusals.
- The fix strengthens the agent contract: an exclusive narrative policy is a
  terminal semantic decision, not a signal to invent additional numeric
  planning work after a refusal answer has already been grounded.
- The remaining work is quality-oriented evidence projection for refusal and
  out-of-scope questions. It should be addressed through generic evidence
  preservation / evaluator alignment, not benchmark-specific runtime rules.

## CEL_T1_038 Unit and Final Answer Consistency (2026-06-12)

참조:

- profile:
  `benchmarks/profiles/curated_ablation_structural_hard_full_system.json`
- focused local result bundle:
  `benchmarks/results/cel_t1_038_unit_repair_check_2026-06-12/`

### Context

`CEL_T1_038` is the hard margin-drag case: compute how much amortization
expense lowers operating margin. The correct target answer is approximately
`8.36%p` from `182,049,824천원 / 2,176,431,531,380원`.

The regression was not a missing-retrieval problem alone. The pipeline could
recover the right source value, but the final answer contract let stale unit
state survive:

- numeric extractor evidence represented revenue as
  `claim=2,176,431,531,380 (원)` and
  `quote_span=2,176,431,531,380`
- lookup slot capture kept an existing table metadata unit `천원` because the
  value-local `원` unit lived only in the claim surface
- downstream ratio traces could recover `8.36%p`, but aggregate synthesis still
  preserved a stale `0.01%p` top-level answer in some runs
- when corrected, the final answer could still include a support subtask
  (`영업이익률 29.93%`) that was not the user's target metric

### Code / Contract Change

- Lookup slot refinement now considers claim-visible value-local units when the
  quote span contains only the raw number.
- Operand normalization repairs source-visible units from rendered/source
  surfaces and rejects implausible same-unit KRW ratio scales.
- Late aggregate alignment re-runs lookup unit alignment and dependency
  projection after source-task / evidence preservation steps.
- Final answer consistency now prefers the completed numeric subtask whose
  metric and operand focus best matches the user query, instead of concatenating
  every support numeric subtask.
- `operating_margin_drag` ontology policy now requires an exact
  amortization-expense surface contract for the numerator, keeping goodwill /
  accumulated amortization rows out of direct matches.
- No company name, benchmark id, or report-specific runtime branch was added.

### Result

Focused final run:

| Question | Numeric judgement | Final answer |
| --- | --- | --- |
| `CEL_T1_038` | `PASS` | `2023년 영업이익률 감소 영향은 8.36%p입니다. 계산: 무형자산상각비 182,049,824천원 / 매출액 2,176,431,531.38천원.` |

Quality signals:

- faithfulness `1.000`
- completeness `1.000`
- numeric grounding `1.000`
- unit consistency `1.000`
- error rate `0.0%`

### Validation

- focused operation/subtask regression tests: OK
- `.venv/bin/python -m src.ops.audit_runtime_domain_terms`: passed with `216`
  reviewed literals
- `git diff --check`: passed
- heartbeat-monitored focused benchmark: `PASS`

### Interpretation

This fix is a runtime-contract closure rather than a benchmark answer patch.
The key lesson is that final answer correctness depends on preserving
source-visible unit evidence across three boundaries: lookup capture,
dependency ratio projection, and final aggregate answer selection. The
deterministic calculator can only protect arithmetic once the operand slots
carry the correct source unit.

## Hard Numeric Runtime Closure (2026-06-11)

참조:

- `benchmarks/profiles/curated_ablation_structural_hard_full_system.json`
- local eval-only bundle was summarized from
  `benchmarks/results/hard_current_evalonly_2026-06-10/` and then deleted under
  benchmark artifact hygiene.

### Context

- The hard numeric set still had two meaningful runtime gaps after the broader
  structural ablation work:
  - `SAM_T1_026`: ROE was calculated against a single equity period instead of
    average current/prior equity.
  - `CEL_T1_038`: the margin-drag question needed an aggregate/final
    amortization expense row, but detail rows could still override the stronger
    structured aggregate slot during late lookup alignment.
- Both failures were treated as contract gaps, not as company/question-specific
  exceptions.

### Code / Contract Change

- `roe` now declares current/prior equity operands and an average denominator in
  the ontology. Period hints flow through operand specs, lookup input bindings,
  and dependency task outputs.
- `operating_margin_drag` is represented as a policy/ontology-driven ratio:
  amortization expense over revenue, rendered in percentage points.
- Numeric lookup rows preserve structural metadata such as `value_role`,
  `aggregation_stage`, and `aggregate_label`.
- Aggregate-preferred lookups avoid cell-less text-only sibling fallback when a
  structured table context is required, and prefer aggregate/final/subtotal
  candidates generically.
- Late source-task/lookup alignment can refresh planless ratio answers from
  stronger structured slots, but it does not let weaker detail lookups replace
  already dependency-backed arithmetic operands.
- No company name, benchmark id, or report-specific runtime branch was added.

### Result

Store-fixed hard replay, eval-only on the existing bundle:

| Question | Result | Final numeric answer |
| --- | --- | --- |
| `KAB_T1_066` | PASS | CIR `37.47%` from `4,355.42억원 / 11,623억원` |
| `MIX_T1_021` | PASS | debt ratio `25.36%`, current ratio `258.77%` |
| `SAM_T1_026` | PASS | ROE `4.31%` using average equity |
| `CEL_T1_038` | PASS | margin drag `8.36%p`, operating margin `29.93%` |
| `SKH_T1_060` | PASS | borrowing over tangible+intangible assets `42.02%` |

Aggregate hard result: `5 / 5` numeric PASS.

### Validation

- Focused runtime tests:
  `tests.test_subtask_loop.SubtaskLoopTests.test_aggregate_final_answer_refreshes_after_late_lookup_slot_alignment`,
  `tests.test_aggregate_subtask_projection.AggregateSubtaskProjectionTests.test_dependency_projection_recalculates_planless_ratio_from_best_lookup_slot`,
  and
  `tests.test_aggregate_subtask_projection.AggregateSubtaskProjectionTests.test_dependency_projection_recalculates_from_stronger_source_task_slot`:
  `3` tests OK.
- Related ontology / planner / operation / structured extraction suites before
  the final alignment guard: `389` tests OK.
- Runtime domain-language audit: passed with `217` reviewed literals.
- Full hard eval-only replay: `5 / 5` numeric PASS.

### Interpretation

- The hard-set result now supports a stronger design claim: structural cell
  metadata is not only useful at retrieval time, but also at late runtime
  alignment time, where final/detail row disambiguation determines whether a
  recovered lookup can safely update a ratio answer.
- The follow-up structural-vs-plain replay below is the controlled hard-set
  comparison. Broader full benchmark work should start from a monitored
  `curated_single_doc_core` run if more coverage is needed.

## Hard Structural-vs-Plain Replay (2026-06-11)

참조:

- structural:
  summarized from `benchmarks/results/hard_current_evalonly_2026-06-10/`
  before that local raw bundle was deleted under artifact hygiene
- plain:
  `benchmarks/results/ablation_structural_hard_plain_retrieval_2026-06-11/`
- profiles:
  - `benchmarks/profiles/curated_ablation_structural_hard_full_system.json`
  - `benchmarks/profiles/curated_ablation_structural_hard_plain_retrieval.json`

### Setup

- Same `5` hard numeric questions were replayed across the same `4` company
  runs.
- Structural variant used `structural_selective_v2` plus deterministic prefix.
- Plain variant used plain chunks without zero-cost prefix.
- Runtime code, ontology, evaluator, retrieval budgets, and question ids were
  otherwise the same. The plain run built fresh local stores with heartbeat
  monitoring.

### Result

| Variant | Numeric pass | Avg completeness | Avg faithfulness | Avg recall | Full eval fail notes |
| --- | ---: | ---: | ---: | ---: | ---: |
| Structural | `5 / 5` | `0.938` | `1.000` | `0.827` | `1` |
| Plain | `4 / 5` | `0.812` | `0.875` | `0.932` | `2` |

Question-level comparison:

| Question | Structural | Plain | Interpretation |
| --- | --- | --- | --- |
| `KAB_T1_066` | PASS, `37.47%` | PASS, `37.47%` | Direct-support and coherent-ratio runtime contract is enough for both variants. |
| `MIX_T1_021` | PASS, `25.36%` / `258.77%` | PASS, `25.36%` / `258.77%` | Balance-sheet ratios are robust once ontology operands are explicit. |
| `SAM_T1_026` | PASS, `4.31%` | PASS, `4.31%` | The recent improvement is mainly ontology/period-binding, not structural ingest alone. |
| `CEL_T1_038` | PASS, `8.36%p` / `29.93%` | PASS, `8.36%p` / `29.93%` | Plain initially calculated a weaker `6.58%p` path, but late structural-slot alignment recovered the aggregate answer. |
| `SKH_T1_060` | PASS, `42.02%` | FAIL, `34.32%` | Plain selected lower borrowing operands: `3,833,263`, `9,073,567`, `6,497,790` instead of structural's `4,145,647`, `10,121,033`, `9,490,410`. |

### Interpretation

- The experiment separates two claims:
  - Ontology/planner/runtime contract fixes are now strong enough that plain
    retrieval can pass several previously hard numeric cases.
  - Structural representation still matters for row binding when multiple
    semantically plausible rows share the same labels, as in `SKH_T1_060`.
- This is a better portfolio narrative than a broad claim that structural
  retrieval always wins. The defensible claim is narrower: structural metadata
  provides a measurable row-binding advantage on ambiguous financial tables,
  while deterministic ontology/runtime contracts carry formula and period
  binding across both retrieval variants.

## KAB_T1_066 CIR Direct-Support And Coherent Ratio Close (2026-06-09)

참조:

- `benchmarks/results/kab_t1_066_final_verified_evalonly_2026-06-09/`
- source store input:
  `benchmarks/results/kab_t1_066_replan_guard_fresh_canary_2026-06-09/`

### Context

- Fresh canary에서 `KAB_T1_066`은 denominator를 별도 재무제표 row로 잘못
  묶어 `91.03%`를 냈다.
- direct-support guard를 추가한 뒤에는 wrong denominator는 막았지만,
  `경비차감전영업이익` 안의 `차감` substring이 aggregate operation token으로
  오인되어 correct denominator `11,623억원`도 reject됐다.
- denominator가 복구된 뒤에도 final rendering은 이전 lookup subtask display
  `435,542백만원`을 우선해 `4,355.42억원`을 답변에 남겼다.

### Code / Contract Change

- Numeric lookup direct-support validation includes the formatted prompt
  context actually shown to the LLM.
- Aggregate-operation detection checks the token's left boundary so an
  operation token embedded inside a longer metric label is not treated as an
  aggregate result.
- Ratio operand assembly probes retrieved/seed docs for a coherent table/source
  context when dependency outputs already cover required operands.
- Late aggregate rendering refreshes ratio answers from resolved calculation
  trace components when result value is present but component display differs.
- No company name, benchmark id, or question-specific runtime branch was added.

### Result

- Final answer:
  `2023년 CIR은 37.47%입니다. 계산: 판매비와관리비 4,355억원 / 경비차감전영업이익 11,623억원.`
- Resolved operands:
  - `판매비와관리비 = 4,355억원`
  - `경비차감전영업이익 = 11,623억원`
  - both from `IV. 이사의 경영진단 및 분석의견::table:3`
- Metrics:
  - numeric `PASS`
  - faithfulness `1.000`
  - completeness `1.000`
  - context recall `1.000`
  - retrieval hit@k `1.000`
  - grounded rendering correctness `1.000`
- Fanout/cost:
  - latency `68.5s`
  - executed queries `2`
  - duplicate executed queries `0`
  - state query-result avoided searches `14`
  - agent LLM tokens `55,104`
  - agent LLM calls `8`
  - estimated runtime cost `$0.056292`

### Validation

- `.venv/bin/python -m unittest tests.test_operation_contracts tests.test_subtask_loop`:
  `362` tests OK.
- `.venv/bin/python -m src.ops.audit_runtime_domain_terms --summary`: passed
  with `217` reviewed literals.
- `src.ops.audit_benchmark_fanout_cost` run on the final eval-only bundle.

### Interpretation

- The focused KAB CIR issue is closed with source-visible operands and grounded
  rendering, not only numeric tolerance.
- Intermediate diagnostic result bundles are local artifacts. Keep the final
  verified bundle and the source fresh store only if reproducible handoff is
  needed.

## Expanded Structural Ablation Refresh (2026-06-10)

참조:

- `benchmarks/profiles/curated_ablation_expanded_candidate_full_system.json`
- `benchmarks/profiles/curated_ablation_expanded_candidate_plain_retrieval.json`
- `benchmarks/results/ablation_expanded_candidate_full_system_2026-06-10/`
- `benchmarks/results/ablation_expanded_candidate_plain_retrieval_2026-06-10/`
- `docs/evaluation/ablation_study_design.md`
- `docs/evaluation/structural_trace_diagnostics.md`

### Context

- Earlier closed-structural ablation evidence was useful but narrow: the main
  separator was `POS_T1_057`.
- The follow-up expanded the candidate set to `9` curated questions across
  `6` company runs while keeping the same evaluator, retrieval budgets, chunk
  size, and question ids for both variants.
- The controlled difference was representation: structural selective chunks
  with deterministic prefixes versus plain chunks without structural prefixes.

### Result

| Metric | Structural full-system | Plain retrieval |
| --- | ---: | ---: |
| Avg numeric pass rate | `1.000` | `0.833` |
| Avg completeness | `0.867` | `0.875` |
| Avg faithfulness | `1.000` | `0.875` |
| Avg context recall | `0.889` | `0.861` |

Separating cases:

- `KBF_T1_017`: structural numeric `PASS`, plain numeric `FAIL`.
  - The plain answer surfaced `1.83%`, `1.73%`, and `0.1%p`, but operand
    selection and numeric grounding failed.
  - The structural path recovered a numeric-passable difference, although
    completeness remained weak.
- `SKH_T3_080`: structural numeric `PASS`, plain numeric `FAIL`.
  - Plain answer: `868,767백만원 - 906,120백만원 = -37,353백만원`.
  - Structural answer: `573,884백만원 - 906,120백만원 = -332,236백만원`.
  - This is the cleanest row-binding example because both variants found
    plausible values, but only the structural path bound the right gain row.

### Interpretation

- The expanded run strengthens the numeric-grounding claim: structural stayed
  at `1.000` average numeric pass rate while plain retrieval dropped to
  `0.833`.
- It does not prove an across-the-board evaluator win. The cross-company
  summary still reports `Full Eval Fails` for both variants because that field
  also includes completeness threshold misses.
- The portfolio narrative should therefore state the result precisely:
  structural representation and provenance-aware operand binding reduce
  numeric grounding failures; explanation completeness remains a separate
  residual quality target.
- Raw result bundles remain local artifacts and should not be staged.

## Runtime Cost-Control Diagnostics (2026-06-09)

참조:

- `kab_t1_066_llm_phase_canary_2026-06-09`: summarized then deleted
- `kab_t1_066_aggregate_compact_canary_2026-06-09`: summarized then deleted
- `kab_t1_066_numeric_prompt_diag_canary_2026-06-09`: local artifact,
  summarized then deleted
- `kab_t1_066_numeric_reject_reuse_canary_2026-06-09`: local artifact,
  summarized then deleted
- `kab_t1_066_lookup_objective_cache_canary_2026-06-09`: local artifact,
  summarized then deleted

### 무엇을 검증했나

- `KAB_T1_066` 단일 질문을 cost-control canary로 사용해 agent LLM fanout을
  phase별로 분해했다.
- 첫 canary는 aggregate synthesis가 가장 큰 비용 phase임을 확인했고, 후속
  변경은 final aggregate prompt에 full runtime payload 대신 compact
  projection rows만 전달하도록 줄였다.
- 그 다음 병목인 `numeric_extraction`은 prompt-size diagnostic과 call-level
  `numeric_debug_trace_history`로 관측했다. 마지막 trace 하나만 남기던
  기존 serialization으로는 retry loop 분석이 불가능했기 때문이다.

### 결과

| Step | Key result |
| --- | --- |
| Phase usage canary | `KAB_T1_066` numeric `PASS`; total agent LLM tokens `258,333`; top phase `aggregate_synthesis` `186,310` tokens |
| Aggregate compact projection | numeric `PASS`; total agent LLM tokens `76,252`; `aggregate_synthesis` `4,064` tokens; largest remaining phase `numeric_extraction` `51,556` tokens |
| Numeric prompt history eval-only | numeric `PASS`; latency `416.0s`; agent LLM tokens `190,990`; `numeric_extraction` `106,483` tokens / `6` calls |
| Numeric result/rejection reuse eval-only | numeric `PASS`; latency `232.7s`; agent LLM tokens `108,158`; `numeric_extraction` `50,224` tokens / `3` calls |
| Lookup objective cache reuse canary | numeric `PASS`; latency `346.8s`; executed queries `12`; duplicate queries `0`; query embedding calls `12`; query-result cache avoided searches `64`; objective cache hits `42`; agent LLM tokens `148,169`; `numeric_extraction` `61,708` tokens / `4` calls |

The final history canary preserved all `6` numeric extraction prompt
diagnostics. Each call selected `8` docs; formatted context size ranged from
`19,823` to `25,901` chars. Four calls rejected a value-visible
`경비차감전영업이익` lookup as `missing_direct_lookup_operand_support`, then
reflection/retry re-entered the same expensive extraction pattern.

The follow-up reuse canary preserved the same `6` history entries but skipped
`3` of them without LLM calls: `2` duplicate direct-support rejections and `1`
duplicate supported result. This reduced numeric extraction from `6` to `3`
LLM calls while keeping the final CIR answer at `37.47%`.

The next canary generalized retrieval-side reuse for equivalent lookup
objectives. Reworded primary/focused/retry queries can now hit the same
state-local query-result cache entry when the lookup objective and metadata
filter match, so the runtime no longer pays separate embedding/vector calls for
those wording variants. On `KAB_T1_066`, that collapsed retrieval fanout from
the prior canary's `34` executed queries with `8` duplicates and `26` embedding
calls to `12` executed queries with `0` duplicates and `12` embedding calls,
while keeping numeric `PASS`. The cache avoided `64` searches, including `42`
objective-level hits. End-to-end latency still rose to `346.8s` because a
direct-support rejection re-entered semantic replan/retry; the same run used
`148,169` agent LLM tokens across `25` calls and surfaced
`duplicate_artifact_id:reflection:task_1:001:report`.

### 해석

- Aggregate prompt compaction was the right first cost-control fix because it
  removed a large prompt payload without changing answer behavior.
- After that, the remaining cost problem was not just prompt size. It was
  repeated numeric extraction over equivalent query + candidate windows.
- The reuse change is generic: successful numeric extraction results and
  `missing_direct_lookup_operand_support` rejections are reused only when the
  normalized numeric query and selected candidate window fingerprint match.
  Value preservation and direct-support validation remain intact.
- Lookup objective cache reuse is also generic: it consumes the planner's
  operand contract rather than matching company names, benchmark IDs, or
  metric-specific keywords.
- The next runtime change started by fixing duplicate reflection artifact ids.
  Reflection retry handoff now allocates `reflection:{target}:NNN` from the
  existing task/artifact ledger, so stale `reflection_count` or re-entry cannot
  append a second `reflection:{target}:NNN:report` artifact.
- The follow-up runtime change then added a bounded replan guard for repeated
  direct-support lookup rejection. After the first semantic replan attempt, if
  numeric extraction history already contains
  `duplicate_missing_direct_lookup_operand_support`, aggregate synthesis keeps
  the partial/refusal closure and routes to `cite` instead of invoking another
  semantic replan. This uses the generic extraction fingerprint/rejection
  history, not company names, benchmark IDs, or metric-specific keywords.
- Remaining runtime-cost work is to quantify the new guard with a store-fixed
  canary when a reusable KAB store is available.
- This is a runtime-cost contract, not a benchmark answer rule. No company,
  question ID, or metric-specific branch should be introduced for the follow-up.

Validation for the replan loop guard:

- focused aggregate/replan tests: `4` OK
- related subtask/run-projection/reflection suites: `217` OK
- runtime domain-term audit: passed with `215` reviewed literals
- full unittest discovery: `1028` OK

Validation for the reflection id allocation change:

- focused reflection/ledger tests: `5` OK
- related subtask/run-projection/reflection suites: `216` OK
- runtime domain-term audit: passed with `215` reviewed literals
- full unittest discovery: `1027` OK

Validation for the lookup objective cache change:

- focused retrieval/cache tests: `5` OK
- related retrieval/fanout/operation suites: `212` OK
- runtime domain-term audit: passed with `215` reviewed literals
- full unittest discovery: `1026` OK

Validation for the numeric reuse change:

- focused numeric reuse tests: `3` OK
- related runtime/evaluator suites: `236` OK
- runtime domain-term audit: passed with `215` reviewed literals
- full unittest discovery: `1025` OK

## Concept Gate Focused Hardening (2026-06-08)

참조:

- `benchmarks/results/tmp_kbf_t2_018_recovery_skip_current_2026-06-08/`
- `benchmarks/results/tmp_pos_t1_057_unit_check_2026-06-08/`
- `benchmarks/results/tmp_kab_t1_066_ratio_component_merge_fix_2026-06-08/`
- `benchmarks/results/concept_gate_fresh_after_ratio_growth_hardening_2026-06-08/`

### 무엇을 검증했나

- 2026-06-04 concept gate `7 / 7 PASS` baseline 이후, budgeted replay와
  focused eval-only에서 드러난 POS/KBF/KAB residual을 store-fixed
  single-question eval-only로 좁혔다.
- 실험 산출물은 local artifact로만 두고 commit 대상에는 포함하지 않는다.

### 결과

| Question | Focused outcome |
| --- | --- |
| `POS_T1_057` | numeric `PASS`, faithfulness/completeness `1.000 / 1.000`, answer `3.5269배` |
| `KAB_T1_066` | numeric `PASS`, faithfulness/completeness `1.000 / 1.000`, CIR answer `37.47%` |
| `KBF_T2_018` | numeric `PASS`, faithfulness/completeness `1.000 / 1.000`, final answer preserves `70.28%`, `3,146,409백만원`, `1,847,775백만원`, and risk-management cause narrative |

후속 monitored full 7 store-fixed eval-only replay:

| Question | Full replay outcome |
| --- | --- |
| `KBF_T2_018` | numeric `PASS`, faithfulness/completeness `1.000 / 1.000` |
| `SKH_T3_080` | numeric `PASS`, faithfulness/completeness `1.000 / 1.000` |
| `CEL_T1_013` | numeric `PASS`, faithfulness/completeness `1.000 / 1.000` |
| `CEL_T3_040` | numeric `PASS`, faithfulness/completeness `1.000 / 1.000` |
| `POS_T1_057` | numeric `PASS`, faithfulness/completeness `1.000 / 1.000`, answer `3.5269배` |
| `KAB_T1_066` | numeric `PASS`, faithfulness/completeness `1.000 / 1.000`, CIR answer `37.47%` |
| `SAM_T3_028` | numeric `PASS`, faithfulness/completeness `1.000 / 1.000`; deterministic trace keeps `62,964백만원 / 180,388,580백만원 = 0.03%` |

### 해석

- POS residual은 특정 회사 보정이 아니라 ratio operand peer-unit contract로
  닫았다. 같은 raw value가 서로 다른 KRW display unit 후보로 존재하면,
  같은 ratio 안의 peer operands와 unit이 맞는 structured evidence를 우선한다.
- KBF residual은 숫자 성장률 문장만으로 mixed growth+narrative intent를
  만족했다고 보는 aggregate repair gap이었다. `narrative_summary` row의
  서술 문장을 deterministic repair 후보로 유지하고, final answer가 실제
  서술 후보를 포함할 때만 supported aggregate answer를 보호한다.
- Follow-up hardening keeps nested aggregate lookup rows available for final
  promotion, realigns growth operands from the promoted lookup slots before
  final projection, rejects same-period current/prior growth operands, and
  preserves digit-free explanatory narrative after late source-surface
  rewrites without reattaching table fragments.
- A monitored fresh/full replay exposed two additional generic issues before
  replacing the baseline: duplicate growth rows could prefer a source-rich but
  sign-mixed candidate over a sign-consistent nested candidate, and `십억원`
  was present in render policy but missing from numeric unit normalization.
  The fix adds sign-consistency to growth row ranking, normalizes `십억원`
  through policy, repairs stale KRW raw-unit scale mismatches before formula
  execution, and declares credit-loss provision magnitude semantics in
  ontology data rather than runtime branches.
- 검증은 focused eval-only와 local regression suite로 닫았다:
  final focused `KBF_T2_018` eval-only `numeric_final_judgement = PASS`,
  `faithfulness = 1.000`, `completeness = 1.000`;
  `src.ops.audit_runtime_domain_terms --summary` passed; `git diff --check`
  passed; and full `python -m unittest discover -s tests` ran `1003` tests OK.
- Final contract follow-up narrowed the supported aggregate answer selector:
  `narrative_summary` rows are ignored even when their answer slots carry
  `operation_family = aggregate_subtasks`. This prevents explanatory
  projections from being promoted as aggregate numeric answers without adding
  company-, question-, or metric-specific runtime branches.
- Follow-up validation for that final contract guard:
  `src.ops.audit_runtime_domain_terms --summary` passed with `215` reviewed
  literals; `python -m unittest tests.test_subtask_loop
  tests.test_operation_contracts` ran `336` tests OK; monitored full 7
  eval-only replay reported `7 / 7` numeric PASS. Raw benchmark output remains
  a local artifact and is not committed.
- A focused `KAB_T1_066` trace-quality follow-up then reduced the long retry
  path without changing the numeric answer. When an active ratio
  reconciliation already supplies every required operand, partial or failed
  lookup dependency producer-scope filters no longer remove those complete
  direct ratio rows. Focused store-fixed eval-only preserved numeric `PASS`,
  faithfulness/completeness `1.000 / 1.000`, and CIR answer `37.47%`, while
  reducing latency `309s -> 108s`, retrieval debug history `8 -> 3`, and task
  artifacts `21 -> 8`. Validation: runtime domain-term audit passed with
  `215` reviewed literals, and `python -m unittest
  tests.test_structured_operand_extraction tests.test_subtask_loop
  tests.test_operation_contracts` ran `358` tests OK.
- A later `KBF_T2_018` trace-consistency follow-up kept the focused numeric
  `PASS` while removing stale nested calculation displays from the serialized
  trace. The runtime now reuses the final aggregate projection's full
  `subtask_results` as a generic consistency source, promotes stronger nested
  lookup rows, realigns dependent growth rows, and recursively syncs nested
  aggregate child rows to the final task rows. Focused store-fixed eval-only
  reported numeric `PASS`, average score `0.924`, and final trace checks found
  `0` stale hits for `(303)` / `-1138.28%` under
  `resolved_calculation_trace` and `structured_result`. Validation:
  `python -m src.ops.audit_runtime_domain_terms --summary` passed, and
  `python -m unittest discover -s tests` ran `1019` tests OK.

## MAS Smoke Outcome Refresh (2026-06-07)

참조:

- `benchmarks/results/mas_e2e_smoke_outcome_refresh_2026-06-07/`
- `benchmarks/results/mas_e2e_smoke_outcome_refresh_replan1_2026-06-07/`
- `benchmarks/results/mas_e2e_smoke_failure_diagnostics_2026-06-07/`
- `benchmarks/results/mas_direct_worker_probe_2026-06-07/`

### 무엇을 검증했나

- PR #39 이후 `mas_e2e_smoke`의 새 `final_acceptance_outcome` surface가
  실제 live/default MAS smoke에서 어떤 상태를 보여주는지 확인했다.
- raw output은 local experiment artifact로만 유지하고 commit 대상에는
  포함하지 않는다.

### 결과

| Run | Key outcome |
| --- | --- |
| default `replan_budget = 0` | `final_acceptance_outcome_counts = {"blocked_without_replan": 2}`, `blocked_count = 2`, final source counts all `0` |
| `--replan-budget 1` | `final_acceptance_outcome_counts = {"blocked_after_replan": 2}`, `replan_routed_count = 2`, `blocked_count = 2`, final source counts all `0` |

Both runs reported `embedding_compatibility.status = unknown`, no critic
acceptance issues, and no task/artifact integrity error in the final trace. The
blocking condition was material-empty execution: Analyst tasks failed with
incomplete numeric results, Researcher tasks failed with empty narrative
results, and final synthesis emitted a blocked/refusal answer because there were
no completed worker artifacts to carry forward.

Follow-up diagnostic surface:

| Run | Key diagnostic |
| --- | --- |
| `mas_e2e_smoke_failure_diagnostics_2026-06-07` | `worker_failure_count = 4`, `worker_failure_missing_artifact_count = 4`, `worker_failure_assignee_counts = {"Analyst": 2, "Researcher": 2}`, `worker_failure_reason_counts = {"incomplete numeric result": 2, "empty narrative result": 2, "missing_worker_artifact": 4}` |
| `mas_direct_worker_probe_2026-06-07` | Planner created `2` Analyst and `2` Researcher tasks, but direct Analyst status was `no_retrieved_docs = 2` and direct Researcher status was `no_raw_retrieval = 2`; store inventory reported `chroma_count = 0`, `bm25_doc_count = 0`, `parent_count = 0`, and `structure_graph_node_count = 0` |
| empty-store preflight | `mas_e2e_smoke` now stops before `VectorStoreManager` / LLM work when the Chroma collection exists but embeddings and sidecar material are all zero; the live default run fails in about `5s` with `Store appears empty for MAS smoke` |
| `mas_default_valid_store_restored_2026-06-07` | Default store moved to the populated Samsung 2023 policy-gate store and the smoke derives embedding runtime from store signature; override-free live run reports `accepted_without_replan = 2`, `blocked_count = 0`, `integrity_error_count = 0`, `worker_failure_count = 0`, final source tasks `4`, artifacts `8`, and evidence refs `55` |
| source-controlled compact baseline | `tests/fixtures/mas_e2e_smoke/default_valid_store_contract_baseline.json` now captures the reviewed valid-store compact contract; `check_mas_e2e_smoke_contract` uses it by default while raw live smoke output remains local-only |

The follow-up changed only smoke observability and CLI robustness: failed worker
diagnostics are now surfaced per case and in the summary, and `--output` creates
its parent directory before writing. The raw JSON remains a local-only
experiment artifact.

### 해석

- The new smoke outcome contract is doing useful work: it distinguishes
  `blocked_without_replan` from `blocked_after_replan` without manual trace
  reading.
- This is not a critic acceptance bug. Critic rejection issue counts stayed
  `0`; the final close was blocked by lack of source material.
- The direct worker probe separated the immediate blocker from planner,
  self-reflection, critic, and final merge behavior. The empty-store preflight
  now prevents API waste when collection and sidecar counts are all zero, and
  the default smoke has been restored to a populated store with matching
  store-signature embedding runtime selection.


## 큰 흐름

버전 흐름을 큰 설계 변화 기준으로 요약하면 다음과 같다.

1. **저비용 ingest 후보 탐색**
   - `plain`, `parent_only`, `selective` 계열을 비교
2. **multi-company generalization**
   - 삼성전자 1건에서 좋아 보이던 후보가 다른 기업에서도 재현되는지 확인
3. **query-stage / answer-stage failure 분리**
   - abstention, risk drift, business over-extension을 분리해서 보기 시작
4. **structured evidence / compression / validation**
   - answer generation을 free-form generation보다 compression 문제로 재정의
5. **single-document Golden Dataset + evaluator 우선**
   - 이제는 multi-company 실험보다, 단일 문서 기준선과 metric을 먼저 고정하는 단계로 이동

---

## v1 Legacy Local Test

참조:

- [archive/v1_legacy_local_test_2026-04-16](../../benchmarks/archive/v1_legacy_local_test_2026-04-16)

### 코드 / 설정 변화

- 초기 low-cost retrieval 비교
- 삼성전자 2024 사업보고서 1건 기준
- 후보 비교:
  - `plain_2500_320`
  - `contextual_all_2500_320`
  - `contextual_parent_only_2500_320`
  - `contextual_selective_2500_320`
  - `contextual_1500_200`

### 핵심 결과

- `contextual_all_2500_320`
  - screening 통과
- `plain_2500_320`
  - 비용은 거의 없지만 risk retrieval miss
- `contextual_parent_only_2500_320`
  - 숫자 질문에서 retrieval miss
- `contextual_selective_2500_320`
  - 비용 절감 폭이 작고 business overview miss
- `contextual_1500_200`
  - 더 느리고 business overview miss

### 해석

- 저비용 후보는 가능성이 있었지만 아직 retrieval 품질이 충분히 안정적이지 않았다.
- 이후 실험은 selective rule과 parent-child 변형을 더 세밀하게 다듬는 방향으로 넘어갔다.

---

## v2 Low-Cost Retrieval

참조:

- [v2_low_cost_2026-04-16/summary.md](../../benchmarks/results/v2_low_cost_2026-04-16/summary.md)

### 코드 / 설정 변화

- benchmark 전용 ingest mode 확장
  - `contextual_parent_hybrid`
  - `contextual_selective_v2`
- selector reason, contamination, failure example 기록 강화

### 핵심 결과

- `contextual_parent_only_2500_320`
  - screening 통과
  - baseline 대비
    - `API calls -86.7%`
    - `ingest time -77.8%`
- `contextual_selective_v2_2500_320`
  - 비용 절감은 컸지만 business overview miss로 탈락
- `contextual_parent_hybrid_2500_320`
  - 통과는 했지만 baseline보다 비싸 실익이 없었음

### 해석

- “저비용 후보도 품질 하한선을 넘길 수 있다”는 가능성을 처음 보여준 버전이다.
- 다만 삼성전자 1건만으로는 일반화 판단이 불가능해, 다음 단계는 다기업 일반화 검증으로 이동했다.

---

## v3 Generalization

참조:

- [v3_generalization_2026-04-16/cross_company_summary.md](../../benchmarks/results/v3_generalization_2026-04-16/cross_company_summary.md)

### 코드 / 설정 변화

- 기업별 canonical eval dataset 도입
  - 삼성전자
  - SK하이닉스
  - NAVER
- cross-company summary와 winner ranking 생성

### 핵심 결과

- 공통 screening 통과 후보 없음
- `삼성전자`
  - `contextual_parent_hybrid_2500_320`만 통과
- `SK하이닉스`
  - `contextual_all_2500_320`만 통과
- `NAVER`
  - 통과 후보 없음

### 해석

- 삼성전자 1건에서 좋아 보인 후보가 다른 기업에서는 재현되지 않았다.
- 특히 NAVER는 `section_path` 비정상 누적과 business overview retrieval 문제가 드러나, parser / evaluation 보정이 먼저 필요하다는 결론으로 이어졌다.

---

## v4 Generalization Fix

참조:

- [v4_generalization_fix_2026-04-17/cross_company_summary.md](../../benchmarks/results/v4_generalization_fix_2026-04-17/cross_company_summary.md)

### 코드 / 설정 변화

- NAVER `section_path` heading-level 정규화
- numeric section alias 확장
  - `매출현황`
  - `재무제표`
  - `요약재무`
  - `연결재무제표`
  - `연결재무제표 주석`
- answerable query 평가에서 full abstention 패턴만 강하게 페널티
- release generalization을 회사별 job으로 분리해 partial / completed run을 지원

### 핵심 결과

- `run_status = completed`
- 3개 기업 공통 screening 통과 후보 없음

후보별 요약:

- `contextual_all_2500_320`
  - 가장 안정적인 baseline
  - 평균 full eval:
    - `faithfulness 0.453`
    - `context recall 0.589`
- `contextual_parent_only_2500_320`
  - 평균 절감:
    - `API calls -86.0%`
    - `ingest time -84.7%`
    - `estimated cost -86.8%`
  - 그러나 numeric / risk / R&D에서 answerable smoke abstention 반복
- `contextual_selective_v2_2500_320`
  - 평균 절감:
    - `API calls -59.6%`
    - `ingest time -61.6%`
    - `estimated cost -60.6%`
  - 그러나 business overview / risk miss 반복
- `contextual_parent_hybrid_2500_320`
  - 평균 비용 이점이 없고 baseline보다 비싼 경우가 있었음

### 해석

- parser / evaluation 보정 이후에도 저비용 후보의 주된 문제는 ingest 비용이 아니라 query-stage abstention과 category-specific retrieval miss였다.
- 그래서 다음 실험 우선순위는
  - 더 싼 ingest mode 추가
  보다
  - numeric / risk / R&D abstention 완화
  - NAVER business overview retrieval 개선
  - missing-information hallucination 억제
  로 이동했다.

---

## dev_fast Cache Check

참조:

- [dev_fast_cache_check_2026-04-17/삼성전자-2024/summary.md](../../benchmarks/results/dev_fast_cache_check_2026-04-17/삼성전자-2024/summary.md)

### 코드 / 설정 변화

- `dev_fast` / `release_generalization` 프로파일 분리
- `Hybrid Cache` 도입
  - `stores/...`
  - `context_cache/...`
- 같은 설정 재실행 시 contextual ingest API를 다시 호출하지 않도록 변경

### 핵심 결과

- 삼성전자 1회사 screening-only를 2회 연속 실행
- 1차 run:
  - 약 `13분 16초`
- 2차 run:
  - 약 `5분 27초`
- 2차 run에서는 모든 후보가:
  - `cache_hit = true`
  - `cache_level = store`
  - `ingest.api_calls = 0`
  - `ingest.elapsed_sec = 0.0`

### 해석

- 반복 실험에서 가장 비싼 contextual ingest 비용을 다시 쓰지 않는 구조가 실제로 검증됐다.
- 이후 일상 루프는 `dev_fast`, release-grade 비교는 회사별 분리 실행이 기본 운영 방식으로 자리 잡았다.

---

## Current Takeaway

현재까지의 실험 흐름은 이렇게 요약할 수 있다.

1. 삼성전자 1건에서 저비용 후보 가능성을 확인했다.
2. 다기업 일반화로 확장하자 공통 승자가 사라졌다.
3. parser / evaluation / workflow를 보정했지만, 핵심 실패는 여전히 query-stage abstention과 category-specific retrieval miss였다.
4. 따라서 지금의 핵심 과제는 “더 싼 ingest mode를 찾는 것”보다 “현재 저비용 후보가 왜 답을 포기하는지 줄이는 것”이다.

---

## Graph Micro + Zero-Cost Prefix (2026-04-22)

참조:

- [graph_micro_2026-04-22](../../benchmarks/results/graph_micro_2026-04-22)
- [graph_micro_constrained_2026-04-22](../../benchmarks/results/graph_micro_constrained_2026-04-22)
- [graph_micro_prefix_2026-04-22](../../benchmarks/results/graph_micro_prefix_2026-04-22)

### 코드 / 설정 변화

- `document-structure graph` 추가
  - `parent_id`
  - `sibling_prev`, `sibling_next`
  - `section_lead`
  - `described_by_paragraph`
  - `table_context`
- `retrieve -> expand_via_structure_graph -> evidence` 경로 추가
- `compact_review.md/html` 추가
  - 질문 / 예시 답변 / 실제 답변 / retrieved chunks / runtime evidence를 간결하게 검수하기 위한 artifact

### 1차 결과

- `plain + graph expansion`만으로는 `contextual_all` 대체 실패
- 비용/시간은 크게 줄었지만
- `q_009` 재무 리스크 질문에서 seed retrieval miss가 반복
- graph expansion은 잘못 잡힌 `이사회`, `경영진단`, `감사제도` 섹션을 더 증폭시키는 경우가 있었다

### 2차 결과: constrained graph

- 제약 추가:
  - `table -> paragraph prev만 허용`
  - `sibling_next 제거`
  - `max_docs = 8`
- noise는 줄었지만, seed retrieval miss 자체는 해결하지 못했다

### 3차 결과: zero-cost prefix

- `plain` / `plain_graph` 인덱싱 텍스트 앞에
  - `[섹션]`
  - `[분류]`
  - `[키워드]`
  를 hardcoded prefix로 삽입
- 목적: LLM 비용 없이 vocabulary mismatch를 줄여 seed retrieval을 보강

핵심 결과:

- `q_009` 재무 리스크 질문
  - prefix 후 plain 계열에서도 `hit@k = 1.0`
  - `plain_graph_1500_200`는 `section_match = 0.75`
- `q_001` 연결 기준 매출액 질문
  - 여전히 `연결재무제표 주석` 표들에 많이 쏠림
  - answerable abstention이 남음

### 해석

- graph expansion은 retrieval replacement가 아니라 **retrieval booster**다
- `q_009`의 핵심 병목은 graph가 아니라 seed retrieval miss였고, 이는 zero-cost prefix로 크게 개선됐다
- 반면 `q_001`은 retrieval만의 문제가 아니라
  - `연결 기준 매출액`
  - `매출 및 수주상황`
  - `연결 손익계산서`
  - `요약재무정보`
  를 하나의 target family로 보지 못하는 **numeric query planning / target alignment** 문제로 더 좁혀졌다

---

## v5 / v6 / v7 Faithfulness Follow-up

참조:

- [v5_fulleval_2026-04-20/삼성전자-2024/summary.md](../../benchmarks/results/v5_fulleval_2026-04-20/삼성전자-2024/summary.md)
- [v6_faithfulness_guard_2026-04-20/삼성전자-2024/summary.md](../../benchmarks/results/v6_faithfulness_guard_2026-04-20/삼성전자-2024/summary.md)
- [v7_faithfulness_guard_refine_2026-04-20/삼성전자-2024/summary.md](../../benchmarks/results/v7_faithfulness_guard_refine_2026-04-20/삼성전자-2024/summary.md)

### 코드 / 설정 변화

- `v5`
  - query_type 6종 확장
  - retrieval lane 분리
  - risk evidence verbatim 제한
  - evaluator context 확장
- `v6`
  - business_overview / numeric / risk answer를 더 보수적으로 만드는 guard 추가
  - section bias와 output style 강화
- `v7`
  - 숫자 1개 / 개수 1개 질문을 더 짧게 답하도록 추가 제약

### 핵심 결과

- baseline `contextual_all_2500_320`의 삼성전자 5문항 full eval faithfulness:
  - `v5`: `0.380`
  - `v6`: `0.500`
  - `v7`: `0.600`
- 하지만 `v7`에서는:
  - `business_overview_001`, `business_overview_003` 회복
  - `risk_analysis_001`은 다시 `0.0`

### 해석

- 일부 metric 회복은 가능했지만, 질문 유형별 rule 추가가 다른 유형에서 새 부작용을 만들었다.
- 이건 “hardcoded rule을 더 붙이면 장기적으로 안 된다”는 신호로 해석한다.
- 따라서 이후 방향은 점수 자체를 더 올리는 것보다:
  - answer generation 원칙 문서화
  - 최근 rule inventory 분류
  - evidence compression 중심의 구조 재정의
로 옮긴다.

---

## Typed Compression / Validation and Sentence-Level Validator

참조:

- [dev_fast_cache_check_2026-04-17/삼성전자-2024/review.md](../../benchmarks/results/dev_fast_cache_check_2026-04-17/삼성전자-2024/review.md)
- [dev_fulleval_sentence_validator_2026-04-21/삼성전자-2024/summary.md](../../benchmarks/results/dev_fulleval_sentence_validator_2026-04-21/삼성전자-2024/summary.md)
- [dev_focus_validator_2026-04-21/삼성전자-2024/summary.md](../../benchmarks/results/dev_focus_validator_2026-04-21/삼성전자-2024/summary.md)

### 코드 / 설정 변화

- `compression -> validation`을 typed output으로 확장
  - `selected_claim_ids`
  - `draft_points`
  - `kept_claim_ids`
  - `dropped_claim_ids`
  - `unsupported_sentences`
  - `sentence_checks`
- sentence-level validator 추가
- validator 결과를 그대로 쓰지 않고, 후처리에서
  - intro sentence 제거
  - 근거 없는 keep 강등
  - 중복 claim 제거
  - 과잉 일반화 문장 제거
  로 연결

### 핵심 결과

- typed artifact는 review artifact에 안정적으로 남는다.
- 하지만 5문항 full eval 기준으로는:
  - retrieval / citation 지표는 소폭 개선
  - `contextual_all`의 answer 품질 지표는 오히려 하락
- 3문항 focus run에서는 처음으로 실제 pruning이 의미 있게 발생했다.
  - `contextual_all / risk_analysis_001`
    - 도입 문장 `drop_redundant`
  - `contextual_parent_only / risk_analysis_001`
    - 도입 문장 `drop_unsupported`
    - `dropped_claim_ids = ev_002`

### 해석

- validator는 이제 “보이기만 하는 단계”는 지났다.
- 하지만 아직 “잘 자르는 validator”는 아니다.
- 현재 병목은 validator 강도보다, `business_overview` / `risk`에서 어떤 claim을 같이 선택하느냐에 더 가깝다.
- 따라서 다음 단계는 validator를 더 세게 만드는 것보다:
  - `claim_type`
  - `topic_key`
  - group-wise selection
  중심으로 compression 앞단을 더 구조화하는 쪽이다.

---

## Numeric Evaluator Follow-up

참조:

- [../architecture/numeric_evaluation_architecture.md](../architecture/numeric_evaluation_architecture.md)
- [dev_fast_cache_check_2026-04-17/삼성전자-2024/review.md](../../benchmarks/results/dev_fast_cache_check_2026-04-17/삼성전자-2024/review.md)

### 코드 / 설정 변화

- structured runtime evidence를 benchmark 결과에 기록
- 숫자 질문 false fail을 generation 문제가 아니라 evaluator 문제로 분리해서 해석
- `numeric_fact`는 일반 서술형 `faithfulness`와 분리해 다루는 architecture 방향 문서화

### 핵심 관찰

- `numeric_fact_001`은 사람이 보기엔 사실상 맞는 답인데도 `faithfulness = 0.0`이 반복됐다.
- 대표 케이스:
  - canonical 표현: `300조 8,709억원`
  - actual answer 표현: `300,870,903 백만원`
- runtime evidence와 retrieved context는 충분했기 때문에, 이 케이스는 retrieval failure보다 evaluator limitation에 가깝다고 판단했다.

### 해석

- 숫자 질문은 값 동치성, grounding, retrieval support를 따로 봐야 한다.
- 따라서 다음 단계는 generation rule 추가보다:
  - `Numeric Extractor`
  - `Numeric Equivalence Checker`
  - `Grounding Judge`
  - `Retrieval Support Check`
  - `Conflict Resolver`
  구조를 실제 evaluator에 반영하는 것이다.

---

## Numeric Evaluator Implementation

참조:

- [dev_fast_cache_check_2026-04-17/삼성전자-2024/results.json](../../benchmarks/results/dev_fast_cache_check_2026-04-17/삼성전자-2024/results.json)
- [dev_fast_cache_check_2026-04-17/삼성전자-2024/review.csv](../../benchmarks/results/dev_fast_cache_check_2026-04-17/삼성전자-2024/review.csv)

### 코드 / 설정 변화

- `src/ops/evaluator.py`에 `numeric_fact` 전용 evaluator path 추가
  - `Numeric Extractor`
  - `Numeric Equivalence Checker`
  - `Grounding Judge`
  - `Retrieval Support Check`
  - `Conflict Resolver`
- `src/ops/benchmark_runner.py`가 numeric evaluator 결과를 benchmark artifact에 직렬화

### 핵심 결과

- `numeric_fact_001`
  - generic `faithfulness = 0.0`
  - `numeric_equivalence = 1.0`
  - `numeric_grounding = 1.0`
  - `numeric_retrieval_support = 1.0`
  - `numeric_final_judgement = PASS`

### 해석

- 숫자 질문에서 generic `faithfulness`와 실제 정답성 / grounding 해석이 갈라질 수 있다는 점이 benchmark 결과에 명확히 드러났다.
- 이 시점부터 `numeric_fact`의 주 판정은 `numeric_final_judgement`로 보고, generic `faithfulness`는 보조 참고치로 낮춰 해석한다.

---

## Typed Compression / Validation Outputs

참조:

- [../architecture/answer_generation_principles.md](../architecture/answer_generation_principles.md)
- [../architecture/architecture_direction.md](../architecture/architecture_direction.md)

### 코드 / 설정 변화

- `src/agent/financial_graph.py`
  - `CompressionOutput`
  - `ValidationOutput`
- `src/ops/evaluator.py`
  - per-question 결과에 claim selection / drop 정보 추가
- `src/ops/benchmark_runner.py`
  - `results.json`, `review.csv`, `review.md`에 새 필드 직렬화

추가된 필드:

- `selected_claim_ids`
- `draft_points`
- `kept_claim_ids`
- `dropped_claim_ids`
- `unsupported_sentences`

동시에 질문 wording을 직접 읽어 output style을 바꾸던 local optimization은 제거했다.

### 핵심 의의

- 기존 `compression -> validation`은 구조적으로는 분리됐지만, 결과 artifact에는 여전히 문자열 중심 정보만 남았다.
- 이제는 reviewer artifact에서
  - 어떤 claim을 선택했는지
  - 무엇을 버렸는지
  - 어떤 문장을 unsupported로 제거했는지
  를 직접 볼 수 있게 됐다.

### 현재 상태

- 코드 반영 완료
- 문법 검증 완료
- 아직 이 새 typed field를 포함한 full eval 재실행은 하지 않았다

### 해석

- 이 단계의 목적은 점수 개선이 아니라 **failure analysis를 더 설명 가능하게 만드는 것**이다.
- 다음 실험부터는 `business_overview` / `risk` 회귀를 “점수 변화”가 아니라 “claim 선택과 제거 흐름”까지 포함해 분석할 수 있어야 한다.

---

## Reset Point: Single-Document Evaluation First

최근 validator, numeric evaluator, typed artifact까지 진행한 뒤 내린 결론은 다음과 같다.

- retrieval / generation의 국소 조정은 계속 가능하다
- 하지만 그 전에 “무엇을 좋은 답으로 볼 것인가”를 단일 문서에서 먼저 고정해야 한다

이 판단의 이유:

- multi-company benchmark는 parser 차이, section alias 차이, evaluator 차이가 함께 섞인다
- local rule이 늘어나면 benchmark-specific optimization으로 흐르기 쉽다
- single-document 기준선이 먼저 있어야 이후 구조 변경을 더 신뢰성 있게 비교할 수 있다

따라서 다음 큰 방향은:

1. 삼성전자 2024 사업보고서 1건 기준 Golden Dataset 구축
2. 질문 taxonomy 확정
3. evaluator 분리
4. single-document benchmark runner 정리
5. 그 다음에만 retrieval / compression / validation 실험 재개

이 전략은 [../evaluation/single_document_eval_strategy.md](../evaluation/single_document_eval_strategy.md)에 정리했다.

---

## Prefix + Selective Contextual Retrieval Focus Run (2026-04-23)

참조:

- [dev_fast_focus_selective_prefix_2026-04-23/삼성전자-2024/summary.md](../../benchmarks/results/dev_fast_focus_selective_prefix_2026-04-23/삼성전자-2024/summary.md)
- [dev_fast_focus_selective_prefix_2026-04-23/삼성전자-2024/results.json](../../benchmarks/results/dev_fast_focus_selective_prefix_2026-04-23/삼성전자-2024/results.json)

### 코드 / 설정 변화

- `src/ops/benchmark_runner.py`
  - `contextual_selective_v2` 경로가 `use_zero_cost_prefix`를 함께 받을 수 있도록 확장
- `benchmarks/profiles/dev_fast_focus.json`
  - `contextual_selective_v2_prefix_2500_320` 후보 추가

### 핵심 결과

- `plain_prefix_2500_320`
  - retrieval seed는 강했지만 `numeric_fact_001`에서 “구체적인 수치 정보가 없다”고 답함
  - `numeric_final_judgement = FAIL`
- `contextual_selective_v2_prefix_2500_320`
  - `screen_pass = yes`
  - `faithfulness 0.675`
  - `answer_relevancy 0.580`
  - `context_recall 0.625`
  - `numeric_pass = 1.000`

질문별 메모:

- `numeric_fact_001`
  - `plain_prefix`는 실패
  - `selective_v2_prefix`는 `300조 8,709억원`으로 복구
- `risk_analysis_001`
  - `selective_v2_prefix`는 `위험관리 및 파생거래` 중심 retrieval과 grounded answer를 유지

### 해석

- `Zero-Cost Prefix`만으로는 표 기반 숫자 질문의 구조적 희소성을 충분히 복원하지 못한다.
- `table` 청크에만 선택적으로 contextualization을 주고 prefix를 함께 유지하는 조합이 더 현실적인 타협점이다.
- 이 시점부터 low-cost 방향의 주력 후보는 `plain_prefix`보다 `contextual_selective_v2_prefix`가 된다.

### 다음 단계

- retrieval / ingest 코드는 잠시 freeze
- numeric evaluator aggregate / reporting을 먼저 정리
- 그 다음 `business_overview` / `risk` generation 튜닝으로 넘어가기

---

## Evaluator + Routing Cascade v1 (2026-04-23)

참조:

- [dev_fast_focus_eval_tuned_2026-04-23/삼성전자-2024/summary.md](../../benchmarks/results/dev_fast_focus_eval_tuned_2026-04-23/삼성전자-2024/summary.md)
- [dev_fast_focus_routing_cascade_2026-04-23/삼성전자-2024/summary.md](../../benchmarks/results/dev_fast_focus_routing_cascade_2026-04-23/삼성전자-2024/summary.md)
- [../architecture/query_routing_rearchitecture.md](../architecture/query_routing_rearchitecture.md)

### 코드 / 설정 변화

- evaluator
  - numeric PASS 시 generic faithfulness short-circuit
  - completeness judge 및 reason 추가
- query routing
  - `intent + format_preference` state 분리
  - semantic router fast-path
  - few-shot LLM fallback
  - rerank / retrieval block-type 보정을 `format_preference` 기준으로 전환

### 핵심 결과

- evaluator tuning 후
  - `numeric_fact_001`에서 `raw_faithfulness=0.0`이어도 `faithfulness=1.0` 보정이 실제로 적용됨
- routing cascade v1 후 `contextual_selective_v2_prefix_2500_320`
  - `faithfulness 0.925`
  - `answer_relevancy 0.632`
  - `context_recall 0.625`
  - `completeness 0.775`
  - `numeric_pass 1.000`
- `risk_analysis_001`
  - semantic top-1이 흔들려도 fast-path가 억제되고 fallback에서 `risk / paragraph`로 교정
- `business_overview_001`
  - fallback에서 `business_overview / mixed`로 교정
- `business_overview_003`
  - fast-path로 `business_overview / mixed`

### 해석

- 이 시점부터 병목은 “retrieval 규칙을 더 붙일 것인가”보다
  - query routing variance를 얼마나 줄일 것인가
  - routing metadata를 결과에서 어떻게 읽을 것인가
로 이동했다.
- selective contextual + prefix 조합의 retrieval 자체는 충분히 유망했고,
  최종 품질을 흔들던 큰 축 중 하나가 routing variance였음이 확인됐다.

### 다음 단계

- `intent / format_preference / routing_source`를 benchmark artifact에 노출
- semantic router threshold와 canonical query set을 Golden Set 기준으로 보정
- fallback 로그를 semantic router 자산으로 다시 흡수

## Routing Calibration + Ambiguity Guard (2026-04-24)

참조:

- [query_router_calibration_2026-04-24/summary.md](../../benchmarks/results/query_router_calibration_2026-04-24/summary.md)
- [query_router_calibration_guard_2026-04-24/summary.md](../../benchmarks/results/query_router_calibration_guard_2026-04-24/summary.md)
- [dev_fast_focus_routing_calibrated_2026-04-24/삼성전자-2024/summary.md](../../benchmarks/results/dev_fast_focus_routing_calibrated_2026-04-24/삼성전자-2024/summary.md)
- [dev_fast_focus_routing_guard_2026-04-24/삼성전자-2024/summary.md](../../benchmarks/results/dev_fast_focus_routing_guard_2026-04-24/삼성전자-2024/summary.md)

### 코드 / 설정 변화

- `benchmarks/golden/query_routing_eval_v1.json`
  - held-out routing 검증셋 추가
- `src/ops/calibrate_query_router.py`
  - semantic router score / margin calibration 스크립트 추가
- `benchmarks/golden/query_routing_canonical_v1.json`
  - risk canonical query 2개 추가
- `src/agent/financial_graph.py`
  - 전역 threshold 완화 시도
  - confusion-pair dynamic margin guard 추가

### 핵심 결과

1. 전역 threshold 완화만 적용한 run
   - calibration 기준으로는
     - coverage `0.733 -> 0.833`
     - accuracy `1.000 -> 1.000`
   - 하지만 실제 `dev_fast_focus_routing_calibrated_2026-04-24`에서는
     - `risk_analysis_001`이 `business_overview / mixed / semantic_fast_path`로 오분류
     - selective-prefix 품질이 오히려 악화

2. ambiguity guard + risk canonical 보강 적용 후
   - `dev_fast_focus_routing_guard_2026-04-24`에서
     - `risk_analysis_001`이 다시 `risk / paragraph / semantic_fast_path`로 복구
     - `business_overview_001`은 애매해서 `llm_fallback`으로 전환
   - 즉 전역 threshold보다
     - canonical query 품질
     - confusion pair margin
     - few-shot fallback
     의 조합이 더 안정적이었다

### 해석

- semantic router는 전역 threshold sweep만으로 운영하기 어렵다
- 특히 `business_overview`, `risk`, `numeric_fact`는 class boundary보다 **confusion pair safety**가 더 중요하다
- routing은 다시 안정화됐고, 현재 병목은
  - `numeric_fact` evidence extraction
  - `risk` / `business_overview` generation completeness
  쪽으로 이동했다

## Numeric Extractor Node (2026-04-26)

참조:

- [numeric_extractor_v2_2026-04-26/삼성전자-2024/summary.md](../../benchmarks/results/numeric_extractor_v2_2026-04-26/삼성전자-2024/summary.md)

### 코드 / 설정 변화

- `src/agent/financial_graph.py`
  - `NumericExtraction` Pydantic 스키마 추가 (`period_check`, `consolidation_check`, `unit`, `raw_value`, `final_value`)
  - `_extract_numeric_fact` 노드: `compress → validate` bypass, CoT structured output으로 수치 추출
  - `_route_after_expand`: `intent == "numeric_fact"` → `numeric_extractor` → `cite` 분기

### 핵심 결과

| 실험 | numeric_pass | faithfulness | ingest cost |
|---|---|---|---|
| contextual_all | 1.000 | 0.700 | $0.919 |
| contextual_parent_only | 1.000 | 0.875 | $0.130 |
| plain_prefix | 0.000 | 0.454 | $0.000 |
| selective_v2_prefix | **1.000** | 0.825 | $0.401 |

- `selective_v2_prefix`: routing_guard 대비 FAIL → PASS 회복
- `plain_prefix`: UNCERTAIN 지속 — plain chunk에 수치 추출 실패, 별도 추적 필요

### 해석

- `compress → validate` 파이프라인은 표 기반 숫자 추출에 구조적으로 취약하다
- `numeric_extractor`는 당기/전기, 연결/별도, 단위를 CoT로 먼저 확인하고 raw_value를 추출
- grounding judge는 numeric_extractor가 생성한 synthetic evidence_item 기준으로 판정
- `plain_prefix`의 numeric_fact 실패는 ingest-side 문제로 별도 추적

## Concept Runtime Gap Gate Answer-Composition Closure (2026-06-04)

참조:

- `benchmarks/results/concept_gate_refresh_after_answer_composition_2026-06-04/`

### 코드 / 설정 변화

- `answer_slots`와 `resolved_calculation_trace`를 최종 answer assembly의
  canonical surface로 더 강하게 사용한다.
- lookup sibling recovery는 table metadata에서 값을 찾더라도 primary row label
  match와 ambiguous context-table guard를 통과해야만 값을 승격한다.
- ratio / lookup direct structured operands도 scope가 명시되지 않은 경우
  context-dependent segment/total table row를 사용하지 않는다.
- aggregate answer composition은 source-visible display와 evidence-visible
  impact relation을 우선하고, recomputed trace는 provenance metadata로 보존한다.

### 핵심 결과

- concept runtime gap gate 최신 store-fixed eval-only refresh:
  - `KBF_T2_018`: PASS
  - `POS_T1_057`: PASS
  - `SKH_T3_080`: PASS
  - `SAM_T3_028`: PASS
  - `CEL_T1_013`: PASS
  - `CEL_T3_040`: PASS
  - `KAB_T1_066`: PASS
- 전체 요약: `7 / 7 PASS`
- `POS_T1_057`는 segment/total context table의 `(718,937)` 또는
  `(1,180,096)` 값을 unscoped denominator로 쓰지 않고, notes evidence의
  `1,001,290백만원`을 denominator로 사용해 `3.5269배`를 계산한다.
- 검증:
  - runtime domain-language audit passed (`215` reviewed literals)
  - related answer-composition / lookup-recovery regression suite: `45` tests OK
  - `POS_T1_057` focused eval-only: faithfulness, completeness, context recall,
    retrieval hit, numeric pass rate all `1.000`
- Runtime/API cost follow-up:
  - `curated_concept_runtime_gap_gate.json` now records the same full-eval
    retrieval budgets used by the official runtime/policy gates:
    `retrieval_query_budget=8`, `focused_retrieval_query_budget=4`,
    `retry_retrieval_query_budget=1`
  - 2026-06-08 store-fixed `CEL_T1_013` budget canary preserved numeric
    `PASS`, faithfulness/completeness `1.000 / 1.000`, and artifact integrity
    `ok`
  - query-budget traces reduced primary query surfaces from `18 -> 8` and
    `15 -> 8`; fan-out audit reported `15` executed queries, `0` duplicates,
    and `1` state query-result cache reuse

### Broader Operation Contract Follow-up

- Pull 후 broader unittest에서 operand precision, value-local unit refinement,
  direct runtime evidence replacement, growth+narrative answer composition
  regressions이 드러났다.
- 수정은 특정 회사/문항 branch 없이 다음 일반 contract로 정리했다:
  - semantic contextual table row가 있으면 numeric proximity 후보보다 우선
  - direct quote/raw-row local unit은 table unit보다 우선하되, 확정 unit은
    weak metadata/claim만으로 바꾸지 않음
  - table-label metadata와 direct runtime evidence가 weak/stale lookup slot을
    교체할 수 있음
  - growth answer는 evidence-visible prior display를 보존하고, narrative
    fallback은 table-fragment noise를 sentence filter로 제거
- 검증:
  - `python -m src.ops.audit_runtime_domain_terms`: passed
  - related answer-composition / lookup-recovery regression suite: `182` tests OK
  - `python -m unittest tests.test_subtask_loop`: `91` tests OK
  - `python -m unittest discover -s tests`: `687` tests OK

### 해석

- 남은 blocker는 benchmark answer를 직접 맞추는 문제가 아니라
  answer-composition contract와 context-dependent table scope contract였다.
- 이번 closure는 특정 회사/문항/계정명 branch가 아니라, evidence schema와
  structured-cell metadata를 이용한 일반 runtime contract로 닫혔다.
- concept-only planner promotion 검토는 이제 "불합격 문항 고치기"가 아니라
  현재 7/7 gate를 baseline으로 잡고 runtime cost, promotion risk, task-ledger
  boundary를 관리하는 단계로 넘어간다.

## Retrieved Driver Evidence Preservation Follow-up (2026-06-07)

참조:

- `benchmarks/results/nav_t2_006_driver_doc_repair_evalonly_2026-06-07/`
  (local store-fixed repair artifact, not committed)

### 배경

- Same-trace duplicate guard 이후 `NAV_T2_006` diagnostic replay에서
  retrieval health는 유지됐지만 final answer가 source-visible growth driver
  하나를 빠뜨리는 현상이 다시 보였다.
- 이 실패는 retrieval miss나 benchmark-specific answer mismatch가 아니라,
  aggregate growth+narrative composition이 retrieved docs에 남아 있는
  policy-backed driver evidence를 evidence item으로 보존하지 못한 문제로
  분류했다.

### 코드 / 테스트 변화

- `src/agent/financial_graph_calculation.py`
  - aggregate evidence assembly 전에 policy-backed narrative driver groups를
    확인한다.
  - 해당 driver surface가 current evidence에는 없지만 `seed_retrieved_docs`
    또는 `retrieved_docs`에 source-visible sentence로 남아 있으면
    `retrieved_driver::*` evidence item으로 승격한다.
  - 회사명, benchmark ID, commerce-specific keyword branch는 추가하지 않고,
    retrieval policy가 제공한 driver groups와 retrieved evidence surface만
    사용한다.
- `tests/test_subtask_loop.py`
  - retrieved docs가 missing growth driver evidence를 보강하는 helper test
    추가.
  - aggregate growth+narrative answer가 promoted retrieved-driver evidence를
    final answer와 selected claim ids에 반영하는 regression test 추가.

### 핵심 결과

- Focused `NAV_T2_006` store-fixed eval-only repair:
  - faithfulness `1.000`
  - completeness `1.000`
  - context recall `1.000`
  - retrieval hit@k `1.000`
  - error rate `0.0%`
- 검증:
  - targeted subtask-loop regression tests: `2` tests OK
  - runtime domain-language audit passed
  - full unittest discovery passed before PR publication

### 해석

- Cross-trace repeated retrieval surfaces remain a runtime/cost topic, not a
  quality blocker by themselves.
- The quality fix is evidence preservation: if the planner/retrieval policy has
  already recovered a relevant driver sentence, aggregate composition must keep
  it visible rather than relying on a later synthesizer to reconstruct it.
- At this point, the remaining non-gate quality cleanup target was
  material-gap replan behavior such as `KBF_T2_043`, not the closed
  `NAV_T2_006` mixed-synthesis gap. This was later closed by the
  `KBF_T2_043` material-gap follow-up described below.

## KBF_T2_043 Material-Gap Follow-Up Close (2026-06-07)

Reference:

- PR #35: `Improve contract-driven narrative numeric handling`

### Result

- Focused store-fixed eval-only replay closed the material-gap/narrative
  numeric blocker.
- Metrics:
  - `numeric_final_judgement = PASS`
  - `faithfulness = 1.0`
  - `numeric_grounding = 1.0`
  - `context_recall = 0.9`
  - `completeness = 0.7`
  - `retrieval_hit_at_k = 0.0`
  - `absolute_error_rate = 0.0`
  - `unit_consistency_pass = 1.0`

### Interpretation

- The original non-gate inventory result remains useful as historical
  screening evidence: `KBF_T2_043` was not a query-budget truncation failure.
- The follow-up fix was contract-driven rather than benchmark-specific:
  material-gap detection, source-visible growth display preservation, and
  policy-required realized context handling were generalized through runtime
  contracts and policy data.
- Remaining work for this case is broader replay and completeness/render
  calibration, not a known material-gap runtime blocker.

## Concept Gate Growth Operand Hardening (2026-06-08)

References:

- `benchmarks/results/tmp_concept_gate_budgeted_evalonly_direct_priority_full_2026-06-08/`
  (local budgeted full eval-only artifact, not committed)
- `benchmarks/results/tmp_kbf_t2_018_recovery_skip_current_2026-06-08/`
  (local focused KBF canary artifact, not committed)
- `benchmarks/results/tmp_pos_t1_057_unit_check_2026-06-08/`
  (local focused POS canary artifact, not committed)

### Background

- The frozen concept gate baseline remains
  `concept_runtime_gap_gate_7of7_2026-06-04`.
- A later budgeted full eval-only replay with the `8 / 4 / 1` retrieval budget
  completed all seven questions but reported `5 / 7` numeric PASS. This replay
  was useful as a stress signal, not as a replacement baseline.
- The observed failures were not patched with company, benchmark ID, or
  account-name branches:
  - `KBF_T2_018` exposed duplicate growth recovery where a current-period value
    with parentheses could be selected again as the prior-period display.
  - `POS_T1_057` passed standalone eval-only but showed full-replay
    unit/source path instability.
  - `KAB_T1_066` was numeric PASS but still a product-quality residual because
    the answer refused to calculate CIR in the observed full replay.

### Code / Test Changes

- Growth-rate extraction now lets complete reconciliation rows override stale
  dependency outputs, matching the existing direct-row preference used for
  other calculation families.
- Supplemental operand merge keys required operands by label, role, and period,
  so same-label current/prior rows do not mask each other.
- Evidence-based prior-period recovery compares compact numeric displays, so
  `(3,146,409)` and `3,146,409백만원` are recognized as the same current value
  and skipped when searching for the prior value.
- Aggregate growth+narrative synthesis now blocks narrative numeric claims when
  required structured numeric slots are still unresolved and a safe partial
  answer is available.

### Results

- Focused `KBF_T2_018` canary after compact-current recovery:
  - `numeric_final_judgement = PASS`
  - faithfulness `1.000`
  - completeness `1.000`
- Focused `POS_T1_057` standalone eval-only:
  - `numeric_final_judgement = PASS`
  - faithfulness `1.000`
  - completeness `1.000`
  - calculator result `3.5269배`
- Validation:
  - focused growth/aggregate regression: `4` tests OK
  - `python -m unittest tests.test_structured_operand_extraction tests.test_semantic_numeric_plan tests.test_operation_contracts tests.test_subtask_loop`:
    `417` tests OK
  - `python -m src.ops.audit_runtime_domain_terms`: passed

### Interpretation

- This is a runtime hardening follow-up to the frozen concept gate, not a new
  full `7 / 7` stable proof.
- A new freeze should require another monitored full seven-question eval-only
  replay after this patch, or a conscious decision to treat the existing
  2026-06-04 baseline plus focused KBF/POS canaries as sufficient for the
  current checkpoint.

## Aggregate Task-Ledger Superseded Trace Cleanup (2026-06-09)

### Code / Contract Change

- Added `TaskStatus.SUPERSEDED` to the DART task schema.
- `_project_task_artifact_trace()` now exposes task resolution metadata:
  `resolution_status`, `superseded_by_task_id`, `superseded_by_artifact_id`,
  and `notes`.
- Aggregate finalization now marks pending/partial planned tasks as
  `superseded` when their target slot is already covered by the final aggregate
  projection or by final subtask answer slots/operands.
- Matching is generic and reuses existing slot key/period extraction. No
  company name, benchmark ID, or metric-specific runtime branch was added.

### Validation

- `python -m unittest tests.test_subtask_loop tests.test_operation_contracts`:
  `339` tests OK.
- `python -m src.ops.audit_runtime_domain_terms --summary`: passed with `215`
  reviewed literals.
- `git diff --check`: passed.

### Interpretation

- This change improves trace readability only. It does not alter retrieval,
  operand selection, calculation, or answer composition.
- KAB focused probes during the cleanup still showed upstream replan and
  operand-coverage volatility, including long latency and occasional partial
  final answers. Treat that as the next runtime blocker, not as solved by the
  ledger cleanup.

## Concept Gate Residual Unit/Artifact Hardening (2026-06-09)

### Context

- The latest seven-question concept runtime gap replay before this change had
  recovered five clean PASS rows, but still exposed:
  - `POS_T1_057`: a ratio answer of `0.0035배` caused by a generated operand
    carrying `천원` while the table metadata and source row were `백만원`;
  - `KAB_T1_066`: a numeric PASS masking a partial refusal, because the
    denominator evidence was preserved as reconciliation artifact refs but not
    promoted into the final ratio operand set.

### Code / Contract Change

- Added a calculation-time KRW unit repair that trusts table-backed
  `unit_hint` only under narrow provenance conditions:
  table evidence, raw value visible in the table surface, KRW display units on
  both sides, and at least `100x` scale disagreement.
- Expanded reconciliation artifact candidate IDs from active
  `evidence_refs` / `source_evidence_ids` and normalized `recon::` prefixes so
  preserved structured evidence refs can be tested by the existing operand
  acceptance contracts.
- The change does not add company names, question IDs, or metric-specific
  runtime branches.

### Results

- Focused `POS_T1_057` eval-only:
  - `numeric_final_judgement = PASS`
  - faithfulness `1.000`
  - completeness `1.000`
  - refusal accuracy `1.000`
  - calculator result `3.5269배`
- Focused `KAB_T1_066` eval-only:
  - `numeric_final_judgement = PASS`
  - faithfulness `1.000`
  - completeness `1.000`
  - refusal accuracy `1.000`
  - calculator result `37.47%`
- Validation:
  - `python -m unittest tests.test_operation_contracts tests.test_structured_operand_extraction`:
    `201` tests OK.
  - `python -m unittest tests.test_subtask_loop`: `166` tests OK.
  - `python -m src.ops.audit_runtime_domain_terms --summary`: passed.

### Interpretation

- The focused failures are closed under store-fixed eval-only.
- A full seven-question replay was attempted with heartbeat logging at
  `benchmarks/results/concept_gate_fresh_after_ratio_growth_hardening_2026-06-08/full7_after_artifact_unit_repair_2026-06-09.log`
  but was stopped after `KBF_T2_018` remained in the first question for more
  than `10` minutes with heartbeat only. This is a run-latency artifact, not a
  completed full-gate proof.

## MIX_T1_046 Resolved Dependency Grounding Close (2026-05-28)

참조:

- `benchmarks/results/naver_mix_t1_046_2026-05-28-grounding-fix`

### 코드 / 설정 변화

- `src/ops/evaluator.py`
  - deterministic numeric grounding override가 resolved `task_output:*`
    operand provenance를 인정하도록 일반화
  - 조건은 `dependency_resolved = true`, `source_anchor`, 그리고
    `source_task_id` 또는 `source_slot`이 있는 경우로 제한
  - unresolved `task_output:*` operand는 기존처럼 grounded로 보지 않음
- `tests/test_evaluator_runtime_projection.py`
  - resolved task-output dependency는 override 가능하고, unresolved
    task-output-only operand는 override 불가한 회귀 테스트 추가/유지

### 핵심 결과

- `MIX_T1_046` targeted replay:
  - `numeric_final_judgement = PASS`
  - `numeric_equivalence = 1.0`
  - `numeric_grounding = 1.0`
  - `numeric_retrieval_support = 1.0`
  - `completeness = 1.0`
- 최종 답변은 `종업원급여 1,701,418,940천원 / 영업비용 8,181,823,307천원 = 20.8%`로 계산됨

### 해석

- 남은 문제는 ratio 계산 하드코딩이 아니라 evaluator runtime projection의
  provenance contract였다.
- composed calculation에서 subtask 결과가 `task_output:*`로 전달되더라도,
  원천 subtask provenance가 보존되어 있으면 grounded operand로 인정하는 것이
  맞다.
- 특정 문항/회사/계정명을 직접 처리하는 rule은 추가하지 않았다.
