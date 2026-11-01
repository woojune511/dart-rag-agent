"""Check saved artifacts only; never invoke an analyzer, index or provider."""
import ast
import gzip
import hashlib
import json
import re
import subprocess
from pathlib import Path
from urllib.parse import quote

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
ARMS = ("A12", "L12", "N12", "NL12")


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(1048576), b""):
            h.update(block)
    return h.hexdigest()


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def save(name, value):
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


protocol, seal = load(OUT / "protocol.json"), load(OUT / "seal.json")
assert sha(OUT / "protocol.json") == seal["protocol_sha256"]
for name, digest in seal["files"].items():
    assert sha(ROOT / name) == digest, name

documents = {}
for p in sorted((OUT.parent / "v12_store_recovery_preparation_2026-10-17").glob("*.jsonl.gz")):
    with gzip.open(p, "rt", encoding="utf-8") as f:
        for line in f:
            row = json.loads(line)
            uid = row["metadata"]["chunk_uid"]
            assert uid not in documents
            assert hashlib.sha256(row["text"].encode()).hexdigest() == row["text_sha256"]
            documents[uid] = row
assert len(documents) == 16051

results = load(OUT / "results.json")
cases = {c["id"]: c for c in protocol["cases"]}
saved_requests = {
    r["case_id"]: json.loads(r["body"]["input"][1]["content"])
    for r in load(OUT.parent / "full77_sol_top12_20261020/requests.json")
}
assert len(results) == len(cases) == 77
assert {r["case_id"] for r in results} == set(cases)
packets, packet_count = {}, 0
for r in results:
    cid = r["case_id"]
    case = cases[cid]
    assert r["query"] == case["question"]
    assert r["report_scope"] == case["report_scope"]
    receipt = str(case["report_scope"]["rcept_no"])
    old = load(OUT.parent / "full77_v12_final_20261018/live/retrieval" / (cid + ".json"))
    assert r["dense"] == [{"uid": x["metadata"]["chunk_uid"], "score": x["score"]} for x in old["dense"]]
    assert len(r["dense"]) == 16
    assert [x["uid"] for x in r["lexical"]["A12"]] == [x["metadata"]["chunk_uid"] for x in old["bm25"]]
    assert all(abs(x["score"] - y["score"]) < 1e-8 for x, y in zip(r["lexical"]["A12"], old["bm25"]))
    assert r["query_tokens"]["A12"] == r["query_tokens"]["L12"]
    assert r["query_tokens"]["N12"] == r["query_tokens"]["NL12"]
    for arm in ARMS:
        lexical = r["lexical"][arm]
        assert len(lexical) <= 24
        assert len({x["uid"] for x in lexical}) == len(lexical)
        assert all(documents[x["uid"]]["metadata"]["rcept_no"] == receipt for x in r["dense"] + lexical)
        # Independently check the fixed rank arithmetic and stable tie order.
        scores = {x["uid"]: 1.0 / (60 + i) for i, x in enumerate(r["dense"], 1)}
        for i, hit in enumerate(lexical, 1):
            scores[hit["uid"]] = scores.get(hit["uid"], 0.0) + 1.0 / (60 + i)
        ranking = [{"uid": u, "score": s} for u, s in sorted(scores.items(), key=lambda x: x[1], reverse=True)]
        assert ranking == r["rrf"][arm]
        packet = load(OUT / "packets" / f"{cid}_{arm}.json")
        packets[cid, arm] = packet
        expected = {"query": case["question"], "report_scope": case["report_scope"], "documents": []}
        omitted = []
        lexical_uids = {x["uid"] for x in lexical}
        for hit in ranking[:12]:
            uid = hit["uid"]
            source = documents[uid]
            doc = {
                "chunk_id": uid,
                "document_id": receipt,
                "source_id": quote(receipt, safe="") + ":" + quote(uid, safe=""),
                "text": source["text"].strip() if uid in lexical_uids else source["text"],
                "context": {k: source["metadata"][k] for k in protocol["source_context_fields"] if k in source["metadata"]},
            }
            proposed = {**expected, "documents": [*expected["documents"], doc]}
            if len(encoded(proposed).encode()) > 65536:
                omitted.append(uid)
            else:
                expected = proposed
        assert packet == expected, (cid, arm)
        assert len(packet["documents"]) <= 12
        assert r["packets"][arm] == {
            "uids": [d["chunk_id"] for d in packet["documents"]],
            "bytes": len(encoded(packet).encode()),
            "omitted": omitted,
        }
        if arm == "A12":
            assert packet == saved_requests[cid]
        packet_count += 1

