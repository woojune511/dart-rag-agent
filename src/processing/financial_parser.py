"""
DART XML 공시 문서 파서.

DART ZIP에서 추출된 XML 파일을 파싱하여:
  - SECTION-N 태그 기준으로 섹션 분할 (<TITLE ATOC="Y"> 헤더 활용)
  - 섹션명 키워드 매핑으로 분류 레이블 부여
  - RecursiveCharacterTextSplitter로 적정 크기 청킹
  - DocumentChunk(content, metadata) 리스트 반환 (vector_store.py 호환)

DART XML 구조:
  BODY > SECTION-1 > TITLE(헤더) + [SECTION-2 > ...] + P(본문) + TABLE(표)

메타데이터 스키마:
  company, stock_code, year, report_type,
  section, section_title, chunk_id, sub_chunk_idx, total_sub_chunks
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

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _classify_section(title: str) -> str:
    """섹션 제목 텍스트에서 분류 레이블 반환."""
    for label, keywords in _SECTION_LABELS:
        for kw in keywords:
            if kw in title:
                return label
    return "기타"


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

    def __init__(self, chunk_size: int = 1500, chunk_overlap: int = 200):
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=["\n\n", "\n", ". ", " ", ""],
            length_function=len,
        )

    # ------------------------------------------------------------------
    # 내부 파싱 로직
    # ------------------------------------------------------------------

    def _collect_text(self, section_elem) -> str:
        """
        SECTION-N 원소에서 직접 속한 본문 텍스트만 수집.
        하위 SECTION-N 원소의 내용은 제외 (별도 섹션으로 처리).

        수집 대상:
          - P 원소: itertext()로 인라인 포매팅(B, I, SPAN 등)까지 포함
          - TD / TU 원소: P 자식이 없는 경우에만 (P를 포함하면 P 처리 시 중복)
        """
        texts: List[str] = []
        for child in section_elem:
            if child.tag in _SECTION_TAGS:
                continue  # 하위 섹션은 별도 항목
            for elem in child.iter():
                if elem.tag == "P":
                    text = _normalize("".join(elem.itertext()))
                    if text:
                        texts.append(text)
                elif elem.tag in ("TD", "TU"):
                    # P 자식이 있으면 P 처리 시 커버됨
                    if not any(c.tag == "P" for c in elem):
                        text = _normalize("".join(elem.itertext()))
                        if text:
                            texts.append(text)
        return "\n".join(texts)

    def _extract_sections(self, root) -> List[Tuple[str, str]]:
        """
        DART XML 트리에서 (섹션 제목, 본문 텍스트) 리스트 반환.

        SECTION-1/2/3 원소 각각을 독립 섹션으로 취급.
        각 섹션의 직속 TITLE ATOC='Y' 를 제목으로 사용.
        """
        sections: List[Tuple[str, str]] = []

        for section in root.iter():
            if section.tag not in _SECTION_TAGS:
                continue

            # 이 섹션의 직속 TITLE(ATOC='Y') 탐색
            title_elem = next(
                (c for c in section if c.tag == "TITLE" and c.get("ATOC") == "Y"),
                None,
            )
            if title_elem is None:
                continue

            title_text = _normalize("".join(title_elem.itertext()))
            if not title_text:
                continue

            body_text = self._collect_text(section)
            if body_text:
                sections.append((title_text, body_text))

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

        Args:
            file_path: 로컬 DART XML 파일 경로 (.html 확장자로 저장된 XML)

        Returns:
            [(section_title, section_label, text), ...]
        """
        root = self._parse_xml(file_path)
        if root is None:
            return []

        raw = self._extract_sections(root)
        result = [
            (title, _classify_section(title), text)
            for title, text in raw
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

        Args:
            file_path: 로컬 DART XML 파일 경로
            source_metadata: 청크 메타데이터에 추가할 필드.
                필수 권장 키: company, stock_code, year, report_type, rcept_no

        Returns:
            List[DocumentChunk] — vector_store.py의 add_documents()에 전달 가능
        """
        sections = self.parse_sections(file_path)
        if not sections:
            logger.warning(f"파싱 결과 없음: {file_path}")
            return []

        chunks: List[DocumentChunk] = []
        chunk_id = 0

        for section_title, section_label, section_text in sections:
            sub_texts = self.text_splitter.split_text(section_text)
            total = len(sub_texts)

            for sub_idx, sub_text in enumerate(sub_texts):
                meta: Dict[str, Any] = {
                    **source_metadata,
                    "section":          section_label,
                    "section_title":    section_title,
                    "chunk_id":         chunk_id,
                    "sub_chunk_idx":    sub_idx,
                    "total_sub_chunks": total,
                }
                chunks.append(DocumentChunk(content=sub_text, metadata=meta))
                chunk_id += 1

        logger.info(
            f"청킹 완료: {len(chunks)}개 청크 / {len(sections)}개 섹션 "
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
