from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from src.storage.store_manifest import (
    assess_store_readiness,
    canonical_store_manifest,
    read_store_manifest,
    write_store_manifest,
)


class StoreManifestTests(unittest.TestCase):
    def test_missing_mismatch_compatible_and_degraded_readiness(self) -> None:
        expected = canonical_store_manifest(collection_name="runtime")
        mismatched = canonical_store_manifest(collection_name="other")
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)

            missing = assess_store_readiness(root, expected=expected)
            degraded = assess_store_readiness(
                root,
                expected=expected,
                allow_degraded_bm25_only=True,
                bm25_available=True,
            )
            write_store_manifest(root, mismatched)
            mismatch = assess_store_readiness(root, expected=expected)
            write_store_manifest(root, expected)
            compatible = assess_store_readiness(root, expected=expected)

        self.assertEqual((missing.status, missing.ready), ("missing", False))
        self.assertEqual(
            (degraded.status, degraded.ready, degraded.degraded),
            ("degraded", True, True),
        )
        self.assertEqual((mismatch.status, mismatch.ready), ("mismatch", False))
        self.assertEqual(
            (compatible.status, compatible.ready),
            ("compatible", True),
        )

    def test_manifest_round_trip_has_only_versioned_contract_fields(self) -> None:
        manifest = canonical_store_manifest(collection_name="runtime")
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = write_store_manifest(temporary_directory, manifest)
            loaded = read_store_manifest(temporary_directory)

        self.assertEqual(loaded, manifest)
        self.assertEqual(path.name, "store_manifest.json")
        self.assertEqual(
            set(manifest.to_projection()),
            {"schema_version", "collection_name", "embedding", "ingest"},
        )

    def test_unknown_manifest_fields_fail_readiness(self) -> None:
        expected = canonical_store_manifest(collection_name="runtime")
        projections = []
        for section in (None, "embedding", "ingest"):
            projection = expected.to_projection()
            target = projection if section is None else projection[section]
            target["unknown_option"] = True
            projections.append((section or "root", projection))

        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "store_manifest.json"
            for section, projection in projections:
                with self.subTest(section=section):
                    path.write_text(json.dumps(projection), encoding="utf-8")
                    readiness = assess_store_readiness(
                        temporary_directory,
                        expected=expected,
                        allow_degraded_bm25_only=True,
                        bm25_available=True,
                    )
                    self.assertEqual((readiness.status, readiness.ready), ("invalid", False))


if __name__ == "__main__":
    unittest.main()
