import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
for path in (PROJECT_ROOT, SRC_ROOT):
    path_text = str(path)
    if path_text not in sys.path:
        sys.path.insert(0, path_text)

from src.ops.benchmark_runner import (
    _collect_report_inventory,
    _build_cache_signature,
    _build_store_signature,
    _cache_meta_is_completed,
    _ensure_benchmark_report_path,
    _inventory_eval_examples,
    _normalise_path,
    _run_ingest,
    _store_signature_matches,
)
from src.ops.evaluator import EvalExample
from src.ingestion.dart_fetcher import ReportMetadata
from src.storage.vector_store import VectorStoreManager


class _FakeVectorStore:
    def __init__(self, metadatas=None):
        self.metadatas = list(metadatas or [])
        self.add_calls = []

    def get(self, where=None, limit=None):
        rows = list(self.metadatas)
        if where and "rcept_no" in where:
            rows = [row for row in rows if str(row.get("rcept_no")) == str(where["rcept_no"])]
        if limit is not None:
            rows = rows[:limit]
        return {"ids": [str(i) for i in range(len(rows))], "metadatas": rows}

    def add_texts(self, texts, metadatas):
        self.add_calls.append({"texts": list(texts), "metadatas": list(metadatas)})
        self.metadatas.extend(dict(metadata or {}) for metadata in metadatas)

    def similarity_search_with_score(self, query, k=4, filter=None):
        raise RuntimeError("RESOURCE_EXHAUSTED: synthetic test failure")


class BenchmarkPathTests(unittest.TestCase):
    def test_normalise_path_remaps_stale_data_reports_workspace(self) -> None:
        stale_path = Path("C:/Users/geonj/Desktop/research agent/data/reports/NAVER/2023_사업보고서_20240318000844.html")

        resolved = _normalise_path(stale_path)

        self.assertEqual(
            resolved,
            (PROJECT_ROOT / "data" / "reports" / "NAVER" / "2023_사업보고서_20240318000844.html").resolve(),
        )


class _FakeIngestVectorManager:
    def __init__(self):
        self.parent_calls = []
        self.document_calls = []

    def add_parents(self, parents):
        self.parent_calls.append(dict(parents))

    def add_documents(self, texts, metadatas, resume=False, batch_size=64, on_progress=None):
        self.document_calls.append(
            {
                "texts": list(texts),
                "metadatas": list(metadatas),
                "resume": resume,
                "batch_size": batch_size,
            }
        )
        return {
            "added_chunks": len(texts),
            "skipped_chunks": 0,
            "batch_count": 1,
        }


