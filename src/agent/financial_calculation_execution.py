"""Validate and execute grounded semantic calculation programs."""

from __future__ import annotations

import ast
import hashlib
import json
import math
import re
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from src.agent.financial_candidate_matching import (
    build_candidate_matches,
    select_source_defined_physical_row_group,
)
from src.agent.financial_answer_slots import (
    build_calculated_value_slot,
    build_operand_value_slot,
)
from src.agent.financial_formula_eval import safe_eval_formula
from src.agent.financial_graph_calculation_rendering import (
    render_grounded_operand_display,
)
from src.agent.financial_row_surfaces import strip_financial_label_annotations
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


_ALLOWED_FUNCTIONS = {"min", "max", "abs", "round", "log", "exp"}
_NEUTRAL_CONSTANTS = {0.0, 1.0, 100.0}
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
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return float(node.value)
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
    function_names = {
        current.func.id
        for current in ast.walk(node)
        if isinstance(current, ast.Call) and isinstance(current.func, ast.Name)
    }
    return {
        current.id
        for current in ast.walk(node)
        if isinstance(current, ast.Name) and current.id not in function_names
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
        if isinstance(current, ast.Constant) and not isinstance(
            current.value, (int, float)
        ):
            return False
        if isinstance(current, ast.Call):
            if not isinstance(current.func, ast.Name):
                return False
            if current.func.id not in _ALLOWED_FUNCTIONS or current.keywords:
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


def _query_constants(query: str) -> List[float]:
    values: List[float] = []
    for token in re.findall(r"[-+]?\d[\d,]*(?:\.\d+)?", str(query or "")):
        try:
            values.append(float(token.replace(",", "")))
        except ValueError:
            continue
    return values


def _constant_allowed(
    value: float,
    declarations: Sequence[Mapping[str, Any]],
    *,
    query_values: Sequence[float],
    binding_count: int,
) -> bool:
    if float(value) in _NEUTRAL_CONSTANTS:
        return True
    for declaration in declarations:
        try:
            declared = float(declaration.get("value"))
        except (TypeError, ValueError):
            continue
        if abs(declared - float(value)) > 1e-12:
            continue
        origin = str(declaration.get("origin") or "").strip().lower()
        if origin == "query" and any(
            abs(candidate - value) <= 1e-12 for candidate in query_values
        ):
            return True
        if (
            origin == "deterministic_cardinality"
            and float(value).is_integer()
            and int(value) == int(binding_count)
        ):
            return True
    return False


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


def _result_unit_valid(result_unit: str, dimension: str) -> bool:
    cleaned = _normalise_spaces(str(result_unit or ""))
    if not cleaned:
        return dimension in {"SCALAR", "RATIO", "UNKNOWN"}
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
        for value in (candidate.get("row_label"), *raw_row_headers):
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


def _period_scope_matches(expected: str, candidate: Mapping[str, Any]) -> bool:
    wanted = _normalise_spaces(str(expected or "")).lower()
    if not wanted or wanted == "unknown":
        return True

    observed = _normalise_spaces(str(candidate.get("period") or "")).lower()
    if observed and _scope_surface_matches(wanted, observed):
        return True

    expected_years = set(re.findall(r"(?<!\d)(?:19|20)\d{2}(?!\d)", wanted))
    if not expected_years:
        return _scope_matches(wanted, observed, candidate)

    explicit_surfaces = [
        observed,
        *[
            _normalise_spaces(str(item)).lower()
            for item in (candidate.get("column_headers") or [])
            if _normalise_spaces(str(item))
        ],
    ]
    explicit_years = {
        year
        for surface in explicit_surfaces
        for year in re.findall(r"(?<!\d)(?:19|20)\d{2}(?!\d)", surface)
    }
    if explicit_years:
        return bool(expected_years & explicit_years)

    value_year = _normalise_spaces(str(candidate.get("value_year") or ""))
    if value_year:
        return value_year in expected_years

    value_role = _normalise_spaces(str(candidate.get("value_role") or "")).lower()
    prior_role = any(
        marker in value_role
        for marker in ("prior", "previous", "opening", "begin")
    )
    if prior_role:
        return False

    has_opaque_numeric_period = any(
        re.search(r"\d", surface) for surface in explicit_surfaces if surface
    )
    current_role = any(
        marker in value_role
        for marker in ("current", "closing", "ending", "end")
    )
    if has_opaque_numeric_period and not current_role:
        return False

    context_surface = _normalise_spaces(
        " ".join(
            str(candidate.get(key) or "")
            for key in ("year", "source_anchor")
        )
    ).lower()
    return any(year in context_surface for year in expected_years)


def _scope_errors(
    candidate: Mapping[str, Any],
    obligation: Mapping[str, Any],
    *,
    include_basis: bool = True,
    applicable_unknown_fields: Sequence[str] = (),
    conflicts_only: bool = False,
) -> List[str]:
    scope = dict(obligation.get("scope") or {})
    applicable = {
        str(field).strip()
        for field in applicable_unknown_fields
        if str(field).strip() in _NARRATIVE_SCOPE_APPLICABILITY_FIELDS
    }
    checks = ["company", "consolidation_scope", "segment"]
    if include_basis:
        checks.append("basis")
    errors: List[str] = []
    for field in checks:
        state = _scope_match_state(field, scope.get(field), candidate)
        if conflicts_only and state != "conflict":
            continue
        if state == "match" or (state == "unknown" and field in applicable):
            continue
        errors.append(f"scope mismatch: {field}")
    period_state = _scope_match_state("period", scope.get("period"), candidate)
    if period_state != "match" and (not conflicts_only or period_state == "conflict"):
        errors.append("scope mismatch: period")
    return errors


def _evidence_requirement_scope_conflicts(
    obligation: Mapping[str, Any],
    requirement: Mapping[str, Any],
) -> List[str]:
    """Return non-period scope fields where an input contradicts its output."""

    output_scope = dict(obligation.get("scope") or {})
    input_scope = dict(requirement.get("scope") or {})
    conflicts: List[str] = []
    for field in ("company", "consolidation_scope", "segment", "basis"):
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
    for field in ("evidence_id", "table_source_id", "context_fingerprint"):
        left = _normalise_spaces(str(candidate.get(field) or ""))
        right = _normalise_spaces(str(witness.get(field) or ""))
        if left and right and left == right:
            return True
    left_anchor = _normalise_spaces(str(candidate.get("source_anchor") or ""))
    right_anchor = _normalise_spaces(str(witness.get("source_anchor") or ""))
    return bool(left_anchor and left_anchor == right_anchor)


def _direct_scope_gap_is_bridgeable(
    candidate: Mapping[str, Any], detail: str
) -> bool:
    field = str(detail or "").rsplit(":", 1)[-1].strip()
    if field == "period":
        explicit_surfaces = [
            _normalise_spaces(str(candidate.get("period") or "")),
            *[
                _normalise_spaces(str(item))
                for item in (candidate.get("column_headers") or [])
                if _normalise_spaces(str(item))
            ],
        ]
        explicit_years = {
            year
            for surface in explicit_surfaces
            for year in re.findall(r"(?<!\d)(?:19|20)\d{2}(?!\d)", surface)
        }
        return not explicit_years and not candidate.get("value_year")
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
        if _period_scope_matches(wanted, candidate):
            return "match"
        explicit_year = candidate.get("value_year") or candidate.get("year")
        period_surface = _normalise_spaces(
            " ".join(
                [
                    str(candidate.get("period") or ""),
                    *[str(item) for item in (candidate.get("column_headers") or [])],
                ]
            )
        )
        if explicit_year not in (None, "") or re.search(
            r"(?<!\d)(?:19|20)\d{2}(?!\d)", period_surface
        ):
            return "conflict"
        return "unknown"

    actual = _normalise_spaces(str(candidate.get(field) or "")).lower()
    if actual and actual != "unknown":
        return "match" if _scope_surface_matches(wanted, actual) else "conflict"
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
        states = [_scope_match_state(field, expected, candidate) for candidate in candidates]
        if "conflict" in states or (
            "match" not in states and field not in applicable
        ):
            errors.append(f"scope mismatch: {field}")
    return errors


def _expression_context_conflicts(
    candidates: Sequence[Mapping[str, Any]],
) -> List[str]:
    """Return semantic context fields that disagree across formula inputs."""

    conflicts: List[str] = []
    for field in (
        "company",
        "consolidation_scope",
        "segment",
        "basis",
        "context_fingerprint",
    ):
        values = {
            _normalise_spaces(str(candidate.get(field) or "")).lower()
            for candidate in candidates
            if _normalise_spaces(str(candidate.get(field) or "")).lower()
            not in {"", "unknown"}
        }
        if len(values) > 1:
            conflicts.append(field)
    return conflicts


def _declared_cross_period_context_is_compatible(
    *,
    candidate_requirement_bindings: Sequence[
        Tuple[Mapping[str, Any], Mapping[str, Any]]
    ],
    numeric_context_candidates: Sequence[Mapping[str, Any]],
    obligation: Mapping[str, Any],
    source_display_candidate: Optional[Mapping[str, Any]] = None,
) -> bool:
    """Allow context identity to vary only across declared period inputs.

    A comparison across periods is not a semantic-context mix when every
    physical input is bound to its own explicitly scoped requirement and the
    candidates remain context-consistent inside each period partition. Other
    scope dimensions and undeclared/dependency sources remain fail-closed.
    """

    bindings = [
        (dict(candidate), dict(requirement))
        for candidate, requirement in candidate_requirement_bindings
        if isinstance(candidate, Mapping) and isinstance(requirement, Mapping)
    ]
    if len(bindings) < 2:
        return False

    contexts_by_period: Dict[str, List[Dict[str, Any]]] = {}
    bound_candidate_ids: set[str] = set()
    for candidate, requirement in bindings:
        requirement_scope = dict(requirement.get("scope") or {})
        period = _normalise_spaces(
            str(requirement_scope.get("period") or "")
        ).lower()
        if period in {"", "unknown"}:
            return False
        if _scope_match_state("period", period, candidate) != "match":
            return False
        candidate_id = str(candidate.get("candidate_id") or "").strip()
        if not candidate_id:
            return False
        bound_candidate_ids.add(candidate_id)
        contexts_by_period.setdefault(period, []).append(candidate)

    if len(contexts_by_period) < 2:
        return False

    for field in ("company", "consolidation_scope", "segment", "basis"):
        declared_values = {
            _normalise_spaces(
                str(dict(requirement.get("scope") or {}).get(field) or "")
            ).lower()
            for _candidate, requirement in bindings
            if _normalise_spaces(
                str(dict(requirement.get("scope") or {}).get(field) or "")
            ).lower()
            not in {"", "unknown"}
        }
        if len(declared_values) > 1:
            return False

    for candidates in contexts_by_period.values():
        fingerprints = {
            _normalise_spaces(str(candidate.get("context_fingerprint") or "")).lower()
            for candidate in candidates
            if _normalise_spaces(
                str(candidate.get("context_fingerprint") or "")
            ).lower()
            not in {"", "unknown"}
        }
        if len(fingerprints) > 1:
            return False

    display_id = ""
    if source_display_candidate is not None:
        display_id = str(
            source_display_candidate.get("candidate_id") or ""
        ).strip()
    allowed_candidate_ids = set(bound_candidate_ids)
    if display_id:
        allowed_candidate_ids.add(display_id)
    context_candidate_ids = {
        str(candidate.get("candidate_id") or "").strip()
        for candidate in numeric_context_candidates
        if str(candidate.get("candidate_id") or "").strip()
    }
    if not context_candidate_ids or not context_candidate_ids.issubset(
        allowed_candidate_ids
    ):
        return False

    if source_display_candidate is not None:
        output_period = _normalise_spaces(
            str(dict(obligation.get("scope") or {}).get("period") or "")
        ).lower()
        if output_period in {"", "unknown"}:
            return False
        if (
            _scope_match_state(
                "period",
                output_period,
                source_display_candidate,
            )
            != "match"
        ):
            return False
        same_period_inputs = contexts_by_period.get(output_period, [])
        if not same_period_inputs or not any(
            _same_source_context(source_display_candidate, candidate)
            for candidate in same_period_inputs
        ):
            return False

    return True


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


def validate_semantic_calculation_program(
    *,
    program: Mapping[str, Any],
    obligations: Sequence[Mapping[str, Any]],
    candidate_catalog: Sequence[Mapping[str, Any]],
    query: str,
    candidate_visibility: Optional[CandidateVisibilityV1] = None,
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

    def candidate_is_exposed(candidate_id: str, owner_id: str) -> bool:
        if selectable_ids_by_owner is not None:
            return candidate_id in selectable_ids_by_owner.get(owner_id, set())
        return selectable_ids is None or candidate_id in selectable_ids

    if len(obligation_by_id) != len(obligation_rows):
        error("duplicate_or_missing_obligation_id")
    if not obligation_rows:
        error("missing_answer_obligations")
    if len(candidate_by_id) != len(candidate_rows):
        error("duplicate_or_missing_candidate_id")

    requirement_by_id: Dict[str, Dict[str, Any]] = {}
    requirement_owner_by_id: Dict[str, str] = {}
    requirement_count = 0
    invalid_evidence_obligation_ids: set[str] = set()
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

    def candidate_has_semantic_conflict(
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
                row_id: semantic_candidate_applicability(candidate, owner)
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

    def already_produced(obligation_id: str) -> bool:
        if obligation_id in produced:
            error("duplicate_obligation_output", obligation_id)
            return True
        return False

    for raw in program.get("direct_bindings") or []:
        binding = dict(raw or {})
        obligation_id = str(binding.get("obligation_id") or "").strip()
        candidate_id = str(binding.get("candidate_id") or "").strip()
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
        if candidate and obligation and candidate_has_semantic_conflict(
            candidate_id,
            obligation_id,
        ):
            error("candidate_semantic_target_mismatch", obligation_id, candidate_id,
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
                    for detail in _scope_errors(witness, obligation, include_basis=False)
                    if detail.endswith(("company", "period"))
                ]
                if hard_errors:
                    for detail in hard_errors:
                        error("compatibility_scope_mismatch", obligation_id, detail,
                              candidate_id=str(witness.get("candidate_id") or ""),
                              location="compatibility_binding",
                              repair_action="replace_candidate" if detail in _scope_errors(witness, obligation, include_basis=False, conflicts_only=True) else "repair_program")
                    invalid = True
                    compatibility_ready = False
                    break
        if obligation and candidate:
            subject_checked = (
                str(obligation.get("kind") or "") == "direct_value"
                and str(candidate.get("kind") or "") == "numeric"
                and _candidate_has_finite_numeric_value(candidate)
            )
            if subject_checked:
                subject_resolution = _direct_subject_resolution(candidate, obligation)
            subject_state = str(subject_resolution.get("state") or "unknown")
            subject_bridge_ready = (
                compatibility_ready
                and subject_state == "unknown"
                and any(
                    _scope_match_state(
                        "segment",
                        (obligation.get("scope") or {}).get("segment"),
                        witness,
                    )
                    == "match"
                    for witness in compatibility_candidates
                )
            )
            if subject_bridge_ready:
                subject_resolution = {
                    "state": "match",
                    "subject": _normalise_spaces(
                        str((obligation.get("scope") or {}).get("segment") or "")
                    ),
                    "source": "compatibility_evidence",
                    "source_row_ids": _clean_source_row_ids(
                        [
                            value
                            for witness in compatibility_candidates
                            for value in (
                                witness.get("candidate_id"),
                                witness.get("source_row_id"),
                                witness.get("evidence_id"),
                                witness.get("source_candidate_id"),
                            )
                        ]
                    ),
                }
            if subject_checked and subject_state != "match" and not subject_bridge_ready:
                error("candidate_subject_mismatch", obligation_id, "segment",
                      candidate_id=candidate_id, location="direct_binding",
                      repair_action="replace_candidate" if subject_state == "conflict" else "repair_program")
                invalid = True
            scope_details = _scope_errors(candidate, obligation)
            if subject_checked and subject_state == "match":
                scope_details = [
                    detail
                    for detail in scope_details
                    if not detail.endswith("segment")
                ]
            if compatibility_ready:
                scope_details = [
                    detail
                    for detail in scope_details
                    if not _direct_scope_gap_is_bridgeable(candidate, detail)
                ]
            for detail in scope_details:
                error("candidate_scope_mismatch", obligation_id, detail,
                      candidate_id=candidate_id, location="direct_binding",
                      repair_action="replace_candidate" if detail in _scope_errors(candidate, obligation, conflicts_only=True) else "repair_program")
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
            if display_unit and not _result_unit_valid(
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

    pending = [dict(item or {}) for item in (program.get("expressions") or [])]
    seen_expression_ids: set[str] = set()
    for expression in pending:
        obligation_id = str(expression.get("obligation_id") or "").strip()
        if obligation_id in seen_expression_ids:
            error("duplicate_expression_output", obligation_id)
        seen_expression_ids.add(obligation_id)

    query_values = _query_constants(query)
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
            source_ids = [str(item.get("source_id") or "").strip() for item in bindings]
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
            declarations = [dict(item or {}) for item in expression.get("constants") or []]
            if not invalid:
                for value in _formula_constants(body):
                    if not _constant_allowed(
                        value,
                        declarations,
                        query_values=query_values,
                        binding_count=len(bindings),
                    ):
                        error("undeclared_formula_constant", obligation_id, repr(value))
                        invalid = True
                        break

            variable_units: Dict[str, str] = {}
            source_candidates: List[str] = []
            bound_requirement_ids: set[str] = set()
            candidate_requirement_bindings: List[
                Tuple[Mapping[str, Any], Mapping[str, Any]]
            ] = []
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
                            if candidate_has_semantic_conflict(
                                source_id,
                                source_requirement_id,
                            ):
                                error(
                                    "candidate_semantic_target_mismatch",
                                    obligation_id,
                                    f"{source_requirement_id}: {source_id}",
                                    owner_id=source_requirement_id, candidate_id=source_id,
                                    location="expression_input", repair_action="replace_candidate",
                                )
                                invalid = True
                            bound_requirement_ids.add(source_requirement_id)
                            candidate_requirement_bindings.append(
                                (candidate, requirement)
                            )
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
                                    repair_action="replace_candidate" if detail in _scope_errors(candidate, {"scope": dict(requirement.get("scope") or {})}, conflicts_only=True) else "repair_program",
                                )
                                invalid = True
                        variable_units[variable] = _candidate_dimension(candidate)
                        source_candidates.append(source_id)
                    else:
                        if source_requirement_id:
                            error(
                                "unexpected_source_requirement_id",
                                obligation_id,
                                source_requirement_id,
                            )
                            invalid = True
                        variable_units[variable] = output_units[source_id]
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
            result_unit = str(
                expression.get("display_unit")
                or expression.get("result_unit")
                or (obligation or {}).get("display_unit")
                or ""
            )
            declared_result_unit = str(expression.get("result_unit") or "")
            if declared_result_unit and not _result_unit_valid(declared_result_unit, dimension):
                error("result_unit_mismatch", obligation_id, f"{dimension} -> {declared_result_unit}",
                      location="expression.result_unit")
                continue
            if not _result_unit_valid(result_unit, dimension):
                error("result_unit_mismatch", obligation_id, f"{dimension} -> {result_unit}")
                continue
            display_candidate: Optional[Mapping[str, Any]] = None
            display_id = str(expression.get("source_display_candidate_id") or "").strip()
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
                display_scope_errors = _scope_errors(
                    display_candidate,
                    obligation or {},
                    include_basis=False,
                )
                if display_scope_errors:
                    for detail in display_scope_errors:
                        error("source_display_scope_mismatch", obligation_id, detail,
                              candidate_id=display_id, location="source_display",
                              repair_action="replace_candidate" if detail in _scope_errors(display_candidate, obligation or {}, include_basis=False, conflicts_only=True) else "repair_program")
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
                numeric_context_candidates
            )
            if (
                context_conflicts == ["context_fingerprint"]
                and obligation
                and _declared_cross_period_context_is_compatible(
                    candidate_requirement_bindings=candidate_requirement_bindings,
                    numeric_context_candidates=numeric_context_candidates,
                    obligation=obligation,
                    source_display_candidate=display_candidate,
                )
            ):
                context_conflicts = []
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
        obligation = obligation_by_id.get(obligation_id)
        candidate_ids = [
            str(item).strip()
            for item in (binding.get("candidate_ids") or [])
            if str(item).strip()
        ]
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
                and candidate_has_semantic_conflict(candidate_id, obligation_id)
            ),
            "",
        )
        if semantic_conflict_id:
            error(
                "candidate_semantic_target_mismatch",
                obligation_id,
                semantic_conflict_id,
            )
            invalid = True
        text = _normalise_spaces(str(binding.get("text") or ""))
        if not text:
            error("empty_narrative_output", obligation_id)
            invalid = True
        ungrounded_numbers = (
            _ungrounded_narrative_numbers(text, selected) if text and selected else []
        )
        if ungrounded_numbers:
            error(
                "ungrounded_narrative_number",
                obligation_id,
                ", ".join(ungrounded_numbers),
            )
            invalid = True
        if obligation:
            for detail in _collective_narrative_scope_errors(
                selected,
                obligation,
                applicable_unknown_fields=scope_applicability_fields,
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
                if candidate_has_semantic_conflict(candidate_id, requirement_id):
                    error(
                        "candidate_semantic_target_mismatch",
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
                ):
                    error(
                        "candidate_requirement_scope_mismatch",
                        obligation_id,
                        f"{requirement_id}: {detail}",
                        owner_id=requirement_id, candidate_id=candidate_id,
                        location="narrative_input",
                        repair_action="replace_candidate" if detail in _scope_errors(candidate, {"scope": dict(requirement.get("scope") or {})}, conflicts_only=True) else "repair_program",
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

    coupling_groups: Dict[str, List[str]] = {}
    for obligation_id, obligation in obligation_by_id.items():
        coupling_key = _normalise_spaces(str(obligation.get("coupling_key") or ""))
        if (
            coupling_key
            and obligation_id in produced
            and str(obligation.get("kind") or "") != "narrative"
        ):
            coupling_groups.setdefault(coupling_key, []).append(obligation_id)
    invalid_coupled: set[str] = set()
    for coupling_key, obligation_ids in coupling_groups.items():
        if len(obligation_ids) < 2:
            continue
        source_candidate_ids_by_obligation = {
            obligation_id: [
                candidate_id
                for candidate_id in sources_by_output.get(obligation_id, [])
                if candidate_id in candidate_by_id
                and candidate_id
                not in set(
                    compatibility_sources_by_output.get(obligation_id, [])
                )
            ]
            for obligation_id in obligation_ids
        }
        contexts_by_obligation = {
            obligation_id: frozenset(
                _normalise_spaces(
                    str(
                        candidate_by_id[candidate_id].get(
                            "context_fingerprint"
                        )
                        or ""
                    )
                )
                for candidate_id in candidate_ids
                if _normalise_spaces(
                    str(
                        candidate_by_id[candidate_id].get(
                            "context_fingerprint"
                        )
                        or ""
                    )
                )
            )
            for obligation_id, candidate_ids in (
                source_candidate_ids_by_obligation.items()
            )
        }
        missing_context = any(
            not _normalise_spaces(
                str(
                    candidate_by_id[candidate_id].get("context_fingerprint")
                    or ""
                )
            )
            for candidate_ids in source_candidate_ids_by_obligation.values()
            for candidate_id in candidate_ids
        )
        compatibility_witnesses = {
            candidate_id
            for obligation_id in obligation_ids
            for candidate_id in compatibility_sources_by_output.get(obligation_id, [])
            if candidate_id in candidate_by_id
        }
        if missing_context and not compatibility_witnesses:
            for obligation_id in obligation_ids:
                error("coupled_context_missing", obligation_id, coupling_key)
                invalid_coupled.add(obligation_id)
        elif (
            len(set(contexts_by_obligation.values())) > 1
            and not compatibility_witnesses
        ):
            for obligation_id in obligation_ids:
                error("coupled_context_mismatch", obligation_id, coupling_key)
                invalid_coupled.add(obligation_id)
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
    for obligation_id in produced:
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
        related_obligation_ids = list(
            dict.fromkeys(
                obligation_id
                for candidate_id in candidate_ids
                for obligation_id in selected_obligations_by_candidate.get(
                    candidate_id, []
                )
            )
        )

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
            for obligation_id in produced
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
    obligation_row = dict(obligation or {})
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
        "normalized_value": candidate.get("normalized_value"),
        "normalized_unit": str(candidate.get("normalized_unit") or "UNKNOWN"),
        "period": str(candidate.get("period") or ""),
        "source_period_surface": str(
            candidate.get("source_period_surface") or ""
        ),
        "period_source": str(candidate.get("period_source") or ""),
        "value_year": candidate.get("value_year"),
        "table_source_id": str(candidate.get("table_source_id") or ""),
        "statement_type": str(candidate.get("statement_type") or ""),
        "consolidation_scope": str(candidate.get("consolidation_scope") or ""),
        "consolidation_scope_source": str(
            candidate.get("consolidation_scope_source") or ""
        ),
        "value_role": str(candidate.get("value_role") or ""),
        "aggregation_stage": str(candidate.get("aggregation_stage") or ""),
        "aggregate_label": str(candidate.get("aggregate_label") or ""),
        "matched_operand_role": obligation_id,
    }


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
    """Render source-visible operands used by one derived output."""

    item_template = str(
        render_policy.get("derived_input_item") or "{label} {value}"
    )
    joiner = str(render_policy.get("derived_input_joiner") or ", ")
    rendered_items: List[str] = []
    for raw_row in output.get("input_rows") or []:
        if not isinstance(raw_row, Mapping):
            continue
        row = dict(raw_row)
        value = render_grounded_operand_display(row)
        if not value:
            continue
        label = _normalise_spaces(
            str(
                row.get("row_label")
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
            str(row.get("source_period_surface") or row.get("period") or "")
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
    candidate_by_id = {
        str(item.get("candidate_id") or ""): dict(item)
        for item in candidate_catalog
        if isinstance(item, Mapping) and str(item.get("candidate_id") or "")
    }
    outputs: Dict[str, Dict[str, Any]] = {}
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
            variable = str(binding.get("variable") or "")
            source_id = str(binding.get("source_id") or "")
            if source_id in candidate_by_id:
                candidate = candidate_by_id[source_id]
                try:
                    env[variable] = float(candidate.get("normalized_value"))
                except (TypeError, ValueError):
                    unavailable = source_id
                    break
                operand = project_semantic_program_operand(
                    candidate,
                    obligation_id=obligation_id,
                )
                input_rows.append(operand)
                candidate_ids.append(source_id)
                source_row_ids.extend(operand.get("source_row_ids") or [])
                source_anchors.append(str(candidate.get("source_anchor") or ""))
            elif source_id in outputs and outputs[source_id].get("normalized_value") is not None:
                env[variable] = float(outputs[source_id]["normalized_value"])
                candidate_ids.extend(outputs[source_id].get("candidate_ids") or [])
                source_row_ids.extend(outputs[source_id].get("source_row_ids") or [])
                source_anchors.extend(outputs[source_id].get("source_anchors") or [])
            else:
                unavailable = source_id
                break
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
        display_unit = str(
            expression.get("display_unit")
            or expression.get("result_unit")
            or obligation.get("display_unit")
            or ""
        )
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
                "input_candidate_ids": [row["candidate_id"] for row in input_rows if row.get("candidate_id")],
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
            "input_rows": input_rows,
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
    operands: List[Dict[str, Any]] = []
    for candidate_id in selected_candidate_ids:
        candidate = candidate_by_id.get(candidate_id)
        if not candidate or candidate.get("kind") != "numeric":
            continue
        binding = direct_binding_by_candidate_id.get(candidate_id)
        obligation_id = str((binding or {}).get("obligation_id") or "")
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
    from copy import deepcopy

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
