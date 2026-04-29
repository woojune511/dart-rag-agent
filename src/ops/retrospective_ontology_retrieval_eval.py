from __future__ import annotations

import argparse
import json
import sys
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from statistics import mean
from typing import Any, Dict, Iterator, List, Optional

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / "src"
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

import agent.financial_graph as financial_graph_module
from agent.financial_graph import FinancialAgent
from ops.evaluator import (
    EvalExample,
    _compute_operand_grounding_score,
    _compute_retrieval_hit_at_k,
    _compute_section_match_rate,
    _example_from_dict,
)
from storage.vector_store import VectorStoreManager

load_dotenv()

DEFAULT_QUESTION_IDS = ["comparison_004", "comparison_005", "comparison_006"]


def _load_results_payload(path: Path) -> Dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Unsupported results payload shape: {path}")
    return payload


def _first_result(payload: Dict[str, Any]) -> Dict[str, Any]:
    results = list(payload.get("results") or [])
    if not results:
        raise ValueError("No experiment results found in source results payload.")
    return dict(results[0])


def _load_examples(dataset_path: Path, question_ids: List[str]) -> List[EvalExample]:
    payload = json.loads(dataset_path.read_text(encoding="utf-8"))
    indexed = {
        str(item.get("id") or ""): _example_from_dict(item)
        for item in payload
        if isinstance(item, dict) and str(item.get("id") or "").strip()
    }
    missing = [question_id for question_id in question_ids if question_id not in indexed]
    if missing:
        raise ValueError(f"Question ids not found in dataset: {missing}")
    return [indexed[question_id] for question_id in question_ids]


def _initial_state(query: str) -> Dict[str, Any]:
    return {
        "query": query,
        "query_type": "",
        "intent": "",
        "target_metric_family": "",
        "format_preference": "",
        "routing_source": "",
        "routing_confidence": 0.0,
        "routing_scores": {},
        "companies": [],
        "years": [],
        "topic": "",
        "section_filter": None,
        "seed_retrieved_docs": [],
        "retrieved_docs": [],
        "evidence_bullets": [],
        "evidence_items": [],
        "evidence_status": "missing",
        "selected_claim_ids": [],
        "draft_points": [],
        "compressed_answer": "",
        "kept_claim_ids": [],
        "dropped_claim_ids": [],
        "unsupported_sentences": [],
        "sentence_checks": [],
        "answer": "",
        "citations": [],
        "numeric_debug_trace": {},
        "calculation_operands": [],
        "calculation_plan": {},
        "calculation_result": {},
        "calculation_debug_trace": {},
        "planner_debug_trace": {},
    }


def _doc_text(doc_tuple: Any) -> str:
    doc = doc_tuple[0] if isinstance(doc_tuple, (tuple, list)) else doc_tuple
    metadata = dict(getattr(doc, "metadata", {}) or {})
    body = str(getattr(doc, "page_content", "") or "")
    table_context = str(metadata.get("table_context") or "")
    return "\n".join(part for part in [table_context, body] if part).strip()


def _top_sections(retrieved_docs: List[Any], limit: int = 5) -> List[str]:
    sections: List[str] = []
    for item in retrieved_docs[:limit]:
        doc = item[0] if isinstance(item, (tuple, list)) else item
        metadata = dict(getattr(doc, "metadata", {}) or {})
        section_path = str(metadata.get("section_path") or metadata.get("section") or "").strip()
        sections.append(section_path)
    return sections


class _RetrievalOnlyOntologyShim:
    def __init__(self, base_manager: Any) -> None:
        self._base = base_manager

    def preferred_sections(self, query: str, topic: str = "", intent: str = "") -> List[str]:
        return []

    def supplement_sections(self, query: str, topic: str = "", intent: str = "") -> List[str]:
        return []

    def query_hints(self, query: str, topic: str = "", intent: str = "") -> List[str]:
        return []

    def __getattr__(self, name: str) -> Any:
        return getattr(self._base, name)


@contextmanager
def _ontology_mode(enabled: bool) -> Iterator[None]:
    original = financial_graph_module.get_financial_ontology
    if enabled:
        yield
        return

    base = original()
    shim = _RetrievalOnlyOntologyShim(base)
    financial_graph_module.get_financial_ontology = lambda: shim
    try:
        yield
    finally:
        financial_graph_module.get_financial_ontology = original


