"""Inspect saved tokens and scores only. No new retrieval condition or analysis model."""
import base64
import gzip
import json
import math
from collections import Counter
from run import OUT,ARMS,prior,save

results=prior.load(OUT/'results.json')
stats=prior.load(OUT/'index_stats.json')
explanations=prior.load(OUT/'score_explanations.json')
text_rows=[base64.b64decode(s.split('\t')[1]).decode() for s in (OUT/'corpus_input.tsv').read_text(encoding='utf-8').splitlines()]
with gzip.open(OUT/'nori_tokens.json.gz','rt',encoding='utf-8') as f:ntokens=json.load(f)
N=16051
dfs={'bigram':Counter(t for s in text_rows[:N] for t in set(prior.tokenize_ko(s))),
     'nori':Counter(t for toks in ntokens[:N] for t in set(toks))}
term_stats={}
for kind,df in dfs.items():
    raw={t:math.log((N-n+.5)/(n+.5)) for t,n in df.items()}
    floor=.25*sum(raw.values())/len(raw)
    term_stats[kind]={'epsilon_floor':floor,'terms':{t:{'df':df.get(t,0),
        'legacy_idf':(raw[t] if raw[t]>=0 else floor) if t in raw else None,
        'positive_idf':math.log1p((N-df[t]+.5)/(df[t]+.5)) if t in raw else None}
        for t in ['매대','판매','판매대','대수','수의','현금','흐름','현금흐름표','의','에','하','2023','연결','consolidated']}}
diagnostics=[]
for cid in ['HYU_T2_010','MIX_T3_048','CEL_T3_040','SKH_T1_060']:
    r=next(r for r in results if r['case_id']==cid)
    probes=[]
    for x in explanations:
        if x['case_id']!=cid:continue
        arm_ranks={a:{'bm25_rank':next((i+1 for i,h in enumerate(r['lexical'][a]) if h['uid']==x['uid']),None),
                      'rrf_rank':next((i+1 for i,h in enumerate(r['rrf'][a]) if h['uid']==x['uid']),None),
                      'packet':x['uid'] in r['packets'][a]['uids'],
                      'top_contributions':x['terms'][a][:10],
                      'maedae_contribution':sum(t['contribution'] for t in x['terms'][a] if t['term']=='매대')}
                   for a in ARMS}
        probes.append({'uid':x['uid'],'arms':arm_ranks})
    diagnostics.append({'case_id':cid,'question':r['query'],'tokens':r['query_tokens'],'probes':probes})
sales=next(r for r in results if r['case_id']=='HYU_T2_010')
false_match_probes=[]
for uid in ['20240313001451:46:6','20240313001451:57:17']:
    pos=next(h['winning_view_index'] for h in sales['lexical']['A12'] if h['uid']==uid)
    by_arm={}
    for a in ARMS:
        kind='bigram' if a in ('A12','L12') else 'nori'
        toks=prior.tokenize_ko(text_rows[pos]) if kind=='bigram' else ntokens[pos]
        freq=Counter(toks);terms=[]
        for term,qtf in Counter(sales['query_tokens'][a]).items():
            f=freq[term]
            if not f:continue
            df=dfs[kind][term]
            raw=math.log((N-df+.5)/(df+.5))
            weight=math.log1p((N-df+.5)/(df+.5)) if a in ('L12','NL12') else (raw if raw>=0 else term_stats[kind]['epsilon_floor'])
            value=weight*f*2.5/(f+1.5*(.25+.75*len(toks)/stats[a]['avgdl']))*qtf
            terms.append({'term':term,'contribution':value,'doc_tf':f,'query_tf':qtf})
        total=sum(t['contribution'] for t in terms)
        found=next((h for h in sales['lexical'][a] if h['uid']==uid),None)
        if found:assert abs(total-found['score'])<1e-8
        by_arm[a]={'score':total,'terms':sorted(terms,key=lambda t:-t['contribution']),
            'bm25_rank':next((i+1 for i,h in enumerate(sales['lexical'][a]) if h['uid']==uid),None),
            'rrf_rank':next((i+1 for i,h in enumerate(sales['rrf'][a]) if h['uid']==uid),None),
            'dense_rank':next((i+1 for i,h in enumerate(sales['dense']) if h['uid']==uid),None),
            'in_packet':uid in sales['packets'][a]['uids']}
    false_match_probes.append({'uid':uid,'arms':by_arm})
save('mechanism_diagnostics.json',{'method':'Saved token counts and fixed-score arithmetic, not a new ranking run','term_stats':term_stats,'cases':diagnostics,'false_match_probes':false_match_probes})
print(json.dumps({'false_match_probes':[{**x,'arms':{a:{**v,'terms':v['terms'][:4]} for a,v in x['arms'].items()}} for x in false_match_probes]},ensure_ascii=False))
