import unittest

from src.ops.build_evidence_policy_audit import infer_row_policy


class BuildEvidencePolicyAuditTests(unittest.TestCase):
    def test_hybrid_row_splits_numeric_narrative_and_supporting(self) -> None:
        row = {
            "id": "NAV_T3_032",
            "question": "2023년 사업보고서에서 데이터센터 인프라 투자와 관련된 자본적 지출(CAPEX) 규모나 관련 주석 내용을 요약해.",
            "answer_type": "summary",
            "expected_refusal": False,
            "expected_sections": [
                "II. 사업의 내용 > 3. 원재료 및 생산설비",
                "II. 사업의 내용 > 7. 기타 참고사항",
                "III. 재무에 관한 사항 > 7. 증권의 발행을 통한 자금조달에 관한 사항 > 7-2. 증권의 발행을 통해 조달된 자금의 사용실적",
            ],
            "evidence": [
                {
                    "section_path": "II. 사업의 내용 > 3. 원재료 및 생산설비",
                    "quote": "CapEx | 692.3",
                    "why_it_supports_answer": "총 투자 규모를 보여준다.",
                },
                {
                    "section_path": "II. 사업의 내용 > 7. 기타 참고사항",
                    "quote": "2023년 3분기에 오픈한 각 세종",
                    "why_it_supports_answer": "운영 관련 설명이다.",
                },
                {
                    "section_path": "III. 재무에 관한 사항 > 7. 증권의 발행을 통한 자금조달에 관한 사항 > 7-2. 증권의 발행을 통해 조달된 자금의 사용실적",
                    "quote": "시설자금(데이터센터 건설) 200,000",
                    "why_it_supports_answer": "조달 자금 사용처를 보여준다.",
                },
            ],
        }

        audit = infer_row_policy(row)

        self.assertEqual(audit["doc_scope"], "single_report")
        self.assertEqual(audit["recommended_strategy"], "hybrid")
        self.assertEqual(audit["numeric_canonical_sections"], ["II. 사업의 내용 > 3. 원재료 및 생산설비"])
        self.assertEqual(audit["narrative_canonical_sections"], ["II. 사업의 내용 > 7. 기타 참고사항"])
        self.assertEqual(
            audit["supporting_sections"],
            ["III. 재무에 관한 사항 > 7. 증권의 발행을 통한 자금조달에 관한 사항 > 7-2. 증권의 발행을 통해 조달된 자금의 사용실적"],
        )

    def test_mixed_numeric_question_uses_narrative_for_cause(self) -> None:
        row = {
            "id": "KBF_T2_018",
            "question": "2023년 연결 포괄손익계산서 상의 신용손실충당금전입액 전년 대비 증가율을 계산하고, 그 원인을 리스크 관리 측면에서 요약해 줘.",
            "answer_type": "summary",
            "expected_refusal": False,
            "expected_sections": [
                "III. 재무에 관한 사항 > 1. 요약재무정보",
                "IV. 이사의 경영진단 및 분석의견",
            ],
            "evidence": [
                {
                    "section_path": "III. 재무에 관한 사항 > 1. 요약재무정보",
                    "quote": "신용손실충당금전입액 (3,146,409) (1,847,775) (1,185,133)",
                    "why_it_supports_answer": "비교 수치다.",
                },
                {
                    "section_path": "IV. 이사의 경영진단 및 분석의견",
                    "quote": "신용손실충당금전입액은 미래경기 불확실성에 대비한 보수적인 충당금적립으로 전년대비 1,299십억원 증가한 3조 146십억원 입니다.",
                    "why_it_supports_answer": "증가 배경을 설명한다.",
                },
                {
                    "section_path": "IV. 이사의 경영진단 및 분석의견",
                    "quote": "경기악화(worse) 시나리오와 위기상황(crisis) 시나리오 반영",
                    "why_it_supports_answer": "보수적 리스크 관리 배경이다.",
                },
            ],
        }

        audit = infer_row_policy(row)

        self.assertEqual(audit["recommended_strategy"], "hybrid")
        self.assertEqual(audit["numeric_canonical_sections"], ["III. 재무에 관한 사항 > 1. 요약재무정보"])
        self.assertEqual(audit["narrative_canonical_sections"], ["IV. 이사의 경영진단 및 분석의견"])
        self.assertEqual(audit["audit_flags"], [])

    def test_numeric_without_structured_quote_is_flagged(self) -> None:
        row = {
            "id": "NAV_T2_031",
            "question": "2023년 서치플랫폼 매출 대비 클라우드 부문 매출의 비율을 계산하고, 클라우드 부문의 주요 기술 적용 사례를 요약해 줘.",
            "answer_type": "summary",
            "expected_refusal": False,
            "expected_sections": [
                "IV. 이사의 경영진단 및 분석의견 > 3. 재무상태 및 영업실적 > 나. 영업실적",
                "II. 사업의 내용 > 7. 기타 참고사항",
            ],
            "evidence": [
                {
                    "section_path": "IV. 이사의 경영진단 및 분석의견 > 3. 재무상태 및 영업실적 > 나. 영업실적",
                    "quote": "2023년 서치플랫폼 매출은 전년 대비 0.6% 성장한 3조 5,891억 원",
                    "why_it_supports_answer": "비율 계산에 필요한 첫 번째 수치다.",
                },
                {
                    "section_path": "IV. 이사의 경영진단 및 분석의견 > 3. 재무상태 및 영업실적 > 나. 영업실적",
                    "quote": "클라우드 매출은 전년 대비 11.0% 성장한 4,472억원",
                    "why_it_supports_answer": "비율 계산에 필요한 두 번째 수치다.",
                },
                {
                    "section_path": "II. 사업의 내용 > 7. 기타 참고사항",
                    "quote": "초대규모 AI인 HyperCLOVA X를 필두로 시장을 선점하고 있으며",
                    "why_it_supports_answer": "기술 적용 사례다.",
                },
            ],
        }

        audit = infer_row_policy(row)

        self.assertIn("numeric_without_structured_quote", audit["audit_flags"])

    def test_refusal_row_is_marked_refusal_strategy(self) -> None:
        row = {
            "id": "X",
            "question": "문서에 없는 해외 경쟁사 수치를 비교해 줘.",
            "answer_type": "refusal",
            "expected_refusal": True,
            "expected_sections": [],
            "evidence": [],
        }

        audit = infer_row_policy(row)

        self.assertEqual(audit["recommended_strategy"], "refusal")
        self.assertFalse(audit["needs_numeric"])
        self.assertFalse(audit["needs_narrative"])


if __name__ == "__main__":
    unittest.main()
