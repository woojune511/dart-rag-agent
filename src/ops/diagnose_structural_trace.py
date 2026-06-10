"""Summarize where a benchmark result lost structural numeric evidence.

This is a read-only diagnostic for local benchmark result bundles. It compares
dataset-level expected values with three runtime surfaces:

1. retrieved previews / runtime evidence
2. structured subtask outputs
3. final resolved calculation operands

The output is intentionally compact Markdown so it can be pasted into
evaluation notes without committing raw benchmark artifacts.
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


NUMBER_RE = re.compile(r"\(?-?\d[\d,]*(?:\.\d+)?\)?")


@dataclass(frozen=True)
class ExpectedValue:
    label: str
    raw_value: str
    raw_unit: str
    source: str


def _read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _compact_text(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _normalize_number_text(value: str) -> str:
    return re.sub(r"[^0-9.]", "", value or "")


def _format_value(raw_value: str, raw_unit: str = "") -> str:
    return f"{raw_value}{raw_unit}" if raw_unit else raw_value


def _extract_numbers(text: str) -> list[str]:
    return [match.group(0) for match in NUMBER_RE.finditer(text or "")]


def _load_dataset(path: Path) -> dict[str, dict[str, Any]]:
    data = _read_json(path)
    if not isinstance(data, list):
        raise ValueError(f"dataset must be a list: {path}")
    return {str(row.get("id")): row for row in data if row.get("id")}


def _iter_question_results(result_dir: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in sorted(result_dir.glob("*/results.json")):
        data = _read_json(path)
        for run in data.get("results", []):
            full_eval = run.get("full_eval") or {}
            for question in full_eval.get("per_question") or []:
                copied = dict(question)
                copied["_result_file"] = str(path)
                copied["_company_dir"] = path.parent.name
                rows.append(copied)
    return rows


def _expected_values(dataset_row: dict[str, Any]) -> list[ExpectedValue]:
    values: list[ExpectedValue] = []
    for operand in dataset_row.get("expected_operands") or []:
        raw_value = str(operand.get("raw_value") or "").strip()
        if not raw_value:
            continue
        values.append(
            ExpectedValue(
                label=str(operand.get("label") or "").strip(),
                raw_value=raw_value,
                raw_unit=str(operand.get("raw_unit") or "").strip(),
                source="expected_operands",
            )
        )
    if values:
        return values

    seen: set[str] = set()
    for evidence in dataset_row.get("evidence") or []:
        quote = str(evidence.get("quote") or "")
        for number in _extract_numbers(quote):
            normalized = _normalize_number_text(number)
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            label = quote.replace(number, "").strip(" :|,，")
            values.append(
                ExpectedValue(
                    label=label or "evidence numeric value",
                    raw_value=number,
                    raw_unit="",
                    source="evidence_quote",
                )
            )
    return values


def _final_operands(question: dict[str, Any]) -> list[dict[str, Any]]:
    trace = question.get("resolved_calculation_trace") or {}
    operands = trace.get("calculation_operands") or []
    return [operand for operand in operands if isinstance(operand, dict)]


def _structured_text(question: dict[str, Any]) -> str:
    payload = {
        "structured_result": question.get("structured_result"),
        "resolved_calculation_trace": question.get("resolved_calculation_trace"),
    }
    return _compact_text(payload)


def _retrieval_text(question: dict[str, Any]) -> str:
    payload = {
        "retrieved_previews": question.get("retrieved_previews"),
        "runtime_evidence": question.get("runtime_evidence"),
        "retrieval_debug_trace": question.get("retrieval_debug_trace"),
    }
    return _compact_text(payload)


def _value_presence(values: list[ExpectedValue], text: str) -> tuple[int, list[str]]:
    found: list[str] = []
    normalized_text = _normalize_number_text(text)
    for value in values:
        normalized = _normalize_number_text(value.raw_value)
        if normalized and normalized in normalized_text:
            found.append(_format_value(value.raw_value, value.raw_unit))
    return len(found), found


def _operand_values(operands: list[dict[str, Any]]) -> list[str]:
    values: list[str] = []
    for operand in operands:
        raw_value = str(operand.get("raw_value") or "").strip()
        if raw_value:
            values.append(_format_value(raw_value, str(operand.get("raw_unit") or "").strip()))
    return values


def _classify(
    judgement: str,
    expected_count: int,
    retrieved_count: int,
    structured_count: int,
    final_count: int,
) -> str:
    if judgement == "PASS":
        return "pass"
    if expected_count == 0:
        return "benchmark contract missing expected values"
    if structured_count >= expected_count and final_count < expected_count:
        return "dependency binding / final operand selection"
    if final_count >= expected_count:
        return "calculation or answer contract"
    if retrieved_count >= expected_count and structured_count < expected_count:
        return "evidence extraction / subtask projection"
    if retrieved_count < expected_count:
        return "retrieval coverage or evidence preservation"
    return "unclassified trace mismatch"


def _markdown_table(rows: list[dict[str, str]]) -> str:
    headers = [
        "Question",
        "Judgement",
        "Expected values seen in retrieval",
        "Expected values seen before final calc",
        "Expected values in final operands",
        "Final operands",
        "Failure layer",
    ]
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"]
    for row in rows:
        lines.append("| " + " | ".join(row[header] for header in headers) + " |")
    return "\n".join(lines)


def build_report(result_dir: Path, dataset_path: Path, question_ids: set[str] | None = None) -> str:
    dataset = _load_dataset(dataset_path)
    questions = _iter_question_results(result_dir)
    if question_ids:
        questions = [question for question in questions if str(question.get("id")) in question_ids]

    rows: list[dict[str, str]] = []
    detail_sections: list[str] = []
    for question in sorted(questions, key=lambda item: str(item.get("id"))):
        qid = str(question.get("id"))
        dataset_row = dataset.get(qid, {})
        expected = _expected_values(dataset_row)
        retrieved_count, retrieved_found = _value_presence(expected, _retrieval_text(question))
        structured_count, structured_found = _value_presence(expected, _structured_text(question))
        final_operands = _final_operands(question)
        final_text = _compact_text(final_operands)
        final_count, final_found = _value_presence(expected, final_text)
        final_operand_values = _operand_values(final_operands)
        judgement = str(question.get("numeric_final_judgement") or "")
        failure_layer = _classify(
            judgement=judgement,
            expected_count=len(expected),
            retrieved_count=retrieved_count,
            structured_count=structured_count,
            final_count=final_count,
        )
        rows.append(
            {
                "Question": f"`{qid}`",
                "Judgement": judgement or "-",
                "Expected values seen in retrieval": f"{retrieved_count}/{len(expected)}"
                + (f": {', '.join(retrieved_found)}" if retrieved_found else ""),
                "Expected values seen before final calc": f"{structured_count}/{len(expected)}"
                + (f": {', '.join(structured_found)}" if structured_found else ""),
                "Expected values in final operands": f"{final_count}/{len(expected)}"
                + (f": {', '.join(final_found)}" if final_found else ""),
                "Final operands": "<br>".join(final_operand_values) or "-",
                "Failure layer": failure_layer,
            }
        )
        expected_rendered = ", ".join(
            _format_value(value.raw_value, value.raw_unit) for value in expected
        ) or "-"
        detail_sections.append(
            "\n".join(
                [
                    f"### `{qid}`",
                    "",
                    f"- Expected values: {expected_rendered}",
                    f"- Answer: {question.get('answer') or '-'}",
                    f"- Numeric debug reason: {(question.get('numeric_debug') or {}).get('equivalence', {}).get('reason', '-')}",
                    f"- Grounding reason: {(question.get('numeric_debug') or {}).get('grounding', {}).get('reason', '-')}",
                ]
            )
        )

    title = "# Structural Trace Diagnostic"
    intro = (
        "Read-only diagnostic comparing dataset expected values with retrieval, "
        "structured runtime state, and final calculation operands."
    )
    return "\n\n".join([title, intro, _markdown_table(rows), *detail_sections]).rstrip() + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--result-dir",
        type=Path,
        required=True,
        help="Benchmark result directory containing per-company results.json files.",
    )
    parser.add_argument(
        "--dataset",
        type=Path,
        default=Path("benchmarks/datasets/single_doc_eval_full.curated.json"),
        help="Evaluation dataset with expected operands/evidence.",
    )
    parser.add_argument(
        "--question-id",
        action="append",
        default=[],
        help="Question id to include. May be passed multiple times.",
    )
    parser.add_argument("--output", type=Path, help="Optional Markdown output path.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = build_report(
        result_dir=args.result_dir,
        dataset_path=args.dataset,
        question_ids=set(args.question_id) if args.question_id else None,
    )
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(report, encoding="utf-8")
    else:
        print(report)


if __name__ == "__main__":
    main()
