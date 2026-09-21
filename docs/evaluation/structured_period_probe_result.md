# Structured measurement-period eight-question live result

On 2026-09-21, the user accepted the proposed **USD 0.25** addition and actual
execution of the [prepared probe](structured_period_probe_preparation.md).
The shared experimental allowance rose from **20.07 to 20.32**, making **1.30143757**
available before the run. The run cap stayed **1.27**. This is an accounting
allowance, not an API credit purchase or an invoice.

All eight first responses completed with valid structured periods. Separate
assistant review accepts **8/8 measurement interpretations and 4/4 period pairs**.
However, the two comparison plans broaden the selected report's year filter:
**selected-report scope passes 6/8; combined period/report checks pass 6/8 and
3/4 pairs**. This is not an all-pass experiment or a full-app result.

## What the model returned

| Case | Operative measurement constraint | Period review | Selected-report scope |
| --- | --- | --- | --- |
| p01 | `unspecified`, blank free period | Pass | 2037 only |
| p02 | `year: 2037`, linked to the explicit restriction | Pass | 2037 only |
| p03 | Inclusive 2036-07-01 through 2037-06-30, actual cumulative basis | Pass | 2037 only |
| p04 | Inclusive 2037-07-01 through 2038-06-30, actual cumulative basis | Pass | 2037 only |
| p05 | `relative_year`: anchor 2037, offset -1; target 2036 | Pass | 2037 only |
| p06 | `year: 2037`, linked to the current-year definition | Pass | 2037 only |
| p07 | Separate 2035/2036 inputs, 2035 reference, forward direction | Pass | **Fail: includes 2035/2036** |
| p08 | Separate 2036/2035 inputs, 2036 reference, reverse direction | Pass | **Fail: includes 2035/2036** |

Raw and normalized operative periods were reviewed separately against the frozen
criteria. p05's relative form and p06's resolved year are permitted equivalents.
Both comparison parents declare an unresolved composite period while their
children have separate executable years; the exact reference instructions remain
owned. Structural request linkage does not certify semantic interpretation, and
no Compiler endpoint selection or arithmetic was performed.

## Confirmed report-scope defect

For p07/p08, raw Planner `years` is `[2035, 2036]`. The unchanged normalization
merges it with the explicit caller year to produce `[2037, 2035, 2036]`.
Provider-free replay of the exact saved plans through `retrieval_phase_input`
and `_build_scope_plan` produces this metadata condition:

```json
{"$and":[{"company":"가상기업 A"},{"year":{"$in":[2037,2035,2036]}},{"report_type":"사업보고서"}]}
```

The original request still selects only the 2037 annual report. The six other
plans produce a single-year 2037 filter. **25 offline assertions reproduce the
finding** and verify unchanged inputs. They establish filter construction, not
that an out-of-report source was actually retrieved: no search/store was opened.

The saved-evidence review retains **106/108 passing checks and these two genuine
failures**. No criterion, response, normalized plan or runtime code was rewritten
to make them pass during this probe. The subsequent [report-year scope correction](report_year_scope.md)
changes only the source-filter boundary and verifies the same saved plans against
authored metadata: local filter acceptance is 8/8. This probe's paid 6/8 result
and two failures remain unchanged; no new provider or full-app result is implied.

## Admission, usage and preserved evidence

Clean source `209f396e`; fresh manifest
`574dee6e6367bd12842afe0beda0b793f6d101777a3b5501bf1979d80966f016`
was consumed once before transport. Exact questions, prompt/schema, ontology and
SDK bodies match preparation. The profile stays Terra/low, 8,192 maximum output,
20,000 input guard, `store=false`, default service tier and zero retries. Supplied
numeric routing and empty inventories isolate Planner interpretation. Saved
answers and criteria cannot be read during generation.

Two fresh-process caller rehearsals reproduce all eight prepared requests and
authored plans. **36 caller controls** pass, including changed requests, funding,
history-read denial and provider failure stops. Separate missing-authority and
consumed-manifest checks prevent transport construction. Existing source tests
from preparation remain unchanged; documentation **2/2** and syntax/diff checks pass.

All **16 actual requests returned HTTP 200**: eight counts and eight generations.
There were zero provider, parsing or requirement-validation errors, SDK retries,
whole-question retries or semantic repairs. Every counted input equals its
generation's reported input usage. The run and final integrity check took about
79 seconds, with 30-second heartbeats.

| Accounting item | Value |
| --- | ---: |
| Input tokens | 63,015 |
| Output tokens, including 861 reasoning tokens | 4,995 |
| Generation estimate | USD 0.21747750 |
| Eight count contingencies | USD 0.08000000 |
| Added accounting | **USD 0.29747750** |
| Shared accounting / allowance | **19.31603993 / 20.32** |
| Remaining / pending | **1.00396007 / 0** |
| Peak run accounting including reservations | USD 0.38241350 / 1.27 |

[Official pricing](https://developers.openai.com/api/docs/pricing) was searched
and fetched on 2026-09-21. Conservative input/output accounting remains USD
2.50/12 per million tokens with no cache discount. Count contingencies are not
a verified count tariff; prior failed reserves remain. No invoice is observed.

All **12,009 protected predecessor files**, **176 source files**, **24 original
store files** and local settings retain hashes. Only documentation is committed;
the new ignored packet is `structured_period_probe_execution_2026-09-21`.
Prior paid Planner and partial app results remain unchanged. No ingest or new
source availability/general accuracy claim is made. These are known synthetic
questions, not a blinded holdout, independent human gold or an A/B effect.
p03's rationale says the value can be checked in the source; without supplied
source evidence that availability claim remains unverified diagnostic prose.

Local evidence: [run receipt](../../benchmarks/results/structured_period_probe_execution_2026-09-21/live/run_receipt.json),
[semantic review](../../benchmarks/results/structured_period_probe_execution_2026-09-21/semantic_review.json),
[two retained failures](../../benchmarks/results/structured_period_probe_execution_2026-09-21/live_review.json),
[scope reproduction](../../benchmarks/results/structured_period_probe_execution_2026-09-21/document_scope_review.json),
[accounting](../../benchmarks/results/structured_period_probe_execution_2026-09-21/accounting.json).
