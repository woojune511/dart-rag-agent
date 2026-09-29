"""Build an explicit local caption sidecar without opening or rebuilding Chroma."""

import argparse
import hashlib
from io import BytesIO
import json
from pathlib import Path

from lxml import etree

from src.processing.financial_parser import _sanitize_xml_like_text
from src.processing.table_caption_links import build_report_caption_links
from src.storage.graph_persistence import load_structure_graph
from src.storage.metadata_payloads import load_table_payloads, metadata_with_table_payload
from src.storage.table_caption_links import CAPTION_LINK_VERSION


def build_sidecar(store_dir, reports):
    """reports maps filing IDs to original local XML files; never discovers files."""
    store_dir = Path(store_dir)
    graph = load_structure_graph(store_dir / "document_structure_graph.json")
    payloads = load_table_payloads(store_dir / "table_payloads.json")
    receipts = {n.get("metadata", {}).get("rcept_no") for n in graph["nodes"].values()}
    if (not isinstance(reports, dict) or not reports
            or any(not isinstance(r, str) or not isinstance(p, str) or r not in receipts
                   for r, p in reports.items())):
        raise ValueError("Reports must map existing filing IDs to local XML paths")
    hydrate = lambda m: metadata_with_table_payload(m, payloads)
    links, summaries = {}, []
    for receipt, path in sorted(reports.items()):
        raw = Path(path).read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        sanitized, _ = _sanitize_xml_like_text(raw.decode("utf-8"))
        root = etree.parse(BytesIO(sanitized.encode("utf-8")),
                           etree.XMLParser(recover=True, encoding="utf-8", huge_tree=True)).getroot()
        stored_hashes = set()
        for node in graph["nodes"].values():
            if node.get("metadata", {}).get("rcept_no") != receipt:
                continue
            source = json.loads(hydrate(dict(node["metadata"])).get("table_object_json") or "{}")
            if source.get("source_document_sha256"):
                stored_hashes.add(source["source_document_sha256"])
        if stored_hashes != {digest}:
            raise ValueError("Original report hash does not match stored table provenance")
        result = build_report_caption_links(root, digest, receipt, graph, hydrate)
        links.update(result["links"])
        summaries.append({"receipt": receipt, "document_sha256": digest,
                          "dispositions": result["dispositions"]})
    return {"version": CAPTION_LINK_VERSION, "links": links, "reports": summaries}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--store-dir", type=Path, required=True)
    parser.add_argument("--reports-json", type=Path, required=True,
                        help="JSON object mapping filing IDs to original local XML paths")
    parser.add_argument("--output", type=Path, required=True,
                        help="New sidecar file; refuses to overwrite an existing file")
    args = parser.parse_args(argv)
    if args.output.exists():
        raise FileExistsError(args.output)
    result = build_sidecar(args.store_dir, json.loads(args.reports_json.read_text(encoding="utf-8")))
    encoded = json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
    with args.output.open("x", encoding="utf-8") as stream:
        stream.write(encoded)
    print(f"Saved {len(result['links'])} verified caption links to {args.output}")


if __name__ == "__main__":
    main()
