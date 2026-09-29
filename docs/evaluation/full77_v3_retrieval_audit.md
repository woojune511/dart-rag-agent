# 새 v3 저장소의 77문항 검색 근거 점검

2026-09-29 상태: **COMPLETE_OFFLINE_RETRIEVAL_AUDIT**. 77문항의 보고서 범위와
질문 임베딩을 확인하고 현재 검색 경로를 실행했다. 새 답변은 생성하지 않았다.

## 확인한 범위

- 77/77 문항의 명시적 접수번호가 새 저장소의11개 회사·2023 보고서와 일치한다.
- 기존 기준을 보존한다: 긍정55, 거절19, 진단용3. 세 진단용 문항은 KBF_T1_017,
  POS_T2_058, POS_T1_075이다. HYU_T3_036의 추가로 알려진 reference 범위 오류도 별도 표시했다.
- 기존 query_vectors.npy의77×3072 float32 값을 봉인 해시·실제 embedding 요청/응답과
  대조했다. 모델명, 차원, 입력 token 배열과 질문 순서 모두 일치한다.
- 새 저장소의 byte-identical 복사본에서 현재 VectorStoreManager.search를 호출했다.
  Chroma dense16, 전체 저장소 BM25 IDF를 사용한 범위 내 top24, RRF60 top8이다.
  원본 앱 연결과 저장소는 보존했다. query cache와 embedding fallback은 사용하지 않았다.
- provider/임베딩 API 호출0, 답변 생성0, 추가 API 비용0. 소켓과 HTTP 호출을 차단했다.

## 대표근거 위치: 27문항

이전 실패 분석에서 검토된 대표근거가 있는27개 긍정 문항을 원문과 대조했다.
동일 질문의 A/B/C 기록을 독립 문항으로 세지 않았다. **아래는 대표 구성요소의 위치이며,
55개 긍정 문항의 근거 충분성이나 정답률이 아니다.** 다른 대체근거·범위·단위 해석을
모두 검증한 것도 아니다. 나머지28개 긍정 문항은 기존 근거 주석의 위치만 기록하고
완전한 의미적 충분성 판단을 유보했다.

| 관측 | 문항 수 |
| --- | ---: |
| 검토한 대표 구성요소가 top8에 있음 | 10 |
| 후보에 있으나 top8에서 빠짐 | 10 |
| 저장소에는 있으나 dense/BM25 후보에 없음 | 5 |
| 알려진 원본 회계 문단이 저장소에도 없음 | 1 |
| 주석의 요청 적합성 판단 유보 | 1 |

top8 밖10개 대표근거의 후보 유입은 BM25만7, dense만2, 양쪽1이다.
후보 누락과 최종 선택 누락은 서로 다른 문제다. 후보 안의 유용한 근거를 발견했다는
사실만으로 LLM 선택기의 답변 개선이나 비용 효율이 입증되지는 않는다.

| 사례 | 관측 |
| --- | --- |
| 삼성전자 연결 배당금 지급 | 연결 현금흐름 표9위, 배당 정책은 top8 |
| NAVER 영업권·손상 | 당기 기말/손상 표16위 |
| SK하이닉스 DRAM 비중 | 실제 MD&A의 DRAM63%는18위 |
| 셀트리온 해외매출 비중 | 국내/해외/전체 매출 표20위 |
| 삼성전자 웰스토리 소송 | 알려진 단체급식 소송 본문은 저장소에 있으나 후보 밖 |
| 카카오 SM 편입 성장 설명 | 사업개요의 편입/제작·유통 성장 연결 문장이 후보 밖 |
| 현대자동차 배출권 회계 | 원본 HTML의 배출권 무형자산·배출부채 문단이 새 graph에도 없음 |

현대자동차의 배출권 제도 대상이라는 다른 문장은 top8에 있다. 회계 문단의 부재를
질문 전체에 대한 무응답 판정으로 일반화하지 않는다. 원본 HTML 해시와 세 특징 구절의
존재/graph 부재를 함께 확인했다. 추가 parser 수정은 이번 범위에 포함하지 않았다.

