"""Provider-free integrity checks; no product tests or live clients are run."""
from __future__ import annotations
import copy
import importlib.util
import json
import os
import subprocess
from pathlib import Path

O = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('top8_prepare_for_validation', O / 'prepare.py')
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
ROOT = m.ROOT


def main():
    inputs = json.loads((O / 'input_manifest.json').read_text('utf8'))
    inputs.update(json.loads((O / 'analysis_input_manifest.json').read_text('utf8')))
    changed = [p for p, h in inputs.items() if not (ROOT / p).is_file() or m.sha(ROOT / p) != h]
    assert not changed, ('Consumed input changed', changed)
    requests = m.load(O / 'requests18.json')
    schedule = m.load(O / 'schedule72.json')
    protocol = m.load(O / 'protocol.json')
    prices = m.load(O / 'pricing.json')
    assert m.load(O / 'rubric18.json') == m.load(m.PREP18 / 'rubric.json'), 'Frozen rubric changed'
    review18 = m.load(O / 'review18.json')
    review77 = m.load(O / 'review77_focus.json')
    assert len(review18['cases']) == 18 and len(review77['cases']) == 12
    assert {c['case_id'] for c in review18['cases']} == {r['case_id'] for r in requests}
    assert review18['verification']['top8_units_checked_including_repeats'] == 1106
    lookup = {(r['case_id'], r['arm']): r for r in requests}
    for row in requests:
        body = copy.deepcopy(row['body'])
        packet = json.loads(body['input'][1]['content'])
        assert m.digest(packet) == row['packet_sha256']
        assert m.digest(body) == row['body_sha256']
        assert len(m.enc(body)) + 4096 == row['input_bound']
        body['input'][1]['content'] = '<PACKET>'
        assert body == protocol['fixed_generation']
        assert len(packet['documents']) == 8
    for row in schedule:
        r = lookup[row['case_id'], row['arm']]
        assert row['input_bound'] == r['input_bound'] and row['body_sha256'] == r['body_sha256']
    assert sum(r['input_bound'] for r in schedule) == prices['reserved_input_tokens_total']
    assert len(schedule) == prices['call_limit'] == protocol['call_limit_future'] == 72
    for cid in {r['case_id'] for r in requests}:
        a = m.load(O / f'packets/{cid}_A.json'); c = m.load(O / f'packets/{cid}_C.json')
        assert m.remove_facts(c) == a and len(m.enc(c)) <= 65536

    # Deliberate corruption must fail at the delivered physical binding boundary.
    # These are copies in memory; no original or prepared packet is overwritten.
    m.ASSEMBLER = m.module(m.OLD77 / 'run.py', 'frozen_assembler_for_validation')
    projections = m.load(m.EXEC18 / 'projections.json')
    packet = m.load(O / 'packets/H01_C.json')
    decisions = m.load(O / 'decisions/H01.json')
    m.unit_map(packet, decisions, projections)
    index = next(i for i, d in enumerate(packet['documents']) if d.get('table_fact_units'))
    mutations = {
        'wrong_source_owner': lambda w: w.update(source_id='invalid-owner'),
        'altered_value_literal': lambda w: w['cells'][w['units'][0][2]].__setitem__(4, 'not-the-source-value'),
        'altered_expanded_cell_position': lambda w: w['units'][0].__setitem__(0, w['units'][0][0]+1),
        'wrong_row_axis': lambda w: w['units'][0].__setitem__(3, [] if w['units'][0][3] else [w['units'][0][2]]),
        'altered_context_frame': lambda w: w.update(table_locator='/invalid-table'),
    }
    guards = {}
    for name, mutate in mutations.items():
        bad = copy.deepcopy(packet)
        mutate(bad['documents'][index]['table_fact_units'])
        try:
            m.unit_map(bad, decisions, projections)
        except AssertionError:
            guards[name] = 'REJECTED'
        else:
            raise AssertionError('Corruption accepted: ' + name)
    old = m.load(O / 'before.json')
    protected_changes = [p for p, h in old['files'].items() if not (ROOT / p).is_file() or m.sha(ROOT / p) != h]
    env = dict(os.environ); env['GIT_OPTIONAL_LOCKS'] = '0'
    git = lambda *args: subprocess.check_output(['git', *args], cwd=ROOT, env=env)
    head = git('rev-parse','HEAD').decode().strip()
    index_path = ROOT / git('rev-parse', '--git-path', 'index').decode().strip()
    index_sha = m.sha(index_path)
    # Match the initial snapshot's explicit all-files, NUL-delimited encoding.
    status = git('status','--short','--untracked-files=all','-z')
    import hashlib
    status_sha = hashlib.sha256(status).hexdigest()
    assert not protected_changes, ('Protected file changed', protected_changes)
    assert head == old['head'] and index_sha == old['index_sha256']
    assert status_sha == old['git_status_sha256']
    preservation = {'status': 'PASS', 'protected_file_count': len(old['files']),
                    'changed_protected_files': protected_changes, 'head_unchanged': True,
                    'index_byte_identical': True, 'git_status_identical': True,
                    'git_status_command': 'git status --short --untracked-files=all -z',
                    'env_byte_identical': '.env' in old['files'],
                    'active_store_files_byte_identical': old['active_store_files'],
                    'consumed_input_files_checked': len(inputs), 'changed_consumed_inputs': changed,
                    'store_clients_opened': 0, 'sqlite_internal_bytes': 'Byte-identical; store was never opened by this task.',
                    'live_application_restart': False}
    m.put('preservation_final.json', preservation)
    m.put('validation.json', {'status':'PASS', 'preparation':m.load(O/'preparation_result.json'),
                            'request_body_schema_prompt_settings_match':36, 'balanced_schedule_calls':72,
                            'existing18_rubric_unchanged':True,
                            'bounded_reviews':{'exposed18':18,'old77_focus':12,'not_full77_semantic_regrade':True},
                            '18_A8_C8_actual_evidence_parity':True, 'all18_boosted_packets_fit64KiB':True,
                            'corruption_guards':guards, 'preservation':preservation,
                            'negative_control_scope':'Physical binding rejection only; not a semantic verifier.'})
    print(json.dumps({'status':'PASS','input_files':len(inputs),'corruption_guards':guards,'preservation':preservation},ensure_ascii=False))


if __name__ == '__main__': main()
