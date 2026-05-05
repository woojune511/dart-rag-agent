"""Build compact dataset review artifacts for direct filing comparison."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
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


def _join_list(values: Iterable[str]) -> str:
    cleaned = [str(value).strip() for value in values if str(value).strip()]
    return " || ".join(cleaned)


def _source_reports(row: Dict[str, Any]) -> List[Dict[str, Any]]:
    reports = list(row.get("source_reports") or [])
    if not reports and row.get("source_report"):
        reports = [dict(row["source_report"])]
    return reports


def _source_report_label(report: Dict[str, Any]) -> str:
    year = report.get("year", "")
    report_type = report.get("report_type", "사업보고서")
    rcept_no = report.get("rcept_no", "")
    return f"{year} {report_type} ({rcept_no})".strip()


def _dart_url(report: Dict[str, Any]) -> str:
    rcept_no = str(report.get("rcept_no") or "").strip()
    if not rcept_no:
        return ""
    return f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={rcept_no}"


def _markdown_file_link(label: str, file_path: str) -> str:
    absolute = _normalise_path(file_path)
    return f"[{label}](<{absolute.as_posix()}>)"


def build_compact_rows(
    curated_rows: List[Dict[str, Any]],
    review_rows: List[Dict[str, Any]],
    rewrite_ids: set[str],
) -> List[Dict[str, str]]:
    review_map = {str(row.get("id") or ""): dict(row) for row in review_rows}
    compact_rows: List[Dict[str, str]] = []

    for row in curated_rows:
        row_id = str(row.get("id") or "")
        review = review_map.get(row_id, {})
        reports = _source_reports(row)
        evidence = list(row.get("evidence") or [])

        compact_rows.append(
            {
                "id": row_id,
                "company": str(row.get("company") or ""),
                "year": str(row.get("year") or ""),
                "question": str(row.get("question") or row.get("query") or ""),
                "answer_key": str(row.get("answer_key") or ""),
                "expected_refusal": str(bool(row.get("expected_refusal", False))),
                "review_decision": str(review.get("review_decision") or ""),
                "rewrite_applied": str(row_id in rewrite_ids),
                "source_report_paths": _join_list(report.get("file_path", "") for report in reports),
                "source_report_urls": _join_list(_dart_url(report) for report in reports),
                "expected_sections": _join_list(row.get("expected_sections") or []),
                "evidence_quotes": _join_list(item.get("quote", "") for item in evidence),
            }
        )

    return compact_rows


def render_review_markdown(
    curated_rows: List[Dict[str, Any]],
    review_rows: List[Dict[str, Any]],
    rewrite_ids: set[str],
) -> str:
    review_map = {str(row.get("id") or ""): dict(row) for row in review_rows}
    company_counts = Counter(str(row.get("company") or "") for row in curated_rows)
    lines: List[str] = ["# Dataset Review Packet", ""]

    lines.extend(["## Company Index", ""])
    for company in sorted(company_counts):
        anchor = company.replace(" ", "-")
        lines.append(f"- [{company} ({company_counts[company]})](#{anchor})")
    lines.append("")

    grouped_rows: Dict[str, List[Dict[str, Any]]] = {}
    for row in curated_rows:
        grouped_rows.setdefault(str(row.get("company") or ""), []).append(row)

    for company in sorted(grouped_rows):
        lines.extend([f"## {company}", ""])
        for row in grouped_rows[company]:
            row_id = str(row.get("id") or "")
            review = review_map.get(row_id, {})
            reports = _source_reports(row)
            evidence = list(row.get("evidence") or [])
            lines.extend(
                [
                    f"### {row_id}",
                    "",
                    f"- 연도: {row.get('year', '')}",
                    f"- 질문: {row.get('question') or row.get('query') or ''}",
                    f"- 답변: {row.get('answer_key') or ''}",
                    f"- expected_refusal: {bool(row.get('expected_refusal', False))}",
                    f"- review_decision: {review.get('review_decision') or ''}",
                    f"- rewrite_applied: {row_id in rewrite_ids}",
                    "",
                    "원문 보고서:",
                ]
            )

            if reports:
                for report in reports:
                    file_path = str(report.get("file_path") or "").strip()
                    label = _source_report_label(report)
                    file_link = _markdown_file_link(label, file_path) if file_path else label
                    dart_url = _dart_url(report)
                    dart_suffix = f" | [DART]({dart_url})" if dart_url else ""
                    lines.append(f"- {file_link}{dart_suffix}")
            else:
                lines.append("- -")

            lines.extend(["", "확인할 섹션:"])
            expected_sections = list(row.get("expected_sections") or [])
            if expected_sections:
                lines.extend(f"- {section}" for section in expected_sections)
            else:
                lines.append("- -")

            lines.extend(["", "근거:"])
            if evidence:
                for item in evidence:
                    section_path = str(item.get("section_path") or "").strip()
                    quote = str(item.get("quote") or "").strip()
                    why = str(item.get("why_it_supports_answer") or "").strip()
                    lines.append(f"- [{section_path}] {quote}")
                    if why:
                        lines.append(f"  설명: {why}")
            else:
                lines.append("- -")

            notes = str(row.get("notes") or "").strip()
            if notes:
                lines.extend(["", f"메모: {notes}"])

            lines.extend(["", "---", ""])

    return "\n".join(lines)


def render_inspect_guide(
    dataset_path: Path,
    review_seed_path: Path,
    rewrite_log_path: Path,
    compact_csv_path: Path,
    review_markdown_path: Path,
    curated_rows: List[Dict[str, Any]],
    rewrite_ids: set[str],
) -> str:
    answer_type_counts = Counter(str(row.get("answer_type") or "") for row in curated_rows)
    refusal_count = sum(1 for row in curated_rows if bool(row.get("expected_refusal", False)))

    lines = [
        "# Curated Dataset Inspection Guide",
        "",
        "## Start Here",
        f"- 문서 대조용 review packet: `{review_markdown_path}`",
        f"- 필터링용 compact CSV: `{compact_csv_path}`",
        "",
        "## Reference Files",
        f"- Final nested dataset: `{dataset_path}`",
        f"- Review seed with full review metadata: `{review_seed_path}`",
        f"- Rewrite log: `{rewrite_log_path}`",
        "",
        "## Snapshot",
        f"- Total rows: {len(curated_rows)}",
        f"- Verified rows: {sum(1 for row in curated_rows if row.get('verification_status') == 'verified')}",
        f"- Expected refusal rows: {refusal_count}",
        f"- Rewritten question rows: {len(rewrite_ids)}",
        "",
        "## Answer Type Counts",
    ]

    for answer_type, count in sorted(answer_type_counts.items()):
        lines.append(f"- {answer_type}: {count}")

    lines.extend(
        [
            "",
            "## Suggested Review Flow",
            "1. Review packet markdown에서 질문/답/근거/원문 링크를 함께 본다.",
            "2. 원문 HTML을 열어 섹션과 인용문이 실제로 맞는지 대조한다.",
            "3. 필요한 경우 compact CSV로 필터링해 회사별/거절문항별로 스캔한다.",
            "",
            "## Compact CSV Columns",
            "- `question`, `answer_key`: 최종 확정 질문/답변",
            "- `source_report_paths`, `source_report_urls`: 원문 보고서 위치",
            "- `expected_sections`, `evidence_quotes`: 문서 대조용 최소 근거",
            "- `review_decision`, `rewrite_applied`: 검수 이력",
        ]
    )

    return "\n".join(lines) + "\n"


def build_review_pack(
    dataset_path: Path,
    review_seed_path: Path,
    rewrite_log_path: Path,
    compact_csv_path: Path,
    inspect_guide_path: Path,
    review_markdown_path: Path,
) -> Dict[str, Any]:
    curated_rows = list(_load_json(dataset_path))
    review_rows = list(_load_json(review_seed_path))
    rewrite_log = list(_load_json(rewrite_log_path))
    rewrite_ids = {str(row.get("id") or "") for row in rewrite_log}

    compact_rows = build_compact_rows(curated_rows, review_rows, rewrite_ids)
    fieldnames = [
        "id",
        "company",
        "year",
        "question",
        "answer_key",
        "expected_refusal",
        "review_decision",
        "rewrite_applied",
        "source_report_paths",
        "source_report_urls",
        "expected_sections",
        "evidence_quotes",
    ]

    with compact_csv_path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(compact_rows)

    review_markdown = render_review_markdown(curated_rows, review_rows, rewrite_ids)
    review_markdown_path.write_text(review_markdown, encoding="utf-8")

    inspect_guide = render_inspect_guide(
        dataset_path=dataset_path,
        review_seed_path=review_seed_path,
        rewrite_log_path=rewrite_log_path,
        compact_csv_path=compact_csv_path,
        review_markdown_path=review_markdown_path,
        curated_rows=curated_rows,
        rewrite_ids=rewrite_ids,
    )
    inspect_guide_path.write_text(inspect_guide, encoding="utf-8")

    return {
        "row_count": len(curated_rows),
        "compact_csv_path": str(compact_csv_path),
        "review_markdown_path": str(review_markdown_path),
        "inspect_guide_path": str(inspect_guide_path),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build compact review artifacts for a curated dataset.")
    parser.add_argument(
        "--dataset",
        default="benchmarks/datasets/single_doc_eval_full.curated.json",
        help="Path to the curated dataset JSON.",
    )
    parser.add_argument(
        "--review-seed",
        default="benchmarks/datasets/single_doc_eval_full.grounded_draft.review/review_seed.json",
        help="Path to the review seed JSON.",
    )
    parser.add_argument(
        "--rewrite-log",
        default="benchmarks/datasets/single_doc_eval_full.rewrite_log.json",
        help="Path to the rewrite log JSON.",
    )
    parser.add_argument(
        "--compact-csv",
        default="benchmarks/datasets/single_doc_eval_full.curated.inspect.csv",
        help="Path to write the compact inspection CSV.",
    )
    parser.add_argument(
        "--inspect-guide",
        default="benchmarks/datasets/single_doc_eval_full.curated.inspect.md",
        help="Path to write the inspection guide markdown.",
    )
    parser.add_argument(
        "--review-markdown",
        default="benchmarks/datasets/single_doc_eval_full.curated.review.md",
        help="Path to write the full review markdown.",
    )
    args = parser.parse_args()

    summary = build_review_pack(
        dataset_path=_normalise_path(args.dataset),
        review_seed_path=_normalise_path(args.review_seed),
        rewrite_log_path=_normalise_path(args.rewrite_log),
        compact_csv_path=_normalise_path(args.compact_csv),
        inspect_guide_path=_normalise_path(args.inspect_guide),
        review_markdown_path=_normalise_path(args.review_markdown),
    )
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
