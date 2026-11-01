"""Finalize source review of the single completed run; no retrieval rerun."""
import copy
import json
import statistics
from collections import Counter

from run import OUT, PREV, ROOT, preserve, prior, save


results = prior.load(OUT / "results.json")
by_case = {r["case_id"]: r for r in results}
protocol = prior.load(OUT / "protocol.json")
old_review = prior.load(PREV / "review.json")
historical = {r["case_id"]: r for r in prior.load(prior.BASE / "review_final.json")["cases"]}
packets = {}
for cid in by_case:
    for arm in ("A", "B", "C"):
        folder = OUT if arm == "C" else PREV
        packets[cid, arm] = prior.load(folder / "packets" / f"{cid}_{arm}.json")


def witness(cid, arm, uid, quote):
    doc = next(d for d in packets[cid, arm]["documents"] if d["chunk_id"] == uid)
    assert quote in doc["text"], (cid, arm, uid, quote)
    return {"case_id": cid, "arm": arm, "uid": uid, "quote": quote,
            "offset": doc["text"].index(quote), "text_sha256": prior.text_sha(doc["text"])}


def rank(rows, uid):
    return next((i + 1 for i, r in enumerate(rows) if r["uid"] == uid), None)


target_review = []
for t in protocol["diagnostic_targets_not_ranking_inputs"]:
    r, uid = by_case[t["case_id"]], t["uid"]
    detail = next(x for x in r["diagnostics"] if x["uid"] == uid)
    target_review.append({**t, "rrf": {a: rank(r[f"{a}_rrf_union"], uid) for a in ("A", "B", "C")},
                          "in_packet": {a: uid in r["packets"][a]["uids"] for a in ("A", "B", "C")},
                          "C_bm25_candidate_rank": rank(r["C_bm25"], uid),
                          "C_full_bm25_rank": detail["full_lexical_rank"], "C_score_detail": detail["score_detail"]})

# Frozen panel criteria remain unchanged. Witness retention locates the known
# positive source; absent witnesses were reviewed against the delivered packet.
panel = copy.deepcopy(old_review["fixed_evidence_panel"]["rows"])
for c in panel:
    cid = c["case_id"]
    present = set(by_case[cid]["packets"]["C"]["uids"])
    for u in c["units"]:
        refs = set(u["packet"]["A"]["witness_uids"] + u["packet"]["B"]["witness_uids"])
        kept = sorted(refs & present)
        u["packet"]["C"] = {"full": bool(kept), "witness_uids": kept}
    c["full_packet_coverage"]["C"] = all(u["packet"]["C"]["full"] for u in c["units"]) if c["units"] else None
    c["prior_review_note_AB"] = c.pop("review_note")
    c["C_review_note"] = "기존 positive 근거 유지 여부와 실제 문맥을 확인. 답변은 생성하지 않음."
    if cid in {"NAV_T3_007", "MIX_T3_048", "SKH_T1_060", "CEL_T3_040"}:
        c["C_review_note"] = "원래 누락된 필수 표 값의 복구 없음. 기존 남아 있던 부분 근거는 유지."
    elif cid in {"HYU_T2_010", "MIX_T1_064"}:
        c["C_review_note"] = "C 문맥은 A와 동일. 혼합 통계 B에서 관측한 필수 근거 복구는 통계 고정 시 재현되지 않음."
    elif cid == "KBF_T2_018":
        c["C_review_note"] = "금액/기간/단위와 662:19의 불확실한 금융환경 및 worse/crisis 시나리오 설명은 유지. 다만 전입액 증가를 미래경기 불확실성에 대비한 보수적 적립으로 직접 연결한 1846:5가 빠짐. risk_cause의 명시적 원인 연결 기준은 partial; 원인 관련 근거 전부 누락 또는 답변 오류로 판정하지 않음."
        risk = next(u for u in c["units"] if u["unit_id"] == "risk_cause")
        risk["packet"]["C"].update({"partial": True, "partial_witness_uids": ["20240326000894:662:19"]})

