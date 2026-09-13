# Current Handoff Context

Last updated: 2026-09-14

## Product and authority

The product is the single-agent `FinancialAgent`.
Working branch: `codex/reviewed-compiler-selection-gate`.
The general correctness audit starts at clean `327002c0`; Git records the implementation history.
Latest [source-address full-agent result](benchmarks/results/narrative_address_full_agent_2026-09-14/RESULTS.md), run HEAD `e6d196b9`/runtime `7ed5f332`: admission `e3a09359f073e80011246d2e9d443f8bab342446d44f7436f70214cd6b7c0a5a` consumed once. **NEW_NARRATIVE_01 complete** (one output, ledger ok, both themes/source criteria met in Codex review); **NAV_T2_006 interrupted**, **NEW_NARRATIVE_02 not dispatched**. Not a three-question score or release success. Flash **4**, Pro **2**, OpenAI **17** SDK requests completed, no provider error/429; estimated **USD 0.17712341/0.80**, billing unobserved. The next Pro request (245,433 bytes) reserved **USD 0.7313425**, bringing cumulative reservation to **0.90846591**; the guard blocked it before transmission. Eight accepted fact/subject quote occurrences match selected original source IDs; **158** runtime files / **34** inputs / **23** store files unchanged. Receipt `4d77c1bc...cc60`, local review `0f86459b...134a`. Interrupted NAV plan/draft/validation were not exported; retry versus another island and its validation cause are unknown. No paid rerun or store mutation; the local diagnostic successor below does not recover this lost trace. The [previous complete-batch full-agent result](benchmarks/results/narrative_reading_full_agent_2026-09-13/RESULTS.md) remains **0/3 complete**, **1/5 outputs accepted**, ledger **3/3 ok**, estimated **USD 0.30784205/0.80** on `ec9d4a20`/`c247cb83`; it is not rewritten by this partial run.

Latest [source-address compiler-only result](benchmarks/results/narrative_address_compiler_2026-09-14/RESULTS.md), run HEAD `9771417f`/runtime `7ed5f332`: admission `a34a75996d7b6ab105c2f75f803f3c5560360f57163391e2eb43e5e97d826ca1` consumed once. **9/9 structurally complete**, **11/11 outputs accepted**, Codex pre-fixed source criteria **9/9** (anonymous **6/6**, saved DART **3/3**); not human gold, unseen holdout, full-agent or ledger success. Pro **13 calls / 2 internal retries**, 202.996s, estimated **USD 0.4594425/0.90**, billing unobserved; provider/execution exceptions **0**. NAV acquisition and CEL liquidity complete in this fixed-plan sample; NAV numeric values/IDs/physical and display provenance are unchanged. Nine V2 execution/final replays are byte-identical, 43 selected fact/subject ranges match transmitted pieces, and retry payloads are unchanged. **110** protected and **161** runtime files intact; receipt `0fbaf3d6...9e75c0`. Both retries were in NAV: missing display-period context, then subject support/source-number formatting. No runtime patch, planner/retrieval/embedding/store call or batch rerun. The [7/9 compiler predecessor](benchmarks/results/subject_fact_compiler_2026-09-13/RESULTS.md) and previous **0/3** full-agent outcome remain immutable.

Read [AGENTS.md](AGENTS.md), [runtime contract](docs/architecture/agent_runtime_contract.md),
[code map](docs/overview/codebase_map.md), and [project status](docs/overview/project_status.md).
The [general audit](docs/architecture/general_correctness_audit.md) records reproduced
defects, generic regressions, coverage limits, and remaining work.

## Current runtime

