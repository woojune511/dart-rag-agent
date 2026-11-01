"""One frozen, provider-free table-row lexical retrieval diagnostic.

This is an experiment artifact, not an application retrieval implementation.
No model/client/store is initialized. Original source packets are returned whole.
"""
from __future__ import annotations

import gzip
import hashlib
import json
import re
import socket
import subprocess
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
BASE = ROOT / "benchmarks/results/full77_v12_final_20261018"
EXPORT = ROOT / "benchmarks/results/v12_store_recovery_preparation_2026-10-17"
SAVED = ROOT / "benchmarks/results/full77_sol_top8_20261020/requests.json"
EVIDENCE = ROOT / "benchmarks/results/query_decomposition_v2_20261020_132630/evidence_units.json"
REVIEW = EVIDENCE.with_name("evidence_review.json")
ACTIVE = ROOT / "data/app_full11_2023_v12_20261017"
START = time.monotonic()


def deny_network(*args, **kwargs):
    raise RuntimeError("Offline experiment: network is disabled")


socket.create_connection = deny_network
socket.socket.connect = deny_network
socket.socket.connect_ex = deny_network
socket.getaddrinfo = deny_network

from rank_bm25 import BM25Okapi
from src.storage.bm25_index import tokenize_ko
from src.storage.search_merge import merge_rrf_results


def encoded(obj):
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def save(name, obj):
    path = OUT / name
    assert path.resolve().is_relative_to(OUT)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def text_sha(s):
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def norm(s):
    return " ".join(str(s or "").split())


def heartbeat(phase, **fields):
    elapsed = time.monotonic() - START
    row = {"phase": phase, "elapsed_seconds": round(elapsed, 2), **fields}
    with (OUT / "heartbeat.jsonl").open("a", encoding="utf-8") as f:
        f.write(encoded(row) + "\n")
    print(encoded(row), flush=True)
    if elapsed > 1800:
        raise RuntimeError("Local wall-clock budget exhausted")


def body_lines(text):
    # Canonical search prefixes are bracketed metadata lines, not table rows.
    result = []
    offset = 0
    for line in text.splitlines(keepends=True):
        clean = line.rstrip("\r\n")
        if "|" in clean and not clean.lstrip().startswith("["):
            result.append((offset, offset + len(clean), clean, [norm(x) for x in clean.split("|")]))
        offset += len(line)
    return result


def subsequence(needles, haystack):
    pos = 0
    for value in needles:
        while pos < len(haystack) and haystack[pos] != value:
            pos += 1
        if pos == len(haystack):
            return False
        pos += 1
    return True


