from __future__ import annotations

from typing import Any, Dict, Iterable, List, Sequence, Tuple


KOREAN_PERIOD_COMPARISON_RE_FRAGMENT = r"(?:전년|전기|직전\s*연도)\s*대비"
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
    {
        "markers": ("EBITDA", "경영지표", "KPI"),
        "statement_types": ("mda", "summary_financials"),
    },
)

FINANCIAL_SEGMENT_SECTION_HINT_POLICY: Dict[str, Any] = {
    "markers": ("부문", "segment", "세그먼트"),
    "statement_types": ("segment_note",),
    "preferred_sections": (
        "부문정보",
        "영업부문",
        "영업실적",
        "(금융업)영업의 현황",
        "(금융업)사업의 개요",
        "영업의 현황",
        "매출현황",
    ),
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
        rf"(?P<unit>조\s*원?|십억\s*원|억\s*원?|백만\s*원|만\s*원|천\s*원|원|백만\s*달러|달러|USD|\$|%p|%|퍼센트|items?|{KOREAN_COUNT_UNIT_RE_FRAGMENT})"
    ),
    "inline_unit_aliases": {"억": "억원", "조": "조원", "십억": "십억원"},
    "canonical_units": {
        "KRW": {"dimension": "KRW", "display_unit": "원"},
        "USD": {"dimension": "USD", "display_unit": "USD"},
        "COUNT": {"dimension": "COUNT", "display_unit": ""},
        "PERCENT": {"dimension": "PERCENT", "display_unit": "%"},
    },
    "composite_value_pattern": (
        r"(?P<major>[\d,]+(?:\.\d+)?)\s*조"
        r"(?:\s*(?P<minor>[\d,]+(?:\.\d+)?)\s*억)?"
        r"\s*(?P<currency>원|달러|USD|\$)?"
    ),
    "composite_major_scale": 1_000_000_000_000.0,
    "composite_minor_scale": 100_000_000.0,
    "composite_default_currency": "KRW",
    "krw_scales": {
        "원": 1.0,
        "천원": 1_000.0,
        "만원": 10_000.0,
        "백만원": 1_000_000.0,
        "억원": 100_000_000.0,
        "십억원": 1_000_000_000.0,
        "조원": 1_0000_0000_0000.0,
    },
    "usd_scales": {"usd": 1.0, "$": 1.0, "달러": 1.0, "백만달러": 1_000_000.0},
    "count_scales": {"item": 1.0, "items": 1.0},
    # Source token boundaries are candidate identity inputs; keep them stable.
    "percent_units": ("%", "퍼센트"),
    "percent_display_units": ("%p",),
}


# Structural unit labels, not metric-specific ranking rules. A label can select
# only among units explicitly declared in the attached table context.
TABLE_COLUMN_UNIT_POLICY: Dict[str, Any] = {
    "declaration_pattern": r"(?:단위|units?)\s*[:：]\s*(?P<units>[^)\]\r\n]+)",
    "unit_separator_pattern": r"\s*(?:[,，;/]|\s+(?:and|및)\s+)\s*",
    "header_unit_pattern": r"[([]([^()\[\]]+)[)\]]",
    "context_relations": ("preceding_block", "caption"),
    "column_groups": (
        {"headers": ("비중", "비율", "구성비", "점유율", "share", "ratio", "percentage"), "dimensions": ("PERCENT",)},
        {"headers": ("금액", "공시금액", "amount", "value"), "dimensions": ("KRW", "USD")},
        {"headers": ("수량", "quantity", "count"), "dimensions": ("COUNT",)},
    ),
}


# Semantic count readings offered for exact, cell-owned axis labels. These are
# choices for the Compiler, not automatic unit declarations or metric recipes.
SOURCE_COUNT_UNIT_POLICY = (
    {"labels": ("건수",), "unit": "건"},
    {"labels": ("개수",), "unit": "개"},
    {"labels": ("인원수",), "unit": "명"},
    {"labels": ("count", "number of cases", "case count"), "unit": "COUNT"},
    {"labels": ("item count", "number of items"), "unit": "items"},
)


STRUCTURED_CELL_AFFINITY_POLICY: Dict[str, Any] = {
    "metric_terms": ("매출액", "매출", "영업수익", "수익"),
    "entity_surface_drop_terms": ("부문", "사업부", "사업"),
    "scoped_direct_row_markers": ("외부고객", "순매출액", "external customer", "net sales"),
    "scoped_adjustment_row_markers": ("부문간 제거", "제거한 금액", "intersegment", "elimination"),
    "year_pattern": r"20\d{2}\s*년?",
    "entity_token_split_pattern": r"[\s/|,]+",
    "aggregate_tokens": ("합계", "총계", "소계", "계", "전체", "total"),
    "aggregate_stage_tokens": {
        "subtotal": ("소계",),
        "final": ("합계", "총계", "계"),
    },
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


CONCEPT_RATIO_RESULT_UNIT_POLICY: Dict[str, Any] = {
    "multiplier_markers": ("배율",),
    "percent_markers": ("비율", "%", "퍼센트", "percentage"),
    "multiplier_unit": "배",
    "percent_unit": "%",
}


CANDIDATE_CONCEPT_CONFLICT_EXCLUSIVE_MARKER = "부채"
CAPEX_TOTAL_CONCEPT_KEY = "capital_expenditure_total"

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
    "location_entity_subject_pattern": r"(?:에서|에서는)(?P<subject>[가-힣A-Za-z0-9]+)(?:은|는)",
    "location_entity_temporal_subject_pattern": rf"^(?:{KOREAN_PERIOD_COMPARISON_RE_FRAGMENT}|20\d{{2}}년?|전년|전기|당기)",
    "location_entity_subject_bonus": 2.0,
    "location_entity_context_penalty": -1.0,
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
    {
        "name": "management_kpi",
        "trigger_terms": ("EBITDA", "경영지표", "KPI"),
        "preferred_sections": ("주요 경영지표", "경영지표", "영업성과", "영업실적", "경영진단"),
        "statement_types": ("mda", "summary_financials"),
    },
)


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
    "missing_focus_answer_template": "{missing_focus} 정보를 찾을 수 없습니다. {refusal_suffix}",
    "generic_result_label": "계산 결과",
    "growth_query_pattern": r"(성장률|증감률|증가율|전년\s*대비)",
    "percent_display_pattern": r"\d+(?:\.\d+)?\s*%",
    "growth_impact_markers": ("영향", "기여", "기인", "개선", "인수", "편입", "성장", "강화", "증가"),
    "growth_generic_focus_terms": ("부문", "매출", "성장률", "계산하고", "요약해", "영향", "실적", "전년", "대비"),
    "growth_metric_label_terms": ("성장률",),
    "growth_direction_metric_terms": ("매출",),
    "growth_supported_candidate_min_score": 12,
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
    "policy_required_realized_footnote_suffix_pattern": r"\s*주\d+\)?\s*$",
    "policy_required_realized_current_change_template": "{label}{topic_particle} {current_value}{unit}이며 전년대비 {change_value}{unit}입니다.",
    "policy_required_realized_current_template": "{label}{topic_particle} {current_value}{unit}입니다.",
}


