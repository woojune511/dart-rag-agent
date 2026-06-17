"""
DART XML parser and structure-aware chunker.

This parser:
- splits the filing by SECTION tags
- classifies sections with lightweight keyword rules
- preserves table structure as text
- creates rich chunk metadata for retrieval and debugging
"""

import logging
import os
import re
import json
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from langchain_text_splitters import RecursiveCharacterTextSplitter
from lxml import etree
from pydantic import BaseModel
from src.processing.block_collection import collect_blocks
from src.processing.chunking import (
    chunk_blocks,
    looks_like_table_header_row,
    split_long_table_row,
    split_table_by_rows,
    split_table_for_chunks,
    split_table_text_fragment,
    split_wide_table_by_columns,
)
from src.processing.section_extraction import (
    SectionParseTimeout,
    build_section_path,
    extract_sections,
)
from src.processing.table_records import (
    build_table_row_records,
    build_table_value_records,
    cell_looks_numeric,
    dedupe_preserve_order,
    extract_period_labels,
    infer_table_header_row_count,
    infer_table_row_axis,
    is_generic_value_label,
    merge_header_stack,
)
from src.processing.table_structure import (
    build_table_object,
    cell_span_int,
    extract_table_row_labels_from_grid,
    format_table_grid,
    grid_row_to_text,
    normalize_table_grid,
    table_has_spans,
)
from src.schema import RowRecord, TableObject, ValueRecord

logger = logging.getLogger(__name__)

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_ROMAN_HEADING_RE = re.compile(r"^[IVXLCDM]+\.\s")
_NUMERIC_HEADING_RE = re.compile(r"^\d+\.\s")
_SUBNUMERIC_HEADING_RE = re.compile(r"^\d+(?:-\d+)+\.\s")
_KOREAN_ALPHA_HEADING_RE = re.compile(r"^[가-하]\.\s")
_PAREN_NUMERIC_HEADING_RE = re.compile(r"^\(\d+\)")
_PAREN_KOREAN_HEADING_RE = re.compile(r"^\([가-하]\)")
_BARE_PAREN_HEADING_RE = re.compile(r"^\((?:\d+|[가-하])\)$")
_BRACKET_HEADING_RE = re.compile(r"^\[[^\]]+\]$")
_SPECIAL_HEADING_RE = re.compile(r"^【.+】$")
_EXAMPLE_NUMERIC_LIST_ITEM_RE = re.compile(r"^\d+\.\s.+\(\s*예:\s*.+\)$")
_COMPOUND_HEADING_MARKER_RE = re.compile(
    r"(?=(\[[^\]]+\]|\((?:\d+|[가-하])\)|\d+(?:-\d+)*\.\s|[가-하]\.\s))"
)
_ATTACHED_KOREAN_ALPHA_HEADING_RE = re.compile(r"(?<!^)([가-하]\.\s*)")
_INLINE_BODY_START_RE = re.compile(
    r"(\d{4}년|연결회사는|회사는|당사는|당사가|당기 및 전기 중|당기말 및 전기말 현재|당기말 현재)"
)
_INLINE_BODY_SEPARATOR_RE = re.compile(
    r"([①②③④⑤⑥⑦⑧⑨⑩]|-\s*[A-Za-z가-힣&]+(?:\s*[A-Za-z가-힣&]+)*\s*:)"
)
_PROBABLE_XML_MARKUP_RE = re.compile(
    r"^/?[A-Za-z_][A-Za-z0-9._:-]*(?:\s+[A-Za-z_][A-Za-z0-9._:-]*\s*=\s*(?:\"[^\"]*\"|'[^']*'))*\s*/?$"
)
_REFERENCE_SIGNAL_RE = re.compile(r"참고|참조")
_REFERENCE_QUOTE_CHARS = "\"'“”‘’「」『』"
_QUOTED_REFERENCE_PAIR_RE = re.compile(
    rf"[{_REFERENCE_QUOTE_CHARS}](?P<left>[^{_REFERENCE_QUOTE_CHARS}]+)[{_REFERENCE_QUOTE_CHARS}]\s*의\s*"
    rf"[{_REFERENCE_QUOTE_CHARS}](?P<right>[^{_REFERENCE_QUOTE_CHARS}]+)[{_REFERENCE_QUOTE_CHARS}]"
)
_QUOTED_REFERENCE_SINGLE_RE = re.compile(
    rf"[{_REFERENCE_QUOTE_CHARS}](?P<title>[^{_REFERENCE_QUOTE_CHARS}]+)[{_REFERENCE_QUOTE_CHARS}]"
    rf"(?:\s*(?:항목|사항|부분))?\s*(?:을|를)?\s*(?:참고|참조)"
)
DEFAULT_CHUNK_SIZE = 2500
DEFAULT_CHUNK_OVERLAP = 320
DEFAULT_SECTION_PARSE_WARN_SEC = float(os.getenv("DART_PARSER_SECTION_WARN_SEC", "0.5"))
DEFAULT_SECTION_PARSE_BUDGET_SEC = float(os.getenv("DART_PARSER_SECTION_BUDGET_SEC", "2.0"))
_UNIT_HINT_RE = re.compile(r"(천원|백만원|억원|%)")
_UNIT_CONTEXT_RE = re.compile(r"단위\s*[:：]?\s*(천원|백만원|억원|원|%)")
_SECTION_LABELS: List[Tuple[str, List[str]]] = [
    ("요약재무", ["요약재무정보"]),
    ("연결재무제표", ["연결재무제표"]),
    ("재무주석", ["재무제표 주석"]),
    ("재무제표", ["재무제표"]),
    ("기타재무", ["배당에 관한 사항", "자금조달에 관한 사항", "재무에 관한 사항"]),
    ("사업개요", ["사업의 개요"]),
    ("주요제품", ["주요 제품", "주요제품"]),
    ("원재료", ["원재료", "생산설비"]),
    ("매출현황", ["매출 및 수주", "수주상황"]),
    ("리스크", ["위험관리", "파생상품", "리스크"]),
    ("연구개발", ["연구개발", "주요계약"]),
    ("기타사업", ["기타 참고사항", "사업의 내용"]),
    ("회사개요", ["회사의 개요", "회사의 현황", "정관의 변경", "주식의 총수", "주주에 관한 사항"]),
    ("경영진단", ["경영진단", "분석의견"]),
    ("감사의견", ["감사의견", "내부감사", "내부통제", "감사제도", "감사위원"]),
    ("이사회", ["이사회", "회사의 기관"]),
    ("주주현황", ["주주에 관한 사항"]),
    ("임원현황", ["임원 및 직원", "임원의 보수"]),
    ("계열회사", ["계열회사"]),
    ("대주주거래", ["대주주"]),
    ("기타공시", ["투자자 보호", "우발부채", "제재", "작성기준일 이후", "상세"]),
    ("기타", []),
]