def row_views(text, meta, obj, expected_document_sha, counters):
    if obj.get("source_document_sha256") != expected_document_sha:
        counters["table_source_hash_not_verified"] += 1
        return []
    if obj.get("table_id") != meta.get("table_source_id"):
        counters["table_identity_not_verified"] += 1
        return []
    # Projected wide columns have new positions. Do not pretend original column
    # indices apply to them; this first diagnostic only admits unshifted columns.
    if meta.get("table_view") in {"column_window", "column_row_window"}:
        counters["column_projection_excluded_chunks"] += 1
        return []
    lines = body_lines(text)
    headers = obj.get("header_rows") or []
    source_context = "\n".join(str(x.get("source_text", "")) for x in obj.get("source_contexts", []))
    physical_text = "\n".join(x[2] for x in lines) + "\n" + source_context
    output = []
    for row in obj.get("rows", []):
        counters["row_record_occurrences"] += 1
        cells = row.get("cells") or []
        axes = [norm(x) for x in row.get("row_headers", []) if norm(x)]
        if not cells or not axes or not any(re.search(r"\d", str(c.get("value_text", ""))) for c in cells):
            counters["non_numeric_or_axisless_rows"] += 1
            continue
        matching = []
        for candidate in lines:
            parts = candidate[3]
            if not subsequence(axes, parts):
                continue
            if all(isinstance(c.get("column_index"), int)
                   and 0 <= c["column_index"] < len(parts)
                   and parts[c["column_index"]] == norm(c.get("value_text")) for c in cells):
                matching.append(candidate)
        if len(matching) != 1:
            counters["row_not_unique_in_parent" if matching else "row_not_visible_in_parent"] += 1
            continue
        start, end, raw_line, parts = matching[0]
        if any(any(norm(h) not in [norm(r[c["column_index"]]) for r in headers if c["column_index"] < len(r)]
                   for h in c.get("column_headers", [])) for c in cells):
            counters["header_axis_not_verified"] += 1
            continue
        # Only copied structure/text. No semantic aliases, ontology keywords,
        # normalized numbers, generated summaries, or inferred year conversion.
        pieces = [meta.get("section_path", ""), meta.get("local_heading", "")]
        caption = str(obj.get("caption") or "")
        if caption and len(caption) <= 512 and norm(caption) in norm(physical_text):
            pieces.append(caption)
        pieces += axes
        for cell in cells:
            pieces.append(" | ".join([*cell.get("column_headers", []), cell["value_text"]]))
        units = sorted({str(c.get("unit_hint") or "") for c in cells} - {""})
        verified_units = [u for u in units if u in physical_text]
        pieces += verified_units
        search_text = "\n".join(dict.fromkeys(str(x) for x in pieces if x))
        if len(search_text.encode("utf-8")) > 8192:
            counters["oversized_view_excluded"] += 1
            continue
        assert text[start:end] == raw_line
        uid = meta["chunk_uid"]
        physical_row = "|".join((str(meta["rcept_no"]), str(obj["table_id"]), str(row["row_id"])))
        output.append({
            "physical_row_id": physical_row, "parent_uid": uid,
            "receipt": str(meta["rcept_no"]), "search_text": search_text,
            "search_text_sha256": text_sha(search_text), "parent_text_sha256": text_sha(text),
            "source_document_sha256": expected_document_sha,
            "table_locator": obj.get("source_table_locator"), "row_id": row["row_id"],
            "row_label": row["row_label"], "row_headers": axes,
            "parent_span": [start, end], "raw_line": raw_line,
            "cells": [{k: c.get(k) for k in ("cell_id", "column_index", "column_headers", "value_text")} for c in cells],
            "verified_units": verified_units,
            "column_header_source": "existing_table_object_header_rows",
        })
        counters["admitted_row_occurrences"] += 1
    return output


def fold_scores(scores, owners, documents, receipt, *, limit=24):
    # One source receives only its best view score, never a sum of row scores.
    best = {}
    for index, value in enumerate(scores):
        uid = owners[index]
        if documents[uid]["receipt"] != receipt or value <= 0:
            continue
        if uid not in best or float(value) > best[uid]["score"]:
            best[uid] = {"uid": uid, "score": float(value), "winning_view_index": index}
    return sorted(best.values(), key=lambda x: (-x["score"], documents[x["uid"]]["order"]))[:limit]


def merge(dense, lexical, docs, limit):
    def pair(row):
        uid = row.get("uid") or row["metadata"]["chunk_uid"]
        return SimpleNamespace(metadata={"chunk_uid": uid}), float(row["score"])
    return [{"uid": doc.metadata["chunk_uid"], "score": score}
            for doc, score in merge_rrf_results([pair(x) for x in dense], [pair(x) for x in lexical], k=limit, k_rrf=60)]


def packet(case, selection, documents, fields, lexical_uids):
    result = {"query": case["question"], "report_scope": case["report_scope"], "documents": []}
    omitted = []
    for hit in selection:
        d = documents[hit["uid"]]
        m = d["metadata"]
        source = {"chunk_id": hit["uid"], "document_id": d["receipt"],
                  "source_id": quote(d["receipt"], safe="") + ":" + quote(hit["uid"], safe=""),
                  "text": d["text"].strip() if hit["uid"] in lexical_uids else d["text"],
                  "context": {k: m[k] for k in fields if k in m}}
        proposed = {**result, "documents": [*result["documents"], source]}
        if len(encoded(proposed).encode("utf-8")) > 65536:
            omitted.append(hit["uid"])
        else:
            result = proposed
    return result, omitted


