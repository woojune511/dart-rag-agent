"""Read-only saved packet comparison for the author axis review.

Does not import the projector/runner, reparse XML, open a store, or call a model.
Run with python -B; output is an inspection inventory, not semantic grading.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

OUT = Path(__file__).resolve().parent
OLD = OUT.parent / 'table_fact_units_offline_20261023'


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def without_extra(packet):
    return {**packet, 'documents': [
        {k: v for k, v in d.items() if k != 'table_fact_units'}
        for d in packet['documents']]}


def frame(bundle):
    return {k: v for k, v in bundle.items() if k not in ('cells', 'units')}


def unpack(bundle, wire):
    cells = bundle['cells']
    r, c, value, row, column = wire
    return {'at': [r, c], 'value': cells[value],
            'row_axes': [cells[i] for i in row],
            'column_axes': [cells[i] for i in column]}


def inventory(packet, arm):
    docs = {d['chunk_id']: d for d in packet['documents']}
    result = {}
    for decision in arm['decisions']:
        uid = decision['uid']
        attached = [u for u in decision.get('units', []) if u['status'] == 'attached']
        if not attached:
            continue
        bundle = docs[uid]['table_fact_units']
        assert len(attached) == len(bundle['units'])
        for record in attached:
            wire = bundle['units'][record['wire_unit_index']]
            assert wire[:2] == record['at']
            key = uid + '|' + record['unit_id']
            assert key not in result
            result[key] = unpack(bundle, wire)
    return result


def audit():
    rows = load(OUT / 'results.json')
    watch = {x['case_id'] for x in load(OLD / 'postrun_axis_review.json')['case_axis_reviews']}
    checks, reviewed_tables = [], {}
    for result in rows:
        cid = result['case_id']
        a12 = load(OLD / f'packets/{cid}_A12.json')
        packets = {label: load(OUT / f'packets/{cid}_{label}.json')
                   for label in ('64KiB', '160KiB')}
        inv = {label: inventory(packets[label], result['arms'][label]) for label in packets}
        a, b = inv['64KiB'], inv['160KiB']
        common = a.keys() & b.keys()
        bundles = {label: {d['chunk_id']: d['table_fact_units'] for d in packet['documents']
                          if 'table_fact_units' in d} for label, packet in packets.items()}
        shared_tables = bundles['64KiB'].keys() & bundles['160KiB'].keys()
        check = {
            'case_id': cid,
            'original_A12_preserved_both': all(without_extra(p) == a12 for p in packets.values()),
            'saved_64_packet_exact': packets['64KiB'] == load(OLD / f'packets/{cid}_FCT12.json'),
            'retained_unit_count': len(common),
            'added_unit_count': len(b.keys() - a.keys()),
            'lost_units': sorted(a.keys() - b.keys()),
            'changed_retained_units': [k for k in sorted(common) if a[k] != b[k]],
            'changed_shared_frames': [uid for uid in sorted(shared_tables)
                                      if frame(bundles['64KiB'][uid]) != frame(bundles['160KiB'][uid])],
            'lost_table_frames': sorted(bundles['64KiB'].keys() - bundles['160KiB'].keys()),
            'added_table_frames': sorted(bundles['160KiB'].keys() - bundles['64KiB'].keys()),
            'watch_case': cid in watch,
        }
        assert check['retained_unit_count'] == result['unit_changes']['retained']
        assert check['added_unit_count'] == len(result['unit_changes']['added'])
        assert check['lost_units'] == result['unit_changes']['lost']
        checks.append(check)
        if cid in watch or result['arms']['160KiB']['budget_rejected_units']:
            reviewed_tables[cid] = []
            for decision in result['arms']['160KiB']['decisions']:
                uid = decision['uid']
                if uid not in bundles['160KiB']:
                    continue
                bundle = bundles['160KiB'][uid]
                old = bundles['64KiB'].get(uid)
                keys = [k for k in b if k.startswith(uid + '|')]
                added = [b[k] for k in keys if k not in a]
                reviewed_tables[cid].append({
                    'uid': uid, 'frame': frame(bundle),
                    'units64': len(old['units']) if old else 0,
                    'units160': len(bundle['units']),
                    'added_units': added,
                    'expanded_row_range160': [min(u[0] for u in bundle['units']), max(u[0] for u in bundle['units'])],
                })
    return {'checks': checks, 'reviewed_tables': reviewed_tables,
            'input_sha256': {n: sha(OUT / n) for n in ('results.json', 'aggregate_summary.json', 'protocol.json', 'freeze.json')},
            'checker_sha256': sha(__file__),
            'scope': 'Saved packet and decision inspection only; no projector, XML, retrieval, store, or model execution.'}


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--case')
    p.add_argument('--uid')
    p.add_argument('--row', type=int)
    args = p.parse_args()
    data = audit()
    if args.case:
        cases = [c for c in data['checks'] if c['case_id'] == args.case]
        tables = data['reviewed_tables'].get(args.case, [])
        if args.uid:
            tables = [t for t in tables if t['uid'] == args.uid]
        if args.row is not None:
            for table in tables:
                table['added_units'] = [u for u in table['added_units'] if u['at'][0] == args.row]
        print(json.dumps({'checks': cases, 'tables': tables}, ensure_ascii=False, indent=2))
    else:
        print(json.dumps({'checks': data['checks'], 'input_sha256': data['input_sha256'],
                          'checker_sha256': data['checker_sha256']}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
