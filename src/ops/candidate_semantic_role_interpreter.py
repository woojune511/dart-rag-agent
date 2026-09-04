"""Build and validate bounded semantic-role requests for prose candidates.

This module is evaluation-only.  It does not construct a provider client or
change runtime candidate order.  A caller may export requests, obtain model or
human responses separately, and project only source-grounded roles into a
semantic tie-break fixture.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
from typing import Any, Literal, Mapping, Protocol, Sequence

from pydantic import BaseModel, Field

from src.agent.financial_candidate_fact_role import CandidateSemanticRoleV1


REQUEST_BUNDLE_SCHEMA = "candidate_semantic_role_request_bundle_v1"
REQUEST_SCHEMA = "candidate_semantic_role_request_v1"
RESPONSE_BUNDLE_SCHEMA = "candidate_semantic_role_response_bundle_v1"
RESPONSE_SCHEMA = "candidate_semantic_role_response_v1"
PROJECTION_SCHEMA = "candidate_semantic_role_fixture_projection_v1"

DECISION_STATUSES = frozenset({"grounded", "unresolved"})
VALUE_ROLES = (
    "reported_total",
    "component",
    "adjustment_component",
    "period_value",
    "rate",
    "derived_display",
    "other",
)

DEFAULT_SOURCE_CHAR_LIMIT = 1200
DEFAULT_CANDIDATE_LIMIT = 8
DEFAULT_REQUEST_LIMIT = 32

_INSTRUCTIONS = (
    "Describe every candidate independently; do not select an answer.",
    "Use exact contiguous source substrings for subject and relation surfaces.",
    "A grounded relation surface must contain that candidate's visible value.",
    "Return unresolved when the source does not establish a candidate-local role.",
)


class CandidateSemanticRoleInterpreter(Protocol):
    """Provider-neutral seam used only by an explicit evaluation caller."""

    def interpret(self, request: Mapping[str, Any]) -> Mapping[str, Any]: ...


class _SemanticRoleDecisionOutput(BaseModel):
    candidate_id: str
    status: Literal["grounded", "unresolved"]
    subject_surfaces: list[str] = Field(default_factory=list)
    relation_surfaces: list[str] = Field(default_factory=list)
    value_role: Literal[
        "reported_total",
        "component",
        "adjustment_component",
        "period_value",
        "rate",
        "derived_display",
        "other",
    ] = "other"


class _SemanticRoleResponseOutput(BaseModel):
    decisions: list[_SemanticRoleDecisionOutput]


class StructuredOutputCandidateSemanticRoleInterpreter:
    """Adapter for an injected LangChain-style structured-output model."""

    def __init__(self, llm: Any) -> None:
        self._structured_llm = llm.with_structured_output(
            _SemanticRoleResponseOutput
        )

    def interpret(self, request: Mapping[str, Any]) -> Mapping[str, Any]:
        output = self._structured_llm.invoke(render_request_prompt(request))
        if isinstance(output, Mapping):
            return dict(output)
        if hasattr(output, "model_dump"):
            return dict(output.model_dump())
        if hasattr(output, "dict"):
            return dict(output.dict())
        raise TypeError("semantic-role interpreter returned unsupported output")


def _fingerprint(value: Any) -> str:
    serialized = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _normalise(value: Any) -> str:
    return " ".join(str("" if value is None else value).split())


def _verify_bundle_fingerprint(
    payload: Mapping[str, Any],
    field: str,
) -> str:
    expected = str(payload.get(field) or "")
    unsigned = dict(payload)
    unsigned.pop(field, None)
    if not expected or _fingerprint(unsigned) != expected:
        raise ValueError(f"semantic-role {field} mismatch")
    return expected


def _candidate_value_span(
    candidate: Mapping[str, Any],
    source_text: str,
) -> tuple[int, int] | None:
    raw_value = str(candidate.get("raw_value") or "")
    raw_span = candidate.get("source_span")
    if (
        isinstance(raw_span, Sequence)
        and not isinstance(raw_span, (str, bytes))
        and len(raw_span) == 2
    ):
        try:
            start, end = int(raw_span[0]), int(raw_span[1])
        except (TypeError, ValueError):
            start, end = -1, -1
        if (
            raw_value
            and 0 <= start < end <= len(source_text)
            and source_text[start:end] == raw_value
        ):
            return start, end
    if not raw_value:
        return None
    starts: list[int] = []
    offset = 0
    while True:
        start = source_text.find(raw_value, offset)
        if start < 0:
            break
        starts.append(start)
        offset = start + max(1, len(raw_value))
    if len(starts) != 1:
        return None
    return starts[0], starts[0] + len(raw_value)


def _request_id(source_text: str, candidates: Sequence[Mapping[str, Any]]) -> str:
    identity = {
        "source_fingerprint": _fingerprint(source_text),
        "candidates": [
            {
                "candidate_id": str(candidate.get("candidate_id") or ""),
                "raw_value": str(candidate.get("raw_value") or ""),
                "value_span": list(candidate.get("value_span") or []),
            }
            for candidate in candidates
        ],
    }
    return f"role_req_{_fingerprint(identity)[:16]}"


def _semantic_candidate_rows(
    fixture: Mapping[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    by_candidate_id: dict[str, dict[str, Any]] = {}
    skipped_by_candidate_id: dict[str, dict[str, str]] = {}
    for raw_case in fixture.get("cases") or []:
        if not isinstance(raw_case, Mapping):
            continue
        for raw_item in raw_case.get("candidates") or []:
            if not isinstance(raw_item, Mapping):
                continue
            item = dict(raw_item)
            fact_role = dict(item.get("fact_role") or {})
            if (
                fact_role.get("source_kind") != "prose"
                or fact_role.get("grounding_state") != "unresolved"
            ):
                continue
            candidate_id = _normalise(item.get("candidate_id"))
            source_text = str(
                item.get("candidate_text")
                or dict(item.get("candidate") or {}).get("source_text")
                or ""
            )
            candidate = dict(item.get("candidate") or {})
            if not candidate_id or not source_text:
                continue
            value_span = _candidate_value_span(candidate, source_text)
            if value_span is None:
                skipped_by_candidate_id[candidate_id] = {
                    "candidate_id": candidate_id,
                    "reason": "value_surface_not_unique",
                }
                continue
            row = {
                "candidate_id": candidate_id,
                "raw_value": str(candidate.get("raw_value") or ""),
                "normalized_value": candidate.get("normalized_value"),
                "value_span": list(value_span),
                "source_text": source_text,
            }
            previous = by_candidate_id.get(candidate_id)
            if previous is not None and previous != row:
                raise ValueError(
                    f"candidate semantic-role source changed: {candidate_id}"
                )
            by_candidate_id[candidate_id] = row
    return (
        list(by_candidate_id.values()),
        list(skipped_by_candidate_id.values()),
    )


def build_request_bundle(
    fixture: Mapping[str, Any],
    *,
    source_char_limit: int = DEFAULT_SOURCE_CHAR_LIMIT,
    candidate_limit: int = DEFAULT_CANDIDATE_LIMIT,
    request_limit: int = DEFAULT_REQUEST_LIMIT,
) -> dict[str, Any]:
    """Group unresolved prose values by exact source without answer labels."""

    if min(source_char_limit, candidate_limit, request_limit) <= 0:
        raise ValueError("semantic-role request limits must be positive")
    candidate_rows, skipped = _semantic_candidate_rows(fixture)
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in candidate_rows:
        grouped.setdefault(str(row.pop("source_text")), []).append(row)

    requests: list[dict[str, Any]] = []
    for source_text, rows in grouped.items():
        if len(source_text) > source_char_limit:
            raise ValueError("semantic-role source exceeds character limit")
        ordered = sorted(rows, key=lambda row: str(row["candidate_id"]))
        if len(ordered) > candidate_limit:
            raise ValueError("semantic-role source exceeds candidate limit")
        request = {
            "schema": REQUEST_SCHEMA,
            "source_fingerprint": _fingerprint(source_text),
            "source_text": source_text,
            "candidates": ordered,
        }
        request["request_id"] = _request_id(source_text, ordered)
        requests.append(request)
    requests.sort(key=lambda row: str(row["request_id"]))
    if len(requests) > request_limit:
        raise ValueError("semantic-role request count exceeds limit")

    payload = {
        "schema": REQUEST_BUNDLE_SCHEMA,
        "source_fixture_fingerprint": _fingerprint(fixture),
        "instructions": list(_INSTRUCTIONS),
        "value_roles": list(VALUE_ROLES),
        "limits": {
            "source_chars": int(source_char_limit),
            "candidates_per_request": int(candidate_limit),
            "requests": int(request_limit),
        },
        "request_count": len(requests),
        "candidate_count": sum(
            len(request["candidates"]) for request in requests
        ),
        "skipped_candidates": sorted(
            skipped,
            key=lambda row: row["candidate_id"],
        ),
        "requests": requests,
    }
    payload["request_bundle_fingerprint"] = _fingerprint(payload)
    return payload


def render_request_prompt(request: Mapping[str, Any]) -> str:
    """Render one answer-label-free request for a structured-output model."""

    if request.get("schema") != REQUEST_SCHEMA:
        raise ValueError("unsupported candidate semantic-role request")
    candidate_rows = [
        {
            "candidate_id": str(candidate.get("candidate_id") or ""),
            "raw_value": str(candidate.get("raw_value") or ""),
            "value_span": list(candidate.get("value_span") or []),
        }
        for candidate in request.get("candidates") or []
        if isinstance(candidate, Mapping)
    ]
    return (
        "You assign candidate-local semantic roles to numeric mentions.\n"
        + "\n".join(f"- {instruction}" for instruction in _INSTRUCTIONS)
        + "\nAllowed value_role values: "
        + ", ".join(VALUE_ROLES)
        + "\nAllowed status values: grounded, unresolved"
        + "\n\nExact source:\n"
        + str(request.get("source_text") or "")
        + "\n\nCandidates:\n"
        + json.dumps(candidate_rows, ensure_ascii=False, indent=2)
        + "\n\nReturn one decision per candidate with candidate_id, status, "
        "subject_surfaces, relation_surfaces, and value_role."
    )


def collect_interpreter_responses(
    request_bundle: Mapping[str, Any],
    interpreter: CandidateSemanticRoleInterpreter,
) -> dict[str, Any]:
    """Call an injected interpreter; no provider is constructed here."""

    if request_bundle.get("schema") != REQUEST_BUNDLE_SCHEMA:
        raise ValueError("unsupported semantic-role request bundle")
    _verify_bundle_fingerprint(
        request_bundle,
        "request_bundle_fingerprint",
    )
    responses: list[dict[str, Any]] = []
    for raw_request in request_bundle.get("requests") or []:
        request = dict(raw_request)
        raw_response = interpreter.interpret(copy.deepcopy(request))
        response = dict(raw_response or {})
        response.setdefault("schema", RESPONSE_SCHEMA)
        response.setdefault("request_id", request["request_id"])
        response.setdefault("source_fingerprint", request["source_fingerprint"])
        responses.append(response)
    payload = {
        "schema": RESPONSE_BUNDLE_SCHEMA,
        "request_bundle_fingerprint": str(
            request_bundle.get("request_bundle_fingerprint") or ""
        ),
        "responses": responses,
    }
    payload["response_bundle_fingerprint"] = _fingerprint(payload)
    return payload


def _role_by_candidate_id(
    request_bundle: Mapping[str, Any],
    response_bundle: Mapping[str, Any],
) -> tuple[dict[str, CandidateSemanticRoleV1], set[str]]:
    if response_bundle.get("schema") != RESPONSE_BUNDLE_SCHEMA:
        raise ValueError("unsupported semantic-role response bundle")
    expected_bundle_fingerprint = _verify_bundle_fingerprint(
        request_bundle,
        "request_bundle_fingerprint",
    )
    _verify_bundle_fingerprint(
        response_bundle,
        "response_bundle_fingerprint",
    )
    if response_bundle.get("request_bundle_fingerprint") != expected_bundle_fingerprint:
        raise ValueError("semantic-role request bundle fingerprint mismatch")
    requests = {
        str(request.get("request_id") or ""): dict(request)
        for request in request_bundle.get("requests") or []
        if isinstance(request, Mapping)
    }
    responses = [
        dict(response)
        for response in response_bundle.get("responses") or []
        if isinstance(response, Mapping)
    ]
    if len(responses) != len(requests):
        raise ValueError("semantic-role response count mismatch")
    if {str(response.get("request_id") or "") for response in responses} != set(
        requests
    ):
        raise ValueError("semantic-role response request ids mismatch")

    roles: dict[str, CandidateSemanticRoleV1] = {}
    unresolved: set[str] = set()
    for response in responses:
        if response.get("schema") != RESPONSE_SCHEMA:
            raise ValueError("unsupported semantic-role response")
        request = requests[str(response.get("request_id") or "")]
        if response.get("source_fingerprint") != request["source_fingerprint"]:
            raise ValueError("semantic-role source fingerprint mismatch")
        candidates = {
            str(candidate.get("candidate_id") or ""): dict(candidate)
            for candidate in request.get("candidates") or []
            if isinstance(candidate, Mapping)
        }
        decisions = [
            dict(decision)
            for decision in response.get("decisions") or []
            if isinstance(decision, Mapping)
        ]
        decision_ids = [str(decision.get("candidate_id") or "") for decision in decisions]
        if len(decision_ids) != len(set(decision_ids)) or set(decision_ids) != set(
            candidates
        ):
            raise ValueError("semantic-role decision candidate ids mismatch")
        source_text = str(request.get("source_text") or "")
        for decision in decisions:
            candidate_id = str(decision.get("candidate_id") or "")
            candidate = candidates[candidate_id]
            status = str(decision.get("status") or "")
            if status not in DECISION_STATUSES:
                raise ValueError("unsupported semantic-role decision status")
            if status == "unresolved":
                unresolved.add(candidate_id)
                continue
            value_role = str(decision.get("value_role") or "")
            if value_role not in VALUE_ROLES:
                raise ValueError("unsupported candidate semantic value role")
            relation_surfaces = [
                str(surface)
                for surface in decision.get("relation_surfaces") or []
                if str(surface).strip()
            ]
            raw_value = _normalise(candidate.get("raw_value"))
            if not relation_surfaces or not any(
                raw_value in _normalise(surface) for surface in relation_surfaces
            ):
                raise ValueError(
                    "grounded semantic relation must contain candidate value"
                )
            roles[candidate_id] = CandidateSemanticRoleV1.create(
                candidate_id=candidate_id,
                source_text=source_text,
                subject_surfaces=decision.get("subject_surfaces") or [],
                relation_surfaces=relation_surfaces,
                value_role=value_role,
            )
    return roles, unresolved


def project_response_bundle(
    fixture: Mapping[str, Any],
    request_bundle: Mapping[str, Any],
    response_bundle: Mapping[str, Any],
) -> dict[str, Any]:
    """Project validated roles into a copied evaluation fixture."""

    if request_bundle.get("schema") != REQUEST_BUNDLE_SCHEMA:
        raise ValueError("unsupported semantic-role request bundle")
    if request_bundle.get("source_fixture_fingerprint") != _fingerprint(fixture):
        raise ValueError("semantic-role source fixture fingerprint mismatch")
    roles, unresolved = _role_by_candidate_id(request_bundle, response_bundle)
    projected = copy.deepcopy(dict(fixture))
    projected_ids: set[str] = set()
    for raw_case in projected.get("cases") or []:
        for raw_item in raw_case.get("candidates") or []:
            candidate_id = str(raw_item.get("candidate_id") or "")
            if candidate_id in roles:
                raw_item["semantic_role"] = roles[candidate_id].to_projection()
                projected_ids.add(candidate_id)
            elif candidate_id in unresolved:
                raw_item.pop("semantic_role", None)
                projected_ids.add(candidate_id)
    expected_ids = set(roles) | unresolved
    if projected_ids != expected_ids:
        raise ValueError("semantic-role projection candidate ids mismatch")
    projected["semantic_role_projection"] = {
        "schema": PROJECTION_SCHEMA,
        "request_bundle_fingerprint": str(
            request_bundle.get("request_bundle_fingerprint") or ""
        ),
        "response_bundle_fingerprint": str(
            response_bundle.get("response_bundle_fingerprint") or ""
        ),
        "grounded_candidate_ids": sorted(roles),
        "unresolved_candidate_ids": sorted(unresolved),
        "runtime_wiring_changed": False,
    }
    return projected


def evaluate_response_bundle(
    request_bundle: Mapping[str, Any],
    expected_response_bundle: Mapping[str, Any],
    actual_response_bundle: Mapping[str, Any],
) -> dict[str, Any]:
    """Compare validated interpreter output with reviewed candidate roles."""

    expected_roles, expected_unresolved = _role_by_candidate_id(
        request_bundle,
        expected_response_bundle,
    )
    actual_roles, actual_unresolved = _role_by_candidate_id(
        request_bundle,
        actual_response_bundle,
    )
    candidate_ids = sorted(set(expected_roles) | expected_unresolved)
    if set(candidate_ids) != set(actual_roles) | actual_unresolved:
        raise ValueError("semantic-role evaluation candidate ids mismatch")

    def surfaces_overlap(left: Sequence[str], right: Sequence[str]) -> bool:
        if not left:
            return True
        normalized_left = [_normalise(surface).casefold() for surface in left]
        normalized_right = [_normalise(surface).casefold() for surface in right]
        return any(
            expected in actual or actual in expected
            for expected in normalized_left
            for actual in normalized_right
            if expected and actual
        )

    rows: list[dict[str, Any]] = []
    matched_count = 0
    for candidate_id in candidate_ids:
        expected_status = (
            "grounded" if candidate_id in expected_roles else "unresolved"
        )
        actual_status = "grounded" if candidate_id in actual_roles else "unresolved"
        expected_role = expected_roles.get(candidate_id)
        actual_role = actual_roles.get(candidate_id)
        value_role_match = bool(
            expected_role is None
            or (
                actual_role is not None
                and actual_role.value_role == expected_role.value_role
            )
        )
        subject_match = bool(
            expected_role is None
            or (
                actual_role is not None
                and surfaces_overlap(
                    expected_role.subject_surfaces,
                    actual_role.subject_surfaces,
                )
            )
        )
        matched = (
            expected_status == actual_status
            and value_role_match
            and subject_match
        )
        matched_count += int(matched)
        rows.append(
            {
                "candidate_id": candidate_id,
                "expected_status": expected_status,
                "actual_status": actual_status,
                "expected_value_role": (
                    expected_role.value_role if expected_role else "unknown"
                ),
                "actual_value_role": (
                    actual_role.value_role if actual_role else "unknown"
                ),
                "value_role_match": value_role_match,
                "subject_surface_match": subject_match,
                "matched": matched,
            }
        )
    candidate_count = len(candidate_ids)
    return {
        "schema": "candidate_semantic_role_interpreter_gate_v1",
        "status": "matched" if matched_count == candidate_count else "needs_review",
        "request_bundle_fingerprint": str(
            request_bundle.get("request_bundle_fingerprint") or ""
        ),
        "expected_response_bundle_fingerprint": str(
            expected_response_bundle.get("response_bundle_fingerprint") or ""
        ),
        "actual_response_bundle_fingerprint": str(
            actual_response_bundle.get("response_bundle_fingerprint") or ""
        ),
        "candidate_count": candidate_count,
        "matched_candidate_count": matched_count,
        "accuracy": (
            round(matched_count / candidate_count, 6) if candidate_count else 1.0
        ),
        "candidates": rows,
    }


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", type=Path, required=True)
    parser.add_argument("--responses", type=Path)
    parser.add_argument("--expected-responses", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--format",
        choices=("json", "prompts"),
        default="json",
        help="Without --responses, export a JSON bundle or rendered prompts.",
    )
    parser.add_argument("--source-char-limit", type=int, default=DEFAULT_SOURCE_CHAR_LIMIT)
    parser.add_argument("--candidate-limit", type=int, default=DEFAULT_CANDIDATE_LIMIT)
    parser.add_argument("--request-limit", type=int, default=DEFAULT_REQUEST_LIMIT)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    fixture = json.loads(args.fixture.read_text(encoding="utf-8"))
    request_bundle = build_request_bundle(
        fixture,
        source_char_limit=args.source_char_limit,
        candidate_limit=args.candidate_limit,
        request_limit=args.request_limit,
    )
    if args.responses:
        response_bundle = json.loads(args.responses.read_text(encoding="utf-8"))
        if args.expected_responses:
            expected_response_bundle = json.loads(
                args.expected_responses.read_text(encoding="utf-8")
            )
            output: Any = evaluate_response_bundle(
                request_bundle,
                expected_response_bundle,
                response_bundle,
            )
        else:
            output = project_response_bundle(
                fixture,
                request_bundle,
                response_bundle,
            )
    elif args.expected_responses:
        raise ValueError("--expected-responses requires --responses")
    elif args.format == "prompts":
        output = "\n\n---\n\n".join(
            render_request_prompt(request)
            for request in request_bundle["requests"]
        )
    else:
        output = request_bundle
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(output, str):
        args.output.write_text(output + "\n", encoding="utf-8", newline="\n")
    else:
        args.output.write_text(
            json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "CandidateSemanticRoleInterpreter",
    "DECISION_STATUSES",
    "PROJECTION_SCHEMA",
    "REQUEST_BUNDLE_SCHEMA",
    "REQUEST_SCHEMA",
    "RESPONSE_BUNDLE_SCHEMA",
    "RESPONSE_SCHEMA",
    "StructuredOutputCandidateSemanticRoleInterpreter",
    "VALUE_ROLES",
    "build_request_bundle",
    "collect_interpreter_responses",
    "evaluate_response_bundle",
    "project_response_bundle",
    "render_request_prompt",
]
