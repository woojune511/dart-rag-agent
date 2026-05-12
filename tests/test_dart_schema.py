import json
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
for path in (PROJECT_ROOT, SRC_ROOT):
    path_text = str(path)
    if path_text not in sys.path:
        sys.path.insert(0, path_text)

from src.schema import ArtifactKind, ArtifactRecord, CellRecord, RowRecord, TableObject, TaskKind, TaskRecord, TaskStatus


class DartSchemaTests(unittest.TestCase):
    def test_table_object_round_trip(self):
        cell = CellRecord(
            cell_id="c1",
            column_index=1,
            column_headers=["2023년 12월말"],
            value_text="92,228,115",
            unit_hint="백만원",
            normalized_value=92228115000000.0,
            normalized_unit="KRW",
        )
        row = RowRecord(
            row_id="r1",
            row_label="부채총계",
            row_headers=["부채총계"],
            cells=[cell],
        )
        table = TableObject(
            table_id="tbl_001",
            source_section_path="III. 재무에 관한 사항 > 1. 요약재무정보",
            statement_type="summary_financials",
            consolidation_scope="consolidated",
            unit_hint="백만원",
            period_labels=["2023"],
            period_focus="current",
            row_count=1,
            column_count=2,
            rows=[row],
            table_header_context="구 분 | 2023년 12월말",
            table_summary_text="요약재무정보 | 부채총계",
        )
        restored = TableObject.model_validate_json(table.model_dump_json())
        self.assertEqual(restored.table_id, "tbl_001")
        self.assertEqual(restored.rows[0].cells[0].normalized_unit, "KRW")

    def test_task_and_artifact_schema(self):
        task = TaskRecord(
            task_id="t1",
            kind=TaskKind.CALCULATION,
            label="부채비율 계산",
            status=TaskStatus.PENDING,
            query="부채비율을 계산해 줘.",
        )
        artifact = ArtifactRecord(
            artifact_id="a1",
            task_id="t1",
            kind=ArtifactKind.CALCULATION_PLAN,
            status="ok",
            summary="ratio plan",
            payload={"formula": "(A / B) * 100"},
            evidence_refs=["ev_001"],
        )
        self.assertEqual(task.kind, TaskKind.CALCULATION)
        self.assertEqual(artifact.kind, ArtifactKind.CALCULATION_PLAN)
        self.assertEqual(json.loads(artifact.model_dump_json())["payload"]["formula"], "(A / B) * 100")


if __name__ == "__main__":
    unittest.main()
