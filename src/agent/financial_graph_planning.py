"""
Planning mixin for the financial graph agent.

This module owns the "front" of the graph:
- classify the query
- extract entity and metric hints
- translate the query into numeric subtasks when possible
- project ledger state back into the runtime calculation trace
"""

from __future__ import annotations

import json
import logging
import re
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from src.agent.financial_graph_calculation_rendering import infer_concept_ratio_result_unit
from src.agent.financial_graph_helpers import (
    _annotate_task_dependencies,
    _build_concept_metric_label,
    _build_concept_required_operands,
    _build_concept_task_constraints,
    _build_generic_retrieval_queries,
    _build_metric_task_query,
    _build_semantic_numeric_plan,
    _infer_generic_concept_spec,
    _infer_operation_family_from_query,
    align_scope_hints,
    append_hybrid_narrative_task,
    apply_segment_labels_to_llm_resolved_specs,
    build_hybrid_narrative_subtask,
    exclusive_narrative_task_policy_active,
    llm_plan_preserves_analysis_shape,
    llm_plan_preserves_segment_sum_shape,
    push_narrative_tasks_after_numeric,
    validate_concept_planner_task,
)
from src.agent.financial_graph_model_loaders import (
    _concept_planner_output_model,
    _validate_answer_slots_payload,
)
from src.agent.financial_answer_slots import answer_slot_has_material
from src.agent.financial_langchain_loaders import _chat_prompt_template_from_template
from src.agent.financial_answer_projection import (
    promote_nested_subtask_result_if_more_specific,
)
if TYPE_CHECKING:
    from src.agent.financial_graph_state import FinancialAgentState
from src.agent.financial_runtime_normalization import (
    _clean_source_row_ids,
    _normalise_spaces,
)
from src.agent.financial_retrieval_hints import _infer_statement_and_section_hints
from src.agent.financial_runtime_trace import (
    _project_task_trace_from_state,
    _report_cache_candidate_for_trace,
    _resolve_runtime_calculation_trace,
)
from src.agent.financial_task_artifacts import semantic_plan_artifact_update as _semantic_plan_artifact_update
from src.agent.financial_lookup_recovery import (
    coerce_lookup_magnitude_record,
    lookup_operand_matches_active_task,
    lookup_slot_supporting_doc_evidence,
    refine_lookup_slot_unit_from_evidence,
    synthesize_lookup_answer_slot_from_prose,
)
from src.config import get_financial_ontology
from src.config.retrieval_policy import PLANNING_POLICY
logger = logging.getLogger(__name__)


