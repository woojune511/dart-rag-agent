from pathlib import Path
import sqlite3
import tempfile
import unittest

from src.ops.adopt_store_manifest import _inspect_chroma, validate_manifest_adoption
from src.storage.store_manifest import canonical_store_manifest


class AdoptStoreManifestTests(unittest.TestCase):
    def test_chroma_inspection_reads_collection_dimension_without_mutating_store(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            store_path = Path(temp_dir)
            database_path = store_path / "chroma.sqlite3"
            connection = sqlite3.connect(database_path)
            try:
                connection.execute(
                    "CREATE TABLE collections ("
                    "id TEXT PRIMARY KEY, name TEXT NOT NULL, dimension INTEGER)"
                )
                connection.execute(
                    "INSERT INTO collections (id, name, dimension) VALUES (?, ?, ?)",
                    ("collection-id", "runtime", 3072),
                )
                connection.commit()
            finally:
                connection.close()

            before = database_path.read_bytes()
            observed = _inspect_chroma(store_path, "runtime")

            self.assertEqual(observed, ("runtime", 3072))
            self.assertEqual(database_path.read_bytes(), before)
            self.assertFalse(database_path.with_name("chroma.sqlite3-wal").exists())
            self.assertFalse(database_path.with_name("chroma.sqlite3-shm").exists())

    def test_chroma_inspection_rejects_missing_collection(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            store_path = Path(temp_dir)
            database_path = store_path / "chroma.sqlite3"
            connection = sqlite3.connect(database_path)
            try:
                connection.execute(
                    "CREATE TABLE collections ("
                    "id TEXT PRIMARY KEY, name TEXT NOT NULL, dimension INTEGER)"
                )
                connection.commit()
            finally:
                connection.close()

            with self.assertRaisesRegex(ValueError, "collection is missing"):
                _inspect_chroma(store_path, "runtime")

    def test_adoption_requires_exact_collection_dimension_and_profile(self) -> None:
        expected = canonical_store_manifest(collection_name="runtime")
        accepted = validate_manifest_adoption(
            expected=expected,
            observed_collection_name="runtime",
            observed_dimension=expected.embedding.dimension,
            declared_profile_id=expected.ingest.profile_id,
        )
        rejected = validate_manifest_adoption(
            expected=expected,
            observed_collection_name="other",
            observed_dimension=12,
            declared_profile_id="other-profile",
        )

        self.assertEqual(accepted["status"], "compatible")
        self.assertTrue(accepted["write_allowed"])
        self.assertEqual(
            set(rejected["errors"]),
            {
                "collection_name_mismatch",
                "embedding_dimension_mismatch",
                "ingest_profile_mismatch",
            },
        )


if __name__ == "__main__":
    unittest.main()
