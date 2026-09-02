import unittest

from src.ops.adopt_store_manifest import validate_manifest_adoption
from src.storage.store_manifest import canonical_store_manifest


class AdoptStoreManifestTests(unittest.TestCase):
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
