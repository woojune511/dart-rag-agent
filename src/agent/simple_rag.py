"""One scoped search and one structured answer; no planning or compilation."""

from copy import deepcopy
import json
import math
from time import perf_counter
from urllib.parse import quote

from src.agent.financial_run_observation import observe_financial_run
from src.agent.financial_run_result import FINANCIAL_RUN_RESULT_SCHEMA_VERSION, FinancialRunResultV1
from src.config.simple_rag import (
    ANSWER_INSTRUCTIONS, MAX_CONTEXT_BYTES, NO_EVIDENCE_ANSWER, SOURCE_CONTEXT_FIELDS, RagAnswer,
)
from src.storage.bm25_index import metadata_matches_filter
from src.storage.report_scope_filter import report_scope_filter
from src.utils.chat_model_routes import ChatModelRoutes
from src.utils.gemini_usage import GeminiUsageCallbackHandler
from src.utils.request_diagnostics import diagnostic_location, record_diagnostic


def _encoded(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False, separators=(",", ":"))


def _caption_bundles(hits, store, limit):
    """Attach only explicitly validated stored sources, preserving all seed hits."""
    lookup = getattr(store, "get_table_caption_doc", None)
    if not callable(lookup):
        return hits, []
    expanded, bindings = [], []
    for doc, score in hits:
        caption = lookup(doc)
        if caption is not None:
            if (not caption.metadata.get("chunk_uid")
                    or caption.metadata.get("chunk_uid") == doc.metadata.get("chunk_uid")
                    or caption.metadata.get("rcept_no") != doc.metadata.get("rcept_no")
                    or not caption.page_content.strip()):
                raise ValueError("Invalid bound caption source")
            # Attachment lookup is not a relevance ranking. Public observations
            # render this score as None, rather than inventing a search score.
            expanded.append((caption, math.nan))
            bindings.append({"document_id": doc.metadata.get("rcept_no"),
                             "table_chunk_id": doc.metadata.get("chunk_uid"),
                             "caption_chunk_id": caption.metadata["chunk_uid"]})
        expanded.append((doc, score))
    if bindings:
        identities = set()
        for doc, _ in expanded:
            meta = doc.metadata
            document = next((meta[k] for k in ("rcept_no", "document_id", "source_document_id")
                             if isinstance(meta.get(k), str) and meta[k].strip()), "")
            chunk = next((meta[k] for k in ("chunk_uid", "id")
                          if isinstance(meta.get(k), str) and meta[k].strip()), "")
            if document and chunk and doc.page_content.strip():
                identities.add((document, chunk))
        if len(identities) > limit:
            record_diagnostic("caption_bundle_rejected", {"reason": "source_count_limit", "limit": limit})
            raise ValueError("Whole caption bundle exceeds source count limit")
    return expanded, bindings


