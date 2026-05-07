"""Dump a report's normalized structure outline for manual inspection."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from processing.financial_parser import FinancialParser


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Dump DART report structure with local headings.")
    parser.add_argument("--report-path", required=True, help="Path to the DART XML/HTML report file.")
    parser.add_argument(
        "--json-output",
        help="Optional path to save the extracted outline as JSON.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    report_path = Path(args.report_path)
    parser = FinancialParser()
    outline = parser.extract_structure_outline(str(report_path))
    if not outline:
        print(f"No outline extracted from {report_path}")
        return 1

    print(f"# Structure outline for {report_path.name}")
    for section in outline:
        print(section["path"])
        for local_heading in section["local_headings"]:
            print(f"  - {local_heading}")

    if args.json_output:
        output_path = Path(args.json_output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(outline, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\nSaved JSON outline to {output_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
