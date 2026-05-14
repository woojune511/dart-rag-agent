"""
Reconciliation mixin for the financial graph agent.

This module turns retrieved evidence into operand-ready candidate sets:
- build candidate rows/chunks from evidence and retrieved docs
- score and optionally rerank candidates per operand
- decide whether retrieval should retry or calculation can continue
"""

import logging
from typing import Any, Dict, List, Optional

from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate
from src.agent.financial_graph_helpers import *  # noqa: F401,F403
from src.agent.financial_graph_models import FinancialAgentState, ReconciliationCandidateRerank
from src.config import get_financial_ontology
from src.schema import ArtifactKind, TaskKind, TaskStatus

logger = logging.getLogger(__name__)

class FinancialAgentReconciliationMixin:
    def _build_reconciliation_candidates(self, state: FinancialAgentState) -> List[Dict[str, Any]]:
        """Build a mixed candidate pool from evidence items and retrieved docs.

        The pool intentionally includes both coarse chunks and more structured
        row-level candidates so later scoring can prefer precise numeric rows
        without losing narrative fallback context.
        """
        candidates: List[Dict[str, Any]] = []
        seen: set[str] = set()

        for item in list(state.get("evidence_items", []) or []):
            evidence_id = str(item.get("evidence_id") or "").strip()
            anchor = str(item.get("source_anchor") or "").strip()
            candidate_id = evidence_id or anchor
            if not candidate_id or candidate_id in seen:
                continue
            seen.add(candidate_id)
            text = " ".join(
                [
                    str(item.get("claim") or ""),
                    str(item.get("quote_span") or ""),
                    str(item.get("source_context") or ""),
                    str(item.get("raw_row_text") or ""),
                    anchor,
                ]
            )
            candidates.append(
                _build_reconciliation_candidate(
                    candidate_id=candidate_id,
                    anchor=anchor,
                    text=text,
                    metadata=dict(item.get("metadata") or {}),
                )
            )
            raw_row_text = _normalise_spaces(str(item.get("raw_row_text") or ""))
            if raw_row_text:
                row_candidate = _build_reconciliation_candidate(
                    candidate_id=f"{candidate_id}::raw_row",
                    anchor=anchor,
                    text=" ".join(
                        part
                        for part in (
                            raw_row_text,
                            str(item.get("source_context") or ""),
                            str(item.get("claim") or ""),
                            anchor,
                        )
                        if part
                    ),
                    metadata={**dict(item.get("metadata") or {}), "row_text": raw_row_text},
                    candidate_kind="evidence_row",
                    row_label=_extract_table_row_label(raw_row_text),
                )
                row_candidate_id = str(row_candidate.get("candidate_id") or "").strip()
                if row_candidate_id and row_candidate_id not in seen:
                    seen.add(row_candidate_id)
                    candidates.append(row_candidate)

        doc_stream: List[tuple[Any, Any]] = []
        for item in list(state.get("retrieved_docs", []) or []):
            doc_stream.append(item)
        for item in list(state.get("seed_retrieved_docs", []) or []):
            doc_stream.append(item)

        for index, (doc, _score) in enumerate(doc_stream, start=1):
            metadata = dict(doc.metadata or {})
            anchor = self._build_source_anchor(metadata)
            candidate_id = str(metadata.get("chunk_uid") or f"doc_{index}")
            if candidate_id in seen:
                continue
            seen.add(candidate_id)
            text = " ".join(
                [
                    str(doc.page_content or ""),
                    str(metadata.get("table_header_context") or ""),
                    str(metadata.get("section_path") or metadata.get("section") or ""),
                    anchor,
                ]
            )
            candidates.append(
                _build_reconciliation_candidate(
                    candidate_id=candidate_id,
                    anchor=anchor,
                    text=text,
                    metadata=metadata,
                )
            )
            if metadata.get("table_source_id"):
                for row_candidate in _build_table_row_reconciliation_candidates(
                    candidate_id_prefix=candidate_id,
                    anchor=anchor,
                    table_text=str(doc.page_content or ""),
                    metadata=metadata,
                ):
                    row_candidate_id = str(row_candidate.get("candidate_id") or "").strip()
                    if not row_candidate_id or row_candidate_id in seen:
                        continue
                    seen.add(row_candidate_id)
                    candidates.append(row_candidate)
        return candidates

    def _should_llm_rerank_candidates(
        self,
        scored_candidates: List[Dict[str, Any]],
    ) -> bool:
        """Escalate only ambiguous top candidates to the LLM reranker."""
        if len(scored_candidates) < 2:
            return False

        top = scored_candidates[0]
        second = scored_candidates[1]
        top_candidate = dict(top.get("candidate") or {})
        top_kind = str(top_candidate.get("candidate_kind") or "")
        score_gap = float(top.get("score") or 0.0) - float(second.get("score") or 0.0)
        top_kinds = {
            str(item.get("candidate", {}).get("candidate_kind") or "")
            for item in scored_candidates[:5]
        }

        if _candidate_is_descriptor_row(top_candidate):
            return True
        if top_kind == "chunk":
            return True
        if score_gap < 1.0:
            return True
        if "chunk" in top_kinds and any(
            kind in {"structured_row", "table_row", "evidence_row"}
            for kind in top_kinds
        ):
            return True
        return False

    def _llm_rerank_operand_candidates(
        self,
        *,
        query: str,
        operand: Dict[str, Any],
        scored_candidates: List[Dict[str, Any]],
    ) -> List[str]:
        top_candidates = scored_candidates[: min(5, len(scored_candidates))]
        if len(top_candidates) < 2:
            return [
                str(item.get("candidate", {}).get("candidate_id") or "").strip()
                for item in top_candidates
                if str(item.get("candidate", {}).get("candidate_id") or "").strip()
            ]

        option_lines: List[str] = []
        allowed_ids: List[str] = []
        for rank, item in enumerate(top_candidates, start=1):
            candidate = dict(item.get("candidate") or {})
            metadata = dict(candidate.get("metadata") or {})
            candidate_id = str(candidate.get("candidate_id") or "").strip()
            if not candidate_id:
                continue
            allowed_ids.append(candidate_id)
            preview = _normalise_spaces(
                str(metadata.get("row_text") or metadata.get("table_header_context") or candidate.get("text") or "")
            )[:280]
            option_lines.append(
                "\n".join(
                    [
                        f"[candidate {rank}]",
                        f"id: {candidate_id}",
                        f"kind: {candidate.get('candidate_kind')}",
                        f"section: {metadata.get('section_path') or metadata.get('section') or ''}",
                        f"statement_type: {metadata.get('statement_type') or ''}",
                        f"consolidation_scope: {metadata.get('consolidation_scope') or ''}",
                        f"row_label: {metadata.get('row_label') or ''}",
                        f"preview: {preview}",
                    ]
                )
            )

        if len(allowed_ids) < 2:
            return allowed_ids

        structured_llm = self.llm.with_structured_output(ReconciliationCandidateRerank)
        prompt = ChatPromptTemplate.from_template(
            """당신은 재무 계산 후보 재정렬기입니다.
질문과 target operand에 가장 잘 맞는 candidate_id를 best-first 순서로 정렬하세요.

우선순위:
1. 직접 숫자 값이 있는 표 row
2. 질문의 연결/별도, 기간, statement_type에 맞는 근거
3. narrative paragraph보다 table row / structured row
4. '범위', '하위범위', '상위범위' 같은 설명 row는 피하세요.

질문:
{query}

target operand:
{operand_label}

candidate options:
{options}
"""
        )
        try:
            reranked: ReconciliationCandidateRerank = (prompt | structured_llm).invoke(
                {
                    "query": query,
                    "operand_label": str(operand.get("label") or ""),
                    "options": "\n\n".join(option_lines),
                }
            )
        except Exception as exc:
            logger.info("[reconcile] llm rerank skipped operand=%s error=%s", operand.get("label"), exc)
            return allowed_ids

        ordered_ids: List[str] = []
        seen: set[str] = set()
        for candidate_id in reranked.ordered_candidate_ids:
            cleaned = str(candidate_id or "").strip()
            if cleaned and cleaned in allowed_ids and cleaned not in seen:
                seen.add(cleaned)
                ordered_ids.append(cleaned)
        for candidate_id in allowed_ids:
            if candidate_id not in seen:
                ordered_ids.append(candidate_id)
        return ordered_ids

    def _rerank_reconciliation_matches_with_llm(
        self,
        state: FinancialAgentState,
        result: Dict[str, Any],
        candidates: List[Dict[str, Any]],
        years: List[int],
    ) -> Dict[str, Any]:
        active_subtask = dict(state.get("active_subtask") or {})
        query = str(active_subtask.get("query") or state.get("query") or "")
        operand_specs = {
            str(item.get("label") or "").strip(): dict(item)
            for item in (active_subtask.get("required_operands") or [])
            if str(item.get("label") or "").strip()
        }
        preferred_statement_types = [
            str(item).strip()
            for item in (active_subtask.get("preferred_statement_types") or [])
            if str(item).strip()
        ]
        constraints = dict(active_subtask.get("constraints") or {})

        updated = dict(result or {})
        notes = [str(item).strip() for item in (updated.get("notes") or []) if str(item).strip()]
        reranked_rows: List[Dict[str, Any]] = []

        for row in (updated.get("matched_operands") or []):
            current = dict(row)
            label = str(current.get("label") or "").strip()
            operand = operand_specs.get(label)
            if not operand:
                reranked_rows.append(current)
                continue

            matches = [candidate for candidate in candidates if _candidate_matches_operand(candidate, operand)]
            scored_candidates = [
                {
                    "candidate": candidate,
                    "score": _score_operand_candidate(
                        candidate,
                        operand=operand,
                        preferred_statement_types=preferred_statement_types,
                        constraints=constraints,
                        query_years=years,
                    ),
                }
                for candidate in matches
            ]
            scored_candidates.sort(key=lambda item: item["score"], reverse=True)
            if not self._should_llm_rerank_candidates(scored_candidates):
                reranked_rows.append(current)
                continue

            ordered_ids = self._llm_rerank_operand_candidates(
                query=query,
                operand=operand,
                scored_candidates=scored_candidates,
            )
            if ordered_ids:
                current["candidate_ids"] = ordered_ids
                notes.append(f"llm_rerank:{label}")
            reranked_rows.append(current)

        updated["matched_operands"] = reranked_rows
        updated["notes"] = list(dict.fromkeys(notes))
        return updated

    def _evidence_items_from_reconciliation_matches(self, state: FinancialAgentState) -> List[Dict[str, Any]]:
        reconciliation_result = dict(state.get("reconciliation_result") or {})
        if str(reconciliation_result.get("status") or "") not in {"ready", "retry_retrieval", "insufficient_operands"}:
            return []

        candidate_map = {
            str(candidate.get("candidate_id") or "").strip(): candidate
            for candidate in self._build_reconciliation_candidates(state)
            if str(candidate.get("candidate_id") or "").strip()
        }
        items: List[Dict[str, Any]] = []
        seen: set[str] = set()
        for operand_match in (reconciliation_result.get("matched_operands") or []):
            for candidate_id in (operand_match.get("candidate_ids") or [])[:2]:
                current = candidate_map.get(str(candidate_id).strip())
                if not current:
                    continue
                evidence_id = f"recon::{candidate_id}"
                if evidence_id in seen:
                    continue
                seen.add(evidence_id)
                metadata = dict(current.get("metadata") or {})
                raw_row_text = _normalise_spaces(str(metadata.get("row_text") or ""))
                if not raw_row_text and str(current.get("candidate_kind") or "") == "structured_row":
                    row_label = str(metadata.get("row_label") or "").strip()
                    values = [
                        str(cell.get("value_text") or "").strip()
                        for cell in (metadata.get("structured_cells") or [])
                        if str(cell.get("value_text") or "").strip()
                    ]
                    raw_row_text = " | ".join([part for part in [row_label, *values] if part])
                claim = _normalise_spaces(str(current.get("text") or ""))
                items.append(
                    {
                        "evidence_id": evidence_id,
                        "source_anchor": str(current.get("source_anchor") or "").strip(),
                        "claim": claim[:1200],
                        "quote_span": claim[:240],
                        "support_level": "direct",
                        "question_relevance": "high",
                        "allowed_terms": [],
                        "source_context": str(metadata.get("table_header_context") or metadata.get("section_path") or "").strip(),
                        "raw_row_text": raw_row_text or None,
                        "metadata": metadata,
                    }
                )
        return items

    def _extract_structured_operands_from_reconciliation(self, state: FinancialAgentState) -> List[Dict[str, Any]]:
        reconciliation_result = dict(state.get("reconciliation_result") or {})
        if str(reconciliation_result.get("status") or "") != "ready":
            return []

        active_subtask = dict(state.get("active_subtask") or {})
        required_operands = [
            dict(item)
            for item in (active_subtask.get("required_operands") or [])
            if bool(item.get("required", True))
        ]
        if not required_operands:
            return []

        constraints = dict(active_subtask.get("constraints") or {})
        period_focus = str(constraints.get("period_focus") or "unknown").strip()
        query_years = _query_years_from_state(state)
        candidates = self._build_reconciliation_candidates(state)
        candidate_map = {
            str(candidate.get("candidate_id") or "").strip(): candidate
            for candidate in candidates
            if str(candidate.get("candidate_id") or "").strip()
        }

        match_map = {
            str(item.get("label") or "").strip(): dict(item)
            for item in (reconciliation_result.get("matched_operands") or [])
            if str(item.get("label") or "").strip()
        }

        operand_rows: List[Dict[str, Any]] = []
        for index, operand in enumerate(required_operands, start=1):
            label = str(operand.get("label") or "").strip()
            if not label:
                continue
            match_entry = match_map.get(label) or {}
            candidate_ids = [
                str(value).strip()
                for value in (match_entry.get("candidate_ids") or [])
                if str(value).strip()
            ]
            candidate: Optional[Dict[str, Any]] = None
            for candidate_id in candidate_ids:
                current = candidate_map.get(candidate_id)
                if not current:
                    continue
                if str(current.get("candidate_kind") or "") == "structured_row":
                    candidate = current
                    break
            if not candidate:
                continue

            metadata = dict(candidate.get("metadata") or {})
            cells = [dict(cell) for cell in (metadata.get("structured_cells") or []) if dict(cell)]
            if not cells and str(candidate.get("candidate_kind") or "") in {"table_row", "evidence_row"}:
                cells = _parse_unstructured_table_row_cells(str(metadata.get("row_text") or ""), metadata)
            if not cells:
                continue
            ranked_cells = sorted(
                cells,
                key=lambda cell: _score_structured_cell(
                    cell,
                    query_years=_operand_target_years(operand, query_years),
                    period_focus=_operand_period_focus(operand, period_focus),
                ),
                reverse=True,
            )
            selected_cell = ranked_cells[0] if ranked_cells else None
            if not selected_cell:
                continue

            raw_value = str(selected_cell.get("value_text") or "").strip()
            raw_unit = str(selected_cell.get("unit_hint") or metadata.get("unit_hint") or "").strip()
            normalized_value, normalized_unit = _normalise_operand_value(raw_value, raw_unit)
            if normalized_value is None:
                continue

            period = _structured_cell_period_text(
                selected_cell,
                _operand_target_years(operand, query_years),
                _operand_period_focus(operand, period_focus),
            )
            row_label = str(metadata.get("row_label") or label).strip() or label
            operand_rows.append(
                {
                    "operand_id": f"op_{index:03d}",
                    "evidence_id": str(candidate.get("candidate_id") or ""),
                    "source_anchor": candidate.get("source_anchor"),
                    "label": f"{period} {row_label}".strip(),
                    "raw_value": raw_value,
                    "raw_unit": raw_unit,
                    "normalized_value": normalized_value,
                    "normalized_unit": normalized_unit,
                    "period": period,
                    "table_source_id": metadata.get("table_source_id"),
                    "statement_type": metadata.get("statement_type"),
                    "consolidation_scope": metadata.get("consolidation_scope"),
                }
            )

        return operand_rows

    def _reconcile_retrieved_evidence(self, state: FinancialAgentState) -> Dict[str, Any]:
        """Match required operands to the best available evidence candidates."""
        active_subtask = dict(state.get("active_subtask") or {})
        years = _query_years_from_state(state)
        report_scope = dict(state.get("report_scope") or {})
        scope_year_raw = report_scope.get("year")
        try:
            if scope_year_raw not in (None, ""):
                scope_year = int(scope_year_raw)
                if scope_year not in years:
                    years = [scope_year, *years]
        except (TypeError, ValueError):
            pass

        candidates = self._build_reconciliation_candidates(state)
        retry_count = int(state.get("reconciliation_retry_count") or 0)
        result = _deterministic_reconcile_task(
            active_subtask=active_subtask,
            candidates=candidates,
            years=years,
            reconciliation_retry_count=retry_count,
        )
        result = self._rerank_reconciliation_matches_with_llm(
            state,
            result,
            candidates,
            years,
        )
        status = str(result.get("status") or "ready")
        logger.info(
            "[reconcile] status=%s task=%s candidates=%s missing=%s retry_count=%s",
            status,
            result.get("task_id"),
            len(candidates),
            len(result.get("missing_operands") or []),
            retry_count,
        )
        artifacts = list(state.get("artifacts") or [])
        tasks = list(state.get("tasks") or [])
        task_id = str(active_subtask.get("task_id") or "reconcile")
        artifact_id = f"reconcile:{task_id}:{len(artifacts) + 1:03d}"
        candidate_ids = [
            str(match_id).strip()
            for item in (result.get("matched_operands") or [])
            for match_id in (item.get("candidate_ids") or [])
            if str(match_id).strip()
        ]
        artifacts = _append_artifact(
            artifacts,
            artifact_id=artifact_id,
            task_id=task_id,
            kind=ArtifactKind.RECONCILIATION_RESULT,
            status=status,
            summary=f"reconciliation={status}",
            payload={"reconciliation_result": result},
            evidence_refs=candidate_ids,
        )
        tasks = _upsert_task(
            tasks,
            task_id=task_id,
            kind=TaskKind.RECONCILIATION,
            label=f"reconcile {active_subtask.get('metric_label') or active_subtask.get('metric_family') or task_id}",
            status=TaskStatus.COMPLETED if status == "ready" else TaskStatus.PARTIAL,
            query=str(active_subtask.get("query") or ""),
            metric_family=str(active_subtask.get("metric_family") or ""),
            constraints=dict(active_subtask.get("constraints") or {}),
            artifact_id=artifact_id,
        )
        updates: Dict[str, Any] = {
            "reconciliation_result": result,
            "tasks": tasks,
            "artifacts": artifacts,
        }
        if status == "retry_retrieval":
            updates.update(
                {
                    "retry_queries": list(result.get("retry_queries") or []),
                    "retry_reason": "missing_operands",
                    "reconciliation_retry_count": retry_count + 1,
                }
            )
        elif status == "insufficient_operands":
            metric_label = str(active_subtask.get("metric_label") or "해당 지표").strip()
            missing_operands = [str(item).strip() for item in (result.get("missing_operands") or []) if str(item).strip()]
            if missing_operands:
                answer = f"{metric_label} 계산에 필요한 값({', '.join(missing_operands)})을 문서 근거에서 충분히 확인하지 못해 계산할 수 없습니다."
            else:
                answer = f"{metric_label} 계산에 필요한 값을 문서 근거에서 충분히 확인하지 못해 계산할 수 없습니다."
            updates.update(
                {
                    "answer": answer,
                    "compressed_answer": answer,
                    "draft_points": [answer],
                    "retry_queries": [],
                    "retry_reason": "insufficient_operands",
                }
            )
        else:
            updates.update({"retry_queries": [], "retry_reason": ""})
        return updates

    def _apply_strict_filter(self, docs, predicate):
        filtered = [item for item in docs if predicate(item[0])]
        return filtered if filtered else docs

    def _supplement_section_seed_docs(self, state: FinancialAgentState) -> List[tuple[Document, float]]:
        query = state["query"]
        topic = state.get("topic") or query
        intent = state.get("intent") or state.get("query_type", "qa")
        section_terms = _supplement_section_terms_for_query(query, topic, intent)
        section_terms.extend(_active_preferred_sections(state, query, topic, intent))
        section_terms = list(dict.fromkeys(term for term in section_terms if term))
        if not section_terms:
            return []

        companies = {str(company).lower() for company in (state.get("companies") or [])}
        years = [int(year) for year in (state.get("years") or [])]
        multi_period = intent in {"comparison", "trend"} and len(years) > 1
        ratio_query = _is_ratio_percent_query(f"{query} {topic}")
        ontology = get_financial_ontology()
        metric_patterns = ontology.row_patterns(query, topic, intent)
        for spec in ontology.component_specs(query, topic, intent):
            metric_patterns.extend(re.escape(keyword) for keyword in spec.get("keywords", []))
        metric_patterns = list(dict.fromkeys(metric_patterns))
        active_operand_needles = [
            _normalise_spaces(needle)
            for operand in (dict(state.get("active_subtask") or {}).get("required_operands") or [])
            for needle in _operand_needles(dict(operand))
            if _normalise_spaces(needle)
        ]
        active_operand_needles = list(dict.fromkeys(active_operand_needles))

        supplemented: List[tuple[Document, float]] = []
        seen_chunk_uids: set[str] = set()
        for body, metadata in zip(self.vsm.bm25_docs, self.vsm.bm25_metadatas):
            metadata = dict(metadata or {})
            section_path = str(metadata.get("section_path") or metadata.get("section") or "")
            body_text = _normalise_spaces(str(body or ""))
            table_context = _normalise_spaces(str(metadata.get("table_context") or ""))
            section_surface = " ".join(part for part in (section_path, table_context, body_text[:400]) if part)
            if not any(term in section_surface for term in section_terms):
                continue
            company = str(metadata.get("company", "")).lower()
            if companies and company not in companies and not any(target in company or company in target for target in companies):
                continue
            if years and not multi_period:
                year_value = metadata.get("year")
                if int(year_value or 0) not in set(years):
                    continue

            chunk_uid = str(metadata.get("chunk_uid") or "")
            if chunk_uid and chunk_uid in seen_chunk_uids:
                continue
            seen_chunk_uids.add(chunk_uid)

            text = _normalise_spaces(f"{table_context}\n{body_text}")
            score = 0.02
            if "연구개발 활동" in section_path or "연구개발활동" in section_path:
                score += 0.03
            if ratio_query and metric_patterns and any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in metric_patterns):
                score += 0.04
            if metric_patterns and any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in ontology.row_patterns(query, topic, intent)):
                score += 0.06
            if active_operand_needles and any(needle in text for needle in active_operand_needles):
                score += 0.08

            supplemented.append((Document(page_content=str(body or ""), metadata=metadata), score))

        supplemented.sort(key=lambda item: item[1], reverse=True)
        if supplemented:
            logger.info(
                "[retrieve] supplemental section seeds=%s for terms=%s",
                len(supplemented[:6]),
                section_terms,
            )
        return supplemented[:6]

    def _is_reflection_eligible(self, state: FinancialAgentState) -> bool:
        intent = state.get("intent") or state.get("query_type", "qa")
        return intent in {"comparison", "trend"}

    def _infer_missing_info(self, state: FinancialAgentState, operands: Optional[List[Dict[str, Any]]] = None) -> List[str]:
        query = self._calc_query(state)
        topic = self._calc_topic(state)
        intent = state.get("intent") or state.get("query_type", "qa")
        years = [int(year) for year in (state.get("years") or [])]
        ontology = get_financial_ontology()
        metric_key = self._calc_metric_family(state)
        metric_info = ontology.metric_family(metric_key) if metric_key else None

        inferred: List[str] = []
        if metric_info:
            display_name = str(metric_info.get("display_name") or "").strip()
            if display_name and _is_ratio_percent_query(query):
                if years:
                    inferred.extend(f"{year}년 {display_name}" for year in years)
                else:
                    inferred.append(display_name)
            for component in (metric_info.get("components") or {}).values():
                component_name = str((component or {}).get("name") or "").strip()
                if not component_name:
                    continue
                if years:
                    inferred.extend(f"{year}년 {component_name}" for year in years)
                else:
                    inferred.append(component_name)

        if not inferred and years:
            inferred.extend(f"{year}년 {topic}" for year in years)
        if not inferred:
            inferred.append(topic)

        cleaned_inferred: List[str] = []
        for item in inferred:
            cleaned = _normalise_spaces(re.sub(r"(비교|차이|대비|합계)\s*$", "", str(item or "")))
            if cleaned:
                cleaned_inferred.append(cleaned)
        inferred = cleaned_inferred or inferred

        if operands:
            operand_text = " ".join(
                _normalise_spaces(
                    " ".join(
                        [
                            str(row.get("label") or ""),
                            str(row.get("raw_value") or ""),
                            str(row.get("period") or ""),
                        ]
                    )
                )
                for row in operands
            )
            filtered: List[str] = []
            for candidate in inferred:
                candidate_tokens = [token for token in re.findall(r"[가-힣A-Za-z0-9]+", candidate) if len(token) >= 2]
                if candidate_tokens and all(token in operand_text for token in candidate_tokens):
                    continue
                filtered.append(candidate)
            inferred = filtered or inferred

        return list(dict.fromkeys(item for item in inferred if item))

    def _build_retry_queries(self, state: FinancialAgentState, missing_info: List[str]) -> List[str]:
        companies = [str(company).strip() for company in (state.get("companies") or []) if str(company).strip()]
        if not companies:
            for doc, _score in (state.get("seed_retrieved_docs") or []):
                company = str((doc.metadata or {}).get("company") or "").strip()
                if company:
                    companies.append(company)
                    break
        years = [str(int(year)) for year in (state.get("years") or [])]
        query = state["query"]
        topic = state.get("topic") or query
        intent = state.get("intent") or state.get("query_type", "qa")
        preferred_sections = _preferred_calc_sections(query, topic, intent)

        queries: List[str] = []
        for item in missing_info:
            parts: List[str] = []
            if companies:
                parts.extend(companies)
            if years:
                parts.extend(years)
            parts.append(item)
            if preferred_sections:
                parts.extend(preferred_sections[:2])
            queries.append(_normalise_spaces(" ".join(parts)))
        return list(dict.fromkeys(query_text for query_text in queries if query_text))

    def _heuristic_reflection_query_plan(
        self,
        state: FinancialAgentState,
        operands: List[Dict[str, Any]],
        retry_objective: str = "generic_retry",
        explanation: str = "",
    ) -> Dict[str, Any]:
        missing_info = [
            str(item).strip()
            for item in (state.get("missing_info") or [])
            if str(item).strip()
        ]
        if not missing_info:
            missing_info = self._infer_missing_info(state, operands)
        subqueries = self._build_retry_queries(state, missing_info)
        preferred_sections = _preferred_calc_sections(
            state["query"],
            state.get("topic") or state["query"],
            state.get("intent") or state.get("query_type", "qa"),
        )
        return {
            "status": "ready" if subqueries else "skip",
            "retry_objective": retry_objective if subqueries else "generic_retry",
            "missing_info": missing_info,
            "subqueries": subqueries,
            "preferred_sections": preferred_sections,
            "explanation": explanation or "heuristic retry query plan",
        }

    def _finalize_retry_queries(
        self,
        state: FinancialAgentState,
        reflection_plan: Dict[str, Any],
        missing_info: List[str],
    ) -> List[str]:
        base_queries = [
            _normalise_spaces(str(item))
            for item in (reflection_plan.get("subqueries") or [])
            if _normalise_spaces(str(item))
        ]
        if not base_queries:
            base_queries = self._build_retry_queries(state, missing_info)

        retry_objective = str(reflection_plan.get("retry_objective") or "")
        if retry_objective in {
            "find_missing_values",
            "resolve_binding",
            "find_direct_row",
        }:
            for item in missing_info[:2]:
                normalized = _normalise_spaces(str(item))
                if normalized:
                    base_queries.append(normalized)

        companies = [str(company).strip() for company in (state.get("companies") or []) if str(company).strip()]
        report_company_hint = ""
        for doc, _score in (state.get("seed_retrieved_docs") or []):
            company = str((doc.metadata or {}).get("company") or "").strip()
            if company:
                report_company_hint = company
                break
        if not report_company_hint:
            for doc, _score in (state.get("retrieved_docs") or []):
                company = str((doc.metadata or {}).get("company") or "").strip()
                if company:
                    report_company_hint = company
                    break

        global_preferred_sections = _preferred_calc_sections(
            state["query"],
            state.get("topic") or state["query"],
            state.get("intent") or state.get("query_type", "qa"),
        )
        preferred_sections = [
            _section_hint_alias(section)
            for section in (
                global_preferred_sections
                + list(reflection_plan.get("preferred_sections") or [])
            )
            if _section_hint_alias(section)
        ]
        preferred_sections = list(dict.fromkeys(preferred_sections))

        if preferred_sections and retry_objective in {
            "find_direct_row",
            "resolve_binding",
        }:
            for item in missing_info[:2]:
                normalized = _normalise_spaces(str(item))
                if not normalized:
                    continue
                for hint in preferred_sections[:2]:
                    base_queries.append(_normalise_spaces(f"{normalized} {hint}"))

        finalized: List[str] = []
        for query_text in base_queries:
            normalized_query = _normalise_spaces(query_text)
            for raw_section in (reflection_plan.get("preferred_sections") or []):
                alias = _section_hint_alias(str(raw_section))
                raw_section_text = _normalise_spaces(str(raw_section))
                if raw_section_text and alias:
                    normalized_query = normalized_query.replace(raw_section_text, alias)
            parts: List[str] = []
            lowered = normalized_query.lower()
            if report_company_hint and report_company_hint.lower() not in lowered:
                parts.append(report_company_hint)
            parts.append(normalized_query)
            finalized.append(_normalise_spaces(" ".join(parts)))

        return list(dict.fromkeys(item for item in finalized if item))

    def _plan_reflection_retry(self, state: FinancialAgentState) -> Dict[str, Any]:
        operands = list(state.get("calculation_operands", []) or [])
        plan = dict(state.get("calculation_plan") or {})
        calc_result = dict(state.get("calculation_result") or {})
        query = state["query"]
        topic = state.get("topic") or query
        intent = state.get("intent") or state.get("query_type", "qa")
        years = [int(year) for year in (state.get("years") or [])]
        companies = [str(company).strip() for company in (state.get("companies") or []) if str(company).strip()]
        preferred_sections = _preferred_calc_sections(query, topic, intent)

        missing_info = [
            str(item).strip()
            for item in (plan.get("missing_info") or state.get("missing_info") or [])
            if str(item).strip()
        ]
        if not missing_info:
            missing_info = self._infer_missing_info(state, operands)

        ratio_query = _is_ratio_percent_query(query)
        percent_point_query = _is_percent_point_difference_query(query)
        sum_query = any(token in query for token in ["합계", "합산", "합친", "합한"])
        fallback_retry_objective = "generic_retry"
        if percent_point_query:
            fallback_retry_objective = "find_direct_row"
        elif ratio_query and len(operands) < 2:
            fallback_retry_objective = "find_missing_values"
        elif sum_query:
            fallback_retry_objective = "find_missing_values"
        elif years and len(years) > 1:
            fallback_retry_objective = "resolve_binding"
        elif re.search(r"\bvs\b|와|과", query):
            fallback_retry_objective = "resolve_binding"
        elif not operands:
            fallback_retry_objective = "find_missing_values"

        seed_sections: List[str] = []
        for doc, _score in (state.get("seed_retrieved_docs") or [])[:6]:
            section_path = str((doc.metadata or {}).get("section_path") or (doc.metadata or {}).get("section") or "").strip()
            if section_path:
                seed_sections.append(section_path)
        seed_sections = list(dict.fromkeys(seed_sections))

        ontology = get_financial_ontology()
        metric_key = str(state.get("target_metric_family") or "")
        metric_info = ontology.metric_family(metric_key) if metric_key else None
        ontology_lines: List[str] = []
        if metric_info:
            ontology_lines.append(f"- key={metric_info.get('key', '')}")
            ontology_lines.append(f"- display_name={metric_info.get('display_name', '')}")
            ontology_lines.append(f"- result_unit={metric_info.get('result_unit', '')}")
            formula_template = str(metric_info.get("formula_template") or "").strip()
            if formula_template:
                ontology_lines.append(f"- formula_template={formula_template}")
            components = metric_info.get("components") or {}
            if components:
                ontology_lines.append("- components:")
                for role, component in components.items():
                    component_name = str((component or {}).get("name") or "").strip()
                    component_keywords = [str(keyword).strip() for keyword in ((component or {}).get("keywords") or []) if str(keyword).strip()]
                    ontology_lines.append(
                        f"  - {role}: {component_name} | keywords={component_keywords}"
                    )
        ontology_context = "\n".join(ontology_lines) or "-"

        operand_lines = [
            (
                f"- {row.get('operand_id', '')} | label={row.get('label', '')} | "
                f"raw={row.get('raw_value', '')} {row.get('raw_unit', '')} | "
                f"normalized={row.get('normalized_value', '')} {row.get('normalized_unit', '')} | "
                f"period={row.get('period', '')}"
            )
            for row in operands
        ]
        seed_section_text = "\n".join(f"- {section}" for section in seed_sections) or "-"
        operand_text = "\n".join(operand_lines) or "-"
        plan_text = json.dumps(plan, ensure_ascii=False, indent=2) if plan else "{}"
        calc_result_text = json.dumps(calc_result, ensure_ascii=False, indent=2) if calc_result else "{}"
        heuristic_plan = self._heuristic_reflection_query_plan(
            state,
            operands,
            retry_objective=fallback_retry_objective,
            explanation="fallback reflection query plan",
        )

        structured_llm = self.llm.with_structured_output(ReflectionQueryPlan)
        prompt = ChatPromptTemplate.from_template(
            """당신은 재무 RAG 에이전트의 reflection planner 입니다.
현재 검색/계산이 실패했을 때, 무엇이 부족한지 진단하고 retrieval-friendly 재검색 쿼리를 1~3개 설계하세요.

목표:
- 사용자 질문의 의도를 유지한 채
- 현재 파이프라인이 다시 검색했을 때 누락된 피연산자나 비율 행을 찾기 쉬운 쿼리로 재정의하세요.

규칙:
- status는 재검색이 의미 있으면 ready, 아니면 skip.
- retry_objective는 이번 재검색의 목적만 고르세요.
  - find_missing_values: 필요한 값 일부가 빠졌음
  - find_direct_row: 질문이 요구하는 직접적인 row/요약값을 찾고 싶음
  - resolve_binding: 기간/대상/레이블 연결을 더 명확히 하고 싶음
  - generic_retry: 위 셋으로 충분히 설명되지 않음
- missing_info에는 현재 컨텍스트에 부족한 정보만 적으세요.
- subqueries는 1~3개만 만드세요.
- 각 subquery는 자연어 장문이 아니라 retrieval-friendly keyword query여야 합니다.
- subquery에는 가능한 한 회사명, 연도, 부족한 metric/entity, 짧은 섹션 힌트를 포함하세요.
- 질문이 %p 차이나 두 비율 비교라면, 먼저 같은 metric의 기간별/대상별 비율 row를 찾는 쿼리를 우선하세요.
- 질문이 비율/이익률 계산인데 비율 row가 없으면, 분자/분모 component를 각각 찾는 쿼리를 만드세요.
- 질문이 합계라면, 합쳐야 하는 구성 항목별 수치를 따로 찾는 쿼리를 만드세요.
- preferred_sections는 재검색에서 특히 유력한 섹션 힌트만 짧게 넣으세요.
- 기존 seed sections에 이미 충분히 있는 정보를 그대로 반복하지 말고, 부족한 부분을 겨냥하세요.
- 하드 필터는 코드가 따로 처리하므로, 기업/연도는 query text에 포함하되 너무 장황하게 쓰지 마세요.

질문: {query}
의도: {intent}
주제: {topic}
기업: {companies}
연도: {years}

현재 실패 추정:
- fallback_retry_objective={retry_objective}
- missing_info(heuristic)={missing_info}

Ontology Context:
{ontology_context}

현재 확보한 피연산자:
{operands}

현재 계산 계획:
{plan_text}

현재 계산 결과:
{calc_result_text}

현재 seed sections:
{seed_sections}

참고용 heuristic retry plan:
{heuristic_plan}
"""
        )
        try:
            reflection_plan: ReflectionQueryPlan = (prompt | structured_llm).invoke(
                {
                    "query": query,
                    "intent": intent,
                    "topic": topic,
                    "companies": companies or ["-"],
                    "years": years or ["-"],
                    "retry_objective": fallback_retry_objective,
                    "missing_info": missing_info or ["-"],
                    "ontology_context": ontology_context,
                    "operands": operand_text,
                    "plan_text": plan_text,
                    "calc_result_text": calc_result_text,
                    "seed_sections": seed_section_text,
                    "heuristic_plan": json.dumps(heuristic_plan, ensure_ascii=False, indent=2),
                }
            )
            plan_data = reflection_plan.model_dump()
            plan_data["missing_info"] = [
                str(item).strip()
                for item in (plan_data.get("missing_info") or [])
                if str(item).strip()
            ]
            plan_data["subqueries"] = [
                _normalise_spaces(str(item))
                for item in (plan_data.get("subqueries") or [])
                if _normalise_spaces(str(item))
            ]
            plan_data["preferred_sections"] = [
                _normalise_spaces(str(item))
                for item in (plan_data.get("preferred_sections") or [])
                if _normalise_spaces(str(item))
            ]
            if not plan_data["missing_info"]:
                plan_data["missing_info"] = missing_info
            if not plan_data["preferred_sections"]:
                plan_data["preferred_sections"] = preferred_sections[:3]
            if not plan_data["subqueries"]:
                plan_data = heuristic_plan
                plan_data["explanation"] = "fallback to heuristic because reflection planner returned no subqueries"
            logger.info(
                "[reflection_replan] status=%s retry_objective=%s subqueries=%s",
                plan_data.get("status"),
                plan_data.get("retry_objective"),
                len(plan_data.get("subqueries") or []),
            )
            return {
                "reflection_plan": plan_data,
                "missing_info": plan_data.get("missing_info", []),
                "retry_reason": str(plan_data.get("explanation") or ""),
                "planner_debug_trace": {
                    **dict(state.get("planner_debug_trace") or {}),
                    "reflection_plan": plan_data,
                    "reflection_seed_sections": seed_sections,
                    "reflection_llm_invoked": True,
                },
            }
        except Exception as exc:
            logger.warning("[reflection_replan] structured output failed: %s", exc)
            fallback_plan = heuristic_plan
            fallback_plan["explanation"] = f"heuristic fallback after reflection planner error: {exc}"
            return {
                "reflection_plan": fallback_plan,
                "missing_info": fallback_plan.get("missing_info", []),
                "retry_reason": str(fallback_plan.get("explanation") or ""),
                "planner_debug_trace": {
                    **dict(state.get("planner_debug_trace") or {}),
                    "reflection_plan": fallback_plan,
                    "reflection_seed_sections": seed_sections,
                    "reflection_llm_invoked": True,
                    "reflection_error": str(exc),
                },
            }

