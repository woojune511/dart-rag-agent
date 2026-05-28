import json
import logging
import os
import re
import time
from collections import OrderedDict
from pathlib import Path
from typing import Any, Dict, Hashable, List, Optional, Tuple

from dotenv import load_dotenv
from langchain_community.vectorstores import Chroma
from langchain_core.documents import Document
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_openai import OpenAIEmbeddings

logger = logging.getLogger(__name__)

load_dotenv()

DEFAULT_EMBEDDING_PROVIDER = os.getenv("DART_EMBEDDING_PROVIDER", "").strip().lower() or (
    "google" if os.getenv("GOOGLE_API_KEY") else "openai" if os.getenv("OPENAI_API_KEY") else "huggingface"
)
DEFAULT_GOOGLE_EMBEDDING_MODEL = os.getenv("GOOGLE_EMBEDDING_MODEL", "models/gemini-embedding-2")
DEFAULT_OPENAI_EMBEDDING_MODEL = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-large")
DEFAULT_HUGGINGFACE_EMBEDDING_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
DEFAULT_EMBEDDING_MODEL = (
    DEFAULT_GOOGLE_EMBEDDING_MODEL
    if DEFAULT_EMBEDDING_PROVIDER == "google"
    else DEFAULT_OPENAI_EMBEDDING_MODEL
    if DEFAULT_EMBEDDING_PROVIDER == "openai"
    else DEFAULT_HUGGINGFACE_EMBEDDING_MODEL
)
DEFAULT_COLLECTION_NAME = "dart_reports_v2"
DEFAULT_CHROMA_HNSW_BATCH_SIZE = int(os.getenv("DART_CHROMA_HNSW_BATCH_SIZE", "100") or 100)
DEFAULT_CHROMA_HNSW_SYNC_THRESHOLD = int(os.getenv("DART_CHROMA_HNSW_SYNC_THRESHOLD", "100000") or 100000)

_KNOWN_EMBEDDING_DIMENSIONS = {
    ("google", "models/gemini-embedding-2"): 3072,
    ("google", "models/text-embedding-004"): 768,
    ("openai", "text-embedding-3-large"): 3072,
    ("openai", "text-embedding-3-small"): 1536,
    ("openai", "text-embedding-ada-002"): 1536,
    ("huggingface", "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"): 384,
}

_CHROMA_METADATA_MAX_STRING_LEN = int(os.getenv("DART_CHROMA_METADATA_MAX_STRING_LEN", "8192") or 8192)
_CHROMA_METADATA_DROP_KEYS = frozenset(
    {
        "table_object_json",
        "table_row_records_json",
        "table_value_records_json",
    }
)


def infer_embedding_dimension(
    provider: Optional[str] = None,
    model_name: Optional[str] = None,
) -> Optional[int]:
    selected_provider = (provider or DEFAULT_EMBEDDING_PROVIDER).strip().lower()
    selected_model = (model_name or DEFAULT_EMBEDDING_MODEL).strip()
    override = os.getenv("DART_EMBEDDING_DIMENSION", "").strip()
    if override:
        try:
            return int(override)
        except ValueError:
            logger.warning("Ignoring invalid DART_EMBEDDING_DIMENSION=%r", override)
    return _KNOWN_EMBEDDING_DIMENSIONS.get((selected_provider, selected_model))


def get_embedding_runtime_spec(
    provider: Optional[str] = None,
    model_name: Optional[str] = None,
) -> Dict[str, Any]:
    selected_provider = (provider or DEFAULT_EMBEDDING_PROVIDER).strip().lower()
    selected_model = (model_name or DEFAULT_EMBEDDING_MODEL).strip()
    return {
        "provider": selected_provider,
        "model_name": selected_model,
        "dimension": infer_embedding_dimension(selected_provider, selected_model),
    }


def create_embeddings(
    provider: Optional[str] = None,
    model_name: Optional[str] = None,
) -> Any:
    selected_provider = (provider or DEFAULT_EMBEDDING_PROVIDER).strip().lower()
    selected_model = (model_name or DEFAULT_EMBEDDING_MODEL).strip()

    if selected_provider == "google":
        if not os.getenv("GOOGLE_API_KEY"):
            raise ValueError("GOOGLE_API_KEY is required for Google API embeddings.")
        return GoogleGenerativeAIEmbeddings(
            model=selected_model or DEFAULT_GOOGLE_EMBEDDING_MODEL,
            google_api_key=os.getenv("GOOGLE_API_KEY"),
        )

    if selected_provider == "openai":
        if not os.getenv("OPENAI_API_KEY"):
            raise ValueError("OPENAI_API_KEY is required for OpenAI API embeddings.")
        return OpenAIEmbeddings(
            model=selected_model or DEFAULT_OPENAI_EMBEDDING_MODEL,
            api_key=os.getenv("OPENAI_API_KEY"),
        )

    if selected_provider == "huggingface":
        return HuggingFaceEmbeddings(model_name=selected_model or DEFAULT_HUGGINGFACE_EMBEDDING_MODEL)

    raise ValueError(
        f"Unsupported embedding provider: {selected_provider}. "
        "Use one of: google, openai, huggingface."
    )


