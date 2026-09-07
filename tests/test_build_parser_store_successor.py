"""Actual temporary Chroma + lower-I/O failures; no source store or providers."""

from contextlib import closing
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from src.ops import build_parser_store_successor as builder
from src.ops.plan_parser_store_successor import compare_index_texts, parse_source_projection, plan_store_successor
from src.storage.graph_persistence import load_structure_graph, persist_structure_graph
from src.storage.metadata_payloads import compact_node_for_storage, load_table_payloads, metadata_for_chroma, metadata_with_table_payload
from src.storage.parent_store import save_parents
from src.storage.store_manifest import assess_store_readiness, canonical_store_manifest, read_store_manifest, write_store_manifest
from src.storage.structure_graph import empty_structure_graph, update_structure_graph


ROOT = Path(__file__).resolve().parents[1]


class ParserStoreReuseTests(unittest.TestCase):
    def setUp(self):
        self.network = patch("socket.socket.connect", side_effect=AssertionError("No provider calls"))
        self.network.start()
        self.addCleanup(self.network.stop)

    def fixture(self, root):
        source = root / "original"
        source.mkdir()
        filing = root / "source.xml"
        shutil.copyfile(Path(__file__).parent / "fixtures/source_context_hierarchy.xml", filing)
        reports = [{"source_file": str(filing), "metadata": {"rcept_no": "fixture", "year": 2024}}]
        manifest = canonical_store_manifest(collection_name="successor_fixture", embedding_dimension=3)
        old = replace(manifest, ingest=replace(manifest.ingest, parser_schema_version="financial_parser_v1"))
        chunks, texts, parents, _ = parse_source_projection(reports, manifest)
        old_metadatas = [deepcopy(chunk.metadata) for chunk in chunks]
        old_metadatas[0]["chunk_uid"] = "historic:renumbered"
        for metadata in old_metadatas:
            table = json.loads(metadata["table_object_json"])
            table["unit_hint"] = "억원"
            table["source_contexts"] = []
            table["header_rows"] = [["historical inferred header"]]
            metadata["table_object_json"] = json.dumps(table)
        old_texts = list(texts)
        old_texts[1] = "obsolete index prefix\n" + old_texts[1]
        vectors = [[1., 0., 0.], [0., 1., 0.], [0., 0., 1.]]
        with closing(builder._client(source)) as client:
            collection = client.create_collection(old.collection_name, embedding_function=None)
            collection.add(ids=[f"old-vector-{index}" for index in range(len(chunks))],
                           documents=old_texts, metadatas=[metadata_for_chroma(m) for m in old_metadatas], embeddings=vectors)
        graph = update_structure_graph(empty_structure_graph(), old_texts, old_metadatas, lambda m: m["chunk_uid"])
        persist_structure_graph(source / "document_structure_graph.json", source / "table_payloads.json", graph,
                                compact_node_for_storage=compact_node_for_storage)
        save_parents(source / "parents.json", parents)
        write_store_manifest(source, old)
        plan = plan_store_successor(source, reports)
        return source, reports, plan, chunks

    def prepared_fixture(self, root):
        source, reports, plan, chunks = self.fixture(root)
        prepared = builder.prepare_successor(plan, reports, root / "preparation")
        request = prepared["embedding_request"]
        supplied = {"schema_version": "parser_successor_embeddings_v1", "embedding": request["embedding"],
                    "request_fingerprint": request["fingerprint"],
                    "vectors_by_text_sha256": {row["text_sha256"]: [0., 1., 0.] for row in request["texts"]}}
        return source, prepared, supplied, chunks

    def test_actual_copy_reuse_new_metadata_and_strict_ready_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, reports, plan, chunks = self.fixture(root)
            client_factory = builder._client
            with patch.object(builder, "_client", wraps=client_factory) as opened:
                prepared = builder.prepare_successor(plan, reports, root / "prep")
            self.assertEqual([Path(call.args[0]) for call in opened.call_args_list], [root / "prep/source_copy"])
            self.assertEqual(prepared, builder.prepare_successor(plan, reports, root / "prep-again"))
            self.assertEqual(sum(row["embedding"] is not None for row in prepared["documents"]), 2)
            first = next(row for row in prepared["documents"] if row["metadata"]["chunk_uid"] == chunks[0].metadata["chunk_uid"])
            self.assertEqual(first["reused_from"]["chunk_uid"], "historic:renumbered")
            self.assertEqual(first["embedding"], [1., 0., 0.])
            self.assertEqual(len(prepared["embedding_request"]["texts"]), 1)
            self.assertFalse((root / "prep/store_manifest.json").exists())
            request = prepared["embedding_request"]
            supplied = {"schema_version": "parser_successor_embeddings_v1", "embedding": request["embedding"],
                        "request_fingerprint": request["fingerprint"],
                        "vectors_by_text_sha256": {request["texts"][0]["text_sha256"]: [0., 1., 0.]}}
            output = root / "successor"
            result = builder.build_successor(prepared, supplied, output, batch_size=1)
            self.assertTrue(result["ready"])
            self.assertEqual(result["provider_calls"], 0)
            self.assertEqual(result["health"]["vectors"], 3)
            manifest = read_store_manifest(output)
            self.assertTrue(assess_store_readiness(output, expected=manifest).ready)
            graph = load_structure_graph(output / "document_structure_graph.json")
            payloads = load_table_payloads(output / "table_payloads.json")
            for chunk in chunks:
                actual = metadata_with_table_payload(graph["nodes"][chunk.metadata["chunk_uid"]]["metadata"], payloads)
                self.assertEqual(json.loads(actual["table_object_json"]), json.loads(chunk.metadata["table_object_json"]))
            self.assertEqual(result, builder.build_successor(prepared, supplied, output, resume=True))
            builder._assert_inputs_unchanged(source, plan["input_hashes"])

    def test_no_exact_vector_never_silently_becomes_a_paid_request(self):
        chunk = SimpleNamespace(metadata={"rcept_no": "f", "chunk_uid": "new"})
        comparison = {"chunks": [{"chunk_uid": "new", "exact_text_source_uids": ["old"]}]}
        for rows in ([], [{"vector_id": "v", "text": "wrong text", "metadata": {"chunk_uid": "old", "rcept_no": "f"}, "embedding": [1, 0, 0]}],
                     [{"vector_id": "v", "text": "exact", "metadata": {"chunk_uid": "old", "rcept_no": "other"}, "embedding": [1, 0, 0]}]):
            with self.subTest(rows=rows), self.assertRaisesRegex(ValueError, "Reusable source vector missing"):
                builder.assemble_reuse_documents([chunk], ["exact"], comparison, rows, 3)

    def test_invalid_vectors_are_rejected(self):
        for vector in (None, [1, 2], [1, float("nan"), 3], [1, float("inf"), 3], [0, 0, 0], [1e99, 0, 0]):
            with self.subTest(vector=vector), self.assertRaises(ValueError):
                builder._vector(vector, 3)

    def test_missing_texts_are_deduplicated_without_fuzzy_or_cross_filing_reuse(self):
        chunks = [SimpleNamespace(metadata={"rcept_no": "new-filing", "chunk_uid": str(i)}) for i in range(3)]
        texts = ["same input", "same input", "same input "]
        old = {"old": {"text": "same input", "metadata": {"rcept_no": "other-filing"}}}
        comparison = compare_index_texts(old, chunks, texts)
        documents, requests = builder.assemble_reuse_documents(chunks, texts, comparison, [], 3)
        self.assertEqual(len(requests), 2)
        self.assertTrue(all(row["embedding"] is None for row in documents))
        self.assertEqual((documents, requests), builder.assemble_reuse_documents(chunks[::-1], texts[::-1], comparison, [], 3))

    def test_source_hash_or_parser_projection_drift_blocks_before_copy(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, reports, plan, _ = self.fixture(root)
            wrong = deepcopy(plan)
            wrong["new_source_projection_fingerprint"] = "wrong"
            with self.assertRaisesRegex(ValueError, "projection drifted"):
                builder.prepare_successor(wrong, reports, root / "no-copy")
            self.assertFalse((root / "no-copy").exists())
            Path(reports[0]["source_file"]).write_text("changed original fixture", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "input hashes"):
                builder.prepare_successor(plan, reports, root / "no-copy")

    def test_missing_extra_and_wrong_model_vectors_block_before_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _, prepared, supplied, _ = self.prepared_fixture(root)
            extra, wrong = deepcopy(supplied), deepcopy(supplied)
            extra["vectors_by_text_sha256"]["hidden"] = [1, 0, 0]
            wrong["embedding"]["model_name"] = "wrong-model"
            wrong_request = {**supplied, "request_fingerprint": "wrong"}
            for data in (None, extra, wrong, wrong_request):
                with self.subTest(data=data), self.assertRaises(ValueError):
                    builder.build_successor(prepared, data, root / "no-output")
                self.assertFalse((root / "no-output").exists())

    def test_prepared_metadata_parent_and_embedding_identity_drift_fail(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _, prepared, supplied, _ = self.prepared_fixture(root)
            variants = [deepcopy(prepared) for _ in range(3)]
            variants[0]["documents"][0]["metadata"]["unit_hint"] = "wrong"
            variants[1]["parents"] = {"wrong": "text"}
            variants[2]["manifest"]["embedding"]["provider"] = "different-provider"
            for variant in variants:
                with self.assertRaises(ValueError):
                    builder.build_successor(variant, supplied, root / "no-output")
                self.assertFalse((root / "no-output").exists())

    def test_lower_file_failure_leaves_unready_and_explicit_resume_preserves_snapshot(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _, prepared, supplied, _ = self.prepared_fixture(root)
            replace_path = Path.replace
            for filename in ("parents.json", "table_payloads.json", "document_structure_graph.json", "store_manifest.json"):
                with self.subTest(filename=filename):
                    output = root / filename.replace(".json", "")
                    attempted = []

                    def fail_lower_replace(path, target):
                        if Path(target).name == filename:
                            attempted.append(str(target))
                            raise OSError("injected lower file replace failure")
                        return replace_path(path, target)

                    with patch.object(Path, "replace", fail_lower_replace), self.assertRaisesRegex(OSError, "lower file replace"):
                        builder.build_successor(prepared, supplied, output)
                    self.assertTrue(attempted)
                    self.assertIsNone(read_store_manifest(output))
                    self.assertTrue(builder.build_successor(prepared, supplied, output, resume=True)["ready"])

    def test_new_process_resume_uses_saved_vectors_and_no_network(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _, prepared, supplied, _ = self.prepared_fixture(root)
            output = root / "successor"
            replace_path = Path.replace

            def fail_graph(path, target):
                if Path(target).name == "document_structure_graph.json":
                    raise OSError("graph interruption")
                return replace_path(path, target)

            with patch.object(Path, "replace", fail_graph), self.assertRaisesRegex(OSError, "graph interruption"):
                builder.build_successor(prepared, supplied, output)
            vectors_path = root / "supplied.json"
            vectors_path.write_text(json.dumps(supplied), encoding="utf-8")
            prepared_path = root / "preparation/prepared.json"
            run = subprocess.run([sys.executable, "-X", "utf8", "-m", "src.ops.build_parser_store_successor", "build",
                  "--prepared", str(prepared_path), "--prepared-sha256", builder._file_sha(prepared_path),
                  "--embeddings", str(vectors_path), "--embeddings-sha256", builder._file_sha(vectors_path),
                  "--output-store", str(output), "--resume"], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", timeout=45)
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertTrue(json.loads(run.stdout.strip().splitlines()[-1])["ready"])

    def test_missing_committed_payload_or_vector_prevents_publication(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _, prepared, supplied, _ = self.prepared_fixture(root)
            replace_path = Path.replace
            for damage in ("payload", "vector"):
                with self.subTest(damage=damage):
                    output = root / damage

                    def corrupt_lower_commit(path, target):
                        if damage == "payload" and Path(target).name == "table_payloads.json":
                            data = json.loads(path.read_text(encoding="utf-8"))
                            data["payloads"].pop(next(iter(data["payloads"])))
                            path.write_text(json.dumps(data), encoding="utf-8")
                        result = replace_path(path, target)
                        if damage == "vector" and Path(target).name == "document_structure_graph.json":
                            with closing(builder._client(output)) as client:
                                collection = client.get_collection(prepared["manifest"]["collection_name"], embedding_function=None)
                                collection.delete(ids=[prepared["documents"][0]["metadata"]["chunk_uid"]])
                        return result

                    with patch.object(Path, "replace", corrupt_lower_commit), self.assertRaises(ValueError):
                        builder.build_successor(prepared, supplied, output)
                    self.assertIsNone(read_store_manifest(output))
                    self.assertTrue(builder.build_successor(prepared, supplied, output, resume=True)["ready"])

    def test_changed_resume_inputs_or_wrong_existing_text_are_not_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _, prepared, supplied, _ = self.prepared_fixture(root)
            output = root / "successor"
            with patch.object(builder, "save_parents", side_effect=OSError("stop after vectors")), self.assertRaises(OSError):
                builder.build_successor(prepared, supplied, output)
            changed = deepcopy(supplied)
            first = next(iter(changed["vectors_by_text_sha256"]))
            changed["vectors_by_text_sha256"][first] = [1, 1, 1]
            with self.assertRaisesRegex(ValueError, "Resume input fingerprint"):
                builder.build_successor(prepared, changed, output, resume=True)
            with closing(builder._client(output)) as client:
                collection = client.get_collection(prepared["manifest"]["collection_name"], embedding_function=None)
                collection.update(ids=[prepared["documents"][0]["metadata"]["chunk_uid"]], documents=["corrupt stale text"],
                                  embeddings=[prepared["documents"][0]["embedding"]])
            with self.assertRaisesRegex(ValueError, "Stored vector/text/metadata mismatch"):
                builder.build_successor(prepared, supplied, output, resume=True)
            self.assertIsNone(read_store_manifest(output))

    def test_original_output_paths_and_unbound_artifacts_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, reports, plan, _ = self.fixture(root)
            for destination in (source, source / "child", root):
                with self.assertRaisesRegex(ValueError, "disjoint"):
                    builder.prepare_successor(plan, reports, destination)
            path = root / "artifact.json"
            path.write_text("{}", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
                builder._load_bound_json(path, "wrong")


if __name__ == "__main__":
    unittest.main()
