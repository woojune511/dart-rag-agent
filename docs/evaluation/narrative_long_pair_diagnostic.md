# Known-source narrative comparison: completed diagnostic successor

The subsequent [eight-control preparation](narrative_blind_review_preparation.md)
adds a masked review template and budget proposal, with no new samples or cost.
The completed pair and its limitations below remain unchanged.

Completed on 2026-09-18 from clean `1af0598d` after the user continued the
recommendation for one fresh pair within the remaining **USD 0.79567246**.
Both generations succeed. Assistant review finds a **sample-level difference**:
the existing instruction adds an unsupported action/object generalization;
the adopted instruction preserves the source distinctions in this pair.
This is one known input with one response per arm, not a general efficacy claim.

## Fixed input and execution

The same frozen NAVER search/display Compiler requests, source/catalog, plan,
schema and Astra/medium/Standard/5120/`store=false` settings are retained.
Only the previously reviewed narrative instruction differs. Four frozen content
criteria and the additional-sentence fidelity check stay outside model input.
There is no live retrieval, Planner, embedding, ingest or full application run.

The caller is byte-identical to the [verified diagnostic successor](openai_error_diagnostics.md).
Fresh single-use manifest
`e908e324eac11eec6ca7574c62e5d4ae8dbfb2bbaabbecc5bf203c59def77d1f`
is consumed once. Both exact counts precede generation and reserve the complete
pair for **0.7471375**, leaving **0.04853496** within this attempt's cap.
All four transmissions return HTTP 200 in about **61 seconds**. No repair,
SDK retry, whole-run retry or resume occurs. The original
[503 attempt](narrative_long_pair.md) remains immutable; this success does not
recover its missing cause or establish that a provider defect was fixed.

| Observation | Existing instructions | Adopted instructions |
| --- | ---: | ---: |
| Exact input tokens, matching usage | 8555 | 8656 |
| Output tokens, including reasoning | 2104 | 2061 |
| Included reasoning tokens | 122 | 127 |
| Schema / current Compiler / V2 execution | Pass | Pass |
| Required content coverage | 4/4 | 4/4 |
| Additional-sentence fidelity | Fails on search summary | Pass in this sample |
| Full semantic acceptance of this sample | Withheld | Accepted by assistant review |

## Semantic finding

The source distinguishes **상품 개선**, **카테고리 확대**, and **AI 기술을 활용한
검색 고도화**. Both answers include those required facts. The baseline then adds:

> 개선 방향은 검색 상품과 카테고리를 확장·개선하고 검색 자체를 고도화하는 데 있다.

This combines products and categories under expansion/improvement, extending
expansion to products without source support. Correct facts in its first sentence
and valid source addresses do not make the extra sentence faithful.

The adopted sample instead says:

> 서비스·상품 개선: 지속적인 상품 개선과 카테고리 확대, AI 기술을 활용한 검색 고도화를 추진하며, 원문은 이를 통해 지속적으로 성장하고 있다고 설명한다.

It preserves the separate action/object pairs and attributes growth to the source.
Its other claims preserve search's information-demand connection, display's
advertiser-message/user relationship, and display's platform/ad-product/new-product
efforts. No required fact is missing, and no unsupported additional clause,
invented effect figure, billing method or unnecessary abstention is observed.

Both untouched raw responses pass source and deterministic execution checks:
two outputs and four claims each, **12 exact subject/fact support occurrences
per arm**, **24 total**. The current prompts and schemas match the frozen requests;
payloads are not repaired or rewritten. This illustrates why source linkage and
semantic acceptance must remain separate.

Review is by the assistant, unblinded and not independent human gold. Fixed order,
sampling variability, unseen questions, paraphrase variety and full-agent behavior
are not controlled by this one pair. The earlier short-source tie stays a tie;
the earlier application response is not retroactively repaired or relabelled.
Retain the already adopted generic policy without another runtime change.

## Accounting and preservation

Usage at pinned conservative input/output rates gives **0.4233875**; adding the
two **0.01** count contingencies accounts **0.4433875**. Reasoning is already
included in output tokens. Rates were rechecked against the
[official Standard pricing table](https://developers.openai.com/api/docs/pricing#standard-pricing-data).
This remains a conservative estimate, not an invoice or an observed count tariff.
The earlier unknown-usage failed-request reserve remains retained.

Shared accounting is now **8.64771504 / 9**, remaining **0.35228496**, pending **0**.
There is no cap increase. Another unchanged pair cannot be fully funded: its two
output ceilings and count contingencies alone require **0.532** before input.
No additional provider call is authorized by this consumed manifest.

Fresh caller controls **7/7**, diagnostic transport controls **4/4**, two historical
Compiler rehearsals and two new sampled-response replays pass with external sockets
blocked. Documentation checks **4/4** pass. All **174** sources, **2848** protected
predecessor artifacts, **187** sealed preparation files, **24** store files and
local settings retain hashes. Prior local **51**, full **2029/2029** and domain
audit **83** remain earlier unchanged-source evidence and were not broadly rerun.
Only documentation is committed; the
[local result packet](../../benchmarks/results/narrative_long_pair_diagnostic_2026-09-18/)
preserves requests, raw responses, review, accounting and integrity receipts.

Next work can prepare a provider-free review packet for the already frozen
anonymous controls and define a broader comparison before any new paid scope.
Do not turn this sample-level difference into an efficacy or release claim.
