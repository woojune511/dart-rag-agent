"""Reviewed intent examples, kept separate from routing control flow.

Examples describe generic question operations, not particular filing answers.
The canonical embedding dataset is a separate, unchanged source artifact.
"""


QUERY_ROUTING_PROMPT = """다음 기업 공시 질문을 `intent`와 `format_preference`로 분류하세요.

intent 정의:
- numeric_fact : 문서에 수치가 직접 기재되어 있어 조회만으로 답할 수 있는 질의. 계산 없이 단일 숫자를 찾으면 됨.
- business_overview : 사업 구조·주요 제품·서비스·고객군·사업 부문 구성 등 기업 개요를 묻는 질의.
- risk : 리스크 요인·위험 관리 방식·파생거래 등을 묻는 질의.
- comparison : 두 수치를 더하거나 빼거나 나눠서 계산해야 답할 수 있는 질의. 합계·차이·비중·이익률 계산 포함.
- trend : 시계열 변화·추이·성장률·전년 대비 변화를 묻는 질의.
- qa : 위 유형에 해당하지 않는 일반 사실·설명 질의.

[핵심 구분 규칙]
- 두 항목을 더한 합계 → comparison
- 두 수치를 나눠 비중·비율·이익률을 계산 → comparison
- 문서에 수치가 이미 기재된 단일 값 조회 → numeric_fact

format_preference 정의:
- table : 표 기반 수치 근거를 우선해야 함
- paragraph : 설명 문단 근거를 우선해야 함
- mixed : 표와 문단을 함께 볼 수 있음

[Few-shot 예시]
Q: 보고서가 식별한 위험 요인과 대응 방식을 설명해 주세요.
A: intent=risk, format_preference=paragraph

Q: 회사의 사업 구조와 주요 제품 및 서비스를 설명해 주세요.
A: intent=business_overview, format_preference=mixed

Q: 원문에 제시된 항목 A의 수량은 얼마인가요?
A: intent=numeric_fact, format_preference=table

Q: 항목 A와 항목 B의 값 차이를 계산해 주세요.
A: intent=comparison, format_preference=table

Q: 최근 세 보고기간에 걸친 항목 A의 변화를 설명해 주세요.
A: intent=trend, format_preference=table

Q: 보고서에서 용어 A를 어떻게 정의하나요?
A: intent=qa, format_preference=paragraph

참고 semantic prior:
- top_intent: {semantic_intent}
- semantic_confidence: {semantic_confidence}

질문: {query}"""
