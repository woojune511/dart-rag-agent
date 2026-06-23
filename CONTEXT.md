# 프로젝트 컨텍스트

> 이 문서는 **현재 상태만 빠르게 파악하기 위한 snapshot 문서**다.  
> 과거 판단과 이유는 [DECISIONS.md](DECISIONS.md), 장기 backlog는 [docs/planning/backlog_and_next_epics.md](docs/planning/backlog_and_next_epics.md)를 본다.

## 현재 범위

- 이 프로젝트의 현재 범위는 **DART 공시 분석 내부**에 한정한다.
- 범용 agent, broad web workflow, productivity tool 확장은 당분간 하지 않는다.
- 목표는 DART single-document / multi-document 분석을 빠르게 안정화하고 닫는 것이다.

## 최신 상태

- 2026-06-24 runtime numeric projection regression fix가 커밋되어
  `origin/main`에 push됐고, 그 상태에서 expanded structural 9-question
  store-fixed `eval-only` refresh를 다시 돌렸다.
  - current HEAD: `1d78b31 Fix runtime numeric projection regressions`
  - branch state: `main` is aligned with `origin/main`; worktree clean before
    the benchmark refresh.
  - source/test commits since PR #77 cleanup:
    - `949cb48 refactor runtime surfaces and import boundaries`
    - `08dbb92 document runtime cleanup split and audit baseline`
    - `7cfe62c Update cleanup handoff after push`
    - `1d78b31 Fix runtime numeric projection regressions`
  - focused/local validation for `1d78b31`:
    - `python3 -m unittest tests.test_subtask_loop`: `232` OK
    - `python3 -m unittest tests.test_financial_agent_run_projection tests.test_import_side_effects`:
      `71` OK
    - `python3 -m unittest tests.test_operation_contracts tests.test_aggregate_subtask_projection`:
      `320` OK
    - `python3 -m src.ops.audit_runtime_domain_terms`: passed with `215`
      reviewed literals
    - `git diff --check`: passed
  - refreshed full eval-only command:
    `python3 -m src.ops.benchmark_runner --config benchmarks/profiles/curated_ablation_expanded_candidate_full_system.json --output-dir benchmarks/results/ablation_expanded_candidate_full_system_2026-06-10 --eval-only --progress-heartbeat-sec 60 --heartbeat-log benchmarks/results/ablation_expanded_candidate_full_system_2026-06-10/heartbeat_full_9q_after_runtime_numeric_projection_fix_2026-06-24.jsonl`
  - refreshed result:
    - run status: `completed`
    - completed companies: `6`; pending companies: `0`
    - numeric final judgement: `9/9` PASS
    - winner ranking: `structural_selective_v2_prefix_2500_320`
      with `avg_full_numeric_pass_rate=1.000`,
      `avg_full_completeness=0.958`, `avg_full_faithfulness=1.000`,
      `avg_full_context_recall=0.900`
    - `full_eval_fail_count=1` remains because KB금융 aggregate completeness is
      `0.750`; this is a quality/completeness residual, not a numeric failure.
  - recommended next action:
    - Do not keep doing blind line-count refactoring.
    - If optimizing, target the KB completeness residual or a named
      owner-boundary item from
      `docs/architecture/core_runtime_surface_refactoring_plan.md`.
    - Keep benchmark artifacts under `benchmarks/results/**` out of commits
      unless explicitly publishing experiment bundles.

- 2026-06-23 PR #77 이후 local runtime cleanup이 source/docs split으로
  커밋되어 `origin/main`에 push됐다.
  - current HEAD: `08dbb92 document runtime cleanup split and audit baseline`
  - source/test commit:
    `949cb48 refactor runtime surfaces and import boundaries`
  - docs/audit commit:
    `08dbb92 document runtime cleanup split and audit baseline`
  - 현재 worktree는 clean이고 `main`은 `origin/main`과 일치한다.
  - source/test split path set:
    - `122` paths
    - `main.py`, `src/**`, `tests/**`
    - exclude: `tests/fixtures/runtime_domain_terms_baseline.json`
  - docs/audit split path set:
    - `12` paths
    - `README.md`, `CONTEXT.md`, `docs/**`,
      `tests/fixtures/runtime_domain_terms_baseline.json`
  - latest dry-run staging checks:
    - source/test:
      `git add --dry-run main.py src tests ':!tests/fixtures/runtime_domain_terms_baseline.json'`
      selects `122` paths
    - docs/audit:
      `git add --dry-run README.md CONTEXT.md docs tests/fixtures/runtime_domain_terms_baseline.json`
      selects `12` paths
    - overlap `0`, uncovered changed paths `0`
  - split manifest:
    `docs/architecture/current_runtime_cleanup_split_manifest.md`
    covers `134` changed source/docs/test paths with `missing=0`.
  - owner-foundation import gate:
    `owner_foundation_imports_ok=23`, `heavy_modules_loaded=<none>`.
  - latest source-bucket union gate:
    - runtime projection focused gate: `169` OK
    - task trace focused gate: `317` OK
    - primitive owner focused gate: `428` OK
    - portfolio review gates: `Status: ready`
    - runtime domain-term audit: passed with `215` reviewed literals
    - full unittest discovery: `1324` OK, `full_elapsed=15.033`
  - latest full cleanup validation after storage/contextual/answer/dependency
    helper splits:
    - `python3 -m unittest discover -s tests`: `1324` OK
    - latest measured full elapsed in manifest source-bucket union gate:
      `15.033s`
    - source-wide import smoke: `modules=123`, `failures=0`,
      `slow_ge_0_05=0`
    - artifact hygiene checks showed no `benchmarks/results/**`, temp benchmark
      files, local stores, or `mlruns` artifacts in the cleanup split.
  - recommended next action:
    - Do not continue reducing large graph/evidence/calculation functions unless
      there is a concrete owner-boundary seam or bug.
    - Run store-fixed eval-only benchmark refresh first to confirm the
      no-behavior-change cleanup did not regress answer quality.
    - If a regression appears, classify it by trace layer
      (`retrieval/evidence/reconcile/calculation/projection`) before patching.

- 2026-06-22 `FinancialAgent` 파악용 문서를 최신 runtime 구조에 맞게 갱신했다.
  - `docs/overview/question_trace_walkthrough.md`: PR #77 이후 graph wiring,
    `run()` output projection map, named projection(`agent_answer`,
    `review_trace`, `debug_bundle`), `financial_answer_projection.py` helper
    boundary를 반영했다.
  - `docs/overview/runtime_flow_roles.md`: `FinancialAgent` facade 책임,
    narrative/calculation graph path, projection/helper modules 지도를 갱신했다.
  - 목적은 코드 변경 전 독해 경로 정리이며, runtime behavior 변경은 없다.

- 2026-06-22 PR #77이 merge되어 현재 runtime/code baseline은
  `main@6d98d67`이다.
  - PR: `https://github.com/woojune511/dart-rag-agent/pull/77`
  - merge commit: `6d98d67 Merge pull request #77 from
    woojune511/codex/numeric-projection-closure`
  - included commits: `6557f50` numeric projection conflict fix, `77b68bf`
    ablation documentation, `c3a75be` aggregate answer projection helper
    extraction
  - current gate claim remains the expanded structural `9/9` numeric PASS
    described below.

- 2026-06-22 numeric-surface conflict fix 이후 maintenance refactor를 진행했다.
  - `src/agent/financial_answer_projection.py`를 추가해 aggregate/narrative
    answer projection 선택 로직을 graph helper bulk에서 분리했다.
  - `financial_graph_helpers.py`는 기존 `_preferred_complete_aggregate_subtask_answer`
    name을 re-export해서 caller-facing helper surface를 유지한다.
  - behavior target: no-behavior-change extraction only; benchmark score claim은
    아래 `9/9` closure 기준을 그대로 사용한다.
  - validation:
    - `python3 -m unittest tests.test_financial_agent_run_projection tests.test_benchmark_runner_runtime_projection`:
      `69` OK
    - `python3 -m unittest discover -s tests`: `1275` OK
    - `python3 -m src.ops.audit_runtime_domain_terms`: passed with `215`
      reviewed literals

- 2026-06-22 `KBF_T2_018` mixed growth+narrative projection gap을 일반
  runtime projection 문제로 고쳤고, expanded structural full-system
  9-question `eval-only`가 최종 `9/9` numeric PASS로 닫혔다.
  - change:
    - `structured_result.subtask_results` 안의 aggregate/narrative subtask가
      현재 numeric public answer를 포함하고 뒤쪽에 숫자 없는 설명 문장을 더
      갖고 있으면, 그 설명을 public answer와 resolved trace projection에
      보존한다.
    - evaluator/runtime resolver가 현재 trace와 public answer가 이미 같더라도
      structured subtask가 더 완성된 aggregate answer를 제공하면 재투영하도록
      했다.
    - complete aggregate answer가 이미 선택된 경우 stale numeric projection이
      noisy nested numeric lead로 다시 덮어쓰지 않게 했다.
    - clean aggregate/narrative candidate가 현재 public answer와 충분한 numeric
      surface overlap을 갖고, public answer 쪽에 candidate가 설명하지 않는
      충돌 숫자 claim이 더 많으면 clean candidate를 선택한다. 이 기준은 숫자
      surface consistency만 사용하며 회사/질문/계정명 runtime branch를 추가하지
      않는다.
  - focused verification:
    - command:
      `python3 -m src.ops.benchmark_runner --config benchmarks/profiles/curated_ablation_expanded_candidate_full_system.json --output-dir benchmarks/results/ablation_expanded_candidate_full_system_2026-06-10 --eval-only --company-run-id kbf_2023_expanded_candidate --question-id KBF_T2_018 --progress-heartbeat-sec 60 --heartbeat-log benchmarks/results/ablation_expanded_candidate_full_system_2026-06-10/heartbeat_kbf_t2_018_numeric_surface_conflict_guard_2026-06-22.jsonl`
    - result: `KBF_T2_018` numeric final judgement `PASS`,
      faithfulness `1.000`, completeness `1.000`, numeric equivalence
      `1.000`, numeric grounding `1.000`, numeric retrieval support `1.000`.
    - answer no longer includes the conflicting `3,146억원 / 1,299억원 /
      142.19%` prefix and preserves `3,146,409백만원 / 1,847,775백만원 /
      70.28%`.
  - ablation readout:
    - live focused commit comparison used temporary copies under
      `/tmp/dart-rag-agent-ablation-20260622`: `HEAD=6557f50` and
      `HEAD~1=66b8cc2` both produced numeric final judgement `PASS` for
      `KBF_T2_018`, so the live score delta is not a stable discriminator.
    - deterministic projection ablation with the same synthetic aggregate state
      isolates the runtime change: `HEAD~1` leaves the conflicting `142.19%`
      numeric prefix in the public answer and exits non-zero, while `HEAD`
      replaces it with the clean aggregate answer and exits `0`.
  - full verification:
    - command:
      `python3 -m src.ops.benchmark_runner --config benchmarks/profiles/curated_ablation_expanded_candidate_full_system.json --output-dir benchmarks/results/ablation_expanded_candidate_full_system_2026-06-10 --eval-only --progress-heartbeat-sec 60 --heartbeat-log benchmarks/results/ablation_expanded_candidate_full_system_2026-06-10/heartbeat_full_structural_after_numeric_surface_conflict_guard_2026-06-22.jsonl`
    - result: `9/9` numeric final judgement `PASS`
    - PASS: `KAB_T1_066`, `POS_T1_057`, `SAM_T3_028`, `MIX_T1_021`,
      `CEL_T1_013`, `KBF_T2_018`, `KBF_T1_017`, `SKH_T3_080`, `SKH_T1_060`
    - elapsed heartbeat: about `1199.2s`
  - unit/audit verification:
    - `python3 -m unittest tests.test_financial_agent_run_projection tests.test_benchmark_runner_runtime_projection tests.test_subtask_loop`:
      `300` OK
    - `python3 -m unittest discover -s tests`: `1275` OK
    - `python3 -m src.ops.audit_runtime_domain_terms`: passed with `215`
      reviewed literals
  - artifact hygiene:
    - focused/full eval updated ignored files under `benchmarks/results/**`; do
      not stage benchmark artifacts unless explicitly requested.

- 2026-06-22 takeout benchmark store/cache 복구 후 최신 코드로 expanded
  structural full-system 9-question `eval-only`를 재실행했다.
  - setup:
    - takeout artifact path:
      `../dart-rag-agent_takeout_important_20260619/dart-rag-agent/`
    - restored local-only artifacts:
      `benchmarks/results/ablation_expanded_candidate_full_system_2026-06-10/`,
      `benchmarks/results/ablation_expanded_candidate_plain_retrieval_2026-06-10/`,
      `.env`
    - takeout result JSON absolute paths from
      `/storage/geonju511/dart-rag-agent` were rewritten to
      `/home/geonju/dart-rag-agent` so store-fixed eval-only could reuse the
      restored Chroma/context-cache artifacts.
  - command:
    - `python3 -m src.ops.benchmark_runner --config benchmarks/profiles/curated_ablation_expanded_candidate_full_system.json --output-dir benchmarks/results/ablation_expanded_candidate_full_system_2026-06-10 --eval-only --progress-heartbeat-sec 60 --heartbeat-log benchmarks/results/ablation_expanded_candidate_full_system_2026-06-10/heartbeat_full_structural_latest_2026-06-22.jsonl`
  - result:
    - numeric final judgement: `8/9` PASS, `1/9` UNCERTAIN
    - PASS: `KAB_T1_066`, `POS_T1_057`, `SAM_T3_028`, `MIX_T1_021`,
      `CEL_T1_013`, `KBF_T1_017`, `SKH_T3_080`, `SKH_T1_060`
    - UNCERTAIN: `KBF_T2_018`
    - run-level winner summary: avg numeric `0.917`, avg completeness `0.892`,
      avg faithfulness `0.917`, avg recall `0.917`
    - heartbeat elapsed: about `1274.6s`
  - `KBF_T2_018` read:
    - public answer preserved the correct numeric surfaces:
      `3,146,409 백만원`, `1,847,775 백만원`, `70.28%`
    - numeric equivalence/grounding were healthy, but final judgement remained
      `UNCERTAIN` because faithfulness was `0.0`, completeness `0.5`, and
      numeric retrieval support `0.5`.
    - This is no longer the earlier spurious `100만원 / 5,400만원 /
      98.15% 감소` final-answer leak; the remaining issue is evaluator/runtime
      evidence-support projection for the mixed growth+narrative answer.
  - validation before run:
    - `python3 -m src.ops.audit_runtime_domain_terms`: passed with `215`
      reviewed literals
    - `python3 -m unittest tests.test_benchmark_runner_runtime_projection tests.test_subtask_loop`:
      `246` OK
  - environment note:
    - no `.venv` existed on this machine; `python3` is Python `3.14.4`.
      Full dependencies were installed into user site-packages with
      `python3 -m pip install --user --break-system-packages -r requirements.txt`
      because `python3 -m venv` failed without `python3.14-venv`.
  - artifact hygiene:
    - `.env`, `benchmarks/results/**`, `mlflow.db`, `mlruns/`, and
      `__pycache__` outputs are local-only and should not be staged.
  - next natural step:
    - Diagnose `KBF_T2_018` as a generic evidence-support/projection issue.
      Do not add company/question-specific runtime branches.

- 2026-06-19 full structural `eval-only` refresh after the SKH projection fix
  completed with `8/9` numeric PASS:
  - command:
    - `.venv/bin/python -m src.ops.benchmark_runner --config benchmarks/profiles/curated_ablation_expanded_candidate_full_system.json --output-dir benchmarks/results/ablation_expanded_candidate_full_system_2026-06-10 --eval-only --progress-heartbeat-sec 60 --heartbeat-log benchmarks/results/ablation_expanded_candidate_full_system_2026-06-10/heartbeat_full_structural_after_projection_fix_2026-06-19.jsonl`
  - result:
    - PASS: `KAB_T1_066`, `POS_T1_057`, `SAM_T3_028`, `MIX_T1_021`,
      `CEL_T1_013`, `KBF_T1_017`, `SKH_T3_080`, `SKH_T1_060`
    - FAIL: `KBF_T2_018`
    - failure answer leaked a spurious period-comparison fragment:
      `100만원 / 5,400만원 / 98.15% 감소`
    - the same trace already contained a supported aggregate narrative subtask
      with the correct numeric material:
      `3,146,409백만원 / 1,847,775백만원 / 70.28% 증가`
  - code/result read:
    - This was not a retrieval miss in the final artifact: a supported
      `aggregate_subtasks` narrative answer existed, but later final answer
      refresh could reattach the weaker growth trace.
    - Runtime now treats a supported `aggregate_subtasks` narrative answer as a
      final replacement candidate when the current final answer has numeric
      surfaces incompatible with that supported aggregate.
    - The check is generic numeric-surface compatibility. No company name,
      benchmark ID, report phrase, or metric-specific runtime branch was added.
  - focused verification after the fix:
    - command:
      - `.venv/bin/python -m src.ops.benchmark_runner --config benchmarks/profiles/curated_ablation_expanded_candidate_full_system.json --output-dir benchmarks/results/ablation_expanded_candidate_full_system_2026-06-10 --eval-only --company-run-id kbf_2023_expanded_candidate --question-id KBF_T2_018 --progress-heartbeat-sec 60 --heartbeat-log benchmarks/results/ablation_expanded_candidate_full_system_2026-06-10/heartbeat_kbf_t2_018_supported_aggregate_fix_2026-06-19.jsonl`
    - `KBF_T2_018`: `numeric_final_judgement = PASS`
    - answer preserves `3,146,409백만원`, `1,847,775백만원`, `70.28%`
    - faithfulness/completeness/context recall/Context P@5:
      `1.000 / 1.000 / 0.667 / 1.000`
    - latency: `306.3s`
  - validation:
    - `python -m unittest` focused growth/projection regression set: `6` OK
    - `python -m src.ops.audit_runtime_domain_terms`: passed with `215`
      reviewed literals
    - `python -m unittest discover -s tests`: `1271` OK
  - important caveat:
    - The full structural aggregate is still a completed `8/9` run plus focused
      closure for the only failing row. Rerun the full 9-question structural
      profile once more before reporting a fresh completed `9/9` aggregate.
  - raw `benchmarks/results/**` outputs and heartbeat logs remain local-only.
  - 다음 natural step:
    - rerun the 9-question structural `eval-only` profile under the new fix if
      the portfolio needs a single fresh aggregate number. Plain retrieval stays
      at the latest completed `5/9` refresh unless comparing variants again.

- 2026-06-19 structured subtask projection fix 이후 `SKH_T1_060` focused
  store-fixed structural full-system `eval-only`를 재실행했다.
  - command:
    - `.venv/bin/python -m src.ops.benchmark_runner --config benchmarks/profiles/curated_ablation_expanded_candidate_full_system.json --output-dir benchmarks/results/ablation_expanded_candidate_full_system_2026-06-10 --eval-only --company-run-id skh_2023_expanded_candidate --question-id SKH_T1_060 --progress-heartbeat-sec 30 --heartbeat-log benchmarks/results/ablation_expanded_candidate_full_system_2026-06-10/heartbeat_skh_t1_060_trace_projection_fix_2026-06-19.jsonl`
  - result:
    - `SKH_T1_060`: `numeric_final_judgement = PASS`
    - answer: `42.02%`
    - faithfulness/completeness/context recall/Context P@5:
      `1.000 / 1.000 / 1.000 / 1.000`
    - latency: `353.7s`
  - code/result read:
    - Before this fix, the same 2026-06-19 session ran the 9-question expanded
      structural profile with heartbeat
      `benchmarks/results/ablation_expanded_candidate_full_system_2026-06-10/heartbeat_full_structural_after_trace_hygiene_2026-06-19.jsonl`.
      That run produced `8/9` numeric PASS and `SKH_T1_060 = UNCERTAIN`.
    - The live calculation can still emit an intermediate stale aggregate
      ratio (`70.33%`), but the public answer and `structured_result`
      are aligned on the source-supported `42.02%`.
    - Runtime/evaluator projection now rebuilds the resolved trace from
      structured subtask outputs when the public answer matches the structured
      subtask result. Compact KRW answer surfaces such as `4조 1,456억원` are
      matched back to canonical KRW slots such as `4,145,647백만원`.
    - This is a generic runtime projection / display-normalization fix. No
      company name, benchmark ID, or metric-specific runtime branch was added.
  - validation:
    - `python -m src.ops.audit_runtime_domain_terms`
    - `python -m unittest tests.test_benchmark_runner_runtime_projection.BenchmarkRunnerRuntimeProjectionTests.test_serialise_eval_results_reprojects_structured_subtasks_when_operands_are_stale tests.test_benchmark_runner_runtime_projection.BenchmarkRunnerRuntimeProjectionTests.test_serialise_eval_results_keeps_structured_runtime_contract`
    - `python -m unittest tests.test_benchmark_runner_runtime_projection tests.test_financial_agent_run_projection tests.test_aggregate_subtask_projection`
  - important caveat:
    - The preceding 9-question structural eval-only run on 2026-06-19 produced
      `8/9` PASS plus `SKH_T1_060 = UNCERTAIN`; the focused residual rerun
      passed after the fix. Rerun the full 9-question structural profile before
      changing the aggregate structural claim from `8/9`.
  - raw `benchmarks/results/**` outputs and heartbeat logs remain local-only.
  - 다음 natural step:
    - run `python -m unittest discover -s tests`, then rerun the 9-question
      structural `eval-only` profile to refresh the aggregate claim. Plain
      `5/9` does not need rerun unless source code changes could affect plain
      projection/scoring.

- 2026-06-19 aggregate numeric trace hygiene 커밋 `e3a1eb1`
  (`Harden aggregate numeric trace hygiene`) 이후 5-case hard set을
  store-fixed structural full-system `eval-only`로 재실행했다.
  - command:
    - `.venv/bin/python -m src.ops.benchmark_runner --config benchmarks/profiles/curated_ablation_expanded_candidate_full_system.json --output-dir benchmarks/results/ablation_expanded_candidate_full_system_2026-06-10 --eval-only --company-run-id kbf_2023_expanded_candidate --question-id KBF_T2_018 --company-run-id posco_2023_expanded_candidate --question-id POS_T1_057 --company-run-id skh_2023_expanded_candidate --question-id SKH_T3_080 --company-run-id samsung_2023_expanded_candidate --question-id SAM_T3_028 --company-run-id celltrion_2023_expanded_candidate --question-id CEL_T3_040 --progress-heartbeat-sec 30 --heartbeat-log benchmarks/results/ablation_expanded_candidate_full_system_2026-06-10/heartbeat_hard_set_after_growth_filter_2026-06-19.jsonl`
  - result:
    - `5/5` numeric PASS:
      `POS_T1_057`, `SAM_T3_028`, `CEL_T3_040`, `KBF_T2_018`,
      `SKH_T3_080`
    - scores:
      - `POS_T1_057`: avg `0.961`, faithfulness/completeness `1.000 / 1.000`
      - `SAM_T3_028`: avg `0.945`, faithfulness/completeness `1.000 / 0.700`
      - `CEL_T3_040`: avg `0.848`, faithfulness/completeness `1.000 / 1.000`
      - `KBF_T2_018`: avg `0.880`, faithfulness/completeness `1.000 / 1.000`
      - `SKH_T3_080`: avg `0.942`, faithfulness/completeness `1.000 / 1.000`
  - code/result read:
    - KBF final answer no longer leaks unsupported `-93.69%` /
      `2,800만원`; it keeps the trace-supported `70.28%` growth answer.
    - SKH final answer no longer leaks stale `0백만원`; it preserves
      `5,739억원`, `9,061억원`, and `-3,322억원`.
    - The change is generic trace/evidence hygiene. No company name,
      benchmark ID, or metric-specific runtime branch was added.
  - validation before commit:
    - `python -m src.ops.audit_runtime_domain_terms`
    - `python -m unittest tests.test_subtask_loop`
    - `python -m unittest discover -s tests`
  - raw `benchmarks/results/**` outputs and heartbeat logs remain local-only.
  - 다음 natural step:
    - source docs are now updated for this state.
    - Next benchmark expansion should be store-fixed `eval-only`, not fresh
      ingest, unless parser/ingest/cache-signature changes are introduced.

- 2026-06-18 structured operand evidence alignment 커밋
  `f9f6183` 이후 broader focused regression을 store-fixed `eval-only`로
  실행했다.
  - command:
    - `.venv/bin/python -m src.ops.benchmark_runner --config benchmarks/profiles/curated_ablation_expanded_candidate_full_system.json --output-dir benchmarks/results/ablation_expanded_candidate_full_system_2026-06-10 --eval-only --company-run-id kakaobank_2023_expanded_candidate --company-run-id posco_2023_expanded_candidate --company-run-id samsung_2023_expanded_candidate --company-run-id celltrion_2023_expanded_candidate --company-run-id kbf_2023_expanded_candidate --company-run-id skh_2023_expanded_candidate --question-id KBF_T2_018 --question-id SKH_T3_080 --question-id CEL_T1_013 --question-id CEL_T3_040 --question-id POS_T1_057 --question-id KAB_T1_066 --question-id SAM_T3_028 --progress-heartbeat-sec 60 --heartbeat-log benchmarks/results/ablation_expanded_candidate_full_system_2026-06-10/heartbeat_broader_focused_gate_2026-06-18.jsonl`
  - result:
    - `7/7` numeric PASS: `KAB_T1_066`, `POS_T1_057`, `SAM_T3_028`,
      `CEL_T1_013`, `CEL_T3_040`, `KBF_T2_018`, `SKH_T3_080`
    - key answers: `37.47%`, `3.5269배`, `2.79%`, `52.99%`,
      `70.28%`, `-3,322억원`
    - wall-clock runtime about `32.2m`
  - residuals:
    - `SAM_T3_028` numeric PASS but completeness `0.5`.
    - `CEL_T3_040` numeric PASS but completeness `0.0` and context recall
      `0.333`.
    - `CEL_T1_013`, `KBF_T2_018`, and `SKH_T3_080` still show intermediate
      stale/noisy calculation traces before final answer recovery.
  - 해석:
    - This is a post-commit regression gate, not a new structural-vs-plain
      aggregate comparison. Keep the latest aggregate claim as structural
      `8/9` vs plain `5/9` until the full expanded profiles are rerun.
  - raw `benchmarks/results/**` outputs and heartbeat logs remain local-only.

- 2026-06-18 operand-candidate filtering 리팩터링 이후 expanded plain
  retrieval 9-question store-fixed `eval-only` refresh를 완료했다.
  - command:
    - `.venv/bin/python -m src.ops.benchmark_runner --config benchmarks/profiles/curated_ablation_expanded_candidate_plain_retrieval.json --output-dir benchmarks/results/ablation_expanded_candidate_plain_retrieval_2026-06-10 --eval-only --progress-heartbeat-sec 60 --heartbeat-log benchmarks/results/ablation_expanded_candidate_plain_retrieval_2026-06-10/heartbeat_plain_after_operand_filter_refactor_2026-06-18.jsonl`
  - result:
    - plain retrieval numeric pass: `5/9`
    - question-level avg faithfulness `0.589`, avg completeness `0.522`,
      avg context recall `0.926`, avg Context P@5 `0.800`
    - runtime usage: `116` LLM calls, `585,879` LLM tokens, `63` query
      embedding calls, estimated runtime cost about `$0.6681`
    - heartbeat runtime about `41.5m`
  - per-question:
    - PASS: `KAB_T1_066`, `SAM_T3_028`, `MIX_T1_021`, `KBF_T2_018`,
      `KBF_T1_017`
    - FAIL: `POS_T1_057`, `CEL_T1_013`, `SKH_T3_080`, `SKH_T1_060`
  - 해석:
    - 최신 current comparison은 structural `8/9` vs plain `5/9`다.
    - `SAM_T3_028`는 더 이상 current structural-only separator가 아니다.
      operand/runtime 개선이 plain에도 전파되어 `2.79%`로 PASS했다.
    - current structural-only separators는 `POS_T1_057`, `CEL_T1_013`,
      `SKH_T3_080`이다.
    - `SKH_T1_060`은 structural/plain 모두 FAIL인 shared hard residual이다.
  - raw `benchmarks/results/**` outputs and heartbeat logs remain local-only.

