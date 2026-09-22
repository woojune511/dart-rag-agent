# Simple-RAG saved-response walkthrough

The current product story is structure-aware ingest → scoped hybrid retrieval →
one answer call → inspectable citations and explicit validation limits. The
[final application run](../evaluation/simple_rag_final_result.md) supplies the
examples here. This walkthrough presents saved actual answers, not a new live
query or the older compiled-workflow fixture.

## Open the packaged viewer

Download or clone the repository and open [demo/index.html](../../demo/index.html)
in a browser. From the repository root on Windows:

```powershell
Start-Process (Resolve-Path 'demo/index.html').Path
```

The standalone file needs no installation, server, credentials, store or network.
It contains exact saved answers and all their cited source texts, per-case timing
and separate reviewer notes for **five selected examples**: F02/F05/F10/F11/F12.
The selection was made after the final run to show successful lookup/calculation,
both abstentions and the failure. The displayed aggregate metrics describe the
full 12-question panel, not a success rate for these five examples.

This viewer is included in Git; it does not start the app or call a provider.
The original 12-case viewer and raw bundle remain local ignored artifacts.
GitHub's HTML source preview is not a running demo; open the downloaded file.
See [demo/README.md](../../demo/README.md) for platform-independent instructions
and the optional standard-library data-integrity check. No hosted deployment is implied.

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

The viewer is a reading aid. The [public manifest](../../demo/provenance.json)
identifies the selected cases, original result hashes and canonical data hash.
`python -I -S demo/verify.py` checks the packaged data using only the standard
library. It does not independently verify upstream execution or answer quality.
The [result report](../evaluation/simple_rag_final_result.md) links the complete
local bundle; those raw logs are not distributed. Reproduction here means opening
the same saved answers and sources, not repeating the evaluation or a paid sample.

For implementation review, follow the
[application contract](../architecture/agent_runtime_contract.md) and
[code map](codebase_map.md). The older
[compiled fixture demo](portfolio_demo_walkthrough.md) remains a separate
historical contract example. Its Planner/Compiler/calculation guarantees do not
describe the default simple-RAG application.
