"""
Structured runtime and document schemas for the DART disclosure analysis agent.
"""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from src.schema.runtime_enums import AggregationStage, ArtifactKind, TaskKind, TaskStatus, ValueRole


class _DeferredBaseModel(BaseModel):
    model_config = ConfigDict(defer_build=True)


class CellRecord(_DeferredBaseModel):
    cell_id: str
    column_index: int
    column_headers: List[str] = Field(default_factory=list)
    value_text: str = ""
    unit_hint: str = ""
    normalized_value: Optional[float] = None
    normalized_unit: Literal["KRW", "PERCENT", "COUNT", "USD", "UNKNOWN"] = "UNKNOWN"


class RowRecord(_DeferredBaseModel):
    row_id: str
    row_label: str
    row_headers: List[str] = Field(default_factory=list)
    cells: List[CellRecord] = Field(default_factory=list)


class ValueRecord(_DeferredBaseModel):
    value_id: str
    row_index: int
    column_index: int
    semantic_label: str
    semantic_aliases: List[str] = Field(default_factory=list)
    label_source: Literal["row", "column", "composite", "unknown"] = "unknown"
    value_role: ValueRole = ValueRole.DETAIL
    aggregation_stage: AggregationStage = AggregationStage.NONE
    aggregate_label: str = ""
    aggregate_role: Literal["none", "direct_total", "subtotal", "final_total", "adjustment"] = "none"
    row_label: str = ""
    row_headers: List[str] = Field(default_factory=list)
    column_headers: List[str] = Field(default_factory=list)
    period_text: str = ""
    period_labels: List[str] = Field(default_factory=list)
    value_text: str = ""
    unit_hint: str = ""
    normalized_value: Optional[float] = None
    normalized_unit: Literal["KRW", "PERCENT", "COUNT", "USD", "UNKNOWN"] = "UNKNOWN"


class TableObject(_DeferredBaseModel):
    table_id: str
    source_section_path: str
    caption: str = ""
    statement_type: str = "unknown"
    consolidation_scope: str = "unknown"
    unit_hint: str = "unknown"
    period_labels: List[str] = Field(default_factory=list)
    period_focus: str = "unknown"
    row_count: int = 0
    column_count: int = 0
    has_spans: bool = False
    header_rows: List[List[str]] = Field(default_factory=list)
    row_labels: List[str] = Field(default_factory=list)
    rows: List[RowRecord] = Field(default_factory=list)
    values: List[ValueRecord] = Field(default_factory=list)
    table_header_context: str = ""
    table_summary_text: str = ""


class TaskRecord(_DeferredBaseModel):
    task_id: str
    kind: TaskKind
    label: str
    status: TaskStatus = TaskStatus.PENDING
    query: str = ""
    metric_family: str = ""
    constraints: Dict[str, Any] = Field(default_factory=dict)
    artifact_ids: List[str] = Field(default_factory=list)
    notes: List[str] = Field(default_factory=list)


class ArtifactRecord(_DeferredBaseModel):
    artifact_id: str
    task_id: str
    kind: ArtifactKind
    status: str = "ok"
    summary: str = ""
    payload: Dict[str, Any] = Field(default_factory=dict)
    evidence_refs: List[str] = Field(default_factory=list)
