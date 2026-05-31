import unittest

from src.ops.audit_runtime_domain_terms import (
    collect_runtime_domain_terms,
    compare_runtime_domain_terms,
    load_runtime_domain_term_baseline,
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


if __name__ == "__main__":
    unittest.main()
