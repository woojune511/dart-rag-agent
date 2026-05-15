from __future__ import annotations

import argparse
import json
import os
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / "src"
for path in (PROJECT_ROOT, SRC_ROOT):
    path_text = str(path)
    if path_text not in sys.path:
        sys.path.insert(0, path_text)

from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI

import src.config.ontology as ontology_module
from src.agent.financial_graph import FinancialAgent, _build_semantic_numeric_plan
from src.config.ontology import FinancialOntologyManager


DEFAULT_PROFILE = PROJECT_ROOT / "benchmarks" / "profiles" / "concept_planner_canary.json"


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_dataset_rows(path: Path) -> List[Dict[str, Any]]:
    payload = _load_json(path)
    if not isinstance(payload, list):
        raise ValueError(f"Dataset must be a JSON list: {path}")
    return [dict(item) for item in payload]


def _find_dataset_row(rows: List[Dict[str, Any]], example_id: str) -> Dict[str, Any]:
    for row in rows:
        if str(row.get("id") or "").strip() == example_id:
            return dict(row)
    raise KeyError(f"example id not found in dataset: {example_id}")


def _normalise_report_scope(raw_scope: Dict[str, Any], row: Dict[str, Any]) -> Dict[str, Any]:
    scope = dict(raw_scope or {})
    if not scope.get("company") and row.get("company"):
        scope["company"] = row.get("company")
    if not scope.get("year") and row.get("year"):
        scope["year"] = row.get("year")
    if not scope.get("report_type"):
        scope["report_type"] = row.get("report_type") or "사업보고서"
    return scope


