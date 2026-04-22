# Compact Review - 삼성전자-2024

## contextual_all_2500_320

### q_001 | single-hop-fact

질문: 2024년 삼성전자의 연결 기준 매출액은 얼마인가?
예시 답변: 2024년 삼성전자의 연결 기준 매출은 300조 8,709억원이다.
실제 답변: 2024년 삼성전자의 연결 기준 매출액은 300,870,903백만원입니다.
기대 Context IDs: sec_2_4_sales_total
기대 섹션: 매출 및 수주상황
Selected Claims: -
Dropped Claims: -

Retrieved Chunks:
- III. 재무에 관한 사항 > 3. 연결재무제표 주석 [table / seed]
- III. 재무에 관한 사항 > 3. 연결재무제표 주석 [table / seed]
- III. 재무에 관한 사항 > 3. 연결재무제표 주석 [table / seed]
- III. 재무에 관한 사항 > 3. 연결재무제표 주석 [table / seed]
- III. 재무에 관한 사항 > 2. 연결재무제표 [table / seed]
- III. 재무에 관한 사항 > 3. 연결재무제표 주석 [table / seed]
- II. 사업의 내용 > 4. 매출 및 수주상황 [paragraph / seed]
- III. 재무에 관한 사항 > 1. 요약재무정보 [paragraph / seed]

Runtime Evidence:
- -

Sentence Checks:
- -

Unsupported Sentences:
- -

---

### q_004 | multi-hop-calculation

질문: 2024년 삼성전자 DX부문 매출은 DS부문 매출보다 얼마나 큰가?
예시 답변: DX부문 매출은 174조 8,877억원, DS부문은 111조 660억원으로 DX가 63조 8,217억원 더 크다.
실제 답변: 2024년 삼성전자 DX부문 매출은 1,748,877억원이고 DS부문 매출은 1,110,660억원으로, DX부문 매출이 DS부문 매출보다 638,217억원 더 큽니다.
기대 Context IDs: sec_2_2_sales_mix
기대 섹션: 매출 및 수주상황
Selected Claims: -
Dropped Claims: -

Retrieved Chunks:
- II. 사업의 내용 > 4. 매출 및 수주상황 [table / seed]
- II. 사업의 내용 > 4. 매출 및 수주상황 [paragraph / seed]
- IV. 이사의 경영진단 및 분석의견 [paragraph / seed]
- III. 재무에 관한 사항 > 3. 연결재무제표 주석 [table / seed]
- III. 재무에 관한 사항 > 3. 연결재무제표 주석 [table / seed]
- III. 재무에 관한 사항 > 4. 재무제표 [table / seed]
- III. 재무에 관한 사항 > 5. 재무제표 주석 [table / seed]
- III. 재무에 관한 사항 > 5. 재무제표 주석 [table / seed]

Runtime Evidence:
- -

Sentence Checks:
- -

Unsupported Sentences:
- -

---

### q_006 | synthesis-abstract

질문: 삼성전자가 영위하는 주요 사업을 요약해라.
예시 답변: 삼성전자는 DX 부문에서 TV·모니터·가전·스마트폰·네트워크시스템·PC를, DS 부문에서 DRAM·NAND Flash·모바일 AP를, SDC에서 스마트폰용 OLED 패널을, Harman에서 디지털 콕핏·카오디오·소비자 오디오 제품을 생산·판매한다.
실제 답변: 삼성전자는 DX(Device eXperience), DS(Device Solutions) 부문, SDC(삼성디스플레이), Harman으로 사업을 영위합니다. DX 부문은 TV, 스마트폰 등 완제품을, DS 부문은 메모리 반도체, System LSI, Foundry 사업을, SDC는 디스플레이 패널 사업을, Harman은 전장부품 및 라이프스타일 오디오 사업을 담당합니다.
기대 Context IDs: sec_2_1_business_overview
기대 섹션: 사업의 개요
Selected Claims: -
Dropped Claims: -

Retrieved Chunks:
- II. 사업의 내용 > 1. 사업의 개요 [paragraph / seed]
- II. 사업의 내용 > 7. 기타 참고사항 [paragraph / seed]
- I. 회사의 개요 > 1. 회사의 개요 [paragraph / seed]
- I. 회사의 개요 > 5. 정관에 관한 사항 [paragraph / seed]
- II. 사업의 내용 > 3. 원재료 및 생산설비 [table / seed]
- VI. 이사회 등 회사의 기관에 관한 사항 > 1. 이사회에 관한 사항 [table / seed]
- III. 재무에 관한 사항 > 3. 연결재무제표 주석 [table / seed]
- VI. 이사회 등 회사의 기관에 관한 사항 > 1. 이사회에 관한 사항 [table / seed]

