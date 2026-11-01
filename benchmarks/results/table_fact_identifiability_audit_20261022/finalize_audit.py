"""Reconcile saved-case audits and verify unchanged protected inputs; no inference."""
from collections import Counter
import subprocess

from collect import ROOT, OUT, load, save, sha
from reconcile import main as reconcile


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT)


def main():
    reconcile()
    inventory = load(OUT / 'case_inventory.json')
    findings = {x['case_id']: x for x in load(OUT / 'findings.json')}
    boundary = {x['case_id']: x for x in load(OUT / 'boundaries_review.json')['cases']}
    numeric = load(OUT / 'numeric_review.json')
    axes = load(OUT / 'axes_review.json')
    root = load(OUT / 'root_source_witnesses.json')
    reviewed = set(findings) | set(boundary) | {'MIX_T4_062'}
    queued = {x['case_id'] for x in inventory if x['detailed_review_queued']}
    assert queued <= reviewed
    assert len(inventory) == len({x['case_id'] for x in inventory}) == 77
    assert Counter(x['group'] for x in inventory) == {
        'common_answerable': 46, 'refusal': 19, 'diagnostic_or_hold': 12}
    rows = []
    for original in inventory:
        cid = original['case_id']
        row = dict(original)
        row['new_accuracy_grade'] = None
        row['refusal_policy_failure_in_saved_results'] = (
            row['group'] == 'refusal' and any(
                v.get('correctness') not in ('PASS', None)
                for v in row['saved_judgments'].values()))
        row['audit_depth'] = ('source_and_packet_focus' if cid in findings
                              else 'saved_boundary_review' if cid in boundary
                              else 'saved_policy_review' if cid == 'MIX_T4_062'
                              else 'inventory_screen_only')
        row['current_assessment'] = findings.get(cid) or (
            {k: boundary[cid].get(k) for k in (
                'primary_boundary', 'table_identifiability', 'finding')}
            if cid in boundary else
            {'primary_boundary': 'REFUSAL_POLICY_MISMATCH',
             'finding': '동결 grounded-only 정책과 명시적 가정 계산의 불일치. 저장된 세 조건에서 support PASS이며 표 근거 누락으로 판정하지 않음.'}
            if cid == 'MIX_T4_062' else
            {'primary_boundary': 'NO_SAVED_FAILURE_SELECTED',
             'finding': '기존 판정과 출처 변경 검토에 이번 심층 분석 대상 신호가 없음. 새 의미 검증 PASS나 원문 완전성을 뜻하지 않음.'})
        rows.append(row)
    save('all77_disposition.json', rows)

    # Fresh source validations only: distinguish span matching from whole-node text.
    assert numeric['summary']['all_saved_source_contexts_verified'] is True
    assert axes['checks']['all_context_span_locator_hash_verified'] is True
    assert axes['checks']['all_table_locator_unique'] is True
    assert all(x['strict_parse_errors'] == 0 for x in root['source_checks'].values())
    assert all(r['table_locator_and_document_sha_verified'] for r in root['records'].values())
    b = load(OUT / 'before.json')
    manifest = load(OUT / 'input_manifest.json')
    protected = dict(b['files'])
    for path, old in manifest.items():
        if path in protected:
            assert protected[path]['sha256'] == old['sha256'], path
        protected[path] = old
    changed = []
    for path, old in protected.items():
        actual = ROOT / path
        if not actual.is_file():
            changed.append({'path': path, 'reason': 'missing'})
        elif sha(actual) != old['sha256'] or actual.stat().st_size != old['bytes']:
            changed.append({'path': path, 'reason': 'content_changed'})
    status = git('status', '--porcelain=v1', '-uall')
    store_files = [p for p in b['files'] if 'app_full11_2023_v12_20261017' in p]
    validation = {
        'status': 'ANALYZED',
        'new_model_api_calls': 0, 'new_retrieval_runs': 0,
        'new_answers': 0, 'cost_usd': 0, 'app_restarts': 0,
        'all77_unique': True,
        'canonical_groups': dict(Counter(x['group'] for x in rows)),
        'saved_failure_or_support_union': sum(x['historical_failure_or_support_issue'] for x in rows),
        'prior_source_review_or_failure_queue': len(queued),
        'reviewed_cases_including_two_policy_sentinels': len(reviewed),
        'focus_cases': len(findings),
        'audit_depth': dict(Counter(x['audit_depth'] for x in rows)),
        'focus_literal_structure_levels': dict(Counter(x['identifiability'] for x in findings.values())),
        'focus_layer_flags_nonexclusive_historical_conditions': dict(Counter(
            y for x in findings.values() for y in x['failure_layers'])),
        'all_queued_cases_reviewed': not bool(queued - reviewed),
        'new_semantic_accuracy_or_causal_effect_measured': False,
        'fresh_source_checks': {
            'numeric_export_records': len(numeric['source_extracts']),
            'axes_export_targets': axes['checks']['target_count'],
            'root_table_targets': len(root['records']),
            'source_span_checks_pass': True,
            'note': 'Some contexts use a substring of an XML paragraph; exact source_span, not whole-node equality, is the contract. Existing sanitizer used in memory before strict parse.'},
        'preservation': {
            'workspace_snapshot_files': len(b['files']),
            'prior_input_manifest_files': len(manifest),
            'unique_protected_files': len(protected),
            'active_store_files': len(store_files),
            'content_changes': changed,
            'head_unchanged': git('rev-parse', 'HEAD').decode().strip() == b['head'],
            'index_unchanged': sha(ROOT / '.git/index') == b['index'],
            'git_status_unchanged': status == (OUT / 'git_status_before.bin').read_bytes(),
            'env_unchanged': sha(ROOT / '.env') == b['files']['.env']['sha256'],
            'store_unchanged': all(not any(c['path'] == p for c in changed) for p in store_files),
            'sqlite_note': 'Only file hashes read. No SQLite/Chroma connection was opened by the audit; database internals and data files were not rewritten.'}}
    save('final_validation.json', validation)
    assert not changed, changed
    assert all(validation['preservation'][k] for k in (
        'head_unchanged', 'index_unchanged', 'git_status_unchanged', 'env_unchanged', 'store_unchanged'))
    print({k: validation[k] for k in (
        'all77_unique', 'reviewed_cases_including_two_policy_sentinels', 'focus_cases',
        'audit_depth', 'focus_literal_structure_levels')})
    print(validation['preservation'])


if __name__ == '__main__':
    main()
