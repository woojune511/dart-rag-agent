# Frozen semantic selection: new-question comparison

Prepared 2026-09-29 after the user requested proceeding with frozen LLM evidence
selection on new questions. This authorizes one isolated comparison; it does not
adopt a selector in the application.

## Question and evidence boundary

Twelve new source-authored positive questions cover four familiar 2023 filings:
LG Energy Solution, POSCO Holdings, SK Innovation and KakaoBank. There are four
lookup, four calculation and four explanation questions. Questions, source
witnesses and component-level criteria were sealed before query retrieval or
generation. A manual comparison against full77 and the earlier final12 found no
same-company/requested-metric paraphrases; exact-query comparison also passes.
This is not exhaustive historical deduplication or a model-training holdout.

The author knows these reports and authored the gold from their frozen text.
There are no unseen-report, independent-gold, random-sampling or negative-question
claims. Source witnesses are locating aids, not exhaustive semantic hit labels.

## Frozen comparison

- Reuse table representation and existing document embeddings; no fresh ingest.
- Embed each exact question once. Search its explicit receipt scope using dense16
  plus BM25 up to24 candidates, merged with RRF60.
- Baseline: first eight RRF candidates. Semantic arm: unchanged original
  `fixed_pool_selection_2026-09-28` selector prompt/schema, up to eight sources.
- Selector input uses the original deterministic source-ID hash order. Preserve
  every baseline-delivered source, then add whole candidates in hash order within
  the 200,000-byte reservation including1,024 overhead. Record all omissions.
- Both answers use the identical original prompt/schema, model settings and
  65,536-byte whole-source packet bound. Sufficiency flags/gold never enter the
  answer. Alternate answer order by question. No ledger, extra query or calculator.
- Model: `gpt-5.6-terra`, low reasoning, max8,192 output, store=false, default tier.

An initial blocked-network synthetic-vector rehearsal exceeded the selector input
bound on N06 after21 mock HTTP calls. No paid calls occurred. That attempt and its
manifest remain intact. `experiment_v2.py` adds only the generic input window
above, before live outcomes; question/gold/prompt files remain unchanged.

## Review and stop rules

Primary outcome: complete and correct requested content, every material claim
supported by cited sources, and abstained=false. Report core completeness,
all-claim support, delivered/pool evidence sufficiency, abstention, paired outcome
matrix, category counts, sufficiency confusion matrix and cost/time separately.
Equivalent evidence can satisfy a component outside its recorded witness IDs.

Assistant source review is not blinded or independent. Preserve ambiguous cases
as explicit sensitivity analyses. Small one-sample-per-arm results are descriptive.
The positive-only panel cannot measure rejection of unanswerable questions.

One batch: at most36 generation calls and12 query embeddings, USD15 cap;
worst-case conservative reservation USD13.657224. Accounting uses prior verified
2026-09-28 rates: USD2.5/12 per million input/output, embedding USD0.13 per million,
ignoring cache discounts. These are estimates, not billing records. No retries,
resume, hidden repairs or automatic successor. First provider, usage, contract,
scope, budget or protected-hash failure stops the remainder as NOT_RUN. Heartbeat
every20 seconds; no results-based question removal or prompt tuning.

## Local artifacts

`benchmarks/results/semantic_selection_new_questions_2026-09-29/` contains the
sealed dataset, original failed offline attempt, corrected pre-live runner,
`manifest_v2.json`, blocked-network rehearsal and fault controls. Results remain
ignored local artifacts. Production source and prior experiment outputs are
protected, and no commit/push is part of this run.
