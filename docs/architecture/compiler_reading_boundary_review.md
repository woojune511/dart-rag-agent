# Compiler reading boundary review

Status: diagnosis and proposed next change; **not implemented**.
2026-09-11; reviewed clean `08ee8a35`, unchanged runtime `ef065b7b...f957a`.
Authority: [runtime contract](agent_runtime_contract.md).

## Conclusion

The latest failures do not establish missing heading text or a validator that
forbids reading headings. The source context and failed retry drafts arrive.
The compiler interface instead mixes a source-reading task with bookkeeping,
ranking factors, numeric instructions and underspecified authored requirements.
Some defects are directly reproducible; their effect on model interpretation is
not causally measured. Another instruction-only paid rerun is not the next step.

This review changed no runtime, model, schema, candidate ID, source store, dataset,
frozen response or evaluation criterion. No provider call was made.

## Findings

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

## Next implementation, one owner seam first

First change only the **compiler presentation projection**, keeping the catalog,
selection/visibility, program schema, validator, executor and provider-call count:

1. Use an explicit allowlist for prompt match fields. Keep necessary applicability
   states, but remove rank vectors/diagnostic scores from model input; keep them in
   trace. A recursive prompt check must catch leaks through either cohorts or rows.
2. Present a source-local reading unit: exact located enclosing headings, local
   paragraph/table body and their existing quote targets next to each other.
   Use actual document identity/location/attachment, never company-name equality or
   title wording, to arrange them. Keep document metadata in a clearly separate
   provenance area. Do not infer a pronoun's identity or overwrite an explicit body subject.
3. Keep empty scalar-only fields and numeric-only explanatory clauses out of a
   narrative-only reading view. Mixed/numeric obligations retain their needed
   fields and rules. This is a prompt projection, not a second answering route.
4. Distinguish ordinary narrative row quotes from the special permission to read
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

## Evidence and limits

[Read-only probe](../../benchmarks/results/compiler_reading_audit_2026-09-11/probe.py)
and [receipt](../../benchmarks/results/compiler_reading_audit_2026-09-11/receipt.json):
**7 anonymous structural controls**, socket-blocked, provider calls **0**;
**88 frozen files** unchanged (58 predecessor files plus 30 latest-run files).
Receipt SHA `ddf56e9034b876e7354b10fc5c8502dc1f18b349998ab1e0fc702fdbf916a7f1`.
Existing focused tests: **53/53** in 6.030s, Python 3.13.

The paid outcome remains runtime **6/7**, narrow fixed source criteria **1/7**, with
an unsupported qualifier even in that one route-separation case. Nothing here is
a new model answer, semantic improvement, full-agent/ledger gate or generalization
claim. The runtime's earlier 1360-test full gate was not rerun for this diagnosis.
