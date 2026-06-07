import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from langchain_core.documents import Document

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
for path in (PROJECT_ROOT, SRC_ROOT):
    path_text = str(path)
    if path_text not in sys.path:
        sys.path.insert(0, path_text)

from src.ops import mas_direct_worker_probe


class FakeVectorStore:
    def __init__(self, docs=None) -> None:
        self.docs = docs or []
        self.calls = []

    def search(self, query, *, k, where_filter=None):
        self.calls.append({"query": query, "k": k, "where_filter": where_filter})
        return list(self.docs)


class FakeAnalystCore:
    def __init__(self, result=None) -> None:
        self.result = result or {}
        self.calls = []

    def run(self, query, *, report_scope=None):
        self.calls.append({"query": query, "report_scope": dict(report_scope or {})})
        return dict(self.result)


class FakeResearcherCore:
    def __init__(self, result=None) -> None:
        self.result = result or {}
        self.calls = []

    def run(self, query, *, report_scope=None):
        self.calls.append({"query": query, "report_scope": dict(report_scope or {})})
        return dict(self.result)


def _planner_node(_state):
    return {
        "tasks": {
            "task_1": {
                "task_id": "task_1",
                "assignee": "Analyst",
                "kind": "calculation",
                "label": "numeric task",
                "instruction": "calculate the numeric value",
                "status": "pending",
                "context_keys": ["numeric_values"],
                "retry_count": 0,
            },
            "task_2": {
                "task_id": "task_2",
                "assignee": "Researcher",
                "kind": "retrieval",
                "label": "narrative task",
                "instruction": "summarize the narrative evidence",
                "status": "pending",
                "context_keys": ["narrative_evidence"],
                "retry_count": 0,
            },
        }
    }


class MasDirectWorkerProbeTests(unittest.TestCase):
    def test_run_probe_classifies_direct_worker_material_failures(self) -> None:
        vector_store = FakeVectorStore(
            docs=[
                (
                    Document(
                        page_content="narrative evidence",
                        metadata={
                            "chunk_uid": "chunk-1",
                            "block_type": "paragraph",
                            "company": "ACME",
                            "year": 2023,
                        },
                    ),
                    0.9,
                )
            ]
        )
        analyst = FakeAnalystCore(
            result={
                "answer": "",
                "retrieved_docs": [
                    (
                        Document(page_content="numeric evidence", metadata={"chunk_uid": "num-1"}),
                        0.8,
                    )
                ],
                "structured_result": {"status": "insufficient_operands"},
                "resolved_calculation_trace": {
                    "calculation_plan": {"mode": "ratio"},
                    "calculation_operands": [],
                    "calculation_result": {"status": "insufficient_operands"},
                },
            }
        )
        researcher = FakeResearcherCore(
            result={
                "answer": "",
                "citations": [],
                "summary_points": [],
                "retrieved_docs": [],
            }
        )

        payload = mas_direct_worker_probe.run_probe(
            store_dir=Path("store"),
            collection_name="collection",
            queries=["question"],
            report_scope={"company": "ACME", "year": "2023", "report_type": "annual"},
            vector_store_manager=vector_store,
            planner_node=_planner_node,
            analyst_core=analyst,
            researcher_core=researcher,
        )

        self.assertEqual(payload["summary"]["planned_task_assignee_counts"], {"Analyst": 1, "Researcher": 1})
        self.assertEqual(payload["store_inventory"]["bm25_doc_count"], 0)
        self.assertIsNone(payload["store_inventory"]["chroma_count"])
        self.assertEqual(payload["summary"]["analyst_material_status_counts"], {"retrieved_without_operands": 1})
        self.assertEqual(payload["summary"]["researcher_material_status_counts"], {"no_result_docs": 1})
        self.assertEqual(payload["summary"]["analyst_success_count"], 0)
        self.assertEqual(payload["summary"]["researcher_success_count"], 0)
        case = payload["cases"][0]
        self.assertEqual(case["analyst"]["items"][0]["retrieved_doc_count"], 1)
        self.assertEqual(case["analyst"]["items"][0]["operand_count"], 0)
        self.assertEqual(case["researcher"]["items"][0]["retrieval_probe"]["raw_retrieved_doc_count"], 1)
        self.assertEqual(case["researcher"]["items"][0]["retrieval_probe"]["selected_doc_count"], 1)

    def test_run_probe_classifies_successful_worker_material(self) -> None:
        doc = Document(
            page_content="material",
            metadata={"chunk_uid": "chunk-1", "block_type": "paragraph"},
        )
        vector_store = FakeVectorStore(docs=[(doc, 0.9)])
        analyst = FakeAnalystCore(
            result={
                "answer": "42%",
                "retrieved_docs": [(doc, 0.9)],
                "structured_result": {"status": "ok", "rendered_value": "42%"},
                "resolved_calculation_trace": {
                    "calculation_plan": {"mode": "ratio"},
                    "calculation_operands": [{"label": "value", "raw_value": "42"}],
                    "calculation_result": {"status": "ok", "rendered_value": "42%"},
                },
            }
        )
        researcher = FakeResearcherCore(
            result={
                "answer": "grounded answer",
                "citations": ["citation"],
                "summary_points": ["point"],
                "retrieved_docs": [(doc, 0.9)],
            }
        )

        payload = mas_direct_worker_probe.run_probe(
            store_dir=Path("store"),
            collection_name="collection",
            queries=["question"],
            vector_store_manager=vector_store,
            planner_node=_planner_node,
            analyst_core=analyst,
            researcher_core=researcher,
        )

        self.assertEqual(payload["summary"]["analyst_material_status_counts"], {"ok": 1})
        self.assertEqual(payload["summary"]["researcher_material_status_counts"], {"ok": 1})
        self.assertEqual(payload["summary"]["analyst_success_count"], 1)
        self.assertEqual(payload["summary"]["researcher_success_count"], 1)

    def test_main_creates_output_parent_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "nested" / "probe.json"
            with (
                patch.object(sys, "argv", ["mas_direct_worker_probe", "--output", str(output_path)]),
                patch.object(mas_direct_worker_probe, "run_probe", return_value={"ok": True}),
            ):
                mas_direct_worker_probe.main()

            self.assertTrue(output_path.exists())
            self.assertEqual(json.loads(output_path.read_text(encoding="utf-8")), {"ok": True})


if __name__ == "__main__":
    unittest.main()
