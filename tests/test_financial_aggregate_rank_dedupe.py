import ast
import inspect
import unittest
from collections import Counter
from copy import deepcopy
from unittest.mock import Mock, patch

from src.agent import financial_aggregate_projection, financial_graph_calculation


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


if __name__ == "__main__":
    unittest.main()