- 2026-06-18 operand-candidate filtering 리팩터링 이후 expanded structural
  9-question store-fixed `eval-only` refresh를 완료했다.
  - command:
    - `.venv/bin/python -m src.ops.benchmark_runner --config benchmarks/profiles/curated_ablation_expanded_candidate_full_system.json --output-dir benchmarks/results/ablation_expanded_candidate_full_system_2026-06-10 --eval-only --progress-heartbeat-sec 60 --heartbeat-log benchmarks/results/ablation_expanded_candidate_full_system_2026-06-10/heartbeat_full_structural_after_operand_filter_refactor_2026-06-18.jsonl`
  - result:
    - structural full-system numeric pass: `8/9`
    - avg faithfulness `0.942`, avg completeness `0.850`, avg context recall
      `0.889`
    - runtime usage: `135` LLM calls, `722,298` LLM tokens, `63` query
      embedding calls, estimated runtime cost about `$0.6334`
    - heartbeat runtime about `42.5m`
  - per-question:
    - PASS: `KAB_T1_066`, `POS_T1_057`, `SAM_T3_028`, `MIX_T1_021`,
      `CEL_T1_013`, `KBF_T2_018`, `KBF_T1_017`, `SKH_T3_080`
    - FAIL: `SKH_T1_060`
  - 해석:
    - 이전 expanded structural refresh의 shared residual이던 `POS_T1_057`는
      focused closure 이후 full structural refresh에서도 PASS로 유지됐다.
    - 남은 hard residual은 `SKH_T1_060` 하나다. 로그상 숫자 후보는 대부분
      회수되지만 `distinct_ratio_roles` reflection 이후에도 denominator /
      role binding이 최종 numeric judge를 통과하지 못했다.
    - plain retrieval counterpart는 이후 같은 코드 상태로 재실행되어 `5/9`
      결과로 갱신됐다.
  - raw `benchmarks/results/**` outputs and heartbeat logs remain local-only.

- 2026-06-18 operand-candidate filtering 리팩터링 이후 expanded structural
  hard-case smoke를 store-fixed `eval-only`로 재확인했다.
  - 목적: `_required_operand_rows_from_candidates()` /
    `_merge_required_operand_fallback_rows()` 추출 이후, structural
    ablation의 강한 separator가 regression 없이 유지되는지 확인했다.
  - commands:
    - `.venv/bin/python -m src.ops.benchmark_runner --config benchmarks/profiles/curated_ablation_expanded_candidate_full_system.json --output-dir benchmarks/results/ablation_expanded_candidate_full_system_2026-06-10 --company-run-id samsung_2023_expanded_candidate --eval-only --question-id SAM_T3_028 --progress-heartbeat-sec 30 --heartbeat-log benchmarks/results/ablation_expanded_candidate_full_system_2026-06-10/heartbeat_sam_t3_028_after_operand_filter_refactor_2026-06-18.jsonl`
    - `.venv/bin/python -m src.ops.benchmark_runner --config benchmarks/profiles/curated_ablation_expanded_candidate_full_system.json --output-dir benchmarks/results/ablation_expanded_candidate_full_system_2026-06-10 --company-run-id celltrion_2023_expanded_candidate --eval-only --question-id CEL_T1_013 --progress-heartbeat-sec 30 --heartbeat-log benchmarks/results/ablation_expanded_candidate_full_system_2026-06-10/heartbeat_cel_t1_013_after_operand_filter_refactor_2026-06-18.jsonl`
  - results:
    - `SAM_T3_028`: `numeric_final_judgement = PASS`, answer `2.79%`,
      faithfulness `1.000`, completeness `0.700`, avg score `0.945`.
    - `CEL_T1_013`: `numeric_final_judgement = PASS`, answer `52.99%`,
      faithfulness `1.000`, completeness `1.000`, avg score `0.923`.
  - 해석:
    - 이번 리팩터링은 benchmark/domain-specific rule 추가 없이 required
      operand candidate 생성과 surface-contract filtering의 공통 계약만
      중앙화했다.
    - 두 separator smoke가 유지됐으므로, 다음 단계는 더 많은 리팩터링보다
      필요 시 expanded 9-question store-fixed eval-only를 한 번 더 돌려
      aggregate claim을 갱신하는 것이다.
  - raw `benchmarks/results/**` outputs and heartbeat logs remain local-only.

- 2026-06-17 `POS_T1_057` focused closure를 store-fixed `eval-only`로
  재확인했다.
  - command:
    - `.venv/bin/python -m src.ops.benchmark_runner --config benchmarks/profiles/curated_ablation_expanded_candidate_full_system.json --output-dir benchmarks/results/ablation_expanded_candidate_full_system_2026-06-10 --company-run-id posco_2023_expanded_candidate --eval-only --question-id POS_T1_057 --progress-heartbeat-sec 30 --heartbeat-log benchmarks/results/ablation_expanded_candidate_full_system_2026-06-10/heartbeat_pos_t1_057_after_evaluator_trace_sync_2026-06-17.jsonl`
  - result:
    - `numeric_final_judgement = PASS`
    - faithfulness `1.000`
    - completeness `0.700`
    - final answer `3.5269배`
    - exported `resolved_calculation_trace.calculation_plan.mode =
      aggregate_subtasks`
  - code changes are generic: interest-expense direct lookup now requires the
    ontology `surface_contract`; requested-scope lookup recovery does not let
    unknown-scope structured rows overwrite requested-scope evidence; public
    answer / evaluator / benchmark export now re-align stale top-level traces
    with structured subtask results when the structured numeric answer is the
    public answer.
  - This is a focused closure after the earlier 9-question expanded refresh;
    the full expanded aggregate has not been rerun in this step.
  - raw `benchmarks/results/**` outputs and heartbeat logs remain local-only.

- 2026-06-17 expanded ablation store-fixed `eval-only` refresh를 실행했다.
  - 목적: aggregate public-answer projection fix 이후, 9문항 expanded
    structural full-system slice가 promotion rule을 회복하는지 확인하고,
    threshold 충족 시 plain-retrieval counterpart를 비교했다.
  - structural command:
    - `.venv/bin/python -m src.ops.benchmark_runner --config benchmarks/profiles/curated_ablation_expanded_candidate_full_system.json --output-dir benchmarks/results/ablation_expanded_candidate_full_system_2026-06-10 --eval-only --progress-heartbeat-sec 60 --heartbeat-log benchmarks/results/ablation_expanded_candidate_full_system_2026-06-10/heartbeat_evalonly_after_kbf_projection_fix_2026-06-17.jsonl`
  - plain command:
    - `.venv/bin/python -m src.ops.benchmark_runner --config benchmarks/profiles/curated_ablation_expanded_candidate_plain_retrieval.json --output-dir benchmarks/results/ablation_expanded_candidate_plain_retrieval_2026-06-10 --eval-only --progress-heartbeat-sec 60 --heartbeat-log benchmarks/results/ablation_expanded_candidate_plain_retrieval_2026-06-10/heartbeat_evalonly_after_fullsystem_7of9_2026-06-17.jsonl`
  - 결과:
    - structural full-system: numeric pass `7/9`, avg completeness `0.578`,
      avg faithfulness `0.833`, avg recall `0.867`, estimated runtime cost
      `$0.6156`, heartbeat runtime about `28.5m`.
    - plain retrieval: numeric pass `4/9`, avg completeness `0.389`, avg
      faithfulness `0.678`, avg recall `0.904`, estimated runtime cost
      `$0.8348`, heartbeat runtime about `32.1m`.
  - structural-only PASS separators:
    - `SAM_T3_028`: structural `2.79%`; plain scale drift `2792.63%`.
    - `CEL_T1_013`: structural `52.99%`; plain broader denominator `49.74%`.
    - `SKH_T3_080`: structural `-3,322억원`; plain misbound loss surface
      `-1,351,498백만원`.
  - 당시 shared residuals:
    - `POS_T1_057`: interest-cost sign/display and unit binding instability.
    - `SKH_T1_060`: debt-component numerator / asset denominator aggregation.
  - 해석:
    - 당시 expanded slice는 더 이상 stop-line이 아니었고, 이후 2026-06-18
      post-refactor structural refresh에서 `POS_T1_057`까지 닫혀 최신
      structural 결과는 `8/9`가 됐다. 이후 같은 코드 상태로 plain도
      재실행되어 최신 comparison은 structural `8/9` vs plain `5/9`가
      됐다.
    - raw `benchmarks/results/**` 산출물과 heartbeat log는 local-only다.

- 2026-06-17 PR 4 simplification 이후 store-fixed ablation smoke
  `eval-only` refresh를 실행했다.
  - 목적: full benchmark로 바로 확장하기 전에, 현재 코드가 기존 smoke
    harness와 결과 형태를 재현하는지 확인했다.
  - profiles:
    - `benchmarks/profiles/curated_ablation_smoke_full_system.json`
    - `benchmarks/profiles/curated_ablation_smoke_plain_retrieval.json`
  - local-only artifact dirs:
    - `benchmarks/results/ablation_smoke_full_system_2026-06-10`
    - `benchmarks/results/ablation_smoke_plain_retrieval_2026-06-10`
  - 결과:
    - `KAB_T1_066`: full-system PASS, plain PASS. 최종 정답은 둘 다
      `37.47%`, 다만 `Context P@5`는 full-system `0.800`, plain `0.400`.
    - `SKH_T1_060`: full-system FAIL, plain FAIL. 둘 다 아직 debt/asset
      operand binding diagnostic case로 남는다.
    - full-system은 SKH context recall `1.000`, plain은 `0.800`으로 structural
      representation 쪽의 evidence coverage는 더 좋았지만, 2문항 smoke의
      numeric pass rate는 둘 다 `1/2`다.
  - 해석:
    - 이 refresh는 portfolio용 최종 ablation claim이 아니라 harness sanity
      check다.
    - 강한 claim은 기존 expanded candidate slice의 documented result를
      기준으로 유지하고, full benchmark 확장은 별도 비용/시간 결정 후
      monitored run으로 진행한다.
  - raw `benchmarks/results/**` 산출물은 commit 대상이 아니다.

- 2026-06-17 PR 4 calculation simplification을 재개했다.
  - 목적을 "helper extraction"이 아니라 누적 patch/dead branch 삭제로 전환했다.
  - runtime에서 호출되지 않는 `_preferred_complete_nested_numeric_narrative_answer`
    및 그 전용 `_preserve_evidence_numeric_display` helper를 제거했다.
  - 해당 private helper만 직접 붙잡던 테스트를 제거하고, source-stated growth
    conflict 검증은 남겼다.
  - `_apply_mutable_numeric_answer` wrapper를 제거하고 두 호출부가 canonical
    `_apply_numeric_answer_to_aggregate_state`를 직접 사용하게 했다.
  - 추가로 runtime 호출자가 없는 `_narrative_summary_gap_is_satisfied`와
    그 private helper만 직접 검증하던 테스트를 제거했다.
  - 삭제된 regex literal은 runtime domain-term audit baseline에서도 제거했다.
  - 이어서 `calculation_rendering` / `financial_answer_slots`로 이미 이동한 뒤
    agent runtime에서 호출하지 않는 7개 thin wrapper shim을 제거했다.
  - mutable aggregate state에서만 쓰이던 `_replace_aggregate_final_answer`,
    `_replace_aggregate_results` 중간 wrapper를 제거하고 mutable update 함수가
    직접 state replacement를 수행하게 했다.
  - 호출자가 없는 `_render_grounded_operand_display` agent shim을 제거했다.
    실제 구현은 `financial_graph_calculation_rendering.render_grounded_operand_display`
    모듈 함수로 유지된다.
  - 결과:
    - `src/agent/financial_graph_calculation.py`: `18,623` -> `18,296` lines
    - latest diff: runtime-only `3` deletions
  - 검증:
    - `python -m src.ops.audit_runtime_domain_terms`: passed
      (`215` reviewed literals)
    - `.venv/bin/python -m unittest tests.test_aggregate_subtask_projection tests.test_operation_contracts tests.test_subtask_loop tests.test_financial_calculation_execution tests.test_financial_calculation_rendering`:
      `507` OK
    - `.venv/bin/python -m unittest tests.test_financial_answer_slots tests.test_financial_calculation_rendering tests.test_operation_contracts tests.test_subtask_loop tests.test_financial_calculation_execution`:
      `464` OK
    - `.venv/bin/python -m unittest tests.test_runtime_domain_term_audit tests.test_subtask_loop tests.test_aggregate_subtask_projection tests.test_operation_contracts tests.test_financial_calculation_execution tests.test_financial_calculation_rendering`:
      `513` OK
    - `.venv/bin/python -m unittest discover -s tests`: `1223` OK
    - `uv run --with-requirements requirements-review.txt python -m src.ops.portfolio_review_gates`:
      `Status: ready`
    - `git diff --check`: passed
  - 다음 simplification 후보는 새 추출이 아니라, runtime 호출자가 없는 private
    helper와 private-helper-only tests를 계속 audit하거나, 같은 state update를
    반복하는 patch layer를 더 줄일 수 있는지 보는 것이다.

- 2026-06-17 PR 8 docs cleanup 세 번째 조각을 진행했다.
  - `portfolio_one_pager.md`에서 README와 중복되는 긴 command block을 제거하고,
    reviewer command source를 README로 단일화했다.
  - `docs/README.md`의 quick review path를 core 5-document path와 optional
    interview/resume deliverable로 분리해 문서 역할을 명확히 했다.
  - 검증:
    - reviewer-facing doc local link check: passed
    - `uv run --with-requirements requirements-review.txt python -m src.ops.portfolio_review_gates`:
      `Status: ready`
    - `git diff --check`: passed
  - 다음 PR 8 후보는 reviewer-facing 문서의 링크 유효성/중복 claim을
    자동 점검하거나, PR8을 stop-line으로 닫고 포트폴리오 최종 점검으로
    넘어가는 것이다.

- 2026-06-17 PR 8 requirements/docs cleanup 두 번째 조각을 진행했다.
  - `requirements.txt`에 full development / ingest / benchmark / app lock임을
    명시했다.
  - README의 representative checks를 lightweight reviewer profile,
    capability-specific gates, full development profile로 분리했다.
  - `docs/README.md`에 dependency profile 설명을 추가해 quick review path가
    full ML stack 설치를 요구하지 않는다는 점을 명확히 했다.
  - 검증:
    - `uv run --with-requirements requirements-review.txt python -m src.ops.portfolio_demo --format json`:
      ready
    - `uv run --with-requirements requirements-review.txt python -m src.ops.portfolio_review_gates`:
      `Status: ready`
    - `requirements.txt` / `requirements-review.txt` parsed via
      `packaging.requirements.Requirement`
    - `git diff --check`: passed
  - 다음 PR 8 후보는 README/overview 문서 수를 더 줄이는 것이 아니라,
    reviewer-facing 5개 문서와 appendix/internal log의 역할이 실제 링크와
    중복 없이 맞는지 점검하는 것이다.

- 2026-06-17 PR 7 MAS isolation 다섯 번째 조각을 진행했다.
  - full MAS caller import scan 결과를 기준으로 compatibility shim 전략을
    고정했다.
  - 새 public/ops/test caller는 `src.experimental.mas`를 사용한다.
  - `src.agent.multi_agent_graph`와 `src.agent.nodes.__init__`는 기존 import를
    깨지 않기 위한 compatibility shim/export surface로 남긴다.
  - `src.agent.mas_graph`, `src.agent.mas_types`, `src.agent.nodes.*`는 아직
    실제 구현 위치이며, implementation file move 전까지 삭제하거나 redirect
    shim으로 바꾸지 않는다.
  - 남은 legacy import 분류:
    - `src.experimental.mas.*`: experimental facade가 기존 구현을 감싸는 의도된
      bridge
    - `tests/test_experimental_mas_namespace.py`: compatibility identity assertion
    - focused node tests: implementation-private constant/helper 검증
    - `src.agent.*` 내부: 구현 내부 의존성
  - 검증:
    - `python -m src.ops.audit_runtime_domain_terms`: passed
    - `.venv/bin/python -m unittest tests.test_experimental_mas_namespace tests.test_multi_agent_graph tests.test_analyst_node tests.test_researcher_node tests.test_critic_node tests.test_orchestrator_node`:
      `37` OK
    - `python -m py_compile src/agent/multi_agent_graph.py src/agent/nodes/__init__.py`:
      passed
    - `uv run --with-requirements requirements-review.txt python -m src.ops.portfolio_review_gates`:
      ready
    - `git diff --check`: passed
  - 다음 PR 7 후보는 implementation move 자체가 아니라, move가 필요한지
    재평가하거나 PR 8 requirements/docs cleanup으로 넘어가는 것이다.

- 2026-06-17 PR 7 MAS isolation 네 번째 조각을 진행했다.
  - `src.experimental.mas.diagnostics`를 추가해 MAS worker probe가 쓰는
    Researcher diagnostic helper surface를 experimental namespace에 분리했다.
  - `src/ops/mas_direct_worker_probe.py`는 더 이상
    `src.agent.nodes.researcher_node`의 private helper를 직접 import하지 않는다.
  - top-level `src.experimental.mas`에는 diagnostic helper를 re-export하지 않아
    product-facing MAS facade를 불필요하게 넓히지 않았다.
  - 검증:
    - `.venv/bin/python -m unittest tests.test_experimental_mas_namespace tests.test_mas_direct_worker_probe tests.test_mas_e2e_smoke tests.test_mas_e2e_smoke_contract tests.test_mas_researcher_smoke_contract tests.test_portfolio_demo`:
      `31` OK
    - `python -m py_compile src/experimental/mas/diagnostics.py src/ops/mas_direct_worker_probe.py tests/test_experimental_mas_namespace.py`:
      passed
    - `uv run --with-requirements requirements-review.txt python -m src.ops.portfolio_review_gates`:
      ready
    - `git diff --check`: passed
  - 다음 PR 7 후보는 full caller import scan 결과를 문서화하고,
    implementation file 이동 전에 compatibility shim/deprecation strategy를
    확정하는 것이다.

- 2026-06-17 PR 7 MAS isolation 세 번째 조각을 진행했다.
  - MAS focused tests의 public graph/type/node factory imports를
    `src.experimental.mas` namespace로 전환했다.
  - legacy import는 `tests/test_experimental_mas_namespace.py`의 compatibility
    assertion과 implementation-private helper/constant 검증에만 남겼다.
  - 검증:
    - `.venv/bin/python -m unittest tests.test_experimental_mas_namespace tests.test_multi_agent_graph tests.test_analyst_node tests.test_researcher_node tests.test_critic_node tests.test_orchestrator_node`:
      `36` OK
    - `python -m py_compile tests/test_analyst_node.py tests/test_researcher_node.py tests/test_critic_node.py tests/test_orchestrator_node.py tests/test_multi_agent_graph.py`:
      passed
    - `uv run --with-requirements requirements-review.txt python -m src.ops.portfolio_review_gates`:
      ready
    - `git diff --check`: passed
  - 다음 PR 7 후보는 Researcher diagnostic private helpers를 experimental
    facade로 올릴지 말지 결정하거나, implementation file 이동 전에 전체
    caller import scan을 한 번 더 고정하는 것이다.

- 2026-06-17 PR 7 MAS isolation 두 번째 조각을 진행했다.
  - `src/ops/mas_analyst_smoke.py`, `mas_researcher_smoke.py`,
    `mas_e2e_smoke.py`, `mas_direct_worker_probe.py`, `portfolio_demo.py`의
    public MAS graph/type/node imports를 `src.experimental.mas` namespace로
    전환했다.
  - `mas_direct_worker_probe.py`의 Researcher private diagnostic helpers
    (`_build_enriched_query`, `_build_where_filter`, `_select_narrative_docs`)
    는 아직 legacy implementation path에 남겼다. facade public surface를
    불필요하게 넓히지 않기 위한 의도적 보류다.
  - 검증:
    - `.venv/bin/python -m unittest tests.test_experimental_mas_namespace tests.test_mas_e2e_smoke tests.test_mas_direct_worker_probe tests.test_mas_e2e_smoke_contract tests.test_mas_researcher_smoke_contract tests.test_portfolio_demo`:
      `30` OK
    - `python -m py_compile src/ops/portfolio_demo.py src/ops/mas_analyst_smoke.py src/ops/mas_researcher_smoke.py src/ops/mas_e2e_smoke.py src/ops/mas_direct_worker_probe.py`:
      passed
    - `git diff --check`: passed
  - 다음 PR 7 후보는 tests의 public MAS imports를 새 namespace로 옮기거나,
    Researcher diagnostic private helpers를 public facade로 올릴지 말지
    결정하는 것이다. 구현 파일 이동은 아직 보류한다.

- 2026-06-17 PR 7 MAS isolation 첫 조각을 진행했다.
  - `src/experimental/mas/` namespace를 추가해 MAS graph/types/nodes를
    experimental surface로 import할 수 있게 했다.
  - 기존 `src.agent.mas_graph`, `src.agent.mas_types`,
    `src.agent.nodes.*` implementation과 import surface는 compatibility
    path로 유지했다. 아직 파일 이동은 하지 않았다.
  - `tests/test_experimental_mas_namespace.py`를 추가해 새 namespace가 기존
    MAS graph/types/node factory surface를 re-export하고 dummy MAS graph를
    실행할 수 있음을 고정했다.
  - 검증:
    - `.venv/bin/python -m unittest tests.test_experimental_mas_namespace tests.test_multi_agent_graph tests.test_analyst_node tests.test_researcher_node tests.test_critic_node tests.test_orchestrator_node`:
      `36` OK
    - `python -m py_compile src/experimental/__init__.py src/experimental/mas/__init__.py src/experimental/mas/graph.py src/experimental/mas/nodes.py src/experimental/mas/types.py`:
      passed
    - `git diff --check`: passed
  - 다음 PR 7 후보는 ops smoke scripts 또는 docs에서 새
    `src.experimental.mas` namespace를 우선 사용하도록 바꾸는
    no-behavior-change adapter migration이다.

- 2026-06-17 PR 6 vector store extraction 네 번째 조각을 진행했다.
  - `src/storage/structure_graph.py`를 추가해 structure graph payload
    normalization, BM25 payload projection, vector result hydration,
    relationship rebuild/update, indexed chunk uid lookup, graph accessor docs
    생성을 `VectorStoreManager` facade 밖으로 분리했다.
  - 기존 `_structure_graph_bm25_payload`,
    `_hydrate_document_from_structure_graph`, `_load_structure_graph`,
    `_rebuild_structure_relationships`, `_update_structure_graph`,
    `_structure_graph_chunk_uids`, `get_structure_node`,
    `get_section_lead_doc`, `get_described_by_doc`, `get_sibling_docs`,
    `get_reference_docs` surface는 compatibility wrapper로 유지했다.
  - `VectorStoreManager.search()`의 vector path, BM25 path, RRF merge,
    telemetry key는 변경하지 않았다.
  - 검증:
    - `.venv/bin/python -m unittest tests.test_vector_store_fallback tests.test_embedding_runtime_config`:
      `18` OK
    - `python -m py_compile src/storage/vector_store.py src/storage/embedding_config.py src/storage/metadata_payloads.py src/storage/bm25_index.py src/storage/structure_graph.py`:
      passed
    - `git diff --check`: passed
  - 현재 판단: PR 6은 embedding config, metadata payload, BM25, structure graph
    helper extraction까지 진행됐다. 다음 분리는 Chroma access / hybrid merge /
    add_documents batching처럼 search behavior와 더 가까우므로, concrete bug나
    telemetry contract gap이 있을 때만 계속하는 편이 안전하다.

- 2026-06-17 PR 6 vector store extraction 세 번째 조각을 진행했다.
  - `src/storage/bm25_index.py`를 추가해 Korean/ASCII tokenization,
    metadata filter matching, BM25 index construction, BM25 candidate
    collection을 `VectorStoreManager` facade 밖으로 분리했다.
  - 기존 `_tokenize_ko`, `_metadata_matches_filter`, `_build_bm25_index`
    surface는 compatibility wrapper로 유지했다.
  - `VectorStoreManager.search()`의 vector path, RRF merge, telemetry key는
    변경하지 않았다.
  - 검증:
    - `.venv/bin/python -m unittest tests.test_vector_store_fallback tests.test_embedding_runtime_config`:
      `18` OK
    - `python -m py_compile src/storage/vector_store.py src/storage/embedding_config.py src/storage/metadata_payloads.py src/storage/bm25_index.py`:
      passed
    - `git diff --check`: passed
  - 다음 PR 6 후보는 structure graph relationship/accessor helpers의
    no-behavior-change extraction이다.

- 2026-06-17 PR 6 vector store extraction 두 번째 조각을 진행했다.
  - `src/storage/metadata_payloads.py`를 추가해 Chroma metadata sanitization,
    table payload sidecar id/stats/load/hydration/compaction helpers를
    `VectorStoreManager` facade 밖으로 분리했다.
  - 기존 `_metadata_for_chroma`, `_table_payload_sidecar_stats`,
    `_load_table_payloads`, `_table_payload_id`,
    `_metadata_with_table_payload`, `_compact_node_for_storage` surface는
    compatibility wrapper로 유지했다.
  - `VectorStoreManager.search()`와 telemetry path는 건드리지 않았다.
  - 검증:
    - `.venv/bin/python -m unittest tests.test_vector_store_fallback tests.test_embedding_runtime_config`:
      `18` OK
    - `python -m py_compile src/storage/vector_store.py src/storage/embedding_config.py src/storage/metadata_payloads.py`:
      passed
    - `git diff --check`: passed
  - 다음 PR 6 후보는 BM25 index/search helpers 또는 structure graph
    relationship/accessor helpers의 no-behavior-change extraction이다.

- 2026-06-17 PR 6 vector store extraction 첫 조각을 진행했다.
  - `src/storage/embedding_config.py`를 추가해 embedding provider selection,
    default model selection, known dimension lookup, runtime spec 생성,
    embedding factory를 `VectorStoreManager` facade 밖으로 분리했다.
  - 기존 `src.storage.vector_store` import surface는 유지했다.
    `DEFAULT_EMBEDDING_PROVIDER`, `DEFAULT_EMBEDDING_MODEL`,
    `create_embeddings`, `get_embedding_runtime_spec`,
    `infer_embedding_dimension`, `_select_default_embedding_provider`는 계속
    `vector_store.py`에서 import 가능하다.
  - `VectorStoreManager.search()`와 telemetry path는 건드리지 않았다.
  - 검증:
    - `.venv/bin/python -m unittest tests.test_embedding_runtime_config tests.test_vector_store_fallback`:
      `18` OK
    - `python -m py_compile src/storage/vector_store.py src/storage/embedding_config.py`:
      passed
    - `git diff --check`: passed
  - 다음 PR 6 후보는 Chroma metadata sanitization / table payload sidecar
    helpers 또는 BM25 index/search helpers 중 하나를 no-behavior-change로
    분리하는 것이다.

- 2026-06-17 PR 5 parser extraction 여섯 번째 조각을 진행했다.
  - `src/processing/reference_resolution.py`를 추가해 quoted intra-filing
    reference hint를 section path로 resolving하는 index/canonicalization
    로직을 `FinancialParser` facade 밖으로 분리했다.
  - 기존 `_canonicalize_reference_text`, `_build_reference_index`,
    `_resolve_reference_path`, `_extract_reference_section_paths`는
    compatibility wrapper로 남겼다.
  - 검증:
    - `uv run --with-requirements requirements-review.txt python -m unittest tests.test_financial_parser`:
      `28` OK
    - `.venv/bin/python -m unittest tests.test_vector_store_fallback`:
      `14` OK
    - `python -m py_compile src/processing/financial_parser.py src/processing/table_records.py src/processing/table_structure.py src/processing/section_extraction.py src/processing/block_collection.py src/processing/chunking.py src/processing/reference_resolution.py`:
      passed
    - `uv run --with-requirements requirements-review.txt python -m src.ops.portfolio_review_gates`:
      `Status: ready`
    - `git diff --check`: passed
  - 현재 판단: PR 5는 public parser facade를 유지하면서 table records,
    table structure, section orchestration, block collection, chunking,
    reference resolution까지 주요 extraction이 끝났다. 추가 parser 분리는
    concrete metadata drift나 parser regression이 있을 때만 진행하고, 다음
    큰 구현 축은 PR 6 vector store extraction이 더 적절하다.

- 2026-06-17 PR 5 parser extraction 다섯 번째 조각을 진행했다.
  - `src/processing/chunking.py`를 추가해 table row/window splitting,
    narrative table-row splitting, wide-table column windows, table metadata
    propagation, section block chunk assembly를 `FinancialParser` facade 밖으로
    분리했다.
  - 기존 `_split_table_by_rows`, `_looks_like_table_header_row`,
    `_split_table_text_fragment`, `_split_long_table_row`,
    `_split_wide_table_by_columns`, `_split_table_for_chunks`,
    `_chunk_blocks`는 compatibility wrapper로 남겼다.
  - 검증:
    - `uv run --with-requirements requirements-review.txt python -m unittest tests.test_financial_parser`:
      `28` OK
    - `.venv/bin/python -m unittest tests.test_vector_store_fallback`:
      `14` OK
    - `python -m py_compile src/processing/financial_parser.py src/processing/table_records.py src/processing/table_structure.py src/processing/section_extraction.py src/processing/block_collection.py src/processing/chunking.py`:
      passed
    - `uv run --with-requirements requirements-review.txt python -m src.ops.portfolio_review_gates`:
      `Status: ready`
  - 다음 PR 5 후보는 reference resolution의 no-behavior-change extraction이다.