Runtime Evidence:
- -

Sentence Checks:
- -

Unsupported Sentences:
- -

---

### q_009 | synthesis-abstract

질문: 삼성전자 2024 사업보고서에서 주요 재무 리스크는 무엇인가?
예시 답변: 사업보고서는 시장위험, 신용위험, 유동성위험을 핵심 재무위험으로 제시하고, 시장위험 중에서는 환율변동위험을 상세히 설명한다.
실제 답변: 환율변동위험: 글로벌 영업활동으로 인해 기능통화와 다른 통화로 거래하며 노출됩니다. 이자율변동위험: 시장금리 변동으로 투자 및 재무 활동에서 발생하는 이자수익, 비용의 현금흐름이 변동될 위험입니다. 주가변동위험: 전략적 목적 등으로 지분상품에 투자하고 있어 노출됩니다. 신용위험: 고객 또는 거래상대방이 계약조건상 의무사항을 지키지 못할 때 발생합니다. 유동성위험: 금융부채와 관련된 모든 의무를 이행하는 데 어려움을 겪게 될 위
기대 Context IDs: sec_2_5_risk_overview | sec_2_5_fx_risk | sec_2_5_credit_risk | sec_2_5_liquidity_risk
기대 섹션: 위험관리 및 파생거래
Selected Claims: -
Dropped Claims: -

Retrieved Chunks:
- II. 사업의 내용 > 5. 위험관리 및 파생거래 [paragraph / seed]
- IV. 이사의 경영진단 및 분석의견 [paragraph / seed]
- IV. 이사의 경영진단 및 분석의견 [paragraph / seed]
- III. 재무에 관한 사항 > 5. 재무제표 주석 [table / seed]
- VI. 이사회 등 회사의 기관에 관한 사항 > 2. 감사제도에 관한 사항 [table / seed]
- III. 재무에 관한 사항 > 3. 연결재무제표 주석 [table / seed]
- III. 재무에 관한 사항 > 1. 요약재무정보 [paragraph / seed]
- III. 재무에 관한 사항 > 4. 재무제표 [table / seed]

Runtime Evidence:
- -

Sentence Checks:
- -

Unsupported Sentences:
- -

---

### q_019 | adversarial-out-of-domain

질문: 애플의 2024년 1분기 매출액은 얼마인가?
예시 답변: 이 문서만으로는 애플의 2024년 1분기 매출액을 알 수 없다.
실제 답변: 관련 공시 문서에서 질문에 직접 답할 수 있는 근거를 찾지 못했습니다. 공시 문서에 정보가 없거나, 현재 검색 결과만으로는 확인하기 어렵습니다.
기대 Context IDs: -
기대 섹션: -
Selected Claims: -
Dropped Claims: -

Retrieved Chunks:
- -

Runtime Evidence:
- -

Sentence Checks:
- -

Unsupported Sentences:
- -

---

## plain_1500_200

### q_001 | single-hop-fact

질문: 2024년 삼성전자의 연결 기준 매출액은 얼마인가?
예시 답변: 2024년 삼성전자의 연결 기준 매출은 300조 8,709억원이다.
실제 답변: 2024년 삼성전자의 연결 기준 매출액은 3,008,709억원입니다.
기대 Context IDs: sec_2_4_sales_total
기대 섹션: 매출 및 수주상황
Selected Claims: -
Dropped Claims: -

Retrieved Chunks:
- III. 재무에 관한 사항 > 3. 연결재무제표 주석 [table / seed]
- III. 재무에 관한 사항 > 3. 연결재무제표 주석 [table / seed]
- III. 재무에 관한 사항 > 3. 연결재무제표 주석 [table / seed]
- III. 재무에 관한 사항 > 3. 연결재무제표 주석 [table / seed]
- III. 재무에 관한 사항 > 3. 연결재무제표 주석 [table / seed]
- III. 재무에 관한 사항 > 3. 연결재무제표 주석 [table / seed]
- II. 사업의 내용 > 2. 주요 제품 및 서비스 [paragraph / seed]
- II. 사업의 내용 > 3. 원재료 및 생산설비 [paragraph / seed]

Runtime Evidence:
- -

Sentence Checks:
- -

Unsupported Sentences:
- -

---

### q_004 | multi-hop-calculation

