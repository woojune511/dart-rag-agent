# Shared-evidence portfolio workflow comparison

Prepared 2026-09-22. **Provider evaluation: NOT_RUN.** This is the next bounded
development comparison under [portfolio scope](../overview/portfolio_scope.md),
not another question-specific runtime repair. Product prompts, policies, parser,
retrieval and Compiler behavior are unchanged by the comparison runner.

## Question and controls

Does the existing structured-evidence workflow produce sufficiently better
answers or failure explanations to justify its extra calls, latency and cost
over a simple retrieve-context-answer baseline?

Both arms receive the same question, filing filter, retrieved chunk identities,
and model settings. Shared frozen BM25 retrieval runs before either arm. It reads
existing sidecars without opening Chroma, embedding, ingesting, expanding a graph,
or asking the Planner for search queries. Whole documents are admitted in order:
at most eight chunks and 65,536 UTF-8 bytes of rendered source text/context.
Documents that exceed the remaining budget are recorded rather than truncated.

| Arm | Input representation and processing |
| --- | --- |
| `simple_rag` | Retrieved text and source context; one structured answer call with source IDs and an abstention flag |
| `planned_compiled` | Same chunks plus their stored typed table metadata; existing Planner, candidates, Compiler, source validation, arithmetic, answer and ledger |

This measures **representation and workflow together**. Stored table metadata
can expose complete axes, attached context and cells beyond the chunk's rendered
text. It is not identical information serialization, an isolated Planner ablation,
or an end-to-end test of production hybrid retrieval. The shared routing input is
`qa`/`mixed`; source inventories are limited to the selected metadata. A citation
ID being valid does not establish that the cited text supports an answer.

All calls use the prepared default OpenAI route: `gpt-5.6-terra`, reasoning `low`,
8,192 maximum output tokens, Responses structured output, `store=false`, default
service tier and zero SDK retries. The production Compiler's separate Astra
route is deliberately not used. Thus results will not be production acceptance.
Arm order alternates by case. No model snapshot beyond the published model ID
is claimed. LangSmith tracing is disabled within the run.

## Development data and source coverage

[Dataset](../../benchmarks/datasets/portfolio_workflow_dev.json): four already
exposed topics. They cannot become an untouched final holdout. `review_criteria`
stay outside both arms' packets and prompts; the runner never grades by matching
an expected keyword or feeds review outcomes back into the system.

| Case | Requested behavior | Pre-run source observation |
| --- | --- | --- |
| `lookup_cash` | Year-end consolidated cash, original units | Management text `20240318000844:894:11` supplies a rounded amount; the precise known balance-sheet amount is absent from the selected text/metadata. Record this retrieval limitation separately from model interpretation. |
| `calculate_commerce_growth` | Calculate a comparable year-on-year growth rate | `20240318000844:888:5` contains commerce 2,546.6 / 1,801.1 and a separately reported 41.4%; check year/unit mapping and actual requested calculation. |
| `explain_acquisition_impact` | Explain acquisition effects with source support | `20240318000844:53:0` has acquisition purpose/expected effects; `20240318000844:518:410` has post-acquisition consolidated revenue/loss. Do not infer that all commerce growth came from this acquisition. |
| `abstain_missing_segment` | Acknowledge insufficient support | No selected support for the requested shipbuilding backlog; absence does not imply zero or prove document-wide absence. |

This is a manual development coverage note, not an automated semantic oracle.
Evaluate source-faithful rounded answers in their actual source context; do not
invent precision from the known full-corpus reference. Missing exact requested
support may justify qualification or abstention. Report task correctness, source
support, requested-output completeness and abstention behavior separately.
Where the shared retrieval lacks evidence, do not attribute every failure to the
Planner or use it to claim that more downstream complexity would solve retrieval.

Read-only snapshot: `data/app_nav_2023_20260916`. The graph contains 1,872 indexed
chunks across two filings. All selected chunks use NAVER's 2023 annual filing,
receipt `20240318000844` (1,090 chunks in that filing). Filing identity is not a
measurement-period assumption. The plan hashes `store_manifest.json`,
`document_structure_graph.json`, `table_payloads.json`, the dataset and each input
packet. Source and packet changes are rejected before a run and sources are
checked again afterwards. Existing source and historical result files stay intact.