- Every intent, including pure narrative, uses the existing requirement planner and
  source-bundle compiler. Intent/format cannot bypass requested-output coverage.
  Exact request units remain active-owner instructions, not coupling/rank signals. Before fixing subjects, the existing planner reads report-scoped whole source axes (64 / 16 KiB), with original-query matches, hierarchy and observed examples. Repeated axes share context; omissions/fingerprint stay traced. This is a hint, not a name allowlist or alias authority. Names/groups/other conditions remain in request/scope; no suffix stripping, target rewrite, validator relaxation or extra call. V2 binds the plan/query, not semantic correctness.
  Narrative-bearing multi-output calls receive one copied full-plan responsibility map, fixed across retries, with no candidate/accepted-answer/status authority. Numeric-only and single-output prompts add nothing. Shared qualifiers and independent topics remain; no fixed count, semantic deletion or new call. The latest fixed-plan sample records reduced but nonzero repetition, not a guarantee about future answers.
- The existing planner links exact owned request excerpts to observed filing-qualified section IDs via `source_section_bindings`; code adds spans/paths/fingerprint. Read-only metadata inventory is bounded and report-scoped. Unknown resolution stays an error, not unrestricted access.
  Parent/input restrictions intersect in retrieval/cohorts/validation, including dependencies. V2 binds original wording and resolved location; foreign/unlocated sections cannot bypass via context.
  Legacy `source_sections` stays literal-only; no dual-write, substring alias rule or extra call. ID/path verification proves location, not the planner's semantic equivalence judgment.
- Compiler selects meaning, bindings, formulas and source display. Deterministic code
  owns units, arithmetic, scope/ID authority, exact source assertions and execution.
  No seven-role classifier, cross-encoder, extra judge or benchmark-ID branch was added.
- Each compiler attempt declares active outputs and bounded-excerpt coverage. Narrative
  `subject_bindings` explicitly share source-local subject support; each claim has its own
  fact selections. Code extracts exact addressed ranges and renders subject labels; both number checks use fact ranges/report year only. Shared subject support grants no numeric authority.
  Current compiler/executor reject raw quote or flat claims. No implicit subject inheritance; structural acceptance still does not prove entailment/completeness.
- `CompilationEnvelopeV2` binds full catalog content, ordered obligations and query.
  Only declared `depends_on` outputs may become formula inputs. Retry assertion
  projection cannot modify unrelated accepted outputs or introduce foreign evidence.
  Narrative retry carries only targeted unvalidated subject registries/claims with original error locations;
  excluded/foreign evidence links are omitted. Unsupported claims may be corrected/dropped or withheld.
  Opt-in `compiler_attempts` retain schema-parsed model/merged-input JSON, hashes, validation locations and exact retry feedback before pruning; request-local capture does not enter answer/review/ledger/scoring or change prompts/calls. Unavailable parsed output is explicit, not fabricated.
- Source bundles preserve adjacent values and document context. Actual unique selectable
  unions are bounded by numeric 96 / narrative 32; at most eight islands and one internal
  retry per island. Budget/admission stops propagate without fallback or extra calls.
- Compiler v8 uses lossless, content/provenance/partition-bound pieces for narrative-bearing calls; only identical document/context attachments share readings. Numeric-only candidate payloads remain byte-identical v7. Metadata/ranking diagnostics are not source authority; candidate IDs, cohorts and bundle/catalog fingerprints are unchanged.
- XML recovery preserves ampersand text and quoted attributes; explicit header/body
  tables remain data. Both narrative modes can read numeric rows. Non-scalar rows gain
  reading-only evidence without changing existing chunk numeric extraction or spans.
- Standalone peer headings persist; paragraph-to-table context stops at heading changes,
  while captions retain enclosing scope. Nested metadata stays outside exact narrative
  body windows; `local_heading` is a hint, never subject authority. Fresh table contexts retain cell-local segments; claims/scope quotes cannot cross them, but multi-cell evidence bindings remain valid. Fresh
  intermediate headings also retain exact XML spans; full scope separates chunks and
  table context. Prose/table candidates receive located quotes through the existing sidecar.
- Narrative exposure separates numeric identity precision from reading eligibility.
  Scope/unit precede topic relevance (including owner-local search hints), then literal mention, with format-neutral tiers
  and document/section/source/row diversity. Hints never establish identity or quote authority;
  numeric matching, explicit conflicts, per-owner permissions and 96/32 caps stay intact.
