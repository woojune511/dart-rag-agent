"""
Contextual ingest helpers for the financial graph agent.
"""

import logging
import os
import re
import time
from typing import Any, Dict, List, Optional

from src.config.retrieval_policy import CONTEXTUAL_INGEST_POLICY
from src.utils.gemini_usage_counts import (
    add_gemini_usage_counts,
    extract_gemini_usage_counts,
    zero_gemini_usage_counts,
)

logger = logging.getLogger(__name__)

DEFAULT_CONTEXT_MAX_WORKERS = max(4, min(12, (os.cpu_count() or 4) * 2))
DEFAULT_CONTEXT_BATCH_SIZE = max(8, DEFAULT_CONTEXT_MAX_WORKERS * 2)


def _context_block_type_label(metadata: dict) -> str:
    labels = CONTEXTUAL_INGEST_POLICY["block_type_labels"]
    if metadata.get("block_type") == "table":
        return str(labels["table"])
    return str(labels["paragraph"])


class FinancialAgentContextualMixin:
    def ingest(self, chunks: List) -> None:
        if not chunks:
            logger.warning("[ingest] chunks are empty.")
            return
        texts = [chunk.content for chunk in chunks]
        metadatas = [chunk.metadata for chunk in chunks]
        self.vsm.add_documents(texts, metadatas)
        logger.info("[ingest] indexed %s chunks", len(chunks))

    def _generate_context(self, text: str, metadata: dict) -> str:
        """Generate one concise context sentence for a chunk."""
        prompt = self._build_context_prompt(text, metadata)
        try:
            response = self.llm.invoke(prompt)
            return response.content.strip()
        except Exception as exc:
            logger.warning("Context generation failed: %s", exc)
            return self._fallback_context(metadata)

    def _fallback_context(self, metadata: dict) -> str:
        return str(CONTEXTUAL_INGEST_POLICY["fallback_context_template"]).format(
            company=metadata.get("company", "?"),
            year=metadata.get("year", "?"),
            section_path=metadata.get("section_path", metadata.get("section", "?")),
            block_type=_context_block_type_label(metadata),
        )

    def _build_context_prompt(self, text: str, metadata: dict) -> str:
        preview_chars = int(CONTEXTUAL_INGEST_POLICY["preview_chars"])
        preview = re.sub(r"\s+", " ", text[:preview_chars]).strip()
        return str(CONTEXTUAL_INGEST_POLICY["context_prompt_template"]).format(
            company=metadata.get("company", "?"),
            year=metadata.get("year", "?"),
            section_path=metadata.get("section_path", metadata.get("section", "?")),
            block_type=_context_block_type_label(metadata),
            preview=preview,
        )

    def _build_index_prefix(self, metadata: dict, context: str) -> str:
        section = metadata.get("section", "?")
        values = {
            "context": context.strip(),
            "company": metadata.get("company", "?"),
            "year": metadata.get("year", "?"),
            "report_type": metadata.get("report_type", "?"),
            "section": section,
            "section_path": metadata.get("section_path", section),
            "block_type": _context_block_type_label(metadata),
        }
        return "\n".join(
            str(template).format(**values)
            for template in CONTEXTUAL_INGEST_POLICY["index_prefix_templates"]
        )

    def _resolve_context_workers(self, max_workers: Optional[int], total: int) -> int:
        if total <= 0:
            return 1

        configured = max_workers or int(
            os.environ.get("CONTEXTUAL_INGEST_MAX_WORKERS", DEFAULT_CONTEXT_MAX_WORKERS)
        )
        return max(1, min(configured, total))

    def _resolve_context_batch_size(self, batch_size: Optional[int], workers: int) -> int:
        configured = batch_size or int(
            os.environ.get("CONTEXTUAL_INGEST_BATCH_SIZE", DEFAULT_CONTEXT_BATCH_SIZE)
        )
        return max(workers, configured)

    def _contextual_index_payload(self, chunks: List, contexts: Dict[int, str]) -> tuple[List[str], List[dict]]:
        total = len(chunks)
        texts = [
            f"{self._build_index_prefix(chunks[i].metadata, contexts[i])}\n\n{chunks[i].content}"
            for i in range(total)
        ]
        return texts, [chunk.metadata for chunk in chunks]

    def _context_generation_metrics(self) -> Dict[str, Any]:
        return {
            "prompt_chars": 0,
            "response_chars": 0,
            "fallback_count": 0,
            **zero_gemini_usage_counts(),
        }

    def _context_batch_responses(self, prompts: List[str], workers: int) -> List[Any]:
        try:
            return self.llm.batch(
                prompts,
                config={"max_concurrency": workers},
                return_exceptions=True,
            )
        except Exception as exc:
            logger.warning("Context batch generation failed, falling back to per-item mode: %s", exc)
            return [exc] * len(prompts)

    def _context_from_response(
        self,
        *,
        chunk: Any,
        response: Any,
        idx: int,
        metrics: Dict[str, Any],
        collect_usage: bool,
        log_item_failures: bool,
    ) -> str:
        if isinstance(response, Exception):
            if log_item_failures:
                logger.warning("Context generation failed for chunk %s: %s", idx, response)
            metrics["fallback_count"] += 1
            return self._fallback_context(chunk.metadata)
        content = getattr(response, "content", "") or ""
        context = content.strip() or self._fallback_context(chunk.metadata)
        if collect_usage:
            add_gemini_usage_counts(metrics, extract_gemini_usage_counts(response))
        return context

    def _generate_contexts_for_chunks(
        self,
        chunks: List,
        *,
        workers: int,
        request_batch_size: int,
        on_progress=None,
        collect_usage: bool = False,
        log_item_failures: bool = False,
    ) -> tuple[Dict[int, str], Dict[str, Any]]:
        total = len(chunks)
        contexts: Dict[int, str] = {}
        metrics = self._context_generation_metrics()
        completed_count = 0
        for start in range(0, total, request_batch_size):
            batch_items = list(enumerate(chunks[start : start + request_batch_size], start=start))
            prompts = [self._build_context_prompt(chunk.content, chunk.metadata) for _, chunk in batch_items]
            metrics["prompt_chars"] += sum(len(prompt) for prompt in prompts)
            responses = self._context_batch_responses(prompts, workers)

            for (idx, chunk), response in zip(batch_items, responses):
                contexts[idx] = self._context_from_response(
                    chunk=chunk,
                    response=response,
                    idx=idx,
                    metrics=metrics,
                    collect_usage=collect_usage,
                    log_item_failures=log_item_failures,
                )
                metrics["response_chars"] += len(contexts[idx])
                completed_count += 1
                if on_progress:
                    on_progress(completed_count, total)
        return contexts, metrics

    def contextual_ingest(
        self,
        chunks: List,
        on_progress=None,
        max_workers: Optional[int] = None,
        batch_size: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Index chunks with contextual retrieval and parent-child storage."""
        if not chunks:
            logger.warning("[contextual_ingest] chunks are empty.")
            return {
                "mode": "contextual",
                "chunks": 0,
                "stored_parent_chunks": 0,
                "api_calls": 0,
                "fallback_count": 0,
                "prompt_chars": 0,
                "response_chars": 0,
                **zero_gemini_usage_counts(),
                "max_workers": 0,
                "batch_size": 0,
                "elapsed_sec": 0.0,
            }

        from src.processing.financial_parser import FinancialParser

        parents = FinancialParser.build_parents(chunks)
        self.vsm.add_parents(parents)
        logger.info("[contextual_ingest] stored %s parent chunks", len(parents))

        total = len(chunks)
        workers = self._resolve_context_workers(max_workers, total)
        request_batch_size = self._resolve_context_batch_size(batch_size, workers)

        logger.info(
            "[contextual_ingest] generating contexts with max_workers=%s batch_size=%s",
            workers,
            request_batch_size,
        )

        contexts, _ = self._generate_contexts_for_chunks(
            chunks,
            workers=workers,
            request_batch_size=request_batch_size,
            on_progress=on_progress,
            log_item_failures=True,
        )
        texts, metadatas = self._contextual_index_payload(chunks, contexts)
        self.vsm.add_documents(texts, metadatas)
        logger.info("[contextual_ingest] indexed %s contextualized chunks", total)
        return {
            "mode": "contextual",
            "chunks": total,
            "stored_parent_chunks": len(parents),
            "api_calls": total,
            "fallback_count": 0,
            "prompt_chars": 0,
            "response_chars": 0,
            **zero_gemini_usage_counts(),
            "max_workers": workers,
            "batch_size": request_batch_size,
            "elapsed_sec": 0.0,
        }

    def benchmark_contextual_ingest(
        self,
        chunks: List,
        on_progress=None,
        on_store_progress=None,
        max_workers: Optional[int] = None,
        batch_size: Optional[int] = None,
        resume_partial_store: bool = False,
        resume_batch_size: int = 64,
        return_artifacts: bool = False,
    ) -> Dict[str, Any]:
        """Contextual ingest variant that returns timing and usage metrics."""
        if not chunks:
            return {
                "mode": "contextual",
                "chunks": 0,
                "stored_parent_chunks": 0,
                "api_calls": 0,
                "fallback_count": 0,
                "prompt_chars": 0,
                "response_chars": 0,
                **zero_gemini_usage_counts(),
                "max_workers": 0,
                "batch_size": 0,
                "elapsed_sec": 0.0,
            }

        from src.processing.financial_parser import FinancialParser

        started_at = time.perf_counter()
        parents = FinancialParser.build_parents(chunks)
        self.vsm.add_parents(parents)

        total = len(chunks)
        workers = self._resolve_context_workers(max_workers, total)
        request_batch_size = self._resolve_context_batch_size(batch_size, workers)

        logger.info(
            "[benchmark_contextual_ingest] generating contexts with max_workers=%s batch_size=%s",
            workers,
            request_batch_size,
        )

        contexts, context_metrics = self._generate_contexts_for_chunks(
            chunks,
            workers=workers,
            request_batch_size=request_batch_size,
            on_progress=on_progress,
            collect_usage=True,
        )
        texts, metadatas = self._contextual_index_payload(chunks, contexts)
        add_metrics = self.vsm.add_documents(
            texts,
            metadatas,
            resume=resume_partial_store,
            batch_size=resume_batch_size,
            on_progress=on_store_progress,
        )

        result = {
            "mode": "contextual",
            "chunks": total,
            "stored_parent_chunks": len(parents),
            "api_calls": total,
            **context_metrics,
            "max_workers": workers,
            "batch_size": request_batch_size,
            "elapsed_sec": time.perf_counter() - started_at,
            "resume_enabled": bool(add_metrics.get("resume_enabled", False)),
            "resume_added_chunks": int(add_metrics.get("added_chunks", 0) or 0),
            "resume_skipped_chunks": int(add_metrics.get("skipped_chunks", 0) or 0),
            "resume_batch_count": int(add_metrics.get("batch_count", 0) or 0),
        }
        if return_artifacts:
            result["artifacts"] = {
                "texts": texts,
                "metadatas": metadatas,
                "parents": parents,
            }
        return result