_CONTENT_RECLASSIFY: List[Tuple[str, List[str]]] = [
    ("리스크", ["위험관리", "위험요인", "리스크", "파생상품", "hedge"]),
    ("매출현황", ["매출", "수주", "매출 구성", "매출비중"]),
    ("원재료", ["원재료", "생산설비", "CAPA", "생산능력", "가동률"]),
    ("연구개발", ["연구개발", "R&D", "특허", "기술개발", "연구인력"]),
    ("임원현황", ["임원", "사내이사", "사외이사", "대표이사"]),
    ("경영진단", ["영업이익률", "매출총이익", "경영환경", "사업전략"]),
    ("사업개요", ["사업 개요", "주요 사업", "사업 부문", "글로벌"]),
]

_STRUCTURED_SECTION_PREFIXES = (
    "III. 재무에 관한 사항",
    "IV. 이사의 경영진단 및 분석의견",
)

_STRUCTURED_SECTION_PATHS = {
    "II. 사업의 내용 > 1. 사업의 개요",
    "II. 사업의 내용 > 4. 매출 및 수주상황",
    "II. 사업의 내용 > 5. 위험관리 및 파생거래",
    "II. 사업의 내용 > 6. 주요계약 및 연구개발활동",
    "II. 사업의 내용 > 7. 기타 참고사항",
}
_DATE_BRACKET_HEADING_RE = re.compile(r"^\[\d{4}년(?:\s*\d{1,2}월)?\]$")
_SENTENCEY_HEADING_ENDINGS = ("입니다", "있습니다", "합니다", "됩니다", "하여", "이며", "이고")
_LOW_VALUE_BRACKET_KEYWORDS = ("분석",)
_BRACKET_SECTION_LABEL_PREFIXES = (
    "II. 사업의 내용 > 5. 위험관리 및 파생거래",
    "II. 사업의 내용 > 7. 기타 참고사항",
    "III. 재무에 관한 사항 > 8. 기타 재무에 관한 사항",
    "IV. 이사의 경영진단 및 분석의견",
)
_SHORT_BRACKET_LABEL_MAX_CHARS = 8


class DocumentChunk(BaseModel):
    content: str
    metadata: Dict[str, Any]


def _normalize(text: str) -> str:
    return re.sub(r"[ \t]+", " ", text).strip()


_ROMAN_NUMERAL_NORMALISATION = {
    "Ⅰ": "I",
    "Ⅱ": "II",
    "Ⅲ": "III",
    "Ⅳ": "IV",
    "Ⅴ": "V",
    "Ⅵ": "VI",
    "Ⅶ": "VII",
    "Ⅷ": "VIII",
    "Ⅸ": "IX",
    "Ⅹ": "X",
    "Ⅺ": "XI",
    "Ⅻ": "XII",
}


def _canonicalize_reference_text(text: str) -> str:
    normalized = _normalize(text)
    for src, dest in _ROMAN_NUMERAL_NORMALISATION.items():
        normalized = normalized.replace(src, dest)
    normalized = normalized.replace("＞", ">").replace("〉", ">")
    normalized = re.sub(r"\s*>\s*", " > ", normalized)
    return normalized


def _summarize_for_context(text: str, max_len: int = 220) -> str:
    text = _normalize(text)
    if len(text) <= max_len:
        return text
    return text[: max_len - 1].rstrip() + "…"


def _classify_section(title: str) -> str:
    for label, keywords in _SECTION_LABELS:
        for kw in keywords:
            if kw in title:
                return label
    return "기타"


def _infer_heading_level(title: str) -> int:
    if _ROMAN_HEADING_RE.match(title) or _SPECIAL_HEADING_RE.match(title):
        return 1
    if _SUBNUMERIC_HEADING_RE.match(title):
        return 3
    if _NUMERIC_HEADING_RE.match(title):
        return 2
    if _KOREAN_ALPHA_HEADING_RE.match(title):
        return 3
    if _BRACKET_HEADING_RE.match(title):
        return 2
    if _PAREN_NUMERIC_HEADING_RE.match(title):
        return 4
    if _PAREN_KOREAN_HEADING_RE.match(title):
        return 5
    return 2


def _is_structured_section(section_path: str) -> bool:
    normalized = _normalize(section_path)
    if not normalized:
        return False
    if normalized in _STRUCTURED_SECTION_PATHS:
        return True
    return any(normalized.startswith(prefix) for prefix in _STRUCTURED_SECTION_PREFIXES)


def _sanitize_path_titles(path_titles: List[str]) -> List[str]:
    sanitized: List[str] = []
    levels: List[int] = []

    for raw_title in path_titles:
        title = _normalize(raw_title)
        if not title:
            continue

        level = _infer_heading_level(title)
        if level == 1:
            sanitized = [title]
            levels = [level]
            continue

        while levels and levels[-1] >= level:
            levels.pop()
            sanitized.pop()

        sanitized.append(title)
        levels.append(level)

    return sanitized


def _reclassify_by_content(text: str, label: str) -> str:
    if label not in ("기타사업", "기타"):
        return label
    for new_label, keywords in _CONTENT_RECLASSIFY:
        for kw in keywords:
            if kw in text:
                return new_label
    return label


def _dedupe_preserve_order(values: List[str]) -> List[str]:
    return dedupe_preserve_order(values)


def _extract_period_labels(text: str) -> List[str]:
    return extract_period_labels(text)


def _infer_period_focus(period_labels: List[str]) -> str:
    if not period_labels:
        return "unknown"
    if len(period_labels) >= 2:
        return "multi_period"
    label = period_labels[0]
    if label.startswith("전기"):
        return "prior"
    if label.startswith("당기") or re.fullmatch(r"20\d{2}", label):
        return "current"
    return "unknown"


