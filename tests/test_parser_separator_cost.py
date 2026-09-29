"""Separator language stays unchanged without nested zero-space repetition."""
import itertools
import re
import subprocess
import sys
import unittest
from src.processing.financial_parser import _INLINE_BODY_SEPARATOR_RE


class ParserSeparatorCostTests(unittest.TestCase):
    def test_short_separator_spans_and_captures_match_previous_pattern(self):
        old = re.compile(r'([①②③④⑤⑥⑦⑧⑨⑩]|-\s*[A-Za-z가-힣&]+(?:\s*[A-Za-z가-힣&]+)*\s*:)')
        inputs = [''.join(parts) for n in range(5) for parts in itertools.product('A가& :', repeat=n)]
        inputs += ['Camera Module', '가나다 라마바', 'A\tB', 'A\nB', '① example', '⑩ last']
        for s in inputs:
            for text in (s, '-'+s, '- '+s+': tail'):
                a = [(m.span(), m.groups()) for m in old.finditer(text)]
                b = [(m.span(), m.groups()) for m in _INLINE_BODY_SEPARATOR_RE.finditer(text)]
                self.assertEqual(a, b, repr(text))

    def test_long_missing_colon_finishes_in_bounded_child_process(self):
        # Isolate a regression so the suite cannot hang inside Python's regex.
        code = "import re,sys; p=re.compile(sys.argv[1]); assert p.search('- '+'가나다라'*25000+'!') is None"
        result = subprocess.run([sys.executable, '-X', 'utf8', '-c', code, _INLINE_BODY_SEPARATOR_RE.pattern],
                                capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr.decode('utf8'))
