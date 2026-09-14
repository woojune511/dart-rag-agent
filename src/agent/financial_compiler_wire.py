"""Per-output compiler transport and one explicit, lossless lowering boundary.

References are execution-local addresses, never names or semantic aliases.
No legacy-program acceptance or guess-based response repair lives here.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import hashlib
from typing import Any, Literal, Mapping, Optional, Sequence

from src.agent.financial_graph_model_loaders import compiler_response_model, semantic_calculation_program_model
from src.agent.financial_request_units import build_request_units
from src.agent.financial_source_interpretation import interpretation_axis_sources
from src.agent.financial_source_bundles import build_semantic_source_bundles, source_bundle_id_by_candidate_id


class CompilerReferenceError(ValueError):
    def __init__(self, code, owner_id="", candidate_id=""):
        super().__init__(code)
        self.code, self.owner_id, self.candidate_id = code, owner_id, candidate_id


@dataclass(frozen=True, slots=True)
class CompilerReferencesV1:
    entries: tuple[tuple[str, str], ...]

    @classmethod
    def build(cls, catalog, obligations, query, payload):
        entries = {}

        def add(value, prefix):
            if not isinstance(value, str) or not value or value in entries:
                return
            # Output/request addresses are already readable checklist keys. Only
            # source addresses need compression; keep sibling planning context
            # identical across islands even when that sibling is not active.
            entries[value] = value if prefix in {"o", "r", "q"} else prefix + hashlib.sha256(value.encode()).hexdigest()[:8]

        for candidate in catalog:
            add(candidate["candidate_id"], "c")
            for axis in interpretation_axis_sources(candidate):
                add(axis, "a")
            for context in candidate.get("source_contexts") or []:
                add(context.get("context_id"), "x")
        for bundle in build_semantic_source_bundles(catalog):
            add(bundle.source_bundle_id, "b")
        for owner in obligations:
            add(owner["obligation_id"], "o")
            for dependency in owner.get("depends_on") or []:
                add(dependency, "o")
            for requirement in owner.get("evidence_requirements") or []:
                add(requirement["requirement_id"], "r")
        for unit in build_request_units(query):
            add(unit.request_unit_id, "q")

        def surfaces(node):
            if isinstance(node, dict):
                for key, value in node.items():
                    if key in {"surface_id", "piece_id"}:
                        add(value, "s" if key == "surface_id" else "p")
                    surfaces(value)
            elif isinstance(node, list):
                for value in node:
                    surfaces(value)
        surfaces(payload)
        if len(set(entries.values())) != len(entries):
            raise ValueError("compiler_reference_collision")
        return cls(tuple(sorted(entries.items())))

    def ref(self, source_id):
        try:
            return dict(self.entries)[source_id]
        except KeyError as exc:
            raise ValueError("unknown_internal_reference") from exc

    def resolve(self, ref):
        try:
            return {short: original for original, short in self.entries}[ref]
        except (KeyError, TypeError) as exc:
            raise ValueError("unknown_compiler_reference") from exc

    def project(self, value, *, reverse=False, field=""):
        """Only address fields/indices change; raw text, numbers and axes never do."""
        refs = dict(self.entries) if not reverse else {short: original for original, short in self.entries}
        indices = {"candidates_by_id", "source_bundles_by_id", "source_contexts_by_id",
                   "request_units_by_id", "candidate_ids_by_owner", "match_by_owner",
                   "interpretation_axis_sources", "source_rows_by_id", "read_only_dependency_outputs", "context_relations"}

        def visit(node, key):
            if isinstance(node, dict):
                return {refs.get(k, k) if key in indices else k: visit(v, k) for k, v in node.items()}
            if isinstance(node, (list, tuple)):
                return [visit(v, key) for v in node]
            if isinstance(node, str) and (key.endswith(("_id", "_ids", "_ref", "_refs")) or key == "depends_on"):
                return refs.get(node, node)
            return deepcopy(node)
        return visit(value, field)


def lower_compiler_response(response, *, model, refs, obligations, catalog, visibility, errors=None):
    """Resolve addresses and assemble fields. Invalid selections are never repaired."""
    raw = model.model_validate(response.model_dump() if hasattr(response, "model_dump") else response).model_dump()
    allowed = visibility.candidate_ids_by_owner()
    candidates = {row["candidate_id"]: row for row in catalog}
    bundle_ids = source_bundle_id_by_candidate_id(build_semantic_source_bundles(catalog))
    result = {"status": "ready", "direct_bindings": [], "expressions": [], "narrative_bindings": [],
              "source_assertions": [], "missing_obligation_ids": [], "ambiguous_obligation_ids": [], "rationale": raw["rationale"]}

    def selected(ref, owner_id, *, dependencies=()):
        try:
            source_id = refs.resolve(ref)
        except ValueError as exc:
            raise CompilerReferenceError("unknown_compiler_reference", owner_id) from exc
        if source_id in dependencies:
            return source_id
        if source_id not in candidates or source_id not in allowed.get(owner_id, ()):
            raise CompilerReferenceError("candidate_not_authorized_for_output_input", owner_id, source_id)
        return source_id

    def numeric(selection, owner_id, *, dependencies=()):
        source_id = selected(selection["source_ref"], owner_id, dependencies=dependencies)
        interpretation = refs.project(selection.get("interpretation"), reverse=True)
        contexts = refs.project(selection.get("context_bindings") or [], reverse=True)
        quote = selection.get("evidence_text")
        if source_id not in candidates:
            if interpretation is not None or contexts or quote is not None:
                raise ValueError("dependency_has_source_grounding")
        else:
            if quote is not None:
                result["source_assertions"].append({"source_bundle_id": bundle_ids[source_id],
                    "candidate_ids": [source_id], "evidence_text": quote})
        return source_id, interpretation, contexts

    def groups(rows, owner):
        requirement_ids = {refs.ref(row["requirement_id"]): row["requirement_id"] for row in owner.get("evidence_requirements") or []}
        for key, selections in rows.items():
            requirement_id = requirement_ids.get(key, "")
            for selection in selections:
                yield requirement_id, selection

    def readings(rows, owner):
        lowered = []
        for requirement_id, selection in groups(rows, owner):
            candidate_id = selected(selection["source_ref"], requirement_id or owner["obligation_id"])
            row = {"candidate_id": candidate_id, "source_requirement_id": requirement_id}
            for short, internal in (("row_description_quote", "row_description_quote"), ("surface_ref", "surface_id"),
                                    ("first_piece_ref", "first_piece_id"), ("last_piece_ref", "last_piece_id")):
                value = selection.get(short)
                if value is not None:
                    row[internal] = value if short == "row_description_quote" else refs.resolve(value)
            lowered.append(row)
        return lowered

    def lower_output(owner):
        owner_id = owner["obligation_id"]
        reply = raw["outputs"][refs.ref(owner_id)]
        content = reply["result"]
        if reply["status"] != "ready":
            if content is not None:
                raise ValueError("unavailable_output_has_content")
            result["ambiguous_obligation_ids" if reply["status"] == "ambiguous" else "missing_obligation_ids"].append(owner_id)
            return
        if content is None:
            raise ValueError("ready_output_missing_content")
        kind = owner["kind"]
        if kind == "direct_value":
            candidate_id, interpretation, contexts = numeric(content["selection"], owner_id)
            result["direct_bindings"].append({"obligation_id": owner_id, "candidate_id": candidate_id,
                "source_interpretation": interpretation, "context_bindings": contexts,
                "compatibility_candidate_ids": [selected(ref, owner_id) for ref in content["compatibility_refs"]]})
        elif kind == "derived_value":
            bindings = []
            for requirement_id, selection in groups(content["inputs"], owner):
                source_id, interpretation, contexts = numeric(selection, requirement_id or owner_id,
                    dependencies=owner.get("depends_on") or [])
                bindings.append({"variable": selection["variable"], "source_id": source_id,
                    "source_requirement_id": requirement_id, "source_interpretation": interpretation,
                    "context_bindings": contexts, "scope_applicability_fields": selection["scope_applicability_fields"]})
            display_id, display_interpretation, display_contexts = (numeric(content["source_display"], owner_id)
                if content["source_display"] is not None else (None, None, []))
            result["expressions"].append({"obligation_id": owner_id, "variable_bindings": bindings,
                **{key: content[key] for key in ("formula", "display_unit", "display_format", "source_display_reason", "constants")},
                "source_display_candidate_id": display_id, "source_display_interpretation": display_interpretation,
                "source_display_context_bindings": display_contexts,
                "compatibility_candidate_ids": [selected(ref, owner_id) for ref in content["compatibility_refs"]]})
        else:
            subjects, claims = [], []
            for index, subject in enumerate(content["subjects"], 1):
                subject_id = f"s{index}"
                subjects.append({"subject_binding_id": subject_id, "subject": subject["subject"],
                                 "evidence_selections": readings(subject["support"], owner)})
                claims.extend({"subject_binding_id": subject_id, "text": claim["text"],
                    "fact_evidence_selections": readings(claim["evidence"], owner)} for claim in subject["claims"])
            result["narrative_bindings"].append({"obligation_id": owner_id, "subject_bindings": subjects,
                "claims": claims, "scope_applicability_fields": content["scope_applicability_fields"],
                "basis_interpretation": content["basis_interpretation"]})
    for owner in obligations:
        assertion_count = len(result["source_assertions"])
        try:
            lower_output(owner)
        except ValueError as exc:
            if errors is None:
                raise
            del result["source_assertions"][assertion_count:]
            owner_id = owner["obligation_id"]
            errors.append({"code": str(exc), "obligation_id": owner_id,
                "owner_id": getattr(exc, "owner_id", "") or owner_id,
                "candidate_id": getattr(exc, "candidate_id", ""), "location": "compiler_response.outputs",
                "repair_action": "repair_program", "detail": "Reference conversion failed; no inferred repair."})
            result["missing_obligation_ids"].append(owner_id)
    if result["missing_obligation_ids"] or result["ambiguous_obligation_ids"]:
        result["status"] = "incomplete" if result["missing_obligation_ids"] else "ambiguous"
    # Internal parsing still checks assembly; the executor independently revalidates
    # selections, exact spans, source interpretations and the immutable visibility.
    return semantic_calculation_program_model().model_validate(result).model_dump()