changed_notes = {
    "KBF_T2_018": {"finding": "DIRECT_CAUSAL_EVIDENCE_WEAKENED", "note": "직접 증가 원인 문장이 전기 회계기준 전환 표로 대체. 현재/전기 수치와 경기악화/위기 시나리오 설명은 유지. 답변 정확도 하락은 미측정."},
    "POS_T4_059": {"finding": "REFUSAL_NOT_EVALUATED", "note": "거절 문항의 후보/문맥 교체. 새로운 답변 또는 예상 영업이익을 만들지 않아 거절 성능 변화는 알 수 없음."},
    "MIX_T4_049": {"finding": "REFUSAL_NOT_EVALUATED", "note": "금융업 자료 사이의 교체. 파운드리 점유율 부재에 대한 새 답변 평가는 없음."},
    "NAV_T4_008": {"finding": "REFUSAL_NOT_EVALUATED", "note": "네이버 사업자료 사이의 교체. 선박 수주 잔고를 생성하거나 거절 응답을 평가하지 않음."},
    "KAK_T3_055": {"finding": "RELEVANT_SUPPORT_LOSS_IN_EXISTING_HOLD", "note": "SM 인수 영업권 및 사업결합 조정 설명이 있는 733:592가 종속기업 목록 150:9로 대체. 기존 HOLD의 의미/열 대응 문제는 해소하지 않았고 정답 회귀 집계에 넣지 않음. 관련 원문 정보가 줄었다는 관측은 남김."},
    "HYU_T3_072": {"finding": "ALTERNATIVE_MOTIONAL_ROW_RECOVERED", "note": "타법인출자 표의 Motional 기말 지분율/장부금액/당기순손익, 다중 헤더와 기간/단위 표제가 문맥에 포함. 연결 주석의 수치/전체 요약 손익과는 범위가 달라 기존 정답 전체 복구로 판정하지 않음."},
    "KBF_T4_020": {"finding": "KNOWN_REQUIRED_VALUES_RETAINED", "note": "연혁/사업종류 자료가 자금조달/운용 표로 대체. 362:285의 매출액 230,825와 매출원가 218,394 및 기간/단위 근거는 유지."},
    "MIX_T3_025": {"finding": "KNOWN_REQUIRED_EVIDENCE_RETAINED_WITH_PRIOR_PERIOD_DISTRACTOR", "note": "지배주주 이익과 비이자이익 원인에 대한 MD&A 1843:2/1846:5는 유지. 전기 회계기준 전환 표 648:5가 새로 포함되어 기간 혼동 가능성은 있으나, 실제 오독은 측정하지 않음."},
    "MIX_T4_065": {"finding": "REFUSAL_NOT_EVALUATED", "note": "영화/방송 관련 없는 사업보고서 문맥 교체. 거절 성능은 답변 미생성으로 미평가."},
    "MIX_T2_022": {"finding": "KNOWN_REQUIRED_EVIDENCE_RETAINED_WITH_MARKET_STATISTICS", "note": "1559:7의 핀테크 매출 14.2%, 결제액 21.8%와 성장 원인은 유지. 일반 핀테크 설명 대신 한국은행 산업 전체 2023 상반기 통계가 추가; 회사 실적과 구별 필요하나 실제 오독은 미평가."},
    "MIX_T3_050": {"finding": "KNOWN_REQUIRED_EVIDENCE_RETAINED_WITH_OTHER_SCOPE_TABLE", "note": "기존 별도 당기/전기 거래 근거는 유지. 값 없는 표제 대신 연결 당기 거래 표가 추가되어 연결/별도 범위를 섞을 가능성은 있으나 실제 답변 회귀는 측정하지 않음."},
}
changed_cases = []
for r in results:
    cid = r["case_id"]
    if not r["lost_vs_A"] and not r["gained_vs_A"]:
        continue
    assert cid in changed_notes
    old = historical[cid]
    changed_cases.append({"case_id": cid, "question": r["query"], **changed_notes[cid],
                          "lost_sources": r["lost_vs_A"], "gained_sources": r["gained_vs_A"],
                          "historical_group": old["group"], "historical_outcome": old["outcome"],
                          "historical_cited_sources_lost": sorted(set(old["cited_chunk_ids"]) - set(r["packets"]["C"]["uids"]))})

