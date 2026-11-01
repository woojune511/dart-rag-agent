"""Offline frozen 2x2: Korean analyzer package x IDF formula. No app changes."""
from __future__ import annotations
import base64
import copy
import gzip
import importlib.util
import json
import math
import os
import re
import subprocess
import sys
import threading
import time
from collections import Counter
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
PREV = OUT.parent/'tokenizer_kiwi_offline_20261022'
spec = importlib.util.spec_from_file_location('kiwi_previous_helpers',PREV/'run.py')
old = importlib.util.module_from_spec(spec)
spec.loader.exec_module(old)  # Socket connect/DNS disabled by original helpers.
prior = old.prior
ARMS = ('A12','L12','N12','NL12')
START = time.monotonic()
CHILD = None

def save(name,obj):
    p = (OUT/name).resolve()
    assert p.is_relative_to(OUT)
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

def heartbeat(phase,**kw):
    row = dict(phase=phase,elapsed_seconds=round(time.monotonic()-START,2),pid=os.getpid(),**kw)
    with (OUT/'heartbeat.jsonl').open('a',encoding='utf-8') as f:
        f.write(prior.encoded(row)+'\n')
    print(prior.encoded(row),flush=True)

old.heartbeat = heartbeat

def protect():
    paths = {str((ROOT/p).resolve().relative_to(ROOT)) for p in old.protect()}
    paths.update(str(p.relative_to(ROOT)) for p in PREV.rglob('*') if p.is_file())
    paths.update(['.git/index','.venv/pyvenv.cfg'])
    return {p:prior.sha(ROOT/p) for p in sorted(paths) if (ROOT/p).is_file()}

def preserve():
    before = prior.load(OUT/'before.json')
    changed = [p for p,h in before.items() if not (ROOT/p).is_file() or prior.sha(ROOT/p)!=h]
    status = subprocess.check_output(['git','status','--porcelain=v1','-z'],cwd=ROOT)
    result = dict(protected_files=len(before),changed=changed,unchanged=not changed,
                  git_status_equal=status==(OUT/'git_status_before.bin').read_bytes())
    save('preservation.json',result)
    assert result['unchanged'] and result['git_status_equal'],result
    return result

def java_tokens(texts,label,trace=False):
    global CHILD
    meta=prior.load(OUT/'dependency_manifest.json')
    inp,output=OUT/(label+'_input.tsv'),OUT/(label+'_output.tsv')
    with inp.open('w',encoding='utf-8',newline='\n') as f:
        for i,text in enumerate(texts):
            f.write(str(i)+'\t'+base64.b64encode(text.encode()).decode()+'\n')
    cp=';'.join([str(OUT),*(x['path'] for x in meta['files'])])
    cmd=[meta['jdk']['java'],'-Xmx1536m','-Djava.security.manager',
         '-Djava.security.policy=='+str(OUT/'offline.policy'),'-cp',cp,'NoriBatch',str(inp),str(output)]
    if trace:cmd.append(str(OUT/(label+'_trace.tsv')))
    with (OUT/(label+'_java.log')).open('w',encoding='utf-8') as log:
        CHILD=subprocess.Popen(cmd,stdout=log,stderr=log)
        code=CHILD.wait(timeout=1200)
        CHILD=None
    assert code==0,('Java failed',label,code)
    assert 'network_denial_verified' in (OUT/(label+'_java.log')).read_text(encoding='utf-8')
    rows=[]
    for i,line in enumerate(output.read_text(encoding='utf-8').splitlines()):
        num,encoded=line.split('\t')
        assert int(num)==i
        hangul=base64.b64decode(encoded).decode().split()
        # Keep legacy ASCII/number splitting exactly; no Korean segment splitting.
        rows.append(hangul+[x.lower() for x in re.findall('[a-zA-Z0-9]+',texts[i])])
    assert len(rows)==len(texts)
    return rows

