"""One frozen offline packet-projection experiment; never import a model/store client."""
from __future__ import annotations

import copy
import gzip
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
PANEL_PATH = RESULTS / 'full77_sol_top12_20261020/panel.json'
RANK_PATH = RESULTS / 'tokenizer_nori_idf_offline_20261022/results.json'
SOURCE_EXPORT = RESULTS / 'v12_store_recovery_preparation_2026-10-17'
CAP = 65536
START = time.monotonic()


def denied(*args, **kwargs):
    raise RuntimeError('This experiment prohibits network and model/store calls')


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


def snapshot_inputs():
    previous = load(RESULTS / 'table_fact_identifiability_audit_20261022/input_manifest.json')
    paths = {ROOT / p for p in previous}
    paths |= {p for p in (RESULTS / 'table_fact_identifiability_audit_20261022').rglob('*') if p.is_file()}
    paths |= {PANEL_PATH, RANK_PATH, RESULTS / 'full77_v12_final_20261018/preparation.json'}
    manifest = {}
    for index, path in enumerate(sorted(paths), 1):
        manifest[str(path.relative_to(ROOT))] = {'sha256': file_sha(path), 'bytes': path.stat().st_size}
        if index % 500 == 0:
            heartbeat('snapshot_inputs', completed=index, total=len(paths))
    save('input_manifest.json', manifest)


def prepare():
    assert not (OUT / 'freeze.json').exists(), 'Protocol was already frozen'
    assert (OUT / 'projector.py').exists() and (OUT / 'evaluation_contract.json').exists()
    synthetic = load(OUT / 'test_summary.json')
    assert synthetic['status'] == 'PASS' and synthetic['failed'] == synthetic['errors'] == 0
    assert synthetic['source_sha256'] == file_sha(OUT / 'projector.py')
    assert synthetic['test_sha256'] == file_sha(OUT / 'test_projector.py')
    assert load(OUT / 'runner_synthetic_validation.json')['passed'] is True
    snapshot_inputs()
    panel = load(PANEL_PATH)
    rankings = {r['case_id']: r for r in load(RANK_PATH)}
    requests = {r['case_id']: r for r in load(RESULTS / 'full77_sol_top12_20261020/requests.json')}
    ids = set()
    needed = {}
    input_checks = []
    for case in panel:
        cid = case['case_id']
        assert cid not in ids
        ids.add(cid)
        rank = rankings[cid]
        packet = case['packet']
        hit_uids = [h['metadata']['chunk_uid'] for h in case['hits']]
        assert len(hit_uids) == 12 == case['k']
        assert hit_uids == [h['uid'] for h in rank['rrf']['A12'][:12]]
        assert packet['query'] == rank['query'] == case['question']
        assert packet['report_scope'] == rank['report_scope'] == case['report_scope']
        assert [d['chunk_id'] for d in packet['documents']] == rank['packets']['A12']['uids']
        assert len(encoded(packet).encode('utf-8')) == rank['packets']['A12']['bytes'] <= CAP
        assert json.loads(requests[cid]['body']['input'][1]['content']) == packet
        for doc in packet['documents']:
            hit = next(h for h in case['hits'] if h['metadata']['chunk_uid'] == doc['chunk_id'])
            assert doc['text'] == hit['text']
            assert all(hit['metadata'].get(k) == v for k, v in doc['context'].items())
            needed.setdefault(doc['chunk_id'], []).append(hit)
        input_checks.append({'case_id': cid, 'selected12': hit_uids,
            'delivered_ids': [d['chunk_id'] for d in packet['documents']],
            'baseline_packet_sha256': digest(packet), 'baseline_bytes': len(encoded(packet).encode('utf-8')),
            'candidate_order_score_sha256': digest({'dense': rank['dense'], 'lexical': rank['lexical']['A12'], 'rrf': rank['rrf']['A12']})})
    assert len(ids) == 77
    matched = set()
    export_edge_whitespace = set()
    for path in sorted(SOURCE_EXPORT.glob('*.jsonl.gz')):
        with gzip.open(path, 'rt', encoding='utf-8') as f:
            for line in f:
                row = json.loads(line)
                uid = row['metadata']['chunk_uid']
                if uid not in needed:
                    continue
                assert hashlib.sha256(row['text'].encode()).hexdigest() == row['text_sha256']
                for hit in needed[uid]:
                    # The historical BM25 graph path strips document-edge whitespace.
                    # Preserve the saved A12 hit/packet verbatim; never normalize it here.
                    assert row['text'] == hit['text'] or row['text'].strip() == hit['text'], ('export text mismatch', uid)
                    if row['text'] != hit['text']:
                        export_edge_whitespace.add(uid)
                    assert json.loads(row['metadata'].get('table_object_json') or '{}') == json.loads(hit['metadata'].get('table_object_json') or '{}'), ('export table mismatch', uid)
                matched.add(uid)
        heartbeat('verify_export_parity', receipt=path.stem, matched=len(matched), needed=len(needed))
    assert matched == set(needed)
    save('input_checks.json', input_checks)
    freeze_names = ['protocol.json', 'projector.py', 'test_projector.py', 'run.py', 'test_runner.py', 'launch.py',
                    'evaluation_contract.json', 'test_summary.json', 'runner_synthetic_validation.json', 'input_checks.json']
    save('freeze.json', {'files': {n: file_sha(OUT / n) for n in freeze_names},
        'all77_saved_packet_parity': True, 'source_export_parity_unique_docs': len(matched),
        'historical_export_edge_whitespace_only': sorted(export_edge_whitespace),
        'scored_run_limit': 1, 'timestamp': time.time()})
    heartbeat('prepared', cases=77, unique_source_docs=len(matched), baseline_byte_omission_cases=sum(len(c['packet']['documents']) < 12 for c in panel))


