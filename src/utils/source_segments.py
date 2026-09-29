"""Exact text partitions: offsets are local to the retained source surface."""

from typing import Any, Mapping, Sequence


def slice_source_segments(segments: Sequence[Mapping[str, Any]], start: int, end: int) -> list[dict[str, Any]]:
    return [{**segment, 'text_span': [max(start, a) - start, min(end, b) - start]}
            for segment in segments for a, b in [segment['text_span']]
            if (a < end and b > start) or (a == b and start <= a < end)]


def source_quote_is_contiguous(text: str, quote: str, segments: Sequence[Mapping[str, Any]] = ()) -> bool:
    """A quote may not bridge independently located cells or intervening markup."""
    return quote in text and (not segments or any(quote in text[slice(*segment['text_span'])]
                                                for segment in segments))


def project_source_surface(text: str, segments: Sequence[Mapping[str, Any]] = ()) -> dict[str, Any]:
    if not segments:
        return {'source_text': text}
    return {'source_segments': [{**segment, 'source_text': text[slice(*segment['text_span'])]}
                                for segment in segments],
            'quote_rule': 'Each segment is an independent exact quote surface; use separate evidence bindings across cells.'}
