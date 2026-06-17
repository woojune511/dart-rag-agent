"""Resolve quoted intra-filing reference hints to section paths."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple


REFERENCE_SIGNAL_RE = re.compile(r"참고|참조")
REFERENCE_QUOTE_CHARS = "\"'“”‘’「」『』"
QUOTED_REFERENCE_PAIR_RE = re.compile(
    rf"[{REFERENCE_QUOTE_CHARS}](?P<left>[^{REFERENCE_QUOTE_CHARS}]+)[{REFERENCE_QUOTE_CHARS}]\s*의\s*"
    rf"[{REFERENCE_QUOTE_CHARS}](?P<right>[^{REFERENCE_QUOTE_CHARS}]+)[{REFERENCE_QUOTE_CHARS}]"
)
QUOTED_REFERENCE_SINGLE_RE = re.compile(
    rf"[{REFERENCE_QUOTE_CHARS}](?P<title>[^{REFERENCE_QUOTE_CHARS}]+)[{REFERENCE_QUOTE_CHARS}]"
    rf"(?:\s*(?:항목|사항|부분))?\s*(?:을|를)?\s*(?:참고|참조)"
)
ROMAN_NUMERAL_NORMALISATION = {
    "Ⅰ": "I",
    "Ⅱ": "II",
    "Ⅲ": "III",
    "Ⅳ": "IV",
    "Ⅴ": "V",
    "Ⅵ": "VI",
    "Ⅶ": "VII",
    "Ⅷ": "VIII",
    "Ⅸ": "IX",
    "Ⅹ": "X",
    "Ⅺ": "XI",
    "Ⅻ": "XII",
}


def normalize_reference_text(text: str) -> str:
    return re.sub(r"[ \t]+", " ", text).strip()


def canonicalize_reference_text(text: str) -> str:
    normalized = normalize_reference_text(text)
    for src, dest in ROMAN_NUMERAL_NORMALISATION.items():
        normalized = normalized.replace(src, dest)
    normalized = normalized.replace("＞", ">").replace("〉", ">")
    normalized = re.sub(r"\s*>\s*", " > ", normalized)
    return normalized


def build_reference_index(raw_sections: List[Dict[str, Any]]) -> Dict[str, Any]:
    entries: List[Dict[str, Any]] = []
    path_map: Dict[str, str] = {}
    title_map: Dict[str, List[str]] = {}

    for section in raw_sections:
        path = str(section.get("path") or "").strip()
        title = str(section.get("title") or "").strip()
        path_titles = [
            str(value).strip()
            for value in section.get("path_titles", [])
            if str(value).strip()
        ]
        if not path or not path_titles:
            continue

        canonical_path = canonicalize_reference_text(path)
        canonical_title = canonicalize_reference_text(title or path_titles[-1])
        entry = {
            "path": path,
            "canonical_path": canonical_path,
            "canonical_title": canonical_title,
            "path_titles": path_titles,
            "canonical_titles": [
                canonicalize_reference_text(value)
                for value in path_titles
            ],
        }
        entries.append(entry)
        path_map[canonical_path] = path
        title_map.setdefault(canonical_title, []).append(path)

    return {"entries": entries, "path_map": path_map, "title_map": title_map}


def resolve_reference_path(
    left: Optional[str],
    right: str,
    reference_index: Dict[str, Any],
) -> Optional[str]:
    entries = list(reference_index.get("entries", []) or [])
    path_map = dict(reference_index.get("path_map", {}) or {})
    title_map = dict(reference_index.get("title_map", {}) or {})

    right_key = canonicalize_reference_text(right)
    if left:
        left_key = canonicalize_reference_text(left)
        exact_path = path_map.get(canonicalize_reference_text(f"{left} > {right}"))
        if exact_path:
            return exact_path

        left_title_matches = title_map.get(left_key, [])
        if len(left_title_matches) == 1:
            candidate_prefix = canonicalize_reference_text(left_title_matches[0])
            for entry in entries:
                if (
                    entry["canonical_path"].startswith(candidate_prefix + " > ")
                    and entry["canonical_titles"][-1] == right_key
                ):
                    return entry["path"]

        for entry in entries:
            titles = list(entry.get("canonical_titles", []) or [])
            if not titles:
                continue
            if titles[0] == left_key and titles[-1] == right_key:
                return entry["path"]
        return None

    exact_path = path_map.get(right_key)
    if exact_path:
        return exact_path

    title_matches = title_map.get(right_key, [])
    if len(title_matches) == 1:
        return title_matches[0]
    return None


def extract_reference_section_paths(
    text: str,
    reference_index: Dict[str, Any],
) -> List[str]:
    normalized = normalize_reference_text(text)
    if not normalized or not REFERENCE_SIGNAL_RE.search(normalized):
        return []

    resolved_paths: List[str] = []
    seen_paths: set[str] = set()
    consumed_spans: List[Tuple[int, int]] = []

    for match in QUOTED_REFERENCE_PAIR_RE.finditer(normalized):
        left = match.group("left")
        right = match.group("right")
        resolved = resolve_reference_path(left, right, reference_index)
        if resolved and resolved not in seen_paths:
            seen_paths.add(resolved)
            resolved_paths.append(resolved)
        consumed_spans.append(match.span())

    masked_text = normalized
    for start, end in reversed(consumed_spans):
        masked_text = masked_text[:start] + (" " * max(0, end - start)) + masked_text[end:]

    for match in QUOTED_REFERENCE_SINGLE_RE.finditer(masked_text):
        title = match.group("title")
        resolved = resolve_reference_path(None, title, reference_index)
        if resolved and resolved not in seen_paths:
            seen_paths.add(resolved)
            resolved_paths.append(resolved)

    return resolved_paths
