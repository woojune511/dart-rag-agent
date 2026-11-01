## Material Passport

- Origin Skill: academic-research-suite / experiment-agent run + validate
- Date: 2026-10-23 Asia/Seoul
- Verification Status: ANALYZED — frozen-input generation and source review completed; not independent human validation or stochastic reproducibility certification.
- Scope: development-exposed77 questions × A/C ×2repetitions; original retrieval and generation conditions fixed.
- Source/implementation changes: none. Only isolated experiment artifacts; no app restart, commit or push.

# 표 값 단위 전달: 기존 77문항 실제 답변 비교

**필요한 값의 전달과 일부 답변은 개선됐지만, 전체 답변의 완전한 성공은 거의 늘지 않았다.** 답변 가능46문항을 각각2회 생성한 결과, 완전 정답은 A83/92에서 C84/92로1개 증가했다. 반복1은42→42, 반복2는41→42였다. C의 입력 토큰은 약2.11배, 성공 요청 추정 비용은 약1.96배였다. 이 결과로 전체160KiB 표 첨부의 일반적인 성능 우월성이나 비용 대비 이득을 확정할 수 없다.

Motional의 지분율·장부가액·최근사업연도 순손실 복구는2/2회 확인됐다. 다만 요청한 요약손익 전체는 남아 있어 부분 개선이다. SK이노베이션 배터리 표의 화폐단위도2/2회 복구됐지만, 추가한 SK온 자체 연결수치의 주체·인용 연결에 한계가 남아 완전 정답으로 올리지 않았다. POS 이자보상배율과 SK하이닉스 자산 대비 차입금 비율은 필요한 피연산자가 여전히 없어 두 조건 모두 계산을 완료하지 못했다.

답변 가능46문항에서는 A가 충족했던 필수 항목을 잃거나 완전 정답에서 탈락한 쌍은 없었다. 그러나 HOLD군에서는 추가 설명의 출처 지지가 약해지거나 미결정인 경우가 있었고, 그중1개는 입력이 동일한 대조 문항이었다. 따라서 전체77문항에 대해 “회귀 없음”이라고 결론짓지 않는다. 제품 구현·기본 문맥 예산은 이번 결과로 변경하지 않았다.

## 조건과 평가 분모

A는 원래 저장된 A12 문맥, C는 같은 문서에 원문 위치 연결을 확인한 표의 값·행·열 정보를 추가한 최대160KiB 문맥이다. 후보·점수·순서·최종 선택12개와 실제 전달 문서 창을 고정했다. 모델은 gpt-6.1-sol, reasoning low, 원래 프롬프트·응답 스키마, 최대 출력8,192토큰이다. 두 조건 모두 이번 실행에서 새 답변을 생성했다. 검색·임베딩·별도 judge API 호출은 없다.

선택12개와 실제 전달 문서는 구분한다. 기존 byte 제한으로 6문항은 실제6–11개 문서였고, 나머지71문항은12개였다. 두 조건에서 그 문서 수·ID·원문·순서는 동일하다. C는 근거 표현과 전달량을 함께 바꾸므로 순수 형식 효과나 순수 예산 효과로 분리할 수 없다.

사전에 동결한 평가군은 답변 가능46문항, 거절19문항, HOLD12문항이다. 조건별 응답 수는92·38·24이다. HOLD의 전체 정확도·완전성·완전 정답은 null로 두었다. 과거48/55문항 분모와 직접 비교하지 않는다. 완전 정답은 정확도·완전성·출처 충실도가 모두 PASS인 경우다. 유효한 출처 ID만으로 의미 지지가 확인되는 것은 아니다.

## 답변 가능46문항

| 판정 | A: 원래 문맥 | C: 표 값 단위 추가 |
|---|---:|---:|
| 정확도 PASS | 83/92 (90.2%) | 86/92 (93.5%) |
| 필수 요청 완료 PASS | 84/92 (91.3%) | 86/92 (93.5%) |
| 출처 충실도 PASS | 89/92 (96.7%) | 90/92 (97.8%) |
| 완전 정답 | 83/92 (90.2%) | 84/92 (91.3%) |

| 반복 | A 완전 정답 | C 완전 정답 |
|---|---:|---:|
| 1 | 42/46 | 42/46 |
| 2 | 41/46 | 42/46 |

