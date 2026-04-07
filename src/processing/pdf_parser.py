import pymupdf4llm
import logging
import os
from typing import List, Dict, Any
from pydantic import BaseModel
from langchain_text_splitters import RecursiveCharacterTextSplitter, MarkdownHeaderTextSplitter

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DocumentChunk(BaseModel):
    content: str
    metadata: Dict[str, Any]

class PDFParser:
    def __init__(self, chunk_size: int = 1500, chunk_overlap: int = 200):
        # 1. Primary Splitter: Markdown Headers (Structural)
        headers_to_split_on = [
            ("#", "Header 1"),
            ("##", "Header 2"),
            ("###", "Header 3"),
        ]
        self.markdown_splitter = MarkdownHeaderTextSplitter(headers_to_split_on=headers_to_split_on)
        
        # 2. Secondary Splitter: Fallback for massive sections
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            length_function=len,
            is_separator_regex=False,
        )

    def extract_text(self, pdf_path: str) -> str:
        """Extracts PDF directly to structurally rich Markdown."""
        try:
            md_text = pymupdf4llm.to_markdown(pdf_path)
            # pymupdf4llm preserves tables and reading order beautifully
            return md_text
        except Exception as e:
            logger.error(f"Failed to extract markdown from {pdf_path}: {e}")
            return ""

    def process_document(self, pdf_path: str, source_metadata: Dict[str, Any]) -> List[DocumentChunk]:
        """Extracts markdown, splits structurally by Headers, then by size if needed."""
        logger.info(f"Processing document (Structure Based): {pdf_path}")
        raw_markdown = self.extract_text(pdf_path)
        if not raw_markdown.strip():
            logger.warning(f"No text extracted from {pdf_path}")
            return []
            
        # 1. Structural Chunking based on Markdown Headers
        md_header_splits = self.markdown_splitter.split_text(raw_markdown)
        
        # 2. Size-based Fallback Chunking (Preserves Header Metadata)
        final_splits = self.text_splitter.split_documents(md_header_splits)
        
        document_chunks = []
        for i, split in enumerate(final_splits):
            meta = source_metadata.copy()
            meta["chunk_id"] = i
            # Merge the Structural Header Metadata (e.g. {"Header 2": "Methodology"})
            meta.update(split.metadata)
            
            document_chunks.append(DocumentChunk(content=split.page_content, metadata=meta))
            
        logger.info(f"Created {len(document_chunks)} structure-aware chunks from {pdf_path}")
        return document_chunks

if __name__ == "__main__":
    # Smoke test for Document Structure Chunking
    parser = PDFParser(chunk_size=1000, chunk_overlap=100)
    
    papers_dir = "data/papers"
    if os.path.exists(papers_dir):
        pdfs = [f for f in os.listdir(papers_dir) if f.endswith(".pdf")]
        if pdfs:
            pdf_path = os.path.join(papers_dir, pdfs[0])
            test_metadata = {"arxiv_id": "test_id", "title": "Test Paper"}
            
            print(f"\n--- Testing Structure-Aware Parsing on {pdfs[0]} ---")
            chunks = parser.process_document(pdf_path, test_metadata)
            
            if chunks:
                print(f"✅ Successfully extracted {len(chunks)} contextual chunks.")
                for i in range(min(3, len(chunks))):
                    print(f"\n[Chunk {i} Metadata]: {chunks[i].metadata}")
                    print(f"[Chunk {i} Content Head]:\n{chunks[i].content[:200]}...\n{'-'*50}")
            else:
                logger.error("Extraction failed or empty.")
        else:
            logger.warning("No PDF files found to test.")
    else:
        logger.warning(f"Directory {papers_dir} does not exist.")
