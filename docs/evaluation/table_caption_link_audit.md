# Table and caption linkage audit

Date: 2026-09-30. Status: **COMPLETE_OFFLINE_DIAGNOSTIC**.

The previous NAVER selection loss has a reproducible structural explanation:
the as-of-date/unit caption is a separate four-column table. It survives in the
store, but does not pass the parser's at-most-three-column context forwarding
guard. Selecting only the numeric table therefore omits its separate caption.
This audit verifies a conservative physical-link subset across the existing
11 reports. It does not change the parser, store, selector, prompt or product.

## Source and owner boundary

- `src/processing/financial_parser.py:355` accepts compact context tables with
  at most two rows and three columns. `_extract_table_unit_suffix` at line382
  has the same column limit. The four-column caption fails both guards.
- `src/processing/block_collection.py:119-168` emits an unrecognized caption
  as an ordinary table; the next table receives only a recognized pending hint.
- `src/storage/structure_graph.py:104-120` sets `described_by_uid` from the
  previous non-table paragraph. It does not represent table-to-caption ownership.
  Of4,880 existing description edges,3,759 are not immediate sibling edges;
  none cross stored parents. These counts do not establish semantic errors:
  one paragraph may introduce several tables.
- NAVER receipt20240318000844 has caption22:2 and data table23:3 in the same
  `I. 회사의 개요 > 4. 주식의 총수 등` parent. The raw paths end in
  `LIBRARY[1]/TABLE-GROUP/TABLE[1]` and `TABLE[2]`. Caption grid is
  `(기준일 : | 2023년 12월 31일 | ) | (단위 : 주)`.
  Both forwarding hints and the target's `described_by_uid` are absent.

The observed failure belongs to parser/evidence linkage and source delivery.
The caption was not deleted. A generic graph paragraph edge is not a safe
substitute for a verified caption link.

## Frozen diagnostic rule and inventory

Before inventory, freeze `scope.json` and `link_rules.py` hash. No question,
gold, company or benchmark ID is an input to the eligibility rule. Only tables
of at most2 rows/8 columns containing exclusively parenthesized explicit date
and/or unit declarations qualify. Validate calendar dates, reject duplicate
labels or mixed data/prose, and require the next XML sibling to be a data table.
Require a unique whole-table text match, the immediately preceding stored
caption in the same report/parent, and persisted XML locators/document hashes
for both nodes. Preserve complete source text and metadata. Do not infer a
period, scope or unit missing from the source.

The production XML loader sanitizes XML-like prose before recovery parsing.
The first diagnostic run omitted this step and stopped on a Hyundai XPath
mismatch before publishing an inventory. `harness_correction.json` records
the error and old script hash. The corrected diagnostic uses the same
sanitizer/parser settings; eligibility was unchanged. A second check uses
the production loader directly and verifies all178 pairs and no intervening
non-whitespace XML tail text.

| Report | Raw caption candidates | Verified stored pairs |
|---|---:|---:|
| 삼성전자 | 145 | 21 |
| 현대자동차 | 116 | 11 |
| LG에너지솔루션 | 119 | 3 |
| NAVER | 128 | 12 |
| 셀트리온 | 171 | 5 |
| SK하이닉스 | 113 | 17 |
| SK이노베이션 | 319 | 54 |
| 카카오뱅크 | 80 | 19 |
| POSCO홀딩스 | 276 | 16 |
| KB금융 | 406 | 14 |
| 카카오 | 200 | 6 |

There are2,073 raw label candidates and178 verified stored pairs. Other
dispositions:1,109 ambiguous/split targets,598 mixed or mismatched predecessor
bodies,139 following tables outside the data-table subset,35 without an
immediate table sibling,14 without a stored predecessor. These are conservative
exclusions, not1,895 parser failures. Caption recall and semantic precision
are not measured.

Among178 accepted pairs,155 captions have four columns;16 have one and7 have
two. None receive the standalone-context hint;23 do receive the existing unit
suffix, so the entire accepted set is not a missing-unit population.
The same assistant inspected12 deterministic samples: one per report and the
exposed NAVER case. Original normalized grids and persisted linkages show no
contradictory adjacent context in these samples. This is a structural spot
check, not an independent semantic evaluation or population precision claim.

## Whole-source delivery checks

All178 caption/table pairs fit actual `SimpleRagAgent` packet construction
with two physical chunks, maximum9,426 UTF-8 bytes (fixed generic audit query).
Sources retain their original IDs, numbers, body text, unit declarations and
metadata. The diagnostic rejects a complete expansion if it exceeds eight
physical sources or65,536 bytes; it never truncates or drops another source
to make room. The byte figure is not a tokenizer or model-cost estimate.

All24 prior A/B answer-input packets reconstruct exactly before expansion.
The isolated replay adds a verified caption only from each frozen candidate
pool, keeps every existing source object, and deduplicates shared captions.
All24 expanded packets fit; only the two NAVER B packets add a source:
one chunk/4,521 bytes becomes two chunks/5,736 bytes (+1,215 bytes,+26.9%).
The NAVER A packet already has the caption; its order changes to put the
caption immediately before the table, with identical contents/count/bytes.

This replay restores physical caption delivery only. No model reread, answer
generation, gold rescore, or replacement of prior results occurred. The prior
comparison remains6/8 versus7/8 twice, **COMPLETE_GATE_NOT_MET** due to one
stable regression. It must not be relabeled8/8 based on these packets.

## Validation and limitations

- Nine blocked-network contract tests pass: fragmented four-column labels,
  mixed/invalid labels, ambiguous matching, scope, nonadjacency, intervening
  XML paragraphs, contaminated stored bodies, candidate/count bounds and
  real whole-source packet overflow. Network attempts0.
- Production-loader cross-check178/178; sample review12; pair packets178/178;
  existing input reconstruction24/24 and expansion24/24.
- Two documentation authority tests and preserved-input checks are recorded
  separately in `completion.json`; protected inputs count2,246.
- Provider/embedding/ingest calls0; USD0. No Chroma open, runtime edit, store
  rebuild, retrieval, LLM-quality evaluation or product adoption.

Next candidate is a separately scoped, provenance-backed caption relationship
and whole-source bundle contract, with bounded exclusions for split or ambiguous
tables. This audit supports implementation feasibility of the narrow subset.
It does not justify widening a column threshold alone, adopting a selector,
or automatic paid follow-up. Fresh question/report evaluation would still be
needed to establish model benefit after freezing the mechanism.

## Local evidence

- `benchmarks/results/table_caption_link_audit_2026-09-30/`: frozen scope/rules,
  harness correction, inventory/packing summaries, secondary checks, sample
  review, tests, protected hashes, completion and seal.
- `D:/CodexArtifacts/dart-rag-agent/table_caption_link_audit_2026-09-30/`:
  full raw/stored pairs, rejected-candidate inventory, existing graph edges,
  deterministic sample, pair packet sizes and24 diagnostic replay packets.
- Prior [final-selection result](final_selection_result.md) and all its frozen
  sources, gold and responses remain unchanged. Local artifacts are not staged.
