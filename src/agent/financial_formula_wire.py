"""Lossless infix-token lowering; request proofs live at their operand position."""

from __future__ import annotations

import keyword
import math

from src.agent.financial_formula_eval import _ALLOWED_FORMULA_FUNCTIONS


FORMULA_SYMBOLS = ("+", "-", "*", "/", "**", "(", ")", ",", "0", "1", "100",
                   *tuple(_ALLOWED_FORMULA_FUNCTIONS), "binding_count")


class FormulaWireError(ValueError):
    def __init__(self, code, index=None):
        super().__init__(code)
        self.location = "compiler_response.outputs.formula" + (f"[{index}]" if index is not None else "")


def lower_formula_tokens(tokens, *, source_variables, resolve_request):
    """Translate explicit tokens only; never infer a quantity or repair an AST.

    Symbols retain order/parentheses. Generated names connect each inline request
    operand to the existing internal scalar proof; they carry no model semantics.
    The existing validator still owns syntax, use, units and arithmetic safety.
    """
    if not isinstance(tokens, list) or not tokens:
        raise FormulaWireError("invalid_formula_tokens")
    names = set(source_variables)
    names.update(t["variable"] for t in tokens if isinstance(t, dict) and isinstance(t.get("variable"), str))

    def fresh_name(stem):
        name = stem
        while name in names:
            name += "_"
        names.add(name)
        return name

    parts, declarations, count_name = [], [], None
    for index, token in enumerate(tokens):
        if isinstance(token, str) and token in FORMULA_SYMBOLS:
            if token == "binding_count":
                if count_name is None:
                    count_name = fresh_name("_binding_count")
                parts.append(count_name)
            else:
                parts.append(token)
        elif isinstance(token, dict) and set(token) == {"variable"}:
            name = token["variable"]
            if not isinstance(name, str) or not name.isidentifier() or keyword.iskeyword(name):
                raise FormulaWireError("invalid_formula_variable", index)
            parts.append(name)
        elif isinstance(token, dict) and set(token) == {"value", "request_unit_id", "interpretation"}:
            value = token["value"]
            try:
                finite = type(value) in (int, float) and math.isfinite(value)
            except OverflowError:
                finite = False
            if not finite or not isinstance(token["interpretation"], str) or not token["interpretation"].strip():
                raise FormulaWireError("invalid_request_operand", index)
            name = fresh_name(f"_request_operand_{index}")
            declaration = resolve_request({"variable": name, **token})
            declarations.append(declaration)
            parts.append(name)
        else:
            raise FormulaWireError("invalid_formula_token", index)
    return {"formula": " ".join(parts), "request_inputs": declarations,
            "binding_count_variable": count_name}