- Optional `row_description_quote` binds exact row-axis text to a physical row and filing.
  Only that quote/report year ground description numbers; ordinary scalar use retains
  its own period checks. Validated description-only IDs are not numeric operands or
  raw-value evidence. No candidate rewrite, role enum, ranking change or extra call.
- One unit contract preserves scale, sign, currency and finite arithmetic.
  Source display is primary; a differing recalculation is labelled separately.
  Downstream formulas consume calculated values, not rounded display values.
- Search, local supplements, seeds and final evidence share the same explicit source
  filter. Empty scoped results stay empty. BM25 filters before candidate cutoff.
  Filing-local chunk numbers cannot collapse distinct or unidentified documents.
- Fixed-year selection priorities were removed. Generic year patterns replace dated
  stopword lists. Routing prompt examples are anonymous declarative data.
- Whole calendar/relative/fiscal labels, including abbreviated years, cannot become
  inferred local subjects. Entity-name substrings and explicit subject authority stay intact.
- Canonical routing caches only complete, finite, correctly dimensioned successful
  batches with known identity. Search-cache values are owned copies, invalidated at
  successful source commits. Persistence failures propagate.
- Atomic source publication is payload union then graph, memory last. Incomplete stores
  block queries but allow ingest recovery using existing vectors/context.
- Query readiness/execution/snapshot share one lock; blocking DB/ingest work runs in
  workers. Public API errors do not interpolate raw provider exception text.
- Explicit phase TypedDicts describe static shape, not runtime immutability.
  `assemble_final → assemble_ledger → END` publishes one answer; ledger status reflects
  partial/incomplete public results rather than calling every aggregate complete.
- HTTP shape, `FinancialRunResultV1`, manifest format and candidate ID/hash algorithms
  are unchanged. Parser prefix preservation affects future parsing only; stored
  catalogs, physical IDs, source stores, datasets and past artifacts are not rewritten.

## Evidence and claim limits

Use Python 3.13 (`.venv/Scripts/python.exe`). Current local validation is recorded in
project status; unit/no-call success is not model accuracy or release acceptance.
Synthetic tests vary names, years, source identities, input order, scope, errors and
mutation, rather than turning reviewed benchmark answers into runtime rules.

The earlier full-agent four-question run used clean `cf721258` and exhausted admission
`a2bd7bdd...a311`: four attempts, API/runtime errors zero, ledgers 4/4 ok.
It did **not** complete four answers: LG omitted the requested-period local value;
Celltrion omitted one theme and used the wrong requested source scope. Those frozen
results are not retroactively fixed by the current code.
[Full-agent result and limits](benchmarks/results/diagnostic_four_full_agent_2026-09-09/README.md).

The separately approved KB successor store is strict-ready/non-degraded in its recorded
receipt; default `data/chroma_dart` is a different, incomplete KB 2022 store and was
not repaired. [Store receipt](benchmarks/results/kbf_parser_openai_store_2026-09-09/README.md).

[Reviewed-case evidence status](docs/evaluation/reviewed_case_evidence_status.md) separates
historical live runs, counterfactual contract replays, and current catalog compatibility.
Old 3/3 and five-case successes are historical, not a synchronized current-head release.

## Next work and hard stops

1. The claim contract is implemented, not a semantic judge. Its
   [socket-blocked counterfactual](benchmarks/results/narrative_claim_grounding_2026-09-11/README.md)
   rejects a metadata-only issuer subject and accepts an authored source-local quote.
   Retagging the old broadened paragraph with its mentioned subsidiary still passes:
   this negative control remains open. No new model answer or semantic score is claimed.
