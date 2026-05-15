from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / "src"
for path in (PROJECT_ROOT, SRC_ROOT):
    path_text = str(path)
    if path_text not in sys.path:
        sys.path.insert(0, path_text)

from langchain_core.documents import Document

from src.agent.financial_graph import FinancialAgent, _candidate_matches_operand, _score_operand_candidate
from src.config.ontology import FinancialOntologyManager
from src.processing.financial_parser import FinancialParser

DEFAULT_DATASET = PROJECT_ROOT / "benchmarks" / "datasets" / "single_doc_eval_multi_metric_numeric.curated.json"
DEFAULT_V2 = PROJECT_ROOT / "src" / "config" / "financial_ontology_v2.draft.json"
DEFAULT_REPORT_ROOT = PROJECT_ROOT / "data" / "reports"


def _load_dataset(path: Path) -> List[Dict[str, Any]]:
    return json.loads(path.read_text(encoding="utf-8"))


def _find_example(dataset: List[Dict[str, Any]], example_id: str) -> Dict[str, Any]:
    for item in dataset:
        if str(item.get("id") or "").strip() == example_id:
            return dict(item)
    raise KeyError(f"example not found: {example_id}")


def _find_local_report(example: Dict[str, Any], report_root: Path) -> Optional[Path]:
    company = str(example.get("company") or "").strip()
    year = str(example.get("year") or "").strip()
    if not company or not year:
        return None
    report_dir = report_root / company
    if not report_dir.exists():
        return None
    candidates = sorted(report_dir.glob(f"{year}_사업보고서_*.html"))
    preview_filtered = [path for path in candidates if not path.name.endswith(".preview.html")]
    return preview_filtered[0] if preview_filtered else (candidates[0] if candidates else None)


def _load_chunks(report_path: Path, example: Dict[str, Any]) -> List[Any]:
    parser = FinancialParser()
    source_metadata = {
        "company": str(example.get("company") or ""),
        "year": int(example.get("year") or 0) if str(example.get("year") or "").strip() else "",
        "report_type": "사업보고서",
    }
    return parser.process_document(str(report_path), source_metadata)


def _docs_from_chunks(chunks: List[Any]) -> List[tuple[Document, float]]:
    docs: List[tuple[Document, float]] = []
    for chunk in chunks:
        docs.append((Document(page_content=chunk.content, metadata=dict(chunk.metadata or {})), 1.0))
    return docs


def _build_candidates(docs: List[tuple[Document, float]]) -> List[Dict[str, Any]]:
    agent = FinancialAgent.__new__(FinancialAgent)
    state = {
        "evidence_items": [],
        "retrieved_docs": docs,
        "seed_retrieved_docs": [],
    }
    return agent._build_reconciliation_candidates(state)


def _legacy_like_operand(spec: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "label": str(spec.get("label") or ""),
        "aliases": list(spec.get("aliases") or []),
        "role": str(spec.get("role") or ""),
        "required": bool(spec.get("required", True)),
    }


def _score_matches(
    *,
    candidates: List[Dict[str, Any]],
    operand: Dict[str, Any],
    preferred_statement_types: List[str],
    constraints: Dict[str, Any],
    query_years: List[int],
) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for candidate in candidates:
        if not _candidate_matches_operand(candidate, operand):
            continue
        score = _score_operand_candidate(
            candidate,
            operand=operand,
            preferred_statement_types=preferred_statement_types,
            constraints=constraints,
            query_years=query_years,
        )
        metadata = dict(candidate.get("metadata") or {})
        rows.append(
            {
                "candidate_id": str(candidate.get("candidate_id") or ""),
                "candidate_kind": str(candidate.get("candidate_kind") or ""),
                "score": score,
                "row_label": str(metadata.get("row_label") or ""),
                "semantic_label": str(metadata.get("semantic_label") or ""),
                "value_role": str(metadata.get("value_role") or ""),
                "aggregation_stage": str(metadata.get("aggregation_stage") or ""),
                "aggregate_role": str(metadata.get("aggregate_role") or ""),
                "period_text": str(metadata.get("period_text") or ""),
                "statement_type": str(metadata.get("statement_type") or ""),
                "section_path": str(metadata.get("section_path") or ""),
                "preview": str(candidate.get("text") or "")[:240],
            }
        )
    rows.sort(key=lambda item: item["score"], reverse=True)
    return rows


