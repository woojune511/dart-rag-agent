# Report-Scoped Cache Capability Contract

This note defines the current boundary for report-scoped value cache work. The
goal is to keep cache material reviewable without silently turning it into a
serving path, a write path, or a task/artifact ledger producer.

## Current Position

Report-scoped cache is a disabled capability. It may classify and project
candidate values, but it may not change retrieval, final answer acceptance, or
ledger state.

Current repo surfaces:

- `src/config/report_scoped_cache.py` owns pure key, candidate, entry,
  rehydration, guarded-consumer, calculation-projection, and producer-policy
  projection helpers.
- `report_cache_capability_status()` exposes the current disabled capability
  boundary as a code-level status helper.
- Runtime calculation traces may carry a read-only `report_cache_candidate`.
- Retrieval may include cache-index diagnostics in `retrieval_debug_trace` when
  `report_cache_index_path` is explicitly configured.
- `src.ops.review_report_cache_index_contract` is the reviewer handoff gate.
- `src.ops.report_cache_promotion_evidence_gate` is the first focused
  promotion-evidence gate for ready, incomplete, and ambiguous cache matches
  across the local-index fixture and a reviewed store-fixed trace summary.

The latest reviewer gate expectation is:

- `status = ok`
- `difference_count = 0`
- `reviewer_handoff.status = ready`
- `reviewer_handoff.mode = candidate_only`
- `reviewer_handoff.retrieval_bypass_enabled = false`
- `reviewer_handoff.write_enabled = false`
- `serving_enabled = false`
- `ledger_insertion_enabled = false`
- one projection-ready candidate and one fallback candidate in the fixture
- one producer-policy-ready candidate and one producer-policy fallback in the
  fixture
- promotion evidence reports ready and fallback cases from fixture plus trace
  summary inputs, with no enabled serving, retrieval-bypass, ledger-insertion,
  or final-acceptance flags

## Capability Pipeline

```text
Runtime trace candidate
  -> ReportCacheCandidate
  -> persisted local-index entry
  -> rehydration candidate
  -> guarded consumer assessment
  -> disabled calculation-contract projection
  -> reviewer handoff
```

Only the last step is a portfolio/reviewer gate today. None of these steps
authorizes retrieval bypass, cache writes, or live ledger insertion.

## Contract Surfaces

| Surface | Required fields | Current owner | Current mode |
| --- | --- | --- | --- |
| `ReportCacheCandidate` | report scope, value identity, provenance scope, structured value, source refs | runtime trace projection | read-only candidate |
| `ReportCacheEntry` | `entry_version`, `source`, normalized key, value payload, provenance payload | persisted local index | readable only from `local_cache_index` |
| `ReportCacheRehydrationCandidate` | answer slots, citation/source anchor, evidence material, calculation trace | rehydration classifier | disabled consumer contract |
| `GuardedConsumerAssessment` | selected match count, key match, rehydration readiness, fallback reasons | guarded consumer classifier | trace-only |
| `CalculationContractProjection` | candidate calculation task, `operand_set`, `calculation_plan`, `calculation_result`, evidence refs, disabled flags | projection helper | candidate-only, not inserted |
| `ProducerPolicyProjection` | calculation task policy name, required artifact kinds, cache-origin metadata, disabled flags, fallback reasons | producer-policy helper | candidate-only, not inserted |
| `PromotionEvidenceCase` | guarded-consumer status, producer-policy status, fallback requirement, disabled flags, acceptance authority | promotion-evidence helper | focused gate, not serving |
| `ReviewerHandoff` | status, mode, disabled flags, projection-ready/fallback counts, producer-policy ready/fallback counts | review command | reviewer gate |

## Required Invariants

- Cache keys must include report scope, value identity, and provenance scope.
- Runtime trace candidates and artifact-store projections are not readable cache
  sources.
- The only currently readable persisted source is `local_cache_index`.
- A readable entry is still not sufficient for serving. It must also pass
  rehydration and guarded-consumer checks.
