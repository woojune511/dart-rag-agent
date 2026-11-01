"""Review the completed, frozen offline comparison; never rerun retrieval."""

import gzip
import hashlib
import json
import statistics
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
OLD = ROOT / "benchmarks/results/full77_v12_final_20261018"
PANEL = ROOT / "benchmarks/results/query_decomposition_v2_20261020_132630"


def load(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def save(name, value):
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


results = {r["case_id"]: r for r in load(OUT / "results.json")}
packets = {
    (cid, arm): load(OUT / "packets" / f"{cid}_{arm}.json")
    for cid in results for arm in ("A", "B")
}


def doc(cid, arm, uid):
    return next(d for d in packets[cid, arm]["documents"] if d["chunk_id"] == uid)


def witness(cid, arm, uid, quote):
    d = doc(cid, arm, uid)
    assert quote in d["text"], (cid, arm, uid, quote)
    return {"arm": arm, "uid": uid, "quote": quote,
            "offset": d["text"].index(quote), "text_sha256": hashlib.sha256(d["text"].encode()).hexdigest()}


def ranks(cid, uid):
    r = results[cid]
    return {k: next((i + 1 for i, hit in enumerate(r[k]) if hit["uid"] == uid), None)
            for k in ("dense", "baseline_bm25", "row_bm25", "A_rrf_union", "B_rrf_union")}


def source_result(cid, uid):
    r = results[cid]
    return {"case_id": cid, "uid": uid, "ranks": ranks(cid, uid),
            "in_packet": {a: uid in r["packets"][a]["uids"] for a in ("A", "B")},
            "treatment_winner": next((h for h in r["row_bm25"] if h["uid"] == uid), None)}


seal = load(OUT / "protocol_seal.json")
assert sha(OUT / "protocol.json") == seal["protocol_sha256"]
protocol = load(OUT / "protocol.json")
assert sha(OUT / "targets.json") == protocol["target_annotations_sha256"]
assert sha(PANEL / "evidence_units.json") == protocol["evidence_annotations_sha256"]
assert sha(PANEL / "evidence_review.json") == protocol["source_review_sha256"]

targets = [{**t, **source_result(t["case_id"], t["uid"])} for t in load(OUT / "targets.json")]

# These are manual source judgments against the pre-existing evidence criteria.
# Reference IDs only locate evidence; alternatives are accepted after source review.
unit_witnesses = {
    ("MIX_T3_048", "return_policy"): ("20240312000736:590:0",),
    ("HYU_T2_010", "sales_current"): ("20240313001451:96:5",),
    ("HYU_T2_010", "sales_prior"): ("20240313001451:96:5",),
    ("HYU_T2_010", "protectionism"): ("20240313001451:1058:14",),
    ("SKH_T1_060", "borrowings"): ("20240319000684:277:148",),
    ("MIX_T1_064", "cost_of_sales"): ("20240313001451:1047:3",),
    ("MIX_T1_064", "revenue"): ("20240313001451:1047:3",),
    ("MIX_T1_064", "selling_admin"): ("20240313001451:408:266",),
    ("KBF_T2_043", "fee_current"): ("20240326000894:1846:5",),
    ("KBF_T2_043", "fee_prior"): ("20240326000894:1846:5",),
    ("KBF_T2_043", "wm_group"): ("20240326000894:1845:4",),
    ("KBF_T2_018", "provision_current"): ("20240326000894:625:2",),
    ("KBF_T2_018", "provision_prior"): ("20240326000894:625:2",),
    ("KBF_T2_018", "risk_cause"): ("20240326000894:1846:5",),
    ("SAM_T1_001", "revenue"): ("20240312000736:123:2",),
    ("SAM_T1_001", "operating_income"): ("20240312000736:123:2",),
    ("CEL_T1_013", "rd_total"): ("20240318000913:101:42",),
    ("CEL_T1_013", "rd_capitalized"): ("20240318000913:101:42",),
}
panel_notes = {
    "NAV_T3_007": "원문 연결 영업권 총액 및 영업권 열의 손상 값이 A/B 모두 없음. 반올림 손상 언급만으로 요청한 주석 전체를 충족하지 않음.",
    "MIX_T3_048": "실제 현금 배당 지급액은 A/B 모두 누락. 2024~2026 환원 정책 근거는 유지.",
    "HYU_T2_010": "B가 현대차 2023 미국 판매 87.0만 대와 2022 78.1만 대를 복구. IRA 대응 근거 유지. 승리 검색 표현은 원래 문단이므로 행 표현 자체의 단독 이득으로 해석하지 않음.",
    "SKH_T1_060": "차입금 표는 유지되나 연결 유형자산/무형자산은 두 문맥 모두 누락. 해당 자산 행 검색 표현은 생성되었지만 후보에 오르지 못함.",
    "CEL_T3_040": "평가손실, 환입, 폐기손실의 각각의 금액은 A/B 모두 누락. 순환입만으로 gross 항목을 대체하지 않음.",
    "MIX_T1_064": "B에 연결 매출액과 원가가 있는 MD&A 표가 들어옴. 판매비와관리비는 기존 주석에 유지. 단위와 연결 범위는 실제 표/문맥에 있음.",
    "KBF_T2_043": "그룹 순수수료이익 전년 비교와 그룹 WM/AUM 설명 모두 같은 근거로 유지. 수수료 원문 반올림 표시는 기존 기준에 따라 허용.",
    "KBF_T2_018": "전입액 두 연도 값은 유지. B는 보수적 적립의 언급과 일반 신용위험 측정 설명을 보유하지만, 미래경기 불확실성에 대비하여 전입액이 늘었다는 직접 연결은 사라짐. risk_cause는 부분 근거만 남아 full 아님.",
    "SAM_T1_001": "현재 연결 매출액/영업이익 표 유지.",
    "CEL_T1_013": "동일 연결 기간/천원 단위의 연구개발비 총액과 자본화 금액 유지.",
}
panel_rows = []
for c in load(PANEL / "evidence_units.json")["cases"]:
    cid = c["case_id"]
    units = []
    for u in c["units"]:
        witnesses = unit_witnesses.get((cid, u["id"]), ())
        by_arm = {}
        for a in ("A", "B"):
            kept = [v for v in witnesses if v in results[cid]["packets"][a]["uids"]]
            by_arm[a] = {"full": bool(kept), "witness_uids": kept}
        units.append({"unit_id": u["id"], "criterion": u["criterion"], "packet": by_arm})
    panel_rows.append({"case_id": cid, "role": c["role"], "units": units,
                       "full_packet_coverage": {a: all(u["packet"][a]["full"] for u in units) if units else None
                                                for a in ("A", "B")},
                       "review_note": panel_notes.get(cid, "거절 문항은 검색 목록 변화만 확인. 답변을 생성하지 않아 거절 정확도/비조작은 미평가.")})

regressions = [
    {"case_id": "NAV_T2_006", "finding": "CONFIRMED_REQUIRED_NUMERIC_EVIDENCE_LOSS",
     "note": "커머스 매출 2023/2022 및 41.4% 성장 표가 RRF 6위에서 9위로 밀림. B에는 산업 시장 규모 표와 Poshmark 개별 취득 효과가 남지만 NAVER 커머스 전체 비교값을 대체하지 못함.",
     "evidence": [witness("NAV_T2_006", "A", "20240318000844:1559:7", "커머스 | 2,546.6 | 1,801.1 | 41.4% | 26.4%")],
     "source": source_result("NAV_T2_006", "20240318000844:1559:7")},
    {"case_id": "KBF_T2_018", "finding": "CONFIRMED_DIRECT_CAUSAL_LINK_LOSS_PARTIAL_TOPIC_RETAINED",
     "note": "금액은 유지. 보수적 충당금 적립 언급은 B에도 있으나, 증가 원인을 미래경기 불확실성과 직접 연결한 문장이 빠짐. 질문 전체가 불가능하거나 금액까지 누락됐다는 뜻은 아님.",
     "evidence": [witness("KBF_T2_018", "A", "20240326000894:1846:5", "신용손실충당금전입액은 미래경기 불확실성에 대비한 보수적인 충당금적립으로"),
                  witness("KBF_T2_018", "B", "20240326000894:1842:1", "보수적인 충당금 적립에도 불구하고")],
     "source": source_result("KBF_T2_018", "20240326000894:1846:5")},
    {"case_id": "MIX_T1_046", "finding": "ESSENTIAL_VALUES_RETAINED_IN_ALTERNATIVE_SOURCE",
     "note": "인용했던 MD&A 출처는 빠졌지만 원래 함께 있었던 당기 연결 비용 표가 유지되어 종업원급여와 비용 총액을 직접 제공. 천원/당기/연결 표시 있음. 실제 답변 회귀 여부는 미평가.",
     "evidence": [witness("MIX_T1_046", "B", "20240318000844:937:813", "종업원급여(*) | 1,701,418,940"),
                  witness("MIX_T1_046", "B", "20240318000844:937:813", "합계 | 8,181,823,307")]},
    {"case_id": "KAB_T3_067", "finding": "ESSENTIAL_CATEGORIES_RETAINED_SOME_DETAIL_LOST",
     "note": "연계대출/계좌 수수료 표, 플랫폼 업무, 2023 조직 확장 및 세금신고 서비스 근거 유지. 빠진 MD&A의 광고 사업 본격화/신용대출 비교 출시를 동일 문장 그대로 재현할 근거는 약해지므로 모든 기존 답변 문장을 보존했다고는 하지 않음.",
     "evidence": [witness("KAB_T3_067", "B", "20240320001487:300:6", "당사는 2023년 플랫폼 역량 강화와 신속한 비즈니스 확장을 위한 조직 개편을 실시하였습니다."),
                  witness("KAB_T3_067", "B", "20240320001487:82:21", "2023년 1월에는 파트너사와의 제휴를 통해 개인사업자 간편 세금신고 서비스를 런칭")],
     "numeric_witness_uid": "20240320001487:173:77"},
]

motional = {**source_result("HYU_T3_072", "20240313001451:1251:9"),
    "finding": "ALTERNATIVE_INVESTMENT_TABLE_ROW_RECOVERED_NOT_FULL_CONSOLIDATED_NOTE",
    "note": "원래 분석에도 기록되어 있던 타법인출자 표의 Motional 행이 22위에서 7위로 복구. 기말 지분율 25.81%, 장부금액 1,294,367, 최근사업연도 당기순손익 -803,742가 있다. 기간/백만원·주·% 표제 청크 1243:1도 A/B에 존재한다. 연결 주석의 26%/700,691 및 영업수익·기타포괄손익 등 전체 요약 손익과는 범위가 다르므로 이를 합치거나 기존 정답 전체 복구로 판정하지 않는다.",
    "evidence": [witness("HYU_T3_072", "B", "20240313001451:1251:9", "Motional | 비상장 | 2020.03.01 | 경영참여 | 1,267,859 | 104,000,100 | 25.92 | 1,294,367 | - | - | - | 104,000,100 | 25.81 | 1,294,367 | 3,150,225 | -803,742"),
                 witness("HYU_T3_072", "B", "20240313001451:1243:1", "(기준일 : | 2023년 12월 31일 | ) | (단위 : 백만원, 주, %)")]}

historical = load(OLD / "review_final.json")["cases"]
citations = []
for c in historical:
    cid = c["case_id"]
    refs = set(c["cited_chunk_ids"])
    a = set(results[cid]["packets"]["A"]["uids"])
    b = set(results[cid]["packets"]["B"]["uids"])
    assert not refs - a, (cid, refs - a)
    citations.append({"case_id": cid, "historical_group": c["group"], "historical_outcome": c["outcome"],
                      "lost_cited_uids": sorted(refs - b), "all_cited_uids_retained": refs <= b})

examples, row_counts = [], Counter()
with gzip.open(OUT / "row_views.jsonl.gz", "rt", encoding="utf-8") as stream:
    for line in stream:
        view = json.loads(line)
        # Inspect schema without depending on row count or candidate scores.
        owner = view.get("uid", view.get("parent_uid", ""))
        row_counts[owner] += 1
        if (owner == "20240319000684:123:0" and view.get("row_label") in ("유형자산 (주12,15,33)", "무형자산 (주13,33)")) or view.get("physical_row_id") in {
            "20240313001451|IV. 이사의 경영진단 및 분석의견::table:2|9:1",
            "20240313001451|XII. 상세표 > 3. 타법인출자 현황(상세)::table:3|225:140",
        }:
            examples.append(view)

before = load(OUT / "before.json")
changed = [name for name, value in before.items() if not (ROOT / name).is_file() or sha(ROOT / name) != value]
preservation = {"protected_files": len(before), "changed": changed, "unchanged": not changed}
save("preservation.json", preservation)
assert not changed, changed

coverage = {a: {"full_cases": sum(c["full_packet_coverage"][a] is True for c in panel_rows),
                "full_units": sum(u["packet"][a]["full"] for c in panel_rows for u in c["units"])}
            for a in ("A", "B")}
packet_stats = {}
for a in ("A", "B"):
    sizes = [r["packets"][a]["bytes"] for r in results.values()]
    packet_stats[a] = {"mean_bytes": statistics.mean(sizes), "median_bytes": statistics.median(sizes),
                       "min_bytes": min(sizes), "max_bytes": max(sizes),
                       "omitted_cases": [cid for cid, r in results.items() if r["packets"][a]["omitted"]]}

review = {
    "status": "COMPLETE_NOT_ADOPTED",
    "decision": "현재 원본+행 BM25 혼합 인덱스는 채택하지 않음. 일부 행 복구 가능성은 관측했으나 후보 누락과 근거 회귀가 남았고 답변 개선은 측정하지 않음.",
    "method": "Frozen single offline comparison, no reranking/retrieval rerun during review. Source review by the same assistant, unblinded and development-exposed.",
    "comparison": {"cases": 77, "baseline_bm25_parity": load(OUT / "baseline_parity.json"),
                   "original_rrf_top8_and_saved_packet_parity": "77/77 asserted in completed runner",
                   "corpus_chunks": 16051, "row_views": 63367, "augmented_index_items": 79418,
                   "dense": "saved Dense16 unchanged", "fusion": "equal RRF60 unchanged", "final_k": 8,
                   "packet_byte_limit": 65536, "api_calls": 0, "model_cost_usd": 0, "answers_generated": 0},
    "confirmed_findings": [
        "Existing table objects can yield source-linked row search views without a new parser or model call.",
        "Motional alternative investment row and Hyundai cost table are promoted with a row view winning the parent's BM25 score.",
        "Hyundai US sales paragraph also enters final8, but its original full-chunk view wins: this gain cannot be attributed to row shortening alone.",
        "SK Hynix asset rows have views but still miss the candidate lists; good table structure is not sufficient for lexical relevance.",
        "NAVER commerce numeric evidence and KB's explicit cause-of-provision-increase sentence leave final8.",
        "Whole-table metadata is inherited by many split chunks; rows absent from the actual parent body must not be indexed as if the parent contains them.",
    ],
    "causal_limits_and_hypotheses": [
        "Adding rows changes BM25 document frequency and average length. The observed difference includes those effects; it is not an isolated wording-only effect.",
        "Many similar rows and alternative periods/scopes may compete for the same eight parent slots. This experiment does not isolate each causal contribution.",
        "Separate row search may still be useful as a candidate source, but safe fusion/coverage under the same budget remains unproven. No additional policy or tuning was attempted.",
    ],
    "row_admission": load(OUT / "row_admission.json"),
    "row_admission_note": "row_not_visible_in_parent counts repeated inherited metadata record occurrences, not unique lost rows. Projected wide-column chunks were excluded instead of guessing index remapping.",
    "target_diagnostics": targets,
    "additional_recovery": [source_result("HYU_T2_010", "20240313001451:96:5"), motional],
    "fixed_evidence_panel": {"answerable_cases": 10, "required_units": 26, "refusal_controls_not_semantically_scored": 2,
                             "counts": coverage, "rows": panel_rows,
                             "scope": "These source-coverage counts are for the pre-existing focused panel, not overall77 accuracy. One partial-cause regression and two full-coverage restorations. No answer/refusal behavior tested."},
    "historical_pass_citation_review": {"historical_pass_cases": 30, "cases_losing_a_cited_source": 4,
                                       "source_review": regressions,
                                       "limit": "Citation retention is only a proxy. Retained sources or substituted evidence do not guarantee answer accuracy, especially after order changes."},
    "all77_citation_retention": citations,
    "all77_packet_changes": {"changed_source_sets": sum(bool(r["lost"] or r["gained"]) for r in results.values()),
                             "changed_source_order_or_set": sum(r["packets"]["A"]["uids"] != r["packets"]["B"]["uids"] for r in results.values()),
                             "removed_source_slots": sum(len(r["lost"]) for r in results.values()),
                             "not_semantic_regression_count": True, "packet_stats": packet_stats},
    "treatment_bm25_winner_types": dict(Counter(h["view_type"] for r in results.values() for h in r["row_bm25"])),
    "example_source_linked_rows": examples,
    "primary_target_row_view_counts": {t["uid"]: row_counts[t["uid"]] for t in targets},
    "limitations": ["No new-report held-out evaluation", "No independent blinded reviewer", "No answer generation or accuracy/faithfulness/refusal scoring", "No Dense row embedding comparison", "Projected wide-column chunks excluded", "No proof that all table metadata/period bindings are correct", "No production code/store/env/app changes"],
    "preservation": preservation,
    "protocol_sha256": sha(OUT / "protocol.json"),
    "results_sha256": sha(OUT / "results.json"),
}
assert coverage == {"A": {"full_cases": 4, "full_units": 14}, "B": {"full_cases": 5, "full_units": 17}}
save("review.json", review)
summary = load(OUT / "summary.json")
summary.update({"status": "COMPLETE_REVIEWED_NOT_ADOPTED", "review": "review.json",
                "review_sha256": sha(OUT / "review.json"), "protected_files_unchanged": len(before),
                "answer_accuracy_measured": False, "additional_retrieval_runs": 0})
save("summary.json", summary)
print(json.dumps({"status": summary["status"], "panel": coverage, "protected_files_unchanged": len(before),
                  "examples": len(examples), "api_calls": 0}, ensure_ascii=False))
