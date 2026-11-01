# 공개 실험 코드와 결과

[최신 결과 해석](../../docs/evaluation/table_evidence_research_2026-10-24.md) · [전체 평가 문서](../../docs/evaluation/README.md)

2026-11-02 공개 묶음입니다. 기존 실험을 다시 실행하거나 결과를 바꾸지 않고,
사용자가 요청한 최근 개선·실험의 코드, 고정 조건, 요약 판정과 보고서를 포함합니다.
실험이 실제 사용한 상대 경로와 코드 해시를 유지하기 위해 선택 파일만
`benchmarks/results/`에 명시적으로 포함했습니다. 나머지 결과 폴더는 계속 ignored입니다.
새 결과 디렉터리 전체를 `git add -f`로 추가하지 마세요. 허용 목록은
[`rag_experiments_202610_manifest.json`](rag_experiments_202610_manifest.json)입니다.

## 검증과 재현 범위

원본/공개 SHA-256와 파일 크기를 기록했습니다. Python 코드는 원본 바이트를 유지합니다.
일부 보고서는 로컬 PC 경로를 가리고, 미포함 로컬 산출물의 링크를 일반 텍스트로 바꿨습니다.
JSON은 저장된 결과이며 manifest 일치는 무결성 검사이지 독립적 정확도 검증이 아닙니다.

```bash
python -I -S benchmarks/published/verify.py
python -m unittest discover -s benchmarks/results/table_bundle_delivery_offline_20261022 -p test_projector.py
python -m unittest discover -s benchmarks/results/table_fact_units_offline_20261023 -p test_projector.py
python -m unittest discover -s benchmarks/results/table_fact_units_offline_20261023 -p test_runner.py
```

첫 명령은 표준 라이브러리만 사용합니다. 합성 계약 테스트는 프로젝트 의존성(`lxml` 등)을
설치한 환경에서 각각 별도 프로세스로 실행하며 원문·store·API가 필요 없습니다.
이 테스트는 물리적 표 연결과 원자적 예산 처리를 검증하며 새 답변 품질을 측정하지 않습니다.

**전체 역사적 실험은 clone만으로 재실행할 수 없습니다.** 과거 raw 원문 export, 고정 후보,
임베딩, 요청·응답 패킷, 일부 review 자료와 store는 포함하지 않았습니다. 각 `run.py`,
`prepare.py`, `launch.py` 등은 당시 코드 스냅샷입니다. 경로에 필요한 로컬 입력이 없으면
실패할 수 있으며, 모델 실행 스크립트는 별도 자격 증명과 비용이 필요합니다.
공개 검증 명령은 위의 provider-free 명령만 대상으로 합니다.

`.env`·API 키·활성 및 평가 store·캐시·전체 provider payload·개인 이력서/면접 문서는 제외했습니다.
표 근거 보강, 160KiB, 형태소 분석기와 검색 스키마는 기본 앱에 연결하지 않았습니다.

## 최근 실험 목록