@dataclass
class QuestionOutcome:
    id: str
    question: str
    target_metric_family: str
    retrieval_hit_at_k: float
    section_match_rate: float
    ratio_row_candidates: int
    component_candidates: int
    operand_count: int
    operand_grounding_score: Optional[float]
    calc_status: str
    rendered_value: str
    top_sections: List[str]

    @property
    def calc_success(self) -> float:
        return 1.0 if self.calc_status == "ok" else 0.0

    @property
    def row_candidate_recovered(self) -> float:
        return 1.0 if self.ratio_row_candidates > 0 else 0.0

    @property
    def component_candidate_recovered(self) -> float:
        return 1.0 if self.component_candidates > 0 else 0.0


def _run_question(agent: FinancialAgent, example: EvalExample) -> QuestionOutcome:
    state = _initial_state(example.question)
    state.update(agent._classify_query(state))
    state.update(agent._extract_entities(state))
    state.update(agent._retrieve(state))
    state.update(agent._expand_via_structure_graph(state))

    evidence_result = agent._extract_evidence(state)
    state.update(evidence_result)

    candidate_docs = state.get("seed_retrieved_docs") or state.get("retrieved_docs") or []
    ratio_row_candidates = agent._extract_ratio_row_candidates(candidate_docs, state["query"], state.get("topic") or state["query"])
    component_candidates = agent._extract_ratio_component_candidates(candidate_docs, state["query"], state.get("topic") or state["query"])

    operands_result = agent._extract_calculation_operands(state)
    state.update(operands_result)

    plan_result = agent._plan_formula_calculation(state)
    state.update(plan_result)

    calc_result = agent._execute_calculation(state)
    state.update(calc_result)

    retrieved_docs = list(state.get("retrieved_docs") or [])
    contexts = [_doc_text(item) for item in retrieved_docs]
    operand_grounding_score, _operand_grounding_debug = _compute_operand_grounding_score(
        runtime_evidence=list(state.get("evidence_items") or []),
        contexts=contexts,
        calculation_operands=list(state.get("calculation_operands") or []),
    )

    calculation_result = dict(state.get("calculation_result") or {})
    return QuestionOutcome(
        id=example.id,
        question=example.question,
        target_metric_family=str(state.get("target_metric_family") or ""),
        retrieval_hit_at_k=_compute_retrieval_hit_at_k(example, retrieved_docs),
        section_match_rate=_compute_section_match_rate(example, retrieved_docs),
        ratio_row_candidates=len(ratio_row_candidates),
        component_candidates=len(component_candidates),
        operand_count=len(list(state.get("calculation_operands") or [])),
        operand_grounding_score=operand_grounding_score,
        calc_status=str(calculation_result.get("status") or ""),
        rendered_value=str(calculation_result.get("formatted_result") or calculation_result.get("rendered_value") or ""),
        top_sections=_top_sections(retrieved_docs),
    )


def _aggregate(outcomes: List[QuestionOutcome]) -> Dict[str, Any]:
    def _avg(values: List[Optional[float]]) -> Optional[float]:
        valid = [float(value) for value in values if value is not None]
        return mean(valid) if valid else None

    return {
        "n_questions": len(outcomes),
        "retrieval_hit_at_k": _avg([row.retrieval_hit_at_k for row in outcomes]),
        "section_match_rate": _avg([row.section_match_rate for row in outcomes]),
        "row_candidate_recovery_rate": _avg([row.row_candidate_recovered for row in outcomes]),
        "component_candidate_recovery_rate": _avg([row.component_candidate_recovered for row in outcomes]),
        "avg_operand_count": _avg([float(row.operand_count) for row in outcomes]),
        "operand_grounding_score": _avg([row.operand_grounding_score for row in outcomes]),
        "calc_success_rate": _avg([row.calc_success for row in outcomes]),
    }


