# Request, reading and execution boundary

Baseline: `d9c36d8d`. Approved implementation uses the existing planner/compiler
calls, preserving source stores, physical IDs, units and public results.

## Independent controls

`tests/fixtures/request_source_semantic_controls.json` was frozen before runtime
edits, SHA-256 `6abc1b5687f435bb18c622488c506d0864e1ae967e47540f4e3045bcbb541dc1`.
Six pairs distinguish wrappers, descendants, periods, heading/body attribution,
consolidation and source/calculated displays, including equal-valued distractors.
These are semantic review controls, not runtime policy or provider-free model
accuracy. Both questions in each pair must be assessed separately in any future
approved provider experiment. Existing benchmark questions are regressions only.

## Source authority

Ranking allocates prompt space. Source conditions decide use of the visible
union. Owners with identical source conditions share that union, even when
their topics differ. Different sections, numeric periods, filings, explicit
unit conflicts and retry exclusions do not share authority. Physical-row
atomicity remains enforced independently. Raw catalogs and request conditions
are never changed by the projection.

Validation of provenance and arithmetic does not certify semantic relevance.
No paid run, fresh ingest or source mutation is part of this implementation.

## Production and offline interfaces

`CompilerResponseV2` has one required key per active output, with only that kind's
result schema. Numeric inputs and narrative support/facts nest under requirement
keys; source addresses are short, stable and exactly reversible. Ranking matches
are absent from the payload. `lower_compiler_response` resolves addresses and
assembles the internal program without inferring choices or missing proof.
Source-linked interpretation and the lowered program are bound by V2 fingerprints.
The selected cell supplies its full axes without model-written axis IDs. Outside
context is quoted once with explicit interpretation/scope uses; the context field
and finite addresses exist only for inputs with exposed numeric attachments.
Lowering assembles internal proofs, retaining exact attachment/quote/partition checks.

`OutputRelationshipV1` requires a shared exact request excerpt owned by all members.
It does not replace declared dependencies or physical-row constraints. Format,
reference and correspondence errors keep evidence; only hard source/dimension
conflicts replace bundles. Accepted program/proof bytes survive targeted repair.

Old fixture files remain immutable. Explicit offline copies add authored request
assignments, relationships and source proofs; the offline wire adapter only
rearranges those existing choices. It is not a production fallback or a model judge.

## Earlier provider-free boundary comparison

The same five reviewed cases were rehearsed at `d9c36d8d` in a temporary clean
worktree and in the current implementation using their respective explicit fixture
transport. Network sockets were blocked. Questions, selected IDs and numeric/display
outputs were retained; current request/proof fields were authored, not model-generated.

| Metric | Baseline | Boundary build before numeric-transport cleanup |
| --- | ---: | ---: |
| Authored cases accepted | 5 | 5 |
| Mock Compiler calls / retries | 6 / 0 | 6 / 0 |
| Prompt UTF-8 bytes | 208,427 | 134,135 |
| Schema UTF-8 bytes, summed per call | 59,832 | 37,115 |
| Provider calls / store writes | 0 | 0 |

Output signature in both runs:
`2ca7903e16772081eb5bed50489e7ce982fc83e020521b586983a200ab5880d5`.
That boundary build's prompt fingerprint:
`ffe814f1c7defd08f24fcd6481b49a948d2b496b81486ab826fcf55091bb18d0`.
These are local compact schema/prompt serializations, not final SDK bytes, measured
tokens, billing or latency. Schema sizes per call: 6,619 / 8,267 / 6,872 / 6,754 /
2,718 / 5,885 bytes, versus six 9,972-byte baseline schemas.

## What the gates do and do not show

- [Authority tests](../../tests/test_candidate_authority_projection.py): same-source
  requirement sharing, hard section/filing/period separation, retry exclusions.
- [Source interpretation](../../tests/test_source_interpretation.py): wrapper-to-axis
  execution, complete own axes, connected headings, foreign-source rejection and
  proof-tampering failure. A plausible but wrong meaning can still pass linkage.
- [Typed transport](../../tests/test_compiler_wire.py): no narrative formula, no hidden
  or foreign-owner address, dependency/input separation and stable ref conversion.
- [Numeric contrasts](../../tests/test_numeric_subject_authority.py): former literal
  mismatch tests separate required proof/physical violations from wrong-meaning
  controls. Full entity scope is not mechanically certified by exact source linkage.
- Existing unit/sign/display, physical-row, atomic capacity, immutable retry,
  public answer/ledger and storage tests remain independent regression gates.

