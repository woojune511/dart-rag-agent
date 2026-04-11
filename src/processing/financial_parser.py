"""
DART XML 공시 문서 파서.

DART ZIP에서 추출된 XML 파일을 파싱하여:
  - SECTION-N 태그 기준으로 섹션 분할 (<TITLE ATOC="Y"> 헤더 활용)
  - 섹션명 키워드 매핑으로 분류 레이블 부여
  - 청크 내용 기반 동적 재분류 (모호한 레이블 보완)
  - RecursiveCharacterTextSplitter로 적정 크기 청킹
  - DocumentChunk(content, metadata) 리스트 반환 (vector_store.py 호환)

DART XML 구조:
  BODY > SECTION-1 > TITLE(헤더) + [SECTION-2 > ...] + P(본문) + TABLE(표)

메타데이터 스키마:
  company, stock_code, year, report_type,
  section, section_title, chunk_id, sub_chunk_idx, total_sub_chunks, is_table
"""

import re
import logging
import os
from typing import List, Dict, Any, Tuple

from lxml import etree
from langchain_text_splitters import RecursiveCharacterTextSplitter

from processing.pdf_parser import DocumentChunk

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------
# 섹션 분류 테이블 (순서 중요: 더 구체적인 키워드가 앞에 위치)
# --------------------------------------------------------------------------
_SECTION_LABELS: List[Tuple[str, List[str]]] = [
    ("요약재무",     ["요약재무정보"]),
    ("연결재무제표", ["연결재무제표"]),
    ("재무주석",     ["재무제표 주석"]),
    ("재무제표",     ["재무제표"]),
    ("기타재무",     ["배당에 관한 사항", "자금조달에 관한 사항", "재무에 관한 사항"]),
    ("사업개요",     ["사업의 개요"]),
    ("주요제품",     ["주요 제품", "주요제품"]),
    ("원재료",       ["원재료", "생산설비"]),
    ("매출현황",     ["매출 및 수주", "수주상황"]),
    ("리스크",       ["위험관리", "파생거래"]),
    ("연구개발",     ["연구개발", "주요계약"]),
    ("기타사업",     ["기타 참고사항", "사업의 내용"]),
    ("회사개요",     ["회사의 개요", "회사의 연혁", "자본금 변동", "주식의 총수", "정관에 관한 사항"]),
    ("경영진단",     ["경영진단", "분석의견"]),
    ("감사의견",     ["감사의견", "외부감사", "내부통제"]),
    ("이사회",       ["이사회", "회사의 기관"]),
    ("주주현황",     ["주주에 관한 사항"]),
    ("임원현황",     ["임원 및 직원", "임원의 보수"]),
    ("계열회사",     ["계열회사"]),
    ("대주주거래",   ["대주주"]),
    ("기타공시",     ["투자자 보호", "우발부채", "제재", "작성기준일 이후", "상세표"]),
    ("기타",         []),   # 기본값
]

_SECTION_TAGS = frozenset({"SECTION-1", "SECTION-2", "SECTION-3"})

# 청크 내용 기반 동적 재분류 (모호한 레이블에만 적용)
# 섹션 제목으로는 구분이 안 되는 대형 섹션(기타사업, 기타) 내부 청크를 세분화
_CONTENT_RECLASSIFY: List[Tuple[str, List[str]]] = [
    ("리스크",    ["위험관리", "위험요인", "리스크", "파생상품", "헤지", "hedge"]),
    ("매출현황",  ["매출액", "수주", "판매실적", "매출 구성", "매출비중"]),
    ("원재료",    ["원재료", "생산설비", "CAPA", "생산능력", "가동률"]),
    ("연구개발",  ["연구개발", "R&D", "특허", "기술개발", "연구인력"]),
    ("임원현황",  ["임원", "등기이사", "사외이사", "대표이사"]),
    ("경영진단",  ["영업이익률", "매출총이익", "경영환경", "사업전략"]),
    ("사업개요",  ["사업 개요", "주요 사업", "사업 부문", "글로벌"]),
]

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _classify_section(title: str) -> str:
    """섹션 제목 텍스트에서 분류 레이블 반환."""
    for label, keywords in _SECTION_LABELS:
        for kw in keywords:
            if kw in title:
                return label
    return "기타"


