"""Authored request/display contracts, not sampled-model semantic accuracy."""

from copy import deepcopy
import unittest

from src.agent.financial_calculation_execution import execute_semantic_calculation_program
from src.agent.financial_graph import FinancialAgent
from src.agent.financial_reconciliation_candidates import build_semantic_candidate_catalog
from tests.semantic_program_test_support import _obligation, _requirement, execute_compiled_fixture


def fixture(initial="70", final="84", reported="19.8", name="Atlas", year="2043"):
    text = (f"In {year}, {name} recorded initial quantity {initial}, final quantity {final}; "
            f"reported change is {reported}%.")
    catalog = build_semantic_candidate_catalog([{
        "candidate_id": "source-" + name, "candidate_kind": "chunk",
        "source_anchor": "[synthetic passage]", "text": text,
        "source_text_exact": text, "metadata": {"is_table": False},
    }])
    by_surface = {row["raw_value"]: row for row in catalog if row["kind"] == "numeric"}
    return {"catalog": catalog, "initial": by_surface[initial], "final": by_surface[final],
            "reported": by_surface[reported], "text": text}


class AuthoredDisplayLLM:
    """Emit fixed nested wire choices; no prompt reading or semantic inference."""

    def __init__(self, case, *, use_display=False, omit_first_decision=False, direct=False):
        self.case, self.use_display = case, use_display
        self.omit_first_decision, self.direct = omit_first_decision, direct
        self.prompts, self.models = [], []

    def with_structured_output(self, model):
        self.models.append(model)
        return self

    def invoke(self, prompt):
        self.prompts.append(prompt)
        refs = self.models[-1].__compiler_references__

        def selection(key):
            candidate = self.case[key]
            return {"source_ref": refs.ref(candidate["candidate_id"]),
                    "evidence_text": candidate["raw_value"] + candidate["raw_unit"]}

        result = {"selection": selection("reported")} if self.direct else {
            "inputs": {"initial": [{**selection("initial"), "variable": "P"}],
                       "final": [{**selection("final"), "variable": "Q"}]},
            "comparison_request_unit_id": None, "formula": "(Q - P) / P * 100", "display_unit": "%",
            "source_display": selection("reported") if self.use_display else None,
            "source_display_reason": ("The request includes the reported figure alongside calculation."
                if self.use_display else "The request asks for calculation from the quantities only."),
            "constants": [],
        }
        if self.omit_first_decision and len(self.prompts) == 1:
            result.pop("source_display")
        return self.models[-1].model_validate({"outputs": {"answer": {"status": "ready", "result": result}}})


def compile_case(case, question, **options):
    direct = options.get("direct", False)
    owner = _obligation("answer", "direct_value" if direct else "derived_value", "change", display_unit="%",
        evidence_requirements=[] if direct else [
            _requirement("initial", "initial quantity"), _requirement("final", "final quantity")])
    llm = AuthoredDisplayLLM(case, **options)
    agent = object.__new__(FinancialAgent)
    agent.llm, agent.llm_routes, agent.llm_usage_callback = llm, {}, None
    state = {"query": question, "answer_obligations": [owner], "include_debug_bundle": True,
        "semantic_candidate_catalog_prebuilt": True, "semantic_source_candidates": case["catalog"],
        "semantic_candidate_catalog": case["catalog"]}
    compiled = agent._compile_semantic_calculation_program(state)
    return agent, state, compiled


