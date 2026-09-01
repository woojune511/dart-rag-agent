import unittest
from collections.abc import Mapping
from copy import deepcopy
from unittest.mock import Mock, patch

import src.agent.financial_numeric_surface as financial_numeric_surface
import src.agent.financial_graph_calculation as financial_graph_calculation
from src.agent.financial_graph import FinancialAgent
from src.agent.financial_graph_calculation import FinancialAgentCalculationMixin
from src.agent.financial_numeric_surface import (
    extract_numeric_surface_candidates,
    numeric_surface_candidates_equivalent,
)


class FinancialNumericProvenanceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.agent = FinancialAgent.__new__(FinancialAgent)

    def test_normalized_numeric_candidate_extractor_has_numeric_surface_owner(self) -> None:
        self.assertTrue(
            hasattr(financial_numeric_surface, "numeric_candidates_with_spans_from_surface")
        )
        self.assertNotIn(
            "_numeric_candidates_with_spans_from_surface",
            FinancialAgentCalculationMixin.__dict__,
        )

    def test_normalized_numeric_candidate_matrix_preserves_units_year_guard_and_spans(
        self,
    ) -> None:
        million_krw = "\ubc31\ub9cc\uc6d0"
        hundred_million_krw = "\uc5b5\uc6d0"
        cases = [
            (
                "explicit_units",
                f"2023 1,234{million_krw} 12.5% 42",
                {},
                [
                    ("currency", 1_234_000_000.0, "KRW", "1,234", million_krw, 1_000_000.0, (5, 10)),
                    ("percent", 12.5, "PERCENT", "12.5", "%", 1.0, (14, 18)),
                ],
            ),
            (
                "metadata_unit_hint",
                "2023 1,234 12",
                {"unit_hint": million_krw},
                [
                    ("currency", 1_234_000_000.0, "KRW", "1,234", million_krw, 1_000_000.0, (5, 10)),
                ],
            ),
            (
                "parenthetical_negative",
                f"metric (1,234){hundred_million_krw}",
                {},
                [
                    (
                        "currency",
                        -123_400_000_000.0,
                        "KRW",
                        "(1,234)",
                        hundred_million_krw,
                        100_000_000.0,
                        (7, 14),
                    ),
                ],
            ),
            (
                "invalid_metadata_unit_falls_back_to_text",
                f"1,234{hundred_million_krw}",
                {"unit_hint": "unknown"},
                [
                    (
                        "currency",
                        123_400_000_000.0,
                        "KRW",
                        "1,234",
                        hundred_million_krw,
                        100_000_000.0,
                        (0, 5),
                    ),
                ],
            ),
            (
                "short_generic",
                "42",
                {},
                [("generic", 42.0, "", "42", "", 1.0, (0, 2))],
            ),
        ]

        for name, surface, metadata, expected in cases:
            with self.subTest(name=name):
                original_metadata = deepcopy(metadata)
                candidates = financial_numeric_surface.numeric_candidates_with_spans_from_surface(
                    surface,
                    metadata,
                )
                signature = [
                    (
                        item["kind"],
                        item["normalized_value"],
                        item["normalized_unit"],
                        item["value_text"],
                        item["unit_text"],
                        item["display_step"],
                        tuple(item["span"]),
                    )
                    for item in candidates
                ]
                self.assertEqual(signature, expected)
                self.assertTrue(all(item["value"] == item["normalized_value"] for item in candidates))
                self.assertTrue(all(item["unit"] == item["unit_text"] for item in candidates))
                self.assertEqual(metadata, original_metadata)

    def test_currency_surface_equivalence_preserves_sign(self) -> None:
        positive = extract_numeric_surface_candidates("1,000백만원")[0]
        negative = extract_numeric_surface_candidates("(1,000)백만원")[0]

        self.assertFalse(numeric_surface_candidates_equivalent(positive, negative))
        self.assertTrue(numeric_surface_candidates_equivalent(negative, dict(negative)))

    def test_numeric_answer_coverage_and_outside_reference_preserve_behavior_contract(self) -> None:
        covers = financial_numeric_surface.answer_covers_numeric_answer
        outside = financial_numeric_surface.answer_has_numeric_material_outside_reference

        for name, answer, reference, expected in (
            ("empty reference", "target 10%", "no numeric material", True),
            ("empty answer", "no numeric material", "target 10%", False),
            ("answer extras allowed", "target 10% and peer 20%", "target 10%", True),
            ("missing reference item", "target 10%", "target 10% and peer 20%", False),
            ("rounded equivalent", "debt 25.4% and current 258.77%", "debt 25.36% and current 258.77%", True),
        ):
            with self.subTest(covers=name):
                self.assertEqual(covers(answer, reference), expected)

        for name, answer, reference, expected in (
            ("empty answer", "no numeric material", "target 10%", False),
            ("empty reference", "target 10%", "no numeric material", False),
            ("equivalent", "target 10%", "target 10%", False),
            ("answer extra", "target 10% and peer 20%", "target 10%", True),
            ("reference extra", "target 10%", "target 10% and peer 20%", False),
        ):
            with self.subTest(outside=name):
                self.assertEqual(outside(answer, reference), expected)

    def test_numeric_answer_coverage_and_outside_reference_preserve_access_contract(self) -> None:
        covers = financial_numeric_surface.answer_covers_numeric_answer
        outside = financial_numeric_surface.answer_has_numeric_material_outside_reference
        events = []

        class TrackedText:
            def __init__(self, name):
                self.name = name

            def __bool__(self):
                events.append(f"bool:{self.name}")
                return True

            def __str__(self):
                events.append(f"str:{self.name}")
                return self.name

        def normalize(value):
            events.append(f"normalize:{value}")
            return value

        input_events = [
            "bool:answer",
            "str:answer",
            "normalize:answer",
            "extract:answer",
            "bool:reference",
            "str:reference",
            "normalize:reference",
            "extract:reference",
        ]

        coverage_answer = [{"id": "a1"}, {"id": "a2"}, {"id": "a3"}]
        coverage_reference = [{"id": "n1"}, {"id": "n2"}, {"id": "n3"}]
        coverage_before = deepcopy((coverage_answer, coverage_reference))
        coverage_pairs = []

        def extract_coverage(value):
            events.append(f"extract:{value}")
            return coverage_answer if value == "answer" else coverage_reference

        def equivalent_coverage(answer_candidate, numeric_candidate):
            pair = (answer_candidate["id"], numeric_candidate["id"])
            coverage_pairs.append(pair)
            if pair == ("a3", "n1") or numeric_candidate["id"] == "n3":
                raise RuntimeError("coverage short circuit failed")
            return pair == ("a2", "n1")

        with (
            patch.object(financial_numeric_surface, "_normalise_spaces", side_effect=normalize),
            patch.object(
                financial_numeric_surface,
                "extract_numeric_surface_candidates",
                side_effect=extract_coverage,
            ),
            patch.object(
                financial_numeric_surface,
                "numeric_surface_candidates_equivalent",
                side_effect=equivalent_coverage,
            ),
        ):
            self.assertFalse(covers(TrackedText("answer"), TrackedText("reference")))
        self.assertEqual(events, input_events)
        self.assertEqual(
            coverage_pairs,
            [("a1", "n1"), ("a2", "n1"), ("a1", "n2"), ("a2", "n2"), ("a3", "n2")],
        )
        self.assertEqual((coverage_answer, coverage_reference), coverage_before)

        outside_answer = [{"id": "a1"}, {"id": "a2"}, {"id": "a3"}]
        outside_reference = [{"id": "r1"}, {"id": "r2"}, {"id": "r3"}]
        outside_before = deepcopy((outside_answer, outside_reference))
        outside_pairs = []

        def extract_outside(value):
            events.append(f"extract:{value}")
            return outside_answer if value == "answer" else outside_reference

        def equivalent_outside(answer_candidate, reference_candidate):
            pair = (answer_candidate["id"], reference_candidate["id"])
            outside_pairs.append(pair)
            if pair == ("a1", "r3") or answer_candidate["id"] == "a3":
                raise RuntimeError("outside short circuit failed")
            return pair == ("a1", "r2")

        events.clear()
        with (
            patch.object(financial_numeric_surface, "_normalise_spaces", side_effect=normalize),
            patch.object(
                financial_numeric_surface,
                "extract_numeric_surface_candidates",
                side_effect=extract_outside,
            ),
            patch.object(
                financial_numeric_surface,
                "numeric_surface_candidates_equivalent",
                side_effect=equivalent_outside,
            ),
        ):
            self.assertTrue(outside(TrackedText("answer"), TrackedText("reference")))
        self.assertEqual(events, input_events)
        self.assertEqual(
            outside_pairs,
            [("a1", "r1"), ("a1", "r2"), ("a2", "r1"), ("a2", "r2"), ("a2", "r3")],
        )
        self.assertEqual((outside_answer, outside_reference), outside_before)

        empty_extract = Mock(
            side_effect=([{"id": "answer"}], [], [], [{"id": "reference"}])
        )
        equivalence_poison = Mock(side_effect=RuntimeError("equivalence accessed"))
        with patch.multiple(
            financial_numeric_surface,
            extract_numeric_surface_candidates=empty_extract,
            numeric_surface_candidates_equivalent=equivalence_poison,
        ):
            self.assertTrue(covers("answer", "reference"))
            self.assertFalse(outside("answer", "reference"))
        self.assertEqual(
            [item.args for item in empty_extract.call_args_list],
            [("answer",), ("reference",), ("answer",), ("reference",)],
        )
        equivalence_poison.assert_not_called()

        gate_events = []

        class CandidateList:
            def __init__(self, name, values):
                self.name = name
                self.values = values

            def __bool__(self):
                gate_events.append(f"bool:{self.name}")
                return bool(self.values)

            def __iter__(self):
                raise RuntimeError(f"iterated:{self.name}")

        class PoisonCandidates:
            def __bool__(self):
                raise RuntimeError("later candidate list accessed")

        gate_extract = Mock(
            side_effect=(
                CandidateList("coverage-answer", []),
                CandidateList("coverage-reference", [{"id": "reference"}]),
                CandidateList("outside-answer", [{"id": "answer"}]),
                CandidateList("outside-reference", []),
                PoisonCandidates(),
                CandidateList("empty-coverage-reference", []),
                CandidateList("empty-outside-answer", []),
                PoisonCandidates(),
            )
        )
        with patch.object(
            financial_numeric_surface,
            "extract_numeric_surface_candidates",
            gate_extract,
        ):
            self.assertFalse(covers("answer", "reference"))
            self.assertFalse(outside("answer", "reference"))
            self.assertTrue(covers("answer", "reference"))
            self.assertFalse(outside("answer", "reference"))
        self.assertEqual(
            gate_events,
            [
                "bool:coverage-reference",
                "bool:coverage-answer",
                "bool:outside-answer",
                "bool:outside-reference",
                "bool:empty-coverage-reference",
                "bool:empty-outside-answer",
            ],
        )

        class StringBomb:
            def __bool__(self):
                return True

            def __str__(self):
                raise RuntimeError("string failed")

        with self.assertRaisesRegex(RuntimeError, "string failed"):
            covers(StringBomb(), "reference")
        for owner_name, patched_owner in (
            ("normalizer", "_normalise_spaces"),
            ("extractor", "extract_numeric_surface_candidates"),
        ):
            with self.subTest(propagates=owner_name), patch.object(
                financial_numeric_surface,
                patched_owner,
                side_effect=RuntimeError(f"{owner_name} failed"),
            ):
                with self.assertRaisesRegex(RuntimeError, f"{owner_name} failed"):
                    outside("answer", "reference")
        with (
            patch.object(
                financial_numeric_surface,
                "extract_numeric_surface_candidates",
                side_effect=([{"id": "answer"}], [{"id": "reference"}]),
            ),
            patch.object(
                financial_numeric_surface,
                "numeric_surface_candidates_equivalent",
                side_effect=RuntimeError("equivalence failed"),
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "equivalence failed"):
                covers("answer", "reference")

    def test_final_answer_numeric_support_and_conflict_predicates_preserve_behavior_contract(
        self,
    ) -> None:
        evidence_support = financial_numeric_surface.evidence_supports_numeric_candidates
        text_support = financial_numeric_surface.text_supports_numeric_candidates
        conflicts = financial_numeric_surface.numeric_surface_conflicts_with_reference

        answer_candidates = extract_numeric_surface_candidates("target 10% and peer 20%")
        evidence = {
            "claim": "target 10%",
            "metadata": {"nested": {"keep": True}},
        }
        evidence_before = deepcopy(evidence)
        self.assertTrue(evidence_support(evidence, answer_candidates))
        self.assertTrue(text_support("peer 20%", answer_candidates))
        self.assertFalse(text_support("unrelated 30%", answer_candidates))
        self.assertEqual(evidence, evidence_before)

        for name, answer, reference, expected in (
            ("empty answer", "no numeric material", "target 10%", False),
            ("empty reference", "target 10%", "no numeric material", False),
            ("equivalent", "target 10%", "target 10%", False),
            ("answer extra", "target 10% and peer 20%", "target 10%", True),
            ("reference extra", "target 10%", "target 10% and peer 20%", False),
        ):
            with self.subTest(conflict=name):
                self.assertEqual(conflicts(answer, reference), expected)

        events = []
        answer_1, answer_2 = object(), object()
        evidence_1, evidence_2 = object(), object()

        class TrackedAnswers:
            def __iter__(self):
                events.append("answers:iter")
                return iter((answer_1, answer_2))

        class TrackedEvidenceCandidates(list):
            def __iter__(self):
                events.append("evidence:iter")
                return super().__iter__()

        raw_evidence = {"claim": "raw"}
        evidence_candidates = TrackedEvidenceCandidates((evidence_1, evidence_2))

        def evidence_text(value):
            self.assertIs(value, raw_evidence)
            events.append("evidence:text")
            return "evidence surface"

        def extract(value):
            self.assertEqual(value, "evidence surface")
            events.append("evidence:extract")
            return evidence_candidates

        def equivalent(answer_candidate, evidence_candidate):
            events.append((answer_candidate, evidence_candidate))
            return answer_candidate is answer_2 and evidence_candidate is evidence_1

        with (
            patch.object(
                financial_numeric_surface,
                "evidence_text_for_numeric_support",
                side_effect=evidence_text,
            ),
            patch.object(
                financial_numeric_surface,
                "extract_numeric_surface_candidates",
                side_effect=extract,
            ),
            patch.object(
                financial_numeric_surface,
                "numeric_surface_candidates_equivalent",
                side_effect=equivalent,
            ),
        ):
            self.assertTrue(evidence_support(raw_evidence, TrackedAnswers()))

        self.assertEqual(
            events,
            [
                "evidence:text",
                "evidence:extract",
                "answers:iter",
                "evidence:iter",
                (answer_1, evidence_1),
                (answer_1, evidence_2),
                "evidence:iter",
                (answer_2, evidence_1),
            ],
        )

        class AnswerIterationBomb:
            def __iter__(self):
                raise AssertionError("empty support candidates must skip answer iteration")

        raw_text = object()
        with patch.object(
            financial_numeric_surface,
            "extract_numeric_surface_candidates",
            side_effect=lambda value: [] if value is raw_text else None,
        ) as extractor:
            self.assertFalse(text_support(raw_text, AnswerIterationBomb()))
        extractor.assert_called_once_with(raw_text)

    def test_final_answer_numeric_support_and_conflict_predicates_preserve_access_contract(
        self,
    ) -> None:
        evidence_support = financial_numeric_surface.evidence_supports_numeric_candidates
        text_support = financial_numeric_surface.text_supports_numeric_candidates
        conflicts = financial_numeric_surface.numeric_surface_conflicts_with_reference

        class IterationBomb:
            def __iter__(self):
                raise RuntimeError("answer iteration failed")

        with (
            patch.object(
                financial_numeric_surface,
                "evidence_text_for_numeric_support",
                return_value="evidence surface",
            ) as evidence_text,
            patch.object(
                financial_numeric_surface,
                "extract_numeric_surface_candidates",
                return_value=[{"id": "evidence"}],
            ) as extractor,
        ):
            with self.assertRaisesRegex(RuntimeError, "answer iteration failed"):
                evidence_support({"claim": "raw"}, IterationBomb())
        evidence_text.assert_called_once_with({"claim": "raw"})
        extractor.assert_called_once_with("evidence surface")

        for name, target, patches in (
            (
                "evidence text",
                lambda: evidence_support({}, []),
                (
                    patch.object(
                        financial_numeric_surface,
                        "evidence_text_for_numeric_support",
                        side_effect=RuntimeError("evidence text failed"),
                    ),
                ),
            ),
            (
                "text extract",
                lambda: text_support("raw text", []),
                (
                    patch.object(
                        financial_numeric_surface,
                        "extract_numeric_surface_candidates",
                        side_effect=RuntimeError("text extract failed"),
                    ),
                ),
            ),
            (
                "equivalence",
                lambda: text_support("raw text", [{"id": "answer"}]),
                (
                    patch.object(
                        financial_numeric_surface,
                        "extract_numeric_surface_candidates",
                        return_value=[{"id": "text"}],
                    ),
                    patch.object(
                        financial_numeric_surface,
                        "numeric_surface_candidates_equivalent",
                        side_effect=RuntimeError("equivalence failed"),
                    ),
                ),
            ),
        ):
            with self.subTest(propagates=name):
                entered = []
                for active_patch in patches:
                    entered.append(active_patch)
                    active_patch.start()
                try:
                    with self.assertRaisesRegex(RuntimeError, f"{name} failed"):
                        target()
                finally:
                    for active_patch in reversed(entered):
                        active_patch.stop()

        events = []

        class CandidateContainer:
            def __init__(self, name: str, truth: bool, *, poison_second: bool = False) -> None:
                self.name = name
                self.truth = truth
                self.poison_second = poison_second
                self.truth_calls = 0

            def __bool__(self) -> bool:
                self.truth_calls += 1
                events.append(f"bool:{self.name}:{self.truth_calls}")
                if self.poison_second and self.truth_calls == 2:
                    raise RuntimeError(f"{self.name} second truth failed")
                return self.truth

            def __iter__(self):
                events.append(f"iter:{self.name}")
                return iter(())

        answer_empty = CandidateContainer("answer", False)
        reference_unused = CandidateContainer("reference", True)
        with patch.object(
            financial_numeric_surface,
            "extract_numeric_surface_candidates",
            side_effect=(answer_empty, reference_unused),
        ):
            self.assertFalse(conflicts("answer", "reference"))
        self.assertEqual(events, ["bool:answer:1", "bool:answer:2"])

        events.clear()
        answer_present = CandidateContainer("answer", True)
        reference_empty = CandidateContainer("reference", False)
        with patch.object(
            financial_numeric_surface,
            "extract_numeric_surface_candidates",
            side_effect=(answer_present, reference_empty),
        ):
            self.assertFalse(conflicts("answer", "reference"))
        self.assertEqual(
            events,
            ["bool:answer:1", "bool:reference:1", "bool:reference:2"],
        )

        answer_poison = CandidateContainer("answer", False, poison_second=True)
        with patch.object(
            financial_numeric_surface,
            "extract_numeric_surface_candidates",
            side_effect=(answer_poison, CandidateContainer("reference", True)),
        ):
            with self.assertRaisesRegex(RuntimeError, "answer second truth failed"):
                conflicts("answer", "reference")

    def test_table_numeric_support_promotion_preserves_behavior_contract(self) -> None:
        promote = financial_numeric_surface.promote_table_numeric_support_evidence

        class Poison:
            def __str__(self):
                raise RuntimeError("later input accessed")

            def __iter__(self):
                raise RuntimeError("later input iterated")

        for name, evidence in (
            ("missing metadata", {"claim": Poison()}),
            ("blank table text", {"metadata": {"table_value_labels_text": " \n "}}),
        ):
            with self.subTest(owner_zero=name):
                self.assertIs(
                    promote(evidence, final_answer=Poison(), answer_candidates=Poison()),
                    evidence,
                )

        final_answer = (
            "alpha metric 10%, alpha metric 20%, beta metric 30%, "
            "gamma metric 40%, delta metric 50%"
        )
        answer_candidates = extract_numeric_surface_candidates(final_answer)
        nested = {"keep": True}
        metadata_nested = {"keep": "metadata"}
        evidence = {
            "evidence_id": "ev_table",
            "claim": "existing claim",
            "quote_span": "existing quote",
            "metadata": {
                "table_header_context": " Item | 2023 ",
                "table_context": " Consolidated ",
                "table_value_labels_text": "\n".join(
                    [
                        " alpha metric 10% ",
                        "alpha metric 20%",
                        "beta metric 30%",
                        "gamma metric 40%",
                        "delta metric 50%",
                    ]
                ),
                "nested": metadata_nested,
            },
            "nested": nested,
        }
        before = deepcopy((evidence, answer_candidates))
        support_text = (
            "Item | 2023 Consolidated ; alpha metric 10% ; alpha metric 20% ; "
            "beta metric 30% ; gamma metric 40%"
        )

        real_line_extract = financial_numeric_surface.extract_numeric_surface_candidates
        real_line_equivalent = financial_numeric_surface.numeric_surface_candidates_equivalent

        def extract_before_cap(line):
            if "delta metric" in line:
                raise RuntimeError("fifth line extracted")
            return real_line_extract(line)

        def equivalent_before_cap(answer_candidate, line_candidate):
            if line_candidate.get("text") == "50%":
                raise RuntimeError("fifth line compared")
            return real_line_equivalent(answer_candidate, line_candidate)

        with (
            patch.object(
                financial_numeric_surface,
                "extract_numeric_surface_candidates",
                side_effect=extract_before_cap,
            ),
            patch.object(
                financial_numeric_surface,
                "numeric_surface_candidates_equivalent",
                side_effect=equivalent_before_cap,
            ),
        ):
            promoted = promote(
                evidence,
                final_answer=final_answer,
                answer_candidates=answer_candidates,
            )

        self.assertEqual(
            promoted,
            {
                **evidence,
                "claim": f"existing claim | {support_text}",
                "quote_span": f"existing quote | {support_text}",
                "metadata": {
                    **evidence["metadata"],
                    "final_answer_table_numeric_support": support_text,
                },
            },
        )
        self.assertIsNot(promoted, evidence)
        self.assertIsNot(promoted["metadata"], evidence["metadata"])
        self.assertIs(promoted["nested"], nested)
        self.assertIs(promoted["metadata"]["nested"], metadata_nested)
        self.assertEqual((evidence, answer_candidates), before)

        headerless = {
            "claim": "",
            "quote_span": "",
            "metadata": {"table_value_labels_text": "target 10%"},
        }
        headerless_promoted = promote(
            headerless,
            final_answer="target 10%",
            answer_candidates=extract_numeric_surface_candidates("target 10%"),
        )
        self.assertEqual(
            headerless_promoted,
            {
                "claim": "target 10%",
                "quote_span": "target 10%",
                "metadata": {
                    "table_value_labels_text": "target 10%",
                    "final_answer_table_numeric_support": "target 10%",
                },
            },
        )

        for name, table_text, answer in (
            ("short label", "x 10%", "x 10%"),
            ("label mismatch", "other metric 10%", "target metric 10%"),
            ("missing number", "target metric", "target metric 10%"),
            ("numeric mismatch", "target metric 10%", "target metric 20%"),
        ):
            with self.subTest(no_support=name):
                row = {"metadata": {"table_value_labels_text": table_text}}
                self.assertIs(
                    promote(
                        row,
                        final_answer=answer,
                        answer_candidates=extract_numeric_surface_candidates(answer),
                    ),
                    row,
                )

    def test_table_numeric_support_promotion_preserves_access_and_exception_contract(self) -> None:
        promote = financial_numeric_surface.promote_table_numeric_support_evidence
        events = []

        class TrackedMapping(Mapping):
            def __init__(self, name, values):
                self.name = name
                self.values = values

            def __len__(self):
                events.append(f"len:{self.name}")
                return len(self.values)

            def __iter__(self):
                events.append(f"iter:{self.name}")
                return iter(self.values)

            def __getitem__(self, key):
                events.append(f"item:{self.name}:{key}")
                return self.values[key]

            def get(self, key, default=None):
                events.append(f"get:{self.name}:{key}")
                return self.values.get(key, default)

        metadata = TrackedMapping(
            "metadata",
            {
                "table_value_labels_text": " target 10% ",
                "table_header_context": " Header ",
                "table_context": " Context ",
            },
        )
        evidence = TrackedMapping(
            "evidence",
            {
                "evidence_id": "ev_table",
                "claim": " claim ",
                "quote_span": " quote ",
                "metadata": metadata,
            },
        )
        real_normalize = financial_numeric_surface._normalise_spaces

        def normalize(value):
            events.append(f"normalize:{value!r}")
            return real_normalize(value)

        def extract(value):
            events.append(f"extract:{value!r}")
            return [{"kind": "percent", "value": 10.0, "unit": "%", "text": "10%"}]

        def equivalent(left, right):
            events.append(f"equivalent:{left.get('text')}:{right.get('text')}")
            return True

        tracked_answer_candidates = extract_numeric_surface_candidates("target 10%")
        with (
            patch.object(financial_numeric_surface, "_normalise_spaces", side_effect=normalize),
            patch.object(
                financial_numeric_surface,
                "extract_numeric_surface_candidates",
                side_effect=extract,
            ),
            patch.object(
                financial_numeric_surface,
                "numeric_surface_candidates_equivalent",
                side_effect=equivalent,
            ),
        ):
            promoted = promote(
                evidence,
                final_answer="target 10%",
                answer_candidates=tracked_answer_candidates,
            )
        self.assertEqual(
            promoted["metadata"]["final_answer_table_numeric_support"],
            "Header Context ; target 10%",
        )
        milestones = [
            "get:evidence:metadata",
            "normalize:' target 10% '",
            "normalize:' target 10% '",
            "normalize:'target 10%'",
            "normalize:'target   '",
            "extract:'target 10%'",
            "equivalent:10%:10%",
            "normalize:' Header   Context '",
            "normalize:'Header Context ; target 10%'",
            "iter:evidence",
            "normalize:' claim '",
            "normalize:' quote '",
            "normalize:'claim | Header Context ; target 10%'",
            "normalize:'quote | Header Context ; target 10%'",
        ]
        cursor = 0
        for event in events:
            if cursor < len(milestones) and event == milestones[cursor]:
                cursor += 1
        self.assertEqual(cursor, len(milestones))
        self.assertEqual(events.count("normalize:' target 10% '"), 2)

        comparison_order = []
        answer_rows = [{"id": "answer_a"}, {"id": "answer_b"}]
        line_rows = [{"id": "line_a"}, {"id": "line_b"}]

        def compare_rows(answer_row, line_row):
            comparison_order.append((answer_row["id"], line_row["id"]))
            return answer_row["id"] == "answer_b" and line_row["id"] == "line_b"

        with (
            patch.object(
                financial_numeric_surface,
                "extract_numeric_surface_candidates",
                return_value=line_rows,
            ),
            patch.object(
                financial_numeric_surface,
                "numeric_surface_candidates_equivalent",
                side_effect=compare_rows,
            ),
        ):
            comparison_promoted = promote(
                {"metadata": {"table_value_labels_text": "target 10%"}},
                final_answer="target 10%",
                answer_candidates=answer_rows,
            )
        self.assertEqual(
            comparison_order,
            [
                ("answer_a", "line_a"),
                ("answer_a", "line_b"),
                ("answer_b", "line_a"),
                ("answer_b", "line_b"),
            ],
        )
        self.assertEqual(
            comparison_promoted["metadata"]["final_answer_table_numeric_support"],
            "target 10%",
        )

        class HeaderPoisonDict(dict):
            def get(self, key, default=None):
                if key in {"table_header_context", "table_context"}:
                    raise RuntimeError("header accessed")
                return super().get(key, default)

        no_support = {
            "metadata": {
                "table_value_labels_text": "target 10%",
                "table_header_context": "poison",
                "table_context": "poison",
            }
        }
        with patch.object(financial_numeric_surface, "dict", HeaderPoisonDict, create=True):
            self.assertIs(
                promote(
                    no_support,
                    final_answer="target 20%",
                    answer_candidates=extract_numeric_surface_candidates("target 20%"),
                ),
                no_support,
            )

        class GetBomb(Mapping):
            def __len__(self):
                return 1

            def __iter__(self):
                return iter(("metadata",))

            def __getitem__(self, key):
                raise KeyError(key)

            def get(self, _key, _default=None):
                raise RuntimeError("mapping get failed")

        class CopyBomb(Mapping):
            def __len__(self):
                return 1

            def __iter__(self):
                raise RuntimeError("mapping copy failed")

            def __getitem__(self, key):
                raise KeyError(key)

        class StringBomb:
            def __str__(self):
                raise RuntimeError("string failed")

        with self.assertRaisesRegex(RuntimeError, "mapping get failed"):
            promote(GetBomb(), final_answer="10%", answer_candidates=[])
        with self.assertRaisesRegex(RuntimeError, "mapping copy failed"):
            promote({"metadata": CopyBomb()}, final_answer="10%", answer_candidates=[])
        with self.assertRaisesRegex(RuntimeError, "string failed"):
            promote(
                {"metadata": {"table_value_labels_text": StringBomb()}},
                final_answer="10%",
                answer_candidates=[],
            )
        for owner_name, error_text, patch_name in (
            ("normalizer", "normalizer failed", "_normalise_spaces"),
            ("extractor", "extractor failed", "extract_numeric_surface_candidates"),
        ):
            with self.subTest(propagates=owner_name), patch.object(
                financial_numeric_surface,
                patch_name,
                side_effect=RuntimeError(error_text),
            ):
                with self.assertRaisesRegex(RuntimeError, error_text):
                    promote(
                        {"metadata": {"table_value_labels_text": "target 10%"}},
                        final_answer="target 10%",
                        answer_candidates=[],
                    )
        with patch.object(
            financial_numeric_surface,
            "numeric_surface_candidates_equivalent",
            side_effect=RuntimeError("equivalence failed"),
        ):
            with self.assertRaisesRegex(RuntimeError, "equivalence failed"):
                promote(
                    {"metadata": {"table_value_labels_text": "target 10%"}},
                    final_answer="target 10%",
                    answer_candidates=extract_numeric_surface_candidates("target 10%"),
                )



if __name__ == "__main__":
    unittest.main()
