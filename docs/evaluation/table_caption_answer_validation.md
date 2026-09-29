# Caption-bundle answer validation

Date: 2026-09-30. Status: **COMPLETE_GATE_NOT_MET**.

Caption-aware selection restored requested date/unit evidence in two new
questions. Both then received complete, source-supported answers twice. The
primary strict progression gate still fails because another positive question
regressed on citation linkage. This is a bounded improvement signal, not a
production adoption or general accuracy result.

## Frozen comparison

- Eight source-authored questions on the existing Hyundai, NAVER and KB2023
  filings: six positives, including three calculations, and two metric/period
  insufficiency controls. Questions, exact original source quotes, requirements,
  numerical criteria and progression gate were fixed before retrieval.
- No exact duplicates among183 previous saved questions. The reports are
  familiar; C05/C07 share a table, and C08 reuses an exposed future-date refusal
  family with different quantities. Eight inputs are not eight independent topics.
- One batch embeds eight questions. Existing document vectors feed exact squared
  L2 Dense16; the unchanged global BM25 supplies at most24 scope-filtered hits,
  merged with RRF60. This is experimental exact-Dense retrieval, not deployed ANN.
- A is the previously frozen rank-ordered whole-source capacity selector.
  B uses the same selector with existing verified table-caption dependencies.
  Each packet has at most eight physical sources and65,536 UTF-8 bytes.
  B may attach only verified captions outside the candidate union; it also
  reorders captions before their tables. This is not a pure formatting ablation.
- Actual SimpleRagAgent packet capture verifies all16 final inputs. Both arms
  use unchanged answer instructions/RagAnswer schema, `gpt-5.6-terra`, low
  reasoning,8,192 output tokens, independent requests and alternating arm order.
  Two repetitions produce32 answers, not32 independent questions.
- No selector generation, tools, calculator, retries, resume, substitution,
  post-result question replacement, prompt tuning or runtime/store activation.

Before paid execution, current official model/pricing/cache documentation and
one account-visible model metadata GET were checked. The entire maximum batch
reserved USD8.79063447 against USD10, including worst-case cache-write input
pricing. Explicit cache mode without breakpoints produced no cache reads/writes.

## Evidence delivery

All six positive data tables reach both arms. A has complete requested evidence
for4/6 positives; B has it for6/6. Two source substitutions explain the difference:

| Question | B attachment | Removed lower-ranked source | Packet bytes A → B |
|---|---|---|---:|
|C02 Hyundai investment carrying-value difference|2023-12-31 / million-KRW caption|Stock-price averaging footnote|29,379 →29,754|
|C03 NAVER bond due2028-11-01|2023-12-31 / million-KRW,% caption|Different2021-issued bonds due2024/2026|18,787 →18,302|

The requested values remain intact. C01/C04/C05/C06/C07 change only source order;
C08 packets are byte-identical. No packet is truncated or exceeds either limit.
Controls remain insufficient in both arms: product counts are not account
counts, and2023 share counts/exercise windows are not2025 actual holdings.
These are packet-level judgments, not a claim to have proved whole-report absence.

## Answers and source support

The same assistant reviewed shuffled answers without arm/repeat labels, using
the source bodies and frozen requirements. Grades were sealed before joining
the arm map. This is not independent review, and source content can reveal an arm.

| Positive question | Required result | A strict passes | B strict passes |
|---|---|---:|---:|
|C01 Small shareholders|889,224 people;111,113,584 shares; date|2/2|0/2|
|C02 Investment difference|26,627,648−1,672,239=24,955,409 million KRW; date|0/2|2/2|
|C03 Bond amount/rate|13,690 million KRW;1.43%; date|0/2|2/2|
|C04 Data-center use of proceeds|200,000+300,000=500,000 million KRW; date|2/2|2/2|
|C05 Trust product counts|7+5=12 products|2/2|2/2|
|C06 FX product counts|11 and5 products|2/2|2/2|

