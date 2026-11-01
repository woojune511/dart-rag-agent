"""Descriptive offline analysis. Known-witness hits are not answer correctness."""
from collections import Counter, defaultdict
from statistics import mean, median
from urllib.parse import unquote

from run import ARMS, OUT, ROOT, prior, save

results = prior.load(OUT / "results.json")
by_id = {r["case_id"]: r for r in results}
panel = prior.load(prior.EVIDENCE)
alternative = prior.load(prior.REVIEW)["alternative_witness_annotations"]
alts = defaultdict(set)
for row in alternative:
    alts[row["case_id"], row["unit_id"]].update(row["chunk_uids"])
panel_rows = []
for case in panel["cases"]:
    cid = case["case_id"]
    result = by_id[cid]
    units = []
    for unit in case["units"]:
        known = {w["chunk_uid"] for w in unit["reference_witnesses"]} | alts[cid, unit["id"]]
        stages = {}
        for arm in ARMS:
            candidate = {h["uid"] for h in result["dense"] + result["lexical"][arm]}
            selected = {h["uid"] for h in result["rrf"][arm][:8 if arm == "A8" else 12]}
            packet = set(result["packets"][arm]["uids"])
            stages[arm] = {s: sorted(uids & known) for s, uids in (("candidate", candidate), ("selected", selected), ("packet", packet))}
        units.append({"unit_id": unit["id"], "criterion": unit["criterion"], "known_witnesses": sorted(known), "stages": stages})
    panel_rows.append({"case_id": cid, "role": case["role"], "units": units})
panel_summary = {}
for arm in ARMS:
    panel_summary[arm] = {stage: {"known_witness_unit_hits": sum(bool(u["stages"][arm][stage]) for c in panel_rows for u in c["units"]),
                                 "all_units_hit_cases": sum(bool(c["units"]) and all(u["stages"][arm][stage] for u in c["units"]) for c in panel_rows)}
                          for stage in ("candidate", "selected", "packet")}
save("known_witness_panel.json", {"method": "Frozen source-grounded known witnesses plus previously reviewed alternatives. UID intersections locate evidence; review alternative sources and source semantics before asserting semantic misses. 2 refusal controls unscored.",
                                  "answerable_cases": 10, "required_units": 26, "summary": panel_summary, "cases": panel_rows})

targets = []
for r in results:
    for target in r["targets"]:
        uid = target["uid"]
        target = dict(target)
        target["arms"] = {}
        for arm in ARMS:
            target["arms"][arm] = {
                "lexical_rank": next((i+1 for i, h in enumerate(r["lexical"][arm]) if h["uid"] == uid), None),
                "rrf_rank": next((i+1 for i, h in enumerate(r["rrf"][arm]) if h["uid"] == uid), None),
                "in_packet": uid in r["packets"][arm]["uids"],
                "omitted_by_byte_limit": uid in r["packets"][arm]["omitted"],
            }
        targets.append(target)
save("target_diagnostics.json", targets)

grades_path = OUT.parent / "full77_sol_top12_20261020/grades.jsonl"
grades = {r["case_id"]: r for r in (prior.json.loads(s) for s in grades_path.read_text(encoding="utf-8").splitlines())}
audits = []
for r in results:
    cid = r["case_id"]
    grade = grades[cid]
    known_citations = {unquote(s.partition(":")[2]) for s in grade["cited_source_ids"]}
    original = set(r["packets"]["A12"]["uids"])
    assert known_citations <= original, (cid, known_citations-original)
    check = {}
    for arm in ARMS:
        current = set(r["packets"][arm]["uids"])
        check[arm] = {"same_source_set_as_A12": current == original,
                      "same_order_as_A12": r["packets"][arm]["uids"] == r["packets"]["A12"]["uids"],
                      "lost_sources": sorted(original-current), "gained_sources": sorted(current-original),
                      "historical_cited_sources_lost": sorted(known_citations-current),
                      "novel_vs_A12_candidate_pool": sorted(current-{h["uid"] for h in r["dense"]+r["lexical"]["A12"]})}
    audits.append({"case_id": cid, "query": r["query"], "historical_group": grade["group"],
                   "historical_all_three_PASS": all(grade[k] == "PASS" for k in ("correctness", "completeness", "support")),
                   "historical_note": grade["note"], "arms": check})
save("all77_source_audit.json", {"method": "All77 changed sources and saved Sol_top12 answer citation retention; source replacement is not itself a semantic regression, and retained citations are not a correctness proof.",
                                 "grades_input_sha256": prior.sha(grades_path), "cases": audits})

summary = {}
for arm in ARMS:
    sizes = [r["packets"][arm]["bytes"] for r in results]
    summary[arm] = {
        "source_set_changed_vs_A12": sum(not a["arms"][arm]["same_source_set_as_A12"] for a in audits),
        "source_order_changed_vs_A12": sum(not a["arms"][arm]["same_order_as_A12"] for a in audits),
        "cases_losing_historical_citations": sum(bool(a["arms"][arm]["historical_cited_sources_lost"]) for a in audits),
        "historical_pass_cases_losing_citations": sum(a["historical_all_three_PASS"] and bool(a["arms"][arm]["historical_cited_sources_lost"]) for a in audits),
        "cases_with_sources_outside_A12_candidate_pool": sum(bool(a["arms"][arm]["novel_vs_A12_candidate_pool"]) for a in audits),
        "packet_mean_bytes": round(mean(sizes), 1), "packet_median_bytes": median(sizes), "packet_max_bytes": max(sizes),
        "cases_with_byte_omissions": sum(bool(r["packets"][arm]["omitted"]) for r in results),
        "omitted_sources": sum(len(r["packets"][arm]["omitted"]) for r in results),
        "packet_known_witness_panel": panel_summary[arm]["packet"]}
save("automated_summary.json", {"status": "SOURCE_REVIEW_PENDING", "arms": summary})
print(prior.encoded(summary))

lines = ["# Source review inputs", "", "These are inspection aids, not automatic semantic judgments.", ""]
for a in audits:
    if a["arms"]["K12"]["same_source_set_as_A12"]:
        continue
    cid = a["case_id"]
    lines += ["## " + cid, "", a["query"], "", "Prior grade: " + a["historical_group"] + " / " + str(a["historical_all_three_PASS"]), a["historical_note"], "",
              "Lost citations: " + str(a["arms"]["K12"]["historical_cited_sources_lost"]), ""]
    for arm, which in (("A12", "lost_sources"), ("K12", "gained_sources")):
        packet = prior.load(OUT / "packets" / f"{cid}_{arm}.json")
        for d in packet["documents"]:
            if d["chunk_id"] not in a["arms"]["K12"][which]:
                continue
            lines += ["### " + arm + " " + d["chunk_id"], "", d["text"], ""]
(OUT / "review_inputs.md").write_text("\n".join(lines), encoding="utf-8")