질문: 2024년 삼성전자 DX부문 매출은 DS부문 매출보다 얼마나 큰가?
예시 답변: DX부문 매출은 174조 8,877억원, DS부문은 111조 660억원으로 DX가 63조 8,217억원 더 크다.
실제 답변: 2024년 삼성전자 DX 부문 매출은 174조 8,877억원이고, DS 부문 매출은 111조 660억원입니다. 따라서 DX 부문 매출이 DS 부문 매출보다 63조 8,217억원 더 큽니다.
기대 Context IDs: sec_2_2_sales_mix
기대 섹션: 매출 및 수주상황
Selected Claims: -
Dropped Claims: -

Retrieved Chunks:
- II. 사업의 내용 > 4. 매출 및 수주상황 [table / seed]
- II. 사업의 내용 > 2. 주요 제품 및 서비스 [paragraph / seed]
- IV. 이사의 경영진단 및 분석의견 [paragraph / seed]
- IV. 이사의 경영진단 및 분석의견 [table / seed]
- II. 사업의 내용 > 7. 기타 참고사항 [table / seed]
- X. 대주주 등과의 거래내용 [table / seed]
- III. 재무에 관한 사항 > 3. 연결재무제표 주석 [table / seed]
- III. 재무에 관한 사항 > 3. 연결재무제표 주석 [table / seed]

Runtime Evidence:
- -

Sentence Checks:
- -

Unsupported Sentences:
- -

---

### q_006 | synthesis-abstract

질문: 삼성전자가 영위하는 주요 사업을 요약해라.
예시 답변: 삼성전자는 DX 부문에서 TV·모니터·가전·스마트폰·네트워크시스템·PC를, DS 부문에서 DRAM·NAND Flash·모바일 AP를, SDC에서 스마트폰용 OLED 패널을, Harman에서 디지털 콕핏·카오디오·소비자 오디오 제품을 생산·판매한다.
실제 답변: 삼성전자는 DX(TV, 스마트폰 등), DS(DRAM, NAND Flash 등) 부문과 SDC(스마트폰용 OLED 패널), Harman(전장제품, 소비자오디오)으로 나누어 사업을 영위합니다.
기대 Context IDs: sec_2_1_business_overview
기대 섹션: 사업의 개요
Selected Claims: -
Dropped Claims: -

Retrieved Chunks:
- II. 사업의 내용 > 1. 사업의 개요 [paragraph / seed]
- I. 회사의 개요 > 5. 정관에 관한 사항 [paragraph / seed]
- I. 회사의 개요 > 1. 회사의 개요 [paragraph / seed]
- I. 회사의 개요 > 1. 회사의 개요 [paragraph / seed]
- II. 사업의 내용 > 3. 원재료 및 생산설비 [table / seed]
- III. 재무에 관한 사항 > 3. 연결재무제표 주석 [table / seed]
- VI. 이사회 등 회사의 기관에 관한 사항 > 2. 감사제도에 관한 사항 [table / seed]
- VI. 이사회 등 회사의 기관에 관한 사항 > 2. 감사제도에 관한 사항 [table / seed]

Runtime Evidence:
- -

Sentence Checks:
- -

Unsupported Sentences:
- -

---

### q_009 | synthesis-abstract

질문: 삼성전자 2024 사업보고서에서 주요 재무 리스크는 무엇인가?
예시 답변: 사업보고서는 시장위험, 신용위험, 유동성위험을 핵심 재무위험으로 제시하고, 시장위험 중에서는 환율변동위험을 상세히 설명한다.
실제 답변: 기업회계기준서 개정으로 유동성위험 집중도에 대한 익스포저 관련 정보 공시가 요구됩니다. 분할된 삼성디스플레이㈜ 등의 분할 전 채무에 관하여 연대하여 변제할 책임이 있습니다. 다수의 소송, 분쟁 및 규제기관의 조사를 진행 중이며, 이에 따른 자원의 유출금액 및 시기는 불확실합니다.
기대 Context IDs: sec_2_5_risk_overview | sec_2_5_fx_risk | sec_2_5_credit_risk | sec_2_5_liquidity_risk
기대 섹션: 위험관리 및 파생거래
Selected Claims: -
Dropped Claims: -

