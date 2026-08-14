from __future__ import annotations

import ast
import json
import unittest
from collections.abc import Mapping
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

from src.agent import financial_graph_reconciliation as reconciliation
from src.agent import financial_reconciliation_candidates as candidates
from src.agent.financial_graph_reconciliation import FinancialAgentReconciliationMixin


class FinancialReconciliationCandidateTests(unittest.TestCase):
    def test_current_source_statement_and_unit_projection_contract(self) -> None:
        agent = FinancialAgentReconciliationMixin()

        with (
            patch.object(candidates, "_normalise_spaces", side_effect=lambda value: str(value).strip()) as normalise,
            patch.object(
                candidates,
                "FINANCIAL_DOCUMENT_STATEMENT_HINT_POLICIES",
                [
                    {"markers": ["income"], "statement_types": ["income_statement"]},
                    {"markers": ["note"], "statement_types": ["notes"]},
                ],
            ),
        ):
            self.assertEqual(
                candidates._candidate_statement_type(
                    {"source_anchor": "note anchor", "source_context": "tail"},
                    {"statement_type": "  explicit  ", "section_path": "ignored"},
                ),
                "explicit",
            )
            explicit_calls = normalise.call_count
            self.assertEqual(
                candidates._candidate_statement_type(
                    {"source_anchor": "note anchor", "source_context": "tail"},
                    {
                        "section_path": "income section",
                        "section_title": "note title",
                        "local_heading": "local",
                        "table_context": "table",
                    },
                ),
                "income_statement",
            )
            self.assertGreater(normalise.call_count, explicit_calls)
            self.assertEqual(candidates._candidate_statement_type({}, {}), "")

        shared_metadata = {"semantic_label": "Margin", "row_label": "Row", "statement_type": "notes"}
        candidate = {"metadata": shared_metadata}
        operand = {"unit_family": "PERCENT", "label": "Margin", "aliases": ["Rate"]}
        cell = {"column_headers": ["Percent"]}
        before = (deepcopy(candidate), deepcopy(operand), deepcopy(cell))
        policy = {
            "percent_unit": "%",
            "ambiguous_krw_units": ["", "원"],
            "note_statement_type": "notes",
        }
        with (
            patch.object(candidates, "RECONCILIATION_POLICY", policy),
            patch.object(candidates, "_label_implies_percent_metric", return_value=True) as percent_match,
            patch.object(candidates, "_resolve_candidate_local_unit_hint", return_value="억원") as local_unit,
        ):
            self.assertEqual(
                candidates._structured_candidate_unit_hint(
                    raw_value="10",
                    raw_unit="",
                    candidate=candidate,
                    operand=operand,
                    selected_cell=cell,
                ),
                "%",
            )
            percent_match.assert_called_once()
            local_unit.assert_not_called()

        with (
            patch.object(candidates, "RECONCILIATION_POLICY", policy),
            patch.object(candidates, "_label_implies_percent_metric", return_value=False),
            patch.object(candidates, "_resolve_candidate_local_unit_hint", return_value="억원") as local_unit,
        ):
            self.assertEqual(
                candidates._structured_candidate_unit_hint(
                    raw_value="10",
                    raw_unit="",
                    candidate=candidate,
                    operand={"unit_family": "KRW"},
                    selected_cell=cell,
                ),
                "억원",
            )
            local_unit.assert_called_once_with(candidate, "10")
        self.assertEqual((candidate, operand, cell), before)

        class PolicyCopyBomb(Mapping):
            def __iter__(self):
                raise RuntimeError("policy copy failed")

            def __len__(self):
                return 1

            def __getitem__(self, key):
                raise KeyError(key)

        with (
            patch.object(candidates, "RECONCILIATION_POLICY", PolicyCopyBomb()),
            self.assertRaisesRegex(RuntimeError, "policy copy failed"),
        ):
            candidates._structured_candidate_unit_hint(
                raw_value="10",
                raw_unit="%",
                candidate=candidate,
                operand={"unit_family": "PERCENT"},
                selected_cell=cell,
            )

    def test_current_source_period_and_identity_projection_contract(self) -> None:
        agent = FinancialAgentReconciliationMixin()
        self.assertEqual(candidates._fallback_period_text_for_operand({"role": "current_period"}, [2022, 2024]), "2024")
        self.assertEqual(candidates._fallback_period_text_for_operand({"role": "prior_period"}, [2024]), "2023")
        self.assertEqual(
            candidates._fallback_period_text_for_operand({"_effective_period_focus": "prior"}, [2021, 2023, 2022]),
            "2022",
        )
        self.assertEqual(candidates._fallback_period_text_for_operand({"period_hint": " Q1 "}, []), "Q1")

        events = []
        with (
            patch.object(candidates, "operand_period_focus", side_effect=lambda operand, focus: events.append("focus") or "prior"),
            patch.object(candidates, "_structured_cell_period_text", side_effect=lambda cell, years, focus: events.append("period") or "unknown"),
            patch.object(candidates, "RECONCILIATION_POLICY", {"period_presence_pattern": r"\d{4}"}),
            patch.object(candidates, "operand_target_years", side_effect=lambda operand, years: events.append("targets") or [2023]),
            patch.object(candidates, "_fallback_period_text_for_operand", side_effect=lambda operand, years: events.append("fallback") or "2022") as fallback,
        ):
            period = candidates._resolved_period_text_for_operand(
                operand={"role": "prior_period"},
                cell={"_report_year": object(), "report_year": "bad", "year": 2023},
                query_years=[2023],
                period_focus="unknown",
            )
        self.assertEqual(period, "2023")
        self.assertEqual(events, ["focus", "period", "targets"])
        fallback.assert_not_called()

        with (
            patch.object(candidates, "operand_period_focus", return_value="current"),
            patch.object(candidates, "_structured_cell_period_text", return_value="not-present"),
            patch.object(candidates, "RECONCILIATION_POLICY", {"period_presence_pattern": r"\d{4}"}),
            patch.object(candidates, "operand_target_years", return_value=[2024]),
            patch.object(candidates, "_fallback_period_text_for_operand", return_value="2024") as fallback,
        ):
            self.assertEqual(
                candidates._resolved_period_text_for_operand(
                    operand={"role": "current_period"},
                    cell={},
                    query_years=[2024],
                    period_focus="current",
                ),
                "2024",
            )
            fallback.assert_called_once_with(
                {"role": "current_period", "_effective_period_focus": "current"},
                [2024],
            )

        self.assertEqual(candidates.structured_cell_identity({"value_id": " value "}), "value")
        self.assertEqual(candidates.structured_cell_identity({"row_index": 2, "column_index": 3}), "2:3")
        self.assertEqual(
            candidates.structured_cell_identity({"column_headers": [" A ", "", "B"], "value_text": " 10 "}),
            "A|B|10",
        )

        with (
            patch.object(candidates, "operand_period_focus", side_effect=RuntimeError("focus failed")),
            patch.object(candidates, "_structured_cell_period_text") as stopped_period,
            self.assertRaisesRegex(RuntimeError, "focus failed"),
        ):
            candidates._resolved_period_text_for_operand(operand={}, cell={}, query_years=[], period_focus="unknown")
        stopped_period.assert_not_called()

    def test_current_source_candidate_and_cell_score_contract(self) -> None:
        agent = FinancialAgentReconciliationMixin()
        candidate = {"candidate_id": "candidate"}
        cell = {"value_id": "cell"}
        operand = {"label": "Metric"}
        preferred = ["notes"]
        constraints = {"period_focus": "current"}
        years = [2024, 2023]
        report_scope = {"company": "Example"}
        events = []

        with (
            patch.object(candidates, "_score_operand_candidate", side_effect=lambda *args, **kwargs: events.append(("candidate", args, kwargs)) or 2.5),
            patch.object(candidates, "operand_target_years", side_effect=lambda op, ys: events.append(("years", op, ys)) or [2024]),
            patch.object(candidates, "operand_period_focus", side_effect=lambda op, focus: events.append(("focus", op, focus)) or "current"),
            patch.object(candidates, "score_structured_cell", side_effect=lambda *args, **kwargs: events.append(("cell", args, kwargs)) or 1.25),
            patch.object(candidates, "_resolved_period_text_for_operand", side_effect=lambda **kwargs: events.append(("period", kwargs)) or "2024") as period,
        ):
            score, period_text = candidates.pair_candidate_period_score(
                candidate=candidate,
                cell=cell,
                operand=operand,
                preferred_statement_types=preferred,
                constraints=constraints,
                query_years=years,
                period_focus="current",
                report_scope=report_scope,
            )
        self.assertEqual((score, period_text), (3.75, "2024"))
        self.assertEqual([event[0] for event in events], ["candidate", "years", "focus", "cell", "period"])
        self.assertIs(events[0][1][0], candidate)
        self.assertIs(events[1][1], operand)
        self.assertIs(events[1][2], years)
        self.assertIs(events[3][1][0], cell)
        period.assert_called_once_with(operand=operand, cell=cell, query_years=years, period_focus="current")

        with (
            patch.object(candidates, "_score_operand_candidate", side_effect=RuntimeError("candidate score failed")),
            patch.object(candidates, "score_structured_cell") as stopped_cell,
            patch.object(candidates, "_resolved_period_text_for_operand") as stopped_period,
            self.assertRaisesRegex(RuntimeError, "candidate score failed"),
        ):
            candidates.pair_candidate_period_score(
                candidate=candidate,
                cell=cell,
                operand=operand,
                preferred_statement_types=preferred,
                constraints=constraints,
                query_years=years,
                period_focus="current",
            )
        stopped_cell.assert_not_called()
        stopped_period.assert_not_called()

    def test_current_source_row_build_and_effective_unit_contract(self) -> None:
        agent = FinancialAgentReconciliationMixin()
        nested = {"preserve": True}
        candidate = {
            "candidate_id": "candidate",
            "source_anchor": "anchor",
            "metadata": {
                "unit_hint": "metadata-unit",
                "semantic_label": "Semantic",
                "row_label": "Row",
                "table_source_id": "table",
                "consolidation_scope": "consolidated",
                "value_role": "metadata-role",
                "aggregation_stage": "metadata-stage",
                "aggregate_label": "metadata-label",
                "nested": nested,
            },
        }
        cell = {
            "value_text": " (12) ",
            "unit_hint": "cell-unit",
            "value_role": " cell-role ",
            "aggregation_stage": " direct ",
            "aggregate_label": " total ",
        }
        operand = {"label": "Metric", "concept": "metric", "role": "numerator"}
        before = (deepcopy(candidate), deepcopy(cell), deepcopy(operand))
        events = []

        def unit_owner(**kwargs):
            events.append(("unit", kwargs))
            return "억원"

        with (
            patch.object(candidates, "_structured_candidate_unit_hint", side_effect=unit_owner),
            patch.object(candidates, "_normalise_operand_value", side_effect=lambda value, unit: events.append(("normalise", value, unit)) or (-12.0, "KRW")),
            patch.object(candidates, "_candidate_statement_type", side_effect=lambda current, metadata: events.append(("statement", current, metadata)) or "notes"),
            patch.object(candidates, "coerce_lookup_magnitude_value", side_effect=lambda **kwargs: events.append(("magnitude", kwargs)) or 12.0),
            patch.object(candidates, "_resolved_period_text_for_operand", side_effect=lambda **kwargs: events.append(("period", kwargs)) or "2024"),
            patch.object(candidates, "_normalise_spaces", side_effect=lambda value: events.append(("spaces", value)) or str(value).strip()),
        ):
            row = candidates.build_operand_row_from_candidate_cell(
                candidate=candidate,
                selected_cell=cell,
                operand=operand,
                index=7,
                period_focus="current",
                query_years=[2024],
            )
        self.assertEqual([event[0] for event in events], ["unit", "normalise", "statement", "magnitude", "period", "statement", "spaces", "spaces", "spaces"])
        self.assertEqual(row["operand_id"], "op_007")
        self.assertEqual(row["label"], "2024 Metric")
        self.assertEqual(row["normalized_value"], 12.0)
        self.assertEqual(row["raw_unit"], "억원")
        self.assertEqual(row["value_role"], "cell-role")
        self.assertEqual(row["aggregation_stage"], "direct")
        self.assertEqual(row["aggregate_label"], "total")
        self.assertEqual((candidate, cell, operand), before)

        with (
            patch.object(candidates, "_structured_candidate_unit_hint", return_value="억원"),
            patch.object(candidates, "_normalise_operand_value", return_value=(None, "KRW")),
            patch.object(candidates, "_candidate_statement_type", return_value="notes"),
            patch.object(candidates, "coerce_lookup_magnitude_value", return_value=None),
            patch.object(candidates, "_resolved_period_text_for_operand") as stopped_period,
        ):
            self.assertIsNone(
                candidates.build_operand_row_from_candidate_cell(
                    candidate=candidate,
                    selected_cell=cell,
                    operand=operand,
                    index=1,
                    period_focus="current",
                    query_years=[2024],
                )
            )
        stopped_period.assert_not_called()

        unit_calls = []
        with patch.object(candidates, "_structured_candidate_unit_hint", side_effect=lambda **kwargs: unit_calls.append(kwargs) or "metadata-unit"):
            self.assertEqual(
                candidates.effective_structured_cell_unit_hint(candidate=candidate, selected_cell={"value_text": "1"}, operand=operand),
                "metadata-unit",
            )
        self.assertEqual(unit_calls[0]["raw_value"], "1")
        self.assertEqual(unit_calls[0]["raw_unit"], "metadata-unit")
        self.assertIs(unit_calls[0]["candidate"], candidate)
        self.assertIs(unit_calls[0]["operand"], operand)

    def test_current_source_reconciliation_match_selection_contract(self) -> None:
        agent = FinancialAgentReconciliationMixin()
        nested = {"preserve": True}
        first = {"label": "Metric", "role": "prior", "candidate_ids": ["a"], "nested": nested}
        exact = {"label": "Metric", "role": "current", "candidate_ids": ["b"], "nested": nested}
        result = {"matched_operands": [first, exact, {"label": "Other", "role": "current"}]}
        before = deepcopy(result)

        selected = candidates.find_reconciliation_match_entry(result, {"label": " Metric ", "role": " current "})
        self.assertEqual(selected["candidate_ids"], ["b"])
        self.assertIsNot(selected, exact)
        self.assertIs(selected["nested"], nested)
        selected["candidate_ids"].append("shared")
        self.assertEqual(exact["candidate_ids"], ["b", "shared"])
        exact["candidate_ids"].pop()
        fallback = candidates.find_reconciliation_match_entry(result, {"label": "Metric", "role": "missing"})
        self.assertEqual(fallback["candidate_ids"], ["a"])
        self.assertEqual(candidates.find_reconciliation_match_entry(result, {"label": "Absent"}), {})
        self.assertEqual(result, before)

        class RowsBomb:
            def __iter__(self):
                raise RuntimeError("rows failed")

        with self.assertRaisesRegex(RuntimeError, "rows failed"):
            candidates.find_reconciliation_match_entry({"matched_operands": RowsBomb()}, {"label": "Metric"})

    def test_current_source_candidate_id_and_copy_projection_contract(self) -> None:
        agent = FinancialAgentReconciliationMixin()
        nested = {"preserve": True}
        candidate_map = {
            "a": {"candidate_id": "a", "candidate_kind": "evidence_row", "metadata": {"row_text": " row ", "nested": nested}},
            "a::raw_row": {"candidate_id": "a::raw_row"},
            "recon::a": {"candidate_id": "recon::a"},
            "recon::a::raw_row": {"candidate_id": "recon::a::raw_row"},
            "recon::b": {"candidate_id": "recon::b"},
            "b": {"candidate_id": "b"},
        }
        before = deepcopy(candidate_map)
        expanded = candidates.expand_structured_candidate_ids([" a ", "recon::a", "", "b", "missing", "a"], candidate_map)
        self.assertEqual(expanded, ["a", "a::raw_row", "recon::a", "recon::a::raw_row", "b", "recon::b"])

        selected = candidates.structured_candidate_from_id(" a ", candidate_map)
        self.assertEqual(selected["candidate_kind"], "table_row")
        self.assertIsNot(selected, candidate_map["a"])
        self.assertIs(selected["metadata"], candidate_map["a"]["metadata"])
        self.assertIs(selected["metadata"]["nested"], nested)
        self.assertIsNone(candidates.structured_candidate_from_id("missing", candidate_map))
        self.assertEqual(candidate_map, before)

        class CandidateIdBomb:
            def __str__(self):
                raise RuntimeError("candidate id failed")

        with self.assertRaisesRegex(RuntimeError, "candidate id failed"):
            candidates.expand_structured_candidate_ids([CandidateIdBomb()], candidate_map)

    def test_current_source_candidate_projection_static_inventory(self) -> None:
        reconciliation_tree = ast.parse(Path(reconciliation.__file__).read_text(encoding="utf-8-sig"))
        owner_tree = ast.parse(Path(candidates.__file__).read_text(encoding="utf-8-sig"))
        names = {
            "_candidate_statement_type",
            "_structured_candidate_unit_hint",
            "_fallback_period_text_for_operand",
            "_resolved_period_text_for_operand",
            "structured_cell_identity",
            "pair_candidate_period_score",
            "find_reconciliation_match_entry",
            "build_operand_row_from_candidate_cell",
            "effective_structured_cell_unit_hint",
            "expand_structured_candidate_ids",
            "structured_candidate_from_id",
        }
        expected_spans = {
            "_candidate_statement_type": 36,
            "_structured_candidate_unit_hint": 37,
            "_fallback_period_text_for_operand": 11,
            "_resolved_period_text_for_operand": 28,
            "structured_cell_identity": 10,
            "pair_candidate_period_score": 32,
            "find_reconciliation_match_entry": 16,
            "build_operand_row_from_candidate_cell": 62,
            "effective_structured_cell_unit_hint": 16,
            "expand_structured_candidate_ids": 25,
            "structured_candidate_from_id": 12,
        }
        definitions = {
            node.name: node.end_lineno - node.lineno + 1
            for node in ast.walk(owner_tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in names
        }
        self.assertEqual(definitions, expected_spans)
        self.assertEqual(sum(definitions.values()), 285)
        self.assertFalse(
            any(
                isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                and node.name
                in {
                    "_candidate_statement_type",
                    "_structured_candidate_unit_hint",
                    "_fallback_period_text_for_operand",
                    "_structured_cell_identity",
                    "_resolved_period_text_for_operand",
                    "_pair_candidate_period_score",
                    "_find_reconciliation_match_entry",
                    "_build_operand_row_from_candidate_cell",
                    "_effective_structured_cell_unit_hint",
                    "_expand_structured_candidate_ids",
                    "_structured_candidate_from_id",
                }
                for node in ast.walk(reconciliation_tree)
            )
        )

        rows = []
        for module, tree in (("owner", owner_tree), ("reconciliation", reconciliation_tree)):
            parents = {child: parent for parent in ast.walk(tree) for child in ast.iter_child_nodes(parent)}

            def enclosing_function(node):
                current = node
                while current in parents:
                    current = parents[current]
                    if isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        return current.name
                return "<module>"

            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                name = node.func.id if isinstance(node.func, ast.Name) else node.func.attr if isinstance(node.func, ast.Attribute) else ""
                if name not in names:
                    continue
                current = node
                try_depth = 0
                while current in parents:
                    current = parents[current]
                    if isinstance(current, ast.Try):
                        try_depth += 1
                rows.append(
                    (
                        name,
                        module,
                        enclosing_function(node),
                        type(node.func).__name__,
                        len(node.args),
                        tuple(keyword.arg for keyword in node.keywords),
                        try_depth,
                    )
                )
        self.assertEqual(len(rows), 26)
        owner_local = [row for row in rows if row[1] == "owner"]
        self.assertEqual((len(rows) - len(owner_local), len(owner_local)), (5, 21))
        self.assertTrue(all(row[-1] == 0 for row in rows))

        expected_external = {
            ("structured_candidate_from_id", "append_candidate_evidence"): 1,
            ("expand_structured_candidate_ids", "_evidence_items_from_reconciliation_matches"): 1,
            ("expand_structured_candidate_ids", "_extract_structured_operands_from_reconciliation"): 1,
            ("structured_candidate_from_id", "_extract_structured_operands_from_reconciliation"): 1,
            ("build_operand_row_from_candidate_cell", "_extract_structured_operands_from_reconciliation"): 1,
        }
        actual_external = {}
        for name, module, caller, *_ in rows:
            if module == "owner":
                continue
            actual_external[(name, caller)] = actual_external.get((name, caller), 0) + 1
        self.assertEqual(actual_external, expected_external)

        baseline = json.loads(Path("tests/fixtures/runtime_domain_terms_baseline.json").read_text(encoding="utf-8"))
        self.assertEqual(len(baseline["records"]), 217)
        self.assertEqual(
            [
                record
                for record in baseline["records"]
                if record["path"] == "src/agent/financial_graph_reconciliation.py"
                and any(98 <= line <= 402 for line in record.get("first_lines", []))
            ],
            [],
        )
        imported = {
            alias.name
            for node in reconciliation_tree.body
            if isinstance(node, ast.ImportFrom) and node.module == "src.agent.financial_reconciliation_candidates"
            for alias in node.names
        }
        self.assertEqual(
            imported,
            {
                "build_operand_row_from_candidate_cell",
                "effective_structured_cell_unit_hint",
                "expand_structured_candidate_ids",
                "extract_structured_period_pair_rows",
                "find_reconciliation_match_entry",
                "pair_candidate_period_score",
                "structured_candidate_from_id",
                "structured_cell_identity",
            },
        )

    def test_current_source_candidate_projection_callers_adopt_and_stop(self) -> None:
        agent = FinancialAgentReconciliationMixin()
        pair_calls = []
        row_calls = []
        events = []

        required_operands = [
            {"label": "Metric", "concept": "metric", "role": "current_period"},
            {"label": "Metric", "concept": "metric", "role": "prior_period"},
        ]
        reconciliation_result = {
            "matched_operands": [
                {"label": "Metric", "role": "current_period", "candidate_ids": ["candidate"]},
                {"label": "Metric", "role": "prior_period", "candidate_ids": ["candidate"]},
            ]
        }
        candidate_map = {
            "candidate": {
                "candidate_id": "candidate",
                "candidate_kind": "structured_value",
                "metadata": {
                    "table_source_id": "table",
                    "structured_cells": [
                        {"value_id": "current", "value_text": "10"},
                        {"value_id": "prior", "value_text": "8"},
                    ],
                },
            }
        }
        inputs_before = deepcopy((required_operands, reconciliation_result, candidate_map))

        def score_owner(**kwargs):
            pair_calls.append(kwargs)
            role = kwargs["operand"]["role"]
            value_id = kwargs["cell"]["value_id"]
            accepted = (role == "current_period" and value_id == "current") or (role == "prior_period" and value_id == "prior")
            return (10.0 if accepted else 1.0), ("2024" if value_id == "current" else "2023")

        def row_owner(**kwargs):
            row_calls.append(kwargs)
            return {"label": kwargs["operand"]["label"], "matched_operand_role": kwargs["operand"]["role"]}

        with (
            patch.object(candidates, "find_reconciliation_match_entry", side_effect=lambda result, operand: next(row for row in result["matched_operands"] if row["role"] == operand["role"])),
            patch.object(candidates, "expand_structured_candidate_ids", side_effect=lambda ids, mapping: list(ids)),
            patch.object(candidates, "structured_candidate_from_id", side_effect=lambda cid, mapping: dict(mapping[cid])),
            patch.object(candidates, "candidate_satisfies_direct_acceptance_contract", return_value=True),
            patch.object(candidates, "pair_candidate_period_score", side_effect=score_owner),
            patch.object(candidates, "structured_cell_identity", side_effect=lambda cell: cell["value_id"]),
            patch.object(candidates, "effective_structured_cell_unit_hint", side_effect=lambda **kwargs: "억원"),
            patch.object(candidates, "build_operand_row_from_candidate_cell", side_effect=row_owner),
        ):
            rows, handled = candidates.extract_structured_period_pair_rows(
                required_operands=required_operands,
                reconciliation_result=reconciliation_result,
                candidate_map=candidate_map,
                preferred_statement_types=["notes"],
                constraints={"period_focus": "current"},
                query_years=[2024, 2023],
                start_index=4,
                operation_family="growth_rate",
                report_scope={"company": "Example"},
            )
        self.assertEqual([row["matched_operand_role"] for row in rows], ["current_period", "prior_period"])
        self.assertEqual(handled, {("Metric", "current_period"), ("Metric", "prior_period")})
        self.assertEqual([call["index"] for call in row_calls], [4, 5])
        self.assertEqual(len(pair_calls), 4)
        self.assertEqual((required_operands, reconciliation_result, candidate_map), inputs_before)

        state = {
            "reconciliation_result": {"status": "ready", "matched_operands": []},
            "active_subtask": {"required_operands": [{"label": "Metric", "role": "value", "required": True}]},
            "report_scope": {},
        }
        state_before = deepcopy(state)
        candidate = {"candidate_id": "candidate", "candidate_kind": "structured_value", "metadata": {"structured_cells": [{"value_text": "10"}]}}
        with (
            patch.object(reconciliation, "active_subtask_with_sibling_lookup_surfaces", side_effect=lambda active, current: active),
            patch.object(reconciliation, "_query_years_from_state", return_value=[2024]),
            patch.object(agent, "_build_reconciliation_candidates", return_value=[candidate]),
            patch.object(reconciliation, "extract_structured_period_pair_rows", return_value=([], set())),
            patch.object(reconciliation, "expand_structured_candidate_ids", return_value=["candidate"]),
            patch.object(reconciliation, "structured_candidate_from_id", return_value=dict(candidate)),
            patch.object(reconciliation, "_score_operand_candidate", return_value=1.0),
            patch.object(reconciliation, "select_structured_cell", return_value={"value_text": "10"}),
            patch.object(reconciliation, "candidate_satisfies_direct_acceptance_contract", return_value=True),
            patch.object(reconciliation, "build_operand_row_from_candidate_cell", return_value={"evidence_id": "candidate"}) as build_row,
            patch.object(reconciliation, "repair_note_operand_units_from_same_block", side_effect=lambda rows, mapping: events.append("repair") or rows),
        ):
            projected = agent._extract_structured_operands_from_reconciliation(state)
        self.assertEqual(projected, [{"evidence_id": "candidate"}])
        build_row.assert_called_once()
        self.assertEqual(events, ["repair"])
        self.assertEqual(state, state_before)

        with (
            patch.object(reconciliation, "active_subtask_with_sibling_lookup_surfaces", side_effect=lambda active, current: active),
            patch.object(reconciliation, "_query_years_from_state", return_value=[2024]),
            patch.object(agent, "_build_reconciliation_candidates", return_value=[candidate]),
            patch.object(reconciliation, "extract_structured_period_pair_rows", return_value=([], set())),
            patch.object(reconciliation, "expand_structured_candidate_ids", side_effect=RuntimeError("expand failed")),
            patch.object(reconciliation, "structured_candidate_from_id") as stopped_candidate,
            patch.object(reconciliation, "build_operand_row_from_candidate_cell") as stopped_row,
            patch.object(reconciliation, "repair_note_operand_units_from_same_block") as stopped_repair,
            self.assertRaisesRegex(RuntimeError, "expand failed"),
        ):
            agent._extract_structured_operands_from_reconciliation(state)
        stopped_candidate.assert_not_called()
        stopped_row.assert_not_called()
        stopped_repair.assert_not_called()
        self.assertEqual(state, state_before)

    def test_current_source_structured_period_pair_grouping_and_candidate_gates(self) -> None:
        agent = FinancialAgentReconciliationMixin()
        operand_nested = {"preserve": True}
        cell_nested = {"cell": True}
        required_operands = [
            {"label": "Current Label", "concept": "metric", "role": "current_period", "nested": operand_nested},
            {"label": "Prior Label", "concept": "metric", "role": "prior_period", "nested": operand_nested},
            {"label": "Ignored", "concept": "metric", "role": "value"},
            {"label": "Incomplete", "concept": "other", "role": "current_period"},
        ]
        reconciliation_result = {
            "matched_operands": [
                {"role": "current_period", "candidate_ids": [" raw ", "", "unsupported"]},
                {"role": "prior_period", "candidate_ids": ["raw", "missing"]},
            ]
        }
        raw_metadata = {"row_text": " raw row ", "year": 2024, "nested": {"metadata": True}}
        raw_candidate = {"candidate_id": "raw", "candidate_kind": "table_row", "metadata": raw_metadata}
        unsupported = {"candidate_id": "unsupported", "candidate_kind": "narrative", "metadata": {}}
        candidate_map = {"raw": raw_candidate, "unsupported": unsupported}
        inputs_before = deepcopy((required_operands, reconciliation_result, candidate_map))
        matched_operands = []
        parsed = []
        accepted_cells = []

        def match_owner(result, operand):
            self.assertIs(result, reconciliation_result)
            self.assertIs(result["matched_operands"], reconciliation_result["matched_operands"])
            matched_operands.append(operand)
            return next(item for item in result["matched_operands"] if item["role"] == operand["role"])

        def expand_owner(candidate_ids, mapping):
            self.assertEqual(candidate_ids, ["raw", "unsupported", "missing"])
            self.assertIs(mapping, candidate_map)
            return list(candidate_ids)

        def candidate_owner(candidate_id, mapping):
            self.assertIs(mapping, candidate_map)
            if candidate_id == "raw":
                return dict(raw_candidate)
            if candidate_id == "unsupported":
                return dict(unsupported)
            return None

        def parse_owner(row_text, metadata):
            parsed.append((row_text, metadata))
            self.assertEqual(row_text, " raw row ")
            self.assertIsNot(metadata, raw_metadata)
            self.assertIs(metadata["nested"], raw_metadata["nested"])
            return [{"value_id": "parsed", "value_text": "10", "nested": cell_nested}]

        def acceptance_owner(candidate, **kwargs):
            self.assertEqual(candidate["candidate_id"], "raw")
            accepted_cells.append(kwargs["selected_cell"])
            return False

        with (
            patch.object(candidates, "find_reconciliation_match_entry", side_effect=match_owner),
            patch.object(candidates, "expand_structured_candidate_ids", side_effect=expand_owner),
            patch.object(candidates, "structured_candidate_from_id", side_effect=candidate_owner),
            patch.object(candidates, "_parse_unstructured_table_row_cells", side_effect=parse_owner),
            patch.object(candidates, "candidate_satisfies_direct_acceptance_contract", side_effect=acceptance_owner),
            patch.object(candidates, "pair_candidate_period_score") as stopped_score,
        ):
            rows, handled = candidates.extract_structured_period_pair_rows(
                required_operands=required_operands,
                reconciliation_result=reconciliation_result,
                candidate_map=candidate_map,
                preferred_statement_types=["notes"],
                constraints={"period_focus": " current "},
                query_years=[2024, 2023],
                start_index=3,
                operation_family="growth_rate",
                report_scope={"company": "Example"},
            )

        self.assertEqual((rows, handled), ([], set()))
        self.assertEqual([item["role"] for item in matched_operands], ["current_period", "prior_period"])
        self.assertTrue(all(item is not required_operands[index] for index, item in enumerate(matched_operands)))
        self.assertTrue(all(item["nested"] is operand_nested for item in matched_operands))
        self.assertEqual(len(parsed), 1)
        self.assertEqual(len(accepted_cells), 2)
        for cell in accepted_cells:
            self.assertEqual(cell["_report_year"], 2024)
            self.assertIs(cell["nested"], cell_nested)
            self.assertEqual(len(cell["_sibling_cells"]), 1)
            self.assertIsNot(cell["_sibling_cells"][0], cell)
            self.assertIs(cell["_sibling_cells"][0]["nested"], cell_nested)
        stopped_score.assert_not_called()
        self.assertEqual((required_operands, reconciliation_result, candidate_map), inputs_before)

        class ConstraintBomb:
            def get(self, key, default=None):
                raise RuntimeError("constraint access failed")

        with (
            patch.object(candidates, "find_reconciliation_match_entry") as stopped_match,
            self.assertRaisesRegex(RuntimeError, "constraint access failed"),
        ):
            candidates.extract_structured_period_pair_rows(
                required_operands=required_operands,
                reconciliation_result=reconciliation_result,
                candidate_map=candidate_map,
                preferred_statement_types=[],
                constraints=ConstraintBomb(),
                query_years=[],
                start_index=1,
                operation_family="difference",
            )
        stopped_match.assert_not_called()

    def test_current_source_structured_period_pair_same_candidate_selection(self) -> None:
        agent = FinancialAgentReconciliationMixin()
        required_operands = [
            {"label": "Metric", "concept": "metric", "role": "current_period"},
            {"label": "Metric", "concept": "metric", "role": "prior_period"},
        ]
        reconciliation_result = {
            "matched_operands": [
                {"role": "current_period", "candidate_ids": ["candidate"]},
                {"role": "prior_period", "candidate_ids": ["candidate"]},
            ]
        }

        def run_case(cells, accepted, scored):
            nested = {"preserve": True}
            original_cells = [{**cell, "nested": nested} for cell in cells]
            candidate = {
                "candidate_id": "candidate",
                "candidate_kind": "structured_value",
                "metadata": {"structured_cells": original_cells},
            }
            row_calls = []

            def accept_owner(_candidate, *, operand, selected_cell, **_kwargs):
                return (operand["role"], selected_cell["value_id"]) in accepted

            def score_owner(*, operand, cell, **_kwargs):
                return scored[(operand["role"], cell["value_id"])]

            def row_owner(**kwargs):
                row_calls.append(kwargs)
                return {"role": kwargs["operand"]["role"], "cell": kwargs["selected_cell"]["value_id"]}

            with (
                patch.object(
                    candidates,
                    "find_reconciliation_match_entry",
                    side_effect=lambda result, operand: next(
                        item for item in result["matched_operands"] if item["role"] == operand["role"]
                    ),
                ),
                patch.object(candidates, "expand_structured_candidate_ids", return_value=["candidate"]),
                patch.object(candidates, "structured_candidate_from_id", return_value=dict(candidate)),
                patch.object(candidates, "candidate_satisfies_direct_acceptance_contract", side_effect=accept_owner),
                patch.object(candidates, "pair_candidate_period_score", side_effect=score_owner),
                patch.object(candidates, "structured_cell_identity", side_effect=lambda cell: cell["value_id"]),
                patch.object(candidates, "effective_structured_cell_unit_hint", return_value=""),
                patch.object(candidates, "build_operand_row_from_candidate_cell", side_effect=row_owner),
            ):
                result = candidates.extract_structured_period_pair_rows(
                    required_operands=required_operands,
                    reconciliation_result=reconciliation_result,
                    candidate_map={"candidate": candidate},
                    preferred_statement_types=["notes"],
                    constraints={"period_focus": "current"},
                    query_years=[2024, 2023],
                    start_index=4,
                    operation_family="growth_rate",
                )
            return result, row_calls, original_cells, nested

        (rows, handled), row_calls, _, _ = run_case(
            [{"value_id": "shared", "value_text": "10"}],
            {("current_period", "shared"), ("prior_period", "shared")},
            {
                ("current_period", "shared"): (100.0, "2024"),
                ("prior_period", "shared"): (100.0, "2023"),
            },
        )
        self.assertEqual((rows, handled, row_calls), ([], set(), []))

        (rows, handled), row_calls, _, _ = run_case(
            [
                {"value_id": "equal-current", "value_text": "10"},
                {"value_id": "equal-prior", "value_text": "8"},
            ],
            {("current_period", "equal-current"), ("prior_period", "equal-prior")},
            {
                ("current_period", "equal-current"): (100.0, "2024"),
                ("prior_period", "equal-prior"): (100.0, "2024"),
            },
        )
        self.assertEqual((rows, handled, row_calls), ([], set(), []))

        tie_cells = [
            {"value_id": "current-first", "value_text": "10"},
            {"value_id": "current-second", "value_text": "11"},
            {"value_id": "prior-first", "value_text": "8"},
            {"value_id": "prior-second", "value_text": "9"},
        ]
        accepted = {
            ("current_period", "current-first"),
            ("current_period", "current-second"),
            ("prior_period", "prior-first"),
            ("prior_period", "prior-second"),
        }
        scored = {
            key: (10.0 if key[0] == "current_period" else 5.0, "2024" if key[0] == "current_period" else "2023")
            for key in accepted
        }
        (rows, handled), row_calls, original_cells, nested = run_case(tie_cells, accepted, scored)
        self.assertEqual(rows, [{"role": "current_period", "cell": "current-first"}, {"role": "prior_period", "cell": "prior-first"}])
        self.assertEqual(handled, {("Metric", "current_period"), ("Metric", "prior_period")})
        self.assertEqual([call["index"] for call in row_calls], [4, 5])
        self.assertTrue(all(call["selected_cell"] is not original for call in row_calls for original in original_cells))
        self.assertTrue(all(call["selected_cell"]["nested"] is nested for call in row_calls))

        plain = {
            "candidate_id": "plain",
            "candidate_kind": "structured_value",
            "metadata": {"structured_cells": [{"value_id": "plain-current"}, {"value_id": "plain-prior"}]},
        }
        table = {
            "candidate_id": "table",
            "candidate_kind": "structured_value",
            "metadata": {"table_source_id": "table-id", "structured_cells": [{"value_id": "table-current"}, {"value_id": "table-prior"}]},
        }

        def accept_bonus(candidate, *, operand, selected_cell, **_kwargs):
            return selected_cell["value_id"].endswith("current" if operand["role"] == "current_period" else "prior")

        def score_bonus(*, candidate, operand, **_kwargs):
            base = 5.0 if candidate["candidate_id"] == "plain" else 4.75
            return base, "2024" if operand["role"] == "current_period" else "2023"

        bonus_rows = []
        with (
            patch.object(candidates, "find_reconciliation_match_entry", side_effect=lambda result, operand: {"candidate_ids": ["plain", "table"]}),
            patch.object(candidates, "expand_structured_candidate_ids", return_value=["plain", "table"]),
            patch.object(candidates, "structured_candidate_from_id", side_effect=lambda cid, mapping: dict(mapping[cid])),
            patch.object(candidates, "candidate_satisfies_direct_acceptance_contract", side_effect=accept_bonus),
            patch.object(candidates, "pair_candidate_period_score", side_effect=score_bonus),
            patch.object(candidates, "structured_cell_identity", side_effect=lambda cell: cell["value_id"]),
            patch.object(candidates, "effective_structured_cell_unit_hint", return_value=""),
            patch.object(
                candidates,
                "build_operand_row_from_candidate_cell",
                side_effect=lambda **kwargs: bonus_rows.append(kwargs) or {"candidate": kwargs["candidate"]["candidate_id"]},
            ),
        ):
            rows, _ = candidates.extract_structured_period_pair_rows(
                required_operands=required_operands,
                reconciliation_result=reconciliation_result,
                candidate_map={"plain": plain, "table": table},
                preferred_statement_types=[],
                constraints={},
                query_years=[],
                start_index=1,
                operation_family="difference",
            )
        self.assertEqual(rows, [{"candidate": "table"}, {"candidate": "table"}])
        self.assertEqual([call["candidate"]["candidate_id"] for call in bonus_rows], ["table", "table"])

    def test_current_source_structured_period_pair_cross_candidate_selection(self) -> None:
        agent = FinancialAgentReconciliationMixin()
        current_cell = {"value_id": "current", "value_text": "10", "nested": {"current": True}}
        first_prior_cell = {"value_id": "prior-first", "value_text": "8", "nested": {"prior": True}}
        tied_prior_cell = {"value_id": "prior-tied", "value_text": "7"}
        wrong_table_cell = {"value_id": "prior-wrong-table", "value_text": "100"}
        candidate_map = {
            "current": {
                "candidate_id": "current",
                "candidate_kind": "structured_value",
                "metadata": {"table_source_id": "shared", "structured_cells": [current_cell]},
            },
            "prior-first": {
                "candidate_id": "prior-first",
                "candidate_kind": "structured_value",
                "metadata": {"table_source_id": "shared", "structured_cells": [first_prior_cell]},
            },
            "prior-tied": {
                "candidate_id": "prior-tied",
                "candidate_kind": "structured_value",
                "metadata": {"table_source_id": "shared", "structured_cells": [tied_prior_cell]},
            },
            "prior-wrong": {
                "candidate_id": "prior-wrong",
                "candidate_kind": "structured_value",
                "metadata": {"table_source_id": "other", "structured_cells": [wrong_table_cell]},
            },
        }
        required_operands = [
            {"label": "Metric", "concept": "metric", "role": "current_period"},
            {"label": "Metric", "concept": "metric", "role": "prior_period"},
        ]
        result = {"matched_operands": [{"role": role, "candidate_ids": list(candidate_map)} for role in ("current_period", "prior_period")]}
        before = deepcopy((required_operands, result, candidate_map))
        row_calls = []

        def accept_owner(candidate, *, operand, **_kwargs):
            return (operand["role"] == "current_period" and candidate["candidate_id"] == "current") or (
                operand["role"] == "prior_period" and candidate["candidate_id"].startswith("prior")
            )

        def score_owner(*, candidate, operand, **_kwargs):
            if candidate["candidate_id"] == "prior-wrong":
                return 100.0, "2023"
            return (10.0 if operand["role"] == "current_period" else 5.0), (
                "2024" if operand["role"] == "current_period" else "2023"
            )

        def unit_owner(*, candidate, operand, **_kwargs):
            if operand["role"] == "current_period":
                return "억원"
            return ""

        def row_owner(**kwargs):
            row_calls.append(kwargs)
            return {"candidate": kwargs["candidate"]["candidate_id"], "role": kwargs["operand"]["role"]}

        with (
            patch.object(candidates, "find_reconciliation_match_entry", side_effect=lambda current, operand: next(item for item in current["matched_operands"] if item["role"] == operand["role"])),
            patch.object(candidates, "expand_structured_candidate_ids", side_effect=lambda ids, mapping: list(dict.fromkeys(ids))),
            patch.object(candidates, "structured_candidate_from_id", side_effect=lambda cid, mapping: dict(mapping[cid])),
            patch.object(candidates, "candidate_satisfies_direct_acceptance_contract", side_effect=accept_owner),
            patch.object(candidates, "pair_candidate_period_score", side_effect=score_owner),
            patch.object(candidates, "structured_cell_identity", side_effect=lambda cell: cell["value_id"]),
            patch.object(candidates, "effective_structured_cell_unit_hint", side_effect=unit_owner),
            patch.object(candidates, "build_operand_row_from_candidate_cell", side_effect=row_owner),
        ):
            rows, handled = candidates.extract_structured_period_pair_rows(
                required_operands=required_operands,
                reconciliation_result=result,
                candidate_map=candidate_map,
                preferred_statement_types=["notes"],
                constraints={"period_focus": "current"},
                query_years=[2024, 2023],
                start_index=9,
                operation_family="growth_rate",
                report_scope={"company": "Example"},
            )

        self.assertEqual(rows, [{"candidate": "current", "role": "current_period"}, {"candidate": "prior-first", "role": "prior_period"}])
        self.assertEqual(handled, {("Metric", "current_period"), ("Metric", "prior_period")})
        self.assertEqual([call["index"] for call in row_calls], [9, 10])
        self.assertEqual(row_calls[1]["selected_cell"]["unit_hint"], "억원")
        self.assertNotIn("unit_hint", first_prior_cell)
        self.assertIs(row_calls[0]["selected_cell"]["nested"], current_cell["nested"])
        self.assertIs(row_calls[1]["selected_cell"]["nested"], first_prior_cell["nested"])
        self.assertEqual((required_operands, result, candidate_map), before)

    def test_current_source_structured_period_pair_rows_handled_and_exception_contract(self) -> None:
        agent = FinancialAgentReconciliationMixin()
        required_operands = [
            {"label": "First", "concept": "first", "role": "current_period"},
            {"label": "First", "concept": "first", "role": "prior_period"},
            {"label": "Second", "concept": "second", "role": "current_period"},
            {"label": "Second", "concept": "second", "role": "prior_period"},
        ]
        candidate_map = {
            name: {
                "candidate_id": name,
                "candidate_kind": "structured_value",
                "metadata": {"structured_cells": [{"value_id": f"{name}-current"}, {"value_id": f"{name}-prior"}]},
            }
            for name in ("first", "second")
        }
        reconciliation_result = {
            "matched_operands": [
                {"label": label, "role": role, "candidate_ids": [key]}
                for label, key in (("First", "first"), ("Second", "second"))
                for role in ("current_period", "prior_period")
            ]
        }
        before = deepcopy((required_operands, reconciliation_result, candidate_map))
        row_calls = []

        def accept_owner(candidate, *, operand, selected_cell, **_kwargs):
            suffix = "current" if operand["role"] == "current_period" else "prior"
            return selected_cell["value_id"] == f"{candidate['candidate_id']}-{suffix}"

        def score_owner(*, operand, **_kwargs):
            return 1.0, "2024" if operand["role"] == "current_period" else "2023"

        def row_owner(**kwargs):
            row_calls.append(kwargs)
            if kwargs["candidate"]["candidate_id"] == "first" and kwargs["operand"]["role"] == "prior_period":
                return None
            return {"label": kwargs["operand"]["label"], "role": kwargs["operand"]["role"]}

        with (
            patch.object(candidates, "find_reconciliation_match_entry", side_effect=lambda result, operand: next(item for item in result["matched_operands"] if item["label"] == operand["label"] and item["role"] == operand["role"])),
            patch.object(candidates, "expand_structured_candidate_ids", side_effect=lambda ids, mapping: list(ids)),
            patch.object(candidates, "structured_candidate_from_id", side_effect=lambda cid, mapping: dict(mapping[cid])),
            patch.object(candidates, "candidate_satisfies_direct_acceptance_contract", side_effect=accept_owner),
            patch.object(candidates, "pair_candidate_period_score", side_effect=score_owner),
            patch.object(candidates, "structured_cell_identity", side_effect=lambda cell: cell["value_id"]),
            patch.object(
                candidates,
                "effective_structured_cell_unit_hint",
                side_effect=lambda *, operand, **_kwargs: "" if operand["role"] == "current_period" else "원",
            ),
            patch.object(candidates, "build_operand_row_from_candidate_cell", side_effect=row_owner),
        ):
            rows, handled = candidates.extract_structured_period_pair_rows(
                required_operands=required_operands,
                reconciliation_result=reconciliation_result,
                candidate_map=candidate_map,
                preferred_statement_types=[],
                constraints={},
                query_years=[2024, 2023],
                start_index=7,
                operation_family="difference",
            )

        self.assertEqual(rows, [{"label": "Second", "role": "current_period"}, {"label": "Second", "role": "prior_period"}])
        self.assertEqual(handled, {("Second", "current_period"), ("Second", "prior_period")})
        self.assertEqual([call["index"] for call in row_calls], [7, 8, 7, 8])
        self.assertEqual(row_calls[0]["selected_cell"]["unit_hint"], "원")
        self.assertEqual(row_calls[2]["selected_cell"]["unit_hint"], "원")
        self.assertEqual((required_operands, reconciliation_result, candidate_map), before)

        with (
            patch.object(candidates, "find_reconciliation_match_entry", side_effect=lambda result, operand: next(item for item in result["matched_operands"] if item["label"] == operand["label"] and item["role"] == operand["role"])),
            patch.object(candidates, "expand_structured_candidate_ids", return_value=["first"]),
            patch.object(candidates, "structured_candidate_from_id", return_value=dict(candidate_map["first"])),
            patch.object(candidates, "candidate_satisfies_direct_acceptance_contract", side_effect=accept_owner),
            patch.object(candidates, "pair_candidate_period_score", side_effect=score_owner),
            patch.object(candidates, "structured_cell_identity", side_effect=lambda cell: cell["value_id"]),
            patch.object(candidates, "effective_structured_cell_unit_hint", side_effect=RuntimeError("unit failed")),
            patch.object(candidates, "build_operand_row_from_candidate_cell") as stopped_row,
            self.assertRaisesRegex(RuntimeError, "unit failed"),
        ):
            candidates.extract_structured_period_pair_rows(
                required_operands=required_operands[:2],
                reconciliation_result=reconciliation_result,
                candidate_map=candidate_map,
                preferred_statement_types=[],
                constraints={},
                query_years=[],
                start_index=1,
                operation_family="difference",
            )
        stopped_row.assert_not_called()
        self.assertEqual((required_operands, reconciliation_result, candidate_map), before)

    def test_current_source_structured_period_pair_static_boundary_contract(self) -> None:
        reconciliation_path = Path(reconciliation.__file__)
        owner_path = Path(candidates.__file__)
        reconciliation_tree = ast.parse(reconciliation_path.read_text(encoding="utf-8-sig"))
        owner_tree = ast.parse(owner_path.read_text(encoding="utf-8-sig"))
        public_name = "extract_structured_period_pair_rows"
        private_name = "_" + public_name
        private_definitions = [
            node
            for node in ast.walk(reconciliation_tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == private_name
        ]
        self.assertEqual(private_definitions, [])
        public_definitions = [
            node
            for node in owner_tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == public_name
        ]
        self.assertEqual(len(public_definitions), 1)
        public_definition = public_definitions[0]
        self.assertEqual(public_definition.end_lineno - public_definition.lineno + 1, 201)
        self.assertEqual([argument.arg for argument in public_definition.args.args], [])
        self.assertEqual(
            [argument.arg for argument in public_definition.args.kwonlyargs],
            [
                "required_operands",
                "reconciliation_result",
                "candidate_map",
                "preferred_statement_types",
                "constraints",
                "query_years",
                "start_index",
                "operation_family",
                "report_scope",
            ],
        )
        self.assertFalse(
            any(
                isinstance(node, ast.Attribute)
                and isinstance(node.value, ast.Name)
                and node.value.id == "self"
                for node in ast.walk(public_definition)
            )
        )

        parents = {child: parent for parent in ast.walk(reconciliation_tree) for child in ast.iter_child_nodes(parent)}

        def enclosing_function(node):
            current = node
            while current in parents:
                current = parents[current]
                if isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    return current.name
            return "<module>"

        target_calls = []
        for node in ast.walk(reconciliation_tree):
            if not isinstance(node, ast.Call):
                continue
            name = node.func.id if isinstance(node.func, ast.Name) else node.func.attr if isinstance(node.func, ast.Attribute) else ""
            if name != public_name:
                continue
            current = node
            try_depth = 0
            while current in parents:
                current = parents[current]
                if isinstance(current, ast.Try):
                    try_depth += 1
            target_calls.append(
                (
                    enclosing_function(node),
                    type(node.func).__name__,
                    ast.unparse(node.func.value) if isinstance(node.func, ast.Attribute) else "",
                    len(node.args),
                    tuple(keyword.arg for keyword in node.keywords),
                    try_depth,
                )
            )
        self.assertEqual(
            target_calls,
            [
                (
                    "_extract_structured_operands_from_reconciliation",
                    "Name",
                    "",
                    0,
                    (
                        "required_operands",
                        "reconciliation_result",
                        "candidate_map",
                        "preferred_statement_types",
                        "constraints",
                        "query_years",
                        "start_index",
                        "operation_family",
                        "report_scope",
                    ),
                    0,
                )
            ],
        )

        owner_top_level = [node for node in owner_tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]
        current_owner_distribution = (
            sum(not node.name.startswith("_") for node in owner_top_level),
            sum(node.name.startswith("_") for node in owner_top_level),
        )
        self.assertEqual(current_owner_distribution, (8, 4))

        module_paths = {path.stem: path for path in Path("src/agent").glob("*.py")}
        edges = {name: set() for name in module_paths}
        for name, path in module_paths.items():
            tree = ast.parse(path.read_text(encoding="utf-8-sig"))
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("src.agent."):
                    dependency = node.module.rsplit(".", 1)[-1]
                    if dependency in module_paths:
                        edges[name].add(dependency)

        def reaches(source, target):
            seen = set()
            pending = [source]
            while pending:
                current = pending.pop()
                if current == target:
                    return True
                if current in seen:
                    continue
                seen.add(current)
                pending.extend(edges.get(current, ()))
            return False

        self.assertIn("financial_graph_helpers", edges["financial_reconciliation_candidates"])
        self.assertIn("financial_row_surfaces", edges["financial_reconciliation_candidates"])
        self.assertFalse(reaches("financial_graph_helpers", "financial_reconciliation_candidates"))
        self.assertFalse(reaches("financial_row_surfaces", "financial_reconciliation_candidates"))
        self.assertFalse(reaches("financial_reconciliation_candidates", "financial_graph_reconciliation"))

        expected_dependency_calls = {
            "candidate_satisfies_direct_acceptance_contract": 2,
            "_parse_unstructured_table_row_cells": 1,
        }
        for dependency_name, expected_count in expected_dependency_calls.items():
            owner_calls = [
                node
                for node in ast.walk(public_definition)
                if isinstance(node, ast.Call)
                and (
                    (isinstance(node.func, ast.Name) and node.func.id == dependency_name)
                    or (isinstance(node.func, ast.Attribute) and node.func.attr == dependency_name)
                )
            ]
            self.assertEqual(len(owner_calls), expected_count, dependency_name)

        baseline = json.loads(Path("tests/fixtures/runtime_domain_terms_baseline.json").read_text(encoding="utf-8"))
        self.assertEqual(len(baseline["records"]), 217)
        self.assertEqual(
            [
                record
                for record in baseline["records"]
                if record["path"] == "src/agent/financial_reconciliation_candidates.py"
                and any(public_definition.lineno <= line <= public_definition.end_lineno for line in record.get("first_lines", []))
            ],
            [],
        )
        imported = {
            alias.name
            for node in reconciliation_tree.body
            if isinstance(node, ast.ImportFrom) and node.module == "src.agent.financial_reconciliation_candidates"
            for alias in node.names
        }
        self.assertIn(public_name, imported)
        self.assertNotIn(private_name, reconciliation_path.read_text(encoding="utf-8-sig"))

    def test_current_source_structured_period_pair_caller_adoption_and_exception_stop(self) -> None:
        agent = FinancialAgentReconciliationMixin()
        current_operand = {"label": "Metric", "concept": "metric", "role": "current_period", "required": True}
        prior_operand = {"label": "Metric", "concept": "metric", "role": "prior_period", "required": True}
        value_operand = {"label": "Value", "concept": "value", "role": "value", "required": True}
        active_subtask = {
            "required_operands": [current_operand, prior_operand, value_operand],
            "constraints": {"period_focus": "current"},
            "preferred_statement_types": [" notes "],
            "operation_family": "lookup",
        }
        reconciliation_result = {
            "status": "ready",
            "matched_operands": [
                {"label": "Metric", "role": "current_period", "candidate_ids": ["pair"]},
                {"label": "Metric", "role": "prior_period", "candidate_ids": ["pair"]},
                {"label": "Value", "role": "value", "candidate_ids": ["value"]},
            ],
        }
        report_scope = {"company": "Example"}
        state = {
            "reconciliation_result": reconciliation_result,
            "active_subtask": active_subtask,
            "report_scope": report_scope,
        }
        value_candidate = {
            "candidate_id": "value",
            "candidate_kind": "structured_value",
            "metadata": {"structured_cells": [{"value_id": "value-cell", "value_text": "10"}]},
        }
        years = [2024, 2023]
        paired_current = {"label": "Metric", "matched_operand_role": "current_period"}
        paired_prior = {"label": "Metric", "matched_operand_role": "prior_period"}
        ordinary_row = {"label": "Value", "matched_operand_role": "value"}
        state_before = deepcopy(state)
        candidate_before = deepcopy(value_candidate)
        events = []
        pair_calls = []

        def pair_owner(**kwargs):
            events.append("pair")
            pair_calls.append(kwargs)
            return [paired_current, paired_prior], {("Metric", "current_period"), ("Metric", "prior_period")}

        def expand_owner(candidate_ids, mapping):
            events.append("expand")
            self.assertEqual(candidate_ids, ["value"])
            self.assertIs(mapping["value"], value_candidate)
            return list(candidate_ids)

        def repair_owner(rows, mapping):
            events.append("repair")
            self.assertEqual(rows, [paired_current, paired_prior, ordinary_row])
            self.assertIsNot(rows, pair_calls[0]["required_operands"])
            self.assertIs(mapping["value"], value_candidate)
            return rows

        with (
            patch.object(reconciliation, "active_subtask_with_sibling_lookup_surfaces", side_effect=lambda active, current: active_subtask),
            patch.object(reconciliation, "_query_years_from_state", return_value=years),
            patch.object(agent, "_build_reconciliation_candidates", return_value=[value_candidate]),
            patch.object(reconciliation, "extract_structured_period_pair_rows", side_effect=pair_owner),
            patch.object(reconciliation, "expand_structured_candidate_ids", side_effect=expand_owner),
            patch.object(reconciliation, "structured_candidate_from_id", side_effect=lambda cid, mapping: events.append("candidate") or dict(mapping[cid])),
            patch.object(reconciliation, "_score_operand_candidate", side_effect=lambda *args, **kwargs: events.append("score") or 1.0),
            patch.object(reconciliation, "select_structured_cell", side_effect=lambda cells, **kwargs: events.append("select") or cells[0]),
            patch.object(reconciliation, "candidate_satisfies_direct_acceptance_contract", side_effect=lambda *args, **kwargs: events.append("accept") or True),
            patch.object(reconciliation, "build_operand_row_from_candidate_cell", side_effect=lambda **kwargs: events.append("row") or ordinary_row),
            patch.object(reconciliation, "repair_note_operand_units_from_same_block", side_effect=repair_owner),
        ):
            projected = agent._extract_structured_operands_from_reconciliation(state)

        self.assertEqual(projected, [paired_current, paired_prior, ordinary_row])
        self.assertEqual(events, ["pair", "expand", "candidate", "score", "select", "accept", "row", "repair"])
        self.assertEqual(len(pair_calls), 1)
        pair_call = pair_calls[0]
        self.assertEqual(tuple(pair_call), (
            "required_operands",
            "reconciliation_result",
            "candidate_map",
            "preferred_statement_types",
            "constraints",
            "query_years",
            "start_index",
            "operation_family",
            "report_scope",
        ))
        self.assertEqual([item["role"] for item in pair_call["required_operands"]], ["current_period", "prior_period", "value"])
        self.assertTrue(all(item is not original for item, original in zip(pair_call["required_operands"], active_subtask["required_operands"])))
        self.assertIsNot(pair_call["reconciliation_result"], reconciliation_result)
        self.assertIs(pair_call["reconciliation_result"]["matched_operands"], reconciliation_result["matched_operands"])
        self.assertIs(pair_call["candidate_map"]["value"], value_candidate)
        self.assertEqual(pair_call["preferred_statement_types"], ["notes"])
        self.assertIsNot(pair_call["constraints"], active_subtask["constraints"])
        self.assertIs(pair_call["query_years"], years)
        self.assertEqual(pair_call["start_index"], 1)
        self.assertEqual(pair_call["operation_family"], "lookup")
        self.assertEqual(pair_call["report_scope"], report_scope)
        self.assertIsNot(pair_call["report_scope"], report_scope)
        self.assertEqual(state, state_before)
        self.assertEqual(value_candidate, candidate_before)

        with (
            patch.object(reconciliation, "active_subtask_with_sibling_lookup_surfaces", side_effect=lambda active, current: active_subtask),
            patch.object(reconciliation, "_query_years_from_state", return_value=years),
            patch.object(agent, "_build_reconciliation_candidates", return_value=[value_candidate]),
            patch.object(reconciliation, "extract_structured_period_pair_rows", side_effect=RuntimeError("pair failed")),
            patch.object(reconciliation, "expand_structured_candidate_ids") as stopped_expand,
            patch.object(reconciliation, "build_operand_row_from_candidate_cell") as stopped_row,
            patch.object(reconciliation, "repair_note_operand_units_from_same_block") as stopped_repair,
            self.assertRaisesRegex(RuntimeError, "pair failed"),
        ):
            agent._extract_structured_operands_from_reconciliation(state)
        stopped_expand.assert_not_called()
        stopped_row.assert_not_called()
        stopped_repair.assert_not_called()
        self.assertEqual(state, state_before)
        self.assertEqual(value_candidate, candidate_before)


if __name__ == "__main__":
    unittest.main()
