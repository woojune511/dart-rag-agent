"""Retrieval pipeline owner for the FinancialAgent graph.

This module owns retrieval query construction, filtering, search execution,
reranking, candidate selection, and retrieval trace projection. All answer
kinds use the same source selection and continue through the Compiler.
"""

from __future__ import annotations

from copy import deepcopy
import logging
import json
import re
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from src.agent.financial_graph_retrieval_budget import (
    apply_query_budget,
    cross_trace_reuse_candidate_diagnostics,
    drop_duplicate_executed_query,
    drop_queries_already_selected,
    limit_query_context_terms,
    lookup_query_result_cache,
    query_budget_int,
    store_query_result_cache,
    summarize_executed_query_telemetry,
)
from src.agent.financial_langchain_loaders import document
from src.agent.financial_retrieval_hints import (
    _active_preferred_sections,
    _active_preferred_statement_types,
    retrieval_hint_from_topic,
    supplement_section_terms_for_query,
)
from src.agent.financial_runtime_normalization import (
    _inline_numeric_unit_match,
    _normalise_spaces,
    _parse_number_text,
)
from src.agent.financial_runtime_trace import resolve_runtime_calculation_trace
from src.agent.financial_source_scope import source_section_allowed_for_query
from src.agent.financial_scope_policies import (
    is_scope_only_period_surface,
    metadata_period_match_strength,
    report_scope_source_receipts,
    should_apply_strict_company_scope,
)
from src.agent.financial_text_surface import (
    strip_index_metadata_prefix,
    strip_rerank_metadata,
    tokenize_terms,
)
from src.config.report_scoped_cache import classify_report_cache_consumer_candidate
from src.config.retrieval_policy import (
    METRIC_TOPIC_EXTRACTION_TERMS,
    NARRATIVE_RERANK_POLICY,
    SEMANTIC_REQUIRED_EVIDENCE_POLICY,
)
from src.routing import default_format_preference
from src.storage.bm25_index import metadata_matches_filter
from src.storage.search_scope import restrict_search_filter
if TYPE_CHECKING:
    from langchain_core.documents import Document

    from src.agent.financial_graph_state import FinancialAgentState, RetrievalInput, RetrievalPhase


logger = logging.getLogger(__name__)


def _retrieval_document_source_id(doc: Any) -> str:
    """Use globally qualified parser identity, not a filing-local row number."""
    metadata = dict(getattr(doc, "metadata", {}) or {})
    source_id = str(metadata.get("chunk_uid") or "").strip()
    if source_id:
        return source_id
    chunk_id = metadata.get("chunk_id")
    if chunk_id is None or str(chunk_id).strip() == "":
        return ""
    for key in ("rcept_no", "document_id", "source_document_id"):
        document_id = str(metadata.get(key) or "").strip()
        if document_id and document_id.lower() not in {"unknown", "none", "null"}:
            return json.dumps([key, document_id, str(chunk_id)], ensure_ascii=False)
    # Company/year/report type do not establish a unique filing. Unknown
    # sources stay separate rather than borrowing authority from a local index.
    return ""


def _stable_retrieval_source_ids(entries: List[Any]) -> tuple[List[str], int]:
    source_ids: List[str] = []
    seen: set[str] = set()
    unidentified_count = 0
    for entry in entries:
        doc = entry[0] if isinstance(entry, (tuple, list)) and entry else entry
        metadata = dict(getattr(doc, "metadata", {}) or {})
        source_id = str(
            metadata.get("chunk_uid")
            or metadata.get("chunk_id")
            or metadata.get("id")
            or ""
        ).strip()
        if not source_id:
            unidentified_count += 1
            continue
        if source_id in seen:
            continue
        seen.add(source_id)
        source_ids.append(source_id)
    return source_ids, unidentified_count


def _metric_terms_from_topic(topic: str) -> set[str]:
    text = _normalise_spaces(topic)
    known_terms = [str(item) for item in METRIC_TOPIC_EXTRACTION_TERMS if str(item)]
    return {term for term in known_terms if term in text}


def _report_cache_consumer_assessment_for_retrieval(state: Dict[str, Any]) -> Dict[str, Any]:
    trace = resolve_runtime_calculation_trace(dict(state), allow_legacy_top_level=False)
    candidate = dict(trace.get("report_cache_candidate") or {})
    if not candidate:
        candidate = dict((dict(state.get("resolved_calculation_trace") or {}).get("report_cache_candidate") or {}))
    if not candidate:
        return {
            "status": "not_available",
            "eligible": False,
            "enabled": False,
            "mode": "trace_only",
            "reasons": ["missing_candidate"],
            "source": "none",
        }
    assessment = dict(candidate.get("retrieval_bypass") or {})
    if not assessment:
        assessment = classify_report_cache_consumer_candidate(candidate)
    return {
        "status": str(assessment.get("status") or "").strip(),
        "eligible": bool(assessment.get("eligible")),
        "enabled": bool(assessment.get("enabled")),
        "mode": str(assessment.get("mode") or "trace_only").strip(),
        "reasons": [str(reason) for reason in list(assessment.get("reasons") or [])],
        "candidate_status": str(candidate.get("status") or "").strip(),
        "candidate_key_id": str(candidate.get("key_id") or assessment.get("key_id") or "").strip(),
        "source": "resolved_calculation_trace.report_cache_candidate",
    }


def _report_cache_index_diagnostics_for_retrieval(
    state: Dict[str, Any],
    index_path: Any,
) -> Dict[str, Any]:
    path_text = str(index_path or "").strip()
    if not path_text:
        return {
            "status": "not_configured",
            "enabled": False,
            "serving_enabled": False,
            "path": "",
            "lookup_attempted": False,
        }

    # The persisted report-cache index is an optional runtime surface. Import
    # it only when a caller explicitly configures an index path.
    from src.storage.report_cache_index import ReportCacheIndex

    trace = resolve_runtime_calculation_trace(dict(state), allow_legacy_top_level=False)
    candidate = dict(trace.get("report_cache_candidate") or {})
    if not candidate:
        candidate = dict((dict(state.get("resolved_calculation_trace") or {}).get("report_cache_candidate") or {}))
    key = candidate.get("key") if isinstance(candidate.get("key"), dict) else {}
    if not key:
        diagnostics = ReportCacheIndex(path_text).load_diagnostics()
        return {
            "status": str(diagnostics.get("status") or "").strip(),
            "enabled": False,
            "serving_enabled": False,
            "path": str(diagnostics.get("path") or path_text),
            "lookup_attempted": False,
            "reason": "missing_report_cache_key",
            "index": {
                "status": diagnostics.get("status"),
                "path": diagnostics.get("path"),
                "readable_count": diagnostics.get("readable_count", 0),
                "blocked_count": diagnostics.get("blocked_count", 0),
                "malformed_count": diagnostics.get("malformed_count", 0),
            },
        }

    diagnostics = ReportCacheIndex(path_text).lookup_diagnostics(key)
    return {
        **diagnostics,
        "lookup_attempted": True,
    }




def make_document(*, page_content: str, metadata: Dict[str, Any]) -> Document:
    return document(page_content=page_content, metadata=metadata)


def _semantic_program_required(state: FinancialAgentState) -> bool:
    semantic_plan = dict(state.get("semantic_plan") or {})
    if "program_required" in semantic_plan:
        return bool(semantic_plan.get("program_required"))
    intent = str(state.get("intent") or state.get("query_type") or "").strip().lower()
    return intent in {"comparison", "trend", "numeric_fact"}


def _declared_query_surfaces(row: Dict[str, Any]) -> List[str]:
    return list(
        dict.fromkeys(
            value
            for value in (
                _normalise_spaces(str(row.get("label") or "")),
                *(
                    _normalise_spaces(str(item))
                    for item in (row.get("retrieval_hints") or [])
                ),
                *(
                    _normalise_spaces(str(item))
                    for item in (row.get("concept_hints") or [])
                ),
            )
            if value
        )
    )