Retrieved Chunks:
- II. 사업의 내용 > 1. 사업의 개요 [paragraph / seed]
- I. 회사의 개요 > 1. 회사의 개요 [paragraph / seed]
- III. 재무에 관한 사항 > 3. 연결재무제표 주석 [table / seed]
- VI. 이사회 등 회사의 기관에 관한 사항 > 2. 감사제도에 관한 사항 [table / seed]
- III. 재무에 관한 사항 > 3. 연결재무제표 주석 [table / seed]
- III. 재무에 관한 사항 > 5. 재무제표 주석 [table / seed]
- I. 회사의 개요 > 5. 정관에 관한 사항 [paragraph / seed]
- XI. 그 밖에 투자자 보호를 위하여 필요한 사항 > 2. 우발부채 등에 관한 사항 [paragraph / seed]

Runtime Evidence:
- -

Sentence Checks:
- -

Unsupported Sentences:
- -

---

### q_019 | adversarial-out-of-domain

질문: 애플의 2024년 1분기 매출액은 얼마인가?
예시 답변: 이 문서만으로는 애플의 2024년 1분기 매출액을 알 수 없다.
실제 답변: 관련 공시 문서에서 질문에 직접 답할 수 있는 근거를 찾지 못했습니다. 공시 문서에 정보가 없거나, 현재 검색 결과만으로는 확인하기 어렵습니다.
기대 Context IDs: -
기대 섹션: -
Selected Claims: -
Dropped Claims: -

Retrieved Chunks:
- -

Runtime Evidence:
- -

Sentence Checks:
- -

Unsupported Sentences:
- -

---

## plain_graph_1500_200

### q_001 | single-hop-fact

질문: 2024년 삼성전자의 연결 기준 매출액은 얼마인가?
예시 답변: 2024년 삼성전자의 연결 기준 매출은 300조 8,709억원이다.
실제 답변: 관련 공시 문서에서 질문에 직접 답할 수 있는 근거를 찾지 못했습니다. 공시 문서에 정보가 없거나, 현재 검색 결과만으로는 확인하기 어렵습니다.
기대 Context IDs: sec_2_4_sales_total
기대 섹션: 매출 및 수주상황
Selected Claims: -
Dropped Claims: -

Retrieved Chunks:
- III. 재무에 관한 사항 > 3. 연결재무제표 주석 [table / seed]
- III. 재무에 관한 사항 > 3. 연결재무제표 주석 [table / seed]
- III. 재무에 관한 사항 > 3. 연결재무제표 주석 [table / seed]
- III. 재무에 관한 사항 > 3. 연결재무제표 주석 [table / sibling_prev]
- III. 재무에 관한 사항 > 3. 연결재무제표 주석 [table / sibling_next]
- III. 재무에 관한 사항 > 3. 연결재무제표 주석 [table / sibling_prev]
- III. 재무에 관한 사항 > 3. 연결재무제표 주석 [table / sibling_prev]
- III. 재무에 관한 사항 > 3. 연결재무제표 주석 [table / sibling_next]

Runtime Evidence:
- -

Sentence Checks:
- -

Unsupported Sentences:
- -

---

### q_004 | multi-hop-calculation

질문: 2024년 삼성전자 DX부문 매출은 DS부문 매출보다 얼마나 큰가?
예시 답변: DX부문 매출은 174조 8,877억원, DS부문은 111조 660억원으로 DX가 63조 8,217억원 더 크다.
실제 답변: 2024년 삼성전자 DX 부문의 매출은 174조 8,877억원이며, DS 부문의 매출은 111조 660억원으로, DX 부문 매출이 DS 부문 매출보다 63조 8,217억원 더 큽니다.
기대 Context IDs: sec_2_2_sales_mix
기대 섹션: 매출 및 수주상황
Selected Claims: -
Dropped Claims: -

Retrieved Chunks:
- II. 사업의 내용 > 4. 매출 및 수주상황 [table / seed]
- II. 사업의 내용 > 4. 매출 및 수주상황 [table_context / table_context]
- II. 사업의 내용 > 4. 매출 및 수주상황 [table / sibling_next]
- II. 사업의 내용 > 2. 주요 제품 및 서비스 [paragraph / seed]
- IV. 이사의 경영진단 및 분석의견 [paragraph / seed]
- II. 사업의 내용 > 2. 주요 제품 및 서비스 [table_context / table_context]
- II. 사업의 내용 > 7. 기타 참고사항 [table / seed]
- IV. 이사의 경영진단 및 분석의견 [paragraph / described_by_paragraph]

Runtime Evidence:
- -

Sentence Checks:
- -

Unsupported Sentences:
- -

---

### q_006 | synthesis-abstract

