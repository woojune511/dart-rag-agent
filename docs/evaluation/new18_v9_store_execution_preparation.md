# v9 별도 평가 store와 새 18문항 실행 준비

2026-10-16. **PREPARED_NOT_EXECUTED**. 실행 조건·원문 projection·임베딩 배치·비용 상한·기존 답변 비교표를 준비했다. 이번 작업은 외부 모델·임베딩·judge·DART 호출 **0회**, store 생성·개방 **0회**이며 `.env`를 변경하거나 자격증명을 읽지 않았다. 공식 요금 문서 조회만 별도로 했다.

**권장 실행 범위는 총 95회·USD 10.25·2시간 30분 상한이다. 새 v9 store에서 18문항을 검색하고, 질문별 동일한 최종 8개 문맥으로 답변을 2회 생성한다.** 기존 답변을 다시 생성하는 A/B는 포함하지 않는다.

## 비교 대상과 해석

주 비교 기준은 [최근 8개 문맥 답변](new18_rrf_window_answer_result.md)의 36개다. 최초 [v6 실행 결과](new_report_user_eval_result.md)도 보조 기준으로 함께 보고해 유리한 과거 결과만 고르지 않는다. 최근 12개 문맥 답변은 U03·U16·U14 오류의 참고 자료이며, 문맥 수가 다른 만큼 동일 조건의 개선 점수에 합치지 않는다.

| 기존 기준 | 엄격 통과 | 두 번 모두 엄격 통과 | 새 결과와의 용도 |
|---|---:|---:|---|
| 최근 RRF 8개 | 23/36 | 11/18 | 주 비교 |
| 최초 v6 RRF 8개 | 18/36 | 7/18 | 별도 보조 비교 |
| 최근 RRF 12개 | 24/36 | 11/18 | 오류·상충 근거 참고 |

최초 v6와 최근 8개 조건의 요청 본문은 **18/18 동일**하지만 생성 결과는 달랐다. 따라서 이번 차이를 파서만의 인과 효과로 단정하지 않는다. 같은 모델 alias라도 내부 snapshot 동일성은 보장되지 않고 임베딩도 새로 만든다.

기존 답변 store는 v6다. 현재 v9까지는 표제·기간 연결, 넓은 표 축, 헤더 없는 단일 행, 기간 중복과 행 단위 수정이 누적됐다. 새 projection은 기존과 청크 ID·순서가 같지만 **검색 입력 635개·본문 17개**가 달라졌다. 이번 비교는 **v7–v9 누적 수정 이후의 실제 답변 변화**이며, v9의 마지막 두 수정만 분리한 실험이 아니다. 특히 cell/value 단위 metadata는 기본 답변 packet에 직접 노출되지 않으므로 단위 교정만으로 답변이 좋아질 것이라고 전제하지 않는다.

## 고정 실행 조건

| 항목 | 조건 |
|---|---|
| 데이터 | 원래 질문 18개·33개 필수 그룹·gold/rubric/예외 판정 해시 고정 |
| 원문 | HD현대일렉트릭·오리온·호텔신라의 기존 2025 사업보고서 3개, 재수집 없음 |
| 파서 | `financial_parser_v9_period_labels_row_units`, chunk2500/overlap320, section budget0, fallback 없음 |
| corpus | 전체 3,645청크·139 parents. 정답이 없는 문맥도 포함 |
| 새 store | `benchmarks/results/new18_v9_store_eval_2026-10-16/live_v1/store`, collection `new18_parser_v9_20261016`; 경로가 이미 존재하면 중단 |
| 임베딩 | `text-embedding-3-large`, 3072차원. 전체 문서와 정확한 질문 18개를 새로 임베딩; 기존 벡터 복사 없음 |
| 배치 | 순서 유지, 최대64개/80,000tokens, 입력별8,192 이하. token 배열·입력 해시 확인, 중복 제거 없음 |
| 검색 | 원래 명시적 report_scope, Dense16·BM25최대24, 동일 가중치 RRF(k=60), 최종8개 |
| 검색 옵션 | 기존 tokenizer·공통 접두어·stopwords 유지. `까지` 제외 실험·가중치 조정·reranker·별도 caption sidecar 없음 |
| 반복 | 실제 검색 18회 후 문항별 packet/request 봉인. 두 반복에 동일 packet 사용; U01→U18, U18→U01 |
| 생성 | `gpt-5.6-terra`, reasoning low, 원래 prompt, Responses API, strict RagAnswer, output8192, default tier, store=false |
| 미설정 | temperature/top_p/seed/truncation/cache key/tools/previous response 추가 없음 |
| 실행 | 동시성1, 요청 timeout최대90초, retry0, 30초 heartbeat, 전체9000초 상한 |
| 추가 호출 | Planner·Compiler·context generation·judge·probe·유료 token count·reranker·DART 모두0 |