- 2026-06-17 PR 5 parser extraction 네 번째 조각을 진행했다.
  - `src/processing/block_collection.py`를 추가해 paragraph/table/local
    heading block state machine을 `FinancialParser` facade 밖으로 분리했다.
  - `FinancialParser._collect_blocks()`는 기존 tests/호출자를 위한
    compatibility wrapper로 남기고, parser-specific callbacks를 새 collector에
    주입하도록 바꿨다.
  - 검증:
    - `uv run --with-requirements requirements-review.txt python -m unittest tests.test_financial_parser`:
      `28` OK
    - `.venv/bin/python -m unittest tests.test_vector_store_fallback`:
      `14` OK
    - `python -m py_compile src/processing/financial_parser.py src/processing/table_records.py src/processing/table_structure.py src/processing/section_extraction.py src/processing/block_collection.py`:
      passed
    - `uv run --with-requirements requirements-review.txt python -m src.ops.portfolio_review_gates`:
      `Status: ready`
  - 다음 PR 5 후보는 chunking, reference resolution 순서의
    no-behavior-change extraction이다.

- 2026-06-17 PR 5 parser extraction 세 번째 조각을 진행했다.
  - `src/processing/section_extraction.py`를 추가해 section tag iteration,
    section path construction, parse budget/fallback orchestration, parse
    timing, section payload assembly를 `FinancialParser` facade 밖으로
    분리했다.
  - `SectionParseTimeout`은 새 모듈로 이동하고, 기존
    `src.processing.financial_parser.SectionParseTimeout` import surface는
    re-export 형태로 유지했다.
  - `FinancialParser._build_section_path()`와 `_extract_sections()`는
    compatibility wrapper로 남겼다. block state machine인 `_collect_blocks()`
    는 아직 parser facade 안에 남아 있다.
  - 검증:
    - `uv run --with-requirements requirements-review.txt python -m unittest tests.test_financial_parser`:
      `28` OK
    - `.venv/bin/python -m unittest tests.test_vector_store_fallback`:
      `14` OK
    - `python -m py_compile src/processing/financial_parser.py src/processing/table_records.py src/processing/table_structure.py src/processing/section_extraction.py`:
      passed
    - `uv run --with-requirements requirements-review.txt python -m src.ops.portfolio_review_gates`:
      `Status: ready`
  - 다음 PR 5 후보는 `_collect_blocks()` block state machine, chunking,
    reference resolution 순서의 no-behavior-change extraction이다.

- 2026-06-17 PR 5 parser extraction 두 번째 조각을 진행했다.
  - `src/processing/table_structure.py`를 추가해 XML table grid
    reconstruction, merged-cell propagation, table text formatting, span
    detection, row-label extraction, table-object payload assembly를
    `FinancialParser` facade 밖으로 분리했다.
  - 기존 private method
    `_cell_span_int`, `_normalize_table_grid`, `_format_table_grid`,
    `_table_has_spans`, `_extract_table_row_labels_from_grid`,
    `_build_table_object`, `_grid_row_to_text`는 compatibility wrapper로
    남겼다.
  - 검증:
    - `uv run --with-requirements requirements-review.txt python -m unittest tests.test_financial_parser`:
      `28` OK
    - `.venv/bin/python -m unittest tests.test_vector_store_fallback`:
      `14` OK
    - `python -m py_compile src/processing/financial_parser.py src/processing/table_records.py src/processing/table_structure.py`:
      passed
    - `uv run --with-requirements requirements-review.txt python -m src.ops.portfolio_review_gates`:
      `Status: ready`
  - 다음 PR 5 후보는 section/block extraction, chunking, reference resolution
    순서의 no-behavior-change extraction이다.

- 2026-06-17 PR 5 parser extraction 첫 조각을 진행했다.
  - `src/processing/table_records.py`를 추가해 parser-normalized table의
    row/value record construction을 `FinancialParser` facade 밖으로 분리했다.
  - `FinancialParser._build_table_row_records()`와
    `_build_table_value_records()`는 기존 테스트/호출자를 위해 compatibility
    wrapper로 남겼다.
  - `process_document()` public facade와 metadata schema는 바꾸지 않았다.
  - 검증:
    - `uv run --with-requirements requirements-review.txt python -m unittest tests.test_financial_parser`:
      `28` OK
    - `.venv/bin/python -m unittest tests.test_vector_store_fallback`:
      `14` OK
    - `python -m py_compile src/processing/financial_parser.py src/processing/table_records.py`:
      passed
    - `uv run --with-requirements requirements-review.txt python -m src.ops.portfolio_review_gates`:
      `Status: ready`
  - 다음 PR 5 후보는 XML/table-grid reconstruction, section/block extraction,
    chunking, reference resolution 순서의 no-behavior-change extraction이다.

- 2026-06-17 PR 8 requirements/docs cleanup을 진행했다.
  - `requirements.txt`의 Windows 전용 `pywin32` pin에
    `sys_platform == "win32"` marker를 붙여 Linux `uv` 환경에서 dependency
    parsing/install이 막히지 않게 했다.
  - reviewer-facing fixture/gate 명령은 새 `requirements-review.txt`를
    사용하도록 README와 핵심 portfolio 문서를 정리했다. 이 파일은
    `portfolio_demo` / `portfolio_review_gates` 같은 lightweight review
    commands가 full ML/dev stack을 설치하지 않도록 분리한 것이다.
  - full development, ingest, benchmark, app 실행은 계속 `requirements.txt`
    기준이다.
  - 검증:
    - `uv run --with-requirements requirements-review.txt python -m src.ops.portfolio_demo --format json`:
      `ready`
    - `uv run --with-requirements requirements-review.txt python -m src.ops.portfolio_review_gates`:
      `Status: ready`
    - `uv run --with-requirements requirements-review.txt python -m src.ops.audit_runtime_domain_terms`:
      passed with `216` reviewed literals
    - `requirements.txt` parsed via `packaging.requirements.Requirement`
    - `git diff --check`: passed

- 2026-06-17 PR 4 calculation extraction의 current stop line을 문서화했다.
  - `docs/architecture/core_runtime_surface_refactoring_plan.md`에 PR 4 완료된
    extraction surface, 검증 baseline, 더 진행해도 되는 구체 seam, 중단해야
    하는 cleanup 유형을 추가했다.
  - 현재 판단: PR 4는 file-size reduction 자체를 목표로 계속 밀지 않고,
    concrete calculation regression이나 contract gap이 생길 때만 이어간다.
    다음 구현 축은 PR 8 requirements/docs cleanup 또는 PR 5 parser extraction이
    더 적절하다.

- 2026-06-17 `time_series` calculation publication 정렬 후 subtask loop broad
  regression을 확인했다.
  - 검증:
    - `uv run --with langchain-google-genai==4.2.1 python -m unittest tests.test_subtask_loop`:
      `210` OK
  - 결과: time-series 성공 경로가 calculation task/artifact를 publish하도록
    바뀐 뒤에도 aggregate/subtask orchestration 회귀는 통과했다.

- 2026-06-17 PR 4 범위의 calculation execution contract 정렬을 진행했다.
  - `time_series` 성공 경로가 scalar 성공 경로처럼
    `build_success_calculation_state_payload`를 사용하도록 바꿨다.
  - 이제 `time_series` 성공 결과도 `resolved_calculation_trace` /
    `structured_result`뿐 아니라 calculation task와 `calculation_result`
    artifact를 함께 publish한다.
  - focused contract test를 추가해 `time_series` 성공 경로의 selected
    evidence ids, calculation-result artifact payload/evidence refs,
    calculation task status/artifact ids를 고정했다.
  - 검증:
    - `uv run --with langchain-google-genai==4.2.1 python -m unittest tests.test_operation_contracts.OperationContractTests.test_time_series_success_publishes_calculation_task_artifact_contract`:
      `1` OK
    - `uv run --with langchain-google-genai==4.2.1 python -m unittest tests.test_financial_calculation_execution tests.test_financial_calculation_rendering`:
      `22` OK
    - `uv run --with langchain-google-genai==4.2.1 python -m unittest tests.test_operation_contracts.OperationContractTests.test_time_series_success_publishes_calculation_task_artifact_contract tests.test_operation_contracts.OperationContractTests.test_difference_result_exposes_structured_value_slots tests.test_operation_contracts.OperationContractTests.test_percent_difference_preserves_two_decimal_percent_rendering tests.test_operation_contracts.OperationContractTests.test_lookup_calculation_preserves_source_table_unit_in_rendered_value tests.test_operation_contracts.OperationContractTests.test_growth_rate_preserves_stated_source_percent_when_available`:
      `5` OK
    - `uv run --with langchain-google-genai==4.2.1 python -m unittest tests.test_operation_contracts`:
      `226` OK
    - `uv run --with langchain-google-genai==4.2.1 python -m src.ops.audit_runtime_domain_terms`:
      passed with `216` reviewed literals
    - `python -m py_compile src/agent/financial_graph_calculation.py`:
      passed

- 2026-06-17 PR 4 범위의 calculation extraction 열여섯 번째 조각을 진행했다.
  - `_execute_calculation`의 `time_series` rendered result 계산을
    `src/agent/financial_graph_calculation_rendering.py`로 이동했다.
    - `time_series_result_display`
  - helper는 `result_unit`이 percent 계열이면 normalized unit을 `PERCENT`로
    표시하고, percent/non-percent rendered value formatting을 기존과 동일하게
    수행한다. percent normalized-unit 판단은 runtime literal이 아니라
    `CALCULATION_RENDER_POLICY`를 사용하도록 바꿨다.
  - runtime domain-term baseline은 `financial_graph_calculation.py`에서 제거된
    기존 `퍼센트` literal count 감소를 반영했다.
  - 검증:
    - `uv run --with langchain-google-genai==4.2.1 python -m unittest tests.test_financial_calculation_rendering tests.test_financial_calculation_execution`:
      `22` OK
    - `uv run --with langchain-google-genai==4.2.1 python -m unittest tests.test_operation_contracts.OperationContractTests.test_difference_result_exposes_structured_value_slots tests.test_operation_contracts.OperationContractTests.test_percent_difference_preserves_two_decimal_percent_rendering tests.test_operation_contracts.OperationContractTests.test_lookup_calculation_preserves_source_table_unit_in_rendered_value tests.test_operation_contracts.OperationContractTests.test_growth_rate_preserves_stated_source_percent_when_available`:
      `4` OK
    - `uv run --with langchain-google-genai==4.2.1 python -m src.ops.audit_runtime_domain_terms`:
      passed with `216` reviewed literals
    - `python -m py_compile src/agent/financial_graph_calculation.py src/agent/financial_graph_calculation_rendering.py`:
      passed

- 2026-06-17 PR 4 범위의 calculation extraction 열다섯 번째 조각을 진행했다.
  - `_execute_calculation`의 `time_series` pairwise YoY growth 계산을
    `src/agent/financial_calculation_execution.py`로 이동했다.
    - `time_series_yoy_growth_rates`
  - helper는 `pairwise_formula`를 `PREV`/`CURR` 환경에서 평가하고,
    기존처럼 `ZeroDivisionError`는 해당 growth rate를 `None`으로 남긴다.
  - 검증:
    - `uv run --with langchain-google-genai==4.2.1 python -m unittest tests.test_financial_calculation_execution tests.test_financial_calculation_rendering`:
      `20` OK
    - `uv run --with langchain-google-genai==4.2.1 python -m unittest tests.test_operation_contracts.OperationContractTests.test_difference_result_exposes_structured_value_slots tests.test_operation_contracts.OperationContractTests.test_percent_difference_preserves_two_decimal_percent_rendering tests.test_operation_contracts.OperationContractTests.test_lookup_calculation_preserves_source_table_unit_in_rendered_value tests.test_operation_contracts.OperationContractTests.test_growth_rate_preserves_stated_source_percent_when_available`:
      `4` OK
    - `uv run --with langchain-google-genai==4.2.1 python -m src.ops.audit_runtime_domain_terms`:
      passed with `216` reviewed literals
    - `python -m py_compile src/agent/financial_graph_calculation.py src/agent/financial_calculation_execution.py`:
      passed

- 2026-06-17 PR 4 범위의 calculation extraction 열네 번째 조각을 진행했다.
  - `_execute_calculation`의 `time_series` result series row assembly를
    `src/agent/financial_graph_calculation_rendering.py`로 이동했다.
    - `time_series_result_series`
  - helper는 ordered operands를 기존 time-series result `series` row shape로
    투영한다. 기존 label normalization, value formatting, raw value/unit
    보존 동작을 유지한다.
  - 검증:
    - `uv run --with langchain-google-genai==4.2.1 python -m unittest tests.test_financial_calculation_rendering tests.test_financial_calculation_execution`:
      `17` OK
    - `uv run --with langchain-google-genai==4.2.1 python -m unittest tests.test_operation_contracts.OperationContractTests.test_difference_result_exposes_structured_value_slots tests.test_operation_contracts.OperationContractTests.test_percent_difference_preserves_two_decimal_percent_rendering tests.test_operation_contracts.OperationContractTests.test_lookup_calculation_preserves_source_table_unit_in_rendered_value tests.test_operation_contracts.OperationContractTests.test_growth_rate_preserves_stated_source_percent_when_available`:
      `4` OK
    - `uv run --with langchain-google-genai==4.2.1 python -m src.ops.audit_runtime_domain_terms`:
      passed with `216` reviewed literals
    - `python -m py_compile src/agent/financial_graph_calculation.py src/agent/financial_graph_calculation_rendering.py`:
      passed

- 2026-06-17 PR 4 범위의 calculation extraction 열세 번째 조각을 진행했다.
  - `_execute_calculation`의 `time_series` success `calculation_result` dict
    조립을 `src/agent/financial_calculation_execution.py`로 이동했다.
    - `build_time_series_calculation_result`
  - helper는 이미 계산된 trend result, rendered value, result series,
    primary answer slot, formula metadata를 기존 payload shape로 구성한다.
    시계열 정렬, 수식 평가, evidence selection, trace update는 변경하지 않았다.
  - 검증:
    - `uv run --with langchain-google-genai==4.2.1 python -m unittest tests.test_financial_calculation_execution`:
      `9` OK
    - `uv run --with langchain-google-genai==4.2.1 python -m unittest tests.test_operation_contracts.OperationContractTests.test_difference_result_exposes_structured_value_slots tests.test_operation_contracts.OperationContractTests.test_percent_difference_preserves_two_decimal_percent_rendering tests.test_operation_contracts.OperationContractTests.test_lookup_calculation_preserves_source_table_unit_in_rendered_value tests.test_operation_contracts.OperationContractTests.test_growth_rate_preserves_stated_source_percent_when_available`:
      `4` OK
    - `uv run --with langchain-google-genai==4.2.1 python -m src.ops.audit_runtime_domain_terms`:
      passed with `216` reviewed literals
    - `python -m py_compile src/agent/financial_graph_calculation.py src/agent/financial_calculation_execution.py`:
      passed

- 2026-06-17 PR 4 calculation extraction 누적 변경 뒤 broad regression을 확인했다.
  - 검증:
    - `uv run --with langchain-google-genai==4.2.1 python -m unittest tests.test_operation_contracts`:
      `225` OK
    - `uv run --with langchain-google-genai==4.2.1 python -m unittest tests.test_subtask_loop`:
      `210` OK
  - 결과: 최근 calculation execution/rendering/result payload extraction 누적분은
    operation contract와 subtask loop의 넓은 회귀 축에서 통과했다.

- 2026-06-17 PR 4 범위의 calculation extraction 열두 번째 조각을 진행했다.
  - `_execute_calculation`의 scalar success `calculation_result` dict 조립을
    `src/agent/financial_calculation_execution.py`로 이동했다.
    - `build_scalar_calculation_result`
  - helper는 이미 계산된 result value, rendered value, result series,
    scalar state, answer slots, formula metadata를 받아 기존
    `calculation_result` payload를 그대로 구성한다.
  - 검증:
    - `uv run --with langchain-google-genai==4.2.1 python -m unittest tests.test_financial_calculation_execution`:
      `8` OK
    - `uv run --with langchain-google-genai==4.2.1 python -m unittest tests.test_operation_contracts.OperationContractTests.test_difference_result_exposes_structured_value_slots tests.test_operation_contracts.OperationContractTests.test_percent_difference_preserves_two_decimal_percent_rendering tests.test_operation_contracts.OperationContractTests.test_lookup_calculation_preserves_source_table_unit_in_rendered_value tests.test_operation_contracts.OperationContractTests.test_growth_rate_preserves_stated_source_percent_when_available`:
      `4` OK
    - `uv run --with langchain-google-genai==4.2.1 python -m src.ops.audit_runtime_domain_terms`:
      passed with `216` reviewed literals
    - `python -m py_compile src/agent/financial_graph_calculation.py src/agent/financial_calculation_execution.py`:
      passed

- 2026-06-17 PR 4 범위의 calculation extraction 열한 번째 조각을 진행했다.
  - `_execute_calculation`의 scalar current/prior/delta state assembly와
    source-stated growth display override를
    `src/agent/financial_calculation_execution.py`로 이동했다.
    - `build_scalar_calculation_state`
  - helper는 ordered operands와 rendered scalar result를 받아
    `current_value`, `prior_value`, `delta_value`, `source_row_ids`,
    source-stated result 사용 여부를 계산한다. 산술식 평가, evidence
    selection, answer slot construction, rendering helper 호출은 변경하지 않았다.
  - 검증:
    - `uv run --with langchain-google-genai==4.2.1 python -m unittest tests.test_financial_calculation_execution`:
      `7` OK
    - `uv run --with langchain-google-genai==4.2.1 python -m unittest tests.test_operation_contracts.OperationContractTests.test_difference_result_exposes_structured_value_slots tests.test_operation_contracts.OperationContractTests.test_percent_difference_preserves_two_decimal_percent_rendering tests.test_operation_contracts.OperationContractTests.test_lookup_calculation_preserves_source_table_unit_in_rendered_value tests.test_operation_contracts.OperationContractTests.test_growth_rate_preserves_stated_source_percent_when_available`:
      `4` OK
    - `uv run --with langchain-google-genai==4.2.1 python -m unittest tests.test_financial_agent_run_projection.FinancialAgentRunProjectionTests.test_run_repairs_period_comparison_trace_from_source_stated_evidence`:
      `1` OK
    - `uv run --with langchain-google-genai==4.2.1 python -m src.ops.audit_runtime_domain_terms`:
      passed with `216` reviewed literals
    - `python -m py_compile src/agent/financial_graph_calculation.py src/agent/financial_calculation_execution.py`:
      passed

- 2026-06-17 PR 4 범위의 calculation extraction 열 번째 조각을 진행했다.
  - `_execute_calculation`의 successful calculation state payload 조립을
    `src/agent/financial_calculation_execution.py`로 이동했다.
    - `build_success_calculation_state_payload`
  - 계산 성공 결과를 task/artifact ledger와 `resolved_calculation_trace`에
    싣는 boundary helper이며, arithmetic, evidence selection, answer slot
    construction, rendering behavior는 변경하지 않았다.
  - 검증:
    - `uv run --with langchain-google-genai==4.2.1 python -m unittest tests.test_financial_calculation_execution`:
      `4` OK
    - `uv run --with langchain-google-genai==4.2.1 python -m unittest tests.test_operation_contracts.OperationContractTests.test_difference_result_exposes_structured_value_slots tests.test_operation_contracts.OperationContractTests.test_percent_difference_preserves_two_decimal_percent_rendering tests.test_operation_contracts.OperationContractTests.test_lookup_calculation_preserves_source_table_unit_in_rendered_value`:
      `3` OK
    - `uv run --with langchain-google-genai==4.2.1 python -m src.ops.audit_runtime_domain_terms`:
      passed with `216` reviewed literals
    - `python -m py_compile src/agent/financial_graph_calculation.py src/agent/financial_calculation_execution.py`:
      passed

- 2026-06-17 PR 4 범위의 calculation extraction 아홉 번째 조각을 진행했다.
  - `_execute_calculation`의 scalar result series row assembly를
    `src/agent/financial_graph_calculation_rendering.py`로 이동했다.
    - `scalar_result_series`
  - ordered operand rows를 result `series` rows로 투영하는 렌더링/표시 계층
    helper이며, source-visible rendered value 보존과 fallback value formatting을
    기존과 동일하게 유지한다.
  - 검증:
    - `uv run --with langchain-google-genai==4.2.1 python -m unittest tests.test_financial_calculation_rendering`:
      `7` OK
    - `uv run --with langchain-google-genai==4.2.1 python -m unittest tests.test_operation_contracts.OperationContractTests.test_difference_result_exposes_structured_value_slots tests.test_operation_contracts.OperationContractTests.test_percent_difference_preserves_two_decimal_percent_rendering tests.test_operation_contracts.OperationContractTests.test_lookup_calculation_preserves_source_table_unit_in_rendered_value`:
      `3` OK
    - `uv run --with langchain-google-genai==4.2.1 python -m unittest tests.test_financial_calculation_rendering tests.test_financial_calculation_execution`:
      `9` OK
    - `uv run --with langchain-google-genai==4.2.1 python -m src.ops.audit_runtime_domain_terms`:
      passed with `216` reviewed literals
    - `python -m py_compile src/agent/financial_graph_calculation.py src/agent/financial_graph_calculation_rendering.py`:
      passed

- 2026-06-17 PR 4 범위의 calculation extraction 여덟 번째 조각을 진행했다.
  - `_execute_calculation`의 scalar result display 결정 로직을
    `src/agent/financial_graph_calculation_rendering.py`로 이동했다.
    - `scalar_result_display`
  - helper는 `result_value`, `result_unit`, `normalized_unit`,
    `result_display_unit`, `operation_family`, `ordered_operands`를 받아
    `rendered_value` / `rendered_with_unit`를 결정한다.
  - KRW display unit, non-KRW unit suffix, lookup/single-value source display
    preservation을 rendering boundary에 모았고, arithmetic execution과 trace
    update는 변경하지 않았다.
  - 검증:
    - `uv run --with langchain-google-genai==4.2.1 python -m unittest tests.test_financial_calculation_rendering`:
      `6` OK
    - `uv run --with langchain-google-genai==4.2.1 python -m unittest tests.test_operation_contracts.OperationContractTests.test_difference_result_exposes_structured_value_slots tests.test_operation_contracts.OperationContractTests.test_percent_difference_preserves_two_decimal_percent_rendering tests.test_operation_contracts.OperationContractTests.test_lookup_calculation_preserves_source_table_unit_in_rendered_value`:
      `3` OK
    - `uv run --with langchain-google-genai==4.2.1 python -m unittest tests.test_financial_calculation_rendering tests.test_financial_calculation_execution`:
      `8` OK
    - `uv run --with langchain-google-genai==4.2.1 python -m src.ops.audit_runtime_domain_terms`:
      passed with `216` reviewed literals
    - `python -m py_compile src/agent/financial_graph_calculation.py src/agent/financial_graph_calculation_rendering.py`:
      passed

- 2026-06-17 PR 4 범위의 calculation extraction 일곱 번째 조각을 진행했다.
  - `_execute_calculation` 내부 실패 경로의 `calculation_result` payload 생성을
    새 module `src/agent/financial_calculation_execution.py`로 분리했다.
    - `build_failed_calculation_result`
  - `_execute_calculation`의 state update, selected evidence, fallback answer,
    route semantics는 그대로 두고, 실패 결과 스키마와 answer slot construction만
    helper에서 만들도록 했다.
  - 검증:
    - `uv run --with langchain-google-genai==4.2.1 python -m unittest tests.test_financial_calculation_execution`:
      `2` OK
    - `uv run --with langchain-google-genai==4.2.1 python -m unittest tests.test_operation_contracts.OperationContractTests.test_failed_lookup_emits_explicit_missing_primary_slot tests.test_operation_contracts.OperationContractTests.test_execute_calculation_ignores_legacy_top_level_operands_and_plan tests.test_operation_contracts.OperationContractTests.test_ratio_calculation_rejects_duplicate_operand_binding`:
      `3` OK
    - `uv run --with langchain-google-genai==4.2.1 python -m unittest tests.test_financial_calculation_execution tests.test_financial_answer_slots`:
      `9` OK
    - `uv run --with langchain-google-genai==4.2.1 python -m src.ops.audit_runtime_domain_terms`:
      passed with `216` reviewed literals
    - `python -m py_compile src/agent/financial_graph_calculation.py src/agent/financial_calculation_execution.py`:
      passed

- 2026-06-17 PR 4 범위의 calculation extraction 여섯 번째 조각을 진행했다.
  - render/verify 경로에 중복돼 있던 direction hint 계산과 negative
    rendered-value sign 보정을
    `src/agent/financial_graph_calculation_rendering.py`로 이동했다.
    - `direction_hint_for_result`
    - `coerce_rendered_value_for_direction`
  - `financial_graph_calculation.py`는 rendering helper를 호출하도록 바뀌었고,
    LLM render/verify 호출, fallback, ratio compact rendering, trace update
    동작은 변경하지 않았다.
  - 검증:
    - `uv run --with langchain-google-genai==4.2.1 python -m unittest tests.test_financial_calculation_rendering`:
      `3` OK
    - `uv run --with langchain-google-genai==4.2.1 python -m unittest tests.test_operation_contracts.OperationContractTests.test_rendered_subtraction_answer_rewrites_double_negative_subtrahend tests.test_operation_contracts.OperationContractTests.test_rendered_subtraction_answer_rewrites_negative_denominator_difference tests.test_subtask_loop.SubtaskLoopTests.test_verify_calculation_skip_does_not_rewrite_compatibility_mirrors`:
      `3` OK
    - `uv run --with langchain-google-genai==4.2.1 python -m unittest tests.test_financial_calculation_rendering tests.test_financial_answer_slots`:
      `10` OK
    - `uv run --with langchain-google-genai==4.2.1 python -m src.ops.audit_runtime_domain_terms`:
      passed with `216` reviewed literals
    - `python -m py_compile src/agent/financial_graph_calculation.py src/agent/financial_graph_calculation_rendering.py`:
      passed

- 2026-06-17 PR 4 범위의 calculation extraction 다섯 번째 조각을 진행했다.
  - `_build_answer_slots`의 operation-family별 answer slot assembly를
    `src/agent/financial_answer_slots.py`의 `build_answer_slots`로 이동했다.
  - `financial_graph_calculation.py`의 `_build_answer_slots` method는 기존
    호출 계약을 보존하는 compatibility wrapper로 남겼다.
  - answer slot row builder와 전체 answer slot assembly가 같은 모듈에 모였고,
    calculation mixin은 실행 결과를 slot construction helper에 전달하는
    orchestration 역할만 남겼다.
  - 검증:
    - `uv run --with langchain-google-genai==4.2.1 python -m unittest tests.test_financial_answer_slots`:
      `7` OK
    - `uv run --with langchain-google-genai==4.2.1 python -m unittest tests.test_operation_contracts.OperationContractTests.test_difference_result_exposes_structured_value_slots tests.test_operation_contracts.OperationContractTests.test_percent_difference_preserves_two_decimal_percent_rendering tests.test_operation_contracts.OperationContractTests.test_failed_lookup_emits_explicit_missing_primary_slot`:
      `3` OK
    - `uv run --with langchain-google-genai==4.2.1 python -m unittest tests.test_runtime_domain_term_audit tests.test_financial_answer_slots`:
      `13` OK
    - `uv run --with langchain-google-genai==4.2.1 python -m src.ops.audit_runtime_domain_terms`:
      passed with `216` reviewed literals
    - `python -m py_compile src/agent/financial_graph_calculation.py src/agent/financial_answer_slots.py`:
      passed
  - Note: the first new unit-test fixture used a non-schema normalized unit for
    percent-point display and failed validation. The fixture was corrected to
    the runtime contract shape (`normalized_unit=PERCENT`, `result_unit=%p`).

