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
- Validated the design with trace-based gates and an expanded structural
  ablation: structural full-system avg numeric `1.000` / faithfulness `1.000`
  vs plain retrieval avg numeric `0.833` / faithfulness `0.875`, with
  separating failures caused by operand-binding drift in the plain path.
- Ran a hard structural-vs-plain replay after ontology/runtime fixes:
  structural `5 / 5` numeric PASS vs plain `4 / 5`, isolating a current/prior
  period row-binding failure in `SKH_T1_060`.

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
In the hard replay, the plain baseline passed four of five hard questions but
failed a period-ambiguous borrowing ratio by selecting prior-period rows;
structural metadata preserved the current-period rows and closed the case.

## Conservative Version

Built and evaluated an evidence-first RAG prototype for DART financial filings,
focused on making numeric answers auditable. The project combines
structure-aware retrieval, deterministic numeric execution, multi-agent artifact
handoff, and reviewer-facing gates. Current results support a narrow claim:
structured provenance reduces operand, unit, and period-row drift on
representative expanded and hard structural cases, while broader benchmark
generalization remains future work.

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
- "Measured a hard replay where structural retrieval passed `5 / 5` numeric
  questions versus plain retrieval `4 / 5`, with the delta traced to
  current/prior row binding"
