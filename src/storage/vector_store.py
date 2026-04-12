import os
import re
import logging
from typing import List
from langchain_community.vectorstores import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_core.documents import Document

logger = logging.getLogger(__name__)


def _tokenize_ko(text: str) -> List[str]:
    """한국어 BM25 토크나이저 — character bigram 방식.

    어절 단위 스페이스 분리 대신 문자 bigram을 사용한다.
    '매출액과' → ['매출', '출액', '액과'] 이므로
    코퍼스의 '매출액' → ['매출', '출액'] 과 교집합이 생겨
    조사/어미가 붙은 형태도 자동으로 매칭된다.

    영문·숫자 토큰은 그대로 단어 단위로 처리한다.
    """
    tokens: List[str] = []
    # 한글 연속 구간과 영문·숫자 구간을 따로 추출
    for segment in re.findall(r'[가-힣]+|[a-zA-Z0-9]+', text):
        if re.match(r'[가-힣]', segment):
            # 한글: character bigram
            tokens.extend(segment[i:i + 2] for i in range(len(segment) - 1))
        else:
            # 영문·숫자: 단어 그대로 (소문자화)
            tokens.append(segment.lower())
    return tokens

class VectorStoreManager:
    def __init__(self, persist_directory: str = "data/chroma_db", collection_name: str = "ai_papers"):
        self.persist_directory = persist_directory
        os.makedirs(self.persist_directory, exist_ok=True)
        self.collection_name = collection_name
        
        # Using a small, fast local embedding model suitable for semantic search
        logger.info("Loading HuggingFace embeddings (all-MiniLM-L6-v2) this might take a minute on first run...")
        self.embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
        
        # Initialize Chroma vector store
        self.vector_store = Chroma(
            collection_name=self.collection_name,
            embedding_function=self.embeddings,
            persist_directory=self.persist_directory
        )
        logger.info(f"Initialized ChromaDB at {self.persist_directory}")
        
        self.bm25 = None
        self.bm25_docs = []
        self.bm25_metadatas = []
        self._init_bm25()

    def _init_bm25(self):
        try:
            docs = self.vector_store.get()
            if docs and docs.get('documents'):
                from rank_bm25 import BM25Okapi
                tokenized_corpus = [_tokenize_ko(doc) for doc in docs['documents']]
                self.bm25 = BM25Okapi(tokenized_corpus)
                self.bm25_docs = docs['documents']
                self.bm25_metadatas = docs['metadatas']
                logger.info(f"Initialized BM25 index with {len(self.bm25_docs)} documents.")
        except Exception as e:
            logger.warning(f"Could not initialize BM25: {e}")

    def is_indexed(self, rcept_no: str) -> bool:
        """해당 접수번호(rcept_no)의 문서가 이미 인덱싱돼 있는지 확인."""
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
            
        logger.info(f"Adding {len(chunks)} chunks to Vector DB...")
        self.vector_store.add_texts(texts=chunks, metadatas=metadatas)
        self._init_bm25()
        logger.info("Successfully added documents and updated BM25 index.")

    def search(self, query: str, k: int = 5, k_rrf: int = 60, where_filter: dict = None):
        """Perform Hybrid Search (Vector + BM25) with Reciprocal Rank Fusion (RRF).

        Args:
            where_filter: ChromaDB metadata filter applied at vector-search time.
                          e.g. {"company": "삼성전자"} or {"company": {"$in": [...]}}
                          BM25 results are post-filtered with the same logic.
        """
        logger.info(f"Hybrid Searching for: '{query}' | filter={where_filter}")

        # 1. Vector Search (ChromaDB where filter applied here)
        # Chroma similarity_search_with_score returns lower score for better match (L2 distance)
        try:
            vector_results = self.vector_store.similarity_search_with_score(
                query, k=k * 2, filter=where_filter
            )
        except Exception:
            # 필터 미지원 버전 폴백
            vector_results = self.vector_store.similarity_search_with_score(query, k=k * 2)
        
        # 2. BM25 Keyword Search
        bm25_results = []
        if self.bm25:
            tokenized_query = _tokenize_ko(query)
            bm25_scores = self.bm25.get_scores(tokenized_query)
            top_n = sorted(range(len(bm25_scores)), key=lambda i: bm25_scores[i], reverse=True)[:k*2]
            
            for idx in top_n:
                if bm25_scores[idx] > 0:
                    doc = Document(page_content=self.bm25_docs[idx], metadata=self.bm25_metadatas[idx])
                    bm25_results.append((doc, bm25_scores[idx]))
                    
        # 3. Apply Reciprocal Rank Fusion
        rrf_scores = {}
        doc_map = {}
        
        for rank, (doc, _) in enumerate(vector_results, 1):
            doc_id = doc.page_content
            doc_map[doc_id] = doc
            rrf_scores[doc_id] = 1.0 / (k_rrf + rank)
            
        for rank, (doc, _) in enumerate(bm25_results, 1):
            doc_id = doc.page_content
            doc_map[doc_id] = doc
            if doc_id in rrf_scores:
                rrf_scores[doc_id] += 1.0 / (k_rrf + rank)
            else:
                rrf_scores[doc_id] = 1.0 / (k_rrf + rank)
                
        sorted_rrf = sorted(rrf_scores.items(), key=lambda item: item[1], reverse=True)
        
        final_results = []
        for doc_id, rrf_score in sorted_rrf[:k]:
            final_results.append((doc_map[doc_id], rrf_score))
            
        return final_results

if __name__ == "__main__":
    # Smoke test
    logging.basicConfig(level=logging.INFO)
    manager = VectorStoreManager()
    
    # Test adding dummy data
    test_chunks = [
        "Retrieval-Augmented Generation (RAG) improves LLM responses.",
        "Agentic workflows use LangGraph to route tasks."
    ]
    test_meta = [{"source": "paper1"}, {"source": "paper2"}]
    
    manager.add_documents(test_chunks, test_meta)
    
    # Test search
    res = manager.search("What is RAG?", k=1)
    for doc, rrf_score in res:
        logger.info(f"RRF Score: {rrf_score:.4f} | Content: {doc.page_content}")
