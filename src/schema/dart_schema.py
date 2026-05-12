"""
Structured runtime and document schemas for the DART disclosure analysis agent.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class TaskStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIAL = "partial"


class TaskKind(str, Enum):
    CALCULATION = "calculation"
    RETRIEVAL = "retrieval"
    RECONCILIATION = "reconciliation"
    VERIFICATION = "verification"
    SYNTHESIS = "synthesis"


class ArtifactKind(str, Enum):
    SEMANTIC_PLAN = "semantic_plan"
    RETRIEVAL_BUNDLE = "retrieval_bundle"
    RECONCILIATION_RESULT = "reconciliation_result"
    OPERAND_SET = "operand_set"
    CALCULATION_PLAN = "calculation_plan"
    CALCULATION_RESULT = "calculation_result"
    AGGREGATED_ANSWER = "aggregated_answer"


class CellRecord(BaseModel):
    cell_id: str
    column_index: int
    column_headers: List[str] = Field(default_factory=list)
    value_text: str = ""
    unit_hint: str = ""
    normalized_value: Optional[float] = None
    normalized_unit: Literal["KRW", "PERCENT", "COUNT", "USD", "UNKNOWN"] = "UNKNOWN"


class RowRecord(BaseModel):
    row_id: str
    row_label: str
    row_headers: List[str] = Field(default_factory=list)
    cells: List[CellRecord] = Field(default_factory=list)


class TableObject(BaseModel):
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
    table_header_context: str = ""
    table_summary_text: str = ""


class TaskRecord(BaseModel):
    task_id: str
    kind: TaskKind
    label: str
    status: TaskStatus = TaskStatus.PENDING
    query: str = ""
    metric_family: str = ""
    constraints: Dict[str, Any] = Field(default_factory=dict)
    artifact_ids: List[str] = Field(default_factory=list)
    notes: List[str] = Field(default_factory=list)


class ArtifactRecord(BaseModel):
    artifact_id: str
    task_id: str
    kind: ArtifactKind
    status: str = "ok"
    summary: str = ""
    payload: Dict[str, Any] = Field(default_factory=dict)
    evidence_refs: List[str] = Field(default_factory=list)
