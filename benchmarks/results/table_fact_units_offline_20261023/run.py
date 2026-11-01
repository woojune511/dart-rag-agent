"""Frozen offline fact-unit delivery; no provider, retrieval or store clients."""
from __future__ import annotations

import copy
import hashlib
import json
import socket
import subprocess
import sys
import time
from collections import Counter
from io import BytesIO
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
RESULTS = ROOT / 'benchmarks/results'
OLD = RESULTS / 'table_bundle_delivery_offline_20261022'
PANEL_PATH = RESULTS / 'full77_sol_top12_20261020/panel.json'
RANK_PATH = RESULTS / 'tokenizer_nori_idf_offline_20261022/results.json'
CAP = 65536
START = time.monotonic()
FIELD = 'table_fact_units'
WIRE_SCHEMA = {
    'cells': '[source_TR_index,source_start_column,rowspan,colspan,literal]; zero-based original physical origins',
    'units': '[expanded_row,column,value_cell_index,row_axis_cell_indices,column_prefix_cell_indices]; zero-based pool indices local to this table; expanded rows exclude all-empty source rows',
    'meaning': 'Located literal cell dependencies only; period, entity, scope and unit assignment remain unverified semantics',
}


def denied(*args, **kwargs):
    raise RuntimeError('Network and model/store calls prohibited in this offline experiment')


socket.create_connection = socket.socket.connect = socket.socket.connect_ex = socket.getaddrinfo = denied


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def encoded(obj):
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, allow_nan=False, separators=(',', ':'))


def digest(obj):
    return hashlib.sha256(encoded(obj).encode('utf-8')).hexdigest()


def file_sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda: f.read(4 * 1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def save(name, obj):
    path = (OUT / name).resolve()
    assert path.is_relative_to(OUT)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def heartbeat(phase, **values):
    row = {'phase': phase, 'elapsed_seconds': round(time.monotonic() - START, 2), **values}
    with (OUT / 'heartbeat.jsonl').open('a', encoding='utf-8') as f:
        f.write(encoded(row) + '\n')
    print(encoded(row), flush=True)
    if time.monotonic() - START > 1800:
        raise TimeoutError('30-minute offline execution cap exceeded')


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT)


