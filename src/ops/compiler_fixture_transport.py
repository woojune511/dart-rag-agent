"""Explicit OFFLINE transport projection for authored internal-program fixtures.

This is not imported by agent runtime. It does not create source proof,
repair bad choices, or model semantic accuracy; it only expresses test choices in
the production wire layout so existing arithmetic/validator tests stay useful.
"""
from copy import deepcopy
import ast
import hashlib
import math
from src.agent.financial_formula_wire import FORMULA_OPERATION_GROUPS


def project_offline_formula_steps(formula, *, request_inputs=(), binding_count_variable=None):
    """Explicit authored-fixture conversion, never a production reply adapter.

    Only already-declared quantities can become request operands. Undeclared
    numeric literals, malformed/unused/duplicate proofs stay schema-invalid.
    """
    invalid = [{"invalid_offline_formula": formula}]
    try:
        declarations = {item["variable"]: item for item in request_inputs}
        if len(declarations) != len(request_inputs) or binding_count_variable in declarations:
            return invalid
        steps, used, count_used = [], set(), False
        binary = {ast.Add: "add", ast.Sub: "subtract", ast.Mult: "multiply", ast.Div: "divide", ast.Pow: "power"}
        arities = {name: (low, high) for names, low, high in FORMULA_OPERATION_GROUPS for name in names}

        def visit(node):
            nonlocal count_used
            if isinstance(node, ast.Name):
                if node.id in declarations:
                    used.add(node.id)
                    return {k: deepcopy(v) for k, v in declarations[node.id].items() if k != "variable"}
                if node.id == binding_count_variable:
                    count_used = True
                    return "binding_count"
                return {"variable": node.id}
            if isinstance(node, ast.Constant):
                value = node.value
                if type(value) not in (int, float):
                    raise ValueError("nonnumeric authored literal")
                return str(int(value)) if value in (0, 1, 100) else value
            if isinstance(node, ast.BinOp) and type(node.op) in binary:
                operation, arguments = binary[type(node.op)], [visit(node.left), visit(node.right)]
            elif isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
                operation, arguments = ("positive" if isinstance(node.op, ast.UAdd) else "negative"), [visit(node.operand)]
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and not node.keywords:
                operation, arguments = node.func.id, [visit(arg) for arg in node.args]
                if operation not in {"min", "max", "abs", "round", "log", "exp"}:
                    raise ValueError("unsupported authored function")
            else:
                raise ValueError("unsupported authored syntax")
            low, high = arities[operation]
            if not low <= len(arguments) <= high:
                raise ValueError("unsupported authored arity")
            steps.append({"operation": operation, "arguments": arguments})
            return {"step": len(steps)}

        final = visit(ast.parse(formula, mode="eval").body)
        if not steps:
            steps.append({"operation": "identity", "arguments": [final]})
        if used != set(declarations) or (binding_count_variable is not None and not count_used):
            return invalid
        return steps
    except (ValueError, TypeError, SyntaxError, KeyError):
        return invalid


def short_ref(value, prefix):
    return value if prefix in {"o", "r", "q"} else prefix + hashlib.sha256(value.encode()).hexdigest()[:8]


