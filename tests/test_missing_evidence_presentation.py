"""A withheld answer may describe request/selection facts, never hidden rationale."""
from copy import deepcopy
from types import SimpleNamespace
import unittest

from src.agent.financial_calculation_execution import (
    assemble_semantic_execution_result, execute_semantic_calculation_program,
)
from src.agent.financial_graph import FinancialAgent
from tests.semantic_program_test_support import _candidate, _obligation, _scope


class MissingEvidencePresentationTests(unittest.TestCase):
    def setUp(self):
        self.query = "선택한 자료로 요청 수량을 알려 줘."
        self.owners = [_obligation("missing", "direct_value", "요청 수량",
            scope=_scope(period="2041-01-01부터 2041-12-31까지"))]
        self.selection = {"company": "Example", "year": 2040, "report_type": "연간 자료", "rcept_no": "doc-one"}
        self.program = {"status": "incomplete", "missing_obligation_ids": ["missing"],
                        "rationale": "PRIVATE DIAGNOSTIC: The complete source says 98765."}

    def execute(self, program=None, owners=None, catalog=()):
        return execute_semantic_calculation_program(program=program or self.program,
            obligations=owners or self.owners, candidate_catalog=catalog, query=self.query)

    def assemble(self, execution=None, owners=None, selection=None, query=None):
        return assemble_semantic_execution_result(execution=execution or self.execute(),
            obligations=owners or self.owners, calculation_plan={}, query=query or self.query,
            report_scope=self.selection if selection is None else selection)

    def test_selected_report_and_requested_period_remain_distinct(self):
        execution = self.execute()
        original = deepcopy((execution, self.owners, self.selection))
        result = self.assemble(execution)
        answer = result["answer"]
        self.assertIn("Example / 보고서 연도: 2040 / 연간 자료", answer)
        self.assertIn("요청 기간: 2041-01-01부터 2041-12-31까지", answer)
        self.assertIn("조회된 근거만으로는", answer)
        self.assertIn("자료 전체에 해당 정보가 없다는 뜻은 아닙니다", answer)
        self.assertNotIn("PRIVATE", answer)
        self.assertNotIn("98765", answer)
        self.assertEqual(result["structured_result"]["status"], "incomplete")
        self.assertEqual(result["structured_result"]["missing_obligation_ids"], ["missing"])
        self.assertEqual(result["resolved_calculation_trace"]["calculation_result"]["answer_slots"], {})
        self.assertEqual((execution, self.owners, self.selection), original)

    def test_same_year_and_non_calendar_period_use_identical_bounded_contract(self):
        for period in ("2040", "requested quarter", ""):
            with self.subTest(period=period):
                owners = [_obligation("missing", "narrative", "설명 요청", scope=_scope(period=period))]
                result = self.assemble(execution=self.execute(owners=owners), owners=owners)
                self.assertIn("조회된 근거만으로는", result["answer"])
                if period:
                    self.assertIn("요청 기간: " + period, result["answer"])
                else:
                    self.assertNotIn("요청 기간", result["answer"])

    def test_unscoped_answer_does_not_invent_a_selected_report(self):
        answer = self.assemble(selection={})["answer"]
        self.assertNotIn("선택한 자료", answer)
        self.assertNotIn("보고서 연도", answer)
        self.assertIn("2041-01-01", answer)

    def test_inventory_selection_never_claims_only_top_level_report_was_used(self):
        for key in ("source_reports", "report_inventory", "source_receipts", "source_companies"):
            with self.subTest(key=key):
                scope = {**self.selection, key: [{"year": 2042}] if "reports" in key or key == "report_inventory" else ["other"]}
                answer = self.assemble(selection=scope)["answer"]
                self.assertIn("선택한 자료에서 조회된 근거", answer)
                self.assertNotIn("보고서 연도: 2040", answer)
                self.assertNotIn("Example", answer)

    def test_english_answer_preserves_exact_declared_period(self):
        result = self.assemble(query="Read the requested quantity.")
        self.assertIn("report year: 2040", result["answer"])
        self.assertIn("requested period: 2041-01-01부터 2041-12-31까지", result["answer"])
        self.assertIn("does not establish", result["answer"])

    def test_contract_failure_is_not_explained_as_a_source_gap(self):
        program = {**self.program, "failed_obligation_ids": ["missing"]}
        execution = self.execute(program=program)
        self.assertTrue(execution["validation"]["errors"])
        answer = self.assemble(execution)["answer"]
        self.assertNotIn("자료 전체", answer)
        self.assertNotIn("선택한 자료 범위", answer)

    def test_execution_error_and_ambiguous_choice_do_not_acquire_missing_evidence_explanation(self):
        execution = self.execute()
        execution["execution_errors"] = [{"code": "arithmetic_failed"}]
        self.assertNotIn("자료 전체", self.assemble(execution)["answer"])
        ambiguous = self.execute(program={"status": "ambiguous", "ambiguous_obligation_ids": ["missing"]})
        self.assertNotIn("자료 전체", self.assemble(ambiguous)["answer"])

    def test_partial_answer_preserves_accepted_value_and_original_execution(self):
        owners = [_obligation("accepted", "direct_value", "known quantity"), *self.owners]
        program = {**self.program, "direct_bindings": [{"obligation_id": "accepted", "candidate_id": "known"}]}
        execution = self.execute(program=program, owners=owners, catalog=[_candidate("known", 17)])
        before = deepcopy(execution)
        result = self.assemble(execution, owners=owners)
        self.assertEqual(result["structured_result"]["status"], "partial")
        self.assertEqual(result["structured_result"]["subtask_results"][0]["calculation_result"]["result_value"], 17)
        self.assertIn("요청 기간: 2041-01-01", result["answer"])
        self.assertEqual(execution, before)

    def test_complete_answer_is_byte_identical_with_or_without_selection(self):
        owners = [_obligation("accepted", "direct_value", "known quantity")]
        execution = self.execute(program={"status": "ready", "direct_bindings": [
            {"obligation_id": "accepted", "candidate_id": "known"}]}, owners=owners, catalog=[_candidate("known", 17)])
        self.assertEqual(self.assemble(execution, owners=owners), self.assemble(execution, owners=owners, selection={}))

    def test_retrieval_only_citations_do_not_support_missing_outputs(self):
        agent = object.__new__(FinancialAgent)
        docs = [(SimpleNamespace(metadata={"company": "Other", "year": 2042, "section_path": "other"}), 0.8)]
        state = {"retrieved_docs": docs, "evidence_items": [],
                 "structured_result": {"status": "incomplete", "missing_obligation_ids": ["missing"]}}
        before = deepcopy(state)
        self.assertEqual(agent._format_citations(state)["citations"], [])
        state["structured_result"]["status"] = "partial"
        state["evidence_items"] = [{"evidence_id": "accepted", "source_anchor": "Accepted source"}]
        self.assertEqual(agent._format_citations(state)["citations"], ["Accepted source"])
        self.assertEqual(state["retrieved_docs"], before["retrieved_docs"])
        state["structured_result"] = {"status": "ok", "missing_obligation_ids": []}
        self.assertEqual(len(agent._format_citations(state)["citations"]), 2)

    def test_final_answer_trace_and_ledger_share_the_explanation(self):
        execution = self.execute()
        agent = object.__new__(FinancialAgent)
        state = {
            "request": {"query": self.query, "report_scope": self.selection},
            "routing": {"query_type": "qa", "companies": ["Example"], "years": [2040]},
            "requirements": {"answer_obligations": self.owners, "semantic_plan": {"answer_obligations": self.owners}},
            "retrieval": {"retrieved_docs": [], "seed_retrieved_docs": []},
            "compilation": {"semantic_program": self.program, "semantic_program_validation": execution["validation"]},
            "numeric_result": {"execution": execution, "calculation_plan": {"operation": "semantic_program"}, "evidence_items": []},
        }
        before = deepcopy(state)
        state.update(agent._assemble_final_phase(state))
        state.update(agent._assemble_ledger_phase(state))
        answer = state["final_result"]["agent_answer"]
        self.assertIn("보고서 연도: 2040", answer["answer"])
        self.assertEqual(answer["answer"], answer["structured_result"]["answer"])
        self.assertEqual(answer["answer"], answer["resolved_calculation_trace"]["calculation_result"]["formatted_result"])
        aggregate = next(a for a in state["ledger"]["artifacts"] if a["kind"] == "aggregated_answer")
        self.assertEqual(aggregate["payload"]["final_answer"], answer["answer"])
        self.assertEqual(state["ledger"]["task_artifact_trace"]["integrity_status"], "ok")
        self.assertEqual({k: state[k] for k in before}, before)


if __name__ == "__main__":
    unittest.main()
