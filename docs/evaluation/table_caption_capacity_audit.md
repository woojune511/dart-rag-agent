# Caption attachment capacity on saved retrieval results

Date: 2026-09-30. Status: **COMPLETE_OFFLINE_CAPACITY_AUDIT — NOT_READY_FOR_ACTIVATION**.

The default saved top8 retrieval leaves no room to attach a missing caption.
Of77 saved questions,4 select a table with a verified caption link. One already
includes that caption; the other3 require one additional physical source and
all fail the unchanged8-source cap before generation. This is3/77 overall
(3.9%), but3/3 of the cases that would add a caption. The attachment feature
cannot provide an added source in this panel under its current capacity contract.

## Frozen scope

- Primary:77 saved v5 production ANN16 + scoped BM25<=24, RRF60/top8 results.
- Sensitivity:exact-Dense16 results for the same77 questions, with fixed BM25.
  These are not154 independent questions. No retrieval or embedding was rerun.
- Existing178-link sidecar and product source were frozen. All saved query,
  explicit scope, ranking, original text/metadata and65,536-byte limit remain.
- Actual `SimpleRagAgent` baseline packets reconstruct exactly for both panels.
  Attachments use the implemented manager lookup and runtime packet builder;
  the answer boundary is intercepted. No Chroma open or store activation.
- The question set is exposed and self-built. Existing positive/refusal/diagnostic
  role labels are reused only for grouping. No gold or answer score is revised.

## Results (identical attachment dispositions in both rankings)

| Measure | Primary ANN77 | Same77 exact sensitivity |
|---|---:|---:|
| Selected table has a verified caption link |4|4|
| Caption already in selected sources |1|1|
| Missing caption would add a source |3|3|
| Count-cap rejection before generation |3|3|
| Additional byte-cap rejection |0|0|
| Input construction proceeds |74|74|

"Linked" is physical eligibility, not a judgement that the question requires
that caption or that the evidence is sufficient. The73 questions with no linked
table are not evidence that no other useful captions exist: the link builder
deliberately excludes ambiguous/split/unsupported structures.

| Question | Existing role | Added sources | Original packet bytes | Full proposed bytes | Result |
|---|---|---:|---:|---:|---|
|HYU_T4_012|refusal|0|25,529|25,529|Pass; caption already present|
|KBF_T4_045|refusal|1|21,970|23,010|9 sources; reject|
|SAM_T4_029|refusal|1|26,591|27,618|9 sources; reject|
|SKI_T1_068|positive|1|32,209|33,372|9 sources; reject|

Three additions total3,230 UTF-8 bytes:1,040 /1,027 /1,163 bytes, mean1,076.7.
Every affected proposal is comfortably below65,536 bytes. No tokenizer or
model-price estimate is inferred from these byte counts. Of55 positive questions,
1 has a linked table and rejects; of19 refusal questions,3 have linked tables
and2 reject; the3 diagnostic questions have no linked table. A runtime error
is not a correct refusal and these counts are not an answer confusion matrix.

## Existing omission and preservation boundary

MIX_T3_063 has no caption link. Its raw eight-source input is82,579 bytes, so
the unchanged baseline builder omits two whole sources and delivers six sources
at65,435 bytes. This occurs in both saved rankings and is not caused by the
caption feature. It remains a successful input construction with two documented
omissions, not full eight-source preservation.

All154 unconstrained diagnostic proposals preserve every original selected
source object; those exceeding bounds are saved only for measurement and never
delivered. All148 successful bounded packets preserve every baseline-visible
source object. Six executions reject before the intercepted model boundary
(three questions in two rankings); they have no delivered packet and must not
be counted as preserved answers. There are no retries, selection replacements,
capacity increases, truncation or LLM calls.

## Verification and conclusion

The154 actual baseline packets match their saved originals. Count/byte flags,
source sets, source objects and emitted-versus-rejected packet files independently
recompute from the saved proposals. ANN/exact caption dispositions are identical.
Twelve existing caption-contract tests and two documentation authority tests pass.
Input/code/store hashes and final checks are recorded in the local completion
manifest. Provider calls, new embeddings, new retrievals and cost are zero.

Do not activate this sidecar on the default top8 path yet. Preserving eight
existing sources, adding a missing ninth source, and retaining an eight-source
cap cannot all hold at once. A separately scoped next experiment could consider
table/caption bundles during final evidence selection, counting both physical
chunks and their full bytes. That would change selection and can lose other
evidence; it requires explicit preservation/coverage evaluation. No such policy
or runtime change is part of this audit. The previous6/8 versus7/8 result and
COMPLETE_GATE_NOT_MET remain unchanged; no answer-quality gain is established.

## Evidence

- `benchmarks/results/table_caption_capacity_audit_2026-09-30/`: frozen manifest,
  protected hashes, analysis, independent verification and completion/seal.
- `D:/CodexArtifacts/dart-rag-agent/table_caption_capacity_audit_2026-09-30/`:
 154 row results,154 full diagnostic proposals and148 bounded packets.
- [Implementation](table_caption_link_implementation.md),
  [saved production retrieval](full77_v5_retrieval_audit.md),
  [same-query exact-Dense comparison](full77_v5_exact_dense.md).
