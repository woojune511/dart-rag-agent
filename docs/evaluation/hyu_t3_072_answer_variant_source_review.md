# HYU_T3_072 Answer-Variant Source Review

Date: 2026-09-01

## Scope and evidence boundary

This is a provider-free, read-only review of the real filing evidence behind
`HYU_T3_072`. It decides whether a complete, source-qualified multi-output
answer variant can be proposed without combining incompatible reporting bases.
It does not register `accepted_answer_variants`, edit the canonical answer,
change a tolerance or score, rerun a benchmark, or accept the row.

The original HTML path recorded in the curated row is not present in this
checkout. The reviewed source authority is the canonical parsed Hyundai 2023
store under
`benchmarks/results/policy_gate_regression_2026-06-03_1138_actual`, opened with
SQLite `mode=ro&immutable=1`, plus its `table_payloads.json`. The SQLite SHA-256
before review was
`73b65b54dfdd6d63390a219f67b4d8a8e61b7169be481a3fc1f6c586db31db37`.
Candidate IDs below were reconstructed locally from that immutable metadata and
the current deterministic candidate catalog. They are not provider selections,
new benchmark outputs, or evaluator judgements.

## Required answer surface

The saved requirement plan contains three obligations:

| Obligation | Kind | Required content |
| --- | --- | --- |
| `ob_001` | `direct_value` | Motional ownership share |
| `ob_002` | `direct_value` | Motional investment carrying amount |
| `ob_003` | `narrative` | Motional summary profit/loss information |

A proposed variant is complete only if all three obligations can be answered
from compatible evidence for the same entity, report period, and reporting
basis. Numeric equality alone is not compatibility.

## Source-qualified candidates

### Consolidated current-period tuple

The direct values occur in one Motional row in the consolidated notes:

- evidence/chunk `20240313001451:175:85`;
- section `III. 재무에 관한 사항 > 3. 연결재무제표 주석`;
- table
  `III. 재무에 관한 사항 > 3. 연결재무제표 주석::table:82`;
- payload
  `table_payload:2b3b36260437497eefe6636b79bd2cc1976c597d04b13c4794bb7eec58f85acb`;
- source row candidate `20240313001451:175:85::rowrec:2`;
- row: `Motional AD LLC (*1,5) | 자율주행 소프트웨어 개발 | 미국 | 26% | 700,691`;
- scope `consolidated`, period focus `current`, table unit `백만원`.

| Output | Candidate ID | Source value ID | Raw display | Normalized value |
| --- | --- | --- | --- | --- |
| ownership share | `cand_f8b33c34fa5f2be89451` | `...::table:82:v:2:4` | `26%` | `26 PERCENT` |
| carrying amount | `cand_7c8fe3f9ccf88fd702f8` | `...::table:82:v:2:5` | `700,691백만원` | `700691000000 KRW` |

The compatible summary row is also in the consolidated notes:

- evidence/chunk `20240313001451:183:93`;
- table
  `III. 재무에 관한 사항 > 3. 연결재무제표 주석::table:90`;
- payload
  `table_payload:6a2f3dd21e2a0484683a2eea880f80dcc99d8c1056013c62fd8de05925ca3ddf`;
- scope `consolidated`, period focus `current`, unit `백만원`.

| Measure | Candidate ID | Raw display | Normalized value |
| --- | --- | --- | --- |
| operating revenue | `cand_a92475445e07f5bac0c0` | `1,775` | `1775000000 KRW` |
| continuing-operation loss | `cand_9f778fb44ea42b603c96` | `(803,742)` | `-803742000000 KRW` |
| other comprehensive income | `cand_37a49e64b6e4af4b86f5` | `12,115` | `12115000000 KRW` |
| total comprehensive loss | `cand_00f1ca43f70ccc76ff7b` | `(791,627)` | `-791627000000 KRW` |

These six candidates form one complete, non-mixed tuple. A pure execution probe
with the saved obligations and these IDs returned `ok`, no validation errors,
and a grounded answer containing `26%`, `700,691백만원`, and all four summary
measures. This is a no-call executor projection, not a paid replay or acceptance.

### Separate current-period direct tuple

The separate notes contain a different Motional direct row:

- evidence/chunk `20240313001451:455:70`;
- section `III. 재무에 관한 사항 > 5. 재무제표 주석`;
- table `III. 재무에 관한 사항 > 5. 재무제표 주석::table:69`;
- payload
  `table_payload:9ad952b7bf1ae5599418450be9b7449e61141d9a0d0449790a4b61bddf5a46c1`;
