from __future__ import annotations

from typing import Any, Dict, Iterable, List, Sequence, Tuple


KOREAN_PERIOD_PREFIX_RE_FRAGMENT = r"(?:20\d{2}년|당기|전기|전년)"
KOREAN_PERIOD_COMPARISON_RE_FRAGMENT = r"(?:전년|전기|직전\s*연도)\s*대비"
KOREAN_PERIOD_RATE_METRIC_SUFFIX_RE_FRAGMENT = r"(?:증감률|증가율|감소율|성장률|변화율)"
KOREAN_COUNT_UNITS = ("개", "명", "건", "곳", "사", "대")
KOREAN_COUNT_SCALE_PREFIXES = (("천", 1_000.0), ("만", 10_000.0), ("백만", 1_000_000.0))
KOREAN_COUNT_UNIT_RE_FRAGMENT = (
    r"(?:(?:백만|만|천)?\s*(?:개|명|건|곳|사|대))"
)
KOREAN_PERCENT_METRIC_HINT_TERMS = (
    "비율",
    "비중",
    "마진",
    "이익률",
    "수익률",
    "성장률",
    "증가율",
    "감소율",
    "증감률",
    "변동률",
)

FINANCIAL_DOCUMENT_STATEMENT_HINT_POLICIES: Tuple[Dict[str, Any], ...] = (
    {
        "markers": ("재무상태표",),
        "statement_types": ("balance_sheet", "summary_financials"),
        "preferred_sections": ("연결 재무상태표", "재무상태표"),
    },
    {
        "markers": ("손익계산서", "포괄손익계산서"),
        "statement_types": ("income_statement", "summary_financials", "segment_note"),
        "preferred_sections": ("연결 손익계산서", "손익계산서", "포괄손익계산서"),
    },
    {
        "markers": ("현금흐름표",),
        "statement_types": ("cash_flow", "summary_financials"),
        "preferred_sections": ("현금흐름표", "현금흐름표 (연결)"),
    },
    {
        "markers": ("주석",),
        "statement_types": ("notes",),
        "preferred_sections": ("연결재무제표 주석", "재무제표 주석"),
    },
)

FINANCIAL_NUMERIC_STATEMENT_HINT_POLICIES: Tuple[Dict[str, Any], ...] = (
    {
        "markers": ("부채비율", "유동비율", "자산총계", "부채총계", "자본총계", "유동자산", "유동부채"),
        "statement_types": ("balance_sheet", "summary_financials"),
    },
    {
        "markers": ("이익률", "ROE", "ROA"),
        "statement_types": ("income_statement", "summary_financials", "segment_note"),
    },
    {
        "markers": ("영업활동현금흐름", "투자활동현금흐름", "재무활동현금흐름", "FCF", "현금흐름"),
        "statement_types": ("cash_flow", "summary_financials"),
    },
)

FINANCIAL_SEGMENT_SECTION_HINT_POLICY: Dict[str, Any] = {
    "markers": ("부문", "segment", "세그먼트"),
    "statement_types": ("segment_note",),
    "preferred_sections": ("부문정보", "영업부문", "영업실적"),
}

CONTEXTUAL_INGEST_POLICY: Dict[str, Any] = {
    "preview_chars": 400,
    "block_type_labels": {
        "table": "표",
        "paragraph": "단락",
    },
    "context_prompt_template": (
        "다음은 {company} {year}년 사업보고서의 [{section_path}] 섹션에서 발췌한 {block_type}입니다.\n"
        "이 내용이 전체 문서 맥락에서 어떤 정보를 담고 있는지 한국어로 한 문장(50자 이내)으로만 설명하세요.\n\n"
        "내용:\n{preview}"
    ),
    "fallback_context_template": "{company} {year}년 사업보고서 / {section_path} / {block_type}",
    "index_prefix_templates": (
        "{context}",
        "{company} {year} {report_type}",
        "섹션: {section_path}",
        "분류: {section} / {block_type}",
    ),
}

CONSOLIDATION_SCOPE_POLICY: Dict[str, Any] = {
    "query_markers": {
        "consolidated": ("연결",),
        "separate": ("별도",),
    },
    "metadata_values": {
        "consolidated": ("연결", "consolidated", "consolidation"),
        "separate": ("별도", "separate", "standalone", "non-consolidated", "nonconsolidated"),
    },
    "query_prefix_labels": {
        "consolidated": "연결기준",
        "separate": "별도기준",
    },
    "context_markers": {
        "consolidated": ("연결재무제표", "연결"),
        "separate": ("별도",),
    },
    "separate_section_patterns": (
        r"(^|>)\s*4\.\s*재무제표(?!\s*주석)",
        r"(^|>)\s*5\.\s*재무제표\s*주석",
    ),
    "default_consolidated_markers": (
        "재무제표",
        "주석",
        "손익계산서",
        "포괄손익계산서",
        "재무상태표",
        "현금흐름표",
        "자본변동표",
        "매출",
        "매출원가",
        "영업이익",
        "당기순이익",
        "자산",
        "부채",
        "자본",
        "비용",
        "원가",
        "수익",
        "이익",
    ),
}

NUMERIC_UNIT_NORMALIZATION_POLICY: Dict[str, Any] = {
    "inline_value_unit_pattern": (
        r"(?P<value>[-+]?\(?[\d,]+(?:\.\d+)?\)?)\s*"
        rf"(?P<unit>조\s*원?|억\s*원?|백만\s*원|천\s*원|원|%|{KOREAN_COUNT_UNIT_RE_FRAGMENT})"
    ),
    "inline_unit_aliases": {"억": "억원", "조": "조원"},
    "krw_scales": {
        "원": 1.0,
        "천원": 1_000.0,
        "백만원": 1_000_000.0,
        "억원": 100_000_000.0,
        "조원": 1_0000_0000_0000.0,
    },
    "usd_scales": {"usd": 1.0, "$": 1.0, "달러": 1.0, "백만달러": 1_000_000.0},
    "percent_units": ("%", "퍼센트"),
}

GENERIC_METRIC_ALIAS_SUBSTITUTIONS: Tuple[Dict[str, Any], ...] = (
    {"source": "순이익", "target": "순손익"},
    {"source": "순손익", "target": "순이익"},
    {"source": "손익", "target": "이익"},
    {"source": "이익", "target": "손익", "blocked_if_present": ("손익",)},
)

OPERATION_FAMILY_QUERY_POLICIES: Tuple[Dict[str, Any], ...] = (
    {"operation_family": "growth_rate", "markers": ("증감률", "증가율", "감소율", "성장률", "변화율")},
    {"operation_family": "difference", "markers": ("차이", "얼마나 더", "보다 얼마나", "더 큰가", "더 높은가", "더 많은가")},
)

PERCENT_POINT_DIFFERENCE_POLICY: Dict[str, Any] = {
    "direct_markers": ("%p",),
    "ratio_metric_markers": ("비율", "비중", "이익률"),
    "comparison_markers": ("차이", "격차", "비교", "증감", "변화", "변동", "몇 %p", "몇%p"),
}

STRUCTURED_CELL_AFFINITY_POLICY: Dict[str, Any] = {
    "metric_terms": ("매출액", "매출", "영업수익", "수익"),
    "entity_surface_drop_terms": ("부문", "사업부", "사업"),
    "year_pattern": r"20\d{2}\s*년?",
    "entity_token_split_pattern": r"[\s/|,]+",
    "aggregate_tokens": ("합계", "총계", "소계", "계"),
    "aggregate_stage_tokens": {
        "subtotal": ("소계",),
        "final": ("합계", "총계", "계"),
    },
}

STRUCTURED_CELL_PERIOD_SCORING_POLICY: Dict[str, Any] = {
    "current_positive_markers": ("당기", "현재"),
    "current_negative_markers": ("전기", "이전"),
    "prior_positive_markers": ("전기", "이전"),
    "prior_negative_markers": ("당기", "현재"),
}

METRIC_TOPIC_EXTRACTION_TERMS = (
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
)

RATIO_PERCENT_QUERY_POLICY: Dict[str, Any] = {
    "markers": ("비율", "비중", "%", "%p", "이익률", "차지"),
}

GENERIC_OPERAND_LABEL_POLICY: Dict[str, Any] = {
    "compound_label_expansions": (
        {"markers": ("유·무형자산", "유/무형자산"), "labels": ("유형자산", "무형자산")},
    ),
    "derived_labels_to_drop": ("총 영업비용", "영업비용률", "순효과"),
    "cleanup_boundaries": ("에서", "기준", "관련"),
    "cleanup_suffix_pattern": r"(?:금액|수치|총액|규모|비중|비율|증감액|증감폭|순효과)\s*$",
    "leading_year_pattern": r"^[0-9]{4}년\s*",
}

GENERIC_UNIT_FAMILY_POLICY: Dict[str, Any] = {
    "count_markers": ("대수", "수량", "건수", "인원수", "직원수", "회원수", "판매량"),
}

CONCEPT_METRIC_LABEL_POLICY: Dict[str, Any] = {
    "label_joiner": " + ",
    "operation_templates": {
        "ratio": "{labels_joined} 비율",
        "sum": "{labels_joined} 합계",
        "difference_two": "{first_label}과 {second_label} 차이",
        "difference_one": "{label} 차이",
        "growth_rate": "{label} 증가율",
    },
    "fallback_label": "개념 기반 수치",
}

GENERIC_PERIOD_OPERAND_POLICY: Dict[str, Any] = {
    "current_period_hint": "당기",
    "prior_period_hint": "전기",
    "current_period_hints": ("당기", "현재"),
    "prior_period_hints": ("전기", "전년", "직전 연도", "이전 연도", "이전"),
    "current_label_template": "{period_hint} {label}",
    "prior_label_template": "{period_hint} {label}",
    "year_label_template": "{year}년 {label}",
    "year_suffix_template": "{year}년",
    "comparison_markers": ("전년 대비", "전기 대비", "증감액", "증감폭", "%p", "추이"),
    "fallback_metric_label": "수치 계산",
}

