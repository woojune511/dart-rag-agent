"""Retrieval pipeline owner for the FinancialAgent graph.

This module owns retrieval query construction, filtering, search execution,
reranking, candidate selection, and retrieval trace projection. Evidence
construction and answer validation remain in financial_graph_evidence.py.
"""

from __future__ import annotations

import logging
import json
import re
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from src.agent.financial_graph_helpers import _build_generic_metric_aliases
from src.agent.financial_graph_retrieval_budget import (
    _apply_query_budget,
    _cross_trace_reuse_candidate_diagnostics,
    _drop_duplicate_executed_query,
    _drop_queries_already_selected,
    _limit_query_context_terms,
    _lookup_query_result_cache,
    _query_budget_int,
    _store_query_result_cache,
    _summarize_executed_query_telemetry,
)
from src.agent.financial_langchain_loaders import _document
from src.agent.financial_retrieval_hints import (
    _active_preferred_sections,
    _active_preferred_statement_types,
    _retrieval_hint_from_topic,
)
from src.agent.financial_runtime_normalization import _normalise_spaces
from src.agent.financial_runtime_trace import _resolve_runtime_calculation_trace
from src.agent.financial_row_surfaces import _operand_text_match
from src.agent.financial_scope_policies import (
    _desired_consolidation_scope,
    _metadata_period_match_strength,
    _report_scope_source_receipts,
    _should_apply_strict_company_scope,
)
from src.agent.financial_surface_contracts import (
    _operand_needles,
    _text_has_negative_surface,
    _text_has_positive_surface,
)
from src.agent.financial_text_surface import (
    _strip_rerank_metadata,
    _tokenize_terms,
)
from src.config.report_scoped_cache import classify_report_cache_consumer_candidate
from src.config.retrieval_policy import (
    EVIDENCE_RUNTIME_POLICY,
    KOREAN_COUNT_UNIT_RE_FRAGMENT,
    KOREAN_PERIOD_COMPARISON_RE_FRAGMENT,
    KOREAN_PERIOD_PREFIX_RE_FRAGMENT,
    METRIC_TOPIC_EXTRACTION_TERMS,
    NARRATIVE_RERANK_POLICY,
    PERIOD_COMPARISON_COUNT_POLICY,
    QUANTITATIVE_IMPACT_ASSEMBLY_POLICY,
    QUANTITATIVE_IMPACT_QUERY_TERMS,
    QUERY_FOCUS_MARKER_POLICY,
    REQUIRED_OPERAND_ASSEMBLY_POLICY,
    active_narrative_policies,
    narrative_policy_active,
    narrative_policy_facets,
    narrative_policy_paragraph_priority_sections,
    narrative_policy_preferred_sections,
    narrative_policy_slot_groups,
    narrative_policy_terms,
)
from src.routing import default_format_preference
from src.storage.report_cache_index import ReportCacheIndex

if TYPE_CHECKING:
    from langchain_core.documents import Document

    from src.agent.financial_graph_state import FinancialAgentState


logger = logging.getLogger(__name__)


_COUNT_VALUE_UNIT_RE = (
    r"(?P<value>[\(\)\-]?\d[\d,]*(?:\.\d+)?)\s*"
    rf"(?P<unit>{KOREAN_COUNT_UNIT_RE_FRAGMENT})"
)


def _metric_terms_from_topic(topic: str) -> set[str]:
    text = _normalise_spaces(topic)
    known_terms = [str(item) for item in METRIC_TOPIC_EXTRACTION_TERMS if str(item)]
    return {term for term in known_terms if term in text}


def _report_cache_consumer_assessment_for_retrieval(state: Dict[str, Any]) -> Dict[str, Any]:
    trace = _resolve_runtime_calculation_trace(dict(state), allow_legacy_top_level=False)
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

    trace = _resolve_runtime_calculation_trace(dict(state), allow_legacy_top_level=False)
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


def _period_target_for_operand(operand: Dict[str, Any], query_years: List[str], report_scope: Dict[str, Any]) -> str:
    label = _normalise_spaces(str(operand.get("label") or ""))
    match = re.search(r"(20\d{2})년?", label)
    if match:
        return match.group(1)
    period_hint = _normalise_spaces(str(operand.get("period_hint") or ""))
    match = re.search(r"(20\d{2})", period_hint)
    if match:
        return match.group(1)
    report_year = str(report_scope.get("year") or "").strip()
    role = str(operand.get("role") or "").strip()
    if report_year.isdigit() and role == "prior_period":
        return str(int(report_year) - 1)
    if report_year.isdigit() and role == "current_period":
        return report_year
    return query_years[0] if query_years else report_year


def _operand_context_surface_variants(operand: Dict[str, Any]) -> List[str]:
    variants: List[str] = []
    for needle in _operand_needles(operand):
        normalized = _normalise_spaces(re.sub(rf"^{KOREAN_PERIOD_PREFIX_RE_FRAGMENT}\s+", "", needle))
        if not normalized:
            continue
        variants.append(normalized)
        tokens = normalized.split()
        if len(tokens) >= 2:
            variants.append(" ".join(tokens[:-1]))
    expanded: List[str] = []
    for variant in variants:
        expanded.append(variant)
        if re.search(r"[가-힣]", variant) and " " in variant:
            expanded.append(re.sub(r"\s+", "", variant))
    return list(dict.fromkeys(item for item in expanded if item))


def _sentence_matches_operand_context(sentence: str, operand: Dict[str, Any]) -> bool:
    normalized = _normalise_spaces(sentence)
    compact = re.sub(r"\s+", "", normalized)
    for surface in _operand_context_surface_variants(operand):
        surface_normalized = _normalise_spaces(surface)
        surface_compact = re.sub(r"\s+", "", surface_normalized)
        if surface_normalized in normalized or (surface_compact and surface_compact in compact):
            return True
    return False


def _sentence_has_subject_after_location_context(sentence: str) -> bool:
    location_subject_pattern = str(EVIDENCE_RUNTIME_POLICY.get("location_subject_pattern") or "")
    return bool(
        location_subject_pattern
        and re.search(location_subject_pattern, re.sub(r"\s+", "", sentence))
    )


_LOOKUP_AGGREGATE_RESULT_RE = re.compile(
    str(EVIDENCE_RUNTIME_POLICY.get("lookup_aggregate_result_pattern") or r"$^")
)


def _lookup_text_has_explicit_aggregate_result(text: str) -> bool:
    normalized = _normalise_spaces(text)
    for match in _LOOKUP_AGGREGATE_RESULT_RE.finditer(normalized):
        previous = normalized[match.start() - 1] if match.start() > 0 else ""
        if previous and re.fullmatch(r"[A-Za-z0-9가-힣_]", previous):
            continue
        return True
    return False


def _safe_json_loads(value: Any) -> Any:
    if not value:
        return None
    try:
        return json.loads(str(value))
    except (TypeError, ValueError):
        return None


def _active_lookup_required_operands(state: FinancialAgentState) -> List[Dict[str, Any]]:
    active_subtask = dict(state.get("active_subtask") or {})
    operation_family = _normalise_spaces(str(active_subtask.get("operation_family") or "")).lower()
    if operation_family not in {"lookup", "single_value"}:
        return []
    return [
        dict(item)
        for item in (active_subtask.get("required_operands") or [])
        if isinstance(item, dict) and bool(item.get("required", True))
    ]


def _numeric_extractor_query_for_state(state: FinancialAgentState) -> str:
    active_subtask = dict(state.get("active_subtask") or {})
    required_operands = _active_lookup_required_operands(state)
    if list(state.get("calc_subtasks") or []) and required_operands:
        operand = required_operands[0]
        label = _normalise_spaces(
            str(
                operand.get("label")
                or operand.get("name")
                or active_subtask.get("metric_label")
                or state.get("query")
                or ""
            )
        )
        period = _normalise_spaces(str(operand.get("period_hint") or ""))
        scope = _normalise_spaces(str(operand.get("consolidation_scope") or ""))
        bits = [bit for bit in (period, scope, label) if bit]
        focused = " ".join(bits) or _normalise_spaces(str(state.get("query") or ""))
        return str(EVIDENCE_RUNTIME_POLICY.get("direct_numeric_lookup_instruction") or "{focused}").format(
            focused=focused
        )
    metric_label = _normalise_spaces(str(active_subtask.get("metric_label") or ""))
    if list(state.get("calc_subtasks") or []) and metric_label:
        return metric_label
    return _normalise_spaces(str(state.get("query") or ""))


def _lookup_retrieval_objective_signature(active_subtask: Dict[str, Any]) -> str:
    operation_family = _normalise_spaces(str(active_subtask.get("operation_family") or "")).lower()
    if operation_family not in {"lookup", "single_value"}:
        return ""
    operand_records: List[Dict[str, str]] = []
    for operand in active_subtask.get("required_operands") or []:
        if not isinstance(operand, dict):
            continue
        operand_records.append(
            {
                "label": _normalise_spaces(str(operand.get("label") or operand.get("name") or "")).lower(),
                "concept": _normalise_spaces(str(operand.get("concept") or "")).lower(),
                "role": _normalise_spaces(str(operand.get("role") or "")).lower(),
                "period": _normalise_spaces(str(operand.get("period_hint") or operand.get("period") or "")).lower(),
                "consolidation_scope": _normalise_spaces(
                    str(operand.get("consolidation_scope") or "")
                ).lower(),
            }
        )
    metric_label = _normalise_spaces(str(active_subtask.get("metric_label") or "")).lower()
    if not operand_records and not metric_label:
        return ""
    return json.dumps(
        {
            "operation_family": operation_family,
            "metric_label": metric_label,
            "required_operands": operand_records,
        },
        ensure_ascii=False,
        sort_keys=True,
    )


def _lookup_line_matches_operand_surface(line: str, operand: Dict[str, Any]) -> bool:
    if _text_has_positive_surface(line, operand) or _operand_text_match(line, operand):
        return True
    assembly_policy = dict(REQUIRED_OPERAND_ASSEMBLY_POLICY)
    token_split_pattern = str(assembly_policy.get("lookup_surface_token_split_pattern") or r"[\s/|,()]+")
    blocked_tokens = {
        str(token)
        for token in (assembly_policy.get("lookup_surface_blocked_tokens") or ())
        if str(token)
    }
    period_prefix_pattern = str(assembly_policy.get("lookup_surface_period_prefix_pattern") or "")
    year_token_pattern = str(QUERY_FOCUS_MARKER_POLICY.get("year_pattern") or "")
    compact_line = re.sub(r"\s+", "", _normalise_spaces(line))
    for needle in _operand_needles(operand):
        needle = _normalise_spaces(needle)
        if period_prefix_pattern:
            needle = re.sub(period_prefix_pattern, "", needle)
        tokens = [
            token
            for token in re.split(token_split_pattern, needle)
            if token
            and not (year_token_pattern and re.fullmatch(year_token_pattern, token))
            and not any(blocked in token for blocked in blocked_tokens)
        ]
        if len(tokens) >= 2 and all(re.sub(r"\s+", "", token) in compact_line for token in tokens):
            return True
        if len(tokens) == 1 and len(re.sub(r"\s+", "", tokens[0])) >= 4 and re.sub(r"\s+", "", tokens[0]) in compact_line:
            return True
    return False


