"""Claim-local quote/subject provenance checks, not semantic entailment judging."""

from typing import Any, Callable, Mapping, Sequence

from src.agent.financial_program_projection import render_narrative_claim
from src.agent.financial_source_bundles import build_semantic_source_bundles


def validate_narrative_claims(
    binding: Mapping[str, Any], candidate_by_id: Mapping[str, Mapping[str, Any]], *,
    number_check: Callable[[str, Sequence[Mapping[str, Any]]], list[str]],
    visible_candidate_ids: Sequence[str] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    claims = binding.get("claims") or []
    if not claims:
        return [], []
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
            source_span = list(candidate.get("source_bundle_context_span") or [])
            if context_id:
                contexts = [row for row in candidate.get("source_contexts") or []
                    if row.get("context_id") == context_id]
                if len(contexts) != 1:
                    fail("invalid_narrative_claim_context", link,
                        detail="Use a context_id attached to this candidate, or leave it empty to quote its source bundle.")
                    continue
                surface = str(contexts[0].get("source_text") or "")
                source_field = "source_context"
                source_span = list(contexts[0].get("source_span") or [])
            if not isinstance(quote, str) or not quote.strip() or quote not in surface:
                fail("invalid_narrative_claim_quote", link,
                    detail="Copy evidence_text verbatim as one continuous excerpt from this candidate's visible bundle or named attached context; do not paraphrase the quote.")
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
                detail="Copy subject verbatim from at least one valid quote attached to this claim; filing metadata alone is not evidence.")
        if number_check(rendered_text, number_sources):
            fail("ungrounded_narrative_claim_number",
                detail="Use only numbers grounded by this claim's exact quotes or their report year, not another claim or an unquoted source tail.")
        readings.append({"claim_index": index, "subject": subject, "text": text, "evidence": evidence,
            **({"rendered_text": rendered_text} if rendered_text != text else {})})
    return readings, errors
