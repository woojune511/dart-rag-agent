"""Reject malformed review records; no automatic semantic score substitution."""
from collections import Counter
from pathlib import Path
import json

AXES={'PASS','PARTIAL','FAIL','AMBIGUOUS'}
STATES={'FULFILLED','PARTIAL','OMITTED','INCORRECT','UNRESOLVED_CRITERION'}

def validate(reviews,mapping,cases,answers):
    assert len(reviews)==308,'Review count'
    ids=[r['review_id'] for r in reviews]
    assert len(set(ids))==308 and set(ids)==set(mapping),'Duplicate/missing review IDs'
    warnings=[]
    for r in reviews:
        rid=r['review_id'];m=mapping[rid];c=cases[m['case_id']]
        assert m['arm'] in {'A','C'} and m['repetition'] in {1,2},(rid,'Unexpected condition/repetition')
        assert m['label']==f"{m['case_id']}:{m['arm']}:r{m['repetition']}",(rid,'Mapping label disagreement')
        assert r['case_id']==m['case_id'],(rid,'Case mismatch')
        for axis in ['accuracy','completeness']:
            if c['group']=='diagnostic_or_hold':assert r[axis] is None,(rid,'HOLD must be null')
            else:assert r[axis] in AXES,(rid,'Invalid scored axis',axis)
        assert r['faithfulness'] in AXES,(rid,'Invalid faithfulness')
        assert r['appropriate_abstention'] in AXES|{'NOT_APPLICABLE'},(rid,'Invalid abstention')
        assert r['citation_validity'] in {'PASS','FAIL'},(rid,'Invalid citation validity')
        assert isinstance(r['unsupported_claims'],list),(rid,'Claims must be array')
        assert isinstance(r['receipts'],list) and len(r['receipts'])>0,(rid,'Evidence receipts required')
        assert r.get('notes'),(rid,'Judgement note required')
        unitids=[u['unit_id'] for u in r['units']]
        expected=[u['unit_id'] for u in c['frozen_required_units']]
        assert len(unitids)==len(set(unitids)) and set(unitids)==set(expected),(rid,'Duplicate/missing unit ID')
        for u in r['units']:
            assert u['status'] in STATES and u.get('note'),(rid,'Invalid unit state/note')
        a=answers[m['label']]
        assert all(a[k]==m[k] for k in ['case_id','arm','repetition','label']),(rid,'Sealed answer identity disagreement')
        assert r['citation_validity']==('FAIL' if a['unknown_citations'] else 'PASS'),(rid,'Citation membership disagreement')
        assert not (a['unknown_citations'] and r['faithfulness']=='PASS'),(rid,'Invalid source ID conflicts with faithfulness PASS; adjudicate')
        assert not (a['structural_error'] and all(r[k]=='PASS' for k in ['accuracy','completeness','faithfulness'])),(rid,'Schema-error complete success requires explicit adjudication')
        if a['structural_error']:warnings.append({'review_id':rid,'type':'generator_schema_error','detail':a['structural_error']})
        if r['completeness']=='PASS' and any(u['status']!='FULFILLED' for u in r['units']):
            warnings.append({'review_id':rid,'type':'PASS_with_unfulfilled_record','note':'Inspect alias/optional/choice semantics manually; do not recalculate automatically.'})
        if r['unsupported_claims'] and r['faithfulness']=='PASS':
            warnings.append({'review_id':rid,'type':'PASS_with_unsupported_claims','note':'Root must reconcile existing criteria, not silently accept.'})
    counts=Counter((m['case_id'],m['arm'],m['repetition']) for m in mapping.values())
    assert len(counts)==308 and all(v==1 for v in counts.values()),'Mapping collisions'
    assert len({m['case_id'] for m in mapping.values()})==77,'Case coverage'
    return warnings
