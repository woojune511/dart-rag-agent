"""Replay evaluator metrics from historical benchmark answers.

This script does not run the agent. It reads a benchmark ``results.json`` that
already contains ``full_eval.per_question`` rows and recomputes the cheap,
deterministic numeric metrics from the saved answer, runtime evidence, and
calculation trace.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from statistics import mean
from typing import Any, Dict, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from agent.financial_graph_helpers import _resolve_runtime_calculation_trace  # noqa: E402
from ops.evaluator import (  # noqa: E402
    _compute_calculation_correctness,
    _compute_numeric_equivalence,
    _compute_numeric_result_correctness,
    _compute_operand_grounding_score,
    _compute_operand_selection_correctness,
    _compute_unit_consistency_pass,
    _resolve_numeric_judgement,
    load_eval_examples_from_path,
)


def _load_source_rows(path: Path) -> List[Dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if "results" in payload:
        rows: List[Dict[str, Any]] = []
        for result in payload.get("results") or []:
            rows.extend(list(((result.get("full_eval") or {}).get("per_question")) or []))
        if rows:
            return rows
    if "company_runs" in payload:
        rows = []
        for bundle in payload.get("company_runs") or []:
            for result in bundle.get("results") or []:
                rows.extend(list(((result.get("full_eval") or {}).get("per_question")) or []))
        if rows:
            return rows
    raise ValueError(f"No full_eval.per_question rows found in {path}")


def _aggregate_replayed(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    numeric_rows = [row for row in rows if row.get("numeric_final_judgement") is not None]

    def avg(key: str) -> Optional[float]:
        values = [float(row[key]) for row in rows if row.get(key) is not None]
        return float(mean(values)) if values else None

    return {
        "question_count": len(rows),
        "numeric_question_count": len(numeric_rows),
        "numeric_pass_rate": (
            sum(1 for row in numeric_rows if row.get("numeric_final_judgement") == "PASS") / len(numeric_rows)
            if numeric_rows
            else None
        ),
        "numeric_equivalence": avg("numeric_equivalence"),
        "numeric_grounding": avg("numeric_grounding"),
        "numeric_retrieval_support": avg("numeric_retrieval_support"),
        "operand_selection_correctness": avg("operand_selection_correctness"),
        "unit_consistency_pass": avg("unit_consistency_pass"),
        "numeric_result_correctness": avg("numeric_result_correctness"),
        "calculation_correctness": avg("calculation_correctness"),
    }


def _source_row_warnings(row: Dict[str, Any]) -> List[str]:
    warnings: List[str] = []
    source_verdict = str(row.get("numeric_final_judgement") or "").strip()
    if source_verdict and source_verdict != "PASS":
        warnings.append(f"source_numeric_final_judgement={source_verdict}")
    if row.get("numeric_grounding") is None:
        warnings.append("source_numeric_grounding_missing")
    grounding_debug = dict((row.get("numeric_debug") or {}).get("grounding") or {})
    reason = str(grounding_debug.get("reason") or "")
    if "RESOURCE_EXHAUSTED" in reason or "429" in reason:
        warnings.append("source_grounding_cap_or_rate_limited")
    if row.get("calculation_operands") in (None, []):
        warnings.append("source_calculation_operands_missing")
    return warnings


def _score_row(row: Dict[str, Any], example_by_id: Dict[str, Any]) -> Dict[str, Any]:
    question_id = str(row.get("id") or "")
    example = example_by_id.get(question_id)
    if example is None:
        raise ValueError(f"Dataset has no example for source row id={question_id}")

    resolved_trace = _resolve_runtime_calculation_trace(row)
    calculation_operands = list(
        row.get("calculation_operands")
        or resolved_trace.get("calculation_operands")
        or []
    )
    calculation_plan = dict(row.get("calculation_plan") or resolved_trace.get("calculation_plan") or {})
    calculation_result = dict(row.get("calculation_result") or resolved_trace.get("calculation_result") or {})
    runtime_evidence = list(row.get("runtime_evidence") or [])
    contexts = []
    for evidence in runtime_evidence:
        if isinstance(evidence, dict):
            contexts.append(
                " ".join(
                    str(evidence.get(key) or "")
                    for key in ("claim", "quote_span", "raw_row_text", "source_context")
                )
            )

    numeric_equivalence, equivalence_debug = _compute_numeric_equivalence(
        answer=str(row.get("answer") or ""),
        answer_key=example.canonical_answer_key,
        canonical_evidence=list(example.evidence or []),
    )
    operand_grounding, operand_grounding_debug = _compute_operand_grounding_score(
        runtime_evidence=runtime_evidence,
        contexts=contexts,
        calculation_operands=calculation_operands,
    )
    retrieval_support = operand_grounding if operand_grounding is not None else row.get("retrieval_hit_at_k")
    source_grounding = row.get("numeric_grounding")
    final_judgement, confidence = _resolve_numeric_judgement(
        equivalence=numeric_equivalence,
        grounding=source_grounding,
        retrieval_support=retrieval_support,
        grounding_confidence=float(row.get("numeric_confidence") or 0.0),
    )
    numeric_result_correctness = _compute_numeric_result_correctness(
        example=example,
        calculation_result=calculation_result,
    )
    operand_selection_correctness = _compute_operand_selection_correctness(
        example=example,
        calculation_operands=calculation_operands,
    )
    unit_consistency_pass = _compute_unit_consistency_pass(
        calculation_operands=calculation_operands,
        calculation_plan=calculation_plan,
    )
    calculation_correctness = _compute_calculation_correctness(
        numeric_result_correctness=numeric_result_correctness,
        trend_interpretation_correctness=row.get("trend_interpretation_correctness"),
        grounded_rendering_correctness=row.get("grounded_rendering_correctness"),
    )
    return {
        "id": question_id,
        "question": row.get("question"),
        "answer": row.get("answer"),
        "source_numeric_final_judgement": row.get("numeric_final_judgement"),
        "numeric_final_judgement": final_judgement,
        "numeric_confidence": confidence,
        "numeric_equivalence": numeric_equivalence,
        "numeric_grounding": source_grounding,
        "numeric_retrieval_support": retrieval_support,
        "operand_selection_correctness": operand_selection_correctness,
        "unit_consistency_pass": unit_consistency_pass,
        "numeric_result_correctness": numeric_result_correctness,
        "calculation_correctness": calculation_correctness,
        "source_warnings": _source_row_warnings(row),
        "debug": {
            "numeric_equivalence": equivalence_debug,
            "operand_grounding": operand_grounding_debug,
            "source_numeric_debug": row.get("numeric_debug") or {},
        },
    }


def _write_outputs(output_dir: Path, rows: List[Dict[str, Any]], source_results: Path, dataset_path: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    aggregate = _aggregate_replayed(rows)
    payload = {
        "source_results": str(source_results),
        "dataset_path": str(dataset_path),
        "mode": "historical_answer_replay",
        "aggregate": aggregate,
        "per_question": rows,
    }
    (output_dir / "summary.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    with open(output_dir / "summary.csv", "w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=[
                "id",
                "source_numeric_final_judgement",
                "numeric_final_judgement",
                "numeric_equivalence",
                "numeric_grounding",
                "numeric_retrieval_support",
                "operand_selection_correctness",
                "unit_consistency_pass",
                "numeric_result_correctness",
                "calculation_correctness",
                "source_warnings",
            ],
        )
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key) for key in writer.fieldnames})
    lines = [
        "# Historical Answer Replay",
        "",
        f"- Source: `{source_results}`",
        f"- Dataset: `{dataset_path}`",
        f"- Questions: {aggregate['question_count']}",
        f"- Numeric pass rate: {aggregate['numeric_pass_rate']}",
        "",
        "| id | source verdict | replay verdict | equivalence | grounding | retrieval support |",
        "|---|---|---|---:|---:|---:|",
    ]
    for row in rows:
        warnings = [str(item) for item in (row.get("source_warnings") or []) if str(item).strip()]
        lines.append(
            "| {id} | {source} | {verdict} | {equivalence} | {grounding} | {support} |".format(
                id=row.get("id"),
                source=row.get("source_numeric_final_judgement"),
                verdict=row.get("numeric_final_judgement"),
                equivalence=row.get("numeric_equivalence"),
                grounding=row.get("numeric_grounding"),
                support=row.get("numeric_retrieval_support"),
            )
        )
        if warnings:
            lines.append(f"- Warning for `{row.get('id')}`: {', '.join(warnings)}")
    (output_dir / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Replay deterministic evaluator metrics from saved benchmark answers.")
    parser.add_argument("--source-results", required=True, help="Path to a benchmark results.json file.")
    parser.add_argument("--dataset-path", required=True, help="Dataset used by the original full evaluation.")
    parser.add_argument("--output-dir", required=True, help="Directory for replay summary outputs.")
    parser.add_argument("--question-id", action="append", default=[], help="Optional question id filter. Repeatable.")
    args = parser.parse_args()

    source_results = Path(args.source_results)
    dataset_path = Path(args.dataset_path)
    output_dir = Path(args.output_dir)
    if not source_results.is_absolute():
        source_results = (PROJECT_ROOT / source_results).resolve()
    if not dataset_path.is_absolute():
        dataset_path = (PROJECT_ROOT / dataset_path).resolve()
    if not output_dir.is_absolute():
        output_dir = (PROJECT_ROOT / output_dir).resolve()

    rows = _load_source_rows(source_results)
    question_ids = {str(item).strip() for item in args.question_id or [] if str(item).strip()}
    if question_ids:
        rows = [row for row in rows if str(row.get("id") or "") in question_ids]
    examples = load_eval_examples_from_path(dataset_path)
    example_by_id = {example.id: example for example in examples}
    scored = [_score_row(row, example_by_id) for row in rows]
    _write_outputs(output_dir, scored, source_results, dataset_path)


if __name__ == "__main__":
    main()