def _tokenize_ko(text: str) -> List[str]:
    """Tokenize Korean with character bigrams plus ASCII word tokens."""
    tokens: List[str] = []
    for segment in re.findall(r"[가-힣]+|[a-zA-Z0-9]+", text):
        if re.fullmatch(r"[가-힣]+", segment):
            if len(segment) == 1:
                tokens.append(segment)
            else:
                tokens.extend(segment[i : i + 2] for i in range(len(segment) - 1))
        else:
            tokens.append(segment.lower())
    return tokens


def _doc_identity(doc: Document) -> str:
    metadata = getattr(doc, "metadata", {}) or {}
    return (
        metadata.get("chunk_uid")
        or metadata.get("id")
        or "|".join(
            str(metadata.get(key, ""))
            for key in ("rcept_no", "chunk_id", "sub_chunk_idx", "company", "year", "section_path")
        )
        or doc.page_content
    )


def _chunk_uid_from_metadata(metadata: Dict[str, Any]) -> str:
    return str(
        metadata.get("chunk_uid")
        or metadata.get("id")
        or "|".join(
            str(metadata.get(key, ""))
            for key in ("rcept_no", "chunk_id", "sub_chunk_idx", "company", "year", "section_path")
        )
    )


def _metadata_for_chroma(metadata: Dict[str, Any]) -> Dict[str, Any]:
    """Return bounded metadata for Chroma's sqlite metadata table."""
    sanitized: Dict[str, Any] = {}
    for key, value in dict(metadata or {}).items():
        if key in _CHROMA_METADATA_DROP_KEYS or value is None:
            continue
        if isinstance(value, (str, int, float, bool)):
            sanitized[key] = value[:_CHROMA_METADATA_MAX_STRING_LEN] if isinstance(value, str) else value
            continue
        if isinstance(value, (list, tuple, set)):
            joined = " | ".join(str(item).strip() for item in value if str(item).strip())
            if joined:
                sanitized[key] = joined[:_CHROMA_METADATA_MAX_STRING_LEN]
            continue
        if isinstance(value, dict):
            compact_json = json.dumps(value, ensure_ascii=False)
            if len(compact_json) <= _CHROMA_METADATA_MAX_STRING_LEN:
                sanitized[key] = compact_json
    return sanitized


def _metadata_matches_filter(metadata: Dict[str, Any], where_filter: Optional[dict]) -> bool:
    if not where_filter:
        return True

    if "$and" in where_filter:
        return all(_metadata_matches_filter(metadata, clause) for clause in where_filter["$and"])

    for key, expected in where_filter.items():
        actual = metadata.get(key)
        if isinstance(expected, dict):
            if "$in" in expected:
                expected_values = expected["$in"]
                if actual not in expected_values and str(actual) not in {str(value) for value in expected_values}:
                    return False
            else:
                return False
        else:
            if actual != expected and str(actual) != str(expected):
                return False
    return True


def _is_embedding_capacity_error(exc: Exception) -> bool:
    message = str(exc or "").lower()
    markers = (
        "resource_exhausted",
        "429",
        "rate limit",
        "quota",
        "error embedding content",
        "embed_query",
    )
    return any(marker in message for marker in markers)


def _is_vector_store_read_error(exc: Exception) -> bool:
    message = str(exc or "").lower()
    markers = (
        "error loading hnsw index",
        "hnsw",
        "segment reader",
        "backfill request to compactor",
        "constructing hnsw segment reader",
    )
    return any(marker in message for marker in markers)


def _is_transient_vector_add_error(exc: Exception) -> bool:
    message = str(exc or "").lower()
    markers = (
        "503",
        "unavailable",
        "service is currently unavailable",
        "servererror",
        "resource_exhausted",
        "429",
        "rate limit",
        "quota",
        "error embedding content",
    )
    return any(marker in message for marker in markers)


def _freeze_filter(where_filter: Optional[dict]) -> Hashable:
    if where_filter is None:
        return ()
    if isinstance(where_filter, dict):
        return tuple(sorted((str(key), _freeze_filter(value)) for key, value in where_filter.items()))
    if isinstance(where_filter, list):
        return tuple(_freeze_filter(item) for item in where_filter)
    return where_filter