def _resolve_case(case: Dict[str, Any], dataset_rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    resolved = dict(case)
    if str(case.get("example_id") or "").strip():
        row = _find_dataset_row(dataset_rows, str(case["example_id"]))
        query = str(row.get("query") or row.get("question") or "").strip()
        topic = str(case.get("topic") or row.get("topic") or query).strip()
        intent = str(case.get("intent") or row.get("intent") or "comparison").strip()
        report_scope = _normalise_report_scope(dict(case.get("report_scope") or {}), row)
        resolved.update(
            {
                "id": str(case.get("id") or row.get("id") or "").strip(),
                "query": query,
                "topic": topic,
                "intent": intent,
                "report_scope": report_scope,
                "source_row": row,
            }
        )
        return resolved

    query = str(case.get("query") or "").strip()
    topic = str(case.get("topic") or query).strip()
    intent = str(case.get("intent") or "comparison").strip()
    resolved.update(
        {
            "id": str(case.get("id") or query[:48]).strip(),
            "query": query,
            "topic": topic,
            "intent": intent,
            "report_scope": dict(case.get("report_scope") or {}),
        }
    )
    return resolved


@contextmanager
def _use_ontology(path: Path) -> Iterator[FinancialOntologyManager]:
    original_singleton = ontology_module._ONTOLOGY_SINGLETON
    manager = FinancialOntologyManager(path)
    ontology_module._ONTOLOGY_SINGLETON = manager
    try:
        yield manager
    finally:
        ontology_module._ONTOLOGY_SINGLETON = original_singleton


def _task_summary(task: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "task_id": str(task.get("task_id") or ""),
        "metric_family": str(task.get("metric_family") or ""),
        "metric_label": str(task.get("metric_label") or ""),
        "operation_family": str(task.get("operation_family") or ""),
        "required_operands": [
            {
                "label": str(item.get("label") or ""),
                "concept": str(item.get("concept") or ""),
                "role": str(item.get("role") or ""),
            }
            for item in (task.get("required_operands") or [])
        ],
        "preferred_statement_types": list(task.get("preferred_statement_types") or []),
        "preferred_sections": list(task.get("preferred_sections") or []),
        "constraints": dict(task.get("constraints") or {}),
    }


def _plan_summary(plan: Dict[str, Any]) -> Dict[str, Any]:
    tasks = [dict(item) for item in (plan.get("tasks") or [])]
    return {
        "status": str(plan.get("status") or ""),
        "fallback_to_general_search": bool(plan.get("fallback_to_general_search", False)),
        "planned_metric_families": list(plan.get("planned_metric_families") or []),
        "planner_notes": [str(item).strip() for item in (plan.get("planner_notes") or []) if str(item).strip()],
        "tasks": [_task_summary(task) for task in tasks],
    }


def _legacy_plan(case: Dict[str, Any], ontology_path: Path) -> Dict[str, Any]:
    with _use_ontology(ontology_path) as ontology:
        metric = ontology.best_metric_family(case["query"], case["topic"], case["intent"])
        target_metric_family = str(metric.get("key") or "") if metric else ""
        plan = _build_semantic_numeric_plan(
            query=case["query"],
            topic=case["topic"],
            intent=case["intent"],
            report_scope=dict(case.get("report_scope") or {}),
            target_metric_family=target_metric_family,
        )
    return _plan_summary(plan)


def _concept_plan(case: Dict[str, Any], ontology_path: Path, llm_model: str) -> Dict[str, Any]:
    load_dotenv()
    if not os.environ.get("GOOGLE_API_KEY"):
        raise ValueError("GOOGLE_API_KEY environment variable is required for concept planner shadow compare.")

    agent = FinancialAgent.__new__(FinancialAgent)
    agent.llm = ChatGoogleGenerativeAI(model=llm_model, temperature=0)

    with _use_ontology(ontology_path):
        result = agent._plan_semantic_numeric_tasks(
            {
                "query": case["query"],
                "intent": case["intent"],
                "query_type": case["intent"],
                "topic": case["topic"],
                "report_scope": dict(case.get("report_scope") or {}),
                "target_metric_family": "",
                "target_metric_family_hint": "",
                "tasks": [],
                "artifacts": [],
            }
        )
    return _plan_summary(dict(result.get("semantic_plan") or {}))


def _compare_case(case: Dict[str, Any], legacy_ontology_path: Path, concept_ontology_path: Path, llm_model: str) -> Dict[str, Any]:
    legacy = _legacy_plan(case, legacy_ontology_path)
    concept = _concept_plan(case, concept_ontology_path, llm_model)
    return {
        "id": case["id"],
        "query": case["query"],
        "topic": case["topic"],
        "intent": case["intent"],
        "report_scope": dict(case.get("report_scope") or {}),
        "legacy": legacy,
        "concept": concept,
        "changed": legacy != concept,
        "source_example_id": str(case.get("example_id") or ""),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare legacy metric-family planning and concept-only planner output.")
    parser.add_argument("--profile", type=Path, default=DEFAULT_PROFILE, help="Path to concept planner canary profile JSON.")
    parser.add_argument("--case-id", action="append", default=[], help="Optional case ids to limit the comparison.")
    parser.add_argument("--output", type=Path, default=None, help="Optional JSON output path.")
    args = parser.parse_args()

    profile = dict(_load_json(args.profile) or {})
    dataset_path = PROJECT_ROOT / str(profile.get("dataset_path") or "")
    dataset_rows = _load_dataset_rows(dataset_path) if dataset_path.exists() else []
    requested_case_ids = {str(item).strip() for item in (args.case_id or []) if str(item).strip()}
    legacy_ontology_path = PROJECT_ROOT / str(profile.get("legacy_ontology_path") or "src/config/financial_ontology_v2.draft.json")
    concept_ontology_path = PROJECT_ROOT / str(profile.get("concept_ontology_path") or "src/config/financial_ontology_concepts_v3.draft.json")
    llm_model = str(profile.get("llm_model") or "gemini-2.5-flash").strip()

    comparisons: List[Dict[str, Any]] = []
    for raw_case in list(profile.get("cases") or []):
        resolved = _resolve_case(dict(raw_case), dataset_rows)
        if requested_case_ids and str(resolved.get("id") or "").strip() not in requested_case_ids:
            continue
        comparisons.append(_compare_case(resolved, legacy_ontology_path, concept_ontology_path, llm_model))

    payload = {
        "profile": str(args.profile),
        "legacy_ontology_path": str(legacy_ontology_path),
        "concept_ontology_path": str(concept_ontology_path),
        "case_count": len(comparisons),
        "results": comparisons,
    }
    rendered = json.dumps(payload, ensure_ascii=False, indent=2)
    print(rendered)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")


if __name__ == "__main__":
    main()
