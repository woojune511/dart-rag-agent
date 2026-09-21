"""Annotated reference transport must preserve constraints and original models."""
from copy import deepcopy
import json
import os
import socket
import unittest
from unittest.mock import patch

import httpx
from jsonschema import Draft202012Validator
from openai.lib._pydantic import to_strict_json_schema
from pydantic import BaseModel, ConfigDict, Field
from typing import Literal

from src.utils.openai_structured import strict_openai_schema


class Entry(BaseModel):
    model_config = ConfigDict(extra='forbid')
    code: Literal['A', 'B']
    quantity: int = Field(ge=1, le=9)


class Envelope(BaseModel):
    model_config = ConfigDict(extra='forbid')
    item: Entry = Field(title='Selected entry', description='The explicitly selected entry.')


def sample():
    return dict(type='object', properties={
        'selected': {'$ref': '#/$defs/Entry', 'description': 'Selected use', 'title': 'Selection'},
        'other': {'$ref': '#/$defs/Entry'},
    }, required=['selected', 'other'], additionalProperties=False, **{'$defs': {'Entry': Entry.model_json_schema()}})


class OpenAISchemaReferenceTests(unittest.TestCase):
    def test_annotated_model_matches_native_sdk_projection(self):
        before = deepcopy(Envelope.model_json_schema())
        projected = strict_openai_schema(Envelope)
        self.assertEqual(projected, to_strict_json_schema(Envelope))
        self.assertNotIn('$ref', projected['properties']['item'])
        self.assertEqual(Envelope.model_json_schema(), before)

    def test_inlined_constraints_have_the_same_validation_results(self):
        source = sample()
        before = deepcopy(source)
        projected = strict_openai_schema(source)
        self.assertNotIn('$ref', projected['properties']['selected'])
        self.assertEqual(projected['properties']['other'], source['properties']['other'])
        self.assertEqual(projected['$defs'], source['$defs'])
        self.assertEqual(source, before)
        original_validator, wire_validator = Draft202012Validator(source), Draft202012Validator(projected)
        valid = {'code': 'A', 'quantity': 3}
        values = [valid, {'code': 'B', 'quantity': 1}, {'code': 'C', 'quantity': 3},
            {'code': 'A', 'quantity': 0}, {'code': 'A', 'quantity': 10},
            {'code': 'A', 'quantity': 2.5}, {'code': 'A'}, valid | {'invented': True}, None]
        for value in values:
            payload = dict(selected=value, other=valid)
            with self.subTest(value=value):
                self.assertEqual(original_validator.is_valid(payload), wire_validator.is_valid(payload))

    def test_annotation_override_never_mutates_shared_definition(self):
        source = sample()
        source['$defs']['Entry']['description'] = 'Definition description'
        projected = strict_openai_schema(source)
        selected = projected['properties']['selected']
        self.assertEqual(selected['description'], 'Selected use')
        self.assertEqual(selected['title'], 'Selection')
        self.assertEqual(projected['$defs']['Entry']['description'], 'Definition description')
        selected['properties']['quantity']['minimum'] = 100
        self.assertEqual(projected['$defs']['Entry']['properties']['quantity']['minimum'], 1)
        self.assertEqual(source['$defs']['Entry']['properties']['quantity']['minimum'], 1)

    def test_annotations_in_arrays_unions_and_reference_chains_expand(self):
        source = dict(type='object', properties={'items': dict(type='array', items={
            'anyOf': [{'$ref': '#/$defs/Alias', 'description': 'Use context'}, {'type': 'null'}]})},
            **{'$defs': {'Alias': {'$ref': '#/$defs/Value', 'title': 'Alias title'},
                'Value': {'type': 'integer', 'minimum': 2, 'maximum': 8}}})
        projected = strict_openai_schema(source)
        item = projected['properties']['items']['items']['anyOf'][0]
        self.assertEqual(item, dict(type='integer', minimum=2, maximum=8, title='Alias title', description='Use context'))
        self.assertEqual(projected['$defs']['Value'], source['$defs']['Value'])
        self.assertEqual(projected['properties']['items']['items']['anyOf'][1], {'type': 'null'})

    def test_escaped_local_pointer_preserves_named_definition(self):
        source = dict(type='object', properties={'item': {'$ref': '#/$defs/A~1B~0C', 'title': 'Use'}},
            **{'$defs': {'A/B~C': {'type': 'string', 'enum': ['x', 'y']}}})
        projected = strict_openai_schema(source)
        self.assertEqual(projected['properties']['item'], {'type': 'string', 'enum': ['x', 'y'], 'title': 'Use'})
        self.assertEqual(projected['$defs'], source['$defs'])

    def test_validation_siblings_are_rejected_instead_of_overriding_constraints(self):
        for key, value in [('minimum', 0), ('type', 'string'), ('enum', [0]),
                           ('required', []), ('properties', {}), ('additionalProperties', True)]:
            source = dict(type='object', properties={'item': {'$ref': '#/$defs/Value', key: value}},
                **{'$defs': {'Value': {'type': 'integer', 'minimum': 2}}})
            before = deepcopy(source)
            with self.subTest(key=key), self.assertRaises(ValueError):
                strict_openai_schema(source)
            self.assertEqual(source, before)

    def test_unresolved_nonlocal_or_invalid_annotated_pointer_is_rejected(self):
        for ref in ('#/$defs/Missing', 'https://example.invalid/schema.json', '#named-anchor',
                    '#/$defs/A~2B', 3):
            source = dict(type='object', properties={'item': {'$ref': ref, 'description': 'Use'}},
                **{'$defs': {'A~2B': {'type': 'integer'}}})
            with self.subTest(ref=ref), self.assertRaises(ValueError):
                strict_openai_schema(source)

    def test_non_schema_reference_target_is_rejected(self):
        source = dict(type='object', properties={'item': {'$ref': '#/required', 'description': 'Use'}}, required=['item'])
        with self.assertRaises(ValueError):
            strict_openai_schema(source)

    def test_cyclic_annotation_expansion_fails_without_recursion_error(self):
        for definitions in (
            {'A': {'$ref': '#/$defs/A', 'description': 'Self'}},
            {'A': {'$ref': '#/$defs/B', 'description': 'A'}, 'B': {'$ref': '#/$defs/A', 'description': 'B'}},
            {'A': {'type': 'object', 'properties': {'next': {'$ref': '#/$defs/A', 'description': 'Next'}}}},
        ):
            source = dict(type='object', properties={'item': {'$ref': '#/$defs/A'}}, **{'$defs': definitions})
            with self.subTest(definitions=definitions), self.assertRaises(ValueError):
                strict_openai_schema(source)

    def test_bare_recursive_references_remain_unchanged(self):
        source = dict(type='object', properties={'next': {'anyOf': [{'$ref': '#'}, {'type': 'null'}]}},
            required=['next'], additionalProperties=False)
        self.assertEqual(strict_openai_schema(source), source)

    def test_referenced_unsupported_constraints_still_fail(self):
        for shape in ({'allOf': [{'type': 'integer'}]}, {'type': 'object', 'additionalProperties': True}):
            source = dict(type='object', properties={'item': {'$ref': '#/$defs/Value', 'description': 'Use'}},
                **{'$defs': {'Value': shape}})
            with self.subTest(shape=shape), self.assertRaises(ValueError):
                strict_openai_schema(source)

    def test_actual_sdk_receives_expanded_shape_and_rejects_invalid_values(self):
        from src.agent.financial_graph import FinancialAgent
        from src.utils.gemini_usage import GeminiUsageCallbackHandler
        from tests.test_openai_compiler_transport import ROUTE, response_body
        agent = object.__new__(FinancialAgent)
        agent.llm_usage_callback = GeminiUsageCallbackHandler()
        with patch.object(socket.socket, 'connect', side_effect=AssertionError('Network forbidden')), \
             patch.object(socket.socket, 'connect_ex', side_effect=AssertionError('Network forbidden')), \
             patch.dict(os.environ, LANGSMITH_TRACING='false', LANGCHAIN_TRACING_V2='false'):
            model = agent._create_chat_model(ROUTE, phase='program_compilation')
            for quantity in (3, 0, 10):
                sent = []
                def send(client, request, **kwargs):
                    sent.append(json.loads(request.content))
                    return httpx.Response(200, request=request, json=response_body({'item': {'code': 'A', 'quantity': quantity}}))
                with self.subTest(quantity=quantity), patch.object(httpx.Client, 'send', send):
                    result = model.with_structured_output(Envelope, include_raw=True).invoke('Read the selected entry.')
                self.assertEqual(len(sent), 1)
                field = sent[0]['text']['format']['schema']['properties']['item']
                self.assertNotIn('$ref', field)
                self.assertEqual(field['properties']['quantity']['minimum'], 1)
                if quantity == 3:
                    self.assertIsNone(result['parsing_error'])
                    self.assertEqual(result['parsed'].item.quantity, 3)
                else:
                    self.assertIsNotNone(result['parsing_error'])
                    self.assertIsNone(result['parsed'])


if __name__ == '__main__':
    unittest.main()
