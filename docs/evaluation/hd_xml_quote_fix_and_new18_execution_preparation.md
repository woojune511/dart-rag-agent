# HD현대일렉트릭 XML 누락 수정과 새 18문항 실행 준비

작성일: 2026-10-15. **파서 수정·근거 보존 검증 완료, 실제 검색·답변 평가는 NOT_RUN.** 이번 작업의 생성·임베딩·judge·DART 원문 요청은 모두0회다. 요금 확인을 위한 공식 문서 조회만 별도로 했다. 기존 평가 세트와 활성 store는 수정하지 않았다.

## 확인된 원인과 최소 수정

HD현대일렉트릭2025년 사업보고서(`20260316000940`)에는 `ENG=""...""`처럼 속성값 따옴표가 중복된 `TH` 여는 태그18개가 있다. 기존 `_sanitize_xml_like_text`는 이를 태그가 아닌 일반 문자열로 escape했지만 `</TH>`는 태그로 남겼다. 첫 오류는 원문14727행에서 시작한다. XML 복구 중 태그 짝이 연쇄적으로 어긋나고37917행의 `Extra content at the end of the document`로 후반부가 트리에서 사라졌다. 뒤에 있는 경영진단 원문은 검색 후보 청크로 만들어지지 않았다. Sanitizer를 생략한 원문 직접 파싱도 실패하므로 전처리 전체 제거는 해결책이 아니다.

수정은 `src/processing/financial_parser.py`의 해당 함수에 한정했다. 원래 태그 문법 검사를 통과하지 못한 후보에서만 중복 속성 따옴표를 정리하고, **후보 전체가 기존 태그 문법을 만족할 때만** 적용한다. 값 안의 따옴표는 `&quot;`로 보존한다. 회사명·질문ID·재무 용어 분기는 없으며, 유효한 빈 속성·일반 문장·CDATA·주석은 그대로 둔다. 원본 XML 파일은 바꾸지 않는다.

파서 결과가 달라지므로 schema를 `financial_parser_v6_doubled_attribute_quotes`로 올렸다. 기존 store를 v6로 잘못 인정하지 않도록 v5 거부 사례도 호환성 테스트에 포함했다. chunk2500/overlap320, ingest profile, 임베딩 모델, BM25, RRF, 생성 프롬프트는 유지했다.

**이번 누락의 직접 원인은 검색 이전의 XML 파싱이다.** Dense·BM25·RRF나 LLM이 이 원문 누락을 만들었다는 증거는 없다. 해당 검색·생성 단계의 다른 실패 가능성을 배제한 것은 아니다.

## 수정 전후 근거 보존

동일한 원문·메타데이터·청킹 조건에서 이전 sanitizer만 교체해 대조했다. 변경 전 projection은 이전에 봉인한2,903개 행과 완전히 같았다. 네트워크를 차단하고 section parsing 시간 제한을0으로 고정해 양쪽을 만들었다.

| 확인 항목 | 수정 전 | 수정 후 |
|---|---:|---:|
| HD XML 오류 |26|0|
| HD 해석된 section |16|46|
| HD 청크 |563|1,305|
| 오리온 청크 |1,092|1,092, 행 전체 동일|
| 호텔신라 청크 |1,248|1,248, 행 전체 동일|
| 세 보고서 총 청크 |2,903|3,645|
| 사전 작성 근거 anchor가 있는 경우 |73/76|76/76|

복원된3곳은 경영진단의 **중동·미주시장 매출 증가 및 수익성 개선**, **2026년 연결 매출계획4조3,500억원**, **예상과 실제 결과의 차이에 대한 주의 문구**다. 이는 U04 원인 설명과 U06 전망 한계 평가에 쓰이는 근거이며, 정답·질문은 수정하지 않았다.

HD 기존563개 중559개의 본문은 정확히 같다. 다른4개의 본문도 수정 후 커진 표 안에 공백 정규화 기준 연속 부분 문자열로 남는다. 다른 두 보고서의2,340개 행은 검색 입력·본문·보존 메타데이터까지 동일하다. 기존11개 보고서와 새3개를 합친14개 원문의 sanitizer 대조에서는 HD 외13개가 바이트 단위로 동일하다. 원문 파일 해시도 보존했다.

이는 **기존 본문과 지정 근거의 보존** 확인이다. 변경된 HD의 모든 표 축·section metadata 의미가 검증됐거나, 검색 순위·답변 정확도가 좋아졌다는 결과는 아니다. 세 보고서의 공통 BM25 IDF는 다시 계산되므로 청크가 같은 다른 두 보고서도 검색 순위 동일성을 보장하지 않는다. HD의 청크 식별자와 문맥은 달라질 수 있으므로 이전 청크ID를 그대로 쓰지 않고 별도 `evidence_mapping_v6.json`으로 추적한다.

