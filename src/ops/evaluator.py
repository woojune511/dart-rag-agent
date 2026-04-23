"""
RAG evaluation pipeline for DART analysis.
"""

from __future__ import annotations

import json
import logging
import re
from statistics import mean
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import mlflow
import numpy as np
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_huggingface import HuggingFaceEmbeddings

from storage.vector_store import DEFAULT_COLLECTION_NAME, DEFAULT_EMBEDDING_MODEL

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_DATASET = _PROJECT_ROOT / "data" / "eval" / "eval_dataset.json"
DEFAULT_NUMERIC_SECTION_ALIASES = [
    "매출현황",
    "재무제표",
    "요약재무",
    "연결재무제표",
    "연결재무제표 주석",
]
MISSING_RESPONSE_MARKERS = (
    "없",
    "찾지 못",
    "근거를 찾지 못",
    "답할 수 있는 근거를 찾지 못",
    "확인되지",
    "확인할 수 없",
    "명시되지",
    "어렵",
)
ABSTENTION_RESPONSE_MARKERS = (
    "관련 공시 문서에서 질문에 직접 답할 수 있는 근거를 찾지 못했습니다",
    "질문에 직접 답할 수 있는 근거를 찾지 못했습니다",
    "공시 문서에 정보가 없거나",
    "현재 검색 결과만으로는 확인하기 어렵습니다",
)


@dataclass
class EvalEvidence:
    section_path: str
    quote: str
    quote_type: str = "verbatim"
    why_it_supports_answer: str = ""


@dataclass
class EvalExample:
    id: str
    question: str
    ground_truth: str
    company: str
    year: int
    section: str
    category: Optional[str] = None
    answer_key: str = ""
    expected_sections: List[str] = field(default_factory=list)
    evidence: List[EvalEvidence] = field(default_factory=list)
    missing_info_policy: Optional[str] = None
    document_id: str = ""
    ground_truth_context_ids: List[str] = field(default_factory=list)
    ground_truth_evidence_quotes: List[str] = field(default_factory=list)
    required_entities: List[str] = field(default_factory=list)
    answer_type: str = ""
    expected_refusal: bool = False
    numeric_constraints: Dict[str, Any] = field(default_factory=dict)
    reasoning_steps: List[str] = field(default_factory=list)
    aliases: Dict[str, List[str]] = field(default_factory=dict)
    verification_status: str = ""
    notes: str = ""

    @property
    def canonical_answer_key(self) -> str:
        return self.answer_key or self.ground_truth

    @property
    def canonical_expected_sections(self) -> List[str]:
        sections: List[str] = []
        for value in self.expected_sections + ([self.section] if self.section else []):
            cleaned = str(value or "").strip()
            if cleaned and cleaned not in sections:
                sections.append(cleaned)
        return sections

    @property
    def recall_reference_text(self) -> str:
        if self.evidence:
            return "\n".join(evidence.quote for evidence in self.evidence if evidence.quote)
        return self.ground_truth


@dataclass
class EvalResult:
    id: str
    question: str
    answer: str
    ground_truth: str
    answer_key: str
    expected_sections: List[str]
    evidence: List[Dict[str, str]]
    raw_faithfulness: Optional[float]
    faithfulness: float
    faithfulness_override_reason: Optional[str]
    answer_relevancy: float
    context_recall: float
    retrieval_hit_at_k: float
    ndcg_at_3: Optional[float]
    ndcg_at_5: Optional[float]
    context_precision_at_3: Optional[float]
    context_precision_at_5: Optional[float]
    section_match_rate: float
    citation_coverage: float
    entity_coverage: Optional[float]
    completeness: Optional[float]
    completeness_reason: Optional[str]
    missing_info_compliance: Optional[float]
    refusal_accuracy: Optional[float]
    retrieved_count: int
    query_type: str
    latency_sec: float
    absolute_error_rate: Optional[float] = None
    calculation_correctness: Optional[float] = None
    citations: List[str] = field(default_factory=list)
    retrieved_metadata: List[Dict[str, Any]] = field(default_factory=list)
    retrieved_previews: List[Dict[str, Any]] = field(default_factory=list)
    runtime_evidence: List[Dict[str, Any]] = field(default_factory=list)
    selected_claim_ids: List[str] = field(default_factory=list)
    draft_points: List[str] = field(default_factory=list)
    kept_claim_ids: List[str] = field(default_factory=list)
    dropped_claim_ids: List[str] = field(default_factory=list)
    unsupported_sentences: List[str] = field(default_factory=list)
    sentence_checks: List[Dict[str, Any]] = field(default_factory=list)
    numeric_equivalence: Optional[float] = None
    numeric_grounding: Optional[float] = None
    numeric_retrieval_support: Optional[float] = None
    numeric_final_judgement: Optional[str] = None
    numeric_confidence: Optional[float] = None
    numeric_debug: Dict[str, Any] = field(default_factory=dict)
    missing_info_policy: Optional[str] = None
    error: Optional[str] = None

    @property
    def aggregate_score(self) -> float:
        metrics = [
            self.faithfulness,
            self.answer_relevancy,
            self.context_recall,
            self.retrieval_hit_at_k,
            self.section_match_rate,
            self.citation_coverage,
        ]
        return sum(metrics) / len(metrics)


_FAITHFULNESS_PROMPT = """\
다음은 검색된 컨텍스트와 그에 대한 답변입니다.
답변이 컨텍스트에서만 근거한 내용인지 평가해주세요.

[컨텍스트]
{context}

[답변]
{answer}

평가 기준:
- 1.0: 답변의 모든 내용이 컨텍스트에 명확히 근거함
- 0.7: 대체로 근거하나 일부 해석/요약이 포함됨
- 0.5: 절반 정도만 근거하고 나머지는 추론이 큼
- 0.3: 컨텍스트와 약하게만 연결됨
- 0.0: 컨텍스트에 없는 내용이 대부분임

예외 규칙:
- 숫자/단위 표현이 달라도 수학적으로 동치이면 감점하지 마세요.
- 연도/기수 표기를 사용자가 이해하기 쉽게 풀어쓴 것은 감점하지 마세요.
- 정보를 압축하거나 요약했더라도 없는 사실을 추가하지 않았다면 감점하지 마세요.

숫자(0.0~1.0)만 답하세요."""

_COMPLETENESS_PROMPT = """\
다음은 질문, 답변, 그리고 정답 기준 요약입니다.
답변이 질문 의도에 비해 얼마나 충분하고 친절하게 설명했는지 평가하세요.

[질문]
{question}

[답변]
{answer}

[정답 기준 요약]
{answer_key}

[필수 엔티티]
{required_entities}

평가 기준:
- 1.0: 질문이 요구한 핵심 요소를 빠짐없이, 이해하기 쉬운 완전한 문장으로 설명함
- 0.7: 핵심 요소는 대체로 포함하지만 설명이 다소 짧거나 일부 맥락이 빠짐
- 0.5: 절반 정도만 답했고 중요한 요소 누락이 있음
- 0.3: 질문과 관련은 있으나 지나치게 짧거나 핵심 누락이 큼
- 0.0: 질문 의도에 거의 답하지 못함

다음 JSON만 답하세요.
{{
  "score": 0.0,
  "reason": "짧은 이유"
}}
"""

