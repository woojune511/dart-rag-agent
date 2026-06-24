# Numeric Regression Methodology

> Internal operating method for numeric benchmark regressions. This is not a
> scorecard. It describes how to turn a benchmark failure into a general runtime
> fix without using the benchmark as an answer key.

## Purpose

Numeric regressions in this repository are rarely just "wrong arithmetic." A
failure can come from retrieval, row binding, operand extraction, unit repair,
dependency reuse, answer rendering, trace projection, or evaluator
interpretation. The method is to isolate the failing layer first, then make the
smallest general contract change that fixes that layer.

## Working Loop

| Step | Output | Stop condition |
| --- | --- | --- |
| 1. Classify | Failure layer and owner file | The issue can be named without a company-specific branch. |
| 2. Reproduce small | Unit or focused replay | One row/failure mode is reproducible. |
| 3. Patch contract | Generic runtime, policy, schema, or evaluator change | No benchmark ID, company name, or metric recipe is added to runtime control flow. |
| 4. Pin tests | Focused regression tests | The fixed behavior is checked at the contract boundary. |
| 5. Focused eval-only | Single question or company replay | The original row closes with healthy evidence and numeric signals. |
| 6. Broader eval-only | Store-fixed multi-company replay | No adjacent row regresses. |
| 7. Record | Experiment history and current status | The result can be reconstructed without committing raw result bundles. |

## Failure Layer Taxonomy

| Layer | Typical symptom | Correct fix location |
| --- | --- | --- |
| Ontology / policy | Missing concept, alias, section prior, or period marker | `src/config/*` or documented policy data |
| Retrieval | Correct row never enters candidate pool | retrieval policy, parser structure, or query planning |
| Evidence selection | Correct row exists but loses to a weaker row | evidence schema, provenance scoring, diversity / row binding |
| Reconcile plan | Required operands are incomplete or bound to the wrong producer task | planner contract or reconciliation scoring |
| Operand extraction | Evidence row is correct but extracted value/unit/period is wrong | calculation operand extraction and surface contract |
| Formula / calculator | Inputs are correct but operation/result is wrong | deterministic formula policy or calculator |
| Aggregate subtasks | Correct subtask outputs are overwritten or combined incoherently | dependency binding and task-output repair |
| Projection / rendering | Final answer text is correct but trace/evaluator sees stale material, or vice versa | public projection, answer slots, render policy |
| Evaluator | Runtime trace is correct but judgement is misleading | evaluator normalization or metric interpretation |

## Evidence And Trace Rules

- Treat source-visible numeric displays as first-class answer slots. If a source
  sentence or table shows a value, preserve its display unit and keep any
  deterministic recomputation in trace metadata.
- Do not let a later aggregate synthesis invent a different display unit when
  evidence already supplies the displayed value.
- When expansion or reranking moves a relevant raw chunk out of final
  `retrieved_docs`, the seed candidate can still be promoted only if it satisfies
  the active required-operand and provenance contract.
- If a task-output operand and a direct-evidence operand conflict, compare their
  source row ids and repair provenance. A direct row should not overwrite a
  coherent task output just because it is nearby in the same retrieved context.
- If final answer text and projected calculation trace diverge, treat that as a
  runtime contract bug even when the human-visible answer looks right.

## Eval-Only Discipline

The default benchmark refresh mode after runtime, evaluator, rendering, or
projection changes is store-fixed `--eval-only`. It reuses the existing parsed
store but reruns the current agent and evaluator. Use fresh ingest only when the
parser, ingest profile, store signature, or source bundle is part of the change.

Always use a heartbeat for runs that can take more than a few minutes:

```bash
python3 -m src.ops.benchmark_runner \
  --config benchmarks/profiles/curated_ablation_expanded_candidate_full_system.json \
  --output-dir benchmarks/results/ablation_expanded_candidate_full_system_2026-06-10 \
  --eval-only \
  --progress-heartbeat-sec 60 \
  --heartbeat-log benchmarks/results/ablation_expanded_candidate_full_system_2026-06-10/<heartbeat>.jsonl
```

Run order:

1. Targeted unit or contract tests.
2. Single-question focused eval-only.
3. Company focused eval-only when the failure involves dependency aggregation.
4. Full store-fixed eval-only only after the focused row is closed.

## Artifact Hygiene

- Keep `benchmarks/results/**`, local stores, heartbeat logs, temporary profiles,
  and cache files out of commits unless explicitly publishing experiment
  artifacts.
- Record the command, scope, result summary, and interpretation in docs instead
  of committing raw result bundles.
- A clean source commit should contain source, tests, docs, or reviewed config
  only.

## Required Documentation For A Numeric Fix

Every non-trivial numeric benchmark fix should leave these records:

| Document | What to record |
| --- | --- |
| `CONTEXT.md` | Latest short handoff state and next action |
| `docs/overview/project_status.md` | Current gate status and active PR/baseline |
| `docs/history/experiment_history.md` | Experiment narrative, commands, results, interpretation |
| PR body | Root cause, changed contract, validation commands |

Use this shape for the experiment entry:

```markdown
## <Short Experiment Name> (YYYY-MM-DD)

### Context
- What failed and why it mattered.

### Failure Layer
- Layer: <taxonomy item>.
- Root cause: <generic mechanism>.

### Code / Contract Change
- What changed.
- Why it is general rather than benchmark-specific.

### Results
- Focused rows.
- Broader replay if run.

### Validation
- Unit tests.
- Audit.
- Benchmark commands and numeric outcomes.

### Interpretation
- What claim is now supported.
- What remains out of scope.
```

## 2026-06-24 Case Pattern

The final 2026-06-24 closure used this method:

- `KBF_T2_018` had correct final answer text and evidence, but public
  `calculation_result` / `calculation_plan` projection remained stale. The fix
  synchronized final-answer surface operands back into the projected growth
  trace.
- `SKH_T1_060` had correct task-output operands, but direct evidence repair
  could overwrite one operand with a conflicting row from a different source
  context. The fix protected disjoint-source task outputs and made table-label
  metadata lookup prefer exact periodless row labels over subtotal rows.
- Focused eval-only closed both rows first, then the full six-company
  nine-question store-fixed eval-only replay returned `9 / 9` numeric PASS.

The important methodological point is that both fixes were expressed as generic
operand provenance, table-label, and projection contracts. No company names,
benchmark IDs, or metric-specific runtime branches were added.
