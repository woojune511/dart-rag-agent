# Evidence-ledger Agentic RAG successor

Frozen before dispatch,2026-09-28. The user requested proceeding with preservation
of established evidence/qualifications and ledger-based stopping after the
[first Agentic experiment](agentic_search_result.md).

## Change boundary

Experiment-only controller/evidence-schema seam. Each decision now emits up to six
stable request requirements with covered/partial/missing status, exact source quotes,
factual notes, qualifications and an explicit revision reason. Each requirement has
at most two evidence and two qualification references; all referenced sources must
be visible and among the selected eight. Previous IDs and requirement wording remain;
revising evidence/status/qualifications requires a nonempty reason. The LLM may revise
an earlier interpretation; code does not decide whether that revision is semantically
justified. Unconditional retention of possibly wrong claims is not the contract.

The ledger travels with retained source texts to later decisions and with original
source text to the answer. It is labeled fallible model interpretation. An answer
packet may not retain a ledger assertion after omitting its supporting source. Exact
quote membership, source scope, lifecycle and self-consistency are checked, not truth,
semantic entailment, actual completeness or arithmetic.

Stopping reasons are search, sufficient, no_further_query and budget_exhausted.
Sufficient requires every model-declared requirement to be covered and both
sufficiency flags true. This catches internal contradiction, not missing requirements
or an incorrect covered label. Missing information may still cause a qualified
partial answer; code does not overwrite the answer's abstained flag.

No financial keywords, company-specific runtime rule or gold answer enters this
mechanism. Original question, caller scope, table corpus, vectors, dense16/BM25 top24,
RRF60, at most two extra searches, eight selected sources,65,536-byte answer packet,
model/output limits and answer system prompt/schema remain unchanged. The ledger
changes controller instructions/schema and answer input together; it is one workflow
addition, not an isolated prompt-token ablation. Production remains SimpleRagAgent.

## Run and comparison

Same exposed six cases, frozen before execution: KAK_T3_055, SAM_T3_003, CEL_T3_015,
MIX_T3_023, SKH_T3_080, CEL_T2_039. Prior outputs remain immutable historical controls;
the old arm is not generated afresh. Different queries and single-generation
variation may influence the result. No independent/holdout or causal superiority claim.

Generate an initial ledger-guided answer, then a final answer only if searches occur.
The initial answer is a diagnostic and is never given to the controller. When the
controller stops immediately, share that exact answer. Compare retained/dropped
qualifications, declared requirement coverage, source recovery, answer/citation
support, abstention flags, search count and cost to the saved predecessor. Preserve
the previously disclosed KAK interpretation sensitivity and corpus-omission control.

## Boundaries and checks

- New single-use budget USD15, worst-case reservation USD14.0106: at most18 decisions,
 12 answers and12 query embeddings. No previous authority is reused.
- Same gpt-5.6-terra, low reasoning,8,192 output tokens, store=false, standard tier;
 input/output estimate2.5/12 USD per1M, embedding0.13. Same-day price basis as the
 predecessor; conservative estimates, not observed billing.
- Exact source quotes up to300 characters, notes250, requirement/revision text300;
 model decisions still bounded by the existing200,000 admission limit.
- Before live dispatch: frozen source/artifact hashes, exact initial retrieval replay,
 blocked-network maximum-path42-call rehearsal and provider/ledger stopping controls.
- Malformed schema, unknown/unselected source, fabricated quote, unexplained revision,
 disappearing requirement, contradictory stopping state, HTTP failure, missing usage,
 incomplete output or budget exhaustion stops the batch. No repair, retry or resume.
 Unexecuted cases remain NOT_RUN. Compact20-second heartbeat.
- Existing corpus/store/vector and sealed experimental artifacts stay unchanged.
 No source runtime adoption or full77 rerun. Local ignored successor artifacts live in
 `benchmarks/results/agentic_ledger_2026-09-28/`; build.py constructs a successor from
 the frozen predecessor without editing it.
