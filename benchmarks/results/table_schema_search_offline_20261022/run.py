"""One frozen table-catalog retrieval probe. Experiment artifact; no runtime edits."""
from __future__ import annotations

import gzip
import importlib.util
import json
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
PREV = OUT.parent / "table_row_search_offline_20261022"
FIXED = OUT.parent / "table_row_fixed_stats_offline_20261022"
spec = importlib.util.spec_from_file_location("offline_source_helpers", PREV / "run.py")
prior = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prior)  # socket connection and DNS are denied here
START = time.monotonic()
ARMS = ("A8", "A12", "D12", "S12")


def save(name, obj):
    path = (OUT / name).resolve()
    assert path.is_relative_to(OUT)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def heartbeat(phase, **kw):
    elapsed = time.monotonic() - START
    r = {"phase": phase, "elapsed_seconds": round(elapsed, 2), **kw}
    with (OUT / "heartbeat.jsonl").open("a", encoding="utf-8") as f:
        f.write(prior.encoded(r) + "\n")
    print(prior.encoded(r), flush=True)
    if elapsed > 1800:
        raise RuntimeError("Offline 30-minute time limit exceeded")


def protect():
    paths = prior.protect()
    extra = [*PREV.rglob("*"), *FIXED.rglob("*"),
             *(prior.BASE / "original_text").glob("*.txt"),
             OUT.parent / "full77_sol_top12_20261020/requests.json"]
    for p in extra:
        if p.is_file():
            paths[str(p.relative_to(ROOT))] = prior.sha(p)
    return {k: v for k, v in paths.items() if not (ROOT / k).is_relative_to(OUT)}


def preserve():
    before = prior.load(OUT / "before.json")
    changed = [p for p, h in before.items() if not (ROOT / p).is_file() or prior.sha(ROOT / p) != h]
    result = {"protected_files": len(before), "changed": changed, "unchanged": not changed}
    save("preservation.json", result)
    assert not changed, changed
    return result


def field_add(table, role, text, binding):
    text = prior.norm(text)
    if text:
        key = role, text
        if key not in table["_fields"]:
            table["_fields"][key] = {"role": role, "text": text, "binding": binding}


def admit_row(row, parent, obj, expected_sha):
    """Validate copied structure against its saved original value row and header axis."""
    assert parent["receipt"] == row["receipt"]
    assert prior.text_sha(parent["text"]) == row["parent_text_sha256"]
    assert row["source_document_sha256"] == expected_sha == obj["source_document_sha256"]
    assert obj["table_id"] == parent["metadata"]["table_source_id"]
    assert row["table_locator"] == obj["source_table_locator"]
    a, b = row["parent_span"]
    assert 0 <= a < b <= len(parent["text"])
    assert parent["text"][a:b] == row["raw_line"]
    parts = [prior.norm(x) for x in row["raw_line"].split("|")]
    assert prior.subsequence(row["row_headers"], parts)
    headers = obj.get("header_rows") or []
    for cell in row["cells"]:
        col = cell["column_index"]
        assert isinstance(col, int) and 0 <= col < len(parts)
        assert parts[col] == prior.norm(cell["value_text"])
        physical_headers = [prior.norm(h[col]) for h in headers if col < len(h)]
        assert all(prior.norm(h) in physical_headers for h in cell["column_headers"])


def table_sources(table_scores, tables, documents, original_scores, receipt, table_limit=12, owners_per_table=2):
    """First locate tables, then look up linked whole sources; no new model or gold."""
    ranked = sorted((i for i, t in enumerate(tables) if t["receipt"] == receipt and table_scores[i] > 0),
                    key=lambda i: (-float(table_scores[i]), tables[i]["table_key"]))
    top = ranked[:table_limit]
    groups = []
    for idx in top:
        t = tables[idx]
        owners = sorted(t["owners"], key=lambda u: (-float(original_scores[documents[u]["order"]]), documents[u]["order"]))
        groups.append((idx, owners[:owners_per_table]))
    hits, seen = [], set()
    for owner_pos in range(owners_per_table):
        for idx, owners in groups:
            if owner_pos >= len(owners) or owners[owner_pos] in seen:
                continue
            uid = owners[owner_pos]
            seen.add(uid)
            hits.append({"uid": uid, "score": float(table_scores[idx]), "table_key": tables[idx]["table_key"],
                         "table_rank": ranked.index(idx) + 1, "owner_rank": owner_pos + 1})
    return hits, [{"table_key": tables[i]["table_key"], "score": float(table_scores[i])} for i in ranked]


