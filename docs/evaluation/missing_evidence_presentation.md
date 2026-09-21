# Missing-evidence explanation and citations

The final assembler now explains an explicit missing-evidence outcome using
the existing selected report scope and each missing output's declared period.
It does not expose model rationale, infer a source's time coverage, or convert
missing evidence into a claim that an entire report lacks the information.
This fixes the presentation gap observed in the [prior live diagnostic](unavailable_2024_result.md).

## Contract

- The executor must report missing obligations with no validation or execution
  errors. Ambiguous outputs and error-derived omissions retain their existing
  fallback; transport/admission exceptions still propagate without an answer.
- The final assembler copies the explicit singular selection's company, report
  year and type into a scope description. An inventory or multi-source selection
  uses generic selected-material wording, never the top-level report as its only
  source. No selection means no invented report. Filing year and requested
  measurement period remain separately labelled, even when equal.
- Missing output labels and their declared periods are rendered through reviewed
  Korean/English policy templates. No year comparison, topic/company branch,
  source text search, model schema change or extra model call is introduced.
  Planner interpretation is not certified by repeating its declared period.
- Partial/incomplete semantic answers with missing outputs cite accepted evidence
  only. Retrieved-document anchors remain available in review trace and are not
  presented as evidence supporting an unresolved output. Accepted partial claims
  retain their own evidence; healthy complete citation behavior is unchanged.
- One final assembly supplies the answer, structured answer, formatted result
  and aggregate ledger. Canonical programs, source candidates, selected values,
  formula/display behavior and missing/error status remain unchanged.

The saved missing-evidence response now renders locally as:

> 선택한 자료 범위(NAVER / 보고서 연도: 2023 / 사업보고서)에서 조회된 근거만으로는 다음 요청을 확인할 수 없습니다: 2024년 연결 영업활동현금흐름 (요청 기간: 2024년 1월 1일부터 2024년 12월 31일까지). 자료 전체에 해당 정보가 없다는 뜻은 아닙니다.

This is selection and request context, not a new assertion that the report covers
only one year. Its absence claim remains limited to retrieved excerpts. No amount,
zero, forecast, rejected source or diagnostic explanation becomes answer evidence.

## Provider-free evidence

**11 new contracts and 95 focused tests pass.** They cover distinct/equal/blank/
non-calendar periods, Korean/English rendering, narrative missing outputs,
unscoped/inventory selection, failed and ambiguous programs, execution errors,
partial accepted values, citation authority and final/ledger consistency.
The first test-only ledger fixture omitted its existing required `operation`
field; adding that field fixed the fixture without changing product validation.
The runtime domain audit passes with **83 reviewed literals** unchanged.

**23 exact saved-replay assertions pass** with external connections blocked:

| Preserved live input | Local outcome | Comparison with preserved answer |
| --- | --- | --- |
| Unsupported 2024 actual | Incomplete; selected report and requested full period explained | No amount added; eight retrieval-only citations become zero; all eight retrieved documents remain in review |
| Consolidated/separate cash flow | Complete | Both values, answer text, accepted rows and ten citations unchanged |
| Dividend policy/status | Complete | Answer text, accepted rows and four citations unchanged |

Replays reuse the exact saved program, catalog and obligations. Source validation
matches the original result; a reconstructed V2 envelope then protects the actual
executor, final assembler and ledger. All three ledgers remain `ok`. There is no
sampled model response, native vector search, store opening or rewritten old run.
The prior paid missing-evidence result remains **partial**; the local correction
does not retroactively upgrade it or establish general semantic accuracy.

**Full unittest: 2,130/2,130 pass**, no skips (87.262 seconds); import/topology/
documentation gate: **24/24 pass**. The initial full-suite discovery command
rejected the namespace test directory before executing tests; using its existing
start-directory discovery convention fixed the harness. Both records are retained.
All **11,061 predecessor artifacts**, **24 original store files** and local settings
retain their hashes. Only four runtime/config owners and the new tests change.
New API calls and added accounting are **zero**; shared accounting remains
**18.74967693 / 20.07 USD**, with **1.32032307** remaining and zero pending.

The remaining Planner blank-period/default-year concern is independent. Future
coverage should distinguish a true missing source, an ambiguous interpretation
and a contract/provider failure; none should be converted to an unsupported
number or full-report absence. This change grants no fresh ingest or paid retry.

Local artifacts: [focused tests](../../benchmarks/results/missing_evidence_presentation_2026-09-21/focused.json),
[exact replay](../../benchmarks/results/missing_evidence_presentation_2026-09-21/replay_result.json),
[corrected local answer](../../benchmarks/results/missing_evidence_presentation_2026-09-21/unavailable_2024_actual_replayed_answer.json),
[handoff](../../benchmarks/results/missing_evidence_presentation_2026-09-21/handoff.json).
