"""
Researcher node adapters for the DART MAS graph.

This node performs scoped semantic retrieval over narrative chunks and uses an
LLM summarizer to produce a grounded contextual answer.
"""

from __future__ import annotations

import os
from typing import Any, Callable, Dict, Iterable, List, Optional, Protocol, Sequence

from dotenv import load_dotenv
from langchain_core.documents import Document
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI

from src.agent.mas_types import AgentTask, Artifact, MultiAgentState, TaskStatus
from src.storage.vector_store import VectorStoreManager

load_dotenv()


class ResearcherCoreRunner(Protocol):
    def run(self, query: str, *, report_scope: Dict[str, Any] | None = None) -> Dict[str, Any]:
        ...


def _trace(message: str) -> List[str]:
    return [message]


def _iter_researcher_tasks(state: MultiAgentState) -> Iterable[tuple[str, AgentTask]]:
    tasks = state.get("tasks", {}) or {}
    for task_id, task in tasks.items():
        if task["assignee"] != "Researcher":
            continue
        if task["status"] not in {TaskStatus.PENDING, TaskStatus.REJECTED_BY_CRITIC}:
            continue
        yield task_id, task


def _dedupe_preserve_order(values: Sequence[str]) -> List[str]:
    seen: set[str] = set()
    ordered: List[str] = []
    for value in values:
        item = str(value or "").strip()
        if not item or item in seen:
            continue
        seen.add(item)
        ordered.append(item)
    return ordered


def _build_where_filter(report_scope: Dict[str, Any] | None) -> Optional[Dict[str, Any]]:
    scope = dict(report_scope or {})
    conditions: List[Dict[str, Any]] = []

    company = str(scope.get("company") or "").strip()
    if company:
        conditions.append({"company": company})

    year_raw = scope.get("year")
    try:
        if year_raw not in (None, ""):
            conditions.append({"year": int(year_raw)})
    except (TypeError, ValueError):
        pass

    report_type = str(scope.get("report_type") or "").strip()
    if report_type:
        conditions.append({"report_type": report_type})

    rcept_no = str(scope.get("rcept_no") or "").strip()
    if rcept_no:
        conditions.append({"rcept_no": rcept_no})

    if not conditions:
        return None
    if len(conditions) == 1:
        return conditions[0]
    return {"$and": conditions}


def _build_enriched_query(query: str, report_scope: Dict[str, Any] | None) -> str:
    scope = dict(report_scope or {})
    parts = [
        str(scope.get("company") or "").strip(),
        str(scope.get("year") or "").strip(),
        str(scope.get("report_type") or "").strip(),
        str(scope.get("consolidation") or "").strip(),
        query.strip(),
    ]
    return " ".join(part for part in parts if part)


def _select_narrative_docs(docs: Sequence[Any], limit: int) -> List[tuple[Document, float]]:
    paragraphs: List[tuple[Document, float]] = []
    fallback_tables: List[tuple[Document, float]] = []
    for item in docs:
        if not isinstance(item, tuple) or not item:
            continue
        doc, score = item
        if not isinstance(doc, Document):
            continue
        block_type = str((doc.metadata or {}).get("block_type") or "").strip().lower()
        if block_type != "table":
            paragraphs.append((doc, float(score)))
        else:
            fallback_tables.append((doc, float(score)))
    ranked = sorted(paragraphs, key=lambda row: row[1], reverse=True)
    if len(ranked) < limit:
        ranked.extend(sorted(fallback_tables, key=lambda row: row[1], reverse=True)[: limit - len(ranked)])
    return ranked[:limit]


def _format_doc_anchor(metadata: Dict[str, Any]) -> str:
    return (
        f"[{metadata.get('company', '?')} | {metadata.get('year', '?')} | "
        f"{metadata.get('section_path', metadata.get('section', '?'))}]"
    )


def _format_context_docs(vsm: VectorStoreManager, docs: Sequence[tuple[Document, float]], limit: int = 5) -> str:
    parts: List[str] = []
    seen_parents: set[str] = set()
    for doc, score in list(docs)[:limit]:
        metadata = dict(doc.metadata or {})
        anchor = _format_doc_anchor(metadata)
        parent_id = str(metadata.get("parent_id") or "")
        text = str(doc.page_content or "")
        if parent_id and parent_id not in seen_parents:
            parent_text = vsm.get_parent(parent_id)
            if parent_text:
                seen_parents.add(parent_id)
                text = parent_text
        elif parent_id and parent_id in seen_parents:
            continue

        table_context = str(metadata.get("table_context") or "").strip()
        if table_context and table_context not in text:
            text = f"[table_context] {table_context}\n{text}"
        parts.append(f"{anchor} | score={score:.3f}\n{text}")
    return "\n\n---\n\n".join(parts)


def _extract_doc_links(retrieved_docs: Sequence[Any]) -> List[str]:
    links: List[str] = []
    for item in retrieved_docs or []:
        doc = item[0] if isinstance(item, tuple) and item else item
        if not isinstance(doc, Document):
            continue
        metadata = doc.metadata or {}
        for key in ("chunk_uid", "section_path", "parent_id"):
            value = str(metadata.get(key) or "").strip()
            if value:
                links.append(value)
                break
    return _dedupe_preserve_order(links)


