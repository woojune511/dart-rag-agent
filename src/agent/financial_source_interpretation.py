"""Source-linked model interpretations, not string-based semantic equivalence."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

from src.agent.financial_request_units import build_request_units
from src.agent.financial_runtime_normalization import resolve_structured_source_unit, resolve_unit_spec
from src.config.retrieval_policy import SOURCE_COUNT_UNIT_POLICY, TABLE_COLUMN_UNIT_POLICY
from src.utils.source_segments import source_quote_is_contiguous


def interpretation_axis_sources(candidate: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    """Address complete observed paths without changing any catalog identity."""
    result = {}
    if candidate.get("candidate_kind") == "sentence_value":
        return result
    for field, values in (
        ("row_headers", candidate.get("row_headers") or [candidate.get("row_label")]),
        ("column_headers", candidate.get("column_headers") or []),
    ):
        path = [value for value in values if isinstance(value, str) and value.strip()]
        if not path:
            continue
        source = {"field": field, "path": path, **{key: candidate.get(key, "") for key in (
            "candidate_id", "source_document_id", "source_document_sha256", "source_anchor",
            "physical_table_id", "physical_row_id", "physical_cell_id", "physical_value_id",
            "source_row_id", "table_source_id")}}
        digest = hashlib.sha256(json.dumps(source, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
        result[f"axis_{digest[:20]}"] = source
    return result


def source_unit_options(candidate: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Offer located axis readings without changing a scalar or its known unit."""
    if (candidate.get("kind") != "numeric" or candidate.get("candidate_kind") == "sentence_value"
            or not candidate.get("physical_cell_id") or not candidate.get("physical_table_id")
            or candidate.get("normalized_unit") != "UNKNOWN"
            or candidate.get("raw_unit") or candidate.get("source_unit_hint")):
        return []
    unit, origin, _ = resolve_structured_source_unit(str(candidate.get("raw_value") or ""), "",
        row_headers=candidate.get("row_headers") or [], column_headers=candidate.get("column_headers") or [],
        source_contexts=candidate.get("source_contexts") or [])
    if unit or origin == "ambiguous_column_unit":
        return []
    axes = interpretation_axis_sources(candidate)
    normalize = lambda text: " ".join(text.split()).casefold()
    labels = {normalize(label): row["unit"] for row in SOURCE_COUNT_UNIT_POLICY for label in row["labels"]}
    conflicts = {normalize(label) for group in TABLE_COLUMN_UNIT_POLICY["column_groups"]
                 if "COUNT" not in group["dimensions"] for label in group["headers"]}
    if any(normalize(label) in conflicts for axis in axes.values() for label in axis["path"]):
        return []
    choices = []
    for axis_id, axis in axes.items():
        for index, label in enumerate(axis["path"]):
            selected_unit = labels.get(normalize(label))
            spec = resolve_unit_spec(selected_unit or "")
            if not spec or spec.normalized_dimension != "COUNT" or spec.scale != 1:
                continue
            choice = {"candidate_id": candidate["candidate_id"], "axis_ref": axis_id,
                      "label_index": index, "label": label, "unit": selected_unit,
                      "normalized_unit": spec.normalized_dimension, "scale": spec.scale}
            digest = hashlib.sha256(json.dumps(choice, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
            choices.append({"unit_option_id": "unit_" + digest[:20], **choice})
    # Distinct counting units on the same cell need a less ambiguous source.
    return choices if len({choice["unit"] for choice in choices}) <= 1 else []


def apply_source_unit_resolution(candidate: Mapping[str, Any], proof: Mapping[str, Any]) -> dict[str, Any]:
    """Project the validated dimension while retaining the original raw unit."""
    resolution = proof.get("unit_resolution")
    if not resolution:
        return dict(candidate)
    return {**dict(candidate), "normalized_unit": resolution["normalized_unit"],
            "result_unit": resolution["unit"], "source_unit_resolution": dict(resolution)}


def attached_context_quote(candidate: Mapping[str, Any], binding: Mapping[str, Any], *, subject=False) -> dict[str, Any]:
    contexts = {str(row.get("context_id") or ""): row for row in candidate.get("source_contexts") or []}
    context = contexts.get(str(binding.get("context_id") or ""))
    allowed = {"ancestor_heading", "intermediate_heading", "caption", "preceding_block", "following_block"}
    if not subject:
        allowed.add("table_text_row")
    if (not context or not candidate.get("source_table_locator")
            or not candidate.get("source_document_sha256")
            or context.get("document_sha256") != candidate.get("source_document_sha256")
            or context.get("relation") not in allowed):
        raise ValueError("context_not_attached_to_candidate")
    table = str(candidate["source_table_locator"])
    parent, locator, relation = str(context.get("parent_locator") or ""), str(context.get("source_locator") or ""), context["relation"]
    attached = (bool(parent) and table.startswith(parent + "/")
                if relation in {"ancestor_heading", "intermediate_heading"} else
                locator.startswith(table + "/") if relation in {"caption", "table_text_row"} else
                parent == table.rsplit("/", 1)[0])
    if not attached:
        raise ValueError("context_not_attached_to_candidate")
    quote, text = binding.get("evidence_text"), str(context.get("source_text") or "")
    if (not isinstance(quote, str) or not quote.strip()
            or not source_quote_is_contiguous(text, quote, context.get("source_segments") or [])):
        raise ValueError("context_quote_not_exact")
    start = text.index(quote)
    return {"context_id": str(context["context_id"]), "evidence_text": quote,
            "relation": relation, "document_sha256": context["document_sha256"],
            "source_locator": locator, "source_span": list(context.get("source_span") or []),
            "quote_span": [start, start + len(quote)]}


def validate_source_interpretation(
    candidate: Mapping[str, Any], interpretation: Any, *, owner: Mapping[str, Any],
    query: str, parent_owner: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    if not isinstance(interpretation, Mapping):
        raise ValueError("missing_source_interpretation")
    allowed = {"request_unit_ids", "subject", "metric", "scope", "axis_refs", "context_evidence", "source_evidence_text", "unit_option_id"}
    if set(interpretation) - allowed or any(
        not isinstance(interpretation.get(key), str) or not interpretation[key].strip()
        for key in ("subject", "metric")
    ):
        raise ValueError("invalid_source_interpretation")
    refs = interpretation.get("request_unit_ids")
    scope = interpretation.get("scope") or {}
    if (not isinstance(scope, Mapping) or set(scope) - {"segment", "basis"}
            or any(not isinstance(value, str) for value in scope.values())):
        raise ValueError("invalid_source_interpretation_scope")
    known = {unit.request_unit_id: unit for unit in build_request_units(query)}
    owned = set(owner.get("request_unit_ids") or (parent_owner or {}).get("request_unit_ids") or [])
    if (not isinstance(refs, list) or not refs or any(not isinstance(ref, str) or ref not in known or ref not in owned for ref in refs)):
        raise ValueError("source_interpretation_request_mismatch")
    axes, axis_refs, contexts = interpretation_axis_sources(candidate), interpretation.get("axis_refs", []), interpretation.get("context_evidence", [])
    source_quote = interpretation.get("source_evidence_text")
    if (not isinstance(axis_refs, list) or not isinstance(contexts, list)
            or not (axis_refs or contexts or source_quote) or any(not isinstance(ref, str) or ref not in axes for ref in axis_refs)
            or any(not isinstance(row, Mapping) for row in contexts)):
        raise ValueError("source_interpretation_evidence_mismatch")
    evidence = [axes[ref] for ref in dict.fromkeys(axis_refs)]
    evidence.extend(attached_context_quote(candidate, row, subject=True) for row in contexts)
    if source_quote is not None:
        source_text = str(candidate.get("source_text") or "")
        if (candidate.get("candidate_kind") != "sentence_value" or not isinstance(source_quote, str)
                or not source_quote.strip() or not source_quote_is_contiguous(source_text, source_quote, [])):
            raise ValueError("source_interpretation_quote_mismatch")
        start = source_text.index(source_quote)
        evidence.append({"candidate_id": candidate["candidate_id"], "evidence_text": source_quote,
                         "source_span": [start, start + len(source_quote)]})
    result = {"request_units": [{"request_unit_id": ref, "text": known[ref].text,
               "span": [known[ref].start, known[ref].end]} for ref in dict.fromkeys(refs)],
              "subject": interpretation["subject"], "metric": interpretation["metric"], "scope": dict(scope),
              "evidence": evidence, "validation_scope": "source_linkage_not_semantic_equivalence"}
    option_id = interpretation.get("unit_option_id")
    if option_id is not None:
        options = {row["unit_option_id"]: row for row in source_unit_options(candidate)}
        if not isinstance(option_id, str) or option_id not in options:
            raise ValueError("source_unit_option_mismatch")
        option = options[option_id]
        if option["axis_ref"] not in axis_refs:
            raise ValueError("source_unit_axis_missing")
        result["unit_resolution"] = {**option, "axis_source": axes[option["axis_ref"]],
            "source_raw_unit": str(candidate.get("raw_unit") or ""),
            "source_normalized_unit": str(candidate.get("normalized_unit") or "UNKNOWN"),
            "validation_scope": "source_linkage_not_semantic_equivalence"}
    result["fingerprint"] = hashlib.sha256(json.dumps(result, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    return result