질문: 삼성전자가 영위하는 주요 사업을 요약해라.
예시 답변: 삼성전자는 DX 부문에서 TV·모니터·가전·스마트폰·네트워크시스템·PC를, DS 부문에서 DRAM·NAND Flash·모바일 AP를, SDC에서 스마트폰용 OLED 패널을, Harman에서 디지털 콕핏·카오디오·소비자 오디오 제품을 생산·판매한다.
실제 답변: 또한, SDC(삼성디스플레이)는 중소형 및 대형 디스플레이 패널 사업을, Harman은 전장부품 및 라이프스타일 오디오 사업을 운영합니다.
기대 Context IDs: sec_2_1_business_overview
기대 섹션: 사업의 개요
Selected Claims: -
Dropped Claims: -

Retrieved Chunks:
- II. 사업의 내용 > 1. 사업의 개요 [paragraph / seed]
- II. 사업의 내용 > 1. 사업의 개요 [paragraph / sibling_next]
- I. 회사의 개요 > 5. 정관에 관한 사항 [paragraph / seed]
- I. 회사의 개요 > 5. 정관에 관한 사항 [table_context / table_context]
- I. 회사의 개요 > 1. 회사의 개요 [paragraph / seed]
- I. 회사의 개요 > 1. 회사의 개요 [paragraph / section_lead]
- I. 회사의 개요 > 1. 회사의 개요 [table_context / table_context]
- I. 회사의 개요 > 1. 회사의 개요 [table_context / table_context]

Runtime Evidence:
- -

Sentence Checks:
- -

Unsupported Sentences:
- -

---

### q_009 | synthesis-abstract

질문: 삼성전자 2024 사업보고서에서 주요 재무 리스크는 무엇인가?
예시 답변: 사업보고서는 시장위험, 신용위험, 유동성위험을 핵심 재무위험으로 제시하고, 시장위험 중에서는 환율변동위험을 상세히 설명한다.
실제 답변: - 유동성위험
기대 Context IDs: sec_2_5_risk_overview | sec_2_5_fx_risk | sec_2_5_credit_risk | sec_2_5_liquidity_risk
기대 섹션: 위험관리 및 파생거래
Selected Claims: -
Dropped Claims: -

Retrieved Chunks:
- II. 사업의 내용 > 1. 사업의 개요 [paragraph / seed]
- I. 회사의 개요 > 1. 회사의 개요 [paragraph / seed]
- I. 회사의 개요 > 1. 회사의 개요 [table_context / table_context]
- II. 사업의 내용 > 1. 사업의 개요 [paragraph / sibling_next]
- I. 회사의 개요 > 1. 회사의 개요 [paragraph / sibling_next]
- III. 재무에 관한 사항 > 3. 연결재무제표 주석 [table / seed]
- VI. 이사회 등 회사의 기관에 관한 사항 > 2. 감사제도에 관한 사항 [table / seed]
- III. 재무에 관한 사항 > 3. 연결재무제표 주석 [table / seed]

Runtime Evidence:
- -

Sentence Checks:
- -

Unsupported Sentences:
- -

---

### q_019 | adversarial-out-of-domain

질문: 애플의 2024년 1분기 매출액은 얼마인가?
예시 답변: 이 문서만으로는 애플의 2024년 1분기 매출액을 알 수 없다.
실제 답변: 관련 공시 문서에서 질문에 직접 답할 수 있는 근거를 찾지 못했습니다. 공시 문서에 정보가 없거나, 현재 검색 결과만으로는 확인하기 어렵습니다.
기대 Context IDs: -
기대 섹션: -
Selected Claims: -
Dropped Claims: -

Retrieved Chunks:
- -

Runtime Evidence:
- -

Sentence Checks:
- -

Unsupported Sentences:
- -

---

## plain_2500_320

### q_001 | single-hop-fact

질문: 2024년 삼성전자의 연결 기준 매출액은 얼마인가?
예시 답변: 2024년 삼성전자의 연결 기준 매출은 300조 8,709억원이다.
실제 답변: 2024년 삼성전자의 연결 기준 총 매출액은 300조 8,709억원입니다.
기대 Context IDs: sec_2_4_sales_total
기대 섹션: 매출 및 수주상황
Selected Claims: -
Dropped Claims: -

Retrieved Chunks:
- III. 재무에 관한 사항 > 3. 연결재무제표 주석 [table / seed]
- III. 재무에 관한 사항 > 3. 연결재무제표 주석 [table / seed]
- III. 재무에 관한 사항 > 3. 연결재무제표 주석 [table / seed]
- III. 재무에 관한 사항 > 3. 연결재무제표 주석 [table / seed]
- III. 재무에 관한 사항 > 3. 연결재무제표 주석 [table / seed]
- III. 재무에 관한 사항 > 3. 연결재무제표 주석 [table / seed]
- II. 사업의 내용 > 4. 매출 및 수주상황 [paragraph / seed]
- II. 사업의 내용 > 2. 주요 제품 및 서비스 [paragraph / seed]

