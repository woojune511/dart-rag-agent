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
from typing import Any, Dict, List, Optional, Tuple

from langchain_text_splitters import RecursiveCharacterTextSplitter
from lxml import etree
from pydantic import BaseModel

logger = logging.getLogger(__name__)

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_SECTION_TAGS = frozenset({"SECTION-1", "SECTION-2", "SECTION-3"})
_ROMAN_HEADING_RE = re.compile(r"^[IVXLCDM]+\.\s")
_NUMERIC_HEADING_RE = re.compile(r"^\d+\.\s")
_SUBNUMERIC_HEADING_RE = re.compile(r"^\d+(?:-\d+)+\.\s")
_SPECIAL_HEADING_RE = re.compile(r"^【.+】$")
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
    return 2


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
    def __init__(self, chunk_size: int = DEFAULT_CHUNK_SIZE, chunk_overlap: int = DEFAULT_CHUNK_OVERLAP):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=["\n\n", ".\n", "다.\n", "\n", ". ", " ", ""],
            length_function=len,
        )

    def _format_table(self, table_elem) -> str:
        rows = []
        for tr in table_elem.findall(".//TR"):
            cells = [
                _normalize("".join(cell.itertext()))
                for cell in tr
                if cell.tag in ("TD", "TH", "TU")
            ]
            cells = [c for c in cells if c]
            if cells:
                rows.append(" | ".join(cells))
        return "\n".join(rows)

    def _collect_blocks(self, section_elem) -> List[Dict[str, Any]]:
        blocks: List[Dict[str, Any]] = []

        def process(elem):
            tag = elem.tag
            if tag in _SECTION_TAGS:
                return
            if tag == "TABLE-GROUP":
                for table in elem.findall("TABLE"):
                    text = self._format_table(table)
                    if text:
                        blocks.append({"text": text, "type": "table"})
                return
            if tag == "TABLE":
                text = self._format_table(elem)
                if text:
                    blocks.append({"text": text, "type": "table"})
                return
            if tag == "P":
                text = _normalize("".join(elem.itertext()))
                if text:
                    blocks.append({"text": text, "type": "paragraph"})
                return
            for child in elem:
                process(child)

        for child in section_elem:
            process(child)

        return blocks

    def _split_table_by_rows(self, table_text: str) -> List[str]:
        rows = table_text.split("\n")
        if len(rows) <= 1:
            return [table_text]

        header = rows[0]
        result: List[str] = []
        current = [header]
        current_len = len(header)

        for row in rows[1:]:
            if current_len + 1 + len(row) > self.chunk_size and len(current) > 1:
                result.append("\n".join(current))
                current = [header, row]
                current_len = len(header) + 1 + len(row)
            else:
                current.append(row)
                current_len += 1 + len(row)

        if current:
            result.append("\n".join(current))

        return result

    def _chunk_blocks(self, blocks: List[Dict[str, Any]], section_path: str) -> List[Dict[str, Any]]:
        result: List[Dict[str, Any]] = []
        pending_blocks: List[Dict[str, Any]] = []
        standalone_threshold = self.chunk_size // 2
        last_paragraph_context = section_path

        def flush_pending():
            if not pending_blocks:
                return

            merged = "\n\n".join(block["text"] for block in pending_blocks)
            table_chars = sum(len(block["text"]) for block in pending_blocks if block["type"] == "table")
            has_table = any(block["type"] == "table" for block in pending_blocks)
            block_type = "table" if table_chars > len(merged) * 0.5 else "paragraph"
            table_context = None
            if has_table:
                first_table = next(block for block in pending_blocks if block["type"] == "table")
                table_context = first_table.get("table_context") or section_path

            if len(merged) > self.chunk_size:
                for idx, sub in enumerate(self.text_splitter.split_text(merged)):
                    if not sub.strip():
                        continue
                    result.append(
                        {
                            "text": sub,
                            "block_type": block_type,
                            "table_context": table_context if idx == 0 else None,
                        }
                    )
            else:
                result.append(
                    {
                        "text": merged,
                        "block_type": block_type,
                        "table_context": table_context,
                    }
                )

            pending_blocks.clear()

        for block in blocks:
            text = block["text"]
            block_type = block["type"]

            if block_type == "paragraph":
                last_paragraph_context = _summarize_for_context(text)

            if block_type == "table":
                block = {
                    **block,
                    "table_context": last_paragraph_context or section_path,
                }

            if block_type == "table" and len(text) >= standalone_threshold:
                flush_pending()
                if len(text) > self.chunk_size:
                    for idx, sub in enumerate(self._split_table_by_rows(text)):
                        result.append(
                            {
                                "text": sub,
                                "block_type": "table",
                                "table_context": block["table_context"] if idx == 0 else None,
                            }
                        )
                else:
                    result.append(
                        {
                            "text": text,
                            "block_type": "table",
                            "table_context": block["table_context"],
                        }
                    )
            else:
                projected = "\n\n".join(item["text"] for item in pending_blocks + [block])
                if len(projected) > self.chunk_size and pending_blocks:
                    flush_pending()
                pending_blocks.append(block)

        flush_pending()
        return result

    def _build_section_path(self, section_elem, title_text: str) -> List[str]:
        path_titles: List[str] = []
        ancestors = list(section_elem.iterancestors())
        for ancestor in reversed(ancestors):
            if ancestor.tag not in _SECTION_TAGS:
                continue
            title_elem = next(
                (child for child in ancestor if child.tag == "TITLE" and child.get("ATOC") == "Y"),
                None,
            )
            if title_elem is None:
                continue
            ancestor_title = _normalize("".join(title_elem.itertext()))
            if ancestor_title:
                path_titles.append(ancestor_title)
        path_titles.append(title_text)
        return _sanitize_path_titles(path_titles)

    def _extract_sections(self, root) -> List[Dict[str, Any]]:
        sections: List[Dict[str, Any]] = []

        for section in root.iter():
            if section.tag not in _SECTION_TAGS:
                continue

            title_elem = next(
                (child for child in section if child.tag == "TITLE" and child.get("ATOC") == "Y"),
                None,
            )
            if title_elem is None:
                continue

            title_text = _normalize("".join(title_elem.itertext()))
            if not title_text:
                continue

            blocks = self._collect_blocks(section)
            if not blocks:
                continue

            path_titles = self._build_section_path(section, title_text)
            sections.append(
                {
                    "title": title_text,
                    "path_titles": path_titles,
                    "path": " > ".join(path_titles),
                    "blocks": blocks,
                }
            )

        return sections

    def _parse_xml(self, file_path: str):
        parser = etree.XMLParser(recover=True, encoding="utf-8", huge_tree=True)
        try:
            tree = etree.parse(file_path, parser)
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
                metadata: Dict[str, Any] = {
                    **source_metadata,
                    "section": refined_label,
                    "section_title": section_title,
                    "section_path": section["path"],
                    "chunk_id": chunk_id,
                    "sub_chunk_idx": sub_chunk_idx,
                    "total_sub_chunks": total_sub_chunks,
                    "is_table": block_type == "table",
                    "block_type": block_type,
                    "table_context": chunk_block.get("table_context"),
                    "parent_id": parent_id,
                }
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
