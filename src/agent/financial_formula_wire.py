"""Bounded operation steps lowered literally to the existing arithmetic engine."""
from __future__ import annotations

import keyword
import math

# Transport budgets, independent of question, metric or model token allowance.
MAX_FORMULA_STEPS = 64
MAX_EXPANDED_FORMULA_NODES = 4096
FORMULA_LITERALS = ("0", "1", "100", "binding_count")
FORMULA_OPERATION_GROUPS = (
    (("add", "subtract", "multiply", "divide", "power"), 2, 2),
    (("identity", "positive", "negative", "abs", "exp"), 1, 1),
    (("round", "log"), 1, 2),
    (("min", "max"), 2, 96),
)
_ARITIES = {name: (low, high) for names, low, high in FORMULA_OPERATION_GROUPS for name in names}
_BINARY = {"add": "+", "subtract": "-", "multiply": "*", "divide": "/", "power": "**"}


class FormulaWireError(ValueError):
    def __init__(self, code, index=None, argument=None):
        super().__init__(code)
        self.location = "compiler_response.outputs.formula" + (f"[{index}]" if index is not None else "")
        if argument is not None:
            self.location += f".arguments[{argument}]"


def lower_formula_steps(steps, *, source_variables, resolve_request):
    """Assemble stated operations only; no inferred quantity, choice or repair.

    Step references are one-based and backward-only. Every step must contribute
    to the final step. Expansion is bounded before joining, including shared
    subexpressions, so a small DAG cannot create an exponential formula.
    """
    if not isinstance(steps, list) or not steps:
        raise FormulaWireError("invalid_formula_steps")
    if len(steps) > MAX_FORMULA_STEPS:
        raise FormulaWireError("formula_step_limit")
    names = set(source_variables)
    for index, step in enumerate(steps):
        if not isinstance(step, dict) or set(step) != {"operation", "arguments"}:
            raise FormulaWireError("invalid_formula_step", index)
        operation, arguments = step["operation"], step["arguments"]
        if not isinstance(operation, str) or operation not in _ARITIES:
            raise FormulaWireError("invalid_formula_operation", index)
        low, high = _ARITIES[operation]
        if not isinstance(arguments, list) or not low <= len(arguments) <= high:
            raise FormulaWireError("invalid_formula_arity", index)
        names.update(arg["variable"] for arg in arguments
            if isinstance(arg, dict) and isinstance(arg.get("variable"), str))

    def fresh_name(stem):
        name = stem
        while name in names:
            name += "_"
        names.add(name)
        return name

    formulas, sizes, reachable, declarations, count_name = [], [], [], [], None
    for index, step in enumerate(steps):
        operation = step["operation"]
        parts, size, used = [], int(operation != "identity"), {index}
        for position, argument in enumerate(step["arguments"]):
            if isinstance(argument, str) and argument in FORMULA_LITERALS:
                if argument == "binding_count":
                    if count_name is None:
                        count_name = fresh_name("_binding_count")
                    part = count_name
                else:
                    part = argument
                size += 1
            elif isinstance(argument, dict) and set(argument) == {"step"}:
                reference = argument["step"]
                if type(reference) is not int or not 1 <= reference <= index:
                    raise FormulaWireError("invalid_formula_step_reference", index, position)
                part = formulas[reference - 1]
                size += sizes[reference - 1]
                used.update(reachable[reference - 1])
            elif isinstance(argument, dict) and set(argument) == {"variable"}:
                part = argument["variable"]
                if not isinstance(part, str) or not part.isidentifier() or keyword.iskeyword(part):
                    raise FormulaWireError("invalid_formula_variable", index, position)
                size += 1
            elif isinstance(argument, dict) and set(argument) == {"value", "request_unit_id", "interpretation"}:
                value = argument["value"]
                try:
                    finite = type(value) in (int, float) and math.isfinite(value)
                except OverflowError:
                    finite = False
                if not finite or not isinstance(argument["interpretation"], str) or not argument["interpretation"].strip():
                    raise FormulaWireError("invalid_request_operand", index, position)
                part = fresh_name(f"_request_operand_{index}_{position}")
                try:
                    declarations.append(resolve_request({"variable": part, **argument}))
                except ValueError as exc:
                    raise FormulaWireError(str(exc), index, position) from exc
                size += 1
            else:
                raise FormulaWireError("invalid_formula_argument", index, position)
            if size > MAX_EXPANDED_FORMULA_NODES:
                raise FormulaWireError("formula_expansion_limit", index)
            parts.append(part)
        if operation in _BINARY:
            formula = f"({parts[0]} {_BINARY[operation]} {parts[1]})"
        elif operation in {"positive", "negative"}:
            formula = f"({'+' if operation == 'positive' else '-'}{parts[0]})"
        elif operation == "identity":
            formula = parts[0]
        else:
            formula = f"{operation}({', '.join(parts)})"
        formulas.append(formula)
        sizes.append(size)
        reachable.append(used)
    unused = set(range(len(steps))) - reachable[-1]
    if unused:
        raise FormulaWireError("unused_formula_step", min(unused))
    return {"formula": formulas[-1], "request_inputs": declarations, "binding_count_variable": count_name}
