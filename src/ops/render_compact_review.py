"""
Render a compact benchmark review from results.json.

This artifact is intentionally smaller than raw results.json and focuses on:
- experiment
- question
- answer key / actual answer
- retrieved docs
- runtime evidence
- sentence checks
"""

from __future__ import annotations

import argparse
import html
import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _normalise_path(path_value: str | Path) -> Path:
    path = Path(path_value)
    if not path.is_absolute():
        path = (PROJECT_ROOT / path).resolve()
    return path


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _resolve_eval_dataset_path(result_payload: Dict[str, Any], result_path: Path) -> Path | None:
    config_path_value = result_payload.get("config_path")
    if not config_path_value:
        return None

    config_path = _normalise_path(config_path_value)
    if not config_path.exists():
        return None

    config = _load_json(config_path)
    company_results = result_payload.get("results", [])
    if not company_results:
        return None
    first_metadata = dict(company_results[0].get("metadata", {}) or {})
    target_company = str(first_metadata.get("company", "")).strip().lower()
    target_year = str(first_metadata.get("year", "")).strip()

    for company_run in config.get("company_runs", []):
        defaults = dict(company_run.get("defaults", {}) or {})
        metadata = dict(defaults.get("metadata", {}) or {})
        company = str(metadata.get("company", "")).strip().lower()
        year = str(metadata.get("year", "")).strip()
        if company == target_company and year == target_year:
            dataset_path = defaults.get("eval_dataset_path")
            if dataset_path:
                return _normalise_path(dataset_path)
    return None


def _build_golden_map(dataset_path: Path | None) -> Dict[str, Dict[str, Any]]:
    if not dataset_path or not dataset_path.exists():
        return {}
    rows = _load_json(dataset_path)
    golden_map: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        query_id = str(row.get("query_id") or row.get("id") or "").strip()
        if query_id:
            golden_map[query_id] = dict(row)
    return golden_map


def _string_list(items: List[Any], limit: int | None = None) -> List[str]:
    values = [str(item).strip() for item in (items or []) if str(item).strip()]
    return values[:limit] if limit else values


def _format_retrieved_rows(retrieved_metadata: List[Dict[str, Any]], limit: int = 8) -> List[str]:
    lines: List[str] = []
    for row in (retrieved_metadata or [])[:limit]:
        section = row.get("section_path") or row.get("section") or "?"
        block_type = row.get("block_type") or "?"
        relation = row.get("graph_relation") or "seed"
        lines.append(f"{section} [{block_type} / {relation}]")
    return lines


def _format_retrieved_previews(retrieved_previews: List[Dict[str, Any]], limit: int = 8) -> List[str]:
    lines: List[str] = []
    for row in (retrieved_previews or [])[:limit]:
        section = row.get("section_path") or row.get("section") or "?"
        block_type = row.get("block_type") or "?"
        relation = row.get("graph_relation") or "seed"
        preview = row.get("preview") or ""
        lines.append(f"{section} [{block_type} / {relation}] {preview}".strip())
    return lines


def _format_runtime_evidence(runtime_evidence: List[Dict[str, Any]], limit: int = 6) -> List[str]:
    lines: List[str] = []
    for row in (runtime_evidence or [])[:limit]:
        evidence_id = row.get("evidence_id") or "?"
        anchor = row.get("source_anchor") or "?"
        claim = row.get("claim") or ""
        quote = row.get("quote_span") or ""
        lines.append(f"{evidence_id} | {anchor} | {claim}" + (f" | quote: {quote}" if quote else ""))
    return lines


def _format_sentence_checks(sentence_checks: List[Dict[str, Any]], limit: int = 8) -> List[str]:
    lines: List[str] = []
    for row in (sentence_checks or [])[:limit]:
        sentence = str(row.get("sentence") or "").strip()
        verdict = str(row.get("verdict") or "").strip()
        reason = str(row.get("reason") or "").strip()
        claim_ids = _string_list(row.get("supporting_claim_ids") or [])
        suffix = f" | claims={', '.join(claim_ids)}" if claim_ids else ""
        lines.append(f"{verdict}: {sentence}" + (f" | {reason}" if reason else "") + suffix)
    return lines