_NUMERIC_GROUNDING_PROMPT = """\
다음은 숫자 질문에 대한 답변과 근거입니다.
답변의 핵심 숫자 주장이 근거에 직접 뒷받침되는지 평가하세요.

중요 규칙:
- 단위 변환으로 같은 값을 표현한 경우는 같은 값으로 인정하세요.
- 예: `300조 8,709억원`과 `300,870,903 백만원`은 같은 금액입니다.
- 숫자가 맞아도 질문이 묻는 대상 항목이 다르면 grounded가 아닙니다.
- 근거에 없는 숫자나 잘못된 단위 해석이면 not_grounded입니다.
- 확실하지 않으면 uncertain을 선택하세요.

[질문]
{question}

[답변]
{answer}

[Canonical Answer]
{answer_key}

[Runtime Evidence]
{runtime_evidence}

[Canonical Evidence]
{canonical_evidence}

다음 JSON만 답하세요.
{{
  "verdict": "grounded|not_grounded|uncertain",
  "confidence": 0.0,
  "reason": "짧은 이유"
}}
"""


def _tokenize_ko(text: str) -> set[str]:
    tokens = re.findall(r"[가-힣A-Za-z0-9]+", text or "")
    return {token.lower() for token in tokens if len(token) >= 2}


def _contains_section(metadata: Dict[str, Any], expected_section: str) -> bool:
    section = str(metadata.get("section", ""))
    section_path = str(metadata.get("section_path", ""))
    return expected_section == section or expected_section in section_path


def _looks_like_missing_answer(text: str) -> bool:
    lowered = (text or "").lower()
    return any(marker in lowered for marker in MISSING_RESPONSE_MARKERS)


def _looks_like_full_abstention_answer(text: str) -> bool:
    lowered = (text or "").lower()
    return any(marker in lowered for marker in ABSTENTION_RESPONSE_MARKERS)


def _safe_float(value: Any) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _parse_number(value: str) -> Optional[float]:
    cleaned = str(value or "").replace(",", "").strip()
    if not cleaned:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def _is_overlapping(start: int, end: int, spans: List[Tuple[int, int]]) -> bool:
    return any(not (end <= existing_start or start >= existing_end) for existing_start, existing_end in spans)


def _build_numeric_candidate(
    *,
    value_text: str,
    unit_text: str,
    kind: str,
    normalized_value: Optional[float],
    start: int,
    end: int,
) -> Dict[str, Any]:
    return {
        "value_text": value_text,
        "unit_text": unit_text,
        "kind": kind,
        "normalized_value": normalized_value,
        "span": [start, end],
    }


def _extract_numeric_candidates(text: str) -> List[Dict[str, Any]]:
    if not text:
        return []

    candidates: List[Dict[str, Any]] = []
    occupied_spans: List[Tuple[int, int]] = []

    composite_currency_patterns = [
        re.compile(r"(?P<jo>[\d,]+)\s*조\s*(?P<eok>[\d,]+)\s*억\s*원?"),
        re.compile(r"(?P<jo>[\d,]+)\s*조\s*(?P<eok>[\d,]+)\s*억원"),
        re.compile(r"(?P<jo>[\d,]+)\s*조원"),
    ]
    for pattern in composite_currency_patterns:
        for match in pattern.finditer(text):
            start, end = match.span()
            if _is_overlapping(start, end, occupied_spans):
                continue
            jo_value = _parse_number(match.groupdict().get("jo") or "")
            eok_value = _parse_number(match.groupdict().get("eok") or "0")
            if jo_value is None:
                continue
            normalized_value = jo_value * 1_0000_0000_0000 + (eok_value or 0.0) * 100_000_000
            candidates.append(
                _build_numeric_candidate(
                    value_text=match.group(0),
                    unit_text="원",
                    kind="currency",
                    normalized_value=normalized_value,
                    start=start,
                    end=end,
                )
            )
            occupied_spans.append((start, end))

    generic_patterns = [
        (re.compile(r"(?P<value>[\d,]+(?:\.\d+)?)\s*(?P<unit>백만원|억원|천원|원)"), "currency"),
        (re.compile(r"(?P<value>[\d,]+(?:\.\d+)?)\s*(?P<unit>%|퍼센트)"), "percent"),
        (re.compile(r"(?P<value>[\d,]+(?:\.\d+)?)\s*(?P<unit>개|곳|명)"), "count"),
    ]
    currency_scale = {
        "원": 1.0,
        "천원": 1_000.0,
        "백만원": 1_000_000.0,
        "억원": 100_000_000.0,
    }

    for pattern, kind in generic_patterns:
        for match in pattern.finditer(text):
            start, end = match.span()
            if _is_overlapping(start, end, occupied_spans):
                continue
            raw_value = _parse_number(match.group("value"))
            unit = match.group("unit")
            if raw_value is None:
                continue
            if kind == "currency":
                normalized_value = raw_value * currency_scale[unit]
            else:
                normalized_value = raw_value
            candidates.append(
                _build_numeric_candidate(
                    value_text=match.group(0),
                    unit_text=unit,
                    kind=kind,
                    normalized_value=normalized_value,
                    start=start,
                    end=end,
                )
            )
            occupied_spans.append((start, end))

    candidates.sort(key=lambda item: (item["span"][0], item["span"][1]))
    return candidates


def _numeric_values_equivalent(left: Dict[str, Any], right: Dict[str, Any]) -> bool:
    if left.get("kind") != right.get("kind"):
        return False
    left_value = _safe_float(left.get("normalized_value"))
    right_value = _safe_float(right.get("normalized_value"))
    if left_value is None or right_value is None:
        return False

    if left.get("kind") == "currency":
        tolerance = max(abs(right_value) * 1e-6, 0.5)
    elif left.get("kind") == "percent":
        tolerance = 1e-6
    else:
        tolerance = 1e-6
    return abs(left_value - right_value) <= tolerance


def _compute_numeric_equivalence(
    answer: str,
    answer_key: str,
    canonical_evidence: List[EvalEvidence],
) -> Tuple[Optional[float], Dict[str, Any]]:
    answer_candidates = _extract_numeric_candidates(answer)
    reference_candidates = _extract_numeric_candidates(answer_key)
    for evidence in canonical_evidence:
        reference_candidates.extend(_extract_numeric_candidates(evidence.quote))

    if not answer_candidates or not reference_candidates:
        return None, {
            "answer_candidates": answer_candidates,
            "reference_candidates": reference_candidates,
            "matched_pair": None,
            "reason": "missing_candidates",
        }

    for answer_candidate in answer_candidates:
        for reference_candidate in reference_candidates:
            if _numeric_values_equivalent(answer_candidate, reference_candidate):
                return 1.0, {
                    "answer_candidates": answer_candidates,
                    "reference_candidates": reference_candidates,
                    "matched_pair": {
                        "answer": answer_candidate,
                        "reference": reference_candidate,
                    },
                    "reason": "equivalent_value",
                }

    return 0.0, {
        "answer_candidates": answer_candidates,
        "reference_candidates": reference_candidates,
        "matched_pair": None,
        "reason": "no_equivalent_value",
    }


