"""Compiler presentation; no candidate selection or semantic authority."""

from __future__ import annotations

from copy import deepcopy
import json
import re
from typing import Any, Mapping, Sequence

from src.agent.financial_calculation_execution import _row_description_reading
from src.agent.financial_request_units import build_request_units, project_request_units
from src.utils.source_segments import project_source_surface


PROMPT_MATCH_FIELDS = (
    "state", "scope_state", "subject_state",
    "owner_kind_state", "metric_state", "unit_state", "target_concept_keys",
    "target_local_subjects", "selection_mode", "reading_metric_state", "context_metric_state",
)
PROMPT_COHORT_FIELDS = (
    "cohort_id", "owner_id", "parent_obligation_id", "owner_type", "candidate_kind",
    "candidate_ids", "candidate_id_fingerprint", "limit",
)
PROMPT_GROUP_FIELDS = (
    "selection_mode", "physical_table_id", "physical_row_id", "candidate_ids",
    "required_candidate_ids", "policy_group_names",
)
DOCUMENT_FIELDS = ("company", "document_company", "year", "source_document_id", "source_anchor")
RESPONSIBILITY_SCOPE_FIELDS = ("company", "period", "consolidation_scope", "segment", "basis")
EMPTY_SCALAR_FIELDS = frozenset((
    "raw_value", "raw_unit", "value_year", "source_value_span", "period",
    "source_period_surface", "period_role", "period_label_surfaces", "period_source",
    "period_label_scope", "aggregation_stage", "aggregate_label", "value_role",
))


