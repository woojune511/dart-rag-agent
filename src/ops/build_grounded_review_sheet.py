"""
Build review artifacts from a grounded draft dataset.

This helper turns a grounded draft JSON dataset into:
- a seed JSON file for review workflows
- a CSV worksheet for human verification against actual DART reports
- a summary JSON file with basic risk and priority counts

Usage:
    python -m src.ops.build_grounded_review_sheet \
        --dataset benchmarks/datasets/single_doc_eval_full.grounded_draft.json
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DART_RECEIPT_URL = "https://dart.fss.or.kr/dsaf001/main.do?rcpNo={rcept_no}"
YEAR_PATTERN = re.compile(r"20\d{2}")
NEGATIVE_PATTERNS = (
    "찾을 수 없",
    "계산할 수 없",
    "확인할 수 없",
    "비교 분석을 할 수 없",
    "정보가 없",
    "제공되지 않",
)


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
        parts = [_stringify_for_csv(item) for item in value]
        return " | ".join(part for part in parts if part)
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value).strip()


def _dedupe_preserve_order(values: Iterable[str]) -> List[str]:
    deduped: List[str] = []
    seen = set()
    for raw in values:
        value = str(raw or "").strip()
        if not value or value in seen:
            continue
        seen.add(value)
        deduped.append(value)
    return deduped


def _coerce_int(value: Any) -> int | None:
    try:
        if value is None or value == "":
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _extract_years(text: str) -> List[int]:
    return sorted({int(match.group(0)) for match in YEAR_PATTERN.finditer(text or "")})


def _question_year(item: Dict[str, Any]) -> int | None:
    explicit_year = _coerce_int(item.get("year"))
    if explicit_year:
        return explicit_year
    question = str(item.get("question") or item.get("query") or "")
    years = _extract_years(question)
    return years[0] if years else None


def _source_expected_refusal(item: Dict[str, Any]) -> bool:
    checkpoints = item.get("eval_checkpoints") or {}
    if not isinstance(checkpoints, dict):
        return False
    return bool(checkpoints.get("reject_expected", False))


def _iter_source_reports(item: Dict[str, Any]) -> List[Dict[str, Any]]:
    reports: List[Dict[str, Any]] = []
    first = item.get("source_report")
    if isinstance(first, dict):
        reports.append(dict(first))
    for raw in _as_list(item.get("source_reports")):
        if isinstance(raw, dict):
            reports.append(dict(raw))

    deduped: List[Dict[str, Any]] = []
    seen = set()
    for report in reports:
        key = (
            str(report.get("file_path") or "").strip(),
            str(report.get("rcept_no") or "").strip(),
            str(report.get("corp_name") or "").strip(),
            str(report.get("year") or "").strip(),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(report)
    return deduped


def _report_urls(reports: List[Dict[str, Any]]) -> List[str]:
    urls: List[str] = []
    for report in reports:
        rcept_no = str(report.get("rcept_no") or "").strip()
        if rcept_no:
            urls.append(DART_RECEIPT_URL.format(rcept_no=rcept_no))
    return _dedupe_preserve_order(urls)


def _report_paths(reports: List[Dict[str, Any]]) -> List[str]:
    return _dedupe_preserve_order(str(report.get("file_path") or "").strip() for report in reports)


def _flatten_evidence_quotes(item: Dict[str, Any]) -> List[str]:
    quotes: List[str] = []
    for row in _as_list(item.get("evidence")):
        if not isinstance(row, dict):
            continue
        quote = str(row.get("quote") or "").strip()
        if quote:
            quotes.append(quote)
    return quotes


def _flatten_section_paths(item: Dict[str, Any]) -> List[str]:
    section_paths = [
        str(section or "").strip()
        for section in _as_list(item.get("expected_sections"))
        if str(section or "").strip()
    ]
    return _dedupe_preserve_order(section_paths)


def _flatten_retrieval_preview(item: Dict[str, Any], limit: int = 5) -> List[str]:
    previews: List[str] = []
    for row in _as_list(item.get("retrieval_preview"))[:limit]:
        if isinstance(row, dict):
            section = str(row.get("section_path") or row.get("section") or "").strip()
            preview = str(row.get("preview") or row.get("text") or "").strip()
            value = " :: ".join(part for part in (section, preview) if part)
            if value:
                previews.append(value)
        else:
            value = str(row or "").strip()
            if value:
                previews.append(value)
    return previews


def _has_value(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, set, dict)):
        return bool(value)
    return True


def _risk_tags(item: Dict[str, Any]) -> List[str]:
    tags: List[str] = []
    source_expected_refusal = _source_expected_refusal(item)
    generated_expected_refusal = bool(item.get("expected_refusal"))
    answer_type = str(item.get("answer_type") or "").strip()
    answer_key = str(item.get("answer_key") or "").strip()
    question_year = _question_year(item)
    evidence_quotes = _flatten_evidence_quotes(item)
    expected_sections = _flatten_section_paths(item)
    expected_operands = _as_list(item.get("expected_operands"))
    reasoning_steps = _as_list(item.get("reasoning_steps"))
    source_reports = _iter_source_reports(item)

    if source_expected_refusal != generated_expected_refusal:
        tags.append("generated_refusal_mismatch")
    if generated_expected_refusal and not evidence_quotes:
        tags.append("refusal_without_evidence")
    if generated_expected_refusal and not expected_sections:
        tags.append("refusal_without_sections")
    if generated_expected_refusal and answer_type != "refusal":
        tags.append("partial_answer_refusal")
    if answer_type == "numeric" and not expected_operands:
        tags.append("numeric_without_operands")
    if not reasoning_steps:
        tags.append("missing_reasoning_steps")

    if question_year:
        combined_text = "\n".join([answer_key, *evidence_quotes])
        referenced_years = _extract_years(combined_text)
        evidence_years = _extract_years("\n".join(evidence_quotes))
        if referenced_years and question_year not in referenced_years:
            tags.append("possible_year_mismatch")
        if evidence_years and question_year not in evidence_years:
            tags.append("evidence_year_mismatch")

    if len(source_reports) > 1:
        tags.append("multi_report_grounding")

    if bool(item.get("expected_refusal")) and answer_key and any(pattern in answer_key for pattern in NEGATIVE_PATTERNS):
        if "다만" in answer_key or "하지만" in answer_key:
            tags.append("mixed_refusal_answer")

    return _dedupe_preserve_order(tags)


def _risk_score(tags: List[str]) -> int:
    weights = {
        "generated_refusal_mismatch": 4,
        "possible_year_mismatch": 4,
        "evidence_year_mismatch": 4,
        "refusal_without_evidence": 3,
        "refusal_without_sections": 2,
        "partial_answer_refusal": 2,
        "mixed_refusal_answer": 2,
        "numeric_without_operands": 1,
        "missing_reasoning_steps": 1,
        "multi_report_grounding": 1,
    }
    return sum(weights.get(tag, 1) for tag in tags)


def _priority(score: int) -> str:
    if score >= 6:
        return "high"
    if score >= 3:
        return "medium"
    return "low"


def prepare_review_records(rows: Iterable[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    total_rows = 0
    priority_counts = {"high": 0, "medium": 0, "low": 0}
    refusal_count = 0
    mismatch_count = 0

    for item in rows:
        if not isinstance(item, dict):
            continue
        total_rows += 1
        reports = _iter_source_reports(item)
        tags = _risk_tags(item)
        score = _risk_score(tags)
        priority = _priority(score)
        source_expected_refusal = _source_expected_refusal(item)
        generated_expected_refusal = bool(item.get("expected_refusal"))
        if generated_expected_refusal:
            refusal_count += 1
        if source_expected_refusal != generated_expected_refusal:
            mismatch_count += 1

        priority_counts[priority] += 1

        record = dict(item)
        record.update(
            {
                "source_expected_refusal": source_expected_refusal,
                "review_risk_tags": tags,
                "review_risk_score": score,
                "review_priority": priority,
                "source_report_paths": _report_paths(reports),
                "source_report_urls": _report_urls(reports),
                "retrieval_preview_lines": _flatten_retrieval_preview(item),
                "review_decision": "",
                "doc_check_status": "pending",
                "verified_answer_key": "",
                "verified_expected_refusal": "",
                "verified_expected_sections": [],
                "verified_evidence_quotes": [],
                "review_notes": "",
            }
        )
        records.append(record)

    records.sort(
        key=lambda row: (
            {"high": 0, "medium": 1, "low": 2}.get(str(row.get("review_priority") or "low"), 2),
            str(row.get("company") or ""),
            str(row.get("id") or ""),
        )
    )

    summary = {
        "total_rows": total_rows,
        "refusal_rows": refusal_count,
        "generated_refusal_mismatch_rows": mismatch_count,
        "priority_counts": priority_counts,
    }
    return records, summary


def _worksheet_rows(records: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    for record in records:
        rows.append(
            {
                "review_priority": _stringify_for_csv(record.get("review_priority")),
                "review_risk_score": _stringify_for_csv(record.get("review_risk_score")),
                "review_risk_tags": _stringify_for_csv(record.get("review_risk_tags")),
                "id": _stringify_for_csv(record.get("id")),
                "company": _stringify_for_csv(record.get("company")),
                "year": _stringify_for_csv(record.get("year")),
                "question": _stringify_for_csv(record.get("question") or record.get("query")),
                "answer_type": _stringify_for_csv(record.get("answer_type")),
                "source_expected_refusal": _stringify_for_csv(record.get("source_expected_refusal")),
                "generated_expected_refusal": _stringify_for_csv(record.get("expected_refusal")),
                "draft_answer_key": _stringify_for_csv(record.get("answer_key")),
                "draft_expected_sections": _stringify_for_csv(record.get("expected_sections")),
                "draft_evidence_quotes": _stringify_for_csv(_flatten_evidence_quotes(record)),
                "source_report_paths": _stringify_for_csv(record.get("source_report_paths")),
                "source_report_urls": _stringify_for_csv(record.get("source_report_urls")),
                "retrieval_preview": _stringify_for_csv(record.get("retrieval_preview_lines")),
                "verification_status": _stringify_for_csv(record.get("verification_status")),
                "review_decision": _stringify_for_csv(record.get("review_decision")),
                "doc_check_status": _stringify_for_csv(record.get("doc_check_status")),
                "verified_answer_key": _stringify_for_csv(record.get("verified_answer_key")),
                "verified_expected_refusal": _stringify_for_csv(record.get("verified_expected_refusal")),
                "verified_expected_sections": _stringify_for_csv(record.get("verified_expected_sections")),
                "verified_evidence_quotes": _stringify_for_csv(record.get("verified_evidence_quotes")),
                "review_notes": _stringify_for_csv(record.get("review_notes")),
            }
        )
    return rows


def _write_csv(path: Path, rows: List[Dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "review_priority",
        "review_risk_score",
        "review_risk_tags",
        "id",
        "company",
        "year",
        "question",
        "answer_type",
        "source_expected_refusal",
        "generated_expected_refusal",
        "draft_answer_key",
        "draft_expected_sections",
        "draft_evidence_quotes",
        "source_report_paths",
        "source_report_urls",
        "retrieval_preview",
        "verification_status",
        "review_decision",
        "doc_check_status",
        "verified_answer_key",
        "verified_expected_refusal",
        "verified_expected_sections",
        "verified_evidence_quotes",
        "review_notes",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build review artifacts from a grounded draft dataset.")
    parser.add_argument("--dataset", required=True, help="Path to grounded draft dataset JSON.")
    parser.add_argument(
        "--output-dir",
        help="Directory to write artifacts into. Defaults to <dataset-stem>.review beside the dataset.",
    )
    args = parser.parse_args()

    dataset_path = _normalise_path(args.dataset)
    output_dir = (
        _normalise_path(args.output_dir)
        if args.output_dir
        else dataset_path.parent / f"{dataset_path.stem}.review"
    )

    rows = _load_json(dataset_path)
    if not isinstance(rows, list):
        raise ValueError(f"Dataset must be a JSON list: {dataset_path}")

    records, summary = prepare_review_records(rows)
    worksheet_path = output_dir / "review_sheet.csv"
    seed_path = output_dir / "review_seed.json"
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
    print(f"Rows output : {summary['total_rows']}")
    print(f"Worksheet   : {worksheet_path}")
    print(f"Seed JSON   : {seed_path}")
    print(f"Summary     : {summary_path}")


if __name__ == "__main__":
    main()
