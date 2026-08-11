import unittest
from copy import deepcopy
from unittest.mock import Mock, patch

from src.agent import financial_graph_calculation, financial_text_surface

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

    def test_current_source_text_term_variant_bindings_pin_exact_calls_post_move_distribution_and_baseline(self) -> None:
        import ast
        import inspect
        import json
        from collections import Counter
        from pathlib import Path

        module_trees = {
            "graph": ast.parse(inspect.getsource(financial_graph_calculation)),
            "owner": ast.parse(inspect.getsource(financial_text_surface)),
        }
        targets = {
            "terms": "narrative_context_terms",
            "focus": "narrative_focus_variants",
            "parenthetical": "parenthetical_focus_variants",
        }
        retired_private_targets = {f"_{name}" for name in targets.values()}
        definitions = {}
        calls = {key: [] for key in targets}
        all_definition_names = set()

        class BindingVisitor(ast.NodeVisitor):
            def __init__(self, module_name: str) -> None:
                self.module_name = module_name
                self.function_stack = []

            def visit_FunctionDef(self, node):
                all_definition_names.add(node.name)
                if node.name in targets.values():
                    definitions[node.name] = (self.module_name, node)
                self.function_stack.append(node.name)
                self.generic_visit(node)
                self.function_stack.pop()

            visit_AsyncFunctionDef = visit_FunctionDef

            def visit_Call(self, node):
                called_name = (
                    node.func.id
                    if isinstance(node.func, ast.Name)
                    else node.func.attr
                    if isinstance(node.func, ast.Attribute)
                    else ""
                )
                receiver = (
                    ast.unparse(node.func.value)
                    if isinstance(node.func, ast.Attribute)
                    else ""
                )
                for key, target in targets.items():
                    if called_name == target:
                        calls[key].append(
                            (
                                self.module_name,
                                self.function_stack[-1] if self.function_stack else "<module>",
                                receiver,
                                tuple(ast.unparse(argument) for argument in node.args),
                                tuple(
                                    (keyword.arg, ast.unparse(keyword.value))
                                    for keyword in node.keywords
                                ),
                            )
                        )
                self.generic_visit(node)

        for module_name, tree in module_trees.items():
            BindingVisitor(module_name).visit(tree)

        self.assertEqual(
            {
                name: (module_name, node.end_lineno - node.lineno + 1)
                for name, (module_name, node) in definitions.items()
            },
            {
                "narrative_context_terms": ("owner", 18),
                "narrative_focus_variants": ("owner", 30),
                "parenthetical_focus_variants": ("owner", 15),
            },
        )
        self.assertTrue(retired_private_targets.isdisjoint(all_definition_names))
        self.assertEqual(
            {key: len(entries) for key, entries in calls.items()},
            {"terms": 18, "focus": 2, "parenthetical": 3},
        )
        self.assertTrue(
            all(
                receiver == "" and not keywords
                for entries in calls.values()
                for _module, _caller, receiver, _args, keywords in entries
            )
        )
        self.assertEqual(
            Counter((caller, args) for _module, caller, _receiver, args, _keywords in calls["terms"]),
            Counter(
                {
                    ("_preferred_complete_numeric_answer", ("str(query or '')",)): 1,
                    ("_label_overlap_score", ("normalized_label",)): 1,
                    ("_strip_untraced_numeric_material_from_growth_narrative_sentence", ("sanitized",)): 1,
                    ("_content_terms", ("text",)): 2,
                    ("_dependency_source_text_match_score", ("left",)): 1,
                    ("_dependency_source_text_match_score", ("right",)): 1,
                    ("narrative_focus_variants", ("query",)): 1,
                    ("parenthetical_focus_variants", ("query",)): 1,
                    ("narrative_context_sentence_from_evidence", ("query",)): 1,
                    ("include_narrative_context_if_needed", ("query",)): 1,
                    ("_growth_narrative_sentence_candidates", ("query",)): 1,
                    ("_narrative_row_focus_context", ("query",)): 1,
                    ("_answer_satisfies_growth_narrative_intent", ("query_text",)): 1,
                    ("_token_overlap_supported", ("sentence",)): 1,
                    ("_token_overlap_supported", ("candidate",)): 1,
                    ("_build_period_comparison_operands_from_table_label_context", ("query",)): 1,
                    ("_label_terms", ("text",)): 1,
                }
            ),
        )
        self.assertEqual(
            Counter((caller, args) for _module, caller, _receiver, args, _keywords in calls["focus"]),
            Counter(
                {
                    ("_compose_growth_narrative_answer", ("query",)): 1,
                    ("_prune_irrelevant_growth_narrative_sentences", ("query",)): 1,
                }
            ),
        )
        self.assertEqual(
            Counter(
                (caller, args)
                for _module, caller, _receiver, args, _keywords in calls["parenthetical"]
            ),
            Counter(
                {
                    ("_compose_growth_narrative_answer", ("query",)): 2,
                    ("_answer_satisfies_growth_narrative_intent", ("query_text",)): 1,
                }
            ),
        )

        owner_local = [
            entry
            for entries in calls.values()
            for entry in entries
            if entry[0] == "owner"
        ]
        graph_external = [
            entry
            for entries in calls.values()
            for entry in entries
            if entry[0] == "graph"
        ]
        self.assertEqual((len(graph_external), len(owner_local)), (18, 5))
        self.assertEqual(
            [(caller, args) for _module, caller, _receiver, args, _keywords in owner_local],
            [
                ("narrative_focus_variants", ("query",)),
                ("parenthetical_focus_variants", ("query",)),
                ("narrative_context_sentence_from_evidence", ("query",)),
                ("include_narrative_context_if_needed", ("query",)),
                ("_content_terms", ("text",)),
            ],
        )

        graph_bindings = [
            (alias.name, alias.asname)
            for node in module_trees["graph"].body
            if isinstance(node, ast.ImportFrom)
            and node.module == "src.agent.financial_text_surface"
            for alias in node.names
            if alias.name in targets.values()
        ]
        self.assertEqual(
            graph_bindings,
            [
                ("narrative_context_terms", None),
                ("narrative_focus_variants", None),
                ("parenthetical_focus_variants", None),
            ],
        )

        baseline = json.loads(
            (Path(__file__).parent / "fixtures" / "runtime_domain_terms_baseline.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(len(baseline["records"]), 217)
        pattern = "[\uac00-\ud7a3A-Za-z0-9()]+"
        matching_records = [
            record
            for record in baseline["records"]
            if record.get("text") == pattern
        ]
        self.assertEqual(
            matching_records,
            [
                {
                    "path": "src/agent/financial_text_surface.py",
                    "text": pattern,
                    "category": "regex_or_pattern",
                    "fingerprint": "8de82bc58774a578",
                    "count": 1,
                    "first_lines": [37],
                }
            ],
        )

    def test_current_source_text_term_variant_callers_pin_args_adoption_laziness_and_exception_stop(self) -> None:
        agent = financial_graph_calculation.FinancialAgentCalculationMixin()

        terms = Mock(side_effect=[("Alpha", "Shared"), ("Shared", "Beta")])
        with patch.object(financial_graph_calculation, "narrative_context_terms", terms):
            self.assertEqual(
                agent._dependency_source_text_match_score("left label", "right label"),
                1,
            )
        self.assertEqual(
            [entry.args for entry in terms.call_args_list],
            [("left label",), ("right label",)],
        )

        terms = Mock()
        with (
            patch.object(
                financial_graph_calculation,
                "_normalise_spaces",
                side_effect=("", "right label"),
            ) as normalizer,
            patch.object(financial_graph_calculation, "narrative_context_terms", terms),
        ):
            self.assertEqual(
                agent._dependency_source_text_match_score("left label", "right label"),
                0,
            )
        self.assertEqual(
            [entry.args for entry in normalizer.call_args_list],
            [("left label",), ("right label",)],
        )
        terms.assert_not_called()

        terms = Mock(side_effect=RuntimeError("term caller failed"))
        with patch.object(financial_graph_calculation, "narrative_context_terms", terms):
            with self.assertRaisesRegex(RuntimeError, "term caller failed"):
                agent._dependency_source_text_match_score("left label", "right label")
        terms.assert_called_once_with("left label")

        growth_row = {"kind": "growth", "nested": {"preserve": True}}
        narrative_row = {"kind": "narrative"}
        ordered_results = [growth_row, narrative_row]
        evidence_items = [{"evidence_id": "ev_1"}]
        original_results = deepcopy(ordered_results)
        original_evidence = deepcopy(evidence_items)
        prune_policy = {
            "growth_query_pattern": "query",
            "percent_display_pattern": r"\d+%",
            "growth_impact_markers": ("impact",),
            "growth_narrative_markers": (),
        }

        def operation_family(row):
            return "growth_rate" if row is growth_row else "narrative_summary"

        focus = Mock(return_value=["Focus"])
        with (
            patch.object(financial_graph_calculation, "CALCULATION_NARRATIVE_POLICY", prune_policy),
            patch.object(financial_graph_calculation, "_split_narrative_sentences", return_value=["Focus impact", "irrelevant"]),
            patch.object(financial_graph_calculation, "_query_requests_narrative_context", return_value=True),
            patch.object(financial_graph_calculation, "row_is_narrative_summary", side_effect=lambda row: row is narrative_row),
            patch.object(financial_graph_calculation, "growth_sentence_has_untraced_material_numeric", return_value=False),
            patch.object(agent, "_aggregate_result_operation_family", side_effect=operation_family),
            patch.object(agent, "_growth_required_display_values", return_value=[]),
            patch.object(agent, "_supported_growth_narrative_candidate_sentences", return_value=[]),
            patch.object(financial_graph_calculation, "narrative_focus_variants", focus),
            patch.object(agent, "_answer_satisfies_growth_narrative_intent", return_value=True) as validation,
            patch.object(agent, "_growth_answer_has_untraced_numeric_material", return_value=False) as numeric_guard,
        ):
            self.assertEqual(
                agent._prune_irrelevant_growth_narrative_sentences(
                    query="query",
                    answer="10% Focus impact. irrelevant.",
                    ordered_results=ordered_results,
                    evidence_items=evidence_items,
                ),
                "Focus impact",
            )
        focus.assert_called_once_with("query")
        validation.assert_called_once_with(
            query="query",
            answer="Focus impact",
            ordered_results=ordered_results,
            evidence_items=evidence_items,
        )
        numeric_guard.assert_called_once_with("Focus impact", ordered_results, evidence_items)
        self.assertEqual(ordered_results, original_results)
        self.assertEqual(evidence_items, original_evidence)

        focus = Mock()
        query_gate = Mock(side_effect=RuntimeError("query gate must remain lazy"))
        with (
            patch.object(financial_graph_calculation, "_split_narrative_sentences", return_value=["single"]),
            patch.object(financial_graph_calculation, "_query_requests_narrative_context", query_gate),
            patch.object(financial_graph_calculation, "narrative_focus_variants", focus),
        ):
            self.assertEqual(
                agent._prune_irrelevant_growth_narrative_sentences(
                    query="query",
                    answer="single",
                    ordered_results=ordered_results,
                    evidence_items=evidence_items,
                ),
                "single",
            )
        query_gate.assert_not_called()
        focus.assert_not_called()

        focus = Mock(side_effect=RuntimeError("focus caller failed"))
        downstream_validation = Mock()
        downstream_numeric_guard = Mock()
        with (
            patch.object(financial_graph_calculation, "CALCULATION_NARRATIVE_POLICY", prune_policy),
            patch.object(financial_graph_calculation, "_split_narrative_sentences", return_value=["Focus impact", "irrelevant"]),
            patch.object(financial_graph_calculation, "_query_requests_narrative_context", return_value=True),
            patch.object(financial_graph_calculation, "row_is_narrative_summary", side_effect=lambda row: row is narrative_row),
            patch.object(financial_graph_calculation, "growth_sentence_has_untraced_material_numeric", return_value=False),
            patch.object(agent, "_aggregate_result_operation_family", side_effect=operation_family),
            patch.object(agent, "_growth_required_display_values", return_value=[]),
            patch.object(agent, "_supported_growth_narrative_candidate_sentences", return_value=[]),
            patch.object(financial_graph_calculation, "narrative_focus_variants", focus),
            patch.object(agent, "_answer_satisfies_growth_narrative_intent", downstream_validation),
            patch.object(agent, "_growth_answer_has_untraced_numeric_material", downstream_numeric_guard),
        ):
            with self.assertRaisesRegex(RuntimeError, "focus caller failed"):
                agent._prune_irrelevant_growth_narrative_sentences(
                    query="query",
                    answer="10% Focus impact. irrelevant.",
                    ordered_results=ordered_results,
                    evidence_items=evidence_items,
                )
        focus.assert_called_once_with("query")
        downstream_validation.assert_not_called()
        downstream_numeric_guard.assert_not_called()

        intent_policy = {
            "growth_query_pattern": "growth",
            "missing_answer_markers": (),
            "percent_display_pattern": r"\d+%",
            "growth_impact_markers": ("impact",),
            "growth_generic_focus_terms": (),
            "growth_metric_label_terms": (),
        }
        terms = Mock(return_value=["Fallback"])
        parenthetical = Mock(return_value=["Needle"])
        candidates = Mock(return_value=[])
        with (
            patch.object(financial_graph_calculation, "CALCULATION_NARRATIVE_POLICY", intent_policy),
            patch.object(financial_graph_calculation, "_query_requests_narrative_context", return_value=True),
            patch.object(financial_graph_calculation, "growth_row_has_conflicting_periods", return_value=False),
            patch.object(agent, "_aggregate_result_operation_family", side_effect=operation_family),
            patch.object(agent, "_growth_required_display_values", return_value=[]),
            patch.object(financial_graph_calculation, "narrative_context_terms", terms),
            patch.object(financial_graph_calculation, "parenthetical_focus_variants", parenthetical),
            patch.object(agent, "_growth_narrative_sentence_candidates", candidates),
            patch.object(agent, "_supported_growth_driver_groups", return_value=[]),
            patch.object(agent, "_narrative_row_focus_context", return_value=None),
        ):
            self.assertTrue(
                agent._answer_satisfies_growth_narrative_intent(
                    query="  growth   query ",
                    answer="10% impact Needle",
                    ordered_results=ordered_results,
                    evidence_items=evidence_items,
                )
            )
        terms.assert_called_once_with("growth query")
        parenthetical.assert_called_once_with("growth query")
        candidates.assert_called_once_with(
            query="growth query",
            ordered_results=ordered_results,
            evidence_items=evidence_items,
        )

        candidates = Mock(side_effect=RuntimeError("candidates must remain lazy"))
        with (
            patch.object(financial_graph_calculation, "CALCULATION_NARRATIVE_POLICY", intent_policy),
            patch.object(financial_graph_calculation, "_query_requests_narrative_context", return_value=True),
            patch.object(financial_graph_calculation, "growth_row_has_conflicting_periods", return_value=False),
            patch.object(agent, "_aggregate_result_operation_family", side_effect=operation_family),
            patch.object(agent, "_growth_required_display_values", return_value=[]),
            patch.object(financial_graph_calculation, "narrative_context_terms", return_value=["Fallback"]),
            patch.object(financial_graph_calculation, "parenthetical_focus_variants", return_value=["Missing"]),
            patch.object(agent, "_growth_narrative_sentence_candidates", candidates),
        ):
            self.assertFalse(
                agent._answer_satisfies_growth_narrative_intent(
                    query="growth query",
                    answer="10% impact Needle",
                    ordered_results=ordered_results,
                    evidence_items=evidence_items,
                )
            )
        candidates.assert_not_called()

        terms = Mock()
        parenthetical = Mock()
        with (
            patch.object(financial_graph_calculation, "_query_requests_narrative_context", return_value=False),
            patch.object(financial_graph_calculation, "narrative_context_terms", terms),
            patch.object(financial_graph_calculation, "parenthetical_focus_variants", parenthetical),
        ):
            self.assertFalse(
                agent._answer_satisfies_growth_narrative_intent(
                    query="growth query",
                    answer="10% impact Needle",
                    ordered_results=ordered_results,
                    evidence_items=evidence_items,
                )
            )
        terms.assert_not_called()
        parenthetical.assert_not_called()

        candidates = Mock()
        parenthetical = Mock(side_effect=RuntimeError("parenthetical caller failed"))
        with (
            patch.object(financial_graph_calculation, "CALCULATION_NARRATIVE_POLICY", intent_policy),
            patch.object(financial_graph_calculation, "_query_requests_narrative_context", return_value=True),
            patch.object(financial_graph_calculation, "growth_row_has_conflicting_periods", return_value=False),
            patch.object(agent, "_aggregate_result_operation_family", side_effect=operation_family),
            patch.object(agent, "_growth_required_display_values", return_value=[]),
            patch.object(financial_graph_calculation, "narrative_context_terms", return_value=["Fallback"]),
            patch.object(financial_graph_calculation, "parenthetical_focus_variants", parenthetical),
            patch.object(agent, "_growth_narrative_sentence_candidates", candidates),
        ):
            with self.assertRaisesRegex(RuntimeError, "parenthetical caller failed"):
                agent._answer_satisfies_growth_narrative_intent(
                    query="growth query",
                    answer="10% impact Needle",
                    ordered_results=ordered_results,
                    evidence_items=evidence_items,
                )
        parenthetical.assert_called_once_with("growth query")
        candidates.assert_not_called()
        self.assertEqual(ordered_results, original_results)
        self.assertEqual(evidence_items, original_evidence)

    def test_current_source_context_sentence_selector_pins_ranking_copy_laziness_and_exceptions(self) -> None:
        from collections.abc import Mapping

        selector = financial_text_surface.narrative_context_sentence_from_evidence

        class IterationBomb:
            def __iter__(self):
                raise RuntimeError("evidence iterated")

        terms = Mock()
        with (
            patch.object(financial_text_surface, "_query_requests_narrative_context", return_value=False) as query_gate,
            patch.object(financial_text_surface, "narrative_context_terms", terms),
        ):
            self.assertEqual(
                selector("query", IterationBomb()),
                "",
            )
        query_gate.assert_called_once_with("query")
        terms.assert_not_called()

        with (
            patch.object(financial_text_surface, "_query_requests_narrative_context", return_value=True),
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
            patch.object(financial_text_surface, "_query_requests_narrative_context", return_value=True),
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
            patch.object(financial_text_surface, "_query_requests_narrative_context", return_value=True),
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
            patch.object(financial_text_surface, "_query_requests_narrative_context", return_value=True),
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
            patch.object(financial_text_surface, "_query_requests_narrative_context", return_value=True),
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
            patch.object(financial_text_surface, "_query_requests_narrative_context", return_value=True),
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
            patch.object(financial_text_surface, "_query_requests_narrative_context", return_value=True),
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
            patch.object(financial_text_surface, "_query_requests_narrative_context", return_value=True),
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
            patch.object(financial_text_surface, "_query_requests_narrative_context", return_value=True),
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
                "_query_requests_narrative_context",
                side_effect=RuntimeError("query gate failed"),
            ),
            patch.object(financial_text_surface, "narrative_context_terms", downstream),
        ):
            with self.assertRaisesRegex(RuntimeError, "query gate failed"):
                selector("query", IterationBomb())
        downstream.assert_not_called()

        splitter = Mock()
        with (
            patch.object(financial_text_surface, "_query_requests_narrative_context", return_value=True),
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
            patch.object(financial_text_surface, "_query_requests_narrative_context", return_value=True),
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
            patch.object(financial_text_surface, "_query_requests_narrative_context", return_value=True),
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
            patch.object(financial_text_surface, "_query_requests_narrative_context", return_value=True),
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
            patch.object(financial_text_surface, "_query_requests_narrative_context", return_value=True),
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
            patch.object(financial_text_surface, "_query_requests_narrative_context", query_gate),
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
            patch.object(financial_text_surface, "_query_requests_narrative_context", query_gate),
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
            patch.object(financial_text_surface, "_query_requests_narrative_context", query_gate),
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
            patch.object(financial_text_surface, "_query_requests_narrative_context", return_value=True),
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
            patch.object(financial_text_surface, "_query_requests_narrative_context", return_value=True),
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
            patch.object(financial_text_surface, "_query_requests_narrative_context", return_value=True),
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
            patch.object(financial_text_surface, "_query_requests_narrative_context", return_value=True),
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
            patch.object(financial_text_surface, "_query_requests_narrative_context", return_value=True),
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
            patch.object(financial_text_surface, "_query_requests_narrative_context", return_value=True),
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
            patch.object(financial_text_surface, "_query_requests_narrative_context", query_gate),
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
            patch.object(financial_text_surface, "_query_requests_narrative_context", query_gate),
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
                "_query_requests_narrative_context",
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
            patch.object(financial_text_surface, "_query_requests_narrative_context", return_value=True),
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
            patch.object(financial_text_surface, "_query_requests_narrative_context", return_value=True),
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
            patch.object(financial_text_surface, "_query_requests_narrative_context", return_value=True),
            patch.object(financial_text_surface, "narrative_context_terms", return_value=[]),
        ):
            with self.assertRaisesRegex(RuntimeError, "prefix normalization failed"):
                include_context(
                    "answer",
                    query="query",
                    narrative_context="context",
                )
        self.assertEqual(normalize_calls, ["answer", "context", "context answer"])

    def test_current_source_context_surface_static_bindings_pin_defs_calls_and_final_distribution(self) -> None:
        import ast
        import inspect

        module_trees = {
            "graph": ast.parse(inspect.getsource(financial_graph_calculation)),
            "owner": ast.parse(inspect.getsource(financial_text_surface)),
        }
        seam_b_targets = {
            "selector": "narrative_context_sentence_from_evidence",
            "include": "include_narrative_context_if_needed",
        }
        retired_private_targets = {f"_{name}" for name in seam_b_targets.values()}
        combined_targets = {
            "terms": "narrative_context_terms",
            "focus": "narrative_focus_variants",
            "parenthetical": "parenthetical_focus_variants",
            **seam_b_targets,
        }
        definitions = {}
        calls = {key: [] for key in combined_targets}
        call_try_depths = {key: [] for key in combined_targets}
        all_definition_names = set()

        class BindingVisitor(ast.NodeVisitor):
            def __init__(self, module_name: str) -> None:
                self.module_name = module_name
                self.function_stack = []
                self.try_depth = 0

            def visit_FunctionDef(self, node):
                all_definition_names.add(node.name)
                if node.name in seam_b_targets.values():
                    definitions[node.name] = (self.module_name, node)
                self.function_stack.append(node.name)
                self.generic_visit(node)
                self.function_stack.pop()

            visit_AsyncFunctionDef = visit_FunctionDef

            def visit_Try(self, node):
                self.try_depth += 1
                self.generic_visit(node)
                self.try_depth -= 1

            visit_TryStar = visit_Try

            def visit_Call(self, node):
                called_name = (
                    node.func.id
                    if isinstance(node.func, ast.Name)
                    else node.func.attr
                    if isinstance(node.func, ast.Attribute)
                    else ""
                )
                receiver = (
                    ast.unparse(node.func.value)
                    if isinstance(node.func, ast.Attribute)
                    else ""
                )
                for key, target in combined_targets.items():
                    if called_name == target:
                        call_try_depths[key].append(self.try_depth)
                        calls[key].append(
                            (
                                self.module_name,
                                self.function_stack[-1] if self.function_stack else "<module>",
                                receiver,
                                tuple(ast.unparse(argument) for argument in node.args),
                                tuple(
                                    (keyword.arg, ast.unparse(keyword.value))
                                    for keyword in node.keywords
                                ),
                            )
                        )
                self.generic_visit(node)

        for module_name, tree in module_trees.items():
            BindingVisitor(module_name).visit(tree)

        self.assertEqual(
            {
                name: (module_name, node.end_lineno - node.lineno + 1)
                for name, (module_name, node) in definitions.items()
            },
            {
                "narrative_context_sentence_from_evidence": ("owner", 57),
                "include_narrative_context_if_needed": ("owner", 25),
            },
        )
        self.assertTrue(retired_private_targets.isdisjoint(all_definition_names))
        self.assertEqual(
            {key: len(entries) for key, entries in calls.items()},
            {
                "terms": 18,
                "focus": 2,
                "parenthetical": 3,
                "selector": 1,
                "include": 1,
            },
        )
        self.assertEqual(
            calls["selector"],
            [
                (
                    "graph",
                    "_aggregate_calculation_subtasks",
                    "",
                    ("str(state.get('query') or '')", "aggregate_evidence_items"),
                    (),
                )
            ],
        )
        self.assertEqual(
            calls["include"],
            [
                (
                    "graph",
                    "_apply_initial_aggregate_answer_composition",
                    "",
                    ("final_answer",),
                    (
                        ("query", "str(state.get('query') or '')"),
                        ("narrative_context", "narrative_context"),
                    ),
                )
            ],
        )
        self.assertEqual(
            (call_try_depths["selector"], call_try_depths["include"]),
            ([0], [0]),
        )
        self.assertEqual(
            (
                sum(entry[0] == "graph" for entries in calls.values() for entry in entries),
                sum(entry[0] == "owner" for entries in calls.values() for entry in entries),
            ),
            (20, 5),
        )

        owner_local = [
            entry
            for entries in calls.values()
            for entry in entries
            if entry[0] == "owner"
        ]
        graph_external = [
            entry
            for entries in calls.values()
            for entry in entries
            if entry[0] == "graph"
        ]
        self.assertEqual((len(graph_external), len(owner_local)), (20, 5))
        self.assertEqual(
            [(caller, args) for _module, caller, _receiver, args, _keywords in owner_local],
            [
                ("narrative_focus_variants", ("query",)),
                ("parenthetical_focus_variants", ("query",)),
                ("narrative_context_sentence_from_evidence", ("query",)),
                ("include_narrative_context_if_needed", ("query",)),
                ("_content_terms", ("text",)),
            ],
        )

        graph_public_bindings = [
            (alias.name, alias.asname)
            for node in module_trees["graph"].body
            if isinstance(node, ast.ImportFrom)
            and node.module == "src.agent.financial_text_surface"
            for alias in node.names
            if alias.name
            in {
                "narrative_context_sentence_from_evidence",
                "include_narrative_context_if_needed",
            }
        ]
        self.assertEqual(
            graph_public_bindings,
            [
                ("include_narrative_context_if_needed", None),
                ("narrative_context_sentence_from_evidence", None),
            ],
        )

    def test_current_source_aggregate_caller_pins_context_selector_args_adoption_order_and_exception_stop(self) -> None:
        from types import SimpleNamespace

        agent = financial_graph_calculation.FinancialAgentCalculationMixin()
        state = {
            "query": "why context",
            "seed_retrieved_docs": ["seed"],
            "retrieved_docs": ["retrieved"],
            "plan_loop_count": 0,
        }
        original_state = deepcopy(state)
        ordered_results = [{"task_id": "task_1"}]
        aggregate_evidence_items = [{"evidence_id": "ev_1"}]
        preliminary_projection = {"calculation_result": {"status": "ok"}}
        prepared_state = SimpleNamespace(
            ordered_results=ordered_results,
            fallback_answer="fallback",
            supported_aggregate_answer="supported",
            complete_numeric_answer="numeric",
            has_narrative_summary=True,
            has_growth_rate_result=False,
            numeric_answer_locked=False,
        )
        evidence_state = SimpleNamespace(
            ordered_results=ordered_results,
            aggregate_evidence_items=aggregate_evidence_items,
            fallback_answer="fallback",
            final_answer="fallback",
            complete_numeric_answer="numeric",
            deterministic_feedback="",
        )
        period_state = SimpleNamespace(
            ordered_results=ordered_results,
            aggregate_projection=preliminary_projection,
            final_answer="fallback",
        )
        events = []

        prepare = Mock(side_effect=lambda actual: events.append(("prepare", actual)) or prepared_state)
        collect = Mock(side_effect=lambda actual, **kwargs: events.append(("collect", actual, kwargs)) or evidence_state)
        rebuild = Mock(side_effect=lambda rows, answer: events.append(("rebuild", rows, answer)) or preliminary_projection)
        runtime_context = Mock(side_effect=lambda actual: events.append(("runtime_context", actual)) or ["runtime"])
        period_items = Mock(
            side_effect=lambda evidence, runtime: events.append(("period_items", evidence, runtime)) or ["period"]
        )
        realign = Mock(side_effect=lambda **kwargs: events.append(("realign", kwargs)) or period_state)
        selector = Mock(
            side_effect=lambda query, evidence: events.append(("selector", query, evidence))
            or "selected narrative context"
        )
        composition = Mock(
            side_effect=lambda actual, **kwargs: events.append(("composition", actual, kwargs))
            or (_ for _ in ()).throw(RuntimeError("composition stop"))
        )

        with (
            patch.object(agent, "_prepare_initial_aggregate_state", prepare),
            patch.object(agent, "_infer_planner_feedback_from_answer_slots", return_value=""),
            patch.object(agent, "_collect_initial_aggregate_evidence_state", collect),
            patch.object(agent, "_rebuild_aggregate_projection", rebuild),
            patch.object(agent, "_runtime_evidence_rows_with_context_docs", runtime_context),
            patch.object(financial_graph_calculation, "_aggregate_period_context_evidence_items", period_items),
            patch.object(agent, "_apply_period_context_realignment_to_aggregate", realign),
            patch.object(financial_graph_calculation, "narrative_context_sentence_from_evidence", selector),
            patch.object(agent, "_apply_initial_aggregate_answer_composition", composition),
        ):
            with self.assertRaisesRegex(RuntimeError, "composition stop"):
                agent._aggregate_calculation_subtasks(state)

        selector.assert_called_once_with("why context", aggregate_evidence_items)
        self.assertIs(selector.call_args.args[1], aggregate_evidence_items)
        self.assertIs(composition.call_args.args[0], state)
        self.assertIs(composition.call_args.kwargs["ordered_results"], ordered_results)
        self.assertIs(
            composition.call_args.kwargs["aggregate_evidence_items"],
            aggregate_evidence_items,
        )
        self.assertEqual(
            composition.call_args.kwargs["narrative_context"],
            "selected narrative context",
        )
        self.assertEqual(
            [event[0] for event in events],
            [
                "prepare",
                "collect",
                "rebuild",
                "runtime_context",
                "period_items",
                "realign",
                "selector",
                "composition",
            ],
        )
        self.assertEqual(state, original_state)

        composition = Mock()
        selector = Mock(side_effect=RuntimeError("context selector failed"))
        with (
            patch.object(agent, "_prepare_initial_aggregate_state", return_value=prepared_state),
            patch.object(agent, "_infer_planner_feedback_from_answer_slots", return_value=""),
            patch.object(agent, "_collect_initial_aggregate_evidence_state", return_value=evidence_state),
            patch.object(agent, "_rebuild_aggregate_projection", return_value=preliminary_projection),
            patch.object(agent, "_runtime_evidence_rows_with_context_docs", return_value=["runtime"]),
            patch.object(financial_graph_calculation, "_aggregate_period_context_evidence_items", return_value=["period"]),
            patch.object(agent, "_apply_period_context_realignment_to_aggregate", return_value=period_state),
            patch.object(financial_graph_calculation, "narrative_context_sentence_from_evidence", selector),
            patch.object(agent, "_apply_initial_aggregate_answer_composition", composition),
        ):
            with self.assertRaisesRegex(RuntimeError, "context selector failed"):
                agent._aggregate_calculation_subtasks(state)
        selector.assert_called_once_with("why context", aggregate_evidence_items)
        composition.assert_not_called()
        self.assertEqual(state, original_state)

    def test_current_source_initial_composition_caller_pins_context_include_args_order_adoption_and_stop(self) -> None:
        from types import SimpleNamespace

        events = []
        include = Mock(
            side_effect=lambda answer, **kwargs: events.append(("include", answer, kwargs))
            or "included context answer"
        )

        def composer(name, result=None):
            return Mock(
                side_effect=lambda *args, **kwargs: events.append((name, args, kwargs)) or result
            )

        growth = composer("growth")
        entity = composer("entity")
        business = composer("business")
        dividend = composer("dividend")
        quantitative = composer("quantitative")
        augment = Mock(
            side_effect=lambda answer, *args, **kwargs: events.append(
                ("augment", answer, args, kwargs)
            )
            or answer
        )
        satisfies = Mock(
            side_effect=lambda **kwargs: events.append(("satisfies", kwargs)) or True
        )
        agent = SimpleNamespace(
            _compose_growth_narrative_answer=growth,
            _compose_entity_table_summary_answer=entity,
            _compose_business_technology_focus_answer=business,
            _compose_dividend_policy_hybrid_answer=dividend,
            _compose_supported_quantitative_impact_answer=quantitative,
            _augment_narrative_answer_with_supported_drivers=augment,
            _answer_satisfies_growth_narrative_intent=satisfies,
        )
        state = {"query": "why context", "report_scope": {"scope": "all"}}
        ordered_results = [{"task_id": "task_1"}]
        preliminary_projection = {"calculation_result": {"status": "ok"}}
        aggregate_evidence_items = [{"evidence_id": "ev_1"}]
        narrative_doc = {"metadata": {"preserve": True}}
        narrative_docs = [narrative_doc]
        originals = (
            deepcopy(state),
            deepcopy(ordered_results),
            deepcopy(preliminary_projection),
            deepcopy(aggregate_evidence_items),
            deepcopy(narrative_docs),
        )

        coerce = Mock(
            side_effect=lambda answer, **kwargs: events.append(("coerce", answer, kwargs))
            or "coerced answer"
        )
        slot_compose = Mock(
            side_effect=lambda **kwargs: events.append(("slot", kwargs)) or ""
        )
        with (
            patch.object(
                financial_graph_calculation,
                "include_narrative_context_if_needed",
                include,
            ),
            patch.object(
                financial_graph_calculation.calculation_rendering,
                "coerce_sign_aware_subtraction_answer",
                coerce,
            ),
            patch.object(
                financial_graph_calculation.calculation_rendering,
                "compose_slot_based_difference_answer",
                slot_compose,
            ),
        ):
            composition_state, complete_numeric_answer = (
                financial_graph_calculation.FinancialAgentCalculationMixin._apply_initial_aggregate_answer_composition(
                    agent,
                    state,
                    ordered_results=ordered_results,
                    preliminary_projection=preliminary_projection,
                    aggregate_evidence_items=aggregate_evidence_items,
                    narrative_docs=narrative_docs,
                    narrative_context="selected narrative context",
                    final_answer="initial answer",
                    supported_aggregate_answer="",
                    complete_numeric_answer="numeric answer",
                    has_narrative_summary=False,
                    has_growth_rate_result=False,
                    numeric_answer_locked=False,
                    planner_feedback="planner",
                    deterministic_feedback="",
                )
            )

        include.assert_called_once_with(
            "coerced answer",
            query="why context",
            narrative_context="selected narrative context",
        )
        self.assertEqual(
            [event[0] for event in events],
            [
                "coerce",
                "slot",
                "include",
                "growth",
                "entity",
                "business",
                "dividend",
                "quantitative",
                "augment",
                "satisfies",
            ],
        )
        self.assertEqual(growth.call_args.kwargs["existing_answer"], "included context answer")
        self.assertEqual(business.call_args.kwargs["existing_answer"], "included context answer")
        self.assertEqual(composition_state.final_answer, "included context answer")
        self.assertEqual(complete_numeric_answer, "numeric answer")
        self.assertEqual(state, originals[0])
        self.assertEqual(ordered_results, originals[1])
        self.assertEqual(preliminary_projection, originals[2])
        self.assertEqual(aggregate_evidence_items, originals[3])
        self.assertEqual(narrative_docs, originals[4])
        self.assertIs(narrative_docs[0], narrative_doc)

        downstream_growth = Mock()
        downstream_entity = Mock()
        failing_include = Mock(side_effect=RuntimeError("context inclusion failed"))
        failing_agent = SimpleNamespace(
            _compose_growth_narrative_answer=downstream_growth,
            _compose_entity_table_summary_answer=downstream_entity,
        )
        coerce = Mock(return_value="coerced answer")
        slot_compose = Mock(return_value="")
        with (
            patch.object(
                financial_graph_calculation,
                "include_narrative_context_if_needed",
                failing_include,
            ),
            patch.object(
                financial_graph_calculation.calculation_rendering,
                "coerce_sign_aware_subtraction_answer",
                coerce,
            ),
            patch.object(
                financial_graph_calculation.calculation_rendering,
                "compose_slot_based_difference_answer",
                slot_compose,
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "context inclusion failed"):
                financial_graph_calculation.FinancialAgentCalculationMixin._apply_initial_aggregate_answer_composition(
                    failing_agent,
                    state,
                    ordered_results=ordered_results,
                    preliminary_projection=preliminary_projection,
                    aggregate_evidence_items=aggregate_evidence_items,
                    narrative_docs=narrative_docs,
                    narrative_context="selected narrative context",
                    final_answer="initial answer",
                    supported_aggregate_answer="",
                    complete_numeric_answer="numeric answer",
                    has_narrative_summary=False,
                    has_growth_rate_result=False,
                    numeric_answer_locked=False,
                    planner_feedback="planner",
                    deterministic_feedback="",
                )
        coerce.assert_called_once()
        slot_compose.assert_called_once()
        failing_include.assert_called_once_with(
            "coerced answer",
            query="why context",
            narrative_context="selected narrative context",
        )
        downstream_growth.assert_not_called()
        downstream_entity.assert_not_called()
        self.assertEqual(state, originals[0])
        self.assertEqual(narrative_docs, originals[4])
        self.assertIs(narrative_docs[0], narrative_doc)

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

    def test_current_source_narrative_preservation_bindings_pin_defs_calls_plan_and_dag(self) -> None:
        import ast
        import inspect
        from pathlib import Path

        from src.agent import financial_numeric_surface

        module_sources = {
            "graph": inspect.getsource(financial_graph_calculation),
            "owner": inspect.getsource(financial_text_surface),
            "numeric": inspect.getsource(financial_numeric_surface),
        }
        module_trees = {name: ast.parse(source) for name, source in module_sources.items()}
        selected_targets = {
            "snippet": "policy_required_realized_snippet_from_doc",
            "preserve": "preserve_retrieved_narrative_source_surface",
        }
        retired_targets = {f"_{target}" for target in selected_targets.values()}
        existing_public_targets = {
            "terms": "narrative_context_terms",
            "focus": "narrative_focus_variants",
            "parenthetical": "parenthetical_focus_variants",
            "selector": "narrative_context_sentence_from_evidence",
            "include": "include_narrative_context_if_needed",
        }
        definitions = {}
        calls = {key: [] for key in {**existing_public_targets, **selected_targets}}
        try_depths = {key: [] for key in selected_targets}
        all_definition_names = set()

        class BindingVisitor(ast.NodeVisitor):
            def __init__(self, module_name: str) -> None:
                self.module_name = module_name
                self.function_stack = []
                self.try_depth = 0

            def visit_FunctionDef(self, node):
                all_definition_names.add(node.name)
                if node.name in selected_targets.values():
                    definitions[node.name] = (self.module_name, node)
                self.function_stack.append(node.name)
                self.generic_visit(node)
                self.function_stack.pop()

            visit_AsyncFunctionDef = visit_FunctionDef

            def visit_Try(self, node):
                self.try_depth += 1
                self.generic_visit(node)
                self.try_depth -= 1

            visit_TryStar = visit_Try

            def visit_Call(self, node):
                called_name = (
                    node.func.id
                    if isinstance(node.func, ast.Name)
                    else node.func.attr
                    if isinstance(node.func, ast.Attribute)
                    else ""
                )
                receiver = (
                    ast.unparse(node.func.value)
                    if isinstance(node.func, ast.Attribute)
                    else ""
                )
                for key, target in {**existing_public_targets, **selected_targets}.items():
                    if called_name != target:
                        continue
                    calls[key].append(
                        (
                            self.module_name,
                            tuple(self.function_stack),
                            receiver,
                            tuple(ast.unparse(argument) for argument in node.args),
                            tuple(
                                (keyword.arg, ast.unparse(keyword.value))
                                for keyword in node.keywords
                            ),
                        )
                    )
                    if key in selected_targets:
                        try_depths[key].append(self.try_depth)
                self.generic_visit(node)

        for module_name in ("graph", "owner"):
            BindingVisitor(module_name).visit(module_trees[module_name])

        self.assertEqual(
            {
                name: (module_name, node.end_lineno - node.lineno + 1)
                for name, (module_name, node) in definitions.items()
            },
            {
                "policy_required_realized_snippet_from_doc": ("owner", 68),
                "preserve_retrieved_narrative_source_surface": ("owner", 71),
            },
        )
        self.assertTrue(retired_targets.isdisjoint(all_definition_names))
        self.assertEqual(
            calls["snippet"],
            [
                (
                    "graph",
                    ("_preserve_policy_required_realized_context",),
                    "",
                    (),
                    (("doc", "doc"), ("policy", "policy")),
                )
            ],
        )
        self.assertEqual(
            calls["preserve"],
            [
                (
                    "graph",
                    ("_apply_final_narrative_repair_pipeline",),
                    "",
                    ("final_answer", "aggregate_evidence_items"),
                    (),
                )
            ],
        )
        self.assertEqual(try_depths, {"snippet": [0], "preserve": [0]})
        self.assertEqual(
            {key: len(entries) for key, entries in calls.items()},
            {
                "terms": 18,
                "focus": 2,
                "parenthetical": 3,
                "selector": 1,
                "include": 1,
                "snippet": 1,
                "preserve": 1,
            },
        )

        final_by_target = {
            key: (
                sum(entry[0] == "graph" for entry in entries),
                sum(entry[0] == "owner" for entry in entries),
            )
            for key, entries in calls.items()
        }
        self.assertEqual(
            final_by_target,
            {
                "terms": (13, 5),
                "focus": (2, 0),
                "parenthetical": (3, 0),
                "selector": (1, 0),
                "include": (1, 0),
                "snippet": (1, 0),
                "preserve": (1, 0),
            },
        )
        self.assertEqual(
            (
                sum(graph_count for graph_count, _owner_count in final_by_target.values()),
                sum(owner_count for _graph_count, owner_count in final_by_target.values()),
            ),
            (22, 5),
        )
        self.assertEqual(len(selected_targets), 2)

        def imported_modules(tree):
            modules = set()
            for node in tree.body:
                if isinstance(node, ast.ImportFrom) and node.module:
                    modules.add(node.module)
                elif isinstance(node, ast.Import):
                    modules.update(alias.name for alias in node.names)
            return modules

        owner_imports = imported_modules(module_trees["owner"])
        numeric_imports = imported_modules(module_trees["numeric"])
        self.assertIn("src.agent.financial_numeric_surface", owner_imports)
        self.assertNotIn("src.agent.financial_text_surface", numeric_imports)
        self.assertTrue(
            numeric_imports.issubset(
                {
                    "__future__",
                    "re",
                    "typing",
                    "src.agent.financial_runtime_normalization",
                    "src.config.retrieval_policy",
                }
            )
        )
        selected_loaded_names = {
            key: {
                node.id
                for node in ast.walk(definitions[target][1])
                if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load)
            }
            for key, target in selected_targets.items()
        }
        self.assertTrue(
            {
                "narrative_policy_terms",
                "topic_particle",
                "split_narrative_sentences",
            }.issubset(selected_loaded_names["snippet"])
        )
        self.assertTrue(
            {
                "extract_numeric_surface_candidates",
                "text_supports_numeric_candidates",
                "narrative_context_terms",
                "split_narrative_sentences",
            }.issubset(selected_loaded_names["preserve"])
        )
        all_selected_loaded_names = set().union(*selected_loaded_names.values())
        final_owner_dependencies = {
            "src.agent.financial_numeric_surface": all_selected_loaded_names
            & {
                "extract_numeric_surface_candidates",
                "text_supports_numeric_candidates",
            },
            "src.config.retrieval_policy": all_selected_loaded_names
            & {"narrative_policy_terms"},
        }
        self.assertEqual(
            final_owner_dependencies,
            {
                "src.agent.financial_numeric_surface": {
                    "extract_numeric_surface_candidates",
                    "text_supports_numeric_candidates",
                },
                "src.config.retrieval_policy": {"narrative_policy_terms"},
            },
        )

        subtask_loop_tree = ast.parse(
            (Path(__file__).parent / "test_subtask_loop.py").read_text(encoding="utf-8")
        )
        preexisting_preserve_refs = [
            node
            for node in ast.walk(subtask_loop_tree)
            if isinstance(node, ast.Attribute)
            and node.attr in retired_targets
        ]
        self.assertEqual(preexisting_preserve_refs, [])

        graph_bindings = [
            (alias.name, alias.asname)
            for node in module_trees["graph"].body
            if isinstance(node, ast.ImportFrom)
            and node.module == "src.agent.financial_text_surface"
            for alias in node.names
            if alias.name in selected_targets.values()
        ]
        self.assertEqual(
            graph_bindings,
            [
                ("policy_required_realized_snippet_from_doc", None),
                ("preserve_retrieved_narrative_source_surface", None),
            ],
        )

    def test_current_source_policy_context_caller_pins_kwargs_scoring_adoption_and_exception_stop(self) -> None:
        policy = {
            "required_realized_terms": ("Required",),
            "focus_terms": ("Focus",),
            "realized_terms": ("Realized",),
            "nested": {"preserve": True},
        }
        original_policy = deepcopy(policy)

        class Doc:
            def __init__(self, page_content, metadata):
                self.page_content = page_content
                self.metadata = metadata

        base_doc = Doc("Required", {"name": "base"})
        high_doc = Doc(
            "Required Focus Realized",
            {"name": "high", "block_type": "table", "period_focus": "current"},
        )
        tied_high_doc = Doc(
            "Required Focus Realized",
            {"name": "tie", "block_type": "table", "period_focus": "current"},
        )
        narrative_docs = [(base_doc, 0.1), high_doc, (tied_high_doc, 0.9)]
        original_docs = list(narrative_docs)
        original_doc_metadata = [
            deepcopy((item[0] if isinstance(item, tuple) else item).metadata)
            for item in narrative_docs
        ]
        doc_identities = [id(item[0] if isinstance(item, tuple) else item) for item in narrative_docs]
        agent = financial_graph_calculation.FinancialAgentCalculationMixin()
        active_policies = Mock(return_value=[policy])
        agent._active_narrative_policies_for_query = active_policies
        snippet_owner = Mock(side_effect=["base snippet", "high snippet", "tied snippet"])

        def policy_terms(policies, key):
            self.assertEqual(policies, [policy])
            return list(policy.get(key) or ())

        with (
            patch.object(financial_graph_calculation, "_query_requests_narrative_context", return_value=True) as query_gate,
            patch.object(financial_graph_calculation, "narrative_policy_terms", side_effect=policy_terms),
            patch.object(
                financial_graph_calculation,
                "policy_required_realized_snippet_from_doc",
                snippet_owner,
            ),
        ):
            self.assertEqual(
                financial_graph_calculation.FinancialAgentCalculationMixin._preserve_policy_required_realized_context(
                    agent,
                    "base answer",
                    query="why narrative",
                    docs=narrative_docs,
                ),
                "base answer high snippet",
            )
        query_gate.assert_called_once_with("why narrative")
        active_policies.assert_called_once_with("why narrative")
        self.assertEqual(
            snippet_owner.call_args_list,
            [
                unittest.mock.call(doc=base_doc, policy=policy),
                unittest.mock.call(doc=high_doc, policy=policy),
                unittest.mock.call(doc=tied_high_doc, policy=policy),
            ],
        )
        for owner_call in snippet_owner.call_args_list:
            self.assertIs(owner_call.kwargs["policy"], policy)
        self.assertEqual(policy, original_policy)
        self.assertEqual(narrative_docs, original_docs)
        self.assertEqual(
            [(item[0] if isinstance(item, tuple) else item).metadata for item in narrative_docs],
            original_doc_metadata,
        )
        self.assertEqual(
            [id(item[0] if isinstance(item, tuple) else item) for item in narrative_docs],
            doc_identities,
        )

        gated_agent = financial_graph_calculation.FinancialAgentCalculationMixin()
        gated_agent._active_narrative_policies_for_query = Mock(
            side_effect=AssertionError("active policies accessed")
        )
        snippet_bomb = Mock(
            side_effect=AssertionError("snippet accessed")
        )
        terms = Mock(side_effect=AssertionError("policy terms accessed"))
        with (
            patch.object(financial_graph_calculation, "narrative_policy_terms", terms),
            patch.object(financial_graph_calculation, "_query_requests_narrative_context", return_value=True) as query_gate,
            patch.object(
                financial_graph_calculation,
                "policy_required_realized_snippet_from_doc",
                snippet_bomb,
            ),
        ):
            self.assertEqual(
                financial_graph_calculation.FinancialAgentCalculationMixin._preserve_policy_required_realized_context(
                    gated_agent,
                    "",
                    query="query",
                    docs=narrative_docs,
                ),
                "",
            )
            self.assertEqual(
                financial_graph_calculation.FinancialAgentCalculationMixin._preserve_policy_required_realized_context(
                    gated_agent,
                    "answer",
                    query="query",
                    docs=[],
                ),
                "answer",
            )
        query_gate.assert_not_called()
        terms.assert_not_called()
        snippet_bomb.assert_not_called()

        with (
            patch.object(
                financial_graph_calculation,
                "_query_requests_narrative_context",
                return_value=False,
            ) as query_gate,
            patch.object(
                financial_graph_calculation,
                "policy_required_realized_snippet_from_doc",
                snippet_bomb,
            ),
        ):
            self.assertEqual(
                financial_graph_calculation.FinancialAgentCalculationMixin._preserve_policy_required_realized_context(
                    gated_agent,
                    "answer",
                    query="query",
                    docs=narrative_docs,
                ),
                "answer",
            )
        query_gate.assert_called_once_with("query")
        snippet_bomb.assert_not_called()

        events = []

        class SecondDocBomb:
            @property
            def metadata(self):
                raise AssertionError("second doc scored")

            @property
            def page_content(self):
                raise AssertionError("second doc surface read")

        first_doc = Doc("Required Focus", {"name": "first"})
        failing_agent = financial_graph_calculation.FinancialAgentCalculationMixin()
        failing_agent._active_narrative_policies_for_query = Mock(return_value=[policy])

        def fail_snippet(*, doc, policy):
            events.append(("snippet", doc, policy))
            raise RuntimeError("snippet failed")

        failing_snippet = Mock(side_effect=fail_snippet)
        with (
            patch.object(financial_graph_calculation, "_query_requests_narrative_context", return_value=True),
            patch.object(financial_graph_calculation, "narrative_policy_terms", side_effect=policy_terms),
            patch.object(
                financial_graph_calculation,
                "policy_required_realized_snippet_from_doc",
                failing_snippet,
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "snippet failed"):
                financial_graph_calculation.FinancialAgentCalculationMixin._preserve_policy_required_realized_context(
                    failing_agent,
                    "base answer",
                    query="why narrative",
                    docs=[first_doc, SecondDocBomb()],
                )
        failing_snippet.assert_called_once_with(
            doc=first_doc,
            policy=policy,
        )
        self.assertIs(
            failing_snippet.call_args.kwargs["policy"],
            policy,
        )
        self.assertIs(events[0][2], policy)
        self.assertEqual(events, [("snippet", first_doc, policy)])

    def test_current_source_final_repair_caller_pins_preservation_order_adoption_and_exception_stop(self) -> None:
        ordered_row = {"task_id": "task_1", "nested": {"preserve": True}}
        ordered_results = [ordered_row]
        projection = {"calculation_operands": [], "nested": {"preserve": True}}
        selected_claim_ids = ["claim_1"]
        evidence_item = {"evidence_id": "ev_1", "nested": {"preserve": True}}
        evidence_items = [evidence_item]
        narrative_doc = Mock(metadata={"section": "narrative"}, page_content="source text")
        narrative_docs = [(narrative_doc, 0.8)]
        state = {"query": "why narrative", "nested": {"preserve": True}}
        mutable_state = financial_graph_calculation._AggregateMutableState(
            financial_graph_calculation._AggregateSynthesisState(
                ordered_results,
                projection,
                "initial answer",
                selected_claim_ids,
            ),
            evidence_items,
        )
        snapshots = {
            "ordered": deepcopy(ordered_results),
            "projection": deepcopy(projection),
            "claims": deepcopy(selected_claim_ids),
            "evidence": deepcopy(evidence_items),
            "state": deepcopy(state),
            "docs": list(narrative_docs),
        }
        identities = {
            "ordered": [id(item) for item in ordered_results],
            "evidence": [id(item) for item in evidence_items],
            "docs": [id(item[0]) for item in narrative_docs],
        }
        events = []

        class FakeAgent:
            pass

        agent = FakeAgent()
        agent._preserve_policy_required_realized_context = Mock(
            side_effect=lambda answer, **kwargs: events.append(
                ("realized_context", answer, kwargs)
            )
            or answer
        )

        def replace_answer(current_state, *, candidate_answer, **kwargs):
            events.append(("replace", candidate_answer, kwargs))
            return current_state.with_updates(final_answer=candidate_answer), True

        agent._replace_mutable_aggregate_answer = Mock(side_effect=replace_answer)
        agent._append_operand_evidence_for_final_answer = Mock(
            side_effect=lambda current, **kwargs: events.append(
                ("append_operand", current, kwargs)
            )
            or current
        )
        agent._append_retrieved_narrative_evidence_for_final_answer = Mock(
            side_effect=lambda current, **kwargs: events.append(
                ("append_retrieved", current, kwargs)
            )
            or (current, [])
        )
        agent._apply_period_context_realignment_to_aggregate = Mock(
            side_effect=lambda **kwargs: events.append(("realign", kwargs))
            or kwargs["aggregate_state"]
        )
        agent._enforce_source_stated_growth_answer_contract = Mock(
            side_effect=lambda answer, rows, **kwargs: events.append(
                ("contract", answer, rows, kwargs)
            )
            or "contracted answer"
        )
        preserve_owner = Mock(
            side_effect=lambda answer, current: events.append(("preserve", answer, current))
            or "source-surface answer"
        )
        gap = Mock(
            side_effect=lambda rows: events.append(("gap", rows)) or False
        )
        agent._unresolved_structured_numeric_gap = gap
        agent._answer_reuses_narrative_summary_text = Mock(
            side_effect=AssertionError("gap fallback accessed")
        )
        prune = Mock(
            side_effect=lambda answer, **kwargs: events.append(("prune", answer, kwargs))
            or answer
        )
        agent._prune_nonfocus_numeric_narrative_sentences = prune
        agent._answer_satisfies_growth_narrative_intent = Mock(
            side_effect=AssertionError("growth intent accessed")
        )
        agent._answer_matches_supported_aggregate_subtask = Mock(
            side_effect=AssertionError("aggregate support accessed")
        )
        agent._promote_and_align_aggregate_results = Mock(
            side_effect=AssertionError("promotion accessed")
        )

        with (
            patch.object(
                financial_graph_calculation,
                "preserve_retrieved_narrative_source_surface",
                preserve_owner,
            ),
            patch.object(
                financial_graph_calculation,
                "_polish_korean_particle_pairs",
                side_effect=lambda answer: events.append(("polish", answer)) or answer,
            ) as polish,
            patch.object(
                financial_graph_calculation,
                "query_requests_explanatory_context",
                side_effect=lambda query: events.append(("explanatory", query)) or False,
            ) as explanatory,
        ):
            updated = financial_graph_calculation.FinancialAgentCalculationMixin._apply_final_narrative_repair_pipeline(
                agent,
                state,
                mutable_state=mutable_state,
                narrative_docs=narrative_docs,
                has_narrative_summary=False,
                has_growth_rate_result=False,
                deterministic_feedback="",
            )

        preserve_owner.assert_called_once_with("contracted answer", evidence_items)
        self.assertIs(preserve_owner.call_args.args[1], evidence_items)
        contract_index = next(index for index, event in enumerate(events) if event[0] == "contract")
        preserve_index = next(index for index, event in enumerate(events) if event[0] == "preserve")
        source_replace_index = next(
            index
            for index, event in enumerate(events)
            if event == ("replace", "source-surface answer", {})
        )
        gap_index = next(index for index, event in enumerate(events) if event[0] == "gap")
        self.assertLess(contract_index, preserve_index)
        self.assertLess(preserve_index, source_replace_index)
        self.assertLess(source_replace_index, gap_index)
        self.assertIn(
            ("replace", "source-surface answer", {}),
            events,
        )
        prune.assert_called_once_with(
            "source-surface answer",
            query="why narrative",
            ordered_results=ordered_results,
            evidence_items=evidence_items,
        )
        polish.assert_called_once_with("source-surface answer")
        explanatory.assert_called_once_with("why narrative")
        self.assertEqual(updated.final_answer, "source-surface answer")
        self.assertIs(updated.evidence_items, evidence_items)
        self.assertEqual(ordered_results, snapshots["ordered"])
        self.assertEqual(projection, snapshots["projection"])
        self.assertEqual(selected_claim_ids, snapshots["claims"])
        self.assertEqual(evidence_items, snapshots["evidence"])
        self.assertEqual(state, snapshots["state"])
        self.assertEqual(narrative_docs, snapshots["docs"])
        self.assertEqual([id(item) for item in ordered_results], identities["ordered"])
        self.assertEqual([id(item) for item in evidence_items], identities["evidence"])
        self.assertEqual([id(item[0]) for item in narrative_docs], identities["docs"])

        failing_events = []
        failing_agent = FakeAgent()
        failing_agent._preserve_policy_required_realized_context = Mock(
            return_value="initial answer"
        )

        def failing_replace(current_state, *, candidate_answer, **kwargs):
            failing_events.append(("replace", candidate_answer, kwargs))
            return current_state.with_updates(final_answer=candidate_answer), True

        failing_agent._replace_mutable_aggregate_answer = Mock(side_effect=failing_replace)
        failing_agent._append_operand_evidence_for_final_answer = Mock(
            side_effect=lambda current, **_kwargs: current
        )
        failing_agent._append_retrieved_narrative_evidence_for_final_answer = Mock(
            side_effect=lambda current, **_kwargs: (current, [])
        )
        failing_agent._apply_period_context_realignment_to_aggregate = Mock(
            side_effect=lambda **kwargs: kwargs["aggregate_state"]
        )
        failing_agent._enforce_source_stated_growth_answer_contract = Mock(
            return_value="contracted answer"
        )
        failing_preserve = Mock(side_effect=RuntimeError("preservation failed"))
        failing_agent._unresolved_structured_numeric_gap = Mock(
            side_effect=AssertionError("numeric gap accessed")
        )
        failing_agent._prune_nonfocus_numeric_narrative_sentences = Mock(
            side_effect=AssertionError("prune accessed")
        )

        with (
            patch.object(
                financial_graph_calculation,
                "preserve_retrieved_narrative_source_surface",
                failing_preserve,
            ),
            patch.object(
                financial_graph_calculation,
                "_polish_korean_particle_pairs",
                side_effect=AssertionError("polish accessed"),
            ) as failing_polish,
        ):
            with self.assertRaisesRegex(RuntimeError, "preservation failed"):
                financial_graph_calculation.FinancialAgentCalculationMixin._apply_final_narrative_repair_pipeline(
                    failing_agent,
                    state,
                    mutable_state=mutable_state,
                    narrative_docs=narrative_docs,
                    has_narrative_summary=False,
                    has_growth_rate_result=False,
                    deterministic_feedback="",
                )
        failing_preserve.assert_called_once_with("contracted answer", evidence_items)
        self.assertIs(failing_preserve.call_args.args[1], evidence_items)
        failing_agent._unresolved_structured_numeric_gap.assert_not_called()
        failing_agent._prune_nonfocus_numeric_narrative_sentences.assert_not_called()
        failing_polish.assert_not_called()
        self.assertEqual(ordered_results, snapshots["ordered"])
        self.assertEqual(projection, snapshots["projection"])
        self.assertEqual(selected_claim_ids, snapshots["claims"])
        self.assertEqual(evidence_items, snapshots["evidence"])
        self.assertEqual(state, snapshots["state"])
        self.assertEqual([id(item) for item in ordered_results], identities["ordered"])
        self.assertEqual([id(item) for item in evidence_items], identities["evidence"])
        self.assertEqual(narrative_docs, snapshots["docs"])
        self.assertEqual([id(item[0]) for item in narrative_docs], identities["docs"])

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


if __name__ == "__main__":
    unittest.main()
