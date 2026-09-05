# Project Status

Last updated: 2026-09-05

## At a glance

| Question | Current answer |
| --- | --- |
| Product | Single-agent `FinancialAgent` for evidence-backed DART filing analysis |
| Working source | `codex/bounded-semantic-tiebreaker`; bundle contract `d4aaf37`, compiler transition `30607cd` |
| Candidate path | Typed applicability followed by bundle-first source admission; no candidate-role classifier or local cross-encoder |
| Compiler path | `semantic_program_candidate_payload_v5` plus exact prose `source_assertions` |
| Public result | `FinancialRunResultV1`; HTTP answer/citation/structured-result shape is unchanged |
| Store | Existing manifest, source store, candidate IDs, and catalog fingerprints are unchanged |
| Provider status | Admission `24322d93...9aaf` consumed once; release `HOLD`, no paid retry authorized |

## Current runtime boundary

- `FinancialAgentStateV2` keeps one writer per phase. The final assembler alone
  writes the ledger-backed answer.
- Compiler, validator, and executor share one immutable candidate-visibility
  envelope. Catalog, visibility, program, or validation drift fails before
  execution.
- Applicability separates scope, local subject, owner kind, document subject,
  unit, metric, and physical locality. `explicit_conflict` is excluded;
  `compatible` precedes `unknown_only`.
- A numeric owner admits at most two `SourceBundleV1` bundles. A prose bundle is
  one exact sentence/window; a table bundle is one physical table row. Every
  non-conflicting numeric member of an admitted bundle remains visible so
  period pairs, signs, and neighboring operands stay together.
- Source text is serialized once in `source_bundles_by_id`. Candidate rows refer
  to the bundle and a local value span. They retain the existing candidate IDs,
  catalog fingerprint inputs, row headers, and physical provenance.
- The existing compiler performs semantic selection. Code validates IDs,
  applicability, formula/binding structure, provenance, and exact source
  grounding; it does not classify values as total/component/rate.
- A selected prose numeric operand or source display requires a
  `source_assertion` whose evidence is a byte-exact contiguous bundle substring
  covering all referenced value spans. Table cells and multi-evidence narrative
  bindings do not require this assertion.
- Candidate validation failure promotes the next source bundle. Assertion or
  format failure retries the same cohort once. Other accepted islands and their
  assertion JSON remain byte-identical.
- Unique prompt visibility is capped at 96 numeric and 32 narrative candidates.
  Bundle expansion is atomic; overflow skips every compiler call.
- Dependencies, non-empty coupling keys, and inferred complete physical rows
  define compilation islands. Unknown/self/cyclic dependencies and more than
  eight islands fail before provider dispatch.
- Retrieval, ingest, exact store readiness, API services, and
  `FinancialRunResultV1` retain their existing ownership contracts. MAS and
  Streamlit remain experimental consumers.

## Local acceptance state

The source-bundle implementation has passed its complete local gate:

- source-bundle/catalog/matching: `28 / 28`;
- cohort/compiler/validator/evidence-bundle/island: `90 / 90`;
- runtime domain-term audit: pass, `86` reviewed literals;
- import/topology: `21 / 21`;
- portfolio review gates: `review_surface_ready`;
- `compileall` and `git diff --check`: pass;
- full unittest discovery: `805 / 805` in `19.636s`.

The provider-free fixtures preserve the reviewed behavior:

- same-source current/prior values and parenthesized negatives remain in exact
  source context;
- table cells retain physical row/cell identity and stable candidate IDs;
- source text appears once per bundle rather than once per candidate;
- hidden, cross-bundle, altered-text, and uncovered-span assertions fail;
- LGE-style reported and adjustment values remain separate formula operands;
- narrative answers may synthesize multiple evidence bindings rather than being
  forced into a top-one candidate.

The immutable three-question predecessor was also reprojected without a
provider call. All three catalogs replayed as verified. T2 keeps `87.0`, `78.1`,
and `11.5` within applicable owner visibility. T3 keeps Motional `26%` visible
and excludes BHAF `53%`. Samsung retains all four previously selected candidate
IDs. This proves the new visibility boundary, not compiler semantic quality.

## Provider validation result

The approved store-fixed run at commit `5c4c796` completed once in `339.1s`.
It used 18 LLM calls and 129,656 LLM tokens; the recorded non-embedding estimate
was USD `0.1187678`. There was no runner retry, fresh ingest, document embedding,
or source-store mutation. Original result, SQLite, and complete store
fingerprints stayed unchanged.

Release remains `HOLD`:

- `HYU_T2_010` is mechanically complete, but the compiler bound `87.0` and
  `78.1` and rendered their `11.4%` formula result instead of binding the visible
  source-stated `11.5%` display. Faithfulness was `0.7`.
- `HYU_T3_072` passed the reviewed boundary. `26%` and `700,691백만원` share
  table 82 row `9:2`; the four summary values share table 90 row `21:4`; BHAF
  `53%` was not selected.
- `SAM_T2_078` selected accepted `cand_27da082cf5bcd0cb9f27` first. Validation
  rejected canonical planner unit `KRW` as a display unit and the retry treated
  that format mismatch as candidate-specific, promoted another bundle, and left
  numeric obligation `ob_001` missing. Completeness was `0.5`.

Mechanical runtime completeness is `2 / 3`; the stricter reviewed
source-consistent gate is `1 / 3`. The immutable run receipt is stored beside
the ignored result bundle.

## Immutable predecessor evidence

The earlier approved three-question store-fixed run remains historical evidence:
`HYU_T2_010`, `HYU_T3_072`, and `SAM_T2_078` were runtime-complete with zero
runtime errors and ledger `ok`. Admission `06a40243...016`, the prose-role
admission `729d1f53...4b93`, and current source-bundle admission
`24322d93...9aaf` were each consumed once and must not be reused.

Benchmark results, source stores, datasets, caches, and prior review HTML remain
uncommitted and immutable. Historical chronology stays in
[implementation_history.md](../history/implementation_history.md) and
[experiment_history.md](../history/experiment_history.md).

## Next gate

1. Add a provider-free unit contract for normalized dimension symbols such as
   `KRW`, and prevent obligation-format errors from evicting candidates.
2. Add a compiler contract fixture in which a selected source bundle contains
   both period operands and a matching source-stated derived display; require
   the semantic program to preserve the display without a keyword branch.
3. Re-run focused tests and replay the saved result artifact without providers.
   Only then prepare a new manifest for separate approval. Do not reuse the
   exhausted admission, auto-retry, or perform fresh ingest.

See [runtime_flow_roles.md](runtime_flow_roles.md) for checked topology and
[agent_runtime_contract.md](../architecture/agent_runtime_contract.md) for the
normative contract.
