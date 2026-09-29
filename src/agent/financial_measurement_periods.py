"""Typed request periods and literal source-date geometry, not intent inference."""
from __future__ import annotations

from datetime import date, timedelta
import re
from typing import Any, Mapping, Sequence

from src.agent.financial_request_units import build_request_units
from src.agent.financial_scope_policies import is_period_only_surface
from src.agent.financial_source_interpretation import attached_context_quote
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
    if not isinstance(kind, str) or kind not in fields:
        return "invalid_measurement_period"
    expected_fields = fields[kind] | {"kind"}
    if kind in {"year", "relative_year"} and "coverage" in value:
        expected_fields.add("coverage")
        if value["coverage"] not in ("whole_year", "within_year"):
            return "invalid_measurement_period"
    if set(value) != expected_fields:
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


def _source_period_surfaces(candidate: Mapping[str, Any]) -> list[str]:
    """Use existing local period axes independently, never join axes."""
    raw_headers = candidate.get("column_headers") or []
    headers = [raw_headers] if isinstance(raw_headers, str) else [str(item) for item in raw_headers]
    surface = str(candidate.get("source_period_surface") or "")
    # This surface may itself be the old presentation join of header axes.
    surfaces = headers + ([] if surface == " / ".join(headers) else [surface])
    if not any(surfaces):
        surfaces = [str(candidate.get("period") or "")]
    return surfaces


def source_period_context_evidence(candidate: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Link a complete column label to its own attached period-declaration line.

    Whitespace is the only permitted label difference. The original header and
    quote/coordinates remain in the witness. No source is selected or rewritten,
    and an attached block's other columns never supply this cell's endpoints.
    """
    raw_headers = candidate.get("column_headers") or []
    headers = [raw_headers] if isinstance(raw_headers, str) else raw_headers
    axes = [(index, str(header)) for index, header in enumerate(headers)
            if is_period_only_surface(str(header))]
    labels = {re.sub(r"\s+", "", header) for _, header in axes}
    evidence = []
    for index, header in axes:
        compact = re.sub(r"\s+", "", header)
        # A bare year cannot match the leading year of an unlabelled ISO date.
        separator = r"\s+" if compact[-1:].isdigit() else r"\s*"
        label_pattern = r"\s*".join(re.escape(char) for char in compact) + separator
        for context in candidate.get("source_contexts") or []:
            if context.get("relation") not in {"preceding_block", "following_block", "caption"}:
                continue
            text = str(context.get("source_text") or "")
            for line in text.splitlines():
                quote = line.strip()
                marker = re.match(label_pattern, quote)
                if marker is None:
                    continue
                tail = quote[marker.end():]
                dates = list(re.finditer(MEASUREMENT_PERIOD_POLICY["source_date_pattern"], tail))
                if not dates and not any(re.search(pattern, tail)
                        for pattern in MEASUREMENT_PERIOD_POLICY["source_subannual_patterns"]):
                    continue
                try:
                    witness = attached_context_quote(candidate, dict(context_id=context.get("context_id"), evidence_text=quote))
                except ValueError:
                    continue
                shape = _source_date_shape(tail)
                if (len(labels) != 1 or text.count(quote) != 1 or not dates or dates[0].start() != 0
                        or not re.fullmatch(MEASUREMENT_PERIOD_POLICY["source_period_declaration_suffix"], tail[dates[-1].end():])):
                    shape = ("unknown",)
                evidence.append(dict(**witness, column_header=header, column_header_index=index,
                    label_quote_span=[0, marker.end()], period_quote_span=[marker.end(), len(quote)],
                    source_table_locator=candidate.get("source_table_locator"),
                    physical_cell_id=candidate.get("physical_cell_id"), date_shape=shape or ("unknown",)))
    return evidence


def _source_date_shape_with_context(candidate: Mapping[str, Any], evidence: Sequence[Mapping[str, Any]]) -> tuple[str, ...] | None:
    shapes = {_source_date_shape(item) for item in _source_period_surfaces(candidate)}
    shapes.update(tuple(row["date_shape"]) for row in evidence)
    shapes.discard(None)
    if not shapes:
        return None
    return next(iter(shapes)) if len(shapes) == 1 else ("unknown",)


def source_date_shape(candidate: Mapping[str, Any]) -> tuple[str, ...] | None:
    return _source_date_shape_with_context(candidate, source_period_context_evidence(candidate))


def _complete_annual_interval(shape: tuple[str, ...]) -> bool:
    if shape[0] != "date_interval":
        return False
    try:
        start, end = date.fromisoformat(shape[1]), date.fromisoformat(shape[2])
        return end + timedelta(days=1) == start.replace(year=start.year + 1)
    except (ValueError, OverflowError):
        return False


def year_coverage_state(
    coverage: str | None, candidate: Mapping[str, Any], expected_years: set[int],
) -> str:
    """Check finer source geometry before the existing annual-year match.

    An annual label retains its existing reading, not a proof of fiscal dates.
    Neither a missing historical declaration nor whole_year licenses a finer
    source period. A complete annual interval is supported only when its dates
    are explicitly linked to this column's own period label in attached source
    text. Neither January nor the fiscal year's endpoints are assumed.
    """
    evidence = source_period_context_evidence(candidate)
    shape = _source_date_shape_with_context(candidate, evidence)
    if shape is not None:
        if (shape != ("unknown",) and expected_years
                and not any(int(shape[1][:4]) <= year <= int(shape[-1][:4]) for year in expected_years)):
            return "conflict"
        if evidence and _complete_annual_interval(shape) and coverage in (None, "whole_year"):
            return "match"
        if shape == ("unknown",) or coverage != "within_year":
            return "unknown"
        return "match" if all(int(endpoint[:4]) in expected_years for endpoint in shape[1:]) else "conflict"
    if coverage != "within_year" and any(
        re.search(pattern, surface)
        for surface in _source_period_surfaces(candidate)
        for pattern in MEASUREMENT_PERIOD_POLICY["source_subannual_patterns"]
    ):
        return "unknown"
    return "match"


def date_period_state(value: Mapping[str, Any], candidate: Mapping[str, Any], *, has_year: bool) -> str:
    shape = source_date_shape(candidate)
    if shape is None:
        return "conflict" if has_year else "unknown"
    if shape == ("unknown",):
        return "unknown"
    wanted = (("date", value["date"]) if value["kind"] == "date"
              else ("date_interval", value["start_date"], value["end_date"]))
    return "match" if wanted == shape else "conflict"
