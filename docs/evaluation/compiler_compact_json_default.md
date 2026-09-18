# Compact JSON as the Compiler default

The user approved default adoption after the
[comparison](compiler_compact_json_transfer_comparison.md) and
[public-trace correction](compiler_display_format_boundary.md).
Starting from clean `23e8ef8d`, the same **466-character serialization instruction**
now prefixes both Compiler templates, including initial and targeted retry calls.
The only production change is `src/config/retrieval_policy.py`.

## Behavior

Numeric, mixed and narrative Compiler responses are instructed to omit optional
whitespace outside JSON strings. Every required field, output, claim, qualification
and evidence reference remains required. Exact quotation spaces, tabs, line breaks
and punctuation inside strings must be preserved; content must not be shortened.

This is a generation instruction. JSON parsing still accepts both pretty and
compact valid responses. There is no output minifier, whitespace rejection gate,
new retry, schema/model/budget change, Planner instruction change or source rewrite.
The previous public-trace separation remains in force.

The shared instruction is provider-independent; current application defaults use
the existing OpenAI profile. This adoption does not assert new provider compliance.
To roll back the policy, remove its concatenation from `_COMPILER_SHARED_INSTRUCTIONS`;
no store, schema or settings migration is required.

## Provider-free verification

The [local packet](../../benchmarks/results/compiler_compact_json_default_2026-09-18/)
captures the baseline policy and replays the four prior sampled replies before and
after adoption. For each case, the actual new prompt equals the old prompt plus
the exact approved prefix; the entire remaining policy dictionary is unchanged.

| Check | Result |
| --- | --- |
| Saved replies / runtime outputs | 4 / 6 on both versions |
| API payloads across all review/debug options | 16 byte-identical pairs, all HTTP 200 |
| Canonical program, validation, execution, final answer and ledger | 20 byte-identical pairs |
| Strict schemas | 4 byte-identical pairs |
| Production SDK requests versus frozen candidate requests | 32/32 equal |
| Authored positive combinations | 16/16, eight cases with pretty and compact replies |
| Invalid transport/source/formula combinations | 14/14 rejected |
| Deliberately false, source-linked narrative readings | 2 still structurally accepted; semantic boundary retained |

The actual installed SDK is used with mocked HTTP and blocked external connections.
Controls cover units, signs, display/dependency values, request quantities, multiline
quotes, narrative and mixed outputs, invalid source refs, inexact quotes, missing
proof/output, invalid step references, incomplete status, refusal and truncated JSON.
Original source/query strings and authored response text stay unchanged.

Three new contracts cover the reviewed instruction and numeric/mixed/narrative
initial/retry paths, exact source whitespace and accepted numeric output preservation.
Focused **39/39**, execution/source/public/ledger **45/45**, and import/topology/docs
**24/24** pass: **108 tests**, plus the separate 32 mocked SDK controls. Runtime
domain audit passes with **83 reviewed literals**. The full suite was not rerun.
During test authoring, the synthetic request was kept within its declared request
unit and quote assertions were aligned with the existing addressed-source contract;
runtime contracts were not weakened to accommodate those fixture errors.

## Cost, preservation and claim limits

All **8,683 predecessor files**, seven runtime owners, 24 original store files and
local settings retain hashes. Of 174 source files, only the policy changes; 173
remain unchanged. Raw sampled responses and historical paid results stay immutable.

Provider/count/embedding calls and added accounting are **zero**. Shared accounting
remains **USD 14.10619659 / 15**, remaining **0.89380341**, pending zero; these are
estimates and contingencies, not invoices. No new paid admission was created.

The prior two-case sample measured 13.19% and 23.21% fewer total output tokens with
83 extra input tokens per case. Rationale/reasoning/wording also differed, so those
reductions are neither pure whitespace attribution nor guaranteed future savings.
Stored responses and authored controls do not measure new model behavior or accuracy.
A future live application check requires a fresh funded admission; consumed manifests
remain consumed. The policy is now enabled without another configuration step.
