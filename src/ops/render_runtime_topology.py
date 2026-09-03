"""Render and verify the checked FinancialAgent graph topology block."""

from __future__ import annotations

import argparse
import ast
from pathlib import Path
from typing import Iterable


PROJECT_ROOT = Path(__file__).resolve().parents[2]
GRAPH_SOURCE = PROJECT_ROOT / "src" / "agent" / "financial_graph.py"
TOPOLOGY_DOCUMENT = PROJECT_ROOT / "docs" / "overview" / "runtime_flow_roles.md"
BEGIN_MARKER = "<!-- BEGIN GENERATED FINANCIAL GRAPH TOPOLOGY -->"
END_MARKER = "<!-- END GENERATED FINANCIAL GRAPH TOPOLOGY -->"


def _literal(value: ast.AST) -> str:
    if isinstance(value, ast.Constant):
        return str(value.value)
    if isinstance(value, ast.Name):
        return value.id
    if isinstance(value, ast.Attribute):
        return value.attr
    return ast.unparse(value)


def _graph_builder(tree: ast.Module) -> ast.FunctionDef:
    for node in tree.body:
        if not isinstance(node, ast.ClassDef) or node.name != "FinancialAgent":
            continue
        for member in node.body:
            if isinstance(member, ast.FunctionDef) and member.name == "_build_graph":
                return member
    raise ValueError("FinancialAgent._build_graph was not found")


def _graph_calls(builder: ast.FunctionDef) -> Iterable[ast.Call]:
    for statement in builder.body:
        value = statement.value if isinstance(statement, ast.Expr) else None
        if not isinstance(value, ast.Call):
            continue
        function = value.func
        if (
            isinstance(function, ast.Attribute)
            and isinstance(function.value, ast.Name)
            and function.value.id == "graph"
        ):
            yield value


def render_topology(source_path: Path = GRAPH_SOURCE) -> str:
    tree = ast.parse(source_path.read_text(encoding="utf-8-sig"))
    builder = _graph_builder(tree)
    nodes: list[tuple[str, str]] = []
    edges: list[str] = []
    entry = ""
    for call in _graph_calls(builder):
        method = call.func.attr
        if method == "add_node" and len(call.args) >= 2:
            nodes.append((_literal(call.args[0]), _literal(call.args[1])))
        elif method == "set_entry_point" and call.args:
            entry = _literal(call.args[0])
        elif method == "add_edge" and len(call.args) >= 2:
            edges.append(f"  {_literal(call.args[0])} -> {_literal(call.args[1])}")
        elif method == "add_conditional_edges" and len(call.args) >= 3:
            source = _literal(call.args[0])
            destinations = call.args[2]
            if not isinstance(destinations, ast.Dict):
                raise ValueError("conditional edge destinations must be a dict literal")
            for key, value in zip(destinations.keys, destinations.values):
                if key is None:
                    continue
                edges.append(
                    f"  {source} -- {_literal(key)} --> {_literal(value)}"
                )
    if not entry or not nodes or not edges:
        raise ValueError("incomplete FinancialAgent graph topology")
    lines = [BEGIN_MARKER, "```text", f"entry: {entry}", "nodes:"]
    lines.extend(f"  {name} -> FinancialAgent.{writer}" for name, writer in nodes)
    lines.append("edges:")
    lines.extend(edges)
    lines.extend(["```", END_MARKER])
    return "\n".join(lines)


def replace_checked_block(document: str, checked_block: str) -> str:
    start = document.find(BEGIN_MARKER)
    end = document.find(END_MARKER)
    if start < 0 or end < start:
        raise ValueError("topology markers are missing or out of order")
    end += len(END_MARKER)
    return f"{document[:start]}{checked_block}{document[end:]}"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    if args.check and args.write:
        parser.error("--check and --write are mutually exclusive")
    checked_block = render_topology()
    if not args.check and not args.write:
        print(checked_block)
        return
    document = TOPOLOGY_DOCUMENT.read_text(encoding="utf-8")
    updated = replace_checked_block(document, checked_block)
    if args.check:
        if updated != document:
            raise SystemExit(
                "FinancialAgent topology document is stale; run "
                "python -m src.ops.render_runtime_topology --write"
            )
        return
    TOPOLOGY_DOCUMENT.write_text(updated, encoding="utf-8")


if __name__ == "__main__":
    main()
