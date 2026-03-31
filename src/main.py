import os
import logging
import argparse
from ingestion.arxiv_fetcher import ArxivFetcher
from processing.pdf_parser import PDFParser
from storage.vector_store import VectorStoreManager
from agent.rag_chain import RAGAgent

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

def ingest_papers(query: str, max_results: int = 2):
    """Fetches papers, parses them, and stores them in Vector DB."""
    fetcher = ArxivFetcher()
    parser = PDFParser()
    vector_store = VectorStoreManager()
    
    logger.info(f"--- Starting Ingestion Pipeline ---")
    logger.info(f"Searching ArXiv for: {query}")
    papers = fetcher.search_papers(query, max_results=max_results)
    
    for paper in papers:
        logger.info(f"\n>> Processing paper: {paper.title}")
        paper = fetcher.download_pdf(paper)
        
        if paper.pdf_path:
            meta = {
                "arxiv_id": paper.arxiv_id,
                "title": paper.title,
                "authors": ", ".join(paper.authors),
                "published_date": paper.published_date
            }
            chunks = parser.process_document(paper.pdf_path, meta)
            
            if chunks:
                texts = [c.content for c in chunks]
                metadatas = [c.metadata for c in chunks]
                vector_store.add_documents(texts, metadatas)
                logger.info(f"Ingested {len(texts)} chunks for {paper.arxiv_id}")
            else:
                logger.warning(f"No text extracted from {paper.arxiv_id}")
        else:
            logger.warning(f"Skipping {paper.arxiv_id} due to missing PDF.")

def query_agent(question: str):
    """Queries the RAG agent."""
    vector_store = VectorStoreManager()
    agent = RAGAgent(vector_store)
    
    print(f"\n[User Question]: {question}")
    answer = agent.answer_question(question)
    print(f"\n[Agent Answer]:\n{answer}\n")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AI Research Agent CLI")
    parser.add_argument("--ingest", type=str, help="Ingest ArXiv papers matching this query")
    parser.add_argument("--max_papers", type=int, default=1, help="Max papers to ingest")
    parser.add_argument("--query", type=str, help="Ask a question to the RAG Agent")
    
    args = parser.parse_args()
    
    os.makedirs("data", exist_ok=True)
    
    if args.ingest:
        ingest_papers(args.ingest, args.max_papers)
    
    if args.query:
        query_agent(args.query)
        
    if not args.ingest and not args.query:
        print("Welcome to AI Research & Reproduction Agent!")
        print("Run with --help to see available commands.")
        print("Example: python src/main.py --ingest 'RAG and Agents' --max_papers 1")
        print("Example: python src/main.py --query 'How does RAG improve language models?'")