| 사전 구분 | 문항 수 | A 완전 정답 | C 완전 정답 |
|---|---:|---:|---:|
| pilot12 중 답변 가능 | 8 | 8/16 (50.0%) | 8/16 (50.0%) |
| other65 중 답변 가능 | 38 | 75/76 (98.7%) | 76/76 (100.0%) |

답변 가능군의 동결126개 평가 항목×2회, 총252개 **평가 기록**에서 FULFILLED는236→244, OMITTED는12→6, PARTIAL은4→2였다. 미충족 기록 합계는16→8이다. 이 목록에는 기존 별칭·확인 항목이 포함돼 독립 사실의 개수로 해석하지 않는다. 특히 Motional의 요약손익2개 기록은 OMITTED에서 PARTIAL로 바뀌었으므로 “누락6개 감소”를 “6개 항목의 완전 복구”로 바꾸어 말하면 안 된다.

두 반복에서 모두 완전 정답인 문항은 41/46→42/46이다. **A에서 두 번 모두 미완료였다가 C에서 두 번 모두 완전 정답이 된 문항은 없다.** KAB_T3_067은 A가 1/2회, C가 2/2회였고 나머지 완전 정답 전환은 없었다. pilot12 중 답변 가능 8문항의 완전 정답은 8/16으로 같고, 다른 38문항에서만 1개 응답 차이가 발생했다. 나머지 65문항을 새 holdout 성능으로 해석하지 않는다.

## 개선·회귀 대조

| 문항·반복 | 정확도 변화 | 완전성 변화 | 충실도 변화 | 새로 충족한 기록 | 충족을 잃은 기록 |
|---|---:|---:|---:|---|---|
| HYU_T2_010 r1 | None | None | -1 | — | us_sales_2022 |
| SKH_T1_060 r2 | 0 | 0 | 0 | long_borrowing, bond | — |
| HYU_T3_072 r1 | 1 | 1 | 0 | ownership, carrying | — |
| HYU_T3_072 r2 | 1 | 1 | 0 | ownership, carrying | — |
| SKI_T1_068 r1 | 1 | 1 | 0 | currency_binding | — |
| SKI_T1_068 r2 | 1 | 1 | 0 | currency_binding | — |
| KAB_T3_067 r2 | 1 | 0 | 1 | — | — |

변화는 FAIL=0, PARTIAL=1, PASS=2의 차이이며 평균 간격척도나 효과 크기로 해석하지 않는다. null/AMBIGUOUS는 수치 차이로 환산하지 않는다. 단위 목록은 동결한 평가 기록이다. 전체154기록에는 alias/checkpoint17개와 선택적 진단1개가 포함되므로 독립 필수 사실154개로 세지 않는다. 종류별 집계는 summary.json의 unit_record_states_by_kind에 보존했다.

| 사례 | 실제 답변에서 확인된 변화 | 해석의 범위 |
|---|---|---|
| HYU_T3_072: Motional | A는2/2회 모두 값 확인을 유보. C는25.81%,1,294,367백만원,최근사업연도 순손실803,742백만원을2/2회 제시 | source1246:4에 붙은 원래 표의 해당 행이 전달된 효과. 매출·기타포괄손익·총포괄손익까지 요구한 요약손익은 미완료 |
| SKI_T1_068: 배터리 영업손실 | 두 조건 모두581,816/1,903,886=30.56%. C는해당 표의백만원 표제를 실제 전달해 금액단위 지지를 복구 | C의 보충 주장581,824 자체는 다른 표에 존재. 그러나 “SK온 자체 연결” 주체 연결에 쓰는181:1/1913:206은 미인용이며 해석적 대응이므로 충실도 PARTIAL |
| SKH_T1_060: 차입금 비율 | C는명명된 세 행 합계23,757,090을2/2회 사용. A는유동성 포함29,468,632를 사용 | A r1에는 비유동 개별값도 괄호 안에 있으므로 그것까지 누락으로 세지 않음. 자산 분모는두 조건 모두없어 최종 비율 미완료 |
| POS_T1_057: 이자보상배율 | 두 조건 모두이자비용1,001,290백만원만 확인하고 비율을 유보 | 영업이익 피연산자가 실제 packet에 없어 표현 추가로 해결되지 않음. 원문 보고서 전체의 부재를 뜻하지 않음 |
| KAB_T3_067: 플랫폼 확장 | A r2만쿠폰 서비스 출시를2023년으로 단정. C는그 보충 단정을하지 않음 | 완전 정답+1의 유일한 원인. 원래 서술 근거는같으므로 표 구조 개선 때문이라고 단정할 수 없는1회 차이 |
| MIX_T3_063: 투자 상위기업(HOLD) | C에서A Holdings15,338,412,557천원 및Mirae Asset-Naver341,924,825천원 복구 | 기업별당기순손익은없고 순위 모집단·손익정의HOLD 유지. 본평가 성공 증가로 합산하지 않음 |

