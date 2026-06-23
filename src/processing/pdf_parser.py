import logging
from dataclasses import dataclass
from typing import List, Dict, Any

logger = logging.getLogger(__name__)


def _markdown_header_text_splitter(**kwargs):
    from langchain_text_splitters import MarkdownHeaderTextSplitter

    return MarkdownHeaderTextSplitter(**kwargs)


def _recursive_character_text_splitter(**kwargs):
    from langchain_text_splitters import RecursiveCharacterTextSplitter

    return RecursiveCharacterTextSplitter(**kwargs)


def _pdf_to_markdown(pdf_path: str) -> str:
    import pymupdf4llm

    return pymupdf4llm.to_markdown(pdf_path)


@dataclass
class DocumentChunk:
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
        self.markdown_splitter = _markdown_header_text_splitter(headers_to_split_on=headers_to_split_on)
        
        # 2. Secondary Splitter: Fallback for massive sections
        self.text_splitter = _recursive_character_text_splitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            length_function=len,
            is_separator_regex=False,
        )

    def extract_text(self, pdf_path: str) -> str:
        """Extracts PDF directly to structurally rich Markdown."""
        try:
            md_text = _pdf_to_markdown(pdf_path)
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