def _merge_question_rows(result: Dict[str, Any]) -> List[Dict[str, Any]]:
    screening_rows = {row.get("id"): dict(row) for row in result.get("screening_eval", {}).get("per_question", [])}
    full_rows = {row.get("id"): dict(row) for row in result.get("full_eval", {}).get("per_question", [])}

    merged: List[Dict[str, Any]] = []
    for question_id in sorted(set(screening_rows) | set(full_rows)):
        screening = screening_rows.get(question_id, {})
        full = full_rows.get(question_id, {})
        row = dict(screening)
        row.update(
            {
                "actual_answer": full.get("answer") or screening.get("answer") or screening.get("answer_preview") or "",
                "answer_key": full.get("answer_key") or screening.get("answer_key") or "",
                "citations": full.get("citations") or screening.get("citations") or [],
                "retrieved_previews": full.get("retrieved_previews") or screening.get("retrieved_previews") or [],
                "runtime_evidence": full.get("runtime_evidence") or [],
                "sentence_checks": full.get("sentence_checks") or [],
                "selected_claim_ids": full.get("selected_claim_ids") or [],
                "dropped_claim_ids": full.get("dropped_claim_ids") or [],
                "unsupported_sentences": full.get("unsupported_sentences") or [],
            }
        )
        merged.append(row)
    return merged


