import ast
import inspect
import unittest
from collections import Counter
from copy import deepcopy
from unittest.mock import Mock, patch

from src.agent import financial_aggregate_projection, financial_graph, financial_graph_calculation


class FinancialAggregateRankDedupeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.agent = financial_graph_calculation.FinancialAgentCalculationMixin()

    def test_aggregate_result_rank_preserves_tuple_access_order_and_exceptions(self) -> None:
        rank = financial_aggregate_projection._aggregate_result_rank
        nested = {"preserve": True}
        events = []

        class FallbackStatusBomb:
            def __bool__(self):
                raise AssertionError("result status fallback accessed")

            def __deepcopy__(self, _memo):
                return self

        class SourceIds:
            def __bool__(self):
                events.append("source-bool")
                return True

            def __iter__(self):
                events.append("source-iter")
                return iter(("source-a", "source-b"))

            def __deepcopy__(self, _memo):
                return self

        source_ids = SourceIds()
        row = {
            "status": " READY ",
            "answer": " answer 10 ",
            "calculation_result": {
                "status": FallbackStatusBomb(),
                "source_row_ids": source_ids,
                "nested": nested,
            },
            "nested": nested,
        }
        source_slots = {"task-a": {"normalized_value": 1.0}}
        before = deepcopy(row)

        def normalize(value):
            events.append(("normalize", value))
            return " ".join(str(value).split())

        def material_gap(prepared_row):
            events.append(("gap", prepared_row))
            return ""

        def growth_sign(prepared_row):
            events.append(("sign", prepared_row))
            return 6

        def coherence(prepared_row, prepared_source_slots):
            events.append(("coherence", prepared_row, prepared_source_slots))
            return 5, 4

        with (
            patch.object(
                financial_aggregate_projection,
                "_normalise_spaces",
                side_effect=normalize,
            ),
            patch.object(
                financial_aggregate_projection,
                "material_gap_feedback_for_subtask_result",
                side_effect=material_gap,
            ),
            patch.object(
                financial_aggregate_projection,
                "growth_operand_sign_consistency_rank",
                side_effect=growth_sign,
            ),
            patch.object(
                financial_aggregate_projection,
                "aggregate_result_dependency_coherence_ranks",
                side_effect=coherence,
            ),
        ):
            self.assertEqual(rank(row, source_slots), (3, 1, 1, 6, 5, 4, 2))

        self.assertEqual(
            [event[0] if isinstance(event, tuple) else event for event in events],
            [
                "normalize",
                "gap",
                "normalize",
                "sign",
                "coherence",
                "source-bool",
                "source-iter",
            ],
        )
        self.assertEqual(
            [event[1] for event in events if isinstance(event, tuple) and event[0] == "normalize"],
            [" READY ", " answer 10 "],
        )
        self.assertIs(next(event[1] for event in events if isinstance(event, tuple) and event[0] == "gap"), row)
        self.assertIs(next(event[1] for event in events if isinstance(event, tuple) and event[0] == "sign"), row)
        coherence_event = next(event for event in events if isinstance(event, tuple) and event[0] == "coherence")
        self.assertIs(coherence_event[1], row)
        self.assertIs(coherence_event[2], source_slots)
        self.assertEqual(row, before)
        self.assertIs(row["nested"], nested)
        self.assertIs(row["calculation_result"]["nested"], nested)

        status_cases = {
            "ok": 4,
            "partial": 3,
            "ready": 3,
            "insufficient_operands": 1,
            "retry_retrieval": 1,
            "missing": 0,
            "unknown": 0,
            "": 0,
        }
        with (
            patch.object(
                financial_aggregate_projection,
                "material_gap_feedback_for_subtask_result",
                return_value="gap",
            ),
            patch.object(
                financial_aggregate_projection,
                "growth_operand_sign_consistency_rank",
                return_value=0,
            ),
            patch.object(
                financial_aggregate_projection,
                "aggregate_result_dependency_coherence_ranks",
                return_value=(0, 0),
            ),
        ):
            for status, expected in status_cases.items():
                with self.subTest(status=status):
                    self.assertEqual(rank({"calculation_result": {"status": status}})[0], expected)
            self.assertEqual(
                rank({"status": "ok", "answer": "nonblank"})[:3],
                (4, 0, 1),
            )

        later = Mock()
        with (
            patch.object(
                financial_aggregate_projection,
                "material_gap_feedback_for_subtask_result",
                side_effect=RuntimeError("gap failed"),
            ),
            patch.object(
                financial_aggregate_projection,
                "growth_operand_sign_consistency_rank",
                later,
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "gap failed"):
                rank(row, source_slots)
        later.assert_not_called()

        coherence_owner = Mock()
        with (
            patch.object(
                financial_aggregate_projection,
                "material_gap_feedback_for_subtask_result",
                return_value="",
            ),
            patch.object(
                financial_aggregate_projection,
                "growth_operand_sign_consistency_rank",
                side_effect=RuntimeError("sign failed"),
            ),
            patch.object(
                financial_aggregate_projection,
                "aggregate_result_dependency_coherence_ranks",
                coherence_owner,
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "sign failed"):
                rank(row, source_slots)
        coherence_owner.assert_not_called()

        class SourceIterationBomb:
            def __bool__(self):
                return True

            def __iter__(self):
                raise RuntimeError("source ids failed")

        with (
            patch.object(
                financial_aggregate_projection,
                "material_gap_feedback_for_subtask_result",
                return_value="",
            ),
            patch.object(
                financial_aggregate_projection,
                "growth_operand_sign_consistency_rank",
                return_value=0,
            ),
            patch.object(
                financial_aggregate_projection,
                "aggregate_result_dependency_coherence_ranks",
                return_value=(0, 0),
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "source ids failed"):
                rank({"calculation_result": {"source_row_ids": SourceIterationBomb()}})

    def test_nested_result_rank_preserves_tuple_material_period_source_and_exception_order(self) -> None:
        rank = financial_aggregate_projection.nested_aggregate_result_rank
        nested = {"preserve": True}
        row_source_ids = ["row-a"]
        result_source_ids = ["row-b"]
        selected_claim_ids = ["claim-a"]
        source_evidence_ids = ["claim-b"]
        row = {
            "status": " OK ",
            "answer": "",
            "source_row_ids": row_source_ids,
            "selected_claim_ids": selected_claim_ids,
            "answer_slots": {
                "current_value": {"period": "2024"},
                "prior_value": {"period": "2023"},
            },
            "calculation_result": {
                "status": "ignored",
                "formatted_result": "",
                "rendered_value": " value 10 ",
                "source_row_ids": result_source_ids,
                "source_evidence_ids": source_evidence_ids,
                "nested": nested,
            },
            "nested": nested,
        }
        before = deepcopy(row)
        events = []

        def normalize(value):
            events.append(("normalize", value))
            return " ".join(str(value).split())

        def material(prepared_row):
            events.append(("material", prepared_row))
            return True

        def gap(prepared_row):
            events.append(("gap", prepared_row))
            return ""

        def family(prepared_row):
            events.append(("family", prepared_row))
            return "growth_rate"

        def sign(prepared_row):
            events.append(("sign", prepared_row))
            return 5

        def clean_sources(values):
            events.append(("sources", values))
            return ["row-a", "row-b", "claim-a", "claim-b"]

        def findall(pattern, value):
            events.append(("findall", pattern, value))
            return ["1", "0"]

        with (
            patch.object(financial_aggregate_projection, "_normalise_spaces", side_effect=normalize),
            patch.object(
                financial_aggregate_projection,
                "subtask_row_has_material",
                side_effect=material,
            ),
            patch.object(
                financial_aggregate_projection,
                "material_gap_feedback_for_subtask_result",
                side_effect=gap,
            ),
            patch.object(
                financial_aggregate_projection,
                "aggregate_result_operation_family",
                side_effect=family,
            ),
            patch.object(
                financial_aggregate_projection,
                "growth_operand_sign_consistency_rank",
                side_effect=sign,
            ),
            patch.object(financial_aggregate_projection, "_clean_source_row_ids", side_effect=clean_sources),
            patch.object(financial_aggregate_projection.re, "findall", side_effect=findall),
        ):
            actual = rank(row)

        self.assertEqual(actual, (4, 1, 1, 1, 5, 4, 2, len("value 10")))
        self.assertEqual(
            [event[0] for event in events],
            ["normalize", "material", "gap", "family", "sign", "sources", "normalize", "findall"],
        )
        self.assertEqual(
            next(event[1] for event in events if event[0] == "sources"),
            [row_source_ids, result_source_ids, selected_claim_ids, source_evidence_ids],
        )
        self.assertEqual(
            [event[1] for event in events if event[0] == "normalize"],
            [" OK ", " value 10 "],
        )
        self.assertEqual(
            next(event[1:] for event in events if event[0] == "findall"),
            (r"\d", "value 10"),
        )
        for event in events:
            if event[0] in {"material", "gap", "family", "sign"}:
                self.assertIs(event[1], row)
        self.assertEqual(row, before)
        self.assertIs(row["nested"], nested)
        self.assertIs(row["calculation_result"]["nested"], nested)

        fallback_row = {
            "status": "",
            "answer": "",
            "calculation_result": {"status": "partial"},
        }
        polarity_cases = (
            (False, "", "lookup", (3, 0, 1, 1)),
            (True, "gap", "lookup", (3, 1, 0, 1)),
            (True, "", "aggregate_subtasks", (3, 1, 1, 0)),
        )
        for material_value, gap_value, family_value, expected_prefix in polarity_cases:
            with self.subTest(nested_polarity=expected_prefix):
                with (
                    patch.object(
                        financial_aggregate_projection,
                        "subtask_row_has_material",
                        return_value=material_value,
                    ),
                    patch.object(
                        financial_aggregate_projection,
                        "material_gap_feedback_for_subtask_result",
                        return_value=gap_value,
                    ),
                    patch.object(
                        financial_aggregate_projection,
                        "aggregate_result_operation_family",
                        return_value=family_value,
                    ),
                    patch.object(
                        financial_aggregate_projection,
                        "growth_operand_sign_consistency_rank",
                        return_value=0,
                    ),
                    patch.object(
                        financial_aggregate_projection,
                        "_clean_source_row_ids",
                        return_value=[],
                    ),
                ):
                    self.assertEqual(rank(fallback_row)[:4], expected_prefix)

        later = Mock()
        with (
            patch.object(
                financial_aggregate_projection,
                "subtask_row_has_material",
                side_effect=RuntimeError("material failed"),
            ),
            patch.object(
                financial_aggregate_projection,
                "material_gap_feedback_for_subtask_result",
                later,
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "material failed"):
                rank(row)
        later.assert_not_called()

        family_owner = Mock()
        with (
            patch.object(financial_aggregate_projection, "subtask_row_has_material", return_value=True),
            patch.object(
                financial_aggregate_projection,
                "material_gap_feedback_for_subtask_result",
                side_effect=RuntimeError("gap failed"),
            ),
            patch.object(financial_aggregate_projection, "aggregate_result_operation_family", family_owner),
        ):
            with self.assertRaisesRegex(RuntimeError, "gap failed"):
                rank(row)
        family_owner.assert_not_called()

        source_owner = Mock()
        with (
            patch.object(financial_aggregate_projection, "subtask_row_has_material", return_value=True),
            patch.object(financial_aggregate_projection, "material_gap_feedback_for_subtask_result", return_value=""),
            patch.object(financial_aggregate_projection, "aggregate_result_operation_family", return_value="lookup"),
            patch.object(
                financial_aggregate_projection,
                "growth_operand_sign_consistency_rank",
                side_effect=RuntimeError("sign failed"),
            ),
            patch.object(financial_aggregate_projection, "_clean_source_row_ids", source_owner),
        ):
            with self.assertRaisesRegex(RuntimeError, "sign failed"):
                rank(row)
        source_owner.assert_not_called()

        regex_owner = Mock()
        with (
            patch.object(financial_aggregate_projection, "subtask_row_has_material", return_value=True),
            patch.object(financial_aggregate_projection, "material_gap_feedback_for_subtask_result", return_value=""),
            patch.object(financial_aggregate_projection, "aggregate_result_operation_family", return_value="lookup"),
            patch.object(financial_aggregate_projection, "growth_operand_sign_consistency_rank", return_value=0),
            patch.object(
                financial_aggregate_projection,
                "_clean_source_row_ids",
                side_effect=RuntimeError("source clean failed"),
            ),
            patch.object(financial_aggregate_projection.re, "findall", regex_owner),
        ):
            with self.assertRaisesRegex(RuntimeError, "source clean failed"):
                rank(row)
        regex_owner.assert_not_called()

        with (
            patch.object(financial_aggregate_projection, "subtask_row_has_material", return_value=True),
            patch.object(financial_aggregate_projection, "material_gap_feedback_for_subtask_result", return_value=""),
            patch.object(financial_aggregate_projection, "aggregate_result_operation_family", return_value="lookup"),
            patch.object(financial_aggregate_projection, "growth_operand_sign_consistency_rank", return_value=0),
            patch.object(financial_aggregate_projection, "_clean_source_row_ids", return_value=[]),
            patch.object(
                financial_aggregate_projection.re,
                "findall",
                side_effect=RuntimeError("regex failed"),
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "regex failed"):
                rank(row)

    def test_dedupe_preserves_stable_winners_passthrough_copies_and_exceptions(self) -> None:
        dedupe = financial_aggregate_projection.dedupe_aggregate_subtask_results
        nested = {"preserve": True}
        blank_first = {"id": "blank-first", "signature": "", "nested": nested}
        a_first = {"id": "a-first", "signature": "a", "rank": 5, "nested": nested}
        b_only = {"id": "b-only", "signature": "b", "rank": 2, "nested": nested}
        a_later = {"id": "a-later", "signature": "a", "rank": 5, "nested": nested}
        blank_last = {"id": "blank-last", "signature": "", "nested": nested}
        rows = [blank_first, a_first, b_only, a_later, blank_last]
        before = deepcopy(rows)
        source_slots = {"task-a": {"normalized_value": 1.0}}
        events = []

        def source_map(prepared_rows):
            events.append(("source-map", prepared_rows))
            return source_slots

        def signature(row):
            events.append(("signature", row))
            return row["signature"]

        def row_rank(row, prepared_source_slots):
            events.append(("rank", row, prepared_source_slots))
            value = row["rank"]
            return value, value, value, value, value, value, value

        with (
            patch.object(
                financial_aggregate_projection,
                "aggregate_source_slot_by_task_id",
                side_effect=source_map,
            ),
            patch.object(
                financial_aggregate_projection,
                "aggregate_result_signature",
                side_effect=signature,
            ),
            patch.object(financial_aggregate_projection, "_aggregate_result_rank", side_effect=row_rank),
        ):
            actual = dedupe(rows)

        self.assertEqual(
            [row["id"] for row in actual],
            ["blank-first", "b-only", "a-later", "blank-last"],
        )
        self.assertIs(events[0][1], rows)
        self.assertEqual(
            [event[1]["id"] for event in events if event[0] == "signature"],
            [row["id"] for row in rows],
        )
        self.assertEqual(
            [event[1]["id"] for event in events if event[0] == "rank"],
            ["a-first", "b-only", "a-later"],
        )
        self.assertTrue(all(event[2] is source_slots for event in events if event[0] == "rank"))
        selected_originals = [blank_first, b_only, a_later, blank_last]
        self.assertIsNot(actual, rows)
        self.assertTrue(all(current is not original for current, original in zip(actual, selected_originals)))
        self.assertTrue(all(row["nested"] is nested for row in actual))
        self.assertEqual(rows, before)
        self.assertTrue(all(row["nested"] is nested for row in rows))

        unequal_rows = [
            {"id": "early-high", "signature": "keep", "rank": 9},
            {"id": "early-low", "signature": "move", "rank": 1},
            {"id": "later-high", "signature": "move", "rank": 9},
            {"id": "later-low", "signature": "keep", "rank": 1},
        ]
        with (
            patch.object(
                financial_aggregate_projection,
                "aggregate_source_slot_by_task_id",
                return_value=source_slots,
            ),
            patch.object(
                financial_aggregate_projection,
                "aggregate_result_signature",
                side_effect=lambda row: row["signature"],
            ),
            patch.object(
                financial_aggregate_projection,
                "_aggregate_result_rank",
                side_effect=lambda row, _slots: (row["rank"],) * 7,
            ),
        ):
            unequal_actual = dedupe(unequal_rows)
        self.assertEqual(
            [row["id"] for row in unequal_actual],
            ["early-high", "later-high"],
        )

        with (
            patch.object(
                financial_aggregate_projection,
                "aggregate_source_slot_by_task_id",
                return_value=source_slots,
            ) as empty_source_owner,
            patch.object(financial_aggregate_projection, "aggregate_result_signature") as empty_signature_owner,
        ):
            empty_first = dedupe([])
            empty_second = dedupe([])
        self.assertEqual(empty_first, [])
        self.assertIsNot(empty_first, empty_second)
        self.assertEqual(empty_source_owner.call_count, 2)
        empty_signature_owner.assert_not_called()

        signature_owner = Mock()
        with (
            patch.object(
                financial_aggregate_projection,
                "aggregate_source_slot_by_task_id",
                side_effect=RuntimeError("source map failed"),
            ),
            patch.object(financial_aggregate_projection, "aggregate_result_signature", signature_owner),
        ):
            with self.assertRaisesRegex(RuntimeError, "source map failed"):
                dedupe(rows)
        signature_owner.assert_not_called()

        rank_owner = Mock()
        with (
            patch.object(financial_aggregate_projection, "aggregate_source_slot_by_task_id", return_value=source_slots),
            patch.object(
                financial_aggregate_projection,
                "aggregate_result_signature",
                side_effect=RuntimeError("signature failed"),
            ),
            patch.object(financial_aggregate_projection, "_aggregate_result_rank", rank_owner),
        ):
            with self.assertRaisesRegex(RuntimeError, "signature failed"):
                dedupe(rows)
        rank_owner.assert_not_called()

        signature_owner = Mock(side_effect=lambda row: row["signature"])
        with (
            patch.object(financial_aggregate_projection, "aggregate_source_slot_by_task_id", return_value=source_slots),
            patch.object(financial_aggregate_projection, "aggregate_result_signature", signature_owner),
            patch.object(
                financial_aggregate_projection,
                "_aggregate_result_rank",
                side_effect=RuntimeError("rank failed"),
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "rank failed"):
                dedupe(rows)
        self.assertEqual(signature_owner.call_count, 2)

    def test_graph_bindings_preserve_external10_args_gates_adoption_and_stop(self) -> None:
        targets = {
            "result": "_aggregate_result_rank",
            "nested": "nested_aggregate_result_rank",
            "dedupe": "dedupe_aggregate_subtask_results",
        }
        calls = {key: [] for key in targets}
        for module_name, module in (
            ("owner", financial_aggregate_projection),
            ("graph", financial_graph_calculation),
        ):
            tree = ast.parse(inspect.getsource(module))
            parents = {}
            for parent in ast.walk(tree):
                for child in ast.iter_child_nodes(parent):
                    parents[child] = parent
            for key, name in targets.items():
                for node in ast.walk(tree):
                    if not isinstance(node, ast.Call):
                        continue
                    if not isinstance(node.func, ast.Name) or node.func.id != name:
                        continue
                    owner = node
                    while owner in parents and not isinstance(owner, ast.FunctionDef):
                        owner = parents[owner]
                    statement = node
                    while statement in parents and not isinstance(statement, ast.stmt):
                        statement = parents[statement]
                    calls[key].append(
                        {
                            "module": module_name,
                            "caller": owner.name,
                            "args": tuple(ast.unparse(arg) for arg in node.args),
                            "call": node,
                            "statement": statement,
                            "parents": parents,
                        }
                    )

        self.assertEqual(
            [(entry["caller"], entry["args"]) for entry in calls["result"]],
            [
                (
                    "dedupe_aggregate_subtask_results",
                    ("row", "source_slot_by_task_id"),
                )
            ],
        )
        self.assertEqual([entry["module"] for entry in calls["result"]], ["owner"])
        self.assertEqual({entry["module"] for entry in calls["nested"]}, {"graph"})
        self.assertEqual({entry["module"] for entry in calls["dedupe"]}, {"graph"})
        self.assertEqual(
            Counter(
                (entry["caller"], entry["args"])
                for entry in calls["nested"]
            ),
            Counter(
                {
                    ("_promote_stronger_nested_aggregate_results", ("nested_row",)): 1,
                    ("_promote_stronger_nested_aggregate_results", ("current_row",)): 1,
                }
            ),
        )
        self.assertEqual(
            Counter(
                (entry["caller"], entry["args"])
                for entry in calls["dedupe"]
            ),
            Counter(
                {
                    ("_prepare_initial_aggregate_state", ("ordered_results",)): 3,
                    ("_prepare_initial_aggregate_state", ("early_aligned_results",)): 1,
                    ("_collect_initial_aggregate_evidence_state", ("own_unit_aligned_results",)): 2,
                    ("_aggregate_calculation_subtasks", ("late_unit_aligned_results",)): 2,
                }
            ),
        )
        self.assertEqual((len(calls["nested"]), len(calls["dedupe"])), (2, 8))

        nested_statements = {id(entry["statement"]): entry["statement"] for entry in calls["nested"]}
        self.assertEqual(len(nested_statements), 1)
        nested_statement = next(iter(nested_statements.values()))
        self.assertIsInstance(nested_statement, ast.If)
        self.assertIsInstance(nested_statement.test, ast.Compare)
        self.assertIsInstance(nested_statement.test.ops[0], ast.LtE)
        self.assertIsInstance(nested_statement.body[0], ast.Continue)

        expected_adoption = Counter(
            {
                ("_prepare_initial_aggregate_state", "ordered_results"): 4,
                ("_collect_initial_aggregate_evidence_state", "ordered_results"): 2,
                ("_aggregate_calculation_subtasks", "late_unit_results"): 2,
            }
        )
        actual_adoption = Counter()
        for entry in calls["dedupe"]:
            statement = entry["statement"]
            self.assertIsInstance(statement, ast.Assign)
            self.assertEqual(len(statement.targets), 1)
            actual_adoption[(entry["caller"], ast.unparse(statement.targets[0]))] += 1
            ancestor = entry["call"]
            parents = entry["parents"]
            while ancestor in parents and not isinstance(ancestor, ast.FunctionDef):
                ancestor = parents[ancestor]
                self.assertNotIsInstance(ancestor, ast.Try)
        self.assertEqual(actual_adoption, expected_adoption)

        state = {"subtask_results": [], "calc_subtasks": []}
        nested = {"preserve": True}
        current_result = {"task_id": "task-a"}
        upserted_row = {"task_id": "task-a", "nested": nested}
        upserted_rows = [upserted_row]
        deduped_rows = [{"task_id": "deduped", "nested": nested}]
        adopted = {}

        def stop_after_dedupe(rows, prepared_state):
            adopted["rows"] = rows
            adopted["state"] = prepared_state
            raise RuntimeError("recovery stop")

        with (
            patch.object(
                self.agent,
                "_capture_current_subtask_result",
                return_value=current_result,
                create=True,
            ),
            patch.object(
                self.agent,
                "_upsert_subtask_result",
                return_value=upserted_rows,
                create=True,
            ),
            patch.object(
                financial_graph_calculation,
                "dedupe_aggregate_subtask_results",
                return_value=deduped_rows,
            ) as dedupe_owner,
            patch.object(
                self.agent,
                "_recover_lookup_results_from_sibling_table_evidence",
                side_effect=stop_after_dedupe,
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "recovery stop"):
                self.agent._prepare_initial_aggregate_state(state)
        prepared_rows = dedupe_owner.call_args.args[0]
        self.assertEqual(prepared_rows, upserted_rows)
        self.assertIsNot(prepared_rows, upserted_rows)
        self.assertIs(prepared_rows[0], upserted_row)
        self.assertIs(adopted["rows"], deduped_rows)
        self.assertIs(adopted["state"], state)

        downstream_owner = Mock()
        with (
            patch.object(
                self.agent,
                "_capture_current_subtask_result",
                return_value=current_result,
                create=True,
            ),
            patch.object(
                self.agent,
                "_upsert_subtask_result",
                return_value=upserted_rows,
                create=True,
            ),
            patch.object(
                financial_graph_calculation,
                "dedupe_aggregate_subtask_results",
                side_effect=RuntimeError("dedupe binding failed"),
            ),
            patch.object(
                self.agent,
                "_recover_lookup_results_from_sibling_table_evidence",
                downstream_owner,
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "dedupe binding failed"):
                self.agent._prepare_initial_aggregate_state(state)
        downstream_owner.assert_not_called()

        current_row = {
            "task_id": "task-a",
            "status": "partial",
            "family": "lookup",
            "nested": nested,
        }
        nested_row = {
            "task_id": "task-a",
            "status": "ok",
            "family": "lookup",
            "answer": "nested answer 10",
            "nested": nested,
        }
        aggregate_row = {
            "task_id": "aggregate",
            "family": "aggregate_subtasks",
            "calculation_result": {"subtask_results": [nested_row]},
        }
        ordered_results = [current_row, aggregate_row]
        source_slots = {"task-a": {"normalized_value": 1.0}}
        events = []

        def operation_family(row):
            return row.get("family", "")

        def nested_rank(row):
            events.append(("rank", row))
            value = 2 if row is nested_row else 1
            return (value,) * 8

        def coherence(row, prepared_source_slots):
            events.append(("coherence", row, prepared_source_slots))
            return 1, 1

        with (
            patch.object(
                self.agent,
                "_aggregate_result_operation_family",
                side_effect=operation_family,
            ),
            patch.object(
                financial_graph_calculation,
                "aggregate_source_slot_by_task_id",
                return_value=source_slots,
            ),
            patch.object(
                self.agent,
                "_nested_subtask_rows",
                return_value=[nested_row],
                create=True,
            ),
            patch.object(
                financial_graph_calculation,
                "material_gap_feedback_for_subtask_result",
                return_value="",
            ),
            patch.object(
                financial_graph_calculation,
                "nested_aggregate_result_rank",
                side_effect=nested_rank,
            ),
            patch.object(
                financial_graph_calculation,
                "aggregate_result_dependency_coherence_ranks",
                side_effect=coherence,
            ),
        ):
            promoted = self.agent._promote_stronger_nested_aggregate_results(
                ordered_results
            )

        self.assertEqual(
            [event[0] for event in events],
            ["rank", "rank", "coherence", "coherence"],
        )
        self.assertIs(events[0][1], nested_row)
        prepared_current = events[1][1]
        self.assertEqual(prepared_current, current_row)
        self.assertIsNot(prepared_current, current_row)
        self.assertIs(prepared_current["nested"], nested)
        self.assertIs(events[2][1], nested_row)
        self.assertIs(events[3][1], prepared_current)
        self.assertIs(events[2][2], source_slots)
        self.assertIs(events[3][2], source_slots)
        self.assertTrue(promoted[0]["promoted_from_nested_aggregate"])
        self.assertIs(promoted[0]["nested"], nested)

        coherence_owner = Mock()
        with (
            patch.object(
                self.agent,
                "_aggregate_result_operation_family",
                side_effect=operation_family,
            ),
            patch.object(
                financial_graph_calculation,
                "aggregate_source_slot_by_task_id",
                return_value=source_slots,
            ),
            patch.object(
                self.agent,
                "_nested_subtask_rows",
                return_value=[nested_row],
                create=True,
            ),
            patch.object(
                financial_graph_calculation,
                "material_gap_feedback_for_subtask_result",
                return_value="",
            ),
            patch.object(
                financial_graph_calculation,
                "nested_aggregate_result_rank",
                side_effect=[(1,) * 8, (1,) * 8],
            ),
            patch.object(
                financial_graph_calculation,
                "aggregate_result_dependency_coherence_ranks",
                coherence_owner,
            ),
        ):
            unchanged = self.agent._promote_stronger_nested_aggregate_results(
                ordered_results
            )
        self.assertIs(unchanged, ordered_results)
        coherence_owner.assert_not_called()

        rank_calls = []

        def failing_rank(row):
            rank_calls.append(row)
            raise RuntimeError("nested rank failed")

        with (
            patch.object(
                self.agent,
                "_aggregate_result_operation_family",
                side_effect=operation_family,
            ),
            patch.object(
                financial_graph_calculation,
                "aggregate_source_slot_by_task_id",
                return_value=source_slots,
            ),
            patch.object(
                self.agent,
                "_nested_subtask_rows",
                return_value=[nested_row],
                create=True,
            ),
            patch.object(
                financial_graph_calculation,
                "material_gap_feedback_for_subtask_result",
                return_value="",
            ),
            patch.object(
                financial_graph_calculation,
                "nested_aggregate_result_rank",
                side_effect=failing_rank,
            ),
            patch.object(
                financial_graph_calculation,
                "aggregate_result_dependency_coherence_ranks",
                coherence_owner,
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "nested rank failed"):
                self.agent._promote_stronger_nested_aggregate_results(
                    ordered_results
                )
        self.assertEqual(rank_calls, [nested_row])
        coherence_owner.assert_not_called()

    def test_current_source_ratio_rebuild_seeds_pin_precedence_copy_order_and_exceptions(self) -> None:
        nested = {"preserve": True}

        class RoleBomb:
            def __bool__(self):
                raise AssertionError("fallback role truthiness accessed")

            def __str__(self):
                raise AssertionError("fallback role string accessed")

            def __deepcopy__(self, _memo):
                return self

        class CalculationResultBomb(dict):
            def get(self, key, default=None):
                if key == "calculation_operands":
                    raise AssertionError("calculation-result operands accessed")
                return super().get(key, default)

        numerator_seed = {
            "matched_operand_role": " numerator_1 ",
            "role": RoleBomb(),
            "label": "numerator",
            "nested": nested,
        }
        fallback_denominator_seed = {"label": "denominator", "nested": nested}
        material_unknown_seed = {"role": "other", "normalized_value": 3.0, "nested": nested}
        empty_unknown_seed = {"role": "empty", "nested": nested}
        row_denominator_seed = {
            "role": "denominator_1",
            "label": "row denominator",
            "nested": nested,
        }
        answer_slots = {
            "components_by_group": {
                "fallback-num": [numerator_seed, "skip-nondict"],
                "fallback-den": [fallback_denominator_seed],
            },
            "components_by_role": {
                "ignored-fallback": [material_unknown_seed, empty_unknown_seed],
            },
        }
        row = {"calculation_operands": [row_denominator_seed], "nested": nested}
        calculation_result = CalculationResultBomb({"nested": nested})
        before = deepcopy(
            {
                "row": row,
                "answer_slots": answer_slots,
                "calculation_result": dict(calculation_result),
            }
        )
        normalized_roles = []
        group_roles = []
        material_rows = []

        def normalize(value):
            normalized_roles.append(value)
            return " ".join(str(value).split())

        def ratio_group(role):
            group_roles.append(role)
            if role in {"numerator_1", "fallback-num"}:
                return "numerator"
            if role in {"denominator_1", "fallback-den"}:
                return "denominator"
            return ""

        def has_material(seed):
            material_rows.append(seed)
            return seed.get("normalized_value") is not None

        with (
            patch.object(financial_aggregate_projection, "_normalise_spaces", side_effect=normalize),
            patch.object(
                financial_aggregate_projection,
                "dependency_ratio_role_group",
                side_effect=ratio_group,
            ),
            patch.object(
                financial_aggregate_projection,
                "answer_slot_has_material",
                side_effect=has_material,
            ),
        ):
            numerator, denominator, ungrouped = financial_aggregate_projection.ratio_rebuild_component_seeds(
                row,
                calculation_result,
                answer_slots,
            )

        self.assertEqual(
            normalized_roles,
            [" numerator_1 ", "fallback-den", "other", "empty", "denominator_1"],
        )
        self.assertEqual(
            group_roles,
            ["numerator_1", "fallback-den", "other", "empty", "denominator_1"],
        )
        self.assertEqual([item.get("label") for item in numerator], ["numerator"])
        self.assertEqual(
            [item.get("label") for item in denominator],
            ["denominator", "row denominator"],
        )
        self.assertEqual(
            ungrouped,
            [
                {
                    **material_unknown_seed,
                    "matched_operand_role": "other",
                }
            ],
        )
        self.assertEqual(
            [item.get("role") for item in material_rows],
            ["other", "empty"],
        )
        self.assertIsNot(numerator[0], numerator_seed)
        self.assertIsNot(denominator[0], fallback_denominator_seed)
        self.assertIsNot(denominator[1], row_denominator_seed)
        self.assertIsNot(ungrouped[0], material_unknown_seed)
        for item in [numerator[0], denominator[0], denominator[1], ungrouped[0]]:
            self.assertIs(item["nested"], nested)
        self.assertEqual(fallback_denominator_seed, {"label": "denominator", "nested": nested})
        self.assertEqual(answer_slots, before["answer_slots"])
        self.assertEqual(row, before["row"])
        self.assertEqual(dict(calculation_result), before["calculation_result"])

        downstream_group = Mock(side_effect=AssertionError("group accessed"))
        downstream_material = Mock(side_effect=AssertionError("material accessed"))
        with (
            patch.object(
                financial_aggregate_projection,
                "_normalise_spaces",
                side_effect=RuntimeError("role normalization failed"),
            ),
            patch.object(
                financial_aggregate_projection,
                "dependency_ratio_role_group",
                downstream_group,
            ),
            patch.object(
                financial_aggregate_projection,
                "answer_slot_has_material",
                downstream_material,
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "role normalization failed"):
                financial_aggregate_projection.ratio_rebuild_component_seeds(
                    {},
                    {},
                    {"components_by_group": {"unknown": [{"role": "other"}]}},
                )
        downstream_group.assert_not_called()
        downstream_material.assert_not_called()

        fallback_operand = {"role": "numerator_1", "label": "fallback operand", "nested": nested}
        with (
            patch.object(financial_aggregate_projection, "_normalise_spaces", side_effect=normalize),
            patch.object(
                financial_aggregate_projection,
                "dependency_ratio_role_group",
                side_effect=ratio_group,
            ),
            patch.object(financial_aggregate_projection, "answer_slot_has_material", side_effect=has_material),
        ):
            fallback_numerator, fallback_denominator, fallback_ungrouped = (
                financial_aggregate_projection.ratio_rebuild_component_seeds(
                    {"calculation_operands": []},
                    {"calculation_operands": [fallback_operand]},
                    {},
                )
            )
        self.assertEqual([item.get("label") for item in fallback_numerator], ["fallback operand"])
        self.assertEqual(fallback_denominator, [])
        self.assertEqual(fallback_ungrouped, [])
        self.assertIsNot(fallback_numerator[0], fallback_operand)
        self.assertIs(fallback_numerator[0]["nested"], nested)

        downstream_material = Mock(side_effect=AssertionError("material accessed"))
        with (
            patch.object(financial_aggregate_projection, "_normalise_spaces", return_value="other"),
            patch.object(
                financial_aggregate_projection,
                "dependency_ratio_role_group",
                side_effect=RuntimeError("group failed"),
            ),
            patch.object(
                financial_aggregate_projection,
                "answer_slot_has_material",
                downstream_material,
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "group failed"):
                financial_aggregate_projection.ratio_rebuild_component_seeds(
                    {},
                    {},
                    {"components_by_group": {"unknown": [{"role": "other"}]}},
                )
        downstream_material.assert_not_called()

        with (
            patch.object(financial_aggregate_projection, "_normalise_spaces", return_value="other"),
            patch.object(financial_aggregate_projection, "dependency_ratio_role_group", return_value=""),
            patch.object(
                financial_aggregate_projection,
                "answer_slot_has_material",
                side_effect=RuntimeError("material gate failed"),
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "material gate failed"):
                financial_aggregate_projection.ratio_rebuild_component_seeds(
                    {},
                    {},
                    {"components_by_group": {"unknown": [{"role": "other"}]}},
                )

    def test_current_source_dependency_source_scores_pin_normalization_fallbacks_and_exceptions(self) -> None:
        events = []

        def normalize(value):
            events.append(("normalize", value))
            return " ".join(str(value).split())

        def terms(value):
            events.append(("terms", value))
            if value == "Metric Alpha":
                return ["Metric", "Alpha", "x"]
            return ["metric", "alpha", "extra"]

        with (
            patch.object(financial_aggregate_projection, "_normalise_spaces", side_effect=normalize),
            patch.object(financial_aggregate_projection, "narrative_context_terms", side_effect=terms),
        ):
            self.assertEqual(
                financial_aggregate_projection._dependency_source_text_match_score(
                    " Metric Alpha ",
                    "Metric Alpha Extended",
                ),
                5,
            )
        self.assertEqual(
            events,
            [
                ("normalize", " Metric Alpha "),
                ("normalize", "Metric Alpha Extended"),
                ("terms", "Metric Alpha"),
                ("terms", "Metric Alpha Extended"),
            ],
        )

        term_owner = Mock(side_effect=AssertionError("terms accessed"))
        with (
            patch.object(
                financial_aggregate_projection,
                "_normalise_spaces",
                side_effect=("", "right"),
            ) as normalizer,
            patch.object(financial_aggregate_projection, "narrative_context_terms", term_owner),
        ):
            self.assertEqual(
                financial_aggregate_projection._dependency_source_text_match_score("left", "right"),
                0,
            )
        self.assertEqual([call.args for call in normalizer.call_args_list], [("left",), ("right",)])
        term_owner.assert_not_called()

        with (
            patch.object(financial_aggregate_projection, "_normalise_spaces", side_effect=lambda value: value),
            patch.object(
                financial_aggregate_projection,
                "narrative_context_terms",
                side_effect=(["Shared"], ["shared"]),
            ),
        ):
            self.assertEqual(
                financial_aggregate_projection._dependency_source_text_match_score("same", "same"),
                7,
            )

        with (
            patch.object(financial_aggregate_projection, "_normalise_spaces", side_effect=lambda value: value),
            patch.object(
                financial_aggregate_projection,
                "narrative_context_terms",
                side_effect=(["Alpha", "One"], ["alpha", "Two"]),
            ),
        ):
            self.assertEqual(
                financial_aggregate_projection._dependency_source_text_match_score(
                    "Alpha One", "Two Alpha"
                ),
                1,
            )

        second_terms = Mock(side_effect=AssertionError("second terms accessed"))

        def failing_terms(value):
            if value == "left":
                raise RuntimeError("term scoring failed")
            return second_terms(value)

        with (
            patch.object(financial_aggregate_projection, "_normalise_spaces", side_effect=lambda value: value),
            patch.object(financial_aggregate_projection, "narrative_context_terms", side_effect=failing_terms),
        ):
            with self.assertRaisesRegex(RuntimeError, "term scoring failed"):
                financial_aggregate_projection._dependency_source_text_match_score("left", "right")
        second_terms.assert_not_called()

        slot_events = []

        class RecordingRow(dict):
            def __init__(self, name, values):
                super().__init__(values)
                self.name = name

            def get(self, key, default=None):
                slot_events.append((self.name, key))
                return super().get(key, default)

        slot = RecordingRow(
            "slot",
            {
                "label": "Slot",
                "metric_label": "Metric",
                "concept": "Concept",
                "period": "2024",
            },
        )
        seed = RecordingRow(
            "seed",
            {
                "label": "",
                "matched_operand_label": "Matched",
                "concept": "Concept2",
                "period": "",
                "matched_operand_period": "Prior",
            },
        )
        base_score = Mock(return_value=10)
        text_score = Mock(return_value=4)
        with (
            patch.object(
                financial_aggregate_projection,
                "dependency_lookup_slot_match_score",
                base_score,
            ),
            patch.object(
                financial_aggregate_projection,
                "_dependency_source_text_match_score",
                text_score,
            ),
        ):
            self.assertEqual(
                financial_aggregate_projection.dependency_source_slot_match_score(
                    slot, seed, "denominator_1"
                ),
                14,
            )
        base_score.assert_called_once_with(slot, seed, "denominator_1")
        text_score.assert_called_once_with(
            "Slot Metric Concept 2024",
            "Matched Concept2 Prior",
        )
        self.assertEqual(
            slot_events,
            [
                ("slot", "label"),
                ("slot", "metric_label"),
                ("slot", "concept"),
                ("slot", "period"),
                ("seed", "label"),
                ("seed", "matched_operand_label"),
                ("seed", "concept"),
                ("seed", "period"),
                ("seed", "matched_operand_period"),
            ],
        )

        untouched_slot = RecordingRow("untouched-slot", {"label": "unused"})
        untouched_seed = RecordingRow("untouched-seed", {"label": "unused"})
        text_score = Mock(side_effect=AssertionError("text score accessed"))
        with (
            patch.object(
                financial_aggregate_projection,
                "dependency_lookup_slot_match_score",
                side_effect=RuntimeError("base score failed"),
            ),
            patch.object(
                financial_aggregate_projection,
                "_dependency_source_text_match_score",
                text_score,
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "base score failed"):
                financial_aggregate_projection.dependency_source_slot_match_score(
                    untouched_slot,
                    untouched_seed,
                    "numerator_1",
                )
        text_score.assert_not_called()
        self.assertNotIn(("untouched-slot", "label"), slot_events)

        with (
            patch.object(
                financial_aggregate_projection,
                "dependency_lookup_slot_match_score",
                return_value=1,
            ),
            patch.object(
                financial_aggregate_projection,
                "_dependency_source_text_match_score",
                side_effect=RuntimeError("text score failed"),
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "text score failed"):
                financial_aggregate_projection.dependency_source_slot_match_score(
                    {}, {}, "numerator_1"
                )

    def test_current_source_best_dependency_source_pins_inference_exclusion_tie_copy_and_exceptions(self) -> None:
        nested = {"preserve": True}
        seed = {
            "label": " Base Label ",
            "concept": " Base Concept ",
            "nested": nested,
        }
        source_slots = {
            "task-inferred": {"label": "inferred", "nested": nested},
            "task-a": {"label": "a", "nested": nested},
            "task-z": {"label": "z", "nested": nested},
            "task-excluded": {"label": "excluded", "nested": nested},
            "task-zero": {"label": "zero", "nested": nested},
        }
        before_seed = deepcopy(seed)
        before_slots = deepcopy(source_slots)
        prepared_seen = []
        inference = Mock(side_effect=lambda prepared, slots: prepared_seen.append((prepared, slots)) or ["task-inferred"])
        scores = {
            "task-inferred": 1,
            "task-a": 12,
            "task-z": 12,
            "task-zero": 0,
        }
        score_calls = []

        def match_score(slot, prepared, role):
            task_id = next(task_id for task_id, candidate in source_slots.items() if candidate is slot)
            score_calls.append((task_id, prepared, role))
            return scores[task_id]

        with (
            patch.object(
                financial_aggregate_projection,
                "aggregate_source_task_ids_for_operand",
                inference,
            ),
            patch.object(
                financial_aggregate_projection,
                "dependency_source_slot_match_score",
                side_effect=match_score,
            ),
        ):
            task_id, selected_slot, prepared_seed, score = financial_aggregate_projection.best_dependency_source_for_seed(
                seed,
                "denominator_1",
                source_slots=source_slots,
                excluded_task_ids={"task-excluded"},
            )

        self.assertEqual((task_id, score), ("task-z", 12))
        self.assertEqual(selected_slot, source_slots["task-z"])
        self.assertIsNot(selected_slot, source_slots["task-z"])
        self.assertIs(selected_slot["nested"], nested)
        self.assertIsNot(prepared_seed, seed)
        self.assertIs(prepared_seed["nested"], nested)
        self.assertEqual(prepared_seed["role"], "denominator_1")
        self.assertEqual(prepared_seed["matched_operand_role"], "denominator_1")
        self.assertEqual(prepared_seed["matched_operand_label"], "Base Label")
        self.assertEqual(prepared_seed["matched_operand_concept"], "Base Concept")
        self.assertEqual(prepared_seen, [(prepared_seed, source_slots)])
        self.assertTrue(all(call[1] is prepared_seed for call in score_calls))
        self.assertEqual(
            [call[0] for call in score_calls],
            ["task-inferred", "task-a", "task-z", "task-zero"],
        )
        self.assertNotIn("task-excluded", [call[0] for call in score_calls])
        self.assertEqual(seed, before_seed)
        self.assertEqual(source_slots, before_slots)

        with (
            patch.object(
                financial_aggregate_projection,
                "aggregate_source_task_ids_for_operand",
                return_value=["only-inferred"],
            ),
            patch.object(
                financial_aggregate_projection,
                "dependency_source_slot_match_score",
                return_value=1,
            ),
        ):
            inferred_task_id, inferred_slot, _inferred_seed, inferred_score = (
                financial_aggregate_projection.best_dependency_source_for_seed(
                    {"label": "seed"},
                    "numerator_1",
                    source_slots={"only-inferred": {"label": "source"}},
                )
            )
        self.assertEqual((inferred_task_id, inferred_slot, inferred_score), (
            "only-inferred",
            {"label": "source"},
            12,
        ))

        with (
            patch.object(
                financial_aggregate_projection,
                "aggregate_source_task_ids_for_operand",
                return_value=[],
            ),
            patch.object(
                financial_aggregate_projection,
                "dependency_source_slot_match_score",
                return_value=0,
            ),
        ):
            self.assertEqual(
                financial_aggregate_projection.best_dependency_source_for_seed(
                    {},
                    "numerator_1",
                    source_slots={"task": {"label": "none"}},
                ),
                ("", {}, {}, 0),
            )

        downstream_score = Mock(side_effect=AssertionError("slot score accessed"))
        with (
            patch.object(
                financial_aggregate_projection,
                "aggregate_source_task_ids_for_operand",
                side_effect=RuntimeError("source inference failed"),
            ),
            patch.object(
                financial_aggregate_projection,
                "dependency_source_slot_match_score",
                downstream_score,
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "source inference failed"):
                financial_aggregate_projection.best_dependency_source_for_seed(
                    seed,
                    "numerator_1",
                    source_slots=source_slots,
                )
        downstream_score.assert_not_called()

        calls = []

        def failing_score(slot, _prepared, _role):
            calls.append(slot)
            raise RuntimeError("slot score failed")

        with (
            patch.object(
                financial_aggregate_projection,
                "aggregate_source_task_ids_for_operand",
                return_value=[],
            ),
            patch.object(
                financial_aggregate_projection,
                "dependency_source_slot_match_score",
                side_effect=failing_score,
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "slot score failed"):
                financial_aggregate_projection.best_dependency_source_for_seed(
                    seed,
                    "numerator_1",
                    source_slots={"first": source_slots["task-a"], "second": source_slots["task-z"]},
                )
        self.assertEqual(calls, [source_slots["task-a"]])

    def test_current_source_component_slot_pins_dependency_args_adoption_copy_and_exceptions(self) -> None:
        nested = {"preserve": True}
        seed = {
            "label": "Seed Label",
            "matched_operand_label": "Matched Label",
            "concept": "Seed Concept",
            "nested": nested,
        }
        source_slot = {
            "label": "Source Label",
            "concept": "Source Concept",
            "nested": nested,
        }
        before_seed = deepcopy(seed)
        before_source = deepcopy(source_slot)
        source_operand = {"normalized_value": 25.0, "nested": nested}
        built_slot = {"normalized_value": 25.0, "nested": nested}
        dependency_builder = Mock(return_value=source_operand)
        slot_builder = Mock(return_value=built_slot)
        with (
            patch.object(
                financial_aggregate_projection,
                "dependency_operand_from_source_slot",
                dependency_builder,
            ),
            patch.object(
                financial_aggregate_projection,
                "build_operand_value_slot",
                slot_builder,
            ),
        ):
            result = financial_aggregate_projection.component_slot_from_dependency_source(
                seed,
                source_slot,
                "task-source",
                "numerator_1",
            )

        dependency_builder.assert_called_once()
        prepared_operand, passed_source = dependency_builder.call_args.args
        self.assertIs(passed_source, source_slot)
        self.assertEqual(dependency_builder.call_args.kwargs, {"source_task_id": "task-source"})
        self.assertIsNot(prepared_operand, seed)
        self.assertIs(prepared_operand["nested"], nested)
        self.assertEqual(
            {
                key: prepared_operand.get(key)
                for key in (
                    "role",
                    "matched_operand_role",
                    "label",
                    "matched_operand_label",
                    "matched_operand_concept",
                )
            },
            {
                "role": "numerator_1",
                "matched_operand_role": "numerator_1",
                "label": "Seed Label",
                "matched_operand_label": "Matched Label",
                "matched_operand_concept": "Source Concept",
            },
        )
        slot_builder.assert_called_once_with(source_operand, default_role="numerator_1")
        self.assertIs(result, built_slot)
        self.assertEqual(result["role"], "numerator_1")
        self.assertEqual(result["source_task_id"], "task-source")
        self.assertIs(result["dependency_resolved"], True)
        self.assertIs(result["nested"], nested)
        self.assertEqual(seed, before_seed)
        self.assertEqual(source_slot, before_source)

        fallback_seed = {"nested": nested}
        fallback_source = {"label": "Source Label", "concept": "Source Concept", "nested": nested}
        dependency_builder = Mock(return_value=source_operand)
        with (
            patch.object(
                financial_aggregate_projection,
                "dependency_operand_from_source_slot",
                dependency_builder,
            ),
            patch.object(
                financial_aggregate_projection,
                "build_operand_value_slot",
                return_value={},
            ),
        ):
            financial_aggregate_projection.component_slot_from_dependency_source(
                fallback_seed,
                fallback_source,
                "task-fallback",
                "denominator_1",
            )
        fallback_prepared = dependency_builder.call_args.args[0]
        self.assertEqual(fallback_prepared["label"], "Source Label")
        self.assertEqual(fallback_prepared["matched_operand_label"], "Source Label")
        self.assertEqual(fallback_prepared["matched_operand_concept"], "Source Concept")

        downstream_slot = Mock(side_effect=AssertionError("slot builder accessed"))
        with (
            patch.object(
                financial_aggregate_projection,
                "dependency_operand_from_source_slot",
                side_effect=RuntimeError("dependency operand failed"),
            ),
            patch.object(
                financial_aggregate_projection,
                "build_operand_value_slot",
                downstream_slot,
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "dependency operand failed"):
                financial_aggregate_projection.component_slot_from_dependency_source(
                    seed,
                    source_slot,
                    "task-source",
                    "numerator_1",
                )
        downstream_slot.assert_not_called()

        with (
            patch.object(
                financial_aggregate_projection,
                "dependency_operand_from_source_slot",
                return_value=source_operand,
            ),
            patch.object(
                financial_aggregate_projection,
                "build_operand_value_slot",
                side_effect=RuntimeError("slot build failed"),
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "slot build failed"):
                financial_aggregate_projection.component_slot_from_dependency_source(
                    seed,
                    source_slot,
                    "task-source",
                    "numerator_1",
                )

    def test_current_source_dependency_source_bindings_pin_defs_calls_plan_dag_and_baseline(self) -> None:
        import json
        from pathlib import Path

        module_sources = {
            "graph": inspect.getsource(financial_graph_calculation),
            "owner": inspect.getsource(financial_aggregate_projection),
        }
        module_trees = {name: ast.parse(source) for name, source in module_sources.items()}
        current_targets = {
            "seeds": "ratio_rebuild_component_seeds",
            "text": "_dependency_source_text_match_score",
            "slot": "dependency_source_slot_match_score",
            "best": "best_dependency_source_for_seed",
            "component": "component_slot_from_dependency_source",
        }
        public_targets = {
            "seeds": "ratio_rebuild_component_seeds",
            "slot": "dependency_source_slot_match_score",
            "best": "best_dependency_source_for_seed",
            "component": "component_slot_from_dependency_source",
        }
        definitions = {}
        public_definitions = set()
        calls = {key: [] for key in current_targets}
        try_depths = {key: [] for key in current_targets}

        class BindingVisitor(ast.NodeVisitor):
            def __init__(self, module_name):
                self.module_name = module_name
                self.function_stack = []
                self.try_depth = 0

            def visit_FunctionDef(self, node):
                if node.name in current_targets.values():
                    definitions[node.name] = (self.module_name, node)
                if node.name in public_targets.values():
                    public_definitions.add((self.module_name, node.name))
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
                receiver = (
                    ast.unparse(node.func.value)
                    if isinstance(node.func, ast.Attribute)
                    else ""
                )
                for key, target in current_targets.items():
                    if called_name != target:
                        continue
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
                name: (module_name, node.end_lineno - node.lineno + 1)
                for name, (module_name, node) in definitions.items()
            },
            {
                "ratio_rebuild_component_seeds": ("owner", 33),
                "_dependency_source_text_match_score": ("owner", 21),
                "dependency_source_slot_match_score": ("owner", 15),
                "best_dependency_source_for_seed": ("owner", 35),
                "component_slot_from_dependency_source": ("owner", 23),
            },
        )
        self.assertEqual(
            public_definitions,
            {
                ("owner", "ratio_rebuild_component_seeds"),
                ("owner", "dependency_source_slot_match_score"),
                ("owner", "best_dependency_source_for_seed"),
                ("owner", "component_slot_from_dependency_source"),
            },
        )
        self.assertEqual(
            {key: len(entries) for key, entries in calls.items()},
            {"seeds": 1, "text": 1, "slot": 2, "best": 3, "component": 2},
        )
        self.assertEqual(
            try_depths,
            {"seeds": [0], "text": [0], "slot": [0, 0], "best": [0, 0, 0], "component": [0, 0]},
        )
        self.assertTrue(
            all(
                receiver == ""
                for entries in calls.values()
                for _module, _stack, receiver, _args, _keywords in entries
            )
        )
        self.assertEqual(
            calls["seeds"][0][3:],
            (("row", "calculation_result", "answer_slots"), ()),
        )
        self.assertEqual(
            calls["text"][0][3:],
            (("slot_text", "seed_text"), ()),
        )
        self.assertEqual(
            [(entry[3], entry[4]) for entry in calls["component"]],
            [
                (("numerator_seed", "numerator_source", "numerator_task_id", "'numerator_1'"), ()),
                (("denominator_seed", "denominator_source", "denominator_task_id", "'denominator_1'"), ()),
            ],
        )
        self.assertEqual(
            [(entry[3], entry[4]) for entry in calls["slot"]],
            [
                (("denominator_source", "metric_seed", "'denominator_1'"), ()),
                (("slot", "seed", "role"), ()),
            ],
        )
        self.assertEqual(
            [(entry[3], entry[4]) for entry in calls["best"]],
            [
                (("numerator_seed", "'numerator_1'"), (("source_slots", "source_slots"),)),
                (
                    ("denominator_seed", "'denominator_1'"),
                    (
                        ("source_slots", "source_slots"),
                        ("excluded_task_ids", "{numerator_task_id}"),
                    ),
                ),
                (
                    ("metric_seed", "'denominator_1'"),
                    (
                        ("source_slots", "source_slots"),
                        ("excluded_task_ids", "{numerator_task_id}"),
                    ),
                ),
            ],
        )

        selected_definition_names = set(current_targets.values())
        planned = {}
        external = 0
        local = 0
        for key, entries in calls.items():
            graph_count = 0
            owner_count = 0
            for module_name, function_stack, _receiver, _args, _keywords in entries:
                planned_module = module_name
                if selected_definition_names.intersection(function_stack):
                    planned_module = "owner"
                if planned_module == "owner":
                    owner_count += 1
                else:
                    graph_count += 1
            planned[key] = (graph_count, owner_count)
            external += graph_count
            local += owner_count
        self.assertEqual(
            planned,
            {
                "seeds": (1, 0),
                "text": (0, 1),
                "slot": (1, 1),
                "best": (3, 0),
                "component": (2, 0),
            },
        )
        self.assertEqual((external, local), (7, 2))

        graph_bindings = {
            alias.name
            for node in module_trees["graph"].body
            if isinstance(node, ast.ImportFrom)
            and node.module == "src.agent.financial_aggregate_projection"
            for alias in node.names
            if alias.name in public_targets.values()
        }
        self.assertEqual(graph_bindings, set(public_targets.values()))

        def imported_modules(tree):
            modules = set()
            for node in tree.body:
                if isinstance(node, ast.ImportFrom) and node.module:
                    modules.add(node.module)
                elif isinstance(node, ast.Import):
                    modules.update(alias.name for alias in node.names)
            return modules

        owner_imports = imported_modules(module_trees["owner"])
        self.assertTrue(
            {
                "src.agent.financial_answer_slots",
                "src.agent.financial_dependency_projection",
                "src.agent.financial_runtime_normalization",
                "src.agent.financial_text_surface",
            }.issubset(owner_imports)
        )
        for path in (
            "src/agent/financial_answer_slots.py",
            "src/agent/financial_dependency_projection.py",
            "src/agent/financial_text_surface.py",
        ):
            tree = ast.parse(Path(path).read_text(encoding="utf-8"))
            self.assertNotIn("src.agent.financial_aggregate_projection", imported_modules(tree))

        baseline = json.loads(
            (Path(__file__).parent / "fixtures" / "runtime_domain_terms_baseline.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(len(baseline["records"]), 217)
        owner_nodes = [node for module_name, node in definitions.values() if module_name == "owner"]
        selected_start = min(node.lineno for node in owner_nodes)
        selected_end = max(node.end_lineno for node in owner_nodes)
        self.assertEqual(
            [
                record
                for record in baseline["records"]
                if record.get("path") == "src/agent/financial_aggregate_projection.py"
                and any(
                    selected_start <= line <= selected_end
                    for line in record.get("first_lines") or []
                )
            ],
            [],
        )

    def test_current_source_ratio_source_caller_pins_args_order_adoption_laziness_and_stop(self) -> None:
        from types import SimpleNamespace

        nested = {"preserve": True}
        numerator_input = {"label": "numerator source", "nested": nested}
        denominator_input = {"label": "denominator source", "nested": nested}
        source_slot_by_task_id = {
            "task-num": numerator_input,
            "task-den": denominator_input,
        }
        row = {
            "calculation_result": {
                "answer_slots": {"metric_label": "Margin", "nested": nested},
                "calculation_operands": [],
                "nested": nested,
            },
            "nested": nested,
        }
        before_row = deepcopy(row)
        before_sources = deepcopy(source_slot_by_task_id)
        numerator_seed = {"label": "Num Seed", "nested": nested}
        denominator_seed = {"label": "Den Seed", "nested": nested}
        metric_seed = {"role": "denominator_1", "label": "Margin"}
        numerator_source = {"label": "numerator source", "nested": nested}
        denominator_source = {"label": "denominator source", "nested": nested}
        metric_source = {"label": "metric source", "nested": nested}
        prepared_metric_seed = {"role": "denominator_1", "label": "prepared metric"}
        numerator_slot = {
            "normalized_value": 25.0,
            "source_row_id": "row-num",
            "nested": nested,
        }
        denominator_slot = {
            "normalized_value": 100.0,
            "source_row_id": "row-den",
            "nested": nested,
        }
        events = []
        copied_sources = []

        def material(slot):
            events.append(("material", slot))
            copied_sources.append(slot)
            return True

        seed_owner = Mock(
            side_effect=lambda prepared_row, result, slots: events.append(
                ("seeds", prepared_row, result, slots)
            )
            or ([numerator_seed], [denominator_seed], [])
        )

        def best_owner(seed, role, **kwargs):
            events.append(("best", seed, role, kwargs))
            best_calls = [event for event in events if event[0] == "best"]
            if len(best_calls) == 1:
                return "task-num", numerator_source, numerator_seed, 10
            if len(best_calls) == 2:
                return "task-den", denominator_source, denominator_seed, 8
            return "task-metric", metric_source, prepared_metric_seed, 3

        slot_score = Mock(
            side_effect=lambda slot, seed, role: events.append(
                ("slot-score", slot, seed, role)
            )
            or 0
        )

        def component_owner(seed, source, task_id, role):
            events.append(("component", seed, source, task_id, role))
            return numerator_slot if role == "numerator_1" else denominator_slot

        compact_owner = Mock(
            side_effect=lambda state, result: events.append(("compact", state, result))
            or "25.0%"
        )
        with (
            patch.object(financial_graph_calculation, "answer_slot_has_material", side_effect=material),
            patch.object(financial_graph_calculation, "ratio_rebuild_component_seeds", seed_owner),
            patch.object(
                financial_graph_calculation,
                "best_dependency_source_for_seed",
                side_effect=best_owner,
            ),
            patch.object(
                financial_graph_calculation,
                "dependency_source_slot_match_score",
                slot_score,
            ),
            patch.object(
                financial_graph_calculation,
                "component_slot_from_dependency_source",
                side_effect=component_owner,
            ),
            patch.object(
                financial_graph_calculation,
                "_ratio_operand_rows_collapse_to_same_slot",
                return_value=False,
            ) as collapse_gate,
            patch.object(
                financial_graph_calculation.financial_answer_slots,
                "coerce_slot_numeric",
                side_effect=lambda value: value,
            ) as numeric_owner,
            patch.object(
                financial_graph_calculation.calculation_rendering,
                "ratio_result_projection",
                return_value={
                    "result_value": 25.0,
                    "result_unit": "%",
                    "normalized_unit": "ratio",
                    "rendered_value": "25.0%",
                },
            ) as ratio_projection,
            patch.object(
                financial_graph_calculation,
                "_clean_source_row_ids",
                return_value=["row-num", "row-den"],
            ) as source_id_owner,
            patch.object(
                financial_graph_calculation,
                "build_dependency_ratio_result_projection",
                return_value=SimpleNamespace(
                    calculation_result={
                        "status": "ok",
                        "result_value": 25.0,
                        "rendered_value": "25.0%",
                    }
                ),
            ) as result_builder,
            patch.object(self.agent, "_compact_ratio_answer", compact_owner),
        ):
            answer = self.agent._ratio_answer_from_dependency_source_slots(
                row,
                source_slot_by_task_id,
                query="ratio query",
            )

        self.assertEqual(answer, "25.0%")
        self.assertEqual([event[0] for event in events], [
            "material",
            "material",
            "seeds",
            "best",
            "best",
            "best",
            "slot-score",
            "component",
            "component",
            "compact",
        ])
        self.assertEqual(len(copied_sources), 2)
        self.assertIsNot(copied_sources[0], numerator_input)
        self.assertIsNot(copied_sources[1], denominator_input)
        self.assertIs(copied_sources[0]["nested"], nested)
        self.assertIs(copied_sources[1]["nested"], nested)
        seed_args = seed_owner.call_args.args
        self.assertIs(seed_args[0], row)
        self.assertIsNot(seed_args[1], row["calculation_result"])
        self.assertEqual(seed_args[1], row["calculation_result"])
        self.assertIsNot(seed_args[2], row["calculation_result"]["answer_slots"])
        self.assertEqual(seed_args[2], row["calculation_result"]["answer_slots"])
        best_calls = [event for event in events if event[0] == "best"]
        self.assertIs(best_calls[0][1], numerator_seed)
        self.assertEqual(best_calls[0][2], "numerator_1")
        first_source_slots = best_calls[0][3]["source_slots"]
        self.assertEqual(set(first_source_slots), {"task-num", "task-den"})
        self.assertIsNot(first_source_slots["task-num"], numerator_input)
        self.assertIsNot(first_source_slots["task-den"], denominator_input)
        self.assertIsNot(first_source_slots["task-num"], copied_sources[0])
        self.assertIsNot(first_source_slots["task-den"], copied_sources[1])
        self.assertIs(first_source_slots["task-num"]["nested"], nested)
        self.assertIs(first_source_slots["task-den"]["nested"], nested)
        self.assertIs(best_calls[1][1], denominator_seed)
        self.assertEqual(
            best_calls[1][2:],
            (
                "denominator_1",
                {"source_slots": first_source_slots, "excluded_task_ids": {"task-num"}},
            ),
        )
        self.assertEqual(best_calls[2][1], metric_seed)
        self.assertEqual(
            best_calls[2][2:],
            (
                "denominator_1",
                {"source_slots": first_source_slots, "excluded_task_ids": {"task-num"}},
            ),
        )
        slot_score.assert_called_once_with(denominator_source, metric_seed, "denominator_1")
        component_calls = [event for event in events if event[0] == "component"]
        self.assertEqual(
            component_calls,
            [
                (
                    "component",
                    numerator_seed,
                    numerator_source,
                    "task-num",
                    "numerator_1",
                ),
                (
                    "component",
                    prepared_metric_seed,
                    metric_source,
                    "task-metric",
                    "denominator_1",
                ),
            ],
        )
        collapse_gate.assert_called_once_with([numerator_slot, denominator_slot])
        self.assertEqual(
            [call.args for call in numeric_owner.call_args_list],
            [(25.0,), (100.0,)],
        )
        ratio_projection.assert_called_once_with(
            numerator_value=25.0,
            denominator_value=100.0,
            query="ratio query",
            metric_label="Margin",
        )
        source_id_owner.assert_called_once()
        result_builder.assert_called_once()
        compact_owner.assert_called_once()
        self.assertEqual(row, before_row)
        self.assertEqual(source_slot_by_task_id, before_sources)
        self.assertIs(row["nested"], nested)
        self.assertIs(source_slot_by_task_id["task-num"]["nested"], nested)

        class RowBomb(dict):
            def get(self, _key, _default=None):
                raise AssertionError("row accessed")

        seed_owner = Mock(side_effect=AssertionError("seed owner accessed"))
        with (
            patch.object(financial_graph_calculation, "answer_slot_has_material", return_value=True),
            patch.object(financial_graph_calculation, "ratio_rebuild_component_seeds", seed_owner),
        ):
            self.assertEqual(
                self.agent._ratio_answer_from_dependency_source_slots(
                    RowBomb(),
                    {"only": {"normalized_value": 1.0}},
                ),
                "",
            )
        seed_owner.assert_not_called()

        downstream_best = Mock(side_effect=AssertionError("best owner accessed"))
        downstream_component = Mock(side_effect=AssertionError("component owner accessed"))
        with (
            patch.object(financial_graph_calculation, "answer_slot_has_material", return_value=True),
            patch.object(
                financial_graph_calculation,
                "ratio_rebuild_component_seeds",
                side_effect=RuntimeError("seed owner failed"),
            ),
            patch.object(
                financial_graph_calculation,
                "best_dependency_source_for_seed",
                downstream_best,
            ),
            patch.object(
                financial_graph_calculation,
                "component_slot_from_dependency_source",
                downstream_component,
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "seed owner failed"):
                self.agent._ratio_answer_from_dependency_source_slots(
                    row,
                    source_slot_by_task_id,
                )
        downstream_best.assert_not_called()
        downstream_component.assert_not_called()
        self.assertEqual(row, before_row)
        self.assertEqual(source_slot_by_task_id, before_sources)

    def test_current_source_narrative_row_focus_sentence_pins_filters_order_and_exceptions(self) -> None:
        nested = {"preserve": True}
        skipped_row = {
            "metric_family": "lookup",
            "answer": "unused",
            "nested": nested,
        }
        narrative_row = {
            "metric_family": " Narrative_Summary ",
            "selected_claim_ids": [" claim_1 ", "", 7],
            "answer": "prepared narrative",
            "nested": nested,
        }
        later_row = {
            "metric_family": "narrative_summary",
            "selected_claim_ids": ["later"],
            "answer": "later narrative",
        }
        ordered_results = [skipped_row, narrative_row, later_row]
        before = deepcopy(ordered_results)
        events = []

        def operation_family(row):
            events.append(("family", row))
            return "lookup"

        def normalize(value):
            events.append(("normalize", value))
            return " ".join(str(value).split())

        def split_sentences(value):
            events.append(("split", value))
            if value == "prepared narrative":
                return [" noisy row ", " fragment row ", " Focus WIN ", "Focus later"]
            return ["Focus unused"]

        def noisy(value):
            events.append(("noisy", value))
            return value == "noisy row"

        def fragment(value, markers):
            events.append(("fragment", value, markers))
            return value == "fragment row"

        policy = {"growth_narrative_markers": ("impact",), "nested": nested}
        with (
            patch.object(financial_aggregate_projection, "CALCULATION_NARRATIVE_POLICY", policy),
            patch.object(financial_aggregate_projection, "aggregate_result_operation_family", side_effect=operation_family),
            patch.object(financial_aggregate_projection, "_normalise_spaces", side_effect=normalize),
            patch.object(financial_aggregate_projection, "_split_narrative_sentences", side_effect=split_sentences),
            patch.object(financial_aggregate_projection, "narrative_sentence_looks_table_noisy", side_effect=noisy),
            patch.object(
                financial_aggregate_projection,
                "narrative_sentence_looks_abbreviated_fragment",
                side_effect=fragment,
            ),
        ):
            selected = financial_aggregate_projection.narrative_row_focus_sentence(
                ordered_results=ordered_results,
                focus_variants=["focus"],
            )

        self.assertEqual(selected, (0, "Focus WIN", ["claim_1", "7"]))
        self.assertEqual([event[0] for event in events], [
            "family",
            "normalize",
            "family",
            "normalize",
            "split",
            "normalize",
            "noisy",
            "normalize",
            "noisy",
            "fragment",
            "normalize",
            "noisy",
            "fragment",
        ])
        self.assertEqual(ordered_results, before)
        self.assertIs(ordered_results[0]["nested"], nested)
        self.assertIs(ordered_results[1]["nested"], nested)
        self.assertEqual(policy, {"growth_narrative_markers": ("impact",), "nested": nested})
        self.assertTrue(
            all(event[2] == ("impact",) for event in events if event[0] == "fragment")
        )

        class ResultsBomb:
            def __iter__(self):
                raise AssertionError("rows accessed")

        with self.assertRaisesRegex(AssertionError, "rows accessed"):
            list(ResultsBomb())
        self.assertIsNone(
            financial_aggregate_projection.narrative_row_focus_sentence(
                ordered_results=ResultsBomb(),
                focus_variants=[],
            )
        )

        split_owner = Mock(side_effect=AssertionError("split accessed"))
        with (
            patch.object(
                financial_aggregate_projection,
                "aggregate_result_operation_family",
                side_effect=RuntimeError("family failed"),
            ),
            patch.object(financial_aggregate_projection, "_split_narrative_sentences", split_owner),
        ):
            with self.assertRaisesRegex(RuntimeError, "family failed"):
                financial_aggregate_projection.narrative_row_focus_sentence(
                    ordered_results=[narrative_row],
                    focus_variants=["focus"],
                )
        split_owner.assert_not_called()

        noisy_owner = Mock(side_effect=AssertionError("noise accessed"))
        with (
            patch.object(financial_aggregate_projection, "aggregate_result_operation_family", return_value="narrative_summary"),
            patch.object(financial_aggregate_projection, "_normalise_spaces", side_effect=normalize),
            patch.object(
                financial_aggregate_projection,
                "_split_narrative_sentences",
                side_effect=RuntimeError("split failed"),
            ),
            patch.object(financial_aggregate_projection, "narrative_sentence_looks_table_noisy", noisy_owner),
        ):
            with self.assertRaisesRegex(RuntimeError, "split failed"):
                financial_aggregate_projection.narrative_row_focus_sentence(
                    ordered_results=[narrative_row],
                    focus_variants=["focus"],
                )
        noisy_owner.assert_not_called()

    def test_current_source_narrative_row_focus_context_pins_scoring_ties_limits_and_exceptions(self) -> None:
        nested = {"preserve": True}
        row = {
            "metric_family": "narrative_summary",
            "selected_claim_ids": [" claim_a ", "", "claim_b"],
            "answer": "prepared",
            "nested": nested,
        }
        ordered_results = [row]
        before = deepcopy(ordered_results)
        sentences = [
            "before query context",
            "Focus 100",
            "later impact context",
            "Focus query 10 20",
        ]
        events = []

        def normalize(value):
            events.append(("normalize", value))
            return " ".join(str(value).split())

        with (
            patch.object(financial_aggregate_projection, "CALCULATION_NARRATIVE_POLICY", {"growth_impact_markers": ("impact",)}),
            patch.object(financial_aggregate_projection, "narrative_context_terms", return_value=["query"]) as terms,
            patch.object(financial_aggregate_projection, "aggregate_result_operation_family", return_value="narrative_summary"),
            patch.object(financial_aggregate_projection, "_split_narrative_sentences", return_value=sentences),
            patch.object(financial_aggregate_projection, "narrative_sentence_looks_table_noisy", return_value=False),
            patch.object(financial_aggregate_projection, "narrative_sentence_looks_abbreviated_fragment", return_value=False),
            patch.object(financial_aggregate_projection, "_normalise_spaces", side_effect=normalize),
        ):
            selected = financial_aggregate_projection.narrative_row_focus_context(
                query="query",
                ordered_results=ordered_results,
                focus_variants=["Focus"],
                max_sentences=2,
            )
        self.assertEqual(selected, (0, "Focus 100 later impact context", ["claim_a", "claim_b"]))
        terms.assert_called_once_with("query")
        self.assertEqual(ordered_results, before)
        self.assertIs(ordered_results[0]["nested"], nested)

        scored_sentences = ["Focus query 10 20 30", "Focus impact 99"]
        with (
            patch.object(financial_aggregate_projection, "CALCULATION_NARRATIVE_POLICY", {"growth_impact_markers": ("impact",)}),
            patch.object(financial_aggregate_projection, "narrative_context_terms", return_value=["query"]),
            patch.object(financial_aggregate_projection, "aggregate_result_operation_family", return_value="narrative_summary"),
            patch.object(financial_aggregate_projection, "_split_narrative_sentences", return_value=scored_sentences),
            patch.object(financial_aggregate_projection, "narrative_sentence_looks_table_noisy", return_value=False),
            patch.object(financial_aggregate_projection, "narrative_sentence_looks_abbreviated_fragment", return_value=False),
        ):
            self.assertEqual(
                financial_aggregate_projection.narrative_row_focus_context(
                    query="query",
                    ordered_results=ordered_results,
                    focus_variants=["Focus"],
                    max_sentences=1,
                ),
                (0, "Focus impact 99", ["claim_a", "claim_b"]),
            )

        filtered_sentences = ["Focus noisy", "Focus fragment", "Focus valid"]
        with (
            patch.object(financial_aggregate_projection, "CALCULATION_NARRATIVE_POLICY", {"growth_impact_markers": ()}),
            patch.object(financial_aggregate_projection, "narrative_context_terms", return_value=[]),
            patch.object(financial_aggregate_projection, "aggregate_result_operation_family", return_value="narrative_summary"),
            patch.object(financial_aggregate_projection, "_split_narrative_sentences", return_value=filtered_sentences),
            patch.object(
                financial_aggregate_projection,
                "narrative_sentence_looks_table_noisy",
                side_effect=lambda value: value == "Focus noisy",
            ),
            patch.object(
                financial_aggregate_projection,
                "narrative_sentence_looks_abbreviated_fragment",
                side_effect=lambda value, _markers: value == "Focus fragment",
            ),
        ):
            self.assertEqual(
                financial_aggregate_projection.narrative_row_focus_context(
                    query="query",
                    ordered_results=ordered_results,
                    focus_variants=["Focus"],
                ),
                (0, "Focus valid", ["claim_a", "claim_b"]),
            )

        term_owner = Mock(side_effect=AssertionError("terms accessed"))
        with patch.object(financial_aggregate_projection, "narrative_context_terms", term_owner):
            self.assertIsNone(
                financial_aggregate_projection.narrative_row_focus_context(
                    query="query",
                    ordered_results=ordered_results,
                    focus_variants=[],
                )
            )
        term_owner.assert_not_called()

        family_owner = Mock(side_effect=AssertionError("family accessed"))
        with (
            patch.object(
                financial_aggregate_projection,
                "narrative_context_terms",
                side_effect=RuntimeError("terms failed"),
            ),
            patch.object(financial_aggregate_projection, "aggregate_result_operation_family", family_owner),
        ):
            with self.assertRaisesRegex(RuntimeError, "terms failed"):
                financial_aggregate_projection.narrative_row_focus_context(
                    query="query",
                    ordered_results=ordered_results,
                    focus_variants=["Focus"],
                )
        family_owner.assert_not_called()

        noisy_owner = Mock(side_effect=AssertionError("noise accessed"))
        with (
            patch.object(financial_aggregate_projection, "CALCULATION_NARRATIVE_POLICY", {"growth_impact_markers": ()}),
            patch.object(financial_aggregate_projection, "narrative_context_terms", return_value=[]),
            patch.object(financial_aggregate_projection, "aggregate_result_operation_family", return_value="narrative_summary"),
            patch.object(
                financial_aggregate_projection,
                "_split_narrative_sentences",
                side_effect=RuntimeError("split failed"),
            ),
            patch.object(financial_aggregate_projection, "narrative_sentence_looks_table_noisy", noisy_owner),
        ):
            with self.assertRaisesRegex(RuntimeError, "split failed"):
                financial_aggregate_projection.narrative_row_focus_context(
                    query="query",
                    ordered_results=ordered_results,
                    focus_variants=["Focus"],
                )
        noisy_owner.assert_not_called()

    def test_current_source_narrative_row_focus_bindings_pin_defs_calls_plan_dag_and_baseline(self) -> None:
        import json
        from pathlib import Path

        module_sources = {
            "graph": inspect.getsource(financial_graph_calculation),
            "owner": inspect.getsource(financial_aggregate_projection),
        }
        module_trees = {name: ast.parse(source) for name, source in module_sources.items()}
        current_targets = {
            "sentence": "narrative_row_focus_sentence",
            "context": "narrative_row_focus_context",
        }
        retired_private_targets = {
            "_" + "narrative_row_focus_sentence",
            "_" + "narrative_row_focus_context",
        }
        definitions = {}
        all_definition_names = set()
        calls = {key: [] for key in current_targets}
        try_depths = {key: [] for key in current_targets}
        noncall_source_refs = []

        class BindingVisitor(ast.NodeVisitor):
            def __init__(self, module_name):
                self.module_name = module_name
                self.function_stack = []
                self.try_depth = 0
                self.call_depth = 0

            def visit_FunctionDef(self, node):
                all_definition_names.add(node.name)
                if node.name in current_targets.values():
                    definitions[node.name] = (self.module_name, node)
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
                receiver = ast.unparse(node.func.value) if isinstance(node.func, ast.Attribute) else ""
                for key, target in current_targets.items():
                    if called_name == target:
                        calls[key].append(
                            (
                                self.module_name,
                                tuple(self.function_stack),
                                receiver,
                                tuple(ast.unparse(argument) for argument in node.args),
                                tuple((keyword.arg, ast.unparse(keyword.value)) for keyword in node.keywords),
                            )
                        )
                        try_depths[key].append(self.try_depth)
                self.call_depth += 1
                self.generic_visit(node)
                self.call_depth -= 1

            def visit_Attribute(self, node):
                if node.attr in current_targets.values() and self.call_depth == 0:
                    noncall_source_refs.append((self.module_name, node.attr, node.lineno))
                self.generic_visit(node)

        for module_name, tree in module_trees.items():
            BindingVisitor(module_name).visit(tree)

        self.assertEqual(
            {
                name: (module_name, node.end_lineno - node.lineno + 1)
                for name, (module_name, node) in definitions.items()
            },
            {
                "narrative_row_focus_sentence": ("owner", 26),
                "narrative_row_focus_context": ("owner", 67),
            },
        )
        self.assertTrue(retired_private_targets.isdisjoint(all_definition_names))
        self.assertEqual({key: len(entries) for key, entries in calls.items()}, {"sentence": 1, "context": 2})
        self.assertEqual(try_depths, {"sentence": [0], "context": [0, 0]})
        self.assertEqual(noncall_source_refs, [])
        self.assertTrue(
            all(
                receiver == "" and not args and keywords
                for entries in calls.values()
                for _module, _stack, receiver, args, keywords in entries
            )
        )
        self.assertEqual(
            calls["sentence"],
            [
                (
                    "graph",
                    ("_compose_growth_narrative_answer",),
                    "",
                    (),
                    (
                        ("ordered_results", "ordered_results"),
                        ("focus_variants", "parenthetical_variants"),
                    ),
                )
            ],
        )
        self.assertEqual(
            calls["context"],
            [
                (
                    "graph",
                    ("_compose_growth_narrative_answer",),
                    "",
                    (),
                    (
                        ("query", "query"),
                        ("ordered_results", "ordered_results"),
                        ("focus_variants", "focus_required_variants or focus_variants"),
                    ),
                ),
                (
                    "graph",
                    ("_answer_satisfies_growth_narrative_intent",),
                    "",
                    (),
                    (
                        ("query", "query_text"),
                        ("ordered_results", "ordered_results"),
                        ("focus_variants", "required_focus_terms"),
                    ),
                ),
            ],
        )

        selected_definition_names = set(current_targets.values())
        actual = {}
        for key, entries in calls.items():
            external = 0
            local = 0
            for module_name, function_stack, _receiver, _args, _keywords in entries:
                if module_name == "owner" or selected_definition_names.intersection(function_stack):
                    local += 1
                else:
                    external += 1
            actual[key] = (external, local)
        self.assertEqual(actual, {"sentence": (1, 0), "context": (2, 0)})
        self.assertEqual(
            (
                sum(external for external, _local in actual.values()),
                sum(local for _external, local in actual.values()),
            ),
            (3, 0),
        )

        def imported_modules(tree):
            modules = set()
            for node in tree.body:
                if isinstance(node, ast.ImportFrom) and node.module:
                    modules.add(node.module)
                elif isinstance(node, ast.Import):
                    modules.update(alias.name for alias in node.names)
            return modules

        owner_imports = imported_modules(module_trees["owner"])
        self.assertIn("src.agent.financial_text_surface", owner_imports)
        self.assertIn("src.config.retrieval_policy", owner_imports)
        graph_bindings = [
            (alias.name, alias.asname)
            for node in module_trees["graph"].body
            if isinstance(node, ast.ImportFrom)
            and node.module == "src.agent.financial_aggregate_projection"
            for alias in node.names
            if alias.name in current_targets.values()
        ]
        self.assertEqual(
            graph_bindings,
            [
                ("narrative_row_focus_context", None),
                ("narrative_row_focus_sentence", None),
            ],
        )
        text_tree = ast.parse(Path("src/agent/financial_text_surface.py").read_text(encoding="utf-8"))
        self.assertNotIn("src.agent.financial_aggregate_projection", imported_modules(text_tree))

        baseline = json.loads(
            (Path(__file__).parent / "fixtures" / "runtime_domain_terms_baseline.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(len(baseline["records"]), 217)
        self.assertEqual(
            [
                record
                for record in baseline["records"]
                if record.get("path") == "src/agent/financial_aggregate_projection.py"
                and any(
                    min(node.lineno for _module, node in definitions.values())
                    <= line
                    <= max(node.end_lineno for _module, node in definitions.values())
                    for line in record.get("first_lines") or []
                )
            ],
            [],
        )

    def test_current_source_narrative_row_focus_composer_callers_pin_args_adoption_and_stop(self) -> None:
        nested = {"preserve": True}
        ordered_results = []
        evidence_items = [{"evidence_id": "ev_1", "nested": nested}]

        def configured_agent():
            primary = {"rendered_value": "10%", "nested": nested}
            current = {"period": "2024", "label": "Revenue", "nested": nested}
            prior = {"period": "2023", "nested": nested}
            row = {
                "calculation_result": {
                    "answer_slots": {
                        "primary_value": primary,
                        "current_value": current,
                        "prior_value": prior,
                    }
                },
                "nested": nested,
            }
            local_agent = financial_graph_calculation.FinancialAgentCalculationMixin()
            local_agent._aggregate_result_operation_family = Mock(return_value="growth_rate")
            local_agent._growth_narrative_sentence_candidates = Mock(
                return_value=[(1, "base candidate", ["base"])]
            )
            local_agent._answer_matches_supported_aggregate_subtask = Mock(return_value=False)
            local_agent._supported_growth_driver_groups = Mock(return_value=[])
            return local_agent, row

        policy = dict(financial_graph_calculation.CALCULATION_NARRATIVE_POLICY)

        def run_with_selected(context_result, sentence_result):
            local_agent, row = configured_agent()
            runtime_results = [row]
            context_owner = Mock(return_value=context_result)
            sentence_owner = Mock(return_value=sentence_result)
            display_owner = Mock(side_effect=["200", "100"])
            share_owner = Mock(return_value=False)
            before_row = deepcopy(row)
            before_evidence = deepcopy(evidence_items)
            with (
                patch.object(
                    financial_graph_calculation,
                    "growth_required_display_values",
                    return_value=["10%", "200", "100"],
                ),
                patch.object(financial_graph_calculation, "_query_requests_narrative_context", return_value=True),
                patch.object(financial_graph_calculation, "answer_looks_truncated", return_value=False),
                patch.object(financial_graph_calculation, "growth_row_has_conflicting_periods", return_value=False),
                patch.object(financial_graph_calculation, "answer_slot_has_material", return_value=True),
                patch.object(financial_graph_calculation, "CALCULATION_NARRATIVE_POLICY", policy),
                patch.object(financial_graph_calculation, "narrative_focus_variants", return_value=["Needle"]),
                patch.object(financial_graph_calculation, "parenthetical_focus_variants", return_value=["Needle"]),
                patch.object(financial_graph_calculation, "answer_covers_narrative_context", return_value=False),
                patch.object(financial_graph_calculation, "narrative_row_focus_context", context_owner),
                patch.object(financial_graph_calculation, "narrative_row_focus_sentence", sentence_owner),
                patch.object(financial_graph_calculation, "growth_slot_display_value", display_owner),
                patch.object(financial_graph_calculation, "growth_slots_share_material", share_owner),
            ):
                result = local_agent._compose_growth_narrative_answer(
                    query="growth query",
                    ordered_results=runtime_results,
                    existing_answer="",
                    evidence_items=evidence_items,
                )
            context_owner.assert_called_once_with(
                query="growth query",
                ordered_results=runtime_results,
                focus_variants=["Needle"],
            )
            self.assertIs(context_owner.call_args.kwargs["ordered_results"], runtime_results)
            self.assertEqual(row, before_row)
            self.assertIs(row["nested"], nested)
            self.assertEqual(evidence_items, before_evidence)
            self.assertIs(evidence_items[0]["nested"], nested)
            return result, sentence_owner, runtime_results

        context_result, sentence_owner, _row = run_with_selected(
            (0, "context row", ["ctx"]),
            None,
        )
        sentence_owner.assert_not_called()
        self.assertIn("context row", context_result["compressed_answer"])
        self.assertEqual(context_result["selected_claim_ids"], ["ctx"])

        sentence_result, sentence_owner, sentence_results = run_with_selected(
            None,
            (0, "sentence row", ["sentence"]),
        )
        sentence_owner.assert_called_once_with(
            ordered_results=sentence_results,
            focus_variants=["Needle"],
        )
        self.assertIs(sentence_owner.call_args.kwargs["ordered_results"], sentence_results)
        self.assertIn("sentence row", sentence_result["compressed_answer"])
        self.assertEqual(sentence_result["selected_claim_ids"], ["sentence"])

        failing_agent, failing_row = configured_agent()
        sentence_owner = Mock(side_effect=AssertionError("sentence accessed"))
        before_row = deepcopy(failing_row)
        with (
            patch.object(
                financial_graph_calculation,
                "growth_required_display_values",
                return_value=["10%", "200", "100"],
            ),
            patch.object(financial_graph_calculation, "_query_requests_narrative_context", return_value=True),
            patch.object(financial_graph_calculation, "answer_looks_truncated", return_value=False),
            patch.object(financial_graph_calculation, "growth_row_has_conflicting_periods", return_value=False),
            patch.object(financial_graph_calculation, "answer_slot_has_material", return_value=True),
            patch.object(financial_graph_calculation, "CALCULATION_NARRATIVE_POLICY", policy),
            patch.object(financial_graph_calculation, "narrative_focus_variants", return_value=["Needle"]),
            patch.object(financial_graph_calculation, "parenthetical_focus_variants", return_value=["Needle"]),
            patch.object(financial_graph_calculation, "growth_slot_display_value", side_effect=["200", "100"]),
            patch.object(financial_graph_calculation, "growth_slots_share_material", return_value=False),
            patch.object(
                financial_graph_calculation,
                "narrative_row_focus_context",
                side_effect=RuntimeError("context owner failed"),
            ),
            patch.object(financial_graph_calculation, "narrative_row_focus_sentence", sentence_owner),
        ):
            with self.assertRaisesRegex(RuntimeError, "context owner failed"):
                failing_agent._compose_growth_narrative_answer(
                    query="growth query",
                    ordered_results=[failing_row],
                    existing_answer="",
                    evidence_items=evidence_items,
                )
        sentence_owner.assert_not_called()
        self.assertEqual(failing_row, before_row)

    def test_current_source_narrative_row_focus_intent_caller_pins_args_result_and_stop(self) -> None:
        nested = {"preserve": True}
        growth_row = {"metric_family": "growth", "nested": nested}
        narrative_row = {"metric_family": "narrative_summary", "nested": nested}
        ordered_results = [growth_row, narrative_row]
        evidence_items = [{"evidence_id": "ev_1", "nested": nested}]
        before_results = deepcopy(ordered_results)
        before_evidence = deepcopy(evidence_items)
        policy = {
            "growth_query_pattern": "growth",
            "missing_answer_markers": (),
            "percent_display_pattern": r"\d+%",
            "growth_impact_markers": ("impact",),
            "growth_generic_focus_terms": (),
            "growth_metric_label_terms": (),
        }

        def family(row):
            return "growth_rate" if row is growth_row else "narrative_summary"

        context_owner = Mock(return_value=None)
        candidates = Mock(return_value=[])
        groups = Mock(return_value=[])
        with (
            patch.object(financial_graph_calculation, "CALCULATION_NARRATIVE_POLICY", policy),
            patch.object(financial_graph_calculation, "_query_requests_narrative_context", return_value=True),
            patch.object(financial_graph_calculation, "growth_row_has_conflicting_periods", return_value=False),
            patch.object(self.agent, "_aggregate_result_operation_family", side_effect=family),
            patch.object(financial_graph_calculation, "growth_required_display_values", return_value=[]),
            patch.object(financial_graph_calculation, "narrative_context_terms", return_value=["Needle"]),
            patch.object(financial_graph_calculation, "parenthetical_focus_variants", return_value=[]),
            patch.object(self.agent, "_growth_narrative_sentence_candidates", candidates),
            patch.object(self.agent, "_supported_growth_driver_groups", groups),
            patch.object(financial_graph_calculation, "narrative_row_focus_context", context_owner),
        ):
            self.assertTrue(
                self.agent._answer_satisfies_growth_narrative_intent(
                    query="  growth   query ",
                    answer="10% impact Needle",
                    ordered_results=ordered_results,
                    evidence_items=evidence_items,
                )
            )
        context_owner.assert_called_once_with(
            query="growth query",
            ordered_results=ordered_results,
            focus_variants=["Needle"],
        )
        self.assertIs(context_owner.call_args.kwargs["ordered_results"], ordered_results)
        candidates.assert_called_once_with(
            query="growth query",
            ordered_results=ordered_results,
            evidence_items=evidence_items,
        )
        self.assertIs(candidates.call_args.kwargs["ordered_results"], ordered_results)
        self.assertIsNot(candidates.call_args.kwargs["evidence_items"], evidence_items)
        self.assertEqual(candidates.call_args.kwargs["evidence_items"], evidence_items)
        groups.assert_called_once_with(query="growth query", narrative_candidates=[])
        self.assertEqual(ordered_results, before_results)
        self.assertEqual(evidence_items, before_evidence)
        self.assertIs(ordered_results[0]["nested"], nested)
        self.assertIs(evidence_items[0]["nested"], nested)

        coverage = Mock(return_value=False)
        with (
            patch.object(financial_graph_calculation, "CALCULATION_NARRATIVE_POLICY", policy),
            patch.object(financial_graph_calculation, "_query_requests_narrative_context", return_value=True),
            patch.object(financial_graph_calculation, "growth_row_has_conflicting_periods", return_value=False),
            patch.object(self.agent, "_aggregate_result_operation_family", side_effect=family),
            patch.object(financial_graph_calculation, "growth_required_display_values", return_value=[]),
            patch.object(financial_graph_calculation, "narrative_context_terms", return_value=["Needle"]),
            patch.object(financial_graph_calculation, "parenthetical_focus_variants", return_value=[]),
            patch.object(self.agent, "_growth_narrative_sentence_candidates", return_value=[]),
            patch.object(self.agent, "_supported_growth_driver_groups", return_value=[]),
            patch.object(financial_graph_calculation, "narrative_row_focus_context", return_value=(0, "required context", [])),
            patch.object(financial_graph_calculation, "answer_covers_narrative_context", coverage),
        ):
            self.assertFalse(
                self.agent._answer_satisfies_growth_narrative_intent(
                    query="growth query",
                    answer="10% impact Needle",
                    ordered_results=ordered_results,
                    evidence_items=evidence_items,
                )
            )
        coverage.assert_called_once_with("10% impact Needle", "required context")

        operation_family = Mock(side_effect=("growth_rate", AssertionError("final scan continued")))
        with (
            patch.object(financial_graph_calculation, "CALCULATION_NARRATIVE_POLICY", policy),
            patch.object(financial_graph_calculation, "_query_requests_narrative_context", return_value=True),
            patch.object(financial_graph_calculation, "growth_row_has_conflicting_periods", return_value=False),
            patch.object(self.agent, "_aggregate_result_operation_family", operation_family),
            patch.object(financial_graph_calculation, "growth_required_display_values", return_value=[]),
            patch.object(financial_graph_calculation, "narrative_context_terms", return_value=["Needle"]),
            patch.object(financial_graph_calculation, "parenthetical_focus_variants", return_value=[]),
            patch.object(self.agent, "_growth_narrative_sentence_candidates", return_value=[]),
            patch.object(self.agent, "_supported_growth_driver_groups", return_value=[]),
            patch.object(
                financial_graph_calculation,
                "narrative_row_focus_context",
                side_effect=RuntimeError("context owner failed"),
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "context owner failed"):
                self.agent._answer_satisfies_growth_narrative_intent(
                    query="growth query",
                    answer="10% impact Needle",
                    ordered_results=ordered_results,
                    evidence_items=evidence_items,
                )
        self.assertEqual(operation_family.call_count, 1)
        self.assertEqual(ordered_results, before_results)
        self.assertEqual(evidence_items, before_evidence)

    def test_current_source_growth_slot_display_pair_pins_precedence_laziness_identity_and_exceptions(self) -> None:
        nested = {"preserve": True}
        source_slot = {
            "rendered_value": " SOURCE DISPLAY ",
            "raw_value": "source raw",
            "nested": nested,
        }
        ordered_results = [
            {"task_id": "other", "answer_slots": {"primary_value": {"rendered_value": "other"}}},
            {
                "task_id": " task_2 ",
                "calculation_result": {
                    "answer_slots": {"prior_value": source_slot},
                    "nested": nested,
                },
                "nested": nested,
            },
        ]
        slot = {
            "source_task_id": " task_2 ",
            "source_slot": " prior_value ",
            "rendered_value": "slot display",
            "nested": nested,
        }
        before_slot = deepcopy(slot)
        before_results = deepcopy(ordered_results)

        def normalize(value):
            return " ".join(str(value).split())

        material = Mock(return_value=True)
        with (
            patch.object(financial_aggregate_projection, "_normalise_spaces", side_effect=normalize),
            patch.object(financial_aggregate_projection, "answer_slot_has_material", material),
        ):
            self.assertEqual(
                financial_aggregate_projection._slot_display_from_source_task(slot, ordered_results),
                "SOURCE DISPLAY",
            )
        material.assert_called_once()
        material_arg = material.call_args.args[0]
        self.assertIsNot(material_arg, source_slot)
        self.assertIs(material_arg["nested"], nested)
        self.assertEqual(slot, before_slot)
        self.assertEqual(ordered_results, before_results)
        self.assertIs(slot["nested"], nested)
        self.assertIs(ordered_results[1]["nested"], nested)

        fallback_source_slot = {"rendered_value": "", "raw_value": " raw fallback ", "nested": nested}
        fallback_results = [
            {
                "task_id": "task_3",
                "answer_slots": {"primary_value": fallback_source_slot},
            }
        ]
        with (
            patch.object(financial_aggregate_projection, "_normalise_spaces", side_effect=normalize),
            patch.object(financial_aggregate_projection, "answer_slot_has_material", return_value=True),
        ):
            self.assertEqual(
                financial_aggregate_projection._slot_display_from_source_task(
                    {"source_row_id": "task_output:task_3", "source_slot": ""},
                    fallback_results,
                ),
                "raw fallback",
            )

        class ResultsBomb:
            def __iter__(self):
                raise AssertionError("rows accessed without a source id")

        self.assertEqual(
            financial_aggregate_projection._slot_display_from_source_task(
                {"source_task_id": "", "source_row_id": "unrelated"},
                ResultsBomb(),
            ),
            "",
        )

        class FallbackBomb(dict):
            def get(self, _key, _default=None):
                raise AssertionError("slot fallback accessed")

        fallback_bomb = FallbackBomb({"nested": nested})
        source_owner = Mock(return_value="source display")
        compatibility = Mock(return_value=True)
        normalizer = Mock(side_effect=AssertionError("fallback normalized"))
        with (
            patch.object(financial_aggregate_projection, "_slot_display_from_source_task", source_owner),
            patch.object(
                financial_aggregate_projection,
                "source_task_display_compatible_with_slot",
                compatibility,
            ),
            patch.object(financial_aggregate_projection, "_normalise_spaces", normalizer),
        ):
            self.assertEqual(
                financial_aggregate_projection.growth_slot_display_value(fallback_bomb, ordered_results),
                "source display",
            )
        source_owner.assert_called_once_with(fallback_bomb, ordered_results)
        compatibility.assert_called_once_with(fallback_bomb, "source display")
        normalizer.assert_not_called()

        compatibility = Mock()
        with (
            patch.object(financial_aggregate_projection, "_slot_display_from_source_task", return_value=""),
            patch.object(
                financial_aggregate_projection,
                "source_task_display_compatible_with_slot",
                compatibility,
            ),
            patch.object(financial_aggregate_projection, "_normalise_spaces", side_effect=normalize),
        ):
            self.assertEqual(
                financial_aggregate_projection.growth_slot_display_value(
                    {"rendered_value": "", "raw_value": " raw value "},
                    ordered_results,
                ),
                "raw value",
            )
        compatibility.assert_not_called()

        for compatibility_result, expected in ((False, "slot display"), (True, "source display")):
            with (
                self.subTest(compatibility_result=compatibility_result),
                patch.object(financial_aggregate_projection, "_slot_display_from_source_task", return_value="source display"),
                patch.object(
                    financial_aggregate_projection,
                    "source_task_display_compatible_with_slot",
                    return_value=compatibility_result,
                ),
                patch.object(financial_aggregate_projection, "_normalise_spaces", side_effect=normalize),
            ):
                self.assertEqual(
                    financial_aggregate_projection.growth_slot_display_value(slot, ordered_results),
                    expected,
                )

        compatibility = Mock()
        with (
            patch.object(
                financial_aggregate_projection,
                "_slot_display_from_source_task",
                side_effect=RuntimeError("source display failed"),
            ),
            patch.object(
                financial_aggregate_projection,
                "source_task_display_compatible_with_slot",
                compatibility,
            ),
            self.assertRaisesRegex(RuntimeError, "source display failed"),
        ):
            financial_aggregate_projection.growth_slot_display_value(slot, ordered_results)
        compatibility.assert_not_called()

        with (
            patch.object(financial_aggregate_projection, "_slot_display_from_source_task", return_value="source display"),
            patch.object(
                financial_aggregate_projection,
                "source_task_display_compatible_with_slot",
                side_effect=RuntimeError("compatibility failed"),
            ),
            self.assertRaisesRegex(RuntimeError, "compatibility failed"),
        ):
            financial_aggregate_projection.growth_slot_display_value(fallback_bomb, ordered_results)

    def test_current_source_growth_material_sharing_pins_display_float_and_exception_scope(self) -> None:
        nested = {"preserve": True}
        current_slot = {"normalized_value": "10", "nested": nested}
        prior_slot = {"normalized_value": 10.0, "nested": nested}
        ordered_results = [{"nested": nested}]
        before_current = deepcopy(current_slot)
        before_prior = deepcopy(prior_slot)
        before_results = deepcopy(ordered_results)

        class NormalizedAccessBomb(dict):
            def get(self, key, default=None):
                if key == "normalized_value":
                    raise AssertionError("normalized value accessed")
                return super().get(key, default)

        equal_current = NormalizedAccessBomb({"nested": nested})
        equal_prior = NormalizedAccessBomb({"nested": nested})
        display_owner = Mock(side_effect=["same display", "same display"])
        with patch.object(financial_aggregate_projection, "growth_slot_display_value", display_owner):
            self.assertTrue(
                financial_aggregate_projection.growth_slots_share_material(
                    equal_current,
                    equal_prior,
                    ordered_results,
                )
            )
        self.assertEqual(
            [call.args for call in display_owner.call_args_list],
            [(equal_current, ordered_results), (equal_prior, ordered_results)],
        )

        for current_value, prior_value, expected in (
            ("10", 10.0, True),
            ("10", 11.0, False),
            (None, 10.0, False),
        ):
            with (
                self.subTest(current_value=current_value, prior_value=prior_value),
                patch.object(financial_aggregate_projection, "growth_slot_display_value", side_effect=["current", "prior"]),
            ):
                self.assertEqual(
                    financial_aggregate_projection.growth_slots_share_material(
                        {"normalized_value": current_value},
                        {"normalized_value": prior_value},
                        ordered_results,
                    ),
                    expected,
                )

        class FloatBomb:
            def __init__(self, exc):
                self.exc = exc

            def __float__(self):
                raise self.exc("float failed")

        for exc in (TypeError, ValueError):
            with (
                self.subTest(exc=exc.__name__),
                patch.object(financial_aggregate_projection, "growth_slot_display_value", side_effect=["current", "prior"]),
            ):
                self.assertFalse(
                    financial_aggregate_projection.growth_slots_share_material(
                        {"normalized_value": FloatBomb(exc)},
                        {"normalized_value": 10},
                        ordered_results,
                    )
                )

        with (
            patch.object(financial_aggregate_projection, "growth_slot_display_value", side_effect=["current", "prior"]),
            self.assertRaisesRegex(RuntimeError, "float failed"),
        ):
            financial_aggregate_projection.growth_slots_share_material(
                {"normalized_value": FloatBomb(RuntimeError)},
                {"normalized_value": 10},
                ordered_results,
            )

        display_owner = Mock(side_effect=RuntimeError("display failed"))
        with (
            patch.object(financial_aggregate_projection, "growth_slot_display_value", display_owner),
            self.assertRaisesRegex(RuntimeError, "display failed"),
        ):
            financial_aggregate_projection.growth_slots_share_material(current_slot, prior_slot, ordered_results)
        display_owner.assert_called_once_with(current_slot, ordered_results)
        self.assertEqual(current_slot, before_current)
        self.assertEqual(prior_slot, before_prior)
        self.assertEqual(ordered_results, before_results)
        self.assertIs(current_slot["nested"], nested)
        self.assertIs(prior_slot["nested"], nested)
        self.assertIs(ordered_results[0]["nested"], nested)

    def test_current_source_recover_growth_prior_material_pins_scan_fallback_and_exceptions(self) -> None:
        class SlotBomb(dict):
            def get(self, _key, _default=None):
                raise AssertionError("slot accessed")

        self.assertEqual(
            financial_aggregate_projection.recover_growth_prior_material_from_evidence(
                current_slot=SlotBomb(),
                prior_slot=SlotBomb(),
                evidence_items=[],
            ),
            {},
        )

        split_owner = Mock(side_effect=AssertionError("split accessed"))
        with patch.object(financial_aggregate_projection, "_split_narrative_sentences", split_owner):
            self.assertEqual(
                financial_aggregate_projection.recover_growth_prior_material_from_evidence(
                    current_slot={"period": "current", "label": "metric"},
                    prior_slot=SlotBomb(),
                    evidence_items=[{"claim": "unused"}],
                ),
                {},
            )
        split_owner.assert_not_called()

        nested = {"preserve": True}
        current_slot = {
            "period": "2024",
            "raw_value": "100",
            "raw_unit": "USD",
            "nested": nested,
        }
        prior_slot = {"period": "2023", "raw_unit": " USD ", "nested": nested}
        evidence_items = [
            {"claim": "surface", "quote_span": "quote", "raw_row_text": "raw", "nested": nested},
            {"claim": "later", "nested": nested},
        ]
        before_current = deepcopy(current_slot)
        before_prior = deepcopy(prior_slot)
        before_evidence = deepcopy(evidence_items)
        split_owner = Mock(
            side_effect=[
                ["2023 100 USD", "2022 80 USD", "2021 70 USD"],
                ["2020 60 USD"],
            ]
        )
        policy = {"period_year_suffix": "Y", "nested": nested}
        with (
            patch.object(financial_aggregate_projection, "_split_narrative_sentences", split_owner),
            patch.object(financial_aggregate_projection, "CALCULATION_NARRATIVE_POLICY", policy),
        ):
            recovered = financial_aggregate_projection.recover_growth_prior_material_from_evidence(
                current_slot=current_slot,
                prior_slot=prior_slot,
                evidence_items=evidence_items,
            )
        self.assertEqual(
            recovered,
            {
                "display": "80 USD",
                "period": "2022Y",
                "raw_value": "80",
                "source_quote": "2022 80 USD",
            },
        )
        split_owner.assert_called_once_with("surface quote raw")
        self.assertEqual(current_slot, before_current)
        self.assertEqual(prior_slot, before_prior)
        self.assertEqual(evidence_items, before_evidence)
        self.assertIs(current_slot["nested"], nested)
        self.assertIs(prior_slot["nested"], nested)
        self.assertIs(evidence_items[0]["nested"], nested)
        self.assertEqual(policy, {"period_year_suffix": "Y", "nested": nested})

        with patch.object(
            financial_aggregate_projection,
            "_split_narrative_sentences",
            return_value=["2023 40 units"],
        ):
            self.assertEqual(
                financial_aggregate_projection.recover_growth_prior_material_from_evidence(
                    current_slot={"label": "metric 2024", "raw_value": "50", "raw_unit": ""},
                    prior_slot={"raw_unit": ""},
                    evidence_items=[{"claim": "2023 40 units"}],
                )["raw_value"],
                "2023",
            )

        downstream_split = Mock()
        with (
            patch.object(
                financial_aggregate_projection,
                "_normalise_spaces",
                side_effect=RuntimeError("normalizer failed"),
            ),
            patch.object(financial_aggregate_projection, "_split_narrative_sentences", downstream_split),
            self.assertRaisesRegex(RuntimeError, "normalizer failed"),
        ):
            financial_aggregate_projection.recover_growth_prior_material_from_evidence(
                current_slot=current_slot,
                prior_slot=prior_slot,
                evidence_items=evidence_items,
            )
        downstream_split.assert_not_called()

        class PolicyBomb(dict):
            def get(self, key, default=None):
                if key == "period_year_suffix":
                    raise RuntimeError("policy failed")
                return super().get(key, default)

        with (
            patch.object(
                financial_aggregate_projection,
                "_split_narrative_sentences",
                return_value=["2022 80 USD"],
            ),
            patch.object(financial_aggregate_projection, "CALCULATION_NARRATIVE_POLICY", PolicyBomb()),
            self.assertRaisesRegex(RuntimeError, "policy failed"),
        ):
            financial_aggregate_projection.recover_growth_prior_material_from_evidence(
                current_slot=current_slot,
                prior_slot=prior_slot,
                evidence_items=evidence_items,
            )

    def test_current_source_growth_display_bindings_pin_defs_calls_plan_dag_and_baseline(self) -> None:
        import json
        from pathlib import Path

        module_sources = {
            "graph": inspect.getsource(financial_graph_calculation),
            "owner": inspect.getsource(financial_aggregate_projection),
        }
        module_trees = {name: ast.parse(source) for name, source in module_sources.items()}
        current_targets = {
            "source": "_slot_display_from_source_task",
            "display": "growth_slot_display_value",
            "share": "growth_slots_share_material",
            "recover": "recover_growth_prior_material_from_evidence",
        }
        definitions = {}
        all_definition_names = set()
        calls = {key: [] for key in current_targets}
        try_depths = {key: [] for key in current_targets}
        noncall_refs = []

        class BindingVisitor(ast.NodeVisitor):
            def __init__(self, module_name):
                self.module_name = module_name
                self.function_stack = []
                self.try_depth = 0
                self.call_depth = 0

            def visit_FunctionDef(self, node):
                all_definition_names.add(node.name)
                if node.name in current_targets.values():
                    definitions[node.name] = (self.module_name, node)
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
                receiver = ast.unparse(node.func.value) if isinstance(node.func, ast.Attribute) else ""
                for key, target in current_targets.items():
                    if called_name == target:
                        calls[key].append(
                            (
                                self.module_name,
                                tuple(self.function_stack),
                                receiver,
                                tuple(ast.unparse(arg) for arg in node.args),
                                tuple((kw.arg, ast.unparse(kw.value)) for kw in node.keywords),
                            )
                        )
                        try_depths[key].append(self.try_depth)
                self.call_depth += 1
                self.generic_visit(node)
                self.call_depth -= 1

            def visit_Attribute(self, node):
                if node.attr in current_targets.values() and self.call_depth == 0:
                    noncall_refs.append((self.module_name, node.attr, node.lineno))
                self.generic_visit(node)

        for module_name, tree in module_trees.items():
            BindingVisitor(module_name).visit(tree)

        self.assertEqual(
            {
                name: (module_name, node.end_lineno - node.lineno + 1)
                for name, (module_name, node) in definitions.items()
            },
            {
                "_slot_display_from_source_task": ("owner", 23),
                "growth_slot_display_value": ("owner", 8),
                "growth_slots_share_material": ("owner", 17),
                "recover_growth_prior_material_from_evidence": ("owner", 55),
            },
        )
        self.assertTrue(
            {
                f"_{current_targets[key]}"
                for key in ("display", "share", "recover")
            }.isdisjoint(all_definition_names)
        )
        self.assertEqual(
            {key: len(entries) for key, entries in calls.items()},
            {"source": 1, "display": 9, "share": 4, "recover": 4},
        )
        self.assertEqual(
            try_depths,
            {
                "source": [0],
                "display": [0] * 9,
                "share": [0] * 4,
                "recover": [0] * 4,
            },
        )
        self.assertEqual(noncall_refs, [])
        self.assertTrue(
            all(
                receiver == ""
                for entries in calls.values()
                for _module, _stack, receiver, _args, _kwargs in entries
            )
        )
        self.assertEqual(
            Counter(stack[-1] for _module, stack, _receiver, _args, _kwargs in calls["source"]),
            Counter({"growth_slot_display_value": 1}),
        )
        self.assertEqual(
            Counter(stack[-1] for _module, stack, _receiver, _args, _kwargs in calls["display"]),
            Counter(
                {
                    "growth_slots_share_material": 2,
                    "growth_required_display_values": 3,
                    "compose_complete_growth_numeric_answer": 2,
                    "_compose_growth_narrative_answer": 2,
                }
            ),
        )
        self.assertEqual(
            Counter(stack[-1] for _module, stack, _receiver, _args, _kwargs in calls["share"]),
            Counter(
                {
                    "growth_required_display_values": 1,
                    "compose_complete_growth_numeric_answer": 1,
                    "_compose_growth_narrative_answer": 1,
                    "_recover_duplicate_growth_prior_operand": 1,
                }
            ),
        )
        self.assertEqual(
            Counter(stack[-1] for _module, stack, _receiver, _args, _kwargs in calls["recover"]),
            Counter(
                {
                    "growth_required_display_values": 1,
                    "compose_complete_growth_numeric_answer": 1,
                    "_compose_growth_narrative_answer": 1,
                    "_recover_duplicate_growth_prior_operand": 1,
                }
            ),
        )
        self.assertTrue(
            all(not kwargs for entries in (calls["source"], calls["display"], calls["share"]) for *_head, kwargs in entries)
        )
        self.assertTrue(
            all(
                not args
                and tuple(name for name, _value in kwargs)
                == ("current_slot", "prior_slot", "evidence_items")
                for _module, _stack, _receiver, args, kwargs in calls["recover"]
            )
        )

        self.assertEqual(
            {
                name: node.end_lineno - node.lineno + 1
                for name, (_module, node) in definitions.items()
            },
            {
                "_slot_display_from_source_task": 23,
                "growth_slot_display_value": 8,
                "growth_slots_share_material": 17,
                "recover_growth_prior_material_from_evidence": 55,
            },
        )

        selected_names = set(current_targets.values())
        distribution = {}
        for key, entries in calls.items():
            external = sum(not selected_names.intersection(stack) for _module, stack, *_rest in entries)
            distribution[key] = (external, len(entries) - external)
        self.assertEqual(
            distribution,
            {"source": (0, 1), "display": (7, 2), "share": (4, 0), "recover": (4, 0)},
        )
        self.assertEqual(
            (
                sum(external for external, _local in distribution.values()),
                sum(local for _external, local in distribution.values()),
            ),
            (15, 3),
        )

        def imported_modules(tree):
            modules = set()
            for node in tree.body:
                if isinstance(node, ast.ImportFrom) and node.module:
                    modules.add(node.module)
                elif isinstance(node, ast.Import):
                    modules.update(alias.name for alias in node.names)
            return modules

        owner_imports = imported_modules(module_trees["owner"])
        self.assertIn("src.agent.financial_answer_slots", owner_imports)
        self.assertIn("src.agent.financial_text_surface", owner_imports)
        self.assertIn("src.config.retrieval_policy", owner_imports)
        answer_slots_tree = ast.parse(
            Path("src/agent/financial_answer_slots.py").read_text(encoding="utf-8")
        )
        text_tree = ast.parse(Path("src/agent/financial_text_surface.py").read_text(encoding="utf-8"))
        self.assertNotIn("src.agent.financial_aggregate_projection", imported_modules(answer_slots_tree))
        self.assertNotIn("src.agent.financial_aggregate_projection", imported_modules(text_tree))
        graph_owner_imports = {
            alias.name
            for node in module_trees["graph"].body
            if isinstance(node, ast.ImportFrom)
            and node.module == "src.agent.financial_aggregate_projection"
            for alias in node.names
        }
        self.assertTrue(
            {
                "growth_slot_display_value",
                "growth_slots_share_material",
                "recover_growth_prior_material_from_evidence",
            }.issubset(graph_owner_imports)
        )

        baseline = json.loads(
            (Path(__file__).parent / "fixtures" / "runtime_domain_terms_baseline.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(len(baseline["records"]), 217)
        moved_owner_lines = {
            line
            for _module, node in definitions.values()
            for line in range(node.lineno, node.end_lineno + 1)
        }
        self.assertEqual(
            [
                record
                for record in baseline["records"]
                if record.get("path") == "src/agent/financial_aggregate_projection.py"
                and moved_owner_lines.intersection(record.get("first_lines") or [])
            ],
            [],
        )

    def test_current_source_growth_required_display_caller_pins_args_adoption_laziness_and_stop(self) -> None:
        nested = {"preserve": True}
        primary = {"role": "primary", "rendered_value": "PRIMARY", "nested": nested}
        current = {"role": "current", "rendered_value": "CURRENT", "nested": nested}
        prior = {"role": "prior", "rendered_value": "PRIOR", "nested": nested}
        row = {
            "calculation_result": {
                "rendered_value": "GROWTH",
                "answer_slots": {
                    "primary_value": primary,
                    "current_value": current,
                    "prior_value": prior,
                },
                "nested": nested,
            },
            "nested": nested,
        }
        ordered_results = [row]
        evidence_items = [{"evidence_id": "ev_1", "nested": nested}]
        before_row = deepcopy(row)
        before_results = deepcopy(ordered_results)
        before_evidence = deepcopy(evidence_items)
        events = []

        def display(slot, results):
            events.append(("display", slot.get("role"), slot, results))
            return {"primary": "PRIMARY", "current": "CURRENT", "prior": "PRIOR"}[slot["role"]]

        def share(current_slot, prior_slot, results):
            events.append(("share", current_slot, prior_slot, results))
            return True

        def recover(*, current_slot, prior_slot, evidence_items):
            events.append(("recover", current_slot, prior_slot, evidence_items))
            return {"display": "RECOVERED", "period": "2022"}

        with (
            patch.object(financial_aggregate_projection, "growth_slot_display_value", side_effect=display) as display_owner,
            patch.object(financial_aggregate_projection, "growth_slots_share_material", side_effect=share) as share_owner,
            patch.object(
                financial_aggregate_projection,
                "recover_growth_prior_material_from_evidence",
                side_effect=recover,
            ) as recover_owner,
        ):
            values = financial_aggregate_projection.growth_required_display_values(
                row,
                ordered_results,
                evidence_items,
            )
        self.assertEqual(values, ["CURRENT", "RECOVERED", "GROWTH"])
        self.assertEqual([event[0] for event in events], ["display", "share", "recover", "display"])
        self.assertEqual([event[1] for event in events if event[0] == "display"], ["prior", "current"])
        self.assertEqual(display_owner.call_count, 2)
        share_owner.assert_called_once()
        recover_owner.assert_called_once()
        prior_arg = display_owner.call_args_list[0].args[0]
        current_arg = display_owner.call_args_list[1].args[0]
        self.assertIsNot(prior_arg, prior)
        self.assertIsNot(current_arg, current)
        self.assertIs(prior_arg["nested"], nested)
        self.assertIs(current_arg["nested"], nested)
        self.assertIs(display_owner.call_args_list[0].args[1], ordered_results)
        self.assertIs(share_owner.call_args.args[2], ordered_results)
        self.assertIs(recover_owner.call_args.kwargs["evidence_items"], evidence_items)
        self.assertEqual(row, before_row)
        self.assertEqual(ordered_results, before_results)
        self.assertEqual(evidence_items, before_evidence)
        self.assertIs(row["nested"], nested)
        self.assertIs(evidence_items[0]["nested"], nested)

        recovery_owner = Mock()
        primary_display = Mock(side_effect=AssertionError("primary display accessed"))
        with (
            patch.object(financial_aggregate_projection, "growth_slot_display_value", side_effect=["PRIOR", "CURRENT"]) as display_owner,
            patch.object(financial_aggregate_projection, "growth_slots_share_material", return_value=False),
            patch.object(financial_aggregate_projection, "recover_growth_prior_material_from_evidence", recovery_owner),
        ):
            self.assertEqual(
                financial_aggregate_projection.growth_required_display_values(row, ordered_results, evidence_items),
                ["CURRENT", "PRIOR", "GROWTH"],
            )
        recovery_owner.assert_not_called()
        self.assertEqual(display_owner.call_count, 2)
        primary_display.assert_not_called()

        recovery_owner = Mock()
        current_display = Mock(side_effect=AssertionError("current display accessed"))
        with (
            patch.object(financial_aggregate_projection, "growth_slot_display_value", side_effect=["PRIOR", current_display]),
            patch.object(
                financial_aggregate_projection,
                "growth_slots_share_material",
                side_effect=RuntimeError("share failed"),
            ),
            patch.object(financial_aggregate_projection, "recover_growth_prior_material_from_evidence", recovery_owner),
            self.assertRaisesRegex(RuntimeError, "share failed"),
        ):
            financial_aggregate_projection.growth_required_display_values(row, ordered_results, evidence_items)
        recovery_owner.assert_not_called()
        self.assertEqual(row, before_row)
        self.assertEqual(evidence_items, before_evidence)

    def test_current_source_complete_growth_caller_pins_args_adoption_order_and_stop(self) -> None:
        nested = {"preserve": True}
        primary = {
            "role": "primary",
            "rendered_value": "10%",
            "normalized_value": 10,
            "direction": "increase",
            "nested": nested,
        }
        current = {
            "role": "current",
            "label": "Metric",
            "period": "2024",
            "nested": nested,
        }
        prior = {"role": "prior", "period": "2023", "nested": nested}
        row = {
            "metric_label": "Metric",
            "calculation_result": {
                "rendered_value": "10%",
                "answer_slots": {
                    "primary_value": primary,
                    "current_value": current,
                    "prior_value": prior,
                },
            },
            "nested": nested,
        }
        ordered_results = [row]
        evidence_items = [{"evidence_id": "ev_1", "nested": nested}]
        before_row = deepcopy(row)
        before_results = deepcopy(ordered_results)
        before_evidence = deepcopy(evidence_items)
        events = []

        def display(slot, results):
            events.append(("display", slot["role"], slot, results))
            return "CURRENT" if slot["role"] == "current" else "PRIOR"

        def share(current_slot, prior_slot, results):
            events.append(("share", current_slot, prior_slot, results))
            return True

        def recover(*, current_slot, prior_slot, evidence_items):
            events.append(("recover", current_slot, prior_slot, evidence_items))
            return {"display": "RECOVERED", "period": "2022"}

        policy = {
            "direction_words": {"increase": "UP", "decrease": "DOWN", "growth": "GROW"},
            "growth_direction_metric_terms": (),
            "period_year_suffix": "Y",
            "period_prefix_with_year_template": "[{period}]",
            "period_prefix_template": "[{period}]",
            "prior_phrase_with_value_template": "prior {period} {value}",
            "growth_numeric_sentence_template": (
                "{period_prefix} {metric_label}{topic_particle} {current_value} "
                "{prior_phrase} {growth_value} {direction_word}"
            ),
        }
        absolute = Mock(side_effect=lambda value: str(value))
        with (
            patch.object(financial_aggregate_projection, "aggregate_result_operation_family", return_value="growth_rate"),
            patch.object(financial_aggregate_projection, "answer_slot_has_material", return_value=True),
            patch.object(financial_aggregate_projection, "growth_slot_display_value", side_effect=display) as display_owner,
            patch.object(financial_aggregate_projection, "growth_slots_share_material", side_effect=share) as share_owner,
            patch.object(
                financial_aggregate_projection,
                "recover_growth_prior_material_from_evidence",
                side_effect=recover,
            ) as recover_owner,
            patch.object(financial_aggregate_projection.calculation_rendering, "absolute_display_value", absolute),
            patch.object(financial_aggregate_projection, "CALCULATION_SLOT_POLICY", {"period_pattern": r"$^"}),
            patch.object(financial_aggregate_projection, "CALCULATION_NARRATIVE_POLICY", policy),
            patch.object(financial_aggregate_projection, "topic_particle", return_value="|P|"),
        ):
            answer = financial_aggregate_projection.compose_complete_growth_numeric_answer(
                row,
                ordered_results,
                evidence_items,
            )
        self.assertEqual(
            answer,
            "[2024] Metric|P| CURRENT prior 2022Y RECOVERED 10% UP",
        )
        self.assertEqual([event[0] for event in events], ["display", "display", "share", "recover"])
        self.assertEqual([event[1] for event in events if event[0] == "display"], ["current", "prior"])
        self.assertIs(display_owner.call_args_list[0].args[1], ordered_results)
        self.assertIs(share_owner.call_args.args[2], ordered_results)
        self.assertIs(recover_owner.call_args.kwargs["evidence_items"], evidence_items)
        self.assertEqual([call.args[0] for call in absolute.call_args_list], ["CURRENT", "PRIOR", "RECOVERED", "10%"])
        self.assertEqual(row, before_row)
        self.assertEqual(ordered_results, before_results)
        self.assertEqual(evidence_items, before_evidence)
        self.assertIs(primary["nested"], nested)
        self.assertIs(evidence_items[0]["nested"], nested)

        downstream_share = Mock()
        downstream_recovery = Mock()
        downstream_absolute = Mock()
        with (
            patch.object(financial_aggregate_projection, "aggregate_result_operation_family", return_value="growth_rate"),
            patch.object(financial_aggregate_projection, "answer_slot_has_material", return_value=True),
            patch.object(
                financial_aggregate_projection,
                "growth_slot_display_value",
                side_effect=RuntimeError("display failed"),
            ),
            patch.object(financial_aggregate_projection, "growth_slots_share_material", downstream_share),
            patch.object(financial_aggregate_projection, "recover_growth_prior_material_from_evidence", downstream_recovery),
            patch.object(financial_aggregate_projection.calculation_rendering, "absolute_display_value", downstream_absolute),
            self.assertRaisesRegex(RuntimeError, "display failed"),
        ):
            financial_aggregate_projection.compose_complete_growth_numeric_answer(row, ordered_results, evidence_items)
        downstream_share.assert_not_called()
        downstream_recovery.assert_not_called()
        downstream_absolute.assert_not_called()
        self.assertEqual(row, before_row)
        self.assertEqual(evidence_items, before_evidence)

    def test_current_source_growth_composer_and_duplicate_recovery_pin_selected_owner_calls(self) -> None:
        nested = {"preserve": True}

        def configured_agent():
            primary = {
                "rendered_value": "10%",
                "normalized_value": 10,
                "direction": "increase",
                "nested": nested,
            }
            current = {"period": "2024", "label": "Revenue", "nested": nested}
            prior = {"period": "2023", "nested": nested}
            row = {
                "calculation_result": {
                    "answer_slots": {
                        "primary_value": primary,
                        "current_value": current,
                        "prior_value": prior,
                    }
                },
                "nested": nested,
            }
            local_agent = financial_graph_calculation.FinancialAgentCalculationMixin()
            local_agent._aggregate_result_operation_family = Mock(return_value="growth_rate")
            local_agent._growth_narrative_sentence_candidates = Mock(
                return_value=[(1, "base candidate", ["base"])]
            )
            local_agent._answer_matches_supported_aggregate_subtask = Mock(return_value=False)
            local_agent._supported_growth_driver_groups = Mock(return_value=[])
            return local_agent, row

        local_agent, row = configured_agent()
        ordered_results = [row]
        evidence_items = [{"evidence_id": "ev_1", "nested": nested}]
        before_row = deepcopy(row)
        before_evidence = deepcopy(evidence_items)
        display_owner = Mock(side_effect=["CURRENT", "PRIOR"])
        share_owner = Mock(return_value=True)
        recover_owner = Mock(return_value={"display": "RECOVERED", "period": "2022"})
        with (
            patch.object(financial_graph_calculation, "growth_required_display_values", return_value=[]),
            patch.object(financial_graph_calculation, "_query_requests_narrative_context", return_value=True),
            patch.object(financial_graph_calculation, "answer_looks_truncated", return_value=False),
            patch.object(financial_graph_calculation, "growth_row_has_conflicting_periods", return_value=False),
            patch.object(financial_graph_calculation, "answer_slot_has_material", return_value=True),
            patch.object(financial_graph_calculation, "narrative_focus_variants", return_value=[]),
            patch.object(financial_graph_calculation, "parenthetical_focus_variants", return_value=[]),
            patch.object(financial_graph_calculation, "narrative_row_focus_context", return_value=None),
            patch.object(financial_graph_calculation, "narrative_row_focus_sentence", return_value=None),
            patch.object(financial_graph_calculation, "growth_slot_display_value", display_owner),
            patch.object(financial_graph_calculation, "growth_slots_share_material", share_owner),
            patch.object(financial_graph_calculation, "recover_growth_prior_material_from_evidence", recover_owner),
        ):
            result = local_agent._compose_growth_narrative_answer(
                query="growth query",
                ordered_results=ordered_results,
                existing_answer="",
                evidence_items=evidence_items,
            )
        self.assertIsNotNone(result)
        self.assertIn("RECOVERED", result["compressed_answer"])
        self.assertEqual(
            [call.args for call in display_owner.call_args_list],
            [(share_owner.call_args.args[0], ordered_results), (share_owner.call_args.args[1], ordered_results)],
        )
        self.assertIs(share_owner.call_args.args[2], ordered_results)
        self.assertIs(recover_owner.call_args.kwargs["evidence_items"], evidence_items)
        self.assertEqual(row, before_row)
        self.assertEqual(evidence_items, before_evidence)
        self.assertIs(row["nested"], nested)
        self.assertIs(evidence_items[0]["nested"], nested)

        local_agent, row = configured_agent()
        downstream_required = Mock()
        with (
            patch.object(financial_graph_calculation, "growth_required_display_values", downstream_required),
            patch.object(financial_graph_calculation, "_query_requests_narrative_context", return_value=True),
            patch.object(financial_graph_calculation, "answer_looks_truncated", return_value=False),
            patch.object(financial_graph_calculation, "growth_row_has_conflicting_periods", return_value=False),
            patch.object(financial_graph_calculation, "answer_slot_has_material", return_value=True),
            patch.object(financial_graph_calculation, "growth_slot_display_value", side_effect=["CURRENT", "PRIOR"]),
            patch.object(financial_graph_calculation, "growth_slots_share_material", return_value=True),
            patch.object(
                financial_graph_calculation,
                "recover_growth_prior_material_from_evidence",
                side_effect=RuntimeError("recovery failed"),
            ),
            self.assertRaisesRegex(RuntimeError, "recovery failed"),
        ):
            local_agent._compose_growth_narrative_answer(
                query="growth query",
                ordered_results=[row],
                existing_answer="",
                evidence_items=evidence_items,
            )
        downstream_required.assert_not_called()
        self.assertEqual(row, before_row)
        self.assertEqual(evidence_items, before_evidence)

        current_row = {
            "operand_id": "current",
            "matched_operand_role": "current_period",
            "raw_unit": "USD",
            "nested": nested,
        }
        prior_row = {
            "operand_id": "prior",
            "matched_operand_role": "prior_period",
            "raw_unit": "USD",
            "nested": nested,
        }
        ordered_operands = [current_row, prior_row]
        before_operands = deepcopy(ordered_operands)
        share_owner = Mock(return_value=True)
        recover_owner = Mock(
            return_value={
                "display": "80 USD",
                "raw_value": "80",
                "period": "2022",
                "source_quote": "source sentence",
            }
        )
        with (
            patch.object(financial_graph_calculation, "growth_slots_share_material", share_owner),
            patch.object(financial_graph_calculation, "recover_growth_prior_material_from_evidence", recover_owner),
            patch.object(financial_graph_calculation, "_normalise_operand_value", return_value=(80.0, "USD")),
        ):
            updated = self.agent._recover_duplicate_growth_prior_operand(
                ordered_operands,
                evidence_items,
            )
        self.assertIsNot(updated, ordered_operands)
        self.assertIs(updated[0], current_row)
        self.assertIsNot(updated[1], prior_row)
        self.assertEqual(updated[1]["raw_value"], "80")
        self.assertEqual(updated[1]["period"], "2022")
        self.assertEqual(updated[1]["prior_recovery_source"], "evidence_period_display")
        share_current, share_prior, share_results = share_owner.call_args.args
        self.assertIsNot(share_current, current_row)
        self.assertIsNot(share_prior, prior_row)
        self.assertIs(share_current["nested"], nested)
        self.assertIs(share_prior["nested"], nested)
        self.assertEqual(share_results, [])
        self.assertIs(recover_owner.call_args.kwargs["current_slot"], share_current)
        self.assertIs(recover_owner.call_args.kwargs["prior_slot"], share_prior)
        self.assertIs(recover_owner.call_args.kwargs["evidence_items"], evidence_items)
        self.assertEqual(ordered_operands, before_operands)
        self.assertIs(ordered_operands[0]["nested"], nested)
        self.assertIs(ordered_operands[1]["nested"], nested)

        recovery_owner = Mock()
        with (
            patch.object(financial_graph_calculation, "growth_slots_share_material", return_value=False),
            patch.object(financial_graph_calculation, "recover_growth_prior_material_from_evidence", recovery_owner),
        ):
            unchanged = self.agent._recover_duplicate_growth_prior_operand(
                ordered_operands,
                evidence_items,
            )
        self.assertIs(unchanged, ordered_operands)
        recovery_owner.assert_not_called()

        recovery_owner = Mock()
        normalizer = Mock()
        with (
            patch.object(
                financial_graph_calculation,
                "growth_slots_share_material",
                side_effect=RuntimeError("share failed"),
            ),
            patch.object(financial_graph_calculation, "recover_growth_prior_material_from_evidence", recovery_owner),
            patch.object(financial_graph_calculation, "_normalise_operand_value", normalizer),
            self.assertRaisesRegex(RuntimeError, "share failed"),
        ):
            self.agent._recover_duplicate_growth_prior_operand(ordered_operands, evidence_items)
        recovery_owner.assert_not_called()
        normalizer.assert_not_called()
        self.assertEqual(ordered_operands, before_operands)

    def test_current_source_dependency_numeric_result_predicate_pins_sources_laziness_and_exceptions(self) -> None:
        nested = {"preserve": True}

        class SkippedRow(dict):
            def get(self, key, default=None):
                if key == "calculation_result":
                    raise AssertionError("unsupported row inspected")
                return super().get(key, default)

        skipped = SkippedRow(operation_family="lookup", nested=nested)
        row_operand = {
            "evidence_id": "row-evidence",
            "source_row_id": "row-source",
            "source_row_ids": ["row-list"],
            "dependency_resolved": True,
            "nested": nested,
        }
        result_operand = {
            "evidence_id": "result-evidence",
            "source_row_id": "result-source",
            "source_row_ids": ["result-list"],
            "nested": nested,
        }
        calculation_result = {
            "source_row_ids": ["result-top"],
            "calculation_operands": [result_operand, "skip"],
            "nested": nested,
        }
        row = {
            "operation_family": "ratio",
            "source_row_ids": ["row-top"],
            "calculation_operands": [row_operand, None],
            "calculation_result": calculation_result,
            "nested": nested,
        }
        ordered_results = [skipped, row]
        before_results = deepcopy(ordered_results)
        operation_owner = Mock(side_effect=["lookup", "ratio"])
        clean_owner = Mock(return_value=[])
        with (
            patch.object(financial_aggregate_projection, "aggregate_result_operation_family", operation_owner),
            patch.object(financial_aggregate_projection, "_clean_source_row_ids", clean_owner),
        ):
            self.assertTrue(
                financial_aggregate_projection.aggregate_results_include_dependency_numeric_result(ordered_results)
            )
        self.assertEqual([call.args[0] for call in operation_owner.call_args_list], ordered_results)
        clean_owner.assert_called_once()
        source_payload = clean_owner.call_args.args[0]
        self.assertEqual(source_payload[0], ["result-top"])
        self.assertEqual(source_payload[1], ["row-top"])
        self.assertEqual(
            source_payload[2],
            [["row-evidence", "row-source", ["row-list"]]],
        )
        self.assertEqual(
            source_payload[3],
            [["result-evidence", "result-source", ["result-list"]]],
        )
        self.assertEqual(ordered_results, before_results)
        self.assertIs(row["nested"], nested)
        self.assertIs(calculation_result["nested"], nested)
        self.assertIs(row_operand["nested"], nested)

        class DependencyAccessBomb(dict):
            def get(self, key, default=None):
                if key == "dependency_resolved":
                    raise AssertionError("dependency flag accessed after task source")
                return super().get(key, default)

        task_operand = DependencyAccessBomb(
            evidence_id="task-evidence",
            source_row_id="task-source",
            source_row_ids=[],
        )
        task_row = {"calculation_operands": [task_operand]}
        with (
            patch.object(financial_aggregate_projection, "aggregate_result_operation_family", return_value="sum"),
            patch.object(
                financial_aggregate_projection,
                "_clean_source_row_ids",
                return_value=["task_output:upstream"],
            ),
        ):
            self.assertTrue(
                financial_aggregate_projection.aggregate_results_include_dependency_numeric_result([task_row])
            )

        with (
            patch.object(financial_aggregate_projection, "aggregate_result_operation_family", return_value="difference"),
            patch.object(financial_aggregate_projection, "_clean_source_row_ids", return_value=[]),
        ):
            self.assertFalse(
                financial_aggregate_projection.aggregate_results_include_dependency_numeric_result(
                    [{"calculation_operands": [{"dependency_resolved": False}]}]
                )
            )

        clean_owner = Mock()
        with (
            patch.object(
                financial_aggregate_projection,
                "aggregate_result_operation_family",
                side_effect=RuntimeError("operation failed"),
            ),
            patch.object(financial_aggregate_projection, "_clean_source_row_ids", clean_owner),
            self.assertRaisesRegex(RuntimeError, "operation failed"),
        ):
            financial_aggregate_projection.aggregate_results_include_dependency_numeric_result([row])
        clean_owner.assert_not_called()

        with (
            patch.object(financial_aggregate_projection, "aggregate_result_operation_family", return_value="ratio"),
            patch.object(
                financial_aggregate_projection,
                "_clean_source_row_ids",
                side_effect=RuntimeError("source cleanup failed"),
            ),
            self.assertRaisesRegex(RuntimeError, "source cleanup failed"),
        ):
            financial_aggregate_projection.aggregate_results_include_dependency_numeric_result([row])

    def test_current_source_source_task_realignment_predicate_pins_scan_laziness_and_exceptions(self) -> None:
        nested = {"preserve": True}
        events = []

        class AlignmentFalseRow(dict):
            def get(self, key, default=None):
                events.append(("get", key))
                return super().get(key, default)

        false_row = AlignmentFalseRow(aligned_from_source_task_slots=False, nested=nested)
        unsupported_row = {"aligned_from_source_task_slots": True, "nested": nested}
        supported_row = {"aligned_from_source_task_slots": "yes", "nested": nested}
        ordered_results = [false_row, unsupported_row, supported_row]
        before_results = deepcopy(ordered_results)
        operation_owner = Mock(side_effect=lambda row: events.append(("operation", row)) or (
            "lookup" if row is unsupported_row else "growth_rate"
        ))
        with patch.object(financial_aggregate_projection, "aggregate_result_operation_family", operation_owner):
            self.assertTrue(
                financial_aggregate_projection.aggregate_results_include_source_task_slot_realignment(ordered_results)
            )
        self.assertEqual(
            [call.args[0] for call in operation_owner.call_args_list],
            [unsupported_row, supported_row],
        )
        self.assertEqual(ordered_results, before_results)
        self.assertIs(false_row["nested"], nested)
        self.assertIs(supported_row["nested"], nested)

        with patch.object(financial_aggregate_projection, "aggregate_result_operation_family", return_value="lookup"):
            self.assertFalse(
                financial_aggregate_projection.aggregate_results_include_source_task_slot_realignment(
                    [{"aligned_from_source_task_slots": True}]
                )
            )

        class AlignmentBoolBomb:
            def __bool__(self):
                raise RuntimeError("alignment truthiness failed")

        operation_owner = Mock()
        with (
            patch.object(financial_aggregate_projection, "aggregate_result_operation_family", operation_owner),
            self.assertRaisesRegex(RuntimeError, "alignment truthiness failed"),
        ):
            financial_aggregate_projection.aggregate_results_include_source_task_slot_realignment(
                [{"aligned_from_source_task_slots": AlignmentBoolBomb()}]
            )
        operation_owner.assert_not_called()

        with (
            patch.object(
                financial_aggregate_projection,
                "aggregate_result_operation_family",
                side_effect=RuntimeError("family failed"),
            ),
            self.assertRaisesRegex(RuntimeError, "family failed"),
        ):
            financial_aggregate_projection.aggregate_results_include_source_task_slot_realignment(
                [{"aligned_from_source_task_slots": True}]
            )

    def test_current_source_narrative_reuse_predicates_pin_substrings_numeric_kinds_and_exceptions(self) -> None:
        nested = {"preserve": True}

        class RowsBomb:
            def __iter__(self):
                raise AssertionError("rows iterated for blank answer")

        self.assertFalse(financial_aggregate_projection.answer_reuses_narrative_summary_text("", RowsBomb()))

        class AnswerAccessBomb(dict):
            def get(self, key, default=None):
                if key == "answer":
                    raise AssertionError("non-narrative answer accessed")
                return super().get(key, default)

        ignored = AnswerAccessBomb(metric_family="other", nested=nested)
        short = {"metric_family": "narrative_summary", "answer": "short 1", "nested": nested}
        no_digit = {
            "metric_family": "narrative_summary",
            "answer": "a sufficiently long narrative without a numeric surface",
            "nested": nested,
        }
        narrative = {
            "metric_family": "narrative_summary",
            "answer": "Revenue increased to 120 units during the reported period.",
            "nested": nested,
        }
        ordered_results = [ignored, short, no_digit, narrative]
        before_results = deepcopy(ordered_results)
        with patch.object(
            financial_aggregate_projection,
            "row_is_narrative_summary",
            side_effect=lambda row: row.get("metric_family") == "narrative_summary",
        ) as narrative_owner:
            self.assertTrue(
                financial_aggregate_projection.answer_reuses_narrative_summary_text(
                    "Prefix Revenue increased to 120 units during the reported period. Suffix",
                    ordered_results,
                )
            )
            self.assertTrue(
                financial_aggregate_projection.answer_reuses_narrative_summary_text(
                    "Revenue increased to 120 units",
                    [narrative],
                )
            )
        self.assertEqual(narrative_owner.call_count, 5)
        self.assertEqual(ordered_results, before_results)
        self.assertIs(narrative["nested"], nested)

        with patch.object(
            financial_aggregate_projection,
            "row_is_narrative_summary",
            return_value=True,
        ):
            self.assertFalse(
                financial_aggregate_projection.answer_reuses_narrative_summary_text(
                    "different 999 narrative material",
                    [narrative],
                )
            )

        reuse_owner = Mock(return_value=False)
        extractor = Mock(side_effect=AssertionError("numeric extraction accessed"))
        with (
            patch.object(financial_aggregate_projection, "answer_reuses_narrative_summary_text", reuse_owner),
            patch.object(financial_aggregate_projection, "extract_numeric_surface_candidates", extractor),
        ):
            self.assertFalse(
                financial_aggregate_projection.answer_reuses_numeric_narrative_summary_text("answer", ordered_results)
            )
        reuse_owner.assert_called_once_with("answer", ordered_results)
        extractor.assert_not_called()

        candidates = [
            {"kind": "percent", "value": 10},
            {"kind": "number", "value": 120},
            {"kind": "currency", "value": 90},
        ]
        with (
            patch.object(financial_aggregate_projection, "answer_reuses_narrative_summary_text", return_value=True),
            patch.object(
                financial_aggregate_projection,
                "extract_numeric_surface_candidates",
                return_value=candidates,
            ) as extractor,
        ):
            self.assertTrue(
                financial_aggregate_projection.answer_reuses_numeric_narrative_summary_text("120 and 90 plus 10%", ordered_results)
            )
        extractor.assert_called_once_with("120 and 90 plus 10%")
        self.assertIs(candidates[0], extractor.return_value[0])

        with (
            patch.object(financial_aggregate_projection, "answer_reuses_narrative_summary_text", return_value=True),
            patch.object(
                financial_aggregate_projection,
                "extract_numeric_surface_candidates",
                return_value=[{"kind": "percent"}, {"kind": "number"}],
            ),
        ):
            self.assertFalse(
                financial_aggregate_projection.answer_reuses_numeric_narrative_summary_text("120 and 10%", ordered_results)
            )

        row_owner = Mock()
        with (
            patch.object(
                financial_aggregate_projection,
                "_normalise_spaces",
                side_effect=RuntimeError("normalizer failed"),
            ),
            patch.object(financial_aggregate_projection, "row_is_narrative_summary", row_owner),
            self.assertRaisesRegex(RuntimeError, "normalizer failed"),
        ):
            financial_aggregate_projection.answer_reuses_narrative_summary_text("answer", ordered_results)
        row_owner.assert_not_called()

        with (
            patch.object(financial_aggregate_projection, "answer_reuses_narrative_summary_text", return_value=True),
            patch.object(
                financial_aggregate_projection,
                "extract_numeric_surface_candidates",
                side_effect=RuntimeError("extractor failed"),
            ),
            self.assertRaisesRegex(RuntimeError, "extractor failed"),
        ):
            financial_aggregate_projection.answer_reuses_numeric_narrative_summary_text("answer", ordered_results)

    def test_current_source_result_support_bindings_pin_defs_calls_plan_dag_and_baseline(self) -> None:
        import json
        from pathlib import Path

        module_sources = {
            "graph": inspect.getsource(financial_graph_calculation),
            "owner": inspect.getsource(financial_aggregate_projection),
        }
        module_trees = {name: ast.parse(source) for name, source in module_sources.items()}
        current_targets = {
            "dependency": "aggregate_results_include_dependency_numeric_result",
            "realignment": "aggregate_results_include_source_task_slot_realignment",
            "narrative": "answer_reuses_narrative_summary_text",
            "numeric": "answer_reuses_numeric_narrative_summary_text",
        }
        retired_targets = {f"_{name}" for name in current_targets.values()}
        definitions = {}
        all_definition_names = set()
        calls = {key: [] for key in current_targets}
        try_depths = {key: [] for key in current_targets}
        noncall_refs = []

        class BindingVisitor(ast.NodeVisitor):
            def __init__(self, module_name):
                self.module_name = module_name
                self.function_stack = []
                self.try_depth = 0
                self.call_depth = 0

            def visit_FunctionDef(self, node):
                all_definition_names.add(node.name)
                if node.name in current_targets.values():
                    definitions[node.name] = (self.module_name, node)
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
                receiver = ast.unparse(node.func.value) if isinstance(node.func, ast.Attribute) else ""
                for key, target in current_targets.items():
                    if called_name == target:
                        calls[key].append(
                            (
                                self.module_name,
                                tuple(self.function_stack),
                                receiver,
                                tuple(ast.unparse(arg) for arg in node.args),
                                tuple((kw.arg, ast.unparse(kw.value)) for kw in node.keywords),
                            )
                        )
                        try_depths[key].append(self.try_depth)
                self.call_depth += 1
                self.generic_visit(node)
                self.call_depth -= 1

            def visit_Attribute(self, node):
                if node.attr in current_targets.values() and self.call_depth == 0:
                    noncall_refs.append((self.module_name, node.attr, node.lineno))
                self.generic_visit(node)

            def visit_Name(self, node):
                if node.id in current_targets.values() and self.call_depth == 0:
                    noncall_refs.append((self.module_name, node.id, node.lineno))
                self.generic_visit(node)

        for module_name, tree in module_trees.items():
            BindingVisitor(module_name).visit(tree)

        self.assertEqual(
            {
                name: (module_name, node.end_lineno - node.lineno + 1)
                for name, (module_name, node) in definitions.items()
            },
            {
                current_targets["dependency"]: ("owner", 39),
                current_targets["realignment"]: ("owner", 10),
                current_targets["narrative"]: ("owner", 16),
                current_targets["numeric"]: ("owner", 12),
            },
        )
        self.assertTrue(retired_targets.isdisjoint(all_definition_names))
        self.assertEqual(
            {key: len(entries) for key, entries in calls.items()},
            {"dependency": 1, "realignment": 1, "narrative": 3, "numeric": 7},
        )
        self.assertEqual(
            try_depths,
            {
                "dependency": [0],
                "realignment": [0],
                "narrative": [0, 0, 0],
                "numeric": [0] * 7,
            },
        )
        self.assertEqual(noncall_refs, [])
        self.assertTrue(
            all(
                receiver == ""
                for entries in calls.values()
                for _module, _stack, receiver, _args, _kwargs in entries
            )
        )
        self.assertEqual(
            Counter(stack[-1] for _module, stack, *_rest in calls["dependency"]),
            Counter({"_preferred_aggregate_fallback_answer": 1}),
        )
        self.assertEqual(
            Counter(stack[-1] for _module, stack, *_rest in calls["realignment"]),
            Counter({"_aggregate_calculation_subtasks": 1}),
        )
        self.assertEqual(
            Counter(stack[-1] for _module, stack, *_rest in calls["narrative"]),
            Counter(
                {
                    current_targets["numeric"]: 1,
                    "_apply_initial_aggregate_answer_composition": 1,
                    "_apply_final_narrative_repair_pipeline": 1,
                }
            ),
        )
        self.assertEqual(
            Counter(stack[-1] for _module, stack, *_rest in calls["numeric"]),
            Counter(
                {
                    "_refresh_numeric_answer_preserving_narrative_context": 1,
                    "_apply_initial_aggregate_answer_composition": 1,
                    "_apply_final_narrative_repair_pipeline": 1,
                    "_aggregate_calculation_subtasks": 4,
                }
            ),
        )
        self.assertTrue(
            all(
                not kwargs and len(args) == expected_arg_count
                for key, entries in calls.items()
                for expected_arg_count in [1 if key in {"dependency", "realignment"} else 2]
                for _module, _stack, _receiver, args, kwargs in entries
            )
        )

        selected_names = set(current_targets.values())
        distribution = {}
        for key, entries in calls.items():
            external = sum(not selected_names.intersection(stack) for _module, stack, *_rest in entries)
            distribution[key] = (external, len(entries) - external)
        self.assertEqual(
            distribution,
            {"dependency": (1, 0), "realignment": (1, 0), "narrative": (2, 1), "numeric": (7, 0)},
        )
        self.assertEqual(
            (
                sum(external for external, _local in distribution.values()),
                sum(local for _external, local in distribution.values()),
            ),
            (11, 1),
        )

        def imported_modules(tree):
            modules = set()
            for node in tree.body:
                if isinstance(node, ast.ImportFrom) and node.module:
                    modules.add(node.module)
                elif isinstance(node, ast.Import):
                    modules.update(alias.name for alias in node.names)
            return modules

        owner_imports = imported_modules(module_trees["owner"])
        self.assertIn("src.agent.financial_numeric_surface", owner_imports)
        self.assertIn("src.agent.financial_runtime_normalization", owner_imports)
        graph_owner_bindings = {
            alias.asname or alias.name
            for node in module_trees["graph"].body
            if isinstance(node, ast.ImportFrom)
            and node.module == "src.agent.financial_aggregate_projection"
            for alias in node.names
        }
        self.assertTrue(set(current_targets.values()).issubset(graph_owner_bindings))
        numeric_tree = ast.parse(Path("src/agent/financial_numeric_surface.py").read_text(encoding="utf-8"))
        normalization_tree = ast.parse(
            Path("src/agent/financial_runtime_normalization.py").read_text(encoding="utf-8")
        )
        self.assertNotIn("src.agent.financial_aggregate_projection", imported_modules(numeric_tree))
        self.assertNotIn("src.agent.financial_aggregate_projection", imported_modules(normalization_tree))

        baseline = json.loads(
            (Path(__file__).parent / "fixtures" / "runtime_domain_terms_baseline.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(len(baseline["records"]), 217)
        selected_lines_by_path = {
            "src/agent/financial_aggregate_projection.py": {
                line
                for module_name, node in definitions.values()
                if module_name == "owner"
                for line in range(node.lineno, node.end_lineno + 1)
            },
            "src/agent/financial_graph_calculation.py": {
                line
                for module_name, node in definitions.values()
                if module_name == "graph"
                for line in range(node.lineno, node.end_lineno + 1)
            },
        }
        self.assertEqual(
            [
                record
                for record in baseline["records"]
                if selected_lines_by_path.get(record.get("path"), set()).intersection(
                    record.get("first_lines") or []
                )
            ],
            [],
        )

    def test_current_source_result_support_callers_pin_fallback_and_alignment_gate(self) -> None:
        ordered_results = [{"task_id": "task_1"}]
        events = []
        dependency_owner = Mock(
            side_effect=lambda rows: events.append(("dependency", rows)) or True
        )
        with (
            patch.object(self.agent, "_unresolved_structured_numeric_gap", return_value=False),
            patch.object(self.agent, "_supported_aggregate_subtask_answer", return_value=""),
            patch.object(self.agent, "_preferred_conflicting_growth_narrative_answer", return_value={}),
            patch.object(
                financial_graph_calculation,
                "row_is_narrative_summary",
                side_effect=lambda row: events.append(("narrative", row)) or False,
            ),
            patch.object(
                self.agent,
                "_preferred_complete_numeric_answer",
                side_effect=lambda rows: events.append(("complete", rows)) or "complete 100",
            ),
            patch.object(
                financial_graph_calculation,
                "aggregate_results_include_dependency_numeric_result",
                dependency_owner,
            ),
        ):
            self.assertEqual(
                self.agent._preferred_aggregate_fallback_answer(ordered_results, "default"),
                "complete 100",
            )
        dependency_owner.assert_called_once_with(ordered_results)
        self.assertIs(dependency_owner.call_args.args[0], ordered_results)
        self.assertEqual([event[0] for event in events], ["narrative", "complete", "dependency"])

        with (
            patch.object(self.agent, "_unresolved_structured_numeric_gap", return_value=False),
            patch.object(self.agent, "_supported_aggregate_subtask_answer", return_value=""),
            patch.object(self.agent, "_preferred_conflicting_growth_narrative_answer", return_value={}),
            patch.object(financial_graph_calculation, "row_is_narrative_summary", return_value=False),
            patch.object(self.agent, "_preferred_complete_numeric_answer", return_value="complete 100"),
            patch.object(
                financial_graph_calculation,
                "aggregate_results_include_dependency_numeric_result",
                side_effect=RuntimeError("dependency predicate failed"),
            ),
            self.assertRaisesRegex(RuntimeError, "dependency predicate failed"),
        ):
            self.agent._preferred_aggregate_fallback_answer(ordered_results, "default")

        base_row = {"task_id": "base"}
        aligned_row = {"task_id": "aligned"}
        base_rows = [base_row]
        aligned_rows = [aligned_row]
        state = {
            "query": "",
            "seed_retrieved_docs": [],
            "retrieved_docs": [],
            "plan_loop_count": 0,
        }
        prepared = financial_graph_calculation._PreparedAggregateState(
            base_rows, "base answer", "", "", False, False, False
        )
        evidence_state = financial_graph_calculation._AggregateEvidenceState(
            base_rows, [], "base answer", "base answer", "", ""
        )
        composition_state = financial_graph_calculation.AggregateCompositionState(
            "base answer", [], None, True, "", ""
        )
        feedback_state = financial_graph_calculation._AggregateFeedbackState(
            "base answer", "", "", [], {}, False, ""
        )
        projection = {
            "calculation_result": {},
            "calculation_operands": [],
            "calculation_plan": {},
        }

        alignment_events = []

        def run_alignment(predicate_owner, replacement_owner):
            alignment_events.clear()
            with (
                patch.object(self.agent, "_prepare_initial_aggregate_state", return_value=prepared),
                patch.object(self.agent, "_infer_planner_feedback_from_answer_slots", return_value=""),
                patch.object(self.agent, "_collect_initial_aggregate_evidence_state", return_value=evidence_state),
                patch.object(self.agent, "_rebuild_aggregate_projection", return_value=projection),
                patch.object(self.agent, "_runtime_evidence_rows_with_context_docs", return_value=[]),
                patch.object(
                    self.agent,
                    "_apply_period_context_realignment_to_aggregate",
                    side_effect=lambda **kwargs: kwargs["aggregate_state"],
                ),
                patch.object(financial_graph_calculation, "narrative_context_sentence_from_evidence", return_value=""),
                patch.object(self.agent, "_apply_initial_aggregate_answer_composition", return_value=(composition_state, "")),
                patch.object(self.agent, "_preserve_source_visible_query_terms", side_effect=lambda answer, **_kwargs: answer),
                patch.object(
                    self.agent,
                    "_preserve_policy_required_context_in_narrative_results",
                    side_effect=lambda rows, **_kwargs: rows,
                ),
                patch.object(self.agent, "_resolve_aggregate_feedback_state", return_value=feedback_state),
                patch.object(financial_graph_calculation, "_aggregate_selected_claim_ids", return_value=[]),
                patch.object(
                    self.agent,
                    "_align_lookup_results_with_dependency_projection",
                    side_effect=lambda rows, _state, _projection: alignment_events.append(("align", rows)) or aligned_rows,
                ),
                patch.object(
                    financial_graph_calculation,
                    "aggregate_results_include_source_task_slot_realignment",
                    side_effect=lambda rows: alignment_events.append(("predicate", rows)) or predicate_owner(rows),
                ),
                patch.object(
                    self.agent,
                    "_replace_mutable_aggregate_results",
                    side_effect=lambda *args, **kwargs: alignment_events.append(("replace", args, kwargs))
                    or replacement_owner(*args, **kwargs),
                ),
            ):
                self.agent._aggregate_calculation_subtasks(state)

        predicate_owner = Mock(return_value=True)
        replacement_owner = Mock(side_effect=RuntimeError("stop after alignment"))
        with self.assertRaisesRegex(RuntimeError, "stop after alignment"):
            run_alignment(predicate_owner, replacement_owner)
        predicate_owner.assert_called_once_with(aligned_rows)
        self.assertIs(predicate_owner.call_args.args[0], aligned_rows)
        replacement_owner.assert_called_once()
        self.assertIs(replacement_owner.call_args.args[2], aligned_rows)
        self.assertTrue(replacement_owner.call_args.kwargs["refresh_numeric_answer"])
        self.assertEqual([event[0] for event in alignment_events], ["align", "predicate", "replace"])

        replacement_owner = Mock()
        with self.assertRaisesRegex(RuntimeError, "realignment predicate failed"):
            run_alignment(
                Mock(side_effect=RuntimeError("realignment predicate failed")),
                replacement_owner,
            )
        replacement_owner.assert_not_called()

    def test_current_source_narrative_reuse_callers_pin_initial_and_final_stop(self) -> None:
        ordered_results = [{"task_id": "task_1"}]
        state = {"query": "why", "report_scope": {}}

        class InitialAgent:
            pass

        initial_agent = InitialAgent()
        initial_agent._answer_matches_supported_aggregate_subtask = Mock(return_value=False)
        numeric_reuse_owner = Mock(return_value=True)
        numeric_completion_owner = Mock(
            side_effect=AssertionError("numeric completion accessed")
        )
        include_owner = Mock(side_effect=RuntimeError("stop after numeric reuse"))
        with (
            patch.object(
                financial_graph_calculation.calculation_rendering,
                "coerce_sign_aware_subtraction_answer",
                side_effect=lambda answer, **_kwargs: answer,
            ),
            patch.object(
                financial_graph_calculation.calculation_rendering,
                "compose_slot_based_difference_answer",
                return_value="",
            ),
            patch.object(financial_graph_calculation, "query_requests_explanatory_context", return_value=True),
            patch.object(
                financial_graph_calculation,
                "answer_reuses_numeric_narrative_summary_text",
                numeric_reuse_owner,
            ),
            patch.object(financial_graph_calculation, "include_narrative_context_if_needed", include_owner),
            patch.object(
                financial_graph_calculation,
                "ensure_complete_growth_numeric_answer",
                numeric_completion_owner,
            ),
            self.assertRaisesRegex(RuntimeError, "stop after numeric reuse"),
        ):
            financial_graph_calculation.FinancialAgentCalculationMixin._apply_initial_aggregate_answer_composition(
                initial_agent,
                state,
                ordered_results=ordered_results,
                preliminary_projection={"calculation_result": {}},
                aggregate_evidence_items=[],
                narrative_docs=[],
                narrative_context="context",
                final_answer="answer 120 and 90",
                supported_aggregate_answer="",
                complete_numeric_answer="",
                has_narrative_summary=True,
                has_growth_rate_result=False,
                numeric_answer_locked=False,
                planner_feedback="",
                deterministic_feedback="",
            )
        numeric_reuse_owner.assert_called_once_with("answer 120 and 90", ordered_results)
        self.assertIs(numeric_reuse_owner.call_args.args[1], ordered_results)
        numeric_completion_owner.assert_not_called()

        include_owner = Mock()
        numeric_reuse_failure = Mock(side_effect=RuntimeError("numeric reuse failed"))
        with (
            patch.object(
                financial_graph_calculation.calculation_rendering,
                "coerce_sign_aware_subtraction_answer",
                side_effect=lambda answer, **_kwargs: answer,
            ),
            patch.object(
                financial_graph_calculation.calculation_rendering,
                "compose_slot_based_difference_answer",
                return_value="",
            ),
            patch.object(financial_graph_calculation, "query_requests_explanatory_context", return_value=True),
            patch.object(
                financial_graph_calculation,
                "answer_reuses_numeric_narrative_summary_text",
                numeric_reuse_failure,
            ),
            patch.object(financial_graph_calculation, "include_narrative_context_if_needed", include_owner),
            patch.object(
                financial_graph_calculation,
                "ensure_complete_growth_numeric_answer",
                numeric_completion_owner,
            ),
            self.assertRaisesRegex(RuntimeError, "numeric reuse failed"),
        ):
            financial_graph_calculation.FinancialAgentCalculationMixin._apply_initial_aggregate_answer_composition(
                initial_agent,
                state,
                ordered_results=ordered_results,
                preliminary_projection={"calculation_result": {}},
                aggregate_evidence_items=[],
                narrative_docs=[],
                narrative_context="context",
                final_answer="answer 120 and 90",
                supported_aggregate_answer="",
                complete_numeric_answer="",
                has_narrative_summary=True,
                has_growth_rate_result=False,
                numeric_answer_locked=False,
                planner_feedback="",
                deterministic_feedback="",
            )
        include_owner.assert_not_called()

        nested = {"preserve": True}
        evidence_items = [{"evidence_id": "ev_1", "nested": nested}]
        mutable_state = financial_graph_calculation._AggregateMutableState(
            financial_graph_calculation._AggregateSynthesisState(
                ordered_results,
                {"calculation_result": {}},
                "source answer 120",
                [],
            ),
            evidence_items,
        )

        class FinalAgent:
            pass

        def configured_final_agent(replace_owner):
            agent = FinalAgent()
            agent._preserve_policy_required_realized_context = Mock(
                side_effect=lambda answer, **_kwargs: answer
            )
            agent._replace_mutable_aggregate_answer = replace_owner
            agent._append_retrieved_narrative_evidence_for_final_answer = Mock(
                side_effect=lambda current, **_kwargs: (current, [])
            )
            agent._apply_period_context_realignment_to_aggregate = Mock(
                side_effect=lambda **kwargs: kwargs["aggregate_state"]
            )
            agent._enforce_source_stated_growth_answer_contract = Mock(
                side_effect=lambda answer, _rows, **_kwargs: answer
            )
            agent._unresolved_structured_numeric_gap = Mock(return_value=True)
            agent._prune_nonfocus_numeric_narrative_sentences = Mock()
            agent._answer_satisfies_growth_narrative_intent = Mock()
            agent._answer_matches_supported_aggregate_subtask = Mock()
            agent._promote_and_align_aggregate_results = Mock()
            return agent

        narrative_reuse_owner = Mock(return_value=True)
        append_passthrough = Mock(side_effect=lambda current, **_kwargs: current)

        def replace_until_safe(current_state, *, candidate_answer, **_kwargs):
            if candidate_answer == "safe partial":
                raise RuntimeError("stop after safe adoption")
            return current_state, False

        replace_owner = Mock(side_effect=replace_until_safe)
        final_agent = configured_final_agent(replace_owner)
        safe_owner = Mock(return_value="safe partial")
        with (
            patch.object(
                financial_graph_calculation,
                "preserve_retrieved_narrative_source_surface",
                side_effect=lambda answer, _items: answer,
            ),
            patch.object(financial_graph_calculation, "safe_partial_answer_for_numeric_gap", safe_owner),
            patch.object(
                financial_graph_calculation,
                "answer_reuses_narrative_summary_text",
                narrative_reuse_owner,
            ),
            patch.object(
                financial_graph_calculation,
                "append_operand_evidence_for_final_answer",
                append_passthrough,
            ),
            self.assertRaisesRegex(RuntimeError, "stop after safe adoption"),
        ):
            financial_graph_calculation.FinancialAgentCalculationMixin._apply_final_narrative_repair_pipeline(
                final_agent,
                state,
                mutable_state=mutable_state,
                narrative_docs=[],
                has_narrative_summary=False,
                has_growth_rate_result=False,
                deterministic_feedback="",
            )
        narrative_reuse_owner.assert_called_once_with("source answer 120", ordered_results)
        self.assertIs(narrative_reuse_owner.call_args.args[1], ordered_results)
        safe_owner.assert_called_once_with(ordered_results)
        self.assertEqual(
            [call.kwargs["candidate_answer"] for call in replace_owner.call_args_list],
            ["source answer 120", "source answer 120", "safe partial"],
        )

        safe_owner = Mock()
        replace_owner = Mock(side_effect=lambda current_state, **_kwargs: (current_state, False))
        final_agent = configured_final_agent(replace_owner)
        narrative_reuse_failure = Mock(side_effect=RuntimeError("narrative reuse failed"))
        with (
            patch.object(
                financial_graph_calculation,
                "preserve_retrieved_narrative_source_surface",
                side_effect=lambda answer, _items: answer,
            ),
            patch.object(financial_graph_calculation, "safe_partial_answer_for_numeric_gap", safe_owner),
            patch.object(
                financial_graph_calculation,
                "answer_reuses_narrative_summary_text",
                narrative_reuse_failure,
            ),
            patch.object(
                financial_graph_calculation,
                "append_operand_evidence_for_final_answer",
                append_passthrough,
            ),
            self.assertRaisesRegex(RuntimeError, "narrative reuse failed"),
        ):
            financial_graph_calculation.FinancialAgentCalculationMixin._apply_final_narrative_repair_pipeline(
                final_agent,
                state,
                mutable_state=mutable_state,
                narrative_docs=[],
                has_narrative_summary=False,
                has_growth_rate_result=False,
                deterministic_feedback="",
            )
        safe_owner.assert_not_called()
        self.assertEqual(
            [call.kwargs["candidate_answer"] for call in replace_owner.call_args_list],
            ["source answer 120", "source answer 120"],
        )


    def test_material_growth_display_values_matrix(self) -> None:
        nested = {"preserve": True}
        primary = {"role": "primary", "nested": nested}
        current = {"role": "current", "nested": nested}
        prior = {"role": "prior", "nested": nested}
        row = {
            "calculation_result": {
                "rendered_value": "",
                "answer_slots": {
                    "primary_value": primary,
                    "current_value": current,
                    "prior_value": prior,
                },
            },
            "nested": nested,
        }
        ordered_results = [row]
        evidence_items = [{"evidence_id": "ev_1", "nested": nested}]
        before_row = deepcopy(row)
        before_results = deepcopy(ordered_results)
        before_evidence = deepcopy(evidence_items)
        events = []

        def display(slot, results):
            events.append(("display", slot["role"], slot, results))
            return {"prior": "PRIOR", "current": "CURRENT", "primary": "CURRENT"}[slot["role"]]

        def share(current_slot, prior_slot, results):
            events.append(("share", current_slot, prior_slot, results))
            return False

        recovery_owner = Mock()
        with (
            patch.object(financial_aggregate_projection, "growth_slot_display_value", side_effect=display) as display_owner,
            patch.object(financial_aggregate_projection, "growth_slots_share_material", side_effect=share) as share_owner,
            patch.object(
                financial_aggregate_projection,
                "recover_growth_prior_material_from_evidence",
                recovery_owner,
            ),
        ):
            values = financial_aggregate_projection.growth_required_display_values(
                row, ordered_results, evidence_items
            )

        self.assertEqual(values, ["CURRENT", "PRIOR"])
        self.assertEqual([event[:2] for event in events], [
            ("display", "prior"),
            ("share", {"role": "current", "nested": nested}),
            ("display", "current"),
            ("display", "primary"),
        ])
        self.assertEqual(display_owner.call_count, 3)
        self.assertIs(display_owner.call_args_list[0].args[1], ordered_results)
        self.assertIs(share_owner.call_args.args[2], ordered_results)
        for index, original in enumerate((prior, current, primary)):
            copied = display_owner.call_args_list[index].args[0]
            self.assertIsNot(copied, original)
            self.assertIs(copied["nested"], nested)
        recovery_owner.assert_not_called()
        self.assertEqual(row, before_row)
        self.assertEqual(ordered_results, before_results)
        self.assertEqual(evidence_items, before_evidence)
        self.assertIs(row["nested"], nested)
        self.assertIs(evidence_items[0]["nested"], nested)

        rendered_row = deepcopy(row)
        rendered_row["calculation_result"]["rendered_value"] = "GROWTH"
        with (
            patch.object(
                financial_aggregate_projection,
                "growth_slot_display_value",
                side_effect=["PRIOR", "CURRENT"],
            ) as display_owner,
            patch.object(financial_aggregate_projection, "growth_slots_share_material", return_value=True),
            patch.object(
                financial_aggregate_projection,
                "recover_growth_prior_material_from_evidence",
                return_value={"display": "RECOVERED"},
            ) as recovery_owner,
        ):
            self.assertEqual(
                financial_aggregate_projection.growth_required_display_values(
                    rendered_row, ordered_results, evidence_items
                ),
                ["CURRENT", "RECOVERED", "GROWTH"],
            )
        self.assertEqual(display_owner.call_count, 2)
        self.assertIs(recovery_owner.call_args.kwargs["evidence_items"], evidence_items)

        normalizer_owner = Mock(side_effect=RuntimeError("normalizer failed"))
        with (
            patch.object(financial_aggregate_projection, "growth_slot_display_value", side_effect=["PRIOR", "CURRENT", "PRIMARY"]),
            patch.object(financial_aggregate_projection, "growth_slots_share_material", return_value=False),
            patch.object(financial_aggregate_projection, "_normalise_spaces", normalizer_owner),
            self.assertRaisesRegex(RuntimeError, "normalizer failed"),
        ):
            financial_aggregate_projection.growth_required_display_values(row, ordered_results, evidence_items)
        normalizer_owner.assert_called_once_with("PRIMARY")

    def test_current_source_material_strong_growth_trace_matrix(self) -> None:
        nested = {"preserve": True}

        def growth_row(kind, *, current_source="source:current", prior_source="source:prior", material=True):
            return {
                "kind": kind,
                "calculation_result": {
                    "answer_slots": {
                        "primary_value": {"role": "primary", "raw_value": "10%" if material else "", "nested": nested},
                        "current_value": {
                            "role": "current",
                            "raw_value": "200" if material else "",
                            "normalized_value": 200,
                            "source_row_id": current_source,
                            "nested": nested,
                        },
                        "prior_value": {
                            "role": "prior",
                            "raw_value": "100" if material else "",
                            "normalized_value": 100,
                            "source_row_id": prior_source,
                            "nested": nested,
                        },
                    }
                },
                "nested": nested,
            }

        class CalculationBomb(dict):
            def get(self, key, default=None):
                if key == "calculation_result":
                    raise AssertionError("calculation result accessed")
                return super().get(key, default)

        non_growth = CalculationBomb(kind="non_growth")
        conflict = CalculationBomb(kind="conflict")
        incomplete = growth_row("incomplete", material=False)
        task_output = growth_row("task_output", current_source="task_output:current")
        complete = growth_row("complete")
        ordered_results = [non_growth, conflict, incomplete, task_output, complete]
        before_results = deepcopy(ordered_results)
        material_args = []
        source_args = []

        def family(row):
            return "growth_rate" if row.get("kind") != "non_growth" else "lookup"

        def conflicting(row):
            return row.get("kind") == "conflict"

        def material(slot):
            material_args.append(slot)
            return bool(slot.get("raw_value"))

        def clean(values):
            source_args.append(values)
            flattened = []
            for value in values:
                if isinstance(value, (list, tuple)):
                    flattened.extend(str(item) for item in value if item)
                elif value:
                    flattened.append(str(value))
            return flattened

        with (
            patch.object(financial_aggregate_projection, "aggregate_result_operation_family", side_effect=family) as family_owner,
            patch.object(financial_aggregate_projection, "growth_row_has_conflicting_periods", side_effect=conflicting) as conflict_owner,
            patch.object(financial_aggregate_projection, "answer_slot_has_material", side_effect=material) as material_owner,
            patch.object(financial_aggregate_projection, "_clean_source_row_ids", side_effect=clean) as clean_owner,
        ):
            self.assertTrue(financial_aggregate_projection.has_strong_growth_trace_for_answer_refresh(ordered_results))

        self.assertEqual(family_owner.call_count, 5)
        self.assertEqual(conflict_owner.call_count, 4)
        self.assertEqual(material_owner.call_count, 7)
        self.assertEqual(clean_owner.call_count, 4)
        self.assertEqual(len(source_args), 4)
        self.assertTrue(all(isinstance(item, list) for item in source_args))
        first_primary = material_args[0]
        self.assertIsNot(first_primary, incomplete["calculation_result"]["answer_slots"]["primary_value"])
        self.assertIs(first_primary["nested"], nested)
        self.assertEqual(ordered_results, before_results)
        self.assertIs(complete["nested"], nested)

        with (
            patch.object(financial_aggregate_projection, "aggregate_result_operation_family", return_value="growth_rate"),
            patch.object(financial_aggregate_projection, "growth_row_has_conflicting_periods", return_value=False),
            patch.object(financial_aggregate_projection, "answer_slot_has_material", return_value=True),
            patch.object(
                financial_aggregate_projection,
                "_clean_source_row_ids",
                side_effect=RuntimeError("source cleanup failed"),
            ),
            self.assertRaisesRegex(RuntimeError, "source cleanup failed"),
        ):
            financial_aggregate_projection.has_strong_growth_trace_for_answer_refresh([complete])

        conflict_owner = Mock()
        with (
            patch.object(
                financial_aggregate_projection,
                "aggregate_result_operation_family",
                side_effect=RuntimeError("family failed"),
            ),
            patch.object(financial_aggregate_projection, "growth_row_has_conflicting_periods", conflict_owner),
            self.assertRaisesRegex(RuntimeError, "family failed"),
        ):
            financial_aggregate_projection.has_strong_growth_trace_for_answer_refresh([complete])
        conflict_owner.assert_not_called()

    def test_current_source_material_lookup_primary_slots_matrix(self) -> None:
        nested = {"preserve": True}

        class FalsyRows:
            def __bool__(self):
                return False

            def __iter__(self):
                raise AssertionError("falsy rows iterated")

        family_owner = Mock(side_effect=AssertionError("family accessed"))
        with patch.object(financial_aggregate_projection, "aggregate_result_operation_family", family_owner):
            self.assertEqual(financial_aggregate_projection.aggregate_lookup_primary_slots(FalsyRows()), [])
        family_owner.assert_not_called()

        class ResultBomb(dict):
            def get(self, key, default=None):
                if key in {"calculation_result", "answer_slots"}:
                    raise AssertionError("non-lookup result accessed")
                return super().get(key, default)

        non_lookup = ResultBomb(family="ratio")
        missing = {
            "family": "lookup",
            "answer_slots": {"primary_value": {"raw_value": "", "nested": nested}},
        }
        first_slot = {"raw_value": "100", "nested": nested}
        second_slot = {"raw_value": "200", "nested": nested}
        first = {
            "family": "lookup",
            "calculation_result": {"answer_slots": {"primary_value": first_slot}},
        }
        second = {"family": "lookup", "answer_slots": {"primary_value": second_slot}}
        opaque_row = object()
        rows = [opaque_row, non_lookup, missing, first, second]
        before_rows = deepcopy(rows)
        material_args = []

        def family(row):
            return row.get("family")

        def material(slot):
            material_args.append(slot)
            return bool(slot.get("raw_value"))

        with (
            patch.object(financial_aggregate_projection, "aggregate_result_operation_family", side_effect=family) as family_owner,
            patch.object(financial_aggregate_projection, "answer_slot_has_material", side_effect=material) as material_owner,
        ):
            slots = financial_aggregate_projection.aggregate_lookup_primary_slots(rows)

        self.assertEqual(slots, [first_slot, second_slot])
        self.assertEqual(family_owner.call_count, 4)
        self.assertEqual(material_owner.call_count, 3)
        self.assertIsNot(slots[0], first_slot)
        self.assertIsNot(slots[1], second_slot)
        self.assertIs(slots[0]["nested"], nested)
        self.assertIs(slots[1]["nested"], nested)
        self.assertIs(rows[0], opaque_row)
        self.assertEqual(rows[1:], before_rows[1:])

        with (
            patch.object(financial_aggregate_projection, "aggregate_result_operation_family", return_value="lookup"),
            patch.object(
                financial_aggregate_projection,
                "answer_slot_has_material",
                side_effect=RuntimeError("material failed"),
            ),
            self.assertRaisesRegex(RuntimeError, "material failed"),
        ):
            financial_aggregate_projection.aggregate_lookup_primary_slots([first])

    def test_current_source_material_ratio_value_and_conflict_matrix(self) -> None:
        nested = {"preserve": True}
        row = {
            "result_value": "row-result",
            "calculation_result": {
                "result_value": "result",
                "answer_slots": {
                    "primary_value": {
                        "normalized_value": "normalized",
                        "raw_value": "raw",
                        "nested": nested,
                    }
                },
            },
            "nested": nested,
        }
        before_row = deepcopy(row)
        seen_values = []

        def coerce(value):
            seen_values.append(value)
            return 12.5 if value == "normalized" else None

        with patch.object(financial_aggregate_projection, "coerce_slot_numeric", side_effect=coerce):
            self.assertEqual(financial_aggregate_projection._ratio_result_numeric_value(row), 12.5)
        self.assertEqual(seen_values, ["result", "normalized"])
        self.assertEqual(row, before_row)
        self.assertIs(row["nested"], nested)

        with patch.object(
            financial_aggregate_projection,
            "coerce_slot_numeric",
            return_value=None,
        ) as coerce_owner:
            self.assertIsNone(financial_aggregate_projection._ratio_result_numeric_value(row))
        self.assertEqual(
            [call.args[0] for call in coerce_owner.call_args_list],
            ["result", "normalized", "raw", "row-result"],
        )

        later_coerce = Mock(side_effect=RuntimeError("coerce failed"))
        with (
            patch.object(
                financial_aggregate_projection,
                "coerce_slot_numeric",
                later_coerce,
            ),
            self.assertRaisesRegex(RuntimeError, "coerce failed"),
        ):
            financial_aggregate_projection._ratio_result_numeric_value(row)
        later_coerce.assert_called_once_with("result")

        task = {"task_id": "ratio_task", "metric_label": "Margin", "nested": nested}
        existing = {
            "task_id": "ratio_task",
            "metric_label": "Margin",
            "operation_family": "ratio",
            "status": "ok",
            "artifact_backed_complete_result": True,
            "calculation_result": {"result_value": 100.0, "nested": nested},
            "nested": nested,
        }
        context_evidence = [{"evidence_id": "ev_ratio", "nested": nested}]
        before_existing = deepcopy(existing)
        before_task = deepcopy(task)
        before_evidence = deepcopy(context_evidence)

        with (
            patch.object(financial_aggregate_projection, "aggregate_result_operation_family", return_value="ratio"),
            patch.object(financial_aggregate_projection, "_ratio_result_numeric_value", return_value=100.0),
            patch.object(
                financial_aggregate_projection,
                "ratio_components_are_complete",
            ) as complete_owner,
            patch.object(financial_aggregate_projection, "ratio_context_has_metric_surface") as surface_owner,
        ):
            self.assertFalse(
                financial_aggregate_projection.retrieved_ratio_projection_conflicts_with_existing_complete_result(
                    [existing], task, result_value=100.05, context_evidence=context_evidence
                )
            )
        complete_owner.assert_not_called()
        surface_owner.assert_not_called()

        for surface_result, expected in ((False, True), (True, False)):
            with (
                self.subTest(surface_result=surface_result),
                patch.object(financial_aggregate_projection, "aggregate_result_operation_family", return_value="ratio"),
                patch.object(financial_aggregate_projection, "_ratio_result_numeric_value", return_value=100.0),
                patch.object(financial_aggregate_projection, "ratio_context_has_metric_surface", return_value=surface_result) as surface_owner,
            ):
                self.assertEqual(
                    financial_aggregate_projection.retrieved_ratio_projection_conflicts_with_existing_complete_result(
                        [existing], task, result_value=100.051, context_evidence=context_evidence
                    ),
                    expected,
                )
            surface_owner.assert_called_once_with(context_evidence, task)

        incomplete = deepcopy(existing)
        incomplete["artifact_backed_complete_result"] = False
        with (
            patch.object(financial_aggregate_projection, "aggregate_result_operation_family", return_value="ratio"),
            patch.object(financial_aggregate_projection, "_ratio_result_numeric_value", return_value=100.0),
            patch.object(
                financial_aggregate_projection,
                "ratio_components_are_complete",
                return_value=False,
            ) as complete_owner,
            patch.object(financial_aggregate_projection, "ratio_context_has_metric_surface") as surface_owner,
        ):
            self.assertFalse(
                financial_aggregate_projection.retrieved_ratio_projection_conflicts_with_existing_complete_result(
                    [incomplete], task, result_value=90.0, context_evidence=context_evidence
                )
            )
        complete_owner.assert_called_once()
        surface_owner.assert_not_called()

        with (
            patch.object(financial_aggregate_projection, "aggregate_result_operation_family", return_value="ratio"),
            patch.object(financial_aggregate_projection, "_ratio_result_numeric_value", return_value=0.0),
            patch.object(financial_aggregate_projection, "ratio_context_has_metric_surface", return_value=False) as surface_owner,
        ):
            self.assertFalse(
                financial_aggregate_projection.retrieved_ratio_projection_conflicts_with_existing_complete_result(
                    [existing], task, result_value=5e-4, context_evidence=context_evidence
                )
            )
            self.assertTrue(
                financial_aggregate_projection.retrieved_ratio_projection_conflicts_with_existing_complete_result(
                    [existing], task, result_value=5.01e-4, context_evidence=context_evidence
                )
            )
        surface_owner.assert_called_once_with(context_evidence, task)

        class LaterRow(dict):
            def get(self, _key, _default=None):
                raise AssertionError("later row accessed")

        with (
            patch.object(financial_aggregate_projection, "aggregate_result_operation_family", return_value="ratio"),
            patch.object(financial_aggregate_projection, "_ratio_result_numeric_value", return_value=100.0),
            patch.object(
                financial_aggregate_projection,
                "ratio_context_has_metric_surface",
                side_effect=RuntimeError("surface failed"),
            ),
            self.assertRaisesRegex(RuntimeError, "surface failed"),
        ):
            financial_aggregate_projection.retrieved_ratio_projection_conflicts_with_existing_complete_result(
                [existing, LaterRow()], task, result_value=90.0, context_evidence=context_evidence
            )
        self.assertEqual(existing, before_existing)
        self.assertEqual(task, before_task)
        self.assertEqual(context_evidence, before_evidence)
        self.assertIs(existing["nested"], nested)
        self.assertIs(context_evidence[0]["nested"], nested)

    def test_current_source_material_inspection_static_bindings_distribution_and_dag(self) -> None:
        import json
        from pathlib import Path

        paths = {
            "graph": Path("src/agent/financial_graph_calculation.py"),
            "owner": Path("src/agent/financial_aggregate_projection.py"),
        }
        trees = {name: ast.parse(path.read_text(encoding="utf-8")) for name, path in paths.items()}
        targets = {
            "growth": "growth_required_display_values",
            "strong": "has_strong_growth_trace_for_answer_refresh",
            "lookup": "aggregate_lookup_primary_slots",
            "ratio_value": "_ratio_result_numeric_value",
            "ratio_conflict": "retrieved_ratio_projection_conflicts_with_existing_complete_result",
        }
        definitions = {}
        calls = {key: [] for key in targets}
        noncall_refs = []
        try_depths = {key: [] for key in targets}

        class Visitor(ast.NodeVisitor):
            def __init__(self, module_name):
                self.module_name = module_name
                self.stack = []
                self.call_depth = 0
                self.try_depth = 0

            def visit_FunctionDef(self, node):
                if node.name in targets.values():
                    definitions[node.name] = (self.module_name, node)
                self.stack.append(node.name)
                self.generic_visit(node)
                self.stack.pop()

            visit_AsyncFunctionDef = visit_FunctionDef

            def visit_Try(self, node):
                self.try_depth += 1
                self.generic_visit(node)
                self.try_depth -= 1

            def visit_Call(self, node):
                name = ""
                receiver = ""
                if isinstance(node.func, ast.Attribute):
                    name = node.func.attr
                    receiver = ast.unparse(node.func.value)
                elif isinstance(node.func, ast.Name):
                    name = node.func.id
                for key, target in targets.items():
                    if name == target:
                        calls[key].append(
                            (
                                self.module_name,
                                tuple(self.stack),
                                receiver,
                                tuple(ast.unparse(arg) for arg in node.args),
                                tuple((item.arg, ast.unparse(item.value)) for item in node.keywords),
                            )
                        )
                        try_depths[key].append(self.try_depth)
                self.call_depth += 1
                self.generic_visit(node)
                self.call_depth -= 1

            def visit_Attribute(self, node):
                if node.attr in targets.values() and self.call_depth == 0:
                    noncall_refs.append((self.module_name, node.attr, node.lineno))
                self.generic_visit(node)

            def visit_Name(self, node):
                if node.id in targets.values() and self.call_depth == 0:
                    noncall_refs.append((self.module_name, node.id, node.lineno))

        for module_name, tree in trees.items():
            Visitor(module_name).visit(tree)

        self.assertEqual(
            {name: (module, node.end_lineno - node.lineno + 1) for name, (module, node) in definitions.items()},
            {
                targets["growth"]: ("owner", 31),
                targets["strong"]: ("owner", 32),
                targets["lookup"]: ("owner", 11),
                targets["ratio_value"]: ("owner", 13),
                targets["ratio_conflict"]: ("owner", 43),
            },
        )
        self.assertEqual({key: len(value) for key, value in calls.items()}, {
            "growth": 11,
            "strong": 3,
            "lookup": 1,
            "ratio_value": 1,
            "ratio_conflict": 1,
        })
        self.assertTrue(all(depth == 0 for values in try_depths.values() for depth in values))
        self.assertEqual(noncall_refs, [])
        self.assertTrue(
            all(receiver == "" for entries in calls.values() for _module, _stack, receiver, _args, _kwargs in entries)
        )
        self.assertEqual(
            Counter(stack[-1] for _module, stack, _receiver, _args, _kwargs in calls["growth"]),
            Counter({
                "ensure_complete_growth_numeric_answer": 1,
                "_final_growth_answer_without_untraced_numeric_sentences": 1,
                "_enforce_source_stated_growth_answer_contract": 1,
                "strip_untraced_numeric_material_from_growth_narrative_sentence": 1,
                "growth_answer_has_untraced_numeric_material": 1,
                "narrative_summary_conflicts_with_growth_trace": 1,
                "growth_narrative_numeric_incompatible_with_trace": 1,
                "_is_growth_supported_sentence": 1,
                "_compose_growth_narrative_answer": 1,
                "_answer_satisfies_growth_narrative_intent": 1,
                "_prune_irrelevant_growth_narrative_sentences": 1,
            }),
        )
        self.assertEqual(
            Counter(stack[-1] for _module, stack, _receiver, _args, _kwargs in calls["strong"]),
            Counter({"_answer_matches_supported_aggregate_subtask": 1, "_aggregate_calculation_subtasks": 2}),
        )
        self.assertEqual(
            [stack[-1] for _module, stack, _receiver, _args, _kwargs in calls["lookup"]],
            ["_sync_aggregate_arithmetic_subtask_surfaces"],
        )
        self.assertEqual(
            [stack[-1] for _module, stack, _receiver, _args, _kwargs in calls["ratio_value"]],
            [targets["ratio_conflict"]],
        )
        self.assertEqual(
            [stack[-1] for _module, stack, _receiver, _args, _kwargs in calls["ratio_conflict"]],
            ["_append_ratio_result_from_retrieved_context"],
        )
        selected_names = set(targets.values())
        distribution = {}
        for key, entries in calls.items():
            external = sum(not selected_names.intersection(stack) for _module, stack, *_rest in entries)
            distribution[key] = (external, len(entries) - external)
        self.assertEqual(
            distribution,
            {"growth": (11, 0), "strong": (3, 0), "lookup": (1, 0), "ratio_value": (0, 1), "ratio_conflict": (1, 0)},
        )
        self.assertEqual(
            (sum(item[0] for item in distribution.values()), sum(item[1] for item in distribution.values())),
            (16, 1),
        )
        self.assertEqual(
            tuple(definitions[targets[key]][1].end_lineno - definitions[targets[key]][1].lineno + 1 for key in targets),
            (31, 32, 11, 13, 43),
        )

        module_paths = list(Path("src/agent").glob("*.py")) + list(Path("src/config").glob("*.py"))
        import_graph = {}
        for path in module_paths:
            module_name = ".".join(path.with_suffix("").parts)
            imported = set()
            for node in ast.parse(path.read_text(encoding="utf-8-sig")).body:
                if isinstance(node, ast.ImportFrom) and node.module:
                    imported.add(node.module)
                elif isinstance(node, ast.Import):
                    imported.update(alias.name for alias in node.names)
            import_graph[module_name] = imported

        def reaches(start, target):
            pending = [start]
            seen = set()
            while pending:
                current = pending.pop()
                if current == target:
                    return True
                if current in seen:
                    continue
                seen.add(current)
                pending.extend(import_graph.get(current, ()))
            return False

        owner_module = "src.agent.financial_aggregate_projection"
        for dependency in (
            "src.agent.financial_answer_projection",
            "src.agent.financial_answer_slots",
            "src.agent.financial_operand_resolution",
        ):
            self.assertFalse(reaches(dependency, owner_module), dependency)

        baseline = json.loads(
            (Path("tests") / "fixtures" / "runtime_domain_terms_baseline.json").read_text(encoding="utf-8")
        )
        self.assertEqual(len(baseline["records"]), 217)
        selected_lines = set()
        for module_name, node in definitions.values():
            if module_name == "owner":
                selected_lines.update(range(node.lineno, node.end_lineno + 1))
        self.assertEqual(
            [
                record
                for record in baseline["records"]
                if record.get("path") == "src/agent/financial_aggregate_projection.py"
                and selected_lines.intersection(record.get("first_lines") or [])
            ],
            [],
        )

    def test_current_source_material_growth_callers_pin_args_adoption_and_stop(self) -> None:
        row = {"task_id": "growth", "nested": {"preserve": True}}
        ordered_results = [row]
        evidence_items = [{"evidence_id": "ev_growth"}]
        before_results = deepcopy(ordered_results)
        before_evidence = deepcopy(evidence_items)

        compose_owner = Mock(return_value="complete 10 200 100")
        required_owner = Mock(return_value=["10", "200", "100"])
        untraced_owner = Mock(return_value=False)
        with (
            patch.object(financial_aggregate_projection, "aggregate_result_operation_family", return_value="growth_rate"),
            patch.object(financial_aggregate_projection, "compose_complete_growth_numeric_answer", compose_owner),
            patch.object(financial_aggregate_projection, "growth_required_display_values", required_owner),
            patch.object(financial_aggregate_projection, "growth_row_has_conflicting_periods", return_value=False),
            patch.object(financial_aggregate_projection, "growth_answer_has_untraced_numeric_sentence", untraced_owner),
        ):
            answer = financial_aggregate_projection.ensure_complete_growth_numeric_answer(
                "complete 10 200 100",
                ordered_results,
                evidence_items=evidence_items,
            )
        self.assertEqual(answer, "complete 10 200 100")
        required_owner.assert_called_once_with(row, ordered_results, evidence_items)
        self.assertIs(required_owner.call_args.args[0], row)
        self.assertIs(required_owner.call_args.args[1], ordered_results)
        self.assertIs(required_owner.call_args.args[2], evidence_items)
        untraced_owner.assert_called_once_with(
            "complete 10 200 100", "complete 10 200 100", ["10", "200", "100"]
        )

        downstream_owner = Mock()
        failing_required_owner = Mock(side_effect=RuntimeError("required failed"))
        with (
            patch.object(financial_aggregate_projection, "aggregate_result_operation_family", return_value="growth_rate"),
            patch.object(financial_aggregate_projection, "compose_complete_growth_numeric_answer", compose_owner),
            patch.object(financial_aggregate_projection, "growth_required_display_values", failing_required_owner),
            patch.object(financial_aggregate_projection, "growth_row_has_conflicting_periods", return_value=False),
            patch.object(financial_aggregate_projection, "growth_answer_has_untraced_numeric_sentence", downstream_owner),
            self.assertRaisesRegex(RuntimeError, "required failed"),
        ):
            financial_aggregate_projection.ensure_complete_growth_numeric_answer(
                "answer",
                ordered_results,
                evidence_items=evidence_items,
            )
        downstream_owner.assert_not_called()

        class GrowthAgent:
            pass

        refresh_agent = GrowthAgent()
        refresh_agent._supported_aggregate_subtask_answer = Mock(return_value="value 10")
        strong_owner = Mock(return_value=True)
        material_owner = Mock(return_value=False)
        with (
            patch.object(financial_graph_calculation, "has_strong_growth_trace_for_answer_refresh", strong_owner),
            patch.object(
                financial_graph_calculation,
                "growth_answer_has_untraced_numeric_material",
                material_owner,
            ),
        ):
            self.assertTrue(
                financial_graph_calculation.FinancialAgentCalculationMixin._answer_matches_supported_aggregate_subtask(
                    refresh_agent,
                    "value 10",
                    ordered_results,
                )
            )
        strong_owner.assert_called_once_with(ordered_results)
        self.assertIs(strong_owner.call_args.args[0], ordered_results)
        material_owner.assert_called_once_with("value 10", ordered_results)

        failing_strong_owner = Mock(side_effect=RuntimeError("strong failed"))
        material_owner.reset_mock()
        with (
            patch.object(financial_graph_calculation, "has_strong_growth_trace_for_answer_refresh", failing_strong_owner),
            self.assertRaisesRegex(RuntimeError, "strong failed"),
        ):
                financial_graph_calculation.FinancialAgentCalculationMixin._answer_matches_supported_aggregate_subtask(
                    refresh_agent,
                    "value 10",
                    ordered_results,
                )
        material_owner.assert_not_called()
        self.assertEqual(ordered_results, before_results)
        self.assertEqual(evidence_items, before_evidence)

    def test_current_source_material_sync_and_ratio_callers_pin_args_adoption_and_stop(self) -> None:
        from types import SimpleNamespace

        nested = {"preserve": True}
        projection_row = {
            "task_id": "lookup_task",
            "operation_family": "lookup",
            "answer": "lookup 1",
            "calculation_result": {"rendered_value": "1", "nested": nested},
            "nested": nested,
        }
        ordered_results = [projection_row]
        aggregate_projection = {
            "calculation_result": {"subtask_results": [projection_row]},
            "calculation_plan": {},
            "nested": nested,
        }
        before_results = deepcopy(ordered_results)
        before_projection = deepcopy(aggregate_projection)

        class SyncAgent:
            pass

        sync_agent = SyncAgent()
        sync_agent._aggregate_result_operation_family = Mock(
            side_effect=lambda row: row.get("operation_family")
        )
        lookup_slots = [{"raw_value": "1", "nested": nested}]
        lookup_owner = Mock(return_value=lookup_slots)
        component_inputs = []

        def sync_surface(payload):
            return SimpleNamespace(projection_row={**payload.projection_row, "answer": payload.answer})

        def sync_components(payload):
            component_inputs.append(payload)
            return SimpleNamespace(projection_row=payload.projection_row)

        with (
            patch.object(financial_graph_calculation, "aggregate_lookup_primary_slots", lookup_owner),
            patch.object(financial_graph_calculation, "answer_covers_numeric_answer", return_value=False),
            patch.object(
                financial_graph_calculation,
                "select_aggregate_projection_answer_sentence",
                return_value="synced 2",
            ),
            patch.object(financial_graph_calculation, "subtask_numeric_answers_conflict", return_value=True),
            patch.object(financial_graph_calculation, "extract_numeric_surface_candidates", return_value=["2"]),
            patch.object(financial_graph_calculation, "aggregate_projection_rendered_value", return_value="2"),
            patch.object(
                financial_graph_calculation,
                "synchronize_aggregate_projection_row_surface",
                side_effect=sync_surface,
            ),
            patch.object(
                financial_graph_calculation,
                "synchronize_aggregate_arithmetic_components",
                side_effect=sync_components,
            ),
        ):
            synced_results, synced_projection = (
                financial_graph_calculation.FinancialAgentCalculationMixin._sync_aggregate_arithmetic_subtask_surfaces(
                    sync_agent,
                    ordered_results,
                    aggregate_projection,
                    "final 2",
                )
            )
        lookup_owner.assert_called_once()
        projection_rows_arg = lookup_owner.call_args.args[0]
        self.assertIsNot(projection_rows_arg, ordered_results)
        self.assertEqual(projection_rows_arg[0]["answer"], "synced 2")
        self.assertEqual(synced_results[0]["answer"], "synced 2")
        self.assertEqual(synced_projection["calculation_result"]["subtask_results"][0]["answer"], "synced 2")
        self.assertEqual(len(component_inputs), 1)
        self.assertIs(component_inputs[0].lookup_slots, lookup_slots)
        self.assertEqual(ordered_results, before_results)
        self.assertEqual(aggregate_projection, before_projection)
        self.assertIs(projection_row["nested"], nested)

        component_owner = Mock()
        failing_lookup_owner = Mock(side_effect=RuntimeError("lookup failed"))
        with (
            patch.object(financial_graph_calculation, "aggregate_lookup_primary_slots", failing_lookup_owner),
            patch.object(financial_graph_calculation, "answer_covers_numeric_answer", return_value=False),
            patch.object(financial_graph_calculation, "select_aggregate_projection_answer_sentence", return_value="synced 2"),
            patch.object(financial_graph_calculation, "subtask_numeric_answers_conflict", return_value=True),
            patch.object(financial_graph_calculation, "extract_numeric_surface_candidates", return_value=["2"]),
            patch.object(financial_graph_calculation, "aggregate_projection_rendered_value", return_value="2"),
            patch.object(financial_graph_calculation, "synchronize_aggregate_projection_row_surface", side_effect=sync_surface),
            patch.object(financial_graph_calculation, "synchronize_aggregate_arithmetic_components", component_owner),
            self.assertRaisesRegex(RuntimeError, "lookup failed"),
        ):
            financial_graph_calculation.FinancialAgentCalculationMixin._sync_aggregate_arithmetic_subtask_surfaces(
                sync_agent, ordered_results, aggregate_projection, "final 2"
            )
        component_owner.assert_not_called()

        context_rows = [
            {
                "matched_operand_role": "numerator_1",
                "label": "Numerator",
                "normalized_value": 100.0,
                "raw_value": "100",
                "raw_unit": "KRW",
                "evidence_id": "ev_num",
                "source_row_id": "ev_num",
                "nested": nested,
            },
            {
                "matched_operand_role": "denominator_1",
                "label": "Denominator",
                "normalized_value": 1000.0,
                "raw_value": "1000",
                "raw_unit": "KRW",
                "evidence_id": "ev_den",
                "source_row_id": "ev_den",
                "nested": nested,
            },
        ]
        context_evidence = [
            {"evidence_id": "ev_num", "claim": "Numerator 100", "nested": nested},
            {"evidence_id": "ev_den", "claim": "Denominator 1000", "nested": nested},
        ]
        task = {
            "task_id": "ratio_task",
            "metric_label": "Margin",
            "operation_family": "ratio",
            "required_operands": [
                {"role": "numerator_1", "label": "Numerator"},
                {"role": "denominator_1", "label": "Denominator"},
            ],
            "nested": nested,
        }
        state = {
            "query": "ratio",
            "topic": "Margin",
            "calc_subtasks": [task],
            "retrieved_docs": [],
            "seed_retrieved_docs": [],
            "nested": nested,
        }
        before_state = deepcopy(state)
        before_context_rows = deepcopy(context_rows)
        before_context_evidence = deepcopy(context_evidence)

        class RatioAgent:
            pass

        ratio_agent = RatioAgent()
        ratio_agent._aggregate_result_operation_family = Mock(return_value="lookup")
        ratio_agent._ratio_operand_context_evidence_from_docs = Mock(return_value=context_evidence)
        ratio_agent._build_complete_ratio_operands_from_coherent_context = Mock(return_value=context_rows)
        conflict_owner = Mock(return_value=False)
        compact_owner = Mock(return_value="10.00%")
        ratio_agent._compact_ratio_answer = compact_owner
        projection = {
            "result_value": 10.0,
            "result_unit": "%",
            "normalized_unit": "%",
            "rendered_value": "10.00%",
        }
        with (
            patch.object(financial_graph_calculation, "ratio_result_rows_from_task_artifacts", return_value=[]),
            patch.object(
                financial_graph_calculation,
                "retrieved_ratio_projection_conflicts_with_existing_complete_result",
                conflict_owner,
            ),
            patch.object(financial_graph_calculation, "collect_retrieval_context_docs", return_value=["doc"]),
            patch.object(financial_graph_calculation, "_missing_required_operands", return_value=False),
            patch.object(financial_graph_calculation, "_ratio_operand_rows_collapse_to_same_slot", return_value=False),
            patch.object(financial_graph_calculation.calculation_rendering, "ratio_result_projection", return_value=projection),
        ):
            appended = financial_graph_calculation.FinancialAgentCalculationMixin._append_ratio_result_from_retrieved_context(
                ratio_agent, [], state
            )
        self.assertEqual(len(appended), 1)
        self.assertTrue(appended[0]["recovered_from_retrieved_ratio_context"])
        conflict_owner.assert_called_once()
        existing_arg, task_arg = conflict_owner.call_args.args
        self.assertEqual(existing_arg, [])
        self.assertIsNot(task_arg, task)
        self.assertEqual(task_arg, task)
        self.assertEqual(conflict_owner.call_args.kwargs["result_value"], 10.0)
        projected_evidence_arg = conflict_owner.call_args.kwargs["context_evidence"]
        self.assertEqual(projected_evidence_arg, context_evidence)
        self.assertIsNot(projected_evidence_arg, context_evidence)
        compact_owner.assert_called_once()
        self.assertEqual(state, before_state)
        self.assertEqual(context_rows, before_context_rows)
        self.assertEqual(context_evidence, before_context_evidence)
        self.assertIs(state["nested"], nested)

        failing_conflict_owner = Mock(side_effect=RuntimeError("conflict failed"))
        compact_owner.reset_mock()
        with (
            patch.object(financial_graph_calculation, "ratio_result_rows_from_task_artifacts", return_value=[]),
            patch.object(
                financial_graph_calculation,
                "retrieved_ratio_projection_conflicts_with_existing_complete_result",
                failing_conflict_owner,
            ),
            patch.object(financial_graph_calculation, "collect_retrieval_context_docs", return_value=["doc"]),
            patch.object(financial_graph_calculation, "_missing_required_operands", return_value=False),
            patch.object(financial_graph_calculation, "_ratio_operand_rows_collapse_to_same_slot", return_value=False),
            patch.object(financial_graph_calculation.calculation_rendering, "ratio_result_projection", return_value=projection),
            self.assertRaisesRegex(RuntimeError, "conflict failed"),
        ):
            financial_graph_calculation.FinancialAgentCalculationMixin._append_ratio_result_from_retrieved_context(
                ratio_agent, [], state
            )
        compact_owner.assert_not_called()
        self.assertEqual(state, before_state)
        self.assertEqual(context_rows, before_context_rows)
        self.assertEqual(context_evidence, before_context_evidence)

    def test_current_source_growth_numeric_renderer_gates_values_recovery_and_exceptions(self) -> None:
        nested = {"preserve": True}

        class CopyBomb:
            def keys(self):
                raise RuntimeError("copy failed")

            def __getitem__(self, _key):
                raise AssertionError("copy item accessed")

        family_after_copy = Mock()
        with (
            patch.object(financial_aggregate_projection, "aggregate_result_operation_family", family_after_copy),
            self.assertRaisesRegex(RuntimeError, "copy failed"),
        ):
            financial_aggregate_projection.compose_complete_growth_numeric_answer(
                {"calculation_result": CopyBomb()},
                [],
            )
        family_after_copy.assert_not_called()

        with (
            patch.object(financial_aggregate_projection, "aggregate_result_operation_family", family_after_copy),
            self.assertRaisesRegex(RuntimeError, "copy failed"),
        ):
            financial_aggregate_projection.compose_complete_growth_numeric_answer(
                {"calculation_result": {"answer_slots": CopyBomb()}},
                [],
            )
        family_after_copy.assert_not_called()

        class SlotCopyBomb:
            def keys(self):
                raise AssertionError("slot copied after non-growth gate")

        non_growth_row = {
            "calculation_result": {
                "answer_slots": {
                    "primary_value": SlotCopyBomb(),
                    "current_value": SlotCopyBomb(),
                    "prior_value": SlotCopyBomb(),
                }
            }
        }
        material_owner = Mock()
        display_owner = Mock()
        with (
            patch.object(financial_aggregate_projection, "aggregate_result_operation_family", return_value="lookup") as family_owner,
            patch.object(financial_aggregate_projection, "answer_slot_has_material", material_owner),
            patch.object(financial_aggregate_projection, "growth_slot_display_value", display_owner),
        ):
            self.assertEqual(
                financial_aggregate_projection.compose_complete_growth_numeric_answer(non_growth_row, [non_growth_row]),
                "",
            )
        family_owner.assert_called_once_with(non_growth_row)
        material_owner.assert_not_called()
        display_owner.assert_not_called()

        primary_nested = {"primary": nested}
        primary = {"rendered_value": "10%", "nested": primary_nested}
        current = {"label": "Metric", "period": "2024", "nested": nested}
        prior = {"period": "2023", "nested": nested}
        gated_row = {
            "calculation_result": {
                "rendered_value": "10%",
                "answer_slots": {
                    "primary_value": primary,
                    "current_value": current,
                    "prior_value": prior,
                },
            }
        }

        def no_material(slot):
            self.assertIsNot(slot, primary)
            self.assertIs(slot["nested"], primary_nested)
            return False

        with (
            patch.object(financial_aggregate_projection, "aggregate_result_operation_family", return_value="growth_rate"),
            patch.object(
                financial_aggregate_projection,
                "answer_slot_has_material",
                side_effect=no_material,
            ) as gated_material,
            patch.object(financial_aggregate_projection, "growth_slot_display_value", display_owner),
        ):
            self.assertEqual(
                financial_aggregate_projection.compose_complete_growth_numeric_answer(gated_row, [gated_row]),
                "",
            )
        gated_material.assert_called_once()
        display_owner.assert_not_called()

        slot_material_owner = Mock()
        with (
            patch.object(financial_aggregate_projection, "aggregate_result_operation_family", return_value="growth_rate"),
            patch.object(financial_aggregate_projection, "answer_slot_has_material", slot_material_owner),
            self.assertRaisesRegex(RuntimeError, "copy failed"),
        ):
            financial_aggregate_projection.compose_complete_growth_numeric_answer(
                {
                    "calculation_result": {
                        "answer_slots": {
                            "primary_value": CopyBomb(),
                            "current_value": {},
                            "prior_value": {},
                        }
                    }
                },
                [],
            )
        slot_material_owner.assert_not_called()

        class LabelStringBomb:
            def __str__(self):
                raise AssertionError("label accessed after missing display")

        missing_row = {
            "metric_label": LabelStringBomb(),
            "calculation_result": {
                "rendered_value": "10%",
                "answer_slots": {
                    "primary_value": {"rendered_value": "10%"},
                    "current_value": {"label": LabelStringBomb()},
                    "prior_value": {},
                },
            },
        }
        with (
            patch.object(financial_aggregate_projection, "aggregate_result_operation_family", return_value="growth_rate"),
            patch.object(financial_aggregate_projection, "answer_slot_has_material", return_value=True),
            patch.object(financial_aggregate_projection, "growth_slot_display_value", side_effect=["", "PRIOR"]),
            patch.object(financial_aggregate_projection, "growth_slots_share_material", return_value=False),
            patch.object(financial_aggregate_projection.calculation_rendering, "absolute_display_value", side_effect=str),
        ):
            self.assertEqual(
                financial_aggregate_projection.compose_complete_growth_numeric_answer(missing_row, [missing_row]),
                "",
            )

        row_slot_fallback = {
            "answer_slots": {
                "primary_value": {
                    "label": "Metric",
                    "rendered_value": "12%",
                    "normalized_value": 12,
                    "direction": "increase",
                },
                "current_value": {"period": "2024"},
                "prior_value": {"period": "2023"},
            },
            "calculation_result": {"rendered_value": ""},
        }
        fallback_policy = {
            "direction_words": {"increase": "UP", "decrease": "DOWN", "growth": "GROW"},
            "growth_direction_metric_terms": (),
            "period_year_suffix": "Y",
            "period_prefix_with_year_template": "[{period}]",
            "period_prefix_template": "[{period}]",
            "prior_phrase_with_value_template": "prior {period} {value}",
            "growth_numeric_sentence_template": (
                "{period_prefix} {metric_label}{topic_particle} {current_value} "
                "{prior_phrase} {growth_value} {direction_word}"
            ),
        }
        with (
            patch.object(financial_aggregate_projection, "aggregate_result_operation_family", return_value="growth_rate"),
            patch.object(financial_aggregate_projection, "answer_slot_has_material", return_value=True),
            patch.object(financial_aggregate_projection, "growth_slot_display_value", side_effect=["CURRENT", "PRIOR"]),
            patch.object(financial_aggregate_projection, "growth_slots_share_material", return_value=False),
            patch.object(financial_aggregate_projection.calculation_rendering, "absolute_display_value", side_effect=str),
            patch.object(financial_aggregate_projection, "CALCULATION_SLOT_POLICY", {"period_pattern": r"$^"}),
            patch.object(financial_aggregate_projection, "CALCULATION_NARRATIVE_POLICY", fallback_policy),
            patch.object(financial_aggregate_projection, "topic_particle", return_value="P"),
        ):
            fallback_answer = financial_aggregate_projection.compose_complete_growth_numeric_answer(
                row_slot_fallback,
                [row_slot_fallback],
            )
        self.assertEqual(fallback_answer, "[2024] MetricP CURRENT prior 2023Y PRIOR 12% UP")

        primary = {
            "role": "primary",
            "rendered_value": "PRIMARY-BOMB-SUPPRESSED",
            "normalized_value": 10,
            "direction": "increase",
            "nested": nested,
        }
        current = {"role": "current", "label": "Metric", "period": "2024", "nested": nested}
        prior = {"role": "prior", "period": "2023", "nested": nested}
        row = {
            "metric_label": "Fallback Metric",
            "calculation_result": {
                "rendered_value": "10%",
                "answer_slots": {
                    "primary_value": primary,
                    "current_value": current,
                    "prior_value": prior,
                },
            },
            "nested": nested,
        }
        ordered_results = [row]
        evidence_items = [{"evidence_id": "ev_1", "nested": nested}]
        before_row = deepcopy(row)
        before_results = deepcopy(ordered_results)
        before_evidence = deepcopy(evidence_items)
        events = []

        def family(prepared_row):
            events.append(("family", prepared_row))
            return "growth_rate"

        def material(slot):
            events.append(("material", slot))
            self.assertIsNot(slot, primary)
            self.assertIs(slot["nested"], nested)
            return True

        def display(slot, results):
            events.append(("display", slot["role"], slot, results))
            self.assertIs(results, ordered_results)
            return "CURRENT" if slot["role"] == "current" else "PRIOR"

        def share(current_slot, prior_slot, results):
            events.append(("share", current_slot, prior_slot, results))
            self.assertIs(results, ordered_results)
            return True

        def recover(*, current_slot, prior_slot, evidence_items):
            events.append(("recover", current_slot, prior_slot, evidence_items))
            self.assertIs(evidence_items, evidence_items_ref)
            return {"display": "RECOVERED", "period": "2022"}

        def absolute(value):
            events.append(("absolute", value))
            return str(value)

        evidence_items_ref = evidence_items
        policy = {
            "direction_words": {"increase": "UP", "decrease": "DOWN", "growth": "GROW"},
            "growth_direction_metric_terms": (),
            "period_year_suffix": "Y",
            "period_prefix_with_year_template": "[{period}]",
            "period_prefix_template": "[{period}]",
            "prior_phrase_with_value_template": "prior {period} {value}",
            "growth_numeric_sentence_template": (
                "{period_prefix} {metric_label}{topic_particle} {current_value} "
                "{prior_phrase} {growth_value} {direction_word}"
            ),
        }
        with (
            patch.object(financial_aggregate_projection, "aggregate_result_operation_family", side_effect=family),
            patch.object(financial_aggregate_projection, "answer_slot_has_material", side_effect=material),
            patch.object(financial_aggregate_projection, "growth_slot_display_value", side_effect=display),
            patch.object(financial_aggregate_projection, "growth_slots_share_material", side_effect=share),
            patch.object(
                financial_aggregate_projection,
                "recover_growth_prior_material_from_evidence",
                side_effect=recover,
            ),
            patch.object(
                financial_aggregate_projection.calculation_rendering,
                "absolute_display_value",
                side_effect=absolute,
            ),
            patch.object(financial_aggregate_projection, "CALCULATION_SLOT_POLICY", {"period_pattern": r"$^"}),
            patch.object(financial_aggregate_projection, "CALCULATION_NARRATIVE_POLICY", policy),
            patch.object(financial_aggregate_projection, "topic_particle", return_value="|P|"),
        ):
            answer = financial_aggregate_projection.compose_complete_growth_numeric_answer(
                row,
                ordered_results,
                evidence_items=evidence_items,
            )
        self.assertEqual(answer, "[2024] Metric|P| CURRENT prior 2022Y RECOVERED 10% UP")
        self.assertEqual(
            [event[0] for event in events],
            ["family", "material", "display", "absolute", "display", "absolute", "share", "recover", "absolute", "absolute"],
        )
        self.assertEqual(row, before_row)
        self.assertEqual(ordered_results, before_results)
        self.assertEqual(evidence_items, before_evidence)
        self.assertIs(row["nested"], nested)
        self.assertIs(evidence_items[0]["nested"], nested)

        downstream_share = Mock()
        downstream_recover = Mock()
        downstream_policy = Mock()
        with (
            patch.object(financial_aggregate_projection, "aggregate_result_operation_family", return_value="growth_rate"),
            patch.object(financial_aggregate_projection, "answer_slot_has_material", return_value=True),
            patch.object(
                financial_aggregate_projection,
                "growth_slot_display_value",
                side_effect=RuntimeError("display failed"),
            ),
            patch.object(financial_aggregate_projection, "growth_slots_share_material", downstream_share),
            patch.object(
                financial_aggregate_projection,
                "recover_growth_prior_material_from_evidence",
                downstream_recover,
            ),
            patch.object(financial_aggregate_projection, "CALCULATION_NARRATIVE_POLICY", downstream_policy),
            self.assertRaisesRegex(RuntimeError, "display failed"),
        ):
            financial_aggregate_projection.compose_complete_growth_numeric_answer(row, ordered_results, evidence_items)
        downstream_share.assert_not_called()
        downstream_recover.assert_not_called()
        downstream_policy.get.assert_not_called()
        self.assertEqual(row, before_row)
        self.assertEqual(evidence_items, before_evidence)

    def test_current_source_growth_numeric_renderer_label_period_direction_and_policy_matrix(self) -> None:
        nested = {"preserve": True}

        def render(*, primary, current, prior, row_label, policy, slot_policy=None):
            row = {
                "metric_label": row_label,
                "calculation_result": {
                    "rendered_value": "10%",
                    "answer_slots": {
                        "primary_value": primary,
                        "current_value": current,
                        "prior_value": prior,
                    },
                },
                "nested": nested,
            }
            ordered_results = [row]
            topic_owner = Mock(return_value="P")
            recovery_owner = Mock(side_effect=AssertionError("recovery accessed when material differs"))
            with (
                patch.object(financial_aggregate_projection, "aggregate_result_operation_family", return_value="growth_rate"),
                patch.object(financial_aggregate_projection, "answer_slot_has_material", return_value=True),
                patch.object(financial_aggregate_projection, "growth_slot_display_value", side_effect=["200", "100"]),
                patch.object(financial_aggregate_projection, "growth_slots_share_material", return_value=False),
                patch.object(
                    financial_aggregate_projection,
                    "recover_growth_prior_material_from_evidence",
                    recovery_owner,
                ),
                patch.object(
                    financial_aggregate_projection.calculation_rendering,
                    "absolute_display_value",
                    side_effect=lambda value: str(value),
                ),
                patch.object(
                    financial_aggregate_projection,
                    "CALCULATION_SLOT_POLICY",
                    slot_policy or {"period_pattern": r"$^"},
                ),
                patch.object(financial_aggregate_projection, "CALCULATION_NARRATIVE_POLICY", policy),
                patch.object(financial_aggregate_projection, "topic_particle", topic_owner),
            ):
                answer = financial_aggregate_projection.compose_complete_growth_numeric_answer(row, ordered_results)
            recovery_owner.assert_not_called()
            return answer, row, topic_owner

        base_policy = {
            "direction_words": {"increase": "UP", "decrease": "DOWN", "growth": "GROW"},
            "growth_direction_metric_terms": (),
            "period_year_suffix": "년",
            "period_prefix_with_year_template": "Y:{period}",
            "period_prefix_template": "P:{period}",
            "default_prior_period": "DEFAULT",
            "prior_phrase_with_value_template": "prior:{period}:{value}",
            "growth_numeric_sentence_template": (
                "{period_prefix}|{metric_label}|{topic_particle}|{current_value}|"
                "{prior_phrase}|{growth_value}|{direction_word}"
            ),
        }
        primary = {
            "label": "Primary Label",
            "rendered_value": "10%",
            "normalized_value": 10,
            "direction": "decrease",
            "nested": nested,
        }
        current = {"label": "2024 Revenue", "period": "2024", "nested": nested}
        prior = {"period": "2023", "nested": nested}
        answer, row, topic_owner = render(
            primary=primary,
            current=current,
            prior=prior,
            row_label="Row Label",
            policy=base_policy,
            slot_policy={"period_pattern": r"\b2024\b"},
        )
        self.assertEqual(answer, "Y:2024|Revenue|P|200|prior:2023년:100|10%|DOWN")
        topic_owner.assert_called_once_with("Revenue")
        self.assertIs(row["nested"], nested)

        growth_policy = {
            **base_policy,
            "growth_direction_metric_terms": ("GrowthTerm",),
        }
        answer, _, topic_owner = render(
            primary={
                "label": "GrowthTerm Metric",
                "rendered_value": "10%",
                "normalized_value": 5,
                "nested": nested,
            },
            current={"label": "", "period": "2024년", "nested": nested},
            prior={"period": "", "nested": nested},
            row_label="Row Label",
            policy=growth_policy,
        )
        self.assertEqual(answer, "P:2024년|GrowthTerm Metric|P|200|prior:DEFAULT:100|10%|GROW")
        topic_owner.assert_called_once_with("GrowthTerm Metric")

        answer, _, topic_owner = render(
            primary={
                "label": "",
                "period": "2025",
                "rendered_value": "10%",
                "normalized_value": 1,
                "direction_hint": "decrease",
                "nested": nested,
            },
            current={"label": "", "period": "", "nested": nested},
            prior={"period": "", "nested": nested},
            row_label="Row Fallback",
            policy=base_policy,
        )
        self.assertEqual(answer, "Y:2025|Row Fallback|P|200|prior:DEFAULT:100|10%|DOWN")
        topic_owner.assert_called_once_with("Row Fallback")

        class TypeFloat:
            def __float__(self):
                raise TypeError("soft type")

        class ValueFloat:
            def __float__(self):
                raise ValueError("soft value")

        for bad_value in (TypeFloat(), ValueFloat()):
            answer, _, _ = render(
                primary={
                    "label": "Fallback Metric",
                    "rendered_value": "-10%",
                    "normalized_value": bad_value,
                    "nested": nested,
                },
                current={"period": "", "nested": nested},
                prior={"period": "", "nested": nested},
                row_label="Row Label",
                policy=base_policy,
            )
            self.assertTrue(answer.endswith("|DOWN"), answer)

        class RuntimeFloat:
            def __float__(self):
                raise RuntimeError("direction failed")

        topic_owner = Mock()
        failing_row = {
            "calculation_result": {
                "rendered_value": "10%",
                "answer_slots": {
                    "primary_value": {
                        "label": "Metric",
                        "rendered_value": "10%",
                        "normalized_value": RuntimeFloat(),
                    },
                    "current_value": {},
                    "prior_value": {},
                },
            }
        }
        with (
            patch.object(financial_aggregate_projection, "aggregate_result_operation_family", return_value="growth_rate"),
            patch.object(financial_aggregate_projection, "answer_slot_has_material", return_value=True),
            patch.object(financial_aggregate_projection, "growth_slot_display_value", side_effect=["200", "100"]),
            patch.object(financial_aggregate_projection, "growth_slots_share_material", return_value=False),
            patch.object(financial_aggregate_projection.calculation_rendering, "absolute_display_value", side_effect=str),
            patch.object(financial_aggregate_projection, "CALCULATION_SLOT_POLICY", {"period_pattern": r"$^"}),
            patch.object(financial_aggregate_projection, "CALCULATION_NARRATIVE_POLICY", base_policy),
            patch.object(financial_aggregate_projection, "topic_particle", topic_owner),
            self.assertRaisesRegex(RuntimeError, "direction failed"),
        ):
            financial_aggregate_projection.compose_complete_growth_numeric_answer(failing_row, [failing_row])
        topic_owner.assert_not_called()

        regex_topic_owner = Mock()
        regex_row = {
            "metric_label": "Metric",
            "calculation_result": {
                "rendered_value": "10%",
                "answer_slots": {
                    "primary_value": {"rendered_value": "10%", "normalized_value": 1},
                    "current_value": {"label": "Metric"},
                    "prior_value": {},
                },
            },
        }
        with (
            patch.object(financial_aggregate_projection, "aggregate_result_operation_family", return_value="growth_rate"),
            patch.object(financial_aggregate_projection, "answer_slot_has_material", return_value=True),
            patch.object(financial_aggregate_projection, "growth_slot_display_value", side_effect=["200", "100"]),
            patch.object(financial_aggregate_projection, "growth_slots_share_material", return_value=False),
            patch.object(financial_aggregate_projection.calculation_rendering, "absolute_display_value", side_effect=str),
            patch.object(financial_aggregate_projection, "CALCULATION_SLOT_POLICY", {"period_pattern": "pattern"}),
            patch.object(financial_aggregate_projection.re, "sub", side_effect=RuntimeError("regex failed")),
            patch.object(financial_aggregate_projection, "topic_particle", regex_topic_owner),
            self.assertRaisesRegex(RuntimeError, "regex failed"),
        ):
            financial_aggregate_projection.compose_complete_growth_numeric_answer(regex_row, [regex_row])
        regex_topic_owner.assert_not_called()

        bad_template_policy = {**base_policy, "growth_numeric_sentence_template": "{missing}"}
        with self.assertRaises(KeyError):
            render(
                primary={"label": "Metric", "rendered_value": "10%", "normalized_value": 1},
                current={},
                prior={},
                row_label="Metric",
                policy=bad_template_policy,
            )

        class NarrativePolicyBomb:
            def get(self, *_args, **_kwargs):
                raise AssertionError("narrative policy accessed after blank label")

        blank_label_row = {
            "calculation_result": {
                "rendered_value": "10%",
                "answer_slots": {
                    "primary_value": {"rendered_value": "10%", "normalized_value": 1},
                    "current_value": {},
                    "prior_value": {},
                },
            }
        }
        with (
            patch.object(financial_aggregate_projection, "aggregate_result_operation_family", return_value="growth_rate"),
            patch.object(financial_aggregate_projection, "answer_slot_has_material", return_value=True),
            patch.object(financial_aggregate_projection, "growth_slot_display_value", side_effect=["200", "100"]),
            patch.object(financial_aggregate_projection, "growth_slots_share_material", return_value=False),
            patch.object(financial_aggregate_projection.calculation_rendering, "absolute_display_value", side_effect=str),
            patch.object(financial_aggregate_projection, "CALCULATION_SLOT_POLICY", {"period_pattern": r"$^"}),
            patch.object(financial_aggregate_projection, "CALCULATION_NARRATIVE_POLICY", NarrativePolicyBomb()),
        ):
            self.assertEqual(
                financial_aggregate_projection.compose_complete_growth_numeric_answer(blank_label_row, [blank_label_row]),
                "",
            )

    def test_current_source_growth_numeric_renderer_static_bindings_plan_dag_and_baseline(self) -> None:
        import json
        from pathlib import Path

        graph_path = Path("src/agent/financial_graph_calculation.py")
        owner_path = Path("src/agent/financial_aggregate_projection.py")
        trees = {
            "graph": ast.parse(graph_path.read_text(encoding="utf-8-sig")),
            "owner": ast.parse(owner_path.read_text(encoding="utf-8-sig")),
        }
        public_name = "compose_complete_growth_numeric_answer"
        private_name = f"_{public_name}"
        definitions = {}
        calls = []
        noncall_refs = []
        try_depths = []

        class Visitor(ast.NodeVisitor):
            def __init__(self, module_name):
                self.module_name = module_name
                self.stack = []
                self.try_depth = 0
                self.call_depth = 0

            def visit_FunctionDef(self, node):
                if node.name in {private_name, public_name}:
                    definitions[(self.module_name, node.name)] = node
                self.stack.append(node.name)
                self.generic_visit(node)
                self.stack.pop()

            def visit_Try(self, node):
                self.try_depth += 1
                self.generic_visit(node)
                self.try_depth -= 1

            def visit_Call(self, node):
                name = ""
                receiver = ""
                if isinstance(node.func, ast.Attribute):
                    name = node.func.attr
                    receiver = ast.unparse(node.func.value)
                elif isinstance(node.func, ast.Name):
                    name = node.func.id
                if name in {private_name, public_name}:
                    calls.append(
                        (
                            self.module_name,
                            tuple(self.stack),
                            receiver,
                            tuple(ast.unparse(arg) for arg in node.args),
                            tuple((item.arg, ast.unparse(item.value)) for item in node.keywords),
                        )
                    )
                    try_depths.append(self.try_depth)
                self.call_depth += 1
                self.generic_visit(node)
                self.call_depth -= 1

            def visit_Attribute(self, node):
                if node.attr in {private_name, public_name} and self.call_depth == 0:
                    noncall_refs.append((self.module_name, node.attr, node.lineno))
                self.generic_visit(node)

            def visit_Name(self, node):
                if node.id in {private_name, public_name} and self.call_depth == 0:
                    noncall_refs.append((self.module_name, node.id, node.lineno))

        for module_name, tree in trees.items():
            Visitor(module_name).visit(tree)

        self.assertEqual(set(definitions), {("owner", public_name)})
        definition = definitions[("owner", public_name)]
        self.assertEqual(definition.end_lineno - definition.lineno + 1, 99)
        self.assertEqual(
            sorted(
                node.attr
                for node in ast.walk(definition)
                if isinstance(node, ast.Attribute)
                and isinstance(node.value, ast.Name)
                and node.value.id == "self"
            ),
            [],
        )
        self.assertEqual(len(calls), 9)
        self.assertEqual(noncall_refs, [])
        self.assertEqual(try_depths, [0] * 9)
        self.assertTrue(all(receiver == "" for _module, _stack, receiver, _args, _kwargs in calls))
        self.assertEqual(Counter(module for module, *_rest in calls), Counter({"graph": 4, "owner": 5}))
        self.assertEqual(
            Counter(stack[-1] for _module, stack, _receiver, _args, _kwargs in calls),
            Counter(
                {
                    "_preferred_complete_numeric_answer": 1,
                    "ensure_complete_growth_numeric_answer": 1,
                    "_final_growth_answer_without_untraced_numeric_sentences": 1,
                    "_enforce_source_stated_growth_answer_contract": 1,
                    "strip_untraced_numeric_material_from_growth_narrative_sentence": 1,
                    "growth_answer_has_untraced_numeric_material": 1,
                    "narrative_summary_conflicts_with_growth_trace": 1,
                    "growth_narrative_numeric_incompatible_with_trace": 1,
                    "_is_growth_supported_sentence": 1,
                }
            ),
        )
        self.assertTrue(all(args == ("row", "ordered_results") for _module, _stack, _receiver, args, _kwargs in calls))
        self.assertEqual(
            Counter(kwargs for _module, _stack, _receiver, _args, kwargs in calls),
            Counter({(("evidence_items", "evidence_items"),): 6, (): 3}),
        )
        self.assertEqual(definition.end_lineno - definition.lineno + 1, 99)
        selected_names = {private_name, public_name}
        external = sum(
            not selected_names.intersection(stack)
            for _module, stack, _receiver, _args, _kwargs in calls
        )
        self.assertEqual((external, len(calls) - external), (9, 0))

        module_paths = list(Path("src/agent").glob("*.py")) + list(Path("src/config").glob("*.py"))
        import_graph = {}
        for path in module_paths:
            module_name = ".".join(path.with_suffix("").parts)
            imported = set()
            for node in ast.parse(path.read_text(encoding="utf-8-sig")).body:
                if isinstance(node, ast.ImportFrom) and node.module:
                    imported.add(node.module)
                elif isinstance(node, ast.Import):
                    imported.update(alias.name for alias in node.names)
            import_graph[module_name] = imported

        def reaches(start, target):
            pending = [start]
            seen = set()
            while pending:
                current = pending.pop()
                if current == target:
                    return True
                if current in seen:
                    continue
                seen.add(current)
                pending.extend(import_graph.get(current, ()))
            return False

        owner_module = "src.agent.financial_aggregate_projection"
        for dependency in (
            "src.agent.financial_text_surface",
            "src.config.retrieval_policy",
        ):
            self.assertFalse(reaches(dependency, owner_module), dependency)
        self.assertIn("src.agent.financial_text_surface", import_graph[owner_module])
        self.assertIn("src.config.retrieval_policy", import_graph[owner_module])

        baseline = json.loads(
            (Path("tests") / "fixtures" / "runtime_domain_terms_baseline.json").read_text(encoding="utf-8")
        )
        self.assertEqual(len(baseline["records"]), 217)
        selected_lines = set(range(definition.lineno, definition.end_lineno + 1))
        self.assertEqual(
            [
                record
                for record in baseline["records"]
                if record.get("path") == "src/agent/financial_aggregate_projection.py"
                and selected_lines.intersection(record.get("first_lines") or [])
            ],
            [],
        )

    def test_current_source_growth_numeric_renderer_preferred_and_complete_callers(self) -> None:
        nested = {"preserve": True}
        row = {
            "status": "ok",
            "operation_family": "growth_rate",
            "metric_label": "Metric",
            "calculation_result": {"answer_slots": {}, "nested": nested},
            "nested": nested,
        }
        ordered_results = [row]
        evidence_items = [{"evidence_id": "ev_1", "nested": nested}]
        before_results = deepcopy(ordered_results)
        before_evidence = deepcopy(evidence_items)

        class PreferredAgent:
            pass

        preferred = PreferredAgent()
        preferred._aggregate_dependency_source_slot_by_task_id = Mock(return_value={})
        preferred._aggregate_result_operation_family = Mock(return_value="growth_rate")
        preferred._ratio_answer_from_dependency_source_slots = Mock()
        preferred._compact_ratio_answer = Mock()
        compose_owner = Mock(return_value="complete growth")
        with (
            patch.object(financial_graph_calculation, "compose_complete_growth_numeric_answer", compose_owner),
            patch.object(financial_graph_calculation, "narrative_context_terms", return_value=[]),
            patch.object(financial_graph_calculation, "material_gap_feedback_for_subtask_result", return_value=""),
            patch.object(financial_graph_calculation, "aggregate_result_dependency_coherence_ranks", return_value=(1, 1)),
            patch.object(financial_graph_calculation, "growth_row_has_conflicting_periods", return_value=False),
        ):
            answer = financial_graph_calculation.FinancialAgentCalculationMixin._preferred_complete_numeric_answer(
                preferred,
                ordered_results,
                query="query",
                evidence_items=evidence_items,
            )
        self.assertEqual(answer, "complete growth")
        compose_owner.assert_called_once_with(row, ordered_results, evidence_items=evidence_items)
        self.assertIs(compose_owner.call_args.args[0], row)
        self.assertIs(compose_owner.call_args.args[1], ordered_results)
        self.assertIs(compose_owner.call_args.kwargs["evidence_items"], evidence_items)
        preferred._compact_ratio_answer.assert_not_called()

        failing_compose = Mock(side_effect=RuntimeError("compose failed"))
        with (
            patch.object(financial_graph_calculation, "compose_complete_growth_numeric_answer", failing_compose),
            patch.object(financial_graph_calculation, "narrative_context_terms", return_value=[]),
            patch.object(financial_graph_calculation, "material_gap_feedback_for_subtask_result", return_value=""),
            patch.object(financial_graph_calculation, "aggregate_result_dependency_coherence_ranks", return_value=(1, 1)),
            patch.object(financial_graph_calculation, "growth_row_has_conflicting_periods", return_value=False),
            self.assertRaisesRegex(RuntimeError, "compose failed"),
        ):
            financial_graph_calculation.FinancialAgentCalculationMixin._preferred_complete_numeric_answer(
                preferred,
                ordered_results,
                evidence_items=evidence_items,
            )
        preferred._compact_ratio_answer.assert_not_called()

        events = []

        def compose(row_arg, results_arg, *, evidence_items):
            events.append(("compose", row_arg, results_arg, evidence_items))
            return "complete 10"

        compose_owner = Mock(side_effect=compose)

        def required(row_arg, results_arg, evidence_arg):
            events.append(("required", row_arg, results_arg, evidence_arg))
            return ["10"]

        def untraced(answer_arg, complete_arg, values_arg):
            events.append(("untraced", answer_arg, complete_arg, values_arg))
            return False

        with (
            patch.object(financial_aggregate_projection, "aggregate_result_operation_family", return_value="growth_rate"),
            patch.object(financial_aggregate_projection, "compose_complete_growth_numeric_answer", compose_owner),
            patch.object(financial_aggregate_projection, "growth_row_has_conflicting_periods", return_value=False),
            patch.object(financial_aggregate_projection, "growth_required_display_values", side_effect=required),
            patch.object(financial_aggregate_projection, "growth_answer_has_untraced_numeric_sentence", side_effect=untraced),
        ):
            answer = financial_aggregate_projection.ensure_complete_growth_numeric_answer(
                "existing 10",
                ordered_results,
                evidence_items=evidence_items,
            )
        self.assertEqual(answer, "existing 10")
        self.assertEqual([event[0] for event in events], ["compose", "required", "untraced"])
        self.assertIs(events[0][1], row)
        self.assertIs(events[0][2], ordered_results)
        self.assertIs(events[0][3], evidence_items)

        required_owner = Mock()
        failing_compose = Mock(side_effect=RuntimeError("owner failed"))
        with (
            patch.object(financial_aggregate_projection, "aggregate_result_operation_family", return_value="growth_rate"),
            patch.object(financial_aggregate_projection, "compose_complete_growth_numeric_answer", failing_compose),
            patch.object(financial_aggregate_projection, "growth_row_has_conflicting_periods", return_value=False),
            patch.object(financial_aggregate_projection, "growth_required_display_values", required_owner),
            self.assertRaisesRegex(RuntimeError, "owner failed"),
        ):
            financial_aggregate_projection.ensure_complete_growth_numeric_answer(
                "answer",
                ordered_results,
                evidence_items=evidence_items,
            )
        required_owner.assert_not_called()
        self.assertEqual(ordered_results, before_results)
        self.assertEqual(evidence_items, before_evidence)
        self.assertIs(row["nested"], nested)

    def test_current_source_growth_numeric_renderer_narrative_and_support_callers(self) -> None:
        nested = {"preserve": True}
        row = {"operation_family": "growth_rate", "nested": nested}
        ordered_results = [row]
        evidence_items = [{"evidence_id": "ev_1", "nested": nested}]
        before_results = deepcopy(ordered_results)
        before_evidence = deepcopy(evidence_items)

        class NarrativeAgent:
            pass

        agent = NarrativeAgent()
        agent._aggregate_result_operation_family = Mock(return_value="growth_rate")
        events = []

        def compose(row_arg, results_arg, *, evidence_items):
            events.append(("compose", row_arg, results_arg, evidence_items))
            return "trace 10"

        compose_owner = Mock(side_effect=compose)

        def required(row_arg, results_arg, *, evidence_items):
            events.append(("required", row_arg, results_arg, evidence_items))
            return ["200", "100"]

        def extract(surface):
            events.append(("extract", surface))
            return [{"value": 99}] if surface == "narrative 99" else [{"value": 10}]

        def equivalent(narrative_candidate, trace_candidate):
            events.append(("equivalent", narrative_candidate, trace_candidate))
            return False

        with (
            patch.object(financial_aggregate_projection, "compose_complete_growth_numeric_answer", compose_owner),
            patch.object(financial_aggregate_projection, "growth_row_has_conflicting_periods", return_value=False),
            patch.object(financial_aggregate_projection, "growth_required_display_values", side_effect=required),
            patch.object(financial_aggregate_projection, "extract_numeric_surface_candidates", side_effect=extract),
            patch.object(financial_aggregate_projection, "numeric_surface_candidates_equivalent", side_effect=equivalent),
        ):
            incompatible = financial_aggregate_projection.growth_narrative_numeric_incompatible_with_trace(
                narrative_answer="narrative 99",
                numeric_answer="numeric 10",
                ordered_results=ordered_results,
                evidence_items=evidence_items,
            )
        self.assertTrue(incompatible)
        self.assertEqual([event[0] for event in events], ["compose", "required", "extract", "extract", "equivalent"])
        self.assertIs(events[0][1], row)
        self.assertIs(events[0][2], ordered_results)
        self.assertIs(events[0][3], evidence_items)
        self.assertIs(events[1][3], evidence_items)

        required_owner = Mock()
        extract_owner = Mock()
        failing_compose = Mock(side_effect=RuntimeError("narrative compose failed"))
        with (
            patch.object(financial_aggregate_projection, "compose_complete_growth_numeric_answer", failing_compose),
            patch.object(financial_aggregate_projection, "growth_row_has_conflicting_periods", return_value=False),
            patch.object(financial_aggregate_projection, "growth_required_display_values", required_owner),
            patch.object(financial_aggregate_projection, "extract_numeric_surface_candidates", extract_owner),
            self.assertRaisesRegex(RuntimeError, "narrative compose failed"),
        ):
            financial_aggregate_projection.growth_narrative_numeric_incompatible_with_trace(
                narrative_answer="narrative 99",
                numeric_answer="numeric 10",
                ordered_results=ordered_results,
                evidence_items=evidence_items,
            )
        required_owner.assert_not_called()
        extract_owner.assert_not_called()

        compose_owner = Mock(return_value="trace 10")
        required_owner = Mock(return_value=["10"])
        untraced_owner = Mock(return_value=True)
        splitter = Mock(side_effect=AssertionError("splitter accessed after direct conflict"))
        with (
            patch.object(financial_aggregate_projection, "compose_complete_growth_numeric_answer", compose_owner),
            patch.object(financial_aggregate_projection, "growth_row_has_conflicting_periods", return_value=False),
            patch.object(financial_aggregate_projection, "growth_required_display_values", required_owner),
            patch.object(financial_aggregate_projection, "growth_answer_has_untraced_numeric_sentence", untraced_owner),
            patch.object(financial_aggregate_projection, "_split_narrative_sentences", splitter),
        ):
            self.assertTrue(
                financial_aggregate_projection.growth_answer_has_untraced_numeric_material(
                    "answer 99",
                    ordered_results,
                    evidence_items=evidence_items,
                )
            )
        compose_owner.assert_called_once_with(row, ordered_results)
        required_owner.assert_called_once_with(row, ordered_results, evidence_items)
        untraced_owner.assert_called_once_with("answer 99", "trace 10", ["10"])
        splitter.assert_not_called()
        self.assertEqual(ordered_results, before_results)
        self.assertEqual(evidence_items, before_evidence)
        self.assertIs(row["nested"], nested)
        self.assertIs(evidence_items[0]["nested"], nested)

    def test_current_source_growth_trace_untraced_material_matrix(self) -> None:
        fn = financial_aggregate_projection.growth_answer_has_untraced_numeric_material

        class IterBomb:
            def __iter__(self):
                raise AssertionError("rows iterated after blank answer")

        family_after_blank = Mock()
        with patch.object(financial_aggregate_projection, "aggregate_result_operation_family", family_after_blank):
            self.assertFalse(fn("   ", IterBomb(), [{"evidence_id": "unused"}]))
        family_after_blank.assert_not_called()

        nested = {"preserve": True}
        rows = [
            {"role": "non-growth", "nested": nested},
            {"role": "conflict", "nested": nested},
            {"role": "missing", "nested": nested},
            {"role": "target", "nested": nested},
        ]
        evidence_items = [{"evidence_id": "ev-1", "nested": nested}]
        before_rows = deepcopy(rows)
        before_evidence = deepcopy(evidence_items)
        events = []

        def family(row):
            events.append(("family", row["role"]))
            return "lookup" if row["role"] == "non-growth" else "growth_rate"

        def conflict(row):
            events.append(("conflict", row["role"]))
            return row["role"] == "conflict"

        def compose(row, results):
            events.append(("compose", row["role"], results))
            return "" if row["role"] == "missing" else "trace 10%"

        def required(row, results, evidence):
            events.append(("required", row["role"], results, evidence))
            return ["10%"]

        def answer_guard(answer, complete, values):
            events.append(("answer", answer, complete, values))
            return False

        def split(answer):
            events.append(("split", answer))
            return ["first sentence", "second sentence"]

        sentence_results = iter((False, True))

        def sentence_guard(sentence, complete, values, evidence):
            events.append(("sentence", sentence, complete, values, evidence))
            return next(sentence_results)

        with (
            patch.object(financial_aggregate_projection, "aggregate_result_operation_family", side_effect=family),
            patch.object(financial_aggregate_projection, "growth_row_has_conflicting_periods", side_effect=conflict),
            patch.object(financial_aggregate_projection, "compose_complete_growth_numeric_answer", side_effect=compose),
            patch.object(financial_aggregate_projection, "growth_required_display_values", side_effect=required),
            patch.object(
                financial_aggregate_projection,
                "growth_answer_has_untraced_numeric_sentence",
                side_effect=answer_guard,
            ),
            patch.object(financial_aggregate_projection, "_split_narrative_sentences", side_effect=split),
            patch.object(
                financial_aggregate_projection,
                "growth_sentence_has_untraced_material_numeric",
                side_effect=sentence_guard,
            ),
        ):
            self.assertTrue(fn(" answer 99% ", rows, evidence_items))

        self.assertEqual(
            [(event[0], event[1]) for event in events if event[0] in {"family", "conflict", "compose", "required"}],
            [
                ("family", "non-growth"),
                ("family", "conflict"),
                ("conflict", "conflict"),
                ("family", "missing"),
                ("conflict", "missing"),
                ("compose", "missing"),
                ("required", "missing"),
                ("family", "target"),
                ("conflict", "target"),
                ("compose", "target"),
                ("required", "target"),
            ],
        )
        self.assertEqual(
            [event[0] for event in events[-4:]],
            ["answer", "split", "sentence", "sentence"],
        )
        self.assertIs(next(event for event in events if event[0] == "compose" and event[1] == "target")[2], rows)
        required_event = next(event for event in events if event[0] == "required")
        self.assertIs(required_event[2], rows)
        self.assertIs(required_event[3], evidence_items)
        self.assertIs(events[-1][4], evidence_items)
        self.assertEqual(rows, before_rows)
        self.assertEqual(evidence_items, before_evidence)
        self.assertIs(rows[0]["nested"], nested)
        self.assertIs(evidence_items[0]["nested"], nested)

        split_owner = Mock(side_effect=AssertionError("split after whole-answer conflict"))
        with (
            patch.object(financial_aggregate_projection, "aggregate_result_operation_family", return_value="growth_rate"),
            patch.object(financial_aggregate_projection, "growth_row_has_conflicting_periods", return_value=False),
            patch.object(financial_aggregate_projection, "compose_complete_growth_numeric_answer", return_value="trace"),
            patch.object(financial_aggregate_projection, "growth_required_display_values", return_value=["10"]),
            patch.object(financial_aggregate_projection, "growth_answer_has_untraced_numeric_sentence", return_value=True),
            patch.object(financial_aggregate_projection, "_split_narrative_sentences", split_owner),
        ):
            self.assertTrue(fn("answer", [rows[-1]], evidence_items))
        split_owner.assert_not_called()

        downstream_split = Mock()
        with (
            patch.object(financial_aggregate_projection, "aggregate_result_operation_family", return_value="growth_rate"),
            patch.object(financial_aggregate_projection, "growth_row_has_conflicting_periods", return_value=False),
            patch.object(financial_aggregate_projection, "compose_complete_growth_numeric_answer", return_value="trace"),
            patch.object(financial_aggregate_projection, "growth_required_display_values", return_value=["10"]),
            patch.object(
                financial_aggregate_projection,
                "growth_answer_has_untraced_numeric_sentence",
                side_effect=RuntimeError("answer guard failed"),
            ),
            patch.object(financial_aggregate_projection, "_split_narrative_sentences", downstream_split),
            self.assertRaisesRegex(RuntimeError, "answer guard failed"),
        ):
            fn("answer", [rows[-1]], evidence_items)
        downstream_split.assert_not_called()

    def test_current_source_growth_trace_narrative_summary_conflict_matrix(self) -> None:
        fn = financial_aggregate_projection.narrative_summary_conflicts_with_growth_trace

        class IterBomb:
            def __iter__(self):
                raise AssertionError("rows iterated after blank narrative")

        family_after_blank = Mock()
        with patch.object(financial_aggregate_projection, "aggregate_result_operation_family", family_after_blank):
            self.assertFalse(fn("", IterBomb(), [{"claim": "unused"}]))
        family_after_blank.assert_not_called()

        nested = {"preserve": True}
        rows = [
            {"role": "non-growth", "nested": nested},
            {"role": "conflict", "nested": nested},
            {"role": "missing", "nested": nested},
            {"role": "target", "nested": nested},
        ]
        evidence_items = [
            {
                "claim": "claim one 10%",
                "quote_span": "quote one",
                "raw_row_text": "raw one",
                "source_context": "context one",
                "metadata": {
                    "table_value_labels_text": "labels one",
                    "table_summary_text": "summary one",
                    "table_header_context": "header one",
                    "table_context": "table one",
                },
                "nested": nested,
            },
            {"claim": "claim two", "metadata": {"table_context": "table two"}, "nested": nested},
        ]
        before_rows = deepcopy(rows)
        before_evidence = deepcopy(evidence_items)
        events = []

        def family(row):
            events.append(("family", row["role"]))
            return "lookup" if row["role"] == "non-growth" else "growth_rate"

        def conflict(row):
            events.append(("conflict", row["role"]))
            return row["role"] == "conflict"

        def compose(row, results):
            events.append(("compose", row["role"], results))
            return "" if row["role"] == "missing" else "trace 10%"

        def required(row, results, evidence):
            events.append(("required", row["role"], results, evidence))
            return ["10%"]

        display_owner = Mock(return_value=[{"text": "84.3%"}])
        policy = {"percent_display_pattern": r"\d+(?:\.\d+)?%"}
        with (
            patch.object(financial_aggregate_projection, "aggregate_result_operation_family", side_effect=family),
            patch.object(financial_aggregate_projection, "growth_row_has_conflicting_periods", side_effect=conflict),
            patch.object(financial_aggregate_projection, "compose_complete_growth_numeric_answer", side_effect=compose),
            patch.object(financial_aggregate_projection, "growth_required_display_values", side_effect=required),
            patch.object(financial_aggregate_projection, "evidence_numeric_display_candidates", display_owner),
            patch.object(financial_aggregate_projection, "CALCULATION_NARRATIVE_POLICY", policy),
        ):
            self.assertTrue(fn(" narrative 99% ", rows, evidence_items))
        self.assertEqual([event[:2] for event in events[:6]], [
            ("family", "non-growth"),
            ("family", "conflict"),
            ("conflict", "conflict"),
            ("family", "missing"),
            ("conflict", "missing"),
            ("compose", "missing"),
        ])
        self.assertIs(display_owner.call_args.args[0], evidence_items)
        expected_surface = (
            "claim one 10% quote one raw one context one labels one summary one "
            "header one table one claim two table two"
        )
        self.assertEqual(display_owner.call_args.args[1], expected_surface)
        self.assertEqual(rows, before_rows)
        self.assertEqual(evidence_items, before_evidence)
        self.assertIs(evidence_items[0]["nested"], nested)

        with (
            patch.object(financial_aggregate_projection, "aggregate_result_operation_family", return_value="growth_rate"),
            patch.object(financial_aggregate_projection, "growth_row_has_conflicting_periods", return_value=False),
            patch.object(financial_aggregate_projection, "compose_complete_growth_numeric_answer", return_value="trace 10%"),
            patch.object(financial_aggregate_projection, "growth_required_display_values", return_value=["10%"]),
            patch.object(
                financial_aggregate_projection,
                "evidence_numeric_display_candidates",
                return_value=[{"text": "84.3%"}],
            ),
            patch.object(financial_aggregate_projection, "CALCULATION_NARRATIVE_POLICY", policy),
        ):
            self.assertFalse(fn("narrative 84.3%", [rows[-1]], evidence_items))

        class CopyBomb:
            def keys(self):
                raise RuntimeError("metadata copy failed")

            def __getitem__(self, _key):
                raise AssertionError("metadata item accessed")

        downstream_display = Mock()
        with (
            patch.object(financial_aggregate_projection, "aggregate_result_operation_family", return_value="growth_rate"),
            patch.object(financial_aggregate_projection, "growth_row_has_conflicting_periods", return_value=False),
            patch.object(financial_aggregate_projection, "compose_complete_growth_numeric_answer", return_value="trace"),
            patch.object(financial_aggregate_projection, "growth_required_display_values", return_value=["10"]),
            patch.object(financial_aggregate_projection, "evidence_numeric_display_candidates", downstream_display),
            patch.object(financial_aggregate_projection, "CALCULATION_NARRATIVE_POLICY", policy),
            self.assertRaisesRegex(RuntimeError, "metadata copy failed"),
        ):
            fn("narrative 99%", [rows[-1]], [{"metadata": CopyBomb()}])
        downstream_display.assert_not_called()

    def test_current_source_growth_trace_numeric_incompatibility_matrix(self) -> None:
        fn = financial_aggregate_projection.growth_narrative_numeric_incompatible_with_trace

        class IterBomb:
            def __iter__(self):
                raise AssertionError("rows iterated after blank narrative")

        family_after_blank = Mock()
        with patch.object(financial_aggregate_projection, "aggregate_result_operation_family", family_after_blank):
            self.assertFalse(
                fn(
                narrative_answer=" ",
                numeric_answer="numeric 10",
                ordered_results=IterBomb(),
                evidence_items=[],
                )
            )
        family_after_blank.assert_not_called()

        nested = {"preserve": True}
        rows = [
            {"role": "non-growth", "nested": nested},
            {"role": "conflict", "nested": nested},
            {"role": "first", "nested": nested},
            {"role": "second", "nested": nested},
        ]
        evidence_items = [{"evidence_id": "ev", "nested": nested}]
        before_rows = deepcopy(rows)
        before_evidence = deepcopy(evidence_items)
        events = []

        def family(row):
            events.append(("family", row["role"]))
            return "lookup" if row["role"] == "non-growth" else "growth_rate"

        def conflict(row):
            events.append(("conflict", row["role"]))
            return row["role"] == "conflict"

        def compose(row, results, *, evidence_items):
            events.append(("compose", row["role"], results, evidence_items))
            return f"trace-{row['role']}"

        def required(row, results, *, evidence_items):
            events.append(("required", row["role"], results, evidence_items))
            return [f"required-{row['role']}"]

        trace_candidates = [{"id": "t1"}, {"id": "t2"}]
        narrative_candidates = [{"id": "n1"}, {"id": "n2"}]

        def extract(surface):
            events.append(("extract", surface))
            return narrative_candidates if surface == "narrative 99" else trace_candidates

        def equivalent(narrative, trace):
            events.append(("equivalent", narrative["id"], trace["id"]))
            return narrative["id"] == "n1" and trace["id"] == "t2"

        with (
            patch.object(financial_aggregate_projection, "aggregate_result_operation_family", side_effect=family),
            patch.object(financial_aggregate_projection, "growth_row_has_conflicting_periods", side_effect=conflict),
            patch.object(financial_aggregate_projection, "compose_complete_growth_numeric_answer", side_effect=compose),
            patch.object(financial_aggregate_projection, "growth_required_display_values", side_effect=required),
            patch.object(financial_aggregate_projection, "extract_numeric_surface_candidates", side_effect=extract),
            patch.object(financial_aggregate_projection, "numeric_surface_candidates_equivalent", side_effect=equivalent),
        ):
            self.assertTrue(
                fn(
                    narrative_answer="narrative 99",
                    numeric_answer="numeric 10",
                    ordered_results=rows,
                    evidence_items=evidence_items,
                )
            )
        self.assertEqual(
            [event for event in events if event[0] == "extract"],
            [
                ("extract", "numeric 10 trace-first required-first trace-second required-second"),
                ("extract", "narrative 99"),
            ],
        )
        self.assertEqual(
            [event for event in events if event[0] == "equivalent"],
            [
                ("equivalent", "n1", "t1"),
                ("equivalent", "n1", "t2"),
                ("equivalent", "n2", "t1"),
                ("equivalent", "n2", "t2"),
            ],
        )
        compose_events = [event for event in events if event[0] == "compose"]
        self.assertIs(compose_events[0][2], rows)
        self.assertIs(compose_events[0][3], evidence_items)
        self.assertEqual(rows, before_rows)
        self.assertEqual(evidence_items, before_evidence)
        self.assertIs(rows[0]["nested"], nested)

        extract_owner = Mock(side_effect=[[], [{"id": "n"}]])
        equivalent_owner = Mock()
        with (
            patch.object(financial_aggregate_projection, "aggregate_result_operation_family", return_value="lookup"),
            patch.object(financial_aggregate_projection, "extract_numeric_surface_candidates", extract_owner),
            patch.object(financial_aggregate_projection, "numeric_surface_candidates_equivalent", equivalent_owner),
        ):
            self.assertFalse(
                fn(
                    narrative_answer="narrative",
                    numeric_answer="numeric",
                    ordered_results=[],
                    evidence_items=evidence_items,
                )
            )
        self.assertEqual(extract_owner.call_count, 2)
        equivalent_owner.assert_not_called()

        downstream_required = Mock()
        downstream_extract = Mock()
        with (
            patch.object(financial_aggregate_projection, "aggregate_result_operation_family", return_value="growth_rate"),
            patch.object(financial_aggregate_projection, "growth_row_has_conflicting_periods", return_value=False),
            patch.object(
                financial_aggregate_projection,
                "compose_complete_growth_numeric_answer",
                side_effect=RuntimeError("compose failed"),
            ),
            patch.object(financial_aggregate_projection, "growth_required_display_values", downstream_required),
            patch.object(financial_aggregate_projection, "extract_numeric_surface_candidates", downstream_extract),
            self.assertRaisesRegex(RuntimeError, "compose failed"),
        ):
            fn(
                narrative_answer="narrative",
                numeric_answer="numeric",
                ordered_results=[rows[-1]],
                evidence_items=evidence_items,
            )
        downstream_required.assert_not_called()
        downstream_extract.assert_not_called()

    def test_current_source_growth_trace_inspection_static_bindings_plan_dag_and_baseline(self) -> None:
        import json
        from pathlib import Path

        graph_path = Path("src/agent/financial_graph_calculation.py")
        owner_path = Path("src/agent/financial_aggregate_projection.py")
        trees = {
            "graph": ast.parse(graph_path.read_text(encoding="utf-8-sig")),
            "owner": ast.parse(owner_path.read_text(encoding="utf-8-sig")),
        }
        public_names = {
            "growth_answer_has_untraced_numeric_material": 28,
            "narrative_summary_conflicts_with_growth_trace": 56,
            "growth_narrative_numeric_incompatible_with_trace": 43,
        }
        private_names = {f"_{name}": span + 1 for name, span in public_names.items()}
        selected_names = set(private_names) | set(public_names)
        definitions = {}
        calls = []
        noncall_refs = []

        class Visitor(ast.NodeVisitor):
            def __init__(self, module_name):
                self.module_name = module_name
                self.stack = []
                self.try_depth = 0
                self.call_depth = 0

            def visit_FunctionDef(self, node):
                if node.name in selected_names:
                    definitions[(self.module_name, node.name)] = node
                self.stack.append(node.name)
                self.generic_visit(node)
                self.stack.pop()

            def visit_Try(self, node):
                self.try_depth += 1
                self.generic_visit(node)
                self.try_depth -= 1

            def visit_Call(self, node):
                target = None
                receiver = None
                if isinstance(node.func, ast.Name):
                    target = node.func.id
                    receiver = "Name"
                elif isinstance(node.func, ast.Attribute):
                    target = node.func.attr
                    receiver = ast.unparse(node.func.value)
                if target in selected_names:
                    calls.append(
                        (
                            self.module_name,
                            tuple(self.stack),
                            target,
                            receiver,
                            tuple(ast.unparse(arg) for arg in node.args),
                            tuple((keyword.arg, ast.unparse(keyword.value)) for keyword in node.keywords),
                            self.try_depth,
                        )
                    )
                self.call_depth += 1
                self.generic_visit(node)
                self.call_depth -= 1

            def visit_Name(self, node):
                if node.id in selected_names and self.call_depth == 0:
                    noncall_refs.append((self.module_name, tuple(self.stack), node.id, "Name"))

            def visit_Attribute(self, node):
                if node.attr in selected_names and self.call_depth == 0:
                    noncall_refs.append(
                        (self.module_name, tuple(self.stack), node.attr, ast.unparse(node.value))
                    )
                self.generic_visit(node)

        for module_name, tree in trees.items():
            Visitor(module_name).visit(tree)

        self.assertEqual(
            {(module, name): node.end_lineno - node.lineno + 1 for (module, name), node in definitions.items()},
            {("owner", name): span for name, span in public_names.items()},
        )
        self.assertEqual(noncall_refs, [])
        self.assertEqual(len(calls), 19)
        self.assertTrue(all(module == "graph" and target in public_names for module, _stack, target, *_ in calls))
        self.assertTrue(all(receiver == "Name" and try_depth == 0 for *_head, receiver, _args, _kwargs, try_depth in calls))
        self.assertEqual(
            Counter(target for _module, _stack, target, _receiver, _args, _kwargs, _try in calls),
            Counter(
                {
                    "growth_answer_has_untraced_numeric_material": 16,
                    "narrative_summary_conflicts_with_growth_trace": 1,
                    "growth_narrative_numeric_incompatible_with_trace": 2,
                }
            ),
        )
        self.assertEqual(
            Counter(stack[-1] for _module, stack, target, *_tail in calls if target == "growth_answer_has_untraced_numeric_material"),
            Counter(
                {
                    "_aggregate_calculation_subtasks": 2,
                    "_answer_matches_supported_aggregate_subtask": 1,
                    "_final_growth_answer_without_untraced_numeric_sentences": 1,
                    "_late_runtime_numeric_answer": 2,
                    "_prune_irrelevant_growth_narrative_sentences": 1,
                    "_refresh_numeric_answer_preserving_narrative_context": 8,
                    "_uncovered_supported_growth_narrative_candidate": 1,
                }
            ),
        )
        conflict_call = next(call for call in calls if call[2] == "narrative_summary_conflicts_with_growth_trace")
        self.assertEqual(conflict_call[1][-1], "_preferred_conflicting_growth_narrative_answer")
        self.assertEqual(conflict_call[4], ("row_answer", "ordered_results", "evidence_items"))
        incompatible_calls = [call for call in calls if call[2] == "growth_narrative_numeric_incompatible_with_trace"]
        self.assertEqual(
            Counter(call[1][-1] for call in incompatible_calls),
            Counter({"_aggregate_calculation_subtasks": 1, "_refresh_numeric_answer_preserving_narrative_context": 1}),
        )
        self.assertTrue(
            all(
                call[4] == ()
                and tuple(name for name, _value in call[5])
                == ("narrative_answer", "numeric_answer", "ordered_results", "evidence_items")
                for call in incompatible_calls
            )
        )

        self.assertEqual(sum(private_names.values()), 130)
        self.assertEqual(sum(public_names.values()), 127)
        self.assertEqual({"external": len(calls), "owner_local": 0}, {"external": 19, "owner_local": 0})

        source_root = Path("src") / "agent"
        import_graph = {}
        for path in source_root.glob("*.py"):
            module_name = f"src.agent.{path.stem}"
            imported = set()
            for node in ast.parse(path.read_text(encoding="utf-8-sig")).body:
                if isinstance(node, ast.ImportFrom) and node.module:
                    imported.add(node.module)
                elif isinstance(node, ast.Import):
                    imported.update(alias.name for alias in node.names)
            import_graph[module_name] = imported

        def reaches(start, target):
            pending = [start]
            seen = set()
            while pending:
                current = pending.pop()
                if current == target:
                    return True
                if current in seen:
                    continue
                seen.add(current)
                pending.extend(import_graph.get(current, ()))
            return False

        owner_module = "src.agent.financial_aggregate_projection"
        for dependency in (
            "src.agent.financial_answer_projection",
            "src.agent.financial_numeric_surface",
        ):
            self.assertIn(dependency, import_graph[owner_module])
            self.assertFalse(reaches(dependency, owner_module), dependency)

        graph_text = graph_path.read_text(encoding="utf-8-sig")
        owner_text = owner_path.read_text(encoding="utf-8-sig")
        selected_source = "\n".join(
            ast.get_source_segment(owner_text, definitions[("owner", name)]) or ""
            for name in public_names
        )
        self.assertEqual(selected_source.count("evidence_numeric_display_candidates"), 1)
        self.assertEqual(graph_text.count("evidence_numeric_display_candidates"), 0)
        self.assertEqual(owner_text.count("evidence_numeric_display_candidates"), 2)
        self.assertGreater(graph_text.count("growth_answer_has_untraced_numeric_sentence"), 1)
        self.assertGreater(graph_text.count("growth_sentence_has_untraced_material_numeric"), 1)

        baseline = json.loads(
            (Path("tests") / "fixtures" / "runtime_domain_terms_baseline.json").read_text(encoding="utf-8")
        )
        self.assertEqual(len(baseline["records"]), 217)
        selected_lines = set()
        for name in public_names:
            node = definitions[("owner", name)]
            selected_lines.update(range(node.lineno, node.end_lineno + 1))
        self.assertEqual(
            [
                record
                for record in baseline["records"]
                if record.get("path") == "src/agent/financial_aggregate_projection.py"
                and selected_lines.intersection(record.get("first_lines") or [])
            ],
            [],
        )

    def test_current_source_growth_trace_untraced_callers_pin_args_adoption_and_stop(self) -> None:
        nested = {"preserve": True}
        row = {"task_id": "growth", "nested": nested}
        ordered_results = [row]
        evidence_items = [{"evidence_id": "ev", "nested": nested}]
        before_rows = deepcopy(ordered_results)
        before_evidence = deepcopy(evidence_items)

        class Agent:
            pass

        answer_agent = Agent()
        answer_agent._supported_aggregate_subtask_answer = Mock(return_value="answer 10")
        untraced_owner = Mock(return_value=False)
        with (
            patch.object(financial_graph_calculation, "has_strong_growth_trace_for_answer_refresh", return_value=True),
            patch.object(financial_graph_calculation, "growth_answer_has_untraced_numeric_material", untraced_owner),
        ):
            self.assertTrue(
                financial_graph_calculation.FinancialAgentCalculationMixin._answer_matches_supported_aggregate_subtask(
                    answer_agent,
                    "answer 10",
                    ordered_results,
                )
            )
        untraced_owner.assert_called_once_with("answer 10", ordered_results)
        self.assertIs(untraced_owner.call_args.args[1], ordered_results)

        failing_untraced_owner = Mock(side_effect=RuntimeError("untraced failed"))
        with (
            patch.object(financial_graph_calculation, "has_strong_growth_trace_for_answer_refresh", return_value=True),
            patch.object(
                financial_graph_calculation,
                "growth_answer_has_untraced_numeric_material",
                failing_untraced_owner,
            ),
            self.assertRaisesRegex(RuntimeError, "untraced failed"),
        ):
            financial_graph_calculation.FinancialAgentCalculationMixin._answer_matches_supported_aggregate_subtask(
                answer_agent,
                "answer 10",
                ordered_results,
            )

        candidate_agent = Agent()
        candidate_agent._narrative_driver_groups = Mock(return_value=[])
        candidate_agent._growth_narrative_sentence_candidates = Mock(
            return_value=[(3, "candidate narrative", ["claim-1"])]
        )
        candidate_strip_owner = Mock(return_value="clean explanatory narrative")
        candidate_untraced = Mock(return_value=False)
        with (
            patch.object(financial_graph_calculation, "answer_covers_narrative_context", return_value=False),
            patch.object(financial_graph_calculation, "sentence_has_growth_explanatory_signal", return_value=True),
            patch.object(
                financial_graph_calculation,
                "growth_answer_has_untraced_numeric_material",
                candidate_untraced,
            ),
            patch.object(
                financial_graph_calculation,
                "strip_untraced_numeric_material_from_growth_narrative_sentence",
                candidate_strip_owner,
            ),
        ):
            candidate = financial_graph_calculation.FinancialAgentCalculationMixin._uncovered_supported_growth_narrative_candidate(
                candidate_agent,
                query="query",
                answer="numeric 10",
                ordered_results=ordered_results,
                evidence_items=evidence_items,
            )
        self.assertEqual(candidate, {"sentence": "clean explanatory narrative", "selected_claim_ids": ["claim-1"]})
        candidate_untraced.assert_called_once_with(
            "clean explanatory narrative", ordered_results, evidence_items
        )
        self.assertIs(candidate_untraced.call_args.args[1], ordered_results)
        self.assertIs(candidate_untraced.call_args.args[2], evidence_items)

        failing_candidate_untraced = Mock(side_effect=RuntimeError("candidate failed"))
        with (
            patch.object(financial_graph_calculation, "answer_covers_narrative_context", return_value=False),
            patch.object(financial_graph_calculation, "sentence_has_growth_explanatory_signal", return_value=True),
            patch.object(
                financial_graph_calculation,
                "growth_answer_has_untraced_numeric_material",
                failing_candidate_untraced,
            ),
            patch.object(
                financial_graph_calculation,
                "strip_untraced_numeric_material_from_growth_narrative_sentence",
                candidate_strip_owner,
            ),
            self.assertRaisesRegex(RuntimeError, "candidate failed"),
        ):
            financial_graph_calculation.FinancialAgentCalculationMixin._uncovered_supported_growth_narrative_candidate(
                candidate_agent,
                query="query",
                answer="numeric 10",
                ordered_results=ordered_results,
                evidence_items=evidence_items,
            )
        self.assertEqual(ordered_results, before_rows)
        self.assertEqual(evidence_items, before_evidence)
        self.assertIs(row["nested"], nested)
        self.assertIs(evidence_items[0]["nested"], nested)

    def test_current_source_growth_trace_conflict_and_incompatibility_callers_pin_args_adoption_and_stop(self) -> None:
        nested = {"preserve": True}
        row = {
            "answer": "narrative 99%",
            "selected_claim_ids": ["claim-1"],
            "nested": nested,
        }
        ordered_results = [row]
        evidence_items = [{"evidence_id": "ev", "nested": nested}]
        before_rows = deepcopy(ordered_results)
        before_evidence = deepcopy(evidence_items)

        class Agent:
            pass

        conflict_agent = Agent()
        conflict_owner = Mock(return_value=True)
        conflict_agent._growth_narrative_sentence_candidates = Mock(return_value=[])
        conflict_agent._aggregate_result_operation_family = Mock(return_value="growth_rate")
        with (
            patch.object(financial_graph_calculation, "row_is_narrative_summary", return_value=True),
            patch.object(financial_graph_calculation, "_narrative_sentence_looks_table_noisy", return_value=False),
            patch.object(financial_graph_calculation, "CALCULATION_NARRATIVE_POLICY", {"missing_answer_markers": ()}),
            patch.object(financial_graph_calculation, "narrative_summary_conflicts_with_growth_trace", conflict_owner),
        ):
            candidate = financial_graph_calculation.FinancialAgentCalculationMixin._preferred_conflicting_growth_narrative_answer(
                conflict_agent,
                query="query",
                ordered_results=ordered_results,
                evidence_items=evidence_items,
            )
        self.assertEqual(
            candidate,
            {
                "answer": "narrative 99%",
                "selected_claim_ids": ["claim-1"],
                "operation_family": "growth_rate",
            },
        )
        conflict_owner.assert_called_once_with("narrative 99%", ordered_results, evidence_items)
        self.assertIs(conflict_owner.call_args.args[1], ordered_results)
        self.assertIs(conflict_owner.call_args.args[2], evidence_items)

        downstream_candidates = Mock()
        failing_conflict_owner = Mock(side_effect=RuntimeError("conflict failed"))
        conflict_agent._growth_narrative_sentence_candidates = downstream_candidates
        with (
            patch.object(financial_graph_calculation, "row_is_narrative_summary", return_value=True),
            patch.object(financial_graph_calculation, "CALCULATION_NARRATIVE_POLICY", {"missing_answer_markers": ()}),
            patch.object(
                financial_graph_calculation,
                "narrative_summary_conflicts_with_growth_trace",
                failing_conflict_owner,
            ),
            self.assertRaisesRegex(RuntimeError, "conflict failed"),
        ):
            financial_graph_calculation.FinancialAgentCalculationMixin._preferred_conflicting_growth_narrative_answer(
                conflict_agent,
                query="query",
                ordered_results=ordered_results,
                evidence_items=evidence_items,
            )
        downstream_candidates.assert_not_called()

        refresh_agent = Agent()
        refresh_agent._preferred_conflicting_growth_narrative_answer = Mock(
            return_value={
                "answer": "narrative 99%",
                "selected_claim_ids": ["claim-1"],
                "operation_family": "aggregate_subtasks",
            }
        )
        incompatible_owner = Mock(return_value=True)
        with (
            patch.object(financial_graph_calculation, "row_is_narrative_summary", return_value=True),
            patch.object(financial_graph_calculation, "query_requests_explanatory_context", return_value=False),
            patch.object(
                financial_graph_calculation,
                "growth_narrative_numeric_incompatible_with_trace",
                incompatible_owner,
            ),
        ):
            refreshed = financial_graph_calculation.FinancialAgentCalculationMixin._refresh_numeric_answer_preserving_narrative_context(
                refresh_agent,
                query="query",
                current_answer="",
                numeric_answer="numeric 10",
                ordered_results=ordered_results,
                evidence_items=evidence_items,
            )
        self.assertEqual(
            refreshed,
            {
                "answer": "narrative 99%",
                "selected_claim_ids": ["claim-1"],
                "operation_family": "aggregate_subtasks",
            },
        )
        incompatible_owner.assert_called_once_with(
            narrative_answer="narrative 99%",
            numeric_answer="numeric 10",
            ordered_results=ordered_results,
            evidence_items=evidence_items,
        )
        self.assertIs(incompatible_owner.call_args.kwargs["ordered_results"], ordered_results)
        self.assertIs(incompatible_owner.call_args.kwargs["evidence_items"], evidence_items)

        downstream_split = Mock()
        failing_incompatible_owner = Mock(side_effect=RuntimeError("incompatible failed"))
        with (
            patch.object(financial_graph_calculation, "row_is_narrative_summary", return_value=True),
            patch.object(financial_graph_calculation, "query_requests_explanatory_context", return_value=False),
            patch.object(
                financial_graph_calculation,
                "growth_narrative_numeric_incompatible_with_trace",
                failing_incompatible_owner,
            ),
            patch.object(financial_graph_calculation, "_split_narrative_sentences", downstream_split),
            self.assertRaisesRegex(RuntimeError, "incompatible failed"),
        ):
            financial_graph_calculation.FinancialAgentCalculationMixin._refresh_numeric_answer_preserving_narrative_context(
                refresh_agent,
                query="query",
                current_answer="",
                numeric_answer="numeric 10",
                ordered_results=ordered_results,
                evidence_items=evidence_items,
            )
        downstream_split.assert_not_called()
        self.assertEqual(ordered_results, before_rows)
        self.assertEqual(evidence_items, before_evidence)
        self.assertIs(row["nested"], nested)
        self.assertIs(evidence_items[0]["nested"], nested)

    def test_current_source_final_answer_evidence_filter_pins_branches_copies_and_exceptions(self) -> None:
        owner = financial_aggregate_projection.filter_aggregate_evidence_for_final_answer

        class IterationBomb:
            def __iter__(self):
                raise AssertionError("selected ids accessed")

        extract = Mock(return_value=[])
        promote = Mock(side_effect=AssertionError("promotion accessed"))
        support = Mock(side_effect=AssertionError("numeric support accessed"))
        text_support = Mock(side_effect=AssertionError("text support accessed"))
        normalize = Mock(side_effect=AssertionError("normalization accessed"))
        with (
            patch.object(financial_aggregate_projection, "extract_numeric_surface_candidates", extract),
            patch.object(financial_aggregate_projection, "promote_table_numeric_support_evidence", promote),
            patch.object(financial_aggregate_projection, "evidence_supports_numeric_candidates", support),
            patch.object(financial_aggregate_projection, "text_supports_numeric_candidates", text_support),
            patch.object(financial_aggregate_projection, "_normalise_spaces", normalize),
        ):
            empty = owner([], final_answer="answer", selected_claim_ids=IterationBomb())
        self.assertEqual(empty, [])
        extract.assert_called_once_with("answer")
        promote.assert_not_called()
        support.assert_not_called()
        text_support.assert_not_called()
        normalize.assert_not_called()

        nested = {"preserve": True}
        original = {"evidence_id": "existing", "nested": nested}
        evidence_items = [original]
        extract = Mock(return_value=[])
        with (
            patch.object(financial_aggregate_projection, "extract_numeric_surface_candidates", extract),
            patch.object(
                financial_aggregate_projection,
                "promote_table_numeric_support_evidence",
                side_effect=AssertionError("promotion accessed"),
            ),
            patch.object(
                financial_aggregate_projection,
                "evidence_supports_numeric_candidates",
                side_effect=AssertionError("numeric support accessed"),
            ),
        ):
            no_candidates = owner(
                evidence_items,
                final_answer="blank",
                selected_claim_ids=IterationBomb(),
            )
        self.assertEqual(no_candidates, evidence_items)
        self.assertIsNot(no_candidates, evidence_items)
        self.assertIs(no_candidates[0], original)
        self.assertIs(no_candidates[0]["nested"], nested)

        answer_candidates = [{"kind": "percent", "value": 10.0}]
        selected_nested = {"selected": True}
        narrative_nested = {"narrative": True}
        selected_drop = {
            "evidence_id": "selected",
            "claim": "selected 10%",
            "quote_span": "quote without number",
            "raw_row_text": "raw 10%",
            "metadata": {"nested": selected_nested},
        }
        narrative_selected = {
            "evidence_id": "retrieved_narrative::one",
            "claim": "narrative 10%",
            "quote_span": "narrative quote",
            "raw_row_text": "narrative raw",
            "metadata": {"nested": narrative_nested},
        }
        noise = {"evidence_id": "noise", "claim": "noise 99%"}
        recon = {"evidence_id": "recon::keep", "claim": "recon 10%"}
        derived = {
            "evidence_id": "operand::derived",
            "claim": "derived operand",
            "metadata": {"supports_derived_percent": True},
        }
        surface = {
            "evidence_id": "operand::surface",
            "claim": "surface operand",
            "metadata": {"supports_answer_numeric_surface": True},
        }
        late_noise = {"evidence_id": "late", "claim": "late 10%"}
        matrix = [selected_drop, narrative_selected, noise, recon, derived, surface, late_noise]
        before_matrix = deepcopy(matrix)
        events = []
        promoted_by_id = {}

        def support_owner(evidence, candidates):
            self.assertIs(candidates, answer_candidates)
            evidence_id = evidence.get("evidence_id")
            events.append(("support", evidence_id))
            return evidence_id in {"selected", "recon::keep"}

        def promote_owner(evidence, *, final_answer, answer_candidates):
            self.assertEqual(final_answer, "answer 10%")
            self.assertIs(answer_candidates, globals_answer_candidates)
            events.append(("promote", evidence["evidence_id"]))
            promoted = {**evidence, "promoted": evidence["evidence_id"]}
            promoted_by_id[evidence["evidence_id"]] = promoted
            return promoted

        def normalize_owner(value):
            events.append(("normalize", value))
            return " ".join(str(value).split())

        def text_owner(text, candidates):
            self.assertIs(candidates, answer_candidates)
            events.append(("text", text))
            return False

        globals_answer_candidates = answer_candidates
        with (
            patch.object(
                financial_aggregate_projection,
                "extract_numeric_surface_candidates",
                return_value=answer_candidates,
            ),
            patch.object(
                financial_aggregate_projection,
                "evidence_supports_numeric_candidates",
                side_effect=support_owner,
            ),
            patch.object(
                financial_aggregate_projection,
                "promote_table_numeric_support_evidence",
                side_effect=promote_owner,
            ),
            patch.object(financial_aggregate_projection, "text_supports_numeric_candidates", side_effect=text_owner),
            patch.object(financial_aggregate_projection, "_normalise_spaces", side_effect=normalize_owner),
        ):
            filtered = owner(
                matrix,
                final_answer="answer 10%",
                selected_claim_ids=[" selected ", "retrieved_narrative::one"],
            )

        self.assertEqual(
            [row["evidence_id"] for row in filtered],
            ["retrieved_narrative::one", "recon::keep", "operand::derived", "operand::surface"],
        )
        self.assertIsNot(filtered[0], narrative_selected)
        self.assertIs(filtered[0]["metadata"]["nested"], narrative_nested)
        self.assertIs(filtered[1], promoted_by_id["recon::keep"])
        self.assertIs(filtered[2], promoted_by_id["operand::derived"])
        self.assertIs(filtered[3], promoted_by_id["operand::surface"])
        self.assertEqual(matrix, before_matrix)
        self.assertIs(matrix[0]["metadata"]["nested"], selected_nested)
        self.assertEqual(
            events,
            [
                ("support", "selected"),
                ("promote", "selected"),
                ("normalize", "quote without number"),
                ("normalize", "raw 10%"),
                ("text", "quote without number"),
                ("normalize", "narrative quote"),
                ("normalize", "narrative raw"),
                ("promote", "noise"),
                ("promote", "recon::keep"),
                ("support", "recon::keep"),
                ("promote", "operand::derived"),
                ("promote", "operand::surface"),
                ("promote", "late"),
            ],
        )

        fallback_first = {"evidence_id": "first", "nested": nested}
        fallback_second = {"evidence_id": "second"}
        fallback_items = [fallback_first, fallback_second]
        promoted_fallbacks = []

        def promote_fallback(evidence, **_kwargs):
            promoted = {**evidence, "promoted": True}
            promoted_fallbacks.append(promoted)
            return promoted

        with (
            patch.object(
                financial_aggregate_projection,
                "extract_numeric_surface_candidates",
                return_value=[{"kind": "number", "value": 1}],
            ),
            patch.object(
                financial_aggregate_projection,
                "promote_table_numeric_support_evidence",
                side_effect=promote_fallback,
            ),
            patch.object(financial_aggregate_projection, "evidence_supports_numeric_candidates", return_value=False),
        ):
            fallback = owner(fallback_items, final_answer="answer 1", selected_claim_ids=[])
        self.assertEqual(fallback, fallback_items)
        self.assertIsNot(fallback, fallback_items)
        self.assertIs(fallback[0], fallback_first)
        self.assertIs(fallback[1], fallback_second)
        self.assertTrue(all(row is not original for row, original in zip(promoted_fallbacks, fallback_items)))

        later = Mock()
        with (
            patch.object(
                financial_aggregate_projection,
                "extract_numeric_surface_candidates",
                side_effect=RuntimeError("extract failed"),
            ),
            patch.object(financial_aggregate_projection, "promote_table_numeric_support_evidence", later),
            self.assertRaisesRegex(RuntimeError, "extract failed"),
        ):
            owner([{"evidence_id": "one"}], final_answer="answer", selected_claim_ids=[])
        later.assert_not_called()

        later_support = Mock()
        with (
            patch.object(
                financial_aggregate_projection,
                "extract_numeric_surface_candidates",
                return_value=[{"kind": "number"}],
            ),
            patch.object(
                financial_aggregate_projection,
                "promote_table_numeric_support_evidence",
                side_effect=RuntimeError("promotion failed"),
            ),
            patch.object(financial_aggregate_projection, "evidence_supports_numeric_candidates", later_support),
            self.assertRaisesRegex(RuntimeError, "promotion failed"),
        ):
            owner([{"evidence_id": "one"}], final_answer="answer 1", selected_claim_ids=[])
        later_support.assert_not_called()

        operand_surface = {
            "evidence_id": "operand::surface",
            "metadata": {"supports_answer_numeric_surface": True},
        }
        later_promotion = Mock()
        with (
            patch.object(
                financial_aggregate_projection,
                "extract_numeric_surface_candidates",
                return_value=[{"kind": "number"}],
            ),
            patch.object(financial_aggregate_projection, "evidence_supports_numeric_candidates", return_value=True),
            patch.object(
                financial_aggregate_projection,
                "promote_table_numeric_support_evidence",
                side_effect=lambda evidence, **_kwargs: evidence,
            ) as first_promotion,
            patch.object(
                financial_aggregate_projection,
                "text_supports_numeric_candidates",
                side_effect=RuntimeError("text support failed"),
            ),
            self.assertRaisesRegex(RuntimeError, "text support failed"),
        ):
            owner(
                [selected_drop, operand_surface, {"evidence_id": "later"}],
                final_answer="answer 1",
                selected_claim_ids=["selected"],
            )
        self.assertEqual(first_promotion.call_count, 1)
        later_promotion.assert_not_called()

    def test_current_source_operand_evidence_append_pins_schema_order_copies_and_exceptions(self) -> None:
        owner = financial_aggregate_projection.append_operand_evidence_for_final_answer

        class IterationBomb:
            def __iter__(self):
                raise AssertionError("operands accessed")

        nested = {"preserve": True}
        existing_row = {"evidence_id": "existing", "nested": nested}
        evidence_items = [existing_row]
        with (
            patch.object(
                financial_aggregate_projection,
                "extract_numeric_surface_candidates",
                return_value=[{"kind": "number", "value": 1}],
            ) as extract,
            patch.object(
                financial_aggregate_projection,
                "_normalise_spaces",
                side_effect=AssertionError("normalization accessed"),
            ),
        ):
            no_operands = owner(
                evidence_items,
                operands=[],
                final_answer="answer 1",
            )
        extract.assert_called_once_with("answer 1")
        self.assertEqual(no_operands, evidence_items)
        self.assertIsNot(no_operands, evidence_items)
        self.assertIs(no_operands[0], existing_row)

        with (
            patch.object(financial_aggregate_projection, "extract_numeric_surface_candidates", return_value=[]),
            patch.object(
                financial_aggregate_projection,
                "_normalise_spaces",
                side_effect=AssertionError("normalization accessed"),
            ),
        ):
            no_candidates = owner(
                evidence_items,
                operands=IterationBomb(),
                final_answer="blank",
            )
        self.assertEqual(no_candidates, evidence_items)
        self.assertIs(no_candidates[0], existing_row)

        answer_candidates = [{"kind": "percent", "value": 70.0}]
        supported_candidate = {"kind": "number", "value": 100.0}
        derived_candidate = {"kind": "number", "value": 200.0}
        unsupported_candidate = {"kind": "number", "value": 300.0}
        supported_nested = {"supported": True}
        supported = {
            "operand_id": "supported",
            "label": "metric",
            "period": "2023",
            "raw_value": "100",
            "raw_unit": "KRW",
            "source_anchor": "[source-a]",
            "source_quote": "source quote 100",
            "role": "other",
            "normalized_unit": "KRW",
            "nested": supported_nested,
        }
        duplicate = {
            **supported,
            "raw_value": "101",
            "source_anchor": "[duplicate]",
        }
        derived = {
            "operand_id": "derived",
            "label": "prior",
            "period": "2022",
            "value": "200",
            "raw_unit": "KRW",
            "source_anchor": "[source-b]",
            "quote_span": "source quote 200",
            "matched_operand_role": "prior_period",
            "normalized_unit": " krw ",
        }
        unsupported = {
            "operand_id": "unsupported",
            "label": "noise",
            "period": "2021",
            "raw_value": "300",
            "raw_unit": "USD",
            "source_anchor": "[source-c]",
            "raw_row_text": "source quote 300",
            "role": "other",
            "normalized_unit": "USD",
        }
        literal = {
            "operand_id": "literal",
            "label": "literal",
            "period": "2020",
            "rendered_value": "4,000 KRW",
            "display": "display fallback bomb",
            "source_anchor": "[source-d]",
            "raw_row_text": "literal source",
            "role": "other",
            "normalized_unit": "KRW",
        }
        missing_value = {"operand_id": "missing", "source_anchor": "[source-e]"}
        missing_anchor = {"operand_id": "anchorless", "raw_value": "500"}
        operands = [supported, duplicate, derived, unsupported, literal, missing_value, missing_anchor]
        before_evidence = deepcopy(evidence_items)
        before_operands = deepcopy(operands)
        events = []

        def extract_owner(text):
            events.append(("extract", text))
            if text == "answer 70% includes 4,000 KRW":
                return answer_candidates
            if "100" in text or "101" in text:
                return [supported_candidate]
            if "200" in text:
                return [derived_candidate]
            if "300" in text:
                return [unsupported_candidate]
            if "4,000 KRW" in text:
                return [{"kind": "number", "value": 4000.0}]
            return []

        def equivalent(answer_candidate, operand_candidate):
            events.append(("equivalent", answer_candidate, operand_candidate))
            return operand_candidate is supported_candidate

        def normalize_owner(value):
            events.append(("normalize", value))
            return " ".join(str(value).split())

        with (
            patch.object(financial_aggregate_projection, "extract_numeric_surface_candidates", side_effect=extract_owner),
            patch.object(
                financial_aggregate_projection,
                "numeric_surface_candidates_equivalent",
                side_effect=equivalent,
            ),
            patch.object(financial_aggregate_projection, "_normalise_spaces", side_effect=normalize_owner),
        ):
            updated = owner(
                evidence_items,
                operands=operands,
                final_answer="answer 70% includes 4,000 KRW",
            )

        self.assertEqual(
            [row["evidence_id"] for row in updated],
            ["existing", "operand::supported", "operand::derived", "operand::literal"],
        )
        self.assertIsNot(updated, evidence_items)
        self.assertIsNot(updated[0], existing_row)
        self.assertIs(updated[0]["nested"], nested)
        supported_evidence = updated[1]
        self.assertEqual(
            supported_evidence,
            {
                "evidence_id": "operand::supported",
                "source_anchor": "[source-a]",
                "claim": "metric 2023 100KRW",
                "quote_span": "source quote 100",
                "support_level": "direct",
                "question_relevance": "high",
                "metadata": {
                    "section_path": "[source-a]",
                    "unit_hint": "KRW",
                    "operand_role": "other",
                    "supports_derived_percent": False,
                    "supports_answer_numeric_surface": False,
                },
            },
        )
        derived_evidence = updated[2]
        self.assertEqual(derived_evidence["quote_span"], "source quote 200")
        self.assertTrue(derived_evidence["metadata"]["supports_derived_percent"])
        self.assertFalse(derived_evidence["metadata"]["supports_answer_numeric_surface"])
        literal_evidence = updated[3]
        self.assertEqual(literal_evidence["claim"], "literal 2020 4,000 KRW")
        self.assertTrue(literal_evidence["metadata"]["supports_answer_numeric_surface"])
        self.assertEqual(evidence_items, before_evidence)
        self.assertEqual(operands, before_operands)
        self.assertIs(operands[0]["nested"], supported_nested)
        self.assertEqual(
            [event for event in events if event[0] == "extract"],
            [
                ("extract", "answer 70% includes 4,000 KRW"),
                ("extract", "metric 2023 100KRW"),
                ("extract", "metric 2023 101KRW"),
                ("extract", "prior 2022 200KRW"),
                ("extract", "noise 2021 300USD"),
                ("extract", "literal 2020 4,000 KRW"),
            ],
        )
        self.assertEqual(
            sum(1 for event in events if event[0] == "equivalent"),
            5,
        )

        matched_role_fallback = {
            "matched_operand_role": "numerator",
            "raw_value": "7",
            "raw_unit": "KRW",
            "source_anchor": "[source-f]",
            "normalized_unit": "KRW",
        }
        default_id = {
            "raw_value": "8",
            "source_anchor": "[source-g]",
        }
        with (
            patch.object(
                financial_aggregate_projection,
                "extract_numeric_surface_candidates",
                side_effect=lambda text: answer_candidates if text == "70%" else [{"kind": "number"}],
            ),
            patch.object(financial_aggregate_projection, "numeric_surface_candidates_equivalent", return_value=True),
        ):
            fallback_ids = owner(
                [],
                operands=[matched_role_fallback, default_id],
                final_answer="70%",
            )
        self.assertEqual(
            [row["evidence_id"] for row in fallback_ids],
            ["operand::numerator", "operand::operand"],
        )

        downstream = Mock()
        with (
            patch.object(
                financial_aggregate_projection,
                "extract_numeric_surface_candidates",
                side_effect=RuntimeError("answer extraction failed"),
            ),
            patch.object(financial_aggregate_projection, "_normalise_spaces", downstream),
            self.assertRaisesRegex(RuntimeError, "answer extraction failed"),
        ):
            owner([], operands=[supported], final_answer="answer")
        downstream.assert_not_called()

        later_extract = Mock()

        def failing_normalize(value):
            if value == "[source-a]":
                raise RuntimeError("anchor normalization failed")
            return " ".join(str(value).split())

        with (
            patch.object(
                financial_aggregate_projection,
                "extract_numeric_surface_candidates",
                side_effect=[answer_candidates],
            ) as answer_extract,
            patch.object(financial_aggregate_projection, "_normalise_spaces", side_effect=failing_normalize),
            patch.object(financial_aggregate_projection, "numeric_surface_candidates_equivalent", later_extract),
            self.assertRaisesRegex(RuntimeError, "anchor normalization failed"),
        ):
            owner([], operands=[supported, derived], final_answer="70%")
        answer_extract.assert_called_once_with("70%")
        later_extract.assert_not_called()

        equivalence_failure = Mock(side_effect=RuntimeError("equivalence failed"))
        with (
            patch.object(
                financial_aggregate_projection,
                "extract_numeric_surface_candidates",
                side_effect=[answer_candidates, [supported_candidate]],
            ),
            patch.object(
                financial_aggregate_projection,
                "numeric_surface_candidates_equivalent",
                equivalence_failure,
            ),
            self.assertRaisesRegex(RuntimeError, "equivalence failed"),
        ):
            owner([], operands=[supported, derived], final_answer="70%")
        equivalence_failure.assert_called_once_with(answer_candidates[0], supported_candidate)

    def test_current_source_final_answer_evidence_bindings_pin_defs_calls_dag_and_baseline(self) -> None:
        from pathlib import Path

        module_sources = {
            "calculation": inspect.getsource(financial_graph_calculation),
            "graph": inspect.getsource(financial_graph),
            "owner": inspect.getsource(financial_aggregate_projection),
        }
        module_trees = {name: ast.parse(source) for name, source in module_sources.items()}
        current_targets = {
            "filter": "filter_aggregate_evidence_for_final_answer",
            "append": "append_operand_evidence_for_final_answer",
        }
        retired_targets = {key: f"_{value}" for key, value in current_targets.items()}
        definitions = {}
        all_definition_names = set()
        calls = {key: [] for key in current_targets}
        retired_calls = {key: [] for key in retired_targets}
        noncall_refs = []

        for module_name, tree in module_trees.items():
            parents = {}
            function_stack = []
            try_depth = 0

            for node in ast.walk(tree):
                for child in ast.iter_child_nodes(node):
                    parents[child] = node

            class BindingVisitor(ast.NodeVisitor):
                def visit_FunctionDef(self, node):
                    nonlocal function_stack
                    all_definition_names.add(node.name)
                    if node.name in {*current_targets.values(), *retired_targets.values()}:
                        definitions[node.name] = (module_name, node)
                    function_stack.append(node.name)
                    self.generic_visit(node)
                    function_stack.pop()

                visit_AsyncFunctionDef = visit_FunctionDef

                def visit_Try(self, node):
                    nonlocal try_depth
                    try_depth += 1
                    self.generic_visit(node)
                    try_depth -= 1

                visit_TryStar = visit_Try

                def visit_Call(self, node):
                    called_name = (
                        node.func.id
                        if isinstance(node.func, ast.Name)
                        else node.func.attr
                        if isinstance(node.func, ast.Attribute)
                        else ""
                    )
                    receiver = ast.unparse(node.func.value) if isinstance(node.func, ast.Attribute) else ""
                    entry = (
                        module_name,
                        tuple(function_stack),
                        receiver,
                        tuple(ast.unparse(arg) for arg in node.args),
                        tuple((kw.arg, ast.unparse(kw.value)) for kw in node.keywords),
                        try_depth,
                    )
                    for key, target in current_targets.items():
                        if called_name == target:
                            calls[key].append(entry)
                    for key, target in retired_targets.items():
                        if called_name == target:
                            retired_calls[key].append(entry)
                    self.generic_visit(node)

                def visit_Attribute(self, node):
                    if node.attr in {*current_targets.values(), *retired_targets.values()}:
                        parent = parents.get(node)
                        if not (isinstance(parent, ast.Call) and parent.func is node):
                            noncall_refs.append((module_name, node.attr, node.lineno))
                    self.generic_visit(node)

                def visit_Name(self, node):
                    if node.id in {*current_targets.values(), *retired_targets.values()}:
                        parent = parents.get(node)
                        if not (isinstance(parent, ast.Call) and parent.func is node):
                            noncall_refs.append((module_name, node.id, node.lineno))
                    self.generic_visit(node)

            BindingVisitor().visit(tree)

        self.assertEqual(
            {
                name: (module_name, node.end_lineno - node.lineno + 1)
                for name, (module_name, node) in definitions.items()
            },
            {
                current_targets["filter"]: ("owner", 65),
                current_targets["append"]: ("owner", 101),
            },
        )
        self.assertTrue(set(retired_targets.values()).isdisjoint(all_definition_names))
        self.assertEqual({key: len(entries) for key, entries in calls.items()}, {"filter": 3, "append": 4})
        self.assertEqual({key: len(entries) for key, entries in retired_calls.items()}, {"filter": 0, "append": 0})
        self.assertEqual(noncall_refs, [])
        self.assertTrue(
            all(
                receiver == "" and try_depth == 0
                for entries in calls.values()
                for _module, _stack, receiver, _args, _kwargs, try_depth in entries
            )
        )
        self.assertEqual(
            Counter(stack[-1] for _module, stack, *_rest in calls["filter"]),
            Counter(
                {
                    "_filter_final_aggregate_evidence_and_projection": 1,
                    "_runtime_evidence_from_retrieved_docs": 2,
                }
            ),
        )
        self.assertEqual(
            Counter(stack[-1] for _module, stack, *_rest in calls["append"]),
            Counter(
                {
                    "_replace_mutable_aggregate_answer": 1,
                    "_apply_final_narrative_repair_pipeline": 2,
                    "_runtime_evidence_from_retrieved_docs": 1,
                }
            ),
        )
        self.assertEqual(
            Counter(module for module, *_rest in calls["filter"]),
            Counter({"calculation": 1, "graph": 2}),
        )
        self.assertEqual(
            Counter(module for module, *_rest in calls["append"]),
            Counter({"calculation": 3, "graph": 1}),
        )
        self.assertEqual(
            Counter((args, kwargs) for _module, _stack, _receiver, args, kwargs, _depth in calls["filter"]),
            Counter(
                {
                    (
                        ("aggregate_evidence_items",),
                        (("final_answer", "final_answer"), ("selected_claim_ids", "selected_claim_ids")),
                    ): 1,
                    (
                        ("evidence_items",),
                        (
                            ("final_answer", "final_answer"),
                            ("selected_claim_ids", "list(final.get('selected_claim_ids') or [])"),
                        ),
                    ): 1,
                    (
                        ("evidence_items",),
                        (("final_answer", "final_answer"), ("selected_claim_ids", "[]")),
                    ): 1,
                }
            ),
        )
        self.assertEqual(
            Counter((args, kwargs) for _module, _stack, _receiver, args, kwargs, _depth in calls["append"]),
            Counter(
                {
                    (
                        ("evidence_items",),
                        (
                            ("operands", "list(aggregate_projection.get('calculation_operands') or [])"),
                            ("final_answer", "candidate_answer"),
                        ),
                    ): 1,
                    (
                        ("aggregate_evidence_items",),
                        (
                            ("operands", "list(aggregate_projection.get('calculation_operands') or [])"),
                            ("final_answer", "final_answer"),
                        ),
                    ): 2,
                    (
                        ("existing",),
                        (("operands", "operands"), ("final_answer", "final_answer")),
                    ): 1,
                }
            ),
        )
        self.assertEqual(
            {
                "filter": (sum(len(stack) == 1 for _module, stack, *_rest in calls["filter"]), 0),
                "append": (sum(len(stack) == 1 for _module, stack, *_rest in calls["append"]), 0),
            },
            {"filter": (3, 0), "append": (4, 0)},
        )
        self.assertEqual(
            {
                key: definitions[current_targets[key]][1].end_lineno
                - definitions[current_targets[key]][1].lineno
                + 1
                for key in current_targets
            },
            {"filter": 65, "append": 101},
        )

        owner_numeric_imports = set()
        calculation_numeric_imports = set()
        for module_name in ("owner", "calculation"):
            for node in ast.walk(module_trees[module_name]):
                if isinstance(node, ast.ImportFrom) and node.module == "src.agent.financial_numeric_surface":
                    names = {alias.name for alias in node.names}
                    if module_name == "owner":
                        owner_numeric_imports.update(names)
                    else:
                        calculation_numeric_imports.update(names)
        owner_additions = {
            "evidence_supports_numeric_candidates",
            "promote_table_numeric_support_evidence",
            "text_supports_numeric_candidates",
        }
        self.assertTrue(owner_additions.issubset(owner_numeric_imports))
        self.assertNotIn("evidence_supports_numeric_candidates", calculation_numeric_imports)
        self.assertNotIn("promote_table_numeric_support_evidence", calculation_numeric_imports)
        self.assertIn("text_supports_numeric_candidates", calculation_numeric_imports)

        selected_ranges = [
            (
                definitions[current_targets[key]][1].lineno,
                definitions[current_targets[key]][1].end_lineno,
            )
            for key in ("filter", "append")
        ]
        outside_loads = {}
        for name in owner_additions:
            outside_loads[name] = [
                node.lineno
                for node in ast.walk(module_trees["calculation"])
                if isinstance(node, ast.Name)
                and isinstance(node.ctx, ast.Load)
                and node.id == name
            ]
        self.assertEqual(outside_loads["evidence_supports_numeric_candidates"], [])
        self.assertEqual(outside_loads["promote_table_numeric_support_evidence"], [])
        self.assertEqual(len(outside_loads["text_supports_numeric_candidates"]), 1)

        project_root = Path(inspect.getfile(financial_graph_calculation)).resolve().parents[2]
        module_edges = {}
        for path in (project_root / "src" / "agent").glob("*.py"):
            module_name = f"src.agent.{path.stem}"
            imported = set()
            tree = ast.parse(path.read_text(encoding="utf-8-sig"))
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("src.agent."):
                    imported.add(node.module)
                elif isinstance(node, ast.Import):
                    imported.update(alias.name for alias in node.names if alias.name.startswith("src.agent."))
            module_edges[module_name] = imported

        def reachable(source, target):
            seen = set()
            pending = list(module_edges.get(source, ()))
            while pending:
                current = pending.pop()
                if current == target:
                    return True
                if current in seen:
                    continue
                seen.add(current)
                pending.extend(module_edges.get(current, ()))
            return False

        aggregate_module = "src.agent.financial_aggregate_projection"
        calculation_module = "src.agent.financial_graph_calculation"
        graph_module = "src.agent.financial_graph"
        numeric_module = "src.agent.financial_numeric_surface"
        self.assertTrue(reachable(calculation_module, aggregate_module))
        self.assertTrue(reachable(graph_module, aggregate_module))
        self.assertFalse(reachable(aggregate_module, calculation_module))
        self.assertFalse(reachable(aggregate_module, graph_module))
        self.assertTrue(reachable(aggregate_module, numeric_module))
        self.assertFalse(reachable(numeric_module, aggregate_module))

        from src.ops.audit_runtime_domain_terms import (
            collect_runtime_domain_term_occurrences,
            collect_runtime_domain_terms,
        )

        records = collect_runtime_domain_terms(project_root)
        occurrences = collect_runtime_domain_term_occurrences(project_root)
        selected_hits = [
            row
            for row in occurrences
            if row["path"] == "src/agent/financial_aggregate_projection.py"
            and any(start <= row["line"] <= end for start, end in selected_ranges)
        ]
        self.assertEqual(len(records), 217)
        self.assertEqual(selected_hits, [])

    def test_current_source_runtime_evidence_caller_pins_combined_args_adoption_and_stop(self) -> None:
        nested = {"preserve": True}
        existing_row = {"evidence_id": "existing", "nested": nested}
        operand = {"operand_id": "one", "nested": nested}
        final = {
            "answer": " answer 10 ",
            "evidence_items": [existing_row],
            "selected_claim_ids": [" selected ", ""],
            "nested": nested,
        }
        before_final = deepcopy(final)
        events = []

        class Agent:
            pass

        agent = Agent()
        trace_projection = {"calculation_operands": [operand]}
        agent._project_runtime_calculation_trace = Mock(
            side_effect=lambda value: events.append(("project", value))
            or trace_projection
        )
        appended = [{"evidence_id": "operand::one", "nested": nested}]
        filtered_rows = [{"evidence_id": f"filtered-{index}"} for index in range(10)]

        def append_owner(items, *, operands, final_answer):
            events.append(("append", items, operands, final_answer))
            return appended

        def filter_owner(items, *, final_answer, selected_claim_ids):
            events.append(("filter", items, final_answer, selected_claim_ids))
            return filtered_rows

        append_projection = Mock(side_effect=append_owner)
        filter_projection = Mock(side_effect=filter_owner)
        enriched = [{"evidence_id": "enriched"}]

        def enrich_owner(value, items):
            events.append(("enrich", value, items))
            return enriched

        agent._enrich_runtime_evidence_metadata = Mock(side_effect=enrich_owner)

        def normalize(value):
            events.append(("normalize", value))
            return " ".join(str(value).split())

        answer_candidates = [{"kind": "number", "value": 10}]
        with (
            patch.object(financial_graph, "_normalise_spaces", side_effect=normalize),
            patch.object(
                financial_graph,
                "extract_numeric_surface_candidates",
                side_effect=lambda value: events.append(("extract", value)) or answer_candidates,
            ),
            patch.object(financial_graph, "append_operand_evidence_for_final_answer", append_projection),
            patch.object(financial_graph, "filter_aggregate_evidence_for_final_answer", filter_projection),
        ):
            result = financial_graph.FinancialAgent._runtime_evidence_from_retrieved_docs(agent, final)

        self.assertIs(result, enriched)
        self.assertEqual([event[0] for event in events], ["normalize", "extract", "project", "append", "filter", "enrich"])
        append_call = append_projection.call_args
        prepared_existing = append_call.args[0]
        self.assertEqual(prepared_existing, [existing_row])
        self.assertIsNot(prepared_existing, final["evidence_items"])
        self.assertIsNot(prepared_existing[0], existing_row)
        self.assertIs(prepared_existing[0]["nested"], nested)
        self.assertEqual(append_call.kwargs["operands"], [operand])
        self.assertIsNot(append_call.kwargs["operands"], trace_projection["calculation_operands"])
        self.assertIs(append_call.kwargs["operands"][0], operand)
        self.assertEqual(append_call.kwargs["final_answer"], "answer 10")
        filter_call = filter_projection.call_args
        self.assertIs(filter_call.args[0], appended)
        self.assertEqual(filter_call.kwargs["final_answer"], "answer 10")
        self.assertEqual(filter_call.kwargs["selected_claim_ids"], [" selected ", ""])
        self.assertIsNot(filter_call.kwargs["selected_claim_ids"], final["selected_claim_ids"])
        enrich_call = agent._enrich_runtime_evidence_metadata.call_args
        self.assertIs(enrich_call.args[0], final)
        self.assertEqual(enrich_call.args[1], filtered_rows[:8])
        self.assertIsNot(enrich_call.args[1], filtered_rows)
        self.assertTrue(all(a is b for a, b in zip(enrich_call.args[1], filtered_rows)))
        self.assertEqual(final, before_final)
        self.assertIs(final["nested"], nested)

        retrieved_nested = {"retrieved": True}
        retrieved_doc = {
            "page_content": " retrieved 20 ",
            "metadata": {"source_anchor": " [source] ", "nested": retrieved_nested},
        }
        fallback_final = {
            "answer": "answer 20",
            "evidence_items": [],
            "selected_claim_ids": ["missing"],
            "seed_retrieved_docs": [(retrieved_doc, 0.9)],
            "retrieved_docs": [retrieved_doc],
        }
        before_fallback = deepcopy(fallback_final)
        fallback_agent = Agent()
        fallback_agent._project_runtime_calculation_trace = Mock(return_value={"calculation_operands": []})
        fallback_append = Mock(return_value=[])
        second_filtered = [{"evidence_id": "retrieved::kept"}]
        fallback_filter = Mock(side_effect=[[], second_filtered])
        fallback_enriched = [{"evidence_id": "fallback-enriched"}]
        fallback_agent._enrich_runtime_evidence_metadata = Mock(return_value=fallback_enriched)
        with (
            patch.object(financial_graph, "_normalise_spaces", side_effect=lambda value: " ".join(str(value).split())),
            patch.object(
                financial_graph,
                "extract_numeric_surface_candidates",
                return_value=[{"kind": "number", "value": 20}],
            ),
            patch.object(financial_graph, "append_operand_evidence_for_final_answer", fallback_append),
            patch.object(financial_graph, "filter_aggregate_evidence_for_final_answer", fallback_filter),
        ):
            fallback_result = financial_graph.FinancialAgent._runtime_evidence_from_retrieved_docs(
                fallback_agent,
                fallback_final,
            )
        self.assertIs(fallback_result, fallback_enriched)
        self.assertEqual(fallback_filter.call_count, 2)
        first_filter, second_filter = fallback_filter.call_args_list
        self.assertIs(first_filter.args[0], fallback_append.return_value)
        self.assertEqual(first_filter.kwargs["selected_claim_ids"], ["missing"])
        generated = second_filter.args[0]
        self.assertEqual(len(generated), 1)
        self.assertEqual(generated[0]["evidence_id"], "retrieved::001")
        self.assertEqual(generated[0]["claim"], "retrieved 20")
        self.assertIs(generated[0]["metadata"]["nested"], retrieved_nested)
        self.assertEqual(second_filter.kwargs, {"final_answer": "answer 20", "selected_claim_ids": []})
        fallback_agent._enrich_runtime_evidence_metadata.assert_called_once_with(fallback_final, second_filtered)
        self.assertEqual(fallback_final, before_fallback)
        self.assertIs(fallback_final["seed_retrieved_docs"][0][0]["metadata"]["nested"], retrieved_nested)

        stopped_filter = Mock()
        stopped_enrich = Mock()
        failing_agent = Agent()
        failing_agent._project_runtime_calculation_trace = Mock(return_value={"calculation_operands": [operand]})
        failing_agent._enrich_runtime_evidence_metadata = stopped_enrich
        failing_append = Mock(side_effect=RuntimeError("append failed"))
        with (
            patch.object(financial_graph, "_normalise_spaces", return_value="answer 10"),
            patch.object(
                financial_graph,
                "extract_numeric_surface_candidates",
                return_value=answer_candidates,
            ),
            patch.object(financial_graph, "append_operand_evidence_for_final_answer", failing_append),
            patch.object(financial_graph, "filter_aggregate_evidence_for_final_answer", stopped_filter),
            self.assertRaisesRegex(RuntimeError, "append failed"),
        ):
            financial_graph.FinancialAgent._runtime_evidence_from_retrieved_docs(failing_agent, final)
        stopped_filter.assert_not_called()
        stopped_enrich.assert_not_called()

    def test_current_source_final_filter_caller_pins_provenance_adoption_and_stop(self) -> None:
        from types import SimpleNamespace

        nested = {"preserve": True}
        aggregate_evidence_items = [{"evidence_id": "input", "nested": nested}]
        aggregate_projection = {"calculation_result": {"nested": nested}}
        selected_claim_ids = ["drop", "keep", "keep"]
        filtered_items = [
            {"evidence_id": "keep", "nested": nested},
            {"evidence_id": "operand::one"},
            {"evidence_id": "keep"},
            {"evidence_id": ""},
        ]
        provenance_projection = {"provenance": True, "nested": nested}
        appended_projection = {"appended": True, "nested": nested}
        events = []

        class Agent:
            pass

        agent = Agent()

        def filter_owner(items, *, final_answer, selected_claim_ids):
            events.append(("filter", items, final_answer, selected_claim_ids))
            return filtered_items

        filter_projection = Mock(side_effect=filter_owner)

        def provenance_owner(value):
            events.append(("provenance", value))
            self.assertIs(value.aggregate_projection, aggregate_projection)
            self.assertEqual(value.kept_evidence_ids, ["keep", "operand::one", "keep"])
            return SimpleNamespace(aggregate_projection=provenance_projection)

        def append_surface(projection, items, *, final_answer):
            events.append(("append-surface", projection, items, final_answer))
            return appended_projection

        append_owner = Mock(side_effect=append_surface)
        before_evidence = deepcopy(aggregate_evidence_items)
        before_projection = deepcopy(aggregate_projection)
        before_selected = list(selected_claim_ids)
        with patch.object(
            financial_graph_calculation,
            "filter_aggregate_projection_provenance",
            side_effect=provenance_owner,
        ) as provenance, patch.object(
            financial_graph_calculation,
            "filter_aggregate_evidence_for_final_answer",
            filter_projection,
        ), patch.object(
            financial_graph_calculation,
            "append_final_answer_surface_operands_from_evidence",
            append_owner,
        ):
            result = financial_graph_calculation.FinancialAgentCalculationMixin._filter_final_aggregate_evidence_and_projection(
                agent,
                aggregate_evidence_items,
                aggregate_projection,
                final_answer="answer 10",
                selected_claim_ids=selected_claim_ids,
            )

        self.assertEqual([event[0] for event in events], ["filter", "provenance", "append-surface"])
        returned_items, returned_projection, returned_selected, kept_ids = result
        self.assertIs(returned_items, filtered_items)
        self.assertIs(returned_projection, appended_projection)
        self.assertEqual(returned_selected, ["keep", "operand::one"])
        self.assertEqual(kept_ids, ["keep", "operand::one", "keep"])
        filter_call = filter_projection.call_args
        self.assertIs(filter_call.args[0], aggregate_evidence_items)
        self.assertEqual(filter_call.kwargs, {"final_answer": "answer 10", "selected_claim_ids": selected_claim_ids})
        self.assertIs(filter_call.kwargs["selected_claim_ids"], selected_claim_ids)
        provenance.assert_called_once()
        append_call = append_owner.call_args
        self.assertIs(append_call.args[0], provenance_projection)
        self.assertIs(append_call.args[1], filtered_items)
        self.assertEqual(append_call.kwargs, {"final_answer": "answer 10"})
        self.assertEqual(aggregate_evidence_items, before_evidence)
        self.assertEqual(aggregate_projection, before_projection)
        self.assertEqual(selected_claim_ids, before_selected)
        self.assertIs(aggregate_evidence_items[0]["nested"], nested)

        later_provenance = Mock()
        later_append = Mock()
        failing_agent = Agent()
        failing_filter = Mock(side_effect=RuntimeError("filter failed"))
        with (
            patch.object(financial_graph_calculation, "filter_aggregate_projection_provenance", later_provenance),
            patch.object(
                financial_graph_calculation,
                "filter_aggregate_evidence_for_final_answer",
                failing_filter,
            ),
            patch.object(
                financial_graph_calculation,
                "append_final_answer_surface_operands_from_evidence",
                later_append,
            ),
            self.assertRaisesRegex(RuntimeError, "filter failed"),
        ):
            financial_graph_calculation.FinancialAgentCalculationMixin._filter_final_aggregate_evidence_and_projection(
                failing_agent,
                aggregate_evidence_items,
                aggregate_projection,
                final_answer="answer 10",
                selected_claim_ids=selected_claim_ids,
            )
        later_provenance.assert_not_called()
        later_append.assert_not_called()

        failing_append = Mock()
        provenance_failure_agent = Agent()
        successful_filter = Mock(return_value=filtered_items)
        with (
            patch.object(
                financial_graph_calculation,
                "filter_aggregate_projection_provenance",
                side_effect=RuntimeError("provenance failed"),
            ),
            patch.object(
                financial_graph_calculation,
                "filter_aggregate_evidence_for_final_answer",
                successful_filter,
            ),
            patch.object(
                financial_graph_calculation,
                "append_final_answer_surface_operands_from_evidence",
                failing_append,
            ),
            self.assertRaisesRegex(RuntimeError, "provenance failed"),
        ):
            financial_graph_calculation.FinancialAgentCalculationMixin._filter_final_aggregate_evidence_and_projection(
                provenance_failure_agent,
                aggregate_evidence_items,
                aggregate_projection,
                final_answer="answer 10",
                selected_claim_ids=selected_claim_ids,
            )
        failing_append.assert_not_called()

    def test_current_source_operand_append_callers_pin_mutable_and_narrative_order_stop(self) -> None:
        from types import SimpleNamespace

        nested = {"preserve": True}
        ordered_results = [{"task_id": "one", "nested": nested}]
        operand = {"operand_id": "one", "nested": nested}
        aggregate_projection = {"calculation_operands": [operand], "nested": nested}
        evidence_items = [{"evidence_id": "existing", "nested": nested}]
        mutable_state = financial_graph_calculation._AggregateMutableState(
            financial_graph_calculation._AggregateSynthesisState(
                ordered_results,
                aggregate_projection,
                "old answer",
                ["claim-one"],
            ),
            evidence_items,
        )
        before_rows = deepcopy(ordered_results)
        before_projection = deepcopy(aggregate_projection)
        before_evidence = deepcopy(evidence_items)

        class Agent:
            pass

        replacement_agent = Agent()
        synced_projection = {"calculation_operands": [operand], "synced": True, "nested": nested}
        appended_evidence = [{"evidence_id": "operand::one", "nested": nested}]
        replacement_append = Mock(return_value=appended_evidence)
        sync_inputs = []

        def sync_owner(value):
            sync_inputs.append(value)
            self.assertIs(value.aggregate_projection, aggregate_projection)
            self.assertEqual(value.final_answer, "candidate answer")
            self.assertTrue(value.sync_rendered_for_aggregate)
            self.assertTrue(value.status_ok)
            return SimpleNamespace(aggregate_projection=synced_projection)

        with (
            patch.object(
                financial_graph_calculation,
                "_normalise_spaces",
                side_effect=lambda value: " ".join(str(value).split()),
            ),
            patch.object(
                financial_graph_calculation,
                "sync_aggregate_projection_final_answer",
                side_effect=sync_owner,
            ) as sync,
            patch.object(
                financial_graph_calculation,
                "append_operand_evidence_for_final_answer",
                replacement_append,
            ),
        ):
            updated_state, changed = financial_graph_calculation.FinancialAgentCalculationMixin._replace_mutable_aggregate_answer(
                replacement_agent,
                mutable_state,
                candidate_answer="  candidate answer  ",
                sync_rendered_for_aggregate=True,
                status_ok=True,
                refresh_operand_evidence=True,
            )
        self.assertTrue(changed)
        sync.assert_called_once()
        append_call = replacement_append.call_args
        self.assertIs(append_call.args[0], evidence_items)
        self.assertEqual(append_call.kwargs["operands"], [operand])
        self.assertIsNot(append_call.kwargs["operands"], synced_projection["calculation_operands"])
        self.assertIs(append_call.kwargs["operands"][0], operand)
        self.assertEqual(append_call.kwargs["final_answer"], "candidate answer")
        self.assertIs(updated_state.evidence_items, appended_evidence)
        self.assertIs(updated_state.aggregate_projection, synced_projection)
        self.assertIs(updated_state.ordered_results, ordered_results)
        self.assertIs(updated_state.selected_claim_ids, mutable_state.selected_claim_ids)
        self.assertEqual(updated_state.final_answer, "candidate answer")
        self.assertEqual(ordered_results, before_rows)
        self.assertEqual(aggregate_projection, before_projection)
        self.assertEqual(evidence_items, before_evidence)
        self.assertIs(ordered_results[0]["nested"], nested)

        skipped_sync = Mock()
        skipped_append = Mock()
        skip_agent = Agent()
        with (
            patch.object(financial_graph_calculation, "_normalise_spaces", return_value="old answer"),
            patch.object(financial_graph_calculation, "sync_aggregate_projection_final_answer", skipped_sync),
            patch.object(
                financial_graph_calculation,
                "append_operand_evidence_for_final_answer",
                skipped_append,
            ),
        ):
            same_state, changed = financial_graph_calculation.FinancialAgentCalculationMixin._replace_mutable_aggregate_answer(
                skip_agent,
                mutable_state,
                candidate_answer="old answer",
                refresh_operand_evidence=True,
            )
        self.assertIs(same_state, mutable_state)
        self.assertFalse(changed)
        skipped_sync.assert_not_called()
        skipped_append.assert_not_called()

        failure_agent = Agent()
        failing_append = Mock(side_effect=RuntimeError("mutable append failed"))
        with (
            patch.object(financial_graph_calculation, "_normalise_spaces", return_value="candidate answer"),
            patch.object(
                financial_graph_calculation,
                "sync_aggregate_projection_final_answer",
                return_value=SimpleNamespace(aggregate_projection=synced_projection),
            ),
            patch.object(
                financial_graph_calculation,
                "append_operand_evidence_for_final_answer",
                failing_append,
            ),
            self.assertRaisesRegex(RuntimeError, "mutable append failed"),
        ):
            financial_graph_calculation.FinancialAgentCalculationMixin._replace_mutable_aggregate_answer(
                failure_agent,
                mutable_state,
                candidate_answer="candidate answer",
                refresh_operand_evidence=True,
            )
        self.assertEqual(aggregate_projection, before_projection)
        self.assertEqual(evidence_items, before_evidence)

        narrative_docs = [{"page_content": "source", "nested": nested}]
        before_docs = deepcopy(narrative_docs)
        pipeline_events = []
        first_evidence = [{"evidence_id": "operand::first", "nested": nested}]
        repaired_operand = {"operand_id": "repaired", "nested": nested}
        repaired_projection = {"calculation_operands": [repaired_operand], "repaired": True}

        pipeline_agent = Agent()
        pipeline_agent._preserve_policy_required_realized_context = Mock(
            side_effect=lambda answer, **_kwargs: pipeline_events.append(("realize", answer)) or "realized answer"
        )

        def replace_owner(current, *, candidate_answer, **kwargs):
            pipeline_events.append(("replace", candidate_answer, kwargs))
            return current.with_updates(final_answer=candidate_answer), True

        pipeline_agent._replace_mutable_aggregate_answer = Mock(side_effect=replace_owner)

        def append_owner(items, *, operands, final_answer):
            pipeline_events.append(("append", items, operands, final_answer))
            if len([event for event in pipeline_events if event[0] == "append"]) == 1:
                return first_evidence
            raise RuntimeError("second append failed")

        pipeline_append = Mock(side_effect=append_owner)

        def retrieved_owner(items, *, final_answer, docs):
            pipeline_events.append(("retrieved", items, final_answer, docs))
            return items, []

        pipeline_agent._append_retrieved_narrative_evidence_for_final_answer = Mock(
            side_effect=retrieved_owner
        )

        def period_owner(*, aggregate_state, state, evidence_items):
            pipeline_events.append(("period", aggregate_state, state, evidence_items))
            return aggregate_state

        pipeline_agent._apply_period_context_realignment_to_aggregate = Mock(side_effect=period_owner)
        pipeline_agent._answer_satisfies_growth_narrative_intent = Mock(
            side_effect=lambda **kwargs: pipeline_events.append(("intent", kwargs["answer"]))
            or (kwargs["answer"] == "repaired answer")
        )
        pipeline_agent._compose_growth_narrative_answer = Mock(
            side_effect=lambda **kwargs: pipeline_events.append(("compose", kwargs))
            or {"compressed_answer": "repaired answer", "selected_claim_ids": ["repaired-claim"]}
        )
        downstream_contract = Mock()
        pipeline_agent._enforce_source_stated_growth_answer_contract = downstream_contract
        pipeline_agent._unresolved_structured_numeric_gap = Mock()
        pipeline_agent._prune_nonfocus_numeric_narrative_sentences = Mock()
        pipeline_agent._answer_matches_supported_aggregate_subtask = Mock()
        pipeline_agent._promote_and_align_aggregate_results = Mock()

        def package_owner(value):
            pipeline_events.append(("package", value))
            return SimpleNamespace(candidate={"answer": value.answer})

        def application_owner(value):
            pipeline_events.append(("application", value))
            return SimpleNamespace(
                aggregate_projection=repaired_projection,
                final_answer="repaired answer",
                selected_claim_ids=["repaired-claim"],
            )

        state = {"query": "query", "nested": nested}
        before_state = deepcopy(state)
        with (
            patch.object(financial_graph_calculation, "package_aggregate_answer_candidate", side_effect=package_owner),
            patch.object(financial_graph_calculation, "apply_aggregate_answer_candidate", side_effect=application_owner),
            patch.object(financial_graph_calculation, "_normalise_spaces", side_effect=lambda value: " ".join(str(value).split())),
            patch.object(
                financial_graph_calculation,
                "append_operand_evidence_for_final_answer",
                pipeline_append,
            ),
            self.assertRaisesRegex(RuntimeError, "second append failed"),
        ):
            financial_graph_calculation.FinancialAgentCalculationMixin._apply_final_narrative_repair_pipeline(
                pipeline_agent,
                state,
                mutable_state=mutable_state,
                narrative_docs=narrative_docs,
                has_narrative_summary=True,
                has_growth_rate_result=False,
                deterministic_feedback="",
            )

        self.assertEqual(
            [event[0] for event in pipeline_events],
            [
                "realize",
                "replace",
                "append",
                "retrieved",
                "period",
                "intent",
                "compose",
                "intent",
                "package",
                "application",
                "append",
            ],
        )
        first_append, second_append = pipeline_append.call_args_list
        self.assertIs(first_append.args[0], evidence_items)
        self.assertEqual(first_append.kwargs["operands"], [operand])
        self.assertIs(first_append.kwargs["operands"][0], operand)
        self.assertEqual(first_append.kwargs["final_answer"], "realized answer")
        retrieved_call = pipeline_agent._append_retrieved_narrative_evidence_for_final_answer.call_args
        self.assertIs(retrieved_call.args[0], first_evidence)
        self.assertEqual(retrieved_call.kwargs["final_answer"], "realized answer")
        self.assertIs(retrieved_call.kwargs["docs"], narrative_docs)
        period_call = pipeline_agent._apply_period_context_realignment_to_aggregate.call_args
        self.assertIs(period_call.kwargs["evidence_items"], first_evidence)
        self.assertIs(second_append.args[0], first_evidence)
        self.assertEqual(second_append.kwargs["operands"], [repaired_operand])
        self.assertIs(second_append.kwargs["operands"][0], repaired_operand)
        self.assertEqual(second_append.kwargs["final_answer"], "repaired answer")
        downstream_contract.assert_not_called()
        self.assertEqual(ordered_results, before_rows)
        self.assertEqual(aggregate_projection, before_projection)
        self.assertEqual(evidence_items, before_evidence)
        self.assertEqual(narrative_docs, before_docs)
        self.assertEqual(state, before_state)
        self.assertIs(narrative_docs[0]["nested"], nested)

    def test_current_source_growth_numeric_completion_pins_precedence_laziness_and_exceptions(self) -> None:
        nested = {"preserve": True}
        earlier = {"task_id": "earlier", "family": "growth_rate", "nested": nested}
        empty = {"task_id": "empty", "family": "growth_rate", "nested": nested}
        conflict = {"task_id": "conflict", "family": "growth_rate", "nested": nested}
        other = {"task_id": "other", "family": "lookup", "nested": nested}
        ordered_results = [earlier, empty, conflict, other]
        evidence_items = [{"evidence_id": "ev-growth", "nested": nested}]
        before_results = deepcopy(ordered_results)
        before_evidence = deepcopy(evidence_items)
        events = []

        def operation_family(row):
            events.append(("family", row["task_id"]))
            return row["family"]

        family_owner = Mock(side_effect=operation_family)

        def conflicting(row):
            events.append(("conflict", row["task_id"]))
            return row is conflict

        def compose(row, rows, *, evidence_items=None):
            events.append(("compose", row["task_id"], rows, evidence_items))
            if row is empty:
                return ""
            return "complete 10% 200 100"

        def required(row, rows, evidence):
            events.append(("required", row["task_id"], rows, evidence))
            return ["10%", "200", "100"]

        split_owner = Mock(
            return_value=[
                "complete 10% 200 100",
                "required 200 should be skipped",
                "untraced 99% should be skipped",
                " stable explanatory context ",
                "",
            ]
        )

        def sentence_untraced(sentence, complete_answer, required_values, evidence):
            events.append(("sentence-untraced", sentence, complete_answer, required_values, evidence))
            return "99%" in sentence

        with (
            patch.object(financial_aggregate_projection, "aggregate_result_operation_family", family_owner),
            patch.object(financial_aggregate_projection, "growth_row_has_conflicting_periods", side_effect=conflicting),
            patch.object(financial_aggregate_projection, "compose_complete_growth_numeric_answer", side_effect=compose),
            patch.object(financial_aggregate_projection, "growth_required_display_values", side_effect=required),
            patch.object(financial_aggregate_projection, "_split_narrative_sentences", split_owner),
            patch.object(
                financial_aggregate_projection,
                "growth_sentence_has_untraced_material_numeric",
                side_effect=sentence_untraced,
            ),
        ):
            answer = financial_aggregate_projection.ensure_complete_growth_numeric_answer(
                " stale 99% answer ",
                ordered_results,
                evidence_items=evidence_items,
            )

        self.assertEqual(answer, "complete 10% 200 100 stable explanatory context")
        self.assertEqual(
            [(event[0], event[1]) for event in events if event[0] in {"family", "conflict", "compose", "required"}],
            [
                ("family", "other"),
                ("family", "conflict"),
                ("conflict", "conflict"),
                ("family", "empty"),
                ("conflict", "empty"),
                ("compose", "empty"),
                ("family", "earlier"),
                ("conflict", "earlier"),
                ("compose", "earlier"),
                ("required", "earlier"),
            ],
        )
        compose_call = next(event for event in events if event[:2] == ("compose", "earlier"))
        self.assertIs(compose_call[2], ordered_results)
        self.assertIs(compose_call[3], evidence_items)
        required_call = next(event for event in events if event[:2] == ("required", "earlier"))
        self.assertIs(required_call[2], ordered_results)
        self.assertIs(required_call[3], evidence_items)
        split_owner.assert_called_once_with("stale 99% answer")
        self.assertEqual(
            [event[1] for event in events if event[0] == "sentence-untraced"],
            ["untraced 99% should be skipped", "stable explanatory context"],
        )

        already_complete_row = {"task_id": "complete", "family": "growth_rate"}
        complete_split = Mock(side_effect=AssertionError("sentence splitter accessed"))
        complete_untraced = Mock(return_value=False)
        with (
            patch.object(financial_aggregate_projection, "aggregate_result_operation_family", return_value="growth_rate"),
            patch.object(financial_aggregate_projection, "growth_row_has_conflicting_periods", return_value=False),
            patch.object(
                financial_aggregate_projection,
                "compose_complete_growth_numeric_answer",
                return_value="complete 10% 200 100",
            ),
            patch.object(
                financial_aggregate_projection,
                "growth_required_display_values",
                return_value=["10%", "200", "100"],
            ),
            patch.object(
                financial_aggregate_projection,
                "growth_answer_has_untraced_numeric_sentence",
                complete_untraced,
            ),
            patch.object(financial_aggregate_projection, "_split_narrative_sentences", complete_split),
        ):
            self.assertEqual(
                financial_aggregate_projection.ensure_complete_growth_numeric_answer(
                    " complete 10% 200 100 ",
                    [already_complete_row],
                    evidence_items=evidence_items,
                ),
                "complete 10% 200 100",
            )
        complete_untraced.assert_called_once_with(
            "complete 10% 200 100",
            "complete 10% 200 100",
            ["10%", "200", "100"],
        )
        complete_split.assert_not_called()

        downstream = Mock()
        failing_required = Mock(side_effect=RuntimeError("required values failed"))
        with (
            patch.object(financial_aggregate_projection, "aggregate_result_operation_family", return_value="growth_rate"),
            patch.object(financial_aggregate_projection, "growth_row_has_conflicting_periods", return_value=False),
            patch.object(
                financial_aggregate_projection,
                "compose_complete_growth_numeric_answer",
                return_value="complete",
            ),
            patch.object(
                financial_aggregate_projection,
                "growth_required_display_values",
                failing_required,
            ),
            patch.object(
                financial_aggregate_projection,
                "growth_answer_has_untraced_numeric_sentence",
                downstream,
            ),
            patch.object(financial_aggregate_projection, "_split_narrative_sentences", downstream),
            self.assertRaisesRegex(RuntimeError, "required values failed"),
        ):
            financial_aggregate_projection.ensure_complete_growth_numeric_answer(
                "answer",
                [earlier],
                evidence_items=evidence_items,
            )
        downstream.assert_not_called()
        self.assertEqual(ordered_results, before_results)
        self.assertEqual(evidence_items, before_evidence)
        self.assertIs(earlier["nested"], nested)
        self.assertIs(evidence_items[0]["nested"], nested)

    def test_current_source_growth_sentence_sanitizer_pins_policy_gates_and_exceptions(self) -> None:
        nested = {"preserve": True}
        row = {"task_id": "growth", "family": "growth_rate", "nested": nested}
        ordered_results = [row]
        evidence_items = [{"evidence_id": "ev-growth", "nested": nested}]
        before_results = deepcopy(ordered_results)
        before_evidence = deepcopy(evidence_items)

        family_bomb = Mock(side_effect=AssertionError("operation family accessed"))
        with patch.object(financial_aggregate_projection, "aggregate_result_operation_family", family_bomb):
            self.assertEqual(
                financial_aggregate_projection.strip_untraced_numeric_material_from_growth_narrative_sentence(
                "   ",
                ordered_results,
                evidence_items=evidence_items,
                ),
                "",
            )
        family_bomb.assert_not_called()

        untraced_bomb = Mock(side_effect=AssertionError("untraced predicate accessed"))
        with (
            patch.object(financial_aggregate_projection, "aggregate_result_operation_family", return_value="growth_rate"),
            patch.object(financial_aggregate_projection, "growth_row_has_conflicting_periods", return_value=False),
            patch.object(financial_aggregate_projection, "compose_complete_growth_numeric_answer", return_value=""),
            patch.object(financial_aggregate_projection, "growth_required_display_values", return_value=[]),
            patch.object(
                financial_aggregate_projection,
                "growth_sentence_has_untraced_material_numeric",
                untraced_bomb,
            ),
        ):
            self.assertEqual(
                financial_aggregate_projection.strip_untraced_numeric_material_from_growth_narrative_sentence(
                    "clean narrative",
                    ordered_results,
                    evidence_items=evidence_items,
                ),
                "",
            )
        untraced_bomb.assert_not_called()

        class NoPolicyAccess:
            def get(self, _key, _default=None):
                raise AssertionError("policy accessed")

        with (
            patch.object(financial_aggregate_projection, "aggregate_result_operation_family", return_value="growth_rate"),
            patch.object(financial_aggregate_projection, "growth_row_has_conflicting_periods", return_value=False),
            patch.object(
                financial_aggregate_projection,
                "compose_complete_growth_numeric_answer",
                return_value="growth 10%",
            ),
            patch.object(financial_aggregate_projection, "growth_required_display_values", return_value=["10%"]),
            patch.object(
                financial_aggregate_projection,
                "growth_sentence_has_untraced_material_numeric",
                return_value=False,
            ),
            patch.object(financial_aggregate_projection, "CALCULATION_NARRATIVE_POLICY", NoPolicyAccess()),
        ):
            self.assertEqual(
                financial_aggregate_projection.strip_untraced_numeric_material_from_growth_narrative_sentence(
                    " clean narrative ",
                    ordered_results,
                    evidence_items=evidence_items,
                ),
                "clean narrative",
            )

        sentence = "because demand improved 99% and revenue 1,000 KRW"
        narrative_policy = {
            "percent_display_pattern": r"\d+(?:\.\d+)?%",
            "growth_narrative_markers": ("because",),
        }
        render_policy = {"krw_display_units": ("KRW",)}
        terms_owner = Mock(return_value=["because", "demand", "improved"])
        noise_owner = Mock(return_value=False)
        fragment_owner = Mock(return_value=False)
        untraced_owner = Mock(side_effect=[True, False])
        with (
            patch.object(financial_aggregate_projection, "aggregate_result_operation_family", return_value="growth_rate"),
            patch.object(financial_aggregate_projection, "growth_row_has_conflicting_periods", return_value=False),
            patch.object(
                financial_aggregate_projection,
                "compose_complete_growth_numeric_answer",
                return_value="growth 10%",
            ),
            patch.object(financial_aggregate_projection, "growth_required_display_values", return_value=["10%"]),
            patch.object(
                financial_aggregate_projection,
                "growth_sentence_has_untraced_material_numeric",
                untraced_owner,
            ),
            patch.object(financial_aggregate_projection, "CALCULATION_NARRATIVE_POLICY", narrative_policy),
            patch.object(financial_aggregate_projection, "CALCULATION_RENDER_POLICY", render_policy),
            patch.object(financial_aggregate_projection, "narrative_context_terms", terms_owner),
            patch.object(financial_aggregate_projection, "narrative_sentence_looks_table_noisy", noise_owner),
            patch.object(
                financial_aggregate_projection,
                "narrative_sentence_looks_abbreviated_fragment",
                fragment_owner,
            ),
        ):
            sanitized = financial_aggregate_projection.strip_untraced_numeric_material_from_growth_narrative_sentence(
                sentence,
                ordered_results,
                evidence_items=evidence_items,
            )
        self.assertEqual(sanitized, "because demand improved and revenue")
        self.assertEqual(untraced_owner.call_count, 2)
        for call in untraced_owner.call_args_list:
            self.assertIs(call.args[2], untraced_owner.call_args_list[0].args[2])
            self.assertIs(call.args[3], evidence_items)
        terms_owner.assert_called_once_with("because demand improved and revenue")
        noise_owner.assert_called_once_with("because demand improved and revenue")
        fragment_owner.assert_called_once_with("because demand improved and revenue", ("because",))

        def gated_result(*, second_untraced=False, markers=("because",), terms=None, noisy=False, fragment=False):
            local_terms = Mock(return_value=terms if terms is not None else ["because", "demand"])
            local_noise = Mock(return_value=noisy)
            local_fragment = Mock(return_value=fragment)
            with (
                patch.object(financial_aggregate_projection, "aggregate_result_operation_family", return_value="growth_rate"),
                patch.object(financial_aggregate_projection, "growth_row_has_conflicting_periods", return_value=False),
                patch.object(
                    financial_aggregate_projection,
                    "compose_complete_growth_numeric_answer",
                    return_value="growth 10%",
                ),
                patch.object(financial_aggregate_projection, "growth_required_display_values", return_value=["10%"]),
                patch.object(
                    financial_aggregate_projection,
                    "growth_sentence_has_untraced_material_numeric",
                    side_effect=[True, second_untraced],
                ),
                patch.object(
                    financial_aggregate_projection,
                    "CALCULATION_NARRATIVE_POLICY",
                    {"percent_display_pattern": r"\d+(?:\.\d+)?%", "growth_narrative_markers": markers},
                ),
                patch.object(financial_aggregate_projection, "CALCULATION_RENDER_POLICY", render_policy),
                patch.object(financial_aggregate_projection, "narrative_context_terms", local_terms),
                patch.object(financial_aggregate_projection, "narrative_sentence_looks_table_noisy", local_noise),
                patch.object(
                    financial_aggregate_projection,
                    "narrative_sentence_looks_abbreviated_fragment",
                    local_fragment,
                ),
            ):
                result = financial_aggregate_projection.strip_untraced_numeric_material_from_growth_narrative_sentence(
                    sentence,
                    ordered_results,
                    evidence_items=evidence_items,
                )
            return result, local_terms, local_noise, local_fragment

        result, terms, noise, fragment = gated_result(second_untraced=True)
        self.assertEqual(result, "")
        terms.assert_not_called()
        noise.assert_not_called()
        fragment.assert_not_called()

        result, terms, noise, fragment = gated_result(markers=("absent",))
        self.assertEqual(result, "")
        terms.assert_not_called()
        noise.assert_not_called()
        fragment.assert_not_called()

        result, terms, noise, fragment = gated_result(terms=["because"])
        self.assertEqual(result, "")
        terms.assert_called_once()
        noise.assert_not_called()
        fragment.assert_not_called()

        result, _terms, noise, fragment = gated_result(noisy=True)
        self.assertEqual(result, "")
        noise.assert_called_once()
        fragment.assert_not_called()

        result, _terms, noise, fragment = gated_result(fragment=True)
        self.assertEqual(result, "")
        noise.assert_called_once()
        fragment.assert_called_once()

        class PolicyBomb:
            def get(self, _key, _default=None):
                raise RuntimeError("narrative policy failed")

        downstream_terms = Mock()
        with (
            patch.object(financial_aggregate_projection, "aggregate_result_operation_family", return_value="growth_rate"),
            patch.object(financial_aggregate_projection, "growth_row_has_conflicting_periods", return_value=False),
            patch.object(
                financial_aggregate_projection,
                "compose_complete_growth_numeric_answer",
                return_value="growth 10%",
            ),
            patch.object(financial_aggregate_projection, "growth_required_display_values", return_value=["10%"]),
            patch.object(
                financial_aggregate_projection,
                "growth_sentence_has_untraced_material_numeric",
                return_value=True,
            ),
            patch.object(financial_aggregate_projection, "CALCULATION_NARRATIVE_POLICY", PolicyBomb()),
            patch.object(financial_aggregate_projection, "narrative_context_terms", downstream_terms),
            self.assertRaisesRegex(RuntimeError, "narrative policy failed"),
        ):
            financial_aggregate_projection.strip_untraced_numeric_material_from_growth_narrative_sentence(
                sentence,
                ordered_results,
                evidence_items=evidence_items,
            )
        downstream_terms.assert_not_called()
        self.assertEqual(ordered_results, before_results)
        self.assertEqual(evidence_items, before_evidence)
        self.assertIs(row["nested"], nested)
        self.assertIs(evidence_items[0]["nested"], nested)

    def test_current_source_growth_numeric_cleanup_bindings_pin_calls_dag_and_baseline(self) -> None:
        import json
        from pathlib import Path

        graph_path = Path("src/agent/financial_graph_calculation.py")
        owner_path = Path("src/agent/financial_aggregate_projection.py")
        graph_tree = ast.parse(graph_path.read_text(encoding="utf-8-sig"))
        owner_tree = ast.parse(owner_path.read_text(encoding="utf-8-sig"))
        private_names = {
            "completion": "_ensure_complete_" + "growth_numeric_answer",
            "sanitizer": "_strip_untraced_numeric_material_from_" + "growth_narrative_sentence",
        }
        public_names = {
            "completion": "ensure_complete_growth_numeric_answer",
            "sanitizer": "strip_untraced_numeric_material_from_growth_narrative_sentence",
        }
        all_target_names = set(private_names.values()) | set(public_names.values())

        def parent_map(tree):
            parents = {}
            for parent in ast.walk(tree):
                for child in ast.iter_child_nodes(parent):
                    parents[child] = parent
            return parents

        trees = {"graph": graph_tree, "owner": owner_tree}
        parents_by_module = {module: parent_map(tree) for module, tree in trees.items()}
        definitions = {}
        calls = {"completion": [], "sanitizer": []}
        noncall_refs = []

        def key_for_name(name):
            for key in private_names:
                if name in {private_names[key], public_names[key]}:
                    return key
            return None

        for module_name, tree in trees.items():
            parents = parents_by_module[module_name]
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef) and node.name in all_target_names:
                    definitions[(module_name, node.name)] = node
                if isinstance(node, ast.Call):
                    receiver = ""
                    target_name = ""
                    if isinstance(node.func, ast.Attribute):
                        target_name = node.func.attr
                        receiver = ast.unparse(node.func.value)
                    elif isinstance(node.func, ast.Name):
                        target_name = node.func.id
                    key = key_for_name(target_name)
                    if key is None:
                        continue
                    caller = "<module>"
                    try_depth = 0
                    current = node
                    while current in parents:
                        current = parents[current]
                        if isinstance(current, ast.Try):
                            try_depth += 1
                        if isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef)):
                            caller = current.name
                            break
                    calls[key].append(
                        {
                            "module": module_name,
                            "caller": caller,
                            "receiver": receiver,
                            "args": tuple(ast.unparse(arg) for arg in node.args),
                            "kwargs": tuple(keyword.arg for keyword in node.keywords),
                            "try_depth": try_depth,
                            "line": node.lineno,
                        }
                    )
                if isinstance(node, ast.Attribute) and node.attr in all_target_names:
                    parent = parents.get(node)
                    if not (isinstance(parent, ast.Call) and parent.func is node):
                        noncall_refs.append((module_name, node.attr, node.lineno))
                if isinstance(node, ast.Name) and node.id in all_target_names:
                    parent = parents.get(node)
                    if not (isinstance(parent, ast.Call) and parent.func is node):
                        noncall_refs.append((module_name, node.id, node.lineno))

        self.assertEqual(
            {
                (module, name): node.end_lineno - node.lineno + 1
                for (module, name), node in definitions.items()
            },
            {
                ("owner", public_names["completion"]): 46,
                ("owner", public_names["sanitizer"]): 107,
            },
        )
        self.assertEqual({key: len(value) for key, value in calls.items()}, {"completion": 12, "sanitizer": 7})
        self.assertEqual(noncall_refs, [])
        self.assertTrue(
            all(
                entry["module"] == "graph"
                and entry["receiver"] == ""
                and len(entry["args"]) == 2
                and entry["kwargs"] == ("evidence_items",)
                and entry["try_depth"] == 0
                for entries in calls.values()
                for entry in entries
            )
        )
        self.assertEqual(
            Counter(entry["caller"] for entry in calls["completion"]),
            Counter(
                {
                    "_final_growth_answer_without_untraced_numeric_sentences": 1,
                    "_refresh_numeric_answer_preserving_narrative_context": 7,
                    "_apply_initial_aggregate_answer_composition": 1,
                    "_apply_final_narrative_repair_pipeline": 1,
                    "_aggregate_calculation_subtasks": 2,
                }
            ),
        )
        self.assertEqual(
            Counter(entry["caller"] for entry in calls["sanitizer"]),
            Counter(
                {
                    "_final_growth_answer_without_untraced_numeric_sentences": 1,
                    "_uncovered_supported_growth_narrative_candidate": 1,
                    "_refresh_numeric_answer_preserving_narrative_context": 4,
                    "_apply_final_narrative_repair_pipeline": 1,
                }
            ),
        )
        self.assertEqual(
            (sum(len(entries) for entries in calls.values()), 0),
            (19, 0),
        )
        module_paths = list(Path("src/agent").glob("*.py")) + list(Path("src/config").glob("*.py"))
        import_graph = {}
        for path in module_paths:
            module_name = ".".join(path.with_suffix("").parts)
            imported = set()
            for node in ast.parse(path.read_text(encoding="utf-8-sig")).body:
                if isinstance(node, ast.ImportFrom) and node.module:
                    imported.add(node.module)
                elif isinstance(node, ast.Import):
                    imported.update(alias.name for alias in node.names)
            import_graph[module_name] = imported

        def reaches(start, target):
            pending = [start]
            seen = set()
            while pending:
                current = pending.pop()
                if current == target:
                    return True
                if current in seen:
                    continue
                seen.add(current)
                pending.extend(import_graph.get(current, ()))
            return False

        owner_module = "src.agent.financial_aggregate_projection"
        graph_module = "src.agent.financial_graph_calculation"
        self.assertIn(owner_module, import_graph[graph_module])
        self.assertFalse(reaches(owner_module, graph_module))
        self.assertFalse(reaches(owner_module, "src.agent.financial_graph"))
        for dependency in (
            "src.agent.financial_answer_projection",
            "src.agent.financial_text_surface",
            "src.agent.financial_runtime_normalization",
        ):
            self.assertIn(dependency, import_graph[owner_module])
            self.assertFalse(reaches(dependency, owner_module), dependency)

        baseline = json.loads(
            (Path("tests") / "fixtures" / "runtime_domain_terms_baseline.json").read_text(encoding="utf-8")
        )
        self.assertEqual(len(baseline["records"]), 217)
        selected_lines = set()
        for name in public_names.values():
            node = definitions[("owner", name)]
            selected_lines.update(range(node.lineno, node.end_lineno + 1))
        self.assertEqual(
            [
                record
                for record in baseline["records"]
                if record.get("path") == "src/agent/financial_aggregate_projection.py"
                and selected_lines.intersection(record.get("first_lines") or [])
            ],
            [],
        )

        referenced_test_modules = set()
        for path in Path("tests").glob("test_*.py"):
            text = path.read_text(encoding="utf-8-sig")
            if any(name in text for name in private_names.values()):
                referenced_test_modules.add(path.stem)
        self.assertEqual(
            referenced_test_modules,
            set(),
        )

    def test_current_source_growth_refresh_caller_pins_cleanup_args_adoption_and_stop(self) -> None:
        nested = {"preserve": True}
        row = {"task_id": "narrative", "answer": "bad 99% explanation", "nested": nested}
        ordered_results = [row]
        evidence_items = [{"evidence_id": "ev-growth", "nested": nested}]
        before_results = deepcopy(ordered_results)
        before_evidence = deepcopy(evidence_items)
        events = []

        class Agent:
            pass

        agent = Agent()
        agent._preferred_conflicting_growth_narrative_answer = Mock(
            return_value={
                "answer": "bad 99% explanation",
                "selected_claim_ids": ["claim-growth"],
                "operation_family": "growth_rate",
            }
        )

        def sanitize(sentence, rows, *, evidence_items=None):
            events.append(("sanitize", sentence, rows, evidence_items))
            return "clean explanation"

        def complete(answer, rows, *, evidence_items=None):
            events.append(("complete", answer, rows, evidence_items))
            return "complete 10% clean explanation"

        strip_owner = Mock(side_effect=sanitize)
        complete_owner = Mock(side_effect=complete)
        agent._answer_satisfies_growth_narrative_intent = Mock(
            side_effect=lambda **kwargs: events.append(("intent", kwargs)) or True
        )

        def final_untraced(answer, rows, evidence):
            events.append(("final-untraced", answer, rows, evidence))
            return False

        with (
            patch.object(financial_graph_calculation, "row_is_narrative_summary", return_value=True),
            patch.object(financial_graph_calculation, "query_requests_explanatory_context", return_value=False),
            patch.object(
                financial_graph_calculation,
                "growth_narrative_numeric_incompatible_with_trace",
                return_value=False,
            ),
            patch.object(financial_graph_calculation, "_split_narrative_sentences", return_value=["bad 99% explanation"]),
            patch.object(
                financial_graph_calculation,
                "growth_answer_has_untraced_numeric_material",
                side_effect=final_untraced,
            ),
            patch.object(
                financial_graph_calculation,
                "CALCULATION_NARRATIVE_POLICY",
                {
                    "growth_narrative_markers": ("explanation",),
                    "growth_impact_markers": (),
                    "explanatory_markers": (),
                    "percent_display_pattern": r"\d+(?:\.\d+)?%",
                },
            ),
            patch.object(
                financial_graph_calculation,
                "strip_untraced_numeric_material_from_growth_narrative_sentence",
                strip_owner,
            ),
            patch.object(
                financial_graph_calculation,
                "ensure_complete_growth_numeric_answer",
                complete_owner,
            ),
        ):
            refreshed = financial_graph_calculation.FinancialAgentCalculationMixin._refresh_numeric_answer_preserving_narrative_context(
                agent,
                query="growth query",
                current_answer="old answer",
                numeric_answer="complete 10%",
                ordered_results=ordered_results,
                evidence_items=evidence_items,
            )

        self.assertEqual(
            refreshed,
            {"answer": "complete 10% clean explanation", "selected_claim_ids": ["claim-growth"]},
        )
        self.assertEqual([event[0] for event in events], ["sanitize", "complete", "final-untraced", "intent"])
        sanitize_event, complete_event, untraced_event, intent_event = events
        self.assertEqual(sanitize_event[1], "bad 99% explanation")
        self.assertIs(sanitize_event[2], ordered_results)
        self.assertIs(sanitize_event[3], evidence_items)
        self.assertEqual(complete_event[1], "complete 10% clean explanation")
        self.assertIs(complete_event[2], ordered_results)
        self.assertIs(complete_event[3], evidence_items)
        self.assertEqual(untraced_event[1], "complete 10% clean explanation")
        self.assertIs(untraced_event[2], ordered_results)
        self.assertIs(untraced_event[3], evidence_items)
        self.assertIs(intent_event[1]["ordered_results"], ordered_results)
        self.assertIs(intent_event[1]["evidence_items"], evidence_items)

        completion_after_failure = Mock()
        downstream_after_failure = Mock()
        failing_strip_agent = Agent()
        failing_strip_agent._preferred_conflicting_growth_narrative_answer = (
            agent._preferred_conflicting_growth_narrative_answer
        )
        failing_strip_agent._answer_satisfies_growth_narrative_intent = downstream_after_failure
        failing_strip_owner = Mock(side_effect=RuntimeError("sanitize failed"))
        with (
            patch.object(financial_graph_calculation, "row_is_narrative_summary", return_value=True),
            patch.object(financial_graph_calculation, "query_requests_explanatory_context", return_value=False),
            patch.object(
                financial_graph_calculation,
                "growth_narrative_numeric_incompatible_with_trace",
                return_value=False,
            ),
            patch.object(financial_graph_calculation, "_split_narrative_sentences", return_value=["bad 99% explanation"]),
            patch.object(
                financial_graph_calculation,
                "growth_answer_has_untraced_numeric_material",
                downstream_after_failure,
            ),
            patch.object(
                financial_graph_calculation,
                "CALCULATION_NARRATIVE_POLICY",
                {"growth_narrative_markers": ("explanation",), "growth_impact_markers": (), "explanatory_markers": ()},
            ),
            patch.object(
                financial_graph_calculation,
                "strip_untraced_numeric_material_from_growth_narrative_sentence",
                failing_strip_owner,
            ),
            patch.object(
                financial_graph_calculation,
                "ensure_complete_growth_numeric_answer",
                completion_after_failure,
            ),
            self.assertRaisesRegex(RuntimeError, "sanitize failed"),
        ):
            financial_graph_calculation.FinancialAgentCalculationMixin._refresh_numeric_answer_preserving_narrative_context(
                failing_strip_agent,
                query="growth query",
                current_answer="old answer",
                numeric_answer="complete 10%",
                ordered_results=ordered_results,
                evidence_items=evidence_items,
            )
        completion_after_failure.assert_not_called()
        downstream_after_failure.assert_not_called()

        failing_complete_agent = Agent()
        failing_complete_agent._preferred_conflicting_growth_narrative_answer = (
            agent._preferred_conflicting_growth_narrative_answer
        )
        failing_complete_strip = Mock(return_value="clean explanation")
        failing_complete_owner = Mock(side_effect=RuntimeError("completion failed"))
        failing_complete_agent._answer_satisfies_growth_narrative_intent = downstream_after_failure
        downstream_after_failure.reset_mock()
        with (
            patch.object(financial_graph_calculation, "row_is_narrative_summary", return_value=True),
            patch.object(financial_graph_calculation, "query_requests_explanatory_context", return_value=False),
            patch.object(
                financial_graph_calculation,
                "growth_narrative_numeric_incompatible_with_trace",
                return_value=False,
            ),
            patch.object(financial_graph_calculation, "_split_narrative_sentences", return_value=["bad 99% explanation"]),
            patch.object(
                financial_graph_calculation,
                "growth_answer_has_untraced_numeric_material",
                downstream_after_failure,
            ),
            patch.object(
                financial_graph_calculation,
                "CALCULATION_NARRATIVE_POLICY",
                {"growth_narrative_markers": ("explanation",), "growth_impact_markers": (), "explanatory_markers": ()},
            ),
            patch.object(
                financial_graph_calculation,
                "strip_untraced_numeric_material_from_growth_narrative_sentence",
                failing_complete_strip,
            ),
            patch.object(
                financial_graph_calculation,
                "ensure_complete_growth_numeric_answer",
                failing_complete_owner,
            ),
            self.assertRaisesRegex(RuntimeError, "completion failed"),
        ):
            financial_graph_calculation.FinancialAgentCalculationMixin._refresh_numeric_answer_preserving_narrative_context(
                failing_complete_agent,
                query="growth query",
                current_answer="old answer",
                numeric_answer="complete 10%",
                ordered_results=ordered_results,
                evidence_items=evidence_items,
            )
        downstream_after_failure.assert_not_called()
        self.assertEqual(ordered_results, before_results)
        self.assertEqual(evidence_items, before_evidence)
        self.assertIs(row["nested"], nested)
        self.assertIs(evidence_items[0]["nested"], nested)

    def test_current_source_growth_final_pipeline_pins_cleanup_order_adoption_and_stop(self) -> None:
        nested = {"preserve": True}
        row = {"task_id": "growth", "answer": "row 99% context", "nested": nested}
        ordered_results = [row]
        evidence_items = [{"evidence_id": "ev-growth", "nested": nested}]
        narrative_docs = [{"page_content": "context", "nested": nested}]
        state = {"query": "growth query", "nested": nested}
        projection = {
            "calculation_result": {},
            "calculation_operands": [],
            "calculation_plan": {"operation": "growth_rate"},
        }
        mutable_state = financial_graph_calculation._AggregateMutableState(
            financial_graph_calculation._AggregateSynthesisState(
                ordered_results,
                projection,
                "base answer",
                ["claim-base"],
            ),
            evidence_items,
        )
        before_rows = deepcopy(ordered_results)
        before_evidence = deepcopy(evidence_items)
        before_docs = deepcopy(narrative_docs)
        before_state = deepcopy(state)

        class Agent:
            pass

        def configured_agent(events, completion_owner, sanitizer_owner):
            agent = Agent()
            agent._preserve_policy_required_realized_context = Mock(
                side_effect=lambda answer, **_kwargs: answer
            )

            def replace_owner(current, *, candidate_answer, **kwargs):
                events.append(("replace", candidate_answer, kwargs))
                updated = current.synthesis_state.with_updates(final_answer=candidate_answer)
                return current.with_synthesis_state(updated), candidate_answer != current.final_answer

            agent._replace_mutable_aggregate_answer = Mock(side_effect=replace_owner)
            agent._append_retrieved_narrative_evidence_for_final_answer = Mock(
                side_effect=lambda current, **_kwargs: (current, [])
            )
            agent._apply_period_context_realignment_to_aggregate = Mock(
                side_effect=lambda **kwargs: kwargs["aggregate_state"]
            )
            agent._answer_satisfies_growth_narrative_intent = Mock(return_value=True)
            agent._compose_growth_narrative_answer = Mock(
                side_effect=AssertionError("growth composition accessed")
            )
            agent._enforce_source_stated_growth_answer_contract = Mock(
                side_effect=lambda answer, _rows, **_kwargs: answer
            )
            agent._unresolved_structured_numeric_gap = Mock(return_value=False)
            agent._answer_matches_supported_aggregate_subtask = Mock(return_value=False)
            agent._prune_nonfocus_numeric_narrative_sentences = Mock(
                side_effect=lambda answer, **_kwargs: events.append(("prune", answer)) or answer
            )
            agent._promote_and_align_aggregate_results = Mock(
                side_effect=lambda rows, _state, answer, **_kwargs: events.append(("promote", answer))
                or (rows, False, False, False)
            )
            return agent

        def common_context_patches():
            return (
                patch.object(
                    financial_graph_calculation,
                    "append_operand_evidence_for_final_answer",
                    side_effect=lambda current, **_kwargs: current,
                ),
                patch.object(
                    financial_graph_calculation,
                    "preserve_retrieved_narrative_source_surface",
                    side_effect=lambda answer, _items: answer,
                ),
                patch.object(
                    financial_graph_calculation,
                    "_polish_korean_particle_pairs",
                    side_effect=lambda answer: answer,
                ),
            )

        events = []

        def complete(answer, rows, *, evidence_items=None):
            events.append(("complete", answer, rows, evidence_items))
            return "completed answer"

        completion_owner = Mock(side_effect=complete)
        sanitizer_owner = Mock(side_effect=AssertionError("sanitizer accessed"))
        agent = configured_agent(events, completion_owner, sanitizer_owner)
        shared_patches = common_context_patches()
        with (
            shared_patches[0],
            shared_patches[1],
            shared_patches[2],
            patch.object(financial_graph_calculation, "query_requests_explanatory_context", return_value=False),
            patch.object(financial_graph_calculation, "ensure_complete_growth_numeric_answer", completion_owner),
            patch.object(
                financial_graph_calculation,
                "strip_untraced_numeric_material_from_growth_narrative_sentence",
                sanitizer_owner,
            ),
        ):
            completed_state = financial_graph_calculation.FinancialAgentCalculationMixin._apply_final_narrative_repair_pipeline(
                agent,
                state,
                mutable_state=mutable_state,
                narrative_docs=narrative_docs,
                has_narrative_summary=True,
                has_growth_rate_result=True,
                deterministic_feedback="",
            )

        self.assertEqual(completed_state.final_answer, "completed answer")
        completion_owner.assert_called_once_with(
            "base answer",
            ordered_results,
            evidence_items=evidence_items,
        )
        self.assertIs(completion_owner.call_args.args[1], ordered_results)
        self.assertIs(completion_owner.call_args.kwargs["evidence_items"], evidence_items)
        event_names = [event[0] for event in events]
        self.assertLess(event_names.index("complete"), event_names.index("prune"))
        self.assertLess(event_names.index("prune"), event_names.index("promote"))
        completion_index = event_names.index("complete")
        self.assertEqual(events[completion_index + 1][0:2], ("replace", "completed answer"))
        self.assertTrue(events[completion_index + 1][2]["refresh_operand_evidence"])
        sanitizer_owner.assert_not_called()

        failed_events = []
        failed_prune = Mock()
        failed_promote = Mock()
        failing_completion = Mock(side_effect=RuntimeError("pipeline completion failed"))
        unused_sanitizer = Mock()
        failing_agent = configured_agent(failed_events, failing_completion, unused_sanitizer)
        failing_agent._prune_nonfocus_numeric_narrative_sentences = failed_prune
        failing_agent._promote_and_align_aggregate_results = failed_promote
        shared_patches = common_context_patches()
        with (
            shared_patches[0],
            shared_patches[1],
            shared_patches[2],
            patch.object(financial_graph_calculation, "query_requests_explanatory_context", return_value=False),
            patch.object(financial_graph_calculation, "ensure_complete_growth_numeric_answer", failing_completion),
            patch.object(
                financial_graph_calculation,
                "strip_untraced_numeric_material_from_growth_narrative_sentence",
                unused_sanitizer,
            ),
            self.assertRaisesRegex(RuntimeError, "pipeline completion failed"),
        ):
            financial_graph_calculation.FinancialAgentCalculationMixin._apply_final_narrative_repair_pipeline(
                failing_agent,
                state,
                mutable_state=mutable_state,
                narrative_docs=narrative_docs,
                has_narrative_summary=True,
                has_growth_rate_result=True,
                deterministic_feedback="",
            )
        failed_prune.assert_not_called()
        failed_promote.assert_not_called()

        sanitizer_events = []

        def sanitize(sentence, rows, *, evidence_items=None):
            sanitizer_events.append(("sanitize", sentence, rows, evidence_items))
            return "clean narrative context"

        unused_completion = Mock()
        pipeline_sanitizer = Mock(side_effect=sanitize)
        sanitizer_agent = configured_agent(sanitizer_events, unused_completion, pipeline_sanitizer)
        shared_patches = common_context_patches()
        with (
            shared_patches[0],
            shared_patches[1],
            shared_patches[2],
            patch.object(financial_graph_calculation, "query_requests_explanatory_context", return_value=True),
            patch.object(financial_graph_calculation, "row_is_narrative_summary", return_value=True),
            patch.object(
                financial_graph_calculation,
                "_split_narrative_sentences",
                return_value=["row 99% context"],
            ),
            patch.object(financial_graph_calculation, "ensure_complete_growth_numeric_answer", unused_completion),
            patch.object(
                financial_graph_calculation,
                "strip_untraced_numeric_material_from_growth_narrative_sentence",
                pipeline_sanitizer,
            ),
        ):
            sanitized_state = financial_graph_calculation.FinancialAgentCalculationMixin._apply_final_narrative_repair_pipeline(
                sanitizer_agent,
                state,
                mutable_state=mutable_state,
                narrative_docs=narrative_docs,
                has_narrative_summary=True,
                has_growth_rate_result=False,
                deterministic_feedback="",
            )
        self.assertEqual(sanitized_state.final_answer, "base answer clean narrative context")
        sanitizer_call = pipeline_sanitizer.call_args
        self.assertEqual(sanitizer_call.args[0], "row 99% context")
        self.assertIs(sanitizer_call.args[1], ordered_results)
        self.assertIs(sanitizer_call.kwargs["evidence_items"], evidence_items)
        sanitizer_names = [event[0] for event in sanitizer_events]
        self.assertLess(sanitizer_names.index("promote"), sanitizer_names.index("sanitize"))
        sanitize_index = sanitizer_names.index("sanitize")
        self.assertEqual(
            sanitizer_events[sanitize_index + 1][0:2],
            ("replace", "base answer clean narrative context"),
        )

        failing_sanitizer_owner = Mock(side_effect=RuntimeError("pipeline sanitizer failed"))
        failing_sanitizer_completion = Mock()
        failing_sanitizer_agent = configured_agent(
            [],
            failing_sanitizer_completion,
            failing_sanitizer_owner,
        )
        shared_patches = common_context_patches()
        with (
            shared_patches[0],
            shared_patches[1],
            shared_patches[2],
            patch.object(financial_graph_calculation, "query_requests_explanatory_context", return_value=True),
            patch.object(financial_graph_calculation, "row_is_narrative_summary", return_value=True),
            patch.object(
                financial_graph_calculation,
                "_split_narrative_sentences",
                return_value=["row 99% context"],
            ),
            patch.object(
                financial_graph_calculation,
                "ensure_complete_growth_numeric_answer",
                failing_sanitizer_completion,
            ),
            patch.object(
                financial_graph_calculation,
                "strip_untraced_numeric_material_from_growth_narrative_sentence",
                failing_sanitizer_owner,
            ),
            self.assertRaisesRegex(RuntimeError, "pipeline sanitizer failed"),
        ):
            financial_graph_calculation.FinancialAgentCalculationMixin._apply_final_narrative_repair_pipeline(
                failing_sanitizer_agent,
                state,
                mutable_state=mutable_state,
                narrative_docs=narrative_docs,
                has_narrative_summary=True,
                has_growth_rate_result=False,
                deterministic_feedback="",
            )

        self.assertEqual(ordered_results, before_rows)
        self.assertEqual(evidence_items, before_evidence)
        self.assertEqual(narrative_docs, before_docs)
        self.assertEqual(state, before_state)
        self.assertIs(row["nested"], nested)
        self.assertIs(evidence_items[0]["nested"], nested)
        self.assertIs(narrative_docs[0]["nested"], nested)

    def test_current_source_growth_remaining_callers_pin_cleanup_args_adoption_and_stop(self) -> None:
        nested = {"preserve": True}
        row = {"task_id": "growth", "nested": nested}
        ordered_results = [row]
        evidence_items = [{"evidence_id": "ev-growth", "nested": nested}]
        before_rows = deepcopy(ordered_results)
        before_evidence = deepcopy(evidence_items)

        class Agent:
            pass

        final_events = []
        final_agent = Agent()
        final_agent._aggregate_result_operation_family = Mock(return_value="growth_rate")

        def final_sanitize(sentence, rows, *, evidence_items=None):
            final_events.append(("sanitize", sentence, rows, evidence_items))
            return ""

        def final_complete(answer, rows, *, evidence_items=None):
            final_events.append(("complete", answer, rows, evidence_items))
            return "completed final answer"

        final_strip_owner = Mock(side_effect=final_sanitize)
        final_complete_owner = Mock(side_effect=final_complete)
        final_agent._answer_covers_numeric_projection = Mock(return_value=False)
        final_agent._answer_satisfies_growth_narrative_intent = Mock(return_value=True)

        def numeric_candidates(text):
            if "complete 10%" in text:
                return [{"value": 10.0}]
            if "99%" in text:
                return [{"value": 99.0}]
            if "77%" in text:
                return [{"value": 77.0}]
            return []

        with (
            patch.object(
                financial_graph_calculation,
                "_split_narrative_sentences",
                return_value=["required 99%", "unsupported 77%", "context sentence"],
            ),
            patch.object(financial_graph_calculation, "growth_row_has_conflicting_periods", return_value=False),
            patch.object(
                financial_graph_calculation,
                "compose_complete_growth_numeric_answer",
                return_value="complete 10%",
            ),
            patch.object(
                financial_graph_calculation,
                "growth_required_display_values",
                return_value=["required"],
            ),
            patch.object(
                financial_graph_calculation,
                "extract_numeric_surface_candidates",
                side_effect=numeric_candidates,
            ),
            patch.object(
                financial_graph_calculation,
                "numeric_surface_candidates_equivalent",
                side_effect=lambda left, right: left["value"] == right["value"],
            ),
            patch.object(
                financial_graph_calculation,
                "growth_answer_has_untraced_numeric_material",
                return_value=False,
            ),
            patch.object(
                financial_graph_calculation,
                "strip_untraced_numeric_material_from_growth_narrative_sentence",
                final_strip_owner,
            ),
            patch.object(
                financial_graph_calculation,
                "ensure_complete_growth_numeric_answer",
                final_complete_owner,
            ),
        ):
            final_answer = financial_graph_calculation.FinancialAgentCalculationMixin._final_growth_answer_without_untraced_numeric_sentences(
                final_agent,
                query="growth query",
                answer="required 99%. unsupported 77%. context sentence",
                ordered_results=ordered_results,
                evidence_items=evidence_items,
            )

        self.assertEqual(final_answer, "completed final answer")
        self.assertEqual([event[0] for event in final_events], ["sanitize", "complete"])
        sanitize_event, complete_event = final_events
        self.assertEqual(sanitize_event[1], "required 99%")
        self.assertIs(sanitize_event[2], ordered_results)
        self.assertIs(sanitize_event[3], evidence_items)
        self.assertEqual(complete_event[1], "context sentence")
        self.assertIs(complete_event[2], ordered_results)
        self.assertIs(complete_event[3], evidence_items)
        final_agent._answer_satisfies_growth_narrative_intent.assert_called_once()
        self.assertEqual(
            final_agent._answer_satisfies_growth_narrative_intent.call_args.kwargs["answer"],
            "completed final answer",
        )

        completion_after_strip_failure = Mock()
        final_strip_failure = Mock(side_effect=RuntimeError("final strip failed"))
        with (
            patch.object(
                financial_graph_calculation,
                "_split_narrative_sentences",
                return_value=["required 99%", "unsupported 77%", "context sentence"],
            ),
            patch.object(financial_graph_calculation, "growth_row_has_conflicting_periods", return_value=False),
            patch.object(
                financial_graph_calculation,
                "compose_complete_growth_numeric_answer",
                return_value="complete 10%",
            ),
            patch.object(
                financial_graph_calculation,
                "growth_required_display_values",
                return_value=["required"],
            ),
            patch.object(
                financial_graph_calculation,
                "extract_numeric_surface_candidates",
                side_effect=numeric_candidates,
            ),
            patch.object(
                financial_graph_calculation,
                "numeric_surface_candidates_equivalent",
                side_effect=lambda left, right: left["value"] == right["value"],
            ),
            patch.object(
                financial_graph_calculation,
                "strip_untraced_numeric_material_from_growth_narrative_sentence",
                final_strip_failure,
            ),
            patch.object(
                financial_graph_calculation,
                "ensure_complete_growth_numeric_answer",
                completion_after_strip_failure,
            ),
            self.assertRaisesRegex(RuntimeError, "final strip failed"),
        ):
            financial_graph_calculation.FinancialAgentCalculationMixin._final_growth_answer_without_untraced_numeric_sentences(
                final_agent,
                query="growth query",
                answer="required 99%. unsupported 77%. context sentence",
                ordered_results=ordered_results,
                evidence_items=evidence_items,
            )
        completion_after_strip_failure.assert_not_called()

        candidate_agent = Agent()
        candidate_agent._narrative_driver_groups = Mock(return_value=[])
        candidate_agent._growth_narrative_sentence_candidates = Mock(
            return_value=[(4, "candidate 99% explanation", ["claim-growth"])]
        )

        def candidate_sanitize(sentence, rows, *, evidence_items=None):
            self.assertEqual(sentence, "candidate 99% explanation")
            self.assertIs(rows, ordered_results)
            self.assertIs(evidence_items, evidence_items_owner)
            return "clean candidate explanation"

        evidence_items_owner = evidence_items
        candidate_strip_owner = Mock(side_effect=candidate_sanitize)
        with (
            patch.object(financial_graph_calculation, "answer_covers_narrative_context", return_value=False),
            patch.object(financial_graph_calculation, "sentence_has_growth_explanatory_signal", return_value=True),
            patch.object(
                financial_graph_calculation,
                "growth_answer_has_untraced_numeric_material",
                return_value=False,
            ),
            patch.object(
                financial_graph_calculation,
                "strip_untraced_numeric_material_from_growth_narrative_sentence",
                candidate_strip_owner,
            ),
        ):
            candidate = financial_graph_calculation.FinancialAgentCalculationMixin._uncovered_supported_growth_narrative_candidate(
                candidate_agent,
                query="growth query",
                answer="base answer",
                ordered_results=ordered_results,
                evidence_items=evidence_items,
            )
        self.assertEqual(
            candidate,
            {"sentence": "clean candidate explanation", "selected_claim_ids": ["claim-growth"]},
        )
        candidate_strip_owner.assert_called_once()

        initial_events = []
        initial_agent = Agent()
        initial_agent._answer_matches_supported_aggregate_subtask = Mock(return_value=False)

        def initial_complete(answer, rows, *, evidence_items=None):
            initial_events.append(("complete", answer, rows, evidence_items))
            return "initial completed answer"

        initial_completion_owner = Mock(side_effect=initial_complete)
        include_owner = Mock(
            side_effect=lambda answer, **kwargs: initial_events.append(("include", answer, kwargs))
            or (_ for _ in ()).throw(RuntimeError("stop after initial completion"))
        )
        initial_state = {"query": "growth query", "report_scope": {}, "nested": nested}
        before_initial_state = deepcopy(initial_state)
        with (
            patch.object(
                financial_graph_calculation.calculation_rendering,
                "coerce_sign_aware_subtraction_answer",
                side_effect=lambda answer, **_kwargs: answer,
            ),
            patch.object(
                financial_graph_calculation.calculation_rendering,
                "compose_slot_based_difference_answer",
                return_value="",
            ),
            patch.object(financial_graph_calculation, "query_requests_explanatory_context", return_value=False),
            patch.object(financial_graph_calculation, "include_narrative_context_if_needed", include_owner),
            patch.object(
                financial_graph_calculation,
                "ensure_complete_growth_numeric_answer",
                initial_completion_owner,
            ),
            self.assertRaisesRegex(RuntimeError, "stop after initial completion"),
        ):
            financial_graph_calculation.FinancialAgentCalculationMixin._apply_initial_aggregate_answer_composition(
                initial_agent,
                initial_state,
                ordered_results=ordered_results,
                preliminary_projection={"calculation_result": {}},
                aggregate_evidence_items=evidence_items,
                narrative_docs=[],
                narrative_context="context",
                final_answer="initial answer",
                supported_aggregate_answer="",
                complete_numeric_answer="",
                has_narrative_summary=True,
                has_growth_rate_result=True,
                numeric_answer_locked=False,
                planner_feedback="",
                deterministic_feedback="",
            )
        self.assertEqual([event[0] for event in initial_events], ["complete", "include"])
        self.assertEqual(initial_events[0][1], "initial answer")
        self.assertIs(initial_events[0][2], ordered_results)
        self.assertIs(initial_events[0][3], evidence_items)
        self.assertEqual(initial_events[1][1], "initial completed answer")
        self.assertEqual(initial_events[1][2], {"query": "growth query", "narrative_context": "context"})

        aggregate_row = {"task_id": "aggregate", "nested": nested}
        aggregate_rows = [aggregate_row]
        aggregate_evidence = [{"evidence_id": "ev-aggregate", "nested": nested}]
        aggregate_state_input = {
            "query": "growth query",
            "report_scope": {},
            "seed_retrieved_docs": [],
            "retrieved_docs": [],
            "plan_loop_count": 0,
            "nested": nested,
        }
        before_aggregate_rows = deepcopy(aggregate_rows)
        before_aggregate_evidence = deepcopy(aggregate_evidence)
        before_aggregate_state = deepcopy(aggregate_state_input)
        prepared = financial_graph_calculation._PreparedAggregateState(
            aggregate_rows,
            "aggregate answer",
            "",
            "",
            True,
            False,
            False,
        )
        evidence_state = financial_graph_calculation._AggregateEvidenceState(
            aggregate_rows,
            aggregate_evidence,
            "aggregate answer",
            "aggregate answer",
            "",
            "",
        )
        composition_state = financial_graph_calculation.AggregateCompositionState(
            "aggregate answer",
            [],
            None,
            False,
            "",
            "",
        )
        feedback_state = financial_graph_calculation._AggregateFeedbackState(
            "aggregate answer",
            "",
            "",
            [],
            {},
            False,
            "",
        )
        aggregate_projection = {
            "calculation_result": {},
            "calculation_operands": [],
            "calculation_plan": {},
        }
        aggregate_completion = Mock(side_effect=RuntimeError("aggregate completion stop"))
        aggregate_downstream = Mock()
        with (
            patch.object(self.agent, "_prepare_initial_aggregate_state", return_value=prepared),
            patch.object(self.agent, "_infer_planner_feedback_from_answer_slots", return_value=""),
            patch.object(self.agent, "_collect_initial_aggregate_evidence_state", return_value=evidence_state),
            patch.object(self.agent, "_rebuild_aggregate_projection", return_value=aggregate_projection),
            patch.object(self.agent, "_runtime_evidence_rows_with_context_docs", return_value=[]),
            patch.object(
                self.agent,
                "_apply_period_context_realignment_to_aggregate",
                side_effect=lambda **kwargs: kwargs["aggregate_state"],
            ),
            patch.object(
                financial_graph_calculation,
                "_aggregate_period_context_evidence_items",
                return_value=aggregate_evidence,
            ),
            patch.object(financial_graph_calculation, "narrative_context_sentence_from_evidence", return_value=""),
            patch.object(
                self.agent,
                "_apply_initial_aggregate_answer_composition",
                return_value=(composition_state, ""),
            ),
            patch.object(
                self.agent,
                "_preserve_source_visible_query_terms",
                side_effect=lambda answer, **_kwargs: answer,
            ),
            patch.object(
                self.agent,
                "_preserve_policy_required_context_in_narrative_results",
                side_effect=lambda rows, **_kwargs: rows,
            ),
            patch.object(self.agent, "_resolve_aggregate_feedback_state", return_value=feedback_state),
            patch.object(financial_graph_calculation, "_aggregate_selected_claim_ids", return_value=[]),
            patch.object(
                self.agent,
                "_align_lookup_results_with_dependency_projection",
                side_effect=lambda rows, _state, _projection: rows,
            ),
            patch.object(
                financial_graph_calculation.calculation_rendering,
                "compose_slot_based_difference_answer",
                return_value="",
            ),
            patch.object(
                self.agent,
                "_prune_irrelevant_growth_narrative_sentences",
                side_effect=lambda **kwargs: kwargs["answer"],
            ),
            patch.object(self.agent, "_answer_matches_supported_aggregate_subtask", return_value=False),
            patch.object(financial_graph_calculation, "query_requests_explanatory_context", return_value=False),
            patch.object(
                financial_graph_calculation,
                "ensure_complete_growth_numeric_answer",
                aggregate_completion,
            ),
            patch.object(self.agent, "_promote_and_align_aggregate_results", aggregate_downstream),
            self.assertRaisesRegex(RuntimeError, "aggregate completion stop"),
        ):
            self.agent._aggregate_calculation_subtasks(aggregate_state_input)
        aggregate_completion.assert_called_once_with(
            "aggregate answer",
            aggregate_rows,
            evidence_items=aggregate_evidence,
        )
        self.assertIs(aggregate_completion.call_args.args[1], aggregate_rows)
        self.assertIs(aggregate_completion.call_args.kwargs["evidence_items"], aggregate_evidence)
        aggregate_downstream.assert_not_called()

        self.assertEqual(ordered_results, before_rows)
        self.assertEqual(evidence_items, before_evidence)
        self.assertEqual(initial_state, before_initial_state)
        self.assertEqual(aggregate_rows, before_aggregate_rows)
        self.assertEqual(aggregate_evidence, before_aggregate_evidence)
        self.assertEqual(aggregate_state_input, before_aggregate_state)
        self.assertIs(row["nested"], nested)
        self.assertIs(evidence_items[0]["nested"], nested)
        self.assertIs(aggregate_row["nested"], nested)
        self.assertIs(aggregate_evidence[0]["nested"], nested)

    def test_current_source_final_surface_projection_pins_identity_copy_and_existing_support(self) -> None:
        owner = financial_aggregate_projection.append_final_answer_surface_operands_from_evidence
        nested = {"preserve": True}
        projection = {
            "calculation_operands": [
                {
                    "label": "metric",
                    "raw_value": "10",
                    "raw_unit": "KRW",
                    "nested": nested,
                }
            ],
            "calculation_result": {"status": "ok", "nested": nested},
            "nested": nested,
        }
        before_projection = deepcopy(projection)

        class EvidenceTruthBomb:
            def __bool__(self):
                raise AssertionError("evidence truthiness must stay lazy")

        with patch.object(
            financial_aggregate_projection,
            "extract_numeric_surface_candidates",
            return_value=[],
        ) as extractor:
            unchanged = owner(projection, EvidenceTruthBomb(), final_answer="blank answer")
        self.assertIs(unchanged, projection)
        extractor.assert_called_once_with("blank answer")

        answer_candidate = {
            "kind": "number",
            "normalized_value": 10.0,
            "value_text": "10",
            "span": [7, 9],
        }
        with patch.object(
            financial_aggregate_projection,
            "extract_numeric_surface_candidates",
            return_value=[answer_candidate],
        ):
            no_evidence = owner(projection, [], final_answer="metric 10")
        self.assertIs(no_evidence, projection)

        extraction_events = []

        def extract(text):
            extraction_events.append(text)
            if text == "metric 10":
                return [dict(answer_candidate)]
            if "metric" in text and "10" in text:
                return [{"kind": "number", "normalized_value": 10.0}]
            return []

        evidence_support_bomb = Mock(side_effect=AssertionError("evidence scan must stay lazy"))
        with (
            patch.object(
                financial_aggregate_projection,
                "extract_numeric_surface_candidates",
                side_effect=extract,
            ),
            patch.object(
                financial_aggregate_projection,
                "numeric_surface_candidates_equivalent",
                side_effect=lambda left, right: left.get("normalized_value") == right.get("normalized_value"),
            ),
            patch.object(
                financial_aggregate_projection,
                "evidence_text_for_numeric_support",
                evidence_support_bomb,
            ),
        ):
            copied = owner(
                projection,
                [{"evidence_id": "unused", "nested": nested}],
                final_answer="metric 10",
            )

        self.assertIsNot(copied, projection)
        self.assertIs(copied["calculation_operands"], projection["calculation_operands"])
        self.assertIs(copied["calculation_operands"][0], projection["calculation_operands"][0])
        self.assertIs(copied["calculation_operands"][0]["nested"], nested)
        self.assertIs(copied["nested"], nested)
        self.assertEqual(copied, projection)
        self.assertEqual(projection, before_projection)
        self.assertIs(projection["nested"], nested)
        evidence_support_bomb.assert_not_called()
        self.assertEqual(extraction_events[0], "metric 10")

        with patch.object(
            financial_aggregate_projection,
            "extract_numeric_surface_candidates",
            side_effect=RuntimeError("surface extraction failed"),
        ), self.assertRaisesRegex(RuntimeError, "surface extraction failed"):
            owner(projection, [], final_answer="metric 10")
        self.assertEqual(projection, before_projection)

    def test_current_source_final_surface_projection_pins_evidence_rank_period_role_and_row_copy(self) -> None:
        owner = financial_aggregate_projection.append_final_answer_surface_operands_from_evidence
        nested = {"preserve": True}
        projection = {
            "calculation_operands": [
                {
                    "status": "ok",
                    "operand_id": "prior_period",
                    "role": "current_period",
                    "matched_operand_role": "current_period",
                    "label": "target metric",
                    "concept": "target_metric",
                    "period": "2024",
                    "raw_value": "999",
                    "raw_unit": "KRW",
                    "nested": nested,
                }
            ],
            "calculation_result": {
                "status": "ok",
                "nested_periods": {"current_period": "2024", "prior_period": "2023"},
            },
            "nested": nested,
        }
        evidence_items = [
            {
                "evidence_id": "recon::first",
                "source_anchor": "first anchor",
                "claim": "2023 target metric 100 KRW",
                "quote_span": "2023 target metric 100 KRW",
                "metadata": {"supports_answer_numeric_surface": True, "nested": nested},
                "nested": nested,
            },
            {
                "evidence_id": "recon::second",
                "source_anchor": "second anchor",
                "claim": "2023 target metric 100 KRW",
                "quote_span": "2023 target metric 100 KRW",
                "metadata": {"supports_answer_numeric_surface": True},
            },
        ]
        before_projection = deepcopy(projection)
        before_evidence = deepcopy(evidence_items)
        answer_candidate = {
            "kind": "number",
            "normalized_value": 100.0,
            "value_text": "100",
            "span": [19, 22],
        }
        evidence_candidate = {"kind": "number", "normalized_value": 100.0}
        relevance_events = []

        def extract(text):
            if text == "In 2023 target metric 100":
                return [dict(answer_candidate)]
            if text == "2023 target metric 100 KRW":
                return [dict(evidence_candidate)]
            if "999" in text:
                return [{"kind": "number", "normalized_value": 999.0}]
            return []

        def relevance(item, **kwargs):
            relevance_events.append((item["evidence_id"], kwargs))
            return 7

        with (
            patch.object(
                financial_aggregate_projection,
                "extract_numeric_surface_candidates",
                side_effect=extract,
            ),
            patch.object(
                financial_aggregate_projection,
                "numeric_surface_candidates_equivalent",
                side_effect=lambda left, right: left.get("normalized_value") == right.get("normalized_value"),
            ),
            patch.object(
                financial_aggregate_projection,
                "evidence_text_for_numeric_support",
                side_effect=lambda item: item.get("quote_span", ""),
            ),
            patch.object(
                financial_aggregate_projection,
                "numeric_evidence_relevance_score",
                side_effect=relevance,
            ),
            patch.object(
                financial_aggregate_projection,
                "numeric_surface_slot_components",
                side_effect=lambda candidate: {
                    "raw_value": "100",
                    "raw_unit": "KRW",
                    "normalized_value": candidate["normalized_value"],
                    "normalized_unit": "KRW",
                    "rendered_value": "100 KRW",
                },
            ),
        ):
            updated = owner(
                projection,
                evidence_items,
                final_answer="In 2023 target metric 100",
            )

        self.assertIsNot(updated, projection)
        self.assertEqual(len(updated["calculation_operands"]), 2)
        appended = updated["calculation_operands"][1]
        self.assertEqual(appended["role"], "prior_period")
        self.assertEqual(appended["matched_operand_role"], "prior_period")
        self.assertEqual(appended["operand_id"], "answer_surface_002")
        self.assertEqual(appended["period"], "2023")
        self.assertEqual(appended["label"], "target metric")
        self.assertEqual(appended["concept"], "target_metric")
        self.assertEqual(appended["source_row_id"], "recon::first")
        self.assertEqual(appended["source_row_ids"], ["recon::first"])
        self.assertEqual(appended["source_anchor"], "first anchor")
        self.assertEqual(appended["source_quote"], "2023 target metric 100 KRW")
        self.assertTrue(appended["projection_backfilled_from_final_evidence"])
        self.assertEqual([event[0] for event in relevance_events], ["recon::first", "recon::second"])
        for _evidence_id, kwargs in relevance_events:
            self.assertEqual(kwargs["answer_text"], "In 2023 target metric 100")
            self.assertEqual(kwargs["period_hint"], "2023")
            self.assertEqual(kwargs["label_hints"], ("target metric", "target_metric"))
        self.assertEqual(projection, before_projection)
        self.assertEqual(evidence_items, before_evidence)
        self.assertIs(projection["nested"], nested)
        self.assertIs(evidence_items[0]["nested"], nested)
        self.assertIs(evidence_items[0]["metadata"]["nested"], nested)

        bonus_evidence = [
            {
                "evidence_id": "recon::lower",
                "claim": "2023 target metric 100 KRW",
                "metadata": {},
            },
            {
                "evidence_id": "operand::higher",
                "claim": "2023 target metric 100 KRW from operand",
                "metadata": {"supports_answer_numeric_surface": True},
            },
        ]
        with (
            patch.object(
                financial_aggregate_projection,
                "extract_numeric_surface_candidates",
                side_effect=lambda text: [dict(answer_candidate)]
                if text == "In 2023 target metric 100"
                else [dict(evidence_candidate)]
                if "100 KRW" in text
                else [],
            ),
            patch.object(
                financial_aggregate_projection,
                "numeric_surface_candidates_equivalent",
                side_effect=lambda left, right: left.get("normalized_value") == right.get("normalized_value"),
            ),
            patch.object(
                financial_aggregate_projection,
                "evidence_text_for_numeric_support",
                side_effect=lambda item: item.get("quote_span") or item.get("claim") or "",
            ),
            patch.object(financial_aggregate_projection, "numeric_evidence_relevance_score", return_value=0),
            patch.object(
                financial_aggregate_projection,
                "numeric_surface_slot_components",
                return_value={"raw_value": "100", "raw_unit": "KRW"},
            ),
        ):
            bonus_selected = owner(
                {"calculation_operands": []},
                bonus_evidence,
                final_answer="In 2023 target metric 100",
            )
        bonus_row = bonus_selected["calculation_operands"][0]
        self.assertEqual(bonus_row["source_row_id"], "operand::higher")
        self.assertEqual(bonus_row["source_quote"], "2023 target metric 100 KRW from operand")

        malformed_candidate = {**answer_candidate, "span": ["bad", 4]}
        with (
            patch.object(
                financial_aggregate_projection,
                "extract_numeric_surface_candidates",
                side_effect=lambda text: [dict(malformed_candidate)]
                if text == "target metric 100"
                else [dict(evidence_candidate)]
                if "target metric 100" in text
                else [],
            ),
            patch.object(
                financial_aggregate_projection,
                "numeric_surface_candidates_equivalent",
                return_value=True,
            ),
            patch.object(
                financial_aggregate_projection,
                "evidence_text_for_numeric_support",
                side_effect=lambda item: item.get("quote_span", ""),
            ),
            patch.object(financial_aggregate_projection, "numeric_evidence_relevance_score", return_value=1),
            patch.object(
                financial_aggregate_projection,
                "numeric_surface_slot_components",
                return_value={"raw_value": "100", "raw_unit": "KRW"},
            ),
        ):
            malformed = owner({}, evidence_items[:1], final_answer="target metric 100")
        self.assertEqual(malformed["calculation_operands"][0]["period"], "")
        self.assertEqual(
            malformed["calculation_operands"][0]["matched_operand_role"],
            "answer_numeric_surface",
        )

        second_text = Mock(side_effect=AssertionError("later evidence must stay untouched"))

        class LaterEvidence(dict):
            def get(self, key, default=None):
                second_text()
                return super().get(key, default)

        with (
            patch.object(
                financial_aggregate_projection,
                "extract_numeric_surface_candidates",
                side_effect=extract,
            ),
            patch.object(financial_aggregate_projection, "numeric_surface_candidates_equivalent", return_value=True),
            patch.object(
                financial_aggregate_projection,
                "evidence_text_for_numeric_support",
                side_effect=lambda item: item.get("quote_span", ""),
            ),
            patch.object(
                financial_aggregate_projection,
                "numeric_evidence_relevance_score",
                side_effect=RuntimeError("relevance failed"),
            ),
            self.assertRaisesRegex(RuntimeError, "relevance failed"),
        ):
            owner(
                {"calculation_operands": []},
                [evidence_items[0], LaterEvidence({"quote_span": "later"})],
                final_answer="In 2023 target metric 100",
            )
        second_text.assert_not_called()

    def test_current_source_final_surface_projection_pins_growth_sync_tolerance_and_slots(self) -> None:
        owner = financial_aggregate_projection.append_final_answer_surface_operands_from_evidence
        nested = {"preserve": True}
        current_row = {
            "status": "ok",
            "role": "current_period",
            "matched_operand_role": "current_period",
            "period": "2024",
            "raw_value": "-120",
            "raw_unit": "KRW",
            "normalized_value": None,
            "source_row_id": "row-current",
            "nested": nested,
        }
        prior_row = {
            "status": "ok",
            "role": "prior_period",
            "matched_operand_role": "prior_period",
            "period": "2023",
            "raw_value": "-80",
            "raw_unit": "KRW",
            "normalized_value": None,
            "source_row_ids": ["row-prior"],
            "nested": nested,
        }
        projection = {
            "calculation_operands": [current_row, prior_row],
            "calculation_result": {
                "status": "stale",
                "derived_metrics": {"preserve": True},
                "nested": nested,
            },
            "calculation_plan": {"status": "stale", "nested": nested},
            "nested": nested,
        }
        evidence_items = [{"evidence_id": "ev", "nested": nested}]
        before_projection = deepcopy(projection)
        before_evidence = deepcopy(evidence_items)
        build_events = []

        def extractor_factory(percent_value):
            def extract(text):
                if text == "target 100; growth display":
                    return [
                        {"kind": "number", "normalized_value": 100.0},
                        {
                            "kind": "percent",
                            "normalized_value": percent_value,
                            "value_text": f"{percent_value}%",
                        },
                    ]
                if "-120" in text or "-80" in text:
                    return [{"kind": "number", "normalized_value": 100.0}]
                return []

            return extract

        def normalize_operand(raw_value, raw_unit):
            self.assertEqual(raw_unit, "KRW")
            return float(raw_value), "KRW"

        def build_slot(row, *, default_role, preserve_source_display):
            build_events.append((row, default_role, preserve_source_display))
            return {
                "role": default_role,
                "normalized_value": row["normalized_value"],
                "raw_value": row["raw_value"],
                "nested": row["nested"],
            }

        with (
            patch.object(
                financial_aggregate_projection,
                "extract_numeric_surface_candidates",
                side_effect=extractor_factory(50.049),
            ),
            patch.object(financial_aggregate_projection, "numeric_surface_candidates_equivalent", return_value=True),
            patch.object(financial_aggregate_projection, "_normalise_operand_value", side_effect=normalize_operand),
            patch.object(
                financial_aggregate_projection,
                "coerce_slot_numeric",
                side_effect=lambda value: None if value is None else float(value),
            ),
            patch.object(
                financial_aggregate_projection,
                "build_operand_value_slot",
                side_effect=build_slot,
            ),
        ):
            synced = owner(
                projection,
                evidence_items,
                final_answer="target 100; growth display",
            )

        result = synced["calculation_result"]
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["operation_family"], "growth_rate")
        self.assertAlmostEqual(result["result_value"], 50.0)
        self.assertEqual(result["rendered_value"], "50.049%")
        self.assertEqual(result["formatted_result"], "target 100; growth display")
        self.assertEqual(result["current_value"], 120.0)
        self.assertEqual(result["prior_value"], 80.0)
        self.assertEqual(result["current_period"], "2024")
        self.assertEqual(result["prior_period"], "2023")
        self.assertEqual(result["source_row_ids"], ["row-current", "row-prior"])
        self.assertTrue(result["derived_metrics"]["preserve"])
        self.assertTrue(result["derived_metrics"]["final_answer_surface_trace_sync"])
        self.assertEqual(synced["calculation_plan"]["operation"], "growth_rate")
        self.assertEqual([event[1] for event in build_events], ["current_period", "prior_period"])
        self.assertTrue(all(event[2] for event in build_events))
        self.assertEqual([event[0]["normalized_value"] for event in build_events], [120.0, 80.0])
        self.assertIs(build_events[0][0]["nested"], nested)
        self.assertIs(result["answer_slots"]["components_by_role"]["current_period"][0]["nested"], nested)
        self.assertEqual(projection, before_projection)
        self.assertEqual(evidence_items, before_evidence)
        self.assertIs(projection["nested"], nested)
        self.assertIs(evidence_items[0]["nested"], nested)

        with (
            patch.object(
                financial_aggregate_projection,
                "extract_numeric_surface_candidates",
                side_effect=extractor_factory(50.051),
            ),
            patch.object(financial_aggregate_projection, "numeric_surface_candidates_equivalent", return_value=True),
            patch.object(financial_aggregate_projection, "_normalise_operand_value", side_effect=normalize_operand),
            patch.object(
                financial_aggregate_projection,
                "coerce_slot_numeric",
                side_effect=lambda value: None if value is None else float(value),
            ),
        ):
            outside = owner(projection, evidence_items, final_answer="target 100; growth display")
        self.assertIsNot(outside, projection)
        self.assertEqual(outside, projection)
        self.assertEqual(outside["calculation_result"]["status"], "stale")

        with (
            patch.object(
                financial_aggregate_projection,
                "extract_numeric_surface_candidates",
                side_effect=extractor_factory(50.0),
            ),
            patch.object(financial_aggregate_projection, "numeric_surface_candidates_equivalent", return_value=True),
            patch.object(financial_aggregate_projection, "_normalise_operand_value", side_effect=normalize_operand),
            patch.object(
                financial_aggregate_projection,
                "coerce_slot_numeric",
                side_effect=lambda value: None if value is None else float(value),
            ),
            patch.object(
                financial_aggregate_projection,
                "build_operand_value_slot",
                side_effect=RuntimeError("slot build failed"),
            ),
            self.assertRaisesRegex(RuntimeError, "slot build failed"),
        ):
            owner(projection, evidence_items, final_answer="target 100; growth display")
        self.assertEqual(projection, before_projection)
        self.assertEqual(evidence_items, before_evidence)

    def test_current_source_final_surface_projection_pins_exact_binding_dag_and_baseline(self) -> None:
        import json
        from pathlib import Path

        retired_target = "_" + "append_final_answer_surface_operands_from_evidence"
        target = "append_final_answer_surface_operands_from_evidence"
        graph_paths = {
            "calculation": Path("src/agent/financial_graph_calculation.py"),
            "graph": Path("src/agent/financial_graph.py"),
            "owner": Path("src/agent/financial_aggregate_projection.py"),
        }
        trees = {
            key: ast.parse(path.read_text(encoding="utf-8-sig"))
            for key, path in graph_paths.items()
        }
        definitions = [
            (key, node)
            for key, tree in trees.items()
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef) and node.name == target
        ]
        self.assertEqual(len(definitions), 1)
        self.assertEqual(definitions[0][0], "owner")
        definition = definitions[0][1]
        self.assertEqual(definition.end_lineno - definition.lineno + 1, 312)
        self.assertEqual(
            sum(
                isinstance(node, ast.Name)
                and node.id == "self"
                and isinstance(node.ctx, ast.Load)
                for node in ast.walk(definition)
            ),
            0,
        )
        self.assertFalse(
            any(
                isinstance(node, ast.FunctionDef)
                and node.name == retired_target
                for tree in trees.values()
                for node in ast.walk(tree)
            )
        )

        calls = []
        for module_name, tree in trees.items():
            parents = {
                child: parent
                for parent in ast.walk(tree)
                for child in ast.iter_child_nodes(parent)
            }
            functions = [node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                func = node.func
                call_name = (
                    func.attr
                    if isinstance(func, ast.Attribute)
                    else func.id
                    if isinstance(func, ast.Name)
                    else ""
                )
                if call_name != target:
                    continue
                containers = [
                    candidate
                    for candidate in functions
                    if candidate.lineno <= node.lineno <= candidate.end_lineno
                ]
                caller = min(containers, key=lambda item: item.end_lineno - item.lineno)
                try_depth = 0
                current = node
                while current in parents:
                    current = parents[current]
                    if isinstance(current, ast.Try):
                        try_depth += 1
                calls.append(
                    (
                        module_name,
                        caller.name,
                        isinstance(func, ast.Attribute) and ast.unparse(func.value),
                        [ast.unparse(arg) for arg in node.args],
                        [(keyword.arg, ast.unparse(keyword.value)) for keyword in node.keywords],
                        try_depth,
                    )
                )
        self.assertEqual(
            sorted(calls),
            sorted(
                [
                    (
                        "calculation",
                        "_filter_final_aggregate_evidence_and_projection",
                        False,
                        ["aggregate_projection", "filtered_evidence_items"],
                        [("final_answer", "final_answer")],
                        0,
                    ),
                    (
                        "graph",
                        "run",
                        False,
                        [
                            "runtime_calculation_trace",
                            "[*list(final_for_evidence.get('evidence_items') or []), *list(runtime_evidence or [])]",
                        ],
                        [("final_answer", "public_answer")],
                        0,
                    ),
                ]
            ),
        )

        selected_loads = Counter(
            node.id
            for node in ast.walk(definition)
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load)
        )
        graph_loads = Counter(
            node.id
            for node in ast.walk(trees["calculation"])
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load)
        )
        self.assertEqual(selected_loads["evidence_text_for_numeric_support"], 1)
        self.assertEqual(selected_loads["numeric_evidence_relevance_score"], 1)
        self.assertEqual(graph_loads["evidence_text_for_numeric_support"], 0)
        self.assertEqual(graph_loads["numeric_evidence_relevance_score"], 0)
        self.assertGreater(graph_loads["_normalise_operand_value"], 0)
        self.assertGreater(graph_loads["financial_answer_slots"], 0)
        self.assertEqual(selected_loads["coerce_slot_numeric"], 2)
        self.assertEqual(selected_loads["build_operand_value_slot"], 2)

        agent_paths = list(Path("src/agent").glob("*.py"))
        module_paths = {path.stem: path for path in agent_paths}
        edges = {name: set() for name in module_paths}
        for name, path in module_paths.items():
            tree = ast.parse(path.read_text(encoding="utf-8-sig"))
            for node in ast.walk(tree):
                imported = []
                if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("src.agent."):
                    imported = [node.module.rsplit(".", 1)[-1]]
                elif isinstance(node, ast.Import):
                    imported = [
                        alias.name.rsplit(".", 1)[-1]
                        for alias in node.names
                        if alias.name.startswith("src.agent.")
                    ]
                edges[name].update(value for value in imported if value in module_paths)

        def reaches(source, destination):
            pending = [source]
            seen = set()
            while pending:
                current = pending.pop()
                if current == destination:
                    return True
                if current in seen:
                    continue
                seen.add(current)
                pending.extend(edges[current] - seen)
            return False

        for dependency in (
            "financial_numeric_surface",
            "financial_answer_slots",
            "financial_runtime_normalization",
        ):
            self.assertTrue(reaches("financial_aggregate_projection", dependency))
            self.assertFalse(reaches(dependency, "financial_aggregate_projection"))
        self.assertFalse(reaches("financial_aggregate_projection", "financial_graph"))
        self.assertFalse(reaches("financial_aggregate_projection", "financial_graph_calculation"))

        baseline = json.loads(
            Path("tests/fixtures/runtime_domain_terms_baseline.json").read_text(encoding="utf-8-sig")
        )
        self.assertEqual(len(baseline["records"]), 217)
        selected_records = [
            record
            for record in baseline["records"]
            if str(record.get("path") or "").endswith("financial_graph_calculation.py")
            and any(4862 <= int(line) <= 5174 for line in record.get("first_lines") or [])
        ]
        self.assertEqual(selected_records, [])
        self.assertEqual(313 - 1, 312)

        retired_test_ref_modules = {
            path.stem
            for path in Path("tests").glob("test_*.py")
            if retired_target in path.read_text(encoding="utf-8-sig")
        }
        self.assertEqual(retired_test_ref_modules, set())
        current_test_ref_modules = {
            path.stem
            for path in Path("tests").glob("test_*.py")
            if target in path.read_text(encoding="utf-8-sig")
        }
        self.assertEqual(
            current_test_ref_modules,
            {
                "test_financial_aggregate_rank_dedupe",
                "test_financial_numeric_provenance",
                "test_subtask_loop",
            },
        )

    def test_current_source_final_surface_filter_caller_pins_args_adoption_order_and_stop(self) -> None:
        nested = {"preserve": True}
        aggregate_evidence = [
            {"evidence_id": "ev-keep", "nested": nested},
            {"evidence_id": "operand::new", "nested": nested},
        ]
        aggregate_projection = {"calculation_operands": [], "nested": nested}
        selected_claim_ids = ["drop", "ev-keep"]
        before_evidence = deepcopy(aggregate_evidence)
        before_projection = deepcopy(aggregate_projection)
        before_selected = list(selected_claim_ids)
        filtered = [aggregate_evidence[0], aggregate_evidence[1]]
        provenance_projection = {"calculation_operands": [], "provenance": True, "nested": nested}
        appended_projection = {"calculation_operands": [{"role": "prior"}], "nested": nested}
        events = []

        class ProjectionOutcome:
            def __init__(self, projection):
                self.aggregate_projection = projection

        def filter_evidence(items, *, final_answer, selected_claim_ids):
            events.append(("filter", items, final_answer, selected_claim_ids))
            return filtered

        def filter_projection(request):
            events.append(("provenance", request.aggregate_projection, request.kept_evidence_ids))
            return ProjectionOutcome(provenance_projection)

        def append_surface(projection, items, *, final_answer):
            events.append(("append", projection, items, final_answer))
            return appended_projection

        agent = Mock()
        append_owner = Mock(side_effect=append_surface)
        with (
            patch.object(
                financial_graph_calculation,
                "filter_aggregate_evidence_for_final_answer",
                side_effect=filter_evidence,
            ),
            patch.object(
                financial_graph_calculation,
                "filter_aggregate_projection_provenance",
                side_effect=filter_projection,
            ),
            patch.object(
                financial_graph_calculation,
                "append_final_answer_surface_operands_from_evidence",
                append_owner,
            ),
        ):
            result = financial_graph_calculation.FinancialAgentCalculationMixin._filter_final_aggregate_evidence_and_projection(
                agent,
                aggregate_evidence,
                aggregate_projection,
                final_answer="final 100",
                selected_claim_ids=selected_claim_ids,
            )

        returned_evidence, returned_projection, returned_claims, returned_ids = result
        self.assertIs(returned_evidence, filtered)
        self.assertIs(returned_projection, appended_projection)
        self.assertEqual(returned_claims, ["ev-keep", "operand::new"])
        self.assertEqual(returned_ids, ["ev-keep", "operand::new"])
        self.assertEqual([event[0] for event in events], ["filter", "provenance", "append"])
        self.assertIs(events[0][1], aggregate_evidence)
        self.assertIs(events[0][3], selected_claim_ids)
        self.assertIs(events[1][1], aggregate_projection)
        self.assertIs(events[2][1], provenance_projection)
        self.assertIs(events[2][2], filtered)
        self.assertEqual(events[2][3], "final 100")
        self.assertEqual(aggregate_evidence, before_evidence)
        self.assertEqual(aggregate_projection, before_projection)
        self.assertEqual(selected_claim_ids, before_selected)
        self.assertIs(aggregate_evidence[0]["nested"], nested)
        self.assertIs(aggregate_projection["nested"], nested)

        failure_events = []
        failing_agent = Mock()

        def fail_append(projection, items, *, final_answer):
            failure_events.append(("append", projection, items, final_answer))
            raise RuntimeError("surface append failed")

        failing_append_owner = Mock(side_effect=fail_append)
        with (
            patch.object(
                financial_graph_calculation,
                "filter_aggregate_evidence_for_final_answer",
                return_value=filtered,
            ),
            patch.object(
                financial_graph_calculation,
                "filter_aggregate_projection_provenance",
                return_value=ProjectionOutcome(provenance_projection),
            ),
            patch.object(
                financial_graph_calculation,
                "append_final_answer_surface_operands_from_evidence",
                failing_append_owner,
            ),
            self.assertRaisesRegex(RuntimeError, "surface append failed"),
        ):
            financial_graph_calculation.FinancialAgentCalculationMixin._filter_final_aggregate_evidence_and_projection(
                failing_agent,
                aggregate_evidence,
                aggregate_projection,
                final_answer="final 100",
                selected_claim_ids=selected_claim_ids,
            )
        self.assertEqual(failure_events, [("append", provenance_projection, filtered, "final 100")])
        self.assertEqual(aggregate_evidence, before_evidence)
        self.assertEqual(aggregate_projection, before_projection)

    def test_current_source_final_surface_run_caller_pins_constructed_evidence_adoption_and_stop(self) -> None:
        nested = {"preserve": True}
        final_evidence = {"evidence_id": "final", "nested": nested}
        runtime_evidence_row = {"evidence_id": "runtime", "nested": nested}
        final_state = {
            "answer": " public 100 ",
            "citations": [],
            "evidence_items": [final_evidence],
            "structured_result": {},
            "tasks": [],
            "artifacts": [],
            "nested": nested,
        }
        before_final = deepcopy(final_state)
        initial_trace = {"calculation_operands": [], "trace": "initial", "nested": nested}
        repaired_trace = {"calculation_operands": [], "trace": "repaired", "nested": nested}
        structured_trace = {"calculation_operands": [], "trace": "structured", "nested": nested}
        ratio_trace = {"calculation_operands": [], "trace": "ratio", "nested": nested}
        appended_trace = {"calculation_operands": [{"raw_value": "100"}], "trace": "appended"}

        class FakeGraph:
            def __init__(self, state):
                self.state = state

            def invoke(self, initial):
                self.initial = initial
                return self.state

        def configure(events):
            agent = financial_graph.FinancialAgent.__new__(financial_graph.FinancialAgent)
            agent.graph = FakeGraph(final_state)
            agent.vsm = object()
            agent._project_runtime_calculation_trace = Mock(return_value=initial_trace)
            agent._repair_public_runtime_calculation_trace = Mock(
                side_effect=[initial_trace, repaired_trace]
            )
            agent._late_runtime_numeric_answer = Mock(return_value="")

            def with_public(state, answer):
                return {**dict(state), "answer": answer, "compressed_answer": answer}

            agent._with_public_answer = Mock(side_effect=with_public)
            agent._runtime_evidence_from_retrieved_docs = Mock(return_value=[runtime_evidence_row])
            agent._complete_aggregate_public_answer_projection = Mock(return_value=("", {}))
            agent._structured_result_answer_for_missing_public_answer = Mock(return_value="")
            agent._apply_stale_structured_numeric_public_answer_repair = Mock(
                side_effect=lambda state, **kwargs: (
                    kwargs["public_answer"],
                    state,
                    kwargs["runtime_calculation_trace"],
                )
            )
            agent._structured_public_answer_trace_projection = Mock(return_value=structured_trace)
            agent._retrieved_ratio_context_projection_for_public_answer = Mock(return_value=ratio_trace)
            agent._project_debug_traces = Mock(
                side_effect=lambda _final: events.append("debug") or {}
            )
            agent._augment_citations_from_runtime_evidence = Mock(
                side_effect=lambda citations, evidence: events.append("citations") or []
            )
            agent._project_agent_answer = Mock(
                side_effect=lambda _final, **kwargs: events.append("agent-answer")
                or {
                    "answer": kwargs["public_answer"],
                    "resolved_calculation_trace": kwargs["runtime_calculation_trace"],
                }
            )
            agent._project_review_trace = Mock(return_value={})
            agent._project_debug_bundle = Mock(return_value={})
            return agent

        success_events = []

        def append_surface(trace, evidence, *, final_answer):
            success_events.append(("append", trace, evidence, final_answer))
            return appended_trace

        agent = configure(success_events)
        with (
            patch.object(financial_graph, "_structured_result_subtask_rows_and_answer", return_value=([], "")),
            patch.object(financial_graph, "_project_task_artifact_trace", return_value={}),
            patch.object(
                financial_graph,
                "append_final_answer_surface_operands_from_evidence",
                side_effect=append_surface,
            ),
        ):
            result = financial_graph.FinancialAgent.run(agent, "query")

        self.assertIs(result["resolved_calculation_trace"], appended_trace)
        self.assertEqual([event if isinstance(event, str) else event[0] for event in success_events], [
            "append",
            "debug",
            "citations",
            "agent-answer",
        ])
        append_event = success_events[0]
        self.assertIs(append_event[1], ratio_trace)
        self.assertEqual(append_event[3], "public 100")
        constructed_evidence = append_event[2]
        self.assertEqual(constructed_evidence, [final_evidence, runtime_evidence_row])
        self.assertIsNot(constructed_evidence, final_state["evidence_items"])
        self.assertIs(constructed_evidence[0], final_evidence)
        self.assertIs(constructed_evidence[1], runtime_evidence_row)
        self.assertIs(agent._project_agent_answer.call_args.kwargs["runtime_calculation_trace"], appended_trace)
        self.assertEqual(final_state, before_final)
        self.assertIs(final_state["nested"], nested)
        self.assertIs(final_evidence["nested"], nested)
        self.assertIs(runtime_evidence_row["nested"], nested)

        failure_events = []

        def fail_append(trace, evidence, *, final_answer):
            failure_events.append(("append", trace, evidence, final_answer))
            raise RuntimeError("run surface append failed")

        failing_agent = configure(failure_events)
        with (
            patch.object(financial_graph, "_structured_result_subtask_rows_and_answer", return_value=([], "")),
            patch.object(financial_graph, "_project_task_artifact_trace", return_value={}),
            patch.object(
                financial_graph,
                "append_final_answer_surface_operands_from_evidence",
                side_effect=fail_append,
            ),
            self.assertRaisesRegex(RuntimeError, "run surface append failed"),
        ):
            financial_graph.FinancialAgent.run(failing_agent, "query")
        self.assertEqual(len(failure_events), 1)
        self.assertIs(failure_events[0][1], ratio_trace)
        self.assertEqual(failure_events[0][2], [final_evidence, runtime_evidence_row])
        failing_agent._project_debug_traces.assert_not_called()
        failing_agent._augment_citations_from_runtime_evidence.assert_not_called()
        failing_agent._project_agent_answer.assert_not_called()
        self.assertEqual(final_state, before_final)
        self.assertIs(final_evidence["nested"], nested)
        self.assertIs(runtime_evidence_row["nested"], nested)


if __name__ == "__main__":
    unittest.main()