evidence = [
    witness("HYU_T3_072", "C", "20240313001451:1251:9", "Motional | 비상장 | 2020.03.01 | 경영참여 | 1,267,859 | 104,000,100 | 25.92 | 1,294,367 | - | - | - | 104,000,100 | 25.81 | 1,294,367 | 3,150,225 | -803,742"),
    witness("HYU_T3_072", "C", "20240313001451:1243:1", "(기준일 : | 2023년 12월 31일 | ) | (단위 : 백만원, 주, %)"),
    witness("NAV_T2_006", "C", "20240318000844:1559:7", "커머스 | 2,546.6 | 1,801.1 | 41.4% | 26.4%"),
    witness("KBF_T2_018", "A", "20240326000894:1846:5", "신용손실충당금전입액은 미래경기 불확실성에 대비한 보수적인 충당금적립으로"),
    witness("KBF_T2_018", "C", "20240326000894:662:19", "연결실체는 당기말 대내외의 불확실한 금융환경과 급격한 경기침체에 따른 잠재적인신용위험을 고려한 경기악화(worse) 시나리오와 위기상황(crisis) 시나리오 등을 반영하여 동 금융자산에 대한 기대신용손실을 측정하였습니다."),
    witness("KBF_T2_018", "C", "20240326000894:647:4", "신용손실충당금전입액 | (1,835,988) | 신용손실충당금전입액 | (1,847,775) | (11,787)"),
    witness("KBF_T4_020", "C", "20240326000894:362:285", "매출원가 | 218,394 | 217,563 | 164,948"),
    witness("KBF_T4_020", "C", "20240326000894:362:285", "매출액 | 230,825 | 233,320 | 174,819"),
    witness("MIX_T2_022", "C", "20240318000844:1559:7", "핀테크 | 1,354.8 | 1,186.6 | 14.2% | 14.0%"),
]

counts = {a: {"full_cases": sum(c["full_packet_coverage"][a] is True for c in panel),
              "full_units": sum(u["packet"][a]["full"] for c in panel for u in c["units"])} for a in ("A", "B", "C")}
assert counts["A"] == {"full_cases": 4, "full_units": 14}
assert counts["B"] == {"full_cases": 5, "full_units": 17}
assert counts["C"] == {"full_cases": 3, "full_units": 13}

all77 = []
for r in results:
    cid = r["case_id"]
    old = historical[cid]
    refs = set(old["cited_chunk_ids"])
    assert refs <= set(r["packets"]["A"]["uids"])
    all77.append({"case_id": cid, "packet_identical_to_A": packets[cid, "A"] == packets[cid, "C"],
                  "same_source_set_as_A": not r["lost_vs_A"] and not r["gained_vs_A"],
                  "historical_group": old["group"], "historical_outcome": old["outcome"],
                  "lost_cited_uids": sorted(refs - set(r["packets"]["C"]["uids"]))})
packet_stats = {}
for a in ("A", "B", "C"):
    sizes = [r["packets"][a]["bytes"] for r in results]
    packet_stats[a] = {"mean_bytes": statistics.mean(sizes), "max_bytes": max(sizes),
                       "omissions": {r["case_id"]: r["packets"][a]["omitted"] for r in results if r["packets"][a]["omitted"]}}