def _reclassify_by_content(text: str, label: str) -> str:
    """
    모호한 섹션 레이블('기타사업', '기타')의 청크를 내용 키워드로 재분류.
    다른 레이블은 그대로 유지.
    """
    if label not in ("기타사업", "기타"):
        return label
    for new_label, keywords in _CONTENT_RECLASSIFY:
        for kw in keywords:
            if kw in text:
                return new_label
    return label


def _normalize(text: str) -> str:
    """연속 공백/탭 정규화."""
    return re.sub(r"[ \t]+", " ", text).strip()


class FinancialParser:
    """
    DART XML 공시 문서 파서.

    Usage:
        parser = FinancialParser()
        chunks = parser.process_document(
            file_path="data/reports/삼성전자/2023_사업보고서_xxx.html",
            source_metadata={
                "company":     "삼성전자",
                "stock_code":  "005930",
                "year":        2023,
                "report_type": "사업보고서",
                "rcept_no":    "20230307000542",
            },
        )
    """

    def __init__(self, chunk_size: int = 1500, chunk_overlap: int = 300):
        self.chunk_size = chunk_size
        # 문자 수준 폴백용 — 단일 P/TABLE 블록이 chunk_size 초과 시에만 사용
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            # 한국어 문장 경계 우선: \n\n(문단) → "다.\n"/"습니다.\n"(문장) → \n → 음절
            separators=["\n\n", "다.\n", "습니다.\n", "\n", ". ", " ", ""],
            length_function=len,
        )

    # ------------------------------------------------------------------
    # 내부 파싱 로직
    # ------------------------------------------------------------------

    def _format_table(self, table_elem) -> str:
        """
        TABLE 원소를 파이프 구분 행 텍스트로 변환.
          TR → "셀1 | 셀2 | 셀3"
        각 행에 계정명·헤더가 포함되어 임베딩 검색 품질을 높임.
        """
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

    def _collect_blocks(self, section_elem) -> List[Dict[str, str]]:
        """
        SECTION-N에서 구조적 블록 목록 반환.
        하위 SECTION-N은 제외 (별도 섹션으로 처리).

        Returns:
            [{"text": str, "type": "paragraph" | "table"}, ...]
        """
        blocks: List[Dict[str, str]] = []

        def process(elem):
            tag = elem.tag
            if tag in _SECTION_TAGS:
                return
            if tag == "TABLE-GROUP":
                for table in elem.findall("TABLE"):
                    t = self._format_table(table)
                    if t:
                        blocks.append({"text": t, "type": "table"})
                return
            if tag == "TABLE":
                t = self._format_table(elem)
                if t:
                    blocks.append({"text": t, "type": "table"})
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

    def _collect_text(self, section_elem) -> str:
        """parse_sections 표시용 — _collect_blocks 래핑."""
        return "\n\n".join(b["text"] for b in self._collect_blocks(section_elem))

    def _split_table_by_rows(self, table_text: str) -> List[str]:
        """
        chunk_size를 초과하는 테이블을 행 단위로 분할.
        첫 번째 행(헤더)은 각 청크에 반복 포함하여 계정명·컬럼 맥락 유지.
        """
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

    def _chunk_blocks(self, blocks: List[Dict[str, str]]) -> List[Tuple[str, bool]]:
        """
        구조 기반 2단계 청킹.

        Level 1 — 구조 경계:
          • paragraph + 소형 table(< chunk_size/2)을 chunk_size 한도까지 누적
          • 대형 table(>= chunk_size/2)은 단독 청크 (경계에서 분리)

        Level 2 — 문자 수준 폴백:
          • 누적 블록이 chunk_size 초과 → RecursiveCharacterTextSplitter
          • 대형 table이 chunk_size 초과 → 헤더 보존 행 단위 분할

        소형 table을 인접 단락과 함께 누적하여 맥락을 보존하고,
        지나치게 작은 단독 table 청크 생성을 방지.

        Returns:
            [(chunk_text, is_table), ...]
        """
        result: List[Tuple[str, bool]] = []
        pending_texts: List[str] = []
        pending_flags: List[bool] = []   # 각 블록의 is_table

        standalone_threshold = self.chunk_size // 2

        def flush_pending():
            if not pending_texts:
                return
            merged = "\n\n".join(pending_texts)
            # 누적 내용 중 테이블 비중이 절반 초과면 is_table=True
            table_chars = sum(len(t) for t, f in zip(pending_texts, pending_flags) if f)
            is_mostly_table = table_chars > len(merged) * 0.5
            if len(merged) > self.chunk_size:
                for sub in self.text_splitter.split_text(merged):
                    if sub.strip():
                        result.append((sub, is_mostly_table))
            else:
                result.append((merged, is_mostly_table))
            pending_texts.clear()
            pending_flags.clear()

        for block in blocks:
            text, btype = block["text"], block["type"]
            is_table = btype == "table"

            if is_table and len(text) >= standalone_threshold:
                # 대형 테이블: 단독 청크
                flush_pending()
                if len(text) > self.chunk_size:
                    for sub in self._split_table_by_rows(text):
                        result.append((sub, True))
                else:
                    result.append((text, True))
            else:
                # 소형 테이블 또는 단락: 누적
                projected = "\n\n".join(pending_texts + [text])
                if len(projected) > self.chunk_size and pending_texts:
                    flush_pending()
                pending_texts.append(text)
                pending_flags.append(is_table)

        flush_pending()
        return result

    def _extract_sections(self, root) -> List[Tuple[str, List[Dict[str, str]]]]:
        """
        DART XML 트리에서 (섹션 제목, 블록 리스트) 반환.

        SECTION-1/2/3 원소 각각을 독립 섹션으로 취급.
        각 섹션의 직속 TITLE ATOC='Y' 를 제목으로 사용.

        Returns:
            [(section_title, [{"text": ..., "type": ...}, ...]), ...]
        """
        sections: List[Tuple[str, List[Dict[str, str]]]] = []

        for section in root.iter():
            if section.tag not in _SECTION_TAGS:
                continue

            title_elem = next(
                (c for c in section if c.tag == "TITLE" and c.get("ATOC") == "Y"),
                None,
            )
            if title_elem is None:
                continue

            title_text = _normalize("".join(title_elem.itertext()))
            if not title_text:
                continue

            blocks = self._collect_blocks(section)
            if blocks:
                sections.append((title_text, blocks))

        return sections

    def _parse_xml(self, file_path: str):
        """lxml로 DART XML 파싱. 인코딩 오류/비표준 태그 대비 recover=True."""
        parser = etree.XMLParser(recover=True, encoding="utf-8", huge_tree=True)
        try:
            tree = etree.parse(file_path, parser)
            return tree.getroot()
        except Exception as e:
            logger.error(f"XML 파싱 실패 [{file_path}]: {e}")
            return None

    # ------------------------------------------------------------------
    # 공개 인터페이스
    # ------------------------------------------------------------------

    def parse_sections(self, file_path: str) -> List[Tuple[str, str, str]]:
        """
        DART XML 파일을 파싱하여 (섹션제목, 섹션분류, 본문텍스트) 리스트 반환.
        텍스트는 검사/표시용이며 청킹은 process_document가 담당.

        Returns:
            [(section_title, section_label, text), ...]
        """
        root = self._parse_xml(file_path)
        if root is None:
            return []

        raw = self._extract_sections(root)
        result = [
            (title, _classify_section(title), "\n\n".join(b["text"] for b in blocks))
            for title, blocks in raw
        ]
        logger.info(f"섹션 추출: {len(result)}개 [{os.path.basename(file_path)}]")
        return result

    def process_document(
        self,
        file_path: str,
        source_metadata: Dict[str, Any],
    ) -> List[DocumentChunk]:
        """
        DART XML 파일 → DocumentChunk 리스트.

        청킹 전략 (2단계):
          1. 구조 경계: P 블록 누적 / TABLE 단독 / 크기 초과 시 flush
          2. 문자 폴백: 단일 블록이 chunk_size 초과 시 RecursiveCharacterTextSplitter

        Args:
            file_path: 로컬 DART XML 파일 경로
            source_metadata: 청크 메타데이터에 추가할 필드.
                필수 권장 키: company, stock_code, year, report_type, rcept_no

        Returns:
            List[DocumentChunk] — vector_store.py의 add_documents()에 전달 가능
        """
        root = self._parse_xml(file_path)
        if root is None:
            logger.warning(f"파싱 결과 없음: {file_path}")
            return []

        raw_sections = self._extract_sections(root)
        if not raw_sections:
            logger.warning(f"섹션 없음: {file_path}")
            return []

        chunks: List[DocumentChunk] = []
        chunk_id = 0

        for section_title, blocks in raw_sections:
            section_label = _classify_section(section_title)
            chunk_pairs = self._chunk_blocks(blocks)   # [(text, is_table), ...]
            total = len(chunk_pairs)

            for sub_idx, (sub_text, is_table) in enumerate(chunk_pairs):
                refined_label = _reclassify_by_content(sub_text, section_label)
                meta: Dict[str, Any] = {
                    **source_metadata,
                    "section":          refined_label,
                    "section_title":    section_title,
                    "chunk_id":         chunk_id,
                    "sub_chunk_idx":    sub_idx,
                    "total_sub_chunks": total,
                    "is_table":         is_table,
                }
                chunks.append(DocumentChunk(content=sub_text, metadata=meta))
                chunk_id += 1

        logger.info(
            f"청킹 완료: {len(chunks)}개 청크 / {len(raw_sections)}개 섹션 "
            f"[{os.path.basename(file_path)}]"
        )
        return chunks


