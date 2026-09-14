"""Explicit OFFLINE transport projection for authored internal-program fixtures.

This is not imported by agent runtime. It does not create source proof,
repair bad choices, or model semantic accuracy; it only expresses test choices in
the production wire layout so existing arithmetic/validator tests stay useful.
"""
from copy import deepcopy
import hashlib


def short_ref(value, prefix):
    return value if prefix in {"o", "r", "q"} else prefix + hashlib.sha256(value.encode()).hexdigest()[:8]


def project_offline_program_to_wire(program, model):
    program = program.model_dump() if hasattr(program, "model_dump") else deepcopy(program)
    output_type = model.model_fields["outputs"].annotation
    outputs = {}
    assertions = {candidate_id: row["evidence_text"] for row in program.get("source_assertions") or [] for candidate_id in row["candidate_ids"]}

    def addresses(node):
        if isinstance(node, list):
            return [addresses(item) for item in node]
        if not isinstance(node, dict):
            return node
        result = deepcopy(node)
        for key, value in node.items():
            if key == "request_unit_ids":
                result[key] = [short_ref(item, "q") for item in value]
            elif isinstance(value, (dict, list)):
                result[key] = addresses(value)
        return result

    def selection(source_id, binding, *, display=False):
        prefix = "source_display_" if display else "source_"
        references = dict(model.__compiler_references__.entries)
        interpretation = deepcopy(binding.get(prefix + "interpretation"))
        evidence = {}

        def context(row):
            key = (row["context_id"], row["evidence_text"])
            if key not in evidence:
                evidence[key] = {"context_ref": references.get(key[0], short_ref(key[0], "x")),
                    "evidence_text": key[1], "supports_interpretation": False, "resolves": []}
            return evidence[key]

        if interpretation is not None:
            own_axes = model.__compiler_references__.axis_refs_for_candidate(source_id)
            if any(axis not in own_axes for axis in interpretation.pop("axis_refs", [])):
                raise ValueError("offline_fixture_has_foreign_axis")
            for row in interpretation.pop("context_evidence", []):
                context(row)["supports_interpretation"] = True
        for row in binding.get("source_display_context_bindings" if display else "context_bindings") or []:
            context(row)["resolves"].append({"field": row["field"], "value": row["value"]})
        result = {"source_ref": references.get(source_id, short_ref(source_id, "c")),
            "interpretation": addresses(interpretation), "evidence_text": assertions.get(source_id)}
        if evidence:
            result["context_evidence"] = list(evidence.values())
        return result

    def reading(row):
        result = {"source_ref": short_ref(row["candidate_id"], "c")}
        for key, prefix in (("surface_id", "s"), ("first_piece_id", "p"), ("last_piece_id", "p")):
            if row.get(key) is not None:
                result[key.replace("_id", "_ref")] = short_ref(row[key], prefix)
        if row.get("row_description_quote") is not None:
            result["row_description_quote"] = row["row_description_quote"]
        return result

    def groups(owner_key, field, rows, transform):
        # Optional result has a single non-null model argument.
        reply = output_type.model_fields[owner_key].annotation
        result_type = next(item for item in reply.model_fields["result"].annotation.__args__ if item is not type(None))
        if field == "inputs":
            group_type = result_type.model_fields["inputs"].annotation
        else:
            subject_type = result_type.model_fields["subjects"].annotation.__args__[0]
            group_type = subject_type.model_fields["support"].annotation
        grouped = {key: [] for key in group_type.model_fields}
        for row in rows:
            key = short_ref(row["source_requirement_id"], "r") if row.get("source_requirement_id") else "own"
            if key == "own" and "dependencies" in grouped:
                key = "dependencies"
            grouped.setdefault(key, []).append(transform(row))
        return grouped

    for field in ("direct_bindings", "expressions", "narrative_bindings"):
        for row in program.get(field) or []:
            key = short_ref(row["obligation_id"], "o")
            if key not in output_type.model_fields:
                outputs[key] = {"status": "ready", "result": {}}
                continue
            if field == "direct_bindings":
                result = {"selection": selection(row["candidate_id"], row),
                    "compatibility_refs": [short_ref(item, "c") for item in row.get("compatibility_candidate_ids") or []]}
            elif field == "expressions":
                def operand(binding):
                    return {**selection(binding["source_id"], binding), "variable": binding["variable"],
                        "scope_applicability_fields": binding.get("scope_applicability_fields") or []}
                result = {"inputs": groups(key, "inputs", row.get("variable_bindings") or [], operand),
                    # Explicit offline projection: absence stays null. Do not
                    # infer comparison intent or rename historical variables.
                    "comparison_request_unit_id": row.get("comparison_request_unit_id"),
                    "formula": row["formula"], "display_unit": row.get("display_unit", ""), "display_format": row.get("display_format", ""),
                    "source_display": selection(row["source_display_candidate_id"], row, display=True) if row.get("source_display_candidate_id") else None,
                    "source_display_reason": row.get("source_display_reason", ""),
                    "compatibility_refs": [short_ref(item, "c") for item in row.get("compatibility_candidate_ids") or []], "constants": row.get("constants") or []}
            else:
                subjects = []
                for subject in row.get("subject_bindings") or []:
                    subjects.append({"subject": subject["subject"],
                        "support": groups(key, "support", subject["evidence_selections"], reading),
                        "claims": [{"text": claim["text"], "evidence": groups(key, "evidence", claim["fact_evidence_selections"], reading)}
                            for claim in row.get("claims") or [] if claim["subject_binding_id"] == subject["subject_binding_id"]]})
                result = {"subjects": subjects, "scope_applicability_fields": row.get("scope_applicability_fields") or [],
                    "basis_interpretation": row.get("basis_interpretation", "")}
            outputs[key] = {"status": "ready", "result": result}
    for source_field, status in (("missing_obligation_ids", "missing"), ("ambiguous_obligation_ids", "ambiguous")):
        for owner_id in program.get(source_field) or []:
            key = short_ref(owner_id, "o")
            previous_content = outputs.get(key, {}).get("result")
            outputs[short_ref(owner_id, "o")] = {"status": "ready" if program.get("status") == "ready" else status,
                "result": previous_content}
    return {"outputs": outputs, "rationale": program.get("rationale", "")}
