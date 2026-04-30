from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from ops.evaluator import (  # noqa: E402
    _compute_numeric_equivalence,
    _compute_numeric_result_correctness,
    _compute_operand_selection_correctness,
    _extract_numeric_candidates,
    _labels_match,
    _normalise_label_text,
    _resolve_numeric_judgement,
    _safe_float,
    load_eval_examples_from_path,
)


@dataclass(frozen=True)
class AblationCase:
    decision_id: str
    question_id: str
    title: str
    note: str


CASES: List[AblationCase] = [
    AblationCase(
        decision_id="73",
        question_id="comparison_001",
        title="Strict numeric equivalence vs current display-aware equivalence",
        note="Originally documented as a tolerance-only fix, but the durable current behavior is display-aware equivalence.",
    ),
    AblationCase(
        decision_id="75",
        question_id="comparison_004",
        title="Legacy label matcher vs current label matcher",
        note="Compare operand-selection scoring on the exact same historical operands.",
    ),
    AblationCase(
        decision_id="76",
        question_id="trend_002",
        title="Operand selection before override vs after override",
        note="Tests the mathematically equivalent derivation-path override on a fixed historical row.",
    ),
    AblationCase(
        decision_id="76",
        question_id="comparison_005",
        title="Operand selection before override vs after override (precomputed ratio path)",
        note="Same override principle applied to a direct precomputed-ratio path.",
    ),
]


