"""Offline preparation only. Does not contain a provider or store execution path.

Artifacts stay in this ignored experiment directory. Existing runtime and saved
inputs are read only. Native packet assembly is exercised with both the retrieval
and generation boundary replaced by recorders, never a persistent store/client.
"""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import math
import os
import socket
import sys
import time
from collections import Counter
from contextlib import ExitStack
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
RESULTS = OUT.parent
OLD77 = RESULTS / 'table_fact_units_offline_20261023'
BUDGET77 = RESULTS / 'table_fact_budget77_offline_20261023'
PREP18 = RESULTS / 'table_fact_holdout18_preparation_20261023'
EXEC18 = PREP18 / 'execution'
sys.path.insert(0, str(ROOT))
os.environ['ANONYMIZED_TELEMETRY'] = 'False'
START = time.monotonic()
INPUTS = {}
DENIED_NETWORK_ATTEMPTS = []


def denied(*args, **kwargs):
    DENIED_NETWORK_ATTEMPTS.append('network boundary reached')
    raise RuntimeError('Provider, network and live retrieval calls are forbidden')


socket.create_connection = socket.getaddrinfo = denied
socket.socket.connect = socket.socket.connect_ex = denied


def enc(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False,
                      separators=(',', ':')).encode('utf8')


def digest(value):
    return hashlib.sha256(enc(value)).hexdigest()


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for part in iter(lambda: stream.read(4 * 1024 * 1024), b''):
            h.update(part)
    return h.hexdigest()


def remember(path):
    path = Path(path).resolve()
    assert path.is_relative_to(ROOT)
    key = path.relative_to(ROOT).as_posix()
    h = sha(path)
    assert key not in INPUTS or INPUTS[key] == h, ('Input changed during preparation', key)
    INPUTS[key] = h
    return path


def load(path):
    return json.loads(remember(path).read_text(encoding='utf8'))


def put(name, value):
    path = (OUT / name).resolve()
    assert path.is_relative_to(OUT), 'Writes are limited to the new experiment directory'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf8')


def heartbeat(stage, **counts):
    record = {'stage': stage, 'elapsed_seconds': round(time.monotonic() - START, 2), **counts}
    with (OUT / 'heartbeat.jsonl').open('a', encoding='utf8') as stream:
        stream.write(enc(record).decode('utf8') + '\n')
    print(enc(record).decode('utf8'), flush=True)
    assert time.monotonic() - START < 1800, 'Offline preparation time limit reached'


def module(path, name):
    path = remember(path)
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    sys.modules[name] = result
    spec.loader.exec_module(result)
    return result


def packet_from_native(case, hits, k, *, historical_fields=None):
    from src.agent.simple_rag import SimpleRagAgent
    calls = {'saved_retrieval': 0, 'capture': 0}

    class SavedStore:
        last_search_telemetry = {'retrieval_mode': 'hybrid'}
        _caption_links = {}

        def search(self, query, **kwargs):
            assert query == case['question'] and kwargs['k'] == k
            assert kwargs['where_filter'] == case['report_scope']
            calls['saved_retrieval'] += 1
            return hits

    class Recorder:
        packet = None

        def with_structured_output(self, schema):
            return self

        def invoke(self, messages):
            from src.config.simple_rag import ANSWER_INSTRUCTIONS
            assert messages[0][1] == ANSWER_INSTRUCTIONS
            self.packet = json.loads(messages[1][1])
            calls['capture'] += 1
            return {'answer': 'offline capture fixture', 'abstained': True, 'cited_source_ids': []}

    recorder = Recorder()
    with ExitStack() as stack:
        stack.enter_context(patch.object(SimpleRagAgent, '_build_llm_routes', lambda self: {'default': recorder}))
        if historical_fields is not None:
            stack.enter_context(patch('src.agent.simple_rag.SOURCE_CONTEXT_FIELDS', historical_fields))
        agent = SimpleRagAgent(SavedStore(), k=k, max_context_bytes=65536)
        result = agent.run(case['question'], report_scope=case['report_scope'],
                           include_debug_bundle=True, include_review_trace=True)
    assert recorder.packet is not None and calls == {'saved_retrieval': 1, 'capture': 1}
    return recorder.packet, result.to_projection()