CONCEPT_RATIO_RESULT_UNIT_POLICY: Dict[str, Any] = {
    "multiplier_markers": ("배율",),
    "percent_markers": ("비율", "%", "퍼센트", "percentage"),
    "multiplier_unit": "배",
    "percent_unit": "%",
}

METRIC_TASK_QUERY_POLICY: Dict[str, Any] = {
    "operand_joiner": "/",
    "operand_hint_template": "({labels} )",
    "canonical_query_template": "{year_text}{consolidation_text}{metric_label}{operand_hint}을 계산해 줘.",
}

TASK_CONSTRAINT_POLICY: Dict[str, Any] = {
    "segment_markers": ("부문",),
}

PERIOD_FOCUS_POLICY: Dict[str, Any] = {
    "prior_markers": ("전기", "전년", "이전 연도", "직전 연도"),
    "current_markers": ("당기", "금년", "현재 연도", "이번 연도"),
    "explicit_year_pattern": r"20\d{2}",
    "period_presence_pattern": r"20\d{2}|당기|전기|현재|이전|제\s*\d+\s*기",
}

EXPLICIT_RATIO_DEFINITION_POLICY: Dict[str, Any] = {
    "definition_marker": "대비",
    "ratio_markers": ("비율", "비중", "퍼센트", "%"),
    "metric_label_template": "{denominator_label} 대비 {numerator_label} 비율",
}

OPERAND_CANDIDATE_SCORING_POLICY: Dict[str, Any] = {
    "note_context_markers": ("주석",),
    "related_party_penalty_terms": ("특수관계자", "관계기업", "공동기업"),
    "generic_suffix_penalty_terms": ("등",),
    "delta_row_markers": ("증가(감소)", "증가", "감소", "증감", "변동"),
    "context_dependent_lookup_scope_markers": ("부문", "세그먼트", "segment"),
    "context_dependent_table_views": ("column_row_window",),
    "ambiguous_lookup_min_structured_cells": 4,
    "ambiguous_lookup_min_distinct_column_headers": 3,
    "capex_total_surfaces": ("시설투자", "시설투자(capex)", "capex", "자본적지출", "시설투자총액"),
    "capex_priority_section_terms": ("원재료 및 생산설비", "시설투자", "사업의 내용"),
    "balance_sheet_scope_markers": {
        "consolidated": ("연결",),
        "separate": ("별도",),
    },
}

VALUE_NEAR_MATCH_POLICY: Dict[str, Any] = {
    "value_pattern": r"([\d,]+\s*조\s*[\d,]+\s*억(?:\s*원)?|[\d,]+\s*억(?:\s*원)?|[\d,]+\s*백만원|[\d,.]+%)",
    "percent_markers": ("%",),
    "million_krw_unit": "백만원",
    "composite_krw_markers": ("조", "억"),
    "composite_krw_unit": "원",
}

KOREAN_WON_COMPACT_FORMAT_POLICY: Dict[str, Any] = {
    "hundred_million_threshold": 100_000_000,
    "trillion_scale": 1_0000_0000_0000,
    "hundred_million_scale": 100_000_000,
    "ten_thousand_scale": 10_000,
    "trillion_suffix": "조",
    "hundred_million_suffix": "억원",
    "ten_thousand_suffix": "만원",
    "base_suffix": "원",
    "zero_hundred_million_label": "0억원",
}

KOREAN_SEGMENT_LABEL_REPORT_TERMS = (
    "사업보고서",
    "반기보고서",
    "분기보고서",
)

KOREAN_SEGMENT_LABEL_SCOPE_TOKENS = (
    "연결",
    "별도",
)

KOREAN_SEGMENT_LABEL_MARKERS = (
    "부문",
    "세그먼트",
    "segment",
)

KOREAN_SEGMENT_LABEL_ANCHORS = (
    "부문의",
    "부문",
    "세그먼트의",
    "세그먼트",
    "segment",
)

KOREAN_SEGMENT_LABEL_BOUNDARIES = (
    "에서",
    "중",
    "내",
    ":",
)

KOREAN_SEGMENT_LABEL_BLOCKED_TOKENS = (
    "매출",
    "부문",
    "세그먼트",
    "segment",
)

KOREAN_SEGMENT_LABEL_BLOCKED_EXACT_LABELS = (
    "대비",
    "전년",
    "전기",
    "당기",
    "증가율",
    "감소율",
    "성장률",
    "변화율",
    "결제액",
    "영업수익",
    "매출액",
    "매출",
    "이것",
    "이것이",
    "그것",
    "그것이",
    "해당",
    "해당 금액",
)

KOREAN_SEGMENT_LABEL_PERIOD_PREFIX_RE_FRAGMENT = r"^20\d{2}년\s*"
KOREAN_SEGMENT_LABEL_TRAILING_PERIOD_RE_FRAGMENT = r"\b(?:전년|전기|당기)\s*$"
KOREAN_SEGMENT_LABEL_PERIOD_RE_FRAGMENT = r"20\d{2}(?:년)?"
KOREAN_SEGMENT_LABEL_PAREN_RE_FRAGMENT = r"(?:부문|세그먼트|segment)\s*\(([^)]{1,30})\)"
KOREAN_SEGMENT_LABEL_SPLIT_RE_FRAGMENT = r"\s*(?:와|과|및|,|/|·|\+)\s*"
KOREAN_SEGMENT_LABEL_TOKEN_PATTERNS = (
    r"([A-Za-z0-9가-힣&/\-]{1,20})\s*부문",
    r"([A-Za-z0-9가-힣&/\-]{1,20})\s*세그먼트",
    r"([A-Za-z0-9가-힣&/\-]{1,20})\s*매출",
)

NUMERIC_SECTION_HINT_POLICIES: tuple[Dict[str, Any], ...] = (
    {
        "name": "income_before_income_taxes",
        "trigger_terms": ("법인세비용차감전순이익", "법인세비용차감전순손익"),
        "preferred_sections": ("법인세비용", "연결 손익계산서", "포괄손익계산서"),
        "statement_types": ("notes", "summary_financials"),
    },
    {
        "name": "foreign_currency_translation",
        "trigger_terms": ("외화환산이익", "외화환산손실", "환율 변동", "외화환산"),
        "preferred_sections": ("현금흐름표 (연결)", "현금흐름표", "금융손익 (연결)", "외화환산"),
        "statement_types": ("cash_flow", "notes"),
    },
    {
        "name": "borrowings",
        "trigger_terms": ("단기차입금", "장기차입금", "유동성장기차입금", "차입금", "사채"),
        "preferred_sections": ("차입금 및 사채", "단기차입금", "장기차입금", "사채", "연결재무제표 주석"),
        "statement_types": ("notes",),
    },
    {
        "name": "capital_expenditure",
        "trigger_terms": ("시설투자", "capex", "자본적 지출"),
        "preferred_sections": ("원재료 및 생산설비", "시설투자", "사업의 내용"),
    },
    {
        "name": "operating_expense",
        "trigger_terms": ("영업비용", "종업원급여", "인건비"),
        "preferred_sections": ("영업비용", "연결재무제표 주석", "재무제표 주석", "연결 손익계산서", "손익계산서"),
        "statement_types": ("notes",),
    },
)

NUMERIC_IMPAIRMENT_LOOKUP_POLICY: Dict[str, Any] = {
    "trigger_terms": ("손상", "환입"),
    "confirmation_terms": ("발생 여부", "손상차손", "손상 여부", "환입"),
    "total_row_labels": ("기말금액", "당기말", "당기말금액", "기말 장부금액", "기말장부금액"),
    "adjustment_row_labels": ("손상 및 환입", "손상차손", "손상", "손상손실", "손상차손 및 환입"),
    "default_unit": "천원",
    "default_adjustment_label": "손상 및 환입",
    "answer_template": (
        "{report_year_label}연결재무제표 주석 기준 {metric_label} 총액은 {total_value}{total_unit}입니다. "
        "또한 {adjustment_label} 금액이 {adjustment_value}{adjustment_unit}으로 표시되어 있어 "
        "당기에 {metric_label} 손상차손이 발생한 것으로 확인됩니다."
    ),
}

REQUIRED_OPERAND_ASSEMBLY_POLICY: Dict[str, Any] = {
    "aggregation_stage_labels": {
        "subtotal": ("소계",),
        "final": ("합계", "총계", "계"),
    },
    "inline_unit_pattern": r"(?P<value>[\(\)\-]?\d[\d,]*(?:\.\d+)?)\s*(?P<unit>%|백만원|천원|원)",
    "fallback_unit_rules": (
        {"surface_terms": ("조", "억"), "unit": "원", "source": "raw_value"},
        {"surface_terms": ("백만원",), "unit": "백만원", "source": "context"},
        {"surface_terms": ("천원",), "unit": "천원", "source": "context"},
    ),
    "default_unit": "원",
    "stated_change_default_unit": "%",
    "lookup_surface_token_split_pattern": r"[\s/|,()]+",
    "lookup_surface_blocked_tokens": ("부문", "부", "기준", "연결", "별도", "당기", "전기"),
    "ratio_percent_pattern": r"[\d,.]+%",
    "ratio_year_pattern": r"(20\d{2}년)",
    "ratio_label": "비율",
    "ratio_unit": "%",
    "ratio_component_value_pattern": r"[\d,]+(?:\s*조\s*[\d,]+\s*억(?:원)?)?|[\d,]+",
    "ratio_row_fallback_patterns": (r"비율", r"비중", r"이익률"),
    "ratio_period_pattern": r"(20\d{2}년|제\d+기|당기|전기)",
    "ratio_component_percent_value_allowed_concepts": ("revenue",),
    "subject_after_context_pattern": r"[가-힣A-Za-z0-9]+(?:에서|에서는)[가-힣A-Za-z0-9]+(?:은|는)",
}