def _project_logical_tasks_from_execution_tasks(
    logical_tasks: List[Dict[str, Any]],
    execution_tasks: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Keep semantic-plan tasks compact while borrowing dependency annotations.

    Planner-facing payloads should preserve the original semantic task list
    (e.g. one ratio task), while executor-facing payloads can expand into
    lookup producers plus a derived consumer. We therefore copy dependency
    annotations back onto the original logical tasks without exposing the
    synthetic execution-only lookup tasks in `semantic_plan.tasks`.
    """
    execution_by_id = {
        str(task.get("task_id") or "").strip(): dict(task)
        for task in execution_tasks
        if str(task.get("task_id") or "").strip()
    }
    projected: List[Dict[str, Any]] = []
    for task in logical_tasks:
        task_id = str(task.get("task_id") or "").strip()
        if task_id and task_id in execution_by_id:
            projected.append(dict(execution_by_id[task_id]))
        else:
            projected.append(dict(task))
    return projected


def _dependency_closure_task_ids(
    tasks: List[Dict[str, Any]],
    seed_task_ids: List[str],
) -> set[str]:
    """Return the dependency closure (ancestors + seeds) for the given tasks."""
    task_by_id = {
        str(task.get("task_id") or "").strip(): dict(task)
        for task in tasks
        if str(task.get("task_id") or "").strip()
    }
    closure = {
        _normalise_spaces(task_id)
        for task_id in seed_task_ids
        if _normalise_spaces(task_id)
    }
    pending = list(closure)
    while pending:
        task_id = pending.pop()
        task = task_by_id.get(task_id)
        if not task:
            continue
        for dependency in list(task.get("depends_on") or []):
            dependency_id = _normalise_spaces(str(dependency or ""))
            if dependency_id and dependency_id not in closure:
                closure.add(dependency_id)
                pending.append(dependency_id)
    return closure


def _non_numeric_operation_intent_override(query: str, topic: str, intent: str) -> tuple[str, str]:
    policy = dict(
        PLANNING_POLICY.get("non_numeric_operation_intent_override")
        or PLANNING_POLICY.get("qa_numeric_lookup_intent_override")
        or {}
    )
    if not bool(policy.get("enabled", False)):
        return intent, ""

    source_intents = {
        _normalise_spaces(str(item))
        for item in (policy.get("source_intents") or ())
        if _normalise_spaces(str(item))
    }
    normalized_intent = _normalise_spaces(intent or "qa")
    if normalized_intent not in source_intents:
        return intent, ""

    normalized_query = _normalise_spaces(query)
    markers = tuple(str(item).strip() for item in (policy.get("query_markers") or ()) if str(item).strip())
    if markers and not any(marker in normalized_query for marker in markers):
        return intent, ""

    ontology = get_financial_ontology()
    operation_family = _infer_operation_family_from_query(query, ontology)
    allowed_operations = {
        _normalise_spaces(str(item))
        for item in (policy.get("operation_families") or ())
        if _normalise_spaces(str(item))
    }
    if allowed_operations and _normalise_spaces(operation_family) not in allowed_operations:
        return intent, ""

    target_intent = str(policy.get("target_intent") or "numeric_fact").strip() or "numeric_fact"
    concept_specs = ontology.concept_specs(query, topic, target_intent)
    try:
        minimum_concepts = int(policy.get("minimum_concepts") or 1)
    except (TypeError, ValueError):
        minimum_concepts = 1
    allowed_unit_families = {
        _normalise_spaces(str(item)).upper()
        for item in (policy.get("unit_families") or ())
        if _normalise_spaces(str(item))
    }
    concept_contract_ok = len(concept_specs) >= max(1, minimum_concepts)
    if concept_contract_ok and allowed_unit_families:
        matched_units = {
            _normalise_spaces(str(spec.get("unit_family") or "")).upper()
            for spec in concept_specs
            if _normalise_spaces(str(spec.get("unit_family") or ""))
        }
        concept_contract_ok = bool(matched_units.intersection(allowed_unit_families))

    generic_plan_ok = False
    if not concept_contract_ok and bool(policy.get("allow_generic_numeric_plan", False)):
        candidate_plan = _build_semantic_numeric_plan(
            query=query,
            topic=topic,
            intent=target_intent,
            report_scope={},
            target_metric_family="",
        )
        for task in (candidate_plan.get("tasks") or []):
            task_operation = _normalise_spaces(str(task.get("operation_family") or ""))
            if allowed_operations and task_operation not in allowed_operations:
                continue
            operands = [dict(operand) for operand in (task.get("required_operands") or [])]
            if not operands:
                continue
            if allowed_unit_families:
                operand_units = {
                    _normalise_spaces(str(operand.get("unit_family") or "")).upper()
                    for operand in operands
                    if _normalise_spaces(str(operand.get("unit_family") or ""))
                }
                if not operand_units.intersection(allowed_unit_families):
                    continue
            generic_plan_ok = True
            break

    if not concept_contract_ok and not generic_plan_ok:
        return intent, ""

    planner_note = str(policy.get("planner_note") or "non_numeric_operation_promoted").strip()
    return target_intent, planner_note


class FinancialAgentPlanningMixin:
    def _classify_query(self, state: FinancialAgentState) -> Dict[str, Any]:
        """Run the lightweight router before any expensive retrieval work."""
        result = self.query_router.route(state["query"])
        return {
            "query_type": result.intent,
            "intent": result.intent,
            "format_preference": result.format_preference,
            "routing_source": result.routing_source,
            "routing_confidence": float(result.routing_confidence or 0.0),
            "routing_scores": dict(result.routing_scores or {}),
        }
    def _extract_entities(self, state: FinancialAgentState) -> Dict[str, Any]:
        """Seed lightweight scope hints before the planner builds the full understanding plan."""
        query = str(state.get("query") or "")
        report_scope = dict(state.get("report_scope") or {})
        query_years = [int(token) for token in re.findall(r"20\d{2}", query)]
        years = list(dict.fromkeys(query_years))
        companies, years = align_scope_hints(companies=[], years=years, report_scope=report_scope)
        logger.info(
            "[extract] companies=%s years=%s target_metric=%s",
            companies,
            years,
            "-",
        )
        return {
            "companies": companies,
            "years": years,
            "topic": query,
            "section_filter": None,
            # Keep metric-family hints empty by default so the planner can prefer
            # concept + operation decomposition instead of eagerly collapsing the
            # query into a legacy metric family.
            "target_metric_family": "",
            "target_metric_family_hint": "",
        }
    def _build_llm_concept_numeric_plan(
        self,
        *,
        query: str,
        topic: str,
        intent: str,
        report_scope: Dict[str, Any],
        planner_feedback: str = "",
        existing_tasks: Optional[List[Dict[str, Any]]] = None,
        replan_mode: bool = False,
    ) -> Optional[Dict[str, Any]]:
        """Ask the LLM to rewrite an implicit numeric query into concept-level tasks.

        This planner is intentionally constrained:
        - operations are limited to a small closed set
        - operands must reference known ontology concepts
        - output is converted back into the same task IR used elsewhere
        """
        ontology = get_financial_ontology()
        planner_feedback = _normalise_spaces(planner_feedback)
        concept_seed_query = query if not planner_feedback else f"{query}\n{planner_feedback}"
        concept_specs = ontology.concept_specs(concept_seed_query, topic, intent)
        used_full_catalog_fallback = False
        if not concept_specs:
            concept_specs = ontology.all_concept_specs()
            used_full_catalog_fallback = True
        if not concept_specs:
            return None
        concept_spec_by_key = {
            str(spec.get("concept") or "").strip(): dict(spec)
            for spec in concept_specs
            if str(spec.get("concept") or "").strip()
        }
        allowed_concept_keys = {
            str(spec.get("concept") or "").strip()
            for spec in concept_specs
            if str(spec.get("concept") or "").strip()
        }
        for spec in concept_specs:
            allowed_concept_keys.update(
                str(item).strip()
                for item in (spec.get("member_concepts") or [])
                if str(item).strip()
            )
        existing_tasks = [dict(task) for task in (existing_tasks or [])]

        concept_lines: List[str] = []
        for spec in concept_specs:
            concept_lines.append(
                "- {concept} [{kind}]: {name} | aliases={aliases} | expands_to={expands_to} | preferred_statement_types={statement_types} | preferred_sections={sections}".format(
                    concept=str(spec.get("concept") or "").strip(),
                    kind="group" if spec.get("is_group") else "atomic",
                    name=str(spec.get("name") or "").strip(),
                    aliases=", ".join(spec.get("aliases") or []) or "-",
                    expands_to=", ".join(spec.get("member_concepts") or []) or "-",
                    statement_types=", ".join(spec.get("preferred_statement_types") or []) or "-",
                    sections=", ".join(spec.get("preferred_sections") or []) or "-",
                )
            )
        guidance = ontology.planner_guidance
        intent_cues = dict(guidance.get("intent_cues") or {})
        allowed_operations = ["lookup", "sum", "difference", "ratio", "growth_rate", "single_value"]
        existing_task_lines: List[str] = []
        for task in existing_tasks:
            operand_bits = ", ".join(
                f"{str(item.get('concept') or '').strip()}[{str(item.get('role') or '').strip() or '-'}]"
                for item in (task.get("required_operands") or [])
                if str(item.get("concept") or "").strip()
            ) or "-"
            existing_task_lines.append(
                "- {task_id}: {label} | op={operation} | operands={operands}".format(
                    task_id=str(task.get("task_id") or "").strip() or "-",
                    label=str(task.get("metric_label") or task.get("metric_family") or "").strip() or "-",
                    operation=str(task.get("operation_family") or "").strip() or "-",
                    operands=operand_bits,
                )
            )
        mode_specific_rules = (
            str(PLANNING_POLICY.get("concept_planner_replan_rules") or "")
            if replan_mode
            else str(PLANNING_POLICY.get("concept_planner_initial_rule") or "")
        )
        prompt = _chat_prompt_template_from_template(
            str(PLANNING_POLICY.get("concept_planner_prompt_template") or "")
        )
        ConceptPlannerOutput = _concept_planner_output_model()
        structured_llm = self._llm_for_phase("concept_planning").with_structured_output(ConceptPlannerOutput)
        try:
            prompt_value = prompt.invoke(
                {
                    "allowed_operations": ", ".join(allowed_operations),
                    "intent_cues": json.dumps(intent_cues, ensure_ascii=False),
                    "concept_catalog": "\n".join(concept_lines),
                    "planning_mode": "replan" if replan_mode else "initial",
                    "planner_feedback": planner_feedback or "-",
                    "existing_tasks": "\n".join(existing_task_lines) or "-",
                    "mode_specific_rules": mode_specific_rules,
                    "query": query,
                    "topic": topic,
                    "intent": intent,
                    "report_scope": json.dumps(report_scope, ensure_ascii=False),
                }
            )
            planned: ConceptPlannerOutput = structured_llm.invoke(prompt_value)
        except Exception as exc:
            logger.warning("[concept_llm_plan] structured planner failed: %s", exc)
            return None

        raw_tasks = list(planned.tasks or [])
        if not raw_tasks:
            return None

        validated_raw_tasks: List[Any] = []
        validation_notes: List[str] = []
        for index, raw_task in enumerate(raw_tasks, start=1):
            is_valid, note = validate_concept_planner_task(
                raw_task,
                ontology,
                allowed_concept_keys=allowed_concept_keys,
                concept_specs_by_key=concept_spec_by_key,
                support_text=concept_seed_query,
                require_surface_contract_match=used_full_catalog_fallback,
            )
            if not is_valid:
                validation_notes.append(f"invalid_task_{index}:{note}")
                continue
            validated_raw_tasks.append(raw_task)
        if not validated_raw_tasks:
            logger.info("[concept_llm_plan] all candidate tasks rejected by lightweight validator: %s", validation_notes)
            return None

        concept_by_key = {
            str(spec.get("concept") or "").strip(): dict(spec)
            for spec in ontology.all_concept_specs()
        }
        planner_tasks: List[Dict[str, Any]] = []
        for index, raw_task in enumerate(validated_raw_tasks, start=1):
            operation_family = str(raw_task.operation_family or "").strip().lower()
            if operation_family not in allowed_operations:
                continue

            resolved_specs: List[Dict[str, Any]] = []
            for raw_operand in list(raw_task.operands or []):
                concept_key = str(raw_operand.concept or "").strip()
                concept_spec = concept_by_key.get(concept_key)
                if not concept_spec:
                    continue
                resolved_spec = dict(concept_spec)
                resolved_spec["role"] = str(raw_operand.role or "").strip()
                resolved_specs.append(resolved_spec)

            if not resolved_specs:
                continue

            raw_metric_label = str(raw_task.metric_label or "").strip()
            if operation_family in {"lookup", "single_value"} and raw_metric_label and len(resolved_specs) == 1:
                metric_spec = _infer_generic_concept_spec(raw_metric_label, ontology)
                metric_concept = _normalise_spaces(str(metric_spec.get("concept") or ""))
                operand_concept = _normalise_spaces(str(resolved_specs[0].get("concept") or ""))
                if metric_concept and operand_concept and metric_concept != operand_concept:
                    validation_notes.append(
                        f"lookup_metric_operand_mismatch:{raw_metric_label}:{operand_concept}->{metric_concept}"
                    )
                    continue

            resolved_specs = apply_segment_labels_to_llm_resolved_specs(
                query=query,
                metric_label=raw_metric_label,
                operation_family=operation_family,
                report_scope=report_scope,
                resolved_specs=resolved_specs,
            )

            normalized_operands = _build_concept_required_operands(
                query,
                report_scope,
                resolved_specs,
                operation_family,
            )
            if not normalized_operands:
                continue

            metric_label = raw_metric_label or _build_concept_metric_label(
                query,
                resolved_specs,
                operation_family,
            )
            preferred_statement_types: List[str] = []
            preferred_sections: List[str] = []
            query_statement_types, query_sections = _infer_statement_and_section_hints(query)
            preferred_statement_types.extend(query_statement_types)
            preferred_sections.extend(query_sections)
            for operand in normalized_operands:
                preferred_statement_types.extend(operand.get("preferred_statement_types") or [])
                preferred_sections.extend(operand.get("preferred_sections") or [])
            preferred_statement_types = list(dict.fromkeys(item for item in preferred_statement_types if str(item).strip()))
            preferred_sections = list(dict.fromkeys(item for item in preferred_sections if str(item).strip()))
            constraints = _build_concept_task_constraints(
                query,
                report_scope,
                ontology,
                operand_specs=normalized_operands,
                operation_family=operation_family,
            )
            retrieval_queries = _build_generic_retrieval_queries(
                query=query,
                metric_label=metric_label,
                operand_specs=normalized_operands,
                preferred_sections=preferred_sections,
                report_scope=report_scope,
                constraints=constraints,
            )
            task_query = _build_metric_task_query(
                original_query=query,
                metric_label=metric_label,
                constraints=constraints,
                operand_specs=normalized_operands,
                report_scope=report_scope,
            )
            planner_tasks.append(
                {
                    "task_id": f"task_{index}",
                    "metric_family": f"concept_{operation_family}",
                    "metric_label": metric_label,
                    "query": task_query,
                    "operation_family": operation_family,
                    "result_unit": infer_concept_ratio_result_unit(query, metric_label, operation_family),
                    "required_operands": normalized_operands,
                    "preferred_statement_types": preferred_statement_types,
                    "preferred_sections": preferred_sections,
                    "retrieval_queries": retrieval_queries,
                    "constraints": constraints,
                }
            )

        if not planner_tasks:
            return None

        execution_tasks = _annotate_task_dependencies(
            planner_tasks,
            report_scope=report_scope,
        )
        planner_tasks = _project_logical_tasks_from_execution_tasks(
            planner_tasks,
            execution_tasks,
        )

        companies, years = align_scope_hints(
            companies=list(planned.companies or []),
            years=list(planned.years or []),
            report_scope=report_scope,
        )
        topic_text = _normalise_spaces(str(planned.topic or topic or query))
        section_filter = _normalise_spaces(str(planned.section_filter or "")) or None

        return {
            "status": "concept_fallback",
            "fallback_to_general_search": False,
            "companies": companies,
            "years": years,
            "topic": topic_text,
            "section_filter": section_filter,
            "planned_metric_families": [
                str(task.get("metric_family") or "").strip()
                for task in planner_tasks
                if str(task.get("metric_family") or "").strip()
            ],
            "tasks": planner_tasks,
            "planner_notes": [
                "concept_llm_planner",
                *(["planner_replan"] if replan_mode else []),
                *validation_notes,
                str(planned.rationale or "").strip(),
            ],
        }
    def _planner_task_signature(self, task: Dict[str, Any]) -> tuple:
        required_operands = tuple(
            (
                str(item.get("concept") or "").strip(),
                str(item.get("role") or "").strip(),
                str(item.get("label") or "").strip(),
            )
            for item in (task.get("required_operands") or [])
        )
        constraints = dict(task.get("constraints") or {})
        return (
            str(task.get("metric_family") or "").strip(),
            str(task.get("metric_label") or "").strip(),
            str(task.get("operation_family") or "").strip(),
            required_operands,
            str(constraints.get("consolidation_scope") or "").strip(),
            str(constraints.get("period_focus") or "").strip(),
            str(constraints.get("entity_scope") or "").strip(),
            str(constraints.get("segment_scope") or "").strip(),
        )

    def _next_planner_task_index(self, tasks: List[Dict[str, Any]]) -> int:
        max_index = 0
        for task in tasks:
            match = re.match(r"task_(\d+)$", str(task.get("task_id") or "").strip())
            if match:
                max_index = max(max_index, int(match.group(1)))
        return max_index + 1

    def _append_replanned_tasks(
        self,
        existing_tasks: List[Dict[str, Any]],
        patch_tasks: List[Dict[str, Any]],
    ) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        merged_tasks = [dict(task) for task in existing_tasks]
        accepted_patch_tasks: List[Dict[str, Any]] = []
        seen_signatures = {
            self._planner_task_signature(task)
            for task in merged_tasks
        }
        next_index = self._next_planner_task_index(merged_tasks)
        for task in patch_tasks:
            signature = self._planner_task_signature(task)
            if signature in seen_signatures:
                continue
            accepted = dict(task)
            accepted["task_id"] = f"task_{next_index}"
            next_index += 1
            merged_tasks.append(accepted)
            accepted_patch_tasks.append(accepted)
            seen_signatures.add(signature)
        return merged_tasks, accepted_patch_tasks

    def _plan_exclusive_narrative_task(
        self,
        state: FinancialAgentState,
        *,
        query: str,
        topic: str,
        intent: str,
        report_scope: Dict[str, Any],
        plan_loop_count: int,
    ) -> Dict[str, Any]:
        if not exclusive_narrative_task_policy_active(query):
            return {}
        narrative_task = build_hybrid_narrative_subtask(
            query=query,
            intent=intent,
            report_scope=report_scope,
            next_task_id="task_1",
        )
        plan = {
            "status": "narrative_policy_exclusive",
            "fallback_to_general_search": False,
            "planned_metric_families": ["narrative_summary"],
            "tasks": [narrative_task],
            "planner_notes": ["exclusive_narrative_task_policy"],
        }
        companies, years = align_scope_hints(
            companies=list(state.get("companies") or []),
            years=list(state.get("years") or []),
            report_scope=report_scope,
        )
        retrieval_queries = [query]
        retrieval_queries.extend(
            str(item).strip()
            for item in (narrative_task.get("retrieval_queries") or [])
            if str(item).strip()
        )
        retrieval_queries = list(dict.fromkeys(item for item in retrieval_queries if item))
        ledger_update = _semantic_plan_artifact_update(
            tasks=list(state.get("tasks") or []),
            artifacts=list(state.get("artifacts") or []),
            artifact_task_id=str(narrative_task.get("task_id") or "semantic_plan"),
            semantic_plan=plan,
            retrieval_queries=retrieval_queries,
            summary="planned exclusive narrative task",
            calculation_tasks=[narrative_task],
        )
        logger.info(
            "[semantic_plan] exclusive narrative policy tasks=%s retrieval_queries=%s",
            1,
            len(retrieval_queries),
        )
        return {
            "semantic_plan": plan,
            "planner_mode": "initial",
            "planner_feedback": "",
            "plan_loop_count": plan_loop_count,
            "companies": companies,
            "years": years,
            "topic": _normalise_spaces(str(topic or query)),
            "section_filter": state.get("section_filter"),
            "calc_subtasks": [narrative_task],
            "planned_metric_families": ["narrative_summary"],
            "retrieval_queries": retrieval_queries,
            "active_subtask_index": 0,
            "active_subtask": narrative_task,
            "subtask_results": [],
            "subtask_debug_trace": {
                "status": plan.get("status"),
                "task_count": 1,
                "planner_notes": list(plan.get("planner_notes") or []),
            },
            "subtask_loop_complete": False,
            "tasks": list(ledger_update["tasks"]),
            "artifacts": list(ledger_update["artifacts"]),
        }
    def _plan_semantic_numeric_tasks(self, state: FinancialAgentState) -> Dict[str, Any]:
        """Build calculation subtasks or explicitly fall back to general search.

        This is the hand-off point between generic QA and the structured
        numeric pipeline. Downstream phases treat `active_subtask` as the
        current unit of calculation work when tasks are present.
        """
        intent = state.get("intent") or state.get("query_type", "qa")
        query = state["query"]
        topic = state.get("topic") or query
        report_scope = dict(state.get("report_scope") or {})
        planner_feedback = _normalise_spaces(str(state.get("planner_feedback") or ""))
        planner_mode = "replan" if str(state.get("planner_mode") or "").strip() == "replan" or planner_feedback else "initial"
        plan_loop_count = int(state.get("plan_loop_count") or 0)
        target_metric_family = str(
            state.get("target_metric_family_hint")
            or state.get("target_metric_family")
            or ""
        )
        intent_override_note = ""
        if intent not in {"comparison", "trend", "numeric_fact"}:
            original_intent = str(intent or "qa").strip() or "qa"
            intent, intent_override_note = _non_numeric_operation_intent_override(query, topic, original_intent)
            if intent_override_note:
                logger.info(
                    "[semantic_plan] promoted intent %s -> %s via ontology numeric operation contract",
                    original_intent,
                    intent,
                )

        exclusive_narrative_plan = self._plan_exclusive_narrative_task(
            state,
            query=query,
            topic=topic,
            intent=intent,
            report_scope=report_scope,
            plan_loop_count=plan_loop_count,
        )
        if exclusive_narrative_plan:
            return exclusive_narrative_plan

        if intent not in {"comparison", "trend", "numeric_fact"}:
            return {
                "semantic_plan": {
                    "status": "fallback_general_search",
                    "fallback_to_general_search": True,
                    "planned_metric_families": [],
                    "tasks": [],
                    "planner_notes": ["non_numeric_intent"],
                },
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
                "subtask_loop_complete": False,
                "tasks": list(state.get("tasks") or []),
                "artifacts": list(state.get("artifacts") or []),
            }

        if planner_mode == "replan":
            existing_execution_tasks = [dict(task) for task in (state.get("calc_subtasks") or [])]
            existing_tasks = [
                dict(task)
                for task in (dict(state.get("semantic_plan") or {}).get("tasks") or existing_execution_tasks)
            ]
            existing_subtask_results = [dict(item) for item in (state.get("subtask_results") or [])]
            existing_plan = dict(state.get("semantic_plan") or {})
            llm_plan = self._build_llm_concept_numeric_plan(
                query=query,
                topic=topic,
                intent=intent,
                report_scope=report_scope,
                planner_feedback=planner_feedback,
                existing_tasks=existing_tasks,
                replan_mode=True,
            )
            patch_tasks = [dict(task) for task in (llm_plan or {}).get("tasks", [])]
            merged_tasks, appended_tasks = self._append_replanned_tasks(existing_tasks, patch_tasks)
            merged_tasks = append_hybrid_narrative_task(
                merged_tasks,
                query=query,
                intent=intent,
                report_scope=report_scope,
            )
            execution_tasks = _annotate_task_dependencies(
                merged_tasks,
                report_scope=report_scope,
            )
            execution_tasks = push_narrative_tasks_after_numeric(execution_tasks)
            semantic_plan_tasks = _project_logical_tasks_from_execution_tasks(
                merged_tasks,
                execution_tasks,
            )
            appended_task_ids = {
                str(task.get("task_id") or "").strip()
                for task in appended_tasks
                if str(task.get("task_id") or "").strip()
            }
            appended_execution_ids = _dependency_closure_task_ids(execution_tasks, list(appended_task_ids))
            completed_task_ids = {
                str(item.get("task_id") or "").strip()
                for item in existing_subtask_results
                if str(item.get("task_id") or "").strip()
            }
            replanned_execution_tasks = [
                dict(task)
                for task in execution_tasks
                if str(task.get("task_id") or "").strip() in appended_execution_ids
            ]
            pending_execution_tasks = [
                dict(task)
                for task in replanned_execution_tasks
                if str(task.get("task_id") or "").strip() not in completed_task_ids
            ]
            planned_metric_families = [
                str(task.get("metric_family") or "").strip()
                for task in semantic_plan_tasks
                if str(task.get("metric_family") or "").strip()
            ]
            planner_notes = list(dict.fromkeys([
                *([intent_override_note] if intent_override_note else []),
                *list(existing_plan.get("planner_notes") or []),
                "planner_replan",
                *(list((llm_plan or {}).get("planner_notes") or [])),
                *(["planner_replan_no_patch"] if not appended_tasks else []),
            ]))
            retrieval_queries = [query]
            for task in pending_execution_tasks or replanned_execution_tasks:
                retrieval_queries.extend(
                    str(item).strip()
                    for item in (task.get("retrieval_queries") or [])
                    if str(item).strip()
                )
            retrieval_queries = list(dict.fromkeys(item for item in retrieval_queries if item))
            active_subtask = dict((pending_execution_tasks or replanned_execution_tasks or [dict(state.get("active_subtask") or {})])[0])
            if pending_execution_tasks or replanned_execution_tasks:
                active_subtask_index = next(
                    (index for index, task in enumerate(execution_tasks) if str(task.get("task_id") or "") == str(active_subtask.get("task_id") or "")),
                    len(existing_execution_tasks),
                )
            else:
                active_subtask_index = int(state.get("active_subtask_index") or 0)
            plan_status = str((llm_plan or {}).get("status") or existing_plan.get("status") or "concept_fallback")
            semantic_plan = {
                "status": plan_status,
                "fallback_to_general_search": False,
                "planned_metric_families": planned_metric_families,
                "tasks": semantic_plan_tasks,
                "planner_notes": planner_notes,
            }
            companies, years = align_scope_hints(
                companies=list((llm_plan or {}).get("companies") or state.get("companies") or []),
                years=list((llm_plan or {}).get("years") or state.get("years") or []),
                report_scope=report_scope,
            )
            topic_text = _normalise_spaces(
                str((llm_plan or {}).get("topic") or state.get("topic") or query)
            )
            section_filter = (
                _normalise_spaces(str((llm_plan or {}).get("section_filter") or ""))
                or state.get("section_filter")
            )
            ledger_update = _semantic_plan_artifact_update(
                tasks=list(state.get("tasks") or []),
                artifacts=list(state.get("artifacts") or []),
                artifact_task_id=str(active_subtask.get("task_id") or "semantic_plan"),
                semantic_plan=semantic_plan,
                retrieval_queries=retrieval_queries,
                summary=f"replanned {len(appended_tasks)} additional numeric task(s)",
                payload_extra={
                    "planner_feedback": planner_feedback,
                    "base_task_count": len(existing_tasks),
                    "appended_task_count": len(appended_tasks),
                    "execution_task_count": len(execution_tasks),
                },
                calculation_tasks=list(pending_execution_tasks or replanned_execution_tasks),
            )
            logger.info(
                "[semantic_plan_replan] base_tasks=%s appended=%s retrieval_queries=%s feedback=%s",
                len(existing_tasks),
                len(replanned_execution_tasks),
                len(retrieval_queries),
                planner_feedback,
            )
            return {
                "semantic_plan": semantic_plan,
                "planner_mode": "initial",
                "planner_feedback": "",
                "plan_loop_count": plan_loop_count + 1,
                "companies": companies,
                "years": years,
                "topic": topic_text,
                "section_filter": section_filter,
                "calc_subtasks": execution_tasks,
                "planned_metric_families": planned_metric_families,
                "retrieval_queries": retrieval_queries,
                "active_subtask_index": active_subtask_index,
                "active_subtask": active_subtask,
                "subtask_results": existing_subtask_results,
                "subtask_debug_trace": {
                    **dict(state.get("subtask_debug_trace") or {}),
                    "status": plan_status,
                    "task_count": len(execution_tasks),
                    "planner_notes": planner_notes,
                    "planner_feedback": planner_feedback,
                    "planner_replan": True,
                    "appended_task_count": len(replanned_execution_tasks),
                },
                "subtask_loop_complete": False if replanned_execution_tasks else bool(state.get("subtask_loop_complete", False)),
                "planner_debug_trace": {
                    **dict(state.get("planner_debug_trace") or {}),
                    "planner_replan": True,
                    "planner_feedback": planner_feedback,
                    "base_task_count": len(existing_tasks),
                    "appended_task_count": len(replanned_execution_tasks),
                },
                "tasks": list(ledger_update["tasks"]),
                "artifacts": list(ledger_update["artifacts"]),
            }

        plan = _build_semantic_numeric_plan(
            query=query,
            topic=topic,
            intent=intent,
            report_scope=report_scope,
            target_metric_family=target_metric_family,
        )
        if str(plan.get("status") or "") in {"concept_fallback", "heuristic_fallback", "fallback_general_search"}:
            llm_plan = self._build_llm_concept_numeric_plan(
                query=query,
                topic=topic,
                intent=intent,
                report_scope=report_scope,
            )
            if llm_plan:
                if llm_plan_preserves_segment_sum_shape(plan, llm_plan) and llm_plan_preserves_analysis_shape(plan, llm_plan):
                    plan = llm_plan
                else:
                    planner_notes = list(plan.get("planner_notes") or [])
                    planner_notes.append("concept_llm_plan_rejected_shape")
                    plan["planner_notes"] = list(dict.fromkeys(planner_notes))
        if intent_override_note:
            plan["planner_notes"] = list(dict.fromkeys([intent_override_note, *list(plan.get("planner_notes") or [])]))
        logical_tasks = [dict(task) for task in (plan.get("tasks") or [])]
        logical_tasks = append_hybrid_narrative_task(
            logical_tasks,
            query=query,
            intent=intent,
            report_scope=report_scope,
        )
        tasks = _annotate_task_dependencies(
            logical_tasks,
            report_scope=report_scope,
        )
        tasks = push_narrative_tasks_after_numeric(tasks)
        plan["tasks"] = _project_logical_tasks_from_execution_tasks(logical_tasks, tasks)
        planned_metric_families = [
            str(task.get("metric_family") or "").strip()
            for task in (plan.get("tasks") or [])
            if str(task.get("metric_family") or "").strip()
        ]
        plan["planned_metric_families"] = planned_metric_families
        companies, years = align_scope_hints(
            companies=list(plan.get("companies") or state.get("companies") or []),
            years=list(plan.get("years") or state.get("years") or []),
            report_scope=report_scope,
        )
        topic_text = _normalise_spaces(str(plan.get("topic") or topic or query))
        section_filter = _normalise_spaces(str(plan.get("section_filter") or "")) or state.get("section_filter")
        retrieval_queries = [query]
        for task in tasks:
            retrieval_queries.extend(str(item).strip() for item in (task.get("retrieval_queries") or []) if str(item).strip())
        retrieval_queries = list(dict.fromkeys(item for item in retrieval_queries if item))
        active_subtask = dict(tasks[0]) if tasks else {}
        ledger_update = _semantic_plan_artifact_update(
            tasks=list(state.get("tasks") or []),
            artifacts=list(state.get("artifacts") or []),
            artifact_task_id=str(active_subtask.get("task_id") or "semantic_plan"),
            semantic_plan=plan,
            retrieval_queries=retrieval_queries,
            summary=f"planned {len(tasks)} numeric task(s)",
            calculation_tasks=list(tasks),
        )
        logger.info(
            "[semantic_plan] status=%s tasks=%s retrieval_queries=%s",
            plan.get("status"),
            len(tasks),
            len(retrieval_queries),
        )
        return {
            "semantic_plan": plan,
            "planner_mode": "initial",
            "planner_feedback": "",
            "plan_loop_count": plan_loop_count,
            "companies": companies,
            "years": years,
            "topic": topic_text,
            "section_filter": section_filter,
            "calc_subtasks": tasks,
            "planned_metric_families": planned_metric_families,
            "retrieval_queries": retrieval_queries,
            "active_subtask_index": 0,
            "active_subtask": active_subtask,
            "subtask_results": [],
            "subtask_debug_trace": {
                "status": plan.get("status"),
                "task_count": len(tasks),
                "planner_notes": list(plan.get("planner_notes") or []),
            },
            "subtask_loop_complete": False,
            "tasks": list(ledger_update["tasks"]),
            "artifacts": list(ledger_update["artifacts"]),
        }
    def _calc_query(self, state: FinancialAgentState) -> str:
        active_subtask = dict(state.get("active_subtask") or {})
        return str(active_subtask.get("query") or state["query"])

    def _calc_topic(self, state: FinancialAgentState) -> str:
        active_subtask = dict(state.get("active_subtask") or {})
        return str(
            active_subtask.get("metric_label")
            or active_subtask.get("query")
            or state.get("topic")
            or state["query"]
        )

    def _calc_metric_family(self, state: FinancialAgentState) -> str:
        active_subtask = dict(state.get("active_subtask") or {})
        return str(active_subtask.get("metric_family") or "")

    def _project_runtime_calculation_trace(self, state: FinancialAgentState) -> Dict[str, Any]:
        """Project caller-facing calculation material into the canonical runtime trace."""
        trace = _resolve_runtime_calculation_trace(dict(state))
        if trace and not trace.get("report_cache_candidate"):
            report_cache_candidate = _report_cache_candidate_for_trace(dict(state), trace)
            if report_cache_candidate:
                trace = dict(trace)
                trace["report_cache_candidate"] = report_cache_candidate
        return trace

    def _capture_current_subtask_result(self, state: FinancialAgentState) -> Dict[str, Any]:
        active_subtask = dict(state.get("active_subtask") or {})
        if not active_subtask:
            return {}
        projected = _project_task_trace_from_state(state, str(active_subtask.get("task_id") or ""))
        calculation_operands = list(projected.get("calculation_operands") or [])
        calculation_plan = dict(projected.get("calculation_plan") or {})
        calculation_result = dict(projected.get("calculation_result") or {})
        reconciliation_result = dict(projected.get("reconciliation_result") or {})
        runtime_evidence = [dict(item) for item in (state.get("evidence_items") or [])]
        answer = _normalise_spaces(str(state.get("answer") or state.get("compressed_answer") or ""))
        selected_claim_ids = list(state.get("selected_claim_ids") or [])
        status = str(
            calculation_result.get("status")
            or reconciliation_result.get("status")
            or ("ok" if answer else "unknown")
        )
        answer, status, calculation_result = promote_nested_subtask_result_if_more_specific(
            active_subtask=active_subtask,
            answer=answer,
            status=status,
            calculation_result=calculation_result,
        )
        if str(active_subtask.get("operation_family") or "").strip().lower() == "narrative_summary" and runtime_evidence:
            deterministic_dividend_answer = self._compose_dividend_policy_hybrid_answer(
                query=str(active_subtask.get("query") or state["query"]),
                evidence_items=runtime_evidence,
            )
            if deterministic_dividend_answer:
                answer = _normalise_spaces(str(deterministic_dividend_answer.get("answer") or "")) or answer
                selected_claim_ids = list(deterministic_dividend_answer.get("supporting_claim_ids") or []) or selected_claim_ids
                if answer and str(calculation_result.get("status") or "").strip().lower() in {"", "partial", "unknown"}:
                    calculation_result = {
                        **calculation_result,
                        "status": "ok",
                        "rendered_value": answer,
                        "formatted_result": answer,
                        "operation_family": "narrative_summary",
                    }
        primary_before_synthesis = dict((calculation_result.get("answer_slots") or {}).get("primary_value") or {})
        active_operation = _normalise_spaces(str(active_subtask.get("operation_family") or "")).lower()
        active_metric_family = _normalise_spaces(str(active_subtask.get("metric_family") or "")).lower()
        lookup_subtask_in_loop = active_metric_family == "concept_lookup" and len(list(state.get("calc_subtasks") or [])) > 1
        if (
            not answer_slot_has_material(primary_before_synthesis)
            and calculation_operands
            and (active_operation in {"lookup", "single_value"} or lookup_subtask_in_loop)
        ):
            matching_operands = [
                dict(operand)
                for operand in calculation_operands
                if lookup_operand_matches_active_task(dict(operand), active_subtask)
            ]
            operand_row = dict(matching_operands[0]) if matching_operands else {}
        else:
            operand_row = {}
        if operand_row:
            source_ids = _clean_source_row_ids([
                operand_row.get("source_row_id"),
                operand_row.get("source_row_ids"),
            ])
            primary_slot_from_operand = {
                "status": "ok",
                "role": "primary_value",
                "label": _normalise_spaces(
                    str(operand_row.get("label") or operand_row.get("matched_operand_label") or active_subtask.get("metric_label") or "")
                ),
                "concept": _normalise_spaces(
                    str(operand_row.get("concept") or operand_row.get("matched_operand_concept") or "")
                ),
                "period": _normalise_spaces(str(operand_row.get("period") or operand_row.get("period_hint") or "")),
                "raw_value": _normalise_spaces(str(operand_row.get("raw_value") or operand_row.get("value") or "")),
                "raw_unit": _normalise_spaces(str(operand_row.get("raw_unit") or "")),
                "normalized_value": operand_row.get("normalized_value"),
                "normalized_unit": _normalise_spaces(str(operand_row.get("normalized_unit") or "UNKNOWN")).upper()
                or "UNKNOWN",
                "rendered_value": _normalise_spaces(str(operand_row.get("rendered_value") or "")),
                "source_row_id": source_ids[0] if source_ids else "",
                "source_row_ids": list(dict.fromkeys(source_ids)),
                "source_anchor": _normalise_spaces(str(operand_row.get("source_anchor") or "")),
                "source_claim_ids": list(operand_row.get("source_claim_ids") or []),
            }
            rendered_value = _normalise_spaces(str(primary_slot_from_operand.get("rendered_value") or ""))
            calculation_result = {
                **calculation_result,
                "status": "ok",
                "operation_family": "lookup",
                "rendered_value": rendered_value,
                "formatted_result": answer or rendered_value,
                "source_row_ids": primary_slot_from_operand["source_row_ids"],
                "answer_slots": _validate_answer_slots_payload(
                    {
                        **dict(calculation_result.get("answer_slots") or {}),
                        "operation_family": "lookup",
                        "primary_value": primary_slot_from_operand,
                    }
                ),
            }
            primary_before_synthesis = primary_slot_from_operand
        if (
            not answer_slot_has_material(primary_before_synthesis)
            and (not calculation_operands or not operand_row)
            and (active_operation in {"lookup", "single_value"} or lookup_subtask_in_loop)
        ):
            calculation_result = synthesize_lookup_answer_slot_from_prose(
                active_subtask=active_subtask,
                answer=answer,
                calculation_result=calculation_result,
                selected_claim_ids=selected_claim_ids,
            )
        primary_slot = dict((calculation_result.get("answer_slots") or {}).get("primary_value") or {})
        if primary_slot and answer_slot_has_material(primary_slot):
            primary_source_ids = set(_clean_source_row_ids([
                primary_slot.get("source_row_id"),
                primary_slot.get("source_row_ids"),
            ]))
            slot_evidence = next(
                (
                    dict(item)
                    for item in runtime_evidence
                    if str(item.get("evidence_id") or "").strip() in primary_source_ids
                ),
                None,
            )
            if not slot_evidence:
                slot_evidence = lookup_slot_supporting_doc_evidence(
                active_subtask=active_subtask,
                slot=primary_slot,
                docs=list(state.get("retrieved_docs", []) or []) + list(state.get("seed_retrieved_docs", []) or []),
                )
            if slot_evidence:
                evidence_id = str(slot_evidence.get("evidence_id") or "").strip()
                existing_ids = {
                    str(item.get("evidence_id") or "").strip()
                    for item in runtime_evidence
                    if isinstance(item, dict)
                }
                if evidence_id:
                    slot_source_ids = _clean_source_row_ids([
                        primary_slot.get("source_row_id"),
                        primary_slot.get("source_row_ids"),
                        evidence_id,
                    ])
                    primary_slot["source_row_id"] = slot_source_ids[0] if slot_source_ids else evidence_id
                    primary_slot["source_row_ids"] = slot_source_ids or [evidence_id]
                    if not _normalise_spaces(str(primary_slot.get("source_anchor") or "")):
                        primary_slot["source_anchor"] = _normalise_spaces(str(slot_evidence.get("source_anchor") or ""))
                    primary_slot = refine_lookup_slot_unit_from_evidence(primary_slot, slot_evidence)
                    primary_slot = coerce_lookup_magnitude_record(primary_slot, slot_evidence)
                    if calculation_operands:
                        refined_operands: List[Dict[str, Any]] = []
                        primary_ids = set(_clean_source_row_ids([primary_slot.get("source_row_ids")]))
                        for operand in calculation_operands:
                            operand_row = dict(operand)
                            operand_ids = set(_clean_source_row_ids([
                                operand_row.get("source_row_id"),
                                operand_row.get("source_row_ids"),
                            ]))
                            if (
                                _normalise_spaces(str(operand_row.get("raw_value") or ""))
                                == _normalise_spaces(str(primary_slot.get("raw_value") or ""))
                                and (not primary_ids or not operand_ids or bool(primary_ids & operand_ids))
                            ):
                                operand_row["raw_unit"] = _normalise_spaces(str(primary_slot.get("raw_unit") or ""))
                                operand_row["normalized_value"] = primary_slot.get("normalized_value")
                                operand_row["normalized_unit"] = _normalise_spaces(
                                    str(primary_slot.get("normalized_unit") or "UNKNOWN")
                                ).upper()
                                operand_row["rendered_value"] = _normalise_spaces(
                                    str(primary_slot.get("rendered_value") or "")
                                )
                                if not _normalise_spaces(str(operand_row.get("source_anchor") or "")):
                                    operand_row["source_anchor"] = _normalise_spaces(str(primary_slot.get("source_anchor") or ""))
                            refined_operands.append(operand_row)
                        calculation_operands = refined_operands
                    if evidence_id not in existing_ids:
                        runtime_evidence.append(slot_evidence)
                    if evidence_id not in selected_claim_ids:
                        selected_claim_ids.append(evidence_id)
                calculation_result["answer_slots"]["primary_value"] = primary_slot
                calculation_result["source_row_ids"] = list(primary_slot.get("source_row_ids") or [])
                if primary_slot.get("rendered_value"):
                    calculation_result["rendered_value"] = _normalise_spaces(str(primary_slot.get("rendered_value") or ""))
        if primary_slot and not calculation_operands:
            calculation_operands = [
                {
                    "operand_id": _normalise_spaces(str(primary_slot.get("role") or "primary_value")) or "primary_value",
                    "matched_operand_role": _normalise_spaces(str(primary_slot.get("role") or "primary_value")) or "primary_value",
                    "label": _normalise_spaces(str(primary_slot.get("label") or active_subtask.get("metric_label") or "")),
                    "concept": _normalise_spaces(str(primary_slot.get("concept") or active_subtask.get("metric_family") or "")),
                    "period": _normalise_spaces(str(primary_slot.get("period") or "")),
                    "raw_value": _normalise_spaces(str(primary_slot.get("raw_value") or "")),
                    "raw_unit": _normalise_spaces(str(primary_slot.get("raw_unit") or "")),
                    "normalized_value": primary_slot.get("normalized_value"),
                    "normalized_unit": _normalise_spaces(str(primary_slot.get("normalized_unit") or "UNKNOWN")),
                    "rendered_value": _normalise_spaces(str(primary_slot.get("rendered_value") or "")),
                    "source_row_id": _normalise_spaces(str(primary_slot.get("source_row_id") or "")),
                    "source_row_ids": _clean_source_row_ids([primary_slot.get("source_row_ids")]),
                    "source_anchor": _normalise_spaces(str(primary_slot.get("source_anchor") or "")),
                    "source_claim_ids": list(primary_slot.get("source_claim_ids") or []),
                }
            ]
        if hasattr(self, "_repair_stale_calculation_result_from_operands"):
            stale_repair = self._repair_stale_calculation_result_from_operands(
                state,
                operands=[dict(item) for item in calculation_operands if isinstance(item, dict)],
                plan=calculation_plan,
                calculation_result=calculation_result,
            )
            calculation_operands = stale_repair.calculation_operands
            calculation_plan = stale_repair.calculation_plan
            calculation_result = stale_repair.calculation_result
            if stale_repair.repair_applied:
                selected_claim_ids = list(stale_repair.selected_evidence_ids)
                repaired_answer = _normalise_spaces(
                    str(calculation_result.get("formatted_result") or calculation_result.get("rendered_value") or "")
                )
                if repaired_answer:
                    answer = repaired_answer
        status = str(
            calculation_result.get("status")
            or reconciliation_result.get("status")
            or status
            or ("ok" if answer else "unknown")
        )
        return {
            "task_id": str(active_subtask.get("task_id") or ""),
            "metric_family": str(active_subtask.get("metric_family") or ""),
            "metric_label": str(active_subtask.get("metric_label") or ""),
            "query": str(active_subtask.get("query") or state["query"]),
            "answer": answer,
            "status": status,
            "artifact_ids": list(projected.get("artifact_ids") or []),
            "selected_claim_ids": selected_claim_ids,
            "runtime_evidence": runtime_evidence,
            "calculation_operands": calculation_operands,
            "calculation_plan": calculation_plan,
            "calculation_result": calculation_result,
            "reconciliation_result": reconciliation_result,
        }
