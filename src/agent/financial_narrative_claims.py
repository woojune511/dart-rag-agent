"""Claim-local quote/subject provenance checks, not semantic entailment judging."""

from typing import Any, Callable, Mapping, Sequence

from src.agent.financial_program_projection import render_narrative_claim
from src.agent.financial_source_bundles import build_semantic_source_bundles
from src.agent.financial_evidence_addresses import build_narrative_address_book, resolve_narrative_selection
from src.utils.source_segments import source_quote_is_contiguous


def project_narrative_retry_drafts(
    program: Mapping[str, Any], *, obligations: Sequence[Mapping[str, Any]],
    target_obligation_ids: Sequence[str], candidate_ids_by_owner: Mapping[str, Sequence[str]],
    visible_catalog: Sequence[Mapping[str, Any]], validation_errors: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Carry failed model statements for repair, without granting source authority.

    Claims keep their original error locations, including claims with no remaining
    links. Only currently selectable owner/requirement links survive; their quotes
    are still unvalidated drafts, not evidence. Failed subject locations additionally
    show their exact selected text from the current prompt's address book, never a
    searched/repaired range. Accepted outputs are not replayed.
    """
    targets = set(target_obligation_ids)
    owners = {
        obligation["obligation_id"]: {
            row["requirement_id"] for row in obligation.get("evidence_requirements") or []
        }
        for obligation in obligations
        if obligation.get("kind") == "narrative" and obligation["obligation_id"] in targets
    }
    selectable = {owner: set(ids) for owner, ids in candidate_ids_by_owner.items()}
    failed_subjects = {(error.get("obligation_id"), error.get("location"))
        for error in validation_errors if error.get("code") == "ungrounded_narrative_subject"}
    book = None
    drafts = []
    for owner_id, requirement_ids in owners.items():
        for binding in program.get("narrative_bindings") or []:
            if binding["obligation_id"] != owner_id or not binding.get("claims"):
                continue
            if binding.get("subject_bindings"):
                def copied_links(links):
                    return [{key: link[key] for key in ("candidate_id", "source_requirement_id",
                        "row_description_quote", "surface_id", "first_piece_id", "last_piece_id") if key in link}
                        for link in links
                        if link["candidate_id"] in selectable.get(owner_id, set())
                        and (not link.get("source_requirement_id") or (
                            link["source_requirement_id"] in requirement_ids
                            and link["candidate_id"] in selectable.get(link["source_requirement_id"], set())))]
                claims, subjects = [], []
                for index, claim in enumerate(binding["claims"]):
                    links = copied_links(claim["fact_evidence_selections"])
                    claims.append({"location": f"narrative_claims[{index}]",
                        "subject_binding_id": claim["subject_binding_id"], "text": claim["text"],
                        "fact_evidence_selections": links,
                        "omitted_evidence_binding_count": len(claim["fact_evidence_selections"]) - len(links)})
                for index, subject in enumerate(binding["subject_bindings"]):
                    links = copied_links(subject["evidence_selections"])
                    location = f"subject_bindings[{index}]"
                    draft = {"location": location,
                        "subject_binding_id": subject["subject_binding_id"], "subject": subject["subject"],
                        "evidence_selections": links,
                        "omitted_evidence_binding_count": len(subject["evidence_selections"]) - len(links)}
                    if (owner_id, location) in failed_subjects:
                        if book is None:
                            book = build_narrative_address_book(visible_catalog)
                        checks = []
                        for link in links:
                            check = {key: link[key] for key in ("candidate_id", "source_requirement_id",
                                "surface_id", "first_piece_id", "last_piece_id") if key in link}
                            try:
                                surface, quote, span = resolve_narrative_selection(link, book)
                            except ValueError as exc:
                                check["resolution_error"] = str(exc)
                            else:
                                check.update(selected_text=quote, source_field=surface.source_field,
                                    source_span=list(span), contains_declared_subject=subject["subject"] in quote)
                            checks.append(check)
                        draft["source_selection_check"] = {"declared_subject": subject["subject"], "selections": checks}
                    subjects.append(draft)
                drafts.append({"obligation_id": owner_id, "subject_bindings": subjects, "claims": claims,
                    "scope_applicability_fields": list(binding.get("scope_applicability_fields") or [])})
                continue
            claims = []
            for index, claim in enumerate(binding["claims"]):
                links = []
                for link in claim.get("evidence_bindings") or []:
                    candidate_id = link["candidate_id"]
                    requirement_id = link.get("source_requirement_id") or ""
                    if candidate_id not in selectable.get(owner_id, set()):
                        continue
                    if requirement_id and (requirement_id not in requirement_ids
                            or candidate_id not in selectable.get(requirement_id, set())):
                        continue
                    links.append({key: link[key] for key in (
                        "candidate_id", "source_requirement_id", "row_description_quote",
                        "evidence_text", "context_id",
                    ) if key in link})
                claims.append({"location": f"narrative_claims[{index}]",
                    "subject": claim["subject"], "text": claim["text"], "evidence_bindings": links,
                    "omitted_evidence_binding_count": len(claim.get("evidence_bindings") or []) - len(links)})
            drafts.append({"obligation_id": owner_id, "claims": claims,
                "scope_applicability_fields": list(binding.get("scope_applicability_fields") or [])})
    return drafts


def validate_narrative_claims(
    binding: Mapping[str, Any], candidate_by_id: Mapping[str, Mapping[str, Any]], *,
    number_check: Callable[[str, Sequence[Mapping[str, Any]]], list[str]],
    visible_candidate_ids: Sequence[str] | None = None,
    require_addressed: bool = False,
) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    claims = binding.get("claims") or []
    if not claims:
        return [], []
    if binding.get("subject_bindings"):
        return _validate_addressed_claims(binding, candidate_by_id, number_check=number_check,
            visible_candidate_ids=visible_candidate_ids)
    if require_addressed:
        return [], [{"code": "missing_narrative_subject_bindings", "location": "subject_bindings",
            "detail": "Use explicit subject_bindings and source-addressed fact selections; raw quote claims are historical only.",
            "owner_id": str(binding.get("obligation_id") or ""), "candidate_id": ""}]
    readings, errors = [], []
    selected_ids = set(binding.get("candidate_ids") or [])
    # Match prompt serialization: a shared row's source text can come from an
    # unselected visible member, never from an unexposed catalog row.
    visible_ids = set(candidate_by_id if visible_candidate_ids is None else visible_candidate_ids)
    visible = [candidate_by_id[key] for key in visible_ids if key in candidate_by_id]
    bundles = {key: bundle for bundle in build_semantic_source_bundles(visible)
        for key in bundle.candidate_ids}

    for index, claim in enumerate(claims):
        location = f"narrative_claims[{index}]"

        def fail(code: str, link: Mapping[str, Any] | None = None, *, detail: str) -> None:
            errors.append({"code": code, "location": location, "detail": detail,
                "owner_id": str((link or {}).get("source_requirement_id") or binding.get("obligation_id") or ""),
                "candidate_id": str((link or {}).get("candidate_id") or "")})

        text, subject = claim.get("text"), claim.get("subject")
        if not isinstance(text, str) or not text.strip() or not isinstance(subject, str) or not subject.strip():
            fail("invalid_narrative_claim", detail="Provide nonblank subject and text strings.")
            continue
        rendered_text = render_narrative_claim(claim)
        links = claim.get("evidence_bindings") or []
        if not links:
            fail("missing_narrative_claim_evidence", detail="Bind at least one visible source and its exact quote to this claim.")
        evidence, number_sources, quotes = [], [], []
        for link in links:
            candidate_id = str(link.get("candidate_id") or "")
            candidate = candidate_by_id.get(candidate_id)
            bundle = bundles.get(candidate_id)
            if not candidate or not bundle or candidate_id not in selected_ids:
                # The ordinary owner/visibility/selection validator rejects these IDs.
                continue
            quote = link.get("evidence_text")
            context_id = link.get("context_id", "")
            surface, source_field = bundle.source_text, "source_bundle"
            segments = bundle.segment_projection()
            source_span = list(candidate.get("source_bundle_context_span") or [])
            if context_id:
                contexts = [row for row in candidate.get("source_contexts") or []
                    if row.get("context_id") == context_id]
                if len(contexts) != 1:
                    fail("invalid_narrative_claim_context", link,
                        detail="Use a context_id attached to this candidate, or leave it empty to quote its source bundle.")
                    continue
                surface = str(contexts[0].get("source_text") or "")
                segments = contexts[0].get('source_segments') or []
                source_field = "source_context"
                source_span = list(contexts[0].get("source_span") or [])
            if not isinstance(quote, str) or not quote.strip() or not source_quote_is_contiguous(surface, quote, segments):
                fail("invalid_narrative_claim_quote", link,
                    detail="Copy evidence_text verbatim as one continuous excerpt from this candidate's visible bundle or named attached context. "
                        "Do not insert a subject or replace a pronoun; keep subject context and fact text in separate evidence_bindings, not a joined quote."
                        + (" Quote each source segment separately; do not join adjacent cells in one evidence_text." if segments else ""))
                continue
            # Repeated identical occurrences do not establish one exact location.
            start = surface.find(quote)
            if surface.find(quote, start + 1) >= 0:
                fail("ambiguous_narrative_claim_quote", link,
                    detail="Extend the exact quote so it identifies only one occurrence in the selected source surface.")
                continue
            quotes.append(quote)
            number_sources.append({"source_text": quote, "year": candidate.get("year")})
            evidence.append({"candidate_id": candidate_id,
                "source_requirement_id": str(link.get("source_requirement_id") or ""),
                "source_bundle_id": bundle.source_bundle_id, "context_id": context_id,
                "source_field": source_field, "evidence_text": quote,
                "source_span": [start, start + len(quote)], "container_source_span": source_span,
                "source_anchor": str(candidate.get("source_anchor") or ""),
                "physical_table_id": str(candidate.get("physical_table_id") or ""),
                "physical_row_id": str(candidate.get("physical_row_id") or "")})
        if not any(subject in quote for quote in quotes):
            fail("ungrounded_narrative_subject",
                detail="Keep the fact quote unchanged. Add a separate exact subject-bearing quote to this claim from an allowed body or attached context only if it supports this attribution. "
                    "Do not insert the subject into evidence_text. If the relation is unsupported, revise the claim or abstain; filing metadata alone is not evidence.")
        if number_check(rendered_text, number_sources):
            fail("ungrounded_narrative_claim_number",
                detail="Use only numbers grounded by this claim's exact quotes or their report year, not another claim or an unquoted source tail.")
        readings.append({"claim_index": index, "subject": subject, "text": text, "evidence": evidence,
            **({"rendered_text": rendered_text} if rendered_text != text else {})})
    return readings, errors


def _validate_addressed_claims(binding, candidate_by_id, *, number_check, visible_candidate_ids):
    """Resolve explicit references, preserving subject/fact authority separately."""
    visible = set(candidate_by_id if visible_candidate_ids is None else visible_candidate_ids)
    book = build_narrative_address_book([candidate_by_id[key] for key in visible if key in candidate_by_id])
    selected = set(binding.get("candidate_ids") or [])
    readings, errors = [], []

    def fail(code, location, link=None, *, detail):
        errors.append({"code": code, "location": location, "detail": detail,
            "owner_id": str((link or {}).get("source_requirement_id") or binding.get("obligation_id") or ""),
            "candidate_id": str((link or {}).get("candidate_id") or "")})

    def resolve(links, location):
        evidence = []
        if not links:
            fail("missing_narrative_claim_evidence", location,
                detail="Select at least one permitted source range; missing references never select a whole surface.")
        for index, link in enumerate(links):
            at = f"{location}[{index}]"
            candidate_id = str(link.get("candidate_id") or "")
            if candidate_id not in selected:
                fail("narrative_requirement_candidate_not_selected", at, link, detail="Select only bound candidate IDs.")
                continue
            try:
                surface, quote, span = resolve_narrative_selection(link, book)
            except ValueError as exc:
                fail(str(exc), at, link, detail="Select existing first/last piece IDs in one permitted surface partition; "
                    "do not invent IDs, join cells, normalize source text or widen to unselected text.")
                continue
            candidate = candidate_by_id[candidate_id]
            context_id = surface.source_id if surface.source_field == "source_context" else ""
            context = next((row for row in candidate.get("source_contexts") or []
                if row.get("context_id") == context_id), {}) if context_id else {}
            evidence.append({"candidate_id": candidate_id,
                "source_requirement_id": str(link.get("source_requirement_id") or ""),
                "surface_id": surface.surface_id, "first_piece_id": link["first_piece_id"],
                "last_piece_id": link["last_piece_id"],
                "source_bundle_id": book[candidate_id][0].source_id, "context_id": context_id,
                "source_field": surface.source_field, "evidence_text": quote, "source_span": list(span),
                "container_source_span": list(context.get("source_span") or []) if context_id
                    else list(candidate.get("source_bundle_context_span") or []),
                "source_anchor": str(candidate.get("source_anchor") or ""),
                "physical_table_id": str(candidate.get("physical_table_id") or ""),
                "physical_row_id": str(candidate.get("physical_row_id") or "")})
        return evidence

    used = {row.get("subject_binding_id") for row in binding["claims"]}
    subjects = {}
    for index, subject in enumerate(binding["subject_bindings"]):
        location = f"subject_bindings[{index}]"
        key = subject["subject_binding_id"]
        if key not in used:
            fail("unused_narrative_subject_binding", location,
                detail="Declare subject support only for referenced claims in this output.")
        evidence = resolve(subject.get("evidence_selections") or [], location + ".evidence_selections")
        if not any(subject["subject"] in row["evidence_text"] for row in evidence):
            fail("ungrounded_narrative_subject", location,
                detail="Select source support containing the declared subject. Interpretation of its relation to each fact remains your responsibility.")
        subjects[key] = (subject["subject"], evidence)
    for index, claim in enumerate(binding["claims"]):
        location = f"narrative_claims[{index}]"
        subject, support = subjects[claim["subject_binding_id"]]
        text = claim.get("text")
        if not isinstance(text, str) or not text.strip():
            fail("invalid_narrative_claim", location, detail="Provide a nonblank source-supported statement.")
            continue
        evidence = resolve(claim.get("fact_evidence_selections") or [], location + ".fact_evidence_selections")
        rendered = render_narrative_claim({"subject": subject, "text": text})
        number_sources = [{"source_text": row["evidence_text"],
            "year": candidate_by_id[row["candidate_id"]].get("year")} for row in evidence]
        if number_check(rendered, number_sources):
            fail("ungrounded_narrative_claim_number", location,
                detail="Numbers require this claim's selected fact ranges/report year, not shared subject support or other claims.")
        readings.append({"claim_index": index, "subject_binding_id": claim["subject_binding_id"],
            "subject": subject, "text": text, "evidence": evidence,
            "subject_evidence": [dict(row) for row in support],
            **({"rendered_text": rendered} if rendered != text else {})})
    return readings, errors
