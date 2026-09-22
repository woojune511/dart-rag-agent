# Portfolio scope and completion

Decision: 2026-09-22. DART remains the working domain. The project demonstrates
document retrieval, evidence-grounded tool use, deterministic calculation, and
inspectable failures. Exhaustive financial-question coverage is outside the
completion target.

## What stays in the product

- Preserve document structure and source identity during ingest.
- Retrieve relevant text and tables with visible query/source traces.
- Use the Planner and Compiler to interpret requests and select evidence.
- Execute calculations and validate source links, units and output coverage in code.
- Return supported answers with citations, or expose missing/ambiguous evidence.

Domain vocabulary in ontology or policy still needs a general retrieval purpose.
Moving a question-specific exception from code into configuration does not make
it general. New fields, prompt rules and validation branches need an explanation
across multiple independent examples and a measured benefit to the chosen scope.
Existing source and arithmetic protections remain required.

## Cleanup implemented

The public Planner already sent every intent, including narratives and failed
plans, through required-output compilation. The obsolete alternative still
carried topic-specific behavior and an independently wired graph branch.
Removed together:

- The extraction/compression/validation answer branch and its graph state.
- Dividend-policy supplementation and hybrid answer assembly, entity-table
  summaries, driver appending and sentence-repair helpers in that branch.
- The alternative narrative document selector and its special ranking bonuses.
- Dedicated prompts, structured-output models, policy dictionaries and private
  helper tests with no surviving production caller.

Retrieval now selects distinct authorized sources using the shared format quotas.
Narrative claims continue through the existing Compiler and source validator.
Structure expansion, source anchors, period/scope checks, arithmetic and coverage
checks remain. This deletion establishes a smaller runtime; it does not establish
better model accuracy. Active ontology/policy priors and Compiler constraints
still need the comparison below, rather than wholesale removal without evidence.

Validation: 2,255 provider-free tests pass; runtime domain audit covers 66
remaining reviewed literals, with 17 obsolete entries removed and no additions.
Runtime/config shrank by 3,723 lines net. Existing protected files (15,050) and
local settings retain their hashes. No paid calls or live quality evaluation.

## Remaining work and stopping point

The [development comparison](../evaluation/portfolio_workflow_comparison_result.md)
has four exposed questions and frozen shared retrieval. Its first paid attempt
was interrupted by an output-persistence defect, now fixed offline; zero pairs
completed. The comparison result and separate final set remain outstanding.

1. Freeze a small supported task set and source snapshot: lookup, calculation,
   evidence-backed explanation, and insufficient-evidence handling. Split familiar
   development regressions from a final set that has not guided implementation.
   Previously inspected or repaired questions cannot become untouched holdout.
2. Build a simple retrieve-context-answer baseline. Compare it with this runtime
   on the same documents, index, questions and semantic model/settings. Freeze
   retrieval budgets and record stage count, tokens, latency and cost. Differences
   in workflow are a system comparison, not proof that one component caused a gain.
   The older `RAGAgent` uses paper citations and a fixed Gemini model; it is not a
   ready DART baseline without matching source formatting and model settings.
3. Select at most one broadly useful improvement from that development comparison.
   Keep added complexity only when the quality/cost evidence justifies it. Existing
   source-integrity defects remain bugs; individual answer misses enter failure
   analysis instead of automatically creating another prompt/schema rule.
4. Run the final set once under a separately bounded run plan. Report answer
   correctness, source support, missing-output/abstention behavior, latency and
   cost separately. Document limitations, publish a reproducible demo/report,
   and close this portfolio milestone. A disappointing result is still reportable;
   it does not restart an indefinite repair loop on the final questions.

The known [year-end interpretation miss](../evaluation/planner_real_questions_result.md)
remains a semantic failure and a development example. It is no longer the automatic
next prompt patch. Historical representative scores and fixture replay are not a
synchronized baseline comparison or new provider acceptance. No new paid run,
funding increase, store rebuild or historical-result rewrite is part of this cleanup.
