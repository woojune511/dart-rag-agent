# Narrative semantic-check budget feasibility

Reviewed 2026-09-18 on clean `2a915ce3`, after [instruction adoption](narrative_clause_policy.md).
The remaining **USD 0.30722246** cannot fully reserve a complete old/new comparison
under the unchanged settings. A single generation is conditional on an unmeasured
input count and would not isolate the instruction's effect. No API request,
new admission, model/bound change or cap increase was made.

## Cost boundary

The current route is Astra, medium reasoning, Standard, 5120 output tokens,
`store=false`, zero SDK retries. The [official pricing table](https://developers.openai.com/api/docs/pricing#standard-pricing-data)
matches the pinned conservative input reserve **12.5** and output **50** USD per
million tokens; the input reserve uses the cache-write rate. The existing **0.01**
per-count allowance is project contingency, not a verified count tariff.

One full output reserve is `5120 × 50 / 1,000,000 = 0.256`; including count allowance
gives **0.266 before input**. All rows below retain that full output bound.

| Shape | Generations + counts | Reserve floor before input | Additional funds to cover that floor |
| --- | ---: | ---: | ---: |
| One initial response | 1 + 1 | 0.266 | 0 |
| One control, old/new instructions | 2 + 2 | 0.532 | 0.22477754 |
| One response plus one reserved repair | 2 + 2 | 0.532 | 0.22477754 |
| Eight controls, adopted instructions | 8 + 8 | 2.128 | 1.82077754 |
| Eight controls, old/new instructions | 16 + 16 | 4.256 | 3.94877754 |

The inherited caps are 12 generations and 12 counts, 200000 input tokens and
300000 request bytes. The 16-pair row is a planning total that also exceeds the
call/count caps; it is not an admissible run under those limits. Any later funded
comparison must separately define its scope without silently raising those caps.

These are full-output reservation floors, **not predicted bills or a claim that
sequential actual outputs must cost this much**. Shorter sampled outputs could
settle for less, but cannot guarantee completion of the comparison within this cap.
Input costs and any further repair would be additional.

A single response leaves **0.04122246** for input: at most **3297 exact input tokens**.
The existing admission preflight agrees: hypothetical 3297 requires **0.3072125**
and fits; 3298 requires **0.307225** and fails. Those are arithmetic boundary
controls, not fabricated provider measurements or a new executable admission.

## Complete request inspection

The [local packet](../../benchmarks/results/narrative_semantic_feasibility_2026-09-18/)
captures **18** real SDK-serialized bodies before HTTP: eight frozen anonymous
sources plus the known search/display input, each with old/adopted instructions.
The eight faithful/unsupported output pairs share eight unique inputs. Their
expected statements and semantic labels are absent from model requests.

Both versions retain identical schemas, sources, settings and complete input
values except for the 418-byte instruction. Adopted anonymous request bodies are
**12666–12693 UTF-8 bytes**, including **2643** schema-JSON bytes; their projected
count bodies are **12587–12614 bytes**. The known adopted request is **35840 bytes**.
Bytes are not token counts. The [counting guide](https://developers.openai.com/api/docs/guides/token-counting)
explains why full formatting/schema overhead requires provider counting.
No count was sent, so even the single-response condition remains unconfirmed.

Budget contracts pass **27/27**, documentation checks **4/4**, without skips or
external connection attempts. All **173** source files, **2269** protected prior
artifacts, **24** store files and settings retain hashes. Prior full **2029/2029**
and domain audit **83** remain unchanged-source evidence and were not rerun.
Shared accounting stays **7.69277754 / 8**, remainder **0.30722246**, pending 0.
The consumed live manifest and its conservative answer-fidelity qualification remain.

Feasibility work is complete. Preserve the captured inputs and separate semantic
labels for a funded comparison; reassess only after an explicit budget or scope
change. Do not spend the remainder on counting alone, start a partially funded
comparison, silently lower output bounds, switch models, or repeat admission
preparation under the same constraint. Model effectiveness remains unmeasured.
