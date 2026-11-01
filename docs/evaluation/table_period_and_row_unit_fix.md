# 기간 중복 판정과 행별 단위 보존 수정

2026-10-16. **PASS_OFFLINE_SOURCE_PRESERVATION**. 외부 모델·임베딩·검색 API **0회**, 비용 **USD 0**. 기존 store와 `.env`는 유지했다.

**중첩된 기간 라벨을 중복 계산하는 결함과 명시된 행 단위를 표 전체 단위로 덮는 결함을 수정했다. 원문 3개의 값·헤더·단위 문자열은 모두 보존했고, 새 18문항의 저장된 문맥에서 필수 근거 회귀는 0개다.** 검색 순위나 실제 답변 개선을 측정한 결과는 아니다.

## 최소 변경

- [기간 추출](../../src/processing/table_records.py)은 기존 6개 상대 기간 표현을 긴 표현부터 겹침 없이 읽는다. 한 번 등장한 `전기말`에서 `전기`를 따로 만들지 않는다. 독립적으로 등장한 라벨의 기존 우선순위, 절대 연도·날짜 규칙, coarse `period_focus` 매핑은 유지했다. 실제 `당기`와 `당기말`이 따로 있으면 둘 다 남긴다.
- [행 단위 처리](../../src/processing/table_unit_hints.py)는 기존 단위 policy와 구조적인 표기를 사용한다. 행 축에 명시된 `(원)`, `(%)`, `(천USD)`, `[USD, 천]`, `단위: …` 등을 원문 표기로 cell/value에 보존한다. 같은 단위의 중복 표기는 병합하고, 값·표 전체 단위·정규화 값은 바꾸지 않는다.
- bare `USD/CNY`나 `(USD)`, 회사 약칭, 설명문은 단위 선언으로 취급하지 않는다. 명시 행 단위끼리 또는 실제 열 단위와 충돌하면 cell/value 힌트를 비운다. 반복된 표 전체 단위 선언은 행 단위 override를 막지 않는다. 빈 셀 힌트가 ValueRecord에서 표 단위로 되돌아가던 fallback도 막았다. 단위 키가 없는 과거 입력의 fallback은 유지한다.

회사·문항별 runtime 분기나 환산 규칙은 추가하지 않았다. 파서 schema를 **`financial_parser_v9_period_labels_row_units`**로 올렸고, v8을 포함한 이전 store를 자동 채택하지 않는 검사를 추가했다. 기존 파싱·청킹 수정은 유지하며 이번 소스 변경은 `table_records.py`, 새 단위 helper, schema 버전으로 한정했다.

## 원문 수정 전후

| 대상 | 수정 전 | 수정 후 |
|---|---|---|
| 실제 HD `전기말` 단독 표 두 곳 | `전기` + `전기말`, `multi_period` | 원문 `전기말` 하나, `prior` |
| 실제 호텔신라 `전전기` 값 축 | `period_text=전기` | `period_text=전전기`, 원문 열·값 유지 |
| 호텔신라 주당순이익 `2,270`, 행 `(원)` | cell/value 단위 `백만원` | 값 `2,270` 그대로, 단위 `원` |
| HD 28열 지급보증 표의 네 통화 행 | 모든 cell/value 단위 `백만원` | 원문 행의 `천USD·천CNY·천NOK·천EUR` |
| 통화 이름만 적힌 행 | 표 단위 사용 | 170개 셀 모두 기존 힌트 유지 |

HD 원문 표의 **9행·28열, 3개 헤더 행, 168개 본문 좌표, 그중 108개 숫자 열 좌표**를 XML locator와 직접 대조했다. 네 통화 행의 cell/value 108개는 각각 명시된 행 단위로 교정되고 숫자·헤더·열 위치는 같다. 원문 표 전체의 `백만원` 선언도 삭제하지 않고 별도로 유지한다. 원문 좌표·선언 검증 (`../../benchmarks/results/table_period_unit_fix_2026-10-16/original_xml_verification_final.json`, local artifact not included).

`전전기말`도 신규 일반 회귀 테스트에서 전체 표현을 유지하지만, 이번 3개 원문의 값 축에는 해당 표현이 없다. 이를 실제 corpus에서 확인한 사례로 세지 않았다. `전전기`/`전전기말` 단독의 coarse focus는 기존 매핑상 `unknown`이며 임의로 `prior`나 특정 연도를 부여하지 않는다.

## 세 원문 전체 대조

수정 전 소스 snapshot을 별도 프로세스로 실행해 직전 v8의 3,645개 청크 본문·metadata·검색 입력과 일치함을 확인했다. 수정 후도 같은 원문과 청킹 `2500/320` 조건을 사용했으며 section fallback은 없다. DB나 외부 provider는 열지 않았다.

| 항목 | 확인 결과 |
|---|---:|
| 원문 블록 / 물리적 표 | 4,424 / 3,234, 모두 보존 |
| 구조화 행 / 셀 / 값 기록 | 11,779 / 38,024 / 32,703, 개수·ID·좌표 유지 |
| 청크 | 3,645 → 3,645, ID·순서·원문 본문 모두 동일 |
| 기간 라벨 교정 | 169개 표, 1,349개 값 기록 |
| coarse focus 변경 | 50개 표: multi → current 46 / prior 2 / unknown 2 |
| 행 단위 교정 | 44개 표·102개 행·364개 셀·361개 값 기록 |
| 단순 통화명 / 회사 `(주)` 음성 대조 | 각각 170 / 1,162개 셀 기존 단위 유지 |
| 검색 입력 텍스트 변경 | 50개, `period_focus` 접두어만 변경 |

