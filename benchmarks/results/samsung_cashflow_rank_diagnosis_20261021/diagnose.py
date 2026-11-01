"""One-question, frozen retrieval-only diagnostic; never changes runtime or stores."""
from pathlib import Path
import sys, os, json, gzip, hashlib, time, threading, re
from decimal import Decimal
from collections import Counter

BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[2]
OLD = ROOT / 'benchmarks/results/dart_representation_pilot10_20261021'
sys.path.insert(0, str(OLD))
from common import load, write, sha, now, offline
import run as original
os.environ['TIKTOKEN_CACHE_DIR'] = str(ROOT/'benchmarks/results/full77_v12_final_20261018/tokenizer_cache')
RID = '20260310003071'
TID = RID + ':106:5'
GID = RID + ':generic:24'
CAP = Decimal('.50')
RATE = Decimal('.13') / 1000000

def rows(path):
    with gzip.open(path, 'rt', encoding='utf-8') as f:
        return [json.loads(line) for line in f]

def save_rows(path, data):
    with gzip.open(path, 'xt', encoding='utf-8', newline='\n') as f:
        for row in data:
            f.write(json.dumps(row, ensure_ascii=False, allow_nan=False)+'\n')

def text_hash(value):
    return hashlib.sha256(value.encode('utf-8')).hexdigest()

def event(stage, **kwargs):
    row = {'at':now(), 'stage':stage, **kwargs}
    with (BASE/'heartbeat.jsonl').open('a', encoding='utf-8', newline='\n') as f:
        f.write(json.dumps(row, ensure_ascii=False)+'\n')
    print(json.dumps(row, ensure_ascii=False), flush=True)

def verify():
    original.verify()
    for path, digest in load(BASE/'freeze.json')['files'].items():
        assert sha(path) == digest, 'Frozen dependency changed: '+path

def retrieve(data, vectors, query, qvector, target):
    import numpy as np
    from rank_bm25 import BM25Okapi
    from src.storage.bm25_index import tokenize_ko
    distances = np.sum((vectors-qvector)**2, axis=1)
    dense_all = sorted(range(len(data)), key=lambda i:(float(distances[i]), i))
    corpus_tokens = [tokenize_ko(x['text']) for x in data]
    bm = BM25Okapi(corpus_tokens)
    query_tokens = tokenize_ko(query)
    scores = bm.get_scores(query_tokens)
    lexical_all = sorted(range(len(data)), key=lambda i:(-float(scores[i]),i))
    dense = dense_all[:24]
    lexical = [i for i in lexical_all[:24] if scores[i]>0]
    rrf = {}
    for order in (dense,lexical):
        for rank,i in enumerate(order,1):
            rrf[i] = rrf.get(i,0)+1/(60+rank)
    fused = sorted(rrf, key=lambda i:rrf[i], reverse=True)
    di = {i:r for r,i in enumerate(dense_all,1)}
    bi = {i:r for r,i in enumerate(lexical_all,1)}
    ri = {i:r for r,i in enumerate(fused,1)}
    def record(i):
        return {'id':data[i]['id'], 'dense_rank':di[i], 'dense_distance':float(distances[i]),
                'bm25_rank':bi[i], 'bm25_score':float(scores[i]), 'rrf_rank':ri.get(i),
                'rrf_score':rrf.get(i,0), 'in_top12':ri.get(i,100000)<=12,
                'dense_contribution':1/(60+di[i]) if di[i]<=24 else 0,
                'bm25_contribution':1/(60+bi[i]) if i in lexical else 0,
                'bm25_length':len(corpus_tokens[i])}
    ti = next(i for i,x in enumerate(data) if x['id']==target)
    terms = []
    for token, count in Counter(query_tokens).items():
        freq = bm.doc_freqs[ti].get(token,0)
        idf = bm.idf.get(token,0)
        score = count*idf*(freq*(bm.k1+1)/(freq+bm.k1*(1-bm.b+bm.b*bm.doc_len[ti]/bm.avgdl)))
        terms.append({'token':token,'query_count':count,'target_tf':freq,'idf':idf,'contribution':score,
                      'df':sum(token in d for d in bm.doc_freqs)})
    assert abs(sum(x['contribution'] for x in terms)-float(scores[ti])) < 1e-8
    return {'target':record(ti), 'chunks':len(data), 'dense_top24':[record(i) for i in dense],
            'bm25_top24':[record(i) for i in lexical], 'rrf_candidates':[record(i) for i in fused],
            'bm25_avg_length':bm.avgdl, 'target_query_token_contributions':terms}

