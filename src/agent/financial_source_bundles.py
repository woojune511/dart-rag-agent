"""Deterministic source-local bundles for semantic compiler candidates."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Dict, Mapping, Sequence, Tuple


SOURCE_BUNDLE_SCHEMA_VERSION = "source_bundle_v1"

_STRUCTURED_CANDIDATE_KINDS = frozenset(
    {"structured_value", "structured_row", "table_row", "evidence_row"}
)


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )


def _fingerprint(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _span(value: Any) -> tuple[int, int] | None:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return None
    try:
        start, end = int(value[0]), int(value[1])
    except (IndexError, TypeError, ValueError):
        return None
    return (start, end) if 0 <= start < end else None


def _unique_surface_span(text: str, surfaces: Sequence[Any]) -> tuple[int, int] | None:
    for raw_surface in surfaces:
        surface = str(raw_surface or "")
        if not surface:
            continue
        start = text.find(surface)
        if start < 0 or text.find(surface, start + 1) >= 0:
            continue
        return start, start + len(surface)
    return None


def _candidate_value_span(candidate: Mapping[str, Any], text: str) -> tuple[int, int] | None:
    projected = _span(candidate.get("source_bundle_value_span"))
    if projected is not None and projected[1] <= len(text):
        return projected
    raw_value = str(candidate.get("raw_value") or "")
    raw_unit = str(candidate.get("raw_unit") or "")
    return _unique_surface_span(
        text,
        [
            f"{raw_value} {raw_unit}".strip(),
            f"{raw_value}{raw_unit}".strip(),
            raw_value,
        ],
    )


def _is_structured(candidate: Mapping[str, Any]) -> bool:
    return bool(candidate.get("physical_table_id") or candidate.get("table_source_id")) or str(
        candidate.get("candidate_kind") or ""
    ) in _STRUCTURED_CANDIDATE_KINDS


def _source_material(candidate: Mapping[str, Any]) -> Dict[str, Any]:
    structured = _is_structured(candidate)
    source_kind = "table_row" if structured else "prose_sentence"
    text = str(
        candidate.get("source_bundle_text")
        or candidate.get("source_text")
        or ""
    )
    context_span = _span(candidate.get("source_bundle_context_span"))
    physical_table_id = str(
        candidate.get("physical_table_id")
        or candidate.get("table_source_id")
        or ""
    )
    physical_row_id = str(
        candidate.get("physical_row_id")
        or candidate.get("source_row_id")
        or ""
    )
    return {
        "source_kind": source_kind,
        "source_anchor": str(candidate.get("source_anchor") or ""),
        "context_fingerprint": str(candidate.get("context_fingerprint") or ""),
        "physical_table_id": physical_table_id if structured else "",
        "physical_row_id": physical_row_id if structured else "",
        "source_candidate_id": (
            ""
            if structured
            else str(
                candidate.get("source_candidate_id")
                or candidate.get("evidence_id")
                or ""
            )
        ),
        "source_context_span": list(context_span) if context_span else [],
        "source_text": text,
    }


@dataclass(frozen=True, slots=True)
class SourceBundleV1:
    """One exact source window shared by one or more compiler candidates."""

    source_bundle_id: str
    source_kind: str
    source_anchor: str
    context_fingerprint: str
    physical_table_id: str
    physical_row_id: str
    source_text: str
    candidate_ids: Tuple[str, ...]
    candidate_value_spans: Tuple[Tuple[str, int, int], ...] = ()
    schema_version: str = SOURCE_BUNDLE_SCHEMA_VERSION

    def value_span_by_candidate_id(self) -> Dict[str, list[int]]:
        return {
            candidate_id: [start, end]
            for candidate_id, start, end in self.candidate_value_spans
        }

    def to_projection(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "source_bundle_id": self.source_bundle_id,
            "source_kind": self.source_kind,
            "source_anchor": self.source_anchor,
            "context_fingerprint": self.context_fingerprint,
            "physical_table_id": self.physical_table_id,
            "physical_row_id": self.physical_row_id,
            "source_text": self.source_text,
            "candidate_ids": list(self.candidate_ids),
            "value_spans_by_candidate_id": self.value_span_by_candidate_id(),
        }


def build_semantic_source_bundles(
    catalog: Sequence[Mapping[str, Any]],
    *,
    candidate_ids: Sequence[Any] = (),
) -> Tuple[SourceBundleV1, ...]:
    """Group catalog rows by deterministic physical/source-local identity."""

    requested_ids = {
        str(candidate_id)
        for candidate_id in candidate_ids
        if str(candidate_id or "")
    }
    grouped: Dict[str, Dict[str, Any]] = {}
    for raw_candidate in catalog:
        candidate = dict(raw_candidate or {})
        candidate_id = str(candidate.get("candidate_id") or "")
        if not candidate_id or (requested_ids and candidate_id not in requested_ids):
            continue
        material = _source_material(candidate)
        source_bundle_id = f"srcb_{_fingerprint(material)[:20]}"
        group = grouped.setdefault(
            source_bundle_id,
            {"material": material, "members": {}},
        )
        if group["material"] != material:
            raise ValueError(f"source bundle hash collision: {source_bundle_id}")
        text = str(material["source_text"])
        group["members"][candidate_id] = _candidate_value_span(candidate, text)

    bundles = []
    for source_bundle_id, group in grouped.items():
        material = dict(group["material"])
        members = dict(group["members"])
        ordered_members = sorted(
            members,
            key=lambda candidate_id: (
                members[candidate_id]
                if members[candidate_id] is not None
                else (10**9, 10**9),
                candidate_id,
            ),
        )
        spans = tuple(
            (candidate_id, members[candidate_id][0], members[candidate_id][1])
            for candidate_id in ordered_members
            if members[candidate_id] is not None
        )
        bundles.append(
            SourceBundleV1(
                source_bundle_id=source_bundle_id,
                source_kind=str(material["source_kind"]),
                source_anchor=str(material["source_anchor"]),
                context_fingerprint=str(material["context_fingerprint"]),
                physical_table_id=str(material["physical_table_id"]),
                physical_row_id=str(material["physical_row_id"]),
                source_text=str(material["source_text"]),
                candidate_ids=tuple(ordered_members),
                candidate_value_spans=spans,
            )
        )
    return tuple(sorted(bundles, key=lambda bundle: bundle.source_bundle_id))


def semantic_source_bundle_fingerprint(
    bundles: Sequence[SourceBundleV1 | Mapping[str, Any]],
) -> str:
    projections = [
        bundle.to_projection() if isinstance(bundle, SourceBundleV1) else dict(bundle)
        for bundle in bundles
    ]
    return _fingerprint(
        sorted(projections, key=lambda item: str(item.get("source_bundle_id") or ""))
    )


def source_bundle_id_by_candidate_id(
    bundles: Sequence[SourceBundleV1],
) -> Dict[str, str]:
    return {
        candidate_id: bundle.source_bundle_id
        for bundle in bundles
        for candidate_id in bundle.candidate_ids
    }


__all__ = [
    "SOURCE_BUNDLE_SCHEMA_VERSION",
    "SourceBundleV1",
    "build_semantic_source_bundles",
    "semantic_source_bundle_fingerprint",
    "source_bundle_id_by_candidate_id",
]
