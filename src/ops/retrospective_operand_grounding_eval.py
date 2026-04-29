from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from statistics import mean
from typing import Any, Dict, List, Optional

from ops.evaluator import _compute_operand_grounding_score, _resolve_numeric_judgement


@dataclass(frozen=True)
class AdjudicationItem:
    question_id: str
    human_correct: bool
    note: str = ""


DEFAULT_ADJUDICATION_SET: List[AdjudicationItem] = [
    AdjudicationItem("comparison_001", True, "정답 수치와 계산은 맞지만 historical evaluator에서 section support 부족으로 FAIL이 난 대표 케이스"),
    AdjudicationItem("comparison_002", True),
    AdjudicationItem("comparison_004", True),
    AdjudicationItem("trend_002", True),
    AdjudicationItem("trend_003", True),
    AdjudicationItem("comparison_005", True),
    AdjudicationItem("comparison_006", True),
    AdjudicationItem("comparison_007", True),
]

EXCLUDED_QUESTION_IDS: Dict[str, str] = {
    "comparison_003": "display-aware equivalence 변경의 영향이 섞여 있어 operand grounding 실험에서 제외",
    "trend_001": "numeric_final_judgement가 없는 trend 서술형 문항이라 제외",
}


def _load_per_question_rows(path: Path) -> List[Dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return list(payload["results"][0]["full_eval"]["per_question"])


def _grounding_confidence(row: Dict[str, Any]) -> float:
    if row.get("numeric_confidence") is not None:
        try:
            return float(row["numeric_confidence"])
        except (TypeError, ValueError):
            pass
    grounding_debug = (row.get("numeric_debug") or {}).get("grounding") or {}
    try:
        return float(grounding_debug.get("confidence") or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _compute_new_judgement(row: Dict[str, Any]) -> Dict[str, Any]:
    operand_grounding_score, operand_grounding_debug = _compute_operand_grounding_score(
        runtime_evidence=list(row.get("runtime_evidence") or []),
        contexts=[],
        calculation_operands=list(row.get("calculation_operands") or []),
    )
    new_judgement, new_confidence = _resolve_numeric_judgement(
        equivalence=row.get("numeric_equivalence"),
        grounding=row.get("numeric_grounding"),
        retrieval_support=operand_grounding_score,
        grounding_confidence=_grounding_confidence(row),
    )
    return {
        "operand_grounding_score": operand_grounding_score,
        "operand_grounding_debug": operand_grounding_debug,
        "numeric_final_judgement": new_judgement,
        "numeric_confidence": new_confidence,
    }


def _false_negative_rate(rows: List[Dict[str, Any]], judgement_key: str) -> float:
    positives = [row for row in rows if row["human_correct"]]
    if not positives:
        return 0.0
    false_negatives = [
        row for row in positives if str((row.get(judgement_key) or "")).upper() != "PASS"
    ]
    return len(false_negatives) / len(positives)


def _write_summary(output_dir: Path, summary: Dict[str, Any], per_question: List[Dict[str, Any]]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "summary.json").write_text(
        json.dumps({"summary": summary, "per_question": per_question}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    lines: List[str] = [
        "# Retrospective Experiment: Operand Grounding Evaluator",
        "",
        "## Setup",
        "",
        f"- Source bundle: `{summary['source_bundle']}`",
        f"- Adjudication positives: `{summary['positive_count']}`",
        f"- Excluded questions: `{', '.join(summary['excluded_questions']) if summary['excluded_questions'] else '-'}`",
        "",
        "## Aggregate",
        "",
        f"- Old false negative rate: `{summary['old_false_negative_rate']:.3f}`",
        f"- New false negative rate: `{summary['new_false_negative_rate']:.3f}`",
        f"- Recovered question ids: `{', '.join(summary['recovered_ids']) if summary['recovered_ids'] else '-'}`",
        "",
        "## Per Question",
        "",
        "| Question | Human Correct | Old Judgement | Old Support | New Judgement | New Support | Note |",
        "|---|---:|---|---:|---|---:|---|",
    ]

    for row in per_question:
        lines.append(
            "| {id} | {human} | {old_j} | {old_s} | {new_j} | {new_s} | {note} |".format(
                id=row["id"],
                human="yes" if row["human_correct"] else "no",
                old_j=row.get("old_numeric_final_judgement") or "-",
                old_s=row.get("old_numeric_retrieval_support")
                if row.get("old_numeric_retrieval_support") is not None
                else "-",
                new_j=row.get("new_numeric_final_judgement") or "-",
                new_s=row.get("new_operand_grounding_score")
                if row.get("new_operand_grounding_score") is not None
                else "-",
                note=row.get("note") or "",
            )
        )

    (output_dir / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Retrospective meta-evaluation: section-support vs operand-grounding support"
    )
    parser.add_argument(
        "--source-results",
        required=True,
        help="Path to a historical benchmark results.json bundle to re-score.",
    )
    parser.add_argument(
        "--output-dir",
        required=True,
        help="Directory where retrospective outputs will be written.",
    )
    args = parser.parse_args()

    source_path = Path(args.source_results)
    output_dir = Path(args.output_dir)
    rows = _load_per_question_rows(source_path)
    rows_by_id = {row["id"]: row for row in rows}

    per_question: List[Dict[str, Any]] = []
    recovered_ids: List[str] = []
    for item in DEFAULT_ADJUDICATION_SET:
        row = rows_by_id[item.question_id]
        new_eval = _compute_new_judgement(row)
        old_judgement = row.get("numeric_final_judgement")
        new_judgement = new_eval["numeric_final_judgement"]
        if item.human_correct and str(old_judgement or "").upper() != "PASS" and str(new_judgement or "").upper() == "PASS":
            recovered_ids.append(item.question_id)
        per_question.append(
            {
                "id": item.question_id,
                "human_correct": item.human_correct,
                "note": item.note,
                "old_numeric_final_judgement": old_judgement,
                "old_numeric_retrieval_support": row.get("numeric_retrieval_support"),
                "new_numeric_final_judgement": new_judgement,
                "new_operand_grounding_score": new_eval["operand_grounding_score"],
            }
        )

    old_false_negative_rate = _false_negative_rate(
        [
            {
                "human_correct": row["human_correct"],
                "old_numeric_final_judgement": row["old_numeric_final_judgement"],
                "numeric_final_judgement": row["old_numeric_final_judgement"],
            }
            for row in per_question
        ],
        "numeric_final_judgement",
    )
    new_false_negative_rate = _false_negative_rate(
        [
            {
                "human_correct": row["human_correct"],
                "numeric_final_judgement": row["new_numeric_final_judgement"],
            }
            for row in per_question
        ],
        "numeric_final_judgement",
    )

    summary = {
        "source_bundle": str(source_path),
        "positive_count": sum(1 for item in DEFAULT_ADJUDICATION_SET if item.human_correct),
        "excluded_questions": [f"{qid}: {reason}" for qid, reason in EXCLUDED_QUESTION_IDS.items()],
        "old_false_negative_rate": old_false_negative_rate,
        "new_false_negative_rate": new_false_negative_rate,
        "recovered_ids": recovered_ids,
    }
    _write_summary(output_dir, summary, per_question)

    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