def unit_map(packet, decisions, projections):
    """Decode and check every emitted binding, including frame and source owner."""
    by_uid = {d['uid']: d for d in decisions}
    result = {}
    for doc in packet['documents']:
        uid = doc['chunk_id']
        wire = doc.get('table_fact_units')
        if not wire:
            continue
        decision = by_uid[uid]
        projection = projections[uid]['projection']
        pool = decision['cell_pool_locators']
        assert len(pool) == len(set(pool)) == len(wire['cells'])
        assert wire['source_id'] == doc['source_id']
        frame = {k: v for k, v in wire.items() if k not in ('cells', 'units', 'source_id', 'schema')}
        assert frame == projection['frame']
        assert wire['schema'] == ASSEMBLER.WIRE_SCHEMA
        for locator, value in zip(pool, wire['cells']):
            assert projection['cells'][locator] == value, ('Cell literal/geometry changed', uid, locator)
        attached = {u['wire_unit_index']: u for u in decision['units'] if u['status'] == 'attached'}
        assert len(attached) == len(wire['units'])
        original = {u['unit_id']: u for u in projection['units']}
        for i, (row, col, value, row_axes, column_axes) in enumerate(wire['units']):
            record = attached[i]
            item = original[record['unit_id']]
            assert [row, col] == item['at'] == record['at']
            assert pool[value] == item['value']
            assert [pool[j] for j in row_axes] == item['row_axes']
            assert [pool[j] for j in column_axes] == item['column_axes']
            key = uid + '|' + item['unit_id']
            assert key not in result
            result[key] = {
                'chunk_uid': uid, 'unit_id': item['unit_id'], 'at': [row, col],
                'value': {'locator': pool[value], 'cell': wire['cells'][value]},
                'row_axes': [{'locator': pool[j], 'cell': wire['cells'][j]} for j in row_axes],
                'column_axes': [{'locator': pool[j], 'cell': wire['cells'][j]} for j in column_axes],
                'frame_sha256': digest(frame), 'source_id': doc['source_id'],
            }
    return result


def remove_facts(packet):
    result = copy.deepcopy(packet)
    for doc in result['documents']:
        doc.pop('table_fact_units', None)
    return result


def frozen_rrf(dense, lexical, selected):
    from src.storage.search_merge import merge_rrf_results

    def pair(row):
        uid = row.get('uid') or row['metadata']['chunk_uid']
        return SimpleNamespace(metadata={'chunk_uid': uid}, page_content=''), row['score']

    assert len(dense) == 16 and len(lexical) <= 24
    merged = merge_rrf_results([pair(r) for r in dense], [pair(r) for r in lexical], k=12, k_rrf=60)
    expected = [(r.get('uid') or r['metadata']['chunk_uid'], r['score']) for r in selected]
    actual = [(doc.metadata['chunk_uid'], score) for doc, score in merged]
    assert actual == expected[:12], 'Saved current RRF order or scores not reproduced'
    actual8 = merge_rrf_results([pair(r) for r in dense], [pair(r) for r in lexical], k=8, k_rrf=60)
    assert [(d.metadata['chunk_uid'], s) for d, s in actual8] == actual[:8]
    return actual


def preserve_sources(projections, source_checks):
    expected = {sha_: record for sha_, record in source_checks.items()}
    for item in projections.values():
        p = item.get('projection')
        if not p:
            continue
        frame = p['frame']
        assert frame['document_sha256'] in expected, 'Projection source hash lacks a matching saved source'
        assert item['physical_key'] == frame['document_sha256'] + '|' + frame['table_locator']


