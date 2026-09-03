"""Grounded candidate catalogs for semantic calculation programs."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Dict, List, Mapping, Optional, Sequence

from src.agent.financial_numeric_surface import extract_numeric_surface_candidates
from src.agent.financial_row_surfaces import parse_unstructured_table_row_cells
from src.agent.financial_runtime_normalization import (
    _normalise_operand_value,
    _normalise_spaces,
    resolve_source_numeric_unit,
)
from src.config.retrieval_policy import (
    CONSOLIDATION_SCOPE_POLICY,
    FINANCIAL_DOCUMENT_STATEMENT_HINT_POLICIES,
    SEMANTIC_CANDIDATE_POLICY,
    STRUCTURED_CELL_AFFINITY_POLICY,
)


def _semantic_candidate_id(payload: Mapping[str, Any]) -> str:
    serialized = json.dumps(dict(payload), ensure_ascii=False, sort_keys=True, default=str)
    return f"cand_{hashlib.sha256(serialized.encode('utf-8')).hexdigest()[:20]}"


def semantic_candidate_catalog_fingerprint(catalog: Sequence[Mapping[str, Any]]) -> str:
    """Return a stable digest for a catalog without exposing it as an authority."""

    payload = sorted(
        [
            {
                "candidate_id": str(item.get("candidate_id") or ""),
                "source_candidate_id": str(item.get("source_candidate_id") or ""),
                "raw_value": str(item.get("raw_value") or ""),
                "raw_unit": str(item.get("raw_unit") or ""),
                "source_row_id": str(item.get("source_row_id") or ""),
            }
            for item in catalog
        ],
        key=lambda item: (
            item["candidate_id"],
            item["source_candidate_id"],
            item["source_row_id"],
        ),
    )
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def semantic_candidate_id_fingerprint(candidate_ids: Sequence[Any]) -> str:
    """Return a stable digest for a set of candidate IDs only."""

    normalized = sorted(
        {
            str(candidate_id).strip()
            for candidate_id in candidate_ids
            if str(candidate_id or "").strip()
        }
    )
    serialized = json.dumps(
        normalized,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _stable_document_source_ids(entries: Sequence[Any]) -> tuple[List[str], int]:
    source_ids: List[str] = []
    seen: set[str] = set()
    unidentified_count = 0
    for entry in entries:
        doc = entry[0] if isinstance(entry, (tuple, list)) and entry else entry
        metadata = dict(getattr(doc, "metadata", {}) or {})
        source_id = str(
            metadata.get("chunk_uid")
            or metadata.get("chunk_id")
            or metadata.get("id")
            or ""
        ).strip()
        if not source_id:
            unidentified_count += 1
            continue
        if source_id in seen:
            continue
        seen.add(source_id)
        source_ids.append(source_id)
    return source_ids, unidentified_count


def _normalized_source_id_list(values: Any) -> List[str]:
    source_ids: List[str] = []
    seen: set[str] = set()
    for value in values if isinstance(values, (tuple, list)) else []:
        source_id = str(value or "").strip()
        if not source_id or source_id in seen:
            continue
        seen.add(source_id)
        source_ids.append(source_id)
    return source_ids


def _source_window_for_stage_diagnostics(
    state: Mapping[str, Any],
) -> tuple[Dict[str, Any], str]:
    retrieval_trace = dict(state.get("retrieval_debug_trace") or {})
    traced_window = retrieval_trace.get("source_window")
    if isinstance(traced_window, Mapping):
        try:
            retrieved_unidentified_count = max(
                0,
                int(traced_window.get("retrieved_unidentified_count") or 0),
            )
        except (TypeError, ValueError):
            retrieved_unidentified_count = 0
        try:
            seed_unidentified_count = max(
                0,
                int(traced_window.get("seed_unidentified_count") or 0),
            )
        except (TypeError, ValueError):
            seed_unidentified_count = 0
        return (
            {
                "retrieved_source_ids": _normalized_source_id_list(
                    traced_window.get("retrieved_source_ids")
                ),
                "retrieved_unidentified_count": retrieved_unidentified_count,
                "seed_source_ids": _normalized_source_id_list(
                    traced_window.get("seed_source_ids")
                ),
                "seed_unidentified_count": seed_unidentified_count,
            },
            "retrieval_debug_trace",
        )

    retrieved_source_ids, retrieved_unidentified_count = _stable_document_source_ids(
        list(state.get("retrieved_docs") or [])
    )
    seed_source_ids, seed_unidentified_count = _stable_document_source_ids(
        list(state.get("seed_retrieved_docs") or [])
    )
    return (
        {
            "retrieved_source_ids": retrieved_source_ids,
            "retrieved_unidentified_count": retrieved_unidentified_count,
            "seed_source_ids": seed_source_ids,
            "seed_unidentified_count": seed_unidentified_count,
        },
        "state_documents_fallback",
    )


def _root_source_id(candidate: Mapping[str, Any], *, catalog_row: bool) -> str:
    if catalog_row:
        source_id = str(candidate.get("evidence_id") or "").strip()
        if source_id:
            return source_id
    source_candidate_id = str(candidate.get("source_candidate_id") or "").strip()
    if not source_candidate_id:
        source_candidate_id = str(candidate.get("candidate_id") or "").strip()
    return source_candidate_id.split("::", 1)[0].strip()


def _candidate_ids_by_source(
    rows: Sequence[Mapping[str, Any]],
    *,
    catalog_rows: bool,
) -> tuple[Dict[str, List[str]], int]:
    grouped: Dict[str, List[str]] = {}
    unresolved_count = 0
    for row in rows:
        source_id = _root_source_id(row, catalog_row=catalog_rows)
        candidate_id = str(row.get("candidate_id") or "").strip()
        if not source_id or not candidate_id:
            unresolved_count += 1
            continue
        source_candidate_ids = grouped.setdefault(source_id, [])
        if candidate_id not in source_candidate_ids:
            source_candidate_ids.append(candidate_id)
    return grouped, unresolved_count


def _candidate_kind_counts(rows: Sequence[Mapping[str, Any]]) -> Dict[str, int]:
    counts = {"numeric": 0, "narrative": 0, "other": 0}
    for row in rows:
        kind = str(row.get("kind") or "").strip()
        counts[kind if kind in {"numeric", "narrative"} else "other"] += 1
    return counts


def semantic_candidate_stage_diagnostics(
    *,
    state: Mapping[str, Any],
    source_candidates: Sequence[Mapping[str, Any]],
    catalog: Sequence[Mapping[str, Any]],
    prompt_catalog: Sequence[Mapping[str, Any]],
    cohorts: Sequence[Mapping[str, Any]] = (),
    attempts: Sequence[Mapping[str, Any]] = (),
) -> Dict[str, Any]:
    """Summarize source-to-prompt projection without copying candidate values.

    Stable source IDs and sorted candidate-ID fingerprints let an offline probe
    distinguish a missing source window, an incomplete local projection, and a
    prompt-admission drop. Raw values, labels, and full catalog rows stay out of
    the runtime trace.
    """

    source_window, source_window_origin = _source_window_for_stage_diagnostics(state)
    retrieved_source_ids = list(source_window["retrieved_source_ids"])
    seed_source_ids = list(source_window["seed_source_ids"])
    source_by_id, unresolved_source_candidate_count = _candidate_ids_by_source(
        source_candidates,
        catalog_rows=False,
    )
    catalog_by_id, unresolved_catalog_candidate_count = _candidate_ids_by_source(
        catalog,
        catalog_rows=True,
    )
    prompt_by_id, unresolved_prompt_candidate_count = _candidate_ids_by_source(
        prompt_catalog,
        catalog_rows=True,
    )
    catalog_rows_by_source: Dict[str, List[Mapping[str, Any]]] = {}
    for row in catalog:
        source_id = _root_source_id(row, catalog_row=True)
        if source_id:
            catalog_rows_by_source.setdefault(source_id, []).append(row)
    prompt_rows_by_source: Dict[str, List[Mapping[str, Any]]] = {}
    for row in prompt_catalog:
        source_id = _root_source_id(row, catalog_row=True)
        if source_id:
            prompt_rows_by_source.setdefault(source_id, []).append(row)

    retrieved_set = set(retrieved_source_ids)
    seed_set = set(seed_source_ids)
    all_source_ids = sorted(
        {
            *retrieved_set,
            *seed_set,
            *source_by_id,
            *catalog_by_id,
            *prompt_by_id,
        }
    )
    by_source: List[Dict[str, Any]] = []
    for source_id in all_source_ids:
        source_candidate_ids = source_by_id.get(source_id, [])
        catalog_candidate_ids = catalog_by_id.get(source_id, [])
        prompt_candidate_ids = prompt_by_id.get(source_id, [])
        catalog_kind_counts = _candidate_kind_counts(
            catalog_rows_by_source.get(source_id, [])
        )
        prompt_kind_counts = _candidate_kind_counts(
            prompt_rows_by_source.get(source_id, [])
        )
        by_source.append(
            {
                "source_id": source_id,
                "in_retrieved_window": source_id in retrieved_set,
                "in_seed_window": source_id in seed_set,
                "source_candidate_count": len(source_candidate_ids),
                "source_candidate_id_fingerprint": semantic_candidate_id_fingerprint(
                    source_candidate_ids
                ),
                "catalog_candidate_count": len(catalog_candidate_ids),
                "catalog_candidate_id_fingerprint": semantic_candidate_id_fingerprint(
                    catalog_candidate_ids
                ),
                "catalog_kind_counts": catalog_kind_counts,
                "prompt_candidate_count": len(prompt_candidate_ids),
                "prompt_candidate_id_fingerprint": semantic_candidate_id_fingerprint(
                    prompt_candidate_ids
                ),
                "prompt_kind_counts": prompt_kind_counts,
                "prompt_drop_count": len(
                    set(catalog_candidate_ids) - set(prompt_candidate_ids)
                ),
            }
        )

    source_candidate_ids = [
        str(item.get("candidate_id") or "").strip()
        for item in source_candidates
        if str(item.get("candidate_id") or "").strip()
    ]
    catalog_candidate_ids = [
        str(item.get("candidate_id") or "").strip()
        for item in catalog
        if str(item.get("candidate_id") or "").strip()
    ]
    prompt_candidate_ids = [
        str(item.get("candidate_id") or "").strip()
        for item in prompt_catalog
        if str(item.get("candidate_id") or "").strip()
    ]
    def numeric_projection_count(
        cells: Sequence[Mapping[str, Any]],
        metadata: Mapping[str, Any],
    ) -> int:
        count = 0
        for cell in cells:
            raw_value = _normalise_spaces(str(cell.get("value_text") or ""))
            if not raw_value or not re.search(r"\d", raw_value):
                continue
            source_unit_hint = _normalise_spaces(
                str(cell.get("unit_hint") or metadata.get("unit_hint") or "")
            )
            raw_unit, _raw_unit_source = resolve_source_numeric_unit(
                raw_value,
                source_unit_hint,
            )
            normalized_value, _normalized_unit = _normalise_operand_value(
                raw_value,
                raw_unit,
            )
            if normalized_value is not None:
                count += 1
        return count

    attached_physical_cell_count = 0
    structured_table_attachment_count = 0
    for entry in [
        *list(state.get("retrieved_docs") or []),
        *list(state.get("seed_retrieved_docs") or []),
    ]:
        doc = entry[0] if isinstance(entry, (tuple, list)) and entry else entry
        metadata = dict(getattr(doc, "metadata", {}) or {})
        _table_object, row_records, value_records = _table_record_bundle(metadata)
        if row_records:
            structured_table_attachment_count += 1
            attached_physical_cell_count += sum(
                numeric_projection_count(
                    [
                        cell
                        for cell in (row.get("cells") or [])
                        if isinstance(cell, Mapping)
                    ],
                    metadata,
                )
                for row in row_records
            )
        elif value_records:
            structured_table_attachment_count += 1
            attached_physical_cell_count += numeric_projection_count(
                value_records,
                metadata,
            )
    physical_cell_keys = {
        str(item.get("physical_cell_key") or "").strip()
        for item in catalog
        if str(item.get("kind") or "") == "numeric"
        and str(item.get("physical_cell_key") or "").strip()
    }
    return {
        "schema": "semantic_candidate_stage_diagnostics_v4",
        "source_window_origin": source_window_origin,
        "source_window": source_window,
        "source_candidate_count": len(source_candidate_ids),
        "source_candidate_id_fingerprint": semantic_candidate_id_fingerprint(
            source_candidate_ids
        ),
        "unresolved_source_candidate_count": unresolved_source_candidate_count,
        "catalog_candidate_count": len(catalog_candidate_ids),
        "catalog_candidate_id_fingerprint": semantic_candidate_id_fingerprint(
            catalog_candidate_ids
        ),
        "unresolved_catalog_candidate_count": unresolved_catalog_candidate_count,
        "prompt_candidate_count": len(prompt_candidate_ids),
        "prompt_candidate_id_fingerprint": semantic_candidate_id_fingerprint(
            prompt_candidate_ids
        ),
        "unresolved_prompt_candidate_count": unresolved_prompt_candidate_count,
        "physical_deduplication": {
            "structured_table_attachment_count": (
                structured_table_attachment_count
            ),
            "attached_physical_cell_projection_count": (
                attached_physical_cell_count
            ),
            "unique_physical_cell_candidate_count": len(physical_cell_keys),
            "duplicate_physical_cell_projection_count": max(
                0,
                attached_physical_cell_count - len(physical_cell_keys),
            ),
        },
        "cohorts": [
            {
                "cohort_id": str(item.get("cohort_id") or ""),
                "owner_id": str(item.get("owner_id") or ""),
                "parent_obligation_id": str(
                    item.get("parent_obligation_id") or ""
                ),
                "owner_type": str(item.get("owner_type") or ""),
                "candidate_kind": str(item.get("candidate_kind") or ""),
                "candidate_count": len(item.get("candidate_ids") or []),
                "candidate_id_fingerprint": str(
                    item.get("candidate_id_fingerprint") or ""
                ),
                "match_counts": dict(
                    item.get("match_counts") or {}
                ),
                "ranking_diagnostics": dict(
                    item.get("ranking_diagnostics") or {}
                ),
                "source_defined_group_selection": dict(
                    item.get("source_defined_group_selection") or {}
                ),
            }
            for item in cohorts
        ],
        "attempts": [dict(item) for item in attempts],
        "by_source": by_source,
    }


def _candidate_period_surface(cell: Mapping[str, Any], metadata: Mapping[str, Any]) -> str:
    explicit = _normalise_spaces(
        str(cell.get("period_text") or cell.get("period") or metadata.get("period_text") or "")
    )
    if explicit:
        return explicit
    headers = [
        _normalise_spaces(str(item))
        for item in (cell.get("column_headers") or [])
        if _normalise_spaces(str(item))
    ]
    return " / ".join(headers)


def _canonical_consolidation_scope(value: Any) -> str:
    cleaned = _normalise_spaces(str(value or "")).lower()
    if not cleaned or cleaned == "unknown":
        return "unknown"
    for scope, values in dict(
        CONSOLIDATION_SCOPE_POLICY.get("metadata_values") or {}
    ).items():
        normalized = {
            _normalise_spaces(str(item or "")).lower() for item in (values or ())
        }
        if cleaned == str(scope).lower() or cleaned in normalized:
            return str(scope)
    return "unknown"


def _candidate_consolidation_scope(
    candidate: Mapping[str, Any],
    metadata: Mapping[str, Any],
    source_text: str,
) -> tuple[str, str]:
    explicit = _canonical_consolidation_scope(metadata.get("consolidation_scope"))
    if explicit != "unknown":
        return explicit, "metadata"

    if str(candidate.get("candidate_kind") or "") not in {
        "structured_row",
        "structured_value",
        "table_row",
        "evidence_row",
    }:
        return "unknown", "unknown"

    surface = _normalise_spaces(
        " ".join(
            str(value or "")
            for value in (
                metadata.get("section_path"),
                metadata.get("section_title"),
                metadata.get("local_heading"),
                metadata.get("table_context"),
                metadata.get("row_text"),
                candidate.get("source_anchor"),
                source_text,
            )
            if str(value or "").strip()
        )
    ).lower()
    matched = {
        str(scope)
        for scope, markers in dict(
            CONSOLIDATION_SCOPE_POLICY.get("context_markers") or {}
        ).items()
        if any(
            _normalise_spaces(str(marker or "")).lower() in surface
            for marker in (markers or ())
            if _normalise_spaces(str(marker or ""))
        )
    }
    if len(matched) == 1:
        return next(iter(matched)), "source_context"
    return "unknown", "unknown"


def _cell_explicit_year(cell: Mapping[str, Any], metadata: Mapping[str, Any]) -> Optional[int]:
    surface = _candidate_period_surface(cell, metadata)
    years = list(dict.fromkeys(re.findall(r"(?<!\d)((?:19|20)\d{2})(?!\d)", surface)))
    return int(years[0]) if len(years) == 1 else None


def _fiscal_ordinal(cell: Mapping[str, Any], metadata: Mapping[str, Any]) -> Optional[int]:
    surface = _candidate_period_surface(cell, metadata)
    match = re.search(
        str(SEMANTIC_CANDIDATE_POLICY.get("fiscal_period_ordinal_pattern") or r"$^"),
        surface,
    )
    return int(match.group(1)) if match else None


def _candidate_period_role(
    cell: Mapping[str, Any], metadata: Mapping[str, Any]
) -> str:
    explicit_role = _normalise_spaces(
        str(cell.get("value_role") or metadata.get("value_role") or "")
    ).lower()
    if explicit_role:
        return explicit_role
    return _normalise_spaces(
        " ".join(str(item or "") for item in (cell.get("column_headers") or []))
    ).lower()


def _candidate_period_role_kind(role: str) -> str:
    if any(marker in role for marker in ("current", "closing", "ending")):
        return "current"
    if any(
        marker in role
        for marker in ("prior", "previous", "opening", "begin")
    ):
        return "prior"
    return ""


def _candidate_has_competing_periods(
    cells: Sequence[Mapping[str, Any]], metadata: Mapping[str, Any]
) -> bool:
    temporal_keys: set[str] = set()
    period_surfaces = [
        _candidate_period_surface(cell, metadata) for cell in cells
    ]
    period_surfaces.extend(
        _normalise_spaces(str(item or ""))
        for item in (metadata.get("period_labels") or [])
    )
    for surface in period_surfaces:
        temporal_keys.update(
            f"year:{year}"
            for year in re.findall(r"(?<!\d)((?:19|20)\d{2})(?!\d)", surface)
        )
        ordinal_match = re.search(
            str(
                SEMANTIC_CANDIDATE_POLICY.get("fiscal_period_ordinal_pattern")
                or r"$^"
            ),
            surface,
        )
        if ordinal_match:
            temporal_keys.add(f"ordinal:{ordinal_match.group(1)}")
    for cell in cells:
        role_kind = _candidate_period_role_kind(
            _candidate_period_role(cell, metadata)
        )
        if role_kind:
            temporal_keys.add(f"role:{role_kind}")
    return len(temporal_keys) > 1


def _candidate_value_year(
    cells: Sequence[Mapping[str, Any]],
    cell_index: int,
    metadata: Mapping[str, Any],
) -> Optional[int]:
    cell = cells[cell_index]
    explicit_year = _cell_explicit_year(cell, metadata)
    if explicit_year is not None:
        return explicit_year

    try:
        report_year = int(metadata.get("year"))
    except (TypeError, ValueError):
        return None

    explicit_role = _candidate_period_role(cell, metadata)
    role_kind = _candidate_period_role_kind(explicit_role)
    if role_kind == "current":
        return report_year
    if role_kind == "prior":
        return report_year - 1

    ordinals = [
        ordinal
        for ordinal in (_fiscal_ordinal(item, metadata) for item in cells)
        if ordinal is not None
    ]
    value_ordinal = _fiscal_ordinal(cell, metadata)
    if ordinals and value_ordinal is not None:
        current_ordinal = max(ordinals)
        offset = current_ordinal - value_ordinal
        if 0 <= offset <= 20:
            return report_year - offset
    if _normalise_spaces(str(metadata.get("period_focus") or "")).lower() != "current":
        return None
    if _candidate_has_competing_periods(cells, metadata):
        return None
    return report_year


def _candidate_period_projection(
    cell: Mapping[str, Any],
    metadata: Mapping[str, Any],
    *,
    value_year: Optional[int],
) -> tuple[str, str, str]:
    source_surface = _candidate_period_surface(cell, metadata)
    if _cell_explicit_year(cell, metadata) is not None:
        return source_surface, source_surface, "explicit_period"
    if _fiscal_ordinal(cell, metadata) is not None:
        return source_surface, source_surface, "fiscal_period"
    role_kind = _candidate_period_role_kind(_candidate_period_role(cell, metadata))
    if value_year is not None:
        period_source = "value_role" if role_kind else "report_current"
        return str(value_year), source_surface, period_source
    return source_surface, source_surface, (
        "source_surface_unresolved" if source_surface else "unknown"
    )


def _candidate_value_role(
    cell: Mapping[str, Any],
    *,
    value_year: Optional[int],
    metadata: Mapping[str, Any],
) -> str:
    explicit = _normalise_spaces(
        str(cell.get("value_role") or metadata.get("value_role") or "")
    )
    if explicit:
        return explicit
    try:
        report_year = int(metadata.get("year"))
    except (TypeError, ValueError):
        return ""
    if value_year == report_year:
        return "current"
    if value_year is not None and value_year < report_year:
        return "prior"
    return ""


def _candidate_aggregate_metadata(
    cell: Mapping[str, Any],
    metadata: Mapping[str, Any],
    row_label: str,
) -> tuple[str, str]:
    explicit_stage = _normalise_spaces(
        str(cell.get("aggregation_stage") or metadata.get("aggregation_stage") or "")
    )
    explicit_label = _normalise_spaces(
        str(cell.get("aggregate_label") or metadata.get("aggregate_label") or "")
    )
    if explicit_stage and explicit_label:
        return explicit_stage, explicit_label

    surface = _normalise_spaces(str(row_label or ""))
    aggregate_tokens = sorted(
        (
            _normalise_spaces(str(item or ""))
            for item in (STRUCTURED_CELL_AFFINITY_POLICY.get("aggregate_tokens") or ())
            if _normalise_spaces(str(item or ""))
        ),
        key=len,
        reverse=True,
    )
    inferred_label = next(
        (
            token
            for token in aggregate_tokens
            if (
                token in surface
                if len(token) > 1
                else bool(
                    re.search(
                        rf"(?<![^\W_]){re.escape(token)}(?![^\W_])",
                        surface,
                        flags=re.UNICODE,
                    )
                )
            )
        ),
        "",
    )
    inferred_stage = ""
    if inferred_label:
        inferred_stage = next(
            (
                str(stage)
                for stage, tokens in dict(
                    STRUCTURED_CELL_AFFINITY_POLICY.get("aggregate_stage_tokens") or {}
                ).items()
                if inferred_label
                in {
                    _normalise_spaces(str(token or ""))
                    for token in (tokens or ())
                    if _normalise_spaces(str(token or ""))
                }
            ),
            "",
        )
    return explicit_stage or inferred_stage, explicit_label or inferred_label


def _semantic_catalog_context_fingerprint(
    candidate: Mapping[str, Any],
    metadata: Mapping[str, Any],
) -> str:
    source_candidate_id = str(candidate.get("candidate_id") or "")
    source_root = re.split(
        r"::(?:value|rowrec|colrec|row)(?::|$)|::raw_row$",
        source_candidate_id,
        maxsplit=1,
    )[0]
    parts = [
        str(
            metadata.get("table_source_id")
            or metadata.get("source_table_id")
            or metadata.get("table_id")
            or source_root
            or candidate.get("source_anchor")
            or ""
        ),
        str(metadata.get("consolidation_scope") or ""),
        str(metadata.get("basis") or metadata.get("accounting_basis") or ""),
        str(metadata.get("segment_label") or ""),
    ]
    return "|".join(_normalise_spaces(part) for part in parts)


def _semantic_source_candidate(
    *,
    candidate_id: str,
    source_anchor: str,
    text: str,
    metadata: Mapping[str, Any],
    candidate_kind: str,
    evidence_id: str = "",
    origin_source_id: str = "",
) -> Dict[str, Any]:
    """Build the generic source envelope consumed by the candidate catalog."""

    envelope = {
        "candidate_id": str(candidate_id or "").strip(),
        "source_anchor": _normalise_spaces(source_anchor),
        "text": _normalise_spaces(text),
        "metadata": dict(metadata or {}),
        "candidate_kind": str(candidate_kind or "chunk"),
    }
    if str(evidence_id or "").strip():
        envelope["evidence_id"] = str(evidence_id).strip()
    if str(origin_source_id or "").strip():
        envelope["origin_source_id"] = str(origin_source_id).strip()
    return envelope


def _json_list(raw_value: Any) -> List[Dict[str, Any]]:
    if isinstance(raw_value, list):
        return [dict(item) for item in raw_value if isinstance(item, Mapping)]
    raw_text = str(raw_value or "").strip()
    if not raw_text:
        return []
    try:
        value = json.loads(raw_text)
    except (TypeError, json.JSONDecodeError):
        return []
    return [dict(item) for item in value if isinstance(item, Mapping)] if isinstance(value, list) else []


def _json_mapping(raw_value: Any) -> Dict[str, Any]:
    if isinstance(raw_value, Mapping):
        return dict(raw_value)
    raw_text = str(raw_value or "").strip()
    if not raw_text:
        return {}
    try:
        value = json.loads(raw_text)
    except (TypeError, json.JSONDecodeError):
        return {}
    return dict(value) if isinstance(value, Mapping) else {}


def _normalized_string_list(raw_values: Any) -> List[str]:
    if isinstance(raw_values, (str, bytes)):
        raw_values = [raw_values]
    elif not isinstance(raw_values, Sequence):
        raw_values = []
    values: List[str] = []
    for raw_value in raw_values:
        value = _normalise_spaces(str(raw_value or ""))
        if value and value not in values:
            values.append(value)
    return values


def _stable_material_digest(payload: Any, *, length: int = 20) -> str:
    serialized = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()[:length]


def _table_record_bundle(
    metadata: Mapping[str, Any],
) -> tuple[Dict[str, Any], List[Dict[str, Any]], List[Dict[str, Any]]]:
    table_object = _json_mapping(metadata.get("table_object_json"))
    rows = _json_list(metadata.get("table_row_records_json"))
    values = _json_list(metadata.get("table_value_records_json"))
    if not rows:
        rows = [
            dict(item)
            for item in (table_object.get("rows") or [])
            if isinstance(item, Mapping)
        ]
    if not values:
        values = [
            dict(item)
            for item in (table_object.get("values") or [])
            if isinstance(item, Mapping)
        ]
    return table_object, rows, values


def _legacy_table_material(
    rows: Sequence[Mapping[str, Any]],
    values: Sequence[Mapping[str, Any]],
) -> List[Dict[str, Any]]:
    material: List[Dict[str, Any]] = []
    if rows:
        for row in rows:
            cells = [
                {
                    "column_index": cell.get("column_index"),
                    "column_headers": _normalized_string_list(
                        cell.get("column_headers")
                    ),
                    "value_text": _normalise_spaces(
                        str(cell.get("value_text") or "")
                    ),
                    "unit_hint": _normalise_spaces(
                        str(cell.get("unit_hint") or "")
                    ),
                }
                for cell in (row.get("cells") or [])
                if isinstance(cell, Mapping)
            ]
            material.append(
                {
                    "row_label": _normalise_spaces(str(row.get("row_label") or "")),
                    "row_headers": _normalized_string_list(row.get("row_headers")),
                    "cells": cells,
                }
            )
        return material
    for record in values:
        material.append(
            {
                "row_index": record.get("row_index"),
                "row_label": _normalise_spaces(str(record.get("row_label") or "")),
                "row_headers": _normalized_string_list(record.get("row_headers")),
                "column_index": record.get("column_index"),
                "column_headers": _normalized_string_list(
                    record.get("column_headers") or record.get("period_labels")
                ),
                "value_text": _normalise_spaces(str(record.get("value_text") or "")),
                "unit_hint": _normalise_spaces(str(record.get("unit_hint") or "")),
            }
        )
    return material


def _physical_table_id(
    metadata: Mapping[str, Any],
    table_object: Mapping[str, Any],
    rows: Sequence[Mapping[str, Any]],
    values: Sequence[Mapping[str, Any]],
) -> str:
    explicit = _normalise_spaces(
        str(
            metadata.get("table_source_id")
            or metadata.get("source_table_id")
            or metadata.get("table_id")
            or table_object.get("table_id")
            or ""
        )
    )
    if explicit:
        return explicit
    return f"legacy_table_{_stable_material_digest(_legacy_table_material(rows, values))}"


def _physical_row_identity(
    *,
    table_id: str,
    row: Mapping[str, Any],
    row_index: Any,
    row_label: str,
    row_headers: Sequence[str],
    cells: Sequence[Mapping[str, Any]],
) -> tuple[str, str]:
    row_id = _normalise_spaces(str(row.get("row_id") or ""))
    if row_id:
        return row_id, f"{table_id}::row:{row_id}"
    fallback = {
        "row_index": row_index,
        "row_label": row_label,
        "row_headers": list(row_headers),
        "cells": [
            {
                "column_index": cell.get("column_index"),
                "column_headers": _normalized_string_list(
                    cell.get("column_headers")
                ),
                "value_text": _normalise_spaces(
                    str(cell.get("value_text") or "")
                ),
                "unit_hint": _normalise_spaces(
                    str(cell.get("unit_hint") or "")
                ),
            }
            for cell in cells
        ],
    }
    row_id = f"legacy_row_{_stable_material_digest(fallback)}"
    return row_id, f"{table_id}::row:{row_id}"


def _physical_cell_identity(
    *,
    table_id: str,
    row_key: str,
    cell: Mapping[str, Any],
) -> tuple[str, str]:
    cell_id = _normalise_spaces(str(cell.get("cell_id") or ""))
    value_id = _normalise_spaces(str(cell.get("value_id") or ""))
    explicit_id = value_id or cell_id
    if explicit_id:
        return cell_id or value_id, f"{table_id}::{row_key}::cell:{explicit_id}"
    fallback = {
        "row_key": row_key,
        "column_index": cell.get("column_index"),
        "column_headers": _normalized_string_list(cell.get("column_headers")),
        "value_text": _normalise_spaces(str(cell.get("value_text") or "")),
        "unit_hint": _normalise_spaces(str(cell.get("unit_hint") or "")),
    }
    fallback_id = f"legacy_cell_{_stable_material_digest(fallback)}"
    return fallback_id, f"{table_id}::{row_key}::cell:{fallback_id}"


def _table_context_text(
    metadata: Mapping[str, Any], table_object: Mapping[str, Any]
) -> str:
    parts: List[str] = []
    for raw_value in (
        table_object.get("caption"),
        metadata.get("caption"),
        metadata.get("table_caption"),
        metadata.get("local_heading"),
    ):
        value = _normalise_spaces(str(raw_value or ""))
        if value and value not in parts:
            parts.append(value)
    return _normalise_spaces(" ".join(parts))


def _local_entity_surfaces(
    source_text: str,
    *,
    row_label: str = "",
    row_headers: Sequence[Any] = (),
    span: Sequence[int] = (),
) -> List[str]:
    """Preserve row axes or generic sentence-local subject surfaces."""

    surfaces = _normalized_string_list([row_label, *list(row_headers or [])])
    if surfaces:
        return surfaces

    text = str(source_text or "")
    try:
        value_start = max(0, min(len(text), int(span[0])))
    except (IndexError, TypeError, ValueError):
        value_start = len(text)
    prefix = text[:value_start]
    prefix = re.split(r"[\n!?。]|(?<!\d)\.|\.(?!\d)", prefix)[-1]
    prefix = prefix[-180:]

    for match in re.finditer(
        str(SEMANTIC_CANDIDATE_POLICY.get("local_subject_clause_pattern") or ""),
        prefix,
    ):
        surface = _normalise_spaces(match.group(1))
        if surface and surface not in surfaces:
            surfaces.append(surface)
    for match in re.finditer(
        str(
            SEMANTIC_CANDIDATE_POLICY.get("local_subject_latin_entity_pattern")
            or ""
        ),
        prefix,
    ):
        surface = _normalise_spaces(match.group(1))
        if surface and surface not in surfaces:
            surfaces.append(surface)
    return surfaces[:8]


def _numeric_context_excerpt(
    source_text: str,
    span: Sequence[int],
    *,
    max_chars: int = 700,
) -> str:
    """Keep the source sentence around a numeric surface without changing it."""

    text = str(source_text or "")
    if not text:
        return ""
    try:
        value_start, value_end = int(span[0]), int(span[1])
    except (IndexError, TypeError, ValueError):
        value_start, value_end = 0, 0
    value_start = min(max(0, value_start), len(text))
    value_end = min(max(value_start, value_end), len(text))
    boundary_positions = [
        match.start()
        for match in re.finditer(
            r"\n|[!?。]|(?<!\d)\.|\.(?!\d)",
            text,
        )
    ]
    sentence_start = max(
        (position for position in boundary_positions if position < value_start),
        default=-1,
    ) + 1
    next_boundary = min(
        (position for position in boundary_positions if position >= value_end),
        default=-1,
    )
    sentence_end = next_boundary + 1 if next_boundary >= 0 else len(text)
    excerpt = _normalise_spaces(text[sentence_start:sentence_end])
    bounded = max(0, int(max_chars))
    if not bounded or len(excerpt) <= bounded:
        return excerpt
    relative_start = max(0, value_start - sentence_start)
    window_start = max(0, relative_start - bounded // 3)
    window_start = min(window_start, max(0, len(excerpt) - bounded))
    return _normalise_spaces(excerpt[window_start : window_start + bounded])


def _narrative_numeric_rows(
    *,
    source_candidate_id: str,
    evidence_id: str,
    base_record: Mapping[str, Any],
    source_text: str,
    require_explicit_unit: bool = False,
    represented_numeric_rows: Sequence[Mapping[str, Any]] = (),
) -> List[Dict[str, Any]]:
    """Project source-visible prose numbers into immutable numeric candidates."""

    def represented_value_matches(
        item: Mapping[str, Any],
        *,
        normalized_value: float,
        normalized_unit: str,
    ) -> bool:
        if str(item.get("normalized_unit") or "").upper() != normalized_unit:
            return False
        try:
            represented_value = float(item.get("normalized_value"))
        except (TypeError, ValueError):
            return False
        return abs(represented_value - normalized_value) <= max(
            1e-9,
            abs(normalized_value) * 1e-12,
        )

    rows: List[Dict[str, Any]] = []
    seen: set[tuple[Any, ...]] = set()
    for index, surface in enumerate(extract_numeric_surface_candidates(source_text)):
        try:
            normalized_value = float(surface.get("value"))
        except (TypeError, ValueError):
            continue
        raw_surface = _normalise_spaces(str(surface.get("text") or ""))
        if not raw_surface:
            continue
        surface_unit = _normalise_spaces(str(surface.get("unit") or ""))
        if require_explicit_unit and not surface_unit:
            continue
        raw_unit = surface_unit
        if "+" in raw_unit or (raw_unit and not raw_surface.endswith(raw_unit)):
            raw_value = raw_surface
            raw_unit = ""
        else:
            raw_value = _normalise_spaces(
                raw_surface[: -len(raw_unit)] if raw_unit else raw_surface
            )
        surface_kind = str(surface.get("kind") or "")
        normalized_unit = (
            "KRW"
            if surface_kind == "currency"
            else "PERCENT"
            if surface_kind == "percent"
            else "COUNT"
        )
        already_represented = any(
            represented_value_matches(
                item,
                normalized_value=normalized_value,
                normalized_unit=normalized_unit,
            )
            for item in represented_numeric_rows
        )
        if already_represented:
            continue
        span = list(surface.get("span") or [])
        context = _numeric_context_excerpt(source_text, span)
        local_entity_surfaces = _local_entity_surfaces(
            source_text,
            span=span,
        )
        fingerprint = (
            source_candidate_id,
            tuple(span),
            raw_value,
            raw_unit,
            normalized_value,
            normalized_unit,
        )
        if fingerprint in seen:
            continue
        seen.add(fingerprint)
        id_payload = {
            "kind": "numeric",
            "candidate_kind": "sentence_value",
            "source_candidate_id": source_candidate_id,
            "surface_index": index,
            "raw_value": raw_value,
            "raw_unit": raw_unit,
            "source_span": span,
            "context_fingerprint": str(base_record.get("context_fingerprint") or ""),
        }
        rows.append(
            {
                **dict(base_record),
                "candidate_id": _semantic_candidate_id(id_payload),
                "candidate_kind": "sentence_value",
                "kind": "numeric",
                "evidence_id": evidence_id,
                "source_text": context,
                "raw_value": raw_value,
                "raw_unit": raw_unit,
                "normalized_value": normalized_value,
                "normalized_unit": normalized_unit,
                "period": "",
                "value_year": None,
                "column_headers": [],
                "value_role": "",
                "aggregation_stage": "",
                "aggregate_label": "",
                "source_span": span,
                "local_entity_surfaces": local_entity_surfaces,
            }
        )
    return rows


def _structured_source_candidates(
    *,
    candidate_id_prefix: str,
    source_anchor: str,
    text: str,
    metadata: Mapping[str, Any],
) -> List[Dict[str, Any]]:
    """Project one source candidate per physical table row.

    Parser-owned row and value records describe the same physical cells. They
    are merged here so repeated chunk attachments and the two record views do
    not multiply the compiler-visible catalog.
    """

    base_metadata = dict(metadata or {})
    table_object, rows, value_records = _table_record_bundle(base_metadata)
    table_id = _physical_table_id(base_metadata, table_object, rows, value_records)
    origin_source_id = str(candidate_id_prefix or "").split("::", 1)[0].strip()
    projection_metadata = {
        key: value
        for key, value in base_metadata.items()
        if key
        not in {
            "table_row_records_json",
            "table_value_records_json",
            "table_object_json",
        }
    }
    projection_metadata.update(
        {
            "table_source_id": table_id,
            "physical_table_id": table_id,
            "origin_source_id": origin_source_id,
        }
    )

    def axis_key(row_index: Any, column_index: Any) -> tuple[str, str]:
        return str(row_index if row_index is not None else ""), str(
            column_index if column_index is not None else ""
        )

    def column_sort_key(item: Mapping[str, Any]) -> tuple[int, str]:
        raw_index = item.get("column_index")
        try:
            return int(raw_index), ""
        except (TypeError, ValueError):
            return 10**9, str(raw_index or "")

    value_by_axis: Dict[tuple[str, str], Dict[str, Any]] = {}
    for record in value_records:
        key = axis_key(record.get("row_index"), record.get("column_index"))
        value_by_axis.setdefault(key, dict(record))

    projected: List[Dict[str, Any]] = []
    seen_source_ids: set[str] = set()
    for row_index, row in enumerate(rows):
        row_headers = _normalized_string_list(row.get("row_headers"))
        row_label = _normalise_spaces(str(row.get("row_label") or ""))
        if not row_label and row_headers:
            row_label = row_headers[0]
        raw_cells = [
            dict(item)
            for item in (row.get("cells") or [])
            if isinstance(item, Mapping)
        ]
        cells: List[Dict[str, Any]] = []
        for cell_index, raw_cell in enumerate(raw_cells):
            cell = dict(raw_cell)
            column_index = cell.get("column_index")
            if column_index is None:
                column_index = cell_index
                cell["column_index"] = column_index
            value_record = value_by_axis.get(axis_key(row_index, column_index), {})
            for field in (
                "semantic_label",
                "semantic_aliases",
                "label_source",
                "period_text",
                "period_labels",
                "value_role",
                "aggregation_stage",
                "aggregate_label",
                "aggregate_role",
            ):
                if value_record.get(field) not in (None, "", []):
                    cell[field] = value_record.get(field)
            if value_record.get("column_headers"):
                cell["column_headers"] = list(value_record["column_headers"])
            if value_record.get("unit_hint") and not cell.get("unit_hint"):
                cell["unit_hint"] = value_record["unit_hint"]
            if value_record.get("value_id"):
                cell["value_id"] = value_record["value_id"]
            cell_id, physical_cell_key = _physical_cell_identity(
                table_id=table_id,
                row_key=_normalise_spaces(str(row.get("row_id") or row_index)),
                cell=cell,
            )
            cell["physical_cell_id"] = cell_id
            cell["physical_value_id"] = _normalise_spaces(
                str(value_record.get("value_id") or "")
            )
            cell["physical_cell_key"] = physical_cell_key
            cells.append(cell)
        if not row_label or not cells:
            continue

        physical_row_id, physical_row_key = _physical_row_identity(
            table_id=table_id,
            row=row,
            row_index=row_index,
            row_label=row_label,
            row_headers=row_headers,
            cells=cells,
        )
        for cell in cells:
            _cell_id, physical_cell_key = _physical_cell_identity(
                table_id=table_id,
                row_key=physical_row_id,
                cell=cell,
            )
            cell["physical_cell_key"] = physical_cell_key

        source_candidate_id = (
            f"table_{_stable_material_digest(table_id)}::"
            f"row_{_stable_material_digest(physical_row_key)}"
        )
        if source_candidate_id in seen_source_ids:
            continue
        seen_source_ids.add(source_candidate_id)
        row_text = _normalise_spaces(
            " | ".join(
                [
                    *(_normalized_string_list([row_label, *row_headers])),
                    *[
                        " / ".join(
                            [
                                *_normalized_string_list(cell.get("column_headers")),
                                _normalise_spaces(str(cell.get("value_text") or "")),
                                _normalise_spaces(
                                    str(
                                        cell.get("unit_hint")
                                        or base_metadata.get("unit_hint")
                                        or ""
                                    )
                                ),
                            ]
                        )
                        for cell in cells
                    ],
                ]
            )
        )
        context_text = _table_context_text(base_metadata, table_object)
        row_metadata = {
            **projection_metadata,
            "row_id": physical_row_id,
            "source_row_id": physical_row_key,
            "physical_row_id": physical_row_id,
            "physical_row_key": physical_row_key,
            "row_label": row_label,
            "semantic_label": row_label,
            "row_headers": row_headers,
            "local_entity_surfaces": _local_entity_surfaces(
                row_text,
                row_label=row_label,
                row_headers=row_headers,
            ),
            "structured_cells": cells,
            "row_text": row_text,
        }
        projected.append(
            _semantic_source_candidate(
                candidate_id=source_candidate_id,
                source_anchor=source_anchor,
                text=_normalise_spaces(" ".join((context_text, row_text))),
                metadata=row_metadata,
                candidate_kind="structured_row",
                evidence_id=table_id,
                origin_source_id=origin_source_id,
            )
        )

    if not rows:
        value_groups: Dict[tuple[str, str], List[Dict[str, Any]]] = {}
        for record in value_records:
            label = _normalise_spaces(
                str(record.get("semantic_label") or record.get("row_label") or "")
            )
            if label:
                group_key = (str(record.get("row_index") or ""), label)
                value_groups.setdefault(group_key, []).append(dict(record))
        for (raw_row_index, row_label), records in sorted(value_groups.items()):
            records = sorted(records, key=column_sort_key)
            row_headers = _normalized_string_list(
                next((record.get("row_headers") for record in records if record.get("row_headers")), [])
            )
            cells: List[Dict[str, Any]] = []
            for record in records:
                value_text = _normalise_spaces(str(record.get("value_text") or ""))
                if not value_text:
                    continue
                period_text = _normalise_spaces(str(record.get("period_text") or ""))
                headers = _normalized_string_list(
                    record.get("column_headers") or record.get("period_labels")
                )
                if not headers and period_text:
                    headers = [period_text]
                cell = {
                    "cell_id": "",
                    "value_id": _normalise_spaces(str(record.get("value_id") or "")),
                    "column_index": record.get("column_index"),
                    "column_headers": headers,
                    "period_text": period_text,
                    "period_labels": _normalized_string_list(record.get("period_labels")),
                    "value_text": value_text,
                    "unit_hint": _normalise_spaces(
                        str(record.get("unit_hint") or base_metadata.get("unit_hint") or "")
                    ),
                    "value_role": _normalise_spaces(str(record.get("value_role") or "")),
                    "aggregation_stage": _normalise_spaces(
                        str(record.get("aggregation_stage") or "")
                    ),
                    "aggregate_label": _normalise_spaces(
                        str(record.get("aggregate_label") or "")
                    ),
                }
                cell_id, physical_cell_key = _physical_cell_identity(
                    table_id=table_id,
                    row_key=raw_row_index,
                    cell=cell,
                )
                cell["physical_cell_id"] = cell_id
                cell["physical_value_id"] = cell["value_id"]
                cell["physical_cell_key"] = physical_cell_key
                cells.append(cell)
            if not cells:
                continue
            fallback_row = {
                "row_label": row_label,
                "row_headers": row_headers,
                "cells": cells,
            }
            physical_row_id, physical_row_key = _physical_row_identity(
                table_id=table_id,
                row=fallback_row,
                row_index=raw_row_index,
                row_label=row_label,
                row_headers=row_headers,
                cells=cells,
            )
            for cell in cells:
                _cell_id, physical_cell_key = _physical_cell_identity(
                    table_id=table_id,
                    row_key=physical_row_id,
                    cell=cell,
                )
                cell["physical_cell_key"] = physical_cell_key
            source_candidate_id = (
                f"table_{_stable_material_digest(table_id)}::"
                f"row_{_stable_material_digest(physical_row_key)}"
            )
            if source_candidate_id in seen_source_ids:
                continue
            seen_source_ids.add(source_candidate_id)
            row_text = _normalise_spaces(
                " | ".join(
                    [
                        *(_normalized_string_list([row_label, *row_headers])),
                        *[
                            " / ".join(
                                [
                                    *_normalized_string_list(cell.get("column_headers")),
                                    _normalise_spaces(str(cell.get("value_text") or "")),
                                    _normalise_spaces(str(cell.get("unit_hint") or "")),
                                ]
                            )
                            for cell in cells
                        ],
                    ]
                )
            )
            value_metadata = {
                **projection_metadata,
                "row_id": physical_row_id,
                "source_row_id": physical_row_key,
                "physical_row_id": physical_row_id,
                "physical_row_key": physical_row_key,
                "row_label": row_label,
                "semantic_label": row_label,
                "row_headers": row_headers,
                "local_entity_surfaces": _local_entity_surfaces(
                    row_text,
                    row_label=row_label,
                    row_headers=row_headers,
                ),
                "structured_cells": cells,
                "row_text": row_text,
            }
            projected.append(
                _semantic_source_candidate(
                    candidate_id=source_candidate_id,
                    source_anchor=source_anchor,
                    text=_normalise_spaces(
                        " ".join(
                            (
                                _table_context_text(base_metadata, table_object),
                                row_text,
                            )
                        )
                    ),
                    metadata=value_metadata,
                    candidate_kind="structured_value",
                    evidence_id=table_id,
                    origin_source_id=origin_source_id,
                )
            )

    if rows or value_records:
        return projected

    pipe_rows = [
        _normalise_spaces(line)
        for line in str(text or "").splitlines()
        if _normalise_spaces(line) and "|" in line
    ]
    if not (
        base_metadata.get("table_source_id")
        or base_metadata.get("source_table_id")
        or base_metadata.get("table_id")
    ) and pipe_rows:
        table_id = f"legacy_table_{_stable_material_digest(pipe_rows)}"
        projection_metadata["table_source_id"] = table_id
        projection_metadata["physical_table_id"] = table_id
    for index, row_text in enumerate(pipe_rows):
        row_label = _normalise_spaces(row_text.split("|", 1)[0])
        cells = parse_unstructured_table_row_cells(row_text, base_metadata)
        if not row_label or not cells:
            continue
        row_headers = [row_label]
        physical_row_id, physical_row_key = _physical_row_identity(
            table_id=table_id,
            row={},
            row_index=index,
            row_label=row_label,
            row_headers=row_headers,
            cells=cells,
        )
        for cell_index, cell in enumerate(cells):
            cell.setdefault("column_index", cell_index)
            cell_id, physical_cell_key = _physical_cell_identity(
                table_id=table_id,
                row_key=physical_row_id,
                cell=cell,
            )
            cell["physical_cell_id"] = cell_id
            cell["physical_value_id"] = ""
            cell["physical_cell_key"] = physical_cell_key
        source_candidate_id = (
            f"table_{_stable_material_digest(table_id)}::"
            f"row_{_stable_material_digest(physical_row_key)}"
        )
        if source_candidate_id in seen_source_ids:
            continue
        seen_source_ids.add(source_candidate_id)
        row_metadata = {
            **projection_metadata,
            "row_id": physical_row_id,
            "source_row_id": physical_row_key,
            "physical_row_id": physical_row_id,
            "physical_row_key": physical_row_key,
            "row_label": row_label,
            "semantic_label": row_label,
            "row_headers": row_headers,
            "local_entity_surfaces": [row_label],
            "row_text": row_text,
            "structured_cells": cells,
        }
        projected.append(
            _semantic_source_candidate(
                candidate_id=source_candidate_id,
                source_anchor=source_anchor,
                text=row_text,
                metadata=row_metadata,
                candidate_kind="table_row",
                evidence_id=table_id,
                origin_source_id=origin_source_id,
            )
        )
    return projected


def build_semantic_source_candidates(
    state: Mapping[str, Any],
    *,
    source_anchor_builder: Any,
) -> List[Dict[str, Any]]:
    """Build a source-complete candidate pool without operation-specific scoring."""

    candidates: List[Dict[str, Any]] = []
    seen: set[str] = set()

    for item in list(state.get("evidence_items") or []):
        if not isinstance(item, Mapping):
            continue
        evidence = dict(item)
        metadata = dict(evidence.get("metadata") or {})
        candidate_id = str(evidence.get("evidence_id") or evidence.get("source_anchor") or "").strip()
        if not candidate_id or candidate_id in seen:
            continue
        seen.add(candidate_id)
        anchor = _normalise_spaces(str(evidence.get("source_anchor") or ""))
        text = _normalise_spaces(
            " ".join(
                str(value or "")
                for value in (
                    evidence.get("claim"),
                    evidence.get("quote_span"),
                    evidence.get("source_context"),
                    evidence.get("raw_row_text"),
                )
                if str(value or "").strip()
            )
        )
        candidates.append(
            _semantic_source_candidate(
                candidate_id=candidate_id,
                source_anchor=anchor,
                text=text,
                metadata=metadata,
                candidate_kind="evidence",
            )
        )
        raw_row_text = _normalise_spaces(str(evidence.get("raw_row_text") or ""))
        if raw_row_text:
            row_id = f"{candidate_id}::raw_row"
            seen.add(row_id)
            candidates.extend(
                _structured_source_candidates(
                    candidate_id_prefix=row_id,
                    source_anchor=anchor,
                    text=raw_row_text,
                    metadata={**metadata, "row_text": raw_row_text},
                )
                or [
                    _semantic_source_candidate(
                        candidate_id=row_id,
                        source_anchor=anchor,
                        text=raw_row_text,
                        metadata={
                            **metadata,
                            "row_text": raw_row_text,
                            "row_label": raw_row_text.split("|", 1)[0].strip(),
                            "structured_cells": parse_unstructured_table_row_cells(raw_row_text, metadata),
                        },
                        candidate_kind="evidence_row",
                    )
                ]
            )

    doc_stream = [
        *list(state.get("retrieved_docs") or []),
        *list(state.get("seed_retrieved_docs") or []),
    ]
    for index, entry in enumerate(doc_stream, start=1):
        try:
            doc, _score = entry
        except (TypeError, ValueError):
            continue
        metadata = dict(getattr(doc, "metadata", {}) or {})
        candidate_id = str(metadata.get("chunk_uid") or f"doc_{index}").strip()
        if not candidate_id or candidate_id in seen:
            continue
        seen.add(candidate_id)
        anchor = _normalise_spaces(str(source_anchor_builder(metadata) or ""))
        text = str(getattr(doc, "page_content", "") or "")
        projected_candidates = _structured_source_candidates(
            candidate_id_prefix=candidate_id,
            source_anchor=anchor,
            text=text,
            metadata=metadata,
        )
        if projected_candidates:
            table_object, rows, value_records = _table_record_bundle(metadata)
            table_id = _physical_table_id(
                metadata,
                table_object,
                rows,
                value_records,
            )
            context_text = _table_context_text(metadata, table_object)
            context_id = (
                f"table_{_stable_material_digest(table_id)}::context"
            )
            if context_text and context_id not in seen:
                seen.add(context_id)
                context_metadata = {
                    key: value
                    for key, value in metadata.items()
                    if key
                    not in {
                        "table_row_records_json",
                        "table_value_records_json",
                        "table_object_json",
                    }
                }
                context_metadata.update(
                    {
                        "table_source_id": table_id,
                        "physical_table_id": table_id,
                        "origin_source_id": candidate_id,
                    }
                )
                candidates.append(
                    _semantic_source_candidate(
                        candidate_id=context_id,
                        source_anchor=anchor,
                        text=context_text,
                        metadata=context_metadata,
                        candidate_kind="table_context",
                        evidence_id=table_id,
                        origin_source_id=candidate_id,
                    )
                )
        else:
            candidates.append(
                _semantic_source_candidate(
                    candidate_id=candidate_id,
                    source_anchor=anchor,
                    text=text,
                    metadata=metadata,
                    candidate_kind="chunk",
                )
            )
        for projected in projected_candidates:
            projected_id = str(projected.get("candidate_id") or "")
            if not projected_id or projected_id in seen:
                continue
            seen.add(projected_id)
            candidates.append(projected)
    return candidates


def build_semantic_candidate_catalog(
    candidates: Sequence[Mapping[str, Any]],
    *,
    evidence_items: Sequence[Mapping[str, Any]] = (),
) -> List[Dict[str, Any]]:
    """Flatten retrieved row/cell evidence into immutable LLM-selectable candidates.

    IDs are derived from provenance and source-visible material. The model never
    supplies values or source identifiers; it can only select IDs from this list.
    """

    evidence_by_id = {
        str(item.get("evidence_id") or "").strip(): dict(item)
        for item in evidence_items
        if str(item.get("evidence_id") or "").strip()
    }
    numeric_rows: List[Dict[str, Any]] = []
    narrative_rows: List[Dict[str, Any]] = []
    seen_fingerprints: set[tuple[Any, ...]] = set()

    for candidate in candidates:
        current = dict(candidate or {})
        source_numeric_start = len(numeric_rows)
        metadata = dict(current.get("metadata") or {})
        source_candidate_id = str(current.get("candidate_id") or "").strip()
        if not source_candidate_id:
            continue
        evidence_id = str(current.get("evidence_id") or "").strip()
        if not evidence_id:
            evidence_id = source_candidate_id.split("::", 1)[0]
        evidence_item = dict(evidence_by_id.get(evidence_id) or {})
        source_anchor = _normalise_spaces(
            str(current.get("source_anchor") or evidence_item.get("source_anchor") or "")
        )
        candidate_kind = str(current.get("candidate_kind") or "")
        if candidate_kind in {"structured_row", "structured_value", "table_row"}:
            source_text = _normalise_spaces(str(current.get("text") or ""))
        else:
            source_parts: List[str] = []
            for raw_value in (
                metadata.get("row_text"),
                current.get("text"),
                evidence_item.get("raw_row_text"),
                evidence_item.get("quote_span"),
                evidence_item.get("claim"),
            ):
                value = _normalise_spaces(str(raw_value or ""))
                if value and value not in source_parts:
                    source_parts.append(value)
            source_text = _normalise_spaces(" ".join(source_parts))
        row_label = _normalise_spaces(
            str(
                metadata.get("semantic_label")
                or metadata.get("row_label")
                or evidence_item.get("label")
                or evidence_item.get("parent_category")
                or ""
            )
        )
        source_row_id = _normalise_spaces(
            str(
                metadata.get("source_row_id")
                or metadata.get("row_id")
                or evidence_item.get("source_row_id")
                or evidence_id
                or source_candidate_id
            )
        )
        context_fingerprint = _semantic_catalog_context_fingerprint(current, metadata)
        raw_row_headers = metadata.get("row_headers") or []
        if isinstance(raw_row_headers, (str, bytes)):
            raw_row_headers = [raw_row_headers]
        elif not isinstance(raw_row_headers, Sequence):
            raw_row_headers = []
        consolidation_scope, consolidation_scope_source = _candidate_consolidation_scope(
            current,
            metadata,
            source_text,
        )
        row_headers = [
            _normalise_spaces(str(item))
            for item in raw_row_headers
            if _normalise_spaces(str(item))
        ]
        raw_local_entity_surfaces = metadata.get("local_entity_surfaces") or []
        local_entity_surfaces = _normalized_string_list(raw_local_entity_surfaces)
        if not local_entity_surfaces and candidate_kind in {
            "structured_row",
            "structured_value",
            "table_row",
        }:
            local_entity_surfaces = _local_entity_surfaces(
                source_text,
                row_label=row_label,
                row_headers=row_headers,
            )
        document_company = _normalise_spaces(
            str(
                metadata.get("company")
                or metadata.get("entity")
                or metadata.get("corp_name")
                or ""
            )
        )
        base_record: Dict[str, Any] = {
            "source_candidate_id": source_candidate_id,
            "evidence_id": evidence_id,
            "source_anchor": source_anchor,
            "source_row_id": source_row_id,
            "table_source_id": _normalise_spaces(
                str(
                    metadata.get("physical_table_id")
                    or metadata.get("table_source_id")
                    or metadata.get("source_table_id")
                    or metadata.get("table_id")
                    or ""
                )
            ),
            "physical_table_id": _normalise_spaces(
                str(metadata.get("physical_table_id") or "")
            ),
            "physical_row_id": _normalise_spaces(
                str(metadata.get("physical_row_id") or metadata.get("row_id") or "")
            ),
            "row_label": row_label,
            "row_headers": row_headers,
            "local_entity_surfaces": local_entity_surfaces,
            "statement_type": _candidate_statement_type(current, metadata),
            "document_company": document_company,
            "company": document_company,
            "year": metadata.get("year"),
            "consolidation_scope": consolidation_scope,
            "consolidation_scope_source": consolidation_scope_source,
            "segment": _normalise_spaces(
                str(metadata.get("segment_label") or evidence_item.get("parent_category") or "")
            ),
            "basis": _normalise_spaces(
                str(metadata.get("basis") or metadata.get("accounting_basis") or "")
            ),
            "context_fingerprint": context_fingerprint,
            "source_text": source_text[:1200],
            "candidate_kind": candidate_kind,
        }

        cells = [dict(cell) for cell in (metadata.get("structured_cells") or []) if isinstance(cell, dict)]
        if not cells and str(current.get("candidate_kind") or "") in {"table_row", "evidence_row"}:
            cells = parse_unstructured_table_row_cells(str(metadata.get("row_text") or ""), metadata)
        if not cells:
            raw_value = _normalise_spaces(str(evidence_item.get("raw_value") or metadata.get("raw_value") or ""))
            if raw_value:
                cells = [
                    {
                        "value_text": raw_value,
                        "unit_hint": evidence_item.get("raw_unit") or metadata.get("unit_hint") or "",
                        "period_text": evidence_item.get("period") or metadata.get("period_text") or "",
                    }
                ]

        for cell_index, cell in enumerate(cells):
            raw_value = _normalise_spaces(str(cell.get("value_text") or ""))
            if not raw_value or not re.search(r"\d", raw_value):
                continue
            source_unit_hint = _normalise_spaces(
                str(cell.get("unit_hint") or metadata.get("unit_hint") or "")
            )
            raw_unit, raw_unit_source = resolve_source_numeric_unit(
                raw_value,
                source_unit_hint,
            )
            normalized_value, normalized_unit = _normalise_operand_value(raw_value, raw_unit)
            if normalized_value is None:
                continue
            value_year = _candidate_value_year(cells, cell_index, metadata)
            period, source_period_surface, period_source = _candidate_period_projection(
                cell,
                metadata,
                value_year=value_year,
            )
            column_headers = [
                _normalise_spaces(str(item))
                for item in (cell.get("column_headers") or [])
                if _normalise_spaces(str(item))
            ]
            physical_cell_id = _normalise_spaces(
                str(cell.get("physical_cell_id") or cell.get("cell_id") or "")
            )
            physical_value_id = _normalise_spaces(
                str(cell.get("physical_value_id") or cell.get("value_id") or "")
            )
            physical_cell_key = _normalise_spaces(
                str(cell.get("physical_cell_key") or "")
            )
            fingerprint = (
                ("physical_cell", physical_cell_key)
                if physical_cell_key
                else (
                    "legacy_cell",
                    source_row_id,
                    row_label,
                    tuple(column_headers),
                    raw_value,
                    source_unit_hint,
                    source_period_surface,
                    context_fingerprint,
                )
            )
            if fingerprint in seen_fingerprints:
                continue
            seen_fingerprints.add(fingerprint)
            if physical_cell_key:
                id_payload = {
                    "kind": "numeric",
                    "physical_table_id": base_record.get("physical_table_id"),
                    "physical_row_id": base_record.get("physical_row_id"),
                    "physical_cell_id": physical_cell_id,
                    "physical_value_id": physical_value_id,
                    "physical_cell_key": physical_cell_key,
                    "row_label": row_label,
                    "column_headers": column_headers,
                    "raw_value": raw_value,
                    "raw_unit": source_unit_hint,
                    "period": source_period_surface,
                    "context_fingerprint": context_fingerprint,
                }
            else:
                id_payload = {
                    "kind": "numeric",
                    "source_candidate_id": source_candidate_id,
                    "cell_index": cell_index,
                    "source_row_id": source_row_id,
                    "row_label": row_label,
                    "column_headers": column_headers,
                    "raw_value": raw_value,
                    "raw_unit": source_unit_hint,
                    "period": source_period_surface,
                    "context_fingerprint": context_fingerprint,
                }
            aggregation_stage, aggregate_label = _candidate_aggregate_metadata(
                cell,
                metadata,
                row_label,
            )
            numeric_rows.append(
                {
                    **base_record,
                    "candidate_id": _semantic_candidate_id(id_payload),
                    "kind": "numeric",
                    "physical_cell_id": physical_cell_id,
                    "physical_value_id": physical_value_id,
                    "physical_cell_key": physical_cell_key,
                    "raw_value": raw_value,
                    "raw_unit": raw_unit,
                    "source_unit_hint": source_unit_hint,
                    "raw_unit_source": raw_unit_source,
                    "normalized_value": normalized_value,
                    "normalized_unit": normalized_unit,
                    "period": period,
                    "source_period_surface": source_period_surface,
                    "period_source": period_source,
                    "value_year": value_year,
                    "column_headers": column_headers,
                    "value_role": _candidate_value_role(
                        cell,
                        value_year=value_year,
                        metadata=metadata,
                    ),
                    "aggregation_stage": aggregation_stage,
                    "aggregate_label": aggregate_label,
                }
            )

        has_structured_material = bool(
            cells
            or metadata.get("table_row_records_json")
            or metadata.get("table_value_records_json")
            or metadata.get("table_object_json")
        )
        is_explicit_non_table_source = (
            metadata.get("is_table") is False
            or _normalise_spaces(str(metadata.get("block_type") or "")).lower()
            not in {"", "table", "table_row"}
        )
        if candidate_kind in {"chunk", "evidence"}:
            narrative_numeric_source = _normalise_spaces(
                str(current.get("text") or evidence_item.get("quote_span") or "")
            )
            numeric_rows.extend(
                _narrative_numeric_rows(
                    source_candidate_id=source_candidate_id,
                    evidence_id=evidence_id,
                    base_record=base_record,
                    source_text=narrative_numeric_source,
                    require_explicit_unit=(
                        has_structured_material and not is_explicit_non_table_source
                    ),
                    represented_numeric_rows=numeric_rows[source_numeric_start:],
                )
            )

        if source_text and candidate_kind in {
            "chunk",
            "evidence",
            "table_context",
        }:
            narrative_payload = {
                "kind": "narrative",
                "source_candidate_id": source_candidate_id,
                "source_row_id": source_row_id,
                "source_text": source_text,
                "context_fingerprint": context_fingerprint,
            }
            narrative_rows.append(
                {
                    **base_record,
                    "candidate_id": _semantic_candidate_id(narrative_payload),
                    "kind": "narrative",
                    "raw_value": "",
                    "raw_unit": "",
                    "normalized_value": None,
                    "normalized_unit": "UNKNOWN",
                    "period": "",
                    "column_headers": [],
                }
            )

    return [*numeric_rows, *narrative_rows]


def _candidate_statement_type(candidate: Dict[str, Any], metadata: Dict[str, Any]) -> str:
    explicit_statement_type = _normalise_spaces(str(metadata.get("statement_type") or ""))
    if explicit_statement_type:
        return explicit_statement_type
    surface = _normalise_spaces(
        " ".join(
            str(value or "")
            for value in (
                metadata.get("section_path"),
                metadata.get("section_title"),
                metadata.get("local_heading"),
                metadata.get("table_context"),
                candidate.get("source_anchor"),
                candidate.get("source_context"),
            )
            if str(value or "").strip()
        )
    )
    if not surface:
        return ""
    for policy in FINANCIAL_DOCUMENT_STATEMENT_HINT_POLICIES:
        markers = [
            _normalise_spaces(str(marker))
            for marker in (policy.get("markers") or [])
            if _normalise_spaces(str(marker))
        ]
        if not any(marker in surface for marker in markers):
            continue
        statement_types = [
            _normalise_spaces(str(statement_type))
            for statement_type in (policy.get("statement_types") or [])
            if _normalise_spaces(str(statement_type))
        ]
        if statement_types:
            return statement_types[0]
    return ""
