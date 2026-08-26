import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
VALIDATION_WORKFLOW_PATH = PROJECT_ROOT / ".github" / "workflows" / "validation.yml"
PYTHON_VERSION_PATH = PROJECT_ROOT / ".python-version"


class ValidationWorkflowContractTests(unittest.TestCase):
    def test_reference_python_version_matches_every_validation_command(self) -> None:
        python_version = PYTHON_VERSION_PATH.read_text(encoding="utf-8").strip()
        workflow = VALIDATION_WORKFLOW_PATH.read_text(encoding="utf-8")

        self.assertRegex(python_version, r"^3\.\d+$")
        self.assertIn(f"Reviewer contracts (Python {python_version})", workflow)
        self.assertIn(f"Full unittest suite (Python {python_version})", workflow)
        self.assertEqual(workflow.count(f"uv run --python {python_version}"), 4)

    def test_whitespace_gate_checks_the_event_commit_range(self) -> None:
        workflow = VALIDATION_WORKFLOW_PATH.read_text(encoding="utf-8")

        required_surfaces = (
            "fetch-depth: 0",
            "diff_base_sha:",
            "required: true",
            "${{ github.event.pull_request.base.sha }}",
            "${{ github.event.pull_request.head.sha }}",
            "${{ github.event.before }}",
            "${{ github.event.after }}",
            "${{ inputs.diff_base_sha }}",
            "set -euo pipefail",
            'empty_tree="$(git mktree </dev/null)"',
            'base="$(git merge-base "$PR_BASE_SHA" "$PR_HEAD_SHA")"',
            'git diff --check "$base" "$head" --',
        )
        for surface in required_surfaces:
            with self.subTest(surface=surface):
                self.assertIn(surface, workflow)

        self.assertNotIn("run: git diff --check", workflow)


if __name__ == "__main__":
    unittest.main()
