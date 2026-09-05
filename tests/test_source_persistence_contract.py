"""Fault injection at real sidecar persistence and resume boundaries."""

from copy import deepcopy
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from src.api.services import AppServices
from src.ingestion.context_generator import ContextGenerator
from src.ingestion.ingest_service import IngestService
from src.storage.atomic_json import atomic_write_json
from src.storage.graph_persistence import load_structure_graph
from src.storage.metadata_payloads import compact_node_for_storage, load_table_payloads
from src.storage.store_manifest import canonical_store_manifest, assess_store_readiness, write_store_manifest
from src.storage.vector_store import VectorStoreManager


class _Vectors:
    def __init__(self):
        self.rows = []
        self.add_calls = 0
        self.record_ids = []
        self.metadata_updates = []
        self._collection = self

    def add_texts(self, texts, metadatas):
        self.add_calls += 1
        self.rows.extend(zip(texts, metadatas))

    def get(self, where=None, **kwargs):
        indexed = [(index, row) for index, row in enumerate(self.rows) if not where or (
            isinstance(row[1], dict) and all(row[1].get(key) == value for key, value in where.items())
        )]
        return {
            "ids": [self.record_ids[index] if index < len(self.record_ids) else f"vector-{index}"
                    for index, _ in indexed],
            "documents": [row[0] for _, row in indexed],
            "metadatas": [row[1] for _, row in indexed],
        }

    def update(self, *, ids, metadatas):
        self.metadata_updates.append((ids, metadatas))
        all_ids = self.get()["ids"]
        for vector_id, metadata in zip(ids, metadatas):
            index = all_ids.index(vector_id)
            self.rows[index] = (self.rows[index][0], metadata)


def _manager(root, vectors=None):
    manager = VectorStoreManager.__new__(VectorStoreManager)
    manager.persist_directory = str(root)
    manager.vector_store = vectors or _Vectors()
    manager.force_bm25_only = False
    manager.skip_vector_add = False
    manager._graph_path = root / "document_structure_graph.json"
    manager._table_payloads_path = root / "table_payloads.json"
    manager._parents_path = root / "parents.json"
    manager._parents = manager._load_parents()
    manager._structure_graph = load_structure_graph(manager._graph_path)
    manager._table_payloads = load_table_payloads(manager._table_payloads_path)
    manager._init_bm25 = lambda: None
    manager.bm25_docs = []
    return manager


def _chunk(uid):
    return SimpleNamespace(content=f"original {uid}", metadata={
        "chunk_uid": uid, "rcept_no": "receipt", "parent_id": "parent",
        "chunk_id": int(uid[-1]), "table_row_records_json": f'["{uid}"]',
    })


