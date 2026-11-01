# 고정 근거의 생성 모델 비교 결과

2026-10-15 · `COMPLETE_GATE_NOT_MET`

**C11은 개선됐지만, 새 6문항에서 반복되는 확정 개선은 없었다.** 원래 질문·검색 결과·생성 조건을 유지한 C11에서 홈쇼핑을 온라인 아래에 넣는 오류는 gpt-5.6-terra 2/2회, gpt-6.1-sol 0/2회였다. 기존 15개 필수 항목과 홈쇼핑은 네 답변 모두 보존했다. 기존 12문항에서 Sol의 정확도·누락·출처 충실도 회귀는 관찰되지 않았다. 그러나 사전 기준인 **새 문항 2개 이상·관계 유형 2종 이상의 반복 개선**을 충족하지 못했다. 기본 모델과 제품 경로를 유지한다.

## 실행 범위와 고정 조건

[준비 문서](generation_model_transfer_preparation.md)의 manifest SHA256 `5134dbef939c4f04dab9d53a450f7dccab7dbb8d7da1c374ad6e74691f56cb81`에 대한 사용자 실행 요청으로 **72/72회**, 모델별36회, 18문항×각2회를 완료했다. 과거 답변을 새 baseline으로 재사용하지 않았다. 오류·재시도·NOT_RUN·추가 검색·임베딩·judge·접근 확인용 probe는 모두0이다. 실행은 UTC08:39:52–08:46:28,395.73초였다.

문항별 두 요청은 모델 ID만 다르다. 원래 프롬프트, `low`, reasoning mode 생략, strict RagAnswer, 최대 출력8,192토큰, `service_tier=default`, `store=false`, 명시적 캐시 모드, 도구 없음이 고정됐다. 반환 모델 ID는 요청과 동일했고, 전부 `low`·`standard`였다. 요청 순서는 인접 쌍으로 교차하고 두 번째 반복에서는 순서를 뒤집었다. timeout90초·heartbeat15초·첫 오류 중단 조건을 적용했다.

기존12는 원래 C11 질문의 세 분류를 포함한 저장 B1 검색 결과를 사용했다. ‘까지’ 제외, 연결 표제·기간을 보존한 BM25/Dense, Dense16/BM25-24·동일 가중 RRF60·top8·보고서 범위를 그대로 유지했으며 검색을 다시 수행하지 않았다. 새6은 기존 canonical v5 청크를 원문에 대조해 고른 충분한 근거 묶음이다. 따라서 아래 두 패널을 **18문항 전체 RAG 정확도로 합산하지 않는다.**

## 정확도와 출처 충실도

P는 필수 내용·요청 충족·실제 인용 근거 및 추가 주장까지 통과, F는 확정 실패, U는 판정 유보다. U를 실패나 성공으로 바꾸지 않았다. 모든 실제 답변과 실제 인용 청크를 대조했으며, 단순 출처 ID 검사 통과를 의미 정확성으로 세지 않았다.

| 패널·엄격 판정 | Terra 1회차 | Sol 1회차 | Terra 2회차 | Sol 2회차 |
|---|---:|---:|---:|---:|
| 기존12 | 10P·1F·1U | 12P | 10P·1F·1U | 12P |
| 새6 | 6P | 6P | 5P·1U | 6P |

기존12의 필수 값·항목·단위·명시적 요청 내용과 그 인용 지원은 양쪽24/24 답변에서 유지됐다. Terra의 C11 F는 **추가한 잘못된 분류 관계**, C09 U는 **중간 반올림 여부를 확인할 수 없는 계산 절차**이다. 이를 제외하고 기존10문항은 양쪽 두 번 모두 엄격 통과했다. C10도 네 답변 모두 같은 현금흐름·당기순이익과5.76%를 정확히 제시했다. 실제 답변에 사용된 원 단위 대체 출처는 고정 기준에 따라 검증했고, 금액·비율은 별도 Decimal 계산으로 대조했다.

### C11: 질문을 바꾸지 않아도 분류 오류 감소

원문70:2는 `홈쇼핑 및 온라인 채널`을 병렬로 열거한다.71:3은 온라인 채널 강화와 자사몰을 설명하지만 홈쇼핑을 온라인의 하위로 선언하지 않는다.