def _query_matches_declared_surface(query: str, surface: str) -> bool:
    normalized_query = _normalise_spaces(query).lower()
    normalized_surface = _normalise_spaces(surface).lower()
    if not normalized_query or not normalized_surface:
        return False
    if normalized_surface in normalized_query or normalized_query in normalized_surface:
        return True
    compact_query = re.sub(r"\s+", "", normalized_query)
    compact_surface = re.sub(r"\s+", "", normalized_surface)
    shorter_compact = (
        compact_query
        if len(compact_query) <= len(compact_surface)
        else compact_surface
    )
    if (
        len(shorter_compact) >= 5
        and any(character.isalpha() for character in shorter_compact)
        and (
            compact_surface in compact_query
            or compact_query in compact_surface
        )
    ):
        return True
    query_terms = tokenize_terms(normalized_query)
    surface_terms = tokenize_terms(normalized_surface)
    if len(query_terms) < 2 or len(surface_terms) < 2:
        return False
    overlap = len(query_terms & surface_terms)
    return overlap >= 2 and overlap / max(min(len(query_terms), len(surface_terms)), 1) >= 0.75


def _semantic_query_ownership(
    state: FinancialAgentState,
    base_query: str,
) -> Dict[str, Any]:
    """Resolve a retrieval query only against planner-declared obligation surfaces."""

    obligations = [
        dict(item)
        for item in (
            state.get("answer_obligations")
            or dict(state.get("semantic_plan") or {}).get("answer_obligations")
            or []
        )
        if isinstance(item, dict)
    ]
    owner_ids: List[str] = []
    owner_kinds: List[str] = []
    required_group_ids: List[str] = []

    def add_owner(owner_id: str, owner_kind: str, *, required_group: bool) -> None:
        if owner_id and owner_id not in owner_ids:
            owner_ids.append(owner_id)
        if owner_kind and owner_kind not in owner_kinds:
            owner_kinds.append(owner_kind)
        if required_group and owner_id and owner_id not in required_group_ids:
            required_group_ids.append(owner_id)

    original_query = _normalise_spaces(str(state.get("query") or ""))
    is_composite_query = bool(
        original_query
        and _normalise_spaces(base_query).lower() == original_query.lower()
    )
    for obligation in obligations:
        obligation_id = _normalise_spaces(str(obligation.get("obligation_id") or ""))
        kind = _normalise_spaces(str(obligation.get("kind") or ""))
        owner_kind = "narrative" if kind == "narrative" else "numeric"
        obligation_matches = is_composite_query or any(
            _query_matches_declared_surface(base_query, surface)
            for surface in _declared_query_surfaces(obligation)
        )
        if obligation_matches:
            add_owner(
                obligation_id,
                owner_kind,
                required_group=bool(obligation.get("required", True))
                and kind in {"direct_value", "narrative"},
            )
        for requirement in obligation.get("evidence_requirements") or []:
            if not isinstance(requirement, dict):
                continue
            requirement_id = _normalise_spaces(
                str(requirement.get("requirement_id") or "")
            )
            requirement_matches = is_composite_query or any(
                _query_matches_declared_surface(base_query, surface)
                for surface in _declared_query_surfaces(requirement)
            )
            if requirement_matches:
                add_owner(
                    requirement_id,
                    owner_kind,
                    required_group=bool(requirement.get("required", True)),
                )

    if not owner_kinds:
        declared_kinds = list(
            dict.fromkeys(
                "narrative"
                if str(obligation.get("kind") or "") == "narrative"
                else "numeric"
                for obligation in obligations
            )
        )
        if len(declared_kinds) == 1:
            owner_kinds = declared_kinds

    if owner_kinds == ["numeric"]:
        mode = "numeric"
    elif owner_kinds == ["narrative"]:
        mode = "narrative"
    elif owner_kinds:
        mode = "composite"
    else:
        mode = "unscoped"
    return {
        "mode": mode,
        "owner_ids": owner_ids,
        "owner_kinds": owner_kinds,
        "required_group_ids": required_group_ids,
    }


def _semantic_required_evidence_groups(
    state: FinancialAgentState,
) -> List[Dict[str, Any]]:
    groups: List[Dict[str, Any]] = []
    obligations = [
        dict(item)
        for item in (
            state.get("answer_obligations")
            or dict(state.get("semantic_plan") or {}).get("answer_obligations")
            or []
        )
        if isinstance(item, dict)
    ]
    for obligation in obligations:
        kind = str(obligation.get("kind") or "")
        requirement_rows = [
            dict(item)
            for item in (obligation.get("evidence_requirements") or [])
            if isinstance(item, dict)
        ]
        source_rows = (
            requirement_rows
            if kind in {"derived_value", "narrative"} and requirement_rows
            else [obligation]
        )
        for row in source_rows:
            if not bool(row.get("required", True)):
                continue
            group_id = _normalise_spaces(
                str(
                    row.get("requirement_id")
                    or obligation.get("obligation_id")
                    or ""
                )
            )
            group_scope = dict(row.get("scope") or obligation.get("scope") or {})
            surfaces = [
                surface
                for surface in _declared_query_surfaces(row)
                if not is_scope_only_period_surface(surface, group_scope)
            ]
            if not group_id or not surfaces:
                continue
            groups.append(
                {
                    "group_id": group_id,
                    "kind": "narrative" if kind == "narrative" else "numeric",
                    "surfaces": surfaces,
                    "scope": group_scope,
                }
            )
    return groups


def _apply_semantic_query_budget(
    state: FinancialAgentState,
    queries: List[str],
    budget: int,
) -> tuple[List[str], Dict[str, Any]]:
    """Reserve one specific query per required semantic evidence group.

    The original composite query remains available, but it does not by itself
    consume every group's reservation. This keeps a bounded query fan-out from
    being monopolized by the first obligation's aliases while leaving search
    and answer selection unchanged.
    """

    candidates, unbounded_trace = apply_query_budget(
        list(queries),
        0,
        dedupe=True,
    )
    bounded_budget = query_budget_int(budget)
    groups = _semantic_required_evidence_groups(state)
    group_ids = list(
        dict.fromkeys(
            _normalise_spaces(str(group.get("group_id") or ""))
            for group in groups
            if _normalise_spaces(str(group.get("group_id") or ""))
        )
    )
    if (
        bounded_budget <= 0
        or len(candidates) <= bounded_budget
        or not group_ids
    ):
        selected, trace = apply_query_budget(
            list(queries),
            bounded_budget,
            dedupe=True,
        )
        return selected, trace

    ownership = [
        _semantic_query_ownership(state, candidate)
        for candidate in candidates
    ]
    selected_indexes: List[int] = [0] if candidates else []
    reserved_group_queries: List[Dict[str, str]] = []
    unreserved_group_ids: List[str] = []

    for group_id in group_ids:
        matching_indexes = [
            index
            for index, row in enumerate(ownership)
            if group_id in set(row.get("required_group_ids") or [])
        ]
        available_indexes = [
            index for index in matching_indexes if index not in selected_indexes
        ]
        if available_indexes and len(selected_indexes) < bounded_budget:
            selected_index = min(
                available_indexes,
                key=lambda index: (
                    len(ownership[index].get("required_group_ids") or []),
                    len(ownership[index].get("owner_ids") or []),
                    index,
                ),
            )
            selected_indexes.append(selected_index)
            reserved_group_queries.append(
                {
                    "group_id": group_id,
                    "query": candidates[selected_index],
                }
            )
            continue

        selected_match = next(
            (index for index in matching_indexes if index in selected_indexes),
            None,
        )
        if selected_match is not None and not available_indexes:
            reserved_group_queries.append(
                {
                    "group_id": group_id,
                    "query": candidates[selected_match],
                }
            )
        else:
            unreserved_group_ids.append(group_id)

    remaining_slots = max(0, bounded_budget - len(selected_indexes))
    remaining_indexes = [
        index for index in range(len(candidates)) if index not in selected_indexes
    ]
    if remaining_slots:
        remaining_queries = [candidates[index] for index in remaining_indexes]
        selected_remaining, _remaining_trace = apply_query_budget(
            remaining_queries,
            remaining_slots,
            dedupe=False,
        )
        selected_remaining_set = set(selected_remaining)
        selected_indexes.extend(
            index
            for index in remaining_indexes
            if candidates[index] in selected_remaining_set
        )

    selected_indexes = selected_indexes[:bounded_budget]
    selected_index_set = set(selected_indexes)
    selected = [candidates[index] for index in selected_indexes]
    return selected, {
        "input_count": int(unbounded_trace.get("input_count") or len(queries)),
        "deduped_count": len(candidates),
        "selected_count": len(selected),
        "budget": bounded_budget,
        "dropped_count": max(len(candidates) - len(selected), 0),
        "dropped_queries": [
            candidate
            for index, candidate in enumerate(candidates)
            if index not in selected_index_set
        ],
        "dedupe_enabled": True,
        "selection_strategy": "semantic_required_group_coverage_v1",
        "composite_query_preserved": bool(candidates and 0 in selected_index_set),
        "reserved_group_queries": reserved_group_queries,
        "unreserved_group_ids": unreserved_group_ids,
    }


