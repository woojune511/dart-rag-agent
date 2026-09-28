# DART RAG saved-example demo

**[Open the web demo](https://woojune511.github.io/dart-rag-agent/)** — choose a saved
question and inspect its answer and cited source text. There is no question input,
backend or provider call.

## Open offline

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
The downloadable file offers the same examples as the hosted site.

## What is included

These are five selected saved outputs from the
[2026-09-22 application evaluation](https://github.com/woojune511/dart-rag-agent/blob/2f3aea223a70648a700092604990f7b0392bf69e/docs/evaluation/simple_rag_final_result.md):

| Case | Why included |
| --- | --- |
| F02 | Successful lookup; distinguish issued, authorized and circulating shares |
| F05 | Successful calculation on source review; runtime arithmetic remains unverified |
| F10 | No evidence in explicit company scope; abstains without answer generation |
| F11 | Model abstention with a separately recorded wording caveat |
| F12 | Failed abstention; annual-average revenue substituted for actual daily revenue |

F02 opens first. Use the five case buttons or the question selector, then expand
its citations. The failure (F12) and caveated abstention (F11) are equally accessible. Exact question,
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

For the evaluated application and its limits, see the application evaluation
report linked above.


## Publication

The `Publish saved-example demo` workflow verifies the package and publishes only
`index.html`, `provenance.json` and `.nojekyll`. No store, settings, source code,
raw run bundle or credential is included in the Pages artifact. Pull requests
build the artifact; deployment runs only on `main`. GitHub Pages must use the
GitHub Actions source in repository settings.

The original public package came from revision `2f3aea223a70648a700092604990f7b0392bf69e`.
This UI changes the initial selection from F12 to F02 and adds case navigation;
all saved questions, answers, source texts, reviews and evaluation metrics remain
unchanged. The payload hash changes only because `initial_case` changes. Linked
reports are pinned to that source revision, since the compiled runtime on `main`
is a separate version. Publishing the viewer does not migrate the runtime.
