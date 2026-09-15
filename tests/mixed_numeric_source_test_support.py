"""Synthetic mixed-source fixtures. No provider, planner, source or answer repair."""
from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from src.agent.financial_calculation_execution import execute_semantic_calculation_program
from src.agent.financial_graph_models import AnswerObligation
from src.agent.financial_langchain_loaders import chat_prompt_template_from_template
from src.agent.financial_reconciliation_candidates import build_semantic_candidate_catalog
from src.agent.financial_source_bundles import build_semantic_source_bundles
from src.ops.compiler_fixture_transport import project_offline_program_to_wire
from src.ops.replay_reviewed_compiler_selection import _CompilerOnlyAgent, _RecordingLLM, _case_state
from tests.source_interpretation_fixture_support import authored_source_program

FIXTURES = Path(__file__).parent / 'fixtures'


def load_sources():
    return json.loads((FIXTURES / 'mixed_numeric_source_cases_v1.json').read_text(encoding='utf-8'))['cases']


def load_criteria():
    return {r['case_id']: r for r in json.loads(
        (FIXTURES / 'mixed_numeric_source_criteria_v1.json').read_text(encoding='utf-8'))['cases']}


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode()


def materialize(source_case, *, reverse_carriers=False):
    """Raw table records/prose -> actual catalog. Local fact keys never enter it."""
    carriers, addresses = [], {}
    document = source_case['document_id']
    for source in source_case['sources']:
        source_id = source['source_id']
        metadata = {'document_id': document}
        if source['format'] == 'table':
            cells = []
            for index, cell in enumerate(source['cells'], 1):
                value_id = f'{source_id}:v{index}'
                addresses[cell['key']] = (source_id, value_id, None)
                cells.append({key: cell[key] for key in ('value_text', 'unit_hint', 'period_text')})
                cells[-1].update(column_headers=[cell['period_text'], source['row_headers'][-1]],
                    physical_cell_id=f'{source_id}:c{index}', physical_value_id=value_id,
                    physical_cell_key=f'{document}:{source_id}:r1:c{index}')
            text = ' | '.join([*source['row_headers'], *[
                f"{c['period_text']} {c['value_text']} {c['unit_hint']}" for c in source['cells']]])
            metadata.update(table_source_id=source_id, physical_table_id=f'{document}:{source_id}',
                physical_row_id='r1', source_row_id='r1', row_label=source['row_headers'][-1],
                row_headers=list(source['row_headers']), structured_cells=cells)
            kind = 'structured_row'
        else:
            assert source['format'] == 'prose'
            text, kind = source['text'], 'chunk'
            metadata['is_table'] = False
            for value in source['values']:
                addresses[value['key']] = (source_id, None, value['surface'])
        carriers.append({'candidate_id': source_id, 'evidence_id': source_id, 'candidate_kind': kind,
            'source_anchor': f'[{document} | synthetic source {source_id}]',
            'text': text, 'source_text_exact': text, 'metadata': metadata})
    if reverse_carriers:
        carriers.reverse()
    catalog = build_semantic_candidate_catalog(carriers)
    selected = {}
    for key, (source_id, value_id, surface) in addresses.items():
        matches = []
        for candidate in catalog:
            if candidate['kind'] != 'numeric' or candidate['source_candidate_id'] != source_id:
                continue
            if value_id is not None:
                matched = candidate.get('physical_value_id') == value_id
            else:
                start, end = candidate['source_bundle_value_span']
                matched = candidate['source_bundle_text'][start:end] == surface
            if matched:
                matches.append(candidate['candidate_id'])
        if len(matches) != 1:
            raise AssertionError(f'Fixture source address {key} has {len(matches)} matches')
        selected[key] = matches[0]
    return {'case_id': source_case['case_id'], 'question': source_case['question'],
        'obligations': [AnswerObligation.model_validate(o).model_dump() for o in source_case['obligations']],
        'candidate_catalog': catalog, 'fixture_candidate_ids': selected}


