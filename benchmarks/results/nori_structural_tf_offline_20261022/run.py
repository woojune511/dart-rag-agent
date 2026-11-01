"""Frozen structural-field TF ablation, offline artifact only. No app/store clients."""
from __future__ import annotations
import base64
import copy
import gzip
import importlib.util
import json
import os
import subprocess
import sys
import threading
import time
from collections import Counter
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
BASE = OUT.parent / 'tokenizer_nori_idf_offline_20261022'
spec = importlib.util.spec_from_file_location('saved_nori_helpers', BASE/'run.py')
previous = importlib.util.module_from_spec(spec)
spec.loader.exec_module(previous)
old, prior = previous.old, previous.prior  # This import disables Python sockets/DNS.
START = time.monotonic()
CHILD = None
ARMS = ('N12', 'F12')

def save(name, value):
    p = (OUT/name).resolve()
    assert p.is_relative_to(OUT)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')

def heartbeat(phase, **kwargs):
    row = dict(phase=phase, elapsed_seconds=round(time.monotonic()-START,2), pid=os.getpid(), **kwargs)
    with (OUT/'heartbeat.jsonl').open('a',encoding='utf-8') as f:
        f.write(prior.encoded(row)+'\n')
    print(prior.encoded(row),flush=True)

old.heartbeat = heartbeat

def field_max(zones):
    """Keep body and unique label terms; no within-field or other-prefix suppression."""
    b,r,v,o = zones
    keys = b.keys() | r.keys() | v.keys()
    return o + Counter({t:max(b[t],r[t],v[t]) for t in keys})

def java_args():
    deps = prior.load(BASE/'dependency_manifest.json')
    cp = ';'.join([str(OUT),*(x['path'] for x in deps['files'])])
    return deps, cp

def tokenize(input_path, output_path, log_path):
    global CHILD
    deps, cp = java_args()
    cmd = [deps['jdk']['java'],'-Xmx1536m','-Djava.security.manager',
           '-Djava.security.policy=='+str(OUT/'offline.policy'),'-cp',cp,
           'NoriFields',str(input_path),str(output_path)]
    with log_path.open('w',encoding='utf-8') as log:
        CHILD = subprocess.Popen(cmd, stdout=log, stderr=log)
        code = CHILD.wait(timeout=1200)
        CHILD = None
    assert code == 0, code
    assert 'network_denial_verified' in log_path.read_text(encoding='utf-8')

def read_fields(path):
    for i,line in enumerate(path.open(encoding='utf-8')):
        row = line.rstrip('\n').split('\t')
        assert len(row)==7 and int(row[0])==i
        full = base64.b64decode(row[1]).decode().split()
        zones = [Counter(base64.b64decode(x).decode().split()) for x in row[2:6]]
        assert Counter(full) == sum(zones,Counter())
        yield full,zones,int(row[6])

