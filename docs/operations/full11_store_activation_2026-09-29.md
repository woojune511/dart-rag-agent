# Eleven-report application store activation

Status: **PASS_ACTIVATED**, 2026-09-29. The user authorized activating the
rebuilt store separately from the preceding strict answer-quality gate.
Only two local `.env` settings changed:

| Setting | Active value |
| --- | --- |
| `DART_STORE_PATH` | `C:/Users/geonj/Desktop/dart-rag-agent/data/app_full11_2023_20260929` |
| `DART_COLLECTION_NAME` | `dart_reports_v3_full11_2023` |

All other dotenv bytes are preserved. Runtime, prompt and embedding model are
unchanged. API and Streamlit share the same settings/service constructor.

## Verification

Actual FastAPI lifespan initialization, using the changed `.env` without store
overrides, completed in an in-process TestClient. Readiness returned HTTP200,
compatible parser schema v3 and no degraded mode. The companies endpoint returned
all11 expected companies, one2023 report each, and14,005 chunks with exact expected
per-company counts. Six receipt-scoped searches used actual Chroma dense search,
BM25 and RRF with the exact query vectors saved in the preceding regression.
All six required witnesses appeared in top8; the KB/Samsung witnesses contain
the corrected heading and exclude the stale subsidiary/division heading.

New provider calls, answer generations, embeddings, ingest and API cost are all0.
External network connections and requests were blocked. Windows asyncio's local
loopback socketpair remained permitted. The first harness attempt blocked that
socketpair before app initialization; its failure log is retained. Only the
verification harness changed before the successful29.90s run.

No app server was running before activation. The in-process verification closed
normally; no persistent server was started. The next normal application startup
will use this store. Streamlit's interactive browser UI was not exercised.

762 protected source, old-store and preceding experiment files retain their
hashes. Opening Chroma changed the target `chroma.sqlite3` file hash; no files were
added or removed, and graph, table payloads, manifest and vector index files are
byte-identical. This check is operational readiness and scoped retrieval evidence,
not a fresh full vector/database equivalence audit.

## Quality boundary and rollback

The preceding [answer regression](../evaluation/heading_scope_answer_regression.md)
remains strict11/12, with the original activation gate unmet. The first KB answer
adds correct domestic ratings without citing their supporting source. This
activation is a subsequent user-authorized storage decision, not a rescoring or
claim that citation support is fixed. No paid follow-up or prompt tuning ran.

The old `data/app_nav_2023_20260916` store is preserved. Local artifacts live in
`benchmarks/results/full11_store_activation_2026-09-29/`: activation and rollback
records, startup/health/company/search evidence, preservation hashes and logs.
No full dotenv contents or secrets are copied into those records.

To restore the exact prior two setting lines, from the repository root:

```powershell
.venv\Scripts\python.exe -X utf8 benchmarks/results/full11_store_activation_2026-09-29/activate.py rollback
```

Rollback refuses to overwrite a dotenv file changed since activation. Its
byte-exact restoration is verified without applying it. The prior v2 store would
again be incompatible with the current parser; rollback restores configuration,
not parser compatibility. Local artifacts and stores are not staged or published.
