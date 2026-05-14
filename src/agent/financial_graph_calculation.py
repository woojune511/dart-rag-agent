"""
Calculation mixin for the financial graph agent.

This module owns the structured numeric path after reconciliation:
- extract normalized operands
- plan the calculation formula
- execute and verify the numeric result
- advance or aggregate multi-subtask calculations
"""

import json
import logging
from typing import Any, Dict, List, Optional

from langchain_core.prompts import ChatPromptTemplate
from src.agent.financial_graph_helpers import *  # noqa: F401,F403
from src.agent.financial_graph_models import CalculationPlan, CalculationRenderOutput, CalculationResult, CalculationVerificationOutput, FinancialAgentState, OperandExtraction
from src.config import get_financial_ontology
from src.schema import ArtifactKind, TaskKind, TaskStatus

logger = logging.getLogger(__name__)

class FinancialAgentCalculationMixin:
    def _extract_calculation_operands(self, state: FinancialAgentState) -> Dict[str, Any]:
        """Build the operand set for the current calculation subtask.

        The flow is intentionally layered:
        1. direct structured-row extraction from reconciliation
        2. evidence-based fallback extraction
        3. merge partial direct hits with fallback rows
        """
        evidence_items = list(state.get("evidence_items", []) or [])
        evidence_bullets = list(state.get("evidence_bullets", []) or [])
        retrieved_docs = state.get("retrieved_docs", []) or []
        seed_retrieved_docs = state.get("seed_retrieved_docs", []) or []
        evidence_status = str(state.get("evidence_status") or "")
        intent = state.get("intent") or state.get("query_type", "qa")
        query = self._calc_query(state)
        topic = self._calc_topic(state)
        empty_result: Dict[str, Any] = {
            "calculation_operands": [],
            "calculation_debug_trace": {"coverage": "missing"},
            "answer": "",
        }
        direct_structured_rows = self._extract_structured_operands_from_reconciliation(state)
        reconciliation_evidence = self._evidence_items_from_reconciliation_matches(state)
        if reconciliation_evidence:
            existing_ids = {str(item.get("evidence_id") or "").strip() for item in evidence_items}
            appended = 0
            for item in reconciliation_evidence:
                evidence_id = str(item.get("evidence_id") or "").strip()
                if evidence_id and evidence_id in existing_ids:
                    continue
                if evidence_id:
                    existing_ids.add(evidence_id)
                evidence_items.append(item)
                raw_row = _normalise_spaces(str(item.get("raw_row_text") or item.get("claim") or ""))
                evidence_bullets.append(f"- {item.get('source_anchor')} {raw_row[:180]} (reconciled)")
                appended += 1
            if appended:
                logger.info("[calc_operands] appended reconciled evidence items=%s", appended)
        active_subtask = dict(state.get("active_subtask") or {})
        required_operands = [
            dict(item)
            for item in (active_subtask.get("required_operands") or [])
            if bool(item.get("required", True))
        ]
        # If reconciliation already found every required operand as clean
        # structured rows, skip the broader fallback path entirely.
        if direct_structured_rows and (
            not required_operands or len(direct_structured_rows) >= len(required_operands)
        ):
            logger.info("[calc_operands] structured-row direct operands=%s", len(direct_structured_rows))
            artifacts = list(state.get("artifacts") or [])
            tasks = list(state.get("tasks") or [])
            task_id = str(active_subtask.get("task_id") or "calc")
            artifact_id = f"operands:{task_id}:{len(artifacts) + 1:03d}"
            artifacts = _append_artifact(
                artifacts,
                artifact_id=artifact_id,
                task_id=task_id,
                kind=ArtifactKind.OPERAND_SET,
                status="ok",
                summary=f"{len(direct_structured_rows)} structured operand(s)",
                payload={"calculation_operands": direct_structured_rows, "source": "structured_row_direct"},
                evidence_refs=[str(row.get("evidence_id") or "") for row in direct_structured_rows if str(row.get("evidence_id") or "").strip()],
            )
            tasks = _upsert_task(
                tasks,
                task_id=task_id,
                kind=TaskKind.CALCULATION,
                label=str(active_subtask.get("metric_label") or task_id),
                status=TaskStatus.IN_PROGRESS,
                query=self._calc_query(state),
                metric_family=self._calc_metric_family(state),
                artifact_id=artifact_id,
            )
            return {
                "calculation_operands": direct_structured_rows,
                "calculation_debug_trace": {
                    "coverage": "sufficient",
                    "source": "structured_row_direct",
                    "operands": direct_structured_rows,
                },
                "tasks": tasks,
                "artifacts": artifacts,
            }
        should_augment_with_docs = (
            bool(retrieved_docs or seed_retrieved_docs)
            and intent in {"comparison", "trend"}
            and (not evidence_items or evidence_status != "sufficient")
        )
        if should_augment_with_docs:
            candidate_docs = seed_retrieved_docs or retrieved_docs
            synthesized_items: List[Dict[str, Any]] = []
            synthesized_bullets: List[str] = []
            seen_anchors = {str(item.get("source_anchor") or "") for item in evidence_items}
            percent_point_query = _is_percent_point_difference_query(query)
            ratio_row_candidates = self._extract_ratio_row_candidates(candidate_docs, query, topic)
            if ratio_row_candidates:
                logger.info("[calc_operands] ratio row fallback candidates=%s", len(ratio_row_candidates))
                synthesized_items.extend(ratio_row_candidates)
                synthesized_bullets.extend(
                    f"- {item['source_anchor']} {item.get('source_context', '')} {str(item.get('raw_row_text') or '')[:180]} (direct)"
                    for item in ratio_row_candidates
                )
                seen_anchors.update(str(item.get("source_anchor") or "") for item in ratio_row_candidates)
            if not percent_point_query:
                component_candidates = self._extract_ratio_component_candidates(candidate_docs, query, topic)
                if component_candidates:
                    logger.info("[calc_operands] ratio component fallback candidates=%s", len(component_candidates))
                    synthesized_items.extend(component_candidates)
                    synthesized_bullets.extend(
                        f"- {item['source_anchor']} {item.get('source_context', '')} {str(item.get('raw_row_text') or '')[:180]} (direct)"
                        for item in component_candidates
                    )
                    seen_anchors.update(str(item.get("source_anchor") or "") for item in component_candidates)
            for index, (doc, _score) in enumerate(candidate_docs[: min(8, len(candidate_docs))], start=1):
                metadata = dict(doc.metadata or {})
                anchor = self._build_source_anchor(metadata)
                if anchor in seen_anchors:
                    continue
                text = _normalise_spaces(doc.page_content)
                claim = text[:1200]
                item = {
                    "evidence_id": f"ev_doc_{index:03d}",
                    "source_anchor": anchor,
                    "claim": claim,
                    "quote_span": claim[:240],
                    "support_level": "direct",
                    "question_relevance": "high",
                    "allowed_terms": [],
                    "metadata": metadata,
                }
                synthesized_items.append(item)
                synthesized_bullets.append(f"- {anchor} {claim[:180]} (direct)")
            if synthesized_items:
                evidence_items = evidence_items + synthesized_items
                evidence_bullets = evidence_bullets + synthesized_bullets
                logger.info(
                    "[calc_operands] augmenting evidence with synthesized retrieved_docs=%s existing=%s",
                    len(synthesized_items),
                    len(state.get("evidence_items", []) or []),
                )
        if not evidence_items:
            return empty_result

        structured_llm = self.llm.with_structured_output(OperandExtraction)
        evidence_text = self._format_evidence_for_prompt(evidence_items, evidence_bullets)
        prompt = ChatPromptTemplate.from_template(
            """당신은 재무 계산을 위한 피연산자 추출기입니다.
질문을 풀기 위해 필요한 숫자만 single-shot으로 한 번에 추출하세요.

규칙:
- 여러 번 나눠 찾지 말고, 필요한 피연산자를 한 번의 호출로 모두 찾으세요.
- operand_id는 비워도 됩니다. 코드는 이후에 고유 ID를 부여합니다.
- 각 operand는 반드시 evidence_id와 source_anchor를 포함하세요.
- raw_value는 문서에 있는 숫자 표현 그대로 적으세요. '111조 659억원'처럼 조+억 복합 표기는 절대 억원이나 조원으로 변환하지 말고 원문 그대로 적으세요. 변환하면 반올림 오차가 발생합니다.
- raw_unit은 숫자 바로 옆 단위를 적으세요. 복합 표기('111조 659억원')는 raw_unit을 '억원'으로 적지 말고, raw_value에 원문 전체를 넣고 raw_unit은 '원'으로 적으세요.
- normalized_value와 normalized_unit은 추정해서 채워도 되지만, 이후 코드가 다시 검증합니다.
- 비교/추세 질문은 질문 해결에 꼭 필요한 숫자만 추출하세요.
- source_context와 raw_row_text가 있으면, 해당 표의 헤더와 행을 함께 읽어 period와 숫자 매핑을 복원하세요.
- raw_row_text에 같은 metric의 여러 연도/기간 값이 함께 있으면, 각 연도/기간별 숫자를 별도 operand로 나누어 추출하세요.
- 질문이 단일 비율/비중/이익률 조회라면 피연산자 1개만 추출할 수 있습니다.
- 질문이 두 기간/두 부문/두 비율의 차이·비교·대비·%p 차이를 묻는다면, 절대 단일 비율 피연산자 1개로 축약하지 말고 비교 대상별 피연산자를 각각 추출하세요.
- 질문에 `%p`, `차이`, `비교`, `대비`가 있고 evidence에 동일 metric의 여러 기간/부문 percent 값이 보이면, 해당 percent 값들을 period별/대상별로 각각 별도 operand로 추출하세요.
- 추이(trend) 질문이고 evidence에 3개 이상의 연도/기간 수치가 보이면, 가능한 한 3개 이상 기간의 피연산자를 빠짐없이 추출하세요.
- 문서 메타데이터의 보고서 연도와 표 안에 적힌 비교 기간(예: 2024년, 2023년, 2022년)을 혼동하지 말고, period 필드에는 표에서 읽은 실제 기간을 그대로 적으세요.
- 수치가 없는 descriptive evidence는 operand로 만들지 마세요.

질문: {query}

Structured Evidence:
{evidence}
"""
        )
        try:
            extracted: OperandExtraction = (prompt | structured_llm).invoke(
                {"query": query, "evidence": evidence_text}
            )
            operand_rows: List[Dict[str, Any]] = []
            for index, item in enumerate(extracted.operands, start=1):
                normalized_value, normalized_unit = _normalise_operand_value(item.raw_value, item.raw_unit)
                row = item.model_dump()
                row["operand_id"] = f"op_{index:03d}"
                row["normalized_value"] = normalized_value
                row["normalized_unit"] = normalized_unit
                operand_rows.append(row)
            if direct_structured_rows and required_operands:
                operand_rows = _merge_operand_rows(
                    direct_structured_rows,
                    operand_rows,
                    required_operands=required_operands,
                )

            missing_required = _missing_required_operands(required_operands, operand_rows) if required_operands else []
            if missing_required:
                generic_fallback_rows = self._build_required_operands_from_candidates(
                    evidence_items,
                    required_operands=missing_required,
                    query=query,
                    topic=state.get("topic") or "",
                    report_scope=dict(state.get("report_scope") or {}),
                )
                if generic_fallback_rows:
                    logger.info("[calc_operands] generic operand fallback rows=%s", len(generic_fallback_rows))
                    operand_rows = _merge_operand_rows(
                        operand_rows,
                        generic_fallback_rows,
                        required_operands=required_operands,
                    )
            missing_required = _missing_required_operands(required_operands, operand_rows) if required_operands else []
            if missing_required and _is_ratio_percent_query(query):
                fallback_rows = self._build_ratio_operands_from_candidates(
                    [item for item in evidence_items if item.get("raw_row_text")],
                    query,
                    topic=state.get("topic") or "",
                    report_scope=dict(state.get("report_scope") or {}),
                )
                if fallback_rows:
                    logger.info("[calc_operands] python ratio fallback operands=%s", len(fallback_rows))
                    operand_rows = _merge_operand_rows(
                        operand_rows,
                        fallback_rows,
                        required_operands=required_operands,
                    )
            if _is_percent_point_difference_query(query):
                operand_rows = [
                    row for row in operand_rows
                    if str(row.get("normalized_unit") or "") == "PERCENT" and row.get("normalized_value") is not None
                ]
                logger.info("[calc_operands] percent-diff operand filtering retained=%s", len(operand_rows))
            merged_coverage = extracted.coverage
            if direct_structured_rows and operand_rows and required_operands:
                merged_coverage = (
                    "sufficient"
                    if not _missing_required_operands(required_operands, operand_rows)
                    else "partial"
                )
            logger.info("[calc_operands] coverage=%s operands=%s", merged_coverage, len(operand_rows))
            artifacts = list(state.get("artifacts") or [])
            tasks = list(state.get("tasks") or [])
            task_id = str(active_subtask.get("task_id") or "calc")
            artifact_id = f"operands:{task_id}:{len(artifacts) + 1:03d}"
            artifacts = _append_artifact(
                artifacts,
                artifact_id=artifact_id,
                task_id=task_id,
                kind=ArtifactKind.OPERAND_SET,
                status=str(merged_coverage),
                summary=f"{len(operand_rows)} operand(s) from llm/fallback extraction",
                payload={"calculation_operands": operand_rows, "coverage": merged_coverage},
                evidence_refs=[str(row.get("evidence_id") or "") for row in operand_rows if str(row.get("evidence_id") or "").strip()],
            )
            tasks = _upsert_task(
                tasks,
                task_id=task_id,
                kind=TaskKind.CALCULATION,
                label=str(active_subtask.get("metric_label") or task_id),
                status=TaskStatus.IN_PROGRESS,
                query=self._calc_query(state),
                metric_family=self._calc_metric_family(state),
                artifact_id=artifact_id,
            )
            return {
                "calculation_operands": operand_rows,
                "calculation_debug_trace": {
                    "coverage": merged_coverage,
                    "direct_structured_rows": direct_structured_rows,
                    "operands": operand_rows,
                },
                "tasks": tasks,
                "artifacts": artifacts,
            }
        except Exception as exc:
            logger.warning("[calc_operands] structured output failed: %s", exc)
            return {
                "calculation_operands": [],
                "calculation_debug_trace": {"coverage": "missing", "error": str(exc)},
            }

    def _plan_formula_calculation(self, state: FinancialAgentState) -> Dict[str, Any]:
        """Translate normalized operands into an executable calculation plan."""
        operands = state.get("calculation_operands", [])
        query = self._calc_query(state)
        if not operands:
            missing_info = self._infer_missing_info(state, [])
            return {
                "calculation_plan": {
                    "status": "incomplete",
                    "mode": "none",
                    "operation": "none",
                    "ordered_operand_ids": [],
                    "variable_bindings": [],
                    "formula": "",
                    "pairwise_formula": "",
                    "result_unit": "",
                    "operation_text": "",
                    "explanation": "no operands",
                    "missing_info": missing_info,
                },
                "missing_info": missing_info,
                "planner_debug_trace": {
                    "llm_invoked": False,
                    "guard_applied": False,
                    "reason": "no operands",
                    "missing_info": missing_info,
                },
            }

        query_text = _normalise_spaces(query)
        structured_llm = self.llm.with_structured_output(CalculationPlan)
        ontology = get_financial_ontology()
        metric_key = self._calc_metric_family(state)
        metric_info = ontology.metric_family(metric_key) if metric_key else None
        ontology_context = ""
        if metric_info:
            components = dict(metric_info.get("components") or {})
            component_lines: List[str] = []
            for role, component in components.items():
                name = str(component.get("name") or "").strip()
                keywords = ", ".join(
                    str(keyword).strip()
                    for keyword in component.get("keywords", [])
                    if str(keyword).strip()
                )
                preferred_sections = ", ".join(
                    str(section).strip()
                    for section in component.get("preferred_sections", [])
                    if str(section).strip()
                )
                bits = [f"{role}={name or '-'}"]
                if keywords:
                    bits.append(f"keywords={keywords}")
                if preferred_sections:
                    bits.append(f"preferred_sections={preferred_sections}")
                component_lines.append(" | ".join(bits))
            preferred_sections = ", ".join(
                str(section).strip()
                for section in metric_info.get("preferred_sections", [])
                if str(section).strip()
            )
            ontology_lines = [
                f"- key={metric_info.get('key', '')}",
                f"- display_name={metric_info.get('display_name', '')}",
                f"- formula_template={metric_info.get('formula_template', '')}",
                f"- result_unit={metric_info.get('result_unit', '')}",
            ]
            if preferred_sections:
                ontology_lines.append(f"- preferred_sections={preferred_sections}")
            if component_lines:
                ontology_lines.append("- components:")
                ontology_lines.extend(f"  - {line}" for line in component_lines)
            ontology_context = "\n".join(ontology_lines)
        operands_text = "\n".join(
            f"- operand_id={row.get('operand_id')} | evidence_id={row.get('evidence_id')} | label={row.get('label')} | raw={row.get('raw_value')} {row.get('raw_unit')} | normalized={row.get('normalized_value')} {row.get('normalized_unit')} | period={row.get('period', '')}"
            for row in operands
        )
        planner_trace_base = {
            "target_metric_family": metric_key,
            "ontology_context": ontology_context or "-",
            "operands_text": operands_text,
        }
        prompt = ChatPromptTemplate.from_template(
            """당신은 재무 계산 계획기입니다.
질문과 피연산자 목록을 보고 변수 바인딩과 계산식을 작성하세요.

규칙:
- variable_bindings에는 반드시 아래 피연산자 목록의 operand_id만 넣으세요.
- 각 binding의 variable은 A, B, C, D, E, F 중 하나만 사용하세요.
- ordered_operand_ids는 variable_bindings와 같은 순서로 넣으세요.
- operation은 로그/평가용 힌트입니다. subtract, add, ratio, growth_rate, max, min, time_series_trend, none 중 가장 가까운 값을 넣으세요.
- 실제 계산은 formula와 pairwise_formula로 표현합니다.
- formula에는 숫자 상수와 변수(A, B, C...) 그리고 +, -, *, /, **, min(), max(), abs(), round(), log(), exp()만 사용할 수 있습니다.
- mode=single_value 이면 formula로 단일 결과를 계산하세요.
- mode=time_series 이면 variable_bindings를 시계열 순서로 배치하고, formula에는 전체 흐름을 대표하는 계산식(예: ((C - A) / A) * 100)을, pairwise_formula에는 인접 시점 계산식(예: ((CURR - PREV) / PREV) * 100)을 적으세요.
- 최근 3년/연도별/추이 질문처럼 3개 이상 기간 데이터가 있을 때는 mode=time_series 와 operation=time_series_trend 를 우선 사용하세요.
- 이미 계산된 단일 비율/비중/이익률 하나만 답하면 되는 질문이라면 mode=single_value, formula=A 를 사용하세요.
- 질문이 단일 비율/비중/이익률 조회이고 피연산자가 퍼센트 1개뿐이라면 반드시 mode=single_value, formula=A 를 사용하세요.
- 질문이 단일 비율/비중/이익률 조회이고 분자/분모 역할의 금액 피연산자 2개가 있다면 formula는 (A / B) * 100 형태로 작성하세요.
- 두 비율/비중의 차이(%p 차이 포함)를 묻는 질문이라면 mode=single_value 로 두고 formula는 A - B 또는 질문 순서에 맞는 차이식으로 작성하세요. 단일 operand 하나로 끝내지 마세요.
- 증가율/감소율/변화율은 가능한 한 질문에서 기준이 되는 이전 값이 분모가 되도록 식을 작성하세요.
- 현재 피연산자만으로 질문을 풀 수 없으면 억지로 수식을 만들지 말고 status=incomplete, mode=none, operation=none 으로 두고 missing_info에 부족한 정보를 적으세요.
- result_unit은 최종 답변 단위를 적으세요. 예: 억원, 원, %, 개
- ontology_context는 이 질문에 대해 추정된 metric family prior 입니다. 실제 피연산자와 모순되면 ontology_context보다 피연산자를 우선하세요.
- ontology_context에 formula_template과 components가 있으면, 단일 비율 조회는 A 또는 (A / B) * 100, %p 차이는 A - B 같은 계획을 세울 때 참고하세요.

질문: {query}

Ontology Context:
{ontology_context}

사용 가능한 피연산자:
{operands}
"""
        )
        try:
            plan: CalculationPlan = (prompt | structured_llm).invoke(
                {
                    "query": query,
                    "operands": operands_text,
                    "ontology_context": ontology_context or "-",
                }
            )
            plan_data = plan.model_dump()
            plan_data.setdefault("status", "ok")
            bindings = plan_data.get("variable_bindings") or []
            if not plan_data.get("ordered_operand_ids") and bindings:
                plan_data["ordered_operand_ids"] = [str(binding.get("operand_id") or "") for binding in bindings if str(binding.get("operand_id") or "").strip()]
            if not bindings and plan_data.get("ordered_operand_ids"):
                plan_data["variable_bindings"] = [
                    {"variable": chr(ord("A") + index), "operand_id": operand_id}
                    for index, operand_id in enumerate(plan_data.get("ordered_operand_ids") or [])
                ]
            if (
                str(plan_data.get("mode") or "").lower() == "none"
                and not (plan_data.get("variable_bindings") or [])
            ):
                plan_data["status"] = "incomplete"
                if not plan_data.get("missing_info"):
                    plan_data["missing_info"] = self._infer_missing_info(state, operands)
            if _should_coerce_percent_point_unit(query_text, operands, plan_data):
                plan_data["result_unit"] = "%p"
            logger.info("[formula_plan] mode=%s op=%s vars=%s", plan_data.get("mode"), plan_data.get("operation"), len(plan_data.get("variable_bindings") or []))
            artifacts = list(state.get("artifacts") or [])
            tasks = list(state.get("tasks") or [])
            task_id = str((state.get("active_subtask") or {}).get("task_id") or "calc")
            artifact_id = f"plan:{task_id}:{len(artifacts) + 1:03d}"
            artifacts = _append_artifact(
                artifacts,
                artifact_id=artifact_id,
                task_id=task_id,
                kind=ArtifactKind.CALCULATION_PLAN,
                status=str(plan_data.get("status") or "ok"),
                summary=f"mode={plan_data.get('mode')} op={plan_data.get('operation')}",
                payload={"calculation_plan": plan_data},
            )
            tasks = _upsert_task(
                tasks,
                task_id=task_id,
                kind=TaskKind.CALCULATION,
                label=str((state.get("active_subtask") or {}).get("metric_label") or task_id),
                status=TaskStatus.IN_PROGRESS,
                query=self._calc_query(state),
                metric_family=self._calc_metric_family(state),
                artifact_id=artifact_id,
            )
            return {
                "calculation_plan": plan_data,
                "missing_info": [str(item).strip() for item in (plan_data.get("missing_info") or []) if str(item).strip()],
                "planner_debug_trace": {
                    **planner_trace_base,
                    "llm_invoked": True,
                    "guard_applied": False,
                    "raw_plan": plan_data,
                },
                "tasks": tasks,
                "artifacts": artifacts,
            }
        except Exception as exc:
            logger.warning("[formula_plan] structured output failed: %s", exc)
            return {
                "calculation_plan": {
                    "status": "incomplete",
                    "mode": "none",
                    "operation": "none",
                    "ordered_operand_ids": [],
                    "variable_bindings": [],
                    "formula": "",
                    "pairwise_formula": "",
                    "result_unit": "",
                    "operation_text": "",
                    "explanation": str(exc),
                    "missing_info": self._infer_missing_info(state, operands),
                },
                "missing_info": self._infer_missing_info(state, operands),
                "planner_debug_trace": {
                    **planner_trace_base,
                    "llm_invoked": True,
                    "guard_applied": False,
                    "error": str(exc),
                },
            }

    def _format_calculation_value(self, value: float, result_unit: str, normalized_unit: str) -> str:
        if normalized_unit == "KRW":
            # normalized_value is always in full KRW — always render as 조/억원 regardless of result_unit hint
            return _format_korean_won_compact(value)
        if (normalized_unit or "").upper() in {"PERCENT", "%", "퍼센트"}:
            return f"{value:.1f}"
        if normalized_unit in {"COUNT", "USD"}:
            return f"{value:,.4f}".rstrip("0").rstrip(".")
        return f"{value}"

    def _execute_calculation(self, state: FinancialAgentState) -> Dict[str, Any]:
        """Execute the planned numeric operation and normalize the result."""
        operands = {row.get("operand_id"): row for row in state.get("calculation_operands", [])}
        plan = state.get("calculation_plan") or {}
        operation = str(plan.get("operation") or "none")
        mode = str(plan.get("mode") or "none")
        ordered_ids = [operand_id for operand_id in (plan.get("ordered_operand_ids") or []) if operand_id in operands]
        variable_bindings = [
            binding for binding in (plan.get("variable_bindings") or [])
            if str(binding.get("operand_id") or "") in operands and str(binding.get("variable") or "").strip()
        ]
        formula = str(plan.get("formula") or "").strip()
        pairwise_formula = str(plan.get("pairwise_formula") or "").strip()
        result_unit = str(plan.get("result_unit") or "")
        explanation = str(plan.get("explanation") or "")
        selected_evidence_ids: List[str] = []
        source_normalized_unit = ""

        def _fail(status: str, reason: str) -> Dict[str, Any]:
            fallback = "질문에 필요한 수치를 계산할 수 있는 근거를 충분히 확보하지 못했습니다."
            return {
                "answer": fallback,
                "compressed_answer": fallback,
                "selected_claim_ids": selected_evidence_ids,
                "draft_points": [],
                "kept_claim_ids": selected_evidence_ids,
                "dropped_claim_ids": [],
                "unsupported_sentences": [],
                "sentence_checks": [],
                "calculation_result": {
                    "status": status,
                    "result_value": None,
                    "result_unit": result_unit,
                    "rendered_value": "",
                    "formatted_result": "",
                    "series": [],
                    "derived_metrics": {},
                    "explanation": reason,
                },
            }

        if mode == "none" or not variable_bindings:
            return _fail("insufficient_operands", explanation or "no operation or operands")

        if not ordered_ids:
            ordered_ids = [str(binding.get("operand_id") or "") for binding in variable_bindings]

        ordered_operands = [operands[operand_id] for operand_id in ordered_ids]
        selected_evidence_ids = list(
            dict.fromkeys(str(row.get("evidence_id")) for row in ordered_operands if row.get("evidence_id"))
        )
        units = {row.get("normalized_unit") for row in ordered_operands}
        if len(units) != 1:
            return _fail("unit_mismatch", f"unit families differ: {sorted(str(unit) for unit in units)}")
        normalized_unit = str(next(iter(units)))
        source_normalized_unit = normalized_unit
        values = [row.get("normalized_value") for row in ordered_operands]
        if any(value is None for value in values):
            return _fail("parse_error", "one or more operands could not be normalized")

        try:
            result_value: Optional[float]
            derived_metrics: Dict[str, Any] = {}
            result_series: List[Dict[str, Any]] = []
            env: Dict[str, float] = {}
            for binding in variable_bindings:
                variable = str(binding.get("variable") or "").strip()
                operand_id = str(binding.get("operand_id") or "").strip()
                operand = operands.get(operand_id)
                if not variable or operand is None or operand.get("normalized_value") is None:
                    return _fail("parse_error", f"invalid variable binding: {binding}")
                env[variable] = float(operand.get("normalized_value"))

            if mode == "time_series":
                if len(variable_bindings) < 2:
                    return _fail("insufficient_operands", "time_series needs at least 2 operands")
                ordered_operands = sorted(
                    [operands[str(binding.get("operand_id"))] for binding in variable_bindings],
                    key=lambda row: _extract_period_sort_key(str(row.get("period") or "")),
                )
                selected_evidence_ids = list(
                    dict.fromkeys(str(row.get("evidence_id")) for row in ordered_operands if row.get("evidence_id"))
                )
                labels = [_display_operand_label(str(row.get("label") or row.get("evidence_id") or "")) for row in ordered_operands]
                metric_names = [re.sub(r"^\d{4}년\s*", "", label).strip() for label in labels]
                metric_name = metric_names[0] if metric_names else "지표"
                for row in ordered_operands:
                    point_value = float(row.get("normalized_value"))
                    point_rendered = self._format_calculation_value(point_value, str(row.get("raw_unit") or row.get("result_unit") or ""), normalized_unit)
                    result_series.append(
                        {
                            "label": _display_operand_label(str(row.get("label") or row.get("evidence_id") or "")),
                            "period": str(row.get("period") or ""),
                            "raw_value": str(row.get("raw_value") or ""),
                            "raw_unit": str(row.get("raw_unit") or ""),
                            "normalized_value": point_value,
                            "normalized_unit": normalized_unit,
                            "rendered_value": point_rendered,
                        }
                    )
                yoy_growth_rates: List[Optional[float]] = [None]
                if pairwise_formula:
                    for previous_row, current_row in zip(ordered_operands, ordered_operands[1:]):
                        prev_value = float(previous_row.get("normalized_value"))
                        curr_value = float(current_row.get("normalized_value"))
                        try:
                            yoy_growth_rates.append(_safe_eval_formula(pairwise_formula, {"PREV": prev_value, "CURR": curr_value}))
                        except ZeroDivisionError:
                            yoy_growth_rates.append(None)
                if not formula:
                    return _fail("parse_error", "missing trend formula")
                result_value = _safe_eval_formula(formula, env)
                if result_unit == "%":
                    normalized_unit = "PERCENT"
                _is_percent = (normalized_unit or "").upper() in {"PERCENT", "%", "퍼센트"}
                if _is_percent:
                    rendered_value = f"{result_value:.1f}%"
                else:
                    rendered_value = f"{result_value:,.4f}".rstrip("0").rstrip(".")
                logger.info("[calculator] mode=%s op=%s result=%s", mode, operation, rendered_value)
                return {
                    "answer": "",
                    "compressed_answer": "",
                    "selected_claim_ids": selected_evidence_ids,
                    "draft_points": [],
                    "kept_claim_ids": selected_evidence_ids,
                    "dropped_claim_ids": [],
                    "unsupported_sentences": [],
                    "sentence_checks": [],
                    "calculation_result": {
                        "status": "ok",
                        "result_value": result_value,
                        "result_unit": result_unit,
                        "rendered_value": rendered_value,
                        "formatted_result": "",
                        "series": result_series,
                        "derived_metrics": {
                            "metric_name": metric_name,
                            "yoy_growth_rates": yoy_growth_rates,
                            "formula": formula,
                            "pairwise_formula": pairwise_formula,
                        },
                        "explanation": explanation or str(plan.get("operation_text") or operation or mode),
                    },
                }

            if not formula:
                return _fail("parse_error", "missing scalar formula")
            result_value = _safe_eval_formula(formula, env)
            if result_unit == "%":
                normalized_unit = "PERCENT"
        except Exception as exc:
            if isinstance(exc, ZeroDivisionError):
                return _fail("zero_division", str(exc))
            return _fail("parse_error", str(exc))

        rendered_value = self._format_calculation_value(result_value, result_unit or "", normalized_unit)
        if normalized_unit == "KRW":
            rendered_with_unit = rendered_value
        elif result_unit:
            rendered_with_unit = f"{rendered_value}{result_unit}"
        else:
            rendered_with_unit = rendered_value
        labels = [_display_operand_label(str(row.get("label") or row.get("evidence_id") or "")) for row in ordered_operands]
        result_series = []
        for row in ordered_operands:
            point_value = float(row.get("normalized_value"))
            point_rendered = self._format_calculation_value(
                point_value,
                str(row.get("raw_unit") or row.get("result_unit") or ""),
                source_normalized_unit,
            )
            result_series.append(
                {
                    "label": _display_operand_label(str(row.get("label") or row.get("evidence_id") or "")),
                    "period": str(row.get("period") or ""),
                    "raw_value": str(row.get("raw_value") or ""),
                    "raw_unit": str(row.get("raw_unit") or ""),
                    "normalized_value": point_value,
                    "normalized_unit": source_normalized_unit,
                    "rendered_value": point_rendered,
                }
            )
        logger.info("[calculator] op=%s result=%s", operation, rendered_with_unit)
        result_payload = {
            "answer": "",
            "compressed_answer": "",
            "selected_claim_ids": selected_evidence_ids,
            "draft_points": [],
            "kept_claim_ids": selected_evidence_ids,
            "dropped_claim_ids": [],
            "unsupported_sentences": [],
            "sentence_checks": [],
            "calculation_result": {
                "status": "ok",
                "result_value": result_value,
                "result_unit": result_unit,
                "rendered_value": rendered_with_unit,
                "formatted_result": "",
                "series": result_series,
                "derived_metrics": {
                    "operand_labels": labels,
                    "formula": formula,
                },
                "explanation": explanation or str(plan.get("operation_text") or operation or mode),
            },
        }
        artifacts = list(state.get("artifacts") or [])
        tasks = list(state.get("tasks") or [])
        task_id = str((state.get("active_subtask") or {}).get("task_id") or "calc")
        artifact_id = f"result:{task_id}:{len(artifacts) + 1:03d}"
        calc_result = dict(result_payload.get("calculation_result") or {})
        artifacts = _append_artifact(
            artifacts,
            artifact_id=artifact_id,
            task_id=task_id,
            kind=ArtifactKind.CALCULATION_RESULT,
            status=str(calc_result.get("status") or "ok"),
            summary=str(calc_result.get("rendered_value") or calc_result.get("formatted_result") or ""),
            payload={"calculation_result": calc_result},
            evidence_refs=selected_evidence_ids,
        )
        tasks = _upsert_task(
            tasks,
            task_id=task_id,
            kind=TaskKind.CALCULATION,
            label=str((state.get("active_subtask") or {}).get("metric_label") or task_id),
            status=TaskStatus.COMPLETED if str(calc_result.get("status") or "") == "ok" else TaskStatus.FAILED,
            query=self._calc_query(state),
            metric_family=self._calc_metric_family(state),
            artifact_id=artifact_id,
        )
        result_payload["tasks"] = tasks
        result_payload["artifacts"] = artifacts
        return result_payload

    def _render_calculation_answer(self, state: FinancialAgentState) -> Dict[str, Any]:
        calculation_result = dict(state.get("calculation_result") or {})
        plan = dict(state.get("calculation_plan") or {})
        operands = list(state.get("calculation_operands") or [])
        if not calculation_result:
            return {"answer": "", "compressed_answer": "", "draft_points": []}

        # direction_hint: Python에서 결정론적으로 계산 — LLM에게 부호 판단 위임하지 않음
        operation = str(plan.get("operation") or "")
        result_val = float(calculation_result.get("result_value") or 0)
        if operation == "growth_rate":
            direction_hint = "증가" if result_val > 0 else "감소" if result_val < 0 else "변동 없음"
        elif operation == "subtract":
            direction_hint = "더 큽니다" if result_val > 0 else "더 작습니다" if result_val < 0 else "동일합니다"
        else:
            direction_hint = ""

        # direction_hint가 방향을 표현할 때 rendered_value의 부호는 중복 — 제거
        if direction_hint and result_val < 0:
            rv = str(calculation_result.get("rendered_value") or "")
            calculation_result["rendered_value"] = rv.lstrip("-")

        if str(calculation_result.get("status") or "") != "ok":
            fallback = "질문에 필요한 수치를 계산할 수 있는 근거를 충분히 확보하지 못했습니다."
            return {
                "answer": fallback,
                "compressed_answer": fallback,
                "draft_points": [fallback],
            }

        structured_llm = self.llm.with_structured_output(CalculationRenderOutput)
        prompt = ChatPromptTemplate.from_template(
            """당신은 한국 기업 공시(DART) 계산 결과를 사용자 친화적인 한국어로 렌더링하는 분석가입니다.

[렌더링 규칙]
- CalculationResult의 rendered_value를 그대로 사용하세요. 숫자를 다시 계산하거나 형식을 바꾸지 마세요.
- operand label에 포함된 연도·기간 정보(예: '2024년', '2023년', '1분기')는 반드시 그대로 유지하세요. '2024년 영업이익'을 '영업이익'으로 줄이지 마세요.
- direction_hint가 제공된 경우, 그 단어를 그대로 사용하세요. 임의로 '변동', '차이' 등 중립적 표현으로 바꾸지 마세요.
- time_series 해석(상승·하락·반등 등)은 series 또는 derived_metrics의 수치 변화를 근거로 표현하세요.
- 데이터에 없는 새로운 연도, 금액, 비율을 만들지 마세요.
- 질문에 직접 답하는 1~2문장만 작성하세요.

질문:
{query}

Direction Hint (방향 판단 결과, 비어 있으면 무시):
{direction_hint}

CalculationPlan:
{plan_json}

CalculationResult:
{result_json}

Operands:
{operands_json}

반드시 final_answer만 채우세요.
"""
        )
        try:
            rendered: CalculationRenderOutput = (prompt | structured_llm).invoke(
                {
                    "query": self._calc_query(state),
                    "direction_hint": direction_hint,
                    "plan_json": json.dumps(plan, ensure_ascii=False, indent=2),
                    "result_json": json.dumps(calculation_result, ensure_ascii=False, indent=2),
                    "operands_json": json.dumps(operands, ensure_ascii=False, indent=2),
                }
            )
            answer = _normalise_spaces(rendered.final_answer)
        except Exception as exc:
            logger.warning("[calc_renderer] structured output failed, using deterministic fallback: %s", exc)
            answer = str(calculation_result.get("rendered_value") or calculation_result.get("formatted_result") or "").strip()
            if not answer:
                answer = "질문에 필요한 수치를 계산했지만 자연어 답변을 생성하지 못했습니다."

        calculation_result["formatted_result"] = answer
        return {
            "answer": answer,
            "compressed_answer": answer,
            "draft_points": [answer] if answer else [],
            "calculation_result": calculation_result,
        }

    def _verify_calculation_answer(self, state: FinancialAgentState) -> Dict[str, Any]:
        """Sanity-check that the rendered answer still matches the result."""
        answer = _normalise_spaces(str(state.get("answer") or state.get("compressed_answer") or ""))
        calculation_result = dict(state.get("calculation_result") or {})
        plan = dict(state.get("calculation_plan") or {})
        operands = list(state.get("calculation_operands", []) or [])

        if not answer:
            return {
                "answer": answer,
                "compressed_answer": answer,
            }

        if str(calculation_result.get("status") or "") != "ok":
            debug_trace = dict(state.get("calculation_debug_trace") or {})
            debug_trace["verification"] = {
                "verdict": "skip",
                "reason": "calculation_status_not_ok",
            }
            return {
                "answer": answer,
                "compressed_answer": answer,
                "calculation_debug_trace": debug_trace,
            }

        deterministic_fallback = str(
            calculation_result.get("formatted_result")
            or calculation_result.get("rendered_value")
            or answer
        ).strip()
        rendered_value = str(calculation_result.get("rendered_value") or "").strip()
        operation = str(plan.get("operation") or "")
        result_val = float(calculation_result.get("result_value") or 0)
        if operation == "growth_rate":
            direction_hint = "증가" if result_val > 0 else "감소" if result_val < 0 else "변동 없음"
        elif operation == "subtract":
            direction_hint = "더 큽니다" if result_val > 0 else "더 작습니다" if result_val < 0 else "동일합니다"
        else:
            direction_hint = ""
        structured_llm = self.llm.with_structured_output(CalculationVerificationOutput)
        prompt = ChatPromptTemplate.from_template(
            """당신은 재무 계산 답변 검증기입니다.
사용자에게 내보내기 직전의 계산 답변이 질문, 계산 결과, 피연산자와 모순이 없는지 검토하세요.

규칙:
- 새로운 숫자, 연도, 단위, 근거를 추가하지 마세요.
- 계산 결과와 질문 의도에 맞는다면 verdict=keep.
- 숫자, 단위, 방향, 비교 관계가 어긋나면 verdict=rewrite 로 두고 1~2문장으로 바로잡으세요.
- 답변이 계산 결과와 크게 모순되거나 불필요한 내용을 덧붙였으면 verdict=fallback 으로 두고 deterministic fallback과 같은 뜻으로 작성하세요.
- final_answer는 rendered_value와 direction_hint를 벗어나지 마세요.
- %p 질문이면 %p를 유지하세요.
- 단일 값 조회 질문이면 계산 과정 설명을 길게 덧붙이지 마세요.

질문:
{query}

현재 답변:
{answer}

Deterministic Fallback:
{fallback}

Direction Hint:
{direction_hint}

CalculationPlan:
{plan_json}

CalculationResult:
{result_json}

Operands:
{operands_json}
"""
        )
        try:
            verified: CalculationVerificationOutput = (prompt | structured_llm).invoke(
                {
                    "query": self._calc_query(state),
                    "answer": answer,
                    "fallback": deterministic_fallback,
                    "direction_hint": direction_hint,
                    "plan_json": json.dumps(plan, ensure_ascii=False, indent=2),
                    "result_json": json.dumps(calculation_result, ensure_ascii=False, indent=2),
                    "operands_json": json.dumps(operands, ensure_ascii=False, indent=2),
                }
            )
            verdict = str(verified.verdict or "keep")
            final_answer = _normalise_spaces(verified.final_answer)
            if verdict == "fallback" or not final_answer:
                final_answer = deterministic_fallback or answer
            calculation_result["formatted_result"] = final_answer
            debug_trace = dict(state.get("calculation_debug_trace") or {})
            debug_trace["verification"] = {
                "verdict": verdict,
                "issues": list(verified.issues or []),
                "input_answer": answer,
                "final_answer": final_answer,
                "rendered_value": rendered_value,
                "direction_hint": direction_hint,
            }
            return {
                "answer": final_answer,
                "compressed_answer": final_answer,
                "draft_points": [final_answer] if final_answer else [],
                "unsupported_sentences": [] if verdict == "keep" else [answer],
                "sentence_checks": [
                    {
                        "sentence": answer,
                        "verdict": "keep" if verdict == "keep" else "drop_overextended",
                        "reason": ",".join(verified.issues or []) or verdict,
                        "supporting_claim_ids": state.get("selected_claim_ids", []),
                    }
                ] if answer else [],
                "calculation_result": calculation_result,
                "calculation_debug_trace": debug_trace,
            }
        except Exception as exc:
            logger.warning("[calc_verify] structured output failed, keeping rendered answer: %s", exc)
            debug_trace = dict(state.get("calculation_debug_trace") or {})
            debug_trace["verification"] = {
                "verdict": "error_keep",
                "error": str(exc),
                "input_answer": answer,
                "rendered_value": rendered_value,
            }
            return {
                "answer": answer,
                "compressed_answer": answer,
                "calculation_debug_trace": debug_trace,
            }

    def _advance_calculation_subtask(self, state: FinancialAgentState) -> Dict[str, Any]:
        """Persist the finished subtask and move to the next one, if any."""
        current_result = self._capture_current_subtask_result(state)
        subtask_results = self._upsert_subtask_result(
            list(state.get("subtask_results") or []),
            current_result,
        )
        tasks = [dict(task) for task in (state.get("calc_subtasks") or [])]
        active_index = int(state.get("active_subtask_index") or 0)
        next_index = active_index + 1
        if next_index < len(tasks):
            next_task = dict(tasks[next_index])
            return {
                "subtask_results": subtask_results,
                "active_subtask_index": next_index,
                "active_subtask": next_task,
                "subtask_loop_complete": False,
                "subtask_debug_trace": {
                    **dict(state.get("subtask_debug_trace") or {}),
                    "last_completed_task_id": str(current_result.get("task_id") or ""),
                    "next_task_id": str(next_task.get("task_id") or ""),
                },
                "selected_claim_ids": [],
                "draft_points": [],
                "compressed_answer": "",
                "kept_claim_ids": [],
                "dropped_claim_ids": [],
                "unsupported_sentences": [],
                "sentence_checks": [],
                "answer": "",
                "citations": [],
                "calculation_operands": [],
                "calculation_plan": {},
                "calculation_result": {},
                "calculation_debug_trace": {},
                "planner_debug_trace": {},
                "missing_info": [],
                "reflection_count": 0,
                "retry_reason": "",
                "retry_queries": [],
                "reconciliation_retry_count": 0,
                "reflection_plan": {},
                "reconciliation_result": {},
            }
        return {
            "subtask_results": subtask_results,
            "subtask_loop_complete": True,
            "subtask_debug_trace": {
                **dict(state.get("subtask_debug_trace") or {}),
                "last_completed_task_id": str(current_result.get("task_id") or ""),
                "next_task_id": "",
            },
        }

    def _aggregate_calculation_subtasks(self, state: FinancialAgentState) -> Dict[str, Any]:
        """Combine completed subtask outputs into a single caller-facing view."""
        current_result = self._capture_current_subtask_result(state)
        subtask_results = self._upsert_subtask_result(
            list(state.get("subtask_results") or []),
            current_result,
        )
        order_map = {
            str(task.get("task_id") or ""): index
            for index, task in enumerate(state.get("calc_subtasks") or [])
        }
        ordered_results = sorted(
            subtask_results,
            key=lambda row: (order_map.get(str(row.get("task_id") or ""), 10_000), str(row.get("task_id") or "")),
        )
        answer_parts = [
            _normalise_spaces(str(row.get("answer") or ""))
            for row in ordered_results
            if _normalise_spaces(str(row.get("answer") or ""))
        ]
        final_answer = " ".join(answer_parts).strip() or _normalise_spaces(
            str(state.get("answer") or state.get("compressed_answer") or "")
        )
        selected_claim_ids = list(
            dict.fromkeys(
                claim_id
                for row in ordered_results
                for claim_id in (row.get("selected_claim_ids") or [])
                if str(claim_id).strip()
            )
        )
        artifacts = list(state.get("artifacts") or [])
        artifact_id = f"aggregate:{len(artifacts) + 1:03d}"
        artifacts = _append_artifact(
            artifacts,
            artifact_id=artifact_id,
            task_id="aggregate",
            kind=ArtifactKind.AGGREGATED_ANSWER,
            status="ok",
            summary=final_answer[:200],
            payload={
                "subtask_results": ordered_results,
                "final_answer": final_answer,
                **self._build_aggregate_calculation_projection(ordered_results, final_answer),
            },
            evidence_refs=selected_claim_ids,
        )
        aggregate_projection = self._build_aggregate_calculation_projection(ordered_results, final_answer)
        return {
            "subtask_results": ordered_results,
            "subtask_loop_complete": True,
            "answer": final_answer,
            "compressed_answer": final_answer,
            "draft_points": [final_answer] if final_answer else [],
            "selected_claim_ids": selected_claim_ids,
            "kept_claim_ids": selected_claim_ids,
            "dropped_claim_ids": [],
            "unsupported_sentences": [],
            "sentence_checks": [],
            "artifacts": artifacts,
            "calculation_operands": aggregate_projection["calculation_operands"],
            "calculation_plan": aggregate_projection["calculation_plan"],
            "calculation_result": aggregate_projection["calculation_result"],
        }

    def _prepare_reflection_retry(self, state: FinancialAgentState) -> Dict[str, Any]:
        current_count = int(state.get("reflection_count") or 0)
        operands = list(state.get("calculation_operands", []) or [])
        plan = dict(state.get("calculation_plan") or {})
        calc_result = dict(state.get("calculation_result") or {})
        reflection_plan = dict(state.get("reflection_plan") or {})

        missing_info = [
            str(item).strip()
            for item in (
                reflection_plan.get("missing_info")
                or plan.get("missing_info")
                or state.get("missing_info")
                or []
            )
            if str(item).strip()
        ]
        if not missing_info:
            missing_info = self._infer_missing_info(state, operands)
        retry_queries = self._finalize_retry_queries(state, reflection_plan, missing_info)
        retry_reason = (
            str(reflection_plan.get("explanation") or "")
            or str(plan.get("explanation") or "")
            or str(calc_result.get("explanation") or "")
            or str(state.get("retry_reason") or "")
            or "missing operands"
        )
        logger.info(
            "[reflection] trigger retry=%s missing_info=%s retry_queries=%s reason=%s",
            current_count + 1,
            missing_info,
            retry_queries,
            retry_reason,
        )
        return {
            "missing_info": missing_info,
            "reflection_count": current_count + 1,
            "retry_reason": retry_reason,
            "retry_queries": retry_queries,
            "evidence_bullets": [],
            "evidence_items": [],
            "evidence_status": "missing",
            "selected_claim_ids": [],
            "draft_points": [],
            "compressed_answer": "",
            "kept_claim_ids": [],
            "dropped_claim_ids": [],
            "unsupported_sentences": [],
            "sentence_checks": [],
            "answer": "",
            "citations": [],
            "calculation_operands": [],
            "calculation_plan": {},
            "calculation_result": {},
            "calculation_debug_trace": {},
            "planner_debug_trace": {},
            "reflection_plan": reflection_plan,
        }

    def _route_after_expand(self, state: FinancialAgentState) -> str:
        intent = state.get("intent") or state.get("query_type", "qa")
        if intent == "numeric_fact":
            return "numeric_extractor"
        return "evidence"

    def _route_after_evidence(self, state: FinancialAgentState) -> str:
        intent = state.get("intent") or state.get("query_type", "qa")
        if intent in {"comparison", "trend"}:
            return "reconcile_plan"
        return "compress"

    def _route_after_reconcile_plan(self, state: FinancialAgentState) -> str:
        result = dict(state.get("reconciliation_result") or {})
        status = str(result.get("status") or "ready")
        if status == "ready":
            return "operand_extractor"
        if status == "retry_retrieval":
            return "retrieve"
        return "advance_subtask"

    def _route_after_advance_subtask(self, state: FinancialAgentState) -> str:
        if bool(state.get("subtask_loop_complete")):
            return "aggregate_subtasks"
        return "reconcile_plan"

    def _route_after_formula_planner(self, state: FinancialAgentState) -> str:
        if not self._is_reflection_eligible(state):
            return "calculator"
        if int(state.get("reflection_count") or 0) >= 1:
            return "calculator"
        plan = dict(state.get("calculation_plan") or {})
        status = str(plan.get("status") or "ok").lower()
        if status == "incomplete":
            return "reflection_replan"
        return "calculator"

    def _route_after_calculator(self, state: FinancialAgentState) -> str:
        if not self._is_reflection_eligible(state):
            return "calc_render"
        if int(state.get("reflection_count") or 0) >= 1:
            return "calc_render"
        result = dict(state.get("calculation_result") or {})
        status = str(result.get("status") or "")
        if status in {"insufficient_operands", "parse_error"}:
            return "reflection_replan"
        return "calc_render"

    def _format_citations(self, state: FinancialAgentState) -> Dict[str, Any]:
        seen = set()
        citations: List[str] = []
        for doc, score in state.get("retrieved_docs", []):
            metadata = doc.metadata or {}
            key = (
                metadata.get("company"),
                metadata.get("year"),
                metadata.get("section_path"),
                metadata.get("chunk_uid"),
            )
            if key in seen:
                continue
            seen.add(key)
            citations.append(
                f"[{metadata.get('company', '?')}] {metadata.get('year', '?')}년 "
                f"{metadata.get('report_type', '?')} / {metadata.get('section_path', metadata.get('section', '?'))} "
                f"/ {metadata.get('block_type', '?')} (score: {score:.3f})"
            )
        return {"citations": citations}

