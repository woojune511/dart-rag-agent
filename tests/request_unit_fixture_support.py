"""Explicit authored request assignments for old, planner-free test fixtures.

Every fixture owner receives the complete question. These copies test execution
and harness contracts, NOT planner mapping quality. Frozen files/programs/source
records/expected outcomes are never changed. Production has no such migration.
"""

from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from src.agent.financial_request_units import build_request_units


def bind_fixture_request(case):
    copied = deepcopy(case)
    refs = [unit.request_unit_id for unit in build_request_units(copied['question'])]
    for owner in copied['obligations']:
        owner['request_unit_ids'] = list(refs)
    return copied


def bind_fixture_requests(corpus):
    return {**deepcopy(corpus), 'cases': [bind_fixture_request(case) for case in corpus['cases']]}


def request_bound_fixture(test, source):
    original = source.read_bytes()
    test.addCleanup(lambda: test.assertEqual(source.read_bytes(), original))
    temp = TemporaryDirectory(dir=Path.cwd())
    test.addCleanup(temp.cleanup)
    target = Path(temp.name) / source.name
    target.write_text(json.dumps(bind_fixture_requests(json.loads(original)), ensure_ascii=False), encoding='utf-8')
    return target
