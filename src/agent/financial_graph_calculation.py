"""Semantic calculation-program nodes for the financial graph."""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional

from src.agent.financial_calculation_execution import (
    execute_semantic_calculation_program,
    project_semantic_program_operand,
    validate_semantic_calculation_program,
)
from src.agent.financial_graph_model_loaders import semantic_calculation_program_model
from src.agent.financial_graph_state import FinancialAgentState
from src.agent.financial_langchain_loaders import chat_prompt_template_from_template
from src.agent.financial_reconciliation_candidates import (
    build_semantic_candidate_catalog,
    build_semantic_source_candidates,
    select_semantic_prompt_candidates,
    semantic_candidate_catalog_fingerprint,
    semantic_candidate_stage_diagnostics,
)
from src.agent.financial_runtime_normalization import _normalise_spaces
from src.agent.financial_runtime_trace import resolve_runtime_calculation_trace, runtime_trace_state_update
from src.agent.financial_scope_policies import is_scope_only_period_surface
from src.agent.financial_task_artifacts import (
    calculation_plan_artifact_update,
    calculation_result_artifact_update,
    operand_set_artifact_update,
)
from src.config.retrieval_policy import CALCULATION_PROMPT_POLICY


logger = logging.getLogger(__name__)


def _semantic_obligation_relevance_groups(
    obligations: List[Dict[str, Any]],
    *,
    owner_kind: Optional[str] = None,
) -> List[List[str]]:
    groups: List[List[str]] = []
    for obligation in obligations:
        obligation_owner = (
            "narrative"
            if str(obligation.get("kind") or "") == "narrative"
            else "numeric"
        )
        if owner_kind and obligation_owner != owner_kind:
            continue
        scope = dict(obligation.get("scope") or {})
        values = [
            str(obligation.get("label") or ""),
            *[str(item) for item in (obligation.get("retrieval_hints") or [])],
            *[str(item) for item in (obligation.get("concept_hints") or [])],
            str(scope.get("segment") or ""),
            str(scope.get("basis") or ""),
        ]
        group = list(
            dict.fromkeys(
                _normalise_spaces(item)
                for item in values
                if _normalise_spaces(item)
                and not is_scope_only_period_surface(item, scope)
            )
        )
        if group:
            groups.append(group)
        for requirement in obligation.get("evidence_requirements") or []:
            requirement_scope = dict(requirement.get("scope") or {})
            effective_requirement_scope = {**scope, **requirement_scope}
            requirement_values = [
                str(requirement.get("label") or ""),
                *[str(item) for item in (requirement.get("retrieval_hints") or [])],
                *[str(item) for item in (requirement.get("concept_hints") or [])],
                str(requirement_scope.get("period") or ""),
                str(requirement_scope.get("segment") or ""),
                str(requirement_scope.get("basis") or ""),
            ]
            requirement_group = list(
                dict.fromkeys(
                    _normalise_spaces(item)
                    for item in requirement_values
                    if _normalise_spaces(item)
                    and not is_scope_only_period_surface(
                        item,
                        effective_requirement_scope,
                    )
                )
            )
            if requirement_group:
                groups.append(requirement_group)
    return groups


def _semantic_required_evidence_relevance_groups(
    obligations: List[Dict[str, Any]],
    *,
    owner_kind: Optional[str] = None,
) -> List[List[str]]:
    """Return only required input groups, without their parent output surface."""

    groups: List[List[str]] = []
    for obligation in obligations:
        obligation_owner = (
            "narrative"
            if str(obligation.get("kind") or "") == "narrative"
            else "numeric"
        )
        if owner_kind and obligation_owner != owner_kind:
            continue
        obligation_scope = dict(obligation.get("scope") or {})
        for requirement in obligation.get("evidence_requirements") or []:
            if not bool(requirement.get("required", True)):
                continue
            requirement_scope = dict(requirement.get("scope") or {})
            effective_requirement_scope = {
                **obligation_scope,
                **requirement_scope,
            }
            values = [
                str(requirement.get("label") or ""),
                *[str(item) for item in (requirement.get("retrieval_hints") or [])],
                *[str(item) for item in (requirement.get("concept_hints") or [])],
                str(requirement_scope.get("period") or ""),
                str(requirement_scope.get("segment") or ""),
                str(requirement_scope.get("basis") or ""),
            ]
            group = list(
                dict.fromkeys(
                    _normalise_spaces(item)
                    for item in values
                    if _normalise_spaces(item)
                    and not is_scope_only_period_surface(
                        item,
                        effective_requirement_scope,
                    )
                )
            )
            if group:
                groups.append(group)
    return groups