class NarrativeResearcherCore:
    def __init__(self, vector_store_manager: VectorStoreManager, *, k: int = 6) -> None:
        self.vsm = vector_store_manager
        self.k = k

        api_key = os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY environment variable is required.")

        self.llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0)
        self.prompt = ChatPromptTemplate.from_template(
            """당신은 DART 공시 문서를 읽고 맥락을 요약하는 리서처입니다.

아래 검색 컨텍스트만 사용해서 질문에 답하세요.
- 질문과 직접 관련된 사실만 2~4문장으로 요약하세요.
- 컨텍스트에 없는 내용은 추가하지 마세요.
- 모르면 '현재 검색된 문맥만으로는 확인하기 어렵습니다.'라고 답하세요.

질문:
{question}

컨텍스트:
{context}

답변:"""
        )

    def run(self, query: str, *, report_scope: Dict[str, Any] | None = None) -> Dict[str, Any]:
        where_filter = _build_where_filter(report_scope)
        enriched_query = _build_enriched_query(query, report_scope)
        raw_docs = self.vsm.search(enriched_query, k=max(self.k * 3, 12), where_filter=where_filter)
        selected_docs = _select_narrative_docs(raw_docs, limit=self.k)
        context = _format_context_docs(self.vsm, selected_docs, limit=min(self.k, 5))
        if not context:
            return {
                "answer": "현재 검색된 문맥만으로는 확인하기 어렵습니다.",
                "citations": [],
                "retrieved_docs": [],
                "summary_points": [],
            }

        answer = (self.prompt | self.llm | StrOutputParser()).invoke(
            {
                "question": query,
                "context": context,
            }
        )
        citations = [_format_doc_anchor(doc.metadata or {}) for doc, _ in selected_docs[:4]]
        summary_points = [line.strip("- ").strip() for line in answer.splitlines() if line.strip()]
        return {
            "answer": answer.strip(),
            "citations": _dedupe_preserve_order(citations),
            "retrieved_docs": selected_docs,
            "summary_points": summary_points[:4],
        }


def _build_evidence_pool_entries(task_id: str, result: Dict[str, Any]) -> List[Dict[str, Any]]:
    entries: List[Dict[str, Any]] = []
    for item in result.get("retrieved_docs", []) or []:
        doc = item[0] if isinstance(item, tuple) and item else item
        if not isinstance(doc, Document):
            continue
        metadata = dict(doc.metadata or {})
        entries.append(
            {
                "task_id": task_id,
                "creator": "Researcher",
                "kind": "retrieved_context",
                "source_anchor": _format_doc_anchor(metadata),
                "snippet": str(doc.page_content or "")[:280],
                "block_type": metadata.get("block_type"),
            }
        )
    return entries


def _build_researcher_artifact(task_id: str, result: Dict[str, Any]) -> Artifact:
    return {
        "task_id": task_id,
        "creator": "Researcher",
        "content": {
            "answer": str(result.get("answer") or "").strip(),
            "citations": list(result.get("citations", []) or []),
            "summary_points": list(result.get("summary_points", []) or []),
        },
        "evidence_links": _extract_doc_links(result.get("retrieved_docs", []) or []),
    }


def _is_successful_research_result(result: Dict[str, Any]) -> bool:
    return bool(str(result.get("answer") or "").strip())


def make_run_researcher(core_runner: ResearcherCoreRunner) -> Callable[[MultiAgentState], Dict[str, Any]]:
    def run_researcher(state: MultiAgentState) -> Dict[str, Any]:
        task_updates: Dict[str, AgentTask] = {}
        artifact_updates: Dict[str, Artifact] = {}
        evidence_pool_entries: List[Dict[str, Any]] = []
        trace: List[str] = []

        for task_id, task in _iter_researcher_tasks(state):
            was_retry = task["status"] == TaskStatus.REJECTED_BY_CRITIC
            try:
                result = core_runner.run(
                    task["instruction"],
                    report_scope=dict(state.get("report_scope") or {}),
                )
            except Exception as exc:
                task_updates[task_id] = {
                    **task,
                    "status": TaskStatus.FAILED,
                }
                trace.append(f"Researcher failed {task_id}: {exc}")
                continue

            if not _is_successful_research_result(result):
                task_updates[task_id] = {
                    **task,
                    "status": TaskStatus.FAILED,
                }
                trace.append(f"Researcher failed {task_id}: empty narrative result")
                continue

            artifact_updates[task_id] = _build_researcher_artifact(task_id, result)
            evidence_pool_entries.extend(_build_evidence_pool_entries(task_id, result))
            task_updates[task_id] = {
                **task,
                "status": TaskStatus.COMPLETED,
                "retry_count": task["retry_count"] + (1 if was_retry else 0),
            }
            trace_message = f"Researcher completed {task_id}"
            if was_retry:
                trace_message += " after critic retry"
            trace.append(trace_message)

        return {
            "tasks": task_updates,
            "artifacts": artifact_updates,
            "evidence_pool": evidence_pool_entries,
            "execution_trace": trace,
        }

    return run_researcher


def build_financial_researcher_node(
    vector_store_manager: VectorStoreManager,
    *,
    k: int = 6,
) -> Callable[[MultiAgentState], Dict[str, Any]]:
    return make_run_researcher(NarrativeResearcherCore(vector_store_manager, k=k))

