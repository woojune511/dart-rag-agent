# Evidence selection problem set: preparation and lexical diagnostic

Prepared 2026-09-28 on `ec714bd0`. This is a separately authorized research
preparation task; the completed Simple RAG portfolio scope and runtime are unchanged.
Six newly worded, source-authored questions have **18 frozen candidate packets**.
No semantic model, new retriever or proposed selection method has been evaluated.

## What is ready

| ID | Report | Question focus | Required distinction / positive control |
| --- | --- | --- | --- |
| P01 | LG Energy Solution 2023 | One-year lease contractual cash flows, prior-year growth, discount/interest basis | Undiscounted cash flow versus carrying value; prior/current evidence must be combined |
| P02 | LG Energy Solution 2023 | Net R&D expenditure growth and two CDO research projects | Before/after grants; CDO versus CTO/CPO; actual projects versus general accounting policy |
| P03 | Hyundai Motor 2022 | Consolidated versus separate discounted lease liability and difference | An explicitly requested cross-scope comparison is valid, not a conflict |
| P04 | Hyundai Motor 2022 | Interim plus planned annual dividend per common/second-preferred share | Security class, period, per-share versus total amount, proposed versus paid status |
| P05 | Samsung Electronics 2024 | Consolidated capitalized borrowing costs and year-on-year growth | Consolidated/separate statements and current/prior columns |
| P06 | Samsung Electronics 2024 | Principal plus interest lease cash outflow, growth and activity classification | Consolidated/separate; principal/interest; intentionally combining financing and operating cash flows |

The three source files are existing local filings outside the prior six-report
table panel, but companies and reports may have earlier development exposure.
This is **not an unseen-company or independent holdout evaluation**. A scan of 591
question strings in tracked benchmark JSONs finds no whitespace-normalized exact
duplicate. That does not establish semantic novelty. The separately authored
`simple_rag_full77_result.md` was read to assess exposure and left unchanged.

Each question has six authentic excerpts and a selection cap of three:

1. `complete_background`: all annotated necessary evidence plus unrelated
   same-report excerpts.
2. `complete_confounded`: necessary evidence plus related authentic excerpts
   involving a competing basis, scope, subject or period. These are candidate
   conditions, not observed model errors.
3. `missing_required`: remove an essential source from the second pool and add
   an unrelated excerpt. Other partial evidence remains. Insufficiency refers
   only to this packet; the full report can still answer the question.

No financial values, period headings or source text were invented for distractors.
The 43 excerpts retain exact raw HTML character spans, source line references and
hashes; table text is a diagnostic display projection, not canonical parser output.
Cover reporting periods and the nearest actual section title remain visible.
Original row/column layouts require source review; text identity is not a semantic
interpretation guarantee.

The six-question set is small and deliberately authored to exercise the proposed
problem. Five questions are principally numeric and one includes project narrative;
it does not represent financial question frequencies or broad narrative ability.
Candidate count is matched across conditions; text length and content are not.
Cross-condition differences cannot isolate distractor content from those effects.

## Frozen data and checks

Ignored local package: `benchmarks/results/evidence_selection_problemset_2026-09-28/`.

- `inputs/`: 18 model-visible packets with question, source context, text and
  opaque evidence IDs. Gold labels, conditions and reference answers are absent.
- `evidence.json`: 43 source excerpts with raw provenance.
- `gold.json`: assistant-authored requirements, possible support IDs, numeric
  references, interpretation caveats and the six absent-source controls.
- `protocol.json` / `freeze.json`: pre-probe criteria, stage statuses and hashes.
- `REVIEW.md`: six full question cards and source links for manual review.
- `verify.py`: isolated standard-library preservation, projection and leakage checks.

Freeze SHA-256:
`e2f46b1675ac8f2ee1938e2744334384a73faaf8762b8373bc716763362e2acf`.

Checks pass for three original source hashes, 43 excerpt projections and contexts,
18 packets, 12 complete/6 incomplete authored controls, eight arithmetic checks,
and four in-memory tamper/missing-source controls. Existing modified documents and
runtime source hashes are preserved. These are mechanical and assistant source
checks, not independent human gold validation or sampled model performance.

## One offline BM25 probe, and its important limitation

The unchanged production Korean tokenizer and default `BM25Okapi` score each
curated six-excerpt pool once. Positive-score top three are retained; ties follow
the frozen candidate order. Raw selections are saved before gold is loaded for
annotation scoring. Network transport is blocked. No parameters were tuned.

| Condition | Complete annotated support retained | Denominator |
| --- | ---: | ---: |
| Complete with background excerpts | 5 | 6 |
| Complete with related competing excerpts | 2 | 6 |
| Essential source removed | 0 | 6 |

These are **candidate-pool annotation-coverage counts**, not answer accuracy,
natural retrieval recall, safe-abstention rates or a production BM25 baseline.
In particular, 0/6 on missing packets does not mean a system recognized absence.

The tiny local index changes IDF. In confounded P05, correct capitalized-cost
sources receive negative BM25 scores, leaving only two positive-score interest
expense sources. In confounded P06, all six scores are negative; production's
positive-score filter leaves no selection. These two cases expose a small-pool
lexical-scoring artifact, **not demonstrated model scope-confusion failures**.
P01 loses both amount tables while retaining the basis paragraph; P03 loses the
consolidated balance while selecting lease expenses. P02 and P04 retain all
annotated requirements even with competing excerpts.

Do not tune BM25 on this set, infer an inherent RRF flaw, or use the 5/6 versus
2/6 contrast to claim a need for a new algorithm. A future corpus-level lexical
baseline needs report-level statistics and a separately specified construction.
The current probe remains recorded with its limitation rather than replaced.

## Decision and the next bounded comparison

The problem set and review packet are ready. **Implementation of a new method is
not yet warranted.** We have not established that ordinary semantic reranking or
an existing evidence-set method fails these questions.

The next comparison should use the unchanged 18 model-visible packets:

- An ordinary semantic relevance selector and an existing set-selection baseline
  such as [SETR](https://arxiv.org/abs/2507.06838), with the same selection model,
  candidate texts, at-most-three sources and fixed limits. Before execution,
  inspect the published method and declare fidelity or deviations; a generic
  coverage prompt is not automatically a faithful SETR reproduction.
- Evaluate whether selected sources cover each requested component with compatible
  meaning, whether missing evidence is acknowledged, and whether valid cross-scope
  requests are over-rejected. Picking an irrelevant source alone is not evidence
  that a wrong number was used. Accept independently reviewed equivalent evidence.
- Keep selected-set sufficiency, generated-answer accuracy, additional cost and
  latency separate. No answer-generation success is inferred from annotations.
- If the existing semantic method solves the contrasts, reuse it or stop this
  proposed contribution. Design a new component only for a recurring residual
  failure. Its later ablation and generalization evaluation require a new panel.

The two semantic selectors, RRF for these new questions, and answer generation
are **NOT_RUN**; the proposed method is **NOT_IMPLEMENTED**. No dense query vectors
exist for these new questions, so old question vectors/ranks are not reused as RRF
results. New model routes, prompts, exact request manifests and full cost limits
must be fixed before any provider run. No spending authorization is created here.

New provider calls, query/document embeddings, store clients and added cost: **0**.
Only this report is a new source-controlled document; raw packets/scripts remain
ignored. Prior working-tree changes, datasets, stores and settings are preserved.
