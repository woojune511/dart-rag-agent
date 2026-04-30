# Retrospective Experiment: Evaluator Sub-decisions Replay

## Setup

- Source bundle: `benchmarks\results\dev_math_focus_evalonly_datasetfix_2026-04-29\삼성전자-2024\results.json`
- Dataset: `benchmarks\eval_dataset.math_focus.json`
- Method: historical answer / runtime trace replay only. No agent rerun.

## Aggregate

| Decision | Question | Baseline | Proposed |
| --- | --- | ---: | ---: |
| 73 | comparison_001 | 0.0 | 1.0 |
| 75 | comparison_004 | 0.0 | 1.0 |
| 76 | trend_002 | 0.0 | 1.0 |
| 76 | comparison_005 | 0.0 | 1.0 |

## Per Case

### Decision 73 / comparison_001

- Title: `Strict numeric equivalence vs current display-aware equivalence`
- Note: Originally documented as a tolerance-only fix, but the durable current behavior is display-aware equivalence.
- Baseline `strict_equivalence`: `0.0`
- Proposed `current_display_aware_equivalence`: `1.0`
- Judgement: `FAIL` -> `PASS`

```json
{
  "baseline_debug": {
    "answer_candidates": [
      {
        "value_text": "63조 8,217억원",
        "unit_text": "원",
        "kind": "currency",
        "normalized_value": 63821700000000.0,
        "span": [
          40,
          51
        ]
      }
    ],
    "reference_candidates": [
      {
        "value_text": "174조 8,877억원",
        "unit_text": "원",
        "kind": "currency",
        "normalized_value": 174887700000000.0,
        "span": [
          15,
          27
        ]
      },
      {
        "value_text": "111조 659억원",
        "unit_text": "원",
        "kind": "currency",
        "normalized_value": 111065900000000.0,
        "span": [
          38,
          48
        ]
      },
      {
        "value_text": "63조 8,218억원",
        "unit_text": "원",
        "kind": "currency",
        "normalized_value": 63821800000000.0,
        "span": [
          67,
          78
        ]
      },
      {
        "value_text": "174조 8,877억원",
        "unit_text": "원",
        "kind": "currency",
        "normalized_value": 174887700000000.0,
        "span": [
          17,
          29
        ]
      },
      {
        "value_text": "58.1%",
        "unit_text": "%",
        "kind": "percent",
        "normalized_value": 58.1,
        "span": [
          30,
          35
        ]
      },
      {
        "value_text": "111조 659억원",
        "unit_text": "원",
        "kind": "currency",
        "normalized_value": 111065900000000.0,
        "span": [
          45,
          55
        ]
      },
      {
        "value_text": "36.9%",
        "unit_text": "%",
        "kind": "percent",
        "normalized_value": 36.9,
        "span": [
          56,
          61
        ]
      }
    ],
    "matched_pair": null,
    "reason": "no_equivalent_value"
  },
  "proposed_debug": {
    "answer_candidates": [
      {
        "value_text": "63조 8,217억원",
        "unit_text": "원",
        "kind": "currency",
        "normalized_value": 63821700000000.0,
        "span": [
          40,
          51
        ]
      }
    ],
    "reference_candidates": [
      {
        "value_text": "174조 8,877억원",
        "unit_text": "원",
        "kind": "currency",
        "normalized_value": 174887700000000.0,
        "span": [
          15,
          27
        ]
      },
      {
        "value_text": "111조 659억원",
        "unit_text": "원",
        "kind": "currency",
        "normalized_value": 111065900000000.0,
        "span": [
          38,
          48
        ]
      },
      {
        "value_text": "63조 8,218억원",
        "unit_text": "원",
        "kind": "currency",
        "normalized_value": 63821800000000.0,
        "span": [
          67,
          78
        ]
      },
      {
        "value_text": "174조 8,877억원",
        "unit_text": "원",
        "kind": "currency",
        "normalized_value": 174887700000000.0,
        "span": [
          17,
          29
        ]
      },
      {
        "value_text": "58.1%",
        "unit_text": "%",
        "kind": "percent",
        "normalized_value": 58.1,
        "span": [
          30,
          35
        ]
      },
      {
        "value_text": "111조 659억원",
        "unit_text": "원",
        "kind": "currency",
        "normalized_value": 111065900000000.0,
        "span": [
          45,
          55
        ]
      },
      {
        "value_text": "36.9%",
        "unit_text": "%",
        "kind": "percent",
        "normalized_value": 36.9,
        "span": [
          56,
          61
        ]
      }
    ],
    "matched_pair": {
      "answer": {
        "value_text": "63조 8,217억원",
        "unit_text": "원",
        "kind": "currency",
        "normalized_value": 63821700000000.0,
        "span": [
          40,
          51
        ]
      },
      "reference": {
        "value_text": "63조 8,218억원",
        "unit_text": "원",
        "kind": "currency",
        "normalized_value": 63821800000000.0,
        "span": [
          67,
          78
        ]
      }
    },
    "reason": "equivalent_value"
  }
}
```

### Decision 75 / comparison_004

- Title: `Legacy label matcher vs current label matcher`
- Note: Compare operand-selection scoring on the exact same historical operands.
- Baseline `legacy_label_match`: `0.0`
- Proposed `current_label_match`: `1.0`

```json
{
  "baseline_debug": {
    "expected_labels": [
      "2024년 영업이익",
      "2024년 매출"
    ],
    "actual_labels": [
      "2024년 연결 기준 매출액",
      "2024년 연결 기준 영업이익"
    ],
    "legacy_matches": [
      {
        "expected": "2024년 영업이익",
        "actual": "2024년 연결 기준 매출액",
        "match": false
      },
      {
        "expected": "2024년 영업이익",
        "actual": "2024년 연결 기준 영업이익",
        "match": false
      },
      {
        "expected": "2024년 매출",
        "actual": "2024년 연결 기준 매출액",
        "match": false
      },
      {
        "expected": "2024년 매출",
        "actual": "2024년 연결 기준 영업이익",
        "match": false
      }
    ]
  },
  "proposed_debug": {
    "current_matches": [
      {
        "expected": "2024년 영업이익",
        "actual": "2024년 연결 기준 매출액",
        "match": false
      },
      {
        "expected": "2024년 영업이익",
        "actual": "2024년 연결 기준 영업이익",
        "match": true
      },
      {
        "expected": "2024년 매출",
        "actual": "2024년 연결 기준 매출액",
        "match": true
      },
      {
        "expected": "2024년 매출",
        "actual": "2024년 연결 기준 영업이익",
        "match": false
      }
    ]
  }
}
```

### Decision 76 / trend_002

- Title: `Operand selection before override vs after override`
- Note: Tests the mathematically equivalent derivation-path override on a fixed historical row.
- Baseline `before_operand_override`: `0.0`
- Proposed `after_operand_override`: `1.0`

```json
{
  "baseline_debug": {
    "numeric_result_correctness": 1.0,
    "numeric_grounding": 1.0
  },
  "proposed_debug": {
    "numeric_result_correctness": 1.0,
    "numeric_grounding": 1.0
  }
}
```

### Decision 76 / comparison_005

- Title: `Operand selection before override vs after override (precomputed ratio path)`
- Note: Same override principle applied to a direct precomputed-ratio path.
- Baseline `before_operand_override`: `0.0`
- Proposed `after_operand_override`: `1.0`

```json
{
  "baseline_debug": {
    "numeric_result_correctness": 1.0,
    "numeric_grounding": 1.0
  },
  "proposed_debug": {
    "numeric_result_correctness": 1.0,
    "numeric_grounding": 1.0
  }
}
```
