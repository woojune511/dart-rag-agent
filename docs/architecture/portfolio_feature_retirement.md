# Portfolio feature retirement

2026-09-22. Architecture cleanup from `d9f323f9`, authorized by the user's
instruction to remove features aggressively. The completed
[development comparison](../evaluation/portfolio_workflow_comparison_successor.md)
does not justify maintaining every surrounding capability. This change removes
features and their callers rather than adding another runtime or disabled flags.

## Removed

- The separate question classifier, canonical routing examples/embedding cache,
  classification LLM fallback and calibration/confusion tools. Every query now
  starts at `plan_requirements`; the graph has seven nodes instead of eight.
- MAS orchestration, analyst/researcher/critic workers, their alternative graphs,
  facade, smoke/probe tools and dedicated tests.
- Report-result cache classification, lookup, trace candidates, promotion,
  rehydration and reviewer tools. The benchmark cache-index CLI option and demo
  cache-review options are removed with the features.
- Unused reflection projection/promotion and reflection-ledger helpers, the old
  paper-specific RAG chain, and an uncalled ratio-answer repair with its helpers.
- Reviewer gates for retired capabilities. The remaining reviewer command checks
  its explicitly historical fixture, without claiming current model acceptance.

Files remain recoverable from Git. Historical result and fixture data are retained;
historical commands must use their recorded source revision. The runtime contains
no alternate copy or compatibility dispatch that restores these removed features.
In total, 63 source/configuration/test files are deleted. Across `src/`, including
operational tools and configuration, 53 lines are added and 10,908 removed: a net
reduction of **10,855 lines**, not a count of lines executed by the product.

## Remaining behavior and compatibility

The product still runs **Planner -> retrieval -> Compiler -> deterministic
execution -> answer -> ledger**. This is not a replacement with one-call RAG.
Source selection, request ownership/coverage, periods/units, source linkage,
calculation and public evidence validation remain. Ingest, parser, vector/store
identity, ordinary search caching and graph source data are unchanged.

Initial filing hints now use only explicit caller `report_scope`; the old regex
no longer turns years appearing in a question into filing filters before planning.
The exact original query reaches the Planner, which retains semantic ownership.
The API response shape remains, but `query_type` is the neutral `qa` label for all
queries. Unspecified retrieval format defaults to mixed evidence rather than an
intent-to-format policy. It no longer advertises a separately predicted intent. LLM provider/model
routes remain configuration; they are distinct from the removed question router.

Removing the classifier avoids its embedding/classification dispatch in the
ordinary application. The preceding fixed-evidence comparison already bypassed
that classifier and the deleted experiments. Its 3.47x cost / 4.79x time result
therefore remains unchanged historical evidence, not a measured saving from this
cleanup. No fresh provider, quality, latency or price comparison was run.

## Validation

The source/execution contracts remain the verification boundary. Focused graph,
retrieval, application-profile, Planner, public/demo and benchmark contracts pass
81 tests; a further 64 retrieval/source-scope/interruption checks pass. The full
remaining provider-free suite passes **2,109/2,109 tests in 73.338 seconds**.
New controls check that construction never touches routing embeddings,
the graph starts at the Planner, and query years cannot silently become filing
scope. Runtime domain audit passes with 35 reviewed literals; 31 entries belonging
to deleted implementations were removed, with no new runtime vocabulary.

Validation logs and an immutable-input hash manifest are local under
`benchmarks/results/portfolio_feature_retirement_2026-09-22/`. The protected set
contains 110 hash-identical files, including the selected store, local settings
and the preceding comparison outputs.
No experiment artifacts are staged. Shared conservative accounting remains
USD21.00190943/26.32, remaining5.31809057, pending0; added provider cost is zero.
