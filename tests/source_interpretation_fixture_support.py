"""Authored source proofs for arithmetic/transport fixtures, never model evaluation.

Call explicitly when migrating a historical test witness. Selected IDs, formula,
numbers, query, source bytes and expected values are not repaired or changed.
No runtime or provider response uses this helper.
"""
from copy import deepcopy

from src.agent.financial_request_units import build_request_units
from src.agent.financial_source_interpretation import interpretation_axis_sources
from src.agent.financial_output_relationships import output_relationships


def authored_relationship_program(program, owners, query, basis="authored fixture common basis"):
    """Explicit test authorship; never applied to a sampled model response."""
    result = deepcopy(program)
    groups, _ = output_relationships(owners, query)
    if groups:
        ready = {row["obligation_id"] for field in ("direct_bindings", "expressions", "narrative_bindings")
                 for row in result.get(field, [])}
        result.setdefault("relationship_declarations", {key: basis for key in groups})
        result.setdefault("relationship_bindings", {owner: [key for key, row in groups.items()
            if owner in row["output_ids"]] for owner in ready if any(owner in row["output_ids"] for row in groups.values())})
    return result


def authored_relationships(owners, query):
    rows = deepcopy(owners)
    groups = {}
    for row in rows:
        key = row.pop("coupling_key", "")
        if key:
            groups.setdefault(key, []).append(row["obligation_id"])
    units = build_request_units(query)
    for row in rows:
        row.setdefault("request_unit_ids", [unit.request_unit_id for unit in units])
    for members in groups.values():
        if len(members) < 2:
            continue
        relation = {"kind": "shared_basis", "output_ids": members,
            "request_unit_id": units[0].request_unit_id, "request_text": units[0].text}
        for row in rows:
            if row["obligation_id"] in members:
                row.setdefault("output_relationships", []).append(deepcopy(relation))
    return rows


def authored_source_program(program, owners, catalog, query):
    result = deepcopy(program)
    owner_by_id = {row["obligation_id"]: row for row in owners}
    candidates = {row["candidate_id"]: row for row in catalog}

    def add(binding, source_id, owner, parent, key):
        candidate = candidates.get(source_id)
        if candidate is None or binding.get(key) is not None:
            return
        scope = {**parent.get("scope", {}), **owner.get("scope", {})}
        target = owner.get("semantic_target") or parent.get("semantic_target") or {}
        subject = next(iter(target.get("local_subjects") or []), scope.get("segment") or candidate.get("row_label") or "fixture subject")
        refs = owner.get("request_unit_ids") or parent.get("request_unit_ids") or [u.request_unit_id for u in build_request_units(query)]
        proof = {"request_unit_ids": refs, "subject": subject, "metric": owner.get("label") or "fixture metric",
            "scope": {key: scope.get(key) or "" for key in ("segment", "basis")},
            "axis_refs": list(interpretation_axis_sources(candidate)), "context_evidence": []}
        if candidate.get("candidate_kind") == "sentence_value":
            proof["source_evidence_text"] = candidate["source_text"]
        binding[key] = proof

    for field in ("direct_bindings", "expressions", "narrative_bindings"):
        for row in result.get(field) or []:
            owner = owner_by_id.get(row["obligation_id"], {})
            if field == "direct_bindings":
                add(row, row["candidate_id"], owner, owner, "source_interpretation")
            elif field == "expressions":
                requirements = {r["requirement_id"]: r for r in owner.get("evidence_requirements") or []}
                for binding in row.get("variable_bindings") or []:
                    add(binding, binding["source_id"], requirements.get(binding.get("source_requirement_id"), owner), owner, "source_interpretation")
                if row.get("source_display_candidate_id"):
                    add(row, row["source_display_candidate_id"], owner, owner, "source_display_interpretation")
    return authored_relationship_program(result, owners, query)


def _authored_inputs(inputs):
    # Compiled envelopes already bind exact source/program bytes. Never rewrite
    # their inputs, including tampering fixtures testing validation drift.
    if inputs.get("compilation_envelope") is not None:
        return inputs
    copied = dict(inputs)
    query = copied.get("query", "")
    owners = authored_relationships(copied["obligations"], query)
    copied["obligations"] = owners
    copied["program"] = authored_source_program(copied["program"], owners, copied["candidate_catalog"], query)
    return copied


def validate_authored_fixture(**inputs):
    from src.agent.financial_calculation_execution import validate_semantic_calculation_program
    return validate_semantic_calculation_program(**_authored_inputs(inputs))


def execute_authored_fixture(**inputs):
    from tests.semantic_program_test_support import execute_semantic_calculation_program
    return execute_semantic_calculation_program(**_authored_inputs(inputs))
