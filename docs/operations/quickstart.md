# 로컬 실행 안내

[프로젝트 홈](../../README.md) · [아키텍처](../overview/project_overview.md) ·
[평가 결과](../evaluation/README.md)

## 저장된 사례 보기

[웹 데모](https://woojune511.github.io/dart-rag-agent/)는 설치나 API 키 없이 열 수 있습니다.
오프라인에서는 저장소를 내려받아 [demo/index.html](../../demo/index.html)을
브라우저로 엽니다. 새 질문을 실행하는 화면은 아닙니다.

```powershell
Start-Process (Resolve-Path 'demo/index.html').Path
```

선택적으로 저장 데이터의 무결성을 확인합니다. Python 표준 라이브러리만
사용하며 검색·모델 호출은 발생하지 않습니다.

```bash
python -I -S demo/verify.py
```

## 실제 API와 Streamlit 실행

Python 3.13과 `uv`, 사용할 모델의 API 키, **공개 코드와 호환되는 기존 공시
store**가 필요합니다. 저장소 다운로드만으로 공시 원문·임베딩 store가 준비되지는
않습니다. 새 수집·임베딩과 실제 질의에는 provider 호출·비용이 발생할 수 있습니다.

공개 코드의 기준은 [.python-version](../../.python-version)과
[runtime 설정](../../src/config/runtime_contract.py)입니다. 다른 parser로 만든
로컬 store를 그대로 사용하면 readiness가 실패할 수 있습니다. Python 3.14는
이 저장소의 CI 기준 버전이 아닙니다.

### 1. 모델과 기존 store 지정

프로젝트 `.env` 또는 프로세스 환경에서 설정합니다. 다음 store 경로와 collection은
**예시 자리표시자**이며 실제 준비한 값으로 바꿔야 합니다.

```dotenv
DART_LLM_PROFILE=openai
OPENAI_API_KEY=your-api-key
DART_STORE_PATH=path/to/compatible-store
DART_COLLECTION_NAME=your-collection
```

`openai` 설정은 답변 `gpt-5.6-terra` / low / 최대 8,192 tokens, ingest 문맥
`gpt-5.6-luna` / none / 최대 512 tokens를 사용합니다. 둘 다 timeout 90초,
`store=false`, standard tier, SDK retry 0입니다. 실제 route는
[llm_profiles.py](../../src/config/llm_profiles.py)에서 확인합니다.

프로세스 환경이 `.env`보다 우선합니다. `DART_LLM_PROFILE`을 비워 두면 Google
경로가 선택됩니다. `openai_compiler`는 비교 전용이며 앱 시작 시 거절됩니다.
모델 설정은 요청별 설정으로, 총비용 상한을 자동으로 부여하지 않습니다.
DART 원문을 새로 가져오는 작업에는 별도 DART 자격 증명도 필요합니다.

### 2. API 시작

저장소 루트에서 실행합니다.

```bash
uv run --python 3.13 --with-requirements requirements.txt uvicorn main:app --reload --port 8000
```

Swagger UI: [http://localhost:8000/docs](http://localhost:8000/docs).
API는 `StoreManifestV1`의 parser·embedding·collection 식별자가 일치해야 질의를
제공합니다. store가 없거나 맞지 않으면 503을 반환합니다. 경로를 지정하는 것은
store 재구축·collection 이름 변경·manifest 자동 수정을 수행하지 않습니다.
[호환성 계약](../architecture/agent_runtime_contract.md)

### 3. Streamlit 시작

```bash
uv run --python 3.13 --with-requirements requirements.txt streamlit run app.py
```

기본 주소는 [http://localhost:8501](http://localhost:8501)입니다. Streamlit은
같은 API 소유 서비스를 직접 구성하므로 FastAPI 서버를 별도로 시작할 필요는
없습니다. 답변과 인용 원문, 보류 여부, 검증 미수행 표시를 함께 확인합니다.

## 개발 검증과 과거 비교 경로

전체 테스트는 실제 질의 실행과 별개입니다.

```bash
uv run --python 3.13 --with-requirements requirements.txt python -m unittest discover -s tests
```

과거 Planner/Compiler fixture는 가벼운 별도 profile로 확인할 수 있습니다.
이 명령은 기본 Simple RAG의 실시간 검색·답변을 실행하지 않습니다.

```bash
uv run --python 3.13 --with-requirements requirements-review.txt python -m src.ops.portfolio_demo
uv run --python 3.13 --with-requirements requirements-review.txt python -m src.ops.portfolio_review_gates
uv run --python 3.13 --with-requirements requirements-review.txt python -m src.ops.audit_runtime_domain_terms
```

[과거 fixture 안내](../overview/demo_walkthrough.md) ·
[실행 검증 상태](../overview/project_status.md) ·
[CI workflow](../../.github/workflows/validation.yml)