def main():
    global ASSEMBLER
    assert not (OUT / 'preparation_result.json').exists(), 'This preparation has already completed'
    ASSEMBLER = module(OLD77 / 'run.py', 'frozen_fact_assembler_top8')
    # Restore counting deny boundary after importing the frozen offline helper.
    socket.create_connection = socket.getaddrinfo = denied
    socket.socket.connect = socket.socket.connect_ex = denied
    ASSEMBLER.CAP = 163840  # In-memory configuration only; old helper is not edited.
    from langchain_core.documents import Document
    from src.config.simple_rag import ANSWER_INSTRUCTIONS, SOURCE_CONTEXT_FIELDS, RagAnswer
    for filename in ('src/agent/simple_rag.py', 'src/config/simple_rag.py', 'src/config/llm_profiles.py',
                     'src/storage/search_merge.py', 'src/api/services.py'):
        remember(ROOT / filename)
    panel77 = load(RESULTS / 'full77_sol_top12_20261020/panel.json')
    ranks77 = {x['case_id']: x for x in load(RESULTS / 'tokenizer_nori_idf_offline_20261022/results.json')}
    projections77 = load(OLD77 / 'projections.json')
    results77 = {r['case_id']: r for r in load(BUDGET77 / 'results.json')}
    questions18 = load(PREP18 / 'questions.json')
    projections18 = load(EXEC18 / 'projections.json')
    protocol18 = load(PREP18 / 'protocol.json')
    rubric18 = load(PREP18 / 'rubric.json')
    sources = {}
    for rid, source in load(OLD77 / 'source_checks.json').items():
        p = remember(ROOT / source['path'])
        assert sha(p) == source['sha256']
        sources[source['sha256']] = {'receipt': rid, 'path': p.relative_to(ROOT).as_posix(), 'sha256': sha(p)}
    for rid in sorted({q['receipt'] for q in questions18}):
        p = remember(PREP18 / 'sources' / rid / 'original.xml')
        sources[sha(p)] = {'receipt': rid, 'path': p.relative_to(ROOT).as_posix(), 'sha256': sha(p)}
    assert len(sources) == 14
    preserve_sources(projections77, sources)
    preserve_sources(projections18, sources)
    put('source_checks.json', {'original_files_hash_checked': list(sources.values()),
                              'projection_validation': 'Reuse existing validated projections only, after source hash parity; no semantic inference',
                              'store_client_opened': False})
    template = copy.deepcopy(protocol18['fixed_generation'])
    assert template['input'][0]['content'] == ANSWER_INSTRUCTIONS
    assert template['text']['format']['schema'] == RagAnswer.model_json_schema()
    assert template['reasoning'] == {'effort': 'low'} and template['max_output_tokens'] == 8192
    template['model'] = 'gpt-5.6-terra'
    put('rubric18.json', rubric18)
    put('protocol.json', {
        'status': 'PROVIDER_FREE_INPUT_PREPARATION_ONLY', 'created_at': datetime.now(timezone.utc).isoformat(),
        'authorization': 'User approved the recommended phase 1: offline input preparation and future cost/call plan. No paid generation execution authorized in this phase.',
        'cohorts': {'development77': 77, 'exposed_transfer18': 18},
        'future_generation_panel': 'Previously evaluated 18; exposed transfer/regression panel, not a new held-out set',
        'retrieval': {'mode': 'saved_candidate_replay', 'dense_count': 16, 'lexical_max_count': 24,
                      'rrf_k': 60, 'selected_k': 8, 'same_scores_and_tie_order': True,
                      'query_reformulation': False, 'nori_experiment': False, 'new_searches': 0},
        'arms': {'A': {'context_cap_bytes': 65536, 'native_original_packet': True},
                 'C': {'context_cap_bytes': 163840, 'original_A_packet_plus_frozen_table_fact_units': True}},
        'estimand': 'Joint effect of frozen table-fact representation and 160KiB ceiling at fixed Terra/low/top8. Not a pure budget or pure representation effect, and not a remeasurement of retrieval recall.',
        'historical_context_schema': 'Saved77 A12 omits unit_hint/period_focus/period_labels that current native delivery includes. Historical12 is replayed using its original field schema only for parity; new A8 and C8 both use the current native schema. The exposed18 already uses the current schema. Report any field/source-budget difference separately; do not attribute it to table augmentation.',
        'fixed_generation': template, 'call_limit_future': 72, 'repetitions_per_arm': 2,
        'automatic_retries': 0, 'timeout_seconds_per_request': 90, 'wall_time_limit_seconds_future': 9000,
        'metrics': {**protocol18['metrics'],
                    'review': 'Freeze existing rubric and new request bytes before execution. Seal72 outputs then fresh-context masked source review. Packet shape may reveal arm; no independent-human validation claim.',
                    'diagnosis': ['source/parser', 'saved candidates', 'fixed RRF top8', 'native A source budget',
                                  'table-unit validation/budget', 'model interpretation/citation'],
                    'statistics': '30 answerable outputs and6 refusal outputs per arm; 18 questions and3 report clusters. Repeats are dependent. No new holdout or population-significance claim.'},
        'stop_policy': ['Stop on failed request; count attempted dispatches including failures; no automatic retry or unplanned model/judge call.',
                        'Stop before spending beyond reserved cost/call/time cap; require complete usage accounting; cache discount never funds extra calls.',
                        'If active inputs or source hashes change, stop; do not silently refresh retrieval or alter the rubric.'],
        'preservation': ['runtime implementation', 'existing uncommitted changes', '.env', 'active v12 store', 'prior experiment artifacts'],
    })
    heartbeat('inputs_loaded', cases=95, sources=14)
    cases = []
    for c in panel77:
        cid = c['case_id']; rank = ranks77[cid]
        assert rank['query'] == c['question'] and rank['report_scope'] == c['report_scope']
        order = frozen_rrf(rank['dense'], rank['lexical']['A12'], rank['rrf']['A12'])
        assert [h['metadata']['chunk_uid'] for h in c['hits']] == [u for u, _ in order]
        assert all(h['score'] == s for h, (_, s) in zip(c['hits'], order))
        cases.append({'cohort': 'development77', 'case': c, 'hits': c['hits'], 'order': order,
                      'candidate_hash': digest({'dense': rank['dense'], 'lexical': rank['lexical']['A12'], 'rrf': rank['rrf']['A12']}),
                      'oldA': c['packet'], 'oldC': load(BUDGET77 / f'packets/{cid}_160KiB.json'),
                      'old_decisions': results77[cid]['arms']['160KiB']['decisions'], 'projections': projections77})
    for c in questions18:
        cid = c['case_id']; rank = load(EXEC18 / f'retrieval/{cid}.json')
        assert rank['query'] == c['question'] and rank['scope'] == c['report_scope']
        order = frozen_rrf(rank['dense'], rank['bm25'], rank['rrf'])
        cases.append({'cohort': 'exposed_transfer18', 'case': c, 'hits': rank['rrf'], 'order': order,
                      'candidate_hash': digest({'dense': rank['dense'], 'lexical': rank['bm25'], 'rrf': rank['rrf']}),
                      'oldA': load(EXEC18 / f'packets/{cid}_A.json'), 'oldC': load(EXEC18 / f'packets/{cid}_C.json'),
                      'old_decisions': load(EXEC18 / f'projection_decisions/{cid}.json'), 'projections': projections18})
    assert len(cases) == len({c['case']['case_id'] for c in cases}) == 95
    results = []
    requests = []
    binding_count = 0
    for number, item in enumerate(cases, 1):
        case = item['case']; cid = case['case_id']; projections = item['projections']
        hits = [(Document(page_content=h['text'], metadata=h['metadata']), h['score']) for h in item['hits']]
        historical_fields = (tuple(k for k in SOURCE_CONTEXT_FIELDS if k not in ('unit_hint', 'period_focus', 'period_labels'))
                             if item['cohort'] == 'development77' else None)
        captured12, _ = packet_from_native(case, hits, 12, historical_fields=historical_fields)
        assert captured12 == item['oldA'], ('Native top12 A replay drift', cid)
        captured8, capture_trace = packet_from_native(case, hits[:8], 8)
        boosted8, decisions8 = ASSEMBLER.project_packet(captured8, projections)
        assert remove_facts(boosted8) == captured8, ('Original evidence drift between A8/C8', cid)
        assert remove_facts(item['oldC']) == item['oldA']
        original12 = {d['chunk_id']: d for d in item['oldA']['documents']}
        delivered8 = [d['chunk_id'] for d in captured8['documents']]
        selected8 = [uid for uid, _ in item['order'][:8]]
        extra_context = {}
        for doc in captured8['documents']:
            original = original12[doc['chunk_id']]
            assert {k: v for k, v in doc.items() if k != 'context'} == {k: v for k, v in original.items() if k != 'context'}
            assert all(doc['context'][k] == v for k, v in original['context'].items())
            added_keys = set(doc['context']) - set(original['context'])
            assert added_keys <= {'unit_hint', 'period_focus', 'period_labels'}
            if added_keys:
                extra_context[doc['chunk_id']] = {k: doc['context'][k] for k in sorted(added_keys)}
        assert all(uid in selected8 for uid in delivered8)
        before = unit_map(item['oldC'], item['old_decisions'], projections)
        after = unit_map(boosted8, decisions8, projections)
        binding_count += len(after)
        common = set(before) & set(after)
        assert all(before[k] == after[k] for k in common), ('Existing table binding changed', cid)
        dropped_sources = [uid for uid in original12 if uid not in delivered8]
        lost_by_topk = sorted(k for k in set(before) - set(after) if before[k]['chunk_uid'] not in delivered8)
        lost_by_budget = sorted(k for k in set(before) - set(after) if before[k]['chunk_uid'] in delivered8)
        added = sorted(set(after) - set(before))
        for arm, packet in [('A', captured8), ('C', boosted8)]:
            assert len(enc(packet)) <= (65536 if arm == 'A' else 163840)
            put(f'packets/{cid}_{arm}.json', packet)
        put(f'decisions/{cid}.json', decisions8)
        put(f'native_capture/{cid}.json', capture_trace)
        put(f'bindings/{cid}.json', {'top8': after,
                                    'top12_lost': {k: before[k] for k in lost_by_topk + lost_by_budget}})
        record = {
            'case_id': cid, 'cohort': item['cohort'], 'question': case['question'], 'report_scope': case['report_scope'],
            'candidate_order_score_sha256': item['candidate_hash'], 'rrf12': item['order'], 'selected8': selected8,
            'native_A12_exact_replay': True, 'A8_C8_original_text_context_ids_order_identical': True,
            'historical12_replay_context_schema': 'historical' if historical_fields else 'current_native',
            'current_native_context_fields_added_to_both_arms_vs_historical': extra_context,
            'A8_delivered': delivered8, 'A12_delivered': list(original12), 'dropped_source_ids_topk': dropped_sources,
            'selected8_omitted_by_original_byte_cap': [uid for uid in selected8 if uid not in delivered8],
            'bytes': {'A8': len(enc(captured8)), 'C8': len(enc(boosted8)),
                      'A12': len(enc(item['oldA'])), 'C12': len(enc(item['oldC']))},
            'table_units': {'C8': len(after), 'C12': len(before), 'retained_exact': len(common), 'added': added,
                            'lost_due_to_topk': lost_by_topk, 'lost_on_retained_sources_due_to_budget': lost_by_budget,
                            'changed_value_axis_frame': []},
            'A8_C8_packet_hash': {arm: digest(p) for arm, p in [('A', captured8), ('C', boosted8)]},
            'interpretation': 'Unit/source visibility is not semantic completeness or answer accuracy. A8/C8 source equality does not prove top8 equals prior top12 coverage.'
        }
        results.append(record)
        if item['cohort'] == 'exposed_transfer18':
            for arm, packet in [('A', captured8), ('C', boosted8)]:
                body = copy.deepcopy(template)
                body['input'][1]['content'] = enc(packet).decode('utf8')
                bound = len(enc(body)) + 4096
                assert bound + 8192 < 272000, 'Short-context price regime exceeded'
                requests.append({'case_id': cid, 'arm': arm, 'body': body, 'body_sha256': digest(body),
                                 'input_bound': bound, 'packet_bytes': len(enc(packet)), 'packet_sha256': digest(packet),
                                 'packet_file_sha256': sha(OUT / f'packets/{cid}_{arm}.json')})
        if number % 5 == 0 or number == len(cases):
            heartbeat('packet_pairs_built', completed=number, total=95, checked_table_units=binding_count)
    put('case_results.json', results)
    put('requests18.json', requests)
    schedule = []
    request_map = {(x['case_id'], x['arm']): x for x in requests}
    for repeat in (1, 2):
        for i, case in enumerate(questions18):
            cid = case['case_id']
            for arm in ('A', 'C') if (i + repeat) % 2 else ('C', 'A'):
                request = request_map[cid, arm]
                schedule.append({'sequence': len(schedule) + 1, 'case_id': cid, 'arm': arm,
                                 'repeat': repeat, 'body_sha256': request['body_sha256'], 'input_bound': request['input_bound']})
    assert len(schedule) == 72
    assert all(n == 2 for n in Counter((r['case_id'], r['arm']) for r in schedule).values())
    put('schedule72.json', schedule)
    put('input_manifest.json', INPUTS)
    assert all(sha(ROOT / p) == h for p, h in INPUTS.items()), 'An input changed during execution'
    assert not DENIED_NETWORK_ATTEMPTS, 'Unexpected attempted external access'
    put('preparation_result.json', {
        'status': 'PASS', 'cases': 95, 'packet_pairs': 95, 'native_top12_exact_replay_cases': 95,
        'native_top8_captures': 95, 'fixed_candidate_rrf_exact_replays': 95,
        'all_original_A8_evidence_preserved_in_C8': True, 'table_value_axis_frame_bindings_checked': binding_count,
        'original_source_files_hash_checked': 14, 'model_calls': 0, 'embedding_calls': 0,
        'real_searches': 0, 'network_attempts': 0, 'store_clients_opened': 0,
        'future_requests_prepared_not_executed': len(requests), 'future_schedule_length': len(schedule),
        'elapsed_seconds': time.monotonic() - START,
        'limits': ['Stored source-validated table projections reused; physical linkage is not semantic verification.',
                   'No fresh candidate retrieval or model answers; no measured answer improvement in this phase.']})
    heartbeat('preparation_pass', pairs=95, future_calls_prepared_not_run=72, external_calls=0)


if __name__ == '__main__':
    main()
