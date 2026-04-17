"""
Render a mobile-friendly HTML review page from benchmark review.csv files.
"""

from __future__ import annotations

import argparse
import csv
import html
from pathlib import Path
from typing import Dict, List

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _normalise_path(path_value: str | Path) -> Path:
    path = Path(path_value)
    if not path.is_absolute():
        path = (PROJECT_ROOT / path).resolve()
    return path


def _read_review_rows(csv_path: Path) -> List[Dict[str, str]]:
    with open(csv_path, encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        return [dict(row) for row in reader]


def _split_pipe_value(value: str) -> List[str]:
    return [item.strip() for item in (value or "").split(" | ") if item.strip()]


def _split_evidence(value: str) -> List[str]:
    return [item.strip() for item in (value or "").split("\n\n") if item.strip()]


def _badge_class(metric_value: str, *, kind: str = "default") -> str:
    if kind == "bool":
        return "badge good" if metric_value and metric_value.lower() not in {"", "none", "0", "0.0", "false"} else "badge"
    try:
        numeric = float(metric_value)
    except Exception:
        return "badge"
    if numeric >= 0.8:
        return "badge good"
    if numeric >= 0.5:
        return "badge warn"
    return "badge bad"


def _render_metric_badges(row: Dict[str, str]) -> str:
    metrics = [
        ("Faithfulness", row.get("faithfulness", "")),
        ("Relevancy", row.get("answer_relevancy", "")),
        ("Recall", row.get("context_recall", "")),
        ("Hit@k", row.get("retrieval_hit_at_k", "")),
        ("Section", row.get("section_match_rate", "")),
        ("Citation", row.get("citation_coverage", "")),
    ]
    if row.get("missing_info_compliance"):
        metrics.append(("Missing", row.get("missing_info_compliance", "")))
    parts = []
    for label, value in metrics:
        if not value:
            continue
        safe_label = html.escape(label)
        safe_value = html.escape(value)
        parts.append(f'<span class="{_badge_class(value)}">{safe_label}: {safe_value}</span>')
    return "".join(parts)


def _render_list_items(values: List[str], class_name: str = "pill-list") -> str:
    if not values:
        return '<div class="empty">없음</div>'
    items = "".join(f"<li>{html.escape(value)}</li>" for value in values)
    return f'<ul class="{class_name}">{items}</ul>'


def _render_card(row: Dict[str, str]) -> str:
    experiment_id = html.escape(row.get("experiment_id", ""))
    question_id = html.escape(row.get("question_id", ""))
    category = html.escape(row.get("category", ""))
    question = html.escape(row.get("question", ""))
    answer_key = html.escape(row.get("answer_key", ""))
    actual_answer = html.escape(row.get("actual_answer", ""))
    expected_sections = _split_pipe_value(row.get("expected_sections", ""))
    top_retrieved = _split_pipe_value(row.get("top_retrieved", ""))
    citations = _split_pipe_value(row.get("citations", ""))
    evidence_quotes = _split_evidence(row.get("evidence_quotes", ""))
    missing_info_policy = html.escape(row.get("missing_info_policy", ""))
    error = html.escape(row.get("error", ""))

    return f"""
    <article class="card">
      <div class="card-head">
        <div class="meta-line">
          <span class="meta-chip">{experiment_id}</span>
          <span class="meta-chip muted">{category}</span>
        </div>
        <h2>{question}</h2>
        <p class="question-id">{question_id}</p>
        <div class="badge-row">{_render_metric_badges(row)}</div>
      </div>

      <section class="section">
        <h3>정답 기준</h3>
        <div class="answer-key">{answer_key or '<span class="empty">없음</span>'}</div>
      </section>

      <section class="section">
        <h3>예상 섹션</h3>
        {_render_list_items(expected_sections)}
      </section>

      <section class="section">
        <h3>근거</h3>
        {_render_list_items(evidence_quotes, class_name="evidence-list")}
      </section>

      <section class="section">
        <h3>실제 응답</h3>
        <div class="actual-answer">{actual_answer or '<span class="empty">없음</span>'}</div>
      </section>

      <details class="section details-block">
        <summary>검색 결과와 인용 보기</summary>
        <div class="details-grid">
          <div>
            <h4>Top Retrieved</h4>
            {_render_list_items(top_retrieved)}
          </div>
          <div>
            <h4>Citations</h4>
            {_render_list_items(citations)}
          </div>
        </div>
      </details>

      {f'''
      <details class="section details-block">
        <summary>Missing-info 정책</summary>
        <div class="policy">{missing_info_policy}</div>
      </details>
      ''' if missing_info_policy else ''}

      {f'''
      <details class="section details-block error-block">
        <summary>Error</summary>
        <div class="policy">{error}</div>
      </details>
      ''' if error else ''}
    </article>
    """


def _render_document(title: str, subtitle: str, rows: List[Dict[str, str]]) -> str:
    cards = "\n".join(_render_card(row) for row in rows)
    return f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
  <title>{html.escape(title)}</title>
  <style>
    :root {{
      --bg: #f3efe7;
      --paper: #fffdf8;
      --ink: #1f1c19;
      --muted: #6f665c;
      --line: #ddd2c3;
      --accent: #115e59;
      --accent-soft: #d8f0ec;
      --warn: #a16207;
      --warn-soft: #f9ecc8;
      --bad: #b42318;
      --bad-soft: #fde7e4;
      --good: #166534;
      --good-soft: #dcfce7;
      --shadow: 0 10px 30px rgba(47, 39, 26, 0.08);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background:
        radial-gradient(circle at top left, rgba(17, 94, 89, 0.10), transparent 30%),
        linear-gradient(180deg, #f7f1e7 0%, var(--bg) 100%);
      color: var(--ink);
      font: 16px/1.55 "Segoe UI", "Apple SD Gothic Neo", "Noto Sans KR", sans-serif;
    }}
    .page {{
      width: min(100%, 860px);
      margin: 0 auto;
      padding: 18px 14px 48px;
    }}
    .hero {{
      padding: 18px 2px 10px;
    }}
    .hero h1 {{
      margin: 0 0 6px;
      font-size: 1.7rem;
      line-height: 1.15;
    }}
    .hero p {{
      margin: 0;
      color: var(--muted);
      font-size: 0.98rem;
    }}
    .card {{
      background: color-mix(in srgb, var(--paper) 92%, white);
      border: 1px solid var(--line);
      border-radius: 20px;
      padding: 16px;
      margin: 16px 0;
      box-shadow: var(--shadow);
      overflow: hidden;
    }}
    .card-head h2 {{
      margin: 10px 0 4px;
      font-size: 1.15rem;
      line-height: 1.35;
    }}
    .question-id {{
      margin: 0;
      color: var(--muted);
      font-size: 0.88rem;
    }}
    .meta-line {{
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
    }}
    .meta-chip, .badge {{
      display: inline-flex;
      align-items: center;
      border-radius: 999px;
      padding: 6px 10px;
      font-size: 0.78rem;
      font-weight: 600;
      border: 1px solid var(--line);
      background: #f7f2ea;
    }}
    .meta-chip.muted {{
      color: var(--muted);
    }}
    .badge-row {{
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
      margin-top: 12px;
    }}
    .badge.good {{
      background: var(--good-soft);
      border-color: #a7f3d0;
      color: var(--good);
    }}
    .badge.warn {{
      background: var(--warn-soft);
      border-color: #facc15;
      color: var(--warn);
    }}
    .badge.bad {{
      background: var(--bad-soft);
      border-color: #fca5a5;
      color: var(--bad);
    }}
    .section {{
      margin-top: 16px;
      padding-top: 14px;
      border-top: 1px dashed var(--line);
    }}
    .section h3, .section h4 {{
      margin: 0 0 8px;
      font-size: 0.95rem;
    }}
    .answer-key, .actual-answer, .policy {{
      white-space: pre-wrap;
      word-break: keep-all;
      overflow-wrap: anywhere;
      background: #faf7f1;
      border: 1px solid #e7ded2;
      border-radius: 14px;
      padding: 12px 13px;
    }}
    .pill-list, .evidence-list {{
      list-style: none;
      padding: 0;
      margin: 0;
      display: grid;
      gap: 8px;
    }}
    .pill-list li, .evidence-list li {{
      background: #faf7f1;
      border: 1px solid #e7ded2;
      border-radius: 14px;
      padding: 11px 12px;
      word-break: keep-all;
      overflow-wrap: anywhere;
    }}
    .evidence-list li {{
      border-left: 4px solid var(--accent);
      background: #f5fbfa;
    }}
    details {{
      border-radius: 14px;
    }}
    summary {{
      cursor: pointer;
      font-weight: 700;
      list-style: none;
    }}
    summary::-webkit-details-marker {{ display: none; }}
    .details-grid {{
      display: grid;
      gap: 14px;
      margin-top: 12px;
    }}
    .empty {{
      color: var(--muted);
    }}
    .error-block .policy {{
      border-color: #fca5a5;
      background: var(--bad-soft);
    }}
    @media (min-width: 700px) {{
      .page {{
        padding-inline: 18px;
      }}
      .details-grid {{
        grid-template-columns: 1fr 1fr;
      }}
    }}
  </style>
</head>
<body>
  <main class="page">
    <header class="hero">
      <h1>{html.escape(title)}</h1>
      <p>{html.escape(subtitle)}</p>
    </header>
    {cards}
  </main>
</body>
</html>
"""


def render_review_mobile(csv_path: Path, output_path: Path | None = None) -> Path:
    rows = _read_review_rows(csv_path)
    if output_path is None:
        output_path = csv_path.with_name("review.mobile.html")
    title = f"{csv_path.parent.name} Mobile Review"
    subtitle = "질문 · 정답 기준 · 근거 · 실제 응답을 모바일 카드 레이아웃으로 정리한 보기"
    output_path.write_text(_render_document(title, subtitle, rows), encoding="utf-8")
    return output_path


def render_index(index_path: Path, review_paths: List[Path]) -> Path:
    links = []
    for path in review_paths:
        relative = path.name if path.parent == index_path.parent else str(path.relative_to(index_path.parent)).replace("\\", "/")
        links.append(
            f'<li><a href="{html.escape(relative)}">{html.escape(path.parent.name)}</a></li>'
        )
    document = f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
  <title>Mobile Review Index</title>
  <style>
    body {{
      margin: 0;
      background: linear-gradient(180deg, #f6efe3 0%, #efe7da 100%);
      color: #1f1c19;
      font: 16px/1.55 "Segoe UI", "Apple SD Gothic Neo", "Noto Sans KR", sans-serif;
    }}
    main {{
      width: min(100%, 720px);
      margin: 0 auto;
      padding: 24px 16px 40px;
    }}
    h1 {{ margin: 0 0 8px; font-size: 1.8rem; }}
    p {{ margin: 0 0 18px; color: #6f665c; }}
    ul {{ list-style: none; padding: 0; margin: 0; display: grid; gap: 12px; }}
    a {{
      display: block;
      text-decoration: none;
      color: inherit;
      background: rgba(255,255,255,0.82);
      border: 1px solid #ddd2c3;
      border-radius: 16px;
      padding: 16px;
      box-shadow: 0 10px 30px rgba(47,39,26,0.08);
      font-weight: 700;
    }}
  </style>
</head>
<body>
  <main>
    <h1>Mobile Review Index</h1>
    <p>기업별 benchmark review를 모바일 카드 레이아웃으로 볼 수 있는 링크 모음입니다.</p>
    <ul>{''.join(links)}</ul>
  </main>
</body>
</html>
"""
    index_path.write_text(document, encoding="utf-8")
    return index_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Render mobile-friendly benchmark review HTML.")
    parser.add_argument("csv_paths", nargs="+", help="Path(s) to review.csv files.")
    parser.add_argument("--index", action="store_true", help="Also write a simple index HTML next to the review files.")
    args = parser.parse_args()

    rendered_paths: List[Path] = []
    for raw_path in args.csv_paths:
        csv_path = _normalise_path(raw_path)
        output_path = render_review_mobile(csv_path)
        rendered_paths.append(output_path)
        print(output_path)

    if args.index and rendered_paths:
        root = rendered_paths[0].parents[1] if len(rendered_paths[0].parents) >= 2 else rendered_paths[0].parent
        index_path = root / "review.mobile.index.html"
        render_index(index_path, rendered_paths)
        print(index_path)


if __name__ == "__main__":
    main()