def _infer_unit_hint(text: str) -> Optional[str]:
    normalized = _normalize(text)
    if not normalized:
        return None
    for line in normalized.splitlines():
        context_match = _UNIT_CONTEXT_RE.search(line)
        if context_match:
            return context_match.group(1)
    match = _UNIT_HINT_RE.search(normalized)
    if match:
        return match.group(1)
    if "%" in normalized:
        return "%"
    return None


def _extract_standalone_table_context_hint(table_object: Dict[str, Any]) -> Optional[str]:
    """Capture small period/unit tables that label the next real table.

    DART often inserts a tiny borderless table like `당기 | (단위 : 백만원)`
    immediately before the actual numeric table. These tables are not useful
    on their own, but their period/unit hint is critical for the following
    value table, especially when the main table itself does not repeat the
    current/prior marker.
    """
    table_text = _normalize(str(table_object.get("table_text") or ""))
    if not table_text:
        return None

    rows = [row for row in table_text.splitlines() if row.strip()]
    row_count = int(table_object.get("row_count") or 0)
    column_count = int(table_object.get("column_count") or 0)
    statement_title_hint = any(
        keyword in table_text
        for keyword in (
            "재무상태표",
            "포괄손익계산서",
            "손익계산서",
            "자본변동표",
            "현금흐름표",
        )
    )

    is_compact_context_table = row_count <= 2 and column_count <= 3
    is_statement_title_table = statement_title_hint and row_count <= 6 and column_count <= 2
    if not (is_compact_context_table or is_statement_title_table):
        return None

    combined = " ".join(rows)
    period_labels = _extract_period_labels(combined)
    unit_hint = _infer_unit_hint(combined)
    # Some filings place `(단위 : 백만원)` in a standalone table without an
    # accompanying period token. Those tiny unit-only tables should still
    # annotate the following real numeric table.
    if not period_labels and not unit_hint and not statement_title_hint:
        return None

    # Guard against accidentally swallowing real numeric tables: standalone
    # context tables are short and should not contain thousands-style amounts.
    if re.search(r"\d{1,3}(?:,\d{3})+", combined):
        return None

    hint_parts = [combined]
    if unit_hint and unit_hint not in combined:
        hint_parts.append(f"(단위: {unit_hint})")
    return _normalize("\n".join(hint_parts))


def _infer_statement_type(section_path: str, header_context: Optional[str]) -> str:
    combined = f"{_normalize(section_path)}\n{_normalize(header_context or '')}"
    if "요약재무정보" in combined:
        return "summary_financials"
    if "재무상태표" in combined:
        return "balance_sheet"
    if "포괄손익계산서" in combined or "손익계산서" in combined:
        return "income_statement"
    if "현금흐름표" in combined:
        return "cash_flow"
    if "자본변동표" in combined:
        return "changes_in_equity"
    if "부문정보" in combined or "영업부문" in combined:
        return "segment_note"
    if "재무제표 주석" in combined or "주석" in combined:
        return "notes"
    if "이사의 경영진단 및 분석의견" in combined:
        return "mda"
    return "unknown"


def _infer_consolidation_scope(section_path: str, header_context: Optional[str]) -> str:
    combined = f"{_normalize(section_path)}\n{_normalize(header_context or '')}"
    if "연결" in combined:
        return "consolidated"
    if "별도" in combined:
        return "separate"
    path_parts = [part.strip() for part in _normalize(section_path).split(">") if part.strip()]
    if any(re.search(r"(?:^|\s)\d+[.)]?\s*재무제표(?:\s+주석)?$", part) for part in path_parts):
        return "separate"
    return "unknown"


def _is_generic_value_label(text: str) -> bool:
    return is_generic_value_label(text)


def _is_probable_xml_markup(inner: str) -> bool:
    stripped = inner.strip()
    if not stripped:
        return False
    if stripped.startswith(("!", "?")):
        return True
    return bool(_PROBABLE_XML_MARKUP_RE.match(stripped))


def _sanitize_xml_like_text(raw: str) -> Tuple[str, int]:
    sanitized_parts: List[str] = []
    replacements = 0
    idx = 0
    raw_len = len(raw)

    while idx < raw_len:
        start = raw.find("<", idx)
        if start < 0:
            sanitized_parts.append(raw[idx:])
            break

        sanitized_parts.append(raw[idx:start])
        end = raw.find(">", start + 1)
        if end < 0:
            sanitized_parts.append(raw[start:])
            break

        candidate = raw[start + 1 : end]
        if _is_probable_xml_markup(candidate):
            sanitized_parts.append(raw[start : end + 1])
        else:
            replacements += 1
            sanitized_parts.append("&lt;")
            sanitized_parts.append(candidate)
            sanitized_parts.append("&gt;")
        idx = end + 1

    return "".join(sanitized_parts), replacements


def _looks_like_local_heading(text: str) -> bool:
    normalized = _normalize(text)
    if not normalized:
        return False
    if len(normalized) > 90:
        return False
    if _BARE_PAREN_HEADING_RE.match(normalized):
        return False
    if _EXAMPLE_NUMERIC_LIST_ITEM_RE.match(normalized):
        return False
    if normalized.endswith(_SENTENCEY_HEADING_ENDINGS):
        return False
    return any(
        pattern.match(normalized)
        for pattern in (
            _NUMERIC_HEADING_RE,
            _SUBNUMERIC_HEADING_RE,
            _KOREAN_ALPHA_HEADING_RE,
            _PAREN_NUMERIC_HEADING_RE,
            _PAREN_KOREAN_HEADING_RE,
            _BRACKET_HEADING_RE,
            _SPECIAL_HEADING_RE,
        )
    )


def _should_discard_bracket_heading(text: str, section_path: str) -> bool:
    normalized = _normalize(text)
    if not normalized or not _BRACKET_HEADING_RE.match(normalized):
        return False
    if _DATE_BRACKET_HEADING_RE.match(normalized):
        return True
    if section_path.startswith("IV. 이사의 경영진단 및 분석의견") and any(
        keyword in normalized for keyword in _LOW_VALUE_BRACKET_KEYWORDS
    ):
        return True
    return False


def _bracket_label_inner_length(text: str) -> int:
    normalized = _normalize(text)
    if len(normalized) >= 2 and normalized.startswith("[") and normalized.endswith("]"):
        normalized = normalized[1:-1]
    normalized = normalized.replace(" ", "")
    return len(normalized)


