"""Explicit authored request assignments for old, planner-free test fixtures.

Every fixture owner receives the complete question. These copies test execution
and harness contracts, NOT planner mapping quality. Frozen files/programs/source
records/expected outcomes are never changed on disk. Temporary copies also
address the already authored narrative quotes, not model behavior. Production
has no such migration.
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
    from tests.source_interpretation_fixture_support import authored_relationships, authored_source_program
    copied['obligations'] = authored_relationships(copied['obligations'], copied['question'])
    if any(copied.get('program', {}).get(field) for field in ('direct_bindings', 'expressions', 'narrative_bindings')):
        from src.ops.replay_reviewed_compiler_selection import _compiler_case_catalog
        from tests.narrative_address_test_support import address_program
        catalog = _compiler_case_catalog(copied)[0]
        copied['program'] = authored_source_program(address_program(copied['program'], catalog),
            copied['obligations'], catalog, copied['question'])
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