def _line_contains_exact_raw_value(line: str, raw_value: str) -> bool:
    raw_normalized = re.sub(r"[\s,]", "", _normalise_spaces(raw_value))
    if not raw_normalized:
        return False
    for match in re.finditer(r"\(?-?\d[\d,]*(?:\.\d+)?\)?", line):
        token_normalized = re.sub(r"[\s,]", "", match.group(0))
        if token_normalized == raw_normalized:
            return True
    return False


def _lookup_numeric_extraction_has_direct_support(
    state: FinancialAgentState,
    debug_trace: Dict[str, Any],
    docs: List[Any],
    *,
    context: str = "",
) -> bool:
    required_operands = _active_lookup_required_operands(state)
    if not required_operands:
        return True

    raw_value = _normalise_spaces(str(debug_trace.get("raw_value") or ""))
    if not raw_value:
        return False
    result_text = _normalise_spaces(
        " ".join(
            str(debug_trace.get(key) or "")
            for key in ("final_value", "period_check", "consolidation_check")
        )
    )
    result_mentions_aggregate = _lookup_text_has_explicit_aggregate_result(result_text)
    result_compact = re.sub(r"\s+", "", result_text)
    assembly_policy = dict(REQUIRED_OPERAND_ASSEMBLY_POLICY)
    blocked_tokens = {
        str(token)
        for token in (assembly_policy.get("lookup_surface_blocked_tokens") or ())
        if str(token)
    }

    operand = dict(required_operands[0])
    support_operands = [operand]
    active_subtask = dict(state.get("active_subtask") or {})
    metric_label = _normalise_spaces(str(active_subtask.get("metric_label") or ""))
    if metric_label:
        support_operands.append(
            {
                "label": metric_label,
                "aliases": [metric_label],
                "concept": str(operand.get("concept") or ""),
                "role": str(operand.get("role") or ""),
                "required": True,
            }
        )
    if not re.sub(r"[\s,]", "", raw_value):
        return False

    support_doc_scores: List[Any] = list(docs[: min(8, len(docs))])
    seen_support_docs: set[tuple[str, str]] = set()
    for doc_score in support_doc_scores:
        doc = doc_score[0] if isinstance(doc_score, tuple) else doc_score
        metadata = dict(getattr(doc, "metadata", {}) or {})
        seen_support_docs.add(
            (
                str(metadata.get("chunk_uid") or metadata.get("chunk_id") or metadata.get("id") or ""),
                str(getattr(doc, "page_content", "") or ""),
            )
        )
    for doc_score in list(state.get("seed_retrieved_docs") or [])[:32]:
        doc = doc_score[0] if isinstance(doc_score, tuple) else doc_score
        metadata = dict(getattr(doc, "metadata", {}) or {})
        doc_key = (
            str(metadata.get("chunk_uid") or metadata.get("chunk_id") or metadata.get("id") or ""),
            str(getattr(doc, "page_content", "") or ""),
        )
        if doc_key in seen_support_docs:
            continue
        seen_support_docs.add(doc_key)
        support_doc_scores.append(doc_score)

    support_lines: List[str] = []
    support_lines.extend(line for line in re.split(r"[\r\n]+", str(context or "")) if line.strip())

    def _append_table_object_support_lines(metadata: Dict[str, Any]) -> None:
        table_object = _safe_json_loads(metadata.get("table_object_json")) or {}
        if not isinstance(table_object, dict):
            return
        for record in table_object.get("rows") or []:
            if not isinstance(record, dict):
                continue
            row_bits = [
                str(record.get("row_label") or ""),
                str(record.get("semantic_label") or ""),
                " ".join(str(item) for item in (record.get("row_headers") or [])),
                " ".join(str(item) for item in (record.get("semantic_aliases") or [])),
            ]
            for cell in record.get("cells") or []:
                if isinstance(cell, dict):
                    row_bits.append(" ".join(str(item) for item in (cell.get("column_headers") or [])))
                    row_bits.append(str(cell.get("value_text") or ""))
                    row_bits.append(str(cell.get("unit_hint") or ""))
            support_lines.append(_normalise_spaces(" ".join(bit for bit in row_bits if bit)))
        for record in table_object.get("values") or []:
            if not isinstance(record, dict):
                continue
            value_bits = [
                str(record.get("semantic_label") or ""),
                str(record.get("row_label") or ""),
                str(record.get("aggregate_label") or ""),
                " ".join(str(item) for item in (record.get("semantic_aliases") or [])),
                " ".join(str(item) for item in (record.get("row_headers") or [])),
                " ".join(str(item) for item in (record.get("column_headers") or [])),
                str(record.get("period_text") or ""),
                str(record.get("value_text") or ""),
                str(record.get("unit_hint") or ""),
            ]
            support_lines.append(_normalise_spaces(" ".join(bit for bit in value_bits if bit)))

    for item in list(state.get("evidence_items") or []) + list(state.get("runtime_evidence") or []):
        if not isinstance(item, dict):
            continue
        metadata = dict(item.get("metadata") or {})
        for key in ("claim", "quote_span", "raw_row_text", "source_context"):
            value = _normalise_spaces(str(item.get(key) or ""))
            if value:
                support_lines.append(value)
        for key in (
            "row_text",
            "raw_row_text",
            "table_header_context",
            "table_value_labels_text",
            "semantic_label",
            "row_label",
        ):
            value = _normalise_spaces(str(metadata.get(key) or ""))
            if value:
                support_lines.append(value)
        _append_table_object_support_lines(metadata)

    for doc_score in support_doc_scores:
        doc = doc_score[0] if isinstance(doc_score, tuple) else doc_score
        metadata = dict(getattr(doc, "metadata", {}) or {})
        page_content = str(getattr(doc, "page_content", "") or "")
        support_lines.extend(line for line in re.split(r"[\r\n]+", page_content) if line.strip())
        for key in (
            "row_text",
            "raw_row_text",
            "table_header_context",
            "table_value_labels_text",
            "semantic_label",
            "row_label",
        ):
            value = _normalise_spaces(str(metadata.get(key) or ""))
            if value:
                support_lines.append(value)
        for record in _safe_json_loads(metadata.get("table_row_records_json")) or []:
            if not isinstance(record, dict):
                continue
            row_bits = [
                str(record.get("row_label") or ""),
                str(record.get("semantic_label") or ""),
            ]
            for cell in record.get("cells") or []:
                if isinstance(cell, dict):
                    row_bits.append(" ".join(str(item) for item in (cell.get("column_headers") or [])))
                    row_bits.append(str(cell.get("value_text") or ""))
                    row_bits.append(str(cell.get("unit_hint") or ""))
            support_lines.append(_normalise_spaces(" ".join(bit for bit in row_bits if bit)))
        for record in _safe_json_loads(metadata.get("table_value_records_json")) or []:
            if not isinstance(record, dict):
                continue
            value_bits = [
                str(record.get("semantic_label") or ""),
                str(record.get("row_label") or ""),
                str(record.get("aggregate_label") or ""),
                " ".join(str(item) for item in (record.get("semantic_aliases") or [])),
                " ".join(str(item) for item in (record.get("row_headers") or [])),
                " ".join(str(item) for item in (record.get("column_headers") or [])),
                str(record.get("period_text") or ""),
                str(record.get("value_text") or ""),
                str(record.get("unit_hint") or ""),
            ]
            support_lines.append(_normalise_spaces(" ".join(bit for bit in value_bits if bit)))
        _append_table_object_support_lines(metadata)

    raw_value_support_lines: List[Dict[str, Any]] = []
    for line in support_lines:
        normalized = _normalise_spaces(line)
        if not _line_contains_exact_raw_value(normalized, raw_value):
            continue
        if result_mentions_aggregate and _lookup_text_has_explicit_aggregate_result(normalized):
            continue
        operand_checks: List[Dict[str, Any]] = []
        for support_operand in support_operands:
            negative_surface = _text_has_negative_surface(normalized, support_operand)
            surface_match = False if negative_surface else _lookup_line_matches_operand_surface(normalized, support_operand)
            operand_checks.append(
                {
                    "label": _normalise_spaces(str(support_operand.get("label") or ""))[:120],
                    "role": str(support_operand.get("role") or "")[:80],
                    "negative_surface": negative_surface,
                    "surface_match": surface_match,
                }
            )
            if negative_surface:
                continue
            if surface_match:
                return True
        if _lookup_text_has_explicit_aggregate_result(normalized):
            continue
        line_before_value = normalized.split(raw_value, 1)[0]
        result_surface_tokens: List[str] = []
        for token in re.findall(r"[A-Za-z가-힣][A-Za-z가-힣0-9_]{5,}", line_before_value):
            if any(blocked in token for blocked in blocked_tokens):
                continue
            if token:
                result_surface_tokens.append(token[:80])
            if token and token in result_compact:
                return True
        if len(raw_value_support_lines) < 8:
            raw_value_support_lines.append(
                {
                    "line": normalized[:240],
                    "operand_checks": operand_checks,
                    "result_surface_tokens": result_surface_tokens[:8],
                }
            )
    raw_compact = re.sub(r"[\s,]", "", raw_value)
    compact_value_lines = [
        _normalise_spaces(line)[:240]
        for line in support_lines
        if raw_compact and raw_compact in re.sub(r"[\s,]", "", _normalise_spaces(line))
    ]
    diagnostics = {
        "raw_value": raw_value,
        "support_line_count": len(support_lines),
        "raw_value_line_count": sum(
            1 for line in support_lines if _line_contains_exact_raw_value(_normalise_spaces(line), raw_value)
        ),
        "compact_value_line_count": len(compact_value_lines),
        "required_operand_labels": [_normalise_spaces(str(item.get("label") or ""))[:120] for item in support_operands],
        "result_text_preview": result_text[:240],
        "result_mentions_aggregate": result_mentions_aggregate,
        "context_chars": len(str(context or "")),
        "context_contains_compact_raw": bool(
            raw_compact and raw_compact in re.sub(r"[\s,]", "", str(context or ""))
        ),
        "raw_value_support_lines": raw_value_support_lines,
        "compact_value_lines": compact_value_lines[:8],
    }
    debug_trace["direct_support_diagnostics"] = diagnostics
    logger.info(
        "[numeric_extractor] lookup support diagnostics raw=%s exact_lines=%s compact_lines=%s context_contains_raw=%s first_compact_line=%s",
        raw_value,
        diagnostics["raw_value_line_count"],
        diagnostics["compact_value_line_count"],
        diagnostics["context_contains_compact_raw"],
        compact_value_lines[0] if compact_value_lines else "",
    )
    return False


