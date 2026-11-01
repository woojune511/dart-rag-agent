"""Analyze fixed outputs and token statistics only; no new ranking policy."""
import gzip
import json
import math
from collections import Counter
from run import OUT, PREV, prior, save, SEGMENT, HANGUL

results = {r['case_id']:r for r in prior.load(OUT/'results.json')}
with gzip.open(OUT/'morphology_cache.json.gz','rt',encoding='utf-8') as f:
    cache = json.load(f)

def tokens(text):
    return [t for s in SEGMENT.findall(text) for t in (cache[s]['forms'] if HANGUL.fullmatch(s) else [s.lower()])]

# Compute document frequencies from saved original exports, without querying a store.
df = Counter()
n = total = 0
for p in sorted(prior.EXPORT.glob('*.jsonl.gz')):
    with gzip.open(p,'rt',encoding='utf-8') as f:
        for line in f:
            r=json.loads(line)
            ts=tokens(r['text'].strip())
            df.update(set(ts))
            total += len(ts)
            n += 1
idf={t:math.log(n-f+0.5)-math.log(f+0.5) for t,f in df.items()}
average_idf=sum(idf.values())/len(idf)
stats=prior.load(OUT/'index_stats.json')['K12']
assert (n,total,len(df))==(stats['documents'],stats['tokens'],stats['vocabulary'])
watch=['의','ᆫ','어','하','주','에','을','현금흐름표','현금','흐름','배당금','판매','매대','차입금']
terms={t:{'df':df[t],'documents':n,'raw_idf':idf.get(t),'effective_idf':None if t not in idf else (0.25*average_idf if idf[t]<0 else idf[t]),'negative_idf_floor_applied':t in idf and idf[t]<0} for t in watch}

samples={s:{'bigram':prior.tokenize_ko(s),'kiwi':cache[s]} for s in ['판매대수의','금융상품판매대리','현금흐름표에서','현금흐름','줘','유형자산','무형자산'] if s in cache}
aid={r['case_id']:r for r in prior.load(OUT/'all77_source_audit.json')['cases']}
stages=[]
for cid,a in aid.items():
    for uid in a['arms']['K12']['historical_cited_sources_lost']:
        row={'case_id':cid,'uid':uid,'group':a['historical_group'],'arms':{}}
        for arm in ['A12','K12']:
            rr=results[cid]
            row['arms'][arm]={'dense_rank':next((i+1 for i,h in enumerate(rr['dense']) if h['uid']==uid),None),
                'bm25_rank':next((i+1 for i,h in enumerate(rr['lexical'][arm]) if h['uid']==uid),None),
                'rrf_rank':next((i+1 for i,h in enumerate(rr['rrf'][arm]) if h['uid']==uid),None),
                'byte_omitted':uid in rr['packets'][arm]['omitted']}
        stages.append(row)
save('mechanism_diagnostics.json',{'scope':'Fixed-run output analysis and original-export document frequencies; no reranking, additional arm or model invocation.',
    'morphology_samples':samples,'bm25_idf':{'average_idf':average_idf,'epsilon':0.25,'terms':terms},
    'lost_historical_citation_stages':stages})
print(prior.encoded({'samples':samples,'idf_terms':terms}))
