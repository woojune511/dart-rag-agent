import json
import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from langchain_community.vectorstores import Chroma
from langchain_core.documents import Document
from langchain_huggingface import HuggingFaceEmbeddings

logger = logging.getLogger(__name__)

DEFAULT_EMBEDDING_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
DEFAULT_COLLECTION_NAME = "dart_reports_v2"


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


class VectorStoreManager:
    def __init__(
        self,
        persist_directory: str = "data/chroma_db",
        collection_name: str = DEFAULT_COLLECTION_NAME,
        embedding_model_name: str = DEFAULT_EMBEDDING_MODEL,
    ):
        self.persist_directory = persist_directory
        os.makedirs(self.persist_directory, exist_ok=True)
        self.collection_name = collection_name
        self.embedding_model_name = embedding_model_name

        logger.info(
            "Loading HuggingFace embeddings (%s). A full reindex is recommended when this model changes.",
            self.embedding_model_name,
        )
        self.embeddings = HuggingFaceEmbeddings(model_name=self.embedding_model_name)

        self.vector_store = Chroma(
            collection_name=self.collection_name,
            embedding_function=self.embeddings,
            persist_directory=self.persist_directory,
        )
        logger.info("Initialized ChromaDB at %s (collection=%s)", self.persist_directory, self.collection_name)

        self.bm25 = None
        self.bm25_docs: List[str] = []
        self.bm25_metadatas: List[dict] = []
        self._init_bm25()

        # Parent chunk store — persisted as JSON alongside the ChromaDB directory
        self._parents_path = Path(self.persist_directory) / "parents.json"
        self._parents: Dict[str, str] = self._load_parents()

    def _init_bm25(self):
        try:
            docs = self.vector_store.get()
            if docs and docs.get("documents"):
                from rank_bm25 import BM25Okapi

                tokenized_corpus = [_tokenize_ko(doc) for doc in docs["documents"]]
                self.bm25 = BM25Okapi(tokenized_corpus)
                self.bm25_docs = docs["documents"]
                self.bm25_metadatas = docs["metadatas"]
                logger.info("Initialized BM25 index with %s documents.", len(self.bm25_docs))
            else:
                self.bm25 = None
                self.bm25_docs = []
                self.bm25_metadatas = []
        except Exception as e:
            logger.warning("Could not initialize BM25: %s", e)

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

    # ------------------------------------------------------------------

    def is_indexed(self, rcept_no: str) -> bool:
        """Return whether the filing is already indexed."""
        try:
            result = self.vector_store.get(where={"rcept_no": rcept_no}, limit=1)
            return len(result.get("ids") or []) > 0
        except Exception:
            return False

    def add_documents(self, chunks: List[str], metadatas: List[dict]):
        """Add document chunks to the vector store."""
        if not chunks:
            logger.warning("No chunks provided to add_documents.")
            return

        logger.info("Adding %s chunks to Vector DB...", len(chunks))
        self.vector_store.add_texts(texts=chunks, metadatas=metadatas)
        self._init_bm25()
        logger.info("Successfully added documents and updated BM25 index.")

    def search(self, query: str, k: int = 5, k_rrf: int = 60, where_filter: dict = None):
        """Perform Hybrid Search (Vector + BM25) with Reciprocal Rank Fusion."""
        logger.info("Hybrid Searching for: %r | filter=%s", query, where_filter)

        try:
            vector_results = self.vector_store.similarity_search_with_score(
                query,
                k=k * 2,
                filter=where_filter,
            )
        except Exception:
            vector_results = self.vector_store.similarity_search_with_score(query, k=k * 2)

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
        return [(doc_map[doc_id], rrf_score) for doc_id, rrf_score in sorted_rrf[:k]]


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
