"""Collect paragraph/table blocks from one DART section element."""

from __future__ import annotations

import json
import time
from typing import Any, Callable, Dict, List, Optional

from src.processing.section_extraction import SECTION_TAGS, SectionParseTimeout
from src.processing.source_context import ancestor_heading_contexts, bounded_source_contexts, heading_scope_key, source_fragment


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
    extract_table_unit_suffix: Callable[[Dict[str, Any]], Optional[str]],
    is_forward_table_caption: Callable[[Dict[str, Any]], bool],
    build_table_context_bundle: Callable[..., Dict[str, Any]],
    extract_paragraph_heading_parts: Callable[..., Any],
    is_single_bracket_heading: Callable[[str], bool],
    classify_bracket_heading: Callable[..., str],
    should_promote_deferred_bracket_heading: Callable[[str, str], bool],
    push_heading: Callable[[List[str], str, str], List[str]],
) -> List[Dict[str, Any]]:
    blocks: List[Dict[str, Any]] = []
    source_elements: Dict[int, Any] = {}
    heading_stack: List[str] = []
    heading_sources: List[Optional[Dict[str, Any]]] = []
    section_contexts = ancestor_heading_contexts(section_elem) + [
        source_fragment(title, "ancestor_heading") for title in section_elem.findall("TITLE")]
    pending_table_heading: Optional[str] = None
    pending_table_heading_source: Optional[Dict[str, Any]] = None
    pending_table_context_hint: Optional[str] = None
    pending_section_label: Optional[tuple[str, Optional[Dict[str, Any]]]] = None
    table_counter = 0
    structured = is_structured_section(section_path) if structured_override is None else structured_override
    section_started_at = time.perf_counter()

    def check_deadline(stage: str) -> None:
        if deadline_monotonic is None:
            return
        now = time.perf_counter()
        if now > deadline_monotonic:
            raise SectionParseTimeout(timeout_label or section_path, stage, now - section_started_at)

    def push_located_heading(heading: str, context: Optional[Dict[str, Any]]) -> None:
        next_stack = push_heading(heading_stack, heading, section_path)
        heading_sources[:] = heading_sources[:len(next_stack) - 1] + [context]
        heading_stack[:] = next_stack

    def enclosing_contexts() -> List[Dict[str, Any]]:
        return bounded_source_contexts(section_contexts + [c for c in heading_sources if c is not None])

    def contextual_table(element: Any) -> Dict[str, Any]:
        table = build_table_object(element)
        excluded = set()
        for neighbor in (element.getprevious(), element.getnext()):
            if neighbor is None or neighbor.tag != "P":
                continue
            leading, parts = extract_paragraph_heading_parts(neighbor, structured=structured)
            headings = [*(leading or []), *(part for part in parts if part["kind"] == "heading")]
            if any(classify_bracket_heading(part["text"], section_path, None,
                       has_body_segments=bool(parts)) != "discard" for part in headings):
                # A mixed/peer heading paragraph is not wholesale adjacency
                # evidence. Its active, located heading is carried separately.
                excluded.add(neighbor.getroottree().getpath(neighbor))
        contexts = enclosing_contexts()
        if pending_table_heading_source is not None:
            contexts.append({**pending_table_heading_source, "relation": "caption"})
        contexts.extend(c for c in table.get("source_contexts", []) if c["source_locator"] not in excluded)
        table["source_contexts"] = bounded_source_contexts(contexts)
        return table

    def emit_block(
        text: str,
        block_type: str,
        local_heading_override: Optional[str] = None,
        extra_metadata: Optional[Dict[str, Any]] = None,
        source_element: Any = None,
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
        contexts = enclosing_contexts()
        if local_heading_override is not None and pending_table_heading_source is not None:
            contexts.append({**pending_table_heading_source, "relation": "caption"})
        if contexts:
            block["source_contexts"] = bounded_source_contexts(contexts)
        if local_heading_override is not None:
            # A table caption labels the table, not a new enclosing section.
            # Keep its enclosing scope for adjacency checks during chunking.
            block["local_heading_scope"] = soft_heading_path(heading_stack)
        blocks.append(block)
        source_elements[id(block)] = source_element

    def process(elem: Any, next_tag: Optional[str] = None) -> None:
        nonlocal pending_table_heading, pending_table_heading_source, pending_table_context_hint, pending_section_label, table_counter
        check_deadline(f"process:{getattr(elem, 'tag', 'unknown')}")
        tag = elem.tag
        if tag in SECTION_TAGS:
            return
        if tag == "TABLE-GROUP":
            for table in elem.findall("TABLE"):
                check_deadline("table-group")
                table_object = contextual_table(table)
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
                        source_element=table,
                        extra_metadata=build_table_context_bundle(
                            text,
                            section_path,
                            table_source_id,
                            local_heading=pending_table_heading,
                            table_object=table_object,
                            context_prefix=pending_table_context_hint,
                        ),
                    )
                    pending_table_context_hint = extract_table_unit_suffix(table_object)
            pending_section_label = None
            return
        if tag == "TABLE":
            check_deadline("table")
            table_object = contextual_table(elem)
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
                    source_element=elem,
                    extra_metadata=build_table_context_bundle(
                        text,
                        section_path,
                        table_source_id,
                        local_heading=pending_table_heading,
                        table_object=table_object,
                        context_prefix=pending_table_context_hint,
                    ),
                )
                pending_table_context_hint = extract_table_unit_suffix(table_object)
            pending_section_label = None
            return
        if tag == "P":
            check_deadline("paragraph:start")
            leading_headings, body_segments = extract_paragraph_heading_parts(
                elem,
                structured=structured,
            )
            def located(part: Dict[str, Any]) -> Optional[Dict[str, Any]]:
                span = part.get("source_span")
                return source_fragment(elem, "intermediate_heading", span) if span is not None else None

            check_deadline("paragraph:parsed")
            heading_only_bracket = (
                leading_headings
                and not body_segments
                and len(leading_headings) == 1
                and is_single_bracket_heading(leading_headings[0]["text"])
            )
            if pending_table_heading is not None and (leading_headings or body_segments):
                pending_table_heading = None
                pending_table_heading_source = None
            if pending_table_context_hint is not None and (leading_headings or body_segments):
                pending_table_context_hint = None
            if leading_headings:
                if heading_only_bracket and next_tag in {"TABLE", "TABLE-GROUP"}:
                    bracket_role = classify_bracket_heading(
                        leading_headings[0]["text"],
                        section_path,
                        next_tag,
                        has_body_segments=False,
                    )
                    if bracket_role == "table_label":
                        pending_table_heading = leading_headings[0]["text"]
                        pending_table_heading_source = located(leading_headings[0])
                else:
                    for part in leading_headings:
                        heading = part["text"]
                        bracket_role = classify_bracket_heading(
                            heading,
                            section_path,
                            next_tag,
                            has_body_segments=bool(body_segments),
                        )
                        if bracket_role == "discard":
                            continue
                        if bracket_role == "defer_section_label":
                            pending_section_label = (heading, located(part))
                            continue
                        if pending_section_label and should_promote_deferred_bracket_heading(
                            heading,
                            section_path,
                        ):
                            push_located_heading(*pending_section_label)
                        pending_section_label = None
                        push_located_heading(heading, located(part))
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
                        pending_section_label = (part["text"], located(part))
                        continue
                    if pending_section_label and should_promote_deferred_bracket_heading(
                        part["text"],
                        section_path,
                    ):
                        push_located_heading(*pending_section_label)
                    pending_section_label = None
                    push_located_heading(part["text"], located(part))
                else:
                    if pending_section_label and not pending_table_heading:
                        pending_section_label = None
                    emit_block(part["text"], "paragraph", source_element=elem)
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

    for prefix, target in zip(blocks, blocks[1:]):
        check_deadline("table-caption")
        if (not is_forward_table_caption(prefix) or target["type"] != "table"
                or not target.get("table_value_records_json")
                or heading_scope_key(prefix) != heading_scope_key(target)
                or prefix.get("local_heading_scope", prefix.get("local_heading"))
                != target.get("local_heading_scope", target.get("local_heading"))):
            continue
        source, table = source_elements[id(prefix)], source_elements[id(target)]
        if (source is None or table is None or source.getparent() is not table.getparent()
                or (source.tail or "").strip()):
            continue
        # Do not turn a fragment of a mixed heading paragraph into a caption.
        if prefix["type"] == "paragraph" and normalize_text("".join(source.itertext())) != prefix["text"]:
            continue
        neighbor = source.getnext()
        while neighbor is not None and neighbor is not table:
            if (neighbor.tail or "").strip():
                break
            if neighbor.tag == "PGBRK" or (neighbor.tag in {"P", "TABLE"}
                    and not normalize_text("".join(neighbor.itertext()))):
                neighbor = neighbor.getnext()
                continue
            unit_table = build_table_object(neighbor) if neighbor.tag == "TABLE" else {}
            hint = extract_standalone_table_context_hint(unit_table)
            unit = extract_table_unit_suffix(unit_table)
            if not hint or not unit or normalize_text(hint.replace("|", " ")) != normalize_text(unit):
                break
            neighbor = neighbor.getnext()
        if neighbor is not table:
            continue
        caption = source_fragment(source, "caption")
        if caption["source_span"][1] != len("".join(source.itertext())):
            continue
        table_object = json.loads(target["table_object_json"])
        existing_contexts = table_object.get("source_contexts", [])
        contexts = bounded_source_contexts([caption, *existing_contexts])
        context_key = lambda c: (c["source_locator"], tuple(c["source_span"]), c["source_text"])
        retained = {context_key(c) for c in contexts}
        if any(context_key(c) not in retained for c in existing_contexts):
            # A caption must not evict existing physical evidence to fit a budget.
            continue
        prefix["table_prefix_target"] = target["table_source_id"]
        target["table_context"] = prefix["text"]
        table_object["source_contexts"] = contexts
        target["table_object_json"] = json.dumps(table_object, ensure_ascii=False)

    return blocks
