"""
Schema models for DART disclosure analysis runtime artifacts and document objects.
"""

from .runtime_enums import (
    AggregationStage,
    ArtifactKind,
    TaskKind,
    TaskStatus,
    ValueRole,
)

__all__ = [
    "AggregationStage",
    "ArtifactKind",
    "ArtifactRecord",
    "CellRecord",
    "RowRecord",
    "TableObject",
    "TaskKind",
    "TaskRecord",
    "TaskStatus",
    "ValueRole",
    "ValueRecord",
]

_MODEL_EXPORTS = {
    "ArtifactRecord",
    "CellRecord",
    "RowRecord",
    "TableObject",
    "TaskRecord",
    "ValueRecord",
}


def __getattr__(name: str):
    if name not in _MODEL_EXPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    from . import dart_schema

    value = getattr(dart_schema, name)
    globals()[name] = value
    return value
