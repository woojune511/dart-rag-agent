# v5 저장소의 77문항 검색·입력 비교

2026-09-29. **COMPLETE_OFFLINE_RETRIEVAL_AUDIT**. 추가 API 비용 **USD0**.

77문항의 검색과 실제 답변 입력 구성을 모두 완료했다. v3에서 빠졌던 회계 문단은
복구됐지만, 고정한 대표근거의 top8 전달은10→8로 감소했다. 별도 회계정책 대체근거의
전달도 발견했다. 따라서 **본문 보존 개선과 검색 순위 개선은 구분해야 한다**.
답변 생성·정답률·전체 근거 충분성은 평가하지 않았다.

## 고정 범위와 비교 방법

- 소스 `6a0c0c41`, 현재 v5 저장소11개 보고서·15,608청크의 바이트 동일 복사본 사용.
- 이전77개 질문·명시적 접수번호 범위·rubric·질문 벡터를 유지했다. 긍정55/거절19/진단3.
- `text-embedding-3-large`,3072차원77개 float32 벡터를 기존 봉인과 원시 요청/응답에 대조했다.
  토큰화한 전체 질문·순서·모델·차원이 일치했다. 미확보 임베딩을 새로 만드는 fallback은 없다.
- 실제 `VectorStoreManager.search`: dense16, 전체 corpus IDF의 범위 내 BM25 top24,
  RRF60 top8. 검색 cache와 query embedding fallback은 비활성화했다.
- 실제 `SimpleRagAgent.run`이 만든 packet을 모델 호출 직전에 가로채고 생성은 중단했다.
  질문·범위·원문·문맥만 전달되며 골드/평가 주석은 포함되지 않는다. 65,536바이트 한도를 유지했다.
- v3/v5의 검색·agent 파일64개가 동일함을 확인했다. 다만 corpus14,005→15,608,
  문서 벡터와 BM25 통계가 달라졌다. 소제목 하나만의 인과 실험이나 ANN 정확 검색 비교가 아니다.
- 이미 노출된 자체 데이터셋과 assistant 검토다. 독립 gold/holdout/일반 성능 주장이 아니다.

## 고정 대표근거 27문항

기존 검토 원문26개는 같은 보고서 안에서 **전체 텍스트가 정확히 같은 단일 청크**로 연결됐다.
추가1개는 과거 검토한 연결 배출권 회계 문단 전체를 공백·표 구분자만 정규화하여 연결했다.
연결은 새 검색 순위를 보기 전에 고정했다. ID·숫자만으로 매칭하지 않았다.
주석의 요청 적합성이 미확정인1개는 그대로 유보했다.

| 대표 구성요소 위치 | v3 | v5 |
| --- | ---: | ---: |
| top8 및 실제 packet에 있음 | 10 | 8 |
| 후보에 있지만 top8 밖 | 10 | 12 |
| 저장소에는 있지만 후보 밖 | 5 | 6 |
| 검토한 원문 문단이 저장소에서 누락 | 1 | 0 |
| 주석 적합성 유보 | 1 | 1 |

이 표는 **27개 대표 구성요소의 위치 비교**다. 55개 긍정 문항의 충분성/정답률이 아니다.
나머지28개 긍정 문항은 주석 구절의 위치만 기록했다. 거절19개는 생성하지 않았으므로
거짓 수치 답변·올바른 거절 여부를 평가할 수 없다. 기존 진단3개와 주석 범위 오류도 유지했다.

## 달라진 사례와 대체근거

| 문항 | 관측 |
| --- | --- |
| SAM_T3_028 | 연결 재고자산평가손실(환입) 등 대표표8→12위. BM253→5위이고 dense 후보에는 양쪽 모두 없음. 별도 수치와 재고 원가 설명은 top8에 있으므로 문항 전체 실패로 집계하지 않음. |
| HYU_T3_072 | 모셔널 출자·요약손익 행4→22위. BM2512위는 유지되지만 기존 dense13위에서 후보 밖으로 이동. 원문은 그대로 있고 상위8개 선택에서 제외됨. |
| CEL_T2_073 | 해외/전체 매출 표20위→후보 밖. 기존 dense13위가 사라졌고 BM25에는 양쪽 모두 없음. 직판 서술은 여전히 입력에 있음. |
| MIX_T3_023 | 과거 누락된 연결 회계 문단이 복구돼 BM2514/RRF25위. **별도 회계정책 문단은 새로4위에 들어 실제 packet에 전달**됨. |

