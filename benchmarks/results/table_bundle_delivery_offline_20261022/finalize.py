"""Assemble a bounded offline evidence report; does not rerun the experiment."""
import hashlib
import json
from pathlib import Path

OUT = Path(__file__).resolve().parent
def load(name):
    return json.loads((OUT / name).read_text(encoding='utf-8'))
def write(name, value):
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

criteria = load('evaluation_contract.json')
results = {x['case_id']: x for x in load('results.json')}
axes = load('postrun_axis_review.json')
facts = load('postrun_required_fact_review.json')
boundary = load('postrun_boundary_review.json')
assert 'PENDING' not in axes['status'] and 'IN_PROGRESS' not in axes['status']
assert boundary['independently_verified']['failures'] == []
assert axes['summary']['confirmed_wrong_new_physical_links'] == 0
assert load('preservation.json')['changed'] == []
focus = {
    'SKI_T1_068': {
        'verdict': 'FULL_EVIDENCE_RECOVERY', 'recovery_type': 'MANDATORY_CURRENCY_AXIS_ONLY',
        'newly_available_required_units': [], 'mandatory_axis_recoveries': ['currency_binding'],
        'remaining_missing_or_unresolved_units': [],
        'explanation': 'Already visible battery loss(581,816) and total operating income1,903,886 now receive the literal source-linked 백만원 caption. No new numeric value; old misleading unit_hint:% remains in preserved original text. No new answer was generated.',
        'supporting_packet_spans_and_source_locators': [
            'packets/SKI_T1_068_T12.json:documents[4].table_evidence.grid[12][2],grid[24][2]',
            '/DOCUMENT/BODY/SECTION-1[5]/TABLE[7]',
            '/DOCUMENT/BODY/SECTION-1[5]/TABLE[6]:decoded span[0,46]'
        ]
    },
    'POS_T1_057': {
        'verdict': 'NO_RECOVERY', 'newly_available_required_units': [], 'mandatory_axis_recoveries': [],
        'remaining_missing_or_unresolved_units': ['operating_income'],
        'explanation': 'Interest cost preserved, but required compatible operating income remains outside actual A12/T12 text and appended complete tables. No top12 or candidate change was made.'
    },
    'SKH_T1_060': {
        'verdict': 'NO_RECOVERY', 'newly_available_required_units': [], 'mandatory_axis_recoveries': [],
        'remaining_missing_or_unresolved_units': ['ppe', 'intangible'],
        'explanation': 'Borrowing evidence remains; two required asset denominators are still absent. Nine originally delivered sources remain nine; original byte omissions were not refilled.'
    },
    'HYU_T3_072': {
        'verdict': 'NO_RECOVERY', 'newly_available_required_units': [], 'mandatory_axis_recoveries': [],
        'remaining_missing_or_unresolved_units': ['ownership', 'carrying', 'profit_summary'],
        'explanation': 'Selected1246:4 already stores the same225x16 physical table with Motional row225:140, closing ownership25.81 and carrying1,294,367. The entire first-owner bundle fails on an ambiguous aggregate row, before byte admission. Therefore not simply candidate absence; hypothetical byte acceptance or full requested profit-summary recovery is unmeasured.'
    }
}

all_cases = []
for c in criteria['cases']:
    cid = c['case_id']; r = results[cid]
    default = ('HOLD_DIAGNOSTIC_ONLY' if c['group'] == 'diagnostic_or_hold'
               else 'REFUSAL_POLICY_CONTROL' if c['group'] == 'refusal' else 'PRESERVED')
    row = {
        'case_id': cid, 'group': c['group'], 'question': c['question'],
        'baseline_sol12_grade': c['baseline_sol12_grade'],
        'original_packet_hashes_equal_after_removing_only_table_evidence': True,
        'original_text_context_ids_order_preserved': r['original_documents_text_context_ids_order_identical'],
        'selected12': r['selected12'], 'delivered_ids': r['delivered_ids'],
        'new_bundle_source_validation': 'Frozen projector admission plus raw-grid/span author review; independent packet constraints. Not independent full semantic verification.',
        'required_units_contract': c['required_units'],
        'required_units_before_after_detail': 'postrun_required_fact_review.json for four current failures and26-unit subpanel; other cases retain original evidence without a new semantic regrade.',
        'newly_available_required_units': 'NO_ADDITIONAL_GAIN_CLAIM_OUTSIDE_REVIEWED_UNITS',
        'mandatory_axis_recoveries': [],
        'already_available_repetitions': 'Reprinting baseline-supported facts is not counted as recovery.',
        'remaining_missing_or_unresolved_units': 'Use frozen HOLD/policy/requirement boundaries; no inferred completion.',
        'byte_budget_skips': [d['uid'] for d in r['decisions'] if d['status'] == 'rejected_byte_budget'],
        'structural_validation_skips': [d for d in r['decisions'] if d['status'] == 'rejected_structural_validation'],
        'invalid_links': {'observed_new_physical_mismatches': 0, 'semantic_safety': 'NOT_CERTIFIED'},
        'verdict': default,
        'baseline_bytes': r['baseline_bytes'], 'experimental_bytes': r['experimental_bytes'],
        'added_tables': r['attached_tables'],
        'historical_nonpass_focus': c['historical_nonpass_focus'],
        'refusal_policy_focus': c['refusal_policy_focus'],
        'table_binding_watch': c['audit_binding_watch'],
        'answer_outcome_NOT_MEASURED': True,
        'supporting_packet_spans_and_source_locators': [f'packets/{cid}_A12.json', f'packets/{cid}_T12.json'],
    }
    if cid in focus:
        row.update(focus[cid])
    all_cases.append(row)
assert len(all_cases) == 77
write('all77_evidence_review.json', all_cases)
write('final_adjudication.json', {
    'verification_status': 'ANALYZED', 'date_local': '2026-10-23',
    'experiment': 'One frozen original-A12 versus append-only T12 offline delivery comparison',
    'all77_original_evidence_preserved': 77,
    'current_common_nonpass_cases_reviewed': 4,
    'current_nonpass_cases_with_new_required_numeric_values': 0,
    'current_nonpass_cases_with_mandatory_axis_recovery': 1,
    'mandatory_axis_recovery_case': 'SKI_T1_068',
    'confirmed_physical_link_mismatches_in_source_audit': 0,
    'source_audit_is_author_review': True,
    'independent_all77_packet_invariant_violations': 0,
    'adoption': 'NOT_ADOPTED: narrow axis-delivery benefit; no generated-answer benefit measured; whole-table overhead and rejection isolation remain limitations.',
    'next_design_hypothesis_only': 'Validate and budget source-bound fact units independently so an unrelated ambiguous row does not invalidate a whole table. No implementation or alternate scoring performed.',
    'new_answer_accuracy_completeness_faithfulness_refusal': 'NOT_MEASURED',
    'evidence_files': {n: hashlib.sha256((OUT/n).read_bytes()).hexdigest() for n in [
        'freeze.json', 'results.json', 'evaluation_contract.json', 'postrun_required_fact_review.json',
        'postrun_axis_review.json', 'postrun_boundary_review.json', 'preservation.json'
    ]},
})
print('Assembled77-case evidence report and bounded final adjudication; no experiment rerun.')