def authored_program(case, criterion):
    """Only the offline witness calls this; transport capture takes no criterion."""
    ids = case['fixture_candidate_ids']
    owners = {o['obligation_id']: o for o in case['obligations']}
    expressions, prose_ids = [], set()
    for row in criterion['expressions']:
        bindings = []
        for binding in row['bindings']:
            if 'source_key' in binding:
                source_id = ids[binding['source_key']]
                bindings.append({'variable': binding['variable'], 'source_id': source_id,
                                 'source_requirement_id': binding['requirement_id']})
                prose_ids.add(source_id)
            else:
                bindings.append({'variable': binding['variable'], 'source_id': binding['dependency_id']})
        display = ids[row['source_display_key']] if row.get('source_display_key') else None
        if display:
            prose_ids.add(display)
        expressions.append({'obligation_id': row['obligation_id'], 'variable_bindings': bindings,
            'comparison_request_unit_id': row.get('comparison_request_unit_id'), 'formula': row['formula'],
            'display_unit': owners[row['obligation_id']]['display_unit'], 'source_display_candidate_id': display,
            'source_display_reason': 'Authored source-plus-calculation witness.' if display else 'Authored calculation-only witness.'})
    assertions = []
    for bundle in build_semantic_source_bundles(case['candidate_catalog']):
        candidates = [c for c in bundle.candidate_ids if c in prose_ids]
        if bundle.source_kind == 'prose_sentence' and candidates:
            assertions.append({'source_bundle_id': bundle.source_bundle_id, 'candidate_ids': candidates,
                               'evidence_text': bundle.source_text})
    program = {'status': 'ready', 'rationale': 'Explicit offline witness; not a model response.',
               'expressions': expressions, 'source_assertions': assertions}
    return authored_source_program(program, case['obligations'], case['candidate_catalog'], case['question'])


class AuthoredQueue:
    def __init__(self, programs, mutate=None):
        self.programs, self.mutate = list(deepcopy(programs)), mutate
        self.models, self.wires, self.messages = [], [], []

    def with_structured_output(self, model, *, include_raw):
        self.models.append(model)
        return self

    def invoke(self, prompt):
        if not self.programs:
            raise AssertionError('Unexpected compiler invocation; no inferred fixture repair')
        model = self.models[-1]
        raw = project_offline_program_to_wire(self.programs.pop(0), model)
        if self.mutate:
            self.mutate(raw, len(self.wires), model)
        self.wires.append(deepcopy(raw))
        self.messages.append([{'type': m.type, 'content': m.content} for m in prompt.to_messages()])
        try:
            return {'raw': None, 'parsed': model.model_validate(raw), 'parsing_error': None}
        except Exception as exc:
            return {'raw': None, 'parsed': None, 'parsing_error': exc}


def compile_case(case, programs, *, mutate=None):
    captured = []
    def factory(template):
        delegate = chat_prompt_template_from_template(template)
        def invoke(values):
            captured.append(deepcopy(values))
            return delegate.invoke(values)
        return SimpleNamespace(invoke=invoke)
    queue = AuthoredQueue(programs, mutate)
    state = _case_state(case, case['candidate_catalog'])
    state['include_debug_bundle'] = True
    before = deepcopy(state)
    with patch('src.agent.financial_graph_calculation.chat_prompt_template_from_template', side_effect=factory):
        compiled = _CompilerOnlyAgent(_RecordingLLM(queue))._compile_semantic_calculation_program(state)
    assert state == before, 'Compilation mutated its input'
    return compiled, queue, captured


def execute(case, compiled):
    return execute_semantic_calculation_program(program=compiled['semantic_program'], obligations=case['obligations'],
        candidate_catalog=case['candidate_catalog'], query=case['question'],
        compilation_envelope=compiled['semantic_compilation_envelope'], require_compilation_envelope=True)


class CaptureStop(BaseException):
    pass


def capture_initial(case):
    """Capture before any answer exists, not by replaying an authored answer."""
    class Capture:
        def with_structured_output(self, model, *, include_raw):
            self.model = model
            return self
        def invoke(self, prompt):
            self.messages = [{'type': m.type, 'content': m.content} for m in prompt.to_messages()]
            raise CaptureStop()
    capture = Capture()
    try:
        _CompilerOnlyAgent(_RecordingLLM(capture))._compile_semantic_calculation_program(_case_state(case, case['candidate_catalog']))
    except CaptureStop:
        return capture.model, capture.messages
    raise AssertionError('No initial compiler call was captured')
