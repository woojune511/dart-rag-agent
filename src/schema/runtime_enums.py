"""Lightweight runtime schema enums.

Keep these enums separate from Pydantic model definitions so runtime helpers
that only need ledger kind/status constants do not import the full schema stack.
"""

from enum import Enum


class TaskStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIAL = "partial"
    SUPERSEDED = "superseded"


class TaskKind(str, Enum):
    CALCULATION = "calculation"
    RETRIEVAL = "retrieval"
    RECONCILIATION = "reconciliation"
    REFLECTION = "reflection"
    VERIFICATION = "verification"
    CRITIC = "critic"
    SYNTHESIS = "synthesis"


class ArtifactKind(str, Enum):
    SEMANTIC_PLAN = "semantic_plan"
    RETRIEVAL_BUNDLE = "retrieval_bundle"
    RECONCILIATION_RESULT = "reconciliation_result"
    OPERAND_SET = "operand_set"
    CALCULATION_PLAN = "calculation_plan"
    CALCULATION_RESULT = "calculation_result"
    REFLECTION_REPORT = "reflection_report"
    AGGREGATED_ANSWER = "aggregated_answer"
    CRITIC_REPORT = "critic_report"


class ValueRole(str, Enum):
    DETAIL = "detail"
    AGGREGATE = "aggregate"
    ADJUSTMENT = "adjustment"


class AggregationStage(str, Enum):
    NONE = "none"
    DIRECT = "direct"
    SUBTOTAL = "subtotal"
    FINAL = "final"