def _classify_bracket_heading(
    text: str,
    section_path: str,
    next_tag: Optional[str],
    has_body_segments: bool,
) -> str:
    normalized = _normalize(text)
    if not normalized or not _BRACKET_HEADING_RE.match(normalized):
        return "not_bracket"
    if _should_discard_bracket_heading(normalized, section_path):
        return "discard"
    if not has_body_segments and next_tag in {"TABLE", "TABLE-GROUP"}:
        return "table_label"
    if any(section_path.startswith(prefix) for prefix in _BRACKET_SECTION_LABEL_PREFIXES):
        if _bracket_label_inner_length(normalized) <= _SHORT_BRACKET_LABEL_MAX_CHARS:
            return "defer_section_label"
        return "section_label"
    return "discard"


def _should_promote_deferred_bracket_heading(heading: str, section_path: str) -> bool:
    normalized = _normalize(heading)
    if not normalized:
        return False
    if section_path.startswith("II. 사업의 내용 > 7. 기타 참고사항"):
        return bool(_PAREN_NUMERIC_HEADING_RE.match(normalized) or _PAREN_KOREAN_HEADING_RE.match(normalized))
    if section_path.startswith("III. 재무에 관한 사항 > 8. 기타 재무에 관한 사항"):
        return bool(_PAREN_NUMERIC_HEADING_RE.match(normalized) or _PAREN_KOREAN_HEADING_RE.match(normalized))
    if section_path.startswith("II. 사업의 내용 > 5. 위험관리 및 파생거래"):
        return bool(
            _KOREAN_ALPHA_HEADING_RE.match(normalized)
            or _PAREN_NUMERIC_HEADING_RE.match(normalized)
            or _PAREN_KOREAN_HEADING_RE.match(normalized)
        )
    return False


def _strip_noisy_heading_suffix(text: str) -> str:
    normalized = _normalize(text)
    if not normalized:
        return ""

    if not normalized.startswith(("(", "[")):
        return normalized

    boundary_match = _INLINE_BODY_SEPARATOR_RE.search(normalized)
    if not boundary_match or boundary_match.start() <= 0:
        return normalized

    candidate = _normalize(normalized[: boundary_match.start()])
    if candidate and _looks_like_local_heading(candidate):
        return candidate
    return normalized


def _prepare_stack_for_heading(stack: List[str], heading: str, section_path: str) -> List[str]:
    if not stack:
        return list(stack)

    top = _normalize(stack[-1])
    normalized = _normalize(heading)
    if not (_BRACKET_HEADING_RE.match(top) and normalized):
        return list(stack)

    if section_path.startswith("II. 사업의 내용 > 7. 기타 참고사항"):
        if not (_PAREN_NUMERIC_HEADING_RE.match(normalized) or _PAREN_KOREAN_HEADING_RE.match(normalized)):
            return list(stack[:-1])
    elif section_path.startswith("III. 재무에 관한 사항 > 8. 기타 재무에 관한 사항"):
        if not (_PAREN_NUMERIC_HEADING_RE.match(normalized) or _PAREN_KOREAN_HEADING_RE.match(normalized)):
            return list(stack[:-1])
    elif section_path.startswith("IV. 이사의 경영진단 및 분석의견"):
        return list(stack[:-1])

    return list(stack)


def _push_heading(stack: List[str], heading: str, section_path: str = "") -> List[str]:
    normalized = _strip_noisy_heading_suffix(heading)
    if not normalized:
        return list(stack)

    next_stack = _prepare_stack_for_heading(stack, normalized, section_path)
    level = _infer_heading_level(normalized)
    next_levels = [_infer_heading_level(value) for value in next_stack]

    while next_levels and next_levels[-1] >= level:
        next_levels.pop()
        next_stack.pop()

    next_stack.append(normalized)
    return next_stack


def _split_compound_heading_text(text: str) -> List[str]:
    normalized = _strip_noisy_heading_suffix(text)
    if not normalized or not _looks_like_local_heading(normalized):
        return [normalized] if normalized else []

    body_start = _INLINE_BODY_START_RE.search(normalized)
    cutoff = body_start.start() if body_start else len(normalized)

    positions = [match.start() for match in _COMPOUND_HEADING_MARKER_RE.finditer(normalized)]
    positions.extend(
        match.start(1)
        for match in _ATTACHED_KOREAN_ALPHA_HEADING_RE.finditer(normalized)
        if match.start(1) < cutoff
    )
    positions = sorted({pos for pos in positions if 0 <= pos < cutoff})
    if len(positions) <= 1:
        return [normalized]

    if positions[0] != 0:
        positions.insert(0, 0)

    segments: List[str] = []
    for idx, start in enumerate(positions):
        end = positions[idx + 1] if idx + 1 < len(positions) else len(normalized)
        segment = _normalize(normalized[start:end])
        if segment and _looks_like_local_heading(segment):
            segments.append(segment)

    return segments or [normalized]


def _split_inline_heading_body(text: str) -> Optional[Tuple[List[str], str]]:
    normalized = _normalize(text)
    if not normalized or not normalized.startswith(("(", "[")):
        return None

    body_start = _INLINE_BODY_START_RE.search(normalized)
    # Avoid the more permissive separator regex unless a colon is present.
    # This prevents pathological backtracking on long hyphenated prose that
    # still cannot match the "... :" inline heading pattern.
    if not body_start and ":" in normalized:
        body_start = _INLINE_BODY_SEPARATOR_RE.search(normalized)
    if not body_start or body_start.start() <= 0:
        return None

    heading_text = _normalize(normalized[: body_start.start()])
    body_text = _normalize(normalized[body_start.start() :])
    if not heading_text or not body_text or not _looks_like_local_heading(heading_text):
        return None

    return _split_compound_heading_text(heading_text), body_text


def _soft_heading_path(stack: List[str]) -> Optional[str]:
    headings = [_normalize(value) for value in stack if _normalize(value)]
    if not headings:
        return None
    if len(headings) == 1:
        return headings[0]
    if len(headings) == 2:
        return " > ".join(headings)
    return f"{headings[0]} > {headings[-1]}"