def _compare_example(
    *,
    example: Dict[str, Any],
    report_path: Path,
    ontology_v2: FinancialOntologyManager,
) -> Dict[str, Any]:
    chunks = _load_chunks(report_path, example)
    docs = _docs_from_chunks(chunks)
    candidates = _build_candidates(docs)

    query = str(example.get("query") or example.get("question") or "")
    metric = ontology_v2.best_metric_family(query, intent="comparison")
    if not metric:
        return {
            "example_id": example.get("id"),
            "query": query,
            "report_path": str(report_path),
            "status": "no_metric_match",
        }

    metric_key = str(metric.get("key") or "")
    operand_specs = ontology_v2.build_operand_spec(metric_key)
    preferred_statement_types = list(ontology_v2.statement_type_hints_for_metric(metric_key))
    constraints = dict(ontology_v2.default_constraints_for_metric(metric_key))
    query_years = [int(example.get("year"))] if str(example.get("year") or "").strip() else []

    comparisons: List[Dict[str, Any]] = []
    for spec in operand_specs:
        legacy_operand = _legacy_like_operand(spec)
        legacy_matches = _score_matches(
            candidates=candidates,
            operand=legacy_operand,
            preferred_statement_types=preferred_statement_types,
            constraints=constraints,
            query_years=query_years,
        )
        policy_matches = _score_matches(
            candidates=candidates,
            operand=spec,
            preferred_statement_types=preferred_statement_types,
            constraints=constraints,
            query_years=query_years,
        )
        legacy_top = legacy_matches[0] if legacy_matches else None
        policy_top = policy_matches[0] if policy_matches else None
        comparisons.append(
            {
                "label": str(spec.get("label") or ""),
                "concept": str(spec.get("concept") or ""),
                "binding_policy": dict(spec.get("binding_policy") or {}),
                "legacy_top": legacy_top,
                "policy_top": policy_top,
                "changed": (legacy_top or {}).get("candidate_id") != (policy_top or {}).get("candidate_id"),
                "legacy_top5": legacy_matches[:5],
                "policy_top5": policy_matches[:5],
            }
        )

    return {
        "example_id": str(example.get("id") or ""),
        "company": str(example.get("company") or ""),
        "year": example.get("year"),
        "query": query,
        "report_path": str(report_path),
        "metric_family": metric_key,
        "preferred_statement_types": preferred_statement_types,
        "constraints": constraints,
        "chunk_count": len(chunks),
        "candidate_count": len(candidates),
        "comparisons": comparisons,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare legacy-like and ontology-policy candidate ranking.")
    parser.add_argument("--example-id", action="append", required=True, help="Benchmark example id to compare.")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--ontology-v2", type=Path, default=DEFAULT_V2)
    parser.add_argument("--report-root", type=Path, default=DEFAULT_REPORT_ROOT)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    dataset = _load_dataset(args.dataset)
    ontology_v2 = FinancialOntologyManager(args.ontology_v2)
    results: List[Dict[str, Any]] = []

    for example_id in args.example_id:
        example = _find_example(dataset, example_id)
        report_path = _find_local_report(example, args.report_root)
        if report_path is None:
            results.append(
                {
                    "example_id": example_id,
                    "query": str(example.get("query") or ""),
                    "status": "missing_local_report",
                }
            )
            continue
        results.append(_compare_example(example=example, report_path=report_path, ontology_v2=ontology_v2))

    payload = {"results": results}
    rendered = json.dumps(payload, ensure_ascii=False, indent=2)
    print(rendered)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")


if __name__ == "__main__":
    main()
