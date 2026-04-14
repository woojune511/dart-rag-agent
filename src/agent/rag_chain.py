import os
import logging
import sys
from dotenv import load_dotenv

# Load variables from .env file
load_dotenv()
from typing import List, Dict, Any
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough

# Dynamic import to support local execution
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    from storage.vector_store import VectorStoreManager
except ImportError:
    pass

logger = logging.getLogger(__name__)

class RAGAgent:
    def __init__(self, vector_store_manager): # Assumes VectorStoreManager
        self.vector_store_manager = vector_store_manager
        
        # Fallback for API key
        api_key = os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            logger.warning("GOOGLE_API_KEY is not set. The LLM will operate in mock mode for testing.")
            self.llm = None
        else:
            self.llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0)
            
        self.prompt = ChatPromptTemplate.from_template(
            """You are an advanced AI research assistant. Synthesize a comprehensive and highly detailed answer based ONLY on the provided context chunks.
When making claims, explicitly cite the source paper using the [Source: arxiv_id] provided in the context. 
If the context contains conflicting information across papers, point it out.
If you don't know the answer or the context doesn't contain the information, say "I cannot find the answer in the retrieved papers."

Context:
{context}

Question: {question}

Answer:"""
        )

    def format_docs(self, docs):
        formatted = []
        for doc, score in docs:
            # The doc object depends on how Chroma returns it. Usually it's a tuple of (Document, score)
            arxiv_id = doc.metadata.get('arxiv_id', 'Unknown')
            formatted.append(f"[Source: {arxiv_id} | distance: {score:.4f}]\n{doc.page_content}")
        return "\n\n".join(formatted)

    def answer_question(self, question: str, retrieved_docs=None) -> str:
        logger.info(f"Answering question: {question}")
        
        # 1. Retrieve (allow injection of pre-retrieved docs to save DB calls)
        if retrieved_docs is None:
            retrieved_docs = self.vector_store_manager.search(question, k=10)
            
        if not retrieved_docs:
            return "No relevant documents found in the database."
            
        context_str = self.format_docs(retrieved_docs)
        logger.info(f"Retrieved {len(retrieved_docs)} contexts.")
        
        # 2. Generate
        if self.llm is None:
            return f"[MOCK LLM RESPONSE]\nRetrieved Context:\n{context_str}\n\n(To get a real AI generated answer, set GOOGLE_API_KEY environment variable)"
            
        chain = (
            {"context": lambda x: context_str, "question": RunnablePassthrough()}
            | self.prompt
            | self.llm
            | StrOutputParser()
        )
        
        return chain.invoke(question)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    from storage.vector_store import VectorStoreManager
    
    manager = VectorStoreManager()
    agent = RAGAgent(manager)
    
    print("\n--- RAG Testing ---")
    query = "What is RAG?"
    answer = agent.answer_question(query)
    print(f"\nQ: {query}\nA: {answer}")
