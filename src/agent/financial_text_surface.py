"""Text surface helpers used by financial answer composition."""

import re
from typing import List

from src.agent.financial_graph_helpers import _normalise_spaces
from src.config.retrieval_policy import CALCULATION_NARRATIVE_POLICY


def topic_particle(value: str) -> str:
    particles = dict(CALCULATION_NARRATIVE_POLICY.get("topic_particles") or {})
    with_final = str(particles.get("with_final_consonant") or "")
    without_final = str(particles.get("without_final_consonant") or "")
    text = _normalise_spaces(str(value or ""))
    if not text:
        return with_final
    last = text[-1]
    codepoint = ord(last)
    if 0xAC00 <= codepoint <= 0xD7A3:
        return with_final if (codepoint - 0xAC00) % 28 else without_final
    return without_final


def polish_korean_particle_pairs(text: str) -> str:
    surface = _normalise_spaces(str(text or ""))
    if not surface:
        return surface
    conjunctive_with_vowel = chr(0xC640)
    conjunctive_with_final = chr(0xACFC)

    def _replace_final_consonant_wa(match: re.Match[str]) -> str:
        stem = match.group("stem")
        last = stem[-1]
        codepoint = ord(last)
        if 0xAC00 <= codepoint <= 0xD7A3 and (codepoint - 0xAC00) % 28:
            return f"{stem}{conjunctive_with_final}"
        return match.group(0)

    return re.sub(
        rf"(?P<stem>[\uac00-\ud7a3A-Za-z0-9·/&\-\)\]]*[\uac00-\ud7a3]){conjunctive_with_vowel}(?=\s|[,.!?。]|$)",
        _replace_final_consonant_wa,
        surface,
    )


def split_narrative_sentences(text: str) -> List[str]:
    surface = _normalise_spaces(str(text or ""))
    if not surface:
        return []
    surface = re.sub(r"(?<=[.!?。])\s*(?=[\-ㆍ•·*]\s*)", " ", surface)
    surface = re.sub(r"(?<=[.!?。])(?=[\uac00-\ud7a3])", " ", surface)
    return [
        _normalise_spaces(fragment)
        for fragment in re.split(r"(?<=[.!?。])\s+|\n+", surface)
        if _normalise_spaces(fragment)
    ]


def narrative_sentence_looks_table_noisy(sentence: str) -> bool:
    text = _normalise_spaces(str(sentence or ""))
    if not text:
        return True
    pipe_count = text.count("|")
    bullet_count = len(re.findall(r"(?:^|\s)[\-ㆍ•·*]\s*", text))
    bracket_header_count = len(re.findall(r"\[[^\]]+\]", text))
    numeric_count = len(re.findall(r"\d[\d,]*(?:\.\d+)?%?", text))
    if pipe_count >= 3:
        return True
    if bracket_header_count >= 3 and re.search(r"\[[a-z_]+:", text.lower()):
        return True
    if len(text) >= 120 and numeric_count >= 6 and (pipe_count or bullet_count or bracket_header_count):
        return True
    if len(text) >= 180 and numeric_count >= 8:
        return True
    return False


def narrative_sentence_looks_abbreviated_fragment(sentence: str, markers: tuple[str, ...]) -> bool:
    text = _normalise_spaces(str(sentence or ""))
    if not text or any(marker in text for marker in markers):
        return False
    return bool(re.search(r"\b[A-Za-z]{1,4}\.$", text))
