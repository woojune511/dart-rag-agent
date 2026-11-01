"""Frozen, offline follow-up: row views scored with original BM25 statistics.

Diagnostic artifact only. Does not initialize a provider, active store or app.
"""
from __future__ import annotations

import gzip
import importlib.util
import json
import socket
import sys
import time
from collections import Counter
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
PREV = OUT.parent / "table_row_search_offline_20261022"
spec = importlib.util.spec_from_file_location("previous_row_experiment", PREV / "run.py")
prior = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prior)  # Also disables socket connections before any work.
START = time.monotonic()


def save(name, obj):
    path = (OUT / name).resolve()
    assert path.is_relative_to(OUT)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def heartbeat(phase, **fields):
    elapsed = time.monotonic() - START
    value = {"phase": phase, "elapsed_seconds": round(elapsed, 2), **fields}
    with (OUT / "heartbeat.jsonl").open("a", encoding="utf-8") as f:
        f.write(prior.encoded(value) + "\n")
    print(prior.encoded(value), flush=True)
    if elapsed > 1800:
        raise RuntimeError("Local wall-clock limit exceeded")


def stat_values(index):
    return {"corpus_size": index.corpus_size, "avgdl": index.avgdl,
            "k1": index.k1, "b": index.b, "epsilon": index.epsilon,
            "idf": index.idf}


def stats_hash(index):
    return prior.text_sha(prior.encoded(stat_values(index)))


class FixedStatsScorer:
    """Use original corpus IDF/average length with each view's own TF/length.

    This intentionally never fits statistics to the row corpus. Terms absent
    from the original vocabulary have zero IDF, matching BM25Okapi.get_scores.
    Query repetitions and the original epsilon-adjusted IDF are retained.
    """

    def __init__(self, original, tokenized_views):
        self.idf = dict(original.idf)
        self.avgdl = original.avgdl
        self.k1 = original.k1
        self.b = original.b
        self.doc_len = np.asarray([len(v) for v in tokenized_views])
        self.doc_freqs = [Counter(v) for v in tokenized_views]

    def get_scores(self, query):
        score = np.zeros(len(self.doc_len))
        for token in query:
            q_freq = np.asarray([d.get(token, 0) for d in self.doc_freqs])
            score += (self.idf.get(token) or 0) * (
                q_freq * (self.k1 + 1)
                / (q_freq + self.k1 * (1 - self.b + self.b * self.doc_len / self.avgdl))
            )
        return score


def validate_saved_row(view, documents, source_hashes):
    parent = documents[view["parent_uid"]]
    assert parent["receipt"] == view["receipt"]
    assert view["source_document_sha256"] == source_hashes[view["receipt"]]
    assert prior.text_sha(parent["text"]) == view["parent_text_sha256"]
    assert prior.text_sha(view["search_text"]) == view["search_text_sha256"]
    a, b = view["parent_span"]
    assert 0 <= a < b <= len(parent["text"])
    assert parent["text"][a:b] == view["raw_line"]


def protected_paths():
    # Previous helper hashes tracked/untracked work, .env, active v12 files,
    # exports and frozen retrieval/evidence inputs. Add the prior result bundle.
    values = prior.protect()
    for path in [*PREV.rglob("*"), *(prior.BASE / "original_text").glob("*.txt")]:
        if path.is_file():
            values[str(path.relative_to(ROOT))] = prior.sha(path)
    return {k: v for k, v in values.items() if not (ROOT / k).is_relative_to(OUT)}


def preserve():
    before = prior.load(OUT / "before.json")
    changed = [p for p, h in before.items() if not (ROOT / p).is_file() or prior.sha(ROOT / p) != h]
    result = {"protected_files": len(before), "changed": changed, "unchanged": not changed}
    save("preservation.json", result)
    assert not changed, changed
    return result