def _has_numeric_value_cell(row_text: str) -> bool:
    """Recognize complete finite value cells without interpreting their role."""

    if "|" not in row_text:
        return False
    for cell in row_text.split("|"):
        value = _normalise_spaces(cell)
        if _parse_number_text(value) is not None:
            return True
        inline = _inline_numeric_unit_match(value)
        if inline and _parse_number_text(inline.group("value")) is not None:
            return True
    return False


def _numeric_atomic_declared_surface_priority(
    metadata: Dict[str, Any],
    body_text: str,
    declared_surfaces: List[str],
) -> tuple[int, int, int, int]:
    """Rank source-visible numeric bindings ahead of contextual surface hits.

    A parser-projected local header/value row is stronger than a full pipe row
    in the source body. Section, table-context, flattened summary, and index-
    prefix matches are deliberately excluded: they can describe the requested
    scope without carrying the requested value.
    """

    atomic_surfaces: List[tuple[int, str]] = []
    # Keep physical lines separate: another header row cannot lend a value.
    # Digits embedded in labels or references are not numeric value cells.
    for line in str(metadata.get("table_header_context") or "").splitlines():
        surface = _normalise_spaces(line)
        if _has_numeric_value_cell(surface):
            atomic_surfaces.append((2, surface))

    source_body = strip_index_metadata_prefix(str(body_text or ""))
    for line in source_body.splitlines():
        surface = _normalise_spaces(line)
        if _has_numeric_value_cell(surface):
            atomic_surfaces.append((1, surface))

    best = (0, 0, 0, 0)
    for source_strength, atomic_surface in atomic_surfaces:
        matched_surfaces = [
            _normalise_spaces(str(surface))
            for surface in declared_surfaces
            if _query_matches_declared_surface(
                atomic_surface,
                str(surface),
            )
        ]
        if not matched_surfaces:
            continue
        specificity = max(
            (
                len(tokenize_terms(surface)),
                len("".join(character for character in surface if character.isalnum())),
            )
            for surface in matched_surfaces
        )
        best = max(
            best,
            (
                source_strength,
                specificity[0],
                specificity[1],
                len(matched_surfaces),
            ),
        )
    return best