Runtime Evidence:
- -

Sentence Checks:
- -

Unsupported Sentences:
- -

---

### q_004 | multi-hop-calculation

질문: 2024년 삼성전자 DX부문 매출은 DS부문 매출보다 얼마나 큰가?
예시 답변: DX부문 매출은 174조 8,877억원, DS부문은 111조 660억원으로 DX가 63조 8,217억원 더 크다.
실제 답변: 2024년 삼성전자 DX부문 매출은 174조 8,877억원이고, DS부문 매출은 111조 660억원으로, DX부문 매출이 DS부문 매출보다 63조 8,217억원 더 큽니다.
기대 Context IDs: sec_2_2_sales_mix
기대 섹션: 매출 및 수주상황
Selected Claims: -
Dropped Claims: -

Retrieved Chunks:
- II. 사업의 내용 > 4. 매출 및 수주상황 [table / seed]
- II. 사업의 내용 > 4. 매출 및 수주상황 [paragraph / seed]
- II. 사업의 내용 > 7. 기타 참고사항 [paragraph / seed]
- II. 사업의 내용 > 2. 주요 제품 및 서비스 [paragraph / seed]
- IV. 이사의 경영진단 및 분석의견 [paragraph / seed]
- X. 대주주 등과의 거래내용 [table / seed]
- III. 재무에 관한 사항 > 3. 연결재무제표 주석 [table / seed]
- III. 재무에 관한 사항 > 3. 연결재무제표 주석 [table / seed]

Runtime Evidence:
- -

Sentence Checks:
- -

Unsupported Sentences:
- -

---

### q_006 | synthesis-abstract

질문: 삼성전자가 영위하는 주요 사업을 요약해라.
예시 답변: 삼성전자는 DX 부문에서 TV·모니터·가전·스마트폰·네트워크시스템·PC를, DS 부문에서 DRAM·NAND Flash·모바일 AP를, SDC에서 스마트폰용 OLED 패널을, Harman에서 디지털 콕핏·카오디오·소비자 오디오 제품을 생산·판매한다.
실제 답변: 삼성전자는 DX(Device eXperience) 부문, DS(Device Solutions) 부문, SDC(패널 사업), Harman(전장부품사업)으로 나누어 경영합니다.
기대 Context IDs: sec_2_1_business_overview
기대 섹션: 사업의 개요
Selected Claims: -
Dropped Claims: -

Retrieved Chunks:
- II. 사업의 내용 > 1. 사업의 개요 [paragraph / seed]
- I. 회사의 개요 > 5. 정관에 관한 사항 [paragraph / seed]
- VI. 이사회 등 회사의 기관에 관한 사항 > 1. 이사회에 관한 사항 [paragraph / seed]
- I. 회사의 개요 > 1. 회사의 개요 [paragraph / seed]
- VI. 이사회 등 회사의 기관에 관한 사항 > 2. 감사제도에 관한 사항 [table / seed]
- II. 사업의 내용 > 3. 원재료 및 생산설비 [table / seed]
- VII. 주주에 관한 사항 [table / seed]
- VI. 이사회 등 회사의 기관에 관한 사항 > 1. 이사회에 관한 사항 [table / seed]

Runtime Evidence:
- -

Sentence Checks:
- -

Unsupported Sentences:
- -

---

### q_009 | synthesis-abstract

질문: 삼성전자 2024 사업보고서에서 주요 재무 리스크는 무엇인가?
예시 답변: 사업보고서는 시장위험, 신용위험, 유동성위험을 핵심 재무위험으로 제시하고, 시장위험 중에서는 환율변동위험을 상세히 설명한다.
실제 답변: 환율 변동 리스크: 해외법인의 외화 포지션에 대해 통화선도 상품을 매매하여 헷지하고 있습니다. 유동성위험: 기업회계기준서 개정으로 유동성위험 집중도에 대한 익스포저와 관련한 정보 공시 요구사항의 예로 공급자금융약정이 추가되었습니다. 우발부채: 중요한 소송사건 및 채무보증내역과 같은 우발부채를 가지고 있으며, 분할된 삼성디스플레이 등의 분할 전 채무에 관하여 연대하여 변제할 책임이 있습니다.
기대 Context IDs: sec_2_5_risk_overview | sec_2_5_fx_risk | sec_2_5_credit_risk | sec_2_5_liquidity_risk
기대 섹션: 위험관리 및 파생거래
Selected Claims: -
Dropped Claims: -