def _period_comparison_count_value_from_text(
    text: str,
    operand: Dict[str, Any],
    *,
    query_years: List[str],
    report_scope: Dict[str, Any],
) -> Optional[Dict[str, str]]:
    normalized = _normalise_spaces(text)
    if not normalized or not re.search(KOREAN_PERIOD_COMPARISON_RE_FRAGMENT, normalized):
        return None

    target_year = _period_target_for_operand(operand, query_years, report_scope)
    if not target_year:
        return None

    count_policy = dict(PERIOD_COMPARISON_COUNT_POLICY)
    sentences = [
        part.strip()
        for part in re.split(str(count_policy.get("sentence_split_pattern") or r"$^"), normalized)
        if part.strip()
    ] or [normalized]
    context_indexes = [
        index
        for index, sentence in enumerate(sentences)
        if _sentence_matches_operand_context(sentence, operand)
    ]
    if not context_indexes:
        return None
    subject_context_indexes = [
        index
        for index in context_indexes
        if _sentence_has_subject_after_location_context(sentences[index])
    ]
    if not subject_context_indexes:
        return None

    candidates: List[tuple[float, Dict[str, str]]] = []
    year_pattern = str(count_policy.get("year_pattern") or r"(20\d{2})")
    for index, sentence in enumerate(sentences):
        period_match = re.search(year_pattern, sentence)
        if not period_match or period_match.group(1) != target_year:
            continue
        if not re.search(KOREAN_PERIOD_COMPARISON_RE_FRAGMENT, sentence):
            continue
        value_matches = list(re.finditer(_COUNT_VALUE_UNIT_RE, sentence))
        if not value_matches:
            continue

        context_hit = _sentence_matches_operand_context(sentence, operand)
        subject_context_hit = _sentence_has_subject_after_location_context(sentence)
        follows_context = any(0 <= index - context_index <= 2 for context_index in subject_context_indexes)
        if not context_hit and not follows_context:
            continue
        if context_hit and not subject_context_hit and not follows_context:
            continue

        score = 1.0
        if context_hit:
            score += 2.0
        if subject_context_hit:
            score += 0.75
        if follows_context and not context_hit:
            score += 0.5

        selected = value_matches[-1]
        stated_change = _stated_period_change_from_text(sentence)
        candidates.append(
            (
                score,
                {
                    "raw_value": selected.group("value"),
                    "raw_unit": _normalise_spaces(selected.group("unit")),
                    "period": f"{target_year}년",
                    **stated_change,
                },
            )
        )

    if not candidates:
        return None
    candidates.sort(key=lambda item: item[0], reverse=True)
    return candidates[0][1]


def _stated_period_change_from_text(text: str) -> Dict[str, str]:
    count_policy = dict(PERIOD_COMPARISON_COUNT_POLICY)
    stated_change_pattern = str(count_policy.get("stated_change_pattern") or "")
    if not stated_change_pattern:
        return {}
    stated_change_match = re.search(stated_change_pattern, text)
    if not stated_change_match:
        return {}
    return {
        "stated_change_raw_value": stated_change_match.group("value"),
        "stated_change_raw_unit": "%"
        if stated_change_match.group("unit") == "%"
        else stated_change_match.group("unit"),
    }


def _period_scoped_count_value_from_text(
    text: str,
    operand: Dict[str, Any],
    *,
    query_years: List[str],
    report_scope: Dict[str, Any],
) -> Optional[Dict[str, str]]:
    normalized = _normalise_spaces(text)
    if not normalized:
        return None
    target_year = _period_target_for_operand(operand, query_years, report_scope)
    if not target_year:
        return None
    count_policy = dict(PERIOD_COMPARISON_COUNT_POLICY)
    year_pattern = str(count_policy.get("year_pattern") or r"$^")
    year_matches = [
        match
        for match in re.finditer(year_pattern, normalized)
        if str(match.group(1) if match.groups() else match.group(0)).strip() == target_year
    ]
    if len(year_matches) != 1:
        return None
    for year_match in year_matches:
        tail = normalized[year_match.end() : year_match.end() + 140]
        value_match = re.search(_COUNT_VALUE_UNIT_RE, tail)
        if not value_match:
            continue
        return {
            "raw_value": value_match.group("value"),
            "raw_unit": _normalise_spaces(value_match.group("unit")),
            "period": target_year,
            **_stated_period_change_from_text(tail),
        }
    return None


def _doc_identity(doc: Document) -> str:
    metadata = dict(getattr(doc, "metadata", {}) or {})
    for key in ("chunk_uid", "chunk_id", "id", "source_id"):
        value = str(metadata.get(key) or "").strip()
        if value:
            return value
    return str(getattr(doc, "page_content", "") or "")[:120]


def _doc_operand_context_text(doc: Document) -> str:
    metadata = dict(getattr(doc, "metadata", {}) or {})
    return _normalise_spaces(
        " ".join(
            part
            for part in (
                str(getattr(doc, "page_content", "") or ""),
                str(metadata.get("table_context") or ""),
                str(metadata.get("table_header_context") or ""),
                str(metadata.get("table_summary_text") or ""),
                str(metadata.get("local_heading") or ""),
                str(metadata.get("section_path") or metadata.get("section") or ""),
            )
            if part
        )
    )


def _doc_has_numeric_signal(doc: Document, ignored_periods: Optional[set[str]] = None) -> bool:
    text = _doc_operand_context_text(doc)
    if not text:
        return False
    ignored = {str(item).strip() for item in (ignored_periods or set()) if str(item).strip()}
    for match in re.finditer(r"\(?-?\d[\d,]*(?:\.\d+)?\)?", text):
        token = str(match.group(0) or "").strip()
        normalized = re.sub(r"[\s,()]", "", token)
        if not normalized:
            continue
        if normalized in ignored:
            continue
        if re.fullmatch(r"20\d{2}", normalized):
            continue
        return True
    return False


def _doc_matches_target_period(doc: Document, target_period: str) -> bool:
    target = _normalise_spaces(str(target_period or ""))
    if not target:
        return True
    metadata = dict(getattr(doc, "metadata", {}) or {})
    metadata_year = _normalise_spaces(str(metadata.get("year") or ""))
    if metadata_year == target:
        return True
    return target in _doc_operand_context_text(doc)


def _is_document_like(doc: Any) -> bool:
    return hasattr(doc, "page_content") and hasattr(doc, "metadata")


def _make_document(*, page_content: str, metadata: Dict[str, Any]) -> Document:
    return _document(page_content=page_content, metadata=metadata)


def _required_operand_coverage_from_docs(
    docs: List[tuple[Document, float]],
    active_subtask: Dict[str, Any],
    query: str,
    report_scope: Dict[str, Any],
) -> Dict[str, Any]:
    required_operands = [
        dict(item)
        for item in (active_subtask.get("required_operands") or [])
        if isinstance(item, dict) and bool(item.get("required", True))
    ]
    if not required_operands:
        return {
            "required_count": 0,
            "covered_count": 0,
            "complete": False,
            "operands": [],
        }

    query_years = re.findall(r"20\d{2}", str(query or ""))
    operand_rows: List[Dict[str, Any]] = []
    for index, operand in enumerate(required_operands):
        target_period = _period_target_for_operand(operand, query_years, report_scope)
        ignored_numeric_periods = {target_period, *query_years}
        matched_doc_ids: List[str] = []
        for doc_score in docs:
            doc = doc_score[0] if isinstance(doc_score, tuple) else doc_score
            if not _is_document_like(doc):
                continue
            if not _doc_has_numeric_signal(doc, ignored_numeric_periods):
                continue
            if not _sentence_matches_operand_context(_doc_operand_context_text(doc), operand):
                continue
            if not _doc_matches_target_period(doc, target_period):
                continue
            matched_doc_ids.append(_doc_identity(doc))
        matched_doc_ids = list(dict.fromkeys(item for item in matched_doc_ids if item))
        operand_rows.append(
            {
                "index": index,
                "label": _normalise_spaces(str(operand.get("label") or "")),
                "role": _normalise_spaces(str(operand.get("role") or "")),
                "target_period": target_period,
                "covered": bool(matched_doc_ids),
                "matched_doc_ids": matched_doc_ids[:5],
            }
        )

    covered_count = sum(1 for row in operand_rows if row.get("covered"))
    return {
        "required_count": len(required_operands),
        "covered_count": covered_count,
        "complete": covered_count == len(required_operands),
        "operands": operand_rows,
    }


def _has_narrative_sibling_subtask(state: FinancialAgentState, active_subtask: Dict[str, Any]) -> bool:
    active_task_id = _normalise_spaces(str(active_subtask.get("task_id") or ""))
    for item in (state.get("calc_subtasks") or []):
        if not isinstance(item, dict):
            continue
        task_id = _normalise_spaces(str(item.get("task_id") or ""))
        if active_task_id and task_id == active_task_id:
            continue
        operation_family = _normalise_spaces(str(item.get("operation_family") or "")).lower()
        if operation_family == "narrative_summary":
            return True
    return False


def _doc_period_count_operand_matches(doc: Document, required_operands: List[Dict[str, Any]]) -> List[int]:
    text = _doc_operand_context_text(doc)
    if not text:
        return []
    if not re.search(KOREAN_PERIOD_COMPARISON_RE_FRAGMENT, text):
        return []
    if not re.search(_COUNT_VALUE_UNIT_RE, text):
        return []
    return [
        index
        for index, operand in enumerate(required_operands)
        if _sentence_matches_operand_context(text, operand)
    ]


def _focused_operand_surface_queries(
    active_subtask: Dict[str, Any],
    query: str,
    report_scope: Dict[str, Any],
) -> List[str]:
    required_operands = [
        dict(item)
        for item in (active_subtask.get("required_operands") or [])
        if isinstance(item, dict)
    ]
    if not required_operands:
        return []
    query_years = re.findall(r"20\d{2}", str(query or ""))
    queries: List[str] = []
    for operand in required_operands:
        target_year = _period_target_for_operand(operand, query_years, report_scope)
        prefix = f"{target_year}년 " if target_year else ""
        for surface in _operand_context_surface_variants(operand):
            surface = _normalise_spaces(surface)
            if surface:
                queries.append(_normalise_spaces(f"{prefix}{surface}"))
    return list(dict.fromkeys(item for item in queries if item))


def _ensure_period_count_operand_docs(
    selected: List[tuple[Document, float]],
    candidates: List[tuple[Document, float]],
    required_operands: List[Dict[str, Any]],
    effective_k: int,
) -> List[tuple[Document, float]]:
    if not required_operands or not candidates or effective_k <= 0:
        return selected[:effective_k]

    covered = set()
    selected_ids = set()
    for item in selected:
        doc = item[0]
        selected_ids.add(_doc_identity(doc))
        covered.update(_doc_period_count_operand_matches(doc, required_operands))

    for candidate in candidates:
        doc = candidate[0]
        identity = _doc_identity(doc)
        if identity in selected_ids:
            continue
        matches = set(_doc_period_count_operand_matches(doc, required_operands))
        if not matches or matches.issubset(covered):
            continue

        if len(selected) < effective_k:
            selected.append(candidate)
        else:
            replace_index = None
            for index in range(len(selected) - 1, -1, -1):
                if not _doc_period_count_operand_matches(selected[index][0], required_operands):
                    replace_index = index
                    break
            if replace_index is None:
                continue
            replaced_identity = _doc_identity(selected[replace_index][0])
            selected_ids.discard(replaced_identity)
            selected[replace_index] = candidate
        selected_ids.add(identity)
        covered.update(matches)
        if len(covered) >= len(required_operands):
            break

    return selected[:effective_k]


