# Planner requirement transport review

Status: provider-free characterization, 2026-09-12. Runtime baseline `222ffba9`.

This review separates model interpretation from code transport. It does not introduce
new planner fields, qualifier keywords, semantic validators, prompt changes or calls.

## Findings

No mechanical loss of the supplied subjects, group distinctions or uncertainty text
was reproduced between a typed planner response and the compiler prompt:

- The planner receives the complete original question, even when routing `topic` is
  a short summary or the requested presentation/intent changes.
- Declared output/input labels are whitespace-normalized, not shortened. Complete
  local names, scope, section restrictions and required flags survive stable-ID
  projection, retrieval inputs, compiler inputs and island-specific serialization.
- A `source_defined_group` output copies its full label, target, scope and hints into
  one required evidence input. Code does not invent the group's members.
- Internal retry retains the targeted requirements and original question, without
  resending or changing a different accepted island's output.

There is a separate open semantic limit. If the model initially returns only a broad
label such as “Describe routes”, code cannot reconstruct an omitted group distinction
or uncertainty requirement from that label. Rationale remains diagnostic, not a
replacement for declared output/input fields. The original question is still visible
to the compiler, so omission from structured fields does not remove it from the prompt.

An explicitly authored negative control requests routes, whole-group distinction and
uncertain attribution but supplies a shortened planner response and route-only compiler
answer. The real graph reaches public `structured_result.status=ok` for the declared
output. This demonstrates that structural readiness is not complete question coverage;
it does **not** establish that a real planner generated this omission.

The latest seven-question paid comparison declared **planner_calls=0** and used fixed
agent-authored obligations. Its observed subject/scope/uncertainty failures cannot be
attributed to planner execution. Complete questions were nevertheless compiler input.

## Evidence and limits

Six new tests in `tests/test_planner_requirement_transport.py` use anonymous English
and Korean subjects, long labels, alternate intents/presentations, source-defined
groups, actual phase projections, an island retry and the real graph with mocked
retrieval/model responses. The negative control is an open-limit characterization,
not an expected good answer, benchmark label or semantic acceptance oracle.

[Socket-blocked captures and receipt](../../benchmarks/results/planner_requirement_transport_2026-09-12/README.md)
record nine authored planner responses and four authored compiler responses. Provider
calls are zero; all 156 runtime files and 157 protected predecessor files are unchanged.
The recorded prompts establish transport only, not the model's ability to produce the
authored requirements, retrieval quality, full-agent success or generalization.

Focused tests **55/55** (including the six new tests); import/boundary/topology/docs/audit
**30/30**; domain audit **83 reviewed literals**, no new exception. Pycompile and diff
checks pass. Runtime/policy/schema did not change, so the previous full gate remains
**1383/1383** on `222ffba9`; no new full-suite run or new full-suite count is claimed.

## Next decision

[Six-question planner-only admission](../../benchmarks/results/planner_semantics_2026-09-12/README.md)
is prepared from `72951f1b`, not executed: current default Flash, three paired
anonymous contrasts, fixed semantic criteria kept outside model input, six calls at
most, USD 0.20 cap. Manifest `f78ee9d1...bf20d` awaits explicit approval. Two independent
network-blocked SDK receipts are byte-identical; admission checks 8/8 and existing
planning/provider tests 26/26 pass. No runtime change, source transmission or semantic
measurement occurred. Inspect actual returned fields separately from faithful
transport; do not add a qualifier enum or keyword coverage rule from authored stubs.

A later compiler comparison must separately identify changed source layouts, supplied
requirements and model outputs. Neither new cell metadata nor this transport review
repairs historical stores or improves an already recorded answer. No paid admission,
automatic rerun, store mutation or source reingest is authorized by this review.
