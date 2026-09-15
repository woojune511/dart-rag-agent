"""Validate and execute grounded semantic calculation programs."""

from __future__ import annotations

import ast
from copy import deepcopy
import hashlib
import json
import math
import re
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from src.agent.financial_candidate_matching import (
    build_candidate_matches,
    declared_local_subjects,
    structured_subject_evidence,
    select_source_defined_physical_row_group,
)
from src.agent.financial_answer_slots import (
    build_calculated_value_slot,
    build_operand_value_slot,
)
from src.agent.financial_formula_eval import safe_eval_formula
from src.agent.financial_formula_constants import FormulaConstantError, resolve_formula_constants
from src.agent.financial_request_units import build_request_units
from src.agent.financial_source_scope import source_section_applicability, source_section_requirement_errors
from src.agent.financial_program_projection import narrative_candidate_ids, narrative_description_only_ids, project_narrative_claims
from src.agent.financial_narrative_claims import validate_narrative_claims
from src.agent.financial_source_interpretation import attached_context_quote, validate_source_interpretation
from src.agent.financial_output_relationships import output_relationships
from src.agent.financial_graph_calculation_rendering import (
    render_grounded_operand_display,
)
from src.agent.financial_row_surfaces import strip_financial_label_annotations
from src.agent.financial_scope_policies import (
    annual_period_evidence, explicit_period_years, relative_period_offsets,
)
from src.agent.financial_text_surface import topic_particle
from src.agent.financial_runtime_normalization import (
    _clean_source_row_ids,
    _normalise_operand_value,
    _normalise_spaces,
    resolve_unit_spec,
    source_display_precision,
)
from src.agent.financial_runtime_contracts import (
    CandidateVisibilityV1,
    CompilationEnvelopeV2,
)
from src.agent.financial_reconciliation_candidates import (
    semantic_candidate_catalog_fingerprint,
)
from src.agent.financial_source_bundles import (
    build_semantic_source_bundles,
    source_bundle_id_by_candidate_id,
)
from src.config.retrieval_policy import (
    CALCULATION_PROMPT_POLICY,
    CALCULATION_RENDER_POLICY,
)
from src.utils.source_segments import source_quote_is_contiguous


_ALLOWED_FUNCTIONS = {"min", "max", "abs", "round", "log", "exp"}
_NARRATIVE_SCOPE_APPLICABILITY_FIELDS = {
    "consolidation_scope",
    "segment",
    "basis",
}
_VARIABLE_SCOPE_APPLICABILITY_FIELDS = {
    "segment",
    "basis",
}
_ROW_LOCAL_NUMERIC_CANDIDATE_KINDS = {
    "structured_row",
    "structured_value",
    "table_row",
    "evidence_row",
}


def _formula_body(expression: str) -> ast.AST:
    return ast.parse(str(expression or ""), mode="eval").body


def _signed_numeric_constant(node: ast.AST) -> Optional[float]:
    if isinstance(node, ast.Constant) and type(node.value) in (int, float):
        try:
            value = float(node.value)
        except OverflowError:
            return None
        return value if math.isfinite(value) else None
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        value = _signed_numeric_constant(node.operand)
        if value is None:
            return None
        return value if isinstance(node.op, ast.UAdd) else -value
    return None


def _formula_constants(node: ast.AST) -> List[float]:
    values: List[float] = []

    def visit(current: ast.AST, *, signed_child: bool = False) -> None:
        signed = _signed_numeric_constant(current)
        if signed is not None:
            if not signed_child:
                values.append(signed)
            return
        for child in ast.iter_child_nodes(current):
            visit(child, signed_child=isinstance(current, ast.UnaryOp))

    visit(node)
    return values


def _formula_names(node: ast.AST) -> set[str]:
    function_nodes = {
        id(current.func)
        for current in ast.walk(node)
        if isinstance(current, ast.Call) and isinstance(current.func, ast.Name)
    }
    return {
        current.id
        for current in ast.walk(node)
        if isinstance(current, ast.Name) and id(current) not in function_nodes
    }


def _formula_ast_allowed(node: ast.AST) -> bool:
    allowed = (
        ast.Expression,
        ast.Constant,
        ast.Name,
        ast.Load,
        ast.UnaryOp,
        ast.UAdd,
        ast.USub,
        ast.BinOp,
        ast.Add,
        ast.Sub,
        ast.Mult,
        ast.Div,
        ast.Pow,
        ast.Call,
    )
    for current in ast.walk(node):
        if not isinstance(current, allowed):
            return False
        if isinstance(current, ast.Constant) and _signed_numeric_constant(current) is None:
            return False
        if isinstance(current, ast.Call):
            if not isinstance(current.func, ast.Name):
                return False
            if current.func.id not in _ALLOWED_FUNCTIONS or current.keywords:
                return False
            if current.func.id in {"min", "max"} and len(current.args) < 2:
                # Variables are scalar floats; the iterable single-argument
                # Python overload cannot execute in this arithmetic language.
                return False
    return True


def _strip_percent_scale(node: ast.AST) -> ast.AST:
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mult):
        if _signed_numeric_constant(node.left) == 100.0:
            return node.right
        if _signed_numeric_constant(node.right) == 100.0:
            return node.left
    return node


def derive_operation_family_from_formula(expression: str) -> str:
    """Derive a legacy compatibility label only after a formula exists."""

    try:
        body = _strip_percent_scale(_formula_body(expression))
    except (SyntaxError, ValueError):
        return "formula"
    if isinstance(body, ast.Name):
        return "lookup"
    if isinstance(body, ast.BinOp) and isinstance(body.op, ast.Sub):
        return "difference"
    if isinstance(body, ast.BinOp) and isinstance(body.op, ast.Div):
        numerator = body.left
        if isinstance(numerator, ast.BinOp) and isinstance(numerator.op, ast.Sub):
            if ast.dump(numerator.right, include_attributes=False) == ast.dump(
                body.right, include_attributes=False
            ):
                return "growth_rate"
        return "ratio"

    def add_only(current: ast.AST) -> bool:
        return isinstance(current, ast.Name) or (
            isinstance(current, ast.BinOp)
            and isinstance(current.op, ast.Add)
            and add_only(current.left)
            and add_only(current.right)
        )

    if isinstance(body, ast.BinOp) and add_only(body):
        return "sum"
    return "formula"


def _candidate_dimension(candidate: Mapping[str, Any]) -> str:
    unit = str(candidate.get("normalized_unit") or "UNKNOWN").strip().upper()
    return unit if unit in {"KRW", "USD", "COUNT", "PERCENT"} else "UNKNOWN"


def _candidate_has_finite_numeric_value(candidate: Mapping[str, Any]) -> bool:
    try:
        return math.isfinite(float(candidate.get("normalized_value")))
    except (TypeError, ValueError):
        return False


def _additive_dimension(left: str, right: str) -> str:
    if left == right:
        return left
    if {left, right} == {"RATIO", "SCALAR"}:
        return "RATIO"
    if "UNKNOWN" in {left, right}:
        raise ValueError("unknown additive unit")
    raise ValueError(f"additive unit mismatch: {left} vs {right}")


def _formula_dimension(node: ast.AST, units: Mapping[str, str]) -> str:
    if isinstance(node, ast.Constant):
        return "SCALAR"
    if isinstance(node, ast.Name):
        if node.id not in units:
            raise ValueError(f"unknown variable unit: {node.id}")
        return str(units[node.id])
    if isinstance(node, ast.UnaryOp):
        return _formula_dimension(node.operand, units)
    if isinstance(node, ast.BinOp):
        left = _formula_dimension(node.left, units)
        right = _formula_dimension(node.right, units)
        if isinstance(node.op, (ast.Add, ast.Sub)):
            return _additive_dimension(left, right)
        if isinstance(node.op, ast.Mult):
            if left == "SCALAR":
                return right
            if right == "SCALAR":
                return left
            raise ValueError(f"unsupported compound multiplication: {left} * {right}")
        if isinstance(node.op, ast.Div):
            if right == "SCALAR":
                return left
            if left == right and left != "UNKNOWN":
                return "RATIO"
            raise ValueError(f"unsupported compound division: {left} / {right}")
        if isinstance(node.op, ast.Pow):
            if right != "SCALAR":
                raise ValueError("formula exponent must be dimensionless")
            exponent = _signed_numeric_constant(node.right)
            if exponent == 1.0:
                return left
            if left in {"SCALAR", "RATIO"}:
                return left
            raise ValueError(f"unsupported dimensional exponent: {left}")
        raise ValueError("unsupported formula operator")
    if isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name) or node.func.id not in _ALLOWED_FUNCTIONS:
            raise ValueError("unsupported formula function")
        dimensions = [_formula_dimension(argument, units) for argument in node.args]
        if node.func.id in {"min", "max"}:
            if not dimensions:
                raise ValueError(f"{node.func.id} requires arguments")
            result = dimensions[0]
            for dimension in dimensions[1:]:
                result = _additive_dimension(result, dimension)
            return result
        if node.func.id == "abs":
            if len(dimensions) != 1:
                raise ValueError("abs requires one argument")
            return dimensions[0]
        if node.func.id == "round":
            if not dimensions or len(dimensions) > 2:
                raise ValueError("round requires one or two arguments")
            if len(dimensions) == 2 and dimensions[1] != "SCALAR":
                raise ValueError("round precision must be dimensionless")
            return dimensions[0]
        if node.func.id in {"log", "exp"}:
            if len(dimensions) != 1 or dimensions[0] not in {"SCALAR", "RATIO"}:
                raise ValueError(f"{node.func.id} requires a dimensionless argument")
            return "SCALAR"
    raise ValueError(f"unsupported formula node: {type(node).__name__}")


def _expression_display_unit(
    expression: Mapping[str, Any], obligation: Mapping[str, Any], dimension: str,
) -> str:
    """Choose presentation only; the formula and operands own the dimension."""
    for value in (expression.get("display_unit"), obligation.get("display_unit")):
        cleaned = _normalise_spaces(str(value or ""))
        if cleaned:
            return cleaned
    spec = resolve_unit_spec("PERCENT" if dimension == "RATIO" else dimension)
    return spec.display_unit if spec is not None else ""


def _display_unit_valid(display_unit: str, dimension: str) -> bool:
    cleaned = _normalise_spaces(str(display_unit or ""))
    if not cleaned:
        return dimension in {"COUNT", "SCALAR", "RATIO", "UNKNOWN"}
    spec = resolve_unit_spec(cleaned)
    normalized = spec.normalized_dimension if spec is not None else "UNKNOWN"
    if spec is None and cleaned.upper() != "UNKNOWN":
        return False
    percent_display_units = {
        str(item)
        for item in (CALCULATION_RENDER_POLICY.get("percent_display_units") or ())
        if str(item)
    }
    if dimension == "RATIO":
        return normalized == "PERCENT" or cleaned in percent_display_units
    if dimension == "PERCENT" and cleaned in percent_display_units:
        return True
    if dimension == "SCALAR":
        return normalized in {"COUNT", "UNKNOWN"}
    if dimension == "UNKNOWN":
        return normalized == "UNKNOWN"
    return spec is not None and normalized == dimension


def _scope_surface_matches(expected: str, actual: str) -> bool:
    wanted = _normalise_spaces(str(expected or "")).lower()
    observed = _normalise_spaces(str(actual or "")).lower()
    if not wanted or not observed:
        return False
    if wanted in observed or observed in wanted:
        return True
    compact_wanted = re.sub(r"\s+", "", wanted)
    compact_observed = re.sub(r"\s+", "", observed)
    return bool(
        min(len(compact_wanted), len(compact_observed)) >= 4
        and (
            compact_wanted in compact_observed
            or compact_observed in compact_wanted
        )
    )


def _scope_matches(expected: str, actual: str, candidate: Mapping[str, Any]) -> bool:
    wanted = _normalise_spaces(str(expected or "")).lower()
    if not wanted or wanted == "unknown":
        return True
    observed = _normalise_spaces(str(actual or "")).lower()
    if observed and observed != "unknown":
        return _scope_surface_matches(wanted, observed)
    surface = _normalise_spaces(
        " ".join(
            str(candidate.get(key) or "")
            for key in ("source_anchor", "source_text", "row_label", "period")
        )
    ).lower()
    return _scope_surface_matches(wanted, surface)


def _direct_subject_resolution(
    candidate: Mapping[str, Any], obligation: Mapping[str, Any]
) -> Dict[str, Any]:
    """Resolve a direct value's subject only from validation-owned evidence."""

    subjects = declared_local_subjects(obligation)
    if subjects and (
        candidate.get("physical_table_id")
        or candidate.get("candidate_kind") in _ROW_LOCAL_NUMERIC_CANDIDATE_KINDS
    ):
        resolution = structured_subject_evidence(candidate, subjects)
        return {
            **resolution,
            "source_row_ids": _clean_source_row_ids([
                candidate.get("candidate_id"), candidate.get("source_row_id"), candidate.get("evidence_id"),
            ]) if resolution["state"] == "match" else [],
        }

    wanted_surface = _normalise_spaces(
        str((obligation.get("scope") or {}).get("segment") or "")
    )
    wanted = wanted_surface.lower()
    if not wanted or wanted == "unknown":
        return {
            "state": "match",
            "subject": "",
            "source": "not_required",
            "source_row_ids": [],
        }

    source_row_ids = _clean_source_row_ids(
        [
            candidate.get("candidate_id"),
            candidate.get("source_row_id"),
            candidate.get("evidence_id"),
            candidate.get("source_candidate_id"),
        ]
    )

    candidate_kind = str(candidate.get("candidate_kind") or "").strip().lower()
    if candidate_kind in _ROW_LOCAL_NUMERIC_CANDIDATE_KINDS:
        raw_row_headers = candidate.get("row_headers") or []
        if isinstance(raw_row_headers, (str, bytes)):
            raw_row_headers = [raw_row_headers]
        elif not isinstance(raw_row_headers, Sequence):
            raw_row_headers = []
        local_surfaces: List[str] = []
        for value in (candidate.get("row_label"), *raw_row_headers, *(candidate.get("column_headers") or [])):
            cleaned = strip_financial_label_annotations(str(value or ""))
            if cleaned and cleaned.lower() != "unknown" and cleaned not in local_surfaces:
                local_surfaces.append(cleaned)

        exact = [surface for surface in local_surfaces if surface.lower() == wanted]
        compatible = [
            surface
            for surface in local_surfaces
            if _scope_surface_matches(wanted, surface)
        ]
        resolved = exact[0] if len(exact) == 1 else (
            compatible[0] if not exact and len(compatible) == 1 else ""
        )
        if resolved:
            return {
                "state": "match",
                "subject": resolved,
                "source": "candidate_row_identity",
                "source_row_ids": source_row_ids,
            }
        if local_surfaces:
            return {
                "state": "conflict",
                "subject": "",
                "source": "candidate_row_identity",
                "source_row_ids": source_row_ids,
            }

    explicit_segment_surface = _normalise_spaces(str(candidate.get("segment") or ""))
    explicit_segment = explicit_segment_surface.lower()
    if explicit_segment and explicit_segment != "unknown":
        matches = _scope_surface_matches(wanted, explicit_segment)
        return {
            "state": "match" if matches else "conflict",
            "subject": explicit_segment_surface if matches else "",
            "source": "candidate_segment_metadata",
            "source_row_ids": source_row_ids,
        }

    state = _scope_match_state("segment", wanted, candidate)
    return {
        "state": state,
        "subject": wanted_surface if state == "match" else "",
        "source": "validated_candidate_context" if state == "match" else "unknown",
        "source_row_ids": source_row_ids if state == "match" else [],
    }


def _candidate_value_period(candidate: Mapping[str, Any]) -> Tuple[bool, Optional[int]]:
    """Use source period evidence; the filing year is only a relative anchor."""

    # Current projections have already applied cell-before-source precedence.
    # Raw source labels remain provenance, not a second competing resolution.
    if candidate.get("period_source") in {
        "explicit_period", "relative_period_label", "fiscal_period", "value_role", "source_period_text", "source_context_binding",
    } and (candidate.get("value_year") is not None or candidate.get("period_source") == "fiscal_period"):
        try:
            return True, int(candidate.get("value_year"))
        except (TypeError, ValueError):
            return True, None
    has_period, value_year = annual_period_evidence(
        candidate.get("period"), candidate.get("source_period_surface"),
        *(candidate.get("column_headers") or []),
        report_year=candidate.get("year"),
    )
    if has_period:
        return True, value_year
    try:
        return True, int(candidate.get("value_year"))
    except (TypeError, ValueError):
        return False, None


