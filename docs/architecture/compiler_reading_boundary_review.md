# Compiler reading boundary review

Status: compiler presentation repair implemented; one paid comparison shows partial improvement, not semantic completeness.
2026-09-11; reviewed clean `08ee8a35`, unchanged runtime `ef065b7b...f957a`.
Authority: [runtime contract](agent_runtime_contract.md).

## Conclusion

The latest failures do not establish missing heading text or a validator that
forbids reading headings. The source context and failed retry drafts arrive.
The compiler interface instead mixes a source-reading task with bookkeeping,
ranking factors, numeric instructions and underspecified authored requirements.
Some defects are directly reproducible; their effect on model interpretation is
not causally measured. Another instruction-only paid rerun is not the next step.

The initial review changed no runtime. Its subsequent presentation repair is recorded
below; models/program schema, IDs, stores, datasets, frozen responses and review criteria remain unchanged. The initial review/repair made no provider call; the separately approved comparison is recorded at the end.

## Findings at the reviewed baseline

| Finding | Evidence | Classification |
| --- | --- | --- |
| Ranking values leak into compiler input | `_semantic_program_prompt_cohort` removes `ranking_diagnostics`, but `_semantic_program_prompt_rows` copies all `match_by_owner` fields, including `rank_vector`. Twenty visible candidates produce **40** rank-vector occurrences across seven initial payloads. | Confirmed prompt-projection/contract mismatch. Runtime contract section 6 excludes ranking diagnostics from compiler input. Not evidence that the model used the vector. |
| The reader must reassemble document structure | Context dictionaries, bundle order and bundle context links sort by hashed IDs. Candidate → bundle → context links preserve attachment but require joins; order is deterministic, not document reading order. Company metadata remains repeated in candidate fields/anchors beside source interpretation fields. | Confirmed representation shape; cognitive burden and issuer anchoring are hypotheses. Context is present, not erased. |
| General compiler material dominates tiny narrative inputs | Every visible narrative row has **43–44 fields**, **21–23 empty**. The common template is **18,308 UTF-8 bytes** and carries arithmetic/display/scalar rules even for narrative-only calls. Full program JSON schema is **8,799 bytes** before SDK transformation. | Confirmed interface overhead, not measured attention failure, tokens or latency. Unknown fields and required provenance cannot all be deleted as waste. |
| Row-description capability is unclear to the reader | The DART first response supplies four `row_description_quote` values for `kind=narrative` rows with empty `row_label`/`row_headers`. They fail the required exact-axis check; retry removes the optional field and ordinary narrative quotes pass. | Prompt/schema capability presentation gap. The exact-axis validator is behaving as specified; relaxing it is not the repair. |
| Requested distinctions are not explicit in the authored owner | Each diagnostic input uses one short owner and one identically labelled evidence requirement: `공급 경로` for six anonymous inputs, `판매경로` for the DART excerpt. Query-specific attribution, domestic/overseas distinctions or requested limits survive only in the full question, marked `context_only` for owner isolation. | Confirmed fixture/requirement specificity limit, **not observed planner failure**: these compiler-only runs bypass the actual planner. Current labels/requirements can express richer requests; a new role enum is unnecessary. |
| Structural completion is not semantic completion | An anonymous heading-plus-body claim passes. Wrong quote container, issuer-only subject and foreign owner fail. Negation, switching the entity inside claim text, and omitting query details can still pass. | Existing, explicitly documented semantic boundary. Source/ID checks are necessary but are not entailment or coverage judging. |

Relevant owners:

- [`financial_graph_calculation.py`](../../src/agent/financial_graph_calculation.py):
  `_semantic_program_prompt_cohort`, `_semantic_program_prompt_rows`,
  `_semantic_program_prompt_payload`, and per-attempt `compilation_scope`.
- [`financial_source_bundles.py`](../../src/agent/financial_source_bundles.py):
  deterministic identity and sorted context links; not a semantic entity resolver.
- [`financial_graph_models.py`](../../src/agent/financial_graph_models.py):
  `AnswerObligation`, `EvidenceRequirement`, narrative claim/binding schema.
- [`retrieval_policy.py`](../../src/config/retrieval_policy.py):
  common compiler template and row-description/metadata/requested-coverage guidance.
- [`financial_narrative_claims.py`](../../src/agent/financial_narrative_claims.py)
  and [`financial_calculation_execution.py`](../../src/agent/financial_calculation_execution.py):
  exact quote-container, subject occurrence, owner and row-axis validation.

## Measured input shape

The seven initial candidate payloads total **93,265 bytes**. Their `source_text`
fields in bundle/context objects contain **3,877 literal UTF-8 bytes** (4.16%).
The rest includes JSON framing, IDs, scope, provenance and matching information;
it is **not** all removable overhead. These source fields can overlap in content,
and other fields also contain source-derived snippets. This is not a unique-text
compression ratio or a tokenizer measurement. `match_by_owner` objects alone
account for 16,186 bytes, excluding their containing key names/framing.

| Input | Candidate payload | Bundle/context literal source bytes | Prompt text bytes, excluding SDK schema |
| --- | ---: | ---: | ---: |
| First anonymous case | 8,734 | 273 | 28,145 |
| Two-peer-heading case | 16,014 | 548 | 35,425 |
| DART excerpt | 34,216 | 1,888 | 53,591 |

These examples are diagnostic observations, never runtime selection conditions.
The stored SDK request hashes match the original admission/rehearsal boundary.

## Implemented seam and remaining boundary

