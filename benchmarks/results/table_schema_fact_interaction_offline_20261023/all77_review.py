"""Read-only evidence comparison; no retrieval, projection, provider, or store client.

Run only after the parent confirms packet execution completion. Semantic review
notes are evaluator-only and cannot feed the frozen projector or retrieval.
"""
import hashlib
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
OLD = ROOT / 'benchmarks/results/table_schema_search_validated_offline_20261022'
DETAIL = OUT / 'all77_review_details'
ARMS = ('A12_original', 'S12_original', 'A12_fact160', 'S12_fact160')


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')).hexdigest()


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def original(packet):
    return {**packet, 'documents': [{k: v for k, v in d.items() if k != 'table_fact_units'} for d in packet['documents']]}


def inventory(packet):
    result = {}
    for d in packet['documents']:
        w = d.get('table_fact_units')
        if not w:
            continue
        frame = {k: v for k, v in w.items() if k not in ('source_id', 'cells', 'units')}
        for row, col, val, ra, ca in w['units']:
            key = w['document_sha256'] + '|' + w['table_locator'] + f'|{row}:{col}'
            assert key not in result
            result[key] = {'owner_uid': d['chunk_id'], 'source_id': d['source_id'], 'physical_key': key,
                           'at': [row, col], 'value': w['cells'][val],
                           'row_axes': [w['cells'][i] for i in ra], 'column_axes': [w['cells'][i] for i in ca],
                           'frame': frame}
    return result


def neutral(unit):
    return {k: v for k, v in unit.items() if k not in ('owner_uid', 'source_id')}


def text_receipt(arm, packet, uid, quote):
    d = next(d for d in packet['documents'] if d['chunk_id'] == uid)
    pos = d['text'].find(quote)
    assert pos >= 0, (arm, uid, quote)
    return {'arm': arm, 'owner_uid': uid, 'source_id': d['source_id'], 'field': 'text',
            'quote': quote, 'character_span': [pos, pos + len(quote)],
            'text_sha256': hashlib.sha256(d['text'].encode('utf-8')).hexdigest()}


