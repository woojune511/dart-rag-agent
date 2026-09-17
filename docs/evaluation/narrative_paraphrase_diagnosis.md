# Narrative paraphrase fidelity: provider-free diagnosis

Base `15db6a39`, 2026-09-18. The concern in the
[fresh search/display answer](search_display_current_app.md) originates in the
sampled Compiler response. Lowering, execution and public presentation preserve
that text; they do not introduce the extra interpretation. This is a Compiler
meaning/claim-fidelity concern, with no observed retrieval, source-address,
parser or final-answer assembly defect.

The [diagnostic packet](../../benchmarks/results/narrative_paraphrase_diagnosis_2026-09-18/)
contains frozen anonymous controls, unchanged-response rehearsals and an
**unadopted** [policy diff](../../benchmarks/results/narrative_paraphrase_diagnosis_2026-09-18/proposed_policy.patch).
No production source, configuration, model setting, store or historical answer changed.
Provider/count/embedding calls and additional cost are **0**; shared accounting
stays **7.69277754 / 8**, remainder **0.30722246**, pending 0.

## Observed boundary

The source separately describes product improvement and category expansion.
The sampled answer first preserves both, then adds a sentence that can apply
expansion to both products and categories. The earlier conservative semantic
qualification remains; this diagnosis does not retroactively pass the live answer.

The exact raw response reconstructs the saved accepted program and execution
outputs without repair. Current instruction text and input values match the paid
request. Embedded JSON object key order differs because saved public JSON sorts
keys; prompt bytes are therefore **not identical**. Applying the existing production
`strict_openai_schema` projection reproduces the paid response schema exactly.
The initial harness incorrectly required byte equality and compared unprojected
Pydantic schema; its partial receipts remain, and the corrected run is separate.

Model-visible instructions are in the user message, not a separate system or
`instructions` field. They already require source-local subjects, claim-local
numeric support, bounded scope, group/member distinctions and direct causal support.
They do not explicitly describe preserving different action/object pairings in
every summary or explanatory clause. The internal model's “do not broaden its
scope” description is absent from the dynamic wire `Claim_*.text` fields, which
carry a nonempty-string constraint. This is an observed schema/instruction
boundary, **not proof that the omission caused the sampled wording**.

## Anonymous controls

Eight source pairs were fixed before the rehearsal; each has an authored faithful
and unsupported statement. Labels are assistant semantic review, not human gold
or newly sampled model answers.

| Contrast | Faithful form retained | Unsupported change |
| --- | --- | --- |
| Different actions, English | Repair panels; extend walkways | Extend both |
| Different actions, Korean | Maintain equipment; expand warehouse | Expand both |
| Action/object pairing | Shorten labels; lengthen windows | Swap the actions |
| Supported shared action | Expand both when both clauses say expand | Substitute repair |
| Conditional intention | Preserve the plan and condition | Assert completion |
| Negation | Preserve the negative meaning | Assert the positive |
| Quantified scope | Preserve “some” through rewording | Assert “all” |
| Additional explanation | Faithful two-sentence restatement | Add a universal causal guarantee |

All **16/16** addressed variants validate and execute: eight faithful and eight
semantically unsupported. That is the expected structural boundary, **not 16/16
answer accuracy**. Three controls with an unlinked surface, hidden source or
unsupported number are rejected. Valid paraphrases, supported coordination and
multiple faithful sentences show why a word blacklist, mandatory quotation or
one-sentence limit would be the wrong repair.

## Reviewable proposal and limits

Add one generic instruction to
`src/config/retrieval_policy.py::_COMPILER_NARRATIVE_INSTRUCTIONS`:

> 각 claim의 모든 문장·절은 선택한 fact evidence가 뒷받침해야 합니다. 요약·비교·부연에서도 주체별 행위와 대상, 조건·정도·부정·시제를 유지하세요. 서로 다른 행위를 하나로 묶어 다른 대상에 적용하지 마세요. 원문 표현을 그대로 반복할 필요는 없지만, 요청 충족에 불필요한 재진술로 새 의미를 더하지 마세요.

The draft adds **418 UTF-8 bytes**, not a measured token estimate, to both existing
general and narrative-only templates. No case names, financial vocabulary, examples,
new schema fields, validators, response rewriting or additional calls are proposed.
It preserves paraphrasing and leaves meaning with the existing Compiler call.

The candidate was substituted only in memory with sockets blocked. Two saved-response
replays plus the 16 anonymous variants under each instruction produce **34 fixed-response
adapter invocations**. Inputs, source permissions, wire schema, lowered programs,
validations and execution outputs remain equal between modes; only the instruction
prefix changes. The unsupported statements still pass structural validation.
Fixed responses cannot show that the instruction improves model behavior or preserves
recall; compliance and over-abstention remain unmeasured.

Focused existing contracts pass **34/34**, documentation checks **4/4**, no skips
or external connection attempts. All **173** source files, **2,177** protected
predecessors, **24** stores and local settings retain hashes. Prior full **2029/2029**
and audit **83** remain unchanged-source evidence, not rerun. The consumed live
manifest remains consumed and no new admission was created.

Next: apply only this reviewed narrative instruction in the policy owner and verify
its delivery through current general/narrative Compiler templates without changing
schema, source authority, execution or historical results. Use provider-free contracts;
make no provider-quality claim, paid request, fresh admission or cap increase.
