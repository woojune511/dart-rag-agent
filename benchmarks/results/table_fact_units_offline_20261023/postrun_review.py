"""Read-only FCT12 audit scaffolding; never run the experiment or grade semantics.

This file is prepared before output inspection.  Its entry point requires a
separate explicit flag after the parent authorizes reading completed outputs.
No value-string detector makes a required-evidence decision here.  Reviewers
must inspect actual source relations and enter their verdicts separately.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path


OUT = Path(__file__).resolve().parent
OLD = OUT.parent / "table_bundle_delivery_offline_20261022"
CONTRACT_SHA = "6df6519b4ac617579d1d9cdf92589dfbcc7de013d493f869115427b75f7ecee6"
SUPPLEMENT_SHA = "05f878a9eebaebbabfac8a35dd99d16be428b8fc330e223267ee644c3692a4c0"
FIELD = "table_fact_units"


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def file_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def original_packet(packet):
    result = copy.deepcopy(packet)
    for doc in result["documents"]:
        doc.pop(FIELD, None)
    return result


def decoded_wire(doc, decision, item):
    """Decode transmitted coordinates and locators, without semantic grading."""
    wire = doc.get(FIELD)
    projection = item.get("projection")
    result = {
        "chunk_uid": doc["chunk_id"],
        "source_id": doc["source_id"],
        "physical_key": item.get("physical_key"),
        "table_delivery_decision": decision,
        "projection_receipt_status": item.get("receipt", {}).get("status"),
        "projection_receipt_reason": item.get("receipt", {}).get("reason"),
        "receipt_is_not_independent_source_recheck": True,
        "transmitted_frame": None,
        "decoded_transmitted_units": [],
        "validated_not_delivered_units": [],
    }
    by_id = {u["unit_id"]: u for u in (projection or {}).get("units", [])}
    pool = decision.get("cell_pool_locators", [])
    if wire is not None:
        assert projection is not None
        assert len(pool) == len(wire["cells"])
        result["transmitted_frame"] = {
            k: v for k, v in wire.items() if k not in {"cells", "units"}
        }
        # This proves wire-to-projection identity, not source semantics.
        for locator, cell in zip(pool, wire["cells"]):
            assert cell == projection["cells"][locator]

    for record in decision.get("units", []):
        unit = by_id[record["unit_id"]]
        reference = {
            "unit_id": record["unit_id"],
            "source_expanded_at": unit["at"],
            "value_locator": unit["value"],
            "row_axis_locators": unit["row_axes"],
            "column_axis_locators": unit["column_axes"],
            "decision": record,
            "source_gate": "UPSTREAM_VALIDATED_REQUIRES_SOURCE_REVIEW",
            "requirement_gate": "PENDING_MANUAL_SOURCE_RELATION_REVIEW",
        }
        if record["status"] != "attached":
            reference["delivery_gate"] = "NOT_DELIVERED"
            result["validated_not_delivered_units"].append(reference)
            continue
        assert wire is not None
        row, col, value_idx, row_indices, col_indices = wire["units"][
            record["wire_unit_index"]
        ]
        assert [row, col] == unit["at"]
        assert pool[value_idx] == unit["value"]
        assert [pool[i] for i in row_indices] == unit["row_axes"]
        assert [pool[i] for i in col_indices] == unit["column_axes"]

        def cell_ref(index):
            return {"locator": pool[index], "wire_cell": wire["cells"][index]}

        reference.update(
            delivery_gate="ACTUALLY_TRANSMITTED",
            wire_unit_index=record["wire_unit_index"],
            value=cell_ref(value_idx),
            row_axes=[cell_ref(i) for i in row_indices],
            column_axes=[cell_ref(i) for i in col_indices],
        )
        result["decoded_transmitted_units"].append(reference)
    return result


def collect(case_id, results, projections):
    baseline = read_json(OUT / "packets" / f"{case_id}_A12.json")
    historical_baseline = read_json(OLD / "packets" / f"{case_id}_A12.json")
    packet = read_json(OUT / "packets" / f"{case_id}_FCT12.json")
    assert baseline == historical_baseline
    assert original_packet(packet) == baseline
    case = results[case_id]
    decisions = {d["uid"]: d for d in case["decisions"]}
    return {
        "case_id": case_id,
        "original_packet_preserved": True,
        "A12_path": str(OUT / "packets" / f"{case_id}_A12.json"),
        "T12_path": str(OLD / "packets" / f"{case_id}_T12.json"),
        "FCT12_path": str(OUT / "packets" / f"{case_id}_FCT12.json"),
        "FCT12_sha256": file_sha(OUT / "packets" / f"{case_id}_FCT12.json"),
        "source_receipts_path": str(OUT / "projections.json"),
        "actual_packet_byte_count_receipt": case.get("experimental_bytes"),
        "documents": [
            decoded_wire(doc, decisions[doc["chunk_id"]], projections[doc["chunk_id"]])
            for doc in packet["documents"]
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--authorized-output-read", action="store_true")
    parser.add_argument("--write-scaffold", action="store_true")
    args = parser.parse_args()
    if not args.authorized_output_read:
        parser.error("Completed-output reading requires separate parent authorization.")
    assert file_sha(OUT / "evaluation_contract.json") == CONTRACT_SHA
    assert file_sha(OUT / "evaluation_supplement.json") == SUPPLEMENT_SHA
    execution = read_json(OUT / "execution_result.json")
    assert execution["status"] == "completed"
    supplement = read_json(OUT / "evaluation_supplement.json")
    results = {r["case_id"]: r for r in read_json(OUT / "results.json")}
    projections = read_json(OUT / "projections.json")
    case_ids = sorted(
        {x["case_id"] for x in supplement["current_nonPASS_case_criteria"]}
        | {x["case_id"] for x in supplement["historical26_unit_panel"]}
    )
    output = {
        "status": "EVIDENCE_SCAFFOLD_ONLY_NOT_SEMANTIC_VERDICT",
        "contract_sha256": CONTRACT_SHA,
        "supplement_sha256": SUPPLEMENT_SHA,
        "generation_calls": 0,
        "retrieval_calls": 0,
        "experiment_rerun": False,
        "current_four_criteria": supplement["current_nonPASS_case_criteria"],
        "historical26_criteria": supplement["historical26_unit_panel"],
        "case_evidence": [collect(cid, results, projections) for cid in case_ids],
        "manual_review_required": [
            "Validate original source locators, source hashes, spans and literal cells.",
            "Inspect actual value-row-column-period-scope-unit relations, not string hits.",
            "Record source validation, delivery and frozen-requirement satisfaction separately.",
            "Compare A12 and T12 independently, including loss of T12 appended axes.",
            "No answer accuracy, faithfulness or refusal grade is measured.",
        ],
    }
    if args.write_scaffold:
        target = OUT / "postrun_review_scaffold.json"
        with target.open("x", encoding="utf-8") as handle:
            json.dump(output, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        print(target)
    print(json.dumps({"review_cases": len(case_ids), "semantic_verdicts": 0}))


if __name__ == "__main__":
    main()
