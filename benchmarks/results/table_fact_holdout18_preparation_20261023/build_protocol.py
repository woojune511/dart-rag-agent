"""Freeze controls and a conservative budget; does not dispatch paid requests."""
from common import *
from decimal import Decimal as D, ROUND_CEILING
def main():
    old=read(ROOT/'benchmarks/results/table_fact_answer_full77_20261023/protocol.json')
    perf=read(ROOT/'benchmarks/results/table_fact_answer_full77_20261023/generation_performance.json')
    plan=read(BASE/'embedding_plan.json');projection=read(BASE/'projection.json')
    from src.config.simple_rag import ANSWER_INSTRUCTIONS,RagAnswer
    fixed=old['fixed_generation']
    assert fixed['input'][0]['content']==ANSWER_INSTRUCTIONS
    assert fixed['text']['format']['schema']==RagAnswer.model_json_schema()
    assert fixed['model']=='gpt-6.1-sol' and fixed['reasoning']=={'effort':'low'}
    # Conservative per-request transport-byte reservation caps, never a target length.
    max_reservations={'A':98304,'C':229376}
    generation_max=sum(D(t)*D('2.5')/1000000+D(8192)*D(10)/1000000 for t in max_reservations.values())*36
    # 32-token reserve per embedding input is an admission margin, not a different embedding string.
    embed_tokens=plan['unique_tokens']+32*plan['unique_inputs']
    doc_max=D(embed_tokens)*D('0.13')/1000000
    query_max=D(18*1024)*D('0.13')/1000000
    saturated=generation_max+doc_max+query_max
    historical=(D(perf['A']['cost_usd'])+D(perf['C']['cost_usd']))*D(18)/D(77)
    no_reuse=sum(D(perf[arm]['input_tokens'])*D('2.5')/1000000+D(perf[arm]['output_tokens'])*D(10)/1000000 for arm in ('A','C'))*D(18)/D(77)
    prices={'checked_at':now(),'sources':['https://developers.openai.com/api/docs/pricing',
       'https://developers.openai.com/api/docs/guides/prompt-caching#summary-of-model-differences'],
       'transport':'OpenAI public standard endpoint; no regional/FedRAMP/Fast/Batch service.',
       'rates_usd_per_million':{'input':'2','output':'10','cached_input':'0.10','cache_write_30m':'2.50','embedding_3_large':'0.13'},
       'short_context_limit_input_tokens':272000,'cache':'Default 30m; no new cache parameters. Reserve at full cache-write price; no discount assumed for cap.',
       'measured_embedding_tokens':plan['unique_tokens'],'embedding_actual_input_estimate_usd':str(D(plan['unique_tokens'])*D('0.13')/1000000),
       'document_embedding_reservation_usd':str(doc_max),'query_embedding_reservation_usd':str(query_max),
       'answer_max_reserved_usd':str(generation_max),'saturated_total_reservation_usd':str(saturated),
       'http_attempts':{'document_embedding':plan['http_attempts'],'query_embedding':18,'answer_generation':72,'total':plan['http_attempts']+90},
       'expected_usd_range':[3,6],'expected_is_not_guaranteed':True,
       'estimate_method':{'basis':'Prior full77 mean input/output and realized cache billing, scaled to 18; new report table sizes and answer lengths unknown before retrieval.',
          'historical_answer_cost_scaled':str(historical),'all_cache_write_answer_estimate_scaled':str(no_reuse),
          'add_fresh_embedding_usd':str(D(plan['unique_tokens'])*D('0.13')/1000000)},
       'cap_usd':'36.00','max_per_answer_input_reservation_tokens':max_reservations,
       'reservation_rule':'Before dispatch: len(canonical UTF-8 serialized request body)+4096 <= arm cap and <=272000; reserve actual bound at2.5/M plus8192 output at10/M. Embedding billed tokens <= local cl100k count+32/input. Never modify a packet to force these gates; stop instead. Missing/unexpected usage stops and retains reserved liability.'}
    assert saturated<D('36.00')
    write(BASE/'pricing.json',prices)
    protocol={'status':'PREPARED_NOT_EXECUTED','at':now(),'scope':'new-report holdout18; source-authored usage scenarios, not logged user queries',
      'question_count':18,'report_count':3,'repetitions_per_arm':2,'arms':{
       'A':{'label':'original_delivery_64KiB','max_packet_bytes':65536},
       'C':{'label':'same_delivered_documents_plus_verified_table_units_160KiB','max_packet_bytes':163840}},
      'estimand':'Combined effect of table-fact representation plus available context bytes. Does not identify separate format and budget effects.',
      'fixed_generation':fixed,
      'retrieval':{'corpus':'Only the 3 new reports, all 3768 original v12 chunks, shared by both arms. BM25 global statistics computed on that same corpus.',
         'manifest':projection['manifest'],'dense_candidates':16,'bm25_candidates_max':24,'bm25':'unchanged tokenize_ko character bigrams + ASCII words; BM25Okapi default k1=1.5,b=0.75,epsilon=0.25',
         'rrf_constant':60,'rrf_weights':[1,1],'final_selected':12,
         'selection':'Call VectorStoreManager.search with k=8 once per question to retain historical Dense16/BM25<=24. In experiment-only observer capture the full two lists, call unchanged merge_rrf_results(...,k=12,k_rrf=60) on that saved union; the search return top8 is not the final experimental selection. Do not call search(k=12), which widens candidates.',
         'ties':'Keep original corpus/document order, descending stable BM25 score, Dense returned order, then Dense insertion before BM25 in unchanged RRF merge.',
         'report_scope':'Explicit caller receipt filter, exactly one selected report per question; do not infer year scope from query.',
         'query':'Original frozen question in both Dense and BM25. No reformulation, decomposition, expansion, Nori, schema field retrieval, reranker, title-only augmentation, experimental country policy or caption links.',
         'parameters':{'allow_query_embedding_fallback':False,'force_bm25_only':False,'experimental_lexical_policy_id':None,'experimental_caption_links_path':None},
         'query_embedding_calls':18,'share':'Compute retrieval once; freeze all candidates/scores/order/top12 and reuse for all four answers per question. Repeat generation only.',
         'historical_comparability':'New corpus necessarily changes corpus statistics; algorithm is frozen across A/C, not a claim of historical IDF or numeric score equality.'},
      'delivery':{'A':'Current SimpleRagAgent packet construction with k12 hit list and65536 canonical UTF-8 bytes; whole-source omission, preserve query/scope/source IDs/text/context/order.',
         'C':'Start from exact A packet. Append only current frozen source-verified table_fact_units to its actual delivered sources;163840 canonical UTF-8 bytes; first physical-table owner, source-order atomic unit dependencies, no query-aware prioritization.',
         'no_refill':'Never add any of the top12 documents omitted by A; no parent/neighbor/oracle retrieval.',
         'projector':'benchmarks/results/table_fact_units_offline_20261023/projector.py',
         'assembler':'benchmarks/results/table_fact_units_offline_20261023/run.py:project_packet with CAP=163840',
         'projector_dependency':'benchmarks/results/table_bundle_delivery_offline_20261022/projector.py',
         'source_boundary':'Use original XML as physical witness for stored metadata only; no new values recovered solely from raw XML. Physical provenance checks do not certify semantic period/entity/unit interpretation.'},
      'schedule':'For H01,H03,... rep1 A then C; H02,H04,... rep1 C then A; reverse each question order in rep2; sequential concurrency1. Same exact body in both repetitions for each arm.',
      'metrics':{'primary':'15 answerable questions x2 repetitions =30 per arm. Complete-and-supported iff accuracy, required-item completeness and citation faithfulness all PASS.',
        'secondary':['accuracy30','required-item completeness30 and named fact omissions','citation faithfulness30','refusal success3x2=6 separate','all18 per-question two-repeat consistency','actual delivered evidence coverage; input/output/reasoning tokens; cost; latency'],
        'refusal':'Require scoped insufficiency and identify missing operand/relation; do not claim whole-report absence from retrieved absence; no invented requested result; abstained=true.',
        'support':'All material factual claims must be supported by actual cited model-visible evidence, not just by gold or a matching source ID. Verify all extra claims as well as required facts.',
        'arithmetic':'Compute reference with Decimal; same period/entity/scope/unit operands; honor requested output precision. Correct refusal of an answerable question is still incomplete.',
        'diagnosis':['raw/parsing loss','candidate loss','RRF top12 loss','A packet omission','table-unit validation/budget omission','delivered-evidence reading/citation error'],
        'review':'Freeze questions/gold before retrieval. Seal all72 raw outputs then mask arm/repetition for fresh-context source review. Packet shape may reveal condition; no fully blind, independent-human or cross-family validation claim.',
        'new_gold_issue':'Retain frozen primary scores; report independently source-adjudicated sensitivity separately. Do not rewrite gold after seeing which arm wins.',
        'statistics':'Report paired counts and percentage-point differences by question, repeat and report. 72 answers are not72 independent questions; only3 report clusters. No general-population accuracy or significance claim.',
        'decision':'Exploratory transfer support only if both repeats have positive answerable complete-and-supported difference, at least2/3 reports are nonnegative, and no adjudicated new material factual/citation/refusal regression. Otherwise mixed/inconclusive; preserve outputs, no automatic tuning or rollout. This is a prespecified practical screen, not a statistical significance test.'},
      'budget':{'max_total_http_attempts':plan['http_attempts']+90,'document_embedding_attempts':plan['http_attempts'],'query_embedding_attempts':18,'answer_attempts':72,'max_usd':'36.00','max_wall_seconds':9000,'retries':0,'concurrency':1,'heartbeat_seconds':20},
      'stop_policy':'Stop before any request exceeding call/cost/time reservation. First transport/provider/model identity/dimension/usage/integrity error stops; no retry/fallback/resume without user authorization. Malformed, incomplete or invalid-citation answers remain scored failures, not regenerated.',
      'execution_store':str(BASE/'execution/store'),'execution_collection':'holdout18_v12_20261023',
      'execution_gate':'This is preparation only. No paid/live runner has been dispatched. On authorization implement a bounded runner under execution/ using these frozen inputs; provider-free guard tests and exact request/preservation checks must pass before any provider request. Runtime source remains unchanged.',
      'preservation':'Write only this ignored preparation folder now and its new execution/ subtree after authorization. Never open active v12 Chroma/SQLite, edit env/runtime, restart app, stage or commit artifacts.'}
    write(BASE/'protocol.json',protocol)
    print(json.dumps({'attempts':prices['http_attempts'],'expected_usd':prices['expected_usd_range'],'max_usd':prices['cap_usd'],'saturated_reservation_usd':prices['saturated_total_reservation_usd']},ensure_ascii=False))
if __name__=='__main__':
    with offline():main()