def prepare():
    import numpy as np, tiktoken
    from src.processing.financial_parser import FinancialParser, _extract_standalone_table_context_hint
    from src.ops.benchmark_runner import _build_structural_selective_prefixed_text, _selective_reason_v2
    from src.storage.bm25_index import tokenize_ko
    from lxml import etree
    original.verify()
    assert not (BASE/'freeze.json').exists()
    encoder=tiktoken.get_encoding('cl100k_base')
    question=next(x for x in load(OLD/'question_seed.json') if x['id']=='02_capex')
    qi=next(i for i,x in enumerate(load(OLD/'question_seed.json')) if x['id']=='02_capex')
    qvector=np.array(load(OLD/'live/queries/embedding.raw.json')['data'][qi]['embedding'],dtype=np.float32)
    generic=rows(OLD/f'generic_{RID}.jsonl.gz')
    dart=rows(OLD/f'dart_{RID}.jsonl.gz')
    gv=np.load(OLD/f'generic_{RID}.npy'); dv=np.load(OLD/f'dart_{RID}.npy')
    baseline={arm:retrieve(ds,vs,question['query'],qvector,target) for arm,ds,vs,target in
              [('generic',generic,gv,GID),('dart',dart,dv,TID)]}
    for arm in baseline:
        saved=next(x for x in load(OLD/'retrieval.json') if x['id']=='02_capex' and x['arm']==arm)
        current=baseline[arm]
        assert [x['id'] for x in current['dense_top24']]==[x['id'] for x in saved['dense']]
        assert [x['id'] for x in current['bm25_top24']]==[x['id'] for x in saved['bm25']]
        assert [x['id'] for x in current['rrf_candidates'][:12]]==[x['id'] for x in saved['rrf_top12']]
        assert all(abs(x['rrf_score']-y['score'])<1e-12 for x,y in zip(current['rrf_candidates'][:12],saved['rrf_top12']))
    assert tuple(baseline['dart']['target'][k] for k in ('dense_rank','bm25_rank','rrf_rank'))==(263,11,22)
    assert tuple(baseline['generic']['target'][k] for k in ('dense_rank','bm25_rank','rrf_rank'))==(9,20,4)
    write(BASE/'baseline.json',baseline)
    source=OLD/'sources'/RID/'original.xml'
    report=next(x for x in load(OLD/'acquisition.json')['reports'] if x['rcept_no']==RID)
    meta={k:report[k] for k in ('company','year','rcept_no')};meta['report_type']='사업보고서'
    parser=FinancialParser(chunk_size=2500,chunk_overlap=320,section_parse_budget_sec=0)
    chunks=parser.process_document(str(source),meta)
    assert len(chunks)==len(dart)==1103
    variants={name:[] for name in ('no_keywords','keywords_only','body_only')}
    bodies={};prefixes={};keyword_lines={}
    for chunk,saved in zip(chunks,dart):
        rendered=_build_structural_selective_prefixed_text(chunk.metadata,chunk.content,selected_reason=_selective_reason_v2(chunk))
        assert chunk.metadata['chunk_uid']==saved['id'] and rendered==saved['text']
        assert rendered.endswith(chunk.content)
        prefix=rendered[:-len(chunk.content)]
        klines=[x for x in prefix.splitlines(keepends=True) if x.startswith('[키워드: ')]
        assert len(klines)==1 and klines[0].rstrip().endswith(']')
        keyword=klines[0]
        no_k=prefix.replace(keyword,'',1)
        texts={'no_keywords':no_k+chunk.content, 'keywords_only':keyword+'\n'+chunk.content, 'body_only':chunk.content}
        for name,text in texts.items():
            assert text.endswith(chunk.content)
            variants[name].append({'id':saved['id'],'text':text})
        bodies[saved['id']]=chunk.content;prefixes[saved['id']]=prefix;keyword_lines[saved['id']]=keyword
    target=next(x for x in dart if x['id']==TID)
    gtarget=next(x for x in generic if x['id']==GID)
    target_chunk=next(x for x in chunks if x.metadata['chunk_uid']==TID)
    root=parser._parse_xml(str(source))
    groups=[x for x in root.iter('TABLE-GROUP') if x.get('ACLASS')=='{XBRL}CF_C']
    assert len(groups)==1
    group=groups[0]; title=' '.join(''.join(group.find('TITLE').itertext()).split())
    tables=group.findall('TABLE'); assert len(tables)==2
    caption_lines=[' '.join(''.join(e.itertext()).split()) for e in tables[0].iter('TE')]
    caption='\n'.join([title]+caption_lines)
    assert caption in gtarget['text'] and caption not in target['text']
    body=bodies[TID]; prefix=prefixes[TID]
    for value in ('1,192,112,995,578','54,210,548,833'):
        assert value in body and value in gtarget['text']
    # Every cash-flow cell, in source order, is shared by both representations.
    cells=[' '.join(''.join(e.itertext()).split()) for e in tables[1].iter() if e.tag in ('TH','TD','TE')]
    cell_tokens=tokenize_ko('\n'.join(cells))
    assert tokenize_ko(body)==cell_tokens
    after_caption=gtarget['text'].split(caption,1)[1].strip()
    generic_cell_text=after_caption.split('\n3. 연결재무제표 주석',1)[0].strip()
    assert tokenize_ko(generic_cell_text)==cell_tokens
    witness={'target':TID,'generic_target':GID,'caption':caption,'group_title':title,
             'caption_context_hint':_extract_standalone_table_context_hint(parser._build_table_object(tables[0])),
             'all_source_cells_same_token_sequence':True,'source_cell_count':len(cells),
             'raw_body':body,'prefix':prefix,'keyword_line':keyword_lines[TID],
             'generic_text':gtarget['text'],'target_metadata':target_chunk.metadata,
             'source_group_xml':etree.tostring(group,encoding='unicode'),
             'source_path':str(source),'source_sha256':sha(source),'all_1103_rendered_chunks_exact_match':True}
    write(BASE/'source_witness.json',witness)
    counter=[
        {'name':'dart_title_restored','background':'dart','target':TID,'text':prefix+title+'\n'+body},
        {'name':'dart_caption_restored','background':'dart','target':TID,'text':prefix+caption+'\n'+body},
        {'name':'body_only_caption_restored','background':'body_only','target':TID,'text':caption+'\n'+body},
        {'name':'generic_caption_removed','background':'generic','target':GID,'text':gtarget['text'].replace(caption+'\n','',1)},
        {'name':'dart_pipe_format_removed','background':'dart','target':TID,'text':prefix+body.replace(' | ','\n').replace('| ','')},
        {'name':'generic_table_cells_only','background':'generic','target':GID,'text':generic_cell_text},
    ]
    assert tokenize_ko(counter[4]['text'])==tokenize_ko(target['text'])
    controls=[{'name':'dart_target','text':target['text'],'reference':{'arm':'dart','id':TID}},
              {'name':'dart_dense_top1','text':dart[next(i for i,x in enumerate(dart) if x['id']==RID+':199:92')]['text'],'reference':{'arm':'dart','id':RID+':199:92'}},
              {'name':'dart_dual_candidate','text':dart[next(i for i,x in enumerate(dart) if x['id']==RID+':205:98')]['text'],'reference':{'arm':'dart','id':RID+':205:98'}},
              {'name':'generic_target','text':gtarget['text'],'reference':{'arm':'generic','id':GID}},
              {'name':'query','text':question['query'],'reference':{'arm':'query','index':qi}}]
    inputs=[];seen=set()
    def add(text):
        digest=text_hash(text)
        if digest in seen:return
        seen.add(digest);nt=len(encoder.encode(text,disallowed_special=()))
        assert 0<nt<=8192
        inputs.append({'hash':digest,'text':text,'tokens':nt})
    for x in controls:add(x['text'])
    # Stability controls are a distinct first call; no variant is embedded before they pass.
    batches=[list(range(len(inputs)))]
    for x in counter:add(x['text'])
    for name,data in variants.items():
        save_rows(BASE/f'{name}.jsonl.gz',data)
        for x in data:add(x['text'])
    batch=[];nt=0
    for i,row in enumerate(inputs[len(controls):],len(controls)):
        if batch and (len(batch)>=64 or nt+row['tokens']>100000):
            batches.append(batch);batch=[];nt=0
        batch.append(i);nt+=row['tokens']
    if batch:batches.append(batch)
    total=sum(x['tokens'] for x in inputs)
    assert Decimal(total)*RATE<CAP
    save_rows(BASE/'embedding_inputs.jsonl.gz',inputs)
    write(BASE/'design.json',{'question':question,'query_index':qi,'corpus_variants':list(variants),
          'counterfactuals':counter,'controls':controls,'dense_candidates':24,'bm25_candidates':24,'rrf_k':60,'final_k':12,
          'prefix_factors':'M=all generated prefix lines except keyword line; K=generated keyword line; raw parser bodies and all chunk boundaries fixed',
          'derived_analyses':['target-only prefix swap in original DART background','cross-background original text/vector swaps'],
          'scope':'single development-exposed regression; retrieval ranks only; no answer generation or adoption',
          'stability_max_l2':.001,'stability_min_cosine':.999999,'stop':'first API error, hash drift, stability failure, budget or 30-minute wall-time; no retry/resume'})
    write(BASE/'preflight.json',{'at':now(),'input_count':len(inputs),'embedding_tokens_local':total,
          'estimated_usd':str(Decimal(total)*RATE),'cap_usd':str(CAP),'provider_calls':len(batches),'batches':batches,
          'model':'text-embedding-3-large','dimensions':3072,'rate_usd_per_million':'.13','answers':0})
    paths=list(BASE.glob('*.py'))+list(BASE.glob('*.json'))+list(BASE.glob('*.gz'))
    paths += [OLD/'freeze.json',OLD/'retrieval.json',OLD/'live/queries/embedding.raw.json']
    paths += [OLD/f'{arm}_{RID}.npy' for arm in ('generic','dart')]
    write(BASE/'freeze.json',{'at':now(),'files':{str(p):sha(p) for p in paths},'original_freeze_verified':True})
    verify();event('FROZEN',inputs=len(inputs),tokens=total,estimated_usd=str(Decimal(total)*RATE),calls=len(batches))

