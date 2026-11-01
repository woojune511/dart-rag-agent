"""Budget-only replay over immutable saved fact units. Never ingest or call providers."""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import statistics
import subprocess
import sys
import time

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
OLD = OUT.parent / 'table_fact_units_offline_20261023'
PRIOR_DIAGNOSTIC = OUT.parent / 'table_fact_budget_diagnostic_20261023'
CAPS = (65536, 163840)
START = time.monotonic()


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(4 * 1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def save(name, obj):
    path = (OUT / name).resolve()
    assert path.is_relative_to(OUT)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT)


def beat(phase, **data):
    row = {'phase': phase, 'elapsed_seconds': round(time.monotonic() - START, 2), **data}
    with (OUT / 'heartbeat.jsonl').open('a', encoding='utf-8') as f:
        f.write(json.dumps(row, ensure_ascii=False) + '\n')
    print(json.dumps(row, ensure_ascii=False), flush=True)


def setup():
    assert not (OUT / 'before.json').exists()
    assert git('check-ignore', str(OUT.relative_to(ROOT))).strip()
    prior = load(OLD / 'before.json')['files']
    paths = {ROOT / p for p in prior}
    for folder in (OLD, PRIOR_DIAGNOSTIC):
        paths.update(p for p in folder.rglob('*') if p.is_file())
    paths.update(ROOT / p.decode('utf-8') for p in git('ls-files', '--cached', '--others', '--exclude-standard', '-z').split(b'\0') if p)
    paths.add(ROOT / '.env')
    paths.update(p for p in (ROOT / 'data/app_full11_2023_v12_20261017').rglob('*') if p.is_file())
    assert all(p.is_file() and not p.resolve().is_relative_to(OUT) for p in paths)
    status = git('status', '--porcelain=v1', '-uall')
    (OUT / 'git_status_before.bin').write_bytes(status)
    files = {str(p.relative_to(ROOT)).replace('\\', '/'): {'sha256': sha(p), 'bytes': p.stat().st_size}
             for p in sorted(paths)}
    save('before.json', {'files': files, 'head': git('rev-parse', 'HEAD').decode().strip(),
                         'index': sha(ROOT / '.git/index'), 'at': time.time()})
    for name in ('evaluation_contract.json', 'evaluation_supplement.json'):
        (OUT / name).write_bytes((OLD / name).read_bytes())
    save('protocol.json', {
        'schema_version': 'saved_fact_budget77_v1', 'status': 'FROZEN_BEFORE_FULL77_OUTPUT',
        'classification': 'isolated offline context-budget experiment; no runtime change',
        'population': {'cases': 77, 'common_answerable': 46, 'refusal': 19, 'HOLD': 12},
        'only_treatment': {'context_cap_UTF8_bytes': list(CAPS), 'labels': ['64KiB', '160KiB']},
        'source': 'Existing immutable projections.json and A12 packets; reuse original project_packet with CAP changed only in memory.',
        'fixed': ['saved source-validated fact unit payloads and dependencies', 'Dense and BM25 candidates, scores, RRF order',
                  'selected top12', 'actual original document membership and omissions', 'first physical-table owner',
                  'original query, report_scope, source IDs, text, context and doc order',
                  'source row/column unit order', 'atomic unit admission, skip oversized unit and continue'],
        'not_permitted': ['new projections', 'unselected or originally omitted doc refill', 'query-specific prioritization',
                          'context rewriting', 'source changes', 'new answer generation', 'runtime/store/env edits'],
        'evaluation': ['64KiB exact packet and full decision replay against saved FCT12 for all77',
                       'full77 original fields and candidate/order hashes unchanged',
                       'physical unit identities and payloads added/lost/changed between caps',
                       'independent original XML and saved witness checks for delivered units',
                       'unchanged mandatory-evidence criteria, current4, legacy26 and19axis-watch',
                       'Motional closing ownership and carrying amount separate from full profit-summary requirement'],
        'criterion_precedence': 'Copied evaluation_contract/supplement govern fact requirements. Their historical 65536-byte cap is superseded only for160KiB; no other criterion changes.',
        'limits': {'external_API_calls': 0, 'cost_usd': 0, 'scored_runs': 1, 'run_timeout_seconds': 1800,
                   'store_or_SQLite_client': False, 'app_restart': False, 'network': 'blocked by imported frozen runner'},
        'interpretation': ['Development-exposed deterministic delivery comparison, not independent generalization.',
                           'Physical source linkage is not semantic entity/period/unit correctness.',
                           'No answer accuracy, faithfulness, refusal or model latency/cost measurement.',
                           'Larger budget is not assumed to retain all smaller-budget units.'],
        'preservation': {'write_scope': str(OUT.relative_to(ROOT)), 'protected_files': len(files),
                         'prior_artifacts_immutable': True, 'HEAD_index_status_unchanged': True},
        'stop_after': 'Two fixed caps, review and report only. No production adoption or further variant.'})
    beat('snapshot_and_protocol', protected_files=len(files))


