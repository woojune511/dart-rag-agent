import unittest

from src.agent.financial_text_surface import (
    narrative_sentence_looks_abbreviated_fragment,
    narrative_sentence_looks_table_noisy,
    polish_korean_particle_pairs,
    split_narrative_sentences,
    topic_particle,
)


class FinancialTextSurfaceTests(unittest.TestCase):
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