def execute():
    import numpy as np,httpx
    from dotenv import dotenv_values
    assert not (BASE/'execution_started.json').exists(),'No rerun or resume'
    verify();write(BASE/'execution_started.json',{'at':now(),'freeze_sha256':sha(BASE/'freeze.json')})
    plan=load(BASE/'preflight.json');design=load(BASE/'design.json');inputs=rows(BASE/'embedding_inputs.jsonl.gz')
    cost=Decimal(0);calls=0;active='initializing';start=time.monotonic();halt=threading.Event();vectors=[]
    def heartbeat():
        while not halt.wait(15):event('HEARTBEAT',active=active,calls=calls,usd=str(cost),seconds=round(time.monotonic()-start))
    threading.Thread(target=heartbeat,daemon=True).start()
    key=os.getenv('OPENAI_API_KEY') or dotenv_values(ROOT/'.env').get('OPENAI_API_KEY')
    try:
        assert key,'Provider key missing'
        for bi,batch in enumerate(plan['batches']):
            verify();assert time.monotonic()-start<1800
            active=f'emb_{bi:03d}';directory=BASE/'live'/active
            texts=[inputs[i]['text'] for i in batch]
            reserve=sum(len(x.encode()) for x in texts)*RATE
            assert cost+reserve<=CAP,'Budget admission refused'
            request={'model':plan['model'],'dimensions':3072,'encoding_format':'float','input':texts}
            write(directory/'request.json',request)
            write(directory/'consumed.json',{'at':now(),'reserve_usd':str(reserve),'retries':0})
            calls+=1;event('DISPATCH',id=active,call=calls,of=plan['provider_calls'])
            tick=time.monotonic()
            try:
                with httpx.Client(transport=httpx.HTTPTransport(retries=0),timeout=120,follow_redirects=False) as client:
                    response=client.post('https://api.openai.com/v1/embeddings',headers={'Authorization':'Bearer '+key},json=request)
            except httpx.HTTPError:
                raise RuntimeError('Provider transport failure; sensitive details withheld; no retry') from None
            write(directory/'http.json',{'status':response.status_code,'seconds':time.monotonic()-tick,'request_id':response.headers.get('x-request-id')})
            assert response.status_code==200,f'HTTP {response.status_code}; no retry'
            raw=response.json();write(directory/'raw.json',raw)
            u=raw['usage'];assert u['prompt_tokens']==u['total_tokens']>0
            usd=u['prompt_tokens']*RATE;assert usd<=reserve and cost+usd<=CAP
            cost+=usd
            with (BASE/'ledger.jsonl').open('a',encoding='utf-8') as f:
                f.write(json.dumps({'id':active,'usage':u,'usd':str(usd),'model':raw['model'],'seconds':time.monotonic()-tick})+'\n')
            assert [x['index'] for x in raw['data']]==list(range(len(batch)))
            part=np.array([x['embedding'] for x in raw['data']],dtype=np.float32)
            assert part.shape==(len(batch),3072) and np.isfinite(part).all()
            vectors.extend(part)
            if bi==0:
                checks=[]
                for control,new in zip(design['controls'],part):
                    ref=control['reference']
                    if ref['arm']=='query':
                        old=np.array(load(OLD/'live/queries/embedding.raw.json')['data'][ref['index']]['embedding'],dtype=np.float32)
                    else:
                        oldrows=rows(OLD/f'{ref["arm"]}_{RID}.jsonl.gz')
                        idx=next(i for i,x in enumerate(oldrows) if x['id']==ref['id'])
                        old=np.load(OLD/f'{ref["arm"]}_{RID}.npy')[idx]
                    l2=float(np.linalg.norm(new-old));cos=float(np.dot(new,old)/(np.linalg.norm(new)*np.linalg.norm(old)))
                    checks.append({'name':control['name'],'l2':l2,'cosine':cos,'pass':l2<=design['stability_max_l2'] and cos>=design['stability_min_cosine']})
                write(BASE/'stability.json',checks)
                assert all(x['pass'] for x in checks),'Embedding provider drift; stop'
        np.save(BASE/'embeddings.npy',np.array(vectors,dtype=np.float32))
        verify();write(BASE/'execution_complete.json',{'at':now(),'usd':str(cost),'provider_calls':calls,'answers':0,'seconds':time.monotonic()-start})
        write(BASE/'raw_seal.json',{str(p):sha(p) for p in (BASE/'live').rglob('*') if p.is_file()})
        event('COMPLETE',usd=str(cost),calls=calls)
    except BaseException as e:
        write(BASE/'stopped.json',{'at':now(),'type':type(e).__name__,'message':str(e),'active':active,'calls':calls,'known_usd':str(cost),'no_retry':True})
        raise
    finally:halt.set()

