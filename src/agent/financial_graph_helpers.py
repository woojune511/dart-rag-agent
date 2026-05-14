"""
Shared helper functions for the financial graph agent.

The helpers in this file are intentionally grouped by responsibility so the
reader can scan them in chunks:
1. text and ledger utilities
2. numeric parsing / normalization
3. semantic numeric planning helpers
4. reconciliation and operand matching helpers
5. retrieval hint helpers

`financial_graph.py` and the mixin modules import these helpers rather than
re-implementing small pieces of logic in each phase module.
"""

import ast
import json
import math
import re
from typing import Any, Dict, List, Optional

from src.config import get_financial_ontology
from src.schema import ArtifactKind, ArtifactRecord, TaskKind, TaskRecord, TaskStatus

__all__ = [
    '_tokenize_terms',
    '_normalise_spaces',
    '_split_sentences',
    '_strip_anchor_text',
    '_section_hint_alias',
    '_append_artifact',
    '_upsert_task',
    '_parse_number_text',
    '_safe_eval_formula',
    '_extract_composite_krw',
    '_normalise_operand_value',
    '_extract_period_sort_key',
    '_format_korean_won_compact',
    '_display_operand_label',
    '_strip_rerank_metadata',
    '_metric_terms_from_topic',
    '_is_ratio_percent_query',
    '_desired_statement_types',
    '_desired_consolidation_scope',
    '_metadata_period_match_strength',
    '_prioritize_candidate_items',
    '_query_mentions_metric',
    '_clean_metric_label',
    '_extract_quoted_metric_labels',
    '_extract_generic_operand_labels',
    '_is_single_metric_period_comparison',
    '_extract_year_tokens',
    '_build_generic_metric_aliases',
    '_infer_statement_and_section_hints',
    '_build_generic_required_operands',
    '_infer_generic_metric_label',
    '_build_generic_retrieval_queries',
    '_build_heuristic_numeric_task',
    '_infer_period_focus',
    '_build_task_constraints',
    '_build_retrieval_query_bundle',
    '_build_metric_task_query',
    '_build_semantic_numeric_plan',
    '_build_reconciliation_candidate',
    '_query_years_from_state',
    '_structured_cell_period_text',
    '_operand_target_years',
    '_operand_period_focus',
    '_score_structured_cell',
    '_operand_needles',
    '_operand_text_match',
    '_extract_numeric_value_after_operand_text',
    '_operand_row_matches_requirement',
    '_missing_required_operands',
    '_merge_operand_rows',
    '_extract_table_row_label',
    '_parse_unstructured_table_row_cells',
    '_build_table_value_reconciliation_candidates',
    '_build_table_row_reconciliation_candidates',
    '_candidate_has_numeric_value_signal',
    '_candidate_is_descriptor_row',
    '_is_balance_sheet_aggregate_operand',
    '_candidate_matches_operand',
    '_score_operand_candidate',
    '_build_reconciliation_retry_queries',
    '_deterministic_reconcile_task',
    '_preferred_calc_sections',
    '_is_percent_point_difference_query',
    '_should_coerce_percent_point_unit',
    '_extract_value_near_match',
    '_supplement_section_terms_for_query',
    '_active_preferred_sections',
    '_active_preferred_statement_types',
    '_retrieval_hint_from_topic'
]

# ---------------------------------------------------------------------------
# Text and ledger utilities
# ---------------------------------------------------------------------------

def _tokenize_terms(text: str) -> set[str]:
    tokens = re.findall(r"[가-힣A-Za-z0-9]+", text or "")
    return {token.lower() for token in tokens if len(token) >= 2}


