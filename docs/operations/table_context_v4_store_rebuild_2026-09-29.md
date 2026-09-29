# v4 표 문맥 수정 후 11개 보고서 저장소 재구축

2026-09-29. **COMPLETE_READY / PASS_ACTIVATED**.
[파서 수정](../evaluation/table_context_hint_preservation.md)의 원문 보존 효과를 새 저장소에 반영했다.
기존 v3 저장소를 보존하고, 검증 후 앱의 두 저장소 설정만 전환했다. 답변 생성·정답률 평가는 **NOT_RUN**이다.

## 저장소와 입력

- 경로: `data/app_full11_2023_v4_20260929`
- Collection: `dart_reports_v4_full11_2023`
- Parser: `financial_parser_v4_label_only_table_context`
- Profile: `structural_selective_v2_prefix_2500_320`, chunk 2500/320
- Embedding: `text-embedding-3-large`, 3072차원; HNSW l2
- 기존 11개 회사의 동일한 2023 사업보고서 원본 SHA 검증, 473개 절, timeout fallback 0
- 15,595개 청크/벡터, 473 parents, 13,879 table payloads

재파싱은 시간 제한 0을 명시했고 20초 heartbeat를 남겼다. 새 보고서 수집이나
답변용 LLM을 통한 ingest는 없었다. 기존 앱 기본 시간 제한에서의 처리 시간을 증명하지 않는다.

| 회사 | 새 청크 | 벡터 재사용 | 새 벡터 필요 청크 |
| --- | ---: | ---: | ---: |
| KB금융 | 2,458 | 2,379 | 79 |
| POSCO홀딩스 | 1,823 | 1,703 | 120 |
| SK하이닉스 | 1,037 | 941 | 96 |
| NAVER | 1,389 | 1,092 | 297 |
| 삼성전자 | 1,064 | 976 | 88 |
| 셀트리온 | 1,254 | 1,088 | 166 |
| 카카오 | 1,454 | 1,329 | 125 |
| 현대자동차 | 1,265 | 1,000 | 265 |
| LG에너지솔루션 | 1,039 | 784 | 255 |
| SK이노베이션 | 2,311 | 1,934 | 377 |
| 카카오뱅크 | 501 | 479 | 22 |
| 합계 | 15,595 | 13,705 | 1,890 |

이전 v3 재구축의 고정 corpus와 벡터 파일을 읽었다. 재사용/신규 벡터 파일에서
완성한 v3 벡터를 당시 전체 저장 검증 해시와 다시 대조했다. 같은 filing의
**전체 embedding 입력이 정확히 같은 경우만** 재사용했다. 청크 ID나 숫자 일치로
벡터를 옮기지 않았다. 기존 Chroma 저장소는 재사용 과정에서 열지 않았다.

## 호출과 비용

- 새 입력 1,890회분을 중복 제거해 1,877개 텍스트, 실제 embedding 호출 **30회**
- 실제 입력 usage **1,230,647 tokens**, 추정 비용 **USD0.15998411**
- 전체 사전 예약 USD0.16048331, 에이전트가 정한 작업 상한 USD2
- 오류·자동 재시도·자동 resume 0, 미결 예약 0
- Embedding 121.76초, 저장/전체 readback 250.04초; 준비·검색 검증 시간 제외
- 새 query embedding·답변·judge·외부 문서 수집 호출 0