def prepare():
    assert not (OUT / 'freeze.json').exists()
    old_results = load(OLD / 'results.json')
    assert len(old_results) == len({r['case_id'] for r in old_results}) == 77
    assert load(OUT / 'protocol.json')['only_treatment']['context_cap_UTF8_bytes'] == list(CAPS)
    for name in ('evaluation_contract.json', 'evaluation_supplement.json'):
        assert sha(OUT / name) == sha(OLD / name)
    deps = [OLD / n for n in ('run.py', 'projector.py', 'projections.json', 'results.json',
                             'input_checks.json', 'source_checks.json', 'postrun_required_fact_review.json',
                             'postrun_axis_review.json', 'postrun_boundary_review.json', 'all77_evidence_review.json')]
    for row in old_results:
        deps.extend(OLD / f'packets/{row["case_id"]}_{arm}.json' for arm in ('A12', 'FCT12'))
    deps.extend(ROOT / r['path'] for r in load(OLD / 'source_checks.json').values())
    for name in ('panel.json', 'requests.json'):
        deps.append(OUT.parent / 'full77_sol_top12_20261020' / name)
    deps.append(OUT.parent / 'tokenizer_nori_idf_offline_20261022/results.json')
    save('freeze.json', {
        'files': {n: sha(OUT / n) for n in ('compare.py', 'launch.py', 'protocol.json',
                                           'evaluation_contract.json', 'evaluation_supplement.json', 'before.json')},
        'dependencies': {str(p.relative_to(ROOT)).replace('\\', '/'): sha(p) for p in deps},
        'at': time.time(), 'scored_runs': 1, 'source_unit_regeneration': False})
    beat('frozen', cases=77, dependencies=len(deps))


def frozen():
    f = load(OUT / 'freeze.json')
    for n, h in f['files'].items():
        assert sha(OUT / n) == h, ('frozen file changed', n)
    for n, h in f['dependencies'].items():
        assert sha(ROOT / n) == h, ('frozen dependency changed', n)


def inventory(decisions, projections):
    result = {}
    for decision in decisions:
        projection = projections[decision['uid']]['projection']
        if not projection or 'units' not in decision:
            continue
        units = {u['unit_id']: u for u in projection['units']}
        for record in decision['units']:
            if record['status'] == 'attached':
                key = decision['uid'] + '|' + record['unit_id']
                assert key not in result
                result[key] = units[record['unit_id']]
    return result


