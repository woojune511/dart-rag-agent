"""Located column-axis observations and explicit model-selected annual readings."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from typing import Any, Mapping, Sequence

from src.agent.financial_scope_policies import explicit_period_years


LOCATION_FIELDS = ("source_document_id", "source_document_sha256", "physical_table_id", "source_table_locator")


def _digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:20]


def _calendar_year(text: Any) -> int | None:
    text = str(text or "").strip()
    years = explicit_period_years(text)
    # Scalar row members need a whole annual label: a decimal could otherwise
    # resemble year.month in the broader, already located header grammar.
    year = next(iter(years)) if len(years) == 1 else None
    return year if year is not None and text == str(year) else None


def _location(row: Mapping[str, Any]) -> tuple:
    return tuple(row.get(key) for key in LOCATION_FIELDS)


def _located_cells(metadata: Mapping[str, Any]) -> list[dict[str, Any]]:
    cells = metadata.get("structured_cells") or []
    if (not all(_location(metadata)) or not metadata.get("physical_row_id") or not cells
            or any(not isinstance(cell, dict) or type(cell.get("column_index")) is not int
                   or cell["column_index"] < 0 or not cell.get("physical_cell_id") for cell in cells)):
        return []
    if len({cell["column_index"] for cell in cells}) != len(cells):
        return []
    return cells


def project_column_period_evidence(
    sources: Sequence[Mapping[str, Any]], catalog: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Attach observed same-column cells, never infer a value's measurement year.

    Parser column-labelled annual cells identify a possible period axis. Complete
    row members include non-annual columns, preventing a total column from borrowing
    the table's general year. This does not grant those cells operand authority.
    """
    by_source, axes = {}, []
    for source in sources:
        metadata = source.get("metadata") or {}
        cells = _located_cells(metadata)
        if not cells:
            continue
        by_source[source["candidate_id"]] = (metadata, cells)
        labelled = [cell for cell in cells if cell.get("label_source") == "column"]
        if (labelled and not metadata.get("unit_hint") and all(
                not cell.get("unit_hint") and _calendar_year(cell.get("value_text")) is not None
                for cell in labelled)):
            axes.append((source["candidate_id"], metadata, cells))
    result = []
    for candidate in catalog:
        observed = []
        own = by_source.get(candidate.get("source_candidate_id"))
        if candidate.get("kind") == "numeric" and own:
            metadata, cells = own
            selected = next((cell for cell in cells if cell["physical_cell_id"] == candidate.get("physical_cell_id")), None)
            if selected and _location(candidate) == _location(metadata):
                for source_id, axis_metadata, axis_cells in axes:
                    if (_location(axis_metadata) != _location(metadata)
                            or axis_metadata["physical_row_id"] == metadata["physical_row_id"]):
                        continue
                    for cell in axis_cells:
                        if (cell["column_index"] != selected["column_index"]
                                or cell.get("column_headers") != selected.get("column_headers")):
                            continue
                        proof = dict(candidate_id=candidate["candidate_id"],
                            target_physical_cell_id=candidate["physical_cell_id"], column_index=selected["column_index"],
                            **{key: candidate[key] for key in LOCATION_FIELDS},
                            source=dict(source_candidate_id=source_id, physical_row_id=axis_metadata["physical_row_id"],
                                physical_cell_id=cell["physical_cell_id"], physical_value_id=cell.get("physical_value_id", ""),
                                column_index=cell["column_index"], raw_value=str(cell.get("value_text") or ""),
                                raw_unit=str(cell.get("unit_hint") or ""), label_source=cell.get("label_source", ""),
                                row_headers=list(axis_metadata.get("row_headers") or []),
                                column_headers=list(cell.get("column_headers") or [])))
                        observed.append(dict(column_period_id="column_period_" + _digest(proof), **proof))
        projected = dict(candidate)
        projected.pop("source_column_period_evidence", None)
        if observed:
            projected["source_column_period_evidence"] = sorted(observed, key=lambda row: row["column_period_id"])
        result.append(projected)
    return result


def source_period_options(candidate: Mapping[str, Any]) -> list[dict[str, Any]]:
    options = []
    for evidence in candidate.get("source_column_period_evidence") or []:
        source = evidence.get("source") or {}
        value_year = _calendar_year(source.get("raw_value"))
        material = {key: value for key, value in evidence.items() if key != "column_period_id"}
        if (value_year is None or source.get("raw_unit") or source.get("label_source") != "column"
                or evidence.get("column_period_id") != "column_period_" + _digest(material)
                or evidence.get("candidate_id") != candidate.get("candidate_id")
                or evidence.get("target_physical_cell_id") != candidate.get("physical_cell_id")
                or not all(_location(candidate)) or _location(evidence) != _location(candidate)
                or source.get("physical_row_id") == candidate.get("physical_row_id")
                or source.get("column_index") != evidence.get("column_index")
                or source.get("column_headers") != candidate.get("column_headers")):
            continue
        options.append(dict(period_option_id=evidence["column_period_id"], period=str(value_year),
            value_year=value_year, evidence=deepcopy(evidence)))
    return options


def apply_source_period_resolution(candidate: Mapping[str, Any], proof: Mapping[str, Any]) -> dict[str, Any]:
    resolution = proof.get("period_resolution")
    if not resolution:
        return dict(candidate)
    return {**candidate, "period": resolution["period"], "value_year": resolution["value_year"],
            "period_source": "source_column_period_binding", "period_label_scope": "source_column",
            "source_period_resolution": deepcopy(resolution)}
