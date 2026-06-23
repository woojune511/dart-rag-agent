import os
import unittest
from unittest.mock import patch

from src.storage.vector_store import _select_default_embedding_provider


class EmbeddingRuntimeConfigTests(unittest.TestCase):
    def test_explicit_embedding_provider_overrides_canonical_default(self) -> None:
        with patch.dict(
            os.environ,
            {
                "DART_EMBEDDING_PROVIDER": "google",
                "GOOGLE_API_KEY": "google-key",
                "OPENAI_API_KEY": "openai-key",
            },
            clear=True,
        ), patch("src.storage.embedding_config._DOTENV_VALUES", {}):
            self.assertEqual(_select_default_embedding_provider(), "google")

    def test_openai_is_preferred_when_both_api_keys_are_available(self) -> None:
        with patch.dict(
            os.environ,
            {
                "GOOGLE_API_KEY": "google-key",
                "OPENAI_API_KEY": "openai-key",
            },
            clear=True,
        ), patch("src.storage.embedding_config._DOTENV_VALUES", {}):
            self.assertEqual(_select_default_embedding_provider(), "openai")

    def test_google_is_fallback_when_openai_key_is_missing(self) -> None:
        with patch.dict(os.environ, {"GOOGLE_API_KEY": "google-key"}, clear=True), patch(
            "src.storage.embedding_config._DOTENV_VALUES",
            {},
        ):
            self.assertEqual(_select_default_embedding_provider(), "google")

    def test_huggingface_is_fallback_when_remote_keys_are_missing(self) -> None:
        with patch.dict(os.environ, {}, clear=True), patch(
            "src.storage.embedding_config._DOTENV_VALUES",
            {},
        ):
            self.assertEqual(_select_default_embedding_provider(), "huggingface")


if __name__ == "__main__":
    unittest.main()