NARRATIVE_RERANK_POLICY: Dict[str, Any] = {
    "causal_markers": ("영향", "기여", "편입효과", "배경", "요인", "성장"),
    "lower_priority_section_markers_by_query_type": {
        "numeric_fact": ("주석",),
        "trend": ("주석",),
    },
    "lower_priority_section_penalty": -0.12,
}


SENTENCE_NORMALISATION_POLICY: Dict[str, Any] = {
    "intro_patterns": (
        "다음과 같습니다",
        "다음과 같",
        "주요 재무 리스크는",
        "주요 사업은",
        "영위하는 주요 사업은",
    ),
    "missing_support_reason": "근거 claim이 연결되지 않음",
    "summary_intro_reason": "요약형 질문의 도입 문장으로 유지",
    "redundant_intro_reason": "후속 문장이 동일 질문에 직접 답하므로 도입 문장은 제거",
}


CALCULATION_NARRATIVE_POLICY: Dict[str, Any] = {
    "explanatory_markers": (
        "요약",
        "설명",
        "배경",
        "이유",
        "원인",
        "요인",
        "영향",
        "의미를",
        "의미는",
        "의미가",
        "어떤 의미",
        "해석",
        "분석",
        "평가",
        "왜",
        "why",
        "explain",
        "reason",
        "driver",
        "impact",
    ),
    "context_stopwords": (
        "2023년",
        "2022년",
        "전년",
        "대비",
        "증감률",
        "계산",
        "계산해",
        "찾고",
        "찾아",
        "총액",
        "시설투자",
        "CAPEX",
        "capex",
        "집행된",
    ),
    "context_priority_section_terms": ("이사의 경영진단",),
    "context_support_levels": ("context",),
    "context_reuse_excluded_terms": ("불구하고", "불구"),
    "growth_narrative_markers": ("영향", "기여", "개선", "성장", "인수", "편입", "확대", "강화", "회복", "둔화"),
    "missing_answer_markers": (
        "확인하지 못",
        "찾을 수 없",
        "제공되지 않았",
        "계산할 수 없습니다",
        "충분히 확인",
        "충분히 확보하지 못",
        "누락",
        "필요한 값",
    ),
    "growth_query_pattern": r"(성장률|증감률|증가율|전년\s*대비)",
    "percent_display_pattern": r"\d+(?:\.\d+)?\s*%",
    "growth_impact_markers": ("영향", "기여", "기인", "개선", "인수", "편입", "성장", "강화", "증가"),
    "growth_generic_focus_terms": ("부문", "매출", "성장률", "계산하고", "요약해", "영향", "실적", "전년", "대비"),
    "growth_metric_label_terms": ("성장률",),
    "growth_direction_metric_terms": ("매출",),
    "direction_words": {"decrease": "감소", "increase": "증가", "growth": "성장"},
    "default_prior_period": "전년",
    "growth_numeric_sentence_template": (
        "{period_prefix}{metric_label}{topic_particle} {current_value}이며, "
        "{prior_phrase}{growth_value} {direction_word}했습니다."
    ),
    "prior_phrase_with_value_template": "{period} {value} 대비 ",
    "prior_phrase_template": "{period} 대비 ",
    "topic_particles": {"with_final_consonant": "은", "without_final_consonant": "는"},
    "period_year_suffix": "년",
    "period_prefix_with_year_template": "{period}년 ",
    "period_prefix_template": "{period} ",
    "sentence_terminal_pattern": r"[.!?。]$",
    "sentence_terminal_suffix": ".",
    "max_growth_driver_sentences": 4,
    "source_visible_term_note_template": "원문 표기: {terms}.",
}


CALCULATION_RENDER_POLICY: Dict[str, Any] = {
    "scope_labels": {"consolidated": "연결기준", "separate": "별도기준"},
    "difference_default_labels": {
        "minuend": "기준값",
        "subtrahend": "차감값",
        "result": "계산 결과",
    },
    "difference_first_sentence_with_prefix": "{prefix} {minuend_label}은 {minuend_value}입니다.",
    "difference_first_sentence": "{minuend_label}은 {minuend_value}입니다.",
    "difference_answer_template": (
        "{first_sentence} {subtrahend_label} 금액은 {subtrahend_value}이며, "
        "이를 제외한 {result_label}은 {result_value}입니다."
    ),
    "adjusted_difference_query_terms": ("제외", "실질", "조정"),
    "adjusted_difference_exclusion_pattern": r"차감(?!전)",
    "source_display_units": ("천원", "백만원"),
    "converted_display_units": ("원", "억원", "조원"),
    "count_or_percent_normalized_units": ("COUNT", "PERCENT", "%", "퍼센트"),
    "percent_display_units": ("%", "%p"),
    "krw_normalized_unit": "KRW",
    "krw_display_units": ("원", "천원", "백만원", "억원", "십억원", "조원"),
    "krw_display_unit_scales": {
        "원": 1.0,
        "천원": 1_000.0,
        "백만원": 1_000_000.0,
        "억원": 100_000_000.0,
        "십억원": 1_000_000_000.0,
        "조원": 1_000_000_000_000.0,
    },
    "count_display_units": ("개", "명"),
    "value_embedded_unit_markers": ("원", "억", "조", "%"),
    "krw_value_magnitude_markers": ("억", "조"),
    "operand_unit_bare_numeric_pattern": r"[\(\)\-]?\d[\d,]*(?:\.\d+)?",
    "operand_unit_ambiguous_krw_units": ("원", "krw"),
    "ratio_default_metric_label": "비율",
    "ratio_year_period_pattern": r"20\d{2}",
    "ratio_period_prefix_template": "{period}년 ",
    "ratio_answer_template": "{period_prefix}{metric_label}은 {rendered_value}입니다.",
    "lookup_list_item_template": "{label} {value}",
    "lookup_list_separator": ", ",
    "lookup_list_answer_template": "{items}입니다.",
    "sign_aware_subtraction_replacements": (
        ("{label} {negative}", "{label} {positive}"),
        ("{label} 금액은 {negative}", "{label} 금액은 {positive}"),
        ("{label}은 {negative}", "{label}은 {positive}"),
        ("{label}는 {negative}", "{label}는 {positive}"),
        ("{negative}을 차감", "{positive}을 차감"),
        ("{negative}를 차감", "{positive}를 차감"),
        ("{negative} 만큼 차감", "{positive} 만큼 차감"),
        ("{negative}만큼 차감", "{positive}만큼 차감"),
    ),
    "direction_hints": {
        "growth_rate": {"positive": "증가", "negative": "감소", "zero": "변동 없음"},
        "subtract": {"positive": "더 큽니다", "negative": "더 작습니다", "zero": "동일합니다"},
    },
    "insufficient_evidence_fallback": "질문에 필요한 수치를 계산할 수 있는 근거를 충분히 확보하지 못했습니다.",
    "low_api_generation_skipped_fallback": "질문에 필요한 수치를 계산했지만 자연어 답변 생성을 생략했습니다.",
    "render_generation_failed_fallback": "질문에 필요한 수치를 계산했지만 자연어 답변을 생성하지 못했습니다.",
    "renderer_prompt_template": (
        "당신은 한국 기업 공시(DART) 계산 결과를 사용자 친화적인 한국어로 렌더링하는 분석가입니다.\n\n"
        "[렌더링 규칙]\n"
        "- CalculationResult의 rendered_value를 그대로 사용하세요. 숫자를 다시 계산하거나 형식을 바꾸지 마세요.\n"
        "- CalculationResult의 answer_slots가 있으면 rendered_value/series보다 먼저 참고해 현재값, 전기값, 증감값, 주된 결과값을 파악하세요.\n"
        "- components_by_role에 subtrahend가 있고 그 rendered_value가 음수처럼 보여도, 서술에서는 절댓값을 차감하는 표현을 우선 사용하세요. \"-X를 차감\"처럼 이중 음수 표현을 만들지 마세요.\n"
        "- operand label에 포함된 연도·기간 정보(예: '2024년', '2023년', '1분기')는 반드시 그대로 유지하세요. '2024년 영업이익'을 '영업이익'으로 줄이지 마세요.\n"
        "- direction_hint가 제공된 경우, 그 단어를 그대로 사용하세요. 임의로 '변동', '차이' 등 중립적 표현으로 바꾸지 마세요.\n"
        "- time_series 해석(상승·하락·반등 등)은 series 또는 derived_metrics의 수치 변화를 근거로 표현하세요.\n"
        "- 데이터에 없는 새로운 연도, 금액, 비율을 만들지 마세요.\n"
        "- 질문에 직접 답하는 1~2문장만 작성하세요.\n\n"
        "질문:\n{query}\n\n"
        "Direction Hint (방향 판단 결과, 비어 있으면 무시):\n{direction_hint}\n\n"
        "CalculationPlan:\n{plan_json}\n\n"
        "CalculationResult:\n{result_json}\n\n"
        "Operands:\n{operands_json}\n\n"
        "반드시 final_answer만 채우세요.\n"
    ),
    "verification_prompt_template": (
        "당신은 재무 계산 답변 검증기입니다.\n"
        "사용자에게 내보내기 직전의 계산 답변이 질문, 계산 결과, 피연산자와 모순이 없는지 검토하세요.\n\n"
        "규칙:\n"
        "- 새로운 숫자, 연도, 단위, 근거를 추가하지 마세요.\n"
        "- 계산 결과와 질문 의도에 맞는다면 verdict=keep.\n"
        "- 숫자, 단위, 방향, 비교 관계가 어긋나면 verdict=rewrite 로 두고 1~2문장으로 바로잡으세요.\n"
        "- 답변이 계산 결과와 크게 모순되거나 불필요한 내용을 덧붙였으면 verdict=fallback 으로 두고 deterministic fallback과 같은 뜻으로 작성하세요.\n"
        "- CalculationResult.answer_slots가 있으면 그 슬롯을 기준으로 답변이 질문 요구사항을 충족하는지 판단하세요.\n"
        "- final_answer는 rendered_value와 direction_hint를 벗어나지 마세요.\n"
        "- %p 질문이면 %p를 유지하세요.\n"
        "- 단일 값 조회 질문이면 계산 과정 설명을 길게 덧붙이지 마세요.\n\n"
        "질문:\n{query}\n\n"
        "현재 답변:\n{answer}\n\n"
        "Deterministic Fallback:\n{fallback}\n\n"
        "Direction Hint:\n{direction_hint}\n\n"
        "CalculationPlan:\n{plan_json}\n\n"
        "CalculationResult:\n{result_json}\n\n"
        "Operands:\n{operands_json}\n"
    ),
}