2. Historical [claim](benchmarks/results/narrative_claim_compiler_2026-09-11/RESULTS.md), [subject](benchmarks/results/narrative_subject_compiler_2026-09-11/RESULTS.md) and [retry](benchmarks/results/narrative_retry_compiler_2026-09-11/RESULTS.md) results remain immutable, not current-head semantic scores; exact quotation does not prove attribution or requested-theme completeness.
3. Server-count admission is now an explicit experiment option, not a runtime default.
   It counts the final SDK body without removing schema/system fields, reserves that
   input plus the unchanged **5120** output bound, and records count allowances
   separately from usage-estimated generation cost. Count failure has no fallback;
   HTTP errors/redirects and usage overruns stop without another transmission.
   [Contract and policy fields](docs/evaluation/provider_admission.md).
   Local implementation gate **1,596/1,596**, provider calls **0**; production prompts/schema/permissions/defaults and old policies/results remain unchanged.
   [Paid guard validation](benchmarks/results/server_count_validation_2026-09-14/RESULTS.md) consumed `b3474acd...6c24c` on clean `557177d8`/runtime `d7b52100`: counts **2** + generations **2**, **4/4 HTTP 200**, retry **0**, 14.079s. Counts/reservations/prompt usage match **20 / 4,135**; full schema/system and output bound **5120** retained.
   Generation estimate **USD 0.01798725** + count allowance **0.12** (not billing) = accounted **0.13798725/0.20**; peak **0.17810725**, pending **0**. Result `1142a959...3d3dc`/review `ceb447ef...d67b7` remain immutable; this does not establish full-agent success.
   [Prepared full-agent successor](benchmarks/results/server_count_full_agent_admission_2026-09-14/README.md), `5295c516ec186d4310203a2b97db15bb79bbf939ceae678e9d56cc5cc0599a14`, keeps the same three questions/order/stores and fresh planning; proposes **USD 1.60** with count allowance **0.06/attempt**, not billing. Tests **14/14 + 36/36**, two byte-identical receipts `4d3c4a2f...fa270`; runtime **161**, input/protected **124**, original store **23** hashes verified. Existing query tokenizer is pinned/read-only; no download. Provider calls **0**, separate approval pending; no automatic resume/default change.
   The [measured predecessor](benchmarks/results/server_token_accounting_2026-09-14/RESULTS.md)
   consumed `1d067e26...bd3fa` on `0f97a533`: full counts **20 / 4,135** matched
   prompt usage; byte reservations **24,841 / 43,977** were excessive on those two
   inputs. **8/8 HTTP 200**, retries **0**, generation estimate **USD 0.01636975**;
   invoices/count tariffs unobserved. No universal framing or schema-billing rule
   follows; even the new two-input guard success is not full-agent validation. Request-local
   interruption diagnostics remain outside answer/ledger/judge authority; lost NAV
   drafts remain unrecoverable. The [12-question pilot](benchmarks/results/independent_pilot_compiler_2026-09-10/README.md)
   remains runtime 7/12, reference-scalar 4/9, with three incomplete/unfaithful narratives.
   The [three-narrative comparison](benchmarks/results/narrative_reading_compiler_2026-09-11/RESULTS.md)
   remains runtime 2/3, Codex source-review 1/3 on `ff283a58`, not current-head output.
   Original sources/results/labels remain immutable. Provisional reference adoption is
   not individual human source verification or untouched-source generalization.
4. Prior [row-description](benchmarks/results/narrative_row_description_2026-09-11/README.md),
   [section](benchmarks/results/requested_source_sections_2026-09-11/README.md) and
   [source-local](benchmarks/results/local_heading_scope_2026-09-11/README.md) probes are
   source-exposed contract regressions, not repaired stores or paid response improvements.
5. No automatic paid rerun, fresh ingest, store adoption/mutation, answer-key adjustment,
   tolerance relaxation, or experimental artifact commit.
6. Remaining characterized limits: planner theme omission/semantic faithfulness still
   require independent review; document acquisition ambiguity/pagination, full source
   text bijection, and retired narrative-helper removal need separate bounded work.
   Formula-wide rounding propagation and default-store recovery remain deferred.

Chronology: [implementation history](docs/history/implementation_history.md),
[experiment history](docs/history/experiment_history.md), and Git.
