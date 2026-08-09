from __future__ import annotations

import unittest
from collections.abc import Mapping
from copy import deepcopy
from typing import Any

from src.agent import financial_task_artifacts
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


if __name__ == "__main__":
    unittest.main()