CALCULATION_SLOT_POLICY: Dict[str, Any] = {
    "period_pattern": r"20\d{2}\s*년?",
    "label_drop_terms": ("총액", "증감률", "증감액", "증가율", "비중", "비율"),
    "label_drop_patterns": (r"(^|\s)부문(?=\s|$)",),
    "parenthetical_alias_pattern": r"\(([^)]{2,80})\)",
    "parenthetical_strip_pattern": r"\([^)]*\)",
    "leading_period_strip_pattern": r"^(?:(?:20\d{2}\s*년?)|(?:제\s*\d+\s*기))(?:\s+|$)",
}


CALCULATION_FEEDBACK_POLICY: Dict[str, Any] = {
    "default_metric_label": "계산 결과",
    "lookup_missing_template": "{metric_label} direct value가 누락되었습니다.",
    "missing_period_value_template": "{period} 값",
    "default_current_period": "current",
    "default_prior_period": "prior",
    "difference_missing_result_label": "증감값",
    "growth_missing_result_label": "증감률",
    "missing_material_template": "{metric_label} 계산에 필요한 {missing_labels}이 누락되었습니다.",
    "missing_material_joiner": " / ",
    "missing_result_template": "{metric_label} 계산 결과가 누락되었습니다.",
    "generic_missing_material_template": "{metric_label} 계산에 필요한 재료가 누락되었습니다.",
}


CALCULATION_PROMPT_POLICY: Dict[str, Any] = {
    "operand_extraction_prompt_template": (
        "당신은 재무 계산을 위한 피연산자 추출기입니다.\n"
        "질문을 풀기 위해 필요한 숫자만 single-shot으로 한 번에 추출하세요.\n\n"
        "규칙:\n"
        "- 여러 번 나눠 찾지 말고, 필요한 피연산자를 한 번의 호출로 모두 찾으세요.\n"
        "- operand_id는 비워도 됩니다. 코드는 이후에 고유 ID를 부여합니다.\n"
        "- 각 operand는 반드시 evidence_id와 source_anchor를 포함하세요.\n"
        "- raw_value는 문서에 있는 숫자 표현 그대로 적으세요. '111조 659억원'처럼 조+억 복합 표기는 절대 억원이나 조원으로 변환하지 말고 원문 그대로 적으세요. 변환하면 반올림 오차가 발생합니다.\n"
        "- raw_unit은 숫자 바로 옆 단위를 적으세요. 복합 표기('111조 659억원')는 raw_unit을 '억원'으로 적지 말고, raw_value에 원문 전체를 넣고 raw_unit은 '원'으로 적으세요.\n"
        "- normalized_value와 normalized_unit은 추정해서 채워도 되지만, 이후 코드가 다시 검증합니다.\n"
        "- 비교/추세 질문은 질문 해결에 꼭 필요한 숫자만 추출하세요.\n"
        "- source_context와 raw_row_text가 있으면, 해당 표의 헤더와 행을 함께 읽어 period와 숫자 매핑을 복원하세요.\n"
        "- raw_row_text에 같은 metric의 여러 연도/기간 값이 함께 있으면, 각 연도/기간별 숫자를 별도 operand로 나누어 추출하세요.\n"
        "- 질문이 단일 비율/비중/이익률 조회라면 피연산자 1개만 추출할 수 있습니다.\n"
        "- 질문이 두 기간/두 부문/두 비율의 차이·비교·대비·%p 차이를 묻는다면, 절대 단일 비율 피연산자 1개로 축약하지 말고 비교 대상별 피연산자를 각각 추출하세요.\n"
        "- 질문에 `%p`, `차이`, `비교`, `대비`가 있고 evidence에 동일 metric의 여러 기간/부문 percent 값이 보이면, 해당 percent 값들을 period별/대상별로 각각 별도 operand로 추출하세요.\n"
        "- 추이(trend) 질문이고 evidence에 3개 이상의 연도/기간 수치가 보이면, 가능한 한 3개 이상 기간의 피연산자를 빠짐없이 추출하세요.\n"
        "- 문서 메타데이터의 보고서 연도와 표 안에 적힌 비교 기간(예: 2024년, 2023년, 2022년)을 혼동하지 말고, period 필드에는 표에서 읽은 실제 기간을 그대로 적으세요.\n"
        "- 수치가 없는 descriptive evidence는 operand로 만들지 마세요.\n\n"
        "질문: {query}\n\n"
        "Structured Evidence:\n{evidence}\n"
    ),
    "formula_plan_prompt_template": (
        "당신은 재무 계산 계획기입니다.\n"
        "질문과 피연산자 목록을 보고 변수 바인딩과 계산식을 작성하세요.\n\n"
        "규칙:\n"
        "- variable_bindings에는 반드시 아래 피연산자 목록의 operand_id만 넣으세요.\n"
        "- 각 binding의 variable은 A, B, C, D, E, F 중 하나만 사용하세요.\n"
        "- ordered_operand_ids는 variable_bindings와 같은 순서로 넣으세요.\n"
        "- operation은 로그/평가용 힌트입니다. subtract, add, ratio, growth_rate, max, min, time_series_trend, none 중 가장 가까운 값을 넣으세요.\n"
        "- 실제 계산은 formula와 pairwise_formula로 표현합니다.\n"
        "- formula에는 숫자 상수와 변수(A, B, C...) 그리고 +, -, *, /, **, min(), max(), abs(), round(), log(), exp()만 사용할 수 있습니다.\n"
        "- mode=single_value 이면 formula로 단일 결과를 계산하세요.\n"
        "- mode=time_series 이면 variable_bindings를 시계열 순서로 배치하고, formula에는 전체 흐름을 대표하는 계산식(예: ((C - A) / A) * 100)을, pairwise_formula에는 인접 시점 계산식(예: ((CURR - PREV) / PREV) * 100)을 적으세요.\n"
        "- 최근 3년/연도별/추이 질문처럼 3개 이상 기간 데이터가 있을 때는 mode=time_series 와 operation=time_series_trend 를 우선 사용하세요.\n"
        "- 이미 계산된 단일 비율/비중/이익률 하나만 답하면 되는 질문이라면 mode=single_value, formula=A 를 사용하세요.\n"
        "- 질문이 단일 비율/비중/이익률 조회이고 피연산자가 퍼센트 1개뿐이라면 반드시 mode=single_value, formula=A 를 사용하세요.\n"
        "- 질문이 단일 비율/비중/이익률 조회이고 분자/분모 역할의 금액 피연산자 2개가 있다면 formula는 (A / B) * 100 형태로 작성하세요.\n"
        "- 두 비율/비중의 차이(%p 차이 포함)를 묻는 질문이라면 mode=single_value 로 두고 formula는 A - B 또는 질문 순서에 맞는 차이식으로 작성하세요. 단일 operand 하나로 끝내지 마세요.\n"
        "- 증가율/감소율/변화율은 가능한 한 질문에서 기준이 되는 이전 값이 분모가 되도록 식을 작성하세요.\n"
        "- 현재 피연산자만으로 질문을 풀 수 없으면 억지로 수식을 만들지 말고 status=incomplete, mode=none, operation=none 으로 두고 missing_info에 부족한 정보를 적으세요.\n"
        "- result_unit은 최종 답변 단위를 적으세요. 예: 억원, 원, %, 개\n"
        "- ontology_context는 이 질문에 대해 추정된 metric family prior 입니다. 실제 피연산자와 모순되면 ontology_context보다 피연산자를 우선하세요.\n"
        "- ontology_context에 formula_template과 components가 있으면, 단일 비율 조회는 A 또는 (A / B) * 100, %p 차이는 A - B 같은 계획을 세울 때 참고하세요.\n\n"
        "질문: {query}\n\n"
        "Ontology Context:\n{ontology_context}\n\n"
        "사용 가능한 피연산자:\n{operands}\n"
    ),
    "aggregate_synthesis_prompt_template": (
        "당신은 DART 재무 질의용 최종 synthesizer입니다.\n"
        "원본 질문과 내부 subtask 결과를 읽고, 사용자에게 보여줄 최종 답변을 작성하세요.\n\n"
        "입력 데이터:\n"
        "1. 원본 질문\n"
        "2. subtask 결과 목록\n"
        "3. deterministic structured material check\n"
        "4. narrative context evidence\n\n"
        "규칙:\n"
        "- 최종 답변은 원본 질문이 명시적으로 요구한 값과 계산 결과를 빠짐없이 포함하도록 노력하세요.\n"
        "- subtask 결과의 answer, calculation_result.rendered_value, calculation_result.series, calculation_operands를 근거로 사용하세요.\n"
        "- subtask 결과의 calculation_result.answer_slots가 있으면 그것을 가장 우선적인 structured result contract로 사용하세요.\n"
        "- narrative context evidence가 있고 원본 질문이 업황/배경/영향 같은 맥락을 요구하면, 최종 답변에 그 맥락을 짧게 반영하세요.\n"
        "- 새로운 숫자, 연도, 단위를 만들지 마세요.\n"
        "- deterministic structured material check가 비어 있으면, 현재 재료만으로 원본 질문을 완전히 충족한다고 보고 planner_feedback은 비워 두세요.\n"
        "- deterministic structured material check가 비어 있지 않으면, 그 누락 재료를 planner_feedback에 반영하세요.\n"
        "- 현재 재료만으로는 원본 질문의 요구사항 일부를 충족할 수 없다면, planner_feedback에 planner가 추가로 모아야 할 재료를 한 문장으로 적으세요.\n"
        "- planner_feedback은 내부 시스템용이므로 간결하게, 누락된 값/기간/개념 중심으로 쓰세요.\n"
        "- final_answer는 사용자용 한국어 답변만 작성하세요.\n\n"
        "원본 질문:\n{query}\n\n"
        "Fallback Answer:\n{fallback_answer}\n\n"
        "Deterministic Structured Material Check:\n{deterministic_feedback}\n\n"
        "Narrative Context Evidence:\n{narrative_context}\n\n"
        "Subtask Results JSON:\n{subtask_results_json}\n"
    ),
}


