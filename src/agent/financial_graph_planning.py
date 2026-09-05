"""Semantic requirement planning for the financial graph runtime."""

from __future__ import annotations

import json
import logging
import re
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from src.agent.financial_graph_model_loaders import requirement_planner_output_model
from src.agent.financial_langchain_loaders import chat_prompt_template_from_template
from src.agent.financial_retrieval_hints import infer_statement_and_section_hints
from src.agent.financial_runtime_normalization import _normalise_spaces, resolve_unit_spec
from src.agent.financial_scope_policies import explicit_query_consolidation_scopes
from src.agent.financial_runtime_trace import (
    report_cache_candidate_for_trace,
    resolve_runtime_calculation_trace,
)
from src.config import get_financial_ontology
from src.config.retrieval_policy import (
    PLANNING_POLICY,
    active_narrative_policies,
    narrative_policy_preferred_sections,
    narrative_policy_query_suffixes,
)

if TYPE_CHECKING:
    from src.agent.financial_graph_state import FinancialAgentState, PlanningInput, RequirementsPhase, RoutingInput, RoutingPhase


logger = logging.getLogger(__name__)


def _normalise_optional_scope_value(value: Any) -> str:
    cleaned = _normalise_spaces(str(value or ""))
    if cleaned.lower() in {
        "report_scope",
        "unknown",
        "unspecified",
        "none",
        "null",
        "n/a",
    }:
        return ""
    return cleaned


def _report_scope_source_companies(report_scope: Dict[str, Any]) -> List[str]:
    companies: List[str] = []
    for key in ("source_reports", "report_inventory"):
        for item in list((report_scope or {}).get(key) or []):
            if not isinstance(item, dict):
                continue
            metadata = dict(item.get("metadata") or {})
            company = _normalise_spaces(
                str(
                    item.get("company")
                    or item.get("corp_name")
                    or item.get("entity")
                    or metadata.get("company")
                    or metadata.get("corp_name")
                    or metadata.get("entity")
                    or ""
                )
            )
            if company and company not in companies:
                companies.append(company)
    return companies


def align_scope_hints(
    *,
    companies: Optional[List[str]],
    years: Optional[List[int]],
    report_scope: Dict[str, Any],
) -> tuple[List[str], List[int]]:
    """Merge query hints with the caller's explicit report scope."""

    normalized_companies = [
        str(item).strip() for item in (companies or []) if str(item).strip()
    ]
    scope_company = _normalise_spaces(
        str(report_scope.get("company") or report_scope.get("corp_name") or "")
    )
    normalized_companies = list(
        dict.fromkeys(
            [
                *_report_scope_source_companies(report_scope),
                *([scope_company] if scope_company else []),
                *normalized_companies,
            ]
        )
    )

    normalized_years: List[int] = []
    for value in [report_scope.get("year"), *(years or [])]:
        try:
            year = int(value)
        except (TypeError, ValueError):
            continue
        if year not in normalized_years:
            normalized_years.append(year)
    return normalized_companies, normalized_years


