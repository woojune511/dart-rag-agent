"""Lossless source addresses; neither semantic segmentation nor evidence selection."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re
from typing import Any, Mapping, Sequence

from src.agent.financial_source_bundles import build_semantic_source_bundles


_BOUNDARY = re.compile(r'''(?:[.!?。！？]["'”’)\]]*(?=\s|$)\s*|[\r\n]+\s*)''')
MAX_PIECE_CHARACTERS = 160


@dataclass(frozen=True, slots=True)
class EvidencePieceV1:
    piece_id: str
    start: int
    end: int
    partition: int


@dataclass(frozen=True, slots=True)
class EvidenceSurfaceV1:
    surface_id: str
    source_id: str
    source_field: str
    source_text: str
    pieces: tuple[EvidencePieceV1, ...]

    def to_projection(self) -> dict[str, Any]:
        # Text appears once. Piece labels are addresses, never inserted source bytes.
        return {"surface_id": self.surface_id, "pieces": [
            {"piece_id": p.piece_id, "partition": p.partition,
             "text": self.source_text[p.start:p.end]} for p in self.pieces]}

    def resolve(self, first_piece_id: str, last_piece_id: str) -> tuple[str, tuple[int, int]]:
        index = {p.piece_id: n for n, p in enumerate(self.pieces)}
        if first_piece_id not in index or last_piece_id not in index:
            raise ValueError("unknown_narrative_piece")
        first, last = index[first_piece_id], index[last_piece_id]
        if first > last:
            raise ValueError("reversed_narrative_selection")
        start, end = self.pieces[first], self.pieces[last]
        if start.partition != end.partition:
            raise ValueError("cross_partition_narrative_selection")
        text = self.source_text[start.start:end.end]
        if not text.strip():
            raise ValueError("empty_narrative_selection")
        return text, (start.start, end.end)


def build_evidence_surface(source: Mapping[str, Any], *, context: bool = False) -> EvidenceSurfaceV1:
    """Bind exact contents/provenance but exclude visible-member/attachment unions."""
    source_id = str(source.get("context_id" if context else "source_bundle_id") or "")
    field = "source_context" if context else "source_bundle"
    text = str(source.get("source_text") or "")
    identity = {key: value for key, value in source.items() if key not in {
        "candidate_ids", "value_spans_by_candidate_id", "context_ids", "context_relations", "relation"}}
    digest = hashlib.sha256(json.dumps([field, identity], ensure_ascii=False,
        sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    segments = source.get("source_segments") or [{"text_span": [0, len(text)]}]
    partitions = sorted(tuple(row["text_span"]) for row in segments)
    pieces: list[EvidencePieceV1] = []
    previous = 0
    for partition, (start, end) in enumerate(partitions):
        if (type(start) is not int or type(end) is not int
                or not 0 <= previous <= start <= end <= len(text)):
            raise ValueError("invalid_narrative_source_partition")
        previous = end
        cursor = start
        boundaries = [start + m.end() for m in _BOUNDARY.finditer(text[start:end])] + [end]
        for boundary in boundaries:
            while cursor < boundary:
                stop = min(boundary, cursor + MAX_PIECE_CHARACTERS)
                if stop < boundary:
                    spaces = [m.end() for m in re.finditer(r"\s+", text[cursor:stop])]
                    if spaces:
                        stop = cursor + spaces[-1]
                pieces.append(EvidencePieceV1(f"p{len(pieces) + 1}", cursor, stop, partition))
                cursor = stop
    return EvidenceSurfaceV1(f"sur_{digest[:20]}", source_id, field, text, tuple(pieces))


def build_narrative_address_book(
    catalog: Sequence[Mapping[str, Any]],
) -> dict[str, tuple[EvidenceSurfaceV1, ...]]:
    """Only passed visible candidates and their own attached contexts are addressable."""
    bodies = {key: build_evidence_surface(bundle.to_projection())
        for bundle in build_semantic_source_bundles(catalog) for key in bundle.candidate_ids}
    return {str(row["candidate_id"]): (bodies[str(row["candidate_id"])], *sorted(
        (build_evidence_surface(context, context=True) for context in row.get("source_contexts") or []),
        key=lambda surface: surface.surface_id))
        for row in sorted(catalog, key=lambda row: str(row["candidate_id"]))}


def resolve_narrative_selection(
    selection: Mapping[str, Any], book: Mapping[str, Sequence[EvidenceSurfaceV1]],
) -> tuple[EvidenceSurfaceV1, str, tuple[int, int]]:
    surfaces = [surface for surface in book.get(str(selection.get("candidate_id") or ""), ())
        if surface.surface_id == selection.get("surface_id")]
    if not surfaces:
        raise ValueError("unknown_narrative_surface")
    surface = surfaces[0]
    text, span = surface.resolve(str(selection.get("first_piece_id") or ""),
        str(selection.get("last_piece_id") or ""))
    return surface, text, span
