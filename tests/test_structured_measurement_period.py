"""Authored semantic periods: linkage and execution, never model accuracy."""
from copy import deepcopy
import json
import socket
import unittest
from unittest.mock import patch

from jsonschema import Draft202012Validator, ValidationError as SchemaError
from pydantic import ValidationError

from src.agent.financial_calculation_execution import source_candidate_applicability
from src.agent.financial_graph import compilation_phase_input, planning_phase_input, retrieval_phase_input
from src.agent.financial_graph_models import AnswerObligationScope, RequirementPlannerOutput, SemanticCalculationProgram
from src.agent.financial_measurement_periods import (
    measurement_period_requirement_errors, period_contract_error, source_date_shape,
)
from src.agent.financial_reconciliation_candidates import build_semantic_candidate_catalog
from src.agent.financial_compiler_presentation import project_output_responsibility_context
from src.utils.openai_structured import strict_openai_schema
from tests.semantic_program_test_support import _StructuredQueueLLM
from tests.source_interpretation_fixture_support import authored_source_program
from tests.test_planner_requirement_transport import agent_for, request


def period(kind, **fields):
    return dict(kind=kind, **({} if kind=='unspecified' else dict(request_unit_ids=['request_001'])), **fields)


def owner(text='', spec=None, *, kind='direct_value', children=()):
    scope=dict(period=text, company='Issuer')
    if spec is not None:
        scope['measurement_period']=deepcopy(spec)
    return dict(kind=kind, label='quantity', scope=scope, evidence_requirements=list(children),
                request_unit_ids=['request_001'])


def cell(label, *, name='value', value=17, report_year=2042):
    source=dict(candidate_id=name, candidate_kind='structured_value',
        source_anchor=f'[Issuer | {report_year} | quantities]', text=f'quantity | {label} | {value} USD',
        metadata=dict(company='Issuer', year=report_year, row_label='quantity', row_headers=['quantity'],
            table_source_id='table', physical_table_id='table', physical_row_id=name,
            structured_cells=[dict(cell_id=name+':value', column_headers=[label],
                                   value_text=str(value), unit_hint='USD')]))
    return next(row for row in build_semantic_candidate_catalog([source]) if row['kind']=='numeric')