def prepare():
    assert not (OUT / 'freeze.json').exists(), 'Protocol already frozen'
    synthetic = load(OUT / 'test_summary.json')
    assert synthetic['status'] == 'PASS' and synthetic['failed'] == synthetic['errors'] == 0
    assert synthetic['source_sha256'] == file_sha(OUT / 'projector.py')
    assert synthetic['test_sha256'] == file_sha(OUT / 'test_projector.py')
    runner = load(OUT / 'runner_synthetic_validation.json')
    assert runner['passed'] and runner['run_sha256'] == file_sha(OUT / 'run.py')
    assert runner['test_sha256'] == file_sha(OUT / 'test_runner.py')
    assert file_sha(OUT / 'evaluation_contract.json') == file_sha(OLD / 'evaluation_contract.json')
    previous = {r['case_id']: r for r in load(OLD / 'input_checks.json')}
    panel = load(PANEL_PATH)
    rankings = {r['case_id']: r for r in load(RANK_PATH)}
    requests = {r['case_id']: r for r in load(RESULTS / 'full77_sol_top12_20261020/requests.json')}
    checks = []
    for case in panel:
        cid, packet = case['case_id'], case['packet']
        rank = rankings[cid]
        prev = previous[cid]
        ids = [h['metadata']['chunk_uid'] for h in case['hits']]
        assert ids == prev['selected12'] == [h['uid'] for h in rank['rrf']['A12'][:12]]
        assert len(ids) == case['k'] == 12
        assert [d['chunk_id'] for d in packet['documents']] == prev['delivered_ids']
        assert digest(packet) == prev['baseline_packet_sha256']
        assert packet == load(OLD / f'packets/{cid}_A12.json')
        assert json.loads(requests[cid]['body']['input'][1]['content']) == packet
        assert packet['query'] == case['question'] == rank['query']
        assert packet['report_scope'] == case['report_scope'] == rank['report_scope']
        assert digest({'dense': rank['dense'], 'lexical': rank['lexical']['A12'], 'rrf': rank['rrf']['A12']}) == prev['candidate_order_score_sha256']
        assert len(encoded(packet).encode('utf-8')) == prev['baseline_bytes'] <= CAP
        for doc in packet['documents']:
            hit = next(h for h in case['hits'] if h['metadata']['chunk_uid'] == doc['chunk_id'])
            assert doc['text'] == hit['text']
            assert all(hit['metadata'].get(k) == v for k, v in doc['context'].items())
        checks.append(prev)
    assert len(checks) == len({r['case_id'] for r in checks}) == 77
    save('input_checks.json', checks)
    # Reuse byte-identical historical source-export parity; do not open the store.
    prior = load(OUT / 'before.json')['files']
    old_inputs = load(OLD / 'input_manifest.json')
    for i, (p, receipt) in enumerate(old_inputs.items(), 1):
        assert p in prior and file_sha(ROOT / p) == receipt['sha256'], ('input changed', p)
        if i % 500 == 0:
            heartbeat('input_hash_parity', completed=i, total=len(old_inputs))
    names = ['protocol.json', 'projector.py', 'test_projector.py', 'run.py', 'test_runner.py', 'launch.py',
             'evaluation_contract.json', 'evaluation_supplement.json', 'test_summary.json',
             'runner_synthetic_validation.json', 'input_checks.json', 'preflight_review.json']
    save('freeze.json', {'files': {n: file_sha(OUT / n) for n in names},
                        'dependencies': {str((OLD / 'projector.py').relative_to(ROOT)): file_sha(OLD / 'projector.py'),
                                         str(PANEL_PATH.relative_to(ROOT)): file_sha(PANEL_PATH),
                                         str(RANK_PATH.relative_to(ROOT)): file_sha(RANK_PATH)},
                        'all77_original_A12_parity': True,
                        'prior_source_export_parity_reused_after_input_hash_check': True,
                        'scored_run_limit': 1, 'at': time.time()})
    heartbeat('prepared', cases=77)


def assert_frozen():
    freeze = load(OUT / 'freeze.json')
    for name, sha in freeze['files'].items():
        assert file_sha(OUT / name) == sha, ('frozen file changed', name)
    for name, sha in freeze['dependencies'].items():
        assert file_sha(ROOT / name) == sha, ('frozen dependency changed', name)


def add_unit(wire, pool, projection, unit):
    """Return tentative complete dependencies; caller commits or discards all."""
    proposed = copy.deepcopy(wire)
    proposed_pool = dict(pool)

    def index(locator):
        if locator not in proposed_pool:
            proposed_pool[locator] = len(proposed['cells'])
            proposed['cells'].append(projection['cells'][locator])
        return proposed_pool[locator]

    # Stable first appearance: row axes, column prefix, then literal value.
    row = [index(loc) for loc in unit['row_axes']]
    col = [index(loc) for loc in unit['column_axes']]
    val = index(unit['value'])
    proposed['units'].append([*unit['at'], val, row, col])
    return proposed, proposed_pool


