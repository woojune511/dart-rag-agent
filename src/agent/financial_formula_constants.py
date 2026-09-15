"""Formula-constant provenance; request interpretation is the Compiler's job."""

from __future__ import annotations

import math
from typing import Any, Mapping, Sequence

from src.agent.financial_request_units import build_request_units


_NEUTRAL_CONSTANTS = {0.0, 1.0, 100.0}


class FormulaConstantError(ValueError):
    def __init__(self, code: str, detail: str = ""):
        super().__init__(code)
        self.detail = detail


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
