"""Question-independent, conservative DART XML caption ownership extraction."""

from collections import Counter, defaultdict
import datetime
import json
import re

from src.processing.table_structure import build_table_object
from src.storage.table_caption_links import CAPTION_LINK_VERSION, node_fingerprint


def _compact(text):
    return re.sub(r"\s+", "", text)


def caption_labels(table):
    if not (1 <= table["row_count"] <= 2 and 1 <= table["column_count"] <= 8):
        return None
    text = _compact(table["table_text"]).replace("|", "")
    parts = list(re.finditer(r"\((기준일|단위):([^()]*)\)", text))
    if not parts or "".join(m.group(0) for m in parts) != text:
        return None
    labels = {}
    for match in parts:
        key, value = match.groups()
        if key in labels or not value or len(value) > 64:
            return None
        if key == "기준일":
            date = re.fullmatch(r"(\d{4})(?:년|[./-])(\d{1,2})(?:월|[./-])(\d{1,2})(?:일|\.)?", value)
            if not date:
                return None
            try:
                datetime.date(*map(int, date.groups()))
            except ValueError:
                return None
        elif not re.fullmatch(r"[가-힣A-Za-z₩$€¥%/.,+-]+", value):
            return None
        labels[key] = value
    return labels


def _body_variants(node):
    body = node["text"].split("\n\n", 1)[-1]
    variants = {_compact(body)}
    heading = node["metadata"].get("local_heading")
    if heading and body.startswith(heading + "\n"):
        variants.add(_compact(body[len(heading):]))
    return variants


def build_report_caption_links(root, document_sha256, receipt, graph, hydrate_metadata):
    """Extract links from an original parsed report and an existing stored graph.

    No mutation, model, question, embedding, source collection or store open.
    Callers must hash the raw bytes from which the canonical XML root was parsed.
    """
    nodes = graph.get("nodes", {})
    report_nodes = [n for n in nodes.values() if n.get("metadata", {}).get("rcept_no") == receipt]
    objects = {t: build_table_object(t) for t in root.iter("TABLE")}
    occurrences = Counter(_compact(o["table_text"]) for o in objects.values())
    by_body = defaultdict(set)
    for node in report_nodes:
        for body in _body_variants(node):
            by_body[body].add(node["chunk_uid"])
    links, dispositions = {}, Counter()
    for element, obj in objects.items():
        if caption_labels(obj) is None:
            continue
        following = element.getnext()
        if following not in objects or (element.tail or "").strip():
            dispositions["not_direct_sibling"] += 1
            continue
        target_obj = objects[following]
        if target_obj["row_count"] < 3 or caption_labels(target_obj) is not None:
            dispositions["not_data_table"] += 1
            continue
        body = _compact(target_obj["table_text"])
        candidates = by_body.get(body, set())
        if len(candidates) != 1 or occurrences[body] != 1:
            dispositions["ambiguous_or_split_target"] += 1
            continue
        uid = next(iter(candidates))
        target = nodes[uid]
        caption = nodes.get(target.get("sibling_prev_uid"))
        if (not caption or not target.get("parent_id")
                or caption.get("parent_id") != target["parent_id"]
                or caption.get("metadata", {}).get("rcept_no") != receipt
                or caption.get("sibling_next_uid") != uid
                or _compact(obj["table_text"]) not in _body_variants(caption)):
            dispositions["missing_or_mixed_predecessor"] += 1
            continue
        valid = True
        for node, raw in ((target, target_obj), (caption, obj)):
            meta = hydrate_metadata(dict(node.get("metadata") or {}))
            try:
                stored = json.loads(meta.get("table_object_json") or "{}")
            except (TypeError, ValueError):
                valid = False
                break
            if (meta.get("chunk_uid") != node.get("chunk_uid")
                    or stored.get("source_document_sha256") != document_sha256
                    or stored.get("source_table_locator") != raw["source_table_locator"]):
                valid = False
                break
        if not valid:
            dispositions["source_binding_mismatch"] += 1
            continue
        links[uid] = dict(table_uid=uid, caption_uid=caption["chunk_uid"], receipt=receipt,
                          parent_id=target["parent_id"], document_sha256=document_sha256,
                          table_locator=target_obj["source_table_locator"],
                          caption_locator=obj["source_table_locator"],
                          table_fingerprint=node_fingerprint(target, hydrate_metadata),
                          caption_fingerprint=node_fingerprint(caption, hydrate_metadata))
        dispositions["linked"] += 1
    return {"version": CAPTION_LINK_VERSION, "links": links, "dispositions": dict(dispositions)}