def _bounded_relevance_excerpt(
    source_text: str,
    focus_texts: List[str],
    *,
    limit: int,
) -> str:
    """Return a bounded source excerpt centered on its strongest visible hint."""

    text = _normalise_spaces(str(source_text or ""))
    bounded = max(0, int(limit))
    if not bounded or len(text) <= bounded:
        return text
    normalized_focus = list(
        dict.fromkeys(
            value
            for item in focus_texts
            for value in [
                _normalise_spaces(str(item or "")).lower(),
                *[
                    token.lower()
                    for token in re.findall(
                        r"[^\W_]+",
                        _normalise_spaces(str(item or "")),
                        flags=re.UNICODE,
                    )
                    if len(token) >= 2
                ],
            ]
            if value
        )
    )
    lowered = text.lower()
    matches = [
        (len(focus), lowered.find(focus), focus)
        for focus in normalized_focus
        if lowered.find(focus) >= 0
    ]
    if not matches:
        return text[:bounded]
    _length, position, focus = max(matches, key=lambda item: (item[0], -item[1]))
    center = position + len(focus) // 2
    start = max(0, center - bounded // 3)
    start = min(start, max(0, len(text) - bounded))
    return text[start : start + bounded]


def _merge_targeted_program_retry(
    *,
    previous_validation: Dict[str, Any],
    retry_program: Dict[str, Any],
    target_obligation_ids: List[str],
) -> Dict[str, Any]:
    """Preserve valid prior outputs and accept retry edits only for targets."""

    targets = {
        str(item).strip() for item in target_obligation_ids if str(item).strip()
    }

    def merged_rows(validation_key: str, program_key: str) -> List[Dict[str, Any]]:
        preserved = [
            dict(item)
            for item in previous_validation.get(validation_key) or []
            if str((item or {}).get("obligation_id") or "").strip() not in targets
        ]
        replacements = [
            dict(item)
            for item in retry_program.get(program_key) or []
            if str((item or {}).get("obligation_id") or "").strip() in targets
        ]
        return [*preserved, *replacements]

    return {
        "status": str(retry_program.get("status") or "incomplete"),
        "direct_bindings": merged_rows(
            "valid_direct_bindings", "direct_bindings"
        ),
        "expressions": merged_rows("valid_expressions", "expressions"),
        "narrative_bindings": merged_rows(
            "valid_narrative_bindings", "narrative_bindings"
        ),
        "missing_obligation_ids": [
            str(item)
            for item in retry_program.get("missing_obligation_ids") or []
            if str(item).strip() in targets
        ],
        "ambiguous_obligation_ids": [
            str(item)
            for item in retry_program.get("ambiguous_obligation_ids") or []
            if str(item).strip() in targets
        ],
        "rationale": str(retry_program.get("rationale") or ""),
    }


def _semantic_program_candidate_ids(program: Dict[str, Any]) -> List[str]:
    values: List[str] = []
    for binding in program.get("direct_bindings") or []:
        if not isinstance(binding, dict):
            continue
        values.append(str(binding.get("candidate_id") or ""))
        values.extend(
            str(item or "")
            for item in (binding.get("compatibility_candidate_ids") or [])
        )
    for expression in program.get("expressions") or []:
        if not isinstance(expression, dict):
            continue
        values.extend(
            str(item.get("source_id") or "")
            for item in (expression.get("variable_bindings") or [])
            if isinstance(item, dict)
        )
        values.append(str(expression.get("source_display_candidate_id") or ""))
        values.extend(
            str(item or "")
            for item in (expression.get("compatibility_candidate_ids") or [])
        )
    for binding in program.get("narrative_bindings") or []:
        if isinstance(binding, dict):
            values.extend(str(item or "") for item in (binding.get("candidate_ids") or []))
    return list(dict.fromkeys(item for item in values if item))


class FinancialAgentCalculationMixin:
    """Compile and execute one grounded program for all answer obligations."""

    def _operand_set_artifact_update(
        self,
        state: FinancialAgentState,
        active_subtask: Dict[str, Any],
        operand_rows: List[Dict[str, Any]],
        *,
        status: str,
        summary: str,
        payload: Dict[str, Any],
        evidence_refs: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        task_id = str(active_subtask.get("task_id") or "task_1")
        return operand_set_artifact_update(
            tasks=list(state.get("tasks") or []),
            artifacts=list(state.get("artifacts") or []),
            task_id=task_id,
            task_label=str(active_subtask.get("metric_label") or task_id),
            query=self._calc_query(state),
            metric_family="semantic_program",
            operand_rows=operand_rows,
            status=status,
            summary=summary,
            payload=payload,
            evidence_refs=evidence_refs,
        )

    def _calculation_plan_artifact_update(
        self,
        state: FinancialAgentState,
        calculation_plan: Dict[str, Any],
    ) -> Dict[str, Any]:
        active_subtask = dict(state.get("active_subtask") or {})
        task_id = str(active_subtask.get("task_id") or "task_1")
        return calculation_plan_artifact_update(
            tasks=list(state.get("tasks") or []),
            artifacts=list(state.get("artifacts") or []),
            task_id=task_id,
            task_label=str(active_subtask.get("metric_label") or task_id),
            query=self._calc_query(state),
            metric_family="semantic_program",
            calculation_plan=calculation_plan,
        )

    def _semantic_source_candidates_for_state(
        self,
        state: FinancialAgentState,
    ) -> List[Dict[str, Any]]:
        return build_semantic_source_candidates(
            state,
            source_anchor_builder=self._build_source_anchor,
        )

    def _semantic_candidate_catalog_for_state(
        self,
        state: FinancialAgentState,
        *,
        source_candidates: Optional[List[Dict[str, Any]]] = None,
    ) -> List[Dict[str, Any]]:
        obligations = [
            dict(item)
            for item in (
                state.get("answer_obligations")
                or dict(state.get("semantic_plan") or {}).get("answer_obligations")
                or []
            )
            if isinstance(item, dict)
        ]
        relevance_groups = _semantic_obligation_relevance_groups(obligations)
        relevance_texts = [item for group in relevance_groups for item in group]
        return build_semantic_candidate_catalog(
            source_candidates
            if source_candidates is not None
            else self._semantic_source_candidates_for_state(state),
            evidence_items=list(state.get("evidence_items") or []),
            relevance_texts=list(dict.fromkeys(item for item in relevance_texts if item)),
        )

    @staticmethod
    def _semantic_program_prompt_rows(
        catalog: List[Dict[str, Any]],
        relevance_groups: Optional[List[List[str]]] = None,
        numeric_relevance_groups: Optional[List[List[str]]] = None,
        narrative_relevance_groups: Optional[List[List[str]]] = None,
        required_numeric_relevance_groups: Optional[List[List[str]]] = None,
        required_narrative_relevance_groups: Optional[List[List[str]]] = None,
    ) -> List[Dict[str, Any]]:
        limits = dict(CALCULATION_PROMPT_POLICY.get("semantic_program_prompt_limits") or {})
        numeric_limit = max(0, int(limits.get("numeric_candidates") or 48))
        narrative_limit = max(0, int(limits.get("narrative_candidates") or 16))
        required_group_limit = max(
            0,
            int(limits.get("required_input_candidates_per_group", 4)),
        )
        relevance_groups = list(relevance_groups or [])
        selected = select_semantic_prompt_candidates(
            catalog,
            relevance_groups=relevance_groups,
            numeric_relevance_groups=numeric_relevance_groups,
            narrative_relevance_groups=narrative_relevance_groups,
            required_numeric_relevance_groups=required_numeric_relevance_groups,
            required_narrative_relevance_groups=required_narrative_relevance_groups,
            max_numeric_candidates=numeric_limit,
            max_narrative_candidates=narrative_limit,
            max_required_candidates_per_group=required_group_limit,
        )
        numeric_groups = (
            relevance_groups
            if numeric_relevance_groups is None
            else list(numeric_relevance_groups)
        )
        narrative_groups = (
            relevance_groups
            if narrative_relevance_groups is None
            else list(narrative_relevance_groups)
        )
        prompt_rows = [
            {
                "candidate_id": str(item.get("candidate_id") or ""),
                "kind": str(item.get("kind") or ""),
                "row_label": str(item.get("row_label") or ""),
                "column_headers": list(item.get("column_headers") or []),
                "raw_value": str(item.get("raw_value") or ""),
                "raw_unit": str(item.get("raw_unit") or ""),
                "normalized_unit": str(item.get("normalized_unit") or ""),
                "period": str(item.get("period") or ""),
                "year": item.get("year"),
                "value_year": item.get("value_year"),
                "company": str(item.get("company") or ""),
                "consolidation_scope": str(item.get("consolidation_scope") or ""),
                "consolidation_scope_source": str(
                    item.get("consolidation_scope_source") or ""
                ),
                "segment": str(item.get("segment") or ""),
                "basis": str(item.get("basis") or ""),
                "value_role": str(item.get("value_role") or ""),
                "statement_type": str(item.get("statement_type") or ""),
                "table_source_id": str(item.get("table_source_id") or ""),
                "context_fingerprint": str(item.get("context_fingerprint") or ""),
                "source_anchor": str(item.get("source_anchor") or ""),
                "candidate_kind": str(item.get("candidate_kind") or ""),
                "aggregation_stage": str(item.get("aggregation_stage") or ""),
                "aggregate_label": str(item.get("aggregate_label") or ""),
                "source_text": _bounded_relevance_excerpt(
                    str(item.get("source_text") or ""),
                    [
                        str(item.get("row_label") or ""),
                        str(item.get("raw_value") or ""),
                        *[
                            value
                            for group in (
                                numeric_groups
                                if str(item.get("kind") or "") == "numeric"
                                else narrative_groups
                            )
                            for value in group
                        ],
                    ],
                    limit=max(
                        0,
                        int(
                            limits.get(
                                "numeric_source_chars"
                                if str(item.get("kind") or "") == "numeric"
                                else "narrative_source_chars"
                            )
                            or (
                                280
                                if str(item.get("kind") or "") == "numeric"
                                else 600
                            )
                        ),
                    ),
                ),
            }
            for item in selected
        ]
        return prompt_rows

    @staticmethod
    def _semantic_program_prompt_catalog(catalog: List[Dict[str, Any]]) -> str:
        return json.dumps(
            FinancialAgentCalculationMixin._semantic_program_prompt_rows(catalog),
            ensure_ascii=False,
            indent=2,
        )

    @staticmethod
    def _semantic_program_evidence_items(
        catalog: List[Dict[str, Any]],
        selected_candidate_ids: List[str],
    ) -> List[Dict[str, Any]]:
        candidate_by_id = {
            str(item.get("candidate_id") or ""): dict(item)
            for item in catalog
            if str(item.get("candidate_id") or "")
        }
        rows: List[Dict[str, Any]] = []
        for candidate_id in dict.fromkeys(selected_candidate_ids):
            candidate = candidate_by_id.get(str(candidate_id or ""))
            if not candidate:
                continue
            source_text = _normalise_spaces(str(candidate.get("source_text") or ""))
            numeric_surface = _normalise_spaces(
                " ".join(
                    str(value or "")
                    for value in (
                        candidate.get("row_label"),
                        " / ".join(str(item) for item in (candidate.get("column_headers") or [])),
                        candidate.get("raw_value"),
                        candidate.get("raw_unit"),
                    )
                    if str(value or "").strip()
                )
            )
            claim = source_text or numeric_surface
            rows.append(
                {
                    "evidence_id": str(candidate_id),
                    "source_anchor": str(candidate.get("source_anchor") or ""),
                    "claim": claim,
                    "quote_span": source_text or numeric_surface,
                    "support_level": "direct",
                    "question_relevance": "high",
                    "raw_value": str(candidate.get("raw_value") or ""),
                    "raw_unit": str(candidate.get("raw_unit") or ""),
                    "source_row_id": str(candidate.get("source_row_id") or ""),
                    "source_candidate_id": str(candidate.get("source_candidate_id") or ""),
                    "metadata": {
                        key: candidate.get(key)
                        for key in (
                            "company", "year", "value_year", "period",
                            "consolidation_scope", "consolidation_scope_source", "segment",
                            "basis", "table_source_id", "statement_type", "context_fingerprint",
                        )
                        if candidate.get(key) not in (None, "")
                    },
                }
            )
        return rows

    def _compile_semantic_calculation_program(
        self,
        state: FinancialAgentState,
    ) -> Dict[str, Any]:
        """Select catalog IDs and compile all obligations in one model call."""

        obligations = [
            dict(item)
            for item in (
                state.get("answer_obligations")
                or dict(state.get("semantic_plan") or {}).get("answer_obligations")
                or []
            )
            if isinstance(item, dict)
        ]
        query = str(state.get("query") or "")
        source_candidates = self._semantic_source_candidates_for_state(state)
        catalog = self._semantic_candidate_catalog_for_state(
            state,
            source_candidates=source_candidates,
        )
        relevance_groups = _semantic_obligation_relevance_groups(obligations)
        numeric_relevance_groups = _semantic_obligation_relevance_groups(
            obligations,
            owner_kind="numeric",
        )
        narrative_relevance_groups = _semantic_obligation_relevance_groups(
            obligations,
            owner_kind="narrative",
        )
        required_numeric_relevance_groups = (
            _semantic_required_evidence_relevance_groups(
                obligations,
                owner_kind="numeric",
            )
        )
        required_narrative_relevance_groups = (
            _semantic_required_evidence_relevance_groups(
                obligations,
                owner_kind="narrative",
            )
        )
        prompt_catalog_rows = self._semantic_program_prompt_rows(
            catalog,
            relevance_groups=relevance_groups,
            numeric_relevance_groups=numeric_relevance_groups,
            narrative_relevance_groups=narrative_relevance_groups,
            required_numeric_relevance_groups=required_numeric_relevance_groups,
            required_narrative_relevance_groups=required_narrative_relevance_groups,
        )
        prompt_catalog_json = json.dumps(prompt_catalog_rows, ensure_ascii=False, indent=2)
        prompt_candidate_ids = [
            str(item.get("candidate_id") or "")
            for item in prompt_catalog_rows
            if str(item.get("candidate_id") or "")
        ]
        candidate_by_id = {
            str(item.get("candidate_id") or ""): dict(item)
            for item in catalog
            if str(item.get("candidate_id") or "")
        }
        prompt_source_catalog_rows = [
            candidate_by_id[candidate_id]
            for candidate_id in prompt_candidate_ids
            if candidate_id in candidate_by_id
        ]
        candidate_stage_diagnostics = semantic_candidate_stage_diagnostics(
            state=state,
            source_candidates=source_candidates,
            catalog=catalog,
            prompt_catalog=prompt_source_catalog_rows,
        )
        required_ids = [
            str(item.get("obligation_id") or "")
            for item in obligations
            if bool(item.get("required", True)) and str(item.get("obligation_id") or "")
        ]
        program_data: Dict[str, Any] = {
            "status": "incomplete",
            "direct_bindings": [],
            "expressions": [],
            "narrative_bindings": [],
            "missing_obligation_ids": required_ids,
            "ambiguous_obligation_ids": [],
            "rationale": "no answer obligations" if not obligations else "",
        }
        validation = validate_semantic_calculation_program(
            program=program_data,
            obligations=obligations,
            candidate_catalog=catalog,
            query=query,
            selectable_candidate_ids=prompt_candidate_ids,
        )
        retry_count = 0
        invocation_errors: List[str] = []
        validation_history: List[Dict[str, Any]] = []
        catalog_candidate_ids = set(candidate_by_id)
        if obligations:
            structured_llm = self._llm_for_phase("program_compilation").with_structured_output(
                semantic_calculation_program_model()
            )
            prompt = chat_prompt_template_from_template(
                str(CALCULATION_PROMPT_POLICY.get("semantic_program_prompt_template") or "")
            )
            retry_feedback = "-"
            retry_target_ids: List[str] = []
            previous_validation: Dict[str, Any] = {}
            for attempt in range(2):
                try:
                    prompt_obligations = (
                        [
                            item
                            for item in obligations
                            if str(item.get("obligation_id") or "")
                            in set(retry_target_ids)
                        ]
                        if attempt and retry_target_ids
                        else obligations
                    )
                    prompt_value = prompt.invoke(
                        {
                            "query": query,
                            "obligations": json.dumps(
                                prompt_obligations,
                                ensure_ascii=False,
                                indent=2,
                            ),
                            "candidate_catalog": prompt_catalog_json,
                            "retry_feedback": retry_feedback,
                        }
                    )
                    compiled: Any = structured_llm.invoke(prompt_value)
                    compiled_program = compiled.model_dump()
                    program_data = (
                        _merge_targeted_program_retry(
                            previous_validation=previous_validation,
                            retry_program=compiled_program,
                            target_obligation_ids=retry_target_ids,
                        )
                        if attempt and retry_target_ids
                        else compiled_program
                    )
                except Exception as exc:
                    invocation_errors.append(str(exc))
                    program_data = {
                        "status": "incomplete",
                        "direct_bindings": [],
                        "expressions": [],
                        "narrative_bindings": [],
                        "missing_obligation_ids": required_ids,
                        "ambiguous_obligation_ids": [],
                        "rationale": str(exc),
                    }
                validation = validate_semantic_calculation_program(
                    program=program_data,
                    obligations=obligations,
                    candidate_catalog=catalog,
                    query=query,
                    selectable_candidate_ids=prompt_candidate_ids,
                )
                proposed_ids = [
                    item
                    for item in _semantic_program_candidate_ids(program_data)
                    if item in catalog_candidate_ids
                ]
                validation_history.append(
                    {
                        "attempt": attempt + 1,
                        "status": str(validation.get("status") or ""),
                        "errors": list(validation.get("errors") or []),
                        "missing_obligation_ids": list(
                            validation.get("missing_obligation_ids") or []
                        ),
                        "ambiguous_obligation_ids": list(
                            validation.get("ambiguous_obligation_ids") or []
                        ),
                        "proposed_candidate_ids": proposed_ids,
                    }
                )
                retry_target_ids = list(
                    dict.fromkeys(
                        [
                            *list(validation.get("missing_obligation_ids") or []),
                            *list(validation.get("ambiguous_obligation_ids") or []),
                        ]
                    )
                )
                needs_retry = (
                    str(validation.get("status") or "") != "ready"
                    and bool(retry_target_ids)
                )
                if not needs_retry or attempt == 1:
                    break
                retry_count = 1
                previous_validation = dict(validation)
                target_id_set = set(retry_target_ids)
                evidence_requirement_ids_by_obligation = {
                    str(item.get("obligation_id") or ""): [
                        str(requirement.get("requirement_id") or "")
                        for requirement in (item.get("evidence_requirements") or [])
                        if bool(requirement.get("required", True))
                        and str(requirement.get("requirement_id") or "")
                    ]
                    for item in obligations
                    if str(item.get("obligation_id") or "") in target_id_set
                }
                validation_errors_by_obligation = {
                    obligation_id: [
                        dict(item)
                        for item in (validation.get("errors") or [])
                        if str((item or {}).get("obligation_id") or "")
                        == obligation_id
                    ]
                    for obligation_id in retry_target_ids
                }
                retry_feedback = json.dumps(
                    {
                        "previous_program": program_data,
                        "missing_obligation_ids": list(validation.get("missing_obligation_ids") or []),
                        "ambiguous_obligation_ids": list(validation.get("ambiguous_obligation_ids") or []),
                        "validation_errors": list(validation.get("errors") or []),
                        "allowed_candidate_ids": prompt_candidate_ids,
                        "declared_obligation_ids": [
                            str(item.get("obligation_id") or "")
                            for item in obligations
                            if str(item.get("obligation_id") or "")
                        ],
                        "declared_evidence_requirement_ids": [
                            str(requirement.get("requirement_id") or "")
                            for item in obligations
                            for requirement in (item.get("evidence_requirements") or [])
                            if str(requirement.get("requirement_id") or "")
                        ],
                        "repair_contract": {
                            "target_obligation_ids": retry_target_ids,
                            "evidence_requirement_ids_by_obligation": (
                                evidence_requirement_ids_by_obligation
                            ),
                            "validation_errors_by_obligation": (
                                validation_errors_by_obligation
                            ),
                            "formula_variable_binding_invariant": (
                                "The set of formula AST variable names must be "
                                "exactly equal to the set of variable_bindings.variable values."
                            ),
                            "candidate_requirement_binding_invariant": (
                                "Every candidate source must bind one requirement ID "
                                "declared for the same target obligation."
                            ),
                            "required_evidence_binding_invariant": (
                                "Bind every required evidence requirement exactly once; "
                                "do not invent candidate, obligation, or requirement IDs."
                            ),
                        },
                        "instruction": "Only repair the listed obligations; retain grounded valid outputs.",
                    },
                    ensure_ascii=False,
                    indent=2,
                )

        selected_candidate_ids = list(validation.get("selected_candidate_ids") or [])
        selected_candidates = [candidate_by_id[item] for item in selected_candidate_ids if item in candidate_by_id]
        proposed_candidate_ids = [
            item
            for item in _semantic_program_candidate_ids(program_data)
            if item in candidate_by_id
        ]
        proposed_candidates = [
            candidate_by_id[item]
            for item in proposed_candidate_ids
            if item in candidate_by_id
        ]
        obligation_by_id = {
            str(item.get("obligation_id") or ""): item
            for item in obligations
            if str(item.get("obligation_id") or "")
        }
        direct_binding_by_candidate_id: Dict[str, Dict[str, Any]] = {}
        for binding in validation.get("valid_direct_bindings") or []:
            candidate_id = str(binding.get("candidate_id") or "")
            if candidate_id and candidate_id not in direct_binding_by_candidate_id:
                direct_binding_by_candidate_id[candidate_id] = dict(binding)
        operand_rows: List[Dict[str, Any]] = []
        for item in selected_candidates:
            if str(item.get("kind") or "") != "numeric":
                continue
            candidate_id = str(item.get("candidate_id") or "")
            binding = direct_binding_by_candidate_id.get(candidate_id)
            obligation_id = str((binding or {}).get("obligation_id") or "")
            operand_rows.append(
                project_semantic_program_operand(
                    item,
                    obligation_id=obligation_id,
                    obligation=obligation_by_id.get(obligation_id),
                    validated_binding=binding,
                )
            )
        calculation_plan = {
            "status": "ok" if validation.get("status") == "ready" else "incomplete",
            "mode": "semantic_program",
            "operation": "semantic_program",
            "ordered_operand_ids": [str(item.get("operand_id") or "") for item in operand_rows],
            "program_mode": "semantic_program",
            "answer_obligations": obligations,
            "semantic_program": program_data,
            "program_validation": validation,
            "program_validation_history": validation_history,
            "program_retry_count": retry_count,
            "candidate_catalog_fingerprint": semantic_candidate_catalog_fingerprint(catalog),
            "candidate_count": len(catalog),
            "prompt_candidate_count": len(prompt_catalog_rows),
            "prompt_candidate_ids": prompt_candidate_ids,
            "prompt_candidate_strategy": "required_input_local_cohort_relevance_v3",
            "prompt_excerpt_strategy": "bounded_relevance_window_v1",
            "candidate_stage_diagnostics": candidate_stage_diagnostics,
            "proposed_candidates": proposed_candidates,
            "selected_candidates": selected_candidates,
            "explanation": str(program_data.get("rationale") or ""),
            "missing_info": list(validation.get("missing_obligation_ids") or []),
        }
        active_subtask = dict(state.get("active_subtask") or {})
        operand_update = self._operand_set_artifact_update(
            state,
            active_subtask,
            operand_rows,
            status="sufficient" if validation.get("status") == "ready" else "partial",
            summary=f"{len(operand_rows)} grounded semantic-program operand(s)",
            payload={
                "calculation_operands": operand_rows,
                "candidate_catalog_fingerprint": calculation_plan["candidate_catalog_fingerprint"],
                "candidate_count": len(catalog),
                "prompt_candidate_count": len(prompt_catalog_rows),
                "prompt_candidate_strategy": "required_input_local_cohort_relevance_v3",
                "prompt_excerpt_strategy": "bounded_relevance_window_v1",
                "candidate_stage_diagnostics": candidate_stage_diagnostics,
                "selected_candidate_ids": selected_candidate_ids,
                "semantic_status": str(validation.get("status") or ""),
                "missing_obligation_ids": list(
                    validation.get("missing_obligation_ids") or []
                ),
            },
            evidence_refs=selected_candidate_ids,
        )
        plan_update = self._calculation_plan_artifact_update(
            {**dict(state), **operand_update},
            calculation_plan,
        )
        trace_update = runtime_trace_state_update(
            state,
            calculation_operands=operand_rows,
            calculation_plan=calculation_plan,
            calculation_result={},
        )
        logger.info(
            "[semantic_program] compile status=%s candidates=%s selected=%s retry=%s errors=%s",
            validation.get("status"), len(catalog), len(selected_candidate_ids), retry_count,
            len(validation.get("errors") or []),
        )
        return {
            **trace_update,
            "answer_obligations": obligations,
            "semantic_candidate_catalog": catalog,
            "semantic_program": program_data,
            "semantic_program_validation": validation,
            "semantic_program_retry_count": retry_count,
            "missing_info": list(validation.get("missing_obligation_ids") or []),
            "planner_debug_trace": {
                **dict(state.get("planner_debug_trace") or {}),
                "program_compiler_invoked": bool(obligations),
                "program_compiler_retry_count": retry_count,
                "candidate_count": len(catalog),
                "prompt_candidate_count": len(prompt_catalog_rows),
                "candidate_stage_diagnostics_schema": str(
                    candidate_stage_diagnostics.get("schema") or ""
                ),
                "selected_candidate_count": len(selected_candidate_ids),
                "program_validation_status": str(validation.get("status") or ""),
                "program_validation_errors": list(validation.get("errors") or []),
                "program_validation_history": validation_history,
                "program_invocation_errors": invocation_errors,
            },
            "tasks": list(plan_update["tasks"]),
            "artifacts": list(plan_update["artifacts"]),
        }

    def _execute_semantic_calculation_program(
        self,
        state: FinancialAgentState,
    ) -> Dict[str, Any]:
        obligations = [dict(item) for item in (state.get("answer_obligations") or [])]
        catalog = [dict(item) for item in (state.get("semantic_candidate_catalog") or [])]
        current_trace = resolve_runtime_calculation_trace(
            dict(state),
            allow_legacy_top_level=False,
        )
        calculation_plan = dict(current_trace.get("calculation_plan") or {})
        selectable_candidate_ids = (
            list(calculation_plan.get("prompt_candidate_ids") or [])
            if "prompt_candidate_ids" in calculation_plan
            else None
        )
        execution = execute_semantic_calculation_program(
            program=dict(state.get("semantic_program") or {}),
            obligations=obligations,
            candidate_catalog=catalog,
            query=str(state.get("query") or ""),
            selectable_candidate_ids=selectable_candidate_ids,
        )
        calculation_operands = list(execution.get("calculation_operands") or [])
        calculation_result = dict(execution.get("calculation_result") or {})
        derived_operation_family = str(
            dict(calculation_result.get("derived_metrics") or {}).get(
                "operation_family"
            )
            or "formula"
        )
        calculation_plan = {
            **calculation_plan,
            "operation_family": derived_operation_family,
        }
        calculation_result = {
            **calculation_result,
            "operation_family": derived_operation_family,
        }
        selected_candidate_ids = list(execution.get("selected_candidate_ids") or [])
        evidence_items = self._semantic_program_evidence_items(catalog, selected_candidate_ids)

        output_rows: List[Dict[str, Any]] = []
        for output in execution.get("outputs") or []:
            obligation_id = str(output.get("obligation_id") or "")
            answer_text = (
                str(output.get("text") or "")
                if str(output.get("kind") or "") == "narrative"
                else f"{str(output.get('label') or obligation_id)}: {str(output.get('rendered_value') or '')}"
            )
            output_rows.append(
                {
                    "task_id": f"task_1:{obligation_id}",
                    "metric_family": "semantic_program",
                    "metric_label": str(output.get("label") or obligation_id),
                    "operation_family": str(output.get("operation_family") or "formula"),
                    "status": str(output.get("status") or "ok"),
                    "answer": _normalise_spaces(answer_text),
                    "calculation_result": {
                        "status": str(output.get("status") or "ok"),
                        "operation_family": str(
                            output.get("operation_family") or "formula"
                        ),
                        "result_value": output.get("normalized_value"),
                        "result_unit": str(output.get("result_unit") or ""),
                        "rendered_value": str(output.get("rendered_value") or ""),
                        "answer_slots": (
                            {
                                "operation_family": (
                                    "lookup"
                                    if str(output.get("operation_family") or "")
                                    == "lookup"
                                    else "single_value"
                                ),
                                "metric_label": str(output.get("label") or obligation_id),
                                "primary_value": dict(output.get("answer_slot") or {}),
                            }
                            if output.get("answer_slot")
                            else {}
                        ),
                        "derived_metrics": {
                            "operation_family": str(
                                output.get("operation_family") or "formula"
                            )
                        },
                        "source_row_ids": list(output.get("source_row_ids") or []),
                    },
                    "source_row_ids": list(output.get("source_row_ids") or []),
                    "source_evidence_ids": list(output.get("candidate_ids") or []),
                }
            )

        answer = _normalise_spaces(str(execution.get("answer") or ""))
        structured_result = {
            "status": str(execution.get("status") or "incomplete"),
            "answer": answer,
            "final_answer": answer,
            "subtask_results": output_rows,
            "answer_obligations": obligations,
            "missing_obligation_ids": list(execution.get("missing_obligation_ids") or []),
            "resolved_calculation_trace": {
                "calculation_operands": calculation_operands,
                "calculation_plan": calculation_plan,
                "calculation_result": calculation_result,
            },
        }
        active_subtask = dict(state.get("active_subtask") or {})
        task_id = str(active_subtask.get("task_id") or "task_1")
        result_update = calculation_result_artifact_update(
            tasks=list(state.get("tasks") or []),
            artifacts=list(state.get("artifacts") or []),
            task_id=task_id,
            task_label=str(active_subtask.get("metric_label") or task_id),
            query=self._calc_query(state),
            metric_family="semantic_program",
            calculation_result=calculation_result,
            evidence_refs=selected_candidate_ids,
        )
        trace_update = runtime_trace_state_update(
            state,
            calculation_operands=calculation_operands,
            calculation_plan=calculation_plan,
            calculation_result=calculation_result,
        )
        logger.info(
            "[semantic_program] execute status=%s outputs=%s missing=%s",
            execution.get("status"), len(output_rows), len(execution.get("missing_obligation_ids") or []),
        )
        return {
            **trace_update,
            "answer": answer,
            "compressed_answer": answer,
            "draft_points": [answer] if answer else [],
            "structured_result": structured_result,
            "subtask_results": output_rows,
            "subtask_loop_complete": True,
            "semantic_program_validation": dict(execution.get("validation") or {}),
            "missing_info": list(execution.get("missing_obligation_ids") or []),
            "evidence_items": evidence_items,
            "runtime_evidence": evidence_items,
            "selected_claim_ids": selected_candidate_ids,
            "kept_claim_ids": selected_candidate_ids,
            "dropped_claim_ids": [],
            "unsupported_sentences": [],
            "sentence_checks": [],
            "evidence_bullets": [
                f"- {item.get('source_anchor', '?')} {item.get('claim', '')} (direct)"
                for item in evidence_items
            ],
            "evidence_status": "sufficient" if execution.get("status") == "ok" else "sparse",
            "tasks": list(result_update.get("tasks") or []),
            "artifacts": list(result_update.get("artifacts") or []),
        }

    def _format_citations(self, state: FinancialAgentState) -> Dict[str, Any]:
        seen: set[Any] = set()
        citations: List[str] = []
        selected_ids = {
            str(value).strip()
            for value in (state.get("selected_claim_ids") or [])
            if str(value).strip()
        }
        for evidence in list(state.get("evidence_items") or []):
            if not isinstance(evidence, dict):
                continue
            evidence_id = str(evidence.get("evidence_id") or "").strip()
            if selected_ids and evidence_id not in selected_ids:
                continue
            anchor = _normalise_spaces(str(evidence.get("source_anchor") or ""))
            metadata = dict(evidence.get("metadata") or {})
            metadata_anchor = self._build_source_anchor(metadata) if metadata else ""
            if metadata_anchor and (not anchor or len(metadata_anchor) > len(anchor)):
                anchor = metadata_anchor
            if anchor and anchor not in seen:
                seen.add(anchor)
                citations.append(anchor)
        for doc, score in state.get("retrieved_docs", []):
            metadata = dict(getattr(doc, "metadata", {}) or {})
            key = (
                metadata.get("company"), metadata.get("year"),
                metadata.get("section_path"), metadata.get("chunk_uid"),
            )
            if key in seen:
                continue
            seen.add(key)
            citations.append(
                f"[{metadata.get('company', '?')}] {metadata.get('year', '?')}년 "
                f"{metadata.get('report_type', '?')} / "
                f"{metadata.get('section_path', metadata.get('section', '?'))} / "
                f"{metadata.get('block_type', '?')} (score: {score:.3f})"
            )
        return {"citations": citations}