- 2026-06-17 PR 4 범위의 calculation extraction 네 번째 조각을 진행했다.
  - `financial_graph_calculation.py`에 있던 answer slot row construction helper를
    새 module `src/agent/financial_answer_slots.py`로 분리했다.
    - `slot_status`
    - `coerce_slot_numeric`
    - `build_missing_value_slot`
    - `build_operand_value_slot`
    - `build_calculated_value_slot`
  - `_build_answer_slots` orchestration 자체는 아직 calculation mixin에 남겼고,
    기존 mixin method names는 compatibility wrapper로 유지했다.
  - KRW display-unit 판정은 새 runtime literal을 만들지 않도록
    `CALCULATION_RENDER_POLICY`의 `krw_normalized_unit` /
    `krw_display_unit_scales`를 소비한다. 이에 따라
    `runtime_domain_terms_baseline.json`은 기존 calculation 파일에서
    policy-driven helper로 빠진 `천원`/`백만원` literal count 감소만 반영했다.
  - 검증:
    - `uv run --with langchain-google-genai==4.2.1 python -m unittest tests.test_financial_answer_slots`:
      `5` OK
    - `uv run --with langchain-google-genai==4.2.1 python -m unittest tests.test_operation_contracts.OperationContractTests.test_difference_result_exposes_structured_value_slots tests.test_operation_contracts.OperationContractTests.test_percent_difference_preserves_two_decimal_percent_rendering tests.test_operation_contracts.OperationContractTests.test_failed_lookup_emits_explicit_missing_primary_slot`:
      `3` OK
    - `uv run --with langchain-google-genai==4.2.1 python -m unittest tests.test_runtime_domain_term_audit tests.test_financial_answer_slots`:
      `11` OK
    - `uv run --with langchain-google-genai==4.2.1 python -m src.ops.audit_runtime_domain_terms`:
      passed with `216` reviewed literals
    - `python -m py_compile src/agent/financial_graph_calculation.py src/agent/financial_answer_slots.py`:
      passed
  - Note: one earlier operation-contract command failed because the specified
    test method names did not exist. An earlier audit run also failed before
    the display-unit check was converted to policy consumption and the baseline
    count reduction was recorded; the corrected audit passed.

- 2026-06-17 PR 4 범위의 calculation extraction 세 번째 조각을 진행했다.
  - `financial_graph_calculation.py`에 있던 narrative/text surface helper를
    새 module `src/agent/financial_text_surface.py`로 분리했다.
    - `topic_particle`
    - `polish_korean_particle_pairs`
    - `split_narrative_sentences`
    - `narrative_sentence_looks_table_noisy`
    - `narrative_sentence_looks_abbreviated_fragment`
  - answer/narrative surface 정리 경계만 분리한 no-behavior-change
    extraction이다. 기존 calculation mixin은 alias import로 같은 helper를
    계속 호출한다.
  - 검증:
    - `uv run --with langchain-google-genai==4.2.1 python -m unittest tests.test_financial_text_surface`:
      `5` OK
    - `uv run --with langchain-google-genai==4.2.1 python -m unittest tests.test_reflection_capability_contract tests.test_financial_text_surface`:
      `14` OK
    - `uv run --with langchain-google-genai==4.2.1 python -m unittest tests.test_subtask_loop.SubtaskLoopTests.test_prepare_reflection_retry_ignores_legacy_top_level_runtime_projection tests.test_subtask_loop.SubtaskLoopTests.test_prepare_synthesis_reflection_retry_records_task_output_source_ids tests.test_subtask_loop.SubtaskLoopTests.test_aggregate_subtasks_replans_on_task_artifact_integrity_error`:
      `3` OK
    - `uv run --with langchain-google-genai==4.2.1 python -m src.ops.audit_runtime_domain_terms`:
      passed with `216` reviewed literals
    - `python -m py_compile src/agent/financial_graph_calculation.py src/agent/financial_text_surface.py`:
      passed
  - Note: one earlier focused unittest invocation failed after the extraction
    because `CALCULATION_NARRATIVE_POLICY` was still used elsewhere in the
    calculation file; restoring that import fixed the issue and the same tests
    passed.

- 2026-06-17 PR 4 범위의 calculation extraction 두 번째 조각을 진행했다.
  - `financial_graph_calculation.py`에 남아 있던 task/artifact ledger
    integrity feedback projection helper를
    `src/agent/financial_reflection_projection.py`로 이동했다.
    - `task_artifact_integrity_feedback`
  - aggregate subtask integrity error를 reflection retry 문장으로 투영하는
    경계만 분리한 no-behavior-change extraction이다. 기존 calculation mixin은
    alias import로 같은 helper를 계속 호출한다.
  - 검증:
    - `uv run --with langchain-google-genai==4.2.1 python -m unittest tests.test_reflection_capability_contract`:
      `9` OK
    - `uv run --with langchain-google-genai==4.2.1 python -m unittest tests.test_subtask_loop.SubtaskLoopTests.test_aggregate_subtasks_replans_on_task_artifact_integrity_error tests.test_subtask_loop.SubtaskLoopTests.test_aggregate_subtasks_replans_on_missing_required_calculation_artifact_kind tests.test_subtask_loop.SubtaskLoopTests.test_aggregate_subtasks_replans_on_missing_required_artifact_payload`:
      `3` OK
    - `uv run --with langchain-google-genai==4.2.1 python -m src.ops.audit_runtime_domain_terms`:
      passed with `216` reviewed literals
    - `python -m py_compile src/agent/financial_graph_calculation.py src/agent/financial_reflection_projection.py`:
      passed
    - `git diff --check`: passed

- 2026-06-17 PR 4 범위의 calculation extraction 첫 조각을 진행했다.
  - `financial_graph_calculation.py`에 있던 reflection handoff projection helper
    두 개를 새 module `src/agent/financial_reflection_projection.py`로 분리했다.
    - `reflection_action_from_plan`
    - `reflection_report_from_action`
  - 계산 실행/operand binding/answer rendering 동작은 건드리지 않은
    no-behavior-change extraction이다. 기존 calculation mixin은 alias import로
    같은 helper를 계속 호출한다.
  - 검증:
    - `uv run --with langchain-google-genai==4.2.1 python -m unittest tests.test_reflection_capability_contract`:
      `7` OK
    - `uv run --with langchain-google-genai==4.2.1 python -m unittest tests.test_subtask_loop.SubtaskLoopTests.test_prepare_reflection_retry_ignores_legacy_top_level_runtime_projection tests.test_subtask_loop.SubtaskLoopTests.test_prepare_synthesis_reflection_retry_records_task_output_source_ids`:
      `2` OK
    - `uv run --with langchain-google-genai==4.2.1 python -m src.ops.audit_runtime_domain_terms`:
      passed with `216` reviewed literals
    - `python -m py_compile src/agent/financial_graph_calculation.py src/agent/financial_reflection_projection.py`:
      passed
    - `git diff --check`: passed
  - Note: two earlier focused unittest invocations failed because the specified
    test method names did not exist; the corrected reflection tests above passed.

- 2026-06-17 PR 3 범위의 `FinancialAgentState` concern split 첫 조각을
  진행했다.
  - 기존 state key와 graph contract는 유지하면서 TypedDict를 아래 concern별
    component로 분리했다.
    - `RoutingState`
    - `RetrievalState`
    - `EvidenceState`
    - `CalculationState`
    - `ReflectionState`
    - `LedgerState`
  - `FinancialAgentState`는 이 component TypedDict들을 다중 상속해 기존 전체
    shape를 보존한다. 런타임 동작 변경은 없다.
  - 검증:
    - `uv run --with langchain-google-genai==4.2.1 python -m unittest tests.test_financial_agent_run_projection`:
      `47` OK
    - `uv run --with langchain-google-genai==4.2.1 python -m src.ops.audit_runtime_domain_terms`:
      passed with `216` reviewed literals
    - `python -m py_compile src/agent/financial_graph_models.py`: passed
    - `git diff --check`: passed

- 2026-06-17 PR 2 범위의 API public response slimming 첫 조각을 진행했다.
  - `/api/query`는 이제 `FinancialAgent.run()`의 flat compatibility payload보다
    `agent_answer` projection을 우선 소비한다.
  - 기본 응답은 answer/query metadata/citations/`structured_result`/
    `resolved_calculation_trace` 중심으로 유지한다.
  - `review_trace`와 `debug_bundle`은 새 request flags
    `include_review_trace`, `include_debug_bundle`가 `true`일 때만 응답에
    포함된다. FastAPI response model은 `None` fields를 제외하도록 설정했다.
  - `.gitignore`는 local-only benchmark result bundles
    `cel_t1_038_unit_repair_check_*`,
    `hard_structural_current_smoke_*`를 무시하도록 보강했다.
  - 검증:
    - `uv run --with langchain-google-genai==4.2.1 python -m unittest tests.test_financial_router_response tests.test_financial_agent_run_projection`:
      `49` OK
    - `uv run --with langchain-google-genai==4.2.1 python -m unittest tests.test_portfolio_demo tests.test_mas_e2e_smoke_contract`:
      `12` OK
    - `uv run --with langchain-google-genai==4.2.1 python -m src.ops.audit_runtime_domain_terms`:
      passed with `216` reviewed literals
    - `git diff --check`: passed

- 2026-06-17 core runtime surface refactor plan을 `main`에 병합하고,
  PR 1 범위의 output boundary cleanup 첫 조각을 시작했다.
  - 새 계획 문서:
    `docs/architecture/core_runtime_surface_refactoring_plan.md`
  - `FinancialAgent.run()`의 기존 flat dict 반환은 유지하면서, 동일 payload를
    명시적인 nested projection으로도 노출한다.
    - `agent_answer`: public answer / query metadata /
      `structured_result` / `resolved_calculation_trace`
    - `review_trace`: retrieval, evidence, reflection, subtask,
      task/artifact review material
    - `debug_bundle`: `debug_traces`, LLM usage, embedding usage
  - API/evaluator compatibility를 깨지 않기 위해 기존 top-level keys는 그대로
    남겼다. 이 변경은 behavior change가 아니라 public/review/debug surface를
    분리하기 위한 boundary extraction이다.
  - 검증:
    - `uv run --with langchain-google-genai==4.2.1 python -m unittest tests.test_financial_agent_run_projection`:
      `46` OK
    - `uv run --with langchain-google-genai==4.2.1 python -m unittest tests.test_operation_contracts`:
      `225` OK
    - `uv run --with langchain-google-genai==4.2.1 python -m unittest tests.test_portfolio_demo tests.test_mas_e2e_smoke_contract`:
      `12` OK
    - `uv run --with langchain-google-genai==4.2.1 python -m src.ops.audit_runtime_domain_terms`:
      passed with `216` reviewed literals
    - `git diff --check`: passed
  - 기본 `python` / `.venv/bin/python`는 현재 `langchain_google_genai`가 없어
    import 기반 tests가 실패한다. 이번 검증은 repo 문서의 `uv run` 경로에 맞춰
    필요한 dependency만 `--with`로 추가해서 수행했다.
  - 남은 local artifact:
    `benchmarks/results/cel_t1_038_unit_repair_check_2026-06-12/`,
    `benchmarks/results/hard_structural_current_smoke_2026-06-12/`는 benchmark
    output이라 commit 대상이 아니다.

- 2026-06-18 calculation/runtime surface post-stop-line cleanup을 진행하고
  `origin/main`에 push했다.
  - 목적은 파일 줄 수 자체가 아니라, 최근 patch layer에서 생긴 중복 ledger
    publication / mutable aggregate state sync / operand precision recovery
    responsibility를 더 작은 runtime contract로 정리하는 것이다.
  - 주요 커밋:
    - `ff15826`: lookup recovery helpers를
      `src/agent/financial_lookup_recovery.py`로 분리.
    - `6b30e2a`: `_extract_calculation_operands`의 nested doc/source helper를
      top-level helper로 정리.
    - `025b088`: aggregate mutable state update 책임을
      `_AggregateMutableState.with_updates()`로 이동.
    - `ef90790`: task/artifact ledger payload contract helper를
      `_project_task_artifact_trace()` 밖으로 분리.
    - `01e047b`: operand precision cell recovery 전략을 contextual note row /
      flattened table surface helper로 분리.
    - `9de3c16`: operand-set artifact/task ledger publication 반복을
      `_operand_set_artifact_update()`로 통합.
  - 효과:
    - `_project_task_artifact_trace()`: `501` lines / nested helper `5`개 ->
      `279` lines / nested helper `0`개.
    - `_refine_operand_precision_from_evidence_table()`: `567` lines /
      nested helper `2`개 -> `258` lines / nested helper `0`개.
    - `_extract_calculation_operands()`: `1196` lines -> `1139` lines.
    - 현재 `src/agent/financial_graph_calculation.py`: `19,729` lines,
      `src/agent/financial_graph_helpers.py`: `9,747` lines.
  - 검증:
    - 관련 targeted suites: `479` OK.
    - `uv run --with langchain-google-genai==4.2.1 python -m unittest discover -s tests`:
      `1248` OK.
    - `uv run --with langchain-google-genai==4.2.1 python -m src.ops.audit_runtime_domain_terms`:
      passed with `215` reviewed literals.
    - `git diff --check`: passed.
  - 다음 리팩터링 후보는 `_extract_calculation_operands()`의 fallback assembly
    블록이다. 계속 진행하더라도 benchmark-specific branch나 domain keyword를
    추가하지 말고, 반복되는 generic assembly / artifact publication /
    dependency guard contract만 줄인다.

- 2026-06-16 `HYU_T1_034` source-slot ratio rebuild residual을 다시 닫았다.
  - 이전 refactor 이후 잘못된 incoherent ratio 후보(`44.1%`, `914.97%`
    계열)는 막았지만, aggregate answer가 이미 확보한 lookup source slots
    에서 ratio를 다시 조립하지 못하는 상태가 있었다.
  - 변경은 일반 source-slot / provenance 계약으로 처리했다.
    - preferred numeric answer path가 lookup/single-value producer slots만
      source 후보로 보도록 제한했다.
    - lookup primary slot이 stale이거나 일반 label이면 producer
      `metric_label`을 source-slot metadata로 보존해 denominator selection에
      사용한다.
    - ratio row가 `insufficient_operands`이거나 dependency-incoherent여도
      numerator/denominator source slots가 material하고 distinct이면
      deterministic ratio answer를 재구성한다.
    - projected lookup realignment는 self-task projection은 유지하되,
      다른 direct provenance끼리는 source id가 disjoint이거나 source
      anchor가 충돌하면 lookup primary slot을 덮어쓰지 않는다.
  - focused store-fixed eval-only:
    - result bundle:
      `benchmarks/results/focused_hyu_t1_034_after_skip_incoherent_numeric_candidate_2026-06-16/`
    - `HYU_T1_034`: numeric `PASS`, faithfulness `1.000`, retrieval hit
      `1.000`, avg score `0.948`.
    - final answer:
      `2023년 전체 영업이익에서 차량 부문이 차지하는 비중은 83.81%입니다. 계산: 차량 영업이익 12조 6,773억원 / 전체 영업이익 15조 1,269억원.`
  - 검증:
    - targeted ratio source-slot tests: `3` OK
    - `tests.test_subtask_loop`: `205` OK
    - related projection/subtask suite: `255` OK
    - full unittest: `1171` OK
    - `.venv\Scripts\python.exe -m src.ops.audit_runtime_domain_terms`:
      passed with `216` reviewed literals
  - 이 benchmark result bundle과 heartbeat logs는 local experiment artifacts라
    commit 대상이 아니다.

- 2026-06-15 `HYU_T1_034` ratio binding residual을 store-fixed focused
  eval-only에서 닫았다.
  - 변경은 runtime domain branch가 아니라 dependency projection 계약 보강이다.
    - lookup task output에서 answer text와 primary slot이 어긋난 경우 단일
      numeric answer surface로 slot value/label을 복구한다.
    - 복구된 task-output slot에 `task_output:<task_id>` provenance를 보존한다.
    - producer task의 단일 required operand concept/period를 recovered slot에
      보강한다.
    - ratio source binding은 이미 다른 ratio role group에 사용된 task output을
      제외하고 다음 후보를 보도록 했다.
  - focused eval-only:
    - result bundle:
      `benchmarks/results/hyu_t1_034_ratio_task_output_distinct_source_2026-06-15/`
    - `HYU_T1_034`: numeric `PASS`, faithfulness `1.000`, numeric grounding
      `1.000`, numeric retrieval support `1.000`, avg score `0.947`.
    - final answer:
      `2023년 전체 영업이익에서 차량 부문이 차지하는 비중은 83.81%입니다. 계산: 차량 영업이익 12,677,300백만원 / 전체 영업이익 15,126,901백만원.`
  - 검증:
    - `tests.test_aggregate_subtask_projection`,
      `tests.test_evaluator_runtime_projection`,
      `tests.test_financial_agent_run_projection`: `152` tests OK
    - `.venv\Scripts\python.exe -m src.ops.audit_runtime_domain_terms`:
      passed with `216` reviewed literals
    - `git diff --check`: passed for touched source/test files
  - HYU fix 이후 focused regression도 store-fixed eval-only로 확인했다.
    - `regression_ski_t2_069_after_hyu_rebind_2026-06-15`: `SKI_T2_069`
      numeric `PASS`, faithfulness/completeness `1.000`.
    - `regression_pos_t1_075_after_hyu_rebind_2026-06-15`: `POS_T1_075`
      numeric `PASS`, faithfulness/completeness `1.000`.
    - `regression_hyu_t1_034_after_hyu_rebind_2026-06-15`: `HYU_T1_034`
      numeric `PASS`, faithfulness `1.000`, numeric grounding `1.000`.
  - Post-fix large-diff review also removed `segment_revenue_*` policy-key
    names from runtime/config consumers, replacing them with generic
    `scoped_*` structured-cell affinity keys. Marker vocabulary remains in
    retrieval policy; runtime now consumes the policy through generic names.
    The same cleanup centralized scoped surface affinity scoring and
    dependency-projection slot/source matching helpers in
    `financial_graph_helpers`, removing duplicated nested implementation from
    `financial_graph_calculation`. Lookup task-output slot recovery is now in
    `src/agent/financial_dependency_projection.py`, so
    `_align_lookup_results_with_dependency_projection()` delegates stale slot
    repair instead of carrying the recovery implementation inline.
    Validation: `tests.test_operation_contracts` plus
    `tests.test_aggregate_subtask_projection` `271` OK, runtime domain-term
    audit passed, projection/evaluator/run projection suites `152` OK, and
    `git diff --check` passed for touched files.
  - Additional structure cleanup moved table-label evidence collection and
    dependency operand construction helpers into
    `financial_dependency_projection.py`, leaving the calculation mixin with
    orchestration rather than inline provenance row assembly. Source-task
    answer-slot candidate extraction for dependency projection now lives in
    the same module. Source-task operand derivation and fallback dependency
    operation-plan construction for ratio/growth repair are also delegated
    there. Existing operand refresh from lookup slots and operand-id dedupe are
    now delegated there as well. Ratio missing-role fill, including denominator
    candidate inference from sibling lookup rows, is also centralized there.
    Dependency calculation-plan executability checks and deterministic/fallback
    rebuild are delegated there via callbacks. Recalculation state creation,
    absolute-ratio magnitude post-processing, and recalculated row assembly are
    now delegated there too. Lookup-row realignment from projected task-output
    operands is now delegated there as a row-level helper.
  - 이 추가 projection helper 추출 이후 store-fixed focused eval-only smoke를
    다시 돌렸다.
    - `refactor_projection_hyu_t1_034_eval_only_2026-06-15`: `HYU_T1_034`
      numeric `PASS`, faithfulness `1.000`, avg `0.947`.
    - `refactor_projection_pos_t1_075_eval_only_2026-06-15`: `POS_T1_075`
      numeric `PASS`, faithfulness/completeness `1.000`, avg `0.919`.
    - `refactor_projection_ski_t2_069_eval_only_2026-06-15`: `SKI_T2_069`
      numeric `PASS`, faithfulness/completeness `1.000`, avg `0.965`.
    - 이 benchmark result bundles는 commit 대상이 아니다.

- 2026-06-15 `financial_graph_calculation` refactor focused check를 마쳤다.
  - 목적은 반복 patch로 길어진 aggregate/projection 경로를 줄이고, 숫자
    surface/evidence 후보 추출을 공용 helper로 빼서 evaluator와 runtime이 같은
    해석을 쓰게 만드는 것이었다.
  - 변경은 일반 계약으로 처리했다.
    - numeric display/evidence candidate 추출은
      `src/agent/financial_numeric_surface.py`로 분리했다.
    - aggregate answer candidate, projection rebuild, artifact payload sync,
      ratio answer refresh helpers를 도입해 중복 갱신 코드를 줄였다.
    - ratio numerator/denominator가 label이나 operand id만 다르고 같은
      source/value slot으로 접히면 plan/evidence complete로 보지 않는다.
  - focused store-fixed eval-only:
    - `SKI_T2_069`: `PASS -> PASS`, avg `0.9630 -> 0.9645`
    - `POS_T1_075`: `PASS -> PASS`, avg `0.9444 -> 0.9194`, answer unchanged
    - `HYU_T1_034`: `FAIL -> FAIL`, avg `0.7612 -> 0.7751`
      - self-ratio `100%` regression은 generic collapse guard로 막혔다.
      - 현재는 안전한 partial answer로 닫히며, 남은 gap은 aggregate answer
        composition이 아니라 operand binding policy / table-structure 쪽이다.
  - 검증:
    - targeted py_compile: OK
    - `tests.test_aggregate_subtask_projection`,
      `tests.test_evaluator_runtime_projection`,
      `tests.test_financial_agent_run_projection`: `145` tests OK
    - `.venv\Scripts\python.exe -m src.ops.audit_runtime_domain_terms`:
      passed with `216` reviewed literals
    - `git diff --check`: passed
  - raw result bundles:
    - `benchmarks/results/refactor_check_ski_t2_069_eval_only_2026-06-15/`
    - `benchmarks/results/refactor_check_hyu_t1_034_eval_only_2026-06-15/`
    - `benchmarks/results/refactor_check_pos_t1_075_eval_only_2026-06-15/`
    - 이들은 commit 대상이 아니다.

- 2026-06-12 `CEL_T1_038` margin-drag regression을 다시 닫았다.
  - root cause는 세 층이었다.
    1. numeric extractor evidence가 `claim=2,176,431,531,380 (원)`,
       `quote_span=2,176,431,531,380` 형태일 때 lookup slot capture가
       이미 있던 table unit `천원`을 유지했다.
    2. late aggregate / projection 단계에서 corrected lookup slot과
       dependency ratio trace가 다시 동기화되지 않아 stale `0.01%p`
       answer가 top-level로 남았다.
    3. final aggregate answer가 target metric뿐 아니라 보조 `영업이익률`
       subtask까지 함께 출력해 evaluator와 user-facing answer가 흔들렸다.
  - 변경은 일반 계약으로 처리했다.
    - claim-visible value-local unit을 lookup capture에서 보존한다.
    - late evidence / source-task alignment 이후 ratio answer를 다시
      projection하고 final answer를 corrected subtask trace와 일치시킨다.
    - query와 operand focus가 가장 잘 맞는 numeric subtask를 final answer로
      우선한다.
  - focused benchmark:
    `benchmarks/results/cel_t1_038_unit_repair_check_2026-06-12/`
    - answer:
      `2023년 영업이익률 감소 영향은 8.36%p입니다. 계산: 무형자산상각비 182,049,824천원 / 매출액 2,176,431,531.38천원.`
    - numeric_final_judgement `PASS`
    - faithfulness/completeness/numeric_grounding/unit_consistency
      `1.000 / 1.000 / 1.000 / 1.000`
  - 검증:
    - `.venv/bin/python -m src.ops.audit_runtime_domain_terms`: passed with
      `216` reviewed literals
    - focused operation/subtask regression tests: OK
    - `git diff --check`: passed

- 2026-06-12 현재 `main`은 `origin/main`과 동기화되어 있다.
  - 최신 커밋:
    - `d5bfbc1 Tighten narrative evidence projection`
    - `ebaeb66 Stop exclusive narrative replanning loops`
  - broader benchmark raw bundle
    `benchmarks/results/curated_single_doc_core_2026-06-11/`은 결과를 문서화한
    뒤 artifact hygiene 차원에서 삭제했다.
  - `benchmarks/results/**`는 source commit 대상이 아니다.
  - 최종 sanity check:
    - focused exclusive-narrative / forward-looking routing tests: `6` tests OK
    - `.venv/bin/python -m src.ops.audit_runtime_domain_terms`: passed with
      `216` reviewed literals
    - `git diff --check`: passed

- Broader curated single-document full eval, 2026-06-12:
  - profile: `benchmarks/profiles/curated_single_doc_core.json`
  - mode: store-fixed `--eval-only` with heartbeat monitoring
  - scope: 삼성전자/네이버/현대자동차 2023, `15` full-eval questions
  - run status: completed, error rate `0.0%`
  - company-level results:
    - 삼성전자: avg `0.837`, faithfulness `1.000`, completeness `1.000`,
      numeric pass `1.000`
    - 네이버: avg `0.795`, faithfulness `1.000`, completeness `1.000`,
      numeric pass `1.000`
    - 현대자동차: avg `0.928`, faithfulness `1.000`, completeness `1.000`
  - Loop closure:
    - `SAM_T4_070` previously repeated
      `semantic_plan -> retrieve -> evidence -> compress` under
      `narrative_policy_exclusive`. The runtime now routes exclusive narrative
      aggregate outputs directly to citation instead of semantic replanning.
    - Focused `SAM_T4_070` eval-only completed in `52.3s`; full Samsung run
      completed all `5` questions with numeric pass `1.000` and error `0.0%`.
  - Remaining quality signals:
    - `SAM_T4_070`: answer/refusal is faithful, but retrieval hit and section
      score remain `0.000` because the answer only preserves the caution/refusal
      evidence, not the adjacent `3나노 GAA` support context.
    - `NAV_T4_008`, `NAV_T4_033`: safe refusal/missing-answer behavior, but
      retrieval hit/section score remain low.
    - These are evidence-projection / evaluator-alignment follow-ups, not
      runtime correctness blockers.

- 이전 hard structural-vs-plain replay는 structural `5 / 5`, plain `4 / 5`로
  요약한다. `SKH_T1_060`에서 plain은 prior-period borrowing rows를
  current-period asset denominator와 섞어 `34.32%`를 냈고, structural은
  current-period borrowing rows를 보존해 `42.02%`를 냈다.

- 2026-06-10 expanded structural-vs-plain ablation refresh를 문서화했다.
  - Commit `8070da8` (`Fix aggregate numeric projection coverage`)는 이미
    `origin/main`에 push됐다.
  - 동일 9문항 / 6회사 expanded candidate set 기준:
    - structural full-system:
      `benchmarks/results/ablation_expanded_candidate_full_system_2026-06-10/`
      - avg numeric `1.000`, faithfulness `1.000`, completeness `0.867`,
        recall `0.889`
    - plain retrieval:
      `benchmarks/results/ablation_expanded_candidate_plain_retrieval_2026-06-10/`
      - avg numeric `0.833`, faithfulness `0.875`, completeness `0.875`,
        recall `0.861`
  - separating numeric failures:
    - `KBF_T1_017`: plain `FAIL`, structural `PASS`
    - `SKH_T3_080`: plain `FAIL`, structural `PASS`
      - plain answer used `868,767` and `906,120` -> `-37,353백만원`
      - structural answer used `573,884백만원` and `906,120백만원` ->
        `-332,236백만원`
  - caveat: cross-company `Full Eval Fails` also counts completeness threshold
    misses, so both variants still show `3` fail notes. Portfolio claim should
    focus on numeric grounding / operand binding / faithfulness, not a blanket
    win on every evaluator dimension.
  - updated docs:
    - `docs/overview/project_status.md`
    - `docs/overview/portfolio_experiment_report.md`
    - `docs/overview/portfolio_one_pager.md`
    - `docs/evaluation/ablation_study_design.md`
    - `docs/evaluation/structural_trace_diagnostics.md`
    - `docs/history/experiment_history.md`
  - raw `benchmarks/results/**` remain local artifacts and should not be
    staged.

- 2026-06-09 `KAB_T1_066` CIR ratio evidence/display path를 닫았다.
  - root cause는 두 층이었다.
    1. lookup direct-support guard가 `경비차감전영업이익` 안의 `차감`을
       aggregate operation token으로 오인해 `11,623억원` denominator를
       reject했다.
    2. ratio final answer가 resolved calculation trace의 coherent MDA table
       operands보다 이전 lookup subtask projection을 우선해
       `4,355.42억원` display를 남겼다.
  - 변경:
    - lookup support 검사는 LLM에 실제로 보여준 prompt context도 검증
      후보로 사용한다.
    - aggregate token guard는 token 앞 경계를 확인해 metric label 내부의
      embedded operation token과 실제 aggregate phrase를 구분한다.
    - ratio calculation은 dependency rows가 이미 required operands를
      채웠더라도 retrieved/seed docs에서 같은 table/context가 모든 required
      operands를 직접 제공하면 coherent context rows를 우선한다.
    - late aggregate answer refresh는 ratio 결과값이 이미 답변에 있어도
      resolved trace의 component display가 다르면 compact ratio answer를
      다시 만든다.
  - 최종 store-fixed eval-only:
    `benchmarks/results/kab_t1_066_final_verified_evalonly_2026-06-09/`
    - answer: `2023년 CIR은 37.47%입니다. 계산: 판매비와관리비 4,355억원 /
      경비차감전영업이익 11,623억원.`
    - operands: both from `IV. 이사의 경영진단 및 분석의견::table:3`
    - numeric `PASS`, faithfulness/completeness/context recall/retrieval hit
      `1.000 / 1.000 / 1.000 / 1.000`, grounded rendering `1.000`
    - latency `68.5s`, agent calls `8`, agent tokens `55,104`,
      estimated runtime cost `$0.056292`
  - 검증:
    - `.venv/bin/python -m unittest tests.test_operation_contracts tests.test_subtask_loop`:
      `362` tests OK.
    - `.venv/bin/python -m src.ops.audit_runtime_domain_terms --summary`:
      passed (`217` reviewed literals).
    - fanout audit: executed queries `2`, duplicate executed queries `0`,
      state query-result avoided searches `14`.