def _build_compact_rows(result_payload: Dict[str, Any], golden_map: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for result in result_payload.get("results", []):
        experiment_id = str(result.get("id") or "")
        for row in _merge_question_rows(result):
            query_id = str(row.get("id") or "")
            golden = golden_map.get(query_id, {})
            rows.append(
                {
                    "experiment_id": experiment_id,
                    "query_id": query_id,
                    "category": row.get("category") or golden.get("category") or "",
                    "question": row.get("question") or golden.get("question") or "",
                    "answer_key": row.get("answer_key") or golden.get("ground_truth_answer") or "",
                    "actual_answer": row.get("actual_answer") or "",
                    "expected_context_ids": _string_list(golden.get("ground_truth_context_ids") or []),
                    "expected_sections": _string_list(row.get("expected_sections") or golden.get("expected_sections") or []),
                    "retrieved_docs": _format_retrieved_previews(row.get("retrieved_previews") or [])
                    or _format_retrieved_rows(row.get("retrieved_metadata") or []),
                    "runtime_evidence": _format_runtime_evidence(row.get("runtime_evidence") or []),
                    "sentence_checks": _format_sentence_checks(row.get("sentence_checks") or []),
                    "selected_claim_ids": _string_list(row.get("selected_claim_ids") or []),
                    "dropped_claim_ids": _string_list(row.get("dropped_claim_ids") or []),
                    "unsupported_sentences": _string_list(row.get("unsupported_sentences") or []),
                }
            )
    return rows


def _render_markdown(rows: List[Dict[str, Any]], title: str) -> str:
    lines = [f"# {title}", ""]
    current_experiment = None
    for row in rows:
        experiment_id = row["experiment_id"]
        if experiment_id != current_experiment:
            current_experiment = experiment_id
            lines.extend([f"## {experiment_id}", ""])
        lines.extend(
            [
                f"### {row['query_id']} | {row['category']}",
                "",
                f"질문: {row['question']}",
                f"예시 답변: {row['answer_key'] or '-'}",
                f"실제 답변: {row['actual_answer'] or '-'}",
                f"기대 Context IDs: {' | '.join(row['expected_context_ids']) or '-'}",
                f"기대 섹션: {' | '.join(row['expected_sections']) or '-'}",
                f"Selected Claims: {' | '.join(row['selected_claim_ids']) or '-'}",
                f"Dropped Claims: {' | '.join(row['dropped_claim_ids']) or '-'}",
                "",
                "Retrieved Chunks:",
            ]
        )
        retrieved = row["retrieved_docs"] or ["-"]
        lines.extend([f"- {item}" for item in retrieved])
        lines.extend(["", "Runtime Evidence:"])
        runtime_evidence = row["runtime_evidence"] or ["-"]
        lines.extend([f"- {item}" for item in runtime_evidence])
        lines.extend(["", "Sentence Checks:"])
        sentence_checks = row["sentence_checks"] or ["-"]
        lines.extend([f"- {item}" for item in sentence_checks])
        lines.extend(["", "Unsupported Sentences:"])
        unsupported = row["unsupported_sentences"] or ["-"]
        lines.extend([f"- {item}" for item in unsupported])
        lines.extend(["", "---", ""])
    return "\n".join(lines)


def _render_html(rows: List[Dict[str, Any]], title: str) -> str:
    blocks: List[str] = []
    current_experiment = None
    for row in rows:
        experiment_id = html.escape(row["experiment_id"])
        if experiment_id != current_experiment:
            current_experiment = experiment_id
            blocks.append(f'<h2 class="experiment">{experiment_id}</h2>')

        def render_list(items: List[str]) -> str:
            if not items:
                return '<div class="empty">-</div>'
            return "<ul>" + "".join(f"<li>{html.escape(item)}</li>" for item in items) + "</ul>"

        blocks.append(
            f"""
            <article class="card">
              <div class="meta">{html.escape(row['query_id'])} | {html.escape(row['category'])}</div>
              <h3>{html.escape(row['question'])}</h3>
              <div class="field"><strong>예시 답변</strong><p>{html.escape(row['answer_key'] or '-')}</p></div>
              <div class="field"><strong>실제 답변</strong><p>{html.escape(row['actual_answer'] or '-')}</p></div>
              <div class="grid">
                <section><h4>기대 Context IDs</h4>{render_list(row['expected_context_ids'])}</section>
                <section><h4>기대 섹션</h4>{render_list(row['expected_sections'])}</section>
              </div>
              <div class="grid">
                <section><h4>Selected Claims</h4>{render_list(row['selected_claim_ids'])}</section>
                <section><h4>Dropped Claims</h4>{render_list(row['dropped_claim_ids'])}</section>
              </div>
              <section><h4>Retrieved Chunks</h4>{render_list(row['retrieved_docs'])}</section>
              <section><h4>Runtime Evidence</h4>{render_list(row['runtime_evidence'])}</section>
              <section><h4>Sentence Checks</h4>{render_list(row['sentence_checks'])}</section>
              <section><h4>Unsupported Sentences</h4>{render_list(row['unsupported_sentences'])}</section>
            </article>
            """
        )

    return f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(title)}</title>
  <style>
    body {{
      margin: 0;
      background: #f5f1e8;
      color: #201b16;
      font: 15px/1.55 "Segoe UI", "Noto Sans KR", sans-serif;
    }}
    .page {{
      max-width: 980px;
      margin: 0 auto;
      padding: 16px;
    }}
    h1 {{ margin: 0 0 16px; font-size: 1.6rem; }}
    .experiment {{
      margin: 24px 0 8px;
      font-size: 1.2rem;
    }}
    .card {{
      background: #fffdf8;
      border: 1px solid #ddd2c3;
      border-radius: 18px;
      padding: 16px;
      margin: 12px 0;
      box-shadow: 0 8px 24px rgba(42, 31, 17, 0.06);
    }}
    .meta {{
      color: #786e63;
      font-size: 0.85rem;
      margin-bottom: 8px;
    }}
    h3 {{ margin: 0 0 12px; font-size: 1.08rem; }}
    h4 {{ margin: 0 0 6px; font-size: 0.95rem; }}
    .field p {{
      margin: 6px 0 12px;
      white-space: pre-wrap;
    }}
    .grid {{
      display: grid;
      gap: 12px;
      grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
    }}
    section {{ margin: 10px 0; }}
    ul {{
      margin: 6px 0 0;
      padding-left: 18px;
    }}
    li {{ margin: 4px 0; }}
    .empty {{ color: #786e63; }}
  </style>
</head>
<body>
  <main class="page">
    <h1>{html.escape(title)}</h1>
    {''.join(blocks)}
  </main>
</body>
</html>"""


def render_compact_review(result_path: Path, output_dir: Path | None = None) -> Tuple[Path, Path]:
    result_payload = _load_json(result_path)
    output_dir = output_dir or result_path.parent
    dataset_path = _resolve_eval_dataset_path(result_payload, result_path)
    golden_map = _build_golden_map(dataset_path)
    rows = _build_compact_rows(result_payload, golden_map)
    title = f"Compact Review - {result_path.parent.name}"

    md_path = output_dir / "compact_review.md"
    html_path = output_dir / "compact_review.html"
    md_path.write_text(_render_markdown(rows, title), encoding="utf-8")
    html_path.write_text(_render_html(rows, title), encoding="utf-8")
    return md_path, html_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Render compact review artifacts from benchmark results.json")
    parser.add_argument("result_path", help="Path to company-level benchmark results.json")
    parser.add_argument("--output-dir", default="", help="Optional output directory")
    args = parser.parse_args()

    result_path = _normalise_path(args.result_path)
    output_dir = _normalise_path(args.output_dir) if args.output_dir else result_path.parent
    md_path, html_path = render_compact_review(result_path, output_dir)
    print(md_path)
    print(html_path)


if __name__ == "__main__":
    main()
