import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
for path in (PROJECT_ROOT, SRC_ROOT):
    path_text = str(path)
    if path_text not in sys.path:
        sys.path.insert(0, path_text)

from src.ops.portfolio_demo import build_demo, render_text  # noqa: E402

FIXTURE_ROOT = PROJECT_ROOT / "tests" / "fixtures" / "portfolio_demo"
DEMO_PAYLOAD_PATH = FIXTURE_ROOT / "demo_payload.json"
EVIDENCE_MANIFEST_PATH = FIXTURE_ROOT / "evidence_manifest.json"


def _normalized_lf_sha256(path: Path) -> str:
    payload = path.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return hashlib.sha256(payload).hexdigest()


class PortfolioDemoTests(unittest.TestCase):
    def _load_payload(self) -> dict:
        return json.loads(DEMO_PAYLOAD_PATH.read_text(encoding="utf-8"))

    def _write_bound_fixture(
        self,
        *,
        temp_dir: str,
        payload: dict,
    ) -> tuple[Path, Path]:
        payload_path = Path(temp_dir) / "demo_payload.json"
        payload_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        manifest = json.loads(EVIDENCE_MANIFEST_PATH.read_text(encoding="utf-8"))
        manifest["fixture_binding"]["path"] = payload_path.name
        manifest["fixture_binding"]["sha256"] = _normalized_lf_sha256(payload_path)
        manifest_path = Path(temp_dir) / "evidence_manifest.json"
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return payload_path, manifest_path

    def test_build_demo_summarizes_runtime_contract_surfaces(self) -> None:
        demo = build_demo()

        self.assertEqual(
            demo["readiness"]["status"],
            "fixture_contract_ready",
        )
        self.assertEqual(demo["readiness"]["scope"], "fixture_contract")
        self.assertTrue(all(demo["readiness"]["checks"].values()))
        self.assertEqual(demo["fixture_evidence"]["status"], "verified")
        self.assertEqual(
            demo["fixture_evidence"]["evidence_kind"],
            "curated_contract_fixture",
        )
        self.assertEqual(
            demo["fixture_evidence"]["upstream_artifact_availability"],
            "not_provided",
        )
        self.assertFalse(demo["fixture_evidence"]["live_runtime_replayed"])
        self.assertFalse(
            demo["fixture_evidence"]["raw_runtime_bundle_checked_in"]
        )
        self.assertTrue(demo["fixture_evidence"]["fixture_sha256_matches"])
        self.assertEqual(
            demo["fixture_evidence"]["fixture_hash_normalization"],
            "line_endings_lf",
        )
        self.assertEqual(
            demo["semantic_plan"]["tasks"][0]["operation_family"],
            "ratio",
        )
        self.assertEqual(demo["retrieval_debug_trace"]["selected_count"], 1)
        self.assertEqual(demo["structured_result"]["rendered_value"], "37.47%")
        self.assertEqual(
            demo["resolved_calculation_trace"]["calculation_result"]["status"],
            "ok",
        )
        self.assertEqual(demo["task_artifact_integrity"]["integrity_status"], "ok")
        self.assertEqual(demo["critic_acceptance"]["status"], "accepted")
        self.assertIsNone(demo["cache_reviewer_handoff"])

    def test_build_demo_can_include_optional_cache_review(self) -> None:
        demo = build_demo(include_cache_review=True)

        self.assertEqual(demo["cache_reviewer_handoff"]["status"], "ready")
        self.assertFalse(demo["cache_reviewer_handoff"]["retrieval_bypass_enabled"])
        self.assertFalse(demo["cache_reviewer_handoff"]["write_enabled"])
        self.assertFalse(demo["cache_reviewer_handoff"]["serving_enabled"])

    def test_demo_critic_acceptance_uses_runtime_contract_not_score(self) -> None:
        payload = self._load_payload()
        report = payload["answer_package"]["critic_reports"][0]
        report["passed"] = True
        report["verdict"] = "passed"
        report["deterministic_score"] = 1.0
        report["acceptance_reason"] = ""

        with tempfile.TemporaryDirectory() as temp_dir:
            payload_path, manifest_path = self._write_bound_fixture(
                temp_dir=temp_dir,
                payload=payload,
            )

            demo = build_demo(
                demo_payload_path=payload_path,
                evidence_manifest_path=manifest_path,
                include_cache_review=False,
            )

        self.assertEqual(demo["critic_acceptance"]["status"], "blocked")
        self.assertIn(
            "missing_acceptance_reason",
            demo["critic_acceptance"]["runtime_acceptance_reasons"],
        )
        self.assertFalse(
            demo["critic_acceptance"]["deterministic_score_used_for_acceptance"]
        )
        self.assertEqual(demo["readiness"]["status"], "needs_review")

    def test_fixture_binding_is_stable_across_checkout_line_endings(self) -> None:
        original = DEMO_PAYLOAD_PATH.read_bytes()
        normalized = original.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
        expected_hash = hashlib.sha256(normalized).hexdigest()

        for label, payload_bytes in (
            ("lf", normalized),
            ("crlf", normalized.replace(b"\n", b"\r\n")),
        ):
            with (
                self.subTest(line_endings=label),
                tempfile.TemporaryDirectory() as temp_dir,
            ):
                payload_path = Path(temp_dir) / "demo_payload.json"
                payload_path.write_bytes(payload_bytes)
                manifest = json.loads(
                    EVIDENCE_MANIFEST_PATH.read_text(encoding="utf-8")
                )
                manifest["fixture_binding"]["path"] = payload_path.name
                manifest["fixture_binding"]["sha256"] = expected_hash
                manifest_path = Path(temp_dir) / "evidence_manifest.json"
                manifest_path.write_text(
                    json.dumps(manifest, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )

                demo = build_demo(
                    demo_payload_path=payload_path,
                    evidence_manifest_path=manifest_path,
                )

                self.assertEqual(demo["fixture_evidence"]["status"], "verified")
                self.assertTrue(
                    demo["fixture_evidence"]["fixture_sha256_matches"]
                )
                self.assertEqual(
                    demo["fixture_evidence"]["fixture_sha256_actual"],
                    expected_hash,
                )

    def test_demo_rejects_manifest_without_hash_normalization(self) -> None:
        payload = self._load_payload()

        with tempfile.TemporaryDirectory() as temp_dir:
            payload_path, manifest_path = self._write_bound_fixture(
                temp_dir=temp_dir,
                payload=payload,
            )
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["fixture_binding"].pop("normalization")
            manifest_path.write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            demo = build_demo(
                demo_payload_path=payload_path,
                evidence_manifest_path=manifest_path,
            )

        self.assertTrue(demo["fixture_evidence"]["fixture_sha256_matches"])
        self.assertEqual(demo["fixture_evidence"]["status"], "invalid")
        self.assertEqual(demo["readiness"]["status"], "needs_review")

    def test_demo_rejects_ratio_result_inconsistent_with_operands(self) -> None:
        payload = self._load_payload()
        operands = payload["answer_package"]["resolved_calculation_trace"][
            "calculation_operands"
        ]
        operands[0]["raw_value"] = "5,000"

        with tempfile.TemporaryDirectory() as temp_dir:
            payload_path, manifest_path = self._write_bound_fixture(
                temp_dir=temp_dir,
                payload=payload,
            )
            demo = build_demo(
                demo_payload_path=payload_path,
                evidence_manifest_path=manifest_path,
            )

        checks = demo["readiness"]["checks"]
        self.assertFalse(checks["ratio_calculation_consistent"])
        self.assertTrue(checks["answer_structured_trace_display_agree"])
        self.assertEqual(demo["readiness"]["status"], "needs_review")

    def test_demo_rejects_answer_structured_trace_display_disagreement(self) -> None:
        payload = self._load_payload()
        payload["answer_package"]["structured_result"]["rendered_value"] = "99.99%"

        with tempfile.TemporaryDirectory() as temp_dir:
            payload_path, manifest_path = self._write_bound_fixture(
                temp_dir=temp_dir,
                payload=payload,
            )
            demo = build_demo(
                demo_payload_path=payload_path,
                evidence_manifest_path=manifest_path,
            )

        self.assertFalse(
            demo["readiness"]["checks"][
                "answer_structured_trace_display_agree"
            ]
        )
        self.assertEqual(demo["readiness"]["status"], "needs_review")

    def test_demo_rejects_semantic_operand_label_trace_disagreement(self) -> None:
        payload = self._load_payload()
        required_operands = payload["answer_package"]["semantic_plan"]["tasks"][0][
            "required_operands"
        ]
        required_operands[0]["label"] = "different numerator label"

        with tempfile.TemporaryDirectory() as temp_dir:
            payload_path, manifest_path = self._write_bound_fixture(
                temp_dir=temp_dir,
                payload=payload,
            )
            demo = build_demo(
                demo_payload_path=payload_path,
                evidence_manifest_path=manifest_path,
            )

        self.assertFalse(
            demo["readiness"]["checks"]["semantic_operand_labels_match_trace"]
        )
        self.assertEqual(demo["readiness"]["status"], "needs_review")

    def test_demo_rejects_source_evidence_citation_disagreement(self) -> None:
        payload = self._load_payload()
        payload["answer_package"]["citations"] = ["[unrelated source]"]

        with tempfile.TemporaryDirectory() as temp_dir:
            payload_path, manifest_path = self._write_bound_fixture(
                temp_dir=temp_dir,
                payload=payload,
            )
            demo = build_demo(
                demo_payload_path=payload_path,
                evidence_manifest_path=manifest_path,
            )

        self.assertFalse(
            demo["readiness"]["checks"]["source_evidence_citation_coherent"]
        )
        self.assertEqual(demo["readiness"]["status"], "needs_review")

    def test_demo_rejects_missing_critic_target_reference(self) -> None:
        payload = self._load_payload()
        report = payload["answer_package"]["critic_reports"][0]
        report["target_artifact_ids"] = ["artifact:missing"]

        with tempfile.TemporaryDirectory() as temp_dir:
            payload_path, manifest_path = self._write_bound_fixture(
                temp_dir=temp_dir,
                payload=payload,
            )
            demo = build_demo(
                demo_payload_path=payload_path,
                evidence_manifest_path=manifest_path,
            )

        self.assertTrue(demo["readiness"]["checks"]["critic_accepted"])
        self.assertFalse(demo["readiness"]["checks"]["critic_targets_exist"])
        target_details = demo["readiness"]["details"]["critic_target_references"]
        self.assertEqual(
            target_details["missing_target_artifact_ids"],
            ["artifact:missing"],
        )
        self.assertEqual(demo["readiness"]["status"], "needs_review")

    def test_demo_rejects_payload_not_bound_by_manifest(self) -> None:
        payload = self._load_payload()
        payload["question"] = "tampered fixture"

        with tempfile.TemporaryDirectory() as temp_dir:
            payload_path = Path(temp_dir) / "demo_payload.json"
            payload_path.write_text(json.dumps(payload), encoding="utf-8")
            demo = build_demo(demo_payload_path=payload_path)

        self.assertEqual(demo["fixture_evidence"]["status"], "invalid")
        self.assertFalse(demo["fixture_evidence"]["fixture_sha256_matches"])
        self.assertFalse(
            demo["readiness"]["checks"]["fixture_evidence_manifest_verified"]
        )
        self.assertEqual(demo["readiness"]["status"], "needs_review")

    def test_demo_rejects_manifest_without_claim_boundary(self) -> None:
        payload = self._load_payload()

        with tempfile.TemporaryDirectory() as temp_dir:
            payload_path, manifest_path = self._write_bound_fixture(
                temp_dir=temp_dir,
                payload=payload,
            )
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["claim_boundary"]["does_not_support"] = []
            manifest_path.write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            demo = build_demo(
                demo_payload_path=payload_path,
                evidence_manifest_path=manifest_path,
            )

        self.assertTrue(demo["fixture_evidence"]["fixture_sha256_matches"])
        self.assertEqual(demo["fixture_evidence"]["status"], "invalid")
        self.assertFalse(
            demo["readiness"]["checks"]["fixture_evidence_manifest_verified"]
        )
        self.assertEqual(demo["readiness"]["status"], "needs_review")

    def test_demo_rejects_malformed_manifest_shape_without_crashing(self) -> None:
        payload = self._load_payload()

        with tempfile.TemporaryDirectory() as temp_dir:
            payload_path, manifest_path = self._write_bound_fixture(
                temp_dir=temp_dir,
                payload=payload,
            )
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["fixture_binding"] = 1
            manifest_path.write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            demo = build_demo(
                demo_payload_path=payload_path,
                evidence_manifest_path=manifest_path,
            )

        self.assertEqual(demo["fixture_evidence"]["status"], "invalid")
        self.assertTrue(demo["fixture_evidence"]["error"])
        self.assertEqual(demo["readiness"]["status"], "needs_review")

    def test_render_text_includes_portfolio_sections(self) -> None:
        text = render_text(build_demo(include_cache_review=False))

        self.assertIn("# Portfolio Runtime Demo", text)
        self.assertIn("Fixture Contract Readiness: fixture_contract_ready", text)
        self.assertIn("Fixture Evidence:", text)
        self.assertIn("evidence_kind: curated_contract_fixture", text)
        self.assertIn("upstream_artifact_availability: not_provided", text)
        self.assertIn("Semantic Plan:", text)
        self.assertIn("planner: concept_llm_planner", text)
        self.assertIn("Retrieval Trace:", text)
        self.assertIn("mode: hybrid", text)
        self.assertIn("Calculation Trace:", text)
        self.assertIn("Task/Artifact Integrity:", text)
        self.assertIn("Critic Acceptance:", text)
        self.assertIn("Cross-Surface Contract Checks:", text)
        self.assertNotIn("Cache Reviewer Handoff:", text)

    def test_render_text_can_include_optional_cache_review(self) -> None:
        text = render_text(build_demo(include_cache_review=True))

        self.assertIn("Cache Reviewer Handoff:", text)
        self.assertIn("retrieval_bypass_enabled:", text)
        self.assertIn("write_enabled:", text)

    def test_cli_writes_json_output(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "portfolio_demo.json"

            demo_result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "src.ops.portfolio_demo",
                    "--format",
                    "json",
                    "--output",
                    str(output),
                ],
                cwd=PROJECT_ROOT,
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )

            self.assertEqual(demo_result.returncode, 0, demo_result.stderr)
            self.assertIn('"readiness"', demo_result.stdout)
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(
                payload["readiness"]["status"],
                "fixture_contract_ready",
            )
            self.assertEqual(payload["fixture_evidence"]["status"], "verified")
            self.assertEqual(payload["semantic_plan"]["tasks"][0]["operation_family"], "ratio")
            self.assertEqual(payload["retrieval_debug_trace"]["selected_count"], 1)
            self.assertIsNone(payload["cache_reviewer_handoff"])


if __name__ == "__main__":
    unittest.main()
