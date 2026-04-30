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
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from ops.benchmark_runner import (
    _company_output_subdir,
    _deep_merge,
    _filter_experiments_by_candidate_ids,
    _load_json,
    _normalise_path,
    _run_full_evaluation,
    _sanitize_settings,
    _write_benchmark_outputs,
)

logger = logging.getLogger(__name__)


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

    from ops.benchmark_runner import _slugify

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