Unnecessary literal rejection is removed for authored source-linked wrapper cases;
this is not a measured false-rejection rate on real model outputs. Further experiments
must retain all frozen pairs, equal-valued distractors and named regressions separately,
reporting structural failures, semantic failures, retries and SDK sizes without one blended score.

The subsequent [delegated one-shot probe](../../benchmarks/results/request_source_boundary_compiler_2026-09-14_v2/RESULTS.md)
completed nine of twelve model cases: seven accepted/source-reviewed correct, one
over-abstention, and one reverse-direction error in a structurally invalid draft.
A Google token-count 404 interrupted question ten; two were unattempted. Five
questions required repair of redundant invalid context references. This shows
remaining transport and semantic errors; it does not justify relaxing source checks.
The unattempted source-display pair also lacked bare-quantity candidates before
the run. The [user-requested interrupted-question successor](../../benchmarks/results/request_source_boundary_remaining_2026-09-14/RESULTS.md)
then completed count/generation on unchanged source bytes, but invalid context fields
still prevented acceptance. This was one bounded continuation, not an automatic retry.
Subsequent catalog-only bare-scalar exposure preserves old member identities and
shared evaluation behavior. Source-display local witnesses now execute the actually
extracted operands without injection; they are not sampled model answers.

Earlier numeric-transport integration gate: Python 3.13, 1,672 tests without skips; focused
numeric-transport/source/retry/compiler/admission 97, import/topology/docs 24, domain audit 83 reviewed
literals, pycompile and clean diff check. No provider
execution or release acceptance is claimed by these gates.

Numeric V2 contracts additionally reject unavailable context fields/addresses,
foreign attachments, altered quotes and ungrounded legacy fixture axes. A single
quote can explicitly support interpretation and resolve scope, without promoting
scope-only context to subject evidence. The selected cell's full axes are assembled
deterministically; meaning remains the Compiler's decision. See
[transport regressions](../../tests/test_numeric_compiler_grounding.py).

The [numeric transport model successor](../../benchmarks/results/numeric_grounding_compiler_2026-09-15/RESULTS.md)
on `51330fe5` ran three synthetic questions once: source/execution 3/3, separate
Codex source-semantic review 2/3, retries 0. The separate-row lookup and source-plus-
calculation request succeed. Calculation-only still incorrectly selects a source
display even though its forward arithmetic is correct. This is a preserved semantic
negative, not a reason to relabel acceptance or add a literal intent gate.
Subsequent numeric instructions and existing nullable-field descriptions explicitly
prioritize request intent over source-first defaults. Calculation-only chooses null;
the reason connects the decision to the request, not just availability of a report.
No new enum, field, prompt-time classifier, call or execution repair was introduced.
Six local contracts preserve exact requested text on initial/retry calls, unchanged
candidate authority, actual normalization through final answer/ledger, direct source
precision and tamper rejection. A wrong authored selection remains structurally valid
and semantically wrong; no keyword gate pretends to prove interpretation.
The prior paid failure is unchanged. The [display-intent successor](../../benchmarks/results/display_intent_compiler_2026-09-15/RESULTS.md)
on `a2d89d40` subsequently ran the unchanged pair once: source/execution **2/2**,
separate Codex source-semantic review **2/2**, two generations/counts, no retries.
The raw model now selects null source display for calculation-only, preserving
11.5%/10% when both are requested. No lowering repair or changed criterion.
Focused 39/39 and two byte-identical no-call rehearsals preceded this run; its
implementation integration gate was 1,678/1,678. The effect of individual instruction
components is not isolated, and one exposed pair is not general accuracy evidence.
No context-rich, full-agent or general retry reduction claim; both manifests consumed.

The later [provider-free numeric-reading replay](../../benchmarks/results/numeric_reading_intent_2026-09-15/RESULTS.md)
separates reverse-direction semantics from retired invalid context fields, and
explicit parent-row availability from model-conjectured aggregation. Correctly
authored selections/formulas execute without a source or arithmetic gate change.
Numeric instructions now resolve requested reference/target before direction and
distinguish row lookup from aggregation. Genuine gaps/ambiguity remain valid;
no answer forcing, new schema field, extra call or code-side semantic correction.
Seven new contracts and 104 focused / 24 import/topology/docs tests pass. Before/after
program/schema/authority bytes and mock call counts are unchanged; prompt strings
grow 1,012 local JSON bytes per invocation. Provider calls 0; model effect unmeasured.
