# Table structure: actual answer comparison

Completed once on2026-09-28: **36/36 answers, zero errors/retries/NOT_RUN**.
Under the frozen8-question primary rubric, flat+RRF yields5/8 fully correct,
complete, cited-source-supported answers; structured+RRF yields4/8. The result
does **not** establish an aggregate answer-quality advantage for structured RAG.
It does show a specific table-boundary recovery that reaches a correct answer.

## Method and outcome

[Preparation and rubric](structure_answer_preparation.md) were frozen before
generation. Replay the existing flat/structured × dense/RRF top8 lists through
unchanged `SimpleRagAgent`, using the same Terra model, low reasoning, prompt,
schema and context/output limits. All288 selected source occurrences fit the
model-visible packet. No new retrieval, embedding, ingest, paid judge or repair.
Nine questions run in each arm; NIM is diagnostic-only, excluded in advance.

| Arm | Reviewed sufficient evidence /8 | Correct, complete and cited-supported /8 | Correct requested numeric components /11 | Abstentions /8 |
| --- | ---: | ---: | ---: | ---: |
| Flat + dense | 3 | **2 (25.0%)** | 4 | 4 |
| Flat + BM25/RRF | 5 | **5 (62.5%)** | 7 | 2 |
| Structured + dense | 3 | **3 (37.5%)** | 4 | 5 |
| Structured + BM25/RRF | 4 | **4 (50.0%)** | 8 | 3 |

Evidence sufficiency is assistant review of the actual packet against the frozen
rubric, not the earlier annotation-hit proxy. Content-only complete correctness
has the same counts here. Numeric components are a secondary completeness view:
one requested result per primary question, except three FX quantities and two
financial ratios. Correct fragments in abstentions count there, not as full answers.
An abstention is not automatically safe: some contain incorrect partial claims.

### Per-question primary outcome

| Question | Flat dense | Flat RRF | Structured dense | Structured RRF |
| --- | --- | --- | --- | --- |
| KakaoBank CIR | Pass | Pass | Pass | Pass |
| POSCO interest coverage | Abstain | Abstain | Abstain | Abstain |
| Samsung inventory loss/effect | Abstain | Pass* | Abstain | Abstain + wrong period |
| Celltrion capitalized R&D | Pass | Pass | Pass | Pass |
| KB provision growth and cause | Abstain | Pass | Abstain | Correct growth; cause incomplete |
| SK hynix translation gain/loss/net | Abstain | Abstain | Abstain | Pass |
| SK hynix borrowing/asset ratio | Scope ambiguity† | Wrong period/basis | Abstain | Abstain + unsupported subtotal |
| Samsung debt/current ratios | Calculation precision error‡ | Pass | Pass | Pass |

No later answer, rubric or prompt was repaired to improve these outcomes.

## Where evidence did and did not become an answer

1. **A concrete structure success — translation gain/loss.** Flat chunk75 ends
   after the gain label, leaving only loss906,120 million KRW. Both flat arms
   abstain. Structured chunk333 retains loss906,120 and gain573,884 in the same
   cash-flow table. Structured+RRF retrieves it, interprets the negative cash-flow
   gain adjustment correctly, and answers net loss332,236 million KRW. Structured
   dense does not retrieve it. This supports a case-specific representation-plus-
   retrieval benefit, not a universal parser benefit or an isolated prefix effect.
2. **Alternative evidence beats the anchor proxy.** Flat+RRF answers Samsung's
   loss/effect question and KB's provision cause using retrieved evidence not fully
   recognized by the original anchor set. KB flat405 supplies conservative
   provisioning and the recession/high-rate environment; structured+RRF has the
   correct70.3% growth but only general ECL policy, and explicitly cannot identify
   the actual annual cause. Its valid citations do not make the answer complete.
3. **Evidence is not arithmetic.** Flat+dense cites all four Samsung ratio
   operands but writes92,228,115 /363,677,865 ×100 =25.40%. The quotient is
   25.359837%, or25.36% at two decimals. The source separately displays25.40%;
   copying it into a calculated equality does not establish correct arithmetic.
   The other arms report the valid one-decimal25.4%. Current ratio258.77% is valid.
4. **Structure does not ensure correct interpretation.** Samsung structured+RRF
   cites chunks explicitly marked `period_focus: prior`, then discusses their
   186,396,549 and151,436,315 inventory costs without qualifying them as prior-year
   in a2023 answer. It also lacks the requested loss amount. SK hynix structured+
   RRF abstains on the missing asset denominator but calls15,189,950 “bonds,”
   whereas its cited table has9,490,410 bonds plus distinct current borrowing rows.

