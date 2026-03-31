import os
import logging
import requests
import json
from datetime import datetime
from typing import List, Dict, Any, Tuple
from dotenv import load_dotenv

# We need pydantic to parse LLM structured outputs elegantly
from pydantic import BaseModel, Field

# Langchain imports
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from duckduckgo_search import DDGS
import math

import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    from ingestion.arxiv_fetcher import PaperMetadata
except ImportError:
    pass

load_dotenv()
logger = logging.getLogger(__name__)

class LLMDeepevalResult(BaseModel):
    is_relevant: bool = Field(description="True if the paper perfectly meets the user's specific domain/topic requirement, False otherwise")
    relevance_score: int = Field(description="Relevance score from 1 to 10")
    reasoning: str = Field(description="A very brief, one-sentence reason for the score")

class FilterAgent:
    def __init__(self):
        self.llm = None
        if os.environ.get("GOOGLE_API_KEY"):
            self.llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0)
            
            # Setup structured output parser
            self.parser = PydanticOutputParser(pydantic_object=LLMDeepevalResult)
            
            self.eval_prompt = ChatPromptTemplate.from_template(
                "You are an expert AI research reviewer.\n"
                "The user is looking for papers satisfying the following requirement: '{user_query}'\n\n"
                "Here is a paper's data:\n"
                "Title: {title}\n"
                "Abstract: {abstract}\n"
                "Community Web Context (Github, Blogs, Discussions): {web_context}\n\n"
                "Evaluate if this paper is highly relevant to the user's requirements and has good community traction.\n"
                "{format_instructions}\n"
            )

    def fetch_citations(self, papers: List[PaperMetadata]) -> Dict[str, int]:
        """
        Uses Semantic Scholar Batch API to fetch citation counts for a list of ArXiv papers.
        """
        if not papers:
            return {}
            
        logger.info(f"Fetching Semantic Scholar citation metrics for {len(papers)} papers...")
        
        # Prepare ArXiv IDs for Semantic Scholar
        # Format: "ArXiv:2104.12345"
        s2_ids = [f"ArXiv:{p.arxiv_id.split('v')[0]}" for p in papers]
        
        url = "https://api.semanticscholar.org/graph/v1/paper/batch?fields=citationCount,year"
        
        try:
            response = requests.post(url, json={"ids": s2_ids})
            response.raise_for_status()
            data = response.json()
            
            citation_map = {}
            for i, item in enumerate(data):
                arxiv_id = papers[i].arxiv_id
                if item and "citationCount" in item:
                    citation_map[arxiv_id] = item["citationCount"]
                else:
                    citation_map[arxiv_id] = 0
            
            return citation_map
        except Exception as e:
            logger.error(f"Failed to fetch from Semantic Scholar: {e}")
            # Fallback to 0 citations if API fails
            return {p.arxiv_id: 0 for p in papers}

    def sort_by_impact(self, papers: List[PaperMetadata], citations: Dict[str, int]) -> List[Tuple[PaperMetadata, float]]:
        """
        Score = citation_count + recency_bonus
        Recency bonus: Papers published in the current/previous year get a slight boost
        """
        scored_papers = []
        current_year = datetime.now().year
        
        for p in papers:
            cite_count = citations.get(p.arxiv_id, 0)
            
            # Simple recency extraction (e.g., from '2023-11-20 18:32:00+00:00')
            pub_year = 2000 # default fallback
            try:
                pub_year = int(p.published_date[:4])
            except:
                pass
                
            # Drop old papers that still have 0 citations (High probability of being noise/unimportant)
            if cite_count == 0 and pub_year < current_year - 1:
                continue

            age = current_year - pub_year
            
            # Base impact is log10 of citations (10 = 1.0, 100 = 2.0, 1000 = 3.0, 10000 = 4.0)
            base_impact = math.log10(cite_count + 1)
            
            # Age penalty: -0.5 points per year after the first year
            age_penalty = max(0, age - 1) * 0.5
            
            # Recency multiplier: Boost papers from this year or last year
            recency_multiplier = 1.0
            if age == 0:
                recency_multiplier = 2.0
            elif age == 1:
                recency_multiplier = 1.5
                
            total_score = (base_impact - age_penalty) * recency_multiplier
            scored_papers.append((p, round(total_score, 2)))
            
        # Sort descending by total score
        scored_papers.sort(key=lambda x: x[1], reverse=True)
        return scored_papers

    def filter_with_llm(self, user_query: str, scored_papers: List[Tuple[PaperMetadata, float]], top_k: int = 3) -> List[PaperMetadata]:
        """
        Read abstracts of the top-impact papers and return the ones that pass the LLM relevance check.
        """
        if not self.llm:
            logger.warning("GOOGLE_API_KEY not set. Skipping LLM filtering, returning top impact directly.")
            return [p for p, score in scored_papers[:top_k]]
            
        logger.info(f"Starting LLM Abstract Review for top candidates to find the best {top_k} papers.")
        approved_papers = []
        
        chain = self.eval_prompt | self.llm | self.parser
        
        for paper, score in scored_papers:
            if len(approved_papers) >= top_k:
                break
                
            logger.info(f"Evaluating: {paper.title} (Impact Score: {score})")
            try:
                # 1. Fetch live community context via Web Search
                logger.info(f"  -> Fetching Web Context via DuckDuckGo...")
                web_query = f"\"{paper.title}\" github OR machine learning blog"
                # Add a fallback in case DuckDuckGo fails
                web_context = "No community context found."
                try:
                    results = DDGS().text(web_query, max_results=3)
                    web_context = " ".join([r.get('body', '') for r in results]) if results else "No community context found."
                    # Truncate to avoid blowing up context window
                    web_context = web_context[:1000] + "..." if len(web_context) > 1000 else web_context
                except Exception as e:
                    logger.warning(f"  -> Web Search failed softly: {e}")

                # 2. Evaluate with Gemini
                result = chain.invoke({
                    "user_query": user_query,
                    "title": paper.title,
                    "abstract": paper.summary,
                    "web_context": web_context,
                    "format_instructions": self.parser.get_format_instructions()
                })
                
                logger.info(f"  -> Relevant: {result.is_relevant}, Score: {result.relevance_score}/10, Reason: {result.reasoning}")
                if result.is_relevant and result.relevance_score >= 6:
                    approved_papers.append(paper)
            except Exception as e:
                logger.error(f"  -> Evaluation parsing failed: {e}")
                
        return approved_papers

