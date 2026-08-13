import ast
from copy import deepcopy
import inspect
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import src.agent.financial_graph_helpers as financial_graph_helpers
import src.agent.financial_graph_planning as financial_graph_planning
import src.agent.financial_dependency_projection as financial_dependency_projection
import src.agent.financial_lookup_recovery as financial_lookup_recovery
import src.agent.financial_reconciliation_candidates as financial_reconciliation_candidates
import src.agent.financial_scope_policies as financial_scope_policies

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
                "_infer_period_focus",
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
            patch.object(financial_graph_helpers, "_infer_period_focus", return_value="prior"),
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
            patch.object(financial_graph_helpers, "_infer_period_focus", period_owner),
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
            (9, 132),
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
            "_infer_period_focus",
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
                    "financial_graph_helpers": 12,
                    "financial_reconciliation_candidates": 2,
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
        self.assertEqual((14 + 23, 1), (37, 1))

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
            (3, 7),
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
            financial_graph_helpers,
            "operand_target_years",
            side_effect=target_years_owner,
        ):
            self.assertEqual(
                financial_graph_helpers._operand_target_receipts(
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
            financial_graph_helpers,
            "operand_target_years",
            side_effect=RuntimeError("target years failed"),
        ):
            with self.assertRaisesRegex(RuntimeError, "target years failed"):
                financial_graph_helpers._operand_target_receipts(
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
                "_select_structured_cell",
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
                "_select_structured_cell",
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


if __name__ == "__main__":
    unittest.main()