사용자의 이번 재구축 지시에 따른 별도 실행이며 이전 실험 예산을 재사용하지 않았다.
비용은 [공식 embedding 요율](https://developers.openai.com/api/docs/models/text-embedding-3-large)
(2026-09-29 확인, 100만 입력 tokens당 USD0.13)과 응답 usage로 산정한 추정치다. 청구서 검증은 아니다.

## 검증

1. 관련 parser/store 테스트 31개, budget/manifest 테스트 15개 통과. 제품 source 변경은 없다.
   직전 v4 수정의 전체 2,154개 통과 기록은 별도이며 이번에 전체 suite를 다시 실행한 것은 아니다.
2. 실제 임시 Chroma 두 filing 계약 검사와 대표 SDK mock 2개 통과.
   전체 30개 배치의 입력 hash·token 수·8192 한도·총비용을 사전 검사했다.
3. 새 저장소를 닫고 다시 열어 **15,595개 전체** ID·텍스트·metadata·float32 벡터를
   기대 해시와 대조했다. graph·parents·table payload는 기대 객체와 일치했다.
   검증 후 manifest를 마지막에 발행했다.
4. 현대자동차의 두 회계정책 표와 LG에너지솔루션의 두 관련 표에서
   **15개 원문 청크 조각 모두** 저장된 graph에서 확인되고 table payload가 조회된다.
5. 보고서별 scope를 적용한 dense self-vector probe 11개, BM25 smoke 11개 통과.
   저장된 KB·삼성 신용평가 소제목의 이전 수정도 유지된다.
6. 임시 설정으로 실제 FastAPI startup·HTTP readiness·회사 목록 검사 통과.
   기존의 정확한 질문 벡터를 재사용해 실제 hybrid 검색 7회 실행했다.
7. 검증 후 `.env`의 `DART_STORE_PATH`, `DART_COLLECTION_NAME`만 전환했다.
   별도 새 프로세스에서 store override 없이 실제 앱 startup/readiness HTTP 200을 확인했다.
   상시 서버는 시작하지 않았다. 기존 v3 저장소 및 그 외 보호 입력은 변경하지 않았다.

마지막 준비 상태 검사의 첫 실행은 설정 전환 프로세스가 끝나기 전에 시작되어
`rollback.json` 생성 전 파일 읽기에서 종료됐다. 앱 startup이나 provider 호출 전의
검증 실행 순서 오류였다. 전환 완료를 확인하고 무호출 검사만 다시 실행했으며,
첫 실패 로그와 최종 로그를 각각 보존했다. 유료 배치 재시도나 중복 설정 전환은 없다.

## 검색 관측과 한계

실행 전에 고정한 7개 질문 중 7개에서 비교 대상 원문이 top8에 포함됐다.
앞선 여섯 질문은 이전 source body 포함 여부, MIX_T3_023은 복구한 배출권 회계 문구의
위치를 확인했다. 이는 원문 위치 비교이며 문항별 근거 충분성·답변 정확성 평가가 아니다.

| 고정 질문 | 비교 대상 원문 top8 |
| --- | --- |
| G02 | 포함 |
| S01 | 포함 |
| G01 | 포함 |
| G04 | 포함 |
| G05 | 포함 |
| G08 | 포함 |
| MIX_T3_023 | 포함 |

문항·검색 설정은 결과에 맞춰 변경하지 않았다. self-vector와 회사명 smoke는
검색 경로·scope 검사이며 실제 질문의 회수율이 아니다. 이전 strict11/12 답변 결과와
77문항 v3 감사 기록은 그대로이고 새 정답률로 바꾸지 않았다.

## 복구와 산출물

이전 `data/app_full11_2023_20260929` / `dart_reports_v3_full11_2023`은 보존했다.
`rollback.json`에는 두 설정의 이전 행과 변경 전후 dotenv hash만 기록했다.
그 두 행을 원복했을 때 이전 파일 바이트 전체가 재현되는지도 검사했다.

실행 기록: `benchmarks/results/table_context_v4_store_rebuild_2026-09-29/`.
고정 preparation/admission, 사용 완료 marker, mock/live budget, 전체 저장 해시,
복구 원문 조회, 실제 검색 출력과 앱 연결/준비 상태를 남겼다.
대용량 corpus·vectors·원시 embedding 요청/응답:
`D:/CodexArtifacts/dart-rag-agent/table_context_v4_store_rebuild_2026-09-29/`.
기존 실험 기록을 덮어쓰거나 모델 재평가를 자동 실행하지 않았다.