quote_receipts = []
review_inputs = [("root_source_review.json", "rows"), ("nori_source_review.json", "items")]
review_pairs = set()
for filename, key in review_inputs:
    review = load(OUT / filename)
    for row in review[key]:
        review_pairs.add((row["case_id"], row["arm"]))
        for witness in row["witnesses"]:
            cid = witness.get("case_id", row["case_id"])
            arm = witness.get("packet_arm", witness.get("arm", row["arm"]))
            doc = next(d for d in packets[cid, arm]["documents"] if d["chunk_id"] == witness["uid"])
            offset = doc["text"].find(witness["quote"])
            assert offset >= 0, (filename, cid, arm, witness)
            digest = hashlib.sha256(doc["text"].encode()).hexdigest()
            if "source_text_sha256" in witness:
                assert witness["source_text_sha256"] == digest
                assert witness["offset"] == offset
            quote_receipts.append({"review": filename, "case_id": cid, "arm": arm, "uid": witness["uid"],
                                   "quote": witness["quote"], "offset": offset, "source_text_sha256": digest})
    for name, digest in review.get("verification", {}).get("input_sha256", {}).items():
        assert sha(ROOT / name) == digest, name
audit = load(OUT / "all77_source_audit.json")["cases"]
expected_review = {(r["case_id"], a) for r in audit for a in ARMS[1:]
                   if r["historical_group"] == "common_answerable" and r["arms"][a]["historical_cited_sources_lost"]}
assert expected_review <= review_pairs, expected_review - review_pairs
save("quote_verification.json", {"exact_quote_checks": len(quote_receipts), "receipts": quote_receipts,
     "all_common_answerable_citation_loss_pairs_reviewed": True, "pairs": len(expected_review)})

before = load(OUT / "before.json")
changed = [p for p, h in before.items() if not (ROOT / p).is_file() or sha(ROOT / p) != h]
assert not changed, changed
assert subprocess.check_output(["git", "status", "--porcelain=v1", "-z"], cwd=ROOT) == (OUT / "git_status_before.bin").read_bytes()
active = ROOT / "data/app_full11_2023_v12_20261017"
old_paths = {str(Path(p)) for p in before if (ROOT / p).is_relative_to(active)}
current_paths = {str(p.relative_to(ROOT)) for p in active.rglob("*") if p.is_file()}
assert old_paths == current_paths, (old_paths - current_paths, current_paths - old_paths)
for path in OUT.glob("*.py"):
    ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

report = OUT / "report.md"
links = 0
if report.exists():
    for target in re.findall(r"\]\(([^)]+)\)", report.read_text(encoding="utf-8")):
        if not target.startswith(("https://", "http://", "#")):
            # This check writes its own receipt after all assertions succeed.
            assert (OUT / target).is_file() or target == "final_validation.json", target
            links += 1
summary = {
    "status": "PASS", "verification_scope": "Saved-artifact consistency only; no new ranking, answer generation or independent reproduction",
    "sealed_files_unchanged": len(seal["files"]), "protocol_unchanged": True,
    "original_chunks": len(documents), "cases": 77, "packets_checked": packet_count,
    "saved_dense_exact": True, "baseline_bm25_and_packets_equal": True,
    "scope_rrf12_bytes_and_original_text_verified": True,
    "quotes_checked": len(quote_receipts), "common_answerable_citation_loss_pairs_reviewed": len(expected_review),
    "protected_files_unchanged": len(before), "git_status_equal": True,
    "active_store_file_inventory_unchanged": True, "active_store_files": len(current_paths),
    "local_report_links_verified": links, "external_model_calls": 0, "answers_generated": 0,
}
save("final_validation.json", summary)
print(json.dumps(summary, ensure_ascii=False))
