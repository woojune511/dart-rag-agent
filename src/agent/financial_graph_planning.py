"""
Planning mixin for the financial graph agent.

This module owns the "front" of the graph:
- classify the query
- extract entity and metric hints
- translate the query into numeric subtasks when possible
- project ledger state back into the legacy flat result shape
"""

import logging
from typing import Any, Dict, List, Optional

from langchain_core.prompts import ChatPromptTemplate
from src.agent.financial_graph_helpers import *  # noqa: F401,F403
from src.agent.financial_graph_models import EntityExtraction, FinancialAgentState
from src.config import get_financial_ontology
from src.routing import default_format_preference
from src.schema import ArtifactKind, TaskKind, TaskStatus

logger = logging.getLogger(__name__)

class FinancialAgentPlanningMixin:
    def _default_format_preference(self, intent: str) -> str:
        return default_format_preference(intent)

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
        """Extract company/year/topic hints and align them with report scope."""
        structured_llm = self.llm.with_structured_output(EntityExtraction)
        prompt = ChatPromptTemplate.from_template(
            "다음 질문에서 기업명, 연도, 핵심 주제, 관련 섹션을 추출하세요.\n\n질문: {query}"
        )
        result: EntityExtraction = (prompt | structured_llm).invoke({"query": state["query"]})
        report_scope = dict(state.get("report_scope") or {})
        scope_company = str(report_scope.get("company") or "").strip()
        scope_year_raw = report_scope.get("year")
        scope_year: Optional[int] = None
        try:
            if scope_year_raw not in (None, ""):
                scope_year = int(scope_year_raw)
        except (TypeError, ValueError):
            scope_year = None

        companies = list(result.companies or [])
        if scope_company:
            if not companies:
                companies = [scope_company]
            elif scope_company not in companies:
                companies = [scope_company, *companies]

        years = list(result.years or [])
        if scope_year is not None:
            if not years:
                years = [scope_year]
            elif scope_year not in years:
                years = [scope_year, *years]

        ontology = get_financial_ontology()
        metric = ontology.best_metric_family(
            state["query"],
            result.topic,
            state.get("intent") or state.get("query_type", "qa"),
        )
        target_metric_family = str(metric.get("key") or "") if metric else ""
        logger.info(
            "[extract] companies=%s years=%s topic=%s section_filter=%s target_metric=%s",
            result.companies,
            result.years,
            result.topic,
            result.section_filter,
            target_metric_family or "-",
        )
        return {
            "companies": companies,
            "years": years,
            "topic": result.topic,
            "section_filter": result.section_filter,
            "target_metric_family": target_metric_family,
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
        target_metric_family = str(state.get("target_metric_family") or "")

        if intent not in {"comparison", "trend", "numeric_fact"}:
            return {
                "semantic_plan": {
                    "status": "fallback_general_search",
                    "fallback_to_general_search": True,
                    "tasks": [],
                    "planner_notes": ["non_numeric_intent"],
                },
                "calc_subtasks": [],
                "retrieval_queries": [query],
                "active_subtask_index": 0,
                "active_subtask": {},
                "subtask_results": [],
                "subtask_debug_trace": {"reason": "non_numeric_intent"},
                "subtask_loop_complete": False,
                "tasks": list(state.get("tasks") or []),
                "artifacts": list(state.get("artifacts") or []),
            }

        plan = _build_semantic_numeric_plan(
            query=query,
            topic=topic,
            intent=intent,
            report_scope=report_scope,
            target_metric_family=target_metric_family,
        )
        tasks = list(plan.get("tasks") or [])
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
            "calc_subtasks": tasks,
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
        return str(active_subtask.get("metric_family") or state.get("target_metric_family") or "")

    def _find_task_record(self, state: FinancialAgentState, task_id: str) -> Dict[str, Any]:
        task_id = str(task_id or "").strip()
        if not task_id:
            return {}
        for task in reversed(list(state.get("tasks") or [])):
            if str(task.get("task_id") or "").strip() == task_id:
                return dict(task)
        return {}

    def _extract_artifact_payload_value(
        self,
        artifact: Dict[str, Any],
        payload_key: str,
    ) -> Any:
        payload = dict(artifact.get("payload") or {})
        value = payload.get(payload_key)
        if isinstance(value, list):
            return [dict(item) if isinstance(item, dict) else item for item in value]
        if isinstance(value, dict):
            return dict(value)
        return value

    def _latest_artifact_value_for_task(
        self,
        state: FinancialAgentState,
        *,
        task_id: str,
        kind: ArtifactKind,
        payload_key: str,
    ) -> Any:
        kind_value = str(kind.value if hasattr(kind, "value") else kind)
        artifacts = [dict(item) for item in (state.get("artifacts") or [])]
        task_record = self._find_task_record(state, task_id)
        artifact_ids = [str(value).strip() for value in (task_record.get("artifact_ids") or []) if str(value).strip()]

        for artifact_id in reversed(artifact_ids):
            for artifact in reversed(artifacts):
                if str(artifact.get("artifact_id") or "").strip() != artifact_id:
                    continue
                if str(artifact.get("kind") or "") != kind_value:
                    continue
                return self._extract_artifact_payload_value(artifact, payload_key)

        for artifact in reversed(artifacts):
            if str(artifact.get("task_id") or "").strip() != str(task_id or "").strip():
                continue
            if str(artifact.get("kind") or "") != kind_value:
                continue
            return self._extract_artifact_payload_value(artifact, payload_key)

        return {} if payload_key.endswith("_result") or payload_key.endswith("_plan") else []

    def _project_task_trace_from_ledger(
        self,
        state: FinancialAgentState,
        task_id: str,
    ) -> Dict[str, Any]:
        task_id = str(task_id or "").strip()
        active_task_id = str((state.get("active_subtask") or {}).get("task_id") or "").strip()
        calculation_operands = self._latest_artifact_value_for_task(
            state,
            task_id=task_id,
            kind=ArtifactKind.OPERAND_SET,
            payload_key="calculation_operands",
        )
        calculation_plan = self._latest_artifact_value_for_task(
            state,
            task_id=task_id,
            kind=ArtifactKind.CALCULATION_PLAN,
            payload_key="calculation_plan",
        )
        calculation_result = self._latest_artifact_value_for_task(
            state,
            task_id=task_id,
            kind=ArtifactKind.CALCULATION_RESULT,
            payload_key="calculation_result",
        )
        reconciliation_result = self._latest_artifact_value_for_task(
            state,
            task_id=task_id,
            kind=ArtifactKind.RECONCILIATION_RESULT,
            payload_key="reconciliation_result",
        )

        if task_id == active_task_id:
            if not calculation_operands:
                calculation_operands = [dict(item) for item in (state.get("calculation_operands") or [])]
            if not calculation_plan:
                calculation_plan = dict(state.get("calculation_plan") or {})
            if not calculation_result:
                calculation_result = dict(state.get("calculation_result") or {})
            if not reconciliation_result:
                reconciliation_result = dict(state.get("reconciliation_result") or {})

        task_record = self._find_task_record(state, task_id)
        return {
            "task_id": task_id,
            "artifact_ids": [str(value).strip() for value in (task_record.get("artifact_ids") or []) if str(value).strip()],
            "calculation_operands": list(calculation_operands or []),
            "calculation_plan": dict(calculation_plan or {}),
            "calculation_result": dict(calculation_result or {}),
            "reconciliation_result": dict(reconciliation_result or {}),
        }

    def _build_aggregate_calculation_projection(
        self,
        ordered_results: List[Dict[str, Any]],
        final_answer: str,
    ) -> Dict[str, Any]:
        aggregate_operands: List[Dict[str, Any]] = []
        subtask_plans: List[Dict[str, Any]] = []
        subtask_result_views: List[Dict[str, Any]] = []

        for row in ordered_results:
            task_id = str(row.get("task_id") or "").strip()
            metric_family = str(row.get("metric_family") or "").strip()
            metric_label = str(row.get("metric_label") or "").strip()
            for operand in list(row.get("calculation_operands") or []):
                operand_row = dict(operand)
                operand_row.setdefault("task_id", task_id)
                operand_row.setdefault("metric_family", metric_family)
                operand_row.setdefault("metric_label", metric_label)
                aggregate_operands.append(operand_row)

            plan = dict(row.get("calculation_plan") or {})
            if plan:
                subtask_plans.append(
                    {
                        "task_id": task_id,
                        "metric_family": metric_family,
                        "metric_label": metric_label,
                        "calculation_plan": plan,
                    }
                )

            subtask_result_views.append(
                {
                    "task_id": task_id,
                    "metric_family": metric_family,
                    "metric_label": metric_label,
                    "answer": _normalise_spaces(str(row.get("answer") or "")),
                    "status": str(row.get("status") or ""),
                    "calculation_result": dict(row.get("calculation_result") or {}),
                }
            )

        all_ok = all(str(item.get("status") or "") == "ok" for item in subtask_result_views) if subtask_result_views else False
        calculation_plan = {
            "status": "ok" if subtask_plans else "empty",
            "mode": "aggregate_subtasks",
            "subtask_count": len(subtask_result_views),
            "subtasks": subtask_plans,
        }
        calculation_result = {
            "status": "ok" if all_ok else "partial",
            "rendered_value": final_answer,
            "formatted_result": final_answer,
            "subtask_results": subtask_result_views,
            "derived_metrics": {
                "subtask_count": len(subtask_result_views),
                "subtask_ids": [str(item.get("task_id") or "") for item in subtask_result_views if str(item.get("task_id") or "").strip()],
            },
        }
        return {
            "calculation_operands": aggregate_operands,
            "calculation_plan": calculation_plan,
            "calculation_result": calculation_result,
        }

    def _project_legacy_calculation_fields(self, state: FinancialAgentState) -> Dict[str, Any]:
        """Project ledger-backed traces into the legacy flat calculation view."""
        subtask_results = [dict(item) for item in (state.get("subtask_results") or [])]
        if subtask_results and (
            str((state.get("calculation_plan") or {}).get("mode") or "") == "aggregate_subtasks"
            or bool((state.get("calculation_result") or {}).get("subtask_results"))
        ):
            return {
                "calculation_operands": list(state.get("calculation_operands") or []),
                "calculation_plan": dict(state.get("calculation_plan") or {}),
                "calculation_result": dict(state.get("calculation_result") or {}),
            }

        if subtask_results:
            final_answer = _normalise_spaces(str(state.get("answer") or state.get("compressed_answer") or ""))
            return self._build_aggregate_calculation_projection(subtask_results, final_answer)

        active_task_id = str((state.get("active_subtask") or {}).get("task_id") or "").strip()
        if active_task_id:
            projected = self._project_task_trace_from_ledger(state, active_task_id)
            return {
                "calculation_operands": list(projected.get("calculation_operands") or []),
                "calculation_plan": dict(projected.get("calculation_plan") or {}),
                "calculation_result": dict(projected.get("calculation_result") or {}),
            }

        return {
            "calculation_operands": list(state.get("calculation_operands") or []),
            "calculation_plan": dict(state.get("calculation_plan") or {}),
            "calculation_result": dict(state.get("calculation_result") or {}),
        }

    def _capture_current_subtask_result(self, state: FinancialAgentState) -> Dict[str, Any]:
        active_subtask = dict(state.get("active_subtask") or {})
        if not active_subtask:
            return {}
        projected = self._project_task_trace_from_ledger(
            state,
            str(active_subtask.get("task_id") or ""),
        )
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

