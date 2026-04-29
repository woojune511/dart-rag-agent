"""
LangGraph-based DART financial analysis agent.
"""

import ast
import json
import logging
import math
import os
import re
import time
from typing import Any, Dict, List, Literal, Optional, TypedDict

from dotenv import load_dotenv
from langchain_core.documents import Document
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import END, StateGraph
from pydantic import BaseModel, Field
from src.config import get_financial_ontology
from src.routing import QueryRouter, default_format_preference

load_dotenv()
logger = logging.getLogger(__name__)

DEFAULT_CONTEXT_MAX_WORKERS = max(4, min(12, (os.cpu_count() or 4) * 2))
DEFAULT_CONTEXT_BATCH_SIZE = max(8, DEFAULT_CONTEXT_MAX_WORKERS * 2)


def _extract_usage_counts(response: Any) -> Dict[str, int]:
    usage = getattr(response, "usage_metadata", None) or {}
    response_metadata = getattr(response, "response_metadata", None) or {}
    token_usage = response_metadata.get("token_usage") or {}

    prompt_tokens = (
        usage.get("input_tokens")
        or usage.get("prompt_token_count")
        or token_usage.get("input_tokens")
        or token_usage.get("prompt_token_count")
        or 0
    )
    output_tokens = (
        usage.get("output_tokens")
        or usage.get("candidates_token_count")
        or token_usage.get("output_tokens")
        or token_usage.get("candidates_token_count")
        or 0
    )
    total_tokens = (
        usage.get("total_tokens")
        or usage.get("total_token_count")
        or token_usage.get("total_tokens")
        or token_usage.get("total_token_count")
        or (prompt_tokens + output_tokens)
    )

    return {
        "prompt_tokens": int(prompt_tokens or 0),
        "output_tokens": int(output_tokens or 0),
        "total_tokens": int(total_tokens or 0),
    }


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


class FinancialAgentState(TypedDict):
    query: str
    query_type: str
    intent: str
    target_metric_family: str
    format_preference: str
    routing_source: str
    routing_confidence: float
    routing_scores: Dict[str, float]
    companies: List[str]
    years: List[int]
    topic: str
    section_filter: Optional[str]
    seed_retrieved_docs: List
    retrieved_docs: List
    evidence_bullets: List[str]
    evidence_items: List[Dict[str, Any]]
    evidence_status: str
    selected_claim_ids: List[str]
    draft_points: List[str]
    compressed_answer: str
    kept_claim_ids: List[str]
    dropped_claim_ids: List[str]
    unsupported_sentences: List[str]
    sentence_checks: List[Dict[str, Any]]
    answer: str
    citations: List[str]
    numeric_debug_trace: Dict[str, Any]
    calculation_operands: List[Dict[str, Any]]
    calculation_plan: Dict[str, Any]
    calculation_result: Dict[str, Any]
    calculation_debug_trace: Dict[str, Any]
    planner_debug_trace: Dict[str, Any]


class EntityExtraction(BaseModel):
    companies: List[str] = Field(default_factory=list, description="질문에 등장한 기업명 목록")
    years: List[int] = Field(default_factory=list, description="질문에 등장한 연도 목록")
    topic: str = Field(description="질문의 핵심 분석 주제")
    section_filter: Optional[str] = Field(
        default=None,
        description=(
            "관련 섹션 레이블 하나. 예: 리스크, 재무제표, 연결재무제표, 요약재무, 재무주석, "
            "사업개요, 주요제품, 원재료, 매출현황, 연구개발, 경영진단, 임원현황, 이사회, 주주현황, 계열회사. "
            "단, 두 개 이상의 서로 다른 섹션 데이터가 모두 필요한 질문(비율·비중·이익률 등 분자/분모가 다른 섹션에 있는 경우)은 None을 반환하세요."
        ),
    )


class EvidenceItem(BaseModel):
    source_anchor: str = Field(description="근거 출처 앵커. 예: [삼성전자 | 2023 | 사업의 개요]")
    parent_category: Optional[str] = Field(
        default=None,
        description=(
            "해당 근거가 속한 상위 범주 레이블. "
            "예: '시장위험', 'DS부문'. 문서에 명시된 상위 범주가 없으면 None."
        ),
    )
    claim: str = Field(description="질문에 직접적으로 도움이 되는 근거 진술")
    support_level: Literal["direct", "partial", "context"] = Field(
        description="direct=직접 근거, partial=부분 근거, context=배경 설명"
    )
    quote_span: str = Field(
        default="",
        description="원문에서 발췌한 짧은 근거 구간",
    )
    question_relevance: Literal["high", "medium", "low"] = Field(
        default="medium",
        description="질문과의 직접 관련도",
    )
    allowed_terms: List[str] = Field(
        default_factory=list,
        description="최종 답변에서 사용해도 되는 핵심 용어 목록",
    )


class EvidenceExtraction(BaseModel):
    coverage: Literal["sufficient", "sparse", "conflicting", "missing"]
    evidence: List[EvidenceItem] = Field(default_factory=list)


class CompressionOutput(BaseModel):
    selected_claim_ids: List[str] = Field(
        default_factory=list,
        description="답변 초안에 실제로 사용한 evidence_id 목록",
    )
    draft_points: List[str] = Field(
        default_factory=list,
        description="최종 초안으로 압축하기 전 핵심 포인트 목록",
    )
    draft_answer: str = Field(
        description="structured evidence만으로 압축한 답변 초안",
    )


class NumericExtraction(BaseModel):
    period_check: str = Field(
        description="질문이 요구하는 연도/기수(예: 2024년, 당기, 제56기)를 확인하고, 문서(표)에서 해당 기간의 열을 찾았는지 설명"
    )
    consolidation_check: str = Field(
        description="질문이 요구하는 기준(연결/별도)을 확인하고, 문서의 기준과 일치하는지 판단"
    )
    unit: str = Field(
        description="해당 숫자가 있는 표나 문단에 명시된 금액 단위 (예: 원, 천원, 백만원, 억원, %)"
    )
    raw_value: str = Field(
        description="문서에서 찾은 원본 숫자 텍스트 그대로 (예: '300,870,903'). 단위 변환 금지."
    )
    final_value: str = Field(
        description="질문에 대한 최종 답변 문장. raw_value와 unit을 바탕으로 자연스러운 한국어 한 문장으로 작성."
    )


class CalculationOperand(BaseModel):
    operand_id: str = Field(description="계산용 고유 피연산자 ID. 예: op_001")
    evidence_id: str = Field(description="이 숫자가 추출된 evidence_id")
    source_anchor: str = Field(description="근거 출처 앵커")
    label: str = Field(description="피연산자의 의미 있는 레이블. 예: DX부문 매출, DS부문 매출, 2024년 영업이익")
    raw_value: str = Field(description="문서에서 읽은 원본 숫자 문자열. 예: 174조 8,877억원, 16.2, 228")
    raw_unit: str = Field(description="원본 숫자의 단위. 예: 조원, 억원, 백만원, %, 개")
    normalized_value: Optional[float] = Field(
        default=None,
        description="코드에서 다시 검증 가능한 기본 단위 값. KRW는 원, PERCENT는 퍼센트포인트, COUNT는 절대 개수 기준."
    )
    normalized_unit: Literal["KRW", "PERCENT", "COUNT", "USD", "UNKNOWN"] = Field(
        default="UNKNOWN",
        description="정규화된 단위 계열"
    )
    period: str = Field(default="", description="이 숫자가 대응하는 기간/기수. 예: 2024년, 2023년, 당기, 전기")


class OperandExtraction(BaseModel):
    coverage: Literal["sufficient", "partial", "missing"] = Field(
        description="질문 계산에 필요한 피연산자를 충분히 찾았는지 여부"
    )
    operands: List[CalculationOperand] = Field(default_factory=list)


class FormulaVariableBinding(BaseModel):
    variable: str = Field(description="수식에서 사용할 변수명. 예: A, B, C")
    operand_id: str = Field(description="이 변수에 바인딩할 operand_id")


class CalculationPlan(BaseModel):
    mode: Literal["single_value", "time_series", "none"] = Field(
        description="단일 계산인지, 시계열 계산인지, 계산 불가인지"
    )
    operation: str = Field(
        default="",
        description="평가/로그용 연산 힌트. 예: subtract, growth_rate, time_series_trend"
    )
    ordered_operand_ids: List[str] = Field(
        default_factory=list,
        description="연산 순서가 중요한 경우를 위해 순서를 보존한 피연산자 목록"
    )
    variable_bindings: List[FormulaVariableBinding] = Field(
        default_factory=list,
        description="수식에서 사용할 변수와 operand_id의 매핑"
    )
    formula: str = Field(
        default="",
        description="A, B, C ... 같은 변수만 사용한 안전한 계산식"
    )
    pairwise_formula: str = Field(
        default="",
        description="time_series 모드에서 PREV와 CURR 두 변수로 인접 시점 변화를 계산하는 식"
    )
    result_unit: str = Field(
        default="",
        description="최종 답변에 사용할 단위. 예: 억원, 원, %, 개"
    )
    operation_text: str = Field(
        default="",
        description="연산 순서를 사람이 읽을 수 있게 표현한 짧은 설명. 예: current_year - previous_year"
    )
    explanation: str = Field(
        default="",
        description="이 연산을 선택한 이유를 한 문장으로 설명"
    )


class CalculationResult(BaseModel):
    status: Literal["ok", "insufficient_operands", "zero_division", "unsupported_operation", "unit_mismatch", "parse_error"] = Field(
        description="계산 수행 상태"
    )
    result_value: Optional[float] = Field(default=None, description="정규화 단위 기준 계산 결과")
    result_unit: str = Field(default="", description="최종 답변 단위")
    rendered_value: str = Field(default="", description="사용자 응답에 들어갈 값 표현")
    formatted_result: str = Field(default="", description="프레젠테이션 계층에서 바로 사용할 수 있는 렌더링 결과")
    series: List[Dict[str, Any]] = Field(default_factory=list, description="기간/항목별 계산 입력 시계열 또는 순서 데이터")
    derived_metrics: Dict[str, Any] = Field(default_factory=dict, description="계산 과정에서 파생된 보조 지표")
    explanation: str = Field(default="", description="계산 또는 실패 이유 설명")


class CalculationRenderOutput(BaseModel):
    final_answer: str = Field(description="CalculationResult와 operand labels만 사용해 작성한 최종 답변")


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
    if _is_ratio_percent_query(text):
        preferred.extend(["요약재무정보", "손익계산서"])
    return list(dict.fromkeys(preferred))


def _is_percent_point_difference_query(text: str) -> bool:
    normalized = _normalise_spaces(text)
    return "%p" in normalized or (
        any(keyword in normalized for keyword in ("비율", "비중", "이익률"))
        and any(keyword in normalized for keyword in ("차이", "비교", "대비"))
    )


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
    if "연구개발" in text:
        hints.append("연구개발")
        # R&D 비중/비율 질문은 분모(총 매출)가 요약재무정보에 있으므로 함께 힌트 추가
        if any(kw in text for kw in ("비중", "비율", "이익률", "차지")):
            hints.append("요약재무정보")
    if "설비투자" in text or "투자" in text:
        hints.extend(["요약재무정보", "재무제표"])
    return " ".join(dict.fromkeys(hints))


class ValidationOutput(BaseModel):
    kept_claim_ids: List[str] = Field(
        default_factory=list,
        description="검증 후 최종 답변에 남긴 evidence_id 목록",
    )
    dropped_claim_ids: List[str] = Field(
        default_factory=list,
        description="검증 과정에서 제거한 evidence_id 목록",
    )
    unsupported_sentences: List[str] = Field(
        default_factory=list,
        description="근거 부족 또는 과잉 설명으로 제거한 문장 목록",
    )
    sentence_checks: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="문장별 검증 결과. sentence, verdict, reason, supporting_claim_ids를 포함",
    )
    final_answer: str = Field(
        description="검증을 거친 최종 답변",
    )


