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
            patch.object(candidates, "_operand_period_focus", side_effect=lambda operand, focus: events.append("focus") or "prior"),
            patch.object(candidates, "_structured_cell_period_text", side_effect=lambda cell, years, focus: events.append("period") or "unknown"),
            patch.object(candidates, "RECONCILIATION_POLICY", {"period_presence_pattern": r"\d{4}"}),
            patch.object(candidates, "_operand_target_years", side_effect=lambda operand, years: events.append("targets") or [2023]),
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
            patch.object(candidates, "_operand_period_focus", return_value="current"),
            patch.object(candidates, "_structured_cell_period_text", return_value="not-present"),
            patch.object(candidates, "RECONCILIATION_POLICY", {"period_presence_pattern": r"\d{4}"}),
            patch.object(candidates, "_operand_target_years", return_value=[2024]),
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
            patch.object(candidates, "_operand_period_focus", side_effect=RuntimeError("focus failed")),
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
            patch.object(candidates, "_operand_target_years", side_effect=lambda op, ys: events.append(("years", op, ys)) or [2024]),
            patch.object(candidates, "_operand_period_focus", side_effect=lambda op, focus: events.append(("focus", op, focus)) or "current"),
            patch.object(candidates, "_score_structured_cell", side_effect=lambda *args, **kwargs: events.append(("cell", args, kwargs)) or 1.25),
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
            patch.object(candidates, "_score_structured_cell") as stopped_cell,
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
        self.assertEqual((len(rows) - len(owner_local), len(owner_local)), (19, 7))
        self.assertTrue(all(row[-1] == 0 for row in rows))

        expected_external = {
            ("pair_candidate_period_score", "_extract_structured_period_pair_rows"): 2,
            ("structured_cell_identity", "_extract_structured_period_pair_rows"): 4,
            ("effective_structured_cell_unit_hint", "_extract_structured_period_pair_rows"): 2,
            ("build_operand_row_from_candidate_cell", "_extract_structured_period_pair_rows"): 2,
            ("find_reconciliation_match_entry", "_extract_structured_period_pair_rows"): 2,
            ("expand_structured_candidate_ids", "_extract_structured_period_pair_rows"): 1,
            ("structured_candidate_from_id", "_extract_structured_period_pair_rows"): 1,
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
            patch.object(reconciliation, "find_reconciliation_match_entry", side_effect=lambda result, operand: next(row for row in result["matched_operands"] if row["role"] == operand["role"])),
            patch.object(reconciliation, "expand_structured_candidate_ids", side_effect=lambda ids, mapping: list(ids)),
            patch.object(reconciliation, "structured_candidate_from_id", side_effect=lambda cid, mapping: dict(mapping[cid])),
            patch.object(reconciliation, "_candidate_satisfies_direct_acceptance_contract", return_value=True),
            patch.object(reconciliation, "pair_candidate_period_score", side_effect=score_owner),
            patch.object(reconciliation, "structured_cell_identity", side_effect=lambda cell: cell["value_id"]),
            patch.object(reconciliation, "effective_structured_cell_unit_hint", side_effect=lambda **kwargs: "억원"),
            patch.object(reconciliation, "build_operand_row_from_candidate_cell", side_effect=row_owner),
        ):
            rows, handled = agent._extract_structured_period_pair_rows(
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
            patch.object(agent, "_extract_structured_period_pair_rows", return_value=([], set())),
            patch.object(reconciliation, "expand_structured_candidate_ids", return_value=["candidate"]),
            patch.object(reconciliation, "structured_candidate_from_id", return_value=dict(candidate)),
            patch.object(reconciliation, "_score_operand_candidate", return_value=1.0),
            patch.object(reconciliation, "_select_structured_cell", return_value={"value_text": "10"}),
            patch.object(reconciliation, "_candidate_satisfies_direct_acceptance_contract", return_value=True),
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
            patch.object(agent, "_extract_structured_period_pair_rows", return_value=([], set())),
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


if __name__ == "__main__":
    unittest.main()
