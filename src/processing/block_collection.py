"""Collect paragraph/table blocks from one DART section element."""

from __future__ import annotations

import time
from typing import Any, Callable, Dict, List, Optional

from src.processing.section_extraction import SECTION_TAGS, SectionParseTimeout


def collect_blocks(
    section_elem: Any,
    section_path: str,
    *,
    structured_override: Optional[bool] = None,
    deadline_monotonic: Optional[float] = None,
    timeout_label: Optional[str] = None,
    is_structured_section: Callable[[str], bool],
    normalize_text: Callable[[str], str],
    soft_heading_path: Callable[[List[str]], Optional[str]],
    build_table_object: Callable[[Any], Dict[str, Any]],
    extract_standalone_table_context_hint: Callable[[Dict[str, Any]], Optional[str]],
    build_table_context_bundle: Callable[..., Dict[str, Any]],
    extract_paragraph_heading_parts: Callable[..., Any],
    is_single_bracket_heading: Callable[[str], bool],
    classify_bracket_heading: Callable[..., str],
    should_promote_deferred_bracket_heading: Callable[[str, str], bool],
    push_heading: Callable[[List[str], str, str], List[str]],
) -> List[Dict[str, Any]]:
    blocks: List[Dict[str, Any]] = []
    heading_stack: List[str] = []
    pending_table_heading: Optional[str] = None
    pending_table_context_hint: Optional[str] = None
    pending_section_label: Optional[str] = None
    table_counter = 0
    structured = is_structured_section(section_path) if structured_override is None else structured_override
    section_started_at = time.perf_counter()

    def check_deadline(stage: str) -> None:
        if deadline_monotonic is None:
            return
        now = time.perf_counter()
        if now > deadline_monotonic:
            raise SectionParseTimeout(timeout_label or section_path, stage, now - section_started_at)

    def emit_block(
        text: str,
        block_type: str,
        local_heading_override: Optional[str] = None,
        extra_metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        normalized = normalize_text(text)
        if not normalized:
            return
        block: Dict[str, Any] = {
            "text": normalized,
            "type": block_type,
            "local_heading": local_heading_override
            if local_heading_override is not None
            else soft_heading_path(heading_stack),
        }
        if extra_metadata:
            block.update(extra_metadata)
        blocks.append(block)

    def process(elem: Any, next_tag: Optional[str] = None) -> None:
        nonlocal pending_table_heading, pending_table_context_hint, pending_section_label, table_counter
        check_deadline(f"process:{getattr(elem, 'tag', 'unknown')}")
        tag = elem.tag
        if tag in SECTION_TAGS:
            return
        if tag == "TABLE-GROUP":
            for table in elem.findall("TABLE"):
                check_deadline("table-group")
                table_object = build_table_object(table)
                context_hint = extract_standalone_table_context_hint(table_object)
                if context_hint:
                    pending_table_context_hint = context_hint
                    continue
                text = table_object["table_text"]
                if text:
                    table_counter += 1
                    table_source_id = f"{section_path}::table:{table_counter}"
                    emit_block(
                        text,
                        "table",
                        local_heading_override=pending_table_heading,
                        extra_metadata=build_table_context_bundle(
                            text,
                            section_path,
                            table_source_id,
                            local_heading=pending_table_heading,
                            table_object=table_object,
                            context_prefix=pending_table_context_hint,
                        ),
                    )
                    pending_table_context_hint = None
            pending_section_label = None
            return
        if tag == "TABLE":
            check_deadline("table")
            table_object = build_table_object(elem)
            context_hint = extract_standalone_table_context_hint(table_object)
            if context_hint:
                pending_table_context_hint = context_hint
                return
            text = table_object["table_text"]
            if text:
                table_counter += 1
                table_source_id = f"{section_path}::table:{table_counter}"
                emit_block(
                    text,
                    "table",
                    local_heading_override=pending_table_heading,
                    extra_metadata=build_table_context_bundle(
                        text,
                        section_path,
                        table_source_id,
                        local_heading=pending_table_heading,
                        table_object=table_object,
                        context_prefix=pending_table_context_hint,
                    ),
                )
                pending_table_context_hint = None
            pending_section_label = None
            return
        if tag == "P":
            check_deadline("paragraph:start")
            leading_headings, body_segments = extract_paragraph_heading_parts(
                elem,
                structured=structured,
            )
            check_deadline("paragraph:parsed")
            heading_only_bracket = (
                leading_headings
                and not body_segments
                and len(leading_headings) == 1
                and is_single_bracket_heading(leading_headings[0])
            )
            if pending_table_heading is not None and (leading_headings or body_segments):
                pending_table_heading = None
            if pending_table_context_hint is not None and (leading_headings or body_segments):
                pending_table_context_hint = None
            if leading_headings:
                if heading_only_bracket and next_tag in {"TABLE", "TABLE-GROUP"}:
                    bracket_role = classify_bracket_heading(
                        leading_headings[0],
                        section_path,
                        next_tag,
                        has_body_segments=False,
                    )
                    if bracket_role == "table_label":
                        pending_table_heading = leading_headings[0]
                else:
                    for heading in leading_headings:
                        bracket_role = classify_bracket_heading(
                            heading,
                            section_path,
                            next_tag,
                            has_body_segments=bool(body_segments),
                        )
                        if bracket_role == "discard":
                            continue
                        if bracket_role == "defer_section_label":
                            pending_section_label = heading
                            continue
                        if pending_section_label and should_promote_deferred_bracket_heading(
                            heading,
                            section_path,
                        ):
                            heading_stack[:] = push_heading(
                                heading_stack,
                                pending_section_label,
                                section_path,
                            )
                        pending_section_label = None
                        heading_stack[:] = push_heading(heading_stack, heading, section_path)
            for part in body_segments:
                if part["kind"] == "heading":
                    bracket_role = classify_bracket_heading(
                        part["text"],
                        section_path,
                        next_tag=None,
                        has_body_segments=True,
                    )
                    if bracket_role == "discard":
                        continue
                    if bracket_role == "defer_section_label":
                        pending_section_label = part["text"]
                        continue
                    if pending_section_label and should_promote_deferred_bracket_heading(
                        part["text"],
                        section_path,
                    ):
                        heading_stack[:] = push_heading(
                            heading_stack,
                            pending_section_label,
                            section_path,
                        )
                    pending_section_label = None
                    heading_stack[:] = push_heading(heading_stack, part["text"], section_path)
                else:
                    if pending_section_label and not pending_table_heading:
                        pending_section_label = None
                    emit_block(part["text"], "paragraph")
            return
        child_nodes = list(elem)
        for child_idx, child in enumerate(child_nodes):
            check_deadline("children")
            child_next_tag = child_nodes[child_idx + 1].tag if child_idx + 1 < len(child_nodes) else None
            process(child, next_tag=child_next_tag)

    children = list(section_elem)
    for idx, child in enumerate(children):
        next_tag = children[idx + 1].tag if idx + 1 < len(children) else None
        process(child, next_tag=next_tag)

    return blocks