CALCULATION_RENDER_POLICY: Dict[str, Any] = {
    "scope_labels": {"consolidated": "연결기준", "separate": "별도기준"},
    "scope_labels_en": {
        "consolidated": "consolidated basis",
        "separate": "separate basis",
    },
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
    "period_difference_direction_words": {"increase": "상승", "decrease": "하락", "flat": "변동 없음"},
    "period_difference_direction_phrase_template": " {direction_word}했습니다",
    "period_difference_neutral_direction_phrase": "입니다",
    "period_difference_answer_template": (
        "{first_sentence} {prior_period} {prior_label} {prior_value} 대비 "
        "{result_label}은 {result_value}{direction_phrase}."
    ),
    "adjusted_difference_query_terms": ("제외", "실질", "조정"),
    "adjusted_difference_exclusion_pattern": r"차감(?!전)",
    "source_display_units": ("천원", "백만원"),
    "converted_display_units": ("원", "억원", "조원"),
    "count_or_percent_normalized_units": ("COUNT", "PERCENT", "%", "퍼센트"),
    "percent_display_units": ("%", "%p"),
    "krw_normalized_unit": "KRW",
    "krw_display_units": ("원", "천원", "만원", "백만원", "억원", "십억원", "조원"),
    "krw_display_unit_scales": dict(NUMERIC_UNIT_NORMALIZATION_POLICY["krw_scales"]),
    "count_display_units": ("개", "명"),
    "inline_unit_right_boundary_block_pattern": r"[0-9A-Za-z가-힣]",
    "inline_unit_right_boundary_allowed_prefixes": (
        "이",
        "가",
        "은",
        "는",
        "을",
        "를",
        "와",
        "과",
        "로",
        "의",
        "에",
        "였",
        "다",
    ),
    "value_embedded_unit_markers": ("원", "억", "조", "%"),
    "krw_value_magnitude_markers": ("억", "조"),
    "operand_unit_bare_numeric_pattern": r"[\(\)\-]?\d[\d,]*(?:\.\d+)?",
    "operand_unit_ambiguous_krw_units": ("원", "krw"),
    "ratio_default_metric_label": "비율",
    "ratio_year_period_pattern": r"20\d{2}",
    "ratio_period_suffix_pattern": r"년$",
    "ratio_period_prefix_template": "{period}년 ",
    "consolidation_scope_answer_prefixes": {
        "consolidated": "연결기준 ",
        "separate": "개별기준 ",
    },
    "ratio_answer_template": "{period_prefix}{metric_label}은 {rendered_value}입니다.",
    "ratio_krw_suspicious_percent_threshold": 10000.0,
    "ratio_absolute_magnitude_markers": ("절대값", "절대 값", "absolute", "magnitude"),
    "ratio_component_answer_template": (
        "{period_prefix}{metric_label}은 {rendered_value}입니다. "
        "계산: {numerator_label} {numerator_value} / {denominator_label} {denominator_value}."
    ),
    "ratio_multi_component_answer_template": (
        "{period_prefix}{metric_label}은 {rendered_value}입니다. "
        "계산: ({numerator_expression}) / ({denominator_expression})."
    ),
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
}


