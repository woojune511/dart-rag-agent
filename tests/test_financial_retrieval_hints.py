import ast
import json
import re
import sys
import unittest
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
for path in (PROJECT_ROOT, SRC_ROOT):
    path_text = str(path)
    if path_text not in sys.path:
        sys.path.insert(0, path_text)


from src.agent import financial_graph_evidence, financial_retrieval_hints
from src.agent.financial_graph import FinancialAgent


class FinancialRetrievalHintTests(unittest.TestCase):
    def test_current_source_focus_term_projection_contract(self) -> None:
        policy = {
            "focus_term_stopwords": ["Stop"],
            "max_focus_terms": 4,
            "focus_term_token_pattern": r"\S+",
            "focus_term_particle_suffix_pattern": r"(?:is|are)$",
        }
        policy_frozen = deepcopy(policy)
        real_findall = re.findall
        real_sub = re.sub
        real_fullmatch = re.fullmatch
        events = []

        def normalize(value):
            events.append(("normalize", str(value)))
            return " ".join(str(value).split())

        def findall(pattern, value, *args, **kwargs):
            events.append(("findall", pattern, value))
            return real_findall(pattern, value, *args, **kwargs)

        def substitute(pattern, replacement, value, *args, **kwargs):
            events.append(("sub", pattern, value))
            return real_sub(pattern, replacement, value, *args, **kwargs)

        def fullmatch(pattern, value, *args, **kwargs):
            events.append(("fullmatch", pattern, value))
            return real_fullmatch(pattern, value, *args, **kwargs)

        with (
            patch.object(financial_retrieval_hints, "EVIDENCE_EXTRACTION_POLICY", policy),
            patch.object(financial_retrieval_hints, "_normalise_spaces", side_effect=normalize),
            patch.object(financial_retrieval_hints.re, "findall", side_effect=findall),
            patch.object(financial_retrieval_hints.re, "sub", side_effect=substitute),
            patch.object(financial_retrieval_hints.re, "fullmatch", side_effect=fullmatch),
        ):
            result = financial_retrieval_hints.evidence_extraction_focus_terms(
                " Alpha(Inside) Alphais Stop 77 X Beta "
            )

        self.assertEqual(result, ["Alpha(Inside)", "Inside", "Alpha", "Beta"])
        self.assertEqual(policy, policy_frozen)
        self.assertEqual(events[0], ("normalize", "Stop"))
        token_scan = next(index for index, event in enumerate(events) if event[:2] == ("findall", r"\S+"))
        parenthetical_scan = next(
            index for index, event in enumerate(events) if event[:2] == ("findall", r"\(([^)]+)\)")
        )
        self.assertLess(token_scan, parenthetical_scan)
        self.assertTrue(any(event[0] == "sub" for event in events))
        self.assertTrue(any(event[0] == "fullmatch" and event[2] == "77" for event in events))

        downstream = []
        with (
            patch.object(financial_retrieval_hints, "EVIDENCE_EXTRACTION_POLICY", policy),
            patch.object(
                financial_retrieval_hints,
                "_normalise_spaces",
                side_effect=RuntimeError("focus normalization failed"),
            ),
            patch.object(
                financial_retrieval_hints.re,
                "findall",
                side_effect=lambda *_args, **_kwargs: downstream.append("findall"),
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "focus normalization failed"):
                financial_retrieval_hints.evidence_extraction_focus_terms("Alpha")
        self.assertEqual(downstream, [])

        tokenize_policy = {**policy, "focus_term_stopwords": []}
        with (
            patch.object(financial_retrieval_hints, "EVIDENCE_EXTRACTION_POLICY", tokenize_policy),
            patch.object(financial_retrieval_hints, "_normalise_spaces", side_effect=normalize),
            patch.object(
                financial_retrieval_hints.re,
                "findall",
                side_effect=RuntimeError("focus tokenization failed"),
            ),
            patch.object(
                financial_retrieval_hints.re,
                "sub",
                side_effect=AssertionError("tokenization failure must stop before substitution"),
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "focus tokenization failed"):
                financial_retrieval_hints.evidence_extraction_focus_terms("Alpha")

    def test_current_source_section_subset_projection_contract(self) -> None:
        nested = {"alias": True}
        preferred_one = {
            "evidence_id": "preferred-1",
            "question_relevance": " high ",
            "support_level": " direct ",
            "metadata": {"section_path": "Preferred > Detail", "nested": nested},
        }
        other = {
            "evidence_id": "other",
            "question_relevance": "high",
            "support_level": "direct",
            "metadata": {"section": "Other"},
        }
        preferred_context = {
            "evidence_id": "preferred-context",
            "question_relevance": "medium",
            "support_level": "context",
            "source_anchor": "Preferred context",
            "metadata": {},
        }
        preferred_two = {
            "evidence_id": "preferred-2",
            "question_relevance": "HIGH",
            "support_level": "DIRECT",
            "metadata": {"section": "preferred notes"},
        }
        evidence_items = [preferred_one, other, preferred_context, preferred_two]
        state = {
            "query": "Narrative query",
            "topic": "Narrative topic",
            "query_type": "risk",
            "intent": "fallback-intent",
            "format_preference": "text",
            "active_subtask": {
                "operation_family": "narrative_summary",
                "intent_override": "summary-intent",
            },
        }
        evidence_frozen = deepcopy(evidence_items)
        state_frozen = deepcopy(state)
        owner_calls = []

        def preferred_sections(actual_state, query, topic, intent):
            self.assertIs(actual_state, state)
            owner_calls.append((query, topic, intent))
            return [" Preferred ", "Other"]

        with patch.object(
            financial_retrieval_hints,
            "_active_preferred_sections",
            side_effect=preferred_sections,
        ):
            selected = financial_retrieval_hints.preferred_section_evidence_subset(evidence_items, state)

        self.assertEqual(owner_calls, [("Narrative query", "Narrative topic", "summary-intent")])
        self.assertEqual(selected, [preferred_one, preferred_context, preferred_two])
        self.assertIs(selected[0], preferred_one)
        self.assertIs(selected[1], preferred_context)
        self.assertIs(selected[2], preferred_two)
        self.assertIs(preferred_one["metadata"]["nested"], nested)
        self.assertEqual(evidence_items, evidence_frozen)
        self.assertEqual(state, state_frozen)

        owner_bomb = Mock(side_effect=AssertionError("early gate must not resolve sections"))
        with patch.object(financial_retrieval_hints, "_active_preferred_sections", owner_bomb):
            self.assertEqual(financial_retrieval_hints.preferred_section_evidence_subset([], state), [])
            self.assertEqual(
                financial_retrieval_hints.preferred_section_evidence_subset(
                    evidence_items,
                    {**state, "format_preference": "table"},
                ),
                [],
            )
            self.assertEqual(
                financial_retrieval_hints.preferred_section_evidence_subset(
                    evidence_items,
                    {
                        **state,
                        "query_type": "comparison",
                        "active_subtask": {"operation_family": "lookup"},
                    },
                ),
                [],
            )
        owner_bomb.assert_not_called()

        with patch.object(financial_retrieval_hints, "_active_preferred_sections", return_value=[]):
            self.assertEqual(financial_retrieval_hints.preferred_section_evidence_subset(evidence_items, state), [])
        with patch.object(
            financial_retrieval_hints,
            "_active_preferred_sections",
            return_value=["preferred"],
        ):
            self.assertEqual(
                financial_retrieval_hints.preferred_section_evidence_subset([preferred_one, other], state),
                [],
            )

        downstream = []
        with (
            patch.object(
                financial_retrieval_hints,
                "_active_preferred_sections",
                side_effect=RuntimeError("preferred section resolution failed"),
            ),
            patch.object(
                financial_retrieval_hints,
                "_normalise_spaces",
                side_effect=lambda *_args: downstream.append("normalize"),
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "preferred section resolution failed"):
                financial_retrieval_hints.preferred_section_evidence_subset(evidence_items, state)
        self.assertEqual(downstream, [])

        with (
            patch.object(financial_retrieval_hints, "_active_preferred_sections", return_value=["preferred"]),
            patch.object(
                financial_retrieval_hints,
                "_normalise_spaces",
                side_effect=RuntimeError("section normalization failed"),
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "section normalization failed"):
                financial_retrieval_hints.preferred_section_evidence_subset(evidence_items, state)

    def test_current_source_guidance_projection_contract(self) -> None:
        nested = {"alias": True}
        policy = {
            "trend_instruction": "trend instruction",
            "trend_output_style": "trend style",
            "trend_context_instruction": "context instruction",
            "trend_context_output_style": "context style",
            "instructions": {"qa": "qa instruction", "comparison": "comparison instruction"},
            "output_styles": {"qa": "qa style", "comparison": "comparison style"},
            "coverage_notes": {"complete": "complete note", "sparse": "sparse note"},
            "nested": nested,
        }
        policy_frozen = deepcopy(policy)
        queries = []

        def narrative_gate(query):
            queries.append(query)
            return query == "context query"

        with (
            patch.object(financial_retrieval_hints, "EVIDENCE_COMPRESSION_GUIDANCE_POLICY", policy),
            patch.object(
                financial_retrieval_hints,
                "query_requests_narrative_context",
                side_effect=narrative_gate,
            ),
        ):
            context = financial_retrieval_hints.compression_guidance("trend", "context query", "complete")
            ordinary = financial_retrieval_hints.compression_guidance("comparison", "ordinary query", "sparse")
            fallback = financial_retrieval_hints.compression_guidance("unknown", "fallback query", "missing")

        self.assertEqual(
            context,
            {
                "instruction": "context instruction",
                "output_style": "context style",
                "coverage_note": "complete note",
            },
        )
        self.assertEqual(
            ordinary,
            {
                "instruction": "comparison instruction",
                "output_style": "comparison style",
                "coverage_note": "sparse note",
            },
        )
        self.assertEqual(
            fallback,
            {
                "instruction": "qa instruction",
                "output_style": "qa style",
                "coverage_note": "",
            },
        )
        self.assertEqual(queries, ["context query", "ordinary query", "fallback query"])
        self.assertEqual(policy, policy_frozen)
        self.assertIs(policy["nested"], nested)

        downstream = []
        with (
            patch.object(financial_retrieval_hints, "EVIDENCE_COMPRESSION_GUIDANCE_POLICY", policy),
            patch.object(
                financial_retrieval_hints,
                "query_requests_narrative_context",
                side_effect=RuntimeError("narrative gate failed"),
            ),
            patch.object(
                financial_graph_evidence,
                "_normalise_spaces",
                side_effect=lambda *_args: downstream.append("normalize"),
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "narrative gate failed"):
                financial_retrieval_hints.compression_guidance("trend", "query", "complete")
        self.assertEqual(downstream, [])

        class PolicyCopyBomb:
            def keys(self):
                raise RuntimeError("guidance policy copy failed")

        with (
            patch.object(
                financial_retrieval_hints,
                "EVIDENCE_COMPRESSION_GUIDANCE_POLICY",
                PolicyCopyBomb(),
            ),
            patch.object(
                financial_retrieval_hints,
                "query_requests_narrative_context",
                side_effect=AssertionError("policy copy must happen before the query gate"),
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "guidance policy copy failed"):
                financial_retrieval_hints.compression_guidance("trend", "query", "complete")

    def test_current_source_retrieval_hint_static_binding_dag_and_baseline(self) -> None:
        graph_path = PROJECT_ROOT / "src" / "agent" / "financial_graph_evidence.py"
        owner_path = PROJECT_ROOT / "src" / "agent" / "financial_retrieval_hints.py"
        graph_tree = ast.parse(graph_path.read_text(encoding="utf-8-sig"))
        owner_tree = ast.parse(owner_path.read_text(encoding="utf-8-sig"))
        graph_class = next(
            node
            for node in graph_tree.body
            if isinstance(node, ast.ClassDef) and node.name == "FinancialAgentEvidenceMixin"
        )
        public_targets = [
            "evidence_extraction_focus_terms",
            "preferred_section_evidence_subset",
            "compression_guidance",
        ]
        retired_targets = [f"_{name}" for name in public_targets]
        graph_defs = {
            node.name: node
            for node in graph_class.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in retired_targets
        }
        self.assertEqual(graph_defs, {})

        owner_defs = {
            node.name: node
            for node in owner_tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in public_targets
        }
        self.assertEqual(list(owner_defs), public_targets)
        self.assertEqual(
            [owner_defs[name].end_lineno - owner_defs[name].lineno + 1 for name in public_targets],
            [40, 58, 18],
        )
        self.assertEqual(
            [[argument.arg for argument in owner_defs[name].args.args] for name in public_targets],
            [["query"], ["evidence_items", "state"], ["query_type", "query", "coverage"]],
        )
        owner_public = []
        owner_private = []
        for node in owner_tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                (owner_private if node.name.startswith("_") else owner_public).append(node.name)
        self.assertEqual((len(owner_public), len(owner_private)), (10, 4))

        class BindingVisitor(ast.NodeVisitor):
            def __init__(self, relative_path):
                self.relative_path = relative_path
                self.stack = []
                self.try_depth = 0
                self.calls = []

            def visit_FunctionDef(self, node):
                self.stack.append(node.name)
                self.generic_visit(node)
                self.stack.pop()

            def visit_AsyncFunctionDef(self, node):
                self.visit_FunctionDef(node)

            def visit_Try(self, node):
                self.try_depth += 1
                self.generic_visit(node)
                self.try_depth -= 1

            def visit_Call(self, node):
                name = node.func.attr if isinstance(node.func, ast.Attribute) else (
                    node.func.id if isinstance(node.func, ast.Name) else ""
                )
                if name in public_targets:
                    receiver = ast.unparse(node.func.value) if isinstance(node.func, ast.Attribute) else "Name"
                    self.calls.append(
                        (
                            self.relative_path,
                            self.stack[-1],
                            name,
                            receiver,
                            len(node.args),
                            tuple(keyword.arg for keyword in node.keywords),
                            self.try_depth,
                        )
                    )
                self.generic_visit(node)

        calls = []
        for path in sorted((PROJECT_ROOT / "src").rglob("*.py")):
            visitor = BindingVisitor(path.relative_to(PROJECT_ROOT).as_posix())
            visitor.visit(ast.parse(path.read_text(encoding="utf-8-sig")))
            calls.extend(visitor.calls)
        self.assertEqual(
            calls,
            [
                (
                    "src/agent/financial_graph_evidence.py",
                    "_select_evidence_for_compression",
                    "preferred_section_evidence_subset",
                    "Name",
                    2,
                    (),
                    0,
                ),
                (
                    "src/agent/financial_graph_evidence.py",
                    "_extract_evidence",
                    "evidence_extraction_focus_terms",
                    "Name",
                    1,
                    (),
                    0,
                ),
                (
                    "src/agent/financial_graph_evidence.py",
                    "_compress_answer",
                    "compression_guidance",
                    "Name",
                    3,
                    (),
                    0,
                ),
            ],
        )

        retired_refs = []
        for path in sorted((PROJECT_ROOT / "src").rglob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8-sig"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Attribute) and node.attr in retired_targets:
                    retired_refs.append((path, node.lineno, node.attr))
                elif isinstance(node, ast.Name) and node.id in retired_targets:
                    retired_refs.append((path, node.lineno, node.id))
        self.assertEqual(retired_refs, [])

        selected_nodes = set()
        for node in owner_defs.values():
            selected_nodes.update(ast.walk(node))
        active_section_loads = [
            node
            for node in ast.walk(owner_tree)
            if isinstance(node, ast.Name)
            and isinstance(node.ctx, ast.Load)
            and node.id == "_active_preferred_sections"
        ]
        self.assertEqual(sum(node in selected_nodes for node in active_section_loads), 1)
        self.assertEqual(sum(node not in selected_nodes for node in active_section_loads), 0)

        graph_imports = {
            alias.name
            for node in graph_tree.body
            if isinstance(node, ast.ImportFrom)
            for alias in node.names
        }
        owner_imports = {
            alias.name
            for node in ast.walk(owner_tree)
            if isinstance(node, ast.ImportFrom)
            for alias in node.names
        }
        self.assertTrue(set(public_targets).issubset(graph_imports))
        self.assertNotIn("_active_preferred_sections", graph_imports)
        self.assertTrue(
            {
                "FinancialAgentState",
                "query_requests_narrative_context",
                "EVIDENCE_EXTRACTION_POLICY",
                "EVIDENCE_COMPRESSION_GUIDANCE_POLICY",
            }.issubset(owner_imports)
        )
        for name in (
            "re",
            "_normalise_spaces",
            "EVIDENCE_EXTRACTION_POLICY",
            "EVIDENCE_COMPRESSION_GUIDANCE_POLICY",
            "query_requests_narrative_context",
        ):
            outside = [
                node
                for node in ast.walk(graph_tree)
                if isinstance(node, ast.Name)
                and isinstance(node.ctx, ast.Load)
                and node.id == name
            ]
            self.assertTrue(outside, name)

        modules = {path.stem: path for path in (PROJECT_ROOT / "src" / "agent").glob("*.py")}
        edges = {name: set() for name in modules}
        for module_name, path in modules.items():
            module_tree = ast.parse(path.read_text(encoding="utf-8-sig"))
            for node in ast.walk(module_tree):
                if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("src.agent."):
                    dependency = node.module.rsplit(".", 1)[-1]
                    if dependency in modules:
                        edges[module_name].add(dependency)
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name.startswith("src.agent."):
                            dependency = alias.name.rsplit(".", 1)[-1]
                            if dependency in modules:
                                edges[module_name].add(dependency)

        def reaches(start, destination):
            pending = list(edges.get(start, ()))
            seen = set()
            while pending:
                current = pending.pop()
                if current == destination:
                    return True
                if current not in seen:
                    seen.add(current)
                    pending.extend(edges.get(current, ()))
            return False

        for dependency in ("financial_graph_state", "financial_operation_policies"):
            self.assertFalse(reaches(dependency, "financial_retrieval_hints"), dependency)
        self.assertFalse(reaches("financial_retrieval_hints", "financial_graph_evidence"))

        from src.ops.audit_runtime_domain_terms import (
            collect_runtime_domain_term_occurrences,
            collect_runtime_domain_terms,
        )

        records = collect_runtime_domain_terms(PROJECT_ROOT)
        occurrences = collect_runtime_domain_term_occurrences(PROJECT_ROOT)
        selected_ranges = [(node.lineno, node.end_lineno) for node in owner_defs.values()]
        selected_hits = [
            row
            for row in occurrences
            if row["path"] == "src/agent/financial_retrieval_hints.py"
            and any(start <= row["line"] <= end for start, end in selected_ranges)
        ]
        self.assertEqual(len(records), 217)
        self.assertEqual(selected_hits, [])

    def test_current_source_retrieval_hint_callers_pin_args_adoption_and_exception_stop(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        nested = {"alias": True}

        ranked_one = {
            "evidence_id": "ranked-1",
            "question_relevance": "high",
            "support_level": "direct",
            "nested": nested,
        }
        ranked_two = {
            "evidence_id": "ranked-2",
            "question_relevance": "high",
            "support_level": "direct",
            "nested": nested,
        }
        input_rows = [ranked_one, ranked_two]
        ranked = [ranked_two, ranked_one]
        preferred = [ranked_one, ranked_two]
        selection_state = {"query": "query", "nested": nested}
        selection_frozen = deepcopy(selection_state)
        input_frozen = deepcopy(input_rows)
        selection_events = []

        def sort_rows(actual_rows):
            self.assertIs(actual_rows, input_rows)
            selection_events.append("sort")
            return ranked

        def choose_preferred(actual_rows, actual_state):
            self.assertIs(actual_rows, ranked)
            self.assertIs(actual_state, selection_state)
            selection_events.append("preferred")
            return preferred

        with (
            patch.object(agent, "_sort_evidence_items", side_effect=sort_rows),
            patch.object(
                financial_graph_evidence,
                "preferred_section_evidence_subset",
                side_effect=choose_preferred,
            ),
        ):
            selected = agent._select_evidence_for_compression(input_rows, "qa", selection_state)
        self.assertEqual(selection_events, ["sort", "preferred"])
        self.assertEqual(selected, preferred)
        self.assertIs(selected[0], ranked_one)
        self.assertIs(selected[1], ranked_two)
        self.assertEqual(input_rows, input_frozen)
        self.assertEqual(selection_state, selection_frozen)

        with (
            patch.object(agent, "_sort_evidence_items", return_value=ranked),
            patch.object(
                financial_graph_evidence,
                "preferred_section_evidence_subset",
                side_effect=RuntimeError("preferred subset failed"),
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "preferred subset failed"):
                agent._select_evidence_for_compression(input_rows, "qa", selection_state)

        doc_one = {"page_content": "one", "nested": nested}
        doc_two = {"page_content": "two", "nested": nested}
        extraction_state = {
            "query": "  extraction query  ",
            "query_type": "qa",
            "retrieved_docs": [doc_one, doc_two],
            "active_subtask": {"operation_family": "lookup"},
            "nested": nested,
        }
        extraction_frozen = deepcopy(extraction_state)
        extraction_events = []

        class ExtractionLlm:
            def with_structured_output(self, model):
                extraction_events.append(("structured", model))
                return object()

        def focus_terms(query):
            self.assertEqual(query, "  extraction query  ")
            extraction_events.append(("focus", query))
            return ["focus"]

        def build_context(actual_docs, *, focus_terms):
            self.assertIsNot(actual_docs, extraction_state["retrieved_docs"])
            self.assertEqual(len(actual_docs), 2)
            self.assertIs(actual_docs[0], doc_one)
            self.assertIs(actual_docs[1], doc_two)
            self.assertEqual(focus_terms, ["focus"])
            extraction_events.append(("context", tuple(focus_terms)))
            raise RuntimeError("context projection stopped")

        with (
            patch.object(financial_graph_evidence, "requires_direct_numeric_grounding", return_value=False),
            patch.object(financial_graph_evidence, "evidence_extraction_model", return_value="model"),
            patch.object(agent, "_llm_for_phase", return_value=ExtractionLlm()),
            patch.object(
                financial_graph_evidence,
                "evidence_extraction_focus_terms",
                side_effect=focus_terms,
            ),
            patch.object(agent, "_build_evidence_context", side_effect=build_context),
        ):
            with self.assertRaisesRegex(RuntimeError, "context projection stopped"):
                agent._extract_evidence(extraction_state)
        self.assertEqual(
            extraction_events,
            [("structured", "model"), ("focus", "  extraction query  "), ("context", ("focus",))],
        )
        self.assertEqual(extraction_state, extraction_frozen)

        context_after_owner = Mock(side_effect=AssertionError("owner failure must stop context construction"))
        with (
            patch.object(financial_graph_evidence, "requires_direct_numeric_grounding", return_value=False),
            patch.object(financial_graph_evidence, "evidence_extraction_model", return_value="model"),
            patch.object(agent, "_llm_for_phase", return_value=ExtractionLlm()),
            patch.object(
                financial_graph_evidence,
                "evidence_extraction_focus_terms",
                side_effect=RuntimeError("focus owner failed"),
            ),
            patch.object(agent, "_build_evidence_context", context_after_owner),
        ):
            with self.assertRaisesRegex(RuntimeError, "focus owner failed"):
                agent._extract_evidence(extraction_state)
        context_after_owner.assert_not_called()

        compression_row = {
            "evidence_id": "ev-1",
            "claim": "claim",
            "question_relevance": "high",
            "support_level": "direct",
            "nested": nested,
        }
        compression_state = {
            "query": "compression query",
            "query_type": "trend",
            "evidence_status": "complete",
            "evidence_items": [compression_row],
            "evidence_bullets": ["- claim"],
            "retrieved_docs": [],
            "nested": nested,
        }
        compression_frozen = deepcopy(compression_state)
        compression_events = []
        guidance = {
            "instruction": "instruction",
            "coverage_note": "coverage note",
            "output_style": "output style",
        }

        class StructuredLlm:
            pass

        structured_llm = StructuredLlm()

        class CompressionLlm:
            def with_structured_output(self, model):
                compression_events.append(("structured", model))
                return structured_llm

        class Chain:
            def invoke(self, payload):
                compression_events.append(("invoke", dict(payload)))
                self_test.assertEqual(
                    payload,
                    {
                        "instruction": "instruction",
                        "coverage_note": "coverage note",
                        "output_style": "output style",
                        "evidence": "formatted evidence",
                        "query": "compression query",
                    },
                )
                return SimpleNamespace(
                    selected_claim_ids=["ev-1"],
                    draft_points=["point"],
                    draft_answer="draft answer",
                )

        self_test = self

        class Prompt:
            def __or__(self, other):
                self_test.assertIs(other, structured_llm)
                compression_events.append("chain")
                return Chain()

        def guidance_owner(query_type, query, coverage):
            self.assertEqual((query_type, query, coverage), ("trend", "compression query", "complete"))
            compression_events.append(("guidance", query_type, query, coverage))
            return guidance

        def expand(ids, evidence, *, query):
            self.assertEqual(ids, ["ev-1"])
            self.assertIs(evidence, compression_state["evidence_items"])
            self.assertEqual(query, "compression query")
            compression_events.append("expand")
            return ["ev-1"]

        def filter_rows(evidence, ids):
            self.assertIs(evidence, compression_state["evidence_items"])
            self.assertEqual(ids, ["ev-1"])
            compression_events.append("filter")
            return [compression_row]

        def augment(answer, evidence, *, query):
            self.assertEqual(answer, "draft answer")
            self.assertIs(evidence[0], compression_row)
            self.assertEqual(query, "compression query")
            compression_events.append("augment")
            return "final answer"

        with (
            patch.object(agent, "_compose_entity_table_summary_answer", return_value=None),
            patch.object(agent, "_select_evidence_for_compression", return_value=[compression_row]),
            patch.object(agent, "_format_evidence_for_prompt", return_value="formatted evidence"),
            patch.object(financial_graph_evidence, "compression_guidance", side_effect=guidance_owner),
            patch.object(agent, "_llm_for_phase", return_value=CompressionLlm()),
            patch.object(financial_graph_evidence, "compression_output_model", return_value="compression-model"),
            patch.object(financial_graph_evidence, "chat_prompt_template_from_template", return_value=Prompt()),
            patch.object(agent, "_expand_selected_claim_ids_for_narrative_drivers", side_effect=expand),
            patch.object(agent, "_filter_evidence_by_ids", side_effect=filter_rows),
            patch.object(agent, "_augment_narrative_answer_with_supported_drivers", side_effect=augment),
        ):
            compressed = agent._compress_answer(compression_state)

        self.assertEqual(
            compressed,
            {
                "selected_claim_ids": ["ev-1"],
                "draft_points": ["point"],
                "compressed_answer": "final answer",
            },
        )
        guidance_index = next(index for index, event in enumerate(compression_events) if isinstance(event, tuple) and event[0] == "guidance")
        structured_index = next(index for index, event in enumerate(compression_events) if isinstance(event, tuple) and event[0] == "structured")
        invoke_index = next(index for index, event in enumerate(compression_events) if isinstance(event, tuple) and event[0] == "invoke")
        self.assertLess(guidance_index, structured_index)
        self.assertLess(structured_index, invoke_index)
        self.assertEqual(compression_state, compression_frozen)
        self.assertIs(compression_state["evidence_items"][0], compression_row)

        compression_downstream = Mock(side_effect=AssertionError("guidance failure must stop LLM construction"))
        with (
            patch.object(agent, "_compose_entity_table_summary_answer", return_value=None),
            patch.object(agent, "_select_evidence_for_compression", return_value=[compression_row]),
            patch.object(agent, "_format_evidence_for_prompt", return_value="formatted evidence"),
            patch.object(
                financial_graph_evidence,
                "compression_guidance",
                side_effect=RuntimeError("guidance owner failed"),
            ),
            patch.object(agent, "_llm_for_phase", compression_downstream),
        ):
            with self.assertRaisesRegex(RuntimeError, "guidance owner failed"):
                agent._compress_answer(compression_state)
        compression_downstream.assert_not_called()
        self.assertEqual(compression_state, compression_frozen)
        self.assertIs(compression_state["evidence_items"][0], compression_row)


if __name__ == "__main__":
    unittest.main()
