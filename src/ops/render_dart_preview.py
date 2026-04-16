"""
Render a browser-friendly HTML preview from a DART XML filing.
"""

from __future__ import annotations

import argparse
import html
import sys
from pathlib import Path
from typing import Any, List

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from processing.financial_parser import FinancialParser, _classify_section, _normalize


def _get_first_text(root: Any, tag: str) -> str:
    elem = root.find(f".//{tag}")
    if elem is None:
        return ""
    return _normalize("".join(elem.itertext()))


def _slugify(value: str) -> str:
    lowered = "".join(ch.lower() if ch.isalnum() else "-" for ch in value)
    return "-".join(part for part in lowered.split("-") if part)


def _render_table(table_text: str) -> str:
    rows = []
    for raw_row in table_text.splitlines():
        if not raw_row.strip():
            continue
        cells = [html.escape(cell.strip()) for cell in raw_row.split(" | ")]
        if cells:
            rows.append(cells)

    if not rows:
        return ""

    body_rows = []
    first_row = rows[0]
    if len(rows) > 1:
        head = "".join(f"<th>{cell}</th>" for cell in first_row)
        body_rows.append(f"<thead><tr>{head}</tr></thead>")
        rows = rows[1:]

    tbody = []
    for row in rows:
        cells = "".join(f"<td>{cell}</td>" for cell in row)
        tbody.append(f"<tr>{cells}</tr>")
    body_rows.append(f"<tbody>{''.join(tbody)}</tbody>")
    return f"<div class=\"table-wrap\"><table>{''.join(body_rows)}</table></div>"


def _render_section(section: dict[str, Any], index: int) -> str:
    section_id = f"section-{index}-{_slugify(section['title'])}"
    label = _classify_section(section["title"])
    blocks_html: List[str] = []

    for block in section["blocks"]:
        block_type = block["type"]
        text = block["text"]
        if block_type == "paragraph":
            blocks_html.append(f"<p>{html.escape(text)}</p>")
        elif block_type == "table":
            rendered_table = _render_table(text)
            if rendered_table:
                blocks_html.append(rendered_table)
            else:
                blocks_html.append(f"<pre>{html.escape(text)}</pre>")

    return f"""
    <section id="{section_id}" class="section">
      <header class="section-header">
        <div class="section-kicker">{html.escape(label)}</div>
        <h2>{html.escape(section["title"])}</h2>
        <div class="section-path">{html.escape(section["path"])}</div>
      </header>
      <div class="section-body">
        {''.join(blocks_html)}
      </div>
    </section>
    """


