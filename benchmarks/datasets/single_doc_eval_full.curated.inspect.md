# Curated Dataset Inspection Guide

## Start Here
- 문서 대조용 review packet: `C:\Users\geonj\Desktop\research agent\benchmarks\datasets\single_doc_eval_full.curated.review.md`
- 필터링용 compact CSV: `C:\Users\geonj\Desktop\research agent\benchmarks\datasets\single_doc_eval_full.curated.inspect.csv`

## Reference Files
- Final nested dataset: `C:\Users\geonj\Desktop\research agent\benchmarks\datasets\single_doc_eval_full.curated.json`
- Review seed with full review metadata: `C:\Users\geonj\Desktop\research agent\benchmarks\datasets\single_doc_eval_full.grounded_draft.review\review_seed.json`
- Rewrite log: `C:\Users\geonj\Desktop\research agent\benchmarks\datasets\single_doc_eval_full.rewrite_log.json`

## Snapshot
- Total rows: 78
- Verified rows: 78
- Expected refusal rows: 19
- Rewritten question rows: 15

## Answer Type Counts
- numeric: 16
- refusal: 29
- summary: 33

## Suggested Review Flow
1. Review packet markdown에서 질문/답/근거/원문 링크를 함께 본다.
2. 원문 HTML을 열어 섹션과 인용문이 실제로 맞는지 대조한다.
3. 필요한 경우 compact CSV로 필터링해 회사별/거절문항별로 스캔한다.

## Compact CSV Columns
- `question`, `answer_key`: 최종 확정 질문/답변
- `source_report_paths`, `source_report_urls`: 원문 보고서 위치
- `expected_sections`, `evidence_quotes`: 문서 대조용 최소 근거
- `review_decision`, `rewrite_applied`: 검수 이력
