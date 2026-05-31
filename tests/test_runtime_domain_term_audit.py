import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from src.ops.audit_runtime_domain_terms import (
    collect_runtime_domain_term_occurrences,
    collect_runtime_domain_terms,
    compare_runtime_domain_terms,
    load_runtime_domain_term_baseline,
    summarise_runtime_domain_terms,
    summarise_runtime_domain_terms_by_symbol,
)


class RuntimeDomainTermAuditTests(unittest.TestCase):
    def test_runtime_domain_terms_match_reviewed_baseline(self) -> None:
        current = collect_runtime_domain_terms()
        baseline = load_runtime_domain_term_baseline()

        diff = compare_runtime_domain_terms(current, baseline)

        self.assertEqual(
            diff,
            {"unexpected": [], "missing": [], "count_mismatches": []},
            "Runtime code gained or lost reviewed domain-language literals. "
            "Move new domain vocabulary to ontology/policy/config, or update "
            "tests/fixtures/runtime_domain_terms_baseline.json with review rationale.",
        )

    def test_comparison_reports_new_and_changed_literals(self) -> None:
        baseline = [{"path": "src/agent/example.py", "text": "기준", "count": 1}]
        current = [
            {"path": "src/agent/example.py", "text": "기준", "count": 2},
            {"path": "src/agent/example.py", "text": "신규", "count": 1},
        ]

        diff = compare_runtime_domain_terms(current, baseline)

        self.assertEqual(len(diff["unexpected"]), 1)
        self.assertEqual(diff["unexpected"][0]["text"], "신규")
        self.assertEqual(len(diff["missing"]), 0)
        self.assertEqual(
            diff["count_mismatches"],
            [
                {
                    "path": "src/agent/example.py",
                    "text": "기준",
                    "current_count": 2,
                    "baseline_count": 1,
                }
            ],
        )

    def test_collector_ignores_main_guard_demo_literals(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            project_root = Path(tmp_dir)
            source_dir = project_root / "src" / "agent"
            source_dir.mkdir(parents=True)
            (source_dir / "example.py").write_text(
                '\n'.join(
                    [
                        'VISIBLE = "런타임"',
                        'if __name__ == "__main__":',
                        '    print("데모")',
                    ]
                ),
                encoding="utf-8",
            )

            records = collect_runtime_domain_terms(project_root, ("src/agent",))

        self.assertEqual([item["text"] for item in records], ["런타임"])

    def test_collector_classifies_pydantic_field_descriptions_as_schema(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            project_root = Path(tmp_dir)
            source_dir = project_root / "src" / "agent"
            source_dir.mkdir(parents=True)
            (source_dir / "models.py").write_text(
                "\n".join(
                    [
                        "from pydantic import Field",
                        'value = Field(description="스키마 설명")',
                        'RUNTIME_VALUE = "런타임"',
                    ]
                ),
                encoding="utf-8",
            )

            records = collect_runtime_domain_terms(project_root, ("src/agent",))

        categories = {item["text"]: item["category"] for item in records}
        self.assertEqual(categories["스키마 설명"], "schema_description")
        self.assertEqual(categories["런타임"], "runtime_literal")

    def test_summary_counts_records_by_category_and_path(self) -> None:
        records = [
            {"path": "src/agent/a.py", "category": "runtime_literal", "count": 2},
            {"path": "src/agent/a.py", "category": "regex_or_pattern", "count": 1},
            {"path": "src/routing/b.py", "category": "runtime_literal", "count": 1},
        ]

        summary = summarise_runtime_domain_terms(records, top_n=1)

        self.assertEqual(summary["record_count"], 3)
        self.assertEqual(summary["literal_count"], 4)
        self.assertEqual(summary["by_category"]["runtime_literal"], 2)
        self.assertEqual(summary["top_paths"], [{"path": "src/agent/a.py", "records": 2}])

    def test_occurrence_summary_groups_literals_by_symbol(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            project_root = Path(tmp_dir)
            source_dir = project_root / "src" / "agent"
            source_dir.mkdir(parents=True)
            (source_dir / "example.py").write_text(
                "\n".join(
                    [
                        'MODULE_VALUE = "\\uc0c1\\uc704"',
                        "class Example:",
                        "    def select(self):",
                        '        return "\\uc120\\ud0dd"',
                        "    async def resolve(self):",
                        '        return "\\uc870\\ub9bd"',
                    ]
                ),
                encoding="utf-8",
            )

            occurrences = collect_runtime_domain_term_occurrences(project_root, ("src/agent",))

        symbols = {(item["symbol"], item["text"]) for item in occurrences}
        self.assertIn(("<module>", "상위"), symbols)
        self.assertIn(("Example.select", "선택"), symbols)
        self.assertIn(("Example.resolve", "조립"), symbols)

        summary = summarise_runtime_domain_terms_by_symbol(occurrences, top_n=2)

        self.assertEqual(summary["occurrence_count"], 3)
        self.assertEqual(len(summary["top_symbols"]), 2)


if __name__ == "__main__":
    unittest.main()
