"""Mine source-grounded semantic tie cases from saved benchmark artifacts.

This command is evaluation-only and provider-free.  It combines saved semantic
obligations with exact matches to verified dataset evidence quotes, rebuilds a
small current-ID candidate catalog from those source nodes, and exports an
unlabeled review packet.  The evidence-scoped population is useful for hard
negative collection; it is not a claim about production retrieval frequency.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from src.agent.financial_candidate_tiebreaker import SEMANTIC_TIE_BREAK_PAIR_SCHEMA
from src.agent.financial_graph_calculation import _semantic_candidate_cohorts
from src.agent.financial_reconciliation_candidates import (
    build_semantic_candidate_catalog,
    build_semantic_source_candidates,
    semantic_candidate_catalog_fingerprint,
)
from src.ops.export_semantic_tiebreak_cases import (
    LABELING_TEMPLATE_SCHEMA,
    build_labeling_template,
)
from src.storage.graph_persistence import load_structure_graph
from src.storage.metadata_payloads import (
    load_table_payloads,
    metadata_with_table_payload,
)


EVIDENCE_MINING_SCHEMA = "semantic_candidate_tiebreak_evidence_mining_v2"
EVIDENCE_SCOPE_SCHEMA = "verified_dataset_evidence_exact_quote_v2"
PROJECT_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True, slots=True)
class _StoredDocument:
    page_content: str
    metadata: dict[str, Any]


def _fingerprint(value: Any) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _compact_text(value: Any) -> str:
    normalized = unicodedata.normalize("NFKC", str(value or "")).casefold()
    return "".join(character for character in normalized if character.isalnum())


def _source_anchor(metadata: Mapping[str, Any]) -> str:
    relation = str(metadata.get("graph_relation") or "").strip()
    relation_suffix = f" | {relation}" if relation else ""
    return (
        f"[{metadata.get('company', '?')} | {metadata.get('year', '?')} | "
        f"{metadata.get('section_path', metadata.get('section', '?'))}"
        f"{relation_suffix}]"
    )


def _result_files(paths: Sequence[Path]) -> list[Path]:
    files: list[Path] = []
    for raw_path in paths:
        path = raw_path.resolve()
        if path.is_file():
            files.append(path)
        elif path.is_dir():
            files.extend(sorted(path.rglob("results.json")))
        else:
            raise FileNotFoundError(path)
    return list(dict.fromkeys(files))


def _calculation_plan(question: Mapping[str, Any]) -> dict[str, Any]:
    trace = question.get("resolved_calculation_trace")
    if isinstance(trace, Mapping) and isinstance(
        trace.get("calculation_plan"), Mapping
    ):
        return dict(trace.get("calculation_plan") or {})
    structured = question.get("structured_result")
    if isinstance(structured, Mapping):
        trace = structured.get("resolved_calculation_trace")
        if isinstance(trace, Mapping) and isinstance(
            trace.get("calculation_plan"), Mapping
        ):
            return dict(trace.get("calculation_plan") or {})
    return {}


def load_saved_question_contexts(
    paths: Sequence[Path],
    *,
    question_ids: set[str] | None = None,
) -> list[dict[str, Any]]:
    """Load semantic obligations with their owning immutable store paths."""

    contexts: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for path in _result_files(paths):
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, Mapping):
            continue
        for company_run in payload.get("company_runs") or []:
            if not isinstance(company_run, Mapping):
                continue
            for result in company_run.get("results") or []:
                if not isinstance(result, Mapping):
                    continue
                store = dict(result.get("store") or {})
                persist_directory = str(store.get("persist_directory") or "")
                full_eval = result.get("full_eval")
                if not isinstance(full_eval, Mapping):
                    continue
                for question in full_eval.get("per_question") or []:
                    if not isinstance(question, Mapping):
                        continue
                    question_id = str(question.get("id") or "").strip()
                    if not question_id or (
                        question_ids and question_id not in question_ids
                    ):
                        continue
                    plan = _calculation_plan(question)
                    obligations = plan.get("answer_obligations")
                    if not isinstance(obligations, Sequence) or not obligations:
                        continue
                    obligation_fingerprint = _fingerprint(obligations)
                    key = (
                        question_id,
                        obligation_fingerprint,
                        str(Path(persist_directory).resolve())
                        if persist_directory
                        else "",
                    )
                    if key in seen:
                        continue
                    seen.add(key)
                    contexts.append(
                        {
                            "question_id": question_id,
                            "question": str(question.get("question") or ""),
                            "source_file": path.as_posix(),
                            "store": store,
                            "plan": plan,
                            "obligation_fingerprint": obligation_fingerprint,
                        }
                    )
    return sorted(
        contexts,
        key=lambda row: (
            str(row.get("question_id") or ""),
            str(row.get("source_file") or ""),
        ),
    )


def load_dataset_rows(path: Path) -> dict[str, dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, Mapping):
        payload = payload.get("questions") or payload.get("items") or []
    if not isinstance(payload, Sequence) or isinstance(payload, (str, bytes)):
        raise ValueError("dataset must contain a question list")
    rows: dict[str, dict[str, Any]] = {}
    for raw_row in payload:
        if not isinstance(raw_row, Mapping):
            continue
        question_id = str(raw_row.get("id") or "").strip()
        if question_id:
            rows[question_id] = dict(raw_row)
    return rows


def match_evidence_source_ids(
    nodes: Mapping[str, Any],
    evidence: Sequence[Mapping[str, Any]],
) -> tuple[list[str], list[dict[str, Any]], list[dict[str, Any]]]:
    """Match verified evidence quotes to graph nodes without fuzzy inference."""

    compact_nodes = {
        str(source_id): _compact_text(dict(node or {}).get("text") or "")
        for source_id, node in sorted(
            nodes.items(),
            key=lambda item: str(item[0]),
        )
    }
    matched_rows: list[dict[str, Any]] = []
    unmatched_rows: list[dict[str, Any]] = []
    source_ids: list[str] = []
    for quote_index, raw_evidence in enumerate(evidence):
        row = dict(raw_evidence or {})
        quote = str(row.get("quote") or "").strip()
        compact_quote = _compact_text(quote)
        matches = [
            source_id
            for source_id, compact_node in compact_nodes.items()
            if compact_quote and compact_quote in compact_node
        ]
        projected = {
            "quote_index": quote_index,
            "quote": quote,
            "section_path": str(row.get("section_path") or ""),
            "why_it_supports_answer": str(
                row.get("why_it_supports_answer") or ""
            ),
            "source_ids": matches,
        }
        if matches:
            matched_rows.append(projected)
            source_ids.extend(matches)
        else:
            unmatched_rows.append(projected)
    return list(dict.fromkeys(source_ids)), matched_rows, unmatched_rows


def _source_node_projection(
    source_id: str,
    node: Mapping[str, Any],
    metadata: Mapping[str, Any],
) -> dict[str, Any]:
    text = str(node.get("text") or "")
    return {
        "source_id": source_id,
        "source_anchor": _source_anchor(metadata),
        "text": text,
        "text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "company": str(metadata.get("company") or ""),
        "year": metadata.get("year"),
        "rcept_no": str(metadata.get("rcept_no") or ""),
        "section_path": str(
            metadata.get("section_path") or metadata.get("section") or ""
        ),
        "local_heading": str(metadata.get("local_heading") or ""),
        "block_type": str(metadata.get("block_type") or ""),
        "is_table": bool(metadata.get("is_table")),
        "table_source_id": str(metadata.get("table_source_id") or ""),
        "table_view": str(metadata.get("table_view") or ""),
    }


def match_candidate_source_ids(
    candidate: Mapping[str, Any],
    source_nodes: Sequence[Mapping[str, Any]],
) -> list[str]:
    """Resolve a candidate to exact graph nodes through stored provenance."""

    direct_locators = {
        str(candidate.get(field) or "").strip()
        for field in ("source_candidate_id", "evidence_id", "source_row_id")
        if str(candidate.get(field) or "").strip()
    }
    table_locators = {
        str(candidate.get(field) or "").strip()
        for field in ("table_source_id", "physical_table_id", "evidence_id")
        if str(candidate.get(field) or "").strip()
    }
    matches: list[str] = []
    for raw_source in source_nodes:
        source = dict(raw_source or {})
        source_id = str(source.get("source_id") or "").strip()
        if not source_id:
            continue
        direct_match = any(
            locator == source_id or locator.startswith(f"{source_id}::")
            for locator in direct_locators
        )
        source_table_id = str(source.get("table_source_id") or "").strip()
        table_match = bool(
            source_table_id and source_table_id in table_locators
        )
        if direct_match or table_match:
            matches.append(source_id)
    return list(dict.fromkeys(matches))


class EvidenceCatalogLoader:
    """Read structure artifacts once per store and build quote-local catalogs."""

    def __init__(self) -> None:
        self._store_cache: dict[
            str, tuple[dict[str, Any], dict[str, Any]]
        ] = {}

    def _load_store(
        self, store_path: Path
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        key = str(store_path.resolve())
        cached = self._store_cache.get(key)
        if cached is not None:
            return cached
        graph_path = store_path / "document_structure_graph.json"
        if not graph_path.is_file():
            raise FileNotFoundError(graph_path)
        graph = load_structure_graph(graph_path)
        payloads = load_table_payloads(store_path / "table_payloads.json")
        loaded = (dict(graph.get("nodes") or {}), payloads)
        self._store_cache[key] = loaded
        return loaded

    def __call__(
        self,
        context: Mapping[str, Any],
        dataset_row: Mapping[str, Any],
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        persist_directory = str(
            dict(context.get("store") or {}).get("persist_directory") or ""
        ).strip()
        if not persist_directory:
            return [], {"status": "unavailable", "reason": "store_path_not_saved"}
        store_path = Path(persist_directory)
        try:
            nodes, table_payloads = self._load_store(store_path)
        except FileNotFoundError:
            return [], {
                "status": "unavailable",
                "reason": "structure_graph_not_found",
                "store_path": str(store_path),
            }
        evidence = [
            dict(item)
            for item in (dataset_row.get("evidence") or [])
            if isinstance(item, Mapping) and str(item.get("quote") or "").strip()
        ]
        source_ids, matched, unmatched = match_evidence_source_ids(nodes, evidence)
        if not source_ids:
            return [], {
                "status": "unavailable",
                "reason": "evidence_quotes_not_found",
                "store_path": str(store_path),
                "matched_evidence": matched,
                "unmatched_evidence": unmatched,
            }
        documents: list[tuple[_StoredDocument, float]] = []
        source_nodes: list[dict[str, Any]] = []
        for source_id in source_ids:
            node = dict(nodes.get(source_id) or {})
            metadata = metadata_with_table_payload(
                dict(node.get("metadata") or {}),
                table_payloads,
            )
            source_nodes.append(
                _source_node_projection(source_id, node, metadata)
            )
            documents.append(
                (
                    _StoredDocument(
                        page_content=str(node.get("text") or ""),
                        metadata=metadata,
                    ),
                    0.0,
                )
            )
        source_candidates = build_semantic_source_candidates(
            {
                "evidence_items": [],
                "retrieved_docs": documents,
                "seed_retrieved_docs": documents,
            },
            source_anchor_builder=_source_anchor,
        )
        catalog = build_semantic_candidate_catalog(source_candidates)
        scope_material = {
            "schema": EVIDENCE_SCOPE_SCHEMA,
            "question_id": str(context.get("question_id") or ""),
            "obligation_fingerprint": str(
                context.get("obligation_fingerprint") or ""
            ),
            "source_ids": source_ids,
            "source_node_fingerprints": [
                {
                    "source_id": source.get("source_id"),
                    "text_sha256": source.get("text_sha256"),
                }
                for source in source_nodes
            ],
            "evidence_quotes": [row.get("quote") for row in evidence],
            "catalog_fingerprint": semantic_candidate_catalog_fingerprint(catalog),
        }
        return catalog, {
            "status": "verified",
            "reason": "",
            "schema": EVIDENCE_SCOPE_SCHEMA,
            "store_path": str(store_path),
            "source_ids": source_ids,
            "source_nodes": source_nodes,
            "source_node_count": len(source_ids),
            "source_candidate_count": len(source_candidates),
            "catalog_candidate_count": len(catalog),
            "catalog_fingerprint": scope_material["catalog_fingerprint"],
            "matched_evidence": matched,
            "unmatched_evidence": unmatched,
            "scope_fingerprint": _fingerprint(scope_material),
        }


def _local_report_paths(dataset_row: Mapping[str, Any]) -> list[str]:
    report_root = PROJECT_ROOT / "data" / "reports"
    paths: list[str] = []
    for report in dataset_row.get("source_reports") or []:
        if not isinstance(report, Mapping):
            continue
        receipt = str(report.get("rcept_no") or "").strip()
        if not receipt:
            continue
        matches = sorted(report_root.rglob(f"*{receipt}*.html"))
        paths.extend(str(path.resolve()) for path in matches)
    return list(dict.fromkeys(paths))


def _candidate_quote_indexes(
    candidate_row: Mapping[str, Any],
    evidence: Sequence[Mapping[str, Any]],
) -> list[int]:
    candidate = dict(candidate_row.get("candidate") or {})
    surface = _compact_text(candidate.get("raw_value") or "")
    if len(surface) < 2:
        return []
    return [
        index
        for index, row in enumerate(evidence)
        if surface in _compact_text(row.get("quote") or "")
    ]


CatalogLoader = Callable[
    [Mapping[str, Any], Mapping[str, Any]],
    tuple[list[dict[str, Any]], dict[str, Any]],
]


def build_evidence_mining_template(
    contexts: Sequence[Mapping[str, Any]],
    dataset_rows: Mapping[str, Mapping[str, Any]],
    *,
    catalog_loader: CatalogLoader | None = None,
) -> dict[str, Any]:
    """Build current-ID atomic tie cases from exact verified evidence nodes."""

    loader = catalog_loader or EvidenceCatalogLoader()
    cases: list[dict[str, Any]] = []
    excluded_cohorts: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    outcomes: list[dict[str, Any]] = []
    seen_case_fingerprints: set[str] = set()

    for raw_context in sorted(
        (dict(item) for item in contexts),
        key=lambda item: (
            str(item.get("question_id") or ""),
            str(item.get("source_file") or ""),
        ),
    ):
        question_id = str(raw_context.get("question_id") or "")
        dataset_row = dict(dataset_rows.get(question_id) or {})
        if not dataset_row:
            skipped.append(
                {"question_id": question_id, "reason": "dataset_question_not_found"}
            )
            continue
        if str(dataset_row.get("verification_status") or "") != "verified":
            skipped.append(
                {"question_id": question_id, "reason": "dataset_question_not_verified"}
            )
            continue
        catalog, scope = loader(raw_context, dataset_row)
        if str(scope.get("status") or "") != "verified":
            skipped.append(
                {
                    "question_id": question_id,
                    "reason": str(scope.get("reason") or "catalog_unavailable"),
                    "source_scope": dict(scope),
                }
            )
            continue
        plan = dict(raw_context.get("plan") or {})
        obligations = [
            dict(item)
            for item in (plan.get("answer_obligations") or [])
            if isinstance(item, Mapping)
        ]
        cohort_plan = _semantic_candidate_cohorts(
            catalog,
            obligations,
            query=str(raw_context.get("question") or dataset_row.get("question") or ""),
        )
        if str(cohort_plan.get("status") or "") != "ok":
            skipped.append(
                {
                    "question_id": question_id,
                    "reason": "cohort_plan_unavailable",
                    "cohort_status": str(cohort_plan.get("status") or ""),
                }
            )
            continue
        scoped_plan = {
            **plan,
            "candidate_cohorts": list(cohort_plan.get("cohorts") or []),
        }
        exported = build_labeling_template(
            [
                {
                    **raw_context,
                    "question": str(
                        raw_context.get("question")
                        or dataset_row.get("question")
                        or ""
                    ),
                    "plan": scoped_plan,
                    "store": {"catalog": catalog},
                }
            ],
            catalog_replay=lambda _plan, store: (
                list(store.get("catalog") or []),
                {"status": "verified", "reason": ""},
            ),
        )
        evidence = [
            dict(item)
            for item in (dataset_row.get("evidence") or [])
            if isinstance(item, Mapping)
        ]
        case_count_before = len(cases)
        for raw_case in exported.get("cases") or []:
            case = dict(raw_case)
            semantic_fingerprint = str(
                case.get("semantic_case_fingerprint") or ""
            )
            if semantic_fingerprint in seen_case_fingerprints:
                continue
            seen_case_fingerprints.add(semantic_fingerprint)
            source_nodes = [
                dict(item)
                for item in (scope.get("source_nodes") or [])
                if isinstance(item, Mapping)
            ]
            candidate_rows = []
            for raw_candidate in case.get("candidates") or []:
                candidate = dict(raw_candidate)
                candidate["reference_quote_indexes"] = _candidate_quote_indexes(
                    candidate,
                    evidence,
                )
                referenced_source_ids = match_candidate_source_ids(
                    dict(candidate.get("candidate") or {}),
                    source_nodes,
                )
                candidate["referenced_source_ids"] = referenced_source_ids
                candidate["source_reference_status"] = (
                    "resolved" if referenced_source_ids else "unresolved"
                )
                candidate_rows.append(candidate)
            case["candidates"] = candidate_rows
            case["source_review"] = {
                "schema": EVIDENCE_SCOPE_SCHEMA,
                "dataset_verification_status": str(
                    dataset_row.get("verification_status") or ""
                ),
                "dataset_answer_type": str(dataset_row.get("answer_type") or ""),
                "dataset_reference_answer": str(
                    dataset_row.get("answer_key")
                    or dataset_row.get("ground_truth")
                    or ""
                ),
                "evidence": evidence,
                "matched_evidence": list(scope.get("matched_evidence") or []),
                "unmatched_evidence": list(scope.get("unmatched_evidence") or []),
                "source_ids": list(scope.get("source_ids") or []),
                "source_nodes": source_nodes,
                "scope_fingerprint": str(scope.get("scope_fingerprint") or ""),
                "local_report_paths": _local_report_paths(dataset_row),
            }
            cases.append(case)
        excluded_cohorts.extend(
            dict(item) for item in (exported.get("excluded_cohorts") or [])
        )
        question_case_count = len(cases) - case_count_before
        outcomes.append(
            {
                "question_id": question_id,
                "status": "cases_found" if question_case_count else "no_atomic_ties",
                "case_count": question_case_count,
                "source_node_count": int(scope.get("source_node_count") or 0),
                "catalog_candidate_count": int(
                    scope.get("catalog_candidate_count") or 0
                ),
                "matched_evidence_count": len(
                    list(scope.get("matched_evidence") or [])
                ),
                "unmatched_evidence_count": len(
                    list(scope.get("unmatched_evidence") or [])
                ),
                "scope_fingerprint": str(scope.get("scope_fingerprint") or ""),
            }
        )

    cases.sort(
        key=lambda item: (
            str(item.get("question_id") or ""),
            str(item.get("cohort_id") or ""),
        )
    )
    fingerprint_material = {
        "schema": EVIDENCE_MINING_SCHEMA,
        "labeling_schema": LABELING_TEMPLATE_SCHEMA,
        "case_fingerprints": [
            case.get("semantic_case_fingerprint") for case in cases
        ],
        "source_scope_fingerprints": [
            outcome.get("scope_fingerprint") for outcome in outcomes
        ],
        "skipped": [
            {
                "question_id": item.get("question_id"),
                "reason": item.get("reason"),
            }
            for item in skipped
        ],
    }
    return {
        "schema": EVIDENCE_MINING_SCHEMA,
        "labeling_schema": LABELING_TEMPLATE_SCHEMA,
        "pair_schema": SEMANTIC_TIE_BREAK_PAIR_SCHEMA,
        "cases": cases,
        "excluded_cohorts": excluded_cohorts,
        "skipped": skipped,
        "question_outcomes": outcomes,
        "summary": {
            "question_count": len(outcomes),
            "question_with_cases_count": sum(
                outcome.get("status") == "cases_found" for outcome in outcomes
            ),
            "case_count": len(cases),
            "candidate_pair_count": sum(
                len(case.get("candidates") or []) for case in cases
            ),
            "excluded_cohort_count": len(excluded_cohorts),
            "skipped_question_count": len(skipped),
            "label_status": "unlabeled",
            "population": "verified_dataset_evidence_nodes",
        },
        "template_fingerprint": _fingerprint(fingerprint_material),
    }


def render_summary(template: Mapping[str, Any]) -> str:
    summary = dict(template.get("summary") or {})
    return (
        "# Evidence-Scoped Semantic Tie Mining\n\n"
        f"Questions inspected: {summary.get('question_count', 0)}\n"
        f"Questions with cases: {summary.get('question_with_cases_count', 0)}\n"
        f"Cases: {summary.get('case_count', 0)}\n"
        f"Candidate pairs: {summary.get('candidate_pair_count', 0)}\n"
        f"Skipped questions: {summary.get('skipped_question_count', 0)}\n"
        f"Fingerprint: {template.get('template_fingerprint', '')}\n"
    )


def _html_value(value: Any) -> str:
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return " / ".join(str(item) for item in value if str(item).strip())
    return str(value or "")


def _source_dom_id(case_id: str, source_id: str) -> str:
    digest = hashlib.sha256(f"{case_id}\0{source_id}".encode("utf-8")).hexdigest()
    return f"source-{digest[:16]}"


def render_review_packet(template: Mapping[str, Any]) -> str:
    """Render a static, local-first review packet for human labeling."""

    sections: list[str] = []
    for index, raw_case in enumerate(template.get("cases") or [], start=1):
        case = dict(raw_case)
        review = dict(case.get("source_review") or {})
        case_id = str(case.get("case_id") or index)
        source_nodes = [
            dict(item)
            for item in (review.get("source_nodes") or [])
            if isinstance(item, Mapping)
        ]
        source_number_by_id = {
            str(source.get("source_id") or ""): source_index
            for source_index, source in enumerate(source_nodes, start=1)
            if str(source.get("source_id") or "")
        }
        referenced_by: dict[str, list[str]] = {}
        evidence_rows = []
        for quote_index, raw_evidence in enumerate(review.get("evidence") or []):
            evidence = dict(raw_evidence or {})
            evidence_rows.append(
                "<blockquote>"
                f"<strong>Quote {quote_index}</strong> "
                f"<span>{html.escape(str(evidence.get('section_path') or ''))}</span>"
                f"<p>{html.escape(str(evidence.get('quote') or ''))}</p>"
                "</blockquote>"
            )
        report_paths = [
            Path(path)
            for path in review.get("local_report_paths") or []
            if Path(path).is_absolute()
        ]
        report_links = " ".join(
            f'<a href="{path.as_uri()}">{html.escape(path.name)}</a>'
            for path in report_paths
        )
        candidate_rows = []
        for rank, raw_candidate in enumerate(case.get("candidates") or [], start=1):
            candidate_row = dict(raw_candidate)
            candidate = dict(candidate_row.get("candidate") or {})
            candidate_id = str(candidate_row.get("candidate_id") or "")
            baseline = "<strong>baseline first</strong>" if rank == 1 else ""
            quote_hits = ", ".join(
                str(item)
                for item in candidate_row.get("reference_quote_indexes") or []
            )
            context = str(
                candidate_row.get("candidate_text")
                or candidate_row.get("projected_evidence_text")
                or ""
            )
            source_links: list[str] = []
            for source_id in candidate_row.get("referenced_source_ids") or []:
                source_id = str(source_id)
                referenced_by.setdefault(source_id, []).append(candidate_id)
                source_number = source_number_by_id.get(source_id)
                if source_number is None:
                    source_links.append(html.escape(source_id))
                    continue
                source_links.append(
                    f'<a href="#{_source_dom_id(case_id, source_id)}">'
                    f"Source {source_number}</a>"
                )
            source_references = " ".join(source_links) or (
                '<strong class="unresolved">unresolved</strong>'
            )
            candidate_rows.append(
                "<tr>"
                f"<td>{rank}<br>{baseline}</td>"
                f"<td><code>{html.escape(candidate_id)}</code></td>"
                f"<td>{html.escape(_html_value(candidate.get('raw_value')))} "
                f"{html.escape(_html_value(candidate.get('raw_unit')))}</td>"
                f"<td>{html.escape(_html_value(candidate.get('row_headers') or candidate.get('row_label')))}</td>"
                f"<td>{html.escape(_html_value(candidate.get('period_label_surfaces') or candidate.get('period')))}</td>"
                f"<td>{html.escape(quote_hits or '-')}</td>"
                f"<td>{source_references}</td>"
                f"<td>{html.escape(context[:1200])}</td>"
                "</tr>"
            )
        source_details = []
        for source_index, source in enumerate(source_nodes, start=1):
            source_id = str(source.get("source_id") or "")
            candidate_ids = list(dict.fromkeys(referenced_by.get(source_id) or []))
            if not candidate_ids:
                continue
            locator = str(source.get("table_source_id") or source_id)
            section_path = str(source.get("section_path") or "")
            receipt = str(source.get("rcept_no") or "")
            source_report_paths = [
                path for path in report_paths if receipt and receipt in path.name
            ]
            source_report_links = " ".join(
                f'<a href="{path.as_uri()}">{html.escape(path.name)}</a>'
                for path in source_report_paths
            )
            source_details.append(
                f'<details class="source-node" id="{_source_dom_id(case_id, source_id)}">'
                f"<summary><strong>Source {source_index}</strong> · "
                f"{html.escape(section_path)} · {html.escape(locator)}</summary>"
                '<div class="source-meta">'
                f"<strong>Referenced by:</strong> "
                f"{html.escape(', '.join(candidate_ids))}<br>"
                f"<strong>source_id:</strong> <code>{html.escape(source_id)}</code><br>"
                f"<strong>Original filing:</strong> "
                f"{source_report_links or 'not resolved'}<br>"
                f"<strong>source text SHA-256:</strong> "
                f"<code>{html.escape(str(source.get('text_sha256') or ''))}</code>"
                "</div>"
                f"<pre>{html.escape(str(source.get('text') or ''))}</pre>"
                "</details>"
            )
        owner = dict(case.get("owner") or {})
        sections.append(
            f"<section><h2>{index}. {html.escape(str(case.get('question_id') or ''))}</h2>"
            f"<p><strong>Question:</strong> {html.escape(str(case.get('query') or ''))}</p>"
            f"<p><strong>Cohort:</strong> <code>{html.escape(str(case.get('cohort_id') or ''))}</code><br>"
            f"<strong>Target:</strong> {html.escape(str(owner.get('label') or ''))}<br>"
            f"<strong>Reports:</strong> {report_links or 'not resolved'}</p>"
            + "".join(evidence_rows)
            + "<details><summary>Dataset reference answer (evaluation-only)</summary><p>"
            + html.escape(str(review.get("dataset_reference_answer") or ""))
            + "</p></details>"
            + '<div class="table-wrap"><table><thead><tr>'
            + "<th>Rank</th><th>Candidate</th><th>Value</th><th>Row</th>"
            + "<th>Period</th><th>Quote hits</th><th>Source</th>"
            + "<th>Candidate context</th>"
            + "</tr></thead><tbody>"
            + "".join(candidate_rows)
            + "</tbody></table></div>"
            + "<h3>Candidate-referenced source nodes</h3>"
            + '<p class="source-note">Exact structure-store text seen by candidate generation. '
            + "Use the report link above to inspect the original filing HTML.</p>"
            + ("".join(source_details) or '<p class="unresolved">No source node resolved.</p>')
            + '<div class="decision"><strong>Human label</strong><br>'
            + "☐ select candidate ID(s): ____________________________<br>"
            + "☐ abstain<br>Notes: _______________________________________</div>"
            + "</section>"
        )
    summary = dict(template.get("summary") or {})
    return f"""<!doctype html>
