"""Terminal admission is not ordinary ingest context fallback."""

from types import SimpleNamespace
import unittest
from unittest.mock import Mock

from src.ingestion.context_generator import ContextGenerator
from src.utils.provider_errors import ProviderAdmissionError


class IngestAdmissionBoundaryTests(unittest.TestCase):
    def test_single_context_keeps_original_terminal_error(self):
        failure = ProviderAdmissionError("budget_exceeded", "stop")
        llm = Mock()
        llm.invoke.side_effect = failure
        with self.assertRaises(ProviderAdmissionError) as caught:
            ContextGenerator(llm, Mock())._generate_context("source", {})
        self.assertIs(caught.exception, failure)
        self.assertEqual(llm.invoke.call_count, 1)

    def test_batch_raised_or_returned_terminal_error_stops_before_indexing(self):
        for returned in (False, True):
            with self.subTest(returned=returned):
                failure = ProviderAdmissionError("budget_exceeded", "stop")
                llm, store = Mock(), Mock()
                store.add_documents.return_value = {"added_chunks": 3}
                if returned:
                    llm.batch.return_value = [failure]
                else:
                    llm.batch.side_effect = failure
                chunks = [SimpleNamespace(content=f"source {i}", metadata={"chunk_uid": str(i)}) for i in range(3)]
                with self.assertRaises(ProviderAdmissionError) as caught:
                    ContextGenerator(llm, store).contextual_ingest(chunks, max_workers=1, batch_size=1)
                self.assertIs(caught.exception, failure)
                self.assertEqual(llm.batch.call_count, 1)
                store.add_documents.assert_not_called()

    def test_ordinary_context_error_retains_existing_fallback(self):
        llm = Mock()
        llm.invoke.side_effect = RuntimeError("ordinary provider failure")
        generator = ContextGenerator(llm, Mock())
        self.assertEqual(generator._generate_context("source", {}), generator._fallback_context({}))


if __name__ == "__main__":
    unittest.main()