class StructuredMeasurementPeriodTests(unittest.TestCase):
    def setUp(self):
        for name in ('connect','connect_ex'):
            self.enterContext(patch.object(socket.socket, name, side_effect=AssertionError('network forbidden')))

    def plan(self, rows, query='Return the requested quantity.'):
        response=RequirementPlannerOutput.model_validate(dict(obligations=deepcopy(rows)))
        before=response.model_dump()
        llm=_StructuredQueueLLM(response)
        agent=agent_for(llm)
        state=request(query, intent='numeric_fact')
        state['requirements']=agent._plan_answer_obligation_program(planning_phase_input(state))
        self.assertEqual(response.model_dump(), before)
        return agent,state,llm

    def finish(self, agent, state, llm, catalog, *, selected=None, program=None):
        if program is None:
            program=dict(direct_bindings=[dict(obligation_id='ob_001', candidate_id=selected or catalog[0]['candidate_id'])])
        enriched=authored_source_program(program,state['requirements']['answer_obligations'],catalog,state['request']['query'])
        response=SemanticCalculationProgram.model_validate(enriched)
        llm.responses.extend([deepcopy(response),deepcopy(response)])
        state['candidates']=dict(semantic_source_candidates=[],semantic_candidate_catalog=deepcopy(catalog))
        before=deepcopy((state['request'],state['requirements'],state['candidates']))
        state['compilation']=agent._compile_semantic_calculation_program(compilation_phase_input(state))
        state.update(agent._execute_numeric_phase(state))
        state.update(agent._assemble_final_phase(state))
        state.update(agent._assemble_ledger_phase(state))
        self.assertEqual((state['request'],state['requirements'],state['candidates']),before)
        self.assertEqual(state['ledger']['task_artifact_trace']['integrity_status'],'ok')
        return state['final_result']['agent_answer']

    def test_relative_anchor_is_added_to_offset_not_matched_as_target(self):
        for anchor,offset in ((1998,-2),(2042,-1),(2057,0),(2034,2)):
            with self.subTest(anchor=anchor,offset=offset):
                spec=period('relative_year',anchor_year=anchor,year_offset=offset)
                row=owner(f'period relative to {anchor}',spec)
                candidate=cell(str(anchor+offset),report_year=2060)
                self.assertEqual(source_candidate_applicability(candidate,row)['field_states']['period'],'match')
                wrong=cell(str(anchor+offset+1),report_year=2060)
                self.assertEqual(source_candidate_applicability(wrong,row)['field_states']['period'],'conflict')
                agent,state,llm=self.plan([row])
                answer=self.finish(agent,state,llm,[candidate])
                self.assertEqual(answer['structured_result']['status'],'ok')
                self.assertEqual(len(llm.prompts),2)

    def test_relative_anchor_does_not_override_explicit_source_year(self):
        row=owner('preceding period',period('relative_year',anchor_year=2042,year_offset=-1))
        for label,expected in (('전기','match'),('2041 전기','match'),('2038 전기','conflict'),('당기','conflict')):
            self.assertEqual(source_candidate_applicability(cell(label),row)['field_states']['period'],expected)

    def test_exact_intervals_execute_across_years_and_within_year(self):
        for start,end,label in (
            ('2041-07-01','2042-06-30','2041년 7월 1일부터 2042년 6월 30일까지'),
            ('2041-07-01','2042-06-30','2041.07.01 ~ 2042.06.30'),
            ('2042-01-01','2042-03-31','2042-01-01 to 2042-03-31'),
        ):
            with self.subTest(label=label):
                row=owner('requested full interval',period('date_interval',start_date=start,end_date=end))
                candidate=cell(label)
                before=deepcopy(candidate)
                self.assertEqual(source_candidate_applicability(candidate,row)['field_states']['period'],'match')
                agent,state,llm=self.plan([row])
                answer=self.finish(agent,state,llm,[candidate])
                self.assertEqual(answer['structured_result']['status'],'ok')
                self.assertEqual(len(llm.prompts),2)
                self.assertEqual(candidate,before)
                operands=answer['resolved_calculation_trace']['calculation_operands']
                self.assertEqual(operands[0]['source_period_surface'],label)
                self.assertNotEqual(operands[0]['period'],'requested full interval')

    def test_interval_rejects_annual_partial_wrong_endpoint_and_point_substitutes(self):
        row=owner('full interval',period('date_interval',start_date='2041-07-01',end_date='2042-06-30'))
        for label in ('2041','2042','2042-01-01 to 2042-03-31','2041-07-02 to 2042-06-30',
                      '2041-07-01 to 2042-06-29','2042-06-30'):
            with self.subTest(label=label):
                candidate=cell(label)
                self.assertEqual(source_candidate_applicability(candidate,row)['field_states']['period'],'conflict')
                agent,state,llm=self.plan([row])
                answer=self.finish(agent,state,llm,[candidate])
                self.assertEqual(answer['structured_result']['status'],'incomplete')
                self.assertEqual(llm.models,['RequirementPlannerOutput'])

    def test_point_date_does_not_become_year_or_interval(self):
        row=owner('point',period('date',date='2042-06-30'))
        for label,expected in (('2042.6.30','match'),('2042','conflict'),('2042-06-29','conflict'),
                              ('2042-06-30 to 2042-06-30','conflict')):
            self.assertEqual(source_candidate_applicability(cell(label),row)['field_states']['period'],expected)

    def test_unknown_invalid_and_unjoined_source_dates_cannot_match(self):
        row=owner('interval',period('date_interval',start_date='2041-07-01',end_date='2042-06-30'))
        for label in ('amount','2041-07-01 ~ 06-30','2041-02-30 to 2042-06-30','2042-06-30 to 2041-07-01'):
            self.assertEqual(source_candidate_applicability(cell(label),row)['field_states']['period'],'unknown')
        candidate=cell('2041-07-01')
        candidate.update(column_headers=['2041-07-01','2042-06-30'],source_period_surface='2041-07-01 / 2042-06-30')
        self.assertEqual(source_date_shape(candidate),('unknown',))
        self.assertEqual(source_candidate_applicability(candidate,row)['field_states']['period'],'unknown')

    def test_unresolved_period_cannot_borrow_report_year_or_source_match(self):
        row=owner('unresolved',period('unresolved'))
        candidate=cell('2042')
        self.assertEqual(source_candidate_applicability(candidate,row)['field_states']['period'],'unknown')
        agent,state,llm=self.plan([row])
        answer=self.finish(agent,state,llm,[candidate])
        self.assertEqual(answer['structured_result']['status'],'incomplete')

    def test_legacy_complex_periods_are_unchanged_but_no_longer_year_sets(self):
        for label in ('2042사업연도의 직전 사업연도','2041년 7월 1일부터 2042년 6월 30일까지','2041 or 2042'):
            row=owner(label)
            agent,state,llm=self.plan([row])
            saved=deepcopy(state['requirements'])
            answer=self.finish(agent,state,llm,[cell('2042')])
            self.assertEqual(answer['structured_result']['status'],'incomplete')
            self.assertEqual(state['requirements'],saved)
            scope=state['requirements']['answer_obligations'][0]['scope']
            self.assertEqual(scope['period'],label)
            self.assertNotIn('measurement_period',scope)

    def test_blank_period_is_unrestricted_and_document_filter_is_unchanged(self):
        for spec in (None,period('unspecified')):
            agent,state,llm=self.plan([owner('',spec)])
            answer=self.finish(agent,state,llm,[cell('2030')])
            self.assertEqual(answer['structured_result']['status'],'ok')
            self.assertEqual(agent._build_scope_plan(retrieval_phase_input(state))['years'],[2042])

    def test_child_inherits_structure_only_with_blank_period(self):
        parent=period('relative_year',anchor_year=2042,year_offset=-1)
        children=[dict(label='inherited'),dict(label='own label',scope=dict(period='2040')),
                  dict(label='own structure',scope=dict(period='2043',measurement_period=period('year',year=2043)))]
        _,state,_=self.plan([owner('previous year',parent,kind='derived_value',children=children)])
        output=state['requirements']['answer_obligations'][0]
        first,second,third=output['evidence_requirements']
        self.assertEqual(first['scope']['measurement_period'],parent)
        self.assertNotIn('measurement_period',second['scope'])
        self.assertEqual(third['scope']['measurement_period']['year'],2043)
        self.assertEqual(source_candidate_applicability(cell('2040'),second,output)['state'],'compatible')
        self.assertEqual(source_candidate_applicability(cell('2041'),second,output)['state'],'explicit_conflict')
        first['scope']['measurement_period']['request_unit_ids'].append('mutated')
        self.assertEqual(output['scope']['measurement_period']['request_unit_ids'],['request_001'])

    def test_explicit_child_structure_does_not_inherit_parent_display_period(self):
        child=dict(label='own period',scope=dict(measurement_period=period('year',year=2043)))
        _,state,_=self.plan([owner('previous year',period('relative_year',anchor_year=2042,year_offset=-1),
                                 kind='derived_value',children=[child])])
        requirement=state['requirements']['answer_obligations'][0]['evidence_requirements'][0]
        self.assertEqual(requirement['scope']['period'],'')
        self.assertEqual(requirement['scope']['measurement_period']['year'],2043)

    def test_child_constraints_control_comparison_binding_and_execution(self):
        for reverse in (False,True):
            years=[2040,2041] if not reverse else [2041,2040]
            children=[dict(label=f'input {year}',scope=dict(period=str(year),measurement_period=period('year',year=year))) for year in years]
            row=owner('comparison',period('unresolved'),kind='derived_value',children=children)
            agent,state,llm=self.plan([row],query='Calculate the change between the requested inputs.')
            candidates=[cell(str(year),name=str(year),value=value) for year,value in ((2040,100),(2041,120))]
            by_year={c['value_year']:c for c in candidates}
            program=dict(expressions=[dict(obligation_id='ob_001',formula='(target - reference) / reference * 100',
                comparison_request_unit_id='request_001',source_display_candidate_id=None,source_display_reason='Calculated change requested.',
                variable_bindings=[dict(variable=variable,source_id=by_year[year]['candidate_id'],source_requirement_id=f'ob_001:req_00{index}')
                                   for index,(variable,year) in enumerate(zip(('reference','target'),years),1)])])
            answer=self.finish(agent,state,llm,candidates,program=program)
            value=answer['resolved_calculation_trace']['calculation_result']['outputs'][0]['normalized_value']
            self.assertAlmostEqual(value,-100/6 if reverse else 20)

    def test_owned_period_references_block_foreign_or_missing_ids_before_compiler(self):
        for ref in ('request_002','request_999'):
            row=owner('year',period('year',year=2041))
            row['scope']['measurement_period']['request_unit_ids']=[ref]
            other=owner()
            other['request_unit_ids']=['request_002']
            agent,state,llm=self.plan([row,other],query='Return the quantity. Explain the result.')
            errors=state['requirements']['semantic_plan']['requirement_errors']
            self.assertIn('unowned_measurement_period_request',[e['code'] for e in errors])
            # Recheck outside planning as well, with the original query.
            self.assertIn('unowned_measurement_period_request',[e['code'] for e in measurement_period_requirement_errors(
                state['requirements']['answer_obligations'],state['request']['query'])])

    def test_unowned_constraint_is_rejected_without_any_compiler_call(self):
        row=owner('year',dict(kind='year',year=2041,request_unit_ids=['request_999']))
        agent,state,llm=self.plan([row])
        answer=self.finish(agent,state,llm,[cell('2041')])
        self.assertEqual(answer['structured_result']['status'],'incomplete')
        self.assertEqual(llm.models,['RequirementPlannerOutput'])

    def test_shared_anchor_request_units_are_preserved(self):
        spec=period('relative_year',anchor_year=2042,year_offset=-1)
        spec['request_unit_ids']=['request_001','request_002']
        row=owner('prior period',spec)
        row['request_unit_ids']=['request_001','request_002']
        _,state,_=self.plan([row],query='Return the preceding quantity. Use 2042 as the current year.')
        self.assertEqual(state['requirements']['semantic_plan']['requirement_errors'],[])
        self.assertEqual(state['requirements']['answer_obligations'][0]['scope']['measurement_period'],spec)

    def test_malformed_structures_fail_python_and_mapping_validation(self):
        specs=[period('year',year=True),period('year',year='2042'),period('relative_year',anchor_year=1,year_offset=-1),
               period('date',date='2041-02-29'),period('date',date='2042-6-30'),
               period('date_interval',start_date='2042-07-01',end_date='2042-06-30'),
               dict(kind='year',year=2042,request_unit_ids=['request_001','request_001']),
               dict(kind='unspecified',year=2042)]
        for spec in specs:
            with self.subTest(spec=spec):
                self.assertTrue(period_contract_error(spec))
                with self.assertRaises(ValidationError):
                    AnswerObligationScope(measurement_period=spec)

    def test_wire_requires_nonnull_structure_and_preserves_supported_anyof(self):
        schema=strict_openai_schema(RequirementPlannerOutput)
        scope=schema['$defs']['AnswerObligationScope']
        self.assertIn('measurement_period',scope['required'])
        field=scope['properties']['measurement_period']
        self.assertEqual(len(field['anyOf']),6)
        self.assertNotIn({'type':'null'},field['anyOf'])
        # Defaults keep old internal fixtures readable, never an on-wire fallback.
        raw=RequirementPlannerOutput(obligations=[owner('year',period('year',year=2042))]).model_dump()
        validator=Draft202012Validator(schema)
        validator.validate(raw)
        for mutation in ('missing','null'):
            invalid=deepcopy(raw)
            if mutation=='missing':
                invalid['obligations'][0]['scope'].pop('measurement_period')
            else:
                invalid['obligations'][0]['scope']['measurement_period']=None
            with self.assertRaises(SchemaError):
                validator.validate(invalid)

    def test_structure_survives_compiler_prompt_and_responsibility_projection(self):
        spec=period('relative_year',anchor_year=2042,year_offset=-1)
        agent,state,llm=self.plan([owner('previous year',spec)])
        self.finish(agent,state,llm,[cell('2041')])
        self.assertIn('measurement_period',str(llm.prompts[1]))
        self.assertIn('year_offset',str(llm.prompts[1]))
        context=project_output_responsibility_context(state['request']['query'],state['requirements']['answer_obligations'])
        self.assertEqual(context['outputs'][0]['scope']['measurement_period'],spec)

    def test_actual_sdk_serializes_period_union_and_returns_original_structures(self):
        import httpx
        from src.config.llm_profiles import app_llm_routing_config
        from src.utils.gemini_usage import GeminiUsageCallbackHandler
        from tests.test_openai_compiler_transport import response_body
        specs=[period('unspecified'),period('unresolved'),period('year',year=2041),
               period('relative_year',anchor_year=2042,year_offset=-1),
               period('date',date='2042-06-30'),
               period('date_interval',start_date='2041-07-01',end_date='2042-06-30')]
        response=RequirementPlannerOutput(obligations=[owner('authored period',spec) for spec in specs])
        agent=agent_for(None)
        agent.llm_usage_callback=GeminiUsageCallbackHandler()
        route=dict(app_llm_routing_config('openai')['llm_routes']['default'],api_key='offline-placeholder')
        sent=[]
        def send(request, **kwargs):
            sent.append(json.loads(request.content))
            body=response_body(response.model_dump())
            body['model']=route['model']
            return httpx.Response(200,request=request,json=body)
        with patch.object(httpx.Client,'send',side_effect=send):
            agent.llm=agent._create_chat_model(route,phase='requirement_planning')
            state=request('Return each requested quantity.',intent='numeric_fact')
            result=agent._plan_answer_obligation_program(planning_phase_input(state))
        self.assertEqual(result['semantic_plan']['requirement_errors'],[])
        self.assertEqual([row['scope']['measurement_period'] for row in result['answer_obligations']],specs)
        body,=sent
        self.assertTrue(body['text']['format']['strict'])
        Draft202012Validator(body['text']['format']['schema']).validate(response.model_dump())

    def test_v2_rejects_changed_period_after_compilation(self):
        agent,state,llm=self.plan([owner('year',period('year',year=2041))])
        self.finish(agent,state,llm,[cell('2041')])
        state['requirements']['answer_obligations'][0]['scope']['measurement_period']['year']=2042
        result=agent._execute_numeric_phase(state)
        self.assertIn('execution_content_mismatch',json.dumps(result))

    def test_wrong_but_well_formed_semantic_period_is_not_certified(self):
        # Deliberately wrong Planner interpretation: linkage cannot read intent.
        row=owner('wrong year',period('year',year=2042))
        agent,state,llm=self.plan([row],query='Return the 2041 quantity.')
        answer=self.finish(agent,state,llm,[cell('2042')])
        self.assertEqual(answer['structured_result']['status'],'ok')


if __name__=='__main__':
    unittest.main()
