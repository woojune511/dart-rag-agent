# 77문항 문서·표 구조 ablation 준비

2026-09-28 현재 상태: **COMPLETED**, [231개 답변의 비교 결과](structure_full77_result.md). 이후 사용자가 승인한 USD12 합산 상한·3×77 단1회 실행을 완료했으며, 추정 비용은 USD10.38216732다. 이 문서의 아래 내용은 실행 전 동결한 준비 기록이며, 당시의 NOT_RUN/승인 대기 문구는 현재 상태가 아니다.

## 비교 조건

| 조건 | 표현과 분할 | 청크 수 | 임베딩 입력 tokens |
| --- | --- | ---: | ---: |
| A `flat` | HTML visible text를 읽기 순서로 펼치고 일반 문자 분할. 보고서 식별 metadata만 제공 | 3,425 | 7,325,952 |
| B `document` | 공통 parser가 추출한 절·문단·제목을 유지. 표 본문을 공백으로 펼치고 일반 문단 분할을 적용. 표 전용 metadata·헤더 전파 제거 | 8,214 | 8,308,028 |
| C `table` | B와 같은 추출 블록에서 기존 표 분할·헤더/행/값/기간/단위 문맥과 structural-selective prefix 적용 | 13,176 | 13,051,821 |

문자 길이 목표 2,500, overlap 목표 320은 공통이다. 표 행 분할과 절 경계 때문에 실제 청크 길이·개수·중복률은 달라진다. 모든 조건에서 원래 헤더 문구와 단위가 평문으로 남을 수 있다. 구조를 제거한다는 이유로 원문 숫자나 헤더 단어 자체를 삭제하지 않는다.

**해석 범위:** A→B는 HTML 추출 대 기존 parser 추출, 제목 경계, 분할, section 분류·검색 prefix가 함께 달라지는 문서 표현 묶음의 비교다. B→C는 동일한 추출 블록에서 표 구조를 검색·답변에 전달하는 방식과 분할의 비교다. B에도 공통 parser의 표 셀 추출·span 복원이 선행하므로 “표 parser 자체를 전부 제거한 효과”는 아니다. C의 특정 prefix 하나만의 효과로 해석하지 않는다.

기존 9문항 비교에서 관측된 flat+RRF5/8, structured+RRF4/8을 보존한다. 구조 보존의 우위를 전제하거나 결과를 보고 조건을 바꾸지 않는다.

## 고정한 실행 조건

- 동일한 11개 2023년 원본 공시, 원본 해시와 77개 질문·명시적 접수번호 scope.
- `text-embedding-3-large`, 3,072 dimensions. 77개 query vector를 한 번 구해 모든 arm에서 공유.
- 각 조건·접수번호별 동일한 corpus 범위에서 exact squared-L2 dense top16, 기존 BM25 top24, 기존 RRF(k=60) top8. 동점은 저장된 corpus 순서로 처리.
- 실제 `SimpleRagAgent`를 호출하되 실험용 검색 adapter를 사용한다. production Chroma ANN 또는 HTTP 앱 전체의 동일 재실행이라고 주장하지 않는다.
- 답변 모델 `gpt-5.6-terra`, low reasoning, 기존 prompt/schema, 최대 출력8,192, whole-source packet65,536 UTF-8 bytes.
- 질문 순서는 기존77개와 동일. 질문마다 A/B/C 호출 순서를 회전한다. 최대231회 답변. 인용 가능한 근거가 없는 경우 앱의 무호출 거절 경로를 유지한다.
- 질문·scope·선택 근거만 모델에 제공. reference/평가 유형/판정은 실행 경로에서 읽지 않는다.
- 후보 순위·선택·context 누락·원시 요청/응답·usage·예산 예약·결과를 저장한다. 30초 heartbeat.
- retry/resume, 유료 judge, query rewrite, reranker, Planner/Compiler, 답변 repair, 결과에 맞춘 prompt/policy 변경 없음.

### 기존77 결과를 C로 재사용하지 않는 이유

