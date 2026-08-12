from __future__ import annotations

import ast
import json
import unittest
from collections.abc import Mapping
from contextlib import ExitStack
from copy import deepcopy
from pathlib import Path
from typing import Any
from unittest.mock import Mock, patch

from src.agent import financial_graph_calculation, financial_graph_reconciliation, financial_task_artifacts
from src.agent.financial_graph import FinancialAgent
from src.agent.financial_task_artifacts import enrich_reconciliation_artifact_refs


class FinancialTaskArtifactRefTests(unittest.TestCase):
    def enrich(
        self,
        artifacts,
        *,
        task_id,
        operand_rows,
        extra_refs=None,
        task_ids=None,
    ):
        return enrich_reconciliation_artifact_refs(
            artifacts,
            task_id=task_id,
            operand_rows=operand_rows,
            extra_refs=extra_refs,
            task_ids=task_ids,
        )

    @staticmethod
    def artifact(
        artifact_id: str,
        task_id: str,
        *,
        kind: str = "reconciliation_result",
        result: Any = None,
        evidence_refs=None,
    ):
        reconciliation_result = {"status": "ready"} if result is None else result
        return {
            "artifact_id": artifact_id,
            "task_id": task_id,
            "kind": kind,
            "payload": {"reconciliation_result": reconciliation_result},
            "evidence_refs": list(evidence_refs or []),
            "nested": {"keep": artifact_id},
        }

    def test_reconciliation_ref_enrichment_preserves_empty_and_ordered_source_contracts(self) -> None:
        self.assertIn("enrich_reconciliation_artifact_refs", financial_task_artifacts.__all__)
        self.assertNotIn("_calculation_operand_source_refs", financial_task_artifacts.__all__)

        class ExplodingString:
            def __str__(self):
                raise RuntimeError("task id accessed")

        class ExplodingIterable:
            def __iter__(self):
                raise RuntimeError("iterated")

        class ExplodingArtifacts:
            def __bool__(self):
                raise RuntimeError("artifact truthiness accessed")

            def __iter__(self):
                raise RuntimeError("artifacts iterated")

        untouched_artifacts = ExplodingArtifacts()
        self.assertIs(
            self.enrich(
                untouched_artifacts,
                task_id=ExplodingString(),
                task_ids=ExplodingIterable(),
                operand_rows=[],
            ),
            untouched_artifacts,
        )
        empty_artifacts = []
        enriched_empty = self.enrich(
            empty_artifacts,
            task_id="",
            operand_rows=[{"evidence_id": "ref"}],
        )
        self.assertEqual(enriched_empty, [])
        self.assertIsNot(enriched_empty, empty_artifacts)

        source_keys = [
            "evidence_id",
            "evidence_ids",
            "source_evidence_id",
            "source_evidence_ids",
            "source_row_id",
            "source_row_ids",
            "row_id",
            "row_ids",
            "candidate_id",
            "candidate_ids",
        ]
        access_events = []

        class TrackedRow(dict):
            def get(self, key, default=None):
                access_events.append(key)
                return super().get(key, default)

        class SkippedMapping(Mapping):
            def __len__(self):
                raise RuntimeError("strict mapping length accessed")

            def __iter__(self):
                raise RuntimeError("strict mapping iterated")

            def __getitem__(self, key):
                raise RuntimeError(f"strict mapping accessed: {key}")

        operand = TrackedRow(
            {
                "evidence_id": "ev_1",
                "evidence_ids": ["ev_2", "dup"],
                "source_evidence_id": "source_ev_1",
                "source_evidence_ids": ("source_ev_2", "ev_1"),
                "source_row_id": "source_row_1",
                "source_row_ids": ["source_row_2", ["source_row_3"]],
                "row_id": "row_1",
                "row_ids": ["row_2"],
                "candidate_id": "candidate_1",
                "candidate_ids": ["candidate_2", "ev_2"],
            }
        )
        eligible = self.artifact(
            "artifact:eligible",
            "task_1",
            evidence_refs=["existing", "", "ev_1", "existing"],
        )
        ignored = self.artifact(
            "artifact:ignored",
            "task_1",
            kind="operand_set",
            evidence_refs=["ignored-existing"],
        )
        artifacts = [eligible, ignored]
        artifacts_before = deepcopy(artifacts)

        updated = self.enrich(
            artifacts,
            task_id="task_1",
            operand_rows=[SkippedMapping(), operand],
            extra_refs=["extra_1", ["extra_2", "ev_1"], None, "null", "nan"],
        )

        self.assertEqual(access_events, source_keys)
        self.assertEqual(
            updated[0]["evidence_refs"],
            [
                "existing",
                "",
                "ev_1",
                "ev_2",
                "dup",
                "source_ev_1",
                "source_ev_2",
                "source_row_1",
                "source_row_2",
                "source_row_3",
                "row_1",
                "row_2",
                "candidate_1",
                "candidate_2",
                "extra_1",
                "extra_2",
            ],
        )
        self.assertEqual(updated[1]["evidence_refs"], ["ignored-existing"])
        self.assertEqual(artifacts, artifacts_before)
        self.assertIsNot(updated, artifacts)
        for copied, original in zip(updated, artifacts):
            self.assertIsNot(copied, original)
            self.assertIs(copied["payload"], original["payload"])
            self.assertIs(copied["nested"], original["nested"])

    def test_reconciliation_ref_enrichment_target_and_artifact_gate_matrix(self) -> None:
        def targeted_artifacts():
            return [
                self.artifact("artifact:primary", "primary"),
                self.artifact("artifact:extra", "extra", result={"status": " OK "}),
                self.artifact("artifact:other", "other"),
            ]

        for name, task_id, task_ids, expected in (
            ("blank targets all", " ", None, {"primary", "extra", "other"}),
            ("single", " primary ", None, {"primary"}),
            ("union", "primary", [" extra ", "", "primary"], {"primary", "extra"}),
        ):
            with self.subTest(target=name):
                updated = self.enrich(
                    targeted_artifacts(),
                    task_id=task_id,
                    task_ids=task_ids,
                    operand_rows=[{"evidence_id": "new_ref"}],
                )
                self.assertEqual(
                    {
                        item["task_id"]
                        for item in updated
                        if item.get("evidence_refs") == ["new_ref"]
                    },
                    expected,
                )

        class CountingString:
            def __init__(self, value):
                self.value = value
                self.calls = 0

            def __str__(self):
                self.calls += 1
                return self.value

        repeated_task_id = CountingString("extra")
        self.enrich(
            targeted_artifacts(),
            task_id="primary",
            task_ids=[repeated_task_id],
            operand_rows=[{"evidence_id": "new_ref"}],
        )
        self.assertEqual(repeated_task_id.calls, 2)

        gate_artifacts = [
            self.artifact("artifact:ready", "task_ready"),
            self.artifact("artifact:ok", "task_ok", result={"status": " OK "}),
            self.artifact(
                "artifact:wrong-kind",
                "task_wrong_kind",
                kind="Reconciliation_Result",
            ),
            self.artifact("artifact:retry", "task_retry", result={"status": "retry"}),
            self.artifact("artifact:bad-result", "task_bad_result", result=[]),
            {
                **self.artifact("artifact:bad-payload", "task_bad_payload"),
                "payload": [],
            },
        ]
        updated = self.enrich(
            gate_artifacts,
            task_id="",
            operand_rows=[{"source_row_id": "new_ref"}],
        )
        self.assertEqual(
            [item["artifact_id"] for item in updated if item.get("evidence_refs") == ["new_ref"]],
            ["artifact:ready", "artifact:ok"],
        )
        self.assertTrue(all(item is not original for item, original in zip(updated, gate_artifacts)))

    def test_reconciliation_ref_enrichment_preserves_exception_and_access_order(self) -> None:
        class TruthBomb:
            def __bool__(self):
                raise RuntimeError("truthiness")

        class IterBomb:
            def __bool__(self):
                return True

            def __iter__(self):
                raise RuntimeError("iteration")

        class StrBomb:
            def __str__(self):
                raise RuntimeError("string")

        with self.assertRaisesRegex(RuntimeError, "truthiness"):
            self.enrich([], task_id="", operand_rows=TruthBomb())
        with self.assertRaisesRegex(RuntimeError, "truthiness"):
            self.enrich([], task_id="", operand_rows=[], extra_refs=TruthBomb())
        with self.assertRaisesRegex(RuntimeError, "iteration"):
            self.enrich(
                [],
                task_id="",
                operand_rows=[{"evidence_id": "ref"}],
                task_ids=IterBomb(),
            )
        with self.assertRaisesRegex(RuntimeError, "string"):
            self.enrich(
                IterBomb(),
                task_id=StrBomb(),
                operand_rows=[{"evidence_id": "ref"}],
            )

        source_keys = [
            "evidence_id",
            "evidence_ids",
            "source_evidence_id",
            "source_evidence_ids",
            "source_row_id",
            "source_row_ids",
            "row_id",
            "row_ids",
            "candidate_id",
            "candidate_ids",
        ]
        access_events = []

        class ExplodingRow(dict):
            def get(self, key, default=None):
                access_events.append(key)
                return StrBomb() if key == "evidence_id" else super().get(key, default)

        with self.assertRaisesRegex(RuntimeError, "string"):
            self.enrich([], task_id="", operand_rows=[ExplodingRow()])
        self.assertEqual(access_events, source_keys)

        class CopyBomb(Mapping):
            def __len__(self):
                return 1

            def __iter__(self):
                raise RuntimeError("dict copy")

            def __getitem__(self, key):
                raise RuntimeError(f"dict item: {key}")

        with self.assertRaisesRegex(RuntimeError, "dict copy"):
            self.enrich(
                [CopyBomb()],
                task_id="",
                operand_rows=[{"evidence_id": "ref"}],
            )

        payload_events = []

        class Payload(dict):
            def get(self, key, default=None):
                payload_events.append(key)
                raise RuntimeError("payload access")

        payload_artifact = self.artifact("artifact:payload", "task_1")
        payload_artifact["payload"] = Payload()
        with self.assertRaisesRegex(RuntimeError, "payload access"):
            self.enrich(
                [payload_artifact],
                task_id="task_1",
                operand_rows=[{"evidence_id": "ref"}],
            )
        self.assertEqual(payload_events, ["reconciliation_result"])

        class PoisonString:
            def __str__(self):
                raise RuntimeError("later gate accessed")

        self.enrich(
            [
                {
                    "kind": "operand_set",
                    "task_id": PoisonString(),
                    "payload": Payload(),
                }
            ],
            task_id="task_1",
            operand_rows=[{"evidence_id": "ref"}],
        )
        self.enrich(
            [
                {
                    "kind": "reconciliation_result",
                    "task_id": "other_task",
                    "payload": Payload(),
                }
            ],
            task_id="task_1",
            operand_rows=[{"evidence_id": "ref"}],
        )

        status_events = []

        class StatusBomb(dict):
            def get(self, key, default=None):
                status_events.append(key)
                raise RuntimeError("status access")

        with self.assertRaisesRegex(RuntimeError, "status access"):
            self.enrich(
                [
                    {
                        "kind": "reconciliation_result",
                        "task_id": "task_1",
                        "payload": {"reconciliation_result": StatusBomb()},
                    }
                ],
                task_id="task_1",
                operand_rows=[{"evidence_id": "ref"}],
            )
        self.assertEqual(status_events, ["status"])

        unhashable = self.artifact(
            "artifact:unhashable",
            "task_1",
            evidence_refs=[[]],
        )
        with self.assertRaises(TypeError):
            self.enrich(
                [unhashable],
                task_id="task_1",
                operand_rows=[{"evidence_id": "ref"}],
            )

    def test_current_source_artifact_text_match_preserves_gate_order_and_exceptions(self) -> None:
        operand = {"label": "Alpha Beta", "nested": {"keep": True}}
        operand_before = deepcopy(operand)
        real_sub = financial_task_artifacts.re.sub

        events = []

        def normalise(value):
            events.append(("normalise", value))
            return " ".join(str(value).split())

        def operand_match(text, received_operand):
            events.append(("operand_match", text, received_operand))
            return text == "direct"

        def operand_needles(received_operand):
            events.append(("needles", received_operand))
            return [" ", "Alpha Beta", "later"]

        def compact(pattern, replacement, value):
            events.append(("compact", pattern, replacement, value))
            return real_sub(pattern, replacement, value)

        with patch.object(
            financial_task_artifacts,
            "_normalise_spaces",
            side_effect=normalise,
        ), patch.object(
            financial_task_artifacts,
            "_operand_text_match",
            side_effect=operand_match,
        ), patch.object(
            financial_task_artifacts,
            "_operand_needles",
            side_effect=operand_needles,
        ), patch.object(
            financial_task_artifacts.re,
            "sub",
            side_effect=compact,
        ):
            self.assertFalse(financial_task_artifacts._artifact_text_matches_operand_surface("   ", operand))
            self.assertEqual(events, [("normalise", "   ")])

            events.clear()
            self.assertTrue(financial_task_artifacts._artifact_text_matches_operand_surface(" direct ", operand))
            self.assertEqual(
                events,
                [
                    ("normalise", " direct "),
                    ("operand_match", "direct", operand),
                ],
            )

            events.clear()
            self.assertTrue(financial_task_artifacts._artifact_text_matches_operand_surface("AlphaBeta", operand))
            self.assertEqual(
                events,
                [
                    ("normalise", "AlphaBeta"),
                    ("operand_match", "AlphaBeta", operand),
                    ("compact", r"\s+", "", "AlphaBeta"),
                    ("needles", operand),
                    ("normalise", " "),
                    ("normalise", "Alpha Beta"),
                    ("compact", r"\s+", "", "Alpha Beta"),
                ],
            )

        for surface, needles, expected in (
            ("Alpha Beta Extra", ["AlphaBeta"], True),
            ("Alpha", ["Alpha Beta"], True),
            ("alpha beta", ["Alpha Beta"], False),
            ("Other", ["Alpha Beta", "Later"], False),
        ):
            with self.subTest(surface=surface, needles=needles):
                with patch.object(
                    financial_task_artifacts,
                    "_operand_text_match",
                    return_value=False,
                ), patch.object(
                    financial_task_artifacts,
                    "_operand_needles",
                    return_value=needles,
                ):
                    self.assertEqual(
                        financial_task_artifacts._artifact_text_matches_operand_surface(surface, operand),
                        expected,
                    )

        self.assertEqual(operand, operand_before)

        class TextStrBomb:
            def __str__(self):
                raise RuntimeError("text string")

        with self.assertRaisesRegex(RuntimeError, "text string"):
            financial_task_artifacts._artifact_text_matches_operand_surface(TextStrBomb(), operand)
        with patch.object(
            financial_task_artifacts,
            "_normalise_spaces",
            side_effect=RuntimeError("normalise failed"),
        ):
            with self.assertRaisesRegex(RuntimeError, "normalise failed"):
                financial_task_artifacts._artifact_text_matches_operand_surface("surface", operand)
        with patch.object(
            financial_task_artifacts,
            "_operand_text_match",
            side_effect=RuntimeError("operand match failed"),
        ):
            with self.assertRaisesRegex(RuntimeError, "operand match failed"):
                financial_task_artifacts._artifact_text_matches_operand_surface("surface", operand)
        with patch.object(
            financial_task_artifacts,
            "_operand_text_match",
            return_value=False,
        ), patch.object(
            financial_task_artifacts.re,
            "sub",
            side_effect=RuntimeError("compact failed"),
        ), patch.object(
            financial_task_artifacts,
            "_operand_needles",
            side_effect=AssertionError("needles must stay lazy"),
        ):
            with self.assertRaisesRegex(RuntimeError, "compact failed"):
                financial_task_artifacts._artifact_text_matches_operand_surface("surface", operand)
        with patch.object(
            financial_task_artifacts,
            "_operand_text_match",
            return_value=False,
        ), patch.object(
            financial_task_artifacts,
            "_operand_needles",
            side_effect=RuntimeError("needles failed"),
        ):
            with self.assertRaisesRegex(RuntimeError, "needles failed"):
                financial_task_artifacts._artifact_text_matches_operand_surface("surface", operand)

    def test_current_source_operand_artifact_candidates_preserve_match_and_fallback_contracts(self) -> None:
        operand = {"label": "Target", "nested": {"keep": True}}
        operand_before = deepcopy(operand)
        state = {
            "artifacts": [
                {
                    "artifact_id": "wrong-case",
                    "kind": "Reconciliation_Result",
                    "payload": {"reconciliation_result": {"matched_operands": []}},
                    "evidence_refs": ["wrong"],
                },
                {
                    "artifact_id": "matched",
                    "kind": "prepared_reconciliation_result_v1",
                    "payload": {
                        "reconciliation_result": {
                            "matched_operands": [
                                None,
                                {
                                    "label": "No label",
                                    "concept": "No concept",
                                    "role": "No role",
                                    "candidate_ids": ["not-used"],
                                },
                                {
                                    "label": "Target label",
                                    "concept": "must stay lazy",
                                    "role": "must stay lazy",
                                    "candidate_ids": [" first ", "dup", "", None],
                                    "nested": operand["nested"],
                                },
                            ]
                        }
                    },
                    "evidence_refs": ["matched-fallback-must-not-appear"],
                },
                {
                    "artifact_id": "fallback",
                    "kind": "reconciliation_result",
                    "payload": {
                        "reconciliation_result": {
                            "matched_operands": [
                                {
                                    "label": "Other",
                                    "concept": "Other concept",
                                    "role": "Other role",
                                    "candidate_ids": ["ignored"],
                                }
                            ]
                        }
                    },
                    "evidence_refs": [" fallback ", "dup", None],
                },
                {
                    "artifact_id": "matched-empty",
                    "kind": "reconciliation_result",
                    "payload": {
                        "reconciliation_result": {
                            "matched_operands": [
                                {
                                    "label": "Target empty",
                                    "concept": "lazy",
                                    "role": "lazy",
                                    "candidate_ids": [],
                                }
                            ]
                        }
                    },
                    "evidence_refs": ["empty-match-fallback-must-not-appear"],
                },
            ],
            "nested": {"keep": True},
        }
        state_before = deepcopy(state)
        matcher_calls = []

        def matcher(surface, received_operand):
            matcher_calls.append((surface, received_operand))
            return surface.startswith("Target")

        with patch.object(
            financial_task_artifacts,
            "_artifact_text_matches_operand_surface",
            side_effect=matcher,
        ):
            candidate_ids = financial_task_artifacts.reconciliation_artifact_candidate_ids_for_operand(
                state,
                operand=operand,
            )

        self.assertEqual(candidate_ids, ["first", "dup", "fallback"])
        self.assertEqual(
            [surface for surface, _ in matcher_calls],
            [
                "No label",
                "No concept",
                "No role",
                "Target label",
                "Other",
                "Other concept",
                "Other role",
                "Target empty",
            ],
        )
        self.assertTrue(all(received is operand for _, received in matcher_calls))
        self.assertEqual(state, state_before)
        self.assertEqual(operand, operand_before)
        self.assertIs(
            state["artifacts"][1]["payload"]["reconciliation_result"]["matched_operands"][2]["nested"],
            operand["nested"],
        )

        class AccessBomb(dict):
            def get(self, key, default=None):
                raise RuntimeError(f"unexpected access: {key}")

        class EvidenceBomb:
            def __bool__(self):
                raise RuntimeError("fallback accessed")

            def __iter__(self):
                raise RuntimeError("fallback iterated")

        lazy_state = {
            "artifacts": [
                {
                    "kind": "Reconciliation_Result",
                    "payload": AccessBomb(),
                    "evidence_refs": EvidenceBomb(),
                },
                {
                    "kind": "reconciliation_result",
                    "payload": {
                        "reconciliation_result": {
                            "matched_operands": [
                                {"label": "Target", "candidate_ids": ["selected"]}
                            ]
                        }
                    },
                    "evidence_refs": EvidenceBomb(),
                },
            ]
        }
        with patch.object(
            financial_task_artifacts,
            "_artifact_text_matches_operand_surface",
            return_value=True,
        ):
            self.assertEqual(
                financial_task_artifacts.reconciliation_artifact_candidate_ids_for_operand(
                    lazy_state,
                    operand=operand,
                ),
                ["selected"],
            )

        with patch.object(
            financial_task_artifacts,
            "_artifact_text_matches_operand_surface",
            side_effect=RuntimeError("match failed"),
        ):
            with self.assertRaisesRegex(RuntimeError, "match failed"):
                financial_task_artifacts.reconciliation_artifact_candidate_ids_for_operand(
                    {
                        "artifacts": [
                            {
                                "kind": "reconciliation_result",
                                "payload": {
                                    "reconciliation_result": {
                                        "matched_operands": [{"label": "surface"}]
                                    }
                                },
                            }
                        ]
                    },
                    operand=operand,
                )

        class PayloadCopyBomb(Mapping):
            def __len__(self):
                return 1

            def __iter__(self):
                raise RuntimeError("payload copy")

            def __getitem__(self, key):
                raise RuntimeError("payload copy")

        with self.assertRaisesRegex(RuntimeError, "payload copy"):
            financial_task_artifacts.reconciliation_artifact_candidate_ids_for_operand(
                {
                    "artifacts": [
                        {
                            "kind": "reconciliation_result",
                            "payload": PayloadCopyBomb(),
                        }
                    ]
                },
                operand=operand,
            )

        class CandidateStrBomb:
            def __str__(self):
                raise RuntimeError("candidate string")

        with patch.object(
            financial_task_artifacts,
            "_artifact_text_matches_operand_surface",
            return_value=True,
        ):
            with self.assertRaisesRegex(RuntimeError, "candidate string"):
                financial_task_artifacts.reconciliation_artifact_candidate_ids_for_operand(
                    {
                        "artifacts": [
                            {
                                "kind": "reconciliation_result",
                                "payload": {
                                    "reconciliation_result": {
                                        "matched_operands": [
                                            {
                                                "label": "surface",
                                                "candidate_ids": [CandidateStrBomb()],
                                            }
                                        ]
                                    }
                                },
                            }
                        ]
                    },
                    operand=operand,
                )

    def test_current_source_artifact_candidates_preserve_source_order_and_gates(self) -> None:
        state = {
            "reconciliation_result": {
                "evidence_refs": [" top_1 ", "", None],
                "source_evidence_ids": ["top_2", "top_1"],
            },
            "artifacts": [
                {
                    "artifact_id": "wrong",
                    "kind": "Reconciliation_Result",
                    "evidence_refs": ["wrong"],
                    "payload": {"reconciliation_result": {"evidence_refs": ["wrong"]}},
                },
                {
                    "artifact_id": "eligible",
                    "kind": "prepared_reconciliation_result_v2",
                    "evidence_refs": ["artifact_1", "top_1"],
                    "payload": {
                        "reconciliation_result": {
                            "evidence_refs": ["artifact_2", "artifact_1"],
                            "source_evidence_ids": ["artifact_3", "top_2"],
                        }
                    },
                },
            ],
            "nested": {"keep": True},
        }
        state_nested = state["nested"]
        state_before = deepcopy(state)

        candidate_ids = financial_task_artifacts.reconciliation_artifact_candidate_ids(state)

        self.assertEqual(
            candidate_ids,
            ["top_1", "top_2", "artifact_1", "artifact_2", "artifact_3"],
        )
        self.assertEqual(state, state_before)
        self.assertIs(state["nested"], state_nested)

        class AccessBomb(dict):
            def get(self, key, default=None):
                raise RuntimeError(f"unexpected access: {key}")

        self.assertEqual(
            financial_task_artifacts.reconciliation_artifact_candidate_ids(
                {
                    "reconciliation_result": {},
                    "artifacts": [
                        {
                            "kind": "Reconciliation_Result",
                            "evidence_refs": AccessBomb(),
                            "payload": AccessBomb(),
                        }
                    ],
                }
            ),
            [],
        )

        class CandidateStrBomb:
            def __str__(self):
                raise RuntimeError("candidate string")

        with self.assertRaisesRegex(RuntimeError, "candidate string"):
            financial_task_artifacts.reconciliation_artifact_candidate_ids(
                {
                    "reconciliation_result": {"evidence_refs": [CandidateStrBomb()]},
                    "artifacts": AccessBomb(),
                }
            )

        class KindStrBomb:
            def __str__(self):
                raise RuntimeError("kind string")

        with self.assertRaisesRegex(RuntimeError, "kind string"):
            financial_task_artifacts.reconciliation_artifact_candidate_ids(
                {
                    "reconciliation_result": {},
                    "artifacts": [{"kind": KindStrBomb()}],
                }
            )

        class CopyBomb(Mapping):
            def __init__(self, message):
                self.message = message

            def __len__(self):
                return 1

            def __iter__(self):
                raise RuntimeError(self.message)

            def __getitem__(self, key):
                raise RuntimeError(self.message)

        with self.assertRaisesRegex(RuntimeError, "top copy"):
            financial_task_artifacts.reconciliation_artifact_candidate_ids(
                {"reconciliation_result": CopyBomb("top copy")}
            )
        with self.assertRaisesRegex(RuntimeError, "artifact copy"):
            financial_task_artifacts.reconciliation_artifact_candidate_ids(
                {"reconciliation_result": {}, "artifacts": [CopyBomb("artifact copy")]}
            )
        with self.assertRaisesRegex(RuntimeError, "payload copy"):
            financial_task_artifacts.reconciliation_artifact_candidate_ids(
                {
                    "reconciliation_result": {},
                    "artifacts": [
                        {
                            "kind": "reconciliation_result",
                            "payload": CopyBomb("payload copy"),
                        }
                    ],
                }
            )
        with self.assertRaisesRegex(RuntimeError, "result copy"):
            financial_task_artifacts.reconciliation_artifact_candidate_ids(
                {
                    "reconciliation_result": {},
                    "artifacts": [
                        {
                            "kind": "reconciliation_result",
                            "payload": {
                                "reconciliation_result": CopyBomb("result copy")
                            },
                        }
                    ],
                }
            )

    def test_current_source_reconciliation_evidence_refs_preserve_flattening_and_access(self) -> None:
        source_keys = [
            "candidate_ids",
            "candidate_id",
            "source_row_ids",
            "source_row_id",
            "source_evidence_ids",
            "source_evidence_id",
            "evidence_ids",
            "evidence_id",
            "row_ids",
            "row_id",
        ]
        access_events = []

        class TrackedMatch(dict):
            def get(self, key, default=None):
                access_events.append(key)
                return super().get(key, default)

        class StrictMapping(Mapping):
            def __len__(self):
                raise RuntimeError("mapping length")

            def __iter__(self):
                raise RuntimeError("mapping iteration")

            def __getitem__(self, key):
                raise RuntimeError(f"mapping item: {key}")

        tracked = TrackedMatch(
            {
                "candidate_ids": [" first ", ("second", ["third", None, "null"])],
                "candidate_id": "fourth",
                "source_row_ids": {"fifth"},
                "source_row_id": "first",
                "source_evidence_ids": ["sixth", "nan"],
                "source_evidence_id": " seventh ",
                "evidence_ids": ("eighth", ""),
                "evidence_id": None,
                "row_ids": [["ninth", "second"]],
                "row_id": " tenth ",
            }
        )
        result = {
            "matched_operands": [StrictMapping(), tracked],
            "nested": {"keep": True},
        }
        result_before = deepcopy(result["nested"])

        refs = financial_task_artifacts.reconciliation_evidence_refs(result)

        self.assertEqual(
            refs,
            [
                "first",
                "second",
                "third",
                "fourth",
                "fifth",
                "sixth",
                "seventh",
                "eighth",
                "ninth",
                "tenth",
            ],
        )
        self.assertEqual(access_events, source_keys)
        self.assertEqual(result["nested"], result_before)
        self.assertIs(result["matched_operands"][1], tracked)

        result_events = []

        class ResultBomb(dict):
            def get(self, key, default=None):
                result_events.append(key)
                raise RuntimeError("result access")

        with self.assertRaisesRegex(RuntimeError, "result access"):
            financial_task_artifacts.reconciliation_evidence_refs(ResultBomb())
        self.assertEqual(result_events, ["matched_operands"])

        item_events = []

        class ItemBomb(dict):
            def get(self, key, default=None):
                item_events.append(key)
                if key == "source_row_id":
                    raise RuntimeError("item access")
                return None

        with self.assertRaisesRegex(RuntimeError, "item access"):
            financial_task_artifacts.reconciliation_evidence_refs({"matched_operands": [ItemBomb()]})
        self.assertEqual(item_events, source_keys[:4])

        class NestedIterBomb(list):
            def __iter__(self):
                raise RuntimeError("nested iteration")

        with self.assertRaisesRegex(RuntimeError, "nested iteration"):
            financial_task_artifacts.reconciliation_evidence_refs(
                {"matched_operands": [{"candidate_ids": [NestedIterBomb()]}]}
            )

        class RefStrBomb:
            def __str__(self):
                raise RuntimeError("ref string")

        with self.assertRaisesRegex(RuntimeError, "ref string"):
            financial_task_artifacts.reconciliation_evidence_refs(
                {"matched_operands": [{"candidate_ids": [RefStrBomb()]}]}
            )

    def test_current_source_reconciliation_artifact_bindings_pin_exact_move_boundary(self) -> None:
        graph_path = Path("src/agent/financial_graph_reconciliation.py")
        owner_path = Path("src/agent/financial_task_artifacts.py")
        graph_text = graph_path.read_text(encoding="utf-8-sig")
        owner_text = owner_path.read_text(encoding="utf-8-sig")
        graph_tree = ast.parse(graph_text)
        owner_tree = ast.parse(owner_text)
        selected_names = {
            "_artifact_text_matches_operand_surface",
            "reconciliation_artifact_candidate_ids_for_operand",
            "reconciliation_artifact_candidate_ids",
            "reconciliation_evidence_refs",
        }
        old_private_names = {
            f"_{name}"
            for name in selected_names
            if not name.startswith("_")
        }
        owner_definitions = {
            node.name: node
            for node in owner_tree.body
            if isinstance(node, ast.FunctionDef) and node.name in selected_names
        }
        self.assertEqual(set(owner_definitions), selected_names)
        self.assertEqual(
            {
                name: node.end_lineno - node.lineno + 1
                for name, node in owner_definitions.items()
            },
            {
                "_artifact_text_matches_operand_surface": 15,
                "reconciliation_artifact_candidate_ids_for_operand": 50,
                "reconciliation_artifact_candidate_ids": 29,
                "reconciliation_evidence_refs": 32,
            },
        )
        self.assertTrue(
            {
                "reconciliation_artifact_candidate_ids_for_operand",
                "reconciliation_artifact_candidate_ids",
                "reconciliation_evidence_refs",
            }.issubset(set(financial_task_artifacts.__all__))
        )
        self.assertNotIn(
            "_artifact_text_matches_operand_surface",
            financial_task_artifacts.__all__,
        )
        graph_class = next(
            node
            for node in graph_tree.body
            if isinstance(node, ast.ClassDef) and node.name == "FinancialAgentReconciliationMixin"
        )
        self.assertEqual(
            {
                node.name
                for node in graph_class.body
                if isinstance(node, ast.FunctionDef)
                and (node.name in selected_names or node.name in old_private_names)
            },
            set(),
        )
        self.assertTrue(all(f"self.{name}" not in graph_text for name in old_private_names))
        self.assertNotIn("_operand_text_match", graph_text)

        def collect_calls(tree, module_label):
            parent = {
                child: node
                for node in ast.walk(tree)
                for child in ast.iter_child_nodes(node)
            }

            def enclosing_function(node):
                current = parent.get(node)
                while current is not None and not isinstance(current, ast.FunctionDef):
                    current = parent.get(current)
                return current.name if isinstance(current, ast.FunctionDef) else ""

            calls = []
            non_call_loads = []
            for node in ast.walk(tree):
                target = None
                receiver = ""
                if isinstance(node, ast.Name) and node.id in selected_names:
                    target = node.id
                elif isinstance(node, ast.Attribute) and node.attr in selected_names:
                    target = node.attr
                    receiver = ast.unparse(node.value)
                else:
                    continue
                parent_node = parent.get(node)
                if not (
                    isinstance(parent_node, ast.Call)
                    and parent_node.func is node
                ):
                    non_call_loads.append((target, receiver, type(parent_node).__name__))
                    continue
                try_depth = 0
                current = parent.get(parent_node)
                while current is not None:
                    if isinstance(current, ast.Try):
                        try_depth += 1
                    current = parent.get(current)
                calls.append(
                    (
                        module_label,
                        target,
                        enclosing_function(parent_node),
                        receiver,
                        tuple(ast.unparse(arg) for arg in parent_node.args),
                        tuple(
                            (keyword.arg, ast.unparse(keyword.value))
                            for keyword in parent_node.keywords
                        ),
                        try_depth,
                    )
                )
            return calls, non_call_loads

        graph_calls, graph_non_calls = collect_calls(graph_tree, "graph")
        owner_calls, owner_non_calls = collect_calls(owner_tree, "owner")
        self.assertEqual(graph_non_calls, [])
        self.assertEqual(owner_non_calls, [])
        self.assertCountEqual(
            [*graph_calls, *owner_calls],
            [
                (
                    "owner",
                    "_artifact_text_matches_operand_surface",
                    "reconciliation_artifact_candidate_ids_for_operand",
                    "",
                    ("surface", "operand"),
                    (),
                    0,
                ),
                (
                    "graph",
                    "reconciliation_artifact_candidate_ids_for_operand",
                    "_extract_structured_operands_from_reconciliation",
                    "",
                    ("state",),
                    (("operand", "operand"),),
                    0,
                ),
                (
                    "graph",
                    "reconciliation_artifact_candidate_ids",
                    "_extract_structured_operands_from_reconciliation",
                    "",
                    ("state",),
                    (),
                    0,
                ),
                (
                    "graph",
                    "reconciliation_evidence_refs",
                    "_reconcile_retrieved_evidence",
                    "",
                    ("result",),
                    (),
                    0,
                ),
                (
                    "graph",
                    "reconciliation_evidence_refs",
                    "_reconcile_retrieved_evidence",
                    "",
                    ("result",),
                    (),
                    0,
                ),
            ],
        )
        self.assertEqual(len(graph_calls), 4)
        self.assertEqual(len(owner_calls), 1)

        task_artifact_imports = {
            alias.asname or alias.name
            for node in graph_tree.body
            if isinstance(node, ast.ImportFrom)
            and node.module == "src.agent.financial_task_artifacts"
            for alias in node.names
        }
        self.assertTrue(
            {
                "reconciliation_artifact_candidate_ids_for_operand",
                "reconciliation_artifact_candidate_ids",
                "reconciliation_evidence_refs",
            }.issubset(task_artifact_imports)
        )

        module_graph = {}
        for path in Path("src/agent").glob("*.py"):
            module_name = f"src.agent.{path.stem}"
            module_graph[module_name] = set()
            module_tree = ast.parse(path.read_text(encoding="utf-8-sig"))
            for node in ast.walk(module_tree):
                if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("src.agent."):
                    module_graph[module_name].add(node.module)
                elif isinstance(node, ast.Import):
                    module_graph[module_name].update(
                        alias.name
                        for alias in node.names
                        if alias.name.startswith("src.agent.")
                    )

        def reaches(start, target):
            pending = [start]
            seen = set()
            while pending:
                current = pending.pop()
                if current == target:
                    return True
                if current in seen:
                    continue
                seen.add(current)
                pending.extend(module_graph.get(current, ()))
            return False

        owner_module = "src.agent.financial_task_artifacts"
        for dependency in (
            "src.agent.financial_row_surfaces",
            "src.agent.financial_surface_contracts",
            "src.agent.financial_graph_state",
        ):
            self.assertFalse(reaches(dependency, owner_module), dependency)
        self.assertFalse(
            reaches(owner_module, "src.agent.financial_graph_reconciliation")
        )

        baseline = json.loads(
            (Path("tests") / "fixtures" / "runtime_domain_terms_baseline.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(len(baseline["records"]), 217)
        selected_lines = set()
        for node in owner_definitions.values():
            selected_lines.update(range(node.lineno, node.end_lineno + 1))
        self.assertEqual(
            [
                record
                for record in baseline["records"]
                if record.get("path") == "src/agent/financial_task_artifacts.py"
                and selected_lines.intersection(record.get("first_lines") or [])
            ],
            [],
        )

    def test_current_source_reconciliation_artifact_callers_pin_args_adoption_and_stop(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        nested = {"keep": True}
        original_operand = {
            "label": "Metric",
            "role": "numerator",
            "required": True,
            "nested": nested,
        }
        active_subtask = {
            "task_id": "task_ratio",
            "operation_family": "ratio",
            "required_operands": [original_operand],
            "constraints": {"period_focus": "current"},
            "preferred_statement_types": [],
        }
        structured_state = {
            "active_subtask": active_subtask,
            "reconciliation_result": {
                "status": "ready",
                "matched_operands": [
                    {
                        "label": "Metric",
                        "role": "numerator",
                        "candidate_ids": ["from_match"],
                    }
                ],
            },
            "report_scope": {},
            "nested": {"state": True},
        }
        structured_before = deepcopy(structured_state)
        structured_events = []
        completed_operands = []
        per_operand_calls = []
        all_candidate_calls = []
        expand_calls = []
        pair_calls = []
        final_rows = [{"row_id": "final"}]

        def active_owner(subtask, received_state):
            structured_events.append("active")
            self.assertIs(received_state, structured_state)
            self.assertIsNot(subtask, active_subtask)
            self.assertEqual(subtask, active_subtask)
            return active_subtask

        def complete_owner(operand):
            structured_events.append("complete")
            completed_operands.append(operand)
            return operand

        def query_years_owner(received_state):
            structured_events.append("years")
            self.assertIs(received_state, structured_state)
            return []

        def candidates_owner(received_state):
            structured_events.append("candidates")
            self.assertIs(received_state, structured_state)
            return []

        def pair_owner(**kwargs):
            structured_events.append("pair")
            pair_calls.append(kwargs)
            return [], set()

        def per_operand_owner(received_state, *, operand):
            structured_events.append("per_operand")
            per_operand_calls.append((received_state, operand))
            return ["from_operand"]

        def all_candidates_owner(received_state):
            structured_events.append("all_candidates")
            all_candidate_calls.append(received_state)
            return ["from_general"]

        def expand_owner(candidate_ids, candidate_map):
            structured_events.append("expand")
            expand_calls.append((candidate_ids, candidate_map))
            return []

        def repair_owner(rows, candidate_map):
            structured_events.append("repair")
            self.assertEqual(rows, [])
            self.assertEqual(candidate_map, {})
            return final_rows

        with patch.object(
            financial_graph_reconciliation,
            "active_subtask_with_sibling_lookup_surfaces",
            side_effect=active_owner,
        ), patch.object(
            agent,
            "_complete_required_operand_from_ontology",
            side_effect=complete_owner,
        ), patch.object(
            financial_graph_reconciliation,
            "_query_years_from_state",
            side_effect=query_years_owner,
        ), patch.object(
            agent,
            "_build_reconciliation_candidates",
            side_effect=candidates_owner,
        ), patch.object(
            agent,
            "_extract_structured_period_pair_rows",
            side_effect=pair_owner,
        ), patch.object(
            financial_graph_reconciliation,
            "reconciliation_artifact_candidate_ids_for_operand",
            side_effect=per_operand_owner,
        ), patch.object(
            financial_graph_reconciliation,
            "reconciliation_artifact_candidate_ids",
            side_effect=all_candidates_owner,
        ), patch.object(
            agent,
            "_expand_structured_candidate_ids",
            side_effect=expand_owner,
        ), patch.object(
            financial_graph_reconciliation,
            "repair_note_operand_units_from_same_block",
            side_effect=repair_owner,
        ):
            extracted = agent._extract_structured_operands_from_reconciliation(
                structured_state
            )

        self.assertIs(extracted, final_rows)
        self.assertEqual(
            structured_events,
            [
                "active",
                "complete",
                "years",
                "candidates",
                "pair",
                "per_operand",
                "all_candidates",
                "expand",
                "repair",
            ],
        )
        self.assertEqual(len(completed_operands), 1)
        completed_operand = completed_operands[0]
        self.assertIsNot(completed_operand, original_operand)
        self.assertIs(completed_operand["nested"], nested)
        self.assertEqual(per_operand_calls, [(structured_state, completed_operand)])
        self.assertEqual(all_candidate_calls, [structured_state])
        self.assertEqual(
            expand_calls,
            [(["from_match", "from_operand", "from_general"], {})],
        )
        self.assertIs(pair_calls[0]["required_operands"][0], completed_operand)
        self.assertEqual(structured_state, structured_before)
        self.assertIs(original_operand["nested"], nested)

        lookup_active = {
            **active_subtask,
            "operation_family": "lookup",
        }
        with patch.object(
            financial_graph_reconciliation,
            "active_subtask_with_sibling_lookup_surfaces",
            return_value=lookup_active,
        ), patch.object(
            agent,
            "_complete_required_operand_from_ontology",
            side_effect=lambda operand: operand,
        ), patch.object(
            financial_graph_reconciliation,
            "_query_years_from_state",
            return_value=[],
        ), patch.object(
            agent,
            "_build_reconciliation_candidates",
            return_value=[],
        ), patch.object(
            agent,
            "_extract_structured_period_pair_rows",
            return_value=([], set()),
        ), patch.object(
            financial_graph_reconciliation,
            "reconciliation_artifact_candidate_ids_for_operand",
            side_effect=AssertionError("per-operand owner must stay lazy"),
        ), patch.object(
            financial_graph_reconciliation,
            "reconciliation_artifact_candidate_ids",
            side_effect=AssertionError("general owner must stay lazy"),
        ), patch.object(
            agent,
            "_expand_structured_candidate_ids",
            return_value=[],
        ), patch.object(
            financial_graph_reconciliation,
            "repair_note_operand_units_from_same_block",
            return_value=[],
        ):
            self.assertEqual(
                agent._extract_structured_operands_from_reconciliation(structured_state),
                [],
            )

        with patch.object(
            financial_graph_reconciliation,
            "active_subtask_with_sibling_lookup_surfaces",
            return_value=active_subtask,
        ), patch.object(
            agent,
            "_complete_required_operand_from_ontology",
            side_effect=lambda operand: operand,
        ), patch.object(
            financial_graph_reconciliation,
            "_query_years_from_state",
            return_value=[],
        ), patch.object(
            agent,
            "_build_reconciliation_candidates",
            return_value=[],
        ), patch.object(
            agent,
            "_extract_structured_period_pair_rows",
            return_value=([], set()),
        ), patch.object(
            financial_graph_reconciliation,
            "reconciliation_artifact_candidate_ids_for_operand",
            side_effect=RuntimeError("per-operand failed"),
        ), patch.object(
            financial_graph_reconciliation,
            "reconciliation_artifact_candidate_ids",
            side_effect=AssertionError("general owner must stop"),
        ), patch.object(
            agent,
            "_expand_structured_candidate_ids",
            side_effect=AssertionError("expansion must stop"),
        ), patch.object(
            financial_graph_reconciliation,
            "repair_note_operand_units_from_same_block",
            side_effect=AssertionError("repair must stop"),
        ):
            with self.assertRaisesRegex(RuntimeError, "per-operand failed"):
                agent._extract_structured_operands_from_reconciliation(structured_state)
        self.assertEqual(structured_state, structured_before)

        with patch.object(
            financial_graph_reconciliation,
            "active_subtask_with_sibling_lookup_surfaces",
            return_value=active_subtask,
        ), patch.object(
            agent,
            "_complete_required_operand_from_ontology",
            side_effect=lambda operand: operand,
        ), patch.object(
            financial_graph_reconciliation,
            "_query_years_from_state",
            return_value=[],
        ), patch.object(
            agent,
            "_build_reconciliation_candidates",
            return_value=[],
        ), patch.object(
            agent,
            "_extract_structured_period_pair_rows",
            return_value=([], set()),
        ), patch.object(
            financial_graph_reconciliation,
            "reconciliation_artifact_candidate_ids_for_operand",
            return_value=[],
        ), patch.object(
            financial_graph_reconciliation,
            "reconciliation_artifact_candidate_ids",
            side_effect=RuntimeError("general ids failed"),
        ), patch.object(
            agent,
            "_expand_structured_candidate_ids",
            side_effect=AssertionError("expansion must stop after general ids"),
        ), patch.object(
            financial_graph_reconciliation,
            "repair_note_operand_units_from_same_block",
            side_effect=AssertionError("repair must stop after general ids"),
        ):
            with self.assertRaisesRegex(RuntimeError, "general ids failed"):
                agent._extract_structured_operands_from_reconciliation(structured_state)
        self.assertEqual(structured_state, structured_before)

        dependency_state = {
            "all_resolved": True,
            "bindings": [{"preferred_task_id": "source"}],
        }
        dependency_result = {"status": "ready", "task_id": "task_ratio"}
        dependency_refs = ["dependency_ref"]
        dependency_ledger = {
            "tasks": [{"task_id": "task_ratio"}],
            "artifacts": [{"artifact_id": "reconciliation:task_ratio"}],
        }
        reconciliation_state = {
            "active_subtask": {"task_id": "task_ratio", "operation_family": "ratio"},
            "tasks": [{"task_id": "task_ratio"}],
            "artifacts": [],
            "reconciliation_retry_count": 0,
            "nested": {"keep": True},
        }
        reconciliation_before = deepcopy(reconciliation_state)
        dependency_events = []
        dependency_ledger_calls = []

        def dependency_active(subtask, received_state):
            dependency_events.append("active")
            self.assertIs(received_state, reconciliation_state)
            return reconciliation_state["active_subtask"]

        def dependency_resolution(received_state):
            dependency_events.append("dependency")
            self.assertIs(received_state, reconciliation_state)
            return dependency_state

        def dependency_preference(received_state):
            dependency_events.append("preference")
            self.assertIs(received_state, reconciliation_state)
            return True

        def dependency_result_owner(**kwargs):
            dependency_events.append("resolved")
            self.assertIs(kwargs["active_subtask"], reconciliation_state["active_subtask"])
            self.assertIs(kwargs["dependency_state"], dependency_state)
            return dependency_result

        def dependency_refs_owner(received_result):
            dependency_events.append("refs")
            self.assertIs(received_result, dependency_result)
            return dependency_refs

        def dependency_ledger_owner(**kwargs):
            dependency_events.append("ledger")
            dependency_ledger_calls.append(kwargs)
            return dependency_ledger

        with patch.object(
            financial_graph_reconciliation,
            "active_subtask_with_sibling_lookup_surfaces",
            side_effect=dependency_active,
        ), patch.object(
            agent,
            "_dependency_binding_resolution_state",
            side_effect=dependency_resolution,
        ), patch.object(
            financial_graph_reconciliation,
            "task_prefers_sibling_output_synthesis",
            side_effect=dependency_preference,
        ), patch.object(
            financial_graph_reconciliation,
            "dependency_resolved_reconciliation_result",
            side_effect=dependency_result_owner,
        ), patch.object(
            financial_graph_reconciliation,
            "reconciliation_evidence_refs",
            side_effect=dependency_refs_owner,
        ), patch.object(
            financial_graph_reconciliation,
            "_reconciliation_result_artifact_update",
            side_effect=dependency_ledger_owner,
        ):
            dependency_updates = agent._reconcile_retrieved_evidence(
                reconciliation_state
            )

        self.assertEqual(
            dependency_events,
            ["active", "dependency", "preference", "resolved", "refs", "ledger"],
        )
        self.assertIs(dependency_updates["reconciliation_result"], dependency_result)
        self.assertIs(
            dependency_ledger_calls[0]["reconciliation_result"], dependency_result
        )
        self.assertIs(dependency_ledger_calls[0]["evidence_refs"], dependency_refs)
        self.assertEqual(reconciliation_state, reconciliation_before)

        with patch.object(
            financial_graph_reconciliation,
            "active_subtask_with_sibling_lookup_surfaces",
            return_value=reconciliation_state["active_subtask"],
        ), patch.object(
            agent,
            "_dependency_binding_resolution_state",
            return_value=dependency_state,
        ), patch.object(
            financial_graph_reconciliation,
            "task_prefers_sibling_output_synthesis",
            return_value=True,
        ), patch.object(
            financial_graph_reconciliation,
            "dependency_resolved_reconciliation_result",
            return_value=dependency_result,
        ), patch.object(
            financial_graph_reconciliation,
            "reconciliation_evidence_refs",
            side_effect=RuntimeError("dependency refs failed"),
        ), patch.object(
            financial_graph_reconciliation,
            "_reconciliation_result_artifact_update",
            side_effect=AssertionError("dependency ledger must stop"),
        ):
            with self.assertRaisesRegex(RuntimeError, "dependency refs failed"):
                agent._reconcile_retrieved_evidence(reconciliation_state)
        self.assertEqual(reconciliation_state, reconciliation_before)

        normal_state = {
            "active_subtask": {"task_id": "task_normal", "operation_family": "lookup"},
            "tasks": [{"task_id": "task_normal"}],
            "artifacts": [],
            "report_scope": {},
            "reconciliation_retry_count": 0,
            "nested": {"keep": True},
        }
        normal_before = deepcopy(normal_state)
        unresolved_dependency = {"all_resolved": False}
        candidates = [{"candidate_id": "candidate"}]
        deterministic_result = {"status": "ready", "task_id": "task_normal"}
        reranked_result = {"status": "ready", "task_id": "task_normal", "reranked": True}
        normal_refs = ["normal_ref"]
        normal_ledger = {
            "tasks": [{"task_id": "task_normal"}],
            "artifacts": [{"artifact_id": "reconciliation:task_normal"}],
        }
        normal_events = []
        normal_ledger_calls = []

        def normal_active(subtask, received_state):
            normal_events.append("active")
            self.assertIs(received_state, normal_state)
            return normal_state["active_subtask"]

        def normal_dependency(received_state):
            normal_events.append("dependency")
            self.assertIs(received_state, normal_state)
            return unresolved_dependency

        def normal_years(received_state):
            normal_events.append("years")
            self.assertIs(received_state, normal_state)
            return [2024]

        def normal_candidates(received_state):
            normal_events.append("candidates")
            self.assertIs(received_state, normal_state)
            return candidates

        def deterministic_owner(**kwargs):
            normal_events.append("deterministic")
            self.assertIs(kwargs["active_subtask"], normal_state["active_subtask"])
            self.assertIs(kwargs["candidates"], candidates)
            self.assertEqual(kwargs["years"], [2024])
            return deterministic_result

        def rerank_owner(received_state, result, received_candidates, years):
            normal_events.append("rerank")
            self.assertIs(received_state, normal_state)
            self.assertIs(result, deterministic_result)
            self.assertIs(received_candidates, candidates)
            self.assertEqual(years, [2024])
            return reranked_result

        def retry_owner(received_state, result):
            normal_events.append("retry")
            self.assertIs(received_state, normal_state)
            self.assertIs(result, reranked_result)
            return ""

        def normal_refs_owner(result):
            normal_events.append("refs")
            self.assertIs(result, reranked_result)
            return normal_refs

        def normal_ledger_owner(**kwargs):
            normal_events.append("ledger")
            normal_ledger_calls.append(kwargs)
            return normal_ledger

        with patch.object(
            financial_graph_reconciliation,
            "active_subtask_with_sibling_lookup_surfaces",
            side_effect=normal_active,
        ), patch.object(
            agent,
            "_dependency_binding_resolution_state",
            side_effect=normal_dependency,
        ), patch.object(
            financial_graph_reconciliation,
            "task_prefers_sibling_output_synthesis",
            side_effect=AssertionError("preference must stay lazy"),
        ), patch.object(
            financial_graph_reconciliation,
            "_query_years_from_state",
            side_effect=normal_years,
        ), patch.object(
            agent,
            "_build_reconciliation_candidates",
            side_effect=normal_candidates,
        ), patch.object(
            financial_graph_reconciliation,
            "_deterministic_reconcile_task",
            side_effect=deterministic_owner,
        ), patch.object(
            agent,
            "_rerank_reconciliation_matches_with_llm",
            side_effect=rerank_owner,
        ), patch.object(
            agent,
            "_select_retry_strategy_for_reconciliation",
            side_effect=retry_owner,
        ), patch.object(
            financial_graph_reconciliation,
            "reconciliation_evidence_refs",
            side_effect=normal_refs_owner,
        ), patch.object(
            financial_graph_reconciliation,
            "_reconciliation_result_artifact_update",
            side_effect=normal_ledger_owner,
        ):
            normal_updates = agent._reconcile_retrieved_evidence(normal_state)

        self.assertEqual(
            normal_events,
            [
                "active",
                "dependency",
                "years",
                "candidates",
                "deterministic",
                "rerank",
                "retry",
                "refs",
                "ledger",
            ],
        )
        self.assertIs(normal_updates["reconciliation_result"], reranked_result)
        self.assertIs(
            normal_ledger_calls[0]["reconciliation_result"], reranked_result
        )
        self.assertIs(normal_ledger_calls[0]["evidence_refs"], normal_refs)
        self.assertEqual(normal_state, normal_before)

        with patch.object(
            financial_graph_reconciliation,
            "active_subtask_with_sibling_lookup_surfaces",
            return_value=normal_state["active_subtask"],
        ), patch.object(
            agent,
            "_dependency_binding_resolution_state",
            return_value=unresolved_dependency,
        ), patch.object(
            financial_graph_reconciliation,
            "_query_years_from_state",
            return_value=[2024],
        ), patch.object(
            agent,
            "_build_reconciliation_candidates",
            return_value=candidates,
        ), patch.object(
            financial_graph_reconciliation,
            "_deterministic_reconcile_task",
            return_value=deterministic_result,
        ), patch.object(
            agent,
            "_rerank_reconciliation_matches_with_llm",
            return_value=reranked_result,
        ), patch.object(
            agent,
            "_select_retry_strategy_for_reconciliation",
            return_value="",
        ), patch.object(
            financial_graph_reconciliation,
            "reconciliation_evidence_refs",
            side_effect=RuntimeError("normal refs failed"),
        ), patch.object(
            financial_graph_reconciliation,
            "_reconciliation_result_artifact_update",
            side_effect=AssertionError("normal ledger must stop"),
        ):
            with self.assertRaisesRegex(RuntimeError, "normal refs failed"):
                agent._reconcile_retrieved_evidence(normal_state)
        self.assertEqual(normal_state, normal_before)

    def test_current_source_runtime_evidence_merge_pins_identity_order_and_exceptions(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        nested = {"keep": True}
        existing = {"evidence_id": " e1 ", "nested": nested}
        existing_marker = "existing-nondict"
        duplicate = {"evidence_id": "e1", "nested": {"duplicate": True}}
        fresh = {"evidence_id": " e2 ", "nested": nested}
        blank_first = {"evidence_id": "", "claim": "blank-first", "nested": nested}
        blank_second = {"claim": "blank-second", "nested": nested}
        duplicate_fresh = {"evidence_id": "e2", "claim": "duplicate-fresh"}
        evidence_items = [existing, existing_marker]
        state = {
            "runtime_evidence": [
                "skip-runtime-nondict",
                duplicate,
                fresh,
                blank_first,
                blank_second,
                duplicate_fresh,
            ],
            "nested": nested,
        }
        evidence_before = deepcopy(evidence_items)
        state_before = deepcopy(state)

        combined = financial_task_artifacts.evidence_items_with_runtime(evidence_items, state)

        self.assertEqual(
            [
                item if not isinstance(item, dict) else item.get("claim") or str(item.get("evidence_id") or "").strip()
                for item in combined
            ],
            ["e1", existing_marker, "e2", "blank-first", "blank-second"],
        )
        self.assertIsNot(combined, evidence_items)
        self.assertIs(combined[0], existing)
        self.assertIs(combined[1], existing_marker)
        self.assertIsNot(combined[2], fresh)
        self.assertIsNot(combined[3], blank_first)
        self.assertIsNot(combined[4], blank_second)
        self.assertIs(combined[2]["nested"], nested)
        self.assertIs(combined[3]["nested"], nested)
        self.assertIs(combined[4]["nested"], nested)
        self.assertEqual(evidence_items, evidence_before)
        self.assertEqual(state, state_before)
        self.assertIs(evidence_items[0]["nested"], nested)
        self.assertIs(state["nested"], nested)

        class StateAccessBomb(dict):
            def get(self, _key, _default=None):
                raise AssertionError("state must remain lazy")

        class EvidenceIterationBomb:
            def __iter__(self):
                raise RuntimeError("input evidence iterated")

        with self.assertRaisesRegex(RuntimeError, "input evidence iterated"):
            financial_task_artifacts.evidence_items_with_runtime(EvidenceIterationBomb(), StateAccessBomb())

        class StringBomb:
            def __str__(self):
                raise RuntimeError("evidence id string failed")

        with self.assertRaisesRegex(RuntimeError, "evidence id string failed"):
            financial_task_artifacts.evidence_items_with_runtime(
                [{"evidence_id": StringBomb()}],
                StateAccessBomb(),
            )

        class RuntimeIterationBomb:
            def __iter__(self):
                raise RuntimeError("runtime evidence iterated")

        with self.assertRaisesRegex(RuntimeError, "runtime evidence iterated"):
            financial_task_artifacts.evidence_items_with_runtime([], {"runtime_evidence": RuntimeIterationBomb()})

        class RuntimeStateGetBomb(dict):
            def get(self, _key, _default=None):
                raise RuntimeError("runtime evidence state access failed")

        with self.assertRaisesRegex(RuntimeError, "runtime evidence state access failed"):
            financial_task_artifacts.evidence_items_with_runtime([], RuntimeStateGetBomb())

        later = {"evidence_id": "later"}
        with self.assertRaisesRegex(RuntimeError, "evidence id string failed"):
            financial_task_artifacts.evidence_items_with_runtime(
                [],
                {"runtime_evidence": [{"evidence_id": StringBomb()}, later]},
            )

    def test_current_source_ratio_artifact_rows_pin_gates_fallbacks_and_copy_contract(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)

        class StateAccessBomb(dict):
            def get(self, _key, _default=None):
                raise AssertionError("artifacts must remain lazy")

        self.assertEqual(
            financial_task_artifacts.ratio_result_rows_from_task_artifacts(
                StateAccessBomb(),
                {"task_id": "   "},
            ),
            [],
        )

        nested = {"keep": True}
        operand_rows = [{"label": "Numerator", "nested": nested}]
        row_ids = ["row-1"]
        evidence_ids = ["evidence-1"]
        fallback_refs = ["fallback-ref"]
        primary_result = {
            "formatted_result": " 10.00% ",
            "rendered_value": "ignored-rendered",
            "status": "complete",
            "source_row_ids": row_ids,
            "source_evidence_ids": evidence_ids,
            "nested": nested,
        }
        rendered_result = {
            "formatted_result": "",
            "rendered_value": " 20.00% ",
            "nested": nested,
        }
        summary_result = {
            "formatted_result": "",
            "rendered_value": "",
            "nested": nested,
        }

        class PayloadAccessBomb:
            def __bool__(self):
                raise AssertionError("payload truthiness must stay lazy")

        artifacts = [
            {
                "task_id": "other-task",
                "kind": "calculation_result",
                "payload": PayloadAccessBomb(),
            },
            {
                "task_id": "ratio-task",
                "kind": "other-kind",
                "payload": PayloadAccessBomb(),
            },
            {
                "task_id": "ratio-task",
                "kind": "calculation_result",
                "payload": {"calculation_result": {}},
            },
            {
                "task_id": "ratio-task",
                "kind": "calculation_result",
                "status": "artifact-status",
                "evidence_refs": fallback_refs,
                "payload": {
                    "calculation_result": primary_result,
                    "calculation_operands": operand_rows,
                },
                "nested": nested,
            },
            {
                "task_id": "ratio-task",
                "kind": "calculation_result",
                "status": "artifact-rendered-status",
                "evidence_refs": fallback_refs,
                "payload": {"calculation_result": rendered_result},
                "nested": nested,
            },
            {
                "task_id": "ratio-task",
                "kind": "calculation_result",
                "summary": " summary fallback ",
                "evidence_refs": fallback_refs,
                "payload": {"calculation_result": summary_result},
                "nested": nested,
            },
        ]
        task = {
            "task_id": " ratio-task ",
            "metric_family": "explicit-ratio",
            "metric_label": "Explicit label",
            "target_metric": "Fallback label",
            "nested": nested,
        }
        state = {"artifacts": artifacts, "nested": nested}
        valid_artifacts_before = deepcopy(artifacts[2:])
        task_before = deepcopy(task)

        rows = financial_task_artifacts.ratio_result_rows_from_task_artifacts(state, task)

        self.assertEqual(len(rows), 3)
        self.assertEqual(
            [row["answer"] for row in rows],
            ["10.00%", "20.00%", "summary fallback"],
        )
        self.assertEqual(
            [row["status"] for row in rows],
            ["complete", "artifact-rendered-status", ""],
        )
        self.assertTrue(all(row["task_id"] == "ratio-task" for row in rows))
        self.assertTrue(all(row["metric_family"] == "explicit-ratio" for row in rows))
        self.assertTrue(all(row["metric_label"] == "Explicit label" for row in rows))
        self.assertTrue(all(row["operation_family"] == "ratio" for row in rows))
        self.assertTrue(all(row["artifact_backed_complete_result"] for row in rows))
        self.assertIs(rows[0]["calculation_operands"], operand_rows)
        self.assertIs(rows[0]["source_row_ids"], row_ids)
        self.assertIs(rows[0]["source_evidence_ids"], evidence_ids)
        self.assertIs(rows[1]["source_row_ids"], fallback_refs)
        self.assertIs(rows[1]["source_evidence_ids"], fallback_refs)
        self.assertIsNot(rows[0]["calculation_result"], primary_result)
        self.assertIs(rows[0]["calculation_result"]["nested"], nested)
        self.assertIs(state["artifacts"], artifacts)
        self.assertEqual(state["artifacts"][2:], valid_artifacts_before)
        self.assertEqual(task, task_before)
        self.assertIs(state["nested"], nested)
        self.assertIs(task["nested"], nested)

        fallback_task = {"task_id": "ratio-task", "target_metric": "Target only"}
        fallback_rows = financial_task_artifacts.ratio_result_rows_from_task_artifacts(
            {"artifacts": [artifacts[3]]},
            fallback_task,
        )
        self.assertEqual(fallback_rows[0]["metric_family"], "concept_ratio")
        self.assertEqual(fallback_rows[0]["metric_label"], "Target only")

        class ArtifactIterationBomb:
            def __iter__(self):
                raise RuntimeError("artifacts iterated")

        with self.assertRaisesRegex(RuntimeError, "artifacts iterated"):
            financial_task_artifacts.ratio_result_rows_from_task_artifacts(
                {"artifacts": ArtifactIterationBomb()},
                {"task_id": "ratio-task"},
            )

        class CopyBomb(Mapping):
            def __len__(self):
                return 1

            def __iter__(self):
                raise RuntimeError("artifact copy failed")

            def __getitem__(self, _key):
                raise AssertionError("artifact item must not be read")

        with self.assertRaisesRegex(RuntimeError, "artifact copy failed"):
            financial_task_artifacts.ratio_result_rows_from_task_artifacts(
                {"artifacts": [CopyBomb()]},
                {"task_id": "ratio-task"},
            )

        class PayloadCopyBomb(Mapping):
            def __len__(self):
                return 1

            def __iter__(self):
                raise RuntimeError("payload copy failed")

            def __getitem__(self, _key):
                raise AssertionError("payload item must not be read")

        with self.assertRaisesRegex(RuntimeError, "payload copy failed"):
            financial_task_artifacts.ratio_result_rows_from_task_artifacts(
                {
                    "artifacts": [
                        {
                            "task_id": "ratio-task",
                            "kind": "calculation_result",
                            "payload": PayloadCopyBomb(),
                        }
                    ]
                },
                {"task_id": "ratio-task"},
            )

        class ResultCopyBomb(Mapping):
            def __len__(self):
                return 1

            def __iter__(self):
                raise RuntimeError("calculation result copy failed")

            def __getitem__(self, _key):
                raise AssertionError("calculation result item must not be read")

        with self.assertRaisesRegex(RuntimeError, "calculation result copy failed"):
            financial_task_artifacts.ratio_result_rows_from_task_artifacts(
                {
                    "artifacts": [
                        {
                            "task_id": "ratio-task",
                            "kind": "calculation_result",
                            "payload": {"calculation_result": ResultCopyBomb()},
                        }
                    ]
                },
                {"task_id": "ratio-task"},
            )

        original_normalise = financial_task_artifacts._normalise_spaces
        normalise_events = []

        def tracked_normalise(value):
            normalise_events.append(value)
            if value == "bad-answer":
                raise RuntimeError("answer normalization failed")
            return original_normalise(value)

        bad_answer_artifact = {
            "task_id": "ratio-task",
            "kind": "calculation_result",
            "payload": {"calculation_result": {"formatted_result": "bad-answer"}},
        }
        with patch.object(
            financial_task_artifacts,
            "_normalise_spaces",
            side_effect=tracked_normalise,
        ), self.assertRaisesRegex(RuntimeError, "answer normalization failed"):
            financial_task_artifacts.ratio_result_rows_from_task_artifacts(
                {"artifacts": [bad_answer_artifact]},
                {"task_id": "ratio-task"},
            )
        self.assertEqual(
            normalise_events,
            ["ratio-task", "ratio-task", "calculation_result", "bad-answer"],
        )

    def test_current_source_task_artifact_read_bindings_pin_exact_move_boundary(self) -> None:
        graph_path = Path("src/agent/financial_graph_calculation.py")
        owner_path = Path("src/agent/financial_task_artifacts.py")
        graph_tree = ast.parse(graph_path.read_text(encoding="utf-8-sig"))
        owner_tree = ast.parse(owner_path.read_text(encoding="utf-8-sig"))
        public_targets = {
            "evidence_items_with_runtime",
            "ratio_result_rows_from_task_artifacts",
        }
        private_targets = {f"_{name}": name for name in public_targets}
        graph_class = next(
            node
            for node in graph_tree.body
            if isinstance(node, ast.ClassDef) and node.name == "FinancialAgentCalculationMixin"
        )
        graph_defs = {
            node.name: node
            for node in graph_class.body
            if isinstance(node, ast.FunctionDef) and node.name in private_targets
        }
        self.assertEqual(graph_defs, {})
        owner_public_defs = {
            node.name: node
            for node in owner_tree.body
            if isinstance(node, ast.FunctionDef) and node.name in private_targets.values()
        }
        self.assertEqual(
            {
                name: (node.lineno, node.end_lineno, node.end_lineno - node.lineno + 1)
                for name, node in owner_public_defs.items()
            },
            {
                "evidence_items_with_runtime": (66, 85, 20),
                "ratio_result_rows_from_task_artifacts": (88, 129, 42),
            },
        )
        self.assertIn("evidence_items_with_runtime", financial_task_artifacts.__all__)
        self.assertIn("ratio_result_rows_from_task_artifacts", financial_task_artifacts.__all__)

        calls = []

        class BindingVisitor(ast.NodeVisitor):
            def __init__(self):
                self.function_stack = []
                self.try_depth = 0

            def visit_FunctionDef(self, node):
                self.function_stack.append(node.name)
                self.generic_visit(node)
                self.function_stack.pop()

            def visit_Try(self, node):
                self.try_depth += 1
                self.generic_visit(node)
                self.try_depth -= 1

            def visit_Call(self, node):
                target_name = None
                receiver = None
                if isinstance(node.func, ast.Attribute):
                    target_name = node.func.attr
                    receiver = ast.unparse(node.func.value)
                elif isinstance(node.func, ast.Name):
                    target_name = node.func.id
                    receiver = "Name"
                if target_name in private_targets or target_name in private_targets.values():
                    calls.append(
                        (
                            target_name,
                            self.function_stack[-1] if self.function_stack else "",
                            receiver,
                            [ast.unparse(value) for value in node.args],
                            [(item.arg, ast.unparse(item.value)) for item in node.keywords],
                            self.try_depth,
                        )
                    )
                self.generic_visit(node)

        BindingVisitor().visit(graph_tree)
        self.assertEqual(
            calls,
            [
                (
                    "ratio_result_rows_from_task_artifacts",
                    "_preferred_ratio_artifact_row_for_conflicting_recalculation",
                    "Name",
                    ["state", "task"],
                    [],
                    0,
                ),
                (
                    "evidence_items_with_runtime",
                    "_extract_calculation_operands",
                    "Name",
                    ["evidence_items", "state"],
                    [],
                    0,
                ),
                (
                    "evidence_items_with_runtime",
                    "_extract_calculation_operands",
                    "Name",
                    ["evidence_items", "state"],
                    [],
                    0,
                ),
                (
                    "ratio_result_rows_from_task_artifacts",
                    "_append_ratio_result_from_retrieved_context",
                    "Name",
                    ["state", "task"],
                    [],
                    0,
                ),
            ],
        )
        self.assertEqual(sum(name == "evidence_items_with_runtime" for name, *_ in calls), 2)
        self.assertEqual(sum(name == "ratio_result_rows_from_task_artifacts" for name, *_ in calls), 2)
        self.assertEqual({item[-1] for item in calls}, {0})
        self.assertEqual({21 - 1, 43 - 1}, {20, 42})
        self.assertEqual((4, 0), (len(calls), 0))

        module_paths = list(Path("src/agent").glob("*.py"))
        modules = {f"src.agent.{path.stem}": path for path in module_paths}
        imports = {module: set() for module in modules}
        for module, path in modules.items():
            tree = ast.parse(path.read_text(encoding="utf-8-sig"))
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module in modules:
                    imports[module].add(node.module)
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name in modules:
                            imports[module].add(alias.name)

        def reaches(start, target):
            pending = [start]
            visited = set()
            while pending:
                current = pending.pop()
                if current == target:
                    return True
                if current in visited:
                    continue
                visited.add(current)
                pending.extend(imports.get(current, set()))
            return False

        graph_module = "src.agent.financial_graph_calculation"
        owner_module = "src.agent.financial_task_artifacts"
        aggregate_module = "src.agent.financial_aggregate_projection"
        self.assertTrue(reaches(graph_module, owner_module))
        self.assertFalse(reaches(owner_module, graph_module))
        self.assertTrue(reaches(aggregate_module, owner_module))
        self.assertFalse(reaches(owner_module, aggregate_module))

        baseline = json.loads(
            (Path("tests") / "fixtures" / "runtime_domain_terms_baseline.json").read_text(encoding="utf-8")
        )
        self.assertEqual(len(baseline["records"]), 217)
        selected_hits = [
            record
            for record in baseline["records"]
            if (
                str(record.get("path") or "").replace("\\", "/").endswith(
                    "src/agent/financial_graph_calculation.py"
                )
                and any(
                    524 <= line <= 544 or 10517 <= line <= 10559
                    for line in (record.get("first_lines") or [])
                )
            )
            or (
                str(record.get("path") or "").replace("\\", "/").endswith(
                    "src/agent/financial_task_artifacts.py"
                )
                and any(66 <= line <= 129 for line in (record.get("first_lines") or []))
            )
        ]
        self.assertEqual(selected_hits, [])

        rank_text = Path("tests/test_financial_aggregate_rank_dedupe.py").read_text(encoding="utf-8-sig")
        subtask_text = Path("tests/test_subtask_loop.py").read_text(encoding="utf-8-sig")
        self.assertTrue(all(private_name not in rank_text + subtask_text for private_name in private_targets))

    def test_current_source_operand_extraction_runtime_evidence_calls_pin_args_adoption_and_stop(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        nested = {"keep": True}
        evidence_item = {"evidence_id": "base", "nested": nested}
        runtime_item = {"evidence_id": "runtime", "nested": nested}
        required_operand = {"label": "Metric", "required": True, "nested": nested}
        direct_row = {"operand_id": "op_001", "nested": nested}

        def execute(operation_family, *, owner_exception=False):
            state = {
                "query": "query",
                "topic": "topic",
                "intent": "numeric_fact",
                "query_type": "numeric_fact",
                "evidence_items": [evidence_item],
                "evidence_bullets": [],
                "runtime_evidence": [runtime_item],
                "retrieved_docs": [],
                "seed_retrieved_docs": [],
                "report_scope": {},
                "active_subtask": {
                    "task_id": "task",
                    "operation_family": operation_family,
                    "metric_family": "concept_ratio",
                    "required_operands": [required_operand],
                },
                "nested": nested,
            }
            before = deepcopy(state)
            events = []
            combined = [evidence_item, runtime_item]

            def acceptance_owner(value):
                events.append("acceptance")
                self.assertIs(value.direct_operand_rows[0], direct_row)
                return Mock(accepted_operand_rows=[direct_row])

            def runtime_owner(items, received_state):
                events.append("runtime")
                self.assertIs(received_state, state)
                self.assertIsNot(items, state["evidence_items"])
                self.assertIs(items[0], evidence_item)
                if owner_exception:
                    raise RuntimeError("runtime owner failed")
                return combined

            def preferred_owner(rows, *, evidence_items, required_operands, operation_family, state):
                events.append("preferred")
                self.assertIs(rows[0], direct_row)
                self.assertIs(evidence_items, combined)
                self.assertIsNot(required_operands[0], required_operand)
                self.assertEqual(required_operands[0], required_operand)
                self.assertIs(required_operands[0]["nested"], nested)
                self.assertEqual(operation_family, operation_family_value)
                self.assertIs(state, state_value)
                raise RuntimeError("preferred stop")

            operation_family_value = operation_family
            state_value = state
            preferred_name = (
                "_prefer_direct_structured_lookup_evidence_rows"
                if operation_family in {"lookup", "single_value"}
                else "_prefer_direct_structured_evidence_rows"
            )
            other_name = (
                "_prefer_direct_structured_evidence_rows"
                if preferred_name == "_prefer_direct_structured_lookup_evidence_rows"
                else "_prefer_direct_structured_lookup_evidence_rows"
            )
            with ExitStack() as stack:
                stack.enter_context(patch.object(agent, "_calc_query", return_value="query"))
                stack.enter_context(patch.object(agent, "_calc_topic", return_value="topic"))
                stack.enter_context(
                    patch.object(agent, "_extract_structured_operands_from_reconciliation", return_value=[direct_row])
                )
                stack.enter_context(
                    patch.object(agent, "_evidence_items_from_reconciliation_matches", return_value=[])
                )
                stack.enter_context(patch.object(agent, "_coerce_operand_row_from_evidence", side_effect=lambda row, _item: row))
                stack.enter_context(patch.object(agent, "_direct_target_metric_operand_from_evidence", return_value=({}, {})))
                stack.enter_context(
                    patch.object(financial_graph_calculation, "evidence_items_with_runtime", side_effect=runtime_owner)
                )
                preferred_mock = stack.enter_context(patch.object(agent, preferred_name, side_effect=preferred_owner))
                other_mock = stack.enter_context(
                    patch.object(agent, other_name, side_effect=AssertionError("other preference must stay lazy"))
                )
                dependency_mock = stack.enter_context(
                    patch.object(agent, "_dependency_binding_resolution_state", side_effect=AssertionError("dependency must stop"))
                )
                stack.enter_context(patch.object(financial_graph_calculation, "_desired_consolidation_scope", return_value=""))
                stack.enter_context(patch.object(financial_graph_calculation, "_calculation_debug_state_update", return_value={}))
                stack.enter_context(patch.object(financial_graph_calculation, "_runtime_trace_state_update", return_value={}))
                stack.enter_context(patch.object(financial_graph_calculation, "_requires_direct_numeric_grounding", return_value=False))
                stack.enter_context(
                    patch.object(financial_graph_calculation, "surface_contract_numeric_evidence_items", return_value=[])
                )
                stack.enter_context(patch.object(financial_graph_calculation, "_evidence_items_by_id", return_value={}))
                stack.enter_context(patch.object(financial_graph_calculation, "_evidence_item_for_operand_row", return_value={}))
                stack.enter_context(
                    patch.object(financial_graph_calculation, "operand_row_conflicts_requested_scope", return_value=False)
                )
                stack.enter_context(
                    patch.object(financial_graph_calculation, "evidence_item_conflicts_requested_scope", return_value=False)
                )
                stack.enter_context(
                    patch.object(financial_graph_calculation, "resolve_direct_structured_operand_acceptance", side_effect=acceptance_owner)
                )
                expected_message = "runtime owner failed" if owner_exception else "preferred stop"
                with self.assertRaisesRegex(RuntimeError, expected_message):
                    agent._extract_calculation_operands(state)
            self.assertEqual(events, ["acceptance", "runtime"] if owner_exception else ["acceptance", "runtime", "preferred"])
            if owner_exception:
                preferred_mock.assert_not_called()
            else:
                preferred_mock.assert_called_once()
            other_mock.assert_not_called()
            dependency_mock.assert_not_called()
            self.assertEqual(state, before)
            self.assertIs(state["nested"], nested)
            self.assertIs(state["evidence_items"][0], evidence_item)
            self.assertIs(state["runtime_evidence"][0], runtime_item)

        execute("lookup")
        execute("ratio")
        execute("lookup", owner_exception=True)

    def test_current_source_preferred_ratio_artifact_caller_pins_args_adoption_and_stop(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        nested = {"keep": True}
        state = {"artifacts": [{"artifact_id": "a", "nested": nested}], "nested": nested}
        task = {"task_id": "ratio-task", "nested": nested}
        recalculated_result = {"result_value": "10", "nested": nested}
        artifact_rows = [{"task_id": "ratio-task", "answer": "9%", "nested": nested}]
        selected = {"task_id": "ratio-task", "answer": "9%", "nested": nested}
        state_before = deepcopy(state)
        task_before = deepcopy(task)
        result_before = deepcopy(recalculated_result)
        events = []

        def row_owner(received_state, received_task):
            events.append("rows")
            self.assertIs(received_state, state)
            self.assertIs(received_task, task)
            return artifact_rows

        def selection_owner(selection_input):
            events.append("selection")
            self.assertIs(selection_input.artifact_rows, artifact_rows)
            self.assertEqual(selection_input.recalculated_value, 10.0)
            return Mock(selected_artifact_row=selected)

        with patch.object(
            financial_graph_calculation.financial_answer_slots,
            "coerce_slot_numeric",
            return_value=10.0,
        ), patch.object(
            financial_graph_calculation,
            "ratio_result_rows_from_task_artifacts",
            side_effect=row_owner,
        ), patch.object(
            financial_graph_calculation,
            "resolve_ratio_artifact_conflict_selection",
            side_effect=selection_owner,
        ):
            resolved = agent._preferred_ratio_artifact_row_for_conflicting_recalculation(
                state,
                task,
                recalculated_result,
            )
        self.assertIs(resolved, selected)
        self.assertEqual(events, ["rows", "selection"])

        row_mock = Mock(side_effect=AssertionError("rows must stay lazy"))
        with patch.object(
            financial_graph_calculation.financial_answer_slots,
            "coerce_slot_numeric",
            return_value=None,
        ), patch.object(financial_graph_calculation, "ratio_result_rows_from_task_artifacts", row_mock), patch.object(
            financial_graph_calculation,
            "resolve_ratio_artifact_conflict_selection",
            side_effect=AssertionError("selection must stay lazy"),
        ):
            self.assertEqual(
                agent._preferred_ratio_artifact_row_for_conflicting_recalculation(
                    state,
                    task,
                    recalculated_result,
                ),
                {},
            )
        row_mock.assert_not_called()

        selection_mock = Mock(side_effect=AssertionError("selection must stop"))
        with patch.object(
            financial_graph_calculation.financial_answer_slots,
            "coerce_slot_numeric",
            return_value=10.0,
        ), patch.object(
            financial_graph_calculation,
            "ratio_result_rows_from_task_artifacts",
            side_effect=RuntimeError("artifact rows failed"),
        ), patch.object(
            financial_graph_calculation,
            "resolve_ratio_artifact_conflict_selection",
            selection_mock,
        ), self.assertRaisesRegex(RuntimeError, "artifact rows failed"):
            agent._preferred_ratio_artifact_row_for_conflicting_recalculation(
                state,
                task,
                recalculated_result,
            )
        selection_mock.assert_not_called()
        self.assertEqual(state, state_before)
        self.assertEqual(task, task_before)
        self.assertEqual(recalculated_result, result_before)
        self.assertIs(state["nested"], nested)
        self.assertIs(task["nested"], nested)
        self.assertIs(recalculated_result["nested"], nested)

    def test_current_source_retrieved_ratio_caller_pins_artifact_rows_order_adoption_and_stop(self) -> None:
        nested = {"keep": True}
        ordered_results = [{"answer": "existing", "nested": nested}]
        context_rows = [
            {
                "matched_operand_role": "numerator_1",
                "label": "Numerator",
                "normalized_value": 100.0,
                "raw_value": "100",
                "raw_unit": "KRW",
                "evidence_id": "ev_num",
                "source_row_id": "ev_num",
                "nested": nested,
            },
            {
                "matched_operand_role": "denominator_1",
                "label": "Denominator",
                "normalized_value": 1000.0,
                "raw_value": "1000",
                "raw_unit": "KRW",
                "evidence_id": "ev_den",
                "source_row_id": "ev_den",
                "nested": nested,
            },
        ]
        context_evidence = [
            {"evidence_id": "ev_num", "claim": "Numerator 100", "nested": nested},
            {"evidence_id": "ev_den", "claim": "Denominator 1000", "nested": nested},
        ]
        task = {
            "task_id": "ratio-task",
            "metric_label": "Margin",
            "operation_family": "ratio",
            "required_operands": [
                {"role": "numerator_1", "label": "Numerator"},
                {"role": "denominator_1", "label": "Denominator"},
            ],
            "nested": nested,
        }
        state = {
            "query": "ratio",
            "topic": "Margin",
            "calc_subtasks": [task],
            "retrieved_docs": [],
            "seed_retrieved_docs": [],
            "nested": nested,
        }
        artifact_rows = [{"answer": "artifact", "nested": nested}]
        projection = {
            "result_value": 10.0,
            "result_unit": "%",
            "normalized_unit": "%",
            "rendered_value": "10.00%",
        }
        ordered_before = deepcopy(ordered_results)
        state_before = deepcopy(state)
        rows_before = deepcopy(context_rows)
        evidence_before = deepcopy(context_evidence)
        events = []

        class RatioAgent:
            pass

        ratio_agent = RatioAgent()
        ratio_agent._aggregate_result_operation_family = Mock(return_value="lookup")
        ratio_agent._ratio_operand_context_evidence_from_docs = Mock(return_value=context_evidence)
        ratio_agent._build_complete_ratio_operands_from_coherent_context = Mock(return_value=context_rows)

        def artifact_owner(received_state, received_task):
            events.append("artifact_rows")
            self.assertIs(received_state, state)
            self.assertIsNot(received_task, task)
            self.assertEqual(received_task, task)
            self.assertIs(received_task["nested"], nested)
            return artifact_rows

        def conflict_owner(existing_rows, received_task, *, result_value, context_evidence):
            events.append("conflict")
            self.assertEqual(existing_rows, [*ordered_results, *artifact_rows])
            self.assertIs(existing_rows[0], ordered_results[0])
            self.assertIs(existing_rows[1], artifact_rows[0])
            self.assertIsNot(received_task, task)
            self.assertEqual(received_task, task)
            self.assertEqual(result_value, 10.0)
            self.assertEqual(context_evidence, context_evidence_value)
            return False

        context_evidence_value = context_evidence
        ratio_agent._compact_ratio_answer = Mock(side_effect=lambda *_args, **_kwargs: events.append("compact") or "10.00%")

        with patch.object(
            financial_graph_calculation,
            "ratio_result_rows_from_task_artifacts",
            side_effect=artifact_owner,
        ), patch.object(
            financial_graph_calculation,
            "retrieved_ratio_projection_conflicts_with_existing_complete_result",
            side_effect=conflict_owner,
        ), patch.object(
            financial_graph_calculation,
            "collect_retrieval_context_docs",
            return_value=["doc"],
        ), patch.object(
            financial_graph_calculation,
            "_missing_required_operands",
            return_value=False,
        ), patch.object(
            financial_graph_calculation,
            "_ratio_operand_rows_collapse_to_same_slot",
            return_value=False,
        ), patch.object(
            financial_graph_calculation.calculation_rendering,
            "ratio_result_projection",
            return_value=projection,
        ):
            appended = financial_graph_calculation.FinancialAgentCalculationMixin._append_ratio_result_from_retrieved_context(
                ratio_agent,
                ordered_results,
                state,
            )
        self.assertEqual(events, ["artifact_rows", "conflict", "compact"])
        self.assertEqual(len(appended), 2)
        self.assertIs(appended[0], ordered_results[0])
        self.assertTrue(appended[1]["recovered_from_retrieved_ratio_context"])

        conflict_mock = Mock(side_effect=AssertionError("conflict must stop"))
        ratio_agent._compact_ratio_answer.reset_mock()
        with patch.object(
            financial_graph_calculation,
            "ratio_result_rows_from_task_artifacts",
            side_effect=RuntimeError("artifact owner failed"),
        ), patch.object(
            financial_graph_calculation,
            "retrieved_ratio_projection_conflicts_with_existing_complete_result",
            conflict_mock,
        ), patch.object(
            financial_graph_calculation,
            "collect_retrieval_context_docs",
            return_value=["doc"],
        ), patch.object(
            financial_graph_calculation,
            "_missing_required_operands",
            return_value=False,
        ), patch.object(
            financial_graph_calculation,
            "_ratio_operand_rows_collapse_to_same_slot",
            return_value=False,
        ), patch.object(
            financial_graph_calculation.calculation_rendering,
            "ratio_result_projection",
            return_value=projection,
        ), self.assertRaisesRegex(RuntimeError, "artifact owner failed"):
            financial_graph_calculation.FinancialAgentCalculationMixin._append_ratio_result_from_retrieved_context(
                ratio_agent,
                ordered_results,
                state,
            )
        conflict_mock.assert_not_called()
        ratio_agent._compact_ratio_answer.assert_not_called()
        self.assertEqual(ordered_results, ordered_before)
        self.assertEqual(state, state_before)
        self.assertEqual(context_rows, rows_before)
        self.assertEqual(context_evidence, evidence_before)
        self.assertIs(ordered_results[0]["nested"], nested)
        self.assertIs(state["nested"], nested)
        self.assertIs(context_rows[0]["nested"], nested)
        self.assertIs(context_evidence[0]["nested"], nested)


if __name__ == "__main__":
    unittest.main()