def analyze():
    import numpy as np
    verify();assert (BASE/'execution_complete.json').exists()
    for path,digest in load(BASE/'raw_seal.json').items():assert sha(path)==digest
    design=load(BASE/'design.json');q=design['question']['query']
    qv=np.array(load(OLD/'live/queries/embedding.raw.json')['data'][design['query_index']]['embedding'],dtype=np.float32)
    new_vectors=np.load(BASE/'embeddings.npy');inputs=rows(BASE/'embedding_inputs.jsonl.gz')
    assert len(inputs)==len(new_vectors)
    by_hash={x['hash']:v for x,v in zip(inputs,new_vectors)}
    data={arm:rows(OLD/f'{arm}_{RID}.jsonl.gz') for arm in ('dart','generic')}
    vec={arm:np.load(OLD/f'{arm}_{RID}.npy') for arm in data}
    results=load(BASE/'baseline.json')
    for name in design['corpus_variants']:
        data[name]=rows(BASE/f'{name}.jsonl.gz')
        vec[name]=np.array([by_hash[text_hash(x['text'])] for x in data[name]],dtype=np.float32)
        results[name]=retrieve(data[name],vec[name],q,qv,TID)
    def swap(name,background,target,text,vector):
        ds=list(data[background]);vs=vec[background].copy();idx=next(i for i,x in enumerate(ds) if x['id']==target)
        ds[idx]={**ds[idx],'text':text};vs[idx]=vector
        results[name]=retrieve(ds,vs,q,qv,target)
        results[name]['intervention']={'background':background,'target':target,'target_only':True}
    for item in design['counterfactuals']:
        swap(item['name'],item['background'],item['target'],item['text'],by_hash[text_hash(item['text'])])
    for name in design['corpus_variants']:
        idx=next(i for i,x in enumerate(data[name]) if x['id']==TID)
        swap('target_only_'+name,'dart',TID,data[name][idx]['text'],vec[name][idx])
    for name,background,target,donor,donor_id in [
        ('generic_text_in_dart','dart',TID,'generic',GID),('dart_text_in_generic','generic',GID,'dart',TID)]:
        idx=next(i for i,x in enumerate(data[donor]) if x['id']==donor_id)
        swap(name,background,target,data[donor][idx]['text'],vec[donor][idx])
    write(BASE/'analysis.json',results)
    for name,value in results.items():
        t=value['target']; print(name,t['dense_rank'],t['bm25_rank'],t['rrf_rank'],t['in_top12'],flush=True)
    write(BASE/'analysis_seal.json',{'analysis_sha256':sha(BASE/'analysis.json'),'freeze_sha256':sha(BASE/'freeze.json'),'raw_seal_sha256':sha(BASE/'raw_seal.json')})

if __name__=='__main__':
    if sys.argv[1]=='prepare':
        with offline():prepare()
    elif sys.argv[1]=='execute':execute()
    elif sys.argv[1]=='analyze':
        with offline():analyze()
    else:raise ValueError('Expected prepare, execute, or analyze')
