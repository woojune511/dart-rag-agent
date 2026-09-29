"""Guard the public guide/runtime boundary when merging separately published docs."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
GUIDES = (
    "README.md", "docs/README.md", "demo/README.md",
    "docs/overview/project_overview.md", "docs/overview/project_summary.md",
    "docs/overview/architecture_walkthrough.md", "docs/overview/design_rationale.md",
    "docs/overview/experiment_report.md", "docs/overview/demo_walkthrough.md",
    "docs/overview/technical_qa.md", "docs/overview/documentation_claim_boundaries.md",
)


class PublicGuideMergeContractTests(unittest.TestCase):
    def test_public_guide_local_markdown_links_resolve(self):
        for relative in GUIDES:
            path = ROOT / relative
            text = path.read_text(encoding="utf-8")
            self.assertNotRegex(text, r"(?m)^(<<<<<<< |=======\s*$|>>>>>>> )")
            for target in re.findall(r"\]\(([^)]+)\)", text):
                if "://" in target or target.startswith("#"):
                    continue
                target = target.split("#", 1)[0]
                if not target.endswith(".md"):
                    continue
                with self.subTest(source=relative, target=target):
                    self.assertTrue((path.parent / target).is_file())

    def test_current_product_and_historical_guarantees_stay_separate(self):
        for relative in ("README.md", "docs/overview/project_summary.md",
                         "docs/overview/documentation_claim_boundaries.md"):
            self.assertIn("SimpleRagAgent", (ROOT / relative).read_text(encoding="utf-8"))
        for name in ("architecture_walkthrough", "design_rationale", "experiment_report",
                     "demo_walkthrough", "technical_qa"):
            preamble = (ROOT / f"docs/overview/{name}.md").read_text(encoding="utf-8").splitlines()[:12]
            self.assertIn("Historical compiled-workflow", "\n".join(preamble))

    def test_pages_deployment_remains_separate_from_pr_build(self):
        text = (ROOT / ".github/workflows/demo-pages.yml").read_text(encoding="utf-8")
        self.assertIn("github.event_name != 'pull_request'", text)
        self.assertIn("github.ref == 'refs/heads/main'", text)
        self.assertIn("python -I -S demo/verify.py", text)
        self.assertIn("cp demo/index.html demo/provenance.json _site/", text)


if __name__ == "__main__":
    unittest.main()