def protect():
    names = subprocess.check_output(["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"], cwd=ROOT).decode().split("\0")
    paths = {ROOT / n for n in names if n and (ROOT / n).is_file()}
    paths.add(ROOT / ".env")
    paths.update(p for p in ACTIVE.rglob("*") if p.is_file())
    paths.update(EXPORT.glob("*.jsonl.gz"))
    paths.update((BASE / "live/retrieval").glob("*.json"))
    paths.update([SAVED, EVIDENCE, REVIEW, BASE / "preparation.json"])
    return {str(p.relative_to(ROOT)): sha(p) for p in sorted(paths) if not p.is_relative_to(OUT)}


def prepare():
    assert not (OUT / "protocol.json").exists(), "A frozen protocol already exists"
    preparation = load(BASE / "preparation.json")
    requests = load(SAVED)
    packets = {r["case_id"]: json.loads(r["body"]["input"][1]["content"]) for r in requests}
    fields = sorted({k for p in packets.values() for d in p["documents"] for k in d["context"]})
    protocol = {
        "status": "FROZEN_BEFORE_ROW_RETRIEVAL", "date": "2026-10-22",
        "hypothesis": "Independent source-linked table rows can expose required evidence hidden in long chunks; answer gains are not tested.",
        "classification": "diagnostic-only retrieval representation experiment",
        "cases": preparation["cases"], "source_context_fields": fields,
        "baseline": "Saved Dense16 + BM25<=24, equal RRF60, final8, 65536 UTF-8 bytes",
        "treatment": "Original corpus plus independent physical table-row BM25 views; max score per parent chunk; saved Dense16 unchanged; same RRF60/final8/byte budget",
        "lexical": "Existing tokenize_ko and BM25Okapi defaults; IDF and average length recomputed on augmented corpus; no weights or query expansion",
        "row_admission": "Numeric row with ordered axes, all original column-index values uniquely present in one parent body line; header labels verified at original column positions; source/table identity verified; projected wide columns excluded",
        "view_fields": "Existing section/local heading, physically supported short caption, row axes, column headers and original cell values, physically supported unit hints. No inferred year/aliases/LLM summaries.",
        "row_dedupe": "One view per physical report/table/row; if multiple valid owner chunks, shortest whole source then UID then span. Max per parent, never sum. Original source documents remain in index.",
        "parent_return": "Original full chunk, unchanged context schema and bytes; no new caption expansion, compression or row-only answer packet",
        "tie_break": "BM25 descending, original canonical corpus order; RRF existing stable implementation",
        "primary_diagnostics": "Previously identified 8 failure cases and their frozen target source IDs; target IDs are not ranking features",
        "target_annotations_sha256": sha(OUT / "targets.json"),
        "evidence_annotations_sha256": sha(EVIDENCE),
        "source_review_sha256": sha(REVIEW),
        "regression_audit": "All77 selection/packet changes, historical cited-source retention proxy; existing source-grounded 12-case evidence panel inspected separately. UID retention is not semantic correctness.",
        "no_tuning": True, "model_api_calls": 0, "model_cost_usd": 0,
        "local_time_limit_seconds": 1800, "max_row_view_bytes": 8192,
        "no_dense_reembedding": True, "no_app_store_env_changes": True,
        "stop_rule": "Stop after this one comparison. Baseline mismatch or provenance mismatch blocks results. No answer generation or runtime adoption.",
        "limitations": "Development-exposed questions, no new-report holdout, no independent reviewer, no answer accuracy or Dense gain measurement.",
    }
    save("before.json", protect())
    save("protocol.json", protocol)
    save("protocol_seal.json", {"protocol_sha256": sha(OUT / "protocol.json"), "runner_sha256": sha(Path(__file__))})
    heartbeat("prepared", cases=len(protocol["cases"]), protected_files=len(load(OUT / "before.json")))


