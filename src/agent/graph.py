import operator
from typing import TypedDict, Annotated, Sequence, Dict, Any, List
from langchain_core.messages import BaseMessage, AIMessage, HumanMessage
from langgraph.graph import StateGraph, END
from pydantic import BaseModel, Field
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
import logging
import sys
import os

# Ensure src is in python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    from ingestion.arxiv_fetcher import ArxivFetcher
    from agent.filter_agent import FilterAgent
    from processing.pdf_parser import PDFParser
    from storage.vector_store import VectorStoreManager
    from agent.rag_chain import RAGAgent
    from processing.github_downloader import GithubDownloader
    from processing.ast_parser import ASTParser
except ImportError:
    pass

logger = logging.getLogger(__name__)

class AgentState(TypedDict):
    """The central state object for the LangGraph orchestrator."""
    messages: Annotated[Sequence[BaseMessage], operator.add]
    current_intent: str
    is_clarified: bool
    requirements: Dict[str, Any]
    fetched_papers: List[Dict[str, Any]]
    rag_context: str
    final_answer: str

class RequirementsExtracted(BaseModel):
    is_clear: bool = Field(description="True if the user's search intent AND specific constraints are clear, OR if the user explicitly commands to just proceed/search without constraints.")
    missing_info_question: str = Field(description="If not clear, the exact conversational question to ask the user to clarify their intent.", default="")
    primary_intent: str = Field(description="One of: RESEARCH_NEW_PAPERS, DEEP_QA_PAPER, CODE_ANALYSIS, GENERAL_CHAT", default="GENERAL_CHAT")
    extracted_keywords: str = Field(description="The core search query to use for ArXiv/DB", default="")
    github_url: str = Field(description="If the user provided a Github repository URL, extract it here.", default="")

def clarification_node(state: AgentState) -> Dict[str, Any]:
    """Checks if the user request is specific enough or asks for more details."""
    logger.info("Executing Clarification Node")
    messages = state.get("messages", [])
    if not messages:
        return {"is_clarified": False}
        
    try:
        llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0)
        structured_llm = llm.with_structured_output(RequirementsExtracted)
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", "You are an AI Research Agent built for advanced ML engineers. Analyze the user's FULL conversation history to determine their true request.\n"
                       "If their combined request is still too broad (e.g., just 'find papers on AI agents') AND they haven't told you to bypass, mark is_clear=False "
                       "and generate a `missing_info_question` to ask them to specify publication year, specific benchmarks, or sub-fields.\n"
                       "**CRITICAL OVERRIDE RULE**: If the user explicitly tells you to 'just search', 'proceed anyway', 'I don't care', '그냥 검색해' or similar commands ignoring your request for clarification, you MUST mark is_clear=True and proceed with whatever broad keywords they provided.\n"
                       "If their conversation history provides highly specific conditions or asks a specific question about an existing paper/codebase, mark is_clear=True.\n"
                       "Valid intents: RESEARCH_NEW_PAPERS (finding candidates), DEEP_QA_PAPER (RAG), CODE_ANALYSIS (Github/AST code QA), GENERAL_CHAT.\n"
                       "Synthesize all constraints (years, methodologies, topics) you gathered from the chat history into `extracted_keywords`."),
            MessagesPlaceholder(variable_name="chat_history")
        ])
        
        chain = prompt | structured_llm
        result = chain.invoke({"chat_history": messages})
        
        if not result.is_clear:
            clarification_msg = AIMessage(content=result.missing_info_question)
            return {
                "is_clarified": False, 
                "messages": [clarification_msg],
                "current_intent": result.primary_intent
            }
        else:
            return {
                "is_clarified": True,
                "current_intent": result.primary_intent,
                "requirements": {"query": result.extracted_keywords}
            }
            
    except Exception as e:
        logger.error(f"Clarification LLM Error: {e}")
        return {"is_clarified": True, "current_intent": "GENERAL_CHAT"}

def router_node(state: AgentState) -> Dict[str, Any]:
    """Routes the clarified request to the proper expert agent."""
    logger.info("Executing Router Node (Pass-through)")
    # The intent was already evaluated and saved to state by the clarification_node
    return {}

def arxiv_ingestion_node(state: AgentState) -> Dict[str, Any]:
    logger.info("Executing ArXiv Ingestion Node")
    reqs = state.get("requirements", {})
    query = reqs.get("query", state.get("messages", [])[-1].content if state.get("messages") else "AI Research")
    
    try:
        fetcher = ArxivFetcher()
        filter_agent = FilterAgent()
        parser = PDFParser()
        vector_store = VectorStoreManager()
        
        # 1. Candidates
        arxiv_papers = fetcher.search_papers(query, max_results=20)
        web_papers = fetcher.search_papers_via_web(query, max_results=5)
        raw_papers = list({p.arxiv_id: p for p in arxiv_papers + web_papers}.values())
        if not raw_papers:
            return {"final_answer": "No candidate papers found for the specified query."}
            
        # 2. Filter
        citations = filter_agent.fetch_citations(raw_papers)
        scored = filter_agent.sort_by_impact(raw_papers, citations)
        final_papers = filter_agent.filter_with_llm(user_query=query, scored_papers=scored, top_k=3)
        
        # 3. Download & Index
        ingested_count = 0
        for paper in final_papers:
            p = fetcher.download_pdf(paper)
            if p.pdf_path:
                meta = {"arxiv_id": p.arxiv_id, "title": p.title}
                chunks = parser.process_document(p.pdf_path, meta)
                if chunks:
                    vector_store.add_documents([c.content for c in chunks], [c.metadata for c in chunks])
                    ingested_count += 1
                    
        ans = f"✅ Pipeline Complete: Extracted, filtered, and seamlessly embedded {ingested_count} high-impact SOTA papers into Hybrid Vector Store for '{query}'."
        return {"messages": [AIMessage(content=ans)], "final_answer": ans, "fetched_papers": [{"id": p.arxiv_id, "title": p.title} for p in final_papers]}
    except Exception as e:
        logger.error(f"ArXiv Node Error: {e}")
        ans = f"Pipeline failed: {str(e)}"
        return {"messages": [AIMessage(content=ans)], "final_answer": ans}