## 입력 한도와 문맥 한계

MIX_T3_063은 검색 top8 중3개 청크가65,536바이트 한도로 제외된다. 현재
SimpleRagAgent의 실제 packet 구성 경로를77회 재생하고 모델 호출 직전에 중단해
검증했다. 해당 packet은5개 source/64,548바이트다. 당기 장부금액 표 자체는 이미19위라
선택 누락과 packet 누락이 함께 존재한다. 이 결과는 실제 답변의 인용/독해 오류가 아니다.

원문에서 근거가 발견되더라도 소제목·기간·기업·단위가 의미적으로 맞는지 자동 판정하지
않았다. 예를 들어 KB데이타시스템 표의 현재 제목은 정당한 자회사 문맥이다. 모셔널은
질문이 허용하는 별도 출자 현황 대안이 top4에 있어, 연결 표가 뒤에 있다는 이유만으로
답변 불가능이라고 분류하지 않았다. KB 그룹 규제 설명도 연결 주석14위 외에 같은 그룹
규제 설명이 별도 주석7위에 존재함을 기록했다. 모든 소제목의 정확성을 인증한 결과는 아니다.

## 기존 주석의 오류와 해석 범위

- SKH_T2_061의 과거 대표41:0/14:0은 원재료 구매비중 표였다. 새 위치53:1도 그 표이며,
  실제 DRAM 매출63%는669:2의 MD&A에 있다. 기존 오류 기록을 덮어쓰지 않았다.
- HYU_T3_036의 원래 reference1,569,085는 별도 기준이다. 현재 top8의 연결2,175,691을
  reference와 다르다는 이유로 검색 실패로 세지 않았다.
- SAM_T2_027의 가우스 문장은 저장소에서 발견되지만 DS 전략의 필수근거인지 유보했다.
  이 주석 불확실성을 확정 후보 누락으로 합산하지 않았다.
- 오래된 동일 source ID를 새 source ID로 그대로 해석하지 않는다. 본문·주변 구절을
  대조하고, 단일 숫자/단어 후보는 사람이 원문 역할을 확인했다. 모든 원시 후보는 별도 보존했다.
- 과거 실험은 접수번호별 exact-dense/BM25였고 현재는 Chroma/전체 IDF다. 청크 수도
  달라졌다. 이번 위치를 과거 답변 점수와 직접 비교하거나 파서 하나의 인과 효과라고 하지 않는다.
- 거절19문항은 검색만 실행했다. 새 confusion matrix·무응답 안전성·정답률은 NOT_RUN이다.

## 검증 및 실행 기록

첫 실행은21문항 저장 후22번째 질문의 원문 비교 assertion에서 멈췄다. 기존 BM25의
본문 양끝 공백 제거를 검사 도구가 반영하지 못한 원인이었다. 첫 실행/manifest/log와
21개 결과를 보존했다. 별도의 무호출 검증 실행에서 dense는 원문 그대로, BM25는 기존
strip 결과와 정확히 비교했다. 내부 공백·숫자·소제목을 정규화해 통과시키지 않았다.
실패한 한 질문을 포함한 나머지56개를 검사했고, 보존21+후속56으로77개 결과가 완성됐다.
총 query-vector 재생78회 중1회는 실패한 검사다. provider 재시도는0회다.

77개 후보 순위와 top8을 독립적으로 재구성했고, source scope·본문의 경로별 일치를
확인했다. 실제77개 packet 구성도 예상과 일치했다. 모델 입력에는 질문·scope·원문만
포함됐다. 4,021개 runtime·원본 store·dotenv·기존 실험 파일 해시가 그대로다.
후속 실행128.92초는 준비/첫 실패 실행/검토 시간을 포함하는 전체 소요시간이 아니다.

새 산출물: `benchmarks/results/full77_v3_retrieval_audit_2026-09-29/`의 coverage,
manifest, source_locations, component_review, question_results, 검증/보호 해시와 로그.
검색 원문과 저장소 복사본은 `D:/CodexArtifacts/dart-rag-agent/full77_v3_retrieval_audit_2026-09-29/`.
프로덕션 코드·프롬프트·정답 주석·기존 결과는 변경하지 않았다. 이전 strict11/12와
인용 누락은 그대로다. 추가 유료 실험이나 제품 적용은 실행하지 않았다.

