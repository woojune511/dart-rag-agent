"""Provider-free post-stop analysis; freezes dense vectors and changes BM25 only."""
from diagnose import *
import numpy as np

def main():
    verify()
    assert (BASE/'stopped.json').exists() and not (BASE/'execution_complete.json').exists()
    design=load(BASE/'design.json');q=design['question']['query']
    qv=np.array(load(OLD/'live/queries/embedding.raw.json')['data'][design['query_index']]['embedding'],dtype=np.float32)
    data={a:rows(OLD/f'{a}_{RID}.jsonl.gz') for a in ('dart','generic')}
    vec={a:np.load(OLD/f'{a}_{RID}.npy') for a in data}
    results={}
    for name in design['corpus_variants']:
        data[name]=rows(BASE/f'{name}.jsonl.gz')
        vec[name]=vec['dart']
        value=retrieve(data[name],vec[name],q,qv,TID)
        value['interpretation']='BM25-only ablation: original DART dense vectors fixed; not a re-embedded retrieval system'
        results['bm25_all_'+name]=value
    def swap(name,background,target,text,vector,label):
        ds=list(data[background]);vs=vec[background].copy();idx=next(i for i,x in enumerate(ds) if x['id']==target)
        ds[idx]={**ds[idx],'text':text};vs[idx]=vector
        results[name]=retrieve(ds,vs,q,qv,target)
        results[name]['interpretation']=label
        results[name]['intervention']={'background':background,'target':target,'target_only':True}
    for item in design['counterfactuals']:
        background=item['background'];idx=next(i for i,x in enumerate(data[background]) if x['id']==item['target'])
        swap('bm25_'+item['name'],background,item['target'],item['text'],vec[background][idx],
             'BM25-only target-text intervention; original dense vector fixed')
    for name in design['corpus_variants']:
        idx=next(i for i,x in enumerate(data[name]) if x['id']==TID)
        swap('bm25_target_only_'+name,'dart',TID,data[name][idx]['text'],vec['dart'][idx],
             'BM25-only target prefix intervention; all competitor text and original dense vectors fixed')
    for name,background,target,donor,donor_id in [
        ('generic_text_in_dart','dart',TID,'generic',GID),('dart_text_in_generic','generic',GID,'dart',TID)]:
        idx=next(i for i,x in enumerate(data[donor]) if x['id']==donor_id)
        swap(name,background,target,data[donor][idx]['text'],vec[donor][idx],
             'Original saved text AND embedding transplanted; same original query vector; all other chunks fixed')
    baseline=load(BASE/'baseline.json')
    fused=baseline['dart']['rrf_candidates'];before=fused[:21]
    counts={'above_target':len(before),'dual_channel':sum(x['dense_contribution']>0 and x['bm25_contribution']>0 for x in before),
            'dense_only':sum(x['dense_contribution']>0 and x['bm25_contribution']==0 for x in before),
            'bm25_only':sum(x['dense_contribution']==0 and x['bm25_contribution']>0 for x in before)}
    write(BASE/'offline_analysis.json',{'scope':'exploratory provider-free analysis after failed embedding stability gate',
          'no_new_provider_calls':True,'dense_counterfactual_embeddings_not_available':True,
          'rrf_above_target_breakdown':counts,'results':results})
    for name,value in {**baseline,**results}.items():
        t=value['target'];print(name,t['dense_rank'],t['bm25_rank'],t['rrf_rank'],round(t['bm25_score'],4),flush=True)
    print('RRF_COUNTS',counts,flush=True)
    write(BASE/'offline_seal.json',{'at':now(),'files':{str(p):sha(p) for p in
          [BASE/'offline_analysis.py',BASE/'offline_analysis.json',BASE/'stability.json',BASE/'stopped.json',BASE/'ledger.jsonl']}})

if __name__=='__main__':
    with offline():main()
