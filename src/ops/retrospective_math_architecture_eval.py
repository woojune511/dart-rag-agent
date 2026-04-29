from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from ops.evaluator import (
    EvalExample,
    _compute_numeric_equivalence,
    _compute_numeric_grounding,
    load_eval_examples_from_path,
)

load_dotenv()


@dataclass(frozen=True)
class ScoredAnswer:
    answer: str
    equivalence: Optional[float]
    grounding: Optional[float]
    strict_correct: bool
    equivalence_debug: Dict[str, Any]
    grounding_debug: Dict[str, Any]


def _load_per_question_rows(path: Path) -> List[Dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))

    if isinstance(payload, list):
        return list(payload)

    if isinstance(payload, dict):
        if "per_question" in payload:
            return list(payload.get("per_question") or [])
        results = payload.get("results") or []
        if results:
            first = results[0]
            full_eval = first.get("full_eval") or {}
            per_question = full_eval.get("per_question")
            if per_question:
                return list(per_question)

    raise ValueError(f"Unsupported results payload shape: {path}")


def _index_examples(dataset_path: Path) -> Dict[str, EvalExample]:
    examples = load_eval_examples_from_path(dataset_path)
    return {example.id: example for example in examples}


def _numeric_slice(rows: List[Dict[str, Any]], examples_by_id: Dict[str, EvalExample]) -> List[Dict[str, Any]]:
    selected: List[Dict[str, Any]] = []
    for row in rows:
        question_id = str(row.get("id") or "")
        example = examples_by_id.get(question_id)
        if not example:
            continue
        if str(example.answer_type or "").lower() != "numeric":
            continue
        selected.append(row)
    return selected


def _flatten_text(text: str) -> str:
    return " ".join((text or "").split()).strip()


def _build_direct_calc_context(row: Dict[str, Any]) -> List[str]:
    blocks: List[str] = []
    seen: set[str] = set()

    for item in list(row.get("runtime_evidence") or [])[:8]:
        pieces = [
            str(item.get("source_anchor") or "").strip(),
            str(item.get("source_context") or "").strip(),
            str(item.get("raw_row_text") or "").strip(),
            str(item.get("quote_span") or "").strip(),
        ]
        text = _flatten_text(" | ".join(piece for piece in pieces if piece))
        if text and text not in seen:
            seen.add(text)
            blocks.append(text)

    for item in list(row.get("retrieved_previews") or [])[:4]:
        preview = _flatten_text(str(item.get("preview") or ""))
        if preview and preview not in seen:
            seen.add(preview)
            blocks.append(preview)

    return blocks


def _build_runtime_evidence_for_scoring(row: Dict[str, Any], context_blocks: List[str]) -> List[Dict[str, Any]]:
    evidence = list(row.get("runtime_evidence") or [])
    if evidence:
        return evidence
    # Fallback for rows that only retained preview context in the serialized artifact.
    synthetic: List[Dict[str, Any]] = []
    for index, block in enumerate(context_blocks[:4], start=1):
        synthetic.append(
            {
                "evidence_id": f"synthetic_{index:03d}",
                "source_anchor": "[synthetic retrieved context]",
                "quote_span": block,
            }
        )
    return synthetic


def _direct_calc_prompt(example: EvalExample, context_blocks: List[str]) -> str:
    context_text = "\n".join(f"- {block}" for block in context_blocks[:10]) or "-"
    return (
        "당신은 재무 문서를 읽고 직접 계산해서 답하는 분석가입니다.\n"
        "아래 근거 텍스트만 사용해서 질문에 답하세요.\n"
        "규칙:\n"
        "1. 필요한 경우 직접 계산하세요.\n"
        "2. 원화 금액은 출처 텍스트에 표시된 단위(억원/조원)를 그대로 사용하세요. "
        "조·억 복합 표기가 보이면 '81조 9,082억원' 형식으로 표현하세요. "
        "백만원 단위로 제시된 숫자라도 조·억원으로 환산해서 표현하세요.\n"
        "3. 질문이 %p 차이를 묻는다면 %가 아니라 %p로 답하세요.\n"
        "4. 답변은 한국어 1~2문장으로 간결하게 쓰세요.\n"
        "5. 추론 과정은 쓰지 말고 최종 답만 쓰세요.\n\n"
        f"질문:\n{example.question}\n\n"
        f"근거:\n{context_text}\n"
    )


def _score_answer(
    *,
    llm: ChatGoogleGenerativeAI,
    example: EvalExample,
    answer: str,
    runtime_evidence: List[Dict[str, Any]],
) -> ScoredAnswer:
    equivalence, equivalence_debug = _compute_numeric_equivalence(
        answer=answer,
        answer_key=example.canonical_answer_key,
        canonical_evidence=example.evidence,
    )
    grounding, grounding_debug = _compute_numeric_grounding(
        llm=llm,
        example=example,
        answer=answer,
        runtime_evidence=runtime_evidence,
    )
    strict_correct = equivalence == 1.0 and grounding == 1.0
    return ScoredAnswer(
        answer=answer,
        equivalence=equivalence,
        grounding=grounding,
        strict_correct=strict_correct,
        equivalence_debug=equivalence_debug,
        grounding_debug=grounding_debug,
    )


