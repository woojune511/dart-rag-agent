# General correctness audit

Date: 2026-09-09. Baseline: clean `327002c0`.
Scope: `FinancialAgent` and its routing, retrieval, parser, compiler/executor,
state/ledger, ingest/storage and API boundaries. No paid experiment was run.

## Is the system fitting the benchmark?

It would be unjustified to say that all prior changes were independent of the
reviewed questions. The audit found absolute-year preferences/penalties, dated
stopword lists, company/segment-specific routing examples, and a separate
metric-policy narrative assembly path. These are concrete generalization risks;
a vocabulary audit alone does not detect them when they live in policy data.

The audited default runtime now sends every intent through existing required-output
planning and source-bundle compilation. Meaning stays with the model; code checks
source/owner authority, arithmetic, exact evidence and completeness relative to
the declared requirements. Fixed-year selection rules were removed. Router examples
now describe anonymous operations with one example per intent, avoiding contradictory
metric-specific exceptions to the intent definitions.

This does **not** prove unseen-question accuracy. The planner can still omit a
requested topic, and structural binding validation is not a semantic faithfulness
judge. Canonical classifier examples and reviewed ontology/policy remain priors;
their quality must be measured on an independently selected holdout.

## Reproduced defects and repairs

| Boundary | Defect | Generic repair / regression |
| --- | --- | --- |
| Planning/answer coverage | Pure narrative skipped obligations and compiled evidence | Same planner/compiler for every intent and format; two synthetic themes test complete and partial output, no legacy summarizer call |
| Ledger | Aggregate marked complete despite partial public result | Derive artifact/task status from finalized structured result; keep public payload byte-equivalent |
| Dependency authority | Formula consumed an undeclared obligation output | Require owner's `depends_on`, including shared islands; declared dependencies remain executable |
| Retry assertions | Foreign retry assertions invalidated accepted output; shared assertions retained replaced inputs | Project target-selected assertions, retain untouched members/quotes, attribute errors to declaring owners |
| Formula AST | Boolean accepted as number, huge integer crashed validation, scalar min/max failed at execution, function names hid variables | Validate finite numeric literals and scalar arity; distinguish AST call positions from variable positions |
| Source scope | Failed dense search retried unfiltered; supplements/seeds restored out-of-scope sources | One source filter through search, local scans and final selection; explicit company cannot be widened by planner companies |
| BM25 | Global cutoff occurred before scope filtering | Filter eligible indices before ranked cutoff; distractor volume cannot starve allowed filing |
| Narrative retrieval | Local chunk IDs merged different reports; narrative requirements were registered as numeric | Use qualified source identity or abstain from dedupe; requirements inherit parent kind |
| Selection capacity | Preferred document-type quota left unused slots despite available sources | Preserve quotas/order, fill spare capacity from authorized ranked sources, suppress known duplicates |
| Parser | Splitting numbered table explanations lost the introductory source text | Include the original start boundary; synthetic coverage tests, no stored document rewrite |
| Source preservation | XML recovery dropped ampersand text; non-scalar rows disappeared and narrative modes had different table access | Literal-safe XML recovery; retain explicit header/body tables and scalar-independent row readings; equal narrative row/prose eligibility without changing original chunk numeric extraction |
| Date/prompt priors | Only named years were prioritized or filtered; router few-shots contradicted generic intent rules | Remove absolute-year ranks; use existing year grammar; anonymous operation-based config examples |
| Routing vectors | Truncated/non-finite/empty batches were cached; extreme finite cosine overflowed | Validate complete successful batches and identity; stable cosine scaling, invalid query vectors explicitly degrade |
| Search cache | Caller-mutated Documents polluted later reads; committed writes left stale results | Deep-copy cached documents/provenance; invalidate only after successful graph publication |
| Persistence/admission | Explicit backend writes and terminal provider errors were swallowed | Propagate lower write failures and admission stops; no fallback/provider retry after a terminal stop |
| API errors | Raw provider text could reveal request URLs/credentials | Generic public errors and safe error-type/status projection; preserve endpoint status contracts |

New tests use synthetic names, shifted years, scope permutations, unrelated high-score
documents, identical local IDs, partial coverage, mutation and injected lower-level
failures. They do not assert new reviewed-company answers. One old generic CAGR test
now explicitly declares its intended two dependencies; formula/expected values remain.
The audit baseline deletes one obsolete inline prompt record and adds no exception.

## Validation and untouched evidence