def _format_runtime_evidence_for_numeric_judge(runtime_evidence: List[Dict[str, Any]]) -> str:
    if not runtime_evidence:
        return "-"
    rows: List[str] = []
    for row in runtime_evidence[:6]:
        metadata = row.get("metadata") or {}
        section = metadata.get("section_path") or metadata.get("section") or "?"
        rows.append(
            " | ".join(
                part
                for part in [
                    row.get("source_anchor") or "?",
                    f"section={section}",
                    f"claim={row.get('claim', '')}",
                    f"quote={row.get('quote_span', '')}",
                ]
                if part
            )
        )
    return "\n".join(rows)


def _format_canonical_evidence_for_numeric_judge(example: EvalExample) -> str:
    if not example.evidence:
        return "-"
    return "\n".join(
        f"{evidence.section_path}: {evidence.quote}"
        for evidence in example.evidence[:4]
        if evidence.quote
    ) or "-"


def _compute_numeric_grounding(
    llm: ChatGoogleGenerativeAI,
    example: EvalExample,
    answer: str,
    runtime_evidence: List[Dict[str, Any]],
) -> Tuple[Optional[float], Dict[str, Any]]:
    if not answer:
        return None, {"verdict": "uncertain", "confidence": 0.0, "reason": "empty_answer"}

    prompt = _NUMERIC_GROUNDING_PROMPT.format(
        question=example.question[:800],
        answer=answer[:1200],
        answer_key=example.canonical_answer_key[:800],
        runtime_evidence=_format_runtime_evidence_for_numeric_judge(runtime_evidence)[:3000],
        canonical_evidence=_format_canonical_evidence_for_numeric_judge(example)[:2000],
    )
    try:
        response = llm.invoke(prompt)
        text = (response.content or "").strip()
        data: Dict[str, Any]
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", text, re.DOTALL)
            data = json.loads(match.group(0)) if match else {}
        verdict = str(data.get("verdict", "uncertain")).strip().lower()
        confidence = _safe_float(data.get("confidence"))
        confidence = confidence if confidence is not None else 0.0
        if verdict == "grounded":
            score = 1.0
        elif verdict == "not_grounded":
            score = 0.0
        else:
            score = None
        return score, {
            "verdict": verdict,
            "confidence": float(max(0.0, min(confidence, 1.0))),
            "reason": str(data.get("reason", "")),
            "raw_response": text,
        }
    except Exception as exc:
        logger.warning("numeric grounding calculation failed: %s", exc)
        return None, {"verdict": "uncertain", "confidence": 0.0, "reason": str(exc)}


def _resolve_numeric_judgement(
    *,
    equivalence: Optional[float],
    grounding: Optional[float],
    retrieval_support: Optional[float],
    grounding_confidence: float,
) -> Tuple[Optional[str], Optional[float]]:
    if equivalence == 0.0 or grounding == 0.0:
        return "FAIL", max(grounding_confidence, 0.7 if equivalence == 0.0 else 0.6)
    if equivalence == 1.0 and grounding == 1.0 and retrieval_support == 1.0:
        confidence = mean([1.0, 1.0, 1.0, max(grounding_confidence, 0.5)])
        return "PASS", min(confidence, 1.0)
    if equivalence is None and grounding is None:
        return "UNCERTAIN", grounding_confidence if grounding_confidence > 0 else None
    if equivalence == 1.0 and grounding is None:
        return "UNCERTAIN", grounding_confidence if grounding_confidence > 0 else 0.5
    if grounding == 1.0 and equivalence is None:
        return "UNCERTAIN", grounding_confidence if grounding_confidence > 0 else 0.5
    if retrieval_support == 0.0:
        return "FAIL", 0.7
    return "UNCERTAIN", grounding_confidence if grounding_confidence > 0 else None


def _compute_numeric_evaluation(
    *,
    llm: ChatGoogleGenerativeAI,
    example: EvalExample,
    answer: str,
    runtime_evidence: List[Dict[str, Any]],
    retrieval_hit_at_k: float,
) -> Dict[str, Any]:
    equivalence, equivalence_debug = _compute_numeric_equivalence(
        answer=answer,
        answer_key=example.canonical_answer_key,
        canonical_evidence=example.evidence,
    )
    grounding, grounding_debug = _compute_numeric_grounding(
        llm=llm,
        example=example,
        answer=answer,
        runtime_evidence=runtime_evidence,
    )
    retrieval_support = retrieval_hit_at_k
    final_judgement, confidence = _resolve_numeric_judgement(
        equivalence=equivalence,
        grounding=grounding,
        retrieval_support=retrieval_support,
        grounding_confidence=float(grounding_debug.get("confidence", 0.0) or 0.0),
    )
    return {
        "numeric_equivalence": equivalence,
        "numeric_grounding": grounding,
        "numeric_retrieval_support": retrieval_support,
        "numeric_final_judgement": final_judgement,
        "numeric_confidence": confidence,
        "numeric_debug": {
            "equivalence": equivalence_debug,
            "grounding": grounding_debug,
        },
    }


def _expected_sections_for_example(example: EvalExample) -> List[str]:
    sections = list(example.canonical_expected_sections)
    if (example.category or "").lower() == "numeric_fact":
        sections.extend(DEFAULT_NUMERIC_SECTION_ALIASES)

    deduped: List[str] = []
    seen = set()
    for section in sections:
        cleaned = str(section or "").strip()
        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            deduped.append(cleaned)
    return deduped


