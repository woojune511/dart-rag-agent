import unittest
from pathlib import Path

from src.config.runtime_contract import CALCULATION_DEBUG_TRACE_FIELD


class CalculationDebugTraceContractTests(unittest.TestCase):
    def test_calculation_module_uses_scratch_helpers_for_debug_trace_field(self) -> None:
        source = Path("src/agent/financial_graph_calculation.py").read_text(encoding="utf-8")

        self.assertIn("_calculation_debug_state_update", source)
        self.assertIn("_clear_calculation_debug_state", source)
        self.assertIn("CALCULATION_DEBUG_TRACE_FIELD", source)
        self.assertNotIn(f'"{CALCULATION_DEBUG_TRACE_FIELD}"', source)


if __name__ == "__main__":
    unittest.main()