def project_packet(packet, projections):
    """Append source-order units from the original first physical-table owner."""
    out = copy.deepcopy(packet)
    current_size = len(encoded(out).encode('utf-8'))
    assert current_size <= CAP
    seen = set()
    decisions = []
    overhead = len((',' + encoded(FIELD) + ':').encode('utf-8'))
    for position, doc in enumerate(out['documents'], 1):
        uid = doc['chunk_id']
        item = projections[uid]
        key, projection = item['physical_key'], item['projection']
        decision = {'uid': uid, 'position': position, 'physical_key': key}
        if key is None:
            decision.update(status='no_table_payload', reason=item['receipt'].get('reason'))
        elif key in seen:
            decision.update(status='duplicate_table_first_owner_only')
        else:
            seen.add(key)
            if projection is None:
                status = ('no_valid_numeric_units' if item['receipt'].get('status') == 'NO_UNITS'
                          else 'rejected_global_validation')
                decision.update(status=status, reason=item['receipt'].get('reason'))
            elif not projection['units']:
                decision.update(status='no_valid_numeric_units', reason=item['receipt'].get('reason'))
            else:
                frame = copy.deepcopy(projection['frame'])
                frame.update(source_id=doc['source_id'], schema=WIRE_SCHEMA)
                wire = {**frame, 'cells': [], 'units': []}
                pool, prior_wire_size, records = {}, 0, []
                for unit in projection['units']:
                    proposed, next_pool = add_unit(wire, pool, projection, unit)
                    new_size = len(encoded(proposed).encode('utf-8'))
                    addition = new_size - prior_wire_size + (overhead if not wire['units'] else 0)
                    record = {'unit_id': unit['unit_id'], 'at': unit['at'],
                              'proposed_packet_bytes': current_size + addition,
                              'incremental_bytes': addition}
                    if current_size + addition <= CAP:
                        wire, pool = proposed, next_pool
                        current_size += addition
                        prior_wire_size = new_size
                        record.update(status='attached', wire_unit_index=len(wire['units']) - 1)
                    else:
                        record.update(status='rejected_byte_budget')
                    records.append(record)
                decision['units'] = records
                if wire['units']:
                    doc[FIELD] = wire
                    decision.update(status='attached', unit_count=len(wire['units']),
                                    unique_physical_cells=len(wire['cells']),
                                    cell_pool_locators=list(pool),
                                    packet_bytes_after=current_size, projection_sha256=digest(wire))
                else:
                    decision.update(status='rejected_byte_budget', unit_count=0)
        decisions.append(decision)
    assert len(encoded(out).encode('utf-8')) == current_size <= CAP
    assert [d['chunk_id'] for d in out['documents']] == [d['chunk_id'] for d in packet['documents']]
    for original, changed in zip(packet['documents'], out['documents']):
        assert all(changed[k] == v for k, v in original.items())
        assert set(changed) - set(original) <= {FIELD}
    assert {k: v for k, v in out.items() if k != 'documents'} == {k: v for k, v in packet.items() if k != 'documents'}
    return out, decisions