탄소 질문은 환경 섹션 또는 주석을 허용하고 연결 범위를 명시하지 않는다. 별도 문단에는
무상 배출권과 매입 배출권, 무상할당 수량 충족/초과 시 배출부채 측정 설명이 실제로 있다.
이 대체근거 관측은 결과 후 별도로 검토했으며 고정 대표근거10→8 집계를 바꾸지 않는다.
반대로 연결 대표근거가25위라는 이유만으로 탄소 질문의 유용한 근거가 전혀 없다고 하지 않는다.
금액이 보고서 전체에 없다는 주장이나 실제 답변 성공도 아니다.

## 원문 전달·packet 한도

- 모든 후보의 원문과 보고서 범위, 소제목·절 문맥을 graph와 대조했다.
  기존 BM25의 앞뒤 공백 제거만 허용했다. 문맥 전달 일치는 제목의 의미적 정확성 인증이 아니다.
- 154개 저장 순위(v3/v5 각77)를 dense/BM25 목록에서 다시 계산했고 실제 v5 packet77개와
  독립 구성 결과가 일치했다. v3의 저장 packet ID/크기도 재구성과 일치했다.
- 원문 기준 top8 순서가 완전히 같은 문항35개, 달라진 문항42개.
- MIX_T3_063에서 packet 한도로 빠진 청크가 v3의3개에서 v5의2개로 바뀌었다.
  현재6개 source/65,435바이트. 이것도 문항의 필수근거 충분성 개선을 뜻하지 않는다.
- 주석 구절의 부분 매칭·미매칭·위치 변화는 `question_results.json`에 남겼다.
  문자열 미매칭은 문서 부재가 아니고 매칭은 기간/대상/단위 적합성 증명이 아니다.

## 실행과 검증

- 검색77/77, 실제 packet77/77, 저장 벡터 재생77회. 검색 오류·재시도·미실행0.
- 실제 감사 실행의 네트워크 시도0, provider 호출0, 신규 임베딩0, 답변 생성0, 비용USD0.
- 검색/packet 배치52.28초. 준비·복사·검증·원문 검토 시간은 제외했다.
- 기존 SimpleRag 계약 테스트16개 및 잘못된 질문/새 임베딩/외부 네트워크 차단3개 통제 통과.
  최초 preflight는 강한 socket 차단이 Windows ASGI의 내부 socketpair를 막아1개 실패했다.
  기존 테스트의 모의 provider 전송과 외부 접속 차단을 유지한 별도 HTTP 검증으로 해결했다.
  그때 검색은 시작 전이었고, 실제77검색은 전체 네트워크 차단 아래 한 번만 수행했다.
- 원본 v5 저장소·설정·코드·기존 결과 등 보호 파일530개를 실행 전후 대조했다.
  원시 기록과 옛 평가/봉인을 덮어쓰지 않았다. 수정은 이번 결과 문서와 현재 상태 기록뿐이다.

## 결론과 종료

원문 누락 복구는 확인됐으나 전체 검색 개선은 입증되지 않았다. 검토한 대표근거 중
12개는 후보에 있고6개는 후보에도 없어, 검색·상위8개 선택 문제는 여전히 남아 있다.
대체근거를 모두 검토하지 않았으므로 이18개를 곧바로 실패 문항으로 세지 않는다.
다음 개선을 검토한다면 새 LLM 호출 이전에 **후보 생성과 최종 선택을 구분**해야 한다.
이 결과만으로 LLM selector·top-k 증가·새 prompt를 도입하지 않았다.
답변 회귀 strict11/14의 미달 기록과 별도 파서 채택 결정은 그대로다.

기록: `benchmarks/results/full77_v5_retrieval_audit_2026-09-29/`.
복사본/77검색/77packet: `D:/CodexArtifacts/dart-rag-agent/full77_v5_retrieval_audit_2026-09-29/`.
주요 자료: `manifest.json`, `coverage.json`, `component_mapping.json`, `execution.json`,
`question_results.json`, `component_comparison.json`, `bounded_source_review.json`,
`reconstruction.json`, `completion.json`, `completion_seal.json`.
새 유료 실험·runtime 변경·원본 저장소 변경·커밋·push는 이번 범위에 포함하지 않았다.