## Judgment limits and sensitivity

*Samsung flat+RRF passes the frozen qualitative criterion: it gives the correct
consolidated5,037,579 loss/reversal **etc.** amount, cites separate inventory-cost
inclusion, explicitly distinguishes bases, and avoids a cross-basis percentage
or claiming a proven pure write-down. This is not a quantified consolidated
cost-of-sales attribution. A stricter same-consolidation attribution requirement
would reduce flat+RRF to4/8, tying structured+RRF; that is a post-run sensitivity,
not a silently revised primary criterion.

†The frozen SK borrowing target sums three named rows:4,145,647 +10,121,033
+9,490,410 =23,757,090; dividing by56,539,420 gives42.0186305%. The question's
wording can also be read as total borrowings including current portions. Flat+
dense's cited total29,468,632 and52.12% are correct for that broader scope. This
is a question/rubric ambiguity, **not invented data**. Accepting that reading
would raise flat+dense to3/8. Keep the original8-question denominator and flag
the ambiguity discovered after generation. Flat+RRF instead mixes prior-year
loan figures with current gross bond principal; that is a separate real error.

‡The two-decimal arithmetic failure follows the frozen displayed-precision rule.
Using a looser numerical tolerance or accepting source-stated25.40% despite the
explicit division would raise flat+dense by one. Do not portray its small
rounding discrepancy as a large financial error or a broad structure advantage.

KB flat+RRF's NPL connective is interpreted as referring to macro deterioration,
which its source describes, not as proof that provisioning causes NPL increases.
The narrative ratings are assistant judgments, not independent human gold.

### NIM diagnostic, outside the primary denominator

All four arms recover **group** NIM2.44%/2.30% and compute+0.14pp, despite the
original reference incorrectly using bank1.83%/1.73%. Flat+dense explicitly
separates the source's+0.13pp change without a causal explanation. Structured+
dense omits that conflict; both RRF arms add an unverified pre-rounding explanation.
This is further evidence that annotation hits and valid citation IDs are not
semantic correctness or faithful conflict handling.

## Cost, execution and preservation

| Arm (nine answers including NIM) | Input tokens | Output tokens | Conservative estimated USD |
| --- | ---: | ---: | ---: |
| Flat dense | 124,598 | 2,780 | 0.344855 |
| Flat RRF | 122,895 | 3,035 | 0.3436575 |
| Structured dense | 79,476 | 2,236 | 0.225522 |
| Structured RRF | 75,690 | 2,520 | 0.219465 |
| Total | 402,659 | 10,571 | **1.1334995** |

Accounting uses the approved conservative USD2.50/M input +USD12/M output rates,
ignoring cache discounts; it is not observed billing. The standalone USD6.85
authority is consumed, with no automatic retry/resume. The preceding retrieval
phase's USD1.47618744 remains separately accounted, totaling USD2.60968694 for
the two phases. The run took138.75 seconds including local instrumentation,
not live retrieval, production latency or a benchmark speed comparison.

Initial startup failed before dispatch because `.env` had not been loaded. A
launch wrapper then used the application's existing dotenv mechanism. A relative
`runpy` path failed its local path check; the absolute path succeeded. There was
no provider retry or frozen runner/input change. Every sampled request matches
the two prior offline rehearsals and the approved ordered request hashes.

Ignored artifact root: `benchmarks/results/structure_retrieval_factorial_2026-09-28/`.
`generation/live_once_env/` stores36 request/response/result/budget/status sets,
startup and receipt. `answer_review.json` records all36 assistant decisions with
request/response hashes; `answer_run_seal.json` seals188 JSON/source-review files
and the unchanged frozen inputs. Hash checks establish integrity, not independent
semantic validation. No raw artifacts were staged, and runtime/prompts/canonical
stores and prior result bytes remain unchanged.

## Conclusion

On this small development-exposed panel, table structure helps a specific
multi-cell answer but **does not beat flat+RRF overall**. Retrieval, context
completeness, calculation, scope interpretation and explanation coverage must be
evaluated separately. One sample per cell, rubric ambiguities and non-blind
assistant review preclude significance or general DART accuracy claims. Do not
add case-specific runtime rules or describe the project as having proven a
general table-structure accuracy improvement.