def _period_scope_state(
    expected: str, candidate: Mapping[str, Any], *, allow_filing_scope: bool = True,
) -> str:
    wanted = _normalise_spaces(str(expected or "")).lower()
    if not wanted or wanted == "unknown":
        return "match"

    expected_years = explicit_period_years(wanted)
    if not expected_years:
        _, expected_year = annual_period_evidence(wanted, report_year=candidate.get("year"))
        if expected_year is not None:
            expected_years = {expected_year}
    has_period, value_year = _candidate_value_period(candidate)
    if value_year is not None and expected_years:
        return "match" if value_year in expected_years else "conflict"
    if has_period and value_year is None and candidate.get("period_source") == "fiscal_period":
        # Retained row-relative text cannot re-resolve an ambiguous fiscal column.
        return "unknown"
    if not expected_years:
        wanted_offsets = relative_period_offsets(wanted)
        observed_surfaces = (
            candidate.get("period"), candidate.get("source_period_surface"),
            *(candidate.get("column_headers") or []),
        )
        observed_offsets = relative_period_offsets(*observed_surfaces)
        if not explicit_period_years(*observed_surfaces) and len(wanted_offsets) == len(observed_offsets) == 1:
            return "match" if wanted_offsets == observed_offsets else "conflict"
    if has_period and value_year is None:
        return "unknown"
    if not expected_years:
        observed = _normalise_spaces(str(candidate.get("period") or "")).lower()
        if observed and has_period:
            return "match" if _scope_surface_matches(wanted, observed) else "conflict"
    # A narrative can describe the filing as a whole. This document scope must
    # never serve as a numeric value's period, including through a witness.
    if allow_filing_scope and candidate.get("kind") == "narrative" and expected_years:
        try:
            report_year = int(candidate.get("year"))
        except (TypeError, ValueError):
            return "unknown"
        else:
            return "match" if report_year in expected_years else "conflict"
    return "unknown"


def _scope_errors(
    candidate: Mapping[str, Any],
    obligation: Mapping[str, Any],
    *,
    applicable_unknown_fields: Sequence[str] = (),
    conflicts_only: bool = False,
    row_description: bool = False,
) -> List[str]:
    scope = dict(obligation.get("scope") or {})
    applicable = {
        str(field).strip()
        for field in applicable_unknown_fields
        if str(field).strip() in _NARRATIVE_SCOPE_APPLICABILITY_FIELDS
    }
    # Free subject/metric/segment/basis labels are reading targets, not source
    # permissions. Numeric interpretation linkage is checked independently.
    checks = ["company", "consolidation_scope"]
    errors: List[str] = []
    for field in checks:
        state = _scope_match_state(field, scope.get(field), candidate)
        if conflicts_only and state != "conflict":
            continue
        if state == "match" or (state == "unknown" and field in applicable):
            continue
        errors.append(f"scope mismatch: {field}")
    period_state = _narrative_period_scope_state(scope.get("period"), candidate, row_description=row_description)
    if period_state != "match" and (not conflicts_only or period_state == "conflict"):
        errors.append("scope mismatch: period")
    return errors


def _narrative_period_scope_state(
    expected: Any, candidate: Mapping[str, Any], *, row_description: bool = False,
) -> str:
    state = _period_scope_state(expected, candidate)
    if not row_description:
        return state
    # The caller has checked the exact row quote and document identity. Keep
    # measurement conflicts; a document reading never resolves the cell year.
    document_state = _period_scope_state(expected, {"kind": "narrative", "year": candidate.get("year")})
    if "conflict" in (state, document_state):
        return "conflict"
    return document_state


def _row_description_reading(candidate: Mapping[str, Any], quote: Any) -> Dict[str, Any]:
    """Validate a binding-local descriptive axis quote, never a scalar fallback."""
    if not isinstance(quote, str) or not quote.strip():
        raise ValueError("invalid_row_description_quote")
    if not all(candidate.get(field) for field in ("source_document_id", "physical_table_id", "physical_row_id")):
        raise ValueError("unlocated_row_description")
    year = candidate.get("year")
    if isinstance(year, bool) or not str(year or "").isdigit():
        raise ValueError("unlocated_row_description")
    text = str(candidate.get("source_bundle_text") or candidate.get("source_text") or "")
    axes = [candidate.get("row_label"), *(candidate.get("row_headers") or [])]
    start = text.find(quote)
    if start < 0 or not any(isinstance(axis, str) and quote in axis for axis in axes):
        raise ValueError("invalid_row_description_quote")
    scalar_tokens = set(_narrative_number_tokens(str(candidate.get("raw_value") or "")))
    if scalar_tokens.intersection(_narrative_number_tokens(quote)):
        raise ValueError("invalid_row_description_quote")
    return {
        "source_document_id": str(candidate["source_document_id"]),
        "physical_table_id": str(candidate["physical_table_id"]),
        "physical_row_id": str(candidate["physical_row_id"]),
        "document_year": int(year), "quote": quote, "quote_span": [start, start + len(quote)],
        "quote_source_field": "source_bundle_text" if candidate.get("source_bundle_text") else "source_text",
    }


def _evidence_requirement_scope_conflicts(
    obligation: Mapping[str, Any],
    requirement: Mapping[str, Any],
) -> List[str]:
    """Return non-period scope fields where an input contradicts its output."""

    output_scope = dict(obligation.get("scope") or {})
    input_scope = dict(requirement.get("scope") or {})
    conflicts: List[str] = []
    for field in ("company", "consolidation_scope"):
        output_value = _normalise_spaces(str(output_scope.get(field) or "")).lower()
        input_value = _normalise_spaces(str(input_scope.get(field) or "")).lower()
        if output_value in {"", "unknown"} or input_value in {"", "unknown"}:
            continue
        if output_value not in input_value and input_value not in output_value:
            conflicts.append(field)
    return conflicts


def _same_source_context(
    candidate: Mapping[str, Any], witness: Mapping[str, Any]
) -> bool:
    left_document = str(candidate.get("source_document_id") or "")
    right_document = str(witness.get("source_document_id") or "")
    if left_document and right_document and left_document != right_document:
        return False
    left_table = str(candidate.get("physical_table_id") or "")
    right_table = str(witness.get("physical_table_id") or "")
    if left_table and right_table:
        return left_table == right_table
    for field in ("evidence_id", "table_source_id", "context_fingerprint"):
        left = _normalise_spaces(str(candidate.get(field) or ""))
        right = _normalise_spaces(str(witness.get(field) or ""))
        if left and right and left == right:
            return True
    left_anchor = _normalise_spaces(str(candidate.get("source_anchor") or ""))
    right_anchor = _normalise_spaces(str(witness.get("source_anchor") or ""))
    return bool(left_anchor and left_anchor == right_anchor)


def _direct_scope_gap_is_bridgeable(
    candidate: Mapping[str, Any], detail: str, *,
    witnesses: Sequence[Mapping[str, Any]] = (), expected_period: str = "",
) -> bool:
    field = str(detail or "").rsplit(":", 1)[-1].strip()
    if field == "period":
        has_period, _ = _candidate_value_period(candidate)
        return not has_period and any(
            _same_source_context(candidate, witness)
            and _period_scope_state(expected_period, witness, allow_filing_scope=False) == "match"
            for witness in witnesses
        )
    actual = _normalise_spaces(str(candidate.get(field) or "")).lower()
    return actual in {"", "unknown"} and field in {
        "consolidation_scope",
        "segment",
        "basis",
    }


def _scope_match_state(
    field: str,
    expected: Any,
    candidate: Mapping[str, Any],
) -> str:
    wanted = _normalise_spaces(str(expected or "")).lower()
    if not wanted or wanted == "unknown":
        return "match"
    if field == "period":
        return _period_scope_state(wanted, candidate)
    if field == "company":
        actual = _normalise_spaces(str(candidate.get("document_company") or candidate.get("company") or "")).lower()
        return ("match" if wanted == actual else "conflict") if actual and actual != "unknown" else "unknown"

    actual = _normalise_spaces(str(candidate.get(field) or "")).lower()
    if actual and actual != "unknown":
        return "match" if _scope_surface_matches(wanted, actual) else (
            "unknown" if field in {"segment", "basis"} else "conflict")
    return "match" if _scope_matches(wanted, actual, candidate) else "unknown"


def semantic_candidate_applicability(
    candidate: Mapping[str, Any],
    owner: Mapping[str, Any],
) -> Dict[str, Any]:
    """Classify one candidate against an obligation or evidence requirement.

    ``compatible`` means every declared scope dimension is supported,
    ``unknown_only`` means no declared dimension conflicts but at least one is
    unavailable, and ``explicit_conflict`` means a source-owned dimension or a
    physical row subject contradicts the owner.
    """

    candidate_row = dict(candidate or {})
    owner_row = dict(owner or {})
    scope = dict(owner_row.get("scope") or {})
    field_states: Dict[str, str] = {}
    subject_resolution: Dict[str, Any] = {
        "state": "match",
        "subject": "",
        "source": "not_required",
        "source_row_ids": [],
    }
    local_surfaces = _normalized_subject_surfaces(
        candidate_row.get("local_entity_surfaces")
    )
    expected_company = _normalise_spaces(str(scope.get("company") or ""))
    expected_segment = _normalise_spaces(str(scope.get("segment") or ""))
    local_subject_state = "unknown"
    if expected_company and any(
        _identity_surface_matches(expected_company, surface)
        for surface in local_surfaces
    ):
        local_subject_state = "company_match"
    elif expected_segment and any(
        _identity_surface_matches(expected_segment, surface)
        for surface in local_surfaces
    ):
        local_subject_state = "segment_match"

    for field in ("company", "period", "consolidation_scope", "segment", "basis"):
        expected = _normalise_spaces(str(scope.get(field) or ""))
        if not expected or expected.lower() == "unknown":
            continue
        state = _scope_match_state(field, expected, candidate_row)
        explicit_candidate_segment = _normalise_spaces(
            str(candidate_row.get("segment") or "")
        ).lower()
        use_row_subject = (
            str(owner_row.get("kind") or "") == "direct_value"
            or explicit_candidate_segment in {"", "unknown"}
        )
        if (
            field == "segment"
            and str(candidate_row.get("kind") or "") == "numeric"
            and use_row_subject
        ):
            subject_resolution = _direct_subject_resolution(
                candidate_row,
                {"scope": scope},
            )
            subject_state = str(subject_resolution.get("state") or "unknown")
            if subject_state in {"match", "conflict"}:
                state = subject_state
            elif subject_state == "unknown":
                if any(
                    _scope_surface_matches(expected.lower(), surface.lower())
                    for surface in local_surfaces
                ):
                    state = "match"
        field_states[field] = state

    if "conflict" in field_states.values():
        state = "explicit_conflict"
    elif "unknown" in field_states.values():
        state = "unknown_only"
    else:
        state = "compatible"
    return {
        "state": state,
        "field_states": field_states,
        "subject_state": str(subject_resolution.get("state") or "unknown"),
        "subject_source": str(subject_resolution.get("source") or ""),
        "local_subject_state": local_subject_state,
    }