class SourcePersistenceContractTests(unittest.TestCase):
    def test_payload_failure_preserves_both_files_and_memory(self):
        with tempfile.TemporaryDirectory() as directory:
            manager = _manager(Path(directory))
            old, new = _chunk("chunk1"), _chunk("chunk2")
            manager.add_documents([old.content], [old.metadata])
            graph_bytes = manager._graph_path.read_bytes()
            payload_bytes = manager._table_payloads_path.read_bytes()
            memory = deepcopy(manager._structure_graph)
            with patch("src.storage.graph_persistence.atomic_write_json", side_effect=OSError("disk full")):
                with self.assertRaisesRegex(OSError, "disk full"):
                    manager.add_documents([new.content], [new.metadata])
            self.assertEqual(manager._graph_path.read_bytes(), graph_bytes)
            self.assertEqual(manager._table_payloads_path.read_bytes(), payload_bytes)
            self.assertEqual(manager._structure_graph, memory)
            self.assertFalse(manager.validate_source_integrity()["ready"])

    def test_graph_failure_keeps_old_snapshot_readable_and_resume_needs_no_provider(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manager = _manager(root)
            old, new = _chunk("chunk1"), _chunk("chunk2")
            manager.add_documents(["stored old context"], [old.metadata])
            graph_bytes = manager._graph_path.read_bytes()
            memory = deepcopy(manager._structure_graph)

            def write(path, payload):
                if path == manager._graph_path:
                    raise OSError("graph commit failed")
                atomic_write_json(path, payload)

            with patch("src.storage.graph_persistence.atomic_write_json", side_effect=write):
                with self.assertRaisesRegex(OSError, "graph commit failed"):
                    manager.add_documents(["stored new context"], [new.metadata])
            self.assertEqual(manager._graph_path.read_bytes(), graph_bytes)
            self.assertEqual(manager._structure_graph, memory)
            self.assertNotIn("chunk2", manager.list_structure_chunk_uids())
            payloads = load_table_payloads(manager._table_payloads_path)
            self.assertEqual(len(payloads), 2)
            self.assertEqual(_manager(root).get_structure_node("chunk1")["metadata"]["table_row_records_json"], '["chunk1"]')

            for restarted in (True, False):
                with self.subTest(restarted=restarted):
                    active = _manager(root, manager.vector_store) if restarted else manager
                    self.assertNotIn("chunk2", active.list_structure_chunk_uids())
                    llm = Mock()
                    llm.invoke.side_effect = AssertionError("repair must not call a provider")
                    context = ContextGenerator(llm, active)
                    result = context.contextual_ingest([old, new], resume_partial_store=True)
                    self.assertEqual(result["added_chunks"], 0)
                    self.assertEqual(result["api_calls"], 0)
                    self.assertEqual(active.vector_store.add_calls, 2)
                    self.assertEqual(active.get_structure_node("chunk2")["text"], "stored new context")
                    self.assertTrue(active.validate_source_integrity()["ready"])
                    self.assertEqual(llm.mock_calls, [])

    def test_benchmark_sidecar_repair_preserves_full_artifact_without_provider(self):
        with tempfile.TemporaryDirectory() as directory:
            manager = _manager(Path(directory))
            chunks = [_chunk("chunk1"), _chunk("chunk2")]
            stored_texts = ["first stored contextual text", "second stored contextual text"]
            manager.vector_store.add_texts(stored_texts, [chunk.metadata for chunk in chunks])
            llm = Mock()
            result = ContextGenerator(llm, manager).benchmark_contextual_ingest(
                chunks, resume_partial_store=True, return_artifacts=True,
            )
            self.assertEqual(result["api_calls"], 0)
            self.assertEqual(result["resume_added_chunks"], 0)
            self.assertEqual(result["resume_skipped_chunks"], 2)
            self.assertEqual(result["artifacts"]["texts"], stored_texts)
            self.assertEqual(result["artifacts"]["metadatas"], [chunk.metadata for chunk in chunks])
            self.assertEqual(manager.vector_store.add_calls, 1)
            self.assertEqual(llm.mock_calls, [])

    def test_resume_generates_context_only_for_new_chunks(self):
        with tempfile.TemporaryDirectory() as directory:
            manager = _manager(Path(directory))
            old, new = _chunk("chunk1"), _chunk("chunk2")
            manager.add_documents(["unchanged indexed text"], [old.metadata])
            context = ContextGenerator(Mock(), manager)
            with patch.object(context, "_generate_contexts_for_chunks", return_value=({0: "new context"}, {})) as generate:
                result = context.contextual_ingest([old, new], resume_partial_store=True)
            self.assertEqual(generate.call_args.args[0], [new])
            self.assertEqual(result["chunks"], 2)
            self.assertEqual(result["added_chunks"], 1)
            self.assertEqual(result["api_calls"], 1)
            self.assertEqual(manager.get_structure_node("chunk1")["text"], "unchanged indexed text")

    def test_ingest_does_not_skip_failed_sidecar_commit(self):
        with tempfile.TemporaryDirectory() as directory:
            manager = _manager(Path(directory))
            chunk = _chunk("chunk1")
            with patch("src.storage.graph_persistence.atomic_write_json", side_effect=OSError("failure")):
                with self.assertRaises(OSError):
                    manager.add_documents([chunk.content], [chunk.metadata])
            service = IngestService(None, None, None, manager, None)
            self.assertFalse(service._report_is_fully_indexed(SimpleNamespace(rcept_no="receipt"), [chunk]))

    def test_readiness_rejects_partial_vectors_then_recovers_after_source_repair(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manager = _manager(root)
            manifest = canonical_store_manifest(collection_name="runtime")
            write_store_manifest(root, manifest)
            chunk = _chunk("chunk1")
            manager.vector_store.add_texts(["stored context"], [chunk.metadata])
            services = AppServices(manifest, assess_store_readiness(root, expected=manifest), store=manager)
            self.assertEqual(services.refresh_readiness().status, "incomplete")
            self.assertFalse(services.readiness.ready)
            manager.repair_indexed_sources([chunk])
            self.assertTrue(services.refresh_readiness().ready)

    def test_missing_payload_and_unreadable_index_are_not_ready(self):
        with tempfile.TemporaryDirectory() as directory:
            manager = _manager(Path(directory))
            chunk = _chunk("chunk1")
            manager.add_documents([chunk.content], [chunk.metadata])
            atomic_write_json(manager._table_payloads_path, {"version": 1, "payloads": {}})
            self.assertFalse(manager.validate_source_integrity()["ready"])
            with patch.object(manager.vector_store, "get", side_effect=OSError("index unavailable")):
                self.assertFalse(manager.validate_source_integrity()["ready"])
                with self.assertRaises(OSError):
                    manager.list_indexed_chunk_uids()

    def test_empty_payload_is_missing_and_repaired_without_provider(self):
        for empty_payload in ({}, {"unrelated": "not a payload"}, {"table_row_records_json": " "}):
            with self.subTest(payload=empty_payload), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                manager = _manager(root)
                chunk = _chunk("chunk1")
                manager.add_documents(["stored context"], [chunk.metadata])
                payload_id = next(iter(load_table_payloads(manager._table_payloads_path)))
                atomic_write_json(manager._table_payloads_path, {
                    "version": 1, "payloads": {payload_id: empty_payload},
                })
                manager = _manager(root, manager.vector_store)
                integrity = manager.validate_source_integrity()
                self.assertFalse(integrity["ready"])
                self.assertEqual(integrity["missing_payload_ids"], [payload_id])
                llm = Mock()
                result = ContextGenerator(llm, manager).contextual_ingest([chunk], resume_partial_store=True)
                self.assertEqual(result["api_calls"], 0)
                self.assertEqual(result["added_chunks"], 0)
                self.assertEqual(manager.vector_store.add_calls, 1)
                self.assertEqual(llm.mock_calls, [])
                self.assertTrue(manager.validate_source_integrity()["ready"])
                self.assertEqual(manager.get_structure_node("chunk1")["metadata"]["table_row_records_json"], '["chunk1"]')

    def test_unidentifiable_vector_is_not_ready_and_blocks_new_provider_work(self):
        for metadata in (None, {}, {"unrelated": "value"}):
            with self.subTest(metadata=metadata), tempfile.TemporaryDirectory() as directory:
                manager = _manager(Path(directory))
                manager.vector_store.rows.append(("indexed document", metadata))
                integrity = manager.validate_source_integrity()
                self.assertFalse(integrity["ready"])
                self.assertEqual(integrity["unidentified_vector_ids"], ["vector-0"])
                self.assertEqual(manager.list_indexed_chunk_uids(rcept_no="receipt"), set())
                llm = Mock()
                with self.assertRaisesRegex(RuntimeError, "indexed source repair blocked"):
                    ContextGenerator(llm, manager).contextual_ingest([_chunk("chunk1")], resume_partial_store=True)
                self.assertEqual(llm.mock_calls, [])
                self.assertEqual(manager.vector_store.add_calls, 0)
                self.assertEqual(manager.vector_store.metadata_updates, [])

    def test_missing_vector_metadata_repairs_by_exact_id_without_embedding(self):
        with tempfile.TemporaryDirectory() as directory:
            manager = _manager(Path(directory))
            chunk = _chunk("chunk1")
            manager.vector_store.rows.append(("original stored contextual text", None))
            manager.vector_store.record_ids = ["chunk1"]
            self.assertFalse(manager.validate_source_integrity()["ready"])
            llm = Mock()
            result = ContextGenerator(llm, manager).contextual_ingest([chunk], resume_partial_store=True)
            self.assertEqual(result["api_calls"], 0)
            self.assertEqual(result["added_chunks"], 0)
            self.assertEqual(llm.mock_calls, [])
            self.assertEqual(manager.vector_store.add_calls, 0)
            self.assertEqual(len(manager.vector_store.metadata_updates), 1)
            self.assertEqual(manager.vector_store.metadata_updates[0][0], ["chunk1"])
            self.assertNotIn("table_row_records_json", manager.vector_store.metadata_updates[0][1][0])
            self.assertEqual(manager.get_structure_node("chunk1")["text"], "original stored contextual text")
            self.assertEqual(manager.get_structure_node("chunk1")["metadata"]["table_row_records_json"], '["chunk1"]')
            self.assertTrue(manager.validate_source_integrity()["ready"])

    def test_absent_vector_metadata_array_does_not_erase_coverage(self):
        with tempfile.TemporaryDirectory() as directory:
            manager = _manager(Path(directory))
            with patch.object(manager.vector_store, "get", return_value={"ids": ["orphan"], "metadatas": []}):
                integrity = manager.validate_source_integrity()
            self.assertFalse(integrity["ready"])
            self.assertEqual(integrity["unidentified_vector_ids"], ["orphan"])

    def test_parent_failure_does_not_publish_memory_or_replace_original(self):
        with tempfile.TemporaryDirectory() as directory:
            manager = _manager(Path(directory))
            manager.add_parents({"old": "original"})
            original = manager._parents_path.read_bytes()
            with patch("src.storage.parent_store.atomic_write_json", side_effect=OSError("failure")):
                with self.assertRaises(OSError):
                    manager.add_parents({"new": "not committed"})
            self.assertEqual(manager._parents, {"old": "original"})
            self.assertEqual(manager._parents_path.read_bytes(), original)

    def test_failed_atomic_replace_keeps_original_and_cleans_temp(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "data.json"
            atomic_write_json(path, {"old": True})
            original = path.read_bytes()
            with patch.object(Path, "replace", side_effect=OSError("replace failed")):
                with self.assertRaises(OSError):
                    atomic_write_json(path, {"new": True})
            self.assertEqual(path.read_bytes(), original)
            self.assertEqual(list(Path(directory).iterdir()), [path])

    def test_unresolved_payload_reference_is_not_silently_erased(self):
        with self.assertRaisesRegex(ValueError, "missing referenced table payload"):
            compact_node_for_storage({"metadata": {"table_payload_id": "missing"}}, {})
        with self.assertRaisesRegex(ValueError, "missing referenced table payload"):
            compact_node_for_storage({"metadata": {"table_payload_id": "empty"}}, {}, {"empty": {}})


if __name__ == "__main__":
    unittest.main()
