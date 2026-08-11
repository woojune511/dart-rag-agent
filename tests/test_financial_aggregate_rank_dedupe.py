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
            local_agent._growth_slot_display_value = Mock(side_effect=["200", "100"])
            local_agent._growth_slots_share_material = Mock(return_value=False)
            local_agent._growth_required_display_values = Mock(return_value=["10%", "200", "100"])
            return local_agent, row

        policy = dict(financial_graph_calculation.CALCULATION_NARRATIVE_POLICY)

        def run_with_selected(context_result, sentence_result):
            local_agent, row = configured_agent()
            runtime_results = [row]
            context_owner = Mock(return_value=context_result)
            sentence_owner = Mock(return_value=sentence_result)
            before_row = deepcopy(row)
            before_evidence = deepcopy(evidence_items)
            with (
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
            patch.object(financial_graph_calculation, "_query_requests_narrative_context", return_value=True),
            patch.object(financial_graph_calculation, "answer_looks_truncated", return_value=False),
            patch.object(financial_graph_calculation, "growth_row_has_conflicting_periods", return_value=False),
            patch.object(financial_graph_calculation, "answer_slot_has_material", return_value=True),
            patch.object(financial_graph_calculation, "CALCULATION_NARRATIVE_POLICY", policy),
            patch.object(financial_graph_calculation, "narrative_focus_variants", return_value=["Needle"]),
            patch.object(financial_graph_calculation, "parenthetical_focus_variants", return_value=["Needle"]),
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
            patch.object(self.agent, "_growth_required_display_values", return_value=[]),
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
            patch.object(self.agent, "_growth_required_display_values", return_value=[]),
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
            patch.object(self.agent, "_growth_required_display_values", return_value=[]),
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


if __name__ == "__main__":
    unittest.main()
