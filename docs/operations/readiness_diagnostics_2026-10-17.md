# Readiness diagnostics and restart verification

Verified on 2026-10-17. Readiness diagnostics now record the initial manifest
assessment and the final source-integrity assessment in the existing application
log. The first temporary startup failure remains unexplained because its detailed
result was not saved. Later successful startup verifies logging, not that cause.

## Logging behavior

`src/api/services.py` emits `Store readiness:` with `stage`, `status`, `reason`,
`ready`, `degraded`, expected/actual store identity and `source_integrity`.
`stage=manifest` records the initial result before store initialization;
`stage=refresh` records the existing integrity check result and final readiness.
`source_integrity=null` means the check was not run. Normal results use INFO;
failed or degraded results use WARNING. Missing IDs and caught read-error reasons
are preserved without an additional integrity scan, retry or readiness rule.

The focused 34 tests passed, covering missing-source diagnostics, caught index
read errors, successful integrity and startup rejection. They verify the existing
check is called once and readiness still rejects incomplete sources.

## Local restart result

The authorized local restart started API and Streamlit once each, with zero
provider calls and zero HTTP probes. Startup logs and OS port ownership confirmed
both services were listening. Manifest and refresh records were `compatible`,
`ready=true`, `degraded=false`; integrity was complete with empty missing-source,
missing-payload and unidentified-vector lists.

This observation used the existing local v12 working tree and
`data/app_full11_2023_v12_20261017`, collection `dart_reports_v12_full11_2023`.
The v12 parser changes and store are separate, uncommitted work; this logging
change does not adopt them or include credentials, stores or raw run artifacts.
No answer-quality evaluation was run.

## File bytes and stored data

- **SQLite bytes changed:** Chroma startup added `acquire_write` row `(8,1)` and
  advanced two header counters from 555 to 556. Exactly 10 bytes of
  `chroma.sqlite3` changed. Whole-store byte identity therefore did not pass.
- **Stored data was preserved:** reversing only those internal differences in
  memory reproduced the exact pre-restart database SHA-256. All other 10 store
  files, including HNSW files and source sidecars, were byte-identical. A read-only
  copy also matched saved build hashes for all 16,051 text/metadata records and
  644 queued vectors. The diagnostic did not restore or rewrite the active store.

`.env`, source and tests were unchanged during restart. The later documentation
closeout preserved all 11 current store files and `.env` byte-for-byte and made
no additional API call or restart. The current internal SQLite counters remain
in place. No follow-up execution or performance experiment is queued.

## Local evidence

These bundles under `benchmarks/results/` remain local and are not committed:

- `readiness_diagnostic_logging_2026-10-17/completion.json`: focused test result.
- `readiness_restart_verification_2026-10-17/`: `completion.json`,
  `api_stderr.log` (readiness lines 4/10), `readiness_records.json`,
  `sqlite_byte_change_diagnosis.json` and `stored_content_verification.json`.
- `readiness_status_closeout_2026-10-17/completion.json`: documentation checks and
  preservation of the post-restart state.
