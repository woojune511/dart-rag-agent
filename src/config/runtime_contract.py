"""
Project-wide runtime defaults and trace field names.

These constants are the code-level counterpart of AGENTS.md and
docs/architecture/agent_runtime_contract.md. Benchmark-specific variants
should override them through explicit profiles, not ad hoc runtime branches.
"""

CANONICAL_INGEST_PROFILE_ID = "structural_selective_v2_prefix_2500_320"
CANONICAL_INGEST_MODE = "structural_selective_v2"
CANONICAL_CHUNK_SIZE = 2500
CANONICAL_CHUNK_OVERLAP = 320

CANONICAL_EMBEDDING_PROVIDER = "openai"
CANONICAL_EMBEDDING_MODEL = "text-embedding-3-large"
CANONICAL_EMBEDDING_DIMENSION = 3072

RETRIEVAL_DEBUG_TRACE_FIELD = "retrieval_debug_trace"
PLANNER_DEBUG_TRACE_FIELD = "planner_debug_trace"
CALCULATION_DEBUG_TRACE_FIELD = "calculation_debug_trace"
SUBTASK_DEBUG_TRACE_FIELD = "subtask_debug_trace"
