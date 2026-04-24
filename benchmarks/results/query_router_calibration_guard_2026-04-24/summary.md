# Query Router Calibration

## Summary

- Current threshold: `score >= 0.86`, `margin >= 0.04`
- Current fast-path coverage: `0.767`
- Current fast-path accuracy: `1.000`
- Recommended threshold: `score >= 0.76`, `margin >= 0.04`
- Recommended fast-path coverage: `0.867`
- Recommended fast-path accuracy: `1.000`

## Ambiguous Queries

| Query ID | True Intent | Top-1 | Score | Top-2 | Margin | Query |
| --- | --- | --- | ---: | --- | ---: | --- |
| route_eval_002 | numeric_fact | comparison | 0.852 | numeric_fact | 0.014 | 삼성전자의 영업이익률은 몇 %로 봐야 해? |
| route_eval_024 | trend | comparison | 0.846 | trend | 0.021 | 설비투자 규모가 최근 몇 년 동안 어떻게 변했지? |
| route_eval_020 | comparison | comparison | 0.864 | numeric_fact | 0.049 | 두 부문 중 어느 쪽 매출이 더 큰지 알려줘. |
| route_eval_022 | trend | trend | 0.933 | comparison | 0.077 | 전년 대비 매출 성장세가 어떻게 달라졌는지 보고 싶어. |
| route_eval_004 | numeric_fact | trend | 0.602 | numeric_fact | 0.106 | 설비투자 금액은 얼마인지 보고 싶어. |
| route_eval_009 | business_overview | business_overview | 0.885 | risk | 0.107 | 삼성전자의 사업 포트폴리오를 간단히 정리해줘. |
| route_eval_003 | numeric_fact | numeric_fact | 0.906 | comparison | 0.112 | 부문별 매출 비중을 숫자로 알려줘. |
| route_eval_016 | comparison | comparison | 0.984 | business_overview | 0.152 | DX와 DS 가운데 매출이 얼마나 차이 나? |
| route_eval_017 | comparison | comparison | 0.788 | trend | 0.154 | 올해와 작년 연구개발비 차이를 비교해줘. |
| route_eval_008 | business_overview | business_overview | 0.863 | qa | 0.156 | 이 회사는 어떤 고객과 시장을 대상으로 사업하나? |

## Current Threshold Misroutes

| Query ID | True Intent | Predicted | Score | Margin | Query |
| --- | --- | --- | ---: | ---: | --- |
| - | - | - | - | - | No fast-path misroutes at current threshold |