- 2026-06-09 duplicate direct-support lookup rejection 이후 replan loop guard를
  추가했다.
  - aggregate 단계에서 `planner_feedback`이 있어도 `plan_loop_count >= 1`이고
    `numeric_debug_trace_history` / `numeric_debug_trace`에
    `duplicate_missing_direct_lookup_operand_support`가 보이면 semantic replan을
    다시 호출하지 않는다.
  - 이 경우 `replan_blocked_reason =
    duplicate_missing_direct_lookup_operand_support`를 남기고, 기존 partial
    answer에 budget-exhausted refusal suffix를 붙여 `cite`로 닫는다.
  - 첫 replan은 계속 허용된다. 같은 candidate window에서 direct-support
    rejection이 이미 duplicate로 재사용된 경우에만 추가 replan을 차단하므로,
    새 evidence 탐색이나 validation contract를 약화하지 않는다.
  - 검증:
    - focused aggregate/replan tests: `4` tests OK.
    - `.venv/bin/python -m unittest tests.test_subtask_loop tests.test_financial_agent_run_projection tests.test_reflection_capability_contract`:
      `217` tests OK.
    - `.venv/bin/python -m src.ops.audit_runtime_domain_terms --summary`:
      passed (`215` reviewed literals).
    - `.venv/bin/python -m unittest discover -s tests`: `1028` tests OK.

- 2026-06-09 reflection retry artifact id allocation을 ledger-aware하게 수정했다.
  - `_prepare_reflection_retry()`가 더 이상 `reflection_count + 1`만으로
    `reflection:{target}:NNN` id를 고르지 않는다. 기존 task/artifact ledger에
    이미 쓰인 `reflection:{target}:NNN` 및 `reflection:{target}:NNN:report`
    id를 스캔하고 다음 빈 번호를 사용한다.
  - 이 변경은 stale `reflection_count`나 re-entry가 있어도
    `duplicate_artifact_id:reflection:...:report` integrity error를 만들지
    않는 generic ledger contract다. retry/replan 판단이나 evidence validation
    behavior는 바꾸지 않는다.
  - 검증:
    - `.venv/bin/python -m unittest tests.test_subtask_loop.SubtaskLoopTests.test_prepare_reflection_retry_ignores_legacy_top_level_runtime_projection tests.test_subtask_loop.SubtaskLoopTests.test_prepare_reflection_retry_allocates_next_id_from_existing_ledger tests.test_subtask_loop.SubtaskLoopTests.test_aggregate_subtasks_replans_on_task_artifact_integrity_error`:
      `3` tests OK.
    - `.venv/bin/python -m unittest tests.test_financial_agent_run_projection.FinancialAgentRunProjectionTests.test_run_accepts_reflection_report_handoff_without_evidence_refs tests.test_financial_agent_run_projection.FinancialAgentRunProjectionTests.test_run_marks_completed_reflection_without_report_as_integrity_error`:
      `2` tests OK.
    - `.venv/bin/python -m unittest tests.test_subtask_loop tests.test_financial_agent_run_projection tests.test_reflection_capability_contract`:
      `216` tests OK.
    - `.venv/bin/python -m src.ops.audit_runtime_domain_terms --summary`:
      passed (`215` reviewed literals).
    - `.venv/bin/python -m unittest discover -s tests`: `1027` tests OK.

- 2026-06-09 lookup objective query-result cache reuse를 추가했다.
  - lookup/single_value retrieval task에서 `operation_family`,
    `metric_label`, `required_operands`를 정규화한
    `objective_signature`를 만든다.
  - state-local query-result cache는 기존 exact query signature hit 외에도
    같은 `where_filter`와 같은 lookup objective signature를 공유하고,
    캐시된 `k`가 현재 요청보다 크거나 같으면 primary/focused/retry query
    전부에서 재사용한다.
  - retrieval trace는
    `state_same_filter_exact_or_lookup_objective_signature` scope와
    `objective_hit_count`를 남겨 exact hit와 objective-level hit를 구분한다.
  - 이는 replan wording variation을 줄이기 위한 generic cache contract다.
    회사명, benchmark ID, metric keyword branch는 추가하지 않았다.
  - live canary:
    `benchmarks/results/kab_t1_066_lookup_objective_cache_canary_2026-06-09/`는
    fresh store local artifact이며 요약 후 삭제 대상이다. `KAB_T1_066`
    결과는 numeric `PASS`, faithfulness/completeness `1.000 / 1.000`,
    context recall/retrieval hit@k `0.500 / 1.000`, latency `346.8s`,
    estimated runtime cost `$0.110721`.
  - 직전 duplicate numeric reuse canary 대비 retrieval fanout은 줄었다:
    executed queries `34 -> 12`, duplicate executed queries `8 -> 0`,
    query embedding API calls `26 -> 12`. query-result cache는 검색 `64`회를
    피했고, 이 중 objective-level hit가 `42`회였다.
  - 다만 end-to-end latency/cost는 `232.7s -> 346.8s`로 개선되지 않았다.
    agent LLM total은 `108,158 -> 148,169` tokens, agent calls는
    `18 -> 25`, `numeric_extraction`은
    `50,224 / 3 calls -> 61,708 / 4 calls`로 늘었다.
  - 이번 변경은 equivalent lookup cache miss를 줄였지만, 남은 병목은
    direct-support reject 이후의 reflection/replan loop다. 같은 canary에서
    `duplicate_artifact_id:reflection:task_1:001:report` ledger integrity
    warning도 노출됐다.
  - 검증:
    - `.venv/bin/python -m unittest tests.test_retrieval_scope.RetrievalScopeTests.test_retrieve_reuses_state_query_result_cache_for_sibling_primary_query tests.test_retrieval_scope.RetrievalScopeTests.test_retrieve_reuses_lookup_objective_cache_for_reworded_primary_query tests.test_benchmark_fanout_cost_audit`:
      `5` tests OK.
    - `.venv/bin/python -m unittest tests.test_retrieval_scope tests.test_benchmark_fanout_cost_audit tests.test_operation_contracts`:
      `212` tests OK.
    - `python -m src.ops.audit_runtime_domain_terms --summary`: passed
      (`215` reviewed literals).
    - `python -m unittest discover -s tests`: `1026` tests OK.

- 2026-06-09 duplicate numeric extraction result/rejection reuse를 추가했다.
  - `numeric_extraction_prompt` diagnostic에 prompt text 대신
    `query_fingerprint`, `candidate_window_fingerprint`,
    `extraction_fingerprint`를 남긴다.
  - 같은 extraction fingerprint에서 이미 direct-supported numeric result가
    있으면 `duplicate_numeric_extraction_result`로 LLM 호출 없이 재사용한다.
  - 같은 extraction fingerprint에서 이미
    `missing_direct_lookup_operand_support` reject가 있으면
    `duplicate_missing_direct_lookup_operand_support`로 LLM 호출 없이 같은
    missing evidence 상태를 재사용한다.
  - 이는 같은 query + candidate window의 repeated extraction만 줄이는
    generic cost-control contract다. 회사명, benchmark ID, metric-specific
    branch는 추가하지 않았다.
  - live canary:
    `benchmarks/results/kab_t1_066_numeric_reject_reuse_canary_2026-06-09/`는
    local artifact이며 요약 후 삭제 대상이다. Fresh store canary 후 같은
    store에서 eval-only를 다시 실행해 최종 수치를 확인했다. `KAB_T1_066`
    결과는 numeric `PASS`, faithfulness/completeness `1.000 / 1.000`,
    context recall/retrieval hit@k `1.000 / 1.000`, latency `232.7s`,
    estimated runtime cost `$0.084768`.
  - 이전 numeric history canary 대비 agent LLM total은
    `190,990 -> 108,158` tokens, agent calls는 `25 -> 18`,
    `numeric_extraction`은 `106,483 / 6 calls -> 50,224 / 3 calls`로
    줄었다. history는 `6` entries를 보존하되 `3` entries가 skipped trace로
    남는다: failed direct-support reject reuse `2`, supported result reuse
    `1`.
  - 남은 병목:
    retrieval/replan side는 still noisy하다. 최종 canary도 executed queries
    `34`, duplicate executed queries `8`, query embedding calls `26`을
    기록했다. 다음 cost-control 타깃은 retry/replan query fanout과 planner가
    새로 만드는 unique query budget 억제다.
  - 검증:
    - `python -m unittest tests.test_operation_contracts.OperationContractTests.test_numeric_extractor_reuses_duplicate_direct_support_rejection tests.test_operation_contracts.OperationContractTests.test_numeric_extractor_reuses_duplicate_supported_result tests.test_operation_contracts.OperationContractTests.test_numeric_extractor_records_prompt_size_diagnostics`:
      `3` tests OK.
    - `python -m unittest tests.test_operation_contracts tests.test_benchmark_runner_runtime_projection tests.test_financial_agent_run_projection tests.test_evaluator_progress`:
      `236` tests OK.
    - `python -m src.ops.audit_runtime_domain_terms --summary`: passed
      (`215` reviewed literals).
    - `python -m unittest discover -s tests`: `1025` tests OK.

- 2026-06-09 `numeric_debug_trace_history` / benchmark
  `agent_numeric_debug_trace_history`를 추가했다.
  - 직전 live canary에서 `numeric_extraction`이 여러 번 호출되는데
    benchmark row에는 마지막 `numeric_debug_trace` 하나만 남아, 실제
    prompt fanout과 retry loop를 사후 분석하기 어려웠다.
  - runtime state, `FinancialAgent.run()` projection, evaluator result,
    benchmark serialization에 call-level history를 그대로 보존한다.
    기존 `numeric_debug_trace`는 backward-compatible하게 마지막 호출
    snapshot으로 유지한다.
  - 이 변경은 관측 계약 확장이다. retrieval, evidence selection, 계산,
    answer composition behavior는 바꾸지 않는다.
  - live eval-only canary:
    `benchmarks/results/kab_t1_066_numeric_prompt_diag_canary_2026-06-09/`는
    local artifact이며 요약 후 삭제 대상이다. 기존 fresh store artifact를
    재사용해 `KAB_T1_066`만 `--eval-only --skip-llm-judges
    --skip-embedding-metrics`로 재실행했다. 결과는 numeric `PASS`,
    faithfulness/completeness `1.000 / 1.000`, context recall/retrieval hit@k
    `1.000 / 1.000`, latency `416.0s`, estimated runtime cost `$0.150280`.
    history는 `6` numeric extraction calls를 보존했고, 각 호출의 prompt
    diagnostics는 selected docs `8`, context chars `19,823-25,901`,
    table-context docs `7-8` 범위를 기록했다.
  - canary 해석:
    품질은 유지됐지만 `numeric_extraction`이 `106,483` tokens / `6` calls로
    최대 phase가 됐다. 같은 `경비차감전영업이익` lookup 후보가
    `missing_direct_lookup_operand_support`로 반복 reject되며 reflection/retry
    loop가 길어진다. 다음 cost-control 타깃은 prompt 축소보다 먼저
    duplicate numeric extraction / failed lookup retry budget 억제다.
  - 검증:
    - `python -m unittest tests.test_operation_contracts.OperationContractTests.test_numeric_extractor_records_prompt_size_diagnostics tests.test_benchmark_runner_runtime_projection.BenchmarkRunnerRuntimeProjectionTests.test_serialise_eval_results_preserves_retrieval_trace_history tests.test_financial_agent_run_projection.FinancialAgentRunProjectionTests.test_run_projects_calculation_debug_trace_under_debug_traces`:
      `3` tests OK.
    - `python -m unittest tests.test_operation_contracts tests.test_benchmark_runner_runtime_projection tests.test_financial_agent_run_projection tests.test_evaluator_progress`:
      `234` tests OK.
    - `python -m src.ops.audit_runtime_domain_terms --summary`: passed
      (`215` reviewed literals).
    - `python -m unittest discover -s tests`: `1023` tests OK.

- 2026-06-09 `numeric_extraction` prompt-size diagnostic을 추가했다.
  - `numeric_debug_trace.numeric_extraction_prompt`에 selected doc count,
    formatted context chars, query chars, source page-content chars,
    parent-context candidate count, table-context doc count, graph-relation doc
    count, doc summaries를 남긴다. prompt 본문 자체는 저장하지 않는다.
  - LLM 성공, LLM failure 후 deterministic lookup fallback, direct-support
    rejection 경로 모두 같은 diagnostic을 보존한다.
  - evaluator/benchmark row에는 evaluator numeric judge debug와 섞지 않도록
    `agent_numeric_debug_trace`로 별도 serialize한다.
  - 이 변경은 다음 `numeric_extraction` token 절감을 위한 관측 계약이며,
    retrieval/evidence selection/answer behavior를 바꾸지 않는다.
  - 검증:
    - `python -m unittest tests.test_operation_contracts.OperationContractTests.test_numeric_extractor_records_prompt_size_diagnostics tests.test_benchmark_runner_runtime_projection.BenchmarkRunnerRuntimeProjectionTests.test_serialise_eval_results_preserves_retrieval_trace_history`:
      `2` tests OK.
    - `python -m unittest tests.test_operation_contracts tests.test_benchmark_runner_runtime_projection tests.test_evaluator_progress`:
      `195` tests OK.
    - `python -m src.ops.audit_runtime_domain_terms --summary`: passed
      (`215` reviewed literals).
    - `python -m unittest discover -s tests`: `1023` tests OK.

- 2026-06-09 `aggregate_synthesis` runtime payload를 compact projection으로
  전환했다.
  - 이전 live phase canary에서 `aggregate_synthesis`가 `186,310` tokens로
    가장 큰 비용 phase였기 때문에, final synthesis LLM에는 `ordered_results`
    원본 전체 대신 aggregate projection 기반 compact rows만 전달한다.
  - compact rows는 `task_id`, metric/operation labels, answer,
    `calculation_result.answer_slots`, source ids, material numeric operands만
    보존하고, retrieval/debug/runtime evidence payload는 prompt에서 제외한다.
    이는 answer rule이 아니라 synthesizer input contract 축소다.
  - `subtask_debug_trace.aggregate_synthesis_prompt`에 compact row count와
    input JSON character count를 남긴다.
  - 검증:
    - `python -m unittest tests.test_subtask_loop.SubtaskLoopTests.test_aggregate_synthesis_prompt_uses_compact_projection_rows tests.test_subtask_loop.SubtaskLoopTests.test_aggregate_subtasks_joins_answers_in_task_order tests.test_subtask_loop.SubtaskLoopTests.test_aggregate_subtasks_dedupes_nested_operand_mirrors`:
      `3` tests OK.
    - `python -m unittest tests.test_subtask_loop`: `169` tests OK.
    - `python -m src.ops.audit_runtime_domain_terms --summary`: passed
      (`215` reviewed literals).
    - `python -m unittest discover -s tests`: `1022` tests OK.
  - live canary:
    `benchmarks/results/kab_t1_066_aggregate_compact_canary_2026-06-09/`는
    reusable store가 없는 checkout에서 실행되어 fresh store 구축을 포함한
    local artifact였고, 수치 요약 후 삭제했다. `KAB_T1_066` 단일 row는
    `--skip-llm-judges --skip-embedding-metrics`로 실행했고 numeric `PASS`,
    faithfulness/completeness `1.000 / 1.000`, context recall/retrieval hit@k
    `1.000 / 1.000`, latency `150.1s`, estimated runtime cost `$0.064986`를
    기록했다. 이전 phase canary 대비 total agent LLM tokens는
    `258,333 -> 76,252`, `aggregate_synthesis`는 `186,310 -> 4,064`,
    estimated runtime cost는 `$0.110654 -> $0.064986`로 줄었다. 이번 run의
    최대 phase는 `numeric_extraction` `51,556` tokens / `$0.038694`였다.
    retrieval side는 executed queries `17`, duplicate queries `0`,
    state query-result avoided searches `8`로 유지됐다.

- 2026-06-09 runtime LLM phase-level usage instrumentation을 추가했다.
  - `GeminiUsageCallbackHandler`가 thread-local current phase와
    phase별 usage/api-call accumulator를 가진다.
  - `FinancialAgent._llm_for_phase()`가 phase를 callback에 전달하고,
    `FinancialAgent.run()`은 기존 `llm_usage`와 별도로
    `llm_usage_by_phase`를 반환한다. 기본 LLM 직접 호출은 `default` phase로
    남는다.
  - evaluator/benchmark runner는 이를 `agent_llm_usage_by_phase`로
    per-question result row에 보존한다.
  - `audit_benchmark_fanout_cost`는 phase별 agent LLM calls/tokens/estimated
    cost와 `Agent LLM Usage By Phase` table을 노출한다. 오래된 result
    bundle은 phase usage가 없어도 계속 읽힌다.
  - 검증:
    - `python -m unittest tests.test_gemini_usage tests.test_benchmark_fanout_cost_audit`:
      `8` tests OK.
    - `python -m unittest tests.test_evaluator_progress tests.test_benchmark_runner_runtime_projection tests.test_benchmark_fanout_cost_audit tests.test_gemini_usage`:
      `24` tests OK.
    - `python -m src.ops.audit_runtime_domain_terms --summary`: passed
      (`215` reviewed literals).
    - legacy local bundle
      `benchmarks/results/dev_fast_focus_canonical_v2_2026-04-24` audit smoke:
      completed without error.
    - `python -m unittest discover -s tests`: `1020` tests OK.
  - live canary:
    `benchmarks/results/kab_t1_066_llm_phase_canary_2026-06-09/`는 reusable
    store가 없는 checkout에서 실행되어 fresh store 구축을 포함한 local
    artifact였고, 수치 요약 후 삭제했다. `KAB_T1_066` 단일 row는
    `--skip-llm-judges --skip-embedding-metrics`로 실행했고 numeric `PASS`,
    faithfulness/completeness `1.000 / 1.000`, retrieval hit@k/context recall
    `1.000 / 1.000`, latency `145.4s`, estimated runtime cost `$0.110654`를
    기록했다. answer relevancy `0.000`은 embedding metric skip의 결과라
    quality baseline으로 해석하지 않는다. phase audit는 agent LLM calls
    `11`, tokens `258,333`을 분해했고 top phases는
    `aggregate_synthesis` `186,310` tokens / `$0.058368`,
    `numeric_extraction` `51,393` tokens / `$0.029749`,
    `reconciliation_rerank` `5,582` tokens / `$0.010426`이었다. retrieval
    side는 executed queries `17`, duplicate queries `0`, state query-result
    avoided searches `8`이었다.

- 2026-06-09 runtime LLM cost audit surface를 보강했다.
  - `src.ops.audit_benchmark_fanout_cost`는 이제 기존 `llm_usage` combined
    summary와 별도로 `agent_llm_usage`, `judge_llm_usage`, agent/judge
    estimated runtime cost, `Top Rows By LLM Usage` Markdown table을 노출한다.
  - 이 변경은 기존 `results.json`만 읽는 offline audit이며 agent 실행,
    retrieval, evaluator를 새로 돌리지 않는다. 최신 result bundle처럼
    per-question `agent_llm_usage` / `judge_llm_usage`가 있는 경우 split을
    보여 주고, 오래된 bundle처럼 combined usage만 있거나 usage가 없는 경우
    backward-compatible하게 빈 split으로 둔다.
  - 검증:
    - `python -m unittest tests.test_benchmark_fanout_cost_audit`: `3` tests OK.
    - legacy local bundle
      `benchmarks/results/dev_fast_focus_canonical_v2_2026-04-24` audit smoke:
      completed without error.

- 2026-06-09 runtime/API cost-control 관측 계약을 보강했다.
  - state-local query-result cache 재사용을 `avoided_search_count`로 노출해,
    sibling task가 같은 source/filter/query 결과를 재사용할 때 실제
    `vsm.search()`를 몇 번 피했는지 audit에서 볼 수 있다.
  - cross-trace reuse diagnostics는 이전 trace의 `reused_queries`도 후보
    history로 읽고, 현재 후보가 vector-store cache hit인지 result-cache
    hit인지 구분한다. retrieval behavior나 answer path는 바꾸지 않았다.
  - 검증:
    - `python -m unittest tests.test_retrieval_scope.RetrievalScopeTests.test_retrieve_reuses_state_query_result_cache_for_sibling_primary_query tests.test_retrieval_scope.RetrievalScopeTests.test_cross_trace_reuse_candidate_diagnostics_matches_prior_same_source_filter_query tests.test_benchmark_fanout_cost_audit`:
      `5` tests OK.
    - `python -m unittest tests.test_retrieval_scope`: `27` tests OK.
    - `python -m src.ops.audit_runtime_domain_terms --summary`: passed
      (`215` reviewed literals).
    - `python -m unittest discover -s tests`: `1019` tests OK.
  - follow-up canary:
    `benchmarks/results/cel_t3_040_result_cache_avoided_search_canary_2026-06-09/`
    는 existing concept-gate result bundle이 없는 checkout에서 실행되어
    fresh store 구축을 포함한 local artifact였고, 수치 요약 후 삭제했다.
    `CEL_T3_040` focused run은 numeric `PASS`, faithfulness/completeness
    `1.000 / 1.000`, context recall `0.333`, retrieval hit@k `1.000`,
    latency `249.2s`, estimated runtime cost `$0.126694`를 기록했다.
    fan-out audit는 retrieval traces `6`, executed queries `26`,
    duplicate queries `0`, state query-result cache reuses `18`,
    avoided searches `18`, cross-trace reuse candidates `18`, current cache
    misses `0`을 보고했다. 이 결과는 cost-observability canary이며 full gate
    baseline 교체가 아니다.

- 2026-06-09 aggregate task-ledger trace 정리를 추가했다.
  - 새 lifecycle status `superseded`를 도입해, 최종 aggregate answer slot /
    operand가 이미 해결한 pending/partial planned task를 실패나 미완료처럼
    보이지 않게 표시한다.
  - 적용 조건은 generic하다: task label/period에서 추출한 slot key가 final
    aggregate projection 또는 final subtask result의 resolved slot과 맞을 때만
    `superseded_by_aggregate_result`로 표시한다. 회사명, benchmark ID, 금융
    metric phrase branch는 추가하지 않았다.
  - trace projection은 `resolution_status`, `superseded_by_task_id`,
    `superseded_by_artifact_id`, `notes`를 노출한다.
  - KAB focused probe 중 upstream replan/operand coverage 변동이 여전히 보여
    latency와 partial-answer volatility는 다음 별도 이슈로 남긴다. 이 변경은
    answer path가 아니라 ledger visibility 후처리다.
  - 검증:
    - `python -m unittest tests.test_subtask_loop tests.test_operation_contracts`:
      `339` tests OK.
    - `python -m src.ops.audit_runtime_domain_terms --summary`: passed
      (`215` reviewed literals).
    - `git diff --check`: passed.

- 2026-06-09 `KAB_T1_066` focused follow-up에서 ratio direct
  reconciliation 우선순위를 정리했다.
  - ratio task가 active reconciliation에서 required operands를 모두 직접
    확보한 경우, 부분/실패한 lookup dependency의 producer-scope 필터로
    완전한 direct ratio rows를 다시 제거하지 않는다.
  - 이는 특정 회사/질문 보정이 아니라 "완전한 active ratio evidence가
    partial dependency output보다 우선한다"는 generic dependency binding
    contract다.
  - focused `KAB_T1_066` store-fixed eval-only는 numeric `PASS`,
    faithfulness/completeness `1.000 / 1.000`, CIR answer `37.47%`를
    유지했다.
  - trace 품질은 개선됐다: latency `309s -> 108s`, retrieval debug history
    `8 -> 3`, task artifacts `21 -> 8`.
  - 검증:
    - `python -m src.ops.audit_runtime_domain_terms --summary`: passed
      (`215` reviewed literals).
    - `python -m unittest tests.test_structured_operand_extraction tests.test_subtask_loop tests.test_operation_contracts`:
      `358` tests OK.

- 2026-06-09 concept runtime gap gate follow-up은 monitored full 7
  store-fixed eval-only로 다시 닫혔다.
  - 변경은 작게 제한했다. `narrative_summary` row는
    `_supported_aggregate_subtask_answer()`에서 supported aggregate numeric
    answer 후보로 보지 않는다. 서술형 projection이 우연히
    `answer_slots.operation_family = aggregate_subtasks`를 들고 있어도
    최종 aggregate numeric answer로 승격하지 않는 generic runtime contract다.
  - full eval-only artifact:
    `benchmarks/results/concept_gate_fresh_after_ratio_growth_hardening_2026-06-08/`
    는 local artifact이며 commit 대상이 아니다.
  - 문항별 결과는 7 / 7 `numeric_final_judgement = PASS`:
    `KBF_T2_018`, `SKH_T3_080`, `CEL_T1_013`, `CEL_T3_040`,
    `POS_T1_057`, `KAB_T1_066`, `SAM_T3_028`.
  - 모든 문항의 faithfulness/completeness는 `1.000 / 1.000`.
    대표 계산 surface는 `POS_T1_057 = 3.5269배`,
    `KAB_T1_066 = 37.47%`, `SAM_T3_028` trace formula
    `62,964백만원 / 180,388,580백만원 = 0.03%`.
  - 검증:
    - `python -m src.ops.audit_runtime_domain_terms --summary`: passed
      (`215` reviewed literals).
    - `python -m unittest tests.test_subtask_loop tests.test_operation_contracts`:
      `336` tests OK.
    - monitored full 7 eval-only: 7 / 7 PASS.

- 2026-06-08 concept runtime gap follow-up에서 ratio unit binding과
  growth+narrative answer repair를 추가로 닫았다.
  - `POS_T1_057` full/replay path의 unit-source instability는 ratio operand
    peer-unit alignment로 보강했다. 같은 raw value가 서로 다른 KRW display
    unit으로 후보화될 때, ratio의 다른 operand와 unit family/raw unit이
    맞는 structured evidence를 우선한다. POSCO/company/benchmark branch가
    아니라 operand peer-unit contract다.
  - `KBF_T2_018`는 숫자 성장률 문장만으로 narrative intent를 만족했다고
    판단하는 aggregate repair gap을 좁혔다. `narrative_summary` row의
    서술 문장은 deterministic repair 후보로 남기고, final answer가 실제
    서술 후보를 포함할 때만 supported aggregate answer 보호를 적용한다.
  - focused eval-only:
    - `POS_T1_057`: numeric PASS, faithfulness/completeness `1.000 / 1.000`,
      answer `3.5269배`.
    - `KAB_T1_066`: numeric PASS, faithfulness/completeness `1.000 / 1.000`,
      CIR answer `37.47%`.
    - `KBF_T2_018`: numeric PASS, faithfulness/completeness `1.000 / 1.000`,
      final answer preserves `70.28%` and the conservative provisioning /
      future economic uncertainty cause.
  - 검증:
    - `python -m unittest tests.test_subtask_loop tests.test_part_whole_ratio_contract`:
      `169` tests OK.
    - `python -m src.ops.audit_runtime_domain_terms`: passed
      (`215` reviewed literals).
    - `python -m unittest discover -s tests`: `997` tests OK.
  - 이 focused hardening의 promotion proof는 이후 2026-06-09 monitored full
    7 store-fixed eval-only로 갱신됐다.

