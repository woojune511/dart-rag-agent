from copy import deepcopy
import unittest

from src.agent.financial_graph_calculation import build_semantic_compilation_islands
from src.agent.financial_calculation_execution import validate_semantic_calculation_program
from tests.semantic_program_test_support import _obligation, _candidate
from tests.test_numeric_subject_authority import authored_interpretation


def relate(owners, query="Use a common basis."):
    relation = {"kind": "shared_basis", "output_ids": [row["obligation_id"] for row in owners],
                "request_unit_id": "request_001", "request_text": query}
    return [{**row, "output_relationships": [deepcopy(relation)]} for row in owners]


class OutputRelationshipTests(unittest.TestCase):
    def test_shared_topic_does_not_connect_but_request_relation_does(self):
        owners = [_obligation("a", "direct_value", "same topic"), _obligation("b", "direct_value", "same topic")]
        self.assertEqual(len(build_semantic_compilation_islands(owners)["islands"]), 2)
        connected = build_semantic_compilation_islands(relate(owners), query="Use a common basis.")
        self.assertEqual(len(connected["islands"]), 1)
        self.assertTrue(connected["islands"][0]["output_relationships"])

    def test_unknown_self_and_ungrounded_relations_block_before_calls(self):
        owners = relate([_obligation("a", "direct_value", "first"), _obligation("b", "direct_value", "second")])
        for field, value in (("output_ids", ["a", "unknown"]), ("output_ids", ["a", "a"]),
                             ("request_text", "Invented request"), ("request_unit_id", "request_002")):
            changed = deepcopy(owners)
            for owner in changed:
                owner["output_relationships"][0][field] = value
            with self.subTest(field=field, value=value):
                plan = build_semantic_compilation_islands(changed, query="Use a common basis.")
                self.assertEqual(plan["status"], "invalid")
                self.assertTrue(all(island["errors"] for island in plan["islands"]))

    def test_legacy_grouping_is_not_silently_accepted(self):
        owner = _obligation("a", "direct_value", "first", coupling_key="arbitrary")
        plan = build_semantic_compilation_islands([owner])
        self.assertEqual(plan["status"], "invalid")
        self.assertEqual(plan["islands"][0]["errors"][0]["repair_action"], "repair_requirements")

    def test_basis_interpretation_is_distinct_from_physical_table_identity(self):
        owners = relate([_obligation("a", "direct_value", "first"), _obligation("b", "direct_value", "second")])
        catalog = [_candidate("ca", 9, context="table-a"), _candidate("cb", 9, context="table-b")]
        bindings = [{"obligation_id": row["obligation_id"], "candidate_id": candidate["candidate_id"],
            "source_interpretation": {**authored_interpretation(candidate, "Maple"), "scope": {"basis": "reported scope"}}}
            for row, candidate in zip(owners, catalog)]
        result = validate_semantic_calculation_program(program={"direct_bindings": bindings}, obligations=owners,
            candidate_catalog=catalog, query="Use a common basis.")
        self.assertEqual(result["status"], "ready", result["errors"])
        bindings[1]["source_interpretation"]["scope"]["basis"] = "different declaration"
        result = validate_semantic_calculation_program(program={"direct_bindings": bindings}, obligations=owners,
            candidate_catalog=catalog, query="Use a common basis.")
        self.assertEqual(result["status"], "invalid")
        self.assertIn("relationship_interpretation_missing_or_inconsistent", [row["code"] for row in result["errors"]])


if __name__ == "__main__":
    unittest.main()