RECONCILIATION_POLICY: Dict[str, Any] = {
    "lookup_surface_period_prefix_pattern": r"^(?:20\d{2}\s*년?)\s+",
    "period_presence_pattern": r"20\d{2}|당기|전기|현재|이전|제\s*\d+\s*기",
    "percent_unit": "%",
    "ambiguous_krw_units": ("", "원", "KRW"),
    "note_statement_type": "notes",
    "candidate_rerank_prompt_template": (
        "당신은 재무 계산 후보 재정렬기입니다.\n"
        "질문과 target operand에 가장 잘 맞는 candidate_id를 best-first 순서로 정렬하세요.\n\n"
        "우선순위:\n"
        "1. 직접 숫자 값이 있는 표 row\n"
        "2. 질문의 연결/별도, 기간, statement_type에 맞는 근거\n"
        "3. narrative paragraph보다 table row / structured row\n"
        "4. '범위', '하위범위', '상위범위' 같은 설명 row는 피하세요.\n\n"
        "질문:\n{query}\n\n"
        "target operand:\n{operand_label}\n\n"
        "candidate options:\n{options}\n"
    ),
    "supplemental_section_bonus_terms": ("연구개발 활동", "연구개발활동"),
    "missing_info_year_template": "{year}년 {label}",
    "missing_info_suffix_cleanup_pattern": r"(비교|차이|대비|합계)\s*$",
    "missing_info_token_pattern": r"[가-힣A-Za-z0-9]+",
    "reflection_sum_query_markers": ("합계", "합산", "합친", "합한"),
    "reflection_binding_query_pattern": r"\bvs\b|와|과",
    "reflection_prompt_template": (
        "당신은 재무 RAG 에이전트의 reflection planner 입니다.\n"
        "현재 검색/계산이 실패했을 때, 무엇이 부족한지 진단하고 retrieval-friendly 재검색 쿼리를 1~3개 설계하세요.\n\n"
        "목표:\n"
        "- 사용자 질문의 의도를 유지한 채\n"
        "- 현재 파이프라인이 다시 검색했을 때 누락된 피연산자나 비율 행을 찾기 쉬운 쿼리로 재정의하세요.\n\n"
        "규칙:\n"
        "- status는 재검색이 의미 있으면 ready, 아니면 skip.\n"
        "- retry_strategy는 아래 셋 중 하나만 고르세요.\n"
        "  - retry_retrieval: 재검색을 더 시도한다\n"
        "  - synthesize_from_task_outputs: 이미 확보한 sibling task output만으로 계산을 시도하고, broad retrieval fallback은 피한다\n"
        "  - stop_insufficient: 현재 근거로는 더 진행해도 의미가 낮다\n"
        "- retry_objective는 이번 재검색의 목적만 고르세요.\n"
        "  - find_missing_values: 필요한 값 일부가 빠졌음\n"
        "  - find_direct_row: 질문이 요구하는 직접적인 row/요약값을 찾고 싶음\n"
        "  - resolve_binding: 기간/대상/레이블 연결을 더 명확히 하고 싶음\n"
        "  - generic_retry: 위 셋으로 충분히 설명되지 않음\n"
        "- missing_info에는 현재 컨텍스트에 부족한 정보만 적으세요.\n"
        "- subqueries는 1~3개만 만드세요.\n"
        "- 각 subquery는 자연어 장문이 아니라 retrieval-friendly keyword query여야 합니다.\n"
        "- subquery에는 가능한 한 회사명, 연도, 부족한 metric/entity, 짧은 섹션 힌트를 포함하세요.\n"
        "- 질문이 %p 차이나 두 비율 비교라면, 먼저 같은 metric의 기간별/대상별 비율 row를 찾는 쿼리를 우선하세요.\n"
        "- 질문이 비율/이익률 계산인데 비율 row가 없으면, 분자/분모 component를 각각 찾는 쿼리를 만드세요.\n"
        "- 질문이 합계라면, 합쳐야 하는 구성 항목별 수치를 따로 찾는 쿼리를 만드세요.\n"
        "- preferred_sections는 재검색에서 특히 유력한 섹션 힌트만 짧게 넣으세요.\n"
        "- 기존 seed sections에 이미 충분히 있는 정보를 그대로 반복하지 말고, 부족한 부분을 겨냥하세요.\n"
        "- 하드 필터는 코드가 따로 처리하므로, 기업/연도는 query text에 포함하되 너무 장황하게 쓰지 마세요.\n"
        "- derived task가 sibling lookup output에 의존하는 상황이면 retry_retrieval보다 synthesize_from_task_outputs를 우선 검토하세요.\n\n"
        "질문: {query}\n"
        "의도: {intent}\n"
        "주제: {topic}\n"
        "기업: {companies}\n"
        "연도: {years}\n\n"
        "현재 실패 추정:\n"
        "- fallback_retry_objective={retry_objective}\n"
        "- missing_info(heuristic)={missing_info}\n\n"
        "Ontology Context:\n{ontology_context}\n\n"
        "현재 확보한 피연산자:\n{operands}\n\n"
        "현재 계산 계획:\n{plan_text}\n\n"
        "현재 계산 결과:\n{calc_result_text}\n\n"
        "현재 seed sections:\n{seed_sections}\n\n"
        "참고용 heuristic retry plan:\n{heuristic_plan}\n"
    ),
}