<html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Evidence-Scoped Semantic Tie Review</title>
<style>
body{{margin:0;background:#eef2f7;color:#172033;font:15px/1.55 system-ui,-apple-system,"Segoe UI",sans-serif}}
main{{max-width:1280px;margin:auto;padding:32px 22px 80px}}h1{{margin-bottom:6px}}h2{{margin-top:42px;border-top:2px solid #172033;padding-top:20px}}
.notice,.decision,blockquote{{background:white;border:1px solid #d8dee8;border-radius:10px;padding:14px 16px}}.notice{{border-left:5px solid #1f6feb}}
.table-wrap{{overflow:auto;background:white;border:1px solid #d8dee8;border-radius:10px}}table{{border-collapse:collapse;width:max-content;min-width:100%}}
th,td{{border:1px solid #d8dee8;padding:7px 9px;vertical-align:top;max-width:460px}}th{{background:#edf2f8}}code{{overflow-wrap:anywhere}}
.decision{{margin:14px 0;background:#fffdf5;border-color:#dbc36c}}blockquote span{{color:#5f6b7a}}details{{margin:12px 0}}
.source-node{{background:white;border:1px solid #d8dee8;border-radius:10px;padding:10px 14px;scroll-margin-top:18px}}.source-node summary{{cursor:pointer}}
.source-meta,.source-note{{color:#4b5565}}pre{{white-space:pre-wrap;overflow:auto;max-height:720px;background:#f7f9fc;border:1px solid #d8dee8;border-radius:8px;padding:12px}}
.unresolved{{color:#b42318}}
</style></head><body><main>
<h1>Evidence-Scoped Semantic Tie Review</h1>
<p>Cases: {summary.get('case_count', 0)} · Candidate pairs: {summary.get('candidate_pair_count', 0)} · Fingerprint: <code>{html.escape(str(template.get('template_fingerprint') or ''))}</code></p>
<div class="notice"><strong>Boundary:</strong> These candidates come only from exact matches to verified dataset evidence quotes. They are useful hard negatives, not proof that production retrieval will expose the same population. Select a winner only from the filing evidence; otherwise abstain.</div>
{''.join(sections)}
</main></body></html>"""


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "paths",
        nargs="+",
        type=Path,
        help="Saved benchmark results.json files or directories containing them.",
    )
    parser.add_argument("--dataset", required=True, type=Path)
    parser.add_argument("--question-id", action="append", default=[])
    parser.add_argument("--output", type=Path)
    parser.add_argument("--html-output", type=Path)
    parser.add_argument("--summary-only", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    question_ids = set(args.question_id) if args.question_id else None
    contexts = load_saved_question_contexts(
        args.paths,
        question_ids=question_ids,
    )
    if not contexts:
        raise SystemExit("No saved semantic question contexts were found.")
    dataset_rows = load_dataset_rows(args.dataset)
    template = build_evidence_mining_template(contexts, dataset_rows)
    serialized = json.dumps(
        template,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    ) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(serialized, encoding="utf-8")
    if args.html_output:
        args.html_output.parent.mkdir(parents=True, exist_ok=True)
        args.html_output.write_text(
            render_review_packet(template),
            encoding="utf-8",
        )
    print(render_summary(template) if args.summary_only else serialized, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "EVIDENCE_MINING_SCHEMA",
    "EVIDENCE_SCOPE_SCHEMA",
    "EvidenceCatalogLoader",
    "build_evidence_mining_template",
    "load_dataset_rows",
    "load_saved_question_contexts",
    "match_candidate_source_ids",
    "match_evidence_source_ids",
    "render_review_packet",
    "render_summary",
]
