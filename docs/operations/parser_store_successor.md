# Parser store successor

Owner: `src.ops.build_parser_store_successor`. 기존 graph를 재임베딩하는
`rebuild_vector_store`와 달리 원본 HTML부터 다시 파싱한다. 두 CLI 단계 모두
외부 socket을 차단하며 provider·fetcher·context generator를 만들지 않는다.
실제 작업용 복사본 및 새 저장소 쓰기는 별도 승인 후 실행한다.

## 1. Prepare

먼저 `src.ops.plan_parser_store_successor`로 만든 전체 filing inventory와 원래
source spec을 고정한다. `prepare`는 다음을 수행한다.

- 원본 파일·저장소 전체 SHA와 manifest를 확인한다.
- inventory와 동일한 parser 설정·prefix로 재투영하고 fingerprint를 비교한다.
- 새로운 작업 폴더의 `source_copy/`에만 Chroma를 연다. 원본은 열지 않는다.
- 같은 filing 안의 완전히 같은 index text에만 실제 벡터를 연결한다.
  원래 후보 ID를 바꾸거나 예전 payload를 새 metadata로 채택하지 않는다.
- 재사용 예정 벡터가 없거나 손상됐으면 중단한다. 유료 요청으로 바꾸지 않는다.
- 새 텍스트는 exact SHA로 중복 제거하여 `embedding_request.json`에 기록한다.
  `prepared.json`에는 새 metadata·parents·재사용 벡터·원본 hash가 담긴다.

```powershell
python -m src.ops.build_parser_store_successor prepare --inventory <inventory.json> --inventory-sha256 <SHA> --spec <source_spec.json> --store-index <0-based-index> --workspace <new-workspace>
```

이 단계에서 실제 source-copy 검증 전의 재사용 개수는 추정치다. 단순히
chunk ID가 같다는 이유로 재사용하지 않으며, 같은 text의 ID 변경은 허용한다.

## 2. Supply vectors, then build

추가 임베딩 실행은 `embedding_request.json`의 정확한 text, provider/model/
dimension, fingerprint 및 비용 한도를 별도로 승인받는다. 이 도구에는 API
호출이나 자동 retry 기능이 없다. 공급 파일 형태는 다음과 같다.

```json
{
  "schema_version": "parser_successor_embeddings_v1",
  "request_fingerprint": "<embedding_request.json fingerprint>",
  "embedding": {"provider": "<provider>", "model_name": "<model>", "dimension": 3},
  "vectors_by_text_sha256": {"<requested text SHA>": [0.1, 0.2, 0.3]}
}
```

표시된 dimension/vector는 형식 예시일 뿐이다. 실제 차원·모델은 request와
정확히 같아야 하며, 요청에 없는 벡터나 누락된 벡터를 허용하지 않는다.
추가 요청이 0개라면 embeddings 인자를 생략할 수 있다.

```powershell
python -m src.ops.build_parser_store_successor build --prepared <prepared.json> --prepared-sha256 <SHA> --embeddings <supplied.json> --embeddings-sha256 <SHA> --output-store <new-store>
```

빌드는 공급 벡터만 사용한다. 새로운 graph/table payload/parents와 벡터를
저장한 뒤 닫고 다시 열어 모든 ID·text·metadata·벡터를 확인하고 dense probe를
실행한다. 이후 `store_manifest.json`을 마지막에 발행한다.

## Failure and resume

- 실패한 결과와 작업 복사본은 자동 삭제하지 않는다. 기존 저장소를 덮어쓰는
  `force`/in-place 옵션은 없다.
- manifest가 없으면 query-ready가 아니다. `prepared.json` 및
  `build_receipt.json`의 사전 검증 성공은 readiness를 대신하지 않는다.
- 중단 후 동일 입력으로 `build ... --resume`을 명시하면 이미 저장된 벡터를
  검증하고 누락분·sidecar를 복구한다. provider 호출은 발생하지 않는다.
- 입력 fingerprint가 다르거나 기존 벡터/text/metadata가 다르면 중단한다.
  manifest가 이미 있는 동일 successor는 재검증만 수행한다.

실제 전환 결과 및 다음 승인 범위는 [project status](../overview/project_status.md)에
기록한다. 유료 평가, 원본 store mutation, dataset/evaluator 변경은 이 도구의
범위가 아니다. 임시 실제-Chroma 계약 테스트는 `tests/test_build_parser_store_successor.py`.