## 문항별 고정 대표근거 비교

| 문항 | v3 위치/순위 | v5 위치/순위 | v5 입력 |
| --- | --- | --- | --- |
| SKH_T3_080 | top8/3 | top8/4 | 있음 |
| NAV_T3_007 | 후보/top8 밖/16 | 후보/top8 밖/18 | 없음 |
| MIX_T3_048 | 후보/top8 밖/9 | 후보/top8 밖/10 | 없음 |
| HYU_T3_011 | 후보/top8 밖/10 | 후보/top8 밖/10 | 없음 |
| POS_T1_057 | 후보/top8 밖/27 | 후보/top8 밖/28 | 없음 |
| SKH_T1_060 | 저장소/후보 밖/- | 저장소/후보 밖/- | 없음 |
| SAM_T3_028 | top8/8 | 후보/top8 밖/12 | 없음 |
| CEL_T2_039 | top8/1 | top8/1 | 있음 |
| KAK_T3_055 | 저장소/후보 밖/- | 저장소/후보 밖/- | 없음 |
| HYU_T3_072 | top8/4 | 후보/top8 밖/22 | 없음 |
| KBF_T3_044 | top8/7 | top8/7 | 있음 |
| KBF_T4_020 | top8/1 | top8/1 | 있음 |
| MIX_T3_025 | 후보/top8 밖/11 | 후보/top8 밖/11 | 없음 |
| SKI_T2_069 | top8/3 | top8/3 | 있음 |
| SKH_T2_061 | 후보/top8 밖/18 | 후보/top8 밖/18 | 없음 |
| MIX_T3_063 | 후보/top8 밖/19 | 후보/top8 밖/30 | 없음 |
| SAM_T2_027 | 주석 적합성 유보/- | 주석 적합성 유보/- | 없음 |
| SAM_T3_003 | 저장소/후보 밖/- | 저장소/후보 밖/- | 없음 |
| CEL_T1_038 | top8/6 | top8/6 | 있음 |
| CEL_T2_073 | 후보/top8 밖/20 | 저장소/후보 밖/- | 없음 |
| CEL_T3_015 | 저장소/후보 밖/- | 저장소/후보 밖/- | 없음 |
| CEL_T3_040 | 후보/top8 밖/11 | 후보/top8 밖/11 | 없음 |
| KAB_T3_067 | top8/8 | top8/8 | 있음 |
| HYU_T2_035 | 저장소/후보 밖/- | 저장소/후보 밖/- | 없음 |
| HYU_T3_036 | top8/8 | top8/8 | 있음 |
| MIX_T1_064 | 후보/top8 밖/9 | 후보/top8 밖/10 | 없음 |
| MIX_T3_023 | 검토 문단 누락/- | 후보/top8 밖/25 | 없음 |

## 전체77문항 위치표

P=packet, O=top8이나 byte 한도로 제외, R=후보/top8 밖, C=저장소/후보 밖,
?=정규화한 구절 미매칭. 각 문자는 고정 주석의 명시 구절 하나다.
**P는 의미적 근거 충분성 통과가 아니며, ?는 문서 부재가 아니다.**