모든 블록의 원문 텍스트·grid·헤더·표 전체 단위·source context, 모든 cell/value의 숫자·좌표·축은 같다. 새 단위 힌트는 원문 행에 실제 존재하는 표기이며, 통화·수량 환산이나 `normalized_unit` 확정은 하지 않았다. 실제 corpus에서 단위 충돌로 새로 빈 힌트가 된 셀은 0개다. 셀과 값 기록의 변경 수 차이는 `-` 셀 3개에 ValueRecord가 없기 때문이다.

직전 진단의 focus 중복 후보 56개 중 실제 교정은 50개다. 나머지 6개는 원문·연결 문맥에 `당기`와 `당기말` 또는 `전기`와 `전기말`이 따로 등장하므로 두 표현을 유지했다. 이 추출기가 서로 다른 표현의 의미까지 같은 기간으로 합치지는 않는다.

전체 비교 (`../../benchmarks/results/table_period_unit_fix_2026-10-16/evidence_comparison.json`, local artifact not included), 기간 witness (`../../benchmarks/results/table_period_unit_fix_2026-10-16/period_preservation.json`, local artifact not included), 행 단위 witness (`../../benchmarks/results/table_period_unit_fix_2026-10-16/unit_preservation.json`, local artifact not included).

## 새 18문항의 고정 출처 회귀

직전 저장된 8개·12개 문맥의 **183개 고유 출처**를 같은 청크 ID·원문·물리적 표에 대응시켰다. 질문·scope·출처 개수·순서는 유지했다. 36개 packet 중 **35개가 동일**하고, **U02의 12개 문맥만** 두 출처의 `period_focus: multi_period`가 `prior`로 바뀌었다. 해당 출처는 `20260316000940:347:239`, `20260316000940:822:223`이며 본문과 표시 문맥은 그대로다.

U11의 배당 표는 구조화 행 단위가 교정되지만, 기본 SimpleRagAgent packet이 cell/value JSON을 직접 포함하지 않으므로 답변 입력 텍스트는 바뀌지 않는다. 이 metadata 수정을 U11 답변 개선으로 해석하지 않는다.

아래는 답변 점수가 아닌 **필수 근거 충족 판정**이다. 기존 33개 기준을 두 조건에서 대조한 66개 판정은 전후 같다.

| 문항 | 8개 문맥 전후 | 12개 문맥 전후 |
|---|---|---|
| U01 | 2P → 2P | 2P → 2P |
| U02 | 1P → 1P | 1P → 1P |
| U03 | 2P → 2P | 2P → 2P |
| U04 | 1F → 1F | 1P → 1P |
| U05 | 2P → 2P | 2P → 2P |
| U06 | 1P → 1P | 1P → 1P |
| U07 | 2P → 2P | 2P → 2P |
| U08 | 1P / 1F → 동일 | 1P / 1F → 동일 |
| U09 | 1P / 1F → 동일 | 1P / 1F → 동일 |
| U10 | 2P → 2P | 2P → 2P |
| U11 | 2P → 2P | 2P → 2P |
| U12 | 2P → 2P | 2P → 2P |
| U13 | 2P → 2P | 2P → 2P |
| U14 | 2P → 2P | 2P → 2P |
| U15 | 1P / 1F → 동일 | 1P / 1F → 동일 |
| U16 | 3F → 3F | 3F → 3F |
| U17 | 1P → 1P | 1P → 1P |
| U18 | 2P → 2P | 2P → 2P |
| 전체 | **26P / 7F → 동일** | **27P / 6F → 동일** |

필수 근거 회귀·출처 누락은 **0개**, 최대 packet은 **47,514 UTF-8 bytes**로 기존 65,536 상한 안이다. 76개 원문 anchor의 대응 청크도 전후 같다. 고정 문맥 (`../../benchmarks/results/table_period_unit_fix_2026-10-16/fixed_source_packets.json`, local artifact not included), 66개 판정과 witness (`../../benchmarks/results/table_period_unit_fix_2026-10-16/required_source_review.json`, local artifact not included).

## 검증과 한계

신규 기간 테스트 9개, 행 단위 테스트 22개를 추가했다. 수정 전 실패를 기록했고, 기간 관련 43개와 단위 22개가 통과했다. 외부 네트워크를 차단한 전체 **2,245개** 테스트도 실패·오류·skip 없이 통과했다. 외부 연결 시도는 0개이며 Windows 내부 loopback 46개만 허용했다. 전체 결과 (`../../benchmarks/results/table_period_unit_fix_2026-10-16/full_suite_result.json`, local artifact not included).

이번 검증은 개발 중 노출된 3개 원문과 저장된 18문항의 근거 보존 검사다. 새로운 검색·임베딩·답변·judge는 실행하지 않았다. U03·U16의 답변 회귀나 기존 누락 근거가 해결됐다고 주장하지 않는다. 변경된 검색 접두어의 순위 영향도 미측정이다.

기간의 단어 경계나 절대 회계연도 의미, 모호한 다중 행의 헤더 추론, 단위의 모든 표현·열 범위 해석은 남는다. 빈 unit_hint는 **parser cell/value 계약**이며, 후속 Compiler의 기존 단위 fallback까지 전역적으로 차단하는 신호는 아니다. 행 단위 교정은 통화 환산·정규화 값 검증이나 SimpleRAG 답변의 의미 검증이 아니다.

변경 전 보호 대상 **2,644개** 중 이번 소스·계약·현재 상태 문서 6개만 허용한 변경으로 기록했다. 기존 `.env`, 앱/평가 store, 원문과 과거 실험은 전후 해시로 보존했다. 기존 DB는 열지 않았고 테스트의 임시 fixture store는 별도다. v9는 소스에만 반영됐으며 store 재구축·활성화·commit·push는 하지 않았다. 최종 보존 기록 (`../../benchmarks/results/table_period_unit_fix_2026-10-16/closeout.json`, local artifact not included).