class FinancialRetrievalPipelineMixin:
    """Graph-node implementation for retrieval and deterministic candidate selection."""

    def _ensure_preferred_operand_section_docs(
        self,
        docs: List[tuple[Document, float]],
        reranked: List[tuple[Document, float]],
        active_subtask: Dict[str, Any],
        effective_k: int,
    ) -> List[tuple[Document, float]]:
        required_operands = [
            dict(item)
            for item in (active_subtask.get("required_operands") or [])
            if isinstance(item, dict)
        ]
        if not required_operands or not reranked or effective_k <= 0:
            return list(docs or [])[:effective_k]

        preferred_statement_types = [
            _normalise_spaces(str(item))
            for item in (active_subtask.get("preferred_statement_types") or [])
            if _normalise_spaces(str(item))
        ]
        preferred_sections = [
            _normalise_spaces(str(item))
            for item in (active_subtask.get("preferred_sections") or [])
            if _normalise_spaces(str(item))
        ]
        for operand in required_operands:
            preferred_statement_types.extend(
                _normalise_spaces(str(item))
                for item in (operand.get("preferred_statement_types") or [])
                if _normalise_spaces(str(item))
            )
            preferred_sections.extend(
                _normalise_spaces(str(item))
                for item in (operand.get("preferred_sections") or [])
                if _normalise_spaces(str(item))
            )
        preferred_statement_types = list(dict.fromkeys(preferred_statement_types))
        preferred_sections = list(dict.fromkeys(preferred_sections))
        if not preferred_statement_types and not preferred_sections:
            return list(docs or [])[:effective_k]

        operand_needles_by_role = [
            [
                _normalise_spaces(str(needle))
                for needle in _operand_needles(operand)
                if _normalise_spaces(str(needle))
            ]
            for operand in required_operands
        ]
        operand_needles_by_role = [needles for needles in operand_needles_by_role if needles]
        if not operand_needles_by_role:
            return list(docs or [])[:effective_k]

        def _doc_key(item: tuple[Document, float]) -> str:
            doc = item[0]
            metadata = getattr(doc, "metadata", {}) or {}
            return str(metadata.get("chunk_uid") or metadata.get("chunk_id") or metadata.get("id") or id(doc))

        def _doc_surface(doc: Document) -> str:
            metadata = getattr(doc, "metadata", {}) or {}
            return _normalise_spaces(
                " ".join(
                    str(part or "")
                    for part in (
                        metadata.get("section_path"),
                        metadata.get("section"),
                        metadata.get("local_heading"),
                        metadata.get("table_context"),
                        metadata.get("table_row_labels_text"),
                        doc.page_content,
                    )
                )
            )

        def _candidate_priority(item: tuple[Document, float]) -> tuple[int, int, int, int, float]:
            doc, score = item
            metadata = getattr(doc, "metadata", {}) or {}
            if str(metadata.get("block_type") or "").strip().lower() != "table":
                return (0, 0, 0, 0, float(score or 0.0))
            surface = _doc_surface(doc)
            if not surface:
                return (0, 0, 0, 1, float(score or 0.0))
            covered_operands = sum(
                1
                for needles in operand_needles_by_role
                if any(needle and needle in surface for needle in needles)
            )
            if covered_operands <= 0:
                return (0, 0, 0, 1, float(score or 0.0))
            statement_type = _normalise_spaces(str(metadata.get("statement_type") or ""))
            statement_match = int(bool(preferred_statement_types and statement_type in preferred_statement_types))
            section_surface = _normalise_spaces(
                " ".join(
                    str(part or "")
                    for part in (
                        metadata.get("section_path"),
                        metadata.get("section"),
                        metadata.get("local_heading"),
                        metadata.get("table_context"),
                    )
                )
            )
            section_match = int(
                bool(preferred_sections)
                and any(section and section in section_surface for section in preferred_sections)
            )
            if preferred_statement_types and preferred_sections and not (statement_match or section_match):
                return (0, 0, 0, 1, float(score or 0.0))
            if preferred_statement_types and not preferred_sections and not statement_match:
                return (0, 0, 0, 1, float(score or 0.0))
            if preferred_sections and not preferred_statement_types and not section_match:
                return (0, 0, 0, 1, float(score or 0.0))
            return (statement_match, section_match, covered_operands, 1, float(score or 0.0))

        selected = list(docs or [])[:effective_k]
        selected_keys = {_doc_key(item) for item in selected}
        candidate_items = [item for item in reranked if _doc_key(item) not in selected_keys]
        if not candidate_items:
            return selected
        best_candidate = max(candidate_items, key=_candidate_priority)
        best_priority = _candidate_priority(best_candidate)
        if best_priority[:3] == (0, 0, 0):
            return selected

        merged = [best_candidate] + [item for item in selected if _doc_key(item) != _doc_key(best_candidate)]
        return merged[:effective_k]

    def _active_narrative_policies_for_query(self, query: str) -> List[Dict[str, Any]]:
        return list(active_narrative_policies(str(query or "")))

    def _narrative_policy_terms_for_query(self, query: str, *keys: str) -> Dict[str, List[str]]:
        active_policies = self._active_narrative_policies_for_query(query)
        return {key: narrative_policy_terms(active_policies, key) for key in keys}

    def _narrative_policy_facets_for_query(self, query: str, key: str) -> List[Dict[str, Any]]:
        return narrative_policy_facets(self._active_narrative_policies_for_query(query), key)

    def _query_focus_marker_groups(self, query: str, *, limit: int = 8) -> List[Dict[str, Any]]:
        """Extract query-specific entity/policy/concept markers without case IDs."""
        surface = _normalise_spaces(str(query or ""))
        if not surface:
            return []

        groups: List[Dict[str, Any]] = []
        seen: set[str] = set()
        marker_policy = dict(QUERY_FOCUS_MARKER_POLICY)

        def _clean_marker(value: str) -> str:
            marker = _normalise_spaces(value)
            marker = marker.strip(str(marker_policy.get("strip_chars") or ""))
            marker = re.sub(str(marker_policy.get("leading_connector_pattern") or r"$^"), "", marker)
            marker = re.sub(str(marker_policy.get("trailing_connector_pattern") or r"$^"), "", marker)
            marker = re.sub(str(marker_policy.get("trailing_particle_pattern") or r"$^"), "", marker)
            return marker.strip()

        def _is_useful_marker(value: str) -> bool:
            marker = _clean_marker(value)
            if not marker:
                return False
            lowered = marker.lower()
            if lowered in self._QUERY_FOCUS_STOPWORDS:
                return False
            if re.fullmatch(str(marker_policy.get("year_pattern") or r"$^"), marker):
                return False
            if marker.isdigit():
                return False
            if re.fullmatch(str(marker_policy.get("single_letter_pattern") or r"$^"), marker):
                return False
            if len(marker) < 2:
                return False
            return True

        def _append_group(variants: List[str]) -> None:
            cleaned = []
            for variant in variants:
                marker = _clean_marker(variant)
                if not _is_useful_marker(marker):
                    continue
                marker_key = marker.lower()
                if marker_key in {item.lower() for item in cleaned}:
                    continue
                cleaned.append(marker)
            if not cleaned:
                return
            key = "|".join(sorted(marker.lower() for marker in cleaned))
            if key in seen:
                return
            seen.add(key)
            groups.append(
                {
                    "label": str(marker_policy.get("label_template") or "{index}").format(index=len(groups) + 1),
                    "variants": cleaned,
                    "phrase": "",
                    "query_focus": True,
                }
            )

        for match in re.finditer(str(marker_policy.get("parenthetical_pair_pattern") or r"$^"), surface):
            left_surface = _clean_marker(match.group(1))
            for pattern in marker_policy.get("left_context_drop_patterns") or ():
                left_surface = re.sub(str(pattern), "", left_surface)
            left = _clean_marker(left_surface.split()[-1])
            if len(left_surface.split()) > 1 and re.search(r"[가-힣]", left_surface):
                left = _clean_marker(left_surface)
            right = _clean_marker(match.group(2))
            _append_group([left, right])

        for quoted in re.findall(str(marker_policy.get("quoted_pattern") or r"$^"), surface):
            _append_group([quoted])

        for acronym in re.findall(str(marker_policy.get("acronym_pattern") or r"$^"), surface):
            _append_group([acronym])

        for token in re.findall(str(marker_policy.get("english_token_pattern") or r"$^"), surface):
            _append_group([token])

        for token in re.findall(str(marker_policy.get("generic_token_pattern") or r"$^"), surface):
            if len(token) < 2:
                continue
            _append_group([token])

        return groups[:limit]

    def _query_focus_markers(self, query: str, *, limit: int = 8) -> List[str]:
        markers: List[str] = []
        for group in self._query_focus_marker_groups(query, limit=limit):
            for variant in group.get("variants") or []:
                marker = str(variant).strip()
                if marker and marker.lower() not in {item.lower() for item in markers}:
                    markers.append(marker)
        return markers

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
        topic_terms = _tokenize_terms(state.get("topic") or state["query"])
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
        desired_consolidation = _desired_consolidation_scope(state["query"], dict(state.get("report_scope") or {}))
        query_years = sorted(years)
        operation_family = str(active_subtask.get("operation_family") or "").strip().lower()
        query_focus_markers = (
            self._query_focus_markers(str(state.get("query") or ""))
            if operation_family == "narrative_summary"
            else []
        )

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
            body_text = _strip_rerank_metadata(doc.page_content)
            document_terms = _tokenize_terms(
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
            period_match_strength = _metadata_period_match_strength(period_labels, query_years)
            if period_match_strength > 0:
                boosted += 0.10 * period_match_strength

            boosted += self._section_bias(intent, section_path)

            # block_type 보정: format_preference 기반으로 표/단락 선호도 반영
            if format_preference == "paragraph" and block_type == "table":
                boosted -= 0.08
            elif format_preference == "table" and block_type == "paragraph":
                boosted -= 0.04

            if operation_family == "narrative_summary":
                if block_type == "paragraph":
                    boosted += 0.12
                elif block_type == "table":
                    boosted -= 0.14
                causal_markers = tuple(str(item) for item in (NARRATIVE_RERANK_POLICY.get("causal_markers") or ()))
                if any(marker in body_text or marker in section_path for marker in causal_markers):
                    boosted += 0.08
                if query_focus_markers:
                    focus_surface = _normalise_spaces(
                        " ".join(
                            part
                            for part in (
                                body_text,
                                section_path,
                                str(metadata.get("table_context") or ""),
                                str(metadata.get("table_value_labels_text") or ""),
                                str(metadata.get("table_row_labels_text") or ""),
                                str(metadata.get("table_summary_text") or ""),
                            )
                            if part
                        )
                    ).lower()
                    focus_hits = sum(1 for marker in query_focus_markers if marker.lower() in focus_surface)
                    if focus_hits:
                        boosted += min(0.08 * focus_hits, 0.32)

            reranked.append((doc, boosted))

        reranked.sort(key=lambda item: item[1], reverse=True)
        return reranked

    def _select_narrative_summary_docs(self, reranked, state: FinancialAgentState, effective_k: int):
        query = str(state.get("query") or "")
        active_policies = self._active_narrative_policies_for_query(query)
        impact_query = narrative_policy_active(active_policies, "impact_context")
        dividend_policy_query = narrative_policy_active(active_policies, "dividend_policy")
        technology_focus_query = narrative_policy_active(active_policies, "technology_focus")
        policy_context_query = narrative_policy_active(active_policies, "policy_context")
        preferred_section_markers = [item.lower() for item in narrative_policy_preferred_sections(active_policies)]
        paragraph_priority_sections = [
            item.lower()
            for item in narrative_policy_paragraph_priority_sections(active_policies)
        ]
        policy_terms_by_key = self._narrative_policy_terms_for_query(
            query,
            "causal_terms",
            "realized_terms",
            "penalty_terms",
            "focus_terms",
            "technology_terms",
            "payout_terms",
            "policy_terms",
            "liquidity_context_terms",
            "outflow_terms",
            "policy_section_terms",
            "policy_period_markers",
        )
        causal_markers = policy_terms_by_key["causal_terms"]
        realized_markers = policy_terms_by_key["realized_terms"]
        penalty_terms = policy_terms_by_key["penalty_terms"]
        focus_policy_terms = policy_terms_by_key["focus_terms"]
        technology_terms = policy_terms_by_key["technology_terms"]
        dividend_payout_terms = policy_terms_by_key["payout_terms"]
        dividend_policy_terms = policy_terms_by_key["policy_terms"]
        dividend_liquidity_context_terms = policy_terms_by_key["liquidity_context_terms"]
        dividend_outflow_terms = policy_terms_by_key["outflow_terms"]
        dividend_policy_section_terms = policy_terms_by_key["policy_section_terms"]
        dividend_policy_period_markers = policy_terms_by_key["policy_period_markers"]
        driver_groups = self._narrative_driver_groups(query)
        query_focus_markers = self._query_focus_markers(query)
        active_subtask = dict(state.get("active_subtask") or {})
        format_preference = str(
            active_subtask.get("format_preference_override")
            or state.get("format_preference")
            or ""
        ).strip().lower()

        def _doc_surface(doc: Document) -> str:
            metadata = doc.metadata or {}
            return _normalise_spaces(
                " ".join(
                    part
                    for part in (
                        str(doc.page_content or ""),
                        str(metadata.get("table_context") or ""),
                        str(metadata.get("table_value_labels_text") or ""),
                        str(metadata.get("table_row_labels_text") or ""),
                        str(metadata.get("table_summary_text") or ""),
                    )
                    if part
                )
            )

        def _paragraph_priority(item) -> tuple[int, float]:
            doc, score = item
            metadata = doc.metadata or {}
            block_type = str(metadata.get("block_type") or "").strip().lower()
            section_path = str(metadata.get("section_path") or metadata.get("section") or "").lower()
            text = _doc_surface(doc).lower()
            focus_markers = list(dict.fromkeys([*query_focus_markers, *focus_policy_terms]))
            priority = 0
            if block_type == "paragraph":
                priority += 3
            if any(marker in section_path for marker in preferred_section_markers):
                priority += 2
            if any(marker in section_path for marker in paragraph_priority_sections):
                priority += 1
            if technology_focus_query:
                if any(marker.lower() in text for marker in technology_terms):
                    priority += 4
            if any(marker.lower() in text for marker in causal_markers):
                priority += 2
            if impact_query:
                if any(marker.lower() in text for marker in realized_markers):
                    priority += 3
                if any(marker.lower() in section_path or marker.lower() in text for marker in penalty_terms):
                    priority -= 2
            if dividend_policy_query:
                if any(term.lower() in section_path for term in dividend_policy_section_terms):
                    priority += 3
                if any(term in section_path for term in paragraph_priority_sections):
                    priority += 2
                if any(marker.lower() in text for marker in (*dividend_payout_terms, *dividend_policy_terms)):
                    priority += 3
            if focus_markers:
                focus_hits = sum(1 for marker in focus_markers if marker.lower() in text)
                if focus_hits:
                    priority += min(focus_hits, 3)
                elif impact_query:
                    priority -= 2
            return priority, float(score)

        def _driver_group_covered(doc_items, variants: List[str]) -> bool:
            for candidate_item in doc_items:
                candidate_doc = candidate_item[0] if isinstance(candidate_item, (tuple, list)) else candidate_item
                lowered = _doc_surface(candidate_doc).lower()
                if any(variant.lower() in lowered for variant in variants):
                    return True
            return False

        def _has_any_term(surface: str, terms: tuple[str, ...]) -> bool:
            lowered = surface.lower()
            return any(term.lower() in lowered for term in terms)

        def _active_policy_slot_groups() -> List[Dict[str, Any]]:
            slot_groups = narrative_policy_slot_groups(active_policies)
            return [
                group
                for group in slot_groups
                if _has_any_term(query, tuple(group["query_terms"]))
            ]

        def _slot_group_preferences_satisfied(doc: Document, slot_group: Dict[str, Any]) -> bool:
            metadata = getattr(doc, "metadata", {}) or {}
            section_path = str(metadata.get("section_path") or metadata.get("section") or "").lower()
            scope = str(metadata.get("consolidation_scope") or "").strip().lower()
            preferred_scopes = tuple(str(item).lower() for item in (slot_group.get("preferred_consolidation_scopes") or ()))
            preferred_sections = tuple(str(item).lower() for item in (slot_group.get("preferred_section_markers") or ()))
            if preferred_scopes and scope not in preferred_scopes:
                return False
            if preferred_sections and not any(marker in section_path for marker in preferred_sections):
                return False
            return True

        def _doc_matches_entity_slot(doc: Document, variants: List[str], slot_group: Dict[str, Any]) -> bool:
            evidence_terms = tuple(slot_group["evidence_terms"])
            surface = _doc_surface(doc)
            surface_lower = surface.lower()
            if not any(variant.lower() in surface_lower for variant in variants):
                return False
            return _has_any_term(surface, evidence_terms)

        def _entity_slot_group_covered(doc_items, variants: List[str], slot_group: Dict[str, Any]) -> bool:
            for candidate_item in doc_items:
                candidate_doc = candidate_item[0] if isinstance(candidate_item, (tuple, list)) else candidate_item
                if _doc_matches_entity_slot(candidate_doc, variants, slot_group):
                    if _slot_group_preferences_satisfied(candidate_doc, slot_group):
                        return True
            return False

        def _focus_candidate_priority(item, variants: List[str]) -> tuple[int, float]:
            doc, score = item
            metadata = getattr(doc, "metadata", {}) or {}
            block_type = str(metadata.get("block_type") or "").strip().lower()
            period_focus = str(metadata.get("period_focus") or "").strip().lower()
            section_path = str(metadata.get("section_path") or metadata.get("section") or "")
            surface = _doc_surface(doc)
            surface_lower = surface.lower()
            content = _normalise_spaces(str(getattr(doc, "page_content", "") or ""))
            priority = 0
            focus_hits = sum(1 for marker in query_focus_markers if marker.lower() in surface_lower)
            priority += min(focus_hits, 6) * 2
            if block_type == "table":
                priority += 2
            if period_focus == "current":
                priority += 2
            for slot_group in _active_policy_slot_groups():
                evidence_terms = tuple(slot_group.get("evidence_terms") or [])
                term_hits = sum(1 for term in evidence_terms if term.lower() in surface_lower)
                if term_hits:
                    priority += min(2 + term_hits, 5)
                    if _slot_group_preferences_satisfied(doc, slot_group):
                        priority += 4
            if technology_focus_query and any(marker.lower() in surface_lower for marker in focus_policy_terms):
                priority += 3
            if policy_context_query and any(marker.lower() in surface_lower for marker in focus_policy_terms):
                priority += 3
            for variant in variants:
                variant_lower = variant.lower()
                for line in content.splitlines():
                    lowered_line = line.lower()
                    if variant_lower not in lowered_line:
                        continue
                    if "|" in line:
                        priority += 3
                    if re.search(r"\(?-?\d[\d,]*(?:\.\d+)?\)?%?", line):
                        priority += 3
                    break
            if preferred_section_markers and any(marker in section_path.lower() for marker in preferred_section_markers):
                priority += 1
            return priority, float(score)

        entity_slot_groups = _active_policy_slot_groups()
        focus_groups = [
            group
            for group in driver_groups
            if bool(group.get("query_focus")) and list(group.get("variants") or [])
        ]
        table_first_focus_query = bool(format_preference == "table" and focus_groups)

        def _focus_table_priority(item: Any) -> int:
            doc = item[0] if isinstance(item, (tuple, list)) else item
            metadata = getattr(doc, "metadata", {}) or {}
            if str(metadata.get("block_type") or "").strip().lower() != "table":
                return 0
            return max(
                (
                    _focus_candidate_priority(item, list(group.get("variants") or []))[0]
                    for group in focus_groups
                    if list(group.get("variants") or [])
                ),
                default=0,
            )

        realized_policies = [
            policy
            for policy in active_policies
            if narrative_policy_terms([policy], "realized_terms")
            and (narrative_policy_terms([policy], "focus_terms") or query_focus_markers)
        ]

        def _policy_realized_priority_for_policy(item: Any, policy: Dict[str, Any]) -> tuple[int, float]:
            doc, score = item
            metadata = getattr(doc, "metadata", {}) or {}
            block_type = str(metadata.get("block_type") or "").strip().lower()
            period_focus = str(metadata.get("period_focus") or "").strip().lower()
            section_path = str(metadata.get("section_path") or metadata.get("section") or "").lower()
            surface_lower = _doc_surface(doc).lower()
            policy_focus_terms = narrative_policy_terms([policy], "focus_terms")
            if not policy_focus_terms:
                policy_focus_terms = list(query_focus_markers)
            policy_realized_terms = narrative_policy_terms([policy], "realized_terms")
            required_realized_terms = narrative_policy_terms([policy], "required_realized_terms")
            focus_hits = sum(1 for marker in policy_focus_terms if marker.lower() in surface_lower)
            realized_hits = sum(1 for marker in policy_realized_terms if marker.lower() in surface_lower)
            if required_realized_terms and not any(
                marker.lower() in surface_lower for marker in required_realized_terms
            ):
                return 0, float(score)
            if not (focus_hits and realized_hits):
                return 0, float(score)
            priority = min(focus_hits, 4) * 2 + min(realized_hits, 4) * 3
            if block_type == "table":
                priority += 2
            if period_focus == "current":
                priority += 2
            if any(marker in section_path for marker in preferred_section_markers):
                priority += 2
            if any(marker in section_path for marker in paragraph_priority_sections):
                priority += 1
            return priority, float(score)

        def _selected_policy_realized_count(policy: Dict[str, Any]) -> int:
            return sum(1 for item in selected if _policy_realized_priority_for_policy(item, policy)[0] > 0)

        focus_table_fill_limit = 0
        if entity_slot_groups and focus_groups:
            focus_table_fill_limit = min(
                effective_k,
                max(2, len(entity_slot_groups)),
            )
        elif focus_groups:
            focus_table_fill_limit = min(effective_k, 2)
        driver_focus_table_limit = min(effective_k, 2) if focus_groups else 0

        def _selected_focus_table_count() -> int:
            return sum(1 for item in selected if _focus_table_priority(item) > 0)

        paragraph_candidates = []
        remainder = []
        for item in reranked:
            doc = item[0] if isinstance(item, (tuple, list)) else item
            metadata = getattr(doc, "metadata", {}) or {}
            if str(metadata.get("block_type") or "").strip().lower() == "paragraph":
                paragraph_candidates.append(item)
            else:
                remainder.append(item)

        paragraph_limit = min(max(effective_k // 2, 3), effective_k)
        if entity_slot_groups or table_first_focus_query:
            paragraph_limit = 0
        paragraph_candidates.sort(key=_paragraph_priority, reverse=True)
        selected = []
        seen_chunk_ids = set()
        if paragraph_limit > 0:
            for item in paragraph_candidates:
                doc = item[0] if isinstance(item, (tuple, list)) else item
                chunk_id = str((getattr(doc, "metadata", {}) or {}).get("chunk_id") or "")
                if chunk_id and chunk_id in seen_chunk_ids:
                    continue
                selected.append(item)
                if chunk_id:
                    seen_chunk_ids.add(chunk_id)
                if len(selected) >= paragraph_limit:
                    break

        for group in driver_groups:
            variants = list(group.get("variants") or [])
            if not variants or _driver_group_covered(selected, variants):
                continue
            group_candidates = []
            for item in reranked:
                doc = item[0] if isinstance(item, (tuple, list)) else item
                metadata = getattr(doc, "metadata", {}) or {}
                chunk_id = str(metadata.get("chunk_id") or "")
                if chunk_id and chunk_id in seen_chunk_ids:
                    continue
                block_type = str(metadata.get("block_type") or "").strip().lower()
                if block_type not in {"paragraph", "table"}:
                    continue
                lowered = _doc_surface(doc).lower()
                if not any(variant.lower() in lowered for variant in variants):
                    continue
                group_candidates.append(item)
            if not group_candidates:
                continue
            best_item = sorted(
                group_candidates,
                key=lambda candidate: _focus_candidate_priority(candidate, variants),
                reverse=True,
            )[0]
            if (
                driver_focus_table_limit
                and _focus_table_priority(best_item) > 0
                and _selected_focus_table_count() >= driver_focus_table_limit
            ):
                continue
            selected.append(best_item)
            best_doc = best_item[0] if isinstance(best_item, (tuple, list)) else best_item
            best_chunk_id = str((getattr(best_doc, "metadata", {}) or {}).get("chunk_id") or "")
            if best_chunk_id:
                seen_chunk_ids.add(best_chunk_id)

        if entity_slot_groups:
            for group in focus_groups:
                variants = list(group.get("variants") or [])
                for slot_group in entity_slot_groups:
                    evidence_terms = tuple(slot_group["evidence_terms"])
                    if _entity_slot_group_covered(selected, variants, slot_group):
                        continue
                    group_candidates = []
                    for item in reranked:
                        doc = item[0] if isinstance(item, (tuple, list)) else item
                        metadata = getattr(doc, "metadata", {}) or {}
                        chunk_id = str(metadata.get("chunk_id") or "")
                        if chunk_id and chunk_id in seen_chunk_ids:
                            continue
                        surface = _doc_surface(doc)
                        surface_lower = surface.lower()
                        if not any(variant.lower() in surface_lower for variant in variants):
                            continue
                        if not _has_any_term(surface, evidence_terms):
                            continue
                        group_candidates.append(item)
                    if not group_candidates:
                        continue
                    best_item = sorted(
                        group_candidates,
                        key=lambda candidate: _focus_candidate_priority(candidate, variants),
                        reverse=True,
                    )[0]
                    best_doc = best_item[0] if isinstance(best_item, (tuple, list)) else best_item
                    replacement_index = None
                    for index, selected_item in enumerate(selected):
                        selected_doc = selected_item[0] if isinstance(selected_item, (tuple, list)) else selected_item
                        if not _doc_matches_entity_slot(selected_doc, variants, slot_group):
                            continue
                        if _slot_group_preferences_satisfied(selected_doc, slot_group):
                            continue
                        replacement_index = index
                        break
                    if replacement_index is None:
                        if any(
                            _doc_matches_entity_slot(
                                selected_item[0] if isinstance(selected_item, (tuple, list)) else selected_item,
                                variants,
                                slot_group,
                            )
                            for selected_item in selected
                        ):
                            continue
                        selected.append(best_item)
                    else:
                        old_doc = selected[replacement_index][0] if isinstance(selected[replacement_index], (tuple, list)) else selected[replacement_index]
                        old_chunk_id = str((getattr(old_doc, "metadata", {}) or {}).get("chunk_id") or "")
                        if old_chunk_id:
                            seen_chunk_ids.discard(old_chunk_id)
                        selected[replacement_index] = best_item
                    best_chunk_id = str((getattr(best_doc, "metadata", {}) or {}).get("chunk_id") or "")
                    if best_chunk_id:
                        seen_chunk_ids.add(best_chunk_id)

            table_fill_candidates = []
            for item in reranked:
                doc = item[0] if isinstance(item, (tuple, list)) else item
                metadata = getattr(doc, "metadata", {}) or {}
                chunk_id = str(metadata.get("chunk_id") or "")
                if chunk_id and chunk_id in seen_chunk_ids:
                    continue
                if str(metadata.get("block_type") or "").strip().lower() != "table":
                    continue
                surfaces_match = False
                for group in focus_groups:
                    variants = list(group.get("variants") or [])
                    if not variants:
                        continue
                    if any(
                        _doc_matches_entity_slot(doc, variants, slot_group)
                        for slot_group in entity_slot_groups
                    ):
                        surfaces_match = True
                        break
                if not surfaces_match:
                    continue
                table_fill_candidates.append(item)
            for item in sorted(
                table_fill_candidates,
                key=lambda candidate: max(
                    (
                        _focus_candidate_priority(candidate, list(group.get("variants") or []))
                        for group in focus_groups
                        if list(group.get("variants") or [])
                    ),
                    default=(0, float(candidate[1] if isinstance(candidate, (tuple, list)) and len(candidate) > 1 else 0.0)),
                ),
                reverse=True,
            ):
                if focus_table_fill_limit and _selected_focus_table_count() >= focus_table_fill_limit:
                    break
                doc = item[0] if isinstance(item, (tuple, list)) else item
                chunk_id = str((getattr(doc, "metadata", {}) or {}).get("chunk_id") or "")
                if chunk_id and chunk_id in seen_chunk_ids:
                    continue
                selected.append(item)
                if chunk_id:
                    seen_chunk_ids.add(chunk_id)

        if table_first_focus_query and not entity_slot_groups:
            table_fill_candidates = []
            for item in reranked:
                doc = item[0] if isinstance(item, (tuple, list)) else item
                metadata = getattr(doc, "metadata", {}) or {}
                chunk_id = str(metadata.get("chunk_id") or "")
                if chunk_id and chunk_id in seen_chunk_ids:
                    continue
                if str(metadata.get("block_type") or "").strip().lower() != "table":
                    continue
                priority = _focus_table_priority(item)
                if priority <= 0:
                    continue
                table_fill_candidates.append(item)
            for item in sorted(
                table_fill_candidates,
                key=lambda candidate: max(
                    (
                        _focus_candidate_priority(candidate, list(group.get("variants") or []))
                        for group in focus_groups
                        if list(group.get("variants") or [])
                    ),
                    default=(0, float(candidate[1] if isinstance(candidate, (tuple, list)) and len(candidate) > 1 else 0.0)),
                ),
                reverse=True,
            ):
                if focus_table_fill_limit and _selected_focus_table_count() >= focus_table_fill_limit:
                    break
                doc = item[0] if isinstance(item, (tuple, list)) else item
                chunk_id = str((getattr(doc, "metadata", {}) or {}).get("chunk_id") or "")
                if chunk_id and chunk_id in seen_chunk_ids:
                    continue
                selected.append(item)
                if chunk_id:
                    seen_chunk_ids.add(chunk_id)

        quantitative_impact_query = any(marker in query for marker in QUANTITATIVE_IMPACT_QUERY_TERMS)
        if quantitative_impact_query:
            quantitative_focus_stopwords = {
                str(item)
                for item in (QUANTITATIVE_IMPACT_ASSEMBLY_POLICY.get("focus_stopwords") or ())
                if str(item)
            }
            relation_markers = tuple(
                str(item)
                for item in (QUANTITATIVE_IMPACT_ASSEMBLY_POLICY.get("relation_markers") or ())
                if str(item)
            )
            relation_context_markers = tuple(
                str(item)
                for item in (
                    tuple(QUANTITATIVE_IMPACT_ASSEMBLY_POLICY.get("primary_denominator_markers") or ())
                    + tuple(QUANTITATIVE_IMPACT_ASSEMBLY_POLICY.get("denominator_markers") or ())
                    + tuple(QUANTITATIVE_IMPACT_ASSEMBLY_POLICY.get("cost_relation_context_markers") or ())
                )
                if str(item)
            )
            focus_token_pattern = str(QUERY_FOCUS_MARKER_POLICY.get("generic_token_pattern") or "")
            focus_terms = [
                term
                for term in (re.findall(focus_token_pattern, query) if focus_token_pattern else [])
                if len(term) >= 3
                and term not in quantitative_focus_stopwords
                and not any(
                    term == excluded or term in excluded or (len(excluded) >= 3 and term.startswith(excluded))
                    for excluded in (
                        relation_markers
                        + relation_context_markers
                        + tuple(QUANTITATIVE_IMPACT_ASSEMBLY_POLICY.get("primary_denominator_markers") or ())
                        + tuple(QUANTITATIVE_IMPACT_ASSEMBLY_POLICY.get("denominator_markers") or ())
                    )
                    if str(excluded)
                )
            ]
            for focus_term in list(dict.fromkeys(focus_terms))[:6]:
                if any(focus_term in _doc_surface(item[0] if isinstance(item, (tuple, list)) else item) for item in selected):
                    continue
                for item in reranked:
                    doc = item[0] if isinstance(item, (tuple, list)) else item
                    metadata = getattr(doc, "metadata", {}) or {}
                    chunk_id = str(metadata.get("chunk_id") or "")
                    if chunk_id and chunk_id in seen_chunk_ids:
                        continue
                    if str(metadata.get("block_type") or "").strip().lower() != "table":
                        continue
                    if focus_term not in _doc_surface(doc):
                        continue
                    selected.append(item)
                    if chunk_id:
                        seen_chunk_ids.add(chunk_id)
                    break
            if relation_markers and focus_terms:
                def _has_quantitative_relation_doc(doc: Document) -> bool:
                    surface = _doc_surface(doc)
                    return (
                        any(term in surface for term in focus_terms)
                        and any(marker in surface for marker in relation_markers)
                        and (
                            not relation_context_markers
                            or any(marker in surface for marker in relation_context_markers)
                        )
                    )

                if not any(_has_quantitative_relation_doc(item[0] if isinstance(item, (tuple, list)) else item) for item in selected):
                    for item in reranked:
                        doc = item[0] if isinstance(item, (tuple, list)) else item
                        metadata = getattr(doc, "metadata", {}) or {}
                        chunk_id = str(metadata.get("chunk_id") or "")
                        if chunk_id and chunk_id in seen_chunk_ids:
                            continue
                        if not _has_quantitative_relation_doc(doc):
                            continue
                        selected.append(item)
                        if chunk_id:
                            seen_chunk_ids.add(chunk_id)
                        break

        if dividend_policy_query:
            def _append_dividend_specific_doc(predicate) -> None:
                for item in reranked:
                    doc = item[0] if isinstance(item, (tuple, list)) else item
                    metadata = getattr(doc, "metadata", {}) or {}
                    chunk_id = str(metadata.get("chunk_id") or "")
                    if chunk_id and chunk_id in seen_chunk_ids:
                        continue
                    if not predicate(doc):
                        continue
                    selected.append(item)
                    if chunk_id:
                        seen_chunk_ids.add(chunk_id)
                    break

            def _is_payout_doc(doc: Document) -> bool:
                metadata = getattr(doc, "metadata", {}) or {}
                text = _doc_surface(doc)
                section_path = _normalise_spaces(str(metadata.get("section_path") or metadata.get("section") or "")).lower()
                local_heading = _normalise_spaces(str(metadata.get("local_heading") or "")).lower()
                return (
                    any(term in text for term in dividend_payout_terms)
                    and bool(self._extract_dividend_amount_surface(text))
                    and (
                        any(term in section_path or term in local_heading for term in dividend_liquidity_context_terms)
                        or any(term in text for term in dividend_outflow_terms)
                    )
                )

            def _is_policy_doc(doc: Document) -> bool:
                metadata = getattr(doc, "metadata", {}) or {}
                text = _doc_surface(doc)
                section_path = _normalise_spaces(str(metadata.get("section_path") or metadata.get("section") or "")).lower()
                return (
                    any(marker in text for marker in dividend_policy_terms)
                    and (
                        any(term in section_path for term in dividend_policy_section_terms)
                        or (
                            bool(dividend_policy_period_markers)
                            and all(marker in text for marker in dividend_policy_period_markers)
                        )
                    )
                )

            _append_dividend_specific_doc(_is_payout_doc)
            _append_dividend_specific_doc(_is_policy_doc)

        for realized_policy in realized_policies:
            if _selected_policy_realized_count(realized_policy) > 0:
                continue
            policy_realized_candidates = []
            for item in reranked:
                doc = item[0] if isinstance(item, (tuple, list)) else item
                metadata = getattr(doc, "metadata", {}) or {}
                chunk_id = str(metadata.get("chunk_id") or "")
                if chunk_id and chunk_id in seen_chunk_ids:
                    continue
                if _policy_realized_priority_for_policy(item, realized_policy)[0] <= 0:
                    continue
                policy_realized_candidates.append(item)
            if policy_realized_candidates and len(selected) < effective_k:
                best_item = sorted(
                    policy_realized_candidates,
                    key=lambda candidate: _policy_realized_priority_for_policy(candidate, realized_policy),
                    reverse=True,
                )[0]
                selected.append(best_item)
                best_doc = best_item[0] if isinstance(best_item, (tuple, list)) else best_item
                best_chunk_id = str((getattr(best_doc, "metadata", {}) or {}).get("chunk_id") or "")
                if best_chunk_id:
                    seen_chunk_ids.add(best_chunk_id)
            elif policy_realized_candidates and effective_k > 0:
                best_item = sorted(
                    policy_realized_candidates,
                    key=lambda candidate: _policy_realized_priority_for_policy(candidate, realized_policy),
                    reverse=True,
                )[0]
                replacement_index = None
                replacement_key: tuple[int, float] = (10_000, float("inf"))
                for index, selected_item in enumerate(selected):
                    priority, score = _policy_realized_priority_for_policy(selected_item, realized_policy)
                    if priority > 0:
                        continue
                    candidate_key = (priority, float(score))
                    if candidate_key < replacement_key:
                        replacement_index = index
                        replacement_key = candidate_key
                if replacement_index is not None:
                    old_doc = selected[replacement_index][0] if isinstance(selected[replacement_index], (tuple, list)) else selected[replacement_index]
                    old_chunk_id = str((getattr(old_doc, "metadata", {}) or {}).get("chunk_id") or "")
                    if old_chunk_id:
                        seen_chunk_ids.discard(old_chunk_id)
                    selected[replacement_index] = best_item
                    best_doc = best_item[0] if isinstance(best_item, (tuple, list)) else best_item
                    best_chunk_id = str((getattr(best_doc, "metadata", {}) or {}).get("chunk_id") or "")
                    if best_chunk_id:
                        seen_chunk_ids.add(best_chunk_id)

        final_candidates = []
        for item in reranked:
            doc = item[0] if isinstance(item, (tuple, list)) else item
            chunk_id = str((getattr(doc, "metadata", {}) or {}).get("chunk_id") or "")
            if chunk_id and chunk_id in seen_chunk_ids:
                continue
            if (
                focus_table_fill_limit
                and _focus_table_priority(item) > 0
                and _selected_focus_table_count() >= focus_table_fill_limit
            ):
                continue
            final_candidates.append(item)

        final_fill_priority = None
        local_section_fill_floor = 0
        if selected and (entity_slot_groups or table_first_focus_query):
            def _item_metadata(doc_item: Any) -> Dict[str, Any]:
                item_doc = doc_item[0] if isinstance(doc_item, (tuple, list)) else doc_item
                return getattr(item_doc, "metadata", {}) or {}

            selected_table_sections = list(
                dict.fromkeys(
                    _normalise_spaces(
                        str(metadata.get("section_path") or metadata.get("section") or "")
                    ).lower()
                    for selected_item in selected
                    for metadata in [_item_metadata(selected_item)]
                    if str(metadata.get("block_type") or "").strip().lower() == "table"
                )
            )

            def _final_fill_priority(candidate: Any) -> tuple[int, float]:
                doc, score = candidate
                metadata = getattr(doc, "metadata", {}) or {}
                section_path = _normalise_spaces(
                    str(metadata.get("section_path") or metadata.get("section") or "")
                ).lower()
                block_type = str(metadata.get("block_type") or "").strip().lower()
                priority = 0
                if section_path and section_path in selected_table_sections:
                    priority += 5
                elif section_path and any(
                    selected_section
                    and (section_path in selected_section or selected_section in section_path)
                    for selected_section in selected_table_sections
                ):
                    priority += 2
                if block_type == "table" and format_preference == "table":
                    priority += 1
                return priority, float(score)

            final_fill_priority = _final_fill_priority
            local_section_fill_floor = min(
                effective_k,
                max(3, len([section for section in selected_table_sections if section])),
            )
            final_candidates.sort(key=final_fill_priority, reverse=True)

        for item in final_candidates:
            doc = item[0] if isinstance(item, (tuple, list)) else item
            chunk_id = str((getattr(doc, "metadata", {}) or {}).get("chunk_id") or "")
            if (
                final_fill_priority is not None
                and local_section_fill_floor
                and len(selected) >= local_section_fill_floor
                and final_fill_priority(item)[0] <= 0
            ):
                continue
            selected.append(item)
            if chunk_id:
                seen_chunk_ids.add(chunk_id)
            if len(selected) >= effective_k:
                break

        return selected[:effective_k]

    def _retrieve(self, state: FinancialAgentState) -> Dict[str, Any]:
        """Retrieve top candidate chunks and rerank them for the active task."""
        query = state["query"]
        retrieval_queries = [str(item).strip() for item in (state.get("retrieval_queries") or []) if str(item).strip()]
        active_subtask = dict(state.get("active_subtask") or {})
        active_subtask_query = str(active_subtask.get("query") or "").strip()
        active_subtask_retrieval_queries = [
            str(item).strip()
            for item in (active_subtask.get("retrieval_queries") or [])
            if str(item).strip()
        ]
        report_scope = dict(state.get("report_scope") or {})
        companies = list(state.get("companies", []) or [])
        years = list(state.get("years", []) or [])
        scope_company = str(report_scope.get("company") or "").strip()
        strict_company_scope = _should_apply_strict_company_scope(companies, report_scope)
        if scope_company and strict_company_scope and scope_company not in companies:
            companies = [scope_company, *companies] if companies else [scope_company]
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
        scope_source_receipts = _report_scope_source_receipts(report_scope)
        has_multi_source_scope = len(scope_source_receipts) > 1
        scope_consolidation = str(report_scope.get("consolidation") or "").strip()
        section_filter = state.get("section_filter")
        intent = str(active_subtask.get("intent_override") or state.get("intent") or state.get("query_type", "qa"))
        reflection_count = int(state.get("reflection_count") or 0)
        retry_queries = [str(item).strip() for item in (state.get("retry_queries") or []) if str(item).strip()]
        effective_k = self.k if reflection_count <= 0 else max(self.k * 2, 4)
        report_cache_consumer_assessment = _report_cache_consumer_assessment_for_retrieval(dict(state))
        report_cache_index_diagnostics = _report_cache_index_diagnostics_for_retrieval(
            dict(state),
            state.get("report_cache_index_path") or getattr(self, "report_cache_index_path", ""),
        )

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

        operation_family = str(active_subtask.get("operation_family") or "").strip().lower()
        lookup_objective_signature = _lookup_retrieval_objective_signature(active_subtask)
        retrieval_intent = intent
        if operation_family in {"lookup", "single_value", "ratio", "sum", "difference", "growth_rate"} and intent not in {
            "comparison",
            "trend",
            "numeric_fact",
        }:
            retrieval_intent = "comparison"
        retrieval_hint = _retrieval_hint_from_topic(query, state.get("topic") or query, retrieval_intent)
        preferred_sections = _active_preferred_sections(state, query, state.get("topic") or "", retrieval_intent)
        query_bundle = (
            active_subtask_retrieval_queries
            or ([active_subtask_query] if active_subtask_query else [])
            or retrieval_queries
            or [query]
        )
        if operation_family == "narrative_summary":
            query_bundle = list(query_bundle)
            for supplemental_query in (query, str(state.get("topic") or "").strip()):
                if supplemental_query and supplemental_query not in query_bundle:
                    query_bundle.append(supplemental_query)
            if any(marker in query for marker in QUANTITATIVE_IMPACT_QUERY_TERMS):
                quantitative_focus_stopwords = {
                    str(item)
                    for item in (QUANTITATIVE_IMPACT_ASSEMBLY_POLICY.get("focus_stopwords") or ())
                    if str(item)
                }
                focus_token_pattern = str(QUERY_FOCUS_MARKER_POLICY.get("generic_token_pattern") or "")
                focus_terms = [
                    term
                    for term in (re.findall(focus_token_pattern, query) if focus_token_pattern else [])
                    if len(term) >= 3 and term not in quantitative_focus_stopwords
                ]
                relation_terms = [
                    str(item)
                    for item in (QUANTITATIVE_IMPACT_ASSEMBLY_POLICY.get("relation_markers") or ())
                    if str(item)
                ]
                context_terms = [
                    str(item)
                    for item in (
                        tuple(QUANTITATIVE_IMPACT_ASSEMBLY_POLICY.get("primary_denominator_markers") or ())
                        + tuple(QUANTITATIVE_IMPACT_ASSEMBLY_POLICY.get("denominator_markers") or ())
                        + tuple(QUANTITATIVE_IMPACT_ASSEMBLY_POLICY.get("cost_relation_context_markers") or ())
                    )
                    if str(item)
                ]
                relation_query_template = str(
                    QUANTITATIVE_IMPACT_ASSEMBLY_POLICY.get("relation_query_template") or ""
                )
                if relation_query_template and focus_terms and relation_terms:
                    relation_query = _normalise_spaces(
                        relation_query_template.format(
                            focus_terms=" ".join(list(dict.fromkeys(focus_terms))[:4]),
                            relation_terms=" ".join(list(dict.fromkeys(relation_terms))[:4]),
                            context_terms=" ".join(list(dict.fromkeys(context_terms))[:6]),
                        )
                    )
                    if relation_query and relation_query not in query_bundle:
                        query_bundle.append(relation_query)
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
            "active_subtask_operation": str(active_subtask.get("operation_family") or ""),
            "input_primary_query_count": len(query_bundle),
            "active_subtask_retrieval_query_count": len(active_subtask_retrieval_queries),
            "state_retrieval_query_count": len(retrieval_queries),
        }
        primary_budget = _query_budget_int(getattr(self, "retrieval_query_budget", 0))
        query_bundle, query_budget_trace["primary"] = _apply_query_budget(
            list(query_bundle),
            primary_budget,
            dedupe=primary_budget > 0,
        )
        hint_budget = _query_budget_int(getattr(self, "retrieval_hint_query_token_budget", 16))
        section_budget = _query_budget_int(getattr(self, "preferred_section_query_budget", 8))
        retrieval_hint_terms = [item for item in _normalise_spaces(retrieval_hint).split(" ") if item]
        selected_retrieval_hint_terms, hint_enrichment_trace = _limit_query_context_terms(
            retrieval_hint_terms,
            hint_budget,
        )
        selected_preferred_sections, section_enrichment_trace = _limit_query_context_terms(
            list(preferred_sections or []),
            section_budget,
            strategy="head_tail",
        )
        query_budget_trace["enrichment"] = {
            "retrieval_hint": hint_enrichment_trace,
            "preferred_sections": section_enrichment_trace,
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
            enriched_query = f"{' '.join(companies)} {base_query}" if companies else base_query
            if scope_report_type:
                enriched_query = f"{enriched_query} {scope_report_type}".strip()
            if scope_consolidation:
                enriched_query = f"{enriched_query} {scope_consolidation}".strip()
            if selected_retrieval_hint_terms:
                enriched_query = f"{enriched_query} {' '.join(selected_retrieval_hint_terms)}".strip()
            if selected_preferred_sections:
                enriched_query = f"{enriched_query} {' '.join(selected_preferred_sections)}".strip()
            if _drop_duplicate_executed_query(
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
                "query_enrichment": {
                    "retrieval_hint_terms": list(selected_retrieval_hint_terms),
                    "preferred_sections": list(selected_preferred_sections),
                },
                "objective_signature": lookup_objective_signature,
            }
            cached_result = _lookup_query_result_cache(
                retrieval_query_result_cache,
                source="primary",
                executed_query=enriched_query,
                where_filter=where_filter,
                k=search_k,
                objective_signature=lookup_objective_signature,
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
            _store_query_result_cache(
                retrieval_query_result_cache,
                source="primary",
                executed_query=enriched_query,
                where_filter=where_filter,
                k=search_k,
                docs=batch_docs,
                objective_signature=lookup_objective_signature,
            )
            docs = batch_docs if not docs else self._merge_retry_candidates(docs, batch_docs)
        focused_operand_queries = _focused_operand_surface_queries(active_subtask, query, report_scope)
        configured_focused_budget = _query_budget_int(getattr(self, "focused_retrieval_query_budget", 0))
        focused_budget = configured_focused_budget or 8
        primary_operand_coverage = _required_operand_coverage_from_docs(docs, active_subtask, query, report_scope)
        focused_operand_queries, query_budget_trace["operand_focus"] = _apply_query_budget(
            focused_operand_queries,
            focused_budget,
            dedupe=configured_focused_budget > 0,
        )
        query_budget_trace["operand_focus"]["primary_operand_coverage"] = primary_operand_coverage
        skip_blocked_reason = ""
        if _has_narrative_sibling_subtask(state, active_subtask):
            skip_blocked_reason = "narrative_sibling_subtask_present"
        if not skip_blocked_reason:
            focused_operand_queries, duplicate_focus_trace = _drop_queries_already_selected(
                focused_operand_queries,
                query_bundle,
            )
            query_budget_trace["operand_focus"].update(duplicate_focus_trace)
            query_budget_trace["operand_focus"]["selected_count_before_duplicate_drop"] = query_budget_trace[
                "operand_focus"
            ].get("selected_count", 0)
            query_budget_trace["operand_focus"]["selected_count"] = len(focused_operand_queries)
        else:
            query_budget_trace["operand_focus"]["duplicate_drop_blocked_reason"] = skip_blocked_reason
        if focused_operand_queries and bool(primary_operand_coverage.get("complete")):
            query_budget_trace["operand_focus"]["skipped"] = True
            query_budget_trace["operand_focus"]["skip_reason"] = "primary_required_operand_coverage_complete"
            if skip_blocked_reason:
                query_budget_trace["operand_focus"]["skip_blocked_reason"] = skip_blocked_reason
            query_budget_trace["operand_focus"]["selected_count_before_skip"] = query_budget_trace["operand_focus"].get(
                "selected_count",
                0,
            )
            query_budget_trace["operand_focus"]["skipped_queries"] = list(focused_operand_queries)
            query_budget_trace["operand_focus"]["selected_count"] = 0
            focused_operand_queries = []
        else:
            query_budget_trace["operand_focus"]["skipped"] = False
            if skip_blocked_reason:
                query_budget_trace["operand_focus"]["skip_blocked_reason"] = skip_blocked_reason
        if focused_operand_queries:
            focused_docs: List[tuple[Document, float]] = []
            for focused_query in focused_operand_queries:
                if _drop_duplicate_executed_query(
                    seen_executed_query_signatures_by_source,
                    executed_duplicate_trace,
                    source="operand_focus",
                    executed_query=focused_query,
                    base_query=focused_query,
                ):
                    continue
                search_k = max(effective_k * 2, 8)
                query_trace = {
                    "source": "operand_focus",
                    "base_query": focused_query,
                    "executed_query": focused_query,
                    "k": search_k,
                    "where_filter": where_filter,
                    "objective_signature": lookup_objective_signature,
                }
                cached_result = _lookup_query_result_cache(
                    retrieval_query_result_cache,
                    source="operand_focus",
                    executed_query=focused_query,
                    where_filter=where_filter,
                    k=search_k,
                    objective_signature=lookup_objective_signature,
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
                    focused_docs.extend(list(cached_result.get("docs") or []))
                    continue
                executed_queries.append(query_trace)
                batch_docs = self.vsm.search(focused_query, k=search_k, where_filter=where_filter)
                search_telemetry = getattr(self.vsm, "last_search_telemetry", None)
                if isinstance(search_telemetry, dict) and search_telemetry:
                    query_trace["search_telemetry"] = dict(search_telemetry)
                _store_query_result_cache(
                    retrieval_query_result_cache,
                    source="operand_focus",
                    executed_query=focused_query,
                    where_filter=where_filter,
                    k=search_k,
                    docs=batch_docs,
                    objective_signature=lookup_objective_signature,
                )
                focused_docs.extend(batch_docs)
            if focused_docs:
                docs = focused_docs if not docs else self._merge_retry_candidates(docs, focused_docs)
        configured_retry_budget = _query_budget_int(getattr(self, "retry_retrieval_query_budget", 0))
        retry_budget = configured_retry_budget or 3
        retry_queries, query_budget_trace["retry"] = _apply_query_budget(
            retry_queries,
            retry_budget,
            dedupe=configured_retry_budget > 0,
        )
        if not skip_blocked_reason:
            retry_queries, duplicate_retry_trace = _drop_queries_already_selected(
                retry_queries,
                [*query_bundle, *focused_operand_queries],
            )
            query_budget_trace["retry"].update(duplicate_retry_trace)
            query_budget_trace["retry"]["selected_count_before_duplicate_drop"] = query_budget_trace["retry"].get(
                "selected_count",
                0,
            )
            query_budget_trace["retry"]["selected_count"] = len(retry_queries)
        else:
            query_budget_trace["retry"]["duplicate_drop_blocked_reason"] = skip_blocked_reason
        if retry_queries:
            retry_docs: List[tuple[Document, float]] = []
            for retry_query in retry_queries:
                if _drop_duplicate_executed_query(
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
                    "objective_signature": lookup_objective_signature,
                }
                cached_result = _lookup_query_result_cache(
                    retrieval_query_result_cache,
                    source="retry",
                    executed_query=retry_query,
                    where_filter=where_filter,
                    k=search_k,
                    objective_signature=lookup_objective_signature,
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
                _store_query_result_cache(
                    retrieval_query_result_cache,
                    source="retry",
                    executed_query=retry_query,
                    where_filter=where_filter,
                    k=search_k,
                    docs=batch_docs,
                    objective_signature=lookup_objective_signature,
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

        # section_filter는 _rerank_docs에서 +0.20 부스트로만 반영.
        # hard filter로 쓰면 LLM이 wrong section을 추출했을 때 관련 청크가 전부 제외됨.

        if companies and strict_company_scope:
            lowered_companies = {company.lower() for company in companies}
            docs = self._apply_strict_filter(
                docs,
                lambda doc: (
                    str(doc.metadata.get("company", "")).lower() in lowered_companies
                    or any(
                        target in str(doc.metadata.get("company", "")).lower()
                        or str(doc.metadata.get("company", "")).lower() in target
                        for target in lowered_companies
                    )
                ),
            )

        if years and not has_multi_source_scope:
            valid_years = {int(year) for year in years}
            docs = self._apply_strict_filter(
                docs,
                lambda doc: int(doc.metadata.get("year", 0)) in valid_years,
            )

        reranked = self._rerank_docs(docs, state)

        intent = state.get("intent") or state.get("query_type", "qa")
        format_preference = str(
            active_subtask.get("format_preference_override")
            or state.get("format_preference")
            or default_format_preference(intent)
        ).strip().lower()
        if operation_family == "narrative_summary":
            docs = self._select_narrative_summary_docs(reranked, state, effective_k)
        else:
            # format_preference에 따라 표/단락 비율 보장
            if format_preference == "table":
                # 수치·추이 쿼리: 표 우선, 단락 최소 2개 보장
                tables = [(d, s) for d, s in reranked if d.metadata.get("block_type") == "table"]
                paras = [(d, s) for d, s in reranked if d.metadata.get("block_type") != "table"]
                # Paragraphs are supplemental; keep a table in the visible window when available.
                min_table = 1 if tables else 0
                min_para = min(2, len(paras), max(effective_k - min_table, 0))
                docs = (tables[: effective_k - min_para] + paras[:min_para])
            elif format_preference == "paragraph":
                # 개요·리스크·일반 쿼리: 단락 최소 절반 보장
                tables = [(d, s) for d, s in reranked if d.metadata.get("block_type") == "table"]
                paras = [(d, s) for d, s in reranked if d.metadata.get("block_type") != "table"]
                min_para = min(effective_k // 2, len(paras))
                docs = (paras[:min_para] + tables[: effective_k - min_para])
                docs.sort(key=lambda x: x[1], reverse=True)
            else:
                docs = reranked

        seed_docs = reranked[: min(len(reranked), effective_k * 4)]
        docs = docs[: effective_k]
        required_operands = [
            dict(item)
            for item in (active_subtask.get("required_operands") or [])
            if isinstance(item, dict)
        ]
        if required_operands and operation_family != "narrative_summary":
            docs = _ensure_period_count_operand_docs(docs, reranked, required_operands, effective_k)
            docs = self._ensure_preferred_operand_section_docs(docs, reranked, active_subtask, effective_k)
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
        cross_trace_reuse_candidates = _cross_trace_reuse_candidate_diagnostics(
            [*executed_queries, *reused_queries],
            retrieval_debug_trace_history,
            current_trace_index=len(retrieval_debug_trace_history) + 1,
        )
        query_result_cache_by_source: Dict[str, Dict[str, int]] = {}
        objective_cache_hit_count = 0
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
            if str(reused_query.get("result_cache_hit_mode") or "") == "objective":
                source_summary["objective_hit_count"] += 1
                objective_cache_hit_count += 1
        retrieval_debug_trace = {
            "query_bundle": list(query_bundle),
            "executed_queries": executed_queries,
            "reused_queries": reused_queries,
            "search_summary": _summarize_executed_query_telemetry(executed_queries),
            "where_filter": where_filter,
            "effective_k": effective_k,
            "reflection_count": reflection_count,
            "retry_queries": retry_queries,
            "query_budget": query_budget_trace,
            "executed_duplicate_guard": executed_duplicate_trace,
            "query_result_cache": {
                "enabled": True,
                "scope": "state_same_filter_exact_or_lookup_objective_signature",
                "entry_count": len(retrieval_query_result_cache),
                "reuse_count": len(reused_queries),
                "avoided_search_count": len(reused_queries),
                "objective_hit_count": objective_cache_hit_count,
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
            "seed_count": len(seed_docs),
            "selected_count": len(docs),
            "selected_chunks": selected_chunks,
            "policy_trace": {
                "intent": intent,
                "operation_family": operation_family,
                "format_preference": format_preference,
                "retrieval_hint": retrieval_hint,
                "preferred_sections": list(preferred_sections or []),
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