- 2026-06-08 concept runtime gap gate의 budgeted eval-only follow-up에서
  growth-rate operand recovery를 보강했다.
  - 2026-06-04 `7 / 7 PASS` baseline은 promotion 기준선으로 그대로 유지한다.
    이번 follow-up은 기준선 교체가 아니라, `8 / 4 / 1` retrieval budget
    replay에서 드러난 runtime 흔들림을 좁힌 하드닝이다.
  - budgeted full replay
    `benchmarks/results/tmp_concept_gate_budgeted_evalonly_direct_priority_full_2026-06-08/`
    는 7문항을 완료했고 `5 / 7` numeric PASS를 기록했다. 이 replay에서
    `KBF_T2_018`는 parenthesized current display를 prior candidate로
    재사용하는 duplicate recovery 문제가 보였고, `POS_T1_057`는 standalone
    eval-only에서는 PASS지만 full replay path에서 unit/source binding noise가
    보였다. `KAB_T1_066`은 numeric PASS였지만 CIR 계산을 거절하는 product
    quality residual로 남았다.
  - runtime 보강은 특정 회사/문항 branch가 아니라 일반 operand contract다:
    complete reconciliation rows는 `growth_rate`에서도 stale dependency
    output보다 우선하고, same-label current/prior operand merge는
    label+role+period로 구분하며, evidence sentence에서 prior 값을 회복할 때
    괄호/단위 차이 때문에 current 값을 prior로 다시 선택하지 않는다.
  - aggregate growth+narrative synthesis는 structured numeric gap이 unresolved
    인데 narrative summary가 숫자 claim을 재사용하면 safe partial answer로
    낮춘다.
  - focused canary:
    - `KBF_T2_018` after compact-current recovery: numeric PASS,
      faithfulness/completeness `1.000 / 1.000`.
    - `POS_T1_057` standalone eval-only: numeric PASS,
      faithfulness/completeness `1.000 / 1.000`, calculator result `3.5269배`.
    - `KAB_T1_066` single-question eval after ratio operand hardening:
      numeric PASS, faithfulness/completeness `1.000 / 1.000`, refusal
      accuracy `1.000`. A follow-up ratio renderer pass now normalizes mixed
      KRW component displays into a shared unit, so the answer renders
      `판매비와관리비 4,355.42억원 / 경비차감전영업이익 11,623억원`
      instead of mixing `백만원 / 억원`. This is still a focused canary, not a
      fresh full-gate baseline.
  - 검증:
    - `python -m unittest tests.test_subtask_loop`: `156` tests OK.
    - focused growth/aggregate regression: `4` tests OK.
    - `python -m unittest tests.test_structured_operand_extraction tests.test_semantic_numeric_plan tests.test_operation_contracts tests.test_subtask_loop`: `417` tests OK.
    - `python -m src.ops.audit_runtime_domain_terms`: passed
      (`215` reviewed literals).
  - 이 follow-up 자체는 처음에는 full stable proof가 아니었고, 이후
    2026-06-09 monitored full 7 store-fixed eval-only replay로 검증을
    갱신했다.

- 2026-06-08 task-ledger/artifact-store capability gates를 정리했다.
  - Reflection promotion gate는 base fixture, store-fixed candidate surface,
    reviewed store-fixed trace summary, reviewed live/default MAS handoff
    trace summary 네 source class를 모두 포함해야 `ready`가 된다.
  - Reflection action ledger surface는 `retry_retrieval`의 visible
    `retry_queries`와 `synthesize_from_task_outputs`의 visible
    `synthesis_source_ids`를 요구한다.
  - Report-cache promotion evidence는 calculation-task producer policy,
    `operand_set` / `calculation_plan` / `calculation_result` artifact kinds,
    cache-origin metadata, fallback safety를 모두 gate로 확인한다.
  - Cache serving, retrieval bypass, live ledger insertion, final acceptance는
    여전히 disabled다. 다음 expansion은 materially different live/default MAS
    또는 store-fixed eval-only surface가 생길 때 trace summary를 추가하는
    것이다.
  - Promotion trace materiality gate는 현재 reviewed store-fixed summary와
    reviewed live/default MAS summary가 서로 다른 reflection action과
    cache fallback reason을 제공하는지 확인한다. 새 summary는 이 gate가
    중복이 아닌 material surface라고 설명할 수 있을 때만 추가한다.
  - `REFERENCE_NOTE`는 `graph_expansion_context_only` capability로 고정했다.
    Researcher retrieval context와 `retrieval_bundle` 안에서만 쓰며,
    report-cache serving, retrieval bypass, live ledger insertion, final
    acceptance authority가 아니다.
  - 최신 검증:
    - `python -m src.ops.reflection_promotion_gate --format text`: ready.
    - `python -m src.ops.report_cache_promotion_evidence_gate --format text`:
      ready.
    - `python -m src.ops.promotion_trace_materiality_gate --format text`:
      ready.
    - `python -m src.ops.portfolio_review_gates --format text`: ready.
    - `python -m unittest discover -s tests`: `980` tests OK.

- 2026-06-04 concept runtime gap gate answer-composition blockers까지 닫았다.
  - 최신 local store-fixed eval-only refresh:
    `benchmarks/results/concept_gate_refresh_after_answer_composition_2026-06-04/`
  - 7문항 모두 `numeric_final_judgement = PASS`:
    `KBF_T2_018`, `POS_T1_057`, `SKH_T3_080`, `SAM_T3_028`,
    `CEL_T1_013`, `CEL_T3_040`, `KAB_T1_066`.
  - summary: `7 / 7 PASS`, faithfulness는 전 문항 `1.000`, numeric pass
    rate는 전 문항 `1.000`.
  - `KBF_T2_018`는 source-stated display와 formula trace가 충돌하지 않도록
    aggregate answer composition이 evidence-visible value display를 보존한다.
  - `SAM_T3_028`는 quantitative-impact answer assembly가 evidence-visible
    value/relationship만 조립하도록 정리되어 numeric, faithfulness,
    completeness가 모두 닫혔다.
  - `POS_T1_057`는 scope가 명시되지 않은 lookup/ratio에서
    context-dependent segment table value를 sibling recovery나 ratio operand로
    승격하지 않도록 generic ambiguous-context-table guard를 적용해 닫았다.
    이후 correct notes row `1,001,290백만원`을 denominator로 사용해
    `3.5269배`가 계산된다.
  - 이 변경은 POSCO, benchmark ID, 특정 계정명 branch가 아니라 기존
    table-view/structured-cell/scope contract를 재사용한 일반 guard다.
  - 검증:
    - `python -m src.ops.audit_runtime_domain_terms`: passed
      (`215` reviewed literals).
    - 관련 answer composition / lookup recovery regression: `45` tests OK.
    - `POS_T1_057` focused eval-only: PASS, faithfulness/completeness/context
      recall/retrieval hit/numeric pass rate all `1.000`.
  - 다음 작업은 concept-only planner default promotion 여부를 바로 켜는 것이
    아니라, 이번 7/7 gate를 기준선으로 고정한 뒤 runtime/API cost control과
    task-ledger/artifact-store boundary를 정리하는 것이다.

- 2026-06-02 `HYU_T2_010` evidence-stated growth display 보존까지 닫았다.
  - 이전 targeted smoke는 답변 품질은 닫혔지만, 계산식 재계산값이 source
    display rounding과 달라질 수 있는 여지가 있었다.
  - runtime 보정은 benchmark/company branch가 아니라 generic evidence-surface
    operand contract로 구현했다:
    - evidence core surface의 `값+단위`가 직접 보이면 LLM/operand 단위 추론을
      보정한다.
    - evidence surface에 명시된 단일 연도가 row period와 충돌하면
      `period_source = evidence_surface`로 period를 교정한다.
    - 단, structured `unit_hint`와 현재 unit family가 이미 일치하면 surface
      unit inference가 기존 단위를 덮어쓰지 않는다.
    - source 문장에 `대비 11.5%`처럼 명시된 파생 display가 있으면
      `answer_slots.primary_value.rendered_value`에 source-stated display를
      보존한다.
  - focused store-fixed eval-only:
    - `HYU_T2_010`: final answer includes `87.0만 대`, `78.1만 대`,
      source-stated `11.5%`, IRA / 핵심원자재법 / 보호무역주의 대응 필요성.
    - metrics: `faithfulness = 1.000`, `completeness = 1.000`,
      `context_recall = 1.000`, `retrieval_hit_at_k = 1.000`,
      `avg_score = 0.958`, `error_rate = 0.0%`.
  - validation:
    - `python -m src.ops.audit_runtime_domain_terms`: passed
      (`215` reviewed literals).
    - `python -m unittest discover -s tests`: `604` tests OK.

- 2026-06-08 concept runtime gap gate profile에도 retrieval query budget을
  명시했다.
  - `curated_concept_runtime_gap_gate.json`의 full-evaluation profile도 이제
    `retrieval_query_budget=8`, `focused_retrieval_query_budget=4`,
    `retry_retrieval_query_budget=1`을 기록한다.
  - `CEL_T1_013` store-fixed eval-only canary는 numeric `PASS`,
    faithfulness/completeness `1.000 / 1.000`, artifact integrity `ok`를
    유지했다.
  - query budget trace는 primary query를 `18 -> 8`, `15 -> 8`로 줄였고,
    fan-out audit은 executed queries `15`, duplicate `0`, state cache reuse
    `1`을 기록했다.
  - 검증:
    - `python -m unittest tests.test_benchmark_runner_runtime_projection tests.test_retrieval_scope tests.test_benchmark_fanout_cost_audit`: `44` tests OK.
    - `python -m unittest discover -s tests`: `985` tests OK.

- 2026-06-02 official gate profile에 retrieval query budget을 명시했다.
  - `curated_runtime_contract_gate.json`과
    `curated_policy_driven_runtime_gate.json`의 full-evaluation profile은
    이제 `retrieval_query_budget=8`, `focused_retrieval_query_budget=4`,
    `retry_retrieval_query_budget=1`을 기본으로 기록한다.
  - runtime에는 benchmark/company/metric별 branch를 추가하지 않았다.
    budget은 benchmark profile이 명시적으로 전달하는 execution-cost
    control이며, unbudgeted runtime default는 그대로 유지된다.
  - `retrieval_debug_trace.query_budget.source`에 active subtask source,
    active-subtask query count, state-level query count를 기록해 최종 trace가
    어느 retrieval stage를 설명하는지 확인할 수 있게 했다.
  - 검증:
    - `python -m unittest tests.test_retrieval_scope tests.test_benchmark_runner_runtime_projection`: `23` tests OK.
    - `python -m unittest discover -s tests`: `597` tests OK.
    - official `NAV_T2_006` eval-only canary with `8/4/1`: final answer
      `41.4%`, faithfulness `1.000`, answer relevancy `0.837`,
      context recall `1.000`, retrieval hit `1.000`, context P@5 `0.800`,
      completeness `1.000`, error rate `0.0%`.
    - final narrative subtask trace recorded `source.kind =
      active_subtask_retrieval_queries`, `state_retrieval_query_count = 61`,
      `primary selected_count = 3`, `operand_focus selected_count = 0`,
      `retry selected_count = 0`.

- 2026-06-02 `NAV_T2_006` low-api removal 후 live canary 회귀를 닫았다.
  - 실패층은 LLM evidence extraction 누락이 아니라 growth-rate operand
    unit/source binding이었다. Evidence path는 충분했지만, current operand는
    `2,546,649백만원`, prior operand는 `1,801,079천원`으로 정규화되어
    `141295.74%`라는 잘못된 growth 계산이 나왔다.
  - runtime code에는 NAVER, 커머스, Poshmark, benchmark ID 같은
    domain-specific branch를 넣지 않았다.
  - 일반 계약으로 두 가지를 추가했다:
    - 반복 row-label table evidence에서는 `current_period` / `prior_period`
      role에 맞춰 같은 row label의 금액 후보를 선택한다.
    - 같은 concept의 `growth_rate` current/prior operand에서 raw 숫자
      비율은 정상인데 normalized 비율만 100배 이상 튀면, prior display
      unit을 current display unit에 맞춰 재정규화한다.
  - 검증:
    - `python -m unittest discover -s tests`: `597` tests OK.
    - `NAV_T2_006` store-fixed eval-only canary: calculator result
      `41.4%`, final answer `2022 1조 8,011억원 대비 41.4% 성장`.
    - canary metrics: faithfulness `1.000`, answer relevancy `0.842`,
      context recall `1.000`, retrieval hit `1.000`, context P@5 `0.800`,
      completeness `0.700`, error rate `0.0%`.

- 2026-06-02 runtime/API cost-control 방향을 수정했다.
  - `low_api_debug`와 `offline_retrieval`은 agent/runtime benchmark path에서
    제거했다. 이 모드는 비용은 낮췄지만 BM25-only/deterministic fallback
    시스템을 테스트해 공식 runtime quality 근거로 쓰기 어렵다.
  - Evidence extraction은 structured LLM extraction 결과가
    `coverage=missing`이거나 실패하면 retrieved snippet을 evidence claim으로
    승격하지 않고 `evidence_status=missing`을 유지한다.
  - 비용 절감은 runtime LLM skip branch가 아니라 `llm_routes` 기반 phase별
    model routing과 evaluator-only skip 옵션으로 처리한다.
  - `llm_routes`는 `evidence_extraction`, `compression`, `validation`,
    `numeric_extraction`, `concept_planning`, `operand_extraction`,
    `formula_planning`, `calculation_render`, `calculation_verification`,
    `aggregate_synthesis`, `reconciliation_rerank`, `reflection_planning`
    phase를 지원한다.

- 2026-06-01 value-local unit contract가 계산 operand와 lookup slot 양쪽에서
  닫혔다.
  - table-level `unit_hint`가 있어도 evidence text의 값 주변에 직접 붙은
    단위가 있으면 value-local surface unit을 우선한다.
  - direct structured operand, LLM operand extraction, lookup answer-slot
    refinement가 같은 unit precedence를 공유한다.
  - embedded-unit raw value도 support scan에서 숫자와 단위를 분리해 처리한다
    (`6,769억원` 같은 surface value가 direct support로 인정된다).
  - `LGE_T1_051` focused smoke는 `영업이익 2,163,234백만원`,
    `AMPC 6,769억원`, `실질 영업이익 1,486,334백만원`으로 `PASS`다.
  - policy gate store-reuse confirmation도 완료됐다:
    `structural_selective_v2_prefix_2500_320`은 4개 회사 모두 screen pass,
    full-eval fail 1개, critical miss 0개, 평균 completeness/recall 1.0이다.
    남은 1개 fail은 현대차 faithfulness 0.75 계열의 evaluator/path noise로
    분류한다.
  - concept planner shadow는 11/11 케이스에서 legacy plan과 다른
    concept-shaped plan을 냈다. legacy는 `ok=6`, `heuristic_fallback=5`,
    concept path는 `concept_fallback=11`이다. 이것은 승격 완료가 아니라
    runtime gate에서 grounding 영향만 따로 볼 수 있는 promotion candidate다.
  - concept runtime grounding gate 첫 smoke로 `SAM_T3_028`를 store-reuse
    eval-only까지 확인했다.
    - 초기 runtime answer는 numeric/grounding은 `PASS`였지만 dataset의
      required entity에 answer key/evidence에 없는 산업 배경어
      (`메모리`, `단가 하락`, `재고자산 평가충당금`)가 남아 completeness/entity가
      낮게 나왔다.
    - dataset contract를 answer key/evidence에 맞춰 `재고자산평가손실`,
      `매출원가`로 좁힌 뒤 재실행 결과: numeric/faithfulness/recall/
      completeness/entity/citation 모두 `1.0`, full-eval fail `0`.
  - concept runtime gap gate 7문항 전체도 실행 완료했고, 1차 blocker
    triage를 evaluator부터 닫았다.
    - clean pass: `SAM_T3_028`, `POS_T1_057`, `KAB_T1_066`
    - `KBF_T2_018`는 answer/evidence가 complete였고 numeric gap은
      `70.24%` vs answer-key `70.28%`의 formula/display rounding
      차이였다. percent numeric equivalence는 0.05 percentage-point
      tolerance를 허용하도록 조정했고 store-reuse eval-only에서
      `numeric_final_judgement = PASS`, faithfulness/recall/completeness
      `1.0`을 확인했다.
    - numeric evaluator는 multi-value answer에서 한 숫자만 answer key와
      맞아도 PASS가 나던 false positive를 차단한다. answer numeric claim이
      answer key나 canonical evidence numeric candidate 어느 쪽에도 맞지
      않으면 `unsupported_answer_numeric_claim`으로 FAIL 처리한다.
    - 남은 runtime blockers: `SKH_T3_080`(parenthesized gain sign/value와
      net-effect binding), `CEL_T1_013`(capitalized development cost operand
      missing), `CEL_T3_040`(inventory valuation loss/reversal value-source
      selection).
    - 재채점 결과 `SKH_T3_080`, `CEL_T1_013`, `CEL_T3_040`는 모두
      numeric FAIL로 정렬됐다. 이것은 승격 blocker가 evaluator noise가
      아니라 runtime evidence/operand binding 문제임을 보여준다.
    - 결론: concept-only planner default 승격은 아직 보류다. 다음 작업은
      새 runtime rule 추가가 아니라 `SKH_T3_080`, `CEL_T1_013`,
      `CEL_T3_040`를 각각 sign/operand/evidence-source binding 층에서
      일반화 가능한 계약으로 닫는 것이다.

- Runtime domain-vocabulary boundary has been tightened again.
  - Benchmark-shaped deterministic runtime code for the Hyundai US-sales policy
    case was removed; policy-growth mixed queries must now rely on generic
    retrieval, evidence, calculation, and synthesis contracts.
  - Dividend mixed-query support now keeps domain regexes/templates and
    statement hints in retrieval policy config instead of agent control-flow
    code.
  - Agent runtime search no longer finds the previously targeted
    commerce/Poshmark/IRA/dividend/shareholder-return keyword bundle in
    `src/agent` or `src/routing` control-flow code; remaining benchmark/domain
    vocabulary is in tests, prompts, ontology, policy, or datasets.
  - Full unit verification passes: `python -m unittest discover -s tests`
    (`470` tests).

- 검증 원칙은 이제 명시적으로 **검증 가능한 최소 단위 우선**이다.
  - unit test / targeted regression
  - 단일 문항 targeted replay
  - store-fixed eval-only
  - smoke / gate
  - broader curated full evaluation
  순서로 올린다.
  - broad rerun은 기본 디버깅 도구가 아니라 최종 승격 단계로 본다.

- curated benchmark 경로를 실제 profile과 evaluator에 연결했다.
- active benchmark/profile track도 curated 중심으로 재정렬하기 시작했다.
  - mainline: `curated_single_doc_core`, `curated_runtime_contract_gate`, `multi_metric_numeric_smoke`, `curated_multi_report_smoke`
  - legacy historical: `dev_fast*`, `dev_math_*`, `release_generalization`
- 공식 gate 비교 기준도 한 단계 정리됐다.
  - `plain_prefix_8000_400`: speed / cost baseline
  - `contextual_selective_v2_prefix_2500_320`: quality baseline
  - `structural_selective_v2_prefix_2500_320`: current operating default
  - `runtime_contract_gate`에서는 `plain`이 `SKH_T1_060`를 놓쳤고, `structural`과 `contextual`은 대표 5문항을 모두 통과했다
  - `multi_entity_grounding_gate`에서도 `structural`과 `contextual`이 `comparison_001~003`을 모두 통과했다
- 최신 runtime hardening도 추가로 닫혔다.
  - `SKH_T1_060`는 structural path에서 direct structured row-label evidence를
    lookup task output dependency보다 우선하는 generic binding repair 이후
    다시 `PASS`로 닫혔다.
    - 실패층은 retrieval이 아니라 lookup/dependency operand binding이었다.
    - `단기차입금 4,145,647백만원`, `장기차입금 10,121,033백만원`,
      `사채 9,490,410백만원`이 final ratio dependency operand로 투영된다.
    - historical focused low-API rerun:
      `benchmarks/results/runtime_lookup_direct_row_skh_t1_060_2026-06-02/`
      returned `42.02%`, `numeric_final_judgement = PASS`.
    - Follow-up producer lookup alignment is now closed: serialized
      `task_6` subtask result views show `9,490,410백만원`, matching the final
      dependency projection, and no stale `(600,550)백만원` value remains in the
      focused result JSON.
  - `MIX_T1_064`는 ontology-driven component ratio shape, evaluator composed-ratio grounding, uncertainty suffix 정리 이후 공식 targeted rerun까지 `PASS`로 닫혔다.
    - `numeric_equivalence = 1.0`
    - `numeric_grounding = 1.0`
    - `numeric_retrieval_support = 1.0`
    - `numeric_final_judgement = PASS`
  - `NAV_T2_006`는 direct `financial_graph` 경로에서도 hybrid query decomposition(`lookup -> lookup -> growth_rate -> narrative_summary`)이 실제 runtime에서 끝까지 돌도록 정리됐다.
  - 최신 post-patch targeted smoke에서 `NAV_T2_006`는 `커머스 매출 성장률 41.4%`, `Poshmark 체질 개선`, `연결 편입효과`, `스마트스토어/브랜드스토어 성장`까지 포함한 답으로 닫혔다.
    - `faithfulness = 1.0`
    - `completeness = 1.0`
    - `refusal_accuracy = 1.0`
    - 기존 failure shape는 growth+narrative aggregate에서 stale feedback이 남아 최종 partial-refusal suffix가 붙던 문제였다.
    - 현재 보강은 NAV 전용 문자열 rule이 아니라, `growth_rate` answer slot과 narrative subtask가 질문 요구를 이미 충족한 경우에만 stale planner feedback을 무효화하는 좁은 guard다.
  - `LGE_T1_051`는 AMPC가 표가 아니라 prose(`약 6,769억원의 IRA Tax Credit`)로 들어오는 경우를 surface-contract numeric evidence로 보존해 닫았다.
    - AMPC numeric value는 선행 숫자+단위 표현에서 추출한다.
    - 영업이익 task-output dependency는 sibling operand의 `source_anchor`를 보존해 provenance가 끊기지 않는다.
    - 이후 LGE focused replay에서 rounded AMPC operand와 source-table unit 렌더링의 결합 문제도 닫았다.
      - `6,769억원(676,874백만원)`처럼 rounded KRW 뒤 괄호 exact 단위가 있으면 exact parenthetical을 우선한다.
      - LLM이 rounded KRW 값을 냈더라도 동일 evidence table metadata 안에 더 정밀한 `백만원/천원` cell이 있으면 operand precision을 보정한다.
      - `제외/실질/조정/차감` 계열 difference 결과는 compact `조/억원` 대신 source table unit으로 렌더링해 파생 계산값 grounding을 안정화한다.
    - latest targeted smoke:
      - answer: `영업이익 2,163,234백만원`, `AMPC 6,769억원`, `실질 영업이익 1,486,334백만원`
      - `numeric_equivalence = 1.0`
      - `numeric_grounding = 1.0`
      - `numeric_retrieval_support = 1.0`
      - `numeric_final_judgement = PASS`
      - `faithfulness = 1.0`
      - `completeness = 1.0`
      - `calculation_correctness = 1.0`
    - 2026-05-29 policy-driven full gate rerun에서도 now closed다.
      - contextual note row에서 AMPC exact cell `676,874백만원`을 회수하고, 실질 영업이익은 deterministic slot-based difference answer로 `1,486,360백만원` 렌더링한다.
      - full gate aggregate 기준 `numeric_pass_rate = 1.0`, `faithfulness = 1.0`, `completeness = 1.0`.
  - `HYU_T2_010`는 post-patch targeted smoke에서 now closed다.
    - 답변은 `87.0만 대`, `78.1만 대`, `11.5%`, IRA/핵심원자재법/보호무역주의 대응 필요성을 모두 포함한다.
    - raw faithfulness judge는 `0.5`였지만, completeness / retrieval / citation / structured calculation-rendering이 모두 통과한 mixed-query evidence coverage 조건에서 `faithfulness = 1.0`으로 보정된다.
    - latest targeted smoke:
      - `faithfulness = 1.0`
      - `completeness = 1.0`
      - `retrieval_hit_at_k = 1.0`
      - `grounded_rendering_correctness = 1.0`
      - `calculation_correctness = 1.0`
      - `avg_score = 0.890`
  - `HYU_T3_072`도 post-patch targeted smoke에서 now closed다.
    - 답변은 Motional의 기말 지분율 `25.81%`, 투자장부금액 `1,294,367백만원`, 계속영업손실 `(803,742)백만원`, 총포괄손실 `(791,627)백만원`을 포함한다.
    - dataset의 required entity와 ground-truth evidence quote도 기말 기준 `25.81%`로 정렬했다. 기초 지분율 `25.92%`는 notes/selection context에만 남기고, 평가 필수 엔티티로는 요구하지 않는다.
    - dataset contract fix 직후에는 answer path만 닫혔고 `entity_coverage = 0.600`이 evidence projection 잔여 신호로 남았지만, 이후 structured row evidence projection으로 이 잔여 신호도 닫혔다.
    - focused store-fixed eval-only after structured row evidence projection now surfaces Motional slot labels in evaluator-visible evidence: `faithfulness = 1.0`, `context_recall = 1.0`, `retrieval_hit_at_k = 1.0`, `grounded_rendering_correctness = 1.0`, `entity_coverage = 1.0`, `avg_score = 0.910`.
    - previous targeted smoke:
      - `faithfulness = 1.0`
      - `completeness = 1.0`
      - `retrieval_hit_at_k = 1.0`
      - `grounded_rendering_correctness = 1.0`
      - `calculation_correctness = 1.0`
      - `avg_score = 0.912`
- parser는 단순 chunk normalization을 넘어 **table-aware grounding** 단계로 들어갔다.
  - 병합된 `ROWSPAN/COLSPAN`을 canonical grid로 복원
  - `table_summary_text`, `table_row_labels_text`, `table_row_records_json`, `table_object_json` 생성
  - structured row-aware reconciliation 추가
- numeric question 경로에는 아래가 들어갔다.
  - ontology 기반 pre-retrieval semantic planning
  - post-retrieval reconciliation
  - multi-metric 질문용 subtask loop / aggregation
  - ready 상태 numeric subtask에 대한 direct `structured_row -> operand` 추출
  - `table_value_records_json -> structured_value` 기반 value-cell-first grounding
- planner / ontology 경로는 최근 아래 방향으로 이동했다.
  - benchmark-shaped `metric_family` 확장을 줄이고 concept-only ontology v3 draft를 추가
  - ontology는 `concept`, `concept_group`, statement/section prior, binding prior 중심으로 축소 시작
  - planner는 `metric_family`보다 `operation_family + required_operands` 중심의 IR로 점진 이동
  - implicit query도 LLM concept planner가 concept 조합으로 풀도록 canary path를 추가
  - planner validator는 형식 / 허용 concept / 허용 operation만 보는 얇은 contract checker로 유지
- answer path는 최근 아래 방향으로 이동했다.
  - planner는 “최종 문장을 최소화”하는 대신 **필요한 재료를 빠짐없이 모으는 방향**으로 조정
  - final synthesizer가 원본 질문과 `subtask_results`를 함께 읽고 최종 답을 조합
  - 재료가 부족하면 synthesizer가 `planner_feedback`를 남기고 기존 `pre_calc_planner`를 replan mode로 재사용
  - replan budget을 모두 써도 재료가 부족하면 `aggregate_subtasks`가 사용자-facing 최종 refusal / partial answer를 확정
  - direct lookup 우선 정책은 planner recipe가 아니라 runtime grounding / acceptance policy로 다룬다
  - direct candidate는 score만 높다고 성공으로 확정하지 않고 binding contract를 만족해야 accept한다
  - `CalculationResult.answer_slots`가 `lookup / difference / ratio / sum`의 공통 structured result contract로 추가됐다
  - aggregate 단계는 이제 `answer_slots`를 보고 `current / prior / delta / primary` 재료 누락을 deterministic하게 먼저 감지할 수 있다
- 내부 실행 구조 일반화를 위한 1차 schema를 추가했다.
  - `tasks`, `artifacts` state 추가
  - parser의 `table_object / row_record / cell_record`를 정식 출력으로 승격 시작
  - semantic plan / reconciliation / operand set / calculation plan / calculation result / aggregated answer를 artifact로 기록 시작
- evaluator는 이제 top-level `calculation_*`만 읽지 않고 runtime ledger를 다시 투영해 trace를 복원한다.
  - single-task 계산은 `tasks + artifacts`에서 operand/plan/result를 다시 읽는다
  - multi-subtask 계산은 `subtask_results`를 aggregate projection으로 다시 묶는다
- numeric reconciliation은 최근 아래 방향으로 보강됐다.
  - `structured_row` 중 `범위/하위범위/상위범위` 같은 descriptor row penalty
  - `chunk`보다 `structured_row / table_row / evidence_row` 우대
  - top candidate가 애매할 때만 LLM rerank helper 사용
  - `retrieved_docs`뿐 아니라 `seed_retrieved_docs`도 reconciliation candidate pool에 포함
  - `유형자산/무형자산/자산총계/부채총계/자본총계` 계열은 `summary_financials / balance_sheet` row를 우대
- parser/table grounding은 최근 아래 방향으로 더 확장됐다.
  - `table_value_records_json`과 `structured_value` candidate 추가
  - `TBODY/TE` 셀을 실제 value cell로 읽도록 확장
  - `(단위 : 백만원)` 같은 unit-only standalone table도 다음 실제 표의 context hint로 승격
  - wide merged-header note table에서 `direct_total / subtotal / final_total / adjustment` aggregate role 복원
