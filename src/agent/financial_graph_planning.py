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
from src.agent.financial_graph_helpers import _extract_segment_labels_from_query, _infer_concept_ratio_result_unit
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


def _is_narrative_summary_task(task: Dict[str, Any]) -> bool:
    operation_family = _normalise_spaces(str(task.get("operation_family") or "")).lower()
    metric_family = _normalise_spaces(str(task.get("metric_family") or "")).lower()
    return operation_family == "narrative_summary" or metric_family == "narrative_summary"


def _needs_hybrid_narrative_subtask(query: str, intent: str) -> bool:
    return intent in {"comparison", "trend", "numeric_fact"} and _query_requests_narrative_context(query)


def _build_hybrid_narrative_subtask(
    *,
    query: str,
    report_scope: Dict[str, Any],
    next_task_id: str,
) -> Dict[str, Any]:
    consolidation_scope = _desired_consolidation_scope(query, report_scope)
    period_focus = _infer_period_focus(query, "unknown")
    retrieval_queries = [
        _normalise_spaces(query),
        _normalise_spaces(f"{query} 원인 배경 영향 설명"),
        _normalise_spaces(f"{query} 경영진단 사업의 내용"),
    ]
    normalized_query = _normalise_spaces(query)
    if "인수" in query or "영향" in query:
        retrieval_queries.append(_normalise_spaces(f"{query} 연결 편입 효과 성장 기여"))
        retrieval_queries.append(_normalise_spaces(f"{query} 연결 편입효과 영업수익 증가"))
    if "포시마크" in query or "Poshmark" in query:
        retrieval_queries.append(_normalise_spaces(f"{query} Poshmark 연결 편입효과 영업수익 증가"))
    if any(token in normalized_query for token in ("배당", "주주환원", "정규배당", "잉여현금흐름", "환원 정책")):
        retrieval_queries.append(_normalise_spaces(f"{query} 배당에 관한 사항 주주환원 정책"))
        retrieval_queries.append(_normalise_spaces(f"{query} 잉여현금흐름 정규배당 추가 환원"))
        retrieval_queries.append(_normalise_spaces(f"{query} 유동성 및 자금조달 배당금 지급"))
    preferred_sections = [
        "IV. 이사의 경영진단 및 분석의견",
        "II. 사업의 내용",
        "사업의 개요",
        "나. 영업실적",
    ]
    if any(token in normalized_query for token in ("배당", "주주환원", "정규배당", "잉여현금흐름", "환원 정책")):
        preferred_sections = [
            "III. 재무에 관한 사항 > 6. 배당에 관한 사항",
            "IV. 이사의 경영진단 및 분석의견 > 유동성 및 자금조달",
            *preferred_sections,
        ]
    return {
        "task_id": next_task_id,
        "metric_family": "narrative_summary",
        "metric_label": "질문 관련 배경/영향 설명",
        "query": query,
        "operation_family": "narrative_summary",
        "required_operands": [],
        "preferred_statement_types": [],
        "preferred_sections": preferred_sections,
        "retrieval_queries": list(dict.fromkeys(item for item in retrieval_queries if item)),
        "constraints": {
            "consolidation_scope": consolidation_scope,
            "period_focus": period_focus,
            "entity_scope": "unknown",
            "segment_scope": "none",
            "context_scope": "narrative",
        },
        "intent_override": "qa",
        "format_preference_override": "paragraph",
    }


def _append_hybrid_narrative_task(
    tasks: List[Dict[str, Any]],
    *,
    query: str,
    intent: str,
    report_scope: Dict[str, Any],
) -> List[Dict[str, Any]]:
    base_tasks = [dict(task) for task in (tasks or [])]
    if not _needs_hybrid_narrative_subtask(query, intent):
        return base_tasks
    if any(_is_narrative_summary_task(task) for task in base_tasks):
        return base_tasks
    next_index = 1
    if base_tasks:
        next_index = max(
            1,
            max(
                (
                    int(match.group(1))
                    for match in (
                        re.match(r"task_(\d+)$", str(task.get("task_id") or "").strip())
                        for task in base_tasks
                    )
                    if match
                ),
                default=0,
            )
            + 1,
        )
    base_tasks.append(
        _build_hybrid_narrative_subtask(
            query=query,
            report_scope=report_scope,
            next_task_id=f"task_{next_index}",
        )
    )
    return base_tasks