CALCULATION_SLOT_POLICY: Dict[str, Any] = {
    "period_pattern": r"20\d{2}\s*년?",
    "fiscal_period_presence_pattern": r"제\s*\d+\s*기",
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


_COMPILER_COMPACT_JSON_INSTRUCTIONS = (
    "Return one JSON object matching the schema. Omit optional whitespace, indentation "
    "and line breaks outside JSON strings; do not add Markdown fences or text outside "
    "the object. This is a serialization rule only: retain every required field, output, "
    "claim, qualification and evidence reference. Do not shorten content to satisfy it. "
    "Do not remove or normalize whitespace inside string values, especially spaces, "
    "line breaks and punctuation in exact source quotations.\n\n"
)

_COMPILER_SHARED_INSTRUCTIONS = (
    _COMPILER_COMPACT_JSON_INSTRUCTIONS +
    "검색된 원문을 읽고 CompilerResponseV2의 outputs를 작성하세요. 별도의 독해 호출이나 원문 이름의 허용 목록은 없습니다.\n"
    "Compilation scope의 active_obligation_ids만 출력하며 각 request_unit_ids의 정확한 요청 구간과 한정 조건을 보존하세요. label/rationale은 상세 요청이나 공개 답변을 대신하지 않습니다. 같은 설명의 공유 조건과 독립적으로 요청된 설명 주제를 구별하세요.\n"
    "Compilation scope의 output_relationships는 요청에 연결된 공통 기준 관계입니다. relationship_declarations의 해당 관계 키에 공통 해석을 한 번만 쓰고, 각 ready result의 relationship_refs에 자신이 속한 모든 관계를 명시하세요. 모든 구성원이 보류하면 선언은 null로 둘 수 있습니다. 개별 원문의 basis 해석을 같은 문장으로 바꾸지 마세요. read_only_relationship_declarations는 이미 통과한 출력과 공유하는 고정 선언이므로 다시 작성하지 말고 해당 관계를 참조하세요. 관계 참조는 원문·주체·범위 검증을 대체하지 않으며, 겹치는 관계의 해석은 각각 독립적입니다.\n"
    "입력은 bounded excerpts입니다. 개별 본문이 완전해도 보고서 전체의 coverage를 뜻하지 않습니다. 근거가 부족하면 해당 출력의 status=missing 또는 ambiguous, result=null로 남기며 전체 문서의 부재를 단정하지 마세요.\n"
    "cohorts의 candidate_ids는 owner별 사용 권한입니다. 동일한 출처 조건의 요구사항은 노출된 근거를 공유할 수 있지만 숨은 후보, 다른 보고서·제한 섹션·명시적 측정 기간·연결 범위는 공유하지 않습니다. 검색 힌트/주체 문자열 차이는 금지 사유가 아닙니다.\n"
    "source_sections/source_section_bindings와 상위 출력의 제한을 모두 지키세요. 제목·본문에 언급됐다는 이유로 다른 절을 사용할 수 없습니다. evidence_bundle_constraints의 물리적 공유 행 option은 반드시 유지하세요.\n"
    "source_readings의 enclosing_contexts → preceding_contexts → bodies → following_contexts를 함께 읽으세요. source_continuation은 같은 본문의 이어지는 구간이고 surface_ref는 이미 제시된 동일 표면입니다. 각 surface의 같은 partition 안 연속 pieces만 하나의 원문 구간입니다. 서로 다른 셀/표면을 이어 붙이지 마세요.\n"
    "제목/행/열 계층과 본문이 실제 가리키는 주체·범위를 해석하세요. document_provenance의 공시 회사·year, parser local_heading, 인접 관계만으로 값이나 문장의 주체를 확정하지 않습니다. 다른 행 이름이나 미연결 제목을 빌려 쓰지 마세요.\n"
    "year는 보고서의 사업연도이며 접수일의 연도가 아닙니다. 숫자의 측정기간과 자동으로 같지는 않습니다. period/value_year는 period_source와 연결된 원문으로 확인하고 unknown이나 unbound_table 힌트만으로 기간을 확정하지 마세요.\n"
    "출력/요구사항/요청은 주어진 중첩 키를 쓰고, 후보와 표면은 짧은 참조만 선택하세요. 모델이 숫자 결과나 새로운 출처 ID를 만들지 않습니다. 의미 정확성은 Compiler의 책임이며 코드가 검증하는 것은 원문 연결과 실행 계약입니다.\n"
)

_COMPILER_NUMERIC_INSTRUCTIONS = (
    "direct result는 selection, derived result는 inputs와 formula입니다. 각 입력은 그 requirement 키 안에 두고 변수 이름을 variable로 적습니다. source_ref는 허용된 후보 또는 선언된 선행 출력입니다. requirements와 dependencies가 함께 있으면 선행 출력만 inputs.dependencies에 둡니다.\n"
    "직접 조회에서는 보고된 행의 조회와 여러 행의 합산 요청을 구별하세요. 전체 행·열 계층과 연결 문맥이 요청 주체·항목·범위를 뒷받침하면 그 보고된 값을 선택하세요. 하위·유사 이름 행이나 같은 값이 함께 있다는 사실만으로 요청되지 않은 합계를 상정하거나 모호하다고 하지 마세요. 반대로 계층만으로 포함·제외·합산 관계를 단정하지 않습니다. 보류한다면 원문에 남은 실제 대안 해석이나 필요한 근거의 공백을 rationale에 설명하세요.\n"
    "숫자 대상·범위는 interpretation에 요청 구간과 해석한 subject/metric/scope를 남기세요. 선택한 셀의 전체 행·열 축은 코드가 그대로 연결하므로 axis_refs를 쓰지 않습니다. 문장 해석에는 interpretation.source_evidence_text로 자기 원문을 명시하세요. schema가 null을 허용할 때도 selection.context_evidence의 연결 문맥이 해석을 뒷받침하는 경우에만 null을 선택합니다. source_ref 선택만으로 주체·항목 해석 근거가 자동으로 채워지지 않습니다. 의미가 같은지는 문자 동일성으로 판정하지 않습니다.\n"
    "표 밖 문맥이 필요하면 selection.context_evidence에 원문 인용을 한 번만 적으세요: schema에 노출된 context_ref, 정확한 evidence_text, 대상·항목 해석 근거이면 supports_interpretation=true, 기간/범위 보완은 resolves의 field/value로 표현합니다. 각 문맥은 선택한 셀에 실제로 연결되어야 합니다. 해당 입력 schema에 문맥 필드가 없으면 쓰지 말고, 이미 축/메타데이터로 확인된 조건에 새 문맥을 만들지 마세요. context_bindings는 모델 출력 필드가 아닙니다.\n"
    "source_column_period_evidence가 있으면 같은 열의 원문 셀을 먼저 읽고, 그 셀이 선택값의 측정연도를 뜻할 때만 interpretation.period_ref로 자기 period_options 중 하나를 선택하세요. 숫자나 연도를 새로 쓰지 마세요. 다른 열의 연도, 표 앞 문장의 일부 인용, 사업연도로 이 열 연결을 대신할 수 없습니다. 연도 선택지가 없는 합계 등은 특정 연도 값으로 해석하지 말고 missing/ambiguous로 남기세요.\n"
    "period/value_year가 비어 있어도 선택 셀에 연결된 원문 문맥의 상대기간이 명확하면 해당 후보의 사업연도 year를 기준으로 해석할 수 있습니다. 당기는 그 사업연도, 전기는 직전 사업연도입니다. selection.context_evidence에 정확한 기간 인용과 resolves의 field=period/value=해석한 연도를 남기세요. 원문에 명시된 연도가 있으면 우선하며, 사업연도가 없거나 기간이 모호하면 상대기간을 특정 연도로 채우지 말고 missing/ambiguous로 남기세요. 다른 셀·표의 기간이나 year만으로 측정기간을 만들지 마세요.\n"
    "prose 숫자는 source_ref로 선택합니다. 코드가 해당 후보의 전체 값 span을 원문 그대로 연결하므로 selection.evidence_text를 쓰지 않습니다. 표 셀은 기존 물리 출처를 사용합니다. 문맥 해석은 명시적 보고서/기간/연결 범위 충돌을 덮지 않습니다.\n"
    "비교 수식은 연결된 요청에서 기준점과 비교점을 먼저 해석하세요. comparison_request_unit_id로 소유한 요청 구간을 선택하고, 기준 입력의 variable은 reference, 비교 입력은 target으로 지정하여 formula에도 그 이름을 쓰세요. 요청 원문은 코드가 그대로 연결하므로 다시 쓰지 않습니다. 비교가 아닌 계산은 comparison_request_unit_id=null입니다. 입력의 기간 라벨이나 나열 순서는 비교 방향을 정하지 않습니다. 시간상 앞·뒤나 관행적인 증가율로 요청한 방향을 대체하지 마세요. 코드는 요청·변수 연결만 확인하며 방향의 의미를 대신 판단하지 않습니다.\n"
    "원문 부호/배율을 유지하고 필요한 의미 변환은 formula에 표현하세요. 부호 있는 값과 크기는 다릅니다: (abs(A)-abs(B))/abs(B)*100, (A-B)/abs(B)*100, (A-B)/B*100은 서로 다른 비교입니다. 원하는 답의 부호로 고르지 말고 비교 대상과 분모를 rationale에 설명하세요.\n"
    'formula는 operation/arguments 단계 배열이며 마지막 단계가 결과입니다. inputs 변수는 {{"variable":"이름"}}, 앞 단계의 결과는 {{"step":1부터 시작하는 앞 단계 번호}}로 사용합니다. 모든 단계는 마지막 결과에 기여해야 합니다. 괄호/쉼표/연산자 토큰을 나열하지 마세요. add/subtract/multiply/divide/power는 arguments 두 개를 순서대로 계산하고 positive/negative는 부호, identity는 인수 그대로, min/max/abs/round/log/exp는 같은 이름의 함수를 뜻합니다. 중립 숫자 0/1/100은 문자열 인수입니다. 요청 수량은 사용하는 인수 위치에 {{"value":수량,"request_unit_id":"소유한 요청 주소","interpretation":"해석"}}를 넣으세요. 별도 request_inputs/이름/상수 목록, origin/source_text를 쓰지 않습니다. 코드는 소유한 요청 구간 전체를 보존하며 부정·대조 조건을 포함한 전체 지시를 해석하세요. 숫자 표기와 자연어 수량의 계약은 같습니다. 입력 개수는 문자열 "binding_count"로 쓰며 코드가 source/dependency inputs만 셉니다. 모든 inputs 변수는 사용하고 이름을 중복하지 마세요. 원문·선행 계산값은 inputs로 선택하며 요청 수량으로 복사하지 않습니다. 요청 연결은 수량 해석의 의미 정확성 증명이 아닙니다. 분모 0을 작은 상수로 보정하지 마세요.\n'
    "단위 차원과 scale은 코드가 추론합니다. 원문 배율을 formula에 재적용하지 말고 display_unit은 표시 의도만 적으세요. 백분율과 percentage-point를 구별하며 나눗셈 비율을 %로 계산할 때만 formula의 *100이 필요합니다.\n"
    "source_display는 필수 nullable 선택이며 선택하면 최종 주 표시값이 됩니다. 명시적인 요청이 원문 우선 기본값보다 우선합니다. 연결된 요청 구간에서 원하는 결과가 원문 보고값인지, 입력으로 계산한 값인지, 둘 다인지 먼저 판단하세요. 계산값만 요청하면 source_display=null로 두고 원문 보고값으로 대체하지 마세요. 두 값이 같아도 요청 의도에 따라 결정합니다.\n"
    "원문 보고값이 요청 결과와 부합할 때만 동일 의미의 원문 파생값을 선택하세요. 별도 표시 지시가 없으면 원문 우선·계산 병기를 적용합니다. source_display_reason에는 단순히 원문 값이 있다는 사실이 아니라 요청과 선택/null의 관계를 쓰세요. 선택해도 formula/원시 입력을 유지하고, 차이를 억지로 맞추거나 근거 없는 반올림 설명을 만들지 마세요.\n"
    "interpretation.scope.basis는 그 선택 원문의 개별 해석입니다. 공통 기준 관계에 속한 숫자 출력도 각 선택 원문의 interpretation을 제공해야 합니다. 공통 기준 문장을 복사하여 개별 근거의 차이를 덮지 마세요. 동일 기준의 의미 판단과 실제 동일 행 사용 여부는 별개입니다. compatibility_refs는 실제 호환성 근거만 가리키며 출처 충돌을 허용하지 않습니다.\n"
    "직접 조회의 compatibility_refs는 선택값의 범위를 보완하는 owner 노출 narrative 후보에만 쓰세요. 선택한 셀의 축·메타데이터나 selection.context_evidence로 필요한 범위가 확인되면 []로 둡니다. 선택값과 동일 원문 문맥에 연결된 witness가 있어야 하며, 같은 보고서·주제·유사한 숫자를 반복하는 다른 절만으로는 충분하지 않습니다. context_evidence의 context_ref를 이 목록에 복사하거나 보조 근거로 선택값의 해석·명시적 출처·기간 충돌을 덮지 마세요.\n"
    "재시도의 read_only_dependency_outputs는 검증된 계산값이지 원문 표시값이 아닙니다. 허용된 dependency ID를 source_ref로 쓰고 상수로 복사하거나 accepted 출력을 다시 작성하지 마세요. 그 candidate IDs는 provenance일 뿐 선택 권한이 아닙니다.\n"
)

_COMPILER_NARRATIVE_INSTRUCTIONS = (
    "narrative result는 subjects입니다. 각 subject에 선택된 원문의 주체 표기, 별도 support, 그리고 text/evidence를 가진 claims를 중첩하세요. subject ID/requirement ID를 selection에 반복 작성하거나 expression을 만들지 않습니다.\n"
    "주체 철자·대소문자·문장부호·단어 경계·집단 범위를 보존하세요. 줄바꿈/연속 공백만 표시용으로 바꿀 수 있고 원문 위치가 유일해야 합니다. 제목에 이름과 본문에 사실이 각각 있다는 것만으로 그 주체의 사실이 되지는 않습니다. 대명사, 다른 주체, 부정과 전체/일부 범위를 원문 문맥으로 읽으세요.\n"
    "support와 fact evidence는 독립 선택입니다. 각 요구사항 키 안에 source_ref, surface_ref, first_piece_ref, last_piece_ref를 적고 시작/끝을 포함한 동일 partition의 연속 구간만 선택하세요. 공통 주체/보조 근거는 own에 둘 수 있지만 필수 requirement를 충족하지는 않습니다. 다른 셀/원문은 별도 selection으로 종합합니다.\n"
    "각 claim의 모든 문장·절은 선택한 fact evidence가 뒷받침해야 합니다. 요약·비교·부연에서도 주체별 행위와 대상, 조건·정도·부정·시제를 유지하세요. 서로 다른 행위를 하나로 묶어 다른 대상에 적용하지 마세요. 원문 표현을 그대로 반복할 필요는 없지만, 요청 충족에 불필요한 재진술로 새 의미를 더하지 마세요.\n"
    "claim의 숫자는 그 claim의 fact evidence에 있는 표기만 사용하세요. 공유 support나 다른 claim/미선택 주변 값은 사실과 숫자의 대체 근거가 아닙니다. text에 주체가 없으면 코드가 그 주체 라벨을 붙이지만 관계를 검증했다고 주장하지는 않습니다.\n"
    "요청한 구분·관계·한계를 text에서 실제로 설명하세요. 전체/주요 구성을 한 사례로 대신하거나 한 구성원의 사실을 집단 전체로 넓히지 마세요. 인과를 말하려면 원문이 결과와 요인을 직접 연결해야 하며 일반 배경이나 동시 변화로 원인을 만들지 않습니다.\n"
    "kind=narrative 본문/읽기용 표 행은 일반 evidence로 읽습니다. numeric 셀을 행 설명으로만 읽을 때는 해당 셀의 전체 행 계층에 속하는 정확한 row_description_quote를 선택하고 숫자 operand로 재해석하지 마세요.\n"
    "source_defined_group_selection이 complete_physical_row면 required_candidate_ids의 모든 셀을 해당 requirement에서 선택하고 원문의 항목 이름과 값을 빠뜨리지 마세요. 표준 항목을 추정해 추가하지 않습니다.\n"
    "의미상 segment/basis 적용은 scope_applicability_fields로 명시할 수 있습니다. 연결 범위 unknown은 연결된 근거로 보완할 수 있으나 명시적 보고서/기간/연결 충돌은 그대로 금지됩니다. basis_interpretation은 이 출력 원문의 개별 해석이며 다른 출력과 같은 문구일 필요는 없습니다.\n"
    "unvalidated_narrative_drafts/unvalidated_compiler_response는 실패한 모델 초안이지 정답·원문·새 권한이 아닙니다. 오류 위치를 보고 현재 허용된 근거로만 수정하세요. 수정 권한이 없는 계획 오류나 실제 근거 부족을 새 출처 발명으로 메우지 마세요.\n"
    "{row_description_instructions}\n"
)

_COMPILER_INPUT_FIELDS = (
    "원본 질문:\n{query}\n\n"
    "Compilation scope:\n{compilation_scope}\n\n"
    "Answer obligations:\n{obligations}\n\n"
    "{output_responsibility_context}"
    "Source bundles, candidate cohorts, and candidates_by_id:\n{candidate_catalog}\n\n"
    "재시도 피드백(없으면 -):\n{retry_feedback}\n"
)

CALCULATION_PROMPT_POLICY: Dict[str, Any] = {
    'semantic_program_subject_selection_repair_invariant': (
        "source_selection_check compares your declared subject with only the exact text your selected addresses resolve to. "
        "It is read-only feedback, not evidence permissions, an attribution verdict or replacement addresses. "
        "Pieces are mechanical addresses, not complete semantic units. If supported, select a continuous first-to-last "
        "range containing the complete source-copied subject within one permitted partition; never join cells/surfaces. "
        "contains_declared_subject is literal containment. Optional subject_grounding reports whitespace-only correspondence "
        "within those same selections; multiple source occurrences require a narrower selection or abstention. "
        "Only whitespace layout may differ, never spelling, punctuation, word boundaries or entity scope. "
        "Otherwise revise the subject/claim from permitted source support or abstain. Do not copy diagnostics into the output schema."
    ),
    'semantic_program_narrative_repair_invariant': (
        "Nest each claim under its subject with separate support and claim evidence. "
        "Keep valid fact ranges; repair the failed surface/piece references using currently permitted addresses. "
        "Share subject support only within that subject, never previous-claim inheritance or filing metadata. "
        "Each selection uses source_ref, surface_ref, first_piece_ref and last_piece_ref inside its requirement key "
        "within one partition. Code extracts exact bytes; do not recopy evidence_text or join cells. "
        "Shared subject support does not authorize a claim's numbers. Text may omit the subject; code labels it. "
        "Repair requested coverage, not just the error. Drafts are unvalidated, not evidence or permissions; "
        "revise unsupported attribution or abstain, never infer it from co-occurrence alone."
    ),
    'semantic_program_output_responsibility_context_template': (
        "Output responsibility context:\n{context}\n"
        "This is planned output responsibility, not source evidence or proof that another output succeeded. "
        "Use it to distinguish the active explanation from separately requested topics. "
        "Retain conditions and relationships needed to make an active answer accurate, even when shared. "
        "Emit only active obligation IDs; select evidence only from their existing visible cohorts. "
        "Do not merge or delete outputs because they share a subject, request, source or wording.\n\n"
    ),
    'semantic_program_prompt_template': (
        _COMPILER_SHARED_INSTRUCTIONS + _COMPILER_NUMERIC_INSTRUCTIONS
        + _COMPILER_NARRATIVE_INSTRUCTIONS + _COMPILER_INPUT_FIELDS
    ),
    'semantic_program_narrative_prompt_template': (
        _COMPILER_SHARED_INSTRUCTIONS + _COMPILER_NARRATIVE_INSTRUCTIONS + _COMPILER_INPUT_FIELDS
    ),
    'semantic_program_row_description_instructions': "- row_description_quote_options가 있는 numeric 후보에서 숫자 자체가 아니라 행 설명만 사용하려면 evidence binding의 row_description_quote를 지정할 수 있습니다. options는 기존 검증을 통과하는 원문 축 문구 예시이며, 다른 부분 인용도 source text와 row_label/row_headers 모두에 정확히 있어야 합니다. 문서 ID·연도, physical table/row ID가 필요하며 scalar 숫자를 인용하면 안 됩니다. 이 권한은 문서 범위의 설명만 허용하고 측정기간을 확정하거나 알려진 scope 충돌을 덮지 않습니다. 일반 kind=narrative 근거나 scalar를 사용하는 근거에서는 비워 두세요.\n",
    'semantic_program_render_templates': {
            "item": "{label}: {value}",
            "item_sentence_ko": "{subject}{topic_particle} {value}입니다.",
            "source_display_comparison": "{source} (recalculated {calculated})",
            "source_display_comparison_ko": "{source} (재계산값 {calculated})",
            "derived_inputs": "Inputs: {items}.",
            "derived_inputs_ko": "입력값은 {items}입니다.",
            "derived_input_item": "{label} {value}",
            "derived_input_joiner": ", ",
            "narrative": "{text}",
            "missing": "필요한 근거를 충분히 확인하지 못했습니다: {labels}",
            "korean_text_pattern": "[가-힣]",
            "period_year_pattern": "(?:19|20)\\d{2}",
            "period_year_suffix": "년",
            "company_possessive_suffix": "의",
        }
,
    'semantic_program_prompt_limits': {
            "numeric_candidates": 96,
            "narrative_candidates": 32,
            "required_input_candidates_per_group": 4,
            "numeric_source_bundles_per_owner": 2,
            "narrative_candidates_per_owner": 6,
            "compatibility_narrative_candidates_per_numeric_obligation": 2,
            "numeric_source_chars": 420,
            "narrative_source_chars": 600,
            "narrative_source_window_chars": 1200,
            "narrative_source_total_chars": 4800,
        }
,
}


SEMANTIC_REQUIRED_EVIDENCE_POLICY: Dict[str, int] = {
    "max_seed_candidates": 8,
    "max_narrative_candidates_per_group": 6,
}


# Whole labels only: a calendar spelling is context, not an inferred entity.
# Do not search this grammar inside names or use it to assign a value's year.
CALENDAR_PERIOD_LABEL_PATTERN = (
    r"(?i)(?:FY\s*)?(?:['’]\s*)?(?:\d{4}|\d{2})"
    r"(?:\s*년(?:\s*\d{1,2}\s*월(?:\s*\d{1,2}\s*일)?)?"
    r"|[./-]\d{1,2}(?:[./-]\d{1,2})?\.?)?(?:\s*말)?"
)


ANNUAL_RELATIVE_PERIOD_LABEL_POLICY = (
    # Cell/header labels only; do not match these inside prose or subject words.
    (0, r"(?<!\w)당기(?:말)?(?!\w)"),
    (-1, r"(?<!\w)전기(?:말)?(?!\w)"),
    (-2, r"(?<!\w)전전기(?:말)?(?!\w)"),
    (0, r"(?i)^(?:current|closing|ending)(?:[ _](?:period|balance))?$"),
    (-1, r"(?i)^(?:prior|previous|opening|beginning)(?:[ _](?:period|balance))?$"),
)


SEMANTIC_CANDIDATE_POLICY: Dict[str, Any] = {
    "fiscal_period_ordinal_pattern": r"제\s*(\d+)\s*기",
    "local_subject_clause_pattern": (
        r"([가-힣A-Za-z0-9][^,;:!?|]{0,70}?)"
        r"(?:은|는|이|가|의|에서|에는)(?=\s|$)"
    ),
    "local_subject_latin_entity_pattern": (
        r"\b([A-Z][A-Za-z0-9&.\-]*(?:\s+[A-Z][A-Za-z0-9&.\-]*){0,4})"
        r"(?:['’]s)?\b"
    ),
}


INDEX_PREFIX_METADATA_POLICY: Dict[str, Any] = {
    # Additional labels emitted by structural source prefixes. Narrative body
    # projection recognizes these without stripping arbitrary bracketed notes.
    "structural_line_labels": (
        "local_heading", "table_context", "table_row_labels", "table_value_labels",
        "parent_section", "parent_local_heading", "parent_preview",
    ),
    "line_labels": (
        "회사",
        "연도",
        "보고서",
        "섹션",
        "분류",
        "키워드",
        "선택사유",
        "statement_type",
        "consolidation_scope",
        "period_focus",
        "table_source_id",
        "unit_hint",
    ),
}


PLANNING_POLICY: Dict[str, Any] = {
    'source_section_inventory_max_sections': 256,
    'source_section_inventory_max_bytes': 65536,
    'source_axis_inventory_max_axes': 64,
    'source_axis_inventory_max_bytes': 16384,
    'requirement_planner_prompt_template': "당신은 DART 재무 질문의 검색 전 의미 요구사항을 정리합니다.\n"
            "계산 종류를 lookup, ratio, growth_rate 같은 고정 operation으로 분류하지 마세요.\n"
            "사용자가 최종 답변에서 확인해야 할 출력 각각을 answer obligation으로 표현하세요.\n\n"
            "규칙:\n"
            "- Request units는 코드가 원문 그대로 나눈 주소 목록입니다. 각 obligation의 request_unit_ids에 수행할 구간 ID를 연결하고 모든 구간을 하나 이상의 출력에 연결하세요. 하나의 출력을 여러 구간에, 하나의 구간을 여러 출력에 연결할 수 있습니다. 공통 조건은 관련 출력 모두에 연결하세요. 구간 수에 맞춰 출력을 늘리거나 새 ID를 만들지 마세요. label은 짧은 출력 이름으로 쓰고 상세 조건은 연결한 원문으로 보존합니다. rationale은 출력 요구를 대신하지 않습니다.\n"
            "- kind는 원문 값을 그대로 보여 주는 direct_value, 근거 값으로 계산하는 derived_value, 설명을 요구하는 narrative 중 하나입니다.\n"
            "- direct_value는 출력 자체가 원문 조회의 근거 소유자이므로 evidence_requirements를 빈 배열로 유지하고 evidence_mode는 declared_inputs로 둡니다. 요청한 주체·항목·범위·검색 힌트는 해당 obligation에 보존하며 별도 입력 requirement로 복제하지 마세요.\n"
            "- direct_value·derived_value의 display_unit에는 요청이 구체적으로 지정한 측정 단위와 배율만 보존합니다. 원·백만원·%·%p처럼 명시한 단위는 그대로 적으세요. 단위를 지정하지 않았거나 원문에서 단위를 따르라고 한 요청이면 빈 문자열로 두고, 검색 전 원문 단위를 추측하지 마세요.\n"
            "- 원문 단위 유지·원문 표기 그대로·정확한 값·소수점 자릿수 같은 지시는 측정 단위 이름이 아니라 표시 의도이므로 display_format과 연결된 원문 요청에 보존합니다. 구체적인 단위와 표시 형식을 함께 요청했다면 두 필드를 각각 채우세요. 명시된 단위가 지원되지 않더라도 display_unit에 그대로 남겨 검증에서 드러나게 하고, 빈 문자열·UNKNOWN·다른 단위로 대체하지 마세요.\n"
            "- narrative는 단일 수치 단위가 없으므로 display_unit을 반드시 빈 문자열로 두고, 요청한 표현 형식은 display_format에 적으세요. 서술에 필요한 사실·수치는 원문 요청과 evidence_requirements에 보존하며, 별도로 요청한 수치 출력은 direct_value 또는 derived_value로 유지하세요.\n"
            "- 하나의 질문에 여러 값과 설명이 필요하면 obligation을 모두 보존합니다.\n"
            "- 서술형 질문도 독립적으로 요청된 설명 주제마다 obligation을 보존합니다. 명시된 주제를 다른 주제의 설명으로 대체하거나 생략하지 마세요. intent와 출력 형식은 이 의무를 생략할 이유가 아닙니다.\n"
            "- 같은 설명을 한정하는 조건은 그 설명의 narrative obligation에 함께 담고 관련 request_unit_ids를 모두 연결하세요. 조건이 다른 request unit에 있다는 이유만으로 별도 출력을 만들지 마세요.\n"
            "- 같은 주어·문장·request unit을 공유한다는 이유로 독립적인 설명을 합치지 마세요. 출력 개수를 미리 정하지 마세요.\n"
            "- 질문이 근거를 특정 문서 절로 명시적으로 제한하면 source_section_bindings로 요청과 실제 위치를 연결하세요. first_request_unit_id와 last_request_unit_id는 그 제한이 담긴 연속 요청 구간의 처음과 마지막 ID입니다. 한 구간이면 같은 ID를 쓰세요. 번호·따옴표가 있는 제목은 여러 구간에 걸칠 수 있으므로 전체 경로와 한정 조건을 모두 포함하고 사이의 모든 구간을 해당 출력의 request_unit_ids에 소유하세요. 코드는 선택된 구간 전체의 원문·공백·문장 부호를 그대로 복사합니다. 요청 인용문이나 위치 숫자를 새로 쓰지 마세요. section_ids는 source_section_inventory에서 의미에 맞는 관측된 절 ID 목록입니다. 목록 안 ID는 대안이며 각 binding과 상위 obligation·근거 입력의 제한은 교집합입니다. 명시적으로 지정된 제목·경로는 다른 절로 바꿀 수 없습니다. 같은 제한을 source_sections에도 중복 작성하지 마세요.\n"
            "- 관측된 위치를 결정할 수 없거나 목록에서 찾지 못하면 요청 범위 ID를 유지하고 section_ids를 비워 unresolved로 남기세요. 제한을 삭제하거나 다른 절로 대체하지 마세요. inventory는 저장된 위치 목록일 뿐 본문이나 보고서 전체의 완전성 증명이 아니며 omitted_section_count가 있으면 일부 위치가 생략됐습니다. 명시적 절 제한이 없으면 source_section_bindings와 source_sections를 비우세요. 추정 검색 위치·본문 주제·ontology hint를 제한으로 만들지 마세요. source_sections는 질문이 정확히 명명한 제목·경로를 그대로 지정하는 기존 형식에만 쓰며, retrieval_hints와 label은 선택 권한이 아닙니다.\n"
            "- 질문이 특정 하위 항목 이름을 열거하지 않고 원문 표의 요약·구성·주요 항목처럼 source schema가 항목을 정하는 묶음을 요청하면 관행적인 표준 항목을 추정해 여러 direct_value obligation으로 만들지 마세요. 그 묶음은 하나의 narrative obligation으로 보존하고, 실제 원문 항목과 값은 검색 후 compiler가 선택하게 하세요. 질문에 명시된 개별 수치만 별도 direct_value 또는 derived_value obligation으로 만듭니다.\n"
            "- 위처럼 원문이 항목을 정하는 narrative 요약은 evidence_mode를 source_defined_group으로 지정하고 evidence_requirements는 비워 두세요. 런타임이 그 obligation의 label·scope·retrieval_hints·concept_hints를 보존한 하나의 필수 원문 그룹 requirement를 만듭니다. evidence_requirements나 검색 힌트에 관행적인 개별 항목을 추정해 넣지 마세요.\n"
            "- obligation_id는 짧고 고유하게 작성합니다. 런타임이 이후 안정 ID로 정규화합니다.\n"
            "- company, period, consolidation_scope, segment, basis처럼 의미가 다른 범위를 scope에 명시합니다.\n"
            "- scope.company는 공시 문서의 회사 범위입니다. 표 행이나 문장 안에서 실제 값의 주체가 되는 회사·사업·대상은 semantic_target.local_subjects에 적고 scope.company로 대체하지 마세요.\n"
            "- 각 obligation과 evidence requirement의 semantic_target을 작성하세요. local_subjects에는 질문이 직접 지목한 local entity만, concept_keys에는 아래 목록에 실제로 있는 ontology concept key만, metric_surfaces에는 질문에 보이는 지표 표현을 보존하세요. 정확한 concept가 없으면 concept_keys를 비운 채 metric_surfaces를 사용하세요.\n"
            "- local_subjects는 검색과 독해를 위한 요청 표현입니다. 이름·집단·부문 등의 한정 조건을 보존하고, 원문 이름의 허용 목록으로 만들지 마세요. 원문 축과 요청 표현의 의미 대응은 검색 후 Compiler가 근거와 함께 해석합니다. Planner는 접미사를 삭제하거나 원문 표현을 추측하여 요청을 고치지 않습니다.\n"
            "- 설명 표현을 주체 이름에 붙이지 않는 것은 요청 조건을 버리는 것이 아닙니다. 기간·지역·연결 범위·제외 조건·전체와 일부의 구별은 해당 request_unit_ids 원문과 적용 가능한 scope/requirements에 보존하세요. 같은 원칙을 각 evidence requirement의 실제 입력 주체에도 적용하며, 다른 입력의 주체나 최종 출력의 주체를 무조건 복사하지 마세요. 명확히 지목된 주체를 비우거나 질문에 없는 별칭을 만들어 불일치를 우회하지 마세요.\n"
            "- source_axis_inventory는 현재 보고서의 저장된 행·열 축 중 질문과 문자 그대로 겹치는 표기를 전체 계층·관측 출처와 함께 보여 주는 참고 자료입니다. local_subjects를 정하기 전에 원래 질문과 함께 읽어 이름과 주변 설명을 구분하세요. 겹친 문자열이 주체라는 뜻은 아니며 축에는 지표·기간도 포함됩니다. 짧은 이름이 보인다고 완전한 이름·집단·한정 조건을 줄이거나 다른 대상으로 치환하지 마세요. 질문에 없는 이름·별칭을 추가하지 마세요. 목록은 후보 선택 권한이나 인용 근거가 아니며, 생략·미일치·빈 목록은 원문 부재나 주체 불일치의 증명이 아닙니다.\n"
            "- 질문이 같은 entity를 여러 언어·이름으로 병기하면 local_subjects에 질문에 나온 각 표기를 모두 보존하세요. 질문에 없는 번역이나 다른 entity 이름은 추가하지 마세요.\n"
            "- derived_value는 사용자에게 표시할 결과 scope와 별도로, 계산에 필요한 각 원시 입력을 evidence_requirements에 선언합니다. 입력마다 고유 requirement_id, label, period 및 다른 scope, retrieval_hints를 적고 이 입력들은 사용자 출력 obligation으로 만들지 않습니다.\n"
            "- depends_on에는 이 obligation의 계산에 앞서 결과가 필요한 다른 answer obligation의 obligation_id만 적으세요. 같은 obligation의 원시 입력이나 evidence requirement ID는 적지 않습니다. 원시 입력 관계는 evidence_requirements만으로 선언합니다.\n"
            "- evidence_mode의 기본값은 declared_inputs입니다. 원시 계산 입력과 질문에 명시된 사실·관계에는 이 모드를 유지하세요. 이 모드의 narrative obligation은 답변에 필요한 각 사실과 관계, 특히 인과 설명을 evidence_requirements에 선언합니다. 대상 변화와 설명 요인을 함께 식별할 수 있는 label과 retrieval_hints를 사용하고, 다른 지표의 변화나 일반적 배경을 대상 변화의 직접 원인 근거로 대용하지 마세요.\n"
            "- 공통 기준이 필요한 출력은 output_relationships에 kind=shared_basis, output_ids와 그 관계를 요구한 request_unit_id 및 정확한 request_text를 기록하세요. 같은 회사·문장·주제라는 이유로 관계를 만들지 마세요. 독립 출력은 관계 목록에서 제외합니다. 계산상 의존성은 depends_on, 물리적 행 공유는 별도 근거 계약입니다.\n"
            "- ontology hints는 검색과 후보 의미 결합에 쓰는 제한된 vocabulary입니다. 질문에 맞는 정확한 concept가 없다고 비슷한 key를 만들거나 obligation을 삭제하지 마세요.\n"
            "- retrieval_hints와 retrieval_queries는 질문의 표현과 선택 가능한 ontology hint를 이용하되 계산식을 넣지 마세요.\n"
            "- 질문에 없는 회사·기간·범위를 만들지 말고 report_scope 기본값만 사용할 수 있습니다.\n"
            "- consolidation_scope의 consolidated 또는 separate는 질문이 그 범위를 명시한 경우에만 사용하고, report_scope의 문서 metadata나 관행으로 사용자 의도를 추정하지 마세요. 명시가 없으면 unknown으로 두세요.\n"
            "- scope 필드에는 실제 값만 쓰고 report_scope, unknown 같은 placeholder를 값으로 복사하지 마세요.\n\n"
            "질문:\n{query}\n\n"
            "Request units:\n{request_units}\n\n"
            "topic:\n{topic}\n\n"
            "intent:\n{intent}\n\n"
            "report_scope:\n{report_scope}\n\n"
            "관측된 source_section_inventory (위치 선택용, 인용 본문 아님):\n{source_section_inventory}\n\n"
            "관측된 source_axis_inventory (이름 해석 참고용, 선택 권한 아님):\n{source_axis_inventory}\n\n"
            "선택 가능한 ontology retrieval hints:\n{ontology_hints}\n"
,
    'money_surface_pattern': r"(?P<raw>\(?\d[\d,]*(?:\.\d+)?\)?)(?:\s*)"
            r"(?P<unit>조\s*\d[\d,]*(?:\.\d+)?\s*억원|조원|십억원|억원|백만원|천원|원|%)"
,
    'year_token_pattern': r"20\d{2}"
,
    'year_label_token_pattern': r"20\d{2}\s*년?"
,
    'money_surface_compound_unit_prefix': "조"
,
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
    "extra_rules_by_answer_mode": {
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
    "numeric_extractor_incomplete_retry_prompt_template": (
        "직전 structured 응답은 final_value를 작성했지만 raw_value를 비워 schema 계약을 위반했습니다.\n"
        "최종 문장을 역으로 파싱하지 말고, 아래 원문 컨텍스트에서 요청한 값을 다시 확인하세요.\n"
        "값을 찾았다면 raw_value에 원문 숫자를 그대로 넣고 unit과 final_value를 함께 채우세요.\n"
        "근거로 확정할 수 없다면 raw_value와 final_value를 모두 빈 문자열로 두세요.\n\n"
        "질문: {query}\n\n"
        "컨텍스트:\n{context}\n"
    ),
}

QUERY_FOCUS_MARKER_POLICY: Dict[str, Any] = {
    "strip_chars": "()[]{}'\"“”‘’,.·:;",
    "leading_connector_pattern": r"^(또는|및|등)\s+",
    "trailing_connector_pattern": r"\s+(또는|및|등)$",
    "trailing_particle_pattern": r"(에서|으로|로|에게|에는|에|은|는|이|가|을|를|과|와|의|도)$",
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
    "payout_priority_section_terms": ("이사의 경영진단",),
}


NARRATIVE_RETRIEVAL_POLICIES: tuple[Dict[str, Any], ...] = (
    {
        "name": "forward_looking_caution",
        "trigger_terms": (
            "예측",
            "예상",
            "전망",
            "미래",
            "forecast",
            "forward-looking",
            "projection",
        ),
        "exclusive_narrative_task": True,
        "format_preference_override": "paragraph",
        "retrieval_query_suffixes": (
            "예측정보 주의사항 미래 전망 가정 실제 결과 차이 수정 의무",
            "예측정보에 대한 주의사항 미래 사업환경 다양한 가정 불확실성",
        ),
        "preferred_sections": (
            "IV. 이사의 경영진단 및 분석의견 > 예측정보에 대한 주의사항",
            "예측정보에 대한 주의사항",
            "IV. 이사의 경영진단 및 분석의견",
        ),
        "paragraph_priority_sections": (
            "예측정보에 대한 주의사항",
            "IV. 이사의 경영진단 및 분석의견",
        ),
        "focus_terms": ("예측정보", "미래", "전망", "예상", "가정", "불확실성"),
        "causal_terms": ("가정", "불확실성", "차이", "수정", "의무"),
        "realized_terms": ("예측정보", "미래", "가정", "불확실성"),
        "support_answer_template": "사업보고서는 {support_sentence}",
    },
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
        "name": "credit_loss_scenario_context",
        "trigger_terms": ("신용손실충당금", "손실충당금", "기대신용손실", "대손상각비"),
        "retrieval_query_suffixes": (
            "기대신용손실 신용위험 미래경기 불확실성 시나리오 손실충당금",
            "보수적 충당금 적립 경기악화 위기상황 worse crisis 시나리오",
        ),
        "preferred_sections": (
            "III. 재무에 관한 사항 > 3. 연결재무제표 주석",
            "연결재무제표 주석",
            "신용위험",
            "금융상품",
            "IV. 이사의 경영진단 및 분석의견",
        ),
        "paragraph_priority_sections": (
            "IV. 이사의 경영진단 및 분석의견",
            "연결재무제표 주석",
            "신용위험",
        ),
        "focus_terms": ("신용손실충당금", "손실충당금", "기대신용손실", "신용위험"),
        "causal_terms": ("미래경기", "불확실성", "보수적", "충당금", "시나리오", "경기악화", "위기상황"),
        "realized_terms": ("신용손실충당금", "전년대비", "기대신용손실", "시나리오"),
    },
    {
        "name": "wealth_management_aum",
        "trigger_terms": ("자산관리", "WM", "wealth management"),
        "retrieval_query_suffixes": (
            "자산관리 WM 총관리자산 AUM 계열사별 총관리자산",
            "총관리자산 AUM 전년대비 증가 은행 증권 자산운용 부동산신탁",
        ),
        "preferred_sections": (
            "II. 사업의 내용 > 5. 재무건전성 등 기타 참고사항",
            "재무건전성 등 기타 참고사항",
            "그 밖에 투자의사결정에 필요한 사항",
            "영업의 현황",
        ),
        "paragraph_priority_sections": (
            "재무건전성 등 기타 참고사항",
            "그 밖에 투자의사결정에 필요한 사항",
        ),
        "focus_terms": ("자산관리", "wm", "총관리자산", "aum", "계열사별"),
        "causal_terms": ("증가", "전년대비", "성장", "영향"),
        "realized_terms": ("총관리자산", "AUM", "전년대비", "계열사별"),
        "required_realized_terms": ("총관리자산", "AUM"),
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
                    "기타포괄손익",
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