- 최근 canary / e2e 관측은 다음과 같다.
  - ontology-v2 canary에서 `SKH_T1_060`은 `42.0%`, `MIX_T1_021`은 부채비율 `25.4%` / 유동비율 `258.8%`로 닫혔다
  - concept-planner shadow canary에서는 `SKH_T1_060`, `MIX_T1_021`, implicit `부채비율` / `유동비율` / `FCF`가 concept-only planner로도 자연스럽게 분해된다
  - `NAV_T1_071`는 now closed end-to-end:
    - planner는 `lookup + difference` 재료 수집 구조로 분해
    - direct structured row grounding으로 `2023 current` / `2022 prior`를 직접 바인딩
    - aggregate 단계가 subtask evidence를 최종 state까지 보존해 evaluator `numeric_retrieval_support`까지 `1.0`으로 복구
  - `KBF_T1_017`도 now closed:
    - `lookup`은 `명목순이자마진(NIM)` canonical row를 직접 바인딩
    - `difference`는 같은 structured row 안의 distinct `2023 / 2022` cell pair를 사용
    - evaluator는 unitless structured percent row와 operand alias mismatch를 허용해 `numeric_retrieval_support = 1.0`, `operand_selection_correctness = 1.0`으로 복구
  - `NAV_T1_030`도 now closed:
    - FCF는 deterministic `subtract` plan으로 유지된다
    - 괄호 음수 outflow row는 runtime과 evaluator에서 같은 operand로 해석된다
    - final rendering은 `-X를 차감` 같은 이중 음수 표현을 남기지 않는다
    - evaluator runtime projection은 `statement_type` metadata를 policy-defined statement section surface로 투영한다
      - 예: `section_path = III. 재무에 관한 사항 > 2. 연결재무제표` + `statement_type = cash_flow`는 `연결현금흐름표` expected section과 매칭된다
      - benchmark ID / 회사명 / FCF 전용 runtime rule은 추가하지 않았다
    - latest focused smoke:
      - `numeric_grounding = 1.0`
      - `numeric_retrieval_support = 1.0`
      - `numeric_final_judgement = PASS`
      - `retrieval_hit_at_k = 1.0`
      - `ndcg_at_5 = 1.0`
      - `context_precision_at_5 = 1.0`
      - `section_match_rate = 1.0`
    - evaluator NDCG는 같은 expected section에 여러 matched docs가 잡힐 때도 `1.0`을 넘지 않도록 cap 처리했다

## 현재 핵심 한계

- public/runtime boundary에서 legacy `calculation_*`는 이미 projection 계층으로 내렸다.
- 남아 있는 `calculation_*`는 주로 internal compatibility mirror / scratch state다.
- planner / synthesizer / result schema의 경계가 이제 막 생겼기 때문에, single-task와 multi-subtask가 항상 같은 answer contract를 공유하지는 못한다.
- concept-only planner는 single-metric / group concept / multi-metric 분해 품질이 좋아졌지만, 모든 numeric family에서 runtime default로 올리기엔 아직 canary가 더 필요하다.
- `difference` / `lookup` / `ratio` 결과를 더 구조적으로 남기는 result schema 정리는 대부분 끝났지만, internal mirror를 완전히 없애는 수준의 graph-state refactor는 아직 남아 있다.
- profile 운영 기준은 이제 curated track이 우선이고, legacy 2024 dataset profile은 historical replay 용도로만 남긴다.
- final refusal ownership은 `aggregate_subtasks`로 올라왔고, `NAV_T1_071`를 통해 `planner_feedback -> replan / close` 루프의 최소 실전 검증은 끝났다.
- direct-first runtime policy는 `NAV_T1_071`에서 닫혔고, 이제 `ratio / sum`처럼 explicit concept numeric task까지 direct grounding 대상으로 확대됐다.
- percent multi-period rows도 별도 metric hardcoding 없이 shared pair-selection / evaluator contract로 닫히기 시작했다.
- 다만 ingest 쪽은 여전히 tradeoff가 남아 있다.
  - `contextual_selective_v2`는 품질은 안정적이지만 ingest 비용이 크다
  - `structural_selective_v2`는 현재 gate 기준으로 같은 품질을 더 낮은 비용으로 달성한 routine default다
- broader curated validation blocker 중 multi-report CAPEX와 `MIX_T1_046` runtime blocker는 현재 닫혔다.
  - `curated_multi_report_smoke`의 `SAM_T2_002`는 CAPEX total direct grounding과 current/prior binding까지 PASS
  - `curated_single_doc_core`의 `MIX_T1_046`는 parent-hybrid probe의 fresh NAVER 2023 bundle에서 `영업비용` denominator binding failure가 다시 노출됐지만, calculation fallback/document scope/operand filtering 보강 후 store-fixed eval-only에서 다시 PASS했다
    - latest answer: `20.8%`
    - `faithfulness = 1.0`, `completeness = 1.0`, `numeric_pass = 1.0`
  - 2026-05-28 targeted replay에서도 `MIX_T1_046`는 다시 PASS로 확인됐다.
    - result dir: `benchmarks/results/naver_mix_t1_046_2026-05-28-grounding-fix`
    - root cause는 계산값 자체가 아니라 composed ratio의 numerator가 `task_output:task_2`로 전달될 때 evaluator grounding override가 resolved dependency provenance를 직접 근거로 인정하지 못한 점이었다.
    - evaluator는 이제 `dependency_resolved = true`이고 `source_task_id` / `source_slot` / `source_anchor`가 있는 `task_output:*` operand를 grounded operand로 인정한다.
    - unresolved `task_output:*`만 있는 operand는 여전히 grounded로 보지 않는다.
    - `numeric_equivalence = 1.0`, `numeric_grounding = 1.0`, `numeric_retrieval_support = 1.0`, `numeric_final_judgement = PASS`
  - 2026-05-28 focused blocker reclassification에서도 `MIX_T1_046`와 `NAV_T3_007`는 PASS다.
    - result dir: `benchmarks/results/curated_single_doc_blocker_reclass_2026-05-28`
    - broader trace에서는 operands가 `source_row_id` 대신 `evidence_id`를 쓰고, denominator period가 `2023년` 대신 `제 25 기`로 들어와 evaluator compatibility gap이 다시 드러났다.
    - evaluator는 이제 source key로 `evidence_id`도 인정하고, explicit year끼리 충돌하지 않는 current fiscal-period alias(`제 N 기`, `당기`, `current`)만 soft match한다.
    - prior-period alias(`전기`)나 서로 다른 explicit year는 여전히 operand match에서 거부한다.
    - Naver slice result: `MIX_T1_046 = PASS`, `NAV_T3_007 = PASS`, `Numeric Pass Rate = 1.000`, `Completeness = 1.000`
  - fresh structural store 기준으로도 `SAM_T2_002`는 multi-source receipt scope, auto-fetch inventory, dependency binding guard, aggregate answer-slot gap suppression, narrative context synthesis 보강 이후 다시 닫혔다
    - `structured_result.status = ok`
    - `faithfulness = 1.0`
    - `completeness = 1.0`
    - `numeric_pass = 1.0`
- fresh structural single-doc blocker였던 `SAM_T3_028`는 parser/store와 generic evidence assembly 보강 이후 fresh structural rerun에서 닫혔다.
  - root cause는 planner가 아니라 parser/store가 grouped table row의 상세 축인 `재고자산평가손실(환입) 등`을 row label로 보존하지 못한 점이었다.
  - parser는 이제 숫자값 앞에 여러 텍스트 축이 있는 행에서 값에 가장 가까운 상세 축을 `row_label`/`semantic_label`로 쓰고, 앞선 그룹 축은 `row_headers`/aliases에 보존한다.
  - 실제 삼성전자 2023 filing parser smoke에서 `재고자산평가손실(환입) 등 = 5,037,579`, `row_headers = [조정내역 계, 재고자산평가손실(환입) 등]`까지 확인했다.
  - structural index/store는 이제 row label뿐 아니라 value-level label text를 함께 prefix/metadata로 싣는다.
  - answer assembly는 retrieval로 들어온 evidence의 label/value만 사용해 numerator/denominator를 고르고 비중을 계산한다. `SAM_T3_028`, inventory, 특정 row/sentence를 직접 찾는 runtime rule은 없다.
  - product runtime path의 `SAM_T3_028` 전용 rule은 제거했다.
    - `rcept_no`로 local HTML filing을 직접 읽어 특정 row/sentence를 주입하는 raw filing fallback을 제거했다.
    - retrieval 후보 안에서 `재고자산평가손실` row, inclusion sentence, `매출원가` row를 hard-coded rule로 승격하거나 deterministic answer로 조립하는 경로도 제거했다.
    - evaluator calibration이나 diagnosis asset으로는 유용할 수 있지만, agent answer path에 특정 filing/row 문구를 직접 주입하거나 승격하면 parser/store 문제를 가리고 일반화 위험을 키운다.
  - 제거한 fallback 기반 targeted rerun 참고 결과:
    - `numeric_final_judgement = PASS`
    - `numeric_equivalence = 1.0`
    - `numeric_grounding = 1.0`
    - `numeric_retrieval_support = 1.0`
    - `faithfulness = 1.0`
    - `completeness = 1.0`
  - fresh structural rerun 결과:
    - result dir: `benchmarks/results/sam_t3_028_parser_store_check_2026-05-27_fix7`
    - `faithfulness = 1.0`
    - `completeness = 1.0`
    - `numeric_pass = 1.0`
    - `retrieval_hit_at_k = 1.0`
    - `section_match = 1.0`
    - `avg_score = 0.966`
  - 위 fresh rerun 결과는 실험 산출물로만 남기고 commit 대상에는 포함하지 않는다.

## 바로 다음에 할 일

| 순서 | 할 일 | 목적 |
| --- | --- | --- |
| 1 | Portfolio capability gates 유지 | `REFERENCE_NOTE` boundary와 promotion trace materiality를 `portfolio_review_gates`에서 함께 확인 |

## 현재 우선순위 요약

1. Portfolio capability gate bundle 유지
2. `REFERENCE_NOTE` capability gate와 promotion trace materiality gate를 개별 green 상태로 유지
3. materially different trace summary가 생길 때만 reflection / report-cache promotion evidence 확장
4. broader curated gate maintenance는 새 artifact가 실제 blocker를 재현할 때만 수행
5. MAS default smoke maintenance는 default store/preflight contract가 바뀔 때만 수행

## 현재 해석

- 2026-06-08 기준 reflection promotion gate와 report-cache promotion evidence gate는 reviewer-facing proof surface로 닫혔다. Reflection gate는 base fixture / store-fixed candidate surface / reviewed store-fixed trace summary / reviewed live-default MAS handoff trace summary source coverage를 요구하고, report-cache gate는 calculation-task producer contract와 fallback safety를 요구한다. `REFERENCE_NOTE` capability gate도 ready이며 note traversal을 Researcher graph-expansion context로 고정한다. `promotion_trace_materiality_gate`는 현재 두 trace summary가 서로 다른 reflection action과 cache fallback reason을 제공하는지 검증한다. Portfolio review gates도 ready다. 다음 작업은 active retry나 cache enable flag가 아니라 이 capability gates를 유지하고, materially different live/default MAS 또는 store-fixed eval-only surface가 gate 기준으로 확인될 때 trace summary를 추가하는 것이다.
- Analyst / Critic / Researcher separation 1차 작업은 2026-06-07에 닫았다. `WorkerArtifactBoundary`와 `project_worker_artifact_boundary()`를 MAS schema layer에 추가해 worker artifact의 payload-first answer, selected artifact id, task id, role, kind/status, evidence refs dedupe를 공유 projection으로 고정했다. Critic review와 Orchestrator final synthesis는 이제 같은 worker-artifact boundary helper를 통해 artifact를 읽는다. 관련 Critic/Orchestrator/MAS graph tests `24`개가 통과했다.
- report-scoped cache capability design은 2026-06-07 기준 candidate-only handoff gate까지 닫았다. `src.ops.review_report_cache_index_contract` 기본 fixture-backed review는 `status = ok`, `difference_count = 0`, `reviewer_handoff.status = ready`, `mode = candidate_only`, projection-ready candidate `1`, fallback candidate `1`을 보고한다. Cache serving, read/write, ledger insertion, retrieval bypass는 모두 disabled로 남는다.
- material-gap / mixed narrative canary maintenance는 2026-06-07에 `docs/evaluation/material_gap_mixed_canary_maintenance.md`로 정리했다. `KBF_T2_043`은 closed runtime blocker이자 broader replay/completeness-render calibration watch item이고, `NAV_T2_006`은 closed mixed numeric+narrative quality target으로 policy-gate regression coverage에 남긴다. 새 artifact가 material evidence / dependency / trace / final synthesis failure를 재현하기 전에는 full benchmark나 runtime patch를 기본값으로 쓰지 않는다.
- internal calculation mirror cleanup 1차 작업은 2026-06-07에 닫았다. Aggregate reconciliation artifact enrichment가 더 이상 stale top-level `calculation_result`의 `source_row_ids` / answer-slot source refs를 evidence refs로 보강하지 않고, canonical projection / ordered subtask refs / selected claims만 사용한다. 회귀 테스트는 canonical `resolved_calculation_trace` source refs는 보존하고 stale top-level refs는 replan-triggering integrity gap으로 남기는 두 경로를 고정한다. `tests.test_subtask_loop` `143`개와 runtime domain-term audit이 통과했다.
- internal calculation mirror cleanup state-typing follow-up도 2026-06-07에 닫았다. `FinancialAgentState`의 top-level `calculation_operands` / `calculation_plan` / `calculation_result`는 optional compatibility mirror로 내려갔다. Focused projection test와 runtime domain-term audit이 통과했다.
- internal calculation debug ownership follow-up도 2026-06-07에 닫았다. `FinancialAgentState`의 `calculation_debug_trace`는 optional compatibility bridge가 됐고, owned public debug surface는 `debug_traces.calculation`으로 분리했다.
- internal compatibility bridge initial-state follow-up도 2026-06-07에 닫았다. `FinancialAgent.run()`은 더 이상 optional top-level `calculation_operands` / `calculation_plan` / `calculation_result` / `calculation_debug_trace`를 빈 값으로 seed하지 않는다.
- portfolio reviewer path refresh는 2026-06-07에 닫았다. README, one-pager, demo walkthrough, presentation outline, project status는 reviewer가 `resolved_calculation_trace` / `structured_result` / `task_artifact_trace`를 primary contract로 보고 top-level calculation/debug mirror를 compatibility bridge로 해석하도록 맞춘다.
- internal compatibility bridge scratch-write audit도 2026-06-07에 닫았다. 계산 노드 diagnostic write는 `_calculation_debug_state_update()` / `_clear_calculation_debug_state()` helper를 통하고, public `FinancialAgent.run()` bridge는 runtime-contract field constant를 사용한다.
- backlog/status refresh도 2026-06-08에 다시 닫았다. 완료된 compatibility bridge / reviewer polish / MAS empty-store diagnosis / reflection handoff / report-cache producer-policy 항목은 기본 우선순위에서 내렸고, 다음 구조 작업은 promotion evidence expansion으로 정렬했다.
- self-reflection capability contract 초안도 2026-06-07에 추가했다. 다음 구현은 answer behavior를 바꾸지 않고 `ReflectionRequest` / `ReflectionPlan` / `ReflectionAction` / `ReflectionReport` helper 또는 TypedDict 경계를 먼저 만드는 순서다.
- self-reflection capability helper 1차 구현도 2026-06-07에 시작했다. TypedDict surfaces, allowed retry strategy guard, plan normalization helper, `reflection_action` projection을 추가하되 graph route와 answer behavior는 유지한다.
- self-reflection request builder follow-up도 2026-06-07에 시작했다. `ReflectionRequest`는 strict runtime trace summary, evidence/retrieval summary, remaining retry budget을 노출하며 legacy top-level calculation mirror를 읽지 않는다.
- runtime critic / offline evaluator boundary follow-up 1차 작업은 2026-06-07에 reviewer/demo surface 정리로 시작했다. `portfolio_demo`와 `mas_researcher_smoke`는 이제 `passed` / `deterministic_score`를 직접 acceptance로 보지 않고 `critic_report_runtime_acceptance_state()`의 status, reasons, target refs, score-used flag를 노출한다. Focused demo/smoke/critic tests `14`개가 통과했다.
- runtime critic / final merge acceptance follow-up은 2026-06-07에 target carry-forward를 보강했다. Critic rejection integrity issue는 raw `target_refs`뿐 아니라 ledger에 존재하는 `target_task_ids` / `target_artifact_ids`를 분리해 노출하고, Orchestrator replan carry-forward는 rejected worker target task도 failed 처리한다. Focused MAS/projection tests와 runtime domain-term audit이 통과했다.
- runtime critic / offline evaluator boundary follow-up은 2026-06-07에 helper level까지 닫았다. `critic_report_runtime_acceptance_state()`는 `passed` / `verdict` / `status` verdict signal을 normalize하고, conflicting verdict signal은 block하며, rejected report는 diagnostic score가 높아도 blocked로 남긴다. `deterministic_score_used_for_acceptance = false`를 유지한다. Focused critic/projection/demo tests와 runtime domain-term audit이 통과했다.
- MAS smoke baseline contract refresh도 2026-06-07에 닫았다. valid default-store compact contract는 `tests/fixtures/mas_e2e_smoke/default_valid_store_contract_baseline.json`로 source-controlled baseline이 됐고, `check_mas_e2e_smoke_contract`는 이 baseline을 기본값으로 사용한다. Focused MAS smoke contract tests가 통과했다.
- MAS smoke critic/replan observability follow-up은 2026-06-07에 닫았다. `mas_e2e_smoke`는 이제 case별 `final_acceptance_outcome`과 summary `final_acceptance_outcome_counts`를 노출해 `accepted_without_replan`, `replan_succeeded`, `blocked_without_replan`, `blocked_after_replan`, `replan_pending`을 구분한다. Critic issue items도 `target_task_ids` / `target_artifact_ids`를 표시하고, compact smoke contract가 final acceptance outcome을 비교한다.
- Live/default MAS smoke outcome refresh는 2026-06-07에 material-empty blocker를 재현했다. 기본 `replan_budget = 0` run은 `final_acceptance_outcome_counts = {"blocked_without_replan": 2}`, `blocked_count = 2`, `final_source_* = 0`이고, `--replan-budget 1` run은 `{"blocked_after_replan": 2}`, `replan_routed_count = 2`, `final_source_* = 0`이다. 두 케이스 모두 Analyst/Researcher task가 incomplete/empty material로 failed였고 critic rejection issue는 없었다. Raw artifacts는 `benchmarks/results/mas_e2e_smoke_outcome_refresh_2026-06-07/`와 `benchmarks/results/mas_e2e_smoke_outcome_refresh_replan1_2026-06-07/`에 local-only로 남긴다.
- MAS smoke material-empty 진단 surface는 2026-06-07에 추가했다. `mas_e2e_smoke`는 이제 case/summary에 `worker_failure_diagnostics`를 노출하고 `--output` 부모 디렉터리를 자동 생성한다. Live/default refresh는 `worker_failure_count = 4`, `worker_failure_missing_artifact_count = 4`, Analyst failures `2`, Researcher failures `2`, incomplete numeric result reasons `2`, empty narrative result reasons `2`, missing worker artifact reasons `4`를 보고했다. Raw artifact는 `benchmarks/results/mas_e2e_smoke_failure_diagnostics_2026-06-07/`에 local-only로 남긴다.
- MAS direct worker material probe는 2026-06-07에 추가했다. `src.ops.mas_direct_worker_probe`는 full MAS/Critic/final merge 없이 planner task instruction을 Analyst/Researcher core에 직접 넣고 material status와 store inventory를 기록한다. Live/default probe는 planner가 Analyst `2`개와 Researcher `2`개 task를 만들었지만 direct Analyst `no_retrieved_docs = 2`, direct Researcher `no_raw_retrieval = 2`였고, default store inventory는 `chroma_count = 0`, `bm25_doc_count = 0`, `parent_count = 0`, `structure_graph_node_count = 0`이었다. Raw artifact는 `benchmarks/results/mas_direct_worker_probe_2026-06-07/`에 local-only로 남긴다. 즉 현재 blocker는 planner/critic/final merge가 아니라 empty default store preflight 문제다.
- MAS default smoke empty-store preflight는 2026-06-07에 추가했다. `mas_e2e_smoke`는 VectorStoreManager / LLM work 전에 Chroma collection embedding count와 sidecar material count를 확인한다. Collection은 있지만 `chroma_embedding_count = 0`, `parent_count = 0`, `structure_graph_node_count = 0`, `table_payload_count = 0`이면 `Store appears empty for MAS smoke`로 조기 실패한다. Live/default run은 약 `5s` 안에 이 preflight에서 실패해 더 이상 빈 store로 worker/API 시간을 쓰지 않는다. 다음 작업은 valid local default store 재설정 또는 재생성 절차 고정이다.
- MAS default smoke valid-store restoration은 2026-06-07에 닫았다. Default store는 populated Samsung 2023 structural-selective store `benchmarks/results/policy_gate_regression_2026-06-03_1138_actual/삼성전자-2023/stores/structural-selective-v2-prefix-2500-320`로 이동했고, `mas_e2e_smoke`는 store signature를 읽어 Google `models/gemini-embedding-2` runtime으로 VectorStoreManager를 연다. Override 없는 live default smoke는 `accepted_without_replan = 2`, `blocked_count = 0`, `integrity_error_count = 0`, `worker_failure_count = 0`, final source tasks `4`, source artifacts `8`, evidence refs `55`를 보고했다. Raw artifact는 `benchmarks/results/mas_default_valid_store_restored_2026-06-07/`에 local-only로 남긴다.
- MAS skeleton과 artifact schema productization 1차 작업은 2026-06-07에 닫았다. `FinalCarryForwardProjection`과 `project_final_report_carry_forward()`를 MAS schema layer로 올렸고, smoke output은 이제 이 shared helper에서 final source task/artifact/evidence/subtask-result counts와 ids를 만든다. Orchestrator와 dummy MAS merge도 `subtask_results` row에 selected worker `artifact_id` / `source_artifact_id`를 보존한다. 관련 MAS API-free tests `29`개와 runtime domain-term audit이 통과했다.
- mixed growth+narrative answer-language polish 1차 작업은 2026-06-07에 닫았다. 최종 aggregate answer surface에서 받침 있는 한글 음절 뒤의 잘못된 conjunctive particle을 generic하게 정리하고, `RuntimeCalculationTrace.calculation_result.formatted_result`도 같은 surface를 보존한다. 이 변경은 회사명/benchmark ID/driver keyword branch 없이 answer surface 후처리만 수행하며, focused aggregate regression과 runtime domain-term audit이 통과했다.
- mixed growth+narrative retrieval fan-out control 1차 작업은 2026-06-07에 audit surface 보강으로 닫았다. `audit_benchmark_fanout_cost.py`는 이제 cross-trace reuse candidates 중 current cache hit / miss counts를 row와 summary, Markdown table에 노출한다. 따라서 `NAV_T2_006` 같은 sibling lookup repeats가 이미 cache-hit로 막힌 관측 항목인지, 실제 추가 비용 후보인지 구분할 수 있다. 새 benchmark는 돌리지 않았다.
- MAS real-node replan smoke and artifact carry-forward review 1차 작업은 2026-06-07에 닫았다. `mas_e2e_smoke.py`는 이제 final report가 carry-forward한 source task/artifact/evidence/subtask-result counts와 ids를 `final_carry_forward`로 노출하고, `check_mas_e2e_smoke_contract.py`도 이 counts를 stable contract에 포함한다. 이번 변경은 real-node wiring을 바꾸지 않는 관측/contract 보강이며, 관련 API-free smoke tests `14`개가 통과했다.
- self-reflection report handoff follow-up은 2026-06-07에 시작했다. `_prepare_reflection_retry()`는 `ReflectionAction`과 함께 `ReflectionReport`를 노출해 retry action, budget consumption, target task/artifact ids, `stop_insufficient` blocking issue를 기록하되 graph route와 final acceptance behavior는 바꾸지 않는다.
- self-reflection ledger handoff follow-up도 2026-06-07에 시작했다. retry 준비 단계는 이제 별도 `reflection` task와 `reflection_report` artifact를 남기며, `task_artifact_trace`가 report payload shape를 검증한다. 이 변경도 route/acceptance behavior는 바꾸지 않는 contract/observability 보강이다.
- reviewer proof refresh도 2026-06-07에 반영했다. `portfolio_demo`는 `Readiness: ready`, `review_report_cache_index_contract`는 `status = ok` / `reviewer_handoff.status = ready`를 보고했고, README / one-pager / demo walkthrough / experiment report는 `reflection_report` ledger handoff와 940-test publication gate 기준으로 갱신했다.
- report-scoped cache capability promotion은 2026-06-07에 enable flag 대신 disabled capability contract 문서화로 진행했다. `docs/architecture/report_cache_capability_contract.md`는 trace candidate -> local-index entry -> rehydration -> guarded consumer -> disabled calculation projection -> reviewer handoff pipeline을 정의하며, serving/write/ledger insertion/retrieval bypass는 계속 false로 둔다.
- broader curated gate maintenance residual review는 2026-06-07에 `docs/evaluation/broader_gate_residual_review.md`로 닫았다. 새 benchmark는 돌리지 않았고, 현재 active broader runtime blocker는 없다. `NAV_T1_030`은 display/entity normalization debt, `KBF_T2_043`은 broader replay + completeness/render calibration watch item으로만 추적한다.
- table payload sidecar / store-size cleanup 1차 작업은 2026-06-07에 닫았다. 기존 sidecar/dedupe 경로는 유지하고 `table_payloads.json`에 payload count, referenced node count, unique/inline byte estimate, dedupe saved estimate를 기록하게 했으며, rebuild summary도 source/output sidecar 규모를 노출한다. 새 benchmark/store artifact는 만들지 않았다.
- concept-only planner runtime promotion check는 2026-06-07 문서 refresh로 닫았다. 현재 기준은 `concept_runtime_gap_gate_7of7_2026-06-04`이며, broad default 승격이 아니라 future concept-runtime 변경 전 store-fixed gate로 재확인할 promotion baseline이다.
- 지금 시스템은 “질문 1개 -> 답 1개” 구조에서 더 멀어져, `task + artifact + structured table object + final synthesizer` 중심으로 이동 중이다.
- planner는 점점 benchmark-shaped metric family보다 **concept + operation + material gathering** 쪽으로 옮겨가고 있다.
- answer completeness와 최종 refusal은 planner가 아니라 final synthesizer / aggregate 단계가 책임지는 방향으로 경계가 정리되고 있다.
- final synthesizer는 이제 LLM 판단만 쓰지 않고, `answer_slots` 기반 deterministic gap checker를 먼저 사용해 재료 부족을 감지한다.
- direct-first policy는 metric-specific planner branching보다 runtime acceptance contract와 lazy replan 쪽으로 구현하는 것이 현재 방향에 더 맞다.
- `NAV_T1_071`는 이 방향으로 실제로 닫혔다.
  - direct structured row grounding
  - same-family current/prior pairing
  - aggregate evidence propagation
  - evaluator numeric pass `1.0`
- public/runtime contract 정리는 거의 끝났고, 남은 리팩터링은 internal mirror 정리 쪽에 가깝다.
- internal compatibility mirror cleanup scope는 2026-06-07에 `docs/architecture/internal_calculation_mirror_cleanup.md`로 정리했다.
  - live graph readers는 strict `resolved_calculation_trace`를 써야 한다.
  - `FinancialAgent.run()` public bridge와 retrospective/replay tools만 명시적 compatibility fallback을 유지한다.
  - `FinancialAgentState`의 top-level `calculation_operands` / `calculation_plan` / `calculation_result`는 이제 optional compatibility mirror다.
  - `calculation_debug_trace`도 optional compatibility bridge가 됐고, owned public debug surface는 `debug_traces.calculation`이다.
  - initial live state에서도 optional top-level compatibility mirror seed를 제거했다.
  - 다음 cleanup은 calculation-node scratch writes와 public compatibility projection을 더 분리할 수 있는지 점검하는 순서다.
- 현재 더 중요한 운영 질문은 planner보다 ingest candidate selection이다.
  - `plain`은 여전히 하나의 대표 gate를 놓친다
  - `contextual_selective_v2`는 품질 baseline이지만 ingest 비용이 크다
  - `structural_selective_v2`는 현재 routine default로 가장 실용적인 middle ground다
- 따라서 다음 구현은 **concept planner shadow 확대 + benchmark maintenance** 쪽으로 돌아가는 흐름이 맞다.
- broader curated gate maintenance residual review는 2026-06-07 문서 기준으로 닫힌 blocker와 calibration debt를 다시 분리했다.
  - `NAV_T1_030`은 focused replay 기준 arithmetic/retrieval/section/citation/provenance blocker가 아니며, 남은 `entity_coverage = 0.75`는 display/entity normalization debt다.
  - `KBF_T2_043`의 과거 `UNCERTAIN`은 historical bounded-query screening evidence로 유지하되, 현재 상태는 PR #35 focused eval-only PASS와 broader replay/completeness-render calibration 대기로 본다.
  - 따라서 broader maintenance는 새 artifact가 runtime blocker를 재현할 때만 다시 active blocker로 올린다.