- Terra1: `온라인 채널: 홈쇼핑, 온라인 채널, 자사몰` → 지원되지 않는 하위 분류.
- Terra2: `온라인 채널: 홈쇼핑, 자사몰 및 온라인 커머스 채널` → 같은 오류. 추가 인용69:1도 이 관계를 지원하지 않는다.
- Sol1: `온라인·홈쇼핑`이라는 병렬 표제 → 통과.
- Sol2: 온라인 채널·자사몰과 별도 `기타: 홈쇼핑` → 통과. 기타는 답변 정리 표제이며 보고서의 공식 분류라고 주장하지 않는다.

네 답변 모두 필수15항목을15/15 보존했다. Sol2의 “판매방법과 대금회수 조건은 내수·수출별로 구분하지 않고 공통 항목으로 제시”라는 설명도71:3의 서술 형식에 부합한다. **C11의 보고된 reasoning 토큰은 네 호출 모두0**이다. 이 개선을 reasoning 토큰 증가의 효과라고 설명할 수 없다.

### C09: 최종 숫자 교정과 구분

네 답변 모두90.94%·91.12%·-0.18%p 및 피연산자가 정확하다. Terra는 두 번 모두 변화량을 반올림 전 비중으로 계산했는지 보이지 않아 기존 기준대로 U이다. Sol은 두 번 모두 원 피연산자로 구성한 비율의 차이를 명시하고, 반올림 전 계산이라고 밝혔다. **U→P의 절차 표현 개선**이며, 오답 숫자를 바로잡은 F→P로 세지 않는다. 보이는 식을 검사한 결과이지 모델 내부 계산 경로나 제품의 산술 실행 검증은 아니다.

### 새6: 반복되는 확정 이득 없음

| 문항 | 확인한 관계 | Terra 두 번 | Sol 두 번 |
|---|---|---|---|
| R13 LG에너지솔루션 | 전지 분야별 적용 예시 | P/P | P/P |
| R14 LG에너지솔루션 | BaaS·EaaS·Recycle/Reuse·ESS 병렬 관계 | P/U | P/P |
| R15 POSCO홀딩스 | 네 회사의 담당 사업·소속 부문 | P/P | P/P |
| R16 삼성전자 | DX·DS·SDC 제품 및 SDC 별도 구분 | P/P | P/P |
| R17 SK하이닉스 | 매출·영업손실·영업외비용의 원인 대응 | P/P | P/P |
| R18 셀트리온 | 준공·가동예정·증설착수·기대효과와 실현 성과 | P/P | P/P |

새6의 필수25개 요구 그룹은 양쪽 매 반복25/25, 총50/50씩 유지됐다. 요청한 핵심 관계의 확정 오류는 없었다. 모든 답변은 `abstained=false`였으며, R18은 지원되는 확충 사실을 답하고 미확인 실현효과만 유보해 고정된 혼합형 기준을 충족했다.

R14 Terra2의 추가 수식 `사용 후 배터리`는 원문의 `배터리 Recycle/Reuse 사업`에 대한 일반적인 뜻풀이인지, 대상 범위를 한정한 주장인지 애매하다. 원문은 대상 범위를 명시하지 않아 추가 주장 출처 충실도만 U로 남겼다. 필수 내용·병렬 관계는 P이며 **확정 오류 감소나 반복 개선으로 세지 않는다.** 이 표현을 통상적 뜻풀이로 허용하는 민감도에서는 새6이 두 모델 모두12/12 엄격 통과하므로, 반복 이득0이라는 결론은 같다.

## 비용·토큰·지연시간