def _score_formula_row(
    *,
    llm: ChatGoogleGenerativeAI,
    example: EvalExample,
    row: Dict[str, Any],
) -> ScoredAnswer:
    runtime_evidence = _build_runtime_evidence_for_scoring(row, _build_direct_calc_context(row))
    return _score_answer(
        llm=llm,
        example=example,
        answer=str(row.get("answer") or ""),
        runtime_evidence=runtime_evidence,
    )


def _run_direct_calc(
    *,
    llm: ChatGoogleGenerativeAI,
    example: EvalExample,
    row: Dict[str, Any],
) -> ScoredAnswer:
    context_blocks = _build_direct_calc_context(row)
    runtime_evidence = _build_runtime_evidence_for_scoring(row, context_blocks)
    answer = (llm.invoke(_direct_calc_prompt(example, context_blocks)).content or "").strip()
    return _score_answer(
        llm=llm,
        example=example,
        answer=answer,
        runtime_evidence=runtime_evidence,
    )


def _rate(rows: List[ScoredAnswer], attr: str) -> float:
    if not rows:
        return 0.0
    total = 0.0
    for row in rows:
        value = getattr(row, attr)
        if value == 1.0:
            total += 1.0
    return total / len(rows)


def _strict_rate(rows: List[ScoredAnswer]) -> float:
    if not rows:
        return 0.0
    return sum(1 for row in rows if row.strict_correct) / len(rows)


def _legacy_overlap(
    *,
    llm: ChatGoogleGenerativeAI,
    examples_by_id: Dict[str, EvalExample],
    legacy_rows: List[Dict[str, Any]],
    active_ids: List[str],
) -> Dict[str, Any]:
    legacy_by_id = {str(row.get("id") or ""): row for row in legacy_rows}
    overlap_ids = [question_id for question_id in active_ids if question_id in legacy_by_id]
    scored: List[ScoredAnswer] = []
    for question_id in overlap_ids:
        example = examples_by_id[question_id]
        scored.append(_score_formula_row(llm=llm, example=example, row=legacy_by_id[question_id]))
    return {
        "question_ids": overlap_ids,
        "count": len(scored),
        "strict_correct_rate": _strict_rate(scored),
        "equivalence_rate": _rate(scored, "equivalence"),
        "grounding_rate": _rate(scored, "grounding"),
    }


