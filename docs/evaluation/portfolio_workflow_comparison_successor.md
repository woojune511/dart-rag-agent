# Shared-evidence comparison: completed successor

2026-09-22, clean source `6bc4aae5`. **Four development pairs completed**: seven
new arms used **11 provider calls**, and one saved baseline answer was reused.
Provider errors, retries and unknown-usage calls: **0**. The original
[interrupted attempt](portfolio_workflow_comparison_result.md) and its conservative
loss accounting remain unchanged. This one-batch authorization is consumed.

These cases show no clear answer-quality advantage from the Planner/Compiler
workflow at its additional cost. Preserve its source/execution protections, freeze
additional per-error rules, and carry simple RAG as the leading candidate into the
separate final evaluation and demo. This is a development decision, not a change
to the production default or evidence of general superiority.

## Observed results

| Development case | Simple RAG | Planner + Compiler |
| --- | --- | --- |
| Year-end cash lookup | Supported rounded management amount; requested precise balance-sheet source not supplied | Qualified abstention; requested lookup not completed |
| Commerce growth | Correct calculation, requested one-decimal **41.4%** | Correct deterministic calculation; displayed **41.39%**, missing the one-decimal instruction |
| Acquisition impact | Supported purpose and consolidated revenue/loss; separate commerce attribution qualified | Supported purpose and consolidated revenue/loss with structured source evidence |
| Missing segment | Appropriate abstention, no invented amount | Appropriate abstention limited to retrieved evidence |

| Measurement across four answers | Simple RAG | Planner + Compiler |
| --- | ---: | ---: |
| Calls represented | 4 (3 new, 1 reused) | 8 new |
| Input tokens | 28,806 | 88,294 |
| Output tokens, including reasoning | 1,011 | 5,937 |
| Measured elapsed time, total | 17.33s | 82.96s |
| Measured elapsed time, mean per question | 4.33s | 20.74s |
| Estimated cost, USD | 0.084147 | 0.291979 |

The current workflow costs **3.47x** as much and takes **4.79x** the measured
elapsed time in this sample. Costs use the frozen conservative input/output rates
without cache discounts; they are not observed billing. The reused baseline's
original latency is included, so this is not a simultaneous timing experiment.

## Source review and limits

The separate `source_review.json` is an unblinded assistant review of original
answers against source text and explicit request conditions, not independent human
gold. Raw runtime quality fields remain `NOT_REVIEWED`/null; no original result is
rewritten into a semantic pass. Completion, source support and semantic correctness
are reviewed separately; an appropriate abstention can have runtime status
`incomplete` without being a quality failure.

- Cash: shared retrieval lacks the requested precise balance-sheet cell. Source
  `20240318000844:894:11` supports the baseline's rounded **3조 5,765억 원**;
  the answer does not qualify that substitution. The current workflow limits its
  non-answer to retrieved material. Its Planner still maps year-end to
  `year=2023, coverage=within_year`; abstention does not prove correct date meaning.
- Growth: `20240318000844:888:5` links 2023/2022 commerce values **2546.6/1801.1**
  in 십억원. Both use the correct change formula. Current execution yields
  **41.39137193937039** with valid source links and no source-display substitution.
  Planner preserves the one-decimal instruction, but the formula has no rounding
  step and the final answer uses two decimals. This is a display-intent gap, not
  incorrect arithmetic; no case-specific patch was added.
- Acquisition: `20240318000844:53:0` supports the global-commerce purpose and
  expected expansion; `20240318000844:518:410` supports post-acquisition consolidated
  revenue **473,849백만원** and net loss **19,063백만원**. Both answers stay supported
  within that scope. The current public citation list also includes retrieved
  anchors beyond the supporting claims; citation presence is not claim-level proof.
- Missing segment: both decline the unsupported shipbuilding backlog amount.
  Sources `20240318000844:27:0` and `20240318000844:19:0` describe service categories.
  Neither answer invents zero or borrows an unrelated amount. The current answer
  explicitly distinguishes missing retrieved evidence from document-wide absence.

The four questions were already exposed during development, concern one selected
filing, and have one sample per arm. There is no holdout accuracy, statistical
winner or isolated causal explanation. The cash retrieval gap remains visible;
gold evidence was not inserted to make either workflow succeed.

## Accounting

New estimated spend is **USD0.359777**. The represented answer costs above also
include **USD0.016349** already charged for the reused baseline; it is not charged
again. Shared conservative accounting is now **USD21.00190943 / USD26.32**, with
**USD5.31809057 remaining** and **0 pending**. The original lost-record ceiling
charges remain in that balance. No new funding was added for this successor.

## Inputs and reuse

All four exposed development questions retain their original eight chunks,
source/packet hashes and `gpt-5.6-terra` model/generation settings: low reasoning,
8,192 output tokens, default service tier, Responses strict schema, `store=false`,
no SDK retries. The completed cash
baseline is reused by file hash with its original answer, usage and latency.
Its exact SDK request hash was reproduced locally with mocked HTTP and blocked
sockets. Reuse also checks the original plan, model settings, retrieval settings
and packet identity. Changed, duplicate or unfinished results cannot be reused.