새 익명 회귀 테스트5개는 수정 전3개 실패·2개 통과였고 수정 후5개 모두 통과했다. 관련 파서·literal/header tests48개, 추가 청킹·heading·store 계약76개, import·문서 검증24개로 중복을 제외한148개가 통과했다. v5 store 거부를 추가한 header tests6개도 재확인했다. `focused_tests.log`, `parser_contract_tests.log`, `v5_rejection_tests.log`, `import_docs_tests.log`에 원기록을 보존했다. 전체 unittest는 실행하지 않았다.

현재 `.env`는 여전히 full11 v5 store를 가리킨다. manifest만 읽은 readiness는 **mismatch/ready=false**다. 이 작업은 기존 store를 열거나 갱신·활성화하지 않았다. 새 평가용 store 생성과 기존 앱의 full11 store 전환은 별개다.

## 고정한 실행 조건

이후 실행은 **수정된 파서에서 새18문항의 첫 기준 성능을 측정**한다. 수정 전후 답변 A/B나 두 모델 비교를 추가하지 않는다. 18문항은 실사용 상황을 가정해 직접 작성한 질문이며 실제 사용자 로그나 독립 인간 평가 세트는 아니다.

| 항목 | 고정 조건 |
|---|---|
| 문항·정답 | 이전 `new_report_user_eval_2026-10-15`의 질문·gold·rubric 해시 유지;18문항, 각2회 |
| 문서 | HD현대일렉트릭·오리온·호텔신라2025년 보고서 전체3,645청크; 정답 근거 외 문맥도 포함 |
| store | 별도 `hd_xml_quote_fix_2026-10-15/future_live_v1/store`; 세 보고서를 하나의 corpus로 구성; 기존 앱 store/.env 유지 |
| 임베딩 | `text-embedding-3-large`,3072차원; 검색 입력3,645개와 원래 질문18개를 각각 한 번 생성 |
| 임베딩 배치 | corpus 순서 유지, 최대64개·80,000tokens/요청; 입력별8,192tokens 이하; 중복 text도 원래 행 유지 |
| 검색 | 명시적 report_scope; Dense16·BM25최대24 → 동일 가중치RRF(k=60) → top8 |
| BM25 | 현행 tokenizer와 prefix·stopwords 그대로; `까지` 제외나 표제 부착 실험 미적용 |
| 문맥 | 현재65,536-byte 한도와 whole-source omission 규칙; 추가 caption link·reranker 없음 |
| 반복 | 문항별 실제 검색 결과·packet을 한 번 봉인하고 두 생성에 동일하게 제공; 첫 회 U01→U18, 둘째 U18→U01 |
| 생성 | 현행 `gpt-5.6-terra`,reasoning low,temperature 미전송,Responses API,strict RagAnswer,최대 output8192,store=false,standard/default tier |
| 실행 | 동시성1,timeout90초,SDK/앱 retry0; 30초 heartbeat와 호출 전 예약액·요청·응답·usage 저장 |
| 추가 호출 | context generation·Planner·Compiler·judge·probe·유료 token count·DART 재수집0 |

평가기는 기존 gold/rubric과 원문을 읽지만 모델 입력은 원래 질문·선택 범위·실제 검색 문맥·현재 프롬프트뿐이다. 정답 anchor로 검색 window를 고르지 않는다. 생성 전후 문항 수정이나 오류별 prompt tuning을 하지 않는다.

실제 검색으로 정해질 provider 요청은 아직 없다. 현재 `SimpleRagAgent`와 strict 모델 경로를 네트워크 차단 mock으로36회 통과시켜 요청 형식·scope·반복 동일성을 확인했다. 문맥 크기 점검에는 각 보고서에서 JSON 크기가 큰8개 청크를 사용했으며, 이는 검색 결과나 평가 답변이 아니다. live 실행기는 별도로 임베딩·store 구축·호출 예약을 연결하고 dispatch guard를 mock 검증한 뒤 실행해야 한다. 기존 benchmark CLI에 준비 JSON을 바로 넣을 수 있다고 주장하지 않는다.

## 예상 비용과 호출 상한