- Ambiguous matches require normal retrieval fallback.
- Missing answer slots, missing primary value display, missing citations/source
  anchors, missing evidence material, or missing calculation trace require
  normal retrieval fallback.
- Candidate calculation projections must carry `operand_set`,
  `calculation_plan`, and `calculation_result` artifacts with evidence refs.
- `enabled`, `serving_enabled`, `ledger_insertion_enabled`, and retrieval-bypass
  behavior must remain false until a separate promotion explicitly changes the
  contract and tests.
- `report_cache_capability_status()` is the code-level source for the current
  candidate-only mode, disabled flags, and reviewer pipeline.
- Cache candidates may not mark final answers accepted. Acceptance remains with
  task/artifact integrity and critic/orchestrator contracts.

## Explicit Non-Goals

- Do not enable cache serving.
- Do not enable retrieval bypass.
- Do not write new cache entries from live runtime.
- Do not insert rehydrated cache candidates into the live task/artifact ledger.
- Do not let `REFERENCE_NOTE` graph expansion become a hidden cache-serving
  mechanism.
- Do not add benchmark-specific cache rules.

## Producer Policy Decision

The current producer-policy decision is now a code-level contract in
`build_report_cache_producer_policy_projection()`: any future cache-derived
ledger candidate must reuse the existing calculation task contract. A
rehydrated cache entry may project to a candidate `calculation` task with
`operand_set`, `calculation_plan`, and `calculation_result` artifacts, carrying
explicit cache-origin metadata:

- `source = report_cache_rehydration`
- `cache_origin = local_cache_index`
- `report_cache_key_id`
- `rehydration_status`
- `consumer_admissibility_status`
- `enabled = false`
- `serving_enabled = false`
- `ledger_insertion_enabled = false`

This is the preferred policy because it keeps cache-derived values inside the
same artifact integrity contract as ordinary numeric answers. It also avoids a
parallel acceptance path: final answer acceptance still belongs to
task/artifact integrity plus critic/orchestrator handoff, not to cache
availability.

Rejected-for-now alternative:

- Add a dedicated `cache_rehydration` task/artifact kind.

That alternative remains available only if future evidence shows that
cache-derived material cannot be represented safely as candidate calculation
artifacts. Until then, a dedicated kind would add a second ledger path and make
acceptance harder to audit.

The producer policy does not enable live ledger insertion. It defines only the
schema that a future promotion would have to satisfy before insertion could be
considered.

## Promotion Preconditions

Before any future serving or ledger insertion flag can be enabled, the repo
must add a new promotion increment that:

1. Keeps cache-derived ledger candidates mapped to the calculation task
   contract above, or explicitly updates this producer-policy decision with a
   stronger reason for a dedicated `cache_rehydration` kind.
2. Runs the existing reviewer handoff gate and adds a focused contract test for
   the new enabled flag.
3. Demonstrates that normal retrieval fallback still happens for blocked,
   ambiguous, or incomplete entries.
4. Shows that final acceptance still depends on task/artifact integrity and
   critic/orchestrator contracts, not cache availability.
5. Documents whether `REFERENCE_NOTE` remains graph-expansion context or becomes
   part of this capability boundary.

The first focused promotion-evidence increment is now present but non-enabling:
`build_report_cache_promotion_evidence_case()` and
`src.ops.report_cache_promotion_evidence_gate` show that a complete local-index
entry can satisfy the guarded consumer plus producer-policy contracts, while
incomplete and ambiguous entries still require normal retrieval fallback. The
gate also consumes a reviewed store-fixed trace summary so the same ready and
fallback expectations are checked outside the raw fixture path. Ready promotion
evidence must expose the calculation-task producer policy, the required
`operand_set`, `calculation_plan`, and `calculation_result` artifact kinds,
cache-origin metadata, and a valid calculation-contract projection. It keeps
retrieval bypass, serving, ledger insertion, and final acceptance disabled.

## Current Interpretation

The current system is ready for reviewer handoff as a candidate-only cache
capability. It is not ready for serving or live ledger insertion. The next
increment should expand promotion evidence with additional live/default MAS
trace summaries before any enable flag is considered.
