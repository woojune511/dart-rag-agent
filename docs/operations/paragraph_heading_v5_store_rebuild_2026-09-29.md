# v5 문단 소제목 수정 후 11개 보고서 저장소 재구축

2026-09-29. **COMPLETE_READY / PASS_ACTIVATED**.
[문단 소제목 수정](../evaluation/paragraph_heading_style_fix.md)을 새 저장소에 반영하고,
전체 readback·검색·답변 입력 전달 검증 후 앱 설정을 전환했다. 실제 답변 품질 평가는 **NOT_RUN**이다.

## 입력과 저장소

- 같은 11개 회사의 2023 사업보고서, 473개 절, timeout fallback 0
- `data/app_full11_2023_v5_20260929` / `dart_reports_v5_full11_2023`
- Parser `financial_parser_v5_inherited_heading_style`
- Profile `structural_selective_v2_prefix_2500_320`; chunk 2500/overlap 320
- `text-embedding-3-large`, 3072차원, HNSW l2
- **15,608 청크/벡터**, 473 parents, 13,892 table payloads
- 기존 v4 Chroma 저장소는 열지 않고 보존했다. 이전 고정 corpus/벡터 및 저장 검증 해시를 대조했다.

| 회사 | 청크 | 기존 벡터 재사용 | 새 벡터 |
| --- | ---: | ---: | ---: |
| KB금융 | 2,458 | 2,458 | 0 |
| POSCO홀딩스 | 1,824 | 1,812 | 12 |
| SK하이닉스 | 1,039 | 1,035 | 4 |
| NAVER | 1,390 | 1,372 | 18 |
| 삼성전자 | 1,064 | 1,064 | 0 |
| 셀트리온 | 1,255 | 1,253 | 2 |
| 카카오 | 1,454 | 1,454 | 0 |
| 현대자동차 | 1,265 | 1,265 | 0 |
| LG에너지솔루션 | 1,039 | 1,039 | 0 |
| SK이노베이션 | 2,317 | 2,303 | 14 |
| 카카오뱅크 | 503 | 497 | 6 |
| 합계 | 15,608 | 15,552 | 56 |

같은 filing의 **전체 embedding 입력이 정확히 같은 경우만** 재사용했다.
본문만 같고 소제목 prefix가 바뀐 입력은 새로 embedding했다. ID 일치로 벡터를 옮기지 않았다.
파싱은 명시적 시간 제한 0, 20초 heartbeat로 실행했다. 원문 수집·LLM ingest는 없다.

## 호출과 비용

- 신규 고유 입력 56개, embedding **1회**, 실제 usage **33,819 tokens**
- 추정 비용 **USD0.00439647**, 전체 사전 예약 USD0.00441311, 별도 에이전트 운영 상한 USD2
- 오류·재시도·resume·미결 예약 0; 새로운 query embedding·answer·judge 호출 0
- embedding 5.53초, 저장/전체 readback 187.67초; 준비·검색 검증 시간 제외

비용은 2026-09-29 확인한 [공식 standard embedding 요율](https://developers.openai.com/api/docs/pricing)
(100만 입력 tokens당 USD0.13)과 응답 usage로 산정했다. 청구서 대조가 아니다.
새 배치는 이번 사용자 지시에 따른 별도 실행이며 이전 실험의 승인/예산을 재사용하지 않았다.

## 검증

1. 시작 시 직전 파서 수정의 seal 75개 파일 검증. 파서/저장소 관련 37개와 budget/manifest 15개 테스트 통과.
   직전 전체2,163 테스트 통과는 그 수정의 기록이며 이번에 전체 suite를 재실행한 것은 아니다.
2. 실제 임시 Chroma 두 filing 계약 검사와 SDK mock 1회 통과. 전체 입력 hash·token 수·한도·비용을 사전 검사했다.
3. **15,608개 전체** ID·본문·metadata·float32 벡터를 닫고 다시 연 저장소에서 기대 해시와 대조했다.
   graph·parents·table payload 객체를 검증한 뒤 manifest를 마지막에 발행했다.
4. NAVER 직원 주석의 본문은 그대로이고 소제목은 `마. 직원 등 현황`이다.
   원본 XML `/DOCUMENT/BODY/SECTION-1[9]/SECTION-2[1]/P[9]` 연결이 projection과 저장 graph/payload에서 유지된다.
   이전 `라. 타회사 임원겸직 현황`이 이 주석의 embedding prefix와 답변 입력에 남지 않는다.
5. 앞서 복구한 현대자동차·LG에너지솔루션의 회계정책 4개 표/15개 원문 조각과 KB·삼성 신용평가 소제목도 유지된다.
6. 11개 scope별 dense self-vector probe와 BM25 smoke 통과. 정확히 동일한 저장 query vector를 사용한
   실제 hybrid 검색 7회 모두 비교 원문이 top8에 있다. 질문/벡터의 기존 seal 17개도 검증했다.
7. 실제 SimpleRagAgent에서 G04→G02→G04를 실행해 cached 검색과 packet 생성을 확인했다.
   모델 대신 recorder를 써서 새 유료 호출 없이 두 NAVER packet에 직원 주석과 올바른 소제목이 있고,
   중간에 다른 질문을 거쳐도 두 packet이 동일함을 확인했다. 모의 답변의 품질은 평가하지 않았다.
8. 실제 FastAPI startup·회사 목록·readiness HTTP200 검증 후 `.env`의 두 store 설정만 전환했다.
   별도 프로세스에서 store override 없이 startup/readiness를 재확인했다. 상시 서버는 시작하지 않았다.
9. 보호 입력 738개는 두 dotenv 설정 외에 변경되지 않았다. 다른 dotenv bytes의 복원 hash도 검증했다.

## 해석과 산출물

7/7은 기존에 본 질문의 원문 위치 확인이지 근거 충분성 또는 답변 정답률이 아니다.
v4의 7문항×2회 14/14 결과는 과거 기록이며 v5 성능으로 옮겨 주장하지 않는다.
문단 스타일 수정이 모든 보고서 소제목을 고쳤다는 주장이나 새 의미 해석/계산 검증도 없다.
제품 코드·프롬프트·검색 정책은 이번 작업에서 변경하지 않았다. 후속 유료 평가는 자동 실행하지 않았다.

- 기록: `benchmarks/results/paragraph_heading_v5_store_rebuild_2026-09-29/`
- bulk: `D:/CodexArtifacts/dart-rag-agent/paragraph_heading_v5_store_rebuild_2026-09-29/`
- 준비/비용: `preparation.json`, `admission.json`, `pricing.json`, `live_embedding_result.json`, `embedding_audit.json`
- 저장/검색: `stored_record_hashes.json`, `stored_witness.json`, `stored_witness_validation.json`, `app_searches.json`
- 전달/전환: `heading_packets.json`, `heading_delivery.json`, `rollback.json`, `active_verification.json`
- 최종 확인: `completion.json`, `completion_seal.json`; 이전 로그·저장소·실험 결과 보존
