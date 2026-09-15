"""Authored operation transport helpers; never repair saved model responses."""
import ast

from src.ops.compiler_fixture_transport import project_offline_formula_steps as formula_steps


def request_operand(result):
    return next(arg for step in result["formula"] for arg in step["arguments"]
                if isinstance(arg, dict) and "value" in arg)


def formula_ast(formula):
    return ast.dump(ast.parse(formula, mode="eval"), include_attributes=False)
