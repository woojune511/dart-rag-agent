"""
Generate document-grounded draft answers for question-only or partial datasets.

This script fetches DART filings as needed, parses the filing into chunks,
retrieves relevant local context with a lightweight BM25 index, and asks Gemini
to produce a draft answer/evidence bundle grounded in the filing.

The output is intended to be reviewed by a human annotator. It is not treated
as a verified golden set.
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Literal, Optional, Sequence, Tuple

from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, Field
from rank_bm25 import BM25Okapi

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from ingestion.dart_fetcher import DARTFetcher, ReportMetadata
from processing.financial_parser import FinancialParser

logger = logging.getLogger(__name__)
CORE_COMPLETENESS_FIELDS = ("answer_key", "expected_sections", "evidence")
BUSINESS_PERIOD_FROM_PATTERN = re.compile(r'AUNIT="PERIODFROM" AUNITVALUE="(\d{8})"')
BUSINESS_PERIOD_TO_PATTERN = re.compile(r'AUNIT="PERIODTO" AUNITVALUE="(\d{8})"')


def _normalise_path(path_value: str | Path) -> Path:
    path = Path(path_value)
    if not path.is_absolute():
        path = (PROJECT_ROOT / path).resolve()
    return path


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _extract_business_period(path: Path) -> Tuple[str, str] | None:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None

    from_match = BUSINESS_PERIOD_FROM_PATTERN.search(text)
    to_match = BUSINESS_PERIOD_TO_PATTERN.search(text)
    if not from_match or not to_match:
        return None
    return from_match.group(1), to_match.group(1)


def _business_year_from_period(period: Tuple[str, str] | None) -> int | None:
    if not period:
        return None
    period_from, period_to = period
    if (
        len(period_from) == 8
        and len(period_to) == 8
        and period_from.endswith("0101")
        and period_to.endswith("1231")
        and period_from[:4] == period_to[:4]
    ):
        return int(period_from[:4])
    return None


def _select_best_report(reports: Sequence[ReportMetadata], target_year: int) -> ReportMetadata:
    if not reports:
        raise ValueError(f"No candidate reports available for {target_year}")

    def selection_key(report: ReportMetadata) -> Tuple[int, int, int, str, str]:
        report_nm = str(report.report_nm or "")
        period_year = None
        if report.file_path:
            period_year = _business_year_from_period(_extract_business_period(Path(report.file_path)))
        exact_period_match = int(period_year == target_year)
        exact_report_name_match = int(f"{target_year}.12" in report_nm)
        has_local_file = int(bool(report.file_path))
        return (
            exact_period_match,
            exact_report_name_match,
            has_local_file,
            str(report.rcept_dt or ""),
            str(report.rcept_no or ""),
        )

    return max(reports, key=selection_key)


def _checkpoint_output_path(output_path: Path) -> Path:
    return output_path.with_name(f"{output_path.stem}.checkpoint{output_path.suffix}")


def _checkpoint_summary_path(output_path: Path) -> Path:
    return output_path.with_name(f"{output_path.stem}.checkpoint.summary.json")


def _summary_payload(
    *,
    dataset_path: Path,
    output_path: Path,
    row_count: int,
    completed_rows: int,
    failures: List[Dict[str, Any]],
    start_time: float,
    status: str,
    last_completed_row_id: str = "",
) -> Dict[str, Any]:
    return {
        "dataset_path": str(dataset_path),
        "output_path": str(output_path),
        "row_count": row_count,
        "completed_rows": completed_rows,
        "failure_count": len(failures),
        "elapsed_sec": round(time.time() - start_time, 2),
        "status": status,
        "last_completed_row_id": last_completed_row_id,
        "failures": failures,
    }


def _write_summary(path: Path, payload: Dict[str, Any]) -> None:
    _write_json(path, payload)


def _safe_unlink(path: Path) -> None:
    try:
        if path.exists():
            path.unlink()
    except Exception as exc:
        logger.warning("failed to remove %s: %s", path, exc)


def _field_has_value(value: Any) -> bool:
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, list):
        return len(value) > 0
    if isinstance(value, dict):
        return len(value) > 0
    if isinstance(value, bool):
        return True
    return value is not None


def _missing_core_fields(row: Dict[str, Any]) -> List[str]:
    missing: List[str] = []
    for field in CORE_COMPLETENESS_FIELDS:
        if not _field_has_value(row.get(field)):
            missing.append(field)
    return missing


def _row_id(row: Dict[str, Any], fallback_index: int = 0) -> str:
    return str(row.get("id") or row.get("query_id") or (f"row_{fallback_index:04d}" if fallback_index else "")).strip()


def _load_existing_rows(path: Path) -> List[Dict[str, Any]]:
    payload = _load_json(path)
    if not isinstance(payload, list):
        raise ValueError(f"Existing output must be a JSON list: {path}")
    return [row for row in payload if isinstance(row, dict)]


def _merge_rows(
    base_rows: Sequence[Dict[str, Any]],
    updated_rows: Sequence[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    updated_by_id = {_row_id(row, index): row for index, row in enumerate(updated_rows, start=1)}
    merged: List[Dict[str, Any]] = []
    seen: set[str] = set()

    for index, row in enumerate(base_rows, start=1):
        row_id = _row_id(row, index)
        if row_id in updated_by_id:
            merged.append(updated_by_id[row_id])
        else:
            merged.append(row)
        seen.add(row_id)

    for index, row in enumerate(updated_rows, start=1):
        row_id = _row_id(row, index)
        if row_id in seen:
            continue
        merged.append(row)

    return merged


def _as_list(value: Any) -> List[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _tokenize_ko(text: str) -> List[str]:
    tokens: List[str] = []
    for segment in re.findall(r"[가-힣]+|[a-zA-Z0-9]+", text or ""):
        if re.fullmatch(r"[가-힣]+", segment):
            if len(segment) == 1:
                tokens.append(segment)
            else:
                tokens.extend(segment[i : i + 2] for i in range(len(segment) - 1))
        else:
            tokens.append(segment.lower())
    return tokens


def _slugify(value: str) -> str:
    lowered = "".join(ch.lower() if ch.isalnum() else "-" for ch in value)
    return "-".join(part for part in lowered.split("-") if part)


def _coerce_question(item: Dict[str, Any]) -> str:
    for key in ("question", "query"):
        value = str(item.get(key) or "").strip()
        if value:
            return value
    return ""


def _coerce_required_keywords(item: Dict[str, Any]) -> List[str]:
    checkpoints = item.get("eval_checkpoints") or {}
    if not isinstance(checkpoints, dict):
        return []
    return [str(raw).strip() for raw in _as_list(checkpoints.get("required_keywords")) if str(raw).strip()]


def _coerce_required_operands(item: Dict[str, Any]) -> List[str]:
    checkpoints = item.get("eval_checkpoints") or {}
    if not isinstance(checkpoints, dict):
        return []
    return [str(raw).strip() for raw in _as_list(checkpoints.get("required_operands")) if str(raw).strip()]


def _coerce_expected_refusal_hint(item: Dict[str, Any]) -> bool:
    checkpoints = item.get("eval_checkpoints") or {}
    if not isinstance(checkpoints, dict):
        return False
    return bool(checkpoints.get("reject_expected", False))


@dataclass
class ParsedChunk:
    report_year: int
    rcept_no: str
    section_path: str
    section: str
    text: str
    chunk_id: str


class EvidenceDraft(BaseModel):
    section_path: str = Field(default="")
    quote: str = Field(default="")
    quote_type: Literal["verbatim", "paraphrase"] = Field(default="verbatim")
    why_it_supports_answer: str = Field(default="")


class OperandDraft(BaseModel):
    label: str = Field(default="")
    period: str = Field(default="")
    raw_value: str = Field(default="")
    raw_unit: str = Field(default="")


class DraftPayload(BaseModel):
    category: str = Field(default="")
    answer_key: str = Field(default="")
    expected_sections: List[str] = Field(default_factory=list)
    evidence: List[EvidenceDraft] = Field(default_factory=list)
    required_entities: List[str] = Field(default_factory=list)
    answer_type: Literal["numeric", "boolean", "span", "list", "summary", "refusal"] = Field(default="summary")
    expected_refusal: bool = Field(default=False)
    expected_operands: List[OperandDraft] = Field(default_factory=list)
    expected_operation: str = Field(default="")
    reasoning_steps: List[str] = Field(default_factory=list)
    notes: str = Field(default="")


@dataclass
class RunProgress:
    total_rows: int
    started_at: float
    completed_rows: int = 0
    failure_count: int = 0
    current_row_id: str = ""
    current_question: str = ""
    current_row_started_at: float = 0.0
    last_completed_row_id: str = ""
    last_checkpoint_rows: int = 0
    checkpoint_path: str = ""


class FilingDraftGenerator:
    def __init__(self) -> None:
        load_dotenv(PROJECT_ROOT / ".env")
        self.fetcher = DARTFetcher()
        self.parser = FinancialParser()
        self.llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0)
        self.structured_llm = self.llm.with_structured_output(DraftPayload)
        self._report_cache: Dict[Tuple[str, int], ReportMetadata] = {}
        self._chunk_cache: Dict[Tuple[str, int, str], List[ParsedChunk]] = {}
        self._bm25_cache: Dict[Tuple[str, int, str], Tuple[BM25Okapi, List[List[str]]]] = {}

    def _discover_local_reports(self, company: str, year: int, report_type: str = "사업보고서") -> List[ReportMetadata]:
        company_dir = PROJECT_ROOT / "data" / "reports" / company
        if not company_dir.exists():
            return []

        reports: List[ReportMetadata] = []
        for path in sorted(company_dir.iterdir(), reverse=True):
            if not path.is_file() or path.suffix.lower() not in {".htm", ".html"}:
                continue
            if not path.name.startswith(f"{year}_") or report_type not in path.name:
                continue

            rcept_no = path.stem.split("_")[-1]
            reports.append(
                ReportMetadata(
                    rcept_no=rcept_no,
                    corp_name=company,
                    corp_code="",
                    stock_code="",
                    report_nm=path.stem,
                    report_type=report_type,
                    rcept_dt=rcept_no[:8] if len(rcept_no) >= 8 else "",
                    year=year,
                    file_path=str(path),
                )
            )
        return reports

    def _ensure_report(self, company: str, year: int) -> ReportMetadata:
        cache_key = (company, year)
        if cache_key in self._report_cache:
            return self._report_cache[cache_key]

        reports = self._discover_local_reports(company, year, report_type="사업보고서")
        if not reports:
            reports = self.fetcher.fetch_company_reports(company, [year], report_type="사업보고서")
        if not reports:
            raise ValueError(f"Unable to fetch filing for {company} {year}")
        report = _select_best_report(reports, year)
        logger.info(
            "selected filing for %s %s -> rcept_no=%s file=%s",
            company,
            year,
            report.rcept_no,
            report.file_path or "-",
        )
        self._report_cache[cache_key] = report
        return report

    def _parse_report(self, report: ReportMetadata) -> List[ParsedChunk]:
        cache_key = (report.corp_name, report.year, report.rcept_no)
        if cache_key in self._chunk_cache:
            return self._chunk_cache[cache_key]

        if not report.file_path:
            raise ValueError(f"Report file path missing for {report.corp_name} {report.year}")

        source_metadata = {
            "company": report.corp_name,
            "stock_code": report.stock_code or "unknown",
            "year": report.year,
            "report_type": report.report_type,
            "rcept_no": report.rcept_no,
        }
        raw_chunks = self.parser.process_document(report.file_path, source_metadata)
        chunks: List[ParsedChunk] = []
        for index, chunk in enumerate(raw_chunks, start=1):
            metadata = dict(chunk.metadata or {})
            section_path = str(metadata.get("section_path") or metadata.get("section") or "").strip()
            section = str(metadata.get("section") or "").strip()
            text = str(chunk.content or "").strip()
            if not text:
                continue
            chunks.append(
                ParsedChunk(
                    report_year=report.year,
                    rcept_no=report.rcept_no,
                    section_path=section_path,
                    section=section,
                    text=text,
                    chunk_id=str(metadata.get("chunk_uid") or f"chunk_{index:04d}"),
                )
            )
        if not chunks:
            raise ValueError(f"No parsed chunks for {report.file_path}")

        self._chunk_cache[cache_key] = chunks
        return chunks

    def _build_bm25(self, report: ReportMetadata) -> Tuple[BM25Okapi, List[List[str]], List[ParsedChunk]]:
        cache_key = (report.corp_name, report.year, report.rcept_no)
        if cache_key in self._bm25_cache:
            bm25, tokenized = self._bm25_cache[cache_key]
            return bm25, tokenized, self._chunk_cache[cache_key]

        chunks = self._parse_report(report)
        tokenized = [
            _tokenize_ko(" ".join(part for part in (chunk.section_path, chunk.section, chunk.text) if part))
            for chunk in chunks
        ]
        bm25 = BM25Okapi(tokenized)
        self._bm25_cache[cache_key] = (bm25, tokenized)
        return bm25, tokenized, chunks

    def _mentioned_business_years(self, question: str, base_year: int) -> List[int]:
        years: List[int] = []
        for match in re.findall(r"20\d{2}", question or ""):
            year = int(match)
            if year != base_year and year not in years:
                years.append(year)
        if "전년" in (question or "") and (base_year - 1) not in years:
            years.append(base_year - 1)
        return [year for year in years if 2000 <= year <= 2100]

    def _collect_reports(self, item: Dict[str, Any]) -> List[ReportMetadata]:
        company = str(item.get("company") or "").strip()
        base_year = int(item.get("year") or 0)
        if not company or not base_year:
            raise ValueError("Row missing company/year")

        reports: List[ReportMetadata] = [self._ensure_report(company, base_year)]
        question = _coerce_question(item)
        for year in self._mentioned_business_years(question, base_year):
            try:
                report = self._ensure_report(company, year)
            except Exception as exc:
                logger.warning("supplemental report fetch failed for %s %s: %s", company, year, exc)
                continue
            reports.append(report)
        return reports

    def _retrieve_context(self, reports: Sequence[ReportMetadata], item: Dict[str, Any], top_k: int = 8) -> List[ParsedChunk]:
        all_chunks: List[ParsedChunk] = []
        tokenized_docs: List[List[str]] = []
        for report in reports:
            _bm25, report_tokens, report_chunks = self._build_bm25(report)
            all_chunks.extend(report_chunks)
            tokenized_docs.extend(report_tokens)

        if not all_chunks:
            return []

        bm25 = BM25Okapi(tokenized_docs)
        question = _coerce_question(item)
        operands = _coerce_required_operands(item)
        keywords = _coerce_required_keywords(item)
        query_text = " ".join([question] + operands + keywords)
        scores = bm25.get_scores(_tokenize_ko(query_text))

        ranked = sorted(range(len(all_chunks)), key=lambda idx: scores[idx], reverse=True)
        selected: List[ParsedChunk] = []
        section_counts: Dict[str, int] = {}

        for idx in ranked:
            chunk = all_chunks[idx]
            section_key = f"{chunk.report_year}:{chunk.section_path or chunk.section or '(unknown)'}"
            if section_counts.get(section_key, 0) >= 2:
                continue
            selected.append(chunk)
            section_counts[section_key] = section_counts.get(section_key, 0) + 1
            if len(selected) >= top_k:
                break

        return selected

    def _format_context(self, chunks: Sequence[ParsedChunk]) -> str:
        parts: List[str] = []
        for index, chunk in enumerate(chunks, start=1):
            parts.append(
                "\n".join(
                    [
                        f"[chunk {index}]",
                        f"report_year: {chunk.report_year}",
                        f"rcept_no: {chunk.rcept_no}",
                        f"section_path: {chunk.section_path}",
                        f"section: {chunk.section}",
                        f"text: {chunk.text}",
                    ]
                )
            )
        return "\n\n---\n\n".join(parts)

    def _prompt_payload(self, item: Dict[str, Any], report: ReportMetadata, context: str) -> str:
        question = _coerce_question(item)
        expected_agents = ", ".join(str(agent).strip() for agent in _as_list(item.get("expected_agents")) if str(agent).strip()) or "-"
        required_operands = ", ".join(_coerce_required_operands(item)) or "-"
        required_keywords = ", ".join(_coerce_required_keywords(item)) or "-"
        expected_refusal_hint = "true" if _coerce_expected_refusal_hint(item) else "false"
        theme = str(item.get("theme") or "").strip() or "-"
        difficulty = str(item.get("difficulty") or "").strip() or "-"

        return f"""당신은 DART 사업보고서를 근거로 평가용 draft answer를 만드는 annotator 입니다.