def run():
    assert_frozen()
    assert not (OUT / 'run_started.json').exists(), 'One scored run only; no automatic rerun'
    save('run_started.json', {'at': time.time(), 'mode': 'offline', 'model_calls': 0})
    sys.path.insert(0, str(ROOT))
    from lxml import etree
    from src.processing.financial_parser import _sanitize_xml_like_text
    from projector import build_units
    panel = load(PANEL_PATH)
    prep = load(RESULTS / 'full77_v12_final_20261018/preparation.json')
    previous_sources = load(OLD / 'source_checks.json')
    trees, hashes, source_checks = {}, {}, {}
    for report in prep['reports']:
        receipt = report['metadata']['rcept_no']
        path = ROOT / report['path']
        hashes[receipt] = file_sha(path)
        assert hashes[receipt] == previous_sources[receipt]['sha256']
        raw = path.read_text(encoding='utf-8')
        clean, edits = _sanitize_xml_like_text(raw)
        parser = etree.XMLParser(no_network=True, resolve_entities=False, recover=False, huge_tree=True)
        trees[receipt] = etree.parse(BytesIO(clean.encode('utf-8')), parser)
        assert not len(parser.error_log)
        source_checks[receipt] = {'path': str(path.relative_to(ROOT)), 'sha256': hashes[receipt],
                                  'sanitizer_changes_in_memory': edits, 'strict_parse_errors': 0}
        heartbeat('source_tree', receipt=receipt, completed=len(trees))
    save('source_checks.json', source_checks)
    projections = {}
    for case in panel:
        visible = {d['chunk_id'] for d in case['packet']['documents']}
        for hit in case['hits']:
            meta = hit['metadata']
            uid = meta['chunk_uid']
            if uid not in visible or uid in projections:
                continue
            obj = json.loads(meta.get('table_object_json') or '{}')
            key = (obj.get('source_document_sha256', '') + '|' + obj.get('source_table_locator', '')) if obj else None
            projection, receipt = build_units(meta, trees[meta['rcept_no']], hashes[meta['rcept_no']])
            projections[uid] = {'physical_key': key, 'projection': projection, 'receipt': receipt}
            if len(projections) % 50 == 0:
                heartbeat('validate_units', unique_docs=len(projections),
                          valid_units=sum(len(x['projection']['units']) for x in projections.values() if x['projection']))
    save('projections.json', projections)
    result = []
    checks = {r['case_id']: r for r in load(OUT / 'input_checks.json')}
    old_results = {r['case_id']: r for r in load(OLD / 'results.json')}
    for ordinal, case in enumerate(panel, 1):
        cid, baseline = case['case_id'], case['packet']
        changed, decisions = project_packet(baseline, projections)
        save(f'packets/{cid}_A12.json', baseline)
        save(f'packets/{cid}_FCT12.json', changed)
        result.append({**checks[cid], 'decisions': decisions,
                       'experimental_packet_sha256': digest(changed),
                       'experimental_bytes': len(encoded(changed).encode('utf-8')),
                       'prior_T12_bytes': old_results[cid]['experimental_bytes'],
                       'original_documents_text_context_ids_order_identical': True,
                       'attached_tables': sum(d['status'] == 'attached' for d in decisions),
                       'attached_units': sum(d.get('unit_count', 0) for d in decisions)})
        heartbeat('case_completed', case=ordinal, total=77, case_id=cid,
                  units=result[-1]['attached_units'], original_bytes=result[-1]['baseline_bytes'],
                  new_bytes=result[-1]['experimental_bytes'])
    save('results.json', result)
    save('execution_result.json', {'status': 'completed', 'elapsed_seconds': round(time.monotonic() - START, 2),
                                 'cases': len(result), 'new_model_api_calls': 0, 'new_retrieval_runs': 0,
                                 'new_answers': 0, 'cost_usd': 0, 'new_runtime_features': 0,
                                 'table_decisions': dict(Counter(d['status'] for r in result for d in r['decisions'])),
                                 'unit_decisions': dict(Counter(u['status'] for r in result for d in r['decisions'] for u in d.get('units', [])))})
    assert_frozen()
    heartbeat('completed', cases=len(result))


def preserve():
    before = load(OUT / 'before.json')
    changed = [p for p, old in before['files'].items() if not (ROOT / p).is_file()
               or file_sha(ROOT / p) != old['sha256'] or (ROOT / p).stat().st_size != old['bytes']]
    status_same = git('status', '--porcelain=v1', '-uall') == (OUT / 'git_status_before.bin').read_bytes()
    result = {'protected_files': len(before['files']), 'changed': changed,
              'env_unchanged': file_sha(ROOT / '.env') == before['files']['.env']['sha256'],
              'active_store_files': sum('app_full11_2023_v12_20261017' in p for p in before['files']),
              'head_unchanged': git('rev-parse', 'HEAD').decode().strip() == before['head'],
              'index_unchanged': file_sha(ROOT / '.git/index') == before['index'],
              'git_status_unchanged': status_same, 'store_or_sqlite_opened': False, 'app_restarts': 0}
    save('preservation.json', result)
    assert not changed and all(result[k] for k in ('env_unchanged', 'head_unchanged', 'index_unchanged', 'git_status_unchanged'))
    heartbeat('preserved', protected_files=len(before['files']))


if __name__ == '__main__':
    {'prepare': prepare, 'run': run, 'preserve': preserve}[sys.argv[1]]()