초기 검토는 C의 SKI 두 응답을 모두 PASS로 판단했지만, 실제 인용 세트와 주체 연결을 다시 대조해 충실도만 PARTIAL로 조정했다. 주결과의 정확도·완전성·필수 unit 충족은 유지한다. 그 결과 C의 초기 완전 정답 86/92가 최종 84/92가 됐다. SKH의 A r1은 직접 표기한 두 개별값의 unit 상태만 FULFILLED로 바로잡았으며 전체 PARTIAL 판정은 동일하다. 변경 전·후와 출처는 [adjudication_log.json](adjudication_log.json), 교차 검토는 crosscase_adjudication.json (`crosscase_adjudication.json`, local artifact not included)에 남겼고 초기 판정은 수정하지 않았다.

## 거절과 HOLD

| 구분 | A | C |
|---|---:|---:|
| 거절19문항: 적절한 거절 PASS | 36/38 (94.7%) | 36/38 (94.7%) |
| 거절19문항: 충실도 PASS | 36/38 (94.7%) | 36/38 (94.7%) |
| HOLD12문항: 개별 주장 충실도 PASS | 22/24 (91.7%) | 19/24 (79.2%) |

거절군에서 두 조건 모두 실패한 2개 응답은 MIX_T4_062의 두 반복이다. 사용자가 제시한 100조 가정을 명시적으로 가정이라고 밝히고 38.6%를 계산했으나, 사전에 고정한 grounded-only 거절정책은 이를 허용하지 않는다. 따라서 정책 실패로 유지한다. 계산 자체가 틀렸거나 100조를 실제 공시액으로 날조했다고 주장하지 않는다. 별도 충실도 축의 해석은 두 조건 모두 AMBIGUOUS다.

HOLD에서 POS_T1_075의 43,248백만원 EBITDA는 두 조건 모두 표 주체가 미확인되어 PARTIAL이다. SAM_T2_027은 A가 2023년 실적·기술성과와 향후 DS 전략의 차이를 명시한 반면 C의 두 답변은 사업 방향을 더 단정적으로 요약해 충실도 AMBIGUOUS로 남겼다. 명백한 새 허위사실 2개라고 확정하거나 null 차이를 수치 0으로 처리하지 않는다. HYU_T2_010의 C r1에는 11.4% 계산값과 11.5% 공시값 차이의 원인을 반올림이라고 단정한 추가 설명이 있어 PARTIAL이다.

**입력이 동일했던 대조 문항:** CEL_T3_015·SAM_T3_003·HYU_T2_010은 A/C 요청 본문이 byte 단위로 같았다. 앞의 2개는 답변 가능군이며 모든 반복 PASS, HYU는 HOLD이며 C r1의 반올림 설명에만 회귀가 있었다. 같은 입력에서도 판정 차이가 발생했다는 관측이며, HYU 회귀는 표 첨부 때문이라고 볼 수 없다. SAM의 향후 전략 문단도 새로 추가된 것이 아니어서 원인 귀속은 확정하지 않는다.

## 실행·비용

- 성공 답변 308개, HTTP 시도 309회. 최초44번째 요청의503/server_is_overloaded는 원본 그대로 보존했다. 사용자 승인 후 실패1개와 미실행264개만 이어서 생성했다. 기존 성공43개를 다시 생성하거나 답변 내용으로 선별하지 않았다.
- 사용량 기준 성공 요청 추정 비용 $9.9381220; 실패 요청의 미정산 예약 $0.1702425를 포함한 보수적 합계 $10.1083645. 승인 상한은 총309회·$70.09. 미정산 실패 호출을 무료로 가정하지 않는다.
- 두 구간 합산 active-process 시간 46.37분. 승인 대기는 제외하며 합계150분 상한을 유지했다. 생성·평가 중 기존 앱 재시작 없음.
- 아래 비용·시간은 답변 생성 API 측정값이다. 네이티브 Codex 검토의 구독 사용량은 별도 계측하지 않았다.

