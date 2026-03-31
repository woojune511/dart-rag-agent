import pymupdf
import logging
import os
from typing import List, Dict, Any
from pydantic import BaseModel
from langchain_text_splitters import RecursiveCharacterTextSplitter

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DocumentChunk(BaseModel):
    content: str
    metadata: Dict[str, Any]

class PDFParser:
    def __init__(self, chunk_size: int = 1500, chunk_overlap: int = 200):
        # We use a semantic-aware text splitter (recursive character)
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            length_function=len,
            is_separator_regex=False,
        )

    def extract_text(self, pdf_path: str) -> str:
        text = ""
        try:
            doc = pymupdf.open(pdf_path)
            for page in doc:
                text += page.get_text() + "\n\n"
            return text
        except Exception as e:
            logger.error(f"Failed to extract text from {pdf_path}: {e}")
            return ""

    def process_document(self, pdf_path: str, source_metadata: Dict[str, Any]) -> List[DocumentChunk]:
        """Extracts text from a PDF, chunks it, and attaches the provided metadata."""
        logger.info(f"Processing document: {pdf_path}")
        raw_text = self.extract_text(pdf_path)
        if not raw_text.strip():
            logger.warning(f"No text extracted from {pdf_path}")
            return []
            
        chunks = self.text_splitter.split_text(raw_text)
        
        document_chunks = []
        for i, chunk in enumerate(chunks):
            # Create a copy of the metadata to avoid modifying the original dictionary across chunks
            meta = source_metadata.copy()
            meta["chunk_id"] = i
            document_chunks.append(DocumentChunk(content=chunk, metadata=meta))
            
        logger.info(f"Created {len(document_chunks)} chunks from {pdf_path}")
        return document_chunks

if __name__ == "__main__":
    # Smoke test
    parser = PDFParser(chunk_size=500, chunk_overlap=50)
    
    papers_dir = "data/papers"
    if os.path.exists(papers_dir):
        pdfs = [f for f in os.listdir(papers_dir) if f.endswith(".pdf")]
        if pdfs:
            pdf_path = os.path.join(papers_dir, pdfs[0])
            test_metadata = {"arxiv_id": "test_id", "title": "Test Paper"}
            chunks = parser.process_document(pdf_path, test_metadata)
            if chunks:
                logger.info(f"Successfully extracted {len(chunks)} chunks.")
                logger.info(f"Sample chunk: {chunks[0].content[:150]}...")
            else:
                logger.error("Extraction failed or empty.")
        else:
            logger.warning("No PDF files found to test.")
    else:
        logger.warning(f"Directory {papers_dir} does not exist.")