def prepare():
    assert not (OUT/'protocol.json').exists(), 'Protocol already frozen'
    before = previous.protect()
    before.update({str(p.relative_to(ROOT)):prior.sha(p) for p in BASE.rglob('*') if p.is_file()})
    save('before.json', before)
    (OUT/'git_status_before.bin').write_bytes(subprocess.check_output(['git','status','--porcelain=v1','-z'],cwd=ROOT))
    policy = 'grant {\n permission java.io.FilePermission "<<ALL FILES>>", "read";\n permission java.io.FilePermission "'+OUT.as_posix()+'/-", "write,delete";\n permission java.util.PropertyPermission "*", "read";\n permission java.lang.RuntimePermission "*";\n permission java.lang.reflect.ReflectPermission "*";\n};\n'
    (OUT/'offline.policy').write_text(policy,encoding='utf-8')
    p = prior.load(BASE/'protocol.json')
    protocol = {
        'status':'FROZEN_BEFORE_CONTRACT_TEST_AND_SCORING','date':'2026-10-22',
        'hypothesis':'Duplicated structural row/value labels can add TF unrelated to independent source evidence; separating their aggregation may recover required evidence without losing existing evidence.',
        'arms':{'N12':'Saved Nori current-IDF baseline, exact reconstruction required',
                'F12':'Nori field-max TF only; original IDF and original length normalization frozen'},
        'cases':p['cases'],'source_context_fields':p['source_context_fields'],
        'targets_not_ranking_features':p['targets_not_ranking_features'],
        'analyzer':p['analyzer'],
        'treatment':{
            'fields':['table_row_labels','table_value_labels'],
            'formula':'tf_F(t,d)=tf_other_prefix(t,d)+max(tf_body(t,d),tf_row_label(t,d),tf_value_label(t,d))',
            'partition':'Only the VALUE ranges of the two named bracketed fields before the first blank line; remaining prefix tokens are O; body is after that separator. No valid prefix means unchanged. Nori runs on ORIGINAL complete text; original token offsets assign fields, UTF-16 aligned. ASCII regex tokens assigned by their original offsets. Boundary-crossing tokens kept in O.',
            'unchanged':'Do not remove unique label terms, within-field multiplicity, mixed-mode overlaps, common keyword prefixes, captions, periods, units, source text or metadata. No new words, channels, scope preference, user dictionary or stopwords.',
            'idf_and_length':'Reuse exact N12 IDF dictionary, original doc_len/avgdl, k1=1.5,b=.75,query tokens and multiplicity. Change doc_freqs ONLY. This is a controlled TF ablation, NOT a normally rebuilt BM25 index.',
            'limits':'Token-level multiset union is a proxy for duplicated field representation, not verified row-identity or semantic deduplication. Equal words can be independent occurrences; separate labels absent from body retain max field count.'},
        'fixed':{'dense':'Exact saved Dense16; no embeddings','bm25_candidates':24,'rrf':'Equal RRF60, original stable ordering','scope':'Explicit report receipt only','final_sources':12,'packet_bytes':65536,'packet':'Original complete source chunks and original metadata; unchanged no-refill byte packing','generation':False},
        'evaluation':'All77 paired candidate/final12/packet audit; frozen10 answerable cases/26 units plus2 unscored refusal controls; historical answer-citation losses newly caused relative to N12 reviewed against exact packet sources. Rank/source preservation is not answer accuracy.',
        'success_gate':'Both requested targets restored to final12 AND delivered packet; no baseline-covered panel unit lost and no confirmed new required-source loss in reviewed changed cases. A tie-order-only target recovery is reported separately and is not semantic scope selection.',
        'stop':'One frozen F12 policy only. No score-driven tuning or added treatment after outcomes. Stop scoring if contract/parity fails.',
        'limits':{'external_model_api_calls':0,'cost_usd':0,'answers':0,'scored_runs':1,'timeout_seconds':1800},
        'limitations':'Development-exposed77, incomplete known-witness annotations, unblinded assistant source review, no generated answers, no held-out generalization. Original length deliberately fixed despite lower effective TF.'}
    save('protocol.json',protocol)
    deps,cp=java_args()
    javac=str(Path(deps['jdk']['java']).with_name('javac.exe'))
    compiled=subprocess.run([javac,'-encoding','UTF-8','-cp',cp,str(OUT/'NoriFields.java')],capture_output=True,text=True,encoding='utf-8')
    (OUT/'compile.log').write_text(compiled.stdout+compiled.stderr,encoding='utf-8')
    assert compiled.returncode==0,compiled.stderr
    inputs=[Path(__file__),OUT/'NoriFields.java',OUT/'NoriFields.class',OUT/'test_contract.py',OUT/'offline.policy',
        BASE/'run.py',old.OUT/'run.py',old.HELPER,BASE/'protocol.json',BASE/'results.json',BASE/'nori_tokens.json.gz',BASE/'corpus_input.tsv',
        BASE/'dependency_manifest.json',BASE/'known_witness_panel.json',prior.EVIDENCE,prior.REVIEW,
        ROOT/'src/storage/bm25_index.py',ROOT/'src/storage/search_merge.py',
        OUT.parent/'full77_sol_top12_20261020/grades.jsonl',Path(deps['jdk']['java']),*[Path(x['path']) for x in deps['files']]]
    inputs+=list(prior.EXPORT.glob('*.jsonl.gz'))+list((prior.BASE/'live/retrieval').glob('*.json'))
    save('seal.json',{'protocol_sha256':prior.sha(OUT/'protocol.json'),'files':{str(p.relative_to(ROOT)):prior.sha(p) for p in inputs}})
    heartbeat('prepared',cases=77,protected_files=len(before))

