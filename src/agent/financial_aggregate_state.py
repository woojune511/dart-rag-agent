"""Lightweight aggregate-subtask state carriers."""

from __future__ import annotations

from typing import Any, Dict, List, NamedTuple, Optional, Sequence

from src.agent.financial_runtime_normalization import _normalise_spaces


class _AggregateSynthesisState(NamedTuple):
    ordered_results: List[Dict[str, Any]]
    aggregate_projection: Dict[str, Any]
    final_answer: str
    selected_claim_ids: List[str]

    def with_updates(
        self,
        *,
        ordered_results: Optional[List[Dict[str, Any]]] = None,
        aggregate_projection: Optional[Dict[str, Any]] = None,
        final_answer: Optional[str] = None,
        selected_claim_ids: Optional[List[str]] = None,
    ) -> "_AggregateSynthesisState":
        return _AggregateSynthesisState(
            self.ordered_results if ordered_results is None else ordered_results,
            self.aggregate_projection if aggregate_projection is None else aggregate_projection,
            self.final_answer if final_answer is None else final_answer,
            self.selected_claim_ids if selected_claim_ids is None else selected_claim_ids,
        )


class _PreparedAggregateState(NamedTuple):
    ordered_results: List[Dict[str, Any]]
    fallback_answer: str
    supported_aggregate_answer: str
    complete_numeric_answer: str
    has_narrative_summary: bool
    has_growth_rate_result: bool
    numeric_answer_locked: bool


class _AggregateEvidenceState(NamedTuple):
    ordered_results: List[Dict[str, Any]]
    aggregate_evidence_items: List[Dict[str, Any]]
    fallback_answer: str
    final_answer: str
    complete_numeric_answer: str
    deterministic_feedback: str


class _AggregateFeedbackState(NamedTuple):
    final_answer: str
    planner_feedback: str
    deterministic_feedback: str
    ledger_artifacts: List[Dict[str, Any]]
    task_artifact_trace: Dict[str, Any]
    should_replan: bool
    replan_blocked_reason: str


class AggregateCompositionState(NamedTuple):
    final_answer: str
    selected_claim_ids: List[str]
    calculation_projection_override: Optional[Dict[str, Any]]
    narrative_answer_locked: bool
    planner_feedback: str
    deterministic_feedback: str


def apply_aggregate_composition_answer(
    composition_state: AggregateCompositionState,
    *,
    answer: str = "",
    selected_claim_ids: Optional[Sequence[Any]] = None,
    calculation_projection_override: Optional[Dict[str, Any]] = None,
    reset_projection_override: bool = False,
    narrative_answer_locked: Optional[bool] = None,
    clear_feedback: bool = True,
) -> AggregateCompositionState:
    final_answer = _normalise_spaces(answer) or composition_state.final_answer
    merged_claim_ids = list(
        dict.fromkeys(
            [
                *[
                    str(claim_id).strip()
                    for claim_id in (composition_state.selected_claim_ids or [])
                    if str(claim_id).strip()
                ],
                *[
                    str(claim_id).strip()
                    for claim_id in (selected_claim_ids or [])
                    if str(claim_id).strip()
                ],
            ]
        )
    )
    projection_override = composition_state.calculation_projection_override
    if reset_projection_override:
        projection_override = None
    elif isinstance(calculation_projection_override, dict):
        projection_override = calculation_projection_override
    locked = (
        composition_state.narrative_answer_locked
        if narrative_answer_locked is None
        else bool(narrative_answer_locked)
    )
    return AggregateCompositionState(
        final_answer=final_answer,
        selected_claim_ids=merged_claim_ids,
        calculation_projection_override=projection_override,
        narrative_answer_locked=locked,
        planner_feedback="" if clear_feedback else composition_state.planner_feedback,
        deterministic_feedback="" if clear_feedback else composition_state.deterministic_feedback,
    )


class _AggregateMutableState(NamedTuple):
    synthesis_state: _AggregateSynthesisState
    evidence_items: List[Dict[str, Any]]

    @property
    def ordered_results(self) -> List[Dict[str, Any]]:
        return self.synthesis_state.ordered_results

    @property
    def aggregate_projection(self) -> Dict[str, Any]:
        return self.synthesis_state.aggregate_projection

    @property
    def final_answer(self) -> str:
        return self.synthesis_state.final_answer

    @property
    def selected_claim_ids(self) -> List[str]:
        return self.synthesis_state.selected_claim_ids

    def with_updates(
        self,
        *,
        ordered_results: Optional[List[Dict[str, Any]]] = None,
        aggregate_projection: Optional[Dict[str, Any]] = None,
        final_answer: Optional[str] = None,
        selected_claim_ids: Optional[List[str]] = None,
        evidence_items: Optional[List[Dict[str, Any]]] = None,
    ) -> "_AggregateMutableState":
        synthesis_state = self.synthesis_state.with_updates(
            ordered_results=ordered_results,
            aggregate_projection=aggregate_projection,
            final_answer=final_answer,
            selected_claim_ids=selected_claim_ids,
        )
        return _AggregateMutableState(
            synthesis_state,
            self.evidence_items if evidence_items is None else evidence_items,
        )

    def with_synthesis_state(
        self,
        synthesis_state: _AggregateSynthesisState,
    ) -> "_AggregateMutableState":
        return _AggregateMutableState(synthesis_state, self.evidence_items)