def prepare():
    assert not (OUT / "protocol.json").exists(), "Protocol already frozen"
    original_protocol = prior.load(PREV / "protocol.json")
    targets = prior.load(PREV / "targets.json") + [
        {"case_id": "HYU_T2_010", "uid": "20240313001451:96:5", "evidence": "미국 판매 당기/전기"},
        {"case_id": "HYU_T3_072", "uid": "20240313001451:1251:9", "evidence": "타법인출자 Motional 대체 행"},
        {"case_id": "NAV_T2_006", "uid": "20240318000844:1559:7", "evidence": "커머스 매출 비교"},
        {"case_id": "KBF_T2_018", "uid": "20240326000894:1846:5", "evidence": "충당금 증가 직접 원인"},
    ]
    protocol = {
        "status": "FROZEN_BEFORE_FIXED_STATS_SCORING", "date": "2026-10-22",
        "classification": "benchmark regression diagnosis; experiment-only representation test",
        "hypothesis": "Original BM25 statistics plus source-linked row max scores retain row recoveries without changing original source scores.",
        "cases": original_protocol["cases"],
        "source_context_fields": original_protocol["source_context_fields"],
        "arms": {
            "A": "Original BM25<=24 and saved Dense16; exact reconstructed baseline",
            "B": "Historical original+row corpus with recomputed statistics; reuse saved result only",
            "C": "Original BM25<=24 candidates ranked by max(original score, highest row score), all using original corpus statistics",
        },
        "row_source": str((PREV / "row_views.jsonl.gz").relative_to(ROOT)),
        "row_count": 63367, "original_chunks": 16051,
        "row_rules": "Reuse byte-identical admitted rows and owner mapping; no new headers, captions, years, aliases, summaries or tokens",
        "scoring": "Original BM25Okapi IDF including epsilon floor, average document length, k1 and b; each view uses its own term frequency and length. Original-OOV terms score zero. Max per parent, never sum.",
        "tie_break": "Canonical original corpus order; original view wins exact score ties",
        "fixed": {"dense_candidates": 16, "lexical_candidates": 24, "rrf_constant": 60,
                  "equal_rrf": True, "final_k": 8, "packet_bytes": 65536,
                  "scope": "same explicit receipt only", "parent_return": "same whole original source and metadata schema"},
        "diagnostic_targets_not_ranking_inputs": targets,
        "review": "All77 source-set/order/citation retention, then source review of prior-PASS citation losses and pre-existing12-case evidence panel. IDs/anchors locate sources, not semantic scoring rules.",
        "decision_gate": "Verify Hyundai cost and Motional row recoveries, NAVER commerce and KB direct-cause preservation, missing asset candidate recovery, and other required-evidence regressions. If similar tradeoffs recur, reject this row-score augmentation without tuning.",
        "limits": {"model_api_calls": 0, "model_cost_usd": 0, "answers_generated": 0,
                   "local_seconds": 1800, "new_treatments": 1},
        "no_app_or_store_or_env_change": True, "no_dense_reembedding": True,
        "no_runtime_adoption": True, "no_tuning_after_results": True,
        "limitations": "Development-exposed questions; source coverage is not answer accuracy; no independent blinded review; inherited row-admission exclusions unchanged.",
    }
    save("before.json", protected_paths())
    save("protocol.json", protocol)
    paths = [PREV / n for n in ("run.py", "protocol.json", "results.json", "review.json", "row_views.jsonl.gz")]
    paths += [prior.EVIDENCE, prior.REVIEW, OUT / "test_contract.py"]
    save("seal.json", {"protocol_sha256": prior.sha(OUT / "protocol.json"),
                       "runner_sha256": prior.sha(Path(__file__)),
                       "inputs": {str(p.relative_to(ROOT)): prior.sha(p) for p in paths}})
    heartbeat("prepared", cases=len(protocol["cases"]), protected_files=len(prior.load(OUT / "before.json")))


