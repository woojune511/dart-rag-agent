import os
import logging
from typing import List, Tuple
from langchain_community.vectorstores import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_core.documents import Document

logger = logging.getLogger(__name__)

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
                tokenized_corpus = [doc.lower().split(" ") for doc in docs['documents']]
                self.bm25 = BM25Okapi(tokenized_corpus)
                self.bm25_docs = docs['documents']
                self.bm25_metadatas = docs['metadatas']
                logger.info(f"Initialized BM25 index with {len(self.bm25_docs)} documents.")
        except Exception as e:
            logger.warning(f"Could not initialize BM25: {e}")

    def add_documents(self, chunks: List[str], metadatas: List[dict]):
        """Add document chunks to the vector store."""
        if not chunks:
            logger.warning("No chunks provided to add_documents.")
            return
            
        logger.info(f"Adding {len(chunks)} chunks to Vector DB...")
        self.vector_store.add_texts(texts=chunks, metadatas=metadatas)
        self._init_bm25()
        logger.info("Successfully added documents and updated BM25 index.")

    def search(self, query: str, k: int = 5, k_rrf: int = 60):
        """Perform Hybrid Search (Vector + BM25) with Reciprocal Rank Fusion (RRF)."""
        logger.info(f"Hybrid Searching for: '{query}'")
        
        # 1. Vector Search
        # Chroma similarity_search_with_score returns lower score for better match (L2 distance)
        vector_results = self.vector_store.similarity_search_with_score(query, k=k*2)
        
        # 2. BM25 Keyword Search
        bm25_results = []
        if self.bm25:
            tokenized_query = query.lower().split(" ")
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
