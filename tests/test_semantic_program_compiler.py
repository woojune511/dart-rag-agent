from __future__ import annotations

from tests.semantic_program_test_support import *


class SemanticCalculationProgramCompilerTests(unittest.TestCase):
    def test_models_accept_open_obligations_and_restricted_program(self) -> None:
        planned = RequirementPlannerOutput.model_validate(
            {
                "topic": "opening and closing quantities",
                "obligations": [
                    {
                        "obligation_id": "growth",
                        "kind": "derived_value",
                        "label": "change rate",
                        "display_unit": "%",
                        "scope": {
                            "period": "2024",
                            "consolidation_scope": "consolidated",
                            "segment": "service",
                            "basis": "gross",
                        },
                        "evidence_requirements": [
                            {
                                "requirement_id": "current",
                                "label": "current quantity",
                                "scope": {"period": "2024"},
                            },
                            {
                                "requirement_id": "prior",
                                "label": "prior quantity",
                                "scope": {"period": "2023"},
                            },
                        ],
                    }
                ],
                "retrieval_queries": ["opening quantity", "closing quantity"],
            }
        )
        program = SemanticCalculationProgram.model_validate(
            {
                "status": "ready",
                "direct_bindings": [
                    {
                        "obligation_id": "ob_direct",
                        "candidate_id": "cand-direct",
                        "compatibility_candidate_ids": ["cand-scope-note"],
                    }
                ],
                "expressions": [
                    {
                        "obligation_id": "ob_001",
                        "variable_bindings": [
                            {
                                "variable": "CURR",
                                "source_id": "cand-current",
                                "source_requirement_id": "ob_001:req_001",
                                "scope_applicability_fields": ["segment"],
                            },
                            {
                                "variable": "PREV",
                                "source_id": "cand-prior",
                                "source_requirement_id": "ob_001:req_002",
                            },
                        ],
                        "formula": "((CURR - PREV) / PREV) * 100",
                        "result_unit": "%",
                    }
                ],
                "narrative_bindings": [
                    {
                        "obligation_id": "ob_note",
                        "candidate_ids": ["cand-note"],
                        "scope_applicability_fields": [
                            "consolidation_scope",
                            "segment",
                        ],
                        "text": "The selected evidence directly states the relationship.",
                    }
                ],
            }
        )
        self.assertEqual(planned.obligations[0].kind, "derived_value")
        self.assertEqual(
            planned.obligations[0].evidence_requirements[1].scope.period,
            "2023",
        )
        self.assertEqual(
            program.direct_bindings[0].compatibility_candidate_ids,
            ["cand-scope-note"],
        )
        self.assertEqual(
            program.narrative_bindings[0].scope_applicability_fields,
            ["consolidation_scope", "segment"],
        )
        self.assertEqual(
            program.expressions[0].variable_bindings[0].scope_applicability_fields,
            ["segment"],
        )
        self.assertEqual(program.expressions[0].formula, "((CURR - PREV) / PREV) * 100")

    def test_program_prompt_excludes_parent_row_context_for_structured_cell(self) -> None:
        candidate = {
            **_candidate("late-context", 10),
            "source_text": (
                "unrelated prefix " * 80
                + "requested semantic context appears beside the source value "
                + "unrelated suffix " * 40
            ),
        }
        row = FinancialAgent._semantic_program_prompt_rows([candidate])[0]
        self.assertNotIn("requested semantic context", row["source_text"])
        self.assertIn("quantity", row["source_text"])
        self.assertIn("10", row["source_text"])
        self.assertLessEqual(len(row["source_text"]), 420)

    def test_targeted_retry_merge_preserves_valid_output_bytes(self) -> None:
        preserved = {
            "obligation_id": "ob_valid",
            "candidate_id": "cand-valid",
            "compatibility_candidate_ids": [],
            "resolved_subject": "target",
            "subject_source": "candidate_row_identity",
            "subject_source_row_ids": ["row-valid"],
        }
        before = json.dumps(
            preserved,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        merged = _merge_targeted_program_retry(
            previous_validation={
                "valid_direct_bindings": [preserved],
                "valid_expressions": [],
                "valid_narrative_bindings": [],
            },
            retry_program={
                "status": "ready",
                "direct_bindings": [
                    {
                        "obligation_id": "ob_retry",
                        "candidate_id": "cand-promoted",
                    }
                ],
            },
            target_obligation_ids=["ob_retry"],
        )
        after = json.dumps(
            merged["direct_bindings"][0],
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        self.assertEqual(after, before)

    def test_source_defined_mode_is_explicit_in_schema_and_prompts(self) -> None:
        mode = AnswerObligation.model_json_schema()["properties"]["evidence_mode"]
        self.assertEqual(mode["enum"], ["declared_inputs", "source_defined_group"])
        self.assertEqual(mode["default"], "declared_inputs")
        planner = PLANNING_POLICY["requirement_planner_prompt_template"]
        compiler = CALCULATION_PROMPT_POLICY["semantic_program_prompt_template"]
        self.assertIn("evidence_mode를 source_defined_group", planner)
        self.assertIn("evidence_requirements는 비워", planner)
        self.assertIn("같은 질문·회사·보고서에 속한다는 이유만으로 묶지", planner)
        self.assertIn("evidence_mode가 source_defined_group", compiler)
        self.assertIn("구조화된 표의 숫자 셀", compiler)
        self.assertIn("원문에 기재된 항목 이름과 값을 보존", compiler)
        self.assertIn("호환성을 명시하는 narrative candidate ID", compiler)

    def test_semantic_prompts_require_relation_grounded_narrative_evidence(self) -> None:
        planner_prompt = str(
            PLANNING_POLICY.get("requirement_planner_prompt_template") or ""
        )
        compiler_prompt = str(
            CALCULATION_PROMPT_POLICY.get("semantic_program_prompt_template") or ""
        )

        self.assertIn("narrative obligation", planner_prompt)
        self.assertIn("evidence_requirements", planner_prompt)
        self.assertIn("source schema", planner_prompt)
        self.assertIn("표준 항목을 추정", planner_prompt)
        self.assertIn("인과", compiler_prompt)
        self.assertIn("직접 연결", compiler_prompt)
        self.assertIn("일반적 맥락", compiler_prompt)
        self.assertIn("required evidence_requirements", compiler_prompt)
        self.assertIn("variable binding의 scope_applicability_fields", compiler_prompt)

    def test_cagr_and_time_series_outputs_share_the_restricted_program(self) -> None:
        obligations = [
            _obligation("start", "direct_value", "start", scope=_scope(period="2021")),
            _obligation("end", "direct_value", "end", scope=_scope(period="2024")),
            _obligation("cagr", "derived_value", "three-year CAGR", display_unit="%"),
            _obligation(
                "change_1",
                "derived_value",
                "first interval",
                display_unit="%",
                evidence_requirements=[
                    _requirement("change_1:req_start", "start", period="2021"),
                    _requirement("change_1:req_mid", "mid", period="2022"),
                ],
            ),
            _obligation(
                "change_2",
                "derived_value",
                "second interval",
                display_unit="%",
                evidence_requirements=[
                    _requirement("change_2:req_mid", "mid", period="2022"),
                    _requirement("change_2:req_next", "next", period="2023"),
                ],
            ),
        ]
        candidates = [
            _candidate("c_start", 100, period="2021"),
            _candidate("c_mid", 110, period="2022"),
            _candidate("c_next", 121, period="2023"),
            _candidate("c_end", 133.1, period="2024"),
        ]
        program = {
            "status": "ready",
            "direct_bindings": [
                {"obligation_id": "start", "candidate_id": "c_start"},
                {"obligation_id": "end", "candidate_id": "c_end"},
            ],
            "expressions": [
                {
                    "obligation_id": "cagr",
                    "variable_bindings": [
                        {"variable": "START", "source_id": "start"},
                        {"variable": "END", "source_id": "end"},
                    ],
                    "formula": "((END / START) ** (1 / 3) - 1) * 100",
                    "result_unit": "%",
                    "constants": [{"value": 3, "origin": "query", "source_text": "3 years"}],
                },
                {
                    "obligation_id": "change_1",
                    "variable_bindings": [
                        _binding("PREV", "c_start", "change_1:req_start"),
                        _binding("CURR", "c_mid", "change_1:req_mid"),
                    ],
                    "formula": "((CURR - PREV) / PREV) * 100",
                    "result_unit": "%",
                },
                {
                    "obligation_id": "change_2",
                    "variable_bindings": [
                        _binding("PREV", "c_mid", "change_2:req_mid"),
                        _binding("CURR", "c_next", "change_2:req_next"),
                    ],
                    "formula": "((CURR - PREV) / PREV) * 100",
                    "result_unit": "%",
                },
            ],
        }
        result = execute_semantic_calculation_program(
            program=program,
            obligations=obligations,
            candidate_catalog=candidates,
            query="Return the CAGR over 3 years and the interval changes.",
        )
        self.assertEqual(result["status"], "ok")
        outputs = result["outputs_by_obligation"]
        self.assertAlmostEqual(outputs["cagr"]["normalized_value"], 10.0, places=8)
        self.assertAlmostEqual(outputs["change_1"]["normalized_value"], 10.0, places=8)
        self.assertAlmostEqual(outputs["change_2"]["normalized_value"], 10.0, places=8)


if __name__ == "__main__":
    unittest.main()
