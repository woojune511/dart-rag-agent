"""One bounded budget-only replay of saved units; never open a store/provider."""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import time

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
OLD = OUT.parent / 'table_fact_units_offline_20261023'
load = lambda p: json.loads(Path(p).read_text(encoding='utf-8'))
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
start = time.monotonic()


def save(name, value):
    target = (OUT / name).resolve()
    assert target.is_relative_to(OUT)
    target.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def beat(**data):
    data['elapsed_seconds'] = round(time.monotonic() - start, 2)
    with (OUT / 'heartbeat.jsonl').open('a', encoding='utf-8') as f:
        f.write(json.dumps(data, ensure_ascii=False) + '\n')
    print(json.dumps(data, ensure_ascii=False), flush=True)


assert not (OUT / 'started.json').exists(), 'One diagnostic run only'
contract = load(OUT / 'contract.json')
save('freeze.json', {str(p.relative_to(ROOT)): sha(p) for p in [OUT / 'contract.json', Path(__file__), OLD / 'run.py', OLD / 'projections.json', OLD / 'results.json']})
save('started.json', {'at': time.time(), 'external_calls': 0})
spec = importlib.util.spec_from_file_location('saved_fact_packet_runner', OLD / 'run.py')
saved = importlib.util.module_from_spec(spec)
spec.loader.exec_module(saved)  # Installs network-denial guards; does not execute CLI.
projections = load(OLD / 'projections.json')
baseline = load(OLD / ('packets/' + contract['case_id'] + '_A12.json'))
old_result = next(r for r in load(OLD / 'results.json') if r['case_id'] == contract['case_id'])
uid = next(d['chunk_id'] for d in baseline['documents'] if d['chunk_id'].endswith(':1246:4'))
units = projections[uid]['projection']['units']
targets = [next(u for u in units if u['at'] == target['at']) for target in contract['targets']]
results = []
for kib in contract['caps_KiB']:
    assert time.monotonic() - start < contract['timeout_seconds']
    saved.CAP = kib * 1024
    packet, decisions = saved.project_packet(baseline, projections)
    assert {**packet, 'documents': [{k: v for k, v in d.items() if k != saved.FIELD} for d in packet['documents']]} == baseline
    if kib == 64:
        assert saved.digest(packet) == old_result['experimental_packet_sha256']
        assert decisions == old_result['decisions']
    target_doc = next(d for d in decisions if d['uid'] == uid)
    by_id = {u['unit_id']: u for u in target_doc.get('units', [])}
    target_results = []
    for unit, target in zip(targets, contract['targets']):
        assert projections[uid]['projection']['cells'][unit['value']][4] == target['value']
        d = by_id[unit['unit_id']]
        target_results.append({**target, 'status': d['status'], 'incremental_bytes': d['incremental_bytes'],
                               'proposed_packet_bytes': d['proposed_packet_bytes']})
    attached_rows = [u['at'][0] for u in target_doc['units'] if u['status'] == 'attached']
    row = {'cap_KiB': kib, 'cap_bytes': saved.CAP,
           'actual_packet_bytes': len(saved.encoded(packet).encode('utf-8')),
           'target_table_attached_units': target_doc.get('unit_count', 0),
           'target_table_last_attached_expanded_row': max(attached_rows) if attached_rows else None,
           'targets': target_results, 'both_targets_delivered': all(t['status'] == 'attached' for t in target_results),
           'original_packet_preserved': True, 'packet_sha256': saved.digest(packet)}
    results.append(row)
    # Diagnostics retain only this case's small final packets and target decisions.
    save(f'packet_{kib}KiB.json', packet)
    beat(cap_KiB=kib, actual_packet_bytes=row['actual_packet_bytes'],
         table_units=row['target_table_attached_units'], both_targets_delivered=row['both_targets_delivered'])

before = load(OUT / 'before.json')
changed = [p for p, r in before['files'].items() if not (ROOT / p).is_file() or sha(ROOT / p) != r['sha256']]
preservation = {'protected_files': len(before['files']), 'changed': changed,
                'head_unchanged': subprocess.check_output(['git','rev-parse','HEAD'], cwd=ROOT).decode().strip() == before['head'],
                'index_unchanged': sha(ROOT / '.git/index') == before['index'],
                'git_status_unchanged': subprocess.check_output(['git','status','--porcelain=v1','-uall'], cwd=ROOT) == (OUT / 'git_status_before.bin').read_bytes(),
                'external_API_calls': 0, 'new_source_projections': 0, 'store_client_opened': False,
                'app_restarts': 0}
assert not changed and all(preservation[k] for k in ['head_unchanged','index_unchanged','git_status_unchanged'])
save('preservation.json', preservation)
save('results.json', {'scope': contract['scope'], 'case_id': contract['case_id'],
                      'source_owner': uid, 'baseline_64KiB_exact_replay': True,
                      'rows': results, 'elapsed_seconds': round(time.monotonic() - start, 2),
                      'source_or_answer_accuracy': 'Not re-evaluated; target delivery only',
                      'first_success_among_predeclared_caps_KiB': next((r['cap_KiB'] for r in results if r['both_targets_delivered']), None)})
beat(phase='completed', caps=len(results), protected_files=len(before['files']))