def run():
    protocol = load(OUT / "protocol.json")
    seal = load(OUT / "protocol_seal.json")
    assert sha(OUT / "protocol.json") == seal["protocol_sha256"]
    assert sha(Path(__file__)) == seal["runner_sha256"]
    assert not (OUT / "results.json").exists()
    prep = load(BASE / "preparation.json")
    source_hashes = {r["metadata"]["rcept_no"]: r["sha256"] for r in prep["reports"]}
    documents, views, counts = {}, {}, Counter()
    for export in sorted(EXPORT.glob("*.jsonl.gz")):
        with gzip.open(export, "rt", encoding="utf-8") as f:
            for n, line in enumerate(f, 1):
                item = json.loads(line)
                text, m = item["text"], item["metadata"]
                uid, receipt = m["chunk_uid"], str(m["rcept_no"])
                assert uid not in documents
                assert text_sha(text) == item["text_sha256"]
                fields = set(protocol["source_context_fields"]) | {"chunk_uid", "chunk_id", "sub_chunk_idx", "table_source_id", "table_view", "block_type"}
                documents[uid] = {"uid": uid, "receipt": receipt, "text": text,
                                  "metadata": {k: v for k, v in m.items() if k in fields},
                                  "export": str(export.relative_to(ROOT)), "export_line": n}
                raw_obj = m.get("table_object_json")
                if not raw_obj:
                    counts["chunks_without_table_object"] += 1
                    continue
                obj = json.loads(raw_obj)
                counts["chunks_with_table_object"] += 1
                for view in row_views(text, m, obj, source_hashes[receipt], counts):
                    key = view["physical_row_id"]
                    rank = (len(text.encode("utf-8")), uid, view["parent_span"][0])
                    if key not in views or rank < views[key][0]:
                        views[key] = (rank, view)
        heartbeat("corpus_loaded", receipt=export.stem.split('.')[0], chunks=len(documents), rows=len(views))
    ordered = sorted(documents, key=lambda u: (documents[u]["receipt"], int(documents[u]["metadata"].get("chunk_id", 0)), int(documents[u]["metadata"].get("sub_chunk_idx", 0)), u))
    for i, uid in enumerate(ordered):
        documents[uid]["order"] = i
    rows = [x[1] for _, x in sorted(views.items())]
    save("row_admission.json", {"counts": dict(counts), "unique_rows": len(rows), "parent_chunks_with_rows": len({r['parent_uid'] for r in rows}), "corpus_chunks": len(documents)})
    with gzip.open(OUT / "row_views.jsonl.gz", "wt", encoding="utf-8") as f:
        for row in rows:
            f.write(encoded(row) + "\n")
    # The baseline is reconstructed first; intervention scores are not inspected
    # until exact stored BM25 rank and score parity succeeds for all cases.
    original_tokens = [tokenize_ko(documents[u]["text"].strip()) for u in ordered]
    baseline = BM25Okapi(original_tokens)
    frozen = {c["id"]: load(BASE / "live/retrieval" / (c["id"] + ".json")) for c in protocol["cases"]}
    maximum_error = 0.0
    for case in protocol["cases"]:
        scores = baseline.get_scores(tokenize_ko(case["question"]))
        observed = fold_scores(scores, ordered, documents, str(case["report_scope"]["rcept_no"]))
        expected = frozen[case["id"]]["bm25"]
        assert [x["uid"] for x in observed] == [x["metadata"]["chunk_uid"] for x in expected], ("BM25 rank parity", case["id"])
        error = max((abs(x["score"] - y["score"]) for x, y in zip(observed, expected)), default=0)
        maximum_error = max(error, maximum_error)
        assert error < 1e-8, ("BM25 score parity", case["id"], error)
    save("baseline_parity.json", {"cases": len(protocol["cases"]), "bm25_ranks_equal": True, "max_score_error": maximum_error})
    del baseline
    heartbeat("baseline_verified", cases=len(protocol["cases"]), bm25_max_score_error=maximum_error)
    owners = ordered + [r["parent_uid"] for r in rows]
    index = BM25Okapi(original_tokens + [tokenize_ko(r["search_text"]) for r in rows])
    del original_tokens
    requests = load(SAVED)
    saved_packets = {r["case_id"]: json.loads(r["body"]["input"][1]["content"]) for r in requests}
    results = []
    for n, case in enumerate(protocol["cases"], 1):
        f = frozen[case["id"]]
        scores = index.get_scores(tokenize_ko(case["question"]))
        lexical = fold_scores(scores, owners, documents, str(case["report_scope"]["rcept_no"]))
        for h in lexical:
            i = h["winning_view_index"]
            h["view_type"] = "original_chunk" if i < len(ordered) else "table_row"
            if i >= len(ordered):
                h["physical_row_id"] = rows[i-len(ordered)]["physical_row_id"]
                h["row_label"] = rows[i-len(ordered)]["row_label"]
        before_rank = merge(f["dense"], f["bm25"], documents, 40)
        assert [x["uid"] for x in before_rank[:8]] == [x["metadata"]["chunk_uid"] for x in f["rrf"]]
        after_rank = merge(f["dense"], lexical, documents, 40)
        packets = {}
        for arm, ranking in [("A", before_rank), ("B", after_rank)]:
            lexical_ids = {x["metadata"]["chunk_uid"] for x in f["bm25"]} if arm == "A" else {x["uid"] for x in lexical}
            p, omitted = packet(case, ranking[:8], documents, protocol["source_context_fields"], lexical_ids)
            if arm == "A":
                assert p == saved_packets[case["id"]], ("packet parity", case["id"])
            packets[arm] = {"uids": [d["chunk_id"] for d in p["documents"]], "bytes": len(encoded(p).encode("utf-8")), "omitted": omitted}
            save("packets/" + case["id"] + "_" + arm + ".json", p)
        results.append({"case_id": case["id"], "query": case["question"], "report_scope": case["report_scope"],
                        "baseline_bm25": [{"uid": x["metadata"]["chunk_uid"], "score": x["score"]} for x in f["bm25"]],
                        "dense": [{"uid": x["metadata"]["chunk_uid"], "score": x["score"]} for x in f["dense"]],
                        "row_bm25": lexical, "A_rrf_union": before_rank, "B_rrf_union": after_rank, "packets": packets,
                        "lost": sorted(set(packets["A"]["uids"])-set(packets["B"]["uids"])),
                        "gained": sorted(set(packets["B"]["uids"])-set(packets["A"]["uids"]))})
        if n % 10 == 0 or n == len(protocol["cases"]):
            heartbeat("retrieval_progress", complete=n, total=len(protocol["cases"]))
    save("results.json", results)
    save("summary.json", {"status": "RETRIEVAL_COMPLETE_REVIEW_PENDING", "cases": len(results),
                          "row_views": len(rows), "changed_packets": sum(bool(r["lost"] or r["gained"]) for r in results),
                          "source_slots_lost": sum(len(r["lost"]) for r in results),
                          "api_calls": 0, "model_cost_usd": 0, "answers_generated": 0,
                          "protocol_sha256": seal["protocol_sha256"]})
    before = load(OUT / "before.json")
    changed = [p for p, h in before.items() if not (ROOT/p).is_file() or sha(ROOT/p) != h]
    save("preservation.json", {"protected_files": len(before), "changed": changed, "unchanged": not changed})
    assert not changed, changed
    heartbeat("complete", cases=len(results), protected_files=len(before))


if __name__ == "__main__":
    try:
        {"prepare": prepare, "run": run}[sys.argv[1]]()
    except Exception as exc:
        save("failure.json", {"type": type(exc).__name__, "error": str(exc)})
        raise
