import io
import os
import logging
import zipfile
import xml.etree.ElementTree as ET
from typing import Dict, List, Optional

import requests
from dotenv import load_dotenv
from pydantic import BaseModel

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DART_BASE_URL = "https://opendart.fss.or.kr/api"

# 프로젝트 루트 기준 절대 경로 (실행 위치와 무관하게 동일한 경로 사용)
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 보고서 종류 코드 (DART pblntf_detail_ty 파라미터)
REPORT_TYPE_CODE = {
    "사업보고서": "A001",
    "반기보고서": "A002",
    "분기보고서(1분기)": "A003",
    "분기보고서(3분기)": "A004",
}


class ReportMetadata(BaseModel):
    rcept_no: str           # 접수번호 (문서 고유 식별자)
    corp_name: str          # 회사명
    corp_code: str          # DART 고유번호
    stock_code: str         # 종목코드 (비상장사는 빈 문자열)
    report_nm: str          # 보고서명 (원문)
    report_type: str        # 보고서 종류 (사업보고서 등)
    rcept_dt: str           # 접수일자 (YYYYMMDD)
    year: int               # 사업연도
    file_path: Optional[str] = None  # 다운로드 후 로컬 경로


class DARTFetcher:
    """
    DART(전자공시시스템) OpenAPI를 통해 기업 공시 문서를 수집하는 클래스.

    주요 기능:
        - 기업명 → DART 고유번호(corp_code) 변환
        - 연도/보고서 종류별 공시 목록 조회
        - 공시 문서 ZIP 다운로드 및 HTML 추출
        - 복수 기업 × 복수 연도 일괄 수집
    """

    def __init__(self, download_dir: str = None):
        self.api_key = os.environ.get("DART_API_KEY")
        if not self.api_key:
            raise ValueError(
                "DART_API_KEY가 설정되지 않았습니다. "
                ".env 파일에 DART_API_KEY=your_key 를 추가해주세요. "
                "발급: https://opendart.fss.or.kr/intro/main.do"
            )
        if download_dir is None:
            download_dir = os.path.join(_PROJECT_ROOT, "data", "reports")
        self.download_dir = download_dir
        os.makedirs(self.download_dir, exist_ok=True)
        self._corp_code_cache: Optional[Dict[str, str]] = None  # 회사명 → corp_code

    # ------------------------------------------------------------------
    # 기업 코드 조회
    # ------------------------------------------------------------------

    def _load_corp_codes(self) -> Dict[str, str]:
        """DART 전체 기업 코드 목록을 다운로드하여 {회사명: corp_code} 딕셔너리로 반환."""
        if self._corp_code_cache is not None:
            return self._corp_code_cache

        logger.info("DART 기업 코드 목록 다운로드 중...")
        resp = requests.get(
            f"{DART_BASE_URL}/corpCode.xml",
            params={"crtfc_key": self.api_key},
            timeout=30,
        )
        resp.raise_for_status()

        # 응답은 CORPCODE.xml을 담은 ZIP 파일
        with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
            with zf.open("CORPCODE.xml") as f:
                tree = ET.parse(f)

        root = tree.getroot()
        corp_map: Dict[str, str] = {}
        for item in root.findall("list"):
            name = (item.findtext("corp_name") or "").strip()
            code = (item.findtext("corp_code") or "").strip()
            if name and code:
                corp_map[name] = code

        self._corp_code_cache = corp_map
        logger.info(f"기업 코드 로드 완료: {len(corp_map):,}개")
        return corp_map

    def get_corp_code(self, company_name: str) -> Optional[str]:
        """
        회사명으로 DART corp_code를 조회합니다.
        정확한 이름이 없으면 부분 일치(포함 여부)로 폴백합니다.
        """
        corp_map = self._load_corp_codes()

        if company_name in corp_map:
            return corp_map[company_name]

        # 부분 일치 폴백
        candidates = {k: v for k, v in corp_map.items() if company_name in k}
        if candidates:
            best_name, best_code = next(iter(candidates.items()))
            logger.info(f"부분 일치: '{company_name}' → '{best_name}' (corp_code: {best_code})")
            return best_code

        logger.warning(f"기업을 찾을 수 없음: '{company_name}'")
        return None

    # ------------------------------------------------------------------
    # 공시 목록 조회
    # ------------------------------------------------------------------

    def get_filing_list(
        self,
        corp_code: str,
        year: int,
        report_type: str = "사업보고서",
    ) -> List[ReportMetadata]:
        """
        특정 기업의 연도별 공시 목록을 조회합니다.

        Args:
            corp_code: DART 기업 고유번호
            year: 사업연도 (예: 2023)
            report_type: 보고서 종류 (REPORT_TYPE_CODE 키 중 하나)

        Returns:
            ReportMetadata 리스트
        """
        pblntf_detail_ty = REPORT_TYPE_CODE.get(report_type, "11011")

        params = {
            "crtfc_key": self.api_key,
            "corp_code": corp_code,
            "bgn_de": f"{year}0101",
            "end_de": f"{year}1231",
            "pblntf_detail_ty": pblntf_detail_ty,
            "page_count": 10,
        }

        resp = requests.get(f"{DART_BASE_URL}/list.json", params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()

        status = data.get("status")
        if status == "013":
            logger.info(f"조회 결과 없음: corp_code={corp_code}, year={year}, type={report_type}")
            return []
        if status != "000":
            logger.warning(f"DART API 오류 ({status}): {data.get('message')}")
            return []

        results: List[ReportMetadata] = []
        for item in data.get("list", []):
            results.append(
                ReportMetadata(
                    rcept_no=item["rcept_no"],
                    corp_name=item["corp_name"],
                    corp_code=corp_code,
                    stock_code=item.get("stock_code", ""),
                    report_nm=item["report_nm"],
                    report_type=report_type,
                    rcept_dt=item["rcept_dt"],
                    year=year,
                )
            )

        logger.info(
            f"공시 목록 조회: {results[0].corp_name if results else corp_code} "
            f"{year}년 {report_type} → {len(results)}건"
        )
        return results

    # ------------------------------------------------------------------
    # 문서 다운로드
    # ------------------------------------------------------------------

    def download_document(self, report: ReportMetadata) -> ReportMetadata:
        """
        공시 문서 ZIP을 다운로드하고, 본문 HTML을 로컬에 저장합니다.

        DART document.xml API는 문서 파일들을 ZIP으로 반환합니다.
        ZIP 내 HTML 파일 중 가장 큰 파일을 본문으로 간주합니다.
        """
        company_dir = os.path.join(self.download_dir, report.corp_name)
        os.makedirs(company_dir, exist_ok=True)

        filename = f"{report.year}_{report.report_type}_{report.rcept_no}.html"
        output_path = os.path.join(company_dir, filename)

        if os.path.exists(output_path):
            logger.info(f"이미 다운로드됨: {output_path}")
            report.file_path = output_path
            return report

        logger.info(
            f"문서 다운로드: {report.corp_name} {report.year}년 {report.report_type} "
            f"(접수번호: {report.rcept_no})"
        )

        resp = requests.get(
            f"{DART_BASE_URL}/document.xml",
            params={"crtfc_key": self.api_key, "rcept_no": report.rcept_no},
            timeout=60,
        )
        resp.raise_for_status()

        with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
            all_files = zf.namelist()
            logger.info(f"ZIP 내 파일 목록: {all_files}")

            # HTML/HTM 우선, 없으면 XML도 시도
            htm_files = [
                name for name in all_files
                if name.lower().endswith((".htm", ".html", ".xml"))
                and not name.lower().endswith("index.xml")  # 인덱스 파일 제외
            ]

            if not htm_files:
                logger.warning(f"ZIP 내 문서 파일 없음: rcept_no={report.rcept_no}, 파일={all_files}")
                return report

            # 가장 큰 파일 = 본문 (목차/커버 제외)
            main_file = max(htm_files, key=lambda f: zf.getinfo(f).file_size)
            logger.info(f"본문 파일 선택: {main_file} ({zf.getinfo(main_file).file_size:,} bytes)")

            with zf.open(main_file) as f:
                content = f.read().decode("utf-8", errors="replace")

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(content)

        report.file_path = output_path
        logger.info(f"저장 완료: {output_path}")
        return report

    # ------------------------------------------------------------------
    # 일괄 수집 (고수준 인터페이스)
    # ------------------------------------------------------------------

    def fetch_company_reports(
        self,
        company_name: str,
        years: List[int],
        report_type: str = "사업보고서",
    ) -> List[ReportMetadata]:
        """
        회사명 + 연도 리스트로 공시 문서를 일괄 수집합니다.

        Args:
            company_name: 회사명 (예: "삼성전자")
            years: 수집할 연도 리스트 (예: [2021, 2022, 2023])
            report_type: 보고서 종류 (기본값: "사업보고서")

        Returns:
            다운로드 완료된 ReportMetadata 리스트
        """
        corp_code = self.get_corp_code(company_name)
        if not corp_code:
            logger.error(f"corp_code 조회 실패: '{company_name}'")
            return []

        all_reports: List[ReportMetadata] = []
        for year in years:
            filings = self.get_filing_list(corp_code, year, report_type)
            for filing in filings:
                downloaded = self.download_document(filing)
                all_reports.append(downloaded)

        success = [r for r in all_reports if r.file_path]
        logger.info(
            f"수집 완료: {company_name} — "
            f"{len(success)}/{len(all_reports)}개 다운로드 성공"
        )
        return all_reports


if __name__ == "__main__":
    # 스모크 테스트: 삼성전자 2023년 사업보고서
    fetcher = DARTFetcher()

    reports = fetcher.fetch_company_reports(
        company_name="삼성전자",
        years=[2023],
        report_type="사업보고서",
    )

    for r in reports:
        status = "OK" if r.file_path else "FAIL"
        print(f"[{status}] {r.corp_name} {r.year}년 {r.report_type} -> {r.file_path}")
