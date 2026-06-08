"""Contract helpers for the REFERENCE_NOTE capability boundary."""

from __future__ import annotations

from typing import Any, Dict


REFERENCE_NOTE_GRAPH_RELATION = "reference_note"
REFERENCE_NOTE_CAPABILITY_STATUS = "graph_expansion_context_only"
REFERENCE_NOTE_OWNER = "researcher_graph_expansion"
REFERENCE_NOTE_ARTIFACT_KIND = "retrieval_bundle"


def reference_note_capability_status() -> Dict[str, Any]:
    """Return the current disabled-serving boundary for REFERENCE_NOTE traversal."""
    return {
        "status": REFERENCE_NOTE_CAPABILITY_STATUS,
        "mode": "context_only",
        "owner": REFERENCE_NOTE_OWNER,
        "graph_relation": REFERENCE_NOTE_GRAPH_RELATION,
        "artifact_kind": REFERENCE_NOTE_ARTIFACT_KIND,
        "retrieval_context_enabled": True,
        "cache_read_source": False,
        "cache_serving_enabled": False,
        "retrieval_bypass_enabled": False,
        "ledger_insertion_enabled": False,
        "final_acceptance_enabled": False,
        "report_cache_origin": "",
        "allowed_surfaces": [
            "graph_expansion.retrieved_docs",
            "retrieval_debug_trace.graph_relation_counts",
            "researcher.retrieval_bundle",
        ],
        "blocked_surfaces": [
            "report_cache_entry.source",
            "report_cache_rehydration.cache_origin",
            "task_artifact_ledger.producer",
            "final_answer.acceptance_authority",
        ],
        "pipeline": [
            "seed_retrieved_docs",
            "structure_graph_reference_parent_ids",
            "graph_relation_reference_note",
            "researcher_retrieval_bundle_context",
            "critic_or_orchestrator_acceptance",
        ],
    }