def interleave(original, schema, limit=24):
    """Equal alternating opportunities; dedupe advances that stream, then fallback."""
    out, seen, positions = [], set(), [0, 0]
    streams = [original, schema]
    while len(out) < limit:
        added = False
        for s, stream in enumerate(streams):
            while positions[s] < len(stream) and stream[positions[s]]["uid"] in seen:
                positions[s] += 1
            if positions[s] < len(stream) and len(out) < limit:
                h = stream[positions[s]]
                positions[s] += 1
                out.append({**h, "origin": "original" if s == 0 else "schema"})
                seen.add(h["uid"])
                added = True
        if not added:
            break
    return out


def prepare():
    assert not (OUT / "protocol.json").exists(), "Already frozen"
    old = prior.load(PREV / "protocol.json")
    fixed = prior.load(FIXED / "protocol.json")
    protocol = {
        "status": "FROZEN_BEFORE_SCHEMA_SCORING", "date": "2026-10-22",
        "origin_skill": "experiment-agent", "mode": "run", "verification_status": "UNVERIFIED",
        "classification": "experiment-only retrieval-schema diagnostic",
        "hypothesis": "A source-linked table schema can expose numeric table evidence missed by full-chunk lexical retrieval, beyond only raising the lexical candidate limit.",
        "cases": old["cases"], "source_context_fields": old["source_context_fields"],
        "arms": {
            "A8": "Original BM25<=24 + saved Dense16; equal RRF60; final8",
            "A12": "Same candidates/scores/order as A8; final12; primary baseline",
            "D12": "Original BM25<=48 + same Dense16; equal RRF60; final12; lexical-depth control",
            "S12": "Independent table-schema BM25, top12 physical tables, up to2 verified original owners each, table-first round-robin; alternate original BM25<=24 and schema source stream, dedupe to24 lexical candidates; same Dense16/RRF60/final12"
        },
        "schema": "Group the already admitted 63367 numeric rows by receipt and physical table ID. Use existing section-path components, physically witnessed short caption/local heading, row axes, column headers, and explicitly witnessed period/unit strings. Never include cell value fields, raw rows, generated summaries, aliases, inferred years, or a common keyword prefix.",
        "schema_provenance": "Recheck original document hash, table identity/locator, exact parent text/span, original cell positions and header labels. Structural binding only, not semantic correctness of inherited parser labels. Section path is copied from source-linked metadata; title/caption/period/unit must occur in original body or a source context with the same document hash.",
        "schema_statistics": "BM25Okapi defaults fitted independently on deduplicated table schemas. Original BM25 statistics/scores unchanged. Raw scores are never compared across original and schema indexes.",
        "source_lookup": "Owners limited to chunks with an admitted exact numeric row. Within a table, rank owners by unchanged original-chunk BM25 score then canonical order; at most2/table. Whole original chunks returned. Numeric-row owner dedup/exclusions inherited, not full-table completeness.",
        "scope": "Original explicit receipt, query unchanged; no year filtering or query interpretation",
        "packet": "Same original sources/context schema, final12 except A8, 65536 UTF-8 byte limit, omit oversized whole sources; no added neighbor/caption or compression",
        "targets_not_ranking_features": fixed["diagnostic_targets_not_ranking_inputs"],
        "evaluation": "All77 source-set/byte/citation-retention audit; existing12-case panel (10 answerable,26 required units,2 refusal controls) with source review; target ranks at schema/candidate/selection/packet stages. A missing known witness is not automatically a semantic miss; inspect alternatives before labeling.",
        "gate": "Baseline exact parity and all admitted-source bindings required. Investigate if S12 recovers previously missing evidence beyond A12 and D12 while preserving required evidence. Any required-source regression blocks automatic adoption. No tuning after results; new-report holdout and answer evaluation remain required regardless.",
        "limits": {"model_api_calls": 0, "cost_usd": 0, "answers": 0, "local_seconds": 1800, "new_schema_policies": 1},
        "limitations": "Development-exposed77; no new-report holdout, no Dense comparison, no independent/blinded semantic judge, not full TableRAG reproduction, no runtime adoption. S12 tests schema plus frozen routing allocation, not representation-only causality. D12 expands lexical candidates only."
    }
    save("before.json", protect())
    save("protocol.json", protocol)
    inputs = [PREV / "row_views.jsonl.gz", PREV / "run.py", FIXED / "protocol.json", prior.EVIDENCE, prior.REVIEW,
              prior.SAVED, OUT.parent / "full77_sol_top12_20261020/requests.json", OUT / "test_contract.py"]
    save("seal.json", {"protocol_sha256": prior.sha(OUT / "protocol.json"), "runner_sha256": prior.sha(Path(__file__)),
                       "inputs": {str(p.relative_to(ROOT)): prior.sha(p) for p in inputs}})
    heartbeat("prepared", cases=len(protocol["cases"]), protected_files=len(prior.load(OUT / "before.json")))


