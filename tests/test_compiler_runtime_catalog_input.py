"""Compiler-only admission preserves a frozen, context-normalized catalog."""

from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, patch
from tests.request_unit_fixture_support import bind_fixture_requests

from src.agent.financial_runtime_normalization import _normalise_operand_value
from src.ops.replay_reviewed_compiler_selection import (
    _canonical_bytes, _compiler_case_catalog, _sha256_bytes, _write_new_json,
    evaluate_reviewed_compiler_selection, rehearse_reviewed_compiler_selection,
)
from src.ops.replay_reviewed_runtime_corpus import _materialize_catalog


FIXTURE = Path(__file__).parent / "fixtures" / "reviewed_runtime_replay_corpus_v3.json"


def runtime_case(catalog):
    return {"catalog_input": {"kind": "runtime_projection_v1",
            "sha256": _sha256_bytes(_canonical_bytes(catalog))}, "candidate_catalog": catalog}


class CompilerRuntimeCatalogInputTests(unittest.TestCase):
    def test_context_normalized_values_survive_without_reinterpreting_bare_surface(self):
        value, unit = _normalise_operand_value("120", "백만원")
        catalog = [{"candidate_id": "source-cell", "kind": "numeric", "raw_value": "120",
            "raw_unit": "", "source_unit_hint": "백만원", "normalized_value": value,
            "normalized_unit": unit, "source_span": [3, 6]}]
        case = runtime_case(catalog)
        actual, checks = _compiler_case_catalog(case)
        self.assertEqual(actual, catalog)
        self.assertEqual(checks, {"runtime_catalog_fingerprint_matches": True})
        self.assertNotIn("normalization_matches_review", checks)
        actual[0]["source_span"][0] = 99
        self.assertEqual(case["candidate_catalog"][0]["source_span"], [3, 6])
        renormalized, _ = _materialize_catalog(catalog)
        self.assertNotEqual(renormalized[0]["normalized_value"], value)

    def test_catalog_content_mutations_fail_before_compiler_invocation(self):
        base = runtime_case([{"candidate_id": "source-cell", "kind": "numeric",
            "raw_value": "120", "normalized_value": 120.0, "normalized_unit": "COUNT",
            "source_text": "120 items", "source_span": [0, 3]}])
        for field, value in (("normalized_value", 121), ("normalized_unit", "KRW"),
                             ("source_text", "other"), ("source_span", [1, 3])):
            with self.subTest(field=field), TemporaryDirectory() as directory:
                case = deepcopy(base)
                case["candidate_catalog"][0][field] = value
                corpus = bind_fixture_requests(json.loads(FIXTURE.read_text(encoding="utf-8")))
                corpus["cases"] = [{**corpus["cases"][0], **case}]
                path = Path(directory) / "corpus.json"
                _write_new_json(path, corpus)
                llm = Mock()
                with self.assertRaisesRegex(ValueError, "runtime catalog fingerprint mismatch"):
                    evaluate_reviewed_compiler_selection(path, llm, run_mode="rehearsal")
                llm.with_structured_output.assert_not_called()

    def test_missing_fingerprint_or_unknown_mode_does_not_fall_back_to_fixture(self):
        for spec in ({"kind": "runtime_projection_v1"}, {"kind": "unknown"}):
            with self.subTest(spec=spec), self.assertRaises(ValueError):
                _compiler_case_catalog({"catalog_input": spec, "candidate_catalog": []})

    def test_existing_fixture_and_runtime_projection_have_identical_prompts_and_outputs(self):
        corpus = bind_fixture_requests(json.loads(FIXTURE.read_text(encoding="utf-8")))
        fixture_corpus = deepcopy(corpus)
        for case in corpus["cases"]:
            catalog, _ = _materialize_catalog(case["candidate_catalog"])
            case.update(runtime_case(catalog))
        with TemporaryDirectory() as directory, patch(
            "socket.socket.connect", side_effect=AssertionError("network forbidden"),
        ):
            path = Path(directory) / "corpus.json"
            fixture_path = Path(directory) / "fixture.json"
            # Keep identical JSON key order for both modes; compact runtime prompts
            # deliberately retain ordered input mappings rather than sort them.
            _write_new_json(fixture_path, fixture_corpus)
            _write_new_json(path, corpus)
            fixture_result = rehearse_reviewed_compiler_selection(fixture_path)
            runtime_result = rehearse_reviewed_compiler_selection(path)
        self.assertEqual(runtime_result["status"], "passed")
        self.assertEqual(fixture_result["summary"], runtime_result["summary"])
        for before, after in zip(fixture_result["cases"], runtime_result["cases"]):
            self.assertEqual(before["execution"], after["execution"])
            self.assertEqual(before["validation"], after["validation"])
            self.assertEqual(before["compiled_program"], after["compiled_program"])
            self.assertTrue(after["checks"]["runtime_catalog_fingerprint_matches"])
            self.assertTrue(before["checks"]["normalization_matches_review"])


if __name__ == "__main__":
    unittest.main()