| 실험 디렉터리 | 보고서 또는 요약 | 고정 조건 |
| --- | --- | --- |
| [dart_representation_pilot10_20261021](../results/dart_representation_pilot10_20261021/) | [REPORT.md](../results/dart_representation_pilot10_20261021/REPORT.md) | [pre_source_protocol.json](../results/dart_representation_pilot10_20261021/pre_source_protocol.json) |
| [nori_structural_tf_offline_20261022](../results/nori_structural_tf_offline_20261022/) | [report.md](../results/nori_structural_tf_offline_20261022/report.md) | [protocol.json](../results/nori_structural_tf_offline_20261022/protocol.json) |
| [samsung_cashflow_rank_diagnosis_20261021](../results/samsung_cashflow_rank_diagnosis_20261021/) | [REPORT.md](../results/samsung_cashflow_rank_diagnosis_20261021/REPORT.md) | see report |
| [table_bundle_delivery_offline_20261022](../results/table_bundle_delivery_offline_20261022/) | [report.md](../results/table_bundle_delivery_offline_20261022/report.md) | [protocol.json](../results/table_bundle_delivery_offline_20261022/protocol.json) |
| [table_fact_adoption_review_20261024](../results/table_fact_adoption_review_20261024/) | [report.md](../results/table_fact_adoption_review_20261024/report.md) | see report |
| [table_fact_answer_full77_20261023](../results/table_fact_answer_full77_20261023/) | [report.md](../results/table_fact_answer_full77_20261023/report.md) | [protocol.json](../results/table_fact_answer_full77_20261023/protocol.json) |
| [table_fact_answer_pilot_20261023](../results/table_fact_answer_pilot_20261023/) | [report.md](../results/table_fact_answer_pilot_20261023/report.md) | [protocol.json](../results/table_fact_answer_pilot_20261023/protocol.json) |
| [table_fact_app_top8_answers_20261024](../results/table_fact_app_top8_answers_20261024/) | [report.md](../results/table_fact_app_top8_answers_20261024/report.md) | see report |
| [table_fact_app_top8_preparation_20261024](../results/table_fact_app_top8_preparation_20261024/) | [report.md](../results/table_fact_app_top8_preparation_20261024/report.md) | [protocol.json](../results/table_fact_app_top8_preparation_20261024/protocol.json) |
| [table_fact_budget77_offline_20261023](../results/table_fact_budget77_offline_20261023/) | [report.md](../results/table_fact_budget77_offline_20261023/report.md) | [protocol.json](../results/table_fact_budget77_offline_20261023/protocol.json) |
| [table_fact_budget_diagnostic_20261023](../results/table_fact_budget_diagnostic_20261023/) | [report.md](../results/table_fact_budget_diagnostic_20261023/report.md) | see report |
| [table_fact_holdout18_preparation_20261023](../results/table_fact_holdout18_preparation_20261023/) | [plan.md](../results/table_fact_holdout18_preparation_20261023/plan.md) | [protocol.json](../results/table_fact_holdout18_preparation_20261023/protocol.json) |
| [table_fact_holdout18_preparation_20261023/execution](../results/table_fact_holdout18_preparation_20261023/execution/) | [report.md](../results/table_fact_holdout18_preparation_20261023/execution/report.md) | see report |
| [table_fact_identifiability_audit_20261022](../results/table_fact_identifiability_audit_20261022/) | [report.md](../results/table_fact_identifiability_audit_20261022/report.md) | [protocol.json](../results/table_fact_identifiability_audit_20261022/protocol.json) |
| [table_fact_units_offline_20261023](../results/table_fact_units_offline_20261023/) | [report.md](../results/table_fact_units_offline_20261023/report.md) | [protocol.json](../results/table_fact_units_offline_20261023/protocol.json) |
| [table_row_fixed_stats_offline_20261022](../results/table_row_fixed_stats_offline_20261022/) | [summary.json](../results/table_row_fixed_stats_offline_20261022/summary.json) | [protocol.json](../results/table_row_fixed_stats_offline_20261022/protocol.json) |
| [table_row_search_offline_20261022](../results/table_row_search_offline_20261022/) | [summary.json](../results/table_row_search_offline_20261022/summary.json) | [protocol.json](../results/table_row_search_offline_20261022/protocol.json) |
| [table_schema_fact_interaction_offline_20261023](../results/table_schema_fact_interaction_offline_20261023/) | [report.md](../results/table_schema_fact_interaction_offline_20261023/report.md) | [protocol.json](../results/table_schema_fact_interaction_offline_20261023/protocol.json) |
| [table_schema_search_offline_20261022](../results/table_schema_search_offline_20261022/) | [automated_summary.json](../results/table_schema_search_offline_20261022/automated_summary.json) | [protocol.json](../results/table_schema_search_offline_20261022/protocol.json) |
| [table_schema_search_validated_offline_20261022](../results/table_schema_search_validated_offline_20261022/) | [report.md](../results/table_schema_search_validated_offline_20261022/report.md) | [protocol.json](../results/table_schema_search_validated_offline_20261022/protocol.json) |
| [tokenizer_kiwi_offline_20261022](../results/tokenizer_kiwi_offline_20261022/) | [report.md](../results/tokenizer_kiwi_offline_20261022/report.md) | [protocol.json](../results/tokenizer_kiwi_offline_20261022/protocol.json) |
| [tokenizer_nori_idf_offline_20261022](../results/tokenizer_nori_idf_offline_20261022/) | [report.md](../results/tokenizer_nori_idf_offline_20261022/report.md) | [protocol.json](../results/tokenizer_nori_idf_offline_20261022/protocol.json) |

## 앞선 실험 기록

