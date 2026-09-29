# Table structure: actual answer comparison preparation

Status: preparation snapshot retained; subsequent approved generation is
**COMPLETED36/36**. See [actual answers and review](structure_answer_result.md).
The following records the pre-generation plan on2026-09-28. The preceding
USD1.60 approval was retrieval-only and is consumed; it does not authorize this
generation phase. No runtime, prompt, policy, canonical store or old result changed.

## Question and fixed comparison

Does evidence retrieved by flat/structured × dense/RRF lead to correct, complete
answers supported by the sources actually cited?

Replay the [retrieval experiment](structure_retrieval_factorial.md)'s exact nine
questions and36 ordered top8 lists through the real `SimpleRagAgent`. The same
Terra model, low reasoning, prompt, strict schema,8,192 output-token limit and
65,536-byte context limit apply to every arm. Rotate the four arm orders across
questions. This is one sample per cell, not a stochastic reliability estimate.
All288 selected source occurrences fit the production packet limit.
No new retrieval, embedding, ingest, Compiler, prompt repair or paid judge.

## Pre-generation criterion correction

`KBF_T1_017` asks about KB Financial Group, but its original reference uses
KB Kookmin Bank's nominal NIM1.83%/1.73%. The raw2023 filing's bank heading and
NIM are at lines10588 and13142. The group NIM(bank+card) row at179120 instead
shows2023=2.44,2022=2.30 and a reported change0.13 percentage points. Displayed
endpoint subtraction gives0.14pp; no rounding explanation is established.

Keep the original question and four arms as an entity/source-conflict diagnostic,
but exclude it from the **primary8-question denominator before generation**.
Do not rewrite the original panel or count bank values as group evidence.
Earlier annotation-hit counts remain historical proxies; the claim that this
item demonstrates structure-preserving retrieval success is withdrawn.

## Answer review

The primary outcome is **correct + complete + cited-source-supported /8** per
arm, covering every requested component. Check entity, consolidation scope,
period, units, arithmetic and source meaning, not just numerical anchors or
valid citation IDs. Equivalent alternative evidence is allowed. Independently
recompute arithmetic at the displayed precision; optional extra claims must
also be correct and supported.

Report content-only correctness separately, alongside numeric components,
unsupported claims, safe abstention, runtime errors and NOT_RUN. An abstention on
an answerable question is incomplete, not a hallucination. Errors/unrun cells
remain in the planned denominator but are not labeled model wrong answers.

For each answer, separately review whether sufficient evidence was visible and
whether the answer was correct/supported. This distinguishes retrieval failures
from evidence-to-answer failures and correct answers without adequate citations.
NIM diagnostics do not enter aggregate accuracy. Assistant source review is not
blind, independent human gold, or an LLM-as-judge score. These filings/questions
are development-exposed; no general DART accuracy or live-search latency claim.

## Bounded execution and verification

- 36 answer calls at most, one attempt each; no automatic retry/resume.
- Conservative full reservation USD6.813559; proposed standalone ceiling
  **USD6.85**. This is a guard ceiling, not expected spending or observed billing.
  The guard reserves serialized request bytes plus1,024 as input-token bounds,
  all8,192 output tokens, and USD2.50/M input +USD12/M output accounting rates.
- Freeze source code, dependency declarations, six filings, corpora, panel,
  retrieval results, criteria and exact ordered SDK request hashes.
- Save each request, response, application result, usage/budget and case status;
  20-second heartbeat. Stop after the first error; remaining cells are NOT_RUN.
- Two blocked-network36-request rehearsals match exactly; five controls cover
  cap, HTTP503, missing usage, foreign citation and persistence failure. Relevant
  SimpleRag/admission/documentation tests26/26 pass. These are execution checks,
  not fresh model-quality evidence.

Local ignored artifacts: `benchmarks/results/structure_retrieval_factorial_2026-09-28/`.
The runner is `generate_answers.py`, criteria `generation_criteria.json`, and
offline verifier `verify_generation_preparation.py`. `generation/manifest.json`
SHA-256 is `c30d76a5f2318e0c4a5f595ad945f0a103debc864f79a3ea108f8120585ba8ce`;
criteria SHA-256 is `be4f0baef58ca1d0783fecb972fdf33aa3774763fd6ede2b1f81825a2ae2578a`.
At preparation time no authorization file or consumption marker existed. The
subsequently approved USD6.85 authorization is now consumed; no automatic rerun.
