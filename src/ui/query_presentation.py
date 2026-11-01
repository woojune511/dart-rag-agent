"""Present stored report metadata and existing query observations without inference."""

from collections import Counter


def indexed_report_catalog(metadatas):
    """Group observed metadata by receipt; a selection binds only those receipts."""
    reports, unidentified = {}, 0
    for meta in metadatas:
        receipt = meta.get("rcept_no") if isinstance(meta, dict) else None
        if not isinstance(receipt, str) or not receipt.strip():
            unidentified += 1
            continue
        receipt = receipt.strip()
        row = reports.setdefault(receipt, {"companies": set(), "years": set(), "types": set()})
        for field, target in (("company", "companies"), ("report_type", "types")):
            value = meta.get(field)
            if isinstance(value, str) and value.strip():
                row[target].add(value.strip())
        year = meta.get("year")
        if type(year) is int or (isinstance(year, str) and year.isdecimal()):
            row["years"].add(int(year))
    catalog = []
    for receipt, row in reports.items():
        companies, years, types = sorted(row["companies"]), sorted(row["years"], reverse=True), sorted(row["types"])
        label = " · ".join((
            ", ".join(companies) or "기업명 미기록",
            ", ".join(map(str, years)) or "연도 미기록",
            ", ".join(types) or "보고서 유형 미기록",
            f"접수 {receipt}",
        ))
        catalog.append({"receipt": receipt, "companies": companies, "years": years, "label": label})
    return sorted(catalog, key=lambda row: (row["companies"], [-year for year in row["years"]], row["receipt"])), unidentified


def query_status_notices(answer, review_trace, *, store_degraded=False):
    """Copy recorded state into UI messages; missing observations stay unknown."""
    trace = (review_trace or {}).get("retrieval_debug_trace") or {}
    search = trace.get("search") or {}
    status = answer.get("retrieval_status") or {}
    cached = search.get("retrieval_mode") == "cache"
    mode = status.get("retrieval_mode") or (
        search.get("cached_retrieval_mode") if cached else search.get("retrieval_mode")
    )
    degraded = bool(status.get("degraded") or mode in {"bm25_only", "bm25_fallback"})
    notices = []
    if degraded:
        reason = search.get("cached_vector_skipped_reason") if cached else search.get("vector_skipped_reason")
        explanation = {
            "force_bm25_only": "현재 설정에서 의미 검색을 사용하지 않습니다.",
            "capacity_cooldown": "의미 검색 요청 한도로 일시 대기 중입니다.",
            "embedding_capacity_error": "의미 검색 요청 한도에 도달했습니다.",
            "vector_store_read_error": "의미 검색 인덱스를 읽지 못했습니다.",
        }.get(reason, "상세 원인은 기록되지 않았습니다.")
        notices.append(("warning", f"검색 제한: 키워드 검색만 사용했습니다. {explanation}"))
    elif mode == "hybrid":
        notices.append(("info", "의미 검색과 키워드 검색을 함께 사용했습니다."))
    elif mode == "empty_scope":
        notices.append(("info", "선택한 검색 범위에 일치하는 자료가 없습니다."))
    else:
        notices.append(("info", "검색 방식 정보가 기록되지 않았습니다."))
    if store_degraded and not degraded:
        notices.append(("warning", "저장소에 검색 제한 상태가 기록되어 있습니다."))
    if cached:
        notices.append(("caption", "이전에 저장한 검색 결과를 재사용했습니다."))
    omitted = trace.get("omitted")
    if isinstance(omitted, list):
        if omitted:
            reasons = Counter(item.get("reason") for item in omitted)
            labels = {
                "context_byte_limit": "입력 용량 제한",
                "missing_source_identity_or_text": "출처 식별정보 또는 본문 누락",
            }
            details = ", ".join(f"{labels.get(reason, '기타 기록된 사유')} {count}개" for reason, count in reasons.items())
            notices.append(("warning", f"근거 {len(omitted)}개를 답변 입력에서 제외했습니다. {details}."))
        else:
            notices.append(("caption", "검색 후 답변 입력을 구성할 때 생략된 근거는 없습니다."))
    else:
        notices.append(("caption", "근거 생략 여부가 기록되지 않았습니다."))
    return notices