if __name__ == "__main__":
    from ingestion.arxiv_fetcher import ArxivFetcher
    logging.basicConfig(level=logging.INFO)
    
    # Simple integration test
    fetcher = ArxivFetcher()
    query = "AI Web Agents" # A broad query
    logger.info("1. ArXiv Ingestion Layer (Fetching 10 broad papers)")
    raw_papers = fetcher.search_papers(query="all:web AND all:agent AND all:LLM", max_results=10)
    
    logger.info("\n2. Impact & Filtering Layer (Citation Tracker)")
    filter_agent = FilterAgent()
    citations = filter_agent.fetch_citations(raw_papers)
    scored = filter_agent.sort_by_impact(raw_papers, citations)
    
    for p, s in scored[:3]:
        logger.info(f"Top Impact Candidate: {p.title} - Score: {s} (Citations: {citations.get(p.arxiv_id, 0)})")
        
    logger.info("\n3. LLM Abstract Review Layer")
    natural_user_query = "Looking for papers specifically about building autonomous agents that can browse the web to do complex tasks."
    final_papers = filter_agent.filter_with_llm(user_query=natural_user_query, scored_papers=scored, top_k=2)
    
    logger.info("\n4. Final Surviving Papers (To be downloaded for PDF RAG):")
    for p in final_papers:
        logger.info(f"- {p.title} (ArXiv ID: {p.arxiv_id})")
