# Routing Confusion Check

## Summary

- Canonical file: `benchmarks\golden\query_routing_canonical_v2.json`
- Cases: `12`
- Final intent accuracy: `1.000`
- Final format accuracy: `1.000`
- Routing source accuracy: `1.000`
- Semantic top-1 accuracy: `0.917`
- Fast-path count: `10`
- Fallback count: `2`

## Case Results

| Case | Expected Intent | Final Intent | Expected Source | Final Source | Semantic Top-1 | Pass | Query |
| --- | --- | --- | --- | --- | --- | --- | --- |
| conf_risk_001 | risk | risk | semantic_fast_path | semantic_fast_path | risk | yes | 주요 재무 리스크는 무엇인가요? |
| conf_risk_002 | risk | risk | semantic_fast_path | semantic_fast_path | risk | yes | 사업보고서에서 위험관리 항목을 요약해줘. |
| conf_overview_001 | business_overview | business_overview | - | semantic_fast_path | business_overview | yes | 회사가 영위하는 주요 사업은 무엇인가요? |
| conf_overview_002 | business_overview | business_overview | semantic_fast_path | semantic_fast_path | business_overview | yes | 삼성전자는 어떤 제품과 서비스를 제공하나요? |
| conf_numeric_001 | numeric_fact | numeric_fact | semantic_fast_path | semantic_fast_path | numeric_fact | yes | 각 부문별 매출 비중은 어떻게 되나요? |
| conf_numeric_002 | numeric_fact | numeric_fact | semantic_fast_path | semantic_fast_path | numeric_fact | yes | 사업부문 간 내부거래 규모는 얼마인가요? |
| conf_numeric_003 | numeric_fact | numeric_fact | llm_fallback | llm_fallback | comparison | yes | 삼성전자의 2024년 매출액은 숫자 말고 줄글로 길게 설명해줘. |
| conf_overview_003 | business_overview | business_overview | llm_fallback | llm_fallback | business_overview | yes | 주요 사업을 설명하되 숫자는 빼고 말해줘. |
| conf_comparison_001 | comparison | comparison | semantic_fast_path | semantic_fast_path | comparison | yes | DX와 DS 부문의 매출 차이는 얼마인가요? |
| conf_trend_001 | trend | trend | semantic_fast_path | semantic_fast_path | trend | yes | 최근 3년 영업이익 추이는 어떻게 변했나요? |
| conf_qa_001 | qa | qa | semantic_fast_path | semantic_fast_path | qa | yes | 삼성전자의 설립일은 언제인가요? |
| conf_numeric_004 | numeric_fact | numeric_fact | semantic_fast_path | semantic_fast_path | numeric_fact | yes | 영업이익률은 몇 퍼센트인가요? |
