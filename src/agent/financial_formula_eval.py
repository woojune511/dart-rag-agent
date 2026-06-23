"""Restricted arithmetic formula evaluation for deterministic calculations."""

from __future__ import annotations

import ast
import math
from typing import Any, Dict

_ALLOWED_FORMULA_FUNCTIONS: Dict[str, Any] = {
    "min": min,
    "max": max,
    "abs": abs,
    "round": round,
    "log": math.log,
    "exp": math.exp,
}


def _safe_eval_formula(expression: str, variables: Dict[str, float]) -> float:
    """Evaluate a restricted arithmetic expression used by calculation plans."""
    tree = ast.parse(expression, mode="eval")

    def _eval(node: ast.AST) -> float:
        if isinstance(node, ast.Expression):
            return _eval(node.body)
        if isinstance(node, ast.Constant):
            if isinstance(node.value, (int, float)):
                return float(node.value)
            raise ValueError("non-numeric constant")
        if isinstance(node, ast.Name):
            if node.id in variables:
                return float(variables[node.id])
            raise ValueError(f"unknown variable: {node.id}")
        if isinstance(node, ast.UnaryOp):
            operand = _eval(node.operand)
            if isinstance(node.op, ast.UAdd):
                return +operand
            if isinstance(node.op, ast.USub):
                return -operand
            raise ValueError("unsupported unary operator")
        if isinstance(node, ast.BinOp):
            left = _eval(node.left)
            right = _eval(node.right)
            if isinstance(node.op, ast.Add):
                return left + right
            if isinstance(node.op, ast.Sub):
                return left - right
            if isinstance(node.op, ast.Mult):
                return left * right
            if isinstance(node.op, ast.Div):
                if right == 0.0:
                    raise ZeroDivisionError("division by zero")
                return left / right
            if isinstance(node.op, ast.Pow):
                return left ** right
            raise ValueError("unsupported binary operator")
        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name):
                raise ValueError("unsupported function call")
            fn = _ALLOWED_FORMULA_FUNCTIONS.get(node.func.id)
            if fn is None:
                raise ValueError(f"unsupported function: {node.func.id}")
            if node.keywords:
                raise ValueError("keyword args are not allowed")
            args = [_eval(arg) for arg in node.args]
            return float(fn(*args))
        raise ValueError(f"unsupported AST node: {type(node).__name__}")

    return float(_eval(tree))
