"""Text surface helpers used by financial answer composition."""

import re
from typing import List

from src.agent.financial_runtime_normalization import _normalise_spaces
from src.config.retrieval_policy import CALCULATION_NARRATIVE_POLICY


def _tokenize_terms(text: str) -> set[str]:
    tokens = re.findall(r"[가-힣A-Za-z0-9]+", text or "")
    return {token.lower() for token in tokens if len(token) >= 2}


def _split_sentences(text: str) -> List[str]:
    cleaned = _normalise_spaces(text)
    if not cleaned:
        return []
    parts = re.split(r"(?<=[.!?])\s+|(?<=다)\s+", cleaned)
    return [part.strip() for part in parts if part.strip()]


def _strip_anchor_text(text: str) -> str:
    cleaned = re.sub(r"\[[^\]]+\]", " ", text or "")
    cleaned = re.sub(r"^[*\-\u2022]+\s*", "", cleaned)
    return _normalise_spaces(cleaned)


def _strip_rerank_metadata(text: str) -> str:
    raw = str(text or "")
    raw = re.sub(r"\[[^\]]+\]", " ", raw)
    raw = re.sub(r"\s+", " ", raw)
    return raw.strip()


def narrative_context_terms(query: str) -> List[str]:
    tokens = re.findall(r"[가-힣A-Za-z0-9()]+", _normalise_spaces(str(query or "")))
    stopwords = {
        str(item)
        for item in (CALCULATION_NARRATIVE_POLICY.get("context_stopwords") or ())
        if str(item)
    }
    terms: List[str] = []
    for token in tokens:
        cleaned = token.strip()
        if len(cleaned) < 2 or cleaned in stopwords:
            continue
        if re.search(r"\d", cleaned):
            continue
        if re.fullmatch(r"\d+", cleaned):
            continue
        terms.append(cleaned)
    return list(dict.fromkeys(terms))


def narrative_focus_variants(query: str) -> List[str]:
    generic_terms = {
        _normalise_spaces(str(item)).lower()
        for item in (
            tuple(CALCULATION_NARRATIVE_POLICY.get("growth_generic_focus_terms") or ())
            + tuple(CALCULATION_NARRATIVE_POLICY.get("context_reuse_excluded_terms") or ())
        )
        if _normalise_spaces(str(item))
    }
    variants: List[str] = []
    for term in narrative_context_terms(query):
        cleaned = _normalise_spaces(str(term))
        if not cleaned or cleaned.lower() in generic_terms:
            continue
        candidates = [cleaned]
        candidates.extend(
            _normalise_spaces(match)
            for match in re.findall(r"\(([^)]+)\)", cleaned)
            if _normalise_spaces(match)
        )
        outside_parentheses = _normalise_spaces(re.sub(r"\([^)]*\)", " ", cleaned))
        if outside_parentheses:
            candidates.append(outside_parentheses)
        for candidate in candidates:
            if len(candidate) < 2:
                continue
            if candidate.lower() in generic_terms:
                continue
            variants.append(candidate)
    return list(dict.fromkeys(variants))


def parenthetical_focus_variants(query: str) -> List[str]:
    variants: List[str] = []
    for term in narrative_context_terms(query):
        cleaned = _normalise_spaces(str(term))
        if not cleaned or "(" not in cleaned:
            continue
        variants.extend(
            _normalise_spaces(match)
            for match in re.findall(r"\(([^)]+)\)", cleaned)
            if _normalise_spaces(match)
        )
        outside_parentheses = _normalise_spaces(re.sub(r"\([^)]*\)", " ", cleaned))
        if outside_parentheses:
            variants.append(outside_parentheses)
    return list(dict.fromkeys(variant for variant in variants if len(variant) >= 2))


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
