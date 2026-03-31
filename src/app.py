import streamlit as st
import os
import sys
import time
import mlflow

# Initialize MLflow Local Tracking
os.makedirs("mlruns", exist_ok=True)
mlflow.set_tracking_uri("file:./mlruns")
mlflow.set_experiment("Research_Agent_RAG")

# Ensure src is in python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from ingestion.arxiv_fetcher import ArxivFetcher
from processing.pdf_parser import PDFParser
from storage.vector_store import VectorStoreManager
from agent.filter_agent import FilterAgent
from agent.rag_chain import RAGAgent

st.set_page_config(page_title="Agent Debug UI", layout="wide")
st.title("🤖 AI Research Agent - Traceability UI")

tab1, tab2, tab3 = st.tabs(["Phase 1.5: Ingestion & Filter", "Phase 1: RAG Q&A", "Phase 3: Multi-Agent Router"])

with tab1:
    st.header("1. Agentic Filtering & Ingestion")
    st.markdown("Fetch papers from ArXiv, filter out the noise with Semantic Scholar and Gemini, and index the final PDFs into our Hybrid RRF Vector Store.")
    
    query = st.text_input("Research Topic / Natural Language Query", "Autonomous Web Browsing Agents")
    
    col1, col2 = st.columns(2)
    with col1:
        max_search = st.number_input("Max ArXiv Candidates to Fetch", min_value=10, max_value=100, value=30)
    with col2:
        max_download = st.number_input("Max PDFs to Download (Top %)", min_value=1, max_value=10, value=2)
    
    if st.button("Run Multi-Agent Ingestion Pipeline", type="primary"):
        # Reset logs for new run
        st.session_state["ingest_logs"] = []
        
        with st.status("Executing Pipeline...", expanded=True) as status:
            fetcher = ArxivFetcher()
            filter_agent = FilterAgent()
            vector_store = VectorStoreManager()
            parser = PDFParser()
            
            st.write(f"**Step 1.1:** Searching ArXiv API for candidates...")
            arxiv_papers = fetcher.search_papers(query, max_results=max_search)
            msg1 = f"🎯 Found {len(arxiv_papers)} candidates from ArXiv API."
            st.write(msg1)
            st.session_state["ingest_logs"].append(msg1)
            
            st.write(f"**Step 1.2:** Supplementing with DuckDuckGo Web Search...")
            web_papers = fetcher.search_papers_via_web(query, max_results=10)
            msg2 = f"🌐 Found {len(web_papers)} hidden/trending candidates via Web Search."
            st.write(msg2)
            st.session_state["ingest_logs"].append(msg2)
            
            # Combine and deduplicate based on ArXiv ID
            raw_papers_dict = {p.arxiv_id: p for p in arxiv_papers + web_papers}
            raw_papers = list(raw_papers_dict.values())
            msg3 = f"**Total Unique Candidates to Process:** {len(raw_papers)}"
            st.write(msg3)
            st.session_state["ingest_logs"].append(msg3)
            
            st.write(f"**Step 2:** Fetching Impact Metrics (Semantic Scholar)...")
            citations = filter_agent.fetch_citations(raw_papers)
            scored = filter_agent.sort_by_impact(raw_papers, citations)
            with st.expander("Show Top 5 Impact Candidates"):
                for p, s in scored[:5]:
                    candidate_msg = f"- **{p.title}** (Citations: {citations.get(p.arxiv_id, 0)} | Impact Score: {s})"
                    st.markdown(candidate_msg)
                    st.session_state["ingest_logs"].append(candidate_msg)
                
            st.write(f"**Step 3:** LLM Abstract Evaluation (Filtering Noise)...")
            final_papers = filter_agent.filter_with_llm(user_query=query, scored_papers=scored, top_k=max_download)
            msg2 = f"Selected {len(final_papers)} highly relevant papers to ingest!"
            st.success(msg2)
            st.session_state["ingest_logs"].append("✅ " + msg2)
            
            for p in final_papers:
                pass_msg = f"- **Passed Filter:** {p.title}"
                st.markdown(pass_msg)
                st.session_state["ingest_logs"].append(pass_msg)
            
            st.write(f"**Step 4:** Downloading & Indexing PDFs...")
            for paper in final_papers:
                st.write(f"⬇️ Downloading {paper.arxiv_id}...")
                p = fetcher.download_pdf(paper)
                if p.pdf_path:
                    st.write(f"✂️ Chunking and Embedding {paper.arxiv_id}...")
                    meta = {"arxiv_id": p.arxiv_id, "title": p.title}
                    chunks = parser.process_document(p.pdf_path, meta)
                    if chunks:
                        texts = [c.content for c in chunks]
                        metadatas = [c.metadata for c in chunks]
                        vector_store.add_documents(texts, metadatas)
                        final_msg = f"✅ Ingested {len(texts)} chunks for {p.arxiv_id} into Hybrid Store."
                        st.write(final_msg)
                        st.session_state["ingest_logs"].append(final_msg)
            
            status.update(label="Pipeline Successfully Completed!", state="complete", expanded=False)

    # Render previous logs if not running
    elif "ingest_logs" in st.session_state and st.session_state["ingest_logs"]:
        st.markdown("### 📜 Previous Ingestion Results (Saved)")
        st.info("The agents previously found & embedded the following data:")
        for log in st.session_state["ingest_logs"]:
            st.markdown(log)

