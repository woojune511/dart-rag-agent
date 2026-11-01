"""Count exact fresh v12 embedding inputs with networking blocked; no store build."""
from common import *
import os, gzip, threading, time, math
def main():
    started=time.monotonic();state={'phase':'import'};stop=threading.Event()
    def heartbeat():
        while not stop.wait(20):
            entry={**state,'seconds':round(time.monotonic()-started,1)}
            with (BASE/'projection_heartbeat.jsonl').open('a',encoding='utf8') as f:f.write(json.dumps(entry)+'\n')
            print(json.dumps(entry),flush=True)
    thread=threading.Thread(target=heartbeat,daemon=True);thread.start()
    try:
        cache=ROOT/'benchmarks/results/kbf_parser_embedding_admission_2026-09-09/tokenizer_cache'
        os.environ['TIKTOKEN_CACHE_DIR']=str(cache)
        import tiktoken
        from src.ops.plan_parser_store_successor import parse_source_projection
        from src.storage.store_manifest import canonical_store_manifest
        encoding=tiktoken.encoding_for_model('text-embedding-3-large')
        manifest=canonical_store_manifest(collection_name='holdout18_v12_20261023',embedding_dimension=3072)
        assert manifest.ingest.parser_schema_version=='financial_parser_v12_schema_literal_labels'
        assert not (BASE/'corpus.jsonl.gz').exists()
        sources=read(BASE/'acquisition.json')['reports']
        inputs=[{'source_file':r['source_file'],'metadata':{'company':r['corp_name'],'corp_code':r['corp_code'],'stock_code':r['stock_code'],'rcept_no':r['rcept_no'],'year':2025,'report_type':'사업보고서'}} for r in sources]
        state['phase']='parse_frozen_v12'
        chunks,texts,parents,reports=parse_source_projection(inputs,manifest,section_parse_budget_sec=0)
        assert not [s for r in reports for s in r['section_modes'] if s['fallback_used']], 'Parser fallback: do not repair automatically'
        state['phase']='serialize_and_count'
        seen={};batches=[];batch=[];batch_tokens=0;summary={}
        with gzip.open(BASE/'corpus.jsonl.gz','wt',encoding='utf8',compresslevel=3) as f:
            for chunk,text in zip(chunks,texts):
                uid=chunk.metadata['chunk_uid'];rid=chunk.metadata['rcept_no']
                tok=len(encoding.encode_ordinary(text));assert 0<tok<=8192,(uid,tok)
                h=hashlib.sha256(text.encode('utf8')).hexdigest()
                row={'uid':uid,'text':text,'raw_chunk_text':chunk.content,'metadata':chunk.metadata,'text_sha256':h,'embedding_tokens':tok}
                f.write(json.dumps(row,ensure_ascii=False,allow_nan=False,separators=(',',':'))+'\n')
                r=summary.setdefault(rid,{'chunks':0,'all_tokens':0,'max_input_tokens':0,'structured_table_chunks':0})
                r['chunks']+=1;r['all_tokens']+=tok;r['max_input_tokens']=max(r['max_input_tokens'],tok)
                r['structured_table_chunks']+=bool(chunk.metadata.get('table_object_json'))
                if h in seen:
                    assert seen[h]['text']==text
                    seen[h]['uids'].append(uid);continue
                seen[h]={'text':text,'uids':[uid],'tokens':tok}
                if batch and (len(batch)>=256 or batch_tokens+tok>250000):
                    batches.append({'index':len(batches),'text_sha256':batch,'tokens':batch_tokens});batch=[];batch_tokens=0
                batch.append(h);batch_tokens+=tok
            if batch:batches.append({'index':len(batches),'text_sha256':batch,'tokens':batch_tokens})
        write(BASE/'embedding_plan.json',{'model':'text-embedding-3-large','dimensions':3072,'encoding':'cl100k_base',
          'dedup':'Exact identical full v12 index text only; replicate vectors to original UIDs; no cross-report semantic dedup.',
          'total_chunks':len(chunks),'unique_inputs':len(seen),'unique_tokens':sum(x['tokens'] for x in seen.values()),
          'max_inputs_per_request':256,'max_tokens_per_request':250000,'max_single_input_tokens':8192,
          'http_attempts':len(batches),'retries':0,'batches':batches,
          'inputs':{h:{'uids':v['uids'],'tokens':v['tokens']} for h,v in seen.items()}})
        write(BASE/'projection.json',{'status':'OFFLINE_V12_PROJECTION_ONLY','manifest':manifest.to_projection(),
          'reports':reports,'counts':summary,'corpus_sha256':sha(BASE/'corpus.jsonl.gz'),'chunks':len(chunks),
          'embedding_batches':len(batches),'embedding_tokens':sum(x['tokens'] for x in seen.values()),
          'model_api_calls':0,'embedding_api_calls':0,'store_writes':0,'seconds':time.monotonic()-started})
        print(json.dumps({'counts':summary,'batches':len(batches),'unique_tokens':sum(x['tokens'] for x in seen.values()),'seconds':time.monotonic()-started},ensure_ascii=False),flush=True)
    finally:stop.set();thread.join(timeout=2)
if __name__=='__main__':
    with offline(): main()
