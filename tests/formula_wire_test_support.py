"""Authored token transport helpers; never repair saved model responses."""
import ast

from src.ops.compiler_fixture_transport import project_offline_formula_tokens as formula_tokens


def request_operand(result):
    return next(token for token in result["formula"] if isinstance(token, dict) and "value" in token)


def formula_ast(formula):
    return ast.dump(ast.parse(formula, mode="eval"), include_attributes=False)
