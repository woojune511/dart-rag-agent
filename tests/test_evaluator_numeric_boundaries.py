"""Quantity-token boundaries must not create or hide numeric answer claims."""

import unittest

from src.ops.evaluator import _compute_numeric_equivalence, _extract_numeric_candidates


class EvaluatorNumericBoundaryTests(unittest.TestCase):
    def test_count_units_inside_following_words_are_not_quantities(self):
        for text in (
            "2023 명목순이자마진(NIM)", "2022명목순이자마진(NIM)",
            "3 개발 계획", "4개별 항목", "5 명칭 변경", "6명세서",
            "7 곳곳의 현황", "8개월", "9명name", "10개_code",
        ):
            with self.subTest(text=text):
                self.assertEqual(_extract_numeric_candidates(text), [])

    def test_actual_counts_remain_visible_with_spacing_and_punctuation(self):
        for unit in ("명", "개", "곳"):
            for space in ("", " "):
                for ending in ("", ".", ", 다음", ")", " / 다음", "\n"):
                    text = f"수량: 2,023{space}{unit}{ending}"
                    with self.subTest(text=text):
                        rows = _extract_numeric_candidates(text)
                        self.assertEqual(len(rows), 1)
                        self.assertEqual(rows[0]["normalized_value"], 2023.0)
                        self.assertEqual(rows[0]["kind"], "count")
                        self.assertEqual(rows[0]["unit_text"], unit)

    def test_postpositions_and_copulas_do_not_hide_real_counts(self):
        for suffix in (
            "은", "는", "이", "가", "을", "를", "의", "와", "과", "도", "만",
            "으로", "로", "에", "에게", "에서", "에게서", "부터", "까지", "보다",
            "처럼", "만큼", "씩", "당", "뿐", "이나", "입니다", "이다", "이며",
            "이고", "이면", "인데", "이지만", "이었다", "이었습니다", "인",
            "이라고", "이라는", "이라서", "이라면", "이라도", "이므로", "이어서", "이든지",
            "으로는", "에게만", "부터는", "입니다만", "가량", "정도", "내외",
        ):
            text = f"참여자는 7명{suffix} 확인했습니다."
            with self.subTest(suffix=suffix):
                rows = _extract_numeric_candidates(text)
                self.assertEqual([row["value_text"] for row in rows], ["7명"])
        for text in ("3개를 선택", "4곳에서는 운영", "5개당 배분"):
            with self.subTest(text=text):
                self.assertEqual(len(_extract_numeric_candidates(text)), 1)

    def test_value_span_sign_and_precision_are_unchanged(self):
        for value, normalized in (("(1,234)", -1234.0), ("-12", -12.0), ("0", 0.0), ("1.50", 1.5)):
            text = f"수량 {value} 명으로 집계"
            with self.subTest(value=value):
                row, = _extract_numeric_candidates(text)
                self.assertEqual(row["normalized_value"], normalized)
                self.assertEqual(row["value_text"], f"{value} 명")
                start, end = row["span"]
                self.assertEqual(text[start:end], row["value_text"])

    def test_period_then_label_does_not_invent_headcounts(self):
        # Minimal form of the saved full-agent answer; no answer rewriting is needed.
        answer = "입력값은 2023 명목순이자마진(NIM) 1.83%, 2022 명목순이자마진(NIM) 1.73%이며 차이는 0.10%p입니다."
        score, debug = _compute_numeric_equivalence(
            answer, "2023년 1.83%, 2022년 1.73%, 차이 0.10%p", [],
        )
        self.assertEqual(score, 1.0)
        self.assertEqual(debug["unsupported_answer_candidates"], [])
        self.assertEqual([row["kind"] for row in debug["answer_candidates"]], ["percent"] * 3)

    def test_unsupported_real_counts_still_fail(self):
        for suffix in ("", "입니다", "으로는", "에게만", "이었다", "정도", "이라고", "이므로"):
            score, debug = _compute_numeric_equivalence(
                f"비율은 1.83%입니다. 참여자는 7명{suffix} 확인했습니다.", "비율은 1.83%", [],
            )
            with self.subTest(suffix=suffix):
                self.assertEqual(score, 0.0)
                self.assertEqual(debug["reason"], "unsupported_answer_numeric_claim")
                self.assertEqual([row["value_text"] for row in debug["unsupported_answer_candidates"]], ["7명"])

    def test_supported_counts_and_changed_numbers_keep_existing_verdicts(self):
        cases = (
            ("참여자는 7명입니다.", "참여자 7명", 1.0),
            ("참여자는 8명입니다.", "참여자 7명", 0.0),
            ("2023 명목 비율은 2.83%입니다.", "비율 1.83%", 0.0),
        )
        for answer, reference, expected in cases:
            with self.subTest(answer=answer):
                score, _ = _compute_numeric_equivalence(answer, reference, [])
                self.assertEqual(score, expected)


if __name__ == "__main__":
    unittest.main()
