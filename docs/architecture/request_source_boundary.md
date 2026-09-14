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

`CompilerResponseV1` has one required key per active output, with only that kind's
result schema. Numeric inputs and narrative support/facts nest under requirement
keys; source addresses are short, stable and exactly reversible. Ranking matches
are absent from the payload. `lower_compiler_response` resolves addresses and
assembles the internal program without inferring choices or missing proof.
Source-linked interpretation and the lowered program are bound by V2 fingerprints.

`OutputRelationshipV1` requires a shared exact request excerpt owned by all members.
It does not replace declared dependencies or physical-row constraints. Format,
reference and correspondence errors keep evidence; only hard source/dimension
conflicts replace bundles. Accepted program/proof bytes survive targeted repair.

Old fixture files remain immutable. Explicit offline copies add authored request
assignments, relationships and source proofs; the offline wire adapter only
rearranges those existing choices. It is not a production fallback or a model judge.

## Provider-free comparison

The same five reviewed cases were rehearsed at `d9c36d8d` in a temporary clean
worktree and in the current implementation using their respective explicit fixture
transport. Network sockets were blocked. Questions, selected IDs and numeric/display
outputs were retained; current request/proof fields were authored, not model-generated.

| Metric | Baseline | Current |
| --- | ---: | ---: |
| Authored cases accepted | 5 | 5 |
| Mock Compiler calls / retries | 6 / 0 | 6 / 0 |
| Prompt UTF-8 bytes | 208,427 | 134,135 |
| Schema UTF-8 bytes, summed per call | 59,832 | 37,115 |
| Provider calls / store writes | 0 | 0 |

Output signature in both runs:
`2ca7903e16772081eb5bed50489e7ce982fc83e020521b586983a200ab5880d5`.
Current prompt fingerprint:
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
this is not a measured false-rejection rate on real model outputs. Semantic error
rate remains unmeasured. A separately approved experiment must assess all frozen
anonymous pairs, equal-valued distractors and named regressions separately, retaining
structural failures, semantic failures, retries and SDK sizes without one blended score.

Local integration gate: Python 3.13, 1,650 tests passed without skips; focused
118 + reading cleanup 20, import/topology/docs 24, domain audit 83 reviewed
literals, pycompile 70 changed Python files and clean diff check. No provider
execution or release acceptance is claimed by these gates.