def _extract_retrieved_metadata(retrieved_docs: List[Any]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for item in retrieved_docs:
        doc = item[0] if isinstance(item, (tuple, list)) else item
        metadata = getattr(doc, "metadata", {}) or {}
        rows.append(
            {
                "company": metadata.get("company"),
                "year": metadata.get("year"),
                "section": metadata.get("section"),
                "section_path": metadata.get("section_path"),
            }
        )
    return rows


def _example_from_dict(item: Dict[str, Any]) -> EvalExample:
    expected_sections = item.get("expected_sections") or item.get("ground_truth_context_ids") or []
    if not isinstance(expected_sections, list):
        expected_sections = [expected_sections]
    evidence_rows = item.get("evidence") or []
    evidence: List[EvalEvidence] = []
    for row in evidence_rows:
        if not isinstance(row, dict):
            continue
        evidence.append(
            EvalEvidence(
                section_path=str(row.get("section_path", "")),
                quote=str(row.get("quote", "")),
                quote_type=str(row.get("quote_type", "verbatim") or "verbatim"),
                why_it_supports_answer=str(row.get("why_it_supports_answer", "")),
            )
        )

    ground_truth_context_ids = item.get("ground_truth_context_ids") or []
    if not isinstance(ground_truth_context_ids, list):
        ground_truth_context_ids = [ground_truth_context_ids]

    ground_truth_evidence_quotes = item.get("ground_truth_evidence_quotes") or []
    if not isinstance(ground_truth_evidence_quotes, list):
        ground_truth_evidence_quotes = [ground_truth_evidence_quotes]

    if not evidence and ground_truth_evidence_quotes:
        fallback_section = str(expected_sections[0] if expected_sections else item.get("section") or "")
        for index, quote in enumerate(ground_truth_evidence_quotes):
            context_id = (
                str(ground_truth_context_ids[index])
                if index < len(ground_truth_context_ids)
                else fallback_section
            )
            evidence.append(
                EvalEvidence(
                    section_path=context_id,
                    quote=str(quote),
                    quote_type="verbatim",
                    why_it_supports_answer="golden dataset evidence quote",
                )
            )

    ground_truth = str(
        item.get("ground_truth")
        or item.get("ground_truth_answer")
        or item.get("answer_key")
        or ""
    )
    answer_key = str(item.get("answer_key") or item.get("ground_truth_answer") or ground_truth)
    section = str(item.get("section") or (expected_sections[0] if expected_sections else ""))
    company = str(item.get("company") or "")
    year = int(item.get("year") or 0)
    aliases = item.get("aliases") or {}
    normalised_aliases: Dict[str, List[str]] = {}
    if isinstance(aliases, dict):
        for alias_key, alias_values in aliases.items():
            if isinstance(alias_values, list):
                normalised_aliases[str(alias_key)] = [str(value) for value in alias_values if str(value).strip()]
            elif alias_values:
                normalised_aliases[str(alias_key)] = [str(alias_values)]
    return EvalExample(
        id=str(item.get("id") or item.get("query_id") or ""),
        question=item["question"],
        ground_truth=ground_truth,
        company=company,
        year=year,
        section=section,
        category=item.get("category"),
        answer_key=answer_key,
        expected_sections=[str(section_value) for section_value in expected_sections if str(section_value).strip()],
        evidence=evidence,
        missing_info_policy=item.get("missing_info_policy"),
        document_id=str(item.get("document_id") or ""),
        ground_truth_context_ids=[str(context_id) for context_id in ground_truth_context_ids if str(context_id).strip()],
        ground_truth_evidence_quotes=[str(quote) for quote in ground_truth_evidence_quotes if str(quote).strip()],
        required_entities=[str(entity) for entity in (item.get("required_entities") or []) if str(entity).strip()],
        answer_type=str(item.get("answer_type") or ""),
        expected_refusal=bool(item.get("expected_refusal", False)),
        numeric_constraints=dict(item.get("numeric_constraints") or {}),
        reasoning_steps=[str(step) for step in (item.get("reasoning_steps") or []) if str(step).strip()],
        aliases=normalised_aliases,
        verification_status=str(item.get("verification_status") or ""),
        notes=str(item.get("notes") or ""),
    )


def load_eval_examples_from_path(dataset_path: str | Path) -> List[EvalExample]:
    with open(dataset_path, encoding="utf-8") as file:
        data = json.load(file)
    return [_example_from_dict(item) for item in data]


def _compute_faithfulness(llm: ChatGoogleGenerativeAI, answer: str, contexts: List[str]) -> float:
    if not answer or not contexts:
        return 0.0

    context_text = "\n\n---\n\n".join(contexts[:8])
    prompt = _FAITHFULNESS_PROMPT.format(context=context_text[:4000], answer=answer[:1500])
    try:
        response = llm.invoke(prompt)
        text = response.content.strip()
        match = re.search(r"(0(?:\.\d+)?|1(?:\.0+)?)", text)
        return float(match.group(1)) if match else 0.5
    except Exception as exc:
        logger.warning("faithfulness calculation failed: %s", exc)
        return 0.5


def _compute_completeness_judge(
    llm: ChatGoogleGenerativeAI,
    example: EvalExample,
    answer: str,
) -> tuple[Optional[float], Optional[str]]:
    if example.expected_refusal:
        return None, None
    if not answer.strip():
        return 0.0, "답변이 비어 있음"

    required_entities = ", ".join(example.required_entities) if example.required_entities else "-"
    prompt = _COMPLETENESS_PROMPT.format(
        question=example.question[:1000],
        answer=answer[:1500],
        answer_key=example.canonical_answer_key[:1000],
        required_entities=required_entities[:500],
    )
    try:
        response = llm.invoke(prompt)
        text = response.content.strip()
        match = re.search(r"\{.*\}", text, re.DOTALL)
        payload = json.loads(match.group(0) if match else text)
        score = payload.get("score")
        score_value = float(score) if score is not None else None
        if score_value is not None:
            score_value = float(np.clip(score_value, 0.0, 1.0))
        return score_value, str(payload.get("reason") or "").strip() or None
    except Exception as exc:
        logger.warning("completeness judge failed: %s", exc)
        return None, None


def _compute_answer_relevancy(
    embeddings: HuggingFaceEmbeddings,
    question: str,
    answer: str,
) -> float:
    if not answer:
        return 0.0

    try:
        q_vec = np.array(embeddings.embed_query(question))
        a_vec = np.array(embeddings.embed_query(answer))
        cosine = np.dot(q_vec, a_vec) / (np.linalg.norm(q_vec) * np.linalg.norm(a_vec) + 1e-9)
        return float(np.clip(cosine, 0.0, 1.0))
    except Exception as exc:
        logger.warning("answer_relevancy calculation failed: %s", exc)
        return 0.5


def _compute_context_recall(example: EvalExample, contexts: List[str]) -> float:
    reference_text = example.recall_reference_text
    if not reference_text or not contexts:
        return 0.0

    context_tokens = _tokenize_ko(" ".join(contexts))
    sentences = re.split(r"[.\n!?]", reference_text)
    sentences = [sentence.strip() for sentence in sentences if len(sentence.strip()) >= 6]
    if not sentences:
        return 0.0

    covered = 0
    for sentence in sentences:
        sentence_tokens = _tokenize_ko(sentence)
        if not sentence_tokens:
            continue
        overlap = sentence_tokens & context_tokens
        if len(overlap) / len(sentence_tokens) >= 0.5:
            covered += 1

    return covered / len(sentences)


def _doc_relevance(example: EvalExample, metadata: Dict[str, Any]) -> int:
    expected_sections = _expected_sections_for_example(example)
    if not expected_sections:
        return 0
    company = str(metadata.get("company", "")).lower()
    year = int(metadata.get("year", 0) or 0)
    if example.company and company != example.company.lower():
        return 0
    if example.year and year != int(example.year):
        return 0
    return int(any(_contains_section(metadata, expected_section) for expected_section in expected_sections))


def _compute_context_precision_at_k(example: EvalExample, retrieved_docs: List[Any], k: int) -> Optional[float]:
    expected_sections = _expected_sections_for_example(example)
    if not expected_sections:
        return None
    top_docs = retrieved_docs[:k]
    if not top_docs:
        return 0.0
    relevant = 0
    for item in top_docs:
        doc = item[0] if isinstance(item, (tuple, list)) else item
        metadata = getattr(doc, "metadata", {}) or {}
        relevant += _doc_relevance(example, metadata)
    return relevant / len(top_docs)


def _compute_ndcg_at_k(example: EvalExample, retrieved_docs: List[Any], k: int) -> Optional[float]:
    expected_sections = _expected_sections_for_example(example)
    if not expected_sections:
        return None
    top_docs = retrieved_docs[:k]
    if not top_docs:
        return 0.0
    relevances: List[int] = []
    for item in top_docs:
        doc = item[0] if isinstance(item, (tuple, list)) else item
        metadata = getattr(doc, "metadata", {}) or {}
        relevances.append(_doc_relevance(example, metadata))
    dcg = 0.0
    for index, rel in enumerate(relevances, start=1):
        if rel:
            dcg += rel / np.log2(index + 1)
    total_relevant = len(example.ground_truth_context_ids) or len(expected_sections)
    ideal_count = min(max(total_relevant, 1), len(top_docs))
    idcg = sum(1.0 / np.log2(index + 1) for index in range(1, ideal_count + 1))
    if idcg == 0.0:
        return 0.0
    return float(dcg / idcg)


def _compute_retrieval_hit_at_k(example: EvalExample, retrieved_docs: List[Any]) -> float:
    expected_company = example.company.lower()
    expected_sections = _expected_sections_for_example(example)
    for item in retrieved_docs:
        doc = item[0] if isinstance(item, (tuple, list)) else item
        metadata = getattr(doc, "metadata", {}) or {}
        company = str(metadata.get("company", "")).lower()
        year = int(metadata.get("year", 0) or 0)
        if (
            company == expected_company
            and year == int(example.year)
            and any(_contains_section(metadata, expected_section) for expected_section in expected_sections)
        ):
            return 1.0
    return 0.0


def _compute_section_match_rate(example: EvalExample, retrieved_docs: List[Any]) -> float:
    if not retrieved_docs:
        return 0.0
    expected_sections = _expected_sections_for_example(example)
    matched = 0
    for item in retrieved_docs:
        doc = item[0] if isinstance(item, (tuple, list)) else item
        metadata = getattr(doc, "metadata", {}) or {}
        if any(_contains_section(metadata, expected_section) for expected_section in expected_sections):
            matched += 1
    return matched / len(retrieved_docs)


def _compute_citation_coverage(example: EvalExample, citations: List[str]) -> float:
    if not citations:
        return 0.0

    citation_blob = " ".join(citations).lower()
    expected_sections = _expected_sections_for_example(example)
    checks = [
        example.company.lower() in citation_blob,
        str(example.year) in citation_blob,
        any(expected_section.lower() in citation_blob for expected_section in expected_sections),
    ]
    return sum(1.0 for matched in checks if matched) / len(checks)


def _compact_text_preview(text: str, limit: int = 220) -> str:
    flattened = " ".join((text or "").split())
    if len(flattened) <= limit:
        return flattened
    return flattened[: max(limit - 3, 0)].rstrip() + "..."


def _extract_retrieved_previews(retrieved_docs: List[Any], limit: int = 8, chars: int = 220) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for item in retrieved_docs[:limit]:
        doc = item[0] if isinstance(item, (tuple, list)) else item
        metadata = getattr(doc, "metadata", {}) or {}
        text = getattr(doc, "content", None) or getattr(doc, "page_content", "")
        rows.append(
            {
                "company": metadata.get("company"),
                "year": metadata.get("year"),
                "section": metadata.get("section"),
                "section_path": metadata.get("section_path"),
                "block_type": metadata.get("block_type"),
                "graph_relation": metadata.get("graph_relation"),
                "preview": _compact_text_preview(text, limit=chars),
            }
        )
    return rows


def _entity_aliases(example: EvalExample, entity: str) -> List[str]:
    values = [entity]
    alias_values = example.aliases.get(entity, [])
    for value in alias_values:
        if value not in values:
            values.append(value)
    return [str(value).strip() for value in values if str(value).strip()]


def _contains_entity_variant(text: str, variants: List[str]) -> bool:
    lowered = (text or "").lower()
    return any(variant.lower() in lowered for variant in variants)


def _compute_entity_coverage(example: EvalExample, contexts: List[str]) -> Optional[float]:
    if not example.required_entities:
        return None
    context_blob = "\n".join(contexts)
    covered = 0
    for entity in example.required_entities:
        variants = _entity_aliases(example, entity)
        if _contains_entity_variant(context_blob, variants):
            covered += 1
    return covered / len(example.required_entities)


def _compute_completeness(example: EvalExample, answer: str) -> Optional[float]:
    if example.expected_refusal:
        return None
    if not answer.strip():
        return 0.0
    if not example.required_entities:
        if example.answer_type == "numeric":
            return 1.0 if _extract_numeric_candidates(answer) else 0.0
        return None
    covered = 0
    for entity in example.required_entities:
        variants = _entity_aliases(example, entity)
        if _contains_entity_variant(answer, variants):
            covered += 1
    entity_score = covered / len(example.required_entities)
    if example.answer_type == "numeric":
        numeric_score = 1.0 if _extract_numeric_candidates(answer) else 0.0
        return max(entity_score, numeric_score)
    return entity_score


def _should_override_numeric_faithfulness(numeric_eval: Dict[str, Any]) -> bool:
    if not numeric_eval:
        return False
    return (
        numeric_eval.get("numeric_final_judgement") == "PASS"
        and numeric_eval.get("numeric_equivalence") == 1.0
        and numeric_eval.get("numeric_grounding") == 1.0
        and numeric_eval.get("numeric_retrieval_support") == 1.0
    )


def _compute_missing_info_compliance(example: EvalExample, answer: str) -> Optional[float]:
    category = (example.category or "").lower()
    if category != "missing_information":
        return None
    lowered = (answer or "").lower()
    if not lowered.strip():
        return 0.0
    if _looks_like_missing_answer(lowered):
        return 1.0
    if example.missing_info_policy:
        policy_tokens = _tokenize_ko(example.missing_info_policy)
        answer_tokens = _tokenize_ko(answer)
        if policy_tokens and len(policy_tokens & answer_tokens) / len(policy_tokens) >= 0.25:
            return 1.0
    return 0.0


def _compute_refusal_accuracy(example: EvalExample, answer: str) -> Optional[float]:
    if not answer.strip():
        return 0.0 if example.expected_refusal else 0.0
    looks_missing = _looks_like_missing_answer(answer)
    if example.expected_refusal:
        return 1.0 if looks_missing else 0.0
    if looks_missing:
        return 0.0
    return 1.0


def _compute_absolute_error_rate(
    answer: str,
    answer_key: str,
    canonical_evidence: List[EvalEvidence],
) -> Optional[float]:
    answer_candidates = _extract_numeric_candidates(answer)
    reference_candidates = _extract_numeric_candidates(answer_key)
    for evidence in canonical_evidence:
        reference_candidates.extend(_extract_numeric_candidates(evidence.quote))
    if not answer_candidates or not reference_candidates:
        return None
    best_error: Optional[float] = None
    for answer_candidate in answer_candidates:
        left = _safe_float(answer_candidate.get("normalized_value"))
        if left is None:
            continue
        for reference_candidate in reference_candidates:
            if answer_candidate.get("kind") != reference_candidate.get("kind"):
                continue
            right = _safe_float(reference_candidate.get("normalized_value"))
            if right is None:
                continue
            denominator = max(abs(right), 1.0)
            error = abs(left - right) / denominator
            if best_error is None or error < best_error:
                best_error = error
    return best_error


def _compute_calculation_correctness(
    example: EvalExample,
    numeric_equivalence: Optional[float],
    absolute_error_rate: Optional[float],
) -> Optional[float]:
    if (example.category or "").lower() != "multi-hop-calculation":
        return None
    if numeric_equivalence is not None:
        return float(numeric_equivalence)
    if absolute_error_rate is None:
        return None
    tolerance = float(example.numeric_constraints.get("tolerance", 0.0) or 0.0)
    return 1.0 if absolute_error_rate <= tolerance else 0.0


class RAGEvaluator:
    def __init__(
        self,
        agent,
        dataset_path: Optional[str] = None,
        experiment_name: str = "dart_rag_eval",
    ):
        self.agent = agent
        self.experiment_name = experiment_name
        self._dataset_path = Path(dataset_path) if dataset_path else _DEFAULT_DATASET
        self._llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0.0)
        self._embeddings = HuggingFaceEmbeddings(model_name=DEFAULT_EMBEDDING_MODEL)

    def load_dataset(self) -> List[EvalExample]:
        return load_eval_examples_from_path(self._dataset_path)

    def build_single_company_eval_slice(
        self,
        examples: Optional[List[EvalExample]] = None,
        max_questions: int = 5,
    ) -> List[EvalExample]:
        if examples is None:
            examples = self.load_dataset()

        buckets = {
            "numeric_fact": None,
            "risk_analysis": None,
            "business_overview": None,
            "r_and_d_investment": None,
            "missing_information": None,
        }

        for example in examples:
            question = example.question.lower()
            section = example.section.lower()
            category = (example.category or "").lower()

            if buckets["numeric_fact"] is None and (
                category == "numeric_fact"
                or any(term in question for term in ("매출", "영업이익", "부채", "수치", "금액"))
            ):
                buckets["numeric_fact"] = example
            elif buckets["risk_analysis"] is None and (
                category == "risk_analysis" or "리스크" in section or "위험" in question
            ):
                buckets["risk_analysis"] = example
            elif buckets["business_overview"] is None and (
                category == "business_overview" or "사업개요" in section or "사업" in question
            ):
                buckets["business_overview"] = example
            elif buckets["r_and_d_investment"] is None and (
                category == "r_and_d_investment"
                or "연구개발" in section
                or any(term in question for term in ("r&d", "연구개발", "투자"))
            ):
                buckets["r_and_d_investment"] = example
            elif buckets["missing_information"] is None and (
                category == "missing_information"
                or any(term in question for term in ("없", "확인되지", "공시 문서에서"))
            ):
                buckets["missing_information"] = example

        selected = [example for example in buckets.values() if example is not None]
        if len(selected) < max_questions:
            seen_ids = {example.id for example in selected}
            for example in examples:
                if example.id in seen_ids:
                    continue
                selected.append(example)
                seen_ids.add(example.id)
                if len(selected) >= max_questions:
                    break

        return selected[:max_questions]

    def evaluate_one(self, example: EvalExample) -> EvalResult:
        started_at = time.time()
        error = None
        answer = ""
        contexts: List[str] = []
        query_type = "unknown"
        retrieved_docs: List[Any] = []
        citations: List[str] = []
        runtime_evidence: List[Dict[str, Any]] = []
        selected_claim_ids: List[str] = []
        draft_points: List[str] = []
        kept_claim_ids: List[str] = []
        dropped_claim_ids: List[str] = []
        unsupported_sentences: List[str] = []
        sentence_checks: List[Dict[str, Any]] = []

        try:
            result = self.agent.run(example.question)
            answer = result.get("answer", "")
            query_type = result.get("query_type", "unknown")
            retrieved_docs = result.get("retrieved_docs", [])
            citations = result.get("citations", [])
            runtime_evidence = result.get("evidence_items", []) or []
            selected_claim_ids = result.get("selected_claim_ids", []) or []
            draft_points = result.get("draft_points", []) or []
            kept_claim_ids = result.get("kept_claim_ids", []) or []
            dropped_claim_ids = result.get("dropped_claim_ids", []) or []
            unsupported_sentences = result.get("unsupported_sentences", []) or []
            sentence_checks = result.get("sentence_checks", []) or []
            for item in retrieved_docs:
                doc = item[0] if isinstance(item, (tuple, list)) else item
                contexts.append(getattr(doc, "content", None) or getattr(doc, "page_content", ""))
        except Exception as exc:
            error = str(exc)
            logger.error("[%s] agent.run failed: %s", example.id, exc)

        latency = time.time() - started_at

        raw_faithfulness = _compute_faithfulness(self._llm, answer, contexts)
        faithfulness = raw_faithfulness
        faithfulness_override_reason = None
        answer_relevancy = _compute_answer_relevancy(self._embeddings, example.question, answer)
        context_recall = _compute_context_recall(example, contexts)
        retrieval_hit_at_k = _compute_retrieval_hit_at_k(example, retrieved_docs)
        section_match_rate = _compute_section_match_rate(example, retrieved_docs)
        citation_coverage = _compute_citation_coverage(example, citations)
        missing_info_compliance = _compute_missing_info_compliance(example, answer)
        numeric_eval: Dict[str, Any] = {}

        if (example.answer_type or "").lower() == "numeric" or (example.category or "").lower() == "numeric_fact":
            numeric_eval = _compute_numeric_evaluation(
                llm=self._llm,
                example=example,
                answer=answer,
                runtime_evidence=runtime_evidence,
                retrieval_hit_at_k=retrieval_hit_at_k,
            )
            if _should_override_numeric_faithfulness(numeric_eval):
                faithfulness = 1.0
                faithfulness_override_reason = (
                    "numeric evaluator PASS (equivalence/grounding/retrieval_support 모두 1.0)로 faithfulness를 1.0으로 보정"
                )

        ndcg_at_3 = _compute_ndcg_at_k(example, retrieved_docs, 3)
        ndcg_at_5 = _compute_ndcg_at_k(example, retrieved_docs, 5)
        context_precision_at_3 = _compute_context_precision_at_k(example, retrieved_docs, 3)
        context_precision_at_5 = _compute_context_precision_at_k(example, retrieved_docs, 5)
        entity_coverage = _compute_entity_coverage(example, contexts)
        completeness, completeness_reason = _compute_completeness_judge(self._llm, example, answer)
        if completeness is None:
            completeness = _compute_completeness(example, answer)
            if completeness is not None and completeness_reason is None:
                completeness_reason = "heuristic completeness fallback"
        refusal_accuracy = _compute_refusal_accuracy(example, answer)
        absolute_error_rate = _compute_absolute_error_rate(
            answer=answer,
            answer_key=example.canonical_answer_key,
            canonical_evidence=example.evidence,
        )
        calculation_correctness = _compute_calculation_correctness(
            example=example,
            numeric_equivalence=numeric_eval.get("numeric_equivalence"),
            absolute_error_rate=absolute_error_rate,
        )

        if _looks_like_full_abstention_answer(answer) and (example.category or "").lower() != "missing_information":
            # Penalize abstentions on answerable questions even when the judge model is lenient.
            faithfulness = 0.0
            faithfulness_override_reason = "answerable question에 대한 full abstention으로 faithfulness를 0.0으로 강등"
            answer_relevancy = min(answer_relevancy, 0.1)

        return EvalResult(
            id=example.id,
            question=example.question,
            answer=answer,
            ground_truth=example.ground_truth,
            answer_key=example.canonical_answer_key,
            expected_sections=example.canonical_expected_sections,
            evidence=[
                {
                    "section_path": evidence.section_path,
                    "quote": evidence.quote,
                    "quote_type": evidence.quote_type,
                    "why_it_supports_answer": evidence.why_it_supports_answer,
                }
                for evidence in example.evidence
            ],
            raw_faithfulness=raw_faithfulness,
            faithfulness=faithfulness,
            faithfulness_override_reason=faithfulness_override_reason,
            answer_relevancy=answer_relevancy,
            context_recall=context_recall,
            retrieval_hit_at_k=retrieval_hit_at_k,
            ndcg_at_3=ndcg_at_3,
            ndcg_at_5=ndcg_at_5,
            context_precision_at_3=context_precision_at_3,
            context_precision_at_5=context_precision_at_5,
            section_match_rate=section_match_rate,
            citation_coverage=citation_coverage,
            entity_coverage=entity_coverage,
            completeness=completeness,
            completeness_reason=completeness_reason,
            missing_info_compliance=missing_info_compliance,
            refusal_accuracy=refusal_accuracy,
            absolute_error_rate=absolute_error_rate,
            calculation_correctness=calculation_correctness,
            retrieved_count=len(contexts),
            query_type=query_type,
            latency_sec=latency,
            citations=citations,
            retrieved_metadata=_extract_retrieved_metadata(retrieved_docs),
            retrieved_previews=_extract_retrieved_previews(retrieved_docs),
            runtime_evidence=runtime_evidence,
            selected_claim_ids=selected_claim_ids,
            draft_points=draft_points,
            kept_claim_ids=kept_claim_ids,
            dropped_claim_ids=dropped_claim_ids,
            unsupported_sentences=unsupported_sentences,
            sentence_checks=sentence_checks,
            numeric_equivalence=numeric_eval.get("numeric_equivalence"),
            numeric_grounding=numeric_eval.get("numeric_grounding"),
            numeric_retrieval_support=numeric_eval.get("numeric_retrieval_support"),
            numeric_final_judgement=numeric_eval.get("numeric_final_judgement"),
            numeric_confidence=numeric_eval.get("numeric_confidence"),
            numeric_debug=numeric_eval.get("numeric_debug", {}),
            missing_info_policy=example.missing_info_policy,
            error=error,
        )

    def run(
        self,
        examples: Optional[List[EvalExample]] = None,
        run_name: Optional[str] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        if examples is None:
            examples = self.load_dataset()

        mlflow.set_experiment(self.experiment_name)

        with mlflow.start_run(run_name=run_name):
            if params:
                mlflow.log_params(params)
            mlflow.log_param("n_questions", len(examples))

            results: List[EvalResult] = []
            for index, example in enumerate(examples, 1):
                logger.info("Evaluating [%s/%s] %s", index, len(examples), example.id)
                result = self.evaluate_one(example)
                results.append(result)
                metrics = {
                    "faithfulness": result.faithfulness,
                    "answer_relevancy": result.answer_relevancy,
                    "context_recall": result.context_recall,
                    "retrieval_hit_at_k": result.retrieval_hit_at_k,
                    "ndcg_at_3": result.ndcg_at_3 or 0.0,
                    "ndcg_at_5": result.ndcg_at_5 or 0.0,
                    "context_precision_at_3": result.context_precision_at_3 or 0.0,
                    "context_precision_at_5": result.context_precision_at_5 or 0.0,
                    "section_match_rate": result.section_match_rate,
                    "citation_coverage": result.citation_coverage,
                    "entity_coverage": result.entity_coverage or 0.0,
                    "completeness": result.completeness or 0.0,
                    "refusal_accuracy": result.refusal_accuracy or 0.0,
                    "latency_sec": result.latency_sec,
                }
                if result.numeric_equivalence is not None:
                    metrics["numeric_equivalence"] = result.numeric_equivalence
                if result.numeric_grounding is not None:
                    metrics["numeric_grounding"] = result.numeric_grounding
                if result.numeric_retrieval_support is not None:
                    metrics["numeric_retrieval_support"] = result.numeric_retrieval_support
                if result.numeric_confidence is not None:
                    metrics["numeric_confidence"] = result.numeric_confidence
                mlflow.log_metrics(metrics, step=index)

            valid_results = [result for result in results if result.error is None]
            error_rate = (len(results) - len(valid_results)) / len(results) if results else 0.0

            def _average(attr: str) -> float:
                values = [getattr(result, attr) for result in valid_results]
                return float(np.mean(values)) if values else 0.0

            def _average_optional(attr: str) -> Optional[float]:
                values = [getattr(result, attr) for result in valid_results if getattr(result, attr) is not None]
                return float(np.mean(values)) if values else None

            numeric_results = [
                result
                for result in valid_results
                if (result.numeric_final_judgement or "").strip()
            ]
            numeric_pass_rate = (
                sum(1.0 for result in numeric_results if result.numeric_final_judgement == "PASS") / len(numeric_results)
                if numeric_results
                else None
            )
            numeric_uncertain_rate = (
                sum(1.0 for result in numeric_results if result.numeric_final_judgement == "UNCERTAIN") / len(numeric_results)
                if numeric_results
                else None
            )

            aggregate = {
                "faithfulness": _average("faithfulness"),
                "answer_relevancy": _average("answer_relevancy"),
                "context_recall": _average("context_recall"),
                "retrieval_hit_at_k": _average("retrieval_hit_at_k"),
                "ndcg_at_3": _average_optional("ndcg_at_3"),
                "ndcg_at_5": _average_optional("ndcg_at_5"),
                "context_precision_at_3": _average_optional("context_precision_at_3"),
                "context_precision_at_5": _average_optional("context_precision_at_5"),
                "section_match_rate": _average("section_match_rate"),
                "citation_coverage": _average("citation_coverage"),
                "entity_coverage": _average_optional("entity_coverage"),
                "completeness": _average_optional("completeness"),
                "refusal_accuracy": _average_optional("refusal_accuracy"),
                "numeric_equivalence": _average_optional("numeric_equivalence"),
                "numeric_grounding": _average_optional("numeric_grounding"),
                "numeric_retrieval_support": _average_optional("numeric_retrieval_support"),
                "numeric_confidence": _average_optional("numeric_confidence"),
                "absolute_error_rate": _average_optional("absolute_error_rate"),
                "calculation_correctness": _average_optional("calculation_correctness"),
                "numeric_pass_rate": numeric_pass_rate,
                "numeric_uncertain_rate": numeric_uncertain_rate,
                "avg_score": _average("aggregate_score"),
                "avg_latency": _average("latency_sec"),
                "error_rate": error_rate,
            }
            mlflow.log_metrics({"agg_" + key: value for key, value in aggregate.items() if value is not None})

            artifact_path = _PROJECT_ROOT / "mlruns" / "_eval_artifact_tmp.json"
            artifact_path.parent.mkdir(parents=True, exist_ok=True)
            with open(artifact_path, "w", encoding="utf-8") as file:
                json.dump(
                    [
                        {
                            "id": result.id,
                            "question": result.question,
                            "answer_key": result.answer_key,
                            "answer": result.answer[:500],
                            "faithfulness": result.faithfulness,
                            "answer_relevancy": result.answer_relevancy,
                            "context_recall": result.context_recall,
                            "retrieval_hit_at_k": result.retrieval_hit_at_k,
                            "ndcg_at_3": result.ndcg_at_3,
                            "ndcg_at_5": result.ndcg_at_5,
                            "context_precision_at_3": result.context_precision_at_3,
                            "context_precision_at_5": result.context_precision_at_5,
                            "section_match_rate": result.section_match_rate,
                            "citation_coverage": result.citation_coverage,
                            "entity_coverage": result.entity_coverage,
                            "completeness": result.completeness,
                            "refusal_accuracy": result.refusal_accuracy,
                            "numeric_equivalence": result.numeric_equivalence,
                            "numeric_grounding": result.numeric_grounding,
                            "numeric_retrieval_support": result.numeric_retrieval_support,
                            "numeric_final_judgement": result.numeric_final_judgement,
                            "numeric_confidence": result.numeric_confidence,
                            "absolute_error_rate": result.absolute_error_rate,
                            "calculation_correctness": result.calculation_correctness,
                            "missing_info_compliance": result.missing_info_compliance,
                            "latency_sec": result.latency_sec,
                            "query_type": result.query_type,
                            "error": result.error,
                        }
                        for result in results
                    ],
                    file,
                    ensure_ascii=False,
                    indent=2,
                )
            mlflow.log_artifact(str(artifact_path), artifact_path="eval_results")
            artifact_path.unlink(missing_ok=True)

            logger.info(
                "\n=== Evaluation complete (%s questions) ===\n"
                "  Faithfulness     : %.3f\n"
                "  Answer Relevancy : %.3f\n"
                "  Context Recall   : %.3f\n"
                "  Retrieval Hit@k  : %.3f\n"
                "  NDCG@5           : %s\n"
                "  Context P@5      : %s\n"
                "  Section Match    : %.3f\n"
                "  Citation Coverage: %.3f\n"
                "  Entity Coverage  : %s\n"
                "  Completeness     : %s\n"
                "  Refusal Accuracy : %s\n"
                "  Numeric Pass Rate: %s\n"
                "  Avg Score        : %.3f\n"
                "  Error Rate       : %.1f%%",
                len(results),
                aggregate["faithfulness"],
                aggregate["answer_relevancy"],
                aggregate["context_recall"],
                aggregate["retrieval_hit_at_k"],
                "-" if aggregate["ndcg_at_5"] is None else f"{aggregate['ndcg_at_5']:.3f}",
                "-" if aggregate["context_precision_at_5"] is None else f"{aggregate['context_precision_at_5']:.3f}",
                aggregate["section_match_rate"],
                aggregate["citation_coverage"],
                "-" if aggregate["entity_coverage"] is None else f"{aggregate['entity_coverage']:.3f}",
                "-" if aggregate["completeness"] is None else f"{aggregate['completeness']:.3f}",
                "-" if aggregate["refusal_accuracy"] is None else f"{aggregate['refusal_accuracy']:.3f}",
                "-" if aggregate["numeric_pass_rate"] is None else f"{aggregate['numeric_pass_rate']:.3f}",
                aggregate["avg_score"],
                aggregate["error_rate"] * 100,
            )

        return {"aggregate": aggregate, "per_question": results}


if __name__ == "__main__":
    import glob
    import sys

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

    sys.path.insert(0, str(_PROJECT_ROOT / "src"))
    from agent.financial_graph import FinancialAgent
    from processing.financial_parser import FinancialParser
    from storage.vector_store import VectorStoreManager

    chroma_path = str(_PROJECT_ROOT / "data" / "chroma_dart")
    vsm = VectorStoreManager(persist_directory=chroma_path, collection_name=DEFAULT_COLLECTION_NAME)

    if len(vsm.bm25_docs) == 0:
        print("[INFO] ChromaDB is empty. Indexing local filings first...")
        reports = glob.glob(str(_PROJECT_ROOT / "data" / "reports" / "**" / "*.html"), recursive=True)
        if not reports:
            print("[ERROR] No .html file found under data/reports/. Run dart_fetcher.py first.")
            sys.exit(1)

        parser = FinancialParser(chunk_size=1500, chunk_overlap=200)
        agent_tmp = FinancialAgent(vsm)
        for file_path in reports:
            parts = Path(file_path).stem.split("_")
            metadata = {
                "company": Path(file_path).parent.name,
                "stock_code": "unknown",
                "year": int(parts[0]) if parts[0].isdigit() else 2023,
                "report_type": parts[1] if len(parts) > 1 else "사업보고서",
                "rcept_no": parts[-1] if len(parts) > 2 else "unknown",
            }
            chunks = parser.process_document(file_path, metadata)
            agent_tmp.ingest(chunks)
            print(f"  indexed: {Path(file_path).name} ({len(chunks)} chunks)")
    else:
        print(f"[INFO] Using existing ChromaDB with {len(vsm.bm25_docs)} chunks")

    agent = FinancialAgent(vsm, k=8)
    evaluator = RAGEvaluator(agent)

    dataset = evaluator.load_dataset()
    smoke_set = evaluator.build_single_company_eval_slice(dataset, max_questions=5)

    print(f"\n=== RAGEvaluator smoke test ({len(smoke_set)} questions) ===\n")
    results = evaluator.run(
        examples=smoke_set,
        run_name="single_company_smoke_test",
        params={
            "chunk_size": 1500,
            "k": 8,
            "strategy": "hybrid_rerank",
            "embedding_model": DEFAULT_EMBEDDING_MODEL,
            "collection_name": DEFAULT_COLLECTION_NAME,
        },
    )

    print("\n[Per-question]")
    for result in results["per_question"]:
        print(
            f"  {result.id:15s} | F={result.faithfulness:.2f} "
            f"R={result.answer_relevancy:.2f} C={result.context_recall:.2f} "
            f"Hit@k={result.retrieval_hit_at_k:.2f} "
            f"Sec={result.section_match_rate:.2f} "
            f"Cite={result.citation_coverage:.2f} "
            f"| {result.latency_sec:.1f}s"
            + (f" ERROR: {result.error}" if result.error else "")
        )

    aggregate = results["aggregate"]
    print(
        "\nAggregate: "
        f"Faithfulness={aggregate['faithfulness']:.3f}, "
        f"Relevancy={aggregate['answer_relevancy']:.3f}, "
        f"Recall={aggregate['context_recall']:.3f}, "
        f"Hit@k={aggregate['retrieval_hit_at_k']:.3f}, "
        f"Section={aggregate['section_match_rate']:.3f}, "
        f"Citation={aggregate['citation_coverage']:.3f}, "
        f"Avg={aggregate['avg_score']:.3f}"
    )
    print("\nMLflow UI: mlflow ui --backend-store-uri mlruns/")
