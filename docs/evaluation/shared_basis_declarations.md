# Shared-basis declarations and member references

Implemented 2026-09-17 from `47cf17ea`. Compiler now declares the common basis
once per request-grounded relationship and explicitly references it from each
ready member. Each output retains its own source interpretation, without an
exact-text equality requirement across those local explanations.

## Contract

- The existing relationship ID binds the output set and the exact request span
  owned by every member. No new request field, grouping heuristic or graph phase.
- `CompilerResponseV2.relationship_declarations` contains fixed, editable
  relationship keys. Related ready results require `relationship_refs` with
  owner-specific finite choices. Independent outputs have neither extra field.
- Lowering copies explicit declarations and member references into two program
  maps, `relationship_declarations` and `relationship_bindings`. It does not infer
  declarations, copy one member's local basis or rewrite source evidence.
- Ready members need a nonblank declaration and every owned reference exactly
  once. All-abstaining groups may declare null; no fabricated common explanation
  is needed. Overlapping groups keep independent declarations.
- Numeric members still need their own source interpretation, including when
  only another member declares the relationship. Narrative subject/fact support,
  owner visibility, known consolidated/separate source conflicts, period/source
  conditions, arithmetic and physical-row checks remain independent.
- Partial retry freezes every declaration used by an accepted, unretried output.
  The prompt exposes it read-only and the generated schema omits that declaration.
  Only targeted outputs and editable declarations change. Reference-format repair
  retains the candidates; accepted output/proof bytes remain intact.
- V2 program and validation fingerprints bind both proof maps. Query, program
  and accepted-proof tampering still fail closed. Source linkage and declared
  agreement do not establish correct semantic interpretation.

## Verification

The [local packet](../../benchmarks/results/shared_basis_declarations_2026-09-17/)
contains socket-blocked test receipts and original-response compatibility checks.

| Check | Result |
| --- | --- |
| New schema/lowering/retry/execution controls | 16/16 |
| Focused contracts | 180/180 |
| Offline replay/debug regression checks | 43/43 |
| Independent narrative review/admission checks | 7/7 |
| Final relationship/source-proof checks | 33/33 |
| Final full integration suite | 1,968/1,968; no skips |
| Runtime domain-language audit | 83 reviewed literals, pass |
| Documentation authority | 2/2 |
| Actual provider/count calls and external test connections | 0 |

Controls cover different local basis texts, direct/derived/narrative outputs,
overlapping groups, abstention, partial retry, frozen declarations, foreign or
missing references, mandatory local source proofs and V2 tampering. Authored
fixture successors only copy explicitly authored proofs; they are not sampled
model responses. Historical fixture JSON remains untouched.

The first integration run exposed dropped proof maps in the offline rehearsal
projection and dropped empty map keys during targeted retry. A later failure
came from an authored independent case retaining its removed relationship's
proofs. Those paths now preserve the intended contracts. Final review also
reproduced a missing local numeric proof when only another member declared the
relationship; validation now checks all members of the grounded relationship.

## Saved responses and limits

All four prior Compiler source payloads and active obligations round-trip
exactly from each run's own diagnostics. Original model/program hashes verify.
The three related historical replies lack the new explicit fields and are
rejected by the current schema/validator; the independent certification reply
remains ready. No response, historical answer or old result is rewritten.

The implementation changes nine of 172 source files. Final integrity verification
checks 1,451 predecessor files, local settings and 24 original/selected store files.
No real store client, ingest, paid retry, new model sample or execution admission.
Shared accounting remains USD **7.08344260 / 8**, remaining **0.91655740**, pending 0;
it includes count contingency and is not an invoice or verified count tariff.

This completes the provider-free representation change. It does not establish
live provider schema acceptance, fewer model repairs, unseen-question accuracy,
latency or token savings. The previous known-source budget successor remains
evidence for its earlier build only. Next bounded work is to freeze a small unseen,
source-backed control set and assess the current schema and remaining budget for
a later bounded live evaluation. No further paid execution is scheduled here.
