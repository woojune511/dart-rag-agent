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
            local_agent._growth_required_display_values = Mock(return_value=["10%", "200", "100"])
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
                    "_growth_required_display_values": 3,
                    "_compose_complete_growth_numeric_answer": 2,
                    "_compose_growth_narrative_answer": 2,
                }
            ),
        )
        self.assertEqual(
            Counter(stack[-1] for _module, stack, _receiver, _args, _kwargs in calls["share"]),
            Counter(
                {
                    "_growth_required_display_values": 1,
                    "_compose_complete_growth_numeric_answer": 1,
                    "_compose_growth_narrative_answer": 1,
                    "_recover_duplicate_growth_prior_operand": 1,
                }
            ),
        )
        self.assertEqual(
            Counter(stack[-1] for _module, stack, _receiver, _args, _kwargs in calls["recover"]),
            Counter(
                {
                    "_growth_required_display_values": 1,
                    "_compose_complete_growth_numeric_answer": 1,
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
            patch.object(financial_graph_calculation, "growth_slot_display_value", side_effect=display) as display_owner,
            patch.object(financial_graph_calculation, "growth_slots_share_material", side_effect=share) as share_owner,
            patch.object(
                financial_graph_calculation,
                "recover_growth_prior_material_from_evidence",
                side_effect=recover,
            ) as recover_owner,
        ):
            values = self.agent._growth_required_display_values(
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
            patch.object(financial_graph_calculation, "growth_slot_display_value", side_effect=["PRIOR", "CURRENT"]) as display_owner,
            patch.object(financial_graph_calculation, "growth_slots_share_material", return_value=False),
            patch.object(financial_graph_calculation, "recover_growth_prior_material_from_evidence", recovery_owner),
        ):
            self.assertEqual(
                self.agent._growth_required_display_values(row, ordered_results, evidence_items),
                ["CURRENT", "PRIOR", "GROWTH"],
            )
        recovery_owner.assert_not_called()
        self.assertEqual(display_owner.call_count, 2)
        primary_display.assert_not_called()

        recovery_owner = Mock()
        current_display = Mock(side_effect=AssertionError("current display accessed"))
        with (
            patch.object(financial_graph_calculation, "growth_slot_display_value", side_effect=["PRIOR", current_display]),
            patch.object(
                financial_graph_calculation,
                "growth_slots_share_material",
                side_effect=RuntimeError("share failed"),
            ),
            patch.object(financial_graph_calculation, "recover_growth_prior_material_from_evidence", recovery_owner),
            self.assertRaisesRegex(RuntimeError, "share failed"),
        ):
            self.agent._growth_required_display_values(row, ordered_results, evidence_items)
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
            patch.object(self.agent, "_aggregate_result_operation_family", return_value="growth_rate"),
            patch.object(financial_graph_calculation, "answer_slot_has_material", return_value=True),
            patch.object(financial_graph_calculation, "growth_slot_display_value", side_effect=display) as display_owner,
            patch.object(financial_graph_calculation, "growth_slots_share_material", side_effect=share) as share_owner,
            patch.object(
                financial_graph_calculation,
                "recover_growth_prior_material_from_evidence",
                side_effect=recover,
            ) as recover_owner,
            patch.object(financial_graph_calculation.calculation_rendering, "absolute_display_value", absolute),
            patch.object(financial_graph_calculation, "CALCULATION_SLOT_POLICY", {"period_pattern": r"$^"}),
            patch.object(financial_graph_calculation, "CALCULATION_NARRATIVE_POLICY", policy),
            patch.object(financial_graph_calculation, "_topic_particle", return_value="|P|"),
        ):
            answer = self.agent._compose_complete_growth_numeric_answer(
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
            patch.object(self.agent, "_aggregate_result_operation_family", return_value="growth_rate"),
            patch.object(financial_graph_calculation, "answer_slot_has_material", return_value=True),
            patch.object(
                financial_graph_calculation,
                "growth_slot_display_value",
                side_effect=RuntimeError("display failed"),
            ),
            patch.object(financial_graph_calculation, "growth_slots_share_material", downstream_share),
            patch.object(financial_graph_calculation, "recover_growth_prior_material_from_evidence", downstream_recovery),
            patch.object(financial_graph_calculation.calculation_rendering, "absolute_display_value", downstream_absolute),
            self.assertRaisesRegex(RuntimeError, "display failed"),
        ):
            self.agent._compose_complete_growth_numeric_answer(row, ordered_results, evidence_items)
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
            local_agent._growth_required_display_values = Mock(return_value=[])
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
        downstream_required = local_agent._growth_required_display_values
        with (
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
        initial_agent._ensure_complete_growth_numeric_answer = Mock(
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
        initial_agent._ensure_complete_growth_numeric_answer.assert_not_called()

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
            agent._append_operand_evidence_for_final_answer = Mock(
                side_effect=lambda current, **_kwargs: current
            )
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


if __name__ == "__main__":
    unittest.main()