def rag_qa_node(state: AgentState) -> Dict[str, Any]:
    logger.info("Executing RAG QA Node")
    messages = state.get("messages", [])
    if not messages:
        return {"final_answer": "No question provided to RAG."}
        
    question = messages[-1].content
    try:
        vector_store = VectorStoreManager()
        agent = RAGAgent(vector_store)
        
        # Pull Massive Context chunks
        retrieved_docs = vector_store.search(question, k=10)
        answer = agent.answer_question(question, retrieved_docs=retrieved_docs)
        
        return {"messages": [AIMessage(content=answer)], "final_answer": answer}
    except Exception as e:
        logger.error(f"RAG QA Error: {e}")
        ans = f"RAG execution failed: {str(e)}"
        return {"messages": [AIMessage(content=ans)], "final_answer": ans}

def code_analysis_node(state: AgentState) -> Dict[str, Any]:
    logger.info("Executing Code Analysis Node")
    reqs = state.get("requirements", {})
    github_url = reqs.get("github_url", "")
    messages = state.get("messages", [])
    question = messages[-1].content if messages else "Explain this codebase architecture."
    
    if not github_url:
        import re
        match = re.search(r'https?://github\.com/[^\s]+', question)
        if match:
            github_url = match.group(0)
        else:
            return {"final_answer": "No GitHub URL was provided or found in the text for analysis."}
            
    try:
        downloader = GithubDownloader()
        ast_parser = ASTParser()
        vector_store = VectorStoreManager()
        agent = RAGAgent(vector_store)
        
        # 1. Download
        repo_path = downloader.download_repo(github_url)
        if not repo_path:
            return {"final_answer": f"Failed to clone repository: {github_url}. Is the URL correct?"}
            
        # 2. Parse AST
        chunks = ast_parser.process_repo(repo_path)
        if not chunks:
            return {"final_answer": "No valid Python code found in the repository to construct an AST."}
            
        # 3. Index Code
        texts = [c.content for c in chunks]
        metadatas = [c.metadata for c in chunks]
        vector_store.add_documents(texts, metadatas)
        
        # 4. RAG against the newly embedded Code blocks
        retrieved_docs = vector_store.search(question, k=10)
        answer = agent.answer_question(question, retrieved_docs=retrieved_docs)
        
        ans = f"✅ Extracted and AST-parsed {len(chunks)} python functions & classes from {github_url}.\n\n🧠 **Code Insights:**\n{answer}"
        return {"messages": [AIMessage(content=ans)], "final_answer": ans}
        
    except Exception as e:
        logger.error(f"Code Analysis Pipeline Error: {e}")
        ans = f"Code analysis execution failed: {str(e)}"
        return {"messages": [AIMessage(content=ans)], "final_answer": ans}

def should_continue(state: AgentState) -> str:
    """Decides whether to route the request or stop to ask the user for clarification."""
    if not state.get("is_clarified", False):
        return "end" # End early to ask user for clarification
    return "router"
    
def route_intent(state: AgentState) -> str:
    """Decides which expert node to run based on the classified intent."""
    intent = state.get("current_intent", "GENERAL_CHAT")
    if intent == "RESEARCH_NEW_PAPERS":
        return "arxiv_ingest"
    elif intent == "DEEP_QA_PAPER":
        return "rag_qa"
    elif intent == "CODE_ANALYSIS":
        return "code_analysis"
    return "end"

def build_graph():
    """Compiles the StateGraph."""
    builder = StateGraph(AgentState)

    # 1. Add Nodes
    builder.add_node("clarify", clarification_node)
    builder.add_node("router", router_node)
    builder.add_node("arxiv_ingest", arxiv_ingestion_node)
    builder.add_node("rag_qa", rag_qa_node)
    builder.add_node("code_analysis", code_analysis_node)

    # 2. Set Entry Point
    builder.set_entry_point("clarify")
    
    # 3. Add Edges
    builder.add_conditional_edges("clarify", should_continue, {
        "router": "router",
        "end": END
    })
    
    builder.add_conditional_edges("router", route_intent, {
        "arxiv_ingest": "arxiv_ingest",
        "rag_qa": "rag_qa",
        "code_analysis": "code_analysis",
        "end": END
    })
    
    # Terminal edges
    builder.add_edge("arxiv_ingest", END)
    builder.add_edge("rag_qa", END)
    builder.add_edge("code_analysis", END)

    return builder.compile()
