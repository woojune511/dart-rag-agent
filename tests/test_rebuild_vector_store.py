import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from src.ops.rebuild_vector_store import load_structure_graph_documents, rebuild_vector_store, validate_vector_store_external


class _FakeVectorStoreManager:
    instances = []

    def __init__(self, **kwargs):
        self.kwargs = dict(kwargs)
        self.added = None
        self.parents = None
        type(self).instances.append(self)

    def add_documents(self, chunks, metadatas, *, resume=False, batch_size=64, on_progress=None):
        self.added = {
            "chunks": list(chunks),
            "metadatas": list(metadatas),
            "resume": resume,
            "batch_size": batch_size,
        }
        return {
            "requested_chunks": len(chunks),
            "added_chunks": len(chunks),
            "skipped_chunks": 0,
            "batch_count": 1,
            "resume_enabled": resume,
        }

    def add_parents(self, parents):
        self.parents = dict(parents)

    def persist(self):
        self.persisted = True

    def validate_vector_index(self):
        return {"ok": True, "result_count": 1}


def _write_source_store(root: Path) -> Path:
    source = root / "source_store"
    source.mkdir()
    graph = {
        "nodes": {
            "b": {
                "chunk_uid": "b",
                "chunk_id": 2,
                "sub_chunk_idx": 0,
                "text": "second chunk",
                "metadata": {"rcept_no": "2024", "chunk_uid": "b", "chunk_id": 2},
            },
            "a": {
                "chunk_uid": "a",
                "chunk_id": 1,
                "sub_chunk_idx": 0,
                "text": "first chunk",
                "metadata": {"rcept_no": "2024", "chunk_uid": "a", "chunk_id": 1},
            },
            "empty": {
                "chunk_uid": "empty",
                "chunk_id": 3,
                "sub_chunk_idx": 0,
                "text": "",
                "metadata": {"rcept_no": "2024", "chunk_uid": "empty", "chunk_id": 3},
            },
        }
    }
    (source / "document_structure_graph.json").write_text(json.dumps(graph), encoding="utf-8")
    (source / "parents.json").write_text(json.dumps({"p1": "parent text"}), encoding="utf-8")
    return source


class RebuildVectorStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        _FakeVectorStoreManager.instances = []

    def test_load_structure_graph_documents_orders_nodes_and_parents(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = _write_source_store(Path(tmp))

            chunks, metadatas, parents = load_structure_graph_documents(source)

        self.assertEqual(chunks, ["first chunk", "second chunk"])
        self.assertEqual([metadata["chunk_uid"] for metadata in metadatas], ["a", "b"])
        self.assertEqual(parents, {"p1": "parent text"})

    def test_load_structure_graph_documents_hydrates_table_payload_sidecar(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = _write_source_store(Path(tmp))
            graph = json.loads((source / "document_structure_graph.json").read_text(encoding="utf-8"))
            graph["nodes"]["a"]["metadata"]["table_payload_id"] = "table_payload:abc"
            (source / "document_structure_graph.json").write_text(json.dumps(graph), encoding="utf-8")
            (source / "table_payloads.json").write_text(
                json.dumps(
                    {
                        "version": 1,
                        "payloads": {
                            "table_payload:abc": {
                                "table_row_records_json": "[rows]",
                                "table_value_records_json": "[values]",
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )

            _chunks, metadatas, _parents = load_structure_graph_documents(source)

        self.assertEqual(metadatas[0]["chunk_uid"], "a")
        self.assertEqual(metadatas[0]["table_row_records_json"], "[rows]")
        self.assertEqual(metadatas[0]["table_value_records_json"], "[values]")

    def test_rebuild_vector_store_populates_output_from_structure_graph(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = _write_source_store(root)
            graph = json.loads((source / "document_structure_graph.json").read_text(encoding="utf-8"))
            graph["nodes"]["a"]["metadata"]["table_payload_id"] = "table_payload:abc"
            (source / "document_structure_graph.json").write_text(json.dumps(graph), encoding="utf-8")
            (source / "table_payloads.json").write_text(
                json.dumps(
                    {
                        "version": 1,
                        "payloads": {
                            "table_payload:abc": {
                                "table_row_records_json": "[rows]",
                                "table_value_records_json": "[values]",
                            }
                        },
                        "stats": {"payload_count": 1, "referenced_node_count": 1},
                    }
                ),
                encoding="utf-8",
            )
            output = root / "rebuilt_store"

            with patch("src.ops.rebuild_vector_store.VectorStoreManager", _FakeVectorStoreManager):
                summary = rebuild_vector_store(
                    source_store=source,
                    output_store=output,
                    collection_name="test_collection",
                    embedding_provider="huggingface",
                    embedding_model_name="test-model",
                    batch_size=16,
                    force=False,
                    resume=False,
                    external_health_check=False,
                )

            manager = _FakeVectorStoreManager.instances[0]
            reopened = _FakeVectorStoreManager.instances[1]

        self.assertEqual(summary["documents"], 2)
        self.assertEqual(summary["parents"], 1)
        self.assertTrue(summary["health"]["ok"])
        self.assertEqual(manager.kwargs["collection_name"], "test_collection")
        self.assertEqual(manager.added["chunks"], ["first chunk", "second chunk"])
        self.assertEqual(manager.added["metadatas"][0]["table_row_records_json"], "[rows]")
        self.assertTrue(summary["source_table_payload_sidecar"]["exists"])
        self.assertEqual(summary["source_table_payload_sidecar"]["payload_count"], 1)
        self.assertEqual(summary["source_table_payload_sidecar"]["stats"]["payload_count"], 1)
        self.assertFalse(manager.added["resume"])
        self.assertEqual(manager.added["batch_size"], 16)
        self.assertEqual(manager.parents, {"p1": "parent text"})
        self.assertTrue(manager.persisted)
        self.assertEqual(reopened.kwargs["persist_directory"], manager.kwargs["persist_directory"])

    def test_rebuild_vector_store_requires_force_for_existing_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = _write_source_store(root)
            output = root / "existing_store"
            output.mkdir()

            with self.assertRaises(FileExistsError):
                rebuild_vector_store(
                    source_store=source,
                    output_store=output,
                    collection_name="test_collection",
                    embedding_provider="huggingface",
                    embedding_model_name="test-model",
                    batch_size=16,
                    force=False,
                    resume=False,
                    external_health_check=False,
                )

    def test_rebuild_vector_store_can_resume_existing_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = _write_source_store(root)
            output = root / "existing_store"
            output.mkdir()

            with patch("src.ops.rebuild_vector_store.VectorStoreManager", _FakeVectorStoreManager):
                summary = rebuild_vector_store(
                    source_store=source,
                    output_store=output,
                    collection_name="test_collection",
                    embedding_provider="huggingface",
                    embedding_model_name="test-model",
                    batch_size=16,
                    force=False,
                    resume=True,
                    external_health_check=False,
                )

            manager = _FakeVectorStoreManager.instances[0]

        self.assertTrue(summary["resume"])
        self.assertTrue(manager.added["resume"])

    def test_in_place_rebuild_uses_final_store_path_and_removes_successful_backup(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = _write_source_store(root)

            with patch("src.ops.rebuild_vector_store.VectorStoreManager", _FakeVectorStoreManager):
                summary = rebuild_vector_store(
                    source_store=source,
                    output_store=source,
                    collection_name="test_collection",
                    embedding_provider="huggingface",
                    embedding_model_name="test-model",
                    batch_size=16,
                    force=True,
                    in_place=True,
                    external_health_check=False,
                )

            manager = _FakeVectorStoreManager.instances[0]
            backup = root / "source_store.rebuild-source-backup"

        self.assertEqual(Path(summary["output_store"]).name, "source_store")
        self.assertTrue(manager.kwargs["persist_directory"].endswith("source_store"))
        self.assertFalse(backup.exists())

    def test_external_health_check_parses_subprocess_json(self) -> None:
        completed = SimpleNamespace(returncode=0, stdout='{"ok": true, "result_count": 1}\n', stderr="")
        with patch("src.ops.rebuild_vector_store.subprocess.run", return_value=completed):
            health = validate_vector_store_external(
                store=Path("store"),
                collection_name="collection",
                embedding_provider="huggingface",
                embedding_model_name="model",
            )

        self.assertTrue(health["ok"])
        self.assertTrue(health["external_process"])


if __name__ == "__main__":
    unittest.main()