New spend excludes reused calls. Comparison statistics include the original
measurements and explicitly label reuse; the first pair therefore spans two runs.
Quality criteria stay outside generation inputs. Shared frozen BM25 retrieval
selects NAVER2023 filing `20240318000844` (1,090 of the source graph's 1,872 chunks
across two filings). Baseline sees retrieved source text; the current workflow
also receives typed axes, cells and attached context from those chunks. This is a
joint representation/workflow comparison, not an isolated Planner effect.
No live hybrid retrieval, embeddings, ingest or graph expansion were tested.
The production application's separate Astra Compiler route was not evaluated.

## Full-batch reservation

The original uniform 80,000 byte-based token reservation rejected an authored
calculation fixture even after its input periods were specified: its SDK body
was 87,800 bytes. This is an admission-size finding, not a sampled model failure.
No prompt or evidence was shortened to fit it.

Seven first requests can be serialized exactly before generation: three baselines
and four Planners. Their body hashes are frozen; a different hash or excess size
stops before dispatch. Body bytes plus 256 overhead total **298,159**. After each
Planner, up to three Compiler requests may use **100,000** input tokens of
conservative byte-based reservation each. The response-call limits remain one per
baseline and four per compiled arm: **19 new calls maximum**, 8,192 output tokens
per call, no SDK retries, same rates USD2.50 input / USD12 output per million.

`((298159 + 12 * 100000) * 2.50 + 19 * 8192 * 12) / 1000000 = USD5.6131735`.

The entire envelope fit the **USD5.67** run cap and pre-run **USD5.67786757**
balance. This was a reservation, not predicted spending or billing. Live Compiler
bodies were 34,381-58,132 bytes and all four arms used one Planner and one Compiler
call. Only Compiler requests may follow a fixed Planner request. Costs are
checkpointed separately before rich-result serialization; no budget block occurred.

## Provider-free gate and reproducibility

Local root: `benchmarks/results/portfolio_workflow_comparison_2026-09-22/successor/`.
The initial `ready/plan.json` records reuse; `admitted/plan.json` additionally fixes
the first-request bodies and revised allocation. Canonical JSON plan fingerprint:
`e58d64605287975998911d54d22854347724b6f203356235b9f64d41862ccc27`.
Serialized plan file SHA-256:
`4f8fb0cc2d22ec5945a1cc97a767a8d544408b3b33c3f91a8f785fd4b00f89c4`.

`run/results.json` contains all eight answers and measured usage. Independent
`run/budget.json` and per-arm checkpoints retain new-call accounting.
`accounting_receipt.json` records completion, the shared balance and original
result hashes; `source_review.json` adds review without editing those results.
Original failure files and all successor raw-result hashes were verified unchanged.

`rehearsal_admitted_report.json` records blocked sockets, mocked HTTP and authored
responses. It replays the saved baseline request exactly and exercises all seven
new arms through real SDK serialization, admission, graph execution and final
JSON persistence. Four pairs persist; 12 mock dispatches include the extra baseline
identity check. These are execution witnesses, **zero paid calls and no model-quality
evidence**. Planner witnesses and missing-output Compiler witnesses are authored;
they do not establish that the model will choose those plans or correct answers.

The full-batch cost bound is enforced independently of fixture sizes. Regression
tests cover reuse without double charging, changed inputs/models/artifacts,
first-request identity/size, phase/call limits and result persistence.
Pre-run validation: **2,271/2,271** tests (72.440s), including **16** comparison
contracts. Product runtime, prompts, policies and source stores are unchanged.
Post-run documentation gates **2/2**, local-link/diff checks and artifact/source
hash verification pass; the full suite was not repeated for documentation edits.

The following one-time command completed. It records the consumed run, not a new
authorization to rerun it:

```powershell
.\.venv\Scripts\python.exe -B -X utf8 -m src.ops.compare_rag_workflows run `
  --plan benchmarks/results/portfolio_workflow_comparison_2026-09-22/successor/admitted/plan.json `
  --output benchmarks/results/portfolio_workflow_comparison_2026-09-22/successor/run `
  --max-cost-usd 5.67 --input-usd-per-million 2.5 --output-usd-per-million 12 `
  *> benchmarks/results/portfolio_workflow_comparison_2026-09-22/successor/progress.log
```

## Next milestone

Freeze further Planner/Compiler complexity for this portfolio milestone. Retain
the current workflow as the inspectable calculation/source-validation comparison
and take simple RAG forward as a candidate, without changing product defaults from
four familiar cases. Select a genuinely separate final set and a reproducible demo
that includes successful retrieval/calculation, abstention and an observed failure.
Any final provider evaluation needs its own frozen scope and cost bound; this run
does not authorize another batch. Report its result once, including negative
findings, instead of using the final set to restart per-question repairs.