## 문항별 위치표

각 주석의 명시 인용 구절을 공백·표 구분자만 제거해 위치를 찾았다. 생략부호로 분리된
구절은 별도 표시한다. T=top8, P=후보/top8 밖, C=저장소/후보 밖, ?=그 구절이 일치하지
않음이다. **?는 문서 부재가 아니며, T는 의미적 근거 충분성 통과가 아니다.**
아래 T는 검색 top8 기준이며, MIX_T3_063의 실제 packet 누락은 위에 별도로 기록했다.

| 문항 | 기존 그룹 | 주석 위치 | 대표근거 검토 | RRF 순위 |
| --- | --- | --- | --- | ---: |
| KBF_T2_018 | positive | TT? | 주석 위치만 점검·충분성 유보 | - |
| POS_T4_059 | refusal | T?? | 거절 생성 미검증 | - |
| SKH_T3_080 | positive | TT | 대표근거 top8 | 3 |
| MIX_T1_046 | positive | CTT | 주석 위치만 점검·충분성 유보 | - |
| NAV_T3_007 | positive | C? | 후보 있으나 top8 밖 | 16 |
| MIX_T3_048 | positive | CTTT | 후보 있으나 top8 밖 | 9 |
| SAM_T2_078 | positive | TTTTT | 주석 위치만 점검·충분성 유보 | - |
| CEL_T1_013 | positive | TT? | 주석 위치만 점검·충분성 유보 | - |
| CEL_T4_016 | refusal | C | 거절 생성 미검증 | - |
| KAK_T3_076 | refusal | C?C | 거절 생성 미검증 | - |
| HYU_T2_010 | positive | PPT | 주석 위치만 점검·충분성 유보 | - |
| HYU_T3_011 | positive | P | 후보 있으나 top8 밖 | 10 |
| MIX_T2_047 | positive | TT | 주석 위치만 점검·충분성 유보 | - |
| MIX_T4_049 | refusal | ? | 거절 생성 미검증 | - |
| LGE_T4_053 | refusal | ? | 거절 생성 미검증 | - |
| POS_T1_057 | positive | PT | 후보 있으나 top8 밖 | 27 |
| SKH_T1_060 | positive | CCTTT | 저장소 있으나 후보 밖 | - |
| NAV_T1_030 | positive | TT | 주석 위치만 점검·충분성 유보 | - |
| NAV_T4_008 | refusal | ? | 거절 생성 미검증 | - |
| NAV_T4_033 | refusal | ? | 거절 생성 미검증 | - |
| SAM_T3_028 | positive | TTC | 대표근거 top8 | 8 |
| SAM_T4_070 | refusal | ? | 거절 생성 미검증 | - |
| CEL_T2_039 | positive | TT | 대표근거 top8 | 1 |
| CEL_T4_041 | refusal | ? | 거절 생성 미검증 | - |
| MIX_T4_024 | refusal | ? | 거절 생성 미검증 | - |
| KAK_T3_055 | positive | CCC? | 저장소 있으나 후보 밖 | - |
| HYU_T3_072 | positive | P???? | 대표근거 top8 | 4 |
| HYU_T4_012 | refusal | ? | 거절 생성 미검증 | - |
| HYU_T4_037 | refusal | ? | 거절 생성 미검증 | - |
| KBF_T1_017 | diagnostic | TT | 기존 진단용 | - |
| KBF_T2_043 | positive | PPC | 주석 위치만 점검·충분성 유보 | - |
| KBF_T3_019 | positive | TTTT?T? | 주석 위치만 점검·충분성 유보 | - |
| KBF_T3_044 | positive | ?TTT | 대표근거 top8 | 7 |
| KBF_T4_020 | positive | TT | 대표근거 top8 | 1 |
| KBF_T4_045 | refusal | CC | 거절 생성 미검증 | - |
| MIX_T3_025 | positive | PTT | 후보 있으나 top8 밖 | 11 |
| LGE_T1_051 | positive | TTTT | 주석 위치만 점검·충분성 유보 | - |
| LGE_T2_052 | positive | TT | 주석 위치만 점검·충분성 유보 | - |
| LGE_T4_077 | refusal | PPP | 거절 생성 미검증 | - |
| POS_T1_075 | diagnostic | TTT | 기존 진단용 | - |
| POS_T2_058 | diagnostic | TTT | 기존 진단용 | - |
| SKI_T1_068 | positive | ?T | 주석 위치만 점검·충분성 유보 | - |
| SKI_T2_069 | positive | TT | 대표근거 top8 | 3 |
| MIX_T4_065 | refusal | PP | 거절 생성 미검증 | - |
| SKH_T2_061 | positive | PTTTTT | 후보 있으나 top8 밖 | 18 |
| MIX_T2_022 | positive | TTTTT | 주석 위치만 점검·충분성 유보 | - |
| MIX_T3_063 | positive | TPPT?? | 후보 있으나 top8 밖 | 19 |
| NAV_T1_005 | positive | T?C | 주석 위치만 점검·충분성 유보 | - |
| NAV_T1_071 | positive | TT | 주석 위치만 점검·충분성 유보 | - |
| NAV_T2_006 | positive | TT | 주석 위치만 점검·충분성 유보 | - |
| NAV_T2_031 | positive | TTTTT | 주석 위치만 점검·충분성 유보 | - |
| NAV_T3_032 | positive | TTTTTT | 주석 위치만 점검·충분성 유보 | - |
| MIX_T1_021 | positive | TTTTT | 주석 위치만 점검·충분성 유보 | - |
| MIX_T4_062 | refusal | TC | 거절 생성 미검증 | - |
| SAM_T1_001 | positive | TTC | 주석 위치만 점검·충분성 유보 | - |
| SAM_T1_026 | positive | PPC | 주석 위치만 점검·충분성 유보 | - |
| SAM_T2_027 | positive | TTTTCTC | 주석의 요청 적합성 유보 | - |
| SAM_T3_003 | positive | TTCT | 저장소 있으나 후보 밖 | - |
| SAM_T4_004 | positive | TTT | 주석 위치만 점검·충분성 유보 | - |
| SAM_T4_029 | refusal | PPP | 거절 생성 미검증 | - |
| CEL_T1_038 | positive | T?P | 대표근거 top8 | 6 |
| CEL_T2_014 | positive | ?? | 주석 위치만 점검·충분성 유보 | - |
| CEL_T2_073 | positive | ?T | 후보 있으나 top8 밖 | 20 |
| CEL_T3_015 | positive | P?P? | 저장소 있으나 후보 밖 | - |
| CEL_T3_040 | positive | ??? | 후보 있으나 top8 밖 | 11 |
| MIX_T3_050 | positive | ?? | 주석 위치만 점검·충분성 유보 | - |
| KAK_T1_054 | positive | ?T? | 주석 위치만 점검·충분성 유보 | - |
| KAK_T4_056 | refusal | T | 거절 생성 미검증 | - |
| KAB_T1_066 | positive | TT | 주석 위치만 점검·충분성 유보 | - |
| KAB_T3_067 | positive | TT?TTP | 대표근거 top8 | 8 |
| HYU_T1_009 | positive | ???CT | 주석 위치만 점검·충분성 유보 | - |
| HYU_T1_034 | positive | T???TTTT | 주석 위치만 점검·충분성 유보 | - |
| HYU_T2_035 | positive | C?CC | 저장소 있으나 후보 밖 | - |
| HYU_T3_036 | positive | TTP? | 대표근거 top8 | 8 |
| HYU_T4_079 | refusal | CPPP | 거절 생성 미검증 | - |
| MIX_T1_064 | positive | PPP | 후보 있으나 top8 밖 | 9 |
| MIX_T3_023 | positive | T??? | 알려진 원문 문단 누락 | - |