기존 실행의 NAVER store에는 다른 연도 보고서도 있어 BM25 IDF 계산의 corpus가 달랐다. 이번에는 모든 조건을 접수번호 단위로 맞추고 dense 검색도 공통 exact 계산으로 고정했다. 또한 시간에 따라 달라지는 parser fallback을 끄므로 일부 청크 수가 다르다(KB2,110→2,128, NAVER1,090→1,093). 따라서 이전 점수를 C로 합치지 않는다. 이전77개 출력과 원본 store는 그대로 보존하고, 새 A/B/C의 대응 문항만 비교한다.

## 사전 채점 기준

원본 dataset을 수정하지 않는다. 답변 가능55문항, 거절19문항이 주 평가 대상이고, 정답 기준의 주체·부문 문제가 확인된 `KBF_T1_017`, `POS_T2_058`, `POS_T1_075`는 세 조건 모두 진단용으로 분리한다. 전체77개 실행 현황과 제외 사유를 함께 공개한다.

주 지표는 **정확성·요청 충족·인용 근거 지지를 모두 만족한 답변 수**다. 실제 전달 근거의 충분성, 올바른 거절, 수치/요약/기업별 결과, 문항별 승·패·동률, 비용과 지연을 별도 보고한다. 오류 또는 비용 중단으로 비교쌍이 완성되지 않으면 누락을 공개하고 성공률의 비교 분모에 섞지 않는다.

동결된 `criteria.json`은 기존 검토에서 확인한 해석 차이도 미리 규정한다. 예를 들어 차입금의 현재 유동성 부분 포함 여부는 명시적 범위와 피연산자가 맞으면 양쪽 해석을 허용하고, 가정된100조원 R&D 질문은 원래 거절 평가 기준을 유지한다. 수치 최종 표시 정밀도의 정확성과 사소한 중간 표시 오차를 구분하며, 근거 없는 반올림 원인 설명은 출처 지지 실패다. 이후 이 기준을 답변별로 바꾸지 않는다.

원시 출력 hash를 먼저 고정한 뒤 assistant가 인용 원문과 대조한다. 개발에 노출된 자체 데이터셋이며 독립 human gold/미노출 holdout/일반 금융 정확도 주장이 아니다. 원문 quote hit만으로 의미 정확성을 판정하지 않는다. 답변의 source-ID 검사와 사후 원문·산술 검토도 구분한다.

## 무호출 검증

| 검증 | 결과 | 범위 |
| --- | --- | --- |
| 전체 실행 경로 | 231/231 mock 완료 | 실제 SDK 직렬화·budget guard·앱 출력·결과 저장. 각 corpus 첫8개와 동일 fake vector, authored 답변 사용 |
| 중단 조건 | 7/7 | cap0, 잘못된 인용, HTTP503, usage 누락, 저장 실패, 질문 변조, 승인 파일 없음 |
| 표현 제거 계약 | 9개 통과 | 비표 문단 보존, 숫자 표기 보존, 제목 유지, 표 metadata 제거, 긴 표의 일반 분할 및 헤더 재전파 없음 |
| corpus 형태 | 33개/24,815청크 통과 | 식별자 중복·scope·hash·조건별 metadata. 짧은 점검 질문 기준 단일 source byte 상한 초과0 |
| parser 정규식 대조 | 5,006개 일치 | 아래 실험 한정 실행 adapter 검증 |
| 원본 입력 | hash 불변 | 이전 dataset/runtime/config/원본 store 보호 목록 |

mock에는34회 embedding 요청과231회 답변 요청이 있었으나 모두 네트워크를 막고 로컬 응답으로 대체했다. 이는 실제 검색·생성 품질이나 provider acceptance 결과가 아니다. 전체 live embedding은433회까지 허용되므로 mock이 전체 네트워크 batching 성공을 보장하지 않는다.

### 준비 중 발견한 parser 실행 지연

KB 원문의 제목 처리에서 `_INLINE_BODY_SEPARATOR_RE`의 `(?:\s*[A-Za-z가-힣&]+)*`가 콜론 없는 긴 문자열을 과도하게 재탐색했다. 첫 준비 시도를 중단하고 stack dump를 켠 두 번째 시도에서 해당 위치를 확인했다. 유료 호출은 없었으며 원본·이전 산출물을 수정하지 않았다.