[공식 요금표](https://developers.openai.com/api/docs/pricing)를2026-10-15에 확인했다. Standard/global,1Mtokens당 Terra 입력$2.00·cache write$2.50·출력$12.00, embedding$0.13이다. Short context 경계272K보다 낮은 입력 상한을 적용한다. 환율·세금은 포함하지 않으며 실제 청구액은 반환 usage로 별도 정산한다.

| 호출 종류 | 상한 | 비용 산정 |
|---|---:|---|
| 전체 문서 임베딩 |58|2,648,007tokens|
| 질문 임베딩 |1|757tokens;18개 묶음, 양 반복 재사용|
| 답변 생성 |36|문항18개×2회;빈 근거이면 코드상 무호출 abstention|
| **총 provider 요청** |**95**|retry·probe·judge 추가 불가|

임베딩의 로컬 token count 기준 예상액은 **$0.34433932**다. 입력당128tokens 여유를 포함한 임베딩 예약액은$0.40529164다. 생성은 매 호출 입력70,000tokens·출력8,192tokens를 예약하고, 입력 전체를 cache write의$2.50/M로 계산한다. reasoning은 출력 사용량에 이미 포함하므로 중복 계산하지 않는다.

- 생성 최대 예약액: `36 × (70,000×$2.50 + 8,192×$12)/1,000,000 = $9.838944`
- 합산 최대 예약액: **$10.24423564**
- 준비한 비용 상한: **$10.25**, 전체95회·생성36회 상한과 동시에 적용

실제 예상액은 문맥과 출력 길이에 달려 있다. 답변당 입력10,000·출력1,000tokens를 가정하면 임베딩 포함 **약$1.50**, 입력을 모두 cache write 요율로 잡으면 **약$1.68**이다. 입력20,000·출력1,500 가정에서는 약$2.43~2.79다. **이는 계획용 가정이며 새18문항에서 측정한 비용은 아니다.**

각 생성 전에 최종 request의 UTF-8 bytes(프롬프트·schema·packet 포함)+1,024 여유가70,000 이하인지 검사한다. 한도를 넘으면 문맥을 임의로 바꾸지 않고 dispatch 전에 중단한다. 누적 비용+진행 중 예약액+다음 호출 최대액이 상한을 넘으면 호출하지 않는다. 오류·timeout·usage 누락·차원/해시/scope 불일치·검색 fallback·잘린 응답·schema/출처ID 오류가 나면 즉시 중단하고 나머지는 NOT_RUN으로 둔다. 응답이 불명확한 호출의 예약액은 환급 처리하지 않는다. 추가 재시도나 자동 재개는 없다.

## 판정과 남은 한계

기존 rubric의 정확도·필수 항목 충족·출처 충실도·인용 지원·답변 한계를 각각 P/F/U/NOT_RUN으로 보고한다. 부가적인 인과·분류 claim도 따로 검사한다. U06/U12/U18의 부분 답변·추론 한계, 사전에 기록한 U15의 원문 간 충돌을 유지한다. source-ID 검사를 의미 검증으로 계산하지 않는다. 1회차 성과와2/2 일관성, 보고서별 결과를 제시하고36응답을 독립36문항처럼 집계하지 않는다.

실패는 원문 자체 부족/충돌 → corpus 누락 → Dense/BM25 후보 누락 → 최종 문맥 누락 → 생성 해석 순서로 근거를 확인한다. 첫 누락 위치가 유일한 원인이라는 인과 주장은 하지 않는다. 기존12문항의 답변 회귀는 이번36회 대상에 포함되지 않는다. 기존11문서의 파싱 입력 보존이 이전 답변 회귀 부재를 뜻하지 않는다.

## 로컬 산출물

- 수정 전후 XML·오류 기록 (`../../benchmarks/results/hd_xml_quote_fix_2026-10-15/xml_comparison.json`, local artifact not included), canonical projection 대조 (`../../benchmarks/results/hd_xml_quote_fix_2026-10-15/projection_comparison.json`, local artifact not included)
- 변경된4개 청크 본문 보존 (`../../benchmarks/results/hd_xml_quote_fix_2026-10-15/chunk_preservation.json`, local artifact not included), 76개 근거 대응표 (`../../benchmarks/results/hd_xml_quote_fix_2026-10-15/evidence_mapping_v6.json`, local artifact not included)
- 실행 조건·36개 슬롯·해시 (`../../benchmarks/results/hd_xml_quote_fix_2026-10-15/run_conditions.json`, local artifact not included), 임베딩58+1 배치 (`../../benchmarks/results/hd_xml_quote_fix_2026-10-15/embedding_plan.json`, local artifact not included), 비용 예약 (`../../benchmarks/results/hd_xml_quote_fix_2026-10-15/cost_plan.json`, local artifact not included)
- 생성 요청 계약 (`../../benchmarks/results/hd_xml_quote_fix_2026-10-15/request_contract.json`, local artifact not included), 무호출36회 요청 점검 (`../../benchmarks/results/hd_xml_quote_fix_2026-10-15/offline_request_contract_check.json`, local artifact not included), 기존 store 호환성 (`../../benchmarks/results/hd_xml_quote_fix_2026-10-15/active_store_readiness.json`, local artifact not included)
- 보존 해시·테스트·비용 상한 최종 점검 (`../../benchmarks/results/hd_xml_quote_fix_2026-10-15/closeout.json`, local artifact not included)

실험 산출물은 `benchmarks/results/**` 아래에 별도로 두고 stage/commit/push하지 않았다. 기존 [18문항 준비 문서](new_report_user_eval_preparation.md)와 그 당시 원본 projection은 그대로 보존한다.
