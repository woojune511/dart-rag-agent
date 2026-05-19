"""
Planning mixin for the financial graph agent.

This module owns the "front" of the graph:
- classify the query
- extract entity and metric hints
- translate the query into numeric subtasks when possible
- project ledger state back into the legacy flat result shape
"""

import json
import logging
import re
from typing import Any, Dict, List, Optional

from langchain_core.prompts import ChatPromptTemplate
from src.agent.financial_graph_helpers import *  # noqa: F401,F403
from src.agent.financial_graph_models import (
    ConceptPlannerOutput,
    EntityExtraction,
    FinancialAgentState,
    validate_answer_slots_payload,
)
from src.config import get_financial_ontology
from src.routing import default_format_preference
from src.schema import ArtifactKind, TaskKind, TaskStatus

logger = logging.getLogger(__name__)

class FinancialAgentPlanningMixin:
    def _default_format_preference(self, intent: str) -> str:
        return default_format_preference(intent)

    def _align_scope_hints(
        self,
        *,
        companies: Optional[List[str]],
        years: Optional[List[int]],
        report_scope: Dict[str, Any],
    ) -> tuple[List[str], List[int]]:
        scope_company = str(report_scope.get("company") or "").strip()
        scope_year_raw = report_scope.get("year")
        scope_year: Optional[int] = None
        try:
            if scope_year_raw not in (None, ""):
                scope_year = int(scope_year_raw)
        except (TypeError, ValueError):
            scope_year = None

        normalized_companies = [str(item).strip() for item in (companies or []) if str(item).strip()]
        normalized_years: List[int] = []
        for item in list(years or []):
            try:
                value = int(item)
            except (TypeError, ValueError):
                continue
            if value not in normalized_years:
                normalized_years.append(value)

        if scope_company:
            if not normalized_companies:
                normalized_companies = [scope_company]
            elif scope_company not in normalized_companies:
                normalized_companies = [scope_company, *normalized_companies]

        if scope_year is not None:
            if not normalized_years:
                normalized_years = [scope_year]
            elif scope_year not in normalized_years:
                normalized_years = [scope_year, *normalized_years]

        return normalized_companies, normalized_years

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
        companies, years = self._align_scope_hints(companies=[], years=years, report_scope=report_scope)
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
        if not concept_specs:
            concept_specs = ontology.all_concept_specs()
        if not concept_specs:
            return None
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
            "- 현재는 replan mode입니다. planner_feedback를 읽고, 기존 task는 유지한 채 누락된 재료를 찾기 위한 추가 task만 만드세요.\n"
            "- 기존 task와 실질적으로 같은 task를 다시 만들지 마세요.\n"
            "- planner_feedback가 이미 확보된 기존 task로 해결된다면 tasks를 비워 둘 수 있습니다."
            if replan_mode
            else "- 현재는 initial mode입니다. 원본 질문을 풀기 위한 전체 재료 수집 계획을 세우세요."
        )
        prompt = ChatPromptTemplate.from_template(
            """당신은 DART 재무 질문 planner입니다.
질문을 직접 답하지 말고, 아래 ontology concept만 사용해서 계산 계획으로 바꾸세요.

허용 operation_family:
{allowed_operations}

role 규칙:
- ratio: numerator_1, numerator_2, ... / denominator_1, denominator_2, ...
- sum: addend_1, addend_2, ...
- difference: minuend, subtrahend 또는 current_period, prior_period
- growth_rate: current_period, prior_period
- lookup/single_value: role은 비워도 됨

planner_guidance.intent_cues:
{intent_cues}

available concepts:
{concept_catalog}

현재 planning mode:
{planning_mode}

현재 planner_feedback:
{planner_feedback}

기존 task 요약:
{existing_tasks}

중요 규칙:
- ontology에 [group]으로 표시된 concept는 축약 표현입니다. planner는 group을 그대로 쓰거나, 그 group이 expands_to로 가리키는 atomic concept 전부를 써도 됩니다.
- 다만 최종 task는 질문에 필요한 모든 atomic 의미를 빠뜨리지 않아야 합니다. 예를 들어 "유·무형자산"이면 유형자산과 무형자산이 모두 포함되어야 합니다.
- 질문이 여러 지표를 "각각" 계산하라고 하면 tasks를 여러 개로 나누세요.
- planner의 목적은 최종 문장을 줄이는 것이 아니라, 질문에 답하는 데 필요한 재료(raw value, period pair, derived metric)를 빠짐없이 확보하는 것입니다.
- 사용자가 특정 연도/기간의 값을 "추출", "제시", "보여", "알려" 달라고 했으면 그 raw value를 위한 lookup task를 만드세요.
- 사용자가 raw value와 파생 계산(증감액, 증가율, 비율 등)을 함께 요구하면, lookup task와 calculation task를 모두 만들어도 됩니다.
- difference 또는 growth_rate task는 계산 재료를 모으는 역할이지, 그 task 하나가 최종 답변의 모든 노출 요구를 대신한다고 가정하지 마세요.
- lookup은 단일 값 조회나, 다른 계산 task와 별도로 원문 질문이 직접 요구한 raw 값을 확보할 때 사용하세요.
- benchmark ?????metric family??? ????? ???, operation??concept ?????? ?????
- ????/?????/?????????(SDC, Harman ??? ???)??company???????? ???????? report_scope???????companies?????? ?????????? segment ?????? ????????
- ??? concept????? ????/????????? ??????????lookup task ??? ??? ????? ???, ?????sum task ??? ??? concept addend????? ??(addend_1, addend_2, ...) ????????
- concept는 available concepts 안의 key만 써야 합니다.
- 질문에 명시되지 않은 company/year는 report_scope 기본값을 따른다고 가정하세요.
{mode_specific_rules}

few-shot 예시 1:
질문: 2023년 연결기준 부채비율을 계산해 줘.
출력:
tasks = [
  {{ metric_label: "부채비율", operation_family: "ratio", operands: [
    {{ concept: "total_liabilities", role: "numerator_1" }},
    {{ concept: "total_equity", role: "denominator_1" }}
  ]}}
]

few-shot 예시 2:
질문: 2023년 연결기준 부채비율과 유동비율을 각각 계산해 줘.
출력:
tasks = [
  {{ metric_label: "부채비율", operation_family: "ratio", operands: [
    {{ concept: "total_liabilities", role: "numerator_1" }},
    {{ concept: "total_equity", role: "denominator_1" }}
  ]}},
  {{ metric_label: "유동비율", operation_family: "ratio", operands: [
    {{ concept: "current_assets", role: "numerator_1" }},
    {{ concept: "current_liabilities", role: "denominator_1" }}
  ]}}
]

few-shot 예시 3:
질문: 2023년 연결 재무상태표에서 유·무형자산의 총합 대비 차입금의 비중을 계산해 줘.
출력:
tasks = [
  {{ metric_label: "유·무형자산 대비 차입금 비중", operation_family: "ratio", operands: [
    {{ concept: "short_term_borrowings", role: "numerator_1" }},
    {{ concept: "long_term_borrowings", role: "numerator_2" }},
    {{ concept: "bonds_payable", role: "numerator_3" }},
    {{ concept: "property_plant_equipment", role: "denominator_1" }},
    {{ concept: "intangible_assets", role: "denominator_2" }}
  ]}}
]

few-shot 예시 4:
질문: 2023년 연결 손익계산서에서 법인세비용차감전순이익을 추출하고, 전년 대비 증감액을 계산해 줘.
출력:
tasks = [
  {{ metric_label: "2023년 법인세비용차감전순이익", operation_family: "lookup", operands: [
    {{ concept: "income_before_income_taxes", role: "current_period" }}
  ]}},
  {{ metric_label: "법인세비용차감전순이익 증감액", operation_family: "difference", operands: [
    {{ concept: "income_before_income_taxes", role: "current_period" }},
    {{ concept: "income_before_income_taxes", role: "prior_period" }}
  ]}}
]
설명:
- 원문 질문이 2023년 raw value와 전년 대비 증감액을 모두 요구하므로, raw value lookup과 difference 계산 재료를 모두 확보합니다.

질문:
{query}

topic:
{topic}

intent:
{intent}

report_scope:
{report_scope}

Also return:
- companies: normalized company list for this question
- years: normalized relevant years
- topic: a concise topic string for retrieval/ranking
- section_filter: a single best section hint when one section is strongly dominant, otherwise null
"""
        )
        structured_llm = self.llm.with_structured_output(ConceptPlannerOutput)
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
            is_valid, note = self._validate_concept_planner_task(raw_task, ontology)
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

            normalized_operands = _build_concept_required_operands(
                query,
                report_scope,
                resolved_specs,
                operation_family,
            )
            if not normalized_operands:
                continue

            metric_label = str(raw_task.metric_label or "").strip() or _build_concept_metric_label(
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
                    "required_operands": normalized_operands,
                    "preferred_statement_types": preferred_statement_types,
                    "preferred_sections": preferred_sections,
                    "retrieval_queries": retrieval_queries,
                    "constraints": constraints,
                }
            )

        if not planner_tasks:
            return None

        companies, years = self._align_scope_hints(
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

    def _validate_concept_planner_task(self, raw_task: Any, ontology: Any) -> tuple[bool, str]:
        """Perform a tiny contract check on planner output before runtime uses it.

        This is intentionally narrow: it validates shape and ontology membership,
        not financial correctness.
        """
        operation_family = str(getattr(raw_task, "operation_family", "") or "").strip().lower()
        allowed_operations = {"lookup", "sum", "difference", "ratio", "growth_rate", "single_value"}
        if operation_family not in allowed_operations:
            return False, f"unsupported_operation:{operation_family or '-'}"

        raw_operands = list(getattr(raw_task, "operands", []) or [])
        if not raw_operands:
            return False, "missing_operands"

        roles = [str(getattr(item, "role", "") or "").strip() for item in raw_operands]
        for item in raw_operands:
            concept_key = str(getattr(item, "concept", "") or "").strip()
            if not concept_key or not ontology.has_concept_key(concept_key):
                return False, f"unknown_concept:{concept_key or '-'}"

        if operation_family == "ratio":
            if not any(role.startswith("numerator") for role in roles):
                return False, "ratio_missing_numerator"
            if not any(role.startswith("denominator") for role in roles):
                return False, "ratio_missing_denominator"
            invalid_role = next(
                (role for role in roles if role and not (role.startswith("numerator") or role.startswith("denominator"))),
                "",
            )
            if invalid_role:
                return False, f"ratio_invalid_role:{invalid_role}"
        elif operation_family == "sum":
            invalid_role = next((role for role in roles if role and not role.startswith("addend")), "")
            if invalid_role:
                return False, f"sum_invalid_role:{invalid_role}"
        elif operation_family == "difference":
            if len(raw_operands) != 2:
                return False, "difference_requires_two_operands"
            valid_roles = {"", "minuend", "subtrahend", "current_period", "prior_period"}
            invalid_role = next((role for role in roles if role not in valid_roles), "")
            if invalid_role:
                return False, f"difference_invalid_role:{invalid_role}"
        elif operation_family == "growth_rate":
            if len(raw_operands) != 2:
                return False, "growth_rate_requires_two_operands"
            valid_roles = {"", "current_period", "prior_period"}
            invalid_role = next((role for role in roles if role not in valid_roles), "")
            if invalid_role:
                return False, f"growth_rate_invalid_role:{invalid_role}"

        return True, "ok"

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
            existing_tasks = [dict(task) for task in (state.get("calc_subtasks") or [])]
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
            planned_metric_families = [
                str(task.get("metric_family") or "").strip()
                for task in merged_tasks
                if str(task.get("metric_family") or "").strip()
            ]
            planner_notes = list(dict.fromkeys([
                *list(existing_plan.get("planner_notes") or []),
                "planner_replan",
                *(list((llm_plan or {}).get("planner_notes") or [])),
                *(["planner_replan_no_patch"] if not appended_tasks else []),
            ]))
            retrieval_queries = [query]
            for task in appended_tasks:
                retrieval_queries.extend(
                    str(item).strip()
                    for item in (task.get("retrieval_queries") or [])
                    if str(item).strip()
                )
            retrieval_queries = list(dict.fromkeys(item for item in retrieval_queries if item))
            active_subtask = dict(appended_tasks[0]) if appended_tasks else dict(state.get("active_subtask") or {})
            if appended_tasks:
                active_subtask_index = next(
                    (index for index, task in enumerate(merged_tasks) if str(task.get("task_id") or "") == str(active_subtask.get("task_id") or "")),
                    len(existing_tasks),
                )
            else:
                active_subtask_index = int(state.get("active_subtask_index") or 0)
            plan_status = str((llm_plan or {}).get("status") or existing_plan.get("status") or "concept_fallback")
            semantic_plan = {
                "status": plan_status,
                "fallback_to_general_search": False,
                "planned_metric_families": planned_metric_families,
                "tasks": merged_tasks,
                "planner_notes": planner_notes,
            }
            companies, years = self._align_scope_hints(
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
            task_records = list(state.get("tasks") or [])
            artifacts = list(state.get("artifacts") or [])
            semantic_artifact_id = f"semantic_plan:{len(artifacts) + 1:03d}"
            artifacts = _append_artifact(
                artifacts,
                artifact_id=semantic_artifact_id,
                task_id=str(active_subtask.get("task_id") or "semantic_plan"),
                kind=ArtifactKind.SEMANTIC_PLAN,
                status=plan_status,
                summary=f"replanned {len(appended_tasks)} additional numeric task(s)",
                payload={
                    "semantic_plan": semantic_plan,
                    "retrieval_queries": retrieval_queries,
                    "planner_feedback": planner_feedback,
                    "base_task_count": len(existing_tasks),
                    "appended_task_count": len(appended_tasks),
                },
            )
            for task in appended_tasks:
                task_records = _upsert_task(
                    task_records,
                    task_id=str(task.get("task_id") or ""),
                    kind=TaskKind.CALCULATION,
                    label=str(task.get("metric_label") or task.get("metric_family") or "calculation"),
                    status=TaskStatus.PENDING,
                    query=str(task.get("query") or ""),
                    metric_family=str(task.get("metric_family") or ""),
                    constraints=dict(task.get("constraints") or {}),
                    artifact_id=semantic_artifact_id,
                )
            logger.info(
                "[semantic_plan_replan] base_tasks=%s appended=%s retrieval_queries=%s feedback=%s",
                len(existing_tasks),
                len(appended_tasks),
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
                "calc_subtasks": merged_tasks,
                "planned_metric_families": planned_metric_families,
                "retrieval_queries": retrieval_queries,
                "active_subtask_index": active_subtask_index,
                "active_subtask": active_subtask,
                "subtask_results": existing_subtask_results,
                "subtask_debug_trace": {
                    **dict(state.get("subtask_debug_trace") or {}),
                    "status": plan_status,
                    "task_count": len(merged_tasks),
                    "planner_notes": planner_notes,
                    "planner_feedback": planner_feedback,
                    "planner_replan": True,
                    "appended_task_count": len(appended_tasks),
                },
                "subtask_loop_complete": False if appended_tasks else bool(state.get("subtask_loop_complete", False)),
                "planner_debug_trace": {
                    **dict(state.get("planner_debug_trace") or {}),
                    "planner_replan": True,
                    "planner_feedback": planner_feedback,
                    "base_task_count": len(existing_tasks),
                    "appended_task_count": len(appended_tasks),
                },
                "tasks": task_records,
                "artifacts": artifacts,
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
                plan = llm_plan
        tasks = list(plan.get("tasks") or [])
        planned_metric_families = [
            str(task.get("metric_family") or "").strip()
            for task in tasks
            if str(task.get("metric_family") or "").strip()
        ]
        plan["planned_metric_families"] = planned_metric_families
        companies, years = self._align_scope_hints(
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
        task_records = list(state.get("tasks") or [])
        artifacts = list(state.get("artifacts") or [])
        semantic_artifact_id = f"semantic_plan:{len(artifacts) + 1:03d}"
        artifacts = _append_artifact(
            artifacts,
            artifact_id=semantic_artifact_id,
            task_id=str(active_subtask.get("task_id") or "semantic_plan"),
            kind=ArtifactKind.SEMANTIC_PLAN,
            status=str(plan.get("status") or "ok"),
            summary=f"planned {len(tasks)} numeric task(s)",
            payload={"semantic_plan": plan, "retrieval_queries": retrieval_queries},
        )
        for task in tasks:
            task_records = _upsert_task(
                task_records,
                task_id=str(task.get("task_id") or ""),
                kind=TaskKind.CALCULATION,
                label=str(task.get("metric_label") or task.get("metric_family") or "calculation"),
                status=TaskStatus.PENDING,
                query=str(task.get("query") or ""),
                metric_family=str(task.get("metric_family") or ""),
                constraints=dict(task.get("constraints") or {}),
                artifact_id=semantic_artifact_id,
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
            "tasks": task_records,
            "artifacts": artifacts,
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

    def _build_aggregate_calculation_projection(
        self,
        ordered_results: List[Dict[str, Any]],
        final_answer: str,
    ) -> Dict[str, Any]:
        aggregate_projection = _build_aggregate_calculation_projection(ordered_results, final_answer)
        aggregate_evidence: List[Dict[str, Any]] = []
        seen_evidence_ids: set[str] = set()

        for row in ordered_results:
            for evidence in list(row.get("runtime_evidence") or []):
                evidence_row = dict(evidence)
                evidence_id = str(evidence_row.get("evidence_id") or "").strip()
                dedupe_key = evidence_id or _normalise_spaces(
                    " ".join(
                        part
                        for part in [
                            str(evidence_row.get("source_anchor") or "").strip(),
                            str(evidence_row.get("quote_span") or "").strip(),
                            str(evidence_row.get("raw_row_text") or "").strip(),
                            str(evidence_row.get("claim") or "").strip(),
                        ]
                        if part
                    )
                )
                if dedupe_key and dedupe_key in seen_evidence_ids:
                    continue
                if dedupe_key:
                    seen_evidence_ids.add(dedupe_key)
                aggregate_evidence.append(evidence_row)
        return {
            "calculation_operands": aggregate_projection["calculation_operands"],
            "calculation_plan": aggregate_projection["calculation_plan"],
            "calculation_result": aggregate_projection["calculation_result"],
            "evidence_items": aggregate_evidence,
        }

    def _project_legacy_calculation_fields(self, state: FinancialAgentState) -> Dict[str, Any]:
        """Project ledger-backed traces into the legacy flat calculation view."""
        return _resolve_runtime_calculation_trace(dict(state))

    def _capture_current_subtask_result(self, state: FinancialAgentState) -> Dict[str, Any]:
        active_subtask = dict(state.get("active_subtask") or {})
        if not active_subtask:
            return {}
        projected = _project_task_trace_from_state(state, str(active_subtask.get("task_id") or ""))
        calculation_operands = list(projected.get("calculation_operands") or [])
        calculation_plan = dict(projected.get("calculation_plan") or {})
        calculation_result = dict(projected.get("calculation_result") or {})
        reconciliation_result = dict(projected.get("reconciliation_result") or {})
        answer = _normalise_spaces(str(state.get("answer") or state.get("compressed_answer") or ""))
        status = str(
            calculation_result.get("status")
            or reconciliation_result.get("status")
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
            "selected_claim_ids": list(state.get("selected_claim_ids") or []),
            "runtime_evidence": [dict(item) for item in (state.get("evidence_items") or [])],
            "calculation_operands": calculation_operands,
            "calculation_plan": calculation_plan,
            "calculation_result": calculation_result,
            "reconciliation_result": reconciliation_result,
        }

    def _upsert_subtask_result(
        self,
        existing: List[Dict[str, Any]],
        current: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        if not current:
            return list(existing or [])
        current_task_id = str(current.get("task_id") or "").strip()
        rows: List[Dict[str, Any]] = []
        replaced = False
        for row in existing or []:
            row_task_id = str(row.get("task_id") or "").strip()
            if current_task_id and row_task_id == current_task_id:
                rows.append(current)
                replaced = True
            else:
                rows.append(row)
        if not replaced:
            rows.append(current)
        return rows

