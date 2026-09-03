from __future__ import annotations

from tests.semantic_program_test_support import *


class SemanticCalculationProgramIntegrationTests(unittest.TestCase):
    def _agent(self, llm):
        agent = object.__new__(FinancialAgent)
        agent.llm = llm
        agent.llm_routes = {}
        agent.llm_usage_callback = None
        return agent

    def test_source_defined_summary_survives_planning_compilation_and_execution(self) -> None:
        planner_response = RequirementPlannerOutput.model_validate(
            {
                "topic": "target unit profile",
                "obligations": [
                    {
                        "kind": "direct_value", "label": "target unit capacity",
                        "scope": {"segment": "target unit"},
                    },
                    {
                        "kind": "direct_value", "label": "target unit allocation share",
                        "scope": {"segment": "target unit"},
                    },
                    {
                        "kind": "narrative", "label": "target unit activity summary",
                        "scope": {"segment": "target unit"},
                        "evidence_mode": "source_defined_group",
                        "retrieval_hints": ["target unit activity summary"],
                    },
                ],
            }
        )
        summary_text = "The target unit reports active items 41 and total items 57."
        compiler_responses = [
            SemanticCalculationProgram.model_validate(
                {
                    "direct_bindings": [
                        {
                            "obligation_id": "ob_001",
                            "candidate_id": "cand-capacity",
                        }
                    ]
                }
            ),
            SemanticCalculationProgram.model_validate(
                {
                    "direct_bindings": [
                        {
                            "obligation_id": "ob_002",
                            "candidate_id": "cand-share",
                        }
                    ]
                }
            ),
            SemanticCalculationProgram.model_validate(
                {
                    "narrative_bindings": [
                        {
                            "obligation_id": "ob_003",
                            "candidate_ids": ["cand-summary"],
                            "evidence_bindings": [
                                {
                                    "candidate_id": "cand-summary",
                                    "source_requirement_id": "ob_003:req_001",
                                }
                            ],
                            "text": summary_text,
                        }
                    ]
                }
            ),
        ]
        llm = _StructuredQueueLLM(planner_response, *compiler_responses)
        agent = self._agent(llm)
        initial_state = {
            "query": "Return the target unit's capacity, allocation share, and source-defined activity summary.",
            "query_type": "numeric_fact", "intent": "numeric_fact",
            "format_preference": "mixed", "topic": "target unit profile",
            "report_scope": {"company": "sample", "year": 2024},
            "companies": [], "years": [], "tasks": [], "artifacts": [],
            "plan_loop_count": 0,
        }
        planned = agent._plan_answer_obligation_program(initial_state)
        self.assertEqual(len(planned["calc_subtasks"]), 1)
        obligations = planned["answer_obligations"]
        self.assertEqual([item["coupling_key"] for item in obligations], ["", "", ""])
        summary = obligations[2]
        self.assertEqual(summary["evidence_mode"], "source_defined_group")
        self.assertEqual(len(summary["evidence_requirements"]), 1)
        requirement = summary["evidence_requirements"][0]
        self.assertEqual(requirement["requirement_id"], "ob_003:req_001")
        self.assertEqual(requirement["label"], summary["label"])
        self.assertEqual(requirement["scope"], summary["scope"])
        self.assertEqual(AnswerObligation.model_validate(summary).model_dump(), summary)
        task = planned["calc_subtasks"][0]
        self.assertEqual(
            [item["role"] for item in task["required_evidence"]],
            ["ob_001", "ob_002", "ob_003:req_001"],
        )
        self.assertEqual(task["required_evidence"][2]["label"], summary["label"])
        catalog = [
            {
                **_candidate(
                    "cand-capacity", 84, row_label="target unit",
                    context="capacity-table", period="2024",
                ),
                "company": "sample",
            },
            {
                **_candidate(
                    "cand-share", 13.2, raw_unit="%", normalized_unit="PERCENT",
                    row_label="target unit", context="allocation-table", period="2024",
                ),
                "company": "sample",
            },
            {
                **_candidate("cand-summary", 0, context="activity-table"),
                "company": "sample", "kind": "narrative",
                "normalized_value": None, "source_text": summary_text,
            },
        ]
        state = {
            **initial_state, **planned, "active_subtask": task,
            "evidence_items": [], "retrieved_docs": [], "seed_retrieved_docs": [],
            "planner_debug_trace": {}, "resolved_calculation_trace": {},
        }
        with patch.object(agent, "_semantic_candidate_catalog_for_state", return_value=catalog):
            compiled = agent._compile_semantic_calculation_program(state)
        self.assertEqual(compiled["semantic_program_retry_count"], 0)
        self.assertEqual(
            llm.models,
            ["RequirementPlannerOutput", *["SemanticCalculationProgram"] * 3],
        )
        self.assertEqual(len(llm.prompts), 4)
        self.assertIn('"evidence_mode": "source_defined_group"', str(llm.prompts[3]))
        self.assertIn('"requirement_id": "ob_003:req_001"', str(llm.prompts[3]))
        compile_validation_bytes = json.dumps(
            compiled["semantic_program_validation"],
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        executed = agent._execute_semantic_calculation_program({**state, **compiled})
        self.assertNotIn("semantic_program_validation", executed)
        self.assertEqual(
            json.dumps(
                compiled["semantic_program_validation"],
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8"),
            compile_validation_bytes,
        )
        self.assertEqual(executed["structured_result"]["status"], "ok")
        self.assertIn(summary_text, executed["answer"])
        trace = executed["resolved_calculation_trace"]
        self.assertEqual(trace["calculation_result"]["semantic_status"], "ok")
        self.assertEqual(trace["calculation_result"]["derived_metrics"]["missing_obligation_ids"], [])
        self.assertEqual(len(trace["calculation_result"]["outputs"]), 3)
        self.assertEqual(
            trace["calculation_plan"]["answer_obligations"][2]["evidence_mode"],
            "source_defined_group",
        )

    def test_requirement_planner_emits_one_program_task_and_stable_obligations(self) -> None:
        response = RequirementPlannerOutput.model_validate(
            {
                "companies": [],
                "years": [2024],
                "topic": "quantity movement and context",
                "obligations": [
                    {
                        "obligation_id": "closing",
                        "kind": "direct_value",
                        "label": "closing quantity",
                        "scope": {"period": "2024"},
                        "retrieval_hints": ["closing quantity"],
                    },
                    {
                        "obligation_id": "change",
                        "kind": "derived_value",
                        "label": "change rate",
                        "display_unit": "%",
                        "scope": {
                            "period": "2024",
                            "consolidation_scope": "consolidated",
                            "segment": "service",
                            "basis": "gross",
                        },
                        "depends_on": ["closing"],
                        "retrieval_hints": ["opening quantity", "closing quantity"],
                        "evidence_requirements": [
                            {
                                "requirement_id": "opening-input",
                                "label": "opening quantity",
                                "scope": {"period": "2023"},
                                "retrieval_hints": ["opening quantity"],
                            }
                        ],
                    },
                    {
                        "obligation_id": "context",
                        "kind": "narrative",
                        "label": "context",
                        "evidence_requirements": [
                            {
                                "requirement_id": "context-relation",
                                "label": "reported change explanation",
                                "retrieval_hints": ["reported change explanation"],
                            }
                        ],
                    },
                ],
                "retrieval_queries": ["quantity table", "quantity context"],
            }
        )
        llm = _StructuredQueueLLM(response)
        agent = self._agent(llm)
        result = agent._plan_answer_obligation_program(
            {
                "query": "Return the closing quantity, its change rate, and explain the context.",
                "query_type": "comparison",
                "intent": "comparison",
                "topic": "quantity movement",
                "report_scope": {"year": 2024},
                "companies": [],
                "years": [2024],
                "tasks": [],
                "artifacts": [],
                "plan_loop_count": 0,
            }
        )
        self.assertEqual(llm.models, ["RequirementPlannerOutput"])
        self.assertEqual(result["planned_metric_families"], ["semantic_program"])
        self.assertEqual(len(result["calc_subtasks"]), 1)
        task = result["calc_subtasks"][0]
        self.assertNotIn("operation_family", task)
        self.assertEqual(len(task["required_evidence"]), 3)
        self.assertEqual(
            [item["obligation_id"] for item in result["answer_obligations"]],
            ["ob_001", "ob_002", "ob_003"],
        )
        self.assertEqual(result["answer_obligations"][1]["depends_on"], ["ob_001"])
        self.assertEqual(
            result["answer_obligations"][1]["evidence_requirements"][0][
                "requirement_id"
            ],
            "ob_002:req_001",
        )
        self.assertEqual(
            result["answer_obligations"][1]["evidence_requirements"][0]["scope"][
                "period"
            ],
            "2023",
        )
        self.assertEqual(
            result["answer_obligations"][1]["evidence_requirements"][0]["scope"],
            {
                "company": "",
                "period": "2023",
                "consolidation_scope": "unknown",
                "segment": "service",
                "basis": "gross",
            },
        )
        self.assertEqual(
            result["answer_obligations"][1]["scope"]["consolidation_scope"],
            "unknown",
        )
        self.assertEqual(
            task["constraints"]["consolidation_scope"],
            "unknown",
        )
        self.assertEqual(
            [item["role"] for item in task["required_evidence"]],
            ["ob_001", "ob_002:req_001", "ob_003:req_001"],
        )
        self.assertTrue(result["semantic_plan"]["program_required"])

    def test_mixed_format_uses_requirement_program_even_when_router_intent_is_narrative(self) -> None:
        response = RequirementPlannerOutput.model_validate(
            {
                "obligations": [
                    {
                        "obligation_id": "value",
                        "kind": "direct_value",
                        "label": "reported value",
                    },
                    {
                        "obligation_id": "context",
                        "kind": "narrative",
                        "label": "reported context",
                    },
                ]
            }
        )
        llm = _StructuredQueueLLM(response)
        agent = self._agent(llm)

        result = agent._plan_answer_obligation_program(
            {
                "query": "Return the value and explain its context.",
                "query_type": "risk",
                "intent": "risk",
                "format_preference": "mixed",
                "topic": "value and context",
                "report_scope": {},
                "companies": [],
                "years": [],
                "tasks": [],
                "artifacts": [],
                "plan_loop_count": 0,
            }
        )

        self.assertEqual(llm.models, ["RequirementPlannerOutput"])
        self.assertTrue(result["semantic_plan"]["program_required"])
        self.assertEqual(len(result["answer_obligations"]), 2)

    def test_requirement_planner_bounds_runaway_coupling_key(self) -> None:
        oversized = "shared-context-" * 1000
        response = RequirementPlannerOutput.model_validate(
            {
                "obligations": [
                    {
                        "obligation_id": "value",
                        "kind": "direct_value",
                        "label": "reported value",
                        "coupling_key": oversized,
                    }
                ]
            }
        )

        self.assertLessEqual(len(response.obligations[0].coupling_key), 128)
        self.assertNotEqual(response.obligations[0].coupling_key, oversized)

    def test_requirement_planner_uses_authoritative_company_and_removes_scope_placeholders(self) -> None:
        response = RequirementPlannerOutput.model_validate(
            {
                "obligations": [
                    {
                        "obligation_id": "value",
                        "kind": "direct_value",
                        "label": "reported value",
                        "scope": {
                            "company": "alternate spelling",
                            "period": "2024",
                            "segment": "report_scope",
                            "basis": "report_scope",
                        },
                    }
                ]
            }
        )
        agent = self._agent(_StructuredQueueLLM(response))
        result = agent._build_llm_requirement_plan(
            query="Return the 2024 reported value.",
            topic="reported value",
            intent="numeric_fact",
            report_scope={"company": "Canonical Company", "year": 2024},
        )
        scope = result["answer_obligations"][0]["scope"]
        self.assertEqual(scope["company"], "Canonical Company")
        self.assertEqual(scope["period"], "2024")
        self.assertEqual(scope["segment"], "")
        self.assertEqual(scope["basis"], "")

    def test_requirement_planner_preserves_typed_local_target_and_known_concepts(self) -> None:
        response = RequirementPlannerOutput.model_validate(
            {
                "obligations": [
                    {
                        "obligation_id": "amount",
                        "kind": "direct_value",
                        "label": "Motional investment carrying amount",
                        "semantic_target": {
                            "local_subjects": ["Motional", "Motional"],
                            "concept_keys": [
                                "investment_carrying_amount",
                                "invented_concept",
                            ],
                            "metric_surfaces": ["investment carrying amount"],
                        },
                    }
                ]
            }
        )
        result = self._agent(_StructuredQueueLLM(response))._build_llm_requirement_plan(
            query="Return Motional's investment carrying amount.",
            topic="investment carrying amount",
            intent="numeric_fact",
            report_scope={"company": "Filing Company", "year": 2024},
        )

        target = result["answer_obligations"][0]["semantic_target"]
        self.assertEqual(target["local_subjects"], ["Motional"])
        self.assertEqual(target["concept_keys"], ["investment_carrying_amount"])
        self.assertEqual(target["metric_surfaces"], ["investment carrying amount"])
        self.assertIn(
            "unknown_semantic_target_concept:invented_concept",
            result["planner_notes"],
        )

    def test_requirement_planner_uses_source_report_company_for_candidate_identity(self) -> None:
        response = RequirementPlannerOutput.model_validate(
            {
                "obligations": [
                    {
                        "obligation_id": "value",
                        "kind": "direct_value",
                        "label": "reported value",
                        "scope": {"company": "display spelling", "period": "2024"},
                    }
                ]
            }
        )
        agent = self._agent(_StructuredQueueLLM(response))
        result = agent._build_llm_requirement_plan(
            query="Return the 2024 reported value.",
            topic="reported value",
            intent="numeric_fact",
            report_scope={
                "company": "Display Company",
                "year": 2024,
                "source_reports": [
                    {"corp_name": "Source Company", "year": 2024, "rcept_no": "receipt-1"}
                ],
            },
        )
        self.assertEqual(
            result["answer_obligations"][0]["scope"]["company"],
            "Source Company",
        )
        self.assertEqual(result["companies"][:2], ["Source Company", "Display Company"])

    def test_requirement_planner_rejects_hard_scope_without_query_provenance(self) -> None:
        fixture = _contract_residual_fixture()["scope_provenance"][
            "implicit_query"
        ]
        response = RequirementPlannerOutput.model_validate(
            {"obligations": fixture["planner_obligations"]}
        )
        agent = self._agent(_StructuredQueueLLM(response))

        result = agent._build_llm_requirement_plan(
            query=fixture["query"],
            topic="target venture results",
            intent="numeric_fact",
            report_scope=fixture["report_scope"],
        )

        self.assertEqual(
            [
                item["scope"]["consolidation_scope"]
                for item in result["answer_obligations"]
            ],
            fixture["expected_obligation_scopes"],
        )
        self.assertEqual(
            result["answer_obligations"][1]["evidence_requirements"][0][
                "scope"
            ]["consolidation_scope"],
            fixture["expected_requirement_scope"],
        )
        self.assertEqual(
            result["tasks"][0]["constraints"]["consolidation_scope"],
            fixture["expected_task_scope"],
        )
        self.assertIn(
            "report_scope의 문서 metadata",
            str(PLANNING_POLICY.get("requirement_planner_prompt_template") or ""),
        )

    def test_requirement_planner_uses_only_query_explicit_hard_scope(self) -> None:
        fixture = _contract_residual_fixture()["scope_provenance"]
        single = fixture["single_explicit_query"]
        single_response = RequirementPlannerOutput.model_validate(
            {
                "obligations": [
                    {
                        "obligation_id": "share",
                        "kind": "direct_value",
                        "label": "target venture ownership share",
                        "scope": {
                            "period": "2024",
                            "consolidation_scope": single["planner_scope"],
                            "segment": "target venture",
                        },
                        "evidence_requirements": [
                            {
                                "requirement_id": "share-input",
                                "label": "target venture reported share",
                                "scope": {
                                    "period": "2024",
                                    "consolidation_scope": "unknown",
                                    "segment": "target venture",
                                },
                            }
                        ],
                    }
                ]
            }
        )
        single_result = self._agent(
            _StructuredQueueLLM(single_response)
        )._build_llm_requirement_plan(
            query=single["query"],
            topic="target venture ownership share",
            intent="numeric_fact",
            report_scope=single["report_scope"],
        )
        self.assertEqual(
            single_result["answer_obligations"][0]["scope"][
                "consolidation_scope"
            ],
            single["expected_scope"],
        )
        self.assertEqual(
            single_result["answer_obligations"][0][
                "evidence_requirements"
            ][0]["scope"]["consolidation_scope"],
            single["expected_scope"],
        )

        multiple = fixture["multiple_explicit_query"]
        multiple_response = RequirementPlannerOutput.model_validate(
            {
                "obligations": [
                    {
                        "obligation_id": f"share-{index}",
                        "kind": "direct_value",
                        "label": f"target venture ownership share {index}",
                        "scope": {
                            "period": "2024",
                            "consolidation_scope": scope,
                            "segment": "target venture",
                        },
                    }
                    for index, scope in enumerate(
                        multiple["planner_scopes"],
                        start=1,
                    )
                ]
            }
        )
        multiple_result = self._agent(
            _StructuredQueueLLM(multiple_response)
        )._build_llm_requirement_plan(
            query=multiple["query"],
            topic="target venture ownership share",
            intent="numeric_fact",
            report_scope={"year": 2024},
        )
        self.assertEqual(
            [
                item["scope"]["consolidation_scope"]
                for item in multiple_result["answer_obligations"]
            ],
            multiple["expected_scopes"],
        )
        self.assertEqual(
            multiple_result["tasks"][0]["constraints"][
                "consolidation_scope"
            ],
            multiple["expected_task_scope"],
        )

    def test_program_prompt_projection_does_not_apply_a_second_candidate_rank(self) -> None:
        agent = self._agent(_StructuredQueueLLM())
        numeric = [
            {**_candidate(f"numeric-{index}", index + 1), "source_text": "n" * 1000}
            for index in range(110)
        ]
        narrative = [
            {
                **_candidate(f"narrative-{index}", 0),
                "kind": "narrative",
                "normalized_value": None,
                "source_text": "x" * 1000,
            }
            for index in range(40)
        ]
        rows = agent._semantic_program_prompt_rows([*numeric, *narrative])
        self.assertEqual(
            [sum(item["kind"] == kind for item in rows) for kind in ("numeric", "narrative")],
            [110, 40],
        )
        self.assertTrue(
            all(
                len(item["source_text"]) <= (420 if item["kind"] == "numeric" else 600)
                for item in rows
            )
        )

    def test_compiler_and_executor_use_candidate_ids_and_project_canonical_trace(self) -> None:
        source_candidates = [
            {
                "candidate_id": "chunk-1::value:0",
                "source_anchor": "[sample | 2024 | section]",
                "text": "opening and closing quantity",
                "candidate_kind": "structured_value",
                "metadata": {
                    "row_label": "quantity",
                    "table_source_id": "table-a",
                    "year": 2024,
                    "structured_cells": [
                        {"column_headers": ["opening"], "value_text": "343", "unit_hint": "개"},
                        {"column_headers": ["closing"], "value_text": "380", "unit_hint": "개"},
                    ],
                },
            }
        ]
        catalog = build_semantic_candidate_catalog(source_candidates)
        numeric = [item for item in catalog if item["kind"] == "numeric"]
        opening_id, closing_id = [item["candidate_id"] for item in numeric]
        invalid_response = SemanticCalculationProgram.model_validate(
            {
                "status": "ready",
                "expressions": [
                    {
                        "obligation_id": "ob_001",
                        "variable_bindings": [
                            _binding(
                                "CLOSING_VALUE",
                                closing_id,
                                "ob_001:req_closing",
                            ),
                            _binding(
                                "OPENING_VALUE",
                                opening_id,
                                "ob_001:req_opening",
                            ),
                        ],
                        "formula": "((CURR - PREV) / PREV) * 100",
                        "result_unit": "%",
                    }
                ],
            }
        )
        response = SemanticCalculationProgram.model_validate(
            {
                "status": "ready",
                "expressions": [
                    {
                        "obligation_id": "ob_001",
                        "variable_bindings": [
                            _binding("CURR", closing_id, "ob_001:req_closing"),
                            _binding("PREV", opening_id, "ob_001:req_opening"),
                        ],
                        "formula": "((CURR - PREV) / PREV) * 100",
                        "result_unit": "%",
                    }
                ],
            }
        )
        llm = _StructuredQueueLLM(invalid_response, response)
        agent = self._agent(llm)
        obligations = [
            _obligation(
                "ob_001",
                "derived_value",
                "change rate",
                display_unit="%",
                evidence_requirements=[
                    _requirement("ob_001:req_closing", "closing quantity"),
                    _requirement("ob_001:req_opening", "opening quantity"),
                ],
            )
        ]
        state = {
            "query": "What percent did the quantity increase from opening to closing?",
            "query_type": "comparison",
            "intent": "comparison",
            "topic": "quantity",
            "report_scope": {},
            "answer_obligations": obligations,
            "semantic_plan": {"program_required": True, "answer_obligations": obligations},
            "active_subtask": {
                "task_id": "task_1",
                "metric_family": "semantic_program",
                "metric_label": "change rate",
                "query": "What percent did the quantity increase from opening to closing?",
            },
            "tasks": [],
            "artifacts": [],
            "evidence_items": [],
            "retrieved_docs": [],
            "seed_retrieved_docs": [],
            "planner_debug_trace": {},
            "resolved_calculation_trace": {},
        }
        with patch.object(agent, "_semantic_candidate_catalog_for_state", return_value=catalog):
            compiled = agent._compile_semantic_calculation_program(state)
        self.assertEqual(llm.models, ["SemanticCalculationProgram"])
        self.assertIn('"year": 2024', str(llm.prompts[0]))
        self.assertEqual(compiled["semantic_program_retry_count"], 1)
        self.assertEqual(len(llm.prompts), 2)
        retry_prompt = str(llm.prompts[1])
        self.assertIn("allowed_candidate_ids", retry_prompt)
        self.assertIn(opening_id, retry_prompt)
        self.assertIn(closing_id, retry_prompt)
        self.assertIn("declared_evidence_requirement_ids", retry_prompt)
        self.assertIn("ob_001:req_opening", retry_prompt)
        self.assertIn("ob_001:req_closing", retry_prompt)
        self.assertIn("repair_contract", retry_prompt)
        self.assertIn("evidence_requirement_ids_by_obligation", retry_prompt)
        self.assertIn("formula_variable_binding_invariant", retry_prompt)
        self.assertIn("exactly equal", retry_prompt)
        trace = compiled["resolved_calculation_trace"]
        self.assertEqual(trace["calculation_plan"]["program_mode"], "semantic_program")
        self.assertEqual(
            trace["calculation_plan"]["prompt_candidate_strategy"],
            "compilation_islands_v2",
        )
        stage_diagnostics = trace["calculation_plan"]["candidate_stage_diagnostics"]
        self.assertEqual(
            stage_diagnostics["schema"],
            "semantic_candidate_stage_diagnostics_v6",
        )
        self.assertEqual(stage_diagnostics["catalog_candidate_count"], 2)
        self.assertEqual(stage_diagnostics["prompt_candidate_count"], 2)
        self.assertEqual(len(trace["calculation_operands"]), 2)
        merged = {**state, **compiled}
        executed = agent._execute_semantic_calculation_program(merged)
        executed_trace = executed["resolved_calculation_trace"]
        self.assertEqual(executed_trace["calculation_result"]["semantic_status"], "ok")
        self.assertAlmostEqual(executed_trace["calculation_result"]["result_value"], (380 - 343) / 343 * 100)
        self.assertEqual(
            executed_trace["calculation_plan"]["operation_family"],
            "growth_rate",
        )
        self.assertEqual(
            executed_trace["calculation_result"]["operation_family"],
            "growth_rate",
        )
        self.assertEqual(executed["structured_result"]["status"], "ok")
        self.assertEqual(len(executed["structured_result"]["subtask_results"]), 1)
        output_result = executed["structured_result"]["subtask_results"][0][
            "calculation_result"
        ]
        self.assertEqual(output_result["operation_family"], "growth_rate")
        self.assertEqual(output_result["answer_slots"]["operation_family"], "single_value")
        self.assertEqual(
            validate_answer_slots_payload(output_result["answer_slots"])[
                "operation_family"
            ],
            "single_value",
        )
        self.assertIn("change rate", executed["answer"])
        artifact_kinds = [item.get("kind") for item in executed["artifacts"]]
        self.assertIn("operand_set", artifact_kinds)
        self.assertIn("calculation_plan", artifact_kinds)
        self.assertIn("calculation_result", artifact_kinds)

    def test_retry_replaces_rejected_candidate_and_omits_valid_output(self) -> None:
        valid = {
            **_candidate(
                "cand-valid",
                10,
                raw_unit="%",
                normalized_unit="PERCENT",
            ),
            "candidate_kind": "structured_row",
            "row_headers": ["valid output"],
        }
        bad_candidates = [
            {
                **_candidate(
                    f"cand-bad-{index}",
                    20 + index,
                    raw_unit="%",
                    normalized_unit="PERCENT",
                ),
                "candidate_kind": "sentence_value",
                "row_label": "reported share",
                "row_headers": [],
                "local_entity_surfaces": [],
                "source_text": f"A generic note reports {20 + index}%.",
            }
            for index in range(1, 5)
        ]
        promoted = {
            **_candidate(
                "cand-promoted",
                26,
                raw_unit="%",
                normalized_unit="PERCENT",
            ),
            "candidate_kind": "structured_row",
            "row_label": "ownership share",
            "row_headers": ["target entity"],
            "local_entity_surfaces": ["ownership share", "target entity"],
        }
        catalog = [valid, *bad_candidates, promoted]
        obligations = [
            _obligation(
                "ob_valid",
                "direct_value",
                "valid output",
                display_unit="%",
            ),
            _obligation(
                "ob_retry",
                "direct_value",
                "target ownership share",
                display_unit="%",
                scope=_scope(segment="target entity"),
            ),
        ]
        first_program = {
            "status": "ready",
            "direct_bindings": [
                {"obligation_id": "ob_valid", "candidate_id": "cand-valid"},
                {"obligation_id": "ob_retry", "candidate_id": "cand-bad-1"},
            ],
        }
        retry_program = {
            "status": "ready",
            "direct_bindings": [
                {
                    "obligation_id": "ob_retry",
                    "candidate_id": "cand-promoted",
                }
            ],
        }
        first_model = SemanticCalculationProgram.model_validate(first_program)
        accepted_first_island = SemanticCalculationProgram.model_validate(
            {
                "status": "ready",
                "direct_bindings": [
                    {
                        "obligation_id": "ob_valid",
                        "candidate_id": "cand-valid",
                    }
                ],
            }
        )
        llm = _StructuredQueueLLM(
            accepted_first_island,
            SemanticCalculationProgram.model_validate(
                {
                    "status": "ready",
                    "direct_bindings": [
                        {
                            "obligation_id": "ob_retry",
                            "candidate_id": "cand-bad-1",
                        }
                    ],
                }
            ),
            SemanticCalculationProgram.model_validate(retry_program),
        )
        agent = self._agent(llm)
        state = {
            "query": "Return the valid output and the target entity ownership share.",
            "query_type": "multi_metric",
            "intent": "multi_metric",
            "topic": "ownership share",
            "report_scope": {},
            "answer_obligations": obligations,
            "semantic_plan": {
                "program_required": True,
                "answer_obligations": obligations,
            },
            "active_subtask": {
                "task_id": "task_1",
                "metric_family": "semantic_program",
                "metric_label": "two outputs",
                "query": "Return both outputs.",
            },
            "tasks": [],
            "artifacts": [],
            "evidence_items": [],
            "retrieved_docs": [],
            "seed_retrieved_docs": [],
            "planner_debug_trace": {},
            "resolved_calculation_trace": {},
        }
        initial_cohorts = _semantic_candidate_cohorts(catalog, obligations)
        first_validation = validate_semantic_calculation_program(
            program=first_model.model_dump(),
            obligations=obligations,
            candidate_catalog=catalog,
            query=state["query"],
            selectable_candidate_ids_by_owner=initial_cohorts[
                "candidate_ids_by_owner"
            ],
        )
        preserved_before = json.dumps(
            accepted_first_island.model_dump()["direct_bindings"][0],
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")

        with patch.object(
            agent,
            "_semantic_candidate_catalog_for_state",
            return_value=catalog,
        ):
            compiled = agent._compile_semantic_calculation_program(state)

        self.assertEqual(compiled["semantic_program_retry_count"], 1)
        self.assertEqual(len(llm.prompts), 3)
        first_prompt = str(llm.prompts[1])
        retry_prompt = str(llm.prompts[2])
        self.assertNotIn("cand-bad-4", first_prompt)
        self.assertIn("cand-bad-4", retry_prompt)
        self.assertNotIn("cand-bad-1", retry_prompt)
        self.assertNotIn('"obligation_id": "ob_valid"', retry_prompt)
        final_valid = next(
            item
            for item in compiled["semantic_program"]["direct_bindings"]
            if item["obligation_id"] == "ob_valid"
        )
        preserved_after = json.dumps(
            final_valid,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        self.assertEqual(preserved_after, preserved_before)
        attempts = compiled["resolved_calculation_trace"]["calculation_plan"][
            "candidate_stage_diagnostics"
        ]["attempts"]
        attempts = [
            item for item in attempts if item["island_id"] == "island_002"
        ]
        self.assertEqual(len(attempts), 2)
        self.assertNotEqual(
            attempts[1]["visible_candidate_id_fingerprint"],
            attempts[0]["visible_candidate_id_fingerprint"],
        )

    def test_retry_excludes_only_the_candidate_role_that_failed(self) -> None:
        program = {
            "direct_bindings": [
                {
                    "obligation_id": "ob_direct",
                    "candidate_id": "cand-primary",
                    "compatibility_candidate_ids": ["cand-witness"],
                }
            ]
        }

        primary_exclusions = _retry_candidate_exclusions(
            program=program,
            validation_errors=[
                {
                    "code": "candidate_scope_mismatch",
                    "obligation_id": "ob_direct",
                    "detail": "period",
                }
            ],
            target_obligation_ids=["ob_direct"],
        )
        witness_exclusions = _retry_candidate_exclusions(
            program=program,
            validation_errors=[
                {
                    "code": "compatibility_scope_mismatch",
                    "obligation_id": "ob_direct",
                    "detail": "consolidation_scope",
                }
            ],
            target_obligation_ids=["ob_direct"],
        )

        self.assertEqual(primary_exclusions, {"ob_direct": ["cand-primary"]})
        self.assertEqual(witness_exclusions, {"ob_direct": ["cand-witness"]})

    def test_requirement_scope_retry_excludes_only_the_failed_input(self) -> None:
        program = {
            "expressions": [
                {
                    "obligation_id": "ob_mix",
                    "variable_bindings": [
                        _binding("A", "cand-valid", "ob_mix:req_valid"),
                        _binding("B", "cand-rejected", "ob_mix:req_rejected"),
                    ],
                }
            ]
        }

        exclusions = _retry_candidate_exclusions(
            program=program,
            validation_errors=[
                {
                    "code": "candidate_requirement_scope_mismatch",
                    "obligation_id": "ob_mix",
                    "detail": "ob_mix:req_rejected: scope mismatch: period",
                }
            ],
            target_obligation_ids=["ob_mix"],
        )

        self.assertEqual(
            exclusions,
            {"ob_mix:req_rejected": ["cand-rejected"]},
        )

    def test_unknown_narrative_retry_requires_an_exact_rejected_id(self) -> None:
        program = {
            "narrative_bindings": [
                {
                    "obligation_id": "ob_summary",
                    "candidate_ids": ["cand-valid", "cand-unregistered"],
                    "evidence_bindings": [
                        {
                            "candidate_id": "cand-valid",
                            "source_requirement_id": "ob_summary:req_summary",
                        }
                    ],
                }
            ]
        }

        generic_exclusions = _retry_candidate_exclusions(
            program=program,
            validation_errors=[
                {
                    "code": "unknown_narrative_candidate",
                    "obligation_id": "ob_summary",
                    "detail": "",
                }
            ],
            target_obligation_ids=["ob_summary"],
        )
        exact_exclusions = _retry_candidate_exclusions(
            program=program,
            validation_errors=[
                {
                    "code": "unknown_narrative_candidate",
                    "obligation_id": "ob_summary",
                    "detail": "cand-unregistered",
                }
            ],
            target_obligation_ids=["ob_summary"],
        )

        self.assertEqual(generic_exclusions, {})
        self.assertEqual(
            exact_exclusions,
            {"ob_summary": ["cand-unregistered"]},
        )

    def test_retry_keeps_same_cohort_for_context_field_mismatch(self) -> None:
        program = {
            "expressions": [
                {
                    "obligation_id": "ob_mix",
                    "variable_bindings": [
                        _binding("A", "cand-a", "ob_mix:req_a"),
                        _binding("B", "cand-b", "ob_mix:req_b"),
                    ],
                }
            ]
        }

        exclusions = _retry_candidate_exclusions(
            program=program,
            validation_errors=[
                {
                    "code": "expression_context_mismatch",
                    "obligation_id": "ob_mix",
                    "detail": "context_fingerprint",
                }
            ],
            target_obligation_ids=["ob_mix"],
        )

        self.assertEqual(exclusions, {})

    def test_structural_context_retry_reuses_identical_candidate_payload(self) -> None:
        obligations = [
            _obligation(
                "ob_mix",
                "derived_value",
                "same-period difference",
                display_unit="개",
                scope=_scope(period="2024"),
                evidence_requirements=[
                    _requirement("ob_mix:req_a", "first amount", period="2024"),
                    _requirement("ob_mix:req_b", "second amount", period="2024"),
                ],
            )
        ]
        catalog = [
            _candidate(
                "cand-a",
                30,
                raw_unit="개",
                period="2024",
                context="statement-context",
                row_label="first amount",
            ),
            _candidate(
                "cand-b",
                20,
                raw_unit="개",
                period="2024",
                context="note-context",
                row_label="second amount",
            ),
        ]
        first_program = SemanticCalculationProgram.model_validate(
            {
                "status": "ready",
                "expressions": [
                    {
                        "obligation_id": "ob_mix",
                        "variable_bindings": [
                            _binding("A", "cand-a", "ob_mix:req_a"),
                            _binding("B", "cand-b", "ob_mix:req_b"),
                        ],
                        "formula": "A - B",
                        "result_unit": "개",
                    }
                ],
            }
        )
        retry_program = SemanticCalculationProgram.model_validate(
            {
                "status": "ambiguous",
                "ambiguous_obligation_ids": ["ob_mix"],
                "rationale": "The disclosed contexts are not explicitly compatible.",
            }
        )
        llm = _StructuredQueueLLM(first_program, retry_program)
        agent = self._agent(llm)
        state = {
            "query": "Subtract the second amount from the first amount.",
            "query_type": "comparison",
            "intent": "comparison",
            "topic": "same-period difference",
            "report_scope": {},
            "answer_obligations": obligations,
            "semantic_plan": {
                "program_required": True,
                "answer_obligations": obligations,
            },
            "active_subtask": {
                "task_id": "task_1",
                "metric_family": "semantic_program",
                "metric_label": "same-period difference",
                "query": "Subtract the second amount from the first amount.",
            },
            "tasks": [],
            "artifacts": [],
            "evidence_items": [],
            "retrieved_docs": [],
            "seed_retrieved_docs": [],
            "planner_debug_trace": {},
            "resolved_calculation_trace": {},
        }

        with patch.object(
            agent,
            "_semantic_candidate_catalog_for_state",
            return_value=catalog,
        ):
            compiled = agent._compile_semantic_calculation_program(state)

        attempts = compiled["resolved_calculation_trace"]["calculation_plan"][
            "candidate_stage_diagnostics"
        ]["attempts"]
        self.assertEqual(compiled["semantic_program_retry_count"], 1)
        self.assertEqual(len(attempts), 2)
        self.assertEqual(
            attempts[0]["visible_candidate_ids"],
            attempts[1]["visible_candidate_ids"],
        )
        self.assertEqual(
            attempts[0]["visible_candidate_id_fingerprint"],
            attempts[1]["visible_candidate_id_fingerprint"],
        )
        self.assertEqual(
            attempts[0]["serialized_candidate_bytes"],
            attempts[1]["serialized_candidate_bytes"],
        )

    def test_source_and_formula_displays_survive_graph_trace_ledger_and_numeric_evaluation(self) -> None:
        from src.agent.financial_task_artifacts import project_task_artifact_trace
        from src.ops.evaluator import EvalExample, RAGEvaluator

        fixture = _source_display_program_fixture()
        llm = _StructuredQueueLLM(SemanticCalculationProgram.model_validate(fixture["program"]))
        agent = self._agent(llm)
        state = {
            "query": fixture["query"], "query_type": "comparison", "intent": "comparison",
            "topic": "quantity", "format_preference": "table", "report_scope": {},
            "answer_obligations": fixture["obligations"],
            "semantic_plan": {"program_required": True, "answer_obligations": fixture["obligations"]},
            "active_subtask": {
                "task_id": "task_1", "metric_family": "semantic_program",
                "metric_label": "quantity change", "query": fixture["query"],
            },
            "tasks": [], "artifacts": [], "evidence_items": [],
            "retrieved_docs": [], "seed_retrieved_docs": [],
            "planner_debug_trace": {}, "resolved_calculation_trace": {},
        }
        with patch.object(
            agent, "_semantic_candidate_catalog_for_state", return_value=fixture["candidate_catalog"],
        ):
            compiled = agent._compile_semantic_calculation_program(state)
        self.assertEqual(compiled["semantic_program_retry_count"], 0)
        self.assertEqual(llm.models, ["SemanticCalculationProgram"])
        self.assertEqual(len(llm.prompts), 1)
        executed = agent._execute_semantic_calculation_program({**state, **compiled})
        self.assertEqual(executed["structured_result"]["status"], "ok")
        self.assertIn("calculated 10% (source-stated 10.2%)", executed["answer"])
        trace = executed["resolved_calculation_trace"]
        calculation_result = trace["calculation_result"]
        output = calculation_result["outputs"][0]
        self.assertEqual(output["formula_rendered_value"], "10%")
        self.assertEqual(output["source_display_value"], "10.2%")
        self.assertFalse(output["source_display_matches_formula"])
        self.assertEqual(calculation_result["derived_metrics"]["semantic_outputs"], [output])
        self.assertEqual(
            executed["structured_result"]["resolved_calculation_trace"]["calculation_result"]["outputs"],
            [output],
        )
        self.assertEqual(
            validate_answer_slots_payload(calculation_result["answer_slots"])["primary_value"]["normalized_value"],
            10.0,
        )
        self.assertIn("cand-stated", executed["selected_claim_ids"])
        source_evidence = next(item for item in executed["evidence_items"] if item["evidence_id"] == "cand-stated")
        self.assertEqual(source_evidence["raw_value"], "10.2")
        citations = agent._format_citations({**state, **compiled, **executed})["citations"]
        self.assertTrue(any("source note" in citation for citation in citations))
        ledger = project_task_artifact_trace(executed["tasks"], executed["artifacts"])
        self.assertEqual(ledger["integrity_status"], "ok")

        runtime_result = {**state, **compiled, **executed, "citations": citations}
        evaluator = RAGEvaluator(
            _StaticFinancialRunAgent(runtime_result), skip_llm_judges=True,
        )
        evaluation = evaluator.evaluate_one(EvalExample(
            id="generic-source-display", question=fixture["query"], ground_truth="10%",
            company="sample", year=2024, section="activity", answer_type="numeric",
            expected_calculation_result={"normalized_value": 10.0, "normalized_unit": "PERCENT", "tolerance": 0.0},
        ))
        self.assertIsNone(evaluation.error)
        self.assertEqual(evaluation.numeric_result_correctness, 1.0)
        self.assertEqual(evaluation.grounded_rendering_correctness, 1.0)
        self.assertEqual(evaluation.calculation_correctness, 1.0)
        self.assertIsNone(evaluation.raw_faithfulness)

    def test_program_compiler_retries_once_for_missing_obligation(self) -> None:
        source_candidates = [
            {
                "candidate_id": "chunk-1::value:0",
                "source_anchor": "[sample | 2024 | section]",
                "text": "quantity 10",
                "candidate_kind": "structured_value",
                "metadata": {
                    "row_label": "quantity",
                    "table_source_id": "table-a",
                    "structured_cells": [
                        {"column_headers": ["current"], "value_text": "10", "unit_hint": "개"},
                    ],
                },
            }
        ]
        candidate_id = next(
            item["candidate_id"]
            for item in build_semantic_candidate_catalog(source_candidates)
            if item["kind"] == "numeric"
        )
        first = SemanticCalculationProgram.model_validate(
            {"status": "incomplete", "missing_obligation_ids": ["ob_001"]}
        )
        second = SemanticCalculationProgram.model_validate(
            {
                "status": "ready",
                "direct_bindings": [{"obligation_id": "ob_001", "candidate_id": candidate_id}],
            }
        )
        llm = _StructuredQueueLLM(first, second)
        agent = self._agent(llm)
        obligations = [_obligation("ob_001", "direct_value", "quantity", display_unit="개")]
        state = {
            "query": "Return the quantity.",
            "query_type": "numeric_fact",
            "intent": "numeric_fact",
            "topic": "quantity",
            "report_scope": {},
            "answer_obligations": obligations,
            "semantic_plan": {"program_required": True, "answer_obligations": obligations},
            "active_subtask": {
                "task_id": "task_1",
                "metric_family": "semantic_program",
                "metric_label": "quantity",
                "query": "Return the quantity.",
            },
            "tasks": [],
            "artifacts": [],
            "evidence_items": [],
            "retrieved_docs": [],
            "seed_retrieved_docs": [],
            "planner_debug_trace": {},
            "resolved_calculation_trace": {},
        }
        catalog = build_semantic_candidate_catalog(source_candidates)
        with patch.object(agent, "_semantic_candidate_catalog_for_state", return_value=catalog):
            compiled = agent._compile_semantic_calculation_program(state)
        self.assertEqual(len(llm.prompts), 2)
        self.assertEqual(compiled["semantic_program_retry_count"], 1)
        self.assertEqual(compiled["semantic_program_validation"]["status"], "ready")
        self.assertIn("missing_obligation_ids", str(llm.prompts[1]))
        history = compiled["resolved_calculation_trace"]["calculation_plan"][
            "program_validation_history"
        ]
        self.assertEqual([item["attempt"] for item in history], [1, 2])
        self.assertEqual([item["status"] for item in history], ["invalid", "ready"])
        self.assertEqual(
            compiled["resolved_calculation_trace"]["calculation_plan"][
                "program_retry_count"
            ],
            1,
        )

    def test_independent_island_cannot_rebind_an_accepted_obligation(self) -> None:
        catalog = [
            _candidate("cand-first", 10),
            _candidate("cand-missing", 20),
            _candidate("cand-replacement", 999),
        ]
        first = SemanticCalculationProgram.model_validate(
            {
                "status": "incomplete",
                "direct_bindings": [
                    {"obligation_id": "ob_001", "candidate_id": "cand-first"}
                ],
                "missing_obligation_ids": ["ob_002"],
            }
        )
        second = SemanticCalculationProgram.model_validate(
            {
                "status": "ready",
                "direct_bindings": [
                    {
                        "obligation_id": "ob_001",
                        "candidate_id": "cand-replacement",
                    },
                    {
                        "obligation_id": "ob_002",
                        "candidate_id": "cand-missing",
                    },
                ],
            }
        )
        llm = _StructuredQueueLLM(first, second)
        agent = self._agent(llm)
        obligations = [
            _obligation("ob_001", "direct_value", "first"),
            _obligation("ob_002", "direct_value", "second"),
        ]
        state = {
            "query": "Return both values.",
            "query_type": "numeric_fact",
            "intent": "numeric_fact",
            "topic": "values",
            "report_scope": {},
            "answer_obligations": obligations,
            "semantic_plan": {
                "program_required": True,
                "answer_obligations": obligations,
            },
            "active_subtask": {
                "task_id": "task_1",
                "metric_family": "semantic_program",
                "metric_label": "values",
                "query": "Return both values.",
            },
            "tasks": [],
            "artifacts": [],
            "evidence_items": [],
            "retrieved_docs": [],
            "seed_retrieved_docs": [],
            "planner_debug_trace": {},
            "resolved_calculation_trace": {},
        }
        with patch.object(
            agent,
            "_semantic_candidate_catalog_for_state",
            return_value=catalog,
        ):
            compiled = agent._compile_semantic_calculation_program(state)

        bindings = {
            item["obligation_id"]: item["candidate_id"]
            for item in compiled["semantic_program"]["direct_bindings"]
        }
        self.assertEqual(
            bindings,
            {"ob_001": "cand-first", "ob_002": "cand-missing"},
        )
        self.assertEqual(compiled["semantic_program_retry_count"], 0)
        self.assertEqual(len(llm.prompts), 2)
        second_island_prompt = str(llm.prompts[1])
        self.assertIn("ob_002", second_island_prompt)
        self.assertNotIn(
            '"obligation_id": "ob_001"',
            second_island_prompt.split("Candidate catalog:", 1)[0],
        )

    def test_compilation_islands_follow_only_dependency_and_coupling_edges(self) -> None:
        obligations = [
            _obligation("ob_a", "direct_value", "a"),
            _obligation(
                "ob_b",
                "direct_value",
                "b",
                depends_on=["ob_a"],
            ),
            _obligation(
                "ob_c",
                "direct_value",
                "c",
                coupling_key="shared",
            ),
            _obligation(
                "ob_d",
                "direct_value",
                "d",
                coupling_key="shared",
            ),
            _obligation("ob_e", "direct_value", "e"),
        ]

        plan = build_semantic_compilation_islands(obligations)

        self.assertEqual(plan["status"], "ok")
        self.assertEqual(
            [item["obligation_ids"] for item in plan["islands"]],
            [["ob_a", "ob_b"], ["ob_c", "ob_d"], ["ob_e"]],
        )

    def test_invalid_dependency_islands_fail_before_any_compiler_call(self) -> None:
        obligations = [
            _obligation(
                "ob_a",
                "direct_value",
                "a",
                depends_on=["missing"],
            ),
            _obligation(
                "ob_b",
                "direct_value",
                "b",
                depends_on=["ob_b"],
            ),
            _obligation(
                "ob_c",
                "direct_value",
                "c",
                depends_on=["ob_d"],
            ),
            _obligation(
                "ob_d",
                "direct_value",
                "d",
                depends_on=["ob_c"],
            ),
        ]
        agent = self._agent(_StructuredQueueLLM())
        state = {
            "query": "Return the declared values.",
            "answer_obligations": obligations,
            "semantic_plan": {
                "program_required": True,
                "answer_obligations": obligations,
            },
            "active_subtask": {"task_id": "task_1"},
            "tasks": [],
            "artifacts": [],
            "resolved_calculation_trace": {},
        }

        with patch.object(
            agent,
            "_semantic_candidate_catalog_for_state",
            return_value=[],
        ):
            compiled = agent._compile_semantic_calculation_program(state)

        self.assertEqual(agent.llm.prompts, [])
        diagnostics = compiled["resolved_calculation_trace"][
            "calculation_plan"
        ]["candidate_stage_diagnostics"]
        self.assertEqual(diagnostics["compiler_call_count"], 0)
        self.assertEqual(
            {
                error["code"]
                for island in diagnostics["islands"]
                for error in island["preflight_errors"]
            },
            {"unknown_dependency", "self_dependency", "dependency_cycle"},
        )

    def test_island_and_global_reservation_limits_fail_before_calls(self) -> None:
        scenarios = {
            "island_limit": [
                _obligation(f"ob_{index}", "direct_value", f"value {index}")
                for index in range(9)
            ],
            "candidate_reservation": [
                _obligation(
                    f"ob_{index}",
                    "derived_value",
                    f"value {index}",
                    coupling_key="shared",
                    evidence_requirements=[
                        _requirement(
                            f"ob_{index}:req_{requirement}",
                            f"input {requirement}",
                        )
                        for requirement in range(3)
                    ],
                )
                for index in range(7)
            ],
        }
        for scenario, obligations in scenarios.items():
            with self.subTest(scenario=scenario):
                agent = self._agent(_StructuredQueueLLM())
                state = {
                    "query": "Return all declared values.",
                    "answer_obligations": obligations,
                    "semantic_plan": {
                        "program_required": True,
                        "answer_obligations": obligations,
                    },
                    "active_subtask": {"task_id": "task_1"},
                    "tasks": [],
                    "artifacts": [],
                    "resolved_calculation_trace": {},
                }
                with patch.object(
                    agent,
                    "_semantic_candidate_catalog_for_state",
                    return_value=[],
                ):
                    compiled = agent._compile_semantic_calculation_program(
                        state
                    )
                diagnostics = compiled["resolved_calculation_trace"][
                    "calculation_plan"
                ]["candidate_stage_diagnostics"]
                self.assertEqual(agent.llm.prompts, [])
                self.assertEqual(diagnostics["compiler_call_count"], 0)
                self.assertEqual(
                    compiled["semantic_program_validation"]["status"],
                    "invalid",
                )

    def test_independent_island_prompts_have_separate_candidate_authority(self) -> None:
        obligations = [
            _obligation(
                "ob_a",
                "direct_value",
                "alpha value",
                scope=_scope(segment="alpha"),
            ),
            _obligation(
                "ob_b",
                "direct_value",
                "beta value",
                scope=_scope(segment="beta"),
            ),
        ]
        catalog = [
            {**_candidate("cand-a", 10, row_label="alpha value"), "segment": "alpha"},
            {**_candidate("cand-b", 20, row_label="beta value"), "segment": "beta"},
        ]
        llm = _StructuredQueueLLM(
            SemanticCalculationProgram.model_validate(
                {
                    "direct_bindings": [
                        {"obligation_id": "ob_a", "candidate_id": "cand-a"}
                    ]
                }
            ),
            SemanticCalculationProgram.model_validate(
                {
                    "direct_bindings": [
                        {"obligation_id": "ob_b", "candidate_id": "cand-b"}
                    ]
                }
            ),
        )
        agent = self._agent(llm)
        state = {
            "query": "Return alpha and beta values.",
            "answer_obligations": obligations,
            "semantic_plan": {
                "program_required": True,
                "answer_obligations": obligations,
            },
            "active_subtask": {"task_id": "task_1"},
            "tasks": [],
            "artifacts": [],
            "resolved_calculation_trace": {},
        }

        with patch.object(
            agent,
            "_semantic_candidate_catalog_for_state",
            return_value=catalog,
        ):
            compiled = agent._compile_semantic_calculation_program(state)

        self.assertEqual(len(llm.prompts), 2)
        self.assertIn("cand-a", str(llm.prompts[0]))
        self.assertNotIn("cand-b", str(llm.prompts[0]))
        self.assertIn("cand-b", str(llm.prompts[1]))
        self.assertNotIn("cand-a", str(llm.prompts[1]))
        self.assertEqual(compiled["semantic_program_validation"]["status"], "ready")

    def test_graph_routes_program_path_without_operation_family_branching(self) -> None:
        agent = self._agent(_StructuredQueueLLM())
        state = {
            "semantic_plan": {"program_required": True},
            "active_subtask": {"operation_family": "ratio"},
            "intent": "comparison",
            "retrieved_docs": [],
            "seed_retrieved_docs": [],
        }
        self.assertEqual(agent._route_after_expand(state), "program_compiler")
        self.assertEqual(
            agent._route_after_expand({"semantic_plan": {"program_required": False}}),
            "evidence",
        )
        self.assertEqual(
            agent._route_after_retrieval_v2(
                {"requirements": {"semantic_plan": {"program_required": True}}}
            ),
            "build_candidates",
        )

    def test_graph_dag_contains_only_canonical_numeric_program_nodes(self) -> None:
        agent = self._agent(_StructuredQueueLLM())
        graph = agent._build_graph().get_graph()
        nodes = set(graph.nodes)
        self.assertTrue(
            {
                "route_request",
                "plan_requirements",
                "retrieve_evidence",
                "build_candidates",
                "compile_program",
                "execute_numeric",
                "build_narrative",
                "assemble_ledger",
                "assemble_final",
            }.issubset(nodes)
        )
        self.assertTrue(
            {
                "operand_extractor",
                "formula_planner",
                "calculator",
                "aggregate",
                "reflection",
                "reconcile",
            }.isdisjoint(nodes)
        )

    def test_graph_phase_keys_have_exactly_one_declared_writer(self) -> None:
        self.assertEqual(
            set(FINANCIAL_GRAPH_PHASE_WRITERS),
            {
                "request",
                "routing",
                "requirements",
                "retrieval",
                "candidates",
                "compilation",
                "numeric_result",
                "narrative_result",
                "ledger",
                "final_result",
            },
        )
        self.assertEqual(
            len(set(FINANCIAL_GRAPH_PHASE_WRITERS.values())),
            len(FINANCIAL_GRAPH_PHASE_WRITERS),
        )


if __name__ == "__main__":
    unittest.main()
