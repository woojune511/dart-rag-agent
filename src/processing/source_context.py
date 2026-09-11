"""Located XML text fragments and observed table relations, not scope inference."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from src.processing.table_records import cell_looks_numeric


MAX_CONTEXT_TEXT = 1200
MAX_TABLE_CONTEXT_TEXT = 4800


def source_text_span(text: str, normalized: str, start: int, end: int) -> list[int] | None:
    """Locate a parser-recognized piece using whitespace variation only."""
    pattern = r"[ \t]+".join(re.escape(part) for part in re.split(r"[ \t]+", normalized.strip()))
    if not pattern:
        return None
    match = re.search(pattern, text[start:end])
    return [start + match.start(), start + match.end()] if match else None


def source_fragment(element: Any, relation: str, span: list[int] | None = None) -> dict[str, Any]:
    tree = element.getroottree()
    text = "".join(element.itertext())
    start, end = span if span is not None else (0, len(text))
    end = min(end, start + MAX_CONTEXT_TEXT)
    return {
        "source_locator": tree.getpath(element),
        "parent_locator": tree.getpath(element.getparent()) if element.getparent() is not None else "",
        "source_text": text[start:end], "source_span": [start, end], "relation": relation,
    }


def ancestor_heading_contexts(element: Any) -> list[dict[str, Any]]:
    return [source_fragment(title, "ancestor_heading")
            for ancestor in reversed(list(element.iterancestors())) for title in ancestor.findall("TITLE")]


def bounded_source_contexts(contexts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep one located span per surface, within the existing context budget."""
    result, seen = [], set()
    remaining = MAX_TABLE_CONTEXT_TEXT
    for original in contexts:
        key = (original["source_locator"], tuple(original["source_span"]))
        if key in seen or not original["source_text"].strip() or remaining <= 0:
            continue
        seen.add(key)
        context = dict(original)
        excerpt = context["source_text"][:min(MAX_CONTEXT_TEXT, remaining)]
        context.update(source_text=excerpt, source_span=[context["source_span"][0], context["source_span"][0] + len(excerpt)])
        remaining -= len(excerpt)
        result.append(context)
    return result


def heading_scope_key(block: dict[str, Any]) -> tuple:
    return tuple((c["source_locator"], tuple(c["source_span"])) for c in block.get("source_contexts") or []
                 if c["relation"] in {"ancestor_heading", "intermediate_heading"})


def collect_table_source_contexts(table: Any) -> list[dict[str, Any]]:
    tree = table.getroottree()
    related: list[tuple[Any, str]] = []
    for ancestor in reversed(list(table.iterancestors())):
        for title in ancestor.findall("TITLE"):
            related.append((title, "ancestor_heading"))
    related.extend((caption, "caption") for caption in table.findall("CAPTION"))
    previous = table.getprevious()
    if previous is not None and previous.tag in {"TABLE", "P"}:
        # A neighboring numeric table is a different source, not context.
        numeric_cells = any(cell_looks_numeric("".join(cell.itertext()))
                            for cell in previous.iter() if cell.tag in {"TD", "TH", "TU", "TE"})
        if previous.tag == "P" or not numeric_cells:
            related.append((previous, "preceding_block"))
    following = table.getnext()
    if following is not None and following.tag == "P":
        related.append((following, "following_block"))
    for row in table.findall(".//TR"):
        if any(a.tag in {"THEAD", "TABLE"} and a is not table for a in row.iterancestors()):
            continue
        cells = [cell for cell in row if cell.tag in {"TD", "TH", "TU", "TE"}]
        if cells and not any(cell_looks_numeric("".join(cell.itertext())) for cell in cells):
            related.append((row, "table_text_row"))

    contexts: list[dict[str, Any]] = []
    seen: set[str] = set()
    remaining = MAX_TABLE_CONTEXT_TEXT
    for element, relation in related:
        locator = tree.getpath(element)
        text = "".join(element.itertext())
        if locator in seen or not text.strip() or remaining <= 0:
            continue
        seen.add(locator)
        # Offsets refer to the exact decoded XML text at this locator, not HTML bytes.
        excerpt = text[:min(MAX_CONTEXT_TEXT, remaining)]
        remaining -= len(excerpt)
        contexts.append({
            "source_locator": locator,
            "parent_locator": tree.getpath(element.getparent()) if element.getparent() is not None else "",
            "source_text": excerpt, "source_span": [0, len(excerpt)],
            "relation": relation,
        })
    return contexts


def bind_document_contexts(sections: list[dict[str, Any]], document_sha256: str) -> None:
    """Bind fresh parser blocks to the immutable source file before chunking."""
    def bind(contexts: list[dict[str, Any]]) -> list[dict[str, Any]]:
        bound = []
        for raw in contexts:
            context = {**raw, "document_sha256": document_sha256}
            identity = {key: context[key] for key in (
                "document_sha256", "source_locator", "source_span", "source_text")}
            encoded = json.dumps(identity, ensure_ascii=False, sort_keys=True).encode("utf-8")
            context["context_id"] = "ctx_" + hashlib.sha256(encoded).hexdigest()[:24]
            bound.append(context)
        return bound

    for section in sections:
        for block in section["blocks"]:
            if block.get("source_contexts"):
                block["source_contexts"] = bind(block["source_contexts"])
            raw_table = block.get("table_object_json")
            if not raw_table:
                continue
            table = json.loads(raw_table)
            contexts = table.get("source_contexts") or []
            if not contexts:
                continue
            table["source_document_sha256"] = document_sha256
            table["source_contexts"] = bind(contexts)
            block["table_object_json"] = json.dumps(table, ensure_ascii=False)
