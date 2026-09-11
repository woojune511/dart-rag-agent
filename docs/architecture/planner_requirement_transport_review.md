# Planner requirement transport review

Status: request-original preservation implemented, 2026-09-12. The earlier
planner-only measurement remains bound to runtime `222ffba9`. The separate
[three-case pipeline](../../benchmarks/results/request_unit_pipeline_2026-09-12/RESULTS.md)
met its fixed source criteria on runtime `27fd6819`; semantic overlap remains characterized
in the [output partition review](narrative_output_partition_review.md). Its later planner-only
policy clarification is locally tested, not a new model result.

This review separates model interpretation from code transport. The new field and
prompt contract below supersede label-only ownership, not evidence validation.

## Current implementation

- Code partitions the exact query at mechanical sentence/line boundaries. Stable
  `request_001`-style IDs, text and string spans survive without normalization or truncation.
  These are addresses, not semantic clauses; an abbreviation may cross several units.
- The planner assigns required `request_unit_ids` to every output. Units can be
  shared; unit count does not dictate output count. Labels remain short names and
  referenced original text supplies details instead of relying on rationale.
- Missing/unknown/malformed references and unassigned units are explicit requirements
  errors. The full query is checked before any compiler call, with no automatic
  assignment, planner retry or candidate exclusion. Old compiler-only inputs need
  explicit new assignments; historical artifacts are not retroactively migrated.
- Every initial/retry compiler scope projects only active owners' linked text, in
  query order. The full original question remains context. Shared references do not
  couple islands or affect rankings. Candidate IDs/payload identity, program schema,
  scope/quote validation, call/retry caps and accepted-output bytes are unchanged.
- Request text is an instruction surface, never source evidence. The existing V2
  content fingerprint binds both original query and owner references through execution.

This guarantees lossless transport and structural ownership, **not correct semantic
assignment or fulfillment**. The route-only negative control below remains structural
`ok` even with the full request linked. No keyword completeness gate or extra judge.

Verification uses anonymous contract/pipeline tests plus the full local suite. Old
planner-free fixtures receive explicitly authored whole-question assignments only in
temporary test copies; sources/programs/expected outcomes and frozen bytes stay intact.
These copies are not new planner output or evidence of improved answers. Current
counts are recorded in [project status](../overview/project_status.md).

## Pre-change findings

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

The earlier seven-question compiler comparison declared **planner_calls=0** and used fixed
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

At the pre-change boundary, focused tests **55/55**; import/boundary/topology/docs/audit
**30/30**; domain audit **83 reviewed literals**, no new exception. Pycompile and diff
checks passed. That transport review did not change runtime/policy/schema; its last
full gate was **1383/1383** on `222ffba9`, not the current implementation gate.

## Actual planner output, separate from transport

[Six-question result](../../benchmarks/results/planner_semantics_2026-09-12/RESULTS.md)
consumed `f78ee9d1...bf20d` once on clean `ad1031a5`: default Flash, six calls, no
retry/error, USD 0.0290838 estimated / 0.20 cap; billing unobserved. No compiler,
retrieval, embeddings, source transmission or store mutation. Controls/criteria
were fixed before calls and withheld from the planner.

All six plans are structurally `ok`, but fixed-criterion Codex field review finds
two retained, one missing qualifier and three partial/ambiguous outputs. PLAN_02
mentions uncertain whole-group applicability in rationale, not its required label.
PLAN_03/05/06 retain general applicability but weaken the explicit uncertainty
condition; PLAN_04 retains limits in both labels. Labels/inputs are not required to
use exact words or a fixed decomposition. One sample cannot attribute differences
to presentation or establish general failure rates.

On the measured predecessor, all six saved SDK responses parse identically; complete requirements phases and
prompts replay byte-identically without provider calls. No code-side qualifier loss
was found. All 156 runtime and 161 predecessor files remain unchanged. The original
question remains a compiler input; no downstream answer failure is proven.

The later three-case synthetic pipeline retained actual assignments and fulfilled its
fixed conditions, with separate Codex source review and unchanged raw-response replay.
Its third answer repeats conditions across outputs. The bounded decomposition policy is
now explicit in the planner prompt, without source-ID dedupe or another paid run.
Local ownership checks remain distinct from an answer-quality score.

A later compiler comparison must separately identify changed source layouts, supplied
requirements and model outputs. Neither new cell metadata nor this transport review
repairs historical stores or improves an already recorded answer. The admission is
consumed; no automatic rerun, store mutation or source reingest is authorized.