PLANNING_POLICY: Dict[str, Any] = {
    "money_surface_pattern": (
        r"(?P<raw>\(?\d[\d,]*(?:\.\d+)?\)?)(?:\s*)"
        r"(?P<unit>조\s*\d[\d,]*(?:\.\d+)?\s*억원|조원|십억원|억원|백만원|천원|원|%)"
    ),
    "year_token_pattern": r"20\d{2}",
    "year_label_token_pattern": r"20\d{2}\s*년?",
    "money_surface_compound_unit_prefix": "조",
    "hybrid_narrative_metric_label": "질문 관련 배경/영향 설명",
    "segment_default_metric_name": "매출액",
    "non_numeric_operation_intent_override": {
        "enabled": True,
        "source_intents": ("qa", "risk", "business_overview"),
        "target_intent": "numeric_fact",
        "operation_families": ("lookup", "single_value", "sum", "difference", "ratio", "growth_rate"),
        "unit_families": ("KRW", "USD", "COUNT", "PERCENT"),
        "query_markers": ("금액", "수치", "규모", "값", "찾", "알려", "제시", "보여", "추출", "요약"),
        "minimum_concepts": 1,
        "allow_generic_numeric_plan": True,
        "planner_note": "non_numeric_operation_promoted_by_ontology",
    },
    "concept_planner_replan_rules": (
        "- 현재는 replan mode입니다. planner_feedback를 읽고, 기존 task는 유지한 채 누락된 재료를 찾기 위한 추가 task만 만드세요.\n"
        "- 기존 task와 실질적으로 같은 task를 다시 만들지 마세요.\n"
        "- planner_feedback가 이미 확보된 기존 task로 해결된다면 tasks를 비워 둘 수 있습니다."
    ),
    "concept_planner_initial_rule": "- 현재는 initial mode입니다. 원본 질문을 풀기 위한 전체 재료 수집 계획을 세우세요.",
    "concept_planner_prompt_template": (
        "당신은 DART 재무 질문 planner입니다.\n"
        "질문을 직접 답하지 말고, 아래 ontology concept만 사용해서 계산 계획으로 바꾸세요.\n\n"
        "허용 operation_family:\n{allowed_operations}\n\n"
        "role 규칙:\n"
        "- ratio: numerator_1, numerator_2, ... / denominator_1, denominator_2, ...\n"
        "- sum: addend_1, addend_2, ...\n"
        "- difference: minuend, subtrahend 또는 current_period, prior_period\n"
        "- growth_rate: current_period, prior_period\n"
        "- lookup/single_value: role은 비워도 됨\n\n"
        "planner_guidance.intent_cues:\n{intent_cues}\n\n"
        "available concepts:\n{concept_catalog}\n\n"
        "현재 planning mode:\n{planning_mode}\n\n"
        "현재 planner_feedback:\n{planner_feedback}\n\n"
        "기존 task 요약:\n{existing_tasks}\n\n"
        "중요 규칙:\n"
        "- ontology에 [group]으로 표시된 concept는 축약 표현입니다. planner는 group을 그대로 쓰거나, 그 group이 expands_to로 가리키는 atomic concept 전부를 써도 됩니다.\n"
        "- 다만 최종 task는 질문에 필요한 모든 atomic 의미를 빠뜨리지 않아야 합니다. 예를 들어 \"유·무형자산\"이면 유형자산과 무형자산이 모두 포함되어야 합니다.\n"
        "- 질문이 여러 지표를 \"각각\" 계산하라고 하면 tasks를 여러 개로 나누세요.\n"
        "- planner의 목적은 최종 문장을 줄이는 것이 아니라, 질문에 답하는 데 필요한 재료(raw value, period pair, derived metric)를 빠짐없이 확보하는 것입니다.\n"
        "- 사용자가 특정 연도/기간의 값을 \"추출\", \"제시\", \"보여\", \"알려\" 달라고 했으면 그 raw value를 위한 lookup task를 만드세요.\n"
        "- 사용자가 raw value와 파생 계산(증감액, 증가율, 비율 등)을 함께 요구하면, lookup task와 calculation task를 모두 만들어도 됩니다.\n"
        "- difference 또는 growth_rate task는 계산 재료를 모으는 역할이지, 그 task 하나가 최종 답변의 모든 노출 요구를 대신한다고 가정하지 마세요.\n"
        "- lookup은 단일 값 조회나, 다른 계산 task와 별도로 원문 질문이 직접 요구한 raw 값을 확보할 때 사용하세요.\n"
        "- benchmark 전용 metric family 이름에 의존하지 말고, operation과 concept 조합으로 task를 만드세요.\n"
        "- 사업/부문/제품/브랜드(SDC, Harman 등)는 company로 보지 말고 report_scope의 company 안에서 분석할 segment로 다루세요.\n"
        "- 여러 concept를 각각 더해야 하는 질문이면 먼저 필요한 lookup task를 만들고, 이후 sum task에서 concept addend 역할(addend_1, addend_2, ...)로 묶으세요.\n"
        "- concept는 available concepts 안의 key만 써야 합니다.\n"
        "- 질문에 명시되지 않은 company/year는 report_scope 기본값을 따른다고 가정하세요.\n"
        "{mode_specific_rules}\n\n"
        "few-shot 예시 1:\n"
        "질문: 2023년 연결기준 부채비율을 계산해 줘.\n"
        "출력:\n"
        "tasks = [\n"
        "  {{ metric_label: \"부채비율\", operation_family: \"ratio\", operands: [\n"
        "    {{ concept: \"total_liabilities\", role: \"numerator_1\" }},\n"
        "    {{ concept: \"total_equity\", role: \"denominator_1\" }}\n"
        "  ]}}\n"
        "]\n\n"
        "few-shot 예시 2:\n"
        "질문: 2023년 연결기준 부채비율과 유동비율을 각각 계산해 줘.\n"
        "출력:\n"
        "tasks = [\n"
        "  {{ metric_label: \"부채비율\", operation_family: \"ratio\", operands: [\n"
        "    {{ concept: \"total_liabilities\", role: \"numerator_1\" }},\n"
        "    {{ concept: \"total_equity\", role: \"denominator_1\" }}\n"
        "  ]}},\n"
        "  {{ metric_label: \"유동비율\", operation_family: \"ratio\", operands: [\n"
        "    {{ concept: \"current_assets\", role: \"numerator_1\" }},\n"
        "    {{ concept: \"current_liabilities\", role: \"denominator_1\" }}\n"
        "  ]}}\n"
        "]\n\n"
        "few-shot 예시 3:\n"
        "질문: 2023년 연결 재무상태표에서 유·무형자산의 총합 대비 차입금의 비중을 계산해 줘.\n"
        "출력:\n"
        "tasks = [\n"
        "  {{ metric_label: \"유·무형자산 대비 차입금 비중\", operation_family: \"ratio\", operands: [\n"
        "    {{ concept: \"short_term_borrowings\", role: \"numerator_1\" }},\n"
        "    {{ concept: \"long_term_borrowings\", role: \"numerator_2\" }},\n"
        "    {{ concept: \"bonds_payable\", role: \"numerator_3\" }},\n"
        "    {{ concept: \"property_plant_equipment\", role: \"denominator_1\" }},\n"
        "    {{ concept: \"intangible_assets\", role: \"denominator_2\" }}\n"
        "  ]}}\n"
        "]\n\n"
        "few-shot 예시 4:\n"
        "질문: 2023년 연결 손익계산서에서 법인세비용차감전순이익을 추출하고, 전년 대비 증감액을 계산해 줘.\n"
        "출력:\n"
        "tasks = [\n"
        "  {{ metric_label: \"2023년 법인세비용차감전순이익\", operation_family: \"lookup\", operands: [\n"
        "    {{ concept: \"income_before_income_taxes\", role: \"current_period\" }}\n"
        "  ]}},\n"
        "  {{ metric_label: \"법인세비용차감전순이익 증감액\", operation_family: \"difference\", operands: [\n"
        "    {{ concept: \"income_before_income_taxes\", role: \"current_period\" }},\n"
        "    {{ concept: \"income_before_income_taxes\", role: \"prior_period\" }}\n"
        "  ]}}\n"
        "]\n"
        "설명:\n"
        "- 원문 질문이 2023년 raw value와 전년 대비 증감액을 모두 요구하므로, raw value lookup과 difference 계산 재료를 모두 확보합니다.\n\n"
        "질문:\n{query}\n\n"
        "topic:\n{topic}\n\n"
        "intent:\n{intent}\n\n"
        "report_scope:\n{report_scope}\n\n"
        "Also return:\n"
        "- companies: normalized company list for this question\n"
        "- years: normalized relevant years\n"
        "- topic: a concise topic string for retrieval/ranking\n"
        "- section_filter: a single best section hint when one section is strongly dominant, otherwise null\n"
    ),
}


HELPER_RUNTIME_POLICY: Dict[str, Any] = {
    "narrative_context_hints": (
        "요약",
        "원인",
        "배경",
        "설명",
        "사례",
        "영향",
        "전략",
        "리스크",
        "의미를",
        "의미는",
        "의미가",
        "왜",
        "어떤",
        "어떻게",
        "적용",
        "관리 방안",
        "관리 전략",
        "관리 현황",
        "어떻게 관리",
        "대응",
        "기여",
        "업황",
        "악화",
        "불구",
        "정책",
        "impact",
        "driver",
        "reason",
        "explain",
        "summarize",
    ),
    "legacy_concept_surface_contracts": {
        "income_before_income_taxes": {
            "positive": (
                "법인세비용차감전순이익",
                "법인세비용차감전순손익",
                "법인세비용 차감 전 순이익",
                "법인세비용 차감 전 순손익",
                "세전이익",
                "세전순이익",
            ),
            "negative": (
                "계속영업순이익",
                "계속영업순손익",
                "당기순이익",
                "당기순손익",
            ),
        }
    },
    "non_value_row_labels": ("범위", "하위범위", "상위범위", "범위 합계"),
    "generic_column_headers": ("구분", "항목", "내용", "세부항목", "비고", "차입금명칭"),
    "balance_sheet_aggregate_labels": (
        "자산총계",
        "부채총계",
        "자본총계",
        "유동자산",
        "비유동자산",
        "유형자산",
        "무형자산",
        "유동부채",
        "비유동부채",
    ),
    "segment_context_bonus_terms": ("매출 및 수주상황", "부문", "세그먼트", "segment"),
    "entity_scoped_default_metric": {
        "query_terms": ("매출",),
        "label": "매출액",
    },
}


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

QUANTITATIVE_IMPACT_ASSEMBLY_POLICY: Dict[str, Any] = {
    "focus_stopwords": ("2023년", "규모를", "찾고", "이것이", "미친", "분석해"),
    "primary_denominator_markers": ("매출원가", "매출액", "영업수익", "영업비용", "총계", "합계"),
    "denominator_markers": ("자산", "부채", "자본"),
    "label_drop_terms": ("등",),
    "cost_denominator_markers": ("원가", "비용"),
    "loss_markers": ("손실", "손상차손"),
    "relation_markers": ("포함", "반영", "인식", "영향"),
    "cost_relation_context_markers": ("원가", "비용", "손익"),
    "relation_query_template": "{focus_terms} {relation_terms} {context_terms}",
    "caveat_trigger_terms": ("등", "환입"),
    "caveat_exception_terms": ("세부",),
    "consolidated_scope_prefix": "연결 기준 ",
    "default_impact_sentence": "해당 기준 금액에 반영된 항목으로 해석할 수 있습니다.",
    "scale_only_impact_template": "{denominator_label} 대비 규모로 확인됩니다.",
    "cost_loss_impact_template": "{denominator_label}에 포함되어 비용을 증가시키고 매출총이익을 압박하는 요인입니다.",
    "cost_impact_template": "{denominator_label}에 포함되어 해당 비용에 영향을 주는 항목입니다.",
    "caveat_sentence": " 항목명상 손실, 환입 등의 세부 구성은 이 근거만으로는 분해하지 않습니다.",
    "answer_template": (
        "{scope_prefix}{numerator_label}은 {numerator_raw}{unit_suffix}입니다. "
        "{impact_sentence} {denominator_label} {denominator_raw}{unit_suffix} 대비 약 {ratio:.2f}% 규모입니다.{caveat}"
    ),
}