규칙:
- 오직 [문서 컨텍스트]에 있는 정보만 사용하세요.
- 문서 컨텍스트에 근거가 부족하면 expected_refusal=true 로 두고, answer_key에는 왜 답을 제한해야 하는지 한국어로 쓰세요.
- evidence.quote 는 반드시 컨텍스트에서 그대로 복사한 짧은 근거여야 합니다.
- expected_sections 는 evidence.section_path 에 대응하는 실제 섹션 경로를 넣으세요.
- 보조 연도 보고서를 사용했다면 evidence.section_path 에 연도 힌트를 포함해도 됩니다. 예: "2022 | II. 사업의 내용 > 3. 원재료 및 생산설비"
- 숫자 계산이 필요한 질문이면 answer_key 에 최종 계산 결과를 자연스러운 한국어 문장으로 쓰세요.
- expected_operands 는 실제 계산 또는 핵심 답변에 사용한 값만 넣으세요.
- required_entities 는 정답 검증에 꼭 필요한 핵심 엔티티/키워드만 2~6개 정도 넣으세요.
- answer_type 은 numeric / boolean / span / list / summary / refusal 중 하나만 고르세요.
- category 는 다음 중 하나를 우선적으로 사용하세요: numeric_fact, comparison, trend, risk_analysis, business_overview, r_and_d_investment, missing_information, qa.
- notes 에는 짧게 draft 생성시 주의점이나 한계를 적어도 됩니다.
- 출력은 구조화된 필드만 채우고, 증거가 없으면 빈 리스트를 허용합니다.

