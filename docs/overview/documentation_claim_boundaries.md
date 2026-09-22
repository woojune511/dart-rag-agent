# Documentation Claim Boundaries

Current product: scoped document QA through `SimpleRagAgent`. Explain structure
preservation, hybrid retrieval, visible sources, evaluation and measured design
tradeoffs. The [runtime contract](../architecture/agent_runtime_contract.md) owns
application guarantees; [project status](project_status.md) owns current validation.

## Application and historical guarantees

- The default performs one search and at most one answer call. It validates
  response shape, source IDs and explicit caller scope.
- Arithmetic, semantic support and requested-output completeness are not checked
  by the default app. A correct-looking calculation is not code execution.
- Planner/Compiler source binding, deterministic calculations and typed task
  artifacts belong to explicit comparison/replay. Do not transfer those guarantees
  to the default path or call an ID check semantic validation.
- Removed MAS, reflection and result-cache features are historical work. Do not
  advertise them as current or optional product functionality.
- Financial vocabulary is reviewed data, not per-company/question runtime rules.
  The contribution is applied systems engineering, not a new model or SOTA TableQA.

## Evidence classes

| Evidence | What it establishes | Required limitation |
| --- | --- | --- |
| Selected saved application outputs | Inspectable recorded questions, answers and cited sources | Name the source run, after-run selection, distributed fields and omitted raw artifacts; viewing is not a live replay |
| Recorded evaluation | Results for a named revision, corpus, questions and date | Separate assistant review from independent gold; state raw-artifact availability, denominators and failures |
| Historical curated contract fixture | Fixture integrity and internal cross-surface checks | Preserve its `curated_contract_fixture` and unavailable upstream-lineage labels; not current application quality |
| `review_surface_ready` | The historical fixture's reviewer checks pass | Does not run the unit suite/domain audit or establish current app readiness |
| Local validation | Specific commands and checks on an identified checkout or exported tree | Separate data integrity, browser behavior, runtime tests and paid model results |
| Remote CI or deployment | Only the observed run/deployment | A workflow file, local PASS or prepared static demo is not remote CI/deployment success |

The [public demo](../../demo/README.md) contains five after-run selections from the
12-question evaluation. Its displayed 9/9 positive and 2/3 abstention results
belong to the complete panel, not the selected five. Neither panel is an unseen
holdout. Successful abstention and ancillary claim faithfulness are separate.

SHA-256 binds content to a manifest. It does not authenticate the manifest, prove
semantic correctness or attest to provider execution. Where original result hashes
are published without their raw files, independent upstream comparison is unavailable.
The public checker proves only the packaged data/manifest match.

## Review before committing

- Link each behavior to its current owner or contract; mark older walkthroughs
  historical where they describe compiled or removed capabilities.
- Attach metrics to source revision, corpus, date, method and artifact availability.
- Keep success, failure, abstention, ERROR and NOT_RUN denominators visible.
- Preserve original model/source bytes when presenting saved answers; label edits,
  excerpts, selections and reviewer prose separately.
- Describe timings as the measured path: local service calls are not production
  HTTP latency. Token-based cost estimates are not invoices.
- Do not merge the earlier fixed-evidence comparison with the later unpaired
  application run into a new superiority or causal claim.
- A packaged offline demo can be reproducibly viewed without claiming that a fresh
  model call will reproduce its outputs.
