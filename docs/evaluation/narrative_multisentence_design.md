# Multi-sentence narrative comparison design

The [subsequent bounded comparison](narrative_multisentence_comparison.md) is now
complete: both instructions accept 4/6 answers and retain 23/25 required criteria,
with four accepted ties and two shared omissions. The preparation below remains
a historical no-call snapshot; its authored examples are not sampled results.

Prepared on 2026-09-18 from clean `6c6a2891`, following the
[eight-control comparison](narrative_eight_control_comparison.md). That run tied
on all eight cases and mostly repeated one-sentence sources. This preparation
adds **six new passages and questions**, with evidence spread across paragraphs
and a concise summary request. **No provider call, input-token count, sampled
response, new semantic score or budget increase occurs.**

## Frozen inputs and interpretation criteria

The [local packet](../../benchmarks/results/narrative_multisentence_design_2026-09-18/)
contains three Korean and three English fictional operational notes. Each has
three paragraphs, **631-1696 source characters** including paragraph separators,
and a new question requesting a summary in at most three sentences. There are
**25 required content criteria**, each linked to an exact source quote/span;
every case requires content from all three paragraphs. A single copied source
sentence cannot cover the required content. Faithful quotation remains allowed;
overlap itself is not an error or a quality score.

| Case | Language | Main distinction to retain | Required criteria |
| --- | --- | --- | ---: |
| M01 | Korean | Equipment maintenance, storage expansion and a deferred order | 4 |
| M02 | English | Different local actions and observations versus group-wide claims | 4 |
| M03 | Korean | Limited trial, two pending conditions and unconfirmed effects | 5 |
| M04 | English | Some versus all sites; missing uploads versus unperformed checks | 3 |
| M05 | Korean | Stated contributing factors versus concurrency and invented dominance | 5 |
| M06 | English | Superseded proposal versus current partial implementation | 4 |

Input SHA-256:
`4cdc05c04fa58bbc5fc994dfb9b44fe5bb63673b709df624472800ceaff96505`.
Rubric SHA-256:
`1028b79f641ef3f198d86ac353b823c3b521234b3541e9dcd4d65202d1c6c39e`.
Both were frozen before SDK capture or any sampling. These are newly authored
inputs, not independent holdout, human gold, real DART filings or material known
to be absent from provider training. Their mechanisms were chosen from earlier
diagnosis. The preparer knows the sources and intended distinctions.

The runtime input contains only the question, one narrative obligation and the
three original source paragraphs as separately addressed candidates. Required
criteria, accepted/rejected examples, review notes and condition labels never
enter the model request. Twelve real SDK request bodies are captured **before
HTTP transmission** with a dummy credential and blocked external sockets.
All eighteen paragraphs are fully exposed in both conditions, including every
criterion's source quote; the prompts are not truncated to fit a token guess.
Only the already reviewed narrative instruction differs between conditions.
Schema, sources, questions, Astra/medium/Standard/5120/`store=false` remain fixed.
Captured bodies span 16416-17105 UTF-8 bytes; these are not server token counts.

## Review and proposed sampling

The [reviewer table](../../benchmarks/results/narrative_multisentence_design_2026-09-18/reviewer/review.md),
JSON template and reviewer-only ZIP contain sources, questions, fixed required
criteria and **twelve uncollected response slots**, with all judgments unfilled.
Authored answer examples, the condition key, execution order, telemetry and
structural outcomes are excluded. The fixed source/criterion tables support
consistent review but do not make the preparer an independent reviewer.

The proposed run collects **6 cases x 2 conditions x 1 response**. Generation
order and displayed A/B position are independently assigned before sampling:
each condition is first in three cases and displayed as A in three, with joint
cells **2/1/1/2**. Each language has one/two per condition in each position,
opposite across languages. Review decisions and exact source/response quotes
are locked before joining the condition key. Folder separation is not access
control; prior familiarity or style can still reveal conditions.

Review every clause, required criterion, subject/action connection, qualifier,
condition, negation, temporal scope, unsupported addition, abstention and request
compliance. Equivalent wording is allowed. The concise-summary instruction is
reviewed against the combined answer, without a keyword or punctuation-count
classifier. Ambiguous judgments remain uncertain; any later adjudication is a
separate record. API missingness stays separate from an actual sampled abstention.

Primary acceptance requires faithful, complete, request-compliant output without
unsupported additions or unnecessary abstention. Report dimensions separately,
then paired adopted-better/adopted-worse/tied-accepted/tied-rejected/uncertain/
unavailable counts. A tied failure is not success. Source-address validation
cannot decide these semantic outcomes, and authored examples are not sampled
answers, exact-match gold or automatic graders.

## Budget and execution boundary

Shared accounting remains **9.60696504 / 14**, remaining **4.39303496**, pending
**0**. At the retained conservative input/output rates and count contingencies,
the proposed maximum is:

| Reservation component | USD |
| --- | ---: |
| Twelve full 5120-output ceilings | 3.072 |
| Twelve count contingencies | 0.120 |
| Twelve inputs at a proposed 6000-token ceiling | 0.900 |
| Proposed run cap | **4.092** |
| Remaining allowance outside that cap | **0.30103496** |
| Additional allowance needed | **0** |

The 6000 ceiling is a proposed stop condition, not a measured count or a runtime
setting change. This calculation reuses the retained
[pricing snapshot](../../benchmarks/results/narrative_multisentence_design_2026-09-18/official_rates.json)
checked on 2026-09-18; it is not a new price fetch, invoice, count tariff or
prediction that the full reserve will be consumed. No cache discount or release
of the historical failed-request reserve is assumed.

A later continuation can use this concrete twelve-response scope within the
existing allowance. It still needs a fresh verified caller and single-use
manifest bound to the final inputs, schedule and cap. All twelve exact counts
must precede any generation, each at most 6000, with every full response reserve
funded. Stop on the first count/provider/incomplete/refusal/schema/usage/identity
failure, preserve partial evidence and retain unknown-usage reservations.
No retry, repair, resume, replacement sample, selective case dropping, source
trimming, model/output change or automatic cap increase follows. This design
has no live manifest and does not reuse the prior consumed admission.

## Local verification and limits

Initial authored source IDs `p1`-`p3` collided with piece IDs during reference
aliasing. A provider-free rehearsal was rejected as `unknown_compiler_reference`
before a second authored invocation; its captured request and diagnostic are
preserved. The final fixture uses distinct `paragraph_1`-`paragraph_3` source IDs.
Only synthetic identity fields and their derived addresses changed; original
source/question/rubric and authored claim text did not. No runtime rule or
validation contract was changed to accept the fixture.

All **24** authored replays pass current Compiler and deterministic execution:
six faithful and six deliberately unsupported examples under each instruction.
The **12 structurally accepted semantic negatives** explicitly preserve the
boundary between valid citation addresses and correct meaning. They are authored
contract witnesses, not evidence of sampled model success or failure.
Twelve negative checks reject invalid count shapes/bounds, missing counts,
condition leakage, premature scoring, missing slots/criteria, changed request
hashes and changed visible source. Documentation checks **4/4** pass. All **174**
source files, **4492** predecessor artifacts, **24** stores and local settings
retain hashes. No full runtime suite or benchmark was rerun; only documentation
is committed, with experimental material retained locally outside Git.

This design is ready for the bounded comparison, not a result. One sample per
condition and six purposively authored cases cannot establish sampling variance,
population efficacy, transfer to DART filings or full-agent quality. If results
later inform another prompt change, this set becomes development evidence; it
must not then be reused as an unseen test. Earlier paid results and their claim
boundaries remain unchanged.
