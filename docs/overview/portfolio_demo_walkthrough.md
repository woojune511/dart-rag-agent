# Portfolio Demo Walkthrough

This walkthrough shows the smallest reviewer-facing demo for the current
runtime contract. It is fixture-backed, so it can run without DART downloads,
vector-store setup, API keys, or benchmark result bundles.

## Run It

```powershell
.\.venv\Scripts\python.exe -m src.ops.portfolio_demo
```

For machine-readable review output:

```powershell
.\.venv\Scripts\python.exe -m src.ops.portfolio_demo --format json
```

The command reads
`tests/fixtures/portfolio_demo/demo_payload.json` and also runs the
repo-default report-cache reviewer handoff check. That means the output shows
the answer contract and the candidate-only cache gate together.

## Review Order

Use this demo as the first scan, then inspect the one-pager or experiment
report only if the reviewer wants the broader story. The current runtime
contract to look for is:

- canonical numeric state is exposed through `resolved_calculation_trace` and
  `structured_result`
- MAS handoff state is exposed through `task_artifact_trace`
- reflection retry state, when triggered, is persisted as a `reflection_report`
  artifact rather than an unbounded graph escape hatch
- critic acceptance is exposed as target refs, verdict/status, and reasons
- report-cache material remains candidate-only with retrieval bypass, writes,
  serving, and ledger insertion disabled
- promotion trace summaries are checked for materially distinct source,
  reflection-action, and cache-fallback surfaces before more summary evidence
  is added
- `REFERENCE_NOTE` traversal remains Researcher graph-expansion context and is
  not cache serving, retrieval bypass, ledger insertion, or final acceptance
  authority
- legacy top-level calculation/debug fields are compatibility bridges, not the
  source of truth for new live runs

## Expected Output

```text
# Portfolio Runtime Demo

Readiness: ready
Question: Which selected metric is supported by the available report evidence?
Answer: The selected metric is 123, grounded in the cited report section.

Citations:
  - [ACME | 2023 | section]

Calculation Trace:
  - operation: lookup
  - result: 123 (ok)
  - operands:
    - selected_metric: 123 from section

Task/Artifact Integrity:
  - status: ok
  - tasks: 2
  - artifacts: 4
  - issue_count: 0

Critic Acceptance:
  - status: accepted
  - target_task_id: task_1
  - target_artifact_ids: artifact:calculation_result
  - reason: Evidence, trace, and target refs are present.

Cache Reviewer Handoff:
  - status: ready
  - mode: candidate_only
  - retrieval_bypass_enabled: false
  - write_enabled: false
  - serving_enabled: false
  - ledger_insertion_enabled: false
```

## What A Reviewer Should Notice

| Output section | What it proves |
| --- | --- |
| `Readiness` | The compact demo contract passed its local checks |
| `Answer` | Final prose stays separate from the structured contract |
| `Citations` | The answer keeps source anchors visible to callers |
| `Calculation Trace` | Numeric output is backed by operands, plan, and result |
| `Task/Artifact Integrity` | The MAS ledger projection is present and clean |
| `reflection_report` artifacts | Retry/reflection actions are inspectable through the same ledger contract when a retry is prepared |
| `Critic Acceptance` | Runtime acceptance uses target refs, verdict, and reasons |
| `Cache Reviewer Handoff` | Cache candidates remain candidate-only with bypass/write/serving/ledger insertion disabled |

The important portfolio point is not the fixture value itself. The point is that
the command exposes the same surfaces that are risky in financial-document RAG:
source grounding, calculation provenance, agent handoff integrity, critic
acceptance, bounded retry/reflection handoff, and cache safety.

## Source Files

| File | Role |
| --- | --- |
| `src/ops/portfolio_demo.py` | CLI and compact readiness projection |
| `tests/fixtures/portfolio_demo/demo_payload.json` | Source-controlled demo payload |
| `tests/test_portfolio_demo.py` | Regression tests for the command and JSON output |
| `src/ops/review_report_cache_index_contract.py` | Candidate-only cache reviewer handoff |

## Optional Capture

For a portfolio README, resume appendix, or PR description, use the text output
as the short scan view and the JSON output as the audit view. The command is
designed to be copied into a terminal recording or screenshot without requiring
the full benchmark environment.
