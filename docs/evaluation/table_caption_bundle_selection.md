# Budget-aware table-caption bundle selection

Date: 2026-09-30. Status: **COMPLETE_OFFLINE_FEASIBLE_NOT_ADOPTED**.

A frozen greedy selector considers caption dependencies before filling the
eight-source packet. It removes all three caption-induced count rejections in
the saved77-question panel while retaining the selected data tables. Each case
replaces one lower-ranked original source with the caption. This establishes
mechanical feasibility; it does not establish better answers or refusal quality.

## Frozen comparison

Primary input is the existing production ANN16/BM25<=24/RRF60 candidate union
for77 questions. The exact-Dense version of the same77 is sensitivity analysis,
not another77 independent questions. No search, embeddings or generation runs.

| Arm | Final selection |
|---|---|
|R reference|Historical top8 followed by existing whole-source byte packing.|
|A capacity control|Scan the same full union in RRF order; take a whole source if cumulative count<=8 and packet<=65,536 bytes; otherwise skip and continue.|
|B caption bundles|Same A scan and limits, but a selected verified table requires its complete caption source; both physical chunks count. Deduplicate captions already selected. Skip the entire incremental bundle if it cannot fit.|

Caption-only ranked candidates remain eligible; a caption does not force an
unretrieved table. B may add only a source from the existing178 verified caption
links. There is no general neighborhood expansion, arbitrary outside-pool source,
question interpretation, gold-based ranking, truncation or post-result tuning.
The selector is an ignored experiment artifact; product code is unchanged.

## Results

Both saved rankings have the following identical dispositions:

| Measure | R | A | B |
|---|---:|---:|---:|
| Bounded input packets |77|77|77|
| Selected tables with a verified caption relationship |4|4|4|
| Those tables accompanied by their caption |1|1|4|
| Count/byte rejection during final packet delivery |0|0|0|

R and A are identical on all77 inputs, including the preexisting byte-omission
case. Compared with A, B changes four packets: three source substitutions and
one order-only change. The remaining73 packets are identical. This isolates
the observed changes to caption bundling rather than ordinary capacity refill.
The prior add-after-top8 implementation rejected three inputs; B prevents those
three rejections by making the necessary source tradeoff during selection.

| Question | Added caption | Removed original source | A bytes | B bytes |
|---|---|---|---:|---:|
|KBF_T4_045|158:81, unit for product counts|124:47, heading-only "마. 영업실적"|21,970|22,336|
|SAM_T4_029|920:8, date/unit for affiliate holdings|478:101, defined-benefit sensitivity table|26,591|24,360|
|SKI_T1_068|1712:5, date/unit for segment results|551:168, FCW impairment note|32,209|29,192|

UID suffixes are filing-qualified in the saved records. The KB caption was rank23
in the original candidate union. Samsung and SKI captions were outside that union
and came solely from their verified source links. Thus B is a practical selection
plus verified-attachment comparison, not a claim of an identical physical source
universe. The data-table candidates and their relevance order are unchanged.

HYU_T4_012 already had both sources and only their presentation order changes.
MIX_T3_063 still delivers six sources/65,435 bytes. Neither A nor B finds another
candidate that fits after the existing two whole-source byte omissions; it is
not a recovered coverage case. No packet exceeds eight physical sources or the
unchanged byte limit.

## Evidence preservation review

The unchanged27 source-reviewed request annotations provide limited preservation
controls: no previously satisfied slot is lost or gained. Their58 exact quote
bindings still match the stored source bodies. These27 controls do **not** cover
the three substituted-source questions, so they alone cannot justify those swaps.

The same assistant separately inspected all three removed whole sources against
the original questions. This is exposed, unblinded review, not an independent
evaluator or complete semantic validation:

- KB asks for factory operating rates and production, while the removed body is
  only a heading. The added source labels bank insurance-product counts. It does
  not make the factory question answerable.
- Samsung asks for life-insurance premium revenue. The removed source is a
  defined-benefit sensitivity table; the retained table and added caption concern
  affiliate ownership percentages. Neither constitutes the requested premiums.
- SKI asks for battery loss relative to total consolidated operating profit.
  The removed note concerns another subsidiary's FCW impairment. All five
  pre-selection witness occurrences remain, including SK On corporate loss,
  the distinct battery-segment loss, and consolidated total operating profit.
  Their scope difference remains explicit; adding a caption does not resolve
  which interpretation the question intends or prove the calculation correct.

No directly requested operand was identified in the three removed sources.
Two changed cases are preexisting refusal questions; with no answer generation,
correct refusal or unsupported numerical answers cannot be evaluated. They must
not be counted as two answer improvements. Broader alternative evidence and full
question completeness have not been independently adjudicated.

## Verification and limits

- Six provider-free selection controls: atomic two-source count, late bundle
  rejection, shared-caption dedupe, standalone caption, exact byte boundary and
  unknown/duplicate source rejection.
-154 historical R packets reconstruct exactly;308 actual A/B SimpleRagAgent
  input packets match their independently proposed whole-source selections.
-308 bounded packets verify source identities, exact original text (allowing
  only the existing search whitespace trim), scope, count/byte caps, and the
  invariant that every selected linked table has its caption.
-58 prior quote bindings,27 request controls per ranking and5 distinct SKI
  diagnostic witness occurrences verify. Two documentation authority tests pass.
-Provider calls, fresh embeddings, new retrievals and cost0. No Chroma open,
  store/.env change, runtime edit, rule tuning or activation. Old scores and the
 6/8 versus7/8 COMPLETE_GATE_NOT_MET conclusion remain unchanged.

The narrow capacity problem is solved in this replay. Before product adoption,
a separately frozen small comparison on new questions would need to test actual
answer support/completeness and refusal behavior, with model, prompt and budget
held fixed. This audit does not launch that comparison or authorize broad rollout.

## Evidence

- `benchmarks/results/table_caption_bundle_selection_2026-09-30/`: frozen
  rules/manifest, prior annotations, pre-selection SKI witnesses, analysis,
  source-change review, verification, completion and seal.
- `D:/CodexArtifacts/dart-rag-agent/table_caption_bundle_selection_2026-09-30/`:
 308 A/B packets and154 per-question records with complete selection traces.
- [Previous capacity finding](table_caption_capacity_audit.md) and
  [explicit caption implementation](table_caption_link_implementation.md).