def run():
    protocol, seal = prior.load(OUT / "protocol.json"), prior.load(OUT / "seal.json")
    assert prior.sha(OUT / "protocol.json") == seal["protocol_sha256"]
    assert prior.sha(Path(__file__)) == seal["runner_sha256"]
    assert not (OUT / "results.json").exists(), "Only one treatment run allowed"
    for p, h in seal["inputs"].items():
        assert prior.sha(ROOT / p) == h, p
    prep = prior.load(prior.BASE / "preparation.json")
    source_hashes = {r["metadata"]["rcept_no"]: r["sha256"] for r in prep["reports"]}
    documents = {}
    fields = set(protocol["source_context_fields"]) | {"chunk_uid", "chunk_id", "sub_chunk_idx"}
    for export in sorted(prior.EXPORT.glob("*.jsonl.gz")):
        with gzip.open(export, "rt", encoding="utf-8") as f:
            for line in f:
                item = json.loads(line)
                text, m = item["text"], item["metadata"]
                uid, receipt = m["chunk_uid"], str(m["rcept_no"])
                assert uid not in documents and prior.text_sha(text) == item["text_sha256"]
                documents[uid] = {"uid": uid, "receipt": receipt, "text": text,
                                  "metadata": {k: v for k, v in m.items() if k in fields}}
        heartbeat("corpus_loaded", receipt=receipt, chunks=len(documents))
    ordered = sorted(documents, key=lambda u: (documents[u]["receipt"], int(documents[u]["metadata"].get("chunk_id", 0)), int(documents[u]["metadata"].get("sub_chunk_idx", 0)), u))
    for i, uid in enumerate(ordered):
        documents[uid]["order"] = i
    assert len(ordered) == protocol["original_chunks"]
    rows, seen = [], set()
    with gzip.open(ROOT / protocol["row_source"], "rt", encoding="utf-8") as f:
        for line in f:
            row = json.loads(line)
            validate_saved_row(row, documents, source_hashes)
            assert row["physical_row_id"] not in seen
            seen.add(row["physical_row_id"])
            rows.append({k: row[k] for k in ("physical_row_id", "parent_uid", "row_label", "search_text")})
    assert len(rows) == protocol["row_count"]
    heartbeat("saved_rows_verified", rows=len(rows))
    baseline = prior.BM25Okapi([prior.tokenize_ko(documents[u]["text"].strip()) for u in ordered])
    original_hash = stats_hash(baseline)
    save("original_bm25_stats.json", stat_values(baseline))
    old = {r["case_id"]: r for r in prior.load(PREV / "results.json")}
    original_scores = {}
    max_error = 0.0
    for case in protocol["cases"]:
        cid = case["id"]
        score = baseline.get_scores(prior.tokenize_ko(case["question"]))
        original_scores[cid] = score
        score.setflags(write=False)
        got = prior.fold_scores(score, ordered, documents, str(case["report_scope"]["rcept_no"]))
        want = old[cid]["baseline_bm25"]
        assert [h["uid"] for h in got] == [h["uid"] for h in want], ("baseline ranks", cid)
        error = max((abs(a["score"] - b["score"]) for a, b in zip(got, want)), default=0)
        max_error = max(max_error, error)
        assert error < 1e-8, ("baseline scores", cid, error)
        rrf = prior.merge(old[cid]["dense"], got, documents, 40)
        assert rrf == old[cid]["A_rrf_union"], ("RRF parity", cid)
        packet, omitted = prior.packet(case, rrf[:8], documents, protocol["source_context_fields"], {h["uid"] for h in got})
        assert packet == prior.load(PREV / "packets" / f"{cid}_A.json"), ("packet parity", cid)
        assert omitted == old[cid]["packets"]["A"]["omitted"]
    save("baseline_parity.json", {"cases": 77, "bm25_ranks_equal": True, "max_score_error": max_error,
                                  "rrf_equal": True, "packets_equal": True})
    heartbeat("baseline_verified", cases=77, maximum_score_error=max_error)
    scorer = FixedStatsScorer(baseline, [prior.tokenize_ko(r["search_text"]) for r in rows])
    assert scorer.idf == baseline.idf and scorer.avgdl == baseline.avgdl
    owners = ordered + [r["parent_uid"] for r in rows]
    results, original_unchanged = [], []
    for n, case in enumerate(protocol["cases"], 1):
        cid, receipt = case["id"], str(case["report_scope"]["rcept_no"])
        query = prior.tokenize_ko(case["question"])
        row_scores = scorer.get_scores(query)
        baseline_now = baseline.get_scores(query)
        assert np.array_equal(original_scores[cid], baseline_now), ("original score changed", cid)
        original_unchanged.append({"case_id": cid, "all_original_scores_equal": True,
                                   "score_count": len(baseline_now),
                                   "scores_sha256": __import__("hashlib").sha256(baseline_now.tobytes()).hexdigest()})
        all_scores = np.concatenate([original_scores[cid], row_scores])
        full = prior.fold_scores(all_scores, owners, documents, receipt, limit=len(ordered))
        for h in full:
            i, uid = h["winning_view_index"], h["uid"]
            h["original_score"] = float(original_scores[cid][documents[uid]["order"]])
            assert h["score"] >= h["original_score"]
            h["view_type"] = "original_chunk" if i < len(ordered) else "table_row"
            if i >= len(ordered):
                row = rows[i - len(ordered)]
                h.update({"physical_row_id": row["physical_row_id"], "row_label": row["row_label"]})
        lexical = full[:24]
        ranking = prior.merge(old[cid]["dense"], lexical, documents, 40)
        packet, omitted = prior.packet(case, ranking[:8], documents, protocol["source_context_fields"], {h["uid"] for h in lexical})
        save(f"packets/{cid}_C.json", packet)
        packet_info = {"uids": [d["chunk_id"] for d in packet["documents"]],
                       "bytes": len(prior.encoded(packet).encode()), "omitted": omitted}
        diagnostics = []
        for t in protocol["diagnostic_targets_not_ranking_inputs"]:
            if t["case_id"] != cid:
                continue
            hit = next(((i + 1, h) for i, h in enumerate(full) if h["uid"] == t["uid"]), None)
            diagnostics.append({**t, "full_lexical_rank": hit[0] if hit else None,
                                "score_detail": hit[1] if hit else None})
        results.append({"case_id": cid, "query": case["question"], "report_scope": case["report_scope"],
                        "dense": old[cid]["dense"], "baseline_bm25": old[cid]["baseline_bm25"],
                        "C_bm25": lexical, "A_rrf_union": old[cid]["A_rrf_union"],
                        "B_rrf_union": old[cid]["B_rrf_union"], "C_rrf_union": ranking,
                        "packets": {**old[cid]["packets"], "C": packet_info},
                        "diagnostics": diagnostics,
                        "scoped_sources_boosted": sum(h["score"] > h["original_score"] for h in full),
                        "lost_vs_A": sorted(set(old[cid]["packets"]["A"]["uids"]) - set(packet_info["uids"])),
                        "gained_vs_A": sorted(set(packet_info["uids"]) - set(old[cid]["packets"]["A"]["uids"]))})
        if n % 10 == 0 or n == len(protocol["cases"]):
            heartbeat("retrieval_progress", completed=n, total=len(protocol["cases"]))
    assert stats_hash(baseline) == original_hash
    save("original_score_preservation.json", {"stats_unchanged": True, "statistics_sha256": original_hash,
                                             "all_1235927_scores_equal": all(r["all_original_scores_equal"] for r in original_unchanged),
                                             "score_count": len(ordered) * len(results), "cases": original_unchanged})
    save("results.json", results)
    preservation = preserve()
    save("summary.json", {"status": "RETRIEVAL_COMPLETE_REVIEW_PENDING", "cases": len(results), "row_views": len(rows),
                          "source_sets_changed_vs_A": sum(bool(r["lost_vs_A"] or r["gained_vs_A"]) for r in results),
                          "api_calls": 0, "model_cost_usd": 0, "answers_generated": 0,
                          "new_treatments": 1, "protected_files": preservation["protected_files"]})
    heartbeat("complete", cases=len(results), protected_files=preservation["protected_files"])


if __name__ == "__main__":
    try:
        {"prepare": prepare, "run": run}[sys.argv[1]]()
    except Exception as exc:
        save("failure.json", {"type": type(exc).__name__, "error": str(exc)})
        raise
