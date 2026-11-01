"""Descriptive postrun counts, not semantic scoring or a projection rerun."""
import collections
import json
from pathlib import Path
import statistics

OUT = Path(__file__).resolve().parent
load = lambda n: json.loads((OUT / n).read_text(encoding='utf-8'))
rows = load('results.json')
projections = load('projections.json')


def sizes(key):
    vals = [r[key] for r in rows]
    return {'min': min(vals), 'median': statistics.median(vals), 'max': max(vals), 'sum': sum(vals)}


def counter(values):
    return dict(collections.Counter(values))


original = sizes('baseline_bytes')
prior = sizes('prior_T12_bytes')
new = sizes('experimental_bytes')
decisions = [d for r in rows for d in r['decisions']]
unit_decisions = [u for d in decisions for u in d.get('units', [])]
attached = {d['uid'] for d in decisions if d['status'] == 'attached'}
summary = {
    'scope': 'Descriptive offline evidence delivery only; no answer scores',
    'cases': len(rows), 'original_delivered_document_events': sum(len(r['delivered_ids']) for r in rows),
    'unique_original_documents': len(projections),
    'unique_attached_source_payloads': len(attached),
    'unique_attached_physical_tables': len({d['physical_key'] for d in decisions if d['status'] == 'attached'}),
    'cases_with_additions': sum(r['attached_units'] > 0 for r in rows),
    'cases_without_additions': [r['case_id'] for r in rows if not r['attached_units']],
    'cases_with_any_unit_budget_exclusions': sum(any(u['status'] == 'rejected_byte_budget' for d in r['decisions'] for u in d.get('units', [])) for r in rows),
    'source_projection_statuses': counter(p['receipt']['status'] for p in projections.values()),
    'source_projection_reasons': counter(p['receipt']['reason'] for p in projections.values()),
    'row_rejections': counter(r.get('reason') for p in projections.values() for r in p['receipt']['rows'] if r['status'] == 'REJECTED'),
    'cell_rejections': counter(c.get('reason') for p in projections.values() for r in p['receipt']['rows'] for c in r.get('cells', []) if c['status'] == 'REJECTED'),
    'context_exclusions': counter(c.get('reason') for p in projections.values() for c in p['receipt']['contexts'] if c['status'] != 'VERIFIED'),
    'table_delivery_decisions': counter(d['status'] for d in decisions),
    'unit_delivery_decisions': counter(u['status'] for u in unit_decisions),
    'source_validated_units_unique_chunk_payloads': sum(len(p['projection']['units']) for p in projections.values() if p['projection']),
    'source_validated_units_first_owner_case_events': len(unit_decisions),
    'source_validated_unique_physical_value_cells': len({(p['physical_key'], u['value']) for p in projections.values() if p['projection'] for u in p['projection']['units']}),
    'delivered_unique_physical_value_cells': len({(d['physical_key'], projections[d['uid']]['projection']['units'][i]['value']) for d in decisions if d['status'] == 'attached' for i, u in enumerate(d['units']) if u['status'] == 'attached'}),
    'bytes': {'A12': original, 'T12': prior, 'FCT12': new,
              'percent_vs_A12': 100 * (new['sum'] / original['sum'] - 1),
              'percent_vs_T12': 100 * (new['sum'] / prior['sum'] - 1)},
    'original_evidence_preserved_cases_runner_asserted': sum(r['original_documents_text_context_ids_order_identical'] for r in rows),
}
(OUT / 'aggregate_summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps(summary, ensure_ascii=False, indent=2))
