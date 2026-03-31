import arxiv
import os
import logging
import ssl
import time
import re
from duckduckgo_search import DDGS
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

load_dotenv()

# Fix SSL certificate verification issues on Windows
try:
    _create_unverified_https_context = ssl._create_unverified_context
except AttributeError:
    pass
else:
    ssl._create_default_https_context = _create_unverified_https_context
from typing import List, Optional
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class PaperMetadata(BaseModel):
    arxiv_id: str
    title: str
    authors: List[str]
    summary: str
    published_date: str
    pdf_url: str
    pdf_path: Optional[str] = None

class ArxivFetcher:
    def __init__(self, download_dir: str = "data/papers"):
        self.download_dir = download_dir
        os.makedirs(self.download_dir, exist_ok=True)
        # Construct the default API client.
        self.client = arxiv.Client()
        
        self.llm = None
        if os.environ.get("GOOGLE_API_KEY"):
            self.llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0)
            self.query_prompt = ChatPromptTemplate.from_template(
                "You are an expert at searching arXiv. Convert the following natural language query into a valid arXiv search API query string. "
                "Use prefixes like ti:, au:, abs:, cat:, all: and logical operators AND, OR, ANDNOT. "
                "If the input already looks like a valid arXiv query (e.g. contains 'all:', 'ti:', 'AND'), return it exactly as is. "
                "Return ONLY the raw query string without any quotes, backticks, markdown formatting, or explanation.\n\n"
                "User Query: {query}\nArXiv Query:"
            )

    def search_papers(self, query: str, max_results: int = 5) -> List[PaperMetadata]:
        arxiv_query = query
        if hasattr(self, 'llm') and self.llm:
            chain = self.query_prompt | self.llm | StrOutputParser()
            arxiv_query = chain.invoke({"query": query}).strip()
            # Remove any wrapping quotes or backticks if the LLM hallucinated them
            arxiv_query = arxiv_query.strip("`'\"")
            logger.info(f"LLM rewritten query: '{arxiv_query}' (Original: '{query}')")

        search = arxiv.Search(
            query=arxiv_query,
            max_results=max_results,
            sort_by=arxiv.SortCriterion.Relevance
        )
        
        results = []
        max_retries = 3
        for attempt in range(max_retries):
            try:
                for result in self.client.results(search):
                    paper = PaperMetadata(
                        arxiv_id=result.entry_id.split('/')[-1],
                        title=result.title,
                        authors=[author.name for author in result.authors],
                        summary=result.summary,
                        published_date=str(result.published),
                        pdf_url=result.pdf_url
                    )
                    results.append(paper)
                break  # Break out of retry loop if successful
            except Exception as e:
                logger.warning(f"ArXiv Search Error (Attempt {attempt+1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    time.sleep(2 * (attempt + 1))  # Exponential-ish backoff
                else:
                    logger.error("Max retries reached for ArXiv search. Returning partial or empty results.")
        return results

    def search_papers_via_web(self, query: str, max_results: int = 10) -> List[PaperMetadata]:
        """Uses DuckDuckGo to search for highly trending ArXiv links (Agentic Query Expansion)."""
        web_query = f"{query} site:arxiv.org/abs"
        logger.info(f"Executing Web Search for Candidates: {web_query}")
        
        arxiv_ids = set()
        max_retries = 3
        for attempt in range(max_retries):
            try:
                results = DDGS().text(web_query, max_results=max_results * 2)
                for r in results:
                    url = r.get('href', '')
                    # Extract ID from https://arxiv.org/abs/2304.03442 -> 2304.03442
                    match = re.search(r'arxiv\.org/abs/(\d+\.\d+(v\d+)?)', url)
                    if match:
                        # Strip version string like v1, v2 to avoid fetch errors
                        clean_id = match.group(1).split('v')[0] 
                        arxiv_ids.add(clean_id)
                break
            except Exception as e:
                logger.warning(f"Web Search Error (Attempt {attempt+1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    time.sleep(2 * (attempt + 1))
                else:
                    return []
                    
        arxiv_ids = list(arxiv_ids)[:max_results]
        if not arxiv_ids:
            return []
            
        logger.info(f"Found {len(arxiv_ids)} unique ArXiv IDs via Web Search. Hydrating metadata...")
        
        # Hydrate metadata using ArXiv bulk ID lookup
        search = arxiv.Search(id_list=arxiv_ids)
        papers = []
        for attempt in range(max_retries):
            try:
                for result in self.client.results(search):
                    paper = PaperMetadata(
                        arxiv_id=result.entry_id.split('/')[-1],
                        title=result.title,
                        authors=[author.name for author in result.authors],
                        summary=result.summary,
                        published_date=str(result.published),
                        pdf_url=result.pdf_url
                    )
                    papers.append(paper)
                break
            except Exception as e:
                logger.warning(f"ArXiv ID Hydration Error (Attempt {attempt+1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    time.sleep(2 * (attempt + 1))
        return papers

    def download_pdf(self, paper: PaperMetadata) -> PaperMetadata:
        try:
            # Clean filename by replacing dots with underscores
            filename = f"{paper.arxiv_id.replace('.', '_')}.pdf"
            pdf_path = os.path.join(self.download_dir, filename)
            
            if os.path.exists(pdf_path):
                logger.info(f"PDF already exists for {paper.arxiv_id}")
                paper.pdf_path = pdf_path
                return paper

            logger.info(f"Downloading PDF for {paper.arxiv_id} from {paper.pdf_url}...")
            
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    # Re-fetch specific paper result object to use its native download method
                    result_search = arxiv.Search(id_list=[paper.arxiv_id])
                    result = next(self.client.results(result_search))
                    
                    # Download to directory
                    result.download_pdf(dirpath=self.download_dir, filename=filename)
                    
                    paper.pdf_path = pdf_path
                    logger.info(f"Successfully downloaded to {pdf_path}")
                    return paper
                except Exception as e:
                    logger.warning(f"Failed to download PDF {paper.arxiv_id} (Attempt {attempt+1}/{max_retries}): {e}")
                    if attempt < max_retries - 1:
                        time.sleep(2 * (attempt + 1))
                    else:
                        logger.error(f"Max retries reached for downloading {paper.arxiv_id}.")
                        return paper
            
        except StopIteration:
            logger.error(f"Paper {paper.arxiv_id} not found when attempting to download.")
            return paper
        except Exception as e:
            logger.error(f"Failed to process PDF download logic for {paper.arxiv_id}: {e}")
            return paper

if __name__ == "__main__":
    # Simple smoke test when running this file directly
    fetcher = ArxivFetcher()
    logger.info("Searching for recent papers using a natural language query...")
    # Using a natural language query to test the LLM rewriter
    papers = fetcher.search_papers(query="find me recent papers about RAG combined with large language models", max_results=2)
    
    for p in papers:
        logger.info(f"Found: {p.title} ({p.published_date})")
        p = fetcher.download_pdf(p)
        logger.info(f"Downloaded at: {p.pdf_path}\n")
