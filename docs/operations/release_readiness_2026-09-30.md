# Offline release-readiness review — 2026-09-30

Status: **PASS_OFFLINE_REGRESSION**. The default application now ignores experimental
caption sidecars unless an experimental caller explicitly supplies their path.
This checkpoint verifies local contracts and packaging boundaries, not a release,
fresh provider quality, remote CI, or deployment.

## Change and regression

At the starting working tree, `VectorStoreManager` automatically read
`table_caption_links.json` from its store directory. Merely placing an experiment
artifact there could change the default answer packet or fail startup on malformed
JSON, despite caption adoption remaining blocked.

The constructor now accepts the keyword-only `experimental_caption_links_path`,
defaulting to `None`. Default API/Streamlit construction never supplies it. Default
construction ignores both valid and malformed sidecars. An explicitly requested
file must exist and pass the existing loader before provider/store construction.
Existing source-fingerprint, scope, deduplication and whole-bundle capacity checks
remain in place. No new caption selector, ranking policy or prompt was adopted.

The new default-isolation test failed against the pre-change constructor for both
valid and malformed files, then passed after the change. Explicit experimental
delivery and cache revalidation remain tested. The original SimpleRagAgent caption
hook and caption builder/loader were pre-existing working changes, preserved here.

## Packaging classification

| Group | Disposition |
| --- | --- |
| Parser v5 | Already committed at `6a0c0c41`; no new parser/ingest change |
| Default application | Constructor isolation in `src/storage/vector_store.py` |
| Experimental implementation | Preserve caption processing/storage/ops modules and existing SimpleRagAgent hook; explicit caller path only |
| Tests and current contracts | Default-isolation/early-rejection regressions and matching runtime/code-map guidance |
| Prior experiment reports | Preserve as historical evidence; no score replacement or adoption claim |
| Raw results, local stores and credentials | Exclude from source commits |

The initial inventory contains 74 modified/untracked paths. It is a classification,
not permission to stage them all. Any subsequent packaging must include the source
dependency group together: `src/agent/simple_rag.py`, `src/storage/vector_store.py`,
`src/storage/table_caption_links.py`, `src/processing/table_caption_links.py`,
`src/ops/build_table_caption_links.py`, and `tests/test_table_caption_links.py`.
Several are currently untracked; packaging only tracked diffs would omit required
imports. Current contracts/handoff documents belong with the change; experimental
reports can be reviewed separately. No staging, commit, push or deployment occurred.

## Verification

| Check | Result and boundary |
| --- | --- |
| Focused app/API/caption regression | 64 tests pass; local fixtures/mocks |
| Runtime domain-term audit | Pass, 35 reviewed literals |
| Full unittest discovery | 2,177 tests pass, zero failures/errors/skips; 62.67 seconds including harness setup |
| Documentation authority after handoff update | 2 tests pass |
| Saved public demo | 5 saved cases match manifest; integrity only |
| Local store | Manifest compatible/ready; 15,608 graph IDs equal persisted vector-record IDs across 11 filings |
| Preservation | 3,422 protected files unchanged, including source store, local settings and prior experiment evidence |

The store inventory used immutable, read-only SQLite and JSON. It did not open the
source store through native Chroma, execute production ANN queries or start a
production server. Temporary fixture integrations in the test suite are separate.
Provider calls, new embeddings and paid cost are zero. Arithmetic and semantic
citation support are still not validated by the default RAG runtime.

The offline harness initially blocked Windows asyncio's internal loopback
socketpair, yielding 20 errors, then four errors where existing tests wrapped
`socket.connect`. These were harness failures, preserved in separate logs. The
final guard verifies the original stdlib socketpair frame, exact connecting socket
and its listener address through wrappers. It allows that internal pair while
blocking external and unrelated loopback connections. The affected-module check
passed 53 tests before the final full run. Final full run observed no blocked
connection attempts and allowed 46 internal socketpairs. No product contract was
weakened to repair the harness.

## Evidence and remaining boundary

Local receipts: `benchmarks/results/release_readiness_2026-09-30/` contains the
initial manifest/inventory, pre-change copies, red test, focused/full logs,
network-guard controls, read-only store inventory, preservation verification and
completion seal. These ignored artifacts are not source-commit candidates.

The [caption answer comparison](../evaluation/table_caption_answer_validation.md)
remains `COMPLETE_GATE_NOT_MET`; the
[citation criteria review](../evaluation/citation_support_review.md) remains an
offline review of exposed saved responses. The earlier
[implementation checkpoint](../evaluation/table_caption_link_implementation.md)
describes the former auto-load behavior; this checkpoint and the current runtime
contract supersede that activation behavior without rewriting its evidence.

Local regression is complete. Source packaging/commit review is the remaining
delivery step. Remote CI, clean-checkout packaging and deployment are **NOT_RUN**
at this checkpoint. Another paid benchmark is not required to finish this boundary
fix, and no follow-up experiment is automatically authorized.
