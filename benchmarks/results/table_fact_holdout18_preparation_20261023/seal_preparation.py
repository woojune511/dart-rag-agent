"""Seal the prepared local plan and criteria before any retrieval or generation."""
from common import *
def main():
    assert not (BASE/'freeze.json').exists()
    assert read(BASE/'validation.json')['status']=='PASS'
    assert not (BASE/'execution').exists()
    (BASE/'passport.md').write_text('# Material Passport\n\n- Origin Skill: academic-research-suite / experiment-agent\n- Origin Mode: plan\n- Origin Date: 2026-10-23\n- Version Label: holdout18-v1\n- Verification Status: PREPARED_NOT_EXECUTED\n- Source reports: Kia / Samsung SDS / Amorepacific, annual2025; 18 authored usage-scenario questions\n- Verified: 134 source witnesses, 3 arithmetic references, source-author cross-review and question-compatible rubric, fixed A64/C160 protocol, input/cost plan, local exposure audit\n- External experiment model/embedding/judge calls: 0; authorized free DART source requests:7\n- Future planned cap:105 HTTP attempts / USD36 / 9000seconds, no retries; not yet authorized or dispatched\n- Model selection for future experiment: gpt-6.1-sol / low\n- Author/review workers requested:gpt-6-astra / xhigh; actual provider identity unattested; not independent human gold\n- Preserved:870 existing protected files, .env,11 active v12 store files,Git HEAD/index/status; no app restart\n- Human-readable deliverable:plan.md\n- Limits:3 purpose-selected reports; bounded prior-record audit; combined representation and budget intervention; no new answers or retrieval scores\n',encoding='utf8')
    names=['common.py','bootstrap.py','acquire.py','catalog_sources.py','prepare_projection.py','audit_exposure.py','build_protocol.py','assemble_and_check.py','validate_preparation.py','write_plan.py','seal_preparation.py',
      'selection_lock.json','acquisition.json','catalog_receipt.json','before.json','git_status_before.bin','corpus.jsonl.gz','projection.json','embedding_plan.json',
      'questions.json','rubric.json','protocol.json','pricing.json','schedule.json','source_witness_validation.json','calculation_validation.json',
      'exposure_audit.json','prior_questions.json','gold_adjudication.json','review_protocol.json','review_amore.json','review_kia_sds.json',
      'kia_questions.json','sds_questions.json','amore_questions.json','kia_notes.md','preparation_incidents.json','validation.json','passport.md','plan.md']
    names += [str(p.relative_to(BASE)) for p in (BASE/'sources').rglob('*') if p.is_file()]
    deps=['src/config/simple_rag.py','src/config/runtime_contract.py','src/config/retrieval_policy.py',
      'src/processing/financial_parser.py','src/processing/chunking.py','src/processing/table_records.py','src/processing/block_collection.py',
      'src/storage/vector_store.py','src/storage/bm25_index.py','src/storage/search_merge.py','src/storage/report_scope_filter.py','src/storage/lexical_query.py','src/storage/store_manifest.py','src/agent/simple_rag.py',
      'src/ops/plan_parser_store_successor.py','src/ops/benchmark_runner.py',
      'benchmarks/results/table_fact_units_offline_20261023/projector.py','benchmarks/results/table_fact_units_offline_20261023/run.py',
      'benchmarks/results/table_bundle_delivery_offline_20261022/projector.py','benchmarks/results/table_fact_answer_full77_20261023/protocol.json',
      'benchmarks/results/table_fact_answer_full77_20261023/generation_performance.json']
    write(BASE/'freeze.json',{'at':now(),'status':'FROZEN_BEFORE_RETRIEVAL_AND_GENERATION','files':{n:sha(BASE/n) for n in sorted(set(names))},
      'dependencies':{n:sha(ROOT/n) for n in deps},'paid_execution_authorized':False,'model_api_calls':0,'embedding_api_calls':0,
      'allowed_future_change':'After explicit execution authorization write new execution subtree only. Frozen questions/gold/algorithm/conditions remain unchanged; halt on hash drift.'})
    print(json.dumps({'frozen_files':len(set(names)),'algorithm_dependencies':len(deps),'paid_execution_authorized':False}))
if __name__=='__main__':main()