| 조건 | 입력 토큰 | 출력 토큰 | reasoning 토큰 | 추정 비용 | 평균 응답 시간 |
|---|---:|---:|---:|---:|---:|
| A | 1,778,012 | 57,028 | 2,852 | $3.3519798 | 8.70초 |
| C | 3,751,396 | 58,242 | 3,077 | $6.5861422 | 8.82초 |

입력 토큰비는 2.11배, 이번 성공 요청 추정 비용비는 1.96배다. 캐시와 503 중단·재개의 영향이 있으므로 모든 실행에서 동일한 비용비가 난다고 예측하지 않는다. 문맥 JSON의 문항당 중앙값은 A 36,352바이트/C 59,334바이트, 최대는 A 64,813바이트/C 163,836바이트다. 최종 선택 12개를 고정한 채 같은 선택 문서의 표 정보 전달량을 늘린 결과이며, 후보 회수율 개선 실험이 아니다.

308개 응답의 출처 ID·스키마 검사는 모두 통과했고, 요청/응답/usage/봉인/보존의 기술 검사 2,206개가 통과했다. 이는 의미 정확도 PASS와 별개다. 완료 색인을 처음 합칠 때 watchdog 종료기록 작성보다 앞서 읽어 로컬 후처리가 중단된 일이 있었다. 부분 색인은 별도 보존하고 종료 후 원본 그대로 다시 합쳤으며 추가 API 호출은 없었다(postprocess_incident.json (`postprocess_incident.json`, local artifact not included)).

## 기존 환경 보존

최종 읽기 전용 검사에서 보호 대상 6,334개 파일의 바이트 해시가 실행 전과 모두 같았다. `.env`와 사용 중인 v12 store의 11개 파일도 동일하며, Git HEAD·index·status·staged diff가 모두 유지됐다. 이번 작업은 SQLite 클라이언트로 활성 store를 열지 않았고, SQLite 내부 파일 변경도 관측되지 않았다. 따라서 논리 데이터만 같다는 추정이 아니라 해당 보호 파일들의 바이트 보존을 확인한 결과다. 원본 데이터베이스에 질의를 실행한 별도 의미 검증은 하지 않았다. 결과는 final_preservation.json (`final_preservation.json`, local artifact not included)에 기록했다.

새 파일과 문서 수정은 이 실험의 무시된 결과 폴더에만 한정했다. 기존 구현·미커밋 변경·다른 실험 산출물은 보존했으며, `.env` 변경·앱 재시작·커밋·push는 수행하지 않았다.

## 해석의 한계와 검증

동결한 기준을 사용해 원본 응답을 봉인한 뒤 네이티브 assistant가 조건명·반복 번호를 가린 입력을 검토했다. 문맥의 길이·표현에서 조건을 추측할 수 있으므로 완전한 맹검이 아니다. 독립 인간 정답이나 다른 모델 계열의 검증으로 주장하지 않는다. 모든77문항은 개발 과정에 노출됐고, 나머지65문항도 새 holdout이 아니다. 반복2회는 독립 문항 수를 두 배로 만들지 않는다. root의 판정 조정은 기존 기준과 실제 출처 인용으로 남기며 초기 판정은 보존한다.

통계 오류 점검11/11: (1) 전체·pilot12·other65·반복별 방향을 분리, (2) 문항 집계를 새 기업 일반화로 확장하지 않음, (3) 개발 노출 표본의 선택 편향 인정, (4) 결과를 본 뒤 평가군 재선택하지 않음, (5) 거절 기저 비율을 분리, (6) 과거 실패와 비교하는 대신 이번 A를 새로 생성, (7)503실패와 재개 기록을 포함하고 모든 성공 답변 유지, (8) 유리한 문항만 보고하지 않고 전체77개 제시, (9) 여러 선행 실험이 있었음을 인정하고 이번 기준 사전 동결, (10) 표현·근거량의 결합 처치를 개별 원인의 효과로 주장하지 않음, (11) 처치가 답변보다 앞서지만 일반적 인과·성능 우월성 주장은 하지 않음. 유의성 검정이나 독립 반복 가정의 신뢰구간은 제시하지 않는다.

## 전체77문항 판정표

각 칸은 정확도/완전성/충실도이며 P=PASS, ~ =PARTIAL, F=FAIL, ?=AMBIGUOUS, H=HOLD(null)이다. 실제 단위별 누락과 판정 근거는 paired_results.json 및 masked_review 원본 검토에 있다.

