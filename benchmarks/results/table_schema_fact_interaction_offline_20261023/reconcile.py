"""Parent bookkeeping validation; bounded semantic review remains explicit."""
import json
import run

OUT,ROOT=run.OUT,run.ROOT
review=run.load(OUT/'required_evidence_review.json')
contract=run.load(OUT/'evaluation_supplement.json')
assert review['status']=='COMPLETE_BOUNDED_SOURCE_REVIEW'
for p,h in review['input_hashes'].items():assert run.sha(ROOT/p)==h,p
for name,h in review['packet_hashes'].items():assert run.sha(OUT/f'packets/{name}.json')==h,name
for source in review['source_files_rechecked'].values():assert run.sha(ROOT/source['path'])==source['sha256']
for key,criteria in [('legacy26_panel','historical26_unit_panel'),('current4','current_nonPASS_case_criteria')]:
    frozen={c['case_id']:c for c in contract[criteria]}
    assert {c['case_id'] for c in review[key]}==frozen.keys()
    for case in review[key]:
        units={u['unit_id']:u for u in frozen[case['case_id']]['units']}
        assert {u['unit_id'] for u in case['units']}==units.keys()
        for u in case['units']:
            assert u['unchanged_criterion']==units[u['unit_id']]['unchanged_criterion']
            assert set(u['present_with_required_relationship_by_arm'])==set(run.ARMS)
            assert all(type(v) is bool for v in u['present_with_required_relationship_by_arm'].values())
for arm,summary in review['summary'].items():
    common=[c for c in review['legacy26_panel'] if c['group']=='common_answerable']
    hold=[c for c in review['legacy26_panel'] if c['group']!='common_answerable']
    cnt=lambda cases:sum(u['present_with_required_relationship_by_arm'][arm] for c in cases for u in c['units'])
    complete=lambda cases:sum(all(u['present_with_required_relationship_by_arm'][arm] for u in c['units']) for c in cases)
    assert cnt(common)==summary['legacy_common_present'] and cnt(hold)==summary['legacy_HOLD_present']
    assert complete(common)==summary['legacy_common_complete_cases'] and complete(hold)==summary['legacy_HOLD_conditional_complete_cases']
    assert cnt(review['current4'])==summary['current4_required_units_present']
    assert complete(review['current4'])==summary['current4_complete_cases']
result={'status':'PASS_BOOKKEEPING_AND_INPUT_RECEIPTS','review_sha256':run.sha(OUT/'required_evidence_review.json'),
    'packet_hashes_verified':len(review['packet_hashes']),'source_hashes_verified':len(review['source_files_rechecked']),
    'unchanged_criteria_and_unit_IDs':True,'all_four_arm_counts_recomputed':True,
    'semantic_scope':'Parent integrates bounded unblinded source review; no independent full77 answer judgement.',
    'hypothesis_gate':'FAIL_REQUIRED_EVIDENCE_REGRESSION; experimental execution itself passed.'}
run.save('required_reconciliation.json',result)
run.save('required_entry.json',{'kind':'tool_receipt','step':'bounded_required_evidence_review','status':'passed',
    'command':'Delegated source review; parent reconcile.py','exit_status':0,'retries_used':0,
    'input_sha256':{'required_evidence_review.json':run.sha(OUT/'required_evidence_review.json'),'reconcile.py':run.sha(OUT/'reconcile.py')},
    'output_sha256':run.sha(OUT/'required_reconciliation.json'),'gate_tokens':['LEGACY26_CURRENT4_SEPARATE','COUNTS_RECONCILED','NO_ADOPTION_GATE']})
print(json.dumps(result,ensure_ascii=False))
