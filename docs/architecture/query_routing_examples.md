# Query Routing Few-Shot Examples v1

이 문서는 `_classify_query`를 zero-shot에서 few-shot 기반으로 옮길 때 사용할 edge case 예제 초안을 정리한다.

목표는 다음과 같다.

- `risk`가 `numeric_fact`로 흔들리는 문제 방지
- `business_overview`가 숫자형 질문과 뒤섞이는 문제 방지
- `comparison`, `trend`를 더 안정적으로 분리

## 사용 원칙

- 예제는 “정말 자주 헷갈리는 질문” 위주로 적는다
- 각 예제에는 최소한
  - `intent`
  - `format_preference`
  를 같이 적는다
- 설명은 짧고 직접적으로 유지한다

## Few-shot 세트

### Risk

**Q:** 삼성전자의 주요 재무 리스크는 무엇인가요?  
**A:** `intent=risk`, `format_preference=paragraph`  
이유: 숫자나 금액이 아니라 리스크 항목 요약을 묻는다.

**Q:** 환율 위험 관리 방식은 어떻게 설명하나요?  
**A:** `intent=risk`, `format_preference=paragraph`  
이유: 위험 관리 설명형 질문이다.

**Q:** 사업보고서에서 유동성위험은 어떻게 정의하나요?  
**A:** `intent=risk`, `format_preference=paragraph`  
이유: 리스크 항목의 정의와 설명을 찾는 질문이다.

### Business Overview

**Q:** 회사가 영위하는 주요 사업은 무엇인가요?  
**A:** `intent=business_overview`, `format_preference=mixed`  
이유: 기업 구조와 사업 내용을 묻는 설명형 질문이다.

**Q:** 삼성전자는 어떤 제품과 서비스를 제공하나요?  
**A:** `intent=business_overview`, `format_preference=mixed`  
이유: 제품/서비스 개요를 묻는다.

**Q:** 삼성전자는 몇 개의 종속기업으로 구성된 글로벌 전자 기업이라고 설명하나요?  
**A:** `intent=business_overview`, `format_preference=mixed`  
이유: 숫자가 있지만 핵심은 기업 구조 설명이다.

**Q:** 삼성전자의 연결대상 종속기업은 총 몇 개인가요?  
**A:** `intent=business_overview`, `format_preference=mixed`  
이유: '몇 개'를 묻지만 재무 실적 수치가 아니라 기업 구조와 연결 범위를 묻는다.

### Numeric Fact

**Q:** 삼성전자의 연결 기준 매출액은 얼마인가요?  
**A:** `intent=numeric_fact`, `format_preference=table`  
이유: 핵심은 단일 금액 수치다.

**Q:** 각 부문별 매출 비중은 어떻게 되나요?  
**A:** `intent=numeric_fact`, `format_preference=table`  
이유: 부문 설명이 아니라 비중 수치를 요구한다.

**Q:** 사업부문 간 내부거래 규모는 얼마인가요?  
**A:** `intent=numeric_fact`, `format_preference=table`  
이유: 최종 답은 금액/규모 수치다.

### Comparison

**Q:** DX와 DS 부문의 매출 차이는 얼마인가요?  
**A:** `intent=comparison`, `format_preference=table`  
이유: 두 항목 간 수치 비교다.

**Q:** 삼성전자와 SK하이닉스의 영업이익을 비교해줘.  
**A:** `intent=comparison`, `format_preference=table`  
이유: 두 기업 간 비교 질문이다.

### Trend

**Q:** 최근 3년 영업이익 추이는 어떻게 변했나요?  
**A:** `intent=trend`, `format_preference=table`  
이유: 시계열 변화 질문이다.

**Q:** 전년 대비 매출 성장률은 어떻게 바뀌었나요?  
**A:** `intent=trend`, `format_preference=table`  
이유: 성장률 변화 추세를 묻는다.

### QA

**Q:** 삼성전자의 설립일은 언제인가요?  
**A:** `intent=qa`, `format_preference=paragraph`  
이유: 일반 사실 질의다.

**Q:** 본사는 어디에 있나요?  
**A:** `intent=qa`, `format_preference=paragraph`  
이유: 단순 사실 질의다.

**Q:** 회사의 임직원 수는 총 몇 명인가요?  
**A:** `intent=qa`, `format_preference=paragraph`  
이유: 개수를 묻지만 재무 실적 수치가 아니라 기업 일반 정보 질의다.

## 프롬프트 주입 초안

```text
[Few-shot 예시]
Q: 삼성전자의 주요 재무 리스크는 무엇인가요?
A: intent=risk, format_preference=paragraph

Q: 회사가 영위하는 주요 사업은 무엇인가요?
A: intent=business_overview, format_preference=mixed

Q: 삼성전자의 연결대상 종속기업은 총 몇 개인가요?
A: intent=business_overview, format_preference=mixed

Q: 각 부문별 매출 비중은 어떻게 되나요?
A: intent=numeric_fact, format_preference=table

Q: 회사의 임직원 수는 총 몇 명인가요?
A: intent=qa, format_preference=paragraph

Q: DX와 DS 부문의 매출 차이는 얼마인가요?
A: intent=comparison, format_preference=table

Q: 최근 3년 영업이익 추이는 어떻게 변했나요?
A: intent=trend, format_preference=table
```

## 선택 기준

초기 few-shot은 6~10개 정도로 시작하는 것이 좋다.

우선순위:

1. `risk` vs `numeric_fact`
2. `business_overview` vs `numeric_fact`
3. `comparison` vs `numeric_fact`
4. `trend` vs `numeric_fact`

즉, 가장 큰 목적은 `numeric_fact`로 과하게 빨려 들어가는 질문들을 안정적으로 분리하는 것이다.
