"""Saved-artifact visibility census and prospective cost, no generation."""
from __future__ import annotations
import copy
import importlib.util
import json
from collections import Counter
from decimal import Decimal, ROUND_CEILING
from pathlib import Path

O = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('top8_preparation', O / 'prepare.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
load, put, enc = m.load, m.put, m.enc
R = O.parent


def source_visibility_reviews(path, cohort, result_map):
    rows = load(path)
    results = {}
    for cid, case in result_map.items():
        if case['cohort'] != cohort:
            continue
        packet = load(O / f'packets/{cid}_A.json')
        visible = {d['source_id'] for d in packet['documents']}
        cited = sorted({r['source_id'] for row in rows if row['case_id'] == cid
                        for r in row.get('receipts', []) if r.get('source_id')})
        results[cid] = {'prior_review_receipt_sources': cited,
                        'retained_sources': sorted(set(cited) & visible),
                        'sources_outside_new8': sorted(set(cited) - visible),
                        'interpretation': 'Receipt-source visibility screen only. A dropped citation may have an equivalent surviving witness; a retained citation does not validate claims or all required facts.'}
    return results


def witnesses(value):
    found = {}
    def visit(x):
        if isinstance(x, dict):
            if x.get('chunk_uid') and x.get('unit_id'):
                key = x['chunk_uid'] + '|' + x['unit_id']
                found[key] = {'chunk_uid': x['chunk_uid'], 'unit_id': x['unit_id'], 'at': x.get('at')}
            for item in x.values(): visit(item)
        elif isinstance(x, list):
            for item in x: visit(item)
    visit(value)
    return found


def main():
    cases = load(O / 'case_results.json')
    byid = {r['case_id']: r for r in cases}
    visibility = source_visibility_reviews(R / 'table_fact_answer_full77_20261023/paired_results.json', 'development77', byid)
    visibility.update(source_visibility_reviews(R / 'table_fact_holdout18_preparation_20261023/execution/graded_answers.json', 'exposed_transfer18', byid))
    put('prior_review_source_visibility95.json', visibility)
    summary = {}
    for cohort in ('development77', 'exposed_transfer18'):
        rows = [r for r in cases if r['cohort'] == cohort]
        summary[cohort] = {
            'cases': len(rows), 'delivered8_cardinality': dict(Counter(len(r['A8_delivered']) for r in rows)),
            'actual_document_pairs_identical': sum(r['A8_C8_original_text_context_ids_order_identical'] for r in rows),
            'source_documents_removed_from12': sum(len(r['dropped_source_ids_topk']) for r in rows),
            'cases_with_original_source_omissions_below8': [r['case_id'] for r in rows if r['selected8_omitted_by_original_byte_cap']],
            'cases_with_added_native_metadata_vs_old12': [r['case_id'] for r in rows if r['current_native_context_fields_added_to_both_arms_vs_historical']],
            'total_bytes': {key: sum(r['bytes'][key] for r in rows) for key in ('A8','C8','A12','C12')},
            'range_bytes': {key: [min(r['bytes'][key] for r in rows), max(r['bytes'][key] for r in rows)] for key in ('A8','C8')},
            'C8_cases_over64KiB': [r['case_id'] for r in rows if r['bytes']['C8'] > 65536],
            'identical_A8_C8_cases': [r['case_id'] for r in rows if r['A8_C8_packet_hash']['A'] == r['A8_C8_packet_hash']['C']],
            'table_units_C8': sum(r['table_units']['C8'] for r in rows),
            'table_units_C12': sum(r['table_units']['C12'] for r in rows),
            'retained_exact_units': sum(r['table_units']['retained_exact'] for r in rows),
            'units_lost_on_removed_sources': sum(len(r['table_units']['lost_due_to_topk']) for r in rows),
            'units_lost_on_retained_sources_due_to_budget': sum(len(r['table_units']['lost_on_retained_sources_due_to_budget']) for r in rows),
            'newly_delivered_units': sum(len(r['table_units']['added']) for r in rows),
            'cases_with_newly_delivered_units': [r['case_id'] for r in rows if r['table_units']['added']],
            'changed_binding_payloads': sum(len(r['table_units']['changed_value_axis_frame']) for r in rows),
            'cases_with_previous_review_source_outside8': [r['case_id'] for r in rows if visibility[r['case_id']]['sources_outside_new8']],
        }
    previous = load(R / 'table_fact_budget77_offline_20261023/postrun_required_fact_review.json')
    prior_cases = previous['current4'] + previous['legacy26_panel']
    prior_cases += [{'case_id': cid, 'data': data} for cid, data in previous['additional_HOLD_evidence'].items()]
    witness_checks = {}
    for c in prior_cases:
        cid = c['case_id']; old = witnesses(c)
        bound = load(O / f'bindings/{cid}.json')
        if cid not in witness_checks: witness_checks[cid] = {}
        for key, w in old.items():
            if key in bound['top8']:
                status = 'EXACT_BINDING_DELIVERED8'
            elif key in bound['top12_lost']:
                status = 'KNOWN_PRIOR_BINDING_LOST8'
            else:
                status = 'NOT_AN_EMITTED_OLD160_WITNESS_OR_NO_BOUND_RECORD'
            witness_checks[cid][key] = {**w, 'status': status}
    put('prior_required_witness_checks.json', {
        'method': 'Match source_uid+unit_id against exact decoded cell/axis/frame bindings. Inherited semantic fact labels are not newly inferred by code.',
        'cases': witness_checks,
        'counts': dict(Counter(w['status'] for case in witness_checks.values() for w in case.values())),
        'coverage_limit': 'Prior source-bound review contains explicit physical witnesses for a subset of77; not a complete semantic recall denominator.'})

    requests = load(O / 'requests18.json')
    oldrequests = {(r['case_id'], r['arm']): r for r in load(R / 'table_fact_holdout18_preparation_20261023/execution/requests.json')}
    newrequests = {(r['case_id'], r['arm']): r for r in requests}
    ledger_path = m.remember(R / 'table_fact_holdout18_preparation_20261023/execution/live/ledger.jsonl')
    ledger = [json.loads(line) for line in ledger_path.read_text('utf8').splitlines()]
    costs = {'same_cache_pattern_proxy': Decimal(0), 'no_cache_read_same_output_proxy': Decimal(0),
             'no_cache_read_triple_output_sensitivity': Decimal(0)}
    tokens = {'input_scaled_proxy': Decimal(0), 'output_saved_sol': 0}
    sample = []
    for row in ledger:
        if row['event'] != 'settled' or row.get('kind') != 'answer': continue
        cid, arm, rep = row['label'].split(':')
        new = newrequests[cid, arm]; old = oldrequests[cid, arm]
        ratio = Decimal(len(enc(new['body']))) / Decimal(len(enc(old['body'])))
        usage = row['usage']; it = Decimal(usage['input_tokens']) * ratio
        detail = usage['input_tokens_details']
        ct = Decimal(detail.get('cached_tokens', 0)) * ratio
        wt = Decimal(detail.get('cache_write_tokens', 0)) * ratio
        assert ct + wt <= it
        ot = Decimal(usage['output_tokens'])
        costs['same_cache_pattern_proxy'] += ((it-ct-wt)*2 + ct*Decimal('.2') + wt*Decimal('2.5') + ot*12) / 1000000
        costs['no_cache_read_same_output_proxy'] += (it*Decimal('2.5') + ot*12)/1000000
        costs['no_cache_read_triple_output_sensitivity'] += (it*Decimal('2.5') + ot*36)/1000000
        tokens['input_scaled_proxy'] += it
        tokens['output_saved_sol'] += int(ot)
        sample.append({'case_id': cid, 'arm': arm, 'repeat': rep, 'body_byte_ratio': float(ratio),
                       'estimated_input_tokens_proxy': float(it), 'saved_sol_output_tokens': int(ot)})
    assert len(sample) == 72
    ibound = sum(r['input_bound'] for r in requests) * 2
    obound = 8192 * 72
    reserve = (Decimal(ibound)*Decimal('2.5')+Decimal(obound)*12)/1000000
    cap = reserve.quantize(Decimal('.01'), rounding=ROUND_CEILING)
    prices = {
        'checked_date': '2026-10-24', 'pricing_url': 'https://developers.openai.com/api/docs/pricing',
        'cache_url': 'https://developers.openai.com/api/docs/guides/prompt-caching',
        'model': 'gpt-5.6-terra', 'service_tier': 'default', 'currency': 'USD',
        'per_million_tokens': {'input': '2.00', 'output_including_reasoning': '12.00', 'cache_read': '0.20', 'default30m_cache_write': '2.50'},
        'short_context_threshold_input_tokens': 272000,
        'max_reserved_input_tokens_per_request': max(r['input_bound'] for r in requests),
        'call_limit': 72, 'output_limit_per_call_including_reasoning': 8192,
        'input_bound_rule': 'Canonical UTF8 bytes of entire request plus4096 for framing. Deliberately loose planning reserve, not a provider tokenizer measurement; stop if actual usage exceeds reservation.',
        'reserved_input_tokens_total': ibound, 'reserved_output_tokens_total': obound,
        'reserve_usd_exact': str(reserve), 'recommended_cost_cap_usd': str(cap),
        'reserve_formula': f'({ibound}*2.50 + {obound}*12)/1000000',
        'proxy_estimates_usd': {k: str(v.quantize(Decimal('.000001'))) for k,v in costs.items()},
        'proxy_input_tokens': float(tokens['input_scaled_proxy']), 'proxy_saved_sol_output_tokens': tokens['output_saved_sol'],
        'expected_range_for_planning_usd': ['1.50', '2.50'],
        'expected_estimate_basis': 'Saved18 Sol usage scaled by new/old full request byte ratio, repriced to Terra. No-cache-read and3x-output sensitivity shown. Model output length and caching remain unknown; this is not a Terra measurement or confidence interval.',
        'wall_time_limit_seconds': 9000, 'request_timeout_seconds': 90, 'retries': 0,
        'no_retrieval_embedding_ingest_judge_calls': True,
        'failed_attempts': 'Count every dispatch and retain full reserved cost for uncertain failures; stop without retry.',
        'no_extra_calls_from_discount': True, 'execution_status': 'NOT_RUN',
        'account_model_availability': 'Not probed; only prior configured model and public pricing checked.',
    }
    put('pricing.json', prices); put('cost_proxy_detail72.json', sample)
    summary['interpretation_limits'] = ['95-case mechanical source/unit audit is not95-case answer evaluation.',
        'Same candidate RRF replay does not establish fresh online retrieval or store behavior.',
        'Current native context schema differs from old77; both new arms use exactly the same fields.',
        'All18 C8 inputs fit64KiB, so this future18 comparison cannot establish the need for a160KiB ceiling.',
        'Previously used18 is an exposed transfer/regression panel.']
    put('analysis.json', summary)
    put('analysis_input_manifest.json', m.INPUTS)
    print(json.dumps({'summary':summary,'pricing':prices},ensure_ascii=False,indent=2))


if __name__ == '__main__': main()
