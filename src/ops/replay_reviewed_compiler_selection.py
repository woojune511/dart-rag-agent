"""Bounded compiler-only evaluation for the reviewed runtime corpus.

The harness deliberately omits retrieval, planning, evaluation, embeddings, and
stores.  It gives the current semantic compiler the reviewed question,
obligations, and compact candidate catalog, then validates and executes the
result with the production contracts.  The default rehearsal substitutes the
reviewed programs for a provider and therefore cannot make a network call.
Raw fixtures are normalized; explicit hash-bound runtime projections retain the
source pipeline's context-aware values without a second partial normalization.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import subprocess
from time import perf_counter
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
from src.utils.gemini_usage_counts import (
    estimate_gemini_cost_usd,
    extract_gemini_usage_counts,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
ADMISSION_SCHEMA_VERSION = "reviewed_compiler_selection_admission_v2"
REHEARSAL_SCHEMA_VERSION = "reviewed_compiler_selection_rehearsal_v2"
RESULT_SCHEMA_VERSION = "reviewed_compiler_selection_result_v2"
COMPARISON_ADMISSION_SCHEMA_VERSION = "reviewed_compiler_model_comparison_admission_v1"
COMPARISON_RESULT_SCHEMA_VERSION = "reviewed_compiler_model_comparison_result_v1"
COMPARISON_REHEARSAL_SCHEMA_VERSION = "reviewed_compiler_model_comparison_rehearsal_v1"
DEFAULT_PROVIDER = "google"
DEFAULT_MODEL = "gemini-2.5-flash"
DEFAULT_MAX_OUTPUT_TOKENS = 4096
DEFAULT_THINKING_BUDGET = 1024
OFFICIAL_STANDARD_PRICING = {
    "input_per_million_tokens_usd": 0.30,
    "output_per_million_tokens_usd": 2.50,
    "thinking_per_million_tokens_usd": 2.50,
}
OFFICIAL_PRICING_URL = "https://ai.google.dev/gemini-api/docs/pricing"
# Reviewed standard text pricing for the bounded <= 200k-token comparison lane.
COMPARISON_MODEL_PRICING = {
    "gemini-2.5-pro": {
        "input_per_million_tokens_usd": 1.25,
        "output_per_million_tokens_usd": 10.0,
        "thinking_per_million_tokens_usd": 10.0,
        "cached_input_per_million_tokens_usd": 0.125,
    },
}


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


def _final_response_text(raw: Any) -> str:
    """Keep only final text, never thought blocks, signatures, or SDK metadata."""
    content = getattr(raw, "content", "")
    if isinstance(content, str):
        return content
    return "".join(
        block if isinstance(block, str) else str(block.get("text") or "")
        for block in content or []
        if isinstance(block, str)
        or (isinstance(block, Mapping) and block.get("type") == "text")
    )


class _RecordingStructuredInvoker:
    def __init__(self, delegate: Any, records: list[dict[str, Any]]) -> None:
        self._delegate = delegate
        self._records = records

    def invoke(self, prompt: Any) -> Any:
        payload = _prompt_bytes(prompt)
        record: dict[str, Any] = {
            "prompt_bytes": len(payload),
            "prompt_sha256": _sha256_bytes(payload),
            "response": {
                "raw_response_available": False,
                "capture_source": "langchain_ai_message_before_parser",
                "final_text": None,
                "finish_reason": None,
                "usage": None,
                "parsing_error": None,
            },
        }
        self._records.append(record)
        try:
            result = self._delegate.invoke(prompt)
        except Exception as error:
            # Transport errors can contain URLs/headers. Keep only their class;
            # parser errors below are restricted to the final structured output.
            record["invocation_error_type"] = type(error).__name__
            raise
        raw = result["raw"]
        parsing_error = result["parsing_error"]
        response = record["response"]
        if raw is not None:
            response.update({
                "raw_response_available": True,
                "final_text": _final_response_text(raw),
                "finish_reason": raw.response_metadata.get("finish_reason"),
                "usage": extract_gemini_usage_counts(raw),
            })
        if parsing_error is not None:
            response["parsing_error"] = {
                "type": type(parsing_error).__name__,
                "message": str(parsing_error),
            }
            # Preserve the compiler's existing single-island retry behavior.
            raise parsing_error
        return result["parsed"]


class _RecordingLLM:
    def __init__(self, delegate: Any) -> None:
        self._delegate = delegate
        self.records: list[dict[str, Any]] = []

    def with_structured_output(self, model: Any) -> _RecordingStructuredInvoker:
        return _RecordingStructuredInvoker(
            self._delegate.with_structured_output(model, include_raw=True),
            self.records,
        )


class _ReviewedProgramQueue:
    """Provider-free structured-output substitute used only by rehearsal."""

    def __init__(self, responses: Sequence[SemanticCalculationProgram]) -> None:
        self._responses = list(responses)
        self.requested_models: list[str] = []

    def with_structured_output(self, model: Any, *, include_raw: bool) -> "_ReviewedProgramQueue":
        if not include_raw:
            raise AssertionError("rehearsal must exercise the raw-response adapter")
        self.requested_models.append(str(getattr(model, "__name__", "")))
        return self

    def invoke(self, _prompt: Any) -> dict[str, Any]:
        if not self._responses:
            raise AssertionError("unexpected reviewed compiler rehearsal invocation")
        return {"raw": None, "parsed": self._responses.pop(0), "parsing_error": None}

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


def _compiler_case_catalog(
    case: Mapping[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, bool]]:
    """Separate raw fixture normalization from already projected runtime facts.

    A runtime projection must be frozen from the current source pipeline before
    admission. Its hash checks identity, not financial correctness. Re-normalizing
    only raw_value/raw_unit would discard context-derived scales and dimensions.
    """
    raw = [dict(item) for item in (case.get("candidate_catalog") or []) if isinstance(item, Mapping)]
    spec = dict(case.get("catalog_input") or {})
    kind = str(spec.get("kind") or "normalized_fixture_v1")
    if kind == "runtime_projection_v1":
        if _sha256_bytes(_canonical_bytes(raw)) != spec.get("sha256"):
            raise ValueError("runtime catalog fingerprint mismatch")
        return deepcopy(raw), {"runtime_catalog_fingerprint_matches": True}
    if kind != "normalized_fixture_v1":
        raise ValueError("unsupported compiler catalog input kind")
    catalog, normalization = _materialize_catalog(raw)
    return catalog, {"normalization_matches_review": all(
        bool(item.get("value_matches")) and bool(item.get("unit_matches"))
        for item in normalization
    )}


def _island_obligation_ids(case: Mapping[str, Any]) -> list[list[str]]:
    catalog, _ = _compiler_case_catalog(case)
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
            response = _program_for_obligations(program, obligation_ids)
            # A declared abstention still takes the runtime's one internal retry.
            # This only schedules offline substitutes; it never drives live retries.
            abstains = response.missing_obligation_ids or response.ambiguous_obligation_ids
            responses.extend([response] * (2 if abstains else 1))
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
    stop_on_provider_error: bool = False,
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
        started = perf_counter() if run_mode == "provider" else None
        catalog, catalog_checks = _compiler_case_catalog(case)
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
            **catalog_checks,
            "validation_matches_expectation": (
                validation.get("status") == expected.get("validation_status", "ready")
            ),
            "execution_matches_expectation": (
                execution.get("status") == expected.get("execution_status", "ok")
            ),
            "resolution_matches_expectation": all(
                list(validation.get(field) or []) == list(expected.get(field) or [])
                for field in ("missing_obligation_ids", "ambiguous_obligation_ids")
            ),
            "selected_candidate_ids_expected": (
                len(selected_ids) == len(expected_ids)
                and set(selected_ids) == set(expected_ids)
            ),
            "expected_outputs_match": (
                all(item["matches"] for item in output_checks)
                if expected_outputs
                else expected.get("execution_status", "ok") != "ok" and not actual_by_owner
            ),
            "compiler_calls_bounded": (
                island_count <= compiler_call_count <= island_count * 2
            ),
            "prompt_capture_matches_calls": len(case_prompts) == compiler_call_count,
            "execution_errors_zero": not list(execution.get("execution_errors") or []),
            "validation_errors_zero": not list(validation.get("errors") or []),
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
        if started is not None:
            results[-1]["elapsed_seconds"] = perf_counter() - started
        provider_error = any(record.get("invocation_error_type") for record in case_prompts)
        if (stop_on_provider_error and provider_error) or (stop_on_case_failure and not passed):
            break

    passed_count = sum(item["status"] == "passed" for item in results)
    prompt_bytes = sum(
        int(record.get("prompt_bytes") or 0)
        for result in results
        for record in result["prompt_records"]
    )
    result = {
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
        "fixture_origin": corpus.get("fixture_origin", "source_derived_reviewed"),
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
                _canonical_bytes([
                    {key: record[key] for key in ("prompt_bytes", "prompt_sha256")}
                    for record in recording_llm.records
                ])
            ),
        },
        "cases": results,
    }
    if stop_on_provider_error:
        result["stopped_for_provider_error"] = any(
            record.get("invocation_error_type")
            for case in results for record in case["prompt_records"]
        )
    return result


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


def _validate_token_budgets(max_output_tokens: Any, thinking_budget: Any) -> None:
    if type(max_output_tokens) is not int or max_output_tokens <= 0:
        raise ValueError("max_output_tokens must be a positive integer")
    if type(thinking_budget) is not int or not 0 <= thinking_budget < max_output_tokens:
        raise ValueError("thinking_budget must be explicit, non-negative, and below max_output_tokens")


def _validate_comparison_model(model: str, max_output_tokens: int, thinking_budget: int) -> None:
    if model not in COMPARISON_MODEL_PRICING:
        raise ValueError("comparison model must differ from the baseline and have reviewed pricing")
    if not 128 <= thinking_budget <= 24576 or max_output_tokens > 65536:
        raise ValueError("shared comparison budgets require thinking 128..24576 and output <= 65536")


def build_admission_manifest(
    *,
    corpus_path: Path,
    manifest_path: Path,
    result_path: Path,
    cost_cap_usd: float,
    max_output_tokens: int = DEFAULT_MAX_OUTPUT_TOKENS,
    thinking_budget: int = DEFAULT_THINKING_BUDGET,
    runtime_build: Mapping[str, Any] | None = None,
    model: str = DEFAULT_MODEL,
    comparison_model: str | None = None,
) -> dict[str, Any]:
    _validate_token_budgets(max_output_tokens, thinking_budget)
    if model != DEFAULT_MODEL:
        _validate_comparison_model(model, max_output_tokens, thinking_budget)
    selected_model_rates = OFFICIAL_STANDARD_PRICING if model == DEFAULT_MODEL else COMPARISON_MODEL_PRICING[model]
    model_rates = {model: selected_model_rates}
    if comparison_model is not None:
        if model != DEFAULT_MODEL:
            raise ValueError("comparison baseline must remain the default model")
        _validate_comparison_model(comparison_model, max_output_tokens, thinking_budget)
        model_rates[DEFAULT_MODEL] = {**OFFICIAL_STANDARD_PRICING, "cached_input_per_million_tokens_usd": 0.03}
        model_rates[comparison_model] = COMPARISON_MODEL_PRICING[comparison_model]
    corpus_abs = Path(corpus_path).resolve()
    corpus = _load_corpus(corpus_abs)
    rehearsal = rehearse_reviewed_compiler_selection(corpus_abs)
    if rehearsal["status"] != "passed":
        raise ValueError("reviewed compiler rehearsal must pass before admission")
    initial_calls = int(rehearsal["summary"]["compiler_island_count"])
    rehearsal_calls = int(rehearsal["summary"]["compiler_invocation_count"])
    maximum_calls = initial_calls * 2
    prompt_bytes = int(rehearsal["summary"]["prompt_bytes"])
    reviewed_output_bytes = sum(
        len(_canonical_bytes(program.model_dump(mode="json")))
        for program in _reviewed_response_queue(corpus)
    )
    likely_input_tokens = math.ceil(prompt_bytes / 3)
    likely_output_tokens = math.ceil(reviewed_output_bytes / 3)
    by_model = {
        model: {
            **rates,
            "likely_estimate_usd": (
                likely_input_tokens / 1_000_000 * rates["input_per_million_tokens_usd"]
                + likely_output_tokens / 1_000_000 * rates["output_per_million_tokens_usd"]
                + rehearsal_calls * thinking_budget / 1_000_000 * rates["thinking_per_million_tokens_usd"]
            ),
            "retry_bounded_planning_estimate_usd": (
                likely_input_tokens * 2 / 1_000_000 * rates["input_per_million_tokens_usd"]
                + maximum_calls * max_output_tokens / 1_000_000 * rates["output_per_million_tokens_usd"]
            ),
        }
        for model, rates in model_rates.items()
    }
    likely_cost = sum(p["likely_estimate_usd"] for p in by_model.values())
    retry_bounded_planning_cost = sum(p["retry_bounded_planning_estimate_usd"] for p in by_model.values())
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
    manifest = {
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
            "progress_heartbeat_sec": 30,
            "heartbeat_mechanism": "foreground subprocess monitor; never restart the runner",
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
            "model": model,
            "temperature": 0,
            "max_output_tokens": max_output_tokens,
            "thinking_budget": thinking_budget,
            "token_budget_semantics": (
                "max_output_tokens includes final text and thinking; thinking_budget "
                "is guidance, not a guaranteed reservation for either component"
            ),
            "provider_client_retries": 0,
            "structured_output": "SemanticCalculationProgram",
            "response_capture": "final_text_finish_reason_usage_and_parsing_error",
            "thought_content_recorded": False,
            "required_credential_name": "GOOGLE_API_KEY",
            "credential_present": bool(
                os.environ.get("GOOGLE_API_KEY") or dotenv.get("GOOGLE_API_KEY")
            ),
            "credential_value_recorded": False,
        },
        "pricing": {
            **selected_model_rates,
            "source": OFFICIAL_PRICING_URL,
            "likely_estimate_usd": likely_cost,
            "retry_bounded_planning_estimate_usd": retry_bounded_planning_cost,
            "estimate_method": (
                "likely uses rehearsal UTF-8 bytes divided by three plus each rehearsed "
                "call's thinking budget; retry-bounded "
                "planning doubles likely input and prices every allowed call at "
                "the configured inclusive output-token maximum (thinking not added twice)"
            ),
            "rehearsal_prompt_bytes": prompt_bytes,
            "rehearsal_reviewed_output_bytes": reviewed_output_bytes,
        },
        "inputs": {
            "corpus": {
                "path": corpus_rel,
                "sha256": _sha256_file(corpus_abs),
                "case_count": len(case_ids),
                "origin": corpus.get("fixture_origin", "source_derived_reviewed"),
            },
            "runtime_build": dict(runtime_build or _tracked_runtime_build()),
            "prompt_contract": "semantic_program_candidate_payload_v6",
            "diagnostics_contract": "semantic_candidate_stage_diagnostics_v9",
            "rehearsal": {
                "compiler_island_count": rehearsal["summary"][
                    "compiler_island_count"
                ],
                "compiler_invocation_count": rehearsal_calls,
                "prompt_fingerprint": rehearsal["summary"]["prompt_fingerprint"],
            },
        },
        "transmission_scope": {
            "destination": "Google Gemini API",
            "included": [
                f"{len(case_ids)} question texts",
                "ordered answer obligations",
                "compact source-bundle excerpts",
                "candidate raw values and provenance metadata",
                "retry validation feedback and validated read-only dependency outputs only when an island fails",
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
            "all_cases_match_declared_expectations": True,
            "validation_and_execution_status": "per_case_corpus_expectation",
            "missing_and_ambiguous_obligation_ids_match_expectation": True,
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
    if comparison_model is not None:
        manifest["schema"] = COMPARISON_ADMISSION_SCHEMA_VERSION
        manifest["provider"].pop("model")
        manifest["provider"]["models"] = list(model_rates)
        manifest["execution"].update({
            "mode": "reviewed_compiler_model_comparison",
            "initial_compiler_calls": initial_calls * len(model_rates),
            "maximum_compiler_calls_with_internal_retry": maximum_calls * len(model_rates),
            "stop_after_first_failed_question": False,
            "stop_after_provider_error": True,
            "case_failure_policy": "record failures and continue bounded comparison; never promote them to passes",
        })
        for field in OFFICIAL_STANDARD_PRICING:
            manifest["pricing"].pop(field)
        manifest["pricing"]["by_model"] = by_model
        manifest["pricing"]["input_price_tier"] = "standard text, each request <= 200000 input tokens"
        manifest["comparison_controls"] = {
            "varied": ["model"],
            "fixed": ["corpus", "question_order", "initial_prompt", "schema", "temperature", "output_budget", "thinking_budget", "internal_retry_policy"],
            "retry_inputs": "model-specific validation feedback and validated read-only dependencies",
            "trials_per_model": 1,
            "rehearsal_counts_are_per_model": True,
            "latency_scope": "per-case compilation, validation, and execution; paid run only",
        }
        manifest["claim_boundary"] = (
            "One budget-matched diagnostic trial per model, not general model superiority, "
            "retrieval, full-agent, evaluator, or release evidence. Failed cases remain failed."
        )
    return manifest


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
    if manifest.get("schema") not in (ADMISSION_SCHEMA_VERSION, COMPARISON_ADMISSION_SCHEMA_VERSION):
        raise ValueError("unsupported compiler selection admission schema")
    provider = dict(manifest.get("provider") or {})
    _validate_token_budgets(provider.get("max_output_tokens"), provider.get("thinking_budget"))
    if manifest["schema"] == COMPARISON_ADMISSION_SCHEMA_VERSION:
        models = provider.get("models") or []
        if len(models) != 2 or models[0] != DEFAULT_MODEL:
            raise ValueError("comparison requires the baseline and one reviewed model")
        _validate_comparison_model(models[1], provider["max_output_tokens"], provider["thinking_budget"])
    elif provider.get("model", DEFAULT_MODEL) != DEFAULT_MODEL:
        _validate_comparison_model(provider["model"], provider["max_output_tokens"], provider["thinking_budget"])
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
    comparison = manifest["schema"] == COMPARISON_ADMISSION_SCHEMA_VERSION
    result = (
        _evaluate_model_comparison(manifest, run_mode="rehearsal")
        if comparison else rehearse_reviewed_compiler_selection(corpus_path)
    )
    observations = result["model_results"] if comparison else [result]
    expected = dict(manifest["inputs"]["rehearsal"])
    checks = {
        "manifest_pending_approval": (
            manifest["authorization"]["status"]
            == "pending_separate_user_approval"
        ),
        "provider_network_calls_zero": result["provider_network_calls"] == 0,
        "compiler_calls_match": (
            all(item["summary"]["compiler_invocation_count"] == expected["compiler_invocation_count"] for item in observations)
        ),
        "islands_match": (
            all(item["summary"]["compiler_island_count"] == expected["compiler_island_count"] for item in observations)
        ),
        "prompt_fingerprint_matches": (
            all(item["summary"]["prompt_fingerprint"] == expected["prompt_fingerprint"] for item in observations)
        ),
        "all_cases_pass": result["status"] == "passed",
    }
    return {
        "schema": COMPARISON_REHEARSAL_SCHEMA_VERSION if comparison else REHEARSAL_SCHEMA_VERSION,
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
    if manifest["schema"] == COMPARISON_ADMISSION_SCHEMA_VERSION:
        result = _evaluate_model_comparison(manifest, run_mode="provider", provider_factory=provider_factory)
        result["manifest_sha256"] = manifest_sha256
        return result
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
    # include_raw runs the model in LangChain's RunnableParallel worker. This
    # callback belongs only to this run; its global snapshot includes that worker.
    usage = callback.snapshot_global()
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


def _evaluate_model_comparison(
    manifest: Mapping[str, Any],
    *,
    run_mode: str,
    provider_factory: Callable[..., Any] | None = None,
) -> dict[str, Any]:
    """Same compiler path and inputs; fresh queue/client and usage owner per model."""
    corpus_path = PROJECT_ROOT / manifest["inputs"]["corpus"]["path"]
    model_results = []
    initialization_error = None
    for model in manifest["provider"]["models"]:
        callback = GeminiUsageCallbackHandler()
        callback.reset_current_thread()
        spec = {key: value for key, value in manifest["provider"].items() if key != "models"}
        spec["model"] = model
        if run_mode == "rehearsal":
            llm = _ReviewedProgramQueue(_reviewed_response_queue(_load_corpus(corpus_path)))
        else:
            try:
                llm = (provider_factory or _create_google_compiler)(spec, callback)
            except Exception as error:
                # Keep completed model evidence even if the next client cannot start.
                initialization_error = {"model": model, "type": type(error).__name__}
                break
        observation = evaluate_reviewed_compiler_selection(
            corpus_path, llm, run_mode=run_mode,
            usage_callback=callback if run_mode == "provider" else None,
            stop_on_case_failure=False, stop_on_provider_error=True,
        )
        usage = callback.snapshot_global()
        observation.update({
            "provider_model": model,
            "provider_network_calls": int(usage.get("api_calls") or 0),
            "usage": usage,
            "estimated_cost_usd": estimate_gemini_cost_usd(usage, manifest["pricing"]["by_model"][model]),
        })
        if run_mode == "rehearsal" and llm.remaining_response_count:
            observation["status"] = "failed"
        model_results.append(observation)
        if observation["stopped_for_provider_error"]:
            break
    return {
        "schema_version": COMPARISON_RESULT_SCHEMA_VERSION,
        "run_mode": run_mode,
        "status": "passed" if len(model_results) == len(manifest["provider"]["models"])
        and all(item["status"] == "passed" for item in model_results) else "failed",
        "claim_boundary": manifest["claim_boundary"],
        "provider_initialization_error": initialization_error,
        "provider_network_calls": sum(item["provider_network_calls"] for item in model_results),
        "estimated_cost_usd": sum(item["estimated_cost_usd"] for item in model_results),
        "cost_authorization_maximum_usd": manifest["authorization"]["maximum"],
        "summary": {
            key: sum(item["summary"][key] for item in model_results)
            for key in ("executed_case_count", "passed_case_count", "failed_case_count",
                        "compiler_island_count", "compiler_invocation_count", "compiler_retry_count")
        },
        "model_results": model_results,
    }


def _create_google_compiler(
    provider_spec: Mapping[str, Any],
    callback: GeminiUsageCallbackHandler,
) -> Any:
    _validate_token_budgets(provider_spec.get("max_output_tokens"), provider_spec.get("thinking_budget"))
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
        max_tokens=provider_spec["max_output_tokens"],
        thinking_budget=provider_spec["thinking_budget"],
        include_thoughts=False,
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
    prepare.add_argument("--max-output-tokens", type=int, default=DEFAULT_MAX_OUTPUT_TOKENS)
    prepare.add_argument("--thinking-budget", type=int, default=DEFAULT_THINKING_BUDGET)
    prepare.add_argument("--model", choices=(DEFAULT_MODEL, *COMPARISON_MODEL_PRICING), default=DEFAULT_MODEL)
    prepare.add_argument("--comparison-model", choices=tuple(COMPARISON_MODEL_PRICING))

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
            max_output_tokens=args.max_output_tokens,
            thinking_budget=args.thinking_budget,
            model=args.model,
            comparison_model=args.comparison_model,
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