def _build_reference_index(raw_sections: List[Dict[str, Any]]) -> Dict[str, Any]:
    entries: List[Dict[str, Any]] = []
    path_map: Dict[str, str] = {}
    title_map: Dict[str, List[str]] = {}

    for section in raw_sections:
        path = str(section.get("path") or "").strip()
        title = str(section.get("title") or "").strip()
        path_titles = [str(value).strip() for value in section.get("path_titles", []) if str(value).strip()]
        if not path or not path_titles:
            continue

        canonical_path = _canonicalize_reference_text(path)
        canonical_title = _canonicalize_reference_text(title or path_titles[-1])
        entry = {
            "path": path,
            "canonical_path": canonical_path,
            "canonical_title": canonical_title,
            "path_titles": path_titles,
            "canonical_titles": [_canonicalize_reference_text(value) for value in path_titles],
        }
        entries.append(entry)
        path_map[canonical_path] = path
        title_map.setdefault(canonical_title, []).append(path)

    return {"entries": entries, "path_map": path_map, "title_map": title_map}


def _resolve_reference_path(
    left: Optional[str],
    right: str,
    reference_index: Dict[str, Any],
) -> Optional[str]:
    entries = list(reference_index.get("entries", []) or [])
    path_map = dict(reference_index.get("path_map", {}) or {})
    title_map = dict(reference_index.get("title_map", {}) or {})

    right_key = _canonicalize_reference_text(right)
    if left:
        left_key = _canonicalize_reference_text(left)
        exact_path = path_map.get(_canonicalize_reference_text(f"{left} > {right}"))
        if exact_path:
            return exact_path

        left_title_matches = title_map.get(left_key, [])
        if len(left_title_matches) == 1:
            candidate_prefix = _canonicalize_reference_text(left_title_matches[0])
            for entry in entries:
                if entry["canonical_path"].startswith(candidate_prefix + " > ") and entry["canonical_titles"][-1] == right_key:
                    return entry["path"]

        for entry in entries:
            titles = list(entry.get("canonical_titles", []) or [])
            if not titles:
                continue
            if titles[0] == left_key and titles[-1] == right_key:
                return entry["path"]
        return None

    exact_path = path_map.get(right_key)
    if exact_path:
        return exact_path

    title_matches = title_map.get(right_key, [])
    if len(title_matches) == 1:
        return title_matches[0]
    return None


def _extract_reference_section_paths(text: str, reference_index: Dict[str, Any]) -> List[str]:
    normalized = _normalize(text)
    if not normalized or not _REFERENCE_SIGNAL_RE.search(normalized):
        return []

    resolved_paths: List[str] = []
    seen_paths: set[str] = set()
    consumed_spans: List[Tuple[int, int]] = []

    for match in _QUOTED_REFERENCE_PAIR_RE.finditer(normalized):
        left = match.group("left")
        right = match.group("right")
        resolved = _resolve_reference_path(left, right, reference_index)
        if resolved and resolved not in seen_paths:
            seen_paths.add(resolved)
            resolved_paths.append(resolved)
        consumed_spans.append(match.span())

    masked_text = normalized
    for start, end in reversed(consumed_spans):
        masked_text = masked_text[:start] + (" " * max(0, end - start)) + masked_text[end:]

    for match in _QUOTED_REFERENCE_SINGLE_RE.finditer(masked_text):
        title = match.group("title")
        resolved = _resolve_reference_path(None, title, reference_index)
        if resolved and resolved not in seen_paths:
            seen_paths.add(resolved)
            resolved_paths.append(resolved)

    return resolved_paths