Retrieved Chunks:
- IV. 이사의 경영진단 및 분석의견 [paragraph / seed]
- VI. 이사회 등 회사의 기관에 관한 사항 > 1. 이사회에 관한 사항 [paragraph / seed]
- VI. 이사회 등 회사의 기관에 관한 사항 > 2. 감사제도에 관한 사항 [table / seed]
- VII. 주주에 관한 사항 [table / seed]
- III. 재무에 관한 사항 > 3. 연결재무제표 주석 [table / seed]
- III. 재무에 관한 사항 > 5. 재무제표 주석 [table / seed]
- I. 회사의 개요 > 5. 정관에 관한 사항 [paragraph / seed]
- XI. 그 밖에 투자자 보호를 위하여 필요한 사항 > 2. 우발부채 등에 관한 사항 [paragraph / seed]

Runtime Evidence:
- -

Sentence Checks:
- -

Unsupported Sentences:
- -

---

### q_019 | adversarial-out-of-domain

질문: 애플의 2024년 1분기 매출액은 얼마인가?
예시 답변: 이 문서만으로는 애플의 2024년 1분기 매출액을 알 수 없다.
실제 답변: 관련 공시 문서에서 질문에 직접 답할 수 있는 근거를 찾지 못했습니다. 공시 문서에 정보가 없거나, 현재 검색 결과만으로는 확인하기 어렵습니다.
기대 Context IDs: -
기대 섹션: -
Selected Claims: -
Dropped Claims: -

Retrieved Chunks:
- -

Runtime Evidence:
- -

Sentence Checks:
- -

Unsupported Sentences:
- -

---

## plain_graph_2500_320

### q_001 | single-hop-fact

질문: 2024년 삼성전자의 연결 기준 매출액은 얼마인가?
예시 답변: 2024년 삼성전자의 연결 기준 매출은 300조 8,709억원이다.
실제 답변: 관련 공시 문서에서 질문에 직접 답할 수 있는 근거를 찾지 못했습니다. 공시 문서에 정보가 없거나, 현재 검색 결과만으로는 확인하기 어렵습니다.
기대 Context IDs: sec_2_4_sales_total
기대 섹션: 매출 및 수주상황
Selected Claims: -
Dropped Claims: -

Retrieved Chunks:
- III. 재무에 관한 사항 > 3. 연결재무제표 주석 [table / seed]
- III. 재무에 관한 사항 > 3. 연결재무제표 주석 [table / seed]
- III. 재무에 관한 사항 > 3. 연결재무제표 주석 [table / sibling_prev]
- III. 재무에 관한 사항 > 3. 연결재무제표 주석 [table / sibling_next]
- III. 재무에 관한 사항 > 3. 연결재무제표 주석 [table / sibling_next]
- III. 재무에 관한 사항 > 3. 연결재무제표 주석 [table / sibling_prev]
- III. 재무에 관한 사항 > 3. 연결재무제표 주석 [table / sibling_next]
- III. 재무에 관한 사항 > 3. 연결재무제표 주석 [table / seed]

Runtime Evidence:
- -

Sentence Checks:
- -

Unsupported Sentences:
- -

---

### q_004 | multi-hop-calculation

질문: 2024년 삼성전자 DX부문 매출은 DS부문 매출보다 얼마나 큰가?
예시 답변: DX부문 매출은 174조 8,877억원, DS부문은 111조 660억원으로 DX가 63조 8,217억원 더 크다.
실제 답변: 2024년 삼성전자 DX 부문 매출(1,748,877억원)은 DS 부문 매출(1,110,660억원)보다 638,217억원 더 큽니다.
기대 Context IDs: sec_2_2_sales_mix
기대 섹션: 매출 및 수주상황
Selected Claims: -
Dropped Claims: -

Retrieved Chunks:
- II. 사업의 내용 > 4. 매출 및 수주상황 [table / seed]
- II. 사업의 내용 > 4. 매출 및 수주상황 [paragraph / section_lead]
- II. 사업의 내용 > 4. 매출 및 수주상황 [table_context / table_context]
- II. 사업의 내용 > 7. 기타 참고사항 [paragraph / seed]
- II. 사업의 내용 > 4. 매출 및 수주상황 [paragraph / sibling_next]
- II. 사업의 내용 > 7. 기타 참고사항 [paragraph / section_lead]
- II. 사업의 내용 > 7. 기타 참고사항 [table_context / table_context]
- II. 사업의 내용 > 7. 기타 참고사항 [paragraph / sibling_prev]

