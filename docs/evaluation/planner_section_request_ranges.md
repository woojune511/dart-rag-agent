# Planner source-section request ranges

Implemented provider-free from `34cd0068` on 2026-09-18. The Planner now selects
existing request-unit endpoints for a section restriction. Code copies the
complete original range instead of asking the model to recopy an excerpt.
This removes free-form request quotation from this production schema while
preserving strict historical validation. It does not establish model accuracy.

The [preceding real-DART run](dart_narrative_pipeline_check.md) remains incomplete:
the model added an opening quote to a section-request excerpt, blocking both
outputs before retrieval and compilation. Its response, answer and consumed
manifest are unchanged. This change addresses the **Planner contract** boundary,
not missing store data or Compiler narrative fidelity.

## Contract

Each `source_section_bindings` item now contains:

```json
{
  "first_request_unit_id": "request_001",
  "last_request_unit_id": "request_003",
  "section_ids": ["an_observed_section_id"]
}
```

The range includes both endpoints and every unit between them. All units must
belong to the output. Code preserves their exact text, punctuation, whitespace
and Python-string span. Numbered or quoted paths can span mechanical units;
the partitioning and IDs do not change. The model still interprets which range
and observed sections express the restriction, including its qualifications.

Unknown/reversed endpoints, unowned intermediate units, unknown section IDs and
empty unresolved selections stay invalid. Parent/input intersection, filing
identity, descendant membership, literal-path checks, per-owner Compiler
preflight and V2 execution fingerprints remain authoritative. The production
schema forbids model-written quotes, offsets and resolved locations for both
output and input owners. Source-defined groups preserve copied typed references.

Historical `SourceSectionBindingV1` records retain their unique exact excerpt
check. Malformed old quotations are neither stripped nor converted to ranges.
Copied text, span or endpoint tampering fails revalidation or execution.
Whole-unit linkage does **not** certify that the model selected every qualifier
or the semantically correct section. An authored wrong known-section choice
remains a semantic negative even when its physical request linkage is valid.
No company/title rule, alias dictionary, new model call or retry was added.

The existing strict OpenAI transport sends fixed objects with required fields;
the new binding uses only strings and arrays within the existing nested schema.
[Official Structured Outputs documentation](https://developers.openai.com/api/docs/guides/structured-outputs#supported-schemas)
was checked for these schema constraints. Local SDK serialization is not live
provider schema acceptance or evidence that the next plan will be correct.

## Verification and evidence limits

The [local packet](../../benchmarks/results/planner_section_request_ranges_2026-09-18/)
freezes the six anonymous numbered/quoted/Unicode/repeated-text controls before
runtime edits. Baseline characterization and existing section/request tests
pass **47/47**. The added-quote variants remain invalid after the change.

The new tests cover exact whole-range copying, noninitial and single-unit ranges,
unowned intermediate units, bad endpoints, unresolved/unknown sections, explicit
path and filing rejection, parent/input intersection, historical preservation,
schema rejection of model-owned text/resolutions, source-group round trips,
Compiler retry, isolated preflight, final answer/ledger and execution tampering.
The real installed SDK is exercised with mocked HTTP and blocked sockets.
Authored plans/programs are transport witnesses, not new model answers.

Focused checks pass **160/160**, and the full suite passes **2058/2058** with no
skips or external connection attempts. Domain audit passes with **83** reviewed
literals; source compilation, documentation checks and `git diff --check` pass.
All **6659** predecessor files, **24** stores and local settings retain hashes;
only the four scoped source/policy files change among 174 source files.

Six saved-plan contrasts preserve the original response's two errors and zero
eligible graph nodes. A separately authored first-to-third-unit range links both
outputs to the known source node; unowned intermediate units, reversed endpoints,
unknown sections and unresolved sections each remain blocked. This is graph-node
eligibility only: no new retrieval, model generation, Compiler or answer occurred.

One development integration fixture initially requested a company absent from
its synthetic candidate; the retained company guard correctly triggered a repair.
The fixture now scopes the observed filing directly. The first full suite had
only a documentation-length failure; one paragraph was consolidated within the
existing limit, and the complete suite then passed. Both failures remain recorded;
no runtime guard or test limit was weakened.

Provider/count/embedding calls, store writes and added cost are **0**. Shared
accounting remains **10.91938255 / 14**, remaining **3.08061745**, pending **0**,
not an invoice. The prior consumed manifest cannot be reused.

Next prepare a fresh bounded real-question check to evaluate the generated
range choice, retrieval exposure and final answer separately. Use the same
known-source question and frozen content criteria; preserve the old incomplete
result and review semantic completeness independently of contract validity.
