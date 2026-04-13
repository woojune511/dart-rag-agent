# Review Findings

## Findings

### High

- Metadata post-filters are skipped when they narrow results down to a single chunk.
  - References: [src/agent/financial_graph.py](src/agent/financial_graph.py) lines 189-211
  - Detail: `section_filter`, `company`, and `year` post-filters are only applied when `len(filtered) >= 2`.
  - Impact: A query that correctly narrows to one matching chunk can still keep broader pre-filter results, which can surface chunks from the wrong company or year in the final answer.
  - Repro note: This is likely when a narrowly scoped question such as a single-company, single-year query matches only one surviving chunk after filtering.

### Medium

- Streamlit year selection is hard-coded and already lags behind the current calendar.
  - References: [app.py](app.py) line 93
  - Detail: The UI offers `range(2024, 2019, -1)`, so newer filing years cannot be selected from the app even though the backend accepts arbitrary years.
  - Impact: Users can believe the system does not support newer filings when the limitation is only in the UI.
  - Repro note: On April 13, 2026, the UI cannot select 2025 business reports or 2026 periodic filings.

- Hybrid search fuses results by raw `page_content`, which can collapse distinct chunks with identical text.
  - References: [src/storage/vector_store.py](src/storage/vector_store.py) lines 124-141
  - Detail: RRF uses `doc.page_content` as the merge key, so repeated table headers or boilerplate text from different companies or years are treated as the same result.
  - Impact: Metadata can be overwritten during fusion, leading to incorrect citations or suppressed sources.
  - Repro note: This is most plausible for repeated disclosure boilerplate or common table fragments across filings.

### Low

- The Streamlit “유형” field for retrieved chunks is not backed by parser metadata.
  - References: [app.py](app.py) lines 269-276, [src/processing/financial_parser.py](src/processing/financial_parser.py) lines 395-403
  - Detail: The UI looks for `chunk_type`, but the parser stores `is_table` instead.
  - Impact: The retrieved chunk inspector shows `—` for type, which makes the debug view less informative.
  - Repro note: This should occur consistently for all retrieved chunks unless another producer injects `chunk_type`.

## Verification Scope

- Static review covered the active app path centered on `app.py`, `main.py`, `src/api/financial_router.py`, `src/agent/financial_graph.py`, `src/storage/vector_store.py`, and `src/processing/financial_parser.py`.
- Major Python files also passed `py_compile`, so the findings above describe behavioral and integration risks rather than syntax errors.
- End-to-end calls against DART, Gemini, ChromaDB, or MLflow were not executed as part of this review.