실험의 `prepare.py`에서만 반복 그룹 사이의 공백을 `\s+`로 바꿨다. 공백 없이 이어진 문자 그룹은 하나의 문자 그룹으로 합칠 수 있으므로 인식 언어와 전체 match span을 유지하면서 중복 분할 탐색을 제거한다. 양쪽 표현의 span/group이5,006개 대조에서 일치하고100,005자 음성 예제가 새 표현에서 약0.004초에 끝났다. 유한 대조가 모든 입력의 형식적 동등성 증명은 아니다. production 파일은 변경하지 않았으며 동일 adapter를 B/C 공통 추출에 적용했다.

이후11개 보고서 준비가 완료됐다. parser 내부 timeout fallback은 비활성화했다. stack dump의 정기 `Timeout` 문구는 진단 timer 출력이며 완료된 준비의 section timeout/누락을 뜻하지 않는다. 이 수정으로 검색·답변 품질이 개선됐다고 주장하지 않는다.

## 실행 전 비용 계획과 승인 범위 (과거 준비 기록)

준비 완료 시점에는 **실제 provider 호출0, 비용0, authorization/consumed 파일 없음**이었다. 이후 별도 승인을 받아 실행했으며 현재 authority는 소비됐다. 아래 예시는 그 준비 시점의 계획이다. 이전77문항 USD5 승인은 재사용하지 않았다.

| 항목 | 계획 |
| --- | ---: |
| 문서 embedding | 432회, 28,685,801 tokens |
| 공통 query embedding | 1회, 4,813 tokens |
| 전체 embedding 추정 | USD3.72977982 |
| 답변 추정: 이전77개 생성 비용×3 | USD5.783793 |
| 합산 예상 | **약 USD9.51** |
| 제안하는 새 합산 hard cap | **USD12.00** |

이 값은 이전 실험과 같은 보수적 회계 계수(embedding0.13/M, 답변 입력2.50/M·출력12/M)이며 현재 청구액 확인이 아니다. 표현별 실제 context와 답변 길이가 달라지므로 예상값은 보장이 아니다. 전체 embedding을 새로 하는 상한 계획이며 아직 벡터 재사용은 검증·반영하지 않았다.

요청 전 최대 입력·출력을 예약하고 다음 요청까지 USD12 안에 들어오지 않으면 전송 전에 중단한다. 모든 답변이 최대치를 소비하는 이론적 답변 예약액만 USD100.767744이므로 USD12는 전체 완료 보장이 아니다. 실패/usage 불명은 해당 예약액을 유지하고 실험 전체를 멈추며 미실행은 NOT_RUN으로 남긴다.

embedding pacing은750,000tokens/61초로 고정했다. 전체 신규 embedding 계획만 약39분 규모이고 답변 생성·로컬 처리까지 합하면 약1시간을 예상하되 실제 소요시간은 보장하지 않는다.

## 실행과 증거

실험 코드·질문·채점·seal·readiness:

`benchmarks/results/structure_full77_preparation_2026-09-28/`

큰 corpus·mock 출력·추후 live 출력:

`D:/CodexArtifacts/dart-rag-agent/structure_full77_preparation_2026-09-28/`

- `manifest.json`: 실행 조건·호출 수·비용·중단 규칙.
- `criteria.json`: 실행 전에 고정한 판정과 민감도.
- `readiness.json`, `terminal_controls.json`, `corpus_shape_audit.json`: 무호출 검증.
- `seal.json`: 입력 hash. SHA-256 `56918b52e6aed87fd432521d1d69573d8ecaa4c4f76d53158a4023a21ed75658`.
- `manifest.json` SHA-256 `27fe7df4369a3c19342389cb436d820c49c69324bb8b9abb2b3e6599e9667938`.
- `review_packet_seal.json`: readiness를 포함한 검토 자료 hash.

아래는 사용자가 이번 USD12 상한·3조건 각각77문항·단1회 실행을 승인한 뒤 실행한 명령의 기록이다. 해당 authority와 label은 소비됐으며 재실행·자동 resume용 명령이 아니다.

```powershell
./.venv/Scripts/python.exe -B -X utf8 benchmarks/results/structure_full77_preparation_2026-09-28/run.py --label full77_abc_once --live
```

새 정확도·검색 coverage·ablation 결과와 한계는 [완료 보고서](structure_full77_result.md)에 있다. source runtime, 기본 앱, 이전 평가 출력과 원본 store를 수정하지 않았으며 새 실험 자료는 local/ignored 상태로 유지한다.
