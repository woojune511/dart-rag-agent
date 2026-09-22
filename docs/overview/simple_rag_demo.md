# Simple-RAG saved-response walkthrough

The current product story is structure-aware ingest → scoped hybrid retrieval →
one answer call → inspectable citations and explicit validation limits. The
[final application run](../evaluation/simple_rag_final_result.md) supplies the
examples here. This walkthrough presents saved actual answers, not a new live
query or the older compiled-workflow fixture.

## Open the local viewer

Open [demo.html](../../benchmarks/results/simple_rag_final_2026-09-22/demo.html)
in a browser. From this repository on Windows:

```powershell
Start-Process (Resolve-Path 'benchmarks/results/simple_rag_final_2026-09-22/demo.html').Path
```

The standalone file needs no server, credentials or network. It contains the
exact saved answer text, cited source text, per-case timing and separate reviewer
notes for all 12 questions. It does not start the app or call a provider. The
viewer and raw run bundle are local ignored artifacts, so a fresh Git clone
contains this report/walkthrough but not the viewer. No publication of the raw
bundle or deployment is implied.

## Five-minute route

1. **F12, the initial selection:** read the daily-revenue request and model answer,
   then expand the annual revenue source. The formula is correct but the requested
   daily fact is unavailable. The reviewer marks failure even though the source
   ID passes and the model adds an average-value caveat.
2. **F02:** compare issued, authorized and circulating shares with the cited table.
   This shows why full source context and explicit filing scope matter.
3. **F05:** inspect the employee counts, inclusion/exclusion conditions and 40.5%
   answer. The calculation is correct on source review, while the app truthfully
   labels arithmetic execution and semantic validation as absent.
4. **F10, then F11:** distinguish empty-scope abstention without generation from
   model abstention after retrieval. F11's period explanation has a separate
   faithfulness caveat; successful abstention does not erase it.
5. Read the [result table and limits](../evaluation/simple_rag_final_result.md):
   positives 9/9, safe abstention 2/3, 4.02 s per question and approximately
   USD0.208 for the run. The questions use two familiar NAVER filings and assistant
   review, not independent gold or unseen-company validation.

Answer text is shown literally, including model Markdown, to keep inspection
faithful to the saved response. Source sections expand without changing the
record. The review column is an offline assessment, not a runtime guarantee.

## Engineering evidence

The viewer is a reading aid. The [result report](../evaluation/simple_rag_final_result.md)
links the frozen questions/rubric, request/response records, pre-review hash map,
usage accounting and browser checks. Reproduction means inspecting those saved
inputs and outputs locally; repeating a paid sample is neither necessary nor
authorized by this walkthrough.

For implementation review, follow the
[application contract](../architecture/agent_runtime_contract.md) and
[code map](codebase_map.md). The older
[compiled fixture demo](portfolio_demo_walkthrough.md) remains a separate
historical contract example. Its Planner/Compiler/calculation guarantees do not
describe the default simple-RAG application.
