"""Reconcile immutable output reviews and preserve the current workspace."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

OUT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('budget77_local_comparison', OUT / 'compare.py')
comp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(comp)
load, save, sha = comp.load, comp.save, comp.sha
comp.frozen()

aggregate = load(OUT / 'aggregate_summary.json')
physical = load(OUT / 'postrun_boundary_review.json')
axes = load(OUT / 'postrun_axis_review.json')
facts = load(OUT / 'postrun_required_fact_review.json')
matrix = load(OUT / 'all77_evidence_review.json')
contract = load(OUT / 'evaluation_contract.json')
results = load(OUT / 'results.json')
assert load(OUT / 'launcher_result.json')['exit_code'] == 0
assert len(results) == len(matrix['cases']) == 77
assert {r['case_id'] for r in results} == {r['case_id'] for r in matrix['cases']}
assert physical['issues'] == facts['source_errors'] == []
assert aggregate['exact64_replays'] == physical['scope']['exact_64KiB_previous_packet_and_decision_replays'] == 77
assert aggregate['unit_changes']['retained'] == facts['summary']['retained64_units'] == axes['summary']['retained_units_with_same_wire_value_row_column_axes'] == 9465
assert aggregate['unit_changes']['added'] == facts['summary']['added160_units'] == axes['summary']['added_units'] == 8307
assert aggregate['unit_changes']['lost'] == facts['summary']['lost64_units'] == axes['summary']['lost_units'] == 0
assert axes['summary']['changed_shared_table_frames'] == axes['summary']['changed_retained_unit_payloads'] == 0
criteria = {c['case_id']: c for c in contract['cases']}
assert sum(len(c['required_criteria']) for c in matrix['cases']) == 154
for row in matrix['cases']:
    original = criteria[row['case_id']]
    assert row['question_unchanged'] == original['question']
    assert [r['frozen_criterion'] for r in row['required_criteria']] == original['required_units']
    assert all(r['original_evidence_preserved'] and r['FCT64_enrichment_preserved'] and
               r['new_answer_verdict'] == 'NOT_MEASURED_NO_GENERATION' for r in row['required_criteria'])
assert facts['summary']['current4_new_complete_required_units'] == ['HYU_T3_072:ownership', 'HYU_T3_072:carrying']
assert facts['summary']['current4_new_complete_cases'] == facts['summary']['hold_status_lifted'] == 0
assert facts['summary']['legacy_common20_present_64'] == facts['summary']['legacy_common20_present_160'] == 18
assert facts['summary']['legacy_HOLD6_present_64'] == facts['summary']['legacy_HOLD6_present_160'] == 6

print('All three reviews and all154 unchanged criteria reconciled. Final protected-file check follows.', flush=True)
comp.preservation()
preservation = load(OUT / 'preservation.json')
adjudication = {
    'status': 'COMPLETED_OFFLINE_BUDGET_ONLY_COMPARISON_NO_PRODUCTION_CHANGE',
    'caps_bytes': [65536, 163840], 'cases': 77, 'frozen_criteria': 154,
    'external_API_calls': 0, 'new_answers': 0, 'cost_usd': 0,
    'confirmed': {'64KiB_exact_reproduction': 77, 'original_packet_preservation': 77,
                  'retained_unit_events': 9465, 'new_unit_events': 8307, 'lost_unit_events': 0,
                  'retained_axis_or_context_changes': 0, 'physical_binding_mismatches': 0,
                  'Motional_new_required_categories': ['ownership', 'carrying'],
                  'Motional_scope': '타법인출자 현황(상세) 2023.12.31 기말잔액 기준 대안; no literal 별도 certification',
                  'Motional_profit_summary_complete': False,
                  'new_complete_current4_cases': 0, 'HOLD_status_lifted': 0,
                  'HOLD_conditional_recovery': facts['summary']['hold_conditional_new_complete_unit'],
                  'HOLD_partial_components': facts['summary']['hold_new_partial_component_only'],
                  'total_context_bytes_increase_percent': load(OUT / 'descriptive_statistics.json')['total_bytes_relative_increase_percent']},
    'limits': ['No generated-answer improvement or regression measured.',
               'All77 evidence preservation is exact; new semantic review is bounded, not154 fresh PASS grades.',
               'Remaining candidate/selection gaps are unchanged; larger budget cannot invent absent evidence.',
               'MIX047 pre-existing inferred prefix exposure grows34 to493 units; semantic safety is not certified.',
               'Development-exposed panel and previously diagnosed160KiB target; not held-out generalization.'],
    'preservation': preservation,
    'artifacts': {name: sha(OUT / name) for name in ['protocol.json', 'freeze.json', 'results.json',
                  'aggregate_summary.json', 'descriptive_statistics.json', 'all77_evidence_review.json',
                  'postrun_required_fact_review.json', 'postrun_axis_review.json', 'postrun_boundary_review.json',
                  'validation.json', 'preservation.json', 'report.md']}}
save('final_adjudication.json', adjudication)
(OUT / 'passport.md').write_text('''## Material Passport

- Origin Skill: academic-research-suite / experiment-agent run and validate
- Origin Date: 2026-10-23 Asia/Seoul
- Verification Status: VERIFIED_64KiB_REPRODUCTION / ANALYZED_OFFLINE_DELIVERY
- Scope: Saved numeric units and candidate/order/selected12 fixed; only context cap64KiB versus160KiB.
- Completion: All77 executed once per cap; all154 frozen criteria retained. No model-generated answers.
- Result: Motional investment ownership/carrying evidence recovered at160KiB, profit summary incomplete. Prior evidence and axes retained; physical linkage checks found no mismatch.
- Limits: Development-exposed panel; bounded semantic interpretation, shared-context author review, no blind or cross-model claim.
- Model: Current Codex runtime preserved; identity not independently attested.
- External API calls and cost: 0 / $0.
- Preservation: 5626 protected files, .env, all11 active v12 store files and git HEAD/index/status unchanged.
- Implementation disposition: No production change; authorized offline comparison completed.
- Authoritative report: report.md
- Reconciled evidence: final_adjudication.json
''', encoding='utf-8')

ledger = Path(r'C:\Users\geonj\.codex\skills\academic-research-suite\ars\scripts\run_ledger.py')
entries = [
    ('independent_physical_review', 'postrun_boundary_review.json', ['postrun_boundary_check.py', 'results.json'],
     ['154_CASE_ARMS', '37568_BUDGET_PROPOSALS', 'NO_PHYSICAL_MISMATCH']),
    ('required_evidence_review', 'postrun_required_fact_review.json', ['required_fact_review.py', 'evaluation_contract.json', 'all77_evidence_review.json'],
     ['154_CRITERIA_UNCHANGED', 'MOTIONAL_TWO_CATEGORIES_PARTIAL', 'LEGACY_REQUIRED_EVIDENCE_RETAINED']),
    ('bounded_axis_review', 'postrun_axis_review.json', ['axis_evidence_check.py', 'results.json'],
     ['19_AXIS_WATCH_CASES', 'NO_LOST_AXES', 'SEMANTIC_SAFETY_NOT_CERTIFIED']),
    ('final_reconciliation_and_preservation', 'final_adjudication.json', ['finalize.py', 'preservation.json', 'validation.json', 'report.md'],
     ['ALL77_COMPLETED', 'PROTECTED_5626_UNCHANGED', 'NO_API_NO_APP_RESTART', 'NO_PRODUCTION_CHANGE']),
]
claims = load(OUT / 'claims.json')
for step, output, inputs, gates in entries:
    entry = {'kind': 'tool_receipt', 'step': step, 'command': 'Local saved-output validation and artifact reconciliation: ' + output,
             'status': 'passed', 'exit_status': 0, 'retries_used': 0,
             'input_sha256': {name: sha(OUT / name) for name in inputs},
             'output_sha256': sha(OUT / output), 'gate_tokens': gates}
    name = step + '_entry.json'
    save(name, entry)
    subprocess.run([sys.executable, '-B', '-X', 'utf8', str(ledger), 'append',
                    '--passport-path', str(OUT / 'passport.md'), '--entry-file', str(OUT / name)], check=True)
    claims['steps'].append({'step': step, 'status': 'passed'})
save('claims.json', claims)
subprocess.run([sys.executable, '-B', '-X', 'utf8', str(ledger), 'report',
                '--passport-path', str(OUT / 'passport.md'), '--claims', str(OUT / 'claims.json'), '--render', 'en'], check=True)
print(json.dumps({'status': adjudication['status'], 'ledger_claims': len(claims['steps']),
                  'protected_files': preservation['protected_files'], 'report_sha256': sha(OUT / 'report.md')}), flush=True)
