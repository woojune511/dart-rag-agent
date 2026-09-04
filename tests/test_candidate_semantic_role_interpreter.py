from __future__ import annotations

import copy
import hashlib
import json
import unittest

from src.ops.candidate_semantic_role_interpreter import (
    REQUEST_SCHEMA,
    StructuredOutputCandidateSemanticRoleInterpreter,
    build_request_bundle,
    collect_interpreter_responses,
    evaluate_response_bundle,
    project_response_bundle,
    render_request_prompt,
)
from src.ops.semantic_tiebreaker_promotion_gate import build_pairs


SOURCE_TEXT = "A 20 credit adjustment raised total profit to 100."


def _fixture() -> dict:
    def prose_candidate(candidate_id: str, raw_value: str) -> dict:
        start = SOURCE_TEXT.index(raw_value)
        return {
            "candidate_id": candidate_id,
            "candidate_text": SOURCE_TEXT,
            "candidate": {
                "candidate_kind": "sentence_value",
                "raw_value": raw_value,
                "normalized_value": float(raw_value),
                "source_span": [start, start + len(raw_value)],
            },
            "fact_role": {
                "source_kind": "prose",
                "grounding_state": "unresolved",
            },
        }

    return {
        "schema": "semantic_candidate_tiebreak_hard_negatives_v1",
        "gate_id": "test",
        "thresholds": {},
        "cases": [
            {
                "case_id": "case-1",
                "cohort_id": "cohort-1",
                "owner_id": "owner-1",
                "query": "Which value is the credit adjustment?",
                "expected_action": "select",
                "acceptable_top_candidate_ids": ["candidate-component"],
                "baseline_candidate_ids": [
                    "candidate-total",
                    "candidate-component",
                ],
                "owner": {
                    "obligation_id": "owner-1",
                    "label": "credit adjustment",
                    "output_kind": "numeric",
                },
                "parent_owner": None,
                "resolved_target": {
                    "local_subjects": [],
                    "concept_keys": [],
                    "metric_surfaces": ["credit adjustment"],
                },
                "candidates": [
                    prose_candidate("candidate-total", "100"),
                    prose_candidate("candidate-component", "20"),
                ],
            }
        ],
    }


def _decisions(request: dict) -> list[dict]:
    return [
        {
            "candidate_id": "candidate-component",
            "status": "grounded",
            "subject_surfaces": ["credit adjustment"],
            "relation_surfaces": ["20 credit adjustment"],
            "value_role": "adjustment_component",
        },
        {
            "candidate_id": "candidate-total",
            "status": "grounded",
            "subject_surfaces": ["total profit"],
            "relation_surfaces": ["total profit to 100"],
            "value_role": "reported_total",
        },
    ]


