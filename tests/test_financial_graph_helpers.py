import ast
from contextlib import ExitStack
from copy import deepcopy
import inspect
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import src.agent.financial_graph_helpers as financial_graph_helpers
import src.agent.financial_graph_planning as financial_graph_planning
import src.agent.financial_graph_reconciliation as financial_graph_reconciliation
import src.agent.financial_dependency_projection as financial_dependency_projection
import src.agent.financial_lookup_recovery as financial_lookup_recovery
import src.agent.financial_operand_resolution as financial_operand_resolution
import src.agent.financial_reconciliation_candidates as financial_reconciliation_candidates
import src.agent.financial_retrieval_hints as financial_retrieval_hints
import src.agent.financial_row_surfaces as financial_row_surfaces
import src.agent.financial_scope_policies as financial_scope_policies
import src.agent.financial_structured_cells as financial_structured_cells
import src.agent.financial_surface_contracts as financial_surface_contracts

from src.agent.financial_runtime_normalization import _display_operand_label
from src.agent.financial_retrieval_hints import (
    _active_preferred_sections,
    _preferred_calc_sections,
    _retrieval_hint_from_topic,
)


class FinancialGraphHelperTests(unittest.TestCase):
    def test_display_operand_label_removes_generic_company_year_prefix(self) -> None:
        self.assertEqual(
            _display_operand_label("\uc0bc\uc131\uc804\uc790 2023\ub144 \uc601\uc5c5\uc774\uc775"),
            "\uc601\uc5c5\uc774\uc775",
        )
        self.assertEqual(_display_operand_label("NAVER 2023\ub144 \ub9e4\ucd9c\uc561"), "\ub9e4\ucd9c\uc561")

    def test_display_operand_label_removes_leading_year(self) -> None:
        self.assertEqual(_display_operand_label("2023\ub144 \uc601\uc5c5\uc774\uc775"), "\uc601\uc5c5\uc774\uc775")

    def test_calc_sections_are_resolved_from_ontology(self) -> None:
        sections = _preferred_calc_sections(
            "2023\ub144 \uc124\ube44\ud22c\uc790 \ucd1d\uc561\uc744 \ucc3e\uc544\uc918.",
            "",
            "comparison",
        )

        self.assertIn("\uc6d0\uc7ac\ub8cc \ubc0f \uc0dd\uc0b0\uc124\ube44", sections)

    def test_retrieval_hint_is_resolved_from_ontology(self) -> None:
        hint = _retrieval_hint_from_topic(
            "2023\ub144 \uc124\ube44\ud22c\uc790 \ucd1d\uc561\uc744 \ucc3e\uc544\uc918.",
            "",
            "comparison",
        )

        self.assertIn("\uc124\ube44\ud22c\uc790", hint)

    def test_forward_looking_questions_use_caution_section_policy(self) -> None:
        query = "2026년 1분기 예상 영업이익과 판매량을 예측해 줘."

        hint = _retrieval_hint_from_topic(query, "", "qa")
        sections = _active_preferred_sections({}, query, "", "qa")

        self.assertIn("예측정보", hint)
        self.assertIn("예측정보에 대한 주의사항", sections)


    def test_current_source_scope_alignment_pins_precedence_copy_soft_fallback_and_exceptions(self) -> None:
        nested = {"preserve": True}
        companies = [" Existing ", "", "Existing"]
        years = ["2023", "bad", 2023]
        report_scope = {
            "company": " ScopeCo ",
            "year": "2024",
            "source_reports": ["report-a"],
            "nested": nested,
        }
        before_companies = list(companies)
        before_years = list(years)
        before_scope = deepcopy(report_scope)
        receipt_owner = Mock(return_value=["receipt-a"])
        with patch.object(
            financial_graph_helpers,
            "_report_scope_source_receipts",
            receipt_owner,
        ):
            aligned_companies, aligned_years = (
                financial_graph_helpers.align_scope_hints(
                    companies=companies,
                    years=years,
                    report_scope=report_scope,
                )
            )

        self.assertEqual(aligned_companies, ["ScopeCo"])
        self.assertEqual(aligned_years, [2024, 2023])
        receipt_scope = receipt_owner.call_args.args[0]
        self.assertIsNot(receipt_scope, report_scope)
        self.assertIs(receipt_scope["nested"], nested)
        self.assertEqual(companies, before_companies)
        self.assertEqual(years, before_years)
        self.assertEqual(report_scope, before_scope)
        self.assertIs(report_scope["nested"], nested)

    def test_current_source_segment_local_binding_pins_order_identity_and_exceptions(self) -> None:
        nested = {"preserve": True}
        candidate = {
            "metadata": {
                "table_row_labels_text": "",
                "table_context": "metric context",
                "table_summary_text": "",
                "column_headers_chain": [],
                "nested": nested,
            },
            "nested": nested,
        }
        operand = {"label": "metric", "segment": "North", "nested": nested}
        before_candidate = deepcopy(candidate)
        before_operand = deepcopy(operand)

        stopped_match = Mock(side_effect=AssertionError("empty segment must stop strict matching"))
        stopped_support = Mock(side_effect=AssertionError("empty segment must stop fallback"))
        with (
            patch.object(financial_row_surfaces, "_operand_segment_label", return_value=""),
            patch.object(financial_row_surfaces, "candidate_matches_segment_binding", stopped_match),
            patch.object(financial_row_surfaces, "candidate_supports_segment_metric_combo", stopped_support),
        ):
            self.assertTrue(
                financial_row_surfaces.candidate_has_segment_local_binding(candidate, operand)
            )
        stopped_match.assert_not_called()
        stopped_support.assert_not_called()

        direct_events = []

        def direct_segment(current_operand):
            direct_events.append("segment")
            self.assertIs(current_operand, operand)
            return "North"

        def direct_match(current_candidate, current_operand, *, strict):
            direct_events.append("match")
            self.assertIs(current_candidate, candidate)
            self.assertIs(current_operand, operand)
            self.assertTrue(strict)
            return True

        stopped_support = Mock(side_effect=AssertionError("strict match must stop fallback"))
        with (
            patch.object(financial_row_surfaces, "_operand_segment_label", side_effect=direct_segment),
            patch.object(
                financial_row_surfaces,
                "candidate_matches_segment_binding",
                side_effect=direct_match,
            ),
            patch.object(financial_row_surfaces, "candidate_supports_segment_metric_combo", stopped_support),
        ):
            self.assertTrue(
                financial_row_surfaces.candidate_has_segment_local_binding(candidate, operand)
            )
        self.assertEqual(direct_events, ["segment", "match"])
        stopped_support.assert_not_called()

        fallback_events = []

        def fallback_segment(current_operand):
            fallback_events.append("segment")
            self.assertIs(current_operand, operand)
            return "North"

        def fallback_match(current_candidate, current_operand, *, strict):
            fallback_events.append("match")
            self.assertIs(current_candidate, candidate)
            self.assertIs(current_operand, operand)
            self.assertTrue(strict)
            return len([event for event in fallback_events if event == "match"]) == 2

        def fallback_surface(text, current_operand):
            fallback_events.append(("surface", text))
            self.assertIs(current_operand, operand)
            return text == "metric context"

        with (
            patch.object(financial_row_surfaces, "_operand_segment_label", side_effect=fallback_segment),
            patch.object(
                financial_row_surfaces,
                "candidate_matches_segment_binding",
                side_effect=fallback_match,
            ),
            patch.object(financial_row_surfaces, "_operand_text_match", side_effect=fallback_surface),
        ):
            self.assertTrue(
                financial_row_surfaces.candidate_has_segment_local_binding(candidate, operand)
            )
        self.assertEqual(
            fallback_events,
            ["segment", "match", "segment", "match", ("surface", "metric context")],
        )

        stopped_support = Mock(side_effect=AssertionError("strict exception must stop fallback"))
        with (
            patch.object(financial_row_surfaces, "_operand_segment_label", return_value="North"),
            patch.object(
                financial_row_surfaces,
                "candidate_matches_segment_binding",
                side_effect=RuntimeError("segment match failed"),
            ),
            patch.object(financial_row_surfaces, "candidate_supports_segment_metric_combo", stopped_support),
        ):
            with self.assertRaisesRegex(RuntimeError, "segment match failed"):
                financial_row_surfaces.candidate_has_segment_local_binding(candidate, operand)
        stopped_support.assert_not_called()

        self.assertEqual(candidate, before_candidate)
        self.assertEqual(operand, before_operand)
        self.assertIs(candidate["nested"], nested)
        self.assertIs(candidate["metadata"]["nested"], nested)
        self.assertIs(operand["nested"], nested)

    def test_current_source_segment_metric_combo_pins_surface_order_copy_laziness_and_exceptions(self) -> None:
        nested = {"preserve": True}
        operand = {"label": "metric", "segment": "North", "nested": nested}

        stopped_match = Mock(side_effect=AssertionError("empty segment must stop strict matching"))
        with (
            patch.object(financial_row_surfaces, "_operand_segment_label", return_value=""),
            patch.object(financial_row_surfaces, "candidate_matches_segment_binding", stopped_match),
        ):
            self.assertFalse(
                financial_row_surfaces.candidate_supports_segment_metric_combo({}, operand)
            )
        stopped_match.assert_not_called()

        stopped_copy = Mock(side_effect=AssertionError("segment mismatch must stop metadata copy"))
        stopped_surface = Mock(side_effect=AssertionError("segment mismatch must stop surface matching"))
        with (
            patch.object(financial_row_surfaces, "_operand_segment_label", return_value="North"),
            patch.object(financial_row_surfaces, "candidate_matches_segment_binding", return_value=False),
            patch.object(financial_row_surfaces, "dict", stopped_copy, create=True),
            patch.object(financial_row_surfaces, "_operand_text_match", stopped_surface),
        ):
            self.assertFalse(
                financial_row_surfaces.candidate_supports_segment_metric_combo({}, operand)
            )
        stopped_copy.assert_not_called()
        stopped_surface.assert_not_called()

        string_events = []

        class TrackedSurface:
            def __init__(self, name, value):
                self.name = name
                self.value = value

            def __str__(self):
                string_events.append(self.name)
                return self.value

        row_surface = TrackedSurface("row", "")
        context_surface = TrackedSurface("context", "metric context")
        summary_surface = TrackedSurface("summary", "metric summary")
        header_surface = TrackedSurface("header", "metric header")
        blank_surface = TrackedSurface("blank", " ")
        metadata = {
            "table_row_labels_text": row_surface,
            "table_context": context_surface,
            "table_summary_text": summary_surface,
            "column_headers_chain": [header_surface, blank_surface],
            "nested": nested,
        }
        candidate = {"metadata": metadata, "nested": nested}
        real_dict = dict
        copies = []

        def copy_mapping(value):
            copied = real_dict(value)
            copies.append((value, copied))
            return copied

        matched_surfaces = []

        def match_surface(text, current_operand):
            matched_surfaces.append(text)
            self.assertIs(current_operand, operand)
            return text == "metric summary"

        with (
            patch.object(financial_row_surfaces, "_operand_segment_label", return_value="North"),
            patch.object(
                financial_row_surfaces,
                "candidate_matches_segment_binding",
                return_value=True,
            ) as binding,
            patch.object(financial_row_surfaces, "dict", side_effect=copy_mapping, create=True),
            patch.object(financial_row_surfaces, "_operand_text_match", side_effect=match_surface),
        ):
            self.assertTrue(
                financial_row_surfaces.candidate_supports_segment_metric_combo(candidate, operand)
            )
        binding.assert_called_once_with(candidate, operand, strict=True)
        self.assertEqual(string_events, ["row", "context", "summary", "header", "header", "blank"])
        self.assertEqual(matched_surfaces, ["metric context", "metric summary"])
        self.assertEqual(len(copies), 1)
        self.assertIs(copies[0][0], metadata)
        self.assertIsNot(copies[0][1], metadata)
        self.assertIs(copies[0][1]["nested"], nested)
        self.assertIs(candidate["metadata"], metadata)
        self.assertIs(candidate["nested"], nested)

        failing_match = Mock(side_effect=RuntimeError("surface match failed"))
        with (
            patch.object(financial_row_surfaces, "_operand_segment_label", return_value="North"),
            patch.object(financial_row_surfaces, "candidate_matches_segment_binding", return_value=True),
            patch.object(financial_row_surfaces, "_operand_text_match", failing_match),
        ):
            with self.assertRaisesRegex(RuntimeError, "surface match failed"):
                financial_row_surfaces.candidate_supports_segment_metric_combo(candidate, operand)
        self.assertEqual(failing_match.call_count, 1)
        self.assertIs(candidate["metadata"], metadata)
        self.assertIs(metadata["nested"], nested)
        self.assertIs(operand["nested"], nested)

    def test_current_source_segment_metric_bindings_pin_defs_calls_dag_imports_and_baseline(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        agent_root = repo_root / "src" / "agent"
        target_names = {
            "candidate_has_segment_local_binding",
            "candidate_supports_segment_metric_combo",
        }
        module_paths = {path.stem: path for path in agent_root.glob("*.py")}
        module_trees = {
            name: ast.parse(path.read_text(encoding="utf-8-sig"))
            for name, path in module_paths.items()
        }
        definitions = {name: [] for name in target_names}
        calls = {name: [] for name in target_names}
        dependency_loads = {
            "_operand_segment_label": [],
            "candidate_matches_segment_binding": [],
            "_operand_text_match": [],
        }

        class BindingVisitor(ast.NodeVisitor):
            def __init__(self, module_name):
                self.module_name = module_name
                self.function_stack = []
                self.try_depth = 0

            def visit_FunctionDef(self, node):
                if node.name in target_names:
                    definitions[node.name].append((self.module_name, node))
                self.function_stack.append(node.name)
                self.generic_visit(node)
                self.function_stack.pop()

            visit_AsyncFunctionDef = visit_FunctionDef

            def visit_Try(self, node):
                self.try_depth += 1
                self.generic_visit(node)
                self.try_depth -= 1

            visit_TryStar = visit_Try

            def visit_Call(self, node):
                called_name = node.func.id if isinstance(node.func, ast.Name) else ""
                if called_name in target_names:
                    calls[called_name].append(
                        (
                            self.module_name,
                            self.function_stack[-1] if self.function_stack else "",
                            type(node.func).__name__,
                            tuple(ast.unparse(arg) for arg in node.args),
                            tuple((kw.arg, ast.unparse(kw.value)) for kw in node.keywords),
                            self.try_depth,
                        )
                    )
                self.generic_visit(node)

            def visit_Name(self, node):
                if (
                    isinstance(node.ctx, ast.Load)
                    and node.id in dependency_loads
                    and self.function_stack
                    and self.function_stack[-1] in target_names
                ):
                    dependency_loads[node.id].append(
                        (self.module_name, self.function_stack[-1])
                    )
                self.generic_visit(node)

        for module_name, tree in module_trees.items():
            BindingVisitor(module_name).visit(tree)

        self.assertEqual(
            {
                name: [
                    (module_name, node.end_lineno - node.lineno + 1)
                    for module_name, node in entries
                ]
                for name, entries in definitions.items()
            },
            {
                "candidate_has_segment_local_binding": [("financial_row_surfaces", 7)],
                "candidate_supports_segment_metric_combo": [("financial_row_surfaces", 15)],
            },
        )
        self.assertEqual(
            {
                name: (
                    [arg.arg for arg in entries[0][1].args.args],
                    [arg.arg for arg in entries[0][1].args.kwonlyargs],
                )
                for name, entries in definitions.items()
            },
            {
                "candidate_has_segment_local_binding": (["candidate", "operand"], []),
                "candidate_supports_segment_metric_combo": (["candidate", "operand"], []),
            },
        )
        self.assertEqual(
            {name: len(entries) for name, entries in calls.items()},
            {
                "candidate_has_segment_local_binding": 1,
                "candidate_supports_segment_metric_combo": 2,
            },
        )
        self.assertEqual(
            {
                name: sorted(entry[:2] for entry in entries)
                for name, entries in calls.items()
            },
            {
                "candidate_has_segment_local_binding": [
                    ("financial_graph_helpers", "_deterministic_reconcile_task")
                ],
                "candidate_supports_segment_metric_combo": sorted([
                    ("financial_graph_helpers", "_candidate_direct_match_strength"),
                    ("financial_row_surfaces", "candidate_has_segment_local_binding"),
                ]),
            },
        )
        self.assertTrue(
            all(entry[2] == "Name" for entries in calls.values() for entry in entries)
        )
        self.assertTrue(all(entry[3] == ("candidate", "operand") for entries in calls.values() for entry in entries))
        self.assertTrue(all(entry[4] == () for entries in calls.values() for entry in entries))
        self.assertTrue(all(entry[5] == 0 for entries in calls.values() for entry in entries))
        self.assertEqual(
            {name: len(entries) for name, entries in dependency_loads.items()},
            {
                "_operand_segment_label": 2,
                "candidate_matches_segment_binding": 2,
                "_operand_text_match": 1,
            },
        )

        graph_defs = [
            node
            for node in module_trees["financial_graph_helpers"].body
            if isinstance(node, ast.FunctionDef)
        ]
        row_defs = [
            node
            for node in module_trees["financial_row_surfaces"].body
            if isinstance(node, ast.FunctionDef)
        ]
        self.assertEqual(
            (
                sum(not node.name.startswith("_") for node in graph_defs),
                sum(node.name.startswith("_") for node in graph_defs),
            ),
            (9, 97),
        )
        self.assertEqual(
            (
                sum(not node.name.startswith("_") for node in row_defs),
                sum(node.name.startswith("_") for node in row_defs),
            ),
            (5, 15),
        )

        retired_names = {"_" + name for name in target_names}
        self.assertFalse(retired_names & {node.name for node in graph_defs})

        row_surface_imports = {
            alias.name
            for node in module_trees["financial_row_surfaces"].body
            if isinstance(node, ast.ImportFrom)
            and node.module == "src.agent.financial_surface_contracts"
            for alias in node.names
        }
        graph_row_imports = {
            alias.name
            for node in module_trees["financial_graph_helpers"].body
            if isinstance(node, ast.ImportFrom)
            and node.module == "src.agent.financial_row_surfaces"
            for alias in node.names
        }
        self.assertTrue(
            {"_operand_segment_label", "candidate_matches_segment_binding"}
            <= row_surface_imports
        )
        self.assertTrue(target_names <= graph_row_imports)

        edges = {name: set() for name in module_trees}
        for module_name, tree in module_trees.items():
            for node in tree.body:
                if not isinstance(node, ast.ImportFrom) or not node.module:
                    continue
                prefix = "src.agent."
                if not node.module.startswith(prefix):
                    continue
                imported = node.module[len(prefix) :]
                if imported in edges:
                    edges[module_name].add(imported)

        def reaches(start, target):
            seen = set()
            pending = list(edges[start])
            while pending:
                current = pending.pop()
                if current == target:
                    return True
                if current in seen:
                    continue
                seen.add(current)
                pending.extend(edges[current])
            return False

        self.assertTrue(reaches("financial_graph_helpers", "financial_row_surfaces"))
        self.assertTrue(reaches("financial_row_surfaces", "financial_surface_contracts"))
        self.assertFalse(reaches("financial_row_surfaces", "financial_graph_helpers"))
        self.assertFalse(reaches("financial_surface_contracts", "financial_row_surfaces"))

        baseline = json.loads(
            (repo_root / "tests" / "fixtures" / "runtime_domain_terms_baseline.json").read_text(
                encoding="utf-8-sig"
            )
        )
        self.assertEqual(len(baseline["records"]), 218)
        selected_hits = []
        for record in baseline["records"]:
            if record.get("path") != "src/agent/financial_row_surfaces.py":
                continue
            for entries in definitions.values():
                for _, node in entries:
                    if any(
                        node.lineno <= line <= node.end_lineno
                        for line in record.get("first_lines") or []
                    ):
                        selected_hits.append(record)
        self.assertEqual(selected_hits, [])

    def test_current_source_segment_metric_callers_pin_args_filter_strength_and_stop(self) -> None:
        nested = {"preserve": True}
        operand = {
            "label": "metric",
            "segment": "North",
            "required": True,
            "nested": nested,
        }
        active_subtask = {
            "task_id": "task-1",
            "operation_family": "growth_rate",
            "required_operands": [operand],
            "constraints": {"nested": nested},
            "nested": nested,
        }
        blocked = {"candidate_id": "blocked", "metadata": {}, "nested": nested}
        kept = {"candidate_id": "kept", "metadata": {}, "nested": nested}
        caller_events = []
        caller_operands = []

        def candidate_match(candidate, current_operand):
            caller_events.append(("match", candidate["candidate_id"]))
            caller_operands.append(current_operand)
            return True

        def local_binding(candidate, current_operand):
            caller_events.append(("segment", candidate["candidate_id"]))
            caller_operands.append(current_operand)
            return candidate is kept

        def score(candidate, **kwargs):
            caller_events.append(("score", candidate["candidate_id"]))
            self.assertIs(candidate, kept)
            self.assertIs(kwargs["operand"], caller_operands[-1])
            return 1.0

        with (
            patch.object(financial_graph_helpers, "_candidate_matches_operand", side_effect=candidate_match),
            patch.object(financial_graph_helpers, "_operand_segment_label", return_value="North"),
            patch.object(
                financial_graph_helpers,
                "candidate_has_segment_local_binding",
                side_effect=local_binding,
            ) as local_owner,
            patch.object(financial_graph_helpers, "_score_operand_candidate", side_effect=score) as scorer,
            patch.object(
                financial_graph_helpers,
                "_candidate_is_direct_grounding_candidate",
                return_value=True,
            ),
        ):
            result = financial_graph_helpers._deterministic_reconcile_task(
                active_subtask=active_subtask,
                candidates=[blocked, kept],
                years=[2024],
                reconciliation_retry_count=0,
                report_scope={"nested": nested},
            )
        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["matched_operands"][0]["candidate_ids"], ["kept"])
        self.assertEqual(
            caller_events,
            [
                ("match", "blocked"),
                ("match", "kept"),
                ("segment", "blocked"),
                ("segment", "kept"),
                ("score", "kept"),
            ],
        )
        self.assertEqual(local_owner.call_count, 2)
        scorer.assert_called_once()
        projected_operand = local_owner.call_args_list[0].args[1]
        self.assertIsNot(projected_operand, operand)
        self.assertIs(projected_operand["nested"], nested)
        self.assertIs(local_owner.call_args_list[1].args[1], projected_operand)

        stopped_score = Mock(side_effect=AssertionError("segment exception must stop scoring"))
        with (
            patch.object(financial_graph_helpers, "_candidate_matches_operand", return_value=True),
            patch.object(financial_graph_helpers, "_operand_segment_label", return_value="North"),
            patch.object(
                financial_graph_helpers,
                "candidate_has_segment_local_binding",
                side_effect=RuntimeError("segment gate failed"),
            ),
            patch.object(financial_graph_helpers, "_score_operand_candidate", stopped_score),
        ):
            with self.assertRaisesRegex(RuntimeError, "segment gate failed"):
                financial_graph_helpers._deterministic_reconcile_task(
                    active_subtask=active_subtask,
                    candidates=[blocked],
                    years=[2024],
                    reconciliation_retry_count=0,
                )
        stopped_score.assert_not_called()

        strength_candidate = {"metadata": {}, "nested": nested}
        strength_operand = {"nested": nested}
        common_strength_patches = (
            patch.object(financial_graph_helpers, "_candidate_conflicts_with_operand_concept", return_value=False),
            patch.object(financial_graph_helpers, "_is_capex_total_operand", return_value=False),
            patch.object(
                financial_graph_helpers,
                "_operand_prefers_contextual_aggregate_match",
                return_value=False,
            ),
        )
        with ExitStack() as stack:
            for current_patch in common_strength_patches:
                stack.enter_context(current_patch)
            combo = stack.enter_context(
                patch.object(
                    financial_graph_helpers,
                    "candidate_supports_segment_metric_combo",
                    return_value=True,
                )
            )
            self.assertEqual(
                financial_graph_helpers._candidate_direct_match_strength(
                    strength_candidate,
                    strength_operand,
                ),
                2.25,
            )
        combo.assert_called_once_with(strength_candidate, strength_operand)

        with ExitStack() as stack:
            for current_patch in common_strength_patches:
                stack.enter_context(current_patch)
            stack.enter_context(
                patch.object(
                    financial_graph_helpers,
                    "candidate_supports_segment_metric_combo",
                    side_effect=RuntimeError("metric combo failed"),
                )
            )
            with self.assertRaisesRegex(RuntimeError, "metric combo failed"):
                financial_graph_helpers._candidate_direct_match_strength(
                    strength_candidate,
                    strength_operand,
                )
        self.assertIs(strength_candidate["nested"], nested)
        self.assertIs(strength_operand["nested"], nested)

    def test_current_source_candidate_required_surface_contract_pins_order_laziness_and_exceptions(self) -> None:
        nested = {"preserve": True}
        candidate = {
            "metadata": {
                "semantic_label": " semantic ",
                "row_label": " row ",
                "aggregate_label": " aggregate ",
                "semantic_aliases": [" alias-a ", "", " alias-b "],
                "row_headers": [" header-a ", " header-b "],
                "table_row_labels_text": " table rows ",
                "table_value_labels_text": " table values ",
                "row_text": " row text ",
                "nested": nested,
            },
            "text": " candidate text ",
            "nested": nested,
        }
        operand = {"label": "metric", "nested": nested}
        selected_cell = {"column_headers": [" column-a ", "", " column-b "], "nested": nested}
        before_candidate = deepcopy(candidate)
        before_operand = deepcopy(operand)
        before_cell = deepcopy(selected_cell)
        observed_surfaces = []

        def match_surface(surface, terms):
            observed_surfaces.append((surface, terms))
            return surface == "candidate text"

        with (
            patch.object(
                financial_surface_contracts,
                "_operand_surface_contract",
                return_value={"positive": [" required ", "", "secondary"]},
            ) as contract,
            patch.object(
                financial_surface_contracts,
                "_text_has_contract_term",
                side_effect=match_surface,
            ) as matcher,
        ):
            self.assertTrue(
                financial_surface_contracts.candidate_has_required_surface_contract(
                    candidate,
                    operand,
                    selected_cell=selected_cell,
                )
            )

        contract.assert_called_once_with(operand)
        self.assertEqual(
            [surface for surface, _ in observed_surfaces],
            [
                "semantic",
                "row",
                "aggregate",
                "alias-a alias-b",
                "header-a header-b",
                "column-a column-b",
                "table rows",
                "table values",
                "row text",
                "candidate text",
            ],
        )
        self.assertEqual([terms for _, terms in observed_surfaces], [["required", "secondary"]] * 10)
        self.assertEqual(matcher.call_count, 10)

        class CandidateBomb(dict):
            def get(self, key, default=None):
                raise AssertionError(f"candidate accessed: {key}")

        with (
            patch.object(financial_surface_contracts, "_operand_surface_contract", return_value={"positive": []}),
            patch.object(
                financial_surface_contracts,
                "_text_has_contract_term",
                side_effect=AssertionError("matcher should stay lazy"),
            ) as matcher,
        ):
            self.assertTrue(
                financial_surface_contracts.candidate_has_required_surface_contract(
                    CandidateBomb(),
                    operand,
                    selected_cell={"column_headers": ["unused"]},
                )
            )
        matcher.assert_not_called()

        stopped_matcher = Mock(side_effect=AssertionError("matcher should stay stopped"))
        with (
            patch.object(
                financial_surface_contracts,
                "_operand_surface_contract",
                side_effect=RuntimeError("contract failed"),
            ),
            patch.object(financial_surface_contracts, "_text_has_contract_term", stopped_matcher),
        ):
            with self.assertRaisesRegex(RuntimeError, "contract failed"):
                financial_surface_contracts.candidate_has_required_surface_contract(candidate, operand)
        stopped_matcher.assert_not_called()

        with (
            patch.object(
                financial_surface_contracts,
                "_operand_surface_contract",
                return_value={"positive": ["required"]},
            ),
            patch.object(
                financial_surface_contracts,
                "_text_has_contract_term",
                side_effect=RuntimeError("surface failed"),
            ) as matcher,
        ):
            with self.assertRaisesRegex(RuntimeError, "surface failed"):
                financial_surface_contracts.candidate_has_required_surface_contract(
                    candidate,
                    operand,
                    selected_cell=selected_cell,
                )
        self.assertEqual(matcher.call_count, 1)
        self.assertEqual(candidate, before_candidate)
        self.assertEqual(operand, before_operand)
        self.assertEqual(selected_cell, before_cell)
        self.assertIs(candidate["nested"], nested)
        self.assertIs(candidate["metadata"]["nested"], nested)
        self.assertIs(operand["nested"], nested)
        self.assertIs(selected_cell["nested"], nested)

    def test_current_source_candidate_numeric_and_descriptor_contracts_pin_precedence_and_stop(self) -> None:
        class StringBomb:
            def __str__(self):
                raise AssertionError("deeper text should stay lazy")

        nested = {"preserve": True}
        structured_candidate = {
            "metadata": {
                "structured_cells": [
                    {"value_text": "none", "nested": nested},
                    {"value_text": "value 7", "nested": nested},
                ],
                "row_text": StringBomb(),
                "nested": nested,
            },
            "text": StringBomb(),
            "nested": nested,
        }
        self.assertTrue(financial_surface_contracts.candidate_has_numeric_value_signal(structured_candidate))
        self.assertFalse(
            financial_surface_contracts.candidate_has_numeric_value_signal(
                {
                    "metadata": {
                        "structured_cells": [{"value_text": "none"}],
                        "row_text": "row | 99",
                    },
                    "text": "100",
                }
            )
        )
        self.assertTrue(
            financial_surface_contracts.candidate_has_numeric_value_signal(
                {"metadata": {"row_text": "label | no | 42"}, "text": StringBomb()}
            )
        )
        self.assertFalse(
            financial_surface_contracts.candidate_has_numeric_value_signal(
                {"metadata": {"row_text": "label | none"}, "text": "88"}
            )
        )
        self.assertTrue(
            financial_surface_contracts.candidate_has_numeric_value_signal(
                {"metadata": {"row_text": "plain row"}, "text": "answer 88"}
            )
        )

        class MetadataBomb(dict):
            def get(self, key, default=None):
                if key == "structured_cells":
                    raise AssertionError("structured cells should stay lazy")
                return super().get(key, default)

        with patch.object(
            financial_surface_contracts,
            "HELPER_RUNTIME_POLICY",
            {"non_value_row_labels": ["descriptor"]},
        ):
            self.assertTrue(
                financial_surface_contracts.candidate_is_descriptor_row(
                    {"metadata": MetadataBomb({"row_label": "descriptor"})}
                )
            )
            self.assertTrue(
                financial_surface_contracts.candidate_is_descriptor_row(
                    {"metadata": {"row_label": "metric", "structured_cells": [{"value_text": "none"}]}}
                )
            )
            self.assertTrue(
                financial_surface_contracts.candidate_is_descriptor_row(
                    {"metadata": {"row_label": "metric", "row_text": "descriptor | none"}}
                )
            )
            self.assertFalse(
                financial_surface_contracts.candidate_is_descriptor_row(
                    {"metadata": {"row_label": "metric", "row_text": "descriptor | 4"}}
                )
            )

        stopped_policy = Mock(side_effect=AssertionError("policy should stay stopped"))
        with (
            patch.object(financial_surface_contracts.re, "search", side_effect=RuntimeError("digit failed")),
            patch.object(financial_surface_contracts, "HELPER_RUNTIME_POLICY", stopped_policy),
        ):
            with self.assertRaisesRegex(RuntimeError, "digit failed"):
                financial_surface_contracts.candidate_has_numeric_value_signal(
                    {"metadata": {"structured_cells": [{"value_text": "3"}]}}
                )
        stopped_policy.assert_not_called()

        with patch.object(
            financial_surface_contracts,
            "_normalise_spaces",
            side_effect=RuntimeError("normalize failed"),
        ):
            with self.assertRaisesRegex(RuntimeError, "normalize failed"):
                financial_surface_contracts.candidate_is_descriptor_row(
                    {"metadata": {"row_label": "metric"}}
                )

        self.assertEqual(structured_candidate["metadata"]["structured_cells"][0]["nested"], nested)
        self.assertIs(structured_candidate["metadata"]["structured_cells"][0]["nested"], nested)
        self.assertIs(structured_candidate["nested"], nested)

    def test_current_source_candidate_segment_surfaces_and_match_pin_order_compaction_and_stop(self) -> None:
        nested = {"preserve": True}
        candidate = {
            "metadata": {
                "semantic_label": " semantic ",
                "row_label": " row ",
                "aggregate_label": " aggregate ",
                "semantic_aliases": [" alias-a ", "", " alias-b "],
                "row_headers": [" header-a ", " header-b "],
                "row_text": " row text ",
                "table_row_labels_text": " table rows ",
                "table_context": " context ",
                "local_heading": " heading ",
                "section_path": " section ",
                "table_summary_text": " summary ",
                "nested": nested,
            },
            "text": " candidate text ",
            "source_anchor": " anchor ",
            "nested": nested,
        }
        before = deepcopy(candidate)
        self.assertEqual(
            financial_surface_contracts._candidate_segment_surfaces(candidate, strict=True),
            ["semantic", "row", "aggregate", "alias-a alias-b", "header-a header-b", "row text"],
        )
        self.assertEqual(
            financial_surface_contracts._candidate_segment_surfaces(candidate),
            [
                "semantic",
                "row",
                "aggregate",
                "alias-a alias-b",
                "header-a header-b",
                "row text",
                "table rows",
                "context",
                "heading",
                "section",
                "summary",
                "candidate text",
                "anchor",
            ],
        )

        class CandidateBomb(dict):
            def get(self, key, default=None):
                raise AssertionError(f"candidate accessed: {key}")

        with (
            patch.object(financial_surface_contracts, "_operand_segment_label", return_value=""),
            patch.object(
                financial_surface_contracts,
                "_candidate_segment_surfaces",
                side_effect=AssertionError("surfaces should stay lazy"),
            ) as surfaces,
        ):
            self.assertTrue(
                financial_surface_contracts.candidate_matches_segment_binding(CandidateBomb(), {"label": "metric"})
            )
        surfaces.assert_not_called()

        operand = {"binding_policy": {"segment_label": "North Region"}, "nested": nested}
        with patch.object(
            financial_surface_contracts,
            "_candidate_segment_surfaces",
            return_value=["Other", "NorthRegion Results"],
        ) as surfaces:
            self.assertTrue(
                financial_surface_contracts.candidate_matches_segment_binding(
                    candidate,
                    operand,
                    strict=True,
                )
            )
        surfaces.assert_called_once_with(candidate, strict=True)

        with patch.object(
            financial_surface_contracts,
            "_candidate_segment_surfaces",
            return_value=["Other Region"],
        ):
            self.assertFalse(financial_surface_contracts.candidate_matches_segment_binding(candidate, operand))

        stopped_surfaces = Mock(side_effect=AssertionError("surfaces should stay stopped"))
        with (
            patch.object(
                financial_surface_contracts,
                "_operand_segment_label",
                side_effect=RuntimeError("segment failed"),
            ),
            patch.object(financial_surface_contracts, "_candidate_segment_surfaces", stopped_surfaces),
        ):
            with self.assertRaisesRegex(RuntimeError, "segment failed"):
                financial_surface_contracts.candidate_matches_segment_binding(candidate, operand)
        stopped_surfaces.assert_not_called()

        with (
            patch.object(financial_surface_contracts, "_operand_segment_label", return_value="North"),
            patch.object(
                financial_surface_contracts,
                "_candidate_segment_surfaces",
                side_effect=RuntimeError("surface projection failed"),
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "surface projection failed"):
                financial_surface_contracts.candidate_matches_segment_binding(candidate, operand)

        self.assertEqual(candidate, before)
        self.assertIs(candidate["metadata"]["nested"], nested)
        self.assertIs(candidate["nested"], nested)
        self.assertIs(operand["nested"], nested)

    def test_current_source_candidate_segment_bonus_pins_scores_laziness_and_exceptions(self) -> None:
        nested = {"preserve": True}
        candidate = {"metadata": {"nested": nested}, "nested": nested}
        operand = {"binding_policy": {"segment_label": "North"}, "nested": nested}
        constraints = {"segment_scope": "segment", "nested": nested}
        before_candidate = deepcopy(candidate)
        before_operand = deepcopy(operand)
        before_constraints = deepcopy(constraints)

        stopped_match = Mock(side_effect=AssertionError("match should stay lazy"))
        with (
            patch.object(financial_surface_contracts, "_operand_segment_label", return_value=""),
            patch.object(financial_surface_contracts, "candidate_matches_segment_binding", stopped_match),
        ):
            self.assertEqual(
                financial_surface_contracts.candidate_segment_binding_bonus(
                    candidate,
                    operand=operand,
                    constraints=constraints,
                    statement_type="notes",
                    local_heading="segment analysis",
                    section_path="",
                ),
                0.0,
            )
        stopped_match.assert_not_called()

        with (
            patch.object(financial_surface_contracts, "_operand_segment_label", return_value="North"),
            patch.object(financial_surface_contracts, "candidate_matches_segment_binding", return_value=True) as match,
            patch.object(
                financial_surface_contracts,
                "HELPER_RUNTIME_POLICY",
                {"segment_context_bonus_terms": ["segment", ""]},
            ),
        ):
            self.assertEqual(
                financial_surface_contracts.candidate_segment_binding_bonus(
                    candidate,
                    operand=operand,
                    constraints=constraints,
                    statement_type="notes",
                    local_heading="segment analysis",
                    section_path="appendix",
                ),
                7.25,
            )
        match.assert_called_once_with(candidate, operand)

        class PolicyBomb(dict):
            def get(self, key, default=None):
                raise AssertionError("policy should stay lazy on mismatch")

        with (
            patch.object(financial_surface_contracts, "_operand_segment_label", return_value="North"),
            patch.object(financial_surface_contracts, "candidate_matches_segment_binding", return_value=False),
            patch.object(financial_surface_contracts, "HELPER_RUNTIME_POLICY", PolicyBomb()),
        ):
            self.assertEqual(
                financial_surface_contracts.candidate_segment_binding_bonus(
                    candidate,
                    operand=operand,
                    constraints=constraints,
                    statement_type="income_statement",
                    local_heading="",
                    section_path="",
                ),
                -6.0,
            )
            self.assertEqual(
                financial_surface_contracts.candidate_segment_binding_bonus(
                    candidate,
                    operand=operand,
                    constraints={"segment_scope": "none"},
                    statement_type="notes",
                    local_heading="",
                    section_path="",
                ),
                -4.5,
            )

        stopped_policy = Mock(side_effect=AssertionError("policy should stay stopped"))
        with (
            patch.object(financial_surface_contracts, "_operand_segment_label", return_value="North"),
            patch.object(
                financial_surface_contracts,
                "candidate_matches_segment_binding",
                side_effect=RuntimeError("match failed"),
            ),
            patch.object(financial_surface_contracts, "HELPER_RUNTIME_POLICY", stopped_policy),
        ):
            with self.assertRaisesRegex(RuntimeError, "match failed"):
                financial_surface_contracts.candidate_segment_binding_bonus(
                    candidate,
                    operand=operand,
                    constraints=constraints,
                    statement_type="notes",
                    local_heading="segment",
                    section_path="",
                )
        stopped_policy.assert_not_called()

        with (
            patch.object(financial_surface_contracts, "_operand_segment_label", return_value="North"),
            patch.object(
                financial_surface_contracts,
                "_normalise_spaces",
                side_effect=RuntimeError("scope failed"),
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "scope failed"):
                financial_surface_contracts.candidate_segment_binding_bonus(
                    candidate,
                    operand=operand,
                    constraints=constraints,
                    statement_type="notes",
                    local_heading="segment",
                    section_path="",
                )

        self.assertEqual(candidate, before_candidate)
        self.assertEqual(operand, before_operand)
        self.assertEqual(constraints, before_constraints)
        self.assertIs(candidate["nested"], nested)
        self.assertIs(operand["nested"], nested)
        self.assertIs(constraints["nested"], nested)

    def test_current_source_candidate_surface_bindings_pin_defs_calls_dag_and_baseline(self) -> None:
        project_root = Path(__file__).resolve().parents[1]
        graph_path = project_root / "src" / "agent" / "financial_graph_helpers.py"
        reconciliation_path = project_root / "src" / "agent" / "financial_graph_reconciliation.py"
        row_path = project_root / "src" / "agent" / "financial_row_surfaces.py"
        owner_path = project_root / "src" / "agent" / "financial_surface_contracts.py"
        graph_tree = ast.parse(graph_path.read_text(encoding="utf-8-sig"))
        reconciliation_tree = ast.parse(reconciliation_path.read_text(encoding="utf-8-sig"))
        row_tree = ast.parse(row_path.read_text(encoding="utf-8-sig"))
        owner_tree = ast.parse(owner_path.read_text(encoding="utf-8-sig"))
        selected = {
            "candidate_has_required_surface_contract": 25,
            "candidate_has_numeric_value_signal": 15,
            "candidate_is_descriptor_row": 20,
            "_candidate_segment_surfaces": 23,
            "candidate_matches_segment_binding": 12,
            "candidate_segment_binding_bonus": 33,
        }
        owner_defs_by_name = {
            node.name: node
            for node in owner_tree.body
            if isinstance(node, ast.FunctionDef) and node.name in selected
        }
        self.assertEqual(set(owner_defs_by_name), set(selected))
        self.assertEqual(
            {name: node.end_lineno - node.lineno + 1 for name, node in owner_defs_by_name.items()},
            selected,
        )
        owner_defs = [node for node in owner_tree.body if isinstance(node, ast.FunctionDef)]
        self.assertEqual(
            (sum(not node.name.startswith("_") for node in owner_defs), sum(node.name.startswith("_") for node in owner_defs)),
            (9, 7),
        )
        self.assertEqual(
            {
                "candidate_has_required_surface_contract",
                "candidate_has_numeric_value_signal",
                "candidate_is_descriptor_row",
                "_candidate_segment_surfaces",
                "candidate_matches_segment_binding",
                "candidate_segment_binding_bonus",
            }
            & {node.name for node in owner_defs},
            set(selected),
        )
        retired = {
            "_" + name
            for name in {
                "candidate_has_required_surface_contract",
                "candidate_has_numeric_value_signal",
                "candidate_is_descriptor_row",
                "candidate_matches_segment_binding",
                "candidate_segment_binding_bonus",
            }
        }
        self.assertFalse(retired & {node.name for node in graph_tree.body if isinstance(node, ast.FunctionDef)})

        expected_counts = {
            "candidate_has_required_surface_contract": 3,
            "candidate_has_numeric_value_signal": 3,
            "candidate_is_descriptor_row": 4,
            "_candidate_segment_surfaces": 1,
            "candidate_matches_segment_binding": 5,
            "candidate_segment_binding_bonus": 1,
        }
        calls = {name: [] for name in selected}
        for module_name, tree in (
            ("graph", graph_tree),
            ("reconciliation", reconciliation_tree),
            ("row", row_tree),
            ("owner", owner_tree),
        ):
            parents = {}
            for parent in ast.walk(tree):
                for child in ast.iter_child_nodes(parent):
                    parents[child] = parent
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                target = node.func.id if isinstance(node.func, ast.Name) else ""
                if target not in calls:
                    continue
                ancestor = node
                try_depth = 0
                caller = "module"
                while ancestor in parents:
                    ancestor = parents[ancestor]
                    if isinstance(ancestor, ast.Try):
                        try_depth += 1
                    if isinstance(ancestor, ast.FunctionDef):
                        caller = ancestor.name
                        break
                calls[target].append((module_name, caller, node, try_depth))
        self.assertEqual({name: len(rows) for name, rows in calls.items()}, expected_counts)
        self.assertTrue(all(isinstance(row[2].func, ast.Name) for rows in calls.values() for row in rows))
        self.assertTrue(all(row[3] == 0 for rows in calls.values() for row in rows))
        self.assertEqual(
            [(module, caller) for module, caller, _, _ in calls["candidate_is_descriptor_row"]],
            [
                ("graph", "_candidate_is_direct_grounding_candidate"),
                ("graph", "_candidate_satisfies_ratio_component_acceptance_contract"),
                ("graph", "_score_operand_candidate"),
                ("reconciliation", "_should_llm_rerank_candidates"),
            ],
        )
        self.assertEqual(
            [keyword.arg for _, _, node, _ in calls["candidate_segment_binding_bonus"] for keyword in node.keywords],
            ["operand", "constraints", "statement_type", "local_heading", "section_path"],
        )
        external_calls = sum(1 for rows in calls.values() for module, _, _, _ in rows if module != "owner")
        local_calls = sum(1 for rows in calls.values() for module, _, _, _ in rows if module == "owner")
        self.assertEqual((external_calls, local_calls), (15, 2))

        def imports_for(path):
            tree = ast.parse(path.read_text(encoding="utf-8-sig"))
            imports = set()
            for node in tree.body:
                if isinstance(node, ast.ImportFrom) and node.module:
                    imports.add(node.module)
                elif isinstance(node, ast.Import):
                    imports.update(alias.name for alias in node.names)
            return imports

        owner_imports = imports_for(owner_path)
        self.assertNotIn("src.agent.financial_graph_helpers", owner_imports)
        self.assertNotIn("src.agent.financial_row_surfaces", owner_imports)
        self.assertIn("src.agent.financial_surface_contracts", imports_for(reconciliation_path))
        self.assertIn("src.agent.financial_surface_contracts", imports_for(project_root / "src" / "agent" / "financial_row_surfaces.py"))

        baseline = json.loads(
            (project_root / "tests" / "fixtures" / "runtime_domain_terms_baseline.json").read_text(
                encoding="utf-8-sig"
            )
        )
        self.assertEqual(len(baseline["records"]), 218)
        selected_hits = []
        for record in baseline["records"]:
            if record.get("path") != "src/agent/financial_surface_contracts.py":
                continue
            for name, node in owner_defs_by_name.items():
                if any(node.lineno <= line <= node.end_lineno for line in record.get("first_lines") or []):
                    selected_hits.append((name, record))
        self.assertEqual(selected_hits, [])

    def test_current_source_candidate_surface_callers_pin_args_adoption_order_and_stop(self) -> None:
        nested = {"preserve": True}
        candidate = {
            "candidate_kind": "structured_value",
            "metadata": {"statement_type": "unknown", "period_focus": "unknown", "nested": nested},
            "nested": nested,
        }
        operand = {"binding_policy": {}, "nested": nested}
        constraints = {"nested": nested}
        query_years = [2024]
        report_scope = {"nested": nested}

        patches = {
            "candidate_is_descriptor_row": False,
            "candidate_has_numeric_value_signal": True,
            "_candidate_direct_match_strength": 1.0,
            "_candidate_value_role": "aggregate",
            "_candidate_aggregation_stage": "final",
            "binding_policy_allows_candidate_shape": True,
            "lookup_prefers_canonical_statement_rows": False,
            "candidate_consolidation_scope": "unknown",
            "operand_period_focus": "unknown",
            "_is_delta_like_row_label": False,
            "candidate_matches_segment_binding": True,
            "candidate_matches_target_report_scope": True,
            "candidate_matches_operand_target_year": False,
            "_operand_surface_contract": {"positive": ["metric"]},
            "candidate_has_required_surface_contract": True,
        }
        with ExitStack() as stack:
            mocks = {
                name: stack.enter_context(patch.object(financial_graph_helpers, name, return_value=value))
                for name, value in patches.items()
            }
            self.assertTrue(
                financial_graph_helpers._candidate_is_direct_grounding_candidate(
                    candidate,
                    operand=operand,
                    constraints=constraints,
                    query_years=query_years,
                    operation_family="",
                    report_scope=report_scope,
                )
            )
            self.assertTrue(
                financial_graph_helpers._candidate_satisfies_ratio_component_acceptance_contract(
                    candidate,
                    operand=operand,
                    constraints=constraints,
                    query_years=query_years,
                    report_scope=report_scope,
                )
            )
        self.assertEqual(mocks["candidate_is_descriptor_row"].call_args_list, [unittest.mock.call(candidate)] * 2)
        self.assertEqual(mocks["candidate_has_numeric_value_signal"].call_args_list, [unittest.mock.call(candidate)] * 2)
        self.assertEqual(
            mocks["candidate_matches_segment_binding"].call_args_list,
            [unittest.mock.call(candidate, operand, strict=True)] * 2,
        )
        mocks["candidate_has_required_surface_contract"].assert_called_once_with(
            candidate,
            operand,
            selected_cell=None,
        )

        stopped_scope = Mock(side_effect=AssertionError("scope should stay stopped"))
        with (
            patch.object(financial_graph_helpers, "candidate_is_descriptor_row", return_value=False),
            patch.object(financial_graph_helpers, "candidate_has_numeric_value_signal", return_value=True),
            patch.object(financial_graph_helpers, "_candidate_direct_match_strength", return_value=1.0),
            patch.object(financial_graph_helpers, "_candidate_value_role", return_value="aggregate"),
            patch.object(financial_graph_helpers, "_candidate_aggregation_stage", return_value="final"),
            patch.object(financial_graph_helpers, "binding_policy_allows_candidate_shape", return_value=True),
            patch.object(financial_graph_helpers, "lookup_prefers_canonical_statement_rows", return_value=False),
            patch.object(financial_graph_helpers, "candidate_consolidation_scope", return_value="unknown"),
            patch.object(financial_graph_helpers, "operand_period_focus", return_value="unknown"),
            patch.object(financial_graph_helpers, "_is_delta_like_row_label", return_value=False),
            patch.object(
                financial_graph_helpers,
                "candidate_matches_segment_binding",
                side_effect=RuntimeError("segment gate failed"),
            ),
            patch.object(financial_graph_helpers, "candidate_matches_target_report_scope", stopped_scope),
        ):
            with self.assertRaisesRegex(RuntimeError, "segment gate failed"):
                financial_graph_helpers._candidate_is_direct_grounding_candidate(
                    candidate,
                    operand=operand,
                    constraints=constraints,
                    query_years=query_years,
                    report_scope=report_scope,
                )
        stopped_scope.assert_not_called()

        with (
            patch.object(financial_row_surfaces, "_operand_segment_label", return_value="North"),
            patch.object(financial_row_surfaces, "candidate_matches_segment_binding", return_value=False) as match,
            patch.object(financial_row_surfaces, "candidate_supports_segment_metric_combo", return_value=True) as support,
        ):
            self.assertTrue(financial_row_surfaces.candidate_has_segment_local_binding(candidate, operand))
        match.assert_called_once_with(candidate, operand, strict=True)
        support.assert_called_once_with(candidate, operand)

        score_kwargs = {
            "operand": operand,
            "preferred_statement_types": [],
            "constraints": constraints,
            "query_years": query_years,
            "report_scope": report_scope,
        }
        with patch.object(financial_graph_helpers, "candidate_segment_binding_bonus", return_value=0.0):
            base_score = financial_graph_helpers._score_operand_candidate(candidate, **score_kwargs)
        with patch.object(financial_graph_helpers, "candidate_segment_binding_bonus", return_value=7.0) as bonus:
            boosted_score = financial_graph_helpers._score_operand_candidate(candidate, **score_kwargs)
        self.assertEqual(boosted_score - base_score, 7.0)
        bonus.assert_called_once()
        self.assertEqual(
            set(bonus.call_args.kwargs),
            {"operand", "constraints", "statement_type", "local_heading", "section_path"},
        )
        self.assertIs(bonus.call_args.kwargs["operand"], operand)
        self.assertIs(bonus.call_args.kwargs["constraints"], constraints)

        top_candidate = {"candidate_id": "top", "nested": nested}
        scored = [
            {"score": 10.0, "candidate": top_candidate},
            {"score": 0.0, "candidate": {"candidate_id": "second"}},
        ]
        with patch.object(
            financial_graph_reconciliation,
            "candidate_is_descriptor_row",
            return_value=True,
        ) as descriptor:
            self.assertTrue(
                financial_graph_reconciliation.FinancialAgentReconciliationMixin._should_llm_rerank_candidates(
                    SimpleNamespace(),
                    scored,
                )
            )
        descriptor_arg = descriptor.call_args.args[0]
        self.assertIsNot(descriptor_arg, top_candidate)
        self.assertIs(descriptor_arg["nested"], nested)

        with patch.object(
            financial_graph_reconciliation,
            "candidate_is_descriptor_row",
            side_effect=RuntimeError("descriptor failed"),
        ):
            with self.assertRaisesRegex(RuntimeError, "descriptor failed"):
                financial_graph_reconciliation.FinancialAgentReconciliationMixin._should_llm_rerank_candidates(
                    SimpleNamespace(),
                    scored,
                )
        self.assertEqual(candidate["metadata"]["nested"], nested)
        self.assertIs(candidate["metadata"]["nested"], nested)
        self.assertIs(candidate["nested"], nested)
        self.assertIs(operand["nested"], nested)
        self.assertIs(constraints["nested"], nested)
        self.assertIs(report_scope["nested"], nested)

        receipt_owner = Mock(side_effect=AssertionError("receipts accessed"))
        with patch.object(
            financial_graph_helpers,
            "_report_scope_source_receipts",
            receipt_owner,
        ):
            rcept_companies, rcept_years = (
                financial_graph_helpers.align_scope_hints(
                    companies=["Existing"],
                    years=[],
                    report_scope={"company": "ReceiptCo", "year": 2025, "rcept_no": " 1 "},
                )
            )
        self.assertEqual((rcept_companies, rcept_years), (["ReceiptCo"], [2025]))
        receipt_owner.assert_not_called()

        with patch.object(
            financial_graph_helpers,
            "_report_scope_source_receipts",
            return_value=["receipt-a", "receipt-b"],
        ):
            multi_companies, multi_years = (
                financial_graph_helpers.align_scope_hints(
                    companies=["Existing", "ScopeCo"],
                    years=[2024, "2022", "invalid"],
                    report_scope={"company": "ScopeCo", "year": "bad"},
                )
            )
            prepended_companies, prepended_years = (
                financial_graph_helpers.align_scope_hints(
                    companies=["Existing"],
                    years=[],
                    report_scope={"company": "ScopeCo", "year": "2024"},
                )
            )
        self.assertEqual((multi_companies, multi_years), (["Existing", "ScopeCo"], [2024, 2022]))
        self.assertEqual((prepended_companies, prepended_years), (["ScopeCo", "Existing"], [2024]))

        with patch.object(
            financial_graph_helpers,
            "_report_scope_source_receipts",
            side_effect=RuntimeError("receipt scan failed"),
        ):
            fallback_companies, fallback_years = (
                financial_graph_helpers.align_scope_hints(
                    companies=[],
                    years=[],
                    report_scope={"company": "FallbackCo", "year": 2021},
                )
            )
        self.assertEqual((fallback_companies, fallback_years), (["FallbackCo"], [2021]))

        class ScopeGetBomb(dict):
            def get(self, key, default=None):
                if key == "company":
                    raise RuntimeError("scope company failed")
                return super().get(key, default)

        receipt_owner = Mock(side_effect=AssertionError("receipts accessed"))
        with patch.object(
            financial_graph_helpers,
            "_report_scope_source_receipts",
            receipt_owner,
        ):
            with self.assertRaisesRegex(RuntimeError, "scope company failed"):
                financial_graph_helpers.align_scope_hints(
                    companies=[],
                    years=[],
                    report_scope=ScopeGetBomb(),
                )
        receipt_owner.assert_not_called()

    def test_current_source_aggregate_like_row_stage_pins_normalization_copies_order_laziness_and_exceptions(self) -> None:
        events = []

        class LabelProbe:
            def __str__(self):
                events.append("label")
                return " A   B "

        class TokenProbe:
            def __init__(self, name, value):
                self.name = name
                self.value = value

            def __str__(self):
                events.append(self.name)
                return self.value

        class TrackingTokens:
            def __init__(self, name, values):
                self.name = name
                self.values = values

            def __iter__(self):
                events.append(("iterate", self.name))
                return iter(self.values)

        first_tokens = TrackingTokens(
            "first",
            [TokenProbe("token-a", "A B"), TokenProbe("token-b", "C")],
        )
        stopped_tokens = TrackingTokens(
            "stopped",
            [TokenProbe("token-stopped", "AB")],
        )
        nested = {"preserve": True}
        policy = {
            "aggregate_stage_tokens": {
                "first": first_tokens,
                "stopped": stopped_tokens,
            },
            "nested": nested,
        }
        before_policy = dict(policy)
        before_stage_tokens = dict(policy["aggregate_stage_tokens"])
        with patch.object(
            financial_row_surfaces,
            "STRUCTURED_CELL_AFFINITY_POLICY",
            policy,
        ):
            self.assertEqual(
                financial_row_surfaces.aggregate_like_row_stage(LabelProbe()),
                "first",
            )

        self.assertEqual(
            events,
            ["label", ("iterate", "first"), "token-a", "token-b"],
        )
        self.assertEqual(policy, before_policy)
        self.assertEqual(policy["aggregate_stage_tokens"], before_stage_tokens)
        self.assertIs(policy["nested"], nested)
        self.assertIs(policy["aggregate_stage_tokens"]["first"], first_tokens)

        class PolicyBomb:
            def keys(self):
                raise AssertionError("blank label must stop policy copy")

        with patch.object(
            financial_row_surfaces,
            "STRUCTURED_CELL_AFFINITY_POLICY",
            PolicyBomb(),
        ):
            self.assertEqual(
                financial_row_surfaces.aggregate_like_row_stage("   "),
                "none",
            )

        with patch.object(
            financial_row_surfaces,
            "STRUCTURED_CELL_AFFINITY_POLICY",
            {"aggregate_stage_tokens": {"first": ("AB",)}},
        ):
            self.assertEqual(
                financial_row_surfaces.aggregate_like_row_stage("XAB"),
                "none",
            )
            self.assertEqual(
                financial_row_surfaces.aggregate_like_row_stage("ab"),
                "none",
            )
            self.assertEqual(
                financial_row_surfaces.aggregate_like_row_stage("A B"),
                "first",
            )

        class CopyBomb:
            def keys(self):
                raise RuntimeError("policy copy failed")

        with patch.object(
            financial_row_surfaces,
            "STRUCTURED_CELL_AFFINITY_POLICY",
            CopyBomb(),
        ):
            with self.assertRaisesRegex(RuntimeError, "policy copy failed"):
                financial_row_surfaces.aggregate_like_row_stage("AB")

        with patch.object(
            financial_row_surfaces,
            "STRUCTURED_CELL_AFFINITY_POLICY",
            {"aggregate_stage_tokens": {"broken": None}},
        ):
            with self.assertRaises(TypeError):
                financial_row_surfaces.aggregate_like_row_stage("AB")

    def test_current_source_aggregate_like_row_role_pins_projection_and_exception_stop(self) -> None:
        label = object()
        stage = Mock(side_effect=["none", "final", "custom"])
        with patch.object(
            financial_row_surfaces,
            "aggregate_like_row_stage",
            stage,
        ):
            self.assertEqual(
                financial_row_surfaces.aggregate_like_row_role(label),
                "detail",
            )
            self.assertEqual(
                financial_row_surfaces.aggregate_like_row_role(label),
                "aggregate",
            )
            self.assertEqual(
                financial_row_surfaces.aggregate_like_row_role(label),
                "aggregate",
            )
        self.assertEqual(stage.call_count, 3)
        self.assertTrue(all(call.args == (label,) for call in stage.call_args_list))

        with patch.object(
            financial_row_surfaces,
            "aggregate_like_row_stage",
            side_effect=RuntimeError("stage failed"),
        ) as stopped_stage:
            with self.assertRaisesRegex(RuntimeError, "stage failed"):
                financial_row_surfaces.aggregate_like_row_role(label)
        stopped_stage.assert_called_once_with(label)

    def test_current_source_aggregate_row_role_bindings_pin_defs_calls_dag_imports_and_baseline(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        agent_root = repo_root / "src" / "agent"
        target_names = {
            "aggregate_like_row_stage",
            "aggregate_like_row_role",
        }
        module_paths = {path.stem: path for path in agent_root.glob("*.py")}
        module_trees = {
            name: ast.parse(path.read_text(encoding="utf-8-sig"))
            for name, path in module_paths.items()
        }
        definitions = {name: [] for name in target_names}
        calls = {name: [] for name in target_names}
        dependency_loads = {
            "STRUCTURED_CELL_AFFINITY_POLICY": [],
            "_normalise_spaces": [],
            "re": [],
        }

        class BindingVisitor(ast.NodeVisitor):
            def __init__(self, module_name):
                self.module_name = module_name
                self.function_stack = []
                self.try_depth = 0

            def visit_FunctionDef(self, node):
                if node.name in target_names:
                    definitions[node.name].append((self.module_name, node))
                self.function_stack.append(node.name)
                self.generic_visit(node)
                self.function_stack.pop()

            visit_AsyncFunctionDef = visit_FunctionDef

            def visit_Try(self, node):
                self.try_depth += 1
                self.generic_visit(node)
                self.try_depth -= 1

            visit_TryStar = visit_Try

            def visit_Call(self, node):
                called_name = node.func.id if isinstance(node.func, ast.Name) else ""
                if called_name in target_names:
                    calls[called_name].append(
                        (
                            self.module_name,
                            self.function_stack[-1] if self.function_stack else "",
                            type(node.func).__name__,
                            tuple(ast.unparse(arg) for arg in node.args),
                            tuple((kw.arg, ast.unparse(kw.value)) for kw in node.keywords),
                            self.try_depth,
                        )
                    )
                self.generic_visit(node)

            def visit_Name(self, node):
                if (
                    isinstance(node.ctx, ast.Load)
                    and node.id in dependency_loads
                    and self.function_stack
                    and self.function_stack[-1] in target_names
                ):
                    dependency_loads[node.id].append(
                        (self.module_name, self.function_stack[-1])
                    )
                self.generic_visit(node)

        for module_name, tree in module_trees.items():
            BindingVisitor(module_name).visit(tree)

        stage_name = "aggregate_like_row_stage"
        role_name = "aggregate_like_row_role"
        expected_owner = "financial_row_surfaces"
        self.assertEqual(
            {
                stage_name: [
                    (module_name, node.end_lineno - node.lineno + 1)
                    for module_name, node in definitions[stage_name]
                ],
                role_name: [
                    (module_name, node.end_lineno - node.lineno + 1)
                    for module_name, node in definitions[role_name]
                ],
            },
            {
                stage_name: [(expected_owner, 10)],
                role_name: [(expected_owner, 2)],
            },
        )
        self.assertEqual(
            {
                name: (
                    [arg.arg for arg in definitions[name][0][1].args.args],
                    [arg.arg for arg in definitions[name][0][1].args.kwonlyargs],
                )
                for name in (stage_name, role_name)
            },
            {
                stage_name: (["label"], []),
                role_name: (["label"], []),
            },
        )
        self.assertEqual(
            {stage_name: len(calls[stage_name]), role_name: len(calls[role_name])},
            {stage_name: 4, role_name: 2},
        )
        self.assertEqual(
            sorted(entry[:2] for entry in calls[stage_name]),
            sorted(
                [
                    ("financial_graph_helpers", "_build_table_row_reconciliation_candidates"),
                    ("financial_graph_helpers", "_candidate_aggregation_stage"),
                    ("financial_graph_helpers", "_candidate_matches_operand"),
                    (expected_owner, role_name),
                ]
            ),
        )
        self.assertEqual(
            sorted(entry[:2] for entry in calls[role_name]),
            sorted(
                [
                    ("financial_graph_helpers", "_build_table_row_reconciliation_candidates"),
                    ("financial_graph_helpers", "_candidate_value_role"),
                ]
            ),
        )
        self.assertTrue(
            all(entry[2] == "Name" for name in (stage_name, role_name) for entry in calls[name])
        )
        self.assertTrue(
            all(entry[4] == () for name in (stage_name, role_name) for entry in calls[name])
        )
        self.assertTrue(
            all(entry[5] == 0 for name in (stage_name, role_name) for entry in calls[name])
        )
        self.assertEqual(
            sorted((name, entry[3]) for name in (stage_name, role_name) for entry in calls[name]),
            sorted(
                [
                    (stage_name, ("label",)),
                    (stage_name, ("row_label",)),
                    (
                        stage_name,
                        ("str(metadata.get('row_label') or metadata.get('semantic_label') or '')",),
                    ),
                    (stage_name, ("aggregate_surface",)),
                    (role_name, ("row_label",)),
                    (
                        role_name,
                        ("str(metadata.get('row_label') or metadata.get('semantic_label') or '')",),
                    ),
                ]
            ),
        )
        self.assertEqual(
            {name: len(entries) for name, entries in dependency_loads.items()},
            {
                "STRUCTURED_CELL_AFFINITY_POLICY": 1,
                "_normalise_spaces": 2,
                "re": 2,
            },
        )

        graph_defs = [
            node
            for node in module_trees["financial_graph_helpers"].body
            if isinstance(node, ast.FunctionDef)
        ]
        row_defs = [
            node
            for node in module_trees["financial_row_surfaces"].body
            if isinstance(node, ast.FunctionDef)
        ]
        self.assertEqual(
            (
                sum(not node.name.startswith("_") for node in graph_defs),
                sum(node.name.startswith("_") for node in graph_defs),
            ),
            (9, 97),
        )
        self.assertEqual(
            (
                sum(not node.name.startswith("_") for node in row_defs),
                sum(node.name.startswith("_") for node in row_defs),
            ),
            (5, 15),
        )

        graph_row_imports = {
            alias.name
            for node in module_trees["financial_graph_helpers"].body
            if isinstance(node, ast.ImportFrom)
            and node.module == "src.agent.financial_row_surfaces"
            for alias in node.names
        }
        self.assertTrue(target_names <= graph_row_imports)

        row_policy_imports = {
            alias.name
            for node in module_trees["financial_row_surfaces"].body
            if isinstance(node, ast.ImportFrom)
            and node.module == "src.config.retrieval_policy"
            for alias in node.names
        }
        self.assertTrue(
            {"HELPER_RUNTIME_POLICY", "STRUCTURED_CELL_AFFINITY_POLICY"}
            <= row_policy_imports
        )

        edges = {name: set() for name in module_trees}
        for module_name, tree in module_trees.items():
            for node in tree.body:
                if not isinstance(node, ast.ImportFrom) or not node.module:
                    continue
                prefix = "src.agent."
                if not node.module.startswith(prefix):
                    continue
                imported = node.module[len(prefix) :]
                if imported in edges:
                    edges[module_name].add(imported)

        def reaches(start, target):
            seen = set()
            pending = list(edges[start])
            while pending:
                current = pending.pop()
                if current == target:
                    return True
                if current in seen:
                    continue
                seen.add(current)
                pending.extend(edges[current])
            return False

        self.assertTrue(reaches("financial_graph_helpers", "financial_row_surfaces"))
        self.assertTrue(reaches("financial_structured_cells", "financial_row_surfaces"))
        self.assertFalse(reaches("financial_row_surfaces", "financial_graph_helpers"))
        self.assertFalse(reaches("financial_row_surfaces", "financial_structured_cells"))

        baseline = json.loads(
            (repo_root / "tests" / "fixtures" / "runtime_domain_terms_baseline.json").read_text(
                encoding="utf-8-sig"
            )
        )
        self.assertEqual(len(baseline["records"]), 218)
        selected_hits = []
        for record in baseline["records"]:
            if record.get("path") != f"src/agent/{expected_owner}.py":
                continue
            for name in (stage_name, role_name):
                node = definitions[name][0][1]
                if any(
                    node.lineno <= line <= node.end_lineno
                    for line in record.get("first_lines") or []
                ):
                    selected_hits.append((name, record))
        self.assertEqual(selected_hits, [])

    def test_current_source_aggregate_row_role_callers_pin_args_adoption_order_and_stop(self) -> None:
        nested = {"preserve": True}
        metadata = {
            "value_role": " explicit-role ",
            "aggregation_stage": " explicit-stage ",
            "aggregate_role": "existing-role",
            "aggregate_label": "existing-label",
            "nested": nested,
        }
        before_metadata = dict(metadata)
        events = []

        def extract_label(row_text):
            events.append(("extract", row_text))
            return "Exact Label"

        def infer_stage(label):
            events.append(("stage", label))
            return "final"

        def infer_role(label):
            events.append(("role", label))
            return "aggregate"

        with (
            patch.object(financial_graph_helpers, "_extract_table_row_label", side_effect=extract_label),
            patch.object(financial_graph_helpers, "aggregate_like_row_stage", side_effect=infer_stage),
            patch.object(financial_graph_helpers, "aggregate_like_row_role", side_effect=infer_role),
            patch.object(financial_graph_helpers, "_parse_unstructured_table_row_cells", return_value=[]),
        ):
            candidates = financial_graph_helpers._build_table_row_reconciliation_candidates(
                candidate_id_prefix="candidate",
                anchor="anchor",
                table_text="raw | 1",
                metadata=metadata,
            )

        self.assertEqual(
            events,
            [
                ("extract", "raw | 1"),
                ("stage", "Exact Label"),
                ("role", "Exact Label"),
            ],
        )
        self.assertEqual(len(candidates), 1)
        candidate_metadata = candidates[0]["metadata"]
        self.assertEqual(candidate_metadata["row_label"], "Exact Label")
        self.assertEqual(candidate_metadata["aggregate_label"], "Exact Label")
        self.assertEqual(candidate_metadata["aggregate_role"], "final_total")
        self.assertEqual(candidate_metadata["value_role"], "explicit-role")
        self.assertEqual(candidate_metadata["aggregation_stage"], "explicit-stage")
        self.assertEqual(metadata, before_metadata)
        self.assertIs(metadata["nested"], nested)
        self.assertIs(candidate_metadata["nested"], nested)

        stopped_stage = Mock(side_effect=AssertionError("explicit value role must stop row inference"))
        with patch.object(financial_graph_helpers, "aggregate_like_row_role", stopped_stage):
            self.assertEqual(
                financial_graph_helpers._candidate_value_role(
                    {"metadata": {"value_role": " custom ", "row_label": "ignored"}}
                ),
                "custom",
            )
        stopped_stage.assert_not_called()

        stopped_stage = Mock(side_effect=AssertionError("aggregate role must stop row inference"))
        with patch.object(financial_graph_helpers, "aggregate_like_row_role", stopped_stage):
            self.assertEqual(
                financial_graph_helpers._candidate_value_role(
                    {"metadata": {"aggregate_role": "subtotal", "row_label": "ignored"}}
                ),
                "aggregate",
            )
        stopped_stage.assert_not_called()

        role_fallback = Mock(return_value="aggregate")
        with patch.object(financial_graph_helpers, "aggregate_like_row_role", role_fallback):
            self.assertEqual(
                financial_graph_helpers._candidate_value_role(
                    {"metadata": {"semantic_label": "Semantic Label"}}
                ),
                "aggregate",
            )
        role_fallback.assert_called_once_with("Semantic Label")

        stopped_stage = Mock(side_effect=AssertionError("explicit stage must stop row inference"))
        with patch.object(financial_graph_helpers, "aggregate_like_row_stage", stopped_stage):
            self.assertEqual(
                financial_graph_helpers._candidate_aggregation_stage(
                    {"metadata": {"aggregation_stage": " custom ", "row_label": "ignored"}}
                ),
                "custom",
            )
        stopped_stage.assert_not_called()

        stopped_stage = Mock(side_effect=AssertionError("aggregate role must stop row inference"))
        with patch.object(financial_graph_helpers, "aggregate_like_row_stage", stopped_stage):
            self.assertEqual(
                financial_graph_helpers._candidate_aggregation_stage(
                    {"metadata": {"aggregate_role": "direct_total", "row_label": "ignored"}}
                ),
                "direct",
            )
        stopped_stage.assert_not_called()

        stage_fallback = Mock(return_value="subtotal")
        with patch.object(financial_graph_helpers, "aggregate_like_row_stage", stage_fallback):
            self.assertEqual(
                financial_graph_helpers._candidate_aggregation_stage(
                    {"metadata": {"semantic_label": "Semantic Label"}}
                ),
                "subtotal",
            )
        stage_fallback.assert_called_once_with("Semantic Label")

        contextual_candidate = {
            "candidate_kind": "structured_value",
            "metadata": {
                "aggregate_label": "Aggregate",
                "row_label": "Row",
                "semantic_label": "Semantic",
            },
        }
        operand = {"binding_policy": {"prefer_value_roles": ["aggregate"]}}
        common_patches = (
            patch.object(financial_graph_helpers, "_candidate_conflicts_with_operand_concept", return_value=False),
            patch.object(financial_graph_helpers, "_operand_text_match", return_value=False),
            patch.object(financial_graph_helpers, "_is_capex_total_operand", return_value=False),
            patch.object(financial_graph_helpers, "_operand_prefers_contextual_aggregate_match", return_value=True),
            patch.object(financial_graph_helpers, "candidate_local_aggregate_context", return_value="context"),
            patch.object(financial_graph_helpers, "_text_has_positive_surface", return_value=True),
        )

        stopped_stage = Mock(side_effect=AssertionError("value role hit must short-circuit stage inference"))
        with ExitStack() as stack:
            for current_patch in common_patches:
                stack.enter_context(current_patch)
            stack.enter_context(patch.object(financial_graph_helpers, "_candidate_value_role", return_value="aggregate"))
            stack.enter_context(patch.object(financial_graph_helpers, "_candidate_aggregation_stage", return_value="none"))
            stack.enter_context(patch.object(financial_graph_helpers, "aggregate_like_row_stage", stopped_stage))
            self.assertTrue(financial_graph_helpers._candidate_matches_operand(contextual_candidate, operand))
        stopped_stage.assert_not_called()

        raw_stage = Mock(return_value="final")
        with ExitStack() as stack:
            for current_patch in common_patches:
                stack.enter_context(current_patch)
            stack.enter_context(patch.object(financial_graph_helpers, "_candidate_value_role", return_value="detail"))
            stack.enter_context(patch.object(financial_graph_helpers, "_candidate_aggregation_stage", return_value="none"))
            stack.enter_context(patch.object(financial_graph_helpers, "aggregate_like_row_stage", raw_stage))
            self.assertTrue(financial_graph_helpers._candidate_matches_operand(contextual_candidate, operand))
        raw_stage.assert_called_once_with("Aggregate Row Semantic")

        stopped_positive = Mock(side_effect=AssertionError("stage exception must stop positive-surface admission"))
        with ExitStack() as stack:
            for current_patch in common_patches[:-1]:
                stack.enter_context(current_patch)
            stack.enter_context(patch.object(financial_graph_helpers, "_text_has_positive_surface", stopped_positive))
            stack.enter_context(patch.object(financial_graph_helpers, "_candidate_value_role", return_value="detail"))
            stack.enter_context(patch.object(financial_graph_helpers, "_candidate_aggregation_stage", return_value="none"))
            stack.enter_context(
                patch.object(
                    financial_graph_helpers,
                    "aggregate_like_row_stage",
                    side_effect=RuntimeError("stage failed"),
                )
            )
            with self.assertRaisesRegex(RuntimeError, "stage failed"):
                financial_graph_helpers._candidate_matches_operand(contextual_candidate, operand)
        stopped_positive.assert_not_called()

    def test_current_source_lookup_preference_projection_pins_segment_short_circuit_coercion_and_exceptions(self) -> None:
        nested = {"preserve": True}
        segment_operand = {"concept": object(), "nested": nested}
        stopped_lookup = Mock(side_effect=AssertionError("segment hit must stop hint lookup"))
        with (
            patch.object(
                financial_operand_resolution,
                "_operand_segment_label",
                return_value=" Segment ",
            ) as segment_owner,
            patch.object(
                financial_operand_resolution,
                "lookup_hints_for_concept_key",
                stopped_lookup,
            ),
        ):
            self.assertFalse(
                financial_operand_resolution.lookup_prefers_canonical_statement_rows(
                    segment_operand
                )
            )
        segment_owner.assert_called_once_with(segment_operand)
        stopped_lookup.assert_not_called()

        events = []

        class ConceptProbe:
            def __str__(self):
                events.append("concept")
                return " concept "

        class PreferenceProbe:
            def __bool__(self):
                events.append("preference-bool")
                return True

        class HintMap:
            def get(self, key):
                events.append(("hint-get", key))
                return PreferenceProbe()

        concept = ConceptProbe()
        operand = {"concept": concept, "nested": nested}
        before_operand = dict(operand)

        def segment_projection(current_operand):
            events.append(("segment", current_operand is operand))
            return ""

        def hint_lookup(concept_key):
            events.append(("lookup", concept_key))
            return HintMap()

        with (
            patch.object(
                financial_operand_resolution,
                "_operand_segment_label",
                side_effect=segment_projection,
            ),
            patch.object(
                financial_operand_resolution,
                "lookup_hints_for_concept_key",
                side_effect=hint_lookup,
            ) as hint_owner,
        ):
            self.assertTrue(
                financial_operand_resolution.lookup_prefers_canonical_statement_rows(
                    operand
                )
            )
        hint_owner.assert_called_once_with(" concept ")
        self.assertEqual(
            events,
            [
                ("segment", True),
                "concept",
                ("lookup", " concept "),
                ("hint-get", "prefer_canonical_statement_rows"),
                "preference-bool",
            ],
        )
        self.assertEqual(operand, before_operand)
        self.assertIs(operand["concept"], concept)
        self.assertIs(operand["nested"], nested)

        with (
            patch.object(
                financial_operand_resolution,
                "_operand_segment_label",
                return_value="",
            ),
            patch.object(
                financial_operand_resolution,
                "lookup_hints_for_concept_key",
                return_value={},
            ) as empty_hint_owner,
        ):
            self.assertFalse(
                financial_operand_resolution.lookup_prefers_canonical_statement_rows(
                    {"concept": 0}
                )
            )
        empty_hint_owner.assert_called_once_with("")

        with (
            patch.object(
                financial_operand_resolution,
                "_operand_segment_label",
                side_effect=RuntimeError("segment failed"),
            ),
            patch.object(
                financial_operand_resolution,
                "lookup_hints_for_concept_key",
            ) as stopped_after_segment,
        ):
            with self.assertRaisesRegex(RuntimeError, "segment failed"):
                financial_operand_resolution.lookup_prefers_canonical_statement_rows(
                    operand
                )
        stopped_after_segment.assert_not_called()

        class ConceptBomb:
            def __str__(self):
                raise RuntimeError("concept failed")

        with (
            patch.object(
                financial_operand_resolution,
                "_operand_segment_label",
                return_value="",
            ),
            patch.object(
                financial_operand_resolution,
                "lookup_hints_for_concept_key",
            ) as stopped_after_concept,
        ):
            with self.assertRaisesRegex(RuntimeError, "concept failed"):
                financial_operand_resolution.lookup_prefers_canonical_statement_rows(
                    {"concept": ConceptBomb()}
                )
        stopped_after_concept.assert_not_called()

        with (
            patch.object(
                financial_operand_resolution,
                "_operand_segment_label",
                return_value="",
            ),
            patch.object(
                financial_operand_resolution,
                "lookup_hints_for_concept_key",
                side_effect=RuntimeError("lookup failed"),
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "lookup failed"):
                financial_operand_resolution.lookup_prefers_canonical_statement_rows(
                    {}
                )

        class HintGetBomb:
            def get(self, key):
                raise RuntimeError(f"hint get failed: {key}")

        with (
            patch.object(
                financial_operand_resolution,
                "_operand_segment_label",
                return_value="",
            ),
            patch.object(
                financial_operand_resolution,
                "lookup_hints_for_concept_key",
                return_value=HintGetBomb(),
            ),
        ):
            with self.assertRaisesRegex(
                RuntimeError,
                "hint get failed: prefer_canonical_statement_rows",
            ):
                financial_operand_resolution.lookup_prefers_canonical_statement_rows(
                    {}
                )

        class PreferenceBoolBomb:
            def __bool__(self):
                raise RuntimeError("preference bool failed")

        with (
            patch.object(
                financial_operand_resolution,
                "_operand_segment_label",
                return_value="",
            ),
            patch.object(
                financial_operand_resolution,
                "lookup_hints_for_concept_key",
                return_value={
                    "prefer_canonical_statement_rows": PreferenceBoolBomb()
                },
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "preference bool failed"):
                financial_operand_resolution.lookup_prefers_canonical_statement_rows(
                    {}
                )

    def test_current_source_lookup_surface_projections_pin_filtering_identity_laziness_and_exceptions(self) -> None:
        events = []

        class ConceptProbe:
            def __str__(self):
                events.append("concept")
                return " concept "

        class TextProbe:
            def __init__(self, name, value):
                self.name = name
                self.value = value

            def __str__(self):
                events.append(self.name)
                return self.value

        type_a = TextProbe("type-a", " A ")
        type_blank = TextProbe("type-blank", "   ")
        section_b = TextProbe("section-b", " B ")
        raw_types = [type_a, type_blank, type_a]
        raw_sections = [section_b]

        class HintMap:
            def get(self, key):
                events.append(("hint-get", key))
                return {
                    "canonical_statement_types": raw_types,
                    "canonical_sections": raw_sections,
                }.get(key)

        operand = {"concept": ConceptProbe(), "nested": {"preserve": True}}

        def canonical_hint_lookup(concept_key):
            events.append(("lookup", concept_key))
            return HintMap()

        with patch.object(
            financial_operand_resolution,
            "lookup_hints_for_concept_key",
            side_effect=canonical_hint_lookup,
        ) as hint_owner:
            canonical_types, canonical_sections = (
                financial_operand_resolution.lookup_canonical_statement_preferences(
                    operand
                )
            )
        hint_owner.assert_called_once_with(" concept ")
        self.assertEqual(canonical_types, ["A", "A"])
        self.assertEqual(canonical_sections, ["B"])
        self.assertIsNot(canonical_types, raw_types)
        self.assertIsNot(canonical_sections, raw_sections)
        self.assertEqual(
            events,
            [
                "concept",
                ("lookup", " concept "),
                ("hint-get", "canonical_statement_types"),
                "type-a",
                "type-a",
                "type-blank",
                "type-a",
                "type-a",
                ("hint-get", "canonical_sections"),
                "section-b",
                "section-b",
            ],
        )

        events.clear()
        surface_c = TextProbe("surface-c", " C ")
        surface_blank = TextProbe("surface-blank", "")
        raw_surfaces = [surface_c, surface_blank, surface_c]

        class SurfaceHintMap:
            def get(self, key):
                events.append(("hint-get", key))
                return raw_surfaces

        def surface_hint_lookup(concept_key):
            events.append(("lookup", concept_key))
            return SurfaceHintMap()

        with patch.object(
            financial_operand_resolution,
            "lookup_hints_for_concept_key",
            side_effect=surface_hint_lookup,
        ) as hint_owner:
            projected_surfaces = (
                financial_operand_resolution.lookup_query_surface_preferences(
                    operand
                )
            )
        hint_owner.assert_called_once_with(" concept ")
        self.assertEqual(projected_surfaces, ["C", "C"])
        self.assertIsNot(projected_surfaces, raw_surfaces)
        self.assertEqual(
            events,
            [
                "concept",
                ("lookup", " concept "),
                ("hint-get", "aggregate_query_surfaces"),
                "surface-c",
                "surface-c",
                "surface-blank",
                "surface-c",
                "surface-c",
            ],
        )

        class FalsyCollection:
            def __bool__(self):
                events.append("collection-bool")
                return False

            def __iter__(self):
                raise AssertionError("falsy collection must not be iterated")

        events.clear()
        with patch.object(
            financial_operand_resolution,
            "lookup_hints_for_concept_key",
            return_value={"aggregate_query_surfaces": FalsyCollection()},
        ):
            self.assertEqual(
                financial_operand_resolution.lookup_query_surface_preferences({}),
                [],
            )
        self.assertEqual(events, ["collection-bool"])

        class IterationBomb:
            def __iter__(self):
                raise RuntimeError("type iteration failed")

        class OrderedHintMap:
            def get(self, key):
                events.append(key)
                if key == "canonical_statement_types":
                    return IterationBomb()
                raise AssertionError("type failure must stop section access")

        events.clear()
        with patch.object(
            financial_operand_resolution,
            "lookup_hints_for_concept_key",
            return_value=OrderedHintMap(),
        ):
            with self.assertRaisesRegex(RuntimeError, "type iteration failed"):
                financial_operand_resolution.lookup_canonical_statement_preferences(
                    {}
                )
        self.assertEqual(events, ["canonical_statement_types"])

        class CollectionBoolBomb:
            def __bool__(self):
                raise RuntimeError("collection bool failed")

        with patch.object(
            financial_operand_resolution,
            "lookup_hints_for_concept_key",
            return_value={
                "aggregate_query_surfaces": CollectionBoolBomb()
            },
        ):
            with self.assertRaisesRegex(RuntimeError, "collection bool failed"):
                financial_operand_resolution.lookup_query_surface_preferences({})

        class ItemStringBomb:
            def __str__(self):
                raise RuntimeError("item string failed")

        with patch.object(
            financial_operand_resolution,
            "lookup_hints_for_concept_key",
            return_value={"aggregate_query_surfaces": [ItemStringBomb()]},
        ):
            with self.assertRaisesRegex(RuntimeError, "item string failed"):
                financial_operand_resolution.lookup_query_surface_preferences({})

        text = object()
        projected = ["surface"]
        matcher_result = object()
        with (
            patch.object(
                financial_operand_resolution,
                "lookup_query_surface_preferences",
                return_value=projected,
            ) as projection_owner,
            patch.object(
                financial_operand_resolution,
                "_text_has_contract_term",
                return_value=matcher_result,
            ) as matcher_owner,
        ):
            self.assertIs(
                financial_operand_resolution.operand_lookup_surface_match(
                    text,
                    operand,
                ),
                matcher_result,
            )
        projection_owner.assert_called_once_with(operand)
        matcher_owner.assert_called_once_with(text, projected)
        self.assertIs(matcher_owner.call_args.args[0], text)
        self.assertIs(matcher_owner.call_args.args[1], projected)

        with (
            patch.object(
                financial_operand_resolution,
                "lookup_query_surface_preferences",
                return_value=[],
            ) as projection_owner,
            patch.object(
                financial_operand_resolution,
                "_text_has_contract_term",
                side_effect=AssertionError("empty projection must stop matcher"),
            ) as stopped_matcher,
        ):
            self.assertFalse(
                financial_operand_resolution.operand_lookup_surface_match(
                    text,
                    operand,
                )
            )
        projection_owner.assert_called_once_with(operand)
        stopped_matcher.assert_not_called()

        with (
            patch.object(
                financial_operand_resolution,
                "lookup_query_surface_preferences",
                side_effect=RuntimeError("projection failed"),
            ),
            patch.object(
                financial_operand_resolution,
                "_text_has_contract_term",
            ) as stopped_matcher,
        ):
            with self.assertRaisesRegex(RuntimeError, "projection failed"):
                financial_operand_resolution.operand_lookup_surface_match(
                    text,
                    operand,
                )
        stopped_matcher.assert_not_called()

        with (
            patch.object(
                financial_operand_resolution,
                "lookup_query_surface_preferences",
                return_value=projected,
            ),
            patch.object(
                financial_operand_resolution,
                "_text_has_contract_term",
                side_effect=RuntimeError("matcher failed"),
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "matcher failed"):
                financial_operand_resolution.operand_lookup_surface_match(
                    text,
                    operand,
                )

    def test_current_source_lookup_hint_bindings_pin_defs_calls_dag_imports_and_baseline(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        agent_root = repo_root / "src" / "agent"
        target_names = {
            "lookup_prefers_canonical_statement_rows",
            "lookup_canonical_statement_preferences",
            "lookup_query_surface_preferences",
            "operand_lookup_surface_match",
        }
        module_paths = {path.stem: path for path in agent_root.glob("*.py")}
        module_trees = {
            name: ast.parse(path.read_text(encoding="utf-8-sig"))
            for name, path in module_paths.items()
        }
        definitions = {name: [] for name in target_names}
        calls = {name: [] for name in target_names}
        dependency_loads = {
            "_operand_segment_label": [],
            "lookup_hints_for_concept_key": [],
            "_text_has_contract_term": [],
        }

        class BindingVisitor(ast.NodeVisitor):
            def __init__(self, module_name):
                self.module_name = module_name
                self.function_stack = []
                self.try_depth = 0

            def visit_FunctionDef(self, node):
                if node.name in target_names:
                    definitions[node.name].append((self.module_name, node))
                self.function_stack.append(node.name)
                self.generic_visit(node)
                self.function_stack.pop()

            visit_AsyncFunctionDef = visit_FunctionDef

            def visit_Try(self, node):
                self.try_depth += 1
                self.generic_visit(node)
                self.try_depth -= 1

            visit_TryStar = visit_Try

            def visit_Call(self, node):
                called_name = node.func.id if isinstance(node.func, ast.Name) else ""
                if called_name in target_names:
                    calls[called_name].append(
                        (
                            self.module_name,
                            self.function_stack[-1] if self.function_stack else "",
                            type(node.func).__name__,
                            tuple(ast.unparse(arg) for arg in node.args),
                            tuple(
                                (keyword.arg, ast.unparse(keyword.value))
                                for keyword in node.keywords
                            ),
                            self.try_depth,
                        )
                    )
                self.generic_visit(node)

            def visit_Name(self, node):
                if (
                    isinstance(node.ctx, ast.Load)
                    and node.id in dependency_loads
                    and self.function_stack
                    and self.function_stack[-1] in target_names
                ):
                    dependency_loads[node.id].append(
                        (self.module_name, self.function_stack[-1])
                    )
                self.generic_visit(node)

        for module_name, tree in module_trees.items():
            BindingVisitor(module_name).visit(tree)

        preference_name = "lookup_prefers_canonical_statement_rows"
        canonical_name = "lookup_canonical_statement_preferences"
        query_name = "lookup_query_surface_preferences"
        match_name = "operand_lookup_surface_match"
        expected_owner = "financial_operand_resolution"
        expected_spans = {
            preference_name: 5,
            canonical_name: 14,
            query_name: 7,
            match_name: 5,
        }
        self.assertEqual(
            {
                name: [
                    (module_name, node.end_lineno - node.lineno + 1)
                    for module_name, node in definitions[name]
                ]
                for name in target_names
            },
            {
                name: [(expected_owner, expected_spans[name])]
                for name in target_names
            },
        )
        self.assertEqual(
            {
                name: (
                    [arg.arg for arg in definitions[name][0][1].args.args],
                    [arg.arg for arg in definitions[name][0][1].args.kwonlyargs],
                    ast.unparse(definitions[name][0][1].returns),
                )
                for name in target_names
            },
            {
                preference_name: (["operand"], [], "bool"),
                canonical_name: (
                    ["operand"],
                    [],
                    "tuple[List[str], List[str]]",
                ),
                query_name: (["operand"], [], "List[str]"),
                match_name: (["text", "operand"], [], "bool"),
            },
        )
        self.assertTrue(
            all(
                not any(isinstance(item, ast.Try) for item in ast.walk(node))
                for entries in definitions.values()
                for _module_name, node in entries
            )
        )

        expected_callers = {
            preference_name: [
                ("financial_graph_helpers", "_candidate_is_canonical_statement_winner"),
                ("financial_graph_helpers", "_build_lookup_producer_task_from_binding"),
                ("financial_graph_helpers", "_build_lookup_producer_task_from_binding"),
                ("financial_graph_helpers", "_candidate_is_direct_grounding_candidate"),
                (
                    "financial_graph_helpers",
                    "_candidate_satisfies_direct_acceptance_contract",
                ),
                ("financial_graph_helpers", "_score_operand_candidate"),
                ("financial_graph_helpers", "_build_reconciliation_retry_queries"),
            ],
            canonical_name: [
                ("financial_graph_helpers", "_candidate_is_canonical_statement_winner"),
                ("financial_graph_helpers", "_build_lookup_producer_task_from_binding"),
                (
                    "financial_graph_helpers",
                    "_candidate_satisfies_direct_acceptance_contract",
                ),
                ("financial_graph_helpers", "_score_operand_candidate"),
                ("financial_graph_helpers", "_build_reconciliation_retry_queries"),
            ],
            query_name: [
                ("financial_graph_helpers", "_query_surfaces_for_operand"),
                (expected_owner, match_name),
                ("financial_graph_helpers", "_build_lookup_producer_task_from_binding"),
                ("financial_graph_helpers", "_build_reconciliation_retry_queries"),
            ],
            match_name: [
                ("financial_graph_helpers", "_candidate_direct_match_strength"),
            ],
        }
        self.assertEqual(
            {
                name: sorted(entry[:2] for entry in calls[name])
                for name in target_names
            },
            {
                name: sorted(expected_callers[name])
                for name in target_names
            },
        )
        self.assertEqual(
            {name: len(calls[name]) for name in target_names},
            {
                preference_name: 7,
                canonical_name: 5,
                query_name: 4,
                match_name: 1,
            },
        )
        self.assertTrue(
            all(
                entry[2] == "Name"
                and entry[4] == ()
                and entry[5] == 0
                for entries in calls.values()
                for entry in entries
            )
        )
        self.assertEqual(
            sorted(
                (name, entry[3])
                for name in target_names
                for entry in calls[name]
            ),
            sorted(
                [
                    *[(preference_name, ("operand",)) for _ in range(6)],
                    (preference_name, ("spec",)),
                    *[(canonical_name, ("operand",)) for _ in range(4)],
                    (canonical_name, ("spec",)),
                    *[(query_name, ("operand",)) for _ in range(3)],
                    (query_name, ("spec",)),
                    (match_name, ("aggregate_signal", "operand")),
                ]
            ),
        )
        self.assertEqual(
            {
                name: sorted(entries)
                for name, entries in dependency_loads.items()
            },
            {
                "_operand_segment_label": [
                    (expected_owner, preference_name)
                ],
                "lookup_hints_for_concept_key": sorted(
                    [
                        (expected_owner, preference_name),
                        (expected_owner, canonical_name),
                        (expected_owner, query_name),
                    ]
                ),
                "_text_has_contract_term": [
                    (expected_owner, match_name)
                ],
            },
        )

        graph_defs = [
            node
            for node in module_trees["financial_graph_helpers"].body
            if isinstance(node, ast.FunctionDef)
        ]
        operand_defs = [
            node
            for node in module_trees["financial_operand_resolution"].body
            if isinstance(node, ast.FunctionDef)
        ]
        self.assertEqual(
            (
                sum(not node.name.startswith("_") for node in graph_defs),
                sum(node.name.startswith("_") for node in graph_defs),
            ),
            (9, 97),
        )
        self.assertEqual(
            (
                sum(not node.name.startswith("_") for node in operand_defs),
                sum(node.name.startswith("_") for node in operand_defs),
            ),
            (43, 37),
        )

        def imported_names(module_name, imported_module):
            return {
                alias.name
                for node in module_trees[module_name].body
                if isinstance(node, ast.ImportFrom)
                and node.module == imported_module
                for alias in node.names
            }

        graph_operand_imports = imported_names(
            "financial_graph_helpers",
            "src.agent.financial_operand_resolution",
        )
        graph_surface_imports = imported_names(
            "financial_graph_helpers",
            "src.agent.financial_surface_contracts",
        )
        operand_surface_imports = imported_names(
            "financial_operand_resolution",
            "src.agent.financial_surface_contracts",
        )
        self.assertNotIn("lookup_hints_for_concept_key", graph_operand_imports)
        self.assertTrue(target_names <= graph_operand_imports)
        self.assertNotIn("_text_has_contract_term", graph_surface_imports)
        self.assertIn("_operand_segment_label", operand_surface_imports)
        self.assertIn("_text_has_contract_term", operand_surface_imports)

        edges = {name: set() for name in module_trees}
        for module_name, tree in module_trees.items():
            for node in tree.body:
                if not isinstance(node, ast.ImportFrom) or not node.module:
                    continue
                prefix = "src.agent."
                if not node.module.startswith(prefix):
                    continue
                imported = node.module[len(prefix) :]
                if imported in edges:
                    edges[module_name].add(imported)

        def reaches(start, target):
            seen = set()
            pending = list(edges[start])
            while pending:
                current = pending.pop()
                if current == target:
                    return True
                if current in seen:
                    continue
                seen.add(current)
                pending.extend(edges[current])
            return False

        self.assertTrue(
            reaches(
                "financial_graph_helpers",
                "financial_operand_resolution",
            )
        )
        self.assertTrue(
            reaches(
                "financial_operand_resolution",
                "financial_surface_contracts",
            )
        )
        self.assertFalse(
            reaches(
                "financial_operand_resolution",
                "financial_graph_helpers",
            )
        )
        self.assertFalse(
            reaches(
                "financial_surface_contracts",
                "financial_operand_resolution",
            )
        )

        baseline = json.loads(
            (
                repo_root
                / "tests"
                / "fixtures"
                / "runtime_domain_terms_baseline.json"
            ).read_text(encoding="utf-8-sig")
        )
        self.assertEqual(len(baseline["records"]), 218)
        selected_hits = []
        for record in baseline["records"]:
            if record.get("path") != f"src/agent/{expected_owner}.py":
                continue
            for name in target_names:
                node = definitions[name][0][1]
                if any(
                    node.lineno <= line <= node.end_lineno
                    for line in record.get("first_lines") or []
                ):
                    selected_hits.append((name, record))
        self.assertEqual(selected_hits, [])

    def test_current_source_lookup_hint_callers_pin_args_adoption_order_and_stop(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        graph_source = (
            repo_root / "src" / "agent" / "financial_graph_helpers.py"
        ).read_text(encoding="utf-8-sig")
        graph_tree = ast.parse(graph_source)
        function_nodes = {
            node.name: node
            for node in graph_tree.body
            if isinstance(node, ast.FunctionDef)
        }

        def function_source(name):
            return ast.get_source_segment(graph_source, function_nodes[name]) or ""

        preference_name = "lookup_prefers_canonical_statement_rows"
        canonical_name = "lookup_canonical_statement_preferences"
        query_name = "lookup_query_surface_preferences"
        match_name = "operand_lookup_surface_match"

        winner_source = function_source(
            "_candidate_is_canonical_statement_winner"
        )
        self.assertLess(
            winner_source.index(preference_name),
            winner_source.index("metadata ="),
        )
        self.assertLess(
            winner_source.index(preference_name),
            winner_source.index(canonical_name),
        )
        self.assertLess(
            winner_source.index(canonical_name),
            winner_source.index("_candidate_direct_match_strength"),
        )

        generic_source = function_source("_build_generic_retrieval_queries")
        self.assertLess(generic_source.index("label ="), generic_source.index("for alias in"))
        self.assertLess(generic_source.index("for alias in"), generic_source.index(query_name))

        producer_source = function_source(
            "_build_lookup_producer_task_from_binding"
        )
        first_preference = producer_source.index(preference_name)
        second_preference = producer_source.index(
            preference_name,
            first_preference + len(preference_name),
        )
        self.assertLess(
            producer_source.index("explicit_binding_policy"),
            first_preference,
        )
        self.assertLess(first_preference, producer_source.index("binding_segment"))
        self.assertLess(producer_source.index("binding_segment"), producer_source.index(query_name))
        self.assertLess(producer_source.index(query_name), second_preference)
        self.assertLess(second_preference, producer_source.index(canonical_name))
        self.assertLess(
            producer_source.index(canonical_name),
            producer_source.index("_build_generic_retrieval_queries"),
        )

        grounding_source = function_source(
            "_candidate_is_direct_grounding_candidate"
        )
        grounding_preference = grounding_source.index(preference_name)
        self.assertLess(
            grounding_source.index("direct_match_strength"),
            grounding_preference,
        )
        self.assertLess(
            grounding_source.index("binding_policy_allows_candidate_shape"),
            grounding_preference,
        )
        self.assertLess(
            grounding_preference,
            grounding_source.index("candidate_kind == \"table_row\""),
        )

        acceptance_source = function_source(
            "_candidate_satisfies_direct_acceptance_contract"
        )
        acceptance_preference = acceptance_source.index(preference_name)
        self.assertLess(
            acceptance_source.rfind(
                "operation_family in",
                0,
                acceptance_preference,
            ),
            acceptance_preference,
        )
        self.assertLess(
            acceptance_preference,
            acceptance_source.index(canonical_name),
        )
        self.assertLess(
            acceptance_source.index(canonical_name),
            acceptance_source.index("_is_balance_sheet_aggregate_operand"),
        )

        strength_source = function_source("_candidate_direct_match_strength")
        strength_match = strength_source.index(match_name)
        self.assertLess(strength_source.index("aggregate_signal ="), strength_match)
        self.assertLess(
            strength_match,
            strength_source.index("_candidate_has_operand_context_surface"),
        )
        self.assertLess(
            strength_source.index("_candidate_has_operand_context_surface"),
            strength_source.index("_candidate_value_role", strength_match),
        )
        self.assertLess(
            strength_source.index("_candidate_value_role", strength_match),
            strength_source.index("_candidate_aggregation_stage", strength_match),
        )

        score_source = function_source("_score_operand_candidate")
        score_preference = score_source.index(preference_name)
        self.assertLess(
            score_source.rfind("statement_type =", 0, score_preference),
            score_preference,
        )
        self.assertLess(score_preference, score_source.index(canonical_name))
        self.assertLess(
            score_source.index(canonical_name),
            score_source.index("candidate_consolidation_scope"),
        )

        retry_source = function_source("_build_reconciliation_retry_queries")
        self.assertLess(retry_source.index(query_name), retry_source.index(preference_name))
        self.assertLess(retry_source.index(preference_name), retry_source.index(canonical_name))
        self.assertLess(
            retry_source.index(canonical_name),
            retry_source.index("binding_policy ="),
        )

        candidate = object()
        operand = object()
        stopped_canonical = Mock(
            side_effect=AssertionError("preference miss must stop canonical lists")
        )
        stopped_strength = Mock(
            side_effect=AssertionError("preference miss must stop direct strength")
        )
        with (
            patch.object(
                financial_graph_helpers,
                preference_name,
                return_value=False,
            ) as winner_preference,
            patch.object(
                financial_graph_helpers,
                canonical_name,
                stopped_canonical,
            ),
            patch.object(
                financial_graph_helpers,
                "_candidate_direct_match_strength",
                stopped_strength,
            ),
        ):
            self.assertFalse(
                financial_graph_helpers._candidate_is_canonical_statement_winner(
                    candidate,
                    operand=operand,
                    query_years=[],
                )
            )
        winner_preference.assert_called_once_with(operand)
        stopped_canonical.assert_not_called()
        stopped_strength.assert_not_called()

        query_operand = {
            "label": "Label",
            "aliases": [
                "Alias One",
                "Alias Two",
                "Alias Three",
                "Never Fourth Alias",
            ],
        }
        with patch.object(
            financial_graph_helpers,
            query_name,
            return_value=["Hint Surface"],
        ) as generic_query_owner:
            retrieval_queries = (
                financial_graph_helpers._build_generic_retrieval_queries(
                    "Base Query",
                    "Metric",
                    [query_operand],
                    [],
                    {},
                    {},
                )
            )
        generic_query_owner.assert_called_once_with(query_operand)
        self.assertTrue(
            any("Hint Surface" in query for query in retrieval_queries)
        )
        self.assertFalse(
            any("Never Fourth Alias" in query for query in retrieval_queries)
        )

        producer_events = []
        source_operand = {
            "role": "current_period",
            "concept": "",
            "aliases": ["Existing Alias"],
            "binding_policy": {
                "prefer_value_roles": ["aggregate"],
                "prefer_aggregation_stages": ["final"],
            },
        }
        consumer_task = {
            "query": "Consumer Query",
            "required_operands": [source_operand],
            "preferred_statement_types": ["consumer-type"],
            "preferred_sections": ["consumer-section"],
            "constraints": {},
        }
        binding = {
            "role": "current_period",
            "concept": "",
            "binding_policy": {"explicit": True},
        }
        producer_operands = []

        def producer_query_preferences(current_operand):
            producer_events.append("query")
            producer_operands.append(current_operand)
            return ["Hint Alias"]

        def producer_preference(current_operand):
            producer_events.append("preference")
            producer_operands.append(current_operand)
            return True

        def producer_canonical(current_operand):
            producer_events.append("canonical")
            producer_operands.append(current_operand)
            return (["canonical-type"], ["canonical-section"])

        def producer_retrieval(**kwargs):
            producer_events.append("retrieval")
            producer_operands.append(kwargs["operand_specs"][0])
            return ["retrieval-query"]

        def producer_task_query(**kwargs):
            producer_events.append("task-query")
            producer_operands.append(kwargs["operand_specs"][0])
            return "task-query"

        with (
            patch.object(
                financial_graph_helpers,
                "_dependency_metric_label",
                return_value="Metric",
            ),
            patch.object(
                financial_graph_helpers,
                "_lookup_constraint_from_binding",
                return_value={},
            ),
            patch.object(
                financial_graph_helpers,
                query_name,
                side_effect=producer_query_preferences,
            ),
            patch.object(
                financial_graph_helpers,
                preference_name,
                side_effect=producer_preference,
            ) as producer_preference_owner,
            patch.object(
                financial_graph_helpers,
                canonical_name,
                side_effect=producer_canonical,
            ),
            patch.object(
                financial_graph_helpers,
                "_build_generic_retrieval_queries",
                side_effect=producer_retrieval,
            ),
            patch.object(
                financial_graph_helpers,
                "_build_metric_task_query",
                side_effect=producer_task_query,
            ),
        ):
            producer_task = (
                financial_graph_helpers._build_lookup_producer_task_from_binding(
                    binding=binding,
                    consumer_task=consumer_task,
                    next_task_id="task-1",
                    report_scope={},
                )
            )
        producer_preference_owner.assert_called_once()
        self.assertEqual(
            producer_events,
            ["query", "preference", "canonical", "retrieval", "task-query"],
        )
        projected_operand = producer_task["required_operands"][0]
        self.assertTrue(
            all(current_operand is projected_operand for current_operand in producer_operands)
        )
        self.assertIsNot(projected_operand, source_operand)
        self.assertEqual(
            projected_operand["aliases"],
            ["Hint Alias", "Existing Alias"],
        )
        self.assertEqual(
            producer_task["preferred_statement_types"],
            ["canonical-type"],
        )
        self.assertEqual(
            producer_task["preferred_sections"],
            ["canonical-section"],
        )

        fallback_events = []
        fallback_operands = []

        def fallback_preference(current_operand):
            fallback_events.append("preference")
            fallback_operands.append(current_operand)
            return len(fallback_operands) == 1

        def fallback_query(current_operand):
            fallback_events.append("query")
            fallback_operands.append(current_operand)
            return []

        stopped_fallback_canonical = Mock(
            side_effect=AssertionError("second preference miss must stop canonical lists")
        )
        with (
            patch.object(
                financial_graph_helpers,
                "_dependency_metric_label",
                return_value="Metric",
            ),
            patch.object(
                financial_graph_helpers,
                "_lookup_constraint_from_binding",
                return_value={},
            ),
            patch.object(
                financial_graph_helpers,
                preference_name,
                side_effect=fallback_preference,
            ),
            patch.object(
                financial_graph_helpers,
                query_name,
                side_effect=fallback_query,
            ),
            patch.object(
                financial_graph_helpers,
                canonical_name,
                stopped_fallback_canonical,
            ),
            patch.object(
                financial_graph_helpers,
                "_build_generic_retrieval_queries",
                return_value=[],
            ),
            patch.object(
                financial_graph_helpers,
                "_build_metric_task_query",
                return_value="task-query",
            ),
        ):
            fallback_task = (
                financial_graph_helpers._build_lookup_producer_task_from_binding(
                    binding={"role": "current_period", "concept": ""},
                    consumer_task=consumer_task,
                    next_task_id="task-2",
                    report_scope={},
                )
            )
        self.assertEqual(
            fallback_events,
            ["preference", "query", "preference"],
        )
        self.assertIs(
            fallback_operands[0],
            fallback_operands[1],
        )
        self.assertIs(
            fallback_operands[1],
            fallback_operands[2],
        )
        stopped_fallback_canonical.assert_not_called()
        fallback_binding_policy = fallback_task["required_operands"][0][
            "binding_policy"
        ]
        self.assertNotIn("prefer_value_roles", fallback_binding_policy)
        self.assertNotIn("prefer_aggregation_stages", fallback_binding_policy)

        grounding_candidate = {
            "candidate_kind": "structured_value",
            "metadata": {},
        }
        grounding_operand = {"binding_policy": {}}
        stopped_consolidation = Mock(
            side_effect=AssertionError("preference exception must stop consolidation")
        )
        with (
            patch.object(
                financial_graph_helpers,
                "candidate_is_descriptor_row",
                return_value=False,
            ),
            patch.object(
                financial_graph_helpers,
                "candidate_has_numeric_value_signal",
                return_value=True,
            ),
            patch.object(
                financial_graph_helpers,
                "_candidate_direct_match_strength",
                return_value=1.0,
            ),
            patch.object(
                financial_graph_helpers,
                "_candidate_value_role",
                return_value="aggregate",
            ),
            patch.object(
                financial_graph_helpers,
                "_candidate_aggregation_stage",
                return_value="final",
            ),
            patch.object(
                financial_graph_helpers,
                "binding_policy_allows_candidate_shape",
                return_value=True,
            ),
            patch.object(
                financial_graph_helpers,
                preference_name,
                side_effect=RuntimeError("grounding preference failed"),
            ) as grounding_preference,
            patch.object(
                financial_graph_helpers,
                "candidate_consolidation_scope",
                stopped_consolidation,
            ),
        ):
            with self.assertRaisesRegex(
                RuntimeError,
                "grounding preference failed",
            ):
                financial_graph_helpers._candidate_is_direct_grounding_candidate(
                    grounding_candidate,
                    operand=grounding_operand,
                    constraints={},
                    query_years=[],
                )
        grounding_preference.assert_called_once_with(grounding_operand)
        stopped_consolidation.assert_not_called()

        acceptance_candidate = {"metadata": {}}
        acceptance_operand = {"binding_policy": {}}
        stopped_ratio_preference = Mock(
            side_effect=AssertionError("non-lookup family must stop preference")
        )
        with (
            patch.object(
                financial_graph_helpers,
                "_candidate_is_direct_grounding_candidate",
                return_value=True,
            ),
            patch.object(
                financial_graph_helpers,
                "operand_period_focus",
                return_value="unknown",
            ),
            patch.object(
                financial_graph_helpers,
                "_candidate_value_role",
                return_value="detail",
            ),
            patch.object(
                financial_graph_helpers,
                "_candidate_aggregation_stage",
                return_value="none",
            ),
            patch.object(
                financial_graph_helpers,
                preference_name,
                stopped_ratio_preference,
            ),
            patch.object(
                financial_graph_helpers,
                "_is_balance_sheet_aggregate_operand",
                return_value=False,
            ),
            patch.object(
                financial_graph_helpers,
                "_is_capex_total_operand",
                return_value=False,
            ),
            patch.object(
                financial_graph_helpers,
                "operand_target_years",
                return_value=[],
            ),
        ):
            self.assertTrue(
                financial_graph_helpers._candidate_satisfies_direct_acceptance_contract(
                    acceptance_candidate,
                    operand=acceptance_operand,
                    constraints={},
                    query_years=[],
                    operation_family="ratio",
                )
            )
        stopped_ratio_preference.assert_not_called()

        stopped_balance = Mock(
            side_effect=AssertionError("canonical exception must stop aggregate policy")
        )
        with (
            patch.object(
                financial_graph_helpers,
                "_candidate_is_direct_grounding_candidate",
                return_value=True,
            ),
            patch.object(
                financial_graph_helpers,
                "operand_period_focus",
                return_value="unknown",
            ),
            patch.object(
                financial_graph_helpers,
                "candidate_selected_unit_family",
                return_value="",
            ),
            patch.object(
                financial_graph_helpers,
                "_candidate_direct_match_strength",
                return_value=2.0,
            ),
            patch.object(
                financial_graph_helpers,
                "_candidate_value_role",
                return_value="aggregate",
            ),
            patch.object(
                financial_graph_helpers,
                "_candidate_aggregation_stage",
                return_value="final",
            ),
            patch.object(
                financial_graph_helpers,
                preference_name,
                return_value=True,
            ) as acceptance_preference,
            patch.object(
                financial_graph_helpers,
                canonical_name,
                side_effect=RuntimeError("canonical failed"),
            ) as acceptance_canonical,
            patch.object(
                financial_graph_helpers,
                "_is_balance_sheet_aggregate_operand",
                stopped_balance,
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "canonical failed"):
                financial_graph_helpers._candidate_satisfies_direct_acceptance_contract(
                    acceptance_candidate,
                    operand=acceptance_operand,
                    constraints={},
                    query_years=[],
                    operation_family="lookup",
                )
        acceptance_preference.assert_called_once_with(acceptance_operand)
        acceptance_canonical.assert_called_once_with(acceptance_operand)
        stopped_balance.assert_not_called()

        strength_candidate = {
            "metadata": {"aggregate_label": " Aggregate Signal "}
        }
        strength_operand = {}
        stopped_context = Mock(
            side_effect=AssertionError("surface miss must stop context")
        )
        stopped_role = Mock(side_effect=AssertionError("surface miss must stop role"))
        stopped_stage = Mock(side_effect=AssertionError("surface miss must stop stage"))
        common_strength_patches = (
            patch.object(
                financial_graph_helpers,
                "_candidate_conflicts_with_operand_concept",
                return_value=False,
            ),
            patch.object(
                financial_graph_helpers,
                "_operand_needles",
                return_value=[],
            ),
            patch.object(
                financial_graph_helpers,
                "_operand_text_match",
                return_value=False,
            ),
            patch.object(
                financial_graph_helpers,
                "_is_capex_total_operand",
                return_value=False,
            ),
            patch.object(
                financial_graph_helpers,
                "_operand_prefers_contextual_aggregate_match",
                return_value=False,
            ),
            patch.object(
                financial_graph_helpers,
                "candidate_supports_segment_metric_combo",
                return_value=False,
            ),
        )
        with ExitStack() as stack:
            for current_patch in common_strength_patches:
                stack.enter_context(current_patch)
            surface_match = stack.enter_context(
                patch.object(
                    financial_graph_helpers,
                    match_name,
                    return_value=False,
                )
            )
            stack.enter_context(
                patch.object(
                    financial_graph_helpers,
                    "_candidate_has_operand_context_surface",
                    stopped_context,
                )
            )
            stack.enter_context(
                patch.object(
                    financial_graph_helpers,
                    "_candidate_value_role",
                    stopped_role,
                )
            )
            stack.enter_context(
                patch.object(
                    financial_graph_helpers,
                    "_candidate_aggregation_stage",
                    stopped_stage,
                )
            )
            self.assertEqual(
                financial_graph_helpers._candidate_direct_match_strength(
                    strength_candidate,
                    strength_operand,
                ),
                0.0,
            )
        surface_match.assert_called_once_with("Aggregate Signal", strength_operand)
        stopped_context.assert_not_called()
        stopped_role.assert_not_called()
        stopped_stage.assert_not_called()

        score_candidate = {"metadata": {}}
        score_operand = {"binding_policy": {}}
        stopped_score_scope = Mock(
            side_effect=AssertionError("preference exception must stop score scope")
        )
        with (
            patch.object(
                financial_graph_helpers,
                "_candidate_conflicts_with_operand_concept",
                return_value=False,
            ),
            patch.object(
                financial_graph_helpers,
                "_candidate_direct_match_strength",
                return_value=0.0,
            ),
            patch.object(
                financial_graph_helpers,
                "_candidate_value_role",
                return_value="",
            ),
            patch.object(
                financial_graph_helpers,
                "_candidate_aggregation_stage",
                return_value="",
            ),
            patch.object(
                financial_graph_helpers,
                "candidate_has_numeric_value_signal",
                return_value=False,
            ),
            patch.object(
                financial_graph_helpers,
                "_candidate_location_entity_subject_score",
                return_value=0.0,
            ),
            patch.object(
                financial_graph_helpers,
                "candidate_is_descriptor_row",
                return_value=False,
            ),
            patch.object(
                financial_graph_helpers,
                preference_name,
                side_effect=RuntimeError("score preference failed"),
            ) as score_preference,
            patch.object(
                financial_graph_helpers,
                "candidate_consolidation_scope",
                stopped_score_scope,
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "score preference failed"):
                financial_graph_helpers._score_operand_candidate(
                    score_candidate,
                    operand=score_operand,
                    preferred_statement_types=[],
                    constraints={},
                    query_years=[],
                )
        score_preference.assert_called_once_with(score_operand)
        stopped_score_scope.assert_not_called()

        retry_nested = {"preserve": True}
        retry_spec = {
            "label": "Operand",
            "aliases": ["Alias"],
            "preferred_sections": ["operand-section"],
            "binding_policy": {},
            "nested": retry_nested,
        }
        retry_task = {
            "metric_label": "Metric",
            "constraints": {},
            "required_operands": [retry_spec],
            "preferred_sections": ["task-section"],
        }
        retry_events = []
        retry_operands = []

        def retry_query_preferences(current_operand):
            retry_events.append("query")
            retry_operands.append(current_operand)
            return ["Hint"]

        def retry_preference(current_operand):
            retry_events.append("preference")
            retry_operands.append(current_operand)
            return True

        def retry_canonical(current_operand):
            retry_events.append("canonical")
            retry_operands.append(current_operand)
            return (["ignored-type"], ["canonical-section"])

        with (
            patch.object(
                financial_graph_helpers,
                query_name,
                side_effect=retry_query_preferences,
            ),
            patch.object(
                financial_graph_helpers,
                preference_name,
                side_effect=retry_preference,
            ),
            patch.object(
                financial_graph_helpers,
                canonical_name,
                side_effect=retry_canonical,
            ),
        ):
            retry_queries = (
                financial_graph_helpers._build_reconciliation_retry_queries(
                    active_subtask=retry_task,
                    missing_operands=["Operand"],
                    years=[],
                )
            )
        self.assertEqual(retry_events, ["query", "preference", "canonical"])
        self.assertTrue(
            all(current_operand is retry_operands[0] for current_operand in retry_operands)
        )
        self.assertIsNot(retry_operands[0], retry_spec)
        self.assertIs(retry_operands[0]["nested"], retry_nested)
        self.assertTrue(
            any("canonical-section" in query for query in retry_queries)
        )
        self.assertFalse(any("ignored-type" in query for query in retry_queries))

        stopped_retry_preference = Mock(
            side_effect=AssertionError("query exception must stop retry preference")
        )
        stopped_retry_canonical = Mock(
            side_effect=AssertionError("query exception must stop canonical lists")
        )
        with (
            patch.object(
                financial_graph_helpers,
                query_name,
                side_effect=RuntimeError("retry query failed"),
            ),
            patch.object(
                financial_graph_helpers,
                preference_name,
                stopped_retry_preference,
            ),
            patch.object(
                financial_graph_helpers,
                canonical_name,
                stopped_retry_canonical,
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "retry query failed"):
                financial_graph_helpers._build_reconciliation_retry_queries(
                    active_subtask=retry_task,
                    missing_operands=["Operand"],
                    years=[],
                )
        stopped_retry_preference.assert_not_called()
        stopped_retry_canonical.assert_not_called()

    def test_current_source_direct_candidate_signature_projection_pins_metadata_value_period_scope_and_identity(self) -> None:
        nested = {"preserve": True}

        class TextBomb:
            def __init__(self, message):
                self.message = message

            def __str__(self):
                raise AssertionError(self.message)

        semantic_bomb = TextBomb("row hit must stop semantic label")
        aggregate_bomb = TextBomb("row hit must stop aggregate label")
        row_text_bomb = TextBomb("selected value must stop row fallback")
        period_bomb = TextBomb("selected headers must stop period fallback")
        section_bomb = TextBomb("block scope must stop section fallback")
        candidate_text_bomb = TextBomb("selected value must stop candidate text")
        metadata = {
            "table_source_id": " table-1 ",
            "row_label": " row-1 ",
            "semantic_label": semantic_bomb,
            "aggregate_label": aggregate_bomb,
            "row_text": row_text_bomb,
            "period_focus": period_bomb,
            "section_path": section_bomb,
            "statement_type": " notes ",
            "nested": nested,
        }
        candidate = {
            "candidate_id": "candidate-1",
            "metadata": metadata,
            "text": candidate_text_bomb,
            "nested": nested,
        }
        headers = [" 2024 ", "", " annual "]
        selected_cell = {
            "value_text": " 100 ",
            "column_headers": headers,
            "nested": nested,
        }
        before_candidate = dict(candidate)
        before_metadata = dict(metadata)
        before_cell = dict(selected_cell)
        before_headers = list(headers)
        block_key = object()
        block_candidates = []

        def block_signature(current_candidate):
            block_candidates.append(current_candidate)
            self.assertIs(current_candidate, candidate)
            self.assertIs(current_candidate["metadata"], metadata)
            self.assertIs(current_candidate["metadata"]["nested"], nested)
            return block_key

        with patch.object(
            financial_operand_resolution,
            "candidate_row_block_signature",
            side_effect=block_signature,
        ) as block_owner:
            logical = financial_operand_resolution.candidate_direct_logical_signature(
                candidate,
                selected_cell=selected_cell,
            )
            family = financial_operand_resolution.candidate_direct_family_signature(
                candidate,
                selected_cell=selected_cell,
            )

        self.assertIs(logical[0], block_key)
        self.assertEqual(logical[1:], ("row-1", "100", "2024 annual"))
        self.assertIs(family[0], block_key)
        self.assertEqual(family[1:], ("row-1", "2024 annual", "notes"))
        self.assertEqual(block_candidates, [candidate, candidate])
        self.assertEqual(block_owner.call_count, 2)
        self.assertEqual(candidate, before_candidate)
        self.assertEqual(metadata, before_metadata)
        self.assertEqual(selected_cell, before_cell)
        self.assertEqual(headers, before_headers)
        self.assertIs(candidate["metadata"], metadata)
        self.assertIs(candidate["nested"], nested)
        self.assertIs(metadata["nested"], nested)
        self.assertIs(selected_cell["nested"], nested)
        self.assertIs(selected_cell["column_headers"], headers)

        table_section_bomb = TextBomb("table scope must stop section fallback")
        table_candidate_text_bomb = TextBomb("row text must stop candidate text")
        table_candidate = {
            "metadata": {
                "table_source_id": " table-2 ",
                "row_label": "",
                "semantic_label": " semantic-row ",
                "aggregate_label": TextBomb("semantic hit must stop aggregate label"),
                "row_text": " row fallback ",
                "period_focus": " prior ",
                "section_path": table_section_bomb,
                "statement_type": " summary_financials ",
                "nested": nested,
            },
            "text": table_candidate_text_bomb,
            "nested": nested,
        }
        with patch.object(
            financial_operand_resolution,
            "candidate_row_block_signature",
            return_value="",
        ) as empty_block_owner:
            table_logical = (
                financial_operand_resolution.candidate_direct_logical_signature(
                    table_candidate,
                    selected_cell={},
                )
            )
            table_family = (
                financial_operand_resolution.candidate_direct_family_signature(
                    table_candidate,
                    selected_cell={},
                )
            )
        self.assertEqual(
            table_logical,
            ("table-2", "semantic-row", "row fallback", "prior"),
        )
        self.assertEqual(
            table_family,
            ("table-2", "semantic-row", "", "summary_financials"),
        )
        self.assertEqual(empty_block_owner.call_args_list[0].args, (table_candidate,))
        self.assertEqual(empty_block_owner.call_args_list[1].args, (table_candidate,))
        self.assertIs(table_candidate["metadata"]["nested"], nested)
        self.assertIs(table_candidate["nested"], nested)

        section_candidate = {
            "metadata": {
                "table_source_id": "",
                "row_label": "",
                "semantic_label": "",
                "aggregate_label": " aggregate-row ",
                "row_text": "",
                "period_focus": " current ",
                "section_path": " section-scope ",
                "statement_type": " income_statement ",
                "nested": nested,
            },
            "text": " candidate fallback ",
            "nested": nested,
        }
        with patch.object(
            financial_operand_resolution,
            "candidate_row_block_signature",
            return_value="",
        ):
            self.assertEqual(
                financial_operand_resolution.candidate_direct_logical_signature(
                    section_candidate,
                    selected_cell=None,
                ),
                (
                    "section-scope",
                    "aggregate-row",
                    "candidate fallback",
                    "current",
                ),
            )
            self.assertEqual(
                financial_operand_resolution.candidate_direct_family_signature(
                    section_candidate,
                    selected_cell=None,
                ),
                ("section-scope", "aggregate-row", "", "income_statement"),
            )
        self.assertIs(section_candidate["metadata"]["nested"], nested)
        self.assertIs(section_candidate["nested"], nested)

    def test_current_source_direct_candidate_signature_projection_pins_laziness_stringification_and_exceptions(self) -> None:
        copy_events = []
        metadata_values = {
            "table_source_id": "table",
            "row_label": "row",
            "row_text": "row text",
            "period_focus": "current",
            "section_path": "section",
            "statement_type": "notes",
        }

        class MetadataMapping:
            def keys(self):
                copy_events.append("metadata-keys")
                return list(metadata_values)

            def __getitem__(self, key):
                copy_events.append(("metadata-item", key))
                return metadata_values[key]

        class CandidateMapping:
            def get(self, key, default=None):
                copy_events.append(("candidate-get", key))
                if key == "metadata":
                    return MetadataMapping()
                return default

        candidate_mapping = CandidateMapping()

        def block_after_copy(current_candidate):
            copy_events.append(("block", current_candidate is candidate_mapping))
            return "block"

        with patch.object(
            financial_operand_resolution,
            "candidate_row_block_signature",
            side_effect=block_after_copy,
        ):
            self.assertEqual(
                financial_operand_resolution.candidate_direct_logical_signature(
                    candidate_mapping,
                    selected_cell={
                        "value_text": "1",
                        "column_headers": ["2024"],
                    },
                ),
                ("block", "row", "1", "2024"),
            )
        self.assertEqual(copy_events[0], ("candidate-get", "metadata"))
        self.assertEqual(copy_events[1], "metadata-keys")
        block_index = copy_events.index(("block", True))
        metadata_item_indexes = [
            index
            for index, event in enumerate(copy_events)
            if isinstance(event, tuple) and event[0] == "metadata-item"
        ]
        self.assertEqual(len(metadata_item_indexes), len(metadata_values))
        self.assertTrue(all(index < block_index for index in metadata_item_indexes))

        class TextProbe:
            def __init__(self, name, value, events):
                self.name = name
                self.value = value
                self.events = events
                self.calls = 0

            def __str__(self):
                self.calls += 1
                self.events.append(self.name)
                return self.value

        class BoolCell(dict):
            def __init__(self, *args, events, name, **kwargs):
                super().__init__(*args, **kwargs)
                self.events = events
                self.name = name
                self.bool_calls = 0

            def __bool__(self):
                self.bool_calls += 1
                self.events.append(f"{self.name}-bool")
                return True

        logical_events = []
        logical_value = TextProbe("value", " value ", logical_events)
        logical_header = TextProbe("header", " header ", logical_events)
        logical_blank = TextProbe("blank", "   ", logical_events)
        logical_cell = BoolCell(
            {
                "value_text": logical_value,
                "column_headers": [
                    logical_header,
                    logical_blank,
                    logical_header,
                ],
            },
            events=logical_events,
            name="logical-cell",
        )
        logical_candidate = {
            "metadata": {
                "row_label": "row",
                "period_focus": TextProbe(
                    "stopped-period",
                    "period",
                    logical_events,
                ),
                "statement_type": "notes",
            }
        }
        with patch.object(
            financial_operand_resolution,
            "candidate_row_block_signature",
            return_value="block",
        ):
            self.assertEqual(
                financial_operand_resolution.candidate_direct_logical_signature(
                    logical_candidate,
                    selected_cell=logical_cell,
                ),
                ("block", "row", "value", "header header"),
            )
        self.assertEqual(logical_cell.bool_calls, 2)
        self.assertEqual(logical_value.calls, 1)
        self.assertEqual(logical_header.calls, 4)
        self.assertEqual(logical_blank.calls, 1)
        self.assertNotIn("stopped-period", logical_events)

        family_events = []
        family_header = TextProbe("family-header", " header ", family_events)
        family_blank = TextProbe("family-blank", "   ", family_events)
        family_cell = BoolCell(
            {
                "value_text": TextProbe(
                    "stopped-family-value",
                    "value",
                    family_events,
                ),
                "column_headers": [family_header, family_blank],
            },
            events=family_events,
            name="family-cell",
        )
        family_candidate = {
            "metadata": {
                "row_label": "row",
                "period_focus": TextProbe(
                    "stopped-family-period",
                    "period",
                    family_events,
                ),
                "statement_type": " statement ",
            }
        }
        with patch.object(
            financial_operand_resolution,
            "candidate_row_block_signature",
            return_value="block",
        ):
            self.assertEqual(
                financial_operand_resolution.candidate_direct_family_signature(
                    family_candidate,
                    selected_cell=family_cell,
                ),
                ("block", "row", "header", "statement"),
            )
        self.assertEqual(family_cell.bool_calls, 1)
        self.assertEqual(family_header.calls, 2)
        self.assertEqual(family_blank.calls, 1)
        self.assertNotIn("stopped-family-value", family_events)
        self.assertNotIn("stopped-family-period", family_events)

        class StringFailure:
            def __init__(self, message):
                self.message = message

            def __str__(self):
                raise RuntimeError(self.message)

        class TruthFailure:
            def __init__(self, message):
                self.message = message

            def __bool__(self):
                raise RuntimeError(self.message)

        class CandidateGetFailure:
            def get(self, key, default=None):
                raise RuntimeError(f"candidate get failed: {key}")

        stopped_block = Mock(side_effect=AssertionError("metadata failure must stop block"))
        with patch.object(
            financial_operand_resolution,
            "candidate_row_block_signature",
            stopped_block,
        ):
            with self.assertRaisesRegex(
                RuntimeError,
                "candidate get failed: metadata",
            ):
                financial_operand_resolution.candidate_direct_logical_signature(
                    CandidateGetFailure()
                )
        stopped_block.assert_not_called()

        class MetadataCopyFailure:
            def keys(self):
                raise RuntimeError("metadata copy failed")

        stopped_after_copy = Mock(
            side_effect=AssertionError("metadata copy failure must stop block")
        )
        with patch.object(
            financial_operand_resolution,
            "candidate_row_block_signature",
            stopped_after_copy,
        ):
            with self.assertRaisesRegex(RuntimeError, "metadata copy failed"):
                financial_operand_resolution.candidate_direct_family_signature(
                    {"metadata": MetadataCopyFailure()}
                )
        stopped_after_copy.assert_not_called()

        block_stopped_candidate = {
            "metadata": {
                "table_source_id": StringFailure("table source accessed"),
                "row_label": StringFailure("row label accessed"),
            }
        }
        with patch.object(
            financial_operand_resolution,
            "candidate_row_block_signature",
            side_effect=RuntimeError("block failed"),
        ):
            with self.assertRaisesRegex(RuntimeError, "block failed"):
                financial_operand_resolution.candidate_direct_logical_signature(
                    block_stopped_candidate
                )

        with patch.object(
            financial_operand_resolution,
            "candidate_row_block_signature",
            return_value="block",
        ):
            with self.assertRaisesRegex(RuntimeError, "row truth failed"):
                financial_operand_resolution.candidate_direct_family_signature(
                    {
                        "metadata": {
                            "row_label": TruthFailure("row truth failed"),
                            "semantic_label": StringFailure(
                                "semantic label accessed"
                            ),
                        }
                    }
                )

        class CellTruthFailure(dict):
            def __bool__(self):
                raise RuntimeError("cell truth failed")

        with patch.object(
            financial_operand_resolution,
            "candidate_row_block_signature",
            return_value="block",
        ):
            with self.assertRaisesRegex(RuntimeError, "cell truth failed"):
                financial_operand_resolution.candidate_direct_logical_signature(
                    {"metadata": {"row_label": "row"}},
                    selected_cell=CellTruthFailure(),
                )

        with patch.object(
            financial_operand_resolution,
            "candidate_row_block_signature",
            return_value="block",
        ):
            with self.assertRaisesRegex(RuntimeError, "value failed"):
                financial_operand_resolution.candidate_direct_logical_signature(
                    {"metadata": {"row_label": "row"}},
                    selected_cell={
                        "value_text": StringFailure("value failed"),
                        "column_headers": [
                            StringFailure("headers accessed after value failure")
                        ],
                    },
                )

        class HeaderTruthFailure:
            def __bool__(self):
                raise RuntimeError("header collection truth failed")

        with patch.object(
            financial_operand_resolution,
            "candidate_row_block_signature",
            return_value="block",
        ):
            with self.assertRaisesRegex(
                RuntimeError,
                "header collection truth failed",
            ):
                financial_operand_resolution.candidate_direct_logical_signature(
                    {
                        "metadata": {
                            "row_label": "row",
                            "period_focus": StringFailure(
                                "period accessed after header truth failure"
                            ),
                        }
                    },
                    selected_cell={
                        "value_text": "1",
                        "column_headers": HeaderTruthFailure(),
                    },
                )

        class HeaderIterationFailure:
            def __bool__(self):
                return True

            def __iter__(self):
                raise RuntimeError("header iteration failed")

        with patch.object(
            financial_operand_resolution,
            "candidate_row_block_signature",
            return_value="block",
        ):
            with self.assertRaisesRegex(RuntimeError, "header iteration failed"):
                financial_operand_resolution.candidate_direct_family_signature(
                    {"metadata": {"row_label": "row"}},
                    selected_cell={
                        "column_headers": HeaderIterationFailure(),
                    },
                )

        period_stop_section = StringFailure("section accessed after period failure")
        with patch.object(
            financial_operand_resolution,
            "candidate_row_block_signature",
            return_value="",
        ):
            with self.assertRaisesRegex(RuntimeError, "period failed"):
                financial_operand_resolution.candidate_direct_logical_signature(
                    {
                        "metadata": {
                            "row_label": "row",
                            "period_focus": StringFailure("period failed"),
                            "section_path": period_stop_section,
                        }
                    },
                    selected_cell={"value_text": "1", "column_headers": []},
                )

        with patch.object(
            financial_operand_resolution,
            "candidate_row_block_signature",
            return_value="",
        ):
            with self.assertRaisesRegex(RuntimeError, "statement failed"):
                financial_operand_resolution.candidate_direct_family_signature(
                    {
                        "metadata": {
                            "row_label": "row",
                            "statement_type": StringFailure("statement failed"),
                            "section_path": StringFailure(
                                "section accessed after statement failure"
                            ),
                        }
                    },
                    selected_cell={"column_headers": []},
                )

        with patch.object(
            financial_operand_resolution,
            "candidate_row_block_signature",
            return_value="",
        ):
            with self.assertRaisesRegex(RuntimeError, "section failed"):
                financial_operand_resolution.candidate_direct_family_signature(
                    {
                        "metadata": {
                            "row_label": "row",
                            "statement_type": "notes",
                            "section_path": StringFailure("section failed"),
                        }
                    },
                    selected_cell={"column_headers": ["2024"]},
                )

    def test_current_source_direct_candidate_signature_bindings_pin_defs_calls_dag_and_baseline(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        agent_root = repo_root / "src" / "agent"
        target_names = {
            "candidate_direct_logical_signature",
            "candidate_direct_family_signature",
        }
        block_name = "candidate_row_block_signature"
        module_paths = {path.stem: path for path in agent_root.glob("*.py")}
        module_trees = {
            name: ast.parse(path.read_text(encoding="utf-8-sig"))
            for name, path in module_paths.items()
        }
        definitions = {name: [] for name in target_names}
        selected_calls = {name: [] for name in target_names}
        block_calls = []

        class BindingVisitor(ast.NodeVisitor):
            def __init__(self, module_name):
                self.module_name = module_name
                self.function_stack = []
                self.try_depth = 0

            def visit_FunctionDef(self, node):
                if node.name in target_names:
                    definitions[node.name].append((self.module_name, node))
                self.function_stack.append(node.name)
                self.generic_visit(node)
                self.function_stack.pop()

            visit_AsyncFunctionDef = visit_FunctionDef

            def visit_Try(self, node):
                self.try_depth += 1
                self.generic_visit(node)
                self.try_depth -= 1

            visit_TryStar = visit_Try

            def visit_Call(self, node):
                called_name = node.func.id if isinstance(node.func, ast.Name) else ""
                if called_name in target_names:
                    selected_calls[called_name].append(
                        (
                            self.module_name,
                            self.function_stack[-1] if self.function_stack else "",
                            type(node.func).__name__,
                            tuple(ast.unparse(arg) for arg in node.args),
                            tuple(
                                (keyword.arg, ast.unparse(keyword.value))
                                for keyword in node.keywords
                            ),
                            self.try_depth,
                        )
                    )
                if called_name == block_name:
                    block_calls.append(
                        (
                            self.module_name,
                            self.function_stack[-1] if self.function_stack else "",
                            type(node.func).__name__,
                            tuple(ast.unparse(arg) for arg in node.args),
                            tuple(keyword.arg for keyword in node.keywords),
                            self.try_depth,
                        )
                    )
                self.generic_visit(node)

        for module_name, tree in module_trees.items():
            BindingVisitor(module_name).visit(tree)

        logical_name = "candidate_direct_logical_signature"
        family_name = "candidate_direct_family_signature"
        expected_owner = "financial_operand_resolution"
        expected_spans = {logical_name: 26, family_name: 22}
        self.assertEqual(
            {
                name: [
                    (module_name, node.end_lineno - node.lineno + 1)
                    for module_name, node in definitions[name]
                ]
                for name in target_names
            },
            {
                logical_name: [(expected_owner, 26)],
                family_name: [(expected_owner, 22)],
            },
        )
        self.assertEqual(
            {
                name: (
                    [arg.arg for arg in definitions[name][0][1].args.args],
                    [arg.arg for arg in definitions[name][0][1].args.kwonlyargs],
                    [
                        ast.unparse(default) if default is not None else None
                        for default in definitions[name][0][1].args.kw_defaults
                    ],
                    ast.unparse(definitions[name][0][1].returns),
                )
                for name in target_names
            },
            {
                logical_name: (
                    ["candidate"],
                    ["selected_cell"],
                    ["None"],
                    "tuple[str, str, str, str]",
                ),
                family_name: (
                    ["candidate"],
                    ["selected_cell"],
                    ["None"],
                    "tuple[str, str, str, str]",
                ),
            },
        )
        self.assertTrue(
            all(
                node.args.defaults == []
                and node.decorator_list == []
                and not any(
                    isinstance(item, (ast.Try, ast.TryStar))
                    for item in ast.walk(node)
                )
                for entries in definitions.values()
                for _module_name, node in entries
            )
        )

        expected_selected_calls = {
            logical_name: [
                (
                    "financial_graph_helpers",
                    "_deterministic_reconcile_task",
                    "Name",
                    ("candidate",),
                    (("selected_cell", "selected_cell"),),
                    0,
                )
            ],
            family_name: [
                (
                    "financial_graph_helpers",
                    "_deterministic_reconcile_task",
                    "Name",
                    ("candidate",),
                    (("selected_cell", "selected_cell"),),
                    0,
                )
            ],
        }
        self.assertEqual(selected_calls, expected_selected_calls)
        self.assertEqual(
            (
                sum(len(entries) for entries in selected_calls.values()),
                sum(
                    entry[0] == "financial_operand_resolution"
                    for entries in selected_calls.values()
                    for entry in entries
                ),
            ),
            (2, 0),
        )

        self.assertEqual(len(block_calls), 7)
        self.assertTrue(
            all(
                entry[2] == "Name"
                and len(entry[3]) == 1
                and entry[4] == ()
                and entry[5] == 0
                for entry in block_calls
            )
        )
        self.assertEqual(
            sorted((entry[0], entry[1]) for entry in block_calls),
            sorted(
                [
                    ("financial_operand_resolution", logical_name),
                    ("financial_operand_resolution", family_name),
                    (
                        "financial_operand_resolution",
                        "repair_note_operand_units_from_same_block",
                    ),
                    *[
                        (
                            "financial_graph_reconciliation",
                            "_extract_structured_operands_from_reconciliation",
                        )
                        for _ in range(4)
                    ],
                ]
            ),
        )
        current_owner_local = sum(
            entry[0] == "financial_operand_resolution" for entry in block_calls
        )
        self.assertEqual(
            (len(block_calls) - current_owner_local, current_owner_local),
            (4, 3),
        )

        graph_defs = [
            node
            for node in module_trees["financial_graph_helpers"].body
            if isinstance(node, ast.FunctionDef)
        ]
        operand_defs = [
            node
            for node in module_trees["financial_operand_resolution"].body
            if isinstance(node, ast.FunctionDef)
        ]
        current_graph_counts = (
            sum(not node.name.startswith("_") for node in graph_defs),
            sum(node.name.startswith("_") for node in graph_defs),
        )
        current_operand_counts = (
            sum(not node.name.startswith("_") for node in operand_defs),
            sum(node.name.startswith("_") for node in operand_defs),
        )
        self.assertEqual(current_graph_counts, (9, 97))
        self.assertEqual(current_operand_counts, (43, 37))

        def imported_names(module_name, imported_module):
            return {
                alias.name
                for node in module_trees[module_name].body
                if isinstance(node, ast.ImportFrom)
                and node.module == imported_module
                for alias in node.names
            }

        owner_module = "src.agent.financial_operand_resolution"
        graph_owner_imports = imported_names(
            "financial_graph_helpers",
            owner_module,
        )
        self.assertNotIn(block_name, graph_owner_imports)
        self.assertTrue(target_names.issubset(graph_owner_imports))
        self.assertIn(
            block_name,
            imported_names("financial_graph_reconciliation", owner_module),
        )

        edges = {name: set() for name in module_trees}
        for module_name, tree in module_trees.items():
            for node in tree.body:
                if not isinstance(node, ast.ImportFrom) or not node.module:
                    continue
                prefix = "src.agent."
                if not node.module.startswith(prefix):
                    continue
                imported = node.module[len(prefix) :]
                if imported in edges:
                    edges[module_name].add(imported)

        def reaches(start, target):
            seen = set()
            pending = list(edges[start])
            while pending:
                current = pending.pop()
                if current == target:
                    return True
                if current in seen:
                    continue
                seen.add(current)
                pending.extend(edges[current])
            return False

        self.assertTrue(
            reaches("financial_graph_helpers", "financial_operand_resolution")
        )
        self.assertTrue(
            reaches("financial_graph_reconciliation", "financial_graph_helpers")
        )
        self.assertTrue(
            reaches(
                "financial_graph_reconciliation",
                "financial_operand_resolution",
            )
        )
        self.assertFalse(
            reaches("financial_operand_resolution", "financial_graph_helpers")
        )
        self.assertFalse(
            reaches(
                "financial_operand_resolution",
                "financial_graph_reconciliation",
            )
        )

        current_test_tree = ast.parse(
            Path(__file__).read_text(encoding="utf-8-sig")
        )
        current_source_methods = {
            node.name
            for node in ast.walk(current_test_tree)
            if isinstance(node, ast.FunctionDef)
            and node.name.startswith(
                "test_current_source_direct_candidate_signature"
            )
        }
        self.assertEqual(
            current_source_methods,
            {
                "test_current_source_direct_candidate_signature_projection_pins_metadata_value_period_scope_and_identity",
                "test_current_source_direct_candidate_signature_projection_pins_laziness_stringification_and_exceptions",
                "test_current_source_direct_candidate_signature_bindings_pin_defs_calls_dag_and_baseline",
                "test_current_source_direct_candidate_signature_caller_pins_args_adoption_collapse_order_and_stop",
            },
        )

        baseline = json.loads(
            (
                repo_root
                / "tests"
                / "fixtures"
                / "runtime_domain_terms_baseline.json"
            ).read_text(encoding="utf-8-sig")
        )
        self.assertEqual(len(baseline["records"]), 218)
        selected_hits = []
        for record in baseline["records"]:
            if record.get("path") != "src/agent/financial_operand_resolution.py":
                continue
            for name in target_names:
                node = definitions[name][0][1]
                if any(
                    node.lineno <= line <= node.end_lineno
                    for line in record.get("first_lines") or []
                ):
                    selected_hits.append((name, record))
        self.assertEqual(selected_hits, [])

    def test_current_source_direct_candidate_signature_caller_pins_args_adoption_collapse_order_and_stop(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        graph_source = (
            repo_root / "src" / "agent" / "financial_graph_helpers.py"
        ).read_text(encoding="utf-8-sig")
        graph_tree = ast.parse(graph_source)
        reconcile_node = next(
            node
            for node in graph_tree.body
            if isinstance(node, ast.FunctionDef)
            and node.name == "_deterministic_reconcile_task"
        )
        reconcile_source = ast.get_source_segment(graph_source, reconcile_node) or ""
        logical_name = "candidate_direct_logical_signature"
        family_name = "candidate_direct_family_signature"
        entry_start = reconcile_source.index("direct_entries.append")
        entry_end = reconcile_source.index("collapsed_entries:", entry_start)
        entry_source = reconcile_source[entry_start:entry_end]
        entry_tokens = [
            '"candidate": candidate',
            f'"logical_signature": {logical_name}',
            f'"family_signature": {family_name}',
            '"selected_value_text": _normalise_spaces',
            '"score": _score_operand_candidate',
            '"canonical_winner": _candidate_is_canonical_statement_winner',
        ]
        entry_indexes = [entry_source.index(token) for token in entry_tokens]
        self.assertEqual(entry_indexes, sorted(entry_indexes))

        collapse_start = reconcile_source.index("collapsed_entries:", entry_start)
        collapse_end = reconcile_source.index(
            "direct_candidates =",
            collapse_start,
        )
        collapse_source = reconcile_source[collapse_start:collapse_end]
        collapse_tokens = [
            "family_signatures =",
            "distinct_values =",
            "if len(family_signatures) == 1 and len(distinct_values) <= 1",
            "best_by_signature",
            "sibling_surfaces =",
            "canonical_entries =",
            "ranked_by_priority =",
            "_direct_candidate_semantic_priority",
        ]
        collapse_indexes = [collapse_source.index(token) for token in collapse_tokens]
        self.assertEqual(collapse_indexes, sorted(collapse_indexes))

        nested = {"preserve": True}
        required_operand = {
            "label": "Metric",
            "required": True,
            "nested": nested,
        }

        class ValueProbe:
            def __init__(self, candidate_id, value, events):
                self.candidate_id = candidate_id
                self.value = value
                self.events = events
                self.calls = 0

            def __str__(self):
                self.calls += 1
                self.events.append(("value", self.candidate_id))
                return self.value

        def run_scenario(candidate_specs):
            events = []
            operand_refs = []
            signature_cells = []
            candidates = []
            cells = {}
            value_probes = {}
            for spec in candidate_specs:
                candidate = {
                    "candidate_id": spec["candidate_id"],
                    "metadata": {"nested": nested},
                    "score": spec["score"],
                    "canonical": spec["canonical"],
                    "logical": spec["logical"],
                    "family": spec["family"],
                    "nested": nested,
                }
                candidates.append(candidate)
                value_probe = ValueProbe(
                    spec["candidate_id"],
                    spec["value"],
                    events,
                )
                value_probes[spec["candidate_id"]] = value_probe
                cells[spec["candidate_id"]] = {
                    "value_text": value_probe,
                    "column_headers": ["2024"],
                    "nested": nested,
                }

            def candidate_match(candidate, operand):
                events.append(("match", candidate["candidate_id"]))
                operand_refs.append(operand)
                return True

            def score_candidate(candidate, **kwargs):
                events.append(("score", candidate["candidate_id"]))
                operand_refs.append(kwargs["operand"])
                return candidate["score"]

            def period_focus(operand, default_value="unknown"):
                events.append(("period", default_value))
                operand_refs.append(operand)
                return "current"

            def select_cell(candidate, **kwargs):
                events.append(("select", candidate["candidate_id"]))
                operand_refs.append(kwargs["operand"])
                return cells[candidate["candidate_id"]]

            def accept_candidate(candidate, **kwargs):
                events.append(("accept", candidate["candidate_id"]))
                operand_refs.append(kwargs["operand"])
                self.assertIs(
                    kwargs["selected_cell"],
                    cells[candidate["candidate_id"]],
                )
                return True

            def logical_signature(candidate, **kwargs):
                events.append(("logical", candidate["candidate_id"]))
                signature_cells.append(
                    (
                        "logical",
                        candidate,
                        kwargs["selected_cell"],
                    )
                )
                return candidate["logical"]

            def family_signature(candidate, **kwargs):
                events.append(("family", candidate["candidate_id"]))
                signature_cells.append(
                    (
                        "family",
                        candidate,
                        kwargs["selected_cell"],
                    )
                )
                return candidate["family"]

            def canonical_winner(candidate, **kwargs):
                events.append(("winner", candidate["candidate_id"]))
                operand_refs.append(kwargs["operand"])
                return candidate["canonical"]

            stopped_sibling = Mock(
                side_effect=AssertionError(
                    "selected collapse must stop sibling reranking"
                )
            )
            stopped_priority = Mock(
                side_effect=AssertionError(
                    "selected collapse must stop semantic priority"
                )
            )
            with (
                patch.object(
                    financial_graph_helpers,
                    "_candidate_matches_operand",
                    side_effect=candidate_match,
                ),
                patch.object(
                    financial_graph_helpers,
                    "_operand_segment_label",
                    return_value="",
                ),
                patch.object(
                    financial_graph_helpers,
                    "_score_operand_candidate",
                    side_effect=score_candidate,
                ),
                patch.object(
                    financial_graph_helpers,
                    "operand_period_focus",
                    side_effect=period_focus,
                ),
                patch.object(
                    financial_graph_helpers,
                    "_candidate_selected_cell_for_operand",
                    side_effect=select_cell,
                ),
                patch.object(
                    financial_graph_helpers,
                    "_candidate_satisfies_direct_acceptance_contract",
                    side_effect=accept_candidate,
                ),
                patch.object(
                    financial_graph_helpers,
                    logical_name,
                    side_effect=logical_signature,
                ),
                patch.object(
                    financial_graph_helpers,
                    family_name,
                    side_effect=family_signature,
                ),
                patch.object(
                    financial_graph_helpers,
                    "_candidate_is_canonical_statement_winner",
                    side_effect=canonical_winner,
                ),
                patch.object(
                    financial_graph_helpers,
                    "candidate_sibling_surface_hit_count",
                    stopped_sibling,
                ),
                patch.object(
                    financial_graph_helpers,
                    "_direct_candidate_semantic_priority",
                    stopped_priority,
                ),
            ):
                result = financial_graph_helpers._deterministic_reconcile_task(
                    active_subtask={
                        "task_id": "task-1",
                        "operation_family": "lookup",
                        "required_operands": [required_operand],
                    },
                    candidates=candidates,
                    years=[2024],
                    reconciliation_retry_count=1,
                )
            stopped_sibling.assert_not_called()
            stopped_priority.assert_not_called()
            projected_operand = operand_refs[0]
            self.assertIsNot(projected_operand, required_operand)
            self.assertIs(projected_operand["nested"], nested)
            self.assertTrue(
                all(current_operand is projected_operand for current_operand in operand_refs)
            )
            self.assertTrue(
                all(candidate["nested"] is nested for candidate in candidates)
            )
            self.assertTrue(
                all(cell["nested"] is nested for cell in cells.values())
            )
            for kind, candidate, current_cell in signature_cells:
                self.assertIn(kind, {"logical", "family"})
                self.assertIs(
                    current_cell,
                    cells[candidate["candidate_id"]],
                )
            return result, events, candidates, cells, value_probes

        fast_specs = [
            {
                "candidate_id": "candidate-a",
                "score": 10.0,
                "canonical": False,
                "logical": ("scope-a", "row", "100", "2024"),
                "family": ("scope", "row", "2024", "type"),
                "value": "100",
            },
            {
                "candidate_id": "candidate-b",
                "score": 5.0,
                "canonical": True,
                "logical": ("scope-b", "row", "100", "2024"),
                "family": ("scope", "row", "2024", "type"),
                "value": "100",
            },
        ]
        fast_result, fast_events, _fast_candidates, _fast_cells, fast_values = (
            run_scenario(fast_specs)
        )
        self.assertEqual(fast_result["status"], "ready")
        self.assertEqual(
            fast_result["matched_operands"][0]["candidate_ids"],
            ["candidate-b", "candidate-a"],
        )
        self.assertEqual(
            fast_events,
            [
                ("match", "candidate-a"),
                ("match", "candidate-b"),
                ("score", "candidate-a"),
                ("score", "candidate-b"),
                ("period", "unknown"),
                ("select", "candidate-a"),
                ("accept", "candidate-a"),
                ("logical", "candidate-a"),
                ("family", "candidate-a"),
                ("value", "candidate-a"),
                ("score", "candidate-a"),
                ("winner", "candidate-a"),
                ("select", "candidate-b"),
                ("accept", "candidate-b"),
                ("logical", "candidate-b"),
                ("family", "candidate-b"),
                ("value", "candidate-b"),
                ("score", "candidate-b"),
                ("winner", "candidate-b"),
            ],
        )
        self.assertEqual(
            {candidate_id: probe.calls for candidate_id, probe in fast_values.items()},
            {"candidate-a": 1, "candidate-b": 1},
        )

        logical_specs = [
            {
                "candidate_id": "candidate-a",
                "score": 10.0,
                "canonical": False,
                "logical": ("same", "row", "value", "period"),
                "family": ("family-a", "row", "2024", "type"),
                "value": "100",
            },
            {
                "candidate_id": "candidate-b",
                "score": 5.0,
                "canonical": True,
                "logical": ("same", "row", "value", "period"),
                "family": ("family-b", "row", "2024", "type"),
                "value": "200",
            },
        ]
        logical_result, logical_events, _logical_candidates, _logical_cells, _ = (
            run_scenario(logical_specs)
        )
        self.assertEqual(logical_result["status"], "ready")
        self.assertEqual(
            logical_result["matched_operands"][0]["candidate_ids"],
            ["candidate-b", "candidate-a"],
        )
        self.assertEqual(
            [event for event in logical_events if event[0] in {"logical", "family"}],
            [
                ("logical", "candidate-a"),
                ("family", "candidate-a"),
                ("logical", "candidate-b"),
                ("family", "candidate-b"),
            ],
        )

        rejected_candidate = {
            "candidate_id": "rejected",
            "metadata": {},
        }
        rejected_cell = {"value_text": "100", "column_headers": ["2024"]}
        stopped_rejected_logical = Mock(
            side_effect=AssertionError("acceptance miss must stop logical signature")
        )
        stopped_rejected_family = Mock(
            side_effect=AssertionError("acceptance miss must stop family signature")
        )
        stopped_rejected_winner = Mock(
            side_effect=AssertionError("acceptance miss must stop winner")
        )
        with (
            patch.object(
                financial_graph_helpers,
                "_candidate_matches_operand",
                return_value=True,
            ),
            patch.object(
                financial_graph_helpers,
                "_operand_segment_label",
                return_value="",
            ),
            patch.object(
                financial_graph_helpers,
                "_score_operand_candidate",
                return_value=1.0,
            ),
            patch.object(
                financial_graph_helpers,
                "operand_period_focus",
                return_value="current",
            ),
            patch.object(
                financial_graph_helpers,
                "_candidate_selected_cell_for_operand",
                return_value=rejected_cell,
            ) as rejected_selector,
            patch.object(
                financial_graph_helpers,
                "_candidate_satisfies_direct_acceptance_contract",
                return_value=False,
            ) as rejected_acceptance,
            patch.object(
                financial_graph_helpers,
                logical_name,
                stopped_rejected_logical,
            ),
            patch.object(
                financial_graph_helpers,
                family_name,
                stopped_rejected_family,
            ),
            patch.object(
                financial_graph_helpers,
                "_candidate_is_canonical_statement_winner",
                stopped_rejected_winner,
            ),
        ):
            rejected_result = financial_graph_helpers._deterministic_reconcile_task(
                active_subtask={
                    "task_id": "task-rejected",
                    "operation_family": "lookup",
                    "required_operands": [required_operand],
                },
                candidates=[rejected_candidate],
                years=[2024],
                reconciliation_retry_count=1,
            )
        self.assertEqual(rejected_result["status"], "insufficient_operands")
        rejected_selector.assert_called_once()
        rejected_acceptance.assert_called_once()
        self.assertIs(rejected_selector.call_args.args[0], rejected_candidate)
        self.assertIs(rejected_acceptance.call_args.args[0], rejected_candidate)
        self.assertIs(rejected_acceptance.call_args.kwargs["selected_cell"], rejected_cell)
        stopped_rejected_logical.assert_not_called()
        stopped_rejected_family.assert_not_called()
        stopped_rejected_winner.assert_not_called()

        class ValueFailure:
            def __str__(self):
                raise RuntimeError("selected value failed")

        def assert_entry_failure(stage):
            candidate = {"candidate_id": "failed", "metadata": {}}
            cell = {
                "value_text": ValueFailure(),
                "column_headers": ["2024"],
            }
            score_owner = Mock(return_value=1.0)
            logical_owner = Mock(
                return_value=("scope", "row", "value", "period")
            )
            family_owner = Mock(
                return_value=("scope", "row", "period", "type")
            )
            if stage == "logical":
                logical_owner.side_effect = RuntimeError("logical failed")
            elif stage == "family":
                family_owner.side_effect = RuntimeError("family failed")
            winner_owner = Mock(
                side_effect=AssertionError("entry failure must stop winner")
            )
            with (
                patch.object(
                    financial_graph_helpers,
                    "_candidate_matches_operand",
                    return_value=True,
                ),
                patch.object(
                    financial_graph_helpers,
                    "_operand_segment_label",
                    return_value="",
                ),
                patch.object(
                    financial_graph_helpers,
                    "_score_operand_candidate",
                    score_owner,
                ),
                patch.object(
                    financial_graph_helpers,
                    "operand_period_focus",
                    return_value="current",
                ),
                patch.object(
                    financial_graph_helpers,
                    "_candidate_selected_cell_for_operand",
                    return_value=cell,
                ),
                patch.object(
                    financial_graph_helpers,
                    "_candidate_satisfies_direct_acceptance_contract",
                    return_value=True,
                ),
                patch.object(
                    financial_graph_helpers,
                    logical_name,
                    logical_owner,
                ),
                patch.object(
                    financial_graph_helpers,
                    family_name,
                    family_owner,
                ),
                patch.object(
                    financial_graph_helpers,
                    "_candidate_is_canonical_statement_winner",
                    winner_owner,
                ),
            ):
                expected_message = {
                    "logical": "logical failed",
                    "family": "family failed",
                    "value": "selected value failed",
                }[stage]
                with self.assertRaisesRegex(RuntimeError, expected_message):
                    financial_graph_helpers._deterministic_reconcile_task(
                        active_subtask={
                            "task_id": "task-failed",
                            "operation_family": "lookup",
                            "required_operands": [required_operand],
                        },
                        candidates=[candidate],
                        years=[2024],
                        reconciliation_retry_count=1,
                    )
            self.assertEqual(score_owner.call_count, 1)
            logical_owner.assert_called_once_with(candidate, selected_cell=cell)
            if stage == "logical":
                family_owner.assert_not_called()
            else:
                family_owner.assert_called_once_with(candidate, selected_cell=cell)
            winner_owner.assert_not_called()

        for failure_stage in ("logical", "family", "value"):
            with self.subTest(failure_stage=failure_stage):
                assert_entry_failure(failure_stage)

    def test_current_source_query_mentions_metric_pins_collection_matching_laziness_and_exceptions(self) -> None:
        public_name = "query_mentions_metric"
        target_name = public_name
        target = getattr(financial_retrieval_hints, target_name)
        events = []
        normalization_inputs = []
        query = object()

        class ValueProbe:
            def __init__(self, name, value, *, truth=True):
                self.name = name
                self.value = value
                self.truth = truth
                self.bool_calls = 0
                self.str_calls = 0

            def __bool__(self):
                self.bool_calls += 1
                events.append((self.name, "bool"))
                return self.truth

            def __str__(self):
                self.str_calls += 1
                events.append((self.name, "str"))
                return self.value

        class IterableProbe:
            def __init__(self, name, values):
                self.name = name
                self.values = list(values)
                self.bool_calls = 0
                self.iter_calls = 0

            def __bool__(self):
                self.bool_calls += 1
                events.append((self.name, "bool"))
                return True

            def __iter__(self):
                self.iter_calls += 1
                events.append((self.name, "iter"))
                for item in self.values:
                    events.append((self.name, "yield", getattr(item, "name", item)))
                    yield item

        class MetricProbe:
            def __init__(self, values):
                self.values = values
                self.get_calls = []

            def get(self, key, default=None):
                self.get_calls.append((key, default))
                events.append(("metric", "get", key))
                return self.values.get(key, default)

        display = ValueProbe("display", "  Unmatched Display  ")
        case_miss = ValueProbe("case-miss", "alpha beta")
        matched = ValueProbe("matched", "Alpha   Beta")
        stopped_alias = ValueProbe("stopped-alias", "Alpha Beta")
        stopped_keyword = ValueProbe("stopped-keyword", "Alpha Beta")
        aliases = IterableProbe(
            "aliases",
            [case_miss, case_miss, matched, stopped_alias],
        )
        keywords = IterableProbe("keywords", [stopped_keyword])
        metric = MetricProbe(
            {
                "display_name": display,
                "aliases": aliases,
                "intent_keywords": keywords,
            }
        )
        real_normalize = financial_retrieval_hints._normalise_spaces

        def normalize(value):
            normalization_inputs.append(value)
            events.append(
                (
                    "normalize",
                    "query"
                    if value is query
                    else getattr(value, "name", value),
                )
            )
            if value is query:
                return "Alpha Beta Query"
            if isinstance(value, ValueProbe):
                return real_normalize(value.value)
            return real_normalize(value)

        original_values = dict(metric.values)
        original_alias_values = list(aliases.values)
        original_keyword_values = list(keywords.values)
        with patch.object(
            financial_retrieval_hints,
            "_normalise_spaces",
            side_effect=normalize,
        ):
            self.assertTrue(target(query, metric))

        self.assertEqual(
            metric.get_calls,
            [
                ("display_name", None),
                ("aliases", []),
                ("intent_keywords", []),
            ],
        )
        self.assertEqual(display.bool_calls, 1)
        self.assertEqual(display.str_calls, 1)
        self.assertEqual(aliases.bool_calls, 1)
        self.assertEqual(aliases.iter_calls, 1)
        self.assertEqual(keywords.bool_calls, 1)
        self.assertEqual(keywords.iter_calls, 1)
        self.assertEqual(case_miss.str_calls, 2)
        self.assertEqual(matched.str_calls, 1)
        self.assertEqual(stopped_alias.str_calls, 0)
        self.assertEqual(stopped_keyword.str_calls, 0)
        self.assertEqual(
            normalization_inputs,
            [
                query,
                "Unmatched Display",
                case_miss,
                case_miss,
                matched,
            ],
        )
        self.assertLess(
            events.index(("keywords", "yield", "stopped-keyword")),
            events.index(("normalize", "Unmatched Display")),
        )
        self.assertEqual(metric.values, original_values)
        self.assertEqual(aliases.values, original_alias_values)
        self.assertEqual(keywords.values, original_keyword_values)
        self.assertIs(metric.values["display_name"], display)
        self.assertIs(metric.values["aliases"], aliases)
        self.assertIs(metric.values["intent_keywords"], keywords)

        self.assertFalse(
            target(
                "Alpha Beta",
                {
                    "display_name": "",
                    "aliases": ["alpha beta"],
                    "intent_keywords": [],
                },
            )
        )

        class MetricBomb:
            def get(self, key, default=None):
                raise AssertionError(f"query normalization must stop metric access: {key}")

        with patch.object(
            financial_retrieval_hints,
            "_normalise_spaces",
            side_effect=RuntimeError("query normalization failed"),
        ):
            with self.assertRaisesRegex(RuntimeError, "query normalization failed"):
                target(object(), MetricBomb())

        class OrderedMetricFailure:
            def __init__(self, failure_key, failure_value):
                self.failure_key = failure_key
                self.failure_value = failure_value
                self.keys = []

            def get(self, key, default=None):
                self.keys.append(key)
                if key == self.failure_key:
                    return self.failure_value
                return []

        class StringFailure:
            def __init__(self, message):
                self.message = message

            def __str__(self):
                raise RuntimeError(self.message)

        display_failure = OrderedMetricFailure(
            "display_name",
            StringFailure("display string failed"),
        )
        with self.assertRaisesRegex(RuntimeError, "display string failed"):
            target("query", display_failure)
        self.assertEqual(display_failure.keys, ["display_name"])

        class IterationFailure:
            def __bool__(self):
                return True

            def __iter__(self):
                raise RuntimeError("alias iteration failed")

        alias_failure = OrderedMetricFailure("aliases", IterationFailure())
        with self.assertRaisesRegex(RuntimeError, "alias iteration failed"):
            target("query", alias_failure)
        self.assertEqual(alias_failure.keys, ["display_name", "aliases"])

        filter_failure_normalization_inputs = []

        def filter_failure_normalize(value):
            filter_failure_normalization_inputs.append(value)
            if value == "query":
                return "query"
            raise AssertionError("filter string failure must stop normalization")

        with patch.object(
            financial_retrieval_hints,
            "_normalise_spaces",
            side_effect=filter_failure_normalize,
        ):
            with self.assertRaisesRegex(RuntimeError, "alias string failed"):
                target(
                    "query",
                    {
                        "display_name": "",
                        "aliases": [StringFailure("alias string failed")],
                        "intent_keywords": [],
                    },
                )
        self.assertEqual(filter_failure_normalization_inputs, ["query"])

        later_string = ValueProbe("later-string", "later")

        def failed_alias_normalize(value):
            if value == "query":
                return "query"
            if value == "":
                return ""
            raise RuntimeError("alias normalization failed")

        with patch.object(
            financial_retrieval_hints,
            "_normalise_spaces",
            side_effect=failed_alias_normalize,
        ):
            with self.assertRaisesRegex(RuntimeError, "alias normalization failed"):
                target(
                    "query",
                    {
                        "display_name": "",
                        "aliases": [ValueProbe("failed-alias", "failed"), later_string],
                        "intent_keywords": [],
                    },
                )
        self.assertEqual(later_string.str_calls, 0)

        with self.assertRaises(TypeError):
            target(
                "query",
                {
                    "display_name": "",
                    "aliases": [ValueProbe("raw-alias", "query")],
                    "intent_keywords": [],
                },
            )

    def test_current_source_query_component_match_count_pins_identity_dedupe_laziness_and_exceptions(self) -> None:
        public_name = "query_component_match_count"
        target_name = public_name
        target = getattr(financial_retrieval_hints, target_name)
        events = []
        normalization_inputs = []
        query = object()

        class ValueProbe:
            def __init__(self, name, value, *, truth=True):
                self.name = name
                self.value = value
                self.truth = truth
                self.bool_calls = 0
                self.str_calls = 0

            def __bool__(self):
                self.bool_calls += 1
                events.append((self.name, "bool"))
                return self.truth

            def __str__(self):
                self.str_calls += 1
                events.append((self.name, "str"))
                return self.value

        class IterableProbe:
            def __init__(self, name, values):
                self.name = name
                self.values = list(values)
                self.iter_calls = 0

            def __bool__(self):
                events.append((self.name, "bool"))
                return True

            def __iter__(self):
                self.iter_calls += 1
                events.append((self.name, "iter"))
                for item in self.values:
                    events.append((self.name, "yield", getattr(item, "name", item)))
                    yield item

        class SpecProbe:
            def __init__(self, name, values):
                self.name = name
                self.values = values
                self.get_calls = []

            def get(self, key, default=None):
                self.get_calls.append((key, default))
                events.append((self.name, "get", key))
                return self.values.get(key, default)

        class OperandSpecsProbe:
            def __init__(self, values):
                self.values = list(values)
                self.iter_calls = 0

            def __iter__(self):
                self.iter_calls += 1
                events.append(("operand-specs", "iter"))
                yield from self.values

        first_label = ValueProbe("label-one", "  One  ")
        first_alias_miss = ValueProbe("first-alias-miss", "TARGET")
        first_keyword_match = ValueProbe("first-keyword-match", " target ")
        first_keyword_stopped = ValueProbe("first-keyword-stopped", "target")
        first_aliases = IterableProbe("first-aliases", [first_alias_miss])
        first_keywords = IterableProbe(
            "first-keywords",
            [first_keyword_match, first_keyword_stopped],
        )
        first = SpecProbe(
            "first",
            {
                "label": first_label,
                "aliases": first_aliases,
                "keywords": first_keywords,
                "concept": ValueProbe("first-concept-stopped", "Stopped"),
            },
        )

        duplicate_alias_match = ValueProbe("duplicate-alias-match", "target")
        duplicate_keyword_stopped = ValueProbe("duplicate-keyword-stopped", "target")
        duplicate_keywords = IterableProbe(
            "duplicate-keywords",
            [duplicate_keyword_stopped],
        )
        duplicate = SpecProbe(
            "duplicate",
            {
                "label": "One",
                "aliases": [duplicate_alias_match],
                "keywords": duplicate_keywords,
            },
        )

        blank_label = ValueProbe("blank-label", "ignored", truth=False)
        blank_alias_match = ValueProbe("blank-alias-match", "target")
        concept = ValueProbe("concept", " Concept ")
        fallback = SpecProbe(
            "fallback",
            {
                "label": blank_label,
                "aliases": [blank_alias_match],
                "keywords": [],
                "concept": concept,
            },
        )

        distinct_alias_match = ValueProbe("distinct-alias-match", "target")
        distinct = SpecProbe(
            "distinct",
            {
                "label": "Three",
                "aliases": [distinct_alias_match],
                "keywords": [],
            },
        )

        unmatched_alias = ValueProbe("unmatched-alias", "missing")
        unmatched_concept = ValueProbe("unmatched-concept-stopped", "Stopped")
        unmatched = SpecProbe(
            "unmatched",
            {
                "label": "Two",
                "aliases": [unmatched_alias],
                "keywords": [],
                "concept": unmatched_concept,
            },
        )
        operand_specs = OperandSpecsProbe(
            [first, duplicate, fallback, distinct, unmatched]
        )
        dedupe_inputs = []
        dedupe_iterables = []
        real_normalize = financial_retrieval_hints._normalise_spaces

        class DictOwner:
            def fromkeys(self, values):
                dedupe_iterables.append(values)
                retained = list(values)
                dedupe_inputs.append(retained)
                return dict.fromkeys(retained)

        def normalize(value):
            normalization_inputs.append(value)
            events.append(
                (
                    "normalize",
                    "query"
                    if value is query
                    else getattr(value, "name", value),
                )
            )
            if value is query:
                return "target query"
            if isinstance(value, ValueProbe):
                return real_normalize(value.value)
            return real_normalize(value)

        original_specs = list(operand_specs.values)
        original_values = [dict(spec.values) for spec in original_specs]
        with (
            patch.object(
                financial_retrieval_hints,
                "_normalise_spaces",
                side_effect=normalize,
            ),
            patch.object(
                financial_retrieval_hints,
                "dict",
                DictOwner(),
                create=True,
            ),
        ):
            self.assertEqual(target(query, operand_specs), 3)

        self.assertEqual(operand_specs.iter_calls, 1)
        self.assertEqual(
            [call[0] for call in first.get_calls],
            ["label", "aliases", "keywords"],
        )
        self.assertEqual(
            [call[0] for call in duplicate.get_calls],
            ["label", "aliases", "keywords"],
        )
        self.assertEqual(
            [call[0] for call in fallback.get_calls],
            ["label", "aliases", "keywords", "concept"],
        )
        self.assertEqual(
            [call[0] for call in distinct.get_calls],
            ["label", "aliases", "keywords"],
        )
        self.assertEqual(
            [call[0] for call in unmatched.get_calls],
            ["label", "aliases", "keywords"],
        )
        self.assertEqual(first_label.bool_calls, 1)
        self.assertEqual(first_label.str_calls, 1)
        self.assertEqual(blank_label.bool_calls, 1)
        self.assertEqual(blank_label.str_calls, 0)
        self.assertEqual(concept.bool_calls, 1)
        self.assertEqual(concept.str_calls, 1)
        self.assertEqual(first_alias_miss.str_calls, 1)
        self.assertEqual(first_keyword_match.str_calls, 1)
        self.assertEqual(first_keyword_stopped.str_calls, 0)
        self.assertEqual(duplicate_alias_match.str_calls, 1)
        self.assertEqual(duplicate_keyword_stopped.str_calls, 0)
        self.assertEqual(unmatched_concept.str_calls, 0)
        self.assertEqual(first_aliases.iter_calls, 1)
        self.assertEqual(first_keywords.iter_calls, 1)
        self.assertEqual(duplicate_keywords.iter_calls, 1)
        self.assertLess(
            events.index(("first-keywords", "yield", "first-keyword-stopped")),
            events.index(("normalize", "One")),
        )
        self.assertEqual(
            normalization_inputs,
            [
                query,
                "One",
                first_alias_miss,
                first_keyword_match,
                "One",
                duplicate_alias_match,
                blank_alias_match,
                "Three",
                distinct_alias_match,
                "Two",
                unmatched_alias,
            ],
        )
        self.assertEqual(len(dedupe_inputs), 1)
        self.assertTrue(inspect.isgenerator(dedupe_iterables[0]))
        self.assertEqual(dedupe_inputs[0], ["One", "One", "Concept", "Three"])
        self.assertEqual(operand_specs.values, original_specs)
        for spec, values in zip(original_specs, original_values):
            self.assertEqual(spec.values, values)

        class OperandIterationBomb:
            def __iter__(self):
                raise AssertionError("query normalization must stop spec iteration")

        with patch.object(
            financial_retrieval_hints,
            "_normalise_spaces",
            side_effect=RuntimeError("component query normalization failed"),
        ):
            with self.assertRaisesRegex(
                RuntimeError,
                "component query normalization failed",
            ):
                target(object(), OperandIterationBomb())

        class SpecIterationFailure:
            def __iter__(self):
                raise RuntimeError("spec iteration failed")

        with self.assertRaisesRegex(RuntimeError, "spec iteration failed"):
            target("query", SpecIterationFailure())

        class StringFailure:
            def __init__(self, message):
                self.message = message

            def __str__(self):
                raise RuntimeError(self.message)

        label_failure = SpecProbe(
            "label-failure",
            {
                "label": StringFailure("label string failed"),
                "aliases": [],
                "keywords": [],
            },
        )
        with self.assertRaisesRegex(RuntimeError, "label string failed"):
            target("query", [label_failure])
        self.assertEqual([call[0] for call in label_failure.get_calls], ["label"])

        class IterationFailure:
            def __bool__(self):
                return True

            def __iter__(self):
                raise RuntimeError("component alias iteration failed")

        alias_failure = SpecProbe(
            "alias-failure",
            {
                "label": "Label",
                "aliases": IterationFailure(),
                "keywords": [],
            },
        )
        with self.assertRaisesRegex(
            RuntimeError,
            "component alias iteration failed",
        ):
            target("query", [alias_failure])
        self.assertEqual(
            [call[0] for call in alias_failure.get_calls],
            ["label", "aliases"],
        )

        concept_failure = SpecProbe(
            "concept-failure",
            {
                "label": "",
                "aliases": ["query"],
                "keywords": [],
                "concept": StringFailure("concept string failed"),
            },
        )
        with self.assertRaisesRegex(RuntimeError, "concept string failed"):
            target("query", [concept_failure])
        self.assertEqual(
            [call[0] for call in concept_failure.get_calls],
            ["label", "aliases", "keywords", "concept"],
        )

        class ConceptBomb:
            def get(self, key, default=None):
                if key == "concept":
                    raise AssertionError("unmatched spec must not read concept")
                return {
                    "label": "",
                    "aliases": ["missing"],
                    "keywords": [],
                }.get(key, default)

        self.assertEqual(target("query", [ConceptBomb()]), 0)

        class DedupeFailure:
            def fromkeys(self, values):
                self.iterable = values
                self.values = list(values)
                raise RuntimeError("component dedupe failed")

        dedupe_failure = DedupeFailure()
        with patch.object(
            financial_retrieval_hints,
            "dict",
            dedupe_failure,
            create=True,
        ):
            with self.assertRaisesRegex(RuntimeError, "component dedupe failed"):
                target(
                    "query",
                    [{"label": "Label", "aliases": ["query"], "keywords": []}],
                )
        self.assertTrue(inspect.isgenerator(dedupe_failure.iterable))
        self.assertEqual(dedupe_failure.values, ["Label"])

        with self.assertRaises(TypeError):
            target(
                "query",
                [
                    {
                        "label": "",
                        "aliases": [ValueProbe("raw-component-alias", "query")],
                        "keywords": [],
                    }
                ],
            )

    def test_current_source_query_metric_match_bindings_pin_defs_calls_dag_and_baseline(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        agent_root = repo_root / "src" / "agent"
        public_names = {
            "query_mentions_metric",
            "query_component_match_count",
        }
        private_names = {"_" + name for name in public_names}
        current_names = set(public_names)
        module_paths = {path.stem: path for path in agent_root.glob("*.py")}
        module_trees = {
            name: ast.parse(path.read_text(encoding="utf-8-sig"))
            for name, path in module_paths.items()
        }
        definitions = {}
        calls = []

        class BindingVisitor(ast.NodeVisitor):
            def __init__(self, module_name):
                self.module_name = module_name
                self.function_stack = []
                self.ancestor_stack = []
                self.try_depth = 0

            def visit_FunctionDef(self, node):
                if node.name in current_names:
                    definitions[node.name] = (self.module_name, node)
                self.function_stack.append(node.name)
                self.ancestor_stack.append(node)
                self.generic_visit(node)
                self.ancestor_stack.pop()
                self.function_stack.pop()

            visit_AsyncFunctionDef = visit_FunctionDef

            def visit_Try(self, node):
                self.try_depth += 1
                self.ancestor_stack.append(node)
                self.generic_visit(node)
                self.ancestor_stack.pop()
                self.try_depth -= 1

            visit_TryStar = visit_Try

            def generic_visit(self, node):
                if isinstance(
                    node,
                    (ast.FunctionDef, ast.AsyncFunctionDef, ast.Try, ast.TryStar),
                ):
                    return super().generic_visit(node)
                self.ancestor_stack.append(node)
                super().generic_visit(node)
                self.ancestor_stack.pop()

            def visit_Call(self, node):
                called_name = node.func.id if isinstance(node.func, ast.Name) else ""
                if called_name in current_names:
                    if any(
                        isinstance(item, ast.ListComp)
                        for item in self.ancestor_stack
                    ):
                        context = "listcomp"
                    else:
                        context = "expression"
                        for item in reversed(self.ancestor_stack):
                            if isinstance(item, ast.Assign):
                                context = "Assign"
                                break
                            if isinstance(item, ast.If):
                                context = "If"
                                break
                    calls.append(
                        (
                            node.lineno,
                            called_name,
                            self.module_name,
                            self.function_stack[-1]
                            if self.function_stack
                            else "",
                            type(node.func).__name__,
                            tuple(ast.unparse(arg) for arg in node.args),
                            tuple(
                                (keyword.arg, ast.unparse(keyword.value))
                                for keyword in node.keywords
                            ),
                            self.try_depth,
                            context,
                        )
                    )
                self.generic_visit(node)

        for module_name, tree in module_trees.items():
            BindingVisitor(module_name).visit(tree)

        mention_name = "query_mentions_metric"
        component_name = "query_component_match_count"
        self.assertEqual(set(definitions), {mention_name, component_name})
        self.assertEqual(
            {
                name: (
                    module_name,
                    node.end_lineno - node.lineno + 1,
                    [argument.arg for argument in node.args.args],
                    ast.unparse(node.returns),
                )
                for name, (module_name, node) in definitions.items()
            },
            {
                mention_name: (
                    "financial_retrieval_hints",
                    6,
                    ["query", "metric"],
                    "bool",
                ),
                component_name: (
                    "financial_retrieval_hints",
                    14,
                    ["query", "operand_specs"],
                    "int",
                ),
            },
        )
        for _module_name, definition in definitions.values():
            self.assertEqual(definition.args.defaults, [])
            self.assertEqual(definition.args.kwonlyargs, [])
            self.assertEqual(definition.decorator_list, [])
            self.assertFalse(
                any(
                    isinstance(node, (ast.Try, ast.TryStar))
                    for node in ast.walk(definition)
                )
            )

        calls = sorted(calls)
        self.assertEqual(
            [row[1:] for row in calls],
            [
                (
                    mention_name,
                    "financial_graph_helpers",
                    "_build_semantic_numeric_plan",
                    "Name",
                    ("query", "item"),
                    (),
                    0,
                    "listcomp",
                ),
                (
                    component_name,
                    "financial_graph_helpers",
                    "_build_semantic_numeric_plan",
                    "Name",
                    ("query", "target_operand_specs"),
                    (),
                    0,
                    "Assign",
                ),
                (
                    mention_name,
                    "financial_graph_helpers",
                    "_build_semantic_numeric_plan",
                    "Name",
                    ("query", "target_metric"),
                    (),
                    0,
                    "If",
                ),
                (
                    mention_name,
                    "financial_graph_helpers",
                    "_build_semantic_numeric_plan",
                    "Name",
                    ("query", "metric"),
                    (),
                    0,
                    "If",
                ),
            ],
        )
        self.assertEqual(
            (
                len(calls),
                sum(row[2] == "financial_retrieval_hints" for row in calls),
            ),
            (4, 0),
        )

        graph_defs = [
            node
            for node in module_trees["financial_graph_helpers"].body
            if isinstance(node, ast.FunctionDef)
        ]
        owner_defs = [
            node
            for node in module_trees["financial_retrieval_hints"].body
            if isinstance(node, ast.FunctionDef)
        ]
        graph_counts = (
            sum(not node.name.startswith("_") for node in graph_defs),
            sum(node.name.startswith("_") for node in graph_defs),
        )
        owner_counts = (
            sum(not node.name.startswith("_") for node in owner_defs),
            sum(node.name.startswith("_") for node in owner_defs),
        )
        self.assertEqual(graph_counts, (9, 97))
        self.assertEqual(owner_counts, (5, 9))

        def imported_names(module_name, imported_module):
            return {
                alias.name
                for node in module_trees[module_name].body
                if isinstance(node, ast.ImportFrom)
                and node.module == imported_module
                for alias in node.names
            }

        owner_module = "src.agent.financial_retrieval_hints"
        graph_owner_imports = imported_names(
            "financial_graph_helpers",
            owner_module,
        )
        self.assertTrue(
            {
                "_infer_statement_and_section_hints",
                "_matched_ontology_concept_specs",
            }.issubset(graph_owner_imports)
        )
        self.assertTrue(public_names.issubset(graph_owner_imports))
        self.assertFalse(private_names & graph_owner_imports)
        self.assertNotIn(
            "src.agent.financial_graph_helpers",
            {
                node.module
                for node in module_trees["financial_retrieval_hints"].body
                if isinstance(node, ast.ImportFrom) and node.module
            },
        )
        self.assertTrue(
            {"Any", "Dict", "List"}.issubset(
                imported_names("financial_retrieval_hints", "typing")
            )
        )
        self.assertIn(
            "_normalise_spaces",
            imported_names(
                "financial_retrieval_hints",
                "src.agent.financial_runtime_normalization",
            ),
        )

        edges = {name: set() for name in module_trees}
        for module_name, tree in module_trees.items():
            for node in tree.body:
                if not isinstance(node, ast.ImportFrom) or not node.module:
                    continue
                prefix = "src.agent."
                if not node.module.startswith(prefix):
                    continue
                imported = node.module[len(prefix) :]
                if imported in edges:
                    edges[module_name].add(imported)

        def reaches(start, target):
            seen = set()
            pending = list(edges[start])
            while pending:
                current = pending.pop()
                if current == target:
                    return True
                if current in seen:
                    continue
                seen.add(current)
                pending.extend(edges[current])
            return False

        self.assertTrue(
            reaches("financial_graph_helpers", "financial_retrieval_hints")
        )
        self.assertFalse(
            reaches("financial_retrieval_hints", "financial_graph_helpers")
        )

        current_test_tree = ast.parse(
            Path(__file__).read_text(encoding="utf-8-sig")
        )
        current_source_methods = {
            node.name
            for node in ast.walk(current_test_tree)
            if isinstance(node, ast.FunctionDef)
            and node.name.startswith("test_current_source_query_")
            and (
                "mentions_metric" in node.name
                or "component_match_count" in node.name
                or "metric_match" in node.name
            )
        }
        self.assertEqual(
            current_source_methods,
            {
                "test_current_source_query_mentions_metric_pins_collection_matching_laziness_and_exceptions",
                "test_current_source_query_component_match_count_pins_identity_dedupe_laziness_and_exceptions",
                "test_current_source_query_metric_match_bindings_pin_defs_calls_dag_and_baseline",
                "test_current_source_query_metric_match_caller_pins_order_admission_and_stops",
            },
        )

        baseline = json.loads(
            (
                repo_root
                / "tests"
                / "fixtures"
                / "runtime_domain_terms_baseline.json"
            ).read_text(encoding="utf-8-sig")
        )
        self.assertEqual(len(baseline["records"]), 218)
        selected_hits = []
        for _name, (module_name, definition) in definitions.items():
            selected_hits.extend(
                record
                for record in baseline["records"]
                if record.get("path")
                == f"src/agent/{module_name}.py"
                and any(
                    definition.lineno <= line <= definition.end_lineno
                    for line in (record.get("first_lines") or [])
                )
            )
        self.assertEqual(selected_hits, [])

    def test_current_source_query_metric_match_caller_pins_order_admission_and_stops(self) -> None:
        mention_public_name = "query_mentions_metric"
        component_public_name = "query_component_match_count"
        mention_name = mention_public_name
        component_name = component_public_name
        query = "query"
        metrics = {
            "target": {
                "key": "target",
                "display_name": "Target",
                "formula_family": "lookup",
            },
            "alpha": {
                "key": "alpha",
                "display_name": "Alpha",
                "formula_family": "lookup",
            },
            "weak": {
                "key": "weak",
                "display_name": "Weak",
                "formula_family": "lookup",
            },
        }
        operand_specs = {
            key: [
                {
                    "label": f"{key}-operand",
                    "required": True,
                    "nested": {"owner": key},
                }
            ]
            for key in metrics
        }

        class Ontology:
            def __init__(self):
                self.calls = []

            def match_metric_families(self, actual_query, topic, intent):
                self.calls.append(
                    ("match_metric_families", actual_query, topic, intent)
                )
                return [metrics["target"], metrics["alpha"], metrics["weak"]]

            def concept_specs(self, actual_query, topic, intent):
                self.calls.append(("concept_specs", actual_query, topic, intent))
                return []

            def metric_family(self, key):
                self.calls.append(("metric_family", key))
                return metrics.get(key) or {}

            def build_operand_spec(self, key):
                self.calls.append(("build_operand_spec", key))
                return operand_specs[key]

            def statement_type_hints_for_metric(self, key):
                self.calls.append(("statement_type_hints", key))
                return []

        def run_plan(component_result):
            ontology = Ontology()
            helper_events = []
            construction_events = []

            def mention(actual_query, metric):
                self.assertEqual(actual_query, query)
                key = metric["key"]
                helper_events.append(("mention", key, metric))
                return key == "alpha"

            def component(actual_query, specs):
                self.assertEqual(actual_query, query)
                helper_events.append(("component", specs))
                return component_result

            mention_owner = Mock(side_effect=mention)
            component_owner = Mock(side_effect=component)

            def build_constraints(actual_query, report_scope, actual_ontology, key):
                self.assertEqual(actual_query, query)
                self.assertIs(actual_ontology, ontology)
                construction_events.append(("constraints", key, report_scope))
                return {"period_focus": "current"}

            def build_queries(actual_query, topic, key, actual_ontology):
                self.assertEqual((actual_query, topic), (query, "topic"))
                self.assertIs(actual_ontology, ontology)
                construction_events.append(("retrieval", key))
                return [f"retrieve:{key}"]

            def build_task_query(**kwargs):
                construction_events.append(
                    ("task-query", kwargs["metric_label"])
                )
                return f"task:{kwargs['metric_label']}"

            metric_snapshot = deepcopy(metrics)
            operand_snapshot = deepcopy(operand_specs)
            with (
                patch.object(
                    financial_graph_helpers,
                    "get_financial_ontology",
                    return_value=ontology,
                ),
                patch.object(
                    financial_graph_helpers,
                    "_infer_operation_family_from_query",
                    return_value="lookup",
                ),
                patch.object(
                    financial_graph_helpers,
                    "_build_entity_scoped_concept_specs",
                    return_value=[],
                ),
                patch.object(
                    financial_graph_helpers,
                    mention_name,
                    mention_owner,
                ),
                patch.object(
                    financial_graph_helpers,
                    component_name,
                    component_owner,
                ),
                patch.object(
                    financial_graph_helpers,
                    "_build_task_constraints",
                    side_effect=build_constraints,
                ),
                patch.object(
                    financial_graph_helpers,
                    "_build_retrieval_query_bundle",
                    side_effect=build_queries,
                ),
                patch.object(
                    financial_graph_helpers,
                    "_build_metric_task_query",
                    side_effect=build_task_query,
                ),
            ):
                plan = financial_graph_helpers._build_semantic_numeric_plan(
                    query,
                    "topic",
                    "qa",
                    {},
                    "target",
                )
            self.assertEqual(metrics, metric_snapshot)
            self.assertEqual(operand_specs, operand_snapshot)
            return (
                plan,
                ontology,
                helper_events,
                construction_events,
                mention_owner,
                component_owner,
            )

        (
            admitted_plan,
            _admitted_ontology,
            admitted_events,
            admitted_construction,
            admitted_mention,
            admitted_component,
        ) = run_plan(2)
        self.assertEqual(
            [
                (event[0], event[1] if event[0] == "mention" else "target")
                for event in admitted_events
            ],
            [
                ("mention", "target"),
                ("mention", "alpha"),
                ("mention", "weak"),
                ("component", "target"),
                ("mention", "target"),
                ("mention", "target"),
                ("mention", "alpha"),
            ],
        )
        self.assertIs(admitted_events[0][2], metrics["target"])
        self.assertIs(admitted_events[1][2], metrics["alpha"])
        self.assertIs(admitted_events[2][2], metrics["weak"])
        self.assertIs(admitted_events[3][1], operand_specs["target"])
        self.assertIs(admitted_events[4][2], metrics["target"])
        self.assertIs(admitted_events[5][2], metrics["target"])
        self.assertIs(admitted_events[6][2], metrics["alpha"])
        self.assertEqual(admitted_mention.call_count, 6)
        admitted_component.assert_called_once_with(query, operand_specs["target"])
        self.assertEqual(admitted_plan["status"], "ok")
        self.assertFalse(admitted_plan["fallback_to_general_search"])
        self.assertEqual(
            admitted_plan["planned_metric_families"],
            ["target", "alpha"],
        )
        self.assertEqual(
            [task["metric_family"] for task in admitted_plan["tasks"]],
            ["target", "alpha"],
        )
        self.assertEqual(
            [task["query"] for task in admitted_plan["tasks"]],
            ["task:Target", "task:Alpha"],
        )
        self.assertEqual(
            admitted_construction,
            [
                ("constraints", "target", {}),
                ("retrieval", "target"),
                ("task-query", "Target"),
                ("constraints", "alpha", {}),
                ("retrieval", "alpha"),
                ("task-query", "Alpha"),
            ],
        )
        self.assertNotIn("drop_weak_target:target", admitted_plan["planner_notes"])

        (
            rejected_plan,
            _rejected_ontology,
            rejected_events,
            rejected_construction,
            _rejected_mention,
            rejected_component,
        ) = run_plan(1)
        self.assertEqual(
            [
                (event[0], event[1] if event[0] == "mention" else "target")
                for event in rejected_events
            ],
            [
                ("mention", "target"),
                ("mention", "alpha"),
                ("mention", "weak"),
                ("component", "target"),
                ("mention", "target"),
                ("mention", "alpha"),
            ],
        )
        rejected_component.assert_called_once_with(query, operand_specs["target"])
        self.assertEqual(rejected_plan["planned_metric_families"], ["alpha"])
        self.assertEqual(
            [task["metric_family"] for task in rejected_plan["tasks"]],
            ["alpha"],
        )
        self.assertIn("drop_weak_target:target", rejected_plan["planner_notes"])
        self.assertEqual(
            rejected_construction,
            [
                ("constraints", "alpha", {}),
                ("retrieval", "alpha"),
                ("task-query", "Alpha"),
            ],
        )

        failure_cases = {
            "strong": (
                [RuntimeError("strong mention failed")],
                None,
                1,
                0,
            ),
            "component": (
                [False, True, False],
                RuntimeError("component match failed"),
                3,
                1,
            ),
            "target": (
                [False, True, False, RuntimeError("target mention failed")],
                2,
                4,
                1,
            ),
            "task-loop": (
                [
                    False,
                    True,
                    False,
                    False,
                    RuntimeError("task-loop mention failed"),
                ],
                2,
                5,
                1,
            ),
        }
        for (
            stage,
            (
                mention_side_effect,
                component_side_effect,
                expected_mentions,
                expected_components,
            ),
        ) in failure_cases.items():
            with self.subTest(stage=stage):
                ontology = Ontology()
                mention_owner = Mock(side_effect=mention_side_effect)
                if isinstance(component_side_effect, BaseException):
                    component_owner = Mock(side_effect=component_side_effect)
                else:
                    component_owner = Mock(return_value=component_side_effect)
                stopped_constraints = Mock(
                    side_effect=AssertionError(
                        f"{stage} matching failure must stop task construction"
                    )
                )
                with (
                    patch.object(
                        financial_graph_helpers,
                        "get_financial_ontology",
                        return_value=ontology,
                    ),
                    patch.object(
                        financial_graph_helpers,
                        "_infer_operation_family_from_query",
                        return_value="lookup",
                    ),
                    patch.object(
                        financial_graph_helpers,
                        "_build_entity_scoped_concept_specs",
                        return_value=[],
                    ),
                    patch.object(
                        financial_graph_helpers,
                        mention_name,
                        mention_owner,
                    ),
                    patch.object(
                        financial_graph_helpers,
                        component_name,
                        component_owner,
                    ),
                    patch.object(
                        financial_graph_helpers,
                        "_build_task_constraints",
                        stopped_constraints,
                    ),
                ):
                    with self.assertRaisesRegex(RuntimeError, stage):
                        financial_graph_helpers._build_semantic_numeric_plan(
                            query,
                            "topic",
                            "qa",
                            {},
                            "target",
                        )
                self.assertEqual(mention_owner.call_count, expected_mentions)
                self.assertEqual(component_owner.call_count, expected_components)
                stopped_constraints.assert_not_called()

    def test_current_source_query_period_focus_pins_precedence_laziness_defaults_and_exceptions(self) -> None:
        public_name = "query_period_focus"
        target_name = public_name
        target_owner = financial_scope_policies
        target = getattr(target_owner, target_name)
        events = []
        query = object()
        prior_match = object()
        stopped_prior = object()
        stopped_current = object()
        nested = {"preserve": True}
        real_dict = dict

        class MarkerStream:
            def __init__(self, name, values):
                self.name = name
                self.values = list(values)
                self.bool_calls = 0
                self.iter_calls = 0

            def __bool__(self):
                self.bool_calls += 1
                events.append((self.name, "bool"))
                return True

            def __iter__(self):
                self.iter_calls += 1
                events.append((self.name, "iter"))
                for value in self.values:
                    events.append((self.name, "yield", value))
                    yield value

        class NormalizedText:
            def __contains__(self, marker):
                events.append(("text", "contains", marker))
                return marker is prior_match

        class RecordingPolicyCopy(dict):
            def get(self, key, default=None):
                events.append(("policy-copy", "get", key, default))
                return super().get(key, default)

        class DictOwner:
            def __init__(self):
                self.copy_inputs = []
                self.copy_results = []
                self.fromkeys_inputs = []

            def __call__(self, value):
                events.append(("dict", "copy", value))
                self.copy_inputs.append(value)
                copied = RecordingPolicyCopy(real_dict(value))
                self.copy_results.append(copied)
                return copied

            def fromkeys(self, values):
                retained = list(values)
                events.append(("dict", "fromkeys", retained))
                self.fromkeys_inputs.append(retained)
                return real_dict.fromkeys(retained)

        prior_markers = MarkerStream("prior", [prior_match, stopped_prior])
        current_markers = MarkerStream("current", [stopped_current])
        policy = {
            "prior_markers": prior_markers,
            "current_markers": current_markers,
            "explicit_year_pattern": r"20\d{2}",
            "nested": nested,
        }
        dict_owner = DictOwner()
        normalization_inputs = []

        def normalize(value):
            normalization_inputs.append(value)
            events.append(("normalize", value))
            self.assertIs(value, query)
            return NormalizedText()

        with (
            patch.object(target_owner, "_normalise_spaces", side_effect=normalize),
            patch.object(target_owner, "PERIOD_FOCUS_POLICY", policy),
            patch.object(target_owner, "dict", dict_owner, create=True),
        ):
            self.assertEqual(target(query, "fallback"), "prior")

        self.assertEqual(normalization_inputs, [query])
        self.assertEqual(dict_owner.copy_inputs, [policy])
        self.assertIsNot(dict_owner.copy_results[0], policy)
        self.assertIs(dict_owner.copy_results[0]["nested"], nested)
        self.assertEqual(dict_owner.fromkeys_inputs, [])
        self.assertEqual(prior_markers.bool_calls, 1)
        self.assertEqual(prior_markers.iter_calls, 1)
        self.assertEqual(current_markers.bool_calls, 0)
        self.assertEqual(current_markers.iter_calls, 0)
        self.assertIn(("prior", "yield", prior_match), events)
        self.assertNotIn(("prior", "yield", stopped_prior), events)
        self.assertNotIn(("current", "yield", stopped_current), events)
        self.assertLess(
            events.index(("normalize", query)),
            events.index(("dict", "copy", policy)),
        )
        self.assertEqual(
            [event[2] for event in events if event[:2] == ("policy-copy", "get")],
            ["prior_markers"],
        )
        self.assertIs(policy["prior_markers"], prior_markers)
        self.assertIs(policy["current_markers"], current_markers)
        self.assertIs(policy["nested"], nested)

        plain_policy = {
            "prior_markers": ("prior",),
            "current_markers": ("current",),
            "explicit_year_pattern": r"20\d{2}",
        }

        class TruthyDefault:
            def __init__(self):
                self.bool_calls = 0

            def __bool__(self):
                self.bool_calls += 1
                return True

        truthy_default = TruthyDefault()
        with patch.object(target_owner, "PERIOD_FOCUS_POLICY", plain_policy):
            self.assertEqual(
                target("prior current 2024", "fallback"),
                "prior",
            )
            self.assertEqual(target("current 2024", "fallback"), "current")
            self.assertEqual(target("2024 2024", "fallback"), "current")
            self.assertIs(target("2024 2023", truthy_default), truthy_default)
            self.assertEqual(target("no marker", ""), "unknown")
            self.assertEqual(target("CURRENT 2024 2023", "fallback"), "fallback")
        self.assertEqual(truthy_default.bool_calls, 1)

        ordered_events = []

        class OrderedPolicyCopy(dict):
            def get(self, key, default=None):
                ordered_events.append(("get", key, default))
                return super().get(key, default)

        class OrderedDictOwner:
            def __call__(self, value):
                ordered_events.append(("copy", value))
                return OrderedPolicyCopy(real_dict(value))

            def fromkeys(self, values):
                ordered_events.append(("fromkeys", values))
                return real_dict.fromkeys(values)

        class ReOwner:
            def findall(self, pattern, text):
                ordered_events.append(("findall", pattern, text))
                return ["2024", "2024"]

        ordered_policy = {
            "prior_markers": (),
            "current_markers": (),
            "explicit_year_pattern": object(),
        }
        ordered_dict = OrderedDictOwner()
        with (
            patch.object(target_owner, "_normalise_spaces", return_value="normalized"),
            patch.object(target_owner, "PERIOD_FOCUS_POLICY", ordered_policy),
            patch.object(target_owner, "dict", ordered_dict, create=True),
            patch.object(target_owner, "re", ReOwner()),
        ):
            self.assertEqual(target(query, "fallback"), "current")
        self.assertEqual(
            [event[1] for event in ordered_events if event[0] == "get"],
            ["prior_markers", "current_markers", "explicit_year_pattern"],
        )
        findall_event = next(event for event in ordered_events if event[0] == "findall")
        fromkeys_event = next(event for event in ordered_events if event[0] == "fromkeys")
        self.assertEqual(findall_event[1:], (str(ordered_policy["explicit_year_pattern"]), "normalized"))
        self.assertEqual(fromkeys_event[1], ["2024", "2024"])
        self.assertLess(ordered_events.index(findall_event), ordered_events.index(fromkeys_event))

        policy_copy = Mock(side_effect=AssertionError("policy copy reached"))
        with (
            patch.object(
                target_owner,
                "_normalise_spaces",
                side_effect=RuntimeError("query normalization failed"),
            ),
            patch.object(target_owner, "dict", policy_copy, create=True),
        ):
            with self.assertRaisesRegex(RuntimeError, "query normalization failed"):
                target(object())
        policy_copy.assert_not_called()

        class IterationFailure:
            def __bool__(self):
                return True

            def __iter__(self):
                raise RuntimeError("prior marker iteration failed")

        with patch.object(
            target_owner,
            "PERIOD_FOCUS_POLICY",
            {
                "prior_markers": IterationFailure(),
                "current_markers": (),
                "explicit_year_pattern": r"20\d{2}",
            },
        ):
            with self.assertRaisesRegex(RuntimeError, "prior marker iteration failed"):
                target("query")

        class ContainsFailure:
            def __contains__(self, marker):
                raise RuntimeError("marker membership failed")

        with (
            patch.object(target_owner, "_normalise_spaces", return_value=ContainsFailure()),
            patch.object(
                target_owner,
                "PERIOD_FOCUS_POLICY",
                {
                    "prior_markers": ("marker",),
                    "current_markers": (),
                    "explicit_year_pattern": r"20\d{2}",
                },
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "marker membership failed"):
                target("query")

        class PatternStringFailure:
            def __str__(self):
                raise RuntimeError("pattern string failed")

        with patch.object(
            target_owner,
            "PERIOD_FOCUS_POLICY",
            {
                "prior_markers": (),
                "current_markers": (),
                "explicit_year_pattern": PatternStringFailure(),
            },
        ):
            with self.assertRaisesRegex(RuntimeError, "pattern string failed"):
                target("query")

        class DedupeFailure:
            def __call__(self, value):
                return real_dict(value)

            def fromkeys(self, values):
                raise RuntimeError("year dedupe failed")

        with (
            patch.object(
                target_owner,
                "PERIOD_FOCUS_POLICY",
                {
                    "prior_markers": (),
                    "current_markers": (),
                    "explicit_year_pattern": r"20\d{2}",
                },
            ),
            patch.object(target_owner, "dict", DedupeFailure(), create=True),
        ):
            with self.assertRaisesRegex(RuntimeError, "year dedupe failed"):
                target("2024")

        class DefaultBoolFailure:
            def __bool__(self):
                raise RuntimeError("default truth failed")

        with patch.object(target_owner, "PERIOD_FOCUS_POLICY", plain_policy):
            with self.assertRaisesRegex(RuntimeError, "default truth failed"):
                target("no marker", DefaultBoolFailure())

    def test_current_source_task_period_focus_from_operands_pins_role_collection_matrix_and_exceptions(self) -> None:
        public_name = "task_period_focus_from_operands"
        target_name = public_name
        target_owner = financial_scope_policies
        target = getattr(target_owner, target_name)
        events = []
        nested = {"preserve": True}

        class RoleProbe:
            def __init__(self, name, value, *, truth=True):
                self.name = name
                self.value = value
                self.truth = truth
                self.bool_calls = 0
                self.str_calls = 0

            def __bool__(self):
                self.bool_calls += 1
                events.append((self.name, "bool"))
                return self.truth

            def __str__(self):
                self.str_calls += 1
                events.append((self.name, "str"))
                return self.value

        class SpecProbe:
            def __init__(self, name, role):
                self.name = name
                self.role = role
                self.get_calls = []
                self.nested = nested

            def get(self, key, default=None):
                self.get_calls.append((key, default))
                events.append((self.name, "get", key))
                return self.role

        class OperandSpecsProbe:
            def __init__(self, values):
                self.values = list(values)
                self.iter_calls = 0

            def __iter__(self):
                self.iter_calls += 1
                events.append(("operand-specs", "iter"))
                for value in self.values:
                    events.append(("operand-specs", "yield", value.name))
                    yield value

        current = RoleProbe("current", " current_period ")
        current_duplicate = RoleProbe("current-duplicate", "current_period")
        prior = RoleProbe("prior", " prior_period ")
        extra = RoleProbe("extra", " extra ")
        blank = RoleProbe("blank", "stopped", truth=False)
        specs = OperandSpecsProbe(
            [
                SpecProbe("current-spec", current),
                SpecProbe("duplicate-spec", current_duplicate),
                SpecProbe("prior-spec", prior),
                SpecProbe("extra-spec", extra),
                SpecProbe("blank-spec", blank),
            ]
        )
        original_specs = list(specs.values)
        self.assertEqual(target("difference", specs, "fallback"), "multi_period")
        self.assertEqual(specs.iter_calls, 1)
        self.assertEqual(specs.values, original_specs)
        self.assertTrue(all(spec.nested is nested for spec in specs.values))
        for spec in specs.values[:-1]:
            self.assertEqual(spec.get_calls, [("role", None), ("role", None)])
        self.assertEqual(specs.values[-1].get_calls, [("role", None)])
        for role in (current, current_duplicate, prior, extra):
            self.assertEqual(role.bool_calls, 2)
            self.assertEqual(role.str_calls, 2)
        self.assertEqual(blank.bool_calls, 1)
        self.assertEqual(blank.str_calls, 0)
        yielded = [event[2] for event in events if event[:2] == ("operand-specs", "yield")]
        self.assertEqual(
            yielded,
            ["current-spec", "duplicate-spec", "prior-spec", "extra-spec", "blank-spec"],
        )

        cases = [
            ("lookup", [{"role": "current_period"}], "fallback", "current"),
            ("single_value", [{"role": "prior_period"}], "fallback", "prior"),
            (
                "lookup",
                [{"role": "current_period"}, {"role": "prior_period"}],
                "fallback",
                "fallback",
            ),
            (
                "difference",
                [
                    {"role": "current_period"},
                    {"role": "prior_period"},
                    {"role": "extra"},
                ],
                "fallback",
                "multi_period",
            ),
            ("growth_rate", [{"role": " current_period "}], "fallback", "current"),
            ("difference", [{"role": "prior_period"}], "fallback", "prior"),
            ("sum", [{"role": "current_period"}], "fallback", "fallback"),
            ("lookup", [{"role": "CURRENT_PERIOD"}], "fallback", "fallback"),
            ("lookup", [], "", "unknown"),
        ]
        for operation_family, operand_specs, default_value, expected in cases:
            with self.subTest(
                operation_family=operation_family,
                operand_specs=operand_specs,
            ):
                before = deepcopy(operand_specs)
                self.assertEqual(
                    target(operation_family, operand_specs, default_value),
                    expected,
                )
                self.assertEqual(operand_specs, before)

        class ChangingSpec:
            def __init__(self):
                self.calls = []
                self.values = iter((" current_period ", " prior_period "))

            def get(self, key, default=None):
                self.calls.append((key, default))
                return next(self.values)

        changing = ChangingSpec()
        self.assertEqual(target("lookup", [changing], "fallback"), "prior")
        self.assertEqual(changing.calls, [("role", None), ("role", None)])

        class SpecIterationFailure:
            def __iter__(self):
                raise RuntimeError("operand spec iteration failed")

        with self.assertRaisesRegex(RuntimeError, "operand spec iteration failed"):
            target("lookup", SpecIterationFailure(), "fallback")

        class RoleGetFailure:
            def get(self, key, default=None):
                raise RuntimeError("role get failed")

        with self.assertRaisesRegex(RuntimeError, "role get failed"):
            target("lookup", [RoleGetFailure()], "fallback")

        class RoleTruthFailure:
            def __bool__(self):
                raise RuntimeError("role truth failed")

        with self.assertRaisesRegex(RuntimeError, "role truth failed"):
            target("lookup", [{"role": RoleTruthFailure()}], "fallback")

        class RoleStringFailure:
            def __bool__(self):
                return True

            def __str__(self):
                raise RuntimeError("role string failed")

        with self.assertRaisesRegex(RuntimeError, "role string failed"):
            target("lookup", [{"role": RoleStringFailure()}], "fallback")

        class LateSpecFailure:
            def get(self, key, default=None):
                raise RuntimeError("late spec failed")

        with self.assertRaisesRegex(RuntimeError, "late spec failed"):
            target(
                "lookup",
                [{"role": "current_period"}, LateSpecFailure()],
                "fallback",
            )

        operation_specs = [SpecProbe("operation-spec", RoleProbe("operation-role", "current_period"))]
        with self.assertRaises(TypeError):
            target([], operation_specs, "fallback")
        self.assertEqual(
            operation_specs[0].get_calls,
            [("role", None), ("role", None)],
        )

        class DefaultBoolFailure:
            def __bool__(self):
                raise RuntimeError("role default truth failed")

        with self.assertRaisesRegex(RuntimeError, "role default truth failed"):
            target("lookup", [], DefaultBoolFailure())

    def test_current_source_period_focus_bindings_pin_defs_calls_dag_and_baseline(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        agent_root = repo_root / "src" / "agent"
        public_names = {
            "query_period_focus",
            "task_period_focus_from_operands",
        }
        private_names = {
            "_infer_period_focus",
            "_task_period_focus_from_operands",
        }
        current_names = set(public_names)
        module_paths = {path.stem: path for path in agent_root.glob("*.py")}
        module_trees = {
            name: ast.parse(path.read_text(encoding="utf-8-sig"))
            for name, path in module_paths.items()
        }
        definitions = {}
        calls = []

        class BindingVisitor(ast.NodeVisitor):
            def __init__(self, module_name):
                self.module_name = module_name
                self.function_stack = []
                self.ancestor_stack = []
                self.try_depth = 0

            def visit_FunctionDef(self, node):
                if node.name in current_names:
                    definitions[node.name] = (self.module_name, node)
                self.function_stack.append(node.name)
                self.ancestor_stack.append(node)
                self.generic_visit(node)
                self.ancestor_stack.pop()
                self.function_stack.pop()

            visit_AsyncFunctionDef = visit_FunctionDef

            def visit_Try(self, node):
                self.try_depth += 1
                self.ancestor_stack.append(node)
                self.generic_visit(node)
                self.ancestor_stack.pop()
                self.try_depth -= 1

            visit_TryStar = visit_Try

            def generic_visit(self, node):
                if isinstance(
                    node,
                    (ast.FunctionDef, ast.AsyncFunctionDef, ast.Try, ast.TryStar),
                ):
                    return super().generic_visit(node)
                self.ancestor_stack.append(node)
                super().generic_visit(node)
                self.ancestor_stack.pop()

            def visit_Call(self, node):
                called_name = node.func.id if isinstance(node.func, ast.Name) else ""
                if called_name in current_names:
                    context = "expression"
                    for item in reversed(self.ancestor_stack):
                        if isinstance(item, ast.Assign):
                            context = "Assign"
                            break
                        if isinstance(item, ast.Dict):
                            context = "Dict"
                            break
                        if isinstance(item, ast.If):
                            context = "If"
                            break
                    calls.append(
                        (
                            node.lineno,
                            called_name,
                            self.module_name,
                            self.function_stack[-1] if self.function_stack else "",
                            type(node.func).__name__,
                            tuple(ast.unparse(arg) for arg in node.args),
                            tuple(
                                (keyword.arg, ast.unparse(keyword.value))
                                for keyword in node.keywords
                            ),
                            self.try_depth,
                            context,
                        )
                    )
                self.generic_visit(node)

        for module_name, tree in module_trees.items():
            BindingVisitor(module_name).visit(tree)

        query_name = "query_period_focus"
        task_name = "task_period_focus_from_operands"
        self.assertEqual(set(definitions), {query_name, task_name})
        self.assertEqual(
            {
                name: (
                    module_name,
                    node.end_lineno - node.lineno + 1,
                    [argument.arg for argument in node.args.args],
                    [ast.unparse(default) for default in node.args.defaults],
                    ast.unparse(node.returns),
                )
                for name, (module_name, node) in definitions.items()
            },
            {
                query_name: (
                    "financial_scope_policies",
                    11,
                    ["query", "default_value"],
                    ["'unknown'"],
                    "str",
                ),
                task_name: (
                    "financial_scope_policies",
                    25,
                    ["operation_family", "operand_specs", "default_value"],
                    [],
                    "str",
                ),
            },
        )
        for _module_name, definition in definitions.values():
            self.assertEqual(definition.args.kwonlyargs, [])
            self.assertEqual(definition.decorator_list, [])
            self.assertFalse(
                any(
                    isinstance(node, (ast.Try, ast.TryStar))
                    for node in ast.walk(definition)
                )
            )

        calls = sorted(calls)
        self.assertEqual(
            [row[1:] for row in calls],
            [
                (
                    query_name,
                    "financial_graph_helpers",
                    "build_hybrid_narrative_subtask",
                    "Name",
                    ("query", "'unknown'"),
                    (),
                    0,
                    "Assign",
                ),
                (
                    query_name,
                    "financial_graph_helpers",
                    "_build_concept_task_constraints",
                    "Name",
                    (
                        "query",
                        "str(defaults.get('period_focus') or 'unknown')",
                    ),
                    (),
                    0,
                    "Assign",
                ),
                (
                    task_name,
                    "financial_graph_helpers",
                    "_build_concept_task_constraints",
                    "Name",
                    ("operation_family", "operand_specs", "period_focus"),
                    (),
                    0,
                    "Assign",
                ),
                (
                    query_name,
                    "financial_graph_helpers",
                    "_build_heuristic_numeric_task",
                    "Name",
                    ("query", "'unknown'"),
                    (),
                    0,
                    "Dict",
                ),
                (
                    task_name,
                    "financial_graph_helpers",
                    "_build_heuristic_numeric_task",
                    "Name",
                    (
                        "operation_family",
                        "operand_specs",
                        "str(constraints.get('period_focus') or 'unknown')",
                    ),
                    (),
                    0,
                    "Assign",
                ),
                (
                    query_name,
                    "financial_graph_helpers",
                    "_build_task_constraints",
                    "Name",
                    (
                        "query",
                        "str(defaults.get('period_focus') or 'unknown')",
                    ),
                    (),
                    0,
                    "Assign",
                ),
            ],
        )
        self.assertEqual(
            (
                len(calls),
                sum(row[2] == "financial_scope_policies" for row in calls),
            ),
            (6, 0),
        )

        graph_defs = [
            node
            for node in module_trees["financial_graph_helpers"].body
            if isinstance(node, ast.FunctionDef)
        ]
        owner_defs = [
            node
            for node in module_trees["financial_scope_policies"].body
            if isinstance(node, ast.FunctionDef)
        ]
        graph_counts = (
            sum(not node.name.startswith("_") for node in graph_defs),
            sum(node.name.startswith("_") for node in graph_defs),
        )
        owner_counts = (
            sum(not node.name.startswith("_") for node in owner_defs),
            sum(node.name.startswith("_") for node in owner_defs),
        )
        self.assertEqual(graph_counts, (9, 97))
        self.assertEqual(owner_counts, (9, 9))

        def imported_names(module_name, imported_module):
            return {
                alias.name
                for node in module_trees[module_name].body
                if isinstance(node, ast.ImportFrom)
                and node.module == imported_module
                for alias in node.names
            }

        owner_module = "src.agent.financial_scope_policies"
        graph_owner_imports = imported_names(
            "financial_graph_helpers",
            owner_module,
        )
        self.assertTrue(
            {
                "_desired_consolidation_scope",
                "operand_period_focus",
            }.issubset(graph_owner_imports)
        )
        self.assertTrue(public_names.issubset(graph_owner_imports))
        self.assertFalse(private_names & graph_owner_imports)
        self.assertNotIn(
            "src.agent.financial_graph_helpers",
            {
                node.module
                for node in module_trees["financial_scope_policies"].body
                if isinstance(node, ast.ImportFrom) and node.module
            },
        )
        self.assertTrue(
            {"Any", "Dict", "List"}.issubset(
                imported_names("financial_scope_policies", "typing")
            )
        )
        self.assertIn(
            "PERIOD_FOCUS_POLICY",
            imported_names(
                "financial_scope_policies",
                "src.config.retrieval_policy",
            ),
        )
        self.assertIn(
            "_normalise_spaces",
            imported_names(
                "financial_scope_policies",
                "src.agent.financial_runtime_normalization",
            ),
        )
        self.assertTrue(
            any(
                isinstance(node, ast.Import)
                and any(alias.name == "re" for alias in node.names)
                for node in module_trees["financial_scope_policies"].body
            )
        )

        edges = {name: set() for name in module_trees}
        for module_name, tree in module_trees.items():
            for node in tree.body:
                if not isinstance(node, ast.ImportFrom) or not node.module:
                    continue
                prefix = "src.agent."
                if not node.module.startswith(prefix):
                    continue
                imported = node.module[len(prefix) :]
                if imported in edges:
                    edges[module_name].add(imported)

        def reaches(start, target):
            seen = set()
            pending = list(edges[start])
            while pending:
                current = pending.pop()
                if current == target:
                    return True
                if current in seen:
                    continue
                seen.add(current)
                pending.extend(edges[current])
            return False

        self.assertTrue(reaches("financial_graph_helpers", "financial_scope_policies"))
        self.assertFalse(reaches("financial_scope_policies", "financial_graph_helpers"))

        current_test_tree = ast.parse(
            Path(__file__).read_text(encoding="utf-8-sig")
        )
        current_source_methods = {
            node.name
            for node in ast.walk(current_test_tree)
            if isinstance(node, ast.FunctionDef)
            and node.name.startswith("test_current_source_")
            and (
                "query_period_focus" in node.name
                or "task_period_focus_from_operands" in node.name
                or "period_focus_bindings" in node.name
                or "period_focus_callers" in node.name
            )
        }
        self.assertEqual(
            current_source_methods,
            {
                "test_current_source_query_period_focus_pins_precedence_laziness_defaults_and_exceptions",
                "test_current_source_task_period_focus_from_operands_pins_role_collection_matrix_and_exceptions",
                "test_current_source_period_focus_bindings_pin_defs_calls_dag_and_baseline",
                "test_current_source_period_focus_callers_pin_order_adoption_and_stops",
            },
        )

        baseline = json.loads(
            (
                repo_root
                / "tests"
                / "fixtures"
                / "runtime_domain_terms_baseline.json"
            ).read_text(encoding="utf-8-sig")
        )
        self.assertEqual(len(baseline["records"]), 218)
        selected_hits = []
        for _name, (module_name, definition) in definitions.items():
            selected_hits.extend(
                record
                for record in baseline["records"]
                if record.get("path") == f"src/agent/{module_name}.py"
                and any(
                    definition.lineno <= line <= definition.end_lineno
                    for line in (record.get("first_lines") or [])
                )
            )
        self.assertEqual(selected_hits, [])

    def test_current_source_period_focus_callers_pin_order_adoption_and_stops(self) -> None:
        query_public_name = "query_period_focus"
        task_public_name = "task_period_focus_from_operands"
        query_name = query_public_name
        task_name = task_public_name
        query = "query"
        nested = {"preserve": True}
        report_scope = {"company": "Example", "nested": nested}

        hybrid_events = []

        def hybrid_scope(actual_query, actual_scope):
            self.assertEqual(actual_query, query)
            self.assertIs(actual_scope, report_scope)
            hybrid_events.append("scope")
            return "consolidated"

        def hybrid_period(actual_query, default_value):
            self.assertEqual((actual_query, default_value), (query, "unknown"))
            hybrid_events.append("query-period")
            return "current"

        def hybrid_policies(actual_query):
            self.assertEqual(actual_query, query)
            hybrid_events.append("policies")
            return []

        before_scope = deepcopy(report_scope)
        with (
            patch.object(
                financial_graph_helpers,
                "_desired_consolidation_scope",
                side_effect=hybrid_scope,
            ),
            patch.object(
                financial_graph_helpers,
                query_name,
                side_effect=hybrid_period,
            ),
            patch.object(
                financial_graph_helpers,
                "active_narrative_policies",
                side_effect=hybrid_policies,
            ),
            patch.object(financial_graph_helpers, "narrative_policy_slot_groups", return_value=[]),
            patch.object(financial_graph_helpers, "default_format_preference", return_value="paragraph"),
            patch.object(financial_graph_helpers, "narrative_policy_query_suffixes", return_value=[]),
            patch.object(financial_graph_helpers, "narrative_policy_preferred_sections", return_value=[]),
            patch.object(financial_graph_helpers, "PLANNING_POLICY", {}),
            patch.object(financial_graph_helpers, "NARRATIVE_BASE_RETRIEVAL_SUFFIXES", ()),
        ):
            hybrid = financial_graph_helpers.build_hybrid_narrative_subtask(
                query=query,
                intent="qa",
                report_scope=report_scope,
                next_task_id="task_1",
            )
        self.assertEqual(hybrid_events, ["scope", "query-period", "policies"])
        self.assertEqual(hybrid["constraints"]["period_focus"], "current")
        self.assertEqual(report_scope, before_scope)
        self.assertIs(report_scope["nested"], nested)

        stopped_policies = Mock(side_effect=AssertionError("period failure must stop policies"))
        with (
            patch.object(financial_graph_helpers, "_desired_consolidation_scope", return_value="unknown"),
            patch.object(
                financial_graph_helpers,
                query_name,
                side_effect=RuntimeError("hybrid query period failed"),
            ),
            patch.object(financial_graph_helpers, "active_narrative_policies", stopped_policies),
        ):
            with self.assertRaisesRegex(RuntimeError, "hybrid query period failed"):
                financial_graph_helpers.build_hybrid_narrative_subtask(
                    query=query,
                    intent="qa",
                    report_scope=report_scope,
                    next_task_id="task_1",
                )
        stopped_policies.assert_not_called()

        class Ontology:
            planner_guidance = {
                "dimension_defaults": {
                    "consolidation_scope": "default-scope",
                    "period_focus": "default-period",
                    "entity_scope": "default-entity",
                }
            }

            def __init__(self):
                self.default_calls = []

            def default_constraints_for_metric(self, metric_key):
                self.default_calls.append(metric_key)
                return {
                    "period_focus": "ontology-period",
                    "entity_scope": "entity",
                    "segment_scope": "segment",
                    "nested": nested,
                }

        ontology = Ontology()
        operand_specs = [{"role": "current_period", "nested": nested}]
        before_operands = deepcopy(operand_specs)
        concept_events = []

        def concept_scope(actual_query, actual_scope):
            concept_events.append("scope")
            self.assertEqual(actual_query, query)
            self.assertIs(actual_scope, report_scope)
            return "unknown"

        def concept_query_period(actual_query, default_value):
            concept_events.append(("query-period", default_value))
            return "prior"

        def concept_task_period(operation_family, actual_specs, default_value):
            concept_events.append(("task-period", operation_family, default_value))
            self.assertIs(actual_specs, operand_specs)
            return "multi_period"

        with (
            patch.object(financial_graph_helpers, "_desired_consolidation_scope", side_effect=concept_scope),
            patch.object(financial_graph_helpers, query_name, side_effect=concept_query_period),
            patch.object(financial_graph_helpers, task_name, side_effect=concept_task_period),
            patch.object(financial_graph_helpers, "TASK_CONSTRAINT_POLICY", {"segment_markers": ()}),
        ):
            concept = financial_graph_helpers._build_concept_task_constraints(
                query,
                report_scope,
                ontology,
                operand_specs,
                "growth_rate",
            )
        self.assertEqual(
            concept_events,
            [
                "scope",
                ("query-period", "default-period"),
                ("task-period", "growth_rate", "prior"),
            ],
        )
        self.assertEqual(concept["period_focus"], "multi_period")
        self.assertEqual(concept["consolidation_scope"], "default-scope")
        self.assertEqual(operand_specs, before_operands)
        self.assertIs(operand_specs[0]["nested"], nested)

        skipped_task_period = Mock(side_effect=AssertionError("falsey specs must skip role refinement"))
        with (
            patch.object(financial_graph_helpers, "_desired_consolidation_scope", return_value="separate"),
            patch.object(financial_graph_helpers, query_name, return_value="current"),
            patch.object(financial_graph_helpers, task_name, skipped_task_period),
            patch.object(financial_graph_helpers, "TASK_CONSTRAINT_POLICY", {"segment_markers": ()}),
        ):
            empty_concept = financial_graph_helpers._build_concept_task_constraints(
                query,
                report_scope,
                ontology,
                [],
                "lookup",
            )
        self.assertEqual(empty_concept["period_focus"], "current")
        skipped_task_period.assert_not_called()

        stopped_task = Mock(side_effect=AssertionError("query-period failure must stop role refinement"))
        stopped_normalize = Mock(side_effect=AssertionError("query-period failure must stop segment policy"))
        with (
            patch.object(financial_graph_helpers, "_desired_consolidation_scope", return_value="unknown"),
            patch.object(
                financial_graph_helpers,
                query_name,
                side_effect=RuntimeError("concept query period failed"),
            ),
            patch.object(financial_graph_helpers, task_name, stopped_task),
            patch.object(financial_graph_helpers, "_normalise_spaces", stopped_normalize),
        ):
            with self.assertRaisesRegex(RuntimeError, "concept query period failed"):
                financial_graph_helpers._build_concept_task_constraints(
                    query,
                    report_scope,
                    ontology,
                    operand_specs,
                    "growth_rate",
                )
        stopped_task.assert_not_called()
        stopped_normalize.assert_not_called()

        stopped_normalize = Mock(side_effect=AssertionError("role failure must stop segment policy"))
        with (
            patch.object(financial_graph_helpers, "_desired_consolidation_scope", return_value="unknown"),
            patch.object(financial_graph_helpers, query_name, return_value="prior"),
            patch.object(
                financial_graph_helpers,
                task_name,
                side_effect=RuntimeError("concept task period failed"),
            ),
            patch.object(financial_graph_helpers, "_normalise_spaces", stopped_normalize),
        ):
            with self.assertRaisesRegex(RuntimeError, "concept task period failed"):
                financial_graph_helpers._build_concept_task_constraints(
                    query,
                    report_scope,
                    ontology,
                    operand_specs,
                    "growth_rate",
                )
        stopped_normalize.assert_not_called()

        heuristic_events = []
        heuristic_specs = [{"role": "current_period", "nested": nested}]
        before_heuristic_specs = deepcopy(heuristic_specs)

        def heuristic_query_period(actual_query, default_value):
            heuristic_events.append(("query-period", default_value))
            return "prior"

        def heuristic_task_period(operation_family, actual_specs, default_value):
            heuristic_events.append(("task-period", operation_family, default_value))
            self.assertIs(actual_specs, heuristic_specs)
            return "multi_period"

        def heuristic_retrieval(**kwargs):
            heuristic_events.append(("retrieval", kwargs["constraints"]["period_focus"]))
            self.assertIs(kwargs["operand_specs"], heuristic_specs)
            return ["retrieve"]

        with (
            patch.object(financial_graph_helpers, "_infer_generic_metric_label", return_value="metric"),
            patch.object(financial_graph_helpers, "_build_generic_required_operands", return_value=heuristic_specs),
            patch.object(financial_graph_helpers, "_infer_statement_and_section_hints", return_value=([], [])),
            patch.object(financial_graph_helpers, "_infer_operation_family_from_query", return_value="growth_rate"),
            patch.object(financial_graph_helpers, "get_financial_ontology", return_value=ontology),
            patch.object(financial_graph_helpers, "_desired_consolidation_scope", return_value="consolidated"),
            patch.object(financial_graph_helpers, query_name, side_effect=heuristic_query_period),
            patch.object(financial_graph_helpers, task_name, side_effect=heuristic_task_period),
            patch.object(financial_graph_helpers, "_build_generic_retrieval_queries", side_effect=heuristic_retrieval),
            patch.object(financial_graph_helpers, "TASK_CONSTRAINT_POLICY", {"segment_markers": ()}),
        ):
            heuristic = financial_graph_helpers._build_heuristic_numeric_task(
                query=query,
                topic="topic",
                intent="comparison",
                report_scope=report_scope,
            )
        self.assertEqual(
            heuristic_events,
            [
                ("query-period", "unknown"),
                ("task-period", "growth_rate", "prior"),
                ("retrieval", "multi_period"),
            ],
        )
        self.assertEqual(heuristic["constraints"]["period_focus"], "multi_period")
        self.assertEqual(heuristic_specs, before_heuristic_specs)
        self.assertIs(heuristic_specs[0]["nested"], nested)

        stopped_task = Mock(side_effect=AssertionError("heuristic query failure must stop role refinement"))
        stopped_retrieval = Mock(side_effect=AssertionError("heuristic query failure must stop retrieval"))
        with (
            patch.object(financial_graph_helpers, "_infer_generic_metric_label", return_value="metric"),
            patch.object(financial_graph_helpers, "_build_generic_required_operands", return_value=[]),
            patch.object(financial_graph_helpers, "_infer_statement_and_section_hints", return_value=([], [])),
            patch.object(financial_graph_helpers, "_infer_operation_family_from_query", return_value="lookup"),
            patch.object(financial_graph_helpers, "get_financial_ontology", return_value=ontology),
            patch.object(financial_graph_helpers, "_desired_consolidation_scope", return_value="unknown"),
            patch.object(
                financial_graph_helpers,
                query_name,
                side_effect=RuntimeError("heuristic query period failed"),
            ),
            patch.object(financial_graph_helpers, task_name, stopped_task),
            patch.object(financial_graph_helpers, "_build_generic_retrieval_queries", stopped_retrieval),
            patch.object(financial_graph_helpers, "TASK_CONSTRAINT_POLICY", {"segment_markers": ()}),
        ):
            with self.assertRaisesRegex(RuntimeError, "heuristic query period failed"):
                financial_graph_helpers._build_heuristic_numeric_task(
                    query=query,
                    topic="topic",
                    intent="comparison",
                    report_scope=report_scope,
                )
        stopped_task.assert_not_called()
        stopped_retrieval.assert_not_called()

        stopped_retrieval = Mock(side_effect=AssertionError("role failure must stop retrieval"))
        with (
            patch.object(financial_graph_helpers, "_infer_generic_metric_label", return_value="metric"),
            patch.object(financial_graph_helpers, "_build_generic_required_operands", return_value=[]),
            patch.object(financial_graph_helpers, "_infer_statement_and_section_hints", return_value=([], [])),
            patch.object(financial_graph_helpers, "_infer_operation_family_from_query", return_value="lookup"),
            patch.object(financial_graph_helpers, "get_financial_ontology", return_value=ontology),
            patch.object(financial_graph_helpers, "_desired_consolidation_scope", return_value="unknown"),
            patch.object(financial_graph_helpers, query_name, return_value="current"),
            patch.object(
                financial_graph_helpers,
                task_name,
                side_effect=RuntimeError("heuristic task period failed"),
            ),
            patch.object(financial_graph_helpers, "_build_generic_retrieval_queries", stopped_retrieval),
            patch.object(financial_graph_helpers, "TASK_CONSTRAINT_POLICY", {"segment_markers": ()}),
        ):
            with self.assertRaisesRegex(RuntimeError, "heuristic task period failed"):
                financial_graph_helpers._build_heuristic_numeric_task(
                    query=query,
                    topic="topic",
                    intent="comparison",
                    report_scope=report_scope,
                )
        stopped_retrieval.assert_not_called()

        task_events = []
        metric_ontology = Ontology()

        def metric_scope(actual_query, actual_scope):
            task_events.append(("scope", actual_query))
            self.assertIs(actual_scope, report_scope)
            return "separate"

        def metric_period(actual_query, default_value):
            task_events.append(("query-period", default_value))
            return "prior"

        with (
            patch.object(financial_graph_helpers, "_desired_consolidation_scope", side_effect=metric_scope),
            patch.object(financial_graph_helpers, query_name, side_effect=metric_period),
        ):
            metric_constraints = financial_graph_helpers._build_task_constraints(
                query,
                report_scope,
                metric_ontology,
                "metric",
            )
        self.assertEqual(metric_ontology.default_calls, ["metric"])
        self.assertEqual(
            task_events,
            [("scope", query), ("query-period", "ontology-period")],
        )
        self.assertEqual(
            metric_constraints,
            {
                "consolidation_scope": "separate",
                "period_focus": "prior",
                "entity_scope": "entity",
                "segment_scope": "segment",
            },
        )

        class OutputStringBomb:
            def __init__(self):
                self.str_calls = 0

            def __str__(self):
                self.str_calls += 1
                raise AssertionError("query-period failure must stop output projection")

        output_bomb = OutputStringBomb()

        class FailingMetricOntology:
            def default_constraints_for_metric(self, metric_key):
                return {
                    "period_focus": "ontology-period",
                    "entity_scope": output_bomb,
                    "segment_scope": "none",
                }

        with (
            patch.object(financial_graph_helpers, "_desired_consolidation_scope", return_value="unknown"),
            patch.object(
                financial_graph_helpers,
                query_name,
                side_effect=RuntimeError("metric query period failed"),
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "metric query period failed"):
                financial_graph_helpers._build_task_constraints(
                    query,
                    report_scope,
                    FailingMetricOntology(),
                    "metric",
                )
        self.assertEqual(output_bomb.str_calls, 0)

    def test_current_source_candidate_sibling_surface_hit_count_pins_projection_dedupe_compaction_and_identity(self) -> None:
        target_name = "candidate_sibling_surface_hit_count"
        target = getattr(financial_row_surfaces, target_name)

        class CandidateBomb:
            def get(self, key, default=None):
                raise AssertionError(f"empty sibling list must stop candidate access: {key}")

        class TruthTrackedList(list):
            def __init__(self, *args):
                super().__init__(*args)
                self.bool_calls = 0

            def __bool__(self):
                self.bool_calls += 1
                return super().__len__() > 0

        empty_surfaces = TruthTrackedList()
        self.assertEqual(target(CandidateBomb(), empty_surfaces), 0)
        self.assertEqual(empty_surfaces.bool_calls, 1)

        nested = {"preserve": True}
        metadata = {
            "table_row_labels_text": " 2024 Revenue Total ",
            "table_value_labels_text": "North Segment",
            "table_summary_text": "Alpha   Beta",
            "row_context_text": "",
            "row_text": "Detail Surface",
            "nested": nested,
        }
        candidate = {
            "candidate_id": "candidate-1",
            "metadata": metadata,
            "text": "Tail Surface",
            "nested": nested,
        }
        sibling_surfaces = TruthTrackedList(
            [
                "Revenue Total",
                " Revenue   Total ",
                "2023 Revenue Total",
                "NorthSegment",
                "Alpha Beta",
                "AlphaBeta",
                "revenue total",
                "",
                "Revenue Total",
            ]
        )
        before_candidate = deepcopy(candidate)
        before_metadata = deepcopy(metadata)
        before_surfaces = list(sibling_surfaces)
        copy_inputs = []
        copy_results = []
        dedupe_inputs = []
        normalization_inputs = []
        strip_inputs = []
        real_normalize = financial_row_surfaces._normalise_spaces
        real_strip = financial_row_surfaces._strip_leading_period_qualifiers

        class DictOwner:
            def __call__(self, value):
                copy_inputs.append(value)
                copied = dict(value)
                copy_results.append(copied)
                return copied

            def fromkeys(self, values):
                dedupe_inputs.append(values)
                return dict.fromkeys(values)

        def normalize(value):
            normalization_inputs.append(value)
            return real_normalize(value)

        def strip(value):
            strip_inputs.append(value)
            return real_strip(value)

        with (
            patch.object(financial_row_surfaces, "dict", DictOwner(), create=True),
            patch.object(
                financial_row_surfaces,
                "_normalise_spaces",
                side_effect=normalize,
            ),
            patch.object(
                financial_row_surfaces,
                "_strip_leading_period_qualifiers",
                side_effect=strip,
            ),
        ):
            hit_count = target(candidate, sibling_surfaces)

        self.assertEqual(hit_count, 6)
        self.assertEqual(sibling_surfaces.bool_calls, 1)
        self.assertEqual(copy_inputs, [metadata])
        self.assertIsNot(copy_results[0], metadata)
        self.assertIs(copy_results[0]["nested"], nested)
        self.assertEqual(dedupe_inputs, [sibling_surfaces])
        self.assertIs(dedupe_inputs[0], sibling_surfaces)
        self.assertEqual(len(normalization_inputs), 17)
        haystack_input = normalization_inputs[0]
        haystack_tokens = [
            "Revenue Total",
            "North Segment",
            "Alpha   Beta",
            "Detail Surface",
            "Tail Surface",
        ]
        token_indexes = [haystack_input.index(token) for token in haystack_tokens]
        self.assertEqual(token_indexes, sorted(token_indexes))
        self.assertEqual(
            normalization_inputs[1::2],
            [
                "Revenue Total",
                " Revenue   Total ",
                "2023 Revenue Total",
                "NorthSegment",
                "Alpha Beta",
                "AlphaBeta",
                "revenue total",
                "",
            ],
        )
        self.assertEqual(
            strip_inputs,
            [
                "Revenue Total",
                "Revenue Total",
                "2023 Revenue Total",
                "NorthSegment",
                "Alpha Beta",
                "AlphaBeta",
                "revenue total",
                "",
            ],
        )
        self.assertEqual(normalization_inputs[2::2], strip_inputs)
        self.assertEqual(candidate, before_candidate)
        self.assertEqual(metadata, before_metadata)
        self.assertEqual(list(sibling_surfaces), before_surfaces)
        self.assertIs(candidate["metadata"], metadata)
        self.assertIs(candidate["metadata"]["nested"], nested)
        self.assertIs(candidate["nested"], nested)

        class IterationBombList(list):
            def __iter__(self):
                raise AssertionError("empty haystack must stop sibling iteration")

        stopped_regex = Mock(
            side_effect=AssertionError("empty haystack must stop regex compaction")
        )
        regex_owner = SimpleNamespace(sub=stopped_regex)
        with patch.object(financial_row_surfaces, "re", regex_owner):
            self.assertEqual(
                target(
                    {"metadata": {}, "text": ""},
                    IterationBombList(["surface"]),
                ),
                0,
            )
        stopped_regex.assert_not_called()

    def test_current_source_candidate_sibling_surface_hit_count_pins_laziness_stringification_and_exceptions(self) -> None:
        target = financial_row_surfaces.candidate_sibling_surface_hit_count
        events = []

        class TextProbe:
            def __init__(self, name, value, *, truth=True):
                self.name = name
                self.value = value
                self.truth = truth
                self.bool_calls = 0
                self.str_calls = 0
                self.hash_calls = 0

            def __bool__(self):
                self.bool_calls += 1
                events.append((self.name, "bool"))
                return self.truth

            def __str__(self):
                self.str_calls += 1
                events.append((self.name, "str"))
                return self.value

            def __hash__(self):
                self.hash_calls += 1
                events.append((self.name, "hash"))
                return object.__hash__(self)

        candidate_probes = [
            TextProbe("candidate-row-labels", "Revenue"),
            TextProbe("candidate-value-labels", "Value"),
            TextProbe("candidate-summary", "Summary"),
            TextProbe("candidate-context", "Stopped Context", truth=False),
            TextProbe("candidate-row", "Row"),
            TextProbe("candidate-text", "Tail"),
        ]
        candidate = {
            "metadata": {
                "table_row_labels_text": candidate_probes[0],
                "table_value_labels_text": candidate_probes[1],
                "table_summary_text": candidate_probes[2],
                "row_context_text": candidate_probes[3],
                "row_text": candidate_probes[4],
            },
            "text": candidate_probes[5],
        }
        first_surface = TextProbe("sibling-first", "Revenue")
        equivalent_surface = TextProbe("sibling-equivalent", " Revenue ")
        blank_surface = TextProbe("sibling-blank", "Stopped Blank", truth=False)
        sibling_surfaces = [
            first_surface,
            first_surface,
            equivalent_surface,
            blank_surface,
        ]

        self.assertEqual(target(candidate, sibling_surfaces), 2)
        for probe in candidate_probes:
            self.assertEqual(probe.bool_calls, 1)
        self.assertEqual(
            [probe.str_calls for probe in candidate_probes],
            [1, 1, 1, 0, 1, 1],
        )
        self.assertEqual(first_surface.bool_calls, 1)
        self.assertEqual(first_surface.str_calls, 1)
        self.assertGreaterEqual(first_surface.hash_calls, 1)
        self.assertEqual(equivalent_surface.bool_calls, 1)
        self.assertEqual(equivalent_surface.str_calls, 1)
        self.assertEqual(blank_surface.bool_calls, 1)
        self.assertEqual(blank_surface.str_calls, 0)
        first_sibling_event = next(
            index
            for index, event in enumerate(events)
            if event[0].startswith("sibling-")
        )
        candidate_string_events = [
            index
            for index, event in enumerate(events)
            if event[0].startswith("candidate-") and event[1] == "str"
        ]
        self.assertTrue(all(index < first_sibling_event for index in candidate_string_events))

        class TruthFailureList:
            def __bool__(self):
                raise RuntimeError("sibling list truth failed")

        with self.assertRaisesRegex(RuntimeError, "sibling list truth failed"):
            target(object(), TruthFailureList())

        class CandidateBomb:
            def get(self, key, default=None):
                raise RuntimeError(f"candidate get failed: {key}")

        with self.assertRaisesRegex(RuntimeError, "candidate get failed: metadata"):
            target(CandidateBomb(), ["surface"])

        class MetadataCopyFailure:
            def keys(self):
                raise RuntimeError("metadata copy failed")

        with self.assertRaisesRegex(RuntimeError, "metadata copy failed"):
            target({"metadata": MetadataCopyFailure()}, ["surface"])

        class StringFailure:
            def __init__(self, message):
                self.message = message

            def __str__(self):
                raise RuntimeError(self.message)

        stopped_normalize = Mock(
            side_effect=AssertionError("candidate string failure must stop normalization")
        )
        with patch.object(
            financial_row_surfaces,
            "_normalise_spaces",
            stopped_normalize,
        ):
            with self.assertRaisesRegex(RuntimeError, "candidate surface failed"):
                target(
                    {
                        "metadata": {
                            "table_row_labels_text": StringFailure(
                                "candidate surface failed"
                            ),
                            "table_value_labels_text": StringFailure(
                                "later candidate surface accessed"
                            ),
                        }
                    },
                    ["surface"],
                )
        stopped_normalize.assert_not_called()

        stopped_strip = Mock(
            side_effect=AssertionError("haystack normalization failure must stop strip")
        )
        with (
            patch.object(
                financial_row_surfaces,
                "_normalise_spaces",
                side_effect=RuntimeError("haystack normalization failed"),
            ),
            patch.object(
                financial_row_surfaces,
                "_strip_leading_period_qualifiers",
                stopped_strip,
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "haystack normalization failed"):
                target({"metadata": {"row_text": "row"}}, ["surface"])
        stopped_strip.assert_not_called()

        stopped_unhashable_strip = Mock(
            side_effect=AssertionError("raw dedupe failure must stop strip")
        )
        with patch.object(
            financial_row_surfaces,
            "_strip_leading_period_qualifiers",
            stopped_unhashable_strip,
        ):
            with self.assertRaises(TypeError):
                target({"metadata": {"row_text": "row"}}, [["unhashable"]])
        stopped_unhashable_strip.assert_not_called()

        class SurfaceTruthFailure:
            def __bool__(self):
                raise RuntimeError("surface truth failed")

        with self.assertRaisesRegex(RuntimeError, "surface truth failed"):
            target({"metadata": {"row_text": "row"}}, [SurfaceTruthFailure()])

        with self.assertRaisesRegex(RuntimeError, "surface string failed"):
            target(
                {"metadata": {"row_text": "row"}},
                [StringFailure("surface string failed")],
            )

        with patch.object(
            financial_row_surfaces,
            "_strip_leading_period_qualifiers",
            side_effect=RuntimeError("period strip failed"),
        ):
            with self.assertRaisesRegex(RuntimeError, "period strip failed"):
                target({"metadata": {"row_text": "row"}}, ["surface"])

        with patch.object(
            financial_row_surfaces,
            "_normalise_spaces",
            return_value=object(),
        ):
            with self.assertRaises(TypeError):
                target({"metadata": {"row_text": "row"}}, ["surface"])

    def test_current_source_candidate_sibling_surface_hit_count_bindings_pin_def_calls_dag_and_baseline(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        agent_root = repo_root / "src" / "agent"
        target_name = "candidate_sibling_surface_hit_count"
        public_name = "candidate_sibling_surface_hit_count"
        module_paths = {path.stem: path for path in agent_root.glob("*.py")}
        module_trees = {
            name: ast.parse(path.read_text(encoding="utf-8-sig"))
            for name, path in module_paths.items()
        }
        definitions = []
        calls = []

        class BindingVisitor(ast.NodeVisitor):
            def __init__(self, module_name):
                self.module_name = module_name
                self.function_stack = []
                self.ancestor_stack = []
                self.try_depth = 0

            def visit_FunctionDef(self, node):
                if node.name == target_name:
                    definitions.append((self.module_name, node))
                self.function_stack.append(node.name)
                self.ancestor_stack.append(node)
                self.generic_visit(node)
                self.ancestor_stack.pop()
                self.function_stack.pop()

            visit_AsyncFunctionDef = visit_FunctionDef

            def visit_Try(self, node):
                self.try_depth += 1
                self.ancestor_stack.append(node)
                self.generic_visit(node)
                self.ancestor_stack.pop()
                self.try_depth -= 1

            visit_TryStar = visit_Try

            def generic_visit(self, node):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Try, ast.TryStar)):
                    return super().generic_visit(node)
                self.ancestor_stack.append(node)
                super().generic_visit(node)
                self.ancestor_stack.pop()

            def visit_Call(self, node):
                called_name = node.func.id if isinstance(node.func, ast.Name) else ""
                if called_name == target_name:
                    context = "expression"
                    if any(isinstance(item, ast.Lambda) for item in self.ancestor_stack):
                        context = "lambda"
                    elif any(isinstance(item, ast.ListComp) for item in self.ancestor_stack):
                        context = "listcomp"
                    elif self.ancestor_stack:
                        context = type(self.ancestor_stack[-1]).__name__
                    calls.append(
                        (
                            node.lineno,
                            self.module_name,
                            self.function_stack[-1] if self.function_stack else "",
                            type(node.func).__name__,
                            tuple(ast.unparse(arg) for arg in node.args),
                            tuple(
                                (keyword.arg, ast.unparse(keyword.value))
                                for keyword in node.keywords
                            ),
                            self.try_depth,
                            context,
                        )
                    )
                self.generic_visit(node)

        for module_name, tree in module_trees.items():
            BindingVisitor(module_name).visit(tree)

        self.assertEqual(len(definitions), 1)
        definition_module, definition = definitions[0]
        self.assertEqual(definition_module, "financial_row_surfaces")
        self.assertEqual(definition.end_lineno - definition.lineno + 1, 30)
        self.assertEqual(
            [argument.arg for argument in definition.args.args],
            ["candidate", "sibling_surfaces"],
        )
        self.assertEqual(definition.args.defaults, [])
        self.assertEqual(definition.args.kwonlyargs, [])
        self.assertEqual(ast.unparse(definition.returns), "int")
        self.assertEqual(definition.decorator_list, [])
        self.assertFalse(
            any(
                isinstance(node, (ast.Try, ast.TryStar))
                for node in ast.walk(definition)
            )
        )

        calls = sorted(calls)
        self.assertEqual(
            [row[1:] for row in calls],
            [
                (
                    "financial_graph_helpers",
                    "_deterministic_reconcile_task",
                    "Name",
                    (
                        "dict(entry.get('candidate') or {})",
                        "sibling_surfaces",
                    ),
                    (),
                    0,
                    "lambda",
                ),
                (
                    "financial_graph_helpers",
                    "_deterministic_reconcile_task",
                    "Name",
                    (
                        "dict(sibling_ranked_entries[0].get('candidate') or {})",
                        "sibling_surfaces",
                    ),
                    (),
                    0,
                    "Assign",
                ),
                (
                    "financial_graph_helpers",
                    "_deterministic_reconcile_task",
                    "Name",
                    (
                        "dict(entry.get('candidate') or {})",
                        "sibling_surfaces",
                    ),
                    (),
                    0,
                    "listcomp",
                ),
            ],
        )
        self.assertEqual(
            (
                len(calls),
                sum(row[1] == "financial_row_surfaces" for row in calls),
            ),
            (3, 0),
        )

        graph_defs = [
            node
            for node in module_trees["financial_graph_helpers"].body
            if isinstance(node, ast.FunctionDef)
        ]
        row_defs = [
            node
            for node in module_trees["financial_row_surfaces"].body
            if isinstance(node, ast.FunctionDef)
        ]
        graph_counts = (
            sum(not node.name.startswith("_") for node in graph_defs),
            sum(node.name.startswith("_") for node in graph_defs),
        )
        row_counts = (
            sum(not node.name.startswith("_") for node in row_defs),
            sum(node.name.startswith("_") for node in row_defs),
        )
        self.assertEqual(graph_counts, (9, 97))
        self.assertEqual(row_counts, (5, 15))

        def imported_names(module_name, imported_module):
            return {
                alias.name
                for node in module_trees[module_name].body
                if isinstance(node, ast.ImportFrom)
                and node.module == imported_module
                for alias in node.names
            }

        row_module = "src.agent.financial_row_surfaces"
        graph_row_imports = imported_names("financial_graph_helpers", row_module)
        self.assertNotIn("_strip_leading_period_qualifiers", graph_row_imports)
        self.assertIn(public_name, graph_row_imports)
        self.assertNotIn(
            "src.agent.financial_graph_helpers",
            {
                node.module
                for node in module_trees["financial_row_surfaces"].body
                if isinstance(node, ast.ImportFrom) and node.module
            },
        )
        self.assertIn(
            "_strip_leading_period_qualifiers",
            {
                node.name
                for node in module_trees["financial_row_surfaces"].body
                if isinstance(node, ast.FunctionDef)
            },
        )
        row_imported_types = imported_names("financial_row_surfaces", "typing")
        self.assertTrue({"Any", "Dict", "List"}.issubset(row_imported_types))
        self.assertIn(
            "_normalise_spaces",
            imported_names(
                "financial_row_surfaces",
                "src.agent.financial_runtime_normalization",
            ),
        )
        self.assertTrue(
            any(
                isinstance(node, ast.Import)
                and any(alias.name == "re" for alias in node.names)
                for node in module_trees["financial_row_surfaces"].body
            )
        )
        strip_loads = [
            node
            for node in ast.walk(definition)
            if isinstance(node, ast.Name)
            and isinstance(node.ctx, ast.Load)
            and node.id == "_strip_leading_period_qualifiers"
        ]
        self.assertEqual(len(strip_loads), 1)

        edges = {name: set() for name in module_trees}
        for module_name, tree in module_trees.items():
            for node in tree.body:
                if not isinstance(node, ast.ImportFrom) or not node.module:
                    continue
                prefix = "src.agent."
                if not node.module.startswith(prefix):
                    continue
                imported = node.module[len(prefix) :]
                if imported in edges:
                    edges[module_name].add(imported)

        def reaches(start, target):
            seen = set()
            pending = list(edges[start])
            while pending:
                current = pending.pop()
                if current == target:
                    return True
                if current in seen:
                    continue
                seen.add(current)
                pending.extend(edges[current])
            return False

        self.assertTrue(reaches("financial_graph_helpers", "financial_row_surfaces"))
        self.assertTrue(reaches("financial_row_surfaces", "financial_surface_contracts"))
        self.assertFalse(reaches("financial_row_surfaces", "financial_graph_helpers"))
        self.assertFalse(reaches("financial_surface_contracts", "financial_row_surfaces"))

        current_test_tree = ast.parse(
            Path(__file__).read_text(encoding="utf-8-sig")
        )
        current_source_methods = {
            node.name
            for node in ast.walk(current_test_tree)
            if isinstance(node, ast.FunctionDef)
            and node.name.startswith(
                "test_current_source_candidate_sibling_surface_hit_count"
            )
        }
        self.assertEqual(
            current_source_methods,
            {
                "test_current_source_candidate_sibling_surface_hit_count_pins_projection_dedupe_compaction_and_identity",
                "test_current_source_candidate_sibling_surface_hit_count_pins_laziness_stringification_and_exceptions",
                "test_current_source_candidate_sibling_surface_hit_count_bindings_pin_def_calls_dag_and_baseline",
                "test_current_source_candidate_sibling_surface_hit_count_caller_pins_copy_rank_filter_adoption_and_stop",
            },
        )

        baseline = json.loads(
            (
                repo_root
                / "tests"
                / "fixtures"
                / "runtime_domain_terms_baseline.json"
            ).read_text(encoding="utf-8-sig")
        )
        self.assertEqual(len(baseline["records"]), 218)
        selected_hits = [
            record
            for record in baseline["records"]
            if record.get("path") == "src/agent/financial_row_surfaces.py"
            and any(
                definition.lineno <= line <= definition.end_lineno
                for line in (record.get("first_lines") or [])
            )
        ]
        self.assertEqual(selected_hits, [])

    def test_current_source_candidate_sibling_surface_hit_count_caller_pins_copy_rank_filter_adoption_and_stop(self) -> None:
        target_name = "candidate_sibling_surface_hit_count"
        nested = {"preserve": True}

        class SurfaceTextProbe:
            def __init__(self, name, value):
                self.name = name
                self.value = value
                self.str_calls = 0

            def __str__(self):
                self.str_calls += 1
                return self.value

        def execute(
            specs,
            sibling_items,
            *,
            helper_owner,
            semantic_owner=None,
        ):
            originals = [
                {
                    "candidate_id": spec["candidate_id"],
                    "rank_score": spec["rank_score"],
                    "entry_score": spec["entry_score"],
                    "hit": spec.get("hit", 0),
                    "canonical": spec.get("canonical", False),
                    "metadata": {"nested": nested},
                    "nested": nested,
                }
                for spec in specs
            ]
            original_snapshots = deepcopy(originals)
            cells = {
                candidate["candidate_id"]: {
                    "value_text": candidate["candidate_id"],
                    "column_headers": ["2024"],
                    "nested": nested,
                }
                for candidate in originals
            }
            score_counts = {candidate["candidate_id"]: 0 for candidate in originals}

            def score_candidate(candidate, **_kwargs):
                candidate_id = candidate["candidate_id"]
                score_counts[candidate_id] += 1
                if score_counts[candidate_id] == 1:
                    return candidate["rank_score"]
                return candidate["entry_score"]

            if semantic_owner is None:
                semantic_owner = Mock(return_value=(0, 0, 0, 0, 0))
            with (
                patch.object(
                    financial_graph_helpers,
                    "_candidate_matches_operand",
                    return_value=True,
                ),
                patch.object(
                    financial_graph_helpers,
                    "_operand_segment_label",
                    return_value="",
                ),
                patch.object(
                    financial_graph_helpers,
                    "_score_operand_candidate",
                    side_effect=score_candidate,
                ),
                patch.object(
                    financial_graph_helpers,
                    "operand_period_focus",
                    return_value="current",
                ),
                patch.object(
                    financial_graph_helpers,
                    "_candidate_selected_cell_for_operand",
                    side_effect=lambda candidate, **_kwargs: cells[
                        candidate["candidate_id"]
                    ],
                ),
                patch.object(
                    financial_graph_helpers,
                    "_candidate_satisfies_direct_acceptance_contract",
                    return_value=True,
                ),
                patch.object(
                    financial_graph_helpers,
                    "candidate_direct_logical_signature",
                    side_effect=lambda candidate, **_kwargs: (
                        "logical",
                        candidate["candidate_id"],
                    ),
                ),
                patch.object(
                    financial_graph_helpers,
                    "candidate_direct_family_signature",
                    side_effect=lambda candidate, **_kwargs: (
                        "family",
                        candidate["candidate_id"],
                    ),
                ),
                patch.object(
                    financial_graph_helpers,
                    "_candidate_is_canonical_statement_winner",
                    side_effect=lambda candidate, **_kwargs: candidate["canonical"],
                ),
                patch.object(
                    financial_graph_helpers,
                    target_name,
                    helper_owner,
                ),
                patch.object(
                    financial_graph_helpers,
                    "_direct_candidate_semantic_priority",
                    semantic_owner,
                ),
            ):
                result = financial_graph_helpers._deterministic_reconcile_task(
                    active_subtask={
                        "task_id": "task-sibling",
                        "operation_family": "lookup",
                        "required_operands": [
                            {
                                "label": "Metric",
                                "required": True,
                                "nested": nested,
                            }
                        ],
                        "sibling_lookup_surfaces": sibling_items,
                    },
                    candidates=originals,
                    years=[2024],
                    reconciliation_retry_count=1,
                )
            self.assertEqual(originals, original_snapshots)
            self.assertTrue(
                all(candidate["metadata"]["nested"] is nested for candidate in originals)
            )
            self.assertTrue(all(candidate["nested"] is nested for candidate in originals))
            self.assertTrue(all(cell["nested"] is nested for cell in cells.values()))
            return result, originals, cells, score_counts, semantic_owner

        positive_specs = [
            {
                "candidate_id": "a",
                "rank_score": 10.0,
                "entry_score": 10.0,
                "hit": 2,
            },
            {
                "candidate_id": "b",
                "rank_score": 8.0,
                "entry_score": 8.0,
                "hit": 1,
            },
            {
                "candidate_id": "c",
                "rank_score": 6.0,
                "entry_score": 6.0,
                "hit": 2,
            },
        ]
        retained_first = SurfaceTextProbe("retained-first", " target ")
        blank = SurfaceTextProbe("blank", "   ")
        retained_second = SurfaceTextProbe("retained-second", "target")
        positive_calls = []
        positive_candidates = []
        positive_surface_refs = []

        def positive_hit(candidate, sibling_surfaces):
            positive_calls.append(candidate["candidate_id"])
            positive_candidates.append(candidate)
            positive_surface_refs.append(sibling_surfaces)
            return candidate["hit"]

        positive_helper = Mock(side_effect=positive_hit)
        positive_result, positive_originals, _cells, positive_scores, _semantic = (
            execute(
                positive_specs,
                [retained_first, blank, retained_second],
                helper_owner=positive_helper,
            )
        )
        self.assertEqual(
            positive_calls,
            ["a", "b", "c", "a", "a", "c", "b"],
        )
        self.assertEqual(positive_helper.call_count, 7)
        self.assertEqual(retained_first.str_calls, 2)
        self.assertEqual(blank.str_calls, 1)
        self.assertEqual(retained_second.str_calls, 2)
        self.assertTrue(
            all(current is positive_surface_refs[0] for current in positive_surface_refs)
        )
        self.assertEqual(positive_surface_refs[0], ["target", "target"])
        original_by_id = {
            candidate["candidate_id"]: candidate for candidate in positive_originals
        }
        self.assertEqual(
            len({id(candidate) for candidate in positive_candidates}),
            len(positive_candidates),
        )
        for copied_candidate in positive_candidates:
            original = original_by_id[copied_candidate["candidate_id"]]
            self.assertIsNot(copied_candidate, original)
            self.assertIs(copied_candidate["metadata"], original["metadata"])
            self.assertIs(copied_candidate["nested"], nested)
        self.assertEqual(positive_scores, {"a": 2, "b": 2, "c": 2})
        self.assertEqual(positive_result["status"], "ready")
        self.assertEqual(
            positive_result["matched_operands"][0]["candidate_ids"],
            ["a", "b", "c"],
        )

        zero_calls = []
        semantic_calls = []

        def zero_hit(candidate, _sibling_surfaces):
            zero_calls.append(candidate["candidate_id"])
            return 0

        def semantic_priority(candidate, **_kwargs):
            semantic_calls.append(candidate["candidate_id"])
            return (0, 0, 0, 0, 0)

        zero_result, _zero_originals, _zero_cells, zero_scores, _ = execute(
            [
                {
                    "candidate_id": "a",
                    "rank_score": 10.0,
                    "entry_score": 1.0,
                },
                {
                    "candidate_id": "b",
                    "rank_score": 8.0,
                    "entry_score": 2.0,
                },
            ],
            ["target"],
            helper_owner=Mock(side_effect=zero_hit),
            semantic_owner=Mock(side_effect=semantic_priority),
        )
        self.assertEqual(zero_calls, ["a", "b", "b"])
        self.assertEqual(semantic_calls, ["a", "b", "b", "a"])
        self.assertEqual(zero_scores, {"a": 2, "b": 2})
        self.assertEqual(zero_result["status"], "ready")
        self.assertEqual(
            zero_result["matched_operands"][0]["candidate_ids"],
            ["b", "a"],
        )

        stopped_single = Mock(
            side_effect=AssertionError("one collapsed entry must stop sibling ranking")
        )
        single_result, _single_originals, _single_cells, _single_scores, _ = execute(
            [
                {
                    "candidate_id": "only",
                    "rank_score": 1.0,
                    "entry_score": 1.0,
                }
            ],
            ["target"],
            helper_owner=stopped_single,
        )
        self.assertEqual(single_result["status"], "ready")
        stopped_single.assert_not_called()

        stopped_blank = Mock(
            side_effect=AssertionError("empty prepared surfaces must stop sibling ranking")
        )
        blank_only = SurfaceTextProbe("blank-only", "   ")
        blank_result, _blank_originals, _blank_cells, _blank_scores, _ = execute(
            positive_specs[:2],
            [blank_only],
            helper_owner=stopped_blank,
        )
        self.assertEqual(blank_result["status"], "ready")
        self.assertEqual(blank_only.str_calls, 1)
        stopped_blank.assert_not_called()

        failure_specs = positive_specs[:2]
        failure_cases = {
            "sort": ([RuntimeError("sort sibling hit failed")], 1),
            "top": ([2, 1, RuntimeError("top sibling hit failed")], 3),
            "filter": (
                [2, 1, 2, RuntimeError("filter sibling hit failed")],
                4,
            ),
        }
        for stage, (side_effects, expected_calls) in failure_cases.items():
            with self.subTest(stage=stage):
                stopped_semantic = Mock(
                    side_effect=AssertionError(
                        f"{stage} helper failure must stop semantic ranking"
                    )
                )
                failing_helper = Mock(side_effect=side_effects)
                with self.assertRaisesRegex(RuntimeError, f"{stage} sibling hit failed"):
                    execute(
                        failure_specs,
                        ["target"],
                        helper_owner=failing_helper,
                        semantic_owner=stopped_semantic,
                    )
                self.assertEqual(failing_helper.call_count, expected_calls)
                stopped_semantic.assert_not_called()


    def test_current_source_plan_shape_predicates_pin_roles_laziness_copy_and_exceptions(self) -> None:
        segment_base = {
            "tasks": [
                {
                    "operation_family": " SUM ",
                    "constraints": {"segment_scope": " Segment "},
                    "required_operands": [{"role": "addend_1"}, {"role": "addend_2"}],
                }
            ]
        }
        preserved_segment = {
            "tasks": [
                {
                    "operation_family": "sum",
                    "constraints": {"segment_scope": "segment"},
                    "required_operands": [
                        {"role": " addend_1 "},
                        {"role": "addend_2"},
                        {"role": "ignored"},
                    ],
                }
            ]
        }
        degraded_segment = {
            "tasks": [
                {
                    "operation_family": "sum",
                    "constraints": {"segment_scope": "segment"},
                    "required_operands": [{"role": "addend_1"}],
                }
            ]
        }
        before_segment = deepcopy((segment_base, preserved_segment, degraded_segment))
        self.assertTrue(
            financial_graph_helpers.llm_plan_preserves_segment_sum_shape(
                {"tasks": [{"operation_family": "lookup"}]},
                {"tasks": object()},
            )
        )
        self.assertTrue(
            financial_graph_helpers.llm_plan_preserves_segment_sum_shape(
                segment_base,
                preserved_segment,
            )
        )
        self.assertFalse(
            financial_graph_helpers.llm_plan_preserves_segment_sum_shape(
                segment_base,
                degraded_segment,
            )
        )
        self.assertEqual((segment_base, preserved_segment, degraded_segment), before_segment)

        role_task = {
            "required_operands": [
                {"concept": " Revenue ", "role": "numerator_1"},
                {"concept": "Revenue", "role": "numerator_2"},
                {"concept": "Cost", "role": " denominator_2 "},
                {"concept": "", "role": "ignored"},
            ]
        }
        before_role_task = deepcopy(role_task)
        with patch.object(
            financial_graph_helpers,
            "_normalise_spaces",
            side_effect=lambda value: " ".join(str(value).split()),
        ) as normalizer:
            self.assertEqual(
                financial_graph_helpers._task_concept_role_families(role_task),
                {("Revenue", "numerator"), ("Cost", "denominator")},
            )
        self.assertEqual(len(normalizer.call_args_list), 8)
        self.assertEqual(role_task, before_role_task)

        base_analysis = {
            "tasks": [
                {
                    "operation_family": " ratio ",
                    "analysis_hints": {"kind": "required"},
                    "required_operands": [
                        {"concept": "Revenue", "role": "numerator_1"},
                        {"concept": "Cost", "role": "denominator_1"},
                    ],
                }
            ]
        }
        compatible_analysis = {
            "tasks": [
                {
                    "operation_family": "ratio",
                    "required_operands": [
                        {"concept": "Revenue", "role": "numerator_9"},
                        {"concept": "Cost", "role": "denominator_2"},
                        {"concept": "Extra", "role": "numerator_2"},
                    ],
                }
            ]
        }
        before_analysis = deepcopy((base_analysis, compatible_analysis))
        self.assertTrue(
            financial_graph_helpers.llm_plan_preserves_analysis_shape(
                {"tasks": [{"operation_family": "ratio"}]},
                {"tasks": object()},
            )
        )
        self.assertTrue(
            financial_graph_helpers.llm_plan_preserves_analysis_shape(
                base_analysis,
                compatible_analysis,
            )
        )
        self.assertFalse(
            financial_graph_helpers.llm_plan_preserves_analysis_shape(
                base_analysis,
                {"tasks": [{"operation_family": "lookup", "required_operands": []}]},
            )
        )
        self.assertEqual((base_analysis, compatible_analysis), before_analysis)

        downstream_role = Mock(side_effect=AssertionError("role helper accessed"))
        with (
            patch.object(
                financial_graph_helpers,
                "_normalise_spaces",
                side_effect=RuntimeError("operation normalization failed"),
            ),
            patch.object(
                financial_graph_helpers,
                "_task_concept_role_families",
                downstream_role,
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "operation normalization failed"):
                financial_graph_helpers.llm_plan_preserves_analysis_shape(
                    base_analysis,
                    compatible_analysis,
                )
        downstream_role.assert_not_called()


    def test_current_source_segment_label_projection_pins_branches_copies_and_exceptions(self) -> None:
        nested = {"preserve": True}
        extractor = Mock(side_effect=AssertionError("segment extractor accessed"))
        with patch.object(
            financial_graph_helpers,
            "_extract_segment_labels_from_query",
            extractor,
        ):
            self.assertEqual(
                financial_graph_helpers.apply_segment_labels_to_llm_resolved_specs(
                    query="query",
                    metric_label="metric",
                    operation_family="sum",
                    report_scope={},
                    resolved_specs=[],
                ),
                [],
            )
        extractor.assert_not_called()

        original = {
            "concept": "revenue",
            "role": "addend_1",
            "name": "Revenue",
            "aliases": ["sales"],
            "binding_policy": {"existing": True},
            "nested": nested,
        }
        original_rows = [original]
        with patch.object(
            financial_graph_helpers,
            "_extract_segment_labels_from_query",
            return_value=[],
        ):
            no_labels = financial_graph_helpers.apply_segment_labels_to_llm_resolved_specs(
                query="query",
                metric_label="metric",
                operation_family="sum",
                report_scope={},
                resolved_specs=original_rows,
            )
        self.assertEqual(no_labels, original_rows)
        self.assertIsNot(no_labels, original_rows)
        self.assertIsNot(no_labels[0], original)
        self.assertIs(no_labels[0]["nested"], nested)
        self.assertIs(no_labels[0]["aliases"], original["aliases"])
        self.assertIs(no_labels[0]["binding_policy"], original["binding_policy"])

        sum_specs = [
            {**original, "role": "addend_1"},
            {**original, "role": "addend_2"},
        ]
        before_sum = deepcopy(sum_specs)
        with patch.object(
            financial_graph_helpers,
            "_extract_segment_labels_from_query",
            return_value=["North", "South"],
        ):
            projected_sum = financial_graph_helpers.apply_segment_labels_to_llm_resolved_specs(
                query="query",
                metric_label="metric",
                operation_family="sum",
                report_scope={"company": "Co"},
                resolved_specs=sum_specs,
            )
        self.assertEqual([item["name"] for item in projected_sum], ["North Revenue", "South Revenue"])
        self.assertEqual(
            [item["binding_policy"]["segment_label"] for item in projected_sum],
            ["North", "South"],
        )
        self.assertEqual(projected_sum[0]["aliases"][:3], ["North Revenue", "North", "Revenue"])
        self.assertIsNot(projected_sum[0], sum_specs[0])
        self.assertIsNot(projected_sum[0]["aliases"], sum_specs[0]["aliases"])
        self.assertIsNot(projected_sum[0]["binding_policy"], sum_specs[0]["binding_policy"])
        self.assertIs(projected_sum[0]["nested"], nested)
        self.assertEqual(sum_specs, before_sum)

        with patch.object(
            financial_graph_helpers,
            "_extract_segment_labels_from_query",
            return_value=["Mobile"],
        ):
            growth = financial_graph_helpers.apply_segment_labels_to_llm_resolved_specs(
                query="query",
                metric_label="metric",
                operation_family="growth_rate",
                report_scope={},
                resolved_specs=[
                    {**original, "role": "current_period"},
                    {**original, "role": "prior_period"},
                ],
            )
            ratio = financial_graph_helpers.apply_segment_labels_to_llm_resolved_specs(
                query="query",
                metric_label="metric",
                operation_family="ratio",
                report_scope={},
                resolved_specs=[
                    {**original, "role": "denominator_1"},
                    {**original, "role": "numerator_1"},
                ],
            )
            lookup = financial_graph_helpers.apply_segment_labels_to_llm_resolved_specs(
                query="query",
                metric_label="mobile revenue",
                operation_family="lookup",
                report_scope={},
                resolved_specs=[{**original, "role": ""}],
            )
        self.assertEqual(
            [item["binding_policy"]["segment_label"] for item in growth],
            ["Mobile", "Mobile"],
        )
        self.assertNotIn("segment_label", ratio[0]["binding_policy"])
        self.assertEqual(ratio[1]["binding_policy"]["segment_label"], "Mobile")
        self.assertEqual(lookup[0]["binding_policy"]["segment_label"], "Mobile")

        attach_owner = Mock(side_effect=RuntimeError("segment attach failed"))
        with (
            patch.object(
                financial_graph_helpers,
                "_extract_segment_labels_from_query",
                return_value=["North", "South"],
            ),
            patch.object(
                financial_graph_helpers,
                "_attach_segment_label_to_resolved_spec",
                attach_owner,
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "segment attach failed"):
                financial_graph_helpers.apply_segment_labels_to_llm_resolved_specs(
                    query="query",
                    metric_label="metric",
                    operation_family="sum",
                    report_scope={},
                    resolved_specs=sum_specs,
                )
        self.assertEqual(len(attach_owner.call_args_list), 1)
        self.assertIsNot(attach_owner.call_args.args[0], sum_specs[0])
        self.assertIs(attach_owner.call_args.args[0]["nested"], nested)


    def test_current_source_planner_task_validation_pins_shape_surface_roles_and_exceptions(self) -> None:
        class Ontology:
            def __init__(self, known=("revenue", "cost")):
                self.known = set(known)
                self.calls = []

            def has_concept_key(self, key):
                self.calls.append(key)
                return key in self.known

        def operand(concept, role=""):
            return SimpleNamespace(concept=concept, role=role)

        def task(operation_family, operands):
            return SimpleNamespace(operation_family=operation_family, operands=operands)

        validate = financial_graph_helpers.validate_concept_planner_task
        ontology = Ontology()
        self.assertEqual(
            validate(task("unknown", [operand("revenue")]), ontology),
            (False, "unsupported_operation:unknown"),
        )
        self.assertEqual(validate(task("lookup", []), ontology), (False, "missing_operands"))
        self.assertEqual(validate(task("lookup", [operand("")]), ontology), (False, "unknown_concept:-"))
        self.assertEqual(
            validate(task("lookup", [operand("other")]), ontology),
            (False, "unknown_concept:other"),
        )
        self.assertEqual(
            validate(
                task("lookup", [operand("revenue")]),
                ontology,
                allowed_concept_keys={"cost"},
            ),
            (False, "concept_not_available:revenue"),
        )

        specs = {
            "revenue": {
                "surface_contract": {
                    "positive": [" Revenue ", "Sales"],
                }
            }
        }
        self.assertEqual(
            validate(
                task("lookup", [operand("revenue")]),
                ontology,
                concept_specs_by_key=specs,
                support_text="Cost only",
                require_surface_contract_match=True,
            ),
            (False, "surface_contract_missing:revenue"),
        )
        self.assertEqual(
            validate(
                task("lookup", [operand("revenue")]),
                ontology,
                concept_specs_by_key=specs,
                support_text="Revenue evidence",
                require_surface_contract_match=True,
            ),
            (True, "ok"),
        )

        role_cases = [
            ("ratio", [operand("revenue", "denominator_1")], "ratio_missing_numerator"),
            ("ratio", [operand("revenue", "numerator_1")], "ratio_missing_denominator"),
            (
                "ratio",
                [operand("revenue", "numerator_1"), operand("cost", "denominator_1"), operand("cost", "other")],
                "ratio_invalid_role:other",
            ),
            ("sum", [operand("revenue", "other")], "sum_invalid_role:other"),
            ("difference", [operand("revenue", "minuend")], "difference_requires_two_operands"),
            (
                "difference",
                [operand("revenue", "minuend"), operand("cost", "other")],
                "difference_invalid_role:other",
            ),
            ("growth_rate", [operand("revenue", "current_period")], "growth_rate_requires_two_operands"),
            (
                "growth_rate",
                [operand("revenue", "current_period"), operand("cost", "other")],
                "growth_rate_invalid_role:other",
            ),
        ]
        for operation_family, operands, expected_note in role_cases:
            with self.subTest(operation_family=operation_family, expected_note=expected_note):
                self.assertEqual(
                    validate(task(operation_family, operands), ontology),
                    (False, expected_note),
                )

        valid_cases = [
            task("ratio", [operand("revenue", "numerator_2"), operand("cost", "denominator_9")]),
            task("sum", [operand("revenue", "addend_1"), operand("cost", "addend_2")]),
            task("difference", [operand("revenue", "minuend"), operand("cost", "subtrahend")]),
            task("growth_rate", [operand("revenue", "current_period"), operand("cost", "prior_period")]),
            task("single_value", [operand("revenue")]),
        ]
        for raw_task in valid_cases:
            with self.subTest(operation_family=raw_task.operation_family):
                before = deepcopy(raw_task)
                self.assertEqual(validate(raw_task, ontology), (True, "ok"))
                self.assertEqual(raw_task, before)

        downstream_ontology = Mock(side_effect=AssertionError("ontology accessed after failure"))
        failing_ontology = SimpleNamespace(has_concept_key=downstream_ontology)

        class OperationBomb:
            def __str__(self):
                raise RuntimeError("operation conversion failed")

        with self.assertRaisesRegex(RuntimeError, "operation conversion failed"):
            validate(
                SimpleNamespace(operation_family=OperationBomb(), operands=[operand("revenue")]),
                failing_ontology,
            )
        downstream_ontology.assert_not_called()

        exploding_ontology = SimpleNamespace(
            has_concept_key=Mock(side_effect=RuntimeError("ontology lookup failed"))
        )
        with self.assertRaisesRegex(RuntimeError, "ontology lookup failed"):
            validate(task("lookup", [operand("revenue")]), exploding_ontology)


    def test_current_source_planning_normalization_bindings_pin_defs_calls_dag_and_baseline(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        module_paths = {
            "graph": repo_root / "src" / "agent" / "financial_graph_planning.py",
            "owner": repo_root / "src" / "agent" / "financial_graph_helpers.py",
        }
        module_sources = {
            name: path.read_text(encoding="utf-8-sig")
            for name, path in module_paths.items()
        }
        module_trees = {name: ast.parse(source) for name, source in module_sources.items()}
        current_targets = {
            "single_scope": "_has_single_report_scope",
            "segment_shape": "llm_plan_preserves_segment_sum_shape",
            "roles": "_task_concept_role_families",
            "analysis_shape": "llm_plan_preserves_analysis_shape",
            "attach_segment": "_attach_segment_label_to_resolved_spec",
            "segment_specs": "apply_segment_labels_to_llm_resolved_specs",
            "align_scope": "align_scope_hints",
            "validate_task": "validate_concept_planner_task",
        }
        current_public = {
            current_targets[key]
            for key in (
                "segment_shape",
                "analysis_shape",
                "segment_specs",
                "align_scope",
                "validate_task",
            )
        }
        target_by_name = {value: key for key, value in current_targets.items()}
        definitions = {}
        calls = {key: [] for key in current_targets}
        try_depths = {key: [] for key in current_targets}

        class BindingVisitor(ast.NodeVisitor):
            def __init__(self, module_name):
                self.module_name = module_name
                self.function_stack = []
                self.class_stack = []
                self.try_depth = 0

            def visit_ClassDef(self, node):
                self.class_stack.append(node.name)
                self.generic_visit(node)
                self.class_stack.pop()

            def visit_FunctionDef(self, node):
                if node.name in target_by_name:
                    definitions[node.name] = (
                        self.module_name,
                        tuple(self.class_stack),
                        node,
                    )
                self.function_stack.append(node.name)
                self.generic_visit(node)
                self.function_stack.pop()

            visit_AsyncFunctionDef = visit_FunctionDef

            def visit_Try(self, node):
                self.try_depth += 1
                self.generic_visit(node)
                self.try_depth -= 1

            visit_TryStar = visit_Try

            def visit_Call(self, node):
                called_name = (
                    node.func.id
                    if isinstance(node.func, ast.Name)
                    else node.func.attr
                    if isinstance(node.func, ast.Attribute)
                    else ""
                )
                key = target_by_name.get(called_name)
                if key:
                    receiver = (
                        ast.unparse(node.func.value)
                        if isinstance(node.func, ast.Attribute)
                        else ""
                    )
                    calls[key].append(
                        (
                            self.module_name,
                            tuple(self.function_stack),
                            receiver,
                            tuple(ast.unparse(argument) for argument in node.args),
                            tuple(
                                (keyword.arg, ast.unparse(keyword.value))
                                for keyword in node.keywords
                            ),
                        )
                    )
                    try_depths[key].append(self.try_depth)
                self.generic_visit(node)

        for module_name, tree in module_trees.items():
            BindingVisitor(module_name).visit(tree)

        self.assertEqual(
            {
                name: (
                    module_name,
                    class_stack,
                    node.end_lineno - node.lineno + 1,
                )
                for name, (module_name, class_stack, node) in definitions.items()
            },
            {
                "_has_single_report_scope": ("owner", (), 8),
                "llm_plan_preserves_segment_sum_shape": ("owner", (), 25),
                "_task_concept_role_families": ("owner", (), 12),
                "llm_plan_preserves_analysis_shape": ("owner", (), 24),
                "_attach_segment_label_to_resolved_spec": ("owner", (), 10),
                "apply_segment_labels_to_llm_resolved_specs": ("owner", (), 80),
                "align_scope_hints": ("owner", (), 40),
                "validate_concept_planner_task": ("owner", (), 72),
            },
        )
        owner_top_level_names = {
            node.name
            for node in module_trees["owner"].body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        self.assertTrue(current_public.issubset(owner_top_level_names))
        self.assertEqual(
            {key: len(entries) for key, entries in calls.items()},
            {
                "single_scope": 1,
                "segment_shape": 1,
                "roles": 2,
                "analysis_shape": 1,
                "attach_segment": 4,
                "segment_specs": 1,
                "align_scope": 5,
                "validate_task": 1,
            },
        )
        self.assertEqual(
            try_depths,
            {
                "single_scope": [0],
                "segment_shape": [0],
                "roles": [0, 0],
                "analysis_shape": [0],
                "attach_segment": [0, 0, 0, 0],
                "segment_specs": [0],
                "align_scope": [0, 0, 0, 0, 0],
                "validate_task": [0],
            },
        )
        self.assertEqual(
            [entry[1][-1] for entry in calls["align_scope"]],
            [
                "_extract_entities",
                "_build_llm_concept_numeric_plan",
                "_plan_exclusive_narrative_task",
                "_plan_semantic_numeric_tasks",
                "_plan_semantic_numeric_tasks",
            ],
        )
        self.assertEqual(
            [entry[2] for entry in calls["align_scope"]],
            [""] * 5,
        )
        self.assertEqual(calls["validate_task"][0][2], "")
        self.assertEqual(
            calls["validate_task"][0][3:],
            (
                ("raw_task", "ontology"),
                (
                    ("allowed_concept_keys", "allowed_concept_keys"),
                    ("concept_specs_by_key", "concept_spec_by_key"),
                    ("support_text", "concept_seed_query"),
                    ("require_surface_contract_match", "used_full_catalog_fallback"),
                ),
            ),
        )
        self.assertEqual(
            calls["segment_specs"][0][3:],
            (
                (),
                (
                    ("query", "query"),
                    ("metric_label", "raw_metric_label"),
                    ("operation_family", "operation_family"),
                    ("report_scope", "report_scope"),
                    ("resolved_specs", "resolved_specs"),
                ),
            ),
        )
        self.assertEqual(
            [(entry[1][-1], entry[2], entry[3], entry[4]) for entry in calls["segment_shape"]],
            [("_plan_semantic_numeric_tasks", "", ("plan", "llm_plan"), ())],
        )
        self.assertEqual(
            [(entry[1][-1], entry[2], entry[3], entry[4]) for entry in calls["analysis_shape"]],
            [("_plan_semantic_numeric_tasks", "", ("plan", "llm_plan"), ())],
        )

        selected_definition_names = set(current_targets.values())
        planned_distribution = {}
        external = 0
        local = 0
        for key, entries in calls.items():
            owner_count = sum(
                bool(selected_definition_names.intersection(function_stack))
                for _module, function_stack, _receiver, _args, _keywords in entries
            )
            graph_count = len(entries) - owner_count
            planned_distribution[key] = (graph_count, owner_count)
            external += graph_count
            local += owner_count
        self.assertEqual(
            planned_distribution,
            {
                "single_scope": (0, 1),
                "segment_shape": (1, 0),
                "roles": (0, 2),
                "analysis_shape": (1, 0),
                "attach_segment": (0, 4),
                "segment_specs": (1, 0),
                "align_scope": (5, 0),
                "validate_task": (1, 0),
            },
        )
        self.assertEqual((external, local), (9, 7))
        non_call_loads = []
        for module_name, tree in module_trees.items():
            parent_by_node = {
                child: parent
                for parent in ast.walk(tree)
                for child in ast.iter_child_nodes(parent)
            }
            for node in ast.walk(tree):
                loaded_name = (
                    node.id
                    if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load)
                    else node.attr
                    if isinstance(node, ast.Attribute) and isinstance(node.ctx, ast.Load)
                    else ""
                )
                if loaded_name not in selected_definition_names:
                    continue
                parent = parent_by_node.get(node)
                if not (isinstance(parent, ast.Call) and parent.func is node):
                    non_call_loads.append((module_name, loaded_name, getattr(node, "lineno", 0)))
        self.assertEqual(non_call_loads, [])

        def imported_modules(tree):
            modules = set()
            for node in tree.body:
                if isinstance(node, ast.ImportFrom) and node.module:
                    modules.add(node.module)
                elif isinstance(node, ast.Import):
                    modules.update(alias.name for alias in node.names)
            return modules

        self.assertIn(
            "src.agent.financial_graph_helpers",
            imported_modules(module_trees["graph"]),
        )
        self.assertNotIn(
            "src.agent.financial_graph_planning",
            imported_modules(module_trees["owner"]),
        )
        graph_public_bindings = {
            alias.name
            for node in module_trees["graph"].body
            if isinstance(node, ast.ImportFrom)
            and node.module == "src.agent.financial_graph_helpers"
            for alias in node.names
            if alias.name in current_public
        }
        self.assertEqual(graph_public_bindings, current_public)
        self.assertIn(
            "src.agent.financial_scope_policies",
            imported_modules(module_trees["owner"]),
        )
        scope_tree = ast.parse(
            (repo_root / "src" / "agent" / "financial_scope_policies.py").read_text(
                encoding="utf-8-sig"
            )
        )
        self.assertNotIn(
            "src.agent.financial_graph_helpers",
            imported_modules(scope_tree),
        )

        graph_load_counts = {
            name: sum(
                isinstance(node, ast.Name)
                and isinstance(node.ctx, ast.Load)
                and node.id == name
                for node in ast.walk(module_trees["graph"])
            )
            for name in ("_extract_segment_labels_from_query", "_report_scope_source_receipts")
        }
        self.assertEqual(
            graph_load_counts,
            {"_extract_segment_labels_from_query": 0, "_report_scope_source_receipts": 0},
        )

        baseline = json.loads(
            (repo_root / "tests" / "fixtures" / "runtime_domain_terms_baseline.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(len(baseline["records"]), 218)
        selected_ranges = [
            (node.lineno, node.end_lineno)
            for module_name, _class_stack, node in definitions.values()
            if module_name == "owner"
        ]
        selected_source = "\n".join(
            ast.get_source_segment(module_sources["owner"], node) or ""
            for module_name, _class_stack, node in definitions.values()
            if module_name == "owner"
        )
        self.assertEqual(
            [
                record
                for record in baseline["records"]
                if record.get("path") == "src/agent/financial_graph_helpers.py"
                and str(record.get("text") or "") in selected_source
                and any(
                    start <= line <= end
                    for line in record.get("first_lines") or []
                    for start, end in selected_ranges
                )
            ],
            [],
        )


    def test_current_source_llm_plan_builder_pins_validator_segment_scope_order_and_stop(self) -> None:
        nested = {"preserve": True}
        concept_spec = {
            "concept": "revenue",
            "name": "Revenue",
            "aliases": ["sales"],
            "preferred_statement_types": ["income_statement"],
            "preferred_sections": ["summary"],
            "nested": nested,
        }
        raw_operand = SimpleNamespace(concept="revenue", role="addend_1")
        raw_task = SimpleNamespace(
            operation_family="sum",
            metric_label="Revenue total",
            operands=[raw_operand],
        )
        planned = SimpleNamespace(
            tasks=[raw_task],
            companies=["LLM Co"],
            years=[2024],
            topic="LLM Topic",
            section_filter="",
            rationale="planner reason",
        )
        ontology = SimpleNamespace(
            concept_specs=Mock(return_value=[concept_spec]),
            all_concept_specs=Mock(return_value=[concept_spec]),
            planner_guidance={"intent_cues": {"comparison": ["compare"]}},
        )
        prompt = SimpleNamespace(invoke=Mock(return_value="prompt-value"))
        structured_llm = SimpleNamespace(invoke=Mock(return_value=planned))
        llm = SimpleNamespace(with_structured_output=Mock(return_value=structured_llm))
        agent = SimpleNamespace(
            _llm_for_phase=Mock(return_value=llm),
        )
        events = []
        validated_spec = {**concept_spec, "role": "addend_1"}
        segmented_spec = {
            **validated_spec,
            "name": "North Revenue",
            "binding_policy": {"segment_label": "North"},
        }
        normalized_operand = {
            "concept": "revenue",
            "role": "addend_1",
            "label": "North Revenue",
            "nested": nested,
        }

        def validate_owner(*args, **kwargs):
            events.append(("validate", args, kwargs))
            return True, "ok"

        def segment_owner(**kwargs):
            events.append(("segment", kwargs))
            return [segmented_spec]

        def operand_owner(*args):
            events.append(("operands", args))
            return [normalized_operand]

        def align_owner(**kwargs):
            events.append(("scope", kwargs))
            return ["Aligned Co"], [2025]

        validate_mock = Mock(side_effect=validate_owner)
        align_mock = Mock(side_effect=align_owner)
        report_scope = {"company": "Scope Co", "year": 2024, "nested": nested}
        before_scope = deepcopy(report_scope)
        before_spec = deepcopy(concept_spec)
        before_task = deepcopy(raw_task)
        segment_mock = Mock(side_effect=segment_owner)
        operand_mock = Mock(side_effect=operand_owner)
        with (
            patch.object(financial_graph_planning, "get_financial_ontology", return_value=ontology),
            patch.object(
                financial_graph_planning,
                "_chat_prompt_template_from_template",
                return_value=prompt,
            ),
            patch.object(financial_graph_planning, "_concept_planner_output_model", return_value=object()),
            patch.object(
                financial_graph_planning,
                "validate_concept_planner_task",
                validate_mock,
            ),
            patch.object(
                financial_graph_planning,
                "apply_segment_labels_to_llm_resolved_specs",
                segment_mock,
            ),
            patch.object(financial_graph_planning, "align_scope_hints", align_mock),
            patch.object(
                financial_graph_planning,
                "_build_concept_required_operands",
                operand_mock,
            ),
            patch.object(
                financial_graph_planning,
                "_infer_statement_and_section_hints",
                return_value=(["query_statement"], ["query_section"]),
            ),
            patch.object(
                financial_graph_planning,
                "_build_concept_task_constraints",
                return_value={"segment_scope": "segment"},
            ),
            patch.object(
                financial_graph_planning,
                "_build_generic_retrieval_queries",
                return_value=["retrieval-query"],
            ),
            patch.object(
                financial_graph_planning,
                "_build_metric_task_query",
                return_value="task-query",
            ),
            patch.object(
                financial_graph_planning,
                "infer_concept_ratio_result_unit",
                return_value="KRW",
            ),
            patch.object(
                financial_graph_planning,
                "_annotate_task_dependencies",
                side_effect=lambda tasks, **_kwargs: [dict(task) for task in tasks],
            ),
            patch.object(
                financial_graph_planning,
                "_project_logical_tasks_from_execution_tasks",
                side_effect=lambda tasks, _execution: [dict(task) for task in tasks],
            ),
        ):
            result = financial_graph_planning.FinancialAgentPlanningMixin._build_llm_concept_numeric_plan(
                agent,
                query="query",
                topic="topic",
                intent="comparison",
                report_scope=report_scope,
            )

            self.assertEqual([event[0] for event in events], ["validate", "segment", "operands", "scope"])
            validate_args, validate_kwargs = events[0][1], events[0][2]
            self.assertIs(validate_args[0], raw_task)
            self.assertIs(validate_args[1], ontology)
            self.assertEqual(validate_kwargs["allowed_concept_keys"], {"revenue"})
            self.assertEqual(validate_kwargs["concept_specs_by_key"], {"revenue": concept_spec})
            self.assertEqual(validate_kwargs["support_text"], "query")
            self.assertIs(validate_kwargs["require_surface_contract_match"], False)
            segment_kwargs = events[1][1]
            self.assertEqual(
                {key: segment_kwargs[key] for key in ("query", "metric_label", "operation_family")},
                {"query": "query", "metric_label": "Revenue total", "operation_family": "sum"},
            )
            self.assertIs(segment_kwargs["report_scope"], report_scope)
            self.assertEqual(segment_kwargs["resolved_specs"], [validated_spec])
            self.assertIsNot(segment_kwargs["resolved_specs"][0], concept_spec)
            self.assertIs(segment_kwargs["resolved_specs"][0]["nested"], nested)
            self.assertEqual(events[2][1], ("query", report_scope, [segmented_spec], "sum"))
            self.assertIs(events[2][1][1], report_scope)
            self.assertIs(events[2][1][2][0], segmented_spec)
            self.assertEqual(
                events[3][1],
                {
                    "companies": ["LLM Co"],
                    "years": [2024],
                    "report_scope": report_scope,
                },
            )
            self.assertEqual(result["companies"], ["Aligned Co"])
            self.assertEqual(result["years"], [2025])
            self.assertEqual(result["tasks"][0]["required_operands"], [normalized_operand])
            self.assertEqual(result["tasks"][0]["constraints"], {"segment_scope": "segment"})
            self.assertEqual(result["tasks"][0]["retrieval_queries"], ["retrieval-query"])
            self.assertEqual(result["tasks"][0]["result_unit"], "KRW")
            self.assertIn("planner reason", result["planner_notes"])
            self.assertEqual(report_scope, before_scope)
            self.assertIs(report_scope["nested"], nested)
            self.assertEqual(concept_spec, before_spec)
            self.assertIs(concept_spec["nested"], nested)
            self.assertEqual(raw_task, before_task)

            events.clear()
            validate_mock.side_effect = RuntimeError("validation failed")
            align_mock.reset_mock()
            segment_mock.reset_mock()
            operand_mock.reset_mock()
            with self.assertRaisesRegex(RuntimeError, "validation failed"):
                financial_graph_planning.FinancialAgentPlanningMixin._build_llm_concept_numeric_plan(
                    agent,
                    query="query",
                    topic="topic",
                    intent="comparison",
                    report_scope=report_scope,
                )
            segment_mock.assert_not_called()
            operand_mock.assert_not_called()
            align_mock.assert_not_called()

            validate_mock.side_effect = validate_owner
            segment_mock.side_effect = RuntimeError("segment projection failed")
            align_mock.reset_mock()
            with self.assertRaisesRegex(RuntimeError, "segment projection failed"):
                financial_graph_planning.FinancialAgentPlanningMixin._build_llm_concept_numeric_plan(
                    agent,
                    query="query",
                    topic="topic",
                    intent="comparison",
                    report_scope=report_scope,
                )
            align_mock.assert_not_called()


    def test_current_source_scope_and_shape_callers_pin_args_adoption_order_and_stop(self) -> None:
        nested = {"preserve": True}
        report_scope = {"company": "Scope Co", "year": 2024, "nested": nested}
        state = {
            "query": "Compare 2024 and 2023 revenue",
            "report_scope": report_scope,
            "nested": nested,
        }
        before_state = deepcopy(state)
        align_owner = Mock(return_value=(["Aligned Co"], [2025, 2024]))
        extract_agent = SimpleNamespace()
        with (
            patch.object(financial_graph_planning, "align_scope_hints", align_owner),
            patch.object(financial_graph_planning.logger, "info") as logger_info,
        ):
            extracted = financial_graph_planning.FinancialAgentPlanningMixin._extract_entities(
                extract_agent,
                state,
            )
        self.assertEqual(extracted["companies"], ["Aligned Co"])
        self.assertEqual(extracted["years"], [2025, 2024])
        self.assertEqual(extracted["topic"], state["query"])
        self.assertEqual(
            align_owner.call_args.kwargs,
            {
                "companies": [],
                "years": [2024, 2023],
                "report_scope": report_scope,
            },
        )
        passed_scope = align_owner.call_args.kwargs["report_scope"]
        self.assertIsNot(passed_scope, report_scope)
        self.assertIs(passed_scope["nested"], nested)
        logger_info.assert_called_once()
        self.assertEqual(state, before_state)
        self.assertIs(state["nested"], nested)

        failing_align = Mock(side_effect=RuntimeError("entity scope failed"))
        with (
            patch.object(financial_graph_planning, "align_scope_hints", failing_align),
            patch.object(financial_graph_planning.logger, "info") as logger_info,
        ):
            with self.assertRaisesRegex(RuntimeError, "entity scope failed"):
                financial_graph_planning.FinancialAgentPlanningMixin._extract_entities(
                    extract_agent,
                    state,
                )
        logger_info.assert_not_called()

        narrative_task = {
            "task_id": "task_1",
            "metric_family": "narrative_summary",
            "retrieval_queries": ["narrative-query"],
            "nested": nested,
        }
        narrative_align = Mock(return_value=(["Narrative Co"], [2024]))
        narrative_agent = SimpleNamespace()
        narrative_artifact = Mock(
            return_value={"tasks": ["task-ledger"], "artifacts": ["artifact-ledger"]}
        )
        narrative_state = {
            "companies": ["State Co"],
            "years": [2023],
            "tasks": ["existing-task"],
            "artifacts": ["existing-artifact"],
            "nested": nested,
        }
        before_narrative_state = deepcopy(narrative_state)
        with (
            patch.object(
                financial_graph_planning,
                "exclusive_narrative_task_policy_active",
                return_value=True,
            ),
            patch.object(
                financial_graph_planning,
                "build_hybrid_narrative_subtask",
                return_value=narrative_task,
            ),
            patch.object(
                financial_graph_planning,
                "_semantic_plan_artifact_update",
                narrative_artifact,
            ),
            patch.object(financial_graph_planning, "align_scope_hints", narrative_align),
        ):
            narrative_result = (
                financial_graph_planning.FinancialAgentPlanningMixin._plan_exclusive_narrative_task(
                    narrative_agent,
                    narrative_state,
                    query="query",
                    topic="topic",
                    intent="qa",
                    report_scope=report_scope,
                    plan_loop_count=2,
                )
            )
        self.assertEqual(
            narrative_align.call_args.kwargs,
            {
                "companies": ["State Co"],
                "years": [2023],
                "report_scope": report_scope,
            },
        )
        self.assertIs(narrative_align.call_args.kwargs["report_scope"], report_scope)
        self.assertEqual(narrative_result["companies"], ["Narrative Co"])
        self.assertEqual(narrative_result["years"], [2024])
        self.assertIs(narrative_result["active_subtask"], narrative_task)
        self.assertEqual(narrative_result["tasks"], ["task-ledger"])
        self.assertEqual(narrative_result["artifacts"], ["artifact-ledger"])
        self.assertEqual(narrative_state, before_narrative_state)
        self.assertIs(narrative_state["nested"], nested)

        failing_narrative_align = Mock(side_effect=RuntimeError("narrative scope failed"))
        narrative_artifact.reset_mock()
        with (
            patch.object(
                financial_graph_planning,
                "exclusive_narrative_task_policy_active",
                return_value=True,
            ),
            patch.object(
                financial_graph_planning,
                "build_hybrid_narrative_subtask",
                return_value=narrative_task,
            ),
            patch.object(
                financial_graph_planning,
                "_semantic_plan_artifact_update",
                narrative_artifact,
            ),
            patch.object(
                financial_graph_planning,
                "align_scope_hints",
                failing_narrative_align,
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "narrative scope failed"):
                financial_graph_planning.FinancialAgentPlanningMixin._plan_exclusive_narrative_task(
                    narrative_agent,
                    narrative_state,
                    query="query",
                    topic="topic",
                    intent="qa",
                    report_scope=report_scope,
                    plan_loop_count=2,
                )
        narrative_artifact.assert_not_called()

        def make_plan(label):
            return {
                "status": "concept_fallback",
                "tasks": [
                    {
                        "task_id": "task_1",
                        "metric_family": label,
                        "operation_family": "sum",
                        "retrieval_queries": [f"{label}-query"],
                        "nested": nested,
                    }
                ],
                "planner_notes": [label],
                "companies": [f"{label} Co"],
                "years": [2024],
                "topic": f"{label} Topic",
                "section_filter": f"{label} Section",
            }

        base_plan = make_plan("base")
        llm_plan = make_plan("llm")
        initial_events = []
        initial_agent = SimpleNamespace(
            _plan_exclusive_narrative_task=Mock(return_value={}),
            _build_llm_concept_numeric_plan=Mock(return_value=llm_plan),
        )
        initial_align = Mock(
            side_effect=lambda **kwargs: initial_events.append(("scope", kwargs))
            or (["Final Co"], [2026])
        )
        segment_shape = Mock(
            side_effect=lambda base, llm: initial_events.append(("segment-shape", base, llm))
            or True
        )
        analysis_shape = Mock(
            side_effect=lambda base, llm: initial_events.append(("analysis-shape", base, llm))
            or True
        )
        artifact_owner = Mock(
            side_effect=lambda **kwargs: initial_events.append(("artifact", kwargs))
            or {"tasks": ["ledger-task"], "artifacts": ["ledger-artifact"]}
        )
        initial_state = {
            "query": "query",
            "intent": "comparison",
            "query_type": "comparison",
            "topic": "topic",
            "report_scope": report_scope,
            "target_metric_family": "",
            "target_metric_family_hint": "",
            "companies": ["State Co"],
            "years": [2023],
            "tasks": [],
            "artifacts": [],
            "nested": nested,
        }
        before_initial_state = deepcopy(initial_state)
        with (
            patch.object(financial_graph_planning, "_build_semantic_numeric_plan", return_value=base_plan),
            patch.object(financial_graph_planning, "llm_plan_preserves_segment_sum_shape", segment_shape),
            patch.object(financial_graph_planning, "llm_plan_preserves_analysis_shape", analysis_shape),
            patch.object(financial_graph_planning, "align_scope_hints", initial_align),
            patch.object(
                financial_graph_planning,
                "append_hybrid_narrative_task",
                side_effect=lambda tasks, **_kwargs: list(tasks),
            ),
            patch.object(
                financial_graph_planning,
                "_annotate_task_dependencies",
                side_effect=lambda tasks, **_kwargs: [dict(task) for task in tasks],
            ),
            patch.object(
                financial_graph_planning,
                "push_narrative_tasks_after_numeric",
                side_effect=lambda tasks: list(tasks),
            ),
            patch.object(
                financial_graph_planning,
                "_project_logical_tasks_from_execution_tasks",
                side_effect=lambda logical, _execution: [dict(task) for task in logical],
            ),
            patch.object(financial_graph_planning, "_semantic_plan_artifact_update", artifact_owner),
        ):
            initial_result = financial_graph_planning.FinancialAgentPlanningMixin._plan_semantic_numeric_tasks(
                initial_agent,
                initial_state,
            )
        self.assertEqual(
            [event[0] for event in initial_events],
            ["segment-shape", "analysis-shape", "scope", "artifact"],
        )
        self.assertIs(initial_events[0][1], base_plan)
        self.assertIs(initial_events[0][2], llm_plan)
        self.assertIs(initial_events[1][1], base_plan)
        self.assertIs(initial_events[1][2], llm_plan)
        self.assertEqual(
            initial_events[2][1],
            {
                "companies": ["llm Co"],
                "years": [2024],
                "report_scope": report_scope,
            },
        )
        self.assertEqual(initial_result["companies"], ["Final Co"])
        self.assertEqual(initial_result["years"], [2026])
        self.assertEqual(initial_result["semantic_plan"]["planner_notes"], ["llm"])
        self.assertEqual(initial_result["calc_subtasks"][0]["metric_family"], "llm")
        self.assertEqual(initial_result["tasks"], ["ledger-task"])
        self.assertEqual(initial_result["artifacts"], ["ledger-artifact"])
        self.assertEqual(initial_state, before_initial_state)
        self.assertIs(initial_state["nested"], nested)

        short_circuit_base = make_plan("short-base")
        short_circuit_llm = make_plan("short-llm")
        initial_agent._build_llm_concept_numeric_plan = Mock(return_value=short_circuit_llm)
        short_align = Mock(return_value=(["Base Co"], [2024]))
        segment_shape = Mock(return_value=False)
        analysis_shape = Mock(side_effect=AssertionError("analysis shape accessed"))
        with (
            patch.object(
                financial_graph_planning,
                "_build_semantic_numeric_plan",
                return_value=short_circuit_base,
            ),
            patch.object(financial_graph_planning, "llm_plan_preserves_segment_sum_shape", segment_shape),
            patch.object(financial_graph_planning, "llm_plan_preserves_analysis_shape", analysis_shape),
            patch.object(financial_graph_planning, "align_scope_hints", short_align),
            patch.object(
                financial_graph_planning,
                "append_hybrid_narrative_task",
                side_effect=lambda tasks, **_kwargs: list(tasks),
            ),
            patch.object(
                financial_graph_planning,
                "_annotate_task_dependencies",
                side_effect=lambda tasks, **_kwargs: [dict(task) for task in tasks],
            ),
            patch.object(
                financial_graph_planning,
                "push_narrative_tasks_after_numeric",
                side_effect=lambda tasks: list(tasks),
            ),
            patch.object(
                financial_graph_planning,
                "_project_logical_tasks_from_execution_tasks",
                side_effect=lambda logical, _execution: [dict(task) for task in logical],
            ),
            patch.object(
                financial_graph_planning,
                "_semantic_plan_artifact_update",
                return_value={"tasks": [], "artifacts": []},
            ),
        ):
            rejected_result = financial_graph_planning.FinancialAgentPlanningMixin._plan_semantic_numeric_tasks(
                initial_agent,
                initial_state,
            )
        analysis_shape.assert_not_called()
        self.assertEqual(rejected_result["calc_subtasks"][0]["metric_family"], "short-base")
        self.assertIn(
            "concept_llm_plan_rejected_shape",
            rejected_result["semantic_plan"]["planner_notes"],
        )

        exception_base = make_plan("exception-base")
        exception_llm = make_plan("exception-llm")
        initial_agent._build_llm_concept_numeric_plan = Mock(return_value=exception_llm)
        exception_align = Mock(side_effect=AssertionError("scope accessed"))
        analysis_shape = Mock(side_effect=AssertionError("analysis accessed"))
        artifact_owner = Mock(side_effect=AssertionError("artifact accessed"))
        with (
            patch.object(
                financial_graph_planning,
                "_build_semantic_numeric_plan",
                return_value=exception_base,
            ),
            patch.object(
                financial_graph_planning,
                "llm_plan_preserves_segment_sum_shape",
                side_effect=RuntimeError("shape validation failed"),
            ),
            patch.object(financial_graph_planning, "llm_plan_preserves_analysis_shape", analysis_shape),
            patch.object(financial_graph_planning, "align_scope_hints", exception_align),
            patch.object(financial_graph_planning, "_semantic_plan_artifact_update", artifact_owner),
        ):
            with self.assertRaisesRegex(RuntimeError, "shape validation failed"):
                financial_graph_planning.FinancialAgentPlanningMixin._plan_semantic_numeric_tasks(
                    initial_agent,
                    initial_state,
                )
        analysis_shape.assert_not_called()
        exception_align.assert_not_called()
        artifact_owner.assert_not_called()

        replan_task = {
            "task_id": "task_1",
            "metric_family": "existing",
            "retrieval_queries": ["existing-query"],
        }
        replan_llm = {
            "status": "concept_fallback",
            "tasks": [],
            "planner_notes": ["llm-replan"],
            "companies": ["Replan Co"],
            "years": [2025],
            "topic": "Replan Topic",
            "section_filter": "Replan Section",
        }
        replan_agent = SimpleNamespace(
            _plan_exclusive_narrative_task=Mock(return_value={}),
            _build_llm_concept_numeric_plan=Mock(return_value=replan_llm),
            _append_replanned_tasks=Mock(return_value=([replan_task], [])),
        )
        replan_align = Mock(return_value=(["Aligned Replan"], [2025]))
        replan_artifact = Mock(return_value={"tasks": [], "artifacts": []})
        replan_state = {
            "query": "query",
            "intent": "comparison",
            "query_type": "comparison",
            "topic": "topic",
            "report_scope": report_scope,
            "planner_mode": "replan",
            "planner_feedback": "retry",
            "plan_loop_count": 1,
            "semantic_plan": {"status": "concept_fallback", "tasks": [replan_task]},
            "calc_subtasks": [replan_task],
            "active_subtask": replan_task,
            "active_subtask_index": 0,
            "companies": ["State Co"],
            "years": [2024],
            "tasks": [],
            "artifacts": [],
            "subtask_results": [],
        }
        with (
            patch.object(
                financial_graph_planning,
                "append_hybrid_narrative_task",
                side_effect=lambda tasks, **_kwargs: list(tasks),
            ),
            patch.object(
                financial_graph_planning,
                "_annotate_task_dependencies",
                side_effect=lambda tasks, **_kwargs: [dict(task) for task in tasks],
            ),
            patch.object(
                financial_graph_planning,
                "push_narrative_tasks_after_numeric",
                side_effect=lambda tasks: list(tasks),
            ),
            patch.object(
                financial_graph_planning,
                "_project_logical_tasks_from_execution_tasks",
                side_effect=lambda logical, _execution: [dict(task) for task in logical],
            ),
            patch.object(
                financial_graph_planning,
                "_dependency_closure_task_ids",
                return_value=set(),
            ),
            patch.object(financial_graph_planning, "_semantic_plan_artifact_update", replan_artifact),
            patch.object(financial_graph_planning, "align_scope_hints", replan_align),
        ):
            replan_result = financial_graph_planning.FinancialAgentPlanningMixin._plan_semantic_numeric_tasks(
                replan_agent,
                replan_state,
            )
        self.assertEqual(
            replan_align.call_args.kwargs,
            {
                "companies": ["Replan Co"],
                "years": [2025],
                "report_scope": report_scope,
            },
        )
        self.assertEqual(replan_result["companies"], ["Aligned Replan"])
        self.assertEqual(replan_result["years"], [2025])
        self.assertEqual(replan_result["topic"], "Replan Topic")
        self.assertEqual(replan_result["section_filter"], "Replan Section")

        failing_replan_align = Mock(side_effect=RuntimeError("replan scope failed"))
        replan_artifact.reset_mock()
        with (
            patch.object(
                financial_graph_planning,
                "append_hybrid_narrative_task",
                side_effect=lambda tasks, **_kwargs: list(tasks),
            ),
            patch.object(
                financial_graph_planning,
                "_annotate_task_dependencies",
                side_effect=lambda tasks, **_kwargs: [dict(task) for task in tasks],
            ),
            patch.object(
                financial_graph_planning,
                "push_narrative_tasks_after_numeric",
                side_effect=lambda tasks: list(tasks),
            ),
            patch.object(
                financial_graph_planning,
                "_project_logical_tasks_from_execution_tasks",
                side_effect=lambda logical, _execution: [dict(task) for task in logical],
            ),
            patch.object(
                financial_graph_planning,
                "_dependency_closure_task_ids",
                return_value=set(),
            ),
            patch.object(financial_graph_planning, "_semantic_plan_artifact_update", replan_artifact),
            patch.object(
                financial_graph_planning,
                "align_scope_hints",
                failing_replan_align,
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "replan scope failed"):
                financial_graph_planning.FinancialAgentPlanningMixin._plan_semantic_numeric_tasks(
                    replan_agent,
                    replan_state,
                )
        replan_artifact.assert_not_called()


    def test_current_source_narrative_predicates_pin_access_laziness_and_exceptions(self) -> None:
        events = []

        class RecordingTask(dict):
            def get(self, key, default=None):
                events.append(("get", key))
                return super().get(key, default)

        class FalsyStringBomb:
            def __bool__(self):
                events.append(("bool", "falsy"))
                return False

            def __str__(self):
                raise AssertionError("falsy value must not be stringified")

        def normalize(value):
            events.append(("normalize", value))
            return str(value).strip()

        task = RecordingTask(
            operation_family=" Narrative_Summary ",
            metric_family=FalsyStringBomb(),
            nested={"preserve": True},
        )
        nested = task["nested"]
        with patch.object(financial_graph_helpers, "_normalise_spaces", side_effect=normalize):
            self.assertTrue(financial_graph_helpers._is_narrative_summary_task(task))
        self.assertEqual(
            events,
            [
                ("get", "operation_family"),
                ("normalize", " Narrative_Summary "),
                ("get", "metric_family"),
                ("bool", "falsy"),
                ("normalize", ""),
            ],
        )
        self.assertEqual(task["operation_family"], " Narrative_Summary ")
        self.assertIs(task["nested"], nested)

        events.clear()
        with patch.object(financial_graph_helpers, "_normalise_spaces", side_effect=normalize):
            self.assertTrue(
                financial_graph_helpers._is_narrative_summary_task(
                    RecordingTask(operation_family="lookup", metric_family=" NARRATIVE_SUMMARY ")
                )
            )
            self.assertFalse(
                financial_graph_helpers._is_narrative_summary_task(
                    RecordingTask(operation_family="lookup", metric_family="ratio")
                )
            )
        self.assertEqual(
            [item for item in events if item[0] == "get"],
            [
                ("get", "operation_family"),
                ("get", "metric_family"),
                ("get", "operation_family"),
                ("get", "metric_family"),
            ],
        )

        class OperationGetBomb(dict):
            def get(self, key, default=None):
                if key == "operation_family":
                    raise RuntimeError("operation access failed")
                raise AssertionError("metric accessed after operation failure")

        normalizer = Mock(side_effect=AssertionError("normalizer accessed"))
        with patch.object(financial_graph_helpers, "_normalise_spaces", normalizer):
            with self.assertRaisesRegex(RuntimeError, "operation access failed"):
                financial_graph_helpers._is_narrative_summary_task(OperationGetBomb())
        normalizer.assert_not_called()

        gate = Mock(return_value=True)
        with patch.object(
            financial_graph_helpers,
            "_query_requests_narrative_context",
            gate,
        ):
            self.assertFalse(
                financial_graph_helpers._needs_hybrid_narrative_subtask(
                    "query",
                    "qa",
                )
            )
            self.assertFalse(
                financial_graph_helpers._needs_hybrid_narrative_subtask(
                    "query",
                    "Comparison",
                )
            )
            for intent in ("comparison", "trend", "numeric_fact"):
                self.assertTrue(
                    financial_graph_helpers._needs_hybrid_narrative_subtask(
                        f"{intent}-query",
                        intent,
                    )
                )
        self.assertEqual(
            [call.args for call in gate.call_args_list],
            [
                ("comparison-query",),
                ("trend-query",),
                ("numeric_fact-query",),
            ],
        )

        downstream = Mock(side_effect=RuntimeError("narrative gate failed"))
        with patch.object(
            financial_graph_helpers,
            "_query_requests_narrative_context",
            downstream,
        ):
            with self.assertRaisesRegex(RuntimeError, "narrative gate failed"):
                financial_graph_helpers._needs_hybrid_narrative_subtask(
                    "query",
                    "comparison",
                )
        downstream.assert_called_once_with("query")

        policy_events = []

        class RecordingPolicy(dict):
            def get(self, key, default=None):
                policy_events.append((dict.get(self, "name"), key))
                return dict.get(self, key, default)

        class PolicyAccessBomb(dict):
            def get(self, key, default=None):
                raise AssertionError("policy accessed after active match")

        policies = [
            RecordingPolicy(name="first", exclusive_narrative_task=False),
            RecordingPolicy(name="second", exclusive_narrative_task=True),
            PolicyAccessBomb(),
        ]
        before_policies = deepcopy(policies)
        with patch.object(
            financial_graph_helpers,
            "active_narrative_policies",
            return_value=policies,
        ) as active_owner:
            self.assertTrue(
                financial_graph_helpers.exclusive_narrative_task_policy_active(
                    "exclusive query"
                )
            )
        active_owner.assert_called_once_with("exclusive query")
        self.assertEqual(
            policy_events,
            [
                ("first", "exclusive_narrative_task"),
                ("second", "exclusive_narrative_task"),
            ],
        )
        self.assertEqual(policies, before_policies)

        with patch.object(
            financial_graph_helpers,
            "active_narrative_policies",
            side_effect=RuntimeError("policy resolution failed"),
        ):
            with self.assertRaisesRegex(RuntimeError, "policy resolution failed"):
                financial_graph_helpers.exclusive_narrative_task_policy_active(
                    "query"
                )


    def test_current_source_hybrid_builder_pins_policy_precedence_dedupe_copy_and_stop(self) -> None:
        events = []
        nested = {"preserve": True}
        report_scope = {"company": "Example", "year": 2024, "nested": nested}
        before_scope = deepcopy(report_scope)
        active_policy = {"format_preference_override": ""}

        def record(name, value):
            events.append((name, value))
            return value

        with (
            patch.object(
                financial_graph_helpers,
                "_desired_consolidation_scope",
                side_effect=lambda query, scope: record("scope", "consolidated"),
            ) as scope_owner,
            patch.object(
                financial_graph_helpers,
                "query_period_focus",
                side_effect=lambda query, default: record("period", "current"),
            ) as period_owner,
            patch.object(
                financial_graph_helpers,
                "active_narrative_policies",
                side_effect=lambda query: record("active", [active_policy]),
            ) as active_owner,
            patch.object(
                financial_graph_helpers,
                "narrative_policy_slot_groups",
                side_effect=lambda policies: record(
                    "slot-groups",
                    [{"query_terms": ["metric"]}],
                ),
            ) as slot_owner,
            patch.object(
                financial_graph_helpers,
                "default_format_preference",
                side_effect=AssertionError("default format accessed"),
            ) as default_owner,
            patch.object(
                financial_graph_helpers,
                "narrative_policy_query_suffixes",
                side_effect=lambda policies: record("suffixes", ["extra", "extra"]),
            ) as suffix_owner,
            patch.object(
                financial_graph_helpers,
                "narrative_policy_terms",
                side_effect=lambda policies, key: record("terms", ["table-section"]),
            ) as term_owner,
            patch.object(
                financial_graph_helpers,
                "narrative_policy_preferred_sections",
                side_effect=AssertionError("paragraph sections accessed"),
            ) as preferred_owner,
            patch.object(
                financial_graph_helpers,
                "_normalise_spaces",
                side_effect=lambda value: " ".join(str(value).split()),
            ),
            patch.object(
                financial_graph_helpers,
                "PLANNING_POLICY",
                {"hybrid_narrative_metric_label": "Narrative label"},
            ),
            patch.object(
                financial_graph_helpers,
                "NARRATIVE_BASE_RETRIEVAL_SUFFIXES",
                ("base",),
            ),
        ):
            table_task = financial_graph_helpers.build_hybrid_narrative_subtask(
                query=" metric   query ",
                intent="numeric_fact",
                report_scope=report_scope,
                next_task_id="task_7",
            )

        self.assertEqual(
            events[:4],
            [
                ("scope", "consolidated"),
                ("period", "current"),
                ("active", [active_policy]),
                ("slot-groups", [{"query_terms": ["metric"]}]),
            ],
        )
        self.assertEqual(table_task["task_id"], "task_7")
        self.assertEqual(table_task["metric_family"], "narrative_summary")
        self.assertEqual(table_task["metric_label"], "Narrative label")
        self.assertEqual(table_task["query"], " metric   query ")
        self.assertEqual(table_task["operation_family"], "narrative_summary")
        self.assertEqual(table_task["required_operands"], [])
        self.assertEqual(table_task["preferred_statement_types"], [])
        self.assertEqual(table_task["preferred_sections"], ["table-section"])
        self.assertEqual(
            table_task["retrieval_queries"],
            ["metric query", "metric query extra"],
        )
        self.assertEqual(
            table_task["constraints"],
            {
                "consolidation_scope": "consolidated",
                "period_focus": "current",
                "entity_scope": "unknown",
                "segment_scope": "none",
                "context_scope": "narrative",
            },
        )
        self.assertEqual(table_task["intent_override"], "qa")
        self.assertEqual(table_task["format_preference_override"], "table")
        scope_owner.assert_called_once_with(" metric   query ", report_scope)
        period_owner.assert_called_once_with(" metric   query ", "unknown")
        active_owner.assert_called_once_with(" metric   query ")
        self.assertIs(slot_owner.call_args.args[0][0], active_policy)
        default_owner.assert_not_called()
        self.assertIs(suffix_owner.call_args.args[0][0], active_policy)
        self.assertEqual(term_owner.call_args.args[1], "preferred_sections")
        self.assertIs(term_owner.call_args.args[0][0], active_policy)
        preferred_owner.assert_not_called()
        self.assertEqual(report_scope, before_scope)
        self.assertIs(report_scope["nested"], nested)

        paragraph_policy = {"format_preference_override": " PARAGRAPH "}
        default_owner = Mock(side_effect=AssertionError("default format accessed"))
        term_owner = Mock(side_effect=AssertionError("table terms accessed"))
        with (
            patch.object(financial_graph_helpers, "_desired_consolidation_scope", return_value="separate"),
            patch.object(financial_graph_helpers, "query_period_focus", return_value="prior"),
            patch.object(financial_graph_helpers, "active_narrative_policies", return_value=[paragraph_policy]),
            patch.object(financial_graph_helpers, "narrative_policy_slot_groups", return_value=[]),
            patch.object(financial_graph_helpers, "default_format_preference", default_owner),
            patch.object(
                financial_graph_helpers,
                "narrative_policy_query_suffixes",
                return_value=["policy", "base"],
            ),
            patch.object(financial_graph_helpers, "narrative_policy_terms", term_owner),
            patch.object(
                financial_graph_helpers,
                "narrative_policy_preferred_sections",
                return_value=["paragraph-section"],
            ) as preferred_owner,
            patch.object(
                financial_graph_helpers,
                "_normalise_spaces",
                side_effect=lambda value: " ".join(str(value).split()),
            ),
            patch.object(financial_graph_helpers, "PLANNING_POLICY", {}),
            patch.object(financial_graph_helpers, "NARRATIVE_BASE_RETRIEVAL_SUFFIXES", ("base",)),
        ):
            paragraph_task = financial_graph_helpers.build_hybrid_narrative_subtask(
                query="query",
                intent="trend",
                report_scope=report_scope,
                next_task_id="task_8",
            )
        self.assertEqual(paragraph_task["format_preference_override"], "paragraph")
        self.assertEqual(
            paragraph_task["retrieval_queries"],
            ["query", "query base", "query policy"],
        )
        self.assertEqual(paragraph_task["preferred_sections"], ["paragraph-section"])
        default_owner.assert_not_called()
        term_owner.assert_not_called()
        self.assertIs(preferred_owner.call_args.args[0][0], paragraph_policy)

        period_owner = Mock(side_effect=AssertionError("period accessed"))
        active_owner = Mock(side_effect=AssertionError("policies accessed"))
        with (
            patch.object(
                financial_graph_helpers,
                "_desired_consolidation_scope",
                side_effect=RuntimeError("scope failed"),
            ),
            patch.object(financial_graph_helpers, "query_period_focus", period_owner),
            patch.object(financial_graph_helpers, "active_narrative_policies", active_owner),
        ):
            with self.assertRaisesRegex(RuntimeError, "scope failed"):
                financial_graph_helpers.build_hybrid_narrative_subtask(
                    query="query",
                    intent="trend",
                    report_scope=report_scope,
                    next_task_id="task_9",
                )
        period_owner.assert_not_called()
        active_owner.assert_not_called()


    def test_current_source_hybrid_append_pins_copy_task_ids_gates_and_exceptions(self) -> None:
        nested = {"preserve": True}
        tasks = [
            {"task_id": "task_2", "operation_family": "sum", "nested": nested},
            {"task_id": "invalid", "operation_family": "lookup"},
        ]
        before = deepcopy(tasks)
        predicate = Mock(side_effect=AssertionError("predicate accessed"))
        builder = Mock(side_effect=AssertionError("builder accessed"))
        with (
            patch.object(
                financial_graph_helpers,
                "_needs_hybrid_narrative_subtask",
                return_value=False,
            ) as gate,
            patch.object(financial_graph_helpers, "_is_narrative_summary_task", predicate),
            patch.object(financial_graph_helpers, "build_hybrid_narrative_subtask", builder),
        ):
            unchanged = financial_graph_helpers.append_hybrid_narrative_task(
                tasks,
                query="query",
                intent="qa",
                report_scope={"company": "Example"},
            )
        gate.assert_called_once_with("query", "qa")
        predicate.assert_not_called()
        builder.assert_not_called()
        self.assertEqual(unchanged, tasks)
        self.assertIsNot(unchanged, tasks)
        self.assertIsNot(unchanged[0], tasks[0])
        self.assertIs(unchanged[0]["nested"], nested)
        self.assertEqual(tasks, before)
        self.assertIs(tasks[0]["nested"], nested)

        existing_narrative = [
            {"task_id": "task_4", "operation_family": "sum"},
            {"task_id": "task_5", "metric_family": "narrative_summary"},
        ]
        seen = []

        def is_narrative(task):
            seen.append(task)
            return task.get("metric_family") == "narrative_summary"

        builder = Mock(side_effect=AssertionError("builder accessed"))
        with (
            patch.object(financial_graph_helpers, "_needs_hybrid_narrative_subtask", return_value=True),
            patch.object(financial_graph_helpers, "_is_narrative_summary_task", side_effect=is_narrative),
            patch.object(financial_graph_helpers, "build_hybrid_narrative_subtask", builder),
        ):
            existing_result = financial_graph_helpers.append_hybrid_narrative_task(
                existing_narrative,
                query="query",
                intent="trend",
                report_scope={},
            )
        self.assertEqual(existing_result, existing_narrative)
        self.assertEqual(len(seen), 2)
        self.assertIsNot(seen[0], existing_narrative[0])
        self.assertIsNot(seen[1], existing_narrative[1])
        builder.assert_not_called()

        source_tasks = [
            {"task_id": "task_7", "operation_family": "sum", "nested": nested},
            {"task_id": "task_3", "operation_family": "lookup"},
            {"task_id": "task_bad", "operation_family": "difference"},
        ]
        report_scope = {"company": "Example", "nested": nested}
        before_tasks = deepcopy(source_tasks)
        before_scope = deepcopy(report_scope)
        built = {"task_id": "task_8", "operation_family": "narrative_summary", "nested": nested}
        predicate = Mock(return_value=False)
        builder = Mock(return_value=built)
        with (
            patch.object(financial_graph_helpers, "_needs_hybrid_narrative_subtask", return_value=True) as gate,
            patch.object(financial_graph_helpers, "_is_narrative_summary_task", predicate),
            patch.object(financial_graph_helpers, "build_hybrid_narrative_subtask", builder),
        ):
            appended = financial_graph_helpers.append_hybrid_narrative_task(
                source_tasks,
                query="query",
                intent="comparison",
                report_scope=report_scope,
            )
        gate.assert_called_once_with("query", "comparison")
        self.assertEqual(len(predicate.call_args_list), 3)
        self.assertTrue(
            all(
                call.args[0] is not original
                for call, original in zip(predicate.call_args_list, source_tasks)
            )
        )
        self.assertEqual(
            builder.call_args.kwargs,
            {
                "query": "query",
                "intent": "comparison",
                "report_scope": report_scope,
                "next_task_id": "task_8",
            },
        )
        self.assertIs(builder.call_args.kwargs["report_scope"], report_scope)
        self.assertEqual(appended[:-1], source_tasks)
        self.assertIs(appended[-1], built)
        self.assertIsNot(appended[0], source_tasks[0])
        self.assertIs(appended[0]["nested"], nested)
        self.assertEqual(source_tasks, before_tasks)
        self.assertEqual(report_scope, before_scope)
        self.assertIs(source_tasks[0]["nested"], nested)
        self.assertIs(report_scope["nested"], nested)

        predicate = Mock(side_effect=AssertionError("predicate accessed"))
        builder = Mock(side_effect=AssertionError("builder accessed"))
        with (
            patch.object(
                financial_graph_helpers,
                "_needs_hybrid_narrative_subtask",
                side_effect=RuntimeError("gate failed"),
            ),
            patch.object(financial_graph_helpers, "_is_narrative_summary_task", predicate),
            patch.object(financial_graph_helpers, "build_hybrid_narrative_subtask", builder),
        ):
            with self.assertRaisesRegex(RuntimeError, "gate failed"):
                financial_graph_helpers.append_hybrid_narrative_task(
                    source_tasks,
                    query="query",
                    intent="comparison",
                    report_scope=report_scope,
                )
        predicate.assert_not_called()
        builder.assert_not_called()


    def test_current_source_narrative_ordering_pins_dependencies_copies_and_exceptions(self) -> None:
        nested = {"preserve": True}
        tasks = [
            {
                "task_id": "task_3",
                "metric_family": "narrative_summary",
                "depends_on": [" task_1 ", "", "task_1"],
                "nested": nested,
            },
            {"task_id": "task_2", "operation_family": "sum"},
            {"task_id": "task_1", "operation_family": "lookup"},
        ]
        before = deepcopy(tasks)
        ordered = financial_graph_helpers.push_narrative_tasks_after_numeric(tasks)
        self.assertEqual(
            [task["task_id"] for task in ordered],
            ["task_2", "task_1", "task_3"],
        )
        self.assertEqual(ordered[-1]["depends_on"], ["task_1", "task_1", "task_2"])
        self.assertIsNot(ordered, tasks)
        self.assertTrue(all(result is not source for result, source in zip(
            sorted(ordered, key=lambda item: item["task_id"]),
            sorted(tasks, key=lambda item: item["task_id"]),
        )))
        narrative_result = next(task for task in ordered if task["task_id"] == "task_3")
        self.assertIs(narrative_result["nested"], nested)
        self.assertEqual(tasks, before)
        self.assertIs(tasks[0]["nested"], nested)

        only_narrative = [
            {
                "task_id": "task_n",
                "operation_family": "narrative_summary",
                "depends_on": [" untouched "],
                "nested": nested,
            }
        ]
        only_result = financial_graph_helpers.push_narrative_tasks_after_numeric(only_narrative)
        self.assertEqual(only_result, only_narrative)
        self.assertIsNot(only_result, only_narrative)
        self.assertIsNot(only_result[0], only_narrative[0])
        self.assertEqual(only_result[0]["depends_on"], [" untouched "])
        self.assertIs(only_result[0]["nested"], nested)

        already_ordered = [
            {"task_id": "task_n", "operation_family": "narrative_summary", "depends_on": [" task_1 "]},
            {"task_id": "task_1", "operation_family": "sum"},
        ]
        no_change = financial_graph_helpers.push_narrative_tasks_after_numeric(already_ordered)
        self.assertEqual([task["task_id"] for task in no_change], ["task_n", "task_1"])
        self.assertEqual(no_change[0]["depends_on"], ["task_1"])
        self.assertIsNot(no_change[0], already_ordered[0])
        self.assertEqual(already_ordered[0]["depends_on"], [" task_1 "])

        predicate = Mock(side_effect=RuntimeError("classification failed"))
        with patch.object(
            financial_graph_helpers,
            "_is_narrative_summary_task",
            predicate,
        ):
            with self.assertRaisesRegex(RuntimeError, "classification failed"):
                financial_graph_helpers.push_narrative_tasks_after_numeric(tasks)
        predicate.assert_called_once()
        self.assertIsNot(predicate.call_args.args[0], tasks[0])
        self.assertEqual(tasks, before)
        self.assertIs(tasks[0]["nested"], nested)


    def test_current_source_narrative_policy_bindings_pin_defs_calls_dag_imports_and_baseline(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        module_paths = {
            "graph": repo_root / "src" / "agent" / "financial_graph_planning.py",
            "owner": repo_root / "src" / "agent" / "financial_graph_helpers.py",
        }
        module_sources = {
            name: path.read_text(encoding="utf-8-sig")
            for name, path in module_paths.items()
        }
        module_trees = {name: ast.parse(source) for name, source in module_sources.items()}
        targets = {
            "is_narrative": "_is_narrative_summary_task",
            "needs_hybrid": "_needs_hybrid_narrative_subtask",
            "build": "build_hybrid_narrative_subtask",
            "append": "append_hybrid_narrative_task",
            "push": "push_narrative_tasks_after_numeric",
            "exclusive": "exclusive_narrative_task_policy_active",
        }
        public_after_move = {
            "build_hybrid_narrative_subtask",
            "append_hybrid_narrative_task",
            "push_narrative_tasks_after_numeric",
            "exclusive_narrative_task_policy_active",
        }
        key_by_name = {name: key for key, name in targets.items()}
        definitions = {}
        calls = {key: [] for key in targets}
        try_depths = {key: [] for key in targets}

        class BindingVisitor(ast.NodeVisitor):
            def __init__(self, module_name):
                self.module_name = module_name
                self.function_stack = []
                self.class_stack = []
                self.try_depth = 0

            def visit_ClassDef(self, node):
                self.class_stack.append(node.name)
                self.generic_visit(node)
                self.class_stack.pop()

            def visit_FunctionDef(self, node):
                if node.name in key_by_name:
                    definitions[node.name] = (
                        self.module_name,
                        tuple(self.class_stack),
                        node,
                    )
                self.function_stack.append(node.name)
                self.generic_visit(node)
                self.function_stack.pop()

            visit_AsyncFunctionDef = visit_FunctionDef

            def visit_Try(self, node):
                self.try_depth += 1
                self.generic_visit(node)
                self.try_depth -= 1

            visit_TryStar = visit_Try

            def visit_Call(self, node):
                called_name = (
                    node.func.id
                    if isinstance(node.func, ast.Name)
                    else node.func.attr
                    if isinstance(node.func, ast.Attribute)
                    else ""
                )
                key = key_by_name.get(called_name)
                if key:
                    calls[key].append(
                        (
                            self.module_name,
                            tuple(self.function_stack),
                            ast.unparse(node.func.value)
                            if isinstance(node.func, ast.Attribute)
                            else "",
                            tuple(ast.unparse(argument) for argument in node.args),
                            tuple(
                                (keyword.arg, ast.unparse(keyword.value))
                                for keyword in node.keywords
                            ),
                        )
                    )
                    try_depths[key].append(self.try_depth)
                self.generic_visit(node)

        for module_name, tree in module_trees.items():
            BindingVisitor(module_name).visit(tree)

        self.assertEqual(
            {
                name: (
                    module_name,
                    class_stack,
                    node.end_lineno - node.lineno + 1,
                )
                for name, (module_name, class_stack, node) in definitions.items()
            },
            {
                "_is_narrative_summary_task": ("owner", (), 4),
                "_needs_hybrid_narrative_subtask": ("owner", (), 2),
                "build_hybrid_narrative_subtask": ("owner", (), 63),
                "append_hybrid_narrative_task": ("owner", (), 38),
                "push_narrative_tasks_after_numeric": ("owner", (), 31),
                "exclusive_narrative_task_policy_active": ("owner", (), 5),
            },
        )
        self.assertEqual(sum(
            node.end_lineno - node.lineno + 1
            for _module_name, _class_stack, node in definitions.values()
        ), 143)
        owner_top_level = {
            node.name
            for node in module_trees["owner"].body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        self.assertTrue(public_after_move.issubset(owner_top_level))
        self.assertEqual(
            (
                sum(not name.startswith("_") for name in owner_top_level),
                sum(name.startswith("_") for name in owner_top_level),
            ),
            (9, 97),
        )
        self.assertEqual(
            {key: len(entries) for key, entries in calls.items()},
            {
                "is_narrative": 5,
                "needs_hybrid": 1,
                "build": 2,
                "append": 2,
                "push": 2,
                "exclusive": 1,
            },
        )
        self.assertEqual(
            try_depths,
            {
                "is_narrative": [0, 0, 0, 0, 0],
                "needs_hybrid": [0],
                "build": [0, 0],
                "append": [0, 0],
                "push": [0, 0],
                "exclusive": [0],
            },
        )
        self.assertTrue(
            all(
                receiver == ""
                for entries in calls.values()
                for _module, _stack, receiver, _args, _keywords in entries
            )
        )
        self.assertEqual(
            [(entry[1][-1], entry[3], entry[4]) for entry in calls["needs_hybrid"]],
            [("append_hybrid_narrative_task", ("query", "intent"), ())],
        )
        self.assertEqual(
            [(entry[1][-1], entry[3], entry[4]) for entry in calls["build"]],
            [
                (
                    "_plan_exclusive_narrative_task",
                    (),
                    (
                        ("query", "query"),
                        ("intent", "intent"),
                        ("report_scope", "report_scope"),
                        ("next_task_id", "'task_1'"),
                    ),
                ),
                (
                    "append_hybrid_narrative_task",
                    (),
                    (
                        ("query", "query"),
                        ("intent", "intent"),
                        ("report_scope", "report_scope"),
                        ("next_task_id", "f'task_{next_index}'"),
                    ),
                ),
            ],
        )
        self.assertEqual(
            [(entry[1][-1], entry[3], entry[4]) for entry in calls["append"]],
            [
                (
                    "_plan_semantic_numeric_tasks",
                    ("merged_tasks",),
                    (("query", "query"), ("intent", "intent"), ("report_scope", "report_scope")),
                ),
                (
                    "_plan_semantic_numeric_tasks",
                    ("logical_tasks",),
                    (("query", "query"), ("intent", "intent"), ("report_scope", "report_scope")),
                ),
            ],
        )
        self.assertEqual(
            [(entry[1][-1], entry[3], entry[4]) for entry in calls["push"]],
            [
                ("_plan_semantic_numeric_tasks", ("execution_tasks",), ()),
                ("_plan_semantic_numeric_tasks", ("tasks",), ()),
            ],
        )

        selected_names = set(targets.values())
        planned_distribution = {}
        external = local = 0
        for key, entries in calls.items():
            local_count = sum(
                bool(selected_names.intersection(function_stack))
                for _module, function_stack, _receiver, _args, _keywords in entries
            )
            external_count = len(entries) - local_count
            planned_distribution[key] = (external_count, local_count)
            external += external_count
            local += local_count
        self.assertEqual(
            planned_distribution,
            {
                "is_narrative": (0, 5),
                "needs_hybrid": (0, 1),
                "build": (1, 1),
                "append": (2, 0),
                "push": (2, 0),
                "exclusive": (1, 0),
            },
        )
        self.assertEqual((external, local), (6, 7))

        selected_nodes = [item[2] for item in definitions.values()]
        selected_node_ids = {
            id(node)
            for definition in selected_nodes
            for node in ast.walk(definition)
        }
        dead_after_move = {
            "query_period_focus",
            "_query_requests_narrative_context",
            "_desired_consolidation_scope",
            "NARRATIVE_BASE_RETRIEVAL_SUFFIXES",
            "active_narrative_policies",
            "narrative_policy_preferred_sections",
            "narrative_policy_query_suffixes",
            "narrative_policy_slot_groups",
            "narrative_policy_terms",
            "default_format_preference",
        }
        outside_loads = {
            name: [
                node.lineno
                for node in ast.walk(module_trees["graph"])
                if isinstance(node, ast.Name)
                and isinstance(node.ctx, ast.Load)
                and node.id == name
                and id(node) not in selected_node_ids
            ]
            for name in dead_after_move
        }
        self.assertEqual(outside_loads, {name: [] for name in dead_after_move})

        def imported_modules(tree):
            modules = set()
            for node in tree.body:
                if isinstance(node, ast.ImportFrom) and node.module:
                    modules.add(node.module)
                elif isinstance(node, ast.Import):
                    modules.update(alias.name for alias in node.names)
            return modules

        owner_imports = imported_modules(module_trees["owner"])
        self.assertIn("src.config.retrieval_policy", owner_imports)
        self.assertIn("src.agent.financial_operation_policies", owner_imports)
        self.assertIn("src.agent.financial_scope_policies", owner_imports)
        self.assertIn("src.routing", owner_imports)
        self.assertNotIn("src.agent.financial_graph_planning", owner_imports)
        routing_imports = set()
        for path in (repo_root / "src" / "routing").rglob("*.py"):
            routing_imports.update(imported_modules(ast.parse(path.read_text(encoding="utf-8-sig"))))
        self.assertNotIn("src.agent.financial_graph_helpers", routing_imports)

        baseline = json.loads(
            (repo_root / "tests" / "fixtures" / "runtime_domain_terms_baseline.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(len(baseline["records"]), 218)
        selected_ranges = [(node.lineno, node.end_lineno) for node in selected_nodes]
        self.assertEqual(
            [
                record
                for record in baseline["records"]
                if record.get("path") == "src/agent/financial_graph_helpers.py"
                and any(
                    start <= line <= end
                    for line in record.get("first_lines") or []
                    for start, end in selected_ranges
                )
            ],
            [],
        )


    def test_current_source_narrative_policy_callers_pin_args_order_adoption_and_stop(self) -> None:
        nested = {"preserve": True}
        report_scope = {"company": "Example", "year": 2024, "nested": nested}
        state = {
            "companies": ["State Co"],
            "years": [2023],
            "tasks": [{"task_id": "ledger-task", "nested": nested}],
            "artifacts": [{"artifact_id": "ledger-artifact"}],
            "section_filter": "section",
            "nested": nested,
        }
        before_state = deepcopy(state)
        narrative_task = {
            "task_id": "task_1",
            "metric_family": "narrative_summary",
            "operation_family": "narrative_summary",
            "retrieval_queries": ["query", "extra", "query"],
            "nested": nested,
        }
        events = []

        def gate(query):
            events.append(("gate", query))
            return True

        def build(**kwargs):
            events.append(("build", kwargs))
            return narrative_task

        def align(**kwargs):
            events.append(("align", kwargs))
            return ["Aligned Co"], [2024]

        def artifact(**kwargs):
            events.append(("artifact", kwargs))
            return {"tasks": ["updated-task"], "artifacts": ["updated-artifact"]}

        with (
            patch.object(
                financial_graph_planning,
                "exclusive_narrative_task_policy_active",
                side_effect=gate,
            ),
            patch.object(
                financial_graph_planning,
                "build_hybrid_narrative_subtask",
                side_effect=build,
            ),
            patch.object(financial_graph_planning, "align_scope_hints", side_effect=align),
            patch.object(
                financial_graph_planning,
                "_semantic_plan_artifact_update",
                side_effect=artifact,
            ),
        ):
            exclusive = financial_graph_planning.FinancialAgentPlanningMixin._plan_exclusive_narrative_task(
                SimpleNamespace(),
                state,
                query="query",
                topic=" topic ",
                intent="trend",
                report_scope=report_scope,
                plan_loop_count=2,
            )
        self.assertEqual([event[0] for event in events], ["gate", "build", "align", "artifact"])
        self.assertEqual(
            events[1][1],
            {
                "query": "query",
                "intent": "trend",
                "report_scope": report_scope,
                "next_task_id": "task_1",
            },
        )
        self.assertIs(events[1][1]["report_scope"], report_scope)
        self.assertEqual(
            events[2][1],
            {
                "companies": ["State Co"],
                "years": [2023],
                "report_scope": report_scope,
            },
        )
        self.assertIs(events[2][1]["report_scope"], report_scope)
        artifact_kwargs = events[3][1]
        self.assertEqual(artifact_kwargs["artifact_task_id"], "task_1")
        self.assertIs(artifact_kwargs["calculation_tasks"][0], narrative_task)
        self.assertEqual(artifact_kwargs["retrieval_queries"], ["query", "extra"])
        self.assertEqual(exclusive["companies"], ["Aligned Co"])
        self.assertEqual(exclusive["years"], [2024])
        self.assertEqual(exclusive["topic"], "topic")
        self.assertIs(exclusive["calc_subtasks"][0], narrative_task)
        self.assertIs(exclusive["active_subtask"], narrative_task)
        self.assertEqual(exclusive["retrieval_queries"], ["query", "extra"])
        self.assertEqual(exclusive["tasks"], ["updated-task"])
        self.assertEqual(exclusive["artifacts"], ["updated-artifact"])
        self.assertEqual(state, before_state)
        self.assertIs(state["nested"], nested)
        self.assertIs(state["tasks"][0]["nested"], nested)

        build_owner = Mock(side_effect=AssertionError("builder accessed"))
        align_owner = Mock(side_effect=AssertionError("scope accessed"))
        artifact_owner = Mock(side_effect=AssertionError("artifact accessed"))
        with (
            patch.object(financial_graph_planning, "exclusive_narrative_task_policy_active", return_value=False),
            patch.object(financial_graph_planning, "build_hybrid_narrative_subtask", build_owner),
            patch.object(financial_graph_planning, "align_scope_hints", align_owner),
            patch.object(financial_graph_planning, "_semantic_plan_artifact_update", artifact_owner),
        ):
            self.assertEqual(
                financial_graph_planning.FinancialAgentPlanningMixin._plan_exclusive_narrative_task(
                    SimpleNamespace(),
                    state,
                    query="query",
                    topic="topic",
                    intent="trend",
                    report_scope=report_scope,
                    plan_loop_count=0,
                ),
                {},
            )
        build_owner.assert_not_called()
        align_owner.assert_not_called()
        artifact_owner.assert_not_called()

        align_owner = Mock(side_effect=AssertionError("scope accessed"))
        artifact_owner = Mock(side_effect=AssertionError("artifact accessed"))
        with (
            patch.object(financial_graph_planning, "exclusive_narrative_task_policy_active", return_value=True),
            patch.object(
                financial_graph_planning,
                "build_hybrid_narrative_subtask",
                side_effect=RuntimeError("builder failed"),
            ),
            patch.object(financial_graph_planning, "align_scope_hints", align_owner),
            patch.object(financial_graph_planning, "_semantic_plan_artifact_update", artifact_owner),
        ):
            with self.assertRaisesRegex(RuntimeError, "builder failed"):
                financial_graph_planning.FinancialAgentPlanningMixin._plan_exclusive_narrative_task(
                    SimpleNamespace(),
                    state,
                    query="query",
                    topic="topic",
                    intent="trend",
                    report_scope=report_scope,
                    plan_loop_count=0,
                )
        align_owner.assert_not_called()
        artifact_owner.assert_not_called()
        self.assertEqual(state, before_state)

        initial_nested = {"preserve": True}
        initial_task = {"task_id": "task_1", "metric_family": "base", "nested": initial_nested}
        appended_task = {"task_id": "task_2", "metric_family": "narrative_summary", "nested": initial_nested}
        execution_task = {"task_id": "task_2", "metric_family": "annotated", "nested": initial_nested}
        pushed_task = {"task_id": "task_2", "metric_family": "pushed", "nested": initial_nested}
        projected_task = {"task_id": "task_2", "metric_family": "projected", "nested": initial_nested}
        initial_plan = {
            "status": "deterministic",
            "tasks": [initial_task],
            "companies": ["Plan Co"],
            "years": [2024],
            "planner_notes": [],
        }
        initial_state = {
            "query": "query",
            "intent": "comparison",
            "topic": "topic",
            "report_scope": report_scope,
            "tasks": [],
            "artifacts": [],
            "nested": initial_nested,
        }
        before_initial = deepcopy(initial_state)
        initial_events = []

        def append_initial(tasks, **kwargs):
            initial_events.append(("append", tasks, kwargs))
            self.assertIsNot(tasks, initial_plan["tasks"])
            self.assertIs(tasks[0]["nested"], initial_nested)
            return [appended_task]

        def annotate_initial(tasks, **kwargs):
            initial_events.append(("annotate", tasks, kwargs))
            self.assertIs(tasks[0], appended_task)
            return [execution_task]

        def push_initial(tasks):
            initial_events.append(("push", tasks))
            self.assertIs(tasks[0], execution_task)
            return [pushed_task]

        def project_initial(logical, execution):
            initial_events.append(("project", logical, execution))
            self.assertIs(logical[0], appended_task)
            self.assertIs(execution[0], pushed_task)
            return [projected_task]

        def align_initial(**kwargs):
            initial_events.append(("align", kwargs))
            return ["Aligned"], [2024]

        def artifact_initial(**kwargs):
            initial_events.append(("artifact", kwargs))
            self.assertIs(kwargs["calculation_tasks"][0], pushed_task)
            return {"tasks": ["ledger"], "artifacts": ["artifact"]}

        initial_agent = SimpleNamespace(
            _plan_exclusive_narrative_task=Mock(return_value={}),
        )
        with (
            patch.object(financial_graph_planning, "_build_semantic_numeric_plan", return_value=initial_plan),
            patch.object(financial_graph_planning, "append_hybrid_narrative_task", side_effect=append_initial),
            patch.object(financial_graph_planning, "_annotate_task_dependencies", side_effect=annotate_initial),
            patch.object(financial_graph_planning, "push_narrative_tasks_after_numeric", side_effect=push_initial),
            patch.object(
                financial_graph_planning,
                "_project_logical_tasks_from_execution_tasks",
                side_effect=project_initial,
            ),
            patch.object(financial_graph_planning, "align_scope_hints", side_effect=align_initial),
            patch.object(financial_graph_planning, "_semantic_plan_artifact_update", side_effect=artifact_initial),
        ):
            initial_result = financial_graph_planning.FinancialAgentPlanningMixin._plan_semantic_numeric_tasks(
                initial_agent,
                initial_state,
            )
        self.assertEqual(
            [event[0] for event in initial_events],
            ["append", "annotate", "push", "project", "align", "artifact"],
        )
        self.assertEqual(
            initial_events[0][2],
            {"query": "query", "intent": "comparison", "report_scope": report_scope},
        )
        self.assertIsNot(initial_events[0][2]["report_scope"], report_scope)
        self.assertIs(initial_events[0][2]["report_scope"]["nested"], nested)
        self.assertEqual(initial_result["semantic_plan"]["tasks"], [projected_task])
        self.assertIs(initial_result["calc_subtasks"][0], pushed_task)
        self.assertIs(initial_result["active_subtask"]["nested"], initial_nested)
        self.assertEqual(initial_result["tasks"], ["ledger"])
        self.assertEqual(initial_state, before_initial)
        self.assertIs(initial_state["nested"], initial_nested)

        downstream = Mock(side_effect=AssertionError("dependency annotation accessed"))
        artifact_owner = Mock(side_effect=AssertionError("artifact accessed"))
        with (
            patch.object(financial_graph_planning, "_build_semantic_numeric_plan", return_value=initial_plan),
            patch.object(
                financial_graph_planning,
                "append_hybrid_narrative_task",
                side_effect=RuntimeError("append failed"),
            ),
            patch.object(financial_graph_planning, "_annotate_task_dependencies", downstream),
            patch.object(financial_graph_planning, "_semantic_plan_artifact_update", artifact_owner),
        ):
            with self.assertRaisesRegex(RuntimeError, "append failed"):
                financial_graph_planning.FinancialAgentPlanningMixin._plan_semantic_numeric_tasks(
                    initial_agent,
                    initial_state,
                )
        downstream.assert_not_called()
        artifact_owner.assert_not_called()
        self.assertEqual(initial_state, before_initial)

        replan_existing = {"task_id": "task_1", "metric_family": "existing", "nested": nested}
        replan_appended = {"task_id": "task_2", "metric_family": "patch", "nested": nested}
        replan_merged = [replan_existing, replan_appended]
        replan_hybrid = {"task_id": "task_3", "metric_family": "narrative_summary", "nested": nested}
        replan_execution = {"task_id": "task_2", "metric_family": "execution", "nested": nested}
        replan_pushed = {"task_id": "task_2", "metric_family": "ordered", "nested": nested}
        replan_projected = {"task_id": "task_2", "metric_family": "logical", "nested": nested}
        replan_state = {
            "query": "query",
            "intent": "trend",
            "topic": "topic",
            "report_scope": report_scope,
            "planner_mode": "replan",
            "planner_feedback": "retry",
            "semantic_plan": {"status": "concept_fallback", "tasks": [replan_existing]},
            "calc_subtasks": [replan_existing],
            "subtask_results": [],
            "tasks": [],
            "artifacts": [],
            "nested": nested,
        }
        before_replan = deepcopy(replan_state)
        replan_events = []
        replan_agent = SimpleNamespace(
            _plan_exclusive_narrative_task=Mock(return_value={}),
            _build_llm_concept_numeric_plan=Mock(
                return_value={
                    "status": "concept_fallback",
                    "tasks": [replan_appended],
                    "planner_notes": ["patch"],
                }
            ),
            _append_replanned_tasks=Mock(return_value=(replan_merged, [replan_appended])),
        )

        def append_replan(tasks, **kwargs):
            replan_events.append(("append", tasks, kwargs))
            self.assertIs(tasks, replan_merged)
            return [replan_hybrid]

        def annotate_replan(tasks, **kwargs):
            replan_events.append(("annotate", tasks, kwargs))
            self.assertIs(tasks[0], replan_hybrid)
            return [replan_execution]

        def push_replan(tasks):
            replan_events.append(("push", tasks))
            self.assertIs(tasks[0], replan_execution)
            return [replan_pushed]

        def project_replan(logical, execution):
            replan_events.append(("project", logical, execution))
            self.assertIs(logical[0], replan_hybrid)
            self.assertIs(execution[0], replan_pushed)
            return [replan_projected]

        with (
            patch.object(financial_graph_planning, "append_hybrid_narrative_task", side_effect=append_replan),
            patch.object(financial_graph_planning, "_annotate_task_dependencies", side_effect=annotate_replan),
            patch.object(financial_graph_planning, "push_narrative_tasks_after_numeric", side_effect=push_replan),
            patch.object(
                financial_graph_planning,
                "_project_logical_tasks_from_execution_tasks",
                side_effect=project_replan,
            ),
            patch.object(financial_graph_planning, "_dependency_closure_task_ids", return_value={"task_2"}),
            patch.object(financial_graph_planning, "align_scope_hints", return_value=([], [])),
            patch.object(
                financial_graph_planning,
                "_semantic_plan_artifact_update",
                return_value={"tasks": [], "artifacts": []},
            ),
        ):
            replan_result = financial_graph_planning.FinancialAgentPlanningMixin._plan_semantic_numeric_tasks(
                replan_agent,
                replan_state,
            )
        self.assertEqual(
            [event[0] for event in replan_events],
            ["append", "annotate", "push", "project"],
        )
        self.assertEqual(
            replan_events[0][2],
            {"query": "query", "intent": "trend", "report_scope": report_scope},
        )
        self.assertIsNot(replan_events[0][2]["report_scope"], report_scope)
        self.assertIs(replan_events[0][2]["report_scope"]["nested"], nested)
        self.assertIs(replan_result["calc_subtasks"][0], replan_pushed)
        self.assertEqual(replan_result["semantic_plan"]["tasks"], [replan_projected])
        self.assertEqual(replan_state, before_replan)
        self.assertIs(replan_state["nested"], nested)

    def test_scope_owner_period_focus_pins_precedence_access_policy_and_exceptions(self) -> None:
        events = []

        class RecordingOperand(dict):
            def get(self, key, default=None):
                events.append(("operand", key))
                return super().get(key, default)

        class RecordingPolicy:
            def __init__(self, values):
                self.values = values

            def keys(self):
                events.append(("policy", "keys"))
                return self.values.keys()

            def __getitem__(self, key):
                events.append(("policy", key))
                return self.values[key]

        policy = RecordingPolicy(
            {
                "current_period_hints": ("current", "now"),
                "prior_period_hints": ("prior", "before"),
            }
        )
        nested = {"preserve": True}
        operand = RecordingOperand(
            period_hint=" prior ",
            role="current_period",
            nested=nested,
        )
        before = deepcopy(operand)
        with patch.object(financial_scope_policies, "GENERIC_PERIOD_OPERAND_POLICY", policy):
            self.assertEqual(
                financial_scope_policies.operand_period_focus(operand, "fallback"),
                "current",
            )
        self.assertEqual(
            events,
            [
                ("operand", "period_hint"),
                ("operand", "role"),
                ("policy", "keys"),
                ("policy", "current_period_hints"),
                ("policy", "prior_period_hints"),
            ],
        )
        self.assertEqual(operand, before)
        self.assertIs(operand["nested"], nested)

        cases = [
            ({"period_hint": "current", "role": "prior_period"}, "current"),
            ({"period_hint": "prior", "role": ""}, "prior"),
            ({"period_hint": "unknown", "role": "prior_period"}, "prior"),
            ({"period_hint": " CURRENT ", "role": ""}, "fallback"),
            ({"period_hint": "", "role": ""}, "fallback"),
        ]
        plain_policy = {
            "current_period_hints": ("current",),
            "prior_period_hints": ("prior",),
        }
        with patch.object(
            financial_scope_policies,
            "GENERIC_PERIOD_OPERAND_POLICY",
            plain_policy,
        ):
            for current_operand, expected in cases:
                with self.subTest(operand=current_operand):
                    self.assertEqual(
                        financial_scope_policies.operand_period_focus(
                            current_operand,
                            "fallback",
                        ),
                        expected,
                    )

        stop_events = []

        class HintBomb:
            def __str__(self):
                stop_events.append("hint-str")
                raise RuntimeError("hint str failed")

        class RoleBomb:
            def __str__(self):
                stop_events.append("role-str")
                raise AssertionError("role should not be accessed")

        with self.assertRaisesRegex(RuntimeError, "hint str failed"):
            financial_scope_policies.operand_period_focus(
                {"period_hint": HintBomb(), "role": RoleBomb()},
                "fallback",
            )
        self.assertEqual(stop_events, ["hint-str"])

        class PolicyBomb:
            def keys(self):
                raise RuntimeError("policy copy failed")

            def __getitem__(self, key):
                raise AssertionError(key)

        with patch.object(
            financial_scope_policies,
            "GENERIC_PERIOD_OPERAND_POLICY",
            PolicyBomb(),
        ):
            with self.assertRaisesRegex(RuntimeError, "policy copy failed"):
                financial_scope_policies.operand_period_focus(
                    {"period_hint": "", "role": ""},
                    "fallback",
                )

    def test_scope_owner_target_years_pins_order_fallback_soft_conversion_and_stop(self) -> None:
        nested = {"preserve": True}
        target_accesses = []

        class RecordingOperand(dict):
            def get(self, key, default=None):
                target_accesses.append(key)
                return super().get(key, default)

        operand = RecordingOperand({
            "period_hint": "2022 2022",
            "label": "2023 2022",
            "nested": nested,
        })
        before_operand = deepcopy(operand)
        target_accesses.clear()

        class QueryYearsBomb:
            def __iter__(self):
                raise AssertionError("explicit years must skip query years")

        skipped_focus = Mock(side_effect=AssertionError("explicit years must skip focus"))
        with patch.object(
            financial_scope_policies,
            "operand_period_focus",
            skipped_focus,
        ):
            self.assertEqual(
                financial_scope_policies.operand_target_years(
                    operand,
                    QueryYearsBomb(),
                ),
                [2022, 2023],
            )
        skipped_focus.assert_not_called()
        self.assertEqual(target_accesses, ["period_hint", "label"])
        self.assertEqual(operand, before_operand)
        self.assertIs(operand["nested"], nested)

        query_years = ["2022", "bad", None, 2024, 2022, 2023]
        before_years = list(query_years)
        focus_calls = []

        def focus_owner(current_operand, default_focus):
            focus_calls.append((current_operand, default_focus))
            return "current"

        clean_operand = {"period_hint": "", "label": "metric", "nested": nested}
        with patch.object(
            financial_scope_policies,
            "operand_period_focus",
            side_effect=focus_owner,
        ):
            self.assertEqual(
                financial_scope_policies.operand_target_years(clean_operand, query_years),
                [2024],
            )
        self.assertEqual(focus_calls, [(clean_operand, "unknown")])
        self.assertIs(focus_calls[0][0], clean_operand)
        self.assertEqual(query_years, before_years)

        for focus, years, expected in [
            ("prior", [2024, 2022, 2023], [2023]),
            ("prior", [2024], [2023]),
            ("unknown", [2024, 2022, 2024, 2023], [2024, 2022, 2023]),
        ]:
            with self.subTest(focus=focus, years=years), patch.object(
                financial_scope_policies,
                "operand_period_focus",
                return_value=focus,
            ) as focus_mock:
                self.assertEqual(
                    financial_scope_policies.operand_target_years(clean_operand, years),
                    expected,
                )
                focus_mock.assert_called_once_with(clean_operand, "unknown")

        skipped_empty_focus = Mock(side_effect=AssertionError("empty years skip focus"))
        with patch.object(
            financial_scope_policies,
            "operand_period_focus",
            skipped_empty_focus,
        ):
            self.assertEqual(
                financial_scope_policies.operand_target_years(clean_operand, []),
                [],
            )
        skipped_empty_focus.assert_not_called()

        class RuntimeIntBomb:
            def __int__(self):
                raise RuntimeError("year conversion failed")

        with self.assertRaisesRegex(RuntimeError, "year conversion failed"):
            financial_scope_policies.operand_target_years(
                clean_operand,
                [RuntimeIntBomb()],
            )

        with patch.object(
            financial_scope_policies,
            "operand_period_focus",
            side_effect=RuntimeError("focus failed"),
        ):
            with self.assertRaisesRegex(RuntimeError, "focus failed"):
                financial_scope_policies.operand_target_years(clean_operand, [2024])

    def test_current_source_operand_period_bindings_pin_defs_calls_dag_and_baseline(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        agent_root = repo_root / "src" / "agent"
        target_names = {"operand_target_years", "operand_period_focus"}
        module_paths = {path.stem: path for path in agent_root.glob("*.py")}
        module_trees = {
            name: ast.parse(path.read_text(encoding="utf-8-sig"))
            for name, path in module_paths.items()
        }
        definitions = {name: [] for name in target_names}
        calls = {name: [] for name in target_names}

        class BindingVisitor(ast.NodeVisitor):
            def __init__(self, module_name):
                self.module_name = module_name
                self.function_stack = []
                self.try_depth = 0

            def visit_FunctionDef(self, node):
                if node.name in target_names:
                    definitions[node.name].append((self.module_name, node))
                self.function_stack.append(node.name)
                self.generic_visit(node)
                self.function_stack.pop()

            visit_AsyncFunctionDef = visit_FunctionDef

            def visit_Try(self, node):
                self.try_depth += 1
                self.generic_visit(node)
                self.try_depth -= 1

            visit_TryStar = visit_Try

            def visit_Call(self, node):
                called_name = (
                    node.func.id
                    if isinstance(node.func, ast.Name)
                    else node.func.attr
                    if isinstance(node.func, ast.Attribute)
                    else ""
                )
                if called_name in target_names:
                    calls[called_name].append(
                        (
                            self.module_name,
                            self.function_stack[-1] if self.function_stack else "",
                            type(node.func).__name__,
                            tuple(ast.unparse(arg) for arg in node.args),
                            tuple((kw.arg, ast.unparse(kw.value)) for kw in node.keywords),
                            self.try_depth,
                        )
                    )
                self.generic_visit(node)

        for module_name, tree in module_trees.items():
            BindingVisitor(module_name).visit(tree)

        self.assertEqual(
            {
                name: [
                    (module_name, node.end_lineno - node.lineno + 1)
                    for module_name, node in entries
                ]
                for name, entries in definitions.items()
            },
            {
                "operand_target_years": [("financial_scope_policies", 29)],
                "operand_period_focus": [("financial_scope_policies", 11)],
            },
        )
        self.assertEqual(
            {
                name: [arg.arg for arg in entries[0][1].args.args]
                for name, entries in definitions.items()
            },
            {
                "operand_target_years": ["operand", "query_years"],
                "operand_period_focus": ["operand", "default_period_focus"],
            },
        )
        self.assertEqual(
            {name: len(entries) for name, entries in calls.items()},
            {"operand_target_years": 14, "operand_period_focus": 24},
        )
        self.assertTrue(
            all(entry[2] == "Name" for entries in calls.values() for entry in entries)
        )
        self.assertTrue(
            all(not entry[4] for entries in calls.values() for entry in entries)
        )
        self.assertTrue(
            all(len(entry[3]) == 2 for entries in calls.values() for entry in entries)
        )
        self.assertTrue(
            all(entry[5] == 0 for entries in calls.values() for entry in entries)
        )
        self.assertEqual(
            {
                name: {
                    module: sum(1 for entry in entries if entry[0] == module)
                    for module in sorted({entry[0] for entry in entries})
                }
                for name, entries in calls.items()
            },
            {
                "operand_target_years": {
                    "financial_graph_helpers": 5,
                    "financial_reconciliation_candidates": 2,
                    "financial_scope_policies": 5,
                    "financial_structured_cells": 2,
                },
                "operand_period_focus": {
                    "financial_dependency_projection": 2,
                    "financial_graph_calculation": 3,
                    "financial_graph_helpers": 6,
                    "financial_graph_reconciliation": 5,
                    "financial_lookup_recovery": 5,
                    "financial_reconciliation_candidates": 2,
                    "financial_scope_policies": 1,
                },
            },
        )
        self.assertEqual(
            [entry[1] for entry in calls["operand_period_focus"]].count(
                "operand_target_years"
            ),
            1,
        )
        self.assertEqual((9 + 23, 5 + 1), (32, 6))

        scope_tree = module_trees["financial_scope_policies"]
        scope_functions = [
            node.name
            for node in scope_tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        ]
        self.assertEqual(
            (
                sum(not name.startswith("_") for name in scope_functions),
                sum(name.startswith("_") for name in scope_functions),
            ),
            (9, 9),
        )
        self.assertIn("operand_target_years", scope_functions)
        self.assertIn("operand_period_focus", scope_functions)

        def imported_modules(tree):
            modules = set()
            for node in tree.body:
                if isinstance(node, ast.ImportFrom) and node.module:
                    modules.add(node.module)
                elif isinstance(node, ast.Import):
                    modules.update(alias.name for alias in node.names)
            return modules

        dependency_graph = {
            f"src.agent.{module_name}": imported_modules(tree)
            for module_name, tree in module_trees.items()
        }

        def reachable(start, target):
            pending = [start]
            seen = set()
            while pending:
                current = pending.pop()
                if current in seen:
                    continue
                seen.add(current)
                for dependency in dependency_graph.get(current, set()):
                    if dependency == target:
                        return True
                    if dependency.startswith("src.agent."):
                        pending.append(dependency)
            return False

        self.assertFalse(
            reachable(
                "src.agent.financial_scope_policies",
                "src.agent.financial_graph_helpers",
            )
        )
        helper_imports = imported_modules(module_trees["financial_graph_helpers"])
        self.assertIn("src.agent.financial_scope_policies", helper_imports)
        self.assertIn("src.config.retrieval_policy", helper_imports)

        baseline = json.loads(
            (repo_root / "tests" / "fixtures" / "runtime_domain_terms_baseline.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(len(baseline["records"]), 218)
        selected_source = "\n".join(
            ast.get_source_segment(
                module_paths[module_name].read_text(encoding="utf-8-sig"),
                node,
            )
            or ""
            for entries in definitions.values()
            for module_name, node in entries
        )
        self.assertEqual(
            [
                record
                for record in baseline["records"]
                if record.get("path") == "src/agent/financial_scope_policies.py"
                and str(record.get("text") or "") in selected_source
            ],
            [],
        )

    def test_current_source_operand_period_callers_pin_args_adoption_order_and_stop(self) -> None:
        nested = {"preserve": True}
        operand = {"period_hint": "current", "role": "current_period", "nested": nested}
        query_years = [2024]
        report_scope = {
            "source_reports": [
                {"rcept_no": "r-2024", "year": 2024},
                {"rcept_no": "r-2023", "year": 2023},
            ],
            "nested": nested,
        }
        before_operand = deepcopy(operand)
        before_scope = deepcopy(report_scope)
        graph_calls = []

        def target_years_owner(current_operand, current_query_years):
            graph_calls.append((current_operand, current_query_years))
            return [2024]

        with patch.object(
            financial_scope_policies,
            "operand_target_years",
            side_effect=target_years_owner,
        ):
            self.assertEqual(
                financial_scope_policies._operand_target_receipts(
                    operand,
                    query_years,
                    report_scope,
                ),
                ["r-2024"],
            )
        self.assertEqual(graph_calls, [(operand, query_years)])
        self.assertIs(graph_calls[0][0], operand)
        self.assertIs(graph_calls[0][1], query_years)
        self.assertEqual(operand, before_operand)
        self.assertEqual(report_scope, before_scope)
        with patch.object(
            financial_scope_policies,
            "operand_target_years",
            side_effect=RuntimeError("target years failed"),
        ):
            with self.assertRaisesRegex(RuntimeError, "target years failed"):
                financial_scope_policies._operand_target_receipts(
                    operand,
                    query_years,
                    report_scope,
                )
        self.assertEqual(operand, before_operand)
        self.assertEqual(report_scope, before_scope)

        binding = {"concept": "revenue", "period": "current", "role": "current_period"}
        slot = {"concept": "revenue", "period": "2024", "label": "Revenue"}
        sibling = {"metric_label": "Revenue", "nested": nested}
        state = {"report_scope": {"year": 2024}, "nested": nested}
        before_binding = deepcopy(binding)
        before_slot = deepcopy(slot)
        before_sibling = deepcopy(sibling)
        before_state = deepcopy(state)
        dependency_calls = []

        def dependency_focus(current_operand, default_focus):
            dependency_calls.append((current_operand, default_focus))
            return "current"

        with patch.object(
            financial_dependency_projection,
            "operand_period_focus",
            side_effect=dependency_focus,
        ):
            self.assertTrue(
                financial_dependency_projection.dependency_slot_matches_input(
                    binding,
                    slot,
                    sibling_row=sibling,
                    state=state,
                )
            )
        self.assertEqual(
            dependency_calls,
            [({"period_hint": "current", "role": "current_period"}, "unknown")],
        )
        self.assertEqual(binding, before_binding)
        self.assertEqual(slot, before_slot)
        self.assertEqual(sibling, before_sibling)
        self.assertEqual(state, before_state)
        with patch.object(
            financial_dependency_projection,
            "operand_period_focus",
            side_effect=RuntimeError("dependency focus failed"),
        ):
            with self.assertRaisesRegex(RuntimeError, "dependency focus failed"):
                financial_dependency_projection.dependency_slot_matches_input(
                    binding,
                    slot,
                    sibling_row=sibling,
                    state=state,
                )

        cell = {"column_headers": ["not-a-year"], "report_year": 2024, "nested": nested}
        before_cell = deepcopy(cell)
        reconciliation_events = []

        def reconciliation_focus(current_operand, default_focus):
            reconciliation_events.append("focus")
            self.assertIs(current_operand, operand)
            self.assertEqual(default_focus, "unknown")
            return "current"

        def period_text_owner(current_cell, current_years, current_focus):
            reconciliation_events.append("period-text")
            self.assertIs(current_cell, cell)
            self.assertIs(current_years, query_years)
            self.assertEqual(current_focus, "current")
            return "not-a-year"

        def reconciliation_target_years(current_operand, current_years):
            reconciliation_events.append("target-years")
            self.assertIs(current_operand, operand)
            self.assertIs(current_years, query_years)
            return [2024]

        with (
            patch.object(
                financial_reconciliation_candidates,
                "operand_period_focus",
                side_effect=reconciliation_focus,
            ),
            patch.object(
                financial_reconciliation_candidates,
                "_structured_cell_period_text",
                side_effect=period_text_owner,
            ),
            patch.object(
                financial_reconciliation_candidates,
                "operand_target_years",
                side_effect=reconciliation_target_years,
            ),
        ):
            self.assertEqual(
                financial_reconciliation_candidates._resolved_period_text_for_operand(
                    operand=operand,
                    cell=cell,
                    query_years=query_years,
                    period_focus="unknown",
                ),
                "2024",
            )
        self.assertEqual(
            reconciliation_events,
            ["focus", "period-text", "target-years"],
        )
        self.assertEqual(cell, before_cell)
        self.assertEqual(query_years, [2024])

        stopped_period_text = Mock(side_effect=AssertionError("period text must stop"))
        stopped_target_years = Mock(side_effect=AssertionError("target years must stop"))
        with (
            patch.object(
                financial_reconciliation_candidates,
                "operand_period_focus",
                side_effect=RuntimeError("reconciliation focus failed"),
            ),
            patch.object(
                financial_reconciliation_candidates,
                "_structured_cell_period_text",
                stopped_period_text,
            ),
            patch.object(
                financial_reconciliation_candidates,
                "operand_target_years",
                stopped_target_years,
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "reconciliation focus failed"):
                financial_reconciliation_candidates._resolved_period_text_for_operand(
                    operand=operand,
                    cell=cell,
                    query_years=query_years,
                    period_focus="unknown",
                )
        stopped_period_text.assert_not_called()
        stopped_target_years.assert_not_called()
        self.assertEqual(cell, before_cell)

        evidence_item = {
            "evidence_id": "ev-1",
            "metadata": {
                "year": 2024,
                "structured_cells": [{"value_text": "10", "nested": nested}],
            },
            "nested": nested,
        }
        before_evidence = deepcopy(evidence_item)
        lookup_events = []

        def lookup_focus(current_operand, default_focus):
            lookup_events.append("focus")
            self.assertIs(current_operand, operand)
            self.assertEqual(default_focus, "current")
            return "current"

        def empty_selector(cells, **kwargs):
            lookup_events.append("selector")
            self.assertIs(kwargs["operand"], operand)
            self.assertEqual(kwargs["query_years"], [2024])
            self.assertEqual(kwargs["period_focus"], "current")
            self.assertIsNot(cells[0], evidence_item["metadata"]["structured_cells"][0])
            self.assertIs(cells[0]["nested"], nested)
            return {}

        with (
            patch.object(
                financial_lookup_recovery,
                "operand_period_focus",
                side_effect=lookup_focus,
            ),
            patch.object(
                financial_lookup_recovery,
                "select_structured_cell",
                side_effect=empty_selector,
            ),
        ):
            self.assertEqual(
                financial_lookup_recovery.lookup_row_from_direct_structured_evidence(
                    operand,
                    evidence_item,
                    index=1,
                ),
                {},
            )
        self.assertEqual(lookup_events, ["focus", "selector"])
        self.assertEqual(evidence_item, before_evidence)
        self.assertIs(evidence_item["nested"], nested)

        stopped_selector = Mock(side_effect=AssertionError("selector must stop"))
        with (
            patch.object(
                financial_lookup_recovery,
                "operand_period_focus",
                side_effect=RuntimeError("period focus failed"),
            ),
            patch.object(
                financial_lookup_recovery,
                "select_structured_cell",
                stopped_selector,
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "period focus failed"):
                financial_lookup_recovery.lookup_row_from_direct_structured_evidence(
                    operand,
                    evidence_item,
                    index=1,
                )
        stopped_selector.assert_not_called()
        self.assertEqual(operand, before_operand)
        self.assertEqual(evidence_item, before_evidence)

    def test_current_source_structured_cell_selector_pins_fiscal_ranking_copy_and_stop(self) -> None:
        operand = {"label": "Revenue", "nested": {"preserve": True}}
        query_years = [2024, 2023]

        fiscal_bomb = Mock(side_effect=AssertionError("empty cells must skip fiscal access"))
        target_bomb = Mock(side_effect=AssertionError("empty cells must skip target years"))
        score_bomb = Mock(side_effect=AssertionError("empty cells must skip scoring"))
        with (
            patch.object(financial_structured_cells, "_structured_cell_fiscal_ordinal", fiscal_bomb),
            patch.object(financial_structured_cells, "operand_target_years", target_bomb),
            patch.object(financial_structured_cells, "score_structured_cell", score_bomb),
        ):
            self.assertIsNone(
                financial_structured_cells.select_structured_cell(
                    [],
                    operand=operand,
                    query_years=query_years,
                    period_focus="current",
                )
            )
        fiscal_bomb.assert_not_called()
        target_bomb.assert_not_called()
        score_bomb.assert_not_called()

        nested = {"preserve": True}
        cells = [
            {"cell_id": "oldest", "ordinal": 1, "nested": nested},
            {"cell_id": "prior", "ordinal": 2, "nested": nested},
            {"cell_id": "current", "ordinal": 3, "nested": nested},
        ]
        before_cells = deepcopy(cells)
        fiscal_events = []

        def fiscal_ordinal(cell):
            fiscal_events.append(cell["cell_id"])
            return cell["ordinal"]

        target_bomb = Mock(side_effect=AssertionError("fiscal ranking must skip target years"))
        score_bomb = Mock(side_effect=AssertionError("fiscal ranking must skip scoring"))
        with (
            patch.object(
                financial_structured_cells,
                "_structured_cell_fiscal_ordinal",
                side_effect=fiscal_ordinal,
            ),
            patch.object(financial_structured_cells, "operand_target_years", target_bomb),
            patch.object(financial_structured_cells, "score_structured_cell", score_bomb),
        ):
            selected_current = financial_structured_cells.select_structured_cell(
                cells,
                operand=operand,
                query_years=query_years,
                period_focus="current",
            )
            selected_prior = financial_structured_cells.select_structured_cell(
                cells,
                operand=operand,
                query_years=query_years,
                period_focus="prior",
            )
        self.assertEqual(selected_current["cell_id"], "current")
        self.assertEqual(selected_prior["cell_id"], "prior")
        self.assertIsNot(selected_current, cells[2])
        self.assertIs(selected_current["nested"], nested)
        self.assertEqual(len(selected_current["_sibling_cells"]), 3)
        for original, sibling in zip(cells, selected_current["_sibling_cells"]):
            self.assertIsNot(sibling, original)
            self.assertIs(sibling["nested"], nested)
        self.assertEqual(cells, before_cells)
        self.assertTrue(fiscal_events)
        target_bomb.assert_not_called()
        score_bomb.assert_not_called()

        with patch.object(
            financial_structured_cells,
            "_structured_cell_fiscal_ordinal",
            return_value=7,
        ):
            only = financial_structured_cells.select_structured_cell(
                [cells[0]],
                operand=operand,
                query_years=query_years,
                period_focus="prior",
            )
        self.assertEqual(only["cell_id"], "oldest")
        self.assertIsNot(only, cells[0])

        score_events = []
        target_calls = []

        def target_years(current_operand, current_query_years):
            target_calls.append((current_operand, current_query_years))
            return [2024]

        def score_cell(cell, **kwargs):
            score_events.append((cell, kwargs))
            return 5.0

        with (
            patch.object(
                financial_structured_cells,
                "_structured_cell_fiscal_ordinal",
                return_value=None,
            ),
            patch.object(
                financial_structured_cells,
                "operand_target_years",
                side_effect=target_years,
            ),
            patch.object(
                financial_structured_cells,
                "score_structured_cell",
                side_effect=score_cell,
            ),
        ):
            stable = financial_structured_cells.select_structured_cell(
                cells[:2],
                operand=operand,
                query_years=query_years,
                period_focus="unknown",
            )
        self.assertEqual(stable["cell_id"], "oldest")
        self.assertEqual(len(target_calls), 2)
        self.assertTrue(all(call[0] is operand for call in target_calls))
        self.assertTrue(all(call[1] is query_years for call in target_calls))
        self.assertEqual([event[0]["cell_id"] for event in score_events], ["oldest", "prior"])
        for enriched, kwargs in score_events:
            self.assertIn("_sibling_cells", enriched)
            self.assertEqual(kwargs["query_years"], [2024])
            self.assertEqual(kwargs["period_focus"], "unknown")
            self.assertIs(kwargs["operand"], operand)
        self.assertEqual(cells, before_cells)

        stopped_target = Mock(side_effect=AssertionError("target years must stop"))
        stopped_score = Mock(side_effect=AssertionError("score must stop"))
        with (
            patch.object(
                financial_structured_cells,
                "_structured_cell_fiscal_ordinal",
                side_effect=RuntimeError("fiscal failed"),
            ),
            patch.object(financial_structured_cells, "operand_target_years", stopped_target),
            patch.object(financial_structured_cells, "score_structured_cell", stopped_score),
        ):
            with self.assertRaisesRegex(RuntimeError, "fiscal failed"):
                financial_structured_cells.select_structured_cell(
                    cells,
                    operand=operand,
                    query_years=query_years,
                    period_focus="current",
                )
        stopped_target.assert_not_called()
        stopped_score.assert_not_called()

        stopped_score = Mock(side_effect=AssertionError("score must stop"))
        with (
            patch.object(
                financial_structured_cells,
                "_structured_cell_fiscal_ordinal",
                return_value=None,
            ),
            patch.object(
                financial_structured_cells,
                "operand_target_years",
                side_effect=RuntimeError("target years failed"),
            ),
            patch.object(financial_structured_cells, "score_structured_cell", stopped_score),
        ):
            with self.assertRaisesRegex(RuntimeError, "target years failed"):
                financial_structured_cells.select_structured_cell(
                    cells,
                    operand=operand,
                    query_years=query_years,
                    period_focus="unknown",
                )
        stopped_score.assert_not_called()
        self.assertEqual(cells, before_cells)

        with (
            patch.object(
                financial_structured_cells,
                "_structured_cell_fiscal_ordinal",
                return_value=None,
            ),
            patch.object(financial_structured_cells, "operand_target_years", return_value=[2024]),
            patch.object(
                financial_structured_cells,
                "score_structured_cell",
                side_effect=RuntimeError("score failed"),
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "score failed"):
                financial_structured_cells.select_structured_cell(
                    cells,
                    operand=operand,
                    query_years=query_years,
                    period_focus="unknown",
                )
        self.assertEqual(cells, before_cells)

    def test_current_source_aggregate_structured_cell_selector_pins_rank_gates_and_copy(self) -> None:
        operand = {"label": "Revenue", "nested": {"preserve": True}}
        query_years = [2024]

        class PolicyBomb:
            def get(self, key, default=None):
                raise AssertionError("empty cells must skip policy")

        with patch.object(
            financial_structured_cells,
            "STRUCTURED_CELL_AFFINITY_POLICY",
            PolicyBomb(),
        ):
            self.assertIsNone(
                financial_structured_cells.select_aggregate_structured_cell(
                    [],
                    operand=operand,
                    query_years=query_years,
                    period_focus="current",
                )
            )

        nested = {"preserve": True}

        class SoftFloatBomb:
            def __float__(self):
                raise TypeError("soft column index")

        cells = [
            {"cell_id": "invalid", "value_text": "bad", "nested": nested},
            {"cell_id": "detail", "value_text": "1", "column_headers": ["Detail"], "nested": nested},
            {
                "cell_id": "aggregate",
                "value_text": "2",
                "value_role": "aggregate",
                "column_index": 1,
                "nested": nested,
            },
            {
                "cell_id": "final",
                "value_text": "3",
                "aggregation_stage": "final",
                "aggregate_label": "Total",
                "column_index": SoftFloatBomb(),
                "nested": nested,
            },
        ]
        before_cells = [dict(cell) for cell in cells]
        before_nested = [cell["nested"] for cell in cells]
        normalized = []
        targets = []
        scored = []

        def normalize(raw_value, raw_unit):
            normalized.append((raw_value, raw_unit))
            return (None, "") if raw_value == "bad" else (1.0, "KRW")

        def target_years(current_operand, current_years):
            targets.append((current_operand, current_years))
            return [2024]

        def score_cell(cell, **kwargs):
            scored.append((cell, kwargs))
            return 0.0

        with (
            patch.object(financial_structured_cells, "STRUCTURED_CELL_AFFINITY_POLICY", {"aggregate_tokens": ()}),
            patch.object(financial_structured_cells, "_normalise_operand_value", side_effect=normalize),
            patch.object(financial_structured_cells, "operand_target_years", side_effect=target_years),
            patch.object(financial_structured_cells, "score_structured_cell", side_effect=score_cell),
            patch.object(financial_structured_cells, "_operand_text_match", return_value=False),
        ):
            selected = financial_structured_cells.select_aggregate_structured_cell(
                cells,
                operand=operand,
                query_years=query_years,
                period_focus="current",
            )
        self.assertEqual(selected["cell_id"], "final")
        self.assertIsNot(selected, cells[3])
        self.assertIs(selected["nested"], nested)
        self.assertEqual(len(selected["_sibling_cells"]), 4)
        self.assertTrue(
            all(sibling is not original for sibling, original in zip(selected["_sibling_cells"], cells))
        )
        self.assertTrue(all(sibling["nested"] is nested for sibling in selected["_sibling_cells"]))
        self.assertEqual(normalized, [("bad", ""), ("1", ""), ("2", ""), ("3", "")])
        self.assertEqual(len(targets), 2)
        self.assertEqual([item[0]["cell_id"] for item in scored], ["aggregate", "final"])
        for _cell, kwargs in scored:
            self.assertEqual(kwargs["query_years"], [2024])
            self.assertEqual(kwargs["period_focus"], "current")
            self.assertIs(kwargs["operand"], operand)
        for current, before, nested_ref in zip(cells, before_cells, before_nested):
            self.assertEqual(current, before)
            self.assertIs(current["nested"], nested_ref)

        tied_cells = [
            {"cell_id": "first", "value_text": "1", "value_role": "aggregate", "nested": nested},
            {"cell_id": "second", "value_text": "2", "value_role": "aggregate", "nested": nested},
        ]
        with (
            patch.object(financial_structured_cells, "STRUCTURED_CELL_AFFINITY_POLICY", {"aggregate_tokens": ()}),
            patch.object(financial_structured_cells, "_normalise_operand_value", return_value=(1.0, "KRW")),
            patch.object(financial_structured_cells, "operand_target_years", return_value=[2024]),
            patch.object(financial_structured_cells, "score_structured_cell", return_value=0.0),
            patch.object(financial_structured_cells, "_operand_text_match", return_value=False),
        ):
            tied = financial_structured_cells.select_aggregate_structured_cell(
                tied_cells,
                operand=operand,
                query_years=query_years,
                period_focus="unknown",
            )
        self.assertEqual(tied["cell_id"], "first")

        token_cells = [
            {
                "cell_id": "token-match",
                "value_text": "1",
                "column_headers": ["Total"],
            },
            {
                "cell_id": "role-reference",
                "value_text": "2",
                "value_role": "aggregate",
            },
        ]

        def token_base_score(cell, **_kwargs):
            return 3.0 if cell.get("cell_id") == "token-match" else 0.0

        with (
            patch.object(
                financial_structured_cells,
                "STRUCTURED_CELL_AFFINITY_POLICY",
                {"aggregate_tokens": ("Total",)},
            ),
            patch.object(financial_structured_cells, "_normalise_operand_value", return_value=(1.0, "KRW")),
            patch.object(financial_structured_cells, "operand_target_years", return_value=[2024]),
            patch.object(financial_structured_cells, "score_structured_cell", side_effect=token_base_score),
            patch.object(
                financial_structured_cells,
                "_operand_text_match",
                side_effect=lambda surface, _operand: surface == "Total",
            ),
        ):
            token_selected = financial_structured_cells.select_aggregate_structured_cell(
                token_cells,
                operand=operand,
                query_years=query_years,
                period_focus="current",
            )
        self.assertEqual(token_selected["cell_id"], "token-match")

        stage_cells = [
            {"cell_id": "direct", "value_text": "1", "aggregation_stage": "direct"},
            {"cell_id": "subtotal", "value_text": "2", "aggregation_stage": "subtotal"},
            {
                "cell_id": "subtotal-role",
                "value_text": "3",
                "aggregation_stage": "subtotal",
                "aggregate_role": "subtotal",
            },
        ]
        with (
            patch.object(financial_structured_cells, "STRUCTURED_CELL_AFFINITY_POLICY", {"aggregate_tokens": ()}),
            patch.object(financial_structured_cells, "_normalise_operand_value", return_value=(1.0, "KRW")),
            patch.object(financial_structured_cells, "operand_target_years", return_value=[2024]),
            patch.object(financial_structured_cells, "score_structured_cell", return_value=0.0),
            patch.object(financial_structured_cells, "_operand_text_match", return_value=False),
        ):
            stage_selected = financial_structured_cells.select_aggregate_structured_cell(
                stage_cells,
                operand=operand,
                query_years=query_years,
                period_focus="current",
            )
        self.assertEqual(stage_selected["cell_id"], "direct")

        index_cells = [
            {"cell_id": "low", "value_text": "1", "value_role": "aggregate", "column_index": 50},
            {"cell_id": "capped", "value_text": "2", "value_role": "aggregate", "column_index": 200},
        ]
        with (
            patch.object(financial_structured_cells, "STRUCTURED_CELL_AFFINITY_POLICY", {"aggregate_tokens": ()}),
            patch.object(financial_structured_cells, "_normalise_operand_value", return_value=(1.0, "KRW")),
            patch.object(financial_structured_cells, "operand_target_years", return_value=[2024]),
            patch.object(financial_structured_cells, "score_structured_cell", return_value=0.0),
            patch.object(financial_structured_cells, "_operand_text_match", return_value=False),
        ):
            index_selected = financial_structured_cells.select_aggregate_structured_cell(
                index_cells,
                operand=operand,
                query_years=query_years,
                period_focus="current",
            )
        self.assertEqual(index_selected["cell_id"], "capped")

        class RuntimeFloatBomb:
            def __float__(self):
                raise RuntimeError("column index failed")

        runtime_cell = {
            "value_text": "1",
            "value_role": "aggregate",
            "column_index": RuntimeFloatBomb(),
        }
        with (
            patch.object(financial_structured_cells, "STRUCTURED_CELL_AFFINITY_POLICY", {"aggregate_tokens": ()}),
            patch.object(financial_structured_cells, "_normalise_operand_value", return_value=(1.0, "KRW")),
            patch.object(financial_structured_cells, "operand_target_years", return_value=[2024]),
            patch.object(financial_structured_cells, "score_structured_cell", return_value=0.0),
            patch.object(financial_structured_cells, "_operand_text_match", return_value=False),
        ):
            with self.assertRaisesRegex(RuntimeError, "column index failed"):
                financial_structured_cells.select_aggregate_structured_cell(
                    [runtime_cell],
                    operand=operand,
                    query_years=query_years,
                    period_focus="current",
                )

        stopped_score = Mock(side_effect=AssertionError("normalization must stop scoring"))
        with (
            patch.object(financial_structured_cells, "STRUCTURED_CELL_AFFINITY_POLICY", {"aggregate_tokens": ()}),
            patch.object(
                financial_structured_cells,
                "_normalise_operand_value",
                side_effect=RuntimeError("normalization failed"),
            ),
            patch.object(financial_structured_cells, "score_structured_cell", stopped_score),
        ):
            with self.assertRaisesRegex(RuntimeError, "normalization failed"):
                financial_structured_cells.select_aggregate_structured_cell(
                    [{"value_text": "1", "value_role": "aggregate"}],
                    operand=operand,
                    query_years=query_years,
                    period_focus="current",
                )
        stopped_score.assert_not_called()

        with (
            patch.object(financial_structured_cells, "STRUCTURED_CELL_AFFINITY_POLICY", {"aggregate_tokens": ()}),
            patch.object(financial_structured_cells, "_normalise_operand_value", return_value=(1.0, "KRW")),
            patch.object(
                financial_structured_cells,
                "operand_target_years",
                side_effect=RuntimeError("aggregate target years failed"),
            ),
            patch.object(financial_structured_cells, "score_structured_cell", stopped_score),
        ):
            with self.assertRaisesRegex(RuntimeError, "aggregate target years failed"):
                financial_structured_cells.select_aggregate_structured_cell(
                    [{"value_text": "1", "value_role": "aggregate"}],
                    operand=operand,
                    query_years=query_years,
                    period_focus="current",
                )
        stopped_score.assert_not_called()

    def test_current_source_structured_cell_affinity_pins_headers_entities_and_exceptions(self) -> None:
        nested = {"preserve": True}
        cell = {"column_headers": ["Generic", "Revenue"], "nested": nested}
        operand = {"label": "Revenue", "nested": nested}
        before_cell = deepcopy(cell)
        before_operand = deepcopy(operand)
        with (
            patch.object(financial_structured_cells, "_generic_column_headers", return_value={"Generic"}),
            patch.object(financial_structured_cells, "_operand_needles", return_value=["Revenue"]),
            patch.object(financial_structured_cells, "_operand_text_match", return_value=False),
            patch.object(
                financial_structured_cells,
                "STRUCTURED_CELL_AFFINITY_POLICY",
                {"metric_terms": (), "aggregate_tokens": ()},
            ),
        ):
            self.assertEqual(
                financial_structured_cells._structured_cell_operand_affinity(cell, operand),
                4.75,
            )
        self.assertEqual(cell, before_cell)
        self.assertEqual(operand, before_operand)
        self.assertIs(cell["nested"], nested)
        self.assertIs(operand["nested"], nested)

        with (
            patch.object(financial_structured_cells, "_generic_column_headers", return_value=set()),
            patch.object(financial_structured_cells, "_operand_needles", return_value=["Metric"]),
            patch.object(financial_structured_cells, "_operand_text_match", return_value=True),
            patch.object(
                financial_structured_cells,
                "STRUCTURED_CELL_AFFINITY_POLICY",
                {"metric_terms": (), "aggregate_tokens": ("Total",)},
            ),
        ):
            self.assertAlmostEqual(
                financial_structured_cells._structured_cell_operand_affinity(
                    {"column_headers": ["Total"]},
                    {"label": "Metric"},
                ),
                6.35,
            )

        entity_policy = {
            "metric_terms": ("Metric",),
            "year_pattern": r"20\d{2}",
            "entity_surface_drop_terms": (),
            "entity_token_split_pattern": r"\s+",
            "aggregate_tokens": (),
        }
        with (
            patch.object(financial_structured_cells, "_generic_column_headers", return_value={"Generic"}),
            patch.object(financial_structured_cells, "_operand_needles", return_value=["Other"]),
            patch.object(financial_structured_cells, "_operand_text_match", return_value=False),
            patch.object(financial_structured_cells, "STRUCTURED_CELL_AFFINITY_POLICY", entity_policy),
        ):
            self.assertEqual(
                financial_structured_cells._structured_cell_operand_affinity(
                    {"column_headers": ["Generic", "Company"], "row_label": "Metric"},
                    {"label": "Company Metric 2024"},
                ),
                3.0,
            )

        generic_bomb = Mock(side_effect=AssertionError("blank headers skip generic policy"))
        needles_bomb = Mock(side_effect=AssertionError("blank headers skip operand needles"))
        with (
            patch.object(financial_structured_cells, "_generic_column_headers", generic_bomb),
            patch.object(financial_structured_cells, "_operand_needles", needles_bomb),
        ):
            self.assertEqual(
                financial_structured_cells._structured_cell_operand_affinity({}, operand),
                0.0,
            )
        generic_bomb.assert_not_called()
        needles_bomb.assert_not_called()

        class PolicyBomb:
            def keys(self):
                raise AssertionError("empty needles skip affinity policy")

            def __getitem__(self, key):
                raise AssertionError(key)

        with (
            patch.object(financial_structured_cells, "_generic_column_headers", return_value=set()),
            patch.object(financial_structured_cells, "_operand_needles", return_value=[]),
            patch.object(financial_structured_cells, "STRUCTURED_CELL_AFFINITY_POLICY", PolicyBomb()),
        ):
            self.assertEqual(
                financial_structured_cells._structured_cell_operand_affinity(
                    {"column_headers": ["Header"]},
                    operand,
                ),
                0.0,
            )

        stopped_needles = Mock(side_effect=AssertionError("generic failure must stop needles"))
        with (
            patch.object(
                financial_structured_cells,
                "_generic_column_headers",
                side_effect=RuntimeError("generic headers failed"),
            ),
            patch.object(financial_structured_cells, "_operand_needles", stopped_needles),
        ):
            with self.assertRaisesRegex(RuntimeError, "generic headers failed"):
                financial_structured_cells._structured_cell_operand_affinity(
                    {"column_headers": ["Header"]},
                    operand,
                )
        stopped_needles.assert_not_called()

        with (
            patch.object(financial_structured_cells, "_generic_column_headers", return_value=set()),
            patch.object(
                financial_structured_cells,
                "_operand_needles",
                side_effect=RuntimeError("needles failed"),
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "needles failed"):
                financial_structured_cells._structured_cell_operand_affinity(
                    {"column_headers": ["Header"]},
                    operand,
                )

        class CopyPolicyBomb:
            def keys(self):
                raise RuntimeError("affinity policy failed")

            def __getitem__(self, key):
                raise AssertionError(key)

        with (
            patch.object(financial_structured_cells, "_generic_column_headers", return_value=set()),
            patch.object(financial_structured_cells, "_operand_needles", return_value=["Other"]),
            patch.object(financial_structured_cells, "_operand_text_match", return_value=False),
            patch.object(financial_structured_cells, "STRUCTURED_CELL_AFFINITY_POLICY", CopyPolicyBomb()),
        ):
            with self.assertRaisesRegex(RuntimeError, "affinity policy failed"):
                financial_structured_cells._structured_cell_operand_affinity(
                    {"column_headers": ["Header"]},
                    operand,
                )

    def test_current_source_structured_cell_score_pins_year_period_binding_and_stop(self) -> None:
        nested = {"preserve": True}
        cell = {
            "column_headers": ["2024 CURRENT OLD"],
            "value_role": "aggregate",
            "aggregation_stage": "final",
            "aggregate_role": "final_total",
            "aggregate_label": "Total",
            "nested": nested,
        }
        operand = {
            "binding_policy": {
                "prefer_value_roles": [" aggregate "],
                "prefer_aggregation_stages": [" final "],
            },
            "segment_label": "",
            "nested": nested,
        }
        before_cell = deepcopy(cell)
        before_operand = deepcopy(operand)
        affinity_calls = []

        def affinity_owner(current_cell, current_operand):
            affinity_calls.append((current_cell, current_operand))
            return 2.5

        with (
            patch.object(
                financial_structured_cells,
                "STRUCTURED_CELL_PERIOD_SCORING_POLICY",
                {
                    "current_positive_markers": ("CURRENT",),
                    "current_negative_markers": ("OLD",),
                    "prior_positive_markers": ("PRIOR",),
                    "prior_negative_markers": ("CURRENT",),
                },
            ),
            patch.object(
                financial_structured_cells,
                "STRUCTURED_CELL_AFFINITY_POLICY",
                {"aggregate_tokens": ("Total",)},
            ),
            patch.object(
                financial_structured_cells,
                "_structured_cell_operand_affinity",
                side_effect=affinity_owner,
            ),
        ):
            score = financial_structured_cells.score_structured_cell(
                cell,
                query_years=[2024],
                period_focus="current",
                operand=operand,
            )
        self.assertEqual(score, 21.75)
        self.assertEqual(affinity_calls, [(cell, operand)])
        self.assertIs(affinity_calls[0][0], cell)
        self.assertIs(affinity_calls[0][1], operand)
        self.assertEqual(cell, before_cell)
        self.assertEqual(operand, before_operand)
        self.assertIs(cell["nested"], nested)
        self.assertIs(operand["nested"], nested)

        affinity_bomb = Mock(side_effect=AssertionError("missing operand skips affinity"))
        with (
            patch.object(
                financial_structured_cells,
                "STRUCTURED_CELL_PERIOD_SCORING_POLICY",
                {
                    "current_positive_markers": (),
                    "current_negative_markers": (),
                    "prior_positive_markers": ("PRIOR",),
                    "prior_negative_markers": ("CURRENT",),
                },
            ),
            patch.object(financial_structured_cells, "_structured_cell_operand_affinity", affinity_bomb),
        ):
            self.assertEqual(
                financial_structured_cells.score_structured_cell(
                    {"column_headers": ["2023 PRIOR CURRENT"]},
                    query_years=[2024, 2023],
                    period_focus="prior",
                    operand=None,
                ),
                12.0,
            )
        affinity_bomb.assert_not_called()

        with (
            patch.object(
                financial_structured_cells,
                "STRUCTURED_CELL_PERIOD_SCORING_POLICY",
                {
                    "current_positive_markers": (),
                    "current_negative_markers": (),
                    "prior_positive_markers": (),
                    "prior_negative_markers": (),
                },
            ),
            patch.object(financial_structured_cells, "STRUCTURED_CELL_AFFINITY_POLICY", {"aggregate_tokens": ()}),
            patch.object(financial_structured_cells, "_structured_cell_operand_affinity", return_value=0.0),
        ):
            self.assertEqual(
                financial_structured_cells.score_structured_cell(
                    {"column_headers": [], "value_role": "detail"},
                    query_years=[],
                    period_focus="unknown",
                    operand={
                        "binding_policy": {"prefer_value_roles": ["aggregate"]},
                        "segment_label": "Segment",
                    },
                ),
                -1.25,
            )

        class PolicyBomb:
            def keys(self):
                raise RuntimeError("period policy failed")

            def __getitem__(self, key):
                raise AssertionError(key)

        stopped_affinity = Mock(side_effect=AssertionError("policy failure must stop affinity"))
        with (
            patch.object(financial_structured_cells, "STRUCTURED_CELL_PERIOD_SCORING_POLICY", PolicyBomb()),
            patch.object(financial_structured_cells, "_structured_cell_operand_affinity", stopped_affinity),
        ):
            with self.assertRaisesRegex(RuntimeError, "period policy failed"):
                financial_structured_cells.score_structured_cell(
                    cell,
                    query_years=[2024],
                    period_focus="current",
                    operand=operand,
                )

        with (
            patch.object(
                financial_structured_cells,
                "STRUCTURED_CELL_PERIOD_SCORING_POLICY",
                {
                    "current_positive_markers": (),
                    "current_negative_markers": (),
                },
            ),
            patch.object(financial_structured_cells, "_structured_cell_operand_affinity", return_value=0.0),
            patch.object(
                financial_structured_cells,
                "_normalise_spaces",
                side_effect=RuntimeError("binding normalization failed"),
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "binding normalization failed"):
                financial_structured_cells.score_structured_cell(
                    cell,
                    query_years=[2024],
                    period_focus="current",
                    operand=operand,
                )
        stopped_affinity.assert_not_called()

        with (
            patch.object(
                financial_structured_cells,
                "STRUCTURED_CELL_PERIOD_SCORING_POLICY",
                {
                    "current_positive_markers": (),
                    "current_negative_markers": (),
                },
            ),
            patch.object(
                financial_structured_cells,
                "_structured_cell_operand_affinity",
                side_effect=RuntimeError("affinity failed"),
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "affinity failed"):
                financial_structured_cells.score_structured_cell(
                    cell,
                    query_years=[2024],
                    period_focus="current",
                    operand=operand,
                )

    def test_current_source_structured_cell_bindings_pin_defs_calls_dag_and_baseline(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        agent_root = repo_root / "src" / "agent"
        target_names = {
            "select_structured_cell",
            "select_aggregate_structured_cell",
            "_structured_cell_operand_affinity",
            "score_structured_cell",
        }
        module_paths = {path.stem: path for path in agent_root.glob("*.py")}
        module_sources = {
            name: path.read_text(encoding="utf-8-sig")
            for name, path in module_paths.items()
        }
        module_trees = {
            name: ast.parse(source)
            for name, source in module_sources.items()
        }
        definitions = {name: [] for name in target_names}
        calls = {name: [] for name in target_names}

        class BindingVisitor(ast.NodeVisitor):
            def __init__(self, module_name):
                self.module_name = module_name
                self.function_stack = []
                self.try_depth = 0

            def visit_FunctionDef(self, node):
                if node.name in target_names:
                    definitions[node.name].append((self.module_name, node))
                self.function_stack.append(node.name)
                self.generic_visit(node)
                self.function_stack.pop()

            visit_AsyncFunctionDef = visit_FunctionDef

            def visit_Try(self, node):
                self.try_depth += 1
                self.generic_visit(node)
                self.try_depth -= 1

            visit_TryStar = visit_Try

            def visit_Call(self, node):
                called_name = (
                    node.func.id
                    if isinstance(node.func, ast.Name)
                    else node.func.attr
                    if isinstance(node.func, ast.Attribute)
                    else ""
                )
                if called_name in target_names:
                    calls[called_name].append(
                        (
                            self.module_name,
                            self.function_stack[-1] if self.function_stack else "",
                            type(node.func).__name__,
                            tuple(ast.unparse(arg) for arg in node.args),
                            tuple((kw.arg, ast.unparse(kw.value)) for kw in node.keywords),
                            self.try_depth,
                        )
                    )
                self.generic_visit(node)

        for module_name, tree in module_trees.items():
            BindingVisitor(module_name).visit(tree)

        self.assertEqual(
            {
                name: [
                    (module_name, node.end_lineno - node.lineno + 1)
                    for module_name, node in entries
                ]
                for name, entries in definitions.items()
            },
            {
                "select_structured_cell": [("financial_structured_cells", 42)],
                "select_aggregate_structured_cell": [("financial_structured_cells", 84)],
                "_structured_cell_operand_affinity": [("financial_structured_cells", 53)],
                "score_structured_cell": [("financial_structured_cells", 66)],
            },
        )
        self.assertEqual(
            {
                name: (
                    [arg.arg for arg in entries[0][1].args.args],
                    [arg.arg for arg in entries[0][1].args.kwonlyargs],
                )
                for name, entries in definitions.items()
            },
            {
                "select_structured_cell": (["cells"], ["operand", "query_years", "period_focus"]),
                "select_aggregate_structured_cell": (["cells"], ["operand", "query_years", "period_focus"]),
                "_structured_cell_operand_affinity": (["cell", "operand"], []),
                "score_structured_cell": (["cell"], ["query_years", "period_focus", "operand"]),
            },
        )
        self.assertEqual(
            {name: len(entries) for name, entries in calls.items()},
            {
                "select_structured_cell": 7,
                "select_aggregate_structured_cell": 5,
                "_structured_cell_operand_affinity": 1,
                "score_structured_cell": 6,
            },
        )
        self.assertTrue(all(entry[2] == "Name" for entries in calls.values() for entry in entries))
        self.assertTrue(all(entry[5] == 0 for entries in calls.values() for entry in entries))
        for name in ("select_structured_cell", "select_aggregate_structured_cell"):
            self.assertTrue(all(len(entry[3]) == 1 for entry in calls[name]))
            self.assertTrue(
                all(
                    tuple(keyword for keyword, _value in entry[4])
                    == ("operand", "query_years", "period_focus")
                    for entry in calls[name]
                )
            )
        self.assertTrue(
            all(len(entry[3]) == 2 and not entry[4] for entry in calls["_structured_cell_operand_affinity"])
        )
        self.assertTrue(all(len(entry[3]) == 1 for entry in calls["score_structured_cell"]))
        self.assertTrue(
            all(
                tuple(keyword for keyword, _value in entry[4])
                == ("query_years", "period_focus", "operand")
                for entry in calls["score_structured_cell"]
            )
        )
        self.assertEqual(
            {
                name: {
                    module: sum(1 for entry in entries if entry[0] == module)
                    for module in sorted({entry[0] for entry in entries})
                }
                for name, entries in calls.items()
            },
            {
                "select_structured_cell": {
                    "financial_graph_calculation": 1,
                    "financial_graph_helpers": 1,
                    "financial_graph_reconciliation": 3,
                    "financial_lookup_recovery": 2,
                },
                "select_aggregate_structured_cell": {
                    "financial_graph_calculation": 1,
                    "financial_graph_reconciliation": 2,
                    "financial_lookup_recovery": 2,
                },
                "_structured_cell_operand_affinity": {"financial_structured_cells": 1},
                "score_structured_cell": {
                    "financial_graph_evidence": 3,
                    "financial_reconciliation_candidates": 1,
                    "financial_structured_cells": 2,
                },
            },
        )
        self.assertEqual(
            sorted(
                (entry[1], entry[3], entry[4])
                for entry in calls["select_structured_cell"]
                if entry[0] == "financial_graph_helpers"
            ),
            [
                (
                    "_candidate_selected_cell_for_operand",
                    ("cells",),
                    (
                        ("operand", "operand"),
                        ("query_years", "query_years"),
                        ("period_focus", "period_focus"),
                    ),
                )
            ],
        )
        self.assertEqual(
            sorted(entry[1] for entry in calls["score_structured_cell"]),
            [
                "_build_required_operands_from_candidates",
                "_build_required_operands_from_candidates",
                "_build_required_operands_from_candidates",
                "_cell_aggregate_rank",
                "pair_candidate_period_score",
                "select_structured_cell",
            ],
        )
        self.assertEqual((16, 3), (7 + 5 + 4, 2 + 1))

        structured_tree = module_trees["financial_structured_cells"]
        structured_functions = [
            node.name
            for node in structured_tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        ]
        self.assertEqual(
            (
                sum(not name.startswith("_") for name in structured_functions),
                sum(name.startswith("_") for name in structured_functions),
            ),
            (3, 4),
        )
        self.assertTrue(target_names.issubset(structured_functions))

        def imported_modules(tree):
            modules = set()
            for node in tree.body:
                if isinstance(node, ast.ImportFrom) and node.module:
                    modules.add(node.module)
                elif isinstance(node, ast.Import):
                    modules.update(alias.name for alias in node.names)
            return modules

        dependency_graph = {
            f"src.agent.{module_name}": imported_modules(tree)
            for module_name, tree in module_trees.items()
        }

        def reachable(start, target):
            pending = [start]
            seen = set()
            while pending:
                current = pending.pop()
                if current in seen:
                    continue
                seen.add(current)
                for dependency in dependency_graph.get(current, set()):
                    if dependency == target:
                        return True
                    if dependency.startswith("src.agent."):
                        pending.append(dependency)
            return False

        self.assertFalse(
            reachable(
                "src.agent.financial_structured_cells",
                "src.agent.financial_graph_helpers",
            )
        )
        for dependency in (
            "src.agent.financial_scope_policies",
            "src.agent.financial_runtime_normalization",
            "src.agent.financial_row_surfaces",
            "src.agent.financial_surface_contracts",
        ):
            self.assertFalse(reachable(dependency, "src.agent.financial_structured_cells"))

        helper_tree = module_trees["financial_graph_helpers"]
        fiscal_calls = [
            node
            for node in ast.walk(helper_tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "_structured_cell_fiscal_ordinal"
        ]
        period_calls = [
            node
            for node in ast.walk(helper_tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "_structured_cell_period_text"
        ]
        self.assertEqual(len(fiscal_calls), 0)
        self.assertGreater(len(period_calls), 0)

        baseline = json.loads(
            (repo_root / "tests" / "fixtures" / "runtime_domain_terms_baseline.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(len(baseline["records"]), 218)
        selected_source = "\n".join(
            ast.get_source_segment(module_sources[module_name], node) or ""
            for entries in definitions.values()
            for module_name, node in entries
        )
        self.assertEqual(
            [
                record
                for record in baseline["records"]
                if str(record.get("text") or "") in selected_source
            ],
            [],
        )

    def test_current_source_structured_cell_callers_pin_args_adoption_order_and_stop(self) -> None:
        nested = {"preserve": True}
        operand = {"label": "Revenue", "nested": nested}
        candidate = {
            "candidate_kind": "table_row",
            "metadata": {
                "year": 2024,
                "structured_cells": [{"value_text": "10", "nested": nested}],
            },
            "nested": nested,
        }
        before_candidate = deepcopy(candidate)
        selected = {"value_text": "10", "nested": nested}
        selector_calls = []

        def selector(cells, **kwargs):
            selector_calls.append((cells, kwargs))
            return selected

        with patch.object(
            financial_graph_helpers,
            "select_structured_cell",
            side_effect=selector,
        ):
            self.assertIs(
                financial_graph_helpers._candidate_selected_cell_for_operand(
                    candidate,
                    operand=operand,
                    query_years=[2024],
                    period_focus="current",
                ),
                selected,
            )
        self.assertEqual(len(selector_calls), 1)
        passed_cells, kwargs = selector_calls[0]
        self.assertEqual(passed_cells[0]["_report_year"], 2024)
        self.assertIsNot(passed_cells[0], candidate["metadata"]["structured_cells"][0])
        self.assertIs(passed_cells[0]["nested"], nested)
        self.assertIs(kwargs["operand"], operand)
        self.assertEqual(kwargs["query_years"], [2024])
        self.assertEqual(kwargs["period_focus"], "current")
        self.assertEqual(candidate, before_candidate)
        self.assertIs(candidate["nested"], nested)

        with patch.object(
            financial_graph_helpers,
            "select_structured_cell",
            side_effect=RuntimeError("selector failed"),
        ):
            with self.assertRaisesRegex(RuntimeError, "selector failed"):
                financial_graph_helpers._candidate_selected_cell_for_operand(
                    candidate,
                    operand=operand,
                    query_years=[2024],
                    period_focus="current",
                )
        self.assertEqual(candidate, before_candidate)

        score_events = []
        score_cell = {"value_text": "10", "nested": nested}
        score_candidate = {"candidate_id": "candidate", "nested": nested}
        score_constraints = {"mode": "strict", "nested": nested}
        report_scope = {"year": 2024, "nested": nested}
        before_score_cell = deepcopy(score_cell)
        before_score_candidate = deepcopy(score_candidate)
        before_constraints = deepcopy(score_constraints)
        before_scope = deepcopy(report_scope)

        def candidate_score(current_candidate, **kwargs):
            score_events.append("candidate")
            self.assertIs(current_candidate, score_candidate)
            self.assertIs(kwargs["operand"], operand)
            self.assertIs(kwargs["constraints"], score_constraints)
            self.assertIs(kwargs["report_scope"], report_scope)
            return 10.0

        def target_years(current_operand, current_years):
            score_events.append("target")
            self.assertIs(current_operand, operand)
            self.assertEqual(current_years, [2024])
            return [2024]

        def period_focus(current_operand, fallback):
            score_events.append("focus")
            self.assertIs(current_operand, operand)
            self.assertEqual(fallback, "unknown")
            return "current"

        def cell_score(current_cell, **kwargs):
            score_events.append("cell")
            self.assertIs(current_cell, score_cell)
            self.assertEqual(kwargs["query_years"], [2024])
            self.assertEqual(kwargs["period_focus"], "current")
            self.assertIs(kwargs["operand"], operand)
            return 2.5

        def period_text(**kwargs):
            score_events.append("period")
            self.assertIs(kwargs["operand"], operand)
            self.assertIs(kwargs["cell"], score_cell)
            return "2024"

        with (
            patch.object(financial_reconciliation_candidates, "_score_operand_candidate", side_effect=candidate_score),
            patch.object(financial_reconciliation_candidates, "operand_target_years", side_effect=target_years),
            patch.object(financial_reconciliation_candidates, "operand_period_focus", side_effect=period_focus),
            patch.object(financial_reconciliation_candidates, "score_structured_cell", side_effect=cell_score),
            patch.object(
                financial_reconciliation_candidates,
                "_resolved_period_text_for_operand",
                side_effect=period_text,
            ),
        ):
            self.assertEqual(
                financial_reconciliation_candidates.pair_candidate_period_score(
                    candidate=score_candidate,
                    cell=score_cell,
                    operand=operand,
                    preferred_statement_types=["income"],
                    constraints=score_constraints,
                    query_years=[2024],
                    period_focus="unknown",
                    report_scope=report_scope,
                ),
                (12.5, "2024"),
            )
        self.assertEqual(score_events, ["candidate", "target", "focus", "cell", "period"])
        self.assertEqual(score_candidate, before_score_candidate)
        self.assertEqual(score_cell, before_score_cell)
        self.assertEqual(score_constraints, before_constraints)
        self.assertEqual(report_scope, before_scope)

        stopped_period = Mock(side_effect=AssertionError("score exception must stop period"))
        with (
            patch.object(financial_reconciliation_candidates, "_score_operand_candidate", return_value=10.0),
            patch.object(financial_reconciliation_candidates, "operand_target_years", return_value=[2024]),
            patch.object(financial_reconciliation_candidates, "operand_period_focus", return_value="current"),
            patch.object(
                financial_reconciliation_candidates,
                "score_structured_cell",
                side_effect=RuntimeError("cell score failed"),
            ),
            patch.object(
                financial_reconciliation_candidates,
                "_resolved_period_text_for_operand",
                stopped_period,
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "cell score failed"):
                financial_reconciliation_candidates.pair_candidate_period_score(
                    candidate=score_candidate,
                    cell=score_cell,
                    operand=operand,
                    preferred_statement_types=["income"],
                    constraints=score_constraints,
                    query_years=[2024],
                    period_focus="unknown",
                    report_scope=report_scope,
                )
        stopped_period.assert_not_called()

        evidence_item = {
            "evidence_id": "ev-1",
            "source_anchor": "anchor",
            "metadata": {
                "year": 2024,
                "value_role": "aggregate",
                "structured_cells": [
                    {"cell_id": "detail", "value_text": "10", "nested": nested},
                    {
                        "cell_id": "aggregate",
                        "value_text": "20",
                        "unit_hint": "KRW",
                        "value_role": "aggregate",
                        "nested": nested,
                    },
                ],
            },
            "nested": nested,
        }
        before_evidence = deepcopy(evidence_item)
        lookup_events = []
        ordinary_selected = {"value_text": "10", "unit_hint": "KRW"}
        aggregate_selected = {
            "value_text": "20",
            "unit_hint": "KRW",
            "value_role": "aggregate",
        }

        def lookup_focus(current_operand, fallback):
            lookup_events.append("focus")
            self.assertIs(current_operand, operand)
            self.assertEqual(fallback, "current")
            return "current"

        def ordinary_selector(cells, **kwargs):
            lookup_events.append("ordinary")
            self.assertEqual([cell["cell_id"] for cell in cells], ["detail", "aggregate"])
            self.assertTrue(all(cell["_report_year"] == 2024 for cell in cells))
            self.assertIs(kwargs["operand"], operand)
            self.assertEqual(kwargs["query_years"], [2024])
            self.assertEqual(kwargs["period_focus"], "current")
            return ordinary_selected

        def aggregate_selector(cells, **kwargs):
            lookup_events.append("aggregate")
            self.assertEqual([cell["cell_id"] for cell in cells], ["aggregate"])
            self.assertIs(kwargs["operand"], operand)
            self.assertEqual(kwargs["query_years"], [2024])
            self.assertEqual(kwargs["period_focus"], "current")
            return aggregate_selected

        def normalize_value(raw_value, raw_unit):
            lookup_events.append("normalize")
            self.assertEqual((raw_value, raw_unit), ("20", "KRW"))
            return 20.0, "KRW"

        def coerce_row(row, current_evidence, **kwargs):
            lookup_events.append("coerce")
            self.assertIs(current_evidence, evidence_item)
            return row

        with (
            patch.object(financial_lookup_recovery, "operand_period_focus", side_effect=lookup_focus),
            patch.object(financial_lookup_recovery, "select_structured_cell", side_effect=ordinary_selector),
            patch.object(
                financial_lookup_recovery,
                "select_aggregate_structured_cell",
                side_effect=aggregate_selector,
            ),
            patch.object(financial_lookup_recovery, "_normalise_operand_value", side_effect=normalize_value),
            patch.object(financial_lookup_recovery, "coerce_lookup_magnitude_record", side_effect=coerce_row),
        ):
            row = financial_lookup_recovery.lookup_row_from_direct_structured_evidence(
                operand,
                evidence_item,
                index=2,
            )
        self.assertEqual(lookup_events, ["focus", "ordinary", "focus", "aggregate", "normalize", "coerce"])
        self.assertEqual(row["raw_value"], "20")
        self.assertEqual(row["normalized_value"], 20.0)
        self.assertEqual(row["value_role"], "aggregate")
        self.assertEqual(evidence_item, before_evidence)
        self.assertIs(evidence_item["nested"], nested)

        stopped_normalize = Mock(side_effect=AssertionError("aggregate exception must stop normalization"))
        stopped_coerce = Mock(side_effect=AssertionError("aggregate exception must stop coercion"))
        with (
            patch.object(financial_lookup_recovery, "operand_period_focus", return_value="current"),
            patch.object(financial_lookup_recovery, "select_structured_cell", return_value=ordinary_selected),
            patch.object(
                financial_lookup_recovery,
                "select_aggregate_structured_cell",
                side_effect=RuntimeError("aggregate selector failed"),
            ),
            patch.object(financial_lookup_recovery, "_normalise_operand_value", stopped_normalize),
            patch.object(financial_lookup_recovery, "coerce_lookup_magnitude_record", stopped_coerce),
        ):
            with self.assertRaisesRegex(RuntimeError, "aggregate selector failed"):
                financial_lookup_recovery.lookup_row_from_direct_structured_evidence(
                    operand,
                    evidence_item,
                    index=2,
                )
        stopped_normalize.assert_not_called()
        stopped_coerce.assert_not_called()
        self.assertEqual(evidence_item, before_evidence)
        self.assertIs(evidence_item["nested"], nested)

    def test_current_source_candidate_receipts_and_comparative_fallback_pin_order_and_stop(self) -> None:
        nested = {"preserve": True}
        source_rows = [
            {"year": 2024, "rcept_no": "r-2024", "nested": nested},
            {"year": 2023, "rcept_no": "r-2023", "nested": nested},
            {"year": 2023, "rcept_no": "r-2023", "nested": nested},
        ]
        report_scope = {"source_reports": source_rows, "nested": nested}
        query_years = [2024, 2023]

        class ReceiptOperand(dict):
            def get(self, key, default=None):
                if key == "role":
                    raise AssertionError("matched receipts must skip role fallback")
                return super().get(key, default)

        operand = ReceiptOperand({"period_hint": "current", "nested": nested})
        before_operand = dict(operand)
        before_scope = deepcopy(report_scope)
        receipt_events = []

        def source_owner(current_scope):
            receipt_events.append("source")
            self.assertIs(current_scope, report_scope)
            return source_rows

        def target_owner(current_operand, current_years):
            receipt_events.append("target")
            self.assertIs(current_operand, operand)
            self.assertIs(current_years, query_years)
            return [2023, 2024]

        with (
            patch.object(
                financial_scope_policies,
                "_report_scope_source_reports",
                side_effect=source_owner,
            ),
            patch.object(
                financial_scope_policies,
                "operand_target_years",
                side_effect=target_owner,
            ),
        ):
            self.assertEqual(
                financial_scope_policies._operand_target_receipts(
                    operand,
                    query_years,
                    report_scope,
                ),
                ["r-2023", "r-2024"],
            )
        self.assertEqual(receipt_events, ["source", "target"])
        self.assertEqual(dict(operand), before_operand)
        self.assertEqual(report_scope, before_scope)
        self.assertIs(report_scope["nested"], nested)
        self.assertIs(source_rows[0]["nested"], nested)

        skipped_target = Mock(side_effect=AssertionError("empty source must stop target lookup"))
        with (
            patch.object(financial_scope_policies, "_report_scope_source_reports", return_value=[]),
            patch.object(financial_scope_policies, "operand_target_years", skipped_target),
        ):
            self.assertEqual(
                financial_scope_policies._operand_target_receipts({}, [], report_scope),
                [],
            )
        skipped_target.assert_not_called()

        ranked_rows = [
            {"year": 2022, "rcept_no": "r-2022"},
            {"year": 2024, "rcept_no": "r-2024"},
            {"year": 2023, "rcept_no": "r-2023"},
        ]
        for role, expected in (
            ("current_period", ["r-2024"]),
            ("prior_period", ["r-2023"]),
            ("other", []),
        ):
            with self.subTest(role=role):
                with (
                    patch.object(
                        financial_scope_policies,
                        "_report_scope_source_reports",
                        return_value=ranked_rows,
                    ),
                    patch.object(financial_scope_policies, "operand_target_years", return_value=[]),
                ):
                    self.assertEqual(
                        financial_scope_policies._operand_target_receipts(
                            {"role": role},
                            query_years,
                            report_scope,
                        ),
                        expected,
                    )
        self.assertEqual([row["year"] for row in ranked_rows], [2022, 2024, 2023])

        candidate = {
            "metadata": {
                "rcept_no": "r-2024",
                "period_focus": "current",
                "nested": nested,
            },
            "nested": nested,
        }
        current_operand = {"role": "current_period", "nested": nested}
        before_candidate = deepcopy(candidate)
        before_current_operand = deepcopy(current_operand)
        fallback_events = []

        def fallback_source(current_scope):
            fallback_events.append("source")
            self.assertIs(current_scope, report_scope)
            return ranked_rows

        def fallback_targets(current_operand, current_years):
            fallback_events.append("target")
            self.assertIs(current_operand, current_operand_ref)
            self.assertIs(current_years, query_years)
            return [2024]

        def explicit_owner(current_candidate):
            fallback_events.append("explicit")
            self.assertIs(current_candidate, candidate)
            return [2024]

        current_operand_ref = current_operand
        with (
            patch.object(
                financial_scope_policies,
                "_report_scope_source_reports",
                side_effect=fallback_source,
            ),
            patch.object(
                financial_scope_policies,
                "operand_target_years",
                side_effect=fallback_targets,
            ),
            patch.object(
                financial_scope_policies,
                "candidate_explicit_years",
                side_effect=explicit_owner,
            ),
        ):
            self.assertTrue(
                financial_scope_policies._candidate_allows_comparative_report_scope_fallback(
                    candidate,
                    operand=current_operand,
                    query_years=query_years,
                    report_scope=report_scope,
                )
            )
        self.assertEqual(fallback_events, ["source", "target", "explicit"])
        self.assertEqual(candidate, before_candidate)
        self.assertEqual(current_operand, before_current_operand)
        self.assertEqual(report_scope, before_scope)
        self.assertIs(candidate["nested"], nested)

        shallow_source = Mock(return_value=[ranked_rows[0]])
        shallow_targets = Mock(side_effect=AssertionError("one source must stop target lookup"))
        shallow_explicit = Mock(side_effect=AssertionError("one source must stop explicit years"))
        with (
            patch.object(financial_scope_policies, "_report_scope_source_reports", shallow_source),
            patch.object(financial_scope_policies, "operand_target_years", shallow_targets),
            patch.object(financial_scope_policies, "candidate_explicit_years", shallow_explicit),
        ):
            self.assertFalse(
                financial_scope_policies._candidate_allows_comparative_report_scope_fallback(
                    candidate,
                    operand=current_operand,
                    query_years=query_years,
                    report_scope=report_scope,
                )
            )
        shallow_targets.assert_not_called()
        shallow_explicit.assert_not_called()

        class CandidateMetadataBomb(dict):
            def get(self, key, default=None):
                if key == "metadata":
                    raise AssertionError("year mismatch must stop metadata access")
                return super().get(key, default)

        mismatch_candidate = CandidateMetadataBomb()
        with (
            patch.object(financial_scope_policies, "_report_scope_source_reports", return_value=ranked_rows),
            patch.object(financial_scope_policies, "operand_target_years", return_value=[2024]),
            patch.object(financial_scope_policies, "candidate_explicit_years", return_value=[2023]),
        ):
            self.assertFalse(
                financial_scope_policies._candidate_allows_comparative_report_scope_fallback(
                    mismatch_candidate,
                    operand=current_operand,
                    query_years=query_years,
                    report_scope=report_scope,
                )
            )

        class RoleBomb(dict):
            def get(self, key, default=None):
                if key == "role":
                    raise AssertionError("receipt mismatch must stop role access")
                return super().get(key, default)

        with (
            patch.object(financial_scope_policies, "_report_scope_source_reports", return_value=ranked_rows),
            patch.object(financial_scope_policies, "operand_target_years", return_value=[2023]),
            patch.object(financial_scope_policies, "candidate_explicit_years", return_value=[2023]),
        ):
            self.assertFalse(
                financial_scope_policies._candidate_allows_comparative_report_scope_fallback(
                    {"metadata": {"rcept_no": "r-2023", "period_focus": "prior"}},
                    operand=RoleBomb(),
                    query_years=query_years,
                    report_scope=report_scope,
                )
            )

        with (
            patch.object(financial_scope_policies, "_report_scope_source_reports", return_value=ranked_rows),
            patch.object(financial_scope_policies, "operand_target_years", return_value=[2024]),
            patch.object(
                financial_scope_policies,
                "candidate_explicit_years",
                side_effect=RuntimeError("explicit years failed"),
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "explicit years failed"):
                financial_scope_policies._candidate_allows_comparative_report_scope_fallback(
                    candidate,
                    operand=current_operand,
                    query_years=query_years,
                    report_scope=report_scope,
                )

    def test_current_source_candidate_year_projection_pins_policy_fallback_and_exceptions(self) -> None:
        nested = {"preserve": True}
        candidate = {
            "metadata": {
                "period_labels": ["2024 2022", "2024"],
                "year": "2024",
                "structured_cells": [
                    {
                        "period_text": "2023",
                        "column_headers": ["CUR", "PREV"],
                        "nested": nested,
                    }
                ],
                "nested": nested,
            },
            "nested": nested,
        }
        before_candidate = deepcopy(candidate)
        with (
            patch.object(
                financial_scope_policies,
                "PERIOD_FOCUS_POLICY",
                {"explicit_year_pattern": r"20\d{2}"},
            ),
            patch.object(
                financial_scope_policies,
                "STRUCTURED_CELL_PERIOD_SCORING_POLICY",
                {
                    "current_positive_markers": ("CUR",),
                    "prior_positive_markers": ("PREV",),
                },
            ),
        ):
            self.assertEqual(
                financial_scope_policies.candidate_explicit_years(candidate),
                [2022, 2023, 2024],
            )
        self.assertEqual(candidate, before_candidate)
        self.assertIs(candidate["nested"], nested)
        self.assertIs(candidate["metadata"]["structured_cells"][0]["nested"], nested)

        with (
            patch.object(
                financial_scope_policies,
                "PERIOD_FOCUS_POLICY",
                {"explicit_year_pattern": r"20\d{2}"},
            ),
            patch.object(
                financial_scope_policies,
                "STRUCTURED_CELL_PERIOD_SCORING_POLICY",
                {"current_positive_markers": (), "prior_positive_markers": ()},
            ),
        ):
            self.assertEqual(
                financial_scope_policies.candidate_explicit_years(
                    {
                        "metadata": {
                            "period_labels": ["2021"],
                            "year": "bad",
                            "structured_cells": [],
                        }
                    }
                ),
                [2021],
            )

        class PolicyBomb:
            def keys(self):
                raise RuntimeError("period policy copy failed")

            def __getitem__(self, key):
                raise AssertionError(key)

        skipped_scoring = Mock(side_effect=AssertionError("period policy failure must stop scoring policy"))
        with (
            patch.object(financial_scope_policies, "PERIOD_FOCUS_POLICY", PolicyBomb()),
            patch.object(
                financial_scope_policies,
                "STRUCTURED_CELL_PERIOD_SCORING_POLICY",
                skipped_scoring,
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "period policy copy failed"):
                financial_scope_policies.candidate_explicit_years(candidate)

        operand = {"period_hint": "current", "nested": nested}
        query_years = [2024]
        skipped_explicit = Mock(side_effect=AssertionError("empty target years must stop explicit years"))
        with (
            patch.object(financial_scope_policies, "operand_target_years", return_value=[]),
            patch.object(financial_scope_policies, "candidate_explicit_years", skipped_explicit),
        ):
            self.assertFalse(
                financial_scope_policies.candidate_matches_operand_target_year(
                    candidate,
                    operand,
                    query_years,
                )
            )
        skipped_explicit.assert_not_called()

        class MetadataBomb(dict):
            def get(self, key, default=None):
                if key == "metadata":
                    raise AssertionError("explicit overlap must stop metadata access")
                return super().get(key, default)

        with (
            patch.object(financial_scope_policies, "operand_target_years", return_value=[2024]),
            patch.object(financial_scope_policies, "candidate_explicit_years", return_value=[2024]),
        ):
            self.assertTrue(
                financial_scope_policies.candidate_matches_operand_target_year(
                    MetadataBomb(),
                    operand,
                    query_years,
                )
            )

        for period_focus, target_years, expected in (
            ("prior", [2023], True),
            ("current", [2024], True),
            ("unknown", [2024], True),
            ("prior", [2024], False),
        ):
            with self.subTest(period_focus=period_focus, target_years=target_years):
                with (
                    patch.object(financial_scope_policies, "operand_target_years", return_value=target_years),
                    patch.object(financial_scope_policies, "candidate_explicit_years", return_value=[]),
                ):
                    self.assertEqual(
                        financial_scope_policies.candidate_matches_operand_target_year(
                            {"metadata": {"year": 2024, "period_focus": period_focus}},
                            operand,
                            query_years,
                        ),
                        expected,
                    )

        class SoftIntBomb:
            def __int__(self):
                raise ValueError("soft year failure")

        with (
            patch.object(financial_scope_policies, "operand_target_years", return_value=[2024]),
            patch.object(financial_scope_policies, "candidate_explicit_years", return_value=[]),
        ):
            self.assertFalse(
                financial_scope_policies.candidate_matches_operand_target_year(
                    {"metadata": {"year": SoftIntBomb()}},
                    operand,
                    query_years,
                )
            )

        class RuntimeIntBomb:
            def __int__(self):
                raise RuntimeError("year conversion failed")

        with (
            patch.object(financial_scope_policies, "operand_target_years", return_value=[2024]),
            patch.object(financial_scope_policies, "candidate_explicit_years", return_value=[]),
        ):
            with self.assertRaisesRegex(RuntimeError, "year conversion failed"):
                financial_scope_policies.candidate_matches_operand_target_year(
                    {"metadata": {"year": RuntimeIntBomb()}},
                    operand,
                    query_years,
                )

        with (
            patch.object(financial_scope_policies, "operand_target_years", return_value=[2024]),
            patch.object(financial_scope_policies, "candidate_explicit_years", return_value=[]),
            patch.object(
                financial_scope_policies,
                "_normalise_spaces",
                side_effect=RuntimeError("normalization failed"),
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "normalization failed"):
                financial_scope_policies.candidate_matches_operand_target_year(
                    {"metadata": {"year": 2024, "period_focus": "current"}},
                    operand,
                    query_years,
                )

    def test_current_source_candidate_target_report_match_pins_precedence_laziness_and_stop(self) -> None:
        nested = {"preserve": True}
        candidate = {
            "metadata": {"rcept_no": "r-2024", "year": "2024", "nested": nested},
            "nested": nested,
        }
        operand = {"role": "current_period", "nested": nested}
        query_years = [2024]
        report_scope = {"source_reports": [{"rcept_no": "r-2024", "year": 2024}], "nested": nested}
        before_candidate = deepcopy(candidate)
        before_operand = deepcopy(operand)
        before_scope = deepcopy(report_scope)
        events = []

        def source_owner(current_scope):
            events.append("source")
            self.assertIs(current_scope, report_scope)
            return report_scope["source_reports"]

        def explicit_owner(current_candidate):
            events.append("explicit")
            self.assertIs(current_candidate, candidate)
            return [2024]

        def target_owner(current_operand, current_years):
            events.append("target")
            self.assertIs(current_operand, operand)
            self.assertIs(current_years, query_years)
            return [2024]

        def receipt_owner(current_operand, current_years, current_scope):
            events.append("receipts")
            self.assertIs(current_operand, operand)
            self.assertIs(current_years, query_years)
            self.assertIs(current_scope, report_scope)
            return ["r-2024"]

        skipped_fallback = Mock(side_effect=AssertionError("matching receipt must skip fallback"))
        with (
            patch.object(financial_scope_policies, "_report_scope_source_reports", side_effect=source_owner),
            patch.object(financial_scope_policies, "candidate_explicit_years", side_effect=explicit_owner),
            patch.object(financial_scope_policies, "operand_target_years", side_effect=target_owner),
            patch.object(financial_scope_policies, "_operand_target_receipts", side_effect=receipt_owner),
            patch.object(
                financial_scope_policies,
                "_candidate_allows_comparative_report_scope_fallback",
                skipped_fallback,
            ),
        ):
            self.assertTrue(
                financial_scope_policies.candidate_matches_target_report_scope(
                    candidate,
                    operand=operand,
                    query_years=query_years,
                    report_scope=report_scope,
                )
            )
        self.assertEqual(events, ["source", "explicit", "target", "receipts"])
        skipped_fallback.assert_not_called()
        self.assertEqual(candidate, before_candidate)
        self.assertEqual(operand, before_operand)
        self.assertEqual(report_scope, before_scope)
        self.assertIs(candidate["nested"], nested)

        fallback_calls = []

        def comparative(current_candidate, **kwargs):
            fallback_calls.append((current_candidate, kwargs))
            return True

        with (
            patch.object(financial_scope_policies, "_report_scope_source_reports", return_value=report_scope["source_reports"]),
            patch.object(financial_scope_policies, "candidate_explicit_years", return_value=[2024]),
            patch.object(financial_scope_policies, "operand_target_years", return_value=[2024]),
            patch.object(financial_scope_policies, "_operand_target_receipts", return_value=["different"]),
            patch.object(
                financial_scope_policies,
                "_candidate_allows_comparative_report_scope_fallback",
                side_effect=comparative,
            ),
        ):
            self.assertTrue(
                financial_scope_policies.candidate_matches_target_report_scope(
                    candidate,
                    operand=operand,
                    query_years=query_years,
                    report_scope=report_scope,
                )
            )
        self.assertEqual(len(fallback_calls), 1)
        self.assertIs(fallback_calls[0][0], candidate)
        self.assertIs(fallback_calls[0][1]["operand"], operand)
        self.assertIs(fallback_calls[0][1]["query_years"], query_years)
        self.assertIs(fallback_calls[0][1]["report_scope"], report_scope)

        for current_candidate, explicit_years, target_years, receipts, expected in (
            ({"metadata": {"rcept_no": "", "year": 2023}}, [2024], [2024], ["r-2024"], True),
            ({"metadata": {"rcept_no": "", "year": 2024}}, [], [2024], [], True),
            ({"metadata": {"rcept_no": "", "year": 2023}}, [], [2024], [], False),
            ({"metadata": {"rcept_no": "", "year": "bad"}}, [], [2024], [], True),
            ({"metadata": {"rcept_no": "", "year": 2023}}, [], [], [], True),
        ):
            with self.subTest(candidate=current_candidate):
                with (
                    patch.object(financial_scope_policies, "_report_scope_source_reports", return_value=report_scope["source_reports"]),
                    patch.object(financial_scope_policies, "candidate_explicit_years", return_value=explicit_years),
                    patch.object(financial_scope_policies, "operand_target_years", return_value=target_years),
                    patch.object(financial_scope_policies, "_operand_target_receipts", return_value=receipts),
                ):
                    self.assertEqual(
                        financial_scope_policies.candidate_matches_target_report_scope(
                            current_candidate,
                            operand=operand,
                            query_years=query_years,
                            report_scope=report_scope,
                        ),
                        expected,
                    )

        skipped_explicit = Mock(side_effect=AssertionError("empty source must stop explicit years"))
        skipped_targets = Mock(side_effect=AssertionError("empty source must stop target years"))
        with (
            patch.object(financial_scope_policies, "_report_scope_source_reports", return_value=[]),
            patch.object(financial_scope_policies, "candidate_explicit_years", skipped_explicit),
            patch.object(financial_scope_policies, "operand_target_years", skipped_targets),
        ):
            self.assertTrue(
                financial_scope_policies.candidate_matches_target_report_scope(
                    candidate,
                    operand=operand,
                    query_years=query_years,
                    report_scope=report_scope,
                )
            )
        skipped_explicit.assert_not_called()
        skipped_targets.assert_not_called()

        stopped_targets = Mock(side_effect=AssertionError("explicit exception must stop target years"))
        stopped_receipts = Mock(side_effect=AssertionError("explicit exception must stop receipts"))
        with (
            patch.object(financial_scope_policies, "_report_scope_source_reports", return_value=report_scope["source_reports"]),
            patch.object(
                financial_scope_policies,
                "candidate_explicit_years",
                side_effect=RuntimeError("explicit years failed"),
            ),
            patch.object(financial_scope_policies, "operand_target_years", stopped_targets),
            patch.object(financial_scope_policies, "_operand_target_receipts", stopped_receipts),
        ):
            with self.assertRaisesRegex(RuntimeError, "explicit years failed"):
                financial_scope_policies.candidate_matches_target_report_scope(
                    candidate,
                    operand=operand,
                    query_years=query_years,
                    report_scope=report_scope,
                )
        stopped_targets.assert_not_called()
        stopped_receipts.assert_not_called()

    def test_current_source_candidate_report_binding_bonus_pins_scores_order_and_exceptions(self) -> None:
        nested = {"preserve": True}
        operand = {"role": "current_period", "nested": nested}
        query_years = [2024]
        report_scope = {"source_reports": [{"year": 2024, "rcept_no": "r-2024"}], "nested": nested}

        skipped_explicit = Mock(side_effect=AssertionError("empty source must stop explicit years"))
        with (
            patch.object(financial_scope_policies, "_report_scope_source_reports", return_value=[]),
            patch.object(financial_scope_policies, "candidate_explicit_years", skipped_explicit),
        ):
            self.assertEqual(
                financial_scope_policies.candidate_report_scope_binding_bonus(
                    {},
                    operand=operand,
                    query_years=query_years,
                    report_scope=report_scope,
                ),
                0.0,
            )
        skipped_explicit.assert_not_called()

        def evaluate(candidate, *, explicit, targets, receipts, fallback=False):
            fallback_mock = Mock(return_value=fallback)
            with (
                patch.object(
                    financial_scope_policies,
                    "_report_scope_source_reports",
                    return_value=report_scope["source_reports"],
                ),
                patch.object(financial_scope_policies, "candidate_explicit_years", return_value=explicit),
                patch.object(financial_scope_policies, "operand_target_years", return_value=targets),
                patch.object(financial_scope_policies, "_operand_target_receipts", return_value=receipts),
                patch.object(
                    financial_scope_policies,
                    "_candidate_allows_comparative_report_scope_fallback",
                    fallback_mock,
                ),
            ):
                result = financial_scope_policies.candidate_report_scope_binding_bonus(
                    candidate,
                    operand=operand,
                    query_years=query_years,
                    report_scope=report_scope,
                )
            return result, fallback_mock

        cases = [
            ({"metadata": {"rcept_no": "r-2024"}}, [], [2024], ["r-2024"], False, 3.0, 0),
            ({"metadata": {"rcept_no": "other"}}, [], [2024], ["r-2024"], True, 1.25, 1),
            ({"metadata": {"rcept_no": "other"}}, [], [2024], ["r-2024"], False, -3.0, 1),
            ({"metadata": {"rcept_no": ""}}, [2024], [2024], ["r-2024"], False, 1.0, 0),
            ({"metadata": {"rcept_no": ""}}, [], [2024], ["r-2024"], False, -3.0, 0),
            ({"metadata": {"year": 2024}}, [2024], [2024], [], False, 1.0, 0),
            ({"metadata": {"year": 2024}}, [], [2024], [], False, 0.75, 0),
            ({"metadata": {"year": 2023}}, [], [2024], [], False, -0.75, 0),
            ({"metadata": {}}, [], [2024], [], False, 0.0, 0),
            ({"metadata": {"year": 2024}}, [], [], [], False, 0.0, 0),
        ]
        for current_candidate, explicit, targets, receipts, fallback, expected, fallback_count in cases:
            with self.subTest(expected=expected, candidate=current_candidate):
                before_candidate = deepcopy(current_candidate)
                result, fallback_mock = evaluate(
                    current_candidate,
                    explicit=explicit,
                    targets=targets,
                    receipts=receipts,
                    fallback=fallback,
                )
                self.assertEqual(result, expected)
                self.assertEqual(fallback_mock.call_count, fallback_count)
                self.assertEqual(current_candidate, before_candidate)

        events = []
        candidate = {"metadata": {"rcept_no": "other", "year": 2024}, "nested": nested}
        before_candidate = deepcopy(candidate)

        def source_owner(current_scope):
            events.append("source")
            self.assertIs(current_scope, report_scope)
            return report_scope["source_reports"]

        def explicit_owner(current_candidate):
            events.append("explicit")
            self.assertIs(current_candidate, candidate)
            return [2024]

        def target_owner(current_operand, current_years):
            events.append("target")
            self.assertIs(current_operand, operand)
            self.assertIs(current_years, query_years)
            return [2024]

        def receipt_owner(current_operand, current_years, current_scope):
            events.append("receipts")
            self.assertIs(current_operand, operand)
            self.assertIs(current_years, query_years)
            self.assertIs(current_scope, report_scope)
            return ["r-2024"]

        def fallback_owner(current_candidate, **kwargs):
            events.append("fallback")
            self.assertIs(current_candidate, candidate)
            self.assertIs(kwargs["operand"], operand)
            self.assertIs(kwargs["query_years"], query_years)
            self.assertIs(kwargs["report_scope"], report_scope)
            return True

        with (
            patch.object(financial_scope_policies, "_report_scope_source_reports", side_effect=source_owner),
            patch.object(financial_scope_policies, "candidate_explicit_years", side_effect=explicit_owner),
            patch.object(financial_scope_policies, "operand_target_years", side_effect=target_owner),
            patch.object(financial_scope_policies, "_operand_target_receipts", side_effect=receipt_owner),
            patch.object(
                financial_scope_policies,
                "_candidate_allows_comparative_report_scope_fallback",
                side_effect=fallback_owner,
            ),
        ):
            self.assertEqual(
                financial_scope_policies.candidate_report_scope_binding_bonus(
                    candidate,
                    operand=operand,
                    query_years=query_years,
                    report_scope=report_scope,
                ),
                1.25,
            )
        self.assertEqual(events, ["source", "explicit", "target", "receipts", "fallback"])
        self.assertEqual(candidate, before_candidate)
        self.assertIs(candidate["nested"], nested)

        stopped_receipts = Mock(side_effect=AssertionError("target exception must stop receipts"))
        with (
            patch.object(
                financial_scope_policies,
                "_report_scope_source_reports",
                return_value=report_scope["source_reports"],
            ),
            patch.object(financial_scope_policies, "candidate_explicit_years", return_value=[]),
            patch.object(
                financial_scope_policies,
                "operand_target_years",
                side_effect=RuntimeError("target years failed"),
            ),
            patch.object(financial_scope_policies, "_operand_target_receipts", stopped_receipts),
        ):
            with self.assertRaisesRegex(RuntimeError, "target years failed"):
                financial_scope_policies.candidate_report_scope_binding_bonus(
                    candidate,
                    operand=operand,
                    query_years=query_years,
                    report_scope=report_scope,
                )
        stopped_receipts.assert_not_called()

    def test_current_source_candidate_report_period_bindings_pin_defs_calls_dag_and_baseline(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        agent_root = repo_root / "src" / "agent"
        target_names = {
            "_operand_target_receipts",
            "_candidate_allows_comparative_report_scope_fallback",
            "candidate_matches_target_report_scope",
            "candidate_report_scope_binding_bonus",
            "candidate_matches_operand_target_year",
            "candidate_explicit_years",
        }
        module_paths = {path.stem: path for path in agent_root.glob("*.py")}
        module_sources = {
            name: path.read_text(encoding="utf-8-sig")
            for name, path in module_paths.items()
        }
        module_trees = {name: ast.parse(source) for name, source in module_sources.items()}
        definitions = {name: [] for name in target_names}
        calls = {name: [] for name in target_names}
        name_loads = {
            "_report_scope_source_reports": [],
            "STRUCTURED_CELL_PERIOD_SCORING_POLICY": [],
            "PERIOD_FOCUS_POLICY": [],
        }

        class BindingVisitor(ast.NodeVisitor):
            def __init__(self, module_name):
                self.module_name = module_name
                self.function_stack = []
                self.try_depth = 0

            def visit_FunctionDef(self, node):
                if node.name in target_names:
                    definitions[node.name].append((self.module_name, node))
                self.function_stack.append(node.name)
                self.generic_visit(node)
                self.function_stack.pop()

            visit_AsyncFunctionDef = visit_FunctionDef

            def visit_Try(self, node):
                self.try_depth += 1
                self.generic_visit(node)
                self.try_depth -= 1

            visit_TryStar = visit_Try

            def visit_Call(self, node):
                called_name = (
                    node.func.id
                    if isinstance(node.func, ast.Name)
                    else node.func.attr
                    if isinstance(node.func, ast.Attribute)
                    else ""
                )
                if called_name in target_names:
                    calls[called_name].append(
                        (
                            self.module_name,
                            self.function_stack[-1] if self.function_stack else "",
                            type(node.func).__name__,
                            tuple(ast.unparse(arg) for arg in node.args),
                            tuple((kw.arg, ast.unparse(kw.value)) for kw in node.keywords),
                            self.try_depth,
                        )
                    )
                self.generic_visit(node)

            def visit_Name(self, node):
                if isinstance(node.ctx, ast.Load) and node.id in name_loads:
                    name_loads[node.id].append(
                        (
                            self.module_name,
                            self.function_stack[-1] if self.function_stack else "",
                        )
                    )
                self.generic_visit(node)

        for module_name, tree in module_trees.items():
            BindingVisitor(module_name).visit(tree)

        self.assertEqual(
            {
                name: [
                    (module_name, node.end_lineno - node.lineno + 1)
                    for module_name, node in entries
                ]
                for name, entries in definitions.items()
            },
            {
                "_operand_target_receipts": [("financial_scope_policies", 31)],
                "_candidate_allows_comparative_report_scope_fallback": [("financial_scope_policies", 39)],
                "candidate_matches_target_report_scope": [("financial_scope_policies", 46)],
                "candidate_report_scope_binding_bonus": [("financial_scope_policies", 49)],
                "candidate_matches_operand_target_year": [("financial_scope_policies", 27)],
                "candidate_explicit_years": [("financial_scope_policies", 36)],
            },
        )
        self.assertEqual(
            {
                name: (
                    [arg.arg for arg in entries[0][1].args.args],
                    [arg.arg for arg in entries[0][1].args.kwonlyargs],
                )
                for name, entries in definitions.items()
            },
            {
                "_operand_target_receipts": (["operand", "query_years", "report_scope"], []),
                "_candidate_allows_comparative_report_scope_fallback": (
                    ["candidate"],
                    ["operand", "query_years", "report_scope"],
                ),
                "candidate_matches_target_report_scope": (
                    ["candidate"],
                    ["operand", "query_years", "report_scope"],
                ),
                "candidate_report_scope_binding_bonus": (
                    ["candidate"],
                    ["operand", "query_years", "report_scope"],
                ),
                "candidate_matches_operand_target_year": (
                    ["candidate", "operand", "query_years"],
                    [],
                ),
                "candidate_explicit_years": (["candidate"], []),
            },
        )
        self.assertEqual(
            {name: len(entries) for name, entries in calls.items()},
            {
                "_operand_target_receipts": 2,
                "_candidate_allows_comparative_report_scope_fallback": 2,
                "candidate_matches_target_report_scope": 2,
                "candidate_report_scope_binding_bonus": 1,
                "candidate_matches_operand_target_year": 6,
                "candidate_explicit_years": 5,
            },
        )
        self.assertTrue(all(entry[2] == "Name" for entries in calls.values() for entry in entries))
        self.assertTrue(all(entry[5] == 0 for entries in calls.values() for entry in entries))
        self.assertTrue(
            all(len(entry[3]) == 3 and not entry[4] for entry in calls["_operand_target_receipts"])
        )
        self.assertTrue(
            all(
                len(entry[3]) == 1
                and tuple(keyword for keyword, _value in entry[4])
                == ("operand", "query_years", "report_scope")
                for name in (
                    "_candidate_allows_comparative_report_scope_fallback",
                    "candidate_matches_target_report_scope",
                    "candidate_report_scope_binding_bonus",
                )
                for entry in calls[name]
            )
        )
        self.assertTrue(
            all(
                len(entry[3]) == 3 and not entry[4]
                for entry in calls["candidate_matches_operand_target_year"]
            )
        )
        self.assertTrue(
            all(len(entry[3]) == 1 and not entry[4] for entry in calls["candidate_explicit_years"])
        )

        self.assertEqual(
            {
                name: sorted(entry[1] for entry in entries)
                for name, entries in calls.items()
            },
            {
                "_operand_target_receipts": [
                    "candidate_matches_target_report_scope",
                    "candidate_report_scope_binding_bonus",
                ],
                "_candidate_allows_comparative_report_scope_fallback": [
                    "candidate_matches_target_report_scope",
                    "candidate_report_scope_binding_bonus",
                ],
                "candidate_matches_target_report_scope": [
                    "_candidate_is_direct_grounding_candidate",
                    "_candidate_satisfies_ratio_component_acceptance_contract",
                ],
                "candidate_report_scope_binding_bonus": ["_score_operand_candidate"],
                "candidate_matches_operand_target_year": [
                    "_candidate_is_canonical_statement_winner",
                    "_candidate_is_direct_grounding_candidate",
                    "_candidate_satisfies_ratio_component_acceptance_contract",
                    "_direct_candidate_semantic_priority",
                    "_score_operand_candidate",
                    "_score_operand_candidate",
                ],
                "candidate_explicit_years": [
                    "_candidate_allows_comparative_report_scope_fallback",
                    "_candidate_period_table_coherence_bonus",
                    "candidate_matches_operand_target_year",
                    "candidate_matches_target_report_scope",
                    "candidate_report_scope_binding_bonus",
                ],
            },
        )
        selected_callers = target_names
        planned_distribution = {}
        for name, entries in calls.items():
            local_count = sum(entry[1] in selected_callers for entry in entries)
            planned_distribution[name] = (len(entries) - local_count, local_count)
        self.assertEqual(
            planned_distribution,
            {
                "_operand_target_receipts": (0, 2),
                "_candidate_allows_comparative_report_scope_fallback": (0, 2),
                "candidate_matches_target_report_scope": (2, 0),
                "candidate_report_scope_binding_bonus": (1, 0),
                "candidate_matches_operand_target_year": (6, 0),
                "candidate_explicit_years": (1, 4),
            },
        )
        self.assertEqual(
            (
                sum(value[0] for value in planned_distribution.values()),
                sum(value[1] for value in planned_distribution.values()),
            ),
            (10, 8),
        )

        scope_tree = module_trees["financial_scope_policies"]
        scope_functions = [
            node.name
            for node in scope_tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        ]
        self.assertEqual(
            (
                sum(not name.startswith("_") for name in scope_functions),
                sum(name.startswith("_") for name in scope_functions),
            ),
            (9, 9),
        )
        self.assertTrue(target_names.issubset(scope_functions))

        def imported_modules(tree):
            modules = set()
            for node in tree.body:
                if isinstance(node, ast.ImportFrom) and node.module:
                    modules.add(node.module)
                elif isinstance(node, ast.Import):
                    modules.update(alias.name for alias in node.names)
            return modules

        dependency_graph = {
            f"src.agent.{module_name}": imported_modules(tree)
            for module_name, tree in module_trees.items()
        }

        def reachable(start, target):
            pending = [start]
            seen = set()
            while pending:
                current = pending.pop()
                if current in seen:
                    continue
                seen.add(current)
                for dependency in dependency_graph.get(current, set()):
                    if dependency == target:
                        return True
                    if dependency.startswith("src.agent."):
                        pending.append(dependency)
            return False

        self.assertFalse(
            reachable(
                "src.agent.financial_scope_policies",
                "src.agent.financial_graph_helpers",
            )
        )
        self.assertIn(
            "src.config.retrieval_policy",
            imported_modules(scope_tree),
        )
        self.assertEqual(
            [
                entry
                for entry in name_loads["_report_scope_source_reports"]
                if entry[0] == "financial_graph_helpers" and entry[1] not in target_names
            ],
            [],
        )
        self.assertEqual(
            [
                entry
                for entry in name_loads["STRUCTURED_CELL_PERIOD_SCORING_POLICY"]
                if entry[0] == "financial_graph_helpers" and entry[1] not in target_names
            ],
            [],
        )
        self.assertEqual(
            sorted(
                entry[1]
                for entry in name_loads["PERIOD_FOCUS_POLICY"]
                if entry[0] == "financial_graph_helpers" and entry[1] not in target_names
            ),
            ["_candidate_satisfies_direct_acceptance_contract"],
        )

        baseline = json.loads(
            (repo_root / "tests" / "fixtures" / "runtime_domain_terms_baseline.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(len(baseline["records"]), 218)
        selected_source = "\n".join(
            ast.get_source_segment(module_sources[module_name], node) or ""
            for entries in definitions.values()
            for module_name, node in entries
        )
        self.assertEqual(
            [
                record
                for record in baseline["records"]
                if str(record.get("text") or "") in selected_source
            ],
            [],
        )

    def test_current_source_candidate_report_period_callers_pin_args_adoption_order_and_stop(self) -> None:
        nested = {"preserve": True}
        candidate = {
            "candidate_kind": "structured_value",
            "text": "Revenue 100",
            "metadata": {
                "row_label": "Revenue",
                "semantic_label": "Revenue",
                "statement_type": "income_statement",
                "consolidation_scope": "unknown",
                "period_focus": "prior",
                "year": 2024,
                "value_role": "aggregate",
                "aggregation_stage": "final",
                "table_source_id": "table-1",
                "structured_cells": [
                    {"value_text": "100", "unit_hint": "KRW", "nested": nested}
                ],
                "nested": nested,
            },
            "nested": nested,
        }
        operand = {
            "label": "Revenue",
            "role": "current_period",
            "period_hint": "current",
            "unit_family": "PERCENT",
            "binding_policy": {
                "prefer_value_roles": ["aggregate"],
                "prefer_aggregation_stages": ["final"],
            },
            "nested": nested,
        }
        query_years = [2024]
        constraints = {"period_focus": "current", "nested": nested}
        report_scope = {"source_reports": [], "nested": nested}
        before_candidate = deepcopy(candidate)
        before_operand = deepcopy(operand)
        before_constraints = deepcopy(constraints)
        before_scope = deepcopy(report_scope)

        canonical_calls = []

        def canonical_year(current_candidate, current_operand, current_years):
            canonical_calls.append((current_candidate, current_operand, current_years))
            return False

        with (
            patch.object(financial_graph_helpers, "lookup_prefers_canonical_statement_rows", return_value=True),
            patch.object(financial_graph_helpers, "lookup_canonical_statement_preferences", return_value=([], [])),
            patch.object(financial_graph_helpers, "_candidate_direct_match_strength", return_value=3.0),
            patch.object(
                financial_graph_helpers,
                "candidate_matches_operand_target_year",
                side_effect=canonical_year,
            ),
            patch.object(financial_graph_helpers, "operand_period_focus", return_value="prior"),
        ):
            self.assertTrue(
                financial_graph_helpers._candidate_is_canonical_statement_winner(
                    candidate,
                    operand=operand,
                    query_years=query_years,
                )
            )
        self.assertEqual(len(canonical_calls), 1)
        self.assertIs(canonical_calls[0][0], candidate)
        self.assertIs(canonical_calls[0][1], operand)
        self.assertIs(canonical_calls[0][2], query_years)

        with (
            patch.object(financial_graph_helpers, "_candidate_value_role", return_value="aggregate"),
            patch.object(financial_graph_helpers, "_candidate_aggregation_stage", return_value="final"),
            patch.object(financial_graph_helpers, "_candidate_direct_match_strength", return_value=2.5),
            patch.object(financial_graph_helpers, "candidate_matches_operand_target_year", return_value=True) as year_match,
        ):
            self.assertEqual(
                financial_graph_helpers._direct_candidate_semantic_priority(
                    candidate,
                    operand=operand,
                    preferred_statement_types=["income_statement"],
                    query_years=query_years,
                ),
                (1, 1, 1, 1, 26),
            )
        year_match.assert_called_once_with(candidate, operand, query_years)

        coherence_events = []

        def explicit_owner(current_candidate):
            coherence_events.append("explicit")
            self.assertIs(current_candidate, candidate)
            return [2023, 2024]

        def target_owner(current_operand, current_years):
            coherence_events.append("target")
            self.assertIs(current_operand, operand)
            self.assertIs(current_years, query_years)
            return [2024]

        with (
            patch.object(financial_graph_helpers, "candidate_explicit_years", side_effect=explicit_owner),
            patch.object(financial_graph_helpers, "operand_target_years", side_effect=target_owner),
        ):
            self.assertAlmostEqual(
                financial_graph_helpers._candidate_period_table_coherence_bonus(
                    candidate,
                    operand=operand,
                    query_years=query_years,
                ),
                2.6,
            )
        self.assertEqual(coherence_events, ["explicit", "target"])

        def enter_common_direct_patches(stack):
            for current_patch in (
                patch.object(financial_graph_helpers, "candidate_is_descriptor_row", return_value=False),
                patch.object(financial_graph_helpers, "candidate_has_numeric_value_signal", return_value=True),
                patch.object(financial_graph_helpers, "_candidate_direct_match_strength", return_value=2.0),
                patch.object(financial_graph_helpers, "_candidate_value_role", return_value="aggregate"),
                patch.object(financial_graph_helpers, "_candidate_aggregation_stage", return_value="final"),
                patch.object(financial_graph_helpers, "binding_policy_allows_candidate_shape", return_value=True),
                patch.object(financial_graph_helpers, "lookup_prefers_canonical_statement_rows", return_value=False),
                patch.object(financial_graph_helpers, "candidate_consolidation_scope", return_value="unknown"),
                patch.object(financial_graph_helpers, "operand_period_focus", return_value="unknown"),
                patch.object(financial_graph_helpers, "_is_delta_like_row_label", return_value=False),
                patch.object(financial_graph_helpers, "candidate_matches_segment_binding", return_value=True),
            ):
                stack.enter_context(current_patch)

        direct_events = []

        def report_match(current_candidate, **kwargs):
            direct_events.append("report")
            self.assertIs(current_candidate, candidate)
            self.assertIs(kwargs["operand"], operand)
            self.assertIs(kwargs["query_years"], query_years)
            self.assertIsNot(kwargs["report_scope"], report_scope)
            self.assertEqual(kwargs["report_scope"], report_scope)
            self.assertIs(kwargs["report_scope"]["nested"], nested)
            return True

        def year_match_owner(current_candidate, current_operand, current_years):
            direct_events.append("year")
            self.assertIs(current_candidate, candidate)
            self.assertIs(current_operand, operand)
            self.assertIs(current_years, query_years)
            return True

        with ExitStack() as stack:
            enter_common_direct_patches(stack)
            stack.enter_context(
                patch.object(financial_graph_helpers, "candidate_matches_target_report_scope", side_effect=report_match)
            )
            stack.enter_context(
                patch.object(
                financial_graph_helpers,
                "candidate_matches_operand_target_year",
                side_effect=year_match_owner,
                )
            )
            self.assertTrue(
                financial_graph_helpers._candidate_is_direct_grounding_candidate(
                    candidate,
                    operand=operand,
                    constraints=constraints,
                    query_years=query_years,
                    report_scope=report_scope,
                )
            )
        self.assertEqual(direct_events, ["report", "year"])

        stopped_direct_year = Mock(side_effect=AssertionError("report mismatch must stop direct year"))
        with ExitStack() as stack:
            enter_common_direct_patches(stack)
            stack.enter_context(
                patch.object(financial_graph_helpers, "candidate_matches_target_report_scope", return_value=False)
            )
            stack.enter_context(
                patch.object(financial_graph_helpers, "candidate_matches_operand_target_year", stopped_direct_year)
            )
            self.assertFalse(
                financial_graph_helpers._candidate_is_direct_grounding_candidate(
                    candidate,
                    operand=operand,
                    constraints=constraints,
                    query_years=query_years,
                    report_scope=report_scope,
                )
            )
        stopped_direct_year.assert_not_called()

        ratio_events = []

        def ratio_report(current_candidate, **kwargs):
            ratio_events.append("report")
            self.assertIs(current_candidate, candidate)
            self.assertIs(kwargs["operand"], operand)
            self.assertIs(kwargs["query_years"], query_years)
            self.assertEqual(kwargs["report_scope"], report_scope)
            return True

        def ratio_year(current_candidate, current_operand, current_years):
            ratio_events.append("year")
            self.assertIs(current_candidate, candidate)
            self.assertIs(current_operand, operand)
            self.assertIs(current_years, query_years)
            return True

        with (
            patch.object(financial_graph_helpers, "candidate_is_descriptor_row", return_value=False),
            patch.object(financial_graph_helpers, "candidate_has_numeric_value_signal", return_value=True),
            patch.object(financial_graph_helpers, "candidate_matches_segment_binding", return_value=True),
            patch.object(financial_graph_helpers, "candidate_matches_target_report_scope", side_effect=ratio_report),
            patch.object(financial_graph_helpers, "_candidate_value_role", return_value="aggregate"),
            patch.object(financial_graph_helpers, "_candidate_aggregation_stage", return_value="final"),
            patch.object(financial_graph_helpers, "binding_policy_allows_candidate_shape", return_value=True),
            patch.object(financial_graph_helpers, "_operand_surface_contract", return_value={}),
            patch.object(financial_graph_helpers, "_candidate_direct_match_strength", return_value=2.0),
            patch.object(financial_graph_helpers, "operand_period_focus", return_value="unknown"),
            patch.object(
                financial_graph_helpers,
                "candidate_matches_operand_target_year",
                side_effect=ratio_year,
            ),
        ):
            self.assertTrue(
                financial_graph_helpers._candidate_satisfies_ratio_component_acceptance_contract(
                    candidate,
                    operand=operand,
                    constraints=constraints,
                    query_years=query_years,
                    report_scope=report_scope,
                )
            )
        self.assertEqual(ratio_events, ["report", "year"])

        score_events = []

        def score_year(current_candidate, current_operand, current_years):
            score_events.append("year")
            self.assertIs(current_candidate, candidate)
            self.assertIs(current_operand, operand)
            self.assertIs(current_years, query_years)
            return True

        def score_coherence(current_candidate, **kwargs):
            score_events.append("coherence")
            self.assertIs(current_candidate, candidate)
            self.assertIs(kwargs["operand"], operand)
            self.assertIs(kwargs["query_years"], query_years)
            return 2.0

        def score_report(current_candidate, **kwargs):
            score_events.append("report")
            self.assertIs(current_candidate, candidate)
            self.assertIs(kwargs["operand"], operand)
            self.assertIs(kwargs["query_years"], query_years)
            self.assertIsNot(kwargs["report_scope"], report_scope)
            self.assertEqual(kwargs["report_scope"], report_scope)
            self.assertIs(kwargs["report_scope"]["nested"], nested)
            return 3.0

        with (
            patch.object(financial_graph_helpers, "_candidate_conflicts_with_operand_concept", return_value=False),
            patch.object(financial_graph_helpers, "candidate_matches_operand_target_year", side_effect=score_year),
            patch.object(
                financial_graph_helpers,
                "_candidate_period_table_coherence_bonus",
                side_effect=score_coherence,
            ),
            patch.object(
                financial_graph_helpers,
                "candidate_report_scope_binding_bonus",
                side_effect=score_report,
            ),
        ):
            score_with_bonus = financial_graph_helpers._score_operand_candidate(
                candidate,
                operand=operand,
                preferred_statement_types=["income_statement"],
                constraints=constraints,
                query_years=query_years,
                report_scope=report_scope,
            )
        self.assertEqual(score_events, ["year", "coherence", "report"])

        with (
            patch.object(financial_graph_helpers, "_candidate_conflicts_with_operand_concept", return_value=False),
            patch.object(financial_graph_helpers, "candidate_matches_operand_target_year", return_value=True),
            patch.object(financial_graph_helpers, "_candidate_period_table_coherence_bonus", return_value=0.0),
            patch.object(financial_graph_helpers, "candidate_report_scope_binding_bonus", return_value=0.0),
        ):
            score_without_bonus = financial_graph_helpers._score_operand_candidate(
                candidate,
                operand=operand,
                preferred_statement_types=["income_statement"],
                constraints=constraints,
                query_years=query_years,
                report_scope=report_scope,
            )
        self.assertEqual(score_with_bonus, score_without_bonus + 5.0)

        stopped_report = Mock(side_effect=AssertionError("coherence exception must stop report bonus"))
        with (
            patch.object(financial_graph_helpers, "_candidate_conflicts_with_operand_concept", return_value=False),
            patch.object(financial_graph_helpers, "candidate_matches_operand_target_year", return_value=True),
            patch.object(
                financial_graph_helpers,
                "_candidate_period_table_coherence_bonus",
                side_effect=RuntimeError("coherence failed"),
            ),
            patch.object(financial_graph_helpers, "candidate_report_scope_binding_bonus", stopped_report),
        ):
            with self.assertRaisesRegex(RuntimeError, "coherence failed"):
                financial_graph_helpers._score_operand_candidate(
                    candidate,
                    operand=operand,
                    preferred_statement_types=["income_statement"],
                    constraints=constraints,
                    query_years=query_years,
                    report_scope=report_scope,
                )
        stopped_report.assert_not_called()

        self.assertEqual(candidate, before_candidate)
        self.assertEqual(operand, before_operand)
        self.assertEqual(constraints, before_constraints)
        self.assertEqual(report_scope, before_scope)
        self.assertIs(candidate["nested"], nested)
        self.assertIs(operand["nested"], nested)
        self.assertIs(constraints["nested"], nested)
        self.assertIs(report_scope["nested"], nested)

    def test_current_source_local_aggregate_context_pins_order_copy_and_exceptions(self) -> None:
        events = []

        class TextProbe:
            def __init__(self, name, value):
                self.name = name
                self.value = value

            def __str__(self):
                events.append(self.name)
                return self.value

        nested = {"preserve": True}
        candidate = {
            "metadata": {
                "local_heading": TextProbe("heading", " Heading "),
                "table_context": TextProbe("context", "   "),
                "table_header_context": TextProbe("header", " Header "),
                "table_summary_text": TextProbe("summary", " Summary "),
                "nested": nested,
            },
            "nested": nested,
        }
        before = dict(candidate)
        before["metadata"] = dict(candidate["metadata"])

        self.assertEqual(
            financial_surface_contracts.candidate_local_aggregate_context(candidate),
            "Heading Header Summary",
        )
        self.assertEqual(events, ["heading", "context", "header", "summary"])
        self.assertEqual(candidate, before)
        self.assertIs(candidate["nested"], nested)
        self.assertIs(candidate["metadata"]["nested"], nested)
        self.assertEqual(
            financial_surface_contracts.candidate_local_aggregate_context({"metadata": {}}),
            "",
        )

        stopped_events = []

        class RaisingText:
            def __str__(self):
                stopped_events.append("heading")
                raise RuntimeError("heading failed")

        class StoppedText:
            def __str__(self):
                stopped_events.append("stopped")
                raise AssertionError("later context should stay stopped")

        with self.assertRaisesRegex(RuntimeError, "heading failed"):
            financial_surface_contracts.candidate_local_aggregate_context(
                {
                    "metadata": {
                        "local_heading": RaisingText(),
                        "table_context": StoppedText(),
                        "table_header_context": StoppedText(),
                        "table_summary_text": StoppedText(),
                    }
                }
            )
        self.assertEqual(stopped_events, ["heading"])

        class CandidateBomb(dict):
            def get(self, key, default=None):
                raise RuntimeError(f"candidate access failed: {key}")

        with self.assertRaisesRegex(RuntimeError, "candidate access failed: metadata"):
            financial_surface_contracts.candidate_local_aggregate_context(CandidateBomb())

    def test_current_source_consolidation_scope_pins_precedence_policy_order_and_exceptions(self) -> None:
        nested = {"preserve": True}

        class StringBomb:
            def __str__(self):
                raise AssertionError("explicit scope must stop context access")

        explicit_metadata = {
            "consolidation_scope": " custom_scope ",
            "local_heading": StringBomb(),
            "nested": nested,
        }
        before_explicit = dict(explicit_metadata)
        self.assertEqual(
            financial_surface_contracts.candidate_consolidation_scope(explicit_metadata),
            "custom_scope",
        )
        self.assertEqual(explicit_metadata, before_explicit)
        self.assertIs(explicit_metadata["nested"], nested)

        events = []

        class TextProbe:
            def __init__(self, name, value):
                self.name = name
                self.value = value

            def __str__(self):
                events.append(self.name)
                return self.value

        metadata = {
            "consolidation_scope": "unknown",
            "local_heading": TextProbe("heading", " BOTH "),
            "table_context": TextProbe("context", " CONSOLIDATED "),
            "section_path": TextProbe("section", " SEPARATE SOLO SECTION "),
            "table_header_context": TextProbe("header", " HEADER "),
            "nested": nested,
        }
        before = dict(metadata)
        policy = {
            "context_markers": {
                "consolidated": ("CONSOLIDATED",),
                "separate": ("SEPARATE",),
            },
            "separate_section_patterns": (r"SOLO\s+SECTION",),
        }
        with (
            patch.object(financial_surface_contracts, "CONSOLIDATION_SCOPE_POLICY", policy),
            patch.object(
                financial_surface_contracts.re,
                "search",
                side_effect=AssertionError("marker hit must stop regex"),
            ) as regex_search,
        ):
            self.assertEqual(
                financial_surface_contracts.candidate_consolidation_scope(metadata),
                "consolidated",
            )
        regex_search.assert_not_called()
        self.assertEqual(events, ["heading", "context", "section", "header"])
        self.assertEqual(metadata, before)
        self.assertIs(metadata["nested"], nested)

        with patch.object(financial_surface_contracts, "CONSOLIDATION_SCOPE_POLICY", policy):
            self.assertEqual(
                financial_surface_contracts.candidate_consolidation_scope(
                    {"local_heading": "SEPARATE", "section_path": "SOLO SECTION"}
                ),
                "separate",
            )
            self.assertEqual(
                financial_surface_contracts.candidate_consolidation_scope(
                    {"section_path": "SOLO SECTION"}
                ),
                "separate",
            )
            self.assertEqual(
                financial_surface_contracts.candidate_consolidation_scope(
                    {"local_heading": "UNMARKED"}
                ),
                "unknown",
            )
            self.assertEqual(
                financial_surface_contracts.candidate_consolidation_scope(
                    {"consolidation_scope": "   ", "local_heading": "UNMARKED"}
                ),
                "unknown",
            )

        class PolicyBomb:
            def keys(self):
                raise RuntimeError("policy copy failed")

            def __getitem__(self, key):
                raise AssertionError(key)

        with patch.object(financial_surface_contracts, "CONSOLIDATION_SCOPE_POLICY", PolicyBomb()):
            with self.assertRaisesRegex(RuntimeError, "policy copy failed"):
                financial_surface_contracts.candidate_consolidation_scope(
                    {"local_heading": "UNMARKED"}
                )

        stopped_regex = Mock(side_effect=AssertionError("normalization failure must stop regex"))
        with (
            patch.object(
                financial_surface_contracts,
                "_normalise_spaces",
                side_effect=RuntimeError("normalization failed"),
            ),
            patch.object(financial_surface_contracts.re, "search", stopped_regex),
        ):
            with self.assertRaisesRegex(RuntimeError, "normalization failed"):
                financial_surface_contracts.candidate_consolidation_scope(metadata)
        stopped_regex.assert_not_called()

    def test_current_source_binding_policy_shape_pins_rejection_preference_order_and_exceptions(self) -> None:
        nested = {"preserve": True}
        events = []

        class TrackingPolicy(dict):
            def get(self, key, default=None):
                events.append(("get", key))
                return super().get(key, default)

        def normalize(value):
            events.append(("normalize", str(value)))
            return str(value or "").strip().lower()

        avoided = TrackingPolicy(
            {
                "avoid_value_roles": [" blocked ", ""],
                "avoid_aggregation_stages": [" halted "],
                "prefer_value_roles": ["aggregate"],
                "prefer_aggregation_stages": ["final"],
                "nested": nested,
            }
        )
        before_avoided = deepcopy(avoided)
        with patch.object(financial_surface_contracts, "_normalise_spaces", side_effect=normalize):
            self.assertFalse(
                financial_surface_contracts.binding_policy_allows_candidate_shape(
                    value_role=" BLOCKED ",
                    aggregation_stage=" final ",
                    operand_binding_policy=avoided,
                )
            )
        self.assertEqual(
            events,
            [
                ("normalize", " BLOCKED "),
                ("normalize", " final "),
                ("get", "avoid_value_roles"),
                ("normalize", " blocked "),
                ("get", "avoid_aggregation_stages"),
                ("normalize", " halted "),
            ],
        )
        self.assertEqual(avoided, before_avoided)
        self.assertIs(avoided["nested"], nested)

        cases = (
            (
                "aggregate",
                "blocked_stage",
                {
                    "avoid_aggregation_stages": ["blocked_stage"],
                    "prefer_value_roles": ["aggregate"],
                    "prefer_aggregation_stages": ["blocked_stage"],
                },
                False,
            ),
            (
                "detail",
                "final",
                {"prefer_value_roles": ["aggregate"], "prefer_aggregation_stages": ["final"]},
                False,
            ),
            (
                "aggregate",
                "subtotal",
                {"prefer_value_roles": ["aggregate"], "prefer_aggregation_stages": ["final"]},
                False,
            ),
            (
                "aggregate",
                "final",
                {"prefer_value_roles": ["aggregate"], "prefer_aggregation_stages": ["final"]},
                True,
            ),
            ("anything", "anything", {}, True),
            ("", "", {"avoid_value_roles": ["detail"], "avoid_aggregation_stages": ["draft"]}, True),
        )
        for value_role, stage, policy, expected in cases:
            with self.subTest(value_role=value_role, stage=stage, policy=policy):
                self.assertEqual(
                    financial_surface_contracts.binding_policy_allows_candidate_shape(
                        value_role=value_role,
                        aggregation_stage=stage,
                        operand_binding_policy=policy,
                    ),
                    expected,
                )

        class PolicyGetBomb(dict):
            def get(self, key, default=None):
                if key == "avoid_value_roles":
                    raise RuntimeError("avoid roles failed")
                raise AssertionError(f"later policy access: {key}")

        with self.assertRaisesRegex(RuntimeError, "avoid roles failed"):
            financial_surface_contracts.binding_policy_allows_candidate_shape(
                value_role="aggregate",
                aggregation_stage="final",
                operand_binding_policy=PolicyGetBomb(),
            )

        class NormalizeBomb:
            def __str__(self):
                raise RuntimeError("role conversion failed")

        stopped_policy = Mock(side_effect=AssertionError("normalization failure must stop policy"))
        with patch.object(financial_surface_contracts, "_normalise_spaces", side_effect=lambda value: str(value)):
            with self.assertRaisesRegex(RuntimeError, "role conversion failed"):
                financial_surface_contracts.binding_policy_allows_candidate_shape(
                    value_role=NormalizeBomb(),
                    aggregation_stage="final",
                    operand_binding_policy=stopped_policy,
                )
        stopped_policy.assert_not_called()

    def test_current_source_selected_unit_family_pins_precedence_normalization_and_exceptions(self) -> None:
        nested = {"preserve": True}

        class StringBomb:
            def __str__(self):
                raise AssertionError("selected cell must stop metadata fallback")

        candidate = {
            "metadata": {
                "value_text": StringBomb(),
                "raw_value": StringBomb(),
                "unit_hint": StringBomb(),
                "raw_unit": StringBomb(),
                "semantic_label": StringBomb(),
                "row_label": StringBomb(),
                "aggregate_label": StringBomb(),
                "nested": nested,
            },
            "nested": nested,
        }
        selected_cell = {
            "value_text": " 100 ",
            "unit_hint": " KRW ",
            "nested": nested,
        }
        before_candidate = dict(candidate)
        before_candidate["metadata"] = dict(candidate["metadata"])
        before_cell = deepcopy(selected_cell)
        with (
            patch.object(
                financial_surface_contracts,
                "_normalise_operand_value",
                return_value=(100.0, "KRW"),
            ) as normalize_value,
            patch.object(
                financial_surface_contracts,
                "_label_implies_percent_metric",
                side_effect=AssertionError("known unit must stop label inference"),
            ) as label_inference,
        ):
            self.assertEqual(
                financial_surface_contracts.candidate_selected_unit_family(
                    candidate,
                    selected_cell=selected_cell,
                ),
                "KRW",
            )
        normalize_value.assert_called_once_with("100", "KRW")
        label_inference.assert_not_called()
        self.assertEqual(candidate, before_candidate)
        self.assertEqual(selected_cell, before_cell)
        self.assertIs(candidate["nested"], nested)
        self.assertIs(candidate["metadata"]["nested"], nested)
        self.assertIs(selected_cell["nested"], nested)

        with patch.object(
            financial_surface_contracts,
            "_normalise_operand_value",
            return_value=(1.0, "COUNT"),
        ) as normalize_value:
            self.assertEqual(
                financial_surface_contracts.candidate_selected_unit_family(
                    {"metadata": {}},
                    selected_cell={"unit_hint": " count "},
                ),
                "COUNT",
            )
        normalize_value.assert_called_once_with("1", "count")

        label_events = []

        def infer_label(label):
            label_events.append(label)
            return True

        with (
            patch.object(
                financial_surface_contracts,
                "_normalise_operand_value",
                return_value=(7.0, "UNKNOWN"),
            ) as normalize_value,
            patch.object(
                financial_surface_contracts,
                "_label_implies_percent_metric",
                side_effect=infer_label,
            ),
        ):
            self.assertEqual(
                financial_surface_contracts.candidate_selected_unit_family(
                    {
                        "metadata": {
                            "value_text": "7",
                            "semantic_label": " semantic ",
                            "row_label": " row ",
                            "aggregate_label": " aggregate ",
                        }
                    }
                ),
                "PERCENT",
            )
        normalize_value.assert_called_once_with("7", "")
        self.assertEqual(label_events, ["semantic row aggregate"])

        with patch.object(
            financial_surface_contracts,
            "_label_implies_percent_metric",
            return_value=False,
        ) as label_inference:
            self.assertEqual(
                financial_surface_contracts.candidate_selected_unit_family(
                    {"metadata": {"row_label": "ordinary"}}
                ),
                "",
            )
        label_inference.assert_called_once_with("ordinary")

        stopped_label = Mock(side_effect=AssertionError("normalization failure must stop label inference"))
        with (
            patch.object(
                financial_surface_contracts,
                "_normalise_operand_value",
                side_effect=RuntimeError("value normalization failed"),
            ),
            patch.object(financial_surface_contracts, "_label_implies_percent_metric", stopped_label),
        ):
            with self.assertRaisesRegex(RuntimeError, "value normalization failed"):
                financial_surface_contracts.candidate_selected_unit_family(
                    {"metadata": {"value_text": "7", "row_label": "ratio"}}
                )
        stopped_label.assert_not_called()

        with patch.object(
            financial_surface_contracts,
            "_label_implies_percent_metric",
            side_effect=RuntimeError("label inference failed"),
        ):
            with self.assertRaisesRegex(RuntimeError, "label inference failed"):
                financial_surface_contracts.candidate_selected_unit_family(
                    {"metadata": {"row_label": "ratio"}}
                )

    def test_current_source_candidate_metadata_policy_bindings_pin_defs_calls_dag_imports_and_baseline(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        agent_root = repo_root / "src" / "agent"
        target_names = {
            "candidate_local_aggregate_context",
            "candidate_consolidation_scope",
            "binding_policy_allows_candidate_shape",
            "candidate_selected_unit_family",
        }
        module_paths = {path.stem: path for path in agent_root.glob("*.py")}
        module_sources = {
            name: path.read_text(encoding="utf-8-sig")
            for name, path in module_paths.items()
        }
        module_trees = {name: ast.parse(source) for name, source in module_sources.items()}
        definitions = {name: [] for name in target_names}
        calls = {name: [] for name in target_names}
        dependency_loads = {
            "CONSOLIDATION_SCOPE_POLICY": [],
            "_normalise_operand_value": [],
            "_label_implies_percent_metric": [],
        }

        class BindingVisitor(ast.NodeVisitor):
            def __init__(self, module_name):
                self.module_name = module_name
                self.function_stack = []
                self.try_depth = 0

            def visit_FunctionDef(self, node):
                if node.name in target_names:
                    definitions[node.name].append((self.module_name, node))
                self.function_stack.append(node.name)
                self.generic_visit(node)
                self.function_stack.pop()

            visit_AsyncFunctionDef = visit_FunctionDef

            def visit_Try(self, node):
                self.try_depth += 1
                self.generic_visit(node)
                self.try_depth -= 1

            visit_TryStar = visit_Try

            def visit_Call(self, node):
                called_name = node.func.id if isinstance(node.func, ast.Name) else ""
                if called_name in target_names:
                    calls[called_name].append(
                        (
                            self.module_name,
                            self.function_stack[-1] if self.function_stack else "",
                            type(node.func).__name__,
                            tuple(ast.unparse(arg) for arg in node.args),
                            tuple((kw.arg, ast.unparse(kw.value)) for kw in node.keywords),
                            self.try_depth,
                        )
                    )
                self.generic_visit(node)

            def visit_Name(self, node):
                if isinstance(node.ctx, ast.Load) and node.id in dependency_loads:
                    dependency_loads[node.id].append(
                        (
                            self.module_name,
                            self.function_stack[-1] if self.function_stack else "",
                        )
                    )
                self.generic_visit(node)

        for module_name, tree in module_trees.items():
            BindingVisitor(module_name).visit(tree)

        self.assertEqual(
            {
                name: [
                    (module_name, node.end_lineno - node.lineno + 1)
                    for module_name, node in entries
                ]
                for name, entries in definitions.items()
            },
            {
                "candidate_local_aggregate_context": [("financial_surface_contracts", 12)],
                "candidate_consolidation_scope": [("financial_surface_contracts", 26)],
                "binding_policy_allows_candidate_shape": [("financial_surface_contracts", 38)],
                "candidate_selected_unit_family": [("financial_surface_contracts", 40)],
            },
        )
        self.assertEqual(
            {
                name: (
                    [arg.arg for arg in entries[0][1].args.args],
                    [arg.arg for arg in entries[0][1].args.kwonlyargs],
                )
                for name, entries in definitions.items()
            },
            {
                "candidate_local_aggregate_context": (["candidate"], []),
                "candidate_consolidation_scope": (["metadata"], []),
                "binding_policy_allows_candidate_shape": (
                    [],
                    ["value_role", "aggregation_stage", "operand_binding_policy"],
                ),
                "candidate_selected_unit_family": (["candidate"], ["selected_cell"]),
            },
        )
        self.assertEqual(
            {name: len(entries) for name, entries in calls.items()},
            {
                "candidate_local_aggregate_context": 3,
                "candidate_consolidation_scope": 2,
                "binding_policy_allows_candidate_shape": 2,
                "candidate_selected_unit_family": 1,
            },
        )
        self.assertTrue(all(entry[2] == "Name" for entries in calls.values() for entry in entries))
        self.assertTrue(all(entry[5] == 0 for entries in calls.values() for entry in entries))
        self.assertEqual(
            {
                name: [entry[1] for entry in entries]
                for name, entries in calls.items()
            },
            {
                "candidate_local_aggregate_context": [
                    "_candidate_source_priority_bonus",
                    "_candidate_matches_operand",
                    "_candidate_direct_match_strength",
                ],
                "candidate_consolidation_scope": [
                    "_candidate_is_direct_grounding_candidate",
                    "_score_operand_candidate",
                ],
                "binding_policy_allows_candidate_shape": [
                    "_candidate_is_direct_grounding_candidate",
                    "_candidate_satisfies_ratio_component_acceptance_contract",
                ],
                "candidate_selected_unit_family": [
                    "_candidate_satisfies_direct_acceptance_contract"
                ],
            },
        )
        self.assertTrue(
            all(len(entry[3]) == 1 and not entry[4] for entry in calls["candidate_local_aggregate_context"])
        )
        self.assertTrue(
            all(len(entry[3]) == 1 and not entry[4] for entry in calls["candidate_consolidation_scope"])
        )
        self.assertTrue(
            all(
                not entry[3]
                and tuple(keyword for keyword, _value in entry[4])
                == ("value_role", "aggregation_stage", "operand_binding_policy")
                for entry in calls["binding_policy_allows_candidate_shape"]
            )
        )
        self.assertTrue(
            all(
                len(entry[3]) == 1
                and tuple(keyword for keyword, _value in entry[4]) == ("selected_cell",)
                for entry in calls["candidate_selected_unit_family"]
            )
        )

        graph_functions = [
            node.name
            for node in module_trees["financial_graph_helpers"].body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        ]
        owner_functions = [
            node.name
            for node in module_trees["financial_surface_contracts"].body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        ]
        self.assertEqual(
            (
                sum(not name.startswith("_") for name in graph_functions),
                sum(name.startswith("_") for name in graph_functions),
            ),
            (9, 97),
        )
        self.assertEqual(
            (
                sum(not name.startswith("_") for name in owner_functions),
                sum(name.startswith("_") for name in owner_functions),
            ),
            (9, 7),
        )

        def imported_modules(tree):
            modules = set()
            for node in tree.body:
                if isinstance(node, ast.ImportFrom) and node.module:
                    modules.add(node.module)
                elif isinstance(node, ast.Import):
                    modules.update(alias.name for alias in node.names)
            return modules

        dependency_graph = {
            f"src.agent.{module_name}": imported_modules(tree)
            for module_name, tree in module_trees.items()
        }

        def reachable(start, target):
            pending = [start]
            seen = set()
            while pending:
                current = pending.pop()
                if current in seen:
                    continue
                seen.add(current)
                for dependency in dependency_graph.get(current, set()):
                    if dependency == target:
                        return True
                    if dependency.startswith("src.agent."):
                        pending.append(dependency)
            return False

        self.assertFalse(
            reachable(
                "src.agent.financial_surface_contracts",
                "src.agent.financial_graph_helpers",
            )
        )
        self.assertFalse(
            reachable(
                "src.agent.financial_surface_contracts",
                "src.agent.financial_row_surfaces",
            )
        )
        self.assertIn(
            "src.agent.financial_surface_contracts",
            imported_modules(module_trees["financial_graph_helpers"]),
        )
        self.assertIn(
            "src.agent.financial_operation_policies",
            imported_modules(module_trees["financial_surface_contracts"]),
        )
        self.assertIn(
            "src.agent.financial_runtime_normalization",
            imported_modules(module_trees["financial_surface_contracts"]),
        )
        self.assertIn(
            "src.config.retrieval_policy",
            imported_modules(module_trees["financial_surface_contracts"]),
        )
        self.assertEqual(
            sorted(
                caller
                for module_name, caller in dependency_loads["CONSOLIDATION_SCOPE_POLICY"]
                if module_name == "financial_graph_helpers" and caller not in target_names
            ),
            [
                "_build_metric_task_query",
                "_build_reconciliation_retry_queries",
                "_score_operand_candidate",
                "_score_operand_candidate",
            ],
        )
        self.assertEqual(
            [
                caller
                for module_name, caller in dependency_loads["_normalise_operand_value"]
                if module_name == "financial_graph_helpers" and caller not in target_names
            ],
            ["_score_operand_candidate"],
        )
        self.assertEqual(
            [
                caller
                for module_name, caller in dependency_loads["_label_implies_percent_metric"]
                if module_name == "financial_graph_helpers" and caller not in target_names
            ],
            ["_infer_generic_unit_family"],
        )

        baseline = json.loads(
            (repo_root / "tests" / "fixtures" / "runtime_domain_terms_baseline.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(len(baseline["records"]), 218)
        selected_hits = []
        for record in baseline["records"]:
            if record.get("path") != "src/agent/financial_surface_contracts.py":
                continue
            for name, entries in definitions.items():
                node = entries[0][1]
                if any(node.lineno <= line <= node.end_lineno for line in record.get("first_lines") or []):
                    selected_hits.append((name, record))
        self.assertEqual(selected_hits, [])

    def test_current_source_candidate_metadata_policy_callers_pin_args_adoption_order_and_stop(self) -> None:
        nested = {"preserve": True}
        candidate = {
            "candidate_kind": "structured_value",
            "metadata": {
                "statement_type": "unknown",
                "period_focus": "unknown",
                "nested": nested,
            },
            "nested": nested,
        }
        operand = {
            "label": "Metric",
            "unit_family": "KRW",
            "binding_policy": {"nested": nested},
            "nested": nested,
        }
        constraints = {"nested": nested}
        query_years = [2024]
        report_scope = {"nested": nested}
        before_candidate = deepcopy(candidate)
        before_operand = deepcopy(operand)
        before_constraints = deepcopy(constraints)
        before_scope = deepcopy(report_scope)

        source_events = []

        def source_context(current_candidate):
            source_events.append("context")
            self.assertIs(current_candidate, candidate)
            return "aggregate context"

        def positive_surface(text, current_operand):
            source_events.append("surface")
            self.assertEqual(text, "aggregate context")
            self.assertIs(current_operand, operand)
            return True

        with (
            patch.object(financial_graph_helpers, "_is_balance_sheet_aggregate_operand", return_value=False),
            patch.object(financial_graph_helpers, "_is_capex_total_operand", return_value=False),
            patch.object(financial_graph_helpers, "_operand_prefers_contextual_aggregate_match", return_value=True),
            patch.object(financial_graph_helpers, "candidate_local_aggregate_context", side_effect=source_context),
            patch.object(financial_graph_helpers, "_text_has_positive_surface", side_effect=positive_surface),
            patch.object(financial_graph_helpers, "_operand_prefers_note_aggregate_lookup", return_value=False),
        ):
            self.assertEqual(
                financial_graph_helpers._candidate_source_priority_bonus(
                    candidate,
                    operand=operand,
                    statement_type="unknown",
                    value_role="aggregate",
                    aggregation_stage="final",
                    local_heading="",
                ),
                2.0,
            )
        self.assertEqual(source_events, ["context", "surface"])

        direct_events = []

        def binding_shape(**kwargs):
            direct_events.append("binding")
            self.assertEqual(set(kwargs), {"value_role", "aggregation_stage", "operand_binding_policy"})
            self.assertEqual(kwargs["value_role"], "aggregate")
            self.assertEqual(kwargs["aggregation_stage"], "final")
            self.assertIsNot(kwargs["operand_binding_policy"], operand["binding_policy"])
            self.assertIs(kwargs["operand_binding_policy"]["nested"], nested)
            return True

        def consolidation_scope(metadata):
            direct_events.append("consolidation")
            self.assertIsNot(metadata, candidate["metadata"])
            self.assertIs(metadata["nested"], nested)
            return "unknown"

        common_direct_patches = (
            patch.object(financial_graph_helpers, "candidate_is_descriptor_row", return_value=False),
            patch.object(financial_graph_helpers, "candidate_has_numeric_value_signal", return_value=True),
            patch.object(financial_graph_helpers, "_candidate_direct_match_strength", return_value=1.0),
            patch.object(financial_graph_helpers, "_candidate_value_role", return_value="aggregate"),
            patch.object(financial_graph_helpers, "_candidate_aggregation_stage", return_value="final"),
            patch.object(financial_graph_helpers, "lookup_prefers_canonical_statement_rows", return_value=False),
            patch.object(financial_graph_helpers, "operand_period_focus", return_value="unknown"),
            patch.object(financial_graph_helpers, "candidate_matches_segment_binding", return_value=True),
            patch.object(financial_graph_helpers, "candidate_matches_target_report_scope", return_value=True),
            patch.object(financial_graph_helpers, "candidate_matches_operand_target_year", return_value=False),
        )
        with ExitStack() as stack:
            for current_patch in common_direct_patches:
                stack.enter_context(current_patch)
            stack.enter_context(
                patch.object(
                    financial_graph_helpers,
                    "binding_policy_allows_candidate_shape",
                    side_effect=binding_shape,
                )
            )
            stack.enter_context(
                patch.object(
                    financial_graph_helpers,
                    "candidate_consolidation_scope",
                    side_effect=consolidation_scope,
                )
            )
            self.assertTrue(
                financial_graph_helpers._candidate_is_direct_grounding_candidate(
                    candidate,
                    operand=operand,
                    constraints=constraints,
                    query_years=query_years,
                    report_scope=report_scope,
                )
            )
        self.assertEqual(direct_events, ["binding", "consolidation"])

        stopped_consolidation = Mock(side_effect=AssertionError("shape rejection must stop consolidation"))
        with ExitStack() as stack:
            for current_patch in common_direct_patches:
                stack.enter_context(current_patch)
            stack.enter_context(
                patch.object(financial_graph_helpers, "binding_policy_allows_candidate_shape", return_value=False)
            )
            stack.enter_context(
                patch.object(financial_graph_helpers, "candidate_consolidation_scope", stopped_consolidation)
            )
            self.assertFalse(
                financial_graph_helpers._candidate_is_direct_grounding_candidate(
                    candidate,
                    operand=operand,
                    constraints=constraints,
                    query_years=query_years,
                    report_scope=report_scope,
                )
            )
        stopped_consolidation.assert_not_called()

        acceptance_events = []
        selected_cell = {}

        def selected_unit(current_candidate, *, selected_cell):
            acceptance_events.append("unit")
            self.assertIs(current_candidate, candidate)
            self.assertIs(selected_cell, selected_cell_ref)
            return "KRW"

        def direct_strength(current_candidate, current_operand):
            acceptance_events.append("strength")
            self.assertIs(current_candidate, candidate)
            self.assertIs(current_operand, operand)
            return 2.0

        selected_cell_ref = selected_cell
        with (
            patch.object(financial_graph_helpers, "_candidate_is_direct_grounding_candidate", return_value=True),
            patch.object(financial_graph_helpers, "operand_period_focus", return_value="unknown"),
            patch.object(financial_graph_helpers, "candidate_selected_unit_family", side_effect=selected_unit),
            patch.object(financial_graph_helpers, "_candidate_direct_match_strength", side_effect=direct_strength),
            patch.object(financial_graph_helpers, "_candidate_value_role", return_value="aggregate"),
            patch.object(financial_graph_helpers, "_candidate_aggregation_stage", return_value="final"),
            patch.object(financial_graph_helpers, "lookup_prefers_canonical_statement_rows", return_value=False),
            patch.object(financial_graph_helpers, "_is_balance_sheet_aggregate_operand", return_value=False),
            patch.object(financial_graph_helpers, "_is_capex_total_operand", return_value=False),
            patch.object(financial_graph_helpers, "operand_target_years", return_value=[]),
        ):
            self.assertTrue(
                financial_graph_helpers._candidate_satisfies_direct_acceptance_contract(
                    candidate,
                    operand=operand,
                    constraints=constraints,
                    query_years=query_years,
                    operation_family="lookup",
                    selected_cell=selected_cell,
                    report_scope=report_scope,
                )
            )
        self.assertEqual(acceptance_events, ["unit", "strength"])

        stopped_strength = Mock(side_effect=AssertionError("unit mismatch must stop strength"))
        with (
            patch.object(financial_graph_helpers, "_candidate_is_direct_grounding_candidate", return_value=True),
            patch.object(financial_graph_helpers, "operand_period_focus", return_value="unknown"),
            patch.object(financial_graph_helpers, "candidate_selected_unit_family", return_value="USD"),
            patch.object(financial_graph_helpers, "_candidate_direct_match_strength", stopped_strength),
        ):
            self.assertFalse(
                financial_graph_helpers._candidate_satisfies_direct_acceptance_contract(
                    candidate,
                    operand=operand,
                    constraints=constraints,
                    query_years=query_years,
                    operation_family="lookup",
                    selected_cell=selected_cell,
                    report_scope=report_scope,
                )
            )
        stopped_strength.assert_not_called()

        ratio_binding = Mock(return_value=True)
        with (
            patch.object(financial_graph_helpers, "candidate_is_descriptor_row", return_value=False),
            patch.object(financial_graph_helpers, "candidate_has_numeric_value_signal", return_value=True),
            patch.object(financial_graph_helpers, "candidate_matches_segment_binding", return_value=True),
            patch.object(financial_graph_helpers, "candidate_matches_target_report_scope", return_value=True),
            patch.object(financial_graph_helpers, "_candidate_value_role", return_value="aggregate"),
            patch.object(financial_graph_helpers, "_candidate_aggregation_stage", return_value="final"),
            patch.object(financial_graph_helpers, "binding_policy_allows_candidate_shape", ratio_binding),
            patch.object(financial_graph_helpers, "_operand_surface_contract", return_value={}),
            patch.object(financial_graph_helpers, "_candidate_direct_match_strength", return_value=1.0),
            patch.object(financial_graph_helpers, "operand_period_focus", return_value="unknown"),
            patch.object(financial_graph_helpers, "candidate_matches_operand_target_year", return_value=False),
        ):
            self.assertTrue(
                financial_graph_helpers._candidate_satisfies_ratio_component_acceptance_contract(
                    candidate,
                    operand=operand,
                    constraints=constraints,
                    query_years=query_years,
                    report_scope=report_scope,
                )
            )
        self.assertEqual(
            ratio_binding.call_args.kwargs["operand_binding_policy"],
            operand["binding_policy"],
        )
        self.assertIsNot(
            ratio_binding.call_args.kwargs["operand_binding_policy"],
            operand["binding_policy"],
        )
        self.assertIs(
            ratio_binding.call_args.kwargs["operand_binding_policy"]["nested"],
            nested,
        )

        stopped_surface = Mock(side_effect=AssertionError("shape rejection must stop surface contract"))
        with (
            patch.object(financial_graph_helpers, "candidate_is_descriptor_row", return_value=False),
            patch.object(financial_graph_helpers, "candidate_has_numeric_value_signal", return_value=True),
            patch.object(financial_graph_helpers, "candidate_matches_segment_binding", return_value=True),
            patch.object(financial_graph_helpers, "candidate_matches_target_report_scope", return_value=True),
            patch.object(financial_graph_helpers, "_candidate_value_role", return_value="aggregate"),
            patch.object(financial_graph_helpers, "_candidate_aggregation_stage", return_value="final"),
            patch.object(financial_graph_helpers, "binding_policy_allows_candidate_shape", return_value=False),
            patch.object(financial_graph_helpers, "_operand_surface_contract", stopped_surface),
        ):
            self.assertFalse(
                financial_graph_helpers._candidate_satisfies_ratio_component_acceptance_contract(
                    candidate,
                    operand=operand,
                    constraints=constraints,
                    query_years=query_years,
                    report_scope=report_scope,
                )
            )
        stopped_surface.assert_not_called()

        contextual_candidate = {
            "candidate_kind": "structured_value",
            "metadata": {"nested": nested},
            "nested": nested,
        }
        context_calls = []

        def contextual_owner(current_candidate):
            context_calls.append(current_candidate)
            return "contextual aggregate"

        common_context_patches = (
            patch.object(financial_graph_helpers, "_candidate_conflicts_with_operand_concept", return_value=False),
            patch.object(financial_graph_helpers, "_operand_text_match", return_value=False),
            patch.object(financial_graph_helpers, "_is_capex_total_operand", return_value=False),
            patch.object(financial_graph_helpers, "_operand_prefers_contextual_aggregate_match", return_value=True),
            patch.object(financial_graph_helpers, "candidate_local_aggregate_context", side_effect=contextual_owner),
            patch.object(financial_graph_helpers, "_text_has_positive_surface", return_value=True),
            patch.object(financial_graph_helpers, "_candidate_value_role", return_value="aggregate"),
            patch.object(financial_graph_helpers, "_candidate_aggregation_stage", return_value="final"),
        )
        with ExitStack() as stack:
            for current_patch in common_context_patches:
                stack.enter_context(current_patch)
            stack.enter_context(patch.object(financial_graph_helpers, "aggregate_like_row_stage", return_value="none"))
            self.assertTrue(
                financial_graph_helpers._candidate_matches_operand(contextual_candidate, operand)
            )
        self.assertEqual(context_calls, [contextual_candidate])

        context_calls.clear()
        with ExitStack() as stack:
            for current_patch in common_context_patches:
                stack.enter_context(current_patch)
            stack.enter_context(
                patch.object(financial_graph_helpers, "candidate_supports_segment_metric_combo", return_value=False)
            )
            self.assertEqual(
                financial_graph_helpers._candidate_direct_match_strength(contextual_candidate, operand),
                2.0,
            )
        self.assertEqual(context_calls, [contextual_candidate])

        score_candidate = {"metadata": {"nested": nested}, "nested": nested}
        score_operand = {"binding_policy": {}, "nested": nested}
        score_constraints = {"consolidation_scope": "consolidated", "nested": nested}

        def score_with_scope(scope):
            with (
                patch.object(financial_graph_helpers, "_candidate_conflicts_with_operand_concept", return_value=False),
                patch.object(financial_graph_helpers, "_candidate_direct_match_strength", return_value=0.0),
                patch.object(financial_graph_helpers, "_candidate_value_role", return_value=""),
                patch.object(financial_graph_helpers, "_candidate_aggregation_stage", return_value=""),
                patch.object(financial_graph_helpers, "candidate_has_numeric_value_signal", return_value=False),
                patch.object(financial_graph_helpers, "_candidate_location_entity_subject_score", return_value=0.0),
                patch.object(financial_graph_helpers, "candidate_is_descriptor_row", return_value=False),
                patch.object(financial_graph_helpers, "lookup_prefers_canonical_statement_rows", return_value=False),
                patch.object(financial_graph_helpers, "candidate_consolidation_scope", return_value=scope) as scope_owner,
                patch.object(financial_graph_helpers, "operand_period_focus", return_value="unknown"),
                patch.object(financial_graph_helpers, "candidate_segment_binding_bonus", return_value=0.0),
                patch.object(financial_graph_helpers, "_candidate_source_priority_bonus", return_value=0.0),
                patch.object(financial_graph_helpers, "_metadata_period_match_strength", return_value=0.0),
                patch.object(financial_graph_helpers, "_candidate_period_table_coherence_bonus", return_value=0.0),
                patch.object(financial_graph_helpers, "candidate_report_scope_binding_bonus", return_value=0.0),
            ):
                score = financial_graph_helpers._score_operand_candidate(
                    score_candidate,
                    operand=score_operand,
                    preferred_statement_types=[],
                    constraints=score_constraints,
                    query_years=query_years,
                    report_scope=report_scope,
                )
            metadata_arg = scope_owner.call_args.args[0]
            self.assertIsNot(metadata_arg, score_candidate["metadata"])
            self.assertIs(metadata_arg["nested"], nested)
            return score

        self.assertEqual(score_with_scope("consolidated") - score_with_scope("separate"), 4.0)

        stopped_period = Mock(side_effect=AssertionError("scope exception must stop period projection"))
        with (
            patch.object(financial_graph_helpers, "_candidate_conflicts_with_operand_concept", return_value=False),
            patch.object(financial_graph_helpers, "_candidate_direct_match_strength", return_value=0.0),
            patch.object(financial_graph_helpers, "_candidate_value_role", return_value=""),
            patch.object(financial_graph_helpers, "_candidate_aggregation_stage", return_value=""),
            patch.object(financial_graph_helpers, "candidate_has_numeric_value_signal", return_value=False),
            patch.object(financial_graph_helpers, "_candidate_location_entity_subject_score", return_value=0.0),
            patch.object(financial_graph_helpers, "candidate_is_descriptor_row", return_value=False),
            patch.object(financial_graph_helpers, "lookup_prefers_canonical_statement_rows", return_value=False),
            patch.object(
                financial_graph_helpers,
                "candidate_consolidation_scope",
                side_effect=RuntimeError("scope failed"),
            ),
            patch.object(financial_graph_helpers, "operand_period_focus", stopped_period),
        ):
            with self.assertRaisesRegex(RuntimeError, "scope failed"):
                financial_graph_helpers._score_operand_candidate(
                    score_candidate,
                    operand=score_operand,
                    preferred_statement_types=[],
                    constraints=score_constraints,
                    query_years=query_years,
                    report_scope=report_scope,
                )
        stopped_period.assert_not_called()

        self.assertEqual(candidate, before_candidate)
        self.assertEqual(operand, before_operand)
        self.assertEqual(constraints, before_constraints)
        self.assertEqual(report_scope, before_scope)
        self.assertIs(candidate["nested"], nested)
        self.assertIs(operand["nested"], nested)
        self.assertIs(constraints["nested"], nested)
        self.assertIs(report_scope["nested"], nested)


if __name__ == "__main__":
    unittest.main()