def _render_markdown(
    *,
    source_results: Path,
    dataset_path: Path,
    direct_rows: List[Dict[str, Any]],
    summary: Dict[str, Any],
) -> str:
    lines: List[str] = [
        "# Retrospective Experiment: Direct Calc vs Formula Planner + AST",
        "",
        "## Setup",
        "",
        f"- Source bundle: `{source_results}`",
        f"- Dataset: `{dataset_path}`",
        f"- Numeric slice: `{summary['n_questions']}` questions",
        f"- Excluded qualitative question ids: `{', '.join(summary['excluded_question_ids']) if summary['excluded_question_ids'] else '-'}`",
        "",
        "## Aggregate",
        "",
        "| Mode | Strict Correct | Numeric Equivalence | Numeric Grounding |",
        "|---|---:|---:|---:|",
        "| Direct Calc | {direct_strict:.3f} | {direct_eq:.3f} | {direct_ground:.3f} |".format(
            direct_strict=summary["direct_calc"]["strict_correct_rate"],
            direct_eq=summary["direct_calc"]["equivalence_rate"],
            direct_ground=summary["direct_calc"]["grounding_rate"],
        ),
        "| Formula Planner + AST | {formula_strict:.3f} | {formula_eq:.3f} | {formula_ground:.3f} |".format(
            formula_strict=summary["formula_ast"]["strict_correct_rate"],
            formula_eq=summary["formula_ast"]["equivalence_rate"],
            formula_ground=summary["formula_ast"]["grounding_rate"],
        ),
        "",
    ]

    legacy = summary.get("legacy_operation")
    if legacy:
        lines.extend(
            [
                "## Legacy Operation-Path Overlap",
                "",
                f"- Overlap question ids: `{', '.join(legacy['question_ids']) if legacy['question_ids'] else '-'}`",
                f"- Count: `{legacy['count']}`",
                f"- Strict Correct: `{legacy['strict_correct_rate']:.3f}`",
                f"- Numeric Equivalence: `{legacy['equivalence_rate']:.3f}`",
                f"- Numeric Grounding: `{legacy['grounding_rate']:.3f}`",
                "",
            ]
        )

    lines.extend(
        [
            "## Per Question",
            "",
            "| Question | Direct Correct | Formula Correct | Direct Answer | Formula Answer | Direct Failure Reason |",
            "|---|---:|---:|---|---|---|",
        ]
    )

    for row in direct_rows:
        failure_reason = "-"
        if not row["direct_calc"]["strict_correct"]:
            failure_reason = str(row["direct_calc"]["equivalence_debug"].get("reason") or row["direct_calc"]["grounding_debug"].get("reason") or "-")
        lines.append(
            "| {id} | {direct_ok} | {formula_ok} | {direct_answer} | {formula_answer} | {reason} |".format(
                id=row["id"],
                direct_ok="yes" if row["direct_calc"]["strict_correct"] else "no",
                formula_ok="yes" if row["formula_ast"]["strict_correct"] else "no",
                direct_answer=str(row["direct_calc"]["answer"]).replace("|", "\\|"),
                formula_answer=str(row["formula_ast"]["answer"]).replace("|", "\\|"),
                reason=str(failure_reason).replace("|", "\\|"),
            )
        )

    lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Retrospective experiment 1: Direct Calc vs Formula Planner + AST"
    )
    parser.add_argument(
        "--source-results",
        required=True,
        help="Path to the current formula+AST benchmark results.json bundle.",
    )
    parser.add_argument(
        "--dataset-path",
        default="benchmarks/eval_dataset.math_focus.json",
        help="Eval dataset path used to recover answer keys/evidence.",
    )
    parser.add_argument(
        "--output-dir",
        required=True,
        help="Directory where retrospective experiment outputs will be written.",
    )
    parser.add_argument(
        "--legacy-operation-results",
        default="",
        help="Optional historical operation-path results.json for overlap-only reporting.",
    )
    args = parser.parse_args()

    source_results = Path(args.source_results)
    dataset_path = Path(args.dataset_path)
    output_dir = Path(args.output_dir)

    rows = _load_per_question_rows(source_results)
    examples_by_id = _index_examples(dataset_path)
    numeric_rows = _numeric_slice(rows, examples_by_id)
    active_ids = [str(row.get("id") or "") for row in numeric_rows]

    llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0.0)

    detailed_rows: List[Dict[str, Any]] = []
    direct_scored_rows: List[ScoredAnswer] = []
    formula_scored_rows: List[ScoredAnswer] = []

    for row in numeric_rows:
        question_id = str(row.get("id") or "")
        example = examples_by_id[question_id]
        formula_scored = _score_formula_row(llm=llm, example=example, row=row)
        direct_scored = _run_direct_calc(llm=llm, example=example, row=row)
        formula_scored_rows.append(formula_scored)
        direct_scored_rows.append(direct_scored)
        detailed_rows.append(
            {
                "id": question_id,
                "question": example.question,
                "formula_ast": {
                    "answer": formula_scored.answer,
                    "equivalence": formula_scored.equivalence,
                    "grounding": formula_scored.grounding,
                    "strict_correct": formula_scored.strict_correct,
                    "equivalence_debug": formula_scored.equivalence_debug,
                    "grounding_debug": formula_scored.grounding_debug,
                },
                "direct_calc": {
                    "answer": direct_scored.answer,
                    "equivalence": direct_scored.equivalence,
                    "grounding": direct_scored.grounding,
                    "strict_correct": direct_scored.strict_correct,
                    "equivalence_debug": direct_scored.equivalence_debug,
                    "grounding_debug": direct_scored.grounding_debug,
                },
            }
        )

    summary: Dict[str, Any] = {
        "source_results": str(source_results),
        "dataset_path": str(dataset_path),
        "n_questions": len(numeric_rows),
        "question_ids": active_ids,
        "excluded_question_ids": sorted(set(examples_by_id.keys()) - set(active_ids)),
        "direct_calc": {
            "strict_correct_rate": _strict_rate(direct_scored_rows),
            "equivalence_rate": _rate(direct_scored_rows, "equivalence"),
            "grounding_rate": _rate(direct_scored_rows, "grounding"),
        },
        "formula_ast": {
            "strict_correct_rate": _strict_rate(formula_scored_rows),
            "equivalence_rate": _rate(formula_scored_rows, "equivalence"),
            "grounding_rate": _rate(formula_scored_rows, "grounding"),
        },
    }

    if args.legacy_operation_results:
        legacy_rows = _load_per_question_rows(Path(args.legacy_operation_results))
        summary["legacy_operation"] = _legacy_overlap(
            llm=llm,
            examples_by_id=examples_by_id,
            legacy_rows=legacy_rows,
            active_ids=active_ids,
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "summary.json").write_text(
        json.dumps({"summary": summary, "per_question": detailed_rows}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (output_dir / "summary.md").write_text(
        _render_markdown(
            source_results=source_results,
            dataset_path=dataset_path,
            direct_rows=detailed_rows,
            summary=summary,
        )
        + "\n",
        encoding="utf-8",
    )

    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
