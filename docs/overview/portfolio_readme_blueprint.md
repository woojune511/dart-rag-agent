# Portfolio README Blueprint

This file is a rewrite plan for turning the repository README into a concise
portfolio-facing entry point. It should stay grounded in the current repo state:
runtime contracts, task/artifact handoff, critic gates, and candidate-only
report-cache review.

## Recommended README Structure

1. **One-line summary**
   - `Evidence-backed numeric QA over DART filings with multi-agent RAG, explicit calculation traces, critic acceptance gates, and reviewer-ready runtime contracts.`

2. **Problem**
   - DART filings are long, structured, and numerically fragile.
   - Common RAG failure modes: wrong row, wrong subtotal, wrong period, wrong
     entity/segment, missing provenance, and numeric equivalence drift.

3. **What I built**
   - section/table-aware retrieval over DART filings
   - deterministic numeric execution with structured calculation traces
   - MAS skeleton with Orchestrator, Analyst, Researcher, Critic, and final merge
   - task/artifact ledger and integrity projection
   - critic acceptance boundary and replan/blocking feedback
   - report-cache candidate review path that stays non-serving

4. **Architecture**
   - include a small text diagram:

```text
User question
  -> Orchestrator plan
      -> Analyst numeric artifacts
      -> Researcher narrative artifacts
      -> Critic reports
  -> Orchestrator merge
  -> Final answer + task_artifact_trace
```

5. **Key engineering decisions**
   - LLMs handle semantics; deterministic code handles execution.
   - Domain vocabulary belongs in ontology/policy/config, not runtime branches.
   - Numeric answers must carry source-visible display values and calculation
     traces.
   - Final close is blocked by integrity errors and rejected critic reports.
   - Cache candidates are observable, reviewable, and disabled for serving until
     a schema-backed producer policy exists.

6. **Validation and gates**
   - `python -m unittest discover -s tests`
   - `python -m src.ops.audit_runtime_domain_terms`
   - `python -m src.ops.review_report_cache_index_contract`
   - focused benchmark/eval-only gates documented under `docs/evaluation`

7. **Representative outputs**
   - final answer
   - citations/evidence refs
   - `resolved_calculation_trace`
   - `task_artifact_trace.integrity_status`
   - critic acceptance status/reasons
   - report-cache `reviewer_handoff.status`

8. **Repository guide**
   - `src/agent`: runtime graph, MAS nodes, task/artifact contracts
   - `src/config`: ontology, retrieval policy, report-cache classification
   - `src/ops`: evaluator, benchmark runner, smoke/review commands
   - `tests`: contract and regression tests
   - `docs/architecture`: design contracts
   - `docs/evaluation`: gate and benchmark notes
   - `docs/overview`: portfolio-facing summaries

9. **What is intentionally not enabled**
   - report-cache serving
   - retrieval bypass from cache
   - cache writes
   - cache candidate insertion into the live ledger
   - benchmark-specific runtime routing rules

10. **Reviewer path**
    - start with the portfolio demo walkthrough for a compact contract scan.
    - use the presentation outline for interview or project-review settings.

## README Opening Draft

```markdown
# DART Multi-Agent Financial Analysis Lab

Evidence-backed numeric QA over Korean DART filings with multi-agent RAG,
explicit calculation traces, critic acceptance gates, and reviewer-ready runtime
contracts.

This project explores how to make financial-document RAG auditable. Instead of
letting the LLM produce unsupported numeric prose, the runtime decomposes a
question into tasks, retrieves evidence, builds structured calculation artifacts,
checks critic acceptance, and only then merges a final answer.
```

## What To Emphasize

- failure modes and the contracts that catch them
- why structured traces matter more than prettier answer text
- how critic acceptance differs from offline evaluator scoring
- how cache work is staged safely as candidate-only reviewer infrastructure
- how tests and review commands protect against benchmark-specific patches

## What To Avoid

- a long tool list without explaining the runtime contract
- claiming cache serving is enabled
- presenting benchmark numbers without explaining failure modes
- implying the LLM is the source of arithmetic truth
- hiding partial/experimental status of future cache insertion and LLM critic work