def assert_frozen():
    freeze = load(OUT / 'freeze.json')
    for name, sha in freeze['files'].items():
        assert file_sha(OUT / name) == sha, ('frozen file changed', name)


def project_packet(packet, hits, bundles):
    """Append complete, first-owner tables only; no truncation, refill or query use."""
    out = copy.deepcopy(packet)
    seen = set()
    decisions = []
    for index, doc in enumerate(out['documents']):
        uid = doc['chunk_id']
        item = bundles[uid]
        key = item['physical_key']
        decision = {'uid': uid, 'position': index + 1, 'physical_key': key}
        if key is None:
            decision.update(status='no_table_payload', reason=item['receipt'].get('reason'))
        elif key in seen:
            decision.update(status='duplicate_table_first_owner_only')
        else:
            seen.add(key)
            if item['bundle'] is None:
                decision.update(status='rejected_structural_validation', reason=item['receipt'].get('reason'))
            else:
                proposed = copy.deepcopy(out)
                proposed['documents'][index]['table_evidence'] = item['bundle']
                size = len(encoded(proposed).encode('utf-8'))
                if size <= CAP:
                    out = proposed
                    decision.update(status='attached', packet_bytes_after=size, bundle_sha256=digest(item['bundle']))
                else:
                    decision.update(status='rejected_byte_budget', proposed_bytes=size,
                        available_bytes=CAP-len(encoded(out).encode('utf-8')))
        decisions.append(decision)
    # Physical preservation checks do not establish model reading or answer quality.
    assert [d['chunk_id'] for d in out['documents']] == [d['chunk_id'] for d in packet['documents']]
    assert out['query'] == packet['query'] and out['report_scope'] == packet['report_scope']
    for original, changed in zip(packet['documents'], out['documents']):
        assert all(changed[k] == v for k, v in original.items())
        assert set(changed) - set(original) <= {'table_evidence'}
    assert len(encoded(out).encode('utf-8')) <= CAP
    return out, decisions


