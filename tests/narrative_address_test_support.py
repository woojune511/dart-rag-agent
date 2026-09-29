"""Explicit authored fixture migration, never a runtime quote-repair fallback.

Old fixture quotes select the containing display pieces (including original
whitespace). Invalid/foreign quotes get an invalid reference, not fuzzy matching.
Specialized new tests author subject and fact selections independently.
"""

from copy import deepcopy

from src.agent.financial_evidence_addresses import build_narrative_address_book
from src.agent.financial_graph_models import SemanticCalculationProgram


def selection(catalog, candidate_id, quote, *, context_id="", occurrence=0, **metadata):
    surfaces = build_narrative_address_book(catalog).get(candidate_id, ())
    surfaces = [s for s in surfaces if (s.source_id == context_id if context_id
        else s.source_field == "source_bundle")]
    link = {"candidate_id": candidate_id, "source_requirement_id": "", **metadata,
        "surface_id": "invalid_fixture_surface", "first_piece_id": "p1", "last_piece_id": "p1"}
    if not surfaces or not isinstance(quote, str) or not quote.strip():
        return link
    surface = surfaces[0]
    start = -1
    for _ in range(occurrence + 1):
        start = surface.source_text.find(quote, start + 1)
        if start < 0:
            return link
    end = start + len(quote)
    pieces = [p for p in surface.pieces if p.end > start and p.start < end]
    if pieces:
        link.update(surface_id=surface.surface_id,
            first_piece_id=pieces[0].piece_id, last_piece_id=pieces[-1].piece_id)
    return link


def address_program(program, catalog):
    result = deepcopy(program)
    for binding in result.get("narrative_bindings") or []:
        if binding.get("subject_bindings") or not binding.get("claims"):
            continue
        claims = binding["claims"]
        if not isinstance(claims, list) or any(not isinstance(c, dict) or not isinstance(c.get("subject"), str)
                or not isinstance(c.get("evidence_bindings"), list) for c in claims):
            continue  # Keep malformed fixture inputs malformed.
        subjects, addressed = [], []
        for index, claim in enumerate(claims):
            links = [selection(catalog, **{key: value for key, value in link.items() if key != "evidence_text"},
                quote=link.get("evidence_text")) for link in claim["evidence_bindings"]]
            key = f"s{index + 1}"
            subjects.append({"subject_binding_id": key, "subject": claim["subject"], "evidence_selections": deepcopy(links)})
            addressed.append({"subject_binding_id": key, "text": claim["text"], "fact_evidence_selections": links})
        binding.update(subject_bindings=subjects, claims=addressed)
    return result


def model_program(program, catalog):
    return SemanticCalculationProgram.model_validate(address_program(program, catalog))