def project_output_responsibility_context(
    query: str, obligations: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Copy an accepted plan's output responsibilities, never execution/evidence state.

    Request and output order are preserved. This describes planned work, not
    whether a sibling output succeeded, and grants no binding or quote authority.
    """
    return {
        "schema": "output_responsibility_context_v1",
        "role": "planning_context_only",
        "outputs": [{
            "obligation_id": row["obligation_id"], "kind": row["kind"], "label": row["label"],
            "request_unit_ids": deepcopy(row["request_unit_ids"]),
            "local_subjects": deepcopy((row.get("semantic_target") or {}).get("local_subjects") or []),
            "scope": {key: deepcopy(value) for key, value in (row.get("scope") or {}).items()
                      if key in RESPONSIBILITY_SCOPE_FIELDS},
            "source_sections": deepcopy(row.get("source_sections") or []),
            **({"source_section_bindings": deepcopy(row["source_section_bindings"])}
               if row.get("source_section_bindings") else {}),
        } for row in obligations],
        "request_units_by_id": project_request_units(build_request_units(query), obligations),
    }


def project_prompt_match(match: Mapping[str, Any]) -> dict[str, Any]:
    return {key: deepcopy(match[key]) for key in PROMPT_MATCH_FIELDS if key in match}


def project_prompt_cohort(cohort: Mapping[str, Any]) -> dict[str, Any]:
    result = {key: deepcopy(cohort[key]) for key in PROMPT_COHORT_FIELDS if key in cohort}
    group = cohort.get("source_defined_group_selection")
    if isinstance(group, Mapping):
        result["source_defined_group_selection"] = {
            key: deepcopy(group[key]) for key in PROMPT_GROUP_FIELDS if key in group
        }
    return result


def narrative_only_cohorts(cohorts: Sequence[Mapping[str, Any]]) -> bool:
    """Use declared owner kinds, not the format of the evidence they can read."""
    outputs = [row for row in cohorts if row.get("owner_type") == "obligation"]
    return bool(outputs) and all(row.get("candidate_kind") == "evidence" for row in outputs)


def project_prompt_retry_feedback(feedback: str, *, narrative_only: bool) -> str:
    """Remove numeric explanatory clauses only, never draft/error/authority data."""
    if not narrative_only or feedback == "-":
        return feedback
    result = json.loads(feedback)
    contract = result.get("repair_contract", {})
    for key in ("formula_variable_binding_invariant", "candidate_requirement_binding_invariant",
                "required_evidence_binding_invariant", "source_assertion_invariant",
                "dependency_input_invariant"):
        contract.pop(key, None)
    return json.dumps(result, ensure_ascii=False, separators=(",", ":"))


def _locator_parts(locator: str) -> tuple:
    # Numeric XML sibling indices sort naturally (P[2] before P[10]). No title text.
    return tuple((0, int(part)) if part.isdigit() else (1, part)
                 for part in re.split(r"(\d+)", locator))


def _located_order(context: Mapping[str, Any]) -> tuple:
    return (_locator_parts(str(context.get("source_locator") or "")),
            tuple(context.get("source_span") or ()), str(context.get("context_id") or ""))


def _heading_order(context: Mapping[str, Any], relation: str) -> tuple:
    parent = str(context.get("parent_locator") or "")
    # Within the same located scope, its formal title encloses local headings.
    # Relation cannot reorder different parents or override outer/inner hierarchy.
    return (parent.count("/"), _locator_parts(parent), relation != "ancestor_heading",
            _located_order(context))


def project_reading_payload(
    payload: Mapping[str, Any], catalog: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Move exact quote containers beside their attached body, keeping authority indices.

    A repeated context uses an explicit reference to its first surface, never a
    concatenated quote. Attachment indices and per-candidate context IDs remain
    authoritative even when visible members share a physical-row bundle.
    """
    result = deepcopy(dict(payload))
    contexts = result["source_contexts_by_id"]
    bundles = result["source_bundles_by_id"]
    candidates = result["candidates_by_id"]
    originals = {str(row["candidate_id"]): row for row in catalog}
    narrative_only = narrative_only_cohorts(result["cohorts"])
    provenance = {}
    for candidate_id, row in candidates.items():
        provenance[candidate_id] = {key: row.pop(key) for key in DOCUMENT_FIELDS if key in row}
        original = originals[candidate_id]
        source_provenance = row.get('source_context_provenance') or {}
        if source_provenance.get('source_segments'):
            # The exact raw text stays in the catalog; do not reintroduce a
            # concatenated quote through the provenance metadata index.
            source_provenance.pop('source_text', None)
        # A shared bundle does not grant every member all other members' contexts.
        attached = {str(c["context_id"]) for c in original.get("source_contexts") or [] if c.get("context_id")}
        if attached != set(bundles[row["source_bundle_id"]].get("context_ids", [])):
            row["attached_context_ids"] = sorted(attached)
        if narrative_only:
            # Missing/empty values are not known matches. Explicit UNKNOWN and
            # applicability states remain; numeric/mixed projections stay complete.
            for key in list(row):
                if row[key] in (None, "", [], {}) and key != "attached_context_ids":
                    del row[key]
        # Advertise only witnessed whole-axis options using the existing validator.
        # Partial quotes still undergo the unchanged binding-local validation.
        options = []
        if original.get("kind") == "numeric":
            projected = {**original, "source_bundle_text": bundles[row["source_bundle_id"]]["source_text"]}
            for axis in [original.get("row_label"), *(original.get("row_headers") or [])]:
                try:
                    reading = _row_description_reading(projected, axis)
                except ValueError:
                    continue
                if reading["quote"] not in options:
                    options.append(reading["quote"])
        if options:
            row["row_description_quote_options"] = options

    def headings(bundle):
        relations = bundle.get("context_relations", {})
        return sorted((contexts[key] for key in bundle.get("context_ids", [])
                       if relations[key] in {"ancestor_heading", "intermediate_heading"}),
                      key=lambda context: _heading_order(context, relations[context["context_id"]]))

    def source_identity(bundle):
        members = [originals[key] for key in bundle["candidate_ids"]]
        documents = sorted({str(row.get("source_document_sha256") or row.get("source_document_id") or "")
                            for row in members} - {""})
        if documents:
            return tuple(documents)
        documents = sorted({str(contexts[key].get("document_sha256") or "")
                            for key in bundle.get("context_ids", [])} - {""})
        # Unknown provenance does not merge unrelated sources by filing-company/name.
        return tuple(documents) or (str(members[0].get("source_candidate_id") or bundle["source_bundle_id"]),)

    def bundle_order(bundle):
        members = [originals[key] for key in bundle["candidate_ids"]]
        location = min((_located_order({
            "source_locator": row.get("source_table_locator", ""),
            "source_span": row.get("source_bundle_context_span") or row.get("source_span") or [],
        }) for row in members), default=())
        return (source_identity(bundle),
                tuple(_heading_order(c, bundle["context_relations"][c["context_id"]]) for c in headings(bundle)),
                location, bundle["source_bundle_id"])

    emitted_contexts: set[str] = set()

    def fragment(key, relation):
        fragment = {"context_id": key, "relation": relation}
        if key not in emitted_contexts:
            fragment.update(project_source_surface(contexts[key]['source_text'], contexts[key].get('source_segments', [])))
            emitted_contexts.add(key)
        else:
            fragment["surface_ref"] = key
        return fragment

    readings = []
    groups = {}
    for bundle in sorted(bundles.values(), key=bundle_order):
        # Share layout only when the complete observed attachment set agrees.
        # Different peer headings, adjacency or documents remain separate units.
        group_key = (source_identity(bundle), tuple(sorted(bundle.get("context_relations", {}).items())))
        body = {"source_bundle_id": bundle["source_bundle_id"],
                "candidate_ids": list(bundle["candidate_ids"]),
                **project_source_surface(bundle['source_text'], bundle.get('source_segments', []))}
        if group_key in groups:
            groups[group_key]["bodies"].append(body)
            continue
        relations = bundle.get("context_relations", {})
        heading_ids = [c["context_id"] for c in headings(bundle)]
        remaining = sorted((key for key in bundle.get("context_ids", []) if key not in heading_ids),
                           key=lambda key: _located_order(contexts[key]))
        after = [key for key in remaining if relations[key] in {"following_block", "source_continuation"}]
        before = [key for key in remaining if key not in after]
        reading = {
            "enclosing_contexts": [fragment(key, relations[key]) for key in heading_ids],
            "preceding_contexts": [fragment(key, relations[key]) for key in before],
            "bodies": [body],
            "following_contexts": [fragment(key, relations[key]) for key in after],
        }
        groups[group_key] = reading
        readings.append(reading)
    # Quote text is only in reading surfaces, not repeated in the authority indices.
    for context in contexts.values():
        context.pop("source_text")
    bundle_provenance = {}
    for key, bundle in bundles.items():
        bundle.pop("source_text")
        bundle_provenance[key] = {"source_anchor": bundle.pop("source_anchor")}
    return {
        "schema": "semantic_program_candidate_payload_v7",
        "reading_mode": "narrative_only" if narrative_only else "numeric_or_mixed",
        "source_readings": readings,
        **{key: value for key, value in result.items() if key != "schema"},
        "document_provenance": {"candidates_by_id": provenance, "bundles_by_id": bundle_provenance},
    }