def positive_idf(index):
    clone=copy.copy(index)
    frequencies=Counter(t for doc in index.doc_freqs for t in doc)
    clone.idf={t:math.log1p((index.corpus_size-n+.5)/(n+.5)) for t,n in frequencies.items()}
    return clone

def prepare():
    assert not (OUT/'protocol.json').exists()
    save('before.json',protect())
    (OUT/'git_status_before.bin').write_bytes(subprocess.check_output(['git','status','--porcelain=v1','-z'],cwd=ROOT))
    policy='grant {\n permission java.io.FilePermission "<<ALL FILES>>", "read";\n permission java.io.FilePermission "'+OUT.as_posix()+'/-", "write,delete";\n permission java.util.PropertyPermission "*", "read";\n permission java.lang.RuntimePermission "*";\n permission java.lang.reflect.ReflectPermission "*";\n};\n'
    (OUT/'offline.policy').write_text(policy,encoding='utf-8')
    p=prior.load(PREV/'protocol.json')
    protocol={
      'status':'FROZEN_BEFORE_SYNTHETIC_GATE_AND_SCORING','date':'2026-10-22',
      'hypothesis':'Nori compound-aware grammatical filtering removes false cross-boundary matches while preserving lexical compounds; positive IDF separately reduces very common-token weight. Test evidence preservation and recovery without assuming gains.',
      'cases':p['cases'],'source_context_fields':p['source_context_fields'],
      'targets_not_ranking_features':p['targets_not_ranking_features'],
      'arms':{'A12':'Legacy bigrams + rank_bm25 IDF','L12':'Legacy bigrams + positive log1p IDF','N12':'Nori package + rank_bm25 IDF','NL12':'Nori package + positive log1p IDF'},
      'analyzer':{'name':'Lucene Nori','version':'9.12.3','mode':'MIXED','unknown_unigrams':False,'discard_punctuation':True,
        'input':'Full original chunk or full original question, including spaces, punctuation and prefixes',
        'drop_left_pos':['E','J','SP','SSC','SSO','SC','SE'],
        'preserve':'All other Hangul lexical forms including MAG, MAJ, MM, XPN, XSA, XSN, XSV, verbs/adjectives and unknown words. Keep dictionary-recognized compound original and components. No guarantee of semantic disambiguation.',
        'ascii':'Ignore Nori ASCII outputs; append original regex [a-zA-Z0-9]+ lowercase to preserve existing ASCII and number multiplicities.',
        'length':'All emitted token occurrences counted, including mixed-mode overlaps; legacy rank_bm25 bag-of-words length, not full Lucene similarity.',
        'user_dictionary':None,'aliases':False,'stopwords':False,'query_expansion':False},
      'idf':{'current':'log((N-df+0.5)/(df+0.5)); negatives replaced by .25*average_idf','positive':'log1p((N-df+0.5)/(df+0.5))','fixed_k1':1.5,'fixed_b':.75,'query_tf':'Keep multiplicity','fit_scope':'All16051 chunks before explicit receipt filter'},
      'fixed':p['fixed'],
      'evaluation':'Same frozen10 answerable/26 required-unit panel,2 unscored refusals; all77 source/citation and packet audit. Review missing known witnesses for alternatives. No answer accuracy or refusal score.',
      'success_gate':'Synthetic boundary/compound/polarity/ASCII contracts must pass before corpus run. For retrieval follow-up candidate: preserve every baseline-covered unit, recover >=1 missing unit, and no confirmed new required-source regression in reviewed historical-citation loss cases. Do not activate runtime automatically.',
      'limits':{'external_model_api_calls':0,'external_model_cost_usd':0,'answers':0,'run_seconds':1800,'repetitions':1},
      'stop':'No dictionary/POS/IDF retuning after benchmark scoring; no retry of crashed scored run; failed synthetic gate stops scoring.',
      'limitations':'Development-exposed77, curated26 units and same-assistant unblinded source review. Nori package changes segmentation, compound expansion and POS filtering jointly; 2x2 isolates package vs IDF, not each linguistic choice. No full-Lucene reproduction or held-out generalization.'}
    protocol['fixed']['bm25']='Only predeclared tokenizer and IDF vary; fit full corpus; k1,b,scope fixed'
    save('protocol.json',protocol)
    inputs=[PREV/'protocol.json',PREV/'results.json',prior.EVIDENCE,prior.REVIEW,
        prior.HELPER if hasattr(prior,'HELPER') else old.HELPER,
        ROOT/'src/storage/bm25_index.py',ROOT/'src/storage/search_merge.py',
        OUT.parent/'full77_sol_top12_20261020/requests.json',OUT.parent/'full77_sol_top12_20261020/grades.jsonl']
    inputs+=list(prior.EXPORT.glob('*.jsonl.gz'))+list((prior.BASE/'live/retrieval').glob('*.json'))
    files=[Path(__file__),OUT/'NoriBatch.java',OUT/'NoriBatch.class',OUT/'test_contract.py',OUT/'offline.policy',OUT/'dependency_manifest.json']
    dep=prior.load(OUT/'dependency_manifest.json')
    files += [Path(x['path']) for x in dep['files']]+[Path(dep['jdk']['java'])]
    save('seal.json',{'protocol_sha256':prior.sha(OUT/'protocol.json'),'files':{str(x.relative_to(ROOT)):prior.sha(x) for x in inputs+files}})
    heartbeat('prepared',cases=77,arms=list(ARMS))