Prepared local plan:
`benchmarks/results/portfolio_workflow_comparison_2026-09-22/ready/plan.json`.
All cases have eight chunks; rendered inputs are 15,507 / 24,300 / 33,298 / 28,800
UTF-8 bytes. These are local serialization sizes, not measured model tokens.
No final evaluation set or final quality score has been produced.

## Cost and terminal behavior

Each baseline allows one request; each compiled arm allows at most four total
requests, including any existing targeted retry. The complete batch allows at
most 20 requests. Each SDK body plus 256 bytes of overhead must fit a conservative
80,000-token input reservation; larger bodies stop before dispatch. This is an
admission bound, not a token prediction. A dynamic Compiler request has not yet
been sampled; future size or schema admission can still terminate the run.

The [OpenAI pricing page](https://developers.openai.com/api/docs/pricing), checked
2026-09-22, lists standard short-context Terra input/output at USD2/12 per million
tokens, and cache writes at USD2.50. Reserve input at **2.50** without cache
discounts and output at **12**. The full conservative envelope is:

`20 * (80000 * 2.50 + 8192 * 12) / 1000000 = USD5.96608`.

A proposed **USD6 run cap** covers this envelope; it is neither expected spending
nor an invoice. Current recorded funding is USD20.02917543 used of USD20.32,
remaining **USD0.29082457**, pending zero. **No funding increase is recorded and
this plan is not authorization to spend USD6.** Underfunding fails before client
creation or output-directory creation. Any new funding must be recorded before
the paid command below is used.

Provider/admission errors stop the remaining batch, even when product code catches
the exception and returns an incomplete answer. Previously finished answers are
retained; remaining arms are `NOT_RUN`. Failed/unaccounted requests retain their
conservative reservation. There is no automatic rerun/resume; an output directory
cannot be overwritten. The CLI does not itself prevent a person from initiating
a separate run with another output path, so a fresh paid attempt needs its own
recorded budget. Network outages, resource limits and incomplete pairs are not
automatically incorrect answers or completed A/B evidence.

## Reproduction and review

Preparation is provider-free (use a new output directory):

```powershell
.\.venv\Scripts\python.exe -B -X utf8 -m src.ops.compare_rag_workflows prepare `
  --dataset benchmarks/datasets/portfolio_workflow_dev.json `
  --store data/app_nav_2023_20260916 `
  --output benchmarks/results/my_workflow_comparison/prepared
```

Only after funding the batch, using the reviewed source revision:

```powershell
.\.venv\Scripts\python.exe -B -X utf8 -m src.ops.compare_rag_workflows run `
  --plan benchmarks/results/my_workflow_comparison/prepared/plan.json `
  --output benchmarks/results/my_workflow_comparison/run `
  --max-cost-usd 6 --input-usd-per-million 2.5 --output-usd-per-million 12 `
  *> benchmarks/results/my_workflow_comparison/progress.log
```

Each SDK request and arm completion emits progress; the configured request timeout
is 90 seconds with no SDK retries. Each completed/interrupted arm is persisted
immediately. Inspect progress and partial files if the final receipt is delayed.
`results.json` includes
paired completion, per-arm calls, observed tokens, unknown-usage counts, elapsed
time, conservative costs and original answer/review/debug records. Runtime
`completed` means the arm returned; it does not mean an answer was correct.
Quality fields remain null and review status `NOT_REVIEWED` until a separate
source-based review. Include retrieval limitations and partial pairs in the report.
Experiment output directories are ignored and must not be committed.

Provider-free contracts cover nonempty shared retrieval, gold isolation, whole
document budgets, source/packet changes, successful and failed graph adapters,
real SDK serialization with mocked HTTP and blocked sockets, funding admission,
input isolation, caught provider failures and partial-result retention. Authored
test replies establish execution behavior, not sampled model quality.

Validation: **2,266/2,266** tests (73.490s), including 11 comparison contracts;
runtime domain audit **66** reviewed literals. Prepared source/packet hashes pass.

After this development comparison, choose at most one justified general change.
Then freeze separate final questions, run once, and publish the demo/report with
limitations. A weak comparison result must not restart per-question repair.