새 store에는 준비한 metadata·parents·구조화 표를 함께 보존한다. 문서/벡터/metadata readback, 3,645개 ID, BM25 전체 corpus, manifest v9, source/structure integrity를 검증한 뒤 검색한다. 이 로컬 단계는 이미 받은 새 벡터만 사용해 추가 임베딩 호출을 막는다. 활성 store와 기존 평가 store는 열거나 수정하지 않으며 `.env`의 store 경로도 바꾸지 않는다.

Dense·BM25 후보, 점수, RRF 순위, 선택·누락 출처, 실제 packet/request를 저장한다. 기존 청크 ID를 강제로 최종 문맥에 넣거나 gold로 순위를 선택하지 않는다. 실제 최종8개 중 바이트 한도로 제외되는 출처가 있으면 **생성 전에 중단**한다.

## 예상 비용과 호출 상한

2026-10-16 공식 문서 기준 Standard/global 요율은 [Terra](https://developers.openai.com/api/docs/models/gpt-5.6-terra) 입력/캐시읽기/캐시쓰기/출력 **USD 2/0.2/2.5/12 per1M**, [임베딩](https://developers.openai.com/api/docs/models/text-embedding-3-large)은 **USD 0.13 per1M**이다. [캐시쓰기는 일반 입력비에 가산하지 않는다](https://developers.openai.com/api/docs/guides/prompt-caching). 세금·환율·실제 청구서 대조는 제외한다.

| 구분 | 호출 상한 | 입력 및 비용 |
|---|---:|---|
| 문서 임베딩 | 58 | 2,665,693 tokens |
| 질문 임베딩 | 1 | 757 tokens, 18개 질문을 한 번 생성해 재사용 |
| 답변 생성 | 36 | 18문항 × 2회 |
| **합계** | **95** | **최대 예약 $10.24653482 ≤ 상한 $10.25** |

임베딩의 로컬 계산 예상액은 **$0.3466385**다. 입력당128tokens 여유를 더하면 3,135,314tokens, 예약액 **$0.40759082**다. 최대 단일 입력3,519·최대 배치78,921tokens로 준비 한도 안이다.

생성은 매 호출 입력70,000·출력8,192tokens를 예약한다. 모든 입력을 더 높은 캐시쓰기 요율로 잡고 reasoning은 출력에 한 번만 포함한다.

`36 × (70,000 × 2.50 + 8,192 × 12) / 1,000,000 = $9.838944`

예상 비용은 최대 예약액보다 작다. 최근 8개 문맥의 실제 사용량이 다시 나온다고 가정하면 새 임베딩 포함 **약 $0.80**, 같은 입력을 전부 캐시쓰기 요율로 잡으면 **약 $1.07**이다. 답변당 입력10,000·출력1,000tokens 가정에서는 **약 $1.50–1.68**, 입력20,000·출력1,500이면 **약 $2.43–2.79**다. 실제 v9 검색 문맥·출력·캐시는 아직 없으므로 이들은 예측용 시나리오다.

한도는 오류 요청도 포함하며 범주별 호출 수를 서로 빌리지 않는다. 호출 직전 확정 비용·미확정 예약액·다음 호출 최대액을 합쳐 검증한다. timeout/usage 누락은 예약액을 환급하지 않는다. 실제 wire의 UTF-8 bytes+1,024가70,000을 넘으면 문맥을 임의 변경하지 않고 전송 전에 중단한다.

## 답변 개선·회귀 판정

기존 33개 필수 그룹과 P/F/U/NOT_RUN 규칙, 대체 근거·반올림 허용·선택 항목·원문 충돌 처리 기준을 유지한다. 원문 정확도, 필수 항목 완전성, 출처 충실도, 실제 인용 지원, 한계 처리, 엄격 성공을 별도로 판정한다. source-ID 검사 통과를 의미·산술 정확도로 세지 않는다.

- 새 36개 답변을 `(question_id, repeat)`, 필수 그룹은 `claim_id`까지 연결해 주/보조 기준과 각각 비교한다. **P→F와 P→U, F→P와 U→P를 구분**하고 합계 상승으로 개별 회귀를 상쇄하지 않는다.
- 문항별 실제 두 판정과 2/2·1/2·0/2, 회사별 결과, 필수 그룹66개 관측을 보고한다. 36개 응답을 독립36문항으로 취급하지 않는다.
- **U04:** HD 핵심 원인 근거가 실제 후보·최종8개에 들어오고, 두 답변에서 정확히 사용·인용됐는지 확인한다.
- **U03·U16:** 지역 열 대응, 당기/전기 현금 구분, 미래 리스 필수 항목을 확인한다. **U02·U11:** 기간과 원문 단위·숫자 유지 여부를 확인한다.
- **U14:** 원문 자체 충돌과 모델의 오독·근거 없는 단정을 구분한다. 선택 사항이던 충돌 언급을 새 필수 항목으로 만들지 않는다. U08·U09·U15와 U06·U12·U18의 범위·시점·추론 한계도 포함해 전체18문항을 검토한다.
- 원문 부족/충돌 → corpus → Dense/BM25 후보 → RRF 최종 문맥 → 생성 해석 순서로 근거를 추적한다. 새 답변 변화와 검색 변화가 같이 보이더라도 단일 원인으로 단정하지 않는다.

조건 이름을 가리고 기존/새 답변을 고정 seed로 섞어 검토한 후 매핑을 연결한다. 같은 assistant와 개발 중 노출된 자료를 사용하므로 독립 인간 평가나 완전한 맹검은 아니다. 새 결과에 맞춘 rubric/prompt 수정, 기본값·store 자동 채택, 후속 호출은 없다.

## 중단 조건과 준비 검증

원문·소스·의존성·요금·승인 해시 불일치, HTTP/timeout 오류, 누락/불일치 usage, 잘못된 차원·scope·fallback, 최종 출처 수 불일치/packet 누락, incomplete/refusal/schema/출처ID 실패, 호출·비용·시간 한도에서 중단한다. 남은 슬롯은 NOT_RUN이며 retry/resume으로 채우지 않는다. 시간은 임베딩·store 구축·검색·생성 전체에 적용하고, 실제 runner는 남은 시간 이하로 요청 timeout을 줄이며 watchdog으로 9000초를 지켜야 한다. 사후 수작업 평가는 provider 실행 시간과 별도다.

준비 검증에서 v9 원문 재파싱은 직전 보존 검증의 **전체3,645개 청크와 정확히 일치**했다. 108개 과거 답변의 원본 행·요청·답변 해시와 33개 기준을 연결했고, 36개 mock 요청의 prompt/route/schema/scope 및 18쌍 반복 해시를 확인했다. 외부 연결 시도는0이다.

**크기 스트레스 검사의 한계:** 각 보고서의 가장 큰8개 출처 조합은 최대78,741bytes여서 12개 mock 슬롯에서 각각2개가 기존 byte gate에 의해 제외됐다. 나머지24개 슬롯은8개를 전달했다. 이는 실제 검색 결과가 아니다. 실제 전달된 최대 packet64,947bytes, wire66,897bytes, 입력 예약67,921tokens-equivalent bytes로 기존 생성 예약 안이지만, 실제 평가에서는 앞서 명시한 **8개 유지·누락 시 중단**을 적용한다. 처음의 무누락 가정 실패와 최종 stress 결과를 모두 기록했다.

이 묶음은 **실행 조건과 무호출 리허설이며 live runner가 아니다.** 별도 실행 지시 후 새 runner를 이 해시에 연결하고, 실제 outgoing HTTP 경계의 비용·호출·시간 admission과 중단 처리를 mock 검증한 뒤 실행해야 한다. 이미 사용한 과거 runner/승인을 재사용하지 않는다.

## 산출물과 보존

준비 묶음 (`../../benchmarks/results/new18_v9_store_preparation_2026-10-16/`, local artifact not included)의 `run_conditions.json`, `slot_plan.json`, `baseline_comparison.json`, `projection_plan.json`, `embedding_plan.json`, `cost_plan.json`, `pricing_snapshot.json`, `request_contract.json`, `offline_request_contract_check.json`, `preparation_closeout.json`에 조건·해시·비용·검증을 남겼다. corpus·parents는 파일 projection이며 DB/store가 아니다.

기존 보호 파일2,694개 중 현재 상태 문서2개만 준비 상태 링크를 추가했다. 소스·테스트·기존 store·`.env`·과거 결과는 해시로 보존하고 기존 store 3곳의 파일 목록도 유지했다. store 전환·commit·push는 하지 않았다. 실제 구축·검색·답변·개선/회귀 결과는 모두 **NOT_RUN**이다.
