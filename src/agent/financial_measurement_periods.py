"""Typed request periods and literal source-date geometry, not intent inference."""
from __future__ import annotations

from datetime import date
import re
from typing import Any, Mapping, Sequence

from src.agent.financial_request_units import build_request_units
from src.config.retrieval_policy import MEASUREMENT_PERIOD_POLICY


def scope_period(scope: Mapping[str, Any]) -> Any:
    """A declared structure owns execution; the free text stays unchanged."""
    value = scope.get("measurement_period")
    return value if value is not None else scope.get("period", "")


def _iso_date(value: Any) -> date:
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise ValueError("invalid_measurement_period")
    return date.fromisoformat(value)


def period_contract_error(value: Any) -> str:
    """Recheck plain mappings too; Pydantic is not execution authority."""
    if not isinstance(value, Mapping):
        return "invalid_measurement_period"
    fields = {
        "unspecified": set(), "unresolved": {"request_unit_ids"},
        "year": {"year", "request_unit_ids"},
        "relative_year": {"anchor_year", "year_offset", "request_unit_ids"},
        "date": {"date", "request_unit_ids"},
        "date_interval": {"start_date", "end_date", "request_unit_ids"},
    }
    kind = value.get("kind")
    if not isinstance(kind, str) or kind not in fields or set(value) != fields[kind] | {"kind"}:
        return "invalid_measurement_period"
    if kind != "unspecified":
        refs = value.get("request_unit_ids")
        if (not isinstance(refs, (list, tuple)) or not refs
                or any(not isinstance(ref, str) or not ref for ref in refs)
                or len(set(refs)) != len(refs)):
            return "invalid_measurement_period_request"
    try:
        if kind in {"year", "relative_year"}:
            year = value["year"] if kind == "year" else value["anchor_year"]
            offset = value.get("year_offset", 0)
            if type(year) is not int or type(offset) is not int or not 1 <= year <= 9999 or not 1 <= year + offset <= 9999:
                return "invalid_measurement_period"
        elif kind == "date":
            _iso_date(value["date"])
        elif kind == "date_interval":
            if _iso_date(value["start_date"]) > _iso_date(value["end_date"]):
                return "invalid_measurement_period"
    except (ValueError, TypeError):
        return "invalid_measurement_period"
    return ""


def measurement_period_requirement_errors(
    obligations: Sequence[Mapping[str, Any]], query: str,
) -> list[dict[str, str]]:
    known = {unit.request_unit_id for unit in build_request_units(query)}
    errors = []
    for output in obligations:
        output_id = str(output.get("obligation_id") or "")
        owned = set(output.get("request_unit_ids") or [])
        for owner in [output, *(output.get("evidence_requirements") or [])]:
            if not isinstance(owner, Mapping):
                continue  # The existing requirement-shape validator owns this error.
            value = (owner.get("scope") or {}).get("measurement_period")
            if value is None:
                continue  # Historical labels never receive an inferred structure.
            code = period_contract_error(value)
            if not code and any(ref not in known or ref not in owned for ref in value.get("request_unit_ids", [])):
                code = "unowned_measurement_period_request"
            if code:
                errors.append(dict(code=code, obligation_id=output_id,
                    owner_id=str(owner.get("requirement_id") or output_id), candidate_id="",
                    location="scope.measurement_period", repair_action="repair_requirements", detail=""))
    return errors


def legacy_period_label(value: str) -> bool:
    """Only whole historical annual labels retain the old annual contract."""
    return any(re.fullmatch(pattern, value) for pattern in MEASUREMENT_PERIOD_POLICY["legacy_annual_labels"])


def _source_date_shape(surface: str) -> tuple[str, ...] | None:
    matches = list(re.finditer(MEASUREMENT_PERIOD_POLICY["source_date_pattern"], surface))
    if not matches:
        return None
    dates = []
    try:
        for match in matches:
            dates.append(date(int(match["year"]), int(match["month"]), int(match["day"])).isoformat())
    except ValueError:
        return ("unknown",)
    if len(matches) == 2:
        between = surface[matches[0].end():matches[1].start()]
        if re.fullmatch(MEASUREMENT_PERIOD_POLICY["source_range_separator"], between) and dates[0] <= dates[1]:
            return ("date_interval", *dates)
        return ("unknown",)
    if len(matches) != 1:
        return ("unknown",)
    remainder = surface[:matches[0].start()] + surface[matches[0].end():]
    # A partial second endpoint/range must not become a point-date reading.
    if re.search(MEASUREMENT_PERIOD_POLICY["source_partial_range_pattern"], remainder):
        return ("unknown",)
    return ("date", dates[0])


def source_date_shape(candidate: Mapping[str, Any]) -> tuple[str, ...] | None:
    """Use each existing local period axis independently, never join axes."""
    raw_headers = candidate.get("column_headers") or []
    headers = [raw_headers] if isinstance(raw_headers, str) else [str(item) for item in raw_headers]
    surface = str(candidate.get("source_period_surface") or "")
    # This surface may itself be the old presentation join of header axes.
    surfaces = headers + ([] if surface == " / ".join(headers) else [surface])
    if not any(surfaces):
        surfaces = [str(candidate.get("period") or "")]
    shapes = {_source_date_shape(item) for item in surfaces}
    shapes.discard(None)
    if not shapes:
        return None
    return next(iter(shapes)) if len(shapes) == 1 else ("unknown",)


def date_period_state(value: Mapping[str, Any], candidate: Mapping[str, Any], *, has_year: bool) -> str:
    shape = source_date_shape(candidate)
    if shape is None:
        return "conflict" if has_year else "unknown"
    if shape == ("unknown",):
        return "unknown"
    wanted = (("date", value["date"]) if value["kind"] == "date"
              else ("date_interval", value["start_date"], value["end_date"]))
    return "match" if wanted == shape else "conflict"
