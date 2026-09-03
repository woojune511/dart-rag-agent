import unittest
from copy import deepcopy
from unittest.mock import Mock, patch

from src.agent import (
    financial_graph_calculation,
    financial_runtime_trace,
    financial_text_surface,
)

from src.agent.financial_text_surface import (
    narrative_sentence_looks_abbreviated_fragment,
    narrative_sentence_looks_table_noisy,
    polish_korean_particle_pairs,
    split_narrative_sentences,
    topic_particle,
)


class FinancialTextSurfaceTests(unittest.TestCase):
    def test_current_source_context_term_tokenization_policy_laziness_and_exceptions(self) -> None:
        policy = {
            "context_stopwords": ("Stop",),
            "preserve": {"nested": True},
        }
        original_policy = deepcopy(policy)
        query = " Alpha (Beta) A 2024 abc2 Stop alpha Alpha "

        with patch.object(financial_text_surface, "CALCULATION_NARRATIVE_POLICY", policy):
            self.assertEqual(
                financial_text_surface.narrative_context_terms(query),
                ["Alpha", "(Beta)", "alpha"],
            )
        self.assertEqual(policy, original_policy)

        events = []

        class RecordingQuery:
            def __bool__(self) -> bool:
                events.append("query:bool")
                return True

            def __str__(self) -> str:
                events.append("query:str")
                return " raw query "

        class RecordingPolicy(dict):
            def get(self, key, default=None):
                events.append(("policy:get", key, default))
                return super().get(key, default)

        def normalize(value):
            events.append(("normalize", value))
            return "normalized query"

        def findall(pattern, value):
            events.append(("findall", pattern, value))
            return [" keep ", "x", "blocked", "a1", "22", "keep", "final"]

        with (
            patch.object(
                financial_text_surface,
                "CALCULATION_NARRATIVE_POLICY",
                RecordingPolicy(context_stopwords=("blocked",)),
            ),
            patch.object(financial_text_surface, "_normalise_spaces", side_effect=normalize),
            patch.object(financial_text_surface.re, "findall", side_effect=findall),
        ):
            self.assertEqual(
                financial_text_surface.narrative_context_terms(RecordingQuery()),
                ["keep", "final"],
            )
        self.assertEqual(
            events[:5],
            [
                "query:bool",
                "query:str",
                ("normalize", " raw query "),
                ("findall", "[\uac00-\ud7a3A-Za-z0-9()]+", "normalized query"),
                ("policy:get", "context_stopwords", None),
            ],
        )

        class FalsyQuery:
            def __bool__(self) -> bool:
                events.append("falsy:bool")
                return False

            def __str__(self) -> str:
                raise RuntimeError("falsy query string accessed")

        events.clear()
        with (
            patch.object(
                financial_text_surface,
                "CALCULATION_NARRATIVE_POLICY",
                RecordingPolicy(context_stopwords=()),
            ),
            patch.object(
                financial_text_surface,
                "_normalise_spaces",
                side_effect=lambda value: events.append(("normalize", value)) or value,
            ),
            patch.object(
                financial_text_surface.re,
                "findall",
                side_effect=lambda pattern, value: events.append(("findall", pattern, value)) or [],
            ),
        ):
            self.assertEqual(financial_text_surface.narrative_context_terms(FalsyQuery()), [])
        self.assertEqual(
            events,
            [
                "falsy:bool",
                ("normalize", ""),
                ("findall", "[\uac00-\ud7a3A-Za-z0-9()]+", ""),
                ("policy:get", "context_stopwords", None),
            ],
        )

        class QueryStringBomb:
            def __bool__(self) -> bool:
                return True

            def __str__(self) -> str:
                raise RuntimeError("query string failed")

        policy_access = Mock()

        class AccessPolicy(dict):
            def get(self, key, default=None):
                policy_access(key, default)
                return ()

        with patch.object(
            financial_text_surface,
            "CALCULATION_NARRATIVE_POLICY",
            AccessPolicy(),
        ):
            with self.assertRaisesRegex(RuntimeError, "query string failed"):
                financial_text_surface.narrative_context_terms(QueryStringBomb())
        policy_access.assert_not_called()

        with (
            patch.object(financial_text_surface, "CALCULATION_NARRATIVE_POLICY", AccessPolicy()),
            patch.object(
                financial_text_surface,
                "_normalise_spaces",
                side_effect=RuntimeError("normalization failed"),
            ),
        ):
            policy_access.reset_mock()
            with self.assertRaisesRegex(RuntimeError, "normalization failed"):
                financial_text_surface.narrative_context_terms("query")
        policy_access.assert_not_called()

        with (
            patch.object(financial_text_surface, "CALCULATION_NARRATIVE_POLICY", AccessPolicy()),
            patch.object(
                financial_text_surface.re,
                "findall",
                side_effect=RuntimeError("tokenization failed"),
            ),
        ):
            policy_access.reset_mock()
            with self.assertRaisesRegex(RuntimeError, "tokenization failed"):
                financial_text_surface.narrative_context_terms("query")
        policy_access.assert_not_called()

        class TokenStripBomb:
            def strip(self):
                raise RuntimeError("token filter accessed")

        class FailingPolicy(dict):
            def get(self, key, default=None):
                raise RuntimeError("stopword policy failed")

        with (
            patch.object(financial_text_surface, "CALCULATION_NARRATIVE_POLICY", FailingPolicy()),
            patch.object(financial_text_surface.re, "findall", return_value=[TokenStripBomb()]),
        ):
            with self.assertRaisesRegex(RuntimeError, "stopword policy failed"):
                financial_text_surface.narrative_context_terms("query")

        class StopwordStringBomb:
            def __str__(self) -> str:
                raise RuntimeError("stopword string failed")

        with patch.object(
            financial_text_surface,
            "CALCULATION_NARRATIVE_POLICY",
            {"context_stopwords": (StopwordStringBomb(),)},
        ):
            with self.assertRaisesRegex(RuntimeError, "stopword string failed"):
                financial_text_surface.narrative_context_terms("query")

    def test_current_source_focus_variant_policy_parentheses_order_and_exceptions(self) -> None:
        source_terms = [
            " Alpha (Beta) ",
            "Beta",
            "generic",
            "Alpha",
            "X(Y)",
            "Other (excluded)",
        ]
        original_terms = list(source_terms)
        policy = {
            "growth_generic_focus_terms": ("generic", "beta"),
            "context_reuse_excluded_terms": ("excluded",),
            "preserve": {"nested": True},
        }
        original_policy = deepcopy(policy)
        query = object()

        with (
            patch.object(financial_text_surface, "CALCULATION_NARRATIVE_POLICY", policy),
            patch.object(financial_text_surface, "narrative_context_terms", return_value=source_terms) as terms,
        ):
            self.assertEqual(
                financial_text_surface.narrative_focus_variants(query),
                ["Alpha (Beta)", "Alpha", "X(Y)", "Other (excluded)", "Other"],
            )
        terms.assert_called_once_with(query)
        self.assertEqual(source_terms, original_terms)
        self.assertEqual(policy, original_policy)

        events = []

        class RecordingPolicy(dict):
            def get(self, key, default=None):
                events.append(("policy:get", key))
                return super().get(key, default)

        real_findall = financial_text_surface.re.findall
        real_sub = financial_text_surface.re.sub

        def findall(pattern, value):
            events.append(("findall", pattern, value))
            return real_findall(pattern, value)

        def substitute(pattern, replacement, value):
            events.append(("sub", pattern, replacement, value))
            return real_sub(pattern, replacement, value)

        helper = Mock(side_effect=lambda value: events.append(("terms", value)) or ["Focus (Inner)"])
        with (
            patch.object(
                financial_text_surface,
                "CALCULATION_NARRATIVE_POLICY",
                RecordingPolicy(
                    growth_generic_focus_terms=(),
                    context_reuse_excluded_terms=(),
                ),
            ),
            patch.object(financial_text_surface, "narrative_context_terms", helper),
            patch.object(financial_text_surface.re, "findall", side_effect=findall),
            patch.object(financial_text_surface.re, "sub", side_effect=substitute),
        ):
            self.assertEqual(
                financial_text_surface.narrative_focus_variants("query"),
                ["Focus (Inner)", "Inner", "Focus"],
            )
        structural_events = [
            event
            for event in events
            if event[0] != "sub" or event[1] == r"\([^)]*\)"
        ]
        self.assertEqual(
            structural_events,
            [
                ("policy:get", "growth_generic_focus_terms"),
                ("policy:get", "context_reuse_excluded_terms"),
                ("terms", "query"),
                ("findall", r"\(([^)]+)\)", "Focus (Inner)"),
                ("sub", r"\([^)]*\)", " ", "Focus (Inner)"),
            ],
        )

        helper = Mock()

        class PolicyAccessBomb(dict):
            def get(self, key, default=None):
                raise RuntimeError(f"policy access failed: {key}")

        with (
            patch.object(
                financial_text_surface,
                "CALCULATION_NARRATIVE_POLICY",
                PolicyAccessBomb(),
            ),
            patch.object(financial_text_surface, "narrative_context_terms", helper),
        ):
            with self.assertRaisesRegex(RuntimeError, "policy access failed"):
                financial_text_surface.narrative_focus_variants("query")
        helper.assert_not_called()

        helper = Mock()
        with (
            patch.object(
                financial_text_surface,
                "CALCULATION_NARRATIVE_POLICY",
                {"growth_generic_focus_terms": ("generic",), "context_reuse_excluded_terms": ()},
            ),
            patch.object(
                financial_text_surface,
                "_normalise_spaces",
                side_effect=RuntimeError("generic normalization failed"),
            ),
            patch.object(financial_text_surface, "narrative_context_terms", helper),
        ):
            with self.assertRaisesRegex(RuntimeError, "generic normalization failed"):
                financial_text_surface.narrative_focus_variants("query")
        helper.assert_not_called()

        with (
            patch.object(
                financial_text_surface,
                "CALCULATION_NARRATIVE_POLICY",
                {"growth_generic_focus_terms": (), "context_reuse_excluded_terms": ()},
            ),
            patch.object(
                financial_text_surface,
                "narrative_context_terms",
                side_effect=RuntimeError("term extraction failed"),
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "term extraction failed"):
                financial_text_surface.narrative_focus_variants("query")

        real_findall = financial_text_surface.re.findall
        with (
            patch.object(
                financial_text_surface,
                "CALCULATION_NARRATIVE_POLICY",
                {"growth_generic_focus_terms": (), "context_reuse_excluded_terms": ()},
            ),
            patch.object(financial_text_surface, "narrative_context_terms", return_value=["Focus (Inner)"]),
            patch.object(financial_text_surface.re, "findall", wraps=real_findall),
            patch.object(
                financial_text_surface.re,
                "sub",
                side_effect=RuntimeError("outside removal failed"),
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "outside removal failed"):
                financial_text_surface.narrative_focus_variants("query")

        with (
            patch.object(
                financial_text_surface,
                "CALCULATION_NARRATIVE_POLICY",
                {"growth_generic_focus_terms": (), "context_reuse_excluded_terms": ()},
            ),
            patch.object(financial_text_surface, "narrative_context_terms", return_value=["Focus (Inner)"]),
            patch.object(
                financial_text_surface.re,
                "findall",
                side_effect=RuntimeError("parenthetical matching failed"),
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "parenthetical matching failed"):
                financial_text_surface.narrative_focus_variants("query")

    def test_current_source_parenthetical_variant_filter_order_laziness_and_exceptions(self) -> None:
        source_terms = [
            " Alpha (Beta) ",
            "Plain",
            "Alpha (Beta)",
            "X(Y)",
            "()",
            "Q()",
            "Other (B)",
        ]
        original_terms = list(source_terms)
        query = object()

        with patch.object(financial_text_surface, "narrative_context_terms", return_value=source_terms) as terms:
            self.assertEqual(
                financial_text_surface.parenthetical_focus_variants(query),
                ["Beta", "Alpha", "Other"],
            )
        terms.assert_called_once_with(query)
        self.assertEqual(source_terms, original_terms)

        events = []

        def normalize(value):
            events.append(("normalize", value))
            return " ".join(str(value).split())

        real_findall = financial_text_surface.re.findall
        real_sub = financial_text_surface.re.sub

        def findall(pattern, value):
            events.append(("findall", pattern, value))
            return real_findall(pattern, value)

        def substitute(pattern, replacement, value):
            events.append(("sub", pattern, replacement, value))
            return real_sub(pattern, replacement, value)

        with (
            patch.object(
                financial_text_surface,
                "narrative_context_terms",
                side_effect=lambda value: events.append(("terms", value))
                or ["Plain", " Focus (Inner) "],
            ),
            patch.object(financial_text_surface, "_normalise_spaces", side_effect=normalize),
            patch.object(financial_text_surface.re, "findall", side_effect=findall) as matches,
            patch.object(financial_text_surface.re, "sub", side_effect=substitute) as strips,
        ):
            self.assertEqual(
                financial_text_surface.parenthetical_focus_variants("query"),
                ["Inner", "Focus"],
            )
        self.assertEqual(events[0], ("terms", "query"))
        self.assertEqual(events[1], ("normalize", "Plain"))
        self.assertNotIn(("normalize", ""), events)
        self.assertEqual(matches.call_count, 1)
        self.assertEqual(strips.call_count, 1)
        self.assertLess(
            events.index(("findall", r"\(([^)]+)\)", "Focus (Inner)")),
            events.index(("sub", r"\([^)]*\)", " ", "Focus (Inner)")),
        )

        with patch.object(
            financial_text_surface,
            "narrative_context_terms",
            side_effect=RuntimeError("term extraction failed"),
        ):
            with self.assertRaisesRegex(RuntimeError, "term extraction failed"):
                financial_text_surface.parenthetical_focus_variants("query")

        with (
            patch.object(financial_text_surface, "narrative_context_terms", return_value=["Focus (Inner)"]),
            patch.object(
                financial_text_surface,
                "_normalise_spaces",
                side_effect=RuntimeError("term normalization failed"),
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "term normalization failed"):
                financial_text_surface.parenthetical_focus_variants("query")

        with (
            patch.object(financial_text_surface, "narrative_context_terms", return_value=["Focus (Inner)"]),
            patch.object(
                financial_text_surface.re,
                "findall",
                side_effect=RuntimeError("parenthetical matching failed"),
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "parenthetical matching failed"):
                financial_text_surface.parenthetical_focus_variants("query")

        real_findall = financial_text_surface.re.findall
        with (
            patch.object(financial_text_surface, "narrative_context_terms", return_value=["Focus (Inner)"]),
            patch.object(financial_text_surface.re, "findall", wraps=real_findall),
            patch.object(
                financial_text_surface.re,
                "sub",
                side_effect=RuntimeError("outside removal failed"),
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "outside removal failed"):
                financial_text_surface.parenthetical_focus_variants("query")



    def test_current_source_context_sentence_selector_pins_ranking_copy_laziness_and_exceptions(self) -> None:
        from collections.abc import Mapping

        selector = financial_text_surface.narrative_context_sentence_from_evidence

        class IterationBomb:
            def __iter__(self):
                raise RuntimeError("evidence iterated")

        terms = Mock()
        with (
            patch.object(financial_text_surface, "query_requests_narrative_context", return_value=False) as query_gate,
            patch.object(financial_text_surface, "narrative_context_terms", terms),
        ):
            self.assertEqual(
                selector("query", IterationBomb()),
                "",
            )
        query_gate.assert_called_once_with("query")
        terms.assert_not_called()

        with (
            patch.object(financial_text_surface, "query_requests_narrative_context", return_value=True),
            patch.object(financial_text_surface, "narrative_context_terms", return_value=[] ) as terms,
        ):
            self.assertEqual(
                selector("query", IterationBomb()),
                "",
            )
        terms.assert_called_once_with("query")

        query_terms = ["focus", "driver"]
        policy = {
            "context_priority_section_terms": ("Priority",),
            "context_support_levels": ("context",),
            "preserve": {"nested": True},
        }
        evidence_items = [
            {
                "source_anchor": "source",
                "metadata": {"section_path": "Priority focus", "section": "driver"},
                "claim": "chosen first. ignored second.",
                "quote_span": "unused quote",
                "raw_row_text": "unused row",
                "support_level": "CONTEXT",
                "nested": {"preserve": True},
            },
            {
                "source_anchor": "Priority focus driver",
                "metadata": {},
                "claim": "later tie",
                "support_level": "context",
            },
            {
                "source_anchor": "",
                "metadata": {},
                "claim": "",
                "quote_span": "focus quote",
                "raw_row_text": "driver raw must remain lazy",
                "support_level": "other",
            },
            {
                "source_anchor": "",
                "metadata": {},
                "claim": "",
                "quote_span": "",
                "raw_row_text": "driver raw",
                "support_level": "other",
            },
            {
                "source_anchor": "Priority focus driver",
                "metadata": {},
                "claim": "   ",
                "quote_span": "focus driver quote must remain lazy",
                "support_level": "context",
            },
        ]
        original_evidence = deepcopy(evidence_items)
        splitter = Mock(return_value=["chosen first", "ignored second"])
        with (
            patch.object(financial_text_surface, "query_requests_narrative_context", return_value=True),
            patch.object(financial_text_surface, "narrative_context_terms", return_value=query_terms),
            patch.object(financial_text_surface, "CALCULATION_NARRATIVE_POLICY", policy),
            patch.object(financial_text_surface, "split_narrative_sentences", splitter),
        ):
            self.assertEqual(
                selector("query", evidence_items),
                "chosen first",
            )
        splitter.assert_called_once_with("chosen first. ignored second.")
        self.assertEqual(evidence_items, original_evidence)
        self.assertEqual(policy["preserve"], {"nested": True})
        self.assertIs(evidence_items[0]["nested"], evidence_items[0]["nested"])

        with (
            patch.object(financial_text_surface, "query_requests_narrative_context", return_value=True),
            patch.object(financial_text_surface, "narrative_context_terms", return_value=["focus"]),
            patch.object(
                financial_text_surface,
                "CALCULATION_NARRATIVE_POLICY",
                {
                    "context_priority_section_terms": ("Priority",),
                    "context_support_levels": (),
                },
            ),
            patch.object(
                financial_text_surface,
                "split_narrative_sentences",
                side_effect=lambda claim: [claim],
            ),
        ):
            self.assertEqual(
                selector(
                    "query",
                    [
                        {"source_anchor": "Priority", "claim": "priority winner"},
                        {"source_anchor": "focus", "claim": "term-only competitor"},
                    ],
                ),
                "priority winner",
            )

        support_policy_events = []

        class SupportRankingPolicy(dict):
            def get(self, key, default=None):
                support_policy_events.append(key)
                return super().get(key, default)

        support_policy = SupportRankingPolicy(
            context_priority_section_terms=(),
            context_support_levels=("context",),
        )
        with (
            patch.object(financial_text_surface, "query_requests_narrative_context", return_value=True),
            patch.object(financial_text_surface, "narrative_context_terms", return_value=["focus"]),
            patch.object(financial_text_surface, "CALCULATION_NARRATIVE_POLICY", support_policy),
            patch.object(
                financial_text_surface,
                "split_narrative_sentences",
                side_effect=lambda claim: [claim],
            ),
        ):
            self.assertEqual(
                selector(
                    "query",
                    [
                        {"source_anchor": "focus", "claim": "support winner", "support_level": "CONTEXT"},
                        {"source_anchor": "focus", "claim": "later support tie", "support_level": "context"},
                        {"source_anchor": "focus", "claim": "term-only competitor", "support_level": "other"},
                    ],
                ),
                "support winner",
            )
        self.assertEqual(
            support_policy_events,
            [
                "context_priority_section_terms",
                "context_support_levels",
            ] * 3,
        )

        with (
            patch.object(financial_text_surface, "query_requests_narrative_context", return_value=True),
            patch.object(financial_text_surface, "narrative_context_terms", return_value=["focus"]),
            patch.object(
                financial_text_surface,
                "CALCULATION_NARRATIVE_POLICY",
                {"context_priority_section_terms": (), "context_support_levels": ()},
            ),
            patch.object(financial_text_surface, "split_narrative_sentences", return_value=[]),
        ):
            self.assertEqual(
                selector(
                    "query",
                    [{"source_anchor": "focus", "claim": "original unsplit claim"}],
                ),
                "original unsplit claim",
            )

        class TruthinessBomb:
            def __bool__(self):
                raise RuntimeError("fallback truthiness accessed")

            def __str__(self):
                raise RuntimeError("fallback string accessed")

        with (
            patch.object(financial_text_surface, "query_requests_narrative_context", return_value=True),
            patch.object(financial_text_surface, "narrative_context_terms", return_value=["focus"]),
            patch.object(
                financial_text_surface,
                "CALCULATION_NARRATIVE_POLICY",
                {"context_priority_section_terms": (), "context_support_levels": ()},
            ),
        ):
            self.assertEqual(
                selector(
                    "query",
                    [
                        {
                            "source_anchor": "focus",
                            "claim": "   ",
                            "quote_span": TruthinessBomb(),
                            "raw_row_text": TruthinessBomb(),
                        }
                    ],
                ),
                "",
            )

        with (
            patch.object(financial_text_surface, "query_requests_narrative_context", return_value=True),
            patch.object(financial_text_surface, "narrative_context_terms", return_value=["focus"]),
            patch.object(
                financial_text_surface,
                "CALCULATION_NARRATIVE_POLICY",
                {"context_priority_section_terms": (), "context_support_levels": ()},
            ),
            patch.object(financial_text_surface, "split_narrative_sentences") as splitter,
        ):
            self.assertEqual(
                selector(
                    "query",
                    [{"claim": "primary", "quote_span": "focus quote", "raw_row_text": "focus row"}],
                ),
                "",
            )
            self.assertEqual(
                selector(
                    "query",
                    [{"claim": "", "quote_span": "quote", "raw_row_text": "focus row"}],
                ),
                "",
            )
        splitter.assert_not_called()

        trace = []

        class TraceEvidence(Mapping):
            def __init__(self):
                self.data = {
                    "source_anchor": "focus",
                    "metadata": {},
                    "claim": "selected",
                    "support_level": "",
                }

            def __bool__(self):
                trace.append("row:bool")
                return True

            def __iter__(self):
                trace.append("row:iter")
                return iter(self.data)

            def __getitem__(self, key):
                trace.append(("row:item", key))
                return self.data[key]

            def __len__(self):
                trace.append("row:len")
                return len(self.data)

        class TraceEvidenceItems:
            def __bool__(self):
                trace.append("items:bool")
                return True

            def __iter__(self):
                trace.append("items:iter")
                return iter([TraceEvidence()])

        with (
            patch.object(financial_text_surface, "query_requests_narrative_context", return_value=True),
            patch.object(financial_text_surface, "narrative_context_terms", return_value=["focus"]),
            patch.object(
                financial_text_surface,
                "CALCULATION_NARRATIVE_POLICY",
                {"context_priority_section_terms": (), "context_support_levels": ()},
            ),
            patch.object(financial_text_surface, "split_narrative_sentences", return_value=["selected"]),
        ):
            self.assertEqual(
                selector("query", TraceEvidenceItems()),
                "selected",
            )
        self.assertEqual(trace[:3], ["items:bool", "items:iter", "row:bool"])
        self.assertIn("row:iter", trace)
        self.assertEqual(
            [event for event in trace if isinstance(event, tuple)],
            [
                ("row:item", "source_anchor"),
                ("row:item", "metadata"),
                ("row:item", "claim"),
                ("row:item", "support_level"),
            ],
        )

        long_sentence = "x" * 218 + "  " + "tail"
        with (
            patch.object(financial_text_surface, "query_requests_narrative_context", return_value=True),
            patch.object(financial_text_surface, "narrative_context_terms", return_value=["focus"]),
            patch.object(
                financial_text_surface,
                "CALCULATION_NARRATIVE_POLICY",
                {"context_priority_section_terms": (), "context_support_levels": ()},
            ),
            patch.object(financial_text_surface, "split_narrative_sentences", return_value=[long_sentence, "later"]),
        ):
            self.assertEqual(
                selector(
                    "query",
                    [{"source_anchor": "focus", "claim": "claim"}],
                ),
                "x" * 218,
            )

        downstream = Mock()
        with (
            patch.object(
                financial_text_surface,
                "query_requests_narrative_context",
                side_effect=RuntimeError("query gate failed"),
            ),
            patch.object(financial_text_surface, "narrative_context_terms", downstream),
        ):
            with self.assertRaisesRegex(RuntimeError, "query gate failed"):
                selector("query", IterationBomb())
        downstream.assert_not_called()

        splitter = Mock()
        with (
            patch.object(financial_text_surface, "query_requests_narrative_context", return_value=True),
            patch.object(
                financial_text_surface,
                "narrative_context_terms",
                side_effect=RuntimeError("term extraction failed"),
            ),
            patch.object(financial_text_surface, "split_narrative_sentences", splitter),
        ):
            with self.assertRaisesRegex(RuntimeError, "term extraction failed"):
                selector("query", IterationBomb())
        splitter.assert_not_called()

        class CopyBomb(Mapping):
            def __bool__(self):
                return True

            def __iter__(self):
                raise RuntimeError("evidence copy failed")

            def __getitem__(self, key):
                raise AssertionError(key)

            def __len__(self):
                return 1

        splitter = Mock()
        with (
            patch.object(financial_text_surface, "query_requests_narrative_context", return_value=True),
            patch.object(financial_text_surface, "narrative_context_terms", return_value=["focus"]),
            patch.object(financial_text_surface, "split_narrative_sentences", splitter),
        ):
            with self.assertRaisesRegex(RuntimeError, "evidence iterated"):
                selector("query", IterationBomb())
            with self.assertRaisesRegex(RuntimeError, "evidence copy failed"):
                selector("query", [CopyBomb()])
        splitter.assert_not_called()

        class MetadataBomb(dict):
            def get(self, key, default=None):
                raise RuntimeError("metadata access failed")

        policy_access = Mock()

        class PolicyBomb(dict):
            def get(self, key, default=None):
                policy_access(key, default)
                raise RuntimeError("priority policy failed")

        splitter = Mock()
        with (
            patch.object(financial_text_surface, "query_requests_narrative_context", return_value=True),
            patch.object(financial_text_surface, "narrative_context_terms", return_value=["focus"]),
            patch.object(financial_text_surface, "CALCULATION_NARRATIVE_POLICY", PolicyBomb()),
            patch.object(financial_text_surface, "split_narrative_sentences", splitter),
        ):
            with self.assertRaisesRegex(RuntimeError, "metadata access failed"):
                selector(
                    "query",
                    [{"metadata": MetadataBomb(value=True), "claim": "focus"}],
                )
            with self.assertRaisesRegex(RuntimeError, "priority policy failed"):
                selector(
                    "query",
                    [{"claim": "focus"}],
                )
        self.assertEqual(policy_access.call_count, 1)
        splitter.assert_not_called()

        support_policy_events = []

        class SupportPolicyBomb(dict):
            def get(self, key, default=None):
                support_policy_events.append(key)
                if key == "context_support_levels":
                    raise RuntimeError("support policy failed")
                return ()

        splitter = Mock()
        with (
            patch.object(financial_text_surface, "query_requests_narrative_context", return_value=True),
            patch.object(financial_text_surface, "narrative_context_terms", return_value=["focus"]),
            patch.object(financial_text_surface, "CALCULATION_NARRATIVE_POLICY", SupportPolicyBomb()),
            patch.object(financial_text_surface, "split_narrative_sentences", splitter),
        ):
            with self.assertRaisesRegex(RuntimeError, "support policy failed"):
                selector(
                    "query",
                    [{"source_anchor": "focus", "claim": "claim", "support_level": "context"}],
                )
        self.assertEqual(
            support_policy_events,
            ["context_priority_section_terms", "context_support_levels"],
        )
        splitter.assert_not_called()

        with (
            patch.object(financial_text_surface, "query_requests_narrative_context", return_value=True),
            patch.object(financial_text_surface, "narrative_context_terms", return_value=["focus"]),
            patch.object(
                financial_text_surface,
                "CALCULATION_NARRATIVE_POLICY",
                {"context_priority_section_terms": (), "context_support_levels": ()},
            ),
            patch.object(
                financial_text_surface,
                "split_narrative_sentences",
                side_effect=RuntimeError("sentence split failed"),
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "sentence split failed"):
                selector(
                    "query",
                    [{"source_anchor": "focus", "claim": "claim"}],
                )

    def test_current_source_context_inclusion_pins_gates_exclusions_overlap_prefix_and_exceptions(self) -> None:
        include_context = financial_text_surface.include_narrative_context_if_needed
        events = []

        def normalize(value):
            events.append(("normalize", value))
            return " ".join(str(value).split())

        query_gate = Mock(side_effect=RuntimeError("query gate must remain lazy"))
        terms = Mock()
        with (
            patch.object(financial_text_surface, "_normalise_spaces", side_effect=normalize),
            patch.object(financial_text_surface, "query_requests_narrative_context", query_gate),
            patch.object(financial_text_surface, "narrative_context_terms", terms),
        ):
            self.assertEqual(
                include_context(
                    "   ",
                    query="query",
                    narrative_context=" context ",
                ),
                "",
            )
        self.assertEqual(events, [("normalize", "   "), ("normalize", " context ")])
        query_gate.assert_not_called()
        terms.assert_not_called()

        events.clear()
        query_gate.reset_mock()
        terms.reset_mock()
        with (
            patch.object(financial_text_surface, "_normalise_spaces", side_effect=normalize),
            patch.object(financial_text_surface, "query_requests_narrative_context", query_gate),
            patch.object(financial_text_surface, "narrative_context_terms", terms),
        ):
            self.assertEqual(
                include_context(
                    " answer ",
                    query="query",
                    narrative_context="   ",
                ),
                "answer",
            )
        self.assertEqual(events, [("normalize", " answer "), ("normalize", "   ")])
        query_gate.assert_not_called()
        terms.assert_not_called()

        query = object()
        query_gate = Mock(return_value=False)
        with (
            patch.object(financial_text_surface, "query_requests_narrative_context", query_gate),
            patch.object(financial_text_surface, "narrative_context_terms", terms),
        ):
            self.assertEqual(
                include_context(
                    " answer ",
                    query=query,
                    narrative_context=" context ",
                ),
                "answer",
            )
        query_gate.assert_called_once_with(query)
        terms.assert_not_called()

        class RecordingPolicy(dict):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.events = []

            def get(self, key, default=None):
                self.events.append((key, default))
                return super().get(key, default)

        policy = RecordingPolicy(
            context_reuse_excluded_terms=("skip",),
            preserve={"nested": True},
        )
        original_policy = deepcopy(policy)
        terms = Mock(return_value=["skip", "Focus", "Focus"])
        with (
            patch.object(financial_text_surface, "query_requests_narrative_context", return_value=True),
            patch.object(financial_text_surface, "narrative_context_terms", terms),
            patch.object(financial_text_surface, "CALCULATION_NARRATIVE_POLICY", policy),
        ):
            self.assertEqual(
                include_context(
                    " answer ",
                    query=query,
                    narrative_context=" skip   Focus context ",
                ),
                "skip Focus context answer",
            )
        terms.assert_called_once_with(query)
        self.assertEqual(
            policy.events,
            [("context_reuse_excluded_terms", None)] * 3,
        )
        self.assertEqual(dict(policy), dict(original_policy))

        events.clear()
        policy = RecordingPolicy(context_reuse_excluded_terms=())
        with (
            patch.object(financial_text_surface, "_normalise_spaces", side_effect=normalize),
            patch.object(financial_text_surface, "query_requests_narrative_context", return_value=True),
            patch.object(financial_text_surface, "narrative_context_terms", return_value=["Focus"]),
            patch.object(financial_text_surface, "CALCULATION_NARRATIVE_POLICY", policy),
        ):
            self.assertEqual(
                include_context(
                    " Focus answer ",
                    query="query",
                    narrative_context=" Focus context ",
                ),
                "Focus answer",
            )
        self.assertEqual(
            events,
            [("normalize", " Focus answer "), ("normalize", " Focus context ")],
        )
        self.assertEqual(policy.events, [("context_reuse_excluded_terms", None)])

        events.clear()
        with (
            patch.object(financial_text_surface, "_normalise_spaces", side_effect=normalize),
            patch.object(financial_text_surface, "query_requests_narrative_context", return_value=True),
            patch.object(financial_text_surface, "narrative_context_terms", return_value=["Absent"]),
            patch.object(
                financial_text_surface,
                "CALCULATION_NARRATIVE_POLICY",
                {"context_reuse_excluded_terms": ()},
            ),
        ):
            self.assertEqual(
                include_context(
                    " prefix context suffix ",
                    query="query",
                    narrative_context=" context ",
                ),
                "prefix context suffix",
            )
        self.assertEqual(
            events,
            [("normalize", " prefix context suffix "), ("normalize", " context ")],
        )

        with (
            patch.object(financial_text_surface, "query_requests_narrative_context", return_value=True),
            patch.object(financial_text_surface, "narrative_context_terms", return_value=["skip"]),
            patch.object(
                financial_text_surface,
                "CALCULATION_NARRATIVE_POLICY",
                {"context_reuse_excluded_terms": ("skip",)},
            ),
        ):
            self.assertEqual(
                include_context(
                    "answer",
                    query="query",
                    narrative_context="skip context",
                ),
                "skip context answer",
            )

        with (
            patch.object(financial_text_surface, "query_requests_narrative_context", return_value=True),
            patch.object(financial_text_surface, "narrative_context_terms", return_value=["Focus"]),
            patch.object(
                financial_text_surface,
                "CALCULATION_NARRATIVE_POLICY",
                {"context_reuse_excluded_terms": ()},
            ),
        ):
            self.assertEqual(
                include_context(
                    "focus answer",
                    query="query",
                    narrative_context="Focus context",
                ),
                "Focus context focus answer",
            )

        with (
            patch.object(financial_text_surface, "query_requests_narrative_context", return_value=True),
            patch.object(financial_text_surface, "narrative_context_terms", return_value=[]),
        ):
            self.assertEqual(
                include_context(
                    "prefix context suffix",
                    query="query",
                    narrative_context="Context",
                ),
                "Context prefix context suffix",
            )

        class StringBomb:
            def __init__(self, message):
                self.message = message

            def __bool__(self):
                return True

            def __str__(self):
                raise RuntimeError(self.message)

        context = StringBomb("context string accessed")
        query_gate = Mock()
        with (
            patch.object(financial_text_surface, "query_requests_narrative_context", query_gate),
            patch.object(financial_text_surface, "narrative_context_terms") as terms,
        ):
            with self.assertRaisesRegex(RuntimeError, "answer string failed"):
                include_context(
                    StringBomb("answer string failed"),
                    query="query",
                    narrative_context=context,
                )
        query_gate.assert_not_called()
        terms.assert_not_called()

        query_gate = Mock()
        with (
            patch.object(financial_text_surface, "query_requests_narrative_context", query_gate),
            patch.object(financial_text_surface, "narrative_context_terms") as terms,
        ):
            with self.assertRaisesRegex(RuntimeError, "context string failed"):
                include_context(
                    "answer",
                    query="query",
                    narrative_context=StringBomb("context string failed"),
                )
        query_gate.assert_not_called()
        terms.assert_not_called()

        terms = Mock()
        with (
            patch.object(
                financial_text_surface,
                "query_requests_narrative_context",
                side_effect=RuntimeError("query gate failed"),
            ),
            patch.object(financial_text_surface, "narrative_context_terms", terms),
        ):
            with self.assertRaisesRegex(RuntimeError, "query gate failed"):
                include_context(
                    "answer",
                    query="query",
                    narrative_context="context",
                )
        terms.assert_not_called()

        policy_access = Mock()

        class PolicyBomb(dict):
            def get(self, key, default=None):
                policy_access(key, default)
                raise RuntimeError("reuse policy failed")

        with (
            patch.object(financial_text_surface, "query_requests_narrative_context", return_value=True),
            patch.object(
                financial_text_surface,
                "narrative_context_terms",
                side_effect=RuntimeError("term extraction failed"),
            ),
            patch.object(financial_text_surface, "CALCULATION_NARRATIVE_POLICY", PolicyBomb()),
        ):
            with self.assertRaisesRegex(RuntimeError, "term extraction failed"):
                include_context(
                    "answer",
                    query="query",
                    narrative_context="context",
                )
        policy_access.assert_not_called()

        with (
            patch.object(financial_text_surface, "query_requests_narrative_context", return_value=True),
            patch.object(financial_text_surface, "narrative_context_terms", return_value=["Focus"]),
            patch.object(financial_text_surface, "CALCULATION_NARRATIVE_POLICY", PolicyBomb()),
        ):
            with self.assertRaisesRegex(RuntimeError, "reuse policy failed"):
                include_context(
                    "answer",
                    query="query",
                    narrative_context="Focus context",
                )
        self.assertEqual(policy_access.call_count, 1)

        normalize_calls = []

        def fail_final_normalize(value):
            normalize_calls.append(value)
            if len(normalize_calls) == 3:
                raise RuntimeError("prefix normalization failed")
            return " ".join(str(value).split())

        with (
            patch.object(financial_text_surface, "_normalise_spaces", side_effect=fail_final_normalize),
            patch.object(financial_text_surface, "query_requests_narrative_context", return_value=True),
            patch.object(financial_text_surface, "narrative_context_terms", return_value=[]),
        ):
            with self.assertRaisesRegex(RuntimeError, "prefix normalization failed"):
                include_context(
                    "answer",
                    query="query",
                    narrative_context="context",
                )
        self.assertEqual(normalize_calls, ["answer", "context", "context answer"])




    def test_current_source_required_policy_snippet_pins_surfaces_templates_fallbacks_and_exceptions(self) -> None:
        nested_metadata = {"preserve": True}
        metadata = {
            "table_value_labels_text": "second 999",
            "table_row_labels_text": "Metric(note) 2023 7 1,234 567",
            "table_summary_text": "summary 888",
            "table_context": "context 777",
            "unit_hint": " USD ",
            "nested": nested_metadata,
        }
        original_metadata = deepcopy(metadata)
        events = []

        class RecordingDoc:
            @property
            def metadata(self):
                events.append("metadata")
                return metadata

            @property
            def page_content(self):
                events.append("page_content")
                return "page 666"

        real_normalize = financial_text_surface._normalise_spaces

        def normalize(value):
            events.append(("normalize", value))
            return real_normalize(value)

        def policy_terms(policies, key):
            events.append(("policy_terms", policies, key))
            return ["Metric", "Second"]

        snippet_policy = {
            "policy_required_realized_footnote_suffix_pattern": r"\(note\)$",
            "policy_required_realized_current_change_template": (
                "{label}|{topic_particle}|{current_value}|{change_value}|{unit}"
            ),
            "policy_required_realized_current_template": (
                "{label}|{topic_particle}|{current_value}|{unit}"
            ),
        }
        topic = Mock(return_value="TOPIC")
        with (
            patch.object(financial_text_surface, "CALCULATION_NARRATIVE_POLICY", snippet_policy),
            patch.object(financial_text_surface, "narrative_policy_terms", side_effect=policy_terms),
            patch.object(financial_text_surface, "_normalise_spaces", side_effect=normalize),
            patch.object(financial_text_surface, "topic_particle", topic),
        ):
            self.assertEqual(
                financial_text_surface.policy_required_realized_snippet_from_doc(
                    doc=RecordingDoc(),
                    policy={"required_realized_terms": ("Metric", "Second")},
                ),
                "Metric|TOPIC|1,234|567|USD",
            )
        self.assertEqual(events[0], "metadata")
        self.assertEqual(
            events[1],
            (
                "policy_terms",
                [{"required_realized_terms": ("Metric", "Second")}],
                "required_realized_terms",
            ),
        )
        self.assertEqual(events[2], "page_content")
        self.assertEqual(
            events[3],
            (
                "normalize",
                "second 999 Metric(note) 2023 7 1,234 567 summary 888 context 777 page 666",
            ),
        )
        topic.assert_called_once_with("Metric")
        self.assertEqual(metadata, original_metadata)
        self.assertIs(metadata["nested"], nested_metadata)

        class PageBombDoc:
            metadata = {"table_value_labels_text": "must not be read", "nested": nested_metadata}

            @property
            def page_content(self):
                raise AssertionError("page content accessed")

        no_terms = Mock(return_value=[])
        with (
            patch.object(financial_text_surface, "narrative_policy_terms", no_terms),
            patch.object(
                financial_text_surface,
                "_normalise_spaces",
                side_effect=AssertionError("surface normalized"),
            ),
        ):
            self.assertEqual(
                financial_text_surface.policy_required_realized_snippet_from_doc(
                    doc=PageBombDoc(),
                    policy={"required_realized_terms": ()},
                ),
                "",
            )
        no_terms.assert_called_once_with(
            [{"required_realized_terms": ()}],
            "required_realized_terms",
        )
        self.assertIs(PageBombDoc.metadata["nested"], nested_metadata)

        class DeeperPolicyBomb(dict):
            def get(self, key, default=None):
                raise AssertionError(f"deeper policy accessed: {key}")

        blank_doc = Mock(
            metadata={
                "table_value_labels_text": "",
                "table_row_labels_text": "",
                "table_summary_text": "",
                "table_context": "",
                "unit_hint": "must not be read",
            },
            page_content="",
        )
        with (
            patch.object(financial_text_surface, "CALCULATION_NARRATIVE_POLICY", DeeperPolicyBomb()),
            patch.object(financial_text_surface, "narrative_policy_terms", return_value=["Metric"]),
            patch.object(financial_text_surface.re, "findall", side_effect=AssertionError("numbers read")),
            patch.object(
                financial_text_surface,
                "split_narrative_sentences",
                side_effect=AssertionError("split ran"),
            ),
        ):
            self.assertEqual(
                financial_text_surface.policy_required_realized_snippet_from_doc(
                    doc=blank_doc,
                    policy={"required_realized_terms": ("Metric",)},
                ),
                "",
            )

        class UnitBomb:
            def __str__(self):
                raise AssertionError("unit read")

        unmatched_doc = Mock(
            metadata={"table_value_labels_text": "Other 123", "unit_hint": UnitBomb()},
            page_content="",
        )
        with (
            patch.object(financial_text_surface, "CALCULATION_NARRATIVE_POLICY", DeeperPolicyBomb()),
            patch.object(financial_text_surface, "narrative_policy_terms", return_value=["Metric"]),
            patch.object(financial_text_surface.re, "findall", side_effect=AssertionError("numbers read")),
            patch.object(
                financial_text_surface,
                "split_narrative_sentences",
                side_effect=AssertionError("split ran"),
            ),
        ):
            self.assertEqual(
                financial_text_surface.policy_required_realized_snippet_from_doc(
                    doc=unmatched_doc,
                    policy={"required_realized_terms": ("Metric",)},
                ),
                "",
            )

        lowercase_policy = {
            "policy_required_realized_footnote_suffix_pattern": "",
            "policy_required_realized_current_template": (
                "{label}:{topic_particle}:{current_value}:{unit}"
            ),
        }
        with (
            patch.object(financial_text_surface, "CALCULATION_NARRATIVE_POLICY", lowercase_policy),
            patch.object(financial_text_surface, "narrative_policy_terms", return_value=["metric"]),
            patch.object(financial_text_surface, "topic_particle", return_value="P") as lowercase_topic,
        ):
            self.assertEqual(
                financial_text_surface.policy_required_realized_snippet_from_doc(
                    doc=Mock(
                        metadata={"table_value_labels_text": "Metric 123", "unit_hint": "units"},
                        page_content="",
                    ),
                    policy={"required_realized_terms": ("metric",)},
                ),
                "metric:P:123:units",
            )
        lowercase_topic.assert_called_once_with("metric")

        current_policy = {
            "policy_required_realized_footnote_suffix_pattern": "",
            "policy_required_realized_current_change_template": "unused {missing}",
            "policy_required_realized_current_template": (
                "{label}:{topic_particle}:{current_value}:{unit}"
            ),
        }
        current_doc = Mock(
            metadata={"table_value_labels_text": "Metric 123", "unit_hint": "units"},
            page_content="",
        )
        with (
            patch.object(financial_text_surface, "CALCULATION_NARRATIVE_POLICY", current_policy),
            patch.object(financial_text_surface, "narrative_policy_terms", return_value=["Metric"]),
            patch.object(financial_text_surface, "topic_particle", return_value="P") as current_topic,
        ):
            self.assertEqual(
                financial_text_surface.policy_required_realized_snippet_from_doc(
                    doc=current_doc,
                    policy={"required_realized_terms": ("Metric",)},
                ),
                "Metric:P:123:units",
            )
        current_topic.assert_called_once_with("Metric")

        long_sentence = "Metric " + ("x" * 230) + " 123."
        fallback_doc = Mock(metadata={}, page_content=long_sentence)
        with (
            patch.object(
                financial_text_surface,
                "CALCULATION_NARRATIVE_POLICY",
                {"policy_required_realized_footnote_suffix_pattern": ""},
            ),
            patch.object(financial_text_surface, "narrative_policy_terms", return_value=["Metric"]),
            patch.object(
                financial_text_surface,
                "split_narrative_sentences",
                return_value=[long_sentence, "Metric 456."],
            ) as splitter,
        ):
            self.assertEqual(
                financial_text_surface.policy_required_realized_snippet_from_doc(
                    doc=fallback_doc,
                    policy={"required_realized_terms": ("Metric",)},
                ),
                long_sentence[:220].rstrip(),
            )
        splitter.assert_called_once_with(long_sentence)

        window_surface = "Metric " + ("z" * 520) + " 999"
        window_doc = Mock(metadata={}, page_content=window_surface)
        with (
            patch.object(
                financial_text_surface,
                "CALCULATION_NARRATIVE_POLICY",
                {"policy_required_realized_footnote_suffix_pattern": ""},
            ),
            patch.object(financial_text_surface, "narrative_policy_terms", return_value=["Metric"]),
            patch.object(financial_text_surface, "split_narrative_sentences", return_value=[]) as splitter,
        ):
            window_result = financial_text_surface.policy_required_realized_snippet_from_doc(
                doc=window_doc,
                policy={"required_realized_terms": ("Metric",)},
            )
        self.assertEqual(window_result, window_surface[:220].rstrip())
        self.assertEqual(len(window_result), 220)
        self.assertNotIn("999", window_result)
        splitter.assert_called_once_with(window_surface)

        class MetadataAccessFailure:
            @property
            def metadata(self):
                raise RuntimeError("metadata failed")

        with self.assertRaisesRegex(RuntimeError, "metadata failed"):
            financial_text_surface.policy_required_realized_snippet_from_doc(
                doc=MetadataAccessFailure(),
                policy={},
            )

        with patch.object(
            financial_text_surface,
            "narrative_policy_terms",
            side_effect=RuntimeError("policy terms failed"),
        ):
            with self.assertRaisesRegex(RuntimeError, "policy terms failed"):
                financial_text_surface.policy_required_realized_snippet_from_doc(
                    doc=Mock(metadata={}, page_content=""),
                    policy={},
                )

        regex_doc = Mock(
            metadata={"table_value_labels_text": "Metric 123", "unit_hint": "units"},
            page_content="",
        )
        with (
            patch.object(financial_text_surface, "narrative_policy_terms", return_value=["Metric"]),
            patch.object(financial_text_surface.re, "findall", side_effect=RuntimeError("regex failed")),
        ):
            with self.assertRaisesRegex(RuntimeError, "regex failed"):
                financial_text_surface.policy_required_realized_snippet_from_doc(
                    doc=regex_doc,
                    policy={},
                )

        class FailingTemplate:
            def __str__(self):
                raise RuntimeError("template failed")

        class TemplatePolicy(dict):
            def get(self, key, default=None):
                if key == "policy_required_realized_current_template":
                    return FailingTemplate()
                return super().get(key, default)

        with (
            patch.object(
                financial_text_surface,
                "CALCULATION_NARRATIVE_POLICY",
                TemplatePolicy(policy_required_realized_footnote_suffix_pattern=""),
            ),
            patch.object(financial_text_surface, "narrative_policy_terms", return_value=["Metric"]),
            patch.object(financial_text_surface, "topic_particle", return_value="P"),
        ):
            with self.assertRaisesRegex(RuntimeError, "template failed"):
                financial_text_surface.policy_required_realized_snippet_from_doc(
                    doc=regex_doc,
                    policy={},
                )

    def test_current_source_retrieved_source_preservation_pins_gates_ties_numeric_veto_and_exceptions(self) -> None:
        answer = (
            "Numeric 123 stays. "
            "Claim alpha beta gamma delta. "
            "Second epsilon zeta eta theta. "
            "Low red blue green yellow. "
            "MISSING guarded coral indigo violet."
        )
        nested = {"preserve": True}
        evidence_items = [
            {
                "evidence_id": "other::skip",
                "claim": "not accessed",
                "quote_span": "not accessed",
            },
            {
                "evidence_id": "retrieved_narrative::missing",
                "claim": "MISSING alpha beta gamma delta",
                "quote_span": "Missing alpha beta.",
            },
            {
                "evidence_id": "retrieved_narrative::same",
                "claim": "same alpha beta",
                "quote_span": "same alpha beta",
            },
            {
                "evidence_id": "retrieved_narrative::first",
                "claim": "Claim alpha beta gamma delta.",
                "quote_span": "Quote alpha beta. Tie alpha beta.",
                "metadata": nested,
            },
            {
                "evidence_id": "retrieved_narrative::raw",
                "claim": "Second epsilon zeta eta theta.",
                "quote_span": "",
                "raw_row_text": "Raw epsilon zeta. Later epsilon zeta.",
            },
            {
                "evidence_id": "retrieved_narrative::numeric",
                "claim": "Numeric stays.",
                "quote_span": "Overstated numeric replacement.",
            },
            {
                "evidence_id": "retrieved_narrative::duplicate",
                "claim": "Claim alpha beta gamma delta.",
                "quote_span": "Later alpha beta.",
            },
            {
                "evidence_id": "retrieved_narrative::below-threshold",
                "claim": "Low red blue green yellow.",
                "quote_span": "Only red.",
            },
            {
                "evidence_id": "retrieved_narrative::answer-marker",
                "claim": "guarded coral indigo violet",
                "quote_span": "Grounded coral indigo.",
            },
        ]
        original_evidence = deepcopy(evidence_items)
        original_identities = [id(item) for item in evidence_items]
        preservation_policy = {
            "missing_answer_markers": ("MISSING",),
            "context_stopwords": (),
        }
        with patch.object(
            financial_text_surface,
            "CALCULATION_NARRATIVE_POLICY",
            preservation_policy,
        ):
            self.assertEqual(
                financial_text_surface.preserve_retrieved_narrative_source_surface(answer, evidence_items),
                (
                    "Numeric 123 stays. Quote alpha beta. Raw epsilon zeta. "
                    "Low red blue green yellow. MISSING guarded coral indigo violet."
                ),
            )
        self.assertEqual(evidence_items, original_evidence)
        self.assertEqual([id(item) for item in evidence_items], original_identities)
        self.assertIs(evidence_items[3]["metadata"], nested)

        numeric = Mock(side_effect=AssertionError("numeric extraction ran"))
        splitter = Mock(side_effect=AssertionError("split ran"))
        with (
            patch.object(financial_text_surface, "extract_numeric_surface_candidates", numeric),
            patch.object(financial_text_surface, "split_narrative_sentences", splitter),
        ):
            self.assertEqual(
                financial_text_surface.preserve_retrieved_narrative_source_surface("   ", evidence_items),
                "",
            )
            self.assertEqual(
                financial_text_surface.preserve_retrieved_narrative_source_surface("kept answer", []),
                "kept answer",
            )
        numeric.assert_not_called()
        splitter.assert_not_called()

        empty_split_events = []

        class EvidenceIterationBomb:
            def __iter__(self):
                raise AssertionError("evidence iterated")

            def __bool__(self):
                return True

        class MissingMarkerPolicyBomb(dict):
            def get(self, key, default=None):
                raise AssertionError(f"policy accessed: {key}")

        with (
            patch.object(
                financial_text_surface,
                "CALCULATION_NARRATIVE_POLICY",
                MissingMarkerPolicyBomb(),
            ),
            patch.object(
                financial_text_surface,
                "extract_numeric_surface_candidates",
                side_effect=lambda value: empty_split_events.append(("numeric", value)) or [],
            ),
            patch.object(
                financial_text_surface,
                "split_narrative_sentences",
                side_effect=lambda value: empty_split_events.append(("split", value)) or [],
            ),
        ):
            self.assertEqual(
                financial_text_surface.preserve_retrieved_narrative_source_surface(
                    "kept answer",
                    EvidenceIterationBomb(),
                ),
                "kept answer",
            )
        self.assertEqual(
            empty_split_events,
            [("numeric", "kept answer"), ("split", "kept answer")],
        )

        events = []
        candidates = [{"kind": "number", "text": "123"}]

        def split(value):
            events.append(("split", value))
            if value == "Numeric 123 stays.":
                return [value]
            return [value]

        def terms(value):
            events.append(("terms", value))
            if value == "Numeric 123 stays.":
                raise AssertionError("numeric sentence terms accessed")
            return ["Numeric", "stays"]

        def numeric_support(value, received_candidates):
            events.append(("numeric_support", value, received_candidates))
            return True

        numeric_evidence = [
            {
                "evidence_id": "retrieved_narrative::numeric",
                "claim": "Numeric stays.",
                "quote_span": "Numeric replacement.",
            }
        ]
        with (
            patch.object(
                financial_text_surface,
                "CALCULATION_NARRATIVE_POLICY",
                {"missing_answer_markers": ()},
            ),
            patch.object(
                financial_text_surface,
                "extract_numeric_surface_candidates",
                side_effect=lambda value: events.append(("numeric", value)) or candidates,
            ),
            patch.object(financial_text_surface, "split_narrative_sentences", side_effect=split),
            patch.object(financial_text_surface, "narrative_context_terms", side_effect=terms),
            patch.object(
                financial_text_surface,
                "text_supports_numeric_candidates",
                side_effect=numeric_support,
            ),
        ):
            self.assertEqual(
                financial_text_surface.preserve_retrieved_narrative_source_surface(
                    "Numeric 123 stays.",
                    numeric_evidence,
                ),
                "Numeric 123 stays.",
            )
        self.assertEqual(events[0], ("numeric", "Numeric 123 stays."))
        self.assertEqual(events[1], ("split", "Numeric 123 stays."))
        self.assertIn(("numeric_support", "Numeric 123 stays.", candidates), events)
        self.assertNotIn(("terms", "Numeric 123 stays."), events)

        class ValueBomb:
            def __str__(self):
                raise AssertionError("skipped value stringified")

        skipped = [
            {
                "evidence_id": "not-retrieved",
                "claim": ValueBomb(),
                "quote_span": ValueBomb(),
            }
        ]
        terms = Mock(side_effect=AssertionError("terms accessed"))
        with (
            patch.object(
                financial_text_surface,
                "CALCULATION_NARRATIVE_POLICY",
                {"missing_answer_markers": ()},
            ),
            patch.object(financial_text_surface, "narrative_context_terms", terms),
        ):
            self.assertEqual(
                financial_text_surface.preserve_retrieved_narrative_source_surface("Plain answer.", skipped),
                "Plain answer.",
            )
        terms.assert_not_called()

        with patch.object(
            financial_text_surface,
            "extract_numeric_surface_candidates",
            side_effect=RuntimeError("numeric failed"),
        ):
            with self.assertRaisesRegex(RuntimeError, "numeric failed"):
                financial_text_surface.preserve_retrieved_narrative_source_surface("answer", [{}])

        with (
            patch.object(financial_text_surface, "extract_numeric_surface_candidates", return_value=[]),
            patch.object(
                financial_text_surface,
                "split_narrative_sentences",
                side_effect=RuntimeError("split failed"),
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "split failed"):
                financial_text_surface.preserve_retrieved_narrative_source_surface("answer", [{}])

        class CopyFailure:
            def __iter__(self):
                raise RuntimeError("copy failed")

        with (
            patch.object(financial_text_surface, "extract_numeric_surface_candidates", return_value=[]),
            patch.object(financial_text_surface, "split_narrative_sentences", return_value=["answer"]),
        ):
            with self.assertRaisesRegex(RuntimeError, "copy failed"):
                financial_text_surface.preserve_retrieved_narrative_source_surface(
                    "answer",
                    [CopyFailure()],
                )

        term_failure_evidence = [
            {
                "evidence_id": "retrieved_narrative::1",
                "claim": "claim alpha beta",
                "quote_span": "quote alpha beta",
            }
        ]
        with (
            patch.object(
                financial_text_surface,
                "CALCULATION_NARRATIVE_POLICY",
                {"missing_answer_markers": ()},
            ),
            patch.object(financial_text_surface, "extract_numeric_surface_candidates", return_value=[]),
            patch.object(financial_text_surface, "split_narrative_sentences", return_value=["answer"]),
            patch.object(
                financial_text_surface,
                "narrative_context_terms",
                side_effect=RuntimeError("terms failed"),
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "terms failed"):
                financial_text_surface.preserve_retrieved_narrative_source_surface(
                    "answer",
                    term_failure_evidence,
                )




    def test_topic_particle_uses_final_consonant_policy(self) -> None:
        self.assertEqual(topic_particle("자본"), "은")
        self.assertEqual(topic_particle("부채"), "는")
        self.assertEqual(topic_particle("ROE"), "는")

    def test_polish_korean_particle_pairs_rewrites_conjunctive_particle(self) -> None:
        self.assertEqual(polish_korean_particle_pairs("자본와 부채"), "자본과 부채")
        self.assertEqual(polish_korean_particle_pairs("부채와 자본"), "부채와 자본")

    def test_split_narrative_sentences_preserves_sentence_units(self) -> None:
        self.assertEqual(
            split_narrative_sentences("첫 문장입니다.둘째 문장입니다.\n셋째 문장입니다."),
            ["첫 문장입니다.", "둘째 문장입니다.", "셋째 문장입니다."],
        )

    def test_narrative_sentence_noise_detection_flags_table_like_rows(self) -> None:
        self.assertTrue(narrative_sentence_looks_table_noisy("a | b | c | d"))
        self.assertTrue(narrative_sentence_looks_table_noisy(""))
        self.assertFalse(narrative_sentence_looks_table_noisy("핵심 변동 요인을 설명합니다."))

    def test_abbreviated_fragment_detection_respects_markers(self) -> None:
        self.assertTrue(narrative_sentence_looks_abbreviated_fragment("reported by Corp.", ()))
        self.assertFalse(narrative_sentence_looks_abbreviated_fragment("reported by Corp.", ("reported",)))

    def test_current_source_query_focus_groups_pin_policy_filters_order_and_exceptions(self) -> None:
        policy = {
            "strip_chars": "()[]{}'\"",
            "leading_connector_pattern": r"^and\s+",
            "trailing_connector_pattern": r"\s+and$",
            "trailing_particle_pattern": r"-suffix$",
            "year_pattern": r"20\d{2}",
            "single_letter_pattern": r"[A-Za-z]",
            "parenthetical_pair_pattern": r"([A-Za-z][A-Za-z ]{1,20})\(([A-Za-z0-9 ]{2,20})\)",
            "left_context_drop_patterns": (r"^.*(?:and)\s+",),
            "quoted_pattern": r'"(.+?)"',
            "acronym_pattern": r"\b[A-Z][A-Z0-9]{1,8}\b",
            "english_token_pattern": r"[A-Za-z][A-Za-z0-9-]{2,}",
            "generic_token_pattern": r"[A-Za-z0-9]+",
            "label_template": "focus-{index}",
            "nested": {"preserve": True},
        }
        original_policy = deepcopy(policy)
        query = 'Prefix and Alpha(ALPHA) "Quoted" BETA stop 2024 77 A AB final-suffix'

        with (
            patch.object(financial_text_surface, "QUERY_FOCUS_MARKER_POLICY", policy),
            patch.object(financial_text_surface, "QUERY_FOCUS_STOPWORDS", frozenset({"stop"})),
        ):
            groups = financial_text_surface.query_focus_marker_groups(query, limit=20)
            limited = financial_text_surface.query_focus_marker_groups(query, limit=3)

        self.assertEqual(
            groups,
            [
                {"label": "focus-1", "variants": ["Alpha"], "phrase": "", "query_focus": True},
                {"label": "focus-2", "variants": ["Quoted"], "phrase": "", "query_focus": True},
                {"label": "focus-3", "variants": ["BETA"], "phrase": "", "query_focus": True},
                {"label": "focus-4", "variants": ["AB"], "phrase": "", "query_focus": True},
                {"label": "focus-5", "variants": ["Prefix"], "phrase": "", "query_focus": True},
                {"label": "focus-6", "variants": ["and"], "phrase": "", "query_focus": True},
                {"label": "focus-7", "variants": ["final"], "phrase": "", "query_focus": True},
                {"label": "focus-8", "variants": ["suffix"], "phrase": "", "query_focus": True},
            ],
        )
        self.assertEqual(limited, groups[:3])
        self.assertEqual(policy, original_policy)

        events = []

        class FalsyQuery:
            def __bool__(self):
                events.append("query:bool")
                return False

            def __str__(self):
                raise AssertionError("falsy query string accessed")

        class PolicyBomb:
            def keys(self):
                raise AssertionError("policy accessed")

        class StopwordBomb:
            def __contains__(self, _item):
                raise AssertionError("stopwords accessed")

        with (
            patch.object(financial_text_surface, "QUERY_FOCUS_MARKER_POLICY", PolicyBomb()),
            patch.object(financial_text_surface, "QUERY_FOCUS_STOPWORDS", StopwordBomb()),
            patch.object(
                financial_text_surface,
                "_normalise_spaces",
                side_effect=lambda value: events.append(("normalize", value)) or "",
            ),
        ):
            self.assertEqual(financial_text_surface.query_focus_marker_groups(FalsyQuery()), [])
        self.assertEqual(events, ["query:bool", ("normalize", "")])

        with patch.object(
            financial_text_surface,
            "_normalise_spaces",
            side_effect=RuntimeError("normalize failed"),
        ):
            with self.assertRaisesRegex(RuntimeError, "normalize failed"):
                financial_text_surface.query_focus_marker_groups("query")

        with (
            patch.object(financial_text_surface, "QUERY_FOCUS_MARKER_POLICY", PolicyBomb()),
            patch.object(financial_text_surface, "_normalise_spaces", return_value="query"),
        ):
            with self.assertRaisesRegex(AssertionError, "policy accessed"):
                financial_text_surface.query_focus_marker_groups("query")

        later_findall = Mock(side_effect=AssertionError("later regex accessed"))
        with (
            patch.object(financial_text_surface, "QUERY_FOCUS_MARKER_POLICY", policy),
            patch.object(financial_text_surface.re, "finditer", side_effect=RuntimeError("regex failed")),
            patch.object(financial_text_surface.re, "findall", later_findall),
        ):
            with self.assertRaisesRegex(RuntimeError, "regex failed"):
                financial_text_surface.query_focus_marker_groups("Token")
        later_findall.assert_not_called()

    def test_current_source_query_focus_markers_pin_flattening_identity_and_exception_stop(self) -> None:
        groups = [
            {"variants": [" Alpha ", "", "alpha", 7], "nested": {"preserve": True}},
            {"variants": ["BETA", "beta", "Gamma"]},
            {"missing": True},
        ]
        original_groups = deepcopy(groups)
        group_owner = Mock(return_value=groups)

        query = object()
        with patch.object(financial_text_surface, "query_focus_marker_groups", group_owner):
            self.assertEqual(
                financial_text_surface.query_focus_markers(query, limit=3),
                ["Alpha", "7", "BETA", "Gamma"],
            )
        group_owner.assert_called_once_with(query, limit=3)
        self.assertIs(group_owner.call_args.args[0], query)
        self.assertEqual(groups, original_groups)

        class StringBomb:
            def __str__(self):
                raise RuntimeError("variant failed")

        class LaterGroup(dict):
            def get(self, key, default=None):
                raise AssertionError("later group accessed")

        group_owner = Mock(
            return_value=[{"variants": [StringBomb()]}, LaterGroup(variants=["later"])]
        )
        with patch.object(financial_text_surface, "query_focus_marker_groups", group_owner):
            with self.assertRaisesRegex(RuntimeError, "variant failed"):
                financial_text_surface.query_focus_markers("query", limit=4)
        group_owner.assert_called_once_with("query", limit=4)

        owner_failure = RuntimeError("group owner failed")
        group_owner = Mock(side_effect=owner_failure)
        with patch.object(financial_text_surface, "query_focus_marker_groups", group_owner):
            with self.assertRaisesRegex(RuntimeError, "group owner failed"):
                financial_text_surface.query_focus_markers("query")


    def test_current_source_rerank_caller_pins_focus_gate_args_adoption_and_exception_stop(self) -> None:
        from src.agent import financial_retrieval_pipeline

        class Doc:
            def __init__(self, text, metadata):
                self.page_content = text
                self.metadata = metadata

        focus_doc = Doc("Focus content", {"block_type": "paragraph"})
        other_doc = Doc("Other content", {"block_type": "paragraph"})
        docs = [(focus_doc, 1.0), (other_doc, 1.0)]
        original_docs = list(docs)
        state = {
            "query": "Focus query",
            "topic": "",
            "active_subtask": {"operation_family": "narrative_summary"},
            "companies": [],
            "years": [],
            "section_filter": "",
            "intent": "qa",
            "query_type": "qa",
            "format_preference": "",
            "report_scope": {},
        }
        original_state = deepcopy(state)
        agent = financial_retrieval_pipeline.FinancialRetrievalPipelineMixin()
        agent._section_bias = Mock(return_value=0.0)
        marker_owner = Mock(return_value=["Focus"])

        patches = (
            patch.object(financial_retrieval_pipeline, "tokenize_terms", return_value=set()),
            patch.object(financial_retrieval_pipeline, "_metric_terms_from_topic", return_value=set()),
            patch.object(financial_retrieval_pipeline, "_active_preferred_sections", return_value=[]),
            patch.object(financial_retrieval_pipeline, "_active_preferred_statement_types", return_value=[]),
            patch.object(financial_retrieval_pipeline, "desired_consolidation_scope", return_value="unknown"),
            patch.object(financial_retrieval_pipeline, "metadata_period_match_strength", return_value=0),
            patch.object(financial_retrieval_pipeline, "NARRATIVE_RERANK_POLICY", {"causal_markers": ()}),
        )
        with (
            patches[0],
            patches[1],
            patches[2],
            patches[3],
            patches[4],
            patches[5],
            patches[6],
            patch.object(financial_retrieval_pipeline, "query_focus_markers", marker_owner),
        ):
            reranked = agent._rerank_docs(docs, state)

        marker_owner.assert_called_once_with("Focus query")
        self.assertEqual([item[0] for item in reranked], [focus_doc, other_doc])
        self.assertAlmostEqual(reranked[0][1], 1.2)
        self.assertAlmostEqual(reranked[1][1], 1.12)
        self.assertIs(reranked[0][0], focus_doc)
        self.assertEqual(docs, original_docs)
        self.assertEqual(state, original_state)

        marker_owner = Mock(side_effect=AssertionError("marker accessed"))
        non_narrative_state = deepcopy(state)
        non_narrative_state["semantic_plan"] = {"program_required": True}
        with (
            patches[0],
            patches[1],
            patches[2],
            patches[3],
            patches[4],
            patches[5],
            patches[6],
            patch.object(financial_retrieval_pipeline, "query_focus_markers", marker_owner),
        ):
            self.assertEqual(agent._rerank_docs([], non_narrative_state), [])
        marker_owner.assert_not_called()

        class DocBomb:
            @property
            def metadata(self):
                raise AssertionError("document accessed")

        marker_owner = Mock(side_effect=RuntimeError("marker failed"))
        with (
            patches[0],
            patches[1],
            patches[2],
            patches[3],
            patches[4],
            patches[5],
            patches[6],
            patch.object(financial_retrieval_pipeline, "query_focus_markers", marker_owner),
        ):
            with self.assertRaisesRegex(RuntimeError, "marker failed"):
                agent._rerank_docs([(DocBomb(), 1.0)], state)

    def test_current_source_evidence_driver_caller_pins_merge_order_copy_and_exception_stop(self) -> None:
        from src.agent import financial_graph_evidence

        policy = {"name": "policy", "nested": {"preserve": True}}
        base_group = {"label": "base", "variants": ["Existing", "Shared"]}
        focus_groups = [
            {
                "label": "focus-1",
                "variants": ["shared", "Fresh", "fresh"],
                "phrase": "",
                "query_focus": True,
                "nested": {"preserve": True},
            },
            {"label": "empty", "variants": ["EXISTING", ""]},
            {"label": "focus-2", "variants": ["FRESH", "Later"]},
        ]
        original_focus_groups = deepcopy(focus_groups)
        events = []
        agent = financial_graph_evidence.FinancialAgentEvidenceMixin()
        agent._active_narrative_policies_for_query = Mock(
            side_effect=lambda query: events.append(("active", query)) or [policy]
        )
        focus_owner = Mock(
            side_effect=lambda query: events.append(("focus", query)) or focus_groups
        )

        def driver_groups(policies):
            events.append(("driver", policies))
            self.assertIs(policies[0], policy)
            return [base_group]

        with (
            patch.object(
                financial_graph_evidence,
                "narrative_policy_driver_groups",
                side_effect=driver_groups,
            ),
            patch.object(financial_graph_evidence, "query_focus_marker_groups", focus_owner),
        ):
            result = agent._narrative_driver_groups("query")

        self.assertEqual(
            events,
            [("active", "query"), ("driver", [policy]), ("focus", "query")],
        )
        self.assertEqual(
            result,
            [
                base_group,
                {**focus_groups[0], "variants": ["Fresh", "fresh"]},
                {**focus_groups[2], "variants": ["Later"]},
            ],
        )
        self.assertIs(result[0], base_group)
        self.assertIsNot(result[1], focus_groups[0])
        self.assertIs(result[1]["nested"], focus_groups[0]["nested"])
        self.assertEqual(focus_groups, original_focus_groups)
        focus_owner.assert_called_once_with("query")

        failing_agent = financial_graph_evidence.FinancialAgentEvidenceMixin()
        failing_agent._active_narrative_policies_for_query = Mock(return_value=[policy])
        failing_focus_owner = Mock(side_effect=RuntimeError("focus failed"))
        with (
            patch.object(
                financial_graph_evidence,
                "narrative_policy_driver_groups",
                return_value=[base_group],
            ) as driver_owner,
            patch.object(
                financial_graph_evidence,
                "query_focus_marker_groups",
                failing_focus_owner,
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "focus failed"):
                failing_agent._narrative_driver_groups("query")
        driver_owner.assert_called_once_with([policy])

    def test_current_source_source_visible_terms_pin_early_gates_marker_filters_and_exceptions(self) -> None:
        class FalsyAnswer:
            def __bool__(self):
                return False

            def __str__(self):
                raise AssertionError("falsy answer string accessed")

        class EvidenceBomb:
            def __bool__(self):
                raise AssertionError("evidence accessed")

        marker_owner = Mock(side_effect=AssertionError("markers accessed"))
        ontology_owner = Mock(side_effect=AssertionError("ontology accessed"))
        with (
            patch.object(financial_text_surface, "query_focus_marker_groups", marker_owner),
            patch.object(financial_text_surface, "get_financial_ontology", ontology_owner),
        ):
            self.assertEqual(
                financial_text_surface.preserve_source_visible_query_terms(
                    FalsyAnswer(),
                    query="query",
                    ordered_results=[],
                    evidence_items=EvidenceBomb(),
                    docs=[],
                ),
                "",
            )
        marker_owner.assert_not_called()
        ontology_owner.assert_not_called()

        invalid_groups = [
            {
                "variants": [
                    "",
                    "lowercase",
                    "A" * 33,
                    "1234",
                    None,
                ]
            }
        ]
        marker_owner = Mock(return_value=invalid_groups)
        policy_bomb = Mock(side_effect=AssertionError("template policy accessed"))
        with (
            patch.object(financial_text_surface, "query_focus_marker_groups", marker_owner),
            patch.object(financial_text_surface, "get_financial_ontology", ontology_owner),
            patch.object(
                financial_text_surface,
                "CALCULATION_NARRATIVE_POLICY",
                {"source_visible_term_note_template": policy_bomb},
            ),
        ):
            self.assertEqual(
                financial_text_surface.preserve_source_visible_query_terms(
                    "  base answer  ",
                    query="query",
                    ordered_results=[],
                    evidence_items=EvidenceBomb(),
                    docs=[],
                ),
                "base answer",
            )
        marker_owner.assert_called_once_with("query")
        ontology_owner.assert_not_called()
        policy_bomb.assert_not_called()

        marker_failure = RuntimeError("marker owner failed")
        with patch.object(
            financial_text_surface,
            "query_focus_marker_groups",
            side_effect=marker_failure,
        ):
            with self.assertRaisesRegex(RuntimeError, "marker owner failed"):
                financial_text_surface.preserve_source_visible_query_terms(
                    "answer",
                    query="query",
                    ordered_results=[],
                    evidence_items=EvidenceBomb(),
                    docs=[],
                )

        class GroupBomb(dict):
            def get(self, key, default=None):
                raise RuntimeError("group access failed")

        with patch.object(
            financial_text_surface,
            "query_focus_marker_groups",
            return_value=[GroupBomb()],
        ):
            with self.assertRaisesRegex(RuntimeError, "group access failed"):
                financial_text_surface.preserve_source_visible_query_terms(
                    "answer",
                    query="query",
                    ordered_results=[],
                    evidence_items=[],
                    docs=[],
                )

    def test_current_source_source_visible_terms_pin_support_copy_order_limit_and_no_mutation(self) -> None:
        nested = {"preserve": True}
        evidence_item = {
            "claim": "ABC support",
            "quote_span": "",
            "raw_row_text": "",
            "allowed_terms": ["TUV"],
            "metadata": {
                "table_context": "",
                "table_header_context": "",
                "table_summary_text": "",
                "text": "",
                "nested": nested,
            },
            "nested": nested,
        }
        row = {
            "answer": "XYZ support",
            "metric_label": "",
            "calculation_result": {
                "formatted_result": "",
                "rendered_value": "",
                "nested": nested,
            },
            "nested": nested,
        }

        class Doc:
            def __init__(self):
                self.page_content = "QRS support"
                self.metadata = {
                    "table_context": "",
                    "table_header_context": "",
                    "table_summary_text": "",
                    "section_path": "",
                    "local_heading": "",
                    "nested": nested,
                }

        doc = Doc()
        evidence_items = [evidence_item]
        ordered_results = [row]
        docs = [(doc, 0.8)]
        snapshots = {
            "evidence": deepcopy(evidence_items),
            "rows": deepcopy(ordered_results),
            "doc_metadata": deepcopy(doc.metadata),
            "docs": list(docs),
        }
        identities = {
            "evidence": [id(item) for item in evidence_items],
            "rows": [id(item) for item in ordered_results],
            "docs": [id(item[0]) for item in docs],
        }
        marker_groups = [
            {"variants": ["ABC", "abc", "XYZ"]},
            {"variants": ["QRS", "TUV", "UVW", "FIFTH", "SIXTH", "ABC"]},
        ]
        ontology = Mock()
        ontology.match_concepts.return_value = []
        policy = {
            "source_visible_term_note_template": "Note: {terms}",
            "nested": nested,
        }
        original_policy = deepcopy(policy)
        with (
            patch.object(
                financial_text_surface,
                "query_focus_marker_groups",
                return_value=marker_groups,
            ) as marker_owner,
            patch.object(financial_text_surface, "get_financial_ontology", return_value=ontology),
            patch.object(financial_text_surface, "CALCULATION_NARRATIVE_POLICY", policy),
        ):
            answer = financial_text_surface.preserve_source_visible_query_terms(
                "Base UVW",
                query="query",
                ordered_results=ordered_results,
                evidence_items=evidence_items,
                docs=docs,
            )

        self.assertEqual(answer, "Base UVW Note: ABC, XYZ, QRS, TUV")
        marker_owner.assert_called_once_with("query")
        ontology.match_concepts.assert_called_once_with("query")
        self.assertEqual(policy, original_policy)
        self.assertEqual(evidence_items, snapshots["evidence"])
        self.assertEqual(ordered_results, snapshots["rows"])
        self.assertEqual(doc.metadata, snapshots["doc_metadata"])
        self.assertEqual(docs, snapshots["docs"])
        self.assertEqual([id(item) for item in evidence_items], identities["evidence"])
        self.assertEqual([id(item) for item in ordered_results], identities["rows"])
        self.assertEqual([id(item[0]) for item in docs], identities["docs"])
        self.assertIs(evidence_item["nested"], nested)
        self.assertIs(row["nested"], nested)
        self.assertIs(doc.metadata["nested"], nested)

        class EvidenceCopyBomb:
            def __bool__(self):
                return True

            def __iter__(self):
                raise RuntimeError("evidence copy failed")

        class RowBomb:
            def get(self, _key, _default=None):
                raise AssertionError("row accessed")

        class DocBomb:
            @property
            def metadata(self):
                raise AssertionError("doc accessed")

        ontology_bomb = Mock(side_effect=AssertionError("ontology accessed"))
        with (
            patch.object(
                financial_text_surface,
                "query_focus_marker_groups",
                return_value=[{"variants": ["ABC"]}],
            ),
            patch.object(financial_text_surface, "get_financial_ontology", ontology_bomb),
        ):
            with self.assertRaisesRegex(RuntimeError, "evidence copy failed"):
                financial_text_surface.preserve_source_visible_query_terms(
                    "answer",
                    query="query",
                    ordered_results=[RowBomb()],
                    evidence_items=[EvidenceCopyBomb()],
                    docs=[DocBomb()],
                )
        ontology_bomb.assert_not_called()

    def test_current_source_source_visible_terms_pin_ontology_support_template_and_exception_stop(self) -> None:
        marker_groups = [{"variants": ["Program", "ABC"]}]
        concept = {
            "key": "program",
            "display_name": "Program",
            "aliases": ["ABC", "Program"],
            "keywords": [],
            "nested": {"preserve": True},
        }
        ontology = Mock()
        ontology.match_concepts.return_value = [
            {"key": "", "display_name": "ignored"},
            concept,
        ]
        policy = {"source_visible_term_note_template": "[{terms}]"}
        with (
            patch.object(
                financial_text_surface,
                "query_focus_marker_groups",
                return_value=marker_groups,
            ),
            patch.object(financial_text_surface, "get_financial_ontology", return_value=ontology),
            patch.object(financial_text_surface, "CALCULATION_NARRATIVE_POLICY", policy),
        ):
            self.assertEqual(
                financial_text_surface.preserve_source_visible_query_terms(
                    "Program result",
                    query="query",
                    ordered_results=[],
                    evidence_items=[],
                    docs=[],
                ),
                "Program result [ABC]",
            )
        ontology.match_concepts.assert_called_once_with("query")

        policy_bomb = Mock()
        policy_bomb.get.side_effect = RuntimeError("policy failed")
        ontology = Mock()
        ontology.match_concepts.return_value = []
        with (
            patch.object(
                financial_text_surface,
                "query_focus_marker_groups",
                return_value=[{"variants": ["ABC"]}],
            ),
            patch.object(financial_text_surface, "get_financial_ontology", return_value=ontology),
            patch.object(financial_text_surface, "CALCULATION_NARRATIVE_POLICY", policy_bomb),
        ):
            with self.assertRaisesRegex(RuntimeError, "policy failed"):
                financial_text_surface.preserve_source_visible_query_terms(
                    "answer",
                    query="query",
                    ordered_results=[],
                    evidence_items=[{"claim": "ABC support"}],
                    docs=[],
                )
        ontology.match_concepts.assert_called_once_with("query")

        ontology_failure = Mock(side_effect=RuntimeError("ontology failed"))
        with (
            patch.object(
                financial_text_surface,
                "query_focus_marker_groups",
                return_value=[{"variants": ["ABC"]}],
            ),
            patch.object(financial_text_surface, "get_financial_ontology", ontology_failure),
            patch.object(
                financial_text_surface,
                "CALCULATION_NARRATIVE_POLICY",
                Mock(get=Mock(side_effect=AssertionError("policy accessed"))),
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "ontology failed"):
                financial_text_surface.preserve_source_visible_query_terms(
                    "answer",
                    query="query",
                    ordered_results=[],
                    evidence_items=[{"claim": "ABC support"}],
                    docs=[],
                )




if __name__ == "__main__":
    unittest.main()
