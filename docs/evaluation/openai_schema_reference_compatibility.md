# Annotated OpenAI schema reference compatibility

Provider-free correction from clean **`e88cdcbf`**, 2026-09-22, following the
[one-count schema rejection](planner_count_error_probe_result.md). One generic
transport owner changes: `src/utils/openai_structured.py`. No Planner meaning,
period field, prompt, model, output limit, source selection or arithmetic changes.

## Reproduced compatibility gap

The submitted Planner schema contains one annotated reference:

```json
{
  "$ref": "#/$defs/PlannerMeasurementPeriod",
  "description": "...",
  "title": "Measurement Period"
}
```

Its location is `PlannerAnswerObligationScope.properties.measurement_period`.
The preceding accepted five-count/five-generation schema contains zero references
with sibling fields. The new period declaration introduced this one occurrence.
Ordinary JSON Schema validity and closed-object/required/reference checks did not
identify it as a transport problem.

The installed **OpenAI Python SDK2.29.0**, `openai/lib/_pydantic.py:95–115`,
explicitly expands references with sibling properties before strict transport.
Its inspected source and SHA256 are preserved in the ignored packet. The
[official schema guide](https://developers.openai.com/api/docs/guides/structured-outputs#supported-schemas)
documents a supported subset, including definitions and recursive references;
general JSON Schema validity alone does not establish API acceptance.

The project wrapper had bypassed that SDK transformation by binding its own
strict dictionary schema. The missing transformation is reproduced locally and
corrected. The saved provider response names only `text.format.schema`; its
missing detailed message means this is **not proof of the sole historical400
cause**, and no corrected request has been sent to the provider.

## Exact transformation and validation

Only local `$ref` objects whose remaining fields are `title` and/or `description`
are expanded. The target is deep-copied; use-specific annotations override only
annotations. The existing strict conversion still removes default annotations,
requires every object property and preserves all value constraints.

Pure references and definitions remain, including bare recursive references.
Escaped JSON pointer names (`~0`, `~1`), arrays, unions and reference chains are
handled. Sibling validation keywords are rejected rather than merged: overriding
a referenced minimum, type, enum or required list could discard a constraint.
Unresolved/nonlocal pointers, invalid escapes, non-schema targets and cyclic
annotation expansion also fail before a request. Existing unsupported composition
and open-dictionary rejection remain intact. The original input schema and
Pydantic response validator are unchanged; no response repair is introduced.

For the actual Planner schema, the result matches the native SDK strict
projection after applying the project's pre-existing default-removal policy.
The old period definition remains available; its inline copy retains all seven
required fields, nullability, enums, integer bounds, date patterns and exact
descriptions. Only that reference location changes in the four frozen bodies.

## Verification

- **12 new regression tests** cover SDK parity, annotation override without
  shared-object mutation, equivalent accepted/rejected values, arrays/unions,
  escaped and chained refs, ambiguous validation siblings, invalid targets,
  cycles, bare recursive refs and real-SDK mock rejection of invalid values.
- **109 focused tests**, **26 public/import/topology boundary tests**, full
  **2267/2267**, documentation2, domain audit **83**, syntax and diff
  gates pass. The new tests reproduce the old gap before the fix. Two existing
  tests now inspect the expanded period fields and retain missing/null rejection;
  no field or runtime requirement is weakened to pass them.
- The before capture reproduces all **8 historical mock requests** exactly.
  Two fresh-process after captures use four count and four generation mocks
  each. All **4 normalized plans** and authored responses are unchanged; all
  **15 files** from the two after processes are byte-identical.
- **58 comparison assertions** verify a single expected schema substitution,
  unchanged model/input/prompt/control fields, exact count projections and SDK
  parity. Generation bodies increase by **2,167 UTF-8 bytes** each:
  **40,523–42,138 → 42,690–44,305**. No real token usage was measured.
- All **14,068 predecessor files**, **176 unrelated production sources**, **24
  original stores** and local settings retain hashes. Source count remains177.
  Experiments stay in `benchmarks/results/planner_schema_compatibility_2026-09-22`;
  only the source owner, three test files and seven documents are committed.

The initial focused pass exposed one further test expecting a literal reference;
its field-shape assertion was updated without altering the rejection cases.
An initial full-test invocation stopped during discovery because the tests folder
is a namespace package; the corrected gate uses the established repository
discovery convention. Both earlier logs remain preserved.

Added provider calls, model samples, paid authority and accounting are **0**.
Shared accounting remains **USD19.75502393/20.32**, available **0.56497607**,
pending0. The two old count manifests remain consumed; original HTTP400 records
and unassessed Planner meanings are unchanged. Historical periods2/6 and scopes6/6
are not improved by authored responses.

The subsequent [one-count verification](planner_corrected_schema_count_result.md)
succeeded with HTTP200 and8417 measured input tokens on clean `5fb9558c`.
Its fresh manifest is consumed, with zero generations and USD0.01 contingency.
That result establishes count-endpoint acceptance only. A later
[single-question generation](planner_single_generation_result.md) also completed
with a valid plan and sampled period/scope1/1. These later observations remain
separate from the zero-call local correction above; broad accuracy and the
sole historical error cause are not established.
