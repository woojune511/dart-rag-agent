from __future__ import annotations

from typing import Any, Dict, Iterable, List, Sequence


QUERY_FOCUS_STOPWORDS = frozenset(
    {
        "2021년",
        "2022년",
        "2023년",
        "2024년",
        "2025년",
        "2026년",
        "사업보고서",
        "재무제표",
        "연결",
        "별도",
        "바탕",
        "기준",
        "또는",
        "등",
        "주석",
        "현황",
        "상세",
        "부문",
        "사업",
        "기술",
        "관련",
        "질문",
        "배경",
        "영향",
        "원인",
        "요약",
        "요약해",
        "요약해줘",
        "정리",
        "정리해",
        "정리해줘",
        "추출",
        "추출하고",
        "찾고",
        "계산",
        "계산하고",
        "분석",
        "분석해",
        "총액",
        "규모",
        "전년",
        "대비",
        "성장률",
        "판매대수",
        "시장",
        "필요성",
        "대한",
        "정책",
        "정책에",
        "주요",
        "초점",
        "방향",
        "비용",
        "수치",
        "정보",
    }
)


SECTION_BIAS_BY_QUERY_TYPE = {
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
        ("IV. 이사의 경영진단 및 분석의견", 0.10),
        ("경영진단", 0.08),
        ("사업의 개요", 0.06),
    ),
    "risk": (
        ("IV. 이사의 경영진단 및 분석의견", 0.18),
        ("경영진단", 0.12),
        ("위험관리 및 파생거래", 0.18),
        ("리스크", 0.10),
    ),
    "risk_analysis": (
        ("IV. 이사의 경영진단 및 분석의견", 0.18),
        ("경영진단", 0.12),
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


ROUTING_CALC_GUARDRAIL_ENABLED = True
ROUTING_CALC_GUARDRAIL_OPERATION_TERMS = frozenset(
    {
        "계산",
        "계산해",
        "산출",
        "구해",
        "이용해",
        "나누",
        "차감",
        "더해",
        "빼",
        "합산",
        "총합",
        "차지하는",
        "대비",
        "증감",
        "증가율",
        "감소율",
    }
)


NARRATIVE_BASE_RETRIEVAL_SUFFIXES = (
    "원인 배경 영향 설명",
    "경영진단 사업의 내용",
)

NARRATIVE_BASE_PREFERRED_SECTIONS = (
    "IV. 이사의 경영진단 및 분석의견",
    "II. 사업의 내용",
    "사업의 개요",
    "나. 영업실적",
)

NARRATIVE_BASE_PARAGRAPH_PRIORITY_SECTIONS = (
    "나. 영업실적",
)

QUANTITATIVE_IMPACT_QUERY_TERMS = ("영향", "분석", "비중", "대비", "차지")


NARRATIVE_RETRIEVAL_POLICIES: tuple[Dict[str, Any], ...] = (
    {
        "name": "impact_context",
        "trigger_terms": ("영향", "기여", "원인", "요약", "인수"),
        "retrieval_query_suffixes": (
            "연결 편입 효과 성장 기여",
            "연결 편입효과 영업수익 증가",
        ),
        "preferred_sections": (
            "IV. 이사의 경영진단 및 분석의견",
            "재무상태 및 영업실적",
            "나. 영업실적",
        ),
        "focus_terms": ("영향", "기여", "편입효과", "성장", "인수", "연결 편입"),
        "causal_terms": ("영향", "기여", "편입효과", "성장", "인수", "연결 편입"),
        "realized_terms": ("전년 대비", "연결 편입", "편입효과"),
        "penalty_terms": (
            "주요계약 및 연구개발활동",
            "경영상의 주요 계약",
            "계약의 목적 및 내용",
            "예상효과",
        ),
    },
    {
        "name": "investment_entity_summary",
        "trigger_terms": (
            "타법인출자",
            "지분율",
            "소유지분율",
            "투자장부금액",
            "장부금액",
            "투자자산",
            "공동기업",
            "관계기업",
            "요약 손익",
            "총포괄손익",
        ),
        "retrieval_query_suffixes": (
            "타법인출자 현황 상세",
            "공동기업 관계기업 투자자산 지분율 장부금액",
            "공동기업 관계기업 요약 손익 계속영업손익 총포괄손익",
            "연결재무제표 주석 재무제표 주석",
        ),
        "preferred_sections": (
            "III. 재무에 관한 사항 > 3. 연결재무제표 주석",
            "III. 재무에 관한 사항 > 5. 재무제표 주석",
            "XII. 상세표 > 3. 타법인출자 현황(상세)",
            "연결재무제표 주석",
            "재무제표 주석",
            "타법인출자 현황",
        ),
        "focus_terms": (
            "타법인출자",
            "지분율",
            "투자장부금액",
            "투자자산",
            "계속영업손익",
            "총포괄손익",
        ),
        "entity_metric_slot_groups": (
            {
                "name": "ownership_investment_balance",
                "query_terms": ("지분율", "소유지분율", "투자장부금액", "장부금액", "투자자산"),
                "evidence_terms": ("지분율", "소유지분율", "투자장부금액", "장부금액", "투자자산"),
                "preferred_consolidation_scopes": ("separate",),
                "preferred_section_markers": ("III. 재무에 관한 사항 > 5. 재무제표 주석",),
            },
            {
                "name": "summary_profit_loss",
                "query_terms": ("요약 손익", "요약손익", "손익", "계속영업", "총포괄손익", "총포괄손실"),
                "evidence_terms": (
                    "계속영업",
                    "계속영업이익",
                    "계속영업손실",
                    "영업수익",
                    "총포괄손익",
                    "총포괄손실",
                ),
                "preferred_consolidation_scopes": ("consolidated",),
                "preferred_section_markers": ("III. 재무에 관한 사항 > 3. 연결재무제표 주석",),
            },
        ),
        "causal_terms": (),
        "realized_terms": (),
    },
    {
        "name": "commerce_growth",
        "trigger_terms": ("커머스", "쇼핑"),
        "focus_terms": ("커머스", "쇼핑", "스마트스토어", "브랜드스토어"),
        "causal_terms": ("브랜드스토어", "스마트스토어"),
        "realized_terms": ("스마트스토어", "브랜드스토어"),
        "driver_groups": (
            {
                "label": "store_growth",
                "variants": ("스마트스토어", "브랜드스토어"),
                "phrase": "스마트스토어와 브랜드스토어의 성장",
            },
        ),
    },
    {
        "name": "acquisition_turnaround",
        "trigger_terms": ("포시마크", "Poshmark", "poshmark"),
        "retrieval_query_suffixes": ("Poshmark 연결 편입효과 영업수익 증가",),
        "focus_terms": ("poshmark", "체질 개선", "연결 편입", "편입효과"),
        "causal_terms": ("체질 개선", "연결 편입", "편입효과"),
        "realized_terms": ("연결 편입", "편입효과", "체질 개선"),
        "driver_groups": (
            {"label": "turnaround", "variants": ("체질 개선",), "phrase": "체질 개선"},
            {
                "label": "consolidation_effect",
                "variants": ("연결 편입효과", "연결 편입 효과", "연결 편입", "편입효과"),
                "phrase": "연결 편입 효과",
            },
        ),
    },
    {
        "name": "dividend_policy",
        "trigger_terms": ("배당", "주주환원", "정규배당", "잉여현금흐름", "환원 정책", "추가 환원"),
        "retrieval_query_suffixes": (
            "배당에 관한 사항 주주환원 정책",
            "잉여현금흐름 정규배당 추가 환원",
            "유동성 및 자금조달 배당금 지급",
        ),
        "preferred_sections": (
            "III. 재무에 관한 사항 > 6. 배당에 관한 사항",
            "IV. 이사의 경영진단 및 분석의견 > 유동성 및 자금조달",
            "배당에 관한 사항",
            "유동성 및 자금조달",
        ),
        "paragraph_priority_sections": ("유동성 및 자금조달",),
        "focus_terms": ("배당금 지급", "주주환원", "정규배당", "잉여현금흐름", "추가 환원"),
        "causal_terms": ("주주환원", "정규배당", "잉여현금흐름", "추가 환원", "배당금 지급"),
        "payout_terms": ("배당금 지급",),
        "payout_deemphasis_terms": ("배당금의 지급",),
        "policy_terms": ("주주환원", "정규배당", "잉여현금흐름", "추가 환원"),
        "regular_terms": ("정규배당",),
        "additional_return_terms": ("추가 환원", "추가로 환원"),
        "policy_query_terms": (
            "주주환원 정책",
            "배당에 관한 사항",
            "정규배당",
            "추가 환원",
            "잉여현금흐름",
        ),
        "policy_preferred_terms": (
            "정규배당",
            "추가 환원",
            "추가로 환원",
            "잉여현금흐름",
            "주주환원 정책",
        ),
        "liquidity_context_terms": ("유동성", "현금흐름"),
        "outflow_terms": ("유출",),
        "table_policy_terms": ("현금배당금총액", "배당성향"),
        "policy_section_terms": ("배당에 관한 사항",),
    },
    {
        "name": "technology_focus",
        "trigger_terms": ("사업 방향", "기술 초점", "전장", "SDV"),
        "preferred_sections": ("기타 참고사항", "사업부문별 현황"),
        "paragraph_priority_sections": ("기타 참고사항", "사업부문별 현황"),
        "focus_terms": ("전장", "sdv", "software defined vehicle", "커넥티드카", "connected car"),
        "technology_terms": (
            "sdv",
            "software defined vehicle",
            "전장사업",
            "무선통신",
            "it 기술",
            "차별화된 기술",
        ),
        "technology_facets": (
            {
                "name": "connected_solution",
                "match_terms": ("커넥티드카 제품 및 솔루션", "커넥티드카", "connected car"),
                "business_phrase": "커넥티드카 제품 및 솔루션을 디자인하고 개발하는 전장부품 사업",
            },
            {
                "name": "digital_cockpit",
                "match_terms": ("디지털 콕핏", "Digital Cockpit"),
                "product_phrase": "디지털 콕핏",
            },
            {
                "name": "car_audio",
                "match_terms": ("카 오디오", "카오디오"),
                "product_phrase": "카오디오",
            },
            {
                "name": "it_technology",
                "required_terms": ("무선통신", "디스플레이"),
                "match_terms": ("IT 기술",),
                "focus_phrase": "무선통신, 디스플레이 등 IT 기술을 전장사업에 지속 접목해 차량의 IT기기화에 대응",
            },
            {
                "name": "sdv",
                "match_terms": ("SDV", "Software Defined Vehicle"),
                "focus_phrase": "SDV(Software Defined Vehicle) 전환에 맞춘 차별화된 기술 개발",
            },
        ),
        "driver_groups": (
            {
                "label": "automotive_sdv_focus",
                "variants": ("SDV", "Software Defined Vehicle"),
                "phrase": "",
            },
            {
                "label": "automotive_it_technology",
                "variants": ("무선통신", "디스플레이", "IT 기술", "차별화된 기술"),
                "phrase": "",
            },
        ),
    },
    {
        "name": "policy_context",
        "trigger_terms": ("보호무역주의", "대응", "IRA", "인플레이션 감축법"),
        "focus_terms": ("보호무역주의", "대응", "ira", "인플레이션 감축법", "핵심원자재법"),
        "query_terms": ("정책", "IRA", "인플레이션 감축법", "보호무역"),
        "sentence_terms": ("인플레이션 감축법", "IRA", "핵심원자재법", "보호무역주의"),
        "primary_terms": ("인플레이션 감축법", "IRA"),
        "response_terms": ("적극적인 대응", "대응이 필요한"),
        "role_terms": ("인플레이션 감축법", "보호무역주의"),
    },
)


def _normalise_policy_text(value: Any) -> str:
    return " ".join(str(value or "").split()).lower()


def _dedupe(items: Iterable[str]) -> List[str]:
    seen: set[str] = set()
    result: List[str] = []
    for item in items:
        text = str(item or "").strip()
        if not text:
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(text)
    return result


def narrative_policy_matches(query: str, policy: Dict[str, Any]) -> bool:
    surface = _normalise_policy_text(query)
    if not surface:
        return False
    return any(_normalise_policy_text(term) in surface for term in policy.get("trigger_terms", ()))


def active_narrative_policies(query: str) -> List[Dict[str, Any]]:
    return [policy for policy in NARRATIVE_RETRIEVAL_POLICIES if narrative_policy_matches(query, policy)]


def narrative_policy_active(policies: Sequence[Dict[str, Any]], name: str) -> bool:
    return any(str(policy.get("name") or "") == name for policy in policies)


def narrative_policy_terms(policies: Sequence[Dict[str, Any]], key: str) -> List[str]:
    return _dedupe(
        str(term)
        for policy in policies
        for term in tuple(policy.get(key, ()) or ())
    )


def narrative_policy_query_suffixes(policies: Sequence[Dict[str, Any]]) -> List[str]:
    return narrative_policy_terms(policies, "retrieval_query_suffixes")


def narrative_policy_preferred_sections(policies: Sequence[Dict[str, Any]]) -> List[str]:
    return _dedupe([*NARRATIVE_BASE_PREFERRED_SECTIONS, *narrative_policy_terms(policies, "preferred_sections")])


def narrative_policy_paragraph_priority_sections(policies: Sequence[Dict[str, Any]]) -> List[str]:
    return _dedupe(
        [
            *NARRATIVE_BASE_PARAGRAPH_PRIORITY_SECTIONS,
            *narrative_policy_terms(policies, "paragraph_priority_sections"),
        ]
    )


def narrative_policy_driver_groups(policies: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    groups: List[Dict[str, Any]] = []
    for policy in policies:
        for group in tuple(policy.get("driver_groups", ()) or ()):
            groups.append(
                {
                    "label": str(group.get("label") or ""),
                    "variants": [str(item) for item in tuple(group.get("variants", ()) or ()) if str(item).strip()],
                    "phrase": str(group.get("phrase") or ""),
                }
            )
    return groups


def narrative_policy_slot_groups(
    policies: Sequence[Dict[str, Any]],
    key: str = "entity_metric_slot_groups",
) -> List[Dict[str, Any]]:
    groups: List[Dict[str, Any]] = []
    for policy in policies:
        for group in tuple(policy.get(key, ()) or ()):
            if not isinstance(group, dict):
                continue
            groups.append(
                {
                    "name": str(group.get("name") or ""),
                    "query_terms": [
                        str(item)
                        for item in tuple(group.get("query_terms", ()) or ())
                        if str(item).strip()
                    ],
                    "evidence_terms": [
                        str(item)
                        for item in tuple(group.get("evidence_terms", ()) or ())
                        if str(item).strip()
                    ],
                    "preferred_consolidation_scopes": [
                        str(item)
                        for item in tuple(group.get("preferred_consolidation_scopes", ()) or ())
                        if str(item).strip()
                    ],
                    "preferred_section_markers": [
                        str(item)
                        for item in tuple(group.get("preferred_section_markers", ()) or ())
                        if str(item).strip()
                    ],
                }
            )
    return groups


def narrative_policy_facets(
    policies: Sequence[Dict[str, Any]],
    key: str,
) -> List[Dict[str, Any]]:
    facets: List[Dict[str, Any]] = []
    for policy in policies:
        for facet in tuple(policy.get(key, ()) or ()):
            if not isinstance(facet, dict):
                continue
            facets.append(
                {
                    "name": str(facet.get("name") or ""),
                    "match_terms": [
                        str(item)
                        for item in tuple(facet.get("match_terms", ()) or ())
                        if str(item).strip()
                    ],
                    "required_terms": [
                        str(item)
                        for item in tuple(facet.get("required_terms", ()) or ())
                        if str(item).strip()
                    ],
                    "business_phrase": str(facet.get("business_phrase") or ""),
                    "product_phrase": str(facet.get("product_phrase") or ""),
                    "focus_phrase": str(facet.get("focus_phrase") or ""),
                }
            )
    return facets
