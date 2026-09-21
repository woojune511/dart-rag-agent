"""Uniform Planner declarations, strict admission and unchanged internal meaning."""
from copy import deepcopy
import json
import os
import socket
import unittest
from unittest.mock import patch

import httpx
from jsonschema import Draft202012Validator, ValidationError as SchemaError
from pydantic import ValidationError

from src.agent.financial_graph import planning_phase_input
from src.agent.financial_graph_models import RequirementPlannerOutput
from src.agent.financial_planner_period_wire import PlannerMeasurementPeriod
from src.utils.gemini_usage import GeminiUsageCallbackHandler
from src.utils.openai_structured import strict_openai_schema
from tests.planner_period_wire_test_support import declared_period
from tests.semantic_program_test_support import _StructuredQueueLLM
from tests.test_openai_compiler_transport import response_body
from tests.test_planner_requirement_transport import agent_for, request
from tests.test_structured_measurement_period import owner, period, cell
from src.agent.financial_calculation_execution import source_candidate_applicability
from src.agent.financial_compiler_presentation import project_output_responsibility_context


class PlannerPeriodWireTests(unittest.TestCase):
    def setUp(self):
        for name in ('connect', 'connect_ex'):
            self.enterContext(patch.object(socket.socket, name, side_effect=AssertionError('network forbidden')))
        self.enterContext(patch.dict(os.environ, LANGSMITH_TRACING='false', LANGCHAIN_TRACING_V2='false'))

    def payload(self, value):
        raw=RequirementPlannerOutput(obligations=[owner('requested period')]).model_dump()
        raw['obligations'][0]['scope']['measurement_period']=deepcopy(value)
        return raw

    def test_generation_has_one_fixed_object_and_seven_required_fields(self):
        schema=strict_openai_schema(RequirementPlannerOutput)
        scope=schema['$defs']['PlannerAnswerObligationScope']
        field=scope['properties']['measurement_period']
        self.assertNotIn('$ref',field)
        shape=schema['$defs']['PlannerMeasurementPeriod']
        self.assertEqual(field['properties'],shape['properties'])
        self.assertEqual(field['required'],shape['required'])
        self.assertFalse(field['additionalProperties'])
        self.assertEqual(set(shape['required']), {'precision','reference_year','year_offset','coverage','start_date','end_date','request_unit_ids'})
        self.assertNotIn('anyOf',shape)
        self.assertFalse(shape['additionalProperties'])
        self.assertNotIn('YearMeasurementPeriod',schema['$defs'])
        validator=Draft202012Validator(schema)
        value=declared_period('year',reference_year=2037,year_offset=0,coverage='within_year')
        raw=self.payload(value)
        validator.validate(raw)
        for field in value:
            changed=deepcopy(raw); del changed['obligations'][0]['scope']['measurement_period'][field]
            with self.subTest(field=field),self.assertRaises(SchemaError):validator.validate(changed)

    def test_absolute_and_relative_years_lower_without_fiscal_dates(self):
        for offset in (-2,0,3):
            for coverage in ('whole_year','within_year'):
                value=declared_period('year',reference_year=2037,year_offset=offset,coverage=coverage)
                expected=period('relative_year',anchor_year=2037,year_offset=offset,coverage=coverage) if offset else period('year',year=2037,coverage=coverage)
                with self.subTest(offset=offset,coverage=coverage):
                    self.assertEqual(PlannerMeasurementPeriod.model_validate(value).to_internal(),expected)

    def test_point_and_equal_endpoint_interval_keep_distinct_geometry(self):
        for precision in ('date','date_interval'):
            value=declared_period(precision,start_date='2036-02-29',end_date='2036-02-29' if precision=='date_interval' else None)
            result=PlannerMeasurementPeriod.model_validate(value).to_internal()
            self.assertEqual(result['kind'],precision)
            self.assertNotIn('year',result)
        interval=declared_period('date_interval',start_date='2035-10-01',end_date='2036-09-30')
        self.assertEqual(PlannerMeasurementPeriod.model_validate(interval).to_internal(),period('date_interval',start_date='2035-10-01',end_date='2036-09-30'))

    def test_unspecified_and_unresolved_remain_distinct(self):
        for precision in ('unspecified','unresolved'):
            self.assertEqual(PlannerMeasurementPeriod.model_validate(declared_period(precision)).to_internal(),period(precision))

    def test_required_and_inactive_field_combinations_fail_instead_of_being_discarded(self):
        year=declared_period('year',reference_year=2037,year_offset=0,coverage='whole_year')
        bad=[year|{name:None} for name in ('reference_year','year_offset','coverage')]
        bad += [year|{'start_date':'2037-01-01'},year|{'end_date':'2037-12-31'},
            declared_period('date',start_date='2037-04-30',coverage='within_year'),
            declared_period('date',start_date='2037-04-30',end_date='2037-04-30'),
            declared_period('date_interval',start_date='2037-04-30'),
            declared_period('unresolved',reference_year=2037),declared_period('unspecified',year_offset=0)]
        for value in bad:
            with self.subTest(value=value),self.assertRaises(ValidationError):RequirementPlannerOutput.model_validate(self.payload(value))

    def test_types_bounds_and_calendar_errors_cannot_reach_execution(self):
        year=declared_period('year',reference_year=2037,year_offset=0,coverage='whole_year')
        bad=[year|{name:value} for name in ('reference_year','year_offset') for value in (True,2.5,'2037')]
        bad += [year|{'reference_year':value} for value in (0,10000)]
        bad += [year|{'reference_year':1,'year_offset':-1},year|{'reference_year':9999,'year_offset':1},
            declared_period('date',start_date='2037-02-29'),declared_period('date',start_date='2037-2-03'),
            declared_period('date_interval',start_date='2037-05-01',end_date='2037-04-30')]
        for value in bad:
            with self.subTest(value=value),self.assertRaises(ValidationError):PlannerMeasurementPeriod.model_validate(value)

    def test_request_references_are_required_unique_and_owned(self):
        for refs in ([],[''],['request_001','request_001']):
            with self.subTest(refs=refs),self.assertRaises(ValidationError):
                PlannerMeasurementPeriod.model_validate(declared_period('unresolved',request_unit_ids=refs))
        with self.assertRaises(ValidationError):
            PlannerMeasurementPeriod.model_validate(declared_period('unspecified',request_unit_ids=['request_001']))
        value=declared_period('year',reference_year=2037,year_offset=0,coverage='whole_year',request_unit_ids=['request_002'])
        model=RequirementPlannerOutput.model_validate(self.payload(value))
        planned=agent_for(_StructuredQueueLLM(model))._plan_answer_obligation_program(planning_phase_input(request('Return quantity. Use the complete year.')))
        self.assertIn('unowned_measurement_period_request',[e['code'] for e in planned['semantic_plan']['requirement_errors']])

    def test_old_internal_periods_remain_readable_without_entering_generation(self):
        schema=Draft202012Validator(strict_openai_schema(RequirementPlannerOutput))
        for spec in (None,period('year',year=2037),period('relative_year',anchor_year=2038,year_offset=-1),
                     period('unresolved'),period('date_interval',start_date='2037-01-01',end_date='2037-12-31')):
            raw=RequirementPlannerOutput(obligations=[owner('old period',spec)]).model_dump()
            before=deepcopy(raw)
            self.assertEqual(RequirementPlannerOutput.model_validate(raw).model_dump(),before)
            with self.assertRaises(SchemaError):schema.validate(raw)
            self.assertEqual(raw,before)

    def test_generation_wire_and_internal_serialization_are_separate(self):
        raw=self.payload(declared_period('year',reference_year=2037,year_offset=0,coverage='within_year'))
        before=deepcopy(raw)
        model=RequirementPlannerOutput.model_validate(raw)
        serialized=model.model_dump()
        self.assertEqual(raw,before)
        self.assertEqual(serialized['obligations'][0]['scope']['measurement_period'],period('year',year=2037,coverage='within_year'))
        self.assertEqual(RequirementPlannerOutput.model_validate(serialized).model_dump(),serialized)

    def test_child_inheritance_and_compiler_context_preserve_declared_meaning(self):
        value=declared_period('year',reference_year=2038,year_offset=-1,coverage='within_year')
        raw=self.payload(value); row=raw['obligations'][0]; row['kind']='derived_value'
        row['evidence_requirements']=[dict(label='quantity',scope=dict(period='',measurement_period=declared_period('unspecified')))]
        model=RequirementPlannerOutput.model_validate(raw)
        planned=agent_for(_StructuredQueueLLM(model))._plan_answer_obligation_program(planning_phase_input(request('Return quantity.')))
        output=planned['answer_obligations'][0]
        self.assertEqual(output['scope']['measurement_period'],output['evidence_requirements'][0]['scope']['measurement_period'])
        projected=project_output_responsibility_context('Return quantity.',[output])
        self.assertEqual(projected['outputs'][0]['scope']['measurement_period'],period('relative_year',anchor_year=2038,year_offset=-1,coverage='within_year'))
        self.assertEqual(source_candidate_applicability(cell('2037-04-30'),output)['field_states']['period'],'match')
        self.assertEqual(source_candidate_applicability(cell('2038-04-30'),output)['field_states']['period'],'conflict')

    def test_source_defined_group_copies_typed_scope_without_wire_reinterpretation(self):
        raw=self.payload(declared_period('year',reference_year=2037,year_offset=0,coverage='whole_year'))
        raw['obligations'][0].update(kind='narrative',evidence_mode='source_defined_group')
        model=RequirementPlannerOutput.model_validate(raw)
        output=model.obligations[0]
        self.assertEqual(output.scope.model_dump(),output.evidence_requirements[0].scope.model_dump())
        self.assertIsNot(output.scope,output.evidence_requirements[0].scope)

    def test_wrong_well_formed_fields_remain_semantic_negatives(self):
        for value in (declared_period('unresolved'),declared_period('date_interval',start_date='2037-01-01',end_date='2037-12-31')):
            model=RequirementPlannerOutput.model_validate(self.payload(value))
            model.rationale='The requested target is a whole named year.'
            planned=agent_for(_StructuredQueueLLM(model))._plan_answer_obligation_program(planning_phase_input(request('Return the whole-year quantity.')))
            self.assertEqual(planned['answer_obligations'][0]['scope']['measurement_period']['kind'],value['precision'])

    def test_real_sdk_accepts_valid_wire_and_blocks_incompatible_fields(self):
        agent=agent_for(None); agent.llm_usage_callback=GeminiUsageCallbackHandler()
        route=dict(provider='openai',model='gpt-5.6-terra',temperature=None,max_output_tokens=8192,
            reasoning_effort='low',provider_client_retries=0,use_responses_api=True,store=False,
            service_tier='default',timeout_seconds=90,api_key='offline-placeholder')
        model=agent._create_chat_model(route,phase='requirement_planning')
        valid=declared_period('year',reference_year=2037,year_offset=0,coverage='within_year')
        for value in (valid,valid|{'coverage':None},period('year',year=2037,coverage='within_year')):
            sent=[]
            def send(client,req,**kwargs):
                sent.append(json.loads(req.content))
                return httpx.Response(200,request=req,json=response_body(self.payload(value)))
            with patch.object(httpx.Client,'send',send):
                result=model.with_structured_output(RequirementPlannerOutput,include_raw=True).invoke('Authored period fixture')
            self.assertEqual(len(sent),1)
            if value==valid:
                self.assertIsNone(result['parsing_error'])
                self.assertEqual(result['parsed'].obligations[0].scope.measurement_period.coverage,'within_year')
            else:
                self.assertIsNotNone(result['parsing_error'])
                self.assertIsNone(result['parsed'])


if __name__=='__main__':
    unittest.main()