# --------------------------------------------------------------------------
# 스모크 테스트
# --------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO)

    reports_dir = os.path.join(_PROJECT_ROOT, "data", "reports")

    # 수집된 파일 자동 탐색
    target = None
    for root_dir, dirs, files in os.walk(reports_dir):
        for fname in files:
            if fname.endswith(".html"):
                target = os.path.join(root_dir, fname)
                break
        if target:
            break

    if not target:
        print(f"[SKIP] {reports_dir} 에 .html 파일 없음. dart_fetcher.py를 먼저 실행하세요.")
        sys.exit(0)

    print(f"\n--- FinancialParser 스모크 테스트: {os.path.basename(target)} ---\n")

    parser = FinancialParser(chunk_size=1500, chunk_overlap=200)

    # 1) 섹션 구조 출력
    sections = parser.parse_sections(target)
    print(f"총 섹션 수: {len(sections)}")
    print("\n[섹션 목록]")
    for i, (title, label, text) in enumerate(sections):
        print(f"  {i+1:>3}. [{label:>10}] {title[:55]}  ({len(text):,}자)")

    # 2) 청킹 결과
    meta = {
        "company":     "삼성전자",
        "stock_code":  "005930",
        "year":        2023,
        "report_type": "사업보고서",
        "rcept_no":    "20230307000542",
    }
    chunks = parser.process_document(target, meta)
    print(f"\n총 청크 수: {len(chunks)}")

    # 3) 섹션별 청크 분포
    from collections import Counter
    dist = Counter(c.metadata["section"] for c in chunks)
    print("\n[섹션별 청크 수]")
    for label, cnt in sorted(dist.items(), key=lambda x: -x[1]):
        print(f"  {label:>12}: {cnt}")

    # 4) 리스크 섹션 샘플
    risk_chunks = [c for c in chunks if c.metadata["section"] == "리스크"]
    if risk_chunks:
        print(f"\n[리스크 샘플 청크]")
        c = risk_chunks[0]
        print(f"  section_title: {c.metadata['section_title']}")
        print(f"  content ({len(c.content)}자): {c.content[:200]}")