Runtime Evidence:
- -

Sentence Checks:
- -

Unsupported Sentences:
- -

---

### q_006 | synthesis-abstract

질문: 삼성전자가 영위하는 주요 사업을 요약해라.
예시 답변: 삼성전자는 DX 부문에서 TV·모니터·가전·스마트폰·네트워크시스템·PC를, DS 부문에서 DRAM·NAND Flash·모바일 AP를, SDC에서 스마트폰용 OLED 패널을, Harman에서 디지털 콕핏·카오디오·소비자 오디오 제품을 생산·판매한다.
실제 답변: 삼성전자는 DX(Device eXperience)와 DS(Device Solutions) 두 개의 부문, 그리고 패널 사업의 SDC, 전장부품사업의 Harman으로 나누어 경영합니다.
기대 Context IDs: sec_2_1_business_overview
기대 섹션: 사업의 개요
Selected Claims: -
Dropped Claims: -

Retrieved Chunks:
- II. 사업의 내용 > 1. 사업의 개요 [paragraph / seed]
- I. 회사의 개요 > 5. 정관에 관한 사항 [paragraph / seed]
- VI. 이사회 등 회사의 기관에 관한 사항 > 1. 이사회에 관한 사항 [paragraph / seed]
- I. 회사의 개요 > 5. 정관에 관한 사항 [table_context / table_context]
- VI. 이사회 등 회사의 기관에 관한 사항 > 1. 이사회에 관한 사항 [paragraph / section_lead]
- I. 회사의 개요 > 1. 회사의 개요 [paragraph / seed]
- VI. 이사회 등 회사의 기관에 관한 사항 > 1. 이사회에 관한 사항 [paragraph / sibling_prev]
- VI. 이사회 등 회사의 기관에 관한 사항 > 1. 이사회에 관한 사항 [table / sibling_next]

Runtime Evidence:
- -

Sentence Checks:
- -

Unsupported Sentences:
- -

---

### q_009 | synthesis-abstract

질문: 삼성전자 2024 사업보고서에서 주요 재무 리스크는 무엇인가?
예시 답변: 사업보고서는 시장위험, 신용위험, 유동성위험을 핵심 재무위험으로 제시하고, 시장위험 중에서는 환율변동위험을 상세히 설명한다.
실제 답변: 환율 변동 및 이자율 변동을 포함한 국내외 금융 시장의 동향 환율 리스크 등 경제적 불확실성
기대 Context IDs: sec_2_5_risk_overview | sec_2_5_fx_risk | sec_2_5_credit_risk | sec_2_5_liquidity_risk
기대 섹션: 위험관리 및 파생거래
Selected Claims: -
Dropped Claims: -

Retrieved Chunks:
- IV. 이사의 경영진단 및 분석의견 [paragraph / seed]
- VI. 이사회 등 회사의 기관에 관한 사항 > 1. 이사회에 관한 사항 [paragraph / seed]
- IV. 이사의 경영진단 및 분석의견 [paragraph / section_lead]
- VI. 이사회 등 회사의 기관에 관한 사항 > 1. 이사회에 관한 사항 [paragraph / section_lead]
- IV. 이사의 경영진단 및 분석의견 [table / sibling_prev]
- VI. 이사회 등 회사의 기관에 관한 사항 > 1. 이사회에 관한 사항 [paragraph / sibling_prev]
- VI. 이사회 등 회사의 기관에 관한 사항 > 1. 이사회에 관한 사항 [table / sibling_next]
- VI. 이사회 등 회사의 기관에 관한 사항 > 2. 감사제도에 관한 사항 [table / seed]

Runtime Evidence:
- -

Sentence Checks:
- -

Unsupported Sentences:
- -

---

### q_019 | adversarial-out-of-domain

질문: 애플의 2024년 1분기 매출액은 얼마인가?
예시 답변: 이 문서만으로는 애플의 2024년 1분기 매출액을 알 수 없다.
실제 답변: 관련 공시 문서에서 질문에 직접 답할 수 있는 근거를 찾지 못했습니다. 공시 문서에 정보가 없거나, 현재 검색 결과만으로는 확인하기 어렵습니다.
기대 Context IDs: -
기대 섹션: -
Selected Claims: -
Dropped Claims: -

Retrieved Chunks:
- -

Runtime Evidence:
- -

Sentence Checks:
- -

Unsupported Sentences:
- -

---