def run():
    assert not (OUT/'started.json').exists(),'No automatic repeated scored run'
    protocol,seal=prior.load(OUT/'protocol.json'),prior.load(OUT/'seal.json')
    assert prior.sha(OUT/'protocol.json')==seal['protocol_sha256']
    for p,h in seal['files'].items():assert prior.sha(ROOT/p)==h,p
    assert prior.load(OUT/'contract_result.json')['passed']
    save('started.json',{'pid':os.getpid(),'utc_epoch':time.time(),'argv':sys.argv})
    done=threading.Event()
    def watchdog():
        while not done.wait(30):
            heartbeat('process_alive',java_pid=CHILD.pid if CHILD else None)
            if time.monotonic()-START>1800:
                print('Hard timeout reached; terminating only experiment process tree.',flush=True)
                if CHILD:CHILD.kill()
                save('failure.json',{'status':'TIMEOUT','seconds':1800})
                os._exit(124)
    threading.Thread(target=watchdog,daemon=True).start()
    documents,ordered=old.load_documents(protocol['source_context_fields'])
    corpus=[documents[u]['text'].strip() for u in ordered]
    aindex=prior.BM25Okapi([prior.tokenize_ko(t) for t in corpus])
    saved={r['case_id']:json.loads(r['body']['input'][1]['content']) for r in prior.load(OUT.parent/'full77_sol_top12_20261020/requests.json')}
    frozen={c['id']:prior.load(prior.BASE/'live/retrieval'/f"{c['id']}.json") for c in protocol['cases']}
    original_scores={}
    for c in protocol['cases']:
        scores=aindex.get_scores(prior.tokenize_ko(c['question']))
        hits=prior.fold_scores(scores,ordered,documents,str(c['report_scope']['rcept_no']))
        expected=frozen[c['id']]['bm25']
        assert [h['uid'] for h in hits]==[h['metadata']['chunk_uid'] for h in expected]
        assert all(abs(x['score']-y['score'])<1e-8 for x,y in zip(hits,expected))
        ranking=prior.merge(frozen[c['id']]['dense'],hits,documents,40)
        packet,_=prior.packet(c,ranking[:12],documents,protocol['source_context_fields'],{h['uid'] for h in hits})
        assert packet==saved[c['id']],c['id']
        original_scores[c['id']]=scores
    save('baseline_parity.json',{'cases':77,'bm25_ranks_equal':True,'bm25_score_atol':1e-8,'saved_packets_exact':True})
    heartbeat('baseline_parity_passed',cases=77)
    texts=corpus+[c['question'] for c in protocol['cases']]
    ntokens=java_tokens(texts,'corpus')
    with gzip.open(OUT/'nori_tokens.json.gz','wt',encoding='utf-8') as f:json.dump(ntokens,f,ensure_ascii=False)
    nindex=prior.BM25Okapi(ntokens[:len(corpus)])
    indexes={'A12':aindex,'L12':positive_idf(aindex),'N12':nindex,'NL12':positive_idf(nindex)}
    save('index_stats.json',{a:{'documents':len(ordered),'tokens':sum(i.doc_len),'avgdl':i.avgdl,'vocabulary':len(i.idf),'idf_min':min(i.idf.values()),'idf_max':max(i.idf.values())} for a,i in indexes.items()})
    heartbeat('indexes_ready')
    results,explanations=[],[]
    for n,c in enumerate(protocol['cases']):
        cid,receipt=c['id'],str(c['report_scope']['rcept_no'])
        qt={a:prior.tokenize_ko(c['question']) if a in ('A12','L12') else ntokens[len(corpus)+n] for a in ARMS}
        scores={a:original_scores[cid] if a=='A12' else idx.get_scores(qt[a]) for a,idx in indexes.items()}
        dense=frozen[cid]['dense']
        streams,rankings,packets={},{},{}
        for arm in ARMS:
            streams[arm]=prior.fold_scores(scores[arm],ordered,documents,receipt)
            rankings[arm]=prior.merge(dense,streams[arm],documents,40)
            packet,omitted=prior.packet(c,rankings[arm][:12],documents,protocol['source_context_fields'],{h['uid'] for h in streams[arm]})
            assert all(d['text'] in (documents[d['chunk_id']]['text'],documents[d['chunk_id']]['text'].strip()) for d in packet['documents'])
            packets[arm]={'uids':[d['chunk_id'] for d in packet['documents']],'bytes':len(prior.encoded(packet).encode()),'omitted':omitted}
            save(f'packets/{cid}_{arm}.json',packet)
        targets=[dict(t) for t in protocol['targets_not_ranking_features'] if t['case_id']==cid]
        for target in targets:
            target['full_lexical_rank']={}
            for a in ARMS:
                full=prior.fold_scores(scores[a],ordered,documents,receipt,limit=len(ordered))
                target['full_lexical_rank'][a]=next((i+1 for i,h in enumerate(full) if h['uid']==target['uid']),None)
        probe_uids=set(h['uid'] for a in ARMS for h in streams[a][:3])|{t['uid'] for t in targets}
        for uid in sorted(probe_uids):
            explanations.append({'case_id':cid,'uid':uid,'terms':{a:old.contributions(idx,qt[a],documents[uid]['order']) for a,idx in indexes.items()}})
        results.append({'case_id':cid,'query':c['question'],'query_tokens':qt,'report_scope':c['report_scope'],
          'dense':[{'uid':h['metadata']['chunk_uid'],'score':h['score']} for h in dense],'lexical':streams,'rrf':rankings,'packets':packets,'targets':targets})
        if (n+1)%10==0 or n==76:heartbeat('retrieval_progress',complete=n+1,total=77)
    save('results.json',results)
    save('score_explanations.json',explanations)
    preservation=preserve()
    save('execution_result.json',{'status':'COMPLETE_REVIEW_PENDING','cases':77,'arms':4,'model_api_calls':0,'cost_usd':0,'answers_generated':0,'elapsed_seconds':round(time.monotonic()-START,2),'exit_code':0,'preservation':preservation})
    done.set()
    heartbeat('complete',cases=77)

if __name__=='__main__':
    try:{'prepare':prepare,'run':run,'preserve':preserve}[sys.argv[1]]()
    except Exception as exc:
        save('failure_'+sys.argv[1]+'.json',{'type':type(exc).__name__,'error':str(exc)})
        raise