def execute():
    frozen()
    assert not (OUT / 'started.json').exists(), 'One scored run; no automatic retry'
    save('started.json', {'at': time.time(), 'external_calls': 0})
    spec = importlib.util.spec_from_file_location('frozen_saved_fact_assembler', OLD / 'run.py')
    assembler = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(assembler)
    projections = load(OLD / 'projections.json')
    old_results = load(OLD / 'results.json')
    input_checks = {r['case_id']: r for r in load(OLD / 'input_checks.json')}
    rankings = {r['case_id']: r for r in load(OUT.parent / 'tokenizer_nori_idf_offline_20261022/results.json')}
    panel = {r['case_id']: r for r in load(OUT.parent / 'full77_sol_top12_20261020/panel.json')}
    requests = {r['case_id']: r for r in load(OUT.parent / 'full77_sol_top12_20261020/requests.json')}
    all_results = []
    for n, old in enumerate(old_results, 1):
        cid = old['case_id']
        baseline = load(OLD / f'packets/{cid}_A12.json')
        prev = input_checks[cid]
        rank = rankings[cid]
        assert baseline == panel[cid]['packet'] == json.loads(requests[cid]['body']['input'][1]['content'])
        assert assembler.digest(baseline) == old['baseline_packet_sha256'] == prev['baseline_packet_sha256']
        assert old['selected12'] == prev['selected12'] == [h['uid'] for h in rank['rrf']['A12'][:12]]
        assert len(old['selected12']) == 12
        assert assembler.digest({'dense': rank['dense'], 'lexical': rank['lexical']['A12'], 'rrf': rank['rrf']['A12']}) == old['candidate_order_score_sha256']
        assert [d['chunk_id'] for d in baseline['documents']] == old['delivered_ids']
        row = {k: copy.deepcopy(old[k]) for k in ('case_id', 'selected12', 'delivered_ids',
               'baseline_packet_sha256', 'baseline_bytes', 'candidate_order_score_sha256')}
        row['arms'] = {}
        inventories = {}
        for cap in CAPS:
            label = f'{cap // 1024}KiB'
            beat('case_started', case_id=cid, case_number=n, total=77, arm=label)
            assembler.CAP = cap
            packet, decisions = assembler.project_packet(baseline, projections)
            packet_sha = assembler.digest(packet)
            if cap == 65536:
                assert packet == load(OLD / f'packets/{cid}_FCT12.json')
                assert packet_sha == old['experimental_packet_sha256']
                assert decisions == old['decisions']
            arm = {'cap_bytes': cap, 'packet_bytes': len(assembler.encoded(packet).encode('utf-8')),
                   'packet_sha256': packet_sha, 'decisions': decisions,
                   'attached_units': sum(d.get('unit_count', 0) for d in decisions),
                   'attached_tables': sum(d['status'] == 'attached' for d in decisions),
                   'budget_rejected_units': sum(u['status'] == 'rejected_byte_budget' for d in decisions for u in d.get('units', [])),
                   'original_packet_preserved': True}
            row['arms'][label] = arm
            inventories[label] = inventory(decisions, projections)
            save(f'packets/{cid}_{label}.json', packet)
            beat('case_arm_completed', case_id=cid, case_number=n, arm=label,
                 bytes=arm['packet_bytes'], units=arm['attached_units'])
        a, b = inventories['64KiB'], inventories['160KiB']
        common = a.keys() & b.keys()
        assert all(a[k] == b[k] for k in common)
        row['unit_changes'] = {'retained': len(common), 'added': sorted(b.keys() - a.keys()),
                               'lost': sorted(a.keys() - b.keys()), 'changed_payloads': 0}
        row['baseline_64KiB_exact_replay'] = True
        all_results.append(row)
        save(f'cases/{cid}.json', row)
        if time.monotonic() - START > 1800:
            raise TimeoutError('Offline execution 30-minute cap exceeded')
    save('results.json', all_results)
    aggregate = {'cases': len(all_results), 'selected_documents': 77 * 12,
                 'actual_original_documents': sum(len(r['delivered_ids']) for r in all_results),
                 'exact64_replays': sum(r['baseline_64KiB_exact_replay'] for r in all_results),
                 'external_API_calls': 0, 'cost_usd': 0, 'source_unit_regeneration': False,
                 'elapsed_seconds': round(time.monotonic() - START, 2), 'arms': {}}
    for label in ('64KiB', '160KiB'):
        arms = [r['arms'][label] for r in all_results]
        sizes = [a['packet_bytes'] for a in arms]
        aggregate['arms'][label] = {'total_packet_bytes': sum(sizes), 'median_packet_bytes': statistics.median(sizes),
                                   'mean_packet_bytes': statistics.mean(sizes), 'max_packet_bytes': max(sizes),
                                   'attached_unit_events': sum(a['attached_units'] for a in arms),
                                   'attached_table_events': sum(a['attached_tables'] for a in arms),
                                   'budget_rejected_unit_events': sum(a['budget_rejected_units'] for a in arms),
                                   'cases_with_budget_rejections': sum(a['budget_rejected_units'] > 0 for a in arms)}
    aggregate['unit_changes'] = {'retained': sum(r['unit_changes']['retained'] for r in all_results),
                                 'added': sum(len(r['unit_changes']['added']) for r in all_results),
                                 'lost': sum(len(r['unit_changes']['lost']) for r in all_results),
                                 'cases_with_added': [r['case_id'] for r in all_results if r['unit_changes']['added']],
                                 'cases_with_lost': [r['case_id'] for r in all_results if r['unit_changes']['lost']],
                                 'changed_payloads': 0}
    save('aggregate_summary.json', aggregate)
    frozen()
    beat('completed', cases=77, exact64_replays=77, elapsed_seconds=round(time.monotonic() - START, 2))


def preservation():
    before = load(OUT / 'before.json')
    changed = [p for p, r in before['files'].items() if not (ROOT / p).is_file() or sha(ROOT / p) != r['sha256']]
    store_paths = [p for p in before['files'] if p.startswith('data/app_full11_2023_v12_20261017/')]
    result = {'protected_files': len(before['files']), 'changed': changed,
              'env_byte_identical': '.env' not in changed,
              'active_v12_store_files': len(store_paths), 'active_v12_store_byte_identical': not any(p in changed for p in store_paths),
              'head_unchanged': git('rev-parse', 'HEAD').decode().strip() == before['head'],
              'index_unchanged': sha(ROOT / '.git/index') == before['index'],
              'git_status_unchanged': git('status', '--porcelain=v1', '-uall') == (OUT / 'git_status_before.bin').read_bytes(),
              'external_API_calls': 0, 'store_or_SQLite_client_opened': False, 'app_restarts': 0,
              'source_unit_regeneration': False}
    assert not changed and all(result[k] for k in ('env_byte_identical', 'active_v12_store_byte_identical', 'head_unchanged', 'index_unchanged', 'git_status_unchanged'))
    save('preservation.json', result)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    {'setup': setup, 'prepare': prepare, 'run': execute, 'preserve': preservation}[sys.argv[1]]()