실행 당일 다시 확인한 [공식 가격](https://developers.openai.com/api/docs/pricing)의 Standard 단기 문맥 요율을 적용했다. 입력은 양쪽$2/M, 출력은 Terra$12/M·Sol$10/M이며, 실제 캐시 읽기·쓰기 토큰은 모두0이다. 아래 요금은 반환 사용량으로 계산한 예상값이며 청구서 정산값은 아니다. reasoning 토큰은 출력에 이미 포함되어 중복 계산하지 않았다.

| 항목 | Terra | Sol |
|---|---:|---:|
| 실제 호출 | 36 | 36 |
| 입력 토큰 | 183,354 | 183,354 |
| 출력 토큰(추론 포함) | 11,161 | 11,126 |
| 보고된 reasoning 토큰 | 1,369 | 420 |
| 사용량 기준 예상 요금 | $0.500640 | $0.477968 |
| 입력을$2.50/M로 계산한 보수적 비용 | $0.592317 | $0.569645 |
| 평균 응답시간 | 3.47초 | 7.52초 |
| 중앙 응답시간 | 3.20초 | 7.05초 |

총 예상 요금은 **$0.978608**, 보수적 비용은 **$1.161962**다. 실행 전 최대 예약액**$10.2595140**과 사용자 상한**$10.26** 이내다. 이 배치에서 Sol의 예상 요금은4.5% 낮았지만 평균 응답시간은2.17배였다. 같은 문항·반복별 비율의 중앙값은 비용0.969배, 지연2.017배였다. 이 관측만으로 일반 비용 효율이나 서비스 지연을 보장하지 않는다.

## 판정·검증·한계

확정 F/F→P/P는 기존 C11 하나다. C09는 U/U→P/P, R14는 P/U→P/P이므로 별도 기록했다. 새 문항의 반복 확정 개선0개·관계 유형0종으로 사전2개·2종 기준을 충족하지 못했다. 단회·반복 모두 Sol의 핵심 내용·누락·인용 지원 회귀는 관찰되지 않았다. **C11의 국소 개선은 확인했지만 모델 교체의 일반화된 근거는 부족하다.** 제품 모델·프롬프트·검색·store는 변경하지 않았고 추가 호출이나 후속 튜닝도 실행하지 않았다.

준비 산출물82개와 보호 입력788개의 해시를 재검증했다. 새 실행기의72회 SDK 모의 전송 및13개 오류 시나리오를 통과한 뒤 실제 실행을 시작했다. 실제 요청72개·원시 응답72개·고유 response ID72개를 재구성했으며, 모델 이외의 조건·출처 ID·usage·예산을 확인했다. 별도 Decimal 계산은9개 원래 계산과2개 대체 원문 계산을 검증했다. 소스 리뷰는 같은 assistant가 작성한 정답 기준으로 수행했다. 답변 읽기 출력에서 모델 필드는 뺐지만 실행 순서를 알고 있었으므로 독립 맹검 평가가 아니다.

18문항·익숙한7개 보고서·각2회라는 범위이고, 새6은5개 보고서의 충분한 단일 청크다. 새 문항의 핵심 관계는 Terra도 모두 맞혀 이 표본에서는 차이를 드러내지 못했다. 미노출 문서·실제 검색 실패·거절 품질이나 모집단 정확도를 검증한 결과가 아니다. 제공자 응답의 모델 ID도 날짜 없는 ID이므로 고정된 불변 snapshot이라고 주장하지 않는다.

- 실행 권한과 상한 (`../../benchmarks/results/generation_model_transfer_2026-10-15/authorization.json`, local artifact not included), 실행 manifest (`../../benchmarks/results/generation_model_transfer_2026-10-15/execution_manifest.json`, local artifact not included), 요금 재확인 (`../../benchmarks/results/generation_model_transfer_2026-10-15/pricing_revalidation.json`, local artifact not included)
- 실제 실행 결과 (`../../benchmarks/results/generation_model_transfer_2026-10-15/live_v1/results.json`, local artifact not included), 요청·응답·비용 재검증 (`../../benchmarks/results/generation_model_transfer_2026-10-15/execution_audit.json`, local artifact not included)
- 72개 답변과 판정 (`../../benchmarks/results/generation_model_transfer_2026-10-15/answer_review.md`, local artifact not included), 요구 그룹별 리뷰 (`../../benchmarks/results/generation_model_transfer_2026-10-15/manual_review.json`, local artifact not included), 집계 (`../../benchmarks/results/generation_model_transfer_2026-10-15/review_summary.json`, local artifact not included)
- 실제 인용 근거 묶음 (`../../benchmarks/results/generation_model_transfer_2026-10-15/source_review_packets.json`, local artifact not included), 계산 대조 (`../../benchmarks/results/generation_model_transfer_2026-10-15/numeric_review.json`, local artifact not included), 무호출 실행기 검사 (`../../benchmarks/results/generation_model_transfer_2026-10-15/offline_execution_checks.json`, local artifact not included)

실험 산출물은 Git ignored이며 커밋·stage·push는 수행하지 않았다. 이전 비교 결과와 준비 시점의 NOT_RUN 기록은 변경하지 않았다.
