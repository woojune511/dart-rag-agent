import ast
import importlib
import json
import logging
import os
import pkgutil
import re
import subprocess
import sys
import textwrap
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RUNTIME_OPTIONAL_MODULE_PREFIXES = (
    "src.agent.mas_graph",
    "src.agent.mas_types",
    "src.experimental.mas",
    "src.ops.benchmark_runner",
    "src.ops.evaluator",
    "src.ops.portfolio_review_gates",
    "src.ops.promotion_trace_materiality_gate",
    "src.ops.reflection_promotion_gate",
    "src.ops.report_cache_index_smoke",
    "src.ops.report_cache_promotion_evidence_gate",
    "src.storage.report_cache_index",
)


class ImportSideEffectTests(unittest.TestCase):
    def _run_python_json(self, script: str, *args: str, timeout: int = 20) -> dict:
        proc = subprocess.run(
            [sys.executable, "-c", textwrap.dedent(script), *args],
            cwd=PROJECT_ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
        )
        self.assertEqual(proc.returncode, 0, msg=f"{args} failed:\n{proc.stderr}")
        return json.loads(proc.stdout.strip().splitlines()[-1])

    def _manifest_owner_foundation_entries(self) -> tuple[list[str], list[str], list[str]]:
        manifest = PROJECT_ROOT / "docs" / "architecture" / "current_runtime_cleanup_split_manifest.md"
        text = manifest.read_text(encoding="utf-8")
        modules_start = text.index("modules = [")
        modules_end = text.index("     ]", modules_start)
        modules = [
            line.strip().strip(",").strip('"')
            for line in text[modules_start:modules_end].splitlines()[1:]
            if line.strip()
        ]

        def command_paths(begin: str, end: str) -> list[str]:
            block = text[text.index(begin):text.index(end)]
            return [
                line.strip().rstrip(" \\")
                for line in block.splitlines()
                if line.strip().startswith("src/")
            ]

        staging_paths = command_paths(
            "Owner-foundation staging command:",
            "Owner-foundation staged review command:",
        )
        review_paths = command_paths(
            "Owner-foundation staged review command:",
            "Then land caller rewrites/removals",
        )
        return modules, staging_paths, review_paths

    def _manifest_review_bucket_entries(self) -> dict[str, tuple[list[str], list[str]]]:
        manifest = PROJECT_ROOT / "docs" / "architecture" / "current_runtime_cleanup_split_manifest.md"
        text = manifest.read_text(encoding="utf-8")
        section_matches = list(re.finditer(r"^## [0-9]+\. .+$", text, flags=re.MULTILINE))
        sections = [
            (match.start(), match.group(0).strip())
            for match in section_matches
        ]
        sections.append((len(text), "<end>"))

        bucket_entries: dict[str, tuple[list[str], list[str]]] = {}
        for (start, title), (end, _) in zip(sections, sections[1:]):
            block = text[start:end]
            if "Files:" not in block or "Staging command:" not in block:
                continue
            files = []
            in_files = False
            for line in block.splitlines():
                stripped = line.strip()
                if stripped == "Files:":
                    in_files = True
                    continue
                if in_files and (
                    stripped == "Minimum gates:"
                    or stripped == "Staging command:"
                    or stripped.startswith("## ")
                ):
                    break
                if in_files and stripped.startswith("- `") and "`" in stripped[3:]:
                    files.append(stripped.split("`", 2)[1])

            command_block = block.split("Staging command:", maxsplit=1)[1]
            command_block = command_block.split("```bash", maxsplit=1)[1].split("```", maxsplit=1)[0]
            staged = [
                line.strip().rstrip(" \\")
                for line in command_block.splitlines()
                if line.strip().startswith(("README", "docs/", "main.py", "src/", "tests/"))
            ]
            bucket_entries[title] = (files, staged)
        return bucket_entries

    def test_runtime_cleanup_manifest_owner_foundation_is_consistent(self) -> None:
        modules, staging_paths, review_paths = self._manifest_owner_foundation_entries()
        module_paths = sorted(module.replace(".", "/") + ".py" for module in modules)

        self.assertEqual(sorted(staging_paths), module_paths)
        self.assertEqual(sorted(review_paths), module_paths)
        self.assertNotIn("src/routing/types.py", staging_paths)
        self.assertIn("src/agent/financial_aggregate_projection.py", staging_paths)
        self.assertIn("src/agent/financial_aggregate_state.py", staging_paths)

    def test_runtime_cleanup_manifest_owner_foundation_import_gate_is_lightweight(self) -> None:
        modules, _, _ = self._manifest_owner_foundation_entries()
        script = """
            import importlib
            import json
            import sys

            modules = sys.argv[1].split(",")
            for name in modules:
                importlib.import_module(name)
            heavy_modules = sorted(
                package
                for package in ("pydantic", "langchain_core")
                if any(key == package or key.startswith(package + ".") for key in sys.modules)
            )
            print(json.dumps({
                "count": len(modules),
                "heavy_modules": heavy_modules,
            }, sort_keys=True))
            """

        payload = self._run_python_json(script, ",".join(modules))

        self.assertEqual(payload["count"], 23)
        self.assertEqual(payload["heavy_modules"], [])

    def test_runtime_cleanup_manifest_bucket_staging_commands_match_file_lists(self) -> None:
        bucket_entries = self._manifest_review_bucket_entries()

        self.assertEqual(
            sorted(bucket_entries),
            [
                "## 1. Runtime Projection",
                "## 2. Task Trace",
                "## 3. Primitive Owner",
                "## 4. Docs Audit",
            ],
        )
        for title, (files, staged) in bucket_entries.items():
            with self.subTest(title=title):
                self.assertEqual(sorted(staged), sorted(files))

    def test_source_package_imports_do_not_mutate_process_state(self) -> None:
        package_names = [
            "src.agent",
            "src.api",
            "src.experimental",
            "src.ingestion",
            "src.ops",
            "src.routing",
            "src.schema",
            "src.storage",
            "src.processing",
            "src.utils",
        ]
        module_names = []
        failures = []
        for package_name in package_names:
            before_path = list(sys.path)
            before_env = dict(os.environ)
            before_level = logging.getLogger().level
            package = importlib.import_module(package_name)
            changed = {
                "syspath_changed": sys.path != before_path,
                "environ_changed": dict(os.environ) != before_env,
                "logging_level_changed": logging.getLogger().level != before_level,
            }
            changed = {key: value for key, value in changed.items() if value}
            if changed:
                failures.append((package_name, changed))
            module_names.append(package_name)
            if hasattr(package, "__path__"):
                module_names.extend(
                    module.name
                    for module in pkgutil.walk_packages(package.__path__, prefix=f"{package_name}.")
                )

        for module_name in sorted(set(module_names)):
            before_path = list(sys.path)
            before_env = dict(os.environ)
            before_level = logging.getLogger().level
            importlib.import_module(module_name)
            changed = {
                "syspath_changed": sys.path != before_path,
                "environ_changed": dict(os.environ) != before_env,
                "logging_level_changed": logging.getLogger().level != before_level,
            }
            changed = {key: value for key, value in changed.items() if value}
            if changed:
                failures.append((module_name, changed))

        self.assertEqual(failures, [])

    def test_core_entrypoint_imports_do_not_mutate_process_state(self) -> None:
        modules = [
            "main",
            "src.api.financial_router",
            "src.agent.financial_graph",
            "src.agent.rag_chain",
            "src.agent.nodes.researcher_node",
            "src.agent.nodes.orchestrator_node",
            "src.storage.embedding_config",
            "src.ingestion.dart_fetcher",
            "src.ops.check_routing_confusions",
            "src.ops.retrospective_math_architecture_eval",
            "src.ops.retrospective_ontology_retrieval_eval",
        ]
        script = """
            import importlib
            import json
            import logging
            import os
            import sys

            name = sys.argv[1]
            before_path = list(sys.path)
            before_env = dict(os.environ)
            before_level = logging.getLogger().level
            importlib.import_module(name)
            print(json.dumps({
                "module": name,
                "syspath_changed": sys.path != before_path,
                "environ_changed": dict(os.environ) != before_env,
                "logging_level_changed": logging.getLogger().level != before_level,
            }, sort_keys=True))
            """

        failures = []
        for module in modules:
            payload = self._run_python_json(script, module)
            changed = {
                key: value
                for key, value in payload.items()
                if key.endswith("_changed") and value
            }
            if changed:
                failures.append((module, changed))

        self.assertEqual(failures, [])

    def test_pure_usage_accounting_imports_do_not_load_langchain(self) -> None:
        modules = [
            "src.utils.gemini_usage_counts",
            "src.agent.financial_graph_contextual",
        ]
        script = """
            import importlib
            import json
            import sys

            name = sys.argv[1]
            importlib.import_module(name)
            print(json.dumps({
                "module": name,
                "langchain_core_loaded": any(
                    key == "langchain_core" or key.startswith("langchain_core.")
                    for key in sys.modules
                ),
            }, sort_keys=True))
            """

        failures = []
        for module in modules:
            payload = self._run_python_json(script, module)
            if payload["langchain_core_loaded"]:
                failures.append(module)

        self.assertEqual(failures, [])

    def test_import_boundary_modules_do_not_load_heavy_dependencies(self) -> None:
        module_expectations = {
            "src.agent.financial_graph": {"pydantic", "langchain_core"},
            "src.agent.financial_aggregate_projection": {"pydantic", "langchain_core"},
            "src.agent.financial_aggregate_state": {"pydantic", "langchain_core"},
            "src.agent.financial_answer_slots": {"pydantic", "langchain_core"},
            "src.agent.financial_graph_calculation": {"pydantic", "langchain_core"},
            "src.agent.financial_graph_evidence": {"pydantic", "langchain_core"},
            "src.agent.financial_graph_model_loaders": {"pydantic", "langchain_core"},
            "src.agent.financial_langchain_loaders": {"pydantic", "langchain_core"},
            "src.agent.financial_graph_planning": {"pydantic", "langchain_core"},
            "src.agent.financial_graph_reconciliation": {"pydantic", "langchain_core"},
            "src.agent.financial_graph_state": {"pydantic", "langchain_core"},
            "src.agent.financial_runtime_trace": {"pydantic", "langchain_core"},
            "src.agent.financial_task_artifacts": {"pydantic", "langchain_core"},
            "src.api.financial_router": {"fastapi", "pydantic"},
            "src.routing.query_router": {"pydantic", "langchain_core"},
            "src.processing.table_records": {"pydantic", "langchain_core"},
            "src.processing.financial_parser": {"pydantic", "langchain_core"},
            "src.processing.pdf_parser": {"pydantic", "langchain_core"},
            "src.ingestion.dart_fetcher": {"pydantic", "requests"},
            "src.experimental.mas.diagnostics": {"pydantic", "langchain_core"},
            "src.ops.mas_direct_worker_probe": {"pydantic", "langchain_core"},
            "src.ops.replay_full_eval_from_results": {"pydantic", "langchain_core", "numpy"},
            "src.ops.retrospective_operand_grounding_eval": {"pydantic", "langchain_core", "numpy"},
            "src.ops.retrospective_evaluator_ablation_eval": {"pydantic", "langchain_core", "numpy"},
            "src.ops.retrospective_math_architecture_eval": {"pydantic", "langchain_core", "numpy"},
            "src.ops.evaluator": {"pydantic", "langchain_core", "numpy"},
            "src.ops.generate_grounded_answer_drafts": {"pydantic", "rank_bm25", "requests"},
            "src.ops.benchmark_runner": {"pydantic", "langchain_core"},
            "src.storage.vector_store": {"pydantic", "langchain_core"},
        }
        script = """
            import importlib
            import json
            import sys

            name = sys.argv[1]
            forbidden = sys.argv[2].split(",")
            importlib.import_module(name)
            loaded = sorted(
                package
                for package in forbidden
                if any(key == package or key.startswith(package + ".") for key in sys.modules)
            )
            print(json.dumps({
                "module": name,
                "loaded": loaded,
            }, sort_keys=True))
            """

        failures = []
        for module, forbidden in module_expectations.items():
            payload = self._run_python_json(script, module, ",".join(sorted(forbidden)))
            if payload["loaded"]:
                failures.append((module, payload["loaded"]))

        self.assertEqual(failures, [])

    def test_default_runtime_imports_do_not_load_optional_subsystems(self) -> None:
        modules = [
            "main",
            "src.api.financial_router",
            "src.agent.financial_graph",
        ]
        script = """
            import importlib
            import json
            import sys

            name = sys.argv[1]
            forbidden = sys.argv[2].split(",")
            importlib.import_module(name)
            loaded = sorted(
                module
                for module in sys.modules
                if any(module == prefix or module.startswith(prefix + ".") for prefix in forbidden)
            )
            print(json.dumps({
                "module": name,
                "loaded": loaded,
            }, sort_keys=True))
            """

        failures = []
        for module in modules:
            payload = self._run_python_json(
                script,
                module,
                ",".join(DEFAULT_RUNTIME_OPTIONAL_MODULE_PREFIXES),
            )
            if payload["loaded"]:
                failures.append((module, payload["loaded"]))

        self.assertEqual(failures, [])

    def test_default_runtime_invocation_does_not_load_optional_subsystems(self) -> None:
        script = """
            import json
            import sys

            from src.agent.financial_graph import FinancialAgent
            from src.agent.financial_retrieval_pipeline import (
                _report_cache_index_diagnostics_for_retrieval,
            )

            class FakeGraph:
                def invoke(self, initial):
                    return {
                        **dict(initial),
                        "answer": "insufficient evidence",
                        "citations": [],
                    }

            class FakeVectorStore:
                embeddings = object()

            FinancialAgent._build_llm_routes = lambda self: {"default": object()}
            FinancialAgent._build_graph = lambda self: FakeGraph()
            agent = FinancialAgent(
                FakeVectorStore(),
                routing_config={
                    "enable_semantic_router": False,
                    "enable_llm_fallback": False,
                },
            )
            result = agent.run("test question")
            cache_diagnostics = _report_cache_index_diagnostics_for_retrieval({}, "")

            forbidden = sys.argv[1].split(",")
            loaded = sorted(
                module
                for module in sys.modules
                if any(module == prefix or module.startswith(prefix + ".") for prefix in forbidden)
            )
            print(json.dumps({
                "answer": result.get("answer"),
                "cache_status": cache_diagnostics.get("status"),
                "loaded": loaded,
            }, sort_keys=True))
            """

        payload = self._run_python_json(
            script,
            ",".join(DEFAULT_RUNTIME_OPTIONAL_MODULE_PREFIXES),
        )

        self.assertEqual(payload["answer"], "insufficient evidence")
        self.assertEqual(payload["cache_status"], "not_configured")
        self.assertEqual(payload["loaded"], [])

    def test_source_has_no_top_level_dotenv_or_logging_configuration(self) -> None:
        violations = []
        for path in sorted((PROJECT_ROOT / "src").rglob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8-sig"))
            for node in tree.body:
                if not isinstance(node, ast.Expr) or not isinstance(node.value, ast.Call):
                    continue
                func = node.value.func
                name = ""
                if isinstance(func, ast.Name):
                    name = func.id
                elif isinstance(func, ast.Attribute):
                    name = func.attr
                if name in {"load_dotenv", "basicConfig"}:
                    violations.append(f"{path.relative_to(PROJECT_ROOT)}:{node.lineno}:{name}")

        self.assertEqual(violations, [])

    def test_state_only_contract_imports_use_lightweight_state_module(self) -> None:
        state_contract_names = {
            "AgentAnswer",
            "CalculationState",
            "DebugBundle",
            "DebugTraceBundle",
            "EvidenceState",
            "FinancialAgentState",
            "LedgerState",
            "ReflectionAction",
            "ReflectionPlanRecord",
            "ReflectionReport",
            "ReflectionRequest",
            "ReflectionRetryStrategy",
            "ReflectionState",
            "RetrievalState",
            "ReviewTrace",
            "RoutingState",
            "RuntimeCalculationTrace",
            "RuntimeProjectionMetadata",
            "TaskResultRecord",
        }
        violations = []
        paths = sorted((PROJECT_ROOT / "src").rglob("*.py"))
        paths.extend(sorted((PROJECT_ROOT / "tests").rglob("*.py")))
        for path in paths:
            tree = ast.parse(path.read_text(encoding="utf-8-sig"))
            for node in ast.walk(tree):
                if not isinstance(node, ast.ImportFrom):
                    continue
                if node.module != "src.agent.financial_graph_models":
                    continue
                imported_state_names = [
                    alias.name for alias in node.names if alias.name in state_contract_names
                ]
                if imported_state_names:
                    violations.append(
                        f"{path.relative_to(PROJECT_ROOT)}:{node.lineno}:"
                        f"{','.join(imported_state_names)}"
                    )

        self.assertEqual(violations, [])

    def test_structured_output_models_do_not_reexport_state_contracts(self) -> None:
        path = PROJECT_ROOT / "src" / "agent" / "financial_graph_models.py"
        tree = ast.parse(path.read_text(encoding="utf-8-sig"))
        violations = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom):
                continue
            if node.module == "src.agent.financial_graph_state":
                violations.append(f"{path.relative_to(PROJECT_ROOT)}:{node.lineno}")

        self.assertEqual(violations, [])

    def test_agent_ledger_writes_stay_in_task_artifact_owner(self) -> None:
        owner_path = PROJECT_ROOT / "src" / "agent" / "financial_task_artifacts.py"
        write_helpers = {"append_artifact", "upsert_task", "_append_artifact", "_upsert_task"}
        violations = []
        for path in sorted((PROJECT_ROOT / "src" / "agent").rglob("*.py")):
            if path == owner_path:
                continue
            tree = ast.parse(path.read_text(encoding="utf-8-sig"))
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module == "src.agent.financial_task_artifacts":
                    for alias in node.names:
                        if alias.name in write_helpers:
                            violations.append(
                                f"{path.relative_to(PROJECT_ROOT)}:{node.lineno}:import {alias.name}"
                            )
                elif isinstance(node, ast.Call):
                    func = node.func
                    if isinstance(func, ast.Name) and func.id in write_helpers:
                        violations.append(
                            f"{path.relative_to(PROJECT_ROOT)}:{node.lineno}:call {func.id}"
                        )

        self.assertEqual(violations, [])

    def test_task_artifact_owner_exports_only_caller_facing_helpers(self) -> None:
        from src.agent import financial_task_artifacts

        path = PROJECT_ROOT / "src" / "agent" / "financial_task_artifacts.py"
        tree = ast.parse(path.read_text(encoding="utf-8-sig"))
        exported = set(financial_task_artifacts.__all__)
        public_functions = {
            node.name
            for node in tree.body
            if isinstance(node, ast.FunctionDef) and not node.name.startswith("_")
        }
        self.assertEqual(public_functions, exported)
        low_level_helpers = {
            "append_artifact",
            "upsert_task",
            "_append_artifact",
            "_upsert_task",
            "normalise_ledger_records",
            "extract_artifact_payload_value",
            "find_task_record_in_list",
            "latest_artifact_value_for_task_records",
            "project_task_trace_from_runtime",
        }
        self.assertFalse(low_level_helpers & exported)
        self.assertFalse(hasattr(financial_task_artifacts, "normalise_ledger_records"))
        self.assertFalse(hasattr(financial_task_artifacts, "extract_artifact_payload_value"))
        self.assertFalse(hasattr(financial_task_artifacts, "find_task_record_in_list"))
        self.assertFalse(hasattr(financial_task_artifacts, "latest_artifact_value_for_task_records"))
        self.assertFalse(hasattr(financial_task_artifacts, "project_task_trace_from_runtime"))
        self.assertIn("operand_set_artifact_update", exported)
        self.assertIn("project_task_artifact_trace", exported)

    def test_runtime_graph_model_imports_stay_in_loader_owner(self) -> None:
        owner_path = PROJECT_ROOT / "src" / "agent" / "financial_graph_model_loaders.py"
        violations = []
        for path in sorted((PROJECT_ROOT / "src" / "agent").rglob("*.py")):
            if path == owner_path:
                continue
            tree = ast.parse(path.read_text(encoding="utf-8-sig"))
            parents = {}
            for node in ast.walk(tree):
                for child in ast.iter_child_nodes(node):
                    parents[child] = node
            for node in ast.walk(tree):
                if not isinstance(node, ast.ImportFrom):
                    continue
                if node.module != "src.agent.financial_graph_models":
                    continue
                parent = parents.get(node)
                type_checking_only = False
                while parent is not None:
                    if (
                        isinstance(parent, ast.If)
                        and isinstance(parent.test, ast.Name)
                        and parent.test.id == "TYPE_CHECKING"
                    ):
                        type_checking_only = True
                        break
                    parent = parents.get(parent)
                if not type_checking_only:
                    violations.append(f"{path.relative_to(PROJECT_ROOT)}:{node.lineno}")

        self.assertEqual(violations, [])

    def test_runtime_langchain_prompt_parser_imports_stay_in_loader_owner(self) -> None:
        owner_path = PROJECT_ROOT / "src" / "agent" / "financial_langchain_loaders.py"
        guarded_modules = {
            "langchain_core.output_parsers",
            "langchain_core.prompts",
            "langchain_core.runnables",
        }
        violations = []
        for path in sorted((PROJECT_ROOT / "src" / "agent").rglob("*.py")):
            if path == owner_path:
                continue
            tree = ast.parse(path.read_text(encoding="utf-8-sig"))
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module in guarded_modules:
                    violations.append(f"{path.relative_to(PROJECT_ROOT)}:{node.lineno}:from {node.module}")
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name in guarded_modules:
                            violations.append(
                                f"{path.relative_to(PROJECT_ROOT)}:{node.lineno}:import {alias.name}"
                            )

        self.assertEqual(violations, [])

    def test_runtime_langchain_document_imports_stay_in_loader_owner(self) -> None:
        owner_path = PROJECT_ROOT / "src" / "agent" / "financial_langchain_loaders.py"
        violations = []
        for path in sorted((PROJECT_ROOT / "src" / "agent").rglob("*.py")):
            if path == owner_path:
                continue
            tree = ast.parse(path.read_text(encoding="utf-8-sig"))
            parents = {}
            for node in ast.walk(tree):
                for child in ast.iter_child_nodes(node):
                    parents[child] = node
            for node in ast.walk(tree):
                import_modules = []
                if isinstance(node, ast.ImportFrom) and node.module == "langchain_core.documents":
                    import_modules.append(f"from {node.module}")
                elif isinstance(node, ast.Import):
                    import_modules.extend(
                        f"import {alias.name}"
                        for alias in node.names
                        if alias.name == "langchain_core.documents"
                    )
                if not import_modules:
                    continue
                parent = parents.get(node)
                type_checking_only = False
                while parent is not None:
                    if (
                        isinstance(parent, ast.If)
                        and isinstance(parent.test, ast.Name)
                        and parent.test.id == "TYPE_CHECKING"
                    ):
                        type_checking_only = True
                        break
                    parent = parents.get(parent)
                if not type_checking_only:
                    for module in import_modules:
                        violations.append(f"{path.relative_to(PROJECT_ROOT)}:{node.lineno}:{module}")

        self.assertEqual(violations, [])

    def test_source_uses_package_qualified_internal_imports(self) -> None:
        internal_roots = {
            "agent",
            "api",
            "config",
            "ingestion",
            "ops",
            "processing",
            "routing",
            "schema",
            "storage",
            "utils",
        }
        violations = []
        paths = sorted([PROJECT_ROOT / "main.py", *(PROJECT_ROOT / "src").rglob("*.py")])
        for path in paths:
            tree = ast.parse(path.read_text(encoding="utf-8-sig"))
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module:
                    root = node.module.split(".", maxsplit=1)[0]
                    if root in internal_roots:
                        violations.append(
                            f"{path.relative_to(PROJECT_ROOT)}:{node.lineno}:from {node.module}"
                        )
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        root = alias.name.split(".", maxsplit=1)[0]
                        if root in internal_roots:
                            violations.append(
                                f"{path.relative_to(PROJECT_ROOT)}:{node.lineno}:import {alias.name}"
                            )

        self.assertEqual(violations, [])

    def test_source_sys_path_mutation_is_direct_run_guarded(self) -> None:
        def is_sys_path_mutation(node: ast.AST) -> bool:
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                return False
            target = node.func.value
            return (
                node.func.attr in {"insert", "append"}
                and isinstance(target, ast.Attribute)
                and target.attr == "path"
                and isinstance(target.value, ast.Name)
                and target.value.id == "sys"
            )

        violations = []
        paths = sorted([PROJECT_ROOT / "main.py", *(PROJECT_ROOT / "src").rglob("*.py")])
        for path in paths:
            tree = ast.parse(path.read_text(encoding="utf-8-sig"))
            parents = {}
            for parent in ast.walk(tree):
                for child in ast.iter_child_nodes(parent):
                    parents[child] = parent

            for node in ast.walk(tree):
                if not is_sys_path_mutation(node):
                    continue
                guarded = False
                parent = parents.get(node)
                while parent is not None:
                    if isinstance(parent, ast.If):
                        condition = ast.unparse(parent.test)
                        if "__package__ in {None, ''}" in condition and "not in sys.path" in condition:
                            guarded = True
                            break
                    parent = parents.get(parent)
                if not guarded:
                    violations.append(f"{path.relative_to(PROJECT_ROOT)}:{node.lineno}")

        self.assertEqual(violations, [])


if __name__ == "__main__":
    unittest.main()
