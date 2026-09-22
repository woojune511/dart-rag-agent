# Shared-evidence comparison successor

2026-09-22. The user approved completing the seven remaining arms using the
existing USD5.67786757 balance. One fresh batch is capped at **USD5.67**; no new
funding, ingest, question-specific runtime changes or automatic paid retry.
The [original interrupted attempt](portfolio_workflow_comparison_result.md) remains
unchanged. This successor has a separate plan, output directory and cost receipt.

## Inputs and reuse

All four exposed development questions retain their original eight chunks,
source/packet hashes and Terra model/generation settings. The completed cash
baseline is reused by file hash with its original answer, usage and latency.
Its exact SDK request hash was reproduced locally with mocked HTTP and blocked
sockets. Reuse also checks the original plan, model settings, retrieval settings
and packet identity. Changed, duplicate or unfinished results cannot be reused.

New spend excludes reused calls. Comparison statistics include the original
measurements and explicitly label reuse; the first pair therefore spans two runs,
and its latency is not a simultaneous timing experiment. Quality criteria stay
outside generation inputs. This remains a joint representation/workflow comparison,
not an isolated Planner effect or production hybrid-retrieval evaluation.

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

The entire envelope fits the USD5.67 run cap and existing balance. This is a
reservation, not predicted spending or billing. Actual sampled Compiler bodies
remain unknown and can still exceed the bound; such a failure stops the batch.
Only Compiler requests may follow a fixed Planner request. Costs are checkpointed
separately before serializing rich results. Original failure accounting stays charged.

## Provider-free gate and reproducibility

Local root: `benchmarks/results/portfolio_workflow_comparison_2026-09-22/successor/`.
The initial `ready/plan.json` records reuse; `admitted/plan.json` additionally fixes
the first-request bodies and revised allocation. Plan SHA-256:
`e58d64605287975998911d54d22854347724b6f203356235b9f64d41862ccc27`.

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

After clean-source validation, the authorized one-time command is:

```powershell
.\.venv\Scripts\python.exe -B -X utf8 -m src.ops.compare_rag_workflows run `
  --plan benchmarks/results/portfolio_workflow_comparison_2026-09-22/successor/admitted/plan.json `
  --output benchmarks/results/portfolio_workflow_comparison_2026-09-22/successor/run `
  --max-cost-usd 5.67 --input-usd-per-million 2.5 --output-usd-per-million 12 `
  *> benchmarks/results/portfolio_workflow_comparison_2026-09-22/successor/progress.log
```

Separate source review must report correctness, source support, requested-output
completion and abstention behavior, alongside calls, tokens, latency and costs.
The known missing exact cash source remains a retrieval limitation. Exposed
development results must not be presented as unseen final-set accuracy.