| 문항 | 그룹 | v3 구절 위치 | v5 구절 위치 | v5 입력 source 수 |
| --- | --- | --- | --- | ---: |
| KBF_T2_018 | positive | PP? | PP? | 8 |
| POS_T4_059 | refusal | P?? | P?? | 8 |
| SKH_T3_080 | positive | PP | PP | 8 |
| MIX_T1_046 | positive | CPP | CPP | 8 |
| NAV_T3_007 | positive | C? | C? | 8 |
| MIX_T3_048 | positive | CPPP | CPPP | 8 |
| SAM_T2_078 | positive | PPPPP | PPPPP | 8 |
| CEL_T1_013 | positive | PP? | PPC | 8 |
| CEL_T4_016 | refusal | C | C | 8 |
| KAK_T3_076 | refusal | C?C | C?C | 8 |
| HYU_T2_010 | positive | RRP | RRP | 8 |
| HYU_T3_011 | positive | R | R | 8 |
| MIX_T2_047 | positive | PP | PP | 8 |
| MIX_T4_049 | refusal | ? | ? | 8 |
| LGE_T4_053 | refusal | ? | ? | 8 |
| POS_T1_057 | positive | RP | RP | 8 |
| SKH_T1_060 | positive | CCPPP | CCPPP | 8 |
| NAV_T1_030 | positive | PP | PP | 8 |
| NAV_T4_008 | refusal | ? | ? | 8 |
| NAV_T4_033 | refusal | ? | ? | 8 |
| SAM_T3_028 | positive | PPC | RPC | 8 |
| SAM_T4_070 | refusal | ? | ? | 8 |
| CEL_T2_039 | positive | PP | PP | 8 |
| CEL_T4_041 | refusal | ? | ? | 8 |
| MIX_T4_024 | refusal | ? | ? | 8 |
| KAK_T3_055 | positive | CCC? | CCC? | 8 |
| HYU_T3_072 | positive | R???? | R???? | 8 |
| HYU_T4_012 | refusal | ? | ? | 8 |
| HYU_T4_037 | refusal | ? | ? | 8 |
| KBF_T1_017 | diagnostic | PP | PP | 8 |
| KBF_T2_043 | positive | RRC | RRC | 8 |
| KBF_T3_019 | positive | PPPP?P? | PPPP?P? | 8 |
| KBF_T3_044 | positive | ?PPP | ?PPP | 8 |
| KBF_T4_020 | positive | PP | PP | 8 |
| KBF_T4_045 | refusal | CC | CC | 8 |
| MIX_T3_025 | positive | RPP | RPP | 8 |
| LGE_T1_051 | positive | PPPP | PPPP | 8 |
| LGE_T2_052 | positive | PP | PP | 8 |
| LGE_T4_077 | refusal | RRR | RRR | 8 |
| POS_T1_075 | diagnostic | PPP | PPP | 8 |
| POS_T2_058 | diagnostic | PPP | PPP | 8 |
| SKI_T1_068 | positive | ?P | ?P | 8 |
| SKI_T2_069 | positive | PP | PP | 8 |
| MIX_T4_065 | refusal | RR | RR | 8 |
| SKH_T2_061 | positive | RPPPPP | RPPPPP | 8 |
| MIX_T2_022 | positive | PPPPP | PPPPP | 8 |
| MIX_T3_063 | positive | ORRO?? | RRRR?? | 6 |
| NAV_T1_005 | positive | P?C | P?C | 8 |
| NAV_T1_071 | positive | PP | PP | 8 |
| NAV_T2_006 | positive | PP | PP | 8 |
| NAV_T2_031 | positive | PPPPP | PPPPP | 8 |
| NAV_T3_032 | positive | PPPPPP | PPPRRR | 8 |
| MIX_T1_021 | positive | PPPPP | PPPPP | 8 |
| MIX_T4_062 | refusal | PC | PC | 8 |
| SAM_T1_001 | positive | PPC | PPC | 8 |
| SAM_T1_026 | positive | RRC | RRC | 8 |
| SAM_T2_027 | positive | PPPPCPC | PPPPCPC | 8 |
| SAM_T3_003 | positive | PPCP | PPCP | 8 |
| SAM_T4_004 | positive | PPP | PPP | 8 |
| SAM_T4_029 | refusal | RRR | RRR | 8 |
| CEL_T1_038 | positive | P?R | P?R | 8 |
| CEL_T2_014 | positive | ?? | ?? | 8 |
| CEL_T2_073 | positive | ?P | ?P | 8 |
| CEL_T3_015 | positive | R?R? | R?C? | 8 |
| CEL_T3_040 | positive | ??? | ??? | 8 |
| MIX_T3_050 | positive | ?? | ?C | 8 |
| KAK_T1_054 | positive | ?P? | ?P? | 8 |
| KAK_T4_056 | refusal | P | P | 8 |
| KAB_T1_066 | positive | PP | PP | 8 |
| KAB_T3_067 | positive | PP?PPR | PP?PPR | 8 |
| HYU_T1_009 | positive | ???CP | ???CP | 8 |
| HYU_T1_034 | positive | P???PPPP | P???PPPP | 8 |
| HYU_T2_035 | positive | C?CC | C?CC | 8 |
| HYU_T3_036 | positive | PPR? | PPRR | 8 |
| HYU_T4_079 | refusal | CRRR | CRRR | 8 |
| MIX_T1_064 | positive | RRR | RRR | 8 |
| MIX_T3_023 | positive | P??? | PRPP | 8 |
