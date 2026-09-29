# Commit packaging review — 2026-09-30

Status: **READY_FOR_LOCAL_COMMIT_REVIEW**. Two ordered review patches separate the
caption implementation from accumulated experiment records. No actual index
staging, branch commit, push, provider call or deployment was performed.
Base: `6a0c0c41360eca0511ad889ce4875059018fff77`.

## 1. Code, tests and runtime contracts — 9 files

Suggested title: `feat: keep verified caption attachments explicitly opt-in`

The default application ignores caption sidecar presence. An experimental caller
can explicitly request validated physical caption attachments; invalid bindings,
scope conflicts and whole-bundle capacity violations fail before generation.
This packages the existing experimental implementation and the later isolation
fix together; it does not adopt the caption selector or claim a quality gain.

| Files | Reason to include together |
| --- | --- |
| `src/agent/simple_rag.py` | Whole-caption packet assembly, deduplication and capacity checks |
| `src/storage/vector_store.py` | Explicit constructor opt-in and validated lookup |
| `src/storage/table_caption_links.py` | Loader and source-binding revalidation required by the store import |
| `src/processing/table_caption_links.py` | Conservative original-XML caption binding |
| `src/ops/build_table_caption_links.py` | Offline sidecar generation without opening Chroma |
| `tests/test_table_caption_links.py` | Attachment, stale-source, default-isolation and fail-before-generation contracts |
| `AGENTS.md` | Default/experimental operating boundary |
| `docs/architecture/agent_runtime_contract.md` | Explicit activation and physical-source constraints |
| `docs/overview/codebase_map.md` | Experimental module ownership |

Splitting the constructor from its new imports creates an incomplete commit.
The date/unit labels in the extractor are DART parser-shape terms, not financial
concept routing or benchmark-answer rules. No company/question branches were added.

## 2. Evaluation and handoff records — 67 files

Suggested title: `docs: record bounded RAG experiments and offline verification`

This contains `CONTEXT.md`, current status and experiment history, the prior
untracked evaluation/operations reports, and this packaging review. It depends on
the first patch. The exact allowlist is stored in the local `plan.json`; every
path in this group is Markdown under `docs/` or `CONTEXT.md`.

Reports keep their original sample/exposure limits and unadopted outcomes.
Packaging/link verification is not a new evaluation of saved answers, source
annotations or provider quality. Historical reports describe their own checkpoints;
the current contract supersedes the old caption auto-load behavior.

## Verification and reproducibility boundary

- The prior [offline regression](release_readiness_2026-09-30.md) seal was verified
  before packaging. Runtime, test and prior report contents are unchanged by this
  review; only current handoff/history and this new report were updated.
- The first candidate Git tree was exported without the local `.env`, stores or
  recent ignored experiments. Focused **64 tests pass**, and all five caption/app
  modules resolve from the export. The 35-literal runtime domain audit passes.
- This used the existing virtualenv. It checks source packaging, **not a fresh
  dependency installation, production startup or remote CI**. No provider calls.
- Local Markdown file targets in the proposed changed docs resolve to packaged
  files except 69 references to intentionally local `benchmarks/results/**`
  evidence. Those raw artifacts are excluded. URL availability and heading-anchor
  validity are outside this file-target check; no historical links were rewritten.
- Both ordered patches are checked against separate temporary Git indexes; their
  resulting trees must match the proposed trees. The real index and HEAD remain
  unchanged. `.env`, local stores and newly generated experiment artifacts are
  excluded from both patches. Already tracked historical fixtures in HEAD remain.

Local receipts: `benchmarks/results/commit_packaging_2026-09-30/` contains
`plan.json`, `01-caption-opt-in.patch`, `02-evidence-docs.patch`, Git-export test
results and completion hashes. These review artifacts are not commit candidates.

The prepared boundary ends at local commit review. Full 2,177-test regression is
the preceding unchanged-code checkpoint; it was not repeated for this packaging
step. New-environment dependency install, remote CI, commit, push and deployment
remain **NOT_RUN**. The caption answer comparison remains `COMPLETE_GATE_NOT_MET`.
