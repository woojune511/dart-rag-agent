"""Audit curated dataset evidence under the numeric/narrative hybrid policy."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Iterable, List

PROJECT_ROOT = Path(__file__).resolve().parents[2]

NUMERIC_HINTS = (
    "계산",
    "비율",
    "증가율",
    "감소율",
    "증가액",
    "감소액",
    "차이",
    "몇 배",
    "얼마",
    "합산",
    "규모",
    "매출 대비",
    "영업이익률",
    "비중",
    "roa",
    "roe",
    "bis",
    "capex",
)

NARRATIVE_HINTS = (
    "요약",
    "원인",
    "배경",
    "설명",
    "사례",
    "영향",
    "전략",
    "리스크",
    "의미",
    "왜",
    "어떤",
    "어떻게",
    "적용",
    "관리",
    "대응",
)

NARRATIVE_QUOTE_HINTS = (
    "원인",
    "배경",
    "설명",
    "시나리오",
    "리스크",
    "대응",
    "전략",
    "적립",
    "영향",
    "사례",
    "관리",
    "추진",
    "확보",
    "선점",
    "확대",
)

SUPPORTING_SECTION_HINTS = (
    "증권의 발행",
    "자금조달",
    "사용실적",
    "사채",
    "차입금",
    "주식의 총수",
    "배당",
    "주권",
)


def _normalise_path(path_value: str | Path) -> Path:
    path = Path(path_value)
    if not path.is_absolute():
        path = (PROJECT_ROOT / path).resolve()
    return path


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _with_extension(prefix: Path, extension: str) -> Path:
    return prefix.parent / f"{prefix.name}{extension}"


def _join_list(values: Iterable[str]) -> str:
    cleaned = [str(value).strip() for value in values if str(value).strip()]
    return " || ".join(cleaned)


def _has_digit(text: str) -> bool:
    return any(char.isdigit() for char in text)


def _looks_like_table_quote(text: str) -> bool:
    stripped = text.strip()
    if "|" in stripped:
        return True
    tokens = [token for token in stripped.split() if token]
    numeric_tokens = [token for token in tokens if any(char.isdigit() for char in token)]
    rich_numeric_tokens = [
        token
        for token in numeric_tokens
        if any(marker in token for marker in (",", ".", "%", "원", "억원", "백만원", "천원", "조", "배", "(", ")"))
    ]
    return len(numeric_tokens) >= 2 and len(tokens) <= 6 and bool(rich_numeric_tokens)


def _looks_like_numeric_quote(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return False
    if _looks_like_table_quote(stripped):
        return True
    if not _has_digit(stripped):
        return False
    numeric_markers = ("%", "원", "억원", "백만원", "천원", "조", "배", "capex", "roa", "roe", "bis")
    lower = stripped.lower()
    return any(marker in stripped for marker in numeric_markers) or any(marker in lower for marker in numeric_markers)


def _needs_numeric(row: Dict[str, Any]) -> bool:
    if bool(row.get("expected_refusal", False)):
        return False
    answer_type = str(row.get("answer_type") or "").lower()
    question = str(row.get("question") or row.get("query") or "").lower()
    category = str(row.get("category") or "").lower()
    if answer_type == "numeric":
        return True
    if "numeric" in category:
        return True
    return any(hint in question for hint in NUMERIC_HINTS)


def _needs_narrative(row: Dict[str, Any]) -> bool:
    if bool(row.get("expected_refusal", False)):
        return False
    answer_type = str(row.get("answer_type") or "").lower()
    question = str(row.get("question") or row.get("query") or "").lower()
    if answer_type == "summary":
        return True
    return any(hint in question for hint in NARRATIVE_HINTS)


def _is_supporting_section(section_path: str, row: Dict[str, Any]) -> bool:
    lower_section = section_path.lower()
    if any(hint in lower_section for hint in SUPPORTING_SECTION_HINTS):
        question = str(row.get("question") or row.get("query") or "")
        question_lower = question.lower()
        if "자금조달" in question or "증권의 발행" in question:
            return False
        if "capex" in question_lower or "투자" in question or "설비" in question:
            return True
        return True
    return False


def _quote_has_narrative_hint(text: str, why: str) -> bool:
    merged = f"{text} {why}".lower()
    return any(hint in merged for hint in NARRATIVE_QUOTE_HINTS)


def infer_row_policy(row: Dict[str, Any]) -> Dict[str, Any]:
    row_id = str(row.get("id") or "")
    question = str(row.get("question") or row.get("query") or "")
    refusal = bool(row.get("expected_refusal", False))
    needs_numeric = _needs_numeric(row)
    needs_narrative = _needs_narrative(row)

    if refusal:
        strategy = "refusal"
    elif needs_numeric and needs_narrative:
        strategy = "hybrid"
    elif needs_numeric:
        strategy = "numeric"
    else:
        strategy = "narrative"

    numeric_sections: List[str] = []
    narrative_sections: List[str] = []
    supporting_sections: List[str] = []
    numeric_quotes: List[str] = []
    narrative_quotes: List[str] = []
    supporting_quotes: List[str] = []
    item_roles: List[Dict[str, str]] = []
    structured_numeric_quotes: List[str] = []

    for item in list(row.get("evidence") or []):
        section_path = str(item.get("section_path") or "").strip()
        quote = str(item.get("quote") or "").strip()
        why = str(item.get("why_it_supports_answer") or "").strip()
        supporting = _is_supporting_section(section_path, row)
        numeric_quote = _looks_like_numeric_quote(quote)
        has_narrative_hint = _quote_has_narrative_hint(quote, why)

        if supporting:
            role = "supporting"
        elif needs_narrative and has_narrative_hint and "|" not in quote:
            role = "narrative_canonical"
        elif needs_numeric and numeric_quote:
            role = "numeric_canonical"
        elif needs_narrative:
            role = "narrative_canonical"
        elif numeric_quote:
            role = "numeric_canonical"
        else:
            role = "supporting"

        item_roles.append(
            {
                "section_path": section_path,
                "quote": quote,
                "role": role,
            }
        )

        if role == "numeric_canonical":
            if section_path not in numeric_sections:
                numeric_sections.append(section_path)
            if quote:
                numeric_quotes.append(quote)
                if _looks_like_table_quote(quote):
                    structured_numeric_quotes.append(quote)
        elif role == "narrative_canonical":
            if section_path not in narrative_sections:
                narrative_sections.append(section_path)
            if quote:
                narrative_quotes.append(quote)
        else:
            if section_path not in supporting_sections:
                supporting_sections.append(section_path)
            if quote:
                supporting_quotes.append(quote)

    for section_path in list(row.get("expected_sections") or []):
        if (
            section_path
            and section_path not in numeric_sections
            and section_path not in narrative_sections
            and section_path not in supporting_sections
        ):
            supporting_sections.append(section_path)

    flags: List[str] = []
    answer_type = str(row.get("answer_type") or "").lower()
    if answer_type == "refusal" and not refusal:
        flags.append("answer_type_refusal_but_expected_refusal_false")
    if needs_numeric and not numeric_quotes:
        flags.append("needs_numeric_but_no_numeric_evidence")
    if needs_numeric and numeric_quotes and not structured_numeric_quotes:
        flags.append("numeric_without_structured_quote")
    if needs_narrative and not narrative_quotes:
        flags.append("needs_narrative_but_no_narrative_evidence")
    if len(numeric_sections) > 1:
        flags.append("multiple_numeric_sections")
    if len(narrative_sections) > 1:
        flags.append("multiple_narrative_sections")

    return {
        "id": row_id,
        "company": str(row.get("company") or ""),
        "year": row.get("year"),
        "question": question,
        "doc_scope": _doc_scope(row),
        "answer_type": str(row.get("answer_type") or ""),
        "expected_refusal": refusal,
        "recommended_strategy": strategy,
        "needs_numeric": needs_numeric,
        "needs_narrative": needs_narrative,
        "numeric_canonical_sections": numeric_sections,
        "narrative_canonical_sections": narrative_sections,
        "supporting_sections": supporting_sections,
        "numeric_evidence_quotes": numeric_quotes,
        "structured_numeric_evidence_quotes": structured_numeric_quotes,
        "narrative_evidence_quotes": narrative_quotes,
        "supporting_evidence_quotes": supporting_quotes,
        "evidence_item_roles": item_roles,
        "audit_flags": flags,
    }


def _markdown_file_link(label: str, file_path: str) -> str:
    absolute = _normalise_path(file_path)
    return f"[{label}](<{absolute.as_posix()}>)"


def _source_reports(row: Dict[str, Any]) -> List[Dict[str, Any]]:
    reports = list(row.get("source_reports") or [])
    if not reports and row.get("source_report"):
        reports = [dict(row["source_report"])]
    return reports


def _doc_scope(row: Dict[str, Any]) -> str:
    explicit = str(row.get("doc_scope") or "").strip()
    if explicit:
        return explicit
    return "multi_report" if len(_source_reports(row)) > 1 else "single_report"


def _source_report_label(report: Dict[str, Any]) -> str:
    year = report.get("year", "")
    report_type = report.get("report_type", "사업보고서")
    rcept_no = report.get("rcept_no", "")
    return f"{year} {report_type} ({rcept_no})".strip()


def render_markdown(curated_rows: List[Dict[str, Any]], audits: List[Dict[str, Any]]) -> str:
    audit_map = {item["id"]: item for item in audits}
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for row in curated_rows:
        grouped.setdefault(str(row.get("company") or ""), []).append(row)

    lines: List[str] = [
        "# Evidence Policy Audit",
        "",
        "Hybrid rule applied:",
        "- numeric meaning: confirm with surrounding narrative, headers, notes",
        "- numeric value: prefer table/structured quote when available",
        "- explanation/cause/use case: prefer narrative prose",
        "- financing/use-of-proceeds type sections: supporting unless the question is directly about financing",
        "",
    ]

    for company in sorted(grouped):
        lines.extend([f"## {company}", ""])
        for row in grouped[company]:
            row_id = str(row.get("id") or "")
            audit = audit_map[row_id]
            reports = _source_reports(row)
            lines.extend(
                [
                    f"### {row_id}",
                    "",
                    f"- question: {row.get('question') or row.get('query') or ''}",
                    f"- doc_scope: {audit['doc_scope']}",
                    f"- strategy: {audit['recommended_strategy']}",
                    f"- needs_numeric: {audit['needs_numeric']}",
                    f"- needs_narrative: {audit['needs_narrative']}",
                    f"- flags: {_join_list(audit['audit_flags']) or '-'}",
                    "",
                    "source reports:",
                ]
            )
            for report in reports:
                file_path = str(report.get("file_path") or "").strip()
                label = _source_report_label(report)
                lines.append(f"- {_markdown_file_link(label, file_path) if file_path else label}")

            lines.extend(["", "numeric canonical sections:"])
            if audit["numeric_canonical_sections"]:
                lines.extend(f"- {section}" for section in audit["numeric_canonical_sections"])
            else:
                lines.append("- -")

            lines.extend(["", "narrative canonical sections:"])
            if audit["narrative_canonical_sections"]:
                lines.extend(f"- {section}" for section in audit["narrative_canonical_sections"])
            else:
                lines.append("- -")

            lines.extend(["", "supporting sections:"])
            if audit["supporting_sections"]:
                lines.extend(f"- {section}" for section in audit["supporting_sections"])
            else:
                lines.append("- -")

            lines.extend(["", "numeric evidence:"])
            if audit["numeric_evidence_quotes"]:
                lines.extend(f"- {quote}" for quote in audit["numeric_evidence_quotes"])
            else:
                lines.append("- -")

            lines.extend(["", "narrative evidence:"])
            if audit["narrative_evidence_quotes"]:
                lines.extend(f"- {quote}" for quote in audit["narrative_evidence_quotes"])
            else:
                lines.append("- -")

            if audit["supporting_evidence_quotes"]:
                lines.extend(["", "supporting evidence:"])
                lines.extend(f"- {quote}" for quote in audit["supporting_evidence_quotes"])

            lines.extend(["", "---", ""])

    return "\n".join(lines)


def build_audit(dataset_path: Path, json_path: Path, csv_path: Path, markdown_path: Path) -> Dict[str, Any]:
    curated_rows = list(_load_json(dataset_path))
    audits = [infer_row_policy(row) for row in curated_rows]

    csv_rows: List[Dict[str, str]] = []
    for audit in audits:
        csv_rows.append(
            {
                "id": audit["id"],
                "company": str(audit["company"]),
                "year": str(audit["year"] or ""),
                "question": str(audit["question"]),
                "doc_scope": str(audit["doc_scope"]),
                "recommended_strategy": str(audit["recommended_strategy"]),
                "needs_numeric": str(audit["needs_numeric"]),
                "needs_narrative": str(audit["needs_narrative"]),
                "numeric_canonical_sections": _join_list(audit["numeric_canonical_sections"]),
                "narrative_canonical_sections": _join_list(audit["narrative_canonical_sections"]),
                "supporting_sections": _join_list(audit["supporting_sections"]),
                "audit_flags": _join_list(audit["audit_flags"]),
            }
        )

    fieldnames = [
        "id",
        "company",
        "year",
        "question",
        "doc_scope",
        "recommended_strategy",
        "needs_numeric",
        "needs_narrative",
        "numeric_canonical_sections",
        "narrative_canonical_sections",
        "supporting_sections",
        "audit_flags",
    ]
    with csv_path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(csv_rows)

    _write_json(json_path, audits)
    markdown_path.write_text(render_markdown(curated_rows, audits), encoding="utf-8")

    strategy_counts = Counter(item["recommended_strategy"] for item in audits)
    flag_counts = Counter(flag for item in audits for flag in item["audit_flags"])
    summary = {
        "row_count": len(audits),
        "strategy_counts": dict(sorted(strategy_counts.items())),
        "flag_counts": dict(sorted(flag_counts.items())),
        "flagged_rows": [item["id"] for item in audits if item["audit_flags"]],
    }
    summary_path = _with_extension(json_path.with_suffix(""), ".summary.json")
    _write_json(summary_path, summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Build evidence-role audit artifacts for the curated dataset.")
    parser.add_argument(
        "--dataset",
        default="benchmarks/datasets/single_doc_eval_full.curated.json",
        help="Path to the curated dataset JSON.",
    )
    parser.add_argument(
        "--output-prefix",
        default="benchmarks/datasets/single_doc_eval_full.evidence_policy_audit",
        help="Output prefix for JSON/CSV/Markdown artifacts.",
    )
    args = parser.parse_args()

    dataset_path = _normalise_path(args.dataset)
    prefix = _normalise_path(args.output_prefix)
    prefix.parent.mkdir(parents=True, exist_ok=True)

    summary = build_audit(
        dataset_path=dataset_path,
        json_path=_with_extension(prefix, ".json"),
        csv_path=_with_extension(prefix, ".csv"),
        markdown_path=_with_extension(prefix, ".md"),
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
