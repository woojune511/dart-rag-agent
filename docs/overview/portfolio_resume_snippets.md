# Portfolio Resume Snippets

Use these as concise resume, portfolio, or LinkedIn project descriptions. The
wording is intentionally scoped: it presents the project as applied
systems/research-engineering work, not as a new model architecture or a general
TableQA SOTA result.

## One-Line Version

Built a contract-driven Agentic RAG runtime for Korean DART filings that
accepts numeric financial answers through structured evidence, deterministic
calculation traces, critic reports, and reproducible reviewer gates.

## Three-Bullet Version

- Designed a financial-document RAG runtime where accepted numeric answers
  expose source evidence, required operands, formula execution,
  `resolved_calculation_trace`, critic acceptance, and task/artifact integrity.
- Separated LLM semantic planning from deterministic execution: LLMs handle
  intent/concept interpretation, while code handles operand binding, arithmetic,
  unit handling, dedupe, validation, and final rendering.
- Validated the design with trace-based gates and store-fixed benchmark
  refreshes; the latest expanded ablation slice reports structural
  full-system `8 / 9` numeric PASS versus plain retrieval `4 / 9`.
- Reproduced structural separators in `POS_T1_057`, `SAM_T3_028`,
  `CEL_T1_013`, and `SKH_T3_080`, while keeping `SKH_T1_060` as the explicit
  residual follow-up case.

## Technical Portfolio Version

Implemented a contract-driven multi-agent RAG runtime for financial QA over
DART filings. The system models Orchestrator, Analyst, Researcher, and Critic
handoff through typed `tasks`, `artifacts`, `evidence_pool`, `critic_reports`,
and `task_artifact_trace` state rather than free-form agent chat. Numeric
answers are accepted only after source-backed operand binding, deterministic
formula execution, canonical trace rendering, and artifact/critic gate checks.

## Research-Engineering Version

Investigated failure modes in financial-document RAG where answer-level
faithfulness can mask wrong row selection, unit-scale drift, stale calculation
mirrors, or missing operand provenance. Built a value-cell-first structured
metadata and runtime-contract approach that preserves table/row context through
retrieval, extraction, calculation, and final rendering. Evaluation uses
trace-based numeric grounding rather than final-text exact match alone.
In structural diagnostics, historical hard replays and the latest expanded
refresh show the same engineering concern: relevant values can be retrieved,
but final operand selection, sign/display handling, or mixed answer composition
can still drift unless the runtime preserves structured traces through final
rendering.

## Conservative Version

Built and evaluated an evidence-first RAG prototype for DART financial filings,
focused on making numeric answers auditable. The project combines
structure-aware retrieval, deterministic numeric execution, multi-agent artifact
handoff, and reviewer-facing gates. Current results support a narrow claim:
structured provenance and trace-based gates make operand, unit, and period-row
drift visible. The latest expanded comparison supports a narrow structural
claim, not a full-benchmark claim.

## Korean Short Version

한국 DART 공시 문서 기반 재무 QA를 위한 contract-driven Agentic RAG runtime을
구축했습니다. 최종 답변 텍스트만 평가하지 않고, source evidence, operand,
formula execution, `resolved_calculation_trace`, critic report,
`task_artifact_trace`를 함께 노출해 numeric answer를 감사 가능하게 만드는 데
초점을 두었습니다. LLM은 intent/concept 해석과 planning에 사용하고, 산술,
단위 처리, operand binding, validation은 deterministic code path로 분리했습니다.

## Avoid These Claims

- "Achieved SOTA on financial TableQA"
- "Eliminated hallucination"
- "Built a new neuro-symbolic algorithm"
- "Used cell-level embeddings"
- "RAGAS proved the final system quality"

Safer alternatives:

- "Made numeric financial RAG answers inspectable through runtime contracts"
- "Moved arithmetic and unit handling out of free-form generation"
- "Preserved value-cell-first structured metadata through retrieval and
  extraction"
- "Used trace-based numeric grounding gates for acceptance"
- "Used store-fixed benchmark refreshes as promotion gates, including a latest
  expanded refresh that separates structural full-system `8 / 9` from plain
  retrieval `4 / 9`, while leaving the remaining structural residual visible"
