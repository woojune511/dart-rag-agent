# DART RAG offline demo

Open [index.html](index.html) in a browser after downloading or cloning this
repository. No install, Python, API key, `.env`, store or server is needed to view
it. JavaScript must be enabled. All viewer code and data are inside that file;
it makes no network or provider requests.

On Windows, from the repository root:

```powershell
Start-Process (Resolve-Path 'demo/index.html').Path
```

On other systems, open `demo/index.html` with your browser's **Open file** command.
GitHub's source preview does not execute HTML; download/clone and open the file.
This repository artifact does not imply a hosted deployment.

## What is included

These are five selected saved outputs from the
[2026-09-22 application evaluation](../docs/evaluation/simple_rag_final_result.md):

| Case | Why included |
| --- | --- |
| F02 | Successful lookup; distinguish issued, authorized and circulating shares |
| F05 | Successful calculation on source review; runtime arithmetic remains unverified |
| F10 | No evidence in explicit company scope; abstains without answer generation |
| F11 | Model abstention with a separately recorded wording caveat |
| F12 | Failed abstention; annual-average revenue substituted for actual daily revenue |

F12 opens first. Select another question and expand its citations. Exact question,
answer, abstention, caller scope, validation labels and all six cited chunk texts
are retained, together with per-case timings and separate assistant reviewer notes.
Sources are stored parser text, including contextual prefixes, not rendered DART XML.
Model Markdown is shown literally to preserve the saved answer.

The top metrics describe the **full 12-question evaluation**, not an accuracy
estimate from this selection. Both the final panel and review use two familiar
NAVER filings; this is not independent human gold or unseen-company validation.
No new model call occurs when opening or selecting a case.

Raw provider logs, uncited retrieval contexts, local stores, credentials and
budget history are excluded. The full local evaluation bundle remains separate.

## Optional data-integrity check

Python 3, standard library only, from the repository root:

```bash
python -I -S demo/verify.py
```

Expected output:

```text
PASS: 5 saved cases match the public data manifest.
Integrity only; no provider calls, runtime execution or new quality evaluation.
```

The [manifest](provenance.json) hashes canonical JSON, so Git line-ending changes
do not affect the check. The hash binds embedded data to the included manifest;
it does not authenticate either file or attest to an upstream run. Original
result hashes are provenance references: the unpublished raw files are required
to independently compare them. The checker does not recalculate full-panel
metrics or assess semantic correctness. Browser behavior is checked separately.

For the architecture and tradeoffs, start with the
[one-page introduction](../docs/overview/portfolio_one_pager.md).