def main():
    assert (OUT / 'execution_entry.json').exists(), 'Execution completion required'
    contract = load(OUT / 'evaluation_contract.json')
    supplement = load(OUT / 'evaluation_supplement.json')
    results = {r['case_id']: r for r in load(OUT / 'results.json')}
    prior = {r['case_id']: r for r in load(OLD / 'all77_source_audit.json')['cases']}
    prior_review = load(OLD / 'source_review.json')
    prior_loss = {r['case_id']: r for r in prior_review['cases']}
    manual_path = DETAIL / 'manual_review.json'
    manual = load(manual_path) if manual_path.exists() else {}
    watch = {r['case_id']: r for r in supplement['axis_binding_watch19']}
    DETAIL.mkdir(exist_ok=True)
    files = [OUT / 'all77_review.py', OUT / 'evaluation_contract.json', OUT / 'evaluation_supplement.json', OUT / 'protocol.json',
             OUT / 'freeze.json', OUT / 'results.json', OLD / 'all77_source_audit.json', OLD / 'source_review.json']
    rows = []
    for c in contract['cases']:
        cid = c['case_id']
        packets = {a: load(OUT / f'packets/{cid}_{a}.json') for a in ARMS}
        paths = {a: OUT / f'packets/{cid}_{a}.json' for a in ARMS}
        a, b = packets['A12_original'], packets['S12_original']
        docs = {arm: {d['chunk_id']: d for d in p['documents']} for arm, p in packets.items()}
        common = docs['A12_original'].keys() & docs['S12_original'].keys()
        lost = sorted(docs['A12_original'].keys() - docs['S12_original'].keys())
        gained = sorted(docs['S12_original'].keys() - docs['A12_original'].keys())
        af, sf = inventory(packets['A12_fact160']), inventory(packets['S12_fact160'])
        common_fact = af.keys() & sf.keys()
        physical = {'common': len(common_fact), 'lost': sorted(af.keys() - sf.keys()),
                    'added': sorted(sf.keys() - af.keys()),
                    'changed_dependencies': [k for k in sorted(common_fact) if neutral(af[k]) != neutral(sf[k])],
                    'first_owner_changed': [k for k in sorted(common_fact) if af[k]['owner_uid'] != sf[k]['owner_uid']]}
        rr = results[cid]['physical_unit_changes']
        assert all(physical[k] == rr[k] for k in ('common', 'lost', 'added', 'changed_dependencies'))
        packet_receipts = {arm: {'path': str(path.relative_to(ROOT)), 'file_sha256': sha(path),
                                'canonical_json_sha256': digest(packets[arm]),
                                'packet_bytes': results[cid]['arms'][arm]['packet_bytes'],
                                'actual_document_count': len(packets[arm]['documents'])} for arm, path in paths.items()}
        invariants = {
            'A12_original_fields_preserved_in_fact160': original(packets['A12_fact160']) == a,
            'S12_original_fields_preserved_in_fact160': original(packets['S12_fact160']) == b,
            'A12_original_exact_prior_packet': a == load(OLD / f'packets/{cid}_A12.json'),
            'S12_original_exact_prior_packet': b == load(OLD / f'packets/{cid}_S12.json'),
            'common_original_docs_exact': all(docs['A12_original'][k] == docs['S12_original'][k] for k in common),
        }
        review = manual.get(cid, {})
        receipts = []
        for item in review.get('text_witnesses', []):
            receipts.append(text_receipt(item['arm'], packets[item['arm']], item['uid'], item['quote']))
        for item in review.get('fact_witnesses', []):
            arm = item.get('arm', 'S12_fact160')
            units = af if arm == 'A12_fact160' else sf
            found = [v for v in units.values() if v['owner_uid'] == item['uid'] and v['at'] == item['at']]
            assert len(found) == 1, (cid, item)
            receipt = found[0]
            if 'value' in item:
                assert receipt['value'][4] == item['value'], (cid, item, receipt['value'])
            other = sf if arm == 'A12_fact160' else af
            counterpart = other.get(receipt['physical_key'])
            receipts.append({'arm': arm, 'field': 'table_fact_units', **receipt,
                             'dependency_payload_sha256': digest(neutral(receipt)),
                             'identical_physical_dependency_in_other_fact160_arm': counterpart is not None and neutral(counterpart) == neutral(receipt),
                             'scope': 'Actual transmitted literal dependency receipt, not independent semantic certification.'})
        for w in prior_review['verified_quote_witnesses']:
            if w['case_id'] != cid:
                continue
            arm = w['arm'] + '_fact160'
            d = docs[arm].get(w['uid'])
            if d and w['quote'] in d['text']:
                receipt = text_receipt(arm, packets[arm], w['uid'], w['quote'])
                receipt['prior_receipt_hash_agrees'] = receipt['text_sha256'] == w['source_text_sha256']
                receipt['receipt_origin'] = 'Prior quote independently located in actual new packet; not a carried-over semantic verdict.'
                receipts.append(receipt)
        if not review and c['group'] == 'refusal':
            review = {'category': 'UNEVALUATED_UNKNOWN', 'required_evidence_regression': 'NOT_APPLICABLE_REFUSAL_CONTROL',
                      'finding': 'Original-field preservation and actual source/fact changes audited. No new refusal behavior or absence-of-fact conclusion.'}
        elif not review and not lost and not gained and not physical['lost'] and not physical['changed_dependencies']:
            review = {'category': 'RETAINED_ORIGINAL_FACTS', 'required_evidence_regression': 'NO_CONTENT_LOSS_WITHIN_AUDITED_REPRESENTATION',
                      'finding': 'Every original document and physical fact dependency remains exact across A12_fact160/S12_fact160; source order can differ. This is content retention only; baseline completeness is not re-certified.'}
        criterion_overrides = review.get('criterion_findings', {})
        row = {
            'case_id': cid, 'group': c['group'], 'question': c['question'],
            'required_units_unchanged': c['required_units'],
            'criterion_review_status': [{'unit_id': u['unit_id'],
                                        'finding': criterion_overrides.get(u['unit_id'], 'NOT_REASSESSED_FOR_FULL_SEMANTIC_SUFFICIENCY')}
                                       for u in c['required_units']],
            'completion_rule_unchanged': c.get('existing_rubric_completion_rule'),
            'axis_watch': cid in watch,
            'axis_watch_inherited_boundary': watch[cid]['inherited_semantic_boundary'] if cid in watch else None,
            'original_facts_retained_within_arm': invariants,
            'primary_comparison': 'S12_fact160 versus A12_fact160',
            'raw_document_changes': {'same_source_set': not lost and not gained, 'common_unchanged': len(common),
                                     'lost_uids': lost, 'gained_uids': gained,
                                     'historical_cited_sources_lost': prior[cid]['arms']['S12']['historical_cited_sources_lost']},
            'physical_unit_changes_not_semantic_facts': physical,
            'budget_and_first_owner': {arm: results[cid]['arms'][arm].get('decisions', []) for arm in ('A12_fact160', 'S12_fact160')},
            'prior_citation_loss_review_context': prior_loss.get(cid),
            'bounded_semantic_review': review or {
                'category': 'UNEVALUATED_UNKNOWN',
                'finding': 'Original text and physical-unit differences audited; no new full semantic sufficiency judgment for this case.',
                'required_evidence_regression': 'UNKNOWN',
            },
            'actual_packet_source_receipts': receipts,
            'input_receipts': packet_receipts,
            'all_unchanged_criteria_semantically_certified': False,
            'answer_accuracy_faithfulness_refusal': 'NOT_MEASURED_NO_GENERATION',
            'HOLD_lifted': False,
        }
        save(DETAIL / f'{cid}.json', row)
        rows.append(row)
    assert len(rows) == 77
    units = sum(len(r['required_units_unchanged']) for r in rows)
    assert units == 154, units
    report = {
        'schema': 'bounded_all77_evidence_comparison_v1',
        'reviewer': 'Delegated reviewer spawned with fork_turns=none; requested gpt-6-astra / xhigh under ARS policy. Provider-attested model identity unavailable. Review was unblinded to prior development-exposed evidence; no blind or cross-model independence claim.',
        'method': 'All77 deterministic packet comparison plus explicit bounded reading of flagged original passages and actual delivered fact dependencies; presence checks never certify semantic completeness.',
        'inputs': [{'path': str(p.relative_to(ROOT)), 'sha256': sha(p)} for p in files],
        'manual_review_sha256': sha(manual_path) if manual_path.exists() else None,
        'fixed_population': dict(Counter(r['group'] for r in rows)),
        'unchanged_required_units': units,
        'all77_invariants': {k: sum(r['original_facts_retained_within_arm'][k] for r in rows) for k in rows[0]['original_facts_retained_within_arm']},
        'review_categories': dict(Counter(r['bounded_semantic_review']['category'] for r in rows)),
        'review_categories_by_group': {g: dict(Counter(r['bounded_semantic_review']['category'] for r in rows if r['group'] == g))
                                       for g in ('common_answerable', 'refusal', 'diagnostic_or_hold')},
        'confirmed_mandatory_evidence_loss_cases': [r['case_id'] for r in rows if r['bounded_semantic_review'].get('required_evidence_regression') == 'CONFIRMED'],
        'conditional_HOLD_evidence_loss_cases': [r['case_id'] for r in rows if r['bounded_semantic_review'].get('required_evidence_regression') == 'CONDITIONAL_HOLD_LOSS'],
        'partial_alternative_fact_loss_with_unresolved_full_criterion': ['HYU_T3_072'],
        'unknown_or_unevaluated_cases': [r['case_id'] for r in rows if r['bounded_semantic_review'].get('required_evidence_regression') == 'UNKNOWN'],
        'axis_watch_coverage': {'total': len(watch), 'with_explicit_bounded_reading': sum(cid in manual for cid in watch)},
        'former_citation_loss_coverage': {'total': len(prior_loss), 'with_explicit_bounded_reading': sum(cid in manual for cid in prior_loss)},
        'bounded_manual_cases': len(manual),
        'criterion_findings': dict(Counter(v['finding'] for r in rows for v in r['criterion_review_status'])),
        'final_review_status': 'COMPLETE_WITH_EXPLICIT_SEMANTIC_UNKNOWNS',
        'limitations': ['No answer generation, answer scoring, refusal outcome, or generalization measurement.',
                        'Within-arm exact text retention is deterministic evidence nonloss, not semantic support or harmlessness of additions.',
                        'Full77 matrix coverage is not full77 semantic completeness; unreviewed criteria and source alternatives remain unknown.',
                        'Physical cells and dependency counts are descriptive; they do not change the154 frozen criteria.',
                        'The19axis-watch overlaps other panels and is not an independent denominator.',
                        'HOLD12 remains HOLD; refusal19 has no new behavioral measurement.',
                        'Source XML validity of all projected units is owned by the separate parent audit; this review uses locators/receipts without executing the projector.'],
        'cases': rows,
    }
    save(OUT / 'all77_evidence_review.json', report)
    print(json.dumps({k: v for k, v in report.items() if k not in ('cases', 'inputs')}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
