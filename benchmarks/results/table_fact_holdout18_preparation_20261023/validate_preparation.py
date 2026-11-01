"""Provider-free preflight. Verifies artifacts only; never opens a store client."""
from common import *
import gzip,re,os
from collections import Counter
from decimal import Decimal as D
def main():
    checks=[]
    def check(name,value,detail=None):
        assert value,name
        checks.append({'name':name,'status':'PASS','detail':detail})
    protocol=read(BASE/'protocol.json');price=read(BASE/'pricing.json');questions=read(BASE/'questions.json')
    rubric=read(BASE/'rubric.json');projection=read(BASE/'projection.json');plan=read(BASE/'embedding_plan.json')
    old=read(ROOT/'benchmarks/results/table_fact_answer_full77_20261023/protocol.json')
    check('fixed_generation_exact',protocol['fixed_generation']==old['fixed_generation'])
    check('18_unique_questions_3_reports',len(questions)==18 and len({q['case_id'] for q in questions})==18 and sorted(Counter(q['receipt'] for q in questions).values())==[6,6,6])
    from src.storage.report_scope_filter import report_scope_filter
    for q in questions:check('scope_'+q['case_id'],report_scope_filter(q['report_scope'])=={'rcept_no':q['receipt']})
    check('question_rubric_parity',[(q['case_id'],q['question'],q['report_scope']) for q in questions]==[(q['case_id'],q['question'],q['report_scope']) for q in rubric['cases']])
    check('15_answerable_3_refusal',len(rubric['primary_answerable_ids'])==15 and len(rubric['refusal_ids'])==3)
    schedule=read(BASE/'schedule.json')
    check('72_balanced_scheduled_answers',len(schedule)==72 and Counter((r['case_id'],r['arm']) for r in schedule)==Counter({(q['case_id'],a):2 for q in questions for a in ('A','C')}))
    for q in questions:
        orders=[[r['arm'] for r in schedule if r['case_id']==q['case_id'] and r['repeat']==rep] for rep in (1,2)]
        check('reversed_pair_order_'+q['case_id'],orders[0]==orders[1][::-1] and set(orders[0])=={'A','C'})
    exposure=read(BASE/'exposure_audit.json')
    check('no_recorded_receipt_source_overlap',exposure['status']=='NO_RECORDED_RECEIPT_OR_SOURCE_OVERLAP' and not exposure['receipt_matches'] and not exposure['prior_source_sha_duplicates'])
    norm=lambda x:re.sub(r'\s+','',x)
    prior={norm(s) for s in read(BASE/'prior_questions.json')}
    check('no_exact_previous_questions',not [q['case_id'] for q in questions if norm(q['question']) in prior],{'prior_unique_questions':len(prior)})
    check('raw_witness_and_calculation_checks',read(BASE/'source_witness_validation.json')['status']=='PASS' and read(BASE/'source_witness_validation.json')['witness_count']==134 and read(BASE/'calculation_validation.json')['status']=='PASS')
    reviews=[read(BASE/n) for n in ('review_amore.json','review_kia_sds.json')]
    flagged={c['case_id'] for r in reviews for c in r.get('case_findings',r.get('cases',[])) if c['status']=='REVISION_NEEDED'}
    adjudication=read(BASE/'gold_adjudication.json')
    check('all_gold_review_findings_resolved_before_answers',flagged=={c['case_id'] for c in adjudication['changes']}=={'H10','H11','H17','H18'})
    for c in adjudication['changes']:
        fact=next(f for q in rubric['cases'] if q['case_id']==c['case_id'] for f in q['required_facts'] if f['id']==c['fact_id'])
        check('adjudication_applied_'+c['case_id'],all(fact[k]==v for k,v in c['after'].items()))
    reviewed=read(BASE/'review_protocol.json')
    check('protocol_review_pass_current_hashes',reviewed['status']=='PASS' and all(sha(BASE/n)==h for n,h in reviewed['inputs'].items()))
    acquisition=read(BASE/'acquisition.json')
    check('DART_only_7_requests',len(acquisition['requests'])==7 and set(r['endpoint'] for r in acquisition['requests'])=={'corpCode.xml','list.json','document.xml'} and acquisition['model_api_calls']==acquisition['embedding_api_calls']==0)
    for r in acquisition['reports']:check('raw_source_hash_'+r['rcept_no'],sha(r['source_file'])==r['xml_sha256'])
    check('corpus_hash',sha(BASE/'corpus.jsonl.gz')==projection['corpus_sha256'])
    unique={};uids=set();per_report=Counter()
    with gzip.open(BASE/'corpus.jsonl.gz','rt',encoding='utf8') as f:
        for line in f:
            row=json.loads(line);uid=row['uid'];assert uid not in uids;uids.add(uid)
            assert row['metadata']['chunk_uid']==uid
            h=hashlib.sha256(row['text'].encode('utf8')).hexdigest();assert h==row['text_sha256']
            assert 0<row['embedding_tokens']<=8192
            entry=unique.setdefault(h,{'uids':[],'tokens':row['embedding_tokens']});assert entry['tokens']==row['embedding_tokens'];entry['uids'].append(uid)
            per_report[row['metadata']['rcept_no']]+=1
    check('exact_embedding_input_map',unique==plan['inputs'])
    check('all3768_uids_preserved_despite_embedding_dedup',len(uids)==3768 and len(unique)==3734,dict(per_report))
    check('batch_partition_once',Counter(h for b in plan['batches'] for h in b['text_sha256'])==Counter({h:1 for h in unique}))
    check('batch_limits_and_tokens',all(len(b['text_sha256'])<=256 and b['tokens']==sum(unique[h]['tokens'] for h in b['text_sha256'])<=250000 for b in plan['batches']))
    os.environ['TIKTOKEN_CACHE_DIR']=str(ROOT/'benchmarks/results/kbf_parser_embedding_admission_2026-09-09/tokenizer_cache')
    import tiktoken
    encoding=tiktoken.encoding_for_model('text-embedding-3-large')
    query_tokens=[len(encoding.encode_ordinary(q['question'])) for q in questions]
    check('query_embedding_reservation_sufficient',all(t+32<=1024 for t in query_tokens),{'tokens':sum(query_tokens),'max':max(query_tokens)})
    check('105_complete_request_cap',len(plan['batches'])==15 and protocol['budget']['max_total_http_attempts']==15+18+72==105)
    computed=D(price['answer_max_reserved_usd'])+D(price['document_embedding_reservation_usd'])+D(price['query_embedding_reservation_usd'])
    check('36USD_reservation_bound',computed==D(price['saturated_total_reservation_usd'])<D(price['cap_usd'])==D('36.00'),str(computed))
    check('no_experiment_executed_or_store_built',not (BASE/'execution').exists() and projection['model_api_calls']==projection['embedding_api_calls']==projection['store_writes']==0)
    before=read(BASE/'before.json');changes=[p for p,h in before['files'].items() if not (ROOT/p).is_file() or sha(ROOT/p)!=h]
    check('protected_existing_file_hashes',not changes,{'files':len(before['files']),'changed':changes})
    check('git_head_index_status_preserved',git('rev-parse','HEAD').decode().strip()==before['head'] and sha(ROOT/'.git/index')==before['index_sha256'] and git('status','--porcelain=v1','-z','--untracked-files=all')==(BASE/'git_status_before.bin').read_bytes())
    if (BASE/'freeze.json').exists():
        freeze=read(BASE/'freeze.json')
        check('frozen_preparation_hashes',all(sha(BASE/p)==h for p,h in freeze['files'].items()))
        check('frozen_algorithm_hashes',all(sha(ROOT/p)==h for p,h in freeze['dependencies'].items()))
    result={'status':'PASS','at':now(),'checks':checks,'model_api_calls':0,'embedding_api_calls':0,
       'DART_free_requests_previously_completed':7,'execution_status':'NOT_RUN','source_overlap_files':exposure['files_scanned'],
       'queries_exact_tokens':sum(query_tokens),'protected_files':len(before['files']),'active_v12_store_files':len(before['active_store_files']),
       'env_unchanged':True,'active_store_bytes_unchanged':True,'git_unchanged':True,
       'review_limit':'Physical witnesses, arithmetic and source-author cross-review passed. No retrieval, answer accuracy or future live-runner correctness measured.'}
    write(BASE/('validation_latest.json' if (BASE/'freeze.json').exists() else 'validation.json'),result)
    print(json.dumps({k:v for k,v in result.items() if k!='checks'},ensure_ascii=False))
if __name__=='__main__':
    with offline():main()