[dataset row]
id: {str(item.get("id") or "").strip()}
company: {str(item.get("company") or "").strip()}
year: {str(item.get("year") or "").strip()}
theme: {theme}
difficulty: {difficulty}
question: {question}
expected_agents: {expected_agents}
required_operands_hint: {required_operands}
required_keywords_hint: {required_keywords}
expected_refusal_hint: {expected_refusal_hint}

[report]
corp_name: {report.corp_name}
base_report_year: {report.year}
report_type: {report.report_type}
base_rcept_no: {report.rcept_no}

[문서 컨텍스트]
{context}
"""

    def generate_for_row(self, item: Dict[str, Any]) -> Dict[str, Any]:
        company = str(item.get("company") or "").strip()
        year = int(item.get("year") or 0)
        if not company or not year:
            raise ValueError("Row missing company/year")

        reports = self._collect_reports(item)
        report = reports[0]
        context_chunks = self._retrieve_context(reports, item)
        context = self._format_context(context_chunks)
        prompt = self._prompt_payload(item, report, context)
        payload: DraftPayload = self.structured_llm.invoke(prompt)

        expected_sections = [value for value in payload.expected_sections if str(value).strip()]
        if not expected_sections:
            expected_sections = []
            for evidence_row in payload.evidence:
                section_path = str(evidence_row.section_path or "").strip()
                if section_path and section_path not in expected_sections:
                    expected_sections.append(section_path)

        evidence_rows = [
            {
                "section_path": str(row.section_path or "").strip(),
                "quote": str(row.quote or "").strip(),
                "quote_type": str(row.quote_type or "verbatim"),
                "why_it_supports_answer": str(row.why_it_supports_answer or "").strip(),
            }
            for row in payload.evidence
            if str(row.quote or "").strip() or str(row.section_path or "").strip()
        ]

        required_entities = [str(value).strip() for value in payload.required_entities if str(value).strip()]
        for hint in _coerce_required_keywords(item):
            if hint not in required_entities:
                required_entities.append(hint)

        expected_operands = [
            {
                "label": str(row.label or "").strip(),
                "period": str(row.period or "").strip(),
                "raw_value": str(row.raw_value or "").strip(),
                "raw_unit": str(row.raw_unit or "").strip(),
            }
            for row in payload.expected_operands
            if str(row.label or "").strip() or str(row.raw_value or "").strip()
        ]

        notes_parts = [
            str(item.get("notes") or "").strip(),
            "draft generated from actual filing(s) " + ",".join(
                f"{extra.year}:{extra.rcept_no}" for extra in reports
            ),
            str(payload.notes or "").strip(),
        ]
        notes = " | ".join(part for part in notes_parts if part)

        answer_key = str(payload.answer_key or "").strip()
        expected_refusal = bool(payload.expected_refusal)

        record = dict(item)
        record.update(
            {
                "question": _coerce_question(item),
                "year": year,
                "category": str(payload.category or item.get("category") or "qa").strip() or "qa",
                "answer_key": answer_key,
                "ground_truth": answer_key,
                "expected_sections": expected_sections,
                "evidence": evidence_rows,
                "required_entities": required_entities,
                "answer_type": str(payload.answer_type or "summary"),
                "expected_refusal": expected_refusal,
                "reasoning_steps": [str(step).strip() for step in payload.reasoning_steps if str(step).strip()],
                "expected_operands": expected_operands,
                "expected_operation": str(payload.expected_operation or "").strip(),
                "verification_status": "draft",
                "notes": notes,
                "source_report": {
                    "corp_name": report.corp_name,
                    "year": report.year,
                    "report_type": report.report_type,
                    "rcept_no": report.rcept_no,
                    "file_path": report.file_path,
                },
                "source_reports": [
                    {
                        "corp_name": extra.corp_name,
                        "year": extra.year,
                        "report_type": extra.report_type,
                        "rcept_no": extra.rcept_no,
                        "file_path": extra.file_path,
                    }
                    for extra in reports
                ],
                "ground_truth_context_ids": [row["section_path"] for row in evidence_rows if row["section_path"]],
                "ground_truth_evidence_quotes": [row["quote"] for row in evidence_rows if row["quote"]],
                "retrieval_preview": [
                    {
                        "report_year": chunk.report_year,
                        "rcept_no": chunk.rcept_no,
                        "section_path": chunk.section_path,
                        "section": chunk.section,
                        "preview": chunk.text[:280],
                    }
                    for chunk in context_chunks
                ],
            }
        )
        return record


def _iter_rows(rows: Iterable[Dict[str, Any]], company_filters: Sequence[str]) -> Iterable[Dict[str, Any]]:
    allowed = {value.strip() for value in company_filters if value.strip()}
    for row in rows:
        if not isinstance(row, dict):
            continue
        if allowed and str(row.get("company") or "").strip() not in allowed:
            continue
        yield row


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate document-grounded draft answers for a dataset.")
    parser.add_argument("--dataset", required=True, help="Path to the source dataset JSON.")
    parser.add_argument(
        "--output",
        help="Output JSON path. Defaults to <dataset-stem>.grounded_draft.json",
    )
    parser.add_argument(
        "--existing-output",
        help="Existing grounded draft JSON to use as a merge base.",
    )
    parser.add_argument(
        "--only-missing-core",
        action="store_true",
        help="Only process rows whose existing grounded draft is missing answer_key/expected_sections/evidence.",
    )
    parser.add_argument(
        "--checkpoint-every",
        type=int,
        default=1,
        help="Write checkpoint artifacts every N completed rows. Default: 1",
    )
    parser.add_argument(
        "--heartbeat-sec",
        type=int,
        default=30,
        help="Emit a heartbeat progress log every N seconds while running. Use 0 to disable.",
    )
    parser.add_argument(
        "--company",
        action="append",
        default=[],
        help="Optional company filter. Repeat for multiple companies.",
    )
    parser.add_argument("--limit", type=int, default=0, help="Optional max row count after filtering.")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

    dataset_path = _normalise_path(args.dataset)
    rows = _load_json(dataset_path)
    if not isinstance(rows, list):
        raise ValueError(f"Dataset must be a JSON list: {dataset_path}")

    existing_output_path = _normalise_path(args.existing_output) if args.existing_output else None
    existing_rows: List[Dict[str, Any]] = []
    existing_by_id: Dict[str, Dict[str, Any]] = {}
    if existing_output_path:
        existing_rows = _load_existing_rows(existing_output_path)
        existing_by_id = {
            _row_id(row, index): row
            for index, row in enumerate(existing_rows, start=1)
            if _row_id(row, index)
        }

    filtered_rows = list(_iter_rows(rows, args.company))
    if args.only_missing_core:
        if not existing_output_path:
            raise ValueError("--only-missing-core requires --existing-output")
        incomplete_rows: List[Dict[str, Any]] = []
        for index, row in enumerate(filtered_rows, start=1):
            row_id = _row_id(row, index)
            existing_row = existing_by_id.get(row_id)
            if existing_row is None or _missing_core_fields(existing_row):
                incomplete_rows.append(row)
        filtered_rows = incomplete_rows
    if args.limit > 0:
        filtered_rows = filtered_rows[: args.limit]

    output_path = (
        _normalise_path(args.output)
        if args.output
        else existing_output_path
        or dataset_path.with_name(f"{dataset_path.stem}.grounded_draft.json")
    )
    checkpoint_path = _checkpoint_output_path(output_path)
    checkpoint_summary_path = _checkpoint_summary_path(output_path)

    generator = FilingDraftGenerator()
    output_rows: List[Dict[str, Any]] = []
    failures: List[Dict[str, Any]] = []
    start = time.time()
    checkpoint_every = max(1, int(args.checkpoint_every or 1))
    progress = RunProgress(
        total_rows=len(filtered_rows),
        started_at=start,
        checkpoint_path=str(checkpoint_path),
    )
    progress_lock = threading.Lock()
    stop_heartbeat = threading.Event()

    def current_serializable_rows() -> List[Dict[str, Any]]:
        if existing_rows:
            return _merge_rows(existing_rows, output_rows)
        return list(output_rows)

    def write_checkpoint() -> None:
        checkpoint_rows = current_serializable_rows()
        _write_json(checkpoint_path, checkpoint_rows)
        checkpoint_summary = _summary_payload(
            dataset_path=dataset_path,
            output_path=checkpoint_path,
            row_count=len(filtered_rows),
            completed_rows=len(output_rows),
            failures=failures,
            start_time=start,
            status="running",
            last_completed_row_id=progress.last_completed_row_id,
        )
        _write_summary(checkpoint_summary_path, checkpoint_summary)
        with progress_lock:
            progress.last_checkpoint_rows = len(output_rows)

    def heartbeat_worker() -> None:
        while not stop_heartbeat.wait(args.heartbeat_sec):
            with progress_lock:
                current_row_id = progress.current_row_id
                current_question = progress.current_question
                row_started_at = progress.current_row_started_at
                completed_rows = progress.completed_rows
                total_rows = progress.total_rows
                failure_count = progress.failure_count
                last_completed_row_id = progress.last_completed_row_id
                last_checkpoint_rows = progress.last_checkpoint_rows
            row_elapsed = time.time() - row_started_at if row_started_at else 0.0
            logger.info(
                "[heartbeat] completed=%s/%s failures=%s current=%s row_elapsed=%.1fs total_elapsed=%.1fs last_completed=%s checkpoint_rows=%s checkpoint=%s question=%s",
                completed_rows,
                total_rows,
                failure_count,
                current_row_id or "-",
                row_elapsed,
                time.time() - start,
                last_completed_row_id or "-",
                last_checkpoint_rows,
                checkpoint_path,
                current_question[:120] if current_question else "-",
            )

    heartbeat_thread: Optional[threading.Thread] = None
    if args.heartbeat_sec and args.heartbeat_sec > 0:
        heartbeat_thread = threading.Thread(
            target=heartbeat_worker,
            name="grounded-draft-heartbeat",
            daemon=True,
        )
        heartbeat_thread.start()

    for index, row in enumerate(filtered_rows, start=1):
        row_id = str(row.get("id") or f"row_{index:04d}")
        question = _coerce_question(row)
        row_start = time.time()
        with progress_lock:
            progress.current_row_id = row_id
            progress.current_question = question
            progress.current_row_started_at = row_start
        logger.info("[%s/%s] drafting %s | %s", index, len(filtered_rows), row_id, question)
        try:
            drafted = generator.generate_for_row(row)
        except Exception as exc:
            logger.exception("draft generation failed for %s", row_id)
            failed = dict(existing_by_id.get(row_id) or row)
            failed["question"] = question
            failed["verification_status"] = "needs_review"
            failed["generation_error"] = str(exc)
            output_rows.append(failed)
            failures.append({"id": row_id, "error": str(exc)})
        else:
            output_rows.append(drafted)
        with progress_lock:
            progress.completed_rows = len(output_rows)
            progress.failure_count = len(failures)
            progress.last_completed_row_id = row_id
            progress.current_row_id = ""
            progress.current_question = ""
            progress.current_row_started_at = 0.0
        logger.info(
            "[%s/%s] completed %s in %.1fs | refusal=%s evidence=%s operands=%s failures=%s",
            index,
            len(filtered_rows),
            row_id,
            time.time() - row_start,
            bool(output_rows[-1].get("expected_refusal", False)),
            len(output_rows[-1].get("evidence") or []),
            len(output_rows[-1].get("expected_operands") or []),
            len(failures),
        )
        if len(output_rows) % checkpoint_every == 0 or index == len(filtered_rows):
            write_checkpoint()
            logger.info(
                "[checkpoint] saved %s/%s rows to %s",
                len(output_rows),
                len(filtered_rows),
                checkpoint_path,
            )

    stop_heartbeat.set()
    if heartbeat_thread is not None:
        heartbeat_thread.join(timeout=1.0)

    final_rows = current_serializable_rows()
    _write_json(output_path, final_rows)

    summary = _summary_payload(
        dataset_path=dataset_path,
        output_path=output_path,
        row_count=len(filtered_rows),
        completed_rows=len(output_rows),
        failures=failures,
        start_time=start,
        status="completed",
        last_completed_row_id=progress.last_completed_row_id,
    )
    summary["merged_row_count"] = len(final_rows)
    summary["only_missing_core"] = bool(args.only_missing_core)
    summary["existing_output_path"] = str(existing_output_path) if existing_output_path else ""
    summary_path = output_path.with_suffix(".summary.json")
    _write_summary(summary_path, summary)
    _safe_unlink(checkpoint_path)
    _safe_unlink(checkpoint_summary_path)

    print(f"Rows processed : {len(filtered_rows)}", flush=True)
    print(f"Output         : {output_path}", flush=True)
    print(f"Summary        : {summary_path}", flush=True)
    print(f"Failures       : {len(failures)}", flush=True)


if __name__ == "__main__":
    main()