def source_candidate_applicability(
    candidate: Mapping[str, Any], owner: Mapping[str, Any],
    parent_owner: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """Source permissions, independent of topic rank or a generated subject label.

    Unknown fields require grounding later; this projection never certifies
    interpretation. Input periods override output periods, while source-section
    restrictions always intersect their parent's restrictions.
    """
    scope = {**dict((parent_owner or {}).get("scope") or {}), **dict(owner.get("scope") or {})}
    hard_owner = {"scope": {key: scope[key] for key in
                  ("company", "period", "consolidation_scope") if key in scope}}
    result = semantic_candidate_applicability(candidate, hard_owner)
    section = source_section_applicability(candidate, owner, parent_owner)["state"]
    if section not in {"unrestricted", "match"}:
        result = {**result, "state": "explicit_conflict"}
    return {**result, "source_section_state": section}


def _normalized_subject_surfaces(raw_values: Any) -> List[str]:
    values = (
        [raw_values]
        if isinstance(raw_values, (str, bytes))
        else list(raw_values or [])
        if isinstance(raw_values, Sequence)
        else []
    )
    normalized: List[str] = []
    for raw_value in values:
        value = strip_financial_label_annotations(str(raw_value or ""))
        if value and value.lower() != "unknown" and value not in normalized:
            normalized.append(value)
    return normalized


def _identity_surface_matches(expected: str, observed: str) -> bool:
    def compact(value: str) -> str:
        return "".join(
            character.casefold()
            for character in _normalise_spaces(str(value or ""))
            if character.isalnum()
        )

    left = compact(expected)
    right = compact(observed)
    if not left or not right:
        return False
    if left == right or (
        min(len(left), len(right)) >= 4
        and (left in right or right in left)
    ):
        return True
    shorter, longer = (left, right) if len(left) <= len(right) else (right, left)
    if (
        len(shorter) < 3
        or len(shorter) / len(longer) < 0.5
        or shorter[:2] != longer[:2]
        or shorter[-1] != longer[-1]
    ):
        return False
    iterator = iter(longer)
    return all(
        any(character == current for current in iterator)
        for character in shorter
    )


def _collective_narrative_scope_errors(
    candidates: Sequence[Mapping[str, Any]],
    obligation: Mapping[str, Any],
    *,
    applicable_unknown_fields: Sequence[str] = (),
    description_candidate_ids: Sequence[str] = (),
) -> List[str]:
    scope = dict(obligation.get("scope") or {})
    applicable = {
        str(field).strip()
        for field in applicable_unknown_fields
        if str(field).strip() in _NARRATIVE_SCOPE_APPLICABILITY_FIELDS
    }
    errors: List[str] = []
    for field in ("company", "consolidation_scope", "segment", "basis", "period"):
        expected = scope.get(field)
        wanted = _normalise_spaces(str(expected or "")).lower()
        if not wanted or wanted == "unknown":
            continue
        states = [
            _narrative_period_scope_state(expected, candidate,
                row_description=str(candidate.get("candidate_id") or "") in description_candidate_ids)
            if field == "period" else _scope_match_state(field, expected, candidate)
            for candidate in candidates
        ]
        if "conflict" in states or (
            "match" not in states and field not in applicable
        ):
            errors.append(f"scope mismatch: {field}")
    return errors


def _expression_context_conflicts(
    candidates: Sequence[Mapping[str, Any]],
) -> List[str]:
    """Compare known filing/consolidation facts, not free interpretation labels.

    Owner binding, source assertions and explicit physical/coupling contracts
    are validated separately; a formula need not live inside one source or use
    identical segment/basis wording. Explicit shared-basis declarations are
    checked only by the request-grounded output-relationship contract.
    """

    conflicts: List[str] = []
    for field in (
        "company",
        "consolidation_scope",
    ):
        values = set()
        for candidate in candidates:
            value = (candidate.get("document_company") or candidate.get("company")
                     if field == "company" else candidate.get(field))
            normalized = _normalise_spaces(str(value or "")).lower()
            if normalized not in {"", "unknown"}:
                values.add(normalized)
        if len(values) > 1:
            conflicts.append(field)
    return conflicts


def _narrative_number_tokens(text: str) -> List[str]:
    return [token.replace(",", "") for token in re.findall(r"[-+]?\d[\d,]*(?:\.\d+)?", text)]


def _ungrounded_narrative_numbers(
    text: str, candidates: Sequence[Mapping[str, Any]]
) -> List[str]:
    tokens = re.findall(r"[-+]?\d[\d,]*(?:\.\d+)?", str(text or ""))
    if not tokens:
        return []
    surface = " ".join(
        str(value or "")
        for candidate in candidates
        for value in (
            candidate.get("source_text"),
            candidate.get("raw_value"),
            candidate.get("period"),
            candidate.get("year"),
        )
    )
    source_tokens = {
        token.replace(",", "")
        for token in re.findall(r"[-+]?\d[\d,]*(?:\.\d+)?", surface)
    }
    return list(
        dict.fromkeys(
            token
            for token in tokens
            if token.replace(",", "") not in source_tokens
        )
    )


def _missing_narrative_candidate_values(
    text: str,
    candidates: Sequence[Mapping[str, Any]],
) -> List[str]:
    """Return selected structured candidates whose source value is not stated."""

    text_tokens = {
        token.replace(",", "").lstrip("+-")
        for token in re.findall(r"[-+]?\d[\d,]*(?:\.\d+)?", str(text or ""))
    }
    missing: List[str] = []
    for candidate in candidates:
        candidate_id = str(candidate.get("candidate_id") or "").strip()
        raw_tokens = {
            token.replace(",", "").lstrip("+-")
            for token in re.findall(
                r"[-+]?\d[\d,]*(?:\.\d+)?",
                str(candidate.get("raw_value") or ""),
            )
        }
        if candidate_id and raw_tokens and raw_tokens.isdisjoint(text_tokens):
            missing.append(candidate_id)
    return missing


def _resolve_source_context_bindings(
    candidate: Mapping[str, Any], bindings: Sequence[Mapping[str, Any]],
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Ground scope interpretation without changing the immutable source candidate."""
    resolved = dict(candidate)
    scope: Dict[str, Any] = {}
    evidence = []
    for binding in bindings:
        source = attached_context_quote(candidate, binding)
        quote = source["evidence_text"]
        field = binding.get("field")
        value = binding.get("value")
        if (field not in {"period", "consolidation_scope", "segment", "basis"}
                or not isinstance(value, str) or not value.strip() or value.lower() == "unknown"):
            raise ValueError("invalid_context_scope_binding")
        if field in scope and scope[field] != value:
            raise ValueError("conflicting_context_scope_bindings")
        if _scope_match_state(field, value, candidate) == "conflict":
            raise ValueError("context_conflicts_with_candidate")
        if field == "consolidation_scope" and value not in {"consolidated", "separate"}:
            raise ValueError("invalid_context_scope_binding")
        if field == "period":
            _, value_year = annual_period_evidence(value, report_year=candidate.get("year"))
            _, quoted_year = annual_period_evidence(quote, report_year=candidate.get("year"))
            if value_year is None or (quoted_year is not None and value_year != quoted_year):
                raise ValueError("context_period_mismatch")
            scope.update(value_year=value_year, period_source="source_context_binding",
                         period_label_scope="source_context")
        scope[field] = value
        evidence.append({**dict(binding), **source})
    if not evidence:
        return resolved, {}
    resolution = {"scope": scope, "evidence": evidence}
    resolution["fingerprint"] = hashlib.sha256(json.dumps(
        resolution, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
    resolved.update(scope)
    resolved["context_resolution"] = resolution
    return resolved, resolution


def _resolve_comparison_request(expression, obligation, query):
    """Check request/variable linkage only; never infer direction or edit a formula."""
    unit_id = expression.get("comparison_request_unit_id")
    if unit_id is None:
        return None
    if not isinstance(unit_id, str) or not unit_id.strip():
        raise ValueError("invalid_comparison_request")
    units = {unit.request_unit_id: unit for unit in build_request_units(query)}
    if unit_id not in (obligation.get("request_unit_ids") or []) or unit_id not in units:
        raise ValueError("comparison_request_not_owned")
    unit = units[unit_id]
    bindings = {str(row.get("variable") or "").strip(): row for row in expression["variable_bindings"]}
    if not {"reference", "target"} <= bindings.keys():
        raise ValueError("comparison_binding_mismatch")
    return {"request_unit_id": unit_id, "requested_text": unit.text, "request_span": [unit.start, unit.end],
        **{variable: {"variable": variable, "source_id": str(bindings[variable].get("source_id") or "").strip(),
            "source_requirement_id": bindings[variable].get("source_requirement_id", "")}
            for variable in ("reference", "target")},
        "validation_scope": "request_binding_not_semantic_equivalence"}


def validate_semantic_calculation_program(
    *,
    program: Mapping[str, Any],
    obligations: Sequence[Mapping[str, Any]],
    candidate_catalog: Sequence[Mapping[str, Any]],
    query: str,
    candidate_visibility: Optional[CandidateVisibilityV1] = None,
    require_narrative_claims: bool = False,
    selectable_candidate_ids: Optional[Sequence[str]] = None,
    selectable_candidate_ids_by_owner: Optional[
        Mapping[str, Sequence[str]]
    ] = None,
) -> Dict[str, Any]:
    """Validate model-selected IDs and expressions without executing them."""

    obligation_rows = [dict(item) for item in obligations if isinstance(item, Mapping)]
    candidate_rows = [dict(item) for item in candidate_catalog if isinstance(item, Mapping)]
    obligation_by_id = {
        str(item.get("obligation_id") or "").strip(): item
        for item in obligation_rows
        if str(item.get("obligation_id") or "").strip()
    }
    candidate_by_id = {
        str(item.get("candidate_id") or "").strip(): item
        for item in candidate_rows
        if str(item.get("candidate_id") or "").strip()
    }
    if candidate_visibility is not None:
        selectable_candidate_ids = candidate_visibility.visible_candidate_ids
        selectable_candidate_ids_by_owner = (
            candidate_visibility.candidate_ids_by_owner()
        )
    selectable_ids = (
        None
        if selectable_candidate_ids is None
        else {
            str(item or "").strip()
            for item in selectable_candidate_ids
            if str(item or "").strip()
        }
    )
    selectable_ids_by_owner = (
        None
        if selectable_candidate_ids_by_owner is None
        else {
            str(owner_id).strip(): {
                str(item or "").strip()
                for item in candidate_ids
                if str(item or "").strip()
            }
            for owner_id, candidate_ids in selectable_candidate_ids_by_owner.items()
            if str(owner_id or "").strip()
        }
    )
    errors: List[Dict[str, str]] = []
    declared_source_owners: Dict[str, set[str]] = {}

    def remember_source_owner(candidate_id: str, obligation_id: str) -> None:
        # Error attribution only: an invalid binding never grants selection
        # authority, but its assertion error still belongs to that output.
        if candidate_id and obligation_id in obligation_by_id:
            declared_source_owners.setdefault(candidate_id, set()).add(obligation_id)

    def error(
        code: str, obligation_id: str = "", detail: str = "", *,
        owner_id: str = "", candidate_id: str = "", location: str = "program",
        repair_action: str = "repair_program",
    ) -> None:
        errors.append(
            {
                "code": code, "obligation_id": obligation_id, "detail": str(detail or ""),
                "owner_id": owner_id or obligation_id, "candidate_id": candidate_id,
                "location": location, "repair_action": repair_action,
            }
        )

    def candidate_section_is_authorized(candidate_id: str, owner_id: str, *, dependency: bool = False) -> bool:
        obligation_id = requirement_owner_by_id.get(owner_id, owner_id)
        owner = requirement_by_id.get(owner_id, obligation_by_id.get(owner_id, {}))
        parent = obligation_by_id.get(obligation_id) if owner_id in requirement_by_id else None
        section = source_section_applicability(candidate_by_id.get(candidate_id, {}), owner, parent)
        if section["state"] not in {"unrestricted", "match"}:
            error(
                "candidate_source_section_mismatch" if section["state"] == "conflict" else "candidate_source_section_unresolved",
                obligation_id, owner_id=owner_id, candidate_id=candidate_id,
                location="expression_input.dependency_source" if dependency else "candidate.source_section_path",
                repair_action="replace_candidate" if section["state"] == "conflict" and not dependency else "repair_program",
            )
            return False
        return True

    def candidate_is_exposed(candidate_id: str, owner_id: str) -> bool:
        if not candidate_section_is_authorized(candidate_id, owner_id):
            return False
        if selectable_ids_by_owner is not None:
            return candidate_id in selectable_ids_by_owner.get(owner_id, set())
        return selectable_ids is None or candidate_id in selectable_ids

    def contextual_candidate(candidate, binding, obligation_id, owner_id, location,
                             *, bindings_key="context_bindings", resolution_key="context_resolution"):
        binding.pop(resolution_key, None)
        interpretation_key = ("source_display_interpretation" if bindings_key.startswith("source_display")
                              else "source_interpretation")
        proof_key = interpretation_key + "_resolution"
        binding.pop(proof_key, None)
        raw_bindings = binding.get(bindings_key) or []
        try:
            if not isinstance(raw_bindings, list) or any(not isinstance(b, Mapping) for b in raw_bindings):
                raise ValueError("invalid_context_scope_binding")
            resolved, resolution = _resolve_source_context_bindings(candidate, raw_bindings)
            parent = obligation_by_id.get(obligation_id, {})
            owner = requirement_by_id.get(owner_id, parent)
            scope = {**dict(parent.get("scope") or {}), **dict(owner.get("scope") or {})}
            interpretation = binding.get(interpretation_key)
            needs_interpretation = (candidate.get("kind") == "numeric" and (
                declared_local_subjects(owner, parent)
                or any(scope.get(field) not in (None, "", "unknown") for field in ("segment", "basis"))))
            if needs_interpretation or interpretation is not None:
                location = location.rsplit('.', 1)[0] + '.source_interpretation'
                proof = validate_source_interpretation(
                    candidate, interpretation, owner=owner, parent_owner=parent, query=query)
                # Free interpretations remain on the proof; they do not overwrite
                # source fields or explicit attached-context resolutions above.
                proof["requested_scope"] = {field: scope[field] for field in ("segment", "basis") if scope.get(field)}
                proof.pop("fingerprint", None)
                proof["fingerprint"] = hashlib.sha256(json.dumps(
                    proof, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
                binding[proof_key] = proof
                resolved["source_interpretation_resolution"] = proof
        except ValueError as exc:
            error(str(exc), obligation_id, owner_id=owner_id,
                  candidate_id=str(candidate.get("candidate_id") or ""), location=location)
            return dict(candidate), False
        if resolution:
            binding[resolution_key] = resolution
        return resolved, True

    if len(obligation_by_id) != len(obligation_rows):
        error("duplicate_or_missing_obligation_id")
    if not obligation_rows:
        error("missing_answer_obligations")
    if len(candidate_by_id) != len(candidate_rows):
        error("duplicate_or_missing_candidate_id")

    requirement_by_id: Dict[str, Dict[str, Any]] = {}
    requirement_owner_by_id: Dict[str, str] = {}
    requirement_count = 0
    section_errors = source_section_requirement_errors(obligation_rows, query)
    errors.extend(section_errors)
    invalid_evidence_obligation_ids = {item["obligation_id"] for item in section_errors}
    for obligation_id, obligation in obligation_by_id.items():
        raw_requirements = list(obligation.get("evidence_requirements") or [])
        requirements = [
            dict(item)
            for item in raw_requirements
            if isinstance(item, Mapping)
        ]
        if len(requirements) != len(raw_requirements):
            error("malformed_evidence_requirement", obligation_id)
        evidence_mode = obligation.get("evidence_mode", "declared_inputs")
        if evidence_mode not in ("declared_inputs", "source_defined_group"):
            error("invalid_evidence_mode", obligation_id)
            invalid_evidence_obligation_ids.add(obligation_id)
        elif evidence_mode == "source_defined_group":
            group = requirements[0] if len(requirements) == 1 else {}
            if (
                obligation.get("kind") != "narrative"
                or len(raw_requirements) != 1
                or group.get("required") is not True
                or any(
                    group.get(field, default) != obligation.get(field, default)
                    for field, default in (
                        ("label", ""),
                        ("scope", {}),
                        ("source_sections", []),
                        ("source_section_bindings", []),
                        ("retrieval_hints", []),
                        ("concept_hints", []),
                        ("semantic_target", {}),
                    )
                )
            ):
                error("invalid_source_defined_group", obligation_id)
                invalid_evidence_obligation_ids.add(obligation_id)
        requirement_count += len(requirements)
        if requirements and str(obligation.get("kind") or "") not in {
            "derived_value",
            "narrative",
        }:
            error("evidence_requirement_on_unsupported_obligation", obligation_id)
        for requirement in requirements:
            requirement_id = str(requirement.get("requirement_id") or "").strip()
            if not requirement_id or requirement_id in requirement_by_id:
                error("duplicate_or_missing_evidence_requirement_id", obligation_id)
                continue
            requirement_by_id[requirement_id] = requirement
            requirement_owner_by_id[requirement_id] = obligation_id
            for field in _evidence_requirement_scope_conflicts(obligation, requirement):
                error(
                    "evidence_requirement_scope_conflict",
                    obligation_id,
                    f"{requirement_id}: {field}",
                )
    if len(requirement_by_id) != requirement_count:
        error("invalid_evidence_requirement_catalog")

    match_cache: Dict[str, Dict[str, Any]] = {}

    def candidate_has_source_conflict(
        candidate_id: str,
        owner_id: str,
    ) -> bool:
        owner = obligation_by_id.get(owner_id)
        parent_owner: Optional[Mapping[str, Any]] = None
        if owner is None:
            requirement = requirement_by_id.get(owner_id)
            parent_id = requirement_owner_by_id.get(owner_id, "")
            parent_owner = obligation_by_id.get(parent_id)
            if requirement is None:
                return False
            owner = {
                **dict(requirement),
                "scope": {
                    **dict((parent_owner or {}).get("scope") or {}),
                    **dict(requirement.get("scope") or {}),
                },
            }
        declared_target = dict(owner.get("semantic_target") or {})
        if not any(
            declared_target.get(field)
            for field in ("local_subjects", "concept_keys", "metric_surfaces")
        ):
            return False
        if owner_id not in match_cache:
            base_applicability = {
                row_id: source_candidate_applicability(candidate, owner, parent_owner)
                for row_id, candidate in candidate_by_id.items()
            }
            match_cache[owner_id] = build_candidate_matches(
                candidate_rows,
                owner=owner,
                parent_owner=parent_owner,
                base_applicability_by_id=base_applicability,
            )
        match = match_cache[owner_id].get(candidate_id)
        return bool(match and match.state == "explicit_conflict")

    declared_missing = {
        str(item).strip()
        for item in (program.get("missing_obligation_ids") or [])
        if str(item).strip()
    }
    declared_ambiguous = {
        str(item).strip()
        for item in (program.get("ambiguous_obligation_ids") or [])
        if str(item).strip()
    }
    for obligation_id in sorted(declared_missing | declared_ambiguous):
        if obligation_id not in obligation_by_id:
            error("unknown_program_obligation_id", obligation_id)
    blocked = declared_missing | declared_ambiguous | invalid_evidence_obligation_ids
    produced: set[str] = set()
    valid_direct: List[Dict[str, Any]] = []
    valid_expressions: List[Dict[str, Any]] = []
    valid_narrative: List[Dict[str, Any]] = []
    sources_by_output: Dict[str, List[str]] = {}
    compatibility_sources_by_output: Dict[str, List[str]] = {}
    output_units: Dict[str, str] = {}
    evidence_bundle_validation: List[Dict[str, Any]] = []
    resolved_sources_by_output: Dict[str, List[Mapping[str, Any]]] = {}

    def already_produced(obligation_id: str) -> bool:
        if obligation_id in produced:
            error("duplicate_obligation_output", obligation_id)
            return True
        return False

    for raw in program.get("direct_bindings") or []:
        binding = dict(raw or {})
        obligation_id = str(binding.get("obligation_id") or "").strip()
        candidate_id = str(binding.get("candidate_id") or "").strip()
        remember_source_owner(candidate_id, obligation_id)
        compatibility_ids = list(
            dict.fromkeys(
                str(item).strip()
                for item in (binding.get("compatibility_candidate_ids") or [])
                if str(item).strip()
            )
        )
        obligation = obligation_by_id.get(obligation_id)
        candidate = candidate_by_id.get(candidate_id)
        invalid = False
        if candidate:
            candidate, context_valid = contextual_candidate(
                candidate, binding, obligation_id, obligation_id, "direct_binding.context_bindings")
            invalid = not context_valid
        if not obligation:
            error("unknown_direct_obligation", obligation_id)
            invalid = True
        if obligation_id in blocked:
            error("blocked_obligation_has_output", obligation_id)
            invalid = True
        if (
            not candidate
            or str((candidate or {}).get("kind") or "") != "numeric"
            or not _candidate_has_finite_numeric_value(candidate or {})
        ):
            error("unknown_or_nonnumeric_candidate", obligation_id, candidate_id)
            invalid = True
        if not candidate_is_exposed(candidate_id, obligation_id):
            error("candidate_not_exposed_to_compiler", obligation_id, candidate_id,
                  candidate_id=candidate_id, location="direct_binding")
            invalid = True
        if candidate and obligation and candidate_has_source_conflict(
            candidate_id,
            obligation_id,
        ):
            error("candidate_source_condition_conflict", obligation_id, candidate_id,
                  candidate_id=candidate_id, location="direct_binding",
                  repair_action="replace_candidate")
            invalid = True
        if obligation and str(obligation.get("kind") or "") != "direct_value":
            error("non_direct_obligation_has_direct_binding", obligation_id)
            invalid = True
        compatibility_candidates = [
            candidate_by_id[item]
            for item in compatibility_ids
            if item in candidate_by_id
        ]
        invalid_compatibility_id = next(
            (
                item
                for item in compatibility_ids
                if item not in candidate_by_id
                or str(candidate_by_id[item].get("kind") or "") != "narrative"
                or not _normalise_spaces(
                    str(candidate_by_id[item].get("source_text") or "")
                )
            ),
            "",
        )
        compatibility_ready = bool(compatibility_ids) and not invalid_compatibility_id
        subject_resolution: Dict[str, Any] = {
            "state": "match",
            "subject": "",
            "source": "not_required",
            "source_row_ids": [],
        }
        if invalid_compatibility_id:
            error(
                "invalid_compatibility_candidate",
                obligation_id,
                invalid_compatibility_id,
            )
            invalid = True
        hidden_compatibility_id = next(
            (
                item
                for item in compatibility_ids
                if not candidate_is_exposed(item, obligation_id)
            ),
            "",
        )
        if hidden_compatibility_id:
            error(
                "candidate_not_exposed_to_compiler",
                obligation_id,
                hidden_compatibility_id,
            )
            invalid = True
        if compatibility_ready and candidate and not any(
            _same_source_context(candidate, witness)
            for witness in compatibility_candidates
        ):
            error("direct_compatibility_context_mismatch", obligation_id)
            invalid = True
            compatibility_ready = False
        if compatibility_ready and obligation:
            for witness in compatibility_candidates:
                hard_errors = [
                    detail
                    for detail in _scope_errors(witness, obligation)
                    if detail.endswith(("company", "period"))
                ]
                if hard_errors:
                    for detail in hard_errors:
                        error("compatibility_scope_mismatch", obligation_id, detail,
                              candidate_id=str(witness.get("candidate_id") or ""),
                              location="compatibility_binding",
                              repair_action="replace_candidate" if detail in _scope_errors(witness, obligation, conflicts_only=True) else "repair_program")
                    invalid = True
                    compatibility_ready = False
                    break
        if obligation and candidate:
            proof = binding.get("source_interpretation_resolution")
            if proof:
                subject_resolution = {
                    "state": "source_linked", "subject": proof["subject"],
                    "source": "compiler_source_interpretation",
                    "source_row_ids": [candidate_id],
                }
            # No text-equality or unrelated compatibility witness can establish
            # semantic equivalence. contextual_candidate owns source linkage.
            scope_details = _scope_errors(candidate, obligation)
            if compatibility_ready:
                scope_details = [
                    detail
                    for detail in scope_details
                    if not _direct_scope_gap_is_bridgeable(
                        candidate, detail, witnesses=compatibility_candidates,
                        expected_period=str((obligation.get("scope") or {}).get("period") or ""),
                    )
                ]
            for detail in scope_details:
                error("candidate_scope_mismatch", obligation_id, detail,
                      candidate_id=candidate_id, location="direct_binding",
                      repair_action="replace_candidate" if detail in _scope_errors(candidate_by_id[candidate_id], obligation, conflicts_only=True) else "repair_program")
                invalid = True
        if (
            obligation
            and candidate
            and str(obligation.get("kind") or "") == "direct_value"
            and str(candidate.get("kind") or "") == "numeric"
            and _candidate_has_finite_numeric_value(candidate)
        ):
            display_unit = _normalise_spaces(
                str(obligation.get("display_unit") or "")
            )
            if display_unit and not _display_unit_valid(
                display_unit,
                _candidate_dimension(candidate),
            ):
                error(
                    "direct_result_unit_mismatch" if resolve_unit_spec(display_unit) else "invalid_obligation_unit",
                    obligation_id,
                    display_unit,
                    candidate_id=candidate_id,
                    location="direct_binding" if resolve_unit_spec(display_unit) else "obligation.display_unit",
                    repair_action="replace_candidate" if resolve_unit_spec(display_unit) else "repair_requirements",
                )
                invalid = True
            preview_operand = project_semantic_program_operand(
                candidate,
                obligation_id=obligation_id,
                obligation=obligation,
                validated_binding={
                    **binding,
                    "resolved_subject": str(subject_resolution.get("subject") or ""),
                    "subject_source": str(subject_resolution.get("source") or ""),
                    "subject_source_row_ids": list(
                        subject_resolution.get("source_row_ids") or []
                    ),
                },
            )
            if not render_grounded_operand_display(preview_operand):
                error("empty_direct_rendering", obligation_id, candidate_id)
                invalid = True
        if already_produced(obligation_id):
            invalid = True
        if invalid:
            continue
        produced.add(obligation_id)
        valid_direct.append(
            {
                **binding,
                "resolved_subject": str(subject_resolution.get("subject") or ""),
                "subject_source": str(subject_resolution.get("source") or ""),
                "subject_source_row_ids": list(
                    subject_resolution.get("source_row_ids") or []
                ),
            }
        )
        sources_by_output[obligation_id] = [candidate_id, *compatibility_ids]
        compatibility_sources_by_output[obligation_id] = compatibility_ids
        output_units[obligation_id] = _candidate_dimension(candidate)
        resolved_sources_by_output[obligation_id] = [candidate]

    pending = [dict(item or {}) for item in (program.get("expressions") or [])]
    seen_expression_ids: set[str] = set()
    for expression in pending:
        obligation_id = str(expression.get("obligation_id") or "").strip()
        if obligation_id in seen_expression_ids:
            error("duplicate_expression_output", obligation_id)
        seen_expression_ids.add(obligation_id)

    unresolved = list(pending)
    while unresolved:
        progressed = False
        deferred: List[Dict[str, Any]] = []
        for expression in unresolved:
            obligation_id = str(expression.get("obligation_id") or "").strip()
            if (
                "source_display_candidate_id" not in expression
                or not isinstance(expression.get("source_display_reason"), str)
                or not str(expression.get("source_display_reason") or "").strip()
                or (expression.get("source_display_candidate_id") is not None
                    and (not isinstance(expression["source_display_candidate_id"], str)
                         or not expression["source_display_candidate_id"].strip()))
            ):
                error("invalid_source_display_decision", obligation_id,
                      location="expression.source_display", repair_action="repair_program")
                continue
            obligation = obligation_by_id.get(obligation_id)
            bindings = [dict(item or {}) for item in expression.get("variable_bindings") or []]
            expression["variable_bindings"] = bindings
            source_ids = [str(item.get("source_id") or "").strip() for item in bindings]
            for source_id in [*source_ids, str(expression.get("source_display_candidate_id") or "").strip()]:
                remember_source_owner(source_id, obligation_id)
            unknown = next(
                (
                    source_id
                    for source_id in source_ids
                    if source_id not in candidate_by_id and source_id not in obligation_by_id
                ),
                "",
            )
            if unknown:
                error("unknown_expression_source", obligation_id, unknown)
                continue
            hidden_source = next(
                (
                    source_id
                    for source_id in source_ids
                    if source_id in candidate_by_id
                    and not candidate_is_exposed(source_id, obligation_id)
                ),
                "",
            )
            if hidden_source:
                error(
                    "candidate_not_exposed_to_compiler",
                    obligation_id,
                    hidden_source,
                )
                continue
            dependencies = [item for item in source_ids if item in obligation_by_id]
            if any(item not in output_units for item in dependencies):
                deferred.append(expression)
                continue

            invalid = False
            if not obligation:
                error("unknown_expression_obligation", obligation_id)
                invalid = True
            elif str(obligation.get("kind") or "") != "derived_value":
                error("non_derived_obligation_has_expression", obligation_id)
                invalid = True
            if obligation_id in blocked:
                error("blocked_obligation_has_output", obligation_id)
                invalid = True
            variables = [str(item.get("variable") or "").strip() for item in bindings]
            if not bindings or any(not item or not item.isidentifier() for item in variables):
                error("invalid_variable_binding", obligation_id)
                invalid = True
            if len(set(variables)) != len(variables):
                error("duplicate_variable_binding", obligation_id)
                invalid = True
            expression.pop("comparison_resolution", None)
            if not invalid:
                try:
                    comparison = _resolve_comparison_request(expression, obligation, query)
                    if comparison is not None:
                        expression["comparison_resolution"] = comparison
                except ValueError as exc:
                    error(str(exc), obligation_id, location="expression.comparison_request")
                    invalid = True
            formula = str(expression.get("formula") or "").strip()
            try:
                body = _formula_body(formula)
            except (SyntaxError, ValueError) as exc:
                error("invalid_formula_syntax", obligation_id, str(exc))
                invalid = True
                body = ast.Constant(value=0)
            if not invalid and not _formula_ast_allowed(body):
                error("unsupported_formula_ast", obligation_id)
                invalid = True
            if not invalid and _formula_names(body) != set(variables):
                error("formula_binding_mismatch", obligation_id)
                invalid = True
            expression.pop("constant_resolutions", None)
            if not invalid:
                try:
                    constants = resolve_formula_constants(
                        expression.get("constants", []), _formula_constants(body),
                        obligation=obligation, query=query, binding_count=len(bindings))
                    if constants:
                        expression["constant_resolutions"] = constants
                except FormulaConstantError as exc:
                    error(str(exc), obligation_id, exc.detail, location="expression.constants")
                    invalid = True

            variable_units: Dict[str, str] = {}
            source_candidates: List[str] = []
            resolved_expression_sources: List[Mapping[str, Any]] = []
            bound_requirement_ids: set[str] = set()
            if not invalid:
                for binding in bindings:
                    variable = str(binding.get("variable") or "").strip()
                    source_id = str(binding.get("source_id") or "").strip()
                    source_requirement_id = str(
                        binding.get("source_requirement_id") or ""
                    ).strip()
                    raw_scope_applicability_fields = [
                        str(item).strip()
                        for item in (binding.get("scope_applicability_fields") or [])
                        if str(item).strip()
                    ]
                    invalid_scope_applicability_fields = [
                        field
                        for field in raw_scope_applicability_fields
                        if field not in _VARIABLE_SCOPE_APPLICABILITY_FIELDS
                    ]
                    scope_applicability_fields = list(
                        dict.fromkeys(
                            field
                            for field in raw_scope_applicability_fields
                            if field in _VARIABLE_SCOPE_APPLICABILITY_FIELDS
                        )
                    )
                    for field in invalid_scope_applicability_fields:
                        error(
                            "invalid_variable_scope_applicability_field",
                            obligation_id,
                            field,
                        )
                        invalid = True
                    if source_id in candidate_by_id:
                        candidate = candidate_by_id[source_id]
                        candidate, context_valid = contextual_candidate(
                            candidate, binding, obligation_id, source_requirement_id,
                            "expression_input.context_bindings")
                        if not context_valid:
                            invalid = True
                        resolved_expression_sources.append(candidate)
                        if (
                            str(candidate.get("kind") or "") != "numeric"
                            or not _candidate_has_finite_numeric_value(candidate)
                        ):
                            error("nonnumeric_expression_source", obligation_id, source_id)
                            invalid = True
                            break
                        requirement = requirement_by_id.get(source_requirement_id)
                        if not source_requirement_id:
                            error(
                                "missing_source_requirement_id",
                                obligation_id,
                                source_id,
                            )
                            invalid = True
                        elif not requirement:
                            error(
                                "unknown_expression_requirement",
                                obligation_id,
                                source_requirement_id,
                            )
                            invalid = True
                        elif requirement_owner_by_id.get(source_requirement_id) != obligation_id:
                            error(
                                "expression_requirement_owner_mismatch",
                                obligation_id,
                                source_requirement_id,
                            )
                            invalid = True
                        else:
                            if not candidate_is_exposed(
                                source_id,
                                source_requirement_id,
                            ):
                                error(
                                    "candidate_not_exposed_to_compiler",
                                    obligation_id,
                                    source_id,
                                )
                                invalid = True
                            if candidate_has_source_conflict(
                                source_id,
                                source_requirement_id,
                            ):
                                error(
                                    "candidate_source_condition_conflict",
                                    obligation_id,
                                    f"{source_requirement_id}: {source_id}",
                                    owner_id=source_requirement_id, candidate_id=source_id,
                                    location="expression_input", repair_action="replace_candidate",
                                )
                                invalid = True
                            bound_requirement_ids.add(source_requirement_id)
                            for detail in _scope_errors(
                                candidate,
                                {"scope": dict(requirement.get("scope") or {})},
                                applicable_unknown_fields=scope_applicability_fields,
                            ):
                                error(
                                    "candidate_requirement_scope_mismatch",
                                    obligation_id,
                                    f"{source_requirement_id}: {detail}",
                                    owner_id=source_requirement_id, candidate_id=source_id,
                                    location="expression_input",
                                    repair_action="replace_candidate" if detail in _scope_errors(candidate_by_id[source_id], {"scope": dict(requirement.get("scope") or {})}, conflicts_only=True) else "repair_program",
                                )
                                invalid = True
                        variable_units[variable] = _candidate_dimension(candidate)
                        source_candidates.append(source_id)
                    else:
                        declared_dependencies = {
                            str(item or "").strip()
                            for item in (obligation or {}).get("depends_on") or []
                        }
                        if source_id not in declared_dependencies:
                            error(
                                "undeclared_expression_dependency", obligation_id, source_id,
                                location="expression_input.source_id",
                            )
                            invalid = True
                        if binding.get("context_bindings"):
                            error("context_binding_on_dependency", obligation_id,
                                  location="expression_input.context_bindings")
                            invalid = True
                        resolved_expression_sources.extend(resolved_sources_by_output.get(source_id, []))
                        if source_requirement_id:
                            error(
                                "unexpected_source_requirement_id",
                                obligation_id,
                                source_requirement_id,
                            )
                            invalid = True
                        variable_units[variable] = output_units[source_id]
                        for inherited_id in sources_by_output.get(source_id, []):
                            if not candidate_section_is_authorized(inherited_id, obligation_id, dependency=True):
                                invalid = True
                        source_candidates.extend(sources_by_output.get(source_id, []))
            if obligation:
                required_requirement_ids = {
                    str(item.get("requirement_id") or "").strip()
                    for item in (obligation.get("evidence_requirements") or [])
                    if bool(item.get("required", True))
                    and str(item.get("requirement_id") or "").strip()
                }
                for missing_requirement_id in sorted(
                    required_requirement_ids - bound_requirement_ids
                ):
                    error(
                        "missing_required_evidence_binding",
                        obligation_id,
                        missing_requirement_id,
                    )
                    invalid = True
            if invalid:
                continue
            try:
                dimension = _formula_dimension(body, variable_units)
            except ValueError as exc:
                error("formula_unit_mismatch", obligation_id, str(exc))
                continue
            display_unit = _expression_display_unit(expression, obligation or {}, dimension)
            if not _display_unit_valid(display_unit, dimension):
                error("result_unit_mismatch", obligation_id, f"{dimension} -> {display_unit}",
                      location="expression.display_unit")
                continue
            display_candidate: Optional[Mapping[str, Any]] = None
            display_id = str(expression.get("source_display_candidate_id") or "").strip()
            expression.pop("source_display_context_resolution", None)
            if not display_id and expression.get("source_display_context_bindings"):
                error("context_binding_without_source_display", obligation_id,
                      location="source_display.context_bindings")
                continue
            if display_id:
                if not candidate_is_exposed(display_id, obligation_id):
                    error(
                        "candidate_not_exposed_to_compiler",
                        obligation_id,
                        display_id,
                    )
                    continue
                display_candidate = candidate_by_id.get(display_id)
                if (
                    not display_candidate
                    or str(display_candidate.get("kind") or "") != "numeric"
                    or not _candidate_has_finite_numeric_value(display_candidate)
                ):
                    error("invalid_source_display_candidate", obligation_id, display_id)
                    continue
                display_candidate, context_valid = contextual_candidate(
                    display_candidate, expression, obligation_id, obligation_id,
                    "source_display.context_bindings", bindings_key="source_display_context_bindings",
                    resolution_key="source_display_context_resolution")
                if not context_valid:
                    continue
                display_scope_errors = _scope_errors(
                    display_candidate,
                    obligation or {},
                )
                if display_scope_errors:
                    for detail in display_scope_errors:
                        error("source_display_scope_mismatch", obligation_id, detail,
                              candidate_id=display_id, location="source_display",
                              repair_action="replace_candidate" if detail in _scope_errors(candidate_by_id[display_id], obligation or {}, conflicts_only=True) else "repair_program")
                    continue
                display_dimension = _candidate_dimension(display_candidate)
                compatible_display_dimensions = (
                    {"PERCENT"} if dimension == "RATIO" else
                    {"COUNT", "UNKNOWN"} if dimension == "SCALAR" else
                    {dimension}
                )
                if display_dimension not in compatible_display_dimensions:
                    error(
                        "source_display_unit_mismatch",
                        obligation_id,
                        f"{display_dimension} cannot display {dimension}",
                        candidate_id=display_id, location="source_display",
                        repair_action="replace_candidate",
                    )
                    continue
                if not render_grounded_operand_display(
                    project_semantic_program_operand(
                        display_candidate,
                        obligation_id=obligation_id,
                    )
                ):
                    error("empty_source_display_rendering", obligation_id, display_id)
                    continue
                source_candidates.append(display_id)
                resolved_expression_sources.append(display_candidate)
            compatibility_ids = list(
                dict.fromkeys(
                    str(item).strip()
                    for item in (expression.get("compatibility_candidate_ids") or [])
                    if str(item).strip()
                )
            )
            invalid_compatibility_id = next(
                (
                    candidate_id
                    for candidate_id in compatibility_ids
                    if candidate_id not in candidate_by_id
                    or str(candidate_by_id[candidate_id].get("kind") or "")
                    != "narrative"
                    or not _normalise_spaces(
                        str(candidate_by_id[candidate_id].get("source_text") or "")
                    )
                ),
                "",
            )
            if invalid_compatibility_id:
                error(
                    "invalid_compatibility_candidate",
                    obligation_id,
                    invalid_compatibility_id,
                )
                continue
            hidden_compatibility_id = next(
                (
                    candidate_id
                    for candidate_id in compatibility_ids
                    if not candidate_is_exposed(candidate_id, obligation_id)
                ),
                "",
            )
            if hidden_compatibility_id:
                error(
                    "candidate_not_exposed_to_compiler",
                    obligation_id,
                    hidden_compatibility_id,
                )
                continue
            numeric_context_candidates = [
                candidate_by_id[candidate_id]
                for candidate_id in source_candidates
                if candidate_id in candidate_by_id
                and str(candidate_by_id[candidate_id].get("kind") or "") == "numeric"
            ]
            context_conflicts = _expression_context_conflicts(
                resolved_expression_sources or numeric_context_candidates
            )
            if context_conflicts and not compatibility_ids:
                error(
                    "expression_context_mismatch",
                    obligation_id,
                    ",".join(context_conflicts),
                )
                continue
            source_candidates.extend(compatibility_ids)
            if already_produced(obligation_id):
                continue
            produced.add(obligation_id)
            valid_expressions.append(expression)
            resolved_sources_by_output[obligation_id] = resolved_expression_sources
            output_units[obligation_id] = dimension
            sources_by_output[obligation_id] = list(dict.fromkeys(source_candidates))
            compatibility_sources_by_output[obligation_id] = compatibility_ids
            progressed = True
        if not deferred:
            break
        if not progressed:
            for expression in deferred:
                error(
                    "cyclic_or_unresolved_expression_dependency",
                    str(expression.get("obligation_id") or "").strip(),
                )
            break
        unresolved = deferred

    for raw in program.get("narrative_bindings") or []:
        binding = dict(raw or {})
        obligation_id = str(binding.get("obligation_id") or "").strip()
        try:
            binding = project_narrative_claims(binding)
        except ValueError as exc:
            error(str(exc), obligation_id, location="narrative_claims")
            continue
        # Resolution is validator-owned, not a model-written permission.
        binding.pop("description_readings", None)
        binding.pop("claim_readings", None)
        obligation_id = str(binding.get("obligation_id") or "").strip()
        obligation = obligation_by_id.get(obligation_id)
        candidate_ids = narrative_candidate_ids(binding)
        selected = [candidate_by_id[item] for item in candidate_ids if item in candidate_by_id]
        raw_scope_applicability_fields = [
            str(item).strip()
            for item in (binding.get("scope_applicability_fields") or [])
            if str(item).strip()
        ]
        invalid_scope_applicability_fields = [
            field
            for field in raw_scope_applicability_fields
            if field not in _NARRATIVE_SCOPE_APPLICABILITY_FIELDS
        ]
        scope_applicability_fields = list(
            dict.fromkeys(
                field
                for field in raw_scope_applicability_fields
                if field in _NARRATIVE_SCOPE_APPLICABILITY_FIELDS
            )
        )
        invalid = False
        if require_narrative_claims and not binding.get("claims"):
            error("missing_narrative_claims", obligation_id, location="narrative_claims")
            invalid = True
        claim_readings, claim_errors = validate_narrative_claims(
            {**binding, "candidate_ids": candidate_ids}, candidate_by_id,
            number_check=_ungrounded_narrative_numbers,
            visible_candidate_ids=None if selectable_ids is None else sorted(selectable_ids),
            require_addressed=require_narrative_claims,
            selection_is_permitted=lambda link: candidate_is_exposed(link["candidate_id"], obligation_id)
                and (not link.get("source_requirement_id") or (
                    requirement_owner_by_id.get(link["source_requirement_id"]) == obligation_id
                    and candidate_is_exposed(link["candidate_id"], link["source_requirement_id"]))))
        for claim_error in claim_errors:
            error(obligation_id=obligation_id, **claim_error)
            invalid = True
        if not obligation or str(obligation.get("kind") or "") != "narrative":
            error("invalid_narrative_obligation", obligation_id)
            invalid = True
        if obligation_id in blocked:
            error("blocked_obligation_has_output", obligation_id)
            invalid = True
        if not candidate_ids or len(selected) != len(candidate_ids):
            error("unknown_narrative_candidate", obligation_id)
            invalid = True
        for field in invalid_scope_applicability_fields:
            error("invalid_scope_applicability_field", obligation_id, field)
            invalid = True
        hidden_candidate_id = next(
            (
                candidate_id
                for candidate_id in candidate_ids
                if not candidate_is_exposed(candidate_id, obligation_id)
            ),
            "",
        )
        if hidden_candidate_id:
            error(
                "candidate_not_exposed_to_compiler",
                obligation_id,
                hidden_candidate_id,
            )
            invalid = True
        semantic_conflict_id = next(
            (
                candidate_id
                for candidate_id in candidate_ids
                if obligation
                and candidate_has_source_conflict(candidate_id, obligation_id)
            ),
            "",
        )
        if semantic_conflict_id:
            error(
                "candidate_source_condition_conflict",
                obligation_id,
                semantic_conflict_id,
            )
            invalid = True
        description_readings: List[Dict[str, Any]] = []
        description_quotes: Dict[str, List[str]] = {}
        scalar_evidence_ids: set[str] = set()
        for raw_evidence_binding in binding.get("evidence_bindings") or []:
            evidence_binding = dict(raw_evidence_binding or {})
            candidate_id = str(evidence_binding.get("candidate_id") or "").strip()
            quote = evidence_binding.get("row_description_quote", "")
            if quote == "":
                scalar_evidence_ids.add(candidate_id)
                continue
            candidate = candidate_by_id.get(candidate_id)
            if not candidate or candidate_id not in candidate_ids:
                continue  # The ordinary ID checks below reject this binding.
            requirement_id = str(evidence_binding.get("source_requirement_id") or "").strip()
            try:
                reading = _row_description_reading(candidate, quote)
            except ValueError as exc:
                error(str(exc), obligation_id, owner_id=requirement_id or obligation_id,
                    candidate_id=candidate_id, location="narrative_input")
                invalid = True
                continue
            description_quotes.setdefault(candidate_id, []).append(quote)
            description_readings.append({"candidate_id": candidate_id,
                "source_requirement_id": requirement_id, **reading})
        description_only_ids = set(description_quotes) - scalar_evidence_ids
        if binding.get("claims"):
            # The claim validator has already resolved exact visible bundle/context
            # quotes. Raw candidate bodies are neither the same surface nor extra
            # number authority. Keep the independent description-only restriction;
            # claim-local checks above still prevent borrowing another claim's numbers.
            number_sources = [
                {"source_text": " ".join(description_quotes[evidence["candidate_id"]])
                    if evidence["candidate_id"] in description_only_ids else evidence["evidence_text"],
                 "year": candidate_by_id[evidence["candidate_id"]].get("year")}
                for reading in claim_readings for evidence in reading["evidence"]
            ]
        else:
            # Explicit historical flat inspection retains its original contract.
            number_sources = [
                {"source_text": " ".join(description_quotes[str(candidate["candidate_id"])]),
                 "year": candidate.get("year")}
                if str(candidate.get("candidate_id") or "") in description_only_ids else candidate
                for candidate in selected
            ]
        text = _normalise_spaces(str(binding.get("text") or ""))
        if not text:
            error("empty_narrative_output", obligation_id)
            invalid = True
        ungrounded_numbers = (
            _ungrounded_narrative_numbers(text, number_sources) if text and selected else []
        )
        if ungrounded_numbers:
            error(
                "ungrounded_narrative_number",
                obligation_id,
                ", ".join(ungrounded_numbers),
            )
            invalid = True
        if obligation:
            for candidate in selected:
                candidate_id = str(candidate.get("candidate_id") or "")
                if candidate.get("kind") != "numeric" or candidate_id in description_only_ids:
                    continue
                period_state = _period_scope_state((obligation.get("scope") or {}).get("period"), candidate,
                    allow_filing_scope=False)
                if period_state != "match":
                    error("candidate_scope_mismatch", obligation_id, "scope mismatch: period",
                        candidate_id=candidate_id, location="narrative_input",
                        repair_action="replace_candidate" if period_state == "conflict" else "repair_program")
                    invalid = True
            for detail in _collective_narrative_scope_errors(
                selected,
                obligation,
                applicable_unknown_fields=scope_applicability_fields,
                description_candidate_ids=description_only_ids,
            ):
                error("candidate_scope_mismatch", obligation_id, detail)
                invalid = True
            required_requirement_ids = {
                str(item.get("requirement_id") or "").strip()
                for item in (obligation.get("evidence_requirements") or [])
                if isinstance(item, Mapping)
                and bool(item.get("required", True))
                and str(item.get("requirement_id") or "").strip()
            }
            bound_requirement_ids: set[str] = set()
            bound_candidate_ids_by_requirement: Dict[str, set[str]] = {}
            for raw_evidence_binding in binding.get("evidence_bindings") or []:
                evidence_binding = dict(raw_evidence_binding or {})
                candidate_id = str(
                    evidence_binding.get("candidate_id") or ""
                ).strip()
                requirement_id = str(
                    evidence_binding.get("source_requirement_id") or ""
                ).strip()
                if candidate_id not in candidate_ids:
                    error(
                        "narrative_requirement_candidate_not_selected",
                        obligation_id,
                        candidate_id,
                    )
                    invalid = True
                    continue
                if not requirement_id:
                    # Owner authority/scope still apply; this satisfies no requirement.
                    continue
                requirement = requirement_by_id.get(requirement_id)
                if not requirement:
                    error(
                        "unknown_narrative_requirement",
                        obligation_id,
                        requirement_id,
                    )
                    invalid = True
                    continue
                if requirement_owner_by_id.get(requirement_id) != obligation_id:
                    error(
                        "narrative_requirement_owner_mismatch",
                        obligation_id,
                        requirement_id,
                    )
                    invalid = True
                    continue
                if not candidate_is_exposed(candidate_id, requirement_id):
                    error(
                        "candidate_not_exposed_to_compiler",
                        obligation_id,
                        candidate_id,
                    )
                    invalid = True
                    continue
                candidate = candidate_by_id.get(candidate_id)
                if not candidate:
                    error(
                        "unknown_narrative_candidate",
                        obligation_id,
                        candidate_id,
                    )
                    invalid = True
                    continue
                if candidate_has_source_conflict(candidate_id, requirement_id):
                    error(
                        "candidate_source_condition_conflict",
                        obligation_id,
                        f"{requirement_id}: {candidate_id}",
                        owner_id=requirement_id, candidate_id=candidate_id,
                        location="narrative_input", repair_action="replace_candidate",
                    )
                    invalid = True
                    continue
                bound_requirement_ids.add(requirement_id)
                bound_candidate_ids_by_requirement.setdefault(
                    requirement_id, set()
                ).add(candidate_id)
                for detail in _scope_errors(
                    candidate,
                    {"scope": dict(requirement.get("scope") or {})},
                    applicable_unknown_fields=scope_applicability_fields,
                    row_description=bool(evidence_binding.get("row_description_quote")) and candidate_id in description_quotes,
                ):
                    error(
                        "candidate_requirement_scope_mismatch",
                        obligation_id,
                        f"{requirement_id}: {detail}",
                        owner_id=requirement_id, candidate_id=candidate_id,
                        location="narrative_input",
                        repair_action="replace_candidate" if detail in _scope_errors(candidate, {"scope": dict(requirement.get("scope") or {})}, conflicts_only=True,
                            row_description=bool(evidence_binding.get("row_description_quote")) and candidate_id in description_quotes) else "repair_program",
                    )
                    invalid = True
            for missing_requirement_id in sorted(
                required_requirement_ids - bound_requirement_ids
            ):
                error(
                    "missing_required_evidence_binding",
                    obligation_id,
                    missing_requirement_id,
                )
                invalid = True
            if (
                str(obligation.get("evidence_mode") or "declared_inputs")
                == "source_defined_group"
                and selectable_ids_by_owner is not None
            ):
                visible_owner_ids = (
                    candidate_visibility.candidate_ids_by_owner().get(
                        obligation_id, []
                    )
                    if candidate_visibility is not None
                    else sorted(
                        selectable_ids_by_owner.get(obligation_id, set())
                    )
                )
                group_selection = select_source_defined_physical_row_group(
                    candidate_rows,
                    visible_owner_ids,
                )
                required_group_candidate_ids = [
                    str(candidate_id)
                    for candidate_id in (
                        group_selection.get("required_candidate_ids") or []
                    )
                    if str(candidate_id)
                ]
                missing_selected_ids = [
                    candidate_id
                    for candidate_id in required_group_candidate_ids
                    if candidate_id not in candidate_ids
                ]
                if missing_selected_ids:
                    error(
                        "incomplete_source_defined_group",
                        obligation_id,
                        ",".join(missing_selected_ids),
                    )
                    invalid = True
                group_requirement_id = next(
                    (
                        str(requirement.get("requirement_id") or "").strip()
                        for requirement in (
                            obligation.get("evidence_requirements") or []
                        )
                        if isinstance(requirement, Mapping)
                        and bool(requirement.get("required", True))
                        and str(requirement.get("requirement_id") or "").strip()
                    ),
                    "",
                )
                missing_binding_ids = [
                    candidate_id
                    for candidate_id in required_group_candidate_ids
                    if candidate_id
                    not in bound_candidate_ids_by_requirement.get(
                        group_requirement_id, set()
                    )
                ]
                if missing_binding_ids:
                    error(
                        "missing_source_defined_group_binding",
                        obligation_id,
                        ",".join(missing_binding_ids),
                    )
                    invalid = True
                if not missing_selected_ids:
                    missing_value_ids = _missing_narrative_candidate_values(
                        text,
                        [
                            candidate_by_id[candidate_id]
                            for candidate_id in required_group_candidate_ids
                            if candidate_id in candidate_by_id
                        ],
                    )
                    if missing_value_ids:
                        error(
                            "source_defined_group_value_omitted",
                            obligation_id,
                            ",".join(missing_value_ids),
                        )
                        invalid = True
        if already_produced(obligation_id):
            invalid = True
        if invalid:
            continue
        produced.add(obligation_id)
        valid_narrative.append(
            {
                **binding,
                "text": text,
                "candidate_ids": candidate_ids,
                "scope_applicability_fields": scope_applicability_fields,
                **({"description_readings": description_readings} if description_readings else {}),
                **({"claim_readings": claim_readings} if claim_readings else {}),
            }
        )
        sources_by_output[obligation_id] = candidate_ids

    invalid_bundled: set[str] = set()
    for constraint in (
        candidate_visibility.evidence_bundle_constraints
        if candidate_visibility is not None
        else ()
    ):
        owner_ids = [
            owner_id
            for owner_id in constraint.owner_ids
            if owner_id in obligation_by_id
        ]
        if len(owner_ids) < 2 or not all(
            owner_id in produced for owner_id in owner_ids
        ):
            evidence_bundle_validation.append(
                {
                    "constraint_id": constraint.constraint_id,
                    "status": "incomplete",
                    "owner_ids": owner_ids,
                    "selected_option_id": "",
                }
            )
            continue
        selected_by_owner = {
            owner_id: [
                candidate_id
                for candidate_id in sources_by_output.get(owner_id, [])
                if candidate_id
                not in set(
                    compatibility_sources_by_output.get(owner_id, [])
                )
            ]
            for owner_id in owner_ids
        }
        matching_options = [
            option
            for option in constraint.options
            if all(
                option.allows(owner_id, selected_by_owner[owner_id])
                for owner_id in owner_ids
            )
        ]
        if matching_options:
            evidence_bundle_validation.append(
                {
                    "constraint_id": constraint.constraint_id,
                    "status": "ready",
                    "owner_ids": owner_ids,
                    "selected_option_id": matching_options[0].option_id,
                }
            )
            continue

        ranked_options = sorted(
            enumerate(constraint.options),
            key=lambda item: (
                -sum(
                    item[1].allows(owner_id, selected_by_owner[owner_id])
                    for owner_id in owner_ids
                ),
                item[0],
            ),
        )
        closest_option = ranked_options[0][1]
        closest_ids_by_owner = closest_option.candidate_ids_by_owner()
        mismatched_owner_ids: List[str] = []
        for owner_id in owner_ids:
            if closest_option.allows(owner_id, selected_by_owner[owner_id]):
                continue
            mismatched_owner_ids.append(owner_id)
            allowed = set(closest_ids_by_owner.get(owner_id, []))
            rejected_ids = [
                candidate_id
                for candidate_id in selected_by_owner[owner_id]
                if candidate_id not in allowed
            ]
            for candidate_id in rejected_ids or selected_by_owner[owner_id]:
                error("evidence_bundle_mismatch", owner_id, candidate_id,
                      owner_id=owner_id, candidate_id=candidate_id,
                      location="evidence_bundle", repair_action="replace_candidate")
        invalid_bundled.update(owner_ids)
        evidence_bundle_validation.append(
            {
                "constraint_id": constraint.constraint_id,
                "status": "mismatch",
                "owner_ids": owner_ids,
                "selected_option_id": "",
                "closest_option_id": closest_option.option_id,
                "mismatched_owner_ids": mismatched_owner_ids,
            }
        )
    if invalid_bundled:
        valid_direct = [
            item
            for item in valid_direct
            if str(item.get("obligation_id") or "") not in invalid_bundled
        ]
        valid_narrative = [
            item
            for item in valid_narrative
            if str(item.get("obligation_id") or "") not in invalid_bundled
        ]
        produced.difference_update(invalid_bundled)

    relationships, relationship_errors = output_relationships(obligation_rows, query)
    errors.extend(relationship_errors)
    invalid_coupled = {issue["obligation_id"] for issue in relationship_errors}
    for relation_id, relation in relationships.items():
        obligation_ids = relation["output_ids"]
        if not all(owner_id in produced for owner_id in obligation_ids):
            continue
        consolidation_scopes = {
            str(source.get("consolidation_scope") or "").lower()
            for owner_id in obligation_ids
            for source in resolved_sources_by_output.get(owner_id, [])
        } - {"", "unknown"}
        if len(consolidation_scopes) > 1:
            for owner_id in obligation_ids:
                error("relationship_source_scope_conflict", owner_id, relation_id,
                      location="output_relationship.consolidation_scope", repair_action="repair_program")
                invalid_coupled.add(owner_id)
            continue
        # The compiler's common-basis declaration is checked for consistency,
        # not equated with sharing a chunk/table. Physical same-row rules above
        # are independent. The truth of this interpretation is model-evaluated.
        declarations = []
        for owner_id in obligation_ids:
            if obligation_by_id[owner_id].get("kind") == "narrative":
                declarations.append(next((str(row.get("basis_interpretation") or "") for row in valid_narrative
                                          if row["obligation_id"] == owner_id), ""))
                continue
            sources = resolved_sources_by_output.get(owner_id, [])
            declarations.extend(str((source.get("source_interpretation_resolution") or {}).get("scope", {}).get("basis") or "")
                                for source in sources if source.get("kind") == "numeric")
        if not declarations or any(not value.strip() for value in declarations) or len(set(declarations)) != 1:
            for owner_id in obligation_ids:
                error("relationship_interpretation_missing_or_inconsistent", owner_id, relation_id,
                      location="source_interpretation.scope.basis", repair_action="repair_program")
                invalid_coupled.add(owner_id)
    if invalid_coupled:
        valid_direct = [
            item for item in valid_direct if str(item.get("obligation_id") or "") not in invalid_coupled
        ]
        valid_expressions = [
            item for item in valid_expressions if str(item.get("obligation_id") or "") not in invalid_coupled
        ]
        valid_narrative = [
            item for item in valid_narrative if str(item.get("obligation_id") or "") not in invalid_coupled
        ]
        produced.difference_update(invalid_coupled)

    source_bundles = build_semantic_source_bundles(candidate_rows)
    source_bundle_by_id = {
        bundle.source_bundle_id: bundle for bundle in source_bundles
    }
    source_bundle_id_by_candidate = source_bundle_id_by_candidate_id(
        source_bundles
    )
    selected_obligations_by_candidate: Dict[str, List[str]] = {}
    required_assertion_ids_by_obligation: Dict[str, List[str]] = {}
    for obligation_id in obligation_by_id:
        if obligation_id not in produced:
            continue
        for candidate_id in sources_by_output.get(obligation_id, []):
            candidate = candidate_by_id.get(candidate_id)
            if not candidate or str(candidate.get("kind") or "") != "numeric":
                continue
            selected_obligations_by_candidate.setdefault(candidate_id, [])
            if obligation_id not in selected_obligations_by_candidate[candidate_id]:
                selected_obligations_by_candidate[candidate_id].append(obligation_id)
            source_bundle = source_bundle_by_id.get(
                source_bundle_id_by_candidate.get(candidate_id, "")
            )
            if (
                str(candidate.get("candidate_kind") or "") == "sentence_value"
                and source_bundle is not None
                and source_bundle.source_kind == "prose_sentence"
            ):
                required_assertion_ids_by_obligation.setdefault(
                    obligation_id, []
                )
                if candidate_id not in required_assertion_ids_by_obligation[
                    obligation_id
                ]:
                    required_assertion_ids_by_obligation[obligation_id].append(
                        candidate_id
                    )

    valid_source_assertions: List[Dict[str, Any]] = []
    asserted_candidate_ids: set[str] = set()
    invalid_assertion_obligation_ids: set[str] = set()
    for raw_assertion in program.get("source_assertions") or []:
        assertion = dict(raw_assertion or {})
        source_bundle_id = str(
            assertion.get("source_bundle_id") or ""
        ).strip()
        candidate_ids = list(
            dict.fromkeys(
                str(candidate_id).strip()
                for candidate_id in (assertion.get("candidate_ids") or [])
                if str(candidate_id).strip()
            )
        )
        evidence_text = str(assertion.get("evidence_text") or "")
        related_obligation_ids = [
            obligation_id
            for obligation_id in obligation_by_id
            if any(obligation_id in selected_obligations_by_candidate.get(candidate_id, [])
                   or obligation_id in declared_source_owners.get(candidate_id, set())
                   for candidate_id in candidate_ids)
        ]

        assertion_error = ""
        detail = source_bundle_id
        bundle = source_bundle_by_id.get(source_bundle_id)
        if not source_bundle_id or bundle is None:
            assertion_error = "unknown_source_bundle"
        elif not candidate_ids:
            assertion_error = "empty_source_assertion_candidates"
        elif any(candidate_id not in candidate_by_id for candidate_id in candidate_ids):
            assertion_error = "unknown_source_assertion_candidate"
        elif any(
            candidate_id not in selected_obligations_by_candidate
            for candidate_id in candidate_ids
        ):
            assertion_error = "source_assertion_candidate_not_selected"
        elif any(
            str(candidate_by_id[candidate_id].get("candidate_kind") or "")
            != "sentence_value"
            or source_bundle_by_id[
                source_bundle_id_by_candidate.get(candidate_id, "")
            ].source_kind
            != "prose_sentence"
            for candidate_id in candidate_ids
        ):
            assertion_error = "source_assertion_nonprose_candidate"
        elif any(
            source_bundle_id_by_candidate.get(candidate_id) != source_bundle_id
            for candidate_id in candidate_ids
        ):
            assertion_error = "source_assertion_bundle_mismatch"
        elif not evidence_text:
            assertion_error = "empty_source_assertion_text"
        else:
            value_spans = bundle.value_span_by_candidate_id()
            if any(candidate_id not in value_spans for candidate_id in candidate_ids):
                assertion_error = "source_assertion_value_span_missing"
            else:
                occurrence_starts: List[int] = []
                search_start = 0
                while True:
                    occurrence_start = bundle.source_text.find(
                        evidence_text, search_start
                    )
                    if occurrence_start < 0:
                        break
                    occurrence_starts.append(occurrence_start)
                    search_start = occurrence_start + 1
                grounded_start = next(
                    (
                        occurrence_start
                        for occurrence_start in occurrence_starts
                        if all(
                            occurrence_start <= value_spans[candidate_id][0]
                            and value_spans[candidate_id][1]
                            <= occurrence_start + len(evidence_text)
                            for candidate_id in candidate_ids
                        )
                    ),
                    None,
                )
                if grounded_start is None:
                    assertion_error = "source_assertion_text_mismatch"

        if assertion_error:
            target_ids = related_obligation_ids or sorted(produced) or [""]
            for obligation_id in target_ids:
                error(
                    assertion_error, obligation_id, detail,
                    candidate_id=candidate_ids[0] if len(candidate_ids) == 1 else "",
                    location="source_assertion",
                )
                if obligation_id:
                    invalid_assertion_obligation_ids.add(obligation_id)
            continue

        assertion_projection = {
            "source_bundle_id": source_bundle_id,
            "candidate_ids": candidate_ids,
            "evidence_text": evidence_text,
        }
        assertion_fingerprint = hashlib.sha256(
            json.dumps(
                assertion_projection,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        valid_source_assertions.append(
            {
                **assertion_projection,
                "assertion_fingerprint": assertion_fingerprint,
                "covered_obligation_ids": related_obligation_ids,
            }
        )
        asserted_candidate_ids.update(candidate_ids)

    for obligation_id, candidate_ids in required_assertion_ids_by_obligation.items():
        for candidate_id in candidate_ids:
            if candidate_id in asserted_candidate_ids:
                continue
            error(
                "missing_source_assertion", obligation_id, candidate_id,
                candidate_id=candidate_id, location="source_assertion",
            )
            invalid_assertion_obligation_ids.add(obligation_id)

    if invalid_assertion_obligation_ids:
        valid_direct = [
            item
            for item in valid_direct
            if str(item.get("obligation_id") or "")
            not in invalid_assertion_obligation_ids
        ]
        valid_expressions = [
            item
            for item in valid_expressions
            if str(item.get("obligation_id") or "")
            not in invalid_assertion_obligation_ids
        ]
        valid_narrative = [
            item
            for item in valid_narrative
            if str(item.get("obligation_id") or "")
            not in invalid_assertion_obligation_ids
        ]
        produced.difference_update(invalid_assertion_obligation_ids)

    required = {
        obligation_id
        for obligation_id, obligation in obligation_by_id.items()
        if bool(obligation.get("required", True))
    }
    missing = sorted((required - produced) | (declared_missing & required))
    ambiguous = sorted(declared_ambiguous & required)
    selected_candidate_ids = list(
        dict.fromkeys(
            candidate_id
            for obligation_id in obligation_by_id
            if obligation_id in produced
            for candidate_id in sources_by_output.get(obligation_id, [])
        )
    )
    material_errors = [
        item
        for item in errors
        if not item.get("obligation_id") or item.get("obligation_id") in required
    ]
    if not missing and not ambiguous and not material_errors:
        status = "ready"
    elif produced:
        status = "partial"
    else:
        status = "invalid"
    return {
        "status": status,
        "errors": errors,
        "valid_direct_bindings": valid_direct,
        "valid_expressions": valid_expressions,
        "valid_narrative_bindings": valid_narrative,
        "valid_source_assertions": valid_source_assertions,
        "missing_obligation_ids": missing,
        "ambiguous_obligation_ids": ambiguous,
        "selected_candidate_ids": selected_candidate_ids,
        "source_candidate_ids_by_obligation": sources_by_output,
        "inferred_units": output_units,
        "evidence_bundle_validation": evidence_bundle_validation,
    }


def project_semantic_program_operand(
    candidate: Mapping[str, Any],
    obligation_id: str = "",
    *,
    obligation: Optional[Mapping[str, Any]] = None,
    validated_binding: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """Project one source candidate into the canonical calculation operand."""

    candidate_id = str(candidate.get("candidate_id") or "")
    binding = dict(validated_binding or {})
    resolution = dict(binding.get("context_resolution") or {})
    interpretation = dict(binding.get("source_interpretation_resolution") or {})
    if resolution:
        candidate = {**dict(candidate), **dict(resolution.get("scope") or {})}
    obligation_row = dict(obligation or {})
    obligation_scope = dict(obligation_row.get("scope") or {})
    period = str(candidate.get("period") or "")
    period_source = str(candidate.get("period_source") or "")
    value_year = candidate.get("value_year")
    if not period and value_year not in (None, ""):
        period = str(value_year)
        period_source = period_source or "candidate_value_year"
    if not period:
        requirement_period = str(obligation_scope.get("period") or "")
        if requirement_period and requirement_period.lower() != "unknown":
            period = requirement_period
            period_source = "requirement_scope"
    if value_year in (None, ""):
        period_years = re.findall(r"(?<!\d)(?:19|20)\d{2}(?!\d)", period)
        if len(set(period_years)) == 1:
            value_year = int(period_years[0])
    raw_row_headers = candidate.get("row_headers") or []
    if isinstance(raw_row_headers, (str, bytes)):
        raw_row_headers = [raw_row_headers]
    elif not isinstance(raw_row_headers, Sequence):
        raw_row_headers = []
    return {
        "operand_id": candidate_id,
        "candidate_id": candidate_id,
        "evidence_id": candidate_id,
        "source_evidence_id": str(candidate.get("evidence_id") or ""),
        "source_anchor": str(candidate.get("source_anchor") or ""),
        "source_row_id": str(candidate.get("source_row_id") or ""),
        "source_row_ids": _clean_source_row_ids(
            [
                candidate_id,
                candidate.get("source_row_id"),
                candidate.get("evidence_id"),
                candidate.get("source_candidate_id"),
            ]
        ),
        "label": str(
            obligation_row.get("label")
            or candidate.get("row_label")
            or obligation_id
        ),
        "subject": str(binding.get("resolved_subject") or ""),
        "subject_source": str(binding.get("subject_source") or ""),
        "subject_source_row_ids": _clean_source_row_ids(
            binding.get("subject_source_row_ids") or []
        ),
        "row_label": str(candidate.get("row_label") or ""),
        "row_headers": [
            _normalise_spaces(str(item or ""))
            for item in raw_row_headers
            if _normalise_spaces(str(item or ""))
        ],
        "raw_value": str(candidate.get("raw_value") or ""),
        "raw_unit": str(candidate.get("raw_unit") or ""),
        "source_unit_hint": str(candidate.get("source_unit_hint") or ""),
        "raw_unit_source": str(candidate.get("raw_unit_source") or ""),
        **({"source_unit_provenance": dict(candidate["source_unit_provenance"])}
           if candidate.get("source_unit_provenance") else {}),
        "normalized_value": candidate.get("normalized_value"),
        "normalized_unit": str(candidate.get("normalized_unit") or "UNKNOWN"),
        "period": period,
        "source_period_surface": str(
            candidate.get("source_period_surface") or ""
        ),
        "period_source": period_source,
        "period_label_surfaces": list(candidate.get("period_label_surfaces") or []),
        "period_label_scope": str(candidate.get("period_label_scope") or ""),
        "value_year": value_year,
        "table_source_id": str(candidate.get("table_source_id") or ""),
        **{key: candidate[key] for key in (
            "source_document_id", "physical_table_id", "physical_row_id",
            "physical_cell_id", "physical_value_id", "physical_cell_key",
        ) if candidate.get(key)},
        "statement_type": str(candidate.get("statement_type") or ""),
        "consolidation_scope": str(candidate.get("consolidation_scope") or ""),
        "consolidation_scope_source": str(
            candidate.get("consolidation_scope_source") or ""
        ),
        "value_role": str(candidate.get("value_role") or ""),
        "aggregation_stage": str(candidate.get("aggregation_stage") or ""),
        "aggregate_label": str(candidate.get("aggregate_label") or ""),
        "matched_operand_role": obligation_id,
        **({"context_resolution": resolution} if resolution else {}),
        **({"source_interpretation_resolution": interpretation} if interpretation else {}),
    }


def _project_expression_input(
    binding: Mapping[str, Any],
    *,
    candidate: Optional[Mapping[str, Any]],
    obligation: Mapping[str, Any],
    source_output: Optional[Mapping[str, Any]],
    source_operand: Optional[Mapping[str, Any]],
) -> Optional[Dict[str, Any]]:
    """Record the same calculated input that enters the arithmetic environment.

    Dependency references stay immediate; their arithmetic lineage excludes display
    and compatibility witnesses. Derived values never impersonate a source cell.
    """
    source_id = str(binding.get("source_id") or "")
    if candidate is not None:
        row = project_semantic_program_operand(
            candidate,
            obligation_id=str(
                binding.get("source_requirement_id") or obligation.get("obligation_id") or ""
            ),
            obligation=obligation,
            validated_binding=binding,
        )
        source_kind = "candidate"
        provenance = {
            "input_candidate_ids": [source_id],
            "source_row_ids": row["source_row_ids"],
            "source_anchors": [row["source_anchor"]] if row["source_anchor"] else [],
        }
    elif source_output is not None and source_output.get("normalized_value") is not None:
        source_kind = "obligation"
        row = {
            **dict(source_operand or {}),
            "label": source_output["label"],
            "normalized_value": source_output["normalized_value"],
            "normalized_unit": source_output["normalized_unit"],
            "rendered_value": (
                source_output["formula_rendered_value"] if source_output["kind"] == "derived_value"
                else source_output["rendered_value"]
            ),
        }
        provenance = source_output["calculated_provenance"]
    else:
        return None
    try:
        value = float(row["normalized_value"])
    except (TypeError, ValueError):
        return None
    if not math.isfinite(value):
        return None
    return deepcopy({
        **row,
        "variable": str(binding.get("variable") or ""),
        "source_id": source_id,
        "source_kind": source_kind,
        "normalized_value": value,
        **{key: provenance[key]
           for key in ("input_candidate_ids", "source_row_ids", "source_anchors")},
    })


def _source_display_matches(candidate: Mapping[str, Any], formula_value: float) -> bool:
    try:
        source_value = float(candidate.get("normalized_value"))
    except (TypeError, ValueError):
        return False
    if not math.isfinite(source_value) or not math.isfinite(formula_value):
        return False
    display_tolerance = source_display_precision(
        str(candidate.get("raw_value") or ""), str(candidate.get("raw_unit") or "")
    )
    if display_tolerance is None:
        return False
    tolerance = max(1e-9, abs(float(formula_value)) * 1e-9, display_tolerance)
    return abs(source_value - float(formula_value)) <= tolerance


def _common_rendered_obligation_scope(
    obligations: Sequence[Mapping[str, Any]],
    outputs: Mapping[str, Mapping[str, Any]],
) -> Dict[str, str]:
    """Return only scope values shared by every rendered obligation."""

    rendered_scopes = [
        dict(obligation.get("scope") or {})
        for obligation in obligations
        if str(obligation.get("obligation_id") or "") in outputs
    ]
    if not rendered_scopes:
        return {}

    common: Dict[str, str] = {}
    empty_values = {"", "unknown", "unspecified", "none", "null"}
    for field in ("company", "period", "consolidation_scope", "segment", "basis"):
        values = [_normalise_spaces(str(scope.get(field) or "")) for scope in rendered_scopes]
        canonical = [value.casefold() for value in values]
        if (
            all(value not in empty_values for value in canonical)
            and len(set(canonical)) == 1
        ):
            common[field] = values[0]
    return common


def _known_rendered_consolidation_scope(value: Any) -> str:
    """Return a canonical consolidation scope only when render policy knows it."""

    canonical = _normalise_spaces(str(value or "")).casefold()
    known_scopes = {
        str(scope).casefold(): str(scope)
        for scope in dict(CALCULATION_RENDER_POLICY.get("scope_labels") or {})
    }
    return known_scopes.get(canonical, "")


def _rendered_output_consolidation_scope(
    obligation: Mapping[str, Any],
    output: Mapping[str, Any],
) -> str:
    """Resolve render-only scope without rewriting the obligation constraint."""

    obligation_scope = _known_rendered_consolidation_scope(
        dict(obligation.get("scope") or {}).get("consolidation_scope")
    )
    if obligation_scope:
        return obligation_scope
    if str(output.get("kind") or "") != "direct_value":
        return ""
    return _known_rendered_consolidation_scope(
        dict(output.get("answer_slot") or {}).get("consolidation_scope")
    )


def _rendered_numeric_consolidation_scopes(
    obligations: Sequence[Mapping[str, Any]],
    outputs: Mapping[str, Mapping[str, Any]],
) -> Tuple[Dict[str, str], str]:
    """Return per-output scopes and a shared scope only when every numeric output agrees."""

    scopes_by_id: Dict[str, str] = {}
    numeric_ids: List[str] = []
    for obligation in obligations:
        obligation_id = str(obligation.get("obligation_id") or "")
        output = outputs.get(obligation_id)
        if not output or str(output.get("kind") or "") == "narrative":
            continue
        numeric_ids.append(obligation_id)
        scope = _rendered_output_consolidation_scope(obligation, output)
        if scope:
            scopes_by_id[obligation_id] = scope
    unique_scopes = set(scopes_by_id.values())
    shared_scope = (
        next(iter(unique_scopes))
        if numeric_ids
        and len(scopes_by_id) == len(numeric_ids)
        and len(unique_scopes) == 1
        else ""
    )
    return scopes_by_id, shared_scope


def _rendered_consolidation_scope_label(value: Any, *, korean: bool) -> str:
    scope = _known_rendered_consolidation_scope(value)
    labels_key = "scope_labels" if korean else "scope_labels_en"
    return _normalise_spaces(
        str(dict(CALCULATION_RENDER_POLICY.get(labels_key) or {}).get(scope, ""))
    )


def _korean_semantic_output_subject(
    *,
    label: str,
    common_scope: Mapping[str, str],
    render_policy: Mapping[str, Any],
) -> str:
    """Project validated common scope into the first Korean numeric sentence."""

    clean_label = _normalise_spaces(label)
    label_folded = clean_label.casefold()
    tokens: List[str] = []

    company = _normalise_spaces(str(common_scope.get("company") or ""))
    if company and company.casefold() not in label_folded:
        tokens.append(
            f"{company}{str(render_policy.get('company_possessive_suffix') or '')}"
        )

    period = _normalise_spaces(str(common_scope.get("period") or ""))
    if period and period.casefold() not in label_folded:
        period_pattern = str(
            render_policy.get("period_year_pattern") or r"(?:19|20)\d{2}"
        )
        if re.fullmatch(period_pattern, period):
            period = f"{period}{str(render_policy.get('period_year_suffix') or '')}"
        tokens.append(period)

    consolidation_scope = _normalise_spaces(
        str(common_scope.get("consolidation_scope") or "")
    )
    scope_label = _rendered_consolidation_scope_label(
        consolidation_scope,
        korean=True,
    )
    if scope_label and scope_label.casefold() not in label_folded:
        tokens.append(scope_label)

    for field in ("segment", "basis"):
        value = _normalise_spaces(str(common_scope.get(field) or ""))
        if value and value.casefold() not in label_folded:
            tokens.append(value)

    return _normalise_spaces(" ".join([*tokens, clean_label]))


def _render_derived_input_summary(
    output: Mapping[str, Any],
    *,
    render_policy: Mapping[str, Any],
    korean_surface: bool,
) -> str:
    """Render source candidates or calculated dependencies used by one output."""

    item_template = str(
        render_policy.get("derived_input_item") or "{label} {value}"
    )
    joiner = str(render_policy.get("derived_input_joiner") or ", ")
    rendered_items: List[str] = []
    for raw_row in output.get("input_rows") or []:
        if not isinstance(raw_row, Mapping):
            continue
        row = dict(raw_row)
        dependency = row.get("source_kind") == "obligation"
        value = (
            str(row.get("rendered_value") or "") if dependency
            else render_grounded_operand_display(row)
        )
        if not value:
            continue
        label = _normalise_spaces(
            str(
                (row.get("label") if dependency else row.get("row_label"))
                or row.get("source_period_surface")
                or row.get("period")
                or ""
            )
        )
        fallback_label = _normalise_spaces(str(row.get("label") or ""))
        if (
            not label
            and fallback_label
            and fallback_label
            != _normalise_spaces(str(row.get("matched_operand_role") or ""))
        ):
            label = fallback_label
        if not label:
            year = row.get("value_year")
            if year is None or year == "":
                anchor_match = re.search(
                    r"\|\s*((?:19|20)\d{2})\s*\|",
                    str(row.get("source_anchor") or ""),
                )
                year = anchor_match.group(1) if anchor_match else ""
            label = _normalise_spaces(str(year or ""))
        period = _normalise_spaces(
            str((row.get("period") if dependency else row.get("source_period_surface") or row.get("period")) or "")
        )
        if period and period.casefold() not in label.casefold():
            label = _normalise_spaces(f"{period} {label}")
        rendered = _normalise_spaces(
            item_template.format(label=label, value=value)
        )
        if rendered and rendered not in rendered_items:
            rendered_items.append(rendered)
    if not rendered_items:
        return ""
    summary_template = str(
        render_policy.get(
            "derived_inputs_ko" if korean_surface else "derived_inputs"
        )
        or render_policy.get("derived_inputs")
        or "Inputs: {items}."
    )
    return _normalise_spaces(
        summary_template.format(items=joiner.join(rendered_items))
    )


def _render_semantic_program_answer(
    *,
    query: str,
    obligations: Sequence[Mapping[str, Any]],
    outputs: Mapping[str, Mapping[str, Any]],
    missing_ids: Sequence[str],
) -> str:
    """Render validated outputs without importing unselected evidence text."""

    render_policy = dict(
        CALCULATION_PROMPT_POLICY.get("semantic_program_render_templates") or {}
    )
    item_template = str(render_policy.get("item") or "{label}: {value}")
    korean_item_template = str(
        render_policy.get("item_sentence_ko")
        or item_template
    )
    narrative_template = str(render_policy.get("narrative") or "{text}")
    missing_template = str(
        render_policy.get("missing") or "Missing required evidence: {labels}"
    )
    common_scope = _common_rendered_obligation_scope(obligations, outputs)
    numeric_scopes_by_id, shared_numeric_scope = (
        _rendered_numeric_consolidation_scopes(obligations, outputs)
    )
    korean_surface = bool(
        re.search(
            str(render_policy.get("korean_text_pattern") or r"$^"),
            str(query or ""),
        )
    )
    answer_parts: List[str] = []
    contextual_numeric_rendered = False
    obligation_by_id = {
        str(item.get("obligation_id") or ""): item for item in obligations
    }

    for obligation in obligations:
        obligation_id = str(obligation.get("obligation_id") or "")
        output = outputs.get(obligation_id)
        if not output:
            continue
        if output.get("kind") == "narrative":
            text = _normalise_spaces(
                narrative_template.format(text=output.get("text") or "")
            )
            if text and not re.search(r"[.!?。]$", text):
                text = f"{text}."
            answer_parts.append(text)
            continue

        label = str(output.get("label") or obligation_id)
        value = str(output.get("rendered_value") or "")
        source_display = str(output.get("source_display_value") or "")
        if source_display and output.get("source_display_matches_formula") is False:
            comparison_template = str(
                render_policy.get(
                    "source_display_comparison_ko" if korean_surface
                    else "source_display_comparison"
                )
                or "{calculated} ({source})"
            )
            value = comparison_template.format(
                calculated=output.get("formula_rendered_value") or value,
                source=source_display,
            )
        if korean_surface:
            output_scope = numeric_scopes_by_id.get(obligation_id, "")
            subject_scope = dict(common_scope) if not contextual_numeric_rendered else {}
            if shared_numeric_scope and not contextual_numeric_rendered:
                subject_scope["consolidation_scope"] = shared_numeric_scope
            elif output_scope and not shared_numeric_scope:
                subject_scope["consolidation_scope"] = output_scope
            subject = _korean_semantic_output_subject(
                label=label,
                common_scope=subject_scope,
                render_policy=render_policy,
            )
            particle_subject = re.sub(r"\s*\([^()]*\)\s*$", "", subject)
            answer_parts.append(
                korean_item_template.format(
                    subject=subject,
                    topic_particle=topic_particle(particle_subject),
                    label=label,
                    value=value,
                )
            )
            contextual_numeric_rendered = True
        else:
            output_scope = numeric_scopes_by_id.get(obligation_id, "")
            displayed_scope = (
                shared_numeric_scope if not contextual_numeric_rendered else ""
            )
            if not shared_numeric_scope:
                displayed_scope = output_scope
            scope_label = _rendered_consolidation_scope_label(
                displayed_scope,
                korean=False,
            )
            scoped_label = _normalise_spaces(label)
            if scope_label and scope_label.casefold() not in scoped_label.casefold():
                scoped_label = _normalise_spaces(f"{scope_label} {scoped_label}")
            answer_parts.append(
                item_template.format(label=scoped_label or label, value=value)
            )
            contextual_numeric_rendered = True
        if output.get("kind") == "derived_value":
            input_summary = _render_derived_input_summary(
                output,
                render_policy=render_policy,
                korean_surface=korean_surface,
            )
            if input_summary:
                answer_parts.append(input_summary)

    if missing_ids:
        labels = [
            str(obligation_by_id[item].get("label") or item)
            for item in missing_ids
            if item in obligation_by_id
        ]
        answer_parts.append(missing_template.format(labels=", ".join(labels)))
    return _normalise_spaces(" ".join(str(item) for item in answer_parts if item))


def _fail_closed_semantic_validation(
    validation: Mapping[str, Any],
    *,
    code: str,
    detail: str,
    obligations: Sequence[Mapping[str, Any]],
) -> Dict[str, Any]:
    failed = dict(validation)
    failed["status"] = "invalid"
    failed["errors"] = [
        *[
            dict(item)
            for item in (validation.get("errors") or [])
            if isinstance(item, Mapping)
        ],
        {
            "code": code, "obligation_id": "", "detail": detail,
            "owner_id": "", "candidate_id": "",
            "location": "compilation_envelope", "repair_action": "repair_program",
        },
    ]
    failed["valid_direct_bindings"] = []
    failed["valid_expressions"] = []
    failed["valid_narrative_bindings"] = []
    failed["valid_source_assertions"] = []
    failed["selected_candidate_ids"] = []
    failed["source_candidate_ids_by_obligation"] = {}
    failed["inferred_units"] = {}
    failed["missing_obligation_ids"] = [
        str(item.get("obligation_id") or "")
        for item in obligations
        if bool(item.get("required", True))
        and str(item.get("obligation_id") or "")
    ]
    return failed


def execute_semantic_calculation_program(
    *,
    program: Mapping[str, Any],
    obligations: Sequence[Mapping[str, Any]],
    candidate_catalog: Sequence[Mapping[str, Any]],
    query: str,
    compilation_envelope: Optional[CompilationEnvelopeV2] = None,
    require_compilation_envelope: bool = False,
) -> Dict[str, Any]:
    """Execute only the validated subset and report completeness separately."""

    authority_error: Optional[Tuple[str, str]] = None
    candidate_visibility: Optional[CandidateVisibilityV1] = None
    if require_compilation_envelope and compilation_envelope is None:
        authority_error = (
            "visibility_mismatch",
            "compile-time visibility envelope is missing",
        )
    if compilation_envelope is not None and not isinstance(compilation_envelope, CompilationEnvelopeV2):
        authority_error = ("execution_content_mismatch", "a V2 compilation envelope is required")
        compilation_envelope = None
    if compilation_envelope is not None:
        candidate_visibility = compilation_envelope.visibility
        actual_catalog_fingerprint = semantic_candidate_catalog_fingerprint(
            candidate_catalog
        )
        if (
            actual_catalog_fingerprint
            != compilation_envelope.visibility.catalog_fingerprint
        ):
            authority_error = (
                "visibility_mismatch",
                "candidate catalog fingerprint changed after compilation",
            )
        elif not compilation_envelope.matches_execution_content(
            candidate_catalog=candidate_catalog, obligations=obligations, query=query,
        ):
            authority_error = (
                "execution_content_mismatch",
                "candidate content, obligations, or query changed after compilation",
            )
        elif not compilation_envelope.matches_program(program):
            authority_error = (
                "validation_drift",
                "semantic program changed after compile-time validation",
            )

    validation = {} if authority_error else validate_semantic_calculation_program(
        program=program,
        obligations=obligations,
        candidate_catalog=candidate_catalog,
        query=query,
        candidate_visibility=candidate_visibility,
        require_narrative_claims=require_compilation_envelope,
    )
    if (
        compilation_envelope is not None
        and authority_error is None
        and not compilation_envelope.matches_validation(validation)
    ):
        authority_error = (
            "validation_drift",
            "runtime validation differs from compile-time validation",
        )
    if authority_error is not None:
        validation = _fail_closed_semantic_validation(
            validation,
            code=authority_error[0],
            detail=authority_error[1],
            obligations=obligations,
        )
    obligation_rows = [dict(item) for item in obligations if isinstance(item, Mapping)]
    obligation_by_id = {
        str(item.get("obligation_id") or ""): item for item in obligation_rows
    }
    requirement_by_id = {
        str(requirement.get("requirement_id") or ""): dict(requirement)
        for obligation in obligation_rows
        for requirement in (obligation.get("evidence_requirements") or [])
        if isinstance(requirement, Mapping)
        and str(requirement.get("requirement_id") or "")
    }
    candidate_by_id = {
        str(item.get("candidate_id") or ""): dict(item)
        for item in candidate_catalog
        if isinstance(item, Mapping) and str(item.get("candidate_id") or "")
    }
    outputs: Dict[str, Dict[str, Any]] = {}
    direct_operand_by_obligation: Dict[str, Dict[str, Any]] = {}
    execution_errors: List[Dict[str, str]] = []

    for binding in validation["valid_direct_bindings"]:
        obligation_id = str(binding.get("obligation_id") or "")
        candidate_id = str(binding.get("candidate_id") or "")
        compatibility_ids = [
            str(item).strip()
            for item in (binding.get("compatibility_candidate_ids") or [])
            if str(item).strip() in candidate_by_id
        ]
        candidate = candidate_by_id[candidate_id]
        obligation = obligation_by_id[obligation_id]
        operand = project_semantic_program_operand(
            candidate,
            obligation_id=obligation_id,
            obligation=obligation,
            validated_binding=binding,
        )
        direct_operand_by_obligation[obligation_id] = operand
        slot = build_operand_value_slot(
            operand, default_role="primary_value", preserve_source_display=True
        )
        compatibility_candidates = [candidate_by_id[item] for item in compatibility_ids]
        source_row_ids = _clean_source_row_ids(
            [
                *list(operand.get("source_row_ids") or []),
                *[
                    value
                    for witness in compatibility_candidates
                    for value in (
                        witness.get("candidate_id"),
                        witness.get("source_row_id"),
                        witness.get("evidence_id"),
                        witness.get("source_candidate_id"),
                    )
                ],
            ]
        )
        outputs[obligation_id] = {
            "obligation_id": obligation_id,
            "kind": str(obligation.get("kind") or "direct_value"),
            "label": str(obligation.get("label") or obligation_id),
            "subject": str(operand.get("subject") or ""),
            "subject_source": str(operand.get("subject_source") or ""),
            "subject_source_row_ids": list(
                operand.get("subject_source_row_ids") or []
            ),
            "status": "ok",
            "value": candidate.get("normalized_value"),
            "normalized_value": candidate.get("normalized_value"),
            "normalized_unit": str(candidate.get("normalized_unit") or "UNKNOWN"),
            "result_unit": str(
                obligation.get("display_unit") or candidate.get("raw_unit") or ""
            ),
            "rendered_value": render_grounded_operand_display(operand),
            "candidate_ids": [candidate_id, *compatibility_ids],
            "compatibility_candidate_ids": compatibility_ids,
            "calculated_provenance": {
                "input_candidate_ids": [candidate_id],
                "source_row_ids": list(operand["source_row_ids"]),
                "source_anchors": [operand["source_anchor"]] if operand["source_anchor"] else [],
            },
            "source_row_ids": source_row_ids,
            "source_anchors": list(
                dict.fromkeys(
                    str(item.get("source_anchor") or "")
                    for item in [candidate, *compatibility_candidates]
                    if str(item.get("source_anchor") or "")
                )
            ),
            "answer_slot": slot,
            "operation_family": "lookup",
            **({"context_resolution": binding["context_resolution"]}
               if binding.get("context_resolution") else {}),
            **({"source_interpretation_resolution": binding["source_interpretation_resolution"]}
               if binding.get("source_interpretation_resolution") else {}),
        }

    for expression in validation["valid_expressions"]:
        obligation_id = str(expression.get("obligation_id") or "")
        obligation = obligation_by_id[obligation_id]
        env: Dict[str, float] = {}
        candidate_ids: List[str] = []
        source_row_ids: List[str] = []
        source_anchors: List[str] = []
        input_rows: List[Dict[str, Any]] = []
        unavailable = ""
        for binding in expression.get("variable_bindings") or []:
            source_id = str(binding.get("source_id") or "")
            operand = _project_expression_input(
                binding,
                candidate=candidate_by_id.get(source_id),
                obligation=(
                    requirement_by_id.get(str(binding.get("source_requirement_id") or ""))
                    or obligation
                ),
                source_output=outputs.get(source_id),
                source_operand=direct_operand_by_obligation.get(source_id),
            )
            if operand is None:
                unavailable = source_id
                break
            env[operand["variable"]] = operand["normalized_value"]
            input_rows.append(operand)
            if operand["source_kind"] == "candidate":
                candidate_ids.append(source_id)
                source_row_ids.extend(operand["source_row_ids"])
                source_anchors.extend(operand["source_anchors"])
            else:
                candidate_ids.extend(outputs[source_id].get("candidate_ids") or [])
                source_row_ids.extend(outputs[source_id].get("source_row_ids") or [])
                source_anchors.extend(outputs[source_id].get("source_anchors") or [])
        if unavailable:
            execution_errors.append(
                {
                    "code": "unavailable_expression_source",
                    "obligation_id": obligation_id,
                    "detail": unavailable,
                }
            )
            continue
        for compatibility_id in expression.get("compatibility_candidate_ids") or []:
            compatibility_id = str(compatibility_id or "").strip()
            if compatibility_id not in candidate_by_id:
                continue
            compatibility_candidate = candidate_by_id[compatibility_id]
            candidate_ids.append(compatibility_id)
            source_row_ids.extend(
                [
                    compatibility_id,
                    compatibility_candidate.get("source_row_id"),
                    compatibility_candidate.get("evidence_id"),
                    compatibility_candidate.get("source_candidate_id"),
                ]
            )
            source_anchors.append(
                str(compatibility_candidate.get("source_anchor") or "")
            )
        formula = str(expression.get("formula") or "")
        try:
            value = float(safe_eval_formula(formula, env))
        except ZeroDivisionError as exc:
            execution_errors.append(
                {"code": "zero_division", "obligation_id": obligation_id, "detail": str(exc)}
            )
            continue
        except Exception as exc:
            execution_errors.append(
                {
                    "code": "formula_execution_error",
                    "obligation_id": obligation_id,
                    "detail": str(exc),
                }
            )
            continue

        if not math.isfinite(value):
            execution_errors.append({
                "code": "non_finite_formula_result", "obligation_id": obligation_id,
                "detail": "formula result must be finite",
            })
            continue

        dimension = str(validation.get("inferred_units", {}).get(obligation_id) or "UNKNOWN")
        normalized_unit = "PERCENT" if dimension == "RATIO" else (
            "UNKNOWN" if dimension == "SCALAR" else dimension
        )
        display_unit = _expression_display_unit(expression, obligation, dimension)
        slot = build_calculated_value_slot(
            label=str(obligation.get("label") or obligation_id),
            normalized_value=value,
            normalized_unit=normalized_unit,
            display_unit=display_unit,
            source_row_ids=_clean_source_row_ids(source_row_ids),
            role="primary_value",
            source_anchor=next((item for item in source_anchors if item), ""),
        )
        rendered_value = str(slot.get("rendered_value") or "")
        formula_rendered_value = rendered_value
        display_id = str(expression.get("source_display_candidate_id") or "").strip()
        source_display_used = False
        source_display_value = ""
        source_display_normalized_value = None
        source_display_matches_formula = None
        if display_id in candidate_by_id:
            display_candidate = candidate_by_id[display_id]
            display_operand = project_semantic_program_operand(
                display_candidate,
                obligation_id=obligation_id,
                validated_binding={"context_resolution": expression.get("source_display_context_resolution"),
                    "source_interpretation_resolution": expression.get("source_display_interpretation_resolution")},
            )
            source_display_value = render_grounded_operand_display(display_operand)
            source_display_normalized_value = float(display_candidate["normalized_value"])
            source_display_matches_formula = _source_display_matches(display_candidate, value)
            # Display authority is independent of numerical equivalence. Dependencies
            # retain the calculated normalized_value, never the reported display value.
            candidate_ids.append(display_id)
            source_row_ids.extend(display_operand.get("source_row_ids") or [])
            source_anchors.append(str(display_candidate.get("source_anchor") or ""))
            if source_display_value:
                rendered_value = source_display_value
                slot = build_operand_value_slot(
                    {
                        **display_operand,
                        "label": str(obligation.get("label") or obligation_id),
                    },
                    default_role="primary_value",
                    preserve_source_display=True,
                )
                source_display_used = True
        operation_family = derive_operation_family_from_formula(formula)
        outputs[obligation_id] = {
            "obligation_id": obligation_id,
            "kind": "derived_value",
            "label": str(obligation.get("label") or obligation_id),
            "status": "ok",
            "value": value,
            "normalized_value": value,
            "normalized_unit": normalized_unit,
            "result_unit": display_unit,
            "rendered_value": rendered_value,
            "candidate_ids": list(dict.fromkeys(candidate_ids)),
            "source_row_ids": _clean_source_row_ids(source_row_ids),
            "source_anchors": list(dict.fromkeys(item for item in source_anchors if item)),
            "answer_slot": slot,
            "operation_family": operation_family,
            "formula": formula,
            "formula_result_value": value,
            "formula_rendered_value": formula_rendered_value,
            "calculated_value": value,
            "calculated_provenance": {
                "formula": formula,
                **{key: list(dict.fromkeys(item for row in input_rows for item in row[key]))
                   for key in ("input_candidate_ids", "source_row_ids", "source_anchors")},
            },
            "display_value": slot.get("normalized_value"),
            "display_provenance": {
                "source_display_candidate_id": display_id if source_display_used else None,
                "source_row_ids": list(slot.get("source_row_ids") or []),
            },
            "source_stated_result_used": source_display_used,
            "source_display_candidate_id": display_id,
            "source_display_value": source_display_value,
            "source_display_normalized_value": source_display_normalized_value,
            "source_display_matches_formula": source_display_matches_formula,
            **({"source_display_context_resolution": expression["source_display_context_resolution"]}
               if expression.get("source_display_context_resolution") else {}),
            **({"source_display_interpretation_resolution": expression["source_display_interpretation_resolution"]}
               if expression.get("source_display_interpretation_resolution") else {}),
            "input_rows": input_rows,
            **({"comparison_resolution": deepcopy(expression["comparison_resolution"])}
               if expression.get("comparison_resolution") else {}),
            **({"constant_resolutions": deepcopy(expression["constant_resolutions"])}
               if expression.get("constant_resolutions") else {}),
        }

    for binding in validation["valid_narrative_bindings"]:
        obligation_id = str(binding.get("obligation_id") or "")
        obligation = obligation_by_id[obligation_id]
        candidate_ids = [str(item) for item in binding.get("candidate_ids") or []]
        outputs[obligation_id] = {
            "obligation_id": obligation_id,
            "kind": "narrative",
            "label": str(obligation.get("label") or obligation_id),
            "status": "ok",
            "text": _normalise_spaces(str(binding.get("text") or "")),
            "candidate_ids": candidate_ids,
            "source_row_ids": _clean_source_row_ids(
                [
                    [
                        candidate_by_id[item].get("candidate_id"),
                        candidate_by_id[item].get("source_row_id"),
                        candidate_by_id[item].get("evidence_id"),
                    ]
                    for item in candidate_ids
                    if item in candidate_by_id
                ]
            ),
            "source_anchors": list(
                dict.fromkeys(
                    str(candidate_by_id[item].get("source_anchor") or "")
                    for item in candidate_ids
                    if item in candidate_by_id
                    and str(candidate_by_id[item].get("source_anchor") or "")
                )
            ),
            "operation_family": "narrative",
            **({"description_readings": deepcopy(binding["description_readings"])}
               if binding.get("description_readings") else {}),
            **({"claim_readings": deepcopy(binding["claim_readings"])}
               if binding.get("claim_readings") else {}),
        }

    required_ids = [
        str(item.get("obligation_id") or "")
        for item in obligation_rows
        if bool(item.get("required", True)) and str(item.get("obligation_id") or "")
    ]
    missing_ids = [item for item in required_ids if item not in outputs]
    if (
        not missing_ids
        and not execution_errors
        and validation.get("status") == "ready"
    ):
        status = "ok"
    elif outputs:
        status = "partial"
    else:
        status = "incomplete"

    numeric_outputs = [
        outputs[str(obligation.get("obligation_id") or "")]
        for obligation in obligation_rows
        if str(obligation.get("obligation_id") or "") in outputs
        and outputs[str(obligation.get("obligation_id") or "")].get("kind")
        != "narrative"
    ]
    primary = numeric_outputs[0] if numeric_outputs else {}
    selected_candidate_ids = list(
        dict.fromkeys(
            candidate_id
            for output in outputs.values()
            for candidate_id in output.get("candidate_ids") or []
        )
    )
    direct_binding_by_candidate_id: Dict[str, Dict[str, Any]] = {}
    for binding in validation.get("valid_direct_bindings") or []:
        candidate_id = str(binding.get("candidate_id") or "")
        if candidate_id and candidate_id not in direct_binding_by_candidate_id:
            direct_binding_by_candidate_id[candidate_id] = dict(binding)
    expression_operand_by_candidate_id: Dict[str, Dict[str, Any]] = {}
    for output in outputs.values():
        for row in output.get("input_rows") or []:
            candidate_id = str(row.get("candidate_id") or "")
            if candidate_id and candidate_id not in expression_operand_by_candidate_id:
                expression_operand_by_candidate_id[candidate_id] = dict(row)
    display_obligation_by_candidate_id: Dict[str, str] = {}
    display_binding_by_candidate_id: Dict[str, Dict[str, Any]] = {}
    for expression in validation.get("valid_expressions") or []:
        candidate_id = str(
            expression.get("source_display_candidate_id") or ""
        ).strip()
        obligation_id = str(expression.get("obligation_id") or "")
        if candidate_id and candidate_id not in display_obligation_by_candidate_id:
            display_obligation_by_candidate_id[candidate_id] = obligation_id
            display_binding_by_candidate_id[candidate_id] = {
                "context_resolution": expression.get("source_display_context_resolution"),
                "source_interpretation_resolution": expression.get("source_display_interpretation_resolution")}
    operands: List[Dict[str, Any]] = []
    description_only_ids = narrative_description_only_ids(validation)
    for candidate_id in selected_candidate_ids:
        candidate = candidate_by_id.get(candidate_id)
        if not candidate or candidate.get("kind") != "numeric" or candidate_id in description_only_ids:
            continue
        binding = direct_binding_by_candidate_id.get(candidate_id)
        obligation_id = str((binding or {}).get("obligation_id") or "")
        if not binding and candidate_id in expression_operand_by_candidate_id:
            operands.append(dict(expression_operand_by_candidate_id[candidate_id]))
            continue
        if not obligation_id:
            obligation_id = display_obligation_by_candidate_id.get(candidate_id, "")
            binding = display_binding_by_candidate_id.get(candidate_id)
        operands.append(
            project_semantic_program_operand(
                candidate,
                obligation_id=obligation_id,
                obligation=obligation_by_id.get(obligation_id),
                validated_binding=binding,
            )
        )
    primary_operation = str(primary.get("operation_family") or "formula")
    primary_slot = dict(primary.get("answer_slot") or {})
    calculation_result = {
        "status": "ok" if status == "ok" else "insufficient_operands",
        "semantic_status": status,
        "ledger_integrity_status": "ok",
        "result_value": primary_slot.get("normalized_value", primary.get("normalized_value")),
        "calculated_result_value": primary.get("normalized_value"),
        "result_unit": str(primary.get("result_unit") or ""),
        "rendered_value": str(primary.get("rendered_value") or ""),
        "series": [],
        "answer_slots": (
            {
                "operation_family": (
                    "lookup" if primary_operation == "lookup" else "single_value"
                ),
                "metric_label": str(primary.get("label") or ""),
                "primary_value": primary_slot,
                "components_by_role": {},
                "components_by_group": {},
                "source_row_ids": _clean_source_row_ids(
                    primary.get("source_row_ids") or []
                ),
            }
            if primary
            else {}
        ),
        "derived_metrics": {
            "operation_family": primary_operation,
            "semantic_outputs": list(outputs.values()),
            "required_obligation_ids": required_ids,
            "missing_obligation_ids": missing_ids,
        },
        "source_row_ids": _clean_source_row_ids(
            [output.get("source_row_ids") for output in outputs.values()]
        ),
        "source_evidence_ids": selected_candidate_ids,
        "explanation": str(program.get("rationale") or ""),
        "outputs": list(outputs.values()),
        "validation": validation,
        "execution_errors": execution_errors,
    }
    return {
        "status": status,
        "outputs": list(outputs.values()),
        "outputs_by_obligation": outputs,
        "missing_obligation_ids": missing_ids,
        "selected_candidate_ids": selected_candidate_ids,
        "calculation_operands": operands,
        "calculation_result": calculation_result,
        "validation": validation,
        "execution_errors": execution_errors,
    }


def assemble_semantic_execution_result(
    *, execution: Mapping[str, Any], obligations: Sequence[Mapping[str, Any]],
    calculation_plan: Mapping[str, Any], query: str,
) -> Dict[str, Any]:
    """Pure final-assembly projection; numeric execution never writes an answer."""

    outputs = deepcopy(dict(execution.get("outputs_by_obligation") or {}))
    answer = _render_semantic_program_answer(
        query=query, obligations=obligations, outputs=outputs,
        missing_ids=list(execution.get("missing_obligation_ids") or []),
    )
    result = deepcopy(dict(execution.get("calculation_result") or {}))
    operation = str(dict(result.get("derived_metrics") or {}).get("operation_family") or "formula")
    result.update(formatted_result=answer, operation_family=operation)
    plan = deepcopy(dict(calculation_plan))
    plan["operation_family"] = operation
    trace = {
        "calculation_operands": deepcopy(list(execution.get("calculation_operands") or [])),
        "calculation_plan": plan,
        "calculation_result": result,
    }
    rows = []
    for output in outputs.values():
        obligation_id = str(output.get("obligation_id") or "")
        family = str(output.get("operation_family") or "formula")
        slot = dict(output.get("answer_slot") or {})
        rows.append({
            "task_id": f"task_1:{obligation_id}", "metric_family": "semantic_program",
            "metric_label": str(output.get("label") or obligation_id),
            "operation_family": family, "status": str(output.get("status") or "ok"),
            "answer": _normalise_spaces(str(output.get("text") or "") if output.get("kind") == "narrative"
                else f"{output.get('label') or obligation_id}: {output.get('rendered_value') or ''}"),
            "calculation_result": {
                "status": str(output.get("status") or "ok"), "operation_family": family,
                "result_value": slot.get("normalized_value", output.get("normalized_value")),
                "calculated_result_value": output.get("normalized_value"),
                "result_unit": str(output.get("result_unit") or ""),
                "rendered_value": str(output.get("rendered_value") or ""),
                "answer_slots": {"operation_family": "lookup" if family == "lookup" else "single_value",
                    "metric_label": str(output.get("label") or obligation_id), "primary_value": slot} if slot else {},
                "derived_metrics": {"operation_family": family},
                "source_row_ids": list(output.get("source_row_ids") or []),
            },
            "source_row_ids": list(output.get("source_row_ids") or []),
            "source_evidence_ids": list(output.get("candidate_ids") or []),
        })
    structured_result = {
        "status": str(execution.get("status") or "incomplete"),
        "answer": answer, "final_answer": answer, "subtask_results": rows,
        "answer_obligations": deepcopy(list(obligations)),
        "missing_obligation_ids": list(execution.get("missing_obligation_ids") or []),
        "resolved_calculation_trace": trace,
    }
    return {"answer": answer, "structured_result": structured_result,
        "resolved_calculation_trace": trace, "subtask_results": rows}