Each repetition has complete correct positive answers **A4/6 versus B6/6**;
including strict citation support, **A4/6 versus B5/6**. Raw numerical selection
is correct in all12 positive responses per arm; all six calculation responses
per arm have correct visible operands, operations and arithmetic. The gain is
restored date/unit evidence and answer completeness, not corrected arithmetic
or demonstrated better semantic selection of numbers.

C02 A acknowledges missing units/exact date but returns `abstained=false` twice.
C03 A correctly sets `abstained=true` while giving the available raw number/rate.
Neither should be described as selecting the wrong monetary amount.

C01 B gives correct values and date but cites the adjacent ownership-table
caption1119:12 rather than the linked small-shareholder caption1121:14. Its
data-table metadata also mentions2023-12-31 for National Pension holdings, which
does not explicitly bind that date to this table. The conservative primary
citation judgment fails both answers. If same-subsection/date context is accepted,
C01 passes and positives become B6/6; this sensitivity is saved separately and
does not replace the primary result. It is a citation-support interpretation,
not a claim that B's stated date is factually wrong.

Both controls abstain correctly twice in both arms, with **zero fabricated
requested counts**. C07 has full cited support throughout. C08 A cites dated
historical evidence, while B twice adds correctly labelled historical counts
and their exact date without citing the available dated source. Strict control
support is A2/2 versus B1/2 per repetition. C08 input packets are identical,
so this difference cannot be attributed to the caption mechanism; it exposes
generation/citation variability in this small sample.

### Packet-answerability confusion matrix

Positive means the delivered packet supports the **entire** request; predicted
positive means `abstained=false`. Counts below are16 responses per arm, including
two repetitions; the underlying input counts remain eight per arm.

| Arm | TP | FN | FP | TN |
|---|---:|---:|---:|---:|
|A|8|0|2|6|
|B|12|0|0|4|

A's two FP responses are C02's partial answers with an incorrect abstention flag,
not fabricated numbers. Denominators differ because B restores full evidence
in C02/C03. On the two designated controls alone, both arms have TN4/FP0.

## Cost, verification and decision

| Observed total over16 answers | A | B |
|---|---:|---:|
|Input tokens|101,238|101,152|
|Output tokens|3,169|2,801|
|Estimated generation USD|0.240504|0.235916|
|Sum of request seconds|60.92|48.87|

One eight-input embedding request used819 tokens/USD0.00010647. Total estimated
cost is **USD0.47652647**; the higher cache-write-rate accounting is USD0.57772147.
Answer batch wall time109.96s. Prices were verified against the
[official pricing page](https://developers.openai.com/api/docs/pricing).
These are usage-based estimates, not invoice amounts or reliable latency gains.

Provider-free checks: six frozen selector tests,12 caption-link tests,
32 mock SDK answers, eight fault/stop controls, one mock embedding batch,
eight source-packet fixtures, and16 actual selected-packet reconstructions.
The preparation verifier initially assumed a caption occupied the entire body;
C08 also preserves a heading. Its correction instead checks the complete stored
text against the audited original node and a unique intact caption occurrence.
This occurred before paid calls and changed no question, gold, prompt or selector.
All32 real response bodies/schema/usage/citations revalidate. Two documentation
authority tests pass;3,257 protected files remain unchanged.

Two stable gains satisfy the first exploratory condition, and no control
fabricates a requested number. C01's strict citation regression fails the
no-regression condition, so the primary outcome is **COMPLETE_GATE_NOT_MET**.
The relaxed C01 citation reading would meet that narrow exploratory threshold,
showing why a broader superiority claim is unwarranted. No application change or
automatic new-report experiment follows this result. A separately authorized
next step can review citation attribution on fresh examples without tuning these
questions. Prior experiments and their conclusions remain unchanged.

## Artifacts

- `benchmarks/results/table_caption_answer_validation_2026-09-30/`: frozen
  questions/gold/rubric, novelty review, selection code, pricing/manifest,
  admission receipts, blinded grades, per-question evaluation, sensitivity and seal.
- `D:/CodexArtifacts/dart-rag-agent/table_caption_answer_validation_2026-09-30/`:
  exact candidate traces,16 packets/requests,32 raw responses and blinded sources.
- [Prior selection feasibility](table_caption_bundle_selection.md).
