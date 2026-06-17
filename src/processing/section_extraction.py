"""Section iteration and parse fallback orchestration for DART XML filings."""

from __future__ import annotations

import time
from typing import Any, Callable, Dict, List


SECTION_TAGS = frozenset({"SECTION-1", "SECTION-2", "SECTION-3"})


class SectionParseTimeout(RuntimeError):
    def __init__(self, section_path: str, stage: str, elapsed_sec: float):
        super().__init__(
            f"Section parse budget exceeded [{section_path}] stage={stage} elapsed={elapsed_sec:.3f}s"
        )
        self.section_path = section_path
        self.stage = stage
        self.elapsed_sec = elapsed_sec


def build_section_path(
    section_elem: Any,
    title_text: str,
    *,
    normalize_text: Callable[[str], str],
    sanitize_path_titles: Callable[[List[str]], List[str]],
) -> List[str]:
    path_titles: List[str] = []
    ancestors = list(section_elem.iterancestors())
    for ancestor in reversed(ancestors):
        if ancestor.tag not in SECTION_TAGS:
            continue
        title_elem = next(
            (child for child in ancestor if child.tag == "TITLE" and child.get("ATOC") == "Y"),
            None,
        )
        if title_elem is None:
            continue
        ancestor_title = normalize_text("".join(title_elem.itertext()))
        if ancestor_title:
            path_titles.append(ancestor_title)
    path_titles.append(title_text)
    return sanitize_path_titles(path_titles)


def extract_sections(
    root: Any,
    *,
    normalize_text: Callable[[str], str],
    sanitize_path_titles: Callable[[List[str]], List[str]],
    is_structured_section: Callable[[str], bool],
    collect_blocks: Callable[..., List[Dict[str, Any]]],
    section_warn_sec: float,
    section_parse_budget_sec: float,
    logger: Any,
) -> List[Dict[str, Any]]:
    sections: List[Dict[str, Any]] = []

    for section in root.iter():
        if section.tag not in SECTION_TAGS:
            continue

        title_elem = next(
            (child for child in section if child.tag == "TITLE" and child.get("ATOC") == "Y"),
            None,
        )
        if title_elem is None:
            continue

        title_text = normalize_text("".join(title_elem.itertext()))
        if not title_text:
            continue

        path_titles = build_section_path(
            section,
            title_text,
            normalize_text=normalize_text,
            sanitize_path_titles=sanitize_path_titles,
        )
        section_path = " > ".join(path_titles)
        section_started_at = time.perf_counter()
        fallback_used = False
        parse_mode = "structured" if is_structured_section(section_path) else "plain"
        deadline_monotonic = None
        if section_parse_budget_sec > 0:
            deadline_monotonic = section_started_at + section_parse_budget_sec
        try:
            blocks = collect_blocks(
                section,
                section_path,
                deadline_monotonic=deadline_monotonic,
                timeout_label=section_path,
            )
        except SectionParseTimeout as exc:
            fallback_used = True
            logger.warning(
                "Section parse budget exceeded; retrying with plain fallback [%s] stage=%s elapsed=%.3fs",
                section_path,
                exc.stage,
                exc.elapsed_sec,
            )
            blocks = collect_blocks(section, section_path, structured_override=False)
            parse_mode = "plain_fallback"
        section_elapsed_sec = time.perf_counter() - section_started_at
        if section_elapsed_sec >= section_warn_sec:
            logger.info(
                "Section parse timing [%s] mode=%s blocks=%s elapsed=%.3fs",
                section_path,
                parse_mode,
                len(blocks),
                section_elapsed_sec,
            )
        if not blocks:
            continue
        sections.append(
            {
                "title": title_text,
                "path_titles": path_titles,
                "path": section_path,
                "blocks": blocks,
                "parse_mode": parse_mode,
                "parse_sec": section_elapsed_sec,
                "fallback_used": fallback_used,
            }
        )

    return sections
