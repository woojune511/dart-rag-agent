"""Opt-in observations of compiler attempts; never execution or prompt authority."""

from copy import deepcopy
import hashlib
from typing import Any, Mapping, Sequence

from src.agent.financial_graph_state import CompilerAttemptDebugV1
from src.utils.request_diagnostics import diagnostic_location, record_diagnostic


def project_compiler_attempt(
    *, attempt: int, active_obligation_ids: Sequence[str],
    island_obligation_ids: Sequence[str], visible_candidate_ids: Sequence[str],
    model_program_json: str | None, validation_input_program_json: str | None,
    validation: Mapping[str, Any], retry_feedback_text: str, response_error_type: str,
) -> CompilerAttemptDebugV1:
    """Snapshot schema-parsed JSON, not provider wire bytes or hidden reasoning.

    Error locations refer to the merged validation input, not necessarily the
    model's targeted retry. A missing parsed response is never reconstructed from
    the runtime's fabricated failure program or a provider exception body.
    """
    def fingerprint(value: str | None) -> str | None:
        return hashlib.sha256(value.encode("utf-8")).hexdigest() if value is not None else None

    valid_ids = {
        row["obligation_id"]
        for key in ("valid_direct_bindings", "valid_expressions", "valid_narrative_bindings")
        for row in validation.get(key) or []
    }
    snapshot: CompilerAttemptDebugV1 = {
        "schema_version": "compiler_attempt_debug_v1",
        "island_id": "",  # Assigned by the island owner when collecting results.
        "attempt": attempt,
        "active_obligation_ids": list(active_obligation_ids),
        "visible_candidate_ids": list(visible_candidate_ids),
        "response_status": "parsed" if model_program_json is not None else "unavailable",
        "response_error_type": response_error_type,
        "model_program_json": model_program_json,
        "model_program_sha256": fingerprint(model_program_json),
        "validation_input_program_json": validation_input_program_json,
        "validation_input_program_sha256": fingerprint(validation_input_program_json),
        "validation_status": str(validation.get("status") or ""),
        "validation_errors": deepcopy(list(validation.get("errors") or [])),
        "compile_valid_obligation_ids": [owner for owner in island_obligation_ids if owner in valid_ids],
        "missing_obligation_ids": list(validation.get("missing_obligation_ids") or []),
        "ambiguous_obligation_ids": list(validation.get("ambiguous_obligation_ids") or []),
        "retry_feedback_text": retry_feedback_text,
    }
    with diagnostic_location(attempt=attempt):
        record_diagnostic("compiler_attempt", snapshot)
    return snapshot