class FinancialAgentPlanningMixin:
    """Own the pre-retrieval semantic contract, without operation classification."""

    def _classify_query(self, state: RoutingInput) -> RoutingPhase:
        result = self.query_router.route(state["query"])
        return {
            "query_type": result.intent,
            "intent": result.intent,
            "format_preference": result.format_preference,
            "routing_source": result.routing_source,
            "routing_confidence": float(result.routing_confidence or 0.0),
            "routing_scores": dict(result.routing_scores or {}),
            "routing_degraded_reason": str(result.degraded_reason or ""),
        }

    def _extract_entities(self, state: FinancialAgentState) -> Dict[str, Any]:
        query = str(state.get("query") or "")
        report_scope = dict(state.get("report_scope") or {})
        query_years = [int(token) for token in re.findall(r"20\d{2}", query)]
        companies, years = align_scope_hints(
            companies=[],
            years=list(dict.fromkeys(query_years)),
            report_scope=report_scope,
        )
        logger.info("[extract] companies=%s years=%s", companies, years)
        return {
            "companies": companies,
            "years": years,
            "topic": query,
            "section_filter": None,
            "target_metric_family": "",
            "target_metric_family_hint": "",
        }

    def _build_llm_requirement_plan(
        self,
        *,
        query: str,
        topic: str,
        intent: str,
        report_scope: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Create answer obligations and retrieval hints, never a formula type."""

        ontology = get_financial_ontology()
        concept_specs = list(ontology.concept_specs(query, topic, intent) or [])
        if not concept_specs:
            concept_specs = list(ontology.all_concept_specs() or [])[:24]
        ontology_hints = [
            {
                "concept": str(spec.get("concept") or ""),
                "name": str(spec.get("name") or ""),
                "aliases": list(spec.get("aliases") or [])[:8],
                "unit_family": str(spec.get("unit_family") or ""),
                "preferred_sections": list(spec.get("preferred_sections") or [])[:6],
                "preferred_statement_types": list(
                    spec.get("preferred_statement_types") or []
                )[:4],
            }
            for spec in concept_specs[:32]
        ]
        RequirementPlannerOutput = requirement_planner_output_model()
        structured_llm = self._llm_for_phase("requirement_planning").with_structured_output(
            RequirementPlannerOutput
        )
        prompt = chat_prompt_template_from_template(
            str(PLANNING_POLICY.get("requirement_planner_prompt_template") or "")
        )
        try:
            prompt_value = prompt.invoke(
                {
                    "query": query,
                    "topic": topic,
                    "intent": intent,
                    "report_scope": json.dumps(report_scope, ensure_ascii=False),
                    "ontology_hints": json.dumps(ontology_hints, ensure_ascii=False),
                }
            )
            planned: Any = structured_llm.invoke(prompt_value)
        except Exception as exc:
            logger.warning("[requirement_plan] structured planner failed: %s", exc)
            companies, years = align_scope_hints(
                companies=[], years=[], report_scope=report_scope
            )
            return {
                "status": "incomplete",
                "companies": companies,
                "years": years,
                "topic": topic,
                "section_filter": None,
                "answer_obligations": [],
                "retrieval_queries": [query],
                "tasks": [],
                "planner_notes": ["requirement_planner_failed", str(exc)],
            }

        raw_obligations = [item.model_dump() for item in list(planned.obligations or [])]
        raw_id_to_stable: Dict[str, str] = {}
        for index, obligation in enumerate(raw_obligations, start=1):
            raw_id = _normalise_spaces(str(obligation.get("obligation_id") or ""))
            if raw_id and raw_id not in raw_id_to_stable:
                raw_id_to_stable[raw_id] = f"ob_{index:03d}"

        scope_company = _normalise_spaces(
            str(report_scope.get("company") or report_scope.get("corp_name") or "")
        )
        source_companies = _report_scope_source_companies(report_scope)
        report_company = source_companies[0] if len(source_companies) == 1 else scope_company
        report_period = _normalise_spaces(str(report_scope.get("year") or ""))
        query_consolidation_scopes = explicit_query_consolidation_scopes(query)
        allowed_query_consolidation_scopes = set(query_consolidation_scopes)
        target_notes: List[str] = []
        dependency_notes: List[str] = []
        requirement_errors: List[Dict[str, str]] = []

        def normalize_semantic_target(
            raw_target: Any,
            *,
            concept_hints: Any = (),
        ) -> Dict[str, List[str]]:
            target = dict(raw_target or {})

            def normalized_values(values: Any) -> List[str]:
                return list(
                    dict.fromkeys(
                        cleaned
                        for item in (values or [])
                        for cleaned in [_normalise_spaces(str(item or ""))]
                        if cleaned
                    )
                )

            requested_concepts = normalized_values(target.get("concept_keys"))
            if not requested_concepts:
                requested_concepts = normalized_values(concept_hints)
            known_concepts: List[str] = []
            for concept_key in requested_concepts:
                if ontology.has_concept_key(concept_key):
                    known_concepts.append(concept_key)
                else:
                    target_notes.append(
                        f"unknown_semantic_target_concept:{concept_key}"
                    )
            return {
                "local_subjects": normalized_values(target.get("local_subjects")),
                "concept_keys": list(dict.fromkeys(known_concepts)),
                "metric_surfaces": normalized_values(target.get("metric_surfaces")),
            }

        def normalize_scope(
            raw_scope: Any,
            *,
            default_period: str = report_period,
            default_scope: Optional[Dict[str, Any]] = None,
        ) -> Dict[str, Any]:
            scope = dict(raw_scope or {})
            inherited = dict(default_scope or {})
            scope["company"] = (
                report_company
                or _normalise_optional_scope_value(scope.get("company"))
                or _normalise_optional_scope_value(inherited.get("company"))
            )
            scope["period"] = _normalise_spaces(
                str(
                    scope.get("period")
                    or inherited.get("period")
                    or default_period
                )
            )
            consolidation = _normalise_spaces(
                str(scope.get("consolidation_scope") or "")
            ).lower()
            inherited_consolidation = _normalise_spaces(
                str(inherited.get("consolidation_scope") or "")
            ).lower()
            if len(query_consolidation_scopes) == 1:
                consolidation = query_consolidation_scopes[0]
            elif consolidation in allowed_query_consolidation_scopes:
                pass
            elif inherited_consolidation in allowed_query_consolidation_scopes:
                consolidation = inherited_consolidation
            else:
                consolidation = "unknown"
            scope["consolidation_scope"] = consolidation
            scope["segment"] = (
                _normalise_optional_scope_value(scope.get("segment"))
                or _normalise_optional_scope_value(inherited.get("segment"))
            )
            scope["basis"] = (
                _normalise_optional_scope_value(scope.get("basis"))
                or _normalise_optional_scope_value(inherited.get("basis"))
            )
            return scope

        obligations: List[Dict[str, Any]] = []
        for index, obligation in enumerate(raw_obligations, start=1):
            stable_id = f"ob_{index:03d}"
            declared_unit = _normalise_spaces(str(obligation.get("display_unit") or ""))
            if declared_unit and declared_unit.upper() != "UNKNOWN" and resolve_unit_spec(declared_unit) is None:
                requirement_errors.append({
                    "code": "invalid_obligation_unit", "obligation_id": stable_id,
                    "owner_id": stable_id, "candidate_id": "",
                    "location": "obligation.display_unit", "repair_action": "repair_requirements",
                    "detail": declared_unit,
                })
            scope = normalize_scope(obligation.get("scope"))
            obligation_concept_hints = list(obligation.get("concept_hints") or [])
            obligation_target = normalize_semantic_target(
                obligation.get("semantic_target"),
                concept_hints=obligation_concept_hints,
            )
            raw_evidence_requirement_ids = {
                requirement_id
                for requirement in (obligation.get("evidence_requirements") or [])
                for requirement_id in [
                    _normalise_spaces(str(dict(requirement or {}).get("requirement_id") or ""))
                ]
                if requirement_id
            }
            evidence_requirements = []
            for requirement_index, requirement in enumerate(
                obligation.get("evidence_requirements") or [],
                start=1,
            ):
                requirement = dict(requirement or {})
                evidence_requirements.append(
                    {
                        **requirement,
                        "requirement_id": f"{stable_id}:req_{requirement_index:03d}",
                        "label": _normalise_spaces(
                            str(
                                requirement.get("label")
                                or f"{stable_id}:req_{requirement_index:03d}"
                            )
                        ),
                        "scope": normalize_scope(
                            requirement.get("scope"),
                            default_period=str(scope.get("period") or report_period),
                            default_scope=scope,
                        ),
                        "retrieval_hints": list(
                            dict.fromkeys(
                                _normalise_spaces(str(item))
                                for item in (requirement.get("retrieval_hints") or [])
                                if _normalise_spaces(str(item))
                            )
                        ),
                        "concept_hints": list(
                            dict.fromkeys(
                                _normalise_spaces(str(item))
                                for item in (requirement.get("concept_hints") or [])
                                if _normalise_spaces(str(item))
                            )
                        ),
                        "semantic_target": normalize_semantic_target(
                            requirement.get("semantic_target"),
                            concept_hints=requirement.get("concept_hints") or [],
                        ),
                    }
                )
            own_evidence_dependency_ids = raw_evidence_requirement_ids | {
                str(requirement.get("requirement_id") or "")
                for requirement in evidence_requirements
            }
            dependencies = []
            for item in (
                _normalise_spaces(str(value))
                for value in (obligation.get("depends_on") or [])
            ):
                if not item:
                    continue
                if item in raw_id_to_stable:
                    dependencies.append(raw_id_to_stable[item])
                    continue
                if item in raw_id_to_stable.values():
                    dependencies.append(item)
                    continue
                if item in own_evidence_dependency_ids:
                    dependency_notes.append(
                        f"redundant_evidence_dependency_removed:{stable_id}:{item}"
                    )
                    continue
                dependencies.append(item)
            obligations.append(
                {
                    **obligation,
                    "obligation_id": stable_id,
                    "label": _normalise_spaces(
                        str(obligation.get("label") or stable_id)
                    ),
                    "scope": scope,
                    "retrieval_hints": list(
                        dict.fromkeys(
                            _normalise_spaces(str(item))
                            for item in (obligation.get("retrieval_hints") or [])
                            if _normalise_spaces(str(item))
                        )
                    ),
                    "concept_hints": list(
                        dict.fromkeys(
                            _normalise_spaces(str(item))
                            for item in (obligation.get("concept_hints") or [])
                            if _normalise_spaces(str(item))
                        )
                    ),
                    "semantic_target": obligation_target,
                    "evidence_requirements": evidence_requirements,
                    "depends_on": list(dict.fromkeys(dependencies)),
                    "coupling_key": _normalise_spaces(
                        str(obligation.get("coupling_key") or "")
                    ),
                }
            )

        retrieval_queries = [query]
        retrieval_queries.extend(
            _normalise_spaces(str(item))
            for item in (planned.retrieval_queries or [])
            if _normalise_spaces(str(item))
        )
        for obligation in obligations:
            retrieval_queries.extend(obligation.get("retrieval_hints") or [])
            for requirement in obligation.get("evidence_requirements") or []:
                retrieval_queries.extend(requirement.get("retrieval_hints") or [])
        retrieval_queries = list(dict.fromkeys(item for item in retrieval_queries if item))

        required_evidence: List[Dict[str, Any]] = []
        for obligation in obligations:
            kind = str(obligation.get("kind") or "")
            requirement_rows = list(obligation.get("evidence_requirements") or [])
            if kind == "narrative" and not requirement_rows:
                continue
            source_rows = (
                requirement_rows
                if kind in {"derived_value", "narrative"} and requirement_rows
                else [obligation]
            )
            for source_row in source_rows:
                required_evidence.append(
                    {
                        "label": str(
                            source_row.get("label")
                            or source_row.get("requirement_id")
                            or obligation.get("obligation_id")
                            or ""
                        ),
                        "concept": "",
                        "aliases": list(
                            dict.fromkeys(
                                [
                                    str(source_row.get("label") or ""),
                                    *list(source_row.get("retrieval_hints") or []),
                                    *list(source_row.get("concept_hints") or []),
                                ]
                            )
                        ),
                        "keywords": list(source_row.get("retrieval_hints") or []),
                        "role": str(
                            source_row.get("requirement_id")
                            or obligation.get("obligation_id")
                            or ""
                        ),
                        "required": bool(source_row.get("required", True)),
                        "binding_policy": dict(source_row.get("scope") or {}),
                        "unit_family": "",
                        "surface_contract": {},
                    }
                )
        preferred_statement_types, preferred_sections = infer_statement_and_section_hints(query)
        consolidation_scopes = {
            str(dict(item.get("scope") or {}).get("consolidation_scope") or "unknown")
            for item in obligations
        }
        consolidation_scope = (
            next(iter(consolidation_scopes))
            if len(consolidation_scopes) == 1
            else "unknown"
        )
        task = {
            "task_id": "task_1",
            "metric_family": "semantic_program",
            "metric_label": _normalise_spaces(str(planned.topic or topic or query)),
            "query": query,
            "required_evidence": required_evidence,
            "depends_on": [],
            "inputs": [],
            "produces": [
                {
                    "slot": str(obligation.get("obligation_id") or ""),
                    "role": str(obligation.get("kind") or ""),
                    "concept": "",
                    "period": str(
                        dict(obligation.get("scope") or {}).get("period") or ""
                    ),
                    "label": str(obligation.get("label") or ""),
                    "segment_label": str(
                        dict(obligation.get("scope") or {}).get("segment") or ""
                    ),
                }
                for obligation in obligations
            ],
            "preferred_statement_types": preferred_statement_types,
            "preferred_sections": preferred_sections,
            "retrieval_queries": retrieval_queries,
            "constraints": {
                "consolidation_scope": consolidation_scope,
                "period_focus": "unknown",
                "entity_scope": "company",
                "segment_scope": (
                    "segment"
                    if any(
                        str(dict(item.get("scope") or {}).get("segment") or "")
                        for item in obligations
                    )
                    else "none"
                ),
            },
            "answer_obligation_ids": [
                str(item.get("obligation_id") or "") for item in obligations
            ],
        }
        companies, years = align_scope_hints(
            companies=list(planned.companies or []),
            years=list(planned.years or []),
            report_scope=report_scope,
        )
        return {
            "status": "ok" if obligations else "incomplete",
            "companies": companies,
            "years": years,
            "topic": _normalise_spaces(str(planned.topic or topic or query)),
            "section_filter": _normalise_spaces(str(planned.section_filter or "")) or None,
            "answer_obligations": obligations,
            "retrieval_queries": retrieval_queries,
            "requirement_errors": requirement_errors,
            "tasks": [task],
            "planner_notes": [
                item
                for item in (
                    "requirement_planner",
                    _normalise_spaces(str(planned.rationale or "")),
                    *list(dict.fromkeys(target_notes)),
                    *list(dict.fromkeys(dependency_notes)),
                )
                if item
            ],
        }

    def _plan_exclusive_narrative_task(
        self,
        state: FinancialAgentState,
        *,
        query: str,
        topic: str,
        report_scope: Dict[str, Any],
        plan_loop_count: int,
    ) -> Dict[str, Any]:
        policies = active_narrative_policies(query)
        if not any(bool(policy.get("exclusive_narrative_task")) for policy in policies):
            return {}
        retrieval_queries = [query]
        retrieval_queries.extend(
            _normalise_spaces(f"{query} {suffix}")
            for suffix in narrative_policy_query_suffixes(policies)
            if _normalise_spaces(str(suffix))
        )
        retrieval_queries = list(dict.fromkeys(retrieval_queries))
        narrative_task = {
            "task_id": "task_1",
            "metric_family": "narrative_summary",
            "metric_label": _normalise_spaces(topic or query),
            "query": query,
            "required_evidence": [],
            "preferred_statement_types": [],
            "preferred_sections": narrative_policy_preferred_sections(policies),
            "retrieval_queries": retrieval_queries,
            "constraints": {"context_scope": "narrative"},
        }
        semantic_plan = {
            "status": "narrative_policy_exclusive",
            "program_required": False,
            "fallback_to_general_search": False,
            "planned_metric_families": ["narrative_summary"],
            "answer_obligations": [],
            "tasks": [narrative_task],
            "planner_notes": ["exclusive_narrative_task_policy"],
        }
        companies, years = align_scope_hints(
            companies=list(state.get("companies") or []),
            years=list(state.get("years") or []),
            report_scope=report_scope,
        )
        return {
            "semantic_plan": semantic_plan,
            "answer_obligations": [],
            "planner_mode": "initial",
            "planner_feedback": "",
            "plan_loop_count": plan_loop_count,
            "companies": companies,
            "years": years,
            "topic": _normalise_spaces(topic or query),
            "section_filter": state.get("section_filter"),
            "calc_subtasks": [],
            "planned_metric_families": ["narrative_summary"],
            "retrieval_queries": retrieval_queries,
            "active_subtask_index": 0,
            "active_subtask": narrative_task,
            "subtask_results": [],
            "subtask_debug_trace": {
                "status": "narrative_policy_exclusive",
                "task_count": 0,
            },
            "subtask_loop_complete": True,
        }

    def _plan_answer_obligation_program(
        self, state: PlanningInput
    ) -> RequirementsPhase:
        intent = state.get("intent") or state.get("query_type", "qa")
        query = str(state.get("query") or "")
        topic = str(state.get("topic") or query)
        report_scope = dict(state.get("report_scope") or {})
        plan_loop_count = int(state.get("plan_loop_count") or 0)
        format_preference = _normalise_spaces(
            str(state.get("format_preference") or "")
        ).lower()
        requires_semantic_program = (
            intent in {"comparison", "trend", "numeric_fact"}
            or format_preference == "mixed"
        )

        if not requires_semantic_program:
            exclusive = self._plan_exclusive_narrative_task(
                state,
                query=query,
                topic=topic,
                report_scope=report_scope,
                plan_loop_count=plan_loop_count,
            )
            if exclusive:
                return exclusive
            return {
                "semantic_plan": {
                    "status": "fallback_general_search",
                    "program_required": False,
                    "fallback_to_general_search": True,
                    "planned_metric_families": [],
                    "answer_obligations": [],
                    "tasks": [],
                    "planner_notes": ["non_numeric_intent"],
                },
                "answer_obligations": [],
                "planner_mode": "initial",
                "planner_feedback": "",
                "plan_loop_count": plan_loop_count,
                "calc_subtasks": [],
                "planned_metric_families": [],
                "retrieval_queries": [query],
                "active_subtask_index": 0,
                "active_subtask": {},
                "subtask_results": [],
                "subtask_debug_trace": {"reason": "non_numeric_intent"},
                "subtask_loop_complete": True,
            }

        plan = self._build_llm_requirement_plan(
            query=query,
            topic=topic,
            intent=str(intent),
            report_scope=report_scope,
        )
        obligations = [dict(item) for item in (plan.get("answer_obligations") or [])]
        retrieval_queries = list(plan.get("retrieval_queries") or [query])
        tasks = [dict(task) for task in (plan.get("tasks") or [])]
        active_subtask = dict(tasks[0]) if tasks else {
            "task_id": "task_1",
            "metric_family": "semantic_program",
            "metric_label": _normalise_spaces(str(plan.get("topic") or topic or query)),
            "query": query,
            "required_evidence": [],
            "retrieval_queries": retrieval_queries,
            "answer_obligation_ids": [],
        }
        if not tasks:
            tasks = [active_subtask]
        semantic_plan = {
            "status": str(plan.get("status") or "incomplete"),
            "program_required": True,
            "fallback_to_general_search": False,
            "planned_metric_families": ["semantic_program"],
            "answer_obligations": obligations,
            "tasks": tasks,
            "planner_notes": list(plan.get("planner_notes") or []),
            "requirement_errors": list(plan.get("requirement_errors") or []),
        }
        companies, years = align_scope_hints(
            companies=list(plan.get("companies") or state.get("companies") or []),
            years=list(plan.get("years") or state.get("years") or []),
            report_scope=report_scope,
        )
        logger.info(
            "[requirement_plan] status=%s obligations=%s retrieval_queries=%s",
            semantic_plan.get("status"),
            len(obligations),
            len(retrieval_queries),
        )
        return {
            "semantic_plan": semantic_plan,
            "answer_obligations": obligations,
            "planner_mode": "initial",
            "planner_feedback": "",
            "plan_loop_count": plan_loop_count,
            "companies": companies,
            "years": years,
            "topic": _normalise_spaces(str(plan.get("topic") or topic or query)),
            "section_filter": plan.get("section_filter") or state.get("section_filter"),
            "calc_subtasks": tasks,
            "planned_metric_families": ["semantic_program"],
            "retrieval_queries": retrieval_queries,
            "active_subtask_index": 0,
            "active_subtask": active_subtask,
            "subtask_results": [],
            "subtask_debug_trace": {
                "status": semantic_plan.get("status"),
                "task_count": 1,
                "answer_obligation_count": len(obligations),
                "planner_notes": list(semantic_plan.get("planner_notes") or []),
            },
            "subtask_loop_complete": False,
        }

    def _calc_query(self, state: FinancialAgentState) -> str:
        active_subtask = dict(state.get("active_subtask") or {})
        return str(active_subtask.get("query") or state["query"])

    def _project_runtime_calculation_trace(
        self, state: FinancialAgentState
    ) -> Dict[str, Any]:
        trace = resolve_runtime_calculation_trace(dict(state))
        if trace and not trace.get("report_cache_candidate"):
            report_cache_candidate = report_cache_candidate_for_trace(dict(state), trace)
            if report_cache_candidate:
                trace = {**trace, "report_cache_candidate": report_cache_candidate}
        return trace