def _normalise_spaces(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def _split_sentences(text: str) -> List[str]:
    cleaned = _normalise_spaces(text)
    if not cleaned:
        return []
    parts = re.split(r"(?<=[.!?])\s+|(?<=다)\s+", cleaned)
    return [part.strip() for part in parts if part.strip()]


def _strip_anchor_text(text: str) -> str:
    cleaned = re.sub(r"\[[^\]]+\]", " ", text or "")
    cleaned = re.sub(r"^[*\-\u2022]+\s*", "", cleaned)
    return _normalise_spaces(cleaned)


def _section_hint_alias(section: str) -> str:
    text = _normalise_spaces(section)
    if not text:
        return ""
    if ">" in text:
        text = text.split(">")[-1].strip()
    text = re.sub(r"^\d+\.\s*", "", text)
    return text


def _append_artifact(
    artifact_list: List[Dict[str, Any]],
    *,
    artifact_id: str,
    task_id: str,
    kind: ArtifactKind,
    status: str = "ok",
    summary: str = "",
    payload: Optional[Dict[str, Any]] = None,
    evidence_refs: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    updated = [dict(item) for item in (artifact_list or [])]
    updated.append(
        ArtifactRecord(
            artifact_id=artifact_id,
            task_id=task_id,
            kind=kind,
            status=status,
            summary=summary,
            payload=dict(payload or {}),
            evidence_refs=[str(value) for value in (evidence_refs or []) if str(value).strip()],
        ).model_dump(mode="json")
    )
    return updated


def _upsert_task(
    task_list: List[Dict[str, Any]],
    *,
    task_id: str,
    kind: TaskKind,
    label: str,
    status: TaskStatus,
    query: str = "",
    metric_family: str = "",
    constraints: Optional[Dict[str, Any]] = None,
    artifact_id: Optional[str] = None,
    notes: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    updated = [dict(item) for item in (task_list or [])]
    for index, item in enumerate(updated):
        if str(item.get("task_id") or "") != task_id:
            continue
        artifact_ids = list(item.get("artifact_ids") or [])
        if artifact_id and artifact_id not in artifact_ids:
            artifact_ids.append(artifact_id)
        updated[index] = TaskRecord(
            task_id=task_id,
            kind=kind,
            label=label,
            status=status,
            query=query or str(item.get("query") or ""),
            metric_family=metric_family or str(item.get("metric_family") or ""),
            constraints=dict(constraints or item.get("constraints") or {}),
            artifact_ids=artifact_ids,
            notes=list(notes or item.get("notes") or []),
        ).model_dump(mode="json")
        return updated

    updated.append(
        TaskRecord(
            task_id=task_id,
            kind=kind,
            label=label,
            status=status,
            query=query,
            metric_family=metric_family,
            constraints=dict(constraints or {}),
            artifact_ids=[artifact_id] if artifact_id else [],
            notes=list(notes or []),
        ).model_dump(mode="json")
    )
    return updated


# ---------------------------------------------------------------------------
# Numeric parsing and normalization
# ---------------------------------------------------------------------------

def _parse_number_text(text: str) -> Optional[float]:
    cleaned = str(text or "").replace(",", "").strip()
    if not cleaned:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


_ALLOWED_FORMULA_FUNCTIONS: Dict[str, Any] = {
    "min": min,
    "max": max,
    "abs": abs,
    "round": round,
    "log": math.log,
    "exp": math.exp,
}


def _safe_eval_formula(expression: str, variables: Dict[str, float]) -> float:
    """Evaluate a restricted arithmetic expression used by calculation plans."""
    tree = ast.parse(expression, mode="eval")

    def _eval(node: ast.AST) -> float:
        if isinstance(node, ast.Expression):
            return _eval(node.body)
        if isinstance(node, ast.Constant):
            if isinstance(node.value, (int, float)):
                return float(node.value)
            raise ValueError("non-numeric constant")
        if isinstance(node, ast.Name):
            if node.id in variables:
                return float(variables[node.id])
            raise ValueError(f"unknown variable: {node.id}")
        if isinstance(node, ast.UnaryOp):
            operand = _eval(node.operand)
            if isinstance(node.op, ast.UAdd):
                return +operand
            if isinstance(node.op, ast.USub):
                return -operand
            raise ValueError("unsupported unary operator")
        if isinstance(node, ast.BinOp):
            left = _eval(node.left)
            right = _eval(node.right)
            if isinstance(node.op, ast.Add):
                return left + right
            if isinstance(node.op, ast.Sub):
                return left - right
            if isinstance(node.op, ast.Mult):
                return left * right
            if isinstance(node.op, ast.Div):
                if right == 0.0:
                    raise ZeroDivisionError("division by zero")
                return left / right
            if isinstance(node.op, ast.Pow):
                return left ** right
            raise ValueError("unsupported binary operator")
        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name):
                raise ValueError("unsupported function call")
            fn = _ALLOWED_FORMULA_FUNCTIONS.get(node.func.id)
            if fn is None:
                raise ValueError(f"unsupported function: {node.func.id}")
            if node.keywords:
                raise ValueError("keyword args are not allowed")
            args = [_eval(arg) for arg in node.args]
            return float(fn(*args))
        raise ValueError(f"unsupported AST node: {type(node).__name__}")

    return float(_eval(tree))


def _extract_composite_krw(text: str) -> Optional[float]:
    cleaned = _normalise_spaces(text)
    composite = re.search(r"(?P<jo>[\d,]+(?:\.\d+)?)\s*조\s*(?P<eok>[\d,]+(?:\.\d+)?)\s*억", cleaned)
    if composite:
        jo = _parse_number_text(composite.group("jo"))
        eok = _parse_number_text(composite.group("eok"))
        if jo is None or eok is None:
            return None
        return jo * 1_0000_0000_0000 + eok * 100_000_000
    only_jo = re.search(r"(?P<jo>[\d,]+(?:\.\d+)?)\s*조\s*원?", cleaned)
    if only_jo:
        jo = _parse_number_text(only_jo.group("jo"))
        if jo is not None:
            return jo * 1_0000_0000_0000
    return None


def _normalise_operand_value(raw_value: str, raw_unit: str) -> tuple[Optional[float], str]:
    """Normalize display-level values into comparison-friendly numeric units."""
    unit = _normalise_spaces(raw_unit).lower()
    composite_krw = _extract_composite_krw(raw_value)
    if composite_krw is not None:
        return composite_krw, "KRW"

    value = _parse_number_text(raw_value)
    if value is None and unit in {"%", "퍼센트"}:
        value = _parse_number_text(str(raw_value or "").replace("%", "").replace("퍼센트", ""))
    if value is None:
        return None, "UNKNOWN"

    krw_scale = {
        "원": 1.0,
        "천원": 1_000.0,
        "백만원": 1_000_000.0,
        "억원": 100_000_000.0,
        "조원": 1_0000_0000_0000.0,
    }
    usd_scale = {
        "usd": 1.0,
        "$": 1.0,
        "달러": 1.0,
        "백만달러": 1_000_000.0,
    }
    count_units = {"개", "명", "곳", "사"}
    percent_units = {"%", "퍼센트"}

    if unit in krw_scale:
        return value * krw_scale[unit], "KRW"
    if unit in usd_scale:
        return value * usd_scale[unit], "USD"
    if unit in count_units:
        return value, "COUNT"
    if unit in percent_units:
        return value, "PERCENT"
    return value, "UNKNOWN"


def _extract_period_sort_key(period: str) -> int:
    text = _normalise_spaces(period)
    year_match = re.search(r"(19|20)\d{2}", text)
    if year_match:
        return int(year_match.group(0))
    if "당기" in text:
        return 9999
    if "전기" in text:
        return 9998
    return -1


def _format_korean_won_compact(value: float) -> str:
    # 1억 이상이면 억 단위에서 반올림, 미만이면 원 단위 그대로
    if abs(value) >= 100_000_000:
        amount = int(round(abs(value) / 100_000_000)) * 100_000_000
    else:
        amount = int(round(abs(value)))
    negative = value < 0
    jo = amount // 1_0000_0000_0000
    amount %= 1_0000_0000_0000
    eok = amount // 100_000_000
    amount %= 100_000_000
    man = amount // 10_000

    parts: List[str] = []
    if jo:
        parts.append(f"{jo}조")
    if eok:
        parts.append(f"{eok:,}억원")
    elif jo:
        parts.append("0억원")
    elif man:
        parts.append(f"{man:,}만원")
    else:
        parts.append(f"{int(round(abs(value))):,}원")

    rendered = " ".join(parts)
    return f"-{rendered}" if negative else rendered


def _display_operand_label(label: str) -> str:
    text = _normalise_spaces(label)
    text = re.sub(r"^\d{4}년\s*", "", text)
    text = re.sub(r"^삼성전자\s*", "", text)
    return text


# ---------------------------------------------------------------------------
# Semantic planning helpers
# ---------------------------------------------------------------------------

def _strip_rerank_metadata(text: str) -> str:
    raw = str(text or "")
    raw = re.sub(r"\[[^\]]+\]", " ", raw)
    raw = re.sub(r"\s+", " ", raw)
    return raw.strip()


def _metric_terms_from_topic(topic: str) -> set[str]:
    text = _normalise_spaces(topic)
    known_terms = [
        "영업이익",
        "매출",
        "연구개발비",
        "연구개발",
        "당기순이익",
        "순이익",
        "설비투자",
        "투자",
        "비용",
        "수익",
    ]
    return {term for term in known_terms if term in text}


def _is_ratio_percent_query(text: str) -> bool:
    normalized = _normalise_spaces(text)
    return any(keyword in normalized for keyword in ("비율", "비중", "%", "%p", "이익률", "차지"))


def _desired_statement_types(query: str, topic: str) -> List[str]:
    text = _normalise_spaces(f"{query} {topic}")
    desired: List[str] = []
    if "재무상태표" in text:
        desired.extend(["balance_sheet", "summary_financials"])
    if "손익계산서" in text or "포괄손익계산서" in text:
        desired.extend(["income_statement", "summary_financials", "segment_note"])
    if "현금흐름표" in text:
        desired.extend(["cash_flow", "summary_financials"])
    if "주석" in text:
        desired.extend(["notes"])
    if any(keyword in text for keyword in ("부채비율", "유동비율", "자산총계", "부채총계", "자본총계", "유동자산", "유동부채")):
        desired.extend(["balance_sheet", "summary_financials"])
    if any(keyword in text for keyword in ("영업이익", "당기순이익", "순이익", "매출액", "매출원가", "판매비와관리비", "이익률", "ROE", "ROA")):
        desired.extend(["income_statement", "summary_financials", "segment_note"])
    if any(keyword in text for keyword in ("영업활동현금흐름", "투자활동현금흐름", "재무활동현금흐름", "FCF", "현금흐름")):
        desired.extend(["cash_flow", "summary_financials"])
    return list(dict.fromkeys(desired))


def _desired_consolidation_scope(query: str, report_scope: Dict[str, Any]) -> str:
    text = _normalise_spaces(query)
    if "연결" in text:
        return "consolidated"
    if "별도" in text:
        return "separate"
    scope_value = str((report_scope or {}).get("consolidation") or "").strip()
    if scope_value == "연결":
        return "consolidated"
    if scope_value == "별도":
        return "separate"
    return "unknown"


def _metadata_period_match_strength(period_labels: List[str], query_years: List[int]) -> float:
    if not query_years or not period_labels:
        return 0.0
    normalized_labels = {str(label).strip() for label in period_labels if str(label).strip()}
    wanted = {str(year) for year in query_years}
    overlap = len(normalized_labels & wanted)
    if overlap <= 0:
        return 0.0
    if overlap >= len(wanted):
        return 1.0
    return overlap / max(len(wanted), 1)


def _prioritize_candidate_items(
    candidate_items: List[Dict[str, Any]],
    query: str,
    topic: str,
    report_scope: Dict[str, Any],
    query_years: List[int],
) -> List[Dict[str, Any]]:
    desired_statement_types = set(_desired_statement_types(query, topic))
    desired_consolidation = _desired_consolidation_scope(query, report_scope)
    table_counts: Dict[str, int] = {}
    for item in candidate_items:
        metadata = dict(item.get("metadata") or {})
        table_source_id = str(metadata.get("table_source_id") or "").strip()
        if table_source_id:
            table_counts[table_source_id] = table_counts.get(table_source_id, 0) + 1

    def score(item: Dict[str, Any]) -> tuple[float, int]:
        metadata = dict(item.get("metadata") or {})
        points = 0.0
        statement_type = str(metadata.get("statement_type") or "unknown").strip()
        if desired_statement_types:
            if statement_type in desired_statement_types:
                points += 3.0
            elif statement_type != "unknown":
                points -= 1.0
        consolidation_scope = str(metadata.get("consolidation_scope") or "unknown").strip()
        if desired_consolidation != "unknown":
            if consolidation_scope == desired_consolidation:
                points += 2.0
            elif consolidation_scope != "unknown":
                points -= 2.0
        period_strength = _metadata_period_match_strength(list(metadata.get("period_labels") or []), query_years)
        points += period_strength * 1.5
        table_source_id = str(metadata.get("table_source_id") or "").strip()
        return points, table_counts.get(table_source_id, 0)

    return sorted(candidate_items, key=score, reverse=True)


def _query_mentions_metric(query: str, metric: Dict[str, Any]) -> bool:
    combined = _normalise_spaces(query)
    aliases = [str(metric.get("display_name") or "").strip()]
    aliases.extend(metric.get("aliases", []) or [])
    aliases.extend(metric.get("intent_keywords", []) or [])
    return any(_normalise_spaces(alias) in combined for alias in aliases if str(alias).strip())


_QUOTED_METRIC_RE = re.compile(r"""['"“”‘’「」『』](?P<label>[^'"“”‘’「」『』]+)['"“”‘’「」『』]""")
_GENERIC_NUMERIC_OPERAND_PATTERNS: List[re.Pattern[str]] = [
    re.compile(pattern)
    for pattern in [
        r"법인세비용차감전순(?:이익|손익)",
        r"외화환산(?:이익|손실)",
        r"순이자마진",
        r"\bNIM\b",
        r"무형자산상각비",
        r"세액공제",
        r"\bAMPC\b",
        r"매출원가",
        r"판매비와관리비",
        r"매출액",
        r"유형자산",
        r"무형자산",
        r"단기차입금",
        r"장기차입금",
        r"사채",
        r"(?:차량|금융)\s*부문\s*영업이익",
        r"전체\s*(?:연결\s*)?영업이익",
        r"연결\s*영업이익",
        r"영업손실",
        r"영업이익",
        r"유동자산",
        r"유동부채",
        r"부채총계",
        r"자본총계",
    ]
]


def _clean_metric_label(label: str) -> str:
    text = _normalise_spaces(str(label or ""))
    text = re.sub(r"^[0-9]{4}년\s*", "", text)
    text = re.sub(r"(?:금액|수치|총액|규모|비중|비율|증감액|증감폭|순효과)\s*$", "", text).strip()
    return text


def _extract_quoted_metric_labels(query: str) -> List[str]:
    labels: List[str] = []
    for match in _QUOTED_METRIC_RE.finditer(str(query or "")):
        cleaned = _clean_metric_label(match.group("label"))
        if cleaned:
            labels.append(cleaned)
    return list(dict.fromkeys(labels))


def _extract_generic_operand_labels(query: str) -> List[str]:
    text = str(query or "")
    labels: List[str] = []

    if "유·무형자산" in text or "유/무형자산" in text:
        labels.extend(["유형자산", "무형자산"])

    labels.extend(_extract_quoted_metric_labels(text))

    for pattern in _GENERIC_NUMERIC_OPERAND_PATTERNS:
        for match in pattern.finditer(text):
            cleaned = _clean_metric_label(match.group(0))
            if cleaned:
                labels.append(cleaned)

    normalized = list(dict.fromkeys(label for label in labels if label))
    if "영업이익" in normalized and any("부문 영업이익" in item for item in normalized):
        normalized = [item for item in normalized if item != "영업이익"]
    derived_labels = {"총 영업비용", "영업비용률", "순효과"}
    normalized = [item for item in normalized if item not in derived_labels]
    return normalized


def _is_single_metric_period_comparison(query: str, operand_labels: List[str]) -> bool:
    text = _normalise_spaces(query)
    comparison_markers = ("전년 대비", "전기 대비", "증감액", "증감폭", "%p", "추이")
    if not any(marker in text for marker in comparison_markers):
        return False
    distinct = [label for label in operand_labels if label]
    distinct = list(dict.fromkeys(distinct))
    if len(distinct) <= 1:
        return True
    return False


def _extract_year_tokens(query: str, report_scope: Dict[str, Any]) -> List[int]:
    years: List[int] = []
    for token in re.findall(r"(20\d{2})년", str(query or "")):
        year = int(token)
        if year not in years:
            years.append(year)
    scope_year_raw = report_scope.get("year")
    try:
        if scope_year_raw not in (None, ""):
            scope_year = int(scope_year_raw)
            if scope_year not in years:
                years.insert(0, scope_year)
    except (TypeError, ValueError):
        pass
    return years


def _build_generic_metric_aliases(label: str) -> List[str]:
    base = str(label or "").strip()
    if not base:
        return []
    aliases = [base]
    if "순이익" in base:
        aliases.append(base.replace("순이익", "순손익"))
    if "순손익" in base:
        aliases.append(base.replace("순손익", "순이익"))
    if "손익" in base:
        aliases.append(base.replace("손익", "이익"))
    if "이익" in base and "손익" not in base:
        aliases.append(base.replace("이익", "손익"))
    return list(dict.fromkeys(alias for alias in aliases if alias))


def _infer_statement_and_section_hints(query: str) -> tuple[List[str], List[str]]:
    text = _normalise_spaces(query)
    statement_types = _desired_statement_types(query, query)
    preferred_sections: List[str] = []
    if "손익계산서" in text or "포괄손익계산서" in text:
        preferred_sections.extend(["연결 손익계산서", "손익계산서", "포괄손익계산서"])
    if "재무상태표" in text:
        preferred_sections.extend(["연결 재무상태표", "재무상태표"])
    if "현금흐름표" in text:
        preferred_sections.extend(["현금흐름표", "현금흐름표 (연결)"])
    if "주석" in text:
        preferred_sections.extend(["연결재무제표 주석", "재무제표 주석"])
        if "notes" not in statement_types:
            statement_types.append("notes")
    if any(keyword in text for keyword in ("부문", "segment", "세그먼트")):
        preferred_sections.extend(["부문정보", "영업부문", "영업실적"])
        if "segment_note" not in statement_types:
            statement_types.append("segment_note")
    if any(keyword in text for keyword in ("법인세비용차감전순이익", "법인세비용차감전순손익")):
        preferred_sections.extend(["법인세비용", "연결 손익계산서", "포괄손익계산서"])
        if "notes" not in statement_types:
            statement_types.append("notes")
        if "summary_financials" not in statement_types:
            statement_types.append("summary_financials")
    if any(keyword in text for keyword in ("외화환산이익", "외화환산손실", "환율 변동", "외화환산")):
        preferred_sections.extend(["현금흐름표 (연결)", "현금흐름표", "금융손익 (연결)", "외화환산"])
        if "cash_flow" not in statement_types:
            statement_types.append("cash_flow")
        if "notes" not in statement_types:
            statement_types.append("notes")
    if any(keyword in text for keyword in ("단기차입금", "장기차입금", "유동성장기차입금", "차입금", "사채")):
        preferred_sections.extend(["차입금 및 사채", "단기차입금", "장기차입금", "사채", "연결재무제표 주석"])
        if "notes" not in statement_types:
            statement_types.append("notes")
    return list(dict.fromkeys(statement_types)), list(dict.fromkeys(preferred_sections))


def _build_generic_required_operands(
    query: str,
    report_scope: Dict[str, Any],
) -> List[Dict[str, Any]]:
    operand_labels = _extract_generic_operand_labels(query)
    if _is_single_metric_period_comparison(query, operand_labels):
        base_label = operand_labels[0] if operand_labels else _infer_generic_metric_label(query, "")
        aliases = _build_generic_metric_aliases(base_label)
        year_tokens = _extract_year_tokens(query, report_scope)
        if year_tokens:
            current_year = year_tokens[0]
            prior_year = year_tokens[1] if len(year_tokens) > 1 else current_year - 1
            return [
                {
                    "label": f"{current_year}년 {base_label}",
                    "aliases": aliases,
                    "role": "current_period",
                    "required": True,
                    "period_hint": str(current_year),
                },
                {
                    "label": f"{prior_year}년 {base_label}",
                    "aliases": aliases,
                    "role": "prior_period",
                    "required": True,
                    "period_hint": str(prior_year),
                },
            ]
        return [
            {
                "label": f"당기 {base_label}",
                "aliases": aliases,
                "role": "current_period",
                "required": True,
                "period_hint": "당기",
            },
            {
                "label": f"전기 {base_label}",
                "aliases": aliases,
                "role": "prior_period",
                "required": True,
                "period_hint": "전기",
            },
        ]

    rows: List[Dict[str, Any]] = []
    for label in operand_labels:
        aliases = _build_generic_metric_aliases(label)
        if label == "NIM":
            aliases.append("순이자마진")
        if label == "순이자마진":
            aliases.append("NIM")
        rows.append(
            {
                "label": label,
                "aliases": list(dict.fromkeys(alias for alias in aliases if alias)),
                "role": "",
                "required": True,
            }
        )
    return rows


def _infer_generic_metric_label(query: str, topic: str) -> str:
    quoted = _extract_quoted_metric_labels(query)
    if len(quoted) == 1:
        return quoted[0]
    operand_labels = _extract_generic_operand_labels(query)
    if operand_labels:
        return operand_labels[0]
    return _clean_metric_label(topic) or "수치 계산"


def _build_generic_retrieval_queries(
    query: str,
    metric_label: str,
    operand_specs: List[Dict[str, Any]],
    preferred_sections: List[str],
    report_scope: Dict[str, Any],
) -> List[str]:
    queries = [query]
    year = str(report_scope.get("year") or "").strip()
    year_prefix = f"{year}년 " if year else ""
    if metric_label:
        queries.append(_normalise_spaces(f"{year_prefix}{metric_label}"))
        for section in preferred_sections[:4]:
            queries.append(_normalise_spaces(f"{year_prefix}{metric_label} {section}"))
    for operand in operand_specs:
        label = str(operand.get("label") or "").strip()
        if not label:
            continue
        queries.append(_normalise_spaces(f"{year_prefix}{label}"))
        for alias in list(operand.get("aliases") or [])[:3]:
            if str(alias).strip():
                queries.append(_normalise_spaces(f"{year_prefix}{alias}"))
                for section in preferred_sections[:2]:
                    queries.append(_normalise_spaces(f"{year_prefix}{alias} {section}"))
        for section in preferred_sections[:2]:
            queries.append(_normalise_spaces(f"{year_prefix}{label} {section}"))
    return list(dict.fromkeys(item for item in queries if item))


def _build_heuristic_numeric_task(
    *,
    query: str,
    topic: str,
    intent: str,
    report_scope: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    metric_label = _infer_generic_metric_label(query, topic)
    operand_specs = _build_generic_required_operands(query, report_scope)
    preferred_statement_types, preferred_sections = _infer_statement_and_section_hints(query)
    constraints = {
        "consolidation_scope": _desired_consolidation_scope(query, report_scope),
        "period_focus": _infer_period_focus(query, "unknown"),
        "entity_scope": "company",
        "segment_scope": "segment" if "부문" in _normalise_spaces(query) else "none",
    }
    retrieval_queries = _build_generic_retrieval_queries(
        query=query,
        metric_label=metric_label,
        operand_specs=operand_specs,
        preferred_sections=preferred_sections,
        report_scope=report_scope,
    )
    if not retrieval_queries:
        return None
    return {
        "task_id": "task_1",
        "metric_family": "generic_numeric",
        "metric_label": metric_label,
        "query": query,
        "required_operands": operand_specs,
        "preferred_statement_types": preferred_statement_types,
        "preferred_sections": preferred_sections,
        "retrieval_queries": retrieval_queries,
        "constraints": constraints,
    }


def _infer_period_focus(query: str, default_value: str = "unknown") -> str:
    text = _normalise_spaces(query)
    if any(keyword in text for keyword in ("전기", "전년", "이전 연도", "직전 연도")):
        return "prior"
    if any(keyword in text for keyword in ("당기", "금년", "현재 연도", "이번 연도")):
        return "current"
    explicit_years = list(dict.fromkeys(re.findall(r"20\d{2}", text)))
    if len(explicit_years) == 1:
        return "current"
    return default_value or "unknown"


def _build_task_constraints(
    query: str,
    report_scope: Dict[str, Any],
    ontology: Any,
    metric_key: str,
) -> Dict[str, str]:
    defaults = dict(ontology.default_constraints_for_metric(metric_key) or {})
    defaults["consolidation_scope"] = _desired_consolidation_scope(query, report_scope)
    defaults["period_focus"] = _infer_period_focus(query, str(defaults.get("period_focus") or "unknown"))
    return {
        "consolidation_scope": str(defaults.get("consolidation_scope") or "unknown"),
        "period_focus": str(defaults.get("period_focus") or "unknown"),
        "entity_scope": str(defaults.get("entity_scope") or "unknown"),
        "segment_scope": str(defaults.get("segment_scope") or "none"),
    }


def _build_retrieval_query_bundle(
    query: str,
    topic: str,
    metric_key: str,
    ontology: Any,
) -> List[str]:
    metric = ontology.metric_family(metric_key) or {}
    display_name = str(metric.get("display_name") or "").strip()
    keywords = ontology.retrieval_keywords_for_metric(metric_key)
    preferred_sections = ontology.preferred_sections(display_name or query, topic, "comparison")
    primary_bits = [query, display_name]
    primary_bits.extend(keywords[:4])
    if preferred_sections:
        primary_bits.extend(preferred_sections[:2])
    primary = _normalise_spaces(" ".join(primary_bits))

    bundles = [primary] if primary else []
    for operand in ontology.build_operand_spec(metric_key):
        operand_bits = [query, display_name, str(operand.get("label") or "")]
        operand_bits.extend(list(operand.get("aliases") or [])[:2])
        operand_bits.extend(list(operand.get("preferred_sections") or [])[:1])
        operand_query = _normalise_spaces(" ".join(operand_bits))
        if operand_query:
            bundles.append(operand_query)
    return list(dict.fromkeys(item for item in bundles if item))


def _build_metric_task_query(
    *,
    original_query: str,
    metric_label: str,
    constraints: Dict[str, str],
    operand_specs: List[Dict[str, Any]],
    report_scope: Dict[str, Any],
) -> str:
    query_text = _normalise_spaces(original_query)
    year = report_scope.get("year")
    year_text = f"{year}년 " if str(year or "").strip() else ""
    consolidation_scope = str((constraints or {}).get("consolidation_scope") or "unknown").strip()
    consolidation_text = ""
    if consolidation_scope == "consolidated":
        consolidation_text = "연결기준 "
    elif consolidation_scope == "separate":
        consolidation_text = "별도기준 "

    operand_labels = [str(spec.get("label") or "").strip() for spec in operand_specs if str(spec.get("label") or "").strip()]
    operand_hint = f"({ '/'.join(operand_labels) })" if len(operand_labels) >= 2 else ""
    canonical_query = _normalise_spaces(f"{year_text}{consolidation_text}{metric_label}{operand_hint}을 계산해 줘.")
    if canonical_query:
        return canonical_query
    return query_text or metric_label


def _build_semantic_numeric_plan(
    query: str,
    topic: str,
    intent: str,
    report_scope: Dict[str, Any],
    target_metric_family: str,
) -> Dict[str, Any]:
    """Translate a query into one or more numeric subtasks.

    This is the main pure planning entrypoint. It prefers ontology-backed tasks
    and falls back to heuristic generic-numeric tasks when no clean ontology
    match is available.
    """
    ontology = get_financial_ontology()
    matches = ontology.match_metric_families(query, topic, intent)
    metric_keys: List[str] = []
    planner_notes: List[str] = []
    if target_metric_family:
        target_metric = ontology.metric_family(target_metric_family) or {}
        if target_metric and _query_mentions_metric(query, target_metric):
            metric_keys.append(target_metric_family)
        else:
            planner_notes.append(f"drop_weak_target:{target_metric_family}")
    metric_keys.extend(
        str(item.get("key") or "").strip()
        for item in matches
        if str(item.get("key") or "").strip() and _query_mentions_metric(query, item)
    )
    metric_keys = list(dict.fromkeys(metric_keys))

    tasks: List[Dict[str, Any]] = []
    if not metric_keys:
        heuristic_task = _build_heuristic_numeric_task(
            query=query,
            topic=topic,
            intent=intent,
            report_scope=report_scope,
        )
        if heuristic_task:
            return {
                "status": "heuristic_fallback",
                "fallback_to_general_search": False,
                "tasks": [heuristic_task],
                "planner_notes": planner_notes + ["heuristic_numeric_task"],
            }
        return {
            "status": "fallback_general_search",
            "fallback_to_general_search": True,
            "tasks": [],
            "planner_notes": planner_notes + ["ontology_match_missing"],
        }

    for index, metric_key in enumerate(metric_keys, start=1):
        metric = ontology.metric_family(metric_key) or {}
        if not metric:
            continue
        display_name = str(metric.get("display_name") or metric_key).strip()
        if matches and not _query_mentions_metric(query, metric) and metric_key != target_metric_family:
            # Avoid over-expanding to weak secondary matches unless explicitly targeted.
            planner_notes.append(f"skip_weak_match:{metric_key}")
            continue
        constraints = _build_task_constraints(query, report_scope, ontology, metric_key)
        operand_specs = ontology.build_operand_spec(metric_key)
        retrieval_queries = _build_retrieval_query_bundle(query, topic, metric_key, ontology)
        task_query = _build_metric_task_query(
            original_query=query,
            metric_label=display_name,
            constraints=constraints,
            operand_specs=operand_specs,
            report_scope=report_scope,
        )
        tasks.append(
            {
                "task_id": f"task_{index}",
                "metric_family": metric_key,
                "metric_label": display_name,
                "query": task_query,
                "required_operands": [
                    {
                        "label": str(spec.get("label") or ""),
                        "aliases": list(spec.get("aliases") or []),
                        "role": str(spec.get("role") or ""),
                        "required": bool(spec.get("required", True)),
                    }
                    for spec in operand_specs
                    if str(spec.get("label") or "").strip()
                ],
                "preferred_statement_types": list(ontology.statement_type_hints_for_metric(metric_key)),
                "preferred_sections": list(metric.get("preferred_sections") or []),
                "retrieval_queries": retrieval_queries,
                "constraints": constraints,
            }
        )

    if not tasks:
        return {
            "status": "fallback_general_search",
            "fallback_to_general_search": True,
            "tasks": [],
            "planner_notes": planner_notes or ["no_viable_tasks"],
        }

    return {
        "status": "ok",
        "fallback_to_general_search": False,
        "tasks": tasks,
        "planner_notes": planner_notes,
    }


# ---------------------------------------------------------------------------
# Reconciliation and operand matching helpers
# ---------------------------------------------------------------------------

def _build_reconciliation_candidate(
    *,
    candidate_id: str,
    anchor: str,
    text: str,
    metadata: Dict[str, Any],
    candidate_kind: str = "chunk",
    row_label: str = "",
    row_index: Optional[int] = None,
) -> Dict[str, Any]:
    """Normalize a raw evidence/doc fragment into reconciliation candidate form."""
    candidate_metadata = dict(metadata or {})
    if row_label:
        candidate_metadata["row_label"] = row_label
    if row_index is not None:
        candidate_metadata["row_index"] = row_index
    return {
        "candidate_id": candidate_id,
        "source_anchor": anchor,
        "text": _normalise_spaces(text),
        "metadata": candidate_metadata,
        "candidate_kind": candidate_kind,
    }


def _query_years_from_state(state: Dict[str, Any]) -> List[int]:
    years: List[int] = []
    for value in list(state.get("years") or []):
        try:
            year = int(value)
        except (TypeError, ValueError):
            continue
        if year not in years:
            years.append(year)
    report_scope = dict(state.get("report_scope") or {})
    scope_year_raw = report_scope.get("year")
    try:
        if scope_year_raw not in (None, ""):
            scope_year = int(scope_year_raw)
            if scope_year not in years:
                years.insert(0, scope_year)
    except (TypeError, ValueError):
        pass
    return years


def _structured_cell_period_text(cell: Dict[str, Any], query_years: List[int], period_focus: str) -> str:
    headers = [str(item).strip() for item in (cell.get("column_headers") or []) if str(item).strip()]
    if query_years:
        for year in query_years:
            year_text = str(year)
            if any(year_text in header for header in headers):
                return year_text
    header_text = " ".join(headers)
    if period_focus == "current" and any(token in header_text for token in ("당기", "현재")):
        return "당기"
    if period_focus == "prior" and any(token in header_text for token in ("전기", "이전")):
        return "전기"
    return header_text


def _operand_target_years(operand: Dict[str, Any], query_years: List[int]) -> List[int]:
    hint = str(operand.get("period_hint") or "").strip()
    years: List[int] = []
    for token in re.findall(r"20\d{2}", f"{hint} {operand.get('label') or ''}"):
        year = int(token)
        if year not in years:
            years.append(year)
    if years:
        return years
    return list(query_years or [])


def _operand_period_focus(operand: Dict[str, Any], default_period_focus: str) -> str:
    hint = str(operand.get("period_hint") or "").strip()
    role = str(operand.get("role") or "").strip()
    if hint in {"당기", "현재"} or role == "current_period":
        return "current"
    if hint in {"전기", "이전"} or role == "prior_period":
        return "prior"
    return default_period_focus


def _score_structured_cell(
    cell: Dict[str, Any],
    *,
    query_years: List[int],
    period_focus: str,
) -> float:
    headers = [str(item).strip() for item in (cell.get("column_headers") or []) if str(item).strip()]
    header_text = " ".join(headers)
    score = 0.0
    if query_years:
        for index, year in enumerate(query_years):
            if str(year) in header_text:
                score += 10.0 - index
    if period_focus == "current":
        if any(token in header_text for token in ("당기", "현재")):
            score += 4.0
        if any(token in header_text for token in ("전기", "이전")):
            score -= 1.0
    elif period_focus == "prior":
        if any(token in header_text for token in ("전기", "이전")):
            score += 4.0
        if any(token in header_text for token in ("당기", "현재")):
            score -= 1.0
    if not header_text:
        score -= 0.25
    return score


def _operand_needles(operand: Dict[str, Any]) -> List[str]:
    label = str(operand.get("label") or "").strip()
    aliases = [str(item).strip() for item in (operand.get("aliases") or []) if str(item).strip()]
    return [needle for needle in [label, *aliases] if needle]


def _operand_text_match(text: str, operand: Dict[str, Any]) -> bool:
    haystack = _normalise_spaces(text or "")
    if not haystack:
        return False
    haystack_compact = re.sub(r"\s+", "", haystack)
    for needle in _operand_needles(operand):
        normalized_needle = _normalise_spaces(needle)
        if not normalized_needle:
            continue
        needle_compact = re.sub(r"\s+", "", normalized_needle)
        if (
            haystack == normalized_needle
            or normalized_needle in haystack
            or (needle_compact and needle_compact in haystack_compact)
        ):
            return True
    return False


def _extract_numeric_value_after_operand_text(text: str, operand: Dict[str, Any]) -> str:
    normalized = _normalise_spaces(text or "")
    if not normalized:
        return ""
    value_pattern = re.compile(r"[\d,]+(?:\s*조\s*[\d,]+\s*억(?:원)?)?|[\d,]+")
    for needle in _operand_needles(operand):
        compact = re.sub(r"\s+", "", _normalise_spaces(needle))
        if not compact:
            continue
        spaced_pattern = r"\s*".join(re.escape(char) for char in compact)
        match = re.search(spaced_pattern, normalized)
        if not match:
            continue
        suffix = normalized[match.end() :]
        value_match = value_pattern.search(suffix)
        if value_match:
            return _normalise_spaces(value_match.group(0))
    return ""


def _operand_row_matches_requirement(row: Dict[str, Any], operand: Dict[str, Any]) -> bool:
    surfaces = [
        str(row.get("label") or "").strip(),
        str(row.get("source_anchor") or "").strip(),
    ]
    return any(_operand_text_match(surface, operand) for surface in surfaces if surface)


def _missing_required_operands(
    required_operands: List[Dict[str, Any]],
    operand_rows: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    missing: List[Dict[str, Any]] = []
    for operand in required_operands:
        if any(_operand_row_matches_requirement(row, operand) for row in operand_rows):
            continue
        missing.append(dict(operand))
    return missing


def _merge_operand_rows(
    preferred_rows: List[Dict[str, Any]],
    supplemental_rows: List[Dict[str, Any]],
    *,
    required_operands: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Keep trusted rows first and only fill still-missing operands from fallback."""
    merged: List[Dict[str, Any]] = [dict(row) for row in preferred_rows]
    if not supplemental_rows:
        return merged

    remaining_required = _missing_required_operands(required_operands, merged) if required_operands else []
    seen_keys: set[tuple[str, str, str]] = {
        (
            _normalise_spaces(str(row.get("label") or "")),
            _normalise_spaces(str(row.get("period") or "")),
            _normalise_spaces(str(row.get("source_anchor") or "")),
        )
        for row in merged
    }
    covered_required: set[str] = set()

    for row in supplemental_rows:
        candidate = dict(row)
        row_key = (
            _normalise_spaces(str(candidate.get("label") or "")),
            _normalise_spaces(str(candidate.get("period") or "")),
            _normalise_spaces(str(candidate.get("source_anchor") or "")),
        )
        if row_key in seen_keys:
            continue

        matched_operand: Optional[Dict[str, Any]] = None
        for operand in remaining_required:
            label_key = _normalise_spaces(str(operand.get("label") or ""))
            if label_key in covered_required:
                continue
            if _operand_row_matches_requirement(candidate, operand):
                matched_operand = operand
                covered_required.add(label_key)
                break

        if matched_operand is None and required_operands:
            continue

        seen_keys.add(row_key)
        merged.append(candidate)

    return merged


def _extract_table_row_label(row_text: str) -> str:
    normalized = _normalise_spaces(row_text)
    if not normalized:
        return ""
    if "|" in normalized:
        first_cell = _normalise_spaces(normalized.split("|", 1)[0])
        if first_cell:
            return first_cell
    return normalized


def _parse_unstructured_table_row_cells(row_text: str, metadata: Dict[str, Any]) -> List[Dict[str, Any]]:
    normalized_row = _normalise_spaces(str(row_text or ""))
    if "|" not in normalized_row:
        return []
    row_parts = [part.strip() for part in normalized_row.split("|")]
    row_parts = [part for part in row_parts if part]
    if len(row_parts) <= 1:
        return []

    header_text = _normalise_spaces(str(metadata.get("table_header_context") or ""))
    header_parts = [part.strip() for part in header_text.split("|") if part.strip()] if "|" in header_text else []
    period_labels = [str(item).strip() for item in (metadata.get("period_labels") or []) if str(item).strip()]

    value_parts = row_parts[1:]
    header_candidates = header_parts[-len(value_parts):] if len(header_parts) >= len(value_parts) else []
    if not header_candidates and len(period_labels) >= len(value_parts):
        header_candidates = period_labels[-len(value_parts):]
    if not header_candidates:
        header_candidates = [f"col_{index}" for index in range(1, len(value_parts) + 1)]

    cells: List[Dict[str, Any]] = []
    for header, value in zip(header_candidates, value_parts):
        raw_value = str(value).strip()
        if not raw_value or not re.search(r"[0-9]", raw_value):
            continue
        cells.append(
            {
                "column_headers": [str(header).strip()] if str(header).strip() else [],
                "value_text": raw_value,
                "unit_hint": str(metadata.get("unit_hint") or "").strip(),
            }
        )
    return cells


_GENERIC_COLUMN_HEADERS = {
    "구분",
    "항목",
    "내용",
    "세부항목",
    "비고",
    "차입금명칭",
}


def _build_table_value_reconciliation_candidates(
    *,
    candidate_id_prefix: str,
    anchor: str,
    metadata: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """Build value-cell-first candidates from parser-normalized table values."""
    value_records_json = str(metadata.get("table_value_records_json") or "").strip()
    if not value_records_json:
        return []
    try:
        value_records = json.loads(value_records_json)
    except json.JSONDecodeError:
        return []

    header_context = str(metadata.get("table_header_context") or "").strip()
    summary_text = str(metadata.get("table_summary_text") or "").strip()
    local_heading = str(metadata.get("local_heading") or "").strip()
    section_path = str(metadata.get("section_path") or metadata.get("section") or "").strip()
    candidates: List[Dict[str, Any]] = []
    for idx, record in enumerate(value_records):
        semantic_label = _normalise_spaces(str(record.get("semantic_label") or ""))
        value_text = _normalise_spaces(str(record.get("value_text") or ""))
        if not semantic_label or not value_text or not re.search(r"\d", value_text):
            continue
        period_text = _normalise_spaces(str(record.get("period_text") or ""))
        semantic_aliases = [
            _normalise_spaces(str(item))
            for item in (record.get("semantic_aliases") or [])
            if _normalise_spaces(str(item))
        ]
        row_headers = [
            _normalise_spaces(str(item))
            for item in (record.get("row_headers") or [])
            if _normalise_spaces(str(item))
        ]
        column_headers = [
            _normalise_spaces(str(item))
            for item in (record.get("column_headers") or [])
            if _normalise_spaces(str(item))
        ]
        structured_cell_headers = [period_text] if period_text else list(record.get("period_labels") or []) or column_headers
        composite_text = " ".join(
            part
            for part in (
                semantic_label,
                " ".join(semantic_aliases),
                " ".join(row_headers),
                " ".join(column_headers),
                period_text,
                value_text,
                header_context,
                summary_text,
                local_heading,
                section_path,
                anchor,
            )
            if part
        )
        candidate = _build_reconciliation_candidate(
            candidate_id=f"{candidate_id_prefix}::value:{idx}",
            anchor=anchor,
            text=composite_text,
            metadata=metadata,
            candidate_kind="structured_value",
            row_label=semantic_label,
            row_index=record.get("row_index"),
        )
        candidate["metadata"]["row_headers"] = row_headers
        candidate["metadata"]["column_headers_chain"] = column_headers
        candidate["metadata"]["semantic_label"] = semantic_label
        candidate["metadata"]["semantic_aliases"] = semantic_aliases
        candidate["metadata"]["label_source"] = str(record.get("label_source") or "")
        candidate["metadata"]["aggregate_label"] = _normalise_spaces(str(record.get("aggregate_label") or ""))
        candidate["metadata"]["aggregate_role"] = _normalise_spaces(str(record.get("aggregate_role") or "none"))
        candidate["metadata"]["period_text"] = period_text
        candidate["metadata"]["structured_cells"] = [
            {
                "column_headers": structured_cell_headers,
                "value_text": value_text,
                "unit_hint": str(record.get("unit_hint") or metadata.get("unit_hint") or "").strip(),
            }
        ]
        candidates.append(candidate)
    return candidates


def _column_candidate_label(column_headers: List[str]) -> str:
    cleaned = [_normalise_spaces(header) for header in column_headers if _normalise_spaces(header)]
    if not cleaned:
        return ""
    filtered = [header for header in cleaned if header not in _GENERIC_COLUMN_HEADERS]
    target = filtered[-1] if filtered else cleaned[-1]
    if re.fullmatch(r"20\d{2}(?:년)?", target):
        return ""
    return target


def _build_table_column_reconciliation_candidates(
    *,
    candidate_id_prefix: str,
    anchor: str,
    metadata: Dict[str, Any],
    row_records: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Transpose row records into column-oriented aggregate candidates.

    This is the complement to row-based reconciliation. Some wide DART tables
    store the metric identity in the merged column header chain while each row
    carries period or range context. In that case we synthesize a candidate per
    meaningful column header and attach the row labels as the per-cell period
    headers so the normal direct structured extraction path can still work.
    """
    grouped: Dict[tuple[str, ...], Dict[str, Any]] = {}
    for record in row_records:
        row_label = _normalise_spaces(str(record.get("row_label") or ""))
        row_headers = [row_label] + [
            _normalise_spaces(str(item))
            for item in (record.get("row_headers") or [])
            if _normalise_spaces(str(item)) and _normalise_spaces(str(item)) != row_label
        ]
        for cell in (record.get("cells") or []):
            value_text = _normalise_spaces(str(cell.get("value_text") or ""))
            if not value_text or not re.search(r"\d", value_text):
                continue
            original_headers = [
                _normalise_spaces(str(item))
                for item in (cell.get("column_headers") or [])
                if _normalise_spaces(str(item))
            ]
            label = _column_candidate_label(original_headers)
            if not label:
                continue
            key = tuple(original_headers) or (label,)
            bucket = grouped.setdefault(
                key,
                {
                    "label": label,
                    "column_headers_chain": original_headers,
                    "cells": [],
                },
            )
            transformed_headers = [item for item in row_headers if item]
            if not transformed_headers:
                transformed_headers = [label]
            bucket["cells"].append(
                {
                    "column_headers": transformed_headers,
                    "value_text": value_text,
                    "unit_hint": str(cell.get("unit_hint") or metadata.get("unit_hint") or "").strip(),
                }
            )

    header_context = str(metadata.get("table_header_context") or "").strip()
    summary_text = str(metadata.get("table_summary_text") or "").strip()
    local_heading = str(metadata.get("local_heading") or "").strip()
    section_path = str(metadata.get("section_path") or metadata.get("section") or "").strip()
    candidates: List[Dict[str, Any]] = []
    for idx, bucket in enumerate(grouped.values()):
        cells = [dict(cell) for cell in bucket.get("cells") or [] if dict(cell)]
        if not cells:
            continue
        label = str(bucket.get("label") or "").strip()
        if not label:
            continue
        cell_text = " ".join(
            _normalise_spaces(
                " ".join(
                    part
                    for part in (
                        " / ".join(str(item).strip() for item in (cell.get("column_headers") or []) if str(item).strip()),
                        str(cell.get("value_text") or "").strip(),
                        str(cell.get("unit_hint") or "").strip(),
                    )
                    if part
                )
            )
            for cell in cells
        )
        full_headers = [str(item).strip() for item in (bucket.get("column_headers_chain") or []) if str(item).strip()]
        composite_text = " ".join(
            part
            for part in (
                label,
                " ".join(full_headers),
                cell_text,
                header_context,
                summary_text,
                local_heading,
                section_path,
                anchor,
            )
            if part
        )
        candidate = _build_reconciliation_candidate(
            candidate_id=f"{candidate_id_prefix}::colrec:{idx}",
            anchor=anchor,
            text=composite_text,
            metadata=metadata,
            candidate_kind="structured_column_value",
            row_label=label,
        )
        candidate["metadata"]["row_headers"] = full_headers
        candidate["metadata"]["column_headers_chain"] = full_headers
        candidate["metadata"]["structured_cells"] = cells
        candidates.append(candidate)
    return candidates


def _build_table_row_reconciliation_candidates(
    *,
    candidate_id_prefix: str,
    anchor: str,
    table_text: str,
    metadata: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """Explode table metadata into row-level reconciliation candidates."""
    header_context = str(metadata.get("table_header_context") or "").strip()
    summary_text = str(metadata.get("table_summary_text") or "").strip()
    local_heading = str(metadata.get("local_heading") or "").strip()
    section_path = str(metadata.get("section_path") or metadata.get("section") or "").strip()
    candidates: List[Dict[str, Any]] = []
    value_candidates = _build_table_value_reconciliation_candidates(
        candidate_id_prefix=candidate_id_prefix,
        anchor=anchor,
        metadata=metadata,
    )
    if value_candidates:
        candidates.extend(value_candidates)

    row_records_json = str(metadata.get("table_row_records_json") or "").strip()

    if row_records_json:
        try:
            row_records = json.loads(row_records_json)
        except json.JSONDecodeError:
            row_records = []
        for idx, record in enumerate(row_records):
            row_headers = [str(item).strip() for item in (record.get("row_headers") or []) if str(item).strip()]
            row_label = str(record.get("row_label") or "").strip() or (row_headers[0] if row_headers else "")
            cells = [dict(cell) for cell in (record.get("cells") or []) if dict(cell)]
            if not row_label or not cells:
                continue
            cell_text = " ".join(
                _normalise_spaces(
                    " ".join(
                        part
                        for part in (
                            " / ".join(str(item).strip() for item in (cell.get("column_headers") or []) if str(item).strip()),
                            str(cell.get("value_text") or "").strip(),
                            str(cell.get("unit_hint") or "").strip(),
                        )
                        if part
                    )
                )
                for cell in cells
            )
            composite_text = " ".join(
                part
                for part in (
                    row_label,
                    " ".join(row_headers),
                    cell_text,
                    header_context,
                    summary_text,
                    local_heading,
                    section_path,
                    anchor,
                )
                if part
            )
            candidate = _build_reconciliation_candidate(
                candidate_id=f"{candidate_id_prefix}::rowrec:{idx}",
                anchor=anchor,
                text=composite_text,
                metadata=metadata,
                candidate_kind="structured_row",
                row_label=row_label,
                row_index=idx,
            )
            candidate["metadata"]["row_headers"] = row_headers
            candidate["metadata"]["structured_cells"] = cells
            candidates.append(candidate)
        column_candidates = _build_table_column_reconciliation_candidates(
            candidate_id_prefix=candidate_id_prefix,
            anchor=anchor,
            metadata=metadata,
            row_records=row_records if isinstance(row_records, list) else [],
        )
        for candidate in column_candidates:
            candidates.append(candidate)
        if candidates:
            return candidates

    rows = [_normalise_spaces(row) for row in str(table_text or "").splitlines() if _normalise_spaces(row)]
    if not rows:
        return []

    for idx, row_text in enumerate(rows):
        if "|" not in row_text:
            continue
        row_label = _extract_table_row_label(row_text)
        composite_text = " ".join(
            part
            for part in (
                row_label,
                row_text,
                header_context,
                summary_text,
                local_heading,
                section_path,
                anchor,
            )
            if part
        )
        candidates.append(
            _build_reconciliation_candidate(
                candidate_id=f"{candidate_id_prefix}::row:{idx}",
                anchor=anchor,
                text=composite_text,
                metadata={**metadata, "row_text": row_text},
                candidate_kind="table_row",
                row_label=row_label,
                row_index=idx,
            )
        )
    return candidates


_NON_VALUE_ROW_LABELS = {
    "범위",
    "하위범위",
    "상위범위",
    "범위 합계",
}

_BALANCE_SHEET_AGGREGATE_LABELS = {
    "자산총계",
    "부채총계",
    "자본총계",
    "유동자산",
    "비유동자산",
    "유형자산",
    "무형자산",
    "유동부채",
    "비유동부채",
}


def _candidate_has_numeric_value_signal(candidate: Dict[str, Any]) -> bool:
    metadata = dict(candidate.get("metadata") or {})
    structured_cells = [dict(cell) for cell in (metadata.get("structured_cells") or []) if dict(cell)]
    if structured_cells:
        for cell in structured_cells:
            if re.search(r"\d", str(cell.get("value_text") or "")):
                return True
        return False

    row_text = _normalise_spaces(str(metadata.get("row_text") or ""))
    if row_text and "|" in row_text:
        parts = [part.strip() for part in row_text.split("|")[1:] if part.strip()]
        return any(re.search(r"\d", part) for part in parts)

    return bool(re.search(r"\d", str(candidate.get("text") or "")))


def _candidate_is_descriptor_row(candidate: Dict[str, Any]) -> bool:
    metadata = dict(candidate.get("metadata") or {})
    row_label = _normalise_spaces(str(metadata.get("row_label") or ""))
    if row_label in _NON_VALUE_ROW_LABELS:
        return True

    structured_cells = [dict(cell) for cell in (metadata.get("structured_cells") or []) if dict(cell)]
    if structured_cells and not any(re.search(r"\d", str(cell.get("value_text") or "")) for cell in structured_cells):
        return True

    row_text = _normalise_spaces(str(metadata.get("row_text") or ""))
    if row_text and "|" in row_text:
        parts = [part.strip() for part in row_text.split("|")]
        if parts and _normalise_spaces(parts[0]) in _NON_VALUE_ROW_LABELS:
            numeric_parts = [part for part in parts[1:] if re.search(r"\d", part)]
            if not numeric_parts:
                return True

    return False


def _is_balance_sheet_aggregate_operand(operand: Dict[str, Any]) -> bool:
    needles = {re.sub(r"\s+", "", _normalise_spaces(needle)) for needle in _operand_needles(operand)}
    needles.discard("")
    return any(needle in _BALANCE_SHEET_AGGREGATE_LABELS for needle in needles)


def _candidate_matches_operand(candidate: Dict[str, Any], operand: Dict[str, Any]) -> bool:
    metadata = dict(candidate.get("metadata") or {})
    row_label = str(metadata.get("row_label") or "").strip()
    if _operand_text_match(row_label, operand):
        return True
    row_headers = " ".join(str(item).strip() for item in (metadata.get("row_headers") or []) if str(item).strip())
    if _operand_text_match(row_headers, operand):
        return True
    if _operand_text_match(str(metadata.get("table_row_labels_text") or ""), operand):
        return True
    return _operand_text_match(str(candidate.get("text") or ""), operand)


def _score_operand_candidate(
    candidate: Dict[str, Any],
    *,
    operand: Dict[str, Any],
    preferred_statement_types: List[str],
    constraints: Dict[str, Any],
    query_years: List[int],
) -> float:
    """Rank candidate rows/chunks for a single operand.

    The scorer is deterministic on purpose: it gives the graph a stable first
    pass before any optional LLM reranking is considered.
    """
    metadata = dict(candidate.get("metadata") or {})
    score = 0.0
    row_label = str(metadata.get("row_label") or "").strip()
    semantic_label = _normalise_spaces(str(metadata.get("semantic_label") or row_label))
    if row_label:
        if any(_normalise_spaces(row_label) == _normalise_spaces(needle) for needle in _operand_needles(operand)):
            score += 3.0
        elif _operand_text_match(row_label, operand):
            score += 1.5
    candidate_kind = str(candidate.get("candidate_kind") or "")
    if candidate_kind == "structured_value":
        score += 2.5
    elif candidate_kind == "structured_row":
        score += 2.0
    elif candidate_kind == "structured_column_value":
        score += 1.75
    elif candidate_kind == "table_row":
        score += 1.0
    elif candidate_kind == "evidence_row":
        score += 0.5
    elif candidate_kind == "chunk":
        score -= 0.25

    aggregate_role = _normalise_spaces(str(metadata.get("aggregate_role") or ""))
    if aggregate_role == "final_total":
        score += 1.5
    elif aggregate_role == "direct_total":
        score += 1.25
    elif aggregate_role == "subtotal":
        score += 0.5
    elif aggregate_role == "adjustment":
        score -= 1.5

    aggregate_signal = " ".join(
        part
        for part in (
            semantic_label,
            row_label,
            _normalise_spaces(str(metadata.get("aggregate_label") or "")),
            " ".join(str(item).strip() for item in (metadata.get("column_headers_chain") or []) if str(item).strip()),
        )
        if part
    )
    if aggregate_role in {"direct_total", "final_total"} and _operand_text_match(aggregate_signal, operand):
        score += 2.0
    elif aggregate_role == "subtotal" and _operand_text_match(aggregate_signal, operand):
        score += 0.75

    if _candidate_has_numeric_value_signal(candidate):
        score += 1.0

    if _candidate_is_descriptor_row(candidate):
        score -= 3.0

    statement_type = str(metadata.get("statement_type") or "unknown").strip()
    if preferred_statement_types:
        if statement_type in preferred_statement_types:
            score += 2.5
        elif statement_type != "unknown":
            score -= 0.8

    desired_consolidation = str((constraints or {}).get("consolidation_scope") or "unknown").strip()
    candidate_consolidation = str(metadata.get("consolidation_scope") or "unknown").strip()
    desired_period_focus = _operand_period_focus(operand, str((constraints or {}).get("period_focus") or "unknown").strip())
    candidate_period_focus = str(metadata.get("period_focus") or "unknown").strip()
    local_heading = _normalise_spaces(
        str(metadata.get("local_heading") or metadata.get("table_context") or metadata.get("section_path") or "")
    )
    if desired_consolidation != "unknown":
        if candidate_consolidation == desired_consolidation:
            score += 2.0
        elif candidate_consolidation != "unknown":
            score -= 2.0
        elif desired_consolidation == "consolidated":
            if "연결" in local_heading:
                score += 1.5
            elif "별도" in local_heading:
                score -= 1.5
        elif desired_consolidation == "separate":
            if "별도" in local_heading:
                score += 1.5
            elif "연결" in local_heading:
                score -= 1.5

    if desired_period_focus == "current":
        if candidate_period_focus == "current":
            score += 1.5
        elif candidate_period_focus == "prior":
            score -= 1.5
    elif desired_period_focus == "prior":
        if candidate_period_focus == "prior":
            score += 1.5
        elif candidate_period_focus == "current":
            score -= 1.5

    if _is_balance_sheet_aggregate_operand(operand):
        if statement_type in {"summary_financials", "balance_sheet"}:
            score += 1.5
            if "연결" in local_heading:
                score += 0.75
            elif "별도" in local_heading:
                score -= 0.75
        elif statement_type == "notes":
            score -= 0.5

    score += _metadata_period_match_strength(list(metadata.get("period_labels") or []), query_years) * 1.5

    if str(metadata.get("table_source_id") or "").strip():
        score += 0.25

    return score


def _build_reconciliation_retry_queries(
    *,
    active_subtask: Dict[str, Any],
    missing_operands: List[str],
    years: List[int],
) -> List[str]:
    metric_label = str(active_subtask.get("metric_label") or "").strip()
    constraints = dict(active_subtask.get("constraints") or {})
    preferred_sections = [str(item).strip() for item in (active_subtask.get("preferred_sections") or []) if str(item).strip()]
    required_operands = list(active_subtask.get("required_operands") or [])
    operand_map = {str(item.get("label") or "").strip(): item for item in required_operands if str(item.get("label") or "").strip()}

    prefixes: List[str] = []
    if years:
        prefixes.append(f"{years[0]}년")
    consolidation_scope = str(constraints.get("consolidation_scope") or "unknown").strip()
    if consolidation_scope == "consolidated":
        prefixes.append("연결기준")
    elif consolidation_scope == "separate":
        prefixes.append("별도기준")

    queries: List[str] = []
    for operand_label in missing_operands:
        spec = dict(operand_map.get(operand_label) or {})
        aliases = [str(item).strip() for item in (spec.get("aliases") or []) if str(item).strip()]
        base_bits = prefixes + [operand_label, metric_label]
        if preferred_sections:
            base_bits.append(preferred_sections[0])
        queries.append(_normalise_spaces(" ".join(base_bits)))
        if aliases:
            alias_bits = prefixes + [aliases[0], metric_label]
            if preferred_sections:
                alias_bits.append(preferred_sections[0])
            queries.append(_normalise_spaces(" ".join(alias_bits)))
    return list(dict.fromkeys(item for item in queries if item))


def _deterministic_reconcile_task(
    *,
    active_subtask: Dict[str, Any],
    candidates: List[Dict[str, Any]],
    years: List[int],
    reconciliation_retry_count: int,
) -> Dict[str, Any]:
    """Match required operands to the best available candidates.

    Output from this function is not yet a final operand set. It is a ranked
    and explainable candidate selection that later calculation stages can
    convert into normalized operand rows.
    """
    if not active_subtask:
        return {
            "status": "ready",
            "task_id": "",
            "matched_operands": [],
            "missing_operands": [],
            "retry_queries": [],
            "notes": ["no_active_subtask"],
        }

    preferred_statement_types = [str(item).strip() for item in (active_subtask.get("preferred_statement_types") or []) if str(item).strip()]
    constraints = dict(active_subtask.get("constraints") or {})
    required_operands = [dict(item) for item in (active_subtask.get("required_operands") or []) if bool(item.get("required", True))]

    matched_operands: List[Dict[str, Any]] = []
    missing_operands: List[str] = []
    operand_top_candidates: Dict[str, List[Dict[str, Any]]] = {}

    for operand in required_operands:
        label = str(operand.get("label") or "").strip()
        matches = [candidate for candidate in candidates if _candidate_matches_operand(candidate, operand)]
        ranked = sorted(
            matches,
            key=lambda candidate: _score_operand_candidate(
                candidate,
                operand=operand,
                preferred_statement_types=preferred_statement_types,
                constraints=constraints,
                query_years=years,
            ),
            reverse=True,
        )
        operand_top_candidates[label] = ranked
        if ranked:
            top = ranked[:3]
            matched_operands.append(
                {
                    "label": label,
                    "matched": True,
                    "candidate_ids": [str(item.get("candidate_id") or "") for item in top if str(item.get("candidate_id") or "").strip()],
                    "reason": "matched_candidates",
                }
            )
        else:
            missing_operands.append(label)
            matched_operands.append(
                {
                    "label": label,
                    "matched": False,
                    "candidate_ids": [],
                    "reason": "no_matching_candidate",
                }
            )

    notes: List[str] = []
    common_table_ids: Optional[set[str]] = None
    for label, ranked in operand_top_candidates.items():
        table_ids = {
            str(item.get("metadata", {}).get("table_source_id") or "").strip()
            for item in ranked[:5]
            if str(item.get("metadata", {}).get("table_source_id") or "").strip()
        }
        if not table_ids:
            continue
        common_table_ids = table_ids if common_table_ids is None else (common_table_ids & table_ids)
    if common_table_ids:
        notes.append("same_table_candidate_available")

    if not missing_operands:
        return {
            "status": "ready",
            "task_id": str(active_subtask.get("task_id") or ""),
            "matched_operands": matched_operands,
            "missing_operands": [],
            "retry_queries": [],
            "notes": notes,
        }

    if reconciliation_retry_count < 1:
        retry_queries = _build_reconciliation_retry_queries(
            active_subtask=active_subtask,
            missing_operands=missing_operands,
            years=years,
        )
        return {
            "status": "retry_retrieval",
            "task_id": str(active_subtask.get("task_id") or ""),
            "matched_operands": matched_operands,
            "missing_operands": missing_operands,
            "retry_queries": retry_queries,
            "notes": notes + ["retry_once_for_missing_operands"],
        }

    return {
        "status": "insufficient_operands",
        "task_id": str(active_subtask.get("task_id") or ""),
        "matched_operands": matched_operands,
        "missing_operands": missing_operands,
        "retry_queries": [],
        "notes": notes + ["retry_exhausted"],
    }


def _preferred_calc_sections(query: str, topic: str, intent: str) -> List[str]:
    if intent not in {"comparison", "trend"}:
        return []
    text = _normalise_spaces(f"{query} {topic}")
    preferred: List[str] = []
    ontology_sections = get_financial_ontology().preferred_sections(query, topic, intent)
    preferred.extend(ontology_sections)
    if "연구개발" in text:
        preferred.extend(["연구개발 활동", "요약재무정보"])
    if "영업이익" in text or "당기순이익" in text or "순이익" in text:
        preferred.extend(["요약재무정보", "손익계산서"])
    if "매출" in text or "수익" in text:
        preferred.extend(["매출 및 수주상황", "손익계산서", "요약재무정보"])
    if any(keyword in text for keyword in ("부채비율", "유동비율", "자산총계", "부채총계", "자본총계", "유동자산", "유동부채")):
        preferred.extend(["재무상태표", "요약재무정보", "위험관리 및 파생거래"])
    if _is_ratio_percent_query(text):
        preferred.extend(["요약재무정보", "손익계산서", "재무상태표"])
    return list(dict.fromkeys(preferred))


def _is_percent_point_difference_query(text: str) -> bool:
    normalized = _normalise_spaces(text)
    if "%p" in normalized:
        return True
    ratio_metric = any(keyword in normalized for keyword in ("비율", "비중", "이익률"))
    if not ratio_metric:
        return False
    comparison_markers = (
        "차이",
        "격차",
        "비교",
        "증감",
        "변화",
        "변동",
        "몇 %p",
        "몇%p",
    )
    return any(marker in normalized for marker in comparison_markers)


def _should_coerce_percent_point_unit(
    query: str,
    operands: List[Dict[str, Any]],
    plan_data: Dict[str, Any],
) -> bool:
    if not _is_percent_point_difference_query(query):
        return False
    if str(plan_data.get("mode") or "") != "single_value":
        return False
    ordered_ids = [str(item or "") for item in (plan_data.get("ordered_operand_ids") or []) if str(item or "").strip()]
    if len(ordered_ids) < 2:
        return False
    operand_map = {str(row.get("operand_id") or ""): row for row in operands}
    selected = [operand_map.get(operand_id) for operand_id in ordered_ids]
    if any(row is None for row in selected):
        return False
    if not all(str((row or {}).get("normalized_unit") or "").upper() == "PERCENT" for row in selected):
        return False
    operation = str(plan_data.get("operation") or "").strip().lower()
    formula = _normalise_spaces(str(plan_data.get("formula") or ""))
    return operation == "subtract" or "-" in formula


def _extract_value_near_match(text: str, start: int, end: int) -> tuple[Optional[str], str]:
    tail = text[end : min(len(text), end + 120)]
    if not tail:
        return None, ""
    tail = _normalise_spaces(tail)
    match = re.search(
        r"([\d,]+\s*조\s*[\d,]+\s*억(?:\s*원)?|[\d,]+\s*억(?:\s*원)?|[\d,]+\s*백만원|[\d,.]+%)",
        tail,
    )
    if not match:
        return None, ""
    raw_value = _normalise_spaces(match.group(1))
    if "%" in raw_value:
        return raw_value, "%"
    if "백만원" in raw_value:
        return raw_value.replace("백만원", "").strip(), "백만원"
    if "조" in raw_value or "억" in raw_value:
        return raw_value, "원"
    return raw_value, ""


def _supplement_section_terms_for_query(query: str, topic: str, intent: str) -> List[str]:
    if intent not in {"comparison", "trend"}:
        return []
    sections: List[str] = []
    sections.extend(get_financial_ontology().supplement_sections(query, topic, intent))
    return list(dict.fromkeys(sections))


# ---------------------------------------------------------------------------
# Retrieval-hint helpers
# ---------------------------------------------------------------------------

def _active_preferred_sections(state: Dict[str, Any], query: str, topic: str, intent: str) -> List[str]:
    """Resolve section hints for the active task or top-level query."""
    sections = [
        str(item).strip()
        for item in (dict(state.get("active_subtask") or {}).get("preferred_sections") or [])
        if str(item).strip()
    ]
    sections.extend(_preferred_calc_sections(query, topic, intent))
    return list(dict.fromkeys(sections))


def _active_preferred_statement_types(state: Dict[str, Any], query: str, topic: str) -> List[str]:
    types = [
        str(item).strip()
        for item in (dict(state.get("active_subtask") or {}).get("preferred_statement_types") or [])
        if str(item).strip()
    ]
    types.extend(_desired_statement_types(query, topic))
    return list(dict.fromkeys(types))


def _retrieval_hint_from_topic(query: str, topic: str, intent: str) -> str:
    if intent not in {"comparison", "trend"}:
        return ""
    text = _normalise_spaces(topic)
    hints: List[str] = []
    hints.extend(get_financial_ontology().query_hints(query, topic, intent))
    if "영업이익" in text or "당기순이익" in text or "순이익" in text:
        hints.extend(["손익계산서", "요약재무정보"])
    if "매출" in text or "수익" in text:
        hints.extend(["매출 및 수주상황", "손익계산서"])
    if any(keyword in text for keyword in ("부채비율", "유동비율", "자산총계", "부채총계", "자본총계", "유동자산", "유동부채")):
        hints.extend(["재무상태표", "요약재무정보", "부채총계", "자본총계", "유동자산", "유동부채"])
    if "연구개발" in text:
        hints.append("연구개발")
        # R&D 비중/비율 질문은 분모(총 매출)가 요약재무정보에 있으므로 함께 힌트 추가
        if any(kw in text for kw in ("비중", "비율", "이익률", "차지")):
            hints.append("요약재무정보")
    if "설비투자" in text or "투자" in text:
        hints.extend(["요약재무정보", "재무제표"])
    return " ".join(dict.fromkeys(hints))