- source row candidate `20240313001451:455:70::rowrec:1`;
- row: `Motional AD LLC (*1,11) | ... | 미국 | 25.81% | 1,294,367`;
- scope `separate`, period focus `current`, table unit `백만원`.

| Output | Candidate ID | Source value ID | Raw display | Normalized value |
| --- | --- | --- | --- | --- |
| ownership share | `cand_f6cf81772743b7a86d29` | `...::table:69:v:1:4` | `25.81%` | `25.81 PERCENT` |
| carrying amount | `cand_1a89d1686b72354c7533` | `...::table:69:v:1:5` | `1,294,367백만원` | `1294367000000 KRW` |

The detailed investment table at `20240313001451:924:9` corroborates the
`25.81` share and `1,294,367` carrying amount and includes a recent-period
profit/loss value of `-803,742`. Its scope and unit metadata are not sufficient
to establish a separate-basis summary tuple, and it does not contain the
`791,627` total comprehensive loss. Within the reviewed immutable store,
`791,627` appears only in the consolidated summary source
`20240313001451:183:93`.

The separate direct pair is therefore source-supported, but a complete
same-basis separate answer variant is not established. Combining it with the
consolidated summary would violate the atomic variant contract.

## Curated-key finding

The current canonical answer combines the separate direct pair
`25.81% / 1,294,367백만원` with consolidated summary losses
`803,742 / 791,627백만원`. Its first evidence description also labels the direct
pair as a consolidated-note value, while the immutable parsed source places that
row in the separate notes. This review records the discrepancy only. Correcting
the canonical key or evidence metadata is a separate dataset-governance
decision.

## Projection blocker observed before repair

The first no-call probe could not represent the complete consolidated tuple
truthfully because the source-to-canonical-operand projection lost three generic
fields:

1. The percentage cell's embedded `%` is normalized to `PERCENT`, but the
   table-wide `백만원` unit remains as its raw unit. The matcher consequently
   reports `output_operand_raw_value_mismatch` for a truthful `26% / %`
   contract; declaring `백만원` instead is rejected by the strict loader.
2. The validator can prove `Motional AD LLC` from the row headers, but the
   canonical operand preserves the row label `미국` as its subject surface.
3. The report year/current-period context is not retained as the operand period.
   The projected periods are metric column labels such as
   `공동기업에 대한 소유지분율` and `공동기업에 대한 투자자산`, with no value year.

A no-call matcher probe confirmed that all truthful answer numbers matched the
proposed consolidated answer text, while trace projection failed before atomic
variant matching for those metadata reasons. Registering a distorted contract
to fit the lossy projection would have weakened the strict source contract and
was not acceptable.

## Generic repair and repeated no-call gate

The projection contract is now repaired without a company, question, metric, or
answer-key branch:

- a recognized unit embedded in the value cell is the effective `raw_unit`,
  while the inherited table hint remains separately traceable;
- parser-footnote-cleaned row headers establish the validated source subject,
  which is carried with source-row provenance rather than inferred from the
  metric label;
- metric column headers remain `source_period_surface`, while an unambiguous
  current-report context projects report year `2023` as `period` and
  `value_year`;
- compile and execution artifacts use one canonical operand projector, and the
  evaluator requires the output to repeat its explicit validated subject.

The same immutable SQLite and `table_payloads.json` were reopened read-only.
All six candidate IDs listed above remained identical. The two direct operands
now project as `26% / %` and `700,691 / 백만원`, both with subject
`Motional AD LLC`, period/value year `2023`, and consolidated scope. The full
three-obligation program returned validation `ready`, execution `ok`, all three
outputs, and no validation errors. An in-memory strict variant named
`hyu_t3_072_consolidated_current` then returned
`atomic_answer_variant_match` with score `1.0` and no projection errors.

This is a provider-free projection/matcher gate, not dataset registration,
benchmark acceptance, or a new provider result. The SQLite, payload, curated
datasets, saved results, and excluded user files remained byte-identical.

## Decision and next seam

- Propose one eventual complete variant, provisionally
  `hyu_t3_072_consolidated_current`, using consolidated share `26%`, carrying
  amount `700,691백만원`, and the four consolidated summary measures above.
- Do not propose or register a complete separate variant from the currently
  reviewed sources.
- Do not edit the curated row in this review.
- The no-call projection gate has passed. Dataset registration and canonical-
  key/evidence correction are now the next separate explicit decision; the
  current key still combines different reporting bases.
- Paid replay, compiler repair, ingest, and Phase 3 remain out of scope.