| 문항 | 평가군 | A r1 | C r1 | A r2 | C r2 |
|---|---|---|---|---|---|
| KBF_T2_018 | common_answerable | P/P/P | P/P/P | P/P/P | P/P/P |
| POS_T4_059 | refusal | P/P/P | P/P/P | P/P/P | P/P/P |
| SKH_T3_080 | common_answerable | P/P/P | P/P/P | P/P/P | P/P/P |
| MIX_T1_046 | common_answerable | P/P/P | P/P/P | P/P/P | P/P/P |
| NAV_T3_007 | common_answerable | P/P/P | P/P/P | P/P/P | P/P/P |
| MIX_T3_048 | common_answerable | P/P/P | P/P/P | P/P/P | P/P/P |
| SAM_T2_078 | common_answerable | P/P/P | P/P/P | P/P/P | P/P/P |
| CEL_T1_013 | common_answerable | P/P/P | P/P/P | P/P/P | P/P/P |
| CEL_T4_016 | refusal | P/P/P | P/P/P | P/P/P | P/P/P |
| KAK_T3_076 | refusal | P/P/P | P/P/P | P/P/P | P/P/P |
| HYU_T2_010 | diagnostic_or_hold | H/H/P | H/H/~ | H/H/P | H/H/P |
| HYU_T3_011 | common_answerable | P/P/P | P/P/P | P/P/P | P/P/P |
| MIX_T2_047 | common_answerable | P/P/P | P/P/P | P/P/P | P/P/P |
| MIX_T4_049 | refusal | P/P/P | P/P/P | P/P/P | P/P/P |
| LGE_T4_053 | refusal | P/P/P | P/P/P | P/P/P | P/P/P |
| POS_T1_057 | common_answerable | ~/~/P | ~/~/P | ~/~/P | ~/~/P |
| SKH_T1_060 | common_answerable | ~/~/P | ~/~/P | ~/~/P | ~/~/P |
| NAV_T1_030 | common_answerable | P/P/P | P/P/P | P/P/P | P/P/P |
| NAV_T4_008 | refusal | P/P/P | P/P/P | P/P/P | P/P/P |
| NAV_T4_033 | refusal | P/P/P | P/P/P | P/P/P | P/P/P |
| SAM_T3_028 | common_answerable | P/P/P | P/P/P | P/P/P | P/P/P |
| SAM_T4_070 | refusal | P/P/P | P/P/P | P/P/P | P/P/P |
| CEL_T2_039 | common_answerable | P/P/P | P/P/P | P/P/P | P/P/P |
| CEL_T4_041 | refusal | P/P/P | P/P/P | P/P/P | P/P/P |
| MIX_T4_024 | refusal | P/P/P | P/P/P | P/P/P | P/P/P |
| KAK_T3_055 | diagnostic_or_hold | H/H/P | H/H/P | H/H/P | H/H/P |
| HYU_T3_072 | common_answerable | F/F/P | ~/~/P | F/F/P | ~/~/P |
| HYU_T4_012 | refusal | P/P/P | P/P/P | P/P/P | P/P/P |
| HYU_T4_037 | refusal | P/P/P | P/P/P | P/P/P | P/P/P |
| KBF_T1_017 | diagnostic_or_hold | H/H/P | H/H/P | H/H/P | H/H/P |
| KBF_T2_043 | diagnostic_or_hold | H/H/P | H/H/P | H/H/P | H/H/P |
| KBF_T3_019 | common_answerable | P/P/P | P/P/P | P/P/P | P/P/P |
| KBF_T3_044 | common_answerable | P/P/P | P/P/P | P/P/P | P/P/P |
| KBF_T4_020 | common_answerable | P/P/P | P/P/P | P/P/P | P/P/P |
| KBF_T4_045 | refusal | P/P/P | P/P/P | P/P/P | P/P/P |
| MIX_T3_025 | common_answerable | P/P/P | P/P/P | P/P/P | P/P/P |
| LGE_T1_051 | common_answerable | P/P/P | P/P/P | P/P/P | P/P/P |
| LGE_T2_052 | common_answerable | P/P/P | P/P/P | P/P/P | P/P/P |
| LGE_T4_077 | refusal | P/P/P | P/P/P | P/P/P | P/P/P |
| POS_T1_075 | diagnostic_or_hold | H/H/~ | H/H/~ | H/H/~ | H/H/~ |
| POS_T2_058 | diagnostic_or_hold | H/H/P | H/H/P | H/H/P | H/H/P |
| SKI_T1_068 | common_answerable | ~/~/~ | P/P/~ | ~/~/~ | P/P/~ |
| SKI_T2_069 | common_answerable | P/P/P | P/P/P | P/P/P | P/P/P |
| MIX_T4_065 | refusal | P/P/P | P/P/P | P/P/P | P/P/P |
| SKH_T2_061 | diagnostic_or_hold | H/H/P | H/H/P | H/H/P | H/H/P |
| MIX_T2_022 | common_answerable | P/P/P | P/P/P | P/P/P | P/P/P |
| MIX_T3_063 | diagnostic_or_hold | H/H/P | H/H/P | H/H/P | H/H/P |
| NAV_T1_005 | common_answerable | P/P/P | P/P/P | P/P/P | P/P/P |
| NAV_T1_071 | common_answerable | P/P/P | P/P/P | P/P/P | P/P/P |
| NAV_T2_006 | common_answerable | P/P/P | P/P/P | P/P/P | P/P/P |
| NAV_T2_031 | common_answerable | P/P/P | P/P/P | P/P/P | P/P/P |
| NAV_T3_032 | common_answerable | P/P/P | P/P/P | P/P/P | P/P/P |
| MIX_T1_021 | common_answerable | P/P/P | P/P/P | P/P/P | P/P/P |
| MIX_T4_062 | refusal | F/F/? | F/F/? | F/F/? | F/F/? |
| SAM_T1_001 | common_answerable | P/P/P | P/P/P | P/P/P | P/P/P |
| SAM_T1_026 | common_answerable | P/P/P | P/P/P | P/P/P | P/P/P |
| SAM_T2_027 | diagnostic_or_hold | H/H/P | H/H/? | H/H/P | H/H/? |
| SAM_T3_003 | common_answerable | P/P/P | P/P/P | P/P/P | P/P/P |
| SAM_T4_004 | common_answerable | P/P/P | P/P/P | P/P/P | P/P/P |
| SAM_T4_029 | refusal | P/P/P | P/P/P | P/P/P | P/P/P |
| CEL_T1_038 | common_answerable | P/P/P | P/P/P | P/P/P | P/P/P |
| CEL_T2_014 | common_answerable | P/P/P | P/P/P | P/P/P | P/P/P |
| CEL_T2_073 | diagnostic_or_hold | H/H/P | H/H/P | H/H/P | H/H/P |
| CEL_T3_015 | common_answerable | P/P/P | P/P/P | P/P/P | P/P/P |
| CEL_T3_040 | common_answerable | P/P/P | P/P/P | P/P/P | P/P/P |
| MIX_T3_050 | common_answerable | P/P/P | P/P/P | P/P/P | P/P/P |
| KAK_T1_054 | common_answerable | P/P/P | P/P/P | P/P/P | P/P/P |
| KAK_T4_056 | refusal | P/P/P | P/P/P | P/P/P | P/P/P |
| KAB_T1_066 | common_answerable | P/P/P | P/P/P | P/P/P | P/P/P |
| KAB_T3_067 | common_answerable | P/P/P | P/P/P | ~/P/~ | P/P/P |
| HYU_T1_009 | common_answerable | P/P/P | P/P/P | P/P/P | P/P/P |
| HYU_T1_034 | common_answerable | P/P/P | P/P/P | P/P/P | P/P/P |
| HYU_T2_035 | diagnostic_or_hold | H/H/P | H/H/P | H/H/P | H/H/P |
| HYU_T3_036 | diagnostic_or_hold | H/H/P | H/H/P | H/H/P | H/H/P |
| HYU_T4_079 | refusal | P/P/P | P/P/P | P/P/P | P/P/P |
| MIX_T1_064 | common_answerable | P/P/P | P/P/P | P/P/P | P/P/P |
| MIX_T3_023 | common_answerable | P/P/P | P/P/P | P/P/P | P/P/P |

## 산출물

- protocol.json / freeze.json / rubric.json: 생성 전 조건·기준
- live/ 및 resume01/live/: 두 구간의 원본 요청·응답·비용·봉인
- combined/: 원본을 보존한308개 답변 색인과 연결 검사
- review_mapping.json / masked_review/: 답변 연결 및 초기 검토
- adjudicated_reviews.json / summary.json / paired_results.json: 최종 판정과 전체 집계
- final_preservation.json: 보호 파일·Git·.env·v12 store 검증
- final_aggregation_audit.json: 별도 네이티브 검토의 원본 연결·독립 재집계·보고서 대조 기록