def run():
    assert_frozen()
    assert not (OUT / 'run_started.json').exists(), 'One scored run only; no automatic rerun'
    save('run_started.json', {'at': time.time(), 'mode': 'offline', 'model_calls': 0})
    sys.path.insert(0, str(ROOT))
    from lxml import etree
    from src.processing.financial_parser import _sanitize_xml_like_text
    from projector import build_bundle
    panel = load(PANEL_PATH)
    source_prep = load(RESULTS / 'full77_v12_final_20261018/preparation.json')
    trees, hashes, source_checks = {}, {}, {}
    for report in source_prep['reports']:
        receipt = report['metadata']['rcept_no']
        path = ROOT / report['path']
        raw = path.read_text(encoding='utf-8')
        text, edits = _sanitize_xml_like_text(raw)
        parser = etree.XMLParser(no_network=True, resolve_entities=False, recover=False, huge_tree=True)
        trees[receipt] = etree.parse(BytesIO(text.encode('utf-8')), parser)
        hashes[receipt] = file_sha(path)
        assert not len(parser.error_log)
        source_checks[receipt] = {'path': str(path.relative_to(ROOT)), 'sha256': hashes[receipt],
            'sanitizer_changes_in_memory': edits, 'strict_parse_errors': 0}
        heartbeat('source_tree', receipt=receipt, completed=len(trees))
    save('source_checks.json', source_checks)
    bundles = {}
    for case in panel:
        visible = {d['chunk_id'] for d in case['packet']['documents']}
        for hit in case['hits']:
            meta = hit['metadata']
            uid = meta['chunk_uid']
            if uid not in visible or uid in bundles:
                continue
            obj = json.loads(meta.get('table_object_json') or '{}')
            key = (obj.get('source_document_sha256', '') + '|' + obj.get('source_table_locator', '')) if obj else None
            bundle, receipt = build_bundle(meta, trees[meta['rcept_no']], hashes[meta['rcept_no']])
            bundles[uid] = {'physical_key': key, 'bundle': bundle, 'receipt': receipt}
            if len(bundles) % 50 == 0:
                heartbeat('project_structures', unique_docs=len(bundles), admitted=sum(x['bundle'] is not None for x in bundles.values()))
    save('bundles.json', bundles)
    result = []
    rank_input = {c['case_id']: c for c in load(OUT / 'input_checks.json')}
    for ordinal, case in enumerate(panel, 1):
        baseline = case['packet']
        changed, decisions = project_packet(baseline, case['hits'], bundles)
        # A pure repeated serialization check, not a second experimental condition.
        repeated, repeated_decisions = project_packet(baseline, case['hits'], bundles)
        assert changed == repeated and decisions == repeated_decisions
        cid = case['case_id']
        save(f'packets/{cid}_A12.json', baseline)
        save(f'packets/{cid}_T12.json', changed)
        result.append({**rank_input[cid], 'decisions': decisions,
            'experimental_packet_sha256': digest(changed),
            'experimental_bytes': len(encoded(changed).encode('utf-8')),
            'original_documents_text_context_ids_order_identical': True,
            'deterministic_projection_repeat_identical': True,
            'attached_tables': sum(d['status'] == 'attached' for d in decisions)})
        heartbeat('case_completed', case=ordinal, total=77, case_id=cid,
            attached_tables=result[-1]['attached_tables'], original_bytes=result[-1]['baseline_bytes'], new_bytes=result[-1]['experimental_bytes'])
    save('results.json', result)
    save('execution_result.json', {'status': 'completed', 'elapsed_seconds': round(time.monotonic() - START, 2),
        'cases': len(result), 'new_model_api_calls': 0, 'new_retrieval_runs': 0, 'new_answers': 0,
        'cost_usd': 0, 'new_runtime_features': 0,
        'case_decisions': dict(Counter(d['status'] for r in result for d in r['decisions'])),
        'projector_outcomes_unique_docs': dict(Counter(x['receipt'].get('reason', 'accepted') for x in bundles.values()))})
    assert_frozen()
    heartbeat('completed', cases=len(result))


def preserve():
    b = load(OUT / 'before.json')
    protected = dict(b['files'])
    protected.update(load(OUT / 'input_manifest.json'))
    changed = [p for p, old in protected.items() if not (ROOT / p).is_file()
               or file_sha(ROOT / p) != old['sha256'] or (ROOT / p).stat().st_size != old['bytes']]
    status_same = git('status', '--porcelain=v1', '-uall') == (OUT / 'git_status_before.bin').read_bytes()
    result = {'protected_files': len(protected), 'changed': changed,
        'env_unchanged': file_sha(ROOT / '.env') == b['files']['.env']['sha256'],
        'active_store_files': sum('app_full11_2023_v12_20261017' in p for p in b['files']),
        'head_unchanged': git('rev-parse', 'HEAD').decode().strip() == b['head'],
        'index_unchanged': file_sha(ROOT / '.git/index') == b['index'],
        'git_status_unchanged': status_same,
        'store_or_sqlite_opened': False, 'app_restarts': 0}
    save('preservation.json', result)
    assert not changed and all(result[k] for k in ('env_unchanged', 'head_unchanged', 'index_unchanged', 'git_status_unchanged'))
    heartbeat('preserved', protected_files=len(protected))


if __name__ == '__main__':
    {'prepare': prepare, 'run': run, 'preserve': preserve}[sys.argv[1]]()
