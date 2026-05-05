"""
Build annotation scaffold artifacts from question-only or partial eval datasets.

This helper is intended for the stage where we already have a dataset of
questions/tasks, but the canonical answers/evidence have not been annotated yet.

It creates:
- a seed JSON file with normalized annotation fields
- a CSV worksheet for manual filling
- a summary JSON report with coverage stats

Usage:
    python -m src.ops.build_annotation_sheet \
        --dataset benchmarks/datasets/single_doc_eval_full.json
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _normalise_path(path_value: str | Path) -> Path:
    path = Path(path_value)
    if not path.is_absolute():
        path = (PROJECT_ROOT / path).resolve()
    return path


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _as_list(value: Any) -> List[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _stringify_for_csv(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return " | ".join(_stringify_for_csv(item) for item in value if _stringify_for_csv(item))
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value).strip()


def _coerce_id(item: Dict[str, Any], fallback_index: int) -> str:
    for key in ("id", "query_id"):
        value = str(item.get(key) or "").strip()
        if value:
            return value
    return f"row_{fallback_index:04d}"


def _coerce_question(item: Dict[str, Any]) -> str:
    for key in ("question", "query"):
        value = str(item.get(key) or "").strip()
        if value:
            return value
    return ""


def _coerce_answer_key(item: Dict[str, Any]) -> str:
    for key in ("answer_key", "ground_truth_answer", "ground_truth"):
        value = str(item.get(key) or "").strip()
        if value:
            return value
    return ""


def _coerce_expected_sections(item: Dict[str, Any]) -> List[str]:
    raw_sections = item.get("expected_sections")
    if raw_sections is None:
        raw_sections = item.get("ground_truth_context_ids")
    if raw_sections is None:
        raw_sections = item.get("section")
    sections: List[str] = []
    for raw in _as_list(raw_sections):
        value = str(raw or "").strip()
        if value and value not in sections:
            sections.append(value)
    return sections


def _coerce_evidence(item: Dict[str, Any], expected_sections: List[str]) -> List[Dict[str, Any]]:
    evidence_rows = item.get("evidence") or []
    evidence: List[Dict[str, Any]] = []
    for row in evidence_rows:
        if not isinstance(row, dict):
            continue
        quote = str(row.get("quote") or "").strip()
        section_path = str(row.get("section_path") or "").strip()
        if not quote and not section_path:
            continue
        evidence.append(
            {
                "section_path": section_path,
                "quote": quote,
                "quote_type": str(row.get("quote_type") or "verbatim"),
                "why_it_supports_answer": str(row.get("why_it_supports_answer") or "").strip(),
            }
        )

    if evidence:
        return evidence

    quote_rows = _as_list(item.get("ground_truth_evidence_quotes"))
    fallback_section = expected_sections[0] if expected_sections else ""
    for quote in quote_rows:
        quote_text = str(quote or "").strip()
        if not quote_text:
            continue
        evidence.append(
            {
                "section_path": fallback_section,
                "quote": quote_text,
                "quote_type": "verbatim",
                "why_it_supports_answer": "imported from ground_truth_evidence_quotes",
            }
        )
    return evidence


def _coerce_required_entities(item: Dict[str, Any]) -> List[str]:
    entities: List[str] = []
    for raw in _as_list(item.get("required_entities")):
        value = str(raw or "").strip()
        if value and value not in entities:
            entities.append(value)

    checkpoints = item.get("eval_checkpoints") or {}
    if isinstance(checkpoints, dict):
        for raw in _as_list(checkpoints.get("required_keywords")):
            value = str(raw or "").strip()
            if value and value not in entities:
                entities.append(value)
    return entities


def _coerce_expected_operands(item: Dict[str, Any]) -> List[Dict[str, Any]]:
    expected_operands: List[Dict[str, Any]] = []
    for row in _as_list(item.get("expected_operands")):
        if not isinstance(row, dict):
            continue
        expected_operands.append(dict(row))

    if expected_operands:
        return expected_operands

    checkpoints = item.get("eval_checkpoints") or {}
    if isinstance(checkpoints, dict):
        for raw in _as_list(checkpoints.get("required_operands")):
            label = str(raw or "").strip()
            if not label:
                continue
            expected_operands.append(
                {
                    "label": label,
                    "period": "",
                    "raw_value": "",
                    "raw_unit": "",
                }
            )
    return expected_operands


def _coerce_expected_refusal(item: Dict[str, Any]) -> bool:
    if "expected_refusal" in item:
        return bool(item.get("expected_refusal"))
    checkpoints = item.get("eval_checkpoints") or {}
    if isinstance(checkpoints, dict):
        return bool(checkpoints.get("reject_expected", False))
    return False


def _infer_answer_type(
    item: Dict[str, Any],
    question: str,
    *,
    expected_refusal: bool,
    expected_operands: List[Dict[str, Any]],
) -> str:
    existing = str(item.get("answer_type") or "").strip()
    if existing:
        return existing
    if expected_refusal:
        return "refusal"
    if expected_operands:
        return "numeric"

    numeric_markers = ("얼마", "비율", "비중", "%", "증가율", "감소율", "차이", "합계", "계산")
    if any(marker in question for marker in numeric_markers):
        return "numeric"

    summary_markers = ("무엇", "어떻게", "요약", "설명", "영향", "배경", "원인")
    if any(marker in question for marker in summary_markers):
        return "summary"
    return "span"


def _suggest_category(
    item: Dict[str, Any],
    question: str,
    *,
    expected_refusal: bool,
    expected_operands: List[Dict[str, Any]],
) -> str:
    existing = str(item.get("category") or "").strip()
    if existing:
        return existing
    if expected_refusal:
        return "adversarial-out-of-domain"
    if expected_operands:
        trend_markers = ("추이", "전년 대비", "증가율", "감소율")
        if any(marker in question for marker in trend_markers):
            return "multi-hop-calculation"
        return "multi-hop-calculation"

    expected_agents = {str(agent).strip() for agent in _as_list(item.get("expected_agents")) if str(agent).strip()}
    if "Researcher" in expected_agents:
        return "synthesis-abstract"
    return "single-hop-fact"


def _merge_notes(item: Dict[str, Any], source_name: str) -> str:
    parts: List[str] = []
    existing = str(item.get("notes") or "").strip()
    if existing:
        parts.append(existing)
    theme = str(item.get("theme") or "").strip()
    if theme:
        parts.append(f"theme={theme}")
    difficulty = str(item.get("difficulty") or "").strip()
    if difficulty:
        parts.append(f"difficulty={difficulty}")
    expected_agents = [str(agent).strip() for agent in _as_list(item.get("expected_agents")) if str(agent).strip()]
    if expected_agents:
        parts.append(f"expected_agents={', '.join(expected_agents)}")
    if source_name:
        parts.append(f"source_dataset={source_name}")
    return " | ".join(parts)


def _missing_fields(
    *,
    answer_key: str,
    expected_sections: List[str],
    evidence: List[Dict[str, Any]],
    answer_type: str,
    expected_operands: List[Dict[str, Any]],
) -> List[str]:
    missing: List[str] = []
    if not answer_key:
        missing.append("answer_key")
    if not expected_sections:
        missing.append("expected_sections")
    if not evidence:
        missing.append("evidence")
    if answer_type == "numeric" and not expected_operands:
        missing.append("expected_operands")
    return missing


def _annotation_status(missing: List[str]) -> str:
    if not missing:
        return "ready_for_review"
    if set(missing) == {"answer_key", "expected_sections", "evidence"}:
        return "question_only"
    return "partial"


def _source_dataset_kind(item: Dict[str, Any]) -> str:
    if "query" in item and "question" not in item:
        return "question_only_taskset"
    if any(key in item for key in ("answer_key", "ground_truth", "ground_truth_answer", "evidence")):
        return "partial_eval_dataset"
    return "unknown"


def prepare_annotation_records(
    rows: Iterable[Dict[str, Any]],
    *,
    source_name: str = "",
    only_incomplete: bool = False,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    total_rows = 0
    skipped_rows = 0

    coverage = {
        "with_answer_key": 0,
        "with_expected_sections": 0,
        "with_evidence": 0,
        "with_expected_operands": 0,
        "expected_refusal": 0,
        "question_only_rows": 0,
        "partial_rows": 0,
    }

    for index, item in enumerate(rows, start=1):
        total_rows += 1
        if not isinstance(item, dict):
            skipped_rows += 1
            continue

        question = _coerce_question(item)
        if not question:
            skipped_rows += 1
            continue

        query_id = _coerce_id(item, index)
        answer_key = _coerce_answer_key(item)
        expected_sections = _coerce_expected_sections(item)
        evidence = _coerce_evidence(item, expected_sections)
        expected_operands = _coerce_expected_operands(item)
        expected_refusal = _coerce_expected_refusal(item)
        required_entities = _coerce_required_entities(item)
        answer_type = _infer_answer_type(
            item,
            question,
            expected_refusal=expected_refusal,
            expected_operands=expected_operands,
        )
        suggested_category = _suggest_category(
            item,
            question,
            expected_refusal=expected_refusal,
            expected_operands=expected_operands,
        )
        reasoning_steps = [
            str(step).strip()
            for step in _as_list(item.get("reasoning_steps"))
            if str(step).strip()
        ]
        verification_status = str(item.get("verification_status") or "draft").strip() or "draft"
        notes = _merge_notes(item, source_name)
        missing = _missing_fields(
            answer_key=answer_key,
            expected_sections=expected_sections,
            evidence=evidence,
            answer_type=answer_type,
            expected_operands=expected_operands,
        )
        annotation_status = _annotation_status(missing)
        dataset_kind = _source_dataset_kind(item)

        if dataset_kind == "question_only_taskset":
            coverage["question_only_rows"] += 1
        else:
            coverage["partial_rows"] += 1

        if answer_key:
            coverage["with_answer_key"] += 1
        if expected_sections:
            coverage["with_expected_sections"] += 1
        if evidence:
            coverage["with_evidence"] += 1
        if expected_operands:
            coverage["with_expected_operands"] += 1
        if expected_refusal:
            coverage["expected_refusal"] += 1

        record = dict(item)
        record.update(
            {
                "id": query_id,
                "question": question,
                "answer_key": answer_key,
                "expected_sections": expected_sections,
                "evidence": evidence,
                "required_entities": required_entities,
                "answer_type": answer_type,
                "expected_refusal": expected_refusal,
                "reasoning_steps": reasoning_steps,
                "expected_operands": expected_operands,
                "verification_status": verification_status,
                "suggested_category": suggested_category,
                "annotation_status": annotation_status,
                "missing_fields": missing,
                "source_dataset_kind": dataset_kind,
                "notes": notes,
            }
        )

        if only_incomplete and not missing:
            continue
        records.append(record)

    summary = {
        "source_name": source_name,
        "total_rows": total_rows,
        "output_rows": len(records),
        "skipped_rows": skipped_rows,
        **coverage,
    }
    return records, summary


def _worksheet_rows(records: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    for record in records:
        evidence = record.get("evidence") or []
        evidence_quotes = [str(row.get("quote") or "").strip() for row in evidence if str(row.get("quote") or "").strip()]
        evidence_sections = [
            str(row.get("section_path") or "").strip()
            for row in evidence
            if str(row.get("section_path") or "").strip()
        ]
        operand_labels = [
            str(row.get("label") or "").strip()
            for row in (record.get("expected_operands") or [])
            if str(row.get("label") or "").strip()
        ]
        rows.append(
            {
                "id": str(record.get("id") or ""),
                "question": str(record.get("question") or ""),
                "company": _stringify_for_csv(record.get("company")),
                "year": _stringify_for_csv(record.get("year")),
                "category": _stringify_for_csv(record.get("category")),
                "suggested_category": _stringify_for_csv(record.get("suggested_category")),
                "answer_type": _stringify_for_csv(record.get("answer_type")),
                "expected_refusal": _stringify_for_csv(record.get("expected_refusal")),
                "expected_sections": _stringify_for_csv(record.get("expected_sections")),
                "required_entities": _stringify_for_csv(record.get("required_entities")),
                "expected_operands": _stringify_for_csv(operand_labels),
                "reasoning_steps": _stringify_for_csv(record.get("reasoning_steps")),
                "answer_key": _stringify_for_csv(record.get("answer_key")),
                "evidence_section_paths": _stringify_for_csv(evidence_sections),
                "evidence_quotes": _stringify_for_csv(evidence_quotes),
                "annotation_status": _stringify_for_csv(record.get("annotation_status")),
                "missing_fields": _stringify_for_csv(record.get("missing_fields")),
                "verification_status": _stringify_for_csv(record.get("verification_status")),
                "theme": _stringify_for_csv(record.get("theme")),
                "difficulty": _stringify_for_csv(record.get("difficulty")),
                "expected_agents": _stringify_for_csv(record.get("expected_agents")),
                "notes": _stringify_for_csv(record.get("notes")),
            }
        )
    return rows


def _write_csv(path: Path, rows: List[Dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "id",
        "question",
        "company",
        "year",
        "category",
        "suggested_category",
        "answer_type",
        "expected_refusal",
        "expected_sections",
        "required_entities",
        "expected_operands",
        "reasoning_steps",
        "answer_key",
        "evidence_section_paths",
        "evidence_quotes",
        "annotation_status",
        "missing_fields",
        "verification_status",
        "theme",
        "difficulty",
        "expected_agents",
        "notes",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build annotation scaffold artifacts from a dataset JSON file.")
    parser.add_argument("--dataset", required=True, help="Path to source dataset JSON.")
    parser.add_argument(
        "--output-dir",
        help="Directory to write artifacts into. Defaults to <dataset-stem>.annotation beside the dataset.",
    )
    parser.add_argument(
        "--only-incomplete",
        action="store_true",
        help="Only include rows that are still missing answer/evidence/section fields.",
    )
    args = parser.parse_args()

    dataset_path = _normalise_path(args.dataset)
    output_dir = (
        _normalise_path(args.output_dir)
        if args.output_dir
        else dataset_path.parent / f"{dataset_path.stem}.annotation"
    )

    rows = _load_json(dataset_path)
    if not isinstance(rows, list):
        raise ValueError(f"Dataset must be a JSON list: {dataset_path}")

    records, summary = prepare_annotation_records(
        rows,
        source_name=dataset_path.name,
        only_incomplete=args.only_incomplete,
    )

    worksheet_path = output_dir / "annotation_sheet.csv"
    seed_path = output_dir / "annotation_seed.json"
    summary_path = output_dir / "summary.json"

    _write_csv(worksheet_path, _worksheet_rows(records))
    _write_json(seed_path, records)
    _write_json(
        summary_path,
        {
            **summary,
            "dataset_path": str(dataset_path),
            "worksheet_path": str(worksheet_path),
            "seed_path": str(seed_path),
        },
    )

    print(f"Dataset     : {dataset_path}")
    print(f"Rows output : {summary['output_rows']} / {summary['total_rows']}")
    print(f"Worksheet   : {worksheet_path}")
    print(f"Seed JSON   : {seed_path}")
    print(f"Summary     : {summary_path}")


if __name__ == "__main__":
    main()
