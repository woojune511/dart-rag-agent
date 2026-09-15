"""Formula-constant provenance; request interpretation is the Compiler's job."""

from __future__ import annotations

import math
import keyword
from typing import Any, Mapping, Sequence

from src.agent.financial_request_units import build_request_units


_NEUTRAL_CONSTANTS = {0.0, 1.0, 100.0}


class FormulaConstantError(ValueError):
    def __init__(self, code: str, detail: str = ""):
        super().__init__(code)
        self.detail = detail


def resolve_request_inputs(
    declarations: Any, count_variable: Any, *, source_variables: Sequence[str],
    obligation: Mapping[str, Any], query: str,
) -> list[dict[str, Any]]:
    """Resolve named dimensionless inputs without reading or rewriting a formula."""
    if not isinstance(declarations, list):
        raise FormulaConstantError("invalid_request_input")
    units = {unit.request_unit_id: unit for unit in build_request_units(query)}
    names, resolved = set(source_variables), []

    def claim_name(value):
        if not isinstance(value, str) or not value.isidentifier() or keyword.iskeyword(value):
            raise FormulaConstantError("invalid_request_input_variable")
        if value in names:
            raise FormulaConstantError("duplicate_variable_binding", value)
        names.add(value)
        return value

    for item in declarations:
        if not isinstance(item, Mapping) or set(item) != {
                "variable", "value", "request_unit_id", "source_text", "interpretation"}:
            raise FormulaConstantError("invalid_request_input")
        variable = claim_name(item["variable"])
        unit = units.get(item["request_unit_id"]) if isinstance(item["request_unit_id"], str) else None
        if unit is None or unit.request_unit_id not in (obligation.get("request_unit_ids") or []):
            raise FormulaConstantError("constant_request_not_owned")
        if item["source_text"] != unit.text:
            raise FormulaConstantError("constant_request_quote_invalid")
        # Reuse the exact request/finite-scalar checks, one named value at a time.
        # Equal scalar values with different names are not duplicate declarations.
        proof = resolve_formula_constants(
            [{**{key: value for key, value in item.items() if key != "variable"}, "origin": "query"}],
            [item["value"]], obligation=obligation, query=query, binding_count=len(source_variables))[0]
        resolved.append({"variable": variable, **proof})
    if count_variable is not None:
        variable = claim_name(count_variable)
        resolved.append({"variable": variable, "value": float(len(source_variables)),
            "origin": "deterministic_cardinality", "binding_count": len(source_variables),
            "validation_scope": "binding_cardinality"})
    return resolved


def resolve_formula_constants(
    declarations: Any, values: Sequence[float], *,
    obligation: Mapping[str, Any], query: str, binding_count: int,
) -> list[dict[str, Any]]:
    """Check exact owned quotes and scalar use, never infer a missing declaration.

    There is no query-wide numeral allowlist or word-to-number dictionary.
    A linked but wrong interpretation remains a semantic evaluation failure.
    """
    if not isinstance(declarations, list):
        raise FormulaConstantError("invalid_formula_constant")
    units = {unit.request_unit_id: unit for unit in build_request_units(query)}
    resolved, declared = [], set()
    for item in declarations:
        if not isinstance(item, Mapping):
            raise FormulaConstantError("invalid_formula_constant")
        value = item.get("value")
        try:
            finite = type(value) in (int, float) and math.isfinite(value)
        except OverflowError:
            finite = False
        if not finite:
            raise FormulaConstantError("invalid_formula_constant")
        value = float(value)
        if value in declared:
            raise FormulaConstantError("duplicate_formula_constant", repr(value))
        if value not in values:
            raise FormulaConstantError("unused_formula_constant", repr(value))
        declared.add(value)
        origin = item.get("origin")
        proof = {"value": value, "origin": origin}
        if origin == "query":
            unit_id = item.get("request_unit_id")
            if (not isinstance(unit_id, str) or unit_id not in units
                    or unit_id not in (obligation.get("request_unit_ids") or [])):
                raise FormulaConstantError("constant_request_not_owned")
            unit, quote = units[unit_id], item.get("source_text")
            if not isinstance(quote, str) or not quote.strip():
                raise FormulaConstantError("constant_request_quote_invalid")
            offset = unit.text.find(quote)
            if offset < 0 or unit.text.find(quote, offset + 1) >= 0:
                raise FormulaConstantError("constant_request_quote_invalid")
            interpretation = item.get("interpretation")
            if not isinstance(interpretation, str) or not interpretation.strip():
                raise FormulaConstantError("constant_interpretation_missing")
            proof.update(request_unit_id=unit_id, source_text=quote,
                request_span=[unit.start + offset, unit.start + offset + len(quote)],
                interpretation=interpretation,
                validation_scope="request_binding_not_semantic_equivalence")
        elif origin == "deterministic_cardinality":
            if value != binding_count:
                raise FormulaConstantError("constant_cardinality_mismatch", repr(value))
            if item.get("request_unit_id") is not None or item.get("interpretation"):
                raise FormulaConstantError("invalid_formula_constant_origin")
            proof.update(binding_count=binding_count, validation_scope="binding_cardinality")
        else:
            raise FormulaConstantError("invalid_formula_constant_origin")
        resolved.append(proof)
    for value in values:
        if value not in _NEUTRAL_CONSTANTS and value not in declared:
            raise FormulaConstantError("undeclared_formula_constant", repr(value))
    return resolved