def render_preview(input_path: Path, output_path: Path) -> Path:
    parser = FinancialParser()
    root = parser._parse_xml(str(input_path))
    if root is None:
        raise RuntimeError(f"Failed to parse {input_path}")

    sections = parser._extract_sections(root)
    company = _get_first_text(root, "COMPANY-NAME") or input_path.parent.name
    report_name = _get_first_text(root, "DOCUMENT-NAME") or "DART 문서"
    fiscal_year = _get_first_text(root, "FORMULA-VERSION")

    toc_items = []
    section_html = []
    for idx, section in enumerate(sections, start=1):
        section_id = f"section-{idx}-{_slugify(section['title'])}"
        toc_items.append(
            f"<li><a href=\"#{section_id}\">{idx}. {html.escape(section['title'])}</a></li>"
        )
        section_html.append(_render_section(section, idx))

    document = f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(company)} - {html.escape(report_name)} Preview</title>
  <style>
    :root {{
      --bg: #f5f1e8;
      --panel: #fffdf8;
      --ink: #1d1c1a;
      --muted: #736b5d;
      --line: #d8cdb9;
      --accent: #8b5e34;
      --accent-soft: #efe2d0;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: "Malgun Gothic", "Apple SD Gothic Neo", sans-serif;
      color: var(--ink);
      background:
        radial-gradient(circle at top left, #fff5e7, transparent 35%),
        linear-gradient(180deg, #f7f2ea 0%, #f1eadf 100%);
      line-height: 1.65;
    }}
    .page {{
      max-width: 1280px;
      margin: 0 auto;
      padding: 32px 24px 80px;
      display: grid;
      grid-template-columns: 320px minmax(0, 1fr);
      gap: 24px;
    }}
    .sidebar, .content {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 18px;
      box-shadow: 0 18px 48px rgba(92, 72, 39, 0.08);
    }}
    .sidebar {{
      position: sticky;
      top: 16px;
      align-self: start;
      padding: 24px 22px;
      max-height: calc(100vh - 32px);
      overflow: auto;
    }}
    .content {{ padding: 28px 30px; }}
    .eyebrow {{
      color: var(--accent);
      font-weight: 700;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      font-size: 12px;
      margin-bottom: 12px;
    }}
    h1 {{
      margin: 0 0 10px;
      font-size: 32px;
      line-height: 1.2;
    }}
    .meta {{
      color: var(--muted);
      margin-bottom: 18px;
      font-size: 14px;
    }}
    .help {{
      padding: 14px 16px;
      background: var(--accent-soft);
      border-radius: 12px;
      color: #5e4325;
      font-size: 14px;
      margin-bottom: 20px;
    }}
    .toc {{
      list-style: none;
      padding: 0;
      margin: 0;
      display: grid;
      gap: 8px;
    }}
    .toc a {{
      color: inherit;
      text-decoration: none;
      display: block;
      padding: 10px 12px;
      border-radius: 10px;
    }}
    .toc a:hover {{
      background: #f6efe4;
    }}
    .section {{
      padding-bottom: 28px;
      margin-bottom: 28px;
      border-bottom: 1px solid var(--line);
    }}
    .section:last-child {{
      border-bottom: 0;
      margin-bottom: 0;
      padding-bottom: 0;
    }}
    .section-kicker {{
      display: inline-block;
      font-size: 12px;
      font-weight: 700;
      color: var(--accent);
      background: var(--accent-soft);
      border-radius: 999px;
      padding: 4px 10px;
      margin-bottom: 10px;
    }}
    .section h2 {{
      margin: 0 0 8px;
      font-size: 24px;
      line-height: 1.3;
    }}
    .section-path {{
      color: var(--muted);
      font-size: 14px;
      margin-bottom: 16px;
    }}
    .section-body p {{
      margin: 0 0 14px;
      white-space: pre-wrap;
    }}
    .table-wrap {{
      overflow: auto;
      border: 1px solid var(--line);
      border-radius: 12px;
      margin: 16px 0 20px;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 14px;
      background: white;
    }}
    th, td {{
      border-bottom: 1px solid #ece2d2;
      border-right: 1px solid #ece2d2;
      padding: 10px 12px;
      text-align: left;
      vertical-align: top;
      white-space: nowrap;
    }}
    th {{
      position: sticky;
      top: 0;
      background: #f6efe5;
      z-index: 1;
    }}
    tr:last-child td {{ border-bottom: 0; }}
    td:last-child, th:last-child {{ border-right: 0; }}
    pre {{
      background: #faf6ef;
      border: 1px solid var(--line);
      border-radius: 12px;
      padding: 16px;
      overflow: auto;
      white-space: pre-wrap;
    }}
    @media (max-width: 980px) {{
      .page {{
        grid-template-columns: 1fr;
      }}
      .sidebar {{
        position: static;
        max-height: none;
      }}
      .content {{
        padding: 22px 18px;
      }}
    }}
  </style>
</head>
<body>
  <div class="page">
    <aside class="sidebar">
      <div class="eyebrow">DART Preview</div>
      <h1>{html.escape(company)}</h1>
      <div class="meta">{html.escape(report_name)}{f" · Formula {html.escape(fiscal_year)}" if fiscal_year else ""}</div>
      <div class="help">
        이 파일은 DART 원본 XML을 브라우저에서 읽기 쉽게 풀어쓴 preview입니다.
        원본 XML은 그대로 유지되고, 이 HTML은 읽기 전용 렌더링 결과입니다.
      </div>
      <ol class="toc">
        {''.join(toc_items)}
      </ol>
    </aside>
    <main class="content">
      {''.join(section_html)}
    </main>
  </div>
</body>
</html>
"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(document, encoding="utf-8")
    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Render a browser-friendly HTML preview from a DART XML filing.")
    parser.add_argument("input", help="Path to the original DART XML/HTML file")
    parser.add_argument(
        "--output",
        help="Output path for the preview HTML. Defaults to <input>.preview.html",
    )
    args = parser.parse_args()

    input_path = Path(args.input).resolve()
    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    output_path = Path(args.output).resolve() if args.output else input_path.with_suffix(".preview.html")
    rendered_path = render_preview(input_path, output_path)
    print(rendered_path)


if __name__ == "__main__":
    main()