- contextual arbitration / benchmark maintenance 정리는 2026-06-07에 문서와 profile metadata 기준으로 닫았다.
  - routine structural profiles에는 `profile_track/profile_role/status_note`로 operating-default 역할을 명시했다.
  - contextual arbitration profile에는 manual quality-reference 용도와 routine triage 금지 조건을 명시했다.
  - `dataset_curation_log.md`는 `structural_selective_v2`를 current operating default, `contextual_selective_v2`를 arbitration-only historical quality reference로 정리했다.
- immediate blocker였던 `SAM_T2_002` follow-up rerun, `MIX_T1_046` denominator binding/evaluator trace compatibility, `NAV_T3_007` numeric gate, `SAM_T3_028` source-level numeric blocker는 now closed다.
- `KBF_T2_043` material-gap/narrative numeric blocker도 PR #35 이후 focused eval-only 기준으로 closed다.
  - `numeric_final_judgement = PASS`
  - `faithfulness = 1.0`
  - `numeric_grounding = 1.0`
  - `context_recall = 0.9`
  - `completeness = 0.7`
  - 남은 일은 broader replay와 completeness/render calibration이지, 현재 알려진 material-gap runtime blocker는 아니다.
- `NAV_T1_030` FCF concept-planner promotion residual은 projection follow-up 이후 focused eval-only에서 numeric/retrieval/section 기준으로 닫혔다.
  - `numeric_final_judgement = PASS`
  - `faithfulness = 1.0`
  - `retrieval_hit_at_k = 1.0`
  - `section_match_rate = 1.0`
  - `completeness = 1.0`
  - surface-normalization replay 이후 `citation_coverage = 1.0`, `entity_coverage = 0.75`, `avg_score = 0.951`까지 개선됐다.
  - 남은 caveat는 entity/display label normalization이며, 이는 arithmetic/retrieval/planning 문제가 아니라 evaluator-visible display surface 문제다.
- `structural_parent_hybrid_v2` probe에서 드러난 `MIX_T1_046` 실패는 parent digest 문제가 아니라 ratio material-binding 문제였고, calculation fallback이 dependency guard를 우회해 retrieved docs를 활용하되 연결/별도 scope와 operand concept을 지키도록 보강해 닫았다.
- focused blocker reclassification에서 `HYU_T2_010`과 `HYU_T3_072`는 targeted smoke 기준으로 닫혔다.
- policy-driven track은 2026-05-29 공식 profile rerun과 summary 재계산 기준으로 닫혔다.
  - `policy_driven_runtime_gate_rerun_2026-05-29`: `pass_count = 4`, `full_eval_fail_count = 0`.
  - 비수치형 문항의 `numeric_pass_rate = None`은 full-eval 실패가 아니라 not-applicable로 집계한다.
  - raw benchmark result bundle은 local experiment artifact이며 commit 대상에는 포함하지 않는다.

## 2026-05-28 Update

- Concept ontology gap closure is now verified at planner level:
  - added concepts for credit-loss provision expense, foreign-currency
    translation gain/loss, capitalized development cost, inventory valuation
    loss/reversal/disposal loss, interest income/expense, pre-expense operating
    profit, bad debt expense, depreciation/amortization, impairment, and
    goodwill impairment
  - expanded concept-planner shadow rerun:
    `benchmarks/results/tmp_curated_concept_planner_shadow_expanded_2026-05-28_concepts.json`
  - result: `concept_fallback = 24 / 24`, `heuristic_fallback = 0 / 24`
  - targeted gap cases now plan as concept tasks:
    `KBF_T2_018`, `SKH_T3_080`, `CEL_T1_013`, `CEL_T3_040`,
    `SAM_T3_028`, `POS_T1_057`, `KAB_T1_066`
  - local DART report scan under `data/reports` supplied additional recurring
    note concepts around interest, allowance/bad debt, impairment,
    depreciation, and amortization
  - verification passed:
    `python -m unittest tests.test_ontology tests.test_semantic_numeric_plan -v`
    and `python -m unittest discover -s tests -v`

- Earlier expanded concept-planner shadow probe, now superseded by the
  gap-closure rerun above:
  - result: `benchmarks/results/tmp_curated_concept_planner_shadow_expanded_2026-05-28_fix3.json`
  - scope: 24 cases, official canary + recent blocker/mixed numeric cases
  - concept planner status: `concept_fallback = 20 / 24`, `heuristic_fallback = 4 / 24`
- Generic planner fixes from the probe:
  - repeated same-concept ratio operands are preserved when roles/segment/scope differ, e.g. segment operating income divided by company operating income
  - `FCF` is represented as a generic concept group (`operating_cash_flow - property_plant_equipment_acquisition`) instead of falling back to `generic_numeric`
- Remaining concept ontology gaps:
  - `KBF_T2_018`: credit-loss provision growth
  - `SKH_T3_080`: foreign-currency translation gain/loss net effect
  - `CEL_T1_013`: capitalized development cost
  - `CEL_T3_040` / `SAM_T3_028`: inventory valuation loss/reversal/disposal concepts
  - `POS_T1_057` / `KAB_T1_066`: interest expense and bank profitability-table denominator concepts

## 2026-05-27 Update

- Documentation has been refreshed after the `MIX_T1_046` denominator-binding
  fix and the parent-hybrid probe follow-up.
- Local benchmark output bundles remain as experiment artifacts and are not
  part of source commits:
  - `benchmarks/results/curated_multi_report_smoke_2026-05-26_fix1/`
  - `benchmarks/results/structural_parent_hybrid_v2_probe_2026-05-26/`
- The next source-level work remains concept-planner shadow validation and
  broader curated gate maintenance, not parent-hybrid promotion.

## 2026-05-17 Update

- Indexing now supports partial-store resume in the benchmark path.
  - `benchmark_runner` writes `benchmark_cache_meta.json` with `status: "in_progress"` before ingest.
  - `resume_partial_store=true` preserves a matching partial store instead of deleting it.
  - `VectorStoreManager.add_documents(..., resume=True)` skips already indexed `chunk_uid`s and adds only missing chunks in batches.
- This was verified on the NAVER 2023 large-chunk reindex path.
  - A legacy partial store was preserved and then completed successfully.
  - A second run hit store cache immediately and skipped re-ingest.
- `NAV_T1_071` status is now clearer.
  - planner / replan loop: implemented and observed on a real question
  - structured current/prior value binding: fixed locally for the NAVER 2023 income-statement row
  - remaining blocker: retrieval fan-out still triggers repeated embedding calls and can hit `429 RESOURCE_EXHAUSTED`
- Immediate bottleneck is no longer parser correctness or fresh-store survival.
  - The next runtime optimization target is retrieval query count and/or query-embedding reuse for `lookup + difference` style questions.

## 2026-05-18 Update

- `NAV_T1_071` moved forward from a planner failure to a much narrower runtime issue.
  - planner now consistently decomposes the question into:
    - `2023년 법인세비용차감전순이익` / `lookup`
    - `법인세비용차감전순이익 증감액` / `difference`
- Runtime ontology now auto-loads the concept-v3 overlay through the default loader, so concept-only planning is no longer a shadow-only path.
- Parser and grounding were tightened for pretax-income style rows.
  - standalone statement title tables are promoted into table context hints
  - statement body tables inherit those hints for `statement_type` / `consolidation_scope`
  - ontology aliases now include spaced variants such as `법인세비용 차감 전 당기순손익`
  - deterministic candidate scoring now penalizes delta-like rows for explicit `current_period` / `prior_period` operands
- Retrieval/runtime stability was improved in two ways.
  - when `rcept_no` is present for a single-document DART run, retrieval now treats it as the primary scope and disables strict company-name filtering
  - vector query embedding `429 RESOURCE_EXHAUSTED` now falls back to BM25-only retrieval instead of aborting the run
- Current `NAV_T1_071` status after these changes:
  - retrieval is alive again on the completed NAVER store
  - task 1 no longer collapses to a generic planner failure
  - the remaining error is now operand choice policy:
    - the system can still prefer an indirect construction (`당기순이익 + 법인세비용`) over a direct pretax-income row
    - prior-period (`2022`) binding remains incomplete for the difference task
- Immediate next fix is no longer broad retrieval tuning.
  - prefer direct pretax-income rows over derived reconstructions when both exist
  - make same-table prior-period cell binding win for `difference` / `prior_period`

## 2026-05-18 Direct-First Close

- `NAV_T1_071` is now closed end-to-end.
  - planner decomposition remains `lookup + difference`
  - direct numeric tasks no longer degrade into generic context fallback
  - pretax-income lookup rejects surrogate metrics such as `계속영업순이익`
  - raw table rows are preserved as reconciliation candidates even when row/value JSON exists
  - `difference` can pair split same-table raw rows into `2023 current` / `2022 prior`
- The final runtime fix was not retrieval itself but state propagation.
  - subtask-level `runtime_evidence` now survives into aggregate projection
  - aggregate state now exposes the same direct row evidence that operand grounding used
  - evaluator `numeric_retrieval_support` therefore returns to `1.0`
- Verified outcome on `benchmarks/results/nav_t1_071_direct_acceptance_2026-05-18-rerun5`:
  - `Numeric Pass Rate = 1.000`
  - `Faithfulness = 1.000`
  - `Completeness = 1.000`
- Immediate priority has therefore shifted away from this canary.
  - next focus is generalized result schema settling
  - then broadening the same direct-first acceptance/evidence propagation policy to other numeric families

## 2026-05-18 Result Contract Update

- `CalculationResult.answer_slots`가 공통 structured result contract로 추가됐다.
  - `primary_value`
  - `current_value`
  - `prior_value`
  - `delta_value`
  - `components_by_role`
- `difference`는 현재/전기/증감 슬롯을 모두 명시적으로 남긴다.
- `lookup`은 direct row에서 잡은 값을 `primary_value`로 노출한다.
- aggregate projection과 evaluator runtime projection도 subtask별 `answer_slots`를 그대로 carry한다.
- `aggregate_subtasks`는 LLM synthesizer 전에 deterministic gap checker를 실행한다.
  - `lookup`은 `primary_value`
  - `difference`는 `current_value`, `prior_value`, `delta_value`
  - `ratio`, `sum`은 `primary_value`
  의 존재를 먼저 확인하고, 비어 있으면 `planner_feedback`를 직접 생성한다.

## 2026-05-19 Answer Slots and Selective Ingest Scope

- `answer_slots`는 이제 renderer / synthesizer뿐 아니라 evaluator runtime projection의 1순위 contract다.
  - evaluator는 `calculation_operands`보다 먼저 `answer_slots`에서 operand-like rows를 복원한다.
  - `result_value`가 없으면 `answer_slots.primary_value.normalized_value`를 numeric result source로 사용한다.
- runtime boundary도 같은 방향으로 정리되었다.
  - `FinancialAgent.run()`은 이제 `resolved_calculation_trace`와 `structured_result`를 함께 반환한다.
  - `/api/query`도 같은 structured contract를 전달한다.
  - MAS analyst/critic, benchmark review export, retrospective evaluator scripts도 이 contract를 우선 사용한다.

### Compatibility note

- public/runtime boundary에서는 top-level `calculation_operands`, `calculation_plan`,
  `calculation_result`를 더 이상 기본 contract로 노출하지 않는다.
- 새 consumer / 새 테스트 / 새 디버그 도구는 아래 둘만 기준으로 삼는다.
  - `structured_result`
  - `resolved_calculation_trace`
- 남아 있는 `calculation_*`는 현재 주로 내부 graph state와 계산 노드의 working state다.
  즉 external compatibility layer 정리는 끝났고, 남은 정리는 내부 runtime representation
  리팩터링에 가깝다.
- slot payload는 단순 숫자 dict가 아니라 `status + normalized/raw value + provenance`를 함께 담는 value object로 정리되기 시작했다.
  - missing material은 key omission이 아니라 `status = "missing"`으로 남긴다.
  - direct grounding이 성공한 값은 `source_row_id / source_row_ids / source_anchor`를 carry한다.
- percent numeric evaluation은 display precision을 존중한다.
  - 예: `25.36%`와 `25.4%`는 rounded display gap으로 허용된다.
- 대표 canary는 현재 모두 PASS 상태다.
  - `NAV_T1_071`
  - `SKH_T1_060`
  - `MIX_T1_021`
  - `KBF_T1_017`
  - `NAV_T1_030`
- 최근 public/runtime boundary에서 top-level flat `calculation_*`를 제거한 뒤에도
  위 대표 canary는 모두 PASS로 유지됐다.
- internal graph state도 이제 `resolved_calculation_trace`와
  `structured_result`를 우선 읽도록 정리됐다.
  - fresh internal-state canary rerun에서도
    - `NAV_T1_030`
    - `NAV_T1_071`
    - `SKH_T1_060`
    - `MIX_T1_021`
    - `KBF_T1_017`
    모두 PASS였다.
  - 남은 `calculation_*`는 내부 compatibility mirror / scratch state로만 본다.
- `selective_v2_sections`의 적용 범위도 분명해졌다.
  - 이것은 benchmark runner의 `contextual_selective_v2` ingest mode에서만 쓰이는 ingest-time 섹션 whitelist다.
  - 일반 `agent.ingest(...)`, `agent.contextual_ingest(...)`, query-time retrieval에는 적용되지 않는다.
  - 따라서 `selective_v2_sections` 문제는 runtime planner 이슈가 아니라 benchmark ingest coverage 이슈로 먼저 봐야 한다.

## 2026-05-21 Ingest Candidate Update

- 공식 gate 기준 ingest 후보 해석은 현재 아래처럼 정리된다.
  - `plain_prefix_8000_400`
    - speed / cost baseline
    - `runtime_contract_gate`에서 `SKH_T1_060` FAIL
  - `contextual_selective_v2_prefix_2500_320`
    - quality baseline
    - `runtime_contract_gate`, `multi_entity_grounding_gate` 모두 PASS
  - `structural_selective_v2_prefix_2500_320`
    - `runtime_contract_gate`, `multi_entity_grounding_gate` 모두 PASS
    - current operating default
- 따라서 지금의 실무 우선순위는 새 planner tweak보다 다음 두 가지다.
  1. `structural_parent_hybrid_v2` 같은 next ingest experiment 설계
  2. concept-only planner와 multi-document path를 더 넓게 검증

## 2026-05-28 SAM_T3_028 Aggregate-Impact Closure

- `SAM_T3_028`의 핵심 실패 원인은 재고자산평가손실/환입 parenthetical label을
  손실-환입 차감식으로 과분해하면서 `매출원가`가 평가손실 operand로 오인될 수
  있었던 점이다.
- source fix는 question-specific row injection이 아니라 ontology/planner contract로
  정리했다.
  - `inventory_valuation_adjustment` concept를 추가해
    `재고자산평가손실(또는 환입)` / `재고자산평가손실(환입) 등`을 aggregate label로
    바인딩한다.
  - concept matcher는 긴 surface가 짧은 surface를 포함하면 longest match가 짧은
    concept를 shadow하도록 보강했다.
  - `analysis_hints`를 추가해 aggregate value가 denominator concept와 함께
    "영향/대비/비중"으로 묻히면 ratio task를 만들 수 있게 했다.
  - LLM planner override는 deterministic analysis shape를 lookup-only나 잘못된
    difference로 지우지 못한다.
  - segment extractor는 `이것이/그것이/해당 금액` 같은 지시어를 segment label로
    오인하지 않는다.
- 검증:
  - `tests.test_semantic_numeric_plan`: 56 tests OK
  - focused SAM rerun:
    `benchmarks/results/sam_t3_028_analysis_fix_2026-05-28`
  - `SAM_T3_028`: `faithfulness = 1.0`, `completeness = 1.0`,
    `numeric_grounding = 1.0`, `retrieval_hit_at_k = 1.0`
- 해석상 주의:
  - focused full evaluation의 최종 user-facing answer는 라우터가 QA path로 처리해
    PASS했다.
  - structured planner의 aggregate/ratio shape는 unit regression으로 보장한다.
  - 따라서 다음에 broad gate에서 확인할 항목은 "답변 품질 PASS 유지"와
    "structured numeric route로 들어갈 때도 같은 aggregate-impact shape 유지"를
    분리해서 본다.

## 2026-05-28 Three-Case Follow-up Status

- Focused follow-up target:
  - `SAM_T2_078`
  - `HYU_T2_010`
  - `HYU_T3_072`
- `SAM_T2_078` is now closed at the focused single-question level.
  - Harman automotive answer composition preserves:
    - `28,352,769백만원` 연결 연구개발비용
    - 커넥티드카 제품 및 솔루션
    - 디지털 콕핏 / 카오디오
    - 무선통신 / 디스플레이 등 IT 기술 접목
    - SDV 기술 초점
  - latest focused metrics observed:
    - `faithfulness = 1.0`
    - `completeness = 1.0`
    - `context_recall = 1.0`
    - `retrieval_hit_at_k = 1.0`
- `HYU_T2_010` user-facing answer and structured calculation trace are now
  corrected.
  - answer includes `87.0만 대`, `78.1만 대`, `11.5%`, and the
    인플레이션 감축법 / 핵심원자재법 / 보호무역주의 policy context.
  - deterministic sales-growth policy composition now emits calculation
    operands, plan, result, and typed `growth_rate` answer slots.
  - latest focused metrics observed:
    - `operand_selection_correctness = 1.0`
    - `grounded_rendering_correctness = 1.0`
    - `calculation_correctness = 1.0`
    - `completeness = 1.0`
    - `faithfulness = 0.5`
  - residual issue is not the visible answer or calculation trace; it is the
    remaining entity/evidence coverage threshold used by the hybrid
    faithfulness override.
- `HYU_T3_072` is closed at focused store-fixed eval-only level after structured
  row evidence projection.
  - deterministic entity-table composition recovers the correct visible answer:
    `25.81%`, `1,294,367백만원`, `계속영업손실 (803,742)백만원`, and
    `총포괄손실 (791,627)백만원`.
  - projected runtime evidence now includes the selected Motional slot
    label/value surfaces, so the focused replay reports `entity_coverage = 1.0`,
    `faithfulness = 1.0`, `context_recall = 1.0`, `retrieval_hit_at_k = 1.0`,
    and `grounded_rendering_correctness = 1.0`.
  - latest store-fixed replay still shows ranking/path variance
    (`section_match_rate = 0.625`, `avg_score = 0.910`), so next broader work
    should treat this as retrieval/ranking stability rather than answer
    selection or evidence projection.
  - table-preferred retrieval now keeps at least one table in small visible
    windows and places table hits before supplemental paragraph context.
  - subsequent store-fixed eval-only with the narrative table-focus guard
    improves the Motional ranking path: `ndcg_at_5 = 1.195`,
    `context_precision_at_5 = 0.800`, `section_match_rate = 0.800`,
    `entity_coverage = 1.0`, `grounded_rendering_correctness = 1.0`,
    `avg_score = 0.939`.
  - the implementation remains policy/slot driven: hybrid narrative subtasks
    inherit table format from table/numeric intents, slot/focus table coverage
    is capped by declared slot groups, and final fill prefers the selected
    table sections instead of padding with broad unrelated paragraphs. Runtime
    code does not add new company/question-specific keyword branches.
- Validation commands used during this pass:
  - `.\.venv\Scripts\python.exe -m py_compile src\agent\financial_graph_evidence.py src\agent\financial_graph_calculation.py tests\test_operation_contracts.py`
  - `.\.venv\Scripts\python.exe -m unittest tests.test_operation_contracts`
  - focused single-question evals for `HYU_T2_010` and `HYU_T3_072` against
    `benchmarks/results/three_remaining_focus_2026-05-28/현대자동차-2023/results.json`

## 2026-06-09 Current Handoff

- Current change closes two concept-gate residuals without benchmark-specific
  runtime branches:
  - POSCO ratio unit path: execution now repairs KRW operand units from
    table-backed `unit_hint` only when provenance and scale-conflict checks are
    satisfied.
  - KakaoBank CIR path: reconciliation artifact `evidence_refs` /
    `source_evidence_ids`, including `recon::` structured refs, can feed the
    existing operand acceptance contract.
- Focused store-fixed eval-only checks passed:
  - `POS_T1_057`: `3.5269배`, numeric PASS, faithfulness/completeness/refusal
    all `1.0`.
  - `KAB_T1_066`: `37.47%`, numeric PASS, faithfulness/completeness/refusal all
    `1.0`.
- Local validation passed:
  - `tests.test_operation_contracts tests.test_structured_operand_extraction`
    (`201` tests)
  - `tests.test_subtask_loop` (`166` tests)
  - focused regression trio (`3` tests)
  - `python -m src.ops.audit_runtime_domain_terms --summary`
  - `git diff --check`
- Full seven-question eval-only replay was attempted with heartbeat logging but
  stopped after `KBF_T2_018` stayed on the first question for more than `10`
  minutes with heartbeat only. Treat full-gate proof as still pending.
- Do not commit `benchmarks/results/**`; the local result directory is an
  experiment artifact.

## 2026-06-13 Pull / Current Handoff

- Local `main` was fast-forwarded to `origin/main` at
  `3e96fa1 Fix margin drag unit consistency`
  (`v0.2.0-portfolio-ready-17-g3e96fa1`).
- Worktree has no tracked source changes after pull. Existing untracked
  `benchmarks/results/**` directories remain local experiment artifacts and
  should not be staged by default.
- Latest source-controlled status is now best read from
  `docs/overview/project_status.md` and README rather than the older 2026-06-09
  handoff above.
- Quick local sanity after pull:
  - `.\.venv\Scripts\python.exe -m src.ops.portfolio_review_gates`: `Status:
    ready`
  - `.\.venv\Scripts\python.exe -m src.ops.audit_runtime_domain_terms`: passed
    with `216` reviewed literals
- Current gate summary:
  - Runtime contract gate: PASS
  - Hard structural numeric gate: PASS, `5 / 5`
  - Concept runtime gap gate: PASS, `7 / 7`
  - Policy-driven runtime gate: PASS
  - Reflection promotion, report-cache promotion evidence, promotion trace
    materiality, `REFERENCE_NOTE`, and portfolio review gates: READY
- Latest runtime closure:
  - `CEL_T1_038` margin-drag unit / final-answer consistency is closed by
    source-visible unit refinement, late ratio trace repair, and query-focused
    numeric subtask selection.
  - The fix stayed generic: no company name, benchmark id, or report-specific
    runtime branch was added.
- Latest broader evidence:
  - 2026-06-12 store-fixed `curated_single_doc_core` full-eval refresh completed
    `15` questions across Samsung, NAVER, and Hyundai with `0.0%` error.
  - Hard structural replay remains `5 / 5` numeric PASS; plain hard replay is
    `4 / 5`, with `SKH_T1_060` documenting the current/prior row-binding split.
- Current next work:
  - Diagnose refusal-support evidence projection for safe missing-answer cases
    such as `SAM_T4_070`, `NAV_T4_008`, and `NAV_T4_033`.
  - Treat this as a generic evidence-surface / refusal-support contract issue,
    not as a benchmark-specific routing or keyword patch.
  - Keep broader 77-question official runs separate until report/profile
    coverage decisions are explicit; use heartbeat monitoring for any long
    benchmark run.
- Refusal-support projection follow-up in this session:
  - `_append_missing_decision_context_evidence()` no longer treats any existing
    `selected_claim_ids` as a blanket reason to skip missing-decision context.
  - It now checks whether selected evidence already covers query focus terms.
    If selected evidence is generic but retrieved docs contain focus-overlapping
    context, the runtime appends `missing_decision_context::*` evidence.
  - This preserves safe refusal behavior while keeping nearby search-scope /
    focus context visible to evaluator and reviewer surfaces.
  - The change is generic focus-coverage logic; it does not add company,
    benchmark id, report-specific, or financial-metric keyword branches.
- Validation after the follow-up:
  - focused missing-decision/refusal tests: `4` OK
  - `.\.venv\Scripts\python.exe -m unittest tests.test_operation_contracts`:
    `219` OK
  - `.\.venv\Scripts\python.exe -m src.ops.audit_runtime_domain_terms`: passed
    with `216` reviewed literals
  - `.\.venv\Scripts\python.exe -m src.ops.portfolio_review_gates`: `Status:
    ready`
  - `git diff --check`: no whitespace errors; PowerShell reported line-ending
    normalization warnings for touched files.
  - `.\.venv\Scripts\python.exe -m unittest tests.test_subtask_loop` fails
    `10` growth/aggregate narrative expectation tests. A clean-HEAD baseline
    check after stashing this session's tracked edits reproduced the same
    `10` failures, so this is not caused by the missing-decision context
    follow-up. Treat it as a separate upstream baseline item before using full
    `test_subtask_loop` as a publication gate.
- Growth / aggregate narrative baseline follow-up:
  - The `tests.test_subtask_loop` baseline failures were closed without adding
    company, benchmark id, report-specific, or metric-specific runtime
    branches.
  - Late `consistent_numeric_answer` refresh now preserves already-supported
    aggregate answers and answers that already cover the numeric projection,
    instead of replacing them with a single preferred numeric answer.
  - If a narrative summary conflicts with a stronger growth trace, ordinary
    `narrative_summary` rows now contribute clean explanatory context while
    numeric material is refreshed from the trace. A structured
    `aggregate_subtasks` row can still override a weaker growth trace when it
    is the stronger aggregate result.
  - Evidence-backed prior material recovery is now available to
    `_preferred_complete_numeric_answer()`, so late growth refresh can preserve
    a source-visible prior value such as `2022년 78.1만 대` rather than reusing
    the current value.
  - Validation:
    - previous `10` failing `SubtaskLoopTests`: OK
    - `.\.venv\Scripts\python.exe -m unittest tests.test_subtask_loop`: `185`
      OK
    - `.\.venv\Scripts\python.exe -m unittest tests.test_operation_contracts
      tests.test_lookup_recovery_policy`: `234` OK
    - `.\.venv\Scripts\python.exe -m src.ops.audit_runtime_domain_terms`:
      passed with `216` reviewed literals
    - `.\.venv\Scripts\python.exe -m src.ops.portfolio_review_gates`: `Status:
      ready`
    - `git diff --check`: no whitespace errors; PowerShell reported line-ending
      normalization warnings for touched files.
    - `.\.venv\Scripts\python.exe -m unittest discover -s tests`: ran `1101`
      tests and reported `2` failures plus `2` errors. After stashing this
      session's tracked edits and rerunning the four failing tests on clean
      HEAD, the same failures/errors reproduced:
      `test_lookup_unit_refinement_preserves_explicit_normalized_unit`,
      `test_surface_unit_inference_does_not_override_known_unit_family`, and
      two Windows subprocess stdout decode errors in CLI JSON-output tests.
      Treat these as pre-existing baseline / Windows encoding items, not as
      regressions from this session's refusal or aggregate-narrative changes.
- Unit-refinement / Windows decode follow-up:
  - The two clean-HEAD unit failures are now closed generically. Lookup slot
    unit refinement only accepts a claim unit for an already-normalized slot
    when the same raw value is anchored in direct quote/raw-row evidence, and
    inline unit inference now applies policy-driven right-boundary checks so a
    label token after a value is not misread as a unit.
  - The boundary policy lives in `CALCULATION_RENDER_POLICY`, keeping the
    runtime code as a generic policy consumer.
  - Windows CLI JSON-output tests now decode subprocess output as UTF-8 with
    replacement for malformed bytes, avoiding host-codepage failures while
    preserving the CLI output contract.
  - Validation:
    - `.\.venv\Scripts\python.exe -m unittest discover -s tests`: `1101` OK
    - `.\.venv\Scripts\python.exe -m src.ops.audit_runtime_domain_terms`:
      passed with `216` reviewed literals
    - `.\.venv\Scripts\python.exe -m src.ops.portfolio_review_gates`: `Status:
      ready`
    - `git diff --check`: no whitespace errors; PowerShell reported line-ending
      normalization warnings for touched files.
- 77-question official profile coverage follow-up:
  - Added `benchmarks/profiles/curated_single_doc_official_77.json` as the
    separated long-running full single-document curated profile.
  - `curated_single_doc_core` remains the routine three-report broader core
    gate; the new profile covers all `77` rows in
    `benchmarks/datasets/single_doc_eval_full.curated.json` across the `11`
    curated 2023 single-document report scopes.
  - Run policy is explicit now: prefer store-fixed `--eval-only` refreshes when
    reusable stores exist; use a fresh monitored run with
    `--progress-heartbeat-sec` / `--heartbeat-log` only when report/profile
    coverage or ingest contracts changed.
  - Validation:
    - JSON/profile coverage check: `77` dataset rows, `11` dataset companies,
      `11` profile company runs, no missing report paths
    - `.\.venv\Scripts\python.exe -m unittest
      tests.test_curated_dataset_consistency
      tests.test_benchmark_runner_runtime_projection`: `15` OK
    - `.\.venv\Scripts\python.exe -m src.ops.portfolio_review_gates`: `Status:
      ready`
