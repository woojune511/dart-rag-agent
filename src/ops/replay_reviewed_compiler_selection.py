"""Bounded compiler-only evaluation for the reviewed runtime corpus.

The harness deliberately omits retrieval, planning, evaluation, embeddings, and
stores.  It gives the current semantic compiler the reviewed question,
obligations, and compact candidate catalog, then validates and executes the
result with the production contracts.  The default rehearsal substitutes the
reviewed programs for a provider and therefore cannot make a network call.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import subprocess
from copy import deepcopy
from datetime import date
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from dotenv import dotenv_values

from src.agent.financial_calculation_execution import (
    execute_semantic_calculation_program,
)
from src.agent.financial_graph_calculation import (
    FinancialAgentCalculationMixin,
    _semantic_candidate_cohorts,
    build_semantic_compilation_islands,
)
from src.agent.financial_graph_models import SemanticCalculationProgram
from src.ops.replay_reviewed_runtime_corpus import (
    CORPUS_SCHEMA_VERSION,
    _canonical_bytes,
    _materialize_catalog,
    _output_matches,
)
from src.utils.gemini_usage import GeminiUsageCallbackHandler
from src.utils.gemini_usage_counts import estimate_gemini_cost_usd


PROJECT_ROOT = Path(__file__).resolve().parents[2]
ADMISSION_SCHEMA_VERSION = "reviewed_compiler_selection_admission_v1"
REHEARSAL_SCHEMA_VERSION = "reviewed_compiler_selection_rehearsal_v1"
RESULT_SCHEMA_VERSION = "reviewed_compiler_selection_result_v1"
DEFAULT_PROVIDER = "google"
DEFAULT_MODEL = "gemini-2.5-flash"
DEFAULT_MAX_OUTPUT_TOKENS = 2048
OFFICIAL_STANDARD_PRICING = {
    "input_per_million_tokens_usd": 0.30,
    "output_per_million_tokens_usd": 2.50,
    "thinking_per_million_tokens_usd": 2.50,
}
OFFICIAL_PRICING_URL = "https://ai.google.dev/gemini-api/docs/pricing"


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _write_new_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(serialized)


def _load_corpus(path: Path) -> dict[str, Any]:
    corpus = json.loads(path.read_text(encoding="utf-8"))
    if str(corpus.get("schema_version") or "") != CORPUS_SCHEMA_VERSION:
        raise ValueError("unsupported reviewed runtime corpus schema")
    return corpus


def _prompt_bytes(prompt: Any) -> bytes:
    to_messages = getattr(prompt, "to_messages", None)
    if not callable(to_messages):
        return str(prompt).encode("utf-8")
    projection = []
    for message in to_messages():
        content = getattr(message, "content", "")
        projection.append(
            {
                "role": str(getattr(message, "type", "") or ""),
                "content": (
                    content
                    if isinstance(content, str)
                    else json.dumps(
                        content,
                        ensure_ascii=False,
                        sort_keys=True,
                        default=str,
                    )
                ),
            }
        )
    return _canonical_bytes(projection)


class _RecordingStructuredInvoker:
    def __init__(self, delegate: Any, records: list[dict[str, Any]]) -> None:
        self._delegate = delegate
        self._records = records

    def invoke(self, prompt: Any) -> Any:
        payload = _prompt_bytes(prompt)
        self._records.append(
            {
                "prompt_bytes": len(payload),
                "prompt_sha256": _sha256_bytes(payload),
            }
        )
        return self._delegate.invoke(prompt)


class _RecordingLLM:
    def __init__(self, delegate: Any) -> None:
        self._delegate = delegate
        self.records: list[dict[str, Any]] = []

    def with_structured_output(self, model: Any) -> _RecordingStructuredInvoker:
        return _RecordingStructuredInvoker(
            self._delegate.with_structured_output(model),
            self.records,
        )


class _ReviewedProgramQueue:
    """Provider-free structured-output substitute used only by rehearsal."""

    def __init__(self, responses: Sequence[SemanticCalculationProgram]) -> None:
        self._responses = list(responses)
        self.requested_models: list[str] = []

    def with_structured_output(self, model: Any) -> "_ReviewedProgramQueue":
        self.requested_models.append(str(getattr(model, "__name__", "")))
        return self

    def invoke(self, _prompt: Any) -> SemanticCalculationProgram:
        if not self._responses:
            raise AssertionError("unexpected reviewed compiler rehearsal invocation")
        return self._responses.pop(0)

    @property
    def remaining_response_count(self) -> int:
        return len(self._responses)


class _CompilerOnlyAgent(FinancialAgentCalculationMixin):
    def __init__(
        self,
        llm: Any,
        *,
        usage_callback: GeminiUsageCallbackHandler | None = None,
    ) -> None:
        self.llm = llm
        self.llm_routes: dict[str, Any] = {}
        self.llm_usage_callback = usage_callback

    def _llm_for_phase(self, phase: str) -> Any:
        if self.llm_usage_callback is not None:
            self.llm_usage_callback.set_current_phase(phase)
        return self.llm


def _island_obligation_ids(case: Mapping[str, Any]) -> list[list[str]]:
    catalog, _ = _materialize_catalog(
        [
            dict(item)
            for item in (case.get("candidate_catalog") or [])
            if isinstance(item, Mapping)
        ]
    )
    obligations = [
        dict(item)
        for item in (case.get("obligations") or [])
        if isinstance(item, Mapping)
    ]
    cohorts = _semantic_candidate_cohorts(catalog, obligations)
    islands = build_semantic_compilation_islands(
        obligations,
        evidence_bundle_constraints=list(
            cohorts.get("evidence_bundle_constraints") or []
        ),
    )
    return [
        [str(item) for item in (island.get("obligation_ids") or [])]
        for island in (islands.get("islands") or [])
        if isinstance(island, Mapping)
    ]


def _program_for_obligations(
    raw_program: Mapping[str, Any],
    obligation_ids: Sequence[str],
) -> SemanticCalculationProgram:
    owners = set(obligation_ids)
    direct_bindings = [
        deepcopy(dict(item))
        for item in (raw_program.get("direct_bindings") or [])
        if isinstance(item, Mapping)
        and str(item.get("obligation_id") or "") in owners
    ]
    expressions = [
        deepcopy(dict(item))
        for item in (raw_program.get("expressions") or [])
        if isinstance(item, Mapping)
        and str(item.get("obligation_id") or "") in owners
    ]
    narrative_bindings = [
        deepcopy(dict(item))
        for item in (raw_program.get("narrative_bindings") or [])
        if isinstance(item, Mapping)
        and str(item.get("obligation_id") or "") in owners
    ]
    selected_candidate_ids = {
        str(item.get("candidate_id") or "") for item in direct_bindings
    }
    for expression in expressions:
        selected_candidate_ids.add(
            str(expression.get("source_display_candidate_id") or "")
        )
        for binding in expression.get("variable_bindings") or []:
            if isinstance(binding, Mapping):
                selected_candidate_ids.add(str(binding.get("source_id") or ""))
    for binding in narrative_bindings:
        selected_candidate_ids.update(
            str(item) for item in (binding.get("candidate_ids") or [])
        )
    selected_candidate_ids.discard("")
    assertions = [
        deepcopy(dict(item))
        for item in (raw_program.get("source_assertions") or [])
        if isinstance(item, Mapping)
        and set(str(value) for value in (item.get("candidate_ids") or []))
        <= selected_candidate_ids
    ]
    projection = {
        "status": str(raw_program.get("status") or "ready"),
        "direct_bindings": direct_bindings,
        "expressions": expressions,
        "narrative_bindings": narrative_bindings,
        "source_assertions": assertions,
        "missing_obligation_ids": [
            str(item)
            for item in (raw_program.get("missing_obligation_ids") or [])
            if str(item) in owners
        ],
        "ambiguous_obligation_ids": [
            str(item)
            for item in (raw_program.get("ambiguous_obligation_ids") or [])
            if str(item) in owners
        ],
        "rationale": str(raw_program.get("rationale") or ""),
    }
    return SemanticCalculationProgram.model_validate(projection)


def _reviewed_response_queue(corpus: Mapping[str, Any]) -> list[SemanticCalculationProgram]:
    responses: list[SemanticCalculationProgram] = []
    for case in corpus.get("cases") or []:
        if not isinstance(case, Mapping):
            continue
        program = dict(case.get("program") or {})
        for obligation_ids in _island_obligation_ids(case):
            responses.append(_program_for_obligations(program, obligation_ids))
    return responses


def _case_state(
    case: Mapping[str, Any],
    catalog: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    obligations = [
        dict(item)
        for item in (case.get("obligations") or [])
        if isinstance(item, Mapping)
    ]
    return {
        "query": str(case.get("question") or ""),
        "answer_obligations": obligations,
        "semantic_plan": {"answer_obligations": obligations},
        "semantic_candidate_catalog_prebuilt": True,
        "semantic_source_candidates": [dict(item) for item in catalog],
        "semantic_candidate_catalog": [dict(item) for item in catalog],
        "evidence_items": [],
        "planner_debug_trace": {},
        "resolved_calculation_trace": {},
    }


def evaluate_reviewed_compiler_selection(
    corpus_path: Path,
    compiler_llm: Any,
    *,
    run_mode: str,
    usage_callback: GeminiUsageCallbackHandler | None = None,
    stop_on_case_failure: bool = False,
) -> dict[str, Any]:
    """Run current compilation islands over reviewed inputs and execute them."""

    path = Path(corpus_path).resolve()
    corpus = _load_corpus(path)
    recording_llm = _RecordingLLM(compiler_llm)
    agent = _CompilerOnlyAgent(recording_llm, usage_callback=usage_callback)
    results: list[dict[str, Any]] = []
    for raw_case in corpus.get("cases") or []:
        if not isinstance(raw_case, Mapping):
            continue
        case = deepcopy(dict(raw_case))
        catalog, normalization = _materialize_catalog(
            [
                dict(item)
                for item in (case.get("candidate_catalog") or [])
                if isinstance(item, Mapping)
            ]
        )
        state = _case_state(case, catalog)
        prompt_start = len(recording_llm.records)
        compiled = agent._compile_semantic_calculation_program(state)
        case_prompts = recording_llm.records[prompt_start:]
        program = dict(compiled.get("semantic_program") or {})
        validation = dict(compiled.get("semantic_program_validation") or {})
        envelope = compiled.get("semantic_compilation_envelope")
        execution = execute_semantic_calculation_program(
            program=program,
            obligations=list(state["answer_obligations"]),
            candidate_catalog=list(catalog),
            query=str(state["query"]),
            compilation_envelope=envelope,
            require_compilation_envelope=True,
        )
        expected = dict(case.get("expected") or {})
        expected_outputs = [
            dict(item)
            for item in (expected.get("outputs") or [])
            if isinstance(item, Mapping)
        ]
        actual_by_owner = {
            str(item.get("obligation_id") or ""): dict(item)
            for item in (execution.get("outputs") or [])
            if isinstance(item, Mapping)
        }
        output_checks = []
        for expected_output in expected_outputs:
            owner_id = str(expected_output.get("obligation_id") or "")
            matches, mismatches = _output_matches(
                actual_by_owner.get(owner_id, {}),
                expected_output,
                absolute_tolerance=float(expected.get("absolute_tolerance") or 1e-9),
            )
            output_checks.append(
                {
                    "obligation_id": owner_id,
                    "matches": matches,
                    "mismatch_fields": mismatches,
                }
            )
        selected_ids = list(execution.get("selected_candidate_ids") or [])
        expected_ids = list(expected.get("selected_candidate_ids") or [])
        island_count = len(_island_obligation_ids(case))
        diagnostics = list(
            dict(compiled.get("planner_debug_trace") or {}).get(
                "compilation_islands"
            )
            or []
        )
        compiler_call_count = int(
            dict(compiled.get("planner_debug_trace") or {}).get(
                "program_compiler_call_count"
            )
            or 0
        )
        checks = {
            "normalization_matches_review": all(
                bool(item.get("value_matches")) and bool(item.get("unit_matches"))
                for item in normalization
            ),
            "validation_ready": validation.get("status") == "ready",
            "execution_ok": execution.get("status") == "ok",
            "selected_candidate_ids_expected": (
                len(selected_ids) == len(expected_ids)
                and set(selected_ids) == set(expected_ids)
            ),
            "expected_outputs_match": (
                bool(output_checks) and all(item["matches"] for item in output_checks)
            ),
            "compiler_calls_bounded": (
                island_count <= compiler_call_count <= island_count * 2
            ),
            "prompt_capture_matches_calls": len(case_prompts) == compiler_call_count,
            "execution_errors_zero": not list(execution.get("execution_errors") or []),
        }
        passed = all(checks.values())
        results.append(
            {
                "case_id": str(case.get("case_id") or ""),
                "question_id": str(case.get("question_id") or ""),
                "status": "passed" if passed else "failed",
                "checks": checks,
                "island_count": island_count,
                "compiler_call_count": compiler_call_count,
                "compiler_retry_count": int(
                    compiled.get("semantic_program_retry_count") or 0
                ),
                "prompt_records": case_prompts,
                "validation": {
                    "status": str(validation.get("status") or ""),
                    "errors": list(validation.get("errors") or []),
                    "selected_candidate_ids": list(
                        validation.get("selected_candidate_ids") or []
                    ),
                },
                "execution": {
                    "status": str(execution.get("status") or ""),
                    "errors": list(execution.get("execution_errors") or []),
                    "selected_candidate_ids": selected_ids,
                    "outputs": list(execution.get("outputs") or []),
                },
                "output_checks": output_checks,
                "compiled_program": program,
                "islands": diagnostics,
            }
        )
        if stop_on_case_failure and not passed:
            break

    passed_count = sum(item["status"] == "passed" for item in results)
    prompt_bytes = sum(
        int(record.get("prompt_bytes") or 0)
        for result in results
        for record in result["prompt_records"]
    )
    return {
        "schema_version": RESULT_SCHEMA_VERSION,
        "run_mode": run_mode,
        "status": (
            "passed"
            if len(results) == len(corpus.get("cases") or [])
            and passed_count == len(results)
            else "failed"
        ),
        "claim_boundary": (
            "Compiler-only selection over reviewed question, obligation, and "
            "source projections; no retrieval, planner, evaluator, or release claim."
        ),
        "corpus_path": path.as_posix(),
        "corpus_sha256": _sha256_file(path),
        "provider_network_calls": 0 if run_mode == "rehearsal" else None,
        "retrieval_calls": 0,
        "planner_calls": 0,
        "evaluator_calls": 0,
        "embedding_calls": 0,
        "store_writes": 0,
        "summary": {
            "configured_case_count": len(corpus.get("cases") or []),
            "executed_case_count": len(results),
            "passed_case_count": passed_count,
            "failed_case_count": len(results) - passed_count,
            "compiler_island_count": sum(item["island_count"] for item in results),
            "compiler_invocation_count": len(recording_llm.records),
            "compiler_retry_count": sum(
                item["compiler_retry_count"] for item in results
            ),
            "prompt_bytes": prompt_bytes,
            "prompt_fingerprint": _sha256_bytes(
                _canonical_bytes(recording_llm.records)
            ),
        },
        "cases": results,
    }


def rehearse_reviewed_compiler_selection(corpus_path: Path) -> dict[str, Any]:
    corpus = _load_corpus(Path(corpus_path))
    responses = _reviewed_response_queue(corpus)
    llm = _ReviewedProgramQueue(responses)
    result = evaluate_reviewed_compiler_selection(
        corpus_path,
        llm,
        run_mode="rehearsal",
    )
    result["schema_version"] = REHEARSAL_SCHEMA_VERSION
    result["provider_network_calls"] = 0
    result["reviewed_response_count"] = len(responses)
    result["unused_reviewed_response_count"] = llm.remaining_response_count
    if llm.remaining_response_count:
        result["status"] = "failed"
    return result


def _tracked_runtime_build() -> dict[str, Any]:
    status = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=no"],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if status:
        raise ValueError("tracked worktree must be clean before manifest creation")
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    raw_paths = subprocess.run(
        ["git", "ls-files", "src"],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()
    paths = sorted(Path(item) for item in raw_paths if item.strip())
    digest = hashlib.sha256()
    for relative in paths:
        digest.update(relative.as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update((PROJECT_ROOT / relative).read_bytes())
        digest.update(b"\0")
    return {
        "algorithm": "sha256(path-null-bytes-null;git-ls-files-src)",
        "git_commit": commit,
        "file_count": len(paths),
        "sha256": digest.hexdigest(),
        "tracked_worktree_clean": True,
    }


def build_admission_manifest(
    *,
    corpus_path: Path,
    manifest_path: Path,
    result_path: Path,
    cost_cap_usd: float,
    runtime_build: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    corpus_abs = Path(corpus_path).resolve()
    corpus = _load_corpus(corpus_abs)
    rehearsal = rehearse_reviewed_compiler_selection(corpus_abs)
    if rehearsal["status"] != "passed":
        raise ValueError("reviewed compiler rehearsal must pass before admission")
    initial_calls = int(rehearsal["summary"]["compiler_invocation_count"])
    maximum_calls = initial_calls * 2
    prompt_bytes = int(rehearsal["summary"]["prompt_bytes"])
    reviewed_output_bytes = sum(
        len(_canonical_bytes(program.model_dump(mode="json")))
        for program in _reviewed_response_queue(corpus)
    )
    likely_input_tokens = math.ceil(prompt_bytes / 3)
    likely_output_tokens = math.ceil(reviewed_output_bytes / 3)
    likely_cost = (
        likely_input_tokens
        / 1_000_000
        * OFFICIAL_STANDARD_PRICING["input_per_million_tokens_usd"]
        + likely_output_tokens
        / 1_000_000
        * OFFICIAL_STANDARD_PRICING["output_per_million_tokens_usd"]
    )
    retry_bounded_planning_cost = (
        likely_input_tokens
        * 2
        / 1_000_000
        * OFFICIAL_STANDARD_PRICING["input_per_million_tokens_usd"]
        + maximum_calls
        * DEFAULT_MAX_OUTPUT_TOKENS
        / 1_000_000
        * OFFICIAL_STANDARD_PRICING["output_per_million_tokens_usd"]
    )
    if float(cost_cap_usd) < retry_bounded_planning_cost:
        raise ValueError("cost cap is below the retry-bounded planning estimate")
    dotenv = {
        key: str(value)
        for key, value in dotenv_values(PROJECT_ROOT / ".env").items()
        if value is not None
    }
    manifest_rel = Path(manifest_path).resolve().relative_to(PROJECT_ROOT).as_posix()
    result_rel = Path(result_path).resolve().relative_to(PROJECT_ROOT).as_posix()
    corpus_rel = corpus_abs.relative_to(PROJECT_ROOT).as_posix()
    case_ids = [
        str(item.get("question_id") or "")
        for item in (corpus.get("cases") or [])
        if isinstance(item, Mapping)
    ]
    return {
        "schema": ADMISSION_SCHEMA_VERSION,
        "prepared_on": date.today().isoformat(),
        "authorization": {
            "status": "pending_separate_user_approval",
            "currency": "USD",
            "maximum": float(cost_cap_usd),
            "mid_request_hard_stop": False,
            "automatic_runner_retry": False,
        },
        "execution": {
            "mode": "reviewed_compiler_only",
            "attempts": 1,
            "question_order": case_ids,
            "initial_compiler_calls": initial_calls,
            "maximum_compiler_calls_with_internal_retry": maximum_calls,
            "internal_retry": "at_most_one_per_failed_compilation_island",
            "stop_after_first_failed_question": True,
            "manifest_path": manifest_rel,
            "result_path": result_rel,
            "runner_args": [
                ".venv/Scripts/python.exe",
                "-m",
                "src.ops.replay_reviewed_compiler_selection",
                "run",
                "--manifest",
                manifest_rel,
                "--approved-manifest-sha256",
                "<exact-approved-sha256>",
                "--output",
                result_rel,
            ],
        },
        "provider": {
            "name": DEFAULT_PROVIDER,
            "model": DEFAULT_MODEL,
            "temperature": 0,
            "max_output_tokens": DEFAULT_MAX_OUTPUT_TOKENS,
            "provider_client_retries": 0,
            "structured_output": "SemanticCalculationProgram",
            "required_credential_name": "GOOGLE_API_KEY",
            "credential_present": bool(
                os.environ.get("GOOGLE_API_KEY") or dotenv.get("GOOGLE_API_KEY")
            ),
            "credential_value_recorded": False,
        },
        "pricing": {
            **OFFICIAL_STANDARD_PRICING,
            "source": OFFICIAL_PRICING_URL,
            "likely_estimate_usd": likely_cost,
            "retry_bounded_planning_estimate_usd": retry_bounded_planning_cost,
            "estimate_method": (
                "likely uses rehearsal UTF-8 bytes divided by three; retry-bounded "
                "planning doubles likely input and prices every allowed call at "
                "the configured output-token maximum"
            ),
            "rehearsal_prompt_bytes": prompt_bytes,
            "rehearsal_reviewed_output_bytes": reviewed_output_bytes,
        },
        "inputs": {
            "corpus": {
                "path": corpus_rel,
                "sha256": _sha256_file(corpus_abs),
                "case_count": len(case_ids),
            },
            "runtime_build": dict(runtime_build or _tracked_runtime_build()),
            "prompt_contract": "semantic_program_candidate_payload_v5",
            "diagnostics_contract": "semantic_candidate_stage_diagnostics_v9",
            "rehearsal": {
                "compiler_island_count": rehearsal["summary"][
                    "compiler_island_count"
                ],
                "compiler_invocation_count": initial_calls,
                "prompt_fingerprint": rehearsal["summary"]["prompt_fingerprint"],
            },
        },
        "transmission_scope": {
            "destination": "Google Gemini API",
            "included": [
                "five question texts",
                "ordered answer obligations",
                "compact source-bundle excerpts",
                "candidate raw values and provenance metadata",
                "retry validation feedback only when an island fails",
            ],
            "excluded": [
                "full DART filings",
                "retrieved store contents outside the fixture",
                "reviewed expected programs and answers",
                "API credential values",
                "datasets outside the fixture",
            ],
        },
        "forbidden_operations": [
            "retrieval",
            "planning",
            "evaluator_calls",
            "embeddings",
            "fresh_fetch_parse_or_ingest",
            "source_store_read_or_write",
            "questions_outside_manifest",
            "automatic_runner_or_provider_retry",
        ],
        "acceptance": {
            "all_five_cases_pass": True,
            "validation_status": "ready",
            "execution_status": "ok",
            "runtime_error_count": 0,
            "selected_candidate_set_matches_review": True,
            "derived_outputs_match_reviewed_tolerance": True,
            "retrieval_planner_evaluator_embedding_store_calls": 0,
        },
        "claim_boundary": (
            "Tests compiler selection and formula construction over reviewed compact "
            "sources only; it is not retrieval, full-agent, evaluator, or release evidence."
        ),
    }


def _verify_manifest(
    manifest_path: Path,
    *,
    approved_sha256: str | None = None,
) -> tuple[dict[str, Any], str]:
    path = Path(manifest_path).resolve()
    manifest_bytes = path.read_bytes()
    manifest_sha256 = _sha256_bytes(manifest_bytes)
    if approved_sha256 is not None and approved_sha256 != manifest_sha256:
        raise ValueError("approved manifest SHA-256 does not match manifest bytes")
    manifest = json.loads(manifest_bytes.decode("utf-8"))
    if manifest.get("schema") != ADMISSION_SCHEMA_VERSION:
        raise ValueError("unsupported compiler selection admission schema")
    corpus_info = dict(dict(manifest.get("inputs") or {}).get("corpus") or {})
    corpus_path = PROJECT_ROOT / str(corpus_info.get("path") or "")
    if _sha256_file(corpus_path) != str(corpus_info.get("sha256") or ""):
        raise ValueError("reviewed corpus hash mismatch")
    runtime_expected = dict(
        dict(manifest.get("inputs") or {}).get("runtime_build") or {}
    )
    runtime_actual = _tracked_runtime_build()
    for field in ("git_commit", "file_count", "sha256"):
        if runtime_actual.get(field) != runtime_expected.get(field):
            raise ValueError(f"runtime build mismatch: {field}")
    return manifest, manifest_sha256


def rehearse_admission_manifest(manifest_path: Path) -> dict[str, Any]:
    manifest, manifest_sha256 = _verify_manifest(manifest_path)
    corpus_path = PROJECT_ROOT / manifest["inputs"]["corpus"]["path"]
    result = rehearse_reviewed_compiler_selection(corpus_path)
    expected = dict(manifest["inputs"]["rehearsal"])
    checks = {
        "manifest_pending_approval": (
            manifest["authorization"]["status"]
            == "pending_separate_user_approval"
        ),
        "provider_network_calls_zero": result["provider_network_calls"] == 0,
        "compiler_calls_match": (
            result["summary"]["compiler_invocation_count"]
            == expected["compiler_invocation_count"]
        ),
        "islands_match": (
            result["summary"]["compiler_island_count"]
            == expected["compiler_island_count"]
        ),
        "prompt_fingerprint_matches": (
            result["summary"]["prompt_fingerprint"]
            == expected["prompt_fingerprint"]
        ),
        "all_cases_pass": result["status"] == "passed",
    }
    return {
        "schema": REHEARSAL_SCHEMA_VERSION,
        "status": "passed" if all(checks.values()) else "failed",
        "manifest_sha256": manifest_sha256,
        "checks": checks,
        "observation": result,
    }


def run_approved_manifest(
    manifest_path: Path,
    *,
    approved_manifest_sha256: str,
    provider_factory: Callable[[Mapping[str, Any], GeminiUsageCallbackHandler], Any]
    | None = None,
) -> dict[str, Any]:
    """Consume one explicit manifest approval and run no other provider work."""

    manifest, manifest_sha256 = _verify_manifest(
        manifest_path,
        approved_sha256=approved_manifest_sha256,
    )
    provider_spec = dict(manifest.get("provider") or {})
    callback = GeminiUsageCallbackHandler()
    callback.reset_current_thread()
    factory = provider_factory or _create_google_compiler
    llm = factory(provider_spec, callback)
    corpus_path = PROJECT_ROOT / manifest["inputs"]["corpus"]["path"]
    result = evaluate_reviewed_compiler_selection(
        corpus_path,
        llm,
        run_mode="provider",
        usage_callback=callback,
        stop_on_case_failure=True,
    )
    usage = callback.snapshot_current_thread()
    result["schema_version"] = RESULT_SCHEMA_VERSION
    result["manifest_sha256"] = manifest_sha256
    result["provider_network_calls"] = int(usage.get("api_calls") or 0)
    result["usage"] = usage
    result["estimated_cost_usd"] = estimate_gemini_cost_usd(
        usage,
        dict(manifest.get("pricing") or {}),
    )
    result["cost_authorization_maximum_usd"] = float(
        manifest["authorization"]["maximum"]
    )
    return result


def _create_google_compiler(
    provider_spec: Mapping[str, Any],
    callback: GeminiUsageCallbackHandler,
) -> Any:
    dotenv = {
        key: str(value)
        for key, value in dotenv_values(PROJECT_ROOT / ".env").items()
        if value is not None
    }
    api_key = str(
        os.environ.get("GOOGLE_API_KEY") or dotenv.get("GOOGLE_API_KEY") or ""
    ).strip()
    if not api_key:
        raise ValueError("GOOGLE_API_KEY is required for approved compiler selection")
    from langchain_google_genai import ChatGoogleGenerativeAI

    return ChatGoogleGenerativeAI(
        model=str(provider_spec.get("model") or DEFAULT_MODEL),
        temperature=float(provider_spec.get("temperature") or 0),
        max_tokens=int(
            provider_spec.get("max_output_tokens") or DEFAULT_MAX_OUTPUT_TOKENS
        ),
        retries=int(provider_spec.get("provider_client_retries") or 0),
        google_api_key=api_key,
        callbacks=[callback],
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    prepare = subparsers.add_parser("prepare")
    prepare.add_argument("--corpus", type=Path, required=True)
    prepare.add_argument("--manifest", type=Path, required=True)
    prepare.add_argument("--result", type=Path, required=True)
    prepare.add_argument("--cost-cap-usd", type=float, required=True)

    rehearse = subparsers.add_parser("rehearse")
    rehearse.add_argument("--manifest", type=Path, required=True)
    rehearse.add_argument("--output", type=Path, required=True)

    run = subparsers.add_parser("run")
    run.add_argument("--manifest", type=Path, required=True)
    run.add_argument("--approved-manifest-sha256", required=True)
    run.add_argument("--output", type=Path, required=True)

    args = parser.parse_args(argv)
    if args.command == "prepare":
        if args.manifest.exists():
            parser.error("manifest already exists")
        manifest = build_admission_manifest(
            corpus_path=args.corpus,
            manifest_path=args.manifest,
            result_path=args.result,
            cost_cap_usd=args.cost_cap_usd,
        )
        _write_new_json(args.manifest, manifest)
        print(
            json.dumps(
                {
                    "status": "prepared",
                    "manifest": args.manifest.as_posix(),
                    "manifest_sha256": _sha256_file(args.manifest),
                    "likely_estimate_usd": manifest["pricing"][
                        "likely_estimate_usd"
                    ],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    if args.output.exists():
        parser.error("output already exists")
    if args.command == "rehearse":
        result = rehearse_admission_manifest(args.manifest)
    else:
        manifest, _ = _verify_manifest(
            args.manifest,
            approved_sha256=args.approved_manifest_sha256,
        )
        expected_output = (
            PROJECT_ROOT / str(manifest["execution"]["result_path"])
        ).resolve()
        if args.output.resolve() != expected_output:
            parser.error("output path does not match approved manifest")
        result = run_approved_manifest(
            args.manifest,
            approved_manifest_sha256=args.approved_manifest_sha256,
        )
    _write_new_json(args.output, result)
    print(
        json.dumps(
            {
                "status": result["status"],
                "output": args.output.as_posix(),
                "manifest_sha256": result["manifest_sha256"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
