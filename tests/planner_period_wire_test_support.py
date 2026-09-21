"""Explicit authored Planner period payloads; no inferred request interpretation."""


def declared_period(precision, **fields):
    return dict(precision=precision, reference_year=None, year_offset=None, coverage=None,
        start_date=None, end_date=None,
        request_unit_ids=[] if precision == 'unspecified' else ['request_001']) | fields


def unspecified_period_payload(model):
    """Project only fixtures that already explicitly declare no period request."""
    raw = model.model_dump()
    for output in raw.get('obligations', []):
        for owner in [output, *output['evidence_requirements']]:
            assert owner['scope']['measurement_period'] == {'kind': 'unspecified'}
            owner['scope']['measurement_period'] = declared_period('unspecified')
    return raw
