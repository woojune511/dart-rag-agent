# Experiment History

> Internal experiment log, not a first-read portfolio document. Start with
> [../../README.md](../../README.md) and
> [../overview/portfolio_experiment_report.md](../overview/portfolio_experiment_report.md)
> for the compressed experiment story. This file preserves detailed historical
> runs and should stay append-oriented.

Full raw benchmark bundles are local-only. Historical links in this document
point only to compact summaries retained for provenance; detailed raw outputs
remain recoverable from the pre-Phase-5 Git history when needed.

이 문서는 benchmark와 retrieval 파이프라인이 버전별로 어떻게 바뀌었는지, 그리고 그때 실험 결과가 어떻게 달라졌는지를 한 번에 보기 위한 기록이다.

## At a Glance

| 항목 | 현재 해석 |
| --- | --- |
| 문서 역할 | append-only experiment log |
| 읽는 순서 | `큰 흐름 -> Timeline Index -> 필요한 버전 상세` |
| 초기 국면 | 저비용 ingest 후보 탐색과 다기업 일반화 검증 |
| 중간 전환 | retrieval 문제와 generation 문제를 분리해서 보기 시작 |
| 최근 전환 | fixed operation planning에서 one-program semantic compilation으로 canonical numeric/mixed path 전환; source-visible 값의 immutable projection과 seed/catalog/prompt 단계별 opaque-ID provenance를 고정했으며, fresh trace로 실제 손실 단계를 확인하기 전에는 admission policy를 바꾸지 않음 |
| published history evidence | 직접 링크된 compact `summary.md`와 작은 diagnostic만 유지; full raw bundle은 local-only |

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
| [Integration Store-Fixed Policy Gate (2026-08-25)](#integration-store-fixed-policy-gate-2026-08-25) | PR #86 source head의 4-company/5-question current-agent refresh와 failed-row 재확인 | 실행은 완주했지만 NAV operand 선택 비결정성, LGE rendering, Samsung trace/evaluator 결함 때문에 release pass가 아님 |
| [NAV Focused Stability And Evaluator Role Split (2026-08-25)](#nav-focused-stability-and-evaluator-role-split-2026-08-25) | segment-bound runtime fix 2회 provider replay와 exact-artifact no-call evaluator replay | runtime trace는 2/2 안정; second-run LLM rendering false negative는 deterministic numeric evaluator로 분리 후 1.000으로 수렴 |
| [LGE Absolute Difference Semantics Closure (2026-08-25)](#lge-absolute-difference-semantics-closure-2026-08-25) | component subtraction과 period delta의 answer-slot 의미 분리 후 store-fixed provider replay | `derived_value`와 neutral absolute-result rendering을 보존했고 numeric/faithfulness/completeness/calculation이 모두 통과 |
| [Samsung Semantic Row And Release-Gate Follow-up (2026-08-26)](#samsung-semantic-row-and-release-gate-follow-up-2026-08-26) | semantic row selection 2회 focused replay, 4-company/5-question gate, LGE derived-value successor | Samsung 3/3 canonical provenance stable; full gate completed but NAV ledger and qualitative residuals keep release on HOLD |
| [NAV Dependency Operand-Artifact Successor (2026-08-26)](#nav-dependency-operand-artifact-successor-2026-08-26) | empty provisional operand artifact를 성공한 task input slot으로 integrity 전에 확정하는 focused replay | `41.4%` 유지, integrity `error -> ok`, recovery replan 제거; qualitative diagnosis와 successor full gate는 남음 |
| [Late Numeric Surface And Clean Integration Gate (2026-08-26)](#late-numeric-surface-and-clean-integration-gate-2026-08-26) | exact-artifact qualitative diagnosis, LGE focused B/C, successor 4-company/5-question gate | generic context/surface contracts restored LGE completeness; final gate is 4/4 company, 5/5 question, full-eval fail 0 |
| [Post-Gate Historical-Answer Compatibility Replay (2026-08-26)](#post-gate-historical-answer-compatibility-replay-2026-08-26) | final defensive hardening 뒤 stored Samsung answer를 현재 evaluator/replay로 no-call 재평가 | deterministic metrics 1.000, but missing numeric grounding keeps `UNCERTAIN`; provider/current-agent pass가 아님 |
| [Exact-Current-Head Three-Row Canary (2026-08-27)](#exact-current-head-three-row-canary-2026-08-27) | `b422a9b`의 SAM/NAV/LGE store-fixed provider replay | SAM/NAV correctness는 유지됐지만 LGE incomplete structured output 뒤 wrong-entity fallback으로 numeric FAIL; integration HOLD |
| [Semantic Source-Scope Repair Three-Row Successor (2026-08-27)](#semantic-source-scope-repair-three-row-successor-2026-08-27) | bounded incomplete-output repair, semantic exact-value source selection, deterministic evaluator replay 뒤 SAM/NAV/LGE focused refresh | 세 answer/provenance 모두 clean; LGE blocker closed, Samsung unit comparison N/A, NAV one-replan/schema residual documented |
| [Current-Head Five-Question Store-Fixed Gate (2026-08-27)](#current-head-five-question-store-fixed-gate-2026-08-27) | semantic source-scope repair 뒤 4-company/5-question current-agent broader replay | runtime/provenance clean, but `HYU_T2_010` attribution-only completeness `0.700` makes formal full-eval fail count 1 |
| [Semantic Calculation Program No-Call Gate (2026-08-27)](#semantic-calculation-program-no-call-gate-2026-08-27) | generic obligations, immutable candidates, fixed compiler outputs, validator/executor, canonical graph and legacy deletion | focused 27/27, audit 86, full unittest 574/574; provider replay and benchmark were not run |
| [Semantic Program Three-Row Diagnostic And No-Call Successor (2026-08-27)](#semantic-program-three-row-diagnostic-and-no-call-successor-2026-08-27) | 새 canonical path의 SAM/NAV/LGE store-fixed 반복 관찰과 일반 후보/표시 후속 | 마지막 paid artifact는 acceptance 실패; source-complete catalog, prose numeric ID, obligation-stratified prompt, aggregate-label 및 percent-display fixtures 뒤 focused 47/47, audit 86, full 589/589 |
| [Approved Semantic-Program Core Replay And Mixed-Chunk Successor (2026-08-27)](#approved-semantic-program-core-replay-and-mixed-chunk-successor-2026-08-27) | repaired SAM/NAV/LGE의 승인된 store-fixed 재검증과 LGE 혼합 문단 경계 진단 | Samsung/NAV runtime complete; LGE 1/3 partial. 실제 저장 cache no-call 후속은 AMPC `sentence_value`를 prompt에 복구했고 focused 48/48, audit 86, full 590/590 |
| [LGE Mixed-Chunk Provider Acceptance Successor (2026-08-27)](#lge-mixed-chunk-provider-acceptance-successor-2026-08-27) | 별도 승인된 LGE-only store-fixed provider replay | precise connected-note AMPC row와 영업이익으로 3/3 obligation 실행; canonical trace accepted, completeness 0.700은 표시 residual |
| [Atomic Multiple Calculation Answer Contract (2026-08-27)](#atomic-multiple-calculation-answer-contract-2026-08-27) | LGE의 precise/rounded 두 source-backed 표현을 evaluator-only atomic variant로 등록하고 저장 artifact를 no-call replay | precise trace가 `connected_note_precise`로만 결합되어 numeric/operand/result/calculation 1.000; 새 provider 호출 없음 |
| [Generic Semantic Rendering Characterization And KB Store Audit (2026-08-27)](#generic-semantic-rendering-characterization-and-kb-store-audit-2026-08-27) | NAVER/LGE `0.700` exact-artifact no-call 분리와 로컬 KB 입력 감사 | LGE common-scope sentence renderer repaired; NAVER는 selected evidence coverage 경계로 유지; 2023 KB store/cache 부재 확인, provider/ingest 실행 없음 |
| [Authorized KB Canonical Store-Only Build (2026-08-27)](#authorized-kb-canonical-store-only-build-2026-08-27) | 별도 승인된 KB 2023 primary-report canonical ingest와 store-only 경계 검증 | 2,093/2,093 embeddings, single receipt scope, evaluator 0; pre-ingest router embedding 1회 관찰 후 minimal ingest facade로 차단 |
| [Approved KB Focused Replay And Generic Program Repairs (2026-08-27)](#approved-kb-focused-replay-and-generic-program-repairs-2026-08-27) | 새 KB store의 두 문항 focused replay와 mixed/unit/prompt-bound 특성화 | 둘 다 numeric PASS지만 T2는 program bypass, T1은 correct formula 뒤 `%p` validator partial; generic no-call repair 후 saved NIM program은 `0.10%p`, 3/3 `ok` |
| [Corrected KB Semantic Replay And Canonical Rejection (2026-08-27)](#corrected-kb-semantic-replay-and-canonical-rejection-2026-08-27) | 승인된 corrected KB pair와 row/value/unit/source audit | T1 canonical 3/3; T2 evaluator PASS·4/4지만 rounded MDA source라 reject. Objective-cache collapse와 `십억원 -> 억원` parser defect를 generic no-call successor로 수정 |
| [Fresh KB Store And Focused Canonical Successor (2026-08-27)](#fresh-kb-store-and-focused-canonical-successor-2026-08-27) | current parser/cache head의 isolated store rebuild와 승인된 KB 두 문항 focused replay | store와 cache/parser 경계는 통과; T2 query enrichment 0/2, T1 invalid retry binding 1/2로 canonical gate reject. 5문항 gate는 실행하지 않음 |
| [KB Residual Contracts No-Call Successor (2026-08-27)](#kb-residual-contracts-no-call-successor-2026-08-27) | query-local enrichment, derived-input binding, eval-only source-store immutability | focused 101/101, audit 86, full 618/618; provider/benchmark 호출 없이 generic repair만 검증 |
| [Approved Residual Replay And Obligation-Owned Retrieval Successor (2026-08-28)](#approved-residual-replay-and-obligation-owned-retrieval-successor-2026-08-28) | 승인된 KB 두 row replay와 T2 retrieval residual의 generic no-call repair | T1 canonical program accepted, T2 0/2 rejected; saved-store probe recovers requested row, focused 109/109, audit 86, full 626/626; 5문항 gate 미실행 |
| [T2-Only Prompt-Readiness Replay And Generic Evidence Successor (2026-08-29)](#t2-only-prompt-readiness-replay-and-generic-evidence-successor-2026-08-29) | 승인된 `KBF_T2_018` 단독 replay와 table-header/prompt-kind/narrative-seed 후속 | paid run 0/2 reject; no-call store probe exposes canonical cells and cause candidate, fixed program 2/2 `70.28%`, focused 115/115, audit 86, full 632/632 |
| [T2 Numeric Acceptance And Narrative-Relation Successor (2026-08-29)](#t2-numeric-acceptance-and-narrative-relation-successor-2026-08-29) | 수정 head의 승인된 T2-only replay와 causal narrative binding 후속 | numeric source/program 2/2 canonical at `70.28%`; unsupported causal narrative keeps mixed acceptance on HOLD; no-call successor focused 118/118, audit 86, full 635/635 |
| [T2 Narrative Replay And Evaluator Role Separation (2026-08-29)](#t2-narrative-replay-and-evaluator-role-separation-2026-08-29) | narrative-relation successor의 승인된 T2-only replay와 faithfulness budget/override 감사 | runtime answer는 2/2, `70.28%`, completeness 1.000; pre-fix raw faithfulness 0.500을 numeric PASS가 덮어 acceptance는 HOLD; generic no-call evaluator successor 118/118, full 637/637 |
| [Corrected-Evaluator T2 Focused Acceptance (2026-08-29)](#corrected-evaluator-t2-focused-acceptance-2026-08-29) | 수정 evaluator를 포함한 별도 승인 `KBF_T2_018` 단독 store-fixed replay | same-row `70.28%`, 2/2, raw/final faithfulness 1.000 without override, completeness 1.000, numeric PASS, ledger `ok`; focused acceptance closed, 5문항 gate 미실행 |
| [Semantic-Program Current-Head Five-Question Gate (2026-08-29)](#semantic-program-current-head-five-question-gate-2026-08-29) | 별도 승인된 `NAV/HYU/LGE/SAM` 5문항 store-fixed integration replay | 4/4 company와 5/5 row는 오류 없이 완주했지만 모든 row가 partial/incomplete, formal full-eval fail 4; integration HOLD와 네 generic no-call blocker 확정 |
| [Generic-Contract Successor Five-Question Gate (2026-08-30)](#generic-contract-successor-five-question-gate-2026-08-30) | 네 no-call contract 수정 뒤 별도 승인된 같은 5문항 store-fixed successor | narrative scope와 retry binding은 개선됐지만 5/5 partial, full-eval fail 4; semantic compatibility, obligation-owned atomic/row admission, direct subject/unit 계약이 다음 blocker |
| [Three-Contract Provider-Free Characterization (2026-08-30)](#three-contract-provider-free-characterization-2026-08-30) | successor의 compatibility/admission/direct-binding 잔여를 회사·문항 독립 fixture로 고정 | 두 expression은 fingerprint-only reject, source-visible 여섯 값은 catalog miss, wrong-row `53%`와 mismatched display unit은 `ok`; focused 61/61, runtime/provider 변경 없음 |
| [Row-Local Direct Subject Validation (2026-08-30)](#row-local-direct-subject-validation-2026-08-30) | table-wide subject leakage를 local row/header 및 evidence-backed bridge 계약으로 교체 | wrong-row direct binding은 `candidate_subject_mismatch`; same-row와 absent-identity compatibility control은 통과, semantic 64/64와 full 647/647 |
| [Candidate-Catalog Source Completeness And Legacy Header Chains (2026-08-30)](#candidate-catalog-source-completeness-and-legacy-header-chains-2026-08-30) | immutable store를 read-only로 감사하고 structured/pipe/flattened provenance 경계를 generic fixture로 고정 | structured row/value와 full pipe row는 stable local candidates; flattened summary는 비권위. legacy 다단 header chain 복원 후 semantic 67/67, full 650/650 |
| [Candidate-Stage Provenance Observability (2026-08-30)](#candidate-stage-provenance-observability-2026-08-30) | retrieved/seed source window와 source/catalog/prompt projection을 값 복제 없이 추적 | generic three-stage loss fixture, semantic 68/68, retrieval 34/34, full 651/651; provider replay와 policy change는 보류 |
| [Candidate-Stage Focused Replay No-Call Admission (2026-08-30)](#candidate-stage-focused-replay-no-call-admission-2026-08-30) | 새 trace를 관찰할 최소 3-row store-fixed 범위, provider path, 비용과 immutable source를 production order로 고정 | 두 rehearsal이 receipt `0c229555...d9da4`로 byte-identical; provider/network 0, `$0.40` one-run ceiling, fresh approval 대기 |
| [Candidate-Stage Focused Replay And Owner Classification (2026-08-30)](#candidate-stage-focused-replay-and-owner-classification-2026-08-30) | 승인된 3-row store-fixed replay로 source/catalog/prompt/compiler 손실 owner를 실제 trace에서 구분 | 3/3 error 0·ledger `ok`지만 모두 partial; SAM source-window, HYU T2 prompt admission, HYU T3 planner/compiler scope-selection; `$0.3156427`, no retry |
| [Required-Input Prompt Admission No-Call Successor (2026-08-30)](#required-input-prompt-admission-no-call-successor-2026-08-30) | required input budget ownership과 decimal sentence context를 generic fixture 및 immutable source slice로 검증 | bounded local cohort와 decimal-aware context 뒤 두 quantity ID가 reconstructed 128-row prompt에 노출; semantic 71/71, full 654/654, provider 0 |
| [Explicit-Query Hard-Scope Provenance No-Call Successor (2026-08-31)](#explicit-query-hard-scope-provenance-no-call-successor-2026-08-31) | pre-evidence consolidated/separate scope를 query-owned constraint로 제한 | implicit/single/dual-scope generic controls와 stored planner projection 통과; semantic 73/73, full 656/656, provider 0 |
| [Obligation-Owned Atomic Seed Preservation No-Call Successor (2026-08-31)](#obligation-owned-atomic-seed-preservation-no-call-successor-2026-08-31) | required numeric seed 예약에서 local row/value와 generic context/statement prior를 분리 | generic failure fixture와 immutable Samsung projection 통과; exact source가 seed에 추가되고 SQLite hash 유지, semantic 73/73, full 657/657, provider 0 |
| [Candidate-Stage Generic Repairs Focused Replay No-Call Admission (2026-08-31)](#candidate-stage-generic-repairs-focused-replay-no-call-admission-2026-08-31) | 세 provider-free owner repair의 최소 3-row successor를 production-order manifest로 고정 | 5,302-byte canonical receipt 두 회가 `fdfbf90f...459af`로 byte-identical; provider/network/output 0, source/target/temp 불변, one-run `$0.40` 승인 대기 |
| [Candidate-Stage Generic Repairs Focused Successor (2026-08-31)](#candidate-stage-generic-repairs-focused-successor-2026-08-31) | 승인된 exact manifest를 Hyundai-then-Samsung store-fixed 3-row로 한 번 실행 | Samsung 2/2 accepted; Hyundai T2 1/2 and T3 0/5 fail-closed. 18 LLM calls, 556,699 tokens, 33 query/0 document embeddings, `$0.2662671`, source stores unchanged, no run retry |
| [Post-Successor Hyundai Residual Contracts No-Call Successor (2026-08-31)](#post-successor-hyundai-residual-contracts-no-call-successor-2026-08-31) | T2 query/input ownership과 unknown-only segment/basis, T3 source-defined summary와 explicit-unit source availability를 일반 계약으로 고정 | semantic/retrieval 113/113, adjacent 285/285, audit 86, import/DAG 20/20, full 662/662; provider/benchmark 0, source hashes unchanged |
| [Post-Successor Hyundai Focused Replay No-Call Admission (2026-08-31)](#post-successor-hyundai-focused-replay-no-call-admission-2026-08-31) | 수정 runtime의 동일 3-row successor를 새 schema-v3 manifest와 production-order rehearsal로 고정 | manifest `4e3e1d8d...e3e4`, 5,189-byte receipt two-run identical at `7f206812...3e91`; provider/network/output 0, explicit `$0.40` approval pending |
| [Post-Successor Hyundai Focused Provider Replay (2026-08-31)](#post-successor-hyundai-focused-provider-replay-2026-08-31) | exact manifest 승인 뒤 immutable store에서 3문항을 한 번 실행하고 canonical trace 감사 | Samsung accepted; HYU T2 2/2 arithmetic recovered but display/override held, HYU T3 1/3 rejected. 289.6s, 17 LLM calls, 467,828 tokens, `$0.2437528`, source unchanged, no run retry |
| [Source-Defined Requirement Ownership No-Call Successor (2026-08-31)](#source-defined-requirement-ownership-no-call-successor-2026-08-31) | 원문 정의 요약의 required-input 발명을 typed group 계약으로 막고 독립/결합 출력 선언을 구분 | semantic 86/86, audit 86, import 19/19 plus canonical graph DAG, full 672/672; fixed planner/compiler and mock catalog only, provider/benchmark 0, prior acceptance unchanged |
| [Source Display And Qualitative Score Separation No-Call Successor (2026-09-01)](#source-display-and-qualitative-score-separation-no-call-successor-2026-09-01) | 원문 표시 보존과 계산값 채택을 분리하고 coverage 기반 정성 점수 상향 두 경로 삭제 | semantic 95/95, evaluator 69/69, adjacent 151/151, audit 86, full 676/676; 저장 T2 프로그램은 `11.4%` 계산과 `11.5%` 원문을 구분, provider/benchmark 0, 기존 acceptance 불변 |
| [Source Group Display Evaluator Focused No-Call Admission (2026-09-01)](#source-group-display-evaluator-focused-no-call-admission-2026-09-01) | 수정된 source-group/display/evaluator의 동일 3-row store-fixed successor를 새 exact manifest로 고정 | manifest `70db0fb1...e91a`, 두 5,490-byte canonical receipt `e0be3cfa...8ed6` 일치, runner/evaluator 99/99, provider/network/output 0; one-run `$0.40` 별도 승인 대기 |
| [Source Group Display Evaluator Focused Provider Replay (2026-09-01)](#source-group-display-evaluator-focused-provider-replay-2026-09-01) | exact manifest 승인 후 동일 세 문항을 한 번 실행하고 기준별 원문·canonical trace를 감사 | 삼성 accepted 2/2, T2 partial 1/2, T3 partial 2/3; 303.767s, 18 LLM calls, 543,641 tokens, `$0.2719901`, source 불변. T3 요약 복구와 정성 점수 독립은 관찰됐으나 전체 acceptance는 1/3 |
| [Scope-Qualified Direct Answers No-Call Characterization (2026-09-01)](#scope-qualified-direct-answers-no-call-characterization-2026-09-01) | 선택된 source basis, 답변 표시, scalar/multi-output 평가와 wrong-row ID를 분리해 특성화 | 합성 15/15, focused 235/235, full 691/691, audit 86. 저장 T3 프로그램 6-candidate projection은 같은 partial 답변을 재현; runtime/dataset/raw scores/provider 결과 불변, 수정은 아직 제안만 |
| [Selected-Source Basis Disclosure No-Call Successor (2026-09-01)](#selected-source-basis-disclosure-no-call-successor-2026-09-01) | 검증된 direct source basis를 query hard scope와 분리해 답변에 표시하고 unknown leakage를 차단 | 합성 17/17, focused 237/237, full 693/693, audit 86. 저장 T3는 `연결기준`만 추가되고 ID/error/partial 불변; provider/evaluator/result/store 0-change |
| [Multi-Output Basis-Qualified Answer Variants No-Call Characterization (2026-09-01)](#multi-output-basis-qualified-answer-variants-no-call-characterization-2026-09-01) | 여러 direct output의 value/unit/subject/period/basis/source를 한 variant로 묶는 비활성 합성 스키마 특성화 | 신규 5/5, focused 242/242, full 698/698, audit 86. 정상 연결/별도 묶음만 match; loader/completeness/runtime/dataset/result/provider 불변 |
| [Multi-Output Answer Variants Production Evaluator Integration (2026-09-01)](#multi-output-answer-variants-production-evaluator-integration-2026-09-01) | 비활성 합성 계약을 strict typed loader, candidate-bound distinct-output matcher, atomic completeness reference로 production evaluator에 연결 | 신규 12/12, focused 249/249, full 705/705, audit 86, socket 0. Scalar/result schema와 curated data/result/provider 불변 |
| [HYU T3 Multi-Output Variant Source Review (2026-09-01)](#hyu-t3-multi-output-variant-source-review-2026-09-01) | immutable Hyundai store에서 연결/별도 Motional tuple의 source basis와 matcher projection을 read-only 검토 | 연결 `26% / 700,691백만원`과 네 summary measure만 완전한 same-basis tuple. 별도 direct pair는 summary가 닫히지 않고 canonical key는 basis를 혼합. 등록 없이 generic unit/subject/period projection blocker를 다음 seam으로 고정 |
| [Canonical Operand Projection Repair And T3 No-Call Gate (2026-09-01)](#canonical-operand-projection-repair-and-t3-no-call-gate-2026-09-01) | inline unit, validated row subject, current report period를 한 canonical operand projector로 보존하고 같은 six-ID proposal 재검증 | generic contract 13/13, focused 261/261, full 707/707, audit 86. 여섯 ID 불변, `ready`/`ok`, strict matcher `atomic_answer_variant_match`; dataset/result/store/provider 불변 |
| [Runtime-Contract Integration Three-Row Provider Gate (2026-09-03)](#runtime-contract-integration-three-row-provider-gate-2026-09-03) | boundary redesign 통합 head와 exact manifest `cb188492...683a8`의 승인된 Hyundai/Samsung 3문항 store-fixed replay | runner는 1회 완주, error 0·ledger 3/3 `ok`지만 runtime completeness는 2/3. T3의 올바른 `700,691백만원` 셀이 owner cohort에서 빠져 release HOLD; `$0.1575934`, no run retry |
| [Typed Candidate Ranking Env-Bound Three-Row Provider Gate (2026-09-03)](#typed-candidate-ranking-env-bound-three-row-provider-gate-2026-09-03) | typed owner target matcher와 env-bound admission의 승인된 동일 3문항 store-fixed replay | 기계적 3/3 `ok`, error 0, ledger 3/3이나 T3가 table 83의 `25.92%`와 table 82의 `700,691백만원`을 혼합해 source-consistent gate 2/3 HOLD; `$0.1356168` plus unpriced embeddings, no retry |
| [Evidence-Bundle Fail-Closed Three-Row Provider Gate (2026-09-03)](#evidence-bundle-fail-closed-three-row-provider-gate-2026-09-03) | physical-row bundle 계약과 exact manifest `b068ac4b...5501`의 승인된 동일 3문항 store-fixed replay | T3 mixed-row proposal을 validator가 거절해 잘못된 출력을 막았지만 0/3 incomplete; 전체 runtime completeness 2/3 HOLD, `$0.1645241` plus unpriced embeddings, no runner retry |
| [Atomic Evidence-Bundle Selection Three-Row Provider Gate (2026-09-03)](#atomic-evidence-bundle-selection-three-row-provider-gate-2026-09-03) | compiler 전에 complete physical-row option을 하나 선택하는 exact manifest `06a40243...016`의 승인된 동일 3문항 replay | T3 direct pair가 table 82 row `9:2`를 공유하고 전체 runtime gate 3/3 PASS; `$0.1212257` plus unpriced embeddings, no runner retry |
| [Bounded Local Cross-Encoder Tie-Breaker Characterization (2026-09-04)](#bounded-local-cross-encoder-tie-breaker-characterization-2026-09-04) | strongest exact factor tier의 31개 pair만 local GTE로 점수화 | 모든 동률이 margin gate에서 abstain해 기존 첫 후보와 T3 table 82를 보존; default disabled, provider benchmark 0 |
| [Evidence-Scoped Atomic Tie Mining (2026-09-04)](#evidence-scoped-atomic-tie-mining-2026-09-04) | 구버전 saved obligation과 verified dataset quote의 exact source node로 current-ID hard negative 수집 | human review 4 select/2 exclude; 1 baseline error, provider 0 |
| [Candidate Fact-Role Projection V1 (2026-09-05)](#candidate-fact-role-projection-v1-2026-09-05) | 물리 후보별 구조 role과 exact-source-grounded prose role 경계 | v5 packet 6/34; raw role context와 exact-surface rank rule은 회귀로 기각, runtime scorer disabled |
| [Bounded Prose Semantic-Role Interpreter Harness (2026-09-05)](#bounded-prose-semantic-role-interpreter-harness-2026-09-05) | query/answer-label-free same-source role extraction contract | one request/two values; reviewed role plumbing 2/2, cross-encoder stays 1/4, provider 0 |
| [Runtime Repair Failed-Row Provider Retry (2026-09-05)](#runtime-repair-failed-row-provider-retry-2026-09-05) | 첫 repair gate의 429 실패 두 행만 exact manifest로 재실행하고 T3 성공을 해시로 carry forward | Samsung 완전 통과, T2 query embedding 429 재발; combined same-runtime gate 2/3 HOLD, no retry |
| [OpenAI-Store T2 Replay And Planner Null Boundary (2026-09-05)](#openai-store-t2-replay-and-planner-null-boundary-2026-09-05) | rebuilt OpenAI store에서 T2를 exact admission으로 1회 실행하고 optional planner sentinel 결함을 분리 | query embedding은 정상화되고 숫자는 완전 통과; narrative는 `display_unit="null"`로 compiler 전 차단. generic no-call fix 뒤 full 877/877, provider successor 미실행 |
| [Optional-Null Successor T2 Replay And Dependency Projection Boundary (2026-09-05)](#optional-null-successor-t2-replay-and-dependency-projection-boundary-2026-09-05) | null-normalization successor를 exact OpenAI-store admission으로 1회 실행 | narrative는 복구됐지만 numeric raw input IDs가 `depends_on`에 중복되어 preflight 차단; generic successor `af9a07e`, full 878/878, provider 재실행 없음 |
| [Dependency-Projection Successor T2 Provider Pass (2026-09-05)](#dependency-projection-successor-t2-provider-pass-2026-09-05) | `af9a07e` successor를 exact OpenAI-store admission으로 1회 실행 | T2 두 obligation 완전 통과, 원문 `11.5%`와 재계산 `11.4%` 병기, combined runtime gate 3/3 PASS |

## 보는 법

| 섹션 | 무엇을 보면 되나 |
| --- | --- |
| `코드 / 설정 변화` | 무엇을 바꿨는지 |
| `핵심 결과` | 어떤 후보가 좋아졌거나 실패했는지 |
| `해석` | 왜 다음 버전으로 넘어갔는지 |

상세 원본 결과는 각 버전 디렉터리의 `results.json`, `summary.md`, `cross_company_summary.md`를 참고한다.

## Evidence-Scoped Atomic Tie Mining (2026-09-04)

The existing fingerprint-verified exporter can replay only the three current
Hyundai/Samsung plans. Extending it across diagnostics v1-v6 produced historical
snapshots of the same three questions, not independent examples. Rebuilding an
entire older store also mixed retrieval misses into semantic ranking, so that
population was rejected for labeling.

The evaluation-only `src.ops.mine_semantic_tiebreak_cases` instead combines
saved obligations with exact matches to `verification_status=verified` dataset
evidence quotes. It rebuilds current candidate IDs only from matched structure
nodes and emits an unlabeled JSON plus static HTML source-review packet. Packet
v2 maps prose candidates by graph source ID and table candidates by physical
`table_source_id`; each candidate links to the exact structure-node text and its
SHA-256 plus the matching local filing HTML. Nine of ten numeric/narrative
evidence quotes matched exactly; the unmatched KBF narrative quote does not
affect the numeric cohorts.

Four questions were inspected. KBF T1 and NAVER had no atomic tie in their
evidence nodes. KBF T2 contributed two requirement cases, while LGE contributed
four output/requirement cases: 6 cases and 34 candidate pairs total. The LGE
AMPC requirement places `2조 1,632억원` first and `6,769억원` second. All 34
candidate rows resolve to exactly one source node. Template fingerprint is
`fcf3038ce5c2776e37f4f2faefa418585e3519252c6551a5bbf6e9df6037b929`.

Human review on 2026-09-05 retained four selection cases / 22 candidates. The
KBF 2023 and 2022 expense targets each accept the three parenthesized
income-statement candidates; the same-magnitude positive candidates are
cash-flow adjustments, not formatting variants. Four source-consistent LGE
operating-income candidates are acceptable, and the AMPC input accepts only
`cand_d0c87437a16bace393ec`, so the reviewed baseline is 3/4 and has one real
error. The derived-output cohort is non-atomic and the repeated operating-income
input is excluded from independent evaluation as a planner dependency issue.

A blanket derived-output exclusion was tested and rejected: it would also remove
valid source-stated derived displays such as Hyundai's `11.5%` growth rate. The
runtime eligibility contract therefore stays unchanged; only this LGE
operand-only case is excluded by its review disposition. The immutable reviewed
packet was not rewritten. A 2026-09-05 successor keeps the same 6 cases / 34
pairs and fingerprint while displaying owner role and full scope in the HTML.

The pinned human review generated a 4-case / 22-candidate atomic fixture
(`6b51a0b6...bbd4`). The existing cached sigmoid cross-encoder reached only
`1/4` top-1 versus the deterministic baseline's `3/4`, a `-0.50` gain. It ranked
adjacent but different KBF rows above both expense rows and still preferred the
whole operating-profit value over the AMPC value; only the LGE operating-income
case stayed correct. All four decisions abstained at margin `0.05`, and warm CPU
p95 was `2747.644 ms`, above the `1000 ms` gate. Result
`970880d2...a024` is therefore `needs_review`; runtime remains disabled and no
margin or keyword policy changed. The next model experiment must first separate
deterministic table-row identity from prose-specific value-role interpretation.

This is a provider-free hard-negative discovery artifact, not runtime-frequency
or model-promotion evidence. No LLM/embedding provider, benchmark runner, fresh
ingest, store mutation, dataset rewrite, or paid retry ran.

Focused semantic/export/mining tests passed 22/22, documentation/import/topology
checks passed 23/23, full unittest discovery passed 823/823, and the 86-literal domain
audit, pycompile, and `git diff --check` passed.

## Bounded Local Cross-Encoder Tie-Breaker Characterization (2026-09-04)

### Contract and implementation

- The deterministic applicability vector remains the admission and tier
  authority. A local cross-encoder sees only candidates tied in the strongest
  exact vector; it cannot admit conflicts, promote lower tiers, expand owner
  visibility, or split a physical-row bundle.
- The scorer is lazy and disabled by default. The pinned multilingual GTE model
  runs in one batch with 12-candidate-per-cohort and 64-pair initial-query caps,
  a bounded process cache, and a `0.05` top-score margin. Unavailability,
  overflow, or low margin preserves the previous deterministic order.
- Pair text contains the typed owner target plus a bounded cell-local evidence
  excerpt. The saved three-question projection contained 31 pairs and stayed
  within the model input window: mean 183.3 tokens, maximum 248 of 256.
- Semantic scores and margins are diagnostic-only and are removed from compiler
  prompt serialization. Candidate IDs, catalog fingerprints, visibility,
  validation, and execution contracts are unchanged.

### Saved-artifact characterization

The immutable source windows for `HYU_T2_010`, `HYU_T3_072`, and
`SAM_T2_078` rebuilt with verified catalog fingerprints. T2 exposed 2 pairs
(1 unique inference pair), T3 20 (13 unique), and Samsung 9 (6 unique). Every
top-versus-runner margin was between `0.0` and `0.00845835`, below the `0.05`
gate. The scorer therefore changed no first candidate, and the T3 complete-row
selector retained table 82.

On the local CPU environment, model score wall time was about 6.107 seconds for
the cold T2 load, 1.064 seconds for the warm 20-pair T3 batch, and 0.656 seconds
for the warm 9-pair Samsung batch. Model weights were fetched only to the
user-level Hugging Face cache for this local characterization; subsequent probes
used local-only loading. No LLM provider, benchmark runner, fresh ingest,
document embedding, source store mutation, or historical result rewrite ran.

### Decision and follow-up

The implementation boundary and latency are usable, but this model has not yet
shown a ranking-quality gain on the known hard negatives. The feature remains
opt-in. Promotion requires a labeled hard-negative set with a measurable top-1
gain, no physical-row regression, and warm deployment p95 below one second.
If it misses that gate, evaluate better hard-negative training or a
smaller/GPU/ONNX reranker rather than adding keyword weights. The persisted
typed fact index remains a separate versioned ingest/store migration.

### Labeled hard-negative promotion gate

Pair v2 corrected the candidate-identity projection and reduced the saved-pair
token envelope from a maximum of 248 to 161 tokens. The local-only gate used
five labeled selection cases and one duplicate-evidence abstention case. The
deterministic baseline and model raw top-1 were `0.2` and `0.6`, for a `0.4`
gain, but only one of five selection cases cleared the runtime `0.05` margin.
Required top-1 and confident-selection rates are `0.8` and `0.6`, so status is
`needs_review`. Duplicate evidence abstained correctly and there were zero
confident errors.

The exact-head rerun used fixture fingerprint
`22a8117f799247ea05750bc9ff2ede97690c8e9ee21c775d8927d27c6037c267`
and scorer `cross_encoder_cb688842c0f5e582`. Three repeated 12-pair CPU batches
had warm p95 `462.494 ms`; cached cold model load was `7,212.528 ms`. A
read-only replay of the immutable three-question
source windows rebuilt all catalogs, projected 31 pairs, changed no first
candidate, and kept the T3 table-82 row bundle. Every cohort still abstained
below the margin. No provider, download, benchmark runner, fresh ingest,
document embedding, store mutation, or result rewrite was used.

The latency boundary is viable, but this general retrieval reranker does not
confidently bind a numeric candidate to the correct clause. Keep it disabled;
the next model experiment should target numeric-binding hard negatives rather
than lower the margin or add keyword weights.

### Clause-local pair v3 and real-tie labeling export

The saved prose candidates retain numeric spans from their parent source while
their `source_text` is a sentence excerpt, so those coordinates cannot be used
blindly. Pair v3 accepts a span only when it matches the exact scorer input;
otherwise it permits one boundary-valid unique value surface and abstains from
clause localization when that surface is missing or ambiguous. This split the
same-sentence `11.5%` growth and `5.6%` share examples into separate clauses.

A provider-free exporter rebuilt every saved catalog with matching fingerprints
and produced an in-memory unlabeled template for all 8 strongest-factor ties and
31 candidate pairs, with no skipped plan. Its deterministic fingerprint was
`a60909c542046bb0af05852cb70d433cb126727a6f23c6a764792ed5d23f8dca`;
no labeling or benchmark artifact was written.

The scorer now declares its transform as part of scorer identity and passes an
explicit activation to SentenceTransformers. The conservative policy remains
`sigmoid`. Its six-case result stayed `needs_review`: unthresholded top-1 `0.6`,
confident selection `0.2`, abstention `1.0`, zero confident errors, and warm CPU
p95 `410.617 ms`. The explicit `raw_logit` comparison also had top-1 `0.6`, but
the unchanged `0.05` gate selected every case and made two confident errors.
Diagnostic calibration could recover only `0.2` zero-error selection coverage
for either transform, so it did not rewrite runtime policy.

The verified three-question scored replay still exposed `2 / 20 / 9` pairs,
abstained in all 8 tied cohorts, changed no first candidate, and retained table
82 row `9:2`. Both transform probes used cached local files only. No provider,
download, benchmark runner, fresh ingest, document embedding, store mutation,
or historical result rewrite ran. Focused semantic tests passed 142/142, import
and documentation gates 29/29, the runtime-domain audit retained 86 reviewed
literals, and full unittest discovery passed 814/814.

## Atomic Evidence-Bundle Selection Three-Row Provider Gate (2026-09-03)

### Authority and execution

The user approved exact manifest
`06a402433efa892f016f537dac1eceb4776e62cc67c83e2e4494309c310dd016`,
one execution of its three ordered questions, and a USD `0.40` ceiling. Two
persisted no-call rehearsals and the immediate pre-dispatch rehearsal produced
the same 6,730-byte receipt SHA-256
`0e7ea486665d42d0be3686a067281461069bb887981dcd9e0d92a9409f95889f`.

Runtime head `28d26dc` ran exactly one store-fixed `eval-only` process in the
order `HYU_T2_010`, `HYU_T3_072`, `SAM_T2_078`, Hyundai before Samsung, with a
30-second heartbeat. It exited zero after 276.8 seconds. The ignored result is
`benchmarks/results/atomic_evidence_bundle_focused_successor_envbound_2026-09-03/results.json`;
its SHA-256 is
`b103657a301aea72ae1d529a163f6db4a686361c061fe4c0029092817f44753e`.

### Runtime gate result

| Question | Runtime obligations | Error / ledger | Observed output |
| --- | --- | --- | --- |
| `HYU_T2_010` | `ok`, 2/2 | `0 / ok` | The same four predecessor evidence IDs; `87.0만 대`, `78.1만 대`, calculated `11.4%`, and source display `11.5%` |
| `HYU_T3_072` | `ok`, 3/3 | `0 / ok` | `26%` and `700,691백만원` both selected from table 82 row `9:2`, plus the source-grounded Motional summary |
| `SAM_T2_078` | `ok`, 2/2 | `0 / ok` | All three predecessor evidence IDs remain; one compatible Harman overview source was added; `28,352,769백만원` and the narrative remain |

The bounded runtime release gate is **3/3 PASS**. The compiler made five island
calls across the three questions with no retry.

### Atomic T3 selection

The T3 ranker considered the two complete direct-output options from the saved
source window: table 82 row `9:2` (`26%`, `700,691백만원`) and table 83 row
`9:2` (`25.92%`, `907,061백만원`). It selected table 82 before compiler
invocation and reduced the compiler-visible dictionary to 10 IDs. The compiler
then selected `cand_e2f2596cb81e73b80bbc` and
`cand_a8aa299ad5dea4f29cd5`, both from that physical row. No table 83 numeric ID
entered validation or execution. Supplemental Motional summary measures remain
grounded in their own source summary rows rather than being relabeled as table
82 cells.

This closes the predecessor's independent per-owner choice defect: the compiler
can only choose the already selected direct-output option, while validator and
executor retain the same fail-closed bundle contract.

### Cost, immutability, and claim boundary

The run recorded 17 LLM calls, 117,631 LLM tokens, 32 query-embedding calls,
zero document-embedding calls, and estimated runtime cost USD `0.1212257`.
Embedding pricing remains unavailable. Both source `results.json` hashes, both
SQLite hashes, and both full store fingerprints exactly match the admission;
no disposable store remains. No automatic runner retry occurred or is
authorized.

This runtime acceptance does not alter the T3 mixed-basis answer key or relax
the evaluator. The raw benchmark still reports T2/T3 completeness `0.7/0.3`,
Samsung faithfulness `0.7`, and two company-level full-eval failures. Those
qualitative/dataset-governance outcomes are preserved rather than promoted into
a broader benchmark-pass claim.

## Evidence-Bundle Fail-Closed Three-Row Provider Gate (2026-09-03)

### Authority and execution

The user approved manifest
`b068ac4b108d8243a417b61e355439ef1f25106c3b707db12ce0561015a45501`,
one execution of its three ordered questions, and a USD `0.40` ceiling. The
immediate production-order rehearsal reproduced the canonical 6,710-byte
receipt SHA-256
`98484f569246a4cc4af07b4e0070426a73aee9def2a4317b4011082593ecb191`
with the target absent and provider/network/output counts zero.

Runtime head `cc14901` then ran exactly one store-fixed `eval-only` process in
the order `HYU_T2_010`, `HYU_T3_072`, `SAM_T2_078`, Hyundai before Samsung,
with a 30-second heartbeat. It exited zero after 313.9 seconds. The ignored
result bundle is
`benchmarks/results/evidence_bundle_focused_successor_envbound_2026-09-03`;
its root `results.json` SHA-256 is
`e679e712d3e228a9e19d6ef4c52b64e649853d9f5a44a83ed700deac48fea6b2`.

### Runtime gate result

| Question | Runtime obligations | Error / ledger | Observed output |
| --- | --- | --- | --- |
| `HYU_T2_010` | `ok`, 2/2 | `0 / ok` | Same predecessor evidence IDs; `87.0만 대` and `78.1만 대` produce `11.4%`, source display `11.5%`, plus policy narrative |
| `HYU_T3_072` | `incomplete`, 0/3 | `0 / ok` | Mixed-row retry proposal rejected as `evidence_bundle_mismatch`; no unsupported value emitted |
| `SAM_T2_078` | `ok`, 2/2 | `0 / ok` | Same predecessor evidence IDs; `28,352,769백만원` and Harman narrative preserved |

The release gate is **2/3 runtime-complete, HOLD**. This differs from the
predecessor failure in a useful way: the old runtime emitted a mechanically
complete but source-inconsistent T3 answer, whereas this runtime refuses the
same kind of mixed-row selection.

### T3 bundle diagnosis

The candidate stage inferred one physical-row bundle spanning `ob_001`,
`ob_002`, and `ob_003`, which correctly merged them into one island. It exposed
two complete options:

- table 82 row `9:2`: `26%`, `700,691백만원`, and compatible narrative IDs;
- table 83 row `9:2`: `25.92%`, `907,061백만원`, and compatible narrative IDs.

The first compiler attempt was `partial`: it proposed one narrative candidate
while both direct obligations remained missing/ambiguous. The one allowed
internal retry retained the same 16 visible IDs and 76,266-byte candidate
payload, then proposed `cand_1662e0875b6da25cc909` from table 83 for ownership
and `cand_a8aa299ad5dea4f29cd5` from table 82 for carrying amount. Validation
reported `evidence_bundle_mismatch`, selected no bundle option, and preserved all
three obligations as missing. No executor output was produced.

The remaining seam is therefore atomic selection, not table parsing, candidate
visibility, wrong-subject filtering, island construction, or validator drift.
The prompt still lets the model choose IDs independently per owner and only
checks the option afterward. The next provider-free change should rank physical
row options from the existing typed owner ranks and project owner visibility
through one selected option, making a mixed-row proposal unrepresentable.

### Cost and immutability

The run recorded 18 LLM calls, 166,963 LLM tokens, 32 query-embedding calls,
zero document-embedding calls, and estimated runtime cost USD `0.1645241`, below
the approved USD `0.40` ceiling. Embedding cost was not priced. Both source
result hashes, both SQLite hashes, and both complete store fingerprints are
unchanged; no disposable store remains. No automatic runner retry occurred or
is authorized.

## Typed Candidate Ranking Env-Bound Three-Row Provider Gate (2026-09-03)

### Authority and execution

The first approved candidate-ranking admission `b6762027...61e3` consumed its
single process attempt but stopped before provider-client construction because
the clean worktree did not contain the `.env` read by runtime configuration. It
was not retried. A versioned successor bound the ignored worktree-root `.env`,
the exact working directory, runtime commit `12fe139`, source hashes, and the
ordered questions `HYU_T2_010`, `HYU_T3_072`, `SAM_T2_078` without recording
credential values or an `.env` hash.

The successor manifest is
`9c1d1807f74397d528278592c6867e491decf23abbb03977fb33c837cf86a3c3`.
Two persisted no-call runs and the immediate pre-dispatch run reproduced the
same 6,552-byte receipt
`31adb7b259247b9006be373e2aa2ff9def635dec50f6416ecbb9e921ff98c5f9`.
The separately approved provider process then completed once in 295.5 seconds
with exit code zero. Its ignored root `results.json` is SHA-256
`a80fdbdff7b7b8d05091b74f2cffcdfaf76822549d992ca5311ee6118d89617d`.

### Result and interpretation

| Question | Mechanical contract | Source-consistency review |
| --- | --- | --- |
| `HYU_T2_010` | 2/2 obligations, calculation `ok`, error 0, ledger `ok` | selected `87.0만 대` and `78.1만 대`; final answer retained `11.4%` and source display `11.5%`, but omitted the raw operand displays |
| `HYU_T3_072` | 3/3 obligations, calculation `ok`, error 0, ledger `ok` | HOLD: compiler selected `25.92%` from table 83, `700,691백만원` from table 82, and only detailed-table `당기순손익 -803,742` |
| `SAM_T2_078` | 2/2 obligations, calculation `ok`, error 0, ledger `ok` | preserved `28,352,769백만원` and the Harman automotive narrative |

The T3 matcher boundary itself improved: `cand_e2f2596cb81e73b80bbc = 26%`
and `cand_a8aa299ad5dea4f29cd5 = 700,691백만원` are first in their respective
owner cohorts, while BHAF `53%` is not selectable. The compiler chose the second
ownership candidate because it described `25.92%` as more precise. The planner
gave all three related obligations empty coupling keys, so they compiled in
three independent islands and validation had no cross-table basis assertion.
This is now a generic multi-output physical-row/table coherence blocker, not a
catalog visibility, table parsing, ledger, or executor error.

The runner recorded 20 LLM calls, 136,312 LLM tokens, 30 embedding calls, zero
document embeddings, and estimated runtime cost USD `0.1356168`; embedding cost
was not priced. One initial canonical-routing embedding request returned HTTP
429 and degraded safely. Source result hashes, SQLite hashes, and complete store
fingerprints remained unchanged, and both disposable stores were removed. No
automatic run retry occurred or is authorized. Mechanical completeness is 3/3,
but source-consistent completeness remains 2/3 and release remains `HOLD`.

## Runtime-Contract Integration Three-Row Provider Gate (2026-09-03)

### Authority and execution

The user approved the exact admission manifest
`cb188492de5b51ee3b42cf5cf9aaf6c12192d92567c001a0426c4e6e785683a8`,
one execution of its three ordered questions, and a USD `0.40` ceiling. A fresh
production-order rehearsal immediately before dispatch reproduced the canonical
5,640-byte receipt SHA-256
`d63ae5e34e939b68f03f4bc69b897af2f2b755c47039e4a4873352d1117105b3`,
with the target absent and provider/network/output counts at zero.

Source head `d3f3319` then ran one store-fixed `eval-only` process in the exact
order `HYU_T2_010`, `HYU_T3_072`, `SAM_T2_078`, with Hyundai before Samsung and
a 30-second heartbeat. The runner exited zero after 314.7 seconds. There was no
automatic run retry, fresh fetch, parse, ingest, source-store write, or document
embedding. The ignored artifact is
`benchmarks/results/runtime_contract_integration_focused_successor_2026-09-02`;
its root `results.json` SHA-256 is
`59e43b35a2b013b13f53ff33ecbc8a43a04d7590f7ca8d5752ca1a62f286e5f3`.

### Runtime gate result

| Question | Runtime obligations | Error / ledger | Observed output |
| --- | --- | --- | --- |
| `HYU_T2_010` | `ok`, 2/2 | `0 / ok` | `87.0만 대` and `78.1만 대` produce calculated `11.4%`, source display `11.5%`, plus the policy-response narrative |
| `HYU_T3_072` | `partial`, 2/3 | `0 / ok` | Motional `26%` and the four-measure summary are present; `ob_002` Motional investment carrying amount is missing |
| `SAM_T2_078` | `ok`, 2/2 | `0 / ok` | `28,352,769백만원` and the Harman direction/technology narrative are present |

The formal runtime release gate is therefore **2/3, HOLD**, despite zero runtime
errors and ledger integrity `ok` for all three rows. Evaluator
faithfulness/completeness were respectively `1.000/0.700`, `0.700/0.500`, and
`0.700/1.000`. Those qualitative scores are recorded for diagnosis; the T2
display omission noted by the completeness judge does not change its 2/2
runtime-obligation status, and answer-key/tolerance governance remains separate.

### T3 owner diagnosis

The source table and physical-cell projection are intact. The Motional row
deterministically projects:

- `cand_e2f2596cb81e73b80bbc`: ownership percentage `26%`;
- `cand_a8aa299ad5dea4f29cd5`: investment asset `700,691백만원`.

The second ID is present in the query's 14-ID global prompt catalog, but it is
not selectable by `ob_002`. That owner's four numeric slots instead contain
`cand_51227debb6062483d19a`, `cand_ab890f3ad3497420a258`,
`cand_d7039c2d704c685f7e04`, and the percentage candidate
`cand_e2f2596cb81e73b80bbc`. Both compiler attempts used the same six visible
IDs, fingerprint
`0f8eb6680036c28dd0871f6be996f307b4ab5a651bf26548752e099cf32e7b1c`,
and 16,070 serialized bytes, proposed no binding, and returned `ob_002` missing.

All three T3 islands had empty dependency edges, empty coupling keys, and no
preflight error. Validation and execution did not reject the correct cell; the
compiler never had owner authority to select it. The BHAF `53%` physical cell
`cand_71982f64d6b3b1dc9d35` was also absent from the Motional owner space, so the
wrong-row exclusion held. The observed failure owner is the obligation-specific
cohort ranking/admission seam, not table parsing, coupling, validator drift, or
execution.

### Cost and immutability

The runner recorded 21 LLM calls and 146,156 tokens with an estimated runtime
LLM cost of USD `0.1575934`, below the approved ceiling. Embedding pricing was
not present in the profile; observed usage was 33 query-embedding calls and zero
document-embedding calls.

The runtime, profile, and dataset hashes remained exactly those in the
admission. Hyundai/Samsung source-store fingerprints remained
`ebdbe7021f3eb34ad75007ee1736033f3428d50745921558fbae85498ba2ae81`
and `862a01380754fd64e2395ecf506f9e4daa6ed404385b623b862623c425ddba3e`;
their SQLite and predecessor `results.json` hashes also remained unchanged.
Both disposable stores were removed. Per the admission stop condition, the raw
artifact was preserved and no paid retry was made.

The next authorized development seam is provider-free: characterize why the
same-row investment cell loses `ob_002`'s four-slot ranking, then repair the
generic policy/ontology/cohort mechanism while retaining owner visibility,
fail-closed validation, and wrong-row exclusion. A new provider run would need a
new manifest, no-call receipts, cost estimate, and separate approval.

## Canonical Operand Projection Repair And T3 No-Call Gate (2026-09-01)

### Authority and scope

The approved seam was the provider-free generic repair identified by the T3
source review. It did not authorize a curated-row or canonical-key edit,
tolerance/score change, provider or evaluator-judge call, benchmark replay,
retrieval/ingest, compiler tuning, paid retry, or Phase 3 work. The synthetic
fixture contains no company name or benchmark ID.

### Contract repair

The candidate catalog now resolves the effective source display unit with cell-
embedded units ahead of inherited table hints while retaining
`source_unit_hint` and `raw_unit_source`. It preserves metric headers as
`source_period_surface`; an unambiguous `period_focus=current` table projects
the report year as canonical `period`/`value_year`. Candidate IDs continue to
hash the immutable source surfaces, so the projection change does not churn
them.

Direct subject validation now resolves parser-footnote-cleaned row identity and
carries `resolved_subject`, `subject_source`, and source-row IDs into one public
canonical operand projector used by both compile and execution artifacts. The
direct output repeats that subject. The multi-output evaluator requires the
explicit subject and its operand provenance and rejects metric-label fallback.
Legacy scalar calculation variants remain source-qualified by allowing their
strict label to match either the canonical metric label or the explicit
validated subject, never an unvalidated table-wide surface.

### Verification and immutable-source result

- synthetic multi-output contract: 13/13;
- semantic/scope/evaluator/provenance/slot/rendering/ledger/import focused set:
  261/261;
- full unittest discovery: 707/707;
- runtime-domain audit: 86 reviewed literals; the only baseline change is a
  documented parser-only numbered-footnote shape;
- import side effects: 19/19; canonical semantic graph DAG: 1/1;
- `git diff --check`: pass.

SQLite was reopened with `mode=ro&immutable=1` and combined only with its
existing `table_payloads.json`. The reconstructed IDs remained exactly
`cand_f8b33c34fa5f2be89451`, `cand_7c8fe3f9ccf88fd702f8`,
`cand_a92475445e07f5bac0c0`, `cand_9f778fb44ea42b603c96`,
`cand_37a49e64b6e4af4b86f5`, and `cand_00f1ca43f70ccc76ff7b`.
The direct operands now retain `%`/`백만원`, subject `Motional AD LLC`, and
period/value year `2023`. The three-obligation program returned validation
`ready`, execution `ok`, all outputs, and no errors. A strict in-memory
`hyu_t3_072_consolidated_current` proposal returned score `1.0`, variant ID
match, reason `atomic_answer_variant_match`, and no projection errors.

SQLite SHA-256 remained
`73b65b54dfdd6d63390a219f67b4d8a8e61b7169be481a3fc1f6c586db31db37`;
`table_payloads.json` remained
`b33cec7ee0a309fbdc1b9dfd7d2caf2519412244c81bc76c6567a39f3a9cf852`.
The three curated dataset hashes, latest saved-result hash, and excluded router
files also remained unchanged. No result bundle was created. The next seam is a
separate dataset-governance decision about registering only the complete
consolidated variant and correcting the currently mixed-basis canonical key.

## HYU T3 Multi-Output Variant Source Review (2026-09-01)

### Authority and source boundary

The documented next step authorized a provider-free, read-only source review,
not a curated-dataset edit, canonical-key correction, tolerance or score change,
compiler repair, paid replay, ingest, or Phase 3 restart. The original HTML path
recorded in the row is absent from this checkout, so the review used the
canonical parsed Hyundai 2023 store in
`policy_gate_regression_2026-06-03_1138_actual`. SQLite was opened with
`mode=ro&immutable=1`; its pre-review SHA-256 was
`73b65b54dfdd6d63390a219f67b4d8a8e61b7169be481a3fc1f6c586db31db37`.
Candidate IDs were reconstructed deterministically from immutable store metadata
and `table_payloads.json`. No provider, embedding, retrieval, evaluator judge, or
benchmark action occurred.

### Source result

| Basis | Direct outputs | Summary source | Review result |
| --- | --- | --- | --- |
| consolidated | chunk `20240313001451:175:85`, table 82: `26%`, `700,691백만원` | chunk `20240313001451:183:93`, table 90: `1,775`, `(803,742)`, `12,115`, `(791,627)`백만원 | Complete current-period tuple for all three obligations |
| separate | chunk `20240313001451:455:70`, table 69: `25.81%`, `1,294,367백만원` | No complete separate-scope summary in the reviewed store | Direct pair is valid, but a complete answer variant is not established |

The consolidated direct candidate IDs are
`cand_f8b33c34fa5f2be89451` and `cand_7c8fe3f9ccf88fd702f8`.
The summary IDs are `cand_a92475445e07f5bac0c0`,
`cand_9f778fb44ea42b603c96`, `cand_37a49e64b6e4af4b86f5`, and
`cand_00f1ca43f70ccc76ff7b`. Replaying exactly those six candidates through the
pure executor produced `ok`, all obligations, no validation errors, and a
grounded consolidated answer. This is a no-call projection, not benchmark
acceptance.

The separate direct IDs are `cand_f6cf81772743b7a86d29` and
`cand_1a89d1686b72354c7533`. The detailed investment table corroborates these
values and includes `-803,742`, but it does not contain `791,627`; that total
comprehensive loss appears only in the consolidated summary source. The current
canonical key therefore combines separate direct outputs with a consolidated
summary. The review records this dataset discrepancy without changing it.

### Projection blocker and decision

The truthful consolidated proposal is not yet registerable against the current
canonical operand projection. The percentage cell keeps table-wide raw unit
`백만원` despite its embedded `%`; the validated Motional row identity is reduced
to row label `미국`; and report year/current-period context is replaced by metric
column labels. A pure matcher probe matched all proposed answer numbers but
failed trace projection, beginning with
`output_operand_raw_value_mismatch`. Weakening the variant contract to repeat the
lossy metadata would invalidate its source-qualified purpose.

The review therefore proposes only one eventual variant,
`hyu_t3_072_consolidated_current`, and registers none. The next seam is a generic
provider-free characterization and repair for cell-over-table unit precedence,
row-header subject preservation, and report-year/current-period preservation,
followed by the same six-ID pure matcher replay. Dataset/key correction and paid
acceptance remain separate decisions. The full evidence ledger is in
[hyu_t3_072_answer_variant_source_review.md](../evaluation/hyu_t3_072_answer_variant_source_review.md).

## Multi-Output Answer Variants Production Evaluator Integration (2026-09-01)

### Authority and scope

The user authorized the documented provider-free production evaluator seam.
This step changed only evaluator contract/loading/matching/completeness-reference
selection plus the existing synthetic fixture/tests and authority docs. It did
not authorize curated dataset registration, canonical-key or tolerance edits,
saved score/result changes, compiler repair, benchmark replay, provider calls,
ingest, or Phase 3.

### Implementation

`EvalAnswerVariant` and `EvalAnswerVariantOutput` now type the optional
`accepted_answer_variants` field. The loader rejects missing or unknown fields,
duplicate variant/output IDs, incomplete per-variant output coverage,
unsupported non-direct kinds, invalid values, and known raw/normalized unit
conflicts. This field is not added to scalar `accepted_answer_keys` and is never
consumed by the runtime agent.

The pure matcher projects only canonical `calculation_result.outputs` whose kind
is `direct_value`. Their semantic output IDs must exactly equal the contract's
required set. Each output must be `ok` and bind by immutable candidate/evidence
ID to exactly one pre-supplementation calculation operand. The joined record must
preserve label, subject, raw and normalized value/unit, period, consolidation
scope, and source. Distinct assignment is required, and exactly one complete
trace variant may survive. Missing/extra outputs, cross-basis mixes, wrong
subject/source/scope, unbound or ambiguous bindings, invalid contracts, and more
than one complete trace variant fail closed.

The answer's complete numeric claims must match that same unique trace variant.
Only then does completeness receive the variant's source-qualified `answer_key`.
Every no-field/no-match/error case retains `canonical_answer_key`. The matcher
does not write a result/debug field or promote faithfulness, completeness,
grounding, or numeric scores. Existing scalar calculation variants retain the
all-operands-bound-to-one-result guard.

### Verification and invariants

- Synthetic production contract: 12/12, including strict loader, all fixed
  complete/fail-closed tuples, answer/trace mismatch, invalid hand-built model,
  ambiguous complete traces, unbound/extra outputs, explicit/canonical prompt
  selection, and fixed raw qualitative scores.
- Nine-module semantic/evaluator/provenance/slot/ledger/import set: 249/249.
- `python -m unittest discover -s tests`: 705/705.
- `python -m src.ops.audit_runtime_domain_terms`: PASS, 86 reviewed literals.
- Network-blocked module repeat: 12/12, zero socket connection attempts.

Production evaluator SHA-256 is
`eca349961c682876a3b57dcb5b34b2286db18242511ddd09aa0e742408e197af` and the
127-file source build is
`da825d0a1fe800ea4c4262a851625105a71c30aee7acd2293eeb1d1213657b26`.
The full/multi-metric/multi-subtask curated dataset hashes remain
`19bb121507275a7c15406dddbda22b392bb870d6bf0fdb9a400d599de8eb1aba`,
`a21647a0fdc62eec187f7790bd263d0052359d0b8091135b82882e88482037a7`, and
`db6d4bd10b747c56bad4b4027971c6affca0a8d982dcf019594b04bfcf59d82a`.
The latest result remains
`6725d3248c4002c6f2f835786a59dc4180e7f09dd1a9e972aa594df606e93e5a`;
excluded router/test hashes remain `ebdc6ad4...f6a8` and `f045e4f1...a029`.
No provider, embedding, benchmark, retrieval, parser/ingest, judge, or result
artifact action occurred. The index remains empty and paid acceptance stays 1/3.

The next bounded seam is read-only source review for any real multi-output
variants. Dataset registration requires a separate explicit decision after the
evidence is shown. T2/T3 compiler failures, paid replay, and Phase 3 remain
separate.

## Multi-Output Basis-Qualified Answer Variants No-Call Characterization (2026-09-01)

### Authority and scope

The user authorized the documented next provider-free characterization, not a
production evaluator repair, dataset edit, score correction, or replay. The new
fixture invents `Sample issuer`, `Unit Alpha`, both sources, all values, and all
answer surfaces. It contains no filing text, company/benchmark ID, provider
output, saved judge rationale, or acceptance oracle.

The executable proposal names the evaluator-only field
`accepted_answer_variants`. Each variant has a stable ID, a source-qualified
completeness `answer_key`, and `expected_outputs` covering the same required
semantic output IDs. Each expected output binds kind, label, subject, raw value
and unit, normalized unit, period, consolidation scope, and source-anchor
constraint. This differs from scalar `accepted_calculation_variants`, which must
continue to bind all operands to one calculation result.

### Fixed-output characterization

The test-only matcher validates schema completeness and uses distinct assignment
of actual outputs to expected outputs. It is an executable specification, not
production scoring or numeric-tolerance policy.

| Fixed case | Expected result |
| --- | --- |
| Complete consolidated share and amount | exactly `consolidated-answer` |
| Complete separate share and amount | exactly `separate-answer` |
| Consolidated share plus separate amount | no match |
| Missing share | no match |
| Equal amount with wrong source and/or scope | no match |
| Unknown selected scope | no match |
| Equal values under a different subject | no match |

Contract mutations also fail for a missing source constraint, duplicate variant
ID, or incomplete required-output coverage. The oracle does not mutate its fixed
inputs.

### Located production boundaries

The real `_example_from_dict` loader ignores the proposed field, so current
`EvalExample` has no typed owner for it and `accepted_answer_keys` remains only
the canonical answer when no scalar calculation variants exist. The real
completeness prompt likewise receives `canonical_answer_key`; a proposed
source-qualified variant appears only in the answer-under-test, not in the
reference section. Existing tests continue to show that forcing two direct
outputs into a scalar calculation variant fails the correct
`result_not_bound_to_all_matched_operands` guard.

Therefore this step proves the desired atomic semantics and exact integration
points, not evaluator acceptance. A future implementation needs strict typed
loading, a pure canonical-output/operand projection and distinct-output matcher,
and a trace-selected completeness reference with canonical fallback. No match,
partial match, mixed variant, invalid contract, or ambiguous complete match must
fail closed. Matching must not promote raw qualitative scores.

### Verification, invariants, and stop line

- New fixed-output characterization: 5/5.
- Nine-module semantic/evaluator/provenance/slot/ledger/import set: 242/242 in
  12.465 seconds, including semantic program 95, scope-qualified 17, evaluator
  projection 69, scalar variants 14, answer slots 11, numeric provenance 9, task
  artifacts 3, and import side effects 19.
- `python -m src.ops.audit_runtime_domain_terms`: PASS, 86 reviewed literals.
- `python -m unittest discover -s tests`: 698/698 in 19.472 seconds.

Production `src/ops/evaluator.py` remains at SHA-256
`058097be64ca9176db4f56f65ba2251155626873e67fa340edc816a91401b617`.
The full/multi-metric/multi-subtask curated datasets remain respectively
`19bb121507275a7c15406dddbda22b392bb870d6bf0fdb9a400d599de8eb1aba`,
`a21647a0fdc62eec187f7790bd263d0052359d0b8091135b82882e88482037a7`, and
`db6d4bd10b747c56bad4b4027971c6affca0a8d982dcf019594b04bfcf59d82a`;
the latest result remains
`6725d3248c4002c6f2f835786a59dc4180e7f09dd1a9e972aa594df606e93e5a`.
The 127-file runtime, source stores, saved results,
admission receipts, and excluded user files are unchanged. No provider,
embedding, benchmark, retrieval, parser/ingest, evaluator judge, or network call
was made and no result bundle was created. The index remains empty; paid
acceptance stays 1/3.

The next proposed step is production evaluator integration against the same
synthetic contract only. Curated answer variants require later source review and
an explicit decision. T3's wrong-row share, T2's company-versus-market selection,
paid replay, broader gate, fresh ingest, and Phase 3 remain separate and
unauthorized.

## Selected-Source Basis Disclosure No-Call Successor (2026-09-01)

### Scope and contract change

This provider-free successor implements only the first repair proposed by the
preceding scope-qualified characterization. It changes the existing semantic
program executor/renderer and reviewed rendering policy. Query hard scope,
candidate selection, source display, provenance/subject/unit/scope/coupling
validation, missing-output status, canonical trace, answer slots, ledger state,
evaluator schemas, answer keys, tolerances, and scores remain unchanged.

For an obligation whose consolidation scope is unknown, a validated primary
`direct_value` answer slot may supply its known consolidation scope for rendering
only. If all rendered numeric outputs share that known scope, the first numeric
output names it once. If independent outputs have different known scopes, each
is qualified. An unknown selected scope remains unlabelled and is never filled
from an unselected candidate, compiler rationale, benchmark key, table-wide
mention, or narrative compatibility witness. Explicit obligation scope retains
authority. Korean and English labels live in reviewed render policy/config.

The fixed synthetic fixture was extended before implementation. Six disclosure
assertions failed against the old renderer while eleven fail-closed controls
passed. After the bounded change, all seventeen pass. The controls include same-
basis single disclosure, cross-basis per-output disclosure, English policy
labels, unknown-scope anti-leakage, explicit conflicts, wrong/equal-valued rows,
coupled-context rejection, missing output, unknown unit, scalar provenance, and
the still-unimplemented multi-output evaluator boundary.

### Saved-program projection

A read-only no-call probe loaded `HYU_T3_072` from
`source_display_qualitative_focused_successor_2026-09-01`, reused its saved
semantic program and obligations, unioned the same six proposed/selected
candidates by immutable ID, and kept the saved prompt allowlist. The pure
executor produced the same values and evidence with one expected answer-only
delta: `2023년 Motional 투자장부금액` became
`2023년 연결기준 Motional 투자장부금액`.

The result remains `partial` at 2/3. Missing `ob_001`, the selected candidate IDs,
`candidate_subject_mismatch`, and the consolidated carrying-amount slot are
unchanged. The wrong-row share is still rejected. This projection is neither a
compiler correction nor a new qualitative judgement and does not turn the paid
row into an acceptance pass.

### Verification, immutability, and limits

- New synthetic disclosure/characterization: 17/17.
- Eight-module semantic/evaluator/provenance/slot/ledger/import set: 237/237.
- Existing semantic-program module: 95/95; evaluator projection 69/69; scalar
  calculation variants 14/14; import side effects 19/19; canonical DAG included.
- `python -m unittest discover -s tests`: 693/693 in 15.904 seconds.
- `python -m src.ops.audit_runtime_domain_terms`: PASS, 86 reviewed literals.
- Network-blocked fixture repeat: 17/17 and zero socket connection attempts.

The 127-file runtime build is
`e9a127d0cd0e0a17d780efa6ee3926f9ebb14198b6c83a684fbe9962d4aa3035`.
The saved Hyundai result remains
`2f96a543deeb652fd9989c1ed5cdd780bd6ddf850db9888fcd7160837519a51b`;
the top result remains
`6725d3248c4002c6f2f835786a59dc4180e7f09dd1a9e972aa594df606e93e5a`.
Both source-store fingerprints and raw SQLite hashes, profile/dataset,
admission/receipt bytes, predecessor results, and excluded user files are
unchanged. No provider, network, benchmark, report fetch, retrieval, parse,
ingest, embedding, evaluator, or judge call was made; no result bundle was
created and the index remains empty. Latest paid acceptance therefore stays 1/3.

### Residual boundary and stop line

The renderer repair does not make scalar calculation variants a multi-output
answer schema. A separately reviewed provider-free evaluator contract should
bind every required output's value, subject, period, basis, unit, and source in
one atomic allowed variant, while retaining the current scalar all-operands-
bound-to-result rule. Completeness may then receive the matched source-qualified
variant; numeric success or coverage must not promote qualitative scores. No
dataset edit, source variant, paid replay, compiler-selection repair, or Phase 3
work is authorized by this successor.

## Scope-Qualified Direct Answers No-Call Characterization (2026-09-01)

### Scope and evidence provenance

This is the authorized characterization follow-up, not a runtime repair, a paid
replay, or a new acceptance decision. The source of the motivating observation
is the immutable `source_display_qualitative_focused_successor_2026-09-01` bundle.
The new checked-in fixture `tests/fixtures/scope_qualified_direct_answers.json`
uses an invented issuer, subject, source IDs, and values. Its two basis-qualified
surfaces are `40% / 120백만원` and `35% / 220백만원`; no company or benchmark-specific
rule or live provider output is embedded in it.

The existing Hyundai receipt HTML was read without parsing or ingesting again.
Its SHA-256 remains
`641c41ae0648ef48e30d25bbb4b9923040ec460b151fdc39b6435076d14dd7df`.
LF-based locations confirm the consolidated notes heading at 12660, current
period/unit at 30427/30431, and `26% / 700,691백만원` at 30546/30550; separate
notes start at 77786, current period/unit at 90938/90942, and
`25.81% / 1,294,367백만원` at 91033/91037. They are two actual reporting bases,
not interchangeable values or grounds to auto-edit the answer key.

### Characterized owner boundaries

| Boundary | Current behavior fixed by the generic tests |
| --- | --- |
| Executor and answer slots | Both complete same-basis programs execute under an unspecified query; values, candidate IDs, and consolidation survive in output slots. Explicit company, period, consolidation, and measurement-basis conflicts remain rejected |
| Semantic renderer | Shared scope comes from obligations, not selected slots. Unknown query consolidation therefore omits a known selected basis. Explicit shared query basis is rendered |
| Independent versus coupled outputs | Empty coupling keys permit independently grounded outputs from different bases; this is not proof of one acceptable answer tuple. A common key rejects cross-context/basis inputs with `coupled_context_mismatch` |
| Candidate-ID authority | A rationale/table-wide mention cannot rescue a wrong local subject. The wrong row is rejected even when its numeric value equals the target value; missing required outputs remain partial despite valid ledger structure |
| Direct display | An unknown-unit value remains rejected even when a different source-basis row has a displayable amount |
| Scalar calculation variants | Each individual amount can match its own source/basis/period and result binding. Equal values do not defeat conflicting provenance constraints. Answer and trace must select the same numeric variant |
| Basis wording | Scalar numeric matching accepts the correct number with correct, omitted, or falsely stated basis wording. It is a numeric signal, not a semantic basis-disclosure check |
| Multi-output schema | Two valid direct operands do not share one scalar output that owns both candidate bindings. Encoding that answer tuple as an existing scalar variant fails `result_not_bound_to_all_matched_operands`; weakening the binding rule would be the wrong repair |
| Completeness and qualitative scores | The actual completeness prompt receives only `canonical_answer_key`, even when a different scalar variant matches the trace. The fixed mixed `evaluate_one` case retains raw/final faithfulness `0.7/0.7`, completeness `0.5`, and numeric judgement N/A. These are fixture-supplied scores, not model judgements or an explanation of T3's saved raw score |

`tests/test_scope_qualified_direct_answers.py` exercises model parsing, the pure
executor, a fixed structured compiler with its bounded retry, actual graph and
canonical trace/slot/ledger projection, scalar matching, the real completeness
prompt builder, and `RAGEvaluator.evaluate_one`. Failure fixtures retain the
invalid/missing binding on the one allowed retry. The compiler catalog and judge
responses are fixed, not retrieval or semantic model observations. No benchmark
file is loaded by the checked-in tests.

### Saved-program projection and verification

A separate read-only probe loaded T3's saved `calculation_plan.semantic_program`
and `answer_obligations`, unioned its `proposed_candidates` and
`selected_candidates` by immutable ID (six rows), and invoked
`execute_semantic_calculation_program` with the saved prompt-ID allowlist.
It reproduced the exact recorded answer string, `partial` with `ob_001` missing,
`700,691백만원` under the consolidated amount slot, and
`candidate_subject_mismatch`. The four narrative source measures are unchanged.
No compiler, provider, retrieval, evaluator judge, source parse, or store client
was run by that projection. It cannot repair the share selection or turn the
paid row into an acceptance pass.

Verification:

- New characterization 15/15; focused eight-module set 235/235: new 15, semantic
  program 95, evaluator projection 69, scalar variants 14, answer slots 11,
  numeric provenance 9, task artifacts 3, import side effects 19. Canonical DAG
  validation is also included in the semantic-program module.
- `python -m src.ops.audit_runtime_domain_terms`: 86 reviewed literals, PASS.
- `python -m unittest discover -s tests`: 691/691 in 15.141 seconds, PASS.
  Mock failure-path logs and the existing Python 3.14/Pydantic compatibility
  warnings do not represent provider execution or test failures.
- A network-blocked repeat passes the new 15/15 with zero socket connection
  attempts. `git diff --check` and new-file whitespace checks pass; the index
  remains empty.
- Runtime remains 127 files at
  `20fefb3212af7c2391fc7e358b53cf1c6c445b1dfd30a8326462808bd95ef9c7`.
  Profile/dataset, admission/receipt bytes, source-store fingerprints and SQLite,
  saved result bytes, and excluded user files remain unchanged. The T3 source
  result is still `2f96a543...9a51b`, and the top result is `6725d324...e93e5a`.
- Only tests/fixture and the current handoff, runtime-contract observation,
  refactoring-plan, and experiment-history documents changed in this step.
  There is no new result bundle, answer-key edit, score correction, staging, or
  paid call. Latest clean focused acceptance stays 1/3.

### Proposal and stop line

First propose a provider-free repair at the existing executor/renderer: expose
the known basis of each validated selected direct value, separate from the
query's hard constraints. Shared rendering is allowed only for genuinely shared
scope; unknown/conflicting source metadata cannot be silently labelled. This
does not choose candidates, replace values, or change validation/completeness.

Then review a separate multi-output answer-variant contract and source-qualified
completeness context. Each required output needs its own source binding within
one allowed answer variant; scalar calculation provenance must stay strict.
Basis wording cannot be certified from numeric equivalence alone, and raw
qualitative scores cannot be promoted from coverage. Any actual dataset variants
require source review and an explicit decision, not automatic acceptance of a
set of numbers. T3 wrong-row and T2 company-versus-market compiler selection are
separate follow-ons. No proposed repair is implemented in this characterization
step; paid replay, fresh ingest, broader gate, and Phase 3 remain out of scope.

## Source Group Display Evaluator Focused Provider Replay (2026-09-01)

### Approval, one-run execution, and accounting

The user explicitly approved canonical manifest
`70db0fb131b648e69b5fc096f4bdfdd3191502ffa90caab7df8538d376b4e91a`
and the `$0.40` authorization ceiling. The unchanged rehearsal was run again
immediately before dispatch. Its 5,490-byte canonical receipt matched
`e0be3cfaa0506d81e49fc49fde890458dc591929102c88fa9010717965568ed6`,
including runtime/profile/dataset hashes, source snapshots, target absence,
and provider/network/output-zero guards. This was followed by exactly one
provider-backed run, not another preparation-only turn.

The approved order was `HYU_T2_010`, `HYU_T3_072`, then `SAM_T2_078`,
Hyundai before Samsung, using `structural_selective_v2_prefix_2500_320` and
the immutable `policy_gate_regression_2026-06-03_1138_actual` source bundle.
The runner exited 0 and the 30-second heartbeat ended at 303.767 seconds.
All three questions started and completed once. Completion counting uses the
company/question pair and positive progress: the next company's zero-progress
initialization carries one stale previous-question completion tag, not a repeat.
There was no automatic run retry, additional company/question, fresh report
fetch, ingest, document embedding, KB replay, or five-question gate.

Per-question usage totals are 18 LLM calls and 543,641 tokens
(494,142 input; 49,499 output), 33 query embeddings, and zero document embeddings.
LLM phases are three routing/default calls, three requirement plans, six compiler
calls, and six evaluator judge calls. Each question used its allowed one internal
compiler retry; this is distinct from a benchmark run retry. Logs also show one
authorized 74-query router-initialization embedding batch per company outside
per-question usage.

The runner LLM estimate is `$0.2719901` (Hyundai `$0.1879761`, Samsung
`$0.0840140`), `$0.1280099` below the approved boundary. Embedding pricing is
absent from the profile and excluded. This is neither a complete provider bill
nor an in-flight hard-stop guarantee. Source-copied ingest timing/cost columns
are historical metadata, not new ingest or the current runtime cost.

### Canonical results and independent scores

Runtime error is 0 and task/artifact integrity is `ok` for all three rows.
Runtime completeness and clean focused acceptance are both 1/3. The formal
runner has one company-level full-eval failure. Every
`numeric_final_judgement=null` here is non-applicable, not a runtime failure.

| Row | Required outputs | Raw / final faithfulness | Completeness | Interpretation |
| --- | --- | --- | --- | --- |
| `SAM_T2_078` | `ok`, 2/2 | `1.000 / 1.000`, no override | `1.000` | Accepted; canonical total, consolidated-scope note, and Harman grounding preserved |
| `HYU_T2_010` | `partial`, 1/2 | `1.000 / 1.000`, no override | `0.500` | Narrative grounded, growth absent; market-wide volumes selected instead of company volumes |
| `HYU_T3_072` | `partial`, 2/3 | `0.700 / 0.700`, no override | `0.500` | Source-defined summary recovered, share missing; carrying-value score also needs basis-qualified review |

Samsung retains `cand_8277c0d709c2804d73cd`, the
`연구개발비용 총계 / 28,352,769 / 백만원 / 20240312000736:80:2` row.
The first attempt fails consolidation-scope validation; the retry adds
`cand_b1928cbb468e083a8bd8` from scope note `:81:3`. Harman is grounded in
`:101:16` and `:99:14`. Calculation and grounded rendering are `1.000`,
absolute error is 0, and context recall is `0.800`.

T2's 128-candidate prompt contains the exact `87.0만 대`, `78.1만 대`, and
source-stated `11.5%` IDs. The compiler instead proposes
`cand_0c407e2a6ae7af17a945` (`1,560.8만 대`) and
`cand_09cdec002a31afa52cd9` (`1,389.9만 대`), whose source sentences describe
the entire US market. Attempt one has formula/evidence-binding errors; attempt
two repairs those bindings but still fails each required input's `basis` check.
The program declares no applicability fields or source display. Only the policy
narrative at `20240313001451:760:14` executes. This is a semantic selection
failure after prompt exposure, not proof of missing retrieval. Relaxing scope
validation would not make those market-wide operands company sales.

T3 uses `source_defined_group` with exactly one required summary input and empty
independent-output coupling keys. It preserves all four source measures at
`20240313001451:183:93`: revenue `1,775`, continuing loss `(803,742)`,
other comprehensive income `12,115`, and total comprehensive loss `(791,627)`,
all in `백만원`. No invented net-income field replaces continuing loss.
The first direct candidates fail `empty_direct_rendering`. On retry, the
rationale describes a `26%` Motional share, but the actual selected ID
`cand_1316607db6121a0a7570` is the China/BHAF row's `53%` candidate.
`candidate_subject_mismatch` rejects it; the value is not rendered.
Rationale text is not authority to replace the bound candidate.

### Basis distinction, not an automatic answer-key correction

The executed T3 carrying candidate `cand_7ed11fbe3b01cc5882b8` at
`20240313001451:189:99` is `700,691백만원`, with consolidated provenance.
Read-only inspection of the existing receipt-matched HTML confirms current-period
consolidated notes state `26% / 700,691백만원` for Motional, while current-period
separate notes state `25.81% / 1,294,367백만원`. The question does not explicitly
choose consolidated or separate scope; the benchmark answer key chooses the
latter pair. The completeness judge records an answer-key value mismatch, but
that does not prove the consolidated amount is arithmetically or factually false.

Source: `data/reports/현대자동차/2023_사업보고서_20240313001451.html`,
SHA-256 `641c41ae0648ef48e30d25bbb4b9923040ec460b151fdc39b6435076d14dd7df`.
Using LF-based line numbers, the consolidated heading is at 12660,
current/unit labels at 30427/30431,
Motional share/value at 30546/30550; separate heading is at 77786,
current/unit labels at 90938/90942, share/value at 91033/91037.
The consolidation difference agrees with the earlier candidate-stage observation
that these are distinct real surfaces, not interchangeable numbers.

The answer retains consolidated scope in the slot/provenance but does not name
that basis in its final sentence. Basis-qualified display and evaluation therefore
remain an open contract. No answer key, score, numeric tolerance, unit policy, or
subject/scope validator was changed, and the original raw judgement is preserved.
The missing share alone still prevents T3 acceptance. The original raw
faithfulness reason is not persisted; do not equate the completeness reason with it.

### Artifacts, verification limits, and next seam

Local-only output:
`benchmarks/results/source_display_qualitative_focused_successor_2026-09-01`.
Top result SHA-256:
`6725d3248c4002c6f2f835786a59dc4180e7f09dd1a9e972aa594df606e93e5a`.
Hyundai/Samsung result hashes are
`2f96a543deeb652fd9989c1ed5cdd780bd6ddf850db9888fcd7160837519a51b` and
`f8db8bb652988469495892cf67aa655cf8306504732f00ca3bf156efc385e1f6`.
The admission's two source-store fingerprints, raw SQLite hashes, source result
hashes, profile/dataset, and 127-file runtime build `20fefb32...f9c7` match after
execution. No temporary `dart_eval_store_*` remains. Predecessor results and
the two excluded user files are unchanged. The immutable admission/receipts remain
under `source_display_qualitative_focused_admission_2026-09-01`; this approval
is now consumed. The execution audit is saved separately under the new output.

The prior no-call source-group/display/evaluator gates and 676/676 discovery
remain the unchanged-build test evidence; this turn did not rerun that suite or
modify runtime source. Actual source-defined summary recovery and independent
raw/final scores were observed. The new dual source/formula display was not
exercised because T2 produced no numeric output. This single run is not causal
proof about prompt changes, a broad quality claim, or fresh-ingest evidence.

Next, characterize scope-qualified direct-answer acceptance without providers:
separate source-basis variants, final basis disclosure, same-basis scoring, and
wrong-row ID rejection using generic fixtures. T2's company-versus-market
selection is a separate follow-on. No automatic dataset correction, weaker
guard, paid rerun, broader gate, or Phase 3 restart is authorized.

## Source Group Display Evaluator Focused No-Call Admission (2026-09-01)

This is the preparation-time record. The exact approval was subsequently granted
and consumed by the provider replay above; its zero-call receipts remain unchanged.

### Scope and exact inputs

The user authorized the documented preparation step, not another paid run.
No runtime source, numeric tolerance, answer key, provider route, or dataset was
changed. Phase 3 remains paused, and the last clean focused acceptance is still
1/3. The source-group/display/evaluator repairs need fresh provider observation.

Canonical schema-v3 admission manifest SHA-256:
`70db0fb131b648e69b5fc096f4bdfdd3191502ffa90caab7df8538d376b4e91a`.
It binds the 127-file runtime build
`20fefb3212af7c2391fc7e358b53cf1c6c445b1dfd30a8326462808bd95ef9c7`,
profile `f0d5d625d1b0a898e8ff59d66e7020bdac500bbce450964924532be6edbd0fb4`,
and dataset `19bb121507275a7c15406dddbda22b392bb870d6bf0fdb9a400d599de8eb1aba`.
The exact order is `HYU_T2_010`, `HYU_T3_072`, then `SAM_T2_078`, Hyundai before
Samsung, experiment `structural_selective_v2_prefix_2500_320`, one eval-only
execution, no automatic run retry, and the existing at-most-one internal compiler
recompile contract. No full gate, other questions/companies, KB replay, fresh
ingest/report fetch, document embedding, source mutation, or in-place output is
within scope.

The immutable source remains
`benchmarks/results/policy_gate_regression_2026-06-03_1138_actual`.
The proposed fresh target is
`benchmarks/results/source_display_qualitative_focused_successor_2026-09-01`.
It remained absent throughout preparation. The approved execution, if granted,
will use a 30-second progress heartbeat under that target.

The manifest enumerates Google `models/gemini-embedding-2` query/routing
embeddings at dimension 3,072, Google `gemini-2.5-flash` default/compiler and
`gemini-2.5-pro` evidence-extraction LLMs, Google `gemini-2.5-flash` evaluator
judges, and OpenAI `text-embedding-3-large` evaluator answer-relevancy embeddings
at dimension 3,072. Credential checks emit only presence booleans, not values.
The proposed authorization ceiling is `$0.40`; the latest same-scope runner LLM
estimate was `$0.2437528`. Embedding pricing is absent from the profile, and the
ceiling is not an in-flight provider kill switch or a new price quotation.

### Production-order no-call proof

The previously reviewed schema-v3 rehearsal was made reproducible as an ignored
local script, with the new date/build/target and latest observed cost. The script
has no paid-execution mode. It additionally guards socket connection attempts,
report-fetch/parser factories, and runtime-build stability. Company selection
must match actual profile order rather than being reordered to fit the manifest.
Its own SHA-256 is bound in the manifest:
`3e1e5eed1a5908e9d83c7c00c9f546c9693f433fc49c46211562c5baa494fccd`.

Two fresh processes entered `src.ops.benchmark_runner.main` with the intended
eval-only arguments. Both company-specific dataset projections were validated;
the normal disposable Hyundai store copy was verified and execution stopped at
the first vector-store/provider construction boundary. No provider or Chroma
client was constructed. Source metadata reads used SQLite
`mode=ro&immutable=1` and file-byte hashing only.

Both 5,490-byte canonical receipts match exactly at
`e0be3cfaa0506d81e49fc49fde890458dc591929102c88fa9010717965568ed6`.
They record provider construction 0, network calls 0, benchmark outputs 0,
unchanged runtime/source fingerprints, target absence, and unchanged temporary
store set. No `dart_eval_store_*` copy remained. Hyundai/Samsung store digests
remain `ebdbe7021f3eb34ad75007ee1736033f3428d50745921558fbae85498ba2ae81`
and `862a01380754fd64e2395ecf506f9e4daa6ed404385b623b862623c425ddba3e`.
Their raw SQLite hashes remain
`73b65b54dfdd6d63390a219f67b4d8a8e61b7169be481a3fc1f6c586db31db37`
and `f492d72be2753ac7a1c3012a36176d8c9ccf0d84fff1cc422c00e47fd5609ed0`,
with 1,764 and 967 embedding rows respectively.

### Saved artifacts, tests, and next authority boundary

Local-only files are in
`benchmarks/results/source_display_qualitative_focused_admission_2026-09-01`:
`manifest.json`, `rehearsal_1.json`, `rehearsal_2.json`, `rehearse.py`, and a README.
The canonical hash convention is sorted compact UTF-8 JSON without a terminal
newline. The two saved receipt files also match byte-for-byte; their file hash
including the terminal newline is
`4d58cbb27a139128f20c6de70758928a90a976ab91bdcd9a4eb94ed026231881`.
Their parsed payloads reproduce the exact canonical hashes above.

Runner/evaluator tests passed 99/99 and rehearsal syntax compilation passed.
The runtime is unchanged from the prior 676/676 full regression gate; no fresh
full run is claimed for this preparation-only step. Excluded user files are
unchanged, the staging index is empty, and all admission artifacts remain ignored.
This is production dispatch-boundary evidence, not provider schema acceptance,
semantic correctness, or independent qualitative acceptance.

Next request explicit approval of this exact manifest, one-run scope, and
`$0.40` ceiling. Immediately before any approved dispatch, rerun the no-call
script and compare the stored manifest/receipt, source state, and absent target.
Any mismatch invalidates this admission; the consumed predecessor approval
cannot authorize the changed build or a second run.

## Source Display And Qualitative Score Separation No-Call Successor (2026-09-01)

### Characterization and scope

This successor handled the two documented provider-free boundaries, not another
structural-refactoring slice or paid replay. Generic fixtures first reproduced
source-display loss when the deterministic result fell outside the source's
precision tolerance, and qualitative-score promotion at the public
`RAGEvaluator.evaluate_one` entry point despite a low fixed raw judgement.

The numeric fixture uses synthetic displayed inputs `40.0` and `44.0`, yielding
`10%`, beside a source-stated `10.2%`. Synthetic precise values `39.96` and
`44.04` demonstrate that such displays can result from input rounding; they are
not recovered hidden filing values or proof of the historical discrepancy's
cause. Controls include a clearly divergent `95.0%` source, equal/absent source
displays, incompatible scope or dimensions, empty source rendering, and valid
count/currency/percentage expressions. No company or benchmark ID enters these
runtime fixtures or decision rules.

The evaluator fixtures supply fixed judge and upstream coverage/numeric metrics
while leaving the real promotion policy active. Before the fix, fifteen
subcases promoted raw `0.0`, `0.4`, or `0.7` to `1.0`, including mixed numeric
PASS with fast gating enabled and narrative-only summary text. Removing only
the hybrid override would still leave the structured-summary override capable
of promotion. These are deterministic policy counterexamples, not new LLM
judgements about the saved answer or an explanation of its raw `0.700` score.

### Code and contract changes

`financial_calculation_execution.py` now separates preservation from adoption:

- Retain every valid selected source display's candidate ID, normalized value,
  display string, source rows/anchors, and executed operand/evidence projection.
- Keep `formula_result_value` and `formula_rendered_value` independently.
  `source_display_matches_formula` records the unchanged precision comparison;
  `source_stated_result_used` remains false when comparison fails.
- Preserve the calculated primary slot on disagreement and label both values
  through declarative English/Korean render templates. Large differences are
  not silently declared equivalent, and execution `ok` is not equivalence.
- Apply dimension compatibility to non-ratio source displays too and reject
  unrenderable selected source values. Existing scope/context checks remain.

`evaluator.py` removes the hybrid and structured-summary coverage-based
faithfulness overrides, together with their callerless question-marker and
answer-entity-coverage helpers. Their eight private-helper tests were replaced
by actual evaluation-entry tests. Numeric PASS remains unable to bypass mixed
or narrative judgement; the existing pure-numeric gate and full-abstention
handling are preserved. Numeric tolerance, answer keys, judge prompts, and
provider call budgets are unchanged. Removed helper references are zero in
`src` and `tests`.

### No-call verification and evidence limits

Twelve new test methods cover the boundaries above. The graph test uses a fixed
compiler output and a mock catalog, then the real executor, citations, canonical
trace, ledger projection, and deterministic evaluator. It retains both source
and formula displays, a calculated primary slot, ledger `ok`, and numeric/result
rendering scores `1.0`; qualitative judgement is disabled, not claimed passed.

Configured-runtime checks passed:

- Semantic-program tests: 95/95, including canonical graph/DAG.
- Evaluator projection: 69/69; adjacent formula/provenance/answer-slot/ledger/
  projection/variant/import tests: 151/151 including that evaluator and import
  side effects 19/19.
- Runtime-domain audit: 86 reviewed literals; affected pycompile: 5/5.
- Full unittest discovery: 676/676 in 21.374 seconds. The reduced legacy-test
  count reflects removal of obsolete promotion expectations, not skipped tests.

A separate read-only projection consumed only the saved T2 program and its five
selected candidates from
`benchmarks/results/post_successor_hyundai_residuals_focused_successor_2026-08-31/현대자동차-2023/results.json`.
It retained formula `11.395646606914212`, rendered calculated `11.4%` beside
source-stated `11.5%`, and recorded comparison false with no source substitution.
All five selected candidates, including the source percentage, remain in the
executed projection. Network connection was guarded; no provider call or
source-store access was needed. This is fixed-program reprojection, not a
fresh retrieval/compiler/qualitative-evaluator run.

The original top result SHA-256 remains
`6e2165cf0c6f966e509d59e556f9fc76f5e0bee30d249ce246b7679511942b16`;
the Hyundai result remains
`bf4b05972d5c8aa3ca4894bc4538692a6f0c6d97090768e820d16f6e4ac6749b`.
No old score or acceptance was rewritten: latest clean focused acceptance is
still 1/3, and the source-group/display/evaluator successors are not yet
provider-validated. Both excluded user files stay byte-identical, nothing is
staged, and benchmark artifacts remain outside the source patch.

Next prepare a fresh exact minimal focused-replay admission and two identical
production-order no-call rehearsals. Paid dispatch requires new explicit cost
approval; the previous one-run approval is consumed. Do not resume Phase 3 or
broaden to the five-question gate before that evidence boundary is satisfied.

## Source-Defined Requirement Ownership No-Call Successor (2026-08-31)

### Characterization and scope

The prior replay's source-summary failure was classified as a planner/evidence
contract gap, not a missing company-specific rule. Keeping a summary as one
output did not stop the planner from inventing mandatory member metrics inside
its `evidence_requirements`. A source-defined group needed an explicit ownership
contract at that inner layer as well.

New generic fixtures use a synthetic unit profile with independently reported
capacity/allocation values and an activity summary whose actual source members
are active and total items. These fixed structured outputs and mock candidates
are not recovered LLM responses or a new observation over a filing store. Before
the fix the structured model rejected the proposed group mode, while the raw
validator allowed a group requirement to be renamed, optionalized, or given
invented member hints. Separately, different-table direct outputs already passed
with empty coupling keys and correctly failed when artificially given a shared
key. That control located the coupling issue at declaration, not at a need to
relax context validation.

### Code and contract changes

`AnswerObligation` now has an explicit evidence mode. The default
`declared_inputs` retains existing raw inputs and query-defined facts or
relationships. Narrative-only `source_defined_group` leaves the planner's input
list empty and materializes one required input from the parent label, scope,
retrieval hints, and concept hints. Revalidation preserves the identical canonical
group and its normalized ID, but rejects invented members, changed scope/hints,
or an optional group input. Runtime does not detect open-ended summaries from
label keywords or silently replace explicitly declared requirements.

Existing planning normalization assigns the generated input its owned stable ID
and carries it into required-evidence retrieval projection and the compiler
prompt. The pure validator independently checks the normalized shape and blocks
malformed group outputs even when model parsing is bypassed. A non-object entry
in the requirement list is recorded as invalid instead of raising while checking
narrative bindings; the invalid group remains blocked. The compiler is
instructed to bind actual source headers/values to that one group requirement and
preserve their names and meanings.

The schema and planner/compiler prompts also clarify coupling: being in the same
query, company, or report is not a common-basis requirement. Independent outputs
leave the key empty; genuinely coupled outputs keep it and require common
context or explicit valid compatibility evidence. No coupling, scope, unit,
source-provenance, AST, rendering, or retry guard was loosened. No new module,
owner move, alternative calculation path, company/question branch, display
tolerance, or answer-key change was introduced.

### No-call verification and limits

Ten new test methods cover group materialization and idempotent round trips,
rejection of invented/numeric group requirements, unchanged declared inputs,
model-bypass rejection, missing/unknown evidence binding, unseen numbers,
conflicting company/period/consolidation/segment/basis, independent-output unit
and scope checks, and coupled-output compatibility controls. A fixed-output graph
fixture carries three obligations through one task, one source-group requirement,
stable IDs, compilation, execution, rendered outputs, and canonical trace with
exactly one planner and one compiler invocation and zero retries. Its candidate
catalog is mocked; it is not an end-to-end retrieval test.

Validation on the configured Python runtime passed:

- `python -m unittest discover -s tests -p test_semantic_calculation_program.py`:
  86/86, including the canonical graph DAG test.
- `python -m src.ops.audit_runtime_domain_terms`: 86 reviewed literals, no new
  runtime-domain exception.
- `python -m unittest discover -s tests -p test_import_side_effects.py`: 19/19.
- Affected `py_compile`: the three changed runtime/config files and the semantic
  test module, 4/4.
- `python -m unittest discover -s tests`: 672/672 in 12.439 seconds, including
  numeric provenance, answer slots/rendering, runtime projection, ledger, and
  retry contracts.

There were no provider calls, paid benchmark runs, or source-store accesses for
this successor. No saved benchmark result was rewritten or reclassified. The
last clean focused acceptance remains 1/3; correct future evidence-mode selection
and source-label interpretation still require actual provider-backed observation.
The modified runtime cannot reuse the consumed predecessor's exact admission.
Both excluded user files remain byte-identical, the staging index remains empty,
and local benchmark artifacts remain outside this source change. `git diff --check`
passed.

The next bounded work is provider-free characterization of source-stated versus
calculated display preservation and the evaluator's hybrid faithfulness override
as separate owners. Do not expand a tolerance or infer an unrecorded judge reason
to accept the observed T2 result. Phase 3 remains paused; any further paid replay
requires fresh admission and explicit cost approval.

## Post-Successor Hyundai Focused Provider Replay (2026-08-31)

### Approval, execution, and accounting

The user approved the exact schema-v3 manifest
`4e3e1d8df40cd25d8fa850eb9f571ec76dadbfc13b7154b22e67d9d96acfe3e4`
and `$0.40` one-run ceiling. Immediately before dispatch, a provider-free
production-order revalidation matched the previously reviewed 5,189-byte receipt
`7f2068120e3c5d6f35b3cb20d810fdae6c0f70587571d13009ccbb71f45b3e91`.
Runtime build, profile, dataset, source results/store hashes, target absence,
and disposable-copy invariants all matched.

Exactly one monitored `eval-only` run executed `HYU_T2_010`, `HYU_T3_072`, and
`SAM_T2_078`, Hyundai then Samsung, against the existing
`policy_gate_regression_2026-06-03_1138_actual` source. The new local bundle is
`benchmarks/results/post_successor_hyundai_residuals_focused_successor_2026-08-31`.
Heartbeat records show each question started once, both companies completed,
and final elapsed time was 289.588 seconds. There was no automatic run retry,
fresh report fetch, ingest, additional company/question, or KB replay.

Per-question totals are 17 LLM calls, 467,828 LLM tokens, 33 query embeddings,
and zero document embeddings. The LLM phases are three routing/default calls,
three requirement plans, five compiler calls, and six evaluator judge calls.
Internal compiler retries were 1, 1, and 0; these are not benchmark retries.
Logs additionally show the authorized router-initialization embedding batch
of 74 canonical queries once per company, outside per-question accounting.

The runner LLM estimate is `$0.2437528` (Hyundai `$0.1953466`, Samsung
`$0.0484062`), below the authorized ceiling by `$0.1562472`. Embedding pricing
is absent from the profile and excluded; this is not a complete provider bill
or a mid-request hard-stop guarantee. Historical ingest timing fields copied
from the source bundle do not represent a new ingest.

### Canonical audit, not score-only acceptance

All three rows have runtime error 0 and task/artifact integrity `ok`. Runtime
completeness is 2/3; clean focused acceptance is only 1/3. The formal runner
reports one company-level full-eval failure, not one runtime error.

| Row | Program result | Acceptance |
| --- | --- | --- |
| `SAM_T2_078` | `ok`, 2/2, no compiler retry | Accepted. The canonical R&D total and compatible scope note are preserved; raw/final faithfulness, completeness, calculation, and grounded rendering are all `1.000` without an override |
| `HYU_T2_010` | `ok`, 2/2 after one retry | Exact operand selection and arithmetic recovered. Source-stated display loss and raw-to-final faithfulness promotion remain held for review |
| `HYU_T3_072` | `partial`, 1/3 after one retry | Rejected. Direct outputs are missing and the narrative confuses distinct source measures; raw/final faithfulness and completeness are `0.300` |

Samsung selected `cand_8277c0d709c2804d73cd`, the
`연구개발비용 총계 / 28,352,769 / 백만원` row at `20240312000736:80:2`,
with compatibility note `:81:3` and Harman sources `:101:16` and `:99:14`.
The final answer preserves the source unit and the supported digital-cockpit,
IT-technology, and SDV explanation.

Hyundai T2 selected `cand_7d5294a9fe110c3e987f` (`87.0만 대`,
`20240313001451:65:1`) and `cand_2edd04c9130daab86745` (`78.1만 대`,
`20230315001030:60:2`). The first attempt failed source-context compatibility;
the retry added an explicit narrative witness and the validated formula produced
`11.395646606914212%`. Its displayed `11.4%` is arithmetically correct, and the
policy narrative is grounded at `20240313001451:760:14`. The planner left segment
and basis empty: this run does not prove the new unknown-only variable scope
allowance, which remains covered by generic fixtures.

The compiler also selected source-stated `11.5%` as
`source_display_candidate_id=cand_47bfc4cc05d682154cfa`. Nevertheless, execution
records `source_stated_result_used=false` and an empty `source_display_value`.
A provider-free call of the actual display predicate reproduces the rejection:
the gap is `0.10435339308578762`, larger than its source-output half-step
tolerance `0.05`. The runtime must distinguish a source statement from the
calculation over displayed inputs; simply enlarging the tolerance is not an
authorized or general fix. Raw faithfulness `0.700` was promoted to `1.000` by
`_should_override_hybrid_faithfulness`, with the recorded reason that mixed-query
evidence coverage was sufficient. The judge's original reason is not persisted;
the display discrepancy cannot be asserted as its exact cause. Correct arithmetic
and a final score of `1.000` therefore do not close this display/evaluator boundary.

Hyundai T3 now has three output obligations, including one narrative summary,
but that narrative declares mandatory revenue, operating-income, and net-income
requirements before seeing the source schema. This is the earlier field-invention
problem at the input-requirement layer, despite the output-level grouping. The
compiler reaches explicit-unit notes source `20240313001451:183:93` and selects
revenue `1,775`, continuing loss `(803,742)`, other comprehensive income `12,115`,
and total comprehensive loss `(791,627)`, all in `백만원`. It binds the same
continuing-loss candidate to both the operating-income and net-income requirements,
states that net income is also `(803,742)`, and omits total comprehensive loss
despite selecting its candidate. Source availability is no longer the blocker
for that summary; requirement semantics and compiler interpretation are.

The planner also assigns one coupling key to the two direct outputs and the
summary. First-attempt direct candidates fail `coupled_context_mismatch`; the
retry withdraws both and reports ambiguity about choosing across different
tables. The numeric coupling validator excludes the narrative itself. The
saved failure establishes the declaration/binding boundary, not permission to
remove coupling or presume that different contexts are compatible.

### Immutability, verification, and next work

The result SHA-256 values are:

| Artifact | SHA-256 |
| --- | --- |
| Top `results.json` | `6e2165cf0c6f966e509d59e556f9fc76f5e0bee30d249ce246b7679511942b16` |
| Hyundai `results.json` | `bf4b05972d5c8aa3ca4894bc4538692a6f0c6d97090768e820d16f6e4ac6749b` |
| Samsung `results.json` | `fc80a6a6fc7d203a9d3e345e9fe1c1369fa81f9c67e8f0bcdcb46bc2377e13db` |

Post-run source store path-and-byte fingerprints remain
`ebdbe7021f3eb34ad75007ee1736033f3428d50745921558fbae85498ba2ae81`
and `862a01380754fd64e2395ecf506f9e4daa6ed404385b623b862623c425ddba3e`.
Raw SQLite hashes remain
`73b65b54dfdd6d63390a219f67b4d8a8e61b7169be481a3fc1f6c586db31db37`
and `f492d72be2753ac7a1c3012a36176d8c9ccf0d84fff1cc422c00e47fd5609ed0`;
immutable read-only counts remain 1,764 and 967 embeddings. Source company
result files are unchanged, and no `dart_eval_store_*` directory remains.

The 127-file runtime still hashes to
`9fabb94a8106befedd43db769bffb9af3131240b807f504a668385cdf83eb1c9`.
Profile, dataset, and both excluded user files are byte-identical. The prior
full 662/662 no-call gate belongs to this unchanged build; no new runtime fix
or full-suite run was performed during this evaluation. Handoff documents were
updated and `git diff --check` passed. The staging index is empty; benchmark
bundles, stores, and heartbeats remain local and unstaged.

The next bounded provider-free seam is end-to-end source-defined summary
requirements and explicit coupled-output compatibility, characterized with
generic fixtures before changing code. Source-stated display preservation and
the hybrid faithfulness override are separate subsequent audits. Keep unit,
scope, context, and missing-obligation checks fail-closed. Further provider work
requires a new admission and cost approval; Phase 3 remains paused.

## Post-Successor Hyundai Focused Replay No-Call Admission (2026-08-31)

The fresh schema-v3 admission manifest is
`4e3e1d8df40cd25d8fa850eb9f571ec76dadbfc13b7154b22e67d9d96acfe3e4`.
It binds the 127-file runtime build
`9fabb94a8106befedd43db769bffb9af3131240b807f504a668385cdf83eb1c9`,
profile `f0d5d625d1b0a898e8ff59d66e7020bdac500bbce450964924532be6edbd0fb4`,
dataset `19bb121507275a7c15406dddbda22b392bb870d6bf0fdb9a400d599de8eb1aba`,
and the immutable Hyundai/Samsung source fingerprints. The exact ordered scope is
`HYU_T2_010`, `HYU_T3_072`, and `SAM_T2_078`, Hyundai then Samsung, experiment
`structural_selective_v2_prefix_2500_320`, one eval-only execution, and no
automatic run retry. The absent target is
`benchmarks/results/post_successor_hyundai_residuals_focused_successor_2026-08-31`.

The provider-operation list includes Google source-store query and routing
embeddings, Google default/compiler and evidence-extraction LLMs, Google evaluator
judges, and OpenAI evaluator answer-relevancy embeddings. It forbids document
embedding, fresh ingest/report fetch, source mutation, in-place output, unlisted
rows/companies, KB replay, automatic run retry, and Phase 3. The maximum is
`$0.40`; the latest same-scope runner estimate is `$0.2662671`, leaving
`$0.1337329`. Embedding pricing is not declared, and the ceiling is not an in-
flight provider kill switch.

Two fresh processes entered `src.ops.benchmark_runner.main`, validated the
company-specific question projections and disposable source-store copy, and
stopped before first vector-store/provider construction. Their full canonical
receipts are byte-identical: 5,189 bytes at
`7f2068120e3c5d6f35b3cb20d810fdae6c0f70587571d13009ccbb71f45b3e91`.
Both prove unchanged source fingerprints, target absence, unchanged temporary-
store set, zero provider constructors, zero network calls, and zero benchmark
outputs. This is provider-free admission evidence only; a paid run requires fresh
explicit approval for the exact manifest and ceiling.

That approval was subsequently granted and consumed by the single provider replay
recorded above; these no-call receipts remain the immutable admission evidence,
not an unused authorization for another run.

## Post-Successor Hyundai Residual Contracts No-Call Successor (2026-08-31)

### Generic characterization and implementation

The accepted-Samsung/rejected-Hyundai artifact remained immutable evidence. No
answer-key value or benchmark ID entered runtime control flow. Generic fixtures
first fixed three independent contracts:

1. a positive semantic query budget preserves the original composite query and
   reserves one most-specific available query for every required obligation or
   evidence-input group before period-balanced fill consumes the remaining fixed
   slots;
2. a formula variable may declare unknown-only applicability for `segment` or
   `basis`, while explicit conflict and company, period, or consolidation scope
   remain unbridgeable; and
3. a question whose unnamed summary members are defined by the source schema
   remains one narrative obligation instead of being expanded into conventional
   direct metrics before retrieval.

The same source-defined group contract allows a bounded set of locally matching
table alternatives only when no matching prose source exists. Generic section or
index keywords are not a declared-surface match. Direct rendering continues to
reject a finite value with `normalized_unit=UNKNOWN`, even when the requested
display unit is blank; runtime must select an explicit-unit source rather than
infer a unit.

### Immutable saved-source probes

Reprojecting the saved T2 query bundle through the new query budget reserved the
two period-specific quantity inputs and the policy narrative independently; no
required group was unreserved. The segment spelling difference is spacing-only,
and the compiler may explicitly bridge only the still-unknown basis metadata.
An explicitly contradictory basis remains invalid.

The T3 detail source has 24 peer chunks and none carries a unit hint, so those
legacy values remain fail-closed. A separate notes table at
`20240313001451:183:93` carries `unit_hint=백만원` and the source-visible columns
for revenue, continuing profit/loss, other comprehensive income, and total
comprehensive income. With ownership, carrying value, and the open-ended summary
as three obligations, the unchanged eight-query budget reserves a specific query
for each. The summary-specific query ranks the explicit-unit notes table sixth in
the saved BM25 corpus. This proves source availability under query admission; it
does not prove a future LLM selection or retroactively accept the paid artifact.

The Hyundai source SQLite remains
`73b65b54dfdd6d63390a219f67b4d8a8e61b7169be481a3fc1f6c586db31db37`,
and its structure graph remains
`110e7063e78f5a75a92fb602c552761304937d3e26329500cf87cd33a374740a`.
No `dart_eval_store_*` directory remains.

### Verification and next boundary

- focused semantic-program and retrieval contracts: 113 / 113;
- expanded calculation, provenance, rendering, runtime projection, evaluator,
  and ledger contracts: 285 / 285;
- `python -m src.ops.audit_runtime_domain_terms`: passed with 86 reviewed
  literals;
- import side effects plus canonical graph/DAG: 20 / 20;
- affected-file pycompile: passed;
- full unittest discovery: 662 / 662;
- `git diff --check`: passed with line-ending warnings only.

Provider, embedding, evaluator, Chroma-client, and benchmark calls were zero.
The next operational step is a fresh no-call schema-v3 admission manifest and two
production-order rehearsals for the same three rows. The predecessor manifest is
stale because the runtime build changed. A provider replay requires separate
approval after byte-identical receipts; Phase 3 remains paused.

## Candidate-Stage Generic Repairs Focused Successor (2026-08-31)

### Authorized execution and audit

The user approved the exact schema-v3 admission manifest
`e9839d111f9bd76a674ee7dd7c4c0d59f75e0836f74cd3e364b2f39b4803435e`.
The monitored production-order `--eval-only` run executed exactly once over
`HYU_T2_010`, `HYU_T3_072`, and `SAM_T2_078`, Hyundai then Samsung. It reused
only `structural_selective_v2_prefix_2500_320` from
`benchmarks/results/policy_gate_regression_2026-06-03_1138_actual` and wrote the
ignored local successor under
`benchmarks/results/candidate_stage_generic_repairs_focused_successor_2026-08-31`.
The runner completed 2/2 companies and 3/3 questions in 283.0 seconds with
runtime error 0 and task/artifact ledger integrity `ok` for every row. No
automatic run retry, fresh ingest, report fetch, extra company, or extra question
ran. Each row used one semantic-program compiler retry allowed by the runtime
contract; this is distinct from retrying the paid benchmark execution.

Independent post-run aggregation gives 18 LLM calls, 511,582 prompt plus 45,117
output tokens, 556,699 total tokens, 33 query-embedding calls, and zero document-
embedding calls. The runner-estimated LLM cost is `$0.2662671`, leaving
`$0.1337329` below the approved `$0.40` ceiling. Embedding pricing is absent from
the profile and is not included in that estimate.

### Semantic results

| Row | Result | Trace evidence |
| --- | --- | --- |
| `SAM_T2_078` | **ACCEPTED**, `ok`, 2/2 | Direct candidate `cand_8277c0d709c2804d73cd` preserves `연구개발비용 총계 / 28,352,769 / 백만원` from `20240312000736:80:2`; `cand_b1928cbb468e083a8bd8` supplies the adjacent connected-scope note and two narrative candidates ground Harman. Faithfulness, completeness, calculation, and grounded rendering are `1.000`; absolute error is `0` |
| `HYU_T2_010` | **REJECTED**, `partial`, 1/2 | Planner scope is now query-owned: consolidation `unknown`, segment `미국 시장`, basis `판매대수`. `cand_7d5294a9fe110c3e987f` for the current-period value reaches the 128-row prompt, but the expected prior-period `cand_2edd04c9130daab86745` does not. The first compiler attempt selects alternatives that fail four generic requirement checks: `segment` and `basis` for both period inputs. Retry retains only the grounded policy narrative |
| `HYU_T3_072` | **REJECTED**, `incomplete`, 0/5 | All five obligation consolidation scopes are correctly `unknown`, closing the earlier hard-scope defect. The compiler selects same Motional-row candidates for `25.81`, `1,294,367`, and `-803,742`, but their raw/normalized display units are unavailable and all three fail `empty_direct_rendering` on both attempts. Revenue and operating-income bindings are also absent, so unit/display recovery must be separated from whether the planned five-output interpretation is supported by the source schema |

`numeric_final_judgement = null` for the accepted Samsung mixed row is treated
as not-applicable, not failure: the deterministic calculation, display,
faithfulness, completeness, error, and ledger signals are all healthy. The top,
Hyundai, and Samsung result SHA-256 values are respectively
`e0ea65581895a23f77f79d38b3c078b2677aa509e1b9e20e3f3b919c3a03cdd8`,
`dd2aad2e5899bf8c52567d2987e43d1a23a42f0e95ea61a220ee0294c72976cb`,
and `6f63c7fcd704436d19a02bb2c1391a35fd15fc549be900ef4a520208fa6b543b`.

### Immutable-store and next boundary

The runner-equivalent path-and-byte store fingerprints remain
`ebdbe7021f3eb34ad75007ee1736033f3428d50745921558fbae85498ba2ae81`
for Hyundai and
`862a01380754fd64e2395ecf506f9e4daa6ed404385b623b862623c425ddba3e`
for Samsung. Their raw SQLite SHA-256 values remain
`73b65b54dfdd6d63390a219f67b4d8a8e61b7169be481a3fc1f6c586db31db37`
and `f492d72be2753ac7a1c3012a36176d8c9ccf0d84fff1cc422c00e47fd5609ed0`.
No disposable `dart_eval_store_*` directory remains, and every output is under
the ignored `benchmarks/results/**` boundary.

This accepts the Samsung source-window repair but does not authorize broad
integration. The next work is provider-free characterization of two separate
Hyundai seams: prior-period prompt admission plus evidence-backed segment/basis
compatibility for T2, and legacy-row unit/display recovery plus obligation-to-
source availability for T3. Direct-render and scope validators remain
fail-closed; company/question branches, another provider replay, and Phase 3 are
not authorized.

## Candidate-Stage Generic Repairs Focused Replay No-Call Admission (2026-08-31)

### Exact scope and canonical manifest

The post-repair integration scope is fixed to `HYU_T2_010`, `HYU_T3_072`, and
`SAM_T2_078`, in Hyundai-then-Samsung company order. It reuses only experiment
`structural_selective_v2_prefix_2500_320` from immutable source bundle
`benchmarks/results/policy_gate_regression_2026-06-03_1138_actual`. The intended,
still-absent target is
`benchmarks/results/candidate_stage_generic_repairs_focused_successor_2026-08-31`.
Other companies and questions, KB replay, report fetch, parse/ingest, document
embedding, in-place evaluation, source mutation, automatic run retry, and Phase 3
are forbidden.

The canonical schema-v3 manifest SHA-256 is
`e9839d111f9bd76a674ee7dd7c4c0d59f75e0836f74cd3e364b2f39b4803435e`.
It binds the 127-file runtime-source build
`8f2f9afc2b5c4b12f13084b5c328dbc9bcfdd5170fdc39ecbc0b9272f423b1d9`,
profile `f0d5d625d1b0a898e8ff59d66e7020bdac500bbce450964924532be6edbd0fb4`,
and dataset `19bb121507275a7c15406dddbda22b392bb870d6bf0fdb9a400d599de8eb1aba`.
The runtime build digest covers path and bytes below `src/**`, excluding only
Python cache files.

The permitted provider-operation types are all enumerated: Google
`models/gemini-embedding-2` at dimension 3,072 for source-store query and agent
routing embeddings; Google `gemini-2.5-flash` for the default agent/compiler;
Google `gemini-2.5-pro` for evidence extraction; Google `gemini-2.5-flash` for
evaluator LLM judges; and OpenAI `text-embedding-3-large` at dimension 3,072 for
evaluator answer relevancy. Credential checks retained presence booleans only.
The manifest permits one execution with no automatic run retry and a `$0.40`
authorization ceiling. The latest same-scope runner estimate was `$0.3156427`,
leaving `$0.0843573` of headroom; embedding pricing is absent from the profile,
and the ceiling cannot interrupt a request already in flight.

### Production-order rehearsal and immutable inputs

The rehearsal entered `src.ops.benchmark_runner.main` with the intended
`--eval-only`, company, question, target, and 30-second heartbeat arguments. It
validated both company-specific dataset projections, fingerprinted the source
stores, made the normal disposable Hyundai store copy, and stopped at the first
`VectorStoreManager` construction boundary. The vector-store, agent, and
evaluator provider constructors were replaced only by fail-closed rehearsal
sentinels. No Chroma client or provider was constructed and no network call was
made.

Two fresh processes emitted the same 5,302 canonical bytes. Their manifest hashes
and full byte payloads matched exactly; the receipt SHA-256 for both is
`fdfbf90f3adb195e9ffe7134177ac68bc856c8fdfe9e40719c09d04ae66459af`.
The intended target remained absent, no benchmark or heartbeat output was
created, and the pre-existing `dart_eval_store_*` set was identical before and
after each run.

The runner's path-and-byte store fingerprints remained
`ebdbe7021f3eb34ad75007ee1736033f3428d50745921558fbae85498ba2ae81`
for Hyundai and
`862a01380754fd64e2395ecf506f9e4daa6ed404385b623b862623c425ddba3e`
for Samsung. Their raw SQLite SHA-256 values remained respectively
`73b65b54dfdd6d63390a219f67b4d8a8e61b7169be481a3fc1f6c586db31db37`
and `f492d72be2753ac7a1c3012a36176d8c9ccf0d84fff1cc422c00e47fd5609ed0`,
with 1,764 and 967 embeddings read through immutable SQLite. Source files were
read only; the rehearsal did not open either source through a Chroma client.

This is admission evidence, not a benchmark refresh or semantic acceptance. No
provider-backed successor is authorized yet. The next action is to request fresh
approval for exactly the one-run scope and `$0.40` ceiling above; Phase 3 remains
paused.

## Obligation-Owned Atomic Seed Preservation No-Call Successor (2026-08-31)

### Characterization and proved owner

The final provider-free owner from the candidate-stage replay was the targeted
seed supplement, not the compiler or candidate catalog. The immutable source
contains the canonical numeric table at `20240312000736:80:2`. The saved runtime
instead preserved the adjacent scope note `:81:3`, while the supplemental numeric
group reserved `:186:72`, a preferred-statement note table that matched only the
generic short hint for a total. The selector sorted statement type before the
strength of the source-visible declared surface, so a contextual coincidence
could own the group's single reserved source.

A company- and benchmark-independent fixture fixes that failure with three
candidates: a preferred-statement table matching only a generic total, a
scope-only context note that repeats the full request but carries no value, and
a local row/value table using a semantically specific declared surface. The old
ordering selects the generic preferred-statement table. The repaired ordering
selects the local row/value source.

### Deterministic repair

Required numeric supplementation now evaluates atomic evidence before statement
priors. A parser-projected local `table_header_context` row or a full raw pipe row
must contain both a numeric surface and a declared obligation/input surface.
Among those witnesses, generic surface specificity is ordered by token and
alphanumeric length; compatible statement type, table structure, and the prior
score remain later tie-breakers.

The check strips index metadata and deliberately excludes section text,
`table_context`, flattened `table_value_labels_text`, and arbitrary prose as
atomic authority. It selects only a document for `seed_retrieved_docs`; it does
not parse a value, create a candidate, bind an answer, or weaken compiler and
validator provenance checks. No company, question ID, answer value, or financial
metric literal was added to runtime control flow.

### Immutable projection and limits

The saved Samsung SQLite was opened only with `mode=ro&immutable=1`. A deterministic
projection reused the saved eight visible retrieval documents and the full local
BM25 corpus. The visible retrieved IDs remain eight and still do not include
`:80:2`; the preserved seed window now includes `20240312000736:80:2`. This is the
intended boundary: the compiler may inspect the exact source through the broader
seed catalog without forcing it into the user-visible top-k window.

The source SQLite SHA-256 remained byte-identical before and after at
`f492d72be2753ac7a1c3012a36176d8c9ccf0d84fff1cc422c00e47fd5609ed0`.
Chroma, provider, embedding, evaluator, and benchmark execution counts were all
zero. Therefore the earlier `SAM_T2_078` partial result remains the latest paid
observation and is not retroactively converted to a pass.

### Verification and next boundary

- semantic-program characterization/regression: 73 / 73;
- adjacent provenance, answer-slot, ledger, runner/evaluator, retrieval-scope,
  and retrieval-hint contracts: 169 / 169;
- `python -m src.ops.audit_runtime_domain_terms`: passed with 86 reviewed
  literals;
- import side effects plus canonical graph/DAG: 32 / 32;
- full unittest discovery: 657 / 657;
- `git diff --check`: passed apart from the repository's existing line-ending
  warnings.

All three candidate-stage owners now have provider-free repairs. The next safe
step is a production-order no-call manifest and two byte-identical rehearsals for
the same three-row store-fixed successor. An actual provider replay still needs
fresh exact scope and cost approval. Phase 3 remains paused.

## Explicit-Query Hard-Scope Provenance No-Call Successor (2026-08-31)

### Characterization and deterministic boundary

The second owner identified by the candidate-stage replay was handled without a
provider call. A generic fixture uses a target venture rather than any company,
filing, benchmark row, or answer value. Before the repair, a query with no
consolidation wording preserved LLM-proposed obligation scopes as
`consolidated / separate`, even when report metadata independently proposed a
hard scope. A single explicit consolidated query also retained the conflicting
LLM value `separate` instead of following the query.

Runtime now derives the allowed hard scopes from the declarative
`CONSOLIDATION_SCOPE_POLICY.query_markers`. Scope normalization applies the
following generic contract:

- no explicit query scope: obligation, required-input, and task scope are
  `unknown`;
- exactly one explicit query scope: that value overrides a conflicting or
  missing LLM value;
- both scopes explicitly requested: each obligation may keep only a requested
  scope, while the shared task constraint remains `unknown`.

Report metadata and common financial-document defaults remain useful source
context elsewhere, but they cannot create a user hard constraint in the
pre-evidence requirement plan. The requirement-planner prompt states the same
rule. Later candidate scope validation remains fail-closed when the user did
explicitly request a scope. No company, question ID, answer value, or financial
metric branch was added.

### Stored-payload diagnostic and limits

The recorded `HYU_T3_072` question does not state consolidated or separate
scope. Its saved requirement-plan obligations carried
`consolidated / consolidated / separate`. Feeding those saved obligations into
the repaired normalizer through a fixed local structured-output stub produced
`unknown / unknown / unknown`, with task scope `unknown`. Provider, embedding,
and evaluator calls were all zero.

This is a planner-normalization projection only. It did not invoke retrieval,
compile a new program, select a candidate, execute a formula, or rerun the
benchmark. The earlier partial artifact therefore remains the latest integration
observation for that row.

### Verification and next boundary

- semantic-program characterization/regression: 73 / 73;
- adjacent provenance, answer-slot, ledger, runner/evaluator, retrieval-scope,
  and retrieval-hint contracts: 168 / 168;
- `python -m src.ops.audit_runtime_domain_terms`: passed with 86 reviewed
  literals;
- import side effects plus canonical graph/DAG: 32 / 32;
- full unittest discovery: 656 / 656.

The remaining provider-free candidate-stage seam is the independent Samsung
retrieval/seed omission: its exact source exists in the immutable store but did
not enter either runtime source window. No provider replay or Phase 3 work is
authorized.

## Required-Input Prompt Admission No-Call Successor (2026-08-30)

### Characterization and repair

The first owner identified by the candidate-stage replay was handled without a
provider call. A company-, filing-, and benchmark-independent fixture first
proved two separate generic failures. Required raw inputs had no pre-budget
admission ownership, so broader result relevance could consume their prompt
share. Separately, sentence extraction treated every period as punctuation: the
later value in `Target venture series increased 11.5% to 870.0 items.` retained
only `5% to 870.0 items.` and lost the subject-bearing prefix.

Prompt projection now derives required-input relevance groups only from required
`evidence_requirements`; it excludes optional inputs and the parent output
surface. Each positive group reserves at most four candidates from its
highest-ranked local source before ordinary obligation/source coverage fills the
unchanged global budget. This is candidate visibility, not value selection.
Numeric context extraction now ignores a period between two digits when locating
the enclosing sentence, so co-stated rate and quantity candidates retain the
same subject, period, and relation. No financial term, company, question ID,
answer value, or operation-word branch was added.

### Immutable diagnostic and limits

The recorded Hyundai source window was reconstructed by querying the existing
SQLite only with `mode=ro&immutable=1`; Chroma was not opened on the source.
Within that reconstructed source-window slice and the unchanged 96-numeric plus
32-narrative projection limit, candidate
`cand_7d5294a9fe110c3e987f` (`87.0만 대`) and candidate
`cand_2edd04c9130daab86745` (`78.1만 대`) are both admitted with their complete
local sentences. The source SQLite size, mtime, and SHA-256 were identical
before and after; its SHA-256 remains
`73b65b54dfdd6d63390a219f67b4d8a8e61b7169be481a3fc1f6c586db31db37`.

This slice-level result validates the repaired owner and its preserved source;
it is not a fresh end-to-end compiler decision and does not retroactively turn
the earlier `HYU_T2_010` partial artifact into an acceptance pass. No benchmark,
LLM, embedding, evaluator, ingest, network, or disposable-store run occurred.

### Verification and next boundary

- semantic-program characterization/regression: 71 / 71;
- adjacent provenance, answer-slot, ledger, runner/evaluator, retrieval-scope,
  and retrieval-hint contracts: 168 / 168;
- `python -m src.ops.audit_runtime_domain_terms`: passed with 86 reviewed
  literals;
- import side effects plus canonical graph/DAG: 30 / 30;
- full unittest discovery: 654 / 654;
- source-store immutable fingerprint check: passed.

The next provider-free seam is explicit-query ownership of hard consolidation
scope for pre-evidence planning. Samsung's independent retrieval/seed omission
remains after that. No additional provider replay or Phase 3 work is authorized.

## Candidate-Stage Focused Replay And Owner Classification (2026-08-30)

### Authorized execution and integrity

After the byte-identical no-call admission below, the user authorized exactly
one monitored eval-only execution over `HYU_T2_010`, `HYU_T3_072`, and
`SAM_T2_078`. The run reused only the Hyundai and Samsung persisted stores from
`benchmarks/results/policy_gate_regression_2026-06-03_1138_actual` and wrote the
ignored local successor
`benchmarks/results/candidate_stage_observability_focused_successor_2026-08-30`.
No automatic retry, fresh fetch/parse/ingest, document embedding, other company,
or other question was authorized or executed.

The run completed normally in 373.4 seconds. Both companies and all three rows
finished with runtime error 0 and task/artifact integrity `ok`. Usage was 18 LLM
calls, 573,899 LLM tokens, 33 query-embedding calls, zero document-embedding
calls, and runner-estimated `$0.3156427`, below the `$0.40` ceiling by
`$0.0843573`. Embedding pricing is not included in the runner estimate. The
top-level result SHA-256 is
`49351e06df72722a63ae4209e358cb84c9dc73a3403912c385576a84bdd4c6a7`.

The source top-level SHA-256 remained
`f8f641f47d3b7dbc3e88bb455c15e7930fbecec1f22e7cfd4f4c3abf9ef72c9d`.
The admission file-manifest fingerprints remained
`e2e0d391449d1e87efe43b722dc6ca6fc60271894cd2669575d46f138ed6026a`
for Hyundai and
`b39280122c6e4d6989e3050dcd727545b1b90e1c7dab60bd16c33ac1fa5d79b7`
for Samsung. Their raw SQLite SHA-256 values remained
`73b65b54dfdd6d63390a219f67b4d8a8e61b7169be481a3fc1f6c586db31db37`
and `f492d72be2753ac7a1c3012a36176d8c9ccf0d84fff1cc422c00e47fd5609ed0`.
No `dart_eval_store_*` directory remained after execution.

### Semantic result and proved owner boundaries

All three rows were `partial`, so the focused acceptance failed despite healthy
execution:

| Row | Result | Candidate-stage evidence |
| --- | --- | --- |
| `SAM_T2_078` | 1/2; Harman narrative completed, research-and-development total missing | Exact total `28,352,769` occurs in source `20240312000736:80:2`, which is absent from both retrieved and preserved seed source IDs. The value never reached source candidates, catalog, or prompt |
| `HYU_T2_010` | 1/2; policy narrative completed, growth calculation missing | Exact `87.0만 대` and `78.1만 대` sources are preserved in the seed window. Deterministic reconstruction reproduced the runtime per-source catalog counts and fingerprints, and the exact value candidates are in those catalogs but absent from the 128-row prompt. Nearby percentages were admitted instead |
| `HYU_T3_072` | 1/3; `700,691백만원` carrying value completed, share and net result ambiguous | The target-row `25.81`, `1,294,367`, and `-803,742` candidates all appear in the prompt. The requirement plan assigned hard `consolidated`/`separate` scopes not explicit in the question. The first compiler attempt also emitted expressions for direct obligations; the validator rejected those and a wrong-subject share candidate fail-closed |

The stage evidence rules out one combined benchmark-tuning patch. `SAM_T2_078`
belongs to retrieval/source preservation. `HYU_T2_010` belongs first to bounded
prompt admission owned by declared evidence requirements, not operation-word
lexical preference. `HYU_T3_072` belongs to scope provenance and direct-binding
compiler behavior after successful prompt exposure. The valid `700,691백만원`
note value and the detailed-table `1,294,367` value are distinct real surfaces;
the latter must not be forced solely because it is the benchmark reference.

No runtime policy changed in this experiment-history update. The next work is a
provider-free generic characterization for each owner, beginning with required-
input prompt coverage and explicit-query-owned hard scope, followed separately
by the source-window omission. Additional provider replay and Phase 3 remain on
HOLD.

## Candidate-Stage Focused Replay No-Call Admission (2026-08-30)

### Exact scope and provider boundary

The smallest affected integration observation is fixed to `HYU_T2_010`,
`HYU_T3_072`, and `SAM_T2_078`, in Hyundai-then-Samsung company order. It reuses
only experiment `structural_selective_v2_prefix_2500_320` from
`benchmarks/results/policy_gate_regression_2026-06-03_1138_actual` and writes,
only after fresh approval, to the still-absent ignored target
`benchmarks/results/candidate_stage_observability_focused_successor_2026-08-30`.
NAVER, LGE, KB, fresh fetch/parse/ingest, document embeddings, other questions,
automatic retry, and Phase 3 are outside the manifest.

The manifest binds Google `models/gemini-embedding-2` at dimension 3,072 for
disposable-store queries; Google `gemini-2.5-flash` for the default agent and
evaluator; Google `gemini-2.5-pro` for evidence extraction; and OpenAI
`text-embedding-3-large` at dimension 3,072 for evaluator answer relevancy.
Credential checks recorded presence booleans only. The runtime build is
`4f84b59ea1926c5a2306bc2e602e29fee68b3526bd9997dbed4ee8eff53155e0`,
the profile is
`f0d5d625d1b0a898e8ff59d66e7020bdac500bbce450964924532be6edbd0fb4`,
and the dataset is
`19bb121507275a7c15406dddbda22b392bb870d6bf0fdb9a400d599de8eb1aba`.

### Cost, rehearsal, and immutability

The latest paid artifact for the same three rows recorded 18 LLM calls,
562,200 tokens, 33 query-embedding calls, zero document embeddings, and a
runner estimate of `$0.2843844`. The admission permits exactly one execution,
no automatic retry, and a `$0.40` ceiling: `$0.1156156`, or about 40.7%, of
headroom. The estimate excludes embedding pricing because the profile does not
declare it. The ceiling is an authorization/reporting boundary, not a
provider-side mid-request hard stop.

Two production-order no-call rehearsals stopped before vector-store/provider
construction and emitted byte-identical canonical output at receipt
`0c229555c3cd9d9216358c7393a26f0aa6b4931eaa404a007197a3facf2d9da4`.
Provider and network calls were zero. The target stayed absent, no
`dart_eval_store_*` directory existed before or after, and no benchmark output
was created.

The receipt-defined Hyundai and Samsung whole-store fingerprints remained
`e2e0d391449d1e87efe43b722dc6ca6fc60271894cd2669575d46f138ed6026a`
and `b39280122c6e4d6989e3050dcd727545b1b90e1c7dab60bd16c33ac1fa5d79b7`.
Their raw SQLite SHA-256 values remained
`73b65b54dfdd6d63390a219f67b4d8a8e61b7169be481a3fc1f6c586db31db37`
and `f492d72be2753ac7a1c3012a36176d8c9ccf0d84fff1cc422c00e47fd5609ed0`,
with 1,764 and 967 embeddings. Source `results.json`, reports, context caches,
and all store bytes were unchanged. This is admission evidence only: the
provider replay has not run and still requires fresh approval.

## Candidate-Stage Provenance Observability (2026-08-30)

### Characterization and contract

The saved five-question successor exposed missing prompt IDs but did not retain
the preserved seed-window or full catalog source identity. It therefore could
not distinguish a retrieval/window miss from an incomplete local-cell
projection or a prompt-budget drop. A provider-free generic fixture now fixes
those three states independently: an expected source absent from both windows,
a present source whose reconstructed required candidate is absent from the
catalog fingerprint, and a catalog candidate omitted from the prompt.

Retrieval now records ordered, deduplicated stable source IDs and unidentified
counts for both `retrieved_docs` and `seed_retrieved_docs`. The semantic
calculation plan records `semantic_candidate_stage_diagnostics_v1`: total and
per-source source/catalog/prompt counts, numeric/narrative/other kind counts,
fingerprints over sorted opaque candidate IDs, and prompt-drop counts. The
compiler maps exposed IDs back to the code-owned catalog for attribution. No raw
value, row label, source text, or full catalog is copied into this diagnostic.

### Verification and interpretation

Before implementation, the focused fixture failed because both the diagnostic
API and retrieval `source_window` field were absent. After implementation,
semantic-program tests pass 68/68, retrieval tests 34/34, import/DAG tests
19/19, the runtime-domain audit reviews 86 literals, `py_compile` passes,
`git diff --check` reports no error, and full discovery passes 651/651.

No provider-backed benchmark, persisted-store retrieval, embedding, ingest,
store mutation, or evaluator run occurred. Synthetic unit tests exercised the
trace path; retrieval selection, calculation, ledger, evaluator, and dataset
semantics did not change. The historical paid successor remains the latest
integration observation and cannot be retroactively assigned to one of the new
stages. No retrieval preservation, catalog projection, prompt-budget, or
compiler-retry policy changed. A future minimal affected store-fixed replay
requires an exact manifest and cost ceiling, two byte-identical no-call
rehearsals, and fresh approval; only its new trace may select the next repair
owner.

## Candidate-Catalog Source Completeness And Legacy Header Chains (2026-08-30)

### Read-only provenance audit

This provider-free seam opened the historical Samsung and Hyundai Chroma SQLite
files only through SQLite URI `mode=ro&immutable=1`. Before and after the audit,
the Samsung file remained 40,361,984 bytes at SHA-256
`f492d72be2753ac7a1c3012a36176d8c9ccf0d84fff1cc422c00e47fd5609ed0`;
the Hyundai file remained 69,447,680 bytes at SHA-256
`73b65b54dfdd6d63390a219f67b4d8a8e61b7169be481a3fc1f6c586db31db37`.
No retrieval query, embedding, LLM, evaluator, ingest, or benchmark execution ran.

Current parser output carries `table_row_records_json`,
`table_value_records_json`, and `table_object_json`. The older stores predate
those fields but retain full pipe-table text and header context. Replaying only
the current deterministic source/catalog builders over exact stored chunks
reconstructed the Samsung requested total, both Hyundai sales-count surfaces,
and the Motional row's share, carrying-value, and net-result cells as stable
numeric candidates. The prior generic fixture had passed an already collapsed
single-row source candidate directly to the catalog builder; its six
`table_value_labels_text` misses characterize that collapsed input only, not a
failure of full document-to-source projection.

### Characterized gap and repair

Structured row/value records preserve row identity, full column-header lists,
raw value, unit hints, source identity, and stable candidate IDs without
cross-pairing neighboring rows. Full legacy pipe rows also preserve row/value
association, but the fallback previously selected only the last valid physical
header line. In a multi-level table this made opening and closing cells share the
same leaf label. The focused negative reproduced that exact loss before the edit.

`financial_row_surfaces.py` now collects every structurally valid header row and
builds an ordered, adjacent-deduplicated header chain for each value column.
Generic fixtures distinguish opening `25.92` from closing `25.81`, retain the
appropriate carrying-value and latest-result parent headers, reject cross-row
pairing, and verify repeatable candidate IDs. A separate control confirms that
flattened `table_value_labels_text` still cannot create candidates. Another
three-obligation control confirms that relevant sibling cells from one source
survive a bounded prompt projection.

### Saved-successor interpretation and verification

The saved successor's historical Motional prompt already contained all four
leaf-header row candidates for the target row; the model nevertheless proposed
an unrelated `53%` source and invalid expressions for direct obligations. That
is not evidence of catalog omission. With the current repair, reprojecting the
same immutable detailed-table chunk produces distinct opening/closing header
chains and new provenance-derived IDs. By contrast, the reconstructed Samsung
total and both Hyundai sales-count IDs were absent from their saved prompt lists.
Because the saved trace records prompt IDs but not preserved seed-source and full
catalog-source identities, it cannot distinguish source-window absence from
prompt-budget loss after the fact.

Focused semantic-program tests pass 67/67, import/DAG tests pass 19/19, the
runtime-domain audit reviews 86 literals, full discovery passes 650/650,
`py_compile` passes, and `git diff --check` reports no error. The paid
2026-08-30 successor remains the latest integration observation; this no-call
repair does not convert it into a pass. Next work is compact candidate-stage
provenance observability, with compiler selection/retry kept as a separate seam.

## Row-Local Direct Subject Validation (2026-08-30)

### Scope and characterization

This was a provider-free validator/evidence-schema repair. Before runtime edits,
the existing semantic-program suite passed 61/61. Two desired controls were then
added and failed exactly at the characterized boundary: the table-wide subject
case remained `ready`, and the catalog omitted structured `row_headers` from the
same-row positive candidate. No company name, benchmark ID, answer key, provider
output, or benchmark artifact entered the fixture or runtime rule.

The successor fixture is marked `mixed_characterization_and_repaired_contract`;
its SHA-256 is
`c3d69743e879e907948fbf9d9f9ff9c993c42b905c1dc2eb3d3af8f4e168f4ea`.
Expression compatibility, candidate admission, and direct display-unit behavior
remain explicit characterizations in that same fixture.

### Runtime contract

Candidate projection now preserves normalized structured `row_headers`. For a
row-backed numeric direct binding, an explicit candidate segment is authoritative;
otherwise only the candidate-local row label and row headers may establish the
requested segment/subject. A match found only in broad source text cannot make a
different local row eligible and produces `candidate_subject_mismatch`.

When local row identity is absent, the prior compatibility path remains available
only through a same-source narrative candidate that itself matches the requested
subject. It cannot override a nonempty contradictory row. Non-row numeric sources
retain their existing source-local scope behavior. No expression-context,
candidate-admission, display conversion, graph, ledger, evaluator, dataset, or
provider path changed.

### Verification and next boundary

The repaired semantic-program suite passes 64/64; adjacent runtime/projection
tests pass 194/194; the runtime-domain audit reviews 86 literals; full unittest
discovery passes 647/647. These are no-call contract results, not refreshed
benchmark acceptance. The 2026-08-30 paid successor remains the latest integration
evidence and integration remains on HOLD.

The next provider-free seam is candidate-catalog source completeness. First prove
whether each source-visible missing number retains a local row/value/unit/period/
source record. Admit only those immutable associations, add a cross-row negative
control, and repair parser/evidence metadata upstream when only a flattened table
summary survives. Do not guess bindings from `table_value_labels_text`, relax
expression context, change display semantics, resume Phase 3, or run a provider in
that seam.

## Three-Contract Provider-Free Characterization (2026-08-30)

### Scope and fixture provenance

This step made no runtime, provider, benchmark, retrieval-store, ingest,
embedding, evaluator, or ledger change. It added the generic
`tests/fixtures/semantic_program_contract_residuals.json` fixture and three
characterization methods in `tests/test_semantic_calculation_program.py`. The
fixture is marked `known_failure_characterization`; it contains no company name,
benchmark ID, answer key, or provider output. Its SHA-256 is
`5e6388b236dc668138a9c61790e2be6150a5680074364bf366f3fdd79b8661be`.

The pre-change semantic-program suite passed 58/58. With the three new methods it
passes 61/61. These tests intentionally assert the current bad behavior so the
next implementation can flip one boundary at a time without silently changing
the other two.

### Observed contracts

1. Both a same-metric adjacent-report-period subtraction and a same-scope
   statement/note subtraction fail with exactly one error:
   `expression_context_mismatch` whose detail is `context_fingerprint`. Company,
   period requirement, consolidation, segment, basis, numeric type, and unit
   validation do not contribute another error.
2. A source candidate's `table_value_labels_text` visibly contains requested
   share, carrying value, net result, aggregate, current count, and prior count
   values. The immutable bindable catalog nevertheless contains only the selected
   row's `53`; all six requested raw values are absent.
3. A direct obligation scoped to `target venture` accepts an `unrelated region`
   row because `target venture` appears elsewhere in table-wide `source_text`.
   Execution returns the wrong `53%` candidate with status `ok`. Separately, a
   normalized KRW value of `700,000,000` requested in `원` records result unit
   `원` but renders the source display `700백만원`, so requested-unit projection is
   not yet deterministic.

### Decision

The first implementation seam is row-local subject validation because it is the
only characterized residual that turns a contradictory source row into an `ok`
answer; the others fail partial/closed. Numeric direct binding must use local
segment, row label, and structured row headers rather than a match found only in
table-wide source text. Explicit conflicts must remain fail-closed, and any
compatibility bridge must stay evidence-backed and same-source.

Do not combine expression compatibility, sibling/atomic admission, or display-
unit normalization into that first change. Phase 3 owner moves and every provider
replay remain on HOLD.

## Generic-Contract Successor Five-Question Gate (2026-08-30)

### Authority and immutable inputs

The user authorized exactly one store-fixed successor over `NAV_T2_006`,
`HYU_T2_010`, `HYU_T3_072`, `LGE_T1_051`, and `SAM_T2_078`, with no automatic
full-run retry. The production-order manifest receipt was
`c48b007fdeeb457fe3fdb977a044b1816d4043c3857de65acba4af9df55640e3` and
bound runtime build
`e4daebab644cf978f21942f73fac49f03788b03c1abe6638ce9e406e1ad5e794`.
It enumerated Google query embeddings, agent/evaluator LLMs, and the OpenAI
answer-relevancy embedding path. Fresh ingest, document embeddings, KB rows,
other question IDs, and another provider run were outside authority.

The immutable source was
`benchmarks/results/policy_gate_regression_2026-06-03_1138_actual`; the ignored
local successor is
`benchmarks/results/integration_policy_gate_semantic_program_generic_contract_successor_2026-08-29`.
The source stores were opened only through verified disposable copies. Their
fingerprints remained unchanged and no disposable `dart_eval_store_*` directory
remained:

- NAVER: `7402849806936522e288cdeeac52a76a3d9504595345cbb836a0dd6faa33b24a`;
- Hyundai: `ebdbe7021f3eb34ad75007ee1736033f3428d50745921558fbae85498ba2ae81`;
- LGE: `d3d84f667f1a9ecc6675c17a9e17c001eaf022c8c14cd2a322db8c2bd13ba715`;
- Samsung: `862a01380754fd64e2395ecf506f9e4daa6ed404385b623b862623c425ddba3e`.

### Paid observation

The monitored run completed normally in `508.3s`: four companies and five
questions finished, runtime error rate was zero, all five task/artifact ledgers
had integrity `ok`, and document-embedding calls stayed zero. It used 31 LLM
calls, 927,550 tokens, 55 query-embedding calls, and an estimated `$0.4644884`,
below the authorized `$0.60` ceiling. The estimate excludes embedding pricing
because that profile has no embedding-price field; it is a runner estimate, not
an invoice. The top-level result SHA-256 is
`e5a13e15a25ac295157ff469b53cd0bf055050edf6060ee89910d31351c9269c`.

The gate failed. Every semantic result was `partial`, all four company full
evaluations failed, and screening pass count four remained only a reused-bundle
admission signal. Company-average faithfulness, completeness, numeric pass rate,
and context recall were `0.800`, `0.3875`, `0.0`, and `0.953125`. The five-row
weighted faithfulness/completeness means were `0.740 / 0.360`; LGE was the only
numeric-applicable row and its numeric judgement was FAIL.

| Row | Result | Observed boundary |
| --- | --- | --- |
| `NAV_T2_006` | 1/2, partial | The compiler selected correct `2,546,649 / 1,801,079백만원` inputs and source display `41.4%`. A relative prior-period candidate first failed period scope; retry selected the explicit 2022-report candidate but exact `context_fingerprint` equality rejected the otherwise compatible adjacent-period expression |
| `HYU_T2_010` | 1/2, partial | The new unknown-only narrative scope declaration validated and preserved the policy explanation. The source-visible `87.0만 대 / 78.1만 대` inputs were still absent from the compiler candidate prompt, so numeric growth remained missing |
| `HYU_T3_072` | 1/3, partial | A `중국` row's `53%` was accepted as Motional because empty subject/segment metadata made direct binding fail open. Motional carrying-value/loss candidates were visible, but LLM-authored `* 1000000` expressions conflicted with planner-declared `direct_value`; structured sibling cells were not all separately bindable |
| `LGE_T1_051` | 1/2, partial | Retry selected the correct consolidated `2,163,234백만원` operating profit, `676,874백만원` AMPC amount, and subtraction. Exact context equality rejected the expression solely because statement and connected-note operands had different fingerprints |
| `SAM_T2_078` | 1/2, partial | Harman narrative remained grounded, but the canonical `28,352,769백만원` aggregate did not enter the runtime catalog/program prompt. Its appearance in benchmark answer/evidence fields is not runtime retrieval evidence |

Per-company result SHA-256 values are LGE
`ef449cf49ed33e99fc6ad8d40a855e0acba147a5dafb9a58724346741810e476`, NAVER
`c8e5ef8e64a4196176f9a05b3d7aceaf0b73b874fd064f3fadee4c2add71de25`, Samsung
`e3415117998e0de91ddc13eaa936d6c2a9c1c7dc0d389e40dc3d9058ae5e1475`, and
Hyundai `7b93859fad68d7e510d6f60db7c7a8683ef8f1ee41b9b76a46bbcbba369f3352`.

### Interpretation and stop line

The earlier four repairs showed real effect: narrative scope applicability now
works on NAV/HYU evidence, LGE retry supplied exact registered bindings, and the
old empty direct rendering no longer passed. The successor nevertheless exposes
three deeper generic contracts:

1. expression coherence needs validated semantic compatibility for adjacent
   periods and explicitly related statement/note operands, rather than exact
   table/report fingerprint identity;
2. obligation-owned numeric admission and structured-row sibling expansion must
   expose source-visible counts, aggregates, and requested cells as bindable IDs;
3. direct binding must validate subject/row identity fail-closed and perform unit
   conversion as deterministic display normalization, not as a derived formula.

No company/question branch, benchmark answer import, automatic replay, or Phase
3 owner move is authorized. The successor is the latest integration evidence;
the next work is provider-free characterization of these three contracts.

## Semantic-Program Current-Head Five-Question Gate (2026-08-29)

### Authority and immutable inputs

The user authorized exactly one current-head store-fixed gate over
`NAV_T2_006`, `HYU_T2_010`, `HYU_T3_072`, `LGE_T1_051`, and `SAM_T2_078`.
Additional rows, fresh ingest, runtime refactoring, and follow-up provider replays
were outside this authority. An initial provider-free path check found that the
manifest's underscore experiment ID maps to hyphenated physical store directory
names; no provider was called. After correcting only that path projection, two
production-order rehearsals were byte-identical at receipt
`c714bdc02c891aa802eb801b57e2056a6060412cea03031ab846e3f02a2ad08e`.

The receipt bound runtime build
`a739e6569585747f93d0412922b32f633415117a4781ba40481a0651a439181a`,
profile SHA-256
`f0d5d625d1b0a898e8ff59d66e7020bdac500bbce450964924532be6edbd0fb4`,
dataset SHA-256
`19bb121507275a7c15406dddbda22b392bb870d6bf0fdb9a400d599de8eb1aba`,
and source top-level SHA-256
`f8f641f47d3b7dbc3e88bb455c15e7930fbecec1f22e7cfd4f4c3abf9ef72c9d`.
The source was
`benchmarks/results/policy_gate_regression_2026-06-03_1138_actual`; the ignored
successor is
`benchmarks/results/integration_policy_gate_semantic_program_current_head_2026-08-29`.

All four source-store logical fingerprints were unchanged after execution:

- NAVER: `7402849806936522e288cdeeac52a76a3d9504595345cbb836a0dd6faa33b24a`;
- Hyundai: `ebdbe7021f3eb34ad75007ee1736033f3428d50745921558fbae85498ba2ae81`;
- LGE: `d3d84f667f1a9ecc6675c17a9e17c001eaf022c8c14cd2a322db8c2bd13ba715`;
- Samsung: `862a01380754fd64e2395ecf506f9e4daa6ed404385b623b862623c425ddba3e`.

### Paid observation

The monitored eval-only run completed normally in `520.3s`: four of four
companies and five of five questions finished, no runtime error occurred, every
task/artifact ledger had integrity `ok`, and document-embedding calls remained
zero. It used 31 agent/judge LLM calls and 939,313 tokens, 55 query-embedding
calls, 409.260 question-seconds, and an estimated `$0.4732093`. The top-level
result SHA-256 is
`10ac822e97e990265a12abd2d239741df5b4a659d6f8f031f65fe07ed263b89e`.

This was not an integration pass. All four screening rows passed, but screening
only confirmed reusable bundle admission. Every question's semantic result was
partial or incomplete, so all four company full evaluations failed. Company-
average faithfulness, completeness, numeric pass rate, and context recall were
respectively `0.875`, `0.375`, `0.0`, and `0.94375`. LGE was the only row to
which the numeric final judgement applied, and it failed.

| Row | Program result | Observed boundary |
| --- | --- | --- |
| `NAV_T2_006` | 1/2, partial | Same-row `2,546.6 / 1,801.1억원` and source display `41.4%` executed correctly. The Poshmark narrative was omitted after strict segment validation rejected semantically relevant evidence whose segment metadata was absent |
| `HYU_T2_010` | 0/2, incomplete | US-sales counts were visible in source text but not exposed as atomic numeric values; the policy narrative had `consolidation_scope=unknown` against an over-specified consolidated obligation |
| `HYU_T3_072` | 1/4, partial | Detail-table stake/carrying-value candidates were rejected because their consolidation metadata was unknown and revenue was absent. The sole accepted direct value had unit `UNKNOWN` and rendered empty despite `status=ok`, exposing a validator/render fail-open defect |
| `LGE_T1_051` | 1/2, partial | The precise `676,874백만원` AMPC candidate was in the 128-ID prompt, but the compiler chose rounded prose and repeated an undeclared formula variable plus missing requirement bindings on retry; validation correctly rejected the derived output |
| `SAM_T2_078` | 1/2, partial | The previously accepted exact `28,352,769백만원` candidate was absent from this 128-ID prompt. Rounded prose was proposed instead and rejected by numeric/context/scope validation; the Harman narrative survived |

The result files for LGE, NAVER, Samsung, and Hyundai have SHA-256 values
`75c4b5efe887f08d69b5bcbb9264932ec9ba45952b9f0d5b70e02ff90c855081`,
`14526a51f66fb5a1d63cac9697b2dfce7efe3ecd475bd5441b6bfc213db5dc07`,
`5abf85322db5e46a39e555bdcddcc4b2525e405a282723ecbccfc24cac7b05c7`,
and `b5bf2192cb468b2e879d23459cc3c93ddcdcb43bc73957270ae7f60d69f9ce62`.

### Admission residual and decision

The rehearsal operation list authorized the five question executions and their
evaluators, but its provider enumeration named the Google source/query embedding
and LLM paths only. Runtime evaluator metrics also made two OpenAI query-
embedding calls per question. Credentials and evaluator operations were in the
approved execution scope, so this is not an additional benchmark or ingest, but
the provider manifest was incomplete and this run must not be described as
perfect admission evidence.

The gate establishes four general no-call work items rather than five row-specific
patches: evidence-surface scope applicability, source-visible atomic numeric and
obligation-stratified prompt coverage, compiler retry formula/evidence binding,
and fail-closed nonempty/unit-compatible direct rendering. Integration and Phase
3 refactoring remain on HOLD. No follow-up provider call is authorized; raw
results, stores, caches, and heartbeat logs remain ignored local artifacts.

## Semantic-Program Four-Contract No-Call Successor (2026-08-29)

### Characterization

The pre-change semantic-program suite passed its existing 54 tests. Four new
generic methods plus structured-schema and retry-prompt assertions then reproduced
six expected failures/errors without using any company name or benchmark ID as a
runtime rule:

- narrative evidence with unknown soft scope could not declare semantic
  applicability, while explicit mismatch still needed rejection;
- explicit `만 대` count values disappeared when a chunk also carried table
  structure, and a relevant alternate aggregate row from an already represented
  source lost the prompt budget to source diversity;
- retry feedback did not close over target-owned requirement IDs or the exact
  formula-variable/binding invariant;
- a finite `UNKNOWN`-unit direct candidate could validate and emit `status=ok`
  with an empty display.

### Generic repair

- Narrative bindings may declare `scope_applicability_fields` only for
  `consolidation_scope`, `segment`, and `basis`. The validator bridges an
  `unknown` state only; explicit conflicts, company, and period remain hard
  failures, including evidence-requirement scope checks.
- The source-number extractor consumes the declarative Korean count-unit policy,
  normalizes scaled count displays, and retains explicit-inline-unit values even
  when structured material is attached. Same-source structured duplicates are
  removed by normalized value/unit, while distinct sentence values remain
  immutable candidates.
- Prompt relevance treats `aggregate_label` as a semantic label and reserves one
  quarter of a sufficiently large obligation group for ranked alternate rows
  after source-diversity coverage. This changes model visibility, not answer
  selection.
- Targeted retry feedback now carries requirement IDs and validation errors by
  obligation plus exact formula-variable and evidence-binding invariants. Valid
  first-attempt outputs remain immutable and the validator still rejects invented
  IDs.
- Direct validation rejects requested-unit/dimension mismatch and empty grounded
  rendering before an output can become `ok`.

### Validation and authority

- semantic-program characterization/regression: 58 / 58;
- adjacent math, numeric-provenance, answer-slot, evaluator-calculation, and
  evaluator-runtime tests: 131 / 131;
- `python -m src.ops.audit_runtime_domain_terms`: passed, 86 reviewed literals;
- import-side-effects plus canonical graph/DAG: 20 / 20;
- full unittest discovery: 641 / 641 in 16.608 seconds;
- affected-file pycompile, legacy calculation-planner symbols zero in `src`, and
  `git diff --check`: passed.

This successor made no provider, benchmark, report-fetch, ingest, query-embedding,
document-embedding, or LLM call. It closes the four blockers only at the no-call
contract level. The failed five-question run remains the latest integration
evidence; any focused store-fixed successor requires a new exact manifest, cost
ceiling, two byte-identical rehearsals, and separate user approval.

## Corrected-Evaluator T2 Focused Acceptance (2026-08-29)

### Authority and immutable inputs

The user authorized exactly one corrected-evaluator store-fixed replay for
`KBF_T2_018`; the five-question gate remained outside authority. Two
production-order no-call rehearsals were byte-identical at receipt
`b8f05c7848ed8d1cc9efd8595ab57ff439f2cb96db2e895086cd4c9ffe302905`.
They bound runtime build
`e3888c98754782f1cb49b4d1be438528c6dffaab05bbfd9e952e196cef18f27f`,
the single question/company run, and the completed 2,093-embedding source store.
The ignored local successor is
`benchmarks/results/kbf_t2_018_corrected_evaluator_acceptance_2026-08-29`.
Its top-level and company-result SHA-256 values are respectively
`9ee18cce8103b5b371628e68591fd2fb91527652ddaad4e075fb74399a93fe0c` and
`3ba6e71e8b013bd5cac2ee3b4f971c8956540ad6814ad469daa8d451850265c0`.

The run made zero document-embedding calls. The complete source-store
fingerprint before and after remained
`484899d27e2b5469c79b1865d287945e634566af7c805898d37714e589404dd4`.

### Paid observation and acceptance

The compiler saw 3,741 catalog candidates, selected three without retry, and
the executor completed both required obligations. The numeric expression bound
the same connected income-statement row `20240326000894:470:1`:

- 2023: `(3,146,409)백만원`;
- 2022: `(1,847,775)백만원`;
- formula: `((abs(v_2023) - abs(v_2022)) / abs(v_2022)) * 100`;
- result: `70.2809595324106%`, rendered `70.28%`.

The narrative obligation bound the selected note evidence directly describing
the uncertain financial environment, potential credit risk under sharp
downturn, and worse/crisis scenarios used in expected-credit-loss measurement.
The final answer therefore preserved both the deterministic calculation and a
source-backed risk-management explanation.

The corrected evaluator recorded `raw_faithfulness=1.000` and final
faithfulness `1.000`, with `faithfulness_override_reason=null`. Raw and final
numeric judgement were both `PASS`; numeric grounding, equivalence,
calculation correctness, grounded rendering, and completeness were all `1.000`.
The task/artifact ledger contained one task and four artifacts with integrity
`ok`, no issue, and no runtime error. This closes the focused mixed-answer
acceptance that the preceding evaluator repair left on HOLD.

Agent usage was three calls / 92,916 tokens and judge usage was three calls /
9,661 tokens. Total usage was six calls / 102,577 tokens; query embeddings were
11, document embeddings were 0, question latency was `62.938s`, and the runner's
estimated runtime cost was `$0.0605193`. Answer relevancy `0.589` and context
recall `0.667` remain diagnostic metrics rather than being promoted by the
numeric result; aggregate error rate was `0.0%`.

### Decision

No additional runtime or evaluator repair is justified by this focused row.
The next executable benchmark is the current-head five-question store-fixed
gate, but it requires separate cost authorization and was not run here. Raw
results, stores, caches, and heartbeat logs remain ignored local artifacts.

## T2 Narrative Replay And Evaluator Role Separation (2026-08-29)

### Authority and immutable inputs

The user authorized exactly one more store-fixed `KBF_T2_018` replay; the
five-question gate remained outside authority. Two production-order no-call
receipts were byte-identical at
`3b10ce5c6537df882fef87de2eb2205051bf662cebf265679af52f930301ebb6`.
They bound runtime build
`a5dc21fd19f9c9f1e6c3791e8e6fe0675e4b231cbe0d6e9d248ff669889b629f`,
one question, one company run, the 2,093-embedding saved store, and the new
ignored target
`benchmarks/results/kbf_t2_018_narrative_relation_acceptance_2026-08-29`.

The run made zero document-embedding calls. The complete source-store
fingerprint before and after remained
`484899d27e2b5469c79b1865d287945e634566af7c805898d37714e589404dd4`.

### Paid observation

The compiler saw 4,305 catalog candidates, selected five without retry, and the
executor completed 2/2 obligations. It reused the connected income-statement row
`20240326000894:470:1`, calculated `(abs(3,146,409) - abs(1,847,775)) /
abs(1,847,775) * 100`, and rendered `70.28%`. The narrative selected three
requirement-bound note candidates covering the worse/crisis scenarios, Expected
Loss and Economic Capital, Total Exposure limits, and forward-looking
macroeconomic methodology. The resulting answer received numeric PASS,
calculation/grounded rendering `1.000`, qualitative completeness `1.000`, ledger
integrity `ok`, and no error.

Agent usage was three calls / 92,720 tokens and judge usage was three calls /
11,528 tokens. Total usage was six calls / 104,248 tokens; query embeddings were
11 and document embeddings 0. Estimated runtime cost recorded by the runner was
`$0.0603562`.

### Evaluator residual and generic no-call successor

The stored final `faithfulness=1.000` is not canonical acceptance evidence. Its
raw LLM faithfulness was `0.500`, after which numeric PASS promoted the entire
mixed answer to `1.000`. This violated the intended role boundary: numeric
correctness may validate the arithmetic claim, but cannot certify narrative
semantics.

The raw judge also received an incomplete evidence view. Final runtime evidence
was prioritized, but identical `claim` and `quote_span` payloads plus indexed
metadata were duplicated before the global 4,000-character prompt limit. Only
the numeric row and part of the scenario evidence fit; the selected
risk-management and forward-looking-method contexts were truncated.

Characterization tests fixed both failures before implementation. The generic
evaluator successor now:

- removes only colon-bearing indexed metadata brackets while preserving
  source-visible headings;
- deduplicates equivalent claim/quote/context payloads per evidence item;
- exposes all four distinct selected contexts from this artifact in 3,008
  characters instead of truncating the last two;
- refuses numeric faithfulness promotion and numeric-fast gating for mixed
  runtime format or whenever the calculation result contains a narrative
  output, including the fail-closed case where a required narrative output is
  missing.

No benchmark or provider call followed this evaluator repair. Evaluator,
calculation-variant, and runner focused tests pass 118/118; full unittest passes
637/637; runtime-domain audit 86 and `git diff --check` pass. Integration
therefore remains HOLD pending a separately authorized corrected-evaluator
T2-only acceptance replay. The five-question gate remains separately authorized
work after that acceptance.

## T2 Numeric Acceptance And Narrative-Relation Successor (2026-08-29)

### Authority and immutable inputs

The user authorized one more store-fixed `KBF_T2_018` replay after the generic
prompt-readiness repair. The five-question gate remained outside authority. Two
production-order no-call rehearsals were byte-identical at receipt
`e172d03e065ba0ae641c08cbb563e2a3a681d35acb8aa220e4f99f5a0b8084e0`.
They bound only the requested row, current runtime/profile/dataset hashes, the
2,093-embedding source store, and target output directory. The ignored local
artifact is
`benchmarks/results/kbf_t2_018_prompt_readiness_acceptance_2026-08-29`.

The run made zero document-embedding calls. The complete source-store
fingerprint before and after execution remained
`484899d27e2b5469c79b1865d287945e634566af7c805898d37714e589404dd4`.

### Paid observation and acceptance split

The compiler saw 4,196 catalog candidates, selected five without a retry, and
the deterministic executor completed both required obligations with no missing
IDs. The numeric expression bound the same connected income-statement row:

- 2023 `cand_e1d8aa527b06dfafde43`: `(3,146,409)백만원`;
- 2022 `cand_ac08297806e6475c8ecd`: `(1,847,775)백만원`;
- formula: `(abs(V_2023) - abs(V_2022)) / abs(V_2022) * 100`;
- result: `70.2809595324106%`, rendered `70.28%`.

The numeric source/program is canonical. Numeric judgement was `PASS` at
confidence `0.9875`; calculation correctness and grounded rendering were
`1.000`; the task/artifact ledger was one task, four artifacts, integrity `ok`.
Agent usage was three calls / 92,720 tokens, judge usage three calls / 12,901
tokens, query embeddings 11, and document embeddings 0.

The mixed answer as a whole was rejected. Its narrative binding asserted that
loan and investment-asset growth caused the provision increase, but the selected
MDA paragraph stated only those asset changes. Qualitative completeness was
`0.700`, and the evaluator's raw grounding response independently identified
that causal leap. The deterministic numeric-grounding override then kept the
calculation assessment grounded from the direct operands. This is the intended
separation between calculation correctness and narrative semantics; numeric
PASS does not convert the qualitative output into canonical acceptance.

### Generic no-call successor

The residual was classified as a narrative relation-grounding contract, not a
company, metric, or benchmark exception:

- the requirement planner now declares factual narrative relations, especially
  causal explanations, as stable `evidence_requirements`;
- task required-evidence projection and targeted retrieval preserve those
  requirement surfaces rather than falling back to the broader obligation hint;
- `SemanticProgramNarrativeBinding.evidence_bindings` explicitly maps every
  selected candidate ID to its owned `source_requirement_id`;
- validation rejects missing required mappings, unknown requirements,
  cross-obligation ownership, unselected candidates, and incompatible scope;
- the compiler contract forbids treating co-occurrence, another metric's change,
  general background, or a risk-management procedure as a direct cause without
  evidence that connects the target change to that factor.

Characterization first demonstrated that the old targeted supplement selected
general context instead of the declared relation and that narrative requirements
were not enforceable. The successor reverses both outcomes without adding a
domain term or benchmark branch.

Validation on the final no-call source tree:

- semantic-program, retrieval, and runner focused tests: 118/118;
- `python -m src.ops.audit_runtime_domain_terms`: 86 reviewed literals, passed;
- `python -m unittest discover -s tests`: 635/635;
- source-store fingerprint unchanged at
  `484899d27e2b5469c79b1865d287945e634566af7c805898d37714e589404dd4`.

No provider call followed this narrative-relation repair. Integration therefore
remains HOLD pending a separately authorized T2-only full mixed-answer acceptance
replay. The five-question gate remains a separate later authorization.

## T2-Only Prompt-Readiness Replay And Generic Evidence Successor (2026-08-29)

### Authority and artifact boundary

The user authorized only one store-fixed `KBF_T2_018` replay. Two production-
order no-call rehearsals were byte-identical at receipt
`4c062416c1c8ed12a0004be688e156632b7e2b61081c4ce872e246a93bef8c5c`.
The run reused the existing 2,093-document store, performed zero document
embeddings, and preserved the full source-directory fingerprint
`484899d27e2b5469c79b1865d287945e634566af7c805898d37714e589404dd4`.
The five-question gate was neither authorized nor executed. The local result is
`benchmarks/results/kbf_t2_018_obligation_owned_replay_2026-08-29` and remains an
ignored experiment artifact.

### Paid observation

The retrieval repair reached the requested connected income-statement chunk:
`20240326000894:470:1` was final selected rank 6. The compiler nevertheless saw
4,447 catalog candidates and 128 prompt candidates without either canonical
numeric cell. It retried once, selected zero candidate IDs, produced zero
outputs, and left both required obligations missing. The final refusal had
numeric judgement `UNCERTAIN`, faithfulness `1.000`, completeness `0.000`,
refusal accuracy `1.000`, and no runtime error.

Agent usage was four calls / 182,857 tokens; judge usage was three calls / 7,541
tokens. Query embeddings were nine calls / nine texts and document embeddings
were zero. These are observed artifact facts, not estimates of the repaired
path.

### Generic diagnosis and no-call successor

The failure was candidate readiness after retrieval, not arithmetic and not a
need for a KB-specific branch:

- parser metadata kept a true multi-line period header followed by a first-row
  preview, but line normalization flattened both and treated preview values as
  column periods;
- candidate admission compared normalized outer whitespace but not spacing-only
  label variants, so an exact semantic row could lose to prompt-budget noise;
- numeric and narrative obligations shared prompt relevance groups, and the
  targeted supplemental seed path represented only numeric requirements.

The successor preserves header lines, ignores structurally numeric data-preview
lines when choosing column headers, and keeps period metadata available for
`value_year` recovery. Prompt ranking now treats whitespace-only label variants
as equivalent and uses candidate-kind-owned obligation groups. Required evidence
supplementation covers both numeric and narrative obligations: numeric inputs
retain the best compatible table source, while narrative obligations retain a
policy-bounded set of compatible explanatory paragraphs so the compiler, not a
lexical one-best rule, makes the semantic choice. Period-only hints remain scope
signals and do not consume narrative semantic diversity.

### Provider-free acceptance probe and validation

A read-only probe loaded only the saved structure graph; it did not open Chroma,
run retrieval embeddings, or invoke an LLM. The resulting prompt contained:

- `cand_e1d8aa527b06dfafde43`: `(3,146,409)`, `value_year = 2023`;
- `cand_ac08297806e6475c8ecd`: `(1,847,775)`, `value_year = 2022`;
- `cand_eca9ff59eee4097a3e74`: the cause paragraph from
  `20240326000894:493:16`.

A fixed structured program referencing only those exposed IDs validated
`ready`, executed `ok`, completed both obligations, calculated
`70.2809595324106%`, and rendered `70.28%` with post-execution family
`growth_rate`.

Validation on the final source tree:

- semantic-program, retrieval, and runner focused tests: 115/115;
- `python -m src.ops.audit_runtime_domain_terms`: 86 reviewed literals, passed;
- `python -m unittest discover -s tests`: 632/632;
- source-store fingerprint after all probes:
  `484899d27e2b5469c79b1865d287945e634566af7c805898d37714e589404dd4`.

No provider call followed the repair, so this is not T2 canonical acceptance.
Integration remains HOLD. Another T2-only paid replay requires fresh approval;
the five-question gate remains a separate later authorization.

## Approved Residual Replay And Obligation-Owned Retrieval Successor (2026-08-28)

### Authority and artifact boundary

The user separately authorized only the store-fixed sequence `KBF_T2_018`
followed by `KBF_T1_017`. The five-question gate was neither authorized nor
executed. The first `uv run` launch failed before provider construction because
the local `.venv` Python executable was unavailable; the approved rows were then
run sequentially through the configured Python runtime with 30-second heartbeat
logs. Benchmark bundles, stores, caches, and logs remain ignored local artifacts.

Both runs reused the existing 2,093-document store and performed zero document
embeddings. The full source-directory fingerprint was
`484899d27e2b5469c79b1865d287945e634566af7c805898d37714e589404dd4`
before the pair and remained byte-identical after each eval-only run, validating
the disposable-copy store contract in a live execution.

### Paid focused observations

- `KBF_T2_018` used 87 retrieval candidates and eight final note chunks. The
  semantic compiler had 3,918 catalog candidates, exposed 128, retried once,
  selected none, and failed closed with both obligations missing. Numeric
  judgement was FAIL; faithfulness was `1.000`, completeness `0.000`, context
  recall `0.333`, and answer relevancy `0.497`. Aggregate usage was 192,265 LLM
  tokens, 453 estimated query-embedding tokens, zero document embeddings, and a
  local runtime-cost estimate of `$0.1033141`. The local result is
  `benchmarks/results/kbf_t2_018_residual_contract_replay_2026-08-28`.
- `KBF_T1_017` compiled on its first response from 1,650 catalog / 128 prompt
  candidates. It bound `cand_fa953151cf02e5921f0b` (`1.83%`, 2023) and
  `cand_4de1f1e0c09dfb8d30d1` (`1.73%`, 2022) from the same row, table, source,
  and consolidated scope to `ob_002:req_001` and `ob_002:req_002`. The validated
  expression `nim_2023 - nim_2022` returned `0.10%p`, two outputs, and no missing
  obligation. Numeric judgement was PASS with faithfulness `1.000`, completeness
  `0.700`, context recall `1.000`, and answer relevancy `0.714`. Aggregate usage
  was 92,896 LLM tokens, 252 estimated query-embedding tokens, zero document
  embeddings, and a local runtime-cost estimate of `$0.0445822`. The local result
  is `benchmarks/results/kbf_t1_017_residual_contract_replay_2026-08-28`.

T1 is accepted as a canonical source/program calculation. Its qualitative
completeness residual is the absence of an explicit increase/decrease direction
word in the rendered sentence; it is separate from arithmetic, binding, and
provenance. T2 is rejected. It is not an arithmetic error: the requested
connected income-statement row `20240326000894:470:1` and its canonical candidate
IDs never entered the catalog or compiler prompt.

### General diagnosis and no-call successor

The previous per-query contract separated executions but did not separate
semantic ownership. Numeric base queries still inherited narrative obligation
risk terms and note-section priors from the mixed task, so distinct searches
converged on the same wrong evidence surface. This is a cross-obligation policy
leak, not a need for a company, metric, or benchmark branch.

The successor resolves every base query only against planner-declared obligation
and evidence-requirement labels/hints. Numeric-owned queries exclude narrative-
only enrichment; narrative-owned queries retain it, and the trace records the
resolved owners. Required numeric evidence is additionally preserved through a
targeted structural supplement: a document must match a declared input surface,
not merely a preferred section; matching scans the full chunk and tolerates only
spacing-equivalent sufficiently long labels; ordered statement types and tables
precede weaker compatible contexts; and the best document for every required
group is retained in `seed_retrieved_docs` even when the visible rerank window is
full. The mechanism does not select a calculation value or synthesize evidence.

A provider-free probe against the saved store and saved T2 obligations now
selects `20240326000894:470:1` as the first supplemental source, ahead of summary
financials and explanatory note paragraphs. This proves candidate preservation,
not end-to-end provider acceptance.

### Validation and next gate

- semantic-program, retrieval, and runner focused tests: 109/109;
- `python -m src.ops.audit_runtime_domain_terms`: 86 reviewed literals, passed;
- `python -m unittest discover -s tests`: 626/626;
- legacy planning symbols have zero production references;
- canonical graph/DAG tests and `git diff --check`: passed.

No provider call was made after this repair. Integration remains HOLD. The next
paid step requires fresh authorization for `KBF_T2_018` only. The five-question
store-fixed gate remains a separate later decision and requires separate cost
authorization even if T2 is canonically accepted.

## KB Residual Contracts No-Call Successor (2026-08-27)

### Authority and evidence boundary

This checkpoint implemented and tested the three generic residual contracts
exposed by the rejected fresh KB pair. It made no provider, benchmark, report
fetch, ingest, query-embedding, or LLM call. Therefore it does not revise the
stored T2 0/2 or T1 1/2 canonical decisions and is not a new quality score.

### Generic contract changes

- Hard source constraints remain shared, but retrieval now derives and budgets
  semantic hints and preferred sections separately for every base query. The
  test requires query-local enrichment; it does not require different documents
  when the same evidence legitimately answers multiple searches.
- A derived answer obligation now declares non-rendered
  `evidence_requirements`. Candidate-bound variables carry the owned requirement
  ID and are checked against that input's period/scope. Previous output
  obligations remain valid expression dependencies without a requirement ID.
  Missing, invented, duplicate, cross-owner, incomplete, or scope-conflicting
  bindings fail closed. Retry feedback enumerates the exact allowed candidate,
  obligation, and requirement IDs.
- Eval-only no longer opens the source Chroma directory. It fingerprints every
  source-store path and byte, creates and verifies a disposable copy, evaluates
  only that copy, closes the Chroma client, verifies the source fingerprint
  again, and deletes the working copy. The prior logical fingerprint remains
  provenance evidence but is not used to excuse source-byte mutation.

### Validation and next gate

- Focused semantic-program, retrieval, and runner tests: 101/101.
- `python -m src.ops.audit_runtime_domain_terms`: passed with 86 reviewed
  literals.
- `python -m unittest discover -s tests`: 618/618.

The next paid step requires fresh authorization and is limited to
`KBF_T2_018` followed by `KBF_T1_017`. A five-question gate remains outside this
checkpoint and should run only after both focused rows are canonically accepted
and the broader cost is separately approved.

## Fresh KB Store And Focused Canonical Successor (2026-08-27)

### Authority and production-order gates

The user separately approved one isolated KB store rebuild followed by focused
replay of `KBF_T2_018` and `KBF_T1_017`. This did not authorize the broader
five-question gate. All stores, caches, results, and heartbeat logs remain ignored
local artifacts.

Two provider-free store-only rehearsals produced the same manifest SHA-256
`50260722b3c567e56404053fc9f93e1df22a67fd51d33c94bd592bac10b7b600`.
Before the pair, two production-order no-call rehearsals produced the same receipt
`4615185a56da5060df7b1ed6c7f98e025556cb134287b201a7d82c099a2fdb97`.
They bound the exact profile, dataset rows in T2-then-T1 order, single report
receipt `20240326000894`, parser signature
`9299547c8f4e554830bdc52b350cff4793eb66d3ed7606b1985bed73c55c6aae`,
and the existing store snapshot before allowing query embeddings, requirement/
program LLM calls, answer generation, or focused evaluators.

### Isolated store-only build

The ignored successor directory is
`benchmarks/results/kbf_2023_canonical_store_only_exact_cache_unit_successor_2026-08-27`.
The monitored build completed in about 100 seconds:

- 51 section parents and 2,093 chunks/embeddings;
- 33 document-embedding calls, 2,093 texts, 2,678,118 input characters, and
  670,334 locally estimated tokens;
- zero semantic/context LLM calls and zero query embeddings during store-only;
- one `KB금융 / 2023 / 20240326000894` report scope, OpenAI
  `text-embedding-3-large`, dimension 3,072, cache status `completed`;
- result SHA-256
  `12ba73947c50ad35489015021217d442a03bdfbb3eacdf14fb8bc0d7c612b20a`.

The rebuilt MDA row `20240326000894:1616:1` now carries `unit_hint = 십억원`.
The requested consolidated income-statement row `20240326000894:470:1` remains
`unit_hint = 백만원` with raw values `(3,146,409)` and `(1,847,775)`. This closes
the longest-first parser defect at the persisted-store boundary. Store-only ran no
questions or evaluators.

### Focused results

Both focused runs reused the 2,093-document store, performed zero document
embeddings, and wrote 30-second heartbeat logs.

| Row | Runtime result | Provider usage | Canonical decision |
| --- | --- | --- | --- |
| `KBF_T2_018` | about 98.5 seconds total; question latency `75.394s`; 4,431 catalog / 128 prompt candidates; one retry; 0/2 semantic obligations; task/artifact `1 / 4`, integrity `ok`; result SHA-256 `a1e6fb5cd0392aaf1068ebe630765fb631dddd8d888ce50ede3bac2282a69926` | 7 LLM calls / 186,319 tokens; 11 query-embedding calls / 464 estimated tokens; local runtime estimate `$0.0943649` | evaluator `UNCERTAIN`, faithfulness `1.0`, completeness `0.0`; reject |
| `KBF_T1_017` | about 86.25 seconds total; question latency `63.451s`; 2,759 catalog / 128 prompt candidates; one retry; 1/2 semantic obligations; task/artifact `1 / 4`, integrity `ok`; result SHA-256 `76aabe8fec1de4407d7d776e6b59c31801d1023c4c8290bdfeb08b96cb943ff8` | 7 LLM calls / 179,035 tokens; 11 query-embedding calls / 274 estimated tokens; local runtime estimate `$0.0830255` | numeric PASS but semantic partial; reject |

These cost figures are profile-based local estimates, not provider invoices.

### Canonical audit

For T2, all eight semantically distinct planned queries executed independently;
there were zero exact-cache objective hits. The previous broad cache-collapse
defect is therefore closed. The runtime nevertheless appended the same long
global risk-term and preferred-section suffix to every base query. All eight final
documents came from connected-statement notes, and the exact statement candidates
`cand_e1d8aa527b06dfafde43` (`(3,146,409)백만원`) and
`cand_ac08297806e6475c8ecd` (`(1,847,775)백만원`) never entered the compiler
prompt. The compiler selected no candidates on either attempt and failed closed.
This is query-enrichment/evidence-coverage failure before arithmetic.

For T1, the prompt contained the correct same-row candidates
`cand_fa953151cf02e5921f0b` (`1.83%`) and
`cand_4de1f1e0c09dfb8d30d1` (`1.73%`). Attempt one proposed both but failed the
period-scope validator for the derived obligation. Retry emitted `X - Y` while
binding `Y` to undeclared `ob_003` rather than the available candidate ID. The
validator correctly rejected the unknown source, leaving only the direct `1.83%`
output. Numeric-evaluator PASS does not make the missing required difference
canonical.

### Store immutability observation and decision

Opening the Chroma store for eval-only changed the raw SQLite SHA after T2 and
again after T1. The pre-eval hash was
`10f1fe0858efb617ecf6a1226d50583d981d61891954fc6f299cc25c93570fb2`;
the observed sequence ended at
`41c8fe989534f0476fb935ab1a9fa62be5e36aaaabcc380dd9d488eff79aec46`.
Embedding count, latest embedding timestamp,
metadata content, and the logical embedding/metadata fingerprint
`9396c8d30e13e76c9eddc30362acb6197544242525cac376e5f7e7716bc54a76`
remained stable. A T1-only production-order rehearsal was therefore repeated twice
against the post-T2 bytes and yielded identical receipt
`09b11b482266a06a133b721073002d471fadae036a733ccb92bad6508982c21b`
before the second provider run.

The fresh store validates the cache and parser repairs, but the focused canonical
gate is rejected on two later, generic seams. Next work is provider-free
characterization of query-local enrichment diversity, compiler retry binding that
forbids undeclared obligation IDs, and eval-only store immutability versus logical
manifest fingerprints. No broader gate or additional paid replay is authorized by
these results.

## Corrected KB Semantic Replay And Canonical Rejection (2026-08-27)

### Authority and preflight

The user separately approved sequential corrected focused execution of only
`KBF_T2_018` and `KBF_T1_017`. The five-question gate remained outside this
authority and did not run. Two production-order no-call preflights stopped before
query embeddings and LLM/provider construction and produced the same receipt
SHA-256:
`d516610e26d6b8352c5901243206708cce368749e3bccd9c7652e30acb635d2d`.
They confirmed the single KB/2023/`20240326000894` store, 2,093 cached embeddings,
OpenAI `text-embedding-3-large` at dimension 3,072, and the two requested rows
only.

Both provider runs were isolated, sequential, and monitored with 30-second
heartbeat logs. They reused the existing document store and performed zero
document-embedding calls.

| Row | Runtime | Provider usage | Evaluator surface |
| --- | --- | --- | --- |
| `KBF_T2_018` | about 102 seconds total; question latency `48.789s`; 5,045 catalog / 128 prompt candidates; first-attempt 4/4 `ok`; task/artifact `1 / 4`, integrity `ok` | 6 LLM calls / 108,855 tokens; 4 query-embedding calls / 168 estimated tokens; local runtime estimate `$0.0743157` | numeric PASS; faithfulness/completeness `1.000 / 1.000`; calculation and grounded rendering `1.000` |
| `KBF_T1_017` | about 44 seconds total; question latency `24.940s`; 2,462 catalog / 128 prompt candidates; first-attempt 3/3 `ok`; task/artifact `1 / 4`, integrity `ok` | 6 LLM calls / 94,378 tokens; 4 query-embedding calls / 95 estimated tokens; local runtime estimate `$0.0423010` | numeric PASS; faithfulness/completeness `1.000 / 1.000`; operand/calculation/grounded rendering `1.000` |

These cost figures are profile-based local estimates, not provider invoices.

### Canonical acceptance audit

`KBF_T1_017` is clean for the observed head. The compiler selected `1.83%` and
`1.73%` from the same NIM row, table, source anchor, and consolidated context,
executed their difference, and rendered `0.10%p`. Coupling keys were 22 characters
rather than the prior 153,874-character failure surface.

`KBF_T2_018` is rejected as canonical acceptance even though its evaluator and
ledger surfaces passed. The program selected:

- current `cand_adb73bc8d7bf7d37c2a6`, raw `3,146억원`;
- prior `cand_7db440fbdcaaca0a57d8`, raw `1,848억원`;
- source row `20240326000894:1616:1`, table
  `IV. 이사의 경영진단 및 분석의견::table:1`, `statement_type = mda`;
- deterministic growth `70.238095...%`, rendered `70.24%`.

The question explicitly requests the connected comprehensive income statement.
The canonical stored row is `20240326000894:470:1`, table
`III. 재무에 관한 사항 > 2. 연결재무제표::table:2`,
`statement_type = income_statement`, with raw
`(3,146,409)백만원 / (1,847,775)백만원` and about `70.28%`. Its reconstructed
immutable candidate IDs are `cand_e1d8aa527b06dfafde43` and
`cand_ac08297806e6475c8ecd`; neither appeared in the 128 exposed compiler IDs.
The dataset row has no expected operands or accepted calculation variant, so the
numeric judge compared the final surface without proving these canonical inputs.

### General cause and no-call successor

The retrieval trace selected eight semantically distinct queries, including the
connected-statement query, but executed only the first vector search. The
state-local cache treated the shared obligation/objective signature as result
equivalence and reused that result seven times. Final retrieval therefore
contained eight note chunks, while the exact statement row never entered the
candidate catalog. This is an evidence-coverage failure before the compiler, not
an arithmetic failure.

The raw filing separately shows `(단위: 십억원, %, %p)` for the rounded MDA table
at line 178561. The stored node and table payload instead carry `unit_hint = 억원`:
the parser matched the shorter suffix inside `십억원`. That metadata error makes
the selected monetary amounts wrong by a factor of ten even though their ratio is
close to the exact statement ratio.

Two company- and benchmark-independent tests failed before the successor and now
pass:

- different semantic retrieval queries with the same obligations execute
  independently; state query-result cache reuse is exact source/query/filter
  only, while an identical query still reuses its cached result;
- parser unit inference recognizes longest token `십억원` before `억원` and
  propagates it to every structured row cell.

Focused retrieval 22/22, parser 31/31, semantic-program 46/46, runtime-domain
audit 86, and full unittest discovery 614/614 pass. No provider call followed
these fixes. Because the parser signature changed, the existing KB store is stale
for exact-current-head acceptance and was not rewritten in place. A fresh
isolated store build and focused replay require separate cost authorization; the
broader five-question gate remains HOLD. All result bundles, stores, caches, and
heartbeat logs remain ignored and local-only.

## Approved KB Focused Replay And Generic Program Repairs (2026-08-27)

### Authority and execution

The user separately approved only sequential store-fixed focused execution of
`KBF_T2_018` and `KBF_T1_017` against the isolated KB 2023 canonical store. Both
runs used 30-second heartbeat logs and separate ignored output directories. They
reused 2,093 stored document embeddings and performed zero document-embedding
calls. The five-question gate was not authorized or executed.

Two no-call production-order receipts were byte-identical before each provider
boundary. `KBF_T2_018` completed in about 119 seconds (question latency 76.404
seconds), with 7 LLM calls / 42,698 tokens and 4 query-embedding calls / 191
estimated tokens. `KBF_T1_017` completed in about 308 seconds (question latency
275.326 seconds), with 7 LLM calls / 368,066 tokens and 4 query-embedding calls /
97 estimated tokens. Profile-based runtime LLM estimates were approximately
`$0.0637086` and `$0.2744958`; they are local estimates, not invoices.

### Observed artifacts

| Row | Evaluator surface | Semantic-program evidence | Interpretation |
| --- | --- | --- | --- |
| `KBF_T2_018` | numeric PASS; faithfulness/completeness `1.000 / 1.000` | routed `risk / mixed`; empty `structured_result`, empty calculation trace, zero tasks and artifacts | the prose answer contained the current/prior amounts, about `70.29%`, and risk explanation, but this run did not exercise the canonical calculation program |
| `KBF_T1_017` | numeric PASS; faithfulness/completeness `1.000 / 0.500` | selected `1.83%` and `1.73%` from the same row/table/source and proposed `v_ob_001 - v_ob_002`; execution remained 2/3 partial | validation rejected only `result_unit_mismatch: PERCENT -> %p`, so the answer refused the required `0.10%p` delta despite correct semantics |

The T1 task/artifact ledger contained one task and four required artifacts with
integrity `ok`. That structural health did not upgrade the missing required
derived obligation. The evaluator dataset has no expected calculation result or
accepted calculation variants for these rows, so numeric equivalence/grounding
could promote both answers to PASS without proving calculation-program
completeness. Score, ledger integrity, and semantic completeness remain separate
signals.

T1 also exposed a 153,874-character repeated `coupling_key` from the requirement
planner. It was propagated into later compiler payloads and accounts for the
abnormally large token total; it is not financial evidence and should never be
an unbounded prompt surface.

### Generic repair and no-call proof

Three company- and benchmark-independent characterization tests failed before
the repair and now pass:

- every `mixed` format enters requirement/program planning even when the coarse
  route is narrative such as `risk`;
- subtracting two `PERCENT` operands may retain canonical `PERCENT` dimension and
  render the difference as `%p`, from declarative render policy;
- coupling keys are whitespace-normalized and deterministically bounded to 128
  characters, while the planner prompt requests at most 64.

Re-executing the exact saved T1 program and exact saved candidates through the
repaired pure executor changed `partial` to `ok`, cleared missing obligations,
and rendered `0.10%p` with the same two candidate/source IDs. This is strong
deterministic evidence for the unit-contract fix, but it is not a fresh provider
observation of routing or bounded planner output.

Eval-only projection was also corrected generically: targets record
`execution_mode = eval_only`, preserve the source mode/scope separately, and
derive completion from only the selected company runs. The T2 artifact was
created before the last projection correction, so its top summary still says
`partial` and its company matrix retains the source question set. The focused
runtime row itself is intact; the historical artifact was not rewritten. The T1
successor records the effective one-question scope and completed status.

### Verification and decision

- semantic-program plus benchmark-runner focused tests: 75/75;
- runtime-domain audit: 86 reviewed literals;
- full unittest discovery: 612/612;
- saved NIM offline execution: 3/3 obligations, status `ok`, `0.10%p`;
- benchmark stores, results, and heartbeat logs remain ignored and local-only.

The next paid boundary is a separately approved corrected focused replay of the
same two KB rows. It must establish that T2 now produces a complete mixed
program and T1 remains complete with bounded prompt state. Do not run the
five-question gate from the current PASS labels alone.

## Semantic Calculation Program No-Call Gate (2026-08-27)

### Setup

- scope: numeric and mixed questions only; narrative-only flow unchanged;
- comparison material: curated generic fixture
  `tests/fixtures/semantic_program_offline_comparison.json` plus fixed Pydantic
  structured outputs;
- provider calls, DART fetch/parse/ingest, embeddings, eval-only replay, and
  benchmark runner: not used;
- working-tree base: `main@a9a2df5`; the result is uncommitted local source
  evidence, not a release or remote-CI receipt.

### Contract change

- pre-retrieval planning emits direct, derived, and narrative answer obligations
  without choosing an operation family;
- runtime builds immutable candidate IDs from retrieved row/cell/sentence
  provenance, and the LLM can select IDs but cannot invent values or evidence;
- one post-evidence compiler produces direct bindings, restricted expressions,
  narrative grounding, displays, and missing/ambiguous IDs;
- deterministic validation checks references, cycles, AST/function allowlist,
  constant origin, finite values, unit dimensions, result unit, obligation kind,
  entity/period/consolidation/segment/basis/source context, coupled-output
  coherence, and grounded compatibility evidence;
- one targeted retry can add only missing/ambiguous obligations and cannot
  overwrite valid first-response bindings;
- `operation_family` is derived after execution for compatibility. Semantic
  completeness and ledger integrity remain separate signals.

### Results and limits

- semantic calculation program focused tests: 27/27;
- runtime domain-language audit: 86 reviewed literals, pass;
- full `unittest discover -s tests` in an isolated requirements environment:
  574/574, pass;
- compileall: pass;
- named legacy planner/extractor/formula symbols have zero production callers;
- the offline fixture confirms equal deterministic growth output for a
  same-context `343 -> 380` case and fail-closed rejection of cross-context
  composition. It is curated characterization evidence, not a fresh benchmark;
- no accuracy, latency, token, or cost claim is made for the new canonical path.

### Decision

Review the code/deletion diff first. With separate cost approval, run the five
specified focused store-fixed replays and compare canonical row/value/unit/source,
required-obligation completeness, retry count, and ledger integrity. Only then
consider the existing heartbeat-monitored five-question gate. Keep all raw
benchmark outputs local.

## Semantic Program Three-Row Diagnostic And No-Call Successor (2026-08-27)

### Setup and evidence boundary

- mode: four sequential, heartbeat-monitored, store-fixed focused iterations;
- questions: `SAM_T2_078`, `NAV_T2_006`, and `LGE_T1_051` only;
- ignored local directories, in execution order:
  - `benchmarks/results/semantic_program_focused_core_2026-08-27/`;
  - `benchmarks/results/semantic_program_focused_core_retry_2026-08-27/`;
  - `benchmarks/results/semantic_program_focused_core_scope_witness_2026-08-27/`;
  - `benchmarks/results/semantic_program_focused_core_full_catalog_2026-08-27/`;
- no fresh DART fetch, parse, ingest, document embedding, or store construction;
- the two requested KB questions were not executed because no reusable KB
  company result bundle/store was present. This missing input did not authorize
  fresh ingest;
- the existing broader five-question gate was not executed for this path.

The directory suffix `full_catalog` records the experiment label, not the
implemented contract. Its trace still had `candidate_count = 128` and
`prompt_candidate_count = 128`, because the then-current builder truncated the
catalog before prompt projection.

### Observed final-iteration artifacts

| Row | Program/execution | Canonical observation | Interpretation |
| --- | --- | --- | --- |
| `NAV_T2_006` | first compiler attempt `ready`; execution `ok`; four obligations rendered | same-row `2,546.6억원` and `1,801.1억원`; formula `41.391...%`; source display `41.4%`; grounded Poshmark text | Numeric selection was correct, but the final answer rendered `41.4%억원`. The percent cell had normalized unit `PERCENT` while a table-wide `억원` raw-unit hint was appended by presentation code |
| `SAM_T2_078` | first compiler attempt `ready`; execution `ok`; two obligations rendered | selected `연구개발비용 계 / 28,339,724백만원`, plus grounded Harman sources | Structural completeness was not semantic correctness. The requested/source-key total is `연구개발비용 총계 / 28,352,769백만원`; the compiler collapsed two nearby aggregate meanings |
| `LGE_T1_051` | first attempt invalid, one targeted retry, then partial with one of three obligations | selected consolidated operating profit `2,163,234백만원`; rationale explicitly saw prose `6,769억원` but reported that it had no bindable numeric candidate ID | Fail-closed behavior was correct. A source sentence existed as narrative evidence, but the catalog exposed no numeric ID for its stated value, so the derived result could not execute |

The final iteration used three agent calls for NAV and Samsung and four for LGE
because only LGE used the bounded compiler retry. Question latency was about
42.14s, 34.70s, and 83.48s respectively. Program-compilation prompts were still
large (about 69k, 67k, and 137k prompt tokens); these are diagnostic
observations under one stored run, not performance claims.

### Generic no-call successor

- The transient candidate catalog now retains all candidates from visible and
  preserved seed evidence. Only the model prompt is bounded.
- Prompt admission is stratified by answer obligation and source group. Exact
  exposed IDs plus projection and excerpt strategy are recorded in the plan;
  validation rejects a real catalog ID if that invocation did not expose it.
- Explicit numeric surfaces in prose become immutable `sentence_value`
  candidates with normalized values, source spans, bounded sentence context,
  and original provenance. Narrative candidates remain narrative grounding.
- Prompt excerpts center on obligation/candidate relevance instead of taking a
  fixed prefix. More-specific source phrases outrank generic token overlap.
- Config-backed `aggregate_label` and `aggregation_stage` preserve distinct
  structural labels for semantic comparison; deterministic code does not decide
  which financial meaning answers the question.
- Source rendering keeps an embedded percent marker and cannot append an
  incompatible table-wide currency hint.

Generic fixtures cover more than 96 competing numeric candidates with a late
source-stated prose value, late relevant context, distinct aggregate labels,
hidden/unexposed candidate rejection, and an embedded percent with a conflicting
raw-unit hint. Final no-call gates are semantic/task/projection focused 47/47,
runtime-domain audit 86, full unittest 589/589, and pycompile. No provider call
was made after these repairs.

### Decision

The diagnostic focused gate remains **not accepted**. A new paid activation
requires separate approval and should rerun the repaired three core rows first.
Only after their canonical row/value/unit/source and obligation completeness are
clean should the project decide how to provision KB stores or run the broader
heartbeat gate. Raw benchmark artifacts remain local and uncommitted.

## Approved Semantic-Program Core Replay And Mixed-Chunk Successor (2026-08-27)

### Setup and evidence boundary

- explicit user approval covered one repaired core-row activation;
- profile: `benchmarks/profiles/curated_policy_driven_runtime_gate.json`;
- read-only source bundle:
  `benchmarks/results/integration_policy_gate_semantic_source_scope_successor_2026-08-27/`;
- ignored local output:
  `benchmarks/results/semantic_program_focused_core_repaired_2026-08-27/`;
- questions ran sequentially with a 30-second heartbeat: `NAV_T2_006`,
  `LGE_T1_051`, then `SAM_T2_078`;
- no DART fetch, parse, ingest, store rebuild, or document embedding occurred.

### Provider result

| Row | Program trace | Canonical result | Evaluation boundary |
| --- | --- | --- | --- |
| `NAV_T2_006` | first compiler attempt `ready`, 930 catalog / 128 prompt candidates, four selected IDs, execution `ok`, 4/4 obligations | same `커머스` row: `2,546.6억원 / 1,801.1억원`; formula `41.391...%`, source display `41.4%`; grounded Poshmark restructuring summary; no `%억원` contamination | calculation/faithfulness `1.000`, integrity `ok`, error 0. Completeness `0.700` because the judge expected a second grounded mechanism, `연결 편입 효과`, which the selected summary omitted |
| `LGE_T1_051` | first attempt invalid, one targeted retry, final `partial`; 810 catalog / 128 prompt candidates; execution 1/3 obligations | correct consolidated `영업이익(손실) / 2,163,234백만원` only. The compiler explicitly identified narrative candidate `cand_e577f8cf18aa32af5120` as containing `6,769억원` but could not bind it as numeric | integrity `ok`, error 0, completeness `0.300`. Numeric PASS reflects the one returned value and must not override semantic partial status |
| `SAM_T2_078` | first compiler attempt `ready`, 1,848 catalog / 128 prompt candidates, four selected IDs, execution `ok`, 2/2 obligations | exact `연구개발비용 총계 / 28,352,769 / 백만원`, final aggregation metadata, same-source consolidated compatibility witness, grounded Harman narrative | calculation/faithfulness/completeness `1.000`, integrity `ok`, error 0 |

The monitored command completed in 235.374 seconds. Question latency was
44.208 seconds for NAVER, 73.818 for LGE, and 35.874 for Samsung. The artifact
records 17 total LLM calls, 366,322 tokens, 12 query embeddings, zero document
embeddings, and estimated runtime cost `$0.1924670`. Top-level result SHA-256 is
`155e5a13d603fcb7ac847f2ad006d15edea5a1ca6cca9d288d7a48946b2b5899`.
These are one-run observations, not latency, token, cost, or accuracy claims.

### Generic post-run successor

The LGE source was present in stored chunk `20240314001110:657:3`. It is an
explicit `paragraph` with `is_table=false`, but the parser also attached adjacent
table row/value metadata. The catalog's former all-or-nothing structured-material
guard therefore suppressed prose-number projection for the sentence that states
`6,769억원`.

The successor retains prose numeric candidates for explicitly non-table chunks
even when adjacent table structure is attached. A generic fixture reproduces
the mixed paragraph shape. A no-call reconstruction over all 783 stored LGE
chunks produced 1,050 candidates (267 numeric and 783 narrative); the immutable
`6,769억원` `sentence_value` was generated once and admitted to the bounded
128-candidate prompt projection.

Final no-call gates are semantic/task/projection focused 48/48, runtime-domain
audit 86, full unittest 590/590, compileall, legacy production callers zero, and
clean diff check. At this checkpoint the mixed-chunk successor had not been
provider-replayed. The separately approved successor below closes that boundary.

## LGE Mixed-Chunk Provider Acceptance Successor (2026-08-27)

### Setup and observed result

- separate user approval covered one `LGE_T1_051` store-fixed replay only;
- source bundle remained
  `benchmarks/results/integration_policy_gate_semantic_source_scope_successor_2026-08-27/`;
- ignored output is
  `benchmarks/results/semantic_program_lge_mixed_chunk_successor_2026-08-27/`;
- the monitored `--eval-only` command used a 30-second heartbeat and performed no
  DART fetch, parse, ingest, store rebuild, or document embedding.

The requirement plan produced three obligations. After one targeted compiler
retry, the 553-candidate catalog / 128-candidate prompt projection selected two
direct IDs and one expression:

- `cand_6434f10c4bdef3501a6f`: connected-note
  `영업이익(손실) 2,163,234백만원`;
- `cand_53eed93ed23c561cad39`: the same connected-note context's
  `기타영업손익 676,874백만원`;
- `operating_income - ampc_amount = 1,486,360백만원`.

The second row is not an unlabeled nearby value. Its same-table source context
explicitly explains that the amount is revenue expected under the US IRA
advanced-manufacturing production-credit scheme. The compiler's explanation
made that semantic link before execution. It therefore chose a more precise
structured value than the rounded management-discussion display `6,769억원`.
The prose candidate remains available in the catalog; forcing its rounded value
would turn source preservation into benchmark-specific deterministic selection.

Execution status is `ok`, all 3/3 obligations are rendered, task/artifact
integrity is `ok`, numeric judgement is PASS, faithfulness is `1.000`, and error
rate is `0.0%`. Completeness is `0.700` because the final answer is a terse slot
list and omits company/year/IRA wording; this is a qualitative rendering
residual, not a calculation or provenance failure. The run recorded 7 LLM calls,
181,362 tokens, four query embeddings, zero document embeddings, 54.042 seconds
of question latency, and estimated runtime cost `$0.0918372`. Root and company
result SHA-256 values are respectively
`afd623fec0a3a570ecc56a461e5af14912898782a96ede40b41b5a63a4f8b618` and
`7e69391e67f56f86db82ce58773dacd189363e3e206679e02d2f121227083ee1`.
These are one-run observations, not general cost or quality claims.

The three core semantic-program rows are now accepted. The two KB rows still
lack reusable stores and the broader five-question gate was not authorized.
Raw benchmark output remains local and uncommitted.

## Atomic Multiple Calculation Answer Contract (2026-08-27)

### Contract and dataset change

- added optional typed `accepted_calculation_variants` to curated numeric
  examples while retaining the primary `answer_key` for qualitative and legacy
  compatibility;
- each variant carries one answer representation, distinct expected operands,
  operation, expected result, and source/scope constraints;
- numeric prose must contain every numeric claim at the selected variant's
  precision, and the canonical semantic-program output must bind every matched
  candidate ID. Mixing operand/result values or provenance across variants
  fails closed;
- current-run evaluation and historical-answer no-call replay use the same
  atomic contract. Variant matching reads the pre-`primary_value` canonical
  operand trace so multi-output semantic programs do not lose direct inputs;
- runtime planning, retrieval, candidate selection, execution, and rendering do
  not read this evaluator-only field.

The canonical LGE record and its multi-subtask/multi-metric curated slices now
carry two synchronized variants:

- `connected_note_precise`: `2,163,234백만원 - 676,874백만원 =
  1,486,360백만원`, with connected-note, `notes`, and consolidated constraints;
- `management_discussion_rounded`: `2조 1,632억원 - 6,769억원 =
  1조 4,863억원`, with the rounded source paragraph context.

The exact `기타영업손익 676,874백만원` structured row was added to canonical
evidence beside the source explanation that identifies it as IRA advanced-
manufacturing production-credit revenue.

### No-call verification

- new focused contract tests: 14/14;
- evaluator/math/runtime-projection/import focused set in the requirements
  environment: 128/128;
- full unittest discovery in the same requirements environment: 604/604;
- runtime-domain audit: 86 reviewed literals; compileall and graph/evaluator
  imports passed;
- existing ignored source artifact:
  `benchmarks/results/semantic_program_lge_mixed_chunk_successor_2026-08-27/`;
- ignored evaluator-only replay output:
  `benchmarks/results/semantic_program_lge_multiple_answer_replay_2026-08-27/`;
- replay result: `accepted_calculation_variant_id = connected_note_precise`,
  `numeric_equivalence = 1.000`, operand/result/calculation correctness
  `1.000`, final numeric judgement PASS.

This replay made no provider, embedding, DART fetch, parse, ingest, or store
rebuild call. It validates the new evaluator contract against an already saved
runtime artifact; it is not a fresh runtime-quality or cost observation.

## Generic Semantic Rendering Characterization And KB Store Audit (2026-08-27)

### Exact-artifact characterization

No provider, embedding, evaluator-judge, DART fetch, parse, ingest, or store
mutation occurred. The inputs were the ignored saved artifacts
`benchmarks/results/semantic_program_focused_core_repaired_2026-08-27/` and
`benchmarks/results/semantic_program_lge_mixed_chunk_successor_2026-08-27/`.

The two qualitative `0.700` results came from different boundaries:

- NAVER had four selected candidates, four runtime evidence rows, and eight
  retrieved previews. None contained the second acquisition-effect mechanism
  named by the qualitative reference. Its one narrative binding grounded only
  the selected restructuring effect. A deterministic renderer cannot introduce
  an absent mechanism from the reference answer or query hints; that would break
  evidence-first generation. This is an evidence/planner/compiler-coverage
  observation, not a renderer patch target.
- LGE's three executed obligations all carried the same company, 2023 period,
  and consolidated scope, but the semantic executor joined them as terse
  `label: value` fragments. A generic renderer now emits scope only when the same
  non-unknown value belongs to every rendered obligation, projects it once on
  the first Korean numeric sentence, and renders later values as complete
  sentences. It never imports unselected narrative text. Pure execution of the
  saved LGE program remained `ok`, preserved all three displays
  (`2,163,234백만원`, `676,874백만원`, `1,486,360백만원`), and reported no missing
  obligation. This was not a new completeness score.

The checked-in fixture
`tests/fixtures/semantic_program_rendering_residuals.json` is company- and
benchmark-independent. One case verifies common company/period/consolidation
projection over two direct values and one expression. The other verifies that
an unselected narrative candidate is not copied into the answer.

### KB input audit

The read-only audit covered every local benchmark `results.json`, Chroma
`chroma.sqlite3`, `vector_store_meta.json`, `benchmark_cache_meta.json`, and
`context_cache/*.json`. It found no reusable 2023 KB result bundle, vector store,
or context cache for `KBF_T2_018` / `KBF_T1_017`. The standalone
`data/chroma_dart` collection contains 1,216 embeddings only for KB receipt
`20230316001417` and year 2022, so it cannot satisfy the target report scope.

Both local 2023 HTML reports exist. The historical expanded-candidate profile
for the requested pair uses receipt `20240326000894`, canonical experiment ID
`structural_selective_v2_prefix_2500_320`, and the structural-selective-v2
2500/320 ingest. With no matching store or context cache, the next operation
would be a fresh canonical store build with document embeddings. That operation
requires explicit cost/ingest authority; it was not inferred from this audit.

### Verification and decision

- semantic-program module: 43/43;
- affected renderer/evaluator/projection/import focused set: 98/98;
- runtime-domain audit: 86 reviewed literals;
- full unittest discovery: 605/605;
- compileall, graph/evaluator imports, JSON parse, and diff check: pass.

The immediate no-cost characterization is closed. Do not tune NAVER from the
benchmark reference and do not claim that LGE's qualitative score improved
without a provider/evaluator replay. Seek separate authorization first for the
KB canonical store build, then for the focused KB rows and broader monitored
gate. Raw benchmark artifacts remain local.

## Authorized KB Canonical Store-Only Build (2026-08-27)

### Authority and preflight

The user separately approved only an isolated canonical store build for the
local KB 2023 report. Questions, agent answer generation, LLM judges, and the
five-question gate were outside that authority. A new fail-closed runner mode
requires exactly one company run and canonical experiment, rejects evaluator
and retrieval-runtime flags, disables report autofetch, and indexes only the
existing primary report rather than evaluation-dataset source-report history.

Two production-order `--store-only --preflight-only` runs stopped before vector-
store/provider construction and produced the byte-identical manifest SHA-256
`3017fdb8cfabb65072ae5e4dff22f047f542235e93cfb3b861b791ab519de0d2`.
It fixed company run `kbf_2023_expanded_candidate`, receipt `20240326000894`,
experiment `structural_selective_v2_prefix_2500_320`, 2500/320 chunks, OpenAI
`text-embedding-3-large`, dimension 3072, primary-report-only inventory, and no
autofetch. The report SHA-256 was
`13b1d57baae0cf9579828b3129e1bae7417e43215e556df5e2ec4cf46ba9aea0`.

### Observed store build

The monitored build completed in about 128 seconds:

- parser output: 51 section parents and 2,093 chunks; one large section exceeded
  its structured parse budget and completed through the existing plain fallback;
- document ingest delta: 33 embedding requests, 2,093 texts, 2,678,098 input
  characters, 670,328 locally estimated tokens, and 2,093 added / 0 skipped;
- semantic/context LLM: zero calls and zero tokens;
- store: one Chroma collection, dimension 3072, exactly 2,093 embeddings;
- metadata: only `KB금융`, year 2023, business report, receipt
  `20240326000894`; cache status `completed`, report inventory count one;
- heartbeat: terminal `completed` at 2,093/2,093, with zero smoke,
  screening-evaluation, and full-evaluation phases;
- local artifact hashes: top results
  `c60a7588a5237e2ffcb92d01015ab66450a022d9b3d773708869a5be49b12a06`,
  company results
  `f899eec1372a4caddfdd0cb3f31af1a6b1fe27f975ede97ec5ae504d4b8b878f`,
  and Chroma SQLite
  `6871be1bbf2e230be100351074e2bb1cff785fb9906e4ab02969ba46029fa02c`.

At the current [official model-card rate](https://developers.openai.com/api/docs/models/text-embedding-3-large)
of `$0.13 / 1M` input tokens, the local document-token estimate corresponds to
about `$0.08714264`. This is an estimate, not an invoice; the profile omitted an
embedding rate, so its result field is null.

### Initialization leakage and closure

Live output exposed one additional OpenAI embeddings request before parsing.
The store-only path had constructed the full `FinancialAgent`, whose semantic
router embedded 74 canonical queries. The local tracker rule estimates 407
tokens (`$0.00005291` at the same rate), making the observed endpoint total 34
requests and the combined local estimate about `$0.08719555`. This was not a
question, LLM answer, or evaluator call, and it did not alter the 2,093-document
store, but it exceeded the manifest's document-only boundary. The build ran
under runner SHA-256
`eb36f765bf42b63506ab14f857a3602e9cb33f1b2a4fb24e9ce3952c76d59ab4`.

The runner now uses a minimal ingest facade exposing only `vsm`; it cannot
initialize semantic routing or evaluator services. Tests assert that store-only
execution does not load the eval dataset or construct `FinancialAgent`, smoke,
screening, or evaluation paths. The repaired runner SHA-256 is
`00fd088376e0f124a9b5d67849a222295d1cb8c67900c4ca4518c1e72ffc87b7`.
Focused store-only tests passed 28/28, the affected ingest/runner set passed
89/89, runtime-domain audit passed with 86 reviewed literals, and full unittest
discovery passed 608/608. The successful paid store was deliberately not rebuilt
solely to remove a historical initialization call.

### Decision

The KB input blocker is closed, but no KB answer quality has yet been observed.
The next paid boundary is a separately approved, heartbeat-monitored store-fixed
run of `KBF_T2_018` and `KBF_T1_017`. Only after inspecting those two artifacts
should the project decide whether to execute the broader five-question gate.
All raw store, cache, results, and heartbeat artifacts remain local and must not
be committed.

## Semantic Source-Scope Repair Three-Row Successor (2026-08-27)

### Setup

- runtime/source contract recorded in `d87e030`;
- profile: `benchmarks/profiles/curated_policy_driven_runtime_gate.json`;
- source stores:
  `benchmarks/results/policy_gate_regression_2026-06-03_1138_actual/`;
- mode: sequential monitored store-fixed `--eval-only` for `SAM_T2_078`,
  `NAV_T2_006`, and `LGE_T1_051`;
- no fresh DART fetch, parse, ingest, or document embedding;
- representative ignored local output directories:
  - `benchmarks/results/focused_semantic_scope_repair_sam_t2_078_b_2026-08-27/`;
  - `benchmarks/results/focused_semantic_scope_repair_nav_t2_006_b_2026-08-27/`;
  - `benchmarks/results/focused_semantic_scope_repair_lge_t1_051_c_2026-08-27/`.

### Generic Contract Change

- A structured numeric response that contains final prose but omits the required
  raw value receives one bounded semantic retry against the same retrieved
  context. A second incomplete response is rejected; final prose is never parsed
  backward into provenance.
- Multiple exact-value source rows receive stable candidate identifiers. The LLM
  selects their meaning or returns ambiguous; code checks that the selected id is
  in the exact-value set and retains row/value/unit/source as deterministic
  authority.
- Materially different structured values force semantic reconciliation despite
  a heuristic score gap. The LLM sees row headers, selected cells, and table
  context. A semantically selected structured row prevents a broad direct
  fallback from overwriting it.
- Structured period recovery preserves actual row and column subjects. A bounded
  realignment retry can ignore stale planner operand roles, and an already
  in-progress ledger task may be superseded only when the resolved aggregate slot
  closes it.
- Evaluator unit consistency returns N/A when fewer than two resolved operands
  exist. The historical replay utility now applies production answer-slot operand
  resolution before deterministic scoring.

### Results

| Row | Answer / provenance | Evaluation | Residual interpretation |
| --- | --- | --- | --- |
| `SAM_T2_078` | `28,352,769백만원`; exact `연구개발비용 총계` row, source `ev_001`, grounded Harman narrative | faithfulness/completeness/refusal/grounded rendering/calculation `1.000`, integrity `ok`, error `0` | stored provider bundle predates the evaluator-only fix and recorded unit `0`; no-call production-order replay returns unit N/A and keeps calculation `1.000` |
| `NAV_T2_006` | exact raw `2,546,649 / 1,801,079백만원`, source-stated display `2조 5,466억원 / 1조 8,011억원`, result `41.4%`, grounded narrative | faithfulness/completeness/refusal/unit/grounded rendering/calculation `1.000`, integrity `ok`, error `0` | operand `0.6667` is two matched calculation inputs divided by three dataset `expected_operands`; the third entry is the derived output `41.4%`. One reflection/replan remains |
| `LGE_T1_051` | selected `영업이익(손실) 2,163,234백만원`; subtracts `6,769억원` to `1,486,334백만원`; preserves `IRA, AMPC` | numeric/operand/unit/faithfulness/completeness/refusal/grounded rendering/calculation `1.000`, integrity `ok`, error `0` | the canary's other-entity `28,980백만원` substitution is gone |

The NAV operand score is an evaluator-schema limitation, not a missing runtime
input. Changing runtime binding to manufacture a third input would violate the
calculation contract. Likewise, the remaining NAV replan is tracked as an
efficiency residual rather than converted into a company/question rule.

### Usage, Receipts, And Decision

- Samsung: 9 LLM calls, 39,861 tokens, 6 query embeddings, 77.308 seconds,
  `$0.0429035`;
- NAVER: 20 calls, 112,062 tokens, 19 query embeddings, 222.486 seconds,
  `$0.1178148`;
- LGE: 11 calls, 48,932 tokens, 5 query embeddings, 61.314 seconds,
  `$0.0457700`;
- aggregate: 40 calls, 200,855 tokens, 30 query embeddings, zero document
  embeddings, 361.107 question-seconds, `$0.2064883`;
- top-level result SHA-256: Samsung
  `81e4f317c95212770d87fce802d51f7455ee1fc9624738c2df55368f36680c89`,
  NAVER `0053610696f624e6614a746b9085e785429f388b027e808262b2bb6a6fc7b931`,
  LGE `b575172602a21e7548a09487027305e06accdea9ec1f3f0dfddef92a5ff35a98`.

Compared with the failed canary, the observed aggregate calls/tokens/latency
changed from `57 / 311,132 / 589.281s` to `40 / 200,855 / 361.107s`. This is a
focused-run observation under provider variance, not a general performance
claim. Runtime-domain audit passed 217; related contracts 794/794, structural
helpers 290/290, dependency projection 75/75, and full unittest 2,172/2,172 in
290.959 seconds passed. GitHub Actions `33007869709` then passed reviewer
contracts 32/32, audit 217, and Ubuntu/Python 3.13 full unittest 2,172/2,172 in
211.605 seconds; the full job took 4 minutes 26 seconds.

The LGE correctness blocker is closed for the selected set. These outputs remain
local ignored artifacts and are not fresh-ingest or held-out evidence. PR #86 is
still draft and `main` unchanged. The next decision is whether to buy one broader
five-question store-fixed gate or proceed to integration review with the NAV
efficiency and evaluator-schema residuals explicitly accepted.

## Current-Head Five-Question Store-Fixed Gate (2026-08-27)

### Setup And Admission

- docs/source HEAD: `5cdab83`; runtime contract: `d87e030`;
- profile: `benchmarks/profiles/curated_policy_driven_runtime_gate.json`;
- read-only source stores:
  `benchmarks/results/policy_gate_regression_2026-06-03_1138_actual/`;
- ignored successor:
  `benchmarks/results/integration_policy_gate_semantic_source_scope_successor_2026-08-27/`;
- questions: `NAV_T2_006`, `HYU_T2_010`, `HYU_T3_072`, `LGE_T1_051`,
  `SAM_T2_078`;
- mode: one sequential monitored `--eval-only`, no fresh DART fetch, parse,
  ingest, or document embedding.

Before provider execution, current profile fields matched each persisted cache
signature and all four cache records were `completed`. The four strict vector
health probes each returned `ok=true`, `result_count=1`. Those probe embeddings
are outside the benchmark artifact's usage counters.

### Result

| Row | Answer / trace | Evaluation | Interpretation |
| --- | --- | --- | --- |
| `NAV_T2_006` | `2,546,649 / 1,801,079백만원 = 41.4%`, grounded Poshmark summary | all key quality/calculation metrics `1.000`, integrity `ok`, error 0 | canonical segment and period operands remain stable; operand `2/3` is the existing dataset-output schema residual |
| `HYU_T2_010` | `87.0만 대 / 78.1만 대 = 11.5%`, grounded IRA/protectionism response need | faithfulness/context recall/grounded rendering/calculation/refusal `1.000`, completeness `0.700`, integrity `ok` | LLM judge required explicit “사업보고서에서” attribution in the final prose; this is the only formal gate failure |
| `HYU_T3_072` | Motional `50.00% -> 25.81%`, `1,294,367백만원`, continuing/total comprehensive losses | completeness and key quality/calculation `1.000`, integrity `ok` | first incomplete numeric structured output was rejected; bounded retry recovered the correct lookup. Heterogeneous lookup unit score `0` is unchanged from the prior clean gate |
| `LGE_T1_051` | `2,163,234백만원 - 6,769억원 = 1,486,334백만원`, `IRA, AMPC` | numeric PASS and all key metrics `1.000`, integrity `ok` | wrong-entity fallback remains closed |
| `SAM_T2_078` | exact `연구개발비용 총계 / 28,352,769 / 백만원 / ev_001`, grounded Harman narrative | all key quality/calculation metrics `1.000`, unit N/A, integrity `ok` | semantic source row remains canonical |

The run completed in 592.607 seconds with company pass count 4, runtime error 0,
and integrity issue 0. Formal `full_eval_fail_count=1` because the ranking requires
company completeness exactly `1.0`; Hyundai averaged `0.850`. Official
company-average completeness is `0.9625`, while the five-question weighted mean
is `0.940`. A prior semantically equivalent `HYU_T2_010` answer scored `1.000`,
and the current answer contains the requested calculation and policy-response
summary. This is recorded as qualitative evaluator variance, not evidence for a
runtime wording branch or benchmark-specific tuning.

### Usage And Receipts

- 59 LLM calls, 324,521 tokens, 45 query embeddings, zero document embeddings;
- 498.909 question-seconds and `$0.3059185` estimated runtime LLM cost;
- compared with the previous clean full gate: calls `52 -> 59`, tokens
  `290,893 -> 324,521`, wall time `570.031 -> 592.607` seconds, and cost
  `$0.2595345 -> $0.3059185`; these are provider-run observations, not general
  performance claims;
- top result SHA-256:
  `1d9f7508e758dd85c057dc1be5d7f87cf261495b44833d1a0d9d88a90c5d63c8`;
- company result SHA-256: NAVER
  `e69381cbb03428ff77111e664140305e34a477ec499b61067359ad6e80fc73e4`,
  Hyundai `597bfafa0edb74888df762d27d22e79a8dd51cf58f8662ac78deb5de366f1c42`,
  LGE `9bf060f86637c5abb664cd01b37edef1c58c4120942d324e9bcfa15d96a788a1`,
  Samsung `4417f382ad3941fd0598d8c1f0a4dca371c3be9969623fee0b70f9f6ebdeeed1`.

A no-call production-order replay confirmed grounded rendering and calculation
`1.000` for all five rows. It also produces synthetic numeric verdicts for mixed
rows whose source verdict is N/A; those replay verdicts are diagnostic and are
not used as the gate score. Raw result, heartbeat, and replay summaries remain
local ignored artifacts. No code changed, PR #86 remains draft, and `main`
remains unchanged.

## Exact-Current-Head Three-Row Canary (2026-08-27)

### Setup

- source/docs head: `b422a9b`;
- profile: `benchmarks/profiles/curated_policy_driven_runtime_gate.json`;
- source stores:
  `benchmarks/results/policy_gate_regression_2026-06-03_1138_actual/`;
- mode: sequential monitored `--eval-only` for `SAM_T2_078`, `NAV_T2_006`,
  and `LGE_T1_051`;
- no fresh DART fetch, parse, ingest, or document embedding;
- local ignored output directories:
  - `benchmarks/results/focused_current_head_sam_t2_078_2026-08-27/`;
  - `benchmarks/results/focused_current_head_nav_t2_006_2026-08-27/`;
  - `benchmarks/results/focused_current_head_lge_t1_051_2026-08-27/`.

### Results

| Row | Answer / trace result | Evaluation | Interpretation |
| --- | --- | --- | --- |
| `SAM_T2_078` | `28,352,769백만원`; exact row `연구개발비용 총계 | 제55기 | 28,352,769 | 백만원`, source `ev_001` | faithfulness/completeness/refusal/grounded rendering/calculation `1.000`; integrity `ok` | canonical row/value/unit/source is stable; no final-prose reverse sync or retrieval-score leakage |
| `NAV_T2_006` | same-row `2,546.6억원 / 1,801.1억원 = 41.4%`; two operands, integrity `ok` | key quality/calculation signals `1.000`; numeric judgement N/A for the mixed row | correct, but first partial operand artifact triggered reflection and semantic replan |
| `LGE_T1_051` | wrong `28,980백만원 - 6,769억원 = -647,920백만원`; expected operand/result `2,163,234백만원 / 1,486,334백만원` | numeric FAIL, equivalence/grounding `0`, operand correctness `0.5`, unit consistency `0`; integrity `ok` | semantic extraction's missing value let fallback bind a subsidiary row despite correct consolidated retrieval coverage |

`numeric_final_judgement=null` for the healthy Samsung/NAVER mixed rows is N/A,
not failure. The LGE result is an actual numeric failure.

### LGE Failure Boundary

The LGE numeric extractor received a candidate window containing the correct
consolidated row and wrote `2,163,234 백만원` in its semantic final prose, but
returned empty structured `raw_value`. The fingerprint
`17c499459ec2a8602f1811df9d9a54b8390fcb1260c4ebda5b23cc9c85aad290`
is identical to the earlier clean run, where the provider did return the raw
value. The runtime correctly did not parse final prose back into the source slot.

The subsequent deterministic lookup fallback selected
`ratio_doc_context_026::row:3`, label `영업이익`, value `28,980백만원`, from a
different entity table. The correct `영업이익(손실) 2,163,234백만원` row remained
present in retrieved table metadata. Therefore this is not a retrieval miss,
derived-value rendering bug, or arithmetic bug. It is a robustness gap at the
semantic structured-output / entity-and-table-scope acceptance boundary.

The next implementation should remain generic: treat nonempty semantic prose
with missing required structured value as a contract violation; allow a bounded
semantic retry against explicit candidate identifiers or fail closed; and make
deterministic validation reject entity-incoherent same-label substitution. A
synthetic consolidated-versus-subsidiary same-label test should precede another
provider replay. Repeating unchanged LGE until it passes would not close the
observed variance.

### Usage, Receipts, And Decision

- Samsung: 9 LLM calls, 41,431 tokens, 6 query embeddings, 88.820 seconds,
  `$0.0508589`;
- NAVER: 30 calls, 177,670 tokens, 21 query embeddings, 371.691 seconds,
  `$0.182507`;
- LGE: 18 calls, 92,031 tokens, 5 query embeddings, 128.770 seconds,
  `$0.0883425`;
- aggregate: 57 calls, 311,132 tokens, 32 query embeddings, zero document
  embeddings, 589.281 question-seconds, `$0.3217084`;
- top-level result SHA-256: Samsung
  `03183027568fd244133723e01c35a109c16d97055ec827c46481635c901a81de`,
  NAVER `4dde511bcd4986c54865dc560c598c7b30569c6d21348446efec3aae14f31121`,
  LGE `b6c47452018a7d3a7710a59fc39355a35c4ac7433b2e87c93cff3816d8c6ba16`;
- company result SHA-256: Samsung
  `e1866d55ccc8e0eaf1461d69a2d4e5ce9fe325a17db60534d60cd7b55ea3baf7`,
  NAVER `c0b83cd3558b6b047562ea46042fe2a607dc89f6c5d405a37f7695bd56c7321c`,
  LGE `bfc05ce8b4bf24aa90ee2f3811669e06442ab48d055ff1cfc197a43161a48461`.

All raw outputs and heartbeats are ignored local artifacts. At this historical
checkpoint the exact-current canary superseded the previous clean five-row gate
and put integration on HOLD. The semantic source-scope successor recorded above
later closed the LGE correctness boundary; this section remains the failure
receipt rather than current authority.

## Late Numeric Surface And Clean Integration Gate (2026-08-26)

### Exact-Artifact Diagnosis

The remaining HYU/LGE scores were not treated as instructions to add runtime
vocabulary or benchmark-specific wording. Exact artifacts exposed two generic
ordering problems:

1. broad retrieved context could precede the final claim-scoped runtime evidence
   in evaluator inputs;
2. a late numeric-answer refresh could replace an already grounded answer and
   omit source-visible query terms preserved at an earlier boundary.

Focused LGE replay B at
`benchmarks/results/lge_t1_051_explicit_difference_term_preservation_replay_b_2026-08-26/`
kept numeric PASS, faithfulness/calculation/grounded rendering `1.000`, integrity
`ok`, and result `1,486,334백만원`, but completeness remained `0.700` because
`IRA` and `AMPC` disappeared from the final surface.

### Generic Contract Change And Focused Successor

- Evaluator context now prioritizes final claim-scoped runtime evidence before
  broad retrieval context with stable dedupe.
- Preferred complete numeric answers render explicit-role component differences
  from structured `minuend`, `subtrahend`, and `primary_value` slots.
- The central late numeric refresh reapplies
  `preserve_source_visible_query_terms(...)` against ordered results and evidence
  items. Unsupported terms are still not added.

Focused replay C at
`benchmarks/results/lge_t1_051_late_numeric_surface_preservation_replay_c_2026-08-26/`
preserved the deterministic result and added the grounded note
`원문 표기: IRA, AMPC.`. Completeness became `1.000`; numeric judgement was PASS,
final faithfulness/calculation/grounded rendering/context recall/hit@k were
`1.000`, integrity was `ok`, and two operands were resolved.

### Successor Full Gate

The same persisted-store, monitored `--eval-only` profile ran at
`benchmarks/results/integration_policy_gate_after_late_numeric_surface_preservation_2026-08-26/`.

- completed in `570.031` seconds;
- 4 / 4 companies, 5 / 5 questions, company pass count 4;
- full-eval fail count 0, runtime errors 0, integrity issues 0;
- aggregate faithfulness/completeness/context recall/numeric pass rate `1.000`;
- 52 LLM calls, 290,893 tokens, 46 query embeddings, zero document embeddings,
  estimated runtime LLM cost `$0.2595345`.

`LGE_T1_051` returned numeric PASS and preserved
`2,163,234백만원 - 6,769억원 = 1,486,334백만원` with `IRA`/`AMPC` visible.
`SAM_T2_078` retained canonical provenance
`연구개발비용 총계 / 28,352,769 / 백만원 / ev_001`. NAVER and both Hyundai rows
had final faithfulness, completeness, and context recall `1.000`, integrity
`ok`, and null errors. Numeric judgement remained correctly N/A for healthy
mixed/narrative rows.

The top result SHA-256 is
`2d786dd729b17b374681ad986250b72bca062093f626ebf9547822c366ad72b3`.
Company result hashes are NAVER
`c5d5ce8e8c5f2201d1d3e8990fabb4747065feb13ddb2fd1cd3fc6816e42bd8c`,
Hyundai `78e9ce1fe0b65968e1602396859d81c8df14bab49bc8f829984cd146b909a2f6`,
LGE `6f538a75edaccaf7f639b823610df9bbce3f2d565aecafadf3c0ef088046e7a9`,
and Samsung `7907dccb012ff88fd181f07b256a77f3bdc5f336f8011081b1068bd48c340f05`.

### Validation And Decision

- related evaluator/answer-surface tests: 498 / 498 passed;
- runtime-domain audit: 217 reviewed literals passed;
- full unittest discovery: 2,163 / 2,163 passed in `308.805` seconds.

This is current-agent/current-evaluator integration evidence over persisted
stores, not fresh-ingest or publishable held-out evidence. Raw results and
heartbeat logs remain ignored local artifacts. The bounded release gate is
closed; PR #86 remains draft, `main` is unchanged, and review must precede an
explicit history-preserving merge decision. Refactoring remains paused.

## Post-Gate Historical-Answer Compatibility Replay (2026-08-26)

### Setup

- The clean five-question provider gate had already completed before final diff
  review added duplicate-value source-row ambiguity rejection, complete-plan
  coverage for direct ledger operands, and deterministic rendering-authority
  protection.
- No provider, agent generation, DART fetch/parse/ingest, query embedding, or
  document embedding ran after those changes.
- A no-write replay loaded only the stored `SAM_T2_078` clean-gate answer and its
  runtime projection, then applied the current replay/evaluator contract.

### Result

- `numeric_equivalence = 1.000`
- `numeric_retrieval_support = 1.000`
- `grounded_rendering_correctness = 1.000`
- `calculation_correctness = 1.000`
- `numeric_grounding = null`
- final numeric judgement `UNCERTAIN`, warning
  `source_numeric_grounding_missing`

### Interpretation

- The stored answer remains compatible with current deterministic rendering and
  calculation contracts.
- The replay cannot establish current-agent source selection or a provider-backed
  pass, and its missing numeric-grounding field must not be silently imputed.
- The earlier clean gate remains the latest provider integration evidence and
  predates final defensive hardening. Runtime audit 217 and full unittest
  2,165/2,165 are the exact-current-source evidence at this checkpoint.

## Integration Store-Fixed Policy Gate (2026-08-25)

참조:

- benchmarked source/docs head: `672fc7f`
- profile: `benchmarks/profiles/curated_policy_driven_runtime_gate.json`
- source store bundle:
  `benchmarks/results/policy_gate_regression_2026-06-03_1138_actual/`
- ignored local output bundles:
  - `benchmarks/results/integration_policy_gate_2026-08-25_672fc7f/`
  - `benchmarks/results/integration_policy_gate_recheck_2026-08-25_672fc7f/`
- top-level `results.json` SHA-256:
  - main run:
    `3ea8064a1e82fbeae0e50594757bccff6bbe4290adafcd026fea72a4b9f8544d`
  - focused rechecks:
    `3930ff87972af74ed921b3bb2d18b58d115b8d37508f584e9f0cb140fc030a45`
- artifact hygiene: raw results and heartbeat logs are local-only and were not
  staged.

### Admission And Execution

- The current profile exactly matched the source bundle's recorded defaults,
  screening config, full-evaluation config, experiment list, and company ids.
- All four persisted Chroma indexes passed strict vector-search health probes.
- Focused benchmark-runner/eval-only/resumable-store contracts passed 46/46
  before provider work.
- The monitored run reused the existing stores but reran the current
  `FinancialAgent` and evaluator. Historical answers were not replayed, and no
  DART parse, fetch, or ingest ran.
- The main run completed four companies and five questions in 670.4 seconds
  with error rate `0.0%`. Two failed-row confirmations added two question
  executions. Across all seven question executions, recorded runtime LLM cost
  was `$0.4344568`; embedding cost was not reported.

### Results

| Question/surface | First run | Focused confirmation | Interpretation |
| --- | --- | --- | --- |
| `HYU_T2_010`, `HYU_T3_072` | faithfulness/completeness `1.000 / 1.000`, error `0.0%` | not rerun | clean comparison/control rows |
| `LGE_T1_051` | numeric `PASS`, faithfulness `1.000`, completeness `0.500` | not rerun | numeric value was accepted, but the absolute result was rendered as `1,486,334백만원 상승했습니다` |
| `NAV_T2_006` | answer `17.6%`, faithfulness `0.300`, completeness `0.500` | answer `41.4%`, faithfulness/completeness/calculation `1.000 / 1.000 / 1.000` | correct lookup task outputs existed in both runs, but the first final trace replaced them with a different MDA pair |
| `SAM_T2_078` | final answer `28,352,769백만원`, structured lookup `28,339,724백만원`, calculation `0.000` | trace converged to `28,352,769백만원`, calculation `1.000` | final-answer/structured-trace stability gap; metadata-style prefix still leaked into the narrative |
| Samsung refusal metric | `0.000` | `0.000` | evaluator false positive: substring marker `없` matched inside `끊임없는` |

The first NAVER run's retrieved evidence explicitly contained source-stated
`41.4%`, and its lookup subtasks returned `2,546,649백만원` and
`1,801,079백만원`. The final resolved trace nevertheless selected
`9,670.6억원` and `8,220.1억원` from a different MDA surface and calculated
`17.6%`. The focused rerun retained the task-output pair and produced `41.4%`.
This is an operand/final-projection stability problem, not a retrieval miss or
an evaluator-only fluctuation.

### Release Interpretation

- This refresh closes the previous "benchmark not run" evidence gap, but it is
  **not** a release pass and does not support a new quality claim.
- The failure layers are generic contracts: candidate/task-output precedence,
  aggregate subtraction rendering, final-answer/structured-trace coherence,
  answer-text cleanup, and evaluator marker boundaries.
- No company name, benchmark id, metric-specific runtime branch, or answer-key
  patch is justified.
- PR #86 remains draft. Close the generic contracts with focused tests, rerun
  the affected rows, and then repeat the same five-question store-fixed gate
  before considering integration.

## NAV Focused Stability And Evaluator Role Split (2026-08-25)

참조:

- source store bundle:
  `benchmarks/results/policy_gate_regression_2026-06-03_1138_actual/`
- ignored provider-backed focused bundles:
  - `benchmarks/results/nav_t2_006_segment_binding_replay_a_2026-08-25/`
  - `benchmarks/results/nav_t2_006_segment_binding_replay_b_2026-08-25/`
- ignored no-call replay summaries:
  - `benchmarks/results/nav_t2_006_evaluator_role_split_replay_a_2026-08-25/`
  - `benchmarks/results/nav_t2_006_evaluator_role_split_replay_b_2026-08-25/`

### Runtime Result

Both monitored, store-fixed provider replays skipped DART parse/fetch/ingest
and reran the current agent/evaluator over `NAV_T2_006`. Both runs retained:

- `binding_policy.segment_label = "커머스"`;
- current/prior slots `2,546,649 / 1,801,079백만원` from `ev_001`;
- formula result `41.39574110852439%`, rendered as `41.4%`;
- `final_answer_surface_trace_sync = true`;
- no promotion of the retrieved total-MDA `9,670.6 / 8,220.1` pair into the
  final answer or resolved calculation trace.

The selected numeric trace fingerprint was byte-identical at
`bca90ad7c72c979477c36f81eefc8c2ff499e552c9df9766cfdd6b05d7130993`.
The two runs recorded 26 LLM calls, 152,096 total LLM tokens, and `$0.1454758`
combined runtime cost. Embedding cost was not reported.

### Evaluator Finding And Role Split

The first run returned grounded rendering/calculation correctness `1.000 /
1.000`. The second had the same correct trace but returned `0.000 / 0.000`
because the LLM rendering judge interpreted the requested acquisition and
integration narrative as forbidden non-numeric content. That verdict
contradicted both the question and the metric's intended numeric-only scope.

Grounded rendering no longer calls an LLM. It now extracts amount, count,
ratio, and percentage surfaces from the answer and deterministically checks
equivalence, display rounding/unit conversion, or permitted derivation against
the canonical calculation trace and current runtime evidence. Non-numeric
narrative is ignored by this metric. Semantic trend judgement remains a
separate score and is no longer averaged into `calculation_correctness`.
Historical replay recomputes the current deterministic rendering score while
retaining the source artifact's saved score for audit.

No-call replay over the exact two provider artifacts produced grounded
rendering/calculation correctness `1.000 / 1.000` for both rows. Focused
evaluator/benchmark contracts passed `114/114`, runtime-domain audit passed at
`217`, and full unittest passed `2,151/2,151` in `246.268` seconds. No provider
run was made after the evaluator change, and no remote CI, commit, push, PR
update, merge, tag, or experiment artifact publication occurred. The full
four-company/five-question release gate remains pending after LGE and Samsung
closure.

## LGE Absolute Difference Semantics Closure (2026-08-25)

참조:

- source store bundle:
  `benchmarks/results/policy_gate_regression_2026-06-03_1138_actual/`
- ignored provider-backed focused bundle:
  `benchmarks/results/lge_t1_051_difference_semantics_replay_2026-08-25/`
- top-level `results.json` SHA-256:
  `a1c4a4f73c1b059021d5857b22cd7d36bcb4a6875b9d6d15cbd4695280d2e9ba`
- company `results.json` SHA-256:
  `9f0884df297b2436da9413858fc84b39792cb942dd99fa3f88862203d154aa18`

```powershell
uv run --with-requirements requirements.txt python -m src.ops.benchmark_runner `
  --config benchmarks/profiles/curated_policy_driven_runtime_gate.json `
  --output-dir benchmarks/results/policy_gate_regression_2026-06-03_1138_actual `
  --eval-output-dir benchmarks/results/lge_t1_051_difference_semantics_replay_2026-08-25 `
  --company-run-id lge_2023_policy_driven_runtime_gate `
  --eval-only `
  --question-id LGE_T1_051 `
  --progress-heartbeat-sec 30 `
  --heartbeat-log benchmarks/results/lge_t1_051_difference_semantics_replay_2026-08-25/_logs/heartbeat.jsonl
```

### Failure Classification And Contract Change

The source operands and arithmetic were correct before this change:
`2,163,234백만원 - 6,769억원 = 1,486,334백만원`. The failure was in generic
answer-slot semantics. Every `difference` had been projected as though it were
a current/prior comparison, so a positive component-subtraction result could be
rendered as an amount that rose.

Fresh difference slots now carry explicit `result_semantics`. A complete
`current_period` plus `prior_period` role pair becomes `period_delta`; a
`minuend` plus `subtrahend` subtraction becomes `derived_value`. Derived rows
expose a primary result and no synthetic current/prior slots or direction.
Explicit semantics takes precedence over legacy aggregate aliases, while older
traces remain structurally readable. This is generic execution policy; no LGE,
benchmark-id, IRA/AMPC, or metric-specific runtime branch was added.

### Focused Provider Result

The monitored eval-only run reused the existing LGE store, reran the current
agent/evaluator for only `LGE_T1_051`, and performed no DART parse, fetch,
ingest, or historical-answer replay. The calculation subtask recorded:

- `result_semantics = derived_value`;
- component roles `minuend` and `subtrahend`;
- `primary_value = 1,486,334백만원` and `direction = null`;
- final answer surface
  `이를 제외한 실질 영업이익은 1,486,334백만원입니다.`

It returned numeric `PASS`; faithfulness, completeness, context recall,
retrieval hit@k, grounded rendering, and calculation correctness were all
`1.000`; error rate was `0.0%`; average score was `0.937761`.
`numeric_result_correctness` and `trend_interpretation_correctness` were null as
not-applicable, not failures. The question took `63.605` seconds. The complete
run recorded 9 LLM calls, 45,848 LLM tokens, 5 query-embedding calls, and
`$0.0478852` estimated runtime cost; embedding cost was not reported.

### Validation And Scope

Focused answer-slot/operation tests passed `260/260`; the expanded related
regression set passed `829/829`; runtime-domain audit passed at `217`; pycompile
passed; and full unittest passed `2,153/2,153` in `227.030` seconds. The focused
bundle and heartbeat remain ignored local artifacts and were not staged. No
remote CI, commit, push, PR update, merge, tag, or artifact publication ran.
This closes LGE only at the focused level; Samsung cleanup and a fresh full
four-company/five-question gate remain before integration.

## Samsung Semantic Row And Release-Gate Follow-up (2026-08-26)

참조:

- source store bundle:
  `benchmarks/results/policy_gate_regression_2026-06-03_1138_actual/`
- ignored provider-backed Samsung bundles:
  - `benchmarks/results/sam_t2_078_semantic_row_selection_replay_b_2026-08-26/`
  - `benchmarks/results/sam_t2_078_semantic_row_selection_replay_c_2026-08-26/`
- ignored full-gate bundle:
  `benchmarks/results/integration_policy_gate_after_samsung_semantic_selection_2026-08-26/`
- ignored LGE successor:
  `benchmarks/results/lge_t1_051_derived_value_one_way_replay_2026-08-26/`
- all raw results and heartbeat logs remain local-only and unstaged.

### Failure Classification

The Samsung source table contained several close numeric rows:
`연구개발비용 총계`, `연구개발비용 계`, and `연구개발비(비용)`. Retrieval
already carried the relevant table. The defect was semantic selection and later
projection, not parser or ingest:

1. deterministic coarse lookup could guess among multiple material rows;
2. the chosen source row was not always the final structured lookup authority;
3. final prose could reverse-sync a different amount into the lookup trace;
4. a structural zero-cost prefix could leak into narrative output;
5. evaluator substring matching treated `없` inside `끊임없는` as refusal.

The generic change lets the LLM explicitly select a reconciliation candidate or
return ambiguous, then requires deterministic period/value/unit/source
validation. Multi-row coarse lookup refuses to guess. Source row -> canonical
lookup slot -> final answer is one-way for lookup results. Prefix removal is
policy-driven and preserves source headings such as `[Harman]`; refusal markers
are phrase-boundary aware. No company, question id, row label, or target number
was added to runtime control flow.

### Focused Samsung Replays

Both monitored runs used the same persisted Samsung store and current
agent/evaluator. They performed no DART fetch, parse, ingest, or document
embedding. The runs were intentionally repeated to test semantic-selection
stability rather than tune a single artifact.

| Signal | Replay B | Replay C |
| --- | ---: | ---: |
| faithfulness | 1.000 | 1.000 |
| completeness | 1.000 | 1.000 |
| refusal accuracy | 1.000 | 1.000 |
| grounded rendering / calculation | 1.000 / 1.000 | 1.000 / 1.000 |
| context recall | 0.800 | 1.000 |
| question latency | 67.556 s | 64.655 s |
| LLM calls / tokens | 9 / 40,752 | 9 / 39,089 |
| query / document embedding calls | 6 / 0 | 6 / 0 |
| estimated runtime LLM cost | `$0.0435822` | `$0.0396073` |

Both answers were byte-identical at 377 characters. Both selected exact source
row `연구개발비용 총계 | 제55기 | 28,352,769 | 백만원`, canonical operand
`28,352,769백만원`, normalized value `28,352,769,000,000 KRW`, source row
`ev_001`, and the same source anchor. Both numeric-extraction fingerprints were
`de311d9fa0818ca04bacad873ee16ad8dda94633ee3296287722cd64a7067c08`.
`numeric_final_judgement=null` is expected for this mixed numeric+narrative row;
the grounded calculation and rendering metrics passed.

SHA-256 receipts:

| Bundle | top-level `results.json` | company `results.json` |
| --- | --- | --- |
| replay B | `99df917f18465517f857596bd7bf3e3641d2166cc802b05fd5857e7df946acaf` | `a4249b0297aa492942c9a85d5c3930aa2f52f9cd577b2fe72c59b25e8a9d9d6c` |
| replay C | `7708ed528548dd0f95aaf8157b92be5193168be7dd84b54ffebf24909bafc435` | `517af35227a68f714e525ee07aaf48c758ac49b19b17f7c0601214fdcf16e07e` |

### Full Store-Fixed Gate

```powershell
uv run --with-requirements requirements.txt python -m src.ops.benchmark_runner `
  --config benchmarks/profiles/curated_policy_driven_runtime_gate.json `
  --output-dir benchmarks/results/policy_gate_regression_2026-06-03_1138_actual `
  --eval-output-dir benchmarks/results/integration_policy_gate_after_samsung_semantic_selection_2026-08-26 `
  --eval-only `
  --progress-heartbeat-sec 30 `
  --heartbeat-log benchmarks/results/integration_policy_gate_after_samsung_semantic_selection_2026-08-26/_logs/heartbeat.jsonl
```

The current agent/evaluator completed 4/4 companies and 5/5 questions in 747.5
seconds with error rate `0.0%`. It reused persisted stores, made 46 query and
zero document embedding calls, and did not run fresh DART fetch/parse/ingest.
Recorded usage was 62 LLM calls, 246,506 prompt plus 107,508 output tokens
(354,014 total), estimated runtime LLM cost `$0.3427218`.

Aggregate metrics were faithfulness `0.9125`, completeness `0.8375`, context
recall `0.9500`, numeric pass `1.000`, and `full_eval_fail_count=2`.

| Row | Result | Interpretation |
| --- | --- | --- |
| `SAM_T2_078` | same byte-identical answer and fingerprint; faithfulness/completeness/refusal/grounded rendering/calculation `1.000`; error 0 | Samsung closure reproduced in the full gate |
| `NAV_T2_006` | correct `41.4%`, but task-artifact integrity `error`; latency 272.587 s | `operands:task_1:003` recorded empty `calculation_operands`, causing two recovery replans |
| `HYU_T2_010` | correct 11.5% answer; faithfulness/completeness `0.300 / 0.700` | direct runtime evidence supports the answer; treat as evaluator-variance candidate until exact-artifact diagnosis, not runtime patch authority |
| `HYU_T3_072` | faithfulness/completeness `1.000 / 1.000` | control stayed stable |
| `LGE_T1_051` | numeric PASS, faithfulness 1.000, completeness 0.500 | top result remained 1,486,334백만원, but terse wording and final-prose reverse sync corrupted the nested derived row to 6,769억원 |

The top-level and Samsung company SHA-256 receipts are
`fc23d30421fe521c86c2e5fba896e66afff30967d12de43beb60fbfb48acfe26`
and `f442b6c9c1bf4c741216427f7403c711f0e86cc9edcb9db465295e667ed4432c`.
The run is **not** a release pass.

### Derived-Value One-Way Successor

The full gate showed that the older arithmetic surface synchronizer ignored the
fresh `result_semantics=derived_value` contract. A bounded generic guard now
excludes only explicit derived-value differences from final-prose numeric
reverse synchronization. Period delta, ratio, growth, and sum paths are
unchanged.

A monitored LGE successor reused the same store and repeated the exact terse
final answer. The nested difference result, primary slot, and top result all
remained `1,486,334백만원`; `projection_surface_synced_from_final_answer` was
absent. Numeric judgement PASS, faithfulness/grounded rendering/calculation
`1.000`, error `0.0%`; completeness remained `0.500`, so no benchmark-keyed
wording patch was made. The run recorded 9 LLM calls, 44,095 tokens, 5 query and
zero document embeddings, `$0.0418109` estimated runtime LLM cost. Top/company
SHA-256 receipts are
`a62d020d9616d772423d0e0917307f106340f903980b6e8fb3225a7711eaf478`
and `f8167ce1f212a99cd8358b9c54d05ba047bf83be65c1b4656f7a3c09936bcaae`.

### Decision

- Samsung semantic selection, lookup provenance, prefix cleanup, and evaluator
  marker boundaries are closed at focused and full-gate levels.
- Explicit derived-value trace reverse synchronization is focused-closed after
  the full-gate finding.
- Integration remains on HOLD. The next section records the NAVER operand-
  artifact successor; qualitative HYU/LGE scoring still requires diagnosis
  without company/question-specific tuning, followed by another monitored
  five-question gate.

## NAV Dependency Operand-Artifact Successor (2026-08-26)

참조:

- source store bundle:
  `benchmarks/results/policy_gate_regression_2026-06-03_1138_actual/`
- first focused diagnostic:
  `benchmarks/results/nav_t2_006_operand_artifact_finalization_replay_2026-08-26/`
- current focused successor:
  `benchmarks/results/nav_t2_006_operand_artifact_finalization_replay_b_2026-08-26/`
- all raw results and heartbeat logs remain ignored local artifacts.

### Failure Classification

The first diagnostic reproduced the full-gate split: operand extraction emitted
zero rows, deterministic execution still calculated `41.4%`, and the result
artifact was correct, but `operands:task_1:003` remained empty. Integrity then
reported `missing_required_artifact_payload` and triggered recovery replans. The
defect was the provisional operand artifact's finalization timing, not retrieval,
semantic label choice, arithmetic, or evaluator scoring.

The generic closure finalizes an already attached operand artifact only from a
successful calculation result whose task-owned input slots cover every plan
operand id and preserve numeric/source provenance. Artifact id, ledger order,
task attachment, and artifact count remain unchanged. Missing artifacts,
incomplete plan coverage, unprovenanced slots, final prose, and the calculated
primary output cannot close the contract.

### Focused Comparison

Both monitored runs reused the same persisted 1,837-document NAVER store and
made no DART fetch, parse, ingest, or document embedding calls. Both reproduced
`coverage=sufficient operands=0` before deterministic `41.4%` execution.

| Signal | First diagnostic | Current successor |
| --- | ---: | ---: |
| task-artifact integrity | `error`, 1 issue | `ok`, 0 issues |
| operand artifact | 0 operands, no refs | 2 finalized operands, `ev_001` |
| recovery replan | present | absent |
| question latency | 268.740 s | 129.626 s |
| agent LLM calls / tokens | 21 / 126,829 | 11 / 70,923 |
| estimated runtime LLM cost | `$0.1366214` | `$0.0744392` |
| query / document embeddings | 8 / 0 | 8 / 0 |
| faithfulness / completeness / calculation | 1.000 / 1.000 / 1.000 | 1.000 / 1.000 / 1.000 |

The current successor's top/company SHA-256 receipts are
`b1a0748557cbb8405055ad9aacce7afc40738d61d8b47502cbfe49abbcd6f078`
and `be3f09147e9c592d86e1fcbbe0ac55a516df6f7e50a6116bf4421079a0b901c7`.
`numeric_final_judgement=null` remains N/A for the mixed row.

### Validation And Decision

- Runtime audit: 217 reviewed literals passed.
- Focused subtask/aggregate projection: 381/381 passed.
- Full local unittest: 2,160/2,160 passed in 316.697 seconds.
- NAVER's hard ledger defect is focused-closed without benchmark- or
  company-specific runtime vocabulary.
- Integration remains on HOLD. Diagnose HYU/LGE qualitative residuals from
  their exact artifacts, then rerun the same monitored five-question gate.

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

참조: 이 초기 raw artifact는 현재 published evidence surface에 포함하지 않는다.

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

- [graph_micro_2026-04-22/cross_company_summary.md](../../benchmarks/results/graph_micro_2026-04-22/cross_company_summary.md)
- [graph_micro_constrained_2026-04-22/cross_company_summary.md](../../benchmarks/results/graph_micro_constrained_2026-04-22/cross_company_summary.md)
- [graph_micro_prefix_2026-04-22/cross_company_summary.md](../../benchmarks/results/graph_micro_prefix_2026-04-22/cross_company_summary.md)

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

- [dev_fast_cache_check_2026-04-17/삼성전자-2024/summary.md](../../benchmarks/results/dev_fast_cache_check_2026-04-17/삼성전자-2024/summary.md)
- [dev_fast_cache_check_2026-04-17/삼성전자-2024/review.md](../../benchmarks/results/dev_fast_cache_check_2026-04-17/삼성전자-2024/review.md)

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

## Routing Dataset Ownership And Leakage Boundary (2026-08-07)

### Context

- Runtime canonical queries were stored under `benchmarks/golden`, which made
  the default router depend on an evaluation-owned path.
- One query in `query_routing_eval_v1.json` later became an exact member of the
  risk canonical set. The historical 2026-04-24 calibration therefore remains
  reproducible, but its v1 accuracy is not a clean held-out claim against the
  current canonical set.

### Code / Contract Change

- Moved canonical v1 unchanged to `src/config/query_routing_canonical_v1.json`.
- Preserved `query_routing_eval_v1.json` as the historical calibration input.
- Added disjoint `query_routing_eval_v2.json` and made it the calibration
  default.
- Added a contract for the runtime config path, environment override, 30 unique
  v2 queries, and normalized exact disjointness between canonical and v2.

### Interpretation

- This is a runtime/evaluation ownership and dataset-leakage correction, not a
  routing score improvement claim.
- No new calibration result was produced. Historical v1 metrics must not be
  presented as v2 metrics or as clean held-out performance against the current
  canonical set.

## HYU T3 Source-Basis Dataset Correction (2026-09-03)

- The immutable source review established one complete consolidated Motional
  tuple: `26%`, `700,691백만원`, and the four table-90 summary measures.
- The curated key and raw required-keyword checkpoint were corrected to that
  basis. Historical benchmark bundles were not edited.
- Provider-free reprojection confirmed that the source-defined summary cohort
  now preserves all four policy-defined cells from table 90 row `21:4`.
- This was a source, contract, and dataset-governance follow-up. It did not run
  a provider, ingest documents, mutate a store, or create a new benchmark
  score.

## Semantic Tie-Break Context V4 Review (2026-09-04)

- Original-filing review labeled atomic A/C/E ties and confirmed that the T3
  ownership-share choice should be resolved by `당기` versus `전기`, not by a
  semantic model.
- Candidate reprojection now preserves parser-owned period role, period labels,
  value year, and bounded table context. Candidate IDs and all three saved
  catalog fingerprints remain unchanged.
- Exporter v2 produced 3 atomic cohorts / 7 pairs and excluded 4
  source-defined output/requirement cohorts from top-one labeling.
- The cached local sigmoid gate kept top-1 at `1.0`, made 1/3 confident
  selections, produced zero confident errors, and measured warm CPU p95 about
  `739 ms`. Status remains `needs_review` because baseline top-1 is also `1.0`
  and confidence coverage is below policy.
- This run was provider-free and store-fixed. It did not perform ingest, mutate
  a store, enable the runtime feature, or create a benchmark/release claim.

## Candidate Fact-Role Projection V1 (2026-09-05)

- Added immutable `CandidateFactRoleV1` and `CandidateSemanticRoleV1` contracts.
  Each projection stays bound to one candidate ID, preserves table/row/cell and
  verified source-span provenance, and rejects semantic surfaces absent from the
  exact candidate source.
- Structured tables project parser-owned subject/relation, statement type,
  polarity, period, and value role. Prose candidates remain `unresolved` until a
  separately produced semantic role is source-grounded. Candidate IDs, catalogs,
  stores, and historical result bundles were not rewritten.
- Rebuilt the provider-free v5 packet as 6 cohorts / 34 candidates, fingerprint
  `4a5d2858...cd1`. The transferred human fixture contains 4 select cases / 22
  candidates and is byte-stable at `f8a38cd5...6efb1` across two builds.
- The reviewed KBF negative income-statement cells now differ structurally from
  signless positive cash-flow adjustments. LGE's AMPC component and reported
  operating-profit total remain unresolved because both originate in prose.
- Feeding all deterministic structural fields to the cached cross-encoder made
  quality worse (`0/4`), so only an explicit semantic-grounded role may augment
  model text. With no such roles, v5 preserves the prior model scores: `1/4`
  against baseline `3/4`, gain `-0.50`, four abstentions at margin `0.05`, and
  warm CPU p95 `2715.932 ms`. Runtime activation remains off.
- An exact-surface-first matching experiment reduced apparent ambiguity but
  displaced accepted Samsung evidence. It was reverted rather than becoming a
  keyword precedence rule.
- No provider, network benchmark, ingest, store mutation, or paid retry ran.
  The next bounded experiment is an evaluation-only prose semantic-role
  interpreter; persisted fact indexing remains a separate versioned migration.

## Bounded Prose Semantic-Role Interpreter Harness (2026-09-05)

- Added an evaluation-only request/response contract and provider-neutral
  structured-output adapter. It groups all unresolved numeric candidates from
  one exact source, omits the user query and acceptable IDs, and caps source,
  candidate, and request counts.
- Response projection requires the exact request/source fingerprints, every
  visible candidate ID, source-grounded subject/relation surfaces, and a relation
  containing the candidate's own displayed value. Invalid or non-unique value
  localization does not gain a role or runtime authority.
- The current reviewed fixture yields one request with two LGE sentence values.
  The human response labels the operating-profit figure as `reported_total` and
  the tax-credit figure as `adjustment_component`. Its 2/2 gate is an oracle
  plumbing self-check, not a model-accuracy result.
- Grounded prose roles now replace noisy heuristic prose subjects rather than
  merging with them. Focused contracts passed before rescoring.
- The cached local cross-encoder still preferred the reported total after this
  cleanup. Overall top-1 stayed `1/4` against baseline `3/4`, all four cases
  abstained at margin `0.05`, and warm CPU p95 was `2801.287 ms`. Further tuning
  of that scorer stopped.
- No provider, ingest, store mutation, benchmark, or runtime activation occurred.
  The next possible action is one separately approved structured-output model
  call on the exact request, followed by the reviewed role gate.

## Source-Local Prose Role Boundary (2026-09-05)

- Admission `729d1f53...4b93` was consumed exactly once on commit `189236a`.
  Gemini 2.5 Flash made one structured-output call with 389 input and 162 output
  tokens (551 total). Repository pricing estimated USD `0.0005217`, below the
  approved USD `0.02` ceiling. There was no provider retry.
- Both candidates were source-grounded. The operating-profit value matched
  `reported_total`; the tax-credit value was returned as `component`, while the
  predecessor oracle expected `adjustment_component`. That original comparison
  was therefore `1/2`.
- Review found that `adjustment_component` had encoded how a later question uses
  the value, information intentionally absent from the model request. The source
  states a component; exclusion is owned by semantic-program AST and binding.
  The immutable provider response matches the corrected successor review `2/2`.
- The source-role vocabulary now rejects task-relative operand use. This result
  does not enable the tie-breaker, change candidate visibility, mutate a store,
  or establish held-out model quality. More prose cases must be reviewed
  provider-free before another model request is proposed.

## Source-Bundle Compiler Three-Question Gate (2026-09-05)

- Admission `24322d93...9aaf` was consumed exactly once at commit `5c4c796`.
  The store-fixed eval-only runner completed in `339.1s` with exit code zero and
  no runner retry. It made 18 LLM calls over 129,656 tokens and 33 query
  embedding calls; document-embedding calls were zero. The recorded
  non-embedding estimate was USD `0.1187678`, below the USD `0.40` ceiling.
- Original company result files, SQLite files, and complete store fingerprints
  matched the manifest after execution. No disposable eval store remained.
  Root result SHA-256 is `05550b8b...596a0`; ignored run receipt SHA-256 is
  `dbbe71b6...10584`.
- `HYU_T2_010` completed with ledger `ok`, selected `87.0` and `78.1`, and
  validated exact sentence assertions. Although `11.5%` was visible in the same
  source bundle, the compiler did not bind it as the source display and the
  answer rendered the recomputed `11.4%`. Faithfulness was `0.7` and
  completeness `1.0`.
- `HYU_T3_072` passed without compiler retry. Ownership `26%` and carrying value
  `700,691백만원` came from table 82 row `9:2`; four summary profit/loss values
  came from table 90 row `21:4`; no BHAF `53%` candidate was selected.
  Faithfulness and completeness were both `1.0`.
- `SAM_T2_078` first selected the accepted `28,352,769백만원` candidate
  `cand_27da082cf5bcd0cb9f27`. Validator rejected obligation
  `display_unit=KRW` with `direct_result_unit_mismatch`; retry then promoted a
  different bundle and produced `non_derived_obligation_has_expression`.
  Numeric obligation `ob_001` remained missing, while the Harman narrative and
  ledger were valid. Completeness was `0.5`.
- Release is `HOLD`: mechanical runtime completeness `2 / 3`, reviewed
  source-consistent acceptance `1 / 3`. The admission is exhausted. Next work
  is provider-free unit-boundary and source-display contract repair; no paid
  retry is authorized.

## Runtime Repair Failed-Row Provider Retry (2026-09-05)

- Runtime-contract repairs were first exercised by admission
  `45ef0f6e...4f03`. T3 passed, while T2 and Samsung failed on Google query-
  embedding `429 RESOURCE_EXHAUSTED`. Follow-up admission
  `da9cd31e...0acf` therefore bound the immutable T3 artifact and selected only
  `HYU_T2_010` and `SAM_T2_078`.
- The approved follow-up runner executed once on `e3ee77f` in `187.253s` and
  exited zero. It performed no fresh fetch, ingest, document embedding, source
  mutation, or runner retry. Original result/SQLite hashes and complete store
  fingerprints stayed unchanged; no disposable eval store remained.
- Samsung completed both obligations without semantic retry. It selected
  `cand_27da082cf5bcd0cb9f27` from the `연구개발비용 총계` row, preserved
  `28,352,769백만원`, and grounded the Harman narrative in two sources. Runtime
  error was zero, ledger was `ok`, and faithfulness, completeness, grounded
  rendering, and calculation were all `1.0`.
- T2 again received a fatal Google query-embedding `429` during retrieval after
  planning and before semantic compilation. This is unavailable provider
  capacity evidence, not a source-display, validator, or executor result.
- The follow-up artifact accounts for Samsung only: 6 LLM calls / 41,405 tokens,
  10 query-embedding calls, and USD `0.0448187` non-embedding estimate. Failed-
  path calls and embedding pricing are not recorded, so exact total cost is
  unavailable. Root result SHA-256 is `d30a321c...422fd`; ignored receipt is
  `0fefdb88...9ac27`.
- With immutable same-runtime T3 carried forward, the combined runtime gate is
  `2 / 3`; release remains `HOLD`. The approval is consumed. Repeating the
  unchanged provider run is not authorized and would not address the remaining
  Google query-embedding capacity boundary.

## OpenAI-Store T2 Replay And Planner Null Boundary (2026-09-05)

- Admission `9bdd8db4...30fe3` was consumed exactly once on commit `b29b239`.
  The store-fixed eval-only runner completed in `93.657s` with exit code zero,
  30-second heartbeats, and no automatic retry. It made no fetch, parse, ingest,
  document-embedding, or source-store mutation.
- OpenAI `text-embedding-3-large` handled all 11 query embedding calls without
  the earlier Google capacity error. The source directory fingerprint remained
  `6231cd8e...24e9`; no disposable eval store remained.
- Numeric `ob_001` completed on the first compiler attempt. It selected
  `cand_7d5294a9fe110c3e987f` (`87.0만 대`) and
  `cand_2edd04c9130daab86745` (`78.1만 대`), preserved source display candidate
  `cand_47bfc4cc05d682154cfa` (`11.5%`), and separately rendered the calculated
  `11.395646606914212` as `11.4%`. Both prose assertions validated.
- Narrative `ob_002` had six visible candidates, including one explicitly
  compatible candidate, but did not reach the compiler. The planner returned
  optional fields as literal strings (`display_unit`, `display_format`, and
  `coupling_key` were `"null"`); unit preflight classified the display value as
  `invalid_obligation_unit` and blocked that island with zero prompt bytes.
  This is a typed planner-projection defect, not retrieval or ranking evidence.
- The result is partial with runtime error `0`, ledger `ok`, and evaluator
  faithfulness/completeness `0.5 / 0.5`. Usage was 5 LLM calls / 34,430 tokens,
  11 query / 0 document embedding calls, with a USD `0.0379082` local
  non-embedding estimate. Actual billing and embedding cost are unavailable.
  Root result SHA-256 is `8aac48c7...32b69`; ignored run receipt SHA-256 is
  `86d21248...ead74`.
- Generic successor `bacb9c2` normalizes exact serialized absence sentinels only
  for optional planner display/coupling text. Existing unsupported-unit failure
  remains covered. Planner 4/4, semantic integration 101/101, import/topology
  28/28, runtime audit 84, pycompile, diff check, and full unittest 877/877 pass.
  No provider call followed the fix. The admission is exhausted and release
  remains `HOLD` at combined same-runtime completeness `2 / 3`.
- Provider-free successor admission `6659d803...27ed5` binds the fixed HEAD and
  same immutable OpenAI store. Two production-order rehearsals produced identical
  7,632-byte receipts at `9cd6616e...8fa3`; no target or provider call was made.

## Optional-Null Successor T2 Replay And Dependency Projection Boundary (2026-09-05)

- Exact admission `640ef7be...986c` was consumed once on clean commit `145982f`.
  The store-fixed `HYU_T2_010` process exited zero in `79.721s` with 30-second
  heartbeats and no runner retry, fetch, parse, ingest, document embedding, or
  source-store mutation.
- OpenAI completed all 11 query embedding calls. The optional-null repair worked:
  narrative `ob_002` had blank optional display/coupling fields, compiled once,
  selected `cand_bbd863eb396fa724d814`, and produced the source-supported policy
  response without an internal retry.
- Numeric `ob_001` never reached the compiler. Its planner output declared raw
  evidence requirements `us_sales_2023` and `us_sales_2022`, then also copied
  those names into `depends_on`. Runtime projection assigned stable requirement
  IDs, so compilation-island preflight correctly rejected both stale names as
  unknown answer-obligation dependencies. Numeric call count and prompt bytes
  were both zero despite visible candidate cohorts.
- The result is partial with runtime error `0`, ledger `ok`, completeness `0.5`,
  faithfulness `0.0`, and no numeric operands resolved. Usage was 5 LLM calls /
  26,782 tokens and 11 query / 0 document embedding calls. Recorded
  non-embedding cost is USD `0.0285496`; actual provider billing and embedding
  cost remain unavailable.
- Source fingerprint stayed `6231cd8e...24e9`; no disposable store remained.
  Root result SHA-256 is `d86b650c...3040`, company result SHA-256 is
  `6b56ab5a...26a8`, and ignored receipt SHA-256 is `859a2483...021f`.
- Generic successor `af9a07e` reserves `depends_on` for other answer obligations
  and removes only exact references to the current obligation's evidence inputs.
  Known other answer dependencies take precedence; unknown and self references
  remain fail-closed. Planner 5/5, semantic contracts 164/164, import/topology
  28/28, runtime audit 84, pycompile/diff checks, and full unittest 878/878 pass.
  No provider call followed the fix. The admission is exhausted; any confirmation
  run requires a new exact clean-HEAD manifest and separate egress/cost approval.

## Dependency-Projection Successor T2 Provider Pass (2026-09-05)

- Admission `0f0c0d52...0445` was consumed exactly once on clean commit
  `58551c7`. The store-fixed `HYU_T2_010` run exited zero in `118.936s`; no
  process retry, fetch, parse, ingest, document embedding, or source mutation
  occurred.
- Both compilation-island preflights had no errors. Numeric `ob_001` selected
  `cand_7d5294a9fe110c3e987f` (`87.0만 대`),
  `cand_2edd04c9130daab86745` (`78.1만 대`), and source display
  `cand_47bfc4cc05d682154cfa` (`11.5%`). The deterministic result
  `11.395646606914212` was separately rendered as `11.4%`.
- The numeric island's first compiler output had malformed source-assertion
  coverage. Its one allowed internal retry kept the same nine visible candidates
  and succeeded; the narrative island was not retried. Narrative `ob_002`
  selected `cand_bbd863eb396fa724d814`. Final program status was ready with two
  outputs, four selected candidates, and no missing obligations.
- Runtime error is `0`, ledger is `ok`, and evaluator faithfulness/completeness,
  context recall, retrieval hit@k, and citation coverage are all `1.0`.
  `numeric_final_judgement=null` is N/A for this mixed question rather than a
  runtime failure.
- Usage was 7 total LLM calls / 71,359 tokens and 11 query / 0 document embedding
  calls. Recorded non-embedding cost is USD `0.0664263`; actual provider billing
  and embedding cost are unavailable.
- Source-store fingerprint remained `6231cd8e...24e9`; no disposable store
  remained. Root result SHA-256 is `a765a132...0ad9`, company result SHA-256 is
  `34cb821b...a310`, and ignored run receipt SHA-256 is `4dd004f2...a3b4`.
- Combined with manifest-bound immutable T3 and Samsung successes, the specified
  source-consistent runtime release gate is `3 / 3 PASS`: all questions complete,
  runtime error zero, and ledger `ok`. Dataset/evaluator governance for T3 and
  formula-wide rounding propagation remain separate. The approval is exhausted;
  no further provider retry is authorized or required for this gate.