def project_offline_program_to_wire(program, model):
    program = program.model_dump() if hasattr(program, "model_dump") else deepcopy(program)
    output_type = model.model_fields["outputs"].annotation
    outputs = {}
    assertions = {candidate_id: row for row in program.get("source_assertions") or [] for candidate_id in row["candidate_ids"]}
    refs = model.__compiler_references__
    units = {unit.request_unit_id: unit for unit in refs.request_units}
    prose_bundles = {candidate_id: bundle for bundle in refs.prose_bundles for candidate_id in bundle.candidate_ids}

    def named_scalar_inputs(row):
        result = {"formula": row["formula"], "request_inputs": deepcopy(row.get("request_inputs", [])),
            "binding_count_variable": row.get("binding_count_variable")}
        for item in result["request_inputs"]:
            unit = units.get(item.get("request_unit_id"))
            if unit is not None and item.get("source_text") == unit.text:
                item.pop("source_text")
            else:
                item["source_text"] = item.get("source_text")  # Invalid proof stays schema-invalid.
        declarations = row.get("constants") or []
        if not declarations:
            return result
        # This explicit OFFLINE migration is for authored legacy fixtures only.
        # Production lowering never substitutes formula literals or invents inputs.
        invalid = {**result, "constants": deepcopy(declarations)}
        if result["request_inputs"] or result["binding_count_variable"] is not None:
            return invalid
        try:
            body = ast.parse(row["formula"], mode="eval")
        except (ValueError, SyntaxError):
            return invalid

        def literal(node):
            try:
                value = ast.literal_eval(node)
                return float(value) if type(value) in (int, float) and math.isfinite(value) else None
            except (ValueError, TypeError, OverflowError):
                return None

        values, names = set(), {node.id for node in ast.walk(body) if isinstance(node, ast.Name)}
        class Literals(ast.NodeVisitor):
            def generic_visit(self, node):
                if (value := literal(node)) is not None:
                    values.add(value)
                else:
                    super().generic_visit(node)
        Literals().visit(body)
        replacements = {}
        for index, item in enumerate(declarations, 1):
            if (not isinstance(item, dict) or set(item) - {
                    "value", "origin", "request_unit_id", "source_text", "interpretation"}
                    or ("source_text" in item and not isinstance(item["source_text"], str))):
                return invalid
            value = item.get("value")
            try:
                if type(value) not in (int, float) or not math.isfinite(value) or value not in values or value in replacements:
                    return invalid
            except OverflowError:
                return invalid
            variable = f"request_input_{index}"
            while variable in names:
                variable += "_"
            names.add(variable)
            if item.get("origin") == "query":
                unit, quote = units.get(item.get("request_unit_id")), item.get("source_text")
                interpretation = item.get("interpretation")
                if (unit is None or not isinstance(quote, str) or not quote.strip()
                        or (at := unit.text.find(quote)) < 0 or unit.text.find(quote, at + 1) >= 0
                        or not isinstance(interpretation, str) or not interpretation.strip()):
                    return invalid
                result["request_inputs"].append({"variable": variable, "value": value,
                    "request_unit_id": item["request_unit_id"], "interpretation": interpretation})
            elif item.get("origin") == "deterministic_cardinality":
                if (value != len(row.get("variable_bindings") or []) or item.get("request_unit_id") is not None
                        or item.get("interpretation") or result["binding_count_variable"] is not None):
                    return invalid
                result["binding_count_variable"] = variable
            else:
                return invalid
            replacements[value] = variable

        class Names(ast.NodeTransformer):
            def generic_visit(self, node):
                value = literal(node)
                return (ast.copy_location(ast.Name(id=replacements[value], ctx=ast.Load()), node)
                    if value in replacements else super().generic_visit(node))
        result["formula"] = ast.unparse(Names().visit(body))
        return result

    def scalar_inputs(row):
        named = named_scalar_inputs(row)
        if "constants" in named:
            return named  # Invalid legacy proof remains forbidden; no migration repair.
        source_names = {b["variable"] for b in row.get("variable_bindings") or []}
        if any(item.get("variable") in source_names for item in named["request_inputs"]):
            return {"formula": [{"invalid_offline_formula": row["formula"]}]}
        return {"formula": project_offline_formula_steps(**named)}

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
            if (dict(model.__compiler_references__.numeric_source_kinds).get(source_id) == "cell"
                    and interpretation.get("source_evidence_text") is None):
                # Internal default, absent from the cell wire. Non-null invalid
                # quotes and missing prose proofs must never be repaired here.
                interpretation.pop("source_evidence_text", None)
            own_axes = model.__compiler_references__.axis_refs_for_candidate(source_id)
            if any(axis not in own_axes for axis in interpretation.pop("axis_refs", [])):
                raise ValueError("offline_fixture_has_foreign_axis")
            for row in interpretation.pop("context_evidence", []):
                context(row)["supports_interpretation"] = True
        for row in binding.get("source_display_context_bindings" if display else "context_bindings") or []:
            context(row)["resolves"].append({"field": row["field"], "value": row["value"]})
        result = {"source_ref": references.get(source_id, short_ref(source_id, "c"))}
        if interpretation is not None:
            result["interpretation"] = addresses(interpretation)
        if source_id in prose_bundles or source_id in assertions:
            assertion, bundle = assertions.get(source_id, {}), prose_bundles.get(source_id)
            quote = assertion.get("evidence_text")
            span = bundle.value_span_by_candidate_id().get(source_id) if bundle else None
            valid = False
            if span and isinstance(quote, str) and quote and assertion.get("source_bundle_id") == bundle.source_bundle_id:
                at = bundle.source_text.find(quote)
                while at >= 0:
                    if at <= span[0] and span[1] <= at + len(quote):
                        valid = True
                        break
                    at = bundle.source_text.find(quote, at + 1)
            if not valid:
                # Preserve a bad/missing old quote as a forbidden field rather
                # than silently replacing it with the current candidate span.
                result["evidence_text"] = quote
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
                    **scalar_inputs(row), "display_unit": row.get("display_unit", ""), "display_format": row.get("display_format", ""),
                    "source_display": selection(row["source_display_candidate_id"], row, display=True) if row.get("source_display_candidate_id") else None,
                    "source_display_reason": row.get("source_display_reason", ""),
                    "compatibility_refs": [short_ref(item, "c") for item in row.get("compatibility_candidate_ids") or []]}
            else:
                subjects = []
                for subject in row.get("subject_bindings") or []:
                    subjects.append({"subject": subject["subject"],
                        "support": groups(key, "support", subject["evidence_selections"], reading),
                        "claims": [{"text": claim["text"], "evidence": groups(key, "evidence", claim["fact_evidence_selections"], reading)}
                            for claim in row.get("claims") or [] if claim["subject_binding_id"] == subject["subject_binding_id"]]})
                result = {"subjects": subjects, "scope_applicability_fields": row.get("scope_applicability_fields") or [],
                    "basis_interpretation": row.get("basis_interpretation", "")}
            if row["obligation_id"] in (program.get("relationship_bindings") or {}):
                result["relationship_refs"] = deepcopy(program["relationship_bindings"][row["obligation_id"]])
            outputs[key] = {"status": "ready", "result": result}
    for source_field, status in (("missing_obligation_ids", "missing"), ("ambiguous_obligation_ids", "ambiguous")):
        for owner_id in program.get(source_field) or []:
            key = short_ref(owner_id, "o")
            previous_content = outputs.get(key, {}).get("result")
            outputs[short_ref(owner_id, "o")] = {"status": "ready" if program.get("status") == "ready" else status,
                "result": previous_content}
    declarations = program.get("relationship_declarations") or {}
    frozen = getattr(model, "__read_only_relationship_declarations__", {})
    editable = {key: deepcopy(value) for key, value in declarations.items()
                if key not in frozen or value != frozen[key]}
    extra = {"relationship_declarations": editable} if editable or "relationship_declarations" in model.model_fields else {}
    return {"outputs": outputs, "rationale": program.get("rationale", ""), **extra}