def preserve():
    before = prior.load(OUT/'before.json')
    changed = [p for p,h in before.items() if not (ROOT/p).is_file() or prior.sha(ROOT/p)!=h]
    status = subprocess.check_output(['git','status','--porcelain=v1','-z'],cwd=ROOT)
    active={str(p.relative_to(ROOT)) for p in prior.ACTIVE.rglob('*') if p.is_file()}
    original={p for p in before if p.replace('\\','/').startswith('data/app_full11_2023_v12_20261017/')}
    value={'protected_files':len(before),'changed':changed,'git_status_equal':status==(OUT/'git_status_before.bin').read_bytes(),
           'active_store_files':len(active),'active_store_file_set_equal':active==original,'env_unchanged':prior.sha(ROOT/'.env')==before['.env']}
    save('preservation.json',value)
    assert not changed and value['git_status_equal'] and value['active_store_file_set_equal'] and value['env_unchanged'],value
    return value

def run():
    assert not (OUT/'started.json').exists(),'No repeated scored run'
    p,seal=prior.load(OUT/'protocol.json'),prior.load(OUT/'seal.json')
    assert prior.sha(OUT/'protocol.json')==seal['protocol_sha256']
    for path,h in seal['files'].items():assert prior.sha(ROOT/path)==h,path
    assert prior.load(OUT/'contract_result.json')['passed']
    save('started.json',{'pid':os.getpid(),'utc_epoch':time.time(),'argv':sys.argv})
    done=threading.Event()
    def watchdog():
        while not done.wait(30):
            heartbeat('process_alive',java_pid=CHILD.pid if CHILD else None)
            if time.monotonic()-START>1800:
                if CHILD:CHILD.kill()
                save('failure.json',{'status':'TIMEOUT'})
                os._exit(124)
    threading.Thread(target=watchdog,daemon=True).start()
    docs,ordered=old.load_documents(p['source_context_fields'])
    with gzip.open(BASE/'nori_tokens.json.gz','rt',encoding='utf-8') as f:tokens=json.load(f)
    for i,line in enumerate((BASE/'corpus_input.tsv').open(encoding='utf-8')):
        n,encoded=line.rstrip('\n').split('\t')
        expected=docs[ordered[i]]['text'].strip() if i<len(ordered) else p['cases'][i-len(ordered)]['question']
        assert int(n)==i and base64.b64decode(encoded).decode()==expected
    assert i+1==len(tokens)==16128
    tokenize(BASE/'corpus_input.tsv',OUT/'fields.tsv',OUT/'java.log')
    nindex=prior.BM25Okapi(tokens[:len(ordered)])
    findex=copy.copy(nindex)
    findex.doc_freqs=[]
    counts=Counter()
    probes={t['uid'] for t in p['targets_not_ranking_features']} | {'20240318000913:518:358','20240318000913:917:320','20240318000913:918:321','20240312000736:258:130','20240312000736:477:93','20240312000736:503:119','20240312000736:504:120'}
    target_fields={}
    for i,(full,zones,nfields) in enumerate(read_fields(OUT/'fields.tsv')):
        assert full==tokens[i],('Nori token parity',i)
        before=Counter(full)
        after=field_max(zones)
        assert before.keys()==after.keys() and all(0<after[t]<=before[t] for t in before)
        counts['tokens_checked']+=len(full)
        if i>=len(ordered):
            assert before==after,'Query must remain unchanged'
            continue
        findex.doc_freqs.append(dict(after))
        counts['chunks']+=1
        counts['chunks_with_labels']+=bool(nfields)
        counts['chunks_tf_changed']+=before!=after
        counts['original_tf_sum']+=sum(before.values())
        counts['effective_tf_sum']+=sum(after.values())
        counts['label_only_terms_preserved']+=sum(t not in zones[0] for t in zones[1].keys()|zones[2].keys())
        if ordered[i] in probes:
            target_fields[ordered[i]]={'fields':dict(zip(('body','row_labels','value_labels','other_prefix'),[dict(z) for z in zones])),'old_tf':dict(before),'new_tf':dict(after),'length':nindex.doc_len[i]}
    assert i+1==len(tokens) and len(findex.doc_freqs)==len(ordered)
    assert findex.idf is nindex.idf and findex.doc_len is nindex.doc_len and findex.avgdl==nindex.avgdl
    save('field_audit.json',{'counts':counts,'all16128_full_token_lists_equal':True,'all_query_terms_and_multiplicity_equal':True,'all_document_term_sets_equal':True,'idf_and_length_identity':True,'targets':target_fields})
    heartbeat('field_parity_passed',**dict(counts))
    saved={r['case_id']:r for r in prior.load(BASE/'results.json')}
    results=[]
    for i,c in enumerate(p['cases']):
        cid,receipt=c['id'],str(c['report_scope']['rcept_no'])
        frozen=prior.load(prior.BASE/'live/retrieval'/f'{cid}.json')
        dense=frozen['dense']
        assert [{'uid':d['metadata']['chunk_uid'],'score':d['score']} for d in dense]==saved[cid]['dense']
        qt=tokens[len(ordered)+i]
        assert qt==saved[cid]['query_tokens']['N12']
        streams,rrfs,packets={},{},{}
        scores={a:idx.get_scores(qt) for a,idx in (('N12',nindex),('F12',findex))}
        for arm in ARMS:
            streams[arm]=prior.fold_scores(scores[arm],ordered,docs,receipt)
            rrfs[arm]=prior.merge(dense,streams[arm],docs,40)
            packet,omitted=prior.packet(c,rrfs[arm][:12],docs,p['source_context_fields'],{h['uid'] for h in streams[arm]})
            packets[arm]={'uids':[d['chunk_id'] for d in packet['documents']],'bytes':len(prior.encoded(packet).encode()),'omitted':omitted}
            for d in packet['documents']:assert d['text'] in (docs[d['chunk_id']]['text'],docs[d['chunk_id']]['text'].strip())
            save(f'packets/{cid}_{arm}.json',packet)
        assert streams['N12']==saved[cid]['lexical']['N12'],('BM25 parity',cid)
        assert rrfs['N12']==saved[cid]['rrf']['N12'],('RRF parity',cid)
        assert packets['N12']==saved[cid]['packets']['N12'],('packet parity',cid)
        assert prior.load(OUT/f'packets/{cid}_N12.json')==prior.load(BASE/f'packets/{cid}_N12.json')
        targets=[]
        for t in p['targets_not_ranking_features']:
            if t['case_id']!=cid:continue
            row=dict(t,arms={})
            for arm in ARMS:
                ranking=prior.fold_scores(scores[arm],ordered,docs,receipt,limit=len(ordered))
                row['arms'][arm]={'bm25_rank':next((j+1 for j,h in enumerate(ranking) if h['uid']==t['uid']),None),
                     'score':float(scores[arm][docs[t['uid']]['order']]),
                     'rrf_rank':next((j+1 for j,h in enumerate(rrfs[arm]) if h['uid']==t['uid']),None),
                     'in_packet':t['uid'] in packets[arm]['uids']}
            targets.append(row)
        explain=[]
        if any(t['case_id']==cid for t in p['targets_not_ranking_features']):
            selected_probes={h['uid'] for a in ARMS for h in rrfs[a][:16]} | {t['uid'] for t in targets}
            for uid in sorted(selected_probes):
                j=docs[uid]['order']
                term_rows={}
                for a,idx in (('N12',nindex),('F12',findex)):
                    # Avoid rescoring the whole corpus for each contribution.
                    rows=[]
                    for term,qtf in Counter(qt).items():
                        tf=idx.doc_freqs[j].get(term,0)
                        if tf:
                            contribution=(idx.idf.get(term) or 0)*tf*(idx.k1+1)/(tf+idx.k1*(1-idx.b+idx.b*idx.doc_len[j]/idx.avgdl))*qtf
                            rows.append({'term':term,'query_tf':qtf,'document_tf':tf,'contribution':contribution})
                    assert abs(sum(x['contribution'] for x in rows)-scores[a][j])<1e-8
                    term_rows[a]=rows
                explain.append({'uid':uid,'length':nindex.doc_len[j],'terms':term_rows})
        results.append({'case_id':cid,'query':c['question'],'query_tokens':qt,'report_scope':c['report_scope'],
            'dense':saved[cid]['dense'],'lexical':streams,'rrf':rrfs,'packets':packets,'targets':targets,'explanations':explain})
        if (i+1)%10==0 or i==76:heartbeat('scored',complete=i+1,total=77)
    save('results.json',results)
    save('baseline_parity.json',{'cases':77,'bm25_exact':True,'rrf_exact':True,'packet_exact':True})
    preservation=preserve()
    save('execution_result.json',{'status':'COMPLETE_SOURCE_REVIEW_PENDING','cases':77,'treatments':1,'external_model_api_calls':0,'cost_usd':0,'answers':0,'elapsed_seconds':round(time.monotonic()-START,2),'preservation':preservation})
    done.set()
    heartbeat('complete',cases=77)

if __name__=='__main__':
    try:{'prepare':prepare,'run':run,'preserve':preserve}[sys.argv[1]]()
    except Exception as exc:
        save('failure_'+sys.argv[1]+'.json',{'type':type(exc).__name__,'error':str(exc)})
        raise
