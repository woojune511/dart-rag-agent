# XML 복구 오류 탐지와 색인 차단

2026-10-16. **PASS_OFFLINE_FAIL_CLOSED.** 기본 XML 파서의 복구 결과 수용 경계만 수정했다. 원문·기존 저장소·평가 결과를 수정하거나 모델을 호출하지 않았다.

## 수정 전 실제 누락 재현

HD현대일렉트릭 원문 `20260316000940`의 SHA-256은 `dfb589262a264453499dd932f24a51676ab62e8325914767a1f9c1fb823d6c6d`이다. 현재 checkout의 HEAD `48b08081`에서 중복 속성 따옴표 수정 전 sanitizer를 추출해 동일 원문에 적용했다. 금융 용어·질문·정답에 따른 분기는 사용하지 않았다.

- 복구 파서는 오류 26개를 기록하고도 트리를 반환했다. 첫 오류는 전처리 XML 14727행의 `ERR_TAG_NAME_MISMATCH`, 마지막은 37917행의 `ERR_DOCUMENT_END`였다.
- 해당 트리에는 경영진단 제목이 없었다. 현재 sanitizer로 파싱한 동일 원문에는 해당 제목이 있고 XML 오류는 0개였다.
- 수정 전 `_parse_xml`은 이전 sanitizer를 주입했을 때 이 불완전한 트리를 그대로 반환했다. 이는 이미 수정된 속성 따옴표 결함의 재현이며, 현재 sanitizer에 그 결함이 남았다는 주장은 아니다.
- 별도 익명 입력에서도 현재 sanitizer를 그대로 사용해 재현했다. 첫 `DOCUMENT` 뒤에 있는 두 번째 섹션이 유실됐지만 `process_document`는 첫 섹션의 청크 1개를 성공 결과로 반환했다.

재현 기록 (`../../benchmarks/results/xml_recovery_guard_2026-10-16/reproduction.json`, local artifact not included)은 원문 해시, 실제 libxml 오류, 수정 전 수용 여부를 보관한다. 기록의 `section_titles`는 트리 안 `TITLE ATOC="Y"` 개수이며, 과거 보고서의 추출 섹션 개수 16/46과 다른 측정값이다.

## 최소 수정

`FinancialParser._parse_xml`은 기존 전처리와 `recover=True`를 유지한다. 복구 후 libxml `ERROR/FATAL`이 남거나 `XMLSyntaxError`가 발생하면 `XMLRecoveryError`를 호출자에게 전달한다. 일반 읽기 실패 처리에 삼켜져 빈 결과가 되지 않도록 예외 경계를 분리했다.

예외는 파일 경로, 보고된 오류 개수, 최대 5개 오류 종류와 전처리 XML 행·열을 포함한다. 마지막 오류도 보존하며 libxml의 원문 포함 메시지는 예외 요약에 복사하지 않는다. 경고만 있는 입력과 기존 정상 전처리는 허용한다.

섹션·outline·청크 파싱 모두 같은 경계를 사용한다. 거절된 문서는 context 생성·임베딩·색인에 도달하지 않는다. 동일 요청에서 앞선 다른 문서가 이미 저장됐을 수 있으므로 전체 batch rollback을 보장하지 않는다.

이전 저장소에 새 검사가 적용됐다고 오인하지 않도록 parser identity를 `financial_parser_v10_xml_recovery_guard`로 올렸다. 기존 v5 앱 저장소와 별도 v9 평가 저장소는 수정·재구축·활성화하지 않았다.

## 영향 범위와 한계

기존 11개와 새 3개 원문을 읽기 전용으로 점검했다. 4개는 현재 전처리 후에도 복구 오류가 남는다.

| 원문 | 보고된 XML 오류 수 | 주요 오류 |
| --- | ---: | --- |
| KB금융 `20240326000894` | 20 | `ERR_GT_REQUIRED` |
| POSCO홀딩스 `20240322000986` | 9 | `ERR_TAG_NAME_MISMATCH`, `ERR_TAG_NOT_FINISHED` |
| 카카오 `20240418000375` | 4 | `ERR_GT_REQUIRED` |
| 현대자동차 `20240313001451` | 10 | 태그·이름 오류, `ERR_INTERNAL_ERROR`, `ERR_DOCUMENT_END` |

이 4개는 이제 명시적으로 거절된다. 오류가 있다는 사실만으로 모든 문서에서 본문 누락을 확정하지 않는다. 원문 복구의 신뢰성을 확인할 수 없는 경우를 보수적으로 차단한 것이며, 각 원인의 추가 수정은 이번 범위에 포함하지 않았다.

오류 없는 파싱도 전체 원문 보존의 증명은 아니다. Sanitizer의 해석, 섹션 추출·청킹 누락, 표 축·단위 의미, 기존 저장소 내용은 이 검사로 검증되지 않는다. 검색·답변 품질 및 일반 DART 문서 정확도에 대한 새 주장은 없다.

## 검증

- 새 [회귀 테스트](../../tests/test_parser_recovery.py) 9개를 포함한 파서·표·제목·ingest·manifest·store successor·import suite **216/216 통과**(47.256초). 실제 libxml 복구를 사용하며, 부분 트리의 섹션 추출 전 차단, 모든 공개 파싱 경로의 예외 전달, 빈 XML·태그 불일치·ERROR 등급 오류, 경고 허용, 오류 격리와 진단 길이 제한을 확인했다.
- 실제 `IngestService`와 가짜 외부 의존성으로 거절 문서의 context 생성·store 쓰기 0회 확인. 이전 parser identity를 정상 호환 저장소로 자동 채택하지 않는 기존 회귀도 v9까지 확장했다.
- 네트워크를 차단한 실제 원문 대조 (`../../benchmarks/results/xml_recovery_guard_2026-10-16/verification.json`, local artifact not included): **14개 원문 해시 유지**, 허용된 **10개 트리의 직렬화 바이트 동일**, 4개 명시적 거절. 과거 HD 전처리 재현도 오류 26개와 마지막 `ERR_DOCUMENT_END`를 보존한 예외로 거절한다.
- 전체 unittest, fresh ingest, 임베딩, 생성, 검색·답변 평가는 실행하지 않았다. 범위에 맞는 로컬 회귀만 수행했으며 기존 실험 결과는 유지했다.