score_check = prior.load(OUT / "original_score_preservation.json")
preservation = preserve()
review = {
    "status": "COMPLETE_NOT_ADOPTED_STOP_THIS_VARIANT",
    "decision": "Motional 대체 행의 제한적 검색 이득은 확인. 원가/판매 복구 미재현, 주요 후보 누락 지속, 직접 원인 문장 손실로 사전 채택 조건 미충족. 이 행 최고점 보강 방식은 채택하지 않고 추가 튜닝 없이 종료.",
    "method": "One pre-frozen treatment C; A exactly reconstructed and B reused. Source review by same assistant, not blinded or independent. No answer generation.",
    "execution": {"cases": 77, "rows": 63367, "new_treatment_runs": 1, "elapsed_seconds": 76.57,
                  "api_calls": 0, "model_cost_usd": 0, "answers_generated": 0,
                  "focused_contract_tests": {"passed": 9, "failed": 0}},
    "baseline_parity": prior.load(OUT / "baseline_parity.json"),
    "statistics_and_original_score_preservation": {"statistics_unchanged": score_check["stats_unchanged"],
                                                   "original_scores_checked": score_check["score_count"],
                                                   "all_scores_equal": all(c["all_original_scores_equal"] for c in score_check["cases"]),
                                                   "statistics_sha256": score_check["statistics_sha256"]},
    "target_diagnostics": target_review,
    "all77_summary": {"packets_byte_equivalent_to_A": sum(r["packet_identical_to_A"] for r in all77),
                      "source_sets_changed": len(changed_cases),
                      "order_only_changed": [r["case_id"] for r in all77 if r["same_source_set_as_A"] and not r["packet_identical_to_A"]],
                      "removed_source_slots": sum(len(r["lost_vs_A"]) for r in results),
                      "historical_pass_cases": 30,
                      "historical_pass_cases_with_a_lost_citation": [r["case_id"] for r in all77 if r["historical_group"] == "common_answerable" and r["historical_outcome"] == "PASS" and r["lost_cited_uids"]],
                      "not_answer_accuracy_or_regression_counts": True},
    "all77_source_audit": all77,
    "changed_case_source_review": changed_cases,
    "fixed_panel": {"answerable_cases": 10, "required_units": 26, "refusal_controls_unscored": 2,
                    "counts": counts, "rows": panel,
                    "interpretation": "C loses the full direct-cause unit under the pre-existing strict criterion; worse/crisis evidence remains partial. This panel excludes Motional's separately diagnosed recovery and must not stand in for all77 answer accuracy."},
    "packet_sizes": packet_stats,
    "C_bm25_winner_types": dict(Counter(h["view_type"] for r in results for h in r["C_bm25"])),
    "source_witnesses": evidence,
    "confirmed": [
        "All original BM25 statistics and 1,235,927 original source scores are unchanged; new effects originate from fixed-stat row scoring and downstream ranking.",
        "Motional's alternative investment row enters final8 (22 -> 8), with title/date/unit source also retained.",
        "The Hyundai cost row's score increases, but it remains BM25 rank16/RRF rank10. The earlier B recovery does not survive this controlled variant.",
        "The Hyundai US-sales paragraph remains RRF11; its earlier B recovery also does not survive fixed statistics.",
        "NAVER commerce is retained at RRF6. KB's direct increase-cause source is still pushed from RRF8 to10 by competing rows despite its score being unchanged.",
        "The KB prior-period accounting-transition table is boosted from65.7473 to104.3465 and becomes BM25 rank1. Its local heading identifies the prior period; the row has not been rewritten as current data.",
        "SK Hynix asset source is lexical rank56 after augmentation and does not enter the24 candidate limit. Saved physical asset rows exist, so this is not evidence of their absence from the parsed corpus.",
    ],
    "inferences_and_limits": [
        "B versus C supports that corpus-statistics changes contributed to B's wider changes; it does not make all B gains spurious or isolate IDF and average length separately.",
        "A higher numeric-row lexical score does not ensure the question's requested causal explanation, period, or scope is represented. This is a selection limitation, not proof of a parser bug or an arithmetic bug in RRF.",
        "Other changed packets retain known required citations, but prior-period, industry-wide or other-scope tables may distract a reader. Actual interpretation errors are unmeasured.",
        "No held-out reports, independent reviewer, new embeddings, generation accuracy, faithfulness or refusal testing. No claim of overall application improvement.",
    ],
    "preservation": preservation,
    "protocol_sha256": prior.sha(OUT / "protocol.json"),
    "results_sha256": prior.sha(OUT / "results.json"),
}
save("review.json", review)
summary = prior.load(OUT / "summary.json")
summary.update({"status": review["status"], "review": "review.json", "review_sha256": prior.sha(OUT / "review.json"),
                "original_scores_unchanged": score_check["score_count"], "focused_tests_passed": 9,
                "answer_accuracy_measured": False, "runtime_adopted": False})
save("summary.json", summary)
print(prior.encoded({"status": summary["status"], "panel": counts, "protected_files": preservation["protected_files"],
                    "unchanged_packets": review["all77_summary"]["packets_byte_equivalent_to_A"]}))