다음 문서는 기존 모델·검색·파싱 실험의 미채택 결과와 구현 판단을 보존합니다.
과거 특정 시점의 상태·권한·예산은 현재 실행 허가나 기본 설정을 뜻하지 않습니다.

- [C11 질문의 내수 세 분류 열거 삭제 비교](../../docs/evaluation/c11_question_categories_comparison.md)
- [C11 질문 분류 삭제: 조건별5회 추가 비교](../../docs/evaluation/c11_question_categories_extension.md)
- [고정 근거 생성 모델 비교: 새6문항 및 기존12문항 준비](../../docs/evaluation/generation_model_transfer_preparation.md)
- [고정 근거의 생성 모델 비교 결과](../../docs/evaluation/generation_model_transfer_result.md)
- [HD현대일렉트릭 XML 누락 수정과 새 18문항 실행 준비](../../docs/evaluation/hd_xml_quote_fix_and_new18_execution_preparation.md)
- [값 없는 표제 청크의 생성·검색 경로 진단](../../docs/evaluation/header_chunk_origin_audit.md)
- [공통 키워드 접두어 제거: BM25 검색 비교](../../docs/evaluation/keyword_prefix_bm25_ablation.md)
- [표제·기간 보존 Dense 실험: 안정성 검사에서 중단](../../docs/evaluation/linked_title_dense_ablation.md)
- [원문 표제·기간의 BM25 검색 입력 보존 실험](../../docs/evaluation/linked_title_search_ablation.md)
- [표제·기간 보존 실험의 ‘까지’ 토큰 대조](../../docs/evaluation/linked_title_until_control.md)
- [새 18문항 Dense와 RRF 검색 근거 비교](../../docs/evaluation/new18_dense_rrf_evidence_comparison.md)
- [새 18문항: Qwen3-Reranker-0.6B와 현재 RRF 비교](../../docs/evaluation/new18_reranker_evidence_comparison.md)
- [새 18문항 경량 Reranker 비교 실행 준비](../../docs/evaluation/new18_reranker_execution_preparation.md)
- [공통 키워드 줄 제거 reranker 대조](../../docs/evaluation/new18_reranker_keyword_ablation.md)
- [U08·U09·U14 reranker 회귀 원인 진단](../../docs/evaluation/new18_reranker_regression_diagnosis.md)
- [저장된 RRF 최종 문맥 8·12·16개 비교](../../docs/evaluation/new18_rrf_context_window_comparison.md)
- [저장 문맥 8개와 12개의 답변 비교 실행 준비](../../docs/evaluation/new18_rrf_window_answer_preparation.md)
- [저장된 RRF 문맥 8개·12개 답변 비교 결과](../../docs/evaluation/new18_rrf_window_answer_result.md)
- [새 18문항 CC DBSF RRF 검색 근거 비교](../../docs/evaluation/new18_score_fusion_evidence_comparison.md)
- [다음 표의 표제와 기간을 보존하는 최소 수정](../../docs/evaluation/new18_table_prefix_preservation_fix.md)
- [U03와 U16 답변 회귀의 원문 및 청킹 진단](../../docs/evaluation/new18_u03_u16_regression_diagnosis.md)
- [v9 국가·소재지 BM25 선택 정책 비교](../../docs/evaluation/new18_v9_country_lexical_policy.md)
- [v9 기존 검색과 BM25 보완 정책의 문맥 12개 답변 비교 준비](../../docs/evaluation/new18_v9_country_policy_answer_preparation.md)
- [v9 기존 검색과 BM25 국가·소재지 보완 정책의 답변 비교 결과](../../docs/evaluation/new18_v9_country_policy_answer_result.md)
- [v9 저장 RRF의 최종 문맥 8개·12개 비교](../../docs/evaluation/new18_v9_rrf_context_window_comparison.md)
- [v9 저장 문맥 8개와 12개의 답변 비교 실행 준비](../../docs/evaluation/new18_v9_rrf_window_answer_preparation.md)
- [v9 저장 문맥 8개·12개 답변 비교 결과](../../docs/evaluation/new18_v9_rrf_window_answer_result.md)
- [v9 별도 평가 store와 새 18문항 실행 준비](../../docs/evaluation/new18_v9_store_execution_preparation.md)
- [v9 별도 store의 새 18문항 답변 평가](../../docs/evaluation/new18_v9_store_execution_result.md)
- [U08 법인 국가 근거의 검색 후보 누락 원인](../../docs/evaluation/new18_v9_u08_candidate_diagnosis.md)
- [U08 국가 연결과 문맥 확대 원인 분석](../../docs/evaluation/new18_v9_u08_country_link_diagnosis.md)
- [새 18문항 RRF 가중치 비교](../../docs/evaluation/new18_weighted_rrf_evidence_comparison.md)
- [새 보고서의 실사용 상황 질문 평가 세트](../../docs/evaluation/new_report_user_eval_preparation.md)
- [새 보고서 18문항 반복 평가 결과](../../docs/evaluation/new_report_user_eval_result.md)
- [표제·기간 보존 검색 결과의 답변 비교](../../docs/evaluation/paired_title_answer_comparison.md)
- [원래 입력·표제/기간 보존 입력의 Fresh Dense 2회 비교](../../docs/evaluation/paired_title_dense_comparison.md)
- [질문 분해 검색의 근거 충족과 답변 성능 실험 설계](../../docs/evaluation/query_decomposition_experiment_design_2026-10-20.md)
- [질문 분해 실험 실행 중단과 원인 검증](../../docs/evaluation/query_decomposition_experiment_result_2026-10-20.md)
- [질문 분해 재실험 결과와 근거 선택 병목](../../docs/evaluation/query_decomposition_experiment_v2_result_2026-10-20.md)
- [DART RAG 평가 종합: 실패 원인, 답변 개선과 유지할 구현](../../docs/evaluation/rag_failure_and_decision_synthesis.md)
- [RAG 개선 작업 종료와 유지 기준선](../../docs/evaluation/rag_improvement_closeout_2026-10-17.md)
- [새 보고서의 근거 전달·독해 진단 준비](../../docs/evaluation/reader_evidence_diagnostic_preparation.md)
- [새 보고서의 근거 전달·독해 진단 결과](../../docs/evaluation/reader_evidence_diagnostic_result.md)
- [동일 근거에서 답변 생성 지시를 바꾼 소규모 실험](../../docs/evaluation/reader_prompt_fixed_evidence_result_2026-10-20.md)
- [동일 근거에서 선택 기록을 출력하는 실험 — 재시도 후 완료 결과](../../docs/evaluation/reader_selection_records_completed_result_2026-10-20.md)
- [동일 근거에서 선택 기록을 출력하는 실험 — 중단된 패널의 부분 결과](../../docs/evaluation/reader_selection_records_result_2026-10-20.md)
- [원래 프롬프트에서 low·medium reasoning effort 2회 비교](../../docs/evaluation/reasoning_effort_comparison.md)
- [원래 프롬프트에서 low·high reasoning effort 2회 비교](../../docs/evaluation/reasoning_high_comparison.md)
- [분류·관계 추가 금지 프롬프트의 2회 비교](../../docs/evaluation/relation_prompt_comparison.md)
- [넓은 표의 축과 헤더 없는 값 표 보존 수정](../../docs/evaluation/table_axis_and_headerless_fix.md)
- [선택된 청크의 행·열·값·단위 연결 비교 준비](../../docs/evaluation/table_cell_links_comparison_preparation.md)
- [선택 청크의 행·열·값·단위 연결 A/B 실행 결과](../../docs/evaluation/table_cell_links_comparison_result.md)
- [현재 표 처리의 정확성과 남은 결함](../../docs/evaluation/table_handling_current_audit.md)
- [기간 중복 판정과 행별 단위 보존 수정](../../docs/evaluation/table_period_and_row_unit_fix.md)
- [같은 검색 후보에서 top-8 / top-12 실제 답변 비교](../../docs/evaluation/top8_top12_answer_ab_result_2026-10-20.md)
- [기존 보고서 2개 실사용 질문 5개 — 실행 전 준비](../../docs/evaluation/use5_fixed_app_preparation_2026-10-17.md)
- [기존 보고서 2개 실사용 질문 5개 — 실행 결과](../../docs/evaluation/use5_fixed_app_result_2026-10-17.md)
- [XML 복구 오류 탐지와 색인 차단](../../docs/evaluation/xml_recovery_guard.md)
- [Schema-bound XML literal recovery](../../docs/evaluation/xml_schema_recovery.md)
- [차단 원문 4개 원인 진단과 문자 경계 복구](../../docs/evaluation/xml_structure_recovery.md)