def _render_markdown(
    *,
    source_results: Path,
    dataset_path: Path,
    question_ids: List[str],
    baseline: Dict[str, Any],
    proposed: Dict[str, Any],
    per_question: List[Dict[str, Any]],
) -> str:
    lines: List[str] = [
        "# Retrospective Experiment: Standard Retrieval vs Ontology-Guided Retrieval",
        "",
        "## Setup",
        "",
        f"- Source bundle: `{source_results}`",
        f"- Dataset: `{dataset_path}`",
        f"- Question ids: `{', '.join(question_ids)}`",
        "- Ablation scope: retrieval-side ontology hooks only (`preferred_sections`, `supplement_sections`, `query_hints`)",
        "- Planner prior and evaluator are kept fixed.",
        "",
        "## Aggregate",
        "",
        "| Mode | Hit@k | Section Match | Row Candidate Recovery | Component Candidate Recovery | Avg Operand Count | Operand Grounding | Calc Success |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
        "| Standard Retrieval | {hit:.3f} | {section:.3f} | {row:.3f} | {component:.3f} | {operands:.3f} | {grounding} | {calc:.3f} |".format(
            hit=baseline["retrieval_hit_at_k"] or 0.0,
            section=baseline["section_match_rate"] or 0.0,
            row=baseline["row_candidate_recovery_rate"] or 0.0,
            component=baseline["component_candidate_recovery_rate"] or 0.0,
            operands=baseline["avg_operand_count"] or 0.0,
            grounding="-" if baseline["operand_grounding_score"] is None else f"{baseline['operand_grounding_score']:.3f}",
            calc=baseline["calc_success_rate"] or 0.0,
        ),
        "| Ontology-Guided Retrieval | {hit:.3f} | {section:.3f} | {row:.3f} | {component:.3f} | {operands:.3f} | {grounding} | {calc:.3f} |".format(
            hit=proposed["retrieval_hit_at_k"] or 0.0,
            section=proposed["section_match_rate"] or 0.0,
            row=proposed["row_candidate_recovery_rate"] or 0.0,
            component=proposed["component_candidate_recovery_rate"] or 0.0,
            operands=proposed["avg_operand_count"] or 0.0,
            grounding="-" if proposed["operand_grounding_score"] is None else f"{proposed['operand_grounding_score']:.3f}",
            calc=proposed["calc_success_rate"] or 0.0,
        ),
        "",
        "## Per Question",
        "",
        "| Question | Standard Retrieval | Ontology-Guided Retrieval | Key Delta |",
        "|---|---|---|---|",
    ]

    for row in per_question:
        off = row["baseline"]
        on = row["proposed"]
        baseline_text = (
            f"hit={off['retrieval_hit_at_k']:.1f}, "
            f"rows={off['ratio_row_candidates']}, comps={off['component_candidates']}, "
            f"operands={off['operand_count']}, calc={off['calc_status']}"
        )
        proposed_text = (
            f"hit={on['retrieval_hit_at_k']:.1f}, "
            f"rows={on['ratio_row_candidates']}, comps={on['component_candidates']}, "
            f"operands={on['operand_count']}, calc={on['calc_status']}"
        )
        delta_bits: List[str] = []
        if off["ratio_row_candidates"] != on["ratio_row_candidates"]:
            delta_bits.append(f"row {off['ratio_row_candidates']} -> {on['ratio_row_candidates']}")
        if off["component_candidates"] != on["component_candidates"]:
            delta_bits.append(f"component {off['component_candidates']} -> {on['component_candidates']}")
        if off["operand_count"] != on["operand_count"]:
            delta_bits.append(f"operand {off['operand_count']} -> {on['operand_count']}")
        if off["calc_status"] != on["calc_status"]:
            delta_bits.append(f"calc {off['calc_status']} -> {on['calc_status']}")
        if not delta_bits:
            delta_bits.append("no material change")
        lines.append(
            "| {id} | {baseline} | {proposed} | {delta} |".format(
                id=row["id"],
                baseline=baseline_text.replace("|", "\\|"),
                proposed=proposed_text.replace("|", "\\|"),
                delta=", ".join(delta_bits).replace("|", "\\|"),
            )
        )

    lines.extend(
        [
            "",
            "## Notes",
            "",
            "- This is a retrieval-side ablation, not a planner ablation.",
            "- `operating_margin` is expected to show a smaller delta because the base heuristics already bias toward `요약재무정보` / `손익계산서`.",
            "- `rnd_ratio` questions are expected to show the largest change because ontology-guided retrieval explicitly supplements `연구개발 활동` / `연구개발실적` sections.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Retrospective experiment 2: Standard Retrieval vs Ontology-Guided Retrieval"
    )
    parser.add_argument(
        "--source-results",
        required=True,
        help="Path to a benchmark results.json bundle that contains persisted store metadata.",
    )
    parser.add_argument(
        "--dataset-path",
        default="benchmarks/eval_dataset.math_focus.json",
        help="Eval dataset path used to recover questions / expected sections.",
    )
    parser.add_argument(
        "--question-id",
        action="append",
        default=[],
        help="Optional question id(s). Defaults to comparison_004/005/006.",
    )
    parser.add_argument(
        "--output-dir",
        required=True,
        help="Directory where retrospective ontology experiment outputs will be written.",
    )
    args = parser.parse_args()

    source_results = Path(args.source_results)
    dataset_path = Path(args.dataset_path)
    output_dir = Path(args.output_dir)

    payload = _load_results_payload(source_results)
    result = _first_result(payload)
    store_info = dict(result.get("store") or {})
    store_dir = Path(str(store_info.get("persist_directory") or ""))
    collection_name = str(store_info.get("collection_name") or "")
    if not store_dir or not collection_name:
        raise ValueError("Source results payload does not include store.persist_directory / collection_name.")

    config = dict(result.get("config") or {})
    k = int(config.get("k") or 8)
    question_ids = list(args.question_id or DEFAULT_QUESTION_IDS)
    examples = _load_examples(dataset_path, question_ids)

    vsm = VectorStoreManager(
        persist_directory=str(store_dir),
        collection_name=collection_name,
    )

    with _ontology_mode(enabled=False):
        baseline_agent = FinancialAgent(vsm, k=k)
        baseline_outcomes = [_run_question(baseline_agent, example) for example in examples]

    with _ontology_mode(enabled=True):
        proposed_agent = FinancialAgent(vsm, k=k)
        proposed_outcomes = [_run_question(proposed_agent, example) for example in examples]

    baseline_agg = _aggregate(baseline_outcomes)
    proposed_agg = _aggregate(proposed_outcomes)

    baseline_by_id = {row.id: row for row in baseline_outcomes}
    proposed_by_id = {row.id: row for row in proposed_outcomes}
    per_question: List[Dict[str, Any]] = []
    for example in examples:
        off = baseline_by_id[example.id]
        on = proposed_by_id[example.id]
        per_question.append(
            {
                "id": example.id,
                "question": example.question,
                "baseline": {
                    "target_metric_family": off.target_metric_family,
                    "retrieval_hit_at_k": off.retrieval_hit_at_k,
                    "section_match_rate": off.section_match_rate,
                    "ratio_row_candidates": off.ratio_row_candidates,
                    "component_candidates": off.component_candidates,
                    "operand_count": off.operand_count,
                    "operand_grounding_score": off.operand_grounding_score,
                    "calc_status": off.calc_status,
                    "rendered_value": off.rendered_value,
                    "top_sections": off.top_sections,
                },
                "proposed": {
                    "target_metric_family": on.target_metric_family,
                    "retrieval_hit_at_k": on.retrieval_hit_at_k,
                    "section_match_rate": on.section_match_rate,
                    "ratio_row_candidates": on.ratio_row_candidates,
                    "component_candidates": on.component_candidates,
                    "operand_count": on.operand_count,
                    "operand_grounding_score": on.operand_grounding_score,
                    "calc_status": on.calc_status,
                    "rendered_value": on.rendered_value,
                    "top_sections": on.top_sections,
                },
            }
        )

    summary = {
        "source_results": str(source_results),
        "dataset_path": str(dataset_path),
        "store_dir": str(store_dir),
        "collection_name": collection_name,
        "question_ids": question_ids,
        "baseline": baseline_agg,
        "proposed": proposed_agg,
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "summary.json").write_text(
        json.dumps({"summary": summary, "per_question": per_question}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (output_dir / "summary.md").write_text(
        _render_markdown(
            source_results=source_results,
            dataset_path=dataset_path,
            question_ids=question_ids,
            baseline=baseline_agg,
            proposed=proposed_agg,
            per_question=per_question,
        )
        + "\n",
        encoding="utf-8",
    )

    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