ENTITY_TABLE_SUMMARY_ASSEMBLY_POLICY: Dict[str, Any] = {
    "consolidated_query_terms": ("연결",),
    "section_score_rules": (
        {"text": "타법인출자", "field": "section_path", "score": 2},
        {"text": "재무제표 주석", "field": "section_path", "score": 2},
        {"text": "타법인출자", "field": "text", "score": 4},
    ),
    "text_score_terms": (("투자자산", "관계기업", "공동기업"), 3),
    "negative_text_terms_without_anchor": {
        "terms": ("연결대상", "종속기업"),
        "anchor": "타법인출자",
        "score": -4,
    },
    "non_consolidated_section_penalty": {"section_marker": "연결재무제표 주석", "score": -1},
    "investment_metric_terms": ("소유지분율", "지분율", "장부금액", "투자자산"),
    "summary_metric_terms": ("계속영업손익", "계속영업이익", "계속영업손실", "총포괄손익"),
    "default_unit": "백만원",
    "period_fallback": "",
    "role_labels": {
        "prior_ownership_ratio": "기초 지분율",
        "ownership_ratio": "기말 지분율",
        "investment_carrying_amount": "투자장부금액",
        "continuing_profit_loss": "계속영업손익",
        "continuing_loss": "계속영업손실",
        "total_comprehensive_profit_loss": "총포괄손익",
        "total_comprehensive_loss": "총포괄손실",
    },
    "investment_sentence_template": "{entity_label}의 {parts}입니다.",
    "summary_sentence_template": "요약 손익은 {parts}입니다.",
    "number_pattern": r"\(?-?\d[\d,]*(?:\.\d+)?\)?%?",
    "part_templates": {
        "prior_current_ratio": "{prior_label}은 {prior_percent}, {current_label}은 {percent}",
        "current_ratio": "{current_label}은 {percent}",
        "amount": "{amount_label}은 {amount}{unit}",
    },
}

EVIDENCE_COMPRESSION_GUIDANCE_POLICY: Dict[str, Any] = {
    "trend_instruction": "시계열 변화와 근거에 직접 있는 원인만 짧게 정리하세요.",
    "trend_context_instruction": (
        "시계열 변화와 함께 실적에 직접 기여한 운영 요인을 1~2개까지 정리하세요. "
        "계약 목적이나 기대효과보다 근거 문서에 실제 성과 원인으로 명시된 요인을 우선하세요."
    ),
    "trend_output_style": "2~4문장.",
    "trend_context_output_style": "2~5문장.",
    "instructions": {
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
        "qa": "질문에 직접 답하는 핵심 사실만 짧게 답하세요.",
    },
    "output_styles": {
        "numeric_fact": "최대 1문장.",
        "business_overview": "각 부문의 구체적 제품/역할이 포함된 3~5개의 bullet.",
        "risk": "항목별로 이름과 짧은 설명(1~2줄)이 함께 있는 bullet. 항목 수는 evidence 범위를 넘기지 말 것.",
        "comparison": "짧은 bullet 비교.",
        "qa": "짧고 직접적으로.",
    },
    "coverage_notes": {
        "sparse": "근거가 제한적입니다. evidence에 직접 적힌 claim과 quote_span만 사용하세요.",
        "conflicting": "근거가 서로 상충하면 충돌을 명시하세요.",
    },
    "driver_phrase_joiner": ", ",
    "driver_pair_joiner": "와",
    "driver_final_joiner": ", 그리고 ",
    "driver_addition_template": "또한 {clause}도 실적 성장에 기여했습니다.",
}

EVIDENCE_EXTRACTION_POLICY: Dict[str, Any] = {
    "extra_rules_by_query_type": {
        "risk": (
            "\n- 리스크 유형명은 컨텍스트에 명시된 단어만 사용하세요. "
            "컨텍스트에 없는 리스크 카테고리(예: '운영위험', '규제위험' 등)를 새로 만들지 마세요."
            "\n- [중요] 컨텍스트에 여러 개의 독립적인 리스크 항목이 나열되어 있다면, "
            "임의로 그룹화하거나 생략하지 마세요. "
            "문서에 존재하는 각 항목을 하나씩 독립적인 EvidenceItem으로 빠짐없이 추출하세요."
            "\n- 문서에서 여러 하위 항목이 상위 범주 아래 묶여 있다면(예: '시장위험' 아래 환율변동위험·이자율변동위험·주가변동위험), "
            "각 하위 항목의 parent_category 필드에 해당 상위 범주 명칭을 그대로 적으세요. "
            "상위 범주가 문서에 명시되어 있지 않으면 None으로 두세요."
        ),
        "business_overview": (
            "\n- [중요] 컨텍스트에 여러 개의 독립적인 사업 부문이나 항목이 나열되어 있다면, "
            "임의로 그룹화하거나 생략하지 마세요. "
            "문서에 존재하는 각 항목을 하나씩 독립적인 EvidenceItem으로 빠짐없이 추출하세요."
            "\n- 문서에서 여러 하위 항목이 상위 부문 아래 묶여 있다면(예: 'DS부문' 아래 메모리·시스템반도체·파운드리), "
            "각 하위 항목의 parent_category 필드에 해당 상위 부문 명칭을 그대로 적으세요. "
            "상위 범주가 문서에 명시되어 있지 않으면 None으로 두세요."
        ),
    },
    "extra_rules_by_operation_family": {
        "narrative_summary": (
            "\n- 질문이 영향/원인을 묻는 경우, 계약 목적이나 예상효과만 적힌 문단보다 "
            "실제 실적 변화의 원인·기여 요인을 설명하는 문단을 우선하세요."
            "\n- 질문 focus terms에 고유명사, 약어, 괄호 표현, 정책/규제/대응/필요성 관련 표현이 있으면, "
            "그 표현들이 들어간 원문 문장을 독립 EvidenceItem으로 추출하세요. "
            "질문 focus terms가 직접 들어간 문장을 넓은 시장/연혁 배경 설명으로 대체하지 마세요."
            "\n- 가능하면 서로 다른 관점의 근거를 2개 이상 추출하세요. "
            "예: (1) 실적 변화나 성장률을 직접 설명하는 문단, "
            "(2) 그 변화의 배경 driver를 문서 표현 그대로 설명하는 문단."
            "\n- '주요 계약' 문단은 실제 성과 영향 문단이 부족할 때만 보조 근거로 사용하세요."
        ),
    },
    "focus_term_stopwords": (
        "2023년",
        "2022년",
        "전년",
        "대비",
        "계산",
        "계산해",
        "계산하고",
        "사업보고서",
        "사업보고서에서",
        "요약",
        "요약해",
        "설명",
        "설명해",
        "대한",
        "등",
        "줘",
    ),
    "max_focus_terms": 12,
    "focus_term_token_pattern": r"[가-힣A-Za-z0-9()]+",
    "focus_term_particle_suffix_pattern": r"(?:에서|에게|으로|로|을|를|은|는|이|가|의|에|와|과|도|만)$",
    "prompt_template": """당신은 기업 공시 분석 보조자입니다.
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
질문 focus terms: {focus_terms}

사용 가능한 source_anchor:
{available_anchors}

컨텍스트:
{context}
""",
}

EVIDENCE_RUNTIME_POLICY: Dict[str, Any] = {
    "location_subject_pattern": r"[가-힣A-Za-z0-9]+(?:에서|에서는)[가-힣A-Za-z0-9]+(?:은|는)",
    "lookup_aggregate_result_pattern": (
        r"(차이|차액|격차|합계|합산|더한|더하면|총합|차감|뺀|비율|비중|성장률|증가율|감소율|몇\s*배|더\s*(?:큽|작|많|적))"
    ),
    "direct_numeric_lookup_instruction": (
        "{focused} 원문 수치만 찾으세요. "
        "차이, 합계, 비율, 증감액 같은 계산 결과가 아니라 해당 항목 자체의 값을 추출하세요."
    ),
    "numeric_not_found_answer": "관련 공시 문서에서 요청한 수치를 찾지 못했습니다.",
    "no_direct_evidence_answer": (
        "관련 공시 문서에서 질문에 직접 답할 수 있는 근거를 찾지 못했습니다. "
        "공시 문서에 정보가 없거나, 현재 검색 결과만으로는 확인하기 어렵습니다."
    ),
    "duplicate_claim_reason": "같은 claim을 반복 설명함",
    "aggregate_supported_reason": "여러 evidence의 합집합을 요약한 supported 문장",
    "overextended_reason": "근거 claim보다 과도하게 일반화되거나 확장됨",
    "compression_prompt_template": (
        "당신은 한국 기업 공시(DART) 분석 전문가입니다.\n"
        "아래 structured evidence를 질문 범위에 맞게 압축해 typed output을 만드세요.\n\n"
        "Compression 규칙:\n"
        "- evidence에 없는 내용은 추가하지 마세요.\n"
        "- 먼저 question_relevance가 high인 evidence만으로 답 구성을 시도하세요.\n"
        "- claim을 기본 단위로 사용하고, 필요할 때만 quote_span의 원문 표현을 그대로 가져오세요.\n"
        "- allowed_terms에 없는 새로운 분류명이나 핵심 용어는 만들지 마세요.\n"
        "- 질문이 요구하지 않은 배경 설명, 예시, 장황한 연결 문장은 넣지 마세요.\n"
        "- 가능한 한 중복 claim을 합치고, 같은 사실은 한 번만 말하세요.\n"
        "- draft_answer와 draft_points 안에 `[회사 | 연도 | ...]` 형태의 source_anchor 원문을 절대 그대로 쓰지 마세요. 출처 추적은 selected_claim_ids로만 수행합니다.\n"
        "{coverage_note}\n\n"
        "질문 유형 지침:\n{instruction}\n\n"
        "출력 형식 지침:\n{output_style}\n\n"
        "Structured Evidence:\n{evidence}\n\n"
        "질문: {query}\n\n"
        "반드시 다음 필드를 채우세요.\n"
        "- selected_claim_ids: 실제로 사용한 evidence_id만\n"
        "- draft_points: 중복을 제거한 핵심 포인트 목록\n"
        "- draft_answer: 사용자에게 보여줄 짧은 초안 답변\n"
    ),
    "validation_prompt_template": (
        "다음 답변 초안을 structured evidence와 대조해 문장 단위로 검증하고 typed output을 만드세요.\n\n"
        "Validator 규칙:\n"
        "- 새 정보는 절대 추가하지 마세요.\n"
        "- 근거로 뒷받침되지 않는 문장, 구, 세부사항만 삭제하거나 더 짧게 축소하세요.\n"
        "- 질문에 직접 필요하지 않은 배경 설명은 삭제하세요.\n"
        "- 숫자, 단위, 비율은 evidence의 quote_span 또는 claim 표기를 그대로 유지하세요.\n"
        "- risk: evidence에 없는 상위 taxonomy나 재분류를 만들지 마세요.\n"
        "- business_overview / risk: 여러 evidence에 흩어진 정보를 하나의 문장이나 bullet로 종합한 경우, 각 표현이 evidence 합집합으로 뒷받침되면 supported로 판단하세요.\n"
        "- business_overview / risk: 특정 문장이 단일 evidence와 1:1로 대응하지 않아도, supporting_claim_ids의 합집합이 그 문장을 직접 지지하면 keep 할 수 있습니다.\n"
        "- duplicated claim은 하나만 남기세요.\n"
        "- 가능한 한 기존 source_anchor는 유지하세요.\n"
        "- 초안을 문장 단위로 나눈 뒤 각 문장을 아래 verdict 중 하나로 판정하세요.\n"
        "  - keep\n"
        "  - drop_overextended\n"
        "  - drop_unsupported\n"
        "  - drop_redundant\n"
        "- supporting_claim_ids에는 그 문장을 직접 지지하는 evidence_id만 넣으세요.\n"
        "- keep가 아닌 문장은 unsupported_sentences에도 넣으세요.\n"
        "- kept_claim_ids / dropped_claim_ids는 sentence_checks와 일관되게 작성하세요.\n"
        "- final_answer는 keep verdict를 받은 문장만 자연스럽게 이어 붙인 결과여야 합니다.\n"
        "- keep 문장이 하나도 없으면, 질문에 직접 답할 수 있는 근거를 찾지 못했다는 짧은 문장만 남기세요.\n\n"
        "질문 유형: {query_type}\n"
        "질문: {query}\n\n"
        "Structured Evidence:\n{evidence}\n\n"
        "초안 답변:\n{answer}\n\n"
        "반드시 다음 필드를 채우세요.\n"
        "- kept_claim_ids: 최종 답변에 실제로 남긴 evidence_id\n"
        "- dropped_claim_ids: 제거한 evidence_id\n"
        "- unsupported_sentences: 삭제하거나 축소한 문장/구\n"
        "- sentence_checks: 각 문장에 대한 verdict, reason, supporting_claim_ids\n"
        "- final_answer: 최종 사용자 답변\n"
    ),
    "numeric_extractor_prompt_template": (
        "당신은 재무 데이터 전문 분석가입니다.\n"
        "아래 질문에 답하기 위해 공시 문서 컨텍스트에서 정확한 수치를 추출하세요.\n\n"
        "지시사항:\n"
        "1. 표(Table)에서 행과 열의 교차점을 정확히 확인하세요.\n"
        "2. 당기/전기, 연결/별도, 금액 단위를 최우선으로 확인하세요.\n"
        "3. raw_value는 문서에서 찾은 숫자를 변환 없이 그대로 적으세요.\n"
        "4. final_value는 raw_value와 unit을 바탕으로 질문에 직접 답하는 자연스러운 한국어 한 문장으로 작성하세요.\n"
        "5. 수치를 찾지 못한 경우 raw_value와 final_value를 빈 문자열로 두세요.\n\n"
        "질문: {query}\n\n"
        "컨텍스트:\n{context}\n"
    ),
}