class SimpleRagAgent(ChatModelRoutes):
    """Application QA entry point. The compiled workflow is an explicit comparison."""

    def __init__(self, vector_store_manager, k=8, routing_config=None, *, max_context_bytes=MAX_CONTEXT_BYTES):
        if type(k) is not int or not 1 <= k <= 32:
            raise ValueError("Search size must be between 1 and 32")
        if type(max_context_bytes) is not int or max_context_bytes <= 0:
            raise ValueError("Context byte limit must be positive")
        self.vsm, self.k, self.max_context_bytes = vector_store_manager, k, max_context_bytes
        routes = deepcopy((routing_config or {}).get("llm_routes") or {})
        # Application construction never initializes an unused Compiler client.
        routes = {key: value for key, value in routes.items() if key in {"default", "context_generation"}}
        routes.setdefault("default", {})
        for spec in routes.values():
            spec["provider_client_retries"] = 0
        self.routing_config = {"llm_routes": routes}
        self.llm_usage_callback = GeminiUsageCallbackHandler()
        self.llm_routes = self._build_llm_routes()
        self.llm = self.llm_routes["default"]

    @observe_financial_run
    def run(self, query, *, report_scope=None, include_review_trace=False, include_debug_bundle=False):
        self.llm_usage_callback.reset_current_thread()
        reset = getattr(self.vsm, "reset_current_thread_embedding_usage", None)
        if callable(reset):
            reset()
        if not isinstance(query, str) or not query.strip():
            raise ValueError("Question must be nonempty")
        scope = deepcopy(report_scope if report_scope is not None else {})
        if not isinstance(scope, dict):
            raise ValueError("Report scope must be an object")
        where = report_scope_filter(scope)
        start = perf_counter()
        packet = {"query": query, "report_scope": scope, "documents": []}
        if len(_encoded(packet).encode("utf-8")) > self.max_context_bytes:
            raise ValueError("Question and scope exceed the context byte limit")
        with diagnostic_location(phase="retrieval"):
            record_diagnostic("phase_started", {})
            hits = self.vsm.search(query, k=self.k, where_filter=deepcopy(where))
            hits, caption_bindings = _caption_bundles(hits[:self.k], self.vsm, self.k)
            sources, seen, omitted = [], {}, []
            for doc, score in hits:
                meta = deepcopy(doc.metadata)
                if not metadata_matches_filter(meta, where):
                    raise ValueError("Search returned a source outside the caller scope")
                document_id = next((meta.get(key) for key in ("rcept_no", "document_id", "source_document_id")
                                    if isinstance(meta.get(key), str) and meta[key].strip()), "")
                chunk_id = next((meta.get(key) for key in ("chunk_uid", "id")
                                if isinstance(meta.get(key), str) and meta[key].strip()), "")
                if not document_id or not chunk_id or not doc.page_content.strip():
                    omitted.append({"reason": "missing_source_identity_or_text"})
                    continue
                source_id = quote(document_id, safe="") + ":" + quote(chunk_id, safe="")
                source = {"source_id": source_id, "document_id": document_id, "chunk_id": chunk_id,
                          "text": doc.page_content,
                          "context": {key: meta[key] for key in SOURCE_CONTEXT_FIELDS if key in meta}}
                if source_id in seen:
                    if seen[source_id] != source:
                        raise ValueError("Conflicting content for the same source identity")
                    continue
                seen[source_id] = source
                proposed = {**packet, "documents": [*packet["documents"], source]}
                if len(_encoded(proposed).encode("utf-8")) > self.max_context_bytes:
                    if caption_bindings:
                        record_diagnostic("caption_bundle_rejected", {"reason": "context_byte_limit",
                                                                      "limit": self.max_context_bytes})
                        raise ValueError("Whole caption bundle exceeds context byte limit")
                    omitted.append({"source_id": source_id, "reason": "context_byte_limit"})
                    continue
                packet = proposed
                sources.append({**source, "score": float(score) if math.isfinite(float(score)) else None})
            telemetry = deepcopy(getattr(self.vsm, "last_search_telemetry", {}) or {})
            retrieval_trace = {"query_bundle": [query], "where_filter": where, "k": self.k,
                               "selected_source_ids": [row["source_id"] for row in sources],
                               "omitted": omitted, "context_bytes": len(_encoded(packet).encode("utf-8")),
                               "context_byte_limit": self.max_context_bytes, "search": telemetry}
            if caption_bindings:
                retrieval_trace["caption_bundles"] = caption_bindings
            record_diagnostic("phase_completed", {"retrieval_debug_trace": retrieval_trace})
        retrieval_seconds = perf_counter() - start
        answer_started = perf_counter()
        if sources:
            with diagnostic_location(phase="simple_rag"):
                record_diagnostic("phase_started", {})
                raw = self._llm_for_phase("simple_rag").with_structured_output(RagAnswer).invoke(
                    [("system", ANSWER_INSTRUCTIONS), ("human", _encoded(packet))])
                answer = RagAnswer.model_validate(raw)
                if not answer.answer.strip():
                    raise ValueError("Answer must be nonempty")
                visible = {row["source_id"] for row in sources}
                if any(key not in visible for key in answer.cited_source_ids):
                    raise ValueError("Answer cites a source not supplied to the model")
                if not answer.abstained and not answer.cited_source_ids:
                    raise ValueError("A non-abstained answer must cite retrieved evidence")
                record_diagnostic("phase_completed", {"source_ids_valid": True, "abstained": answer.abstained})
        else:
            answer = RagAnswer(answer=NO_EVIDENCE_ANSWER, cited_source_ids=[], abstained=True)
        cited = list(dict.fromkeys(answer.cited_source_ids))
        mode = telemetry.get("cached_retrieval_mode") if telemetry.get("retrieval_mode") == "cache" else telemetry.get("retrieval_mode")
        retrieval_status = {"degraded": mode in {"bm25_only", "bm25_fallback"}, "retrieval_mode": mode}
        public = {"query": query, "report_scope": scope, "query_type": "qa", "workflow": "simple_rag",
                  "companies": list(dict.fromkeys(row["context"]["company"] for row in sources if row["context"].get("company"))),
                  "years": list(dict.fromkeys(int(row["context"]["year"]) for row in sources if str(row["context"].get("year", "")).isdigit())),
                  "answer": answer.answer, "citations": cited, "abstained": answer.abstained,
                  "cited_sources": [deepcopy(row) for row in sources if row["source_id"] in cited],
                  "validation": {"source_ids": "passed" if cited else "not_applicable",
                                 "source_scope": "passed" if where else "not_applicable", "semantic_support": "not_checked",
                                 "arithmetic": "not_executed", "output_coverage": "not_checked"},
                  "structured_result": {}, "resolved_calculation_trace": {}, "retrieval_status": retrieval_status}
        review = {"retrieved_sources": deepcopy(sources), "retrieval_debug_trace": retrieval_trace} if include_review_trace else None
        embedding = getattr(self.vsm, "get_current_thread_embedding_usage_snapshot", None)
        debug = {"llm_usage": self.llm_usage_callback.snapshot_current_thread(),
                 "llm_usage_by_phase": self.llm_usage_callback.snapshot_current_thread_by_phase(),
                 "embedding_usage": embedding() if callable(embedding) else None,
                 "timings_seconds": {"retrieval": retrieval_seconds, "answer": perf_counter() - answer_started,
                                     "total": perf_counter() - start}} if include_debug_bundle else None
        return FinancialRunResultV1(FINANCIAL_RUN_RESULT_SCHEMA_VERSION, public, review, debug)
