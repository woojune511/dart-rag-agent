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
remain; further changes need quality/cost evidence across independent examples.

Validation: 2,255 provider-free tests pass; runtime domain audit covers 66
remaining reviewed literals, with 17 obsolete entries removed and no additions.
Runtime/config shrank by 3,723 lines net. Existing protected files (15,050) and
local settings retain their hashes. Cleanup itself used no paid quality evaluation.

## Remaining work and stopping point

The [development successor](../evaluation/portfolio_workflow_comparison_successor.md)
completed all four exposed question pairs with frozen shared retrieval, one reused
baseline and 11 new calls. Current Planner/Compiler showed no clear answer-quality
advantage at 3.47x estimated cost and 4.79x measured time. The shared exact-cash
retrieval gap, lost year-end meaning and one-decimal display miss remain visible.
This small joint representation/workflow comparison does not decide production
defaults. Freeze added complexity and carry simple RAG as a leading candidate;
retain the current workflow's inspectable source/calculation protections.

1. Freeze a small supported task set and source snapshot: lookup, calculation,
   evidence-backed explanation, and insufficient-evidence handling. Split familiar
   development regressions from a final set that has not guided implementation.
   Previously inspected or repaired questions cannot become untouched holdout.
2. Reuse the implemented simple retrieve-context-answer baseline and comparison
   harness. Keep matched documents, questions, retrieval budgets and semantic model
   settings; record stage count, tokens, latency and cost. Joint representation and
   workflow differences remain a system comparison, not an isolated component gain.
3. No new runtime improvement is selected from these four development cases.
   Keep added complexity only when broader quality/cost evidence justifies it.
   Existing source-integrity defects remain bugs; individual answer misses enter
   failure analysis instead of automatically creating another prompt/schema rule.
4. Run the final set once under a separately bounded run plan. Report answer
   correctness, source support, missing-output/abstention behavior, latency and
   cost separately. Document limitations, publish a reproducible demo/report,
   and close this portfolio milestone. A disappointing result is still reportable;
   it does not restart an indefinite repair loop on the final questions.

The known [year-end interpretation miss](../evaluation/planner_real_questions_result.md)
remains a semantic failure and a development example. It is no longer the automatic
next prompt patch. Historical representative scores and fixture replay are not a
synchronized baseline comparison or new provider acceptance. The successor's single
batch is consumed; it does not authorize another paid run. The separate final set,
demo and report remain outstanding. No store rebuild or historical-result rewrite
is needed to finish this milestone.
