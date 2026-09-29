"""Caller projections preserve evidence while compiler records stay opt-in."""
from copy import deepcopy
import json
import unittest

from src.agent.financial_graph import FinancialAgent
from tests.test_financial_agent_run_projection import _Graph
from tests.test_financial_api_contract import _client, _services


def _fixture():
    program = {"expressions": [{"display_format": "自由な内部書式"}]}
    validation = {"status": "ready", "valid_expressions": program["expressions"]}
    obligations = [{"obligation_id": "o1", "display_format": "keep the requested unit"}]
    # These names and languages are legitimate source data, not projection keys.
    source = {"source_ref": "s1", "period": "prior", "value": "14",
              "display_format": "原文の引用", "semantic_program": "source literal",
              "validation": "verbatim"}
    public_trace = {
        "calculation_operands": [source],
        "calculation_plan": {
            "operation": "semantic_program", "answer_obligations": obligations,
            "execution_content_fingerprint": "original-content-fingerprint",
        },
        "calculation_result": {
            "status": "ok", "result_value": -4, "result_unit": "units",
            "outputs": [{"formula": "current - prior", "value": -4,
                         "source_evidence_ids": ["s1", "s2"]}],
        },
    }
    canonical_trace = deepcopy(public_trace)
    canonical_trace["calculation_plan"].update({
        "semantic_program": program,
        "program_validation": validation,
        "program_validation_history": [{"island_id": "i1", "validation": validation}],
    })
    canonical_trace["calculation_result"]["validation"] = validation
    answer = {
        "query": "return the difference", "query_type": "numeric_fact",
        "companies": [], "years": [], "answer": "-4 units; source: 原文の引用",
        "citations": ["s1", "s2"], "resolved_calculation_trace": canonical_trace,
        "structured_result": {
            "status": "ok", "answer": "-4 units; source: 原文の引用",
            "answer_obligations": obligations,
            "resolved_calculation_trace": canonical_trace,
        },
    }
    state = {
        "final_result": {
            "agent_answer": answer,
            "review_trace": {"semantic_program": program,
                             "semantic_program_validation": validation},
            "debug_traces": {},
        },
        "ledger": {
            "tasks": [], "artifacts": [{"payload": canonical_trace}],
            "task_artifact_trace": {"integrity_status": "ok"},
        },
        "compilation": {
            "compiler_attempts": [{"parsed_response_json": json.dumps(program)}],
        },
    }
    agent = object.__new__(FinancialAgent)
    agent.graph = _Graph(state)
    agent.llm_usage_callback = None
    agent.vsm = None
    return agent, state, public_trace


class FinancialPublicTraceProjectionTests(unittest.TestCase):
    def assert_public_answer(self, answer, original, expected_trace):
        expected = deepcopy(original)
        expected["resolved_calculation_trace"] = expected_trace
        expected["structured_result"]["resolved_calculation_trace"] = expected_trace
        self.assertEqual(answer, expected)

    def test_caller_excludes_internal_records_from_both_trace_paths(self):
        agent, state, expected_trace = _fixture()
        original = deepcopy(state)

        result = agent.run("return the difference")

        self.assert_public_answer(result.agent_answer,
                                  original["final_result"]["agent_answer"], expected_trace)
        self.assertIsNone(result.review_trace)
        self.assertIsNone(result.debug_bundle)
        self.assertEqual(state, original)

    def test_opt_in_retains_full_program_validation_attempts_and_ledger(self):
        agent, state, expected_trace = _fixture()
        original = deepcopy(state)
        for review, debug in ((False, False), (True, False), (False, True), (True, True)):
            with self.subTest(review=review, debug=debug):
                result = agent.run("return the difference", include_review_trace=review,
                                   include_debug_bundle=debug)
                self.assert_public_answer(result.agent_answer,
                                          original["final_result"]["agent_answer"], expected_trace)
                if review:
                    self.assertEqual(result.review_trace, {
                        **original["final_result"]["review_trace"], **original["ledger"],
                    })
                else:
                    self.assertIsNone(result.review_trace)
                if debug:
                    self.assertEqual(result.debug_bundle["compiler_attempts"],
                                     original["compilation"]["compiler_attempts"])
                else:
                    self.assertIsNone(result.debug_bundle)
                self.assertEqual(state, original)

    def test_http_uses_caller_projection_with_all_review_debug_options(self):
        agent, state, expected_trace = _fixture()
        original = deepcopy(state)
        services, _, _ = _services(agent=agent)
        with _client(services) as client:
            for review, debug in ((False, False), (True, False), (False, True), (True, True)):
                with self.subTest(review=review, debug=debug):
                    response = client.post("/api/query", json={
                        "question": "return the difference", "include_review_trace": review,
                        "include_debug_bundle": debug,
                    })
                    self.assertEqual(response.status_code, 200)
                    payload = response.json()
                    self.assertEqual(payload["resolved_calculation_trace"], expected_trace)
                    self.assertEqual(payload["structured_result"]["resolved_calculation_trace"],
                                     expected_trace)
                    self.assertEqual(payload["answer"], original["final_result"]["agent_answer"]["answer"])
                    self.assertEqual(payload["citations"], ["s1", "s2"])
                    self.assertEqual("review_trace" in payload, review)
                    self.assertEqual("debug_bundle" in payload, debug)
                    if review:
                        self.assertEqual(payload["review_trace"], {
                            **original["final_result"]["review_trace"], **original["ledger"],
                        })
                    if debug:
                        self.assertEqual(payload["debug_bundle"]["compiler_attempts"],
                                         original["compilation"]["compiler_attempts"])
        self.assertEqual(state, original)


if __name__ == "__main__":
    unittest.main()