class CompilerDisplayIntentTests(unittest.TestCase):
    def assert_ready(self, compiled):
        self.assertEqual(compiled["semantic_program_validation"]["status"], "ready",
                         compiled["semantic_program_validation"]["errors"])

    def execute(self, agent, state, compiled):
        self.assert_ready(compiled)
        return execute_compiled_fixture(agent, {**state, **compiled}, state["semantic_candidate_catalog"])

    def test_production_schema_explains_request_priority_without_extra_display_fields(self):
        agent, _, _ = compile_case(fixture(), "Calculate the change using the quantities only.")
        result = agent.llm.models[0].model_json_schema()["$defs"]["Calculation_answer"]
        props = result["properties"]
        self.assertEqual(set(props), {"comparison_request_unit_id", "inputs", "formula", "display_unit", "display_format",
            "source_display", "source_display_reason", "compatibility_refs", "constants"})
        self.assertIn("source_display", result["required"])
        self.assertIn({"type": "null"}, props["source_display"]["anyOf"])
        self.assertIn("calculation-only", props["source_display"].get("description", ""))
        self.assertIn("request", props["source_display_reason"].get("description", ""))

    def test_request_priority_and_exact_query_reach_initial_and_same_cohort_retry(self):
        question = "표시된 수량만으로 변화율을 계산하고 원문 보고 비율을 주 결과로 쓰지 마세요."
        agent, state, compiled = compile_case(fixture(), question, omit_first_decision=True)
        self.assert_ready(compiled)
        self.assertEqual(compiled["semantic_program_retry_count"], 1)
        self.assertEqual(len(agent.llm.prompts), 2)
        for prompt in agent.llm.prompts:
            content = prompt.to_messages()[0].content
            self.assertIn(question, content)
            self.assertTrue("명시적인 요청이 원문 우선 기본값보다 우선" in content,
                            "Initial and retry prompts must state request precedence.")
            self.assertTrue("계산값만 요청하면 source_display=null" in content,
                            "Calculation-only intent must have an explicit null-display instruction.")
        attempts = compiled["resolved_calculation_trace"]["calculation_plan"]["candidate_stage_diagnostics"]["attempts"]
        self.assertEqual(attempts[0]["visible_candidate_ids"], attempts[1]["visible_candidate_ids"])

    def test_authored_display_choices_survive_normalizer_compiler_final_and_ledger(self):
        for initial, final, reported, name, year in (
            ("70", "84", "19.8", "Atlas", "2043"),
            ("8", "6", "-24.7", "Birch", "2047"),
            ("60", "75", "25.00", "Cobalt", "2051"),
        ):
            case = fixture(initial, final, reported, name, year)
            calculated = (float(final) - float(initial)) / float(initial) * 100
            permissions = []
            before = deepcopy(case["catalog"])
            for use_display in (False, True):
                with self.subTest(initial=initial, use_display=use_display):
                    question = ("Report the source figure and the independently calculated change."
                        if use_display else "Compute the change from quantities alone.")
                    agent, state, compiled = compile_case(case, question, use_display=use_display)
                    result = self.execute(agent, state, compiled)
                    self.assertEqual(len(agent.llm.prompts), 1)
                    self.assertEqual(compiled["semantic_program"]["expressions"][0]["source_display_candidate_id"],
                                     case["reported"]["candidate_id"] if use_display else None)
                    trace = result["resolved_calculation_trace"]["calculation_result"]
                    self.assertAlmostEqual(trace["calculated_result_value"], calculated)
                    self.assertAlmostEqual(trace["result_value"], float(reported) if use_display else calculated)
                    self.assertEqual(result["task_artifact_trace"]["integrity_status"], "ok")
                    aggregate = next(row["payload"] for row in result["artifacts"] if row["kind"] == "aggregated_answer")
                    self.assertEqual(aggregate["final_answer"], result["answer"])
                    self.assertEqual(aggregate["structured_result"], result["structured_result"])
                    if use_display:
                        self.assertIn(reported + "%", result["answer"])
                    elif float(reported) != calculated:
                        self.assertNotIn(reported + "%", result["answer"])
                    permissions.append(compiled["semantic_compilation_envelope"].visibility)
            self.assertEqual(permissions[0], permissions[1])
            self.assertEqual(case["catalog"], before)

    def test_direct_lookup_keeps_reported_precision(self):
        agent, state, compiled = compile_case(fixture(reported="19.800"),
            "What change does the source explicitly report?", direct=True)
        result = self.execute(agent, state, compiled)
        self.assertIn("19.800%", result["answer"])
        self.assertEqual(len(agent.llm.prompts), 1)

    def test_wrong_authored_semantic_choice_is_not_silently_repaired_or_retried(self):
        # Wrong meaning with valid source linkage remains an evaluation negative.
        agent, state, compiled = compile_case(fixture(),
            "Calculate the change from the quantities only.", use_display=True)
        result = self.execute(agent, state, compiled)
        self.assertEqual(result["resolved_calculation_trace"]["calculation_result"]["result_value"], 19.8)
        self.assertEqual(compiled["semantic_program_retry_count"], 0)
        self.assertEqual(len(agent.llm.prompts), 1)

    def test_query_and_display_tampering_still_fail_execution_fingerprints(self):
        agent, state, compiled = compile_case(fixture(), "Compute the change from quantities alone.")
        self.assert_ready(compiled)
        for change in ("query", "display"):
            with self.subTest(change=change):
                program, query = deepcopy(compiled["semantic_program"]), state["query"]
                if change == "query":
                    query = "Report the source figure instead."
                else:
                    program["expressions"][0]["source_display_candidate_id"] = fixture()["reported"]["candidate_id"]
                execution = execute_semantic_calculation_program(program=program,
                    obligations=state["answer_obligations"], candidate_catalog=state["semantic_candidate_catalog"],
                    query=query, compilation_envelope=compiled["semantic_compilation_envelope"],
                    require_compilation_envelope=True)
                self.assertNotEqual(execution["status"], "ok")
                self.assertEqual(execution["outputs"], [])


if __name__ == "__main__":
    unittest.main()
