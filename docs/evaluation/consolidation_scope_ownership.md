# Planner consolidation-scope ownership

The [six-question probe](measurement_coverage_probe_result.md) exposed a code error:
the ordinary phrase `별도의 특정 날짜` changed the model's `unknown` reporting basis
to `separate`. The query-marker scan could also erase English scope interpretations,
override a negated scope word, or choose one basis for independently scoped outputs.

## Contract correction

Planner interprets the owned request and declares `consolidation_scope`. Code now
preserves that declaration instead of creating, replacing or erasing it from query
substrings. An unknown child can inherit its declared parent's known basis; a
child's own known basis stays intact. Filing metadata supplies no request default.
No new fields, prompt changes, keyword exceptions or model calls are introduced.

The task's shared retrieval preference now summarizes the actual source owners:
direct outputs and declared evidence inputs. A single uniform known basis permits
the existing ranking bonus/penalty. Mixed or unknown scopes yield no shared basis
preference. Reranking reads that task declaration instead of scanning the query or
defaulting financial vocabulary to consolidated statements. This is a preference,
not a new source filter; owner-specific source-conflict checks remain independent.

The old generic fixture that supplied unrequested/wrong model scopes remains
unchanged. Its integration tests now retain those choices as semantic negatives,
instead of asserting that keyword-based coercion proves request provenance.
Wrong but well-formed model interpretations are not automatically repaired.
Known source conflicts still fail existing owner/Compiler/execution checks.

Only `financial_graph_planning.py` and `financial_retrieval_pipeline.py` change in
production. Older query-marker helpers remain in the separate legacy helper
surface; they are no longer called by Planner normalization or retrieval reranking.
This change does not claim to remove every heuristic from the repository.

## Provider-free evidence

Clean baseline **`70784547`**. The installed SDK replays the six original raw model
responses with blocked sockets and unchanged questions. All six request bodies
are identical to the preceding instruction-change capture: same prompt/schema,
model and limits. There is no new model sample or saved-response rewrite.

Only c04 changes: its declared `unknown` is retained in all **eight** normalized
scope/task projections formerly forced to `separate`. The other **5/6** plans are
identical. All six measurement constraints and report filters are unchanged.
The original period semantic result stays **2/6**, coverage **0/4**; its four model
errors and consumed manifest remain historical evidence. No actual search occurs.

Twelve new regressions cover ordinary and negated wording, English interpretations,
metadata isolation, parent/child scopes, uniform/mixed ranking, deliberate semantic
negatives and known source conflicts. Ten fail before the edit; all twelve pass
afterwards. **170/170** focused tests, full **2,225/2,225** (70.512 seconds),
import/topology/documentation gates and domain audit **83** pass. No skips or
external network attempts. An obsolete
mock removal initially left two stale tuple indexes in a caller test; those test
indexes were corrected without changing runtime behavior, and the failed log is
retained. Syntax/diff and protected-file integrity checks also pass.

All **13,040 predecessor files**, **174 unrelated production sources**, **24 original
store files**, local settings and the old generic fixture retain their hashes.
The ignored packet is `benchmarks/results/consolidation_scope_ownership_2026-09-22`.
Added provider calls/accounting **0**; shared **19.54154943/20.32**, remaining
**0.77845057**, pending zero. No ingest, funding increase, automatic paid retry or
general model-accuracy claim.

Next prepare a bounded new Planner comparison with frozen period and scope criteria
that fits the remaining allowance. A provider-free replay does not establish how
the model will interpret new requests; any later live run needs fresh admission.
