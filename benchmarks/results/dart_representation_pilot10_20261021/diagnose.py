"""Post-run source/rank diagnosis, strictly offline and no changed retrieval."""
from common import *
import gzip

def main():
    import numpy as np
    from rank_bm25 import BM25Okapi
    from src.storage.bm25_index import tokenize_ko
    import run
    run.verify()
    qs=load(BASE/'rubric.json')['questions'];tr=load(BASE/'retrieval.json')
    qv=np.array([d['embedding'] for d in load(BASE/'live/queries/embedding.raw.json')['data']],dtype=np.float32)
    results=[]
    for c in load(BASE/'corpus_manifest.json')['corpora']:
        ds=run.rows(c['path']);v=np.load(BASE/f'{c["arm"]}_{c["rcept_no"]}.npy');bm=BM25Okapi([tokenize_ko(d['text']) for d in ds])
        for qi,q in enumerate(qs):
            if q['company']!=c['company'] or q['kind'] not in ('capex','inventory'):continue
            t=next(x for x in tr if x['id']==q['id'] and x['arm']==c['arm'])
            distances=np.sum((v-qv[qi])**2,axis=1);bs=bm.get_scores(tokenize_ko(q['query']))
            dense=sorted(range(len(ds)),key=lambda i:(float(distances[i]),i));lex=sorted(range(len(ds)),key=lambda i:(-float(bs[i]),i))
            scores={}
            for order in (dense[:24],[i for i in lex[:24] if bs[i]>0]):
                for rank,i in enumerate(order,1):scores[i]=scores.get(i,0)+1/(60+rank)
            fused=sorted(scores,key=lambda i:scores[i],reverse=True)
            assert [ds[i]['id'] for i in fused[:12]]==[x['id'] for x in t['rrf_top12']]
            for field,value in q['gold'].items():
                if not field.endswith('_krw') or field=='sum_krw':continue
                for i,d in enumerate(ds):
                    if f'{value:,}' not in d['text']:continue
                    results.append({'id':q['id'],'arm':c['arm'],'field':field,'chunk_id':d['id'],'dense_rank_all':dense.index(i)+1,'bm25_rank_all':lex.index(i)+1,
                                    'in_candidates':i in scores,'rrf_rank_candidates':fused.index(i)+1 if i in scores else None,'in_top12':i in fused[:12],'in_packet':d['id'] in t['selected'],
                                    'source_context':d['metadata'],'exact_value_match_only':True})
    write(BASE/'rank_diagnosis.json',results)
    for r in results:print(r['id'],r['arm'],r['field'],r['chunk_id'],'dense',r['dense_rank_all'],'bm25',r['bm25_rank_all'],'rrf',r['rrf_rank_candidates'],'packet',r['in_packet'])

if __name__=='__main__':
    with offline():main()