with tab2:
    st.header("2. RAG Q&A (Hybrid RRF Search)")
    st.markdown("Ask deep questions about the ingested PDFs. The Agent uses BM25 + Dense Vectors (RRF) to retrieve contexts.")
    
    user_q = st.text_input("Ask a question:", "What does the paper say about evaluating LLM agent capabilities?")
    
    if st.button("Ask Agent", type="primary"):
        vector_store = VectorStoreManager()
        agent = RAGAgent(vector_store)
        
        with mlflow.start_run() as run:
            # Save run details to session state for feedback attachment
            st.session_state["last_run_id"] = run.info.run_id
            st.session_state["last_question"] = user_q
            mlflow.log_param("user_query", user_q)
            
            start_time = time.time()
            
            with st.status("Agent Thinking...", expanded=True) as status:
                st.write("🔍 Searching Vector DB & BM25 with Reciprocal Rank Fusion...")
                
                # Retrieve top 10 chunks for the LLM to have massive context
                retrieved_docs = vector_store.search(user_q, k=10)
                
                # Show only Top 3 to the user to avoid UI clutter
                for i, (doc, score) in enumerate(retrieved_docs[:3]):
                    with st.expander(f"Top Context {i+1} (RRF Score: {score:.4f})"):
                        st.json(doc.metadata)
                        st.write(doc.page_content)
                        
                if len(retrieved_docs) > 3:
                    st.write(f"... and {len(retrieved_docs) - 3} more chunks sent privately to the LLM.")
                
                st.write("🧠 Generating final synthesis with Gemini...")
                # Pass the exact 10 retrieved chunks so it doesn't double-query DB
                answer = agent.answer_question(user_q, retrieved_docs=retrieved_docs)
                
                status.update(label="Response Ready!", state="complete", expanded=False)
                
            latency = time.time() - start_time
            mlflow.log_metric("latency_seconds", latency)
            st.session_state["last_answer"] = answer
            
    # Draw the answer and feedback UI independently of the Ask button
    if "last_answer" in st.session_state:
        st.markdown("### 💬 Final Agent Answer")
        st.info(st.session_state["last_answer"])
        
        st.markdown("#### 🔄 Rate this answer to improve the model (Feedback Loop)")
        colA, colB, _ = st.columns([1, 1, 4])
        with colA:
            if st.button("👍 Accurate"):
                with mlflow.start_run(run_id=st.session_state["last_run_id"]):
                    mlflow.log_metric("user_feedback_score", 1.0)
                st.success("Positive feedback logged to MLflow Dashboard!")
        with colB:
            if st.button("👎 Inaccurate / Hallucination"):
                with mlflow.start_run(run_id=st.session_state["last_run_id"]):
                    mlflow.log_metric("user_feedback_score", 0.0)
                st.warning("Negative feedback logged. This trace will be reviewed for prompt optimization.")

with tab3:
    st.header("3. LangGraph Multi-Agent Orchestration")
    st.markdown("Interact with the **Clarification Agent**. It analyzes your intent using Semantic Routing and actively questions vague prompts before triggering execution.")
    
    from agent.graph import build_graph
    from langchain_core.messages import HumanMessage, AIMessage
    
    if "graph_instance" not in st.session_state:
        st.session_state["graph_instance"] = build_graph()
        
    if "phase3_messages" not in st.session_state:
        st.session_state["phase3_messages"] = [AIMessage(content="Hello! I am your AI Research Router. What would you like to build or research today?")]
        
    # Chat container
    chat_container = st.container(height=500)
    with chat_container:
        for msg in st.session_state["phase3_messages"]:
            role = "user" if isinstance(msg, HumanMessage) else "assistant"
            with st.chat_message(role):
                st.markdown(msg.content)
                
    # Input
    if user_input := st.chat_input("Ex: 'Find me papers on AI agents' or 'What does our Github repo AST look like?'"):
        with chat_container:
            with st.chat_message("user"):
                st.markdown(user_input)
                
        st.session_state["phase3_messages"].append(HumanMessage(content=user_input))
        
        with st.spinner("LangGraph is routing your request..."):
            initial_state = {"messages": st.session_state["phase3_messages"]}
            # Since we haven't implemented SQLite checkpointer memory yet, we pass the whole thread
            result = st.session_state["graph_instance"].invoke(initial_state)
            
        # Update state immediately
        st.session_state["phase3_messages"] = result["messages"]
        
        with chat_container:
            new_msg = result["messages"][-1]
            if isinstance(new_msg, AIMessage):
                with st.chat_message("assistant"):
                    st.markdown(new_msg.content)
                    
            with st.expander("🔍 LangGraph Internal State Trace", expanded=True):
                st.json({
                    "is_clarified": result.get("is_clarified"),
                    "current_intent": result.get("current_intent"),
                    "extracted_requirements": result.get("requirements", {})
                })