def run():
    protocol, seal = prior.load(OUT / "protocol.json"), prior.load(OUT / "seal.json")
    assert prior.sha(OUT / "protocol.json") == seal["protocol_sha256"]
    assert prior.sha(Path(__file__)) == seal["runner_sha256"]
    assert not (OUT / "results.json").exists(), "No repeated treatment runs"
    for p, h in seal["inputs"].items():
        assert prior.sha(ROOT / p) == h, p
    prep = prior.load(prior.BASE / "preparation.json")
    source_hashes = {r["metadata"]["rcept_no"]: r["sha256"] for r in prep["reports"]}
    for report in prep["reports"]:
        assert prior.sha(ROOT / report["path"]) == report["sha256"], report["path"]
    documents, objects = {}, {}
    fields = set(protocol["source_context_fields"]) | {"chunk_uid", "chunk_id", "sub_chunk_idx", "table_source_id", "table_view", "section_path", "local_heading"}
    for path in sorted(prior.EXPORT.glob("*.jsonl.gz")):
        with gzip.open(path, "rt", encoding="utf-8") as f:
            for line in f:
                item = json.loads(line)
                m, text = item["metadata"], item["text"]
                uid = m["chunk_uid"]
                assert uid not in documents and prior.text_sha(text) == item["text_sha256"]
                documents[uid] = {"uid": uid, "receipt": str(m["rcept_no"]), "text": text,
                                  "metadata": {k: v for k, v in m.items() if k in fields}}
                if m.get("table_object_json"):
                    objects[uid] = json.loads(m["table_object_json"])
        heartbeat("source_loaded", chunks=len(documents))
    ordered = sorted(documents, key=lambda u: (documents[u]["receipt"], int(documents[u]["metadata"].get("chunk_id", 0)), int(documents[u]["metadata"].get("sub_chunk_idx", 0)), u))
    assert len(ordered) == 16051
    for i, uid in enumerate(ordered):
        documents[uid]["order"] = i
    catalog, counts = {}, Counter()
    with gzip.open(PREV / "row_views.jsonl.gz", "rt", encoding="utf-8") as f:
        for line in f:
            row = json.loads(line)
            uid = row["parent_uid"]
            d, obj = documents[uid], objects[uid]
            admit_row(row, d, obj, source_hashes[row["receipt"]])
            key = row["receipt"] + "|" + obj["table_id"]
            if key not in catalog:
                catalog[key] = {"table_key": key, "table_id": obj["table_id"], "receipt": row["receipt"],
                                "table_locator": obj["source_table_locator"], "source_document_sha256": obj["source_document_sha256"],
                                "owners": set(), "rows": [], "_fields": {}}
            t = catalog[key]
            assert t["table_locator"] == obj["source_table_locator"]
            first_owner = uid not in t["owners"]
            t["owners"].add(uid)
            t["rows"].append({"physical_row_id": row["physical_row_id"], "parent_uid": uid,
                              "parent_span": row["parent_span"], "raw_line_sha256": prior.text_sha(row["raw_line"]),
                              "cell_ids": [c["cell_id"] for c in row["cells"]]})
            for axis in row["row_headers"]:
                field_add(t, "row_header", axis, {"row_id": row["row_id"], "parent_uid": uid, "span": row["parent_span"]})
            for cell in row["cells"]:
                for h in cell["column_headers"]:
                    field_add(t, "column_header", h, {"parent_uid": uid, "column_index": cell["column_index"], "source": "table_object.header_rows"})
            if first_owner:
                physical = "\n".join(x[2] for x in prior.body_lines(d["text"]))
                contexts = [c for c in obj.get("source_contexts", []) if c.get("document_sha256") == source_hashes[d["receipt"]]]
                witness = prior.norm(physical + "\n" + "\n".join(c.get("source_text", "") for c in contexts))
                for s in str(d["metadata"].get("section_path") or "").split(">"):
                    field_add(t, "section", s, {"parent_uid": uid, "source": "source-linked section_path metadata"})
                extras = [("caption", obj.get("caption")), ("heading", d["metadata"].get("local_heading")),
                          ("unit", obj.get("unit_hint"))]
                extras += [("period", p) for p in obj.get("period_labels", [])]
                extras += [("unit", p) for p in row["verified_units"]]
                for role, value in extras:
                    v = prior.norm(value)
                    if not v:
                        continue
                    if len(v) <= 512 and v in witness:
                        field_add(t, role, v, {"parent_uid": uid, "source": "exact string in original table body or document-hash-bound source_context"})
                    else:
                        counts["unwitnessed_or_oversized_" + role] += 1
            counts["verified_numeric_rows"] += 1
    assert counts["verified_numeric_rows"] == 63367
    tables = []
    for key, t in sorted(catalog.items()):
        t["owners"] = sorted(t["owners"], key=lambda u: documents[u]["order"])
        t["fields"] = list(t.pop("_fields").values())
        t["search_text"] = "\n".join(dict.fromkeys(f["text"] for f in t["fields"]))
        t["schema_sha256"] = prior.text_sha(t["search_text"])
        assert all(f["role"] in {"section", "caption", "heading", "unit", "period", "row_header", "column_header"} for f in t["fields"])
        tables.append(t)
    del objects, catalog
    with gzip.open(OUT / "table_catalog.jsonl.gz", "wt", encoding="utf-8") as f:
        for t in tables:
            f.write(prior.encoded(t) + "\n")
    save("catalog_admission.json", {"counts": dict(counts), "tables": len(tables), "original_chunks": len(documents),
                                   "owner_chunks": len({u for t in tables for u in t["owners"]}),
                                   "schema_roles": dict(Counter(f["role"] for t in tables for f in t["fields"])),
                                   "exclusions": "Inherited numeric-row admission only; headerless/axisless/nonnumeric rows and shifted column windows not added. Table existence does not imply complete source-owner coverage."})
    original = prior.BM25Okapi([prior.tokenize_ko(documents[u]["text"].strip()) for u in ordered])
    table_index = prior.BM25Okapi([prior.tokenize_ko(t["search_text"]) for t in tables])
    heartbeat("catalog_ready", tables=len(tables), rows=counts["verified_numeric_rows"])
    saved = {}
    for arm, path in (("A8", prior.SAVED), ("A12", OUT.parent / "full77_sol_top12_20261020/requests.json")):
        saved[arm] = {r["case_id"]: json.loads(r["body"]["input"][1]["content"]) for r in prior.load(path)}
    frozen = {c["id"]: prior.load(prior.BASE / "live/retrieval" / (c["id"] + ".json")) for c in protocol["cases"]}
    all_scores, max_error = {}, 0.0
    for c in protocol["cases"]:
        scores = original.get_scores(prior.tokenize_ko(c["question"]))
        all_scores[c["id"]] = scores
        hits = prior.fold_scores(scores, ordered, documents, str(c["report_scope"]["rcept_no"]))
        expected = frozen[c["id"]]["bm25"]
        assert [h["uid"] for h in hits] == [h["metadata"]["chunk_uid"] for h in expected], c["id"]
        e = max((abs(x["score"] - y["score"]) for x, y in zip(hits, expected)), default=0)
        max_error = max(max_error, e)
        assert e < 1e-8
        ranking = prior.merge(frozen[c["id"]]["dense"], hits, documents, 40)
        for arm, k in (("A8", 8), ("A12", 12)):
            p, _ = prior.packet(c, ranking[:k], documents, protocol["source_context_fields"], {h["uid"] for h in hits})
            assert p == saved[arm][c["id"]], ("packet parity", arm, c["id"])
    save("baseline_parity.json", {"cases": len(protocol["cases"]), "BM25_rank_parity": True, "BM25_max_score_error": max_error,
                                 "A8_saved_packet_exact": True, "A12_saved_packet_exact": True})
    heartbeat("baseline_parity_passed", cases=77)
    results = []
    owners_to_tables = defaultdict(list)
    for t in tables:
        for uid in t["owners"]:
            owners_to_tables[uid].append(t["table_key"])
    for n, c in enumerate(protocol["cases"], 1):
        cid, receipt = c["id"], str(c["report_scope"]["rcept_no"])
        scores = all_scores[cid]
        lexical = prior.fold_scores(scores, ordered, documents, receipt, limit=24)
        deep = prior.fold_scores(scores, ordered, documents, receipt, limit=48)
        ss = table_index.get_scores(prior.tokenize_ko(c["question"]))
        schema_sources, schema_rank = table_sources(ss, tables, documents, scores, receipt)
        mixed = interleave(lexical, schema_sources)
        dense = frozen[cid]["dense"]
        streams = {"A8": lexical, "A12": lexical, "D12": deep, "S12": mixed}
        rankings, packets = {}, {}
        for arm in ARMS:
            rankings[arm] = prior.merge(dense, streams[arm], documents, 80)
            k = 8 if arm == "A8" else 12
            p, omitted = prior.packet(c, rankings[arm][:k], documents, protocol["source_context_fields"], {h["uid"] for h in streams[arm]})
            # Answer evidence always copies original text, aside from existing strip behavior.
            assert all(d["text"] in (documents[d["chunk_id"]]["text"], documents[d["chunk_id"]]["text"].strip()) for d in p["documents"])
            packets[arm] = {"uids": [d["chunk_id"] for d in p["documents"]], "bytes": len(prior.encoded(p).encode("utf-8")), "omitted": omitted}
            save(f"packets/{cid}_{arm}.json", p)
        targets = []
        for target in protocol["targets_not_ranking_features"]:
            if target["case_id"] != cid:
                continue
            uid = target["uid"]
            physical_key = receipt + "|" + str(documents[uid]["metadata"].get("table_source_id"))
            targets.append({**target, "physical_table_key": physical_key,
                            "table_schema_rank": next((i + 1 for i, h in enumerate(schema_rank) if h["table_key"] == physical_key), None),
                            "admitted_owner": bool(owners_to_tables.get(uid)),
                            "schema_source_rank": next((i + 1 for i, h in enumerate(schema_sources) if h["uid"] == uid), None)})
        results.append({"case_id": cid, "query": c["question"], "report_scope": c["report_scope"],
                        "dense": [{"uid": h["metadata"]["chunk_uid"], "score": h["score"]} for h in dense],
                        "lexical": streams, "table_ranking": schema_rank, "schema_source_candidates": schema_sources,
                        "rrf": rankings, "packets": packets, "targets": targets})
        if n % 10 == 0 or n == 77:
            heartbeat("retrieval_progress", complete=n, total=77)
    save("results.json", results)
    preservation = preserve()
    save("execution_result.json", {"status": "COMPLETE_REVIEW_PENDING", "origin_skill": "experiment-agent", "mode": "run",
                                  "verification_status": "PARTIAL: retrieval and preservation verified; source review pending",
                                  "api_calls": 0, "model_cost_usd": 0, "answers_generated": 0, "cases": len(results),
                                  "elapsed_seconds": round(time.monotonic()-START, 2), "preservation": preservation})
    heartbeat("complete", cases=77)


if __name__ == "__main__":
    try:
        {"prepare": prepare, "run": run, "preserve": preserve}[sys.argv[1]]()
    except Exception as exc:
        save("failure.json", {"type": type(exc).__name__, "error": str(exc)})
        raise