class FinancialAgent:
    _SECTION_BIAS_BY_QUERY_TYPE = {
        "numeric_fact": (
            ("손익계산서", 0.08),
            ("매출 및 수주상황", 0.08),
            ("요약재무정보", 0.06),
            ("연결재무제표", 0.06),
        ),
        "comparison": (
            ("매출 및 수주상황", 0.10),
            ("연구개발 활동", 0.10),
            ("연구개발", 0.08),
            ("손익계산서", 0.08),
            ("요약재무정보", 0.10),
            ("연결재무제표", 0.06),
        ),
        "business_overview": (
            ("II. 사업의 내용 > 1. 사업의 개요", 0.14),
            ("II. 사업의 내용 > 2. 주요 제품 및 서비스", 0.10),
            ("사업의 개요", 0.06),
        ),
        "risk": (
            ("위험관리 및 파생거래", 0.18),
            ("리스크", 0.10),
        ),
        "trend": (
            ("손익계산서", 0.12),
            ("요약재무정보", 0.12),
            ("연결재무제표", 0.08),
            ("재무제표", 0.06),
        ),
    }

    def __init__(self, vector_store_manager, k: int = 8, graph_expansion_config: Optional[Dict[str, Any]] = None):
        self.vsm = vector_store_manager
        self.k = k
        self.graph_expansion_config = {
            "enabled": False,
            "include_parent_context": True,
            "include_section_lead": True,
            "include_reference_notes": True,
            "include_described_by_paragraph": True,
            "include_table_context": True,
            "include_sibling_prev": True,
            "include_sibling_next": False,
            "table_sibling_prev_paragraph_only": True,
            "sibling_window": 1,
            "max_docs": k,
        }
        if graph_expansion_config:
            self.graph_expansion_config.update(graph_expansion_config)

        api_key = os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY environment variable is required.")

        self.llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0)
        self.query_router = QueryRouter(embeddings=self.vsm.embeddings, llm=self.llm)
        self.graph = self._build_graph()

    def _default_format_preference(self, intent: str) -> str:
        return default_format_preference(intent)

    def _classify_query(self, state: FinancialAgentState) -> Dict[str, Any]:
        result = self.query_router.route(state["query"])
        return {
            "query_type": result.intent,
            "intent": result.intent,
            "format_preference": result.format_preference,
            "routing_source": result.routing_source,
            "routing_confidence": float(result.routing_confidence or 0.0),
            "routing_scores": dict(result.routing_scores or {}),
        }

    def _extract_entities(self, state: FinancialAgentState) -> Dict[str, Any]:
        structured_llm = self.llm.with_structured_output(EntityExtraction)
        prompt = ChatPromptTemplate.from_template(
            "다음 질문에서 기업명, 연도, 핵심 주제, 관련 섹션을 추출하세요.\n\n질문: {query}"
        )
        result: EntityExtraction = (prompt | structured_llm).invoke({"query": state["query"]})
        ontology = get_financial_ontology()
        metric = ontology.best_metric_family(
            state["query"],
            result.topic,
            state.get("intent") or state.get("query_type", "qa"),
        )
        target_metric_family = str(metric.get("key") or "") if metric else ""
        logger.info(
            "[extract] companies=%s years=%s topic=%s section_filter=%s target_metric=%s",
            result.companies,
            result.years,
            result.topic,
            result.section_filter,
            target_metric_family or "-",
        )
        return {
            "companies": result.companies,
            "years": result.years,
            "topic": result.topic,
            "section_filter": result.section_filter,
            "target_metric_family": target_metric_family,
        }

    def _apply_strict_filter(self, docs, predicate):
        filtered = [item for item in docs if predicate(item[0])]
        return filtered if filtered else docs

    def _supplement_section_seed_docs(self, state: FinancialAgentState) -> List[tuple[Document, float]]:
        query = state["query"]
        topic = state.get("topic") or query
        intent = state.get("intent") or state.get("query_type", "qa")
        section_terms = _supplement_section_terms_for_query(query, topic, intent)
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

        supplemented: List[tuple[Document, float]] = []
        seen_chunk_uids: set[str] = set()
        for body, metadata in zip(self.vsm.bm25_docs, self.vsm.bm25_metadatas):
            metadata = dict(metadata or {})
            section_path = str(metadata.get("section_path") or metadata.get("section") or "")
            if not any(term in section_path for term in section_terms):
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

            text = _normalise_spaces(str(metadata.get("table_context") or "") + "\n" + str(body or ""))
            score = 0.02
            if "연구개발 활동" in section_path or "연구개발활동" in section_path:
                score += 0.03
            if ratio_query and metric_patterns and any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in metric_patterns):
                score += 0.04
            if metric_patterns and any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in ontology.row_patterns(query, topic, intent)):
                score += 0.06

            supplemented.append((Document(page_content=str(body or ""), metadata=metadata), score))

        supplemented.sort(key=lambda item: item[1], reverse=True)
        if supplemented:
            logger.info(
                "[retrieve] supplemental section seeds=%s for terms=%s",
                len(supplemented[:6]),
                section_terms,
            )
        return supplemented[:6]

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
        # 주석 섹션은 numeric_fact/trend에서 본문 재무제표보다 유용도가 낮으므로 페널티
        if "주석" in lowered and query_type in self._TABLE_PREFERRED_TYPES:
            bias -= 0.12
        return bias

    def _rerank_docs(self, docs, state: FinancialAgentState):
        companies = {company.lower() for company in state.get("companies", [])}
        years = {int(year) for year in state.get("years", [])}
        topic_terms = _tokenize_terms(state.get("topic") or state["query"])
        section_filter = (state.get("section_filter") or "").strip()
        intent = state.get("intent") or state.get("query_type", "qa")
        format_preference = state.get("format_preference") or self._default_format_preference(intent)
        metric_terms = _metric_terms_from_topic(state.get("topic") or state["query"])
        preferred_sections = _preferred_calc_sections(state["query"], state.get("topic") or "", intent)

        reranked = []
        for doc, score in docs:
            metadata = doc.metadata or {}
            company = str(metadata.get("company", "")).lower()
            year = metadata.get("year")
            section = str(metadata.get("section", ""))
            section_path = str(metadata.get("section_path", section))
            block_type = metadata.get("block_type", "")
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
                boosted += 0.14

            boosted += self._section_bias(intent, section_path)

            # block_type 보정: format_preference 기반으로 표/단락 선호도 반영
            if format_preference == "paragraph" and block_type == "table":
                boosted -= 0.08
            elif format_preference == "table" and block_type == "paragraph":
                boosted -= 0.04

            reranked.append((doc, boosted))

        reranked.sort(key=lambda item: item[1], reverse=True)
        return reranked

    def _retrieve(self, state: FinancialAgentState) -> Dict[str, Any]:
        query = state["query"]
        companies = state.get("companies", [])
        years = state.get("years", [])
        section_filter = state.get("section_filter")
        intent = state.get("intent") or state.get("query_type", "qa")

        conditions = []
        if companies:
            if len(companies) == 1:
                conditions.append({"company": companies[0]})
            else:
                conditions.append({"company": {"$in": companies}})
        if years:
            int_years = [int(year) for year in years]
            if intent in {"comparison", "trend"} and len(int_years) > 1:
                logger.info(
                    "[retrieve] multi-period %s query detected; skipping strict metadata year filter and keeping years in query text only: %s",
                    intent,
                    int_years,
                )
            elif len(int_years) == 1:
                conditions.append({"year": int_years[0]})
            else:
                conditions.append({"year": {"$in": int_years}})

        if not conditions:
            where_filter = None
        elif len(conditions) == 1:
            where_filter = conditions[0]
        else:
            where_filter = {"$and": conditions}

        retrieval_hint = _retrieval_hint_from_topic(query, state.get("topic") or query, intent)
        preferred_sections = _preferred_calc_sections(query, state.get("topic") or "", intent)
        enriched_query = f"{' '.join(companies)} {query}" if companies else query
        if retrieval_hint:
            enriched_query = f"{enriched_query} {retrieval_hint}".strip()
        if preferred_sections:
            enriched_query = f"{enriched_query} {' '.join(preferred_sections)}".strip()
        docs = self.vsm.search(enriched_query, k=self.k * 4, where_filter=where_filter)
        supplemental_docs = self._supplement_section_seed_docs(state)
        if supplemental_docs:
            merged: List[tuple[Document, float]] = list(docs)
            seen_chunk_uids = {
                str((doc.metadata or {}).get("chunk_uid") or "")
                for doc, _score in merged
            }
            for doc, score in supplemental_docs:
                chunk_uid = str((doc.metadata or {}).get("chunk_uid") or "")
                if chunk_uid and chunk_uid in seen_chunk_uids:
                    continue
                if chunk_uid:
                    seen_chunk_uids.add(chunk_uid)
                merged.append((doc, score))
            docs = merged

        logger.info(
            "[retrieve] companies=%s years=%s topic=%s where=%s -> %s candidates",
            companies,
            years,
            state.get("topic"),
            where_filter,
            len(docs),
        )

        # section_filter는 _rerank_docs에서 +0.20 부스트로만 반영.
        # hard filter로 쓰면 LLM이 wrong section을 추출했을 때 관련 청크가 전부 제외됨.

        if companies:
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

        if years:
            valid_years = {int(year) for year in years}
            docs = self._apply_strict_filter(
                docs,
                lambda doc: int(doc.metadata.get("year", 0)) in valid_years,
            )

        reranked = self._rerank_docs(docs, state)

        # format_preference에 따라 표/단락 비율 보장
        intent = state.get("intent") or state.get("query_type", "qa")
        format_preference = state.get("format_preference") or self._default_format_preference(intent)
        if format_preference == "table":
            # 수치·추이 쿼리: 표 우선, 단락 최소 2개 보장
            tables = [(d, s) for d, s in reranked if d.metadata.get("block_type") == "table"]
            paras = [(d, s) for d, s in reranked if d.metadata.get("block_type") != "table"]
            min_para = min(2, len(paras))
            docs = (tables[: self.k - min_para] + paras[:min_para])
            docs.sort(key=lambda x: x[1], reverse=True)
        elif format_preference == "paragraph":
            # 개요·리스크·일반 쿼리: 단락 최소 절반 보장
            tables = [(d, s) for d, s in reranked if d.metadata.get("block_type") == "table"]
            paras = [(d, s) for d, s in reranked if d.metadata.get("block_type") != "table"]
            min_para = min(self.k // 2, len(paras))
            docs = (paras[:min_para] + tables[: self.k - min_para])
            docs.sort(key=lambda x: x[1], reverse=True)
        else:
            docs = reranked

        seed_docs = reranked[: min(len(reranked), self.k * 4)]
        docs = docs[: self.k]
        logger.info(
            "[retrieve] intent=%s format=%s final %s chunks returned",
            intent,
            format_preference,
            len(docs),
        )
        return {"seed_retrieved_docs": seed_docs, "retrieved_docs": docs}

    def _expand_via_structure_graph(self, state: FinancialAgentState) -> Dict[str, Any]:
        config = dict(self.graph_expansion_config or {})
        if not config.get("enabled"):
            return {}

        seed_docs = list(state.get("retrieved_docs", []) or [])
        if not seed_docs:
            return {}

        include_parent_context = bool(config.get("include_parent_context", True))
        include_section_lead = bool(config.get("include_section_lead", True))
        include_reference_notes = bool(config.get("include_reference_notes", True))
        include_described_by_paragraph = bool(config.get("include_described_by_paragraph", True))
        include_table_context = bool(config.get("include_table_context", True))
        include_sibling_prev = bool(config.get("include_sibling_prev", True))
        include_sibling_next = bool(config.get("include_sibling_next", False))
        table_sibling_prev_paragraph_only = bool(config.get("table_sibling_prev_paragraph_only", True))
        sibling_window = max(0, int(config.get("sibling_window", 1) or 0))
        max_docs = max(self.k, int(config.get("max_docs", self.k) or self.k))

        expanded: List[Any] = []
        seen_keys: set[str] = set()

        def add_doc(doc: Document, score: float, relation: str = "") -> None:
            metadata = dict(doc.metadata or {})
            key = str(metadata.get("chunk_uid") or metadata.get("graph_relation") or relation or doc.page_content[:80])
            relation_key = metadata.get("graph_relation") or relation or "seed"
            dedupe_group = relation_key
            if relation_key in {"seed", "sibling_prev", "sibling_next"}:
                dedupe_group = "chunk"
            dedupe_key = f"{key}::{dedupe_group}"
            if dedupe_key in seen_keys:
                return
            seen_keys.add(dedupe_key)
            expanded.append((doc, score))

        for doc, score in seed_docs:
            metadata = dict(doc.metadata or {})
            parent_id = str(metadata.get("parent_id") or "")
            chunk_uid = str(metadata.get("chunk_uid") or "")
            block_type = str(metadata.get("block_type") or "").strip().lower()
            seed_metadata = dict(metadata)
            if include_parent_context and parent_id:
                seed_metadata["graph_seed_with_parent_context"] = True
            add_doc(Document(page_content=doc.page_content, metadata=seed_metadata), float(score), relation="seed")

            if include_parent_context and parent_id:
                parent_text = self.vsm.get_parent(parent_id)
                if parent_text:
                    parent_metadata = {
                        **metadata,
                        "graph_relation": "parent_context",
                        "graph_source_chunk_uid": chunk_uid,
                        "block_type": "parent_context",
                        "chunk_uid": f"{chunk_uid}::parent_context" if chunk_uid else f"{parent_id}::parent_context",
                    }
                    add_doc(Document(page_content=parent_text, metadata=parent_metadata), float(score) - 0.005, "parent_context")

            if include_section_lead and parent_id:
                section_lead_doc = self.vsm.get_section_lead_doc(parent_id=parent_id, exclude_chunk_uid=chunk_uid)
                if section_lead_doc is not None:
                    add_doc(section_lead_doc, float(score) - 0.006, "section_lead")

            if include_reference_notes and chunk_uid:
                reference_docs = self.vsm.get_reference_docs(chunk_uid=chunk_uid, limit=4)
                for offset, reference_doc in enumerate(reference_docs, start=1):
                    add_doc(reference_doc, float(score) - 0.008 - (offset * 0.001), "reference_note")

            if sibling_window > 0 and parent_id and chunk_uid:
                sibling_docs = self.vsm.get_sibling_docs(parent_id=parent_id, chunk_uid=chunk_uid, window=sibling_window)
                for offset, sibling_doc in enumerate(sibling_docs, start=1):
                    sibling_metadata = dict(sibling_doc.metadata or {})
                    relation = str(sibling_metadata.get("graph_relation") or "sibling").strip()
                    sibling_block_type = str(sibling_metadata.get("block_type") or "").strip().lower()
                    if relation == "sibling_prev" and not include_sibling_prev:
                        continue
                    if relation == "sibling_next" and not include_sibling_next:
                        continue
                    if (
                        block_type == "table"
                        and relation == "sibling_prev"
                        and table_sibling_prev_paragraph_only
                        and sibling_block_type != "paragraph"
                    ):
                        continue
                    add_doc(sibling_doc, float(score) - 0.01 - (offset * 0.001), relation)

            if include_described_by_paragraph and chunk_uid and str(metadata.get("block_type") or "") == "table":
                described_by_doc = self.vsm.get_described_by_doc(chunk_uid=chunk_uid)
                if described_by_doc is not None:
                    add_doc(described_by_doc, float(score) - 0.004, "described_by_paragraph")

            if include_table_context:
                table_context = _normalise_spaces(str(metadata.get("table_context") or ""))
                if table_context:
                    table_metadata = {
                        **metadata,
                        "graph_relation": "table_context",
                        "graph_source_chunk_uid": chunk_uid,
                        "block_type": "table_context",
                        "chunk_uid": f"{chunk_uid}::table_context" if chunk_uid else f"{parent_id}::table_context",
                    }
                    add_doc(Document(page_content=table_context, metadata=table_metadata), float(score) - 0.007, "table_context")

        expanded.sort(key=lambda item: item[1], reverse=True)
        expanded = expanded[:max_docs]
        logger.info(
            "[graph_expand] seed=%s expanded=%s parent=%s section_lead=%s reference_note=%s sibling_prev=%s sibling_next=%s sibling_window=%s table_context=%s max_docs=%s",
            len(seed_docs),
            len(expanded),
            include_parent_context,
            include_section_lead,
            include_reference_notes,
            include_sibling_prev,
            include_sibling_next,
            sibling_window,
            include_table_context,
            max_docs,
        )
        return {"retrieved_docs": expanded}

    def _format_context(self, docs) -> str:
        """검색된 자식 청크를 부모 청크(섹션 전체)로 확장해 LLM 컨텍스트 구성.

        부모 청크가 있으면 부모 텍스트를 사용한다(더 넓은 맥락).
        없으면 자식 청크 텍스트를 그대로 사용한다.
        동일 parent_id가 여러 청크에서 반환될 경우 부모는 한 번만 포함한다.
        """
        parts = []
        seen_parents: set = set()

        for doc, score in docs:
            metadata = doc.metadata or {}
            company      = metadata.get("company", "?")
            year         = metadata.get("year", "?")
            report_type  = metadata.get("report_type", "?")
            section_path = metadata.get("section_path", metadata.get("section", "?"))
            parent_id    = metadata.get("parent_id")
            graph_relation = metadata.get("graph_relation")
            skip_auto_parent = bool(metadata.get("graph_seed_with_parent_context"))

            header = (
                f"[{company} | {year} | {report_type} | {section_path} | score={score:.3f}]"
            )

            if graph_relation:
                parts.append(f"{header}\n{doc.page_content}")
                continue

            # 부모 청크 우선 사용
            if parent_id and not skip_auto_parent and parent_id not in seen_parents:
                parent_text = self.vsm.get_parent(parent_id)
                if parent_text:
                    seen_parents.add(parent_id)
                    parts.append(f"{header}\n{parent_text}")
                    continue

            # 부모가 없거나 이미 포함된 parent_id → 자식 청크 사용
            if parent_id in seen_parents:
                # 이미 이 섹션의 부모를 포함했으므로 중복 제외
                continue

            table_context = metadata.get("table_context")
            body = f"[table_context] {table_context}\n{doc.page_content}" if table_context else doc.page_content
            parts.append(f"{header}\n{body}")

        return "\n\n---\n\n".join(parts)

    def _build_source_anchor(self, metadata: Dict[str, Any]) -> str:
        relation = str(metadata.get("graph_relation") or "").strip()
        relation_suffix = f" | {relation}" if relation else ""
        return (
            f"[{metadata.get('company', '?')} | {metadata.get('year', '?')} | "
            f"{metadata.get('section_path', metadata.get('section', '?'))}{relation_suffix}]"
        )

    def _build_evidence_context(self, docs) -> Dict[str, Any]:
        parts = []
        anchor_lookup: Dict[str, Dict[str, Any]] = {}
        seen_parents: set = set()

        for doc, _score in docs:
            metadata = doc.metadata or {}
            anchor = self._build_source_anchor(metadata)
            anchor_lookup[anchor] = {
                "company": metadata.get("company"),
                "year": metadata.get("year"),
                "report_type": metadata.get("report_type"),
                "section": metadata.get("section"),
                "section_path": metadata.get("section_path", metadata.get("section")),
                "block_type": metadata.get("block_type"),
                "graph_relation": metadata.get("graph_relation"),
                "chunk_uid": metadata.get("chunk_uid"),
                "parent_id": metadata.get("parent_id"),
            }

            parent_id = metadata.get("parent_id")
            graph_relation = metadata.get("graph_relation")
            skip_auto_parent = bool(metadata.get("graph_seed_with_parent_context"))
            if graph_relation:
                parts.append(f"{anchor}\n{doc.page_content}")
                continue

            if parent_id and not skip_auto_parent and parent_id not in seen_parents:
                parent_text = self.vsm.get_parent(parent_id)
                if parent_text:
                    seen_parents.add(parent_id)
                    parts.append(f"{anchor}\n{parent_text}")
                    continue

            if parent_id in seen_parents:
                continue

            table_context = metadata.get("table_context")
            body = f"[table_context] {table_context}\n{doc.page_content}" if table_context else doc.page_content
            parts.append(f"{anchor}\n{body}")

        return {
            "context": "\n\n---\n\n".join(parts),
            "anchor_lookup": anchor_lookup,
            "available_anchors": list(anchor_lookup.keys()),
        }

    def _build_runtime_evidence_item(
        self,
        item: EvidenceItem,
        index: int,
        anchor_lookup: Dict[str, Dict[str, Any]],
    ) -> Dict[str, Any]:
        metadata = dict(anchor_lookup.get(item.source_anchor) or {})
        allowed_terms: List[str] = []
        seen_terms = set()
        for term in item.allowed_terms:
            cleaned = str(term or "").strip()
            if cleaned and cleaned not in seen_terms:
                seen_terms.add(cleaned)
                allowed_terms.append(cleaned)

        result: Dict[str, Any] = {
            "evidence_id": f"ev_{index:03d}",
            "source_anchor": item.source_anchor,
            "claim": item.claim,
            "quote_span": item.quote_span,
            "support_level": item.support_level,
            "question_relevance": item.question_relevance,
            "allowed_terms": allowed_terms,
            "metadata": metadata,
        }
        if item.parent_category:
            result["parent_category"] = item.parent_category.strip()
        return result

    def _sort_evidence_items(self, evidence_items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        relevance_order = {"high": 0, "medium": 1, "low": 2}
        support_order = {"direct": 0, "partial": 1, "context": 2}
        return sorted(
            evidence_items,
            key=lambda item: (
                relevance_order.get(str(item.get("question_relevance", "medium")), 1),
                support_order.get(str(item.get("support_level", "context")), 2),
                str(item.get("evidence_id", "")),
            ),
        )

    def _format_evidence_for_prompt(
        self,
        evidence_items: List[Dict[str, Any]],
        evidence_bullets: List[str],
    ) -> str:
        if evidence_items:
            parts = []
            for item in self._sort_evidence_items(evidence_items):
                allowed_terms = ", ".join(item.get("allowed_terms") or [])
                quote_span = str(item.get("quote_span") or "").strip()
                lines = [
                    f"- evidence_id: {item.get('evidence_id', '?')}",
                    f"  source_anchor: {item.get('source_anchor', '?')}",
                    f"  support_level: {item.get('support_level', '?')}",
                    f"  question_relevance: {item.get('question_relevance', '?')}",
                ]
                if item.get("parent_category"):
                    lines.append(f"  parent_category: {item['parent_category']}")
                lines += [
                    f"  claim: {item.get('claim', '')}",
                ]
                if quote_span:
                    lines.append(f"  quote_span: {quote_span}")
                if item.get("source_context"):
                    lines.append(f"  source_context: {item.get('source_context')}")
                if item.get("raw_row_text"):
                    lines.append(f"  raw_row_text: {item.get('raw_row_text')}")
                if allowed_terms:
                    lines.append(f"  allowed_terms: {allowed_terms}")
                parts.append("\n".join(lines))
            return "\n\n".join(parts)
        return "\n".join(evidence_bullets)

    def _extract_ratio_row_candidates(
        self,
        retrieved_docs: List,
        query: str,
        topic: str,
    ) -> List[Dict[str, Any]]:
        combined_query = _normalise_spaces(f"{query} {topic}")
        if not _is_ratio_percent_query(combined_query):
            return []

        metric_patterns: List[str] = get_financial_ontology().row_patterns(query, topic, "comparison")
        if not metric_patterns:
            metric_patterns.extend([r"비율", r"비중", r"이익률"])

        candidates: List[Dict[str, Any]] = []
        seen_keys: set[tuple[str, str]] = set()
        year_pattern = re.compile(r"(20\d{2}년|제\d+기|당기|전기)")
        percent_pattern = re.compile(r"[\d,.]+%")

        for index, (doc, _score) in enumerate(retrieved_docs[: min(8, len(retrieved_docs))], start=1):
            metadata = dict(doc.metadata or {})
            if str(metadata.get("block_type") or "") != "table":
                continue

            section_path = str(metadata.get("section_path") or metadata.get("section") or "")
            table_context = _normalise_spaces(str(metadata.get("table_context") or ""))
            body = str(doc.page_content or "")
            combined = _normalise_spaces(f"{table_context}\n{body}")
            if not combined:
                continue

            for pattern in metric_patterns:
                match = re.search(pattern, combined, flags=re.IGNORECASE)
                if not match:
                    continue

                window_start = max(0, match.start() - 180)
                window_end = min(len(combined), match.end() + 280)
                snippet = _normalise_spaces(combined[window_start:window_end])
                percents = percent_pattern.findall(snippet)
                if not percents:
                    continue

                years = []
                for token in year_pattern.findall(combined[max(0, match.start() - 240): min(len(combined), match.end() + 80)]):
                    if token not in years:
                        years.append(token)
                if not years and table_context:
                    for token in year_pattern.findall(table_context):
                        if token not in years:
                            years.append(token)
                header_text = " | ".join(years[:4]) if years else (table_context[:120] if table_context else section_path)
                source_context = f"[표: {section_path}] | [헤더: {header_text}]"
                row_text = snippet
                key = (section_path, row_text)
                if key in seen_keys:
                    continue
                seen_keys.add(key)

                candidates.append(
                    {
                        "evidence_id": f"ev_ratio_{index:03d}_{len(candidates) + 1:03d}",
                        "source_anchor": self._build_source_anchor(metadata),
                        "claim": row_text,
                        "quote_span": row_text[:240],
                        "source_context": source_context,
                        "raw_row_text": row_text,
                        "support_level": "direct",
                        "question_relevance": "high",
                        "allowed_terms": years[:4] + percents[:4],
                        "metadata": metadata,
                    }
                )
                break

        return candidates

    def _extract_ratio_component_candidates(
        self,
        retrieved_docs: List,
        query: str,
        topic: str,
    ) -> List[Dict[str, Any]]:
        combined_query = _normalise_spaces(f"{query} {topic}")
        if not _is_ratio_percent_query(combined_query):
            return []
        if _is_percent_point_difference_query(combined_query):
            return []

        specs: List[tuple[str, List[str], List[str]]] = []
        ontology_specs = get_financial_ontology().component_specs(query, topic, "comparison")
        for spec in ontology_specs:
            metric_name = str(spec.get("name") or "")
            preferred_sections = list(spec.get("preferred_sections") or [])
            patterns = [re.escape(keyword) for keyword in (spec.get("keywords") or [])]
            if metric_name and patterns:
                specs.append((metric_name, preferred_sections, patterns))
        if not specs:
            return []

        candidates: List[Dict[str, Any]] = []
        seen_keys: set[tuple[str, str, str]] = set()
        year_pattern = re.compile(r"(20\d{2}년|제\d+기|당기|전기)")

        for metric_name, preferred_sections, patterns in specs:
            best_candidate: Optional[Dict[str, Any]] = None
            best_score = -1
            for index, (doc, _score) in enumerate(retrieved_docs[: min(16, len(retrieved_docs))], start=1):
                metadata = dict(doc.metadata or {})
                section_path = str(metadata.get("section_path") or metadata.get("section") or "")
                if preferred_sections and not any(section_term in section_path for section_term in preferred_sections):
                    continue
                text = _normalise_spaces(f"{metadata.get('table_context') or ''}\n{doc.page_content or ''}")
                if not text:
                    continue
                for pattern in patterns:
                    match = re.search(pattern, text, flags=re.IGNORECASE)
                    if not match:
                        continue
                    window_start = max(0, match.start() - 180)
                    window_end = min(len(text), match.end() + 260)
                    row_text = _normalise_spaces(text[window_start:window_end])
                    if not row_text:
                        continue
                    raw_value, raw_unit = _extract_value_near_match(text, match.start(), match.end())
                    if not raw_value:
                        continue
                    if metric_name != "매출액" and "%" in raw_value:
                        continue
                    source_context = f"[표: {section_path}]"
                    years = []
                    for token in year_pattern.findall(text[max(0, match.start() - 240): min(len(text), match.end() + 120)]):
                        if token not in years:
                            years.append(token)
                    if years:
                        source_context += f" | [헤더: {' | '.join(years[:4])}]"
                    key = (metric_name, section_path, row_text)
                    if key in seen_keys:
                        continue
                    score = 0
                    if any(section_term in section_path for section_term in preferred_sections[:1]):
                        score += 3
                    if "2024년" in row_text:
                        score += 2
                    if metric_name in row_text:
                        score += 2
                    if metric_name == "연구개발비용" and any(alias in row_text for alias in ("총계", "연구개발비용", "연구개발비")):
                        score += 2
                    if metric_name == "매출액" and any(alias in row_text for alias in ("매출액", "당기매출액", "수익")):
                        score += 2
                    candidate = {
                        "evidence_id": f"ev_component_{metric_name}_{index:03d}_{len(candidates) + 1:03d}",
                        "source_anchor": self._build_source_anchor(metadata),
                        "claim": row_text,
                        "quote_span": row_text[:240],
                        "source_context": source_context,
                        "raw_row_text": row_text,
                        "support_level": "direct",
                        "question_relevance": "high",
                        "allowed_terms": [metric_name] + years[:4],
                        "metadata": metadata,
                        "matched_metric": metric_name,
                        "matched_value": raw_value,
                        "matched_unit": raw_unit,
                    }
                    if score > best_score:
                        best_score = score
                        best_candidate = candidate
            if best_candidate:
                key = (str(best_candidate.get("matched_metric") or ""), str(best_candidate.get("source_anchor") or ""), str(best_candidate.get("raw_row_text") or ""))
                if key not in seen_keys:
                    seen_keys.add(key)
                    candidates.append(best_candidate)

        return candidates

    def _build_ratio_operands_from_candidates(
        self,
        candidate_items: List[Dict[str, Any]],
        query: str,
    ) -> List[Dict[str, Any]]:
        if not candidate_items:
            return []

        query_text = _normalise_spaces(query)
        query_years = re.findall(r"(20\d{2}년)", query_text)
        operand_rows: List[Dict[str, Any]] = []
        seen: set[tuple[str, str, str]] = set()
        percent_pattern = re.compile(r"[\d,.]+%")
        year_pattern = re.compile(r"(20\d{2}년)")

        # 1) row-level percent operands with header context
        for item in candidate_items:
            raw_row = _normalise_spaces(str(item.get("raw_row_text") or item.get("claim") or ""))
            if not raw_row:
                continue
            percents = percent_pattern.findall(raw_row)
            if not percents:
                continue
            context_text = _normalise_spaces(f"{item.get('source_context') or ''} {raw_row}")
            context_years = []
            for token in year_pattern.findall(context_text):
                if token not in context_years:
                    context_years.append(token)
            if query_years and len(context_years) >= len(query_years):
                periods = query_years
            else:
                periods = context_years[: len(percents)]
            for idx, raw_value in enumerate(percents):
                period = periods[idx] if idx < len(periods) else ""
                key = (str(item.get("source_anchor") or ""), raw_value, period)
                if key in seen:
                    continue
                seen.add(key)
                normalized_value, normalized_unit = _normalise_operand_value(raw_value, "%")
                operand_rows.append(
                    {
                        "operand_id": f"op_{len(operand_rows) + 1:03d}",
                        "evidence_id": item.get("evidence_id"),
                        "source_anchor": item.get("source_anchor"),
                        "label": f"{period} 비율".strip(),
                        "raw_value": raw_value,
                        "raw_unit": "%",
                        "normalized_value": normalized_value,
                        "normalized_unit": normalized_unit,
                        "period": period,
                    }
                )

        if operand_rows:
            if _is_percent_point_difference_query(query_text):
                if query_years:
                    filtered = [row for row in operand_rows if row.get("period") in query_years]
                    if len(filtered) >= 2:
                        return filtered[:2]
                return operand_rows[:2]
            if query_years:
                filtered = [row for row in operand_rows if row.get("period") in query_years[:1]]
                if filtered:
                    return filtered[:1]
            return operand_rows[:1]

        # 2) component-based operands (e.g. 연구개발비용, 매출액)
        if _is_percent_point_difference_query(query_text):
            return []

        metric_specs = [
            ("연구개발비용", ("연구개발비용", "연구개발비")),
            ("매출액", ("매출액", "당기매출액", "수익")),
        ]
        for label_name, aliases in metric_specs:
            for item in candidate_items:
                raw_row = _normalise_spaces(str(item.get("raw_row_text") or item.get("claim") or ""))
                if not raw_row or not any(alias in raw_row for alias in aliases):
                    continue
                period = ""
                for token in query_years or year_pattern.findall(_normalise_spaces(str(item.get("source_context") or "") + " " + raw_row)):
                    period = token
                    break
                raw_value = _normalise_spaces(str(item.get("matched_value") or ""))
                raw_unit = str(item.get("matched_unit") or "")
                if not raw_value:
                    value_match = re.search(r"[\d,]+(?:\s*조\s*[\d,]+\s*억(?:원)?)?|[\d,]+", raw_row)
                    if not value_match:
                        continue
                    raw_value = value_match.group(0)
                    raw_unit = "원" if "조" in raw_value or "억" in raw_value else ("백만원" if "백만원" in raw_row else "")
                normalized_value, normalized_unit = _normalise_operand_value(raw_value, raw_unit)
                if normalized_value is None:
                    continue
                operand_rows.append(
                    {
                        "operand_id": f"op_{len(operand_rows) + 1:03d}",
                        "evidence_id": item.get("evidence_id"),
                        "source_anchor": item.get("source_anchor"),
                        "label": f"{period} {label_name}".strip(),
                        "raw_value": raw_value,
                        "raw_unit": raw_unit or "원",
                        "normalized_value": normalized_value,
                        "normalized_unit": normalized_unit,
                        "period": period,
                    }
                )
                break

        return operand_rows

    # enumeration 질문은 항목이 많아 기본 cap=6이 부족할 수 있음
    _EVIDENCE_CAP_BY_QUERY_TYPE: Dict[str, int] = {
        "risk": 10,
        "business_overview": 8,
        "comparison": 8,
    }

    def _select_evidence_for_compression(
        self, evidence_items: List[Dict[str, Any]], query_type: str = "qa"
    ) -> List[Dict[str, Any]]:
        if not evidence_items:
            return []
        limit = self._EVIDENCE_CAP_BY_QUERY_TYPE.get(query_type, 6)
        ranked = self._sort_evidence_items(evidence_items)
        high_priority = [item for item in ranked if item.get("question_relevance") == "high"]
        medium_priority = [item for item in ranked if item.get("question_relevance") == "medium"]
        low_priority = [item for item in ranked if item.get("question_relevance") == "low"]

        selected: List[Dict[str, Any]] = []
        for pool in (high_priority, medium_priority, low_priority):
            for item in pool:
                selected.append(item)
                if len(selected) >= limit:
                    return selected
        return selected[:limit]

    def _filter_evidence_by_ids(
        self,
        evidence_items: List[Dict[str, Any]],
        evidence_ids: List[str],
    ) -> List[Dict[str, Any]]:
        if not evidence_items or not evidence_ids:
            return []
        wanted = {str(value).strip() for value in evidence_ids if str(value).strip()}
        return [item for item in evidence_items if str(item.get("evidence_id", "")).strip() in wanted]

    def _evidence_lookup(self, evidence_items: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        return {
            str(item.get("evidence_id", "")).strip(): item
            for item in evidence_items
            if str(item.get("evidence_id", "")).strip()
        }

    def _sentence_support_text(self, claim_ids: List[str], evidence_lookup: Dict[str, Dict[str, Any]]) -> str:
        parts: List[str] = []
        for claim_id in claim_ids:
            item = evidence_lookup.get(str(claim_id).strip())
            if not item:
                continue
            parts.append(str(item.get("claim", "")).strip())
            parts.append(str(item.get("quote_span", "")).strip())
        return " ".join(part for part in parts if part)

    def _is_intro_sentence(self, sentence: str) -> bool:
        lowered = _normalise_spaces(sentence).lower()
        intro_patterns = (
            "다음과 같습니다",
            "다음과 같",
            "주요 재무 리스크는",
            "주요 사업은",
            "영위하는 주요 사업은",
        )
        return any(pattern in lowered for pattern in intro_patterns)

    def _normalise_sentence_checks(
        self,
        *,
        query_type: str,
        compressed_answer: str,
        sentence_checks: List[Dict[str, Any]],
        selected_claim_ids: List[str],
        evidence_items: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        evidence_lookup = self._evidence_lookup(evidence_items)
        normalized: List[Dict[str, Any]] = []

        raw_checks = sentence_checks or []
        if not raw_checks:
            raw_checks = [
                {
                    "sentence": sentence,
                    "verdict": "keep",
                    "reason": "fallback_keep",
                    "supporting_claim_ids": selected_claim_ids,
                }
                for sentence in _split_sentences(compressed_answer)
            ]

        seen_sentences: set[str] = set()
        previous_keep_signature: Optional[tuple] = None
        previous_keep_tokens: set[str] = set()

        for index, entry in enumerate(raw_checks):
            sentence = _normalise_spaces(str(entry.get("sentence", "")))
            if not sentence or sentence in seen_sentences:
                continue
            seen_sentences.add(sentence)
            normalized_sentence = _strip_anchor_text(sentence)

            verdict = str(entry.get("verdict", "keep") or "keep").strip()
            reason = _normalise_spaces(str(entry.get("reason", "")))
            supporting_claim_ids = [
                str(value).strip()
                for value in (entry.get("supporting_claim_ids") or [])
                if str(value).strip()
            ]

            if verdict not in {"keep", "drop_overextended", "drop_unsupported", "drop_redundant"}:
                verdict = "keep"

            if verdict == "keep" and not supporting_claim_ids:
                verdict = "drop_unsupported"
                reason = reason or "근거 claim이 연결되지 않음"

            support_text = self._sentence_support_text(supporting_claim_ids, evidence_lookup)
            support_tokens = _tokenize_terms(support_text)
            sentence_tokens = _tokenize_terms(normalized_sentence)
            overlap_ratio = len(sentence_tokens & support_tokens) / max(len(sentence_tokens), 1)
            aggregate_supported = (
                query_type in {"business_overview", "risk"}
                and bool(supporting_claim_ids)
                and (
                    overlap_ratio >= 0.2
                    or len(supporting_claim_ids) >= 2
                    or (query_type == "risk" and len(sentence_tokens) <= 8 and len(sentence_tokens & support_tokens) >= 1)
                )
            )

            if verdict == "keep" and self._is_intro_sentence(sentence) and index < len(raw_checks) - 1:
                if query_type in {"business_overview", "risk"} and supporting_claim_ids:
                    verdict = "keep"
                    reason = reason or "요약형 질문의 도입 문장으로 유지"
                else:
                    verdict = "drop_redundant"
                    reason = reason or "후속 문장이 동일 질문에 직접 답하므로 도입 문장은 제거"

            if verdict == "keep" and previous_keep_signature and tuple(supporting_claim_ids) == previous_keep_signature:
                overlap = len(sentence_tokens & previous_keep_tokens) / max(len(sentence_tokens | previous_keep_tokens), 1)
                if overlap >= 0.6:
                    verdict = "drop_redundant"
                    reason = reason or "같은 claim을 반복 설명함"

            if verdict in {"drop_overextended", "drop_unsupported"} and aggregate_supported:
                verdict = "keep"
                reason = reason or "여러 evidence의 합집합을 요약한 supported 문장"

            if verdict == "drop_redundant" and query_type in {"business_overview", "risk"} and self._is_intro_sentence(sentence) and supporting_claim_ids:
                verdict = "keep"
                reason = reason or "요약형 질문의 도입 문장으로 유지"

            if verdict == "keep" and query_type in {"business_overview", "risk"} and support_tokens:
                if overlap_ratio < 0.2 and len(sentence_tokens) >= 5 and len(supporting_claim_ids) <= 1:
                    verdict = "drop_overextended"
                    reason = reason or "근거 claim보다 과도하게 일반화되거나 확장됨"

            normalized.append(
                {
                    "sentence": sentence,
                    "verdict": verdict,
                    "reason": reason,
                    "supporting_claim_ids": supporting_claim_ids,
                }
            )

            if verdict == "keep":
                previous_keep_signature = tuple(supporting_claim_ids)
                previous_keep_tokens = sentence_tokens

        kept_sentences = [item["sentence"] for item in normalized if item["verdict"] == "keep"]
        kept_claim_ids = sorted(
            {
                claim_id
                for item in normalized
                if item["verdict"] == "keep"
                for claim_id in item.get("supporting_claim_ids", [])
            }
        )
        dropped_claim_ids = sorted(set(selected_claim_ids) - set(kept_claim_ids))
        unsupported_sentences = [
            item["sentence"] for item in normalized if item["verdict"] != "keep"
        ]
        final_answer = " ".join(kept_sentences).strip()
        if not final_answer:
            final_answer = (
                "관련 공시 문서에서 질문에 직접 답할 수 있는 근거를 찾지 못했습니다. "
                "공시 문서에 정보가 없거나, 현재 검색 결과만으로는 확인하기 어렵습니다."
            )

        return {
            "kept_claim_ids": kept_claim_ids,
            "dropped_claim_ids": dropped_claim_ids,
            "unsupported_sentences": unsupported_sentences,
            "sentence_checks": normalized,
            "answer": final_answer,
        }

    def _compression_guidance(self, query_type: str, query: str, coverage: str) -> Dict[str, str]:
        instructions = {
            "numeric_fact": (
                "질문이 요청한 숫자·금액·비율만 답하세요. claim과 quote_span에 있는 표기를 그대로 유지하고, "
                "동일 값을 다른 단위나 다른 숫자 표기로 바꾸지 마세요."
            ),
            "business_overview": (
                "질문에 직접 필요한 사업 구조를 정리하되, 각 부문을 설명할 때 "
                "근거에 등장하는 구체적인 예시(제품명, 주요 역할 등)를 생략하지 말고 포함하세요. "
                "같은 사실을 반복하거나 evidence에 없는 배경 설명은 빼세요. "
                "evidence에 parent_category가 명시된 항목들은 해당 상위 부문을 먼저 적고 "
                "그 아래에 하위 항목을 묶어서 구조화하세요."
            ),
            "risk": (
                "근거에 있는 리스크 항목만 추출하세요. 각 항목을 나열할 때 이름만 적지 말고, "
                "근거에 있는 구체적인 정의나 영향을 한 줄씩 함께 요약하세요. "
                "evidence에 parent_category가 명시된 항목들은 해당 상위 범주(예: 시장위험)를 먼저 적고 "
                "그 아래에 하위 항목을 묶어서 구조화하세요. "
                "evidence에 없는 새로운 상위 범주를 만들지 마세요."
            ),
            "comparison": "각 항목을 나란히 비교하되, evidence에 직접 있는 차이만 정리하세요.",
            "trend": "시계열 변화와 근거에 직접 있는 원인만 짧게 정리하세요.",
            "qa": "질문에 직접 답하는 핵심 사실만 짧게 답하세요.",
        }
        output_styles = {
            "numeric_fact": "최대 1문장.",
            "business_overview": "각 부문의 구체적 제품/역할이 포함된 3~5개의 bullet.",
            "risk": "항목별로 이름과 짧은 설명(1~2줄)이 함께 있는 bullet. 항목 수는 evidence 범위를 넘기지 말 것.",
            "comparison": "짧은 bullet 비교.",
            "trend": "2~4문장.",
            "qa": "짧고 직접적으로.",
        }

        coverage_note = ""
        if coverage == "sparse":
            coverage_note = "근거가 제한적입니다. evidence에 직접 적힌 claim과 quote_span만 사용하세요."
        elif coverage == "conflicting":
            coverage_note = "근거가 서로 상충하면 충돌을 명시하세요."

        return {
            "instruction": instructions.get(query_type, instructions["qa"]),
            "output_style": output_styles.get(query_type, output_styles["qa"]),
            "coverage_note": coverage_note,
        }

    def _extract_evidence(self, state: FinancialAgentState) -> Dict[str, Any]:
        docs = state.get("retrieved_docs", [])
        if not docs:
            return {"evidence_bullets": [], "evidence_items": [], "evidence_status": "missing"}

        structured_llm = self.llm.with_structured_output(EvidenceExtraction)
        query_type = state.get("query_type", "qa")
        evidence_context = self._build_evidence_context(docs[: min(8, len(docs))])
        anchor_lookup = evidence_context["anchor_lookup"]
        if query_type == "risk":
            extra_rules = (
                "\n- 리스크 유형명은 컨텍스트에 명시된 단어만 사용하세요. "
                "컨텍스트에 없는 리스크 카테고리(예: '운영위험', '규제위험' 등)를 새로 만들지 마세요."
                "\n- [중요] 컨텍스트에 여러 개의 독립적인 리스크 항목이 나열되어 있다면, "
                "임의로 그룹화하거나 생략하지 마세요. "
                "문서에 존재하는 각 항목을 하나씩 독립적인 EvidenceItem으로 빠짐없이 추출하세요."
                "\n- 문서에서 여러 하위 항목이 상위 범주 아래 묶여 있다면(예: '시장위험' 아래 환율변동위험·이자율변동위험·주가변동위험), "
                "각 하위 항목의 parent_category 필드에 해당 상위 범주 명칭을 그대로 적으세요. "
                "상위 범주가 문서에 명시되어 있지 않으면 None으로 두세요."
            )
        elif query_type == "business_overview":
            extra_rules = (
                "\n- [중요] 컨텍스트에 여러 개의 독립적인 사업 부문이나 항목이 나열되어 있다면, "
                "임의로 그룹화하거나 생략하지 마세요. "
                "문서에 존재하는 각 항목을 하나씩 독립적인 EvidenceItem으로 빠짐없이 추출하세요."
                "\n- 문서에서 여러 하위 항목이 상위 부문 아래 묶여 있다면(예: 'DS부문' 아래 메모리·시스템반도체·파운드리), "
                "각 하위 항목의 parent_category 필드에 해당 상위 부문 명칭을 그대로 적으세요. "
                "상위 범주가 문서에 명시되어 있지 않으면 None으로 두세요."
            )
        else:
            extra_rules = ""
        prompt = ChatPromptTemplate.from_template(
            """당신은 기업 공시 분석 보조자입니다.
질문에 답하기 전에, 아래 검색 결과에서 질문과 직접적으로 관련된 근거만 뽑아주세요.

규칙:
- 제공된 컨텍스트 밖의 정보를 추가하지 마세요.
- 각 근거는 반드시 아래 제공된 source_anchor 중 하나를 정확히 사용하세요.
- 숫자, 기간, 조건이 보이면 그대로 유지하세요.
- quote_span에는 실제 근거 원문 일부를 짧게 그대로 옮기세요.
- allowed_terms에는 답변에 사용 가능한 핵심 용어만 넣으세요.
- 근거가 부족하면 coverage를 sparse로, 서로 충돌하면 conflicting으로 설정하세요.
- 아예 답할 근거가 없으면 coverage를 missing으로 두고 evidence는 비우세요.{extra_rules}

질문: {query}
핵심 주제: {topic}

사용 가능한 source_anchor:
{available_anchors}

컨텍스트:
{context}
"""
        )

        def _deterministic_fallback(doc_list) -> tuple[List[str], List[Dict[str, Any]]]:
            bullets = []
            items = []
            for doc, _score in doc_list[: min(6, len(doc_list))]:
                metadata = doc.metadata or {}
                anchor = self._build_source_anchor(metadata)
                snippet = re.sub(r"\s+", " ", doc.page_content).strip()[:220]
                bullets.append(f"- {anchor} {snippet}")
                items.append(
                    {
                        "evidence_id": f"ev_{len(items) + 1:03d}",
                        "source_anchor": anchor,
                        "claim": snippet,
                        "quote_span": snippet,
                        "support_level": "context",
                        "question_relevance": "medium",
                        "allowed_terms": sorted(_tokenize_terms(snippet))[:8],
                        "metadata": dict(anchor_lookup.get(anchor) or {}),
                    }
                )
            return bullets, items

        try:
            result: EvidenceExtraction = (prompt | structured_llm).invoke(
                {
                    "query": state["query"],
                    "topic": state.get("topic") or state["query"],
                    "available_anchors": "\n".join(evidence_context["available_anchors"]),
                    "context": evidence_context["context"],
                    "extra_rules": extra_rules,
                }
            )
            evidence_items = [
                self._build_runtime_evidence_item(item, index, anchor_lookup)
                for index, item in enumerate(result.evidence, start=1)
            ]
            evidence_bullets = [
                f"- {item.source_anchor} {item.claim} ({item.support_level})"
                for item in result.evidence
            ]
            logger.info("[evidence] coverage=%s bullets=%s", result.coverage, len(evidence_bullets))

            # structured output이 missing을 반환했지만 docs는 있는 경우:
            # hard abstain 대신 deterministic fallback으로 sparse 답변 시도
            if not evidence_bullets and result.coverage == "missing":
                logger.info("[evidence] structured output returned missing with docs present — using deterministic fallback")
                fallback, fallback_items = _deterministic_fallback(docs)
                return {
                    "evidence_bullets": fallback,
                    "evidence_items": fallback_items,
                    "evidence_status": "sparse" if fallback else "missing",
                }

            return {
                "evidence_bullets": evidence_bullets,
                "evidence_items": evidence_items,
                "evidence_status": result.coverage,
            }
        except Exception as exc:
            logger.warning("Evidence extraction failed, using deterministic fallback: %s", exc)
            fallback, fallback_items = _deterministic_fallback(docs)
            return {
                "evidence_bullets": fallback,
                "evidence_items": fallback_items,
                "evidence_status": "sparse" if fallback else "missing",
            }

    def _compress_answer(self, state: FinancialAgentState) -> Dict[str, Any]:
        evidence_items = state.get("evidence_items", [])
        evidence_bullets = state.get("evidence_bullets", [])
        if not evidence_items and not evidence_bullets:
            return {
                "selected_claim_ids": [],
                "draft_points": [],
                "compressed_answer": (
                    "관련 공시 문서에서 질문에 직접 답할 수 있는 근거를 찾지 못했습니다. "
                    "공시 문서에 정보가 없거나, 현재 검색 결과만으로는 확인하기 어렵습니다."
                ),
            }

        coverage = state.get("evidence_status", "sparse")
        query = state["query"]
        query_type = state.get("query_type", "qa")
        selected_evidence = self._select_evidence_for_compression(evidence_items, query_type)
        evidence_text = self._format_evidence_for_prompt(selected_evidence, evidence_bullets)
        guidance = self._compression_guidance(query_type, query, coverage)

        structured_llm = self.llm.with_structured_output(CompressionOutput)
        prompt = ChatPromptTemplate.from_template(
            """당신은 한국 기업 공시(DART) 분석 전문가입니다.
아래 structured evidence를 질문 범위에 맞게 압축해 typed output을 만드세요.

Compression 규칙:
- evidence에 없는 내용은 추가하지 마세요.
- 먼저 question_relevance가 high인 evidence만으로 답 구성을 시도하세요.
- claim을 기본 단위로 사용하고, 필요할 때만 quote_span의 원문 표현을 그대로 가져오세요.
- allowed_terms에 없는 새로운 분류명이나 핵심 용어는 만들지 마세요.
- 질문이 요구하지 않은 배경 설명, 예시, 장황한 연결 문장은 넣지 마세요.
- 가능한 한 중복 claim을 합치고, 같은 사실은 한 번만 말하세요.
- draft_answer와 draft_points 안에 `[회사 | 연도 | ...]` 형태의 source_anchor 원문을 절대 그대로 쓰지 마세요. 출처 추적은 selected_claim_ids로만 수행합니다.
{coverage_note}

질문 유형 지침:
{instruction}

출력 형식 지침:
{output_style}

Structured Evidence:
{evidence}

질문: {query}

반드시 다음 필드를 채우세요.
- selected_claim_ids: 실제로 사용한 evidence_id만
- draft_points: 중복을 제거한 핵심 포인트 목록
- draft_answer: 사용자에게 보여줄 짧은 초안 답변
"""
        )

        try:
            chain = prompt | structured_llm
            compressed: CompressionOutput = chain.invoke(
                {
                    "instruction": guidance["instruction"],
                    "coverage_note": guidance["coverage_note"],
                    "output_style": guidance["output_style"],
                    "evidence": evidence_text,
                    "query": state["query"],
                }
            )
            logger.info("[compress] typed compression generated")
            return {
                "selected_claim_ids": compressed.selected_claim_ids,
                "draft_points": compressed.draft_points,
                "compressed_answer": compressed.draft_answer,
            }
        except Exception as exc:
            logger.warning("Compression structured output failed, using fallback text output: %s", exc)
            chain = prompt | self.llm | StrOutputParser()
            compressed_answer = chain.invoke(
                {
                    "instruction": guidance["instruction"],
                    "coverage_note": guidance["coverage_note"],
                    "output_style": guidance["output_style"],
                    "evidence": evidence_text,
                    "query": state["query"],
                }
            )
            return {
                "selected_claim_ids": [item.get("evidence_id", "") for item in selected_evidence if item.get("evidence_id")],
                "draft_points": [item.get("claim", "") for item in selected_evidence if item.get("claim")][:4],
                "compressed_answer": compressed_answer,
            }

    def _validate_answer(self, state: FinancialAgentState) -> Dict[str, Any]:
        compressed_answer = state.get("compressed_answer", "")
        if not compressed_answer:
            return {
                "kept_claim_ids": [],
                "dropped_claim_ids": [],
                "unsupported_sentences": [],
                "sentence_checks": [],
                "answer": compressed_answer,
            }

        query_type = state.get("query_type", "qa")
        evidence_items = state.get("evidence_items", [])
        evidence_bullets = state.get("evidence_bullets", [])
        selected_claim_ids = state.get("selected_claim_ids", [])
        selected_evidence = self._filter_evidence_by_ids(evidence_items, selected_claim_ids)
        if not selected_evidence:
            selected_evidence = self._select_evidence_for_compression(evidence_items, query_type)
        evidence_text = self._format_evidence_for_prompt(selected_evidence, evidence_bullets)

        structured_llm = self.llm.with_structured_output(ValidationOutput)
        validator_prompt = ChatPromptTemplate.from_template(
            """다음 답변 초안을 structured evidence와 대조해 문장 단위로 검증하고 typed output을 만드세요.

Validator 규칙:
- 새 정보는 절대 추가하지 마세요.
- 근거로 뒷받침되지 않는 문장, 구, 세부사항만 삭제하거나 더 짧게 축소하세요.
- 질문에 직접 필요하지 않은 배경 설명은 삭제하세요.
- 숫자, 단위, 비율은 evidence의 quote_span 또는 claim 표기를 그대로 유지하세요.
- risk: evidence에 없는 상위 taxonomy나 재분류를 만들지 마세요.
- business_overview / risk: 여러 evidence에 흩어진 정보를 하나의 문장이나 bullet로 종합한 경우, 각 표현이 evidence 합집합으로 뒷받침되면 supported로 판단하세요.
- business_overview / risk: 특정 문장이 단일 evidence와 1:1로 대응하지 않아도, supporting_claim_ids의 합집합이 그 문장을 직접 지지하면 keep 할 수 있습니다.
- duplicated claim은 하나만 남기세요.
- 가능한 한 기존 source_anchor는 유지하세요.
- 초안을 문장 단위로 나눈 뒤 각 문장을 아래 verdict 중 하나로 판정하세요.
  - keep
  - drop_overextended
  - drop_unsupported
  - drop_redundant
- supporting_claim_ids에는 그 문장을 직접 지지하는 evidence_id만 넣으세요.
- keep가 아닌 문장은 unsupported_sentences에도 넣으세요.
- kept_claim_ids / dropped_claim_ids는 sentence_checks와 일관되게 작성하세요.
- final_answer는 keep verdict를 받은 문장만 자연스럽게 이어 붙인 결과여야 합니다.
- keep 문장이 하나도 없으면, 질문에 직접 답할 수 있는 근거를 찾지 못했다는 짧은 문장만 남기세요.

질문 유형: {query_type}
질문: {query}

Structured Evidence:
{evidence}

초안 답변:
{answer}

반드시 다음 필드를 채우세요.
- kept_claim_ids: 최종 답변에 실제로 남긴 evidence_id
- dropped_claim_ids: 제거한 evidence_id
- unsupported_sentences: 삭제하거나 축소한 문장/구
- sentence_checks: 각 문장에 대한 verdict, reason, supporting_claim_ids
- final_answer: 최종 사용자 답변
"""
        )
        try:
            validated: ValidationOutput = (validator_prompt | structured_llm).invoke(
                {
                    "query_type": query_type,
                    "query": state["query"],
                    "evidence": evidence_text,
                    "answer": compressed_answer,
                }
            )
            logger.info("[validate] typed validation generated")
            return self._normalise_sentence_checks(
                query_type=query_type,
                compressed_answer=validated.final_answer or compressed_answer,
                sentence_checks=validated.sentence_checks,
                selected_claim_ids=[item.get("evidence_id", "") for item in selected_evidence if item.get("evidence_id")],
                evidence_items=selected_evidence,
            )
        except Exception as exc:
            logger.warning("Validation structured output failed, using fallback text output: %s", exc)
            validated_answer = (validator_prompt | self.llm | StrOutputParser()).invoke(
                {
                    "query_type": query_type,
                    "query": state["query"],
                    "evidence": evidence_text,
                    "answer": compressed_answer,
                }
            )
            selected_ids = [item.get("evidence_id", "") for item in selected_evidence if item.get("evidence_id")]
            return self._normalise_sentence_checks(
                query_type=query_type,
                compressed_answer=validated_answer,
                sentence_checks=[
                    {
                        "sentence": validated_answer,
                        "verdict": "keep",
                        "reason": "fallback",
                        "supporting_claim_ids": selected_ids,
                    }
                ]
                if validated_answer
                else [],
                selected_claim_ids=selected_ids,
                evidence_items=selected_evidence,
            )

    def _extract_numeric_fact(self, state: FinancialAgentState) -> Dict[str, Any]:
        docs = state.get("retrieved_docs", [])
        empty_result: Dict[str, Any] = {
            "answer": "관련 공시 문서에서 요청한 수치를 찾지 못했습니다.",
            "compressed_answer": "",
            "selected_claim_ids": [],
            "draft_points": [],
            "kept_claim_ids": [],
            "dropped_claim_ids": [],
            "unsupported_sentences": [],
            "sentence_checks": [],
            "evidence_items": [],
            "evidence_bullets": [],
            "evidence_status": "missing",
            "numeric_debug_trace": {},
        }
        if not docs:
            return empty_result

        context = self._format_context(docs[: min(8, len(docs))])
        structured_llm = self.llm.with_structured_output(NumericExtraction)
        prompt = ChatPromptTemplate.from_template(
            """당신은 재무 데이터 전문 분석가입니다.
아래 질문에 답하기 위해 공시 문서 컨텍스트에서 정확한 수치를 추출하세요.

지시사항:
1. 표(Table)에서 행과 열의 교차점을 정확히 확인하세요.
2. 당기/전기, 연결/별도, 금액 단위를 최우선으로 확인하세요.
3. raw_value는 문서에서 찾은 숫자를 변환 없이 그대로 적으세요.
4. final_value는 raw_value와 unit을 바탕으로 질문에 직접 답하는 자연스러운 한국어 한 문장으로 작성하세요.
5. 수치를 찾지 못한 경우 raw_value와 final_value를 빈 문자열로 두세요.

질문: {query}

컨텍스트:
{context}
"""
        )

        try:
            result: NumericExtraction = (prompt | structured_llm).invoke(
                {"query": state["query"], "context": context}
            )
            debug_trace = result.model_dump()
            logger.info(
                "[numeric_extractor] period=%s consolidation=%s unit=%s raw=%s",
                (result.period_check or "")[:60],
                (result.consolidation_check or "")[:60],
                result.unit,
                result.raw_value,
            )
            answer = result.final_value if result.final_value else empty_result["answer"]
        except Exception as exc:
            logger.warning("[numeric_extractor] structured output failed: %s", exc)
            debug_trace = {"error": str(exc)}
            answer = empty_result["answer"]

        # grounding judge가 검증할 수 있도록 numeric_extractor 결과를 evidence_item으로 변환
        evidence_items: List[Dict[str, Any]] = []
        evidence_bullets: List[str] = []
        evidence_status = "missing"
        if debug_trace and debug_trace.get("raw_value"):
            anchor = self._build_source_anchor(
                (docs[0][0].metadata if docs else {})
            )
            claim = f"{debug_trace.get('raw_value', '')} ({debug_trace.get('unit', '')})"
            quote_span = debug_trace.get("raw_value", "")
            evidence_items = [
                {
                    "evidence_id": "ev_001",
                    "source_anchor": anchor,
                    "claim": claim,
                    "quote_span": quote_span,
                    "support_level": "direct",
                    "question_relevance": "high",
                    "allowed_terms": [debug_trace.get("raw_value", ""), debug_trace.get("unit", "")],
                    "metadata": docs[0][0].metadata if docs else {},
                }
            ]
            evidence_bullets = [f"- {anchor} {claim} (direct)"]
            evidence_status = "sufficient"

        return {
            "answer": answer,
            "compressed_answer": answer,
            "selected_claim_ids": ["ev_001"] if evidence_items else [],
            "draft_points": [answer] if answer else [],
            "kept_claim_ids": ["ev_001"] if evidence_items else [],
            "dropped_claim_ids": [],
            "unsupported_sentences": [],
            "sentence_checks": [],
            "evidence_items": evidence_items,
            "evidence_bullets": evidence_bullets,
            "evidence_status": evidence_status,
            "numeric_debug_trace": debug_trace,
        }

    def _extract_calculation_operands(self, state: FinancialAgentState) -> Dict[str, Any]:
        evidence_items = list(state.get("evidence_items", []) or [])
        evidence_bullets = list(state.get("evidence_bullets", []) or [])
        retrieved_docs = state.get("retrieved_docs", []) or []
        seed_retrieved_docs = state.get("seed_retrieved_docs", []) or []
        evidence_status = str(state.get("evidence_status") or "")
        intent = state.get("intent") or state.get("query_type", "qa")
        query = state["query"]
        topic = state.get("topic") or query
        empty_result: Dict[str, Any] = {
            "calculation_operands": [],
            "calculation_debug_trace": {"coverage": "missing"},
            "answer": "",
        }
        should_augment_with_docs = (
            bool(retrieved_docs or seed_retrieved_docs)
            and intent in {"comparison", "trend"}
            and (not evidence_items or evidence_status != "sufficient")
        )
        if should_augment_with_docs:
            candidate_docs = seed_retrieved_docs or retrieved_docs
            synthesized_items: List[Dict[str, Any]] = []
            synthesized_bullets: List[str] = []
            seen_anchors = {str(item.get("source_anchor") or "") for item in evidence_items}
            percent_point_query = _is_percent_point_difference_query(query)
            ratio_row_candidates = self._extract_ratio_row_candidates(candidate_docs, query, topic)
            if ratio_row_candidates:
                logger.info("[calc_operands] ratio row fallback candidates=%s", len(ratio_row_candidates))
                synthesized_items.extend(ratio_row_candidates)
                synthesized_bullets.extend(
                    f"- {item['source_anchor']} {item.get('source_context', '')} {str(item.get('raw_row_text') or '')[:180]} (direct)"
                    for item in ratio_row_candidates
                )
                seen_anchors.update(str(item.get("source_anchor") or "") for item in ratio_row_candidates)
            if not percent_point_query:
                component_candidates = self._extract_ratio_component_candidates(candidate_docs, query, topic)
                if component_candidates:
                    logger.info("[calc_operands] ratio component fallback candidates=%s", len(component_candidates))
                    synthesized_items.extend(component_candidates)
                    synthesized_bullets.extend(
                        f"- {item['source_anchor']} {item.get('source_context', '')} {str(item.get('raw_row_text') or '')[:180]} (direct)"
                        for item in component_candidates
                    )
                    seen_anchors.update(str(item.get("source_anchor") or "") for item in component_candidates)
            for index, (doc, _score) in enumerate(candidate_docs[: min(8, len(candidate_docs))], start=1):
                metadata = dict(doc.metadata or {})
                anchor = self._build_source_anchor(metadata)
                if anchor in seen_anchors:
                    continue
                text = _normalise_spaces(doc.page_content)
                claim = text[:1200]
                item = {
                    "evidence_id": f"ev_doc_{index:03d}",
                    "source_anchor": anchor,
                    "claim": claim,
                    "quote_span": claim[:240],
                    "support_level": "direct",
                    "question_relevance": "high",
                    "allowed_terms": [],
                    "metadata": metadata,
                }
                synthesized_items.append(item)
                synthesized_bullets.append(f"- {anchor} {claim[:180]} (direct)")
            if synthesized_items:
                evidence_items = evidence_items + synthesized_items
                evidence_bullets = evidence_bullets + synthesized_bullets
                logger.info(
                    "[calc_operands] augmenting evidence with synthesized retrieved_docs=%s existing=%s",
                    len(synthesized_items),
                    len(state.get("evidence_items", []) or []),
                )
        if not evidence_items:
            return empty_result

        structured_llm = self.llm.with_structured_output(OperandExtraction)
        evidence_text = self._format_evidence_for_prompt(evidence_items, evidence_bullets)
        prompt = ChatPromptTemplate.from_template(
            """당신은 재무 계산을 위한 피연산자 추출기입니다.
질문을 풀기 위해 필요한 숫자만 single-shot으로 한 번에 추출하세요.

규칙:
- 여러 번 나눠 찾지 말고, 필요한 피연산자를 한 번의 호출로 모두 찾으세요.
- operand_id는 비워도 됩니다. 코드는 이후에 고유 ID를 부여합니다.
- 각 operand는 반드시 evidence_id와 source_anchor를 포함하세요.
- raw_value는 문서에 있는 숫자 표현 그대로 적으세요. '111조 659억원'처럼 조+억 복합 표기는 절대 억원이나 조원으로 변환하지 말고 원문 그대로 적으세요. 변환하면 반올림 오차가 발생합니다.
- raw_unit은 숫자 바로 옆 단위를 적으세요. 복합 표기('111조 659억원')는 raw_unit을 '억원'으로 적지 말고, raw_value에 원문 전체를 넣고 raw_unit은 '원'으로 적으세요.
- normalized_value와 normalized_unit은 추정해서 채워도 되지만, 이후 코드가 다시 검증합니다.
- 비교/추세 질문은 질문 해결에 꼭 필요한 숫자만 추출하세요.
- source_context와 raw_row_text가 있으면, 해당 표의 헤더와 행을 함께 읽어 period와 숫자 매핑을 복원하세요.
- raw_row_text에 같은 metric의 여러 연도/기간 값이 함께 있으면, 각 연도/기간별 숫자를 별도 operand로 나누어 추출하세요.
- 질문이 단일 비율/비중/이익률 조회라면 피연산자 1개만 추출할 수 있습니다.
- 질문이 두 기간/두 부문/두 비율의 차이·비교·대비·%p 차이를 묻는다면, 절대 단일 비율 피연산자 1개로 축약하지 말고 비교 대상별 피연산자를 각각 추출하세요.
- 질문에 `%p`, `차이`, `비교`, `대비`가 있고 evidence에 동일 metric의 여러 기간/부문 percent 값이 보이면, 해당 percent 값들을 period별/대상별로 각각 별도 operand로 추출하세요.
- 추이(trend) 질문이고 evidence에 3개 이상의 연도/기간 수치가 보이면, 가능한 한 3개 이상 기간의 피연산자를 빠짐없이 추출하세요.
- 문서 메타데이터의 보고서 연도와 표 안에 적힌 비교 기간(예: 2024년, 2023년, 2022년)을 혼동하지 말고, period 필드에는 표에서 읽은 실제 기간을 그대로 적으세요.
- 수치가 없는 descriptive evidence는 operand로 만들지 마세요.

질문: {query}

Structured Evidence:
{evidence}
"""
        )
        try:
            extracted: OperandExtraction = (prompt | structured_llm).invoke(
                {"query": query, "evidence": evidence_text}
            )
            operand_rows: List[Dict[str, Any]] = []
            for index, item in enumerate(extracted.operands, start=1):
                normalized_value, normalized_unit = _normalise_operand_value(item.raw_value, item.raw_unit)
                row = item.model_dump()
                row["operand_id"] = f"op_{index:03d}"
                row["normalized_value"] = normalized_value
                row["normalized_unit"] = normalized_unit
                operand_rows.append(row)
            if not operand_rows and _is_ratio_percent_query(query):
                fallback_rows = self._build_ratio_operands_from_candidates(
                    [item for item in evidence_items if item.get("raw_row_text")],
                    query,
                )
                if fallback_rows:
                    logger.info("[calc_operands] python ratio fallback operands=%s", len(fallback_rows))
                    operand_rows = fallback_rows
            if _is_percent_point_difference_query(query):
                operand_rows = [
                    row for row in operand_rows
                    if str(row.get("normalized_unit") or "") == "PERCENT" and row.get("normalized_value") is not None
                ]
                logger.info("[calc_operands] percent-diff operand filtering retained=%s", len(operand_rows))
            logger.info("[calc_operands] coverage=%s operands=%s", extracted.coverage, len(operand_rows))
            return {
                "calculation_operands": operand_rows,
                "calculation_debug_trace": {
                    "coverage": extracted.coverage,
                    "operands": operand_rows,
                },
            }
        except Exception as exc:
            logger.warning("[calc_operands] structured output failed: %s", exc)
            return {
                "calculation_operands": [],
                "calculation_debug_trace": {"coverage": "missing", "error": str(exc)},
            }

    def _plan_formula_calculation(self, state: FinancialAgentState) -> Dict[str, Any]:
        operands = state.get("calculation_operands", [])
        query = state["query"]
        if not operands:
            return {
                "calculation_plan": {
                    "mode": "none",
                    "operation": "none",
                    "ordered_operand_ids": [],
                    "variable_bindings": [],
                    "formula": "",
                    "pairwise_formula": "",
                    "result_unit": "",
                    "operation_text": "",
                    "explanation": "no operands",
                },
                "planner_debug_trace": {
                    "llm_invoked": False,
                    "guard_applied": False,
                    "reason": "no operands",
                },
            }

        query_text = _normalise_spaces(query)
        structured_llm = self.llm.with_structured_output(CalculationPlan)
        ontology = get_financial_ontology()
        metric_key = str(state.get("target_metric_family") or "")
        metric_info = ontology.metric_family(metric_key) if metric_key else None
        ontology_context = ""
        if metric_info:
            components = dict(metric_info.get("components") or {})
            component_lines: List[str] = []
            for role, component in components.items():
                name = str(component.get("name") or "").strip()
                keywords = ", ".join(
                    str(keyword).strip()
                    for keyword in component.get("keywords", [])
                    if str(keyword).strip()
                )
                preferred_sections = ", ".join(
                    str(section).strip()
                    for section in component.get("preferred_sections", [])
                    if str(section).strip()
                )
                bits = [f"{role}={name or '-'}"]
                if keywords:
                    bits.append(f"keywords={keywords}")
                if preferred_sections:
                    bits.append(f"preferred_sections={preferred_sections}")
                component_lines.append(" | ".join(bits))
            preferred_sections = ", ".join(
                str(section).strip()
                for section in metric_info.get("preferred_sections", [])
                if str(section).strip()
            )
            ontology_lines = [
                f"- key={metric_info.get('key', '')}",
                f"- display_name={metric_info.get('display_name', '')}",
                f"- formula_template={metric_info.get('formula_template', '')}",
                f"- result_unit={metric_info.get('result_unit', '')}",
            ]
            if preferred_sections:
                ontology_lines.append(f"- preferred_sections={preferred_sections}")
            if component_lines:
                ontology_lines.append("- components:")
                ontology_lines.extend(f"  - {line}" for line in component_lines)
            ontology_context = "\n".join(ontology_lines)
        operands_text = "\n".join(
            f"- operand_id={row.get('operand_id')} | evidence_id={row.get('evidence_id')} | label={row.get('label')} | raw={row.get('raw_value')} {row.get('raw_unit')} | normalized={row.get('normalized_value')} {row.get('normalized_unit')} | period={row.get('period', '')}"
            for row in operands
        )
        planner_trace_base = {
            "target_metric_family": metric_key,
            "ontology_context": ontology_context or "-",
            "operands_text": operands_text,
        }
        prompt = ChatPromptTemplate.from_template(
            """당신은 재무 계산 계획기입니다.
질문과 피연산자 목록을 보고 변수 바인딩과 계산식을 작성하세요.

규칙:
- variable_bindings에는 반드시 아래 피연산자 목록의 operand_id만 넣으세요.
- 각 binding의 variable은 A, B, C, D, E, F 중 하나만 사용하세요.
- ordered_operand_ids는 variable_bindings와 같은 순서로 넣으세요.
- operation은 로그/평가용 힌트입니다. subtract, add, ratio, growth_rate, max, min, time_series_trend, none 중 가장 가까운 값을 넣으세요.
- 실제 계산은 formula와 pairwise_formula로 표현합니다.
- formula에는 숫자 상수와 변수(A, B, C...) 그리고 +, -, *, /, **, min(), max(), abs(), round(), log(), exp()만 사용할 수 있습니다.
- mode=single_value 이면 formula로 단일 결과를 계산하세요.
- mode=time_series 이면 variable_bindings를 시계열 순서로 배치하고, formula에는 전체 흐름을 대표하는 계산식(예: ((C - A) / A) * 100)을, pairwise_formula에는 인접 시점 계산식(예: ((CURR - PREV) / PREV) * 100)을 적으세요.
- 최근 3년/연도별/추이 질문처럼 3개 이상 기간 데이터가 있을 때는 mode=time_series 와 operation=time_series_trend 를 우선 사용하세요.
- 이미 계산된 단일 비율/비중/이익률 하나만 답하면 되는 질문이라면 mode=single_value, formula=A 를 사용하세요.
- 질문이 단일 비율/비중/이익률 조회이고 피연산자가 퍼센트 1개뿐이라면 반드시 mode=single_value, formula=A 를 사용하세요.
- 질문이 단일 비율/비중/이익률 조회이고 분자/분모 역할의 금액 피연산자 2개가 있다면 formula는 (A / B) * 100 형태로 작성하세요.
- 두 비율/비중의 차이(%p 차이 포함)를 묻는 질문이라면 mode=single_value 로 두고 formula는 A - B 또는 질문 순서에 맞는 차이식으로 작성하세요. 단일 operand 하나로 끝내지 마세요.
- 증가율/감소율/변화율은 가능한 한 질문에서 기준이 되는 이전 값이 분모가 되도록 식을 작성하세요.
- 질문을 풀 수 없으면 mode=none, operation=none 으로 두세요.
- result_unit은 최종 답변 단위를 적으세요. 예: 억원, 원, %, 개
- ontology_context는 이 질문에 대해 추정된 metric family prior 입니다. 실제 피연산자와 모순되면 ontology_context보다 피연산자를 우선하세요.
- ontology_context에 formula_template과 components가 있으면, 단일 비율 조회는 A 또는 (A / B) * 100, %p 차이는 A - B 같은 계획을 세울 때 참고하세요.

질문: {query}

Ontology Context:
{ontology_context}

사용 가능한 피연산자:
{operands}
"""
        )
        try:
            plan: CalculationPlan = (prompt | structured_llm).invoke(
                {
                    "query": query,
                    "operands": operands_text,
                    "ontology_context": ontology_context or "-",
                }
            )
            plan_data = plan.model_dump()
            bindings = plan_data.get("variable_bindings") or []
            if not plan_data.get("ordered_operand_ids") and bindings:
                plan_data["ordered_operand_ids"] = [str(binding.get("operand_id") or "") for binding in bindings if str(binding.get("operand_id") or "").strip()]
            if not bindings and plan_data.get("ordered_operand_ids"):
                plan_data["variable_bindings"] = [
                    {"variable": chr(ord("A") + index), "operand_id": operand_id}
                    for index, operand_id in enumerate(plan_data.get("ordered_operand_ids") or [])
                ]
            if _should_coerce_percent_point_unit(query_text, operands, plan_data):
                plan_data["result_unit"] = "%p"
            logger.info("[formula_plan] mode=%s op=%s vars=%s", plan_data.get("mode"), plan_data.get("operation"), len(plan_data.get("variable_bindings") or []))
            return {
                "calculation_plan": plan_data,
                "planner_debug_trace": {
                    **planner_trace_base,
                    "llm_invoked": True,
                    "guard_applied": False,
                    "raw_plan": plan_data,
                },
            }
        except Exception as exc:
            logger.warning("[formula_plan] structured output failed: %s", exc)
            return {
                "calculation_plan": {
                    "mode": "none",
                    "operation": "none",
                    "ordered_operand_ids": [],
                    "variable_bindings": [],
                    "formula": "",
                    "pairwise_formula": "",
                    "result_unit": "",
                    "operation_text": "",
                    "explanation": str(exc),
                },
                "planner_debug_trace": {
                    **planner_trace_base,
                    "llm_invoked": True,
                    "guard_applied": False,
                    "error": str(exc),
                },
            }

    def _format_calculation_value(self, value: float, result_unit: str, normalized_unit: str) -> str:
        if normalized_unit == "KRW":
            # normalized_value is always in full KRW — always render as 조/억원 regardless of result_unit hint
            return _format_korean_won_compact(value)
        if (normalized_unit or "").upper() in {"PERCENT", "%", "퍼센트"}:
            return f"{value:.1f}"
        if normalized_unit in {"COUNT", "USD"}:
            return f"{value:,.4f}".rstrip("0").rstrip(".")
        return f"{value}"

    def _execute_calculation(self, state: FinancialAgentState) -> Dict[str, Any]:
        operands = {row.get("operand_id"): row for row in state.get("calculation_operands", [])}
        plan = state.get("calculation_plan") or {}
        operation = str(plan.get("operation") or "none")
        mode = str(plan.get("mode") or "none")
        ordered_ids = [operand_id for operand_id in (plan.get("ordered_operand_ids") or []) if operand_id in operands]
        variable_bindings = [
            binding for binding in (plan.get("variable_bindings") or [])
            if str(binding.get("operand_id") or "") in operands and str(binding.get("variable") or "").strip()
        ]
        formula = str(plan.get("formula") or "").strip()
        pairwise_formula = str(plan.get("pairwise_formula") or "").strip()
        result_unit = str(plan.get("result_unit") or "")
        explanation = str(plan.get("explanation") or "")
        selected_evidence_ids: List[str] = []
        source_normalized_unit = ""

        def _fail(status: str, reason: str) -> Dict[str, Any]:
            fallback = "질문에 필요한 수치를 계산할 수 있는 근거를 충분히 확보하지 못했습니다."
            return {
                "answer": fallback,
                "compressed_answer": fallback,
                "selected_claim_ids": selected_evidence_ids,
                "draft_points": [],
                "kept_claim_ids": selected_evidence_ids,
                "dropped_claim_ids": [],
                "unsupported_sentences": [],
                "sentence_checks": [],
                "calculation_result": {
                    "status": status,
                    "result_value": None,
                    "result_unit": result_unit,
                    "rendered_value": "",
                    "formatted_result": "",
                    "series": [],
                    "derived_metrics": {},
                    "explanation": reason,
                },
            }

        if mode == "none" or not variable_bindings:
            return _fail("insufficient_operands", explanation or "no operation or operands")

        if not ordered_ids:
            ordered_ids = [str(binding.get("operand_id") or "") for binding in variable_bindings]

        ordered_operands = [operands[operand_id] for operand_id in ordered_ids]
        selected_evidence_ids = list(
            dict.fromkeys(str(row.get("evidence_id")) for row in ordered_operands if row.get("evidence_id"))
        )
        units = {row.get("normalized_unit") for row in ordered_operands}
        if len(units) != 1:
            return _fail("unit_mismatch", f"unit families differ: {sorted(str(unit) for unit in units)}")
        normalized_unit = str(next(iter(units)))
        source_normalized_unit = normalized_unit
        values = [row.get("normalized_value") for row in ordered_operands]
        if any(value is None for value in values):
            return _fail("parse_error", "one or more operands could not be normalized")

        try:
            result_value: Optional[float]
            derived_metrics: Dict[str, Any] = {}
            result_series: List[Dict[str, Any]] = []
            env: Dict[str, float] = {}
            for binding in variable_bindings:
                variable = str(binding.get("variable") or "").strip()
                operand_id = str(binding.get("operand_id") or "").strip()
                operand = operands.get(operand_id)
                if not variable or operand is None or operand.get("normalized_value") is None:
                    return _fail("parse_error", f"invalid variable binding: {binding}")
                env[variable] = float(operand.get("normalized_value"))

            if mode == "time_series":
                if len(variable_bindings) < 2:
                    return _fail("insufficient_operands", "time_series needs at least 2 operands")
                ordered_operands = sorted(
                    [operands[str(binding.get("operand_id"))] for binding in variable_bindings],
                    key=lambda row: _extract_period_sort_key(str(row.get("period") or "")),
                )
                selected_evidence_ids = list(
                    dict.fromkeys(str(row.get("evidence_id")) for row in ordered_operands if row.get("evidence_id"))
                )
                labels = [_display_operand_label(str(row.get("label") or row.get("evidence_id") or "")) for row in ordered_operands]
                metric_names = [re.sub(r"^\d{4}년\s*", "", label).strip() for label in labels]
                metric_name = metric_names[0] if metric_names else "지표"
                for row in ordered_operands:
                    point_value = float(row.get("normalized_value"))
                    point_rendered = self._format_calculation_value(point_value, str(row.get("raw_unit") or row.get("result_unit") or ""), normalized_unit)
                    result_series.append(
                        {
                            "label": _display_operand_label(str(row.get("label") or row.get("evidence_id") or "")),
                            "period": str(row.get("period") or ""),
                            "raw_value": str(row.get("raw_value") or ""),
                            "raw_unit": str(row.get("raw_unit") or ""),
                            "normalized_value": point_value,
                            "normalized_unit": normalized_unit,
                            "rendered_value": point_rendered,
                        }
                    )
                yoy_growth_rates: List[Optional[float]] = [None]
                if pairwise_formula:
                    for previous_row, current_row in zip(ordered_operands, ordered_operands[1:]):
                        prev_value = float(previous_row.get("normalized_value"))
                        curr_value = float(current_row.get("normalized_value"))
                        try:
                            yoy_growth_rates.append(_safe_eval_formula(pairwise_formula, {"PREV": prev_value, "CURR": curr_value}))
                        except ZeroDivisionError:
                            yoy_growth_rates.append(None)
                if not formula:
                    return _fail("parse_error", "missing trend formula")
                result_value = _safe_eval_formula(formula, env)
                if result_unit == "%":
                    normalized_unit = "PERCENT"
                _is_percent = (normalized_unit or "").upper() in {"PERCENT", "%", "퍼센트"}
                if _is_percent:
                    rendered_value = f"{result_value:.1f}%"
                else:
                    rendered_value = f"{result_value:,.4f}".rstrip("0").rstrip(".")
                logger.info("[calculator] mode=%s op=%s result=%s", mode, operation, rendered_value)
                return {
                    "answer": "",
                    "compressed_answer": "",
                    "selected_claim_ids": selected_evidence_ids,
                    "draft_points": [],
                    "kept_claim_ids": selected_evidence_ids,
                    "dropped_claim_ids": [],
                    "unsupported_sentences": [],
                    "sentence_checks": [],
                    "calculation_result": {
                        "status": "ok",
                        "result_value": result_value,
                        "result_unit": result_unit,
                        "rendered_value": rendered_value,
                        "formatted_result": "",
                        "series": result_series,
                        "derived_metrics": {
                            "metric_name": metric_name,
                            "yoy_growth_rates": yoy_growth_rates,
                            "formula": formula,
                            "pairwise_formula": pairwise_formula,
                        },
                        "explanation": explanation or str(plan.get("operation_text") or operation or mode),
                    },
                }

            if not formula:
                return _fail("parse_error", "missing scalar formula")
            result_value = _safe_eval_formula(formula, env)
            if result_unit == "%":
                normalized_unit = "PERCENT"
        except Exception as exc:
            if isinstance(exc, ZeroDivisionError):
                return _fail("zero_division", str(exc))
            return _fail("parse_error", str(exc))

        rendered_value = self._format_calculation_value(result_value, result_unit or "", normalized_unit)
        if normalized_unit == "KRW":
            rendered_with_unit = rendered_value
        elif result_unit:
            rendered_with_unit = f"{rendered_value}{result_unit}"
        else:
            rendered_with_unit = rendered_value
        labels = [_display_operand_label(str(row.get("label") or row.get("evidence_id") or "")) for row in ordered_operands]
        result_series = []
        for row in ordered_operands:
            point_value = float(row.get("normalized_value"))
            point_rendered = self._format_calculation_value(
                point_value,
                str(row.get("raw_unit") or row.get("result_unit") or ""),
                source_normalized_unit,
            )
            result_series.append(
                {
                    "label": _display_operand_label(str(row.get("label") or row.get("evidence_id") or "")),
                    "period": str(row.get("period") or ""),
                    "raw_value": str(row.get("raw_value") or ""),
                    "raw_unit": str(row.get("raw_unit") or ""),
                    "normalized_value": point_value,
                    "normalized_unit": source_normalized_unit,
                    "rendered_value": point_rendered,
                }
            )
        logger.info("[calculator] op=%s result=%s", operation, rendered_with_unit)
        return {
            "answer": "",
            "compressed_answer": "",
            "selected_claim_ids": selected_evidence_ids,
            "draft_points": [],
            "kept_claim_ids": selected_evidence_ids,
            "dropped_claim_ids": [],
            "unsupported_sentences": [],
            "sentence_checks": [],
            "calculation_result": {
                "status": "ok",
                "result_value": result_value,
                "result_unit": result_unit,
                "rendered_value": rendered_with_unit,
                "formatted_result": "",
                "series": result_series,
                "derived_metrics": {
                    "operand_labels": labels,
                    "formula": formula,
                },
                "explanation": explanation or str(plan.get("operation_text") or operation or mode),
            },
        }

    def _render_calculation_answer(self, state: FinancialAgentState) -> Dict[str, Any]:
        calculation_result = dict(state.get("calculation_result") or {})
        plan = dict(state.get("calculation_plan") or {})
        operands = list(state.get("calculation_operands") or [])
        if not calculation_result:
            return {"answer": "", "compressed_answer": "", "draft_points": []}

        # direction_hint: Python에서 결정론적으로 계산 — LLM에게 부호 판단 위임하지 않음
        operation = str(plan.get("operation") or "")
        result_val = float(calculation_result.get("result_value") or 0)
        if operation == "growth_rate":
            direction_hint = "증가" if result_val > 0 else "감소" if result_val < 0 else "변동 없음"
        elif operation == "subtract":
            direction_hint = "더 큽니다" if result_val > 0 else "더 작습니다" if result_val < 0 else "동일합니다"
        else:
            direction_hint = ""

        # direction_hint가 방향을 표현할 때 rendered_value의 부호는 중복 — 제거
        if direction_hint and result_val < 0:
            rv = str(calculation_result.get("rendered_value") or "")
            calculation_result["rendered_value"] = rv.lstrip("-")

        if str(calculation_result.get("status") or "") != "ok":
            fallback = "질문에 필요한 수치를 계산할 수 있는 근거를 충분히 확보하지 못했습니다."
            return {
                "answer": fallback,
                "compressed_answer": fallback,
                "draft_points": [fallback],
            }

        structured_llm = self.llm.with_structured_output(CalculationRenderOutput)
        prompt = ChatPromptTemplate.from_template(
            """당신은 한국 기업 공시(DART) 계산 결과를 사용자 친화적인 한국어로 렌더링하는 분석가입니다.

[렌더링 규칙]
- CalculationResult의 rendered_value를 그대로 사용하세요. 숫자를 다시 계산하거나 형식을 바꾸지 마세요.
- operand label에 포함된 연도·기간 정보(예: '2024년', '2023년', '1분기')는 반드시 그대로 유지하세요. '2024년 영업이익'을 '영업이익'으로 줄이지 마세요.
- direction_hint가 제공된 경우, 그 단어를 그대로 사용하세요. 임의로 '변동', '차이' 등 중립적 표현으로 바꾸지 마세요.
- time_series 해석(상승·하락·반등 등)은 series 또는 derived_metrics의 수치 변화를 근거로 표현하세요.
- 데이터에 없는 새로운 연도, 금액, 비율을 만들지 마세요.
- 질문에 직접 답하는 1~2문장만 작성하세요.

질문:
{query}

Direction Hint (방향 판단 결과, 비어 있으면 무시):
{direction_hint}

CalculationPlan:
{plan_json}

CalculationResult:
{result_json}

Operands:
{operands_json}

반드시 final_answer만 채우세요.
"""
        )
        try:
            rendered: CalculationRenderOutput = (prompt | structured_llm).invoke(
                {
                    "query": state["query"],
                    "direction_hint": direction_hint,
                    "plan_json": json.dumps(plan, ensure_ascii=False, indent=2),
                    "result_json": json.dumps(calculation_result, ensure_ascii=False, indent=2),
                    "operands_json": json.dumps(operands, ensure_ascii=False, indent=2),
                }
            )
            answer = _normalise_spaces(rendered.final_answer)
        except Exception as exc:
            logger.warning("[calc_renderer] structured output failed, using deterministic fallback: %s", exc)
            answer = str(calculation_result.get("rendered_value") or calculation_result.get("formatted_result") or "").strip()
            if not answer:
                answer = "질문에 필요한 수치를 계산했지만 자연어 답변을 생성하지 못했습니다."

        calculation_result["formatted_result"] = answer
        return {
            "answer": answer,
            "compressed_answer": answer,
            "draft_points": [answer] if answer else [],
            "calculation_result": calculation_result,
        }

    def _route_after_expand(self, state: FinancialAgentState) -> str:
        intent = state.get("intent") or state.get("query_type", "qa")
        if intent == "numeric_fact":
            return "numeric_extractor"
        return "evidence"

    def _route_after_evidence(self, state: FinancialAgentState) -> str:
        intent = state.get("intent") or state.get("query_type", "qa")
        if intent in {"comparison", "trend"}:
            return "operand_extractor"
        return "compress"

    def _format_citations(self, state: FinancialAgentState) -> Dict[str, Any]:
        seen = set()
        citations: List[str] = []
        for doc, score in state.get("retrieved_docs", []):
            metadata = doc.metadata or {}
            key = (
                metadata.get("company"),
                metadata.get("year"),
                metadata.get("section_path"),
                metadata.get("chunk_uid"),
            )
            if key in seen:
                continue
            seen.add(key)
            citations.append(
                f"[{metadata.get('company', '?')}] {metadata.get('year', '?')}년 "
                f"{metadata.get('report_type', '?')} / {metadata.get('section_path', metadata.get('section', '?'))} "
                f"/ {metadata.get('block_type', '?')} (score: {score:.3f})"
            )
        return {"citations": citations}

    def _build_graph(self):
        graph = StateGraph(FinancialAgentState)

        graph.add_node("classify", self._classify_query)
        graph.add_node("extract", self._extract_entities)
        graph.add_node("retrieve", self._retrieve)
        graph.add_node("expand", self._expand_via_structure_graph)
        graph.add_node("numeric_extractor", self._extract_numeric_fact)
        graph.add_node("evidence", self._extract_evidence)
        graph.add_node("operand_extractor", self._extract_calculation_operands)
        graph.add_node("formula_planner", self._plan_formula_calculation)
        graph.add_node("calculator", self._execute_calculation)
        graph.add_node("calc_render", self._render_calculation_answer)
        graph.add_node("compress", self._compress_answer)
        graph.add_node("validate", self._validate_answer)
        graph.add_node("cite", self._format_citations)

        graph.set_entry_point("classify")
        graph.add_edge("classify", "extract")
        graph.add_edge("extract", "retrieve")
        graph.add_edge("retrieve", "expand")
        graph.add_conditional_edges(
            "expand",
            self._route_after_expand,
            {"numeric_extractor": "numeric_extractor", "evidence": "evidence"},
        )
        graph.add_edge("numeric_extractor", "cite")
        graph.add_conditional_edges(
            "evidence",
            self._route_after_evidence,
            {"operand_extractor": "operand_extractor", "compress": "compress"},
        )
        graph.add_edge("operand_extractor", "formula_planner")
        graph.add_edge("formula_planner", "calculator")
        graph.add_edge("calculator", "calc_render")
        graph.add_edge("calc_render", "cite")
        graph.add_edge("compress", "validate")
        graph.add_edge("validate", "cite")
        graph.add_edge("cite", END)

        return graph.compile()

    def run(self, query: str) -> Dict[str, Any]:
        initial: FinancialAgentState = {
            "query": query,
            "query_type": "",
            "intent": "",
            "target_metric_family": "",
            "format_preference": "",
            "routing_source": "",
            "routing_confidence": 0.0,
            "routing_scores": {},
            "companies": [],
            "years": [],
            "topic": "",
            "section_filter": None,
            "seed_retrieved_docs": [],
            "retrieved_docs": [],
            "evidence_bullets": [],
            "evidence_items": [],
            "evidence_status": "missing",
            "selected_claim_ids": [],
            "draft_points": [],
            "compressed_answer": "",
            "kept_claim_ids": [],
            "dropped_claim_ids": [],
            "unsupported_sentences": [],
            "sentence_checks": [],
            "answer": "",
            "citations": [],
            "numeric_debug_trace": {},
            "calculation_operands": [],
            "calculation_plan": {},
            "calculation_result": {},
            "calculation_debug_trace": {},
            "planner_debug_trace": {},
        }
        final = self.graph.invoke(initial)
        return {
            "query": final["query"],
            "query_type": final["query_type"],
            "intent": final.get("intent", final["query_type"]),
            "target_metric_family": final.get("target_metric_family", ""),
            "format_preference": final.get("format_preference", ""),
            "routing_source": final.get("routing_source", ""),
            "routing_confidence": final.get("routing_confidence", 0.0),
            "routing_scores": final.get("routing_scores", {}),
            "companies": final["companies"],
            "years": final["years"],
            "answer": final["answer"],
            "citations": final["citations"],
            "seed_retrieved_docs": final.get("seed_retrieved_docs", []),
            "retrieved_docs": final["retrieved_docs"],
            "evidence_items": final.get("evidence_items", []),
            "selected_claim_ids": final.get("selected_claim_ids", []),
            "draft_points": final.get("draft_points", []),
            "kept_claim_ids": final.get("kept_claim_ids", []),
            "dropped_claim_ids": final.get("dropped_claim_ids", []),
            "unsupported_sentences": final.get("unsupported_sentences", []),
            "sentence_checks": final.get("sentence_checks", []),
            "numeric_debug_trace": final.get("numeric_debug_trace", {}),
            "calculation_operands": final.get("calculation_operands", []),
            "calculation_plan": final.get("calculation_plan", {}),
            "calculation_result": final.get("calculation_result", {}),
            "calculation_debug_trace": final.get("calculation_debug_trace", {}),
            "planner_debug_trace": final.get("planner_debug_trace", {}),
        }

    def ingest(self, chunks: List) -> None:
        if not chunks:
            logger.warning("[ingest] chunks are empty.")
            return
        texts = [chunk.content for chunk in chunks]
        metadatas = [chunk.metadata for chunk in chunks]
        self.vsm.add_documents(texts, metadatas)
        logger.info("[ingest] indexed %s chunks", len(chunks))

    # ------------------------------------------------------------------
    # Contextual Retrieval + Parent-child ingest
    # ------------------------------------------------------------------

    def _generate_context(self, text: str, metadata: dict) -> str:
        """청크 1개에 대해 LLM으로 1문장 컨텍스트 설명 생성.

        생성된 컨텍스트는 청크 텍스트 앞에 붙여 인덱싱함으로써
        BM25·벡터 검색 양쪽에서 섹션/주제 신호를 강화한다.
        """
        company      = metadata.get("company", "?")
        year         = metadata.get("year", "?")
        section_path = metadata.get("section_path", metadata.get("section", "?"))
        block_type   = "표" if metadata.get("block_type") == "table" else "단락"
        preview      = re.sub(r"\s+", " ", text[:400]).strip()

        prompt = (
            f"다음은 {company} {year}년 사업보고서의 [{section_path}] 섹션에서 발췌한 {block_type}입니다.\n"
            f"이 내용이 전체 문서 맥락에서 어떤 정보를 담고 있는지 한국어로 한 문장(50자 이내)으로만 설명하세요.\n\n"
            f"내용:\n{preview}"
        )
        try:
            response = self.llm.invoke(prompt)
            return response.content.strip()
        except Exception as e:
            logger.warning("Context generation failed: %s", e)
            return f"{company} {year}년 사업보고서 / {section_path} / {block_type}"

    def _fallback_context(self, metadata: dict) -> str:
        company = metadata.get("company", "?")
        year = metadata.get("year", "?")
        section_path = metadata.get("section_path", metadata.get("section", "?"))
        block_type = "표" if metadata.get("block_type") == "table" else "단락"
        return f"{company} {year}년 사업보고서 / {section_path} / {block_type}"

    def _build_context_prompt(self, text: str, metadata: dict) -> str:
        company = metadata.get("company", "?")
        year = metadata.get("year", "?")
        section_path = metadata.get("section_path", metadata.get("section", "?"))
        block_type = "표" if metadata.get("block_type") == "table" else "단락"
        preview = re.sub(r"\s+", " ", text[:400]).strip()
        return (
            f"다음은 {company} {year}년 사업보고서의 [{section_path}] 섹션에서 발췌한 {block_type}입니다.\n"
            f"이 내용이 전체 문서 맥락에서 어떤 정보를 담고 있는지 한국어로 한 문장(50자 이내)으로만 설명하세요.\n\n"
            f"내용:\n{preview}"
        )

    def _build_index_prefix(self, metadata: dict, context: str) -> str:
        company = metadata.get("company", "?")
        year = metadata.get("year", "?")
        report_type = metadata.get("report_type", "?")
        section = metadata.get("section", "?")
        section_path = metadata.get("section_path", section)
        block_type = "표" if metadata.get("block_type") == "table" else "단락"
        return "\n".join(
            [
                context.strip(),
                f"{company} {year} {report_type}",
                f"섹션: {section_path}",
                f"분류: {section} / {block_type}",
            ]
        )

    def _resolve_context_workers(self, max_workers: Optional[int], total: int) -> int:
        if total <= 0:
            return 1

        configured = max_workers or int(
            os.environ.get("CONTEXTUAL_INGEST_MAX_WORKERS", DEFAULT_CONTEXT_MAX_WORKERS)
        )
        return max(1, min(configured, total))

    def _resolve_context_batch_size(self, batch_size: Optional[int], workers: int) -> int:
        configured = batch_size or int(
            os.environ.get("CONTEXTUAL_INGEST_BATCH_SIZE", DEFAULT_CONTEXT_BATCH_SIZE)
        )
        return max(workers, configured)

    def contextual_ingest(
        self,
        chunks: List,
        on_progress=None,
        max_workers: Optional[int] = None,
        batch_size: Optional[int] = None,
    ) -> None:
        """Contextual Retrieval + Parent-child 방식으로 청크를 인덱싱한다.

        1. 섹션 단위 부모 청크를 생성해 VectorStoreManager에 저장
        2. 각 자식 청크에 대해 LLM으로 컨텍스트 문장 생성 (병렬 처리)
        3. '컨텍스트 + 원문'을 ChromaDB·BM25에 인덱싱

        Args:
            chunks:       FinancialParser.process_document() 반환값
            on_progress:  진행 콜백 (completed: int, total: int) → None
            max_workers:  LLM 병렬 호출 수
            batch_size:   한 번에 LLM.batch()로 보내는 요청 수
        """
        if not chunks:
            logger.warning("[contextual_ingest] chunks are empty.")
            return {
                "mode": "contextual",
                "chunks": 0,
                "stored_parent_chunks": 0,
                "api_calls": 0,
                "fallback_count": 0,
                "prompt_chars": 0,
                "response_chars": 0,
                "prompt_tokens": 0,
                "output_tokens": 0,
                "total_tokens": 0,
                "max_workers": 0,
                "batch_size": 0,
                "elapsed_sec": 0.0,
            }

        from processing.financial_parser import FinancialParser

        # 1) 부모 청크 저장
        parents = FinancialParser.build_parents(chunks)
        self.vsm.add_parents(parents)
        logger.info("[contextual_ingest] stored %s parent chunks", len(parents))

        # 2) 배치 병렬 컨텍스트 생성
        total = len(chunks)
        contexts: Dict[int, str] = {}
        workers = self._resolve_context_workers(max_workers, total)
        request_batch_size = self._resolve_context_batch_size(batch_size, workers)
        completed_count = 0

        logger.info(
            "[contextual_ingest] generating contexts with max_workers=%s batch_size=%s",
            workers,
            request_batch_size,
        )

        for start in range(0, total, request_batch_size):
            batch_items = list(enumerate(chunks[start : start + request_batch_size], start=start))
            prompts = [self._build_context_prompt(chunk.content, chunk.metadata) for _, chunk in batch_items]

            try:
                responses = self.llm.batch(
                    prompts,
                    config={"max_concurrency": workers},
                    return_exceptions=True,
                )
            except Exception as exc:
                logger.warning("Context batch generation failed, falling back to per-item mode: %s", exc)
                responses = [exc] * len(batch_items)

            for (idx, chunk), response in zip(batch_items, responses):
                if isinstance(response, Exception):
                    logger.warning("Context generation failed for chunk %s: %s", idx, response)
                    contexts[idx] = self._fallback_context(chunk.metadata)
                else:
                    content = getattr(response, "content", "") or ""
                    contexts[idx] = content.strip() or self._fallback_context(chunk.metadata)

                completed_count += 1
                if on_progress:
                    on_progress(completed_count, total)

        # 3) 컨텍스트 prefix를 붙여 인덱싱
        texts = [
            f"{self._build_index_prefix(chunks[i].metadata, contexts[i])}\n\n{chunks[i].content}"
            for i in range(total)
        ]
        metadatas = [chunk.metadata for chunk in chunks]
        self.vsm.add_documents(texts, metadatas)
        logger.info("[contextual_ingest] indexed %s contextualized chunks", total)

    def benchmark_contextual_ingest(
        self,
        chunks: List,
        on_progress=None,
        max_workers: Optional[int] = None,
        batch_size: Optional[int] = None,
        return_artifacts: bool = False,
    ) -> Dict[str, Any]:
        """Contextual ingest variant that returns timing and usage metrics."""
        if not chunks:
            return {
                "mode": "contextual",
                "chunks": 0,
                "stored_parent_chunks": 0,
                "api_calls": 0,
                "fallback_count": 0,
                "prompt_chars": 0,
                "response_chars": 0,
                "prompt_tokens": 0,
                "output_tokens": 0,
                "total_tokens": 0,
                "max_workers": 0,
                "batch_size": 0,
                "elapsed_sec": 0.0,
            }

        from processing.financial_parser import FinancialParser

        started_at = time.perf_counter()
        parents = FinancialParser.build_parents(chunks)
        self.vsm.add_parents(parents)

        total = len(chunks)
        contexts: Dict[int, str] = {}
        workers = self._resolve_context_workers(max_workers, total)
        request_batch_size = self._resolve_context_batch_size(batch_size, workers)
        completed_count = 0
        prompt_chars = 0
        response_chars = 0
        prompt_tokens = 0
        output_tokens = 0
        total_tokens = 0
        fallback_count = 0

        logger.info(
            "[benchmark_contextual_ingest] generating contexts with max_workers=%s batch_size=%s",
            workers,
            request_batch_size,
        )

        for start in range(0, total, request_batch_size):
            batch_items = list(enumerate(chunks[start : start + request_batch_size], start=start))
            prompts = [self._build_context_prompt(chunk.content, chunk.metadata) for _, chunk in batch_items]
            prompt_chars += sum(len(prompt) for prompt in prompts)

            try:
                responses = self.llm.batch(
                    prompts,
                    config={"max_concurrency": workers},
                    return_exceptions=True,
                )
            except Exception as exc:
                logger.warning("Context batch generation failed, falling back to per-item mode: %s", exc)
                responses = [exc] * len(batch_items)

            for (idx, chunk), response in zip(batch_items, responses):
                if isinstance(response, Exception):
                    contexts[idx] = self._fallback_context(chunk.metadata)
                    fallback_count += 1
                else:
                    content = getattr(response, "content", "") or ""
                    contexts[idx] = content.strip() or self._fallback_context(chunk.metadata)
                    usage = _extract_usage_counts(response)
                    prompt_tokens += usage["prompt_tokens"]
                    output_tokens += usage["output_tokens"]
                    total_tokens += usage["total_tokens"]

                response_chars += len(contexts[idx])
                completed_count += 1
                if on_progress:
                    on_progress(completed_count, total)

        texts = [
            f"{self._build_index_prefix(chunks[i].metadata, contexts[i])}\n\n{chunks[i].content}"
            for i in range(total)
        ]
        metadatas = [chunk.metadata for chunk in chunks]
        self.vsm.add_documents(texts, metadatas)

        result = {
            "mode": "contextual",
            "chunks": total,
            "stored_parent_chunks": len(parents),
            "api_calls": total,
            "fallback_count": fallback_count,
            "prompt_chars": prompt_chars,
            "response_chars": response_chars,
            "prompt_tokens": prompt_tokens,
            "output_tokens": output_tokens,
            "total_tokens": total_tokens,
            "max_workers": workers,
            "batch_size": request_batch_size,
            "elapsed_sec": time.perf_counter() - started_at,
        }
        if return_artifacts:
            result["artifacts"] = {
                "texts": texts,
                "metadatas": metadatas,
                "parents": parents,
            }
        return result


if __name__ == "__main__":
    import os
    import sys

    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    logging.basicConfig(level=logging.INFO)

    from processing.financial_parser import FinancialParser
    from storage.vector_store import DEFAULT_COLLECTION_NAME, VectorStoreManager

    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    reports_dir = os.path.join(project_root, "data", "reports")
    chroma_dir = os.path.join(project_root, "data", "chroma_dart")

    target = None
    for root_dir, _dirs, files in os.walk(reports_dir):
        for filename in files:
            if filename.endswith(".html"):
                target = os.path.join(root_dir, filename)
                break
        if target:
            break

    if not target:
        print("[SKIP] data/reports/ 아래에 .html 파일이 없습니다. dart_fetcher.py를 먼저 실행하세요.")
        sys.exit(0)

    parser = FinancialParser()
    metadata = {
        "company": "삼성전자",
        "stock_code": "005930",
        "year": 2023,
        "report_type": "사업보고서",
        "rcept_no": "20230307000542",
    }
    chunks = parser.process_document(target, metadata)
    print(f"[1] parsed {len(chunks)} chunks")

    vsm = VectorStoreManager(persist_directory=chroma_dir, collection_name=DEFAULT_COLLECTION_NAME)
    agent = FinancialAgent(vsm)
    agent.ingest(chunks)
    print("[2] indexing complete")

    for question in [
        "삼성전자의 주요 리스크 요인을 알려줘.",
        "삼성전자 2023년 매출과 영업이익은?",
    ]:
        result = agent.run(question)
        print(f"\nQ: {question}")
        print(f"type: {result['query_type']} | companies: {result['companies']} | years: {result['years']}")
        print(result["answer"][:500])
        print(result["citations"][:3])