class FinancialRetrievalPipelineMixin:
    @staticmethod
    def _apply_strict_filter(docs, predicate):
        """Keep only authorized sources, including an empty result when none match."""

        return [item for item in docs if predicate(item[0])]

    def _supplement_section_seed_docs(
        self,
        state: FinancialAgentState,
    ) -> List[tuple[Document, float]]:
        """Preserve relevant parser rows from preferred sections in the seed pool.

        Selection uses retrieval hints and document structure only. It does not
        infer an operation family or synthesize required operands from wording.
        """

        query = str(state.get("query") or "")
        topic = str(state.get("topic") or query)
        intent = str(state.get("intent") or state.get("query_type") or "qa")
        section_terms = supplement_section_terms_for_query(query, topic, intent)
        section_terms.extend(_active_preferred_sections(state, query, topic, intent))
        section_terms = list(dict.fromkeys(_normalise_spaces(item) for item in section_terms if _normalise_spaces(item)))
        statement_types = _active_preferred_statement_types(state, query, topic)
        obligations = [
            dict(item)
            for item in (
                state.get("answer_obligations")
                or dict(state.get("semantic_plan") or {}).get("answer_obligations")
                or []
            )
            if isinstance(item, dict)
        ]
        evidence_groups = (
            _semantic_required_evidence_groups(state)
            if _semantic_program_required(state)
            else []
        )
        hint_terms = list(
            dict.fromkeys(
                _normalise_spaces(str(value))
                for value in (
                    (
                        surface
                        for group in evidence_groups
                        for surface in group.get("surfaces") or []
                    )
                    if evidence_groups
                    else (
                        value
                        for obligation in obligations
                        for value in (
                            list(obligation.get("retrieval_hints") or [])
                            + list(obligation.get("concept_hints") or [])
                        )
                    )
                )
                if _normalise_spaces(str(value))
            )
        )
        if not section_terms and not statement_types and not evidence_groups:
            return []

        bodies = list(getattr(self.vsm, "bm25_docs", []) or [])
        metadatas = list(getattr(self.vsm, "bm25_metadatas", []) or [])
        if not bodies or not metadatas:
            return []
        where_filter = self._build_scope_plan(state)["where_filter"]
        supplemented: List[tuple[Document, float]] = []
        group_candidates: Dict[
            str,
            List[
                tuple[
                    Document,
                    float,
                    int,
                    int,
                    int,
                    tuple[int, int, int, int],
                ]
            ],
        ] = {
            str(group.get("group_id") or ""): []
            for group in evidence_groups
            if str(group.get("group_id") or "")
        }
        seen: set[str] = set()
        for body, raw_metadata in zip(bodies, metadatas):
            metadata = dict(raw_metadata or {})
            if not metadata_matches_filter(metadata, where_filter):
                continue
            if not source_section_allowed_for_query(metadata, state.get("answer_obligations") or []):
                continue
            company = _normalise_spaces(str(metadata.get("company") or "")).lower()

            body_text = str(body or "")
            source_body = strip_index_metadata_prefix(body_text)
            surface = _normalise_spaces(
                " ".join(
                    str(value or "")
                    for value in (
                        metadata.get("section_path"),
                        metadata.get("section"),
                        metadata.get("local_heading"),
                        metadata.get("table_context"),
                        metadata.get("table_row_labels_text"),
                        body_text[:1000],
                    )
                    if str(value or "").strip()
                )
            )
            declared_match_surface = _normalise_spaces(
                " ".join(
                    str(value or "")
                    for value in (
                        metadata.get("local_heading"),
                        metadata.get("table_context"),
                        metadata.get("table_header_context"),
                        metadata.get("table_row_labels_text"),
                        source_body,
                    )
                    if str(value or "").strip()
                )
            )
            section_match = any(term in surface for term in section_terms)
            statement_type = _normalise_spaces(
                str(metadata.get("statement_type") or "unknown")
            )
            statement_match = statement_type in statement_types
            statement_priority = (
                len(statement_types) - statement_types.index(statement_type)
                if statement_match
                else 0
            )
            block_type = _normalise_spaces(
                str(metadata.get("block_type") or "")
            ).lower()
            if not section_match and not statement_match and not evidence_groups:
                continue
            matching_groups: List[tuple[Dict[str, Any], int]] = []
            for group in evidence_groups:
                group_scope = dict(group.get("scope") or {})
                expected_company = _normalise_spaces(
                    str(group_scope.get("company") or "")
                ).lower()
                if expected_company and company and not (
                    expected_company == company
                    or expected_company in company
                    or company in expected_company
                ):
                    continue
                expected_consolidation = _normalise_spaces(
                    str(group_scope.get("consolidation_scope") or "")
                ).lower()
                actual_consolidation = _normalise_spaces(
                    str(metadata.get("consolidation_scope") or "")
                ).lower()
                if (
                    expected_consolidation in {"consolidated", "separate"}
                    and actual_consolidation in {"consolidated", "separate"}
                    and expected_consolidation != actual_consolidation
                ):
                    continue
                matching_surfaces = [
                    term
                    for term in (group.get("surfaces") or [])
                    if _query_matches_declared_surface(
                        declared_match_surface,
                        str(term),
                    )
                ]
                if matching_surfaces:
                    matching_groups.append((group, len(matching_surfaces)))
            if evidence_groups and not matching_groups:
                continue
            chunk_uid = str(metadata.get("chunk_uid") or "").strip()
            dedupe_key = chunk_uid or f"{metadata.get('section_path')}|{surface[:200]}"
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            hint_hits = sum(1 for term in hint_terms if term in declared_match_surface)
            score = 0.02 + (0.08 if section_match else 0.0) + (0.08 if statement_match else 0.0)
            if statement_types and not statement_match and statement_type != "unknown":
                score -= 0.06
            score += min(0.08, hint_hits * 0.02)
            doc = make_document(page_content=body_text, metadata=metadata)
            supplemented.append((doc, score))
            for group, group_hint_hits in matching_groups:
                group_score = score + min(0.08, group_hint_hits * 0.02)
                group_kind = str(group.get("kind") or "numeric")
                structure_priority = int(
                    block_type != "table"
                    if group_kind == "narrative"
                    else block_type == "table"
                )
                period_text = _normalise_spaces(
                    str(dict(group.get("scope") or {}).get("period") or "")
                )
                period_years = [
                    int(value)
                    for value in re.findall(r"(?:19|20)\d{2}", period_text)
                ]
                if period_years:
                    group_score += 0.05 * metadata_period_match_strength(
                        list(metadata.get("period_labels") or []),
                        period_years,
                    )
                group_id = str(group.get("group_id") or "")
                atomic_numeric_priority = (
                    _numeric_atomic_declared_surface_priority(
                        metadata,
                        body_text,
                        list(group.get("surfaces") or []),
                    )
                    if group_kind == "numeric"
                    else (0, 0, 0, 0)
                )
                group_candidates.setdefault(group_id, []).append(
                    (
                        doc,
                        group_score,
                        statement_priority,
                        structure_priority,
                        group_hint_hits,
                        atomic_numeric_priority,
                    )
                )
        supplemented.sort(key=lambda item: item[1], reverse=True)
        if not evidence_groups:
            return supplemented[:6]
        max_seed_candidates = max(
            1,
            int(
                SEMANTIC_REQUIRED_EVIDENCE_POLICY.get("max_seed_candidates")
                or 8
            ),
        )
        max_narrative_candidates_per_group = max(
            1,
            int(
                SEMANTIC_REQUIRED_EVIDENCE_POLICY.get(
                    "max_narrative_candidates_per_group"
                )
                or 1
            ),
        )
        selected: List[tuple[Document, float]] = []
        selected_ids: set[str] = set()
        ranked_narrative_groups: List[
            tuple[
                List[
                    tuple[
                        Document,
                        float,
                        int,
                        int,
                        int,
                        tuple[int, int, int, int],
                    ]
                ],
                bool,
            ]
        ] = []

        def add_item(item: tuple[Document, float]) -> None:
            doc, _score = item
            metadata = dict(getattr(doc, "metadata", {}) or {})
            key = str(metadata.get("chunk_uid") or "").strip() or str(doc.page_content)[:160]
            if key in selected_ids:
                return
            selected_ids.add(key)
            selected.append(item)

        for group in evidence_groups:
            group_kind = str(group.get("kind") or "numeric")
            candidates = sorted(
                group_candidates.get(str(group.get("group_id") or ""), []),
                # Numeric inputs prefer the declared statement context and a
                # table surface. Narrative inputs prefer explanatory prose,
                # then the strongest declared-surface match.
                key=(
                    (lambda item: (item[3], item[2], item[4], item[1]))
                    if group_kind == "narrative"
                    else (
                        lambda item: (
                            *item[5],
                            item[2],
                            item[3],
                            item[4],
                            item[1],
                        )
                    )
                ),
                reverse=True,
            )
            if candidates:
                add_item((candidates[0][0], candidates[0][1]))
            if group_kind == "narrative":
                ranked_narrative_groups.append(
                    (
                        candidates[:max_narrative_candidates_per_group],
                        any(candidate[3] > 0 for candidate in candidates),
                    )
                )
        for rank in range(1, max_narrative_candidates_per_group):
            for candidates, has_prose_candidate in ranked_narrative_groups:
                if len(selected) >= max_seed_candidates:
                    break
                if rank >= len(candidates):
                    continue
                candidate = candidates[rank]
                if has_prose_candidate and candidate[3] <= 0:
                    continue
                add_item((candidate[0], candidate[1]))
            if len(selected) >= max_seed_candidates:
                break
        return selected[:max_seed_candidates]

    """Graph-node implementation for retrieval and deterministic candidate selection."""


    def _merge_retry_candidates(self, docs, previous_docs) -> List[tuple[Document, float]]:
        merged: List[tuple[Document, float]] = list(docs)
        seen_chunk_uids = {
            str((doc.metadata or {}).get("chunk_uid") or "")
            for doc, _score in merged
        }
        for doc, score in previous_docs:
            chunk_uid = str((doc.metadata or {}).get("chunk_uid") or "")
            if chunk_uid and chunk_uid in seen_chunk_uids:
                continue
            if chunk_uid:
                seen_chunk_uids.add(chunk_uid)
            merged.append((doc, score))
        return merged

    # intent별 표 청크 선호 여부
    _TABLE_PREFERRED_TYPES = frozenset(["numeric_fact", "trend"])
    _PARAGRAPH_PREFERRED_TYPES = frozenset(["business_overview", "risk", "qa"])

    def _section_bias(self, query_type: str, section_path: str) -> float:
        lowered = (section_path or "").lower()
        bias = 0.0
        # 가장 긴 needle부터 검사하고 첫 매칭에서 break → 구체적인 섹션명이 우선 적용되고 중복 가산 방지
        for needle, weight in sorted(
            self._SECTION_BIAS_BY_QUERY_TYPE.get(query_type, ()),
            key=lambda x: len(x[0]),
            reverse=True,
        ):
            if needle.lower() in lowered:
                bias += weight
                break
        rerank_policy = dict(NARRATIVE_RERANK_POLICY)
        lower_priority_markers = tuple(
            str(marker)
            for marker in (
                dict(rerank_policy.get("lower_priority_section_markers_by_query_type") or {}).get(query_type) or ()
            )
            if str(marker)
        )
        if any(marker.lower() in lowered for marker in lower_priority_markers):
            bias += float(rerank_policy.get("lower_priority_section_penalty") or 0.0)
        return bias

    def _rerank_docs(self, docs, state: FinancialAgentState):
        active_subtask = dict(state.get("active_subtask") or {})
        companies = {company.lower() for company in state.get("companies", [])}
        years = {int(year) for year in state.get("years", [])}
        topic_terms = tokenize_terms(state.get("topic") or state["query"])
        section_filter = (state.get("section_filter") or "").strip()
        intent = str(active_subtask.get("intent_override") or state.get("intent") or state.get("query_type", "qa"))
        format_preference = str(
            active_subtask.get("format_preference_override")
            or state.get("format_preference")
            or default_format_preference(intent)
        )
        metric_terms = _metric_terms_from_topic(state.get("topic") or state["query"])
        preferred_sections = _active_preferred_sections(state, state["query"], state.get("topic") or "", intent)
        desired_statement_types = set(_active_preferred_statement_types(state, state["query"], state.get("topic") or ""))
        desired_consolidation = str(
            dict(active_subtask.get("constraints") or {}).get("consolidation_scope") or "unknown"
        )
        if desired_consolidation not in {"consolidated", "separate"}:
            desired_consolidation = "unknown"
        query_years = sorted(years)
        reranked = []
        for doc, score in docs:
            metadata = doc.metadata or {}
            company = str(metadata.get("company", "")).lower()
            year = metadata.get("year")
            section = str(metadata.get("section", ""))
            section_path = str(metadata.get("section_path", section))
            block_type = metadata.get("block_type", "")
            statement_type = str(metadata.get("statement_type") or "unknown").strip()
            consolidation_scope = str(metadata.get("consolidation_scope") or "unknown").strip()
            period_labels = list(metadata.get("period_labels") or [])
            body_text = strip_rerank_metadata(doc.page_content)
            document_terms = tokenize_terms(
                " ".join(
                    [
                        body_text,
                        section,
                        section_path,
                        str(metadata.get("table_context") or ""),
                    ]
                )
            )

            boosted = float(score)
            if companies:
                if company in companies:
                    boosted += 0.35
                elif any(target in company or company in target for target in companies):
                    boosted += 0.20
            if years and year in years:
                boosted += 0.25
            if section_filter and (section == section_filter or section_filter in section_path):
                boosted += 0.20
            if topic_terms and document_terms:
                overlap = len(topic_terms & document_terms) / max(len(topic_terms), 1)
                boosted += min(overlap, 0.20)
            if intent in {"comparison", "trend"} and metric_terms:
                metric_hit = sum(1 for term in metric_terms if term in body_text or term in section_path)
                if metric_hit:
                    boosted += min(0.16 + 0.05 * metric_hit, 0.30)
                else:
                    boosted -= 0.20
            if preferred_sections and any(section_term in section_path for section_term in preferred_sections):
                boosted += 0.20
            if desired_statement_types:
                if statement_type in desired_statement_types:
                    boosted += 0.24
                elif statement_type != "unknown":
                    boosted -= 0.08
            if desired_consolidation != "unknown":
                if consolidation_scope == desired_consolidation:
                    boosted += 0.12
                elif consolidation_scope != "unknown":
                    boosted -= 0.18
            period_match_strength = metadata_period_match_strength(period_labels, query_years)
            if period_match_strength > 0:
                boosted += 0.10 * period_match_strength

            boosted += self._section_bias(intent, section_path)

            # block_type 보정: format_preference 기반으로 표/단락 선호도 반영
            if format_preference == "paragraph" and block_type == "table":
                boosted -= 0.08
            elif format_preference == "table" and block_type == "paragraph":
                boosted -= 0.04


            reranked.append((doc, boosted))

        reranked.sort(key=lambda item: item[1], reverse=True)
        return reranked

    def _build_scope_plan(self, state: FinancialAgentState) -> Dict[str, Any]:
        """One source filter for search, local supplementation and final evidence."""
        active_subtask = dict(state.get("active_subtask") or {})
        report_scope = dict(state.get("report_scope") or {})
        companies = list(state.get("companies", []) or [])
        years = list(state.get("years", []) or [])
        scope_company = str(report_scope.get("company") or "").strip()
        if scope_company:
            # Caller report scope is a source boundary, not another planner
            # entity to union into it. Explicit receipt lists still take priority.
            companies = [scope_company]
        strict_company_scope = should_apply_strict_company_scope(companies, report_scope)
        scope_year_raw = report_scope.get("year")
        scope_year: Optional[int] = None
        try:
            if scope_year_raw not in (None, ""):
                scope_year = int(scope_year_raw)
        except (TypeError, ValueError):
            scope_year = None
        if scope_year is not None and scope_year not in years:
            years = [scope_year, *years] if years else [scope_year]
        scope_report_type = str(report_scope.get("report_type") or "").strip()
        scope_rcept_no = str(report_scope.get("rcept_no") or "").strip()
        scope_source_receipts = report_scope_source_receipts(report_scope)
        has_multi_source_scope = len(scope_source_receipts) > 1
        scope_consolidation = str(report_scope.get("consolidation") or "").strip()
        intent = str(active_subtask.get("intent_override") or state.get("intent") or state.get("query_type", "qa"))

        conditions = []
        if companies and strict_company_scope:
            if len(companies) == 1:
                conditions.append({"company": companies[0]})
            else:
                conditions.append({"company": {"$in": companies}})
        if years:
            int_years = [int(year) for year in years]
            if has_multi_source_scope:
                logger.info(
                    "[retrieve] multi-report source scope detected; skipping strict metadata year filter and using source receipts only: %s",
                    scope_source_receipts,
                )
            elif scope_year is not None:
                # Explicit document scope constrains sources without rewriting period hints.
                conditions.append({"year": scope_year})
            elif intent in {"comparison", "trend"} and len(int_years) > 1:
                logger.info(
                    "[retrieve] multi-period %s query detected; skipping strict metadata year filter and keeping years in query text only: %s",
                    intent,
                    int_years,
                )
            elif len(int_years) == 1:
                conditions.append({"year": int_years[0]})
            else:
                conditions.append({"year": {"$in": int_years}})
        if scope_report_type:
            conditions.append({"report_type": scope_report_type})
        if scope_source_receipts:
            if len(scope_source_receipts) == 1:
                conditions.append({"rcept_no": scope_source_receipts[0]})
            else:
                conditions.append({"rcept_no": {"$in": scope_source_receipts}})
        elif scope_rcept_no:
            conditions.append({"rcept_no": scope_rcept_no})

        if not conditions:
            where_filter = None
        elif len(conditions) == 1:
            where_filter = conditions[0]
        else:
            where_filter = {"$and": conditions}

        return {
            "companies": companies, "years": years, "intent": intent,
            "strict_company_scope": strict_company_scope,
            "has_multi_source_scope": has_multi_source_scope,
            "scope_report_type": scope_report_type,
            "scope_consolidation": scope_consolidation,
            "where_filter": where_filter,
        }

    def _build_plan(self, state: FinancialAgentState) -> Dict[str, Any]:
        """Normalize scope and construct the deterministic retrieval plan."""
        query = state["query"]
        retrieval_queries = [str(item).strip() for item in (state.get("retrieval_queries") or []) if str(item).strip()]
        active_subtask = dict(state.get("active_subtask") or {})
        active_subtask_query = str(active_subtask.get("query") or "").strip()
        active_subtask_retrieval_queries = [
            str(item).strip()
            for item in (active_subtask.get("retrieval_queries") or [])
            if str(item).strip()
        ]
        scope_plan = self._build_scope_plan(state)
        intent = str(scope_plan["intent"])
        reflection_count = int(state.get("reflection_count") or 0)
        retry_queries = [str(item).strip() for item in (state.get("retry_queries") or []) if str(item).strip()]
        effective_k = self.k if reflection_count <= 0 else max(self.k * 2, 4)
        report_cache_consumer_assessment = _report_cache_consumer_assessment_for_retrieval(dict(state))
        report_cache_index_diagnostics = _report_cache_index_diagnostics_for_retrieval(
            dict(state),
            state.get("report_cache_index_path") or getattr(self, "report_cache_index_path", ""),
        )
        semantic_program_required = _semantic_program_required(state)
        retrieval_intent = intent
        if semantic_program_required and intent not in {"comparison", "trend", "numeric_fact"}:
            retrieval_intent = "comparison"
        query_bundle = (
            active_subtask_retrieval_queries
            or ([active_subtask_query] if active_subtask_query else [])
            or retrieval_queries
            or [query]
        )
        if not semantic_program_required:
            query_bundle = list(query_bundle)
            for supplemental_query in (query, str(state.get("topic") or "").strip()):
                if supplemental_query and supplemental_query not in query_bundle:
                    query_bundle.append(supplemental_query)
        query_budget_trace: Dict[str, Any] = {}
        query_budget_trace["source"] = {
            "kind": (
                "active_subtask_retrieval_queries"
                if active_subtask_retrieval_queries
                else "active_subtask_query"
                if active_subtask_query
                else "state_retrieval_queries"
                if retrieval_queries
                else "query"
            ),
            "active_subtask_id": str(active_subtask.get("task_id") or ""),
            "answer_mode": "semantic_program" if semantic_program_required else "narrative",
            "input_primary_query_count": len(query_bundle),
            "active_subtask_retrieval_query_count": len(active_subtask_retrieval_queries),
            "state_retrieval_query_count": len(retrieval_queries),
        }
        primary_budget = query_budget_int(getattr(self, "retrieval_query_budget", 0))
        if semantic_program_required and primary_budget > 0:
            query_bundle, query_budget_trace["primary"] = (
                _apply_semantic_query_budget(
                    state,
                    list(query_bundle),
                    primary_budget,
                )
            )
        else:
            query_bundle, query_budget_trace["primary"] = apply_query_budget(
                list(query_bundle),
                primary_budget,
                dedupe=primary_budget > 0,
            )
        hint_budget = query_budget_int(getattr(self, "retrieval_hint_query_token_budget", 16))
        section_budget = query_budget_int(getattr(self, "preferred_section_query_budget", 8))
        return {
            **scope_plan,
            "query": query,
            "active_subtask": active_subtask,
            "reflection_count": reflection_count,
            "retry_queries": retry_queries,
            "effective_k": effective_k,
            "report_cache_consumer_assessment": report_cache_consumer_assessment,
            "report_cache_index_diagnostics": report_cache_index_diagnostics,
            "semantic_program_required": semantic_program_required,
            "retrieval_intent": retrieval_intent,
            "query_bundle": query_bundle,
            "query_budget_trace": query_budget_trace,
            "hint_budget": hint_budget,
            "section_budget": section_budget,
        }

    def _execute_searches(
        self,
        state: FinancialAgentState,
        plan: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Execute planned primary and retry searches without selecting evidence."""
        active_subtask = dict(plan["active_subtask"])
        companies = list(plan["companies"])
        scope_report_type = str(plan["scope_report_type"])
        scope_consolidation = str(plan["scope_consolidation"])
        semantic_program_required = bool(plan["semantic_program_required"])
        retrieval_intent = str(plan["retrieval_intent"])
        intent = str(plan["intent"])
        query_bundle = list(plan["query_bundle"])
        query_budget_trace = dict(plan["query_budget_trace"])
        hint_budget = int(plan["hint_budget"])
        section_budget = int(plan["section_budget"])
        where_filter = plan["where_filter"]
        obligations = state.get("answer_obligations") or []
        source_scope_search = {"applied": False, "reason": "unrestricted_output"}
        if not source_section_allowed_for_query({}, obligations):
            where_filter, source_scope_search = restrict_search_filter(
                getattr(self.vsm, "bm25_metadatas", []) or [], where_filter=where_filter,
                allowed=lambda metadata: source_section_allowed_for_query(metadata, obligations),
            )
        effective_k = int(plan["effective_k"])
        retry_queries = list(plan["retry_queries"])
        reflection_count = int(plan["reflection_count"])
        retrieval_hint = ""
        preferred_sections: List[str] = []
        query_budget_trace["enrichment"] = {
            "mode": "per_query",
            "queries": [],
        }
        executed_duplicate_trace: Dict[str, Any] = {
            "enabled": True,
            "scope": "same_trace_same_source_exact_signature",
            "dropped_count": 0,
            "by_source": {},
        }
        seen_executed_query_signatures_by_source: Dict[str, set[str]] = {}
        executed_queries: List[Dict[str, Any]] = []
        reused_queries: List[Dict[str, Any]] = []
        retrieval_query_result_cache: Dict[str, Dict[str, Any]] = {
            str(key): dict(value)
            for key, value in dict(state.get("retrieval_query_result_cache") or {}).items()
            if isinstance(value, dict)
        }
        docs: List[tuple[Document, float]] = []
        for base_query in query_bundle:
            query_semantics = (
                _semantic_query_ownership(state, base_query)
                if semantic_program_required
                else {
                    "mode": "legacy",
                    "owner_ids": [],
                    "owner_kinds": [],
                    "required_group_ids": [],
                }
            )
            include_narrative_policies = (
                not semantic_program_required
                or query_semantics.get("mode") in {"narrative", "composite"}
            )
            query_retrieval_intent = retrieval_intent
            if semantic_program_required and query_semantics.get("mode") == "narrative":
                query_retrieval_intent = intent
            enrichment_state = state
            if semantic_program_required and len(query_bundle) > 1:
                active_for_query = dict(active_subtask)
                active_for_query["preferred_sections"] = []
                enrichment_state = {**state, "active_subtask": active_for_query}
            retrieval_hint = retrieval_hint_from_topic(
                base_query,
                base_query,
                query_retrieval_intent,
                include_narrative_policies=include_narrative_policies,
            )
            preferred_sections = _active_preferred_sections(
                enrichment_state,
                base_query,
                base_query,
                query_retrieval_intent,
                include_narrative_policies=include_narrative_policies,
            )
            retrieval_hint_terms = [
                item
                for item in _normalise_spaces(retrieval_hint).split(" ")
                if item
            ]
            selected_retrieval_hint_terms, hint_enrichment_trace = (
                limit_query_context_terms(
                    retrieval_hint_terms,
                    hint_budget,
                )
            )
            selected_preferred_sections, section_enrichment_trace = (
                limit_query_context_terms(
                    list(preferred_sections or []),
                    section_budget,
                    strategy="head_tail",
                )
            )
            enrichment_trace = {
                "base_query": base_query,
                "query_semantics": dict(query_semantics),
                "retrieval_hint": hint_enrichment_trace,
                "preferred_sections": section_enrichment_trace,
            }
            query_budget_trace["enrichment"]["queries"].append(enrichment_trace)
            if "retrieval_hint" not in query_budget_trace["enrichment"]:
                query_budget_trace["enrichment"].update(
                    {
                        "retrieval_hint": hint_enrichment_trace,
                        "preferred_sections": section_enrichment_trace,
                    }
                )
            enriched_query = f"{' '.join(companies)} {base_query}" if companies else base_query
            if scope_report_type:
                enriched_query = f"{enriched_query} {scope_report_type}".strip()
            if scope_consolidation:
                enriched_query = f"{enriched_query} {scope_consolidation}".strip()
            if selected_retrieval_hint_terms:
                enriched_query = f"{enriched_query} {' '.join(selected_retrieval_hint_terms)}".strip()
            if selected_preferred_sections:
                enriched_query = f"{enriched_query} {' '.join(selected_preferred_sections)}".strip()
            if drop_duplicate_executed_query(
                seen_executed_query_signatures_by_source,
                executed_duplicate_trace,
                source="primary",
                executed_query=enriched_query,
                base_query=base_query,
            ):
                continue
            search_k = effective_k * 4
            query_trace = {
                "source": "primary",
                "base_query": base_query,
                "executed_query": enriched_query,
                "k": search_k,
                "where_filter": where_filter,
                "query_semantics": dict(query_semantics),
                "query_enrichment": {
                    "retrieval_hint_terms": list(selected_retrieval_hint_terms),
                    "preferred_sections": list(selected_preferred_sections),
                },
            }
            cached_result = lookup_query_result_cache(
                retrieval_query_result_cache,
                source="primary",
                executed_query=enriched_query,
                where_filter=where_filter,
                k=search_k,
            )
            if cached_result:
                reused_queries.append(
                    {
                        **query_trace,
                        "result_cache_hit": True,
                        "result_cache_hit_mode": cached_result.get("cache_hit_mode") or "exact",
                        "result_cache_key": cached_result.get("cache_key"),
                        "cached_k": cached_result.get("k"),
                        "doc_count": len(list(cached_result.get("docs") or [])),
                    }
                )
                batch_docs = list(cached_result.get("docs") or [])
                docs = batch_docs if not docs else self._merge_retry_candidates(docs, batch_docs)
                continue
            executed_queries.append(query_trace)
            batch_docs = self.vsm.search(enriched_query, k=search_k, where_filter=where_filter)
            search_telemetry = getattr(self.vsm, "last_search_telemetry", None)
            if isinstance(search_telemetry, dict) and search_telemetry:
                query_trace["search_telemetry"] = dict(search_telemetry)
            store_query_result_cache(
                retrieval_query_result_cache,
                source="primary",
                executed_query=enriched_query,
                where_filter=where_filter,
                k=search_k,
                docs=batch_docs,
            )
            docs = batch_docs if not docs else self._merge_retry_candidates(docs, batch_docs)
        configured_retry_budget = query_budget_int(getattr(self, "retry_retrieval_query_budget", 0))
        retry_budget = configured_retry_budget or 3
        retry_queries, query_budget_trace["retry"] = apply_query_budget(
            retry_queries,
            retry_budget,
            dedupe=configured_retry_budget > 0,
        )
        retry_queries, duplicate_retry_trace = drop_queries_already_selected(
            retry_queries,
            query_bundle,
        )
        query_budget_trace["retry"].update(duplicate_retry_trace)
        query_budget_trace["retry"]["selected_count_before_duplicate_drop"] = query_budget_trace["retry"].get(
            "selected_count",
            0,
        )
        query_budget_trace["retry"]["selected_count"] = len(retry_queries)
        if retry_queries:
            retry_docs: List[tuple[Document, float]] = []
            for retry_query in retry_queries:
                if drop_duplicate_executed_query(
                    seen_executed_query_signatures_by_source,
                    executed_duplicate_trace,
                    source="retry",
                    executed_query=retry_query,
                    base_query=retry_query,
                ):
                    continue
                search_k = max(effective_k * 2, 8)
                query_trace = {
                    "source": "retry",
                    "base_query": retry_query,
                    "executed_query": retry_query,
                    "k": search_k,
                    "where_filter": where_filter,
                }
                cached_result = lookup_query_result_cache(
                    retrieval_query_result_cache,
                    source="retry",
                    executed_query=retry_query,
                    where_filter=where_filter,
                    k=search_k,
                )
                if cached_result:
                    reused_queries.append(
                        {
                            **query_trace,
                            "result_cache_hit": True,
                            "result_cache_hit_mode": cached_result.get("cache_hit_mode") or "exact",
                            "result_cache_key": cached_result.get("cache_key"),
                            "cached_k": cached_result.get("k"),
                            "doc_count": len(list(cached_result.get("docs") or [])),
                        }
                    )
                    retry_docs.extend(list(cached_result.get("docs") or []))
                    continue
                executed_queries.append(query_trace)
                batch_docs = self.vsm.search(retry_query, k=search_k, where_filter=where_filter)
                search_telemetry = getattr(self.vsm, "last_search_telemetry", None)
                if isinstance(search_telemetry, dict) and search_telemetry:
                    query_trace["search_telemetry"] = dict(search_telemetry)
                store_query_result_cache(
                    retrieval_query_result_cache,
                    source="retry",
                    executed_query=retry_query,
                    where_filter=where_filter,
                    k=search_k,
                    docs=batch_docs,
                )
                retry_docs.extend(batch_docs)
            if retry_docs:
                docs = self._merge_retry_candidates(docs, retry_docs)
        supplemental_docs = self._supplement_section_seed_docs(state)
        if supplemental_docs:
            docs = self._merge_retry_candidates(docs, supplemental_docs)

        if reflection_count > 0:
            previous_docs = list(state.get("seed_retrieved_docs", []) or [])
            if previous_docs:
                docs = self._merge_retry_candidates(docs, previous_docs)

        return {
            "docs": docs,
            "supplemental_docs": supplemental_docs,
            "query_budget_trace": query_budget_trace,
            "executed_duplicate_trace": executed_duplicate_trace,
            "executed_queries": executed_queries,
            "reused_queries": reused_queries,
            "retrieval_query_result_cache": retrieval_query_result_cache,
            "retry_queries": retry_queries,
            "retrieval_hint": retrieval_hint,
            "preferred_sections": preferred_sections,
            "source_scope_search": source_scope_search,
        }

    def _select_evidence(
        self,
        state: FinancialAgentState,
        plan: Dict[str, Any],
        searches: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Apply scope filters, reranking, and the visible evidence policy."""
        docs = list(searches["docs"])
        supplemental_docs = list(searches["supplemental_docs"])
        companies = list(plan["companies"])
        years = list(plan["years"])
        where_filter = plan["where_filter"]
        reflection_count = int(plan["reflection_count"])
        retry_queries = list(searches["retry_queries"])
        active_subtask = dict(plan["active_subtask"])
        semantic_program_required = bool(plan["semantic_program_required"])
        effective_k = int(plan["effective_k"])

        logger.info(
            "[retrieve] companies=%s years=%s topic=%s where=%s retry_count=%s retry_queries=%s -> %s candidates",
            companies,
            years,
            state.get("topic"),
            where_filter,
            reflection_count,
            retry_queries,
            len(docs),
        )

        # Legacy section_filter is a soft relevance hint. Explicit source_sections
        # are separate query authority and never fall back to foreign sections.

        # Search backends, cached/retry docs and local sidecar scans all share
        # this boundary. Never reintroduce rejected supplements into seed docs.
        obligations = state.get("answer_obligations") or []
        def scope_predicate(doc):
            metadata = dict(doc.metadata or {})
            return metadata_matches_filter(metadata, where_filter) and source_section_allowed_for_query(metadata, obligations)
        input_count = len(docs)
        supplemental_input_count = len(supplemental_docs)
        docs = self._apply_strict_filter(docs, scope_predicate)
        supplemental_docs = self._apply_strict_filter(supplemental_docs, scope_predicate)
        scope_filter_trace = {
            "input_count": input_count, "retained_count": len(docs),
            "excluded_count": input_count - len(docs),
            "supplemental_input_count": supplemental_input_count,
            "supplemental_retained_count": len(supplemental_docs),
        }
        if any(owner.get("source_sections") for owner in obligations):
            scope_filter_trace["source_sections_by_owner"] = {
                str(owner.get("obligation_id") or ""): list(owner.get("source_sections") or [])
                for owner in obligations
            }
        if any(owner.get("source_section_bindings") for owner in obligations):
            scope_filter_trace["source_section_bindings_by_owner"] = {
                str(owner.get("obligation_id") or ""): deepcopy(owner.get("source_section_bindings") or [])
                for owner in obligations
            }

        reranked = self._rerank_docs(docs, state)

        intent = state.get("intent") or state.get("query_type", "qa")
        format_preference = str(
            active_subtask.get("format_preference_override")
            or state.get("format_preference")
            or default_format_preference(intent)
        ).strip().lower()
        def selection_key(item: Any) -> tuple[str, Any]:
            source_id = _retrieval_document_source_id(item[0])
            return ("source", source_id) if source_id else ("object", id(item[0]))

        # Reserve distinct sources, retaining their original rerank order.
        # Anonymous objects do not establish equality with another source.
        unique_ranked: Dict[tuple[str, Any], Any] = {}
        for item in reranked:
            unique_ranked.setdefault(selection_key(item), item)
        ranked_docs = list(unique_ranked.values())
        # format_preference에 따라 표/단락 비율 보장
        if format_preference == "table":
            # 수치·추이 쿼리: 표 우선, 단락 최소 2개 보장
            tables = [(d, s) for d, s in ranked_docs if d.metadata.get("block_type") == "table"]
            paras = [(d, s) for d, s in ranked_docs if d.metadata.get("block_type") != "table"]
            # Paragraphs are supplemental; keep a table in the visible window when available.
            min_table = 1 if tables else 0
            min_para = min(2, len(paras), max(effective_k - min_table, 0))
            docs = (tables[: effective_k - min_para] + paras[:min_para])
        elif format_preference == "paragraph":
            # 개요·리스크·일반 쿼리: 단락 최소 절반 보장
            tables = [(d, s) for d, s in ranked_docs if d.metadata.get("block_type") == "table"]
            paras = [(d, s) for d, s in ranked_docs if d.metadata.get("block_type") != "table"]
            min_para = min(effective_k // 2, len(paras))
            docs = (paras[:min_para] + tables[: effective_k - min_para])
            docs.sort(key=lambda x: x[1], reverse=True)
        else:
            docs = ranked_docs[:effective_k]
        # A missing source type must not waste the remaining visible budget.
        # Keep the reserved ordering, then fill from authorized ranked input.
        selected_keys = {selection_key(item) for item in docs}
        for item in ranked_docs:
            if len(docs) >= effective_k:
                break
            key = selection_key(item)
            if key not in selected_keys:
                docs.append(item)
                selected_keys.add(key)

        seed_docs = reranked[: min(len(reranked), effective_k * 4)]
        if semantic_program_required and supplemental_docs:
            seed_docs = self._merge_retry_candidates(seed_docs, supplemental_docs)
        docs = docs[: effective_k]
        retrieved_source_ids, retrieved_unidentified_count = _stable_retrieval_source_ids(
            docs
        )
        seed_source_ids, seed_unidentified_count = _stable_retrieval_source_ids(
            seed_docs
        )
        return {
            "docs": docs,
            "seed_docs": seed_docs,
            "reranked": reranked,
            "format_preference": format_preference,
            "retrieved_source_ids": retrieved_source_ids,
            "retrieved_unidentified_count": retrieved_unidentified_count,
            "seed_source_ids": seed_source_ids,
            "seed_unidentified_count": seed_unidentified_count,
            "scope_filter": scope_filter_trace,
        }

    def _build_trace(
        self,
        state: FinancialAgentState,
        plan: Dict[str, Any],
        searches: Dict[str, Any],
        selection: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Project selected evidence and search telemetry into the graph trace."""
        query = str(plan["query"])
        query_bundle = list(plan["query_bundle"])
        where_filter = plan["where_filter"]
        effective_k = int(plan["effective_k"])
        reflection_count = int(plan["reflection_count"])
        semantic_program_required = bool(plan["semantic_program_required"])
        intent = str(plan["intent"])
        strict_company_scope = bool(plan["strict_company_scope"])
        has_multi_source_scope = bool(plan["has_multi_source_scope"])
        scope_report_type = str(plan["scope_report_type"])
        scope_consolidation = str(plan["scope_consolidation"])
        report_cache_consumer_assessment = dict(
            plan["report_cache_consumer_assessment"]
        )
        report_cache_index_diagnostics = dict(
            plan["report_cache_index_diagnostics"]
        )
        docs = list(selection["docs"])
        seed_docs = list(selection["seed_docs"])
        reranked = list(selection["reranked"])
        format_preference = str(selection["format_preference"])
        retrieved_source_ids = list(selection["retrieved_source_ids"])
        retrieved_unidentified_count = int(
            selection["retrieved_unidentified_count"]
        )
        seed_source_ids = list(selection["seed_source_ids"])
        seed_unidentified_count = int(selection["seed_unidentified_count"])
        executed_queries = list(searches["executed_queries"])
        reused_queries = list(searches["reused_queries"])
        retry_queries = list(searches["retry_queries"])
        query_budget_trace = dict(searches["query_budget_trace"])
        executed_duplicate_trace = dict(searches["executed_duplicate_trace"])
        retrieval_query_result_cache = dict(
            searches["retrieval_query_result_cache"]
        )
        retrieval_hint = str(searches["retrieval_hint"])
        preferred_sections = list(searches["preferred_sections"])
        selected_chunks: List[Dict[str, Any]] = []
        for rank, item in enumerate(docs, start=1):
            doc, score = item
            metadata = dict(getattr(doc, "metadata", {}) or {})
            try:
                serialised_score: Optional[float] = float(score)
            except (TypeError, ValueError):
                serialised_score = None
            selected_chunks.append(
                {
                    "rank": rank,
                    "score": serialised_score,
                    "chunk_uid": metadata.get("chunk_uid") or metadata.get("chunk_id") or metadata.get("id"),
                    "section_path": metadata.get("section_path"),
                    "block_type": metadata.get("block_type"),
                    "company": metadata.get("company"),
                    "year": metadata.get("year"),
                    "rcept_no": metadata.get("rcept_no"),
                }
            )
        retrieval_debug_trace_history = [
            dict(item)
            for item in (state.get("retrieval_debug_trace_history") or [])
            if isinstance(item, dict)
        ]
        cross_trace_reuse_candidates = cross_trace_reuse_candidate_diagnostics(
            [*executed_queries, *reused_queries],
            retrieval_debug_trace_history,
            current_trace_index=len(retrieval_debug_trace_history) + 1,
        )
        query_result_cache_by_source: Dict[str, Dict[str, int]] = {}
        for reused_query in reused_queries:
            source_key = _normalise_spaces(str(reused_query.get("source") or "unknown")) or "unknown"
            source_summary = query_result_cache_by_source.setdefault(
                source_key,
                {
                    "reuse_count": 0,
                    "avoided_search_count": 0,
                    "objective_hit_count": 0,
                },
            )
            source_summary["reuse_count"] += 1
            source_summary["avoided_search_count"] += 1
        retrieval_debug_trace = {
            "query_bundle": list(query_bundle),
            "executed_queries": executed_queries,
            "reused_queries": reused_queries,
            "search_summary": summarize_executed_query_telemetry(executed_queries),
            "where_filter": where_filter,
            "effective_k": effective_k,
            "reflection_count": reflection_count,
            "retry_queries": retry_queries,
            "query_budget": query_budget_trace,
            "executed_duplicate_guard": executed_duplicate_trace,
            "query_result_cache": {
                "enabled": True,
                "scope": "state_same_filter_exact_signature",
                "entry_count": len(retrieval_query_result_cache),
                "reuse_count": len(reused_queries),
                "avoided_search_count": len(reused_queries),
                "objective_hit_count": 0,
                "by_source": query_result_cache_by_source,
            },
            "cross_trace_reuse_candidates": cross_trace_reuse_candidates,
            "report_cache_consumer_assessment": {
                **report_cache_consumer_assessment,
                "normal_retrieval_executed": bool(executed_queries),
                "executed_query_count": len(executed_queries),
            },
            "report_cache_index_diagnostics": {
                **report_cache_index_diagnostics,
                "normal_retrieval_executed": bool(executed_queries),
                "executed_query_count": len(executed_queries),
            },
            "candidate_count": len(reranked),
            "scope_filter": dict(selection.get("scope_filter") or {}),
            "source_scope_search": dict(searches.get("source_scope_search") or {}),
            "seed_count": len(seed_docs),
            "selected_count": len(docs),
            "selected_chunks": selected_chunks,
            "source_window": {
                "retrieved_source_ids": retrieved_source_ids,
                "retrieved_unidentified_count": retrieved_unidentified_count,
                "seed_source_ids": seed_source_ids,
                "seed_unidentified_count": seed_unidentified_count,
            },
            "policy_trace": {
                "intent": intent,
                "answer_mode": "semantic_program" if semantic_program_required else "narrative",
                "retrieval_mode": str(
                    getattr(self, "retrieval_mode", "hybrid") or "hybrid"
                ),
                "degraded_reason": str(
                    getattr(self, "retrieval_degraded_reason", "") or ""
                ),
                "format_preference": format_preference,
                "retrieval_hint": retrieval_hint if len(query_bundle) == 1 else "",
                "preferred_sections": (
                    list(preferred_sections or []) if len(query_bundle) == 1 else []
                ),
                "query_enrichment_mode": "per_query",
                "query_enrichment": list(
                    query_budget_trace.get("enrichment", {}).get("queries") or []
                ),
                "preferred_statement_types": list(
                    _active_preferred_statement_types(state, query, state.get("topic") or "")
                ),
                "strict_company_scope": strict_company_scope,
                "multi_source_scope": has_multi_source_scope,
                "scope_report_type": scope_report_type,
                "scope_consolidation": scope_consolidation,
            },
        }
        logger.info(
            "[retrieve] intent=%s format=%s final %s chunks returned",
            intent,
            format_preference,
            len(docs),
        )
        retrieval_debug_trace_history.append(retrieval_debug_trace)
        return {
            "seed_retrieved_docs": seed_docs,
            "retrieved_docs": docs,
            "retrieval_debug_trace": retrieval_debug_trace,
            "retrieval_debug_trace_history": retrieval_debug_trace_history,
            "retrieval_query_result_cache": retrieval_query_result_cache,
        }

    def _retrieve(self, state: RetrievalInput) -> RetrievalPhase:
        """Run the four retrieval boundary stages in a stable order."""
        plan = self._build_plan(state)
        searches = self._execute_searches(state, plan)
        selection = self._select_evidence(state, plan, searches)
        return self._build_trace(state, plan, searches, selection)