class VectorStoreManager:
    def __init__(
        self,
        persist_directory: str = "data/chroma_db",
        collection_name: str = DEFAULT_COLLECTION_NAME,
        embedding_provider: str = DEFAULT_EMBEDDING_PROVIDER,
        embedding_model_name: str = DEFAULT_EMBEDDING_MODEL,
        allow_query_embedding_fallback: bool = True,
    ):
        self.persist_directory = persist_directory
        os.makedirs(self.persist_directory, exist_ok=True)
        self.collection_name = collection_name
        self.embedding_provider = embedding_provider
        self.embedding_model_name = embedding_model_name
        self.allow_query_embedding_fallback = bool(allow_query_embedding_fallback)
        self.vector_capacity_cooldown_sec = max(0.0, float(os.getenv("DART_VECTOR_CAPACITY_COOLDOWN_SEC", "90") or 90))
        self.search_cache_size = max(0, int(os.getenv("DART_RETRIEVAL_SEARCH_CACHE_SIZE", "256") or 256))
        self.vector_add_max_retries = max(1, int(os.getenv("DART_VECTOR_ADD_MAX_RETRIES", "4") or 4))
        self.vector_add_retry_sleep_sec = max(0.0, float(os.getenv("DART_VECTOR_ADD_RETRY_SLEEP_SEC", "3") or 3))
        self.chroma_hnsw_batch_size = max(1, DEFAULT_CHROMA_HNSW_BATCH_SIZE)
        self.chroma_hnsw_sync_threshold = max(self.chroma_hnsw_batch_size, DEFAULT_CHROMA_HNSW_SYNC_THRESHOLD)
        self._vector_capacity_cooldown_until = 0.0
        self._search_cache: "OrderedDict[Tuple[str, int, int, Hashable], List[Tuple[Document, float]]]" = OrderedDict()
        self.embedding_spec = get_embedding_runtime_spec(
            provider=self.embedding_provider,
            model_name=self.embedding_model_name,
        )

        logger.info(
            "Loading %s embeddings (%s). A full reindex is recommended when this model changes.",
            self.embedding_provider,
            self.embedding_model_name,
        )
        self.embeddings = create_embeddings(
            provider=self.embedding_provider,
            model_name=self.embedding_model_name,
        )

        self.vector_store = Chroma(
            collection_name=self.collection_name,
            embedding_function=self.embeddings,
            persist_directory=self.persist_directory,
            collection_metadata={
                "hnsw:batch_size": self.chroma_hnsw_batch_size,
                "hnsw:sync_threshold": self.chroma_hnsw_sync_threshold,
            },
        )
        logger.info("Initialized ChromaDB at %s (collection=%s)", self.persist_directory, self.collection_name)

        # Parent chunk store — persisted as JSON alongside the ChromaDB directory
        self._parents_path = Path(self.persist_directory) / "parents.json"
        self._parents: Dict[str, str] = self._load_parents()
        self._graph_path = Path(self.persist_directory) / "document_structure_graph.json"
        self._structure_graph: Dict[str, Any] = self._load_structure_graph()

        self.bm25 = None
        self.bm25_docs: List[str] = []
        self.bm25_metadatas: List[dict] = []
        self._init_bm25()

    def in_capacity_cooldown(self) -> bool:
        return time.time() < float(getattr(self, "_vector_capacity_cooldown_until", 0.0) or 0.0)

    def _open_capacity_cooldown(self, exc: Exception) -> None:
        if self.vector_capacity_cooldown_sec <= 0:
            return
        self._vector_capacity_cooldown_until = time.time() + self.vector_capacity_cooldown_sec
        logger.warning(
            "Vector embedding capacity error detected; disabling vector search for %.1fs: %s",
            self.vector_capacity_cooldown_sec,
            exc,
        )

    def _search_cache_key(
        self,
        query: str,
        *,
        k: int,
        k_rrf: int,
        where_filter: Optional[dict],
    ) -> Tuple[str, int, int, Hashable]:
        normalized_query = " ".join(str(query or "").split())
        return (normalized_query, int(k), int(k_rrf), _freeze_filter(where_filter))

    def _get_cached_search(self, key: Tuple[str, int, int, Hashable]) -> Optional[List[Tuple[Document, float]]]:
        cache = getattr(self, "_search_cache", None)
        if not cache:
            return None
        cached = cache.get(key)
        if cached is None:
            return None
        cache.move_to_end(key)
        return list(cached)

    def _store_cached_search(self, key: Tuple[str, int, int, Hashable], results: List[Tuple[Document, float]]) -> None:
        if self.search_cache_size <= 0:
            return
        cache = getattr(self, "_search_cache", None)
        if cache is None:
            self._search_cache = OrderedDict()
            cache = self._search_cache
        cache[key] = list(results)
        cache.move_to_end(key)
        while len(cache) > self.search_cache_size:
            cache.popitem(last=False)

    def persist(self) -> None:
        persist = getattr(self.vector_store, "persist", None)
        if not callable(persist):
            return
        try:
            persist()
        except Exception as exc:
            logger.warning("Failed to explicitly persist vector store: %s", exc)

    def _init_bm25(self):
        docs: List[str] = []
        metadatas: List[dict] = []
        docs, metadatas = self._structure_graph_bm25_payload()
        if docs:
            self._build_bm25_index(docs, metadatas)
            logger.info("Initialized BM25 index from structure graph with %s documents.", len(self.bm25_docs))
            return

        try:
            payload = self.vector_store.get()
            docs = list(payload.get("documents") or []) if payload else []
            metadatas = list(payload.get("metadatas") or []) if payload else []
        except Exception as e:
            logger.warning("Could not initialize BM25 from Chroma collection: %s", e)

        if docs:
            self._build_bm25_index(docs, metadatas)
            logger.info("Initialized BM25 index with %s documents.", len(self.bm25_docs))
            return

        self.bm25 = None
        self.bm25_docs = []
        self.bm25_metadatas = []

    def validate_vector_index(self, *, query: Optional[str] = None, where_filter: Optional[dict] = None) -> Dict[str, Any]:
        """Probe whether the persisted vector index can serve vector search.

        This intentionally bypasses BM25 fallback so official eval-only runs can
        fail before spending time on answer generation when the vector index is
        unreadable.
        """
        probe = (query or "").strip()
        if not probe:
            for doc in self.bm25_docs:
                probe = str(doc or "").strip()
                if probe:
                    break
        if not probe:
            probe = "vector store health check"
        probe = " ".join(probe.split())[:500]

        try:
            results = self.vector_store.similarity_search_with_score(
                probe,
                k=1,
                filter=where_filter,
            )
        except Exception as exc:
            return {
                "ok": False,
                "error": str(exc),
                "embedding_capacity_error": _is_embedding_capacity_error(exc),
                "vector_store_read_error": _is_vector_store_read_error(exc),
                "probe_query": probe,
            }

        return {
            "ok": bool(results),
            "result_count": len(results or []),
            "probe_query": probe,
        }

    def _build_bm25_index(self, docs: List[str], metadatas: List[dict]) -> None:
        from rank_bm25 import BM25Okapi

        tokenized_corpus = [_tokenize_ko(doc) for doc in docs]
        self.bm25 = BM25Okapi(tokenized_corpus)
        self.bm25_docs = list(docs)
        self.bm25_metadatas = list(metadatas or [{} for _ in docs])

    def _structure_graph_bm25_payload(self) -> tuple[List[str], List[dict]]:
        nodes = dict((self._structure_graph or {}).get("nodes", {}) or {})
        if not nodes:
            return [], []

        ordered_nodes = sorted(
            nodes.values(),
            key=lambda node: (
                str((node.get("metadata") or {}).get("rcept_no") or ""),
                int(node.get("chunk_id", 0) or 0),
                int(node.get("sub_chunk_idx", 0) or 0),
                str(node.get("chunk_uid") or ""),
            ),
        )
        docs: List[str] = []
        metadatas: List[dict] = []
        for node in ordered_nodes:
            text = str(node.get("text") or "").strip()
            metadata = dict(node.get("metadata") or {})
            if not text:
                continue
            docs.append(text)
            metadatas.append(metadata)
        return docs, metadatas

    def _hydrate_document_from_structure_graph(self, doc: Document) -> Document:
        metadata = dict(getattr(doc, "metadata", {}) or {})
        chunk_uid = _chunk_uid_from_metadata(metadata)
        if not chunk_uid:
            return doc
        node = ((self._structure_graph or {}).get("nodes", {}) or {}).get(chunk_uid)
        if not node:
            return doc
        hydrated_metadata = dict(metadata)
        hydrated_metadata.update(dict((node.get("metadata") or {})))
        text = str(node.get("text") or doc.page_content or "")
        return Document(page_content=text, metadata=hydrated_metadata)

    # ------------------------------------------------------------------
    # Parent chunk storage
    # ------------------------------------------------------------------

    def _load_parents(self) -> Dict[str, str]:
        if self._parents_path.exists():
            try:
                return json.loads(self._parents_path.read_text(encoding="utf-8"))
            except Exception as e:
                logger.warning("Failed to load parents.json: %s", e)
        return {}

    def _save_parents(self) -> None:
        try:
            self._parents_path.write_text(
                json.dumps(self._parents, ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception as e:
            logger.warning("Failed to save parents.json: %s", e)

    def _load_structure_graph(self) -> Dict[str, Any]:
        if self._graph_path.exists():
            try:
                payload = json.loads(self._graph_path.read_text(encoding="utf-8"))
                if isinstance(payload, dict):
                    return {
                        "nodes": dict(payload.get("nodes", {}) or {}),
                        "parents": dict(payload.get("parents", {}) or {}),
                        "sections": dict(payload.get("sections", {}) or {}),
                    }
            except Exception as e:
                logger.warning("Failed to load document_structure_graph.json: %s", e)
        return {"nodes": {}, "parents": {}, "sections": {}}

    def _save_structure_graph(self) -> None:
        try:
            self._graph_path.write_text(
                json.dumps(self._structure_graph, ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception as e:
            logger.warning("Failed to save document_structure_graph.json: %s", e)

    def _rebuild_structure_relationships(self) -> None:
        nodes = dict(self._structure_graph.get("nodes", {}) or {})
        grouped: Dict[str, List[Dict[str, Any]]] = {}

        for node in nodes.values():
            parent_id = str(node.get("parent_id") or "")
            if not parent_id:
                continue
            grouped.setdefault(parent_id, []).append(node)

        parents: Dict[str, List[str]] = {}
        sections: Dict[str, Dict[str, Any]] = {}
        for parent_id, items in grouped.items():
            ordered = sorted(
                items,
                key=lambda item: (
                    int(item.get("sub_chunk_idx", 0) or 0),
                    int(item.get("chunk_id", 0) or 0),
                ),
            )
            chunk_uids = [str(item.get("chunk_uid")) for item in ordered if item.get("chunk_uid")]
            parents[parent_id] = chunk_uids
            lead_paragraph_uid = None
            previous_paragraph_uid = None
            for index, item in enumerate(ordered):
                chunk_uid = str(item.get("chunk_uid") or "")
                if not chunk_uid:
                    continue
                prev_uid = chunk_uids[index - 1] if index > 0 else None
                next_uid = chunk_uids[index + 1] if index + 1 < len(chunk_uids) else None
                nodes[chunk_uid]["sibling_prev_uid"] = prev_uid
                nodes[chunk_uid]["sibling_next_uid"] = next_uid
                block_type = str((item.get("metadata") or {}).get("block_type") or item.get("metadata", {}).get("is_table") and "table" or "")
                if block_type != "table":
                    previous_paragraph_uid = chunk_uid
                    if lead_paragraph_uid is None:
                        lead_paragraph_uid = chunk_uid
                elif previous_paragraph_uid:
                    nodes[chunk_uid]["described_by_uid"] = previous_paragraph_uid
                    described_node = nodes.get(previous_paragraph_uid)
                    if described_node:
                        described_node.setdefault("describes_table_uids", [])
                        if chunk_uid not in described_node["describes_table_uids"]:
                            described_node["describes_table_uids"].append(chunk_uid)

            first_node = ordered[0] if ordered else {}
            first_metadata = dict(first_node.get("metadata", {}) or {})
            sections[parent_id] = {
                "parent_id": parent_id,
                "section_path": first_metadata.get("section_path"),
                "section": first_metadata.get("section"),
                "lead_paragraph_uid": lead_paragraph_uid,
                "chunk_uids": chunk_uids,
            }

        self._structure_graph = {"nodes": nodes, "parents": parents, "sections": sections}

    def _update_structure_graph(self, chunks: List[str], metadatas: List[dict]) -> None:
        nodes = dict(self._structure_graph.get("nodes", {}) or {})

        for text, metadata in zip(chunks, metadatas):
            metadata = dict(metadata or {})
            chunk_uid = str(
                metadata.get("chunk_uid")
                or metadata.get("id")
                or "|".join(
                    str(metadata.get(key, ""))
                    for key in ("rcept_no", "chunk_id", "sub_chunk_idx", "company", "year", "section_path")
                )
            )
            if not chunk_uid:
                continue

            nodes[chunk_uid] = {
                "chunk_uid": chunk_uid,
                "text": text,
                "metadata": metadata,
                "parent_id": metadata.get("parent_id"),
                "chunk_id": metadata.get("chunk_id"),
                "sub_chunk_idx": metadata.get("sub_chunk_idx", 0),
                "table_context": metadata.get("table_context"),
                "reference_parent_ids": list(metadata.get("reference_parent_ids", []) or []),
            }

        self._structure_graph["nodes"] = nodes
        self._rebuild_structure_relationships()
        self._save_structure_graph()

    def add_parents(self, parents: Dict[str, str]) -> None:
        """부모 청크 딕셔너리를 저장 (기존 항목에 병합)."""
        self._parents.update(parents)
        self._save_parents()
        logger.info("Stored %s parent chunks (total=%s).", len(parents), len(self._parents))

    def get_parent(self, parent_id: str) -> Optional[str]:
        """parent_id에 해당하는 섹션 전체 텍스트 반환. 없으면 None."""
        return self._parents.get(parent_id)

    def delete_parents_for_rcept(self, rcept_no: str) -> None:
        """특정 접수번호의 부모 청크를 모두 삭제."""
        prefix = f"{rcept_no}::"
        before = len(self._parents)
        self._parents = {k: v for k, v in self._parents.items() if not k.startswith(prefix)}
        self._save_parents()
        logger.info("Deleted %s parent chunks for rcept_no=%s.", before - len(self._parents), rcept_no)

        nodes = dict(self._structure_graph.get("nodes", {}) or {})
        filtered_nodes = {
            chunk_uid: node
            for chunk_uid, node in nodes.items()
            if str((node.get("metadata") or {}).get("rcept_no", "")) != str(rcept_no)
        }
        self._structure_graph["nodes"] = filtered_nodes
        self._rebuild_structure_relationships()
        self._save_structure_graph()

    # ------------------------------------------------------------------

    def is_indexed(self, rcept_no: str) -> bool:
        """Return whether the filing is already indexed."""
        try:
            result = self.vector_store.get(where={"rcept_no": rcept_no}, limit=1)
            return len(result.get("ids") or []) > 0
        except Exception:
            return False

    def list_indexed_chunk_uids(self, *, rcept_no: Optional[str] = None) -> set[str]:
        where_filter = {"rcept_no": rcept_no} if rcept_no else None
        try:
            result = self.vector_store.get(where=where_filter)
        except Exception:
            return set()

        indexed: set[str] = set()
        for metadata in result.get("metadatas") or []:
            if not isinstance(metadata, dict):
                continue
            chunk_uid = _chunk_uid_from_metadata(metadata)
            if chunk_uid:
                indexed.add(chunk_uid)
        return indexed

    def add_documents(
        self,
        chunks: List[str],
        metadatas: List[dict],
        *,
        resume: bool = False,
        batch_size: int = 64,
    ) -> Dict[str, Any]:
        """Add document chunks to the vector store."""
        if not chunks:
            logger.warning("No chunks provided to add_documents.")
            return {
                "requested_chunks": 0,
                "added_chunks": 0,
                "skipped_chunks": 0,
                "batch_count": 0,
                "resume_enabled": bool(resume),
            }

        if len(chunks) != len(metadatas):
            raise ValueError("chunks and metadatas must have the same length.")

        effective_batch_size = max(int(batch_size or 0), 1)
        prepared: List[tuple[str, dict, str]] = []
        seen_input_chunk_uids: set[str] = set()
        duplicate_input_count = 0
        for text, metadata in zip(chunks, metadatas):
            normalized_metadata = dict(metadata or {})
            chunk_uid = _chunk_uid_from_metadata(normalized_metadata)
            if chunk_uid and chunk_uid in seen_input_chunk_uids:
                duplicate_input_count += 1
                continue
            if chunk_uid:
                seen_input_chunk_uids.add(chunk_uid)
            prepared.append((text, normalized_metadata, chunk_uid))

        existing_chunk_uids: set[str] = set()
        if resume:
            rcept_nos = {
                str(metadata.get("rcept_no")).strip()
                for _, metadata, _ in prepared
                if str(metadata.get("rcept_no", "")).strip()
            }
            existing_chunk_uids = self.list_indexed_chunk_uids(rcept_no=next(iter(rcept_nos)) if len(rcept_nos) == 1 else None)

        pending = [
            (text, metadata, chunk_uid)
            for text, metadata, chunk_uid in prepared
            if not chunk_uid or chunk_uid not in existing_chunk_uids
        ]
        skipped_chunks = duplicate_input_count + (len(prepared) - len(pending))

        if not pending:
            logger.info(
                "Skipping add_documents because all %s chunks are already indexed (resume=%s).",
                len(prepared),
                resume,
            )
            return {
                "requested_chunks": len(chunks),
                "added_chunks": 0,
                "skipped_chunks": skipped_chunks,
                "batch_count": 0,
                "resume_enabled": bool(resume),
            }

        logger.info(
            "Adding %s/%s chunks to Vector DB in %s batch(es) (resume=%s, skipped=%s).",
            len(pending),
            len(chunks),
            (len(pending) + effective_batch_size - 1) // effective_batch_size,
            resume,
            skipped_chunks,
        )
        batch_count = 0
        for start in range(0, len(pending), effective_batch_size):
            batch = pending[start : start + effective_batch_size]
            batch_texts = [text for text, _, _ in batch]
            batch_metadatas = [metadata for _, metadata, _ in batch]
            chroma_metadatas = [_metadata_for_chroma(metadata) for metadata in batch_metadatas]
            max_attempts = max(1, int(getattr(self, "vector_add_max_retries", 1) or 1))
            for attempt in range(1, max_attempts + 1):
                try:
                    self.vector_store.add_texts(texts=batch_texts, metadatas=chroma_metadatas)
                    break
                except Exception as exc:
                    if attempt >= max_attempts or not _is_transient_vector_add_error(exc):
                        raise
                    sleep_sec = float(getattr(self, "vector_add_retry_sleep_sec", 0.0) or 0.0) * attempt
                    logger.warning(
                        "Transient vector add failure on batch %s/%s; retrying in %.1fs (attempt %s/%s): %s",
                        (start // effective_batch_size) + 1,
                        (len(pending) + effective_batch_size - 1) // effective_batch_size,
                        sleep_sec,
                        attempt,
                        max_attempts,
                        exc,
                    )
                    if sleep_sec > 0:
                        time.sleep(sleep_sec)
            self._update_structure_graph(batch_texts, batch_metadatas)
            batch_count += 1
        self.persist()
        self._init_bm25()
        logger.info("Successfully added documents and updated BM25 index.")
        return {
            "requested_chunks": len(chunks),
            "added_chunks": len(pending),
            "skipped_chunks": skipped_chunks,
            "batch_count": batch_count,
            "resume_enabled": bool(resume),
        }

    def get_structure_node(self, chunk_uid: str) -> Optional[Dict[str, Any]]:
        return (self._structure_graph.get("nodes", {}) or {}).get(chunk_uid)

    def get_section_lead_doc(self, parent_id: str, exclude_chunk_uid: Optional[str] = None) -> Optional[Document]:
        if not parent_id:
            return None
        section = (self._structure_graph.get("sections", {}) or {}).get(parent_id) or {}
        lead_uid = str(section.get("lead_paragraph_uid") or "")
        if not lead_uid or (exclude_chunk_uid and lead_uid == exclude_chunk_uid):
            return None
        node = self.get_structure_node(lead_uid)
        if not node:
            return None
        metadata = dict(node.get("metadata", {}) or {})
        metadata["graph_relation"] = "section_lead"
        metadata["graph_source_parent_id"] = parent_id
        return Document(page_content=str(node.get("text", "")), metadata=metadata)

    def get_described_by_doc(self, chunk_uid: str) -> Optional[Document]:
        node = self.get_structure_node(chunk_uid)
        if not node:
            return None
        described_by_uid = str(node.get("described_by_uid") or "")
        if not described_by_uid:
            return None
        paragraph_node = self.get_structure_node(described_by_uid)
        if not paragraph_node:
            return None
        metadata = dict(paragraph_node.get("metadata", {}) or {})
        metadata["graph_relation"] = "described_by_paragraph"
        metadata["graph_source_chunk_uid"] = chunk_uid
        return Document(page_content=str(paragraph_node.get("text", "")), metadata=metadata)

    def get_sibling_docs(self, parent_id: str, chunk_uid: str, window: int = 1) -> List[Document]:
        if not parent_id or not chunk_uid or window <= 0:
            return []

        parent_chunks = list((self._structure_graph.get("parents", {}) or {}).get(parent_id, []) or [])
        if chunk_uid not in parent_chunks:
            return []

        index = parent_chunks.index(chunk_uid)
        start = max(0, index - window)
        end = min(len(parent_chunks), index + window + 1)
        siblings: List[Document] = []

        for sibling_index in range(start, end):
            sibling_uid = parent_chunks[sibling_index]
            if sibling_uid == chunk_uid:
                continue
            node = self.get_structure_node(sibling_uid)
            if not node:
                continue
            metadata = dict(node.get("metadata", {}) or {})
            direction = "sibling_prev" if sibling_index < index else "sibling_next"
            metadata["graph_relation"] = direction
            metadata["graph_source_chunk_uid"] = chunk_uid
            siblings.append(Document(page_content=str(node.get("text", "")), metadata=metadata))

        return siblings

    def get_reference_docs(self, chunk_uid: str, limit: int = 4) -> List[Document]:
        node = self.get_structure_node(chunk_uid)
        if not node or limit <= 0:
            return []

        metadata = dict(node.get("metadata", {}) or {})
        source_parent_id = str(metadata.get("parent_id") or "")
        reference_parent_ids = [
            str(value).strip()
            for value in (metadata.get("reference_parent_ids") or node.get("reference_parent_ids") or [])
            if str(value).strip()
        ]
        if not reference_parent_ids:
            return []

        docs: List[Document] = []
        seen_parent_ids: set[str] = set()
        for reference_parent_id in reference_parent_ids:
            if reference_parent_id in seen_parent_ids or reference_parent_id == source_parent_id:
                continue
            seen_parent_ids.add(reference_parent_id)

            referenced_doc = self.get_section_lead_doc(parent_id=reference_parent_id, exclude_chunk_uid=None)
            if referenced_doc is None:
                section = (self._structure_graph.get("sections", {}) or {}).get(reference_parent_id) or {}
                chunk_uids = list(section.get("chunk_uids", []) or [])
                if not chunk_uids:
                    continue
                fallback_node = self.get_structure_node(str(chunk_uids[0]))
                if not fallback_node:
                    continue
                fallback_metadata = dict(fallback_node.get("metadata", {}) or {})
                referenced_doc = Document(
                    page_content=str(fallback_node.get("text", "")),
                    metadata=fallback_metadata,
                )

            ref_metadata = dict(referenced_doc.metadata or {})
            ref_metadata["graph_relation"] = "reference_note"
            ref_metadata["graph_source_chunk_uid"] = chunk_uid
            ref_metadata["graph_reference_parent_id"] = reference_parent_id
            docs.append(Document(page_content=referenced_doc.page_content, metadata=ref_metadata))

            if len(docs) >= limit:
                break

        return docs

    def search(self, query: str, k: int = 5, k_rrf: int = 60, where_filter: dict = None):
        """Perform Hybrid Search (Vector + BM25) with Reciprocal Rank Fusion."""
        logger.info("Hybrid Searching for: %r | filter=%s", query, where_filter)

        cache_key = self._search_cache_key(query, k=k, k_rrf=k_rrf, where_filter=where_filter)
        cached = self._get_cached_search(cache_key)
        if cached is not None:
            logger.info("Search cache hit for %r | filter=%s", query, where_filter)
            return cached

        vector_results = []
        if self.allow_query_embedding_fallback and self.in_capacity_cooldown():
            logger.info(
                "Skipping vector search for %r because capacity cooldown is active for %.1fs more.",
                query,
                max(0.0, float(self._vector_capacity_cooldown_until) - time.time()),
            )
        else:
            try:
                vector_results = self.vector_store.similarity_search_with_score(
                    query,
                    k=k * 2,
                    filter=where_filter,
                )
                vector_results = [
                    (self._hydrate_document_from_structure_graph(doc), score)
                    for doc, score in vector_results
                ]
            except Exception as exc:
                if self.allow_query_embedding_fallback and (
                    _is_embedding_capacity_error(exc) or _is_vector_store_read_error(exc)
                ):
                    if _is_embedding_capacity_error(exc):
                        self._open_capacity_cooldown(exc)
                    else:
                        logger.warning(
                            "Vector search unavailable for %r; falling back to BM25-only search: %s",
                            query,
                            exc,
                        )
                    vector_results = []
                elif where_filter and not _is_vector_store_read_error(exc) and not _is_embedding_capacity_error(exc):
                    vector_results = self.vector_store.similarity_search_with_score(query, k=k * 2)
                    vector_results = [
                        (self._hydrate_document_from_structure_graph(doc), score)
                        for doc, score in vector_results
                    ]
                else:
                    raise

        bm25_results = []
        if self.bm25:
            tokenized_query = _tokenize_ko(query)
            bm25_scores = self.bm25.get_scores(tokenized_query)
            top_n = sorted(range(len(bm25_scores)), key=lambda i: bm25_scores[i], reverse=True)[: k * 3]

            for idx in top_n:
                if bm25_scores[idx] <= 0:
                    continue
                metadata = self.bm25_metadatas[idx] or {}
                if not _metadata_matches_filter(metadata, where_filter):
                    continue
                doc = Document(page_content=self.bm25_docs[idx], metadata=metadata)
                bm25_results.append((doc, bm25_scores[idx]))

        rrf_scores: Dict[str, float] = {}
        doc_map: Dict[str, Document] = {}

        for rank, (doc, _) in enumerate(vector_results, 1):
            doc_id = _doc_identity(doc)
            doc_map[doc_id] = doc
            rrf_scores[doc_id] = 1.0 / (k_rrf + rank)

        for rank, (doc, _) in enumerate(bm25_results, 1):
            doc_id = _doc_identity(doc)
            doc_map[doc_id] = doc
            rrf_scores[doc_id] = rrf_scores.get(doc_id, 0.0) + 1.0 / (k_rrf + rank)

        sorted_rrf = sorted(rrf_scores.items(), key=lambda item: item[1], reverse=True)
        results = [(doc_map[doc_id], rrf_score) for doc_id, rrf_score in sorted_rrf[:k]]
        self._store_cached_search(cache_key, results)
        return results


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    manager = VectorStoreManager()

    test_chunks = [
        "Retrieval-Augmented Generation (RAG) improves LLM responses.",
        "Agentic workflows use LangGraph to route tasks.",
    ]
    test_meta = [{"source": "paper1", "chunk_uid": "paper1:0"}, {"source": "paper2", "chunk_uid": "paper2:0"}]

    manager.add_documents(test_chunks, test_meta)

    res = manager.search("What is RAG?", k=1)
    for doc, rrf_score in res:
        logger.info("RRF Score: %.4f | Content: %s", rrf_score, doc.page_content)