- Baseline Python 3.13.13 full unittest: **1173/1173**.
- Final full unittest: **1236/1236**, 33.361s; **63 new synthetic regressions**.
- Source-preservation successor: **1251/1251**, 40.630s; **15 additional anonymous
  regressions**. Frozen chunk-to-catalog replay preserves 44,757 numeric IDs/contents.
- Focused cross-boundary/import/topology/documentation gate: **62/62**, 13.714s.
- Domain-language audit: **83 reviewed literals**, no newly accepted runtime terms.
- Focused tests cover each repaired boundary; import/topology, changed/new Python
  pycompile and diff hygiene pass, not used as model-accuracy claims.
- No paid API request, fresh ingest, original-store mutation, dataset/evaluator edit,
  automatic benchmark retry, or historical-result rewrite.
- Public HTTP/result shape, candidate-ID/hash algorithms and store manifest format
  remain. Future parser fragment boundaries may change; old parser outputs stay frozen.

The last four-question paid artifact belongs to its old build, not this source.
Its omissions remain omissions. Routing/planning/provider request shapes changed;
any new run requires a new manifest, explicit transmission scope and cost approval.

Reproduction commands use `.venv/Scripts/python.exe -X utf8`:

```text
-m src.ops.audit_runtime_domain_terms
-m unittest tests.test_uniform_requirement_contract tests.test_aggregate_answer_status tests.test_retrieval_scope_isolation tests.test_parser_fragment_coverage tests.test_query_router_embedding_authority tests.test_import_side_effects tests.test_runtime_topology_doc tests.test_documentation_authority -q
-m unittest discover -s tests -q
```

New focused files also include `test_semantic_compiler_authority_audit.py`,
`test_storage_failure_boundaries.py`, `test_ingest_admission_boundaries.py`, and
`test_api_error_boundary.py`. No existing benchmark fixture was relabelled.

## Current narrative selection diagnosis — repair pending

On 2026-09-11, the [provider-free source/rank diagnosis](../../benchmarks/results/narrative_evidence_coverage_diagnosis_2026-09-10/README.md)
located the omitted source passages in all three frozen narrative catalogs. Recomputed
selection IDs match the completed paid run's output and requirement visibility.
Two business-overview prose candidates are outranked by detail rows; a channel table's
local title exists in its row rendering but is absent from the matching fact view.

`project_candidate_fact` applies numeric metric isolation to narrative structured reading;
`build_candidate_matches` also keeps cell-locality priority for narrative owners.
Shared-heading word matches elevate detail rows, while unknown-only ties fall back to
source-key order. Eligibility/source diversity therefore does not imply theme coverage.
Five anonymous, socket-blocked characterizations reproduce these mechanisms and preserve
explicit-company conflict rejection. They are ignored diagnostic artifacts, not regression
tests that require known defects forever. Runtime and original inputs remain unchanged.

Next bounded repair: owner-aware narrative reading projection and hierarchy-aware source
selection, preserving numeric metric isolation, scope/subject/ID authority and budgets.
Do not add reviewed business keywords, promote gold IDs, declare prose universally better,
or rerun the model before fixing input coverage. This is compiler-only whole-catalog
diagnosis, not full-agent retrieval measurement, a completed fix, or new answer accuracy.

## Review limits and next bounded work

1. Freeze the generic mechanism fixes, then select holdout documents, periods and
   question structures independently of the failed examples. Separate retrieval
   coverage, runtime correctness and semantic completeness; do not tune answer keys.
   The subsequent [offline source diagnosis](../evaluation/independent_holdout_protocol.md)
   reproduced XML text loss and table reading-evidence gaps, now repaired under a
   successor freeze. Source-exposed cases are regressions for those repairs, not an
   untouched parser/catalog holdout; no new agent score is claimed.
2. Retained legacy narrative helpers/graph compatibility branch are no longer selected
   by the public planner. Their physical removal needs a caller/deletion inventory;
   this audit does not claim the entire legacy module was removed.
3. DART acquisition still uses first-page/partial-name lookup. Pagination and ambiguous
   corporate identity need acquisition-contract tests before changing selection policy.
4. Source integrity checks are not a full vector-to-source text/provenance bijection.
   Extend only with characterization of supported BM25-only stores and recovery.
5. Public FastAPI errors are redacted; experimental/lower-level logs need a separate
   logging boundary review. Formula-wide rounding propagation and default-store
   recovery remain deferred; the current actual stores were not repaired.

Review covered the owned runtime packages and their consumers, not every possible
execution path. Passing tests and structural source inspection do not establish a
bug-free system, current release acceptance, or an unbiased dataset.
