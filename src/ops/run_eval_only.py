"""
Run a store-fixed end-to-end evaluation against an existing benchmark bundle.

This tool skips parse / ingest / screening and reuses the persisted Chroma
collection from a previous benchmark output directory, but it still re-runs the
current agent and evaluator for each question.

Important:
- This is NOT a historical answer replay tool.
- It does NOT reuse the old answer / runtime_evidence / calculation trace.
- Use retrospective_* replay scripts when you need evaluator-only comparisons
  against the exact same historical outputs.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if __package__ in {None, ""} and str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.storage.embedding_config import DEFAULT_EMBEDDING_MODEL, DEFAULT_EMBEDDING_PROVIDER

VectorStoreManager = None

logger = logging.getLogger(__name__)


def _load_json(path: Path) -> Any:
    with open(path, encoding="utf-8") as file:
        return json.load(file)


def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _slugify(value: str) -> str:
    lowered = "".join(ch.lower() if ch.isalnum() else "-" for ch in value)
    return "-".join(part for part in lowered.split("-") if part)


def _looks_like_windows_absolute_path(path_text: str) -> bool:
    return len(path_text) >= 3 and path_text[1] == ":" and path_text[2] in {"\\", "/"}


def _normalise_path(path_value: str | Path) -> Path:
    path_text = str(path_value)
    path = Path(path_text)
    if not path.is_absolute() and not _looks_like_windows_absolute_path(path_text):
        path = (PROJECT_ROOT / path).resolve()
    parts_lower = [part.lower() for part in path.parts]
    for index in range(len(parts_lower) - 1):
        if parts_lower[index] == "data" and parts_lower[index + 1] == "reports":
            return (PROJECT_ROOT / "data" / "reports" / Path(*path.parts[index + 2 :])).resolve()
    return path


def _company_output_subdir(company_run: Dict[str, Any], defaults: Dict[str, Any]) -> str:
    if company_run.get("output_subdir"):
        return str(company_run["output_subdir"])
    metadata = _deep_merge(defaults.get("metadata", {}), company_run.get("defaults", {}).get("metadata", {}))
    company = str(metadata.get("company") or company_run.get("id") or "company")
    year = str(metadata.get("year") or "").strip()
    parts = [_slugify(company)]
    if year:
        parts.append(year)
    return "-".join(part for part in parts if part)


def _filter_experiments_by_candidate_ids(
    experiments: List[Dict[str, Any]],
    candidate_ids: List[str],
) -> List[Dict[str, Any]]:
    if not candidate_ids:
        return experiments
    requested = [candidate_id for candidate_id in candidate_ids if candidate_id]
    requested_set = set(requested)
    filtered = [experiment for experiment in experiments if str(experiment.get("id")) in requested_set]
    missing = [candidate_id for candidate_id in requested if candidate_id not in {str(exp.get("id")) for exp in filtered}]
    if missing:
        raise ValueError(f"Unknown candidate_ids requested: {missing}")
    return filtered


def _is_path_like_key(key: str) -> bool:
    lowered = key.lower()
    return lowered.endswith("_path") or "directory" in lowered


def _sanitize_settings(value: Any, key: str = "") -> Any:
    if isinstance(value, dict):
        sanitised: Dict[str, Any] = {}
        for child_key, child_value in value.items():
            if _is_path_like_key(child_key):
                continue
            sanitised[child_key] = _sanitize_settings(child_value, child_key)
        return sanitised
    if isinstance(value, list):
        return [_sanitize_settings(item, key) for item in value]
    return value


def _resolve_company_run(matrix: Dict[str, Any], company_run_id: str) -> Dict[str, Any]:
    company_runs = matrix.get("company_runs", [])
    for company_run in company_runs:
        if str(company_run.get("id")) == company_run_id:
            return company_run
    raise ValueError(f"Unknown company_run id: {company_run_id}")


def _resolve_merged_experiments(matrix: Dict[str, Any], company_run: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    defaults = matrix.get("defaults", {})
    shared_experiments = matrix.get("experiments", [])
    company_defaults = _deep_merge(defaults, company_run.get("defaults", {}))
    experiments = company_run.get("experiments", shared_experiments)
    candidate_ids = list(company_run.get("candidate_ids") or defaults.get("candidate_ids") or [])
    experiments = _filter_experiments_by_candidate_ids(list(experiments), candidate_ids)

    merged_by_id: Dict[str, Dict[str, Any]] = {}
    for experiment in experiments:
        merged = _deep_merge(company_defaults, experiment)
        experiment_id = str(merged.get("id") or "")
        if not experiment_id:
            raise ValueError("Each experiment must include an id.")
        merged_by_id[experiment_id] = merged
    return merged_by_id


def _load_existing_results(company_output_dir: Path) -> List[Dict[str, Any]]:
    result_path = company_output_dir / "results.json"
    if not result_path.exists():
        raise FileNotFoundError(f"Existing benchmark results not found: {result_path}")
    payload = _load_json(result_path)
    return list(payload.get("results", []) or [])


def _validate_store_for_eval_only(store_info: Dict[str, Any], *, allow_degraded_retrieval: bool) -> Dict[str, Any]:
    vector_store_manager_cls = VectorStoreManager
    if vector_store_manager_cls is None:
        from src.storage.vector_store import VectorStoreManager as vector_store_manager_cls

    vsm = vector_store_manager_cls(
        persist_directory=store_info["persist_directory"],
        collection_name=store_info["collection_name"],
        embedding_provider=store_info.get("embedding_provider", DEFAULT_EMBEDDING_PROVIDER),
        embedding_model_name=store_info.get("embedding_model_name", DEFAULT_EMBEDDING_MODEL),
        allow_query_embedding_fallback=allow_degraded_retrieval,
    )
    health = vsm.validate_vector_index()
    if health.get("ok"):
        logger.info(
            "Vector store health check passed for %s (probe results=%s)",
            store_info["persist_directory"],
            health.get("result_count"),
        )
        return health

    message = (
        "Vector store health check failed before eval-only execution. "
        f"persist_directory={store_info['persist_directory']} "
        f"collection={store_info['collection_name']} "
        f"error={health.get('error')}"
    )
    if allow_degraded_retrieval:
        logger.warning("%s; continuing because --allow-degraded-retrieval was set.", message)
        return health
    raise RuntimeError(
        message
        + ". Rebuild/repair the store with `python -m src.ops.rebuild_vector_store`, "
        "or rerun with --allow-degraded-retrieval for a diagnostic BM25 fallback run."
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run store-fixed full evaluation using an existing benchmark store (re-runs current agent/evaluator)."
    )
    parser.add_argument(
        "--config",
        required=True,
        help="Path to the benchmark profile JSON.",
    )
    parser.add_argument(
        "--source-output-dir",
        required=True,
        help="Existing benchmark output root that already contains stores/results. The persisted store is reused, but answers are regenerated.",
    )
    parser.add_argument(
        "--output-dir",
        required=True,
        help="Directory where store-fixed end-to-end evaluation results will be written.",
    )
    parser.add_argument(
        "--company-run-id",
        required=True,
        help="Target company_run id from the profile.",
    )
    parser.add_argument(
        "--experiment-id",
        action="append",
        default=[],
        help="Optional experiment id(s) to evaluate. Defaults to all results found for the company bundle.",
    )
    parser.add_argument(
        "--allow-degraded-retrieval",
        action="store_true",
        help=(
            "Continue when the persisted vector index health check fails by enabling existing BM25 fallback. "
            "Use only for diagnostic runs; official gate eval-only remains strict by default."
        ),
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

    config_path = _normalise_path(args.config)
    source_output_root = _normalise_path(args.source_output_dir)
    output_root = _normalise_path(args.output_dir)

    matrix = _load_json(config_path)
    defaults = matrix.get("defaults", {})
    screening_config = matrix.get("screening", {})
    full_eval_config = matrix.get("full_evaluation", {})
    company_run = _resolve_company_run(matrix, args.company_run_id)

    company_output_subdir = _company_output_subdir(company_run, defaults)
    source_company_output_dir = source_output_root / company_output_subdir
    target_company_output_dir = output_root / company_output_subdir

    existing_results = _load_existing_results(source_company_output_dir)
    merged_by_id = _resolve_merged_experiments(matrix, company_run)

    from src.ops.benchmark_runner import _slugify

    requested_ids = set(args.experiment_id or [])
    selected_results: List[Dict[str, Any]] = []
    for result in existing_results:
        experiment_id = str(result.get("id") or "")
        if requested_ids and experiment_id not in requested_ids:
            continue
        if experiment_id not in merged_by_id:
            logger.warning("Skipping result with unknown experiment id in current config: %s", experiment_id)
            continue
        logger.info(
            "Running store-fixed full evaluation for %s / %s (current agent/evaluator will be re-executed)",
            args.company_run_id,
            experiment_id,
        )
        updated = dict(result)
        # Re-map persist_directory to source-output-dir in case results were generated on a different machine
        local_store_dir = source_company_output_dir / "stores" / _slugify(experiment_id)
        if local_store_dir.exists():
            updated = dict(result)
            updated["store"] = dict(result.get("store") or {})
            updated["store"]["persist_directory"] = str(local_store_dir)
            logger.info("Re-mapped store to local path: %s", local_store_dir)
        updated["store"] = dict(updated.get("store") or {})
        health = _validate_store_for_eval_only(
            updated["store"],
            allow_degraded_retrieval=bool(args.allow_degraded_retrieval),
        )
        updated["store_health"] = health
        if args.allow_degraded_retrieval:
            updated["store"]["allow_retrieval_fallback"] = True
        from src.ops.benchmark_runner import _run_full_evaluation

        updated["full_eval"] = _run_full_evaluation(updated, merged_by_id[experiment_id], full_eval_config)
        selected_results.append(updated)

    if requested_ids:
        found_ids = {str(result.get("id") or "") for result in selected_results}
        missing = sorted(requested_ids - found_ids)
        if missing:
            raise ValueError(f"Requested experiment ids not found: {missing}")

    if not selected_results:
        raise ValueError("No experiment results selected for eval-only run.")

    recorded_matrix = {
        "defaults": _sanitize_settings(defaults),
        "screening": _sanitize_settings(screening_config),
        "full_evaluation": _sanitize_settings(full_eval_config),
        "experiments": [_sanitize_settings(exp) for exp in matrix.get("experiments", [])],
        "company_runs": [_sanitize_settings(company_run)],
    }
    selected_ids = [str(result.get("id") or "") for result in selected_results]
    from src.ops.benchmark_runner import _write_benchmark_outputs

    _write_benchmark_outputs(
        output_dir=target_company_output_dir,
        config_path=config_path,
        recorded_matrix=recorded_matrix,
        screening_config=screening_config,
        full_eval_config=full_eval_config,
        selected_ids=selected_ids,
        results=selected_results,
    )
    logger.info("Store-fixed end-to-end evaluation outputs written to %s", target_company_output_dir)


if __name__ == "__main__":
    main()