The repair changes only the **compiler presentation projection**, keeping the catalog,
selection/visibility, program schema, validator, executor and provider-call count:

1. Explicit allowlists cover prompt match/cohort fields. Keep necessary applicability
   states, but remove rank vectors/diagnostic scores from model input; keep them in
   trace. A recursive prompt check must catch leaks through either cohorts or rows.
2. v7 presents a source-local reading unit: exact located enclosing headings, local
   paragraph/table body and their existing quote targets next to each other.
   Use actual document identity/location/attachment, never company-name equality or
   title wording, to arrange them. Keep document metadata in a clearly separate
   provenance area. Do not infer a pronoun's identity or overwrite an explicit body subject.
3. Empty fields and numeric-only template/retry explanatory clauses stay out of a
   narrative-only reading view. Mixed/numeric obligations retain their needed
   fields and rules. This is a prompt projection, not a second answering route.
4. Ordinary narrative row quotes are distinct from the special permission to read
   a numeric cell's row description without using its scalar. Show the latter
   only with its actual axis/provenance prerequisites; do not weaken checks or
   introduce a semantic candidate-role classifier.

Do not simultaneously rewrite the seven old diagnostic requirements. Keep them
frozen to isolate presentation effects. In a separate provider-free contract
exercise, use existing `label`/`evidence_requirements` to preserve query-written
identity, relationship and limitations. Verify planner → compiler copying with
authored planner outputs before alleging a production planner omission. Missing
detail must not be repaired by matching question-specific runtime keywords.

### Local acceptance before any new provider admission

- Candidate IDs, catalog contents/fingerprints, owner selectable sets and physical
  provenance are unchanged. Source text and quote targets remain exact; presentation
  cannot create contiguous quotes across different fragments.
- No ranking vector is recursively present in any compiler payload. Ranking and
  debug traces remain available without becoming evidence authority.
- Source ordering is deterministic under input reordering, but follows located
  hierarchy within a source; peer headings/foreign filings remain separate.
- Empty-field removal does not convert `unknown` into a positive match. Numeric and
  mixed calls keep unit/period/coupling/source-display contracts.
- Correct heading+body quotes still validate; wrong container/owner/hidden ID and
  metadata-only subject still fail. Unsupported semantic controls remain explicitly
  unproven, not relabelled as correct because structural validation passes.
- Retry retains the same authorization and unrelated accepted bytes. It may repair,
  remove or abstain; no fixed claim-count or candidate-ID oracle.
- Focused tests first; then domain audit/import/topology/pycompile/diff. Full unittest
  at the compiler projection integration boundary. Only after a meaningful mechanism
  change and these gates should a fresh manifest, rehearsals and separate paid approval
  be considered. No automatic rerun under a consumed admission.

### Current provider-free verification

The [projection receipt](../../benchmarks/results/compiler_reading_projection_2026-09-11_v2/README.md)
reprojects all seven frozen inputs and ten saved responses, socket-blocked. Candidate
catalogs, selectable cohorts, bundle/context fingerprints and exact quote surfaces are
unchanged; saved programs/validation/envelopes/execution remain byte-identical. All 88
protected files survive. This is a changed-prompt counterfactual, not exact old-prompt
replay, new model answers, SDK rehearsal or paid admission.

Initial serialized prompt bytes total **189,859**, previously **239,551** (20.74% less).
Candidate payloads alone total **91,540**, previously **93,265** (1.85% less). Shared
context layout adds explicit reading boundaries; most reduction is numeric instruction
removal, not lost source text. Per-input full prompt reduction is 13.5–24.8%; bytes are
not measured tokens/cost/latency. Local tests and remaining gates are in project status.

## Evidence and limits

[Read-only probe](../../benchmarks/results/compiler_reading_audit_2026-09-11/probe.py)
and [receipt](../../benchmarks/results/compiler_reading_audit_2026-09-11/receipt.json):
**7 anonymous structural controls**, socket-blocked, provider calls **0**;
**88 frozen files** unchanged (58 predecessor files plus 30 latest-run files).
Receipt SHA `ddf56e9034b876e7354b10fc5c8502dc1f18b349998ab1e0fc702fdbf916a7f1`.
Existing focused tests: **53/53** in 6.030s, Python 3.13.

The diagnosis's predecessor remains runtime **6/7**, narrow source review **1/7**
with an unsupported qualifier. The [subsequent v7 comparison](../../benchmarks/results/compiler_reading_compiler_2026-09-11/RESULTS.md),
admission `73391c0e`, ran seven calls with no retry: runtime **7/7**, source review
**2 clearly met / 1 partial-uncertain / 4 not met**, estimated USD 0.18855625/0.60.
Seven responses replay identically, API 0; 93 protected files unchanged. Group scope,
uncertainty and subject interpretation remain open. No full-agent/ledger or generalization claim.

The subsequent [heading-order correction](../../benchmarks/results/compiler_heading_order_2026-09-11/README.md)
fixes the observed TITLE/P reversal using existing parent depth/path and heading relation:
within one parent, its formal title precedes intermediate headings. Outer/inner and
different-parent ordering remain prior to relation, with natural sibling indices/spans.
This does not claim full XML order across arbitrary different-tag body siblings.
Anonymous XML reproduces the failure before repair. Seven saved responses retain all
program/validation/envelope/execution bytes; source surfaces, owner authority and 123
protected files remain unchanged. Only two input layouts change; API calls zero.
Semantic impact is unmeasured. Pre-existing row-cell text concatenation and requirement/
planner specificity remain separate next work; no prior artifact or store is rewritten.