def _load_per_question_rows(path: Path) -> List[Dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return list(payload["results"][0]["full_eval"]["per_question"])


def _strict_numeric_values_equivalent(left: Dict[str, Any], right: Dict[str, Any]) -> bool:
    if left.get("kind") != right.get("kind"):
        return False
    left_value = _safe_float(left.get("normalized_value"))
    right_value = _safe_float(right.get("normalized_value"))
    if left_value is None or right_value is None:
        return False

    if left.get("kind") == "currency":
        tolerance = max(abs(right_value) * 1e-6, 0.5)
    else:
        tolerance = 1e-6
    return abs(left_value - right_value) <= tolerance


def _compute_strict_numeric_equivalence(answer: str, answer_key: str, evidence_quotes: List[str]) -> Tuple[Optional[float], Dict[str, Any]]:
    answer_candidates = _extract_numeric_candidates(answer)
    reference_candidates = _extract_numeric_candidates(answer_key)
    for quote in evidence_quotes:
        reference_candidates.extend(_extract_numeric_candidates(quote))

    if not answer_candidates or not reference_candidates:
        return None, {
            "answer_candidates": answer_candidates,
            "reference_candidates": reference_candidates,
            "matched_pair": None,
            "reason": "missing_candidates",
        }

    for answer_candidate in answer_candidates:
        for reference_candidate in reference_candidates:
            if _strict_numeric_values_equivalent(answer_candidate, reference_candidate):
                return 1.0, {
                    "answer_candidates": answer_candidates,
                    "reference_candidates": reference_candidates,
                    "matched_pair": {
                        "answer": answer_candidate,
                        "reference": reference_candidate,
                    },
                    "reason": "equivalent_value",
                }

    return 0.0, {
        "answer_candidates": answer_candidates,
        "reference_candidates": reference_candidates,
        "matched_pair": None,
        "reason": "no_equivalent_value",
    }


def _legacy_labels_match(expected_label: str, actual_label: str) -> bool:
    expected = _normalise_label_text(expected_label)
    actual = _normalise_label_text(actual_label)
    if not expected or not actual:
        return True
    return expected == actual or expected in actual or actual in expected


def _legacy_operand_matches(expected: Dict[str, Any], actual: Dict[str, Any]) -> bool:
    expected_period = re.sub(r"\s+", "", str(expected.get("period") or "")).strip().lower()
    actual_period = re.sub(r"\s+", "", str(actual.get("period") or "")).strip().lower()
    if expected_period and actual_period and expected_period != actual_period:
        return False

    expected_label = str(expected.get("label") or "")
    actual_label = str(actual.get("label") or "")
    if expected_label and actual_label and not _legacy_labels_match(expected_label, actual_label):
        return False

    # Keep value/unit comparison aligned with the current evaluator so the
    # ablation isolates label matching rather than numeric normalization.
    from ops.evaluator import _normalise_math_operand_value  # noqa: WPS433

    expected_value, expected_unit = _normalise_math_operand_value(
        str(expected.get("raw_value") or ""),
        str(expected.get("raw_unit") or ""),
    )
    actual_value = _safe_float(actual.get("normalized_value"))
    actual_unit = str(actual.get("normalized_unit") or "").strip()
    if expected_value is not None and actual_value is not None:
        if expected_unit and actual_unit and expected_unit != actual_unit:
            return False
        denominator = max(abs(expected_value), 1.0)
        if abs(actual_value - expected_value) / denominator > 1e-4:
            return False
    return True


def _compute_legacy_operand_selection(example: Any, calculation_operands: List[Dict[str, Any]]) -> Optional[float]:
    expected_operands = list(example.expected_operands or [])
    if not expected_operands:
        return None
    if not calculation_operands:
        return 0.0

    unmatched_actual_indices = list(range(len(calculation_operands)))
    matched = 0
    for expected in expected_operands:
        match_index: Optional[int] = None
        for actual_index in unmatched_actual_indices:
            if _legacy_operand_matches(expected, calculation_operands[actual_index]):
                match_index = actual_index
                break
        if match_index is not None:
            matched += 1
            unmatched_actual_indices.remove(match_index)
    return matched / len(expected_operands)


def _override_operand_selection(
    base_score: Optional[float],
    numeric_result_correctness: Optional[float],
    numeric_grounding: Optional[float],
) -> Optional[float]:
    if (
        numeric_result_correctness == 1.0
        and numeric_grounding == 1.0
        and base_score is not None
        and base_score < 1.0
    ):
        return 1.0
    return base_score


def _score_case(case: AblationCase, row: Dict[str, Any], example: Any) -> Dict[str, Any]:
    evidence_quotes = [str(item.quote) for item in list(example.evidence or [])]

    if case.decision_id == "73":
        old_equivalence, old_debug = _compute_strict_numeric_equivalence(
            answer=str(row.get("answer") or ""),
            answer_key=example.canonical_answer_key,
            evidence_quotes=evidence_quotes,
        )
        new_equivalence, new_debug = _compute_numeric_equivalence(
            answer=str(row.get("answer") or ""),
            answer_key=example.canonical_answer_key,
            canonical_evidence=list(example.evidence or []),
        )
        old_judgement, _ = _resolve_numeric_judgement(
            equivalence=old_equivalence,
            grounding=row.get("numeric_grounding"),
            retrieval_support=row.get("numeric_retrieval_support"),
            grounding_confidence=float(row.get("numeric_confidence") or 0.0),
        )
        new_judgement, _ = _resolve_numeric_judgement(
            equivalence=new_equivalence,
            grounding=row.get("numeric_grounding"),
            retrieval_support=row.get("numeric_retrieval_support"),
            grounding_confidence=float(row.get("numeric_confidence") or 0.0),
        )
        return {
            "decision_id": case.decision_id,
            "question_id": case.question_id,
            "title": case.title,
            "note": case.note,
            "baseline_label": "strict_equivalence",
            "baseline_value": old_equivalence,
            "baseline_debug": old_debug,
            "baseline_judgement": old_judgement,
            "proposed_label": "current_display_aware_equivalence",
            "proposed_value": new_equivalence,
            "proposed_debug": new_debug,
            "proposed_judgement": new_judgement,
        }

    if case.decision_id == "75":
        legacy_score = _compute_legacy_operand_selection(example, list(row.get("calculation_operands") or []))
        current_score = _compute_operand_selection_correctness(
            example=example,
            calculation_operands=list(row.get("calculation_operands") or []),
        )
        return {
            "decision_id": case.decision_id,
            "question_id": case.question_id,
            "title": case.title,
            "note": case.note,
            "baseline_label": "legacy_label_match",
            "baseline_value": legacy_score,
            "baseline_debug": {
                "expected_labels": [item.get("label") for item in list(example.expected_operands or [])],
                "actual_labels": [item.get("label") for item in list(row.get("calculation_operands") or [])],
                "legacy_matches": [
                    {
                        "expected": str(expected.get("label") or ""),
                        "actual": str(actual.get("label") or ""),
                        "match": _legacy_labels_match(
                            str(expected.get("label") or ""),
                            str(actual.get("label") or ""),
                        ),
                    }
                    for expected in list(example.expected_operands or [])
                    for actual in list(row.get("calculation_operands") or [])
                ],
            },
            "baseline_judgement": None,
            "proposed_label": "current_label_match",
            "proposed_value": current_score,
            "proposed_debug": {
                "current_matches": [
                    {
                        "expected": str(expected.get("label") or ""),
                        "actual": str(actual.get("label") or ""),
                        "match": _labels_match(
                            str(expected.get("label") or ""),
                            str(actual.get("label") or ""),
                        ),
                    }
                    for expected in list(example.expected_operands or [])
                    for actual in list(row.get("calculation_operands") or [])
                ],
            },
            "proposed_judgement": None,
        }

    numeric_result_correctness = _compute_numeric_result_correctness(
        example=example,
        calculation_result=dict(row.get("calculation_result") or {}),
    )
    base_score = _compute_operand_selection_correctness(
        example=example,
        calculation_operands=list(row.get("calculation_operands") or []),
    )
    overridden_score = _override_operand_selection(
        base_score=base_score,
        numeric_result_correctness=numeric_result_correctness,
        numeric_grounding=row.get("numeric_grounding"),
    )
    return {
        "decision_id": case.decision_id,
        "question_id": case.question_id,
        "title": case.title,
        "note": case.note,
        "baseline_label": "before_operand_override",
        "baseline_value": base_score,
        "baseline_debug": {
            "numeric_result_correctness": numeric_result_correctness,
            "numeric_grounding": row.get("numeric_grounding"),
        },
        "baseline_judgement": None,
        "proposed_label": "after_operand_override",
        "proposed_value": overridden_score,
        "proposed_debug": {
            "numeric_result_correctness": numeric_result_correctness,
            "numeric_grounding": row.get("numeric_grounding"),
        },
        "proposed_judgement": None,
    }


def _write_summary(output_dir: Path, summary: Dict[str, Any], rows: List[Dict[str, Any]]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "summary.json").write_text(
        json.dumps({"summary": summary, "cases": rows}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    lines: List[str] = [
        "# Retrospective Experiment: Evaluator Sub-decisions Replay",
        "",
        "## Setup",
        "",
        f"- Source bundle: `{summary['source_bundle']}`",
        f"- Dataset: `{summary['dataset_path']}`",
        "- Method: historical answer / runtime trace replay only. No agent rerun.",
        "",
        "## Aggregate",
        "",
        "| Decision | Question | Baseline | Proposed |",
        "| --- | --- | ---: | ---: |",
    ]
    for row in rows:
        lines.append(
            f"| {row['decision_id']} | {row['question_id']} | {row['baseline_value']} | {row['proposed_value']} |"
        )

    lines.extend(
        [
            "",
            "## Per Case",
            "",
        ]
    )
    for row in rows:
        lines.extend(
            [
                f"### Decision {row['decision_id']} / {row['question_id']}",
                "",
                f"- Title: `{row['title']}`",
                f"- Note: {row['note']}",
                f"- Baseline `{row['baseline_label']}`: `{row['baseline_value']}`",
                f"- Proposed `{row['proposed_label']}`: `{row['proposed_value']}`",
            ]
        )
        if row.get("baseline_judgement") is not None or row.get("proposed_judgement") is not None:
            lines.append(
                f"- Judgement: `{row.get('baseline_judgement')}` -> `{row.get('proposed_judgement')}`"
            )
        lines.extend(
            [
                "",
                "```json",
                json.dumps(
                    {
                        "baseline_debug": row.get("baseline_debug"),
                        "proposed_debug": row.get("proposed_debug"),
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                "```",
                "",
            ]
        )

    (output_dir / "summary.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Replay evaluator sub-decisions on fixed historical outputs.")
    parser.add_argument("--source-results", required=True, help="Path to historical results.json bundle.")
    parser.add_argument("--dataset", required=True, help="Path to eval dataset JSON.")
    parser.add_argument("--output-dir", required=True, help="Directory for summary outputs.")
    args = parser.parse_args()

    source_path = Path(args.source_results)
    dataset_path = Path(args.dataset)
    output_dir = Path(args.output_dir)

    rows = _load_per_question_rows(source_path)
    rows_by_id = {row["id"]: row for row in rows}
    examples_by_id = {example.id: example for example in load_eval_examples_from_path(dataset_path)}

    scored_rows: List[Dict[str, Any]] = []
    for case in CASES:
        row = rows_by_id[case.question_id]
        example = examples_by_id[case.question_id]
        scored_rows.append(_score_case(case, row, example))

    summary = {
        "source_bundle": str(source_path),
        "dataset_path": str(dataset_path),
        "case_count": len(scored_rows),
        "decision_ids": sorted({row["decision_id"] for row in scored_rows}),
    }
    _write_summary(output_dir, summary, scored_rows)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
