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
from src.agent.financial_formula_wire import lower_formula_tokens
from src.agent.financial_request_units import RequestUnitV1, build_request_units
from src.agent.financial_source_interpretation import interpretation_axis_sources
from src.agent.financial_source_bundles import SourceBundleV1, build_semantic_source_bundles


class CompilerReferenceError(ValueError):
    def __init__(self, code, owner_id="", candidate_id=""):
        super().__init__(code)
        self.code, self.owner_id, self.candidate_id = code, owner_id, candidate_id


@dataclass(frozen=True, slots=True)
class CompilerReferencesV1:
    entries: tuple[tuple[str, str], ...]
    numeric_axes: tuple[tuple[str, tuple[str, ...]], ...]
    owner_context_refs: tuple[tuple[str, tuple[str, ...]], ...]
    numeric_source_kinds: tuple[tuple[str, str], ...]
    request_units: tuple[RequestUnitV1, ...]
    prose_bundles: tuple[SourceBundleV1, ...]

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
        bundles = build_semantic_source_bundles(catalog)
        for bundle in bundles:
            add(bundle.source_bundle_id, "b")
        for owner in obligations:
            add(owner["obligation_id"], "o")
            for dependency in owner.get("depends_on") or []:
                add(dependency, "o")
            for requirement in owner.get("evidence_requirements") or []:
                add(requirement["requirement_id"], "r")
        request_units = build_request_units(query)
        for unit in request_units:
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
        exposed = set(payload.get("source_contexts_by_id") or {})
        visible = set(payload.get("candidates_by_id") or {})
        numeric = {row["candidate_id"]: row for row in catalog if row.get("kind") == "numeric"}
        contexts_by_owner = {}
        for cohort in payload.get("cohorts") or []:
            permitted = contexts_by_owner.setdefault(cohort["owner_id"], set())
            for candidate_id in cohort.get("candidate_ids") or []:
                if candidate_id not in visible or candidate_id not in numeric:
                    continue
                permitted.update(entries[context["context_id"]]
                    for context in numeric[candidate_id].get("source_contexts") or []
                    if context.get("context_id") in exposed)
        prose_ids = {candidate_id for bundle in bundles if bundle.source_kind == "prose_sentence"
                     for candidate_id in bundle.candidate_ids}
        return cls(tuple(sorted(entries.items())),
            tuple(sorted((key, tuple(interpretation_axis_sources(row))) for key, row in numeric.items())),
            tuple(sorted((key, tuple(sorted(values))) for key, values in contexts_by_owner.items())),
            tuple(sorted((key, "prose" if row.get("candidate_kind") == "sentence_value" and key in prose_ids
                          else "cell") for key, row in numeric.items())), request_units,
            tuple(bundle for bundle in bundles if bundle.source_kind == "prose_sentence"))

    def context_refs_for_owner(self, owner_id):
        return dict(self.owner_context_refs).get(owner_id, ())

    def axis_refs_for_candidate(self, candidate_id):
        return dict(self.numeric_axes).get(candidate_id, ())

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
        permission_indices = {"candidate_ids_by_owner", "allowed_candidate_ids_by_owner"}
        indices = {"candidates_by_id", "source_bundles_by_id", "source_contexts_by_id", "bundles_by_id",
                   "request_units_by_id", "candidate_ids_by_owner",
                   "interpretation_axis_sources", "source_rows_by_id", "read_only_dependency_outputs", "context_relations", *permission_indices}

        def visit(node, key):
            if isinstance(node, dict):
                return {refs.get(k, k) if key in indices else k: visit(v, "candidate_ids" if key in permission_indices else k)
                        for k, v in node.items()}
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
    prose_bundles = {candidate_id: bundle for bundle in build_semantic_source_bundles(catalog)
                    if bundle.source_kind == "prose_sentence" for candidate_id in bundle.candidate_ids}
    request_units = {unit.request_unit_id: unit for unit in refs.request_units}
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
        contexts, interpretation_contexts = [], []
        for evidence in selection.get("context_evidence") or []:
            context_id = refs.resolve(evidence["context_ref"])
            proof = {"context_id": context_id, "evidence_text": evidence["evidence_text"]}
            if evidence["supports_interpretation"]:
                if interpretation is None:
                    raise CompilerReferenceError("context_without_interpretation", owner_id, source_id)
                interpretation_contexts.append(proof)
            elif not evidence["resolves"]:
                raise CompilerReferenceError("unused_context_evidence", owner_id, source_id)
            contexts.extend({**proof, **binding} for binding in evidence["resolves"])
        if source_id not in candidates:
            if interpretation is not None or contexts:
                raise ValueError("dependency_has_source_grounding")
        else:
            if interpretation is not None:
                # Selection addresses exactly one cell: carry all its observed
                # axes without asking the model to repeat (or invent) axis IDs.
                interpretation.update(axis_refs=list(refs.axis_refs_for_candidate(source_id)),
                    context_evidence=interpretation_contexts)
            if candidates[source_id].get("candidate_kind") == "sentence_value":
                bundle = prose_bundles.get(source_id)
                span = bundle.value_span_by_candidate_id().get(source_id) if bundle else None
                if span is None:
                    raise CompilerReferenceError("source_assertion_value_span_missing", owner_id, source_id)
                # The selected candidate already addresses one physical value.
                # Copy its complete span, not a model-retyped or inferred quote.
                result["source_assertions"].append({"source_bundle_id": bundle.source_bundle_id,
                    "candidate_ids": [source_id], "evidence_text": bundle.source_text[span[0]:span[1]]})
        return source_id, interpretation, contexts

    def request_operand(item, owner):
        try:
            unit_id = refs.resolve(item["request_unit_id"])
        except ValueError as exc:
            raise CompilerReferenceError("constant_request_not_owned", owner["obligation_id"]) from exc
        if unit_id not in request_units or unit_id not in (owner.get("request_unit_ids") or []):
            raise CompilerReferenceError("constant_request_not_owned", owner["obligation_id"])
        # Whole instruction linkage, not unique quantity occurrence or meaning.
        return dict(item, request_unit_id=unit_id, source_text=request_units[unit_id].text)

    def groups(rows, owner):
        requirement_ids = {refs.ref(row["requirement_id"]): row["requirement_id"] for row in owner.get("evidence_requirements") or []}
        for key, selections in rows.items():
            requirement_id = requirement_ids.get(key, "")
            for selection in selections:
                if key == "dependencies" and refs.resolve(selection.get("source_ref")) not in (owner.get("depends_on") or []):
                    raise CompilerReferenceError("nondependency_in_dependency_input", owner["obligation_id"])
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
                    try:
                        row[internal] = value if short == "row_description_quote" else refs.resolve(value)
                    except ValueError as exc:
                        raise CompilerReferenceError("unknown_compiler_reference",
                            requirement_id or owner["obligation_id"], candidate_id) from exc
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
                    dependencies=(owner.get("depends_on") or []) if not requirement_id else ())
                bindings.append({"variable": selection["variable"], "source_id": source_id,
                    "source_requirement_id": requirement_id, "source_interpretation": interpretation,
                    "context_bindings": contexts, "scope_applicability_fields": selection["scope_applicability_fields"]})
            display_id, display_interpretation, display_contexts = (numeric(content["source_display"], owner_id)
                if content["source_display"] is not None else (None, None, []))
            result["expressions"].append({"obligation_id": owner_id, "variable_bindings": bindings,
                "comparison_request_unit_id": (refs.resolve(content["comparison_request_unit_id"])
                    if content["comparison_request_unit_id"] is not None else None),
                **{key: content[key] for key in ("display_unit", "display_format", "source_display_reason")},
                **lower_formula_tokens(content["formula"], source_variables=[b["variable"] for b in bindings],
                    resolve_request=lambda item: request_operand(item, owner)),
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
                "candidate_id": getattr(exc, "candidate_id", ""), "location": getattr(exc, "location", "compiler_response.outputs"),
                "repair_action": "repair_program", "detail": "Reference conversion failed; no inferred repair."})
            result["missing_obligation_ids"].append(owner_id)
    if result["missing_obligation_ids"] or result["ambiguous_obligation_ids"]:
        result["status"] = "incomplete" if result["missing_obligation_ids"] else "ambiguous"
    # Internal parsing still checks assembly; the executor independently revalidates
    # selections, exact spans, source interpretations and the immutable visibility.
    return semantic_calculation_program_model().model_validate(result).model_dump()
