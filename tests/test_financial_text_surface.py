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
                    ("_narrative_context_sentence_from_evidence", ("query",)): 1,
                    ("_include_narrative_context_if_needed", ("query",)): 1,
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
        self.assertEqual((len(graph_external), len(owner_local)), (21, 2))
        self.assertEqual(
            [(caller, args) for _module, caller, _receiver, args, _keywords in owner_local],
            [
                ("narrative_focus_variants", ("query",)),
                ("parenthetical_focus_variants", ("query",)),
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