class ResumableIngestTests(unittest.TestCase):
    def _make_manager(self, existing_metadatas=None):
        manager = VectorStoreManager.__new__(VectorStoreManager)
        manager.vector_store = _FakeVectorStore(existing_metadatas)
        manager._update_structure_graph = Mock()
        manager._init_bm25 = Mock()
        manager.allow_query_embedding_fallback = True
        manager.force_bm25_only = False
        manager.skip_vector_add = False
        manager.bm25 = None
        manager.bm25_docs = []
        manager.bm25_metadatas = []
        return manager

    def test_add_documents_skips_existing_chunk_uids_when_resume_enabled(self) -> None:
        manager = self._make_manager(
            [{"chunk_uid": "r1::chunk:1", "rcept_no": "r1"}]
        )

        result = manager.add_documents(
            ["old", "new"],
            [
                {"chunk_uid": "r1::chunk:1", "rcept_no": "r1"},
                {"chunk_uid": "r1::chunk:2", "rcept_no": "r1"},
            ],
            resume=True,
            batch_size=8,
        )

        self.assertEqual(result["added_chunks"], 1)
        self.assertEqual(result["skipped_chunks"], 1)
        self.assertEqual(result["batch_count"], 1)
        self.assertEqual(len(manager.vector_store.add_calls), 1)
        self.assertEqual(manager.vector_store.add_calls[0]["texts"], ["new"])
        self.assertEqual(
            [metadata["chunk_uid"] for metadata in manager.vector_store.add_calls[0]["metadatas"]],
            ["r1::chunk:2"],
        )
        manager._update_structure_graph.assert_called_once()
        manager._init_bm25.assert_called_once()

    def test_add_documents_batches_pending_chunks_and_skips_input_duplicates(self) -> None:
        manager = self._make_manager()
        progress_events = []

        result = manager.add_documents(
            ["a", "b", "dup", "c"],
            [
                {"chunk_uid": "r1::chunk:1", "rcept_no": "r1"},
                {"chunk_uid": "r1::chunk:2", "rcept_no": "r1"},
                {"chunk_uid": "r1::chunk:2", "rcept_no": "r1"},
                {"chunk_uid": "r1::chunk:3", "rcept_no": "r1"},
            ],
            resume=False,
            batch_size=2,
            on_progress=lambda current, total: progress_events.append((current, total)),
        )

        self.assertEqual(result["added_chunks"], 3)
        self.assertEqual(result["skipped_chunks"], 1)
        self.assertEqual(result["batch_count"], 2)
        self.assertEqual(len(manager.vector_store.add_calls), 2)
        self.assertEqual(manager.vector_store.add_calls[0]["texts"], ["a", "b"])
        self.assertEqual(manager.vector_store.add_calls[1]["texts"], ["c"])
        self.assertEqual(progress_events, [(0, 3), (2, 3), (3, 3)])
        self.assertEqual(manager._update_structure_graph.call_count, 2)
        manager._init_bm25.assert_called_once()

    def test_add_documents_can_skip_vector_add_for_bm25_only_debug_store(self) -> None:
        manager = self._make_manager()
        manager.skip_vector_add = True
        progress_events = []

        result = manager.add_documents(
            ["a", "b"],
            [
                {"chunk_uid": "r1::chunk:1", "rcept_no": "r1"},
                {"chunk_uid": "r1::chunk:2", "rcept_no": "r1"},
            ],
            resume=False,
            batch_size=1,
            on_progress=lambda current, total: progress_events.append((current, total)),
        )

        self.assertEqual(result["added_chunks"], 2)
        self.assertTrue(result["vector_add_skipped"])
        self.assertEqual(manager.vector_store.add_calls, [])
        self.assertEqual(manager._update_structure_graph.call_count, 2)
        manager._init_bm25.assert_called_once()
        self.assertEqual(progress_events, [(0, 2), (1, 2), (2, 2)])

    def test_skip_vector_add_resume_reads_existing_structure_graph_uids(self) -> None:
        manager = self._make_manager()
        manager.skip_vector_add = True
        manager._structure_graph = {
            "nodes": {
                "r1::chunk:1": {
                    "metadata": {"chunk_uid": "r1::chunk:1", "rcept_no": "r1"}
                }
            }
        }

        result = manager.add_documents(
            ["old", "new"],
            [
                {"chunk_uid": "r1::chunk:1", "rcept_no": "r1"},
                {"chunk_uid": "r1::chunk:2", "rcept_no": "r1"},
            ],
            resume=True,
            batch_size=8,
        )

        self.assertEqual(result["added_chunks"], 1)
        self.assertEqual(result["skipped_chunks"], 1)
        self.assertEqual(manager.vector_store.add_calls, [])

    def test_cache_meta_completed_distinguishes_in_progress(self) -> None:
        self.assertTrue(_cache_meta_is_completed({"status": "completed"}))
        self.assertTrue(_cache_meta_is_completed({"signature": {"x": 1}}))
        self.assertFalse(_cache_meta_is_completed({"status": "in_progress"}))

    def test_store_signature_tracks_embedding_backend(self) -> None:
        config = {
            "metadata": {"company": "삼성전자", "year": 2024, "report_type": "사업보고서", "rcept_no": "r1"},
            "chunk_size": 2500,
            "chunk_overlap": 320,
            "ingest_mode": "contextual_selective_v2",
            "k": 8,
            "embedding_provider": "huggingface",
            "embedding_model_name": "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
        }
        collection_name = "dart_reports_v2_test"

        store_signature = _build_store_signature(config, collection_name)
        cache_signature = _build_cache_signature(config, collection_name)

        self.assertEqual(store_signature["collection_name"], collection_name)
        self.assertEqual(store_signature["embedding"]["provider"], "huggingface")
        self.assertEqual(
            store_signature["embedding"]["model_name"],
            "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
        )
        self.assertEqual(store_signature["embedding"]["dimension"], 384)
        self.assertEqual(cache_signature["store_signature"], store_signature)

    def test_cache_signature_tracks_multi_report_inventory(self) -> None:
        base_config = {
            "report_path": "data/reports/삼성전자/2023_사업보고서_20240312000736.html",
            "metadata": {
                "company": "삼성전자",
                "year": 2023,
                "report_type": "사업보고서",
                "rcept_no": "20240312000736",
            },
            "chunk_size": 2500,
            "chunk_overlap": 320,
            "ingest_mode": "structural_selective_v2",
            "k": 8,
        }
        examples = [
            EvalExample(
                id="SAM_T2_002",
                question="q",
                ground_truth="g",
                company="삼성전자",
                year=2023,
                section="s",
                source_reports=[
                    {
                        "corp_name": "삼성전자",
                        "year": 2023,
                        "report_type": "사업보고서",
                        "rcept_no": "20240312000736",
                    },
                    {
                        "corp_name": "삼성전자",
                        "year": 2022,
                        "report_type": "사업보고서",
                        "rcept_no": "20230307000542",
                    },
                ],
            )
        ]
        report_inventory = _collect_report_inventory(base_config, base_config["metadata"], examples)
        config_with_inventory = dict(base_config)
        config_with_inventory["report_inventory"] = report_inventory

        cache_signature = _build_cache_signature(config_with_inventory, "dart_reports_v2_test")

        self.assertEqual(
            cache_signature["report_inventory"],
            [
                {
                    "company": "삼성전자",
                    "year": 2023,
                    "report_type": "사업보고서",
                    "rcept_no": "20240312000736",
                },
                {
                    "company": "삼성전자",
                    "year": 2022,
                    "report_type": "사업보고서",
                    "rcept_no": "20230307000542",
                },
            ],
        )

    def test_collect_report_inventory_includes_multi_report_sources(self) -> None:
        config = {
            "report_path": "data/reports/삼성전자/2023_사업보고서_20240312000736.html",
        }
        metadata = {
            "company": "삼성전자",
            "year": 2023,
            "report_type": "사업보고서",
            "rcept_no": "20240312000736",
        }
        examples = [
            EvalExample(
                id="SAM_T2_002",
                question="q",
                ground_truth="g",
                company="삼성전자",
                year=2023,
                section="s",
                source_reports=[
                    {
                        "corp_name": "삼성전자",
                        "year": 2023,
                        "report_type": "사업보고서",
                        "rcept_no": "20240312000736",
                    },
                    {
                        "corp_name": "삼성전자",
                        "year": 2022,
                        "report_type": "사업보고서",
                        "rcept_no": "20230307000542",
                    },
                ],
            )
        ]

        report_inventory = _collect_report_inventory(config, metadata, examples)

        self.assertEqual(len(report_inventory), 2)
        self.assertEqual(report_inventory[0]["metadata"]["rcept_no"], "20240312000736")
        self.assertEqual(report_inventory[1]["metadata"]["rcept_no"], "20230307000542")
        self.assertIn("2022_사업보고서_20230307000542.html", report_inventory[1]["report_path"])

    def test_inventory_eval_examples_include_full_eval_question_ids(self) -> None:
        config = {
            "eval_dataset_path": "ignored.json",
            "eval_mode": "question_ids",
            "question_ids": ["SAM_T2_078"],
        }
        metadata = {
            "company": "삼성전자",
            "year": 2023,
        }
        examples = [
            EvalExample(
                id="SAM_T2_002",
                question="시설투자 증감률",
                ground_truth="g1",
                company="삼성전자",
                year=2023,
                section="s",
            ),
            EvalExample(
                id="SAM_T2_078",
                question="다른 질문",
                ground_truth="g2",
                company="삼성전자",
                year=2023,
                section="s",
            ),
        ]

        from src.ops import benchmark_runner as runner_module

        original_loader = runner_module._load_eval_dataset
        runner_module._load_eval_dataset = lambda path: list(examples)
        try:
            selected = _inventory_eval_examples(
                config,
                metadata,
                {"enabled": True, "eval_mode": "question_ids", "question_ids": ["SAM_T2_002"]},
            )
        finally:
            runner_module._load_eval_dataset = original_loader

        self.assertEqual([example.id for example in selected], ["SAM_T2_078", "SAM_T2_002"])

    def test_store_signature_mismatch_detects_embedding_dimension_change(self) -> None:
        expected = {
            "store_signature": {
                "collection_name": "dart_reports_v2_test",
                "embedding": {
                    "provider": "huggingface",
                    "model_name": "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
                    "dimension": 384,
                },
            }
        }
        actual = {
            "store_signature": {
                "collection_name": "dart_reports_v2_test",
                "embedding": {
                    "provider": "google",
                    "model_name": "models/gemini-embedding-2",
                    "dimension": 3072,
                },
            }
        }

        self.assertFalse(_store_signature_matches(actual, expected["store_signature"]))

    def test_search_raises_when_query_fallback_disabled(self) -> None:
        manager = self._make_manager()
        manager.allow_query_embedding_fallback = False

        with self.assertRaises(RuntimeError):
            manager.search("테스트", k=3)

    def test_structural_selective_v2_ingest_skips_llm_context_generation(self) -> None:
        agent = SimpleNamespace(
            vsm=_FakeIngestVectorManager(),
            llm=SimpleNamespace(batch=Mock(side_effect=AssertionError("llm.batch should not be called"))),
        )
        chunks = [
            SimpleNamespace(
                content="매출액 | 100",
                metadata={
                    "parent_id": "p1",
                    "company": "삼성전자",
                    "year": 2024,
                    "report_type": "사업보고서",
                    "section": "요약재무정보",
                    "section_path": "II. 사업의 내용 > 요약재무정보",
                    "block_type": "table",
                    "statement_type": "summary_financials",
                    "consolidation_scope": "consolidated",
                    "table_context": "주요 부문별 실적",
                    "table_row_labels_text": "DX\nDS\nSDC",
                    "period_focus": "current",
                    "unit_hint": "억원",
                },
            ),
            SimpleNamespace(
                content="이 문단은 선택되지 않아야 할 정도로 길고 일반적인 설명입니다. " * 50,
                metadata={
                    "parent_id": "p2",
                    "company": "삼성전자",
                    "year": 2024,
                    "report_type": "사업보고서",
                    "section": "기타",
                    "section_path": "I. 회사의 개요 > 기타",
                    "block_type": "paragraph",
                },
            ),
        ]

        metrics = _run_ingest(
            agent,
            chunks,
            {
                "ingest_mode": "structural_selective_v2",
                "selective_v2_short_text_threshold": 700,
                "selective_v2_short_table_threshold": 1600,
                "selective_v2_sections": ["요약재무정보"],
                "resume_partial_store": False,
                "resume_batch_size": 64,
            },
            return_artifacts=True,
        )

        self.assertEqual(metrics["mode"], "structural_selective_v2")
        self.assertEqual(metrics["api_calls"], 0)
        self.assertEqual(metrics["contextualized_chunks"], 1)
        self.assertEqual(metrics["child_context_calls"], 0)
        self.assertEqual(len(agent.vsm.document_calls), 1)
        texts = agent.vsm.document_calls[0]["texts"]
        self.assertIn("[선택사유: short_table]", texts[0])
        self.assertIn("[statement_type: summary_financials]", texts[0])
        self.assertIn("[table_context: 주요 부문별 실적]", texts[0])
        self.assertNotIn("[선택사유:", texts[1])

    def test_structural_parent_hybrid_v2_adds_parent_digest_without_llm_calls(self) -> None:
        agent = SimpleNamespace(
            vsm=_FakeIngestVectorManager(),
            llm=SimpleNamespace(batch=Mock(side_effect=AssertionError("llm.batch should not be called"))),
        )
        chunks = [
            SimpleNamespace(
                content="매출액 | 100",
                metadata={
                    "parent_id": "p1",
                    "company": "삼성전자",
                    "year": 2024,
                    "report_type": "사업보고서",
                    "section": "요약재무정보",
                    "section_path": "II. 사업의 내용 > 요약재무정보",
                    "block_type": "table",
                    "statement_type": "summary_financials",
                    "table_context": "주요 부문별 실적",
                    "local_heading": "연결 실적",
                },
            ),
            SimpleNamespace(
                content="DS 부문은 메모리 중심으로 성장했습니다. " * 8,
                metadata={
                    "parent_id": "p1",
                    "company": "삼성전자",
                    "year": 2024,
                    "report_type": "사업보고서",
                    "section": "요약재무정보",
                    "section_path": "II. 사업의 내용 > 요약재무정보",
                    "block_type": "paragraph",
                    "local_heading": "연결 실적",
                },
            ),
        ]

        metrics = _run_ingest(
            agent,
            chunks,
            {
                "ingest_mode": "structural_parent_hybrid_v2",
                "selective_v2_short_text_threshold": 700,
                "selective_v2_short_table_threshold": 1600,
                "selective_v2_sections": ["요약재무정보"],
                "resume_partial_store": False,
                "resume_batch_size": 64,
            },
            return_artifacts=True,
        )

        self.assertEqual(metrics["mode"], "structural_parent_hybrid_v2")
        self.assertEqual(metrics["api_calls"], 0)
        self.assertEqual(metrics["stored_parent_chunks"], 1)
        self.assertEqual(len(agent.vsm.document_calls), 1)
        texts = agent.vsm.document_calls[0]["texts"]
        self.assertIn("[parent_preview:", texts[0])
        self.assertIn("[parent_local_heading: 연결 실적]", texts[0])
        self.assertIn("[선택사유: short_table]", texts[0])
        self.assertIn("[parent_preview:", texts[1])

    def test_ensure_benchmark_report_path_auto_fetches_exact_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            report_file = Path(temp_dir) / "2023_사업보고서_20990101000001.html"
            report_file.write_text("<html>report</html>", encoding="utf-8")
            fetcher = Mock()
            fetcher.fetch_company_reports.return_value = [
                ReportMetadata(
                    rcept_no="20990101000001",
                    corp_name="테스트자동차",
                    corp_code="",
                    stock_code="005380",
                    report_nm="사업보고서 (2099.12)",
                    report_type="사업보고서",
                    rcept_dt="20990101",
                    year=2099,
                    file_path=str(report_file),
                )
            ]

            resolved = _ensure_benchmark_report_path(
                PROJECT_ROOT / "data" / "reports" / "테스트자동차" / "2099_사업보고서_20990101000001.html",
                {
                    "company": "테스트자동차",
                    "year": 2099,
                    "report_type": "사업보고서",
                    "rcept_no": "20990101000001",
                },
                {"auto_fetch_missing_report": True},
                fetcher=fetcher,
            )

            self.assertEqual(resolved, report_file.resolve())
            fetcher.fetch_company_reports.assert_called_once_with("테스트자동차", [2099], report_type="사업보고서")

    def test_ensure_benchmark_report_path_requires_exact_receipt_when_present(self) -> None:
        fetcher = Mock()
        fetcher.fetch_company_reports.return_value = [
            ReportMetadata(
                rcept_no="20990101000002",
                corp_name="테스트자동차",
                corp_code="",
                stock_code="005380",
                report_nm="사업보고서 (2099.12) [정정]",
                report_type="사업보고서",
                rcept_dt="20990102",
                year=2099,
                file_path=str(PROJECT_ROOT / "data" / "reports" / "테스트자동차" / "2099_사업보고서_20990101000002.html"),
            )
        ]

        with self.assertRaises(FileNotFoundError):
            _ensure_benchmark_report_path(
                PROJECT_ROOT / "data" / "reports" / "테스트자동차" / "2099_사업보고서_20990101000001.html",
                {
                    "company": "테스트자동차",
                    "year": 2099,
                    "report_type": "사업보고서",
                    "rcept_no": "20990101000001",
                },
                {"auto_fetch_missing_report": True},
                fetcher=fetcher,
            )


if __name__ == "__main__":
    unittest.main()
