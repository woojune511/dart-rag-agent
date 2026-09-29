"""Source anchors and optional structural expansion for retrieved evidence."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Dict, List

from src.agent.financial_retrieval_pipeline import make_document
from src.agent.financial_runtime_normalization import _normalise_spaces

if TYPE_CHECKING:
    from langchain_core.documents import Document
    from src.agent.financial_graph_state import FinancialAgentState

logger = logging.getLogger(__name__)


class FinancialAgentEvidenceMixin:
    def _expand_via_structure_graph(self, state: FinancialAgentState) -> Dict[str, Any]:
        """Attach nearby structural context to seed retrieval hits.

        The original hits remain the ranking anchors; expansion adds parent
        paragraphs, sibling context, and table descriptions when configured.
        """
        config = dict(self.graph_expansion_config or {})
        if not config.get("enabled"):
            return {}

        seed_docs = list(state.get("retrieved_docs", []) or [])
        if not seed_docs:
            return {}

        include_parent_context = bool(config.get("include_parent_context", True))
        include_section_lead = bool(config.get("include_section_lead", True))
        include_reference_notes = bool(config.get("include_reference_notes", True))
        include_described_by_paragraph = bool(config.get("include_described_by_paragraph", True))
        include_table_context = bool(config.get("include_table_context", True))
        include_sibling_prev = bool(config.get("include_sibling_prev", True))
        include_sibling_next = bool(config.get("include_sibling_next", False))
        table_sibling_prev_paragraph_only = bool(config.get("table_sibling_prev_paragraph_only", True))
        sibling_window = max(0, int(config.get("sibling_window", 1) or 0))
        max_docs = max(self.k, int(config.get("max_docs", self.k) or self.k))

        expanded: List[Any] = []
        seen_keys: set[str] = set()

        def add_doc(doc: Document, score: float, relation: str = "") -> None:
            metadata = dict(doc.metadata or {})
            key = str(metadata.get("chunk_uid") or metadata.get("graph_relation") or relation or doc.page_content[:80])
            relation_key = metadata.get("graph_relation") or relation or "seed"
            dedupe_group = relation_key
            if relation_key in {"seed", "sibling_prev", "sibling_next"}:
                dedupe_group = "chunk"
            dedupe_key = f"{key}::{dedupe_group}"
            if dedupe_key in seen_keys:
                return
            seen_keys.add(dedupe_key)
            expanded.append((doc, score))

        for doc, score in seed_docs:
            metadata = dict(doc.metadata or {})
            parent_id = str(metadata.get("parent_id") or "")
            chunk_uid = str(metadata.get("chunk_uid") or "")
            block_type = str(metadata.get("block_type") or "").strip().lower()
            seed_metadata = dict(metadata)
            if include_parent_context and parent_id:
                seed_metadata["graph_seed_with_parent_context"] = True
            add_doc(make_document(page_content=doc.page_content, metadata=seed_metadata), float(score), relation="seed")

            if include_parent_context and parent_id:
                parent_text = self.vsm.get_parent(parent_id)
                if parent_text:
                    parent_metadata = {
                        **metadata,
                        "graph_relation": "parent_context",
                        "graph_source_chunk_uid": chunk_uid,
                        "block_type": "parent_context",
                        "chunk_uid": f"{chunk_uid}::parent_context" if chunk_uid else f"{parent_id}::parent_context",
                    }
                    add_doc(
                        make_document(page_content=parent_text, metadata=parent_metadata),
                        float(score) - 0.005,
                        "parent_context",
                    )

            if include_section_lead and parent_id:
                section_lead_doc = self.vsm.get_section_lead_doc(parent_id=parent_id, exclude_chunk_uid=chunk_uid)
                if section_lead_doc is not None:
                    add_doc(section_lead_doc, float(score) - 0.006, "section_lead")

            if include_reference_notes and chunk_uid:
                reference_docs = self.vsm.get_reference_docs(chunk_uid=chunk_uid, limit=4)
                for offset, reference_doc in enumerate(reference_docs, start=1):
                    add_doc(reference_doc, float(score) - 0.008 - (offset * 0.001), "reference_note")

            if sibling_window > 0 and parent_id and chunk_uid:
                sibling_docs = self.vsm.get_sibling_docs(parent_id=parent_id, chunk_uid=chunk_uid, window=sibling_window)
                for offset, sibling_doc in enumerate(sibling_docs, start=1):
                    sibling_metadata = dict(sibling_doc.metadata or {})
                    relation = str(sibling_metadata.get("graph_relation") or "sibling").strip()
                    sibling_block_type = str(sibling_metadata.get("block_type") or "").strip().lower()
                    if relation == "sibling_prev" and not include_sibling_prev:
                        continue
                    if relation == "sibling_next" and not include_sibling_next:
                        continue
                    if (
                        block_type == "table"
                        and relation == "sibling_prev"
                        and table_sibling_prev_paragraph_only
                        and sibling_block_type != "paragraph"
                    ):
                        continue
                    add_doc(sibling_doc, float(score) - 0.01 - (offset * 0.001), relation)

            if include_described_by_paragraph and chunk_uid and str(metadata.get("block_type") or "") == "table":
                described_by_doc = self.vsm.get_described_by_doc(chunk_uid=chunk_uid)
                if described_by_doc is not None:
                    add_doc(described_by_doc, float(score) - 0.004, "described_by_paragraph")

            if include_table_context:
                table_context = _normalise_spaces(str(metadata.get("table_context") or ""))
                if table_context:
                    table_metadata = {
                        **metadata,
                        "graph_relation": "table_context",
                        "graph_source_chunk_uid": chunk_uid,
                        "block_type": "table_context",
                        "chunk_uid": f"{chunk_uid}::table_context" if chunk_uid else f"{parent_id}::table_context",
                    }
                    add_doc(
                        make_document(page_content=table_context, metadata=table_metadata),
                        float(score) - 0.007,
                        "table_context",
                    )

        expanded.sort(key=lambda item: item[1], reverse=True)
        expanded = expanded[:max_docs]
        logger.info(
            "[graph_expand] seed=%s expanded=%s parent=%s section_lead=%s reference_note=%s sibling_prev=%s sibling_next=%s sibling_window=%s table_context=%s max_docs=%s",
            len(seed_docs),
            len(expanded),
            include_parent_context,
            include_section_lead,
            include_reference_notes,
            include_sibling_prev,
            include_sibling_next,
            sibling_window,
            include_table_context,
            max_docs,
        )
        return {"retrieved_docs": expanded}

    def _build_source_anchor(self, metadata: Dict[str, Any]) -> str:
        relation = str(metadata.get("graph_relation") or "").strip()
        relation_suffix = f" | {relation}" if relation else ""
        return (
            f"[{metadata.get('company', '?')} | {metadata.get('year', '?')} | "
            f"{metadata.get('section_path', metadata.get('section', '?'))}{relation_suffix}]"
        )
