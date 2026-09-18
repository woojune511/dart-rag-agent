# Two-case v11 Compiler API probe

Executed 2026-09-19 from clean `f67b0ccf`, following the
[frozen preparation](compiler_axis_probe_preparation.md). Both first responses
pass the original schema, source-lowering and deterministic execution contracts.
Separate assistant source review passes both frozen criteria: calculated Commerce
growth and acquisition impact. **This is a Compiler-only result for two parts of
one known-source question; no fresh application answer was assembled or delivered.**

## Results

| Case | Count / generation input tokens | Output tokens | Included reasoning | Runtime / source review |
| --- | ---: | ---: | ---: | --- |
| Numeric | 23,664 | 911 | 163 | Pass / pass |
| Narrative | 17,372 | 1,449 | 346 | Pass / pass |

All four transmissions returned HTTP 200: two counts and two generations. Both
count results equal the corresponding generation usage. There were no provider,
parsing or source-contract errors, incomplete responses, repairs, SDK/HTTP retries
or whole-run retries. Both raw outputs contain **zero whitespace outside JSON
strings**. Source quotations and required content remain intact.

Numeric selection preserves the original 2023/2022 Commerce revenue cells:
2,546,648,516 / 1,801,079,126 thousand KRW. Both retain the complete revenue-row
and Commerce-column paths, physical cell provenance and attached period
evidence (original quotes `당기` / `전기`). The 2022 value is the reference
and denominator; the 2023 value is the target. Independent decimal arithmetic
gives **41.39570434397450231734016554%**; deterministic output is **41.4%**.
Source display is null, respecting the calculation request. Raw model format
metadata is `0.00`; existing execution renders 41.4%. No precision was requested,
so this is not a failure of the frozen criterion or proof of general format support.

Narrative review checks **three claims and seven subject/fact support occurrences**
against their exact original source spans:

- January 2023 acquisition of 100% of Poshmark voting shares and the North American
  C2C expansion purpose are supported by the acquisition note. Purpose remains
  separate from realized financial performance.
- The direct Commerce paragraph supports 41.4% growth and 2조 5,466억원 revenue,
  alongside Poshmark restructuring, Smart Store and Brand Store growth. The reply
  retains the other drivers and does not attribute all growth to the acquisition.
- Post-acquisition revenue 473,849백만원 and net loss 19,063백만원 belong to
  Poshmark and its subsidiaries, as included in the consolidated income statement.
  The reply preserves that scope and period, without assigning the loss to the
  entire Commerce segment or presenting hypothetical full-year figures as actuals.

These are assistant judgments about known evidence, not human gold, unseen
accuracy, or a result inferred from successful source linkage alone.

## Input observations and cost

Historical counts for the original saved requests were 26,131 / 17,529. The new
v11 counts are lower by **2,467 (9.4409%) / 157 (0.8957%)** respectively. This is a
descriptive comparison with historical measurements; there is no newly run
baseline arm, isolated causal A/B result, general efficiency claim or verified
invoice saving. Request bytes remain 89,817 / 65,090. The former preparation's
7.6992% / 0.5455% byte reductions remain distinct from token measurements.

The user approved **+$1**, raising the shared experiment cap **$15 → $16**.
The fresh manifest `6dac4e5c...6271f1a` was consumed exactly once. It reserves at
most **$1.282** for the whole batch, with 30,000 measured input tokens and 5,120
output tokens per case. Actual usage stayed below both limits.

| Conservative local accounting | USD |
| --- | ---: |
| Numeric generation | 0.34135 |
| Narrative generation | 0.28960 |
| Two count contingencies | 0.02000 |
| Added accounted amount | **0.65095** |
| Shared accounted total / cap | **15.22872845 / 16** |
| Remaining allowance | **0.77127155** |
| Pending reservations | **0** |

Rates retain $12.50 per million input tokens and $50 per million output tokens;
no cache discount is assumed. Responses report zero cached tokens and cache-write
counts of 23,661 / 17,369. The $0.01 per count remains a contingency, not a verified
tariff. These accounting amounts are not the provider invoice. Peak batch usage
plus active reservation and count contingencies was **$0.83450**, below $1.282.

## Admission, preservation and next boundary

The new caller reconstructs both current requests from the original canonical
521-candidate catalog, 204 source candidates and owned requirements. It preserves
JSON insertion order in that canonical input because it affects prompt strings.
Both regenerated requests match the prepared hashes exactly. Review criteria and
past answers never enter paid inputs. A historical numeric response is used only
as an explicitly labeled offline control for source lowering and execution.

Eleven caller controls pass, covering maximum funding, exact order, count limits,
503 handling without retry, retained unknown-usage reservation, malformed schema,
unlinked source quotes, changed requests and observed usage overruns. Separate
processes produce **13 identical rehearsal files**, including four SDK bodies.
Two documentation checks pass: **13 checks this turn**. Initial local preparation
findings (input key order and missing transport context-manager support) were
fixed before sealing admission; their failed no-call records remain preserved.
Existing production gates were not rerun because runtime source is unchanged.

All **9,124 predecessor files**, **174 source files**, seven runtime owners,
**24 store files** and local settings retain hashes. The manifest also pins
caller/policy/input files and installed SDK identities. Only documentation is
committed; admission, responses and review artifacts remain ignored local evidence.

The bounded experiment is complete. Next, prepare a provider-free rehearsal and
fresh cost admission for the normal application's combined answer path. Planning,
retrieval, answer assembly and task-ledger completion were outside this probe.
The earlier mixed application request remains budget-stopped with no final answer;
its consumed manifest and partial evidence remain unchanged. No automatic retry,
resume, full-app paid run or further budget increase follows from this result.

Local evidence: [admission](../../benchmarks/results/compiler_axis_probe_admission_2026-09-19/manifest.json),
[execution receipt](../../benchmarks/results/compiler_axis_probe_2026-09-19/run_receipt.json),
[source review](../../benchmarks/results/compiler_axis_probe_2026-09-19/source_semantic_and_format_review.json),
[accounting](../../benchmarks/results/compiler_axis_probe_2026-09-19/accounting.json),
[preservation](../../benchmarks/results/compiler_axis_probe_2026-09-19/integrity.json).