def _refresh_response_fingerprint(response_bundle: dict) -> None:
    response_bundle.pop("response_bundle_fingerprint", None)
    serialized = json.dumps(
        response_bundle,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    response_bundle["response_bundle_fingerprint"] = hashlib.sha256(
        serialized.encode("utf-8")
    ).hexdigest()


class _Interpreter:
    def __init__(self) -> None:
        self.requests: list[dict] = []

    def interpret(self, request: dict) -> dict:
        self.requests.append(copy.deepcopy(request))
        return {"decisions": _decisions(request)}


class _StructuredLlm:
    def __init__(self) -> None:
        self.schema = None
        self.prompts: list[str] = []

    def with_structured_output(self, schema: object) -> "_StructuredLlm":
        self.schema = schema
        return self

    def invoke(self, prompt: str) -> dict:
        self.prompts.append(prompt)
        return {"decisions": _decisions({})}


class CandidateSemanticRoleInterpreterTests(unittest.TestCase):
    def test_request_groups_same_source_and_excludes_answer_labels(self) -> None:
        fixture = _fixture()
        request_bundle = build_request_bundle(fixture)

        self.assertEqual(request_bundle["request_count"], 1)
        self.assertEqual(request_bundle["candidate_count"], 2)
        request = request_bundle["requests"][0]
        self.assertEqual(request["schema"], REQUEST_SCHEMA)
        self.assertEqual(
            [candidate["candidate_id"] for candidate in request["candidates"]],
            ["candidate-component", "candidate-total"],
        )
        serialized = json.dumps(request, ensure_ascii=False)
        self.assertNotIn("acceptable_top_candidate_ids", serialized)
        self.assertNotIn(fixture["cases"][0]["query"], serialized)
        prompt = render_request_prompt(request)
        self.assertIn(SOURCE_TEXT, prompt)
        self.assertIn("do not select an answer", prompt)

    def test_interpreter_roles_are_projected_and_rebuilt_per_candidate(self) -> None:
        fixture = _fixture()
        request_bundle = build_request_bundle(fixture)
        interpreter = _Interpreter()
        response_bundle = collect_interpreter_responses(
            request_bundle,
            interpreter,
        )
        projected = project_response_bundle(
            fixture,
            request_bundle,
            response_bundle,
        )

        self.assertEqual(len(interpreter.requests), 1)
        self.assertEqual(
            projected["semantic_role_projection"]["grounded_candidate_ids"],
            ["candidate-component", "candidate-total"],
        )
        pairs = {pair.candidate_id: pair for pair in build_pairs(projected)}
        self.assertEqual(
            pairs["candidate-component"].fact_role.value_role,
            "adjustment_component",
        )
        self.assertEqual(
            pairs["candidate-total"].fact_role.value_role,
            "reported_total",
        )
        self.assertIn(
            "Candidate relations: 20 credit adjustment",
            pairs["candidate-component"].evidence_text,
        )

    def test_structured_output_adapter_uses_bounded_prompt(self) -> None:
        request_bundle = build_request_bundle(_fixture())
        llm = _StructuredLlm()
        interpreter = StructuredOutputCandidateSemanticRoleInterpreter(llm)

        response_bundle = collect_interpreter_responses(
            request_bundle,
            interpreter,
        )

        self.assertIsNotNone(llm.schema)
        self.assertEqual(len(llm.prompts), 1)
        self.assertIn(SOURCE_TEXT, llm.prompts[0])
        self.assertNotIn("Which value is", llm.prompts[0])
        self.assertEqual(len(response_bundle["responses"]), 1)

    def test_relation_for_another_value_is_rejected(self) -> None:
        fixture = _fixture()
        request_bundle = build_request_bundle(fixture)
        interpreter = _Interpreter()
        response_bundle = collect_interpreter_responses(
            request_bundle,
            interpreter,
        )
        response_bundle["responses"][0]["decisions"][0][
            "relation_surfaces"
        ] = ["total profit to 100"]
        _refresh_response_fingerprint(response_bundle)

        with self.assertRaisesRegex(ValueError, "must contain candidate value"):
            project_response_bundle(fixture, request_bundle, response_bundle)

    def test_interpreter_gate_compares_role_and_subject(self) -> None:
        request_bundle = build_request_bundle(_fixture())
        expected = collect_interpreter_responses(
            request_bundle,
            _Interpreter(),
        )

        matched = evaluate_response_bundle(request_bundle, expected, expected)
        self.assertEqual(matched["status"], "matched")
        self.assertEqual(matched["accuracy"], 1.0)

        actual = copy.deepcopy(expected)
        actual["responses"][0]["decisions"][0]["value_role"] = "reported_total"
        _refresh_response_fingerprint(actual)
        mismatched = evaluate_response_bundle(request_bundle, expected, actual)
        self.assertEqual(mismatched["status"], "needs_review")
        self.assertEqual(mismatched["accuracy"], 0.5)

    def test_non_unique_value_surface_stays_out_of_requests(self) -> None:
        fixture = _fixture()
        candidate = fixture["cases"][0]["candidates"][0]
        candidate["candidate_text"] = "The total was 100 and later remained 100."
        candidate["candidate"]["source_span"] = None

        request_bundle = build_request_bundle(fixture)

        self.assertEqual(request_bundle["candidate_count"], 1)
        self.assertEqual(
            request_bundle["skipped_candidates"],
            [
                {
                    "candidate_id": "candidate-total",
                    "reason": "value_surface_not_unique",
                }
            ],
        )


if __name__ == "__main__":
    unittest.main()
