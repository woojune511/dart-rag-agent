from __future__ import annotations

from tests.semantic_program_test_support import *


class SemanticCalculationProgramCatalogTests(unittest.TestCase):
    def test_candidate_catalog_assigns_stable_ids_and_preserves_source_material(self) -> None:
        source_candidates = [
            {
                "candidate_id": "chunk-1::value:0",
                "source_anchor": "[sample | 2024 | section]",
                "text": "opening and closing quantity",
                "candidate_kind": "structured_value",
                "metadata": {
                    "row_label": "quantity",
                    "table_source_id": "table-a",
                    "year": 2024,
                    "structured_cells": [
                        {"column_headers": ["opening"], "value_text": "343", "unit_hint": "items"},
                        {"column_headers": ["closing"], "value_text": "380", "unit_hint": "items"},
                    ],
                },
            }
        ]
        first = build_semantic_candidate_catalog(source_candidates)
        second = build_semantic_candidate_catalog(source_candidates)
        numeric = [item for item in first if item["kind"] == "numeric"]
        self.assertEqual(len(numeric), 2)
        self.assertEqual([item["candidate_id"] for item in first], [item["candidate_id"] for item in second])
        self.assertEqual(semantic_candidate_catalog_fingerprint(first), semantic_candidate_catalog_fingerprint(second))
        self.assertEqual([item["raw_value"] for item in numeric], ["343", "380"])
        self.assertTrue(all(item["context_fingerprint"].startswith("table-a") for item in numeric))

    def test_candidate_stage_diagnostics_distinguish_three_generic_loss_stages(self) -> None:
        state = {
            "retrieved_docs": [
                (
                    SimpleNamespace(
                        page_content="neighbor value only",
                        metadata={"chunk_uid": "source-local"},
                    ),
                    0.9,
                )
            ],
            "seed_retrieved_docs": [
                (
                    SimpleNamespace(
                        page_content="neighbor value only",
                        metadata={"chunk_uid": "source-local"},
                    ),
                    0.9,
                ),
                (
                    SimpleNamespace(
                        page_content="two projected values",
                        metadata={"chunk_uid": "source-prompt"},
                    ),
                    0.8,
                ),
            ],
            "retrieval_debug_trace": {
                "source_window": {
                    "retrieved_source_ids": ["source-local"],
                    "retrieved_unidentified_count": 0,
                    "seed_source_ids": ["source-local", "source-prompt"],
                    "seed_unidentified_count": 0,
                }
            },
        }
        source_candidates = [
            {
                "candidate_id": "source-local::row:0",
                "candidate_kind": "table_row",
            },
            {
                "candidate_id": "source-prompt::row:0",
                "candidate_kind": "table_row",
            },
        ]
        catalog = [
            {
                "candidate_id": "cand-neighbor",
                "evidence_id": "source-local",
                "kind": "numeric",
            },
            {
                "candidate_id": "cand-kept",
                "evidence_id": "source-prompt",
                "kind": "numeric",
            },
            {
                "candidate_id": "cand-dropped",
                "evidence_id": "source-prompt",
                "kind": "numeric",
            },
        ]
        diagnostics = semantic_candidate_stage_diagnostics(
            state=state,
            source_candidates=source_candidates,
            catalog=catalog,
            prompt_catalog=[catalog[1]],
        )
        by_source = {
            item["source_id"]: item for item in diagnostics["by_source"]
        }
        self.assertEqual(
            diagnostics["source_window_origin"],
            "retrieval_debug_trace",
        )

        # Stage 1: the expected source never entered either preserved window.
        self.assertNotIn("source-absent", diagnostics["source_window"]["seed_source_ids"])
        self.assertNotIn("source-absent", by_source)

        # Stage 2: the source was projected, but a reconstructed local-cell ID is absent.
        local = by_source["source-local"]
        self.assertTrue(local["in_retrieved_window"])
        self.assertEqual(local["source_candidate_count"], 1)
        self.assertEqual(local["catalog_candidate_count"], 1)
        self.assertEqual(
            local["catalog_candidate_id_fingerprint"],
            semantic_candidate_id_fingerprint(["cand-neighbor"]),
        )
        self.assertNotEqual(
            local["catalog_candidate_id_fingerprint"],
            semantic_candidate_id_fingerprint(["cand-neighbor", "cand-needed"]),
        )

        # Stage 3: the catalog contains the candidate but prompt admission removes it.
        prompt = by_source["source-prompt"]
        self.assertTrue(prompt["in_seed_window"])
        self.assertEqual(prompt["catalog_candidate_count"], 2)
        self.assertEqual(prompt["prompt_candidate_count"], 1)
        self.assertEqual(prompt["prompt_drop_count"], 1)
        self.assertEqual(
            prompt["catalog_candidate_id_fingerprint"],
            semantic_candidate_id_fingerprint(["cand-kept", "cand-dropped"]),
        )
        self.assertEqual(
            prompt["prompt_candidate_id_fingerprint"],
            semantic_candidate_id_fingerprint(["cand-kept"]),
        )

    def test_unstructured_table_row_ignores_data_preview_after_period_header(self) -> None:
        catalog = build_semantic_candidate_catalog(
            [
                {
                    "candidate_id": "statement-row",
                    "source_anchor": "[sample | 2023 | primary statement]",
                    "text": "target metric | (300) | (200) | (100)",
                    "candidate_kind": "table_row",
                    "metadata": {
                        "year": 2023,
                        "row_label": "target metric",
                        "row_text": "target metric | (300) | (200) | (100)",
                        "unit_hint": "items",
                        "statement_type": "income_statement",
                        "consolidation_scope": "consolidated",
                        "table_source_id": "statement-table",
                        "table_header_context": (
                            "| 2023 | 2022 | 2021\n"
                            "baseline metric | 500 | 400 | 300"
                        ),
                        "period_labels": ["current", "2023", "2022", "2021"],
                    },
                }
            ]
        )

        numeric = [item for item in catalog if item["kind"] == "numeric"]
        self.assertEqual([item["period"] for item in numeric], ["2023", "2022", "2021"])
        self.assertEqual([item["value_year"] for item in numeric], [2023, 2022, 2021])

    def test_candidate_catalog_keeps_prose_value_when_paragraph_has_table_metadata(self) -> None:
        catalog = build_semantic_candidate_catalog(
            [
                {
                    "candidate_id": "mixed-paragraph",
                    "source_anchor": "[sample | 2024 | discussion]",
                    "text": (
                        "Metric A | 2,163,234 | 백만원\n"
                        "The discussion states the requested adjustment as "
                        "6,769억원 and explains its effect."
                    ),
                    "candidate_kind": "chunk",
                    "metadata": {
                        "year": 2024,
                        "block_type": "paragraph",
                        "is_table": False,
                        "table_row_records_json": json.dumps(
                            [
                                {
                                    "row_label": "Metric A",
                                    "cells": [
                                        {
                                            "value_text": "2,163,234",
                                            "unit_hint": "백만원",
                                        }
                                    ],
                                }
                            ]
                        ),
                        "structured_cells": [
                            {"value_text": "2,163,234", "unit_hint": "백만원"}
                        ],
                    },
                }
            ]
        )

        prose = next(
            item
            for item in catalog
            if item.get("candidate_kind") == "sentence_value"
            and item.get("raw_value") == "6,769"
        )
        self.assertEqual(prose["raw_unit"], "억원")
        self.assertEqual(prose["normalized_value"], 676_900_000_000.0)
        self.assertIn("requested adjustment", prose["source_text"])

        table_catalog = build_semantic_candidate_catalog(
            [
                {
                    "candidate_id": "table-chunk",
                    "source_anchor": "[sample | 2024 | table]",
                    "text": "Metric A | 2,163,234백만원",
                    "candidate_kind": "chunk",
                    "metadata": {
                        "year": 2024,
                        "block_type": "table",
                        "is_table": True,
                        "structured_cells": [
                            {"value_text": "2,163,234", "unit_hint": "백만원"}
                        ],
                    },
                }
            ]
        )
        self.assertFalse(
            any(
                item.get("candidate_kind") == "sentence_value"
                for item in table_catalog
            )
        )

    def test_candidate_catalog_keeps_explicit_count_values_when_chunk_has_table_metadata(self) -> None:
        catalog = build_semantic_candidate_catalog(
            [
                {
                    "candidate_id": "mixed-structure",
                    "source_anchor": "[sample | 2024 | operating discussion]",
                    "text": (
                        "The source states that the first quantity was 1,560만 대 and "
                        "the second quantity was 87.0만 대."
                    ),
                    "candidate_kind": "chunk",
                    "metadata": {
                        "year": 2024,
                        "structured_cells": [
                            {"value_text": "12.5", "unit_hint": "%"}
                        ],
                        "table_row_records_json": json.dumps(
                            [
                                {
                                    "row_label": "unrelated rate",
                                    "cells": [
                                        {"value_text": "12.5", "unit_hint": "%"}
                                    ],
                                }
                            ]
                        ),
                    },
                }
            ]
        )

        sentence_values = {
            (item.get("raw_value"), item.get("raw_unit")): item
            for item in catalog
            if item.get("candidate_kind") == "sentence_value"
        }
        self.assertEqual(
            sentence_values[("1,560", "만 대")]["normalized_value"],
            15_600_000.0,
        )
        self.assertEqual(
            sentence_values[("87.0", "만 대")]["normalized_value"],
            870_000.0,
        )
        self.assertTrue(
            all(item["normalized_unit"] == "COUNT" for item in sentence_values.values())
        )

    def test_candidate_catalog_preserves_distinct_aggregate_labels(self) -> None:
        catalog = build_semantic_candidate_catalog(
            [
                {
                    "candidate_id": "aggregate-total",
                    "source_anchor": "[sample | 2024 | section]",
                    "text": "source total row",
                    "candidate_kind": "structured_value",
                    "metadata": {
                        "year": 2024,
                        "row_label": "연구개발비용 총계",
                        "structured_cells": [
                            {"value_text": "1,010", "unit_hint": "백만원"}
                        ],
                    },
                },
                {
                    "candidate_id": "aggregate-net",
                    "source_anchor": "[sample | 2024 | section]",
                    "text": "source net row",
                    "candidate_kind": "structured_value",
                    "metadata": {
                        "year": 2024,
                        "row_label": "연구개발비용 계",
                        "structured_cells": [
                            {"value_text": "1,000", "unit_hint": "백만원"}
                        ],
                    },
                },
                {
                    "candidate_id": "non-aggregate",
                    "source_anchor": "[sample | 2024 | section]",
                    "text": "non-aggregate source row",
                    "candidate_kind": "structured_value",
                    "metadata": {
                        "year": 2024,
                        "row_label": "회계처리 비용",
                        "structured_cells": [
                            {"value_text": "900", "unit_hint": "백만원"}
                        ],
                    },
                }
            ]
        )
        aggregate_by_row = {
            item["row_label"]: item["aggregate_label"]
            for item in catalog
            if item["kind"] == "numeric"
        }
        self.assertEqual(aggregate_by_row["연구개발비용 총계"], "총계")
        self.assertEqual(aggregate_by_row["연구개발비용 계"], "계")
        self.assertEqual(aggregate_by_row["회계처리 비용"], "")

    def test_catalog_maps_fiscal_ordinals_to_value_year_and_source_scope(self) -> None:
        catalog = build_semantic_candidate_catalog(
            [
                {
                    "candidate_id": "chunk-scope::value:0",
                    "source_anchor": "[sample | 2023 | research]",
                    "text": "The following amounts are disclosed. 연결 누계기준입니다.",
                    "candidate_kind": "structured_value",
                    "metadata": {
                        "company": "sample",
                        "year": 2023,
                        "period_focus": "multi_period",
                        "row_label": "research total",
                        "table_source_id": "table-research",
                        "structured_cells": [
                            {
                                "column_headers": ["제55기"],
                                "value_text": "380",
                                "unit_hint": "개",
                            },
                            {
                                "column_headers": ["제54기"],
                                "value_text": "343",
                                "unit_hint": "개",
                            },
                        ],
                    },
                }
            ]
        )
        numeric = [item for item in catalog if item["kind"] == "numeric"]
        self.assertEqual([item["value_year"] for item in numeric], [2023, 2022])
        self.assertEqual([item["value_role"] for item in numeric], ["current", "prior"])
        self.assertTrue(
            all(item["consolidation_scope"] == "consolidated" for item in numeric)
        )
        self.assertTrue(
            all(
                item["consolidation_scope_source"] == "source_context"
                for item in numeric
            )
        )
        validation = validate_semantic_calculation_program(
            program={
                "status": "ready",
                "direct_bindings": [
                    {
                        "obligation_id": "current",
                        "candidate_id": numeric[0]["candidate_id"],
                    },
                    {
                        "obligation_id": "prior",
                        "candidate_id": numeric[1]["candidate_id"],
                    },
                ],
            },
            obligations=[
                _obligation(
                    "current",
                    "direct_value",
                    "current",
                    scope=_scope(
                        company="sample",
                        period="2023",
                        consolidation_scope="consolidated",
                    ),
                ),
                _obligation(
                    "prior",
                    "direct_value",
                    "prior",
                    scope=_scope(
                        company="sample",
                        period="2022",
                        consolidation_scope="consolidated",
                    ),
                ),
            ],
            candidate_catalog=numeric,
            query="Return the current and prior research totals.",
        )
        self.assertEqual(validation["status"], "ready")

    def test_structured_table_records_preserve_local_sibling_provenance(self) -> None:
        row_records = [
            {
                "row_label": "target venture",
                "row_headers": ["target venture"],
                "cells": [
                    {
                        "column_headers": ["ownership share"],
                        "value_text": "25.81",
                        "unit_hint": "%",
                    },
                    {
                        "column_headers": ["carrying value"],
                        "value_text": "1,294,367",
                        "unit_hint": "items",
                    },
                    {
                        "column_headers": ["net result"],
                        "value_text": "-803,742",
                        "unit_hint": "items",
                    },
                ],
            },
            {
                "row_label": "unrelated region",
                "row_headers": ["unrelated region"],
                "cells": [
                    {
                        "column_headers": ["ownership share"],
                        "value_text": "53",
                        "unit_hint": "%",
                    },
                    {
                        "column_headers": ["carrying value"],
                        "value_text": "637,681",
                        "unit_hint": "items",
                    },
                ],
            },
        ]
        value_records = [
            {
                "row_index": row_index,
                "column_index": column_index,
                "semantic_label": row["row_label"],
                "period_text": cell["column_headers"][0],
                "value_text": cell["value_text"],
                "unit_hint": cell["unit_hint"],
            }
            for row_index, row in enumerate(row_records)
            for column_index, cell in enumerate(row["cells"])
        ]
        base_metadata = {
            "chunk_uid": "sample:table:1",
            "company": "sample",
            "year": 2024,
            "is_table": True,
            "block_type": "table",
            "table_source_id": "sample table::1",
        }
        expected_local_cells = {
            ("target venture", ("ownership share",), "25.81"),
            ("target venture", ("carrying value",), "1,294,367"),
            ("target venture", ("net result",), "-803,742"),
            ("unrelated region", ("ownership share",), "53"),
            ("unrelated region", ("carrying value",), "637,681"),
        }

        for metadata_key, records, candidate_kind in (
            ("table_row_records_json", row_records, "structured_row"),
            ("table_value_records_json", value_records, "structured_value"),
        ):
            with self.subTest(metadata_key=metadata_key):
                metadata = {**base_metadata, metadata_key: json.dumps(records)}
                first_catalog = _catalog_from_document(
                    "The table body is available through immutable structured records.",
                    metadata,
                )
                second_catalog = _catalog_from_document(
                    "The table body is available through immutable structured records.",
                    metadata,
                )
                numeric = [
                    item
                    for item in first_catalog
                    if item.get("kind") == "numeric"
                    and item.get("candidate_kind") == candidate_kind
                ]
                local_cells = {
                    (
                        item.get("row_label"),
                        tuple(item.get("column_headers") or []),
                        item.get("raw_value"),
                    )
                    for item in numeric
                }

                self.assertEqual(local_cells, expected_local_cells)
                self.assertNotIn(
                    ("target venture", ("ownership share",), "53"),
                    local_cells,
                )
                self.assertNotIn(
                    ("unrelated region", ("net result",), "-803,742"),
                    local_cells,
                )
                self.assertEqual(
                    {
                        item["candidate_id"]
                        for item in numeric
                    },
                    {
                        item["candidate_id"]
                        for item in second_catalog
                        if item.get("kind") == "numeric"
                        and item.get("candidate_kind") == candidate_kind
                    },
                )
                self.assertTrue(
                    all(
                        str(item.get("source_candidate_id") or "").startswith("table_")
                        and "::row_" in str(item.get("source_candidate_id") or "")
                        for item in numeric
                    )
                )

    def test_repeated_table_bundle_uses_one_candidate_per_physical_cell(self) -> None:
        table_source_id = "sample section::table:7"
        row_records = [
            {
                "row_id": "2:0",
                "row_label": "target entity",
                "row_headers": ["region", "target entity"],
                "cells": [
                    {
                        "cell_id": "2:0:2",
                        "column_index": 2,
                        "column_headers": ["current period", "ownership share"],
                        "value_text": "26",
                        "unit_hint": "%",
                    }
                ],
            },
            {
                "row_id": "2:1",
                "row_label": "other entity",
                "row_headers": ["region", "other entity"],
                "cells": [
                    {
                        "cell_id": "2:1:2",
                        "column_index": 2,
                        "column_headers": ["current period", "ownership share"],
                        "value_text": "53",
                        "unit_hint": "%",
                    }
                ],
            },
        ]
        value_records = [
            {
                "value_id": f"{table_source_id}:v:{row_index}:2",
                "row_index": row_index,
                "column_index": 2,
                "semantic_label": row["row_label"],
                "row_label": row["row_label"],
                "row_headers": row["row_headers"],
                "column_headers": ["current period", "ownership share"],
                "period_text": "current period",
                "value_text": row["cells"][0]["value_text"],
                "unit_hint": "%",
                "value_role": "detail",
                "aggregation_stage": "none",
            }
            for row_index, row in enumerate(row_records)
        ]

        def build(order):
            docs = []
            for chunk_uid in order:
                docs.append(
                    (
                        SimpleNamespace(
                            page_content=(
                                "PARENT TABLE BODY target entity 26% other entity 53% "
                                "unrelated material must not be copied into every row."
                            ),
                            metadata={
                                "chunk_uid": chunk_uid,
                                "company": "document company",
                                "year": 2024,
                                "is_table": True,
                                "block_type": "table",
                                "table_source_id": table_source_id,
                                "table_header_context": "entity | current period ownership share",
                                "table_row_records_json": json.dumps(row_records),
                                "table_value_records_json": json.dumps(value_records),
                            },
                        ),
                        0.0,
                    )
                )
            source_state = {"retrieved_docs": docs}
            sources = build_semantic_source_candidates(
                source_state,
                source_anchor_builder=lambda item: f"[{item.get('chunk_uid')}]",
            )
            return source_state, sources, build_semantic_candidate_catalog(sources)

        first_state, first_sources, first_catalog = build(["chunk-b", "chunk-a"])
        _second_state, second_sources, second_catalog = build(["chunk-a", "chunk-b"])
        first_numeric = [
            item
            for item in first_catalog
            if item.get("kind") == "numeric"
            and item.get("candidate_kind") == "structured_row"
        ]
        second_numeric = [
            item
            for item in second_catalog
            if item.get("kind") == "numeric"
            and item.get("candidate_kind") == "structured_row"
        ]

        self.assertEqual(
            len(
                [
                    item
                    for item in first_sources
                    if item.get("candidate_kind") == "structured_row"
                ]
            ),
            2,
        )
        self.assertEqual(len(first_numeric), 2)
        self.assertEqual(
            {item["candidate_id"] for item in first_numeric},
            {item["candidate_id"] for item in second_numeric},
        )
        self.assertEqual(
            semantic_candidate_catalog_fingerprint(first_catalog),
            semantic_candidate_catalog_fingerprint(second_catalog),
        )
        target = next(item for item in first_numeric if item["raw_value"] == "26")
        self.assertEqual(target["physical_table_id"], table_source_id)
        self.assertEqual(target["physical_row_id"], "2:0")
        self.assertEqual(target["physical_cell_id"], "2:0:2")
        self.assertEqual(
            target["physical_value_id"],
            f"{table_source_id}:v:0:2",
        )
        self.assertEqual(target["row_headers"], ["region", "target entity"])
        self.assertEqual(
            target["local_entity_surfaces"],
            ["target entity", "region"],
        )
        self.assertNotIn("other entity 53", target["source_text"])
        self.assertNotIn("unrelated material", target["source_text"])
        diagnostics = semantic_candidate_stage_diagnostics(
            state=first_state,
            source_candidates=first_sources,
            catalog=first_catalog,
            prompt_catalog=first_catalog,
        )
        self.assertEqual(
            diagnostics["physical_deduplication"],
            {
                "structured_table_attachment_count": 2,
                "attached_physical_cell_projection_count": 4,
                "unique_physical_cell_candidate_count": 2,
                "duplicate_physical_cell_projection_count": 2,
            },
        )

    def test_canonical_operand_projection_resolves_local_unit_and_current_period(self) -> None:
        fixture = _contract_residual_fixture()["canonical_operand_projection"]
        expected = fixture["expected_after_repair"]
        catalog = build_semantic_candidate_catalog([fixture["source_candidate"]])
        numeric = {
            tuple(item.get("column_headers") or []): item
            for item in catalog
            if item.get("kind") == "numeric"
        }
        share = numeric[("ownership share",)]
        amount = numeric[("carrying amount",)]

        self.assertEqual(share["candidate_id"], expected["share_candidate_id"])
        self.assertEqual(amount["candidate_id"], expected["amount_candidate_id"])
        self.assertEqual(share["raw_value"], expected["share_raw_value"])
        self.assertEqual(share["raw_unit"], expected["share_raw_unit"])
        self.assertEqual(
            share["source_unit_hint"], expected["share_source_unit_hint"]
        )
        self.assertEqual(
            share["raw_unit_source"], expected["share_raw_unit_source"]
        )
        self.assertEqual(
            share["normalized_unit"], expected["share_normalized_unit"]
        )
        self.assertEqual(amount["raw_unit"], expected["amount_raw_unit"])
        self.assertEqual(
            amount["raw_unit_source"], expected["amount_raw_unit_source"]
        )
        self.assertEqual(
            amount["normalized_unit"], expected["amount_normalized_unit"]
        )
        self.assertEqual(
            [share["period"], amount["period"]],
            [expected["period"], expected["period"]],
        )
        self.assertEqual(
            [share["value_year"], amount["value_year"]],
            [expected["value_year"], expected["value_year"]],
        )
        self.assertEqual(
            [share["period_source"], amount["period_source"]],
            [expected["period_source"], expected["period_source"]],
        )
        self.assertEqual(
            [share["source_period_surface"], amount["source_period_surface"]],
            ["ownership share", "carrying amount"],
        )

        execution = execute_semantic_calculation_program(
            program={
                "status": "ready",
                "direct_bindings": [
                    {
                        "obligation_id": "ob_share",
                        "candidate_id": share["candidate_id"],
                    },
                    {
                        "obligation_id": "ob_amount",
                        "candidate_id": amount["candidate_id"],
                    },
                ],
                "expressions": [],
                "narrative_bindings": [],
                "missing_obligation_ids": [],
                "ambiguous_obligation_ids": [],
            },
            obligations=fixture["obligations"],
            candidate_catalog=catalog,
            query=fixture["query"],
        )

        self.assertEqual(execution["status"], "ok")
        outputs = {
            item["obligation_id"]: item for item in execution["outputs"]
        }
        operands = {
            item["candidate_id"]: item
            for item in execution["calculation_operands"]
        }
        self.assertEqual(outputs["ob_share"]["subject"], expected["subject"])
        self.assertEqual(outputs["ob_amount"]["subject"], expected["subject"])
        self.assertEqual(operands[share["candidate_id"]]["label"], "target venture ownership share")
        self.assertEqual(operands[amount["candidate_id"]]["label"], "target venture carrying amount")
        self.assertEqual(operands[share["candidate_id"]]["row_label"], "region")
        self.assertEqual(operands[share["candidate_id"]]["subject"], expected["subject"])
        self.assertEqual(
            operands[share["candidate_id"]]["subject_source"],
            "candidate_row_identity",
        )

    def test_pipe_table_rows_preserve_local_value_association_without_structured_metadata(self) -> None:
        catalog = _catalog_from_document(
            "\n".join(
                [
                    (
                        "entity | opening balance | opening balance | closing balance | "
                        "closing balance | latest result"
                    ),
                    (
                        "entity | ownership share | carrying value | ownership share | "
                        "carrying value | net result"
                    ),
                    "target venture | 25.92% | 700,691 | 25.81% | 1,294,367 | -803,742",
                    "unrelated region | 53% | 637,681 | 50% | 9,413 | 120",
                ]
            ),
            {
                "chunk_uid": "sample:legacy-table:1",
                "company": "sample",
                "year": 2024,
                "is_table": True,
                "block_type": "table",
                "unit_hint": "items",
                "table_source_id": "sample legacy table::1",
                "table_header_context": "\n".join(
                    [
                        (
                            "entity | opening balance | opening balance | "
                            "closing balance | closing balance | latest result"
                        ),
                        (
                            "entity | ownership share | carrying value | "
                            "ownership share | carrying value | net result"
                        ),
                    ]
                ),
            },
        )
        local_cells = {
            (
                item.get("row_label"),
                tuple(item.get("column_headers") or []),
                item.get("raw_value"),
            )
            for item in catalog
            if item.get("kind") == "numeric"
            and item.get("candidate_kind") == "table_row"
        }

        self.assertIn(
            (
                "target venture",
                ("opening balance", "ownership share"),
                "25.92",
            ),
            local_cells,
        )
        self.assertIn(
            (
                "target venture",
                ("closing balance", "ownership share"),
                "25.81",
            ),
            local_cells,
        )
        self.assertIn(
            (
                "target venture",
                ("closing balance", "carrying value"),
                "1,294,367",
            ),
            local_cells,
        )
        self.assertIn(
            ("target venture", ("latest result", "net result"), "-803,742"),
            local_cells,
        )
        self.assertNotIn(
            ("target venture", ("opening balance", "ownership share"), "53"),
            local_cells,
        )

    def test_flattened_table_summary_is_not_binding_authority(self) -> None:
        fixture = _contract_residual_fixture()["candidate_admission"]
        source_metadata = fixture["source_candidates"][0]["metadata"]
        catalog = build_semantic_candidate_catalog(
            fixture["source_candidates"],
            relevance_texts=fixture["relevance_texts"],
        )
        raw_values = {
            str(item.get("raw_value") or "")
            for item in catalog
            if item.get("kind") == "numeric"
        }
        expected = fixture["expected_current"]

        for raw_value in expected["present_raw_values"]:
            self.assertIn(raw_value, raw_values)
        for raw_value in expected["missing_raw_values"]:
            self.assertIn(raw_value, source_metadata["table_value_labels_text"])
            self.assertNotIn(raw_value, raw_values)

    def test_sentence_value_context_does_not_split_at_decimal_points(self) -> None:
        fixture = _contract_residual_fixture()["candidate_admission"][
            "required_input_prompt_coverage"
        ]["decimal_pair_context"]
        catalog = _catalog_from_document(
            fixture["text"],
            {"chunk_uid": fixture["source_id"]},
        )
        target = next(
            item
            for item in catalog
            if item.get("kind") == "numeric"
            and item.get("raw_value") == fixture["target_value"]
        )

        self.assertEqual(target["source_text"], fixture["expected_context"])
        selected = select_semantic_prompt_candidates(
            catalog,
            relevance_groups=[[fixture["required_surface"]]],
            required_numeric_relevance_groups=[
                [fixture["required_surface"]]
            ],
            max_numeric_candidates=2,
            max_narrative_candidates=0,
            max_required_candidates_per_group=2,
        )

        self.assertIn(
            target["candidate_id"],
            {item["candidate_id"] for item in selected},
        )

    def test_direct_binding_accepts_subject_from_structured_same_row_header(self) -> None:
        fixture = _contract_residual_fixture()["direct_binding"]["subject_identity"]
        catalog = build_semantic_candidate_catalog(
            [fixture["same_row_source_candidate"]]
        )
        numeric_candidates = [item for item in catalog if item["kind"] == "numeric"]
        self.assertEqual(len(numeric_candidates), 1)
        candidate = numeric_candidates[0]
        expected = fixture["same_row_expected"]

        self.assertEqual(candidate.get("row_headers"), expected["row_headers"])
        execution = execute_semantic_calculation_program(
            program={
                "status": "ready",
                "direct_bindings": [
                    {
                        "obligation_id": "ob_share",
                        "candidate_id": candidate["candidate_id"],
                    }
                ],
            },
            obligations=fixture["obligations"],
            candidate_catalog=catalog,
            query=fixture["query"],
        )

        self.assertEqual(execution["status"], expected["status"])
        self.assertEqual(
            execution["outputs_by_obligation"]["ob_share"]["rendered_value"],
            expected["rendered_value"],
        )


if __name__ == "__main__":
    unittest.main()