class FinancialParser:
    def __init__(
        self,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
        section_warn_sec: float = DEFAULT_SECTION_PARSE_WARN_SEC,
        section_parse_budget_sec: float = DEFAULT_SECTION_PARSE_BUDGET_SEC,
    ):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.section_warn_sec = max(0.0, section_warn_sec)
        self.section_parse_budget_sec = max(0.0, section_parse_budget_sec)
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=["\n\n", ".\n", "다.\n", "\n", ". ", " ", ""],
            length_function=len,
        )

    @staticmethod
    def _cell_span_int(cell, attr_name: str) -> int:
        return cell_span_int(cell, attr_name)

    def _normalize_table_grid(self, table_elem) -> List[List[str]]:
        return normalize_table_grid(table_elem)

    @staticmethod
    def _format_table_grid(grid: List[List[str]]) -> str:
        return format_table_grid(grid)

    @staticmethod
    def _table_has_spans(table_elem) -> bool:
        return table_has_spans(table_elem)

    @staticmethod
    def _extract_table_row_labels_from_grid(grid: List[List[str]], max_labels: int = 20) -> List[str]:
        return extract_table_row_labels_from_grid(grid, max_labels=max_labels)

    def _build_table_object(self, table_elem) -> Dict[str, Any]:
        return build_table_object(table_elem)

    @staticmethod
    def _grid_row_to_text(row: List[str]) -> str:
        return grid_row_to_text(row)

    @staticmethod
    def _cell_looks_numeric(text: str) -> bool:
        return cell_looks_numeric(text)

    def _infer_table_row_axis(self, row: List[str]) -> Tuple[str, List[str], set[int]]:
        return infer_table_row_axis(row)

    def _infer_table_header_row_count(self, grid: List[List[str]]) -> int:
        return infer_table_header_row_count(grid)

    @staticmethod
    def _merge_header_stack(parts: List[str]) -> List[str]:
        return merge_header_stack(parts)

    def _build_table_row_records(self, table_object: Dict[str, Any], unit_hint: str) -> List[Dict[str, Any]]:
        return build_table_row_records(table_object, unit_hint)

    def _build_table_value_records(
        self,
        row_records: List[Dict[str, Any]],
        *,
        table_id: str,
        unit_hint: str,
    ) -> List[Dict[str, Any]]:
        return build_table_value_records(
            row_records,
            table_id=table_id,
            unit_hint=unit_hint,
        )

    def _format_table(self, table_elem) -> str:
        return self._build_table_object(table_elem)["table_text"]

    def _extract_table_header_context(self, table_text: str, max_rows: int = 2) -> Optional[str]:
        rows = [row for row in table_text.split("\n") if row.strip()]
        if not rows:
            return None

        header_rows: List[str] = []
        for row in rows[:max_rows]:
            if self._looks_like_table_header_row(row):
                header_rows.append(row)

        if not header_rows:
            header_rows.append(rows[0])

        return _normalize("\n".join(header_rows))

    def _build_table_context_bundle(
        self,
        table_text: str,
        section_path: str,
        table_source_id: str,
        *,
        local_heading: Optional[str] = None,
        table_object: Optional[Dict[str, Any]] = None,
        context_prefix: Optional[str] = None,
    ) -> Dict[str, Any]:
        header_context = self._extract_table_header_context(table_text)
        row_labels_text = ""
        summary_text = header_context or table_text[:400]
        table_row_count = 0
        table_column_count = 0
        table_has_spans = False
        table_row_records_json = ""
        table_value_records_json = ""
        table_value_labels_text = ""
        table_object_json = ""
        if table_object:
            row_labels = list(table_object.get("row_labels") or [])
            row_labels_text = "\n".join(row_labels)
            table_row_count = int(table_object.get("row_count") or 0)
            table_column_count = int(table_object.get("column_count") or 0)
            table_has_spans = bool(table_object.get("has_spans"))
            summary_parts = [part for part in (header_context, " | ".join(row_labels[:8])) if part]
            if summary_parts:
                summary_text = _normalize("\n".join(summary_parts))
        bundle_context = "\n".join(
            part
            for part in (
                context_prefix or "",
                local_heading or "",
                header_context or "",
                table_text[:800],
            )
            if part
        )
        semantic_context = "\n".join(
            part
            for part in (
                context_prefix or "",
                local_heading or "",
                header_context or "",
            )
            if part
        )
        period_labels = _extract_period_labels(bundle_context)
        unit_hint = _infer_unit_hint(bundle_context)
        inferred_statement_type = _infer_statement_type(section_path, semantic_context or header_context)
        inferred_consolidation_scope = _infer_consolidation_scope(section_path, semantic_context or header_context)
        if table_object:
            table_row_records = self._build_table_row_records(table_object, unit_hint)
            if table_row_records:
                table_row_records_json = json.dumps(table_row_records, ensure_ascii=False)
            table_value_records = self._build_table_value_records(
                table_row_records,
                table_id=table_source_id,
                unit_hint=unit_hint or "",
            )
            if table_value_records:
                table_value_records_json = json.dumps(table_value_records, ensure_ascii=False)
                value_label_lines: List[str] = []
                seen_value_labels: set[str] = set()
                for record in table_value_records[:40]:
                    label = _normalize(
                        str(record.get("semantic_label") or record.get("row_label") or "")
                    )
                    value = _normalize(str(record.get("value_text") or ""))
                    if not label or not value:
                        continue
                    line = _normalize(f"{label} {value}")
                    if line in seen_value_labels:
                        continue
                    seen_value_labels.add(line)
                    value_label_lines.append(line)
                table_value_labels_text = "\n".join(value_label_lines)
            header_row_count = self._infer_table_header_row_count(list(table_object.get("grid") or []))
            table_model = TableObject(
                table_id=table_source_id,
                source_section_path=section_path,
                caption=local_heading or "",
                statement_type=inferred_statement_type,
                consolidation_scope=inferred_consolidation_scope,
                unit_hint=unit_hint or "unknown",
                period_labels=period_labels,
                period_focus=_infer_period_focus(period_labels),
                row_count=int(table_object.get("row_count") or 0),
                column_count=int(table_object.get("column_count") or 0),
                has_spans=bool(table_object.get("has_spans")),
                header_rows=[list(row) for row in list(table_object.get("grid") or [])[:header_row_count]],
                row_labels=row_labels,
                rows=[RowRecord(**record) for record in table_row_records],
                values=[ValueRecord(**record) for record in table_value_records],
                table_header_context=header_context or "",
                table_summary_text=summary_text,
            )
            table_object_json = table_model.model_dump_json()
        return {
            "table_source_id": table_source_id,
            "table_header_context": header_context,
            "period_labels": period_labels,
            "period_focus": _infer_period_focus(period_labels),
            "unit_hint": unit_hint,
            "statement_type": inferred_statement_type,
            "consolidation_scope": inferred_consolidation_scope,
            "header_propagated": False,
            "table_summary_text": summary_text,
            "table_row_labels_text": row_labels_text,
            "table_row_records_json": table_row_records_json,
            "table_value_records_json": table_value_records_json,
            "table_value_labels_text": table_value_labels_text,
            "table_object_json": table_object_json,
            "table_row_count": table_row_count,
            "table_column_count": table_column_count,
            "table_has_spans": table_has_spans,
        }

    def _extract_paragraph_heading_parts(
        self,
        paragraph_elem,
        structured: bool,
    ) -> Tuple[Optional[List[str]], List[Dict[str, Any]]]:
        if not structured:
            combined = _normalize("".join(paragraph_elem.itertext()))
            if not combined:
                return None, []
            if _BRACKET_HEADING_RE.match(combined):
                return [combined], []
            return None, [{"kind": "text", "text": combined}]

        parts: List[Dict[str, Any]] = []

        def append_text(value: Optional[str]):
            normalized = _normalize(value or "")
            if normalized:
                parts.append({"kind": "text", "text": normalized})

        def append_heading(value: Optional[str]):
            normalized = _normalize(value or "")
            if not normalized:
                return
            for heading in _split_compound_heading_text(normalized):
                parts.append({"kind": "heading", "text": heading})

        append_text(paragraph_elem.text)
        for child in paragraph_elem:
            candidate = _normalize("".join(child.itertext()))
            usermark = child.get("USERMARK", "") if hasattr(child, "get") else ""
            if child.tag == "SPAN" and "B" in usermark:
                inline_split = _split_inline_heading_body(candidate)
                if inline_split:
                    headings, body_text = inline_split
                    for heading in headings:
                        parts.append({"kind": "heading", "text": heading})
                    append_text(body_text)
                elif _looks_like_local_heading(candidate):
                    append_heading(candidate)
                else:
                    append_text("".join(child.itertext()))
            else:
                append_text("".join(child.itertext()))
            append_text(child.tail)

        if not parts:
            return None, []

        grouped: List[Dict[str, Any]] = []
        pending_text: List[str] = []

        def flush_text():
            if pending_text:
                grouped.append({"kind": "text", "text": _normalize(" ".join(pending_text))})
                pending_text.clear()

        for part in parts:
            if part["kind"] == "heading":
                flush_text()
                grouped.append(part)
            else:
                pending_text.append(part["text"])
        flush_text()

        if len(grouped) == 1 and grouped[0]["kind"] == "text":
            inline_split = _split_inline_heading_body(grouped[0]["text"])
            if inline_split:
                headings, body_text = inline_split
                return headings, [{"kind": "text", "text": body_text}]
            if _looks_like_local_heading(grouped[0]["text"]):
                return _split_compound_heading_text(grouped[0]["text"]), []

        promoted: List[Dict[str, Any]] = []
        idx = 0
        while idx < len(grouped):
            part = grouped[idx]
            if (
                part["kind"] == "heading"
                and idx + 1 < len(grouped)
                and grouped[idx + 1]["kind"] == "text"
                and _looks_like_local_heading(grouped[idx + 1]["text"])
            ):
                promoted.append(part)
                for heading in _split_compound_heading_text(grouped[idx + 1]["text"]):
                    promoted.append({"kind": "heading", "text": heading})
                idx += 2
                continue
            promoted.append(part)
            idx += 1

        leading_headings: List[str] = []
        body_segments: List[Dict[str, Any]] = []
        saw_body = False
        for part in promoted:
            if not saw_body and part["kind"] == "heading":
                leading_headings.append(part["text"])
                continue
            if part["kind"] == "text":
                saw_body = True
            body_segments.append(part)

        return (leading_headings or None), body_segments

    def _collect_blocks(
        self,
        section_elem,
        section_path: str,
        *,
        structured_override: Optional[bool] = None,
        deadline_monotonic: Optional[float] = None,
        timeout_label: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        return collect_blocks(
            section_elem,
            section_path,
            structured_override=structured_override,
            deadline_monotonic=deadline_monotonic,
            timeout_label=timeout_label,
            is_structured_section=_is_structured_section,
            normalize_text=_normalize,
            soft_heading_path=_soft_heading_path,
            build_table_object=self._build_table_object,
            extract_standalone_table_context_hint=_extract_standalone_table_context_hint,
            build_table_context_bundle=self._build_table_context_bundle,
            extract_paragraph_heading_parts=self._extract_paragraph_heading_parts,
            is_single_bracket_heading=lambda text: bool(_BRACKET_HEADING_RE.match(text)),
            classify_bracket_heading=_classify_bracket_heading,
            should_promote_deferred_bracket_heading=_should_promote_deferred_bracket_heading,
            push_heading=_push_heading,
        )

    def _split_table_by_rows(self, table_text: str) -> List[str]:
        return split_table_by_rows(
            table_text,
            chunk_size=self.chunk_size,
            normalize_text=_normalize,
        )

    def _looks_like_table_header_row(self, row_text: str) -> bool:
        return looks_like_table_header_row(row_text, chunk_size=self.chunk_size)

    def _split_table_text_fragment(self, text: str, max_len: int) -> List[str]:
        return split_table_text_fragment(text, max_len, normalize_text=_normalize)

    def _split_long_table_row(self, row_text: str, max_len: int) -> List[str]:
        return split_long_table_row(row_text, max_len, normalize_text=_normalize)

    def _split_wide_table_by_columns(self, table_text: str) -> Optional[List[str]]:
        return split_wide_table_by_columns(table_text)

    def _split_table_for_chunks(self, table_text: str) -> List[Dict[str, str]]:
        return split_table_for_chunks(
            table_text,
            chunk_size=self.chunk_size,
            normalize_text=_normalize,
        )

    def _chunk_blocks(self, blocks: List[Dict[str, Any]], section_path: str) -> List[Dict[str, Any]]:
        return chunk_blocks(
            blocks,
            section_path,
            chunk_size=self.chunk_size,
            text_splitter=self.text_splitter,
            summarize_for_context=_summarize_for_context,
            normalize_text=_normalize,
        )

    def _build_section_path(self, section_elem, title_text: str) -> List[str]:
        return build_section_path(
            section_elem,
            title_text,
            normalize_text=_normalize,
            sanitize_path_titles=_sanitize_path_titles,
        )

    def _extract_sections(self, root) -> List[Dict[str, Any]]:
        return extract_sections(
            root,
            normalize_text=_normalize,
            sanitize_path_titles=_sanitize_path_titles,
            is_structured_section=_is_structured_section,
            collect_blocks=self._collect_blocks,
            section_warn_sec=self.section_warn_sec,
            section_parse_budget_sec=self.section_parse_budget_sec,
            logger=logger,
        )

    def _parse_xml(self, file_path: str):
        parser = etree.XMLParser(recover=True, encoding="utf-8", huge_tree=True)
        try:
            raw_xml = Path(file_path).read_text(encoding="utf-8")
            sanitized_xml, replacement_count = _sanitize_xml_like_text(raw_xml)
            if replacement_count:
                logger.info(
                    "Sanitized %s xml-like text spans before parsing [%s]",
                    replacement_count,
                    os.path.basename(file_path),
                )
            tree = etree.parse(BytesIO(sanitized_xml.encode("utf-8")), parser)
            return tree.getroot()
        except Exception as e:
            logger.error("XML parsing failed [%s]: %s", file_path, e)
            return None

    def _make_chunk_uid(self, source_metadata: Dict[str, Any], chunk_id: int, sub_chunk_idx: int) -> str:
        report_key = (
            source_metadata.get("rcept_no")
            or f"{source_metadata.get('company', 'unknown')}:{source_metadata.get('year', 'unknown')}"
        )
        return f"{report_key}:{chunk_id}:{sub_chunk_idx}"

    def parse_sections(self, file_path: str) -> List[Tuple[str, str, str]]:
        root = self._parse_xml(file_path)
        if root is None:
            return []

        raw_sections = self._extract_sections(root)
        result = [
            (
                section["title"],
                _classify_section(section["title"]),
                "\n\n".join(block["text"] for block in section["blocks"]),
            )
            for section in raw_sections
        ]
        logger.info("Extracted %s sections [%s]", len(result), os.path.basename(file_path))
        return result

    def extract_structure_outline(self, file_path: str) -> List[Dict[str, Any]]:
        root = self._parse_xml(file_path)
        if root is None:
            return []

        raw_sections = self._extract_sections(root)
        outline: List[Dict[str, Any]] = []
        for section in raw_sections:
            local_headings: List[str] = []
            seen_headings: set[str] = set()
            for block in section["blocks"]:
                local_heading = block.get("local_heading")
                if local_heading and local_heading not in seen_headings:
                    seen_headings.add(local_heading)
                    local_headings.append(local_heading)
            outline.append(
                {
                    "title": section["title"],
                    "path_titles": list(section["path_titles"]),
                    "path": section["path"],
                    "local_headings": local_headings,
                }
            )
        return outline

    def process_document(self, file_path: str, source_metadata: Dict[str, Any]) -> List[DocumentChunk]:
        root = self._parse_xml(file_path)
        if root is None:
            logger.warning("No parsing result: %s", file_path)
            return []

        raw_sections = self._extract_sections(root)
        if not raw_sections:
            logger.warning("No sections found: %s", file_path)
            return []

        reference_index = _build_reference_index(raw_sections)

        chunks: List[DocumentChunk] = []
        chunk_id = 0

        for section in raw_sections:
            section_title = section["title"]
            section_label = _classify_section(section_title)
            chunk_blocks = self._chunk_blocks(section["blocks"], section["path"])
            total_sub_chunks = len(chunk_blocks)

            for sub_chunk_idx, chunk_block in enumerate(chunk_blocks):
                refined_label = _reclassify_by_content(chunk_block["text"], section_label)
                block_type = chunk_block["block_type"]
                rcept_no = source_metadata.get("rcept_no", "unknown")
                parent_id = f"{rcept_no}::{section['path']}"
                table_header_context = chunk_block.get("table_header_context")
                period_labels = list(chunk_block.get("period_labels") or [])
                metadata: Dict[str, Any] = {
                    **source_metadata,
                    "section": refined_label,
                    "section_title": section_title,
                    "section_path": section["path"],
                    "local_heading": chunk_block.get("local_heading"),
                    "chunk_id": chunk_id,
                    "sub_chunk_idx": sub_chunk_idx,
                    "total_sub_chunks": total_sub_chunks,
                    "is_table": block_type == "table",
                    "block_type": block_type,
                    "table_context": chunk_block.get("table_context"),
                    "table_view": chunk_block.get("table_view"),
                    "table_source_id": chunk_block.get("table_source_id"),
                    "table_header_context": table_header_context,
                    "table_summary_text": chunk_block.get("table_summary_text"),
                    "table_row_labels_text": chunk_block.get("table_row_labels_text"),
                    "table_row_records_json": chunk_block.get("table_row_records_json"),
                    "table_value_records_json": chunk_block.get("table_value_records_json"),
                    "table_value_labels_text": chunk_block.get("table_value_labels_text"),
                    "table_object_json": chunk_block.get("table_object_json"),
                    "table_row_count": chunk_block.get("table_row_count"),
                    "table_column_count": chunk_block.get("table_column_count"),
                    "table_has_spans": chunk_block.get("table_has_spans", False),
                    "header_propagated": chunk_block.get("header_propagated", False),
                    "period_focus": chunk_block.get("period_focus") or _infer_period_focus([]),
                    "unit_hint": chunk_block.get("unit_hint") or _infer_unit_hint(
                        "\n".join(part for part in (section["path"], table_header_context or "") if part)
                    ),
                    "statement_type": chunk_block.get("statement_type")
                    or _infer_statement_type(section["path"], table_header_context),
                    "consolidation_scope": chunk_block.get("consolidation_scope")
                    or _infer_consolidation_scope(section["path"], table_header_context),
                    "parent_id": parent_id,
                }
                if period_labels:
                    metadata["period_labels"] = period_labels
                reference_paths = _extract_reference_section_paths(chunk_block["text"], reference_index)
                if reference_paths:
                    metadata["reference_section_paths"] = reference_paths
                    metadata["reference_parent_ids"] = [
                        f"{rcept_no}::{section_path}" for section_path in reference_paths
                    ]
                metadata["chunk_uid"] = self._make_chunk_uid(metadata, chunk_id, sub_chunk_idx)
                chunks.append(DocumentChunk(content=chunk_block["text"], metadata=metadata))
                chunk_id += 1

        logger.info(
            "Chunked %s chunks across %s sections [%s]",
            len(chunks),
            len(raw_sections),
            os.path.basename(file_path),
        )
        return chunks

    @staticmethod
    def build_parents(chunks: List[DocumentChunk], max_parent_len: int = 6000) -> Dict[str, str]:
        """청크 리스트에서 parent_id → 섹션 전체 텍스트 딕셔너리 생성.

        동일 parent_id(= rcept_no + section_path)를 공유하는 청크를 합쳐
        LLM에 전달할 넓은 컨텍스트 단위로 만든다.
        max_parent_len을 초과하면 앞부분만 보존한다.
        """
        from collections import defaultdict
        groups: Dict[str, List[str]] = defaultdict(list)
        for chunk in chunks:
            pid = chunk.metadata.get("parent_id")
            if pid:
                groups[pid].append(chunk.content)

        parents: Dict[str, str] = {}
        for pid, texts in groups.items():
            full = "\n\n".join(texts)
            parents[pid] = full[:max_parent_len] if len(full) > max_parent_len else full
        return parents


if __name__ == "__main__":
    import sys
    from collections import Counter

    logging.basicConfig(level=logging.INFO)

    reports_dir = os.path.join(_PROJECT_ROOT, "data", "reports")
    target = None
    for root_dir, _, files in os.walk(reports_dir):
        for filename in files:
            if filename.endswith(".html"):
                target = os.path.join(root_dir, filename)
                break
        if target:
            break

    if not target:
        print(f"[SKIP] No .html file found under {reports_dir}. Run dart_fetcher.py first.")
        sys.exit(0)

    print(f"\n--- FinancialParser smoke test: {os.path.basename(target)} ---\n")

    parser = FinancialParser(chunk_size=DEFAULT_CHUNK_SIZE, chunk_overlap=DEFAULT_CHUNK_OVERLAP)
    sections = parser.parse_sections(target)
    print(f"Total sections: {len(sections)}")

    meta = {
        "company": "삼성전자",
        "stock_code": "005930",
        "year": 2023,
        "report_type": "사업보고서",
        "rcept_no": "20230307000542",
    }
    chunks = parser.process_document(target, meta)
    print(f"Total chunks: {len(chunks)}")

    distribution = Counter(chunk.metadata["section"] for chunk in chunks)
    print("\n[Section distribution]")
    for label, count in distribution.most_common():
        print(f"  {label:>10}: {count}")

    risk_chunks = [chunk for chunk in chunks if chunk.metadata["section"] == "리스크"]
    if risk_chunks:
        sample = risk_chunks[0]
        print("\n[Risk sample]")
        print(f"  section_path: {sample.metadata['section_path']}")
        print(f"  block_type  : {sample.metadata['block_type']}")
        print(f"  table_ctx   : {sample.metadata.get('table_context')}")
        print(f"  content     : {sample.content[:200]}")