def _push_narrative_tasks_after_numeric(tasks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    ordered = [dict(task) for task in (tasks or [])]
    numeric_task_ids = [
        str(task.get("task_id") or "").strip()
        for task in ordered
        if not _is_narrative_summary_task(task) and str(task.get("task_id") or "").strip()
    ]
    if not numeric_task_ids:
        return ordered

    changed = False
    for task in ordered:
        if not _is_narrative_summary_task(task):
            continue
        task_id = str(task.get("task_id") or "").strip()
        dependencies = [
            _normalise_spaces(str(item or ""))
            for item in (task.get("depends_on") or [])
            if _normalise_spaces(str(item or ""))
        ]
        for dependency_id in numeric_task_ids:
            if dependency_id == task_id or dependency_id in dependencies:
                continue
            dependencies.append(dependency_id)
            changed = True
        task["depends_on"] = dependencies
    if not changed:
        return ordered
    numeric_tasks = [task for task in ordered if not _is_narrative_summary_task(task)]
    narrative_tasks = [task for task in ordered if _is_narrative_summary_task(task)]
    return numeric_tasks + narrative_tasks

def _llm_plan_preserves_segment_sum_shape(base_plan: Dict[str, Any], llm_plan: Dict[str, Any]) -> bool:
    """Reject LLM overrides that destroy deterministic segment-sum structure."""
    base_tasks = [dict(task) for task in (base_plan.get("tasks") or [])]
    has_segment_sum = any(
        str(task.get("operation_family") or "").strip().lower() == "sum"
        and str((task.get("constraints") or {}).get("segment_scope") or "none").strip().lower() == "segment"
        for task in base_tasks
    )
    if not has_segment_sum:
        return True

    llm_tasks = [dict(task) for task in (llm_plan.get("tasks") or [])]
    for task in llm_tasks:
        if str(task.get("operation_family") or "").strip().lower() != "sum":
            continue
        if str((task.get("constraints") or {}).get("segment_scope") or "none").strip().lower() != "segment":
            continue
        addend_roles = [
            str(item.get("role") or "").strip()
            for item in (task.get("required_operands") or [])
            if str(item.get("role") or "").strip().startswith("addend_")
        ]
        if len(addend_roles) >= 2:
            return True
    return False


def _attach_segment_label_to_resolved_spec(spec: Dict[str, Any], segment_label: str) -> Dict[str, Any]:
    updated = dict(spec)
    base_name = str(updated.get("name") or "").strip() or "매출액"
    updated["name"] = f"{segment_label} {base_name}".strip()
    aliases = list(updated.get("aliases") or [])
    updated["aliases"] = list(dict.fromkeys([updated["name"], segment_label, base_name, *aliases]))
    binding_policy = dict(updated.get("binding_policy") or {})
    binding_policy["segment_label"] = segment_label
    updated["binding_policy"] = binding_policy
    return updated


def _apply_segment_labels_to_llm_resolved_specs(
    *,
    query: str,
    metric_label: str,
    operation_family: str,
    report_scope: Dict[str, Any],
    resolved_specs: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Recover segment-scoped operand identity when the LLM only emits repeated concepts.

    The structured planner often emits `revenue` twice for queries like
    "SDC와 Harman 부문의 매출 합계". We keep the operation-family/role signal from
    the LLM, but re-attach segment labels from the original query/metric label so
    downstream grounding can distinguish SDC from Harman instead of binding the
    same company-total row twice.
    """
    specs = [dict(spec) for spec in (resolved_specs or [])]
    if not specs:
        return specs

    segment_labels = _extract_segment_labels_from_query(query, report_scope)
    if not segment_labels:
        return specs

    metric_label_text = _normalise_spaces(metric_label)
    segment_labels_lower = [_normalise_spaces(label).lower() for label in segment_labels]

    repeated_same_concept = len({
        str(spec.get("concept") or "").strip()
        for spec in specs
        if str(spec.get("concept") or "").strip()
    }) == 1

    if operation_family in {"sum", "difference", "growth_rate"}:
        roles = [str(spec.get("role") or "").strip() for spec in specs]
        expected_role_prefix = "addend_" if operation_family == "sum" else ""
        valid_difference_roles = {"minuend", "subtrahend"}
        valid_growth_roles = {"current_period", "prior_period"}
        role_shape_ok = (
            all(role.startswith(expected_role_prefix) for role in roles)
            if operation_family == "sum"
            else (
                valid_difference_roles.issubset(set(roles))
                if operation_family == "difference"
                else valid_growth_roles.issubset(set(roles))
            )
        )
        required_segment_labels = 2 if operation_family in {"sum", "difference"} else 1
        if repeated_same_concept and len(specs) >= 2 and role_shape_ok and len(segment_labels) >= required_segment_labels:
            if operation_family == "growth_rate":
                for index, spec in enumerate(specs):
                    specs[index] = _attach_segment_label_to_resolved_spec(spec, segment_labels[0])
            else:
                for index, spec in enumerate(specs):
                    if index >= len(segment_labels):
                        break
                    specs[index] = _attach_segment_label_to_resolved_spec(spec, segment_labels[index])
            return specs

    if operation_family == "ratio" and repeated_same_concept and len(specs) >= 2 and segment_labels:
        for index, spec in enumerate(specs):
            role = str(spec.get("role") or "").strip()
            if not role.startswith("numerator"):
                continue
            specs[index] = _attach_segment_label_to_resolved_spec(spec, segment_labels[0])
            break
        return specs

    if operation_family in {"lookup", "single_value"} and len(specs) == 1:
        matched_segment = next(
            (
                segment_labels[index]
                for index, segment_key in enumerate(segment_labels_lower)
                if segment_key and segment_key in metric_label_text.lower()
            ),
            "",
        )
        if matched_segment:
            specs[0] = _attach_segment_label_to_resolved_spec(specs[0], matched_segment)
    return specs

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
- benchmark 전용 metric family 이름에 의존하지 말고, operation과 concept 조합으로 task를 만드세요.
- 사업/부문/제품/브랜드(SDC, Harman 등)는 company로 보지 말고 report_scope의 company 안에서 분석할 segment로 다루세요.
- 여러 concept를 각각 더해야 하는 질문이면 먼저 필요한 lookup task를 만들고, 이후 sum task에서 concept addend 역할(addend_1, addend_2, ...)로 묶으세요.
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

            resolved_specs = _apply_segment_labels_to_llm_resolved_specs(
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
                    "result_unit": _infer_concept_ratio_result_unit(query, metric_label, operation_family),
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
            merged_tasks = _append_hybrid_narrative_task(
                merged_tasks,
                query=query,
                intent=intent,
                report_scope=report_scope,
            )
            execution_tasks = _annotate_task_dependencies(
                merged_tasks,
                report_scope=report_scope,
            )
            execution_tasks = _push_narrative_tasks_after_numeric(execution_tasks)
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
                    "execution_task_count": len(execution_tasks),
                },
            )
            for task in pending_execution_tasks or replanned_execution_tasks:
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
                if _llm_plan_preserves_segment_sum_shape(plan, llm_plan):
                    plan = llm_plan
                else:
                    planner_notes = list(plan.get("planner_notes") or [])
                    planner_notes.append("concept_llm_plan_rejected_segment_sum_shape")
                    plan["planner_notes"] = list(dict.fromkeys(planner_notes))
        logical_tasks = [dict(task) for task in (plan.get("tasks") or [])]
        logical_tasks = _append_hybrid_narrative_task(
            logical_tasks,
            query=query,
            intent=intent,
            report_scope=report_scope,
        )
        tasks = _annotate_task_dependencies(
            logical_tasks,
            report_scope=report_scope,
        )
        tasks = _push_narrative_tasks_after_numeric(tasks)
        plan["tasks"] = _project_logical_tasks_from_execution_tasks(logical_tasks, tasks)
        planned_metric_families = [
            str(task.get("metric_family") or "").strip()
            for task in (plan.get("tasks") or [])
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
        runtime_evidence = [dict(item) for item in (state.get("evidence_items") or [])]
        answer = _normalise_spaces(str(state.get("answer") or state.get("compressed_answer") or ""))
        selected_claim_ids = list(state.get("selected_claim_ids") or [])
        if str(active_subtask.get("operation_family") or "").strip().lower() == "narrative_summary" and runtime_evidence:
            deterministic_dividend_answer = self._compose_dividend_policy_hybrid_answer(
                query=str(active_subtask.get("query") or state["query"]),
                evidence_items=runtime_evidence,
            )
            if deterministic_dividend_answer:
                answer = _normalise_spaces(str(deterministic_dividend_answer.get("answer") or "")) or answer
                selected_claim_ids = list(deterministic_dividend_answer.get("supporting_claim_ids") or []) or selected_claim_ids
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
            "selected_claim_ids": selected_claim_ids,
            "runtime_evidence": runtime_evidence,
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

