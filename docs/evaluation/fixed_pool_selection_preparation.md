# 실제 후보를 고정한 근거 선택 비교

2026-09-28. 사용자 요청에 따른 focused 단회 비교. 개발에 노출된 사례이며 미노출 holdout이 아니다. 제품 runtime 변경 없음.

[실패 분석](structure_full77_failure_boundaries.md)에서 후보에 필요한 근거가 있지만 top8에서 탈락한 사례를 대상으로 한다. 기존 일반 의미 선택 지시를 최대3개에서8개로 바꿔 재사용한다. 새 자체 reranker나 회사별 규칙은 만들지 않는다.

## 실행 전에 고정한 설계

| 항목 | 고정 내용 |
| --- | --- |
| 질문 | SKH_T3_080, HYU_T3_011, SAM_T3_028, CEL_T2_039, SKH_T2_061, CEL_T3_040 |
| 조건 | 각 질문의 A 일반 텍스트와 C 문서+표: 6문항 × 2표현 =12입력 |
| 선택 이유 | 각 질문에서 A/C 중 하나는 기존 성공, 하나는 선택 누락 실패: 실패 회복6개와 성공 회귀6개를 함께 확인 |
| 후보 | 원래 dense16/BM25 24의 합집합 전체; source text/context/범위 그대로, 재검색 없음 |
| 기준선 | 저장된 RRF top8을 사용해 **답변을 새로 생성**; 예전 답변은 참고용 |
| 비교 방식 | 질문과 후보 전체만 보고 일반 의미 관련성으로 최대8개 선택 후 동일 답변 생성 |
| selector 입력 | 후보 순위/점수·과거 성공 여부·정답·근거 주석 미제공. ID hash 기반 고정 순서 |
| 모델 | 선택/답변 모두 기존 gpt-5.6-terra, low, Standard, 출력8192 |
| 답변 | 기존 정확한 요청 본문/스키마/프롬프트를 사용하며 documents만 변경 |
| 전달 | 두 방식 모두 최대8개, packet65536 UTF-8 bytes; 초과 source는 원문을 자르지 않고 제외 |
| 호출 순서 | 각 입력에서 selector1회, 이후 RRF/semantic 답변 순서를 입력마다 교대 |
| 호출 | 선택12 + 답변24 = 최대36; embedding/유료 judge/새 store0 |

두 조건의 최종 답변 예산은 같다. 의미 선택은 추가 모델 호출을 사용하므로 **동일 총비용 비교는 아니다**. 선택 비용·시간과 답변 비용·시간을 분리한다. 실제 선택 개수/전달 byte도 같다고 가정하지 않는다. 모델의 충분성 선언은 답변 모델에 전달하지 않는다.

## 사전 판정과 종료 기준

- 기존 동결 rubric의 정확성·요청 완전성·실제 인용 지지를 적용한다. 숫자·주체·연도·연결/별도·단위·계산을 원문과 대조한다. 원래 reference가 불완전하면 원문 기반 대체를 따로 공개하고 원본을 덮어쓰지 않는다.
- 모든 요청 근거가 최종 packet에 있는지와 답변이 이를 제대로 사용하는지 구분한다. 대표 누락 chunk 회복만으로 전체 근거 충분/답변 성공을 판정하지 않는다.
- 과거 실패6개에서 회복, 과거 성공6개에서 회귀, 새 RRF/semantic 답변의 paired 결과를 각각 보고한다. 기존 답변과 새 기준선의 차이도 공개한다.
- 충분성 선언은 보조 관측이다. 실제 packet/source 검토가 우선한다. 모델 선언을 정답으로 사용하지 않는다.
- 모델 출력 후 source 인용을 assistant가 검토한다. 독립 사람 평가 또는 blind gold 검증이 아니며, 선택된6문항의 비율을 full77 정확도로 확장하지 않는다.
- 한 번씩 생성한 뒤 종료한다. 결과에 따른 프롬프트/후보/표본 조정, paid retry/resume, 자동 전체 평가 또는 제품 채택은 하지 않는다.
- ERROR/NOT_RUN은 품질 실패와 별도로 보고한다. 첫 transport/usage/형식/외부ID/보존 실패에서 중단한다.

## 비용과 무호출 검증

[공식 OpenAI 가격](https://developers.openai.com/api/docs/pricing)을 2026-09-28 확인했다. Terra Standard 입력2/출력12달러 per1M tokens이며, 예약은 cache write까지 고려해 입력2.5를 적용하고 할인은 반영하지 않는다. 단일 입력 byte 기반 예약은200000 이내다. 실제 청구서가 아닌 보수적 추정이다.

전체36회 최대 예약 **USD11.9124865**, 새 실행 상한 **USD12**. 사용자의 이번 진행 지시를 이 focused 단회 범위에 적용하며, 이전 실험의 소비된 승인을 재사용하지 않는다. 90초 timeout, SDK retry0, 20초 heartbeat, 실행 디렉터리/consumed 기록은 배타 생성한다.

실험 디렉터리 `benchmarks/results/fixed_pool_selection_2026-09-28/`는 Git ignored다. `panel.json`과 별도 `evaluation_only.json`, 보호된 source/리뷰/정확한 baseline 요청 hash를 manifest에 고정했다. selector/answer 작성 경로는 평가용 정답을 읽지 않는다.

실제 SDK·mock HTTP·socket 차단 rehearsal36/36 통과. 비용 초과, 요청 변조, 외부 선택 ID, 외부 인용 ID, HTTP503, usage 누락, incomplete 응답의7개 중단 control 통과. 비용/변조는 HTTP 전에 차단했다. 이는 실제 모델 품질이나 provider 허용의 증거가 아니다.