QUERY_FOCUS_MARKER_POLICY: Dict[str, Any] = {
    "strip_chars": "()[]{}'\"“”‘’,.·:;",
    "leading_connector_pattern": r"^(또는|및|등)\s+",
    "trailing_connector_pattern": r"\s+(또는|및|등)$",
    "trailing_particle_pattern": r"(에서|으로|로|에게|에는|에|은|는|이|가|을|를|과|와|도)$",
    "year_pattern": r"20\d{2}년?",
    "single_letter_pattern": r"[A-Za-z]",
    "parenthetical_pair_pattern": r"([가-힣A-Za-z0-9\s·./-]{2,40})\(([A-Za-z0-9\s·./-]{2,40})\)",
    "left_context_drop_patterns": (
        r"^.*(?:과|와|및|또는)\s+",
        r"^.*(?:에서|에는|으로|은|는|이|가|을|를|의)\s+",
    ),
    "quoted_pattern": r"[\"'“”‘’](.+?)[\"'“”‘’]",
    "acronym_pattern": r"\b[A-Z][A-Z0-9]{1,8}\b",
    "english_token_pattern": r"[A-Za-z][A-Za-z0-9./-]{2,}",
    "generic_token_pattern": r"[가-힣A-Za-z0-9]+",
    "label_template": "query_focus_{index}",
}

PERIOD_COMPARISON_COUNT_POLICY: Dict[str, Any] = {
    "sentence_split_pattern": r"(?<=[.!?。])\s+|(?<=[가-힣])\.(?=(?:20\d{2}|[가-힣]))",
    "year_pattern": r"(20\d{2})년?",
    "stated_change_pattern": (
        rf"(?:{KOREAN_PERIOD_COMPARISON_RE_FRAGMENT}|대비)\s*"
        r"(?P<value>[\-+]?\d[\d,]*(?:\.\d+)?)\s*(?P<unit>%|퍼센트)"
    ),
}

DIVIDEND_POLICY_ASSEMBLY_POLICY: Dict[str, Any] = {
    "amount_patterns": (
        r"(\d+\s*조\s*\d{1,3}(?:,\d{3})?\s*억원)",
        r"(\d{1,3}(?:,\d{3})+\s*억원)",
        r"(\d{1,3}(?:,\d{3})+\s*백만원)",
    ),
    "rank_patterns": {
        "trillion_eok": r"(\d+)\s*조(?:\s*(\d{1,3}(?:,\d{3})?))?\s*억원",
        "eok": r"(\d{1,3}(?:,\d{3})+)\s*억원",
        "million_krw": r"(\d{1,3}(?:,\d{3})+)\s*백만원",
    },
    "million_krw_to_eok_divisor": 100.0,
    "trillion_to_eok_multiplier": 10000,
    "clause_split_pattern": r"(?<=[.!?])\s+|\n+",
    "clause_max_chars": 240,
    "year_pattern": r"(20\d{2})년",
    "year_prefix_template": "{year}년 ",
    "preferred_policy_period_markers": ("2024", "2026"),
    "stale_policy_period_markers": ("2021", "2023"),
    "payout_priority_section_terms": ("이사의 경영진단",),
}


NARRATIVE_RETRIEVAL_POLICIES: tuple[Dict[str, Any], ...] = (
    {
        "name": "impact_context",
        "trigger_terms": ("영향", "기여", "원인", "요약", "인수"),
        "preferred_sections": (
            "IV. 이사의 경영진단 및 분석의견",
            "재무상태 및 영업실적",
            "나. 영업실적",
        ),
        "focus_terms": ("영향", "기여", "성장", "인수"),
        "causal_terms": ("영향", "기여", "성장", "인수"),
        "realized_terms": ("전년 대비",),
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
        "retrieval_query_suffixes": ("스마트스토어 브랜드스토어 성장",),
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
        "statement_types": ("cash_flow", "notes"),
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
        "policy_period_markers": ("2024", "2026"),
        "cash_generation_terms": ("잉여현금흐름", "free cash flow"),
        "payout_amount_patterns": (
            r"배당금(?:의)?\s*지급[^0-9]{0,24}(\d+\s*조(?:\s*\d{1,3}(?:,\d{3})?)?\s*억원)",
            r"배당금(?:의)?\s*지급[^0-9]{0,24}(\d{1,3}(?:,\d{3})+\s*억원)",
            r"배당금(?:의)?\s*지급[^0-9]{0,24}(\d{1,3}(?:,\d{3})+\s*백만원)",
        ),
        "payout_sentence_template": ("{year_prefix}연결 현금흐름표상 배당금 지급으로 유출된 현금은 {amount}입니다.",),
        "policy_sentence_prefix": ("사업보고서의 배당에 관한 사항에 따르면",),
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
        "rnd_subject_terms": ("연구개발",),
        "rnd_context_terms": ("비용", "총액", "계", "누계", "백만원"),
        "rnd_metric_label": ("연구개발비용",),
        "rnd_unit": ("백만원",),
        "rnd_min_value": (1_000_000,),
        "rnd_sentence_template": ("{year_label}{scope_label}{metric_label} 총액은 {amount}{unit}입니다.",),
        "scope_terms": ("연결",),
        "existing_answer_reuse_terms": ("연구개발",),
        "business_sentence_template": ("{entity} 부문의 전장 사업 방향은 {parts}을 중심으로 합니다.",),
        "focus_sentence_template": ("주요 기술 초점은 {parts}하는 데 있습니다.",),
        "product_phrase_suffix": ("등 전장제품",),
        "business_phrase_joiner": ("과 ",),
        "product_phrase_joiner": (", ",),
        "focus_phrase_joiner": ("하고, ",),
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
        "retrieval_query_suffixes": (
            "인플레이션 감축법 IRA 보호무역주의 대응 필요",
            "보호무역주의 핵심원자재법 적극적인 대응",
        ),
        "preferred_sections": (
            "IV. 이사의 경영진단 및 분석의견",
            "재무상태 및 영업실적",
            "나. 영업실적",
        ),
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


def active_numeric_section_hint_policies(query: str) -> List[Dict[str, Any]]:
    return [policy for policy in NUMERIC_SECTION_HINT_POLICIES if narrative_policy_matches(query, policy)]


def numeric_section_policy_preferred_sections(policies: Sequence[Dict[str, Any]]) -> List[str]:
    return narrative_policy_terms(policies, "preferred_sections")


def numeric_section_policy_statement_types(policies: Sequence[Dict[str, Any]]) -> List[str]:
    return narrative_policy_terms(policies, "statement_types")


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
