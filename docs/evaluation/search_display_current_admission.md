# Current-source search/display admission

Base `9698bd4a`; **no-call preparation** on 2026-09-18. One fresh application
attempt is prepared against current source, the unchanged search/display question
and the same four source-review criteria. The new manifest remains unconsumed.
No answer-quality result or paid completion is claimed.

The [local packet](../../benchmarks/results/search_display_current_admission_2026-09-18/)
contains the reviewed caller, runner, exact input, checks, official documentation
snapshots and a manifest bound to the final clean documentation commit. The old
`search_display_app_admission_2026-09-17` manifest remains consumed and immutable.
Runtime source, model settings, output limits and original stores are unchanged.

## Admission and budget

Shared accounting remains **USD 7.38602105 / 8**, remainder **0.61397895**,
pending **0**. The caller's only policy change lowers its cap from 0.91655740 to
that remainder. Limits stay 12 Responses, 12 counts, 48 embeddings and zero Google
calls; these are ceilings, not a promise that the whole workload fits. Routing
and Planner remain Terra/8192/low; Compiler remains Astra/5120/medium, all with
`store=false` and standard service tier. Context generation and fresh ingest are barred.

The [official pricing table](https://developers.openai.com/api/docs/pricing)
lists standard short-context input / cache-write / output per million tokens as
**10 / 12.5 / 50** for Astra and **2 / 2.5 / 12** for Terra; large embeddings are
**0.13**. The existing accounting envelope retains the higher input/cache-write
rate for every input and takes no cache discount. These are conservative estimates,
not a relabeling of base input prices or a repricing of prior receipts.
The [Astra](https://developers.openai.com/api/docs/models/gpt-6-astra) and
[Terra](https://developers.openai.com/api/docs/models/gpt-5.6-terra) pages place
long-context pricing above 272K input tokens; this caller rejects inputs above 200K.

The [token-counting guide](https://developers.openai.com/api/docs/guides/token-counting)
supports counting model-visible input and schema before generation. The exact
counted generation body is frozen for its single send. Endpoint price/free status
is not established, so **0.01 per attempted count** remains an experimental
contingency, including failed counts. Key presence is checked without exposing
the key; current account/model/count access is not tested.

| Accounting scenario, before input and embedding costs | USD |
| --- | ---: |
| Two full Terra outputs, one full Compiler output, three count contingencies | 0.482608 |
| Remaining headroom for that scenario | 0.13137095 |
| Same scenario plus one full Compiler repair and count | 0.748608 |

The last scenario exceeds the remainder by **0.13462905**. Actual sequential
usage may be lower, but complete live fit remains unknown. No output reduction,
model substitution or cap increase was made. Known denial blocks even counting;
the measured input and full output reservation must also fit before generation.
An authored boundary example admits 8,509 Compiler input tokens and rejects 8,510
after two fully used Terra calls with 5,000 inputs each and three contingencies;
it excludes embeddings and is not a server measurement.

## Verification and limits

- Caller/runner controls **23/23**, counted-request/budget contracts **30/30**,
  documentation checks **4/4** pass without skips or external connection attempts.
  Provider, count and embedding requests and added experiment cost are **0**.
- Actual app/lifespan, ASGI and normal retrieval use a verified disposable copy of
  the selected store with mocked embeddings, counts and model responses. Nine mock
  HTTP attempts include three count/generation pairs. Authored missing Compiler
  output gives HTTP 200 / **incomplete**; this proves transport plumbing, not semantics.
- Current SDK bodies are **3,720 / 64,156 / 48,405 bytes** for routing, Planner and
  Compiler. Count projections preserve every admitted model-visible input field
  and schema. These are exact rehearsal bodies, not known future model-generated
  prompts or measured tokens. The separate two-question stress fixture uses 500
  authored input tokens to exercise success under the smaller cap; its 100,000-token
  budget-negative case and all model/output limits remain intact.
- Existing controls preserve phase/question/scope authority, earlier diagnostics
  on failure, no retry or redirect, and denial of foreign endpoints, input drift,
  unscoped embeddings and historical answer/criteria reads during application execution.
  Runner changes only select a fresh output and derive the source count instead of
  reporting the stale literal 172. No production source or test changes were needed.
- All **173** sources, **2,050** predecessor artifacts, **24** store files and local
  settings retain hashes; main/API/run owners are separately verified. Prior full
  **2029/2029** and domain audit **83** remain unchanged-source evidence, not rerun.
  Experiment packets stay local and ignored.

## Next bounded step

Verify the unconsumed manifest and exact clean runtime identity, then execute the
single fresh `search_display_comparison` attempt under the **0.61397895** cap.
It uses normal routing, planning and retrieval without authored answers or criteria
injection. Review the four frozen source criteria separately from HTTP/ledger status,
then settle accounting and preserve raw evidence. The caller consumes the manifest
before dispatch and stops on provider, budget or app errors; no whole-query retry,
other question, ingest or cap increase follows. Current preparation sends no request.

The original paid search/display result remains **0/4**; exact offline replay is
separately **4/4**. Research and missing-cost questions remain live-unexecuted.
