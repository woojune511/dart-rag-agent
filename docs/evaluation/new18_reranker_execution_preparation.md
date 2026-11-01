# 새 18문항 경량 Reranker 비교 실행 준비

작성일: 2026-10-15. **한국어 지원 모델 `Qwen/Qwen3-Reranker-0.6B` 하나를 선정했다.** 저장된622개 질문–후보 쌍을 로컬 CPU에서 각1회 채점하고, 최종8개 근거를 현재 RRF와 비교하는 조건이다. 모델 가중치 다운로드·모델 추론·답변 생성은 아직 실행하지 않았다.

목표는 HD현대일렉트릭 경영진단 원인을 복구하면서 U08·U15를 포함한 기존 필수 근거를 보존하는지 확인하는 것이다. [CC·DBSF 비교](new18_score_fusion_evidence_comparison.md)는 HD를 복구했지만 U08·U15의 기존 근거를 잃었다. 같은 후보 합집합에서 본문을 읽는 모델이 다른 선택을 하는지 평가하며, 새 검색이나 질문별 규칙을 추가하지 않는다.

## 선정 모델과 로컬 환경

Qwen 공식 자료는0.6B 규모, 한국어를 포함한100개 이상 언어,32K 입력, Apache-2.0 라이선스를 명시한다. 기본 Transformers 구현으로 질문–문서 관련성을 마지막 위치의 yes/no logit 차이로 평가할 수 있다. 한국어 지원과 공개 벤치마크가 DART 근거 개선을 보장하지는 않는다. [공식 모델 카드](https://huggingface.co/Qwen/Qwen3-Reranker-0.6B), [공식 언어 목록](https://github.com/QwenLM/Qwen3-Embedding#multilingual-support)

모델과 토크나이저 revision은 `e61197ed45024b0ed8a2d74b80b4d909f1255473`으로 고정했다. 모델 파일은1,191,588,280bytes이며 SHA256은 `27cd75a405b9c1b46b59abfd88aaa209e6fed2a1972cde9b70e7659537c5e65b`다. 실행 때 main의 새 버전을 받지 않는다. [고정 revision](https://huggingface.co/Qwen/Qwen3-Reranker-0.6B/tree/e61197ed45024b0ed8a2d74b80b4d909f1255473)

현재 PC는 Ryzen7 7800X3D8코어, 약32GB RAM, RTX5060Ti8GB다. 그러나 저장소의 PyTorch는 **2.10.0+cpu**이며 CUDA를 사용할 수 없다. 기존 환경을 유지해 CPU·float32·batch1·연산 스레드8개·interop1개로 준비했다. GPU용 PyTorch 설치, 별도 GPU 환경, 양자화나 다른 모델로의 자동 전환은 포함하지 않는다.

Transformers5.3.0의 기본 Qwen3 클래스 import와 `logits_to_keep` 인자를 확인했다. 이는 모델 로드·추론 성공 검증은 아니다. 실행은 `eval()`·`inference_mode()`·SDPA·`use_cache=False`·`logits_to_keep=1`을 고정한다. 마지막 위치만 계산하므로 모든 토큰의 vocabulary logits를 만들 필요가 없다. `generate()`는 호출하지 않는다. [Qwen3 forward 문서](https://huggingface.co/docs/transformers/model_doc/qwen3#transformers.Qwen3ForCausalLM.forward)

## 준비 중 확인한 입력

공개 토크나이저·설정5개 파일15,881,773bytes만 내려받아 revision의 blob/LFS 해시와 대조했다. 가중치는 받지 않았다. 원래 질문과 후보 본문에 공식 입력 형식을 적용해 실제 토큰 길이를 계산했다.

| 항목 | 확인 결과 |
|---|---:|
| 질문 |18개,3개 보고서 |
| 고정 후보 합집합 |622개 질문–후보 쌍 |
| 기존 RRF 문맥 재현 |18/18, 내용·순서 일치 |
| 전체 입력 토큰 |529,588 |
| 평균 / 중앙값 |851.4 /673 |
| 95백분위 / 최대 |2,024 /3,055 |
| 허용 길이 |공식 template 포함32,768 |
| 초과 / 절단 |0 /0 |

현재 입력은 모두 무절단 처리 범위에 있다.32K 지원 자체가 이번 데이터에서 성능 우위의 근거는 아니다. 각 입력의 토큰 ID와 해시도 저장해 이후 tokenizer 기본값 변경을 방지했다.

## 고정 실행 조건

| 항목 | RRF 기준 | Qwen reranker |
|---|---|---|
| 후보 |저장 Dense16·BM25 최대24의 UID 합집합 |같은 합집합 |
| 질문·범위 |원래 질문·명시적 회사/보고서 범위 |동일 |
| 순위 |동일 가중RRF, 상수60 |질문–문서별 raw `yes_logit-no_logit` 내림차순 |
| 최종 문맥 |8개,65,536 UTF-8 bytes |동일 |
| 동점 |기존 Dense 우선 합집합 삽입 순서 |동일 |
| 본문·출처 |저장 원문·메타데이터·출처 ID |동일 |
| 추가 처리 |없음 |RRF 재혼합·threshold·backfill·본문 중복 제거·요약·분할 없음 |

모델 입력은 **원래 질문과 저장된 후보 본문**이다. 본문에 원래 포함된 표제·기간·단위 접두어는 유지한다. 별도 출처 ID, 문항 ID, gold, 필수 근거 라벨, 기존 순위·점수·판정은 넣지 않는다. 최종 답변용 문맥을 재구성할 때는 기존 source context와 출처 ID를 그대로 보존한다.

instruction은 공식 기본값 하나를 모든 문항에 사용한다.

`Given a web search query, retrieve relevant passages that answer the query`

공식 system prefix와 비추론 suffix를 포함한 template는 manifest (`../../benchmarks/results/new18_reranker_preparation_2026-10-15/manifest.json`, local artifact not included)에 고정했다. 한국어 번역이나 DART·회사별 지시문을 추가하지 않는다. sigmoid 점수는 관찰용으로만 기록하고 정렬에는 raw logit 차이를 사용한다.

622쌍을 각각 한 번만 평가한다. 추가 warm-up·pilot·재시도·두 번째 seed 실행을 더하지 않으며, 첫 실제 평가도622쌍 안에 포함한다. 현재18문항의 두 답변 반복은 같은 검색 결과를 공유했으므로 reranker를 반복 평가 표본으로 세지 않는다.

## 예상 비용과 실행 상한

| 항목 | 예상 또는 상한 |
|---|---|
| 외부 모델 API |**0회·$0** |
| 로컬 모델 평가 |**최대622쌍, 각1회**, batch1 |
| 새 임베딩·답변 생성·유료 judge |각0회 |
| 실행 시 추가 다운로드 |고정 가중치 약1.19GB; 이미 준비한 토크나이저 약15.9MB |
| 가중치 메모리 |FP32 변환 시 약2.38GB; 전체 실행 메모리는 미측정 |
| 프로세스 메모리 상한 |8GiB RSS |
| 다운로드 시간 상한 |30분 |
| 모델 로드 포함 추론 시간 상한 |2시간 |
| 실행 전체 시간 상한 |2시간30분 |
| 시작 전 자원 조건 |사용 가능 RAM8GiB 이상, 여유 디스크3GiB 이상 |

**시간 상한은 ETA가 아니다.** 실제 속도·peak RAM은 모델을 실행하지 않아 알 수 없다. 약53만 입력 토큰의 CPU 평가이며,622회가 외부 유료 호출을 뜻하지 않는다. 로컬 전력·컴퓨터 점유 비용은$0 API 비용과 별개다. 클라우드 GPU 임대나 GPU 라이브러리 설치 비용은 계획에 포함하지 않는다.

준비 시점 여유 RAM은 약10.34GiB, 디스크는 약9.85GiB였으나 실행 시작 때 다시 확인한다. 가중치는 실험 전용 폴더로 직접 받아 해시를 검증하고 기존 store·`.env`·전역 모델 캐시·설치 패키지는 수정하지 않는다. 추론 단계에서는 네트워크를 차단한다.

## 성공과 회귀 판정

기존33개 필수 근거 그룹과 허용된 대체 근거를 유지한다. 답변 생성 없이 원문 대상·기간·단위·관계를 확인하고66개 그룹 판정(RRF33+reranker33)을 기록한다.

필수 그룹 개선 gate는 다음을 모두 만족해야 한다.

1. U04.1의 지정한 중동·미주 매출 증가 및 수익성 개선 원문이 최종8개에서 복구된다.
2. 현재 RRF에서P인26개 그룹이 **모두** 유지된다. 합계만 맞추는 교환은 불허한다.
3. 따라서 최소27/33개 그룹, 기존 완비13문항 유지 및 U04 추가로 최소14/18문항이어야 한다.
4. U08.2·U15.1을 포함한 전체18문항을 판정한다. 기존 미완비 문항 내부의 추가 손실도 회귀다.

| 주요 대상 | 확인 내용 |
|---|---|
| HD U04 |1128:1의 원인과2025 실적 연결; 기존 넓은 답변U는 재채점하지 않음 |
| U06 |현재 연결 잔고, 계약 기한·진행률의 부분 손실 |
| U08 |법인별 매출값과 범위 연결; 국가명/지역 정의만 남는 경우 제외 |
| U10·U12 |필수 그룹과 별도로 환율10% 민감도 등 상세 근거 손실 |
| U14 |부문별 수치 보존 및 상충하는 개선 서술 추가 |
| U15 |TR·호텔 수요 원인, 이미F인 그룹 안의 손익 방향 근거, 값 없는 표제 점유 |
| U18 |예측 주의와2025 영업흑자·순손실 동시 보존 |
| 전체18 |잘못된 기간·대상·단위, 상충 근거, 유효한 대체 근거 |

필수 그룹 gate를 통과해도 중대한 부분 손실·상충 근거가 추가되면 그 사실을 별도 보고하며 “전체 회귀 없음”으로 결론내리지 않는다. 기존26/33→25/33,13/18→14/18처럼 문항 수와 그룹 수가 엇갈리는 상황을 다시 확인한다.

후보에 없는U09 영업현금흐름, U15 위약금 원인, U16 현재현금/리스 등은 이 비교로 복구할 수 없다. 원래 기준을 완화하거나 특정 UID를 반드시 선택하는 규칙을 모델에 제공하지 않는다. 이번 패널은 이미 노출된 개발 진단이며, 통과해도 기본 runtime 채택이나 실제 답변 개선으로 간주하지 않는다.

## 실행 절차와 중단 조건

1. 고정 입력·평가 기준·코드·기존 결과 해시와 자원을 확인한다. 저장된 RRF18개 문맥 재현을 통과한다.
2. 고정 revision의 단일 가중치 파일만 받아 크기와 SHA256을 검증한다. 이후 모델을 로컬 파일만으로 로드한다.
3.622쌍을 순서대로 각1회 평가하며 입력 해시·전체 점수·소요시간·메모리를 기록한다.30초마다 heartbeat를 기록하고 첫 결과까지10분을 초과하면 중단한다.
4. 각 문항에서 점수순8개를 선택하고 원래 문맥을 재구성한다. 전체 순위·동점·출처·바이트 한도를 검증한다.
5. 동일33개 그룹과 부분 손실을 원문 대조하고, 기존 파일 보존을 확인한다.

입력·모델 revision·해시 불일치, 길이 초과, 로드/추론 오류, 비유한 점수, 메모리/시간 초과, 누락·중복 평가, 최종 문맥 바이트 초과 시 중단한다. 중단된 비교는 미완료로 남긴다. 재시도·자동 resume·GPU/CPU 전환·정밀도 변경·양자화·다른 모델·문장 절단으로 자동 우회하지 않는다. 실행 시 자원 감독이 진행 중인 forward도 종료할 수 있어야 하며 단순히 다음 반복에서 한도를 확인하는 것으로 대체하지 않는다.

## 준비 산출물

- 고정 모델과 실행 조건 (`../../benchmarks/results/new18_reranker_preparation_2026-10-15/manifest.json`, local artifact not included)
- 622개 입력과 토큰 ID (`../../benchmarks/results/new18_reranker_preparation_2026-10-15/frozen_pairs.json`, local artifact not included), 후보 명단 (`../../benchmarks/results/new18_reranker_preparation_2026-10-15/roster.json`, local artifact not included), RRF 기준 문맥 (`../../benchmarks/results/new18_reranker_preparation_2026-10-15/baseline_packets.json`, local artifact not included)
- 토큰 길이와 작업량 (`../../benchmarks/results/new18_reranker_preparation_2026-10-15/preflight.json`, local artifact not included), 공개 모델 메타데이터 (`../../benchmarks/results/new18_reranker_preparation_2026-10-15/public_model_metadata.json`, local artifact not included), 토크나이저 파일 해시 (`../../benchmarks/results/new18_reranker_preparation_2026-10-15/tokenizer_assets.json`, local artifact not included)
- 준비 검증과 보존 (`../../benchmarks/results/new18_reranker_preparation_2026-10-15/preparation_closeout.json`, local artifact not included)

준비 상태는 **PREPARED_NOT_EXECUTED**다. 가중치 다운로드, 모델 forward, 새로운 답변 정확도·누락·출처 충실도 평가는NOT_RUN이다. 현재 RRF·기존 store·`.env`·소스·과거 평가를 유지하며, 실험 자료는 로컬 결과 폴더에 둔다. stage·commit·push하지 않았다.
